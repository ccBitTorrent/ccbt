from __future__ import annotations

from pathlib import Path

import pytest

from ccbt.security.key_manager import Ed25519KeyManager
from ccbt.security.swarm_auth_contract import (
    ALLOWED_TRUST_PROOF_HINTS,
    SWARM_AUTH_PREFIX,
    build_swarm_auth_extension,
    build_swarm_auth_message,
    evaluate_swarm_auth_verification_order,
    parse_swarm_auth_dict,
)
from ccbt.security.swarm_identity import canonicalize_swarm_id

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.fixture
def key_manager(tmp_path: Path) -> Ed25519KeyManager:
    return Ed25519KeyManager(key_dir=tmp_path / "swarm-auth")


def _fixed_peer_and_info() -> tuple[bytes, bytes]:
    return b"\x01" * 20, b"\x02" * 20


def _make_extension(
    swarm_id: str,
    peer_id: bytes,
    info_hash: bytes | tuple[bytes, bytes],
    timestamp: int,
    transport_hint: str,
    key_manager: Ed25519KeyManager,
    trust_hint: str | None = None,
) -> tuple[dict, bytes, bytes]:
    payload = build_swarm_auth_message(
        swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint=transport_hint,
    )
    signature = key_manager.sign_message(payload)
    extension = build_swarm_auth_extension(
        swarm_id=swarm_id,
        public_key=key_manager.get_public_key_bytes(),
        signature=signature,
        timestamp=timestamp,
        trust_proof_hint=trust_hint,
    )
    return extension, payload, signature


def test_build_swarm_auth_message_contract_and_lengths() -> None:
    peer_id, info_hash = _fixed_peer_and_info()
    swarm_id = canonicalize_swarm_id("aa112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")
    timestamp = 1_700_000_000

    payload = build_swarm_auth_message(
        swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint="Plain",
    )

    assert payload.startswith(SWARM_AUTH_PREFIX)
    expected = (
        len(SWARM_AUTH_PREFIX)
        + len(bytes.fromhex(swarm_id))
        + 20
        + 20
        + 8
        + len(b"plain")
    )
    assert len(payload) == expected


def test_build_swarm_auth_message_supports_hybrid_family() -> None:
    peer_id, info_hash_v1 = _fixed_peer_and_info()
    info_hash_v2 = b"\x33" * 32
    swarm_id = canonicalize_swarm_id("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")
    timestamp = 1_700_000_050

    payload = build_swarm_auth_message(
        swarm_id,
        peer_id=peer_id,
        info_hash=(info_hash_v1, info_hash_v2),
        timestamp=timestamp,
        transport_hint="tls",
    )
    expected = (
        len(SWARM_AUTH_PREFIX)
        + len(bytes.fromhex(swarm_id))
        + len(peer_id)
        + len(info_hash_v1)
        + len(info_hash_v2)
        + 8
        + len(b"tls")
    )
    assert len(payload) == expected


def test_swarm_auth_extension_round_trip_with_ed25519_signing(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id, info_hash = _fixed_peer_and_info()
    swarm_id = "f" * 64
    timestamp = 1_700_000_001

    extension, payload, signature = _make_extension(
        swarm_id=swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint="mse",
        key_manager=key_manager,
        trust_hint="spki_sha256",
    )

    assert extension["v"] == 1
    assert extension["sid"] == canonicalize_swarm_id(swarm_id)
    assert extension["tp"] == "spki_sha256"
    proof = parse_swarm_auth_dict(extension)
    assert proof.timestamp == timestamp
    assert proof.version == 1
    assert proof.to_extension_dict()["sig"] == extension["sig"]
    assert payload.startswith(SWARM_AUTH_PREFIX)
    assert proof.public_key == key_manager.get_public_key_bytes()
    assert signature == key_manager.sign_message(
        build_swarm_auth_message(
            proof.swarm_id,
            peer_id=peer_id,
            info_hash=info_hash,
            timestamp=timestamp,
            transport_hint="mse",
        )
    )


def test_evaluate_swarm_auth_verification_order_allows_valid_proof(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id, info_hash = _fixed_peer_and_info()
    swarm_id = canonicalize_swarm_id("12345678-9abc-def0-1234-56789abcdef0")
    timestamp = 1_700_000_100
    extension, _, _ = _make_extension(
        swarm_id=swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint="tls",
        key_manager=key_manager,
    )

    allowed, reason = evaluate_swarm_auth_verification_order(
        raw_swarm_auth=extension,
        peer_id=peer_id,
        info_hash=info_hash,
        transport_hint="tls",
        signer_verify=Ed25519KeyManager.verify_signature,
        trusted_swarm_ids=[swarm_id],
        now=timestamp,
        freshness_window_seconds=300,
    )

    assert allowed is True
    assert reason == "allow"


def test_evaluate_swarm_auth_verification_order_allows_hybrid_family(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"\x02" * 20
    info_hash_v1 = b"\x03" * 20
    info_hash_v2 = b"\x04" * 32
    swarm_id = canonicalize_swarm_id("12345678-9abc-def0-1234-56789abcdef0")
    timestamp = 1_700_000_150
    extension, _, _ = _make_extension(
        swarm_id=swarm_id,
        peer_id=peer_id,
        info_hash=(info_hash_v1, info_hash_v2),
        timestamp=timestamp,
        transport_hint="mse",
        key_manager=key_manager,
    )

    allowed, reason = evaluate_swarm_auth_verification_order(
        raw_swarm_auth=extension,
        peer_id=peer_id,
        info_hash=(info_hash_v1, info_hash_v2),
        transport_hint="mse",
        signer_verify=Ed25519KeyManager.verify_signature,
        trusted_swarm_ids=[swarm_id],
        now=timestamp,
        freshness_window_seconds=300,
    )
    assert allowed is True
    assert reason == "allow"


def test_evaluate_swarm_auth_rejects_trust_miss_or_tampering(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id, info_hash = _fixed_peer_and_info()
    swarm_id = canonicalize_swarm_id("bbbbbbbb" * 8)
    timestamp = 1_700_000_200
    extension, _, _ = _make_extension(
        swarm_id=swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint="other",
        key_manager=key_manager,
    )

    # wrong trust allow list
    allowed, reason = evaluate_swarm_auth_verification_order(
        raw_swarm_auth=extension,
        peer_id=peer_id,
        info_hash=info_hash,
        transport_hint="other",
        signer_verify=Ed25519KeyManager.verify_signature,
        trusted_swarm_ids=["aaaaaaaa" * 8],
        now=timestamp,
    )
    assert allowed is False
    assert reason == "trust_lookup_failed"

    extension["sig"] = extension["sig"][:-2] + "aa"
    allowed, reason = evaluate_swarm_auth_verification_order(
        raw_swarm_auth=extension,
        peer_id=peer_id,
        info_hash=info_hash,
        transport_hint="other",
        signer_verify=Ed25519KeyManager.verify_signature,
        trusted_swarm_ids=[swarm_id],
        now=timestamp,
    )
    assert allowed is False
    assert reason == "invalid_signature"


def test_swarm_auth_extension_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="peer_id must be 20 bytes"):
        build_swarm_auth_message(
            "cccccccc" * 10 + "cc",
            peer_id=b"\x00" * 19,
            info_hash=b"\x00" * 20,
            timestamp=1,
            transport_hint="plain",
        )

    with pytest.raises(ValueError, match="unsupported trust_proof_hint"):
        build_swarm_auth_extension(
            swarm_id="cccc" * 16,
            public_key=b"\x01" * 32,
            signature=b"\x01" * 64,
            timestamp=1,
            trust_proof_hint="not-a-hint",
        )

    invalid_hint = "not-a-hint"
    assert invalid_hint not in ALLOWED_TRUST_PROOF_HINTS
