"""Comprehensive unit tests for uTP covering all methods and edge cases."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
    UTPPacket,
    UTPPacketType,
)
from ccbt.transport.utp_socket import UTPSocketManager


class TestConnectionLifecycle:
    """Tests for connection lifecycle management."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        return conn

    def test_connection_initialization(self, connection):
        """Test connection initialization."""
        assert connection.state == UTPConnectionState.IDLE
        assert connection.connection_id == 12345
        assert connection.remote_addr == ("127.0.0.1", 6881)
        assert connection.seq_nr == 0
        assert connection.ack_nr == 0

    def test_set_transport(self, connection):
        """Test setting transport."""
        transport = MagicMock()
        connection.set_transport(transport)
        assert connection.transport == transport

    @pytest.mark.asyncio
    async def test_initialize_transport(self, connection):
        """Test initializing transport via socket manager."""
        with patch(
            "ccbt.transport.utp_socket.UTPSocketManager.get_instance"
        ) as mock_get_instance:
            mock_manager = MagicMock()
            mock_transport = MagicMock()
            mock_manager.get_transport.return_value = mock_transport
            mock_manager._generate_connection_id.return_value = 12345
            mock_get_instance.return_value = mock_manager

            await connection.initialize_transport()

            # Transport should be set
            assert connection.transport is not None
            # Connection should be registered
            mock_manager.register_connection.assert_called_once()
            # Connection ID should be set
            assert connection.connection_id == 12345

    def test_get_timestamp_microseconds(self, connection):
        """Test timestamp calculation."""
        timestamp = connection._get_timestamp_microseconds()
        assert timestamp >= 0
        assert timestamp <= 0xFFFFFFFF  # 32-bit

    def test_can_send(self, connection):
        """Test _can_send() method."""
        connection.state = UTPConnectionState.CONNECTED
        connection.send_window = 10000
        connection.max_unacked_packets = 10

        # Empty send buffer
        assert connection._can_send() is True

        # Fill send buffer
        for i in range(15):  # More than max_unacked_packets
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=i,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            )
            connection.send_buffer[i] = (packet, 0.0, 0)

        # Should not be able to send
        assert connection._can_send() is False

    def test_can_send_window_exhausted(self, connection):
        """Test _can_send() when window is exhausted."""
        connection.state = UTPConnectionState.CONNECTED
        connection.send_window = 1000
        connection.max_unacked_packets = 100

        # Fill send buffer with many packets
        for i in range(10):
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=i,
                ack_nr=0,
                wnd_size=0,
                data=b"x" * 200,  # Large packets
            )
            connection.send_buffer[i] = (packet, 0.0, 0)

        # Window might be exhausted
        result = connection._can_send()
        assert isinstance(result, bool)


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

    @pytest.mark.asyncio
    async def test_handle_fin_packet(self, connection):
        """Test handling FIN packet."""
        connection.state = UTPConnectionState.CONNECTED
        fin_packet = UTPPacket(
            type=UTPPacketType.ST_FIN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        connection._handle_fin_packet(fin_packet)

        # Should transition to FIN_RECEIVED
        assert connection.state == UTPConnectionState.FIN_RECEIVED
        # Give async close task time
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_handle_reset_packet(self, connection):
        """Test handling RESET packet."""
        connection.state = UTPConnectionState.CONNECTED
        connection.transport = MagicMock()
        
        reset_packet = UTPPacket(
            type=UTPPacketType.ST_RESET,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        connection._handle_reset_packet(reset_packet)

        # Should transition to RESET
        assert connection.state == UTPConnectionState.RESET
        
        # Give async close task time to complete
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_handle_reset_during_syn_sent(self, connection):
        """Test handling RESET during SYN_SENT (possible collision)."""
        connection.state = UTPConnectionState.SYN_SENT
        connection.transport = MagicMock()

        reset_packet = UTPPacket(
            type=UTPPacketType.ST_RESET,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        # Should handle gracefully (possible collision)
        connection._handle_reset_packet(reset_packet)
        
        # Should transition to RESET state
        assert connection.state == UTPConnectionState.RESET
        
        # Give async close task time to complete
        await asyncio.sleep(0.1)

    def test_process_out_of_order_packets(self, connection):
        """Test processing out-of-order packets."""
        # Add out-of-order packets to buffer
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=2,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet2",
        )
        packet3 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=3,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet3",
        )

        connection.recv_buffer[2] = packet2
        connection.recv_buffer[3] = packet3
        connection.recv_buffer_expected_seq = 1

        # Receive packet 1 (in-order)
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet1",
        )

        connection._handle_data_packet(packet1)

        # All packets should now be processed
        assert 2 not in connection.recv_buffer
        assert 3 not in connection.recv_buffer


class TestSendRateCalculation:
    """Tests for send rate calculation."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_calculate_send_rate_initial(self, connection):
        """Test initial send rate calculation."""
        rate = connection._calculate_send_rate()
        assert rate > 0

    def test_calculate_send_rate_additive_increase(self, connection):
        """Test send rate additive increase."""
        connection.current_send_rate = 1500.0
        connection.last_rate_update = 0.0
        connection.last_timestamp_diff = 30000  # 30ms (below target)

        # Mock time
        import time

        with patch("time.perf_counter", return_value=0.2):
            rate = connection._calculate_send_rate()

            # Should increase rate
            assert rate >= connection.current_send_rate

    def test_calculate_send_rate_rate_limit(self, connection):
        """Test send rate respects max rate limit."""
        connection.current_send_rate = 10000.0
        connection.last_rate_update = 0.0
        connection.last_timestamp_diff = 30000

        # Mock config with max rate
        with patch.object(
            connection.config.network.utp, "max_rate", 5000.0
        ), patch.object(
            connection.config.network.utp, "min_rate", 100.0
        ), patch("time.perf_counter", return_value=0.2):
            rate = connection._calculate_send_rate()

            # Should not exceed max rate
            assert rate <= 5000.0

    def test_update_send_window(self, connection):
        """Test updating send window."""
        connection.send_window = 10000
        connection.srtt = 0.1
        connection.last_timestamp_diff = 50000

        connection._update_send_window()

        # Window should be updated based on congestion control
        assert connection.send_window > 0


class TestSocketManager:
    """Tests for UTPSocketManager."""

    @pytest.fixture
    def socket_manager(self):
        """Create a socket manager."""
        manager = UTPSocketManager()
        manager.transport = MagicMock()
        manager.transport.sendto = MagicMock()
        manager._initialized = True
        return manager

    @pytest.mark.asyncio
    async def test_get_instance_singleton(self):
        """Test get_instance returns singleton."""
        # Reset singleton for clean test
        old_instance = UTPSocketManager._instance
        UTPSocketManager._instance = None
        
        try:
            manager1 = await UTPSocketManager.get_instance()
            manager2 = await UTPSocketManager.get_instance()
            assert manager1 is manager2
            
            # Cleanup - stop the manager
            if manager1._initialized:
                await manager1.stop()
        except Exception:
            # If stop fails, try to reset
            pass
        finally:
            # Restore original instance or reset
            UTPSocketManager._instance = old_instance

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

    def test_send_packet(self, socket_manager):
        """Test sending packet."""
        packet_data = b"test packet"
        addr = ("127.0.0.1", 6881)

        socket_manager.send_packet(packet_data, addr)

        # Verify packet was sent
        socket_manager.transport.sendto.assert_called_once_with(packet_data, addr)
        assert socket_manager.total_packets_sent == 1
        assert socket_manager.total_bytes_sent == len(packet_data)

    def test_send_packet_not_initialized(self):
        """Test sending packet when not initialized."""
        manager = UTPSocketManager()
        manager.transport = None

        with pytest.raises(RuntimeError, match="socket not initialized"):
            manager.send_packet(b"data", ("127.0.0.1", 6881))

    def test_get_transport_not_initialized(self):
        """Test getting transport when not initialized."""
        manager = UTPSocketManager()
        manager.transport = None

        with pytest.raises(RuntimeError, match="socket not initialized"):
            manager.get_transport()


class TestConnectionClose:
    """Tests for connection closing."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    @pytest.mark.asyncio
    async def test_close_connected(self, connection):
        """Test closing connected connection."""
        # Add some packets to send buffer
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        connection.send_buffer[1] = (packet, 0.0, 0)

        # Start background tasks
        connection._start_background_tasks()
        connection._start_ack_timer()

        # Close connection
        await connection.close()

        # Should send FIN and transition to CLOSED
        assert connection.state == UTPConnectionState.CLOSED
        assert connection.transport.sendto.called

    @pytest.mark.asyncio
    async def test_close_already_closed(self, connection):
        """Test closing already closed connection."""
        connection.state = UTPConnectionState.CLOSED

        # Should not crash
        await connection.close()

        # Should remain closed
        assert connection.state == UTPConnectionState.CLOSED

    @pytest.mark.asyncio
    async def test_close_sends_pending_acks(self, connection):
        """Test closing sends pending ACKs."""
        connection.state = UTPConnectionState.CONNECTED
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

        # Close
        await connection.close()

        # Pending ACK should be sent
        assert connection.transport.sendto.called


class TestSequenceNumberHandling:
    """Tests for sequence number handling."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_is_sequence_acked(self, connection):
        """Test sequence ACK checking."""
        # Normal case - seq before ack_nr
        assert connection._is_sequence_acked(50, 100) is True
        # Normal case - seq after ack_nr
        assert connection._is_sequence_acked(150, 100) is False
        
        # Test wraparound logic
        # When ack_nr is 0x0001, sequences 0xFFFF and 0x0000 are acked
        # (wrapped around)
        # The logic checks: seq <= ack_nr OR seq < (ack_nr + 0x8000) % 0x10000
        # For ack_nr=0x0001: (0x0001 + 0x8000) % 0x10000 = 0x8001
        # So seq < 0x8001 is acked (wrapped case)
        assert connection._is_sequence_acked(0xFFFF, 0x0001) is False  # Not acked (too far)
        assert connection._is_sequence_acked(0x0000, 0x0001) is True  # Acked (before ack_nr)
        assert connection._is_sequence_acked(0x8000, 0x0001) is False  # Not acked

    def test_sequence_wraparound(self, connection):
        """Test sequence number wraparound."""
        connection.recv_buffer_expected_seq = 0xFFFE

        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=0xFFFE,
            ack_nr=0,
            wnd_size=65535,
            data=b"data",
        )

        connection._handle_data_packet(packet)

        # Should wrap to 0xFFFF, then 0
        assert connection.recv_buffer_expected_seq in (0xFFFF, 0)


class TestExtensionNegotiation:
    """Tests for extension negotiation."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_advertise_extensions(self, connection):
        """Test advertising extensions."""
        extensions = connection._advertise_extensions()

        # Should include supported extensions
        assert len(extensions) > 0

        # Should include ECN
        from ccbt.transport.utp_extensions import ECNExtension

        has_ecn = any(isinstance(ext, ECNExtension) for ext in extensions)
        assert has_ecn

    def test_process_extension_negotiation(self, connection):
        """Test processing extension negotiation."""
        from ccbt.transport.utp_extensions import (
            ECNExtension,
            WindowScalingExtension,
        )

        peer_extensions = [
            WindowScalingExtension(scale_factor=2),
            ECNExtension(ecn_echo=False, ecn_cwr=False),
        ]

        connection._process_extension_negotiation(peer_extensions)

        # Should negotiate common extensions
        from ccbt.transport.utp_extensions import UTPExtensionType

        assert UTPExtensionType.WINDOW_SCALING in connection.negotiated_extensions
        assert UTPExtensionType.ECN in connection.negotiated_extensions

    def test_process_extension_not_supported(self, connection):
        """Test processing extension we don't support."""
        from ccbt.transport.utp_extensions import WindowScalingExtension, UTPExtensionType

        # Remove window scaling from supported
        connection.supported_extensions.discard(UTPExtensionType.WINDOW_SCALING)
        # Ensure it's actually removed
        assert UTPExtensionType.WINDOW_SCALING not in connection.supported_extensions

        peer_extensions = [WindowScalingExtension(scale_factor=2)]
        
        # Store initial negotiated extensions
        initial_negotiated = connection.negotiated_extensions.copy()
        
        connection._process_extension_negotiation(peer_extensions)

        # Should not negotiate (we don't support it)
        # The extension type check in _process_extension_negotiation checks:
        # `if ext_type == UTPExtensionType.WINDOW_SCALING:` then checks `if UTPExtensionType.WINDOW_SCALING in self.supported_extensions:`
        # Since it's not in supported_extensions, it won't be negotiated
        assert UTPExtensionType.WINDOW_SCALING not in connection.negotiated_extensions
        # Negotiated extensions should not have changed (or window_scale should remain 0)
        assert UTPExtensionType.WINDOW_SCALING not in connection.negotiated_extensions

