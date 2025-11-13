"""Base cipher interface for BEP 3 encryption.

from __future__ import annotations

Defines abstract base class for all cipher implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CipherSuite(ABC):
    """Abstract base class for cipher implementations."""

    @abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data.

        Args:
            data: Plaintext data to encrypt

        Returns:
            Encrypted data

        """

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data.

        Args:
            data: Encrypted data to decrypt

        Returns:
            Decrypted plaintext data

        """

    @abstractmethod
    def key_size(self) -> int:
        """Get the key size in bytes required for this cipher.

        Returns:
            Key size in bytes

        """
