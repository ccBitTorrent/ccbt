"""Unit tests for uTP delayed ACK implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType


class TestDelayedACK:
    """Tests for delayed ACK functionality."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_should_send_immediate_ack_out_of_order(self, connection):
        """Test immediate ACK for out-of-order packets."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,  # Out of order (expected is 0)
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        assert connection._should_send_immediate_ack(packet) is True

    def test_should_send_immediate_ack_every_second(self, connection):
        """Test immediate ACK every 2nd packet."""
        connection.recv_buffer_expected_seq = 100
        connection.ack_packet_count = 0

        # First packet (in-order)
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data1",
        )
        assert connection._should_send_immediate_ack(packet1) is False

        # Second packet (in-order) - should trigger immediate ACK
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=101,
            ack_nr=0,
            wnd_size=0,
            data=b"data2",
        )
        assert connection._should_send_immediate_ack(packet2) is True

    def test_queue_ack(self, connection):
        """Test queuing ACK packet."""
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )

        connection._queue_ack(ack_packet)

        assert len(connection.pending_acks) == 1
        assert connection.pending_acks[0] == ack_packet

    def test_queue_ack_replaces_old(self, connection):
        """Test queuing ACK replaces old pending ACK."""
        ack1 = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )
        ack2 = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=101,
            wnd_size=65535,
        )

        connection._queue_ack(ack1)
        connection._queue_ack(ack2)

        # Should only have latest ACK
        assert len(connection.pending_acks) == 1
        assert connection.pending_acks[0] == ack2

    def test_send_batched_acks(self, connection):
        """Test sending batched ACKs."""
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )

        connection.pending_acks.append(ack_packet)
        connection._send_batched_acks()

        # Verify ACK was sent
        assert connection.transport.sendto.called
        assert len(connection.pending_acks) == 0
        assert connection.ack_packet_count == 0

    def test_send_batched_acks_empty(self, connection):
        """Test sending batched ACKs when queue is empty."""
        connection.pending_acks = []
        connection._send_batched_acks()

        # Should not crash
        assert not connection.transport.sendto.called

    @pytest.mark.asyncio
    async def test_delayed_ack_loop(self, connection):
        """Test delayed ACK loop."""
        # Set short delay for testing
        connection.ack_delay = 0.01  # 10ms

        # Queue an ACK
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )
        connection.pending_acks.append(ack_packet)

        # Start ACK timer
        task = asyncio.create_task(connection._delayed_ack_loop())

        # Wait a bit longer than delay
        await asyncio.sleep(0.02)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify ACK was sent
        assert connection.transport.sendto.called

    def test_send_ack_immediate(self, connection):
        """Test sending immediate ACK."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection._send_ack(packet=packet, immediate=True)

        # Verify ACK was sent immediately
        assert connection.transport.sendto.called
        assert len(connection.pending_acks) == 0

    def test_send_ack_delayed(self, connection):
        """Test sending delayed ACK."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        connection.recv_buffer_expected_seq = 100  # In-order packet

        connection._send_ack(packet=packet, immediate=False)

        # Verify ACK was queued, not sent immediately
        assert len(connection.pending_acks) == 1
        # Note: sendto might be called for other reasons, so we check pending_acks

    @pytest.mark.asyncio
    async def test_ack_timer_lifecycle(self, connection):
        """Test ACK timer start/stop lifecycle."""
        # Start timer
        connection._start_ack_timer()
        assert connection.ack_timer is not None
        assert not connection.ack_timer.done()

        # Stop timer
        await connection._stop_ack_timer()
        assert connection.ack_timer is None

    @pytest.mark.asyncio
    async def test_ack_timer_stop_with_pending(self, connection):
        """Test stopping ACK timer sends pending ACKs."""
        connection._start_ack_timer()

        # Queue an ACK
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )
        connection.pending_acks.append(ack_packet)

        # Stop timer - this should send pending ACKs via _delayed_ack_loop cancellation
        await connection._stop_ack_timer()

        # Give async cancellation time to complete and send ACKs
        await asyncio.sleep(0.05)

        # Verify pending ACK was sent (via _delayed_ack_loop cancellation handler)
        # The ACK should be sent when the loop is cancelled
        assert connection.transport.sendto.called or len(connection.pending_acks) == 0

    def test_handle_data_packet_triggers_ack(self, connection):
        """Test that handling data packet triggers ACK."""
        connection.recv_buffer_expected_seq = 100

        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        connection._handle_data_packet(packet)

        # ACK should be queued (or sent if immediate)
        # Either pending_acks has an entry, or sendto was called
        assert len(connection.pending_acks) > 0 or connection.transport.sendto.called

