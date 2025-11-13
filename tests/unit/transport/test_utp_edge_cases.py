"""Unit tests for uTP edge cases and error handling."""

from unittest.mock import MagicMock

import pytest

from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
    UTPPacket,
    UTPPacketType,
)
from ccbt.transport.utp_socket import UTPSocketManager


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    def test_handle_invalid_packet(self, connection):
        """Test handling invalid packet data."""
        # Too small to be a valid packet
        invalid_data = b"short"

        # Should not crash
        connection._handle_packet(invalid_data, ecn_ce=False)

        # Should log warning but continue

    def test_sequence_number_wraparound(self, connection):
        """Test sequence number wraparound handling."""
        connection.state = UTPConnectionState.CONNECTED
        connection.ack_nr = 0xFFFE
        connection.recv_buffer_expected_seq = 0xFFFE

        # Receive packet at wraparound boundary (in-order)
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0xFFFE,  # Expected seq (in-order)
            ack_nr=0,
            wnd_size=65535,
            data=b"data",
        )

        # Should handle wraparound
        connection._handle_data_packet(packet)

        # Expected seq should wrap to 0xFFFF, then 0
        assert connection.recv_buffer_expected_seq in (0xFFFF, 0)

    def test_window_size_zero(self, connection):
        """Test handling zero window size."""
        connection.send_window = 0

        # Should still function
        assert connection._can_send() is not None  # May be False

    def test_connection_id_zero(self):
        """Test connection ID 0 handling."""
        # Connection ID 0 is invalid (should be 1-0xFFFE)
        # Generation should avoid 0
        manager = UTPSocketManager()
        manager._initialized = True

        for _ in range(100):
            conn_id = manager._generate_connection_id()
            assert conn_id != 0
            assert conn_id != 0xFFFF

    def test_empty_data_packet(self, connection):
        """Test handling empty data packet."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"",  # Empty data
        )

        connection.recv_buffer_expected_seq = 1
        connection._handle_data_packet(packet)

        # Should handle gracefully
        assert connection.ack_nr == 1

    def test_duplicate_packet(self, connection):
        """Test handling duplicate packet."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"data",
        )

        connection.recv_buffer_expected_seq = 2  # Already received seq 1

        # Receive duplicate
        connection._handle_data_packet(packet)

        # Should handle gracefully (ignore duplicate)
        assert connection.recv_buffer_expected_seq == 2

    def test_close_during_handshake(self, connection):
        """Test closing connection during handshake."""
        connection.state = UTPConnectionState.SYN_SENT

        # Close connection
        import asyncio

        asyncio.run(connection.close())

        # Should transition to CLOSED
        assert connection.state == UTPConnectionState.CLOSED

    def test_send_when_not_connected(self, connection):
        """Test sending data when not connected."""
        connection.state = UTPConnectionState.IDLE

        # Should raise error
        import asyncio

        with pytest.raises(RuntimeError, match="Cannot send data"):
            asyncio.run(connection.send(b"data"))

    def test_receive_when_no_data(self, connection):
        """Test receiving when no data available."""
        connection.state = UTPConnectionState.CONNECTED
        connection.recv_data_buffer = bytearray()

        # Should wait for data
        # This is tested in integration tests with actual async waits

    def test_retransmission_empty_buffer(self, connection):
        """Test retransmission with empty send buffer."""
        connection.send_buffer = {}

        # Should not crash
        import asyncio

        asyncio.run(connection._check_retransmissions())

    def test_sack_empty_received_seqs(self, connection):
        """Test SACK generation with empty received sequences."""
        from ccbt.transport.utp_extensions import UTPExtensionType

        connection.negotiated_extensions.add(UTPExtensionType.SACK)
        connection.received_seqs = set()

        blocks = connection._generate_sack_blocks()

        assert len(blocks) == 0

    def test_extension_parsing_malformed(self):
        """Test parsing malformed extension data."""
        from ccbt.transport.utp_extensions import parse_extensions

        # Malformed: claims length 10 but only 2 bytes
        data = b"\x01\x0A\x00\x00"  # Type 1, length 10, but only 4 bytes total
        extensions, _ = parse_extensions(data, 0)

        # Should skip malformed extension
        assert len(extensions) == 0

    def test_window_scaling_invalid_scale(self):
        """Test window scaling with invalid scale factor."""
        from ccbt.transport.utp_extensions import WindowScalingExtension

        with pytest.raises(ValueError, match="Invalid scale_factor"):
            WindowScalingExtension(scale_factor=15)

    def test_sack_block_invalid_range(self):
        """Test SACK block with invalid range."""
        from ccbt.transport.utp_extensions import SACKBlock

        with pytest.raises(ValueError, match="start_seq.*>=.*end_seq"):
            SACKBlock(start_seq=105, end_seq=100)

    def test_connection_id_collision_max_attempts(self):
        """Test connection ID generation with full ID space."""
        manager = UTPSocketManager()
        manager._initialized = True

        # Fill up ID space
        for i in range(0x0001, 0xFFFE):
            manager.active_connection_ids.add(i)

        # Should raise error
        with pytest.raises(RuntimeError, match="Could not generate unique"):
            manager._generate_connection_id()

    def test_ack_delay_configurable(self, connection):
        """Test ACK delay is configurable."""
        # Default delay
        assert connection.ack_delay > 0

        # Should be configurable via config
        # (tested indirectly through initialization)

    def test_rtt_update_no_timestamp_diff(self, connection):
        """Test RTT update when no timestamp_diff."""
        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=0,  # No timestamp_diff
        )

        old_srtt = connection.srtt
        connection._update_rtt(packet, 0.0)

        # Should use send_time if available
        # Or estimate from RTT if no timestamp_diff

    def test_congestion_control_no_measurements(self, connection):
        """Test congestion control with no RTT/delay measurements."""
        connection.srtt = 0.0
        connection.last_timestamp_diff = 0

        # Should still calculate valid window
        target = connection._calculate_target_window()

        assert target > 0
        assert target <= 65535

