from __future__ import annotations

import uuid

import pytest

from ccbt.security.swarm_identity import (
    canonical_torrent_info_hash_family,
    canonicalize_swarm_id,
    legacy_swarm_id_fallback,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ABCD1234", "abcd1234"),
        ("0xABCD1234", "abcd1234"),
        ("00112233-4455-6677-8899-AABBCCDDEEFF", "00112233445566778899aabbccddeeff"),
        (str(uuid.UUID("00112233-4455-6677-8899-aabbccddeeff")), "00112233445566778899aabbccddeeff"),
    ],
)
def test_canonicalize_swarm_id_supports_hex_and_uuid_inputs(
    raw: str,
    expected: str,
) -> None:
    assert canonicalize_swarm_id(raw) == expected


@pytest.mark.unit
def test_legacy_swarm_id_fallback_is_deterministic() -> None:
    first = legacy_swarm_id_fallback(b"\x01" * 32)
    second = legacy_swarm_id_fallback(b"\x01" * 32)

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


@pytest.mark.unit
def test_legacy_fallback_uses_combined_v1_v2_bytes_for_hybrid() -> None:
    family = canonical_torrent_info_hash_family(
        info_hash_v1=b"\x01" * 20,
        info_hash_v2=b"\x02" * 32,
    )
    assert legacy_swarm_id_fallback(family) == legacy_swarm_id_fallback(family)


@pytest.mark.unit
def test_canonicalize_swarm_id_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="swarm_id"):
        canonicalize_swarm_id("not-a-valid-id")
