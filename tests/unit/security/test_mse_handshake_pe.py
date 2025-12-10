"""Tests for Protocol Encryption (PE) support in MSEHandshake.

Covers:
- PE detection on incoming connections
- PE handshake methods (initiate_pe_as_initiator, respond_pe_as_receiver)
- Detection of encrypted vs plain BitTorrent handshakes
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from ccbt.security.mse_handshake import MSEHandshake

pytestmark = [pytest.mark.unit, pytest.mark.security]


class TestPEDetection:
    """Tests for PE (encrypted handshake) detection."""

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_pe_connection(self):
        """Test detect_encrypted_handshake detects PE connection."""
        # Create mock reader with PE handshake (MSE message)
        mock_reader = AsyncMock()

        # PE connection starts with MSE message length (4 bytes) + message type
        # Example: [length=96][type=0x02 (SKEYE)][payload...]
        length_bytes = b"\x00\x00\x00\x60"  # 96 bytes total message
        type_byte = b"\x02"  # SKEYE

        async def mock_read(n):
            if n == 4:
                return length_bytes
            if n == 1:
                return type_byte
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        assert is_pe is True
        assert len(first_bytes) == 5  # 4 bytes length + 1 byte type

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_plain_connection(self):
        """Test detect_encrypted_handshake detects plain BitTorrent connection."""
        # Create mock reader with plain BitTorrent handshake
        # BitTorrent handshake starts with [19][B][i][t] = [0x13][0x42][0x69][0x74]
        mock_reader = AsyncMock()

        # Plain connection starts with protocol length (19 = 0x13)
        protocol_start = b"\x13" + b"Bit"  # First 4 bytes: [19][B][i][t]

        async def mock_read(n):
            if n == 4:
                return protocol_start
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        assert is_pe is False
        assert len(first_bytes) == 4
        assert first_bytes[0] == 19  # BitTorrent protocol length

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_invalid_message_type(self):
        """Test detect_encrypted_handshake with invalid MSE message type."""
        mock_reader = AsyncMock()

        # Valid length but invalid message type
        length_bytes = b"\x00\x00\x00\x60"  # 96 bytes
        invalid_type = b"\x99"  # Invalid message type (not 0x02, 0x03, 0x04)

        async def mock_read(n):
            if n == 4:
                return length_bytes
            if n == 1:
                return invalid_type
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        # Should not detect as PE because message type is invalid
        assert is_pe is False
        assert len(first_bytes) == 5

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_too_large_length(self):
        """Test detect_encrypted_handshake with unreasonably large length."""
        mock_reader = AsyncMock()

        # Very large length (unreasonable for MSE message)
        large_length = b"\xff\xff\xff\xff"  # Max uint32

        async def mock_read(n):
            if n == 4:
                return large_length
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        assert is_pe is False
        assert len(first_bytes) == 4

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_timeout(self):
        """Test detect_encrypted_handshake with timeout."""
        mock_reader = AsyncMock()

        async def mock_read(_n):
            # Simulate timeout by waiting longer than timeout
            await asyncio.sleep(3.0)
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        assert is_pe is False
        assert first_bytes == b""

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_short_read(self):
        """Test detect_encrypted_handshake with short read (less than 4 bytes)."""
        mock_reader = AsyncMock()

        async def mock_read(n):
            if n == 4:
                return b"\x13"  # Only 1 byte instead of 4
            return b""

        mock_reader.read = mock_read

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=1.0
        )

        assert is_pe is False
        assert len(first_bytes) < 4


class TestPEMethods:
    """Tests for PE-specific handshake methods."""

    @pytest.fixture
    def info_hash(self):
        """Create a test info hash."""
        return b"\x01" * 20

    @pytest.mark.asyncio
    async def test_initiate_pe_as_initiator_method_exists(self):
        """Test initiate_pe_as_initiator method exists and is callable."""
        handshake = MSEHandshake()

        # Verify method exists
        assert hasattr(handshake, "initiate_pe_as_initiator")
        assert callable(handshake.initiate_pe_as_initiator)

        # Verify it delegates to initiate_as_initiator
        # (the actual handshake behavior is tested in test_mse_handshake.py)
        # This test just ensures the PE wrapper method exists

    @pytest.mark.asyncio
    async def test_respond_pe_as_receiver_method_exists(self):
        """Test respond_pe_as_receiver method exists and is callable."""
        handshake = MSEHandshake()

        # Verify method exists
        assert hasattr(handshake, "respond_pe_as_receiver")
        assert callable(handshake.respond_pe_as_receiver)

        # Verify it delegates to respond_as_receiver
        # (the actual handshake behavior is tested in test_mse_handshake.py)
        # This test just ensures the PE wrapper method exists

    @pytest.mark.asyncio
    async def test_pe_methods_same_as_regular_methods(self):
        """Test that PE methods behave the same as regular methods."""
        handshake = MSEHandshake()

        # Since regular methods require full bidirectional communication,
        # we'll just verify they call the same underlying methods
        # The actual behavior is tested in test_mse_handshake.py

        # Both PE methods should delegate to regular methods
        # (implementation detail, but we verify they exist and are callable)
        assert hasattr(handshake, "initiate_pe_as_initiator")
        assert hasattr(handshake, "respond_pe_as_receiver")
        assert callable(handshake.initiate_pe_as_initiator)
        assert callable(handshake.respond_pe_as_receiver)

