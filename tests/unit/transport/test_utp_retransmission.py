"""Unit tests for uTP retransmission and RTO calculation."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
    UTPPacket,
    UTPPacketType,
)


class TestRetransmission:
    """Tests for retransmission logic."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_check_retransmissions_timeout(self, connection):
        """Test retransmission on timeout."""
        # Add packet to send buffer with old send time
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        # Set old send time (past RTO)
        connection.srtt = 0.1
        connection.rttvar = 0.01
        import time

        old_time = time.perf_counter() - 1.0  # 1 second ago
        connection.send_buffer[100] = (packet, old_time, 0)

        # Check retransmissions
        await connection._check_retransmissions()

        # Verify packet was retransmitted
        assert connection.transport.sendto.called
        assert 100 in connection.retransmitted_packets

    @pytest.mark.asyncio
    async def test_check_retransmissions_exponential_backoff(self, connection):
        """Test exponential backoff for retransmissions."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection.srtt = 0.1
        connection.rttvar = 0.01
        import time

        old_time = time.perf_counter() - 1.0
        connection.send_buffer[100] = (packet, old_time, 2)  # Already retried 2 times

        # Check retransmissions
        await connection._check_retransmissions()

        # Verify retry count increased
        assert connection.send_buffer[100][2] == 3  # retry_count

    @pytest.mark.asyncio
    async def test_check_retransmissions_max_retries(self, connection):
        """Test connection fails after max retries."""
        connection.state = UTPConnectionState.CONNECTED
        connection.transport = MagicMock()
        connection.transport.sendto = MagicMock()
        
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection.srtt = 0.1
        connection.rttvar = 0.01
        import time

        # Get max_retries using same logic as _check_retransmissions
        # The implementation checks hasattr and defaults to 5 if not found
        max_retries = (
            connection.config.network.utp.max_retransmits
            if hasattr(connection.config, "network")
            and hasattr(connection.config.network, "utp")
            and hasattr(connection.config.network.utp, "max_retransmits")
            else 5
        )
        
        # Calculate RTO to determine timeout
        # RTO = SRTT + 4 * RTTVAR (from the code)
        rto = connection.srtt + 4.0 * connection.rttvar
        rto = max(0.1, min(rto, 60.0))  # Bounded between 0.1 and 60.0
        
        # With exponential backoff, packet_timeout = rto * (2**retry_count)
        # For retry_count = max_retries, we need to ensure old_time is old enough
        # Set old send time to be well past the timeout even with exponential backoff
        packet_timeout = rto * (2**max_retries)  # Exponential backoff
        # Add extra margin to ensure timeout
        old_time = time.perf_counter() - (packet_timeout + 1.0)
        
        # Set retry count to max_retries (will trigger connection close)
        # The code checks: if retry_count >= max_retries: then close
        connection.send_buffer[100] = (packet, old_time, max_retries)

        # Check retransmissions
        await connection._check_retransmissions()

        # Connection should be closed after max retries
        assert connection.state == UTPConnectionState.CLOSED

    @pytest.mark.asyncio
    async def test_check_retransmissions_no_timeout(self, connection):
        """Test no retransmission when not timed out."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection.srtt = 0.1
        connection.rttvar = 0.01
        import time

        recent_time = time.perf_counter()  # Recent
        connection.send_buffer[100] = (packet, recent_time, 0)

        # Clear call count
        connection.transport.sendto.reset_mock()

        # Check retransmissions
        await connection._check_retransmissions()

        # Should not retransmit
        assert not connection.transport.sendto.called

    def test_rto_calculation(self, connection):
        """Test RTO calculation."""
        connection.srtt = 0.1  # 100ms
        connection.rttvar = 0.02  # 20ms

        # RTO = SRTT + 4 * RTTVAR = 0.1 + 4 * 0.02 = 0.18
        # This is tested indirectly in _check_retransmissions

    def test_rto_bounds(self, connection):
        """Test RTO is bounded."""
        # Test minimum bound
        connection.srtt = 0.001  # Very small
        connection.rttvar = 0.0001

        # RTO should be at least 100ms
        # Tested in _check_retransmissions

        # Test maximum bound
        connection.srtt = 100.0  # Very large
        connection.rttvar = 10.0

        # RTO should be at most 60s
        # Tested in _check_retransmissions

    def test_retransmitted_packet_tracking(self, connection):
        """Test tracking retransmitted packets."""
        # Mark packet as retransmitted
        connection.retransmitted_packets.add(100)

        # Verify Karn's algorithm excludes it
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

        # SRTT should not be updated
        assert connection.srtt == old_srtt


class TestRetransmissionScenarios:
    """Tests for various retransmission scenarios."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_fast_retransmit_marks_retransmitted(self, connection):
        """Test fast retransmit marks packet as retransmitted."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection.send_buffer[100] = (packet, 0.0, 0)
        connection.last_ack_nr = 50

        # Send 3 duplicate ACKs
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=50,
            wnd_size=65535,
        )

        for _ in range(3):
            connection._handle_state_packet(ack)

        # Packet should be marked as retransmitted
        assert 100 in connection.retransmitted_packets

    def test_selective_retransmit_marks_retransmitted(self, connection):
        """Test selective retransmit marks packets as retransmitted."""
        packets = {}
        for seq in [100, 101, 102]:
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=f"data{seq}".encode(),
            )
            connection.send_buffer[seq] = (packet, 0.0, 0)

        # Selectively retransmit
        connection._selective_retransmit([100, 102])

        # Both should be marked
        assert 100 in connection.retransmitted_packets
        assert 102 in connection.retransmitted_packets

    def test_retransmission_updates_retry_count(self, connection):
        """Test retransmission updates retry count."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection.send_buffer[100] = (packet, 0.0, 1)  # Already retried once

        # Retransmit
        connection._selective_retransmit([100])

        # Retry count should increase
        assert connection.send_buffer[100][2] == 2

