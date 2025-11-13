"""Tests for ChaCha20 cipher implementation.

Covers:
- ChaCha20 cipher encryption/decryption
- Key and nonce handling
- Error cases
- Interface compliance
"""

from __future__ import annotations

import pytest

from ccbt.security.ciphers.base import CipherSuite
from ccbt.security.ciphers.chacha20 import ChaCha20Cipher

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_chacha20_cipher_init_valid_key():
    """Test ChaCha20Cipher initialization with valid 32-byte key."""
    key = bytes(range(32))  # Exactly 32 bytes
    cipher = ChaCha20Cipher(key)

    assert cipher.key == key
    assert cipher.key_size() == 32
    assert len(cipher.nonce) == 16


def test_chacha20_cipher_init_invalid_key_size():
    """Test ChaCha20Cipher initialization with invalid key size raises error."""
    invalid_key = b"invalid_key_16_bytes!!"  # 16 bytes, not 32
    with pytest.raises(ValueError, match="ChaCha20 key must be 32 bytes"):
        ChaCha20Cipher(invalid_key)


def test_chacha20_cipher_init_auto_nonce():
    """Test ChaCha20Cipher initialization with auto-generated nonce."""
    key = bytes(range(32))
    cipher1 = ChaCha20Cipher(key)
    cipher2 = ChaCha20Cipher(key)

    # Nonces should be different (randomly generated)
    assert cipher1.nonce != cipher2.nonce
    assert len(cipher1.nonce) == 16
    assert len(cipher2.nonce) == 16


def test_chacha20_cipher_init_custom_nonce():
    """Test ChaCha20Cipher initialization with custom nonce."""
    key = bytes(range(32))
    nonce = b"16_bytes_nonce!!"  # Exactly 16 bytes
    cipher = ChaCha20Cipher(key, nonce=nonce)

    assert cipher.key == key
    assert cipher.nonce == nonce


def test_chacha20_cipher_init_invalid_nonce_size():
    """Test ChaCha20Cipher initialization with invalid nonce size raises error."""
    key = bytes(range(32))
    invalid_nonce = b"invalid_nonce"  # Not 16 bytes
    with pytest.raises(ValueError, match="ChaCha20 nonce must be 16 bytes"):
        ChaCha20Cipher(key, nonce=invalid_nonce)


def test_chacha20_encrypt_decrypt_roundtrip():
    """Test ChaCha20 encryption and decryption round-trip."""
    key = bytes(range(32))
    nonce = b"16_bytes_nonce!!"
    cipher = ChaCha20Cipher(key, nonce=nonce)

    plaintext = b"Hello, World! This is a test message."
    encrypted = cipher.encrypt(plaintext)

    # Encrypted should be different from plaintext
    assert encrypted != plaintext
    assert len(encrypted) == len(plaintext)

    # Decrypt should recover original
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == plaintext


def test_chacha20_encrypt_empty_data():
    """Test ChaCha20 with empty data."""
    key = bytes(range(32))
    cipher = ChaCha20Cipher(key)

    encrypted = cipher.encrypt(b"")
    assert encrypted == b""

    decrypted = cipher.decrypt(b"")
    assert decrypted == b""


def test_chacha20_encrypt_various_sizes():
    """Test ChaCha20 with various data sizes."""
    key = bytes(range(32))
    nonce = b"16_bytes_nonce!!"
    cipher = ChaCha20Cipher(key, nonce=nonce)

    # Test with 1 byte
    data1 = b"x"
    encrypted1 = cipher.encrypt(data1)
    decrypted1 = cipher.decrypt(encrypted1)
    assert decrypted1 == data1

    # Test with 100 bytes
    data2 = b"x" * 100
    encrypted2 = cipher.encrypt(data2)
    decrypted2 = cipher.decrypt(encrypted2)
    assert decrypted2 == data2

    # Test with 1MB
    data3 = b"x" * (1024 * 1024)
    encrypted3 = cipher.encrypt(data3)
    decrypted3 = cipher.decrypt(encrypted3)
    assert decrypted3 == data3


def test_chacha20_same_key_nonce_same_ciphertext():
    """Test that encrypting same plaintext with same key/nonce produces same ciphertext."""
    key = bytes(range(32))
    nonce = b"16_bytes_nonce!!"

    cipher1 = ChaCha20Cipher(key, nonce=nonce)
    cipher2 = ChaCha20Cipher(key, nonce=nonce)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Same key and nonce should produce same ciphertext
    assert encrypted1 == encrypted2


def test_chacha20_different_nonce_different_ciphertext():
    """Test that different nonces produce different ciphertexts with same key."""
    key = bytes(range(32))
    nonce1 = b"nonce_one_16byte"
    nonce2 = b"nonce_two_16byte"

    cipher1 = ChaCha20Cipher(key, nonce=nonce1)
    cipher2 = ChaCha20Cipher(key, nonce=nonce2)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Different nonces should produce different ciphertext
    assert encrypted1 != encrypted2


def test_chacha20_key_size():
    """Test ChaCha20 key_size() method."""
    key = bytes(range(32))
    cipher = ChaCha20Cipher(key)
    assert cipher.key_size() == 32


def test_chacha20_implements_cipher_suite():
    """Test that ChaCha20Cipher implements CipherSuite interface."""
    key = bytes(range(32))
    cipher = ChaCha20Cipher(key)

    assert isinstance(cipher, CipherSuite)
    assert hasattr(cipher, "encrypt")
    assert hasattr(cipher, "decrypt")
    assert hasattr(cipher, "key_size")
    assert callable(cipher.encrypt)
    assert callable(cipher.decrypt)
    assert callable(cipher.key_size)


def test_chacha20_polymorphic_usage():
    """Test that ChaCha20Cipher can be used polymorphically with other ciphers."""
    key = bytes(range(32))
    cipher: CipherSuite = ChaCha20Cipher(key)

    # Should work with CipherSuite type hint
    plaintext = b"Test data"
    encrypted = cipher.encrypt(plaintext)
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == plaintext
    assert cipher.key_size() == 32


def test_chacha20_different_keys():
    """Test that different keys produce different ciphertext."""
    key1 = bytes(range(32))
    key2 = bytes(range(16, 48))  # Different 32-byte key
    nonce = b"16_bytes_nonce!!"

    cipher1 = ChaCha20Cipher(key1, nonce=nonce)
    cipher2 = ChaCha20Cipher(key2, nonce=nonce)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Different keys should produce different ciphertext
    assert encrypted1 != encrypted2


def test_chacha20_large_data():
    """Test ChaCha20 with larger data sets."""
    key = bytes(range(32))
    nonce = b"16_bytes_nonce!!"
    cipher = ChaCha20Cipher(key, nonce=nonce)

    # Test with 1KB data
    large_data = b"x" * 1024
    encrypted = cipher.encrypt(large_data)
    decrypted = cipher.decrypt(encrypted)

    assert len(encrypted) == len(large_data)
    assert decrypted == large_data

