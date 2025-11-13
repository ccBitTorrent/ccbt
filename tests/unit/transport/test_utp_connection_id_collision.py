"""Unit tests for uTP connection ID collision detection."""

import pytest

from ccbt.transport.utp_socket import UTPSocketManager


class TestConnectionIDCollision:
    """Tests for connection ID collision detection and resolution."""

    @pytest.fixture
    def socket_manager(self):
        """Create a socket manager for testing."""
        manager = UTPSocketManager()
        manager.transport = None  # Not needed for these tests
        manager._initialized = True
        return manager

    def test_generate_connection_id_unique(self, socket_manager):
        """Test connection ID generation produces unique IDs."""
        ids = set()
        for _ in range(100):
            conn_id = socket_manager._generate_connection_id()
            assert conn_id not in ids
            assert 0x0001 <= conn_id <= 0xFFFE
            ids.add(conn_id)

    def test_generate_connection_id_avoids_active(self, socket_manager):
        """Test connection ID generation avoids active IDs."""
        # Add some active IDs
        socket_manager.active_connection_ids.add(100)
        socket_manager.active_connection_ids.add(200)
        socket_manager.active_connection_ids.add(300)

        # Generate many IDs
        for _ in range(100):
            conn_id = socket_manager._generate_connection_id()
            assert conn_id not in socket_manager.active_connection_ids
            assert conn_id not in (100, 200, 300)

    def test_register_connection_adds_id(self, socket_manager):
        """Test registering connection adds ID to active set."""
        from unittest.mock import MagicMock

        conn = MagicMock()
        conn.connection_id = 12345

        socket_manager.register_connection(conn, ("127.0.0.1", 6881), 12345)

        assert 12345 in socket_manager.active_connection_ids

    def test_unregister_connection_removes_id(self, socket_manager):
        """Test unregistering connection removes ID from active set."""
        from unittest.mock import MagicMock

        conn = MagicMock()
        conn.connection_id = 12345

        socket_manager.register_connection(conn, ("127.0.0.1", 6881), 12345)
        assert 12345 in socket_manager.active_connection_ids

        socket_manager.unregister_connection(("127.0.0.1", 6881), 12345)
        assert 12345 not in socket_manager.active_connection_ids

    def test_collision_detection_same_id_different_addr(self, socket_manager):
        """Test collision detection for same ID, different address."""
        from unittest.mock import MagicMock

        # Register connection with ID 12345
        conn1 = MagicMock()
        conn1.connection_id = 12345
        socket_manager.register_connection(conn1, ("127.0.0.1", 6881), 12345)

        # Try to handle packet with same ID but different address
        data = b"\x04\x01\x00\x00\x39\x30\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        addr = ("127.0.0.2", 6882)  # Different address

        # Should detect collision and drop packet
        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)

        # Connection should not be created for different address
        key = (addr[0], addr[1], 12345)
        assert key not in socket_manager.connections

    def test_collision_detection_no_collision(self, socket_manager):
        """Test that same ID, same address is not a collision."""
        from unittest.mock import MagicMock
        from ccbt.transport.utp import UTPPacket, UTPPacketType

        # Register connection
        conn1 = MagicMock()
        conn1.connection_id = 12345
        conn1._handle_packet = MagicMock()  # Mock the packet handler
        socket_manager.register_connection(conn1, ("127.0.0.1", 6881), 12345)

        # Handle packet with same ID and same address (not a collision)
        # Create a proper packet (not SYN, so it routes to existing connection)
        data_packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=1,
            ack_nr=0,
            wnd_size=65535,
            data=b"test",
        )
        data = data_packet.pack()
        addr = ("127.0.0.1", 6881)  # Same address

        # Should route to existing connection
        socket_manager._handle_incoming_packet(data, addr, ecn_ce=False)
        
        # Verify packet was routed to connection (not dropped as collision)
        # _handle_packet is called with (packet_data: bytes, ecn_ce: bool)
        conn1._handle_packet.assert_called_once()
        # Check that it was called with the correct arguments
        # The call is: connection._handle_packet(data, ecn_ce=ecn_ce)
        # So data is positional, ecn_ce is keyword
        call_args, call_kwargs = conn1._handle_packet.call_args
        assert call_args[0] == data  # First positional arg should be the packet data
        assert call_kwargs.get('ecn_ce') == False  # ecn_ce should be in kwargs

        # Connection should exist and packet should be handled
        key = (addr[0], addr[1], 12345)
        assert key in socket_manager.connections

    def test_get_active_connection_ids(self, socket_manager):
        """Test getting active connection IDs."""
        from unittest.mock import MagicMock

        # Register some connections
        conn1 = MagicMock()
        conn1.connection_id = 100
        socket_manager.register_connection(conn1, ("127.0.0.1", 6881), 100)

        conn2 = MagicMock()
        conn2.connection_id = 200
        socket_manager.register_connection(conn2, ("127.0.0.1", 6882), 200)

        # Get active IDs
        active_ids = socket_manager.get_active_connection_ids()

        assert 100 in active_ids
        assert 200 in active_ids
        assert len(active_ids) == 2

    def test_connection_id_generation_max_attempts(self, socket_manager):
        """Test connection ID generation with many active IDs."""
        # Fill up most of the ID space
        for i in range(0x0001, 0xFFFE):
            socket_manager.active_connection_ids.add(i)

        # Should raise error after max attempts
        with pytest.raises(RuntimeError, match="Could not generate unique connection ID"):
            socket_manager._generate_connection_id()

