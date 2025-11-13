"""Encrypted stream wrappers for BEP 3 encryption.

from __future__ import annotations

Provides transparent encryption/decryption wrappers for asyncio streams,
allowing BitTorrent protocol messages to be encrypted transparently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import asyncio

    from ccbt.security.ciphers.base import CipherSuite


class EncryptedStreamReader:
    """Encrypted stream reader wrapper.

    Wraps asyncio.StreamReader to transparently decrypt data as it's read.
    """

    def __init__(self, reader: asyncio.StreamReader, cipher: CipherSuite):
        """Initialize encrypted stream reader.

        Args:
            reader: Underlying stream reader
            cipher: Cipher instance for decryption

        """
        self.reader = reader
        self.cipher = cipher
        self._buffer = b""

    async def read(self, n: int = -1) -> bytes:
        """Read and decrypt data.

        Args:
            n: Number of bytes to read (-1 for all available)

        Returns:
            Decrypted data

        """
        if n == -1:
            # Read all available data
            encrypted = await self.reader.read(-1)
            if not encrypted:
                return b""
            return self.cipher.decrypt(encrypted)

        # Read specified number of bytes
        # We may need to read more encrypted bytes to get n decrypted bytes
        # For stream ciphers, encrypted size == decrypted size
        encrypted = await self.reader.read(n)
        if not encrypted:
            return b""

        return self.cipher.decrypt(encrypted)

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes and decrypt.

        Args:
            n: Exact number of bytes to read

        Returns:
            Decrypted data (exactly n bytes)

        Raises:
            asyncio.IncompleteReadError: If insufficient data available

        """
        # For stream ciphers, encrypted size == decrypted size
        encrypted = await self.reader.readexactly(n)
        return self.cipher.decrypt(encrypted)

    def at_eof(self) -> bool:
        """Check if stream is at EOF.

        Returns:
            True if at EOF

        """
        return self.reader.at_eof()

    def __getattr__(self, name: str) -> Any:
        """Delegate other attributes to underlying reader."""
        return getattr(self.reader, name)


class EncryptedStreamWriter:
    """Encrypted stream writer wrapper.

    Wraps asyncio.StreamWriter to transparently encrypt data before writing.
    """

    def __init__(self, writer: asyncio.StreamWriter, cipher: CipherSuite):
        """Initialize encrypted stream writer.

        Args:
            writer: Underlying stream writer
            cipher: Cipher instance for encryption

        """
        self.writer = writer
        self.cipher = cipher

    def write(self, data: bytes) -> None:
        """Encrypt and write data.

        Args:
            data: Plaintext data to encrypt and write

        """
        if not data:
            return

        encrypted = self.cipher.encrypt(data)
        self.writer.write(encrypted)

    async def drain(self) -> None:
        """Drain writer buffer."""
        await self.writer.drain()

    def close(self) -> None:
        """Close writer."""
        self.writer.close()

    async def wait_closed(self) -> None:
        """Wait for writer to close."""
        await self.writer.wait_closed()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Get extra info from writer."""
        return self.writer.get_extra_info(name, default)

    def __getattr__(self, name: str) -> Any:
        """Delegate other attributes to underlying writer."""
        return getattr(self.writer, name)
