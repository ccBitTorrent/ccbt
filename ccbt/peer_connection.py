"""Peer connection management for BitTorrent client.

This module handles establishing TCP connections to peers, exchanging handshakes,
managing bitfields, and coordinating peer communication.
"""

import logging
import select
import socket as socket_module
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .peer import (
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    HaveMessage,
    InterestedMessage,
    KeepAliveMessage,
    MessageDecoder,
    MessageType,
    NotInterestedMessage,
    PeerInfo,
    PeerMessage,
    PeerState,
    PieceMessage,
    RequestMessage,
    UnchokeMessage,
)


class ConnectionState(Enum):
    """States of a peer connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKE_SENT = "handshake_sent"
    HANDSHAKE_RECEIVED = "handshake_received"
    CONNECTED = "connected"
    BITFIELD_SENT = "bitfield_sent"
    BITFIELD_RECEIVED = "bitfield_received"
    ACTIVE = "active"
    CHOKED = "choked"
    ERROR = "error"


class ConnectionError(Exception):
    """Exception raised when peer connection fails."""


@dataclass
class PeerConnection:
    """Represents a connection to a single peer."""

    peer_info: PeerInfo
    torrent_data: Dict[str, Any]
    socket: Optional[socket_module.socket] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    peer_state: PeerState = field(default_factory=PeerState)
    message_decoder: MessageDecoder = field(default_factory=MessageDecoder)
    last_activity: float = field(default_factory=time.time)
    connection_thread: Optional[threading.Thread] = None
    error_message: Optional[str] = None

    def __str__(self):
        return f"PeerConnection({self.peer_info}, state={self.state.value})"

    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.state in [ConnectionState.CONNECTED, ConnectionState.BITFIELD_SENT,
                            ConnectionState.BITFIELD_RECEIVED, ConnectionState.ACTIVE,
                            ConnectionState.CHOKED]

    def is_active(self) -> bool:
        """Check if connection is fully active (handshake and bitfield exchanged)."""
        return self.state in [ConnectionState.ACTIVE, ConnectionState.CHOKED]

    def has_timed_out(self, timeout: float = 30.0) -> bool:
        """Check if connection has timed out due to inactivity."""
        return time.time() - self.last_activity > timeout


class PeerConnectionManager:
    """Manages connections to multiple peers."""

    def __init__(self, torrent_data: Dict[str, Any], piece_manager: Any,
                 peer_id: Optional[bytes] = None, max_connections: int = 50, connection_timeout: float = 10.0):
        """Initialize peer connection manager.

        Args:
            torrent_data: Parsed torrent data
            piece_manager: Piece manager instance for reads/bitfield
            peer_id: Our peer ID (20 bytes). If None, a default is generated
            max_connections: Maximum number of concurrent connections
            connection_timeout: Timeout for establishing connections
        """
        self.torrent_data = torrent_data
        self.piece_manager = piece_manager
        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout

        # Connection management
        self.connections: Dict[str, PeerConnection] = {}
        self.connected_peers: Set[str] = set()
        self.lock = threading.Lock()

        # Callbacks
        self.on_peer_connected: Optional[Callable[[PeerConnection], None]] = None
        self.on_peer_disconnected: Optional[Callable[[PeerConnection], None]] = None
        self.on_bitfield_received: Optional[Callable[[PeerConnection, BitfieldMessage], None]] = None
        self.on_piece_received: Optional[Callable[[PeerConnection, PieceMessage], None]] = None

        # Message handlers
        self.message_handlers: Dict[MessageType, Callable[[PeerConnection, PeerMessage], None]] = {
            MessageType.CHOKE: self._handle_choke,
            MessageType.UNCHOKE: self._handle_unchoke,
            MessageType.INTERESTED: self._handle_interested,
            MessageType.NOT_INTERESTED: self._handle_not_interested,
            MessageType.HAVE: self._handle_have,
            MessageType.BITFIELD: self._handle_bitfield,
            MessageType.REQUEST: self._handle_request,
            MessageType.PIECE: self._handle_piece,
            MessageType.CANCEL: self._handle_cancel,
        }

        # Logging
        self.logger = logging.getLogger(__name__)

        # Upload control
        self.max_upload_slots: int = 4
        self.optimistic_unchoke_interval: float = 30.0

    def connect_to_peers(self, peer_list: List[Dict[str, Any]]) -> None:
        """Connect to a list of peers.

        Args:
            peer_list: List of peer dictionaries from tracker response
        """
        with self.lock:
            # Limit connections to max_connections
            available_slots = self.max_connections - len(self.connections)
            if available_slots <= 0:
                return

            # Take only the peers we can handle
            peers_to_connect = peer_list[:available_slots]

        # Connect to peers concurrently
        for peer_data in peers_to_connect:
            peer_info = PeerInfo(ip=peer_data["ip"], port=peer_data["port"])

            # Skip if already connected
            if str(peer_info) in self.connections:
                continue

            # Create connection and start thread
            connection = PeerConnection(peer_info, self.torrent_data)
            with self.lock:
                self.connections[str(peer_info)] = connection

            thread = threading.Thread(target=self._connect_to_peer, args=(connection,))
            thread.daemon = True
            connection.connection_thread = thread
            thread.start()

            self.logger.info(f"Started connection thread for peer {peer_info}")

    def _connect_to_peer(self, connection: PeerConnection) -> None:
        """Connect to a single peer (runs in thread)."""
        try:
            self.logger.info(f"Connecting to peer {connection.peer_info}")
            connection.state = ConnectionState.CONNECTING

            # Create socket
            sock = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_STREAM)
            sock.settimeout(self.connection_timeout)

            # Connect to peer
            sock.connect((connection.peer_info.ip, connection.peer_info.port))
            connection.socket = sock
            connection.state = ConnectionState.HANDSHAKE_SENT
            connection.last_activity = time.time()

            # Send handshake
            info_hash = self.torrent_data["info_hash"]
            handshake = Handshake(info_hash, self.our_peer_id)
            handshake_data = handshake.encode()
            sock.send(handshake_data)

            self.logger.debug(f"Sent handshake to {connection.peer_info}")

            # Receive and validate handshake
            peer_handshake_data = self._receive_exactly(sock, 68)
            if len(peer_handshake_data) != 68:
                raise ConnectionError(f"Invalid handshake length: {len(peer_handshake_data)}")

            peer_handshake = Handshake.decode(peer_handshake_data)
            connection.peer_info.peer_id = peer_handshake.peer_id
            connection.state = ConnectionState.HANDSHAKE_RECEIVED
            connection.last_activity = time.time()

            # Validate handshake
            if peer_handshake.info_hash != info_hash:
                raise ConnectionError(f"Info hash mismatch: expected {info_hash.hex()}, got {peer_handshake.info_hash.hex()}")

            self.logger.info(f"Handshake successful with peer {connection.peer_info}")

            # Send our bitfield and unchoke to allow requests
            self._send_bitfield(connection)
            self._send_unchoke(connection)

            # Start message handling loop
            self._handle_peer_messages(connection)

        except Exception as e:
            self.logger.error(f"Connection failed to peer {connection.peer_info}: {e}")
            self._handle_connection_error(connection, str(e))

    def _receive_exactly(self, sock: socket_module.socket, num_bytes: int) -> bytes:
        """Receive exactly num_bytes from socket."""
        data = b""
        while len(data) < num_bytes:
            chunk = sock.recv(num_bytes - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            data += chunk
        return data

    def _send_bitfield(self, connection: PeerConnection) -> None:
        """Send our bitfield to the peer."""
        if connection.socket is None:
            return

        # Build bitfield from verified pieces
        num_pieces = self.torrent_data["pieces_info"]["num_pieces"]
        bitfield_bytes = bytearray((num_pieces + 7) // 8)
        try:
            verified = set(self.piece_manager.verified_pieces)
        except Exception:
            verified = set()
        for idx in verified:
            if 0 <= idx < num_pieces:
                byte_index = idx // 8
                bit_index = idx % 8
                bitfield_bytes[byte_index] |= (1 << (7 - bit_index))
        bitfield_data = bytes(bitfield_bytes)

        if bitfield_data:
            bitfield_message = BitfieldMessage(bitfield_data)
            self._send_message(connection, bitfield_message)
            connection.state = ConnectionState.BITFIELD_SENT

        self.logger.debug(f"Sent bitfield to {connection.peer_info}")

    def _send_unchoke(self, connection: PeerConnection) -> None:
        """Unchoke the peer to allow them to request blocks."""
        if connection.socket is None:
            return
        try:
            msg = UnchokeMessage()
            self._send_message(connection, msg)
        except Exception as e:
            self.logger.debug(f"Failed to send unchoke to {connection.peer_info}: {e}")

    def _handle_peer_messages(self, connection: PeerConnection) -> None:
        """Handle incoming messages from a peer (runs in thread)."""
        try:
            sock = connection.socket
            if sock is None:
                return

            # Set to non-blocking for message loop
            sock.settimeout(0)

            while connection.is_connected():
                # Check if socket is ready for reading
                ready = select.select([sock], [], [], 1.0)
                if not ready[0]:
                    # No data available, check for timeout
                    if connection.has_timed_out(60.0):  # 60 second timeout
                        raise ConnectionError("Connection timed out")
                    continue

                # Receive data
                try:
                    data = sock.recv(4096)
                    if not data:
                        # Connection closed by peer
                        raise ConnectionError("Connection closed by peer")

                    connection.last_activity = time.time()

                    # Decode messages
                    messages = connection.message_decoder.add_data(data)

                    for message in messages:
                        self._handle_message(connection, message)

                except OSError as e:
                    if e.errno in (socket_module.EWOULDBLOCK, socket_module.EAGAIN):
                        # No data available, continue
                        continue
                    raise ConnectionError(f"Socket error: {e}")

        except Exception as e:
            self.logger.error(f"Error handling messages from peer {connection.peer_info}: {e}")
            self._handle_connection_error(connection, str(e))

    def _handle_message(self, connection: PeerConnection, message: PeerMessage) -> None:
        """Handle a single message from a peer."""
        try:
            # Update activity
            connection.last_activity = time.time()

            # Route to appropriate handler
            if isinstance(message, KeepAliveMessage):
                # Keep-alive, just update activity
                pass
            elif isinstance(message, BitfieldMessage):
                self.message_handlers[MessageType.BITFIELD](connection, message)
            elif isinstance(message, HaveMessage):
                self.message_handlers[MessageType.HAVE](connection, message)
            elif isinstance(message, PieceMessage):
                self.message_handlers[MessageType.PIECE](connection, message)
            else:
                # Handle state change messages
                if isinstance(message, ChokeMessage):
                    connection.peer_state.am_choking = True
                    connection.state = ConnectionState.CHOKED
                elif isinstance(message, UnchokeMessage):
                    connection.peer_state.am_choking = False
                    connection.state = ConnectionState.ACTIVE
                elif isinstance(message, InterestedMessage):
                    connection.peer_state.peer_interested = True
                elif isinstance(message, NotInterestedMessage):
                    connection.peer_state.peer_interested = False

                self.logger.debug(f"Received {message.__class__.__name__} from {connection.peer_info}")

        except Exception as e:
            self.logger.error(f"Error handling message from peer {connection.peer_info}: {e}")
            self._handle_connection_error(connection, f"Message handling error: {e}")

    def _handle_choke(self, connection: PeerConnection, message: ChokeMessage) -> None:
        """Handle choke message."""
        connection.peer_state.am_choking = True
        connection.state = ConnectionState.CHOKED
        self.logger.debug(f"Peer {connection.peer_info} choked us")

    def _handle_unchoke(self, connection: PeerConnection, message: UnchokeMessage) -> None:
        """Handle unchoke message."""
        connection.peer_state.am_choking = False
        connection.state = ConnectionState.ACTIVE
        self.logger.debug(f"Peer {connection.peer_info} unchoked us")

    def _handle_interested(self, connection: PeerConnection, message: InterestedMessage) -> None:
        """Handle interested message."""
        connection.peer_state.peer_interested = True
        self.logger.debug(f"Peer {connection.peer_info} is interested")

    def _handle_not_interested(self, connection: PeerConnection, message: NotInterestedMessage) -> None:
        """Handle not interested message."""
        connection.peer_state.peer_interested = False
        self.logger.debug(f"Peer {connection.peer_info} is not interested")

    def _handle_have(self, connection: PeerConnection, message: HaveMessage) -> None:
        """Handle have message."""
        piece_index = message.piece_index
        connection.peer_state.pieces_we_have.add(piece_index)
        self.logger.debug(f"Peer {connection.peer_info} has piece {piece_index}")

    def _handle_bitfield(self, connection: PeerConnection, message: BitfieldMessage) -> None:
        """Handle bitfield message."""
        connection.peer_state.bitfield = message
        connection.state = ConnectionState.BITFIELD_RECEIVED

        # If we also sent our bitfield, we're now active
        if connection.state == ConnectionState.BITFIELD_SENT:
            connection.state = ConnectionState.ACTIVE

        # Notify callback
        if self.on_bitfield_received:
            self.on_bitfield_received(connection, message)

        self.logger.info(f"Received bitfield from {connection.peer_info}: {len(message.bitfield)} bytes")

    def _handle_request(self, connection: PeerConnection, message: RequestMessage) -> None:
        """Handle request message."""
        piece_index = message.piece_index
        begin = message.begin
        length = message.length

        # Try to read from in-memory verified pieces first
        block = None
        try:
            block = self.piece_manager.get_block(piece_index, begin, length)
        except Exception:
            block = None

        # Fallback to disk via file assembler
        if block is None and getattr(self.piece_manager, "file_assembler", None):
            try:
                block = self.piece_manager.file_assembler.read_block(piece_index, begin, length)
            except Exception:
                block = None

        if block is None or len(block) != length:
            self.logger.debug(f"Cannot serve request {piece_index}:{begin}:{length} to {connection.peer_info}")
            return

        # Send the piece block
        try:
            piece_msg = PieceMessage(piece_index, begin, block)
            self._send_message(connection, piece_msg)
            self.logger.debug(f"Served block {piece_index}:{begin}:{length} to {connection.peer_info}")
        except Exception as e:
            self.logger.error(f"Failed to send piece to {connection.peer_info}: {e}")

    def _handle_piece(self, connection: PeerConnection, message: PieceMessage) -> None:
        """Handle piece message."""
        # Notify callback
        if self.on_piece_received:
            self.on_piece_received(connection, message)

        self.logger.debug(f"Received piece {message.piece_index} block from {connection.peer_info}")

    def _handle_cancel(self, connection: PeerConnection, message: CancelMessage) -> None:
        """Handle cancel message."""
        # No queued sends implemented; treat as no-op for now
        self.logger.debug(f"Peer {connection.peer_info} cancelled request for piece {message.piece_index}")

    def _send_message(self, connection: PeerConnection, message: PeerMessage) -> None:
        """Send a message to a peer."""
        if connection.socket is None:
            return

        try:
            data = message.encode()
            connection.socket.send(data)
            connection.last_activity = time.time()
            self.logger.debug(f"Sent {message.__class__.__name__} to {connection.peer_info}")
        except Exception as e:
            self.logger.error(f"Failed to send message to {connection.peer_info}: {e}")
            self._handle_connection_error(connection, f"Send error: {e}")

    def _handle_connection_error(self, connection: PeerConnection, error: str) -> None:
        """Handle connection error and cleanup."""
        connection.state = ConnectionState.ERROR
        connection.error_message = error

        # Close socket if open
        if connection.socket:
            try:
                connection.socket.close()
            except:
                pass
            connection.socket = None

        # Stop thread if running
        if connection.connection_thread and connection.connection_thread.is_alive():
            connection.connection_thread = None

        # Notify callback
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

        self.logger.error(f"Connection error for peer {connection.peer_info}: {error}")

    def send_interested(self, connection: PeerConnection) -> None:
        """Send interested message to peer."""
        if connection.is_connected():
            message = InterestedMessage()
            self._send_message(connection, message)
            connection.peer_state.am_interested = True

    def send_not_interested(self, connection: PeerConnection) -> None:
        """Send not interested message to peer."""
        if connection.is_connected():
            message = NotInterestedMessage()
            self._send_message(connection, message)
            connection.peer_state.am_interested = False

    def request_piece(self, connection: PeerConnection, piece_index: int, begin: int, length: int) -> None:
        """Request a block from a peer."""
        if connection.is_connected() and not connection.peer_state.am_choking:
            message = RequestMessage(piece_index, begin, length)
            self._send_message(connection, message)
            self.logger.debug(f"Requested block {piece_index}:{begin}:{length} from {connection.peer_info}")

    def broadcast_have(self, piece_index: int) -> None:
        """Broadcast HAVE message to all connected peers for a verified piece."""
        have_msg = HaveMessage(piece_index)
        with self.lock:
            for connection in self.connections.values():
                if connection.is_connected():
                    self._send_message(connection, have_msg)

    def get_connected_peers(self) -> List[PeerConnection]:
        """Get list of connected peers."""
        with self.lock:
            return [conn for conn in self.connections.values() if conn.is_connected()]

    def get_active_peers(self) -> List[PeerConnection]:
        """Get list of active peers (fully connected with bitfield exchanged)."""
        with self.lock:
            return [conn for conn in self.connections.values() if conn.is_active()]

    def get_peer_bitfields(self) -> Dict[str, BitfieldMessage]:
        """Get bitfields for all connected peers."""
        result = {}
        with self.lock:
            for peer_key, connection in self.connections.items():
                if connection.peer_state.bitfield:
                    result[peer_key] = connection.peer_state.bitfield
        return result

    def disconnect_peer(self, peer_info: PeerInfo) -> None:
        """Disconnect from a specific peer."""
        peer_key = str(peer_info)
        with self.lock:
            if peer_key in self.connections:
                connection = self.connections[peer_key]
                self._handle_connection_error(connection, "Manual disconnect")

    def disconnect_all(self) -> None:
        """Disconnect from all peers."""
        with self.lock:
            for connection in self.connections.values():
                self._handle_connection_error(connection, "Shutdown")

    def shutdown(self) -> None:
        """Shutdown the connection manager."""
        self.logger.info("Shutting down peer connection manager")
        self.disconnect_all()

        # Wait for threads to finish
        with self.lock:
            for connection in self.connections.values():
                if connection.connection_thread and connection.connection_thread.is_alive():
                    connection.connection_thread.join(timeout=5.0)

        self.logger.info("Peer connection manager shutdown complete")
