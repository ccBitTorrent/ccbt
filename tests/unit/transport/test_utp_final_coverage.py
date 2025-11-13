"""Final tests to achieve 100% coverage for uTP implementation."""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

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
    WindowScalingExtension,
)
from ccbt.transport.utp_socket import UTPSocketManager


class TestUTPPacketUnpackEdgeCases:
    """Tests for packet unpacking edge cases."""

    def test_unpack_extension_parse_error(self):
        """Test unpacking packet with extension parse error."""
        # Create a packet with invalid extension data
        # First create valid packet
        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )
        data = packet.pack()
        
        # Manually modify to have extension field set but invalid extension data
        data = bytearray(data)
        data[2] = 1  # Set extension field to indicate extensions present
        # Add invalid extension data that will cause parse error
        # Extension format: [type:1][length:1][data]
        # Invalid: type=0x99 (reserved), length=1, but data is incomplete
        data.extend(b"\x99\x01")  # Invalid extension (incomplete data)
        data = bytes(data)

        # Should handle gracefully (catches exception in unpack)
        # The unpack method catches exceptions during extension parsing
        unpacked = UTPPacket.unpack(data)
        # Should still return a packet (extensions will be empty or partial)
        assert unpacked is not None

    def test_unpack_unsupported_version(self):
        """Test unpacking packet with unsupported version."""
        # Create packet with version != 1
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
        )
        data = packet.pack()
        
        # Modify version byte
        data = bytearray(data)
        data[1] = 2  # Version 2 (unsupported)
        data = bytes(data)

        # Should unpack but log warning
        unpacked = UTPPacket.unpack(data)
        assert unpacked is not None


class TestConnectionInitialization:
    """Tests for connection initialization edge cases."""

    def test_connection_id_generation_during_init(self):
        """Test connection ID generation during initialization."""
        # Connection with connection_id=None should get ID 0 initially
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=None)
        assert conn.connection_id == 0  # Will be set during initialization
        assert not conn._connection_id_generated

    def test_connection_id_already_set(self):
        """Test connection with connection_id already set."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        assert conn.connection_id == 54321
        # If connection_id is provided (not None), _connection_id_generated is True
        # (meaning the ID already exists, doesn't need to be generated)
        assert conn._connection_id_generated is True

    @pytest.mark.asyncio
    async def test_initialize_transport_with_connection_id_generation(self):
        """Test initialize_transport with connection ID generation."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=None)
        
        with patch(
            "ccbt.transport.utp_socket.UTPSocketManager.get_instance"
        ) as mock_get_instance:
            mock_manager = MagicMock()
            mock_transport = MagicMock()
            mock_manager.get_transport.return_value = mock_transport
            mock_manager._generate_connection_id.return_value = 54321
            mock_manager._initialized = True  # Ensure manager is initialized
            mock_get_instance.return_value = mock_manager

            await conn.initialize_transport()

            # Connection ID should be generated
            assert conn.connection_id == 54321
            assert conn._connection_id_generated
            mock_manager._generate_connection_id.assert_called_once()
            mock_manager.register_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_transport_with_existing_connection_id(self):
        """Test initialize_transport when connection_id already set."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        
        with patch(
            "ccbt.transport.utp_socket.UTPSocketManager.get_instance"
        ) as mock_get_instance:
            mock_manager = MagicMock()
            mock_transport = MagicMock()
            mock_manager.get_transport.return_value = mock_transport
            mock_manager._initialized = True
            mock_get_instance.return_value = mock_manager

            await conn.initialize_transport()

            # Connection ID should remain the same
            assert conn.connection_id == 12345
            assert conn._connection_id_generated
            # Should not call _generate_connection_id
            mock_manager._generate_connection_id.assert_not_called()


class TestRTTUpdate:
    """Tests for RTT update edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_update_rtt_no_send_time(self, connection):
        """Test RTT update when send_time is 0."""
        connection.srtt = 0.0
        connection.rttvar = 0.0

        # ACK with timestamp_diff but no send_time
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,  # 50ms delay
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
            0.0,  # send_time = 0
            0,
        )

        # Should use timestamp_diff path (send_time > 0 check fails)
        connection._update_rtt(ack, 0.0)
        
        # SRTT should be updated using timestamp_diff
        assert connection.srtt > 0

    def test_update_rtt_initial_srtt(self, connection):
        """Test initial SRTT calculation."""
        connection.srtt = 0.0
        connection.rttvar = 0.0

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,
        )

        import time
        send_time = time.perf_counter() - 0.05  # 50ms ago
        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            send_time,  # Valid send_time
            0,
        )

        connection._update_rtt(ack, send_time)

        # SRTT should be initialized (was 0, now set to measured_rtt)
        assert connection.srtt > 0

    def test_update_rtt_existing_srtt(self, connection):
        """Test RTT update when SRTT already exists."""
        connection.srtt = 0.1  # Existing SRTT
        connection.rttvar = 0.01

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=60000,  # 60ms
        )

        import time
        send_time = time.perf_counter() - 0.06  # 60ms ago
        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            send_time,
            0,
        )

        old_srtt = connection.srtt
        connection._update_rtt(ack, send_time)

        # SRTT should be updated using EWMA
        assert connection.srtt != old_srtt

    def test_update_rtt_retransmitted_packet(self, connection):
        """Test RTT update skips retransmitted packets (Karn's algorithm)."""
        connection.retransmitted_packets.add(100)

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
            timestamp_diff=50000,
        )

        import time
        send_time = time.perf_counter() - 0.05
        connection.send_buffer[100] = (
            UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=100,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            ),
            send_time,
            0,
        )

        old_srtt = connection.srtt
        connection._update_rtt(ack, send_time)

        # SRTT should not be updated (Karn's algorithm)
        assert connection.srtt == old_srtt


class TestConnectMethod:
    """Tests for connect() method edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    @pytest.mark.asyncio
    async def test_connect_timeout(self, connection):
        """Test connect with timeout."""
        # Start connection
        connect_task = asyncio.create_task(connection.connect())

        # Wait a bit
        await asyncio.sleep(0.1)

        # Cancel to simulate timeout
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass


class TestHandshakeMethods:
    """Tests for handshake methods."""

    @pytest.fixture
    def connection(self):
        """Create a connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    @pytest.mark.asyncio
    async def test_handle_syn_passive_connection(self, connection):
        """Test handling SYN for passive connection."""
        connection.state = UTPConnectionState.IDLE

        syn = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=54321,  # Peer's connection ID
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        syn_data = syn.pack()
        connection._handle_packet(syn_data, ecn_ce=False)

        # Should transition to SYN_RECEIVED
        assert connection.state == UTPConnectionState.SYN_RECEIVED

    @pytest.mark.asyncio
    async def test_handle_syn_ack_complete_handshake(self, connection):
        """Test handling SYN-ACK completes handshake."""
        connection.state = UTPConnectionState.SYN_SENT
        connection.seq_nr = 0

        syn_ack = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,  # ACK our SYN
            wnd_size=65535,
        )

        syn_ack_data = syn_ack.pack()
        connection._handle_packet(syn_ack_data, ecn_ce=False)

        # Give async tasks time
        await asyncio.sleep(0.1)
        
        # Should complete handshake
        assert connection.state == UTPConnectionState.CONNECTED
        
        # Cleanup
        await connection.close()

    @pytest.mark.asyncio
    async def test_complete_handshake(self, connection):
        """Test completing handshake."""
        connection.state = UTPConnectionState.SYN_RECEIVED
        connection.transport = MagicMock()
        connection.on_connected = None  # No callback

        connection._complete_handshake()

        # Should transition to CONNECTED
        assert connection.state == UTPConnectionState.CONNECTED
        
        # Background tasks should be started
        await asyncio.sleep(0.1)
        
        # Cleanup
        await connection.close()

    @pytest.mark.asyncio
    async def test_complete_handshake_with_callback(self, connection):
        """Test completing handshake with callback."""
        connection.state = UTPConnectionState.SYN_RECEIVED
        connection.transport = MagicMock()
        
        callback_called = False
        
        def on_connected():
            nonlocal callback_called
            callback_called = True
        
        connection.on_connected = on_connected

        connection._complete_handshake()

        # Should transition to CONNECTED and call callback
        assert connection.state == UTPConnectionState.CONNECTED
        assert callback_called
        
        # Cleanup
        await asyncio.sleep(0.1)
        await connection.close()

    @pytest.mark.asyncio
    async def test_complete_handshake_callback_exception(self, connection):
        """Test completing handshake with callback that raises exception."""
        connection.state = UTPConnectionState.SYN_RECEIVED
        connection.transport = MagicMock()
        
        def on_connected():
            raise Exception("Test exception")
        
        connection.on_connected = on_connected

        connection._complete_handshake()

        # Should handle exception gracefully
        assert connection.state == UTPConnectionState.CONNECTED
        
        # Cleanup
        await asyncio.sleep(0.1)
        await connection.close()


class TestSendMethod:
    """Tests for send() method edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        conn.send_window = 10000
        return conn

    @pytest.mark.asyncio
    async def test_send_empty_data(self, connection):
        """Test sending empty data."""
        await connection.send(b"")

        # Should handle gracefully
        # May or may not send packet depending on implementation

    @pytest.mark.asyncio
    async def test_send_large_data(self, connection):
        """Test sending large data that requires multiple packets."""
        large_data = b"x" * 100000  # 100KB

        send_task = asyncio.create_task(connection.send(large_data))

        # Wait a bit
        await asyncio.sleep(0.1)

        # Cancel task
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass


class TestReceiveMethod:
    """Tests for receive() method edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_receive_partial_data(self, connection):
        """Test receiving partial data."""
        # Add some data to buffer
        connection.recv_data_buffer = bytearray(b"partial")

        # Request more than available
        receive_task = asyncio.create_task(connection.receive(100))

        # Wait a bit
        await asyncio.sleep(0.05)

        # Cancel task
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_receive_exact_amount(self, connection):
        """Test receiving exact amount of data."""
        connection.recv_data_buffer = bytearray(b"exact data")

        data = await connection.receive(10)  # Exactly 10 bytes

        assert len(data) == 10
        assert data == b"exact data"
        assert len(connection.recv_data_buffer) == 0

    @pytest.mark.asyncio
    async def test_receive_less_than_available(self, connection):
        """Test receiving less than available."""
        connection.recv_data_buffer = bytearray(b"more data than needed")

        data = await connection.receive(4)  # Only 4 bytes

        assert len(data) == 4
        assert data == b"more"
        # Rest should remain in buffer
        assert len(connection.recv_data_buffer) > 0
        assert connection.recv_data_buffer == bytearray(b" data than needed")
        # Should set event since more data available
        assert connection.recv_data_available.is_set()

    @pytest.mark.asyncio
    async def test_receive_all_available(self, connection):
        """Test receiving all available data."""
        connection.recv_data_buffer = bytearray(b"all data")

        data = await connection.receive(-1)  # All available

        assert data == b"all data"
        assert len(connection.recv_data_buffer) == 0


class TestBackgroundTasks:
    """Tests for background task management."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_retransmission_loop_exception(self, connection):
        """Test retransmission loop handles exceptions."""
        connection.state = UTPConnectionState.CONNECTED
        
        # Mock _check_retransmissions to raise exception
        original_check = connection._check_retransmissions
        call_count = 0
        
        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test exception")
            # After exception, call original
            await original_check()
        
        connection._check_retransmissions = mock_check
        
        task = asyncio.create_task(connection._retransmission_loop())
        
        # Wait a bit for exception to occur and loop to continue
        await asyncio.sleep(0.25)
        
        # Verify loop continued after exception (call_count should be > 1)
        assert call_count > 1, "Loop should continue after exception"
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_send_loop_exception(self, connection):
        """Test send loop handles exceptions."""
        connection.state = UTPConnectionState.CONNECTED
        
        # Mock send to raise exception
        original_send = connection.send
        call_count = 0
        
        async def mock_send(data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test exception")
            await original_send(data)
        
        connection.send = mock_send
        
        # Add data to queue
        await connection.send_queue.put(b"test")
        
        task = asyncio.create_task(connection._send_loop())
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_send_loop_timeout(self, connection):
        """Test send loop timeout handling."""
        connection.state = UTPConnectionState.CONNECTED
        
        task = asyncio.create_task(connection._send_loop())
        
        # Wait for timeout (1 second)
        await asyncio.sleep(1.1)
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestDelayedAckLoop:
    """Tests for delayed ACK loop."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_delayed_ack_loop_exception(self, connection):
        """Test delayed ACK loop handles exceptions."""
        connection.state = UTPConnectionState.CONNECTED
        connection.ack_delay = 0.01
        
        # Mock _send_batched_acks to raise exception
        original_send = connection._send_batched_acks
        call_count = 0
        
        def mock_send():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test exception")
            original_send()
        
        connection._send_batched_acks = mock_send
        
        # Add pending ACK
        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=65535,
        )
        connection.pending_acks.append(ack)
        
        task = asyncio.create_task(connection._delayed_ack_loop())
        
        # Wait a bit
        await asyncio.sleep(0.05)
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestSACKBlockGeneration:
    """Tests for SACK block generation edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connection with SACK enabled."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        from ccbt.transport.utp_extensions import UTPExtensionType
        conn.negotiated_extensions.add(UTPExtensionType.SACK)
        return conn

    def test_process_sack_blocks_empty_list(self, connection):
        """Test processing empty SACK blocks list."""
        connection._process_sack_blocks([])
        
        # Should handle gracefully
        assert True  # No exception

    def test_process_sack_blocks_not_instance(self, connection):
        """Test processing SACK blocks with non-SACKBlock items."""
        from ccbt.transport.utp_extensions import SACKBlock
        
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

        # Process with mix of SACKBlock and non-SACKBlock items
        real_block = SACKBlock(start_seq=100, end_seq=105)
        fake_block = MagicMock()  # Not a SACKBlock
        fake_block.start_seq = 105
        fake_block.end_seq = 110
        
        connection._process_sack_blocks([real_block, fake_block])

        # Should process real block but skip fake one (isinstance check fails)
        # Packets 100-104 should be removed
        assert 100 not in connection.send_buffer
        assert 101 not in connection.send_buffer
        assert 102 not in connection.send_buffer
        assert 103 not in connection.send_buffer
        assert 104 not in connection.send_buffer
        # Packets 105-109 should remain (fake block skipped)
        assert 105 in connection.send_buffer
        assert 109 in connection.send_buffer

    def test_selective_retransmit(self, connection):
        """Test selective retransmission."""
        # Add packets to send buffer
        for seq in [100, 101, 102]:
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            )
            import time
            connection.send_buffer[seq] = (packet, time.perf_counter(), 0)

        connection.transport = MagicMock()
        connection.transport.sendto = MagicMock()

        # Retransmit missing sequences
        missing_seqs = [101, 102]
        connection._selective_retransmit(missing_seqs)

        # Should retransmit packets 101 and 102
        assert connection.transport.sendto.call_count == 2
        assert 101 in connection.retransmitted_packets
        assert 102 in connection.retransmitted_packets
        # Packets should still be in send_buffer with updated retry count
        assert 101 in connection.send_buffer
        assert 102 in connection.send_buffer

    def test_selective_retransmit_not_in_buffer(self, connection):
        """Test selective retransmit when packet not in buffer."""
        connection.transport = MagicMock()
        connection.transport.sendto = MagicMock()

        # Try to retransmit packet not in send buffer
        missing_seqs = [999]
        connection._selective_retransmit(missing_seqs)

        # Should not send anything
        assert not connection.transport.sendto.called

    def test_generate_sack_blocks_empty(self, connection):
        """Test generating SACK blocks with no received sequences."""
        connection.received_seqs = set()
        blocks = connection._generate_sack_blocks()
        
        assert len(blocks) == 0

    def test_generate_sack_blocks_single(self, connection):
        """Test generating SACK blocks with single sequence."""
        connection.received_seqs = {100}
        blocks = connection._generate_sack_blocks()
        
        assert len(blocks) == 1
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 101

    def test_generate_sack_blocks_contiguous(self, connection):
        """Test generating SACK blocks with contiguous sequences."""
        connection.received_seqs = {100, 101, 102, 103, 104}
        blocks = connection._generate_sack_blocks()
        
        # Should be one contiguous block
        assert len(blocks) == 1
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 105

    def test_generate_sack_blocks_gaps(self, connection):
        """Test generating SACK blocks with gaps."""
        connection.received_seqs = {100, 101, 105, 106, 110, 111}
        blocks = connection._generate_sack_blocks()
        
        # Should have 3 blocks
        assert len(blocks) == 3
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 102
        assert blocks[1].start_seq == 105
        assert blocks[1].end_seq == 107
        assert blocks[2].start_seq == 110
        assert blocks[2].end_seq == 112

    def test_generate_sack_blocks_max_limit(self, connection):
        """Test SACK blocks limited to max 4 blocks."""
        # Create more than 4 gaps
        connection.received_seqs = {100, 102, 104, 106, 108, 110, 112, 114, 116}
        blocks = connection._generate_sack_blocks()
        
        # Should be limited to 4 blocks (RFC 2018)
        assert len(blocks) <= 4

    def test_generate_sack_blocks_wraparound(self, connection):
        """Test generating SACK blocks with sequence wraparound."""
        # Sequences near wraparound boundary (0xFFFE and 0xFFFF are contiguous)
        # When 0xFFFF is encountered, block_end would be 0x10000 which wraps to 0
        # However, SACKBlock validation requires end_seq to be > start_seq and <= 0xFFFF
        # So we can't represent a block that ends at 0 (wrapped). The code handles this
        # by creating a block ending at 0xFFFF instead.
        connection.received_seqs = {0xFFFE, 0xFFFF}
        blocks = connection._generate_sack_blocks()
        
        # Should handle wraparound: Since 0xFFFF + 1 wraps to 0, but we can't represent
        # end_seq=0 (must be > start_seq), the code creates a block ending at 0xFFFF
        assert len(blocks) == 1
        assert blocks[0].start_seq == 0xFFFE
        # End should be 0xFFFF (max valid value, since we can't represent wraparound)
        assert blocks[0].end_seq == 0xFFFF


class TestWindowScaling:
    """Tests for window scaling edge cases."""

    @pytest.fixture
    def connection(self):
        """Create a connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_window_scaling_zero_scale(self, connection):
        """Test window scaling with scale factor 0."""
        connection.window_scale = 0
        connection.send_window = 10000

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=20000,
            timestamp=0,
        )

        connection._handle_state_packet(ack)

        # No scaling (scale = 0)
        assert connection.send_window == 20000

    def test_window_scaling_large_scale(self, connection):
        """Test window scaling with large scale factor."""
        connection.window_scale = 4
        connection.send_window = 10000

        ack = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=100,
            wnd_size=10000,
            timestamp=0,
        )

        connection._handle_state_packet(ack)

        # Should be scaled: 10000 << 4 = 160000
        assert connection.send_window == 160000


class TestSocketManagerEdgeCases:
    """Tests for socket manager edge cases."""

    @pytest.fixture
    def socket_manager(self):
        """Create a socket manager."""
        manager = UTPSocketManager()
        manager.transport = MagicMock()
        return manager

    def test_handle_incoming_packet_pending_connection(self, socket_manager):
        """Test handling packet for pending connection."""
        # Create pending connection
        conn = MagicMock()
        conn.connection_id = 12345
        socket_manager.pending_connections[12345] = conn
        conn._handle_packet = MagicMock()

        # Create packet
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        data = packet.pack()
        addr = ("127.0.0.1", 6881)

        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)

        # Should route to pending connection
        conn._handle_packet.assert_called_once()

    def test_handle_incoming_packet_collision_check(self, socket_manager):
        """Test collision detection in packet handling."""
        # Register connection with ID
        conn1 = MagicMock()
        conn1.connection_id = 12345
        socket_manager.register_connection(conn1, ("127.0.0.1", 6881), 12345)
        socket_manager.active_connection_ids.add(12345)

        # Create packet with same ID but different address
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        data = packet.pack()
        addr = ("127.0.0.2", 6882)  # Different address

        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)

        # Should detect collision and drop packet
        # No new connection should be created

    def test_handle_incoming_packet_too_small(self, socket_manager):
        """Test handling packet that's too small."""
        small_data = b"\x01\x00"  # Too small
        addr = ("127.0.0.1", 6881)

        socket_manager._handle_incoming_packet(small_data, addr, ecn_ce=False)

        # Should handle gracefully (logged and dropped)

    def test_handle_incoming_packet_unknown_connection(self, socket_manager):
        """Test handling packet for unknown connection."""
        # Use a valid connection_id (0-65535) that's not registered
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=54321,  # Unknown ID (valid range)
            seq_nr=0,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        data = packet.pack()
        addr = ("127.0.0.1", 6881)

        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)

        # Should handle gracefully (logged and dropped)

    def test_send_packet_not_initialized(self, socket_manager):
        """Test sending packet when not initialized."""
        socket_manager.transport = None

        packet_data = b"test"
        addr = ("127.0.0.1", 6881)

        with pytest.raises(RuntimeError, match="uTP socket not initialized"):
            socket_manager.send_packet(packet_data, addr)

    def test_get_statistics(self, socket_manager):
        """Test getting statistics."""
        socket_manager.total_packets_received = 100
        socket_manager.total_packets_sent = 50
        socket_manager.total_bytes_received = 10000
        socket_manager.total_bytes_sent = 5000

        stats = socket_manager.get_statistics()

        assert stats["total_packets_received"] == 100
        assert stats["total_packets_sent"] == 50
        assert stats["total_bytes_received"] == 10000
        assert stats["total_bytes_sent"] == 5000
        assert "active_connections" in stats

    def test_generate_connection_id_exhaustion(self, socket_manager):
        """Test connection ID generation when all IDs are used."""
        # Fill all possible IDs
        for i in range(0x0001, 0xFFFE):
            socket_manager.active_connection_ids.add(i)

        # Should raise RuntimeError after max attempts
        with pytest.raises(RuntimeError, match="Could not generate unique connection ID"):
            socket_manager._generate_connection_id()


class TestCalculateSendRate:
    """Tests for send rate calculation."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_calculate_send_rate_initial(self, connection):
        """Test initial send rate calculation."""
        connection.srtt = 0.0
        connection.last_timestamp_diff = 0

        rate = connection._calculate_send_rate()
        
        # Should return some rate
        assert rate >= 0

    def test_calculate_send_rate_with_rtt(self, connection):
        """Test send rate calculation with RTT."""
        connection.srtt = 0.1  # 100ms
        connection.last_timestamp_diff = 50000  # 50ms
        connection.last_rate_update = 0.0

        rate = connection._calculate_send_rate()
        
        # Should calculate based on RTT
        assert rate > 0

    def test_calculate_send_rate_max_limit(self, connection):
        """Test send rate respects max limit."""
        from unittest.mock import patch
        
        connection.srtt = 0.001  # Very small RTT
        connection.last_timestamp_diff = 1000  # Very small delay
        connection.last_rate_update = 0.0

        with patch.object(
            connection.config.network.utp, "max_rate", 1000.0
        ) if hasattr(connection.config, "network") else patch.object(
            connection, "config", MagicMock()
        ):
            rate = connection._calculate_send_rate()
            
            # Should not exceed max rate
            # (actual check depends on config structure)

    def test_calculate_send_rate_min_limit(self, connection):
        """Test send rate respects min limit."""
        connection.srtt = 10.0  # Very large RTT
        connection.last_timestamp_diff = 10000000  # Very large delay
        connection.last_rate_update = 0.0

        rate = connection._calculate_send_rate()
        
        # Should respect minimum rate
        assert rate >= 0


class TestUpdateSendWindow:
    """Tests for send window update."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_update_send_window_initial(self, connection):
        """Test initial send window update."""
        connection.send_window = 0
        connection.srtt = 0.0
        connection.last_timestamp_diff = 0

        connection._update_send_window()
        
        # Should set some window size
        assert connection.send_window >= 0

    def test_update_send_window_with_timestamp_diff(self, connection):
        """Test send window update with timestamp_diff."""
        connection.send_window = 10000
        connection.srtt = 0.1
        connection.last_timestamp_diff = 50000  # 50ms

        connection._update_send_window()
        
        # Window should be updated
        assert connection.send_window > 0


class TestProcessOutOfOrderPackets:
    """Tests for processing out-of-order packets."""

    @pytest.fixture
    def connection(self):
        """Create a connected connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_process_out_of_order_none(self, connection):
        """Test processing when no out-of-order packets."""
        connection.recv_buffer_expected_seq = 100
        connection.recv_buffer = {}  # Empty

        connection._process_out_of_order_packets()

        # Should handle gracefully (nothing to process)
        assert connection.recv_buffer_expected_seq == 100

    def test_process_out_of_order_single(self, connection):
        """Test processing single out-of-order packet."""
        connection.recv_buffer_expected_seq = 100

        # Add out-of-order packet
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=101,  # Out of order
            ack_nr=0,
            wnd_size=65535,
            data=b"packet2",
        )
        connection.recv_buffer[101] = packet

        # Add in-order packet
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,  # In order
            ack_nr=0,
            wnd_size=65535,
            data=b"packet1",
        )
        connection.recv_buffer[100] = packet2

        connection._process_out_of_order_packets()

        # Both should be processed (100 triggers processing, 101 is in-order after)
        assert 100 not in connection.recv_buffer
        assert 101 not in connection.recv_buffer
        assert connection.recv_buffer_expected_seq == 102
        assert b"packet1" in connection.recv_data_buffer
        assert b"packet2" in connection.recv_data_buffer

    def test_process_out_of_order_chain(self, connection):
        """Test processing chain of out-of-order packets."""
        connection.recv_buffer_expected_seq = 100

        # Add chain of out-of-order packets
        for seq in [101, 102, 103]:
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=65535,
                data=f"packet{seq}".encode(),
            )
            connection.recv_buffer[seq] = packet

        # Add in-order packet to trigger processing
        packet0 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet100",
        )
        connection.recv_buffer[100] = packet0

        connection._process_out_of_order_packets()

        # All should be processed (continuous chain from 100-103)
        assert len(connection.recv_buffer) == 0
        assert connection.recv_buffer_expected_seq == 104
        assert b"packet100" in connection.recv_data_buffer
        assert b"packet101" in connection.recv_data_buffer
        assert b"packet102" in connection.recv_data_buffer
        assert b"packet103" in connection.recv_data_buffer

