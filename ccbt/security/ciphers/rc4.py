"""RC4 stream cipher implementation for BEP 3.

from __future__ import annotations

RC4 is deprecated but required for BEP 3 compatibility with existing
BitTorrent clients. This is a direct implementation to avoid external
dependencies.
"""

from __future__ import annotations

from ccbt.security.ciphers.base import CipherSuite


class RC4Cipher(CipherSuite):
    """RC4 stream cipher implementation."""

    def __init__(self, key: bytes):
        """Initialize RC4 cipher with key.

        Args:
            key: Encryption key (typically 16 bytes for BEP 3)

        """
        if not key:
            msg = "RC4 key cannot be empty"
            raise ValueError(msg)

        self.key = key
        self._s = list(range(256))
        self._i = 0
        self._j = 0

        # Key scheduling algorithm (KSA)
        j = 0
        for i in range(256):
            j = (j + self._s[i] + key[i % len(key)]) % 256
            self._s[i], self._s[j] = self._s[j], self._s[i]

    def _prga(self, length: int) -> bytes:
        """Pseudo-random generation algorithm (PRGA).

        Args:
            length: Number of bytes to generate

        Returns:
            Key stream bytes

        """
        result = bytearray(length)
        for k in range(length):
            self._i = (self._i + 1) % 256
            self._j = (self._j + self._s[self._i]) % 256
            self._s[self._i], self._s[self._j] = (
                self._s[self._j],
                self._s[self._i],
            )
            result[k] = self._s[(self._s[self._i] + self._s[self._j]) % 256]
        return bytes(result)

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using RC4.

        Args:
            data: Plaintext data to encrypt

        Returns:
            Encrypted data (same length as input)

        """
        if not data:
            return b""

        # RC4 is symmetric: encryption == decryption (XOR with key stream)
        key_stream = self._prga(len(data))
        return bytes(a ^ b for a, b in zip(data, key_stream))

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using RC4.

        Args:
            data: Encrypted data to decrypt

        Returns:
            Decrypted plaintext data (same length as input)

        """
        # RC4 is symmetric (XOR cipher), but we need fresh state
        # Create a new cipher instance with same key to decrypt
        # This ensures we start with fresh PRGA state
        decrypt_cipher = RC4Cipher(self.key)
        return decrypt_cipher.encrypt(data)

    def key_size(self) -> int:
        """Get the key size in bytes.

        Returns:
            Key size in bytes (16 for BEP 3)

        """
        return 16
