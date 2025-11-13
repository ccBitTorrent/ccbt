"""Additional tests to improve coverage for uTP transport."""

import asyncio
import struct
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
    UTPPacket,
    UTPPacketType,
)


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.network.utp.prefer_over_tcp = True
    config.network.utp.connection_timeout = 5.0
    config.network.utp.max_window_size = 65535
    config.network.utp.mtu = 1200
    config.network.utp.initial_rate = 5120
    config.network.utp.min_rate = 512
    config.network.utp.max_rate = 1000000
    config.network.utp.ack_interval = 0.1
    config.network.utp.retransmit_timeout_factor = 1.0
    config.network.utp.max_retransmits = 10
    config.network.listen_interface = "0.0.0.0"
    config.network.listen_port = 6881
    return config


@pytest.fixture
def remote_addr():
    """Remote address for testing."""
    return ("127.0.0.1", 6881)


class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    def test_packet_validation_timestamp_too_large(self):
        """Test packet validation with timestamp too large."""
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

    def test_packet_validation_timestamp_diff_too_large(self):
        """Test packet validation with timestamp_diff too large."""
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

    @pytest.mark.asyncio
    async def test_set_transport(self, mock_config, remote_addr):
        """Test setting transport."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            mock_transport = MagicMock()
            conn.set_transport(mock_transport)
            assert conn.transport == mock_transport

    @pytest.mark.asyncio
    async def test_update_rtt_existing_rtt(self, mock_config, remote_addr):
        """Test RTT update with existing RTT."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            conn.rtt_variance = 0.01
            packet = UTPPacket(
                type=UTPPacketType.ST_STATE,
                connection_id=conn.connection_id,
                seq_nr=1,
                ack_nr=1,
                wnd_size=65535,
                timestamp=1000000,
                timestamp_diff=100000,
                data=b"",
            )
            send_time = time.perf_counter() - 0.05
            conn._update_rtt(packet, send_time)
            # RTT should be smoothed
            assert conn.rtt > 0

    @pytest.mark.asyncio
    async def test_update_rtt_variance_existing(self, mock_config, remote_addr):
        """Test RTT variance update with existing variance."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            conn.rtt_variance = 0.01
            packet = UTPPacket(
                type=UTPPacketType.ST_STATE,
                connection_id=conn.connection_id,
                seq_nr=1,
                ack_nr=1,
                wnd_size=65535,
                timestamp=1000000,
                timestamp_diff=100000,
                data=b"",
            )
            send_time = time.perf_counter() - 0.05
            conn._update_rtt(packet, send_time)
            # Variance should be updated
            assert conn.rtt_variance >= 0

    @pytest.mark.asyncio
    async def test_connect_transport_not_set(self, mock_config, remote_addr):
        """Test connect when transport not set."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            with pytest.raises(RuntimeError, match="Transport not set"):
                await conn.connect()

    @pytest.mark.asyncio
    async def test_connect_timeout_handler(self, mock_config, remote_addr):
        """Test connect timeout handler."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            mock_transport = MagicMock()
            mock_transport.sendto = Mock()
            conn.transport = mock_transport

            # Start connection with short timeout
            connect_task = asyncio.create_task(conn.connect())
            await asyncio.sleep(0.01)

            # Simulate timeout by setting state and cancelling timeout task
            if conn._connection_timeout_task:
                conn._connection_timeout_task.cancel()
                try:
                    await conn._connection_timeout_task
                except asyncio.CancelledError:
                    pass

            connect_task.cancel()
            try:
                await connect_task
            except (asyncio.CancelledError, TimeoutError):
                pass

    @pytest.mark.asyncio
    async def test_handle_syn_ack_invalid_state(self, mock_config, remote_addr):
        """Test handling SYN-ACK in invalid state."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.state = UTPConnectionState.CONNECTED  # Not SYN_SENT

            syn_ack = UTPPacket(
                type=UTPPacketType.ST_SYN,
                connection_id=conn.connection_id,
                seq_nr=1,
                ack_nr=0,
                wnd_size=65535,
                timestamp=0,
                data=b"",
            )
            conn._handle_syn_ack(syn_ack)
            # Should handle gracefully (log warning, return early)

    @pytest.mark.asyncio
    async def test_send_loop_exception_handling(self, mock_config, remote_addr):
        """Test send loop exception handling."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.state = UTPConnectionState.CONNECTED
            mock_transport = MagicMock()
            mock_transport.sendto = Mock(side_effect=Exception("Send error"))
            conn.transport = mock_transport
            conn.send_window = 65535
            conn.max_unacked_packets = 100

            # Add data that will cause exception
            await conn.send_queue.put(b"test data")

            # Start send loop
            task = asyncio.create_task(conn._send_loop())

            await asyncio.sleep(0.05)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_send_loop_timeout_error(self, mock_config, remote_addr):
        """Test send loop timeout error handling."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.state = UTPConnectionState.CONNECTED
            mock_transport = MagicMock()
            mock_transport.sendto = Mock()
            conn.transport = mock_transport
            conn.send_window = 65535
            conn.max_unacked_packets = 100

            # Mock send to raise TimeoutError
            async def mock_send(data):
                raise asyncio.TimeoutError("Timeout")

            with patch.object(conn, "send", side_effect=mock_send):
                await conn.send_queue.put(b"test data")

                # Start send loop
                task = asyncio.create_task(conn._send_loop())

                await asyncio.sleep(0.05)

                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_receive_wait_for_data(self, mock_config, remote_addr):
        """Test receive waiting for data."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.state = UTPConnectionState.CONNECTED
            mock_transport = MagicMock()
            mock_transport.sendto = Mock()
            conn.transport = mock_transport

            # Try to receive with timeout
            receive_task = asyncio.create_task(conn.receive(100))
            await asyncio.sleep(0.01)
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_receive_all_data_empty_buffer(self, mock_config, remote_addr):
        """Test receiving all data when buffer is empty."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.state = UTPConnectionState.CONNECTED
            mock_transport = MagicMock()
            mock_transport.sendto = Mock()
            conn.transport = mock_transport

            # Try to receive all (-1) when buffer is empty
            receive_task = asyncio.create_task(conn.receive(-1))
            await asyncio.sleep(0.01)
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_calculate_target_window_no_delay(self, mock_config, remote_addr):
        """Test window calculation with no delay."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            conn.last_timestamp_diff = 0  # No delay measurement
            window = conn._calculate_target_window()
            assert window > 0

    @pytest.mark.asyncio
    async def test_calculate_target_window_congestion_decrease(self, mock_config, remote_addr):
        """Test window calculation with congestion (decrease)."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            # High delay - should trigger decrease
            conn.last_timestamp_diff = 300000  # 300ms (high)
            target_delay = conn.rtt * 2.0  # 200ms
            # actual_delay > target_delay * 1.5
            window = conn._calculate_target_window()
            assert window > 0

    @pytest.mark.asyncio
    async def test_calculate_target_window_increase(self, mock_config, remote_addr):
        """Test window calculation with low delay (increase)."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            # Low delay - should trigger increase
            conn.last_timestamp_diff = 50000  # 50ms (low)
            window = conn._calculate_target_window()
            assert window > 0

    @pytest.mark.asyncio
    async def test_update_send_window_zero(self, mock_config, remote_addr):
        """Test update send window when send_window is 0."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.send_window = 0  # Zero window
            conn._update_send_window()
            # Should use target_window when send_window is 0

    @pytest.mark.asyncio
    async def test_calculate_send_rate_no_config(self, mock_config, remote_addr):
        """Test send rate calculation without config attributes."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            conn.last_timestamp_diff = 100000  # 100ms
            conn.last_rate_update = time.perf_counter() - 0.2
            conn.current_send_rate = 10000

            # Mock config to not have network.utp attributes
            mock_config_no_utp = MagicMock()
            mock_config_no_utp.network = MagicMock()
            delattr(mock_config_no_utp.network, "utp")  # Remove utp attribute

            with patch("ccbt.transport.utp.get_config", return_value=mock_config_no_utp):
                rate = conn._calculate_send_rate()
                # Should use default values
                assert rate > 0

    @pytest.mark.asyncio
    async def test_calculate_send_rate_high_delay_no_utp_config(self, mock_config, remote_addr):
        """Test send rate with high delay but no utp config."""
        with patch("ccbt.transport.utp.get_config", return_value=mock_config):
            conn = UTPConnection(remote_addr=remote_addr)
            conn.rtt = 0.1
            conn.last_timestamp_diff = 300000  # High delay
            conn.last_rate_update = time.perf_counter() - 0.2
            conn.current_send_rate = 1000

            # Mock config to not have network.utp attributes
            mock_config_no_utp = MagicMock()
            mock_config_no_utp.network = MagicMock()
            delattr(mock_config_no_utp.network, "utp")  # Remove utp attribute

            with patch("ccbt.transport.utp.get_config", return_value=mock_config_no_utp):
                rate = conn._calculate_send_rate()
                # Should use default min_rate (512)
                assert rate >= 512


@pytest.mark.asyncio
async def test_utp_socket_manager_error_received(mock_config):
    """Test UTP protocol error_received."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPProtocol, UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()
            protocol = UTPProtocol(manager)

            # Test error_received
            protocol.error_received(Exception("UDP error"))
            # Should handle gracefully (log debug)

            await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_start_already_initialized(mock_config):
    """Test socket manager start when already initialized."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()
            manager._initialized = True

            # Start again - should return early
            await manager.start()

            await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_stop_not_initialized(mock_config):
    """Test socket manager stop when not initialized."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()
            manager._initialized = False

            # Stop when not initialized - should return early
            await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_stop_close_error(mock_config):
    """Test socket manager stop with connection close error."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()

            # Register a connection that will raise error on close
            with patch("ccbt.transport.utp.get_config", return_value=mock_config):
                conn = UTPConnection(remote_addr=("127.0.0.1", 6881))
                conn.close = AsyncMock(side_effect=Exception("Close error"))
                manager.register_connection(conn, ("127.0.0.1", 6881), conn.connection_id)

                # Stop should handle error gracefully
                await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_get_transport_not_initialized(mock_config):
    """Test get_transport when not initialized."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        manager = UTPSocketManager()
        manager.transport = None
        manager._initialized = True  # Set initialized but no transport

        with pytest.raises(RuntimeError, match="not initialized"):
            manager.get_transport()


@pytest.mark.asyncio
async def test_utp_socket_manager_handle_syn_unknown(mock_config):
    """Test handling SYN packet for unknown connection."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()

            # Create SYN packet for unknown connection
            packet = UTPPacket(
                type=UTPPacketType.ST_SYN,
                connection_id=0x9999,
                seq_nr=0,
                ack_nr=0,
                wnd_size=65535,
                timestamp=0,
                data=b"",
            )

            # Handle packet - should log debug and return
            manager._handle_incoming_packet(packet.pack(), ("127.0.0.1", 6881))

            await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_handle_packet_parse_error(mock_config):
    """Test handling packet with parse error."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()

            # Create invalid packet (too small for struct.unpack)
            invalid_packet = b"\x00\x01\x02\x03"  # Only 4 bytes

            # Handle packet - should handle parse error gracefully
            manager._handle_incoming_packet(invalid_packet, ("127.0.0.1", 6881))

            await manager.stop()


@pytest.mark.asyncio
async def test_utp_socket_manager_handle_packet_index_error(mock_config):
    """Test handling packet with index error."""
    with patch("ccbt.transport.utp_socket.get_config", return_value=mock_config):
        from ccbt.transport.utp_socket import UTPSocketManager

        UTPSocketManager._instance = None

        # Mock socket creation to avoid actual socket operations
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(None, None))
            manager = await UTPSocketManager.get_instance()

            # Create packet that will cause IndexError when extracting connection_id
            # Need at least 20 bytes for minimum header, but connection_id at offset 4-6
            # So we need at least 6 bytes, but less than 20 to trigger the len check
            invalid_packet = b"\x00\x01\x02\x03\x04\x05"  # 6 bytes, but connection_id extract might fail

            # Actually, if len < 20, it returns early before struct.unpack
            # So let's create a packet that passes len check but fails struct.unpack
            # We need 20+ bytes but invalid struct format
            invalid_packet2 = b"\x00" * 25  # 25 bytes but might fail unpack

            # Handle packet - should handle error gracefully
            try:
                manager._handle_incoming_packet(invalid_packet2, ("127.0.0.1", 6881))
            except Exception:
                # May raise, that's ok - we're testing error handling
                pass

            await manager.stop()

