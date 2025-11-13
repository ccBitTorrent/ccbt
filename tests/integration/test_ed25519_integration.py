"""Integration tests for Ed25519 features.

from __future__ import annotations
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:
    from ccbt.security.key_manager import Ed25519KeyManager
    from ccbt.security.ed25519_handshake import Ed25519Handshake
    from ccbt.security.messaging import SecureMessaging, SecureMessage
except ImportError:
    pytest.skip("cryptography library not available", allow_module_level=True)


@pytest.fixture
def temp_key_dir():
    """Create temporary directory for key storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def key_manager1(temp_key_dir):
    """Create first Ed25519KeyManager instance."""
    manager = Ed25519KeyManager(key_dir=temp_key_dir / "keys1")
    manager.get_or_create_keypair()
    return manager


@pytest.fixture
def key_manager2(temp_key_dir):
    """Create second Ed25519KeyManager instance."""
    manager = Ed25519KeyManager(key_dir=temp_key_dir / "keys2")
    manager.get_or_create_keypair()
    return manager


def test_ed25519_handshake(key_manager1, key_manager2):
    """Test Ed25519 handshake between two peers."""
    info_hash = b"x" * 20
    peer_id1 = b"y" * 20
    peer_id2 = b"z" * 20

    # Peer 1 initiates handshake
    handshake1 = Ed25519Handshake(key_manager1)
    public_key1, signature1 = handshake1.initiate_handshake(info_hash, peer_id1)

    # Peer 2 verifies handshake
    handshake2 = Ed25519Handshake(key_manager2)
    is_valid = handshake2.verify_peer_handshake(
        info_hash, peer_id1, public_key1, signature1
    )
    assert is_valid is True


def test_secure_messaging(key_manager1, key_manager2):
    """Test secure messaging between two peers."""
    messaging1 = SecureMessaging(key_manager1)
    messaging2 = SecureMessaging(key_manager2)

    # Peer 1 encrypts message for peer 2
    message = b"Hello, secure world!"
    recipient_public_key = key_manager2.get_public_key_bytes()
    secure_message = messaging1.encrypt_message(message, recipient_public_key)

    assert secure_message is not None
    assert secure_message.encrypted_payload != message

    # Peer 2 decrypts message
    decrypted = messaging2.decrypt_message(secure_message)
    assert decrypted == message


def test_secure_message_serialization(key_manager1, key_manager2):
    """Test secure message serialization."""
    messaging1 = SecureMessaging(key_manager1)
    message = b"Test message"
    recipient_public_key = key_manager2.get_public_key_bytes()
    secure_message = messaging1.encrypt_message(message, recipient_public_key)

    # Serialize to dict
    message_dict = secure_message.to_dict()
    assert "sender_public_key" in message_dict
    assert "encrypted_payload" in message_dict
    assert "signature" in message_dict

    # Deserialize from dict
    restored_message = SecureMessage.from_dict(message_dict)
    assert restored_message.sender_public_key == secure_message.sender_public_key
    assert restored_message.encrypted_payload == secure_message.encrypted_payload

    # Decrypt restored message
    messaging2 = SecureMessaging(key_manager2)
    decrypted = messaging2.decrypt_message(restored_message)
    assert decrypted == message

