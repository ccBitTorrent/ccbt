"""Tests for encrypted stream wrappers.

Covers:
- EncryptedStreamReader read/readexactly operations
- EncryptedStreamWriter write/drain operations
- Encryption/decryption round-trips
- Partial reads
- Error handling
- EOF detection
- Attribute delegation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.security.ciphers.rc4 import RC4Cipher
from ccbt.security.encrypted_stream import (
    EncryptedStreamReader,
    EncryptedStreamWriter,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


class TestEncryptedStreamReader:
    """Tests for EncryptedStreamReader."""

    @pytest.fixture
    def mock_reader(self):
        """Create mock StreamReader."""
        return AsyncMock()

    @pytest.fixture
    def cipher(self):
        """Create test cipher."""
        return RC4Cipher(b"test_key_16bytes")

    @pytest.fixture
    def encrypted_reader(self, mock_reader, cipher):
        """Create EncryptedStreamReader instance."""
        return EncryptedStreamReader(mock_reader, cipher)

    @pytest.mark.asyncio
    async def test_init(self, encrypted_reader, mock_reader, cipher):
        """Test EncryptedStreamReader initialization."""
        assert encrypted_reader.reader == mock_reader
        assert encrypted_reader.cipher == cipher
        assert encrypted_reader._buffer == b""

    @pytest.mark.asyncio
    async def test_read_all_data(self, encrypted_reader, mock_reader):
        """Test reading all available data."""
        plaintext = b"Hello, World!"
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        mock_reader.read.return_value = encrypted

        result = await encrypted_reader.read(-1)

        assert result == plaintext
        mock_reader.read.assert_called_once_with(-1)

    @pytest.mark.asyncio
    async def test_read_specific_bytes(self, encrypted_reader, mock_reader):
        """Test reading specific number of bytes."""
        plaintext = b"Test data"
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        mock_reader.read.return_value = encrypted

        result = await encrypted_reader.read(len(plaintext))

        assert result == plaintext
        mock_reader.read.assert_called_once_with(len(plaintext))

    @pytest.mark.asyncio
    async def test_read_empty_data(self, encrypted_reader, mock_reader):
        """Test reading when stream returns empty."""
        mock_reader.read.return_value = b""

        result = await encrypted_reader.read(10)

        assert result == b""
        mock_reader.read.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_read_all_empty_data(self, encrypted_reader, mock_reader):
        """Test reading all data when stream returns empty."""
        mock_reader.read.return_value = b""

        result = await encrypted_reader.read(-1)

        assert result == b""
        mock_reader.read.assert_called_once_with(-1)

    @pytest.mark.asyncio
    async def test_readexactly(self, encrypted_reader, mock_reader):
        """Test readexactly method."""
        plaintext = b"Exact read test"
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        mock_reader.readexactly.return_value = encrypted

        result = await encrypted_reader.readexactly(len(plaintext))

        assert result == plaintext
        assert len(result) == len(plaintext)
        mock_reader.readexactly.assert_called_once_with(len(plaintext))

    @pytest.mark.asyncio
    async def test_readexactly_incomplete_read_error(self, encrypted_reader, mock_reader):
        """Test readexactly raises IncompleteReadError."""
        import asyncio

        incomplete_data = b"partial"
        mock_reader.readexactly.side_effect = asyncio.IncompleteReadError(
            incomplete_data, 10
        )

        with pytest.raises(asyncio.IncompleteReadError):
            await encrypted_reader.readexactly(10)

    @pytest.mark.asyncio
    async def test_read_partial_encrypted_data(self, encrypted_reader, mock_reader):
        """Test reading partial encrypted data."""
        plaintext = b"Partial read test data"
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        # Simulate partial read
        mock_reader.read.return_value = encrypted[:10]

        result = await encrypted_reader.read(10)

        # Should decrypt whatever was read
        assert len(result) == 10
        # Result should be decrypted (can't directly compare due to encryption)
        assert isinstance(result, bytes)

    def test_at_eof(self, encrypted_reader, mock_reader):
        """Test at_eof delegation."""
        mock_reader.at_eof = MagicMock(return_value=True)

        assert encrypted_reader.at_eof() is True
        mock_reader.at_eof.assert_called_once()

        mock_reader.at_eof = MagicMock(return_value=False)
        assert encrypted_reader.at_eof() is False

    @pytest.mark.asyncio
    async def test_attribute_delegation(self, encrypted_reader, mock_reader):
        """Test that other attributes are delegated to underlying reader."""
        mock_reader.custom_attr = "test_value"

        assert encrypted_reader.custom_attr == "test_value"

    @pytest.mark.asyncio
    async def test_read_large_data(self, encrypted_reader, mock_reader):
        """Test reading large data."""
        plaintext = b"x" * 10240  # 10KB
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        mock_reader.read.return_value = encrypted

        result = await encrypted_reader.read(-1)

        assert result == plaintext
        assert len(result) == len(plaintext)

    @pytest.mark.asyncio
    async def test_decryption_round_trip(self, encrypted_reader, mock_reader):
        """Test that decryption correctly recovers plaintext."""
        plaintext = b"Round trip test data"
        encrypted = encrypted_reader.cipher.encrypt(plaintext)

        mock_reader.read.return_value = encrypted

        result = await encrypted_reader.read(-1)

        assert result == plaintext


class TestEncryptedStreamWriter:
    """Tests for EncryptedStreamWriter."""

    @pytest.fixture
    def mock_writer(self):
        """Create mock StreamWriter."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        writer.get_extra_info = MagicMock()
        return writer

    @pytest.fixture
    def cipher(self):
        """Create test cipher."""
        return RC4Cipher(b"test_key_16bytes")

    @pytest.fixture
    def encrypted_writer(self, mock_writer, cipher):
        """Create EncryptedStreamWriter instance."""
        return EncryptedStreamWriter(mock_writer, cipher)

    def test_init(self, encrypted_writer, mock_writer, cipher):
        """Test EncryptedStreamWriter initialization."""
        assert encrypted_writer.writer == mock_writer
        assert encrypted_writer.cipher == cipher

    def test_write(self, encrypted_writer, mock_writer):
        """Test write method encrypts and writes."""
        plaintext = b"Hello, World!"

        encrypted_writer.write(plaintext)

        # Verify write was called once
        assert mock_writer.write.call_count == 1
        # Get the encrypted data that was written
        call_args = mock_writer.write.call_args[0]
        encrypted = call_args[0]
        
        # Verify we can decrypt it back to original
        decrypted = encrypted_writer.cipher.decrypt(encrypted)
        assert decrypted == plaintext

    def test_write_empty_data(self, encrypted_writer, mock_writer):
        """Test writing empty data does nothing."""
        encrypted_writer.write(b"")

        mock_writer.write.assert_not_called()

    def test_write_multiple_times(self, encrypted_writer, mock_writer):
        """Test writing multiple times."""
        data1 = b"First chunk"
        data2 = b"Second chunk"

        encrypted_writer.write(data1)
        encrypted_writer.write(data2)

        assert mock_writer.write.call_count == 2

    @pytest.mark.asyncio
    async def test_drain(self, encrypted_writer, mock_writer):
        """Test drain method."""
        await encrypted_writer.drain()

        mock_writer.drain.assert_called_once()

    def test_close(self, encrypted_writer, mock_writer):
        """Test close method."""
        encrypted_writer.close()

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_closed(self, encrypted_writer, mock_writer):
        """Test wait_closed method."""
        await encrypted_writer.wait_closed()

        mock_writer.wait_closed.assert_called_once()

    def test_get_extra_info(self, encrypted_writer, mock_writer):
        """Test get_extra_info method."""
        mock_writer.get_extra_info.return_value = "test_value"

        result = encrypted_writer.get_extra_info("peername")

        assert result == "test_value"
        mock_writer.get_extra_info.assert_called_once_with("peername", None)

    def test_get_extra_info_with_default(self, encrypted_writer, mock_writer):
        """Test get_extra_info with default value."""
        # The wrapper passes the default parameter through to the underlying writer
        mock_writer.get_extra_info.return_value = None

        result = encrypted_writer.get_extra_info("unknown", default="default")

        # Verify the call was made with the default value we passed
        mock_writer.get_extra_info.assert_called_once_with("unknown", "default")
        # The wrapper just delegates, so result is what the mock returns
        assert result is None

    def test_attribute_delegation(self, encrypted_writer, mock_writer):
        """Test that other attributes are delegated to underlying writer."""
        mock_writer.custom_attr = "test_value"

        assert encrypted_writer.custom_attr == "test_value"

    def test_write_large_data(self, encrypted_writer, mock_writer):
        """Test writing large data."""
        plaintext = b"y" * 10240  # 10KB

        encrypted_writer.write(plaintext)

        # Verify write was called
        assert mock_writer.write.call_count == 1
        # Get the encrypted data that was written
        call_args = mock_writer.write.call_args[0]
        encrypted = call_args[0]
        
        # Verify we can decrypt it back and length matches
        decrypted = encrypted_writer.cipher.decrypt(encrypted)
        assert decrypted == plaintext
        assert len(encrypted) == len(plaintext)

    def test_encryption_round_trip(self, encrypted_writer, mock_writer):
        """Test that encryption produces correct ciphertext."""
        plaintext = b"Round trip test"

        encrypted_writer.write(plaintext)

        # Get the encrypted data that was written
        call_args = mock_writer.write.call_args[0]
        encrypted = call_args[0]

        # Verify we can decrypt it back
        decrypted = encrypted_writer.cipher.decrypt(encrypted)
        assert decrypted == plaintext


class TestEncryptedStreamIntegration:
    """Integration tests for encrypted streams."""

    @pytest.fixture
    def cipher(self):
        """Create shared cipher for reader and writer."""
        return RC4Cipher(b"shared_test_key_16")

    @pytest.fixture
    def mock_reader(self):
        """Create mock reader."""
        return AsyncMock()

    @pytest.fixture
    def mock_writer(self):
        """Create mock writer."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        return writer

    @pytest.mark.asyncio
    async def test_full_encrypt_decrypt_round_trip(
        self, cipher, mock_reader, mock_writer
    ):
        """Test full encryption/decryption round-trip."""
        plaintext = b"Integration test data"

        # Write through encrypted writer
        writer = EncryptedStreamWriter(mock_writer, cipher)
        writer.write(plaintext)

        # Get encrypted data
        encrypted = mock_writer.write.call_args[0][0]

        # Read through encrypted reader
        reader = EncryptedStreamReader(mock_reader, cipher)
        mock_reader.read.return_value = encrypted

        result = await reader.read(-1)

        assert result == plaintext

    @pytest.mark.asyncio
    async def test_multiple_chunks(self, cipher, mock_reader, mock_writer):
        """Test multiple chunks of data."""
        chunks = [b"Chunk 1", b"Chunk 2", b"Chunk 3"]

        writer = EncryptedStreamWriter(mock_writer, cipher)
        for chunk in chunks:
            writer.write(chunk)

        # Collect all encrypted chunks
        all_encrypted = b"".join(
            call[0][0] for call in mock_writer.write.call_args_list
        )

        # Read all chunks
        reader = EncryptedStreamReader(mock_reader, cipher)
        mock_reader.read.return_value = all_encrypted

        result = await reader.read(-1)

        # Verify all chunks can be decrypted
        assert result == b"".join(chunks)

    @pytest.mark.asyncio
    async def test_readexactly_integration(self, cipher, mock_reader):
        """Test readexactly with encrypted stream."""
        plaintext = b"Exact read integration test"
        encrypted = cipher.encrypt(plaintext)

        reader = EncryptedStreamReader(mock_reader, cipher)
        mock_reader.readexactly.return_value = encrypted

        result = await reader.readexactly(len(plaintext))

        assert result == plaintext
        assert len(result) == len(plaintext)

