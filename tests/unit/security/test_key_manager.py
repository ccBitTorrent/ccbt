"""Unit tests for Ed25519KeyManager.

from __future__ import annotations
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:
    from ccbt.security.key_manager import Ed25519KeyManager, Ed25519KeyManagerError
except ImportError:
    pytest.skip("cryptography library not available", allow_module_level=True)


@pytest.fixture
def temp_key_dir():
    """Create temporary directory for key storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def key_manager(temp_key_dir):
    """Create Ed25519KeyManager instance."""
    return Ed25519KeyManager(key_dir=temp_key_dir)


def test_key_generation(key_manager):
    """Test key pair generation."""
    private_key, public_key = key_manager.generate_keypair()
    assert private_key is not None
    assert public_key is not None


def test_key_persistence(key_manager):
    """Test key persistence and loading."""
    # Generate and save keys
    private_key, public_key = key_manager.generate_keypair()
    key_manager.save_keypair(private_key, public_key)

    # Create new manager instance and load keys
    new_manager = Ed25519KeyManager(key_dir=key_manager.key_dir)
    loaded_private, loaded_public = new_manager.load_keypair()

    assert loaded_private is not None
    assert loaded_public is not None


def test_get_or_create_keypair(key_manager):
    """Test get_or_create_keypair method."""
    private_key, public_key = key_manager.get_or_create_keypair()
    assert private_key is not None
    assert public_key is not None

    # Should return same keys on second call
    private_key2, public_key2 = key_manager.get_or_create_keypair()
    assert private_key == private_key2
    assert public_key == public_key2


def test_get_public_key_bytes(key_manager):
    """Test getting public key as bytes."""
    key_manager.get_or_create_keypair()
    public_key_bytes = key_manager.get_public_key_bytes()
    assert len(public_key_bytes) == 32


def test_get_public_key_hex(key_manager):
    """Test getting public key as hex string."""
    key_manager.get_or_create_keypair()
    public_key_hex = key_manager.get_public_key_hex()
    assert len(public_key_hex) == 64  # 32 bytes = 64 hex chars


def test_sign_and_verify(key_manager):
    """Test message signing and verification."""
    key_manager.get_or_create_keypair()
    message = b"test message"

    # Sign message
    signature = key_manager.sign_message(message)
    assert len(signature) == 64  # Ed25519 signature is 64 bytes

    # Verify signature
    public_key_bytes = key_manager.get_public_key_bytes()
    is_valid = key_manager.verify_signature(message, signature, public_key_bytes)
    assert is_valid is True

    # Verify with wrong message
    wrong_message = b"wrong message"
    is_valid = key_manager.verify_signature(
        wrong_message, signature, public_key_bytes
    )
    assert is_valid is False


def test_key_rotation(key_manager):
    """Test key rotation."""
    # Generate initial keys
    private_key1, public_key1 = key_manager.get_or_create_keypair()
    public_key_bytes1 = key_manager.get_public_key_bytes()

    # Rotate keys
    private_key2, public_key2 = key_manager.rotate_keypair()
    public_key_bytes2 = key_manager.get_public_key_bytes()

    # Keys should be different
    assert public_key_bytes1 != public_key_bytes2


def test_load_nonexistent_keys(temp_key_dir):
    """Test loading keys that don't exist."""
    manager = Ed25519KeyManager(key_dir=temp_key_dir)
    with pytest.raises(Ed25519KeyManagerError):
        manager.load_keypair()

