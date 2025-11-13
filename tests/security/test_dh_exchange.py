"""Tests for Diffie-Hellman key exchange.

Covers:
- DH parameter generation (768-bit and 1024-bit)
- Keypair generation
- Shared secret computation
- Key derivation
- Error handling
"""

from __future__ import annotations

import pytest

from ccbt.security.dh_exchange import DHKeyPair, DHPeerExchange

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_dh_exchange_init_768():
    """Test DHPeerExchange initialization with 768-bit key."""
    dh = DHPeerExchange(key_size=768)
    assert dh.key_size == 768


def test_dh_exchange_init_1024():
    """Test DHPeerExchange initialization with 1024-bit key."""
    dh = DHPeerExchange(key_size=1024)
    assert dh.key_size == 1024


def test_dh_exchange_init_invalid_size():
    """Test DHPeerExchange initialization with invalid key size raises error."""
    with pytest.raises(ValueError, match="DH key size must be 768 or 1024 bits"):
        DHPeerExchange(key_size=512)


def test_dh_get_dh_parameters_invalid_size():
    """Test _get_dh_parameters with invalid key size raises error."""
    # Test the private method directly to cover the error path
    # This tests lines 79-80 which are the fallback error case
    with pytest.raises(ValueError, match="Unsupported key size"):
        DHPeerExchange._get_dh_parameters(512)  # Invalid key size


def test_dh_generate_keypair_768():
    """Test DH keypair generation for 768-bit."""
    dh = DHPeerExchange(key_size=768)
    keypair = dh.generate_keypair()

    assert isinstance(keypair, DHKeyPair)
    assert keypair.private_key is not None
    assert keypair.public_key is not None


def test_dh_generate_keypair_1024():
    """Test DH keypair generation for 1024-bit."""
    dh = DHPeerExchange(key_size=1024)
    keypair = dh.generate_keypair()

    assert isinstance(keypair, DHKeyPair)
    assert keypair.private_key is not None
    assert keypair.public_key is not None


def test_dh_keypair_unique():
    """Test that different keypairs are generated."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    # Public keys should be different
    public1_bytes = dh.get_public_key_bytes(keypair1)
    public2_bytes = dh.get_public_key_bytes(keypair2)
    assert public1_bytes != public2_bytes


def test_dh_compute_shared_secret_768():
    """Test shared secret computation for 768-bit."""
    dh = DHPeerExchange(key_size=768)

    # Generate two keypairs (simulating two peers)
    alice_keypair = dh.generate_keypair()
    bob_keypair = dh.generate_keypair()

    # Compute shared secrets (should be same)
    alice_secret = dh.compute_shared_secret(
        alice_keypair.private_key, bob_keypair.public_key
    )
    bob_secret = dh.compute_shared_secret(
        bob_keypair.private_key, alice_keypair.public_key
    )

    # Shared secrets should be identical
    assert alice_secret == bob_secret
    assert len(alice_secret) > 0


def test_dh_compute_shared_secret_1024():
    """Test shared secret computation for 1024-bit."""
    dh = DHPeerExchange(key_size=1024)

    alice_keypair = dh.generate_keypair()
    bob_keypair = dh.generate_keypair()

    alice_secret = dh.compute_shared_secret(
        alice_keypair.private_key, bob_keypair.public_key
    )
    bob_secret = dh.compute_shared_secret(
        bob_keypair.private_key, alice_keypair.public_key
    )

    assert alice_secret == bob_secret
    assert len(alice_secret) > 0


def test_dh_derive_encryption_key():
    """Test encryption key derivation."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )

    info_hash = bytes(range(20))  # Exactly 20 bytes
    encryption_key = dh.derive_encryption_key(shared_secret, info_hash)

    # Key should be 20 bytes (SHA-1 output)
    assert len(encryption_key) == 20
    assert encryption_key != shared_secret


def test_dh_derive_encryption_key_with_pad():
    """Test encryption key derivation with custom pad."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )

    info_hash = bytes(range(20))  # Exactly 20 bytes
    pad = b"\x00" * 20

    key1 = dh.derive_encryption_key(shared_secret, info_hash, pad=pad)
    key2 = dh.derive_encryption_key(shared_secret, info_hash, pad=pad)

    # Same inputs should produce same key
    assert key1 == key2


def test_dh_derive_encryption_key_different_pads():
    """Test that different pads produce different keys."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )

    info_hash = bytes(range(20))  # Exactly 20 bytes
    pad1 = b"\x00" * 20
    pad2 = b"\x01" * 20

    key1 = dh.derive_encryption_key(shared_secret, info_hash, pad=pad1)
    key2 = dh.derive_encryption_key(shared_secret, info_hash, pad=pad2)

    # Different pads should produce different keys
    assert key1 != key2


def test_dh_derive_encryption_key_invalid_info_hash():
    """Test key derivation with invalid info hash size raises error."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )

    invalid_info_hash = b"too_short"  # Not 20 bytes

    with pytest.raises(ValueError, match="Info hash must be 20 bytes"):
        dh.derive_encryption_key(shared_secret, invalid_info_hash)


def test_dh_get_public_key_bytes_768():
    """Test getting public key as bytes for 768-bit."""
    dh = DHPeerExchange(key_size=768)
    keypair = dh.generate_keypair()

    public_bytes = dh.get_public_key_bytes(keypair)

    # Should be approximately 96 bytes (768 bits / 8)
    # But may be slightly less if leading zeros are not included
    assert len(public_bytes) <= 96
    assert len(public_bytes) >= 90  # At least 90 bytes


def test_dh_get_public_key_bytes_1024():
    """Test getting public key as bytes for 1024-bit."""
    dh = DHPeerExchange(key_size=1024)
    keypair = dh.generate_keypair()

    public_bytes = dh.get_public_key_bytes(keypair)

    # Should be approximately 128 bytes (1024 bits / 8)
    assert len(public_bytes) <= 128
    assert len(public_bytes) >= 120  # At least 120 bytes


def test_dh_public_key_from_bytes():
    """Test reconstructing public key from bytes."""
    dh = DHPeerExchange(key_size=768)

    # Generate original keypair
    original_keypair = dh.generate_keypair()
    original_public_bytes = dh.get_public_key_bytes(original_keypair)

    # Reconstruct public key
    reconstructed_public_key = dh.public_key_from_bytes(
        original_public_bytes, original_keypair.private_key
    )

    # Reconstructed public key should match original
    reconstructed_bytes = dh.get_public_key_bytes(
        DHKeyPair(original_keypair.private_key, reconstructed_public_key)
    )
    assert reconstructed_bytes == original_public_bytes


def test_dh_shared_secret_symmetric():
    """Test that shared secret computation is symmetric."""
    dh = DHPeerExchange(key_size=768)

    alice_keypair = dh.generate_keypair()
    bob_keypair = dh.generate_keypair()

    # Compute from both sides
    secret1 = dh.compute_shared_secret(
        alice_keypair.private_key, bob_keypair.public_key
    )
    secret2 = dh.compute_shared_secret(
        bob_keypair.private_key, alice_keypair.public_key
    )

    # Secrets should be identical
    assert secret1 == secret2
    assert len(secret1) > 0


def test_dh_shared_secret_different_keypairs():
    """Test that different keypairs produce different shared secrets."""
    dh = DHPeerExchange(key_size=768)

    alice_keypair = dh.generate_keypair()
    bob_keypair = dh.generate_keypair()
    charlie_keypair = dh.generate_keypair()

    # Alice-Bob shared secret
    ab_secret = dh.compute_shared_secret(
        alice_keypair.private_key, bob_keypair.public_key
    )

    # Alice-Charlie shared secret
    ac_secret = dh.compute_shared_secret(
        alice_keypair.private_key, charlie_keypair.public_key
    )

    # Should be different
    assert ab_secret != ac_secret


def test_dh_key_derivation_consistency():
    """Test that key derivation is consistent with same inputs."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )
    info_hash = bytes(range(20))  # Exactly 20 bytes

    key1 = dh.derive_encryption_key(shared_secret, info_hash)
    key2 = dh.derive_encryption_key(shared_secret, info_hash)

    # Same inputs should produce same key
    assert key1 == key2


def test_dh_key_derivation_different_info_hashes():
    """Test that different info hashes produce different keys."""
    dh = DHPeerExchange(key_size=768)
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )

    info_hash1 = bytes(range(20))  # Exactly 20 bytes
    info_hash2 = bytes(range(20, 40))  # Exactly 20 bytes, different values

    key1 = dh.derive_encryption_key(shared_secret, info_hash1)
    key2 = dh.derive_encryption_key(shared_secret, info_hash2)

    # Different info hashes should produce different keys
    assert key1 != key2

