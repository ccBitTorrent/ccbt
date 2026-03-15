"""Unit tests for tonic link generation and parsing."""

from __future__ import annotations

import pytest

from ccbt.core.tonic_link import generate_tonic_link, parse_tonic_link

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_tonic_link_round_trip() -> None:
    """Generated tonic links should parse back into their original data."""
    info_hash = b"1" * 32
    allowlist_hash = b"2" * 32

    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="demo-folder",
        trackers=["udp://tracker.example:80/announce"],
        git_refs=["abc123"],
        sync_mode="best_effort",
        source_peers=["peer-a", "peer-b"],
        allowlist_hash=allowlist_hash,
    )

    parsed = parse_tonic_link(link)

    assert parsed.info_hash == info_hash
    assert parsed.display_name == "demo-folder"
    assert parsed.trackers == ["udp://tracker.example:80/announce"]
    assert parsed.git_refs == ["abc123"]
    assert parsed.sync_mode == "best_effort"
    assert parsed.source_peers == ["peer-a", "peer-b"]
    assert parsed.allowlist_hash == allowlist_hash


def test_tonic_link_rejects_invalid_mode() -> None:
    """Parser should reject invalid sync modes."""
    link = f"tonic?:xt=urn:xet:{(b'1' * 32).hex()}&mode=invalid"

    with pytest.raises(ValueError, match="Invalid sync mode"):
        parse_tonic_link(link)


def test_tonic_link_requires_xet_target() -> None:
    """Parser should require an xt=urn:xet target."""
    with pytest.raises(ValueError, match="missing xt=urn:xet"):
        parse_tonic_link("tonic?:dn=demo")


def test_tonic_link_rejects_wrong_hash_length() -> None:
    """Parser should reject non-32-byte workspace identifiers."""
    short_hash = b"abc".hex()

    with pytest.raises(ValueError, match="Info hash must be 32 bytes"):
        parse_tonic_link(f"tonic?:xt=urn:xet:{short_hash}")
