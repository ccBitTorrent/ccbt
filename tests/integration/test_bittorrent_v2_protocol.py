"""Integration tests for BitTorrent Protocol v2 (BEP 52) communication.

Tests for protocol handshake exchange, message exchange, and protocol upgrade
in realistic async scenarios.
Target: 90%+ integration test coverage for v2 protocol workflows.
"""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.protocols]

from ccbt.protocols.bittorrent_v2 import (
    HANDSHAKE_V1_SIZE,
    HANDSHAKE_V2_SIZE,
    INFO_HASH_V1_LEN,
    INFO_HASH_V2_LEN,
    MESSAGE_ID_FILE_TREE_REQUEST,
    MESSAGE_ID_FILE_TREE_RESPONSE,
    MESSAGE_ID_PIECE_LAYER_REQUEST,
    MESSAGE_ID_PIECE_LAYER_RESPONSE,
    PEER_ID_LEN,
    PROTOCOL_STRING,
    PROTOCOL_STRING_LEN,
    RESERVED_BYTES_LEN,
    FileTreeRequest,
    FileTreeResponse,
    PieceLayerRequest,
    PieceLayerResponse,
    ProtocolVersion,
    ProtocolVersionError,
    create_hybrid_handshake,
    create_v2_handshake,
    detect_protocol_version,
    handle_v2_handshake,
    negotiate_protocol_version,
    parse_v2_handshake,
    send_hybrid_handshake,
    send_v2_handshake,
    upgrade_to_v2,
)


class MockStreamWriter:
    """Mock asyncio.StreamWriter for testing."""

    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, data: bytes):
        """Write data to buffer."""
        self.data.extend(data)

    async def drain(self):
        """Drain (no-op for mock)."""
        await asyncio.sleep(0)

    def close(self):
        """Close the writer."""
        self.closed = True

    async def wait_closed(self):
        """Wait for close."""
        await asyncio.sleep(0)


class MockStreamReader:
    """Mock asyncio.StreamReader for testing."""

    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes."""
        if self.position + n > len(self.data):
            raise asyncio.IncompleteReadError(
                self.data[self.position :], n
            )
        result = self.data[self.position : self.position + n]
        self.position += n
        return result

    async def read(self, n: int = -1) -> bytes:
        """Read up to n bytes."""
        if n == -1:
            result = self.data[self.position :]
            self.position = len(self.data)
        else:
            result = self.data[self.position : self.position + n]
            self.position += min(n, len(self.data) - self.position)
        return result


@pytest.mark.asyncio
class TestV2HandshakeIntegration:
    """Integration tests for v2 handshake exchange."""

    async def test_v2_handshake_exchange_success(self):
        """Test successful v2 handshake exchange between two peers."""
        # Peer A's info
        info_hash_v2_a = b"a" * INFO_HASH_V2_LEN
        peer_id_a = b"A" * PEER_ID_LEN

        # Peer B's info
        info_hash_v2_b = b"a" * INFO_HASH_V2_LEN  # Same torrent
        peer_id_b = b"B" * PEER_ID_LEN

        # Peer A sends handshake
        writer_a = MockStreamWriter()
        await send_v2_handshake(writer_a, info_hash_v2_a, peer_id_a)

        # Peer B receives handshake
        reader_b = MockStreamReader(bytes(writer_a.data))
        writer_b = MockStreamWriter()

        version, received_peer_id, parsed = await handle_v2_handshake(
            reader_b, writer_b, our_info_hash_v2=info_hash_v2_b
        )

        assert version == ProtocolVersion.V2
        assert received_peer_id == peer_id_a
        assert parsed["info_hash_v2"] == info_hash_v2_a

        # Peer B sends handshake back
        await send_v2_handshake(writer_b, info_hash_v2_b, peer_id_b)

        # Peer A receives handshake
        reader_a = MockStreamReader(bytes(writer_b.data))
        writer_a_response = MockStreamWriter()

        version, received_peer_id, parsed = await handle_v2_handshake(
            reader_a, writer_a_response, our_info_hash_v2=info_hash_v2_a
        )

        assert version == ProtocolVersion.V2
        assert received_peer_id == peer_id_b
        assert parsed["info_hash_v2"] == info_hash_v2_b

    async def test_hybrid_handshake_exchange(self):
        """Test hybrid handshake exchange between peers."""
        # Both peers support hybrid - MUST use same hashes
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id_a = b"A" * PEER_ID_LEN

        # Peer A sends hybrid handshake
        writer_a = MockStreamWriter()
        await send_hybrid_handshake(writer_a, info_hash_v1, info_hash_v2, peer_id_a)

        # Verify handshake structure (hybrid is 100 bytes)
        assert len(writer_a.data) == 100

        # Read and parse manually since handle_v2_handshake doesn't support 100-byte hybrid
        handshake_bytes = bytes(writer_a.data)
        
        # Detect version
        version = detect_protocol_version(handshake_bytes)
        assert version == ProtocolVersion.HYBRID

        # Parse handshake
        parsed = parse_v2_handshake(handshake_bytes)
        assert parsed["version"] == ProtocolVersion.HYBRID
        assert parsed["peer_id"] == peer_id_a
        assert parsed["info_hash_v1"] == info_hash_v1
        assert parsed["info_hash_v2"] == info_hash_v2

    async def test_handshake_timeout_handling(self):
        """Test handshake exchange with timeout."""
        # Create a reader that never provides data
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        writer = MockStreamWriter()

        with pytest.raises(asyncio.TimeoutError):
            await handle_v2_handshake(reader, writer, timeout=0.1)

    async def test_handshake_info_hash_validation(self):
        """Test handshake validation rejects wrong info_hash."""
        # Peer A sends handshake with wrong info_hash
        info_hash_v2_a = b"a" * INFO_HASH_V2_LEN
        peer_id_a = b"A" * PEER_ID_LEN

        writer_a = MockStreamWriter()
        await send_v2_handshake(writer_a, info_hash_v2_a, peer_id_a)

        # Peer B expects different info_hash
        expected_hash = b"b" * INFO_HASH_V2_LEN
        reader_b = MockStreamReader(bytes(writer_a.data))
        writer_b = MockStreamWriter()

        with pytest.raises(ValueError, match="Info hash v2 mismatch"):
            await handle_v2_handshake(
                reader_b, writer_b, our_info_hash_v2=expected_hash
            )

    async def test_handshake_version_mismatch_v1_v2(self):
        """Test version negotiation when peer versions don't match."""
        # Peer A is v1-only
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        peer_id_a = b"A" * PEER_ID_LEN

        v1_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN  # No v2 bit
            + info_hash_v1
            + peer_id_a
        )

        # Peer B only supports v2
        supported_versions = [ProtocolVersion.V2]
        negotiated = negotiate_protocol_version(v1_handshake, supported_versions)

        # Should return None for incompatible versions
        assert negotiated is None

    async def test_handshake_incomplete_read(self):
        """Test handling incomplete handshake data."""
        # Create partial handshake data (truncated)
        partial_data = b"x" * 50  # Less than full handshake

        reader = MockStreamReader(partial_data)
        writer = MockStreamWriter()

        with pytest.raises((ProtocolVersionError, asyncio.IncompleteReadError)):
            await handle_v2_handshake(reader, writer)

    async def test_concurrent_handshake_exchanges(self):
        """Test multiple concurrent handshake exchanges."""
        # Simulate multiple peers connecting simultaneously
        peers = []
        for i in range(5):
            info_hash_v2 = b"h" * INFO_HASH_V2_LEN
            peer_id = (b"P" + str(i).encode() + b"x" * 18)[:PEER_ID_LEN]
            peers.append((info_hash_v2, peer_id))

        async def exchange_handshake(info_hash, peer_id):
            """Exchange handshake with a peer."""
            writer = MockStreamWriter()
            await send_v2_handshake(writer, info_hash, peer_id)

            reader = MockStreamReader(bytes(writer.data))
            response_writer = MockStreamWriter()

            version, received_id, parsed = await handle_v2_handshake(
                reader, response_writer, our_info_hash_v2=info_hash
            )
            return (version, received_id)

        # Run all exchanges concurrently
        tasks = [exchange_handshake(h, pid) for h, pid in peers]
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 5
        for i, (version, peer_id) in enumerate(results):
            assert version == ProtocolVersion.V2
            assert peer_id == peers[i][1]


@pytest.mark.asyncio
class TestV2MessageExchange:
    """Integration tests for v2 message exchange."""

    async def test_piece_layer_request_response_exchange(self):
        """Test piece layer request/response exchange."""
        # Peer A requests piece layer
        pieces_root = b"r" * 32
        request = PieceLayerRequest(pieces_root)
        request_data = request.serialize()

        # Send through mock stream
        writer = MockStreamWriter()
        writer.write(request_data)

        # Peer B receives request
        reader = MockStreamReader(bytes(writer.data))
        received_data = await reader.readexactly(len(request_data))

        # Parse request (skip length prefix)
        parsed_request = PieceLayerRequest.deserialize(received_data[4:])
        assert parsed_request.pieces_root == pieces_root

        # Peer B sends response
        piece_hashes = [b"h" + b"\x00" * 31 for _ in range(3)]
        response = PieceLayerResponse(pieces_root, piece_hashes)
        response_data = response.serialize()

        response_writer = MockStreamWriter()
        response_writer.write(response_data)

        # Peer A receives response
        response_reader = MockStreamReader(bytes(response_writer.data))
        received_response_data = await response_reader.readexactly(len(response_data))

        # Parse response
        parsed_response = PieceLayerResponse.deserialize(received_response_data[4:])
        assert parsed_response.pieces_root == pieces_root
        assert len(parsed_response.piece_hashes) == 3
        assert parsed_response.piece_hashes == piece_hashes

    async def test_file_tree_request_response_exchange(self):
        """Test file tree request/response exchange."""
        # Peer A requests file tree
        request = FileTreeRequest()
        request_data = request.serialize()

        writer = MockStreamWriter()
        writer.write(request_data)

        # Peer B receives request
        reader = MockStreamReader(bytes(writer.data))
        received_data = await reader.readexactly(len(request_data))

        # Parse request
        parsed_request = FileTreeRequest.deserialize(received_data[4:])
        assert parsed_request.message_id == MESSAGE_ID_FILE_TREE_REQUEST

        # Peer B sends response with file tree
        file_tree_data = b"d4:file6:lengthi12345ee"  # Bencoded
        response = FileTreeResponse(file_tree_data)
        response_data = response.serialize()

        response_writer = MockStreamWriter()
        response_writer.write(response_data)

        # Peer A receives response
        response_reader = MockStreamReader(bytes(response_writer.data))
        received_response_data = await response_reader.readexactly(len(response_data))

        # Parse response
        parsed_response = FileTreeResponse.deserialize(received_response_data[4:])
        assert parsed_response.file_tree == file_tree_data

    async def test_message_serialization_through_async_streams(self):
        """Test that messages serialize correctly through async streams."""
        # Create various messages
        pieces_root = b"r" * 32
        piece_hashes = [b"h" + b"\x00" * 31, b"i" + b"\x00" * 31]

        messages = [
            PieceLayerRequest(pieces_root),
            PieceLayerResponse(pieces_root, piece_hashes),
            FileTreeRequest(),
            FileTreeResponse(b"d4:test5:valuee"),
        ]

        for msg in messages:
            # Serialize
            data = msg.serialize()

            # Send through stream
            writer = MockStreamWriter()
            writer.write(data)
            await writer.drain()

            # Read from stream
            reader = MockStreamReader(bytes(writer.data))
            received = await reader.readexactly(len(data))

            # Verify
            assert received == data

    async def test_message_deserialization_from_async_streams(self):
        """Test deserializing messages from async streams."""
        pieces_root = b"r" * 32

        # Create and serialize request
        request = PieceLayerRequest(pieces_root)
        data = request.serialize()

        # Stream the data
        reader = MockStreamReader(data)

        # Read length prefix
        length_bytes = await reader.readexactly(4)
        length = struct.unpack("!I", length_bytes)[0]

        # Read message
        message_bytes = await reader.readexactly(length)

        # Deserialize
        parsed = PieceLayerRequest.deserialize(message_bytes)
        assert parsed.pieces_root == pieces_root

    async def test_message_exchange_incomplete_data(self):
        """Test error handling for incomplete message data."""
        # Create incomplete message (missing data)
        incomplete_data = struct.pack("!I", 100) + b"x" * 50  # Says 100 but only 50

        reader = MockStreamReader(incomplete_data)

        # Read length
        length_bytes = await reader.readexactly(4)
        length = struct.unpack("!I", length_bytes)[0]

        # Try to read message (should fail)
        with pytest.raises(asyncio.IncompleteReadError):
            await reader.readexactly(length)

    async def test_multiple_messages_in_sequence(self):
        """Test sending/receiving multiple messages in sequence."""
        pieces_root1 = b"r" * 32
        pieces_root2 = b"s" * 32

        # Create multiple messages
        msg1 = PieceLayerRequest(pieces_root1)
        msg2 = PieceLayerRequest(pieces_root2)
        msg3 = FileTreeRequest()

        # Serialize all
        data1 = msg1.serialize()
        data2 = msg2.serialize()
        data3 = msg3.serialize()

        # Write to stream
        writer = MockStreamWriter()
        writer.write(data1)
        writer.write(data2)
        writer.write(data3)
        await writer.drain()

        # Read from stream
        reader = MockStreamReader(bytes(writer.data))

        # Read and parse message 1
        length1 = struct.unpack("!I", await reader.readexactly(4))[0]
        parsed1 = PieceLayerRequest.deserialize(await reader.readexactly(length1))
        assert parsed1.pieces_root == pieces_root1

        # Read and parse message 2
        length2 = struct.unpack("!I", await reader.readexactly(4))[0]
        parsed2 = PieceLayerRequest.deserialize(await reader.readexactly(length2))
        assert parsed2.pieces_root == pieces_root2

        # Read and parse message 3
        length3 = struct.unpack("!I", await reader.readexactly(4))[0]
        parsed3 = FileTreeRequest.deserialize(await reader.readexactly(length3))
        assert parsed3.message_id == MESSAGE_ID_FILE_TREE_REQUEST

    async def test_concurrent_message_exchanges(self):
        """Test multiple concurrent message exchanges."""
        async def exchange_messages(peer_id: int):
            """Exchange messages for a peer."""
            pieces_root = (b"p" + str(peer_id).encode() + b"\x00" * 30)[:32]

            # Send request
            request = PieceLayerRequest(pieces_root)
            writer = MockStreamWriter()
            writer.write(request.serialize())
            await writer.drain()

            # Receive and parse
            reader = MockStreamReader(bytes(writer.data))
            length = struct.unpack("!I", await reader.readexactly(4))[0]
            parsed = PieceLayerRequest.deserialize(await reader.readexactly(length))

            return parsed.pieces_root

        # Run 10 concurrent exchanges
        tasks = [exchange_messages(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique


@pytest.mark.asyncio
class TestProtocolUpgrade:
    """Integration tests for protocol upgrade scenarios."""

    async def test_upgrade_v1_to_v2_success(self):
        """Test successful upgrade from v1 to v2."""
        # Mock v1 connection
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN

        # Mock writer
        connection.writer = MockStreamWriter()

        # Prepare v2 handshake response
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01

        response = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        # Mock reader to return upgrade response
        connection.reader = MockStreamReader(response)

        # Attempt upgrade
        result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is True
        assert len(connection.writer.data) > 0  # Sent upgrade request

    async def test_upgrade_failure_no_writer(self):
        """Test upgrade failure when connection has no writer."""
        connection = MagicMock()
        connection.writer = None

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_failure_timeout(self):
        """Test upgrade failure due to timeout."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = MockStreamWriter()

        # Mock reader that times out
        async def slow_read(n):
            await asyncio.sleep(1)
            raise asyncio.TimeoutError()

        connection.reader = MagicMock()
        connection.reader.readexactly = slow_read

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_failure_hash_mismatch(self):
        """Test upgrade failure when peer returns wrong hash."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = MockStreamWriter()

        # Prepare response with wrong hash
        wrong_hash = b"w" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01

        response = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + wrong_hash
            + peer_id
        )

        connection.reader = MockStreamReader(response)

        # Attempt upgrade with different hash
        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_with_no_peer_id(self):
        """Test upgrade when connection has no peer_id."""
        connection = MagicMock()
        connection.our_peer_id = None  # No peer ID
        connection.writer = MockStreamWriter()

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01

        response = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        connection.reader = MockStreamReader(response)

        # Should use default peer ID
        result = await upgrade_to_v2(connection, info_hash_v2)

        # Verify a handshake was sent (with default peer ID)
        assert len(connection.writer.data) == HANDSHAKE_V2_SIZE

    async def test_upgrade_peer_response_validation(self):
        """Test validation of peer response during upgrade."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = MockStreamWriter()

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01

        # Valid response
        response = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        connection.reader = MockStreamReader(response)

        result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is True

        # Verify handshake was parsed correctly
        parsed = parse_v2_handshake(response)
        assert parsed["version"] == ProtocolVersion.V2
        assert parsed["info_hash_v2"] == info_hash_v2

    async def test_multiple_concurrent_upgrades(self):
        """Test multiple connections upgrading concurrently."""
        async def upgrade_connection(conn_id: int, info_hash: bytes):
            """Upgrade a single connection."""
            connection = MagicMock()
            connection.our_peer_id = (b"p" + str(conn_id).encode() + b"x" * 18)[:20]
            connection.writer = MockStreamWriter()

            # Prepare response
            peer_id = (b"q" + str(conn_id).encode() + b"x" * 18)[:20]
            reserved = bytearray(RESERVED_BYTES_LEN)
            reserved[0] |= 0x01

            response = (
                struct.pack("B", PROTOCOL_STRING_LEN)
                + PROTOCOL_STRING
                + bytes(reserved)
                + info_hash
                + peer_id
            )

            connection.reader = MockStreamReader(response)

            return await upgrade_to_v2(connection, info_hash)

        info_hash_v2 = b"i" * INFO_HASH_V2_LEN

        # Upgrade 5 connections concurrently
        tasks = [upgrade_connection(i, info_hash_v2) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)
        assert len(results) == 5

