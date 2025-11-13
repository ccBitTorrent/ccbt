"""ChaCha20 cipher implementation for BEP 3.

from __future__ import annotations

Uses ChaCha20 stream cipher as specified in BEP 3.
Supports ChaCha20-256 (32-byte keys, 16-byte nonces).
Note: The cryptography library requires 16-byte (128-bit) nonces.
"""

from __future__ import annotations

import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from ccbt.security.ciphers.base import CipherSuite


class ChaCha20Cipher(CipherSuite):
    """ChaCha20 stream cipher implementation."""

    def __init__(self, key: bytes, nonce: bytes | None = None):
        """Initialize ChaCha20 cipher.

        Args:
            key: Encryption key (32 bytes for ChaCha20-256)
            nonce: Nonce (16 bytes / 128 bits). If None, generates random nonce.
                Note: The cryptography library requires 16-byte nonces (128 bits).

        Raises:
            ValueError: If key size is invalid (must be 32 bytes)
            ValueError: If nonce size is invalid (must be 16 bytes)

        """
        if len(key) != 32:
            msg = f"ChaCha20 key must be 32 bytes, got {len(key)}"
            raise ValueError(msg)

        self.key = key
        self.nonce = nonce or secrets.token_bytes(16)

        if len(self.nonce) != 16:
            msg = f"ChaCha20 nonce must be 16 bytes, got {len(self.nonce)}"
            raise ValueError(msg)

        # Create ChaCha20 cipher (ChaCha20 algorithm takes key and nonce)
        algorithm = algorithms.ChaCha20(self.key, self.nonce)
        self._cipher = Cipher(algorithm, mode=None, backend=default_backend())

        # Store encryption/decryption contexts
        self._encryptor = None
        self._decryptor = None

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using ChaCha20.

        Args:
            data: Plaintext data to encrypt

        Returns:
            Encrypted data

        """
        if not data:
            return b""

        if self._encryptor is None:
            self._encryptor = self._cipher.encryptor()

        # Encrypt data
        return self._encryptor.update(data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using ChaCha20.

        Args:
            data: Encrypted data to decrypt

        Returns:
            Decrypted plaintext data

        """
        if not data:
            return b""

        if self._decryptor is None:
            self._decryptor = self._cipher.decryptor()

        # Decrypt data
        return self._decryptor.update(data)

    def key_size(self) -> int:
        """Get the key size in bytes.

        Returns:
            Key size in bytes (32 for ChaCha20-256)

        """
        return 32
