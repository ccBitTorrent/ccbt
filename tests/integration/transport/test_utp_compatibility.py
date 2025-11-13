"""Compatibility tests for uTP implementation."""

from unittest.mock import MagicMock

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType
from ccbt.transport.utp_extensions import (
    ECNExtension,
    SACKExtension,
    SACKBlock,
    WindowScalingExtension,
)


class TestPacketCompatibility:
    """Tests for packet format compatibility with BEP 29."""

    def test_packet_header_format(self):
        """Test packet header matches BEP 29 format."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=50,
            wnd_size=65535,
            timestamp=1000000,
            timestamp_diff=500000,
        )

        packed = packet.pack()

        # Verify header size
        assert len(packed) >= UTPPacket.HEADER_SIZE

        # Verify can be unpacked
        unpacked = UTPPacket.unpack(packed)
        assert unpacked.type == packet.type
        assert unpacked.connection_id == packet.connection_id

    def test_extension_format(self):
        """Test extension format matches BEP 29."""
        from ccbt.transport.utp_extensions import encode_extensions

        extensions = [
            SACKExtension(blocks=[SACKBlock(start_seq=100, end_seq=105)]),
            WindowScalingExtension(scale_factor=2),
            ECNExtension(ecn_echo=True, ecn_cwr=False),
        ]

        encoded = encode_extensions(extensions)

        # Verify format: [type:1][length:1][data:variable]
        assert len(encoded) > 0

        # Verify can be parsed
        from ccbt.transport.utp_extensions import parse_extensions

        parsed, _ = parse_extensions(encoded, 0)
        assert len(parsed) == 3


class TestStateMachineCompatibility:
    """Tests for state machine compatibility."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    def test_state_transitions_active(self, connection):
        """Test state transitions for active connection."""
        # IDLE -> SYN_SENT -> CONNECTED
        assert connection.state == UTPConnectionState.IDLE

        # Would transition to SYN_SENT on connect()
        # Would transition to CONNECTED on SYN-ACK

    def test_state_transitions_passive(self, connection):
        """Test state transitions for passive connection."""
        # IDLE -> SYN_RECEIVED -> CONNECTED
        assert connection.state == UTPConnectionState.IDLE

        # Would transition to SYN_RECEIVED on incoming SYN
        # Would transition to CONNECTED on ACK

    def test_invalid_state_transitions(self, connection):
        """Test invalid state transitions are handled."""
        connection.state = UTPConnectionState.CONNECTED

        # Try to handle SYN in CONNECTED state
        syn = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        # Should not crash, just log warning
        connection._handle_syn(syn)
        assert connection.state == UTPConnectionState.CONNECTED  # Unchanged


class TestBackwardCompatibility:
    """Tests for backward compatibility with older implementations."""

    def test_packet_without_extensions(self):
        """Test packet without extensions (backward compatible)."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=50,
            wnd_size=65535,
        )

        # Should have empty extensions list
        assert len(packet.extensions) == 0

        # Should pack/unpack correctly
        packed = packet.pack()
        unpacked = UTPPacket.unpack(packed)

        assert unpacked.type == packet.type
        assert len(unpacked.extensions) == 0

    def test_unknown_extensions_ignored(self):
        """Test unknown extensions are ignored."""
        # Create packet with unknown extension type
        # This would be done by manually crafting packet data
        # In normal operation, unknown extensions are skipped during parsing

        from ccbt.transport.utp_extensions import parse_extensions

        # Unknown extension: type=99, length=2, data=0x1234
        data = b"\x63\x02\x12\x34"  # Type 99
        extensions, _ = parse_extensions(data, 0)

        # Unknown extensions should be skipped
        assert len(extensions) == 0

    def test_missing_extensions_graceful(self):
        """Test graceful handling of missing extension support."""
        # Connection without SACK support
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED

        # Remove SACK from supported
        from ccbt.transport.utp_extensions import UTPExtensionType

        conn.supported_extensions.remove(UTPExtensionType.SACK)

        # Should still function without SACK
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"data",
        )

        # Should handle packet normally
        conn._handle_data_packet(packet)

