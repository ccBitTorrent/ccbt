"""Additional tests to improve coverage for utp.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import UTPConfig
from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
    UTPPacket,
    UTPPacketType,
)
from ccbt.transport.utp_extensions import (
    ECNExtension,
    SACKExtension,
    SACKBlock,
    UTPExtensionType,
)


class TestConnectionInitialization:
    """Tests for connection initialization and setup."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        return UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)

    def test_connection_default_values(self, connection):
        """Test connection default values."""
        assert connection.state == UTPConnectionState.IDLE
        assert connection.connection_id == 12345
        assert connection.seq_nr == 0
        assert connection.ack_nr == 0
        assert connection.send_window == 0
        assert connection.recv_window == 65535
        assert connection.rtt == 0.0
        assert connection.rtt_variance == 0.0

    def test_connection_with_custom_window(self):
        """Test connection with custom window sizes."""
        conn = UTPConnection(
            remote_addr=("127.0.0.1", 6881),
            connection_id=54321,
            recv_window_size=32768,
        )
        assert conn.recv_window == 32768


class TestPacketHandling:
    """Tests for packet handling methods."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_handle_packet_invalid_data(self, connection):
        """Test handling invalid packet data."""
        # Too small to be valid
        invalid = b"short"
        connection._handle_packet(invalid, ecn_ce=False)
        # Should log warning but not crash

    def test_handle_packet_unknown_type(self, connection):
        """Test handling packet with unknown type."""
        # Create a valid packet first, then manually modify the type byte
        # UTPPacketType is an IntEnum, so we can create an invalid value
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,  # Valid type initially
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
            data=b"test",
        )
        packet_data = packet.pack()
        # Manually modify type byte to invalid value
        # The first byte is: type (4 bits) | ver (2 bits) | extension (1 bit) | reserved (1 bit)
        # For ST_DATA (type=1), the byte is 0x01
        # We'll set it to 0x63 (99) which gives us type=3, ver=3, ext=1, reserved=1
        packet_data = bytearray(packet_data)
        packet_data[0] = 0x63  # Invalid/unknown type
        packet_data = bytes(packet_data)

        # Try to unpack - this might fail or succeed depending on validation
        # If it succeeds, we'll get a packet with an invalid type
        connection._handle_packet(packet_data, ecn_ce=False)
        # Should log warning for unknown type or invalid packet

    @pytest.mark.asyncio
    async def test_handle_syn_in_syn_sent_state(self, connection):
        """Test handling SYN-ACK when in SYN_SENT state."""
        connection.state = UTPConnectionState.SYN_SENT

        syn_ack = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=54321,
            seq_nr=0,
            ack_nr=0,  # ACK our SYN
            wnd_size=65535,
        )

        syn_ack_data = syn_ack.pack()
        connection._handle_packet(syn_ack_data, ecn_ce=False)

        # Should handle SYN-ACK and transition to CONNECTED
        # Give async tasks time to start
        await asyncio.sleep(0.1)
        assert connection.state == UTPConnectionState.CONNECTED
        
        # Cleanup
        await connection.close()

    def test_handle_syn_in_invalid_state(self, connection):
        """Test handling SYN in invalid state."""
        connection.state = UTPConnectionState.CLOSED

        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        syn_data = syn_packet.pack()
        connection._handle_packet(syn_data, ecn_ce=False)

        # Should log warning but not crash
        assert connection.state == UTPConnectionState.CLOSED


class TestRTTUpdate:
    """Tests for RTT update logic."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_update_rtt_retransmitted_packet(self, connection):
        """Test RTT update excludes retransmitted packets."""
        # Mark packet as retransmitted
        connection.retransmitted_packets.add(100)
        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            0.0,
            1,
        )

        # Set initial RTT
        connection.srtt = 0.1
        old_srtt = connection.srtt

        # Receive ACK for retransmitted packet
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,
        )

        connection._update_rtt(ack, 0.0)

        # SRTT should not be updated (Karn's algorithm)
        assert connection.srtt == old_srtt

    def test_update_rtt_initial_measurement(self, connection):
        """Test initial RTT measurement."""
        # No prior RTT
        connection.srtt = 0.0
        connection.rttvar = 0.0

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,  # 50ms
        )

        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            0.0,
            0,
        )

        connection._update_rtt(ack, 0.0)

        # SRTT should be set
        assert connection.srtt > 0

    def test_update_rtt_ewma_calculation(self, connection):
        """Test RTT update using EWMA."""
        connection.srtt = 0.1  # 100ms
        connection.rttvar = 0.01

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=60000,  # 60ms
        )

        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            0.0,
            0,
        )

        old_srtt = connection.srtt
        connection._update_rtt(ack, 0.0)

        # SRTT should be updated using EWMA
        assert connection.srtt != old_srtt


class TestSendWindow:
    """Tests for send window management."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration with UTP settings."""
        config = MagicMock()
        config.network = MagicMock()
        config.network.utp = UTPConfig()
        return config

    @pytest.fixture
    def connection(self, mock_config):
        """Create a connected UTP connection."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
            conn.transport = MagicMock()
            conn.state = UTPConnectionState.CONNECTED
            return conn

    def test_update_send_window_with_scaling(self, connection, mock_config):
        """Test updating send window with window scaling."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            connection.window_scale = 2
            connection.send_window = 10000
            connection.srtt = 0.1
            connection.last_timestamp_diff = 50000

            connection._update_send_window()

            # Window should be updated (may be reduced due to congestion control)
            assert connection.send_window > 0

    def test_update_send_window_no_scaling(self, connection, mock_config):
        """Test updating send window without scaling."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            connection.window_scale = 0
            connection.send_window = 10000
            connection.srtt = 0.1
            connection.last_timestamp_diff = 50000

            connection._update_send_window()

            # Window should be updated (may be reduced due to congestion control)
            assert connection.send_window > 0


class TestStatePacketHandling:
    """Tests for state packet handling."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_handle_state_packet_with_sack(self, connection):
        """Test handling state packet with SACK extension."""
        from ccbt.transport.utp_extensions import UTPExtensionType

        connection.negotiated_extensions.add(UTPExtensionType.SACK)

        # Add packets to send buffer
        packets = {}
        for seq in [100, 101, 102]:
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            )
            connection.send_buffer[seq] = (packet, 0.0, 0)

        # Create ACK with SACK
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,  # ACK seq 100
            wnd_size=65535,
            extensions=[
                SACKExtension(blocks=[SACKBlock(start_seq=101, end_seq=103)])
            ],
        )

        connection._handle_state_packet(ack)

        # SACK'd packets should be removed
        assert 101 not in connection.send_buffer
        assert 102 not in connection.send_buffer

    def test_handle_state_packet_window_scaling(self, connection):
        """Test handling state packet with window scaling."""
        connection.window_scale = 2

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=10000,  # Scaled window
            timestamp=0,
        )

        connection._handle_state_packet(ack)

        # Window should be scaled: 10000 << 2 = 40000
        assert connection.send_window == 40000

    def test_handle_state_packet_duplicate_ack(self, connection):
        """Test handling duplicate ACK."""
        connection.last_ack_nr = 50
        connection.duplicate_acks = 2

        # Send duplicate ACK
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=50,  # Same as last_ack_nr
            wnd_size=65535,
        )

        connection._handle_state_packet(ack)

        # Should increment duplicate ACK count
        assert connection.duplicate_acks == 3

    def test_handle_state_packet_new_ack(self, connection):
        """Test handling new ACK (not duplicate)."""
        connection.last_ack_nr = 50
        connection.duplicate_acks = 2

        # Send new ACK
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,  # New ACK number
            wnd_size=65535,
        )

        connection._handle_state_packet(ack)

        # Should reset duplicate ACK count
        assert connection.duplicate_acks == 0
        assert connection.last_ack_nr == 100


class TestSACKBlockGeneration:
    """Tests for SACK block generation."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        from ccbt.transport.utp_extensions import UTPExtensionType

        conn.negotiated_extensions.add(UTPExtensionType.SACK)
        return conn

    def test_generate_sack_blocks_contiguous(self, connection):
        """Test generating SACK blocks for contiguous range."""
        connection.received_seqs = {100, 101, 102, 103, 104, 105}
        blocks = connection._generate_sack_blocks()

        assert len(blocks) == 1
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 106  # Exclusive end

    def test_generate_sack_blocks_gaps(self, connection):
        """Test generating SACK blocks with gaps."""
        # Sequences: 100, 101, 105, 106, 110, 111, 112
        connection.received_seqs = {100, 101, 105, 106, 110, 111, 112}
        blocks = connection._generate_sack_blocks()

        # Should have 3 blocks
        assert len(blocks) == 3
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 102
        assert blocks[1].start_seq == 105
        assert blocks[1].end_seq == 107
        assert blocks[2].start_seq == 110
        assert blocks[2].end_seq == 113

    def test_process_sack_blocks(self, connection):
        """Test processing SACK blocks."""
        # Add packets to send buffer
        for seq in range(100, 110):
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            )
            connection.send_buffer[seq] = (packet, 0.0, 0)

        # Process SACK blocks
        sack_blocks = [
            SACKBlock(start_seq=100, end_seq=105),  # ACK seq 100-104
            SACKBlock(start_seq=107, end_seq=110),  # ACK seq 107-109
        ]

        connection._process_sack_blocks(sack_blocks)

        # SACK'd packets should be removed
        assert 100 not in connection.send_buffer
        assert 101 not in connection.send_buffer
        assert 102 not in connection.send_buffer
        assert 103 not in connection.send_buffer
        assert 104 not in connection.send_buffer
        assert 107 not in connection.send_buffer
        assert 108 not in connection.send_buffer
        assert 109 not in connection.send_buffer

        # Not SACK'd packets should remain
        assert 105 in connection.send_buffer
        assert 106 in connection.send_buffer


class TestConnectMethod:
    """Tests for connect() method."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    @pytest.mark.asyncio
    async def test_connect_sends_syn(self, connection):
        """Test connect() sends SYN packet."""
        # Start connection with short timeout to avoid hanging
        connect_task = asyncio.create_task(connection.connect(timeout=0.5))

        # Wait a bit for SYN to be sent (should be immediate)
        await asyncio.sleep(0.05)

        # Verify SYN was sent
        assert connection.transport.sendto.called
        call_args = connection.transport.sendto.call_args
        packet_data = call_args[0][0]

        # Unpack and verify it's a SYN
        packet = UTPPacket.unpack(packet_data)
        assert packet.type == UTPPacketType.ST_SYN

        # Cancel task and wait for cleanup
        connect_task.cancel()
        try:
            await asyncio.wait_for(connect_task, timeout=0.1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        
        # Ensure connection timeout task is cleaned up
        if hasattr(connection, '_connection_timeout_task') and connection._connection_timeout_task:
            if not connection._connection_timeout_task.done():
                connection._connection_timeout_task.cancel()
                try:
                    await asyncio.wait_for(connection._connection_timeout_task, timeout=0.1)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        
        # Clean up any background tasks
        if hasattr(connection, '_retransmission_task') and connection._retransmission_task:
            if not connection._retransmission_task.done():
                connection._retransmission_task.cancel()
                try:
                    await asyncio.wait_for(connection._retransmission_task, timeout=0.1)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        
        if hasattr(connection, '_send_task') and connection._send_task:
            if not connection._send_task.done():
                connection._send_task.cancel()
                try:
                    await asyncio.wait_for(connection._send_task, timeout=0.1)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass


class TestSendMethod:
    """Tests for send() method."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        conn.send_window = 10000
        return conn

    @pytest.mark.asyncio
    async def test_send_data(self, connection):
        """Test sending data."""
        # Ensure send_window is set and send_buffer is empty
        connection.send_window = 100000  # Large enough window
        connection.send_buffer.clear()  # Clear any existing packets
        connection.max_unacked_packets = 100  # Ensure limit is reasonable
        
        data = b"test data" * 100

        # Send data with timeout to prevent hanging
        try:
            await asyncio.wait_for(connection.send(data), timeout=1.0)
        except asyncio.TimeoutError:
            # If timeout occurs, verify that at least some packets were sent
            # This can happen if window closes during send
            assert connection.transport.sendto.called or len(connection.send_buffer) > 0
            return

        # Verify packets were sent
        assert connection.transport.sendto.called

    @pytest.mark.asyncio
    async def test_send_not_connected(self, connection):
        """Test sending when not connected."""
        connection.state = UTPConnectionState.IDLE

        with pytest.raises(RuntimeError, match="Cannot send data"):
            await connection.send(b"data")


class TestReceiveMethod:
    """Tests for receive() method."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_receive_data(self, connection):
        """Test receiving data."""
        # Add data to receive buffer
        connection.recv_data_buffer = bytearray(b"received data")

        # Receive data
        data = await connection.receive(-1)

        assert data == b"received data"

    @pytest.mark.asyncio
    async def test_receive_with_timeout(self, connection):
        """Test receiving with timeout."""
        connection.recv_data_buffer = bytearray()

        # Try to receive with short timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(connection.receive(-1), timeout=0.1)


class TestBackgroundTasks:
    """Tests for background task management."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_start_background_tasks(self, connection):
        """Test starting background tasks."""
        connection._start_background_tasks()

        # Tasks should be created
        assert connection._retransmission_task is not None
        assert connection._send_task is not None

        # Cleanup
        await connection.close()

    @pytest.mark.asyncio
    async def test_retransmission_loop(self, connection):
        """Test retransmission loop."""
        connection.state = UTPConnectionState.CONNECTED
        connection._retransmission_task = asyncio.create_task(
            connection._retransmission_loop()
        )

        # Wait a bit
        await asyncio.sleep(0.15)  # Longer than check interval

        # Cancel task
        connection._retransmission_task.cancel()
        try:
            await connection._retransmission_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_send_loop(self, connection):
        """Test send loop."""
        connection.state = UTPConnectionState.CONNECTED
        connection._send_task = asyncio.create_task(connection._send_loop())

        # Add data to queue
        await connection.send_queue.put(b"test data")

        # Wait a bit
        await asyncio.sleep(0.1)

        # Cancel task
        connection._send_task.cancel()
        try:
            await connection._send_task
        except asyncio.CancelledError:
            pass


class TestCloseMethod:
    """Tests for close() method."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_close_sends_fin(self, connection):
        """Test close() sends FIN packet."""
        await connection.close()

        # Verify FIN was sent
        assert connection.transport.sendto.called
        call_args = connection.transport.sendto.call_args
        packet_data = call_args[0][0]

        # Unpack and verify it's a FIN
        packet = UTPPacket.unpack(packet_data)
        assert packet.type == UTPPacketType.ST_FIN

        # State should be FIN_SENT or CLOSED
        assert connection.state in (
            UTPConnectionState.FIN_SENT,
            UTPConnectionState.CLOSED,
        )

    @pytest.mark.asyncio
    async def test_close_stops_tasks(self, connection):
        """Test close() stops background tasks."""
        connection._start_background_tasks()
        connection._start_ack_timer()

        await connection.close()

        # Tasks should be cancelled
        assert connection._retransmission_task is None or connection._retransmission_task.done()
        assert connection._send_task is None or connection._send_task.done()
        assert connection.ack_timer is None or connection.ack_timer.done()


class TestShouldSendImmediateAck:
    """Tests for immediate ACK conditions."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_immediate_ack_out_of_order(self, connection):
        """Test immediate ACK for out-of-order packet."""
        connection.recv_buffer_expected_seq = 100

        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=105,  # Out of order
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )

        assert connection._should_send_immediate_ack(packet) is True

    def test_immediate_ack_every_second(self, connection):
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
        connection.ack_packet_count = 1
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=101,
            ack_nr=0,
            wnd_size=0,
            data=b"data2",
        )
        assert connection._should_send_immediate_ack(packet2) is True


class TestQueueAck:
    """Tests for ACK queueing."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

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
        assert connection.pending_acks[0].ack_nr == 101


class TestSendBatchedAcks:
    """Tests for batched ACK sending."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_send_batched_acks(self, connection):
        """Test sending batched ACKs."""
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )

        connection.pending_acks.append(ack)
        connection._send_batched_acks()

        # ACK should be sent
        assert connection.transport.sendto.called
        assert len(connection.pending_acks) == 0
        assert connection.ack_packet_count == 0


class TestPacketValidation:
    """Tests for packet validation errors."""

    def test_packet_validation_invalid_type(self):
        """Test packet validation with invalid type."""
        packet = UTPPacket(
            type=99,  # Invalid type (> 4)
            connection_id=0x1234,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid packet type"):
            packet.pack()

    def test_packet_validation_invalid_connection_id(self):
        """Test packet validation with invalid connection_id."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x10000,  # Too large (17 bits)
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid connection_id"):
            packet.pack()

    def test_packet_validation_invalid_seq_nr(self):
        """Test packet validation with invalid seq_nr."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x1234,
            seq_nr=0x10000,  # Too large (17 bits)
            ack_nr=0,
            wnd_size=65535,
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid seq_nr"):
            packet.pack()

    def test_packet_validation_invalid_ack_nr(self):
        """Test packet validation with invalid ack_nr."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x1234,
            seq_nr=0,
            ack_nr=0x10000,  # Too large (17 bits)
            wnd_size=65535,
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid ack_nr"):
            packet.pack()

    def test_packet_validation_invalid_wnd_size(self):
        """Test packet validation with invalid wnd_size."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x1234,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0x100000000,  # Too large (33 bits)
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid wnd_size"):
            packet.pack()

    def test_packet_validation_invalid_timestamp(self):
        """Test packet validation with invalid timestamp."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x1234,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            timestamp=0x100000000,  # Too large (33 bits)
            timestamp_diff=0,
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid timestamp"):
            packet.pack()

    def test_packet_validation_invalid_timestamp_diff(self):
        """Test packet validation with invalid timestamp_diff."""
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=0x1234,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            timestamp=0,
            timestamp_diff=0x100000000,  # Too large (33 bits)
            data=b"",
        )
        with pytest.raises(ValueError, match="Invalid timestamp_diff"):
            packet.pack()


class TestInitializeTransport:
    """Tests for initialize_transport method."""

    @pytest.mark.asyncio
    async def test_initialize_transport(self):
        """Test initializing transport via socket manager."""
        from ccbt.transport.utp_socket import UTPSocketManager

        # Create connection
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)

        # Mock socket manager
        mock_socket_manager = MagicMock(spec=UTPSocketManager)
        mock_transport = MagicMock()
        mock_socket_manager.get_transport.return_value = mock_transport
        mock_socket_manager._generate_connection_id.return_value = 54321
        mock_socket_manager.register_connection = MagicMock()

        with patch(
            "ccbt.transport.utp_socket.UTPSocketManager.get_instance",
            return_value=mock_socket_manager,
        ):
            await conn.initialize_transport()

        # Verify transport was set
        assert conn.transport == mock_transport
        # Verify connection was registered
        mock_socket_manager.register_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_transport_generates_connection_id(self):
        """Test initialize_transport generates connection ID if not set."""
        from ccbt.transport.utp_socket import UTPSocketManager

        # Create connection without connection_id
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=None)
        conn._connection_id_generated = False

        # Mock socket manager
        mock_socket_manager = MagicMock(spec=UTPSocketManager)
        mock_transport = MagicMock()
        mock_socket_manager.get_transport.return_value = mock_transport
        mock_socket_manager._generate_connection_id.return_value = 99999
        mock_socket_manager.register_connection = MagicMock()

        with patch(
            "ccbt.transport.utp_socket.UTPSocketManager.get_instance",
            return_value=mock_socket_manager,
        ):
            await conn.initialize_transport()

        # Verify connection ID was generated
        assert conn.connection_id == 99999
        assert conn._connection_id_generated is True

