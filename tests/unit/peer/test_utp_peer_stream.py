"""Tests for uTP peer stream reader and writer (lines 42-138 of utp_peer.py).

Covers:
- UTPStreamReader read and readexactly methods
- UTPStreamWriter write, drain, close methods
- Buffer management and error handling
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.peer.utp_peer import UTPStreamReader, UTPStreamWriter
from ccbt.transport.utp import UTPConnection

pytestmark = [pytest.mark.unit, pytest.mark.peer]


@pytest.fixture
def mock_utp_connection():
    """Create a mock uTP connection."""
    conn = MagicMock(spec=UTPConnection)
    conn.receive = AsyncMock()
    conn.send = AsyncMock()
    return conn


class TestUTPStreamReader:
    """Tests for UTPStreamReader (lines 42-92)."""

    @pytest.mark.asyncio
    async def test_read_all_available_with_buffer(self, mock_utp_connection):
        """Test read(-1) with buffer data (lines 54-59)."""
        reader = UTPStreamReader(mock_utp_connection)
        reader._buffer.extend(b"test data")
        
        result = await reader.read(-1)
        
        assert result == b"test data"
        assert len(reader._buffer) == 0

    @pytest.mark.asyncio
    async def test_read_all_available_without_buffer(self, mock_utp_connection):
        """Test read(-1) without buffer (line 60)."""
        reader = UTPStreamReader(mock_utp_connection)
        mock_utp_connection.receive.return_value = b"data from connection"
        
        result = await reader.read(-1)
        
        assert result == b"data from connection"
        mock_utp_connection.receive.assert_called_once_with(-1)

    @pytest.mark.asyncio
    async def test_read_exact_bytes_with_buffer(self, mock_utp_connection):
        """Test read(n) with partial buffer (lines 62-74)."""
        reader = UTPStreamReader(mock_utp_connection)
        reader._buffer.extend(b"test")  # 4 bytes
        mock_utp_connection.receive.return_value = b" data"  # More bytes
        
        result = await reader.read(9)  # Request 9 bytes
        
        assert result == b"test data"
        assert len(reader._buffer) == 0

    @pytest.mark.asyncio
    async def test_read_exact_bytes_connection_closed(self, mock_utp_connection):
        """Test read(n) when connection closes (lines 66-68)."""
        reader = UTPStreamReader(mock_utp_connection)
        reader._buffer.extend(b"test")  # 4 bytes
        mock_utp_connection.receive.return_value = b""  # Connection closed
        
        result = await reader.read(10)  # Request 10 bytes, only 4 available
        
        assert result == b"test"  # Should return what's available

    @pytest.mark.asyncio
    async def test_readexactly_success(self, mock_utp_connection):
        """Test readexactly with enough data (line 88)."""
        reader = UTPStreamReader(mock_utp_connection)
        mock_utp_connection.receive.return_value = b"test data"
        
        result = await reader.readexactly(9)
        
        assert result == b"test data"

    @pytest.mark.asyncio
    async def test_readexactly_eof_error(self, mock_utp_connection):
        """Test readexactly raises EOFError when insufficient data (lines 89-91)."""
        reader = UTPStreamReader(mock_utp_connection)
        # Simulate connection closing by returning empty bytes after initial data
        call_count = [0]
        async def mock_receive(n):
            call_count[0] += 1
            if call_count[0] == 1:
                return b"test"  # Only 4 bytes on first call
            return b""  # Connection closed on subsequent calls
        
        mock_utp_connection.receive = AsyncMock(side_effect=mock_receive)
        
        with pytest.raises(EOFError, match="Connection closed: expected 10 bytes"):
            await reader.readexactly(10)


class TestUTPStreamWriter:
    """Tests for UTPStreamWriter (lines 95-138)."""

    @pytest.mark.asyncio
    async def test_write_success(self, mock_utp_connection):
        """Test write method (lines 107-124)."""
        writer = UTPStreamWriter(mock_utp_connection)
        
        await writer.write(b"test data")
        
        mock_utp_connection.send.assert_called_once_with(b"test data")

    @pytest.mark.asyncio
    async def test_write_when_closed(self, mock_utp_connection):
        """Test write raises RuntimeError when closed (lines 116-118)."""
        writer = UTPStreamWriter(mock_utp_connection)
        writer._closed = True
        
        with pytest.raises(RuntimeError, match="Cannot write to closed connection"):
            await writer.write(b"test")

    @pytest.mark.asyncio
    async def test_write_when_connection_none(self, mock_utp_connection):
        """Test write raises RuntimeError when connection is None (lines 120-122)."""
        writer = UTPStreamWriter(mock_utp_connection)
        writer.utp_connection = None
        
        with pytest.raises(RuntimeError, match="uTP connection not initialized"):
            await writer.write(b"test")

    @pytest.mark.asyncio
    async def test_drain(self, mock_utp_connection):
        """Test drain method (lines 126-130)."""
        writer = UTPStreamWriter(mock_utp_connection)
        
        start = asyncio.get_event_loop().time()
        await writer.drain()
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should wait approximately 0.01 seconds
        assert elapsed >= 0.005  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_close(self, mock_utp_connection):
        """Test close method (lines 132-134)."""
        writer = UTPStreamWriter(mock_utp_connection)
        
        await writer.close()
        
        assert writer._closed is True

    def test_is_closing_when_open(self, mock_utp_connection):
        """Test is_closing returns False when open (line 138)."""
        writer = UTPStreamWriter(mock_utp_connection)
        
        assert writer.is_closing() is False

    def test_is_closing_when_closed(self, mock_utp_connection):
        """Test is_closing returns True when closed (line 138)."""
        writer = UTPStreamWriter(mock_utp_connection)
        writer._closed = True
        
        assert writer.is_closing() is True

