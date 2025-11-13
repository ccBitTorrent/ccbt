"""Unit tests for uTP passive connection handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType
from ccbt.transport.utp_socket import UTPSocketManager


class TestPassiveConnectionHandling:
    """Tests for passive connection acceptance."""

    @pytest.fixture
    def socket_manager(self):
        """Create a socket manager for testing."""
        manager = UTPSocketManager()
        # Mock transport
        manager.transport = MagicMock()
        manager.transport.sendto = MagicMock()
        manager._initialized = True
        yield manager
        # Cleanup - no need to await stop() for mock

    @pytest.fixture
    def mock_transport(self):
        """Create a mock UDP transport."""
        transport = MagicMock()
        transport.sendto = MagicMock()
        return transport

    @pytest.mark.asyncio
    async def test_handle_incoming_syn_packet(self, socket_manager):
        """Test handling incoming SYN packet."""
        # Create a SYN packet
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,  # Peer's connection ID
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            timestamp=1000000,
        )

        addr = ("127.0.0.1", 6881)
        packet_data = syn_packet.pack()

        # Handle incoming SYN
        await socket_manager._handle_incoming_syn(packet_data, addr, 12345)

        # Verify connection was created
        # Check that a connection was registered (local connection ID would be different)
        assert len(socket_manager.connections) > 0 or len(socket_manager.pending_connections) > 0

    def test_generate_connection_id_unique(self, socket_manager):
        """Test connection ID generation produces unique IDs."""
        ids = set()
        for _ in range(100):
            conn_id = socket_manager._generate_connection_id()
            assert conn_id not in ids
            assert 0x0001 <= conn_id <= 0xFFFE
            ids.add(conn_id)

    def test_connection_id_collision_detection(self, socket_manager):
        """Test connection ID collision detection."""
        # Register a connection with a specific ID
        conn1 = MagicMock()
        conn1.connection_id = 12345
        socket_manager.register_connection(conn1, ("127.0.0.1", 6881), 12345)

        # Try to create another connection with same ID but different address
        # This should trigger collision detection
        # Create a proper SYN packet
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,  # Same ID as existing connection
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )
        data = syn_packet.pack()
        addr = ("127.0.0.2", 6882)  # Different address

        # Should detect collision and drop packet
        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)
        # Connection should not be created for different address with same ID
        # (collision detection logs warning and drops packet)

    def test_handle_syn_method(self, mock_transport):
        """Test UTPConnection._handle_syn() method."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        conn.set_transport(mock_transport)
        conn.state = UTPConnectionState.IDLE

        # Create incoming SYN packet
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,  # Peer's connection ID
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            timestamp=1000000,
        )

        # Handle SYN
        conn._handle_syn(syn_packet)

        # Verify state transition
        assert conn.state == UTPConnectionState.SYN_RECEIVED
        assert conn.remote_connection_id == 12345
        assert conn.send_window == 65535

        # Verify SYN-ACK was sent
        assert mock_transport.sendto.called

    def test_send_syn_ack(self, mock_transport):
        """Test sending SYN-ACK response."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        conn.set_transport(mock_transport)
        conn.state = UTPConnectionState.SYN_RECEIVED

        # Send SYN-ACK
        conn._send_syn_ack(peer_seq_nr=0)

        # Verify packet was sent
        assert mock_transport.sendto.called
        call_args = mock_transport.sendto.call_args
        packet_data = call_args[0][0]
        addr = call_args[0][1]

        # Verify address
        assert addr == ("127.0.0.1", 6881)

        # Unpack and verify packet
        packet = UTPPacket.unpack(packet_data)
        assert packet.type == UTPPacketType.ST_SYN
        assert packet.connection_id == 54321
        assert packet.ack_nr == 0  # ACK peer's SYN

    @pytest.mark.asyncio
    async def test_three_way_handshake_passive(self, mock_transport):
        """Test complete three-way handshake for passive connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        conn.set_transport(mock_transport)
        conn.state = UTPConnectionState.SYN_RECEIVED

        # Step 1: Received SYN (already handled in _handle_syn)
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )
        conn._handle_syn(syn_packet)

        # Step 2: Send SYN-ACK (already done in _handle_syn)
        # Verify SYN-ACK was sent
        assert mock_transport.sendto.called
        mock_transport.sendto.reset_mock()

        # Step 3: Receive ACK for our SYN-ACK
        # For passive connection, we need to set seq_nr to 0 (our SYN-ACK seq)
        conn.seq_nr = 0  # Our SYN-ACK was sent with seq_nr=0
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=54321,
            seq_nr=1,
            ack_nr=0,  # ACK our SYN (seq_nr=0)
            wnd_size=65535,
        )

        conn._handle_state_packet(ack_packet)

        # Verify connection is now CONNECTED
        assert conn.state == UTPConnectionState.CONNECTED
        
        # Cleanup
        await conn.close()

    def test_handle_syn_invalid_state(self, mock_transport):
        """Test handling SYN in invalid state."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        conn.set_transport(mock_transport)
        conn.state = UTPConnectionState.CONNECTED  # Invalid state

        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )

        # Should not crash, but log warning
        conn._handle_syn(syn_packet)
        # State should remain CONNECTED
        assert conn.state == UTPConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_complete_handshake_method(self, mock_transport):
        """Test _complete_handshake() method."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=54321)
        conn.set_transport(mock_transport)
        conn.state = UTPConnectionState.SYN_RECEIVED

        # Complete handshake (starts background tasks which need event loop)
        conn._complete_handshake()

        # Verify state transition
        assert conn.state == UTPConnectionState.CONNECTED
        assert conn.seq_nr == 1  # Next packet seq_nr
        
        # Cleanup background tasks
        await conn.close()

    @pytest.mark.asyncio
    async def test_on_incoming_connection_callback(self, socket_manager):
        """Test on_incoming_connection callback."""
        callback_called = False
        callback_conn = None
        callback_addr = None

        def callback(conn, addr):
            nonlocal callback_called, callback_conn, callback_addr
            callback_called = True
            callback_conn = conn
            callback_addr = addr

        socket_manager.on_incoming_connection = callback

        # Create SYN packet
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
        )
        addr = ("127.0.0.1", 6881)
        packet_data = syn_packet.pack()

        # Handle incoming SYN
        await socket_manager._handle_incoming_syn(packet_data, addr, 12345)

        # Verify callback was called
        assert callback_called
        assert callback_conn is not None
        assert callback_addr == addr

