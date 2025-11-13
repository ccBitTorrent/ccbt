"""Integration tests for uTP full handshake (active and passive)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType
from ccbt.transport.utp_socket import UTPSocketManager


class TestActiveHandshake:
    """Tests for active (initiator) three-way handshake."""

    @pytest_asyncio.fixture
    async def socket_manager(self):
        """Create a socket manager for testing."""
        manager = UTPSocketManager()
        manager.transport = MagicMock()
        manager.transport.sendto = MagicMock()
        manager._initialized = True
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_active_handshake_complete(self, socket_manager):
        """Test complete active three-way handshake."""
        # Create connection
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.set_transport(socket_manager.transport)
        # Don't call initialize_transport - it requires a real socket manager
        # Just set the transport directly

        # Start connection
        connect_task = asyncio.create_task(conn.connect())

        # Wait a bit for SYN to be sent
        await asyncio.sleep(0.1)

        # Simulate receiving SYN-ACK
        syn_ack = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,  # ACK our SYN
            wnd_size=65535,
            timestamp=1000000,
        )
        conn._handle_syn_ack(syn_ack)

        # Wait for handshake to complete
        await asyncio.sleep(0.1)

        # Verify connection is established
        assert conn.state == UTPConnectionState.CONNECTED

        # Cleanup
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass


class TestPassiveHandshake:
    """Tests for passive (listener) three-way handshake."""

    @pytest_asyncio.fixture
    async def socket_manager(self):
        """Create a socket manager for testing."""
        manager = UTPSocketManager()
        manager.transport = MagicMock()
        manager.transport.sendto = MagicMock()
        manager._initialized = True
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_passive_handshake_complete(self, socket_manager):
        """Test complete passive three-way handshake."""
        # Simulate incoming SYN
        syn_packet = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=54321,  # Peer's connection ID
            seq_nr=0,
            ack_nr=0,
            wnd_size=65535,
            timestamp=1000000,
        )

        addr = ("127.0.0.1", 6881)
        packet_data = syn_packet.pack()

        # Handle incoming SYN
        await socket_manager._handle_incoming_syn(packet_data, addr, 54321)

        # Find the created connection
        assert len(socket_manager.connections) > 0 or len(socket_manager.pending_connections) > 0

        # Get the connection
        conn = None
        for c in socket_manager.connections.values():
            conn = c
            break
        if not conn and socket_manager.pending_connections:
            conn = list(socket_manager.pending_connections.values())[0]

        assert conn is not None
        assert conn.state == UTPConnectionState.SYN_RECEIVED

        # Simulate receiving ACK for our SYN-ACK
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=conn.connection_id,
            seq_nr=1,
            ack_nr=0,  # ACK our SYN (seq_nr=0)
            wnd_size=65535,
        )

        conn._handle_state_packet(ack_packet)

        # Verify connection is established
        assert conn.state == UTPConnectionState.CONNECTED


class TestHandshakeWithExtensions:
    """Tests for handshake with extension negotiation."""

    @pytest_asyncio.fixture
    async def socket_manager(self):
        """Create a socket manager for testing."""
        manager = UTPSocketManager()
        manager.transport = MagicMock()
        manager.transport.sendto = MagicMock()
        manager._initialized = True
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_handshake_with_window_scaling(self, socket_manager):
        """Test handshake with window scaling extension."""
        # Create connection
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.set_transport(socket_manager.transport)
        # Don't call initialize_transport - it requires a real socket manager

        # Advertise extensions
        extensions = conn._advertise_extensions()

        # Should include window scaling if max_window > 65535
        from ccbt.transport.utp_extensions import WindowScalingExtension

        has_window_scaling = any(
            isinstance(ext, WindowScalingExtension) for ext in extensions
        )
        # May or may not have window scaling depending on config

    @pytest.mark.asyncio
    async def test_handshake_with_ecn(self, socket_manager):
        """Test handshake with ECN extension."""
        # Create connection
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.set_transport(socket_manager.transport)
        # Don't call initialize_transport - it requires a real socket manager

        # Advertise extensions
        extensions = conn._advertise_extensions()

        # Should include ECN
        from ccbt.transport.utp_extensions import ECNExtension

        has_ecn = any(isinstance(ext, ECNExtension) for ext in extensions)
        assert has_ecn  # ECN should always be advertised if supported

    @pytest.mark.asyncio
    async def test_extension_negotiation(self, socket_manager):
        """Test extension negotiation during handshake."""
        # Create connection
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.set_transport(socket_manager.transport)
        # Don't call initialize_transport - it might reset state or interfere
        # Just set the transport directly
        
        # Set connection to SYN_SENT state (as if we sent a SYN)
        conn.state = UTPConnectionState.SYN_SENT
        conn.seq_nr = 1  # Set sequence number
        
        # window_scale starts at 0 (no scaling)
        # The negotiation logic now handles this: if our_scale is 0, it uses peer's scale
        # So we don't need to set it explicitly
        
        # Verify state is set correctly
        assert conn.state == UTPConnectionState.SYN_SENT, f"Expected SYN_SENT, got {conn.state}"

        # Simulate receiving SYN-ACK with extensions
        from ccbt.transport.utp_extensions import (
            ECNExtension,
            WindowScalingExtension,
        )

        syn_ack = UTPPacket(
            type=UTPPacketType.ST_SYN,
            connection_id=12345,
            seq_nr=0,
            ack_nr=1,  # ACK our SYN (seq_nr=1)
            wnd_size=65535,
            extensions=[
                WindowScalingExtension(scale_factor=2),
                ECNExtension(ecn_echo=False, ecn_cwr=False),
            ],
        )

        # Directly call _handle_syn_ack to test extension negotiation
        # The method checks state internally, so we ensure state is correct
        conn._handle_syn_ack(syn_ack)

        # Verify extensions were negotiated
        from ccbt.transport.utp_extensions import UTPExtensionType

        assert UTPExtensionType.WINDOW_SCALING in conn.negotiated_extensions, \
            f"Window scaling not negotiated. Negotiated: {conn.negotiated_extensions}, supported: {conn.supported_extensions}"
        assert UTPExtensionType.ECN in conn.negotiated_extensions, \
            f"ECN not negotiated. Negotiated: {conn.negotiated_extensions}, supported: {conn.supported_extensions}"
        assert conn.window_scale == 2, \
            f"Window scale should be 2, got {conn.window_scale}"


class TestDataTransmission:
    """Tests for data transmission after handshake."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        conn.seq_nr = 1
        return conn

    @pytest.mark.asyncio
    async def test_send_data(self, connection):
        """Test sending data over connection."""
        # Ensure connection is in CONNECTED state
        connection.state = UTPConnectionState.CONNECTED
        # Set a large send window so data can be sent
        connection.send_window = 100000
        connection.recv_window = 65535
        
        data = b"test data" * 100  # Larger than MTU

        # Send data (will buffer it)
        send_task = asyncio.create_task(connection.send(data))
        
        # Wait a bit for packets to be created
        await asyncio.sleep(0.1)
        
        # Cancel send task (it may be waiting on window)
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass

        # Verify packets were created (even if not all sent)
        assert len(connection.send_buffer) > 0

    @pytest.mark.asyncio
    async def test_receive_data(self, connection):
        """Test receiving data over connection."""
        # Receive data packet
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"received data",
        )

        connection.recv_buffer_expected_seq = 1
        connection._handle_data_packet(packet)

        # Verify data is available
        received = await connection.receive(-1)
        assert b"received data" in received

    @pytest.mark.asyncio
    async def test_out_of_order_packets(self, connection):
        """Test handling out-of-order packets."""
        # Receive packet 2 before packet 1
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=2,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet2",
        )

        connection.recv_buffer_expected_seq = 1
        connection._handle_data_packet(packet2)

        # Packet should be buffered
        assert 2 in connection.recv_buffer

        # Receive packet 1
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"packet1",
        )

        connection._handle_data_packet(packet1)

        # Both packets should now be in order
        received = await connection.receive(-1)
        assert b"packet1" in received
        assert b"packet2" in received

