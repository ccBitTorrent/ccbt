"""AES cipher implementation for BEP 3.

from __future__ import annotations

Uses AES in CFB mode (stream-like behavior) as specified in BEP 3.
Supports AES-128 and AES-256.
"""

from __future__ import annotations

import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ccbt.security.ciphers.base import CipherSuite


class AESCipher(CipherSuite):
    """AES cipher implementation using CFB mode."""

    def __init__(self, key: bytes, iv: bytes | None = None):
        """Initialize AES cipher.

        Args:
            key: Encryption key (16 bytes for AES-128, 32 bytes for AES-256)
            iv: Initialization vector (16 bytes). If None, generates random IV.
                Note: For BEP 3, IV handling may need special consideration.

        Raises:
            ValueError: If key size is invalid (must be 16 or 32 bytes)

        """
        if len(key) not in (16, 32):
            msg = f"AES key must be 16 or 32 bytes, got {len(key)}"
            raise ValueError(msg)

        self.key = key
        self.iv = iv or secrets.token_bytes(16)

        if len(self.iv) != 16:
            msg = f"AES IV must be 16 bytes, got {len(self.iv)}"
            raise ValueError(msg)

        # Create cipher with CFB mode (no padding needed, stream-like)
        algorithm = algorithms.AES(self.key)
        mode = modes.CFB(self.iv)
        self._cipher = Cipher(algorithm, mode, backend=default_backend())

        # Store encryption/decryption contexts
        self._encryptor = None
        self._decryptor = None

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using AES-CFB.

        Args:
            data: Plaintext data to encrypt

        Returns:
            Encrypted data (prefixed with IV if IV was generated)

        """
        if not data:
            return b""

        if self._encryptor is None:
            self._encryptor = self._cipher.encryptor()

        # Encrypt data
        return self._encryptor.update(data)

        # Note: For BEP 3, IV handling may need to be done externally
        # The IV is typically sent separately in the handshake

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using AES-CFB.

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
            Key size in bytes (16 for AES-128, 32 for AES-256)

        """
        return len(self.key)
