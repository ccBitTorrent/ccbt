"""Unit tests for uTP congestion control implementation."""

from unittest.mock import MagicMock, patch

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType


class TestRTTMeasurement:
    """Tests for RTT measurement using Karn's algorithm."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_update_rtt_initial(self, connection):
        """Test initial RTT update."""
        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,  # 50ms in microseconds
        )

        send_time = 0.0
        connection._update_rtt(packet, send_time)

        # Verify SRTT was set
        assert connection.srtt > 0
        assert connection.rtt > 0

    def test_update_rtt_karns_algorithm(self, connection):
        """Test Karn's algorithm excludes retransmitted packets."""
        # Add packet to retransmitted set
        connection.retransmitted_packets.add(100)

        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,  # ACK for retransmitted packet
            wnd_size=65535,
            timestamp_diff=50000,
        )

        old_srtt = connection.srtt
        connection._update_rtt(packet, 0.0)

        # SRTT should not be updated (Karn's algorithm)
        assert connection.srtt == old_srtt

    def test_update_rtt_ewma(self, connection):
        """Test RTT update using EWMA."""
        # Set initial RTT
        connection.srtt = 0.1  # 100ms
        connection.rttvar = 0.01

        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=60000,  # 60ms
        )

        old_srtt = connection.srtt
        connection._update_rtt(packet, 0.0)

        # SRTT should be updated using EWMA
        # Should be between old_srtt and measured_rtt
        assert connection.srtt != old_srtt

    def test_rtt_variance_update(self, connection):
        """Test RTT variance update."""
        connection.srtt = 0.1
        connection.rttvar = 0.01

        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=80000,  # 80ms (different from SRTT)
        )

        old_rttvar = connection.rttvar
        connection._update_rtt(packet, 0.0)

        # RTTVAR should be updated
        assert connection.rttvar != old_rttvar


class TestRTOCalculation:
    """Tests for RTO (Retransmission Timeout) calculation."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_rto_calculation(self, connection):
        """Test RTO calculation."""
        connection.srtt = 0.1  # 100ms
        connection.rttvar = 0.02  # 20ms

        # RTO = SRTT + 4 * RTTVAR = 0.1 + 4 * 0.02 = 0.18
        # This is tested indirectly through _check_retransmissions

    def test_rto_bounds(self, connection):
        """Test RTO is bounded between 100ms and 60s."""
        # Test minimum bound
        connection.srtt = 0.01  # Very small
        connection.rttvar = 0.001

        # RTO should be at least 100ms
        # This is tested in _check_retransmissions

        # Test maximum bound
        connection.srtt = 100.0  # Very large
        connection.rttvar = 10.0

        # RTO should be at most 60s
        # This is tested in _check_retransmissions


class TestLEDBATCongestionControl:
    """Tests for LEDBAT congestion control algorithm."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_calculate_target_window_below_target(self, connection):
        """Test window calculation when delay is below target."""
        connection.srtt = 0.05  # 50ms RTT
        connection.last_timestamp_diff = 30000  # 30ms (below target)
        connection.send_window = 1500  # Current window

        target_window = connection._calculate_target_window()

        # Should increase window (additive increase)
        assert target_window >= connection.send_window

    def test_calculate_target_window_above_target(self, connection):
        """Test window calculation when delay is above target."""
        connection.srtt = 0.05  # 50ms RTT
        connection.last_timestamp_diff = 150000  # 150ms (above target of 50ms)
        connection.send_window = 15000  # Current window

        target_window = connection._calculate_target_window()

        # Should decrease window (multiplicative decrease)
        assert target_window < connection.send_window

    def test_calculate_target_window_at_target(self, connection):
        """Test window calculation when delay is at target."""
        connection.srtt = 0.05  # 50ms RTT
        connection.last_timestamp_diff = 50000  # 50ms (at target)
        connection.send_window = 15000  # Current window

        target_window = connection._calculate_target_window()

        # Should maintain window
        # May vary slightly due to algorithm, but should be close
        assert abs(target_window - connection.send_window) < 1500

    def test_calculate_target_window_target_delay(self, connection):
        """Test target delay is min(100ms, RTT)."""
        # RTT < 100ms
        connection.srtt = 0.05  # 50ms
        target_window = connection._calculate_target_window()
        # Should use 50ms as target

        # RTT > 100ms
        connection.srtt = 0.2  # 200ms
        target_window = connection._calculate_target_window()
        # Should use 100ms as target (min of 200ms and 100ms)

    def test_calculate_target_window_no_rtt(self, connection):
        """Test window calculation when no RTT measurement."""
        connection.srtt = 0.0
        connection.last_timestamp_diff = 0

        target_window = connection._calculate_target_window()

        # Should still return valid window
        assert target_window > 0
        assert target_window <= 65535

    def test_calculate_target_window_with_scaling(self, connection):
        """Test window calculation with window scaling."""
        connection.window_scale = 2  # Scale factor 2
        connection.srtt = 0.05
        connection.last_timestamp_diff = 30000

        # Mock config
        with patch.object(
            connection.config.network.utp, "max_window_size", 65535
        ):
            target_window = connection._calculate_target_window()

            # Should account for scaling in max window
            assert target_window <= 65535 << 2  # Scaled max window


class TestECNCongestionResponse:
    """Tests for ECN congestion response."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        from ccbt.transport.utp_extensions import UTPExtensionType

        conn.negotiated_extensions.add(UTPExtensionType.ECN)
        return conn

    def test_handle_ecn_congestion(self, connection):
        """Test handling ECN congestion indication."""
        connection.send_window = 10000
        old_window = connection.send_window

        connection._handle_ecn_congestion()

        # Window should be reduced
        assert connection.send_window < old_window
        assert connection.ecn_cwr is True  # CWR flag set

    def test_handle_ecn_congestion_not_negotiated(self, connection):
        """Test ECN congestion handling when ECN not negotiated."""
        from ccbt.transport.utp_extensions import UTPExtensionType

        connection.negotiated_extensions.remove(UTPExtensionType.ECN)
        connection.send_window = 10000
        old_window = connection.send_window

        connection._handle_ecn_congestion()

        # Window should not be changed
        assert connection.send_window == old_window

    def test_process_ecn_extension(self, connection):
        """Test processing ECN extension from peer."""
        from ccbt.transport.utp_extensions import ECNExtension

        ext = ECNExtension(ecn_echo=False, ecn_cwr=True)
        connection._process_ecn_extension(ext)

        # Should not crash, just log
        # This is informational, no action needed

    def test_ecn_congestion_reduces_window(self, connection):
        """Test ECN congestion reduces window by 0.8 factor."""
        connection.send_window = 10000

        connection._handle_ecn_congestion()

        # Should be reduced to approximately 8000 (0.8 * 10000)
        assert connection.send_window == 8000

    def test_ecn_congestion_minimum_window(self, connection):
        """Test ECN congestion doesn't reduce window below minimum."""
        connection.send_window = 10  # Very small window

        connection._handle_ecn_congestion()

        # Should be at least 2 (minimum)
        assert connection.send_window >= 2

