"""Tests for peer protocol implementation.
"""

import struct

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.peer import (
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    HandshakeError,
    HaveMessage,
    InterestedMessage,
    KeepAliveMessage,
    MessageDecoder,
    MessageError,
    MessageType,
    NotInterestedMessage,
    PeerInfo,
    PeerState,
    PieceMessage,
    RequestMessage,
    UnchokeMessage,
    create_message,
)


class TestHandshake:
    """Test cases for Handshake."""

    def test_handshake_creation(self):
        """Test creating a handshake."""
        info_hash = b"x" * 20
        peer_id = b"y" * 20

        handshake = Handshake(info_hash, peer_id)

        assert handshake.info_hash == info_hash
        assert handshake.peer_id == peer_id

    def test_handshake_invalid_info_hash(self):
        """Test handshake with invalid info hash length."""
        with pytest.raises(HandshakeError, match="Info hash must be 20 bytes"):
            Handshake(b"short", b"x" * 20)

        with pytest.raises(HandshakeError, match="Info hash must be 20 bytes"):
            Handshake(b"x" * 21, b"x" * 20)

    def test_handshake_invalid_peer_id(self):
        """Test handshake with invalid peer ID length."""
        with pytest.raises(HandshakeError, match="Peer ID must be 20 bytes"):
            Handshake(b"x" * 20, b"short")

        with pytest.raises(HandshakeError, match="Peer ID must be 20 bytes"):
            Handshake(b"x" * 20, b"x" * 21)

    def test_handshake_encode(self):
        """Test encoding handshake to bytes."""
        info_hash = b"info_hash_20_bytes__"
        peer_id = b"peer_id_20_bytes____"

        handshake = Handshake(info_hash, peer_id)
        encoded = handshake.encode()

        assert len(encoded) == 68

        # Check protocol length
        protocol_len = struct.unpack("B", encoded[0:1])[0]
        assert protocol_len == 19

        # Check protocol string
        protocol = encoded[1:20]
        assert protocol == b"BitTorrent protocol"

        # Check reserved bytes
        reserved = encoded[20:28]
        assert reserved == b"\x00" * 8

        # Check info hash
        decoded_info_hash = encoded[28:48]
        assert decoded_info_hash == info_hash

        # Check peer ID
        decoded_peer_id = encoded[48:68]
        assert decoded_peer_id == peer_id

    def test_handshake_decode(self):
        """Test decoding handshake from bytes."""
        info_hash = b"info_hash_20_bytes__"
        peer_id = b"peer_id_20_bytes____"

        handshake = Handshake(info_hash, peer_id)
        encoded = handshake.encode()

        decoded = Handshake.decode(encoded)

        assert decoded.info_hash == info_hash
        assert decoded.peer_id == peer_id

    def test_handshake_decode_invalid_length(self):
        """Test decoding handshake with invalid length."""
        with pytest.raises(HandshakeError, match="Handshake must be 68 bytes"):
            Handshake.decode(b"x" * 67)  # Too short

        with pytest.raises(HandshakeError, match="Handshake must be 68 bytes"):
            Handshake.decode(b"x" * 69)  # Too long

    def test_handshake_decode_invalid_protocol_length(self):
        """Test decoding handshake with invalid protocol length."""
        # Create handshake with wrong protocol length
        info_hash = b"info_hash_20_bytes__"
        peer_id = b"peer_id_20_bytes____"

        # Manually create invalid handshake data (67 bytes, should be 68)
        protocol_len = 18  # Should be 19
        encoded = (
            struct.pack("B", protocol_len)
            + b"BitTorrent protoco"  # 18 bytes instead of 19
            + b"\x00" * 8
            + info_hash
            + peer_id
        )
        # Pad to 68 bytes to pass length check
        encoded = encoded.ljust(68, b"\x00")

        with pytest.raises(HandshakeError, match="Invalid protocol length"):
            Handshake.decode(encoded)

    def test_handshake_decode_invalid_protocol_string(self):
        """Test decoding handshake with invalid protocol string."""
        info_hash = b"info_hash_20_bytes__"
        peer_id = b"peer_id_20_bytes____"

        # Create handshake with wrong protocol string
        encoded = (
            b"\x13"  # 19
            b"Wrong protocol name" + b"\x00" * 8 + info_hash + peer_id
        )

        with pytest.raises(HandshakeError, match="Invalid protocol string"):
            Handshake.decode(encoded)

    def test_handshake_from_parts(self):
        """Test creating handshake from individual components."""
        protocol_len = 19
        protocol = b"BitTorrent protocol"
        reserved = b"\x00" * 8
        info_hash = b"info_hash_20_bytes__"
        peer_id = b"peer_id_20_bytes____"

        handshake = Handshake.from_parts(
            protocol_len,
            protocol,
            reserved,
            info_hash,
            peer_id,
        )

        assert handshake.info_hash == info_hash
        assert handshake.peer_id == peer_id

        # Test encoding produces same result as direct creation
        direct_handshake = Handshake(info_hash, peer_id)
        assert handshake.encode() == direct_handshake.encode()

    def test_handshake_from_parts_invalid_protocol_length(self):
        """Test creating handshake with mismatched protocol length."""
        with pytest.raises(HandshakeError, match="Protocol length mismatch"):
            Handshake.from_parts(
                19,
                b"Wrong length protocol",
                b"\x00" * 8,
                b"x" * 20,
                b"y" * 20,
            )

    def test_handshake_from_parts_invalid_reserved_length(self):
        """Test creating handshake with invalid reserved bytes length."""
        with pytest.raises(HandshakeError, match="Reserved must be 8 bytes"):
            Handshake.from_parts(
                19,
                b"BitTorrent protocol",
                b"\x00" * 7,
                b"x" * 20,
                b"y" * 20,
            )


class TestKeepAliveMessage:
    """Test cases for KeepAliveMessage."""

    def test_encode(self):
        """Test encoding keep-alive message."""
        message = KeepAliveMessage()
        encoded = message.encode()

        assert len(encoded) == 4
        assert encoded == struct.pack("!I", 0)

    def test_decode(self):
        """Test decoding keep-alive message."""
        encoded = struct.pack("!I", 0)
        message = KeepAliveMessage.decode(encoded)

        assert isinstance(message, KeepAliveMessage)

    def test_decode_invalid_length(self):
        """Test decoding keep-alive with invalid length."""
        encoded = struct.pack("!I", 1)  # Length should be 0

        with pytest.raises(MessageError, match="Keep-alive length must be 0"):
            KeepAliveMessage.decode(encoded)

    def test_decode_short_data(self):
        """Test decoding keep-alive with insufficient data."""
        with pytest.raises(MessageError, match="Keep-alive must be 4 bytes"):
            KeepAliveMessage.decode(b"x" * 3)  # Only 3 bytes


class TestChokeMessage:
    """Test cases for ChokeMessage."""

    def test_encode(self):
        """Test encoding choke message."""
        message = ChokeMessage()
        encoded = message.encode()

        assert len(encoded) == 5
        length, message_id = struct.unpack("!IB", encoded)
        assert length == 1
        assert message_id == MessageType.CHOKE

    def test_decode(self):
        """Test decoding choke message."""
        encoded = struct.pack("!IB", 1, MessageType.CHOKE)
        message = ChokeMessage.decode(encoded)

        assert isinstance(message, ChokeMessage)

    def test_decode_invalid_length(self):
        """Test decoding choke with invalid length."""
        with pytest.raises(MessageError, match="Choke message length must be 1"):
            ChokeMessage.decode(struct.pack("!IB", 2, MessageType.CHOKE))

    def test_decode_wrong_message_id(self):
        """Test decoding choke with wrong message ID."""
        with pytest.raises(MessageError, match="Expected choke message ID"):
            ChokeMessage.decode(struct.pack("!IB", 1, MessageType.UNCHOKE))


class TestUnchokeMessage:
    """Test cases for UnchokeMessage."""

    def test_encode(self):
        """Test encoding unchoke message."""
        message = UnchokeMessage()
        encoded = message.encode()

        assert len(encoded) == 5
        length, message_id = struct.unpack("!IB", encoded)
        assert length == 1
        assert message_id == MessageType.UNCHOKE

    def test_decode(self):
        """Test decoding unchoke message."""
        encoded = struct.pack("!IB", 1, MessageType.UNCHOKE)
        message = UnchokeMessage.decode(encoded)

        assert isinstance(message, UnchokeMessage)


class TestInterestedMessage:
    """Test cases for InterestedMessage."""

    def test_encode(self):
        """Test encoding interested message."""
        message = InterestedMessage()
        encoded = message.encode()

        assert len(encoded) == 5
        length, message_id = struct.unpack("!IB", encoded)
        assert length == 1
        assert message_id == MessageType.INTERESTED

    def test_decode(self):
        """Test decoding interested message."""
        encoded = struct.pack("!IB", 1, MessageType.INTERESTED)
        message = InterestedMessage.decode(encoded)

        assert isinstance(message, InterestedMessage)


class TestNotInterestedMessage:
    """Test cases for NotInterestedMessage."""

    def test_encode(self):
        """Test encoding not interested message."""
        message = NotInterestedMessage()
        encoded = message.encode()

        assert len(encoded) == 5
        length, message_id = struct.unpack("!IB", encoded)
        assert length == 1
        assert message_id == MessageType.NOT_INTERESTED

    def test_decode(self):
        """Test decoding not interested message."""
        encoded = struct.pack("!IB", 1, MessageType.NOT_INTERESTED)
        message = NotInterestedMessage.decode(encoded)

        assert isinstance(message, NotInterestedMessage)


class TestHaveMessage:
    """Test cases for HaveMessage."""

    def test_encode(self):
        """Test encoding have message."""
        message = HaveMessage(42)
        encoded = message.encode()

        assert len(encoded) == 9
        length, message_id, piece_index = struct.unpack("!IBI", encoded)
        assert length == 5
        assert message_id == MessageType.HAVE
        assert piece_index == 42

    def test_decode(self):
        """Test decoding have message."""
        encoded = struct.pack("!IBI", 5, MessageType.HAVE, 123)
        message = HaveMessage.decode(encoded)

        assert isinstance(message, HaveMessage)
        assert message.piece_index == 123

    def test_decode_invalid_length(self):
        """Test decoding have with invalid length."""
        with pytest.raises(MessageError, match="Have message length must be 5"):
            HaveMessage.decode(struct.pack("!IBI", 6, MessageType.HAVE, 123))


class TestBitfieldMessage:
    """Test cases for BitfieldMessage."""

    def test_encode(self):
        """Test encoding bitfield message."""
        bitfield = b"\xff\x00\x80"  # 24 bits: 11111111 00000000 10000000
        message = BitfieldMessage(bitfield)
        encoded = message.encode()

        # Length should be 1 (ID) + 3 (bitfield) = 4
        length, message_id = struct.unpack("!IB", encoded[:5])
        assert length == 4
        assert message_id == MessageType.BITFIELD

        # Check bitfield data
        decoded_bitfield = encoded[5:]
        assert decoded_bitfield == bitfield

    def test_decode(self):
        """Test decoding bitfield message."""
        bitfield = b"\xff\x00\x80"
        encoded = (
            struct.pack("!I", 4)  # length = 4 (1 ID + 3 bitfield)
            + struct.pack("B", MessageType.BITFIELD)
            + bitfield
        )

        message = BitfieldMessage.decode(encoded)

        assert isinstance(message, BitfieldMessage)
        assert message.bitfield == bitfield

    def test_has_piece(self):
        """Test checking if peer has specific pieces."""
        # Bitfield: 10110001 01100010 (first byte: 10110001, second: 01100010)
        bitfield = bytes([0b10110001, 0b01100010])
        message = BitfieldMessage(bitfield)

        # Test piece indices 0-15
        # Byte 0: 10110001 -> pieces 0,2,3,7 (from high to low bit)
        # Byte 1: 01100010 -> pieces 9,10,14 (from high to low bit)

        assert message.has_piece(0, 16)  # Bit 7 of byte 0
        assert not message.has_piece(1, 16)  # Bit 6 of byte 0
        assert message.has_piece(2, 16)  # Bit 5 of byte 0
        assert message.has_piece(3, 16)  # Bit 4 of byte 0
        assert not message.has_piece(4, 16)  # Bit 3 of byte 0
        assert not message.has_piece(5, 16)  # Bit 2 of byte 0
        assert not message.has_piece(6, 16)  # Bit 1 of byte 0
        assert message.has_piece(7, 16)  # Bit 0 of byte 0

        assert not message.has_piece(8, 16)  # Bit 7 of byte 1
        assert message.has_piece(9, 16)  # Bit 6 of byte 1
        assert message.has_piece(10, 16)  # Bit 5 of byte 1
        assert not message.has_piece(11, 16)  # Bit 4 of byte 1
        assert not message.has_piece(12, 16)  # Bit 3 of byte 1
        assert not message.has_piece(13, 16)  # Bit 2 of byte 1
        assert message.has_piece(14, 16)  # Bit 1 of byte 1
        assert not message.has_piece(15, 16)  # Bit 0 of byte 1

        # Test out of range
        assert not message.has_piece(-1, 16)
        assert not message.has_piece(16, 16)
        assert not message.has_piece(100, 16)

    def test_decode_invalid_length(self):
        """Test decoding bitfield with invalid length."""
        with pytest.raises(MessageError, match="Bitfield message length mismatch"):
            # Length says 4 but data is shorter
            BitfieldMessage.decode(struct.pack("!IB", 4, MessageType.BITFIELD) + b"x")


class TestRequestMessage:
    """Test cases for RequestMessage."""

    def test_encode(self):
        """Test encoding request message."""
        message = RequestMessage(5, 1000, 16384)
        encoded = message.encode()

        assert len(encoded) == 17
        length, message_id, piece_index, begin, req_length = struct.unpack(
            "!IBIII",
            encoded,
        )
        assert length == 13
        assert message_id == MessageType.REQUEST
        assert piece_index == 5
        assert begin == 1000
        assert req_length == 16384

    def test_decode(self):
        """Test decoding request message."""
        encoded = struct.pack("!IBIII", 13, MessageType.REQUEST, 10, 2000, 8192)
        message = RequestMessage.decode(encoded)

        assert isinstance(message, RequestMessage)
        assert message.piece_index == 10
        assert message.begin == 2000
        assert message.length == 8192


class TestPieceMessage:
    """Test cases for PieceMessage."""

    def test_encode(self):
        """Test encoding piece message."""
        block = b"x" * 1000
        message = PieceMessage(5, 1000, block)
        encoded = message.encode()

        # Length should be 1 (ID) + 4 (index) + 4 (begin) + 1000 (block) = 1009
        length, message_id = struct.unpack("!IB", encoded[:5])
        assert length == 1009
        assert message_id == MessageType.PIECE

        # Check payload
        piece_index, begin = struct.unpack("!II", encoded[5:13])
        decoded_block = encoded[13:]

        assert piece_index == 5
        assert begin == 1000
        assert decoded_block == block

    def test_decode(self):
        """Test decoding piece message."""
        block = b"piece data here"
        encoded = (
            struct.pack("!I", 9 + len(block))  # length = 9 + 15 = 24
            + struct.pack("B", MessageType.PIECE)
            + struct.pack("!II", 7, 1500)
            + block
        )

        message = PieceMessage.decode(encoded)

        assert isinstance(message, PieceMessage)
        assert message.piece_index == 7
        assert message.begin == 1500
        assert message.block == block


class TestCancelMessage:
    """Test cases for CancelMessage."""

    def test_encode(self):
        """Test encoding cancel message."""
        message = CancelMessage(5, 1000, 16384)
        encoded = message.encode()

        assert len(encoded) == 17
        length, message_id, piece_index, begin, req_length = struct.unpack(
            "!IBIII",
            encoded,
        )
        assert length == 13
        assert message_id == MessageType.CANCEL
        assert piece_index == 5
        assert begin == 1000
        assert req_length == 16384

    def test_decode(self):
        """Test decoding cancel message."""
        encoded = struct.pack("!IBIII", 13, MessageType.CANCEL, 10, 2000, 8192)
        message = CancelMessage.decode(encoded)

        assert isinstance(message, CancelMessage)
        assert message.piece_index == 10
        assert message.begin == 2000
        assert message.length == 8192


class TestMessageDecoder:
    """Test cases for MessageDecoder."""

    async def test_decode_keepalive(self):
        """Test decoding keep-alive message."""
        decoder = MessageDecoder()
        await decoder.feed_data(struct.pack("!I", 0))
        message = await decoder.get_message()

        assert message is not None
        assert isinstance(message, KeepAliveMessage)

    async def test_decode_choke(self):
        """Test decoding choke message."""
        decoder = MessageDecoder()
        await decoder.feed_data(struct.pack("!IB", 1, MessageType.CHOKE))
        message = await decoder.get_message()

        assert message is not None
        assert isinstance(message, ChokeMessage)

    async def test_decode_have(self):
        """Test decoding have message."""
        decoder = MessageDecoder()
        # Full message: length(5) + id(4) + piece_index(42)
        await decoder.feed_data(memoryview(struct.pack("!IBI", 5, MessageType.HAVE, 42)))
        message = await decoder.get_message()

        assert message is not None
        assert isinstance(message, HaveMessage)
        assert message.piece_index == 42

    async def test_decode_bitfield(self):
        """Test decoding bitfield message."""
        decoder = MessageDecoder()
        bitfield = b"\xff\x00"
        # Full message: length(3) + id(5) + bitfield
        encoded = (
            struct.pack("!I", 3)  # length = 3 (1 ID + 2 bitfield)
            + struct.pack("B", MessageType.BITFIELD)
            + bitfield
        )
        await decoder.feed_data(memoryview(encoded))
        message = await decoder.get_message()

        assert message is not None
        assert isinstance(message, BitfieldMessage)
        assert message.bitfield == bitfield

    async def test_decode_partial_data(self):
        """Test decoding with partial data."""
        decoder = MessageDecoder()

        # Add partial message (only length)
        await decoder.feed_data(struct.pack("!I", 5))
        message = await decoder.get_message()
        assert message is None  # Should be None since message is incomplete

        # Add rest of message (message ID and payload, length field already in buffer)
        await decoder.feed_data(memoryview(struct.pack("BI", MessageType.HAVE, 42)))
        message = await decoder.get_message()
        assert message is not None
        assert isinstance(message, HaveMessage)
        assert message.piece_index == 42

    async def test_decode_multiple_messages(self):
        """Test decoding multiple messages in one data chunk."""
        decoder = MessageDecoder()

        # Create multiple messages (each with full length field)
        messages_data = (
            struct.pack("!IB", 1, MessageType.CHOKE)
            + struct.pack("!IB", 1, MessageType.UNCHOKE)
            + struct.pack("!IBI", 5, MessageType.HAVE, 10)
        )

        await decoder.feed_data(memoryview(messages_data))

        # Get all messages
        messages = []
        while True:
            message = await decoder.get_message()
            if message is None:
                break
            messages.append(message)

        assert len(messages) == 3
        assert isinstance(messages[0], ChokeMessage)
        assert isinstance(messages[1], UnchokeMessage)
        assert isinstance(messages[2], HaveMessage)
        assert messages[2].piece_index == 10

    async def test_decode_piece_message(self):
        """Test decoding piece message."""
        decoder = MessageDecoder()

        block = b"x" * 100
        # Full message: length(109) + id(7) + piece_index(5) + begin(1000) + block(100)
        # Total: 4 + 1 + 4 + 4 + 100 = 113 bytes
        encoded = (
            struct.pack("!I", 9 + len(block))  # length = 9 + 100 = 109
            + struct.pack("B", MessageType.PIECE)
            + struct.pack("!II", 5, 1000)
            + block
        )

        await decoder.feed_data(memoryview(encoded))
        message = await decoder.get_message()

        assert message is not None
        assert isinstance(message, PieceMessage)
        assert message.piece_index == 5
        assert message.begin == 1000
        assert message.block == block


class TestCreateMessage:
    """Test cases for create_message factory function."""

    def test_create_choke(self):
        """Test creating choke message."""
        message = create_message(MessageType.CHOKE)
        assert isinstance(message, ChokeMessage)

    def test_create_have(self):
        """Test creating have message."""
        message = create_message(MessageType.HAVE, piece_index=42)
        assert isinstance(message, HaveMessage)
        assert message.piece_index == 42

    def test_create_bitfield(self):
        """Test creating bitfield message."""
        bitfield = b"\xff\x00"
        message = create_message(MessageType.BITFIELD, bitfield=bitfield)
        assert isinstance(message, BitfieldMessage)
        assert message.bitfield == bitfield

    def test_create_request(self):
        """Test creating request message."""
        message = create_message(
            MessageType.REQUEST,
            piece_index=5,
            begin=1000,
            length=16384,
        )
        assert isinstance(message, RequestMessage)
        assert message.piece_index == 5
        assert message.begin == 1000
        assert message.length == 16384

    def test_create_unknown_type(self):
        """Test creating message with unknown type."""
        with pytest.raises(MessageError, match="Unknown message type"):
            create_message(999)


class TestPeerState:
    """Test cases for PeerState."""

    def test_initial_state(self):
        """Test initial peer state."""
        state = PeerState()

        assert state.am_choking
        assert not state.am_interested
        assert state.peer_choking
        assert not state.peer_interested
        assert state.bitfield is None
        assert state.pieces_we_have == set()

    def test_string_representation(self):
        """Test string representation of peer state."""
        state = PeerState()
        state.am_interested = True
        state.peer_choking = False

        state_str = str(state)
        assert "choking=True" in state_str
        assert "interested=True" in state_str
        assert "peer_choking=False" in state_str


class TestPeerInfo:
    """Test cases for PeerInfo."""

    def test_creation(self):
        """Test creating peer info."""
        peer = PeerInfo(ip="192.168.1.100", port=6881)

        assert peer.ip == "192.168.1.100"
        assert peer.port == 6881
        assert peer.peer_id is None

    def test_creation_with_peer_id(self):
        """Test creating peer info with peer ID."""
        peer_id = b"peer_id_20_bytes____"
        peer = PeerInfo(ip="192.168.1.100", port=6881, peer_id=peer_id)

        assert peer.peer_id == peer_id

    def test_string_representation(self):
        """Test string representation of peer info."""
        peer = PeerInfo(ip="192.168.1.100", port=6881)
        assert str(peer) == "192.168.1.100:6881"
