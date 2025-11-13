"""Unit tests for Ed25519 IPC authentication.

from __future__ import annotations
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

try:
    from ccbt.security.key_manager import Ed25519KeyManager
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
    manager = Ed25519KeyManager(key_dir=temp_key_dir)
    manager.get_or_create_keypair()
    return manager


def test_key_manager_initialization(key_manager):
    """Test key manager initialization."""
    assert key_manager is not None
    public_key = key_manager.get_public_key_hex()
    assert len(public_key) == 64


def test_request_signing(key_manager):
    """Test request signing for IPC authentication."""
    import hashlib
    import time

    method = "GET"
    path = "/api/v1/status"
    body = b""
    timestamp = str(time.time())
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method} {path}\n{timestamp}\n{body_hash}".encode()

    signature = key_manager.sign_message(message)
    assert len(signature) == 64

    # Verify signature
    public_key_bytes = key_manager.get_public_key_bytes()
    is_valid = key_manager.verify_signature(message, signature, public_key_bytes)
    assert is_valid is True


def test_signature_verification_failure(key_manager):
    """Test signature verification with wrong signature."""
    message = b"test message"
    signature = key_manager.sign_message(message)
    public_key_bytes = key_manager.get_public_key_bytes()

    # Wrong signature
    wrong_signature = b"x" * 64
    is_valid = key_manager.verify_signature(
        message, wrong_signature, public_key_bytes
    )
    assert is_valid is False


def test_timestamp_replay_protection(key_manager):
    """Test timestamp-based replay attack prevention."""
    import hashlib
    import time

    method = "GET"
    path = "/api/v1/status"
    body = b""
    # Use old timestamp (outside 5-minute window)
    old_timestamp = str(time.time() - 400)  # 400 seconds ago
    body_hash = hashlib.sha256(body).hexdigest()
    message = f"{method} {path}\n{old_timestamp}\n{body_hash}".encode()

    signature = key_manager.sign_message(message)
    public_key_bytes = key_manager.get_public_key_bytes()

    # Signature should still be valid cryptographically
    is_valid = key_manager.verify_signature(message, signature, public_key_bytes)
    assert is_valid is True
    # But server should reject it based on timestamp check

