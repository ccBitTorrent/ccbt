"""Unit tests for signed XET handshake metadata."""

from __future__ import annotations

import hashlib

import pytest

from ccbt.extensions.xet_handshake import XetHandshakeExtension

pytestmark = [pytest.mark.unit, pytest.mark.extensions]


class _FakeKeyManager:
    """Minimal signing helper for handshake verification tests."""

    def __init__(self, private_key: bytes) -> None:
        self._private_key = private_key

    def get_public_key_bytes(self) -> bytes:
        return hashlib.sha256(self._private_key).digest()

    def sign_message(self, message: bytes) -> bytes:
        digest = hashlib.sha512(self.get_public_key_bytes() + message).digest()
        return digest

    @staticmethod
    def verify_signature(message: bytes, signature: bytes, public_key: bytes) -> bool:
        expected = hashlib.sha512(public_key + message).digest()
        return signature == expected


def test_signed_handshake_identity_round_trip() -> None:
    """Peers should verify signed handshake identity payloads."""
    key_manager = _FakeKeyManager(b"peer-private-key")
    handshake = XetHandshakeExtension(
        allowlist_hash=b"A" * 32,
        sync_mode="best_effort",
        git_ref="deadbeef",
        key_manager=key_manager,
    )

    encoded = handshake.encode_handshake()
    decoded = handshake.decode_handshake("peer-1", encoded)

    assert decoded is not None
    assert handshake.verify_handshake_identity("peer-1", decoded) is True


def test_signed_handshake_identity_rejects_tampering() -> None:
    """Tampering any signed handshake field should invalidate identity verification."""
    key_manager = _FakeKeyManager(b"peer-private-key")
    handshake = XetHandshakeExtension(
        allowlist_hash=b"B" * 32,
        sync_mode="best_effort",
        git_ref="deadbeef",
        key_manager=key_manager,
    )

    encoded = handshake.encode_handshake()
    decoded = handshake.decode_handshake("peer-1", encoded)
    assert decoded is not None
    decoded["sync_mode"] = "consensus"

    assert handshake.verify_handshake_identity("peer-1", decoded) is False


def test_signed_handshake_carries_workspace_and_hash_algorithm() -> None:
    """Signed handshake payloads should bind workspace and hash algorithm."""
    key_manager = _FakeKeyManager(b"peer-private-key")
    handshake = XetHandshakeExtension(
        allowlist_hash=b"C" * 32,
        sync_mode="best_effort",
        git_ref="deadbeef",
        key_manager=key_manager,
        workspace_id=b"W" * 32,
        hash_algorithm="blake3",
        capabilities={"supports_metadata_exchange": True},
    )

    encoded = handshake.encode_handshake()
    decoded = handshake.decode_handshake("peer-1", encoded)

    assert decoded is not None
    assert decoded["workspace_id"] == b"W" * 32
    assert decoded["hash_algorithm"].startswith("xet-hash:v1:")
    assert decoded["hash_algorithm"].endswith("blake3")
    assert handshake.verify_handshake_identity("peer-1", decoded) is True


def test_signed_handshake_requires_signature_when_enabled() -> None:
    """Unsigned handshakes should be rejected when signed metadata is required."""
    handshake = XetHandshakeExtension(require_signed_metadata=True)

    assert handshake.verify_handshake_identity(
        "peer-1",
        {
            "version": "1.0",
            "supports_folder_sync": True,
        },
    ) is False
