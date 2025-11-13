"""Tests for cipher implementations.

Covers:
- RC4 cipher encryption/decryption
- AES cipher encryption/decryption
- Key handling and error cases
- Known test vectors (where available)
"""

from __future__ import annotations

import pytest

from ccbt.security.ciphers.aes import AESCipher
from ccbt.security.ciphers.base import CipherSuite
from ccbt.security.ciphers.rc4 import RC4Cipher

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_rc4_cipher_init():
    """Test RC4Cipher initialization."""
    key = b"test_key_16bytes"  # 16 bytes
    cipher = RC4Cipher(key)

    assert cipher.key == key
    assert cipher.key_size() == 16


def test_rc4_cipher_init_empty_key():
    """Test RC4Cipher initialization with empty key raises error."""
    with pytest.raises(ValueError, match="RC4 key cannot be empty"):
        RC4Cipher(b"")


def test_rc4_cipher_encrypt_decrypt():
    """Test RC4 encryption and decryption round-trip."""
    key = b"secret_key_12345"
    cipher = RC4Cipher(key)

    plaintext = b"Hello, World! This is a test message."
    encrypted = cipher.encrypt(plaintext)

    # Encrypted should be different from plaintext
    assert encrypted != plaintext
    assert len(encrypted) == len(plaintext)

    # Decrypt should recover original
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == plaintext


def test_rc4_cipher_symmetric():
    """Test that RC4 encrypt and decrypt are symmetric (same operation)."""
    key = b"test_key_16bytes"
    cipher1 = RC4Cipher(key)
    cipher2 = RC4Cipher(key)

    plaintext = b"Test data"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Same key should produce same output
    assert encrypted1 == encrypted2

    # Decryption should work with new cipher instance
    cipher3 = RC4Cipher(key)
    decrypted = cipher3.decrypt(encrypted1)
    assert decrypted == plaintext


def test_rc4_cipher_empty_data():
    """Test RC4 with empty data."""
    key = b"test_key_16bytes"
    cipher = RC4Cipher(key)

    encrypted = cipher.encrypt(b"")
    assert encrypted == b""

    decrypted = cipher.decrypt(b"")
    assert decrypted == b""


def test_rc4_cipher_different_keys():
    """Test that different keys produce different ciphertext."""
    key1 = b"key_one_123456"
    key2 = b"key_two_123456"

    cipher1 = RC4Cipher(key1)
    cipher2 = RC4Cipher(key2)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Different keys should produce different ciphertext
    assert encrypted1 != encrypted2


def test_rc4_cipher_key_size():
    """Test RC4 key_size() method."""
    key = b"16_bytes_key_!!"
    cipher = RC4Cipher(key)
    assert cipher.key_size() == 16


def test_aes_cipher_init_aes128():
    """Test AESCipher initialization with AES-128 key."""
    key = b"16_bytes_key_!!!"  # 16 bytes for AES-128
    cipher = AESCipher(key)

    assert cipher.key == key
    assert cipher.key_size() == 16
    assert len(cipher.iv) == 16


def test_aes_cipher_init_aes256():
    """Test AESCipher initialization with AES-256 key."""
    key = bytes(range(32))  # Exactly 32 bytes for AES-256
    cipher = AESCipher(key)

    assert cipher.key == key
    assert cipher.key_size() == 32
    assert len(cipher.iv) == 16


def test_aes_cipher_init_with_iv():
    """Test AESCipher initialization with provided IV."""
    key = b"16_bytes_key_!!!"
    iv = b"16_bytes_iv_!!!!"
    cipher = AESCipher(key, iv=iv)

    assert cipher.key == key
    assert cipher.iv == iv


def test_aes_cipher_init_invalid_key_size():
    """Test AESCipher initialization with invalid key size raises error."""
    invalid_key = b"invalid_key"
    with pytest.raises(ValueError, match="AES key must be 16 or 32 bytes"):
        AESCipher(invalid_key)


def test_aes_cipher_init_invalid_iv_size():
    """Test AESCipher initialization with invalid IV size raises error."""
    key = b"16_bytes_key_!!!"
    invalid_iv = b"invalid_iv"
    with pytest.raises(ValueError, match="AES IV must be 16 bytes"):
        AESCipher(key, iv=invalid_iv)


def test_aes_cipher_encrypt_decrypt():
    """Test AES encryption and decryption round-trip."""
    key = b"16_bytes_key_!!!"
    cipher = AESCipher(key)

    plaintext = b"Hello, World! This is a test message."
    encrypted = cipher.encrypt(plaintext)

    # Encrypted should be different from plaintext
    assert encrypted != plaintext
    assert len(encrypted) == len(plaintext)

    # Decrypt should recover original
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == plaintext


def test_aes_cipher_empty_data():
    """Test AES with empty data."""
    key = b"16_bytes_key_!!!"
    cipher = AESCipher(key)

    encrypted = cipher.encrypt(b"")
    assert encrypted == b""

    decrypted = cipher.decrypt(b"")
    assert decrypted == b""


def test_aes_cipher_different_keys():
    """Test that different keys produce different ciphertext."""
    key1 = b"key_one_12345678"  # 16 bytes
    key2 = b"key_two_12345678"  # 16 bytes

    cipher1 = AESCipher(key1)
    cipher2 = AESCipher(key2)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Different keys should produce different ciphertext
    assert encrypted1 != encrypted2


def test_aes_cipher_different_ivs():
    """Test that different IVs produce different ciphertext with same key."""
    key = b"16_bytes_key_!!!"
    iv1 = b"iv_one_12345678!"  # 16 bytes
    iv2 = b"iv_two_12345678!"  # 16 bytes

    cipher1 = AESCipher(key, iv=iv1)
    cipher2 = AESCipher(key, iv=iv2)

    plaintext = b"Same plaintext"
    encrypted1 = cipher1.encrypt(plaintext)
    encrypted2 = cipher2.encrypt(plaintext)

    # Different IVs should produce different ciphertext
    assert encrypted1 != encrypted2


def test_aes_cipher_key_size():
    """Test AES key_size() method for both key sizes."""
    key128 = b"16_bytes_key_!!!"
    cipher128 = AESCipher(key128)
    assert cipher128.key_size() == 16

    key256 = bytes(range(32))  # Exactly 32 bytes
    cipher256 = AESCipher(key256)
    assert cipher256.key_size() == 32


def test_cipher_suite_interface():
    """Test that ciphers implement CipherSuite interface."""
    # Test RC4 implements interface
    rc4_cipher = RC4Cipher(b"test_key_16bytes")
    assert isinstance(rc4_cipher, CipherSuite)
    assert hasattr(rc4_cipher, "encrypt")
    assert hasattr(rc4_cipher, "decrypt")
    assert hasattr(rc4_cipher, "key_size")

    # Test AES implements interface
    aes_cipher = AESCipher(b"16_bytes_key_!!!")
    assert isinstance(aes_cipher, CipherSuite)
    assert hasattr(aes_cipher, "encrypt")
    assert hasattr(aes_cipher, "decrypt")
    assert hasattr(aes_cipher, "key_size")


def test_rc4_large_data():
    """Test RC4 with larger data sets."""
    key = b"test_key_16bytes"
    cipher = RC4Cipher(key)

    # Test with 1KB data
    large_data = b"x" * 1024
    encrypted = cipher.encrypt(large_data)
    decrypted = cipher.decrypt(encrypted)

    assert len(encrypted) == len(large_data)
    assert decrypted == large_data


def test_aes_large_data():
    """Test AES with larger data sets."""
    key = b"16_bytes_key_!!!"
    cipher = AESCipher(key)

    # Test with 1KB data
    large_data = b"x" * 1024
    encrypted = cipher.encrypt(large_data)
    decrypted = cipher.decrypt(encrypted)

    assert len(encrypted) == len(large_data)
    assert decrypted == large_data

