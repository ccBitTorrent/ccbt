"""Unit tests for UTPPacket."""

import pytest

from ccbt.transport.utp import UTPPacket, UTPPacketType
from ccbt.transport.utp_extensions import (
    ECNExtension,
    SACKExtension,
    SACKBlock,
    WindowScalingExtension,
)


class TestUTPPacket:
    """Tests for UTPPacket."""

    def test_packet_creation(self):
        """Test creating a basic packet."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=50,
            wnd_size=65535,
            timestamp=1000000,
            timestamp_diff=500000,
            data=b"test data",
        )

        assert packet.type == UTPPacketType.ST_DATA
        assert packet.connection_id == 12345
        assert packet.seq_nr == 100
        assert packet.ack_nr == 50
        assert packet.wnd_size == 65535
        assert packet.timestamp == 1000000
        assert packet.timestamp_diff == 500000
        assert packet.data == b"test data"

    def test_packet_pack(self):
        """Test packing a packet."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=50,
            wnd_size=65535,
            timestamp=1000000,
            timestamp_diff=500000,
            data=b"test",
        )

        packed = packet.pack()
        assert len(packed) == UTPPacket.HEADER_SIZE + len(b"test")

    def test_packet_unpack(self):
        """Test unpacking a packet."""
        original = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=50,
            wnd_size=65535,
            timestamp=1000000,
            timestamp_diff=500000,
            data=b"test data",
        )

        packed = original.pack()
        unpacked = UTPPacket.unpack(packed)

        assert unpacked.type == original.type
        assert unpacked.connection_id == original.connection_id
        assert unpacked.seq_nr == original.seq_nr
        assert unpacked.ack_nr == original.ack_nr
        assert unpacked.wnd_size == original.wnd_size
        assert unpacked.timestamp == original.timestamp
        assert unpacked.timestamp_diff == original.timestamp_diff
        assert unpacked.data == original.data

    def test_packet_unpack_too_small(self):
        """Test unpacking packet that's too small."""
        with pytest.raises(ValueError, match="too small"):
            UTPPacket.unpack(b"short")

    def test_packet_with_extensions(self):
        """Test packet with extensions."""
        extensions = [
            WindowScalingExtension(scale_factor=2),
            SACKExtension(blocks=[SACKBlock(start_seq=100, end_seq=105)]),
        ]

        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=1,
            ack_nr=1,
            wnd_size=65535,
            extensions=extensions,
        )

        assert len(packet.extensions) == 2
        packed = packet.pack()

        # Unpack and verify extensions
        unpacked = UTPPacket.unpack(packed)
        assert len(unpacked.extensions) == 2
        assert isinstance(unpacked.extensions[0], WindowScalingExtension)
        assert isinstance(unpacked.extensions[1], SACKExtension)

    def test_packet_with_ecn_extension(self):
        """Test packet with ECN extension."""
        extensions = [ECNExtension(ecn_echo=True, ecn_cwr=False)]
        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=1,
            ack_nr=1,
            wnd_size=65535,
            extensions=extensions,
        )

        packed = packet.pack()
        unpacked = UTPPacket.unpack(packed)

        assert len(unpacked.extensions) == 1
        assert isinstance(unpacked.extensions[0], ECNExtension)
        assert unpacked.extensions[0].ecn_echo is True
        assert unpacked.extensions[0].ecn_cwr is False

    def test_packet_pack_invalid_type(self):
        """Test packing packet with invalid type."""
        packet = UTPPacket(
            type=10,  # Invalid type
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
        )

        with pytest.raises(ValueError, match="Invalid packet type"):
            packet.pack()

    def test_packet_pack_invalid_connection_id(self):
        """Test packing packet with invalid connection_id."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x10000,  # Too large
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
        )

        with pytest.raises(ValueError, match="Invalid connection_id"):
            packet.pack()

    def test_packet_pack_invalid_seq_nr(self):
        """Test packing packet with invalid seq_nr."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0x10000,  # Too large
            ack_nr=0,
            wnd_size=0,
        )

        with pytest.raises(ValueError, match="Invalid seq_nr"):
            packet.pack()

    def test_packet_default_values(self):
        """Test packet with default values."""
        packet = UTPPacket(type=UTPPacketType.ST_DATA, connection_id=12345)

        assert packet.ver == 1
        assert packet.extension == 0
        assert packet.seq_nr == 0
        assert packet.ack_nr == 0
        assert packet.wnd_size == 0
        assert packet.timestamp == 0
        assert packet.timestamp_diff == 0
        assert packet.data == b""
        assert packet.extensions == []

    def test_packet_roundtrip_with_extensions(self):
        """Test roundtrip pack/unpack with extensions."""
        original = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=54321,
            seq_nr=200,
            ack_nr=150,
            wnd_size=32768,
            timestamp=2000000,
            timestamp_diff=1000000,
            data=b"payload",
            extensions=[
                WindowScalingExtension(scale_factor=3),
                SACKExtension(blocks=[SACKBlock(start_seq=110, end_seq=120)]),
                ECNExtension(ecn_echo=False, ecn_cwr=True),
            ],
        )

        packed = original.pack()
        unpacked = UTPPacket.unpack(packed)

        assert unpacked.type == original.type
        assert unpacked.connection_id == original.connection_id
        assert unpacked.seq_nr == original.seq_nr
        assert unpacked.ack_nr == original.ack_nr
        assert unpacked.wnd_size == original.wnd_size
        assert unpacked.timestamp == original.timestamp
        assert unpacked.timestamp_diff == original.timestamp_diff
        assert unpacked.data == original.data
        assert len(unpacked.extensions) == 3

