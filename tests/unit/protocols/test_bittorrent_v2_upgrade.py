"""Unit tests for BitTorrent v2 protocol upgrade functionality."""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.core.bencode import BencodeDecoder, BencodeEncoder
from ccbt.extensions.protocol import ExtensionMessageType
from ccbt.protocols.bittorrent_v2 import (
    INFO_HASH_V2_LEN,
    PEER_ID_LEN,
    PROTOCOL_STRING,
    PROTOCOL_STRING_LEN,
    RESERVED_BYTES_LEN,
    ProtocolVersion,
    _check_extension_protocol_support,
    _receive_extension_message,
    _send_extension_message,
    _upgrade_via_direct_handshake,
    _upgrade_via_extension_protocol,
    upgrade_to_v2,
)


@pytest.mark.asyncio
class TestSendExtensionMessage:
    """Test _send_extension_message function."""

    async def test_send_extension_message_success(self):
        """Test successful extension message sending."""
        connection = MagicMock()
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()  # write is synchronous
        connection.writer.drain = AsyncMock()  # drain is async

        result = await _send_extension_message(connection, 1, b"test payload")

        assert result is True
        connection.writer.write.assert_called_once()
        connection.writer.drain.assert_awaited_once()

    async def test_send_extension_message_no_writer(self):
        """Test extension message sending with no writer."""
        connection = MagicMock()
        connection.writer = None

        result = await _send_extension_message(connection, 1, b"test payload")

        assert result is False

    async def test_send_extension_message_write_error(self):
        """Test extension message sending with write error."""
        connection = MagicMock()
        connection.writer = MagicMock()  # Use MagicMock instead of AsyncMock
        connection.writer.write = MagicMock(side_effect=Exception("Write error"))
        connection.writer.drain = AsyncMock()

        result = await _send_extension_message(connection, 1, b"test payload")

        assert result is False


@pytest.mark.asyncio
class TestReceiveExtensionMessage:
    """Test _receive_extension_message function."""

    async def test_receive_extension_message_success(self):
        """Test successful extension message receiving."""
        connection = MagicMock()
        connection.reader = AsyncMock()

        # Mock extension message: <length><message_id_20><extension_id><bencoded_data>
        extension_id = 1
        bencoded_data = b"d3:key5:valuee"
        payload = struct.pack("B", ExtensionMessageType.EXTENDED) + struct.pack(
            "B",
            extension_id,
        ) + bencoded_data
        message_length = len(payload)
        length_data = struct.pack("!I", message_length)

        connection.reader.readexactly = AsyncMock(
            side_effect=[length_data, payload],
        )

        result = await _receive_extension_message(connection, timeout=10.0)

        assert result is not None
        ext_id, bencoded = result
        assert ext_id == extension_id
        assert bencoded == bencoded_data

    async def test_receive_extension_message_keep_alive(self):
        """Test receiving keep-alive message instead of extension."""
        connection = MagicMock()
        connection.reader = AsyncMock()

        # Keep-alive message (length 0)
        length_data = struct.pack("!I", 0)
        connection.reader.readexactly = AsyncMock(return_value=length_data)

        result = await _receive_extension_message(connection)

        assert result is None

    async def test_receive_extension_message_not_extension(self):
        """Test receiving non-extension message."""
        connection = MagicMock()
        connection.reader = AsyncMock()

        # Non-extension message (ID 1)
        payload = struct.pack("B", 1) + b"data"
        message_length = len(payload)
        length_data = struct.pack("!I", message_length)

        connection.reader.readexactly = AsyncMock(
            side_effect=[length_data, payload],
        )

        result = await _receive_extension_message(connection)

        assert result is None

    async def test_receive_extension_message_timeout(self):
        """Test extension message receive timeout."""
        connection = MagicMock()
        connection.reader = AsyncMock()
        connection.reader.readexactly = AsyncMock(
            side_effect=asyncio.TimeoutError(),
        )

        result = await _receive_extension_message(connection, timeout=0.1)

        assert result is None

    async def test_receive_extension_message_no_reader(self):
        """Test extension message receive with no reader."""
        connection = MagicMock()
        connection.reader = None

        result = await _receive_extension_message(connection)

        assert result is None

    async def test_receive_extension_message_short_payload(self):
        """Test extension message receive with short payload."""
        connection = MagicMock()
        connection.reader = AsyncMock()

        # Payload too short (only message ID, no extension ID)
        payload = struct.pack("B", ExtensionMessageType.EXTENDED)
        message_length = len(payload)
        length_data = struct.pack("!I", message_length)

        connection.reader.readexactly = AsyncMock(
            side_effect=[length_data, payload],
        )

        result = await _receive_extension_message(connection)

        assert result is None


class TestCheckExtensionProtocolSupport:
    """Test _check_extension_protocol_support function."""

    def test_check_extension_protocol_support_with_protocol(self):
        """Test checking extension protocol support when protocol exists."""
        connection = MagicMock()
        # Use a real object instead of MagicMock to pass the isinstance check
        class FakeExtensionProtocol:
            pass
        connection.extension_protocol = FakeExtensionProtocol()

        result = _check_extension_protocol_support(connection)

        assert result is True

    def test_check_extension_protocol_support_with_manager(self):
        """Test checking extension protocol support with extension manager."""
        connection = MagicMock()
        connection.extension_protocol = None
        # Use a real object instead of MagicMock to pass the isinstance check
        class FakeExtensionManager:
            def is_extension_active(self, name):
                return True
        connection.extension_manager = FakeExtensionManager()

        result = _check_extension_protocol_support(connection)

        assert result is True

    def test_check_extension_protocol_support_with_reserved_bytes(self):
        """Test checking extension protocol support via reserved bytes."""
        connection = MagicMock()
        connection.extension_protocol = None
        connection.extension_manager = None
        reserved_bytes = bytearray(RESERVED_BYTES_LEN)
        reserved_bytes[0] |= 0x10  # Set bit 5 for extension protocol
        connection.reserved_bytes = bytes(reserved_bytes)

        result = _check_extension_protocol_support(connection)

        assert result is True

    def test_check_extension_protocol_support_no_support(self):
        """Test checking extension protocol support when not supported."""
        connection = MagicMock()
        connection.extension_protocol = None
        connection.extension_manager = None
        reserved_bytes = bytearray(RESERVED_BYTES_LEN)
        # Bit 5 not set
        connection.reserved_bytes = bytes(reserved_bytes)

        result = _check_extension_protocol_support(connection)

        assert result is False

    def test_check_extension_protocol_support_no_attributes(self):
        """Test checking extension protocol support with no relevant attributes."""
        connection = MagicMock()
        connection.extension_protocol = None
        connection.extension_manager = None

        result = _check_extension_protocol_support(connection)

        assert result is False


@pytest.mark.asyncio
class TestUpgradeViaExtensionProtocol:
    """Test _upgrade_via_extension_protocol function."""

    async def test_upgrade_via_extension_protocol_success(self):
        """Test successful upgrade via extension protocol."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.protocol_version = None
        connection.info_hash_v2 = None

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Create upgrade request
        upgrade_request = {
            b"info_hash_v2": info_hash_v2,
            b"peer_id": connection.our_peer_id,
            b"version": b"2.0",
        }
        encoder = BencodeEncoder()
        bencoded_request = encoder.encode(upgrade_request)

        # Create upgrade response
        upgrade_response = {
            b"info_hash_v2": info_hash_v2,
            b"peer_id": b"q" * PEER_ID_LEN,
            b"version": b"2.0",
        }
        encoder_response = BencodeEncoder()
        bencoded_response = encoder_response.encode(upgrade_response)

        # Mock extension message response
        extension_id = 1
        payload = (
            struct.pack("B", ExtensionMessageType.EXTENDED)
            + struct.pack("B", extension_id)
            + bencoded_response
        )
        message_length = len(payload)
        length_data = struct.pack("!I", message_length)

        connection.reader.readexactly = AsyncMock(
            side_effect=[length_data, payload],
        )

        result = await _upgrade_via_extension_protocol(connection, info_hash_v2)

        assert result is True
        assert connection.protocol_version == ProtocolVersion.V2
        assert connection.info_hash_v2 == info_hash_v2
        connection.writer.write.assert_called_once()
        connection.writer.drain.assert_awaited_once()

    async def test_upgrade_via_extension_protocol_hash_mismatch(self):
        """Test upgrade via extension protocol with hash mismatch."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_info_hash_v2 = b"j" * INFO_HASH_V2_LEN  # Different hash

        # Create upgrade response with mismatched hash
        upgrade_response = {
            b"info_hash_v2": peer_info_hash_v2,
            b"peer_id": b"q" * PEER_ID_LEN,
            b"version": b"2.0",
        }
        encoder = BencodeEncoder()
        bencoded_response = encoder.encode(upgrade_response)

        # Mock extension message response
        extension_id = 1
        payload = (
            struct.pack("B", ExtensionMessageType.EXTENDED)
            + struct.pack("B", extension_id)
            + bencoded_response
        )
        message_length = len(payload)
        length_data = struct.pack("!I", message_length)

        connection.reader.readexactly = AsyncMock(
            side_effect=[length_data, payload],
        )

        result = await _upgrade_via_extension_protocol(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_via_extension_protocol_no_response(self):
        """Test upgrade via extension protocol with no response."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Mock _receive_extension_message to return None
        with patch(
            "ccbt.protocols.bittorrent_v2._receive_extension_message",
            return_value=None,
        ):
            result = await _upgrade_via_extension_protocol(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_via_extension_protocol_no_reader(self):
        """Test upgrade via extension protocol with no reader."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = None
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        result = await _upgrade_via_extension_protocol(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_via_extension_protocol_timeout(self):
        """Test upgrade via extension protocol with timeout."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Mock _receive_extension_message to raise timeout
        with patch(
            "ccbt.protocols.bittorrent_v2._receive_extension_message",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await _upgrade_via_extension_protocol(connection, info_hash_v2)

        assert result is False


@pytest.mark.asyncio
class TestUpgradeViaDirectHandshake:
    """Test _upgrade_via_direct_handshake function."""

    async def test_upgrade_via_direct_handshake_success(self):
        """Test successful upgrade via direct handshake."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.protocol_version = None
        connection.info_hash_v2 = None

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN

        # Create v2 handshake response
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01  # Set bit 0 for v2 support
        response_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        connection.reader.readexactly = AsyncMock(return_value=response_handshake)

        result = await _upgrade_via_direct_handshake(connection, info_hash_v2)

        assert result is True
        assert connection.protocol_version == ProtocolVersion.V2
        assert connection.info_hash_v2 == info_hash_v2
        connection.writer.write.assert_called_once()
        connection.writer.drain.assert_awaited_once()

    async def test_upgrade_via_direct_handshake_hash_mismatch(self):
        """Test upgrade via direct handshake with hash mismatch."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_info_hash_v2 = b"j" * INFO_HASH_V2_LEN  # Different hash
        peer_id = b"q" * PEER_ID_LEN

        # Create v2 handshake response with mismatched hash
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        response_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + peer_info_hash_v2
            + peer_id
        )

        connection.reader.readexactly = AsyncMock(return_value=response_handshake)

        result = await _upgrade_via_direct_handshake(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_via_direct_handshake_timeout(self):
        """Test upgrade via direct handshake with timeout."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        connection.reader.readexactly = AsyncMock(
            side_effect=asyncio.TimeoutError(),
        )
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        result = await _upgrade_via_direct_handshake(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_via_direct_handshake_no_reader(self):
        """Test upgrade via direct handshake with no reader."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = None
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        result = await _upgrade_via_direct_handshake(connection, info_hash_v2)

        assert result is False


@pytest.mark.asyncio
class TestUpgradeToV2:
    """Test upgrade_to_v2 function."""

    async def test_upgrade_to_v2_invalid_hash_length(self):
        """Test upgrade with invalid info_hash_v2 length."""
        connection = MagicMock()
        connection.writer = AsyncMock()

        invalid_hash = b"i" * 20  # Wrong length

        result = await upgrade_to_v2(connection, invalid_hash)

        assert result is False

    async def test_upgrade_to_v2_no_writer(self):
        """Test upgrade with no writer."""
        connection = MagicMock()
        connection.writer = None

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is False

    async def test_upgrade_to_v2_with_extension_protocol(self):
        """Test upgrade using extension protocol."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        # Use a real object instead of MagicMock to pass the isinstance check
        class FakeExtensionProtocol:
            pass
        connection.extension_protocol = FakeExtensionProtocol()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Mock successful extension protocol upgrade
        with patch(
            "ccbt.protocols.bittorrent_v2._upgrade_via_extension_protocol",
            return_value=True,
        ) as mock_upgrade:
            result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is True
        mock_upgrade.assert_awaited_once_with(connection, info_hash_v2)

    async def test_upgrade_to_v2_without_extension_protocol(self):
        """Test upgrade without extension protocol (fallback)."""
        connection = MagicMock()
        connection.writer = AsyncMock()
        connection.reader = AsyncMock()
        # No extension protocol
        connection.extension_protocol = None
        connection.extension_manager = None
        connection.reserved_bytes = bytearray(RESERVED_BYTES_LEN)
        connection.our_peer_id = b"p" * PEER_ID_LEN

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Mock successful direct handshake upgrade
        with patch(
            "ccbt.protocols.bittorrent_v2._upgrade_via_direct_handshake",
            return_value=True,
        ) as mock_upgrade:
            result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is True
        mock_upgrade.assert_awaited_once_with(connection, info_hash_v2)

