"""Unit tests for authenticated swarm revocation parsing."""

from __future__ import annotations

import json

import pytest

from ccbt.security.swarm_revocation import (
    SwarmRevocationProfile,
    allow_after_parse_failure,
    load_swarm_revocation_cache,
    load_swarm_revocation_profile,
    parse_swarm_revocation_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_parse_swarm_revocation_payload_supports_schema_fields() -> None:
    payload = {
        "revoked_fingerprints": ["ABCD", "1234"],
        "revoked_swarm_ids": ["aaaa", "bbbb"],
        "reason_code": "manual",
    }
    parsed = parse_swarm_revocation_payload(payload)

    assert parsed.reason_code == "manual"
    assert parsed.is_revoked_fingerprint("abcd")
    assert parsed.is_revoked_swarm_id("AAAA")


def test_parse_swarm_revocation_rejects_bad_types() -> None:
    with pytest.raises(ValueError):
        parse_swarm_revocation_payload({"revoked_fingerprints": "no-list"})


def test_load_swarm_revocation_profile_from_disk(tmp_path) -> None:
    payload = {
        "revoked_fingerprints": ["deadbeef"],
        "revoked_swarm_ids": ["abab"],
    }
    path = tmp_path / "revocation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parsed = load_swarm_revocation_profile(path)

    assert isinstance(parsed, SwarmRevocationProfile)
    assert parsed.is_revoked_fingerprint("DEADBEEF")


def test_load_swarm_revocation_cache_surfaces_parse_errors(tmp_path) -> None:
    path = tmp_path / "revocation.json"
    path.write_text("{}", encoding="utf-8")

    cache, parse_error = load_swarm_revocation_cache(path)
    assert cache is not None
    assert parse_error is False

    invalid = tmp_path / "bad-revocation.json"
    invalid.write_text('{"revoked_fingerprints": "oops"}', encoding="utf-8")

    cache, parse_error = load_swarm_revocation_cache(invalid, stale_tolerant=True)
    assert cache is None
    assert parse_error is True

    with pytest.raises(ValueError):
        load_swarm_revocation_cache(invalid, stale_tolerant=False)


def test_parse_failure_policy_keeps_strict_hard_fails_and_opportunistic_soft_fails() -> None:
    assert not allow_after_parse_failure(
        strict_mode=True,
        stale_cache_present=False,
        parse_error=True,
    )
    assert allow_after_parse_failure(
        strict_mode=False,
        stale_cache_present=True,
        parse_error=True,
    )
    assert not allow_after_parse_failure(
        strict_mode=False,
        stale_cache_present=False,
        parse_error=True,
        fail_closed_on_parse_errors=True,
    )
