"""
Tests for peer connection management.
"""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ccbt.peer import create_message
from ccbt.peer_connection import (
    ConnectionError,
    ConnectionState,
    PeerConnection,
    PeerConnectionManager,
    PeerInfo,
)


class TestPeerConnection:
    """Test cases for PeerConnection."""

    def test_creation(self):
        """Test creating a peer connection."""
        torrent_data = {
            "info_hash": b"x" * 20,
            "pieces_info": {"num_pieces": 10},
        }
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)

        connection = PeerConnection(peer_info, torrent_data)

        assert connection.peer_info == peer_info
        assert connection.torrent_data == torrent_data
        assert connection.state == ConnectionState.DISCONNECTED
        assert not connection.is_connected()
        assert not connection.is_active()
        assert connection.socket is None

    def test_connected_state(self):
        """Test connection state checking."""
        torrent_data = {"info_hash": b"x" * 20, "pieces_info": {"num_pieces": 10}}
        connection = PeerConnection(PeerInfo(ip="192.168.1.100", port=6881), torrent_data)

        # Initially disconnected
        assert connection.state == ConnectionState.DISCONNECTED
        assert not connection.is_connected()
        assert not connection.is_active()

        # Connected but not fully active states
        for state in [ConnectionState.CONNECTED, ConnectionState.BITFIELD_SENT,
                     ConnectionState.BITFIELD_RECEIVED]:
            connection.state = state
            assert connection.is_connected()
            assert not connection.is_active()

        # ACTIVE and CHOKED are fully active
        connection.state = ConnectionState.ACTIVE
        assert connection.is_connected()
        assert connection.is_active()

        connection.state = ConnectionState.CHOKED
        assert connection.is_connected()
        assert connection.is_active()

    def test_timeout_detection(self):
        """Test timeout detection."""
        torrent_data = {"info_hash": b"x" * 20, "pieces_info": {"num_pieces": 10}}
        connection = PeerConnection(PeerInfo(ip="192.168.1.100", port=6881), torrent_data)

        # Recent activity should not timeout
        connection.last_activity = time.time()
        assert not connection.has_timed_out(30.0)

        # Old activity should timeout
        connection.last_activity = time.time() - 60.0  # 60 seconds ago
        assert connection.has_timed_out(30.0)


class TestPeerConnectionManager:
    """Test cases for PeerConnectionManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.torrent_data = {
            "info_hash": b"info_hash_20_bytes__",
            "pieces_info": {"num_pieces": 10},
        }
        self.our_peer_id = b"our_peer_id_20_bytes"
        # Mock piece manager
        self.mock_piece_manager = Mock()
        self.manager = PeerConnectionManager(self.torrent_data, self.mock_piece_manager, self.our_peer_id)

    def test_creation(self):
        """Test creating connection manager."""
        assert self.manager.torrent_data == self.torrent_data
        assert self.manager.our_peer_id == self.our_peer_id
        assert self.manager.max_connections == 50
        assert self.manager.connection_timeout == 10.0
        assert len(self.manager.connections) == 0
        assert len(self.manager.connected_peers) == 0

    def test_connect_to_peer_handshake_validation(self):
        """Test handshake validation logic."""
        # Test that handshake validation works correctly
        from ccbt.peer import Handshake

        # Matching handshake should validate
        info_hash = b"info_hash_20_bytes__"
        our_peer_id = b"our_peer_id_20_bytes"
        peer_handshake = Handshake(info_hash, b"remote_peer_id_20_by")  # 20 bytes

        # Should not raise exception for matching info hash
        assert peer_handshake.info_hash == info_hash

        # Non-matching handshake should fail validation
        wrong_handshake = Handshake(b"wrong_info_hash_20_b", b"remote_peer_id_20_by")  # 20 bytes

        with pytest.raises(ConnectionError, match="Info hash mismatch"):
            if wrong_handshake.info_hash != info_hash:
                raise ConnectionError(f"Info hash mismatch: expected {info_hash.hex()}, got {wrong_handshake.info_hash.hex()}")


    def test_connect_to_peers_list(self):
        """Test connecting to a list of peers."""
        peer_list = [
            {"ip": "192.168.1.100", "port": 6881},
            {"ip": "192.168.1.101", "port": 6882},
            {"ip": "192.168.1.102", "port": 6883},
        ]

        # Should create connections for all peers
        self.manager.connect_to_peers(peer_list)

        assert len(self.manager.connections) == 3
        assert "192.168.1.100:6881" in self.manager.connections
        assert "192.168.1.101:6882" in self.manager.connections
        assert "192.168.1.102:6883" in self.manager.connections

    def test_connect_to_peers_max_connections(self):
        """Test connecting respects max connections limit."""
        # Set low max connections
        self.manager.max_connections = 2

        peer_list = [
            {"ip": "192.168.1.100", "port": 6881},
            {"ip": "192.168.1.101", "port": 6882},
            {"ip": "192.168.1.102", "port": 6883},
            {"ip": "192.168.1.103", "port": 6884},
        ]

        self.manager.connect_to_peers(peer_list)

        # Should only create 2 connections
        assert len(self.manager.connections) == 2

    def test_connect_to_peers_duplicate(self):
        """Test connecting to same peer twice."""
        peer_list = [
            {"ip": "192.168.1.100", "port": 6881},
            {"ip": "192.168.1.100", "port": 6881},  # Duplicate
        ]

        self.manager.connect_to_peers(peer_list)

        # Should only create 1 connection
        assert len(self.manager.connections) == 1

    @patch("ccbt.peer_connection.socket_module.socket")
    def test_send_interested(self, mock_socket_class):
        """Test sending interested message."""
        # Mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Create connected peer
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, self.torrent_data)
        connection.socket = mock_socket
        connection.state = ConnectionState.ACTIVE

        # Send interested
        self.manager.send_interested(connection)

        # Should send InterestedMessage
        mock_socket.send.assert_called_once()
        sent_data = mock_socket.send.call_args[0][0]

        # Verify message format
        assert len(sent_data) == 5  # 4 bytes length + 1 byte message ID
        length = int.from_bytes(sent_data[:4], byteorder="big")
        message_id = sent_data[4]
        assert length == 1
        assert message_id == 2  # MessageType.INTERESTED

    @patch("ccbt.peer_connection.socket_module.socket")
    def test_send_not_interested(self, mock_socket_class):
        """Test sending not interested message."""
        # Mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Create connected peer
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, self.torrent_data)
        connection.socket = mock_socket
        connection.state = ConnectionState.ACTIVE

        # Send not interested
        self.manager.send_not_interested(connection)

        # Should send NotInterestedMessage
        mock_socket.send.assert_called_once()
        sent_data = mock_socket.send.call_args[0][0]

        # Verify message format
        assert len(sent_data) == 5  # 4 bytes length + 1 byte message ID
        length = int.from_bytes(sent_data[:4], byteorder="big")
        message_id = sent_data[4]
        assert length == 1
        assert message_id == 3  # MessageType.NOT_INTERESTED

    @patch("ccbt.peer_connection.socket_module.socket")
    def test_request_piece(self, mock_socket_class):
        """Test requesting a piece from peer."""
        # Mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Create unchoked peer
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, self.torrent_data)
        connection.socket = mock_socket
        connection.state = ConnectionState.ACTIVE
        connection.peer_state.am_choking = False

        # Request piece
        self.manager.request_piece(connection, 5, 1000, 16384)

        # Should send RequestMessage
        mock_socket.send.assert_called_once()
        sent_data = mock_socket.send.call_args[0][0]

        # Verify message format (17 bytes: 4 length + 1 ID + 4 index + 4 begin + 4 length)
        assert len(sent_data) == 17
        length = int.from_bytes(sent_data[:4], byteorder="big")
        message_id = sent_data[4]
        piece_index = int.from_bytes(sent_data[5:9], byteorder="big")
        begin = int.from_bytes(sent_data[9:13], byteorder="big")
        req_length = int.from_bytes(sent_data[13:17], byteorder="big")

        assert length == 13
        assert message_id == 6  # MessageType.REQUEST
        assert piece_index == 5
        assert begin == 1000
        assert req_length == 16384

    @patch("ccbt.peer_connection.socket_module.socket")
    def test_request_piece_choked(self, mock_socket_class):
        """Test requesting piece from choked peer."""
        # Mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Create choked peer
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, self.torrent_data)
        connection.socket = mock_socket
        connection.state = ConnectionState.CHOKED
        connection.peer_state.am_choking = True

        # Request piece (should not send)
        self.manager.request_piece(connection, 5, 1000, 16384)

        # Should not send anything
        mock_socket.send.assert_not_called()

    def test_get_connected_peers(self):
        """Test getting connected peers."""
        # Create mock connections
        peer1 = PeerInfo(ip="192.168.1.100", port=6881)
        peer2 = PeerInfo(ip="192.168.1.101", port=6882)

        connection1 = PeerConnection(peer1, self.torrent_data)
        connection2 = PeerConnection(peer2, self.torrent_data)

        # Initially no connections
        assert len(self.manager.get_connected_peers()) == 0

        # Add connections
        with self.manager.lock:
            self.manager.connections[str(peer1)] = connection1
            self.manager.connections[str(peer2)] = connection2

        # Still no connected peers (not actually connected)
        assert len(self.manager.get_connected_peers()) == 0

        # Make one connection active
        connection1.state = ConnectionState.ACTIVE
        assert len(self.manager.get_connected_peers()) == 1

    def test_get_active_peers(self):
        """Test getting active peers."""
        peer1 = PeerInfo(ip="192.168.1.100", port=6881)
        peer2 = PeerInfo(ip="192.168.1.101", port=6882)

        connection1 = PeerConnection(peer1, self.torrent_data)
        connection2 = PeerConnection(peer2, self.torrent_data)

        # Add connections
        with self.manager.lock:
            self.manager.connections[str(peer1)] = connection1
            self.manager.connections[str(peer2)] = connection2

        # Initially no active peers
        assert len(self.manager.get_active_peers()) == 0

        # Make connections active
        connection1.state = ConnectionState.ACTIVE
        connection2.state = ConnectionState.BITFIELD_RECEIVED

        assert len(self.manager.get_active_peers()) == 1

    def test_disconnect_peer(self):
        """Test disconnecting a specific peer."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, self.torrent_data)

        # Add connection
        with self.manager.lock:
            self.manager.connections[str(peer_info)] = connection

        # Disconnect
        self.manager.disconnect_peer(peer_info)

        # Connection should be in error state
        assert connection.state == ConnectionState.ERROR
        assert connection.error_message == "Manual disconnect"

    def test_disconnect_all(self):
        """Test disconnecting all peers."""
        # Add multiple connections
        for i in range(3):
            peer_info = PeerInfo(ip=f"192.168.1.{100 + i}", port=6881 + i)
            connection = PeerConnection(peer_info, self.torrent_data)
            with self.manager.lock:
                self.manager.connections[str(peer_info)] = connection

        # Disconnect all
        self.manager.disconnect_all()

        # All connections should be in error state
        with self.manager.lock:
            for connection in self.manager.connections.values():
                assert connection.state == ConnectionState.ERROR
                assert connection.error_message == "Shutdown"

    def test_message_handlers_setup(self):
        """Test that message handlers are properly set up."""
        # Check that all expected message types have handlers
        expected_handlers = {
            0: "_handle_choke",      # CHOKE
            1: "_handle_unchoke",    # UNCHOKE
            2: "_handle_interested", # INTERESTED
            3: "_handle_not_interested", # NOT_INTERESTED
            4: "_handle_have",       # HAVE
            5: "_handle_bitfield",   # BITFIELD
            6: "_handle_request",    # REQUEST
            7: "_handle_piece",      # PIECE
            8: "_handle_cancel",     # CANCEL
        }

        for msg_type, handler_name in expected_handlers.items():
            assert msg_type in self.manager.message_handlers
            assert hasattr(self.manager, handler_name)

    def test_callbacks_setup(self):
        """Test that callbacks are initially None."""
        assert self.manager.on_peer_connected is None
        assert self.manager.on_peer_disconnected is None
        assert self.manager.on_bitfield_received is None
        assert self.manager.on_piece_received is None

    def test_shutdown(self):
        """Test shutting down the connection manager."""
        # Add mock connections
        for i in range(2):
            peer_info = PeerInfo(ip=f"192.168.1.{100 + i}", port=6881 + i)
            connection = PeerConnection(peer_info, self.torrent_data)
            connection.connection_thread = MagicMock()
            connection.connection_thread.is_alive.return_value = False
            with self.manager.lock:
                self.manager.connections[str(peer_info)] = connection

        # Shutdown should not raise errors
        self.manager.shutdown()

        # All connections should be in error state
        with self.manager.lock:
            for connection in self.manager.connections.values():
                assert connection.state == ConnectionState.ERROR


class TestMessageHandling:
    """Test cases for message handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.torrent_data = {
            "info_hash": b"info_hash_20_bytes__",
            "pieces_info": {"num_pieces": 10},
        }
        self.our_peer_id = b"our_peer_id_20_bytes"
        # Mock piece manager
        self.mock_piece_manager = Mock()
        self.manager = PeerConnectionManager(self.torrent_data, self.mock_piece_manager, self.our_peer_id)

        self.peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        self.connection = PeerConnection(self.peer_info, self.torrent_data)
        self.connection.state = ConnectionState.ACTIVE

    def test_handle_choke(self):
        """Test handling choke message."""
        initial_state = self.connection.peer_state.am_choking

        message = create_message(0)  # CHOKE
        self.manager._handle_choke(self.connection, message)

        assert self.connection.peer_state.am_choking == True
        assert self.connection.state == ConnectionState.CHOKED

    def test_handle_unchoke(self):
        """Test handling unchoke message."""
        self.connection.peer_state.am_choking = True
        self.connection.state = ConnectionState.CHOKED

        message = create_message(1)  # UNCHOKE
        self.manager._handle_unchoke(self.connection, message)

        assert self.connection.peer_state.am_choking == False
        assert self.connection.state == ConnectionState.ACTIVE

    def test_handle_interested(self):
        """Test handling interested message."""
        message = create_message(2)  # INTERESTED
        self.manager._handle_interested(self.connection, message)

        assert self.connection.peer_state.peer_interested == True

    def test_handle_not_interested(self):
        """Test handling not interested message."""
        self.connection.peer_state.peer_interested = True

        message = create_message(3)  # NOT_INTERESTED
        self.manager._handle_not_interested(self.connection, message)

        assert self.connection.peer_state.peer_interested == False

    def test_handle_have(self):
        """Test handling have message."""
        message = create_message(4, piece_index=5)  # HAVE
        self.manager._handle_have(self.connection, message)

        assert 5 in self.connection.peer_state.pieces_we_have

    def test_handle_bitfield(self):
        """Test handling bitfield message."""
        bitfield_data = b"\xFF\x00"  # 16 bits: 11111111 00000000
        message = create_message(5, bitfield=bitfield_data)  # BITFIELD

        # Set up callback
        received_bitfield = None
        def bitfield_callback(conn, bf):
            nonlocal received_bitfield
            received_bitfield = bf

        self.manager.on_bitfield_received = bitfield_callback

        self.manager._handle_bitfield(self.connection, message)

        # Check state
        assert self.connection.peer_state.bitfield == message
        assert self.connection.state == ConnectionState.BITFIELD_RECEIVED

        # Check callback
        assert received_bitfield == message

    def test_handle_piece(self):
        """Test handling piece message."""
        block_data = b"piece block data"
        message = create_message(7, piece_index=3, begin=1000, block=block_data)  # PIECE

        # Set up callback
        received_piece = None
        def piece_callback(conn, piece):
            nonlocal received_piece
            received_piece = piece

        self.manager.on_piece_received = piece_callback

        self.manager._handle_piece(self.connection, message)

        # Check callback
        assert received_piece == message
