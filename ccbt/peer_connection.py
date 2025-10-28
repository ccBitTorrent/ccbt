"""Async peer connection management for BitTorrent client.

This module handles establishing TCP connections to peers, exchanging handshakes,
managing bitfields, and coordinating peer communication using asyncio.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ccbt.peer import (
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


class PeerConnectionError(Exception):
    """Exception raised when peer connection fails."""


@dataclass
class PeerConnection:
    """Represents an async connection to a single peer."""

    peer_info: PeerInfo
    torrent_data: dict[str, Any]
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    peer_state: PeerState = field(default_factory=PeerState)
    message_decoder: MessageDecoder = field(default_factory=MessageDecoder)
    last_activity: float = field(default_factory=time.time)
    connection_task: asyncio.Task | None = None
    error_message: str | None = None

    def __str__(self):
        """Return string representation of peer connection."""
        return f"PeerConnection({self.peer_info}, state={self.state.value})"

    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.state in [
            ConnectionState.CONNECTED,
            ConnectionState.BITFIELD_SENT,
            ConnectionState.BITFIELD_RECEIVED,
            ConnectionState.ACTIVE,
            ConnectionState.CHOKED,
        ]

    def is_active(self) -> bool:
        """Check if connection is fully active (handshake and bitfield exchanged)."""
        return self.state in [ConnectionState.ACTIVE, ConnectionState.CHOKED]

    def has_timed_out(self, timeout: float = 30.0) -> bool:
        """Check if connection has timed out due to inactivity."""
        return time.time() - self.last_activity > timeout


class AsyncPeerConnectionManager:
    """Async manager for connections to multiple peers."""

    def __init__(
        self,
        torrent_data: dict[str, Any],
        piece_manager: Any,
        peer_id: bytes | None = None,
        max_connections: int = 50,
        connection_timeout: float = 10.0,
    ):
        """Initialize async peer connection manager.

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
        self.connections: dict[str, PeerConnection] = {}
        self.connected_peers: set[str] = set()
        self.connection_lock = asyncio.Lock()

        # Callbacks
        self.on_peer_connected: Callable[[PeerConnection], None] | None = None
        self.on_peer_disconnected: Callable[[PeerConnection], None] | None = None
        self.on_bitfield_received: (
            Callable[[PeerConnection, BitfieldMessage], None] | None
        ) = None
        self.on_piece_received: (
            Callable[[PeerConnection, PieceMessage], None] | None
        ) = None

        # Message handlers
        self.message_handlers: dict[
            MessageType,
            Callable[[PeerConnection, PeerMessage], Any],
        ] = {
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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()

    async def connect_to_peers(self, peer_list: list[dict[str, Any]]) -> None:
        """Connect to a list of peers concurrently.

        Args:
            peer_list: List of peer dictionaries from tracker response
        """
        async with self.connection_lock:
            # Limit connections to max_connections
            available_slots = self.max_connections - len(self.connections)
            if available_slots <= 0:
                return

            # Take only the peers we can handle
            peers_to_connect = peer_list[:available_slots]

        # Connect to peers concurrently
        tasks = []
        for peer_data in peers_to_connect:
            peer_info = PeerInfo(ip=peer_data["ip"], port=peer_data["port"])

            # Skip if already connected
            if str(peer_info) in self.connections:
                continue

            task = asyncio.create_task(self._connect_to_peer(peer_info))
            tasks.append(task)

        # Wait for all connections to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error("Connection failed: %s", result)

    async def _connect_to_peer(self, peer_info: PeerInfo) -> None:
        """Connect to a single peer."""
        try:
            self.logger.info("Connecting to peer %s", peer_info)

            # Create connection object
            connection = PeerConnection(peer_info, self.torrent_data)
            connection.state = ConnectionState.CONNECTING

            # Establish TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(peer_info.ip, peer_info.port),
                timeout=self.connection_timeout,
            )

            connection.reader = reader
            connection.writer = writer
            connection.state = ConnectionState.HANDSHAKE_SENT
            connection.last_activity = time.time()

            # Send handshake
            info_hash = self.torrent_data["info_hash"]
            handshake = Handshake(info_hash, self.our_peer_id)
            handshake_data = handshake.encode()
            writer.write(handshake_data)
            await writer.drain()

            self.logger.debug("Sent handshake to %s", peer_info)

            # Receive and validate handshake
            peer_handshake_data = await reader.readexactly(68)
            if len(peer_handshake_data) != 68:
                msg = f"Invalid handshake length: {len(peer_handshake_data)}"
                raise PeerConnectionError(msg)

            peer_handshake = Handshake.decode(peer_handshake_data)
            connection.peer_info.peer_id = peer_handshake.peer_id
            connection.state = ConnectionState.HANDSHAKE_RECEIVED
            connection.last_activity = time.time()

            # Validate handshake
            if peer_handshake.info_hash != info_hash:
                msg = f"Info hash mismatch: expected {info_hash.hex()}, got {peer_handshake.info_hash.hex()}"
                raise PeerConnectionError(msg)

            self.logger.info("Handshake successful with peer %s", peer_info)

            # Send our bitfield and unchoke to allow requests
            await self._send_bitfield(connection)
            await self._send_unchoke(connection)

            # Start message handling loop
            connection.connection_task = asyncio.create_task(
                self._handle_peer_messages(connection)
            )

            # Add to connections
            async with self.connection_lock:
                self.connections[str(peer_info)] = connection

            # Notify callback
            if self.on_peer_connected:
                self.on_peer_connected(connection)

            self.logger.info("Connected to peer %s", peer_info)

        except Exception as e:
            self.logger.exception("Failed to connect to peer %s", peer_info)
            await self._handle_connection_error(connection, str(e))

    async def _handle_peer_messages(self, connection: PeerConnection) -> None:
        """Handle incoming messages from a peer."""
        try:
            while connection.is_connected():
                if connection.reader is None:
                    break

                # Read message length
                length_data = await connection.reader.readexactly(4)
                length = int.from_bytes(length_data, "big")

                if length == 0:
                    # Keep-alive message
                    connection.last_activity = time.time()
                    continue

                # Read message payload
                payload = await connection.reader.readexactly(length)
                connection.last_activity = time.time()

                # Decode message
                message_data = length_data + payload
                try:
                    await connection.message_decoder.feed_data(message_data)
                    # Get messages from the decoder
                    while True:
                        message = await connection.message_decoder.get_message()
                        if message is None:
                            break
                        await self._handle_message(connection, message)
                except Exception as e:
                    self.logger.warning(
                        "Failed to decode message from %s: %s",
                        connection.peer_info,
                        e,
                    )
                    continue

        except asyncio.CancelledError:
            pass
        except Exception:
            self.logger.exception(
                "Error handling messages from peer %s",
                connection.peer_info,
            )
        finally:
            await self._handle_connection_error(connection, "Message loop ended")

    async def _handle_message(
        self, connection: PeerConnection, message: PeerMessage
    ) -> None:
        """Handle a single message from a peer."""
        try:
            # Update activity
            connection.last_activity = time.time()

            # Route to appropriate handler
            if isinstance(message, KeepAliveMessage):
                # Keep-alive, just update activity
                pass
            elif isinstance(message, BitfieldMessage):
                await self.message_handlers[MessageType.BITFIELD](connection, message)
            elif isinstance(message, HaveMessage):
                await self.message_handlers[MessageType.HAVE](connection, message)
            elif isinstance(message, PieceMessage):
                await self.message_handlers[MessageType.PIECE](connection, message)
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

                self.logger.debug(
                    "Received %s from %s",
                    message.__class__.__name__,
                    connection.peer_info,
                )

        except Exception as e:
            self.logger.exception(
                "Error handling message from peer %s",
                connection.peer_info,
            )
            await self._handle_connection_error(
                connection, f"Message handling error: {e}"
            )

    async def _handle_choke(
        self, connection: PeerConnection, _message: ChokeMessage
    ) -> None:
        """Handle choke message."""
        connection.peer_state.am_choking = True
        connection.state = ConnectionState.CHOKED
        self.logger.debug("Peer %s choked us", connection.peer_info)

    async def _handle_unchoke(
        self,
        connection: PeerConnection,
        _message: UnchokeMessage,
    ) -> None:
        """Handle unchoke message."""
        connection.peer_state.am_choking = False
        connection.state = ConnectionState.ACTIVE
        self.logger.debug("Peer %s unchoked us", connection.peer_info)

    async def _handle_interested(
        self,
        connection: PeerConnection,
        _message: InterestedMessage,
    ) -> None:
        """Handle interested message."""
        connection.peer_state.peer_interested = True
        self.logger.debug("Peer %s is interested", connection.peer_info)

    async def _handle_not_interested(
        self,
        connection: PeerConnection,
        _message: NotInterestedMessage,
    ) -> None:
        """Handle not interested message."""
        connection.peer_state.peer_interested = False
        self.logger.debug("Peer %s is not interested", connection.peer_info)

    async def _handle_have(
        self, connection: PeerConnection, message: HaveMessage
    ) -> None:
        """Handle have message."""
        piece_index = message.piece_index
        connection.peer_state.pieces_we_have.add(piece_index)
        self.logger.debug("Peer %s has piece %s", connection.peer_info, piece_index)

    async def _handle_bitfield(
        self,
        connection: PeerConnection,
        message: BitfieldMessage,
    ) -> None:
        """Handle bitfield message."""
        connection.peer_state.bitfield = message.bitfield
        connection.state = ConnectionState.BITFIELD_RECEIVED

        # If we also sent our bitfield, we're now active
        if connection.state == ConnectionState.BITFIELD_SENT:
            connection.state = ConnectionState.ACTIVE

        # Notify callback
        if self.on_bitfield_received:
            self.on_bitfield_received(connection, message)

        self.logger.info(
            "Received bitfield from %s: %s bytes",
            connection.peer_info,
            len(message.bitfield),
        )

    async def _handle_request(
        self,
        connection: PeerConnection,
        message: RequestMessage,
    ) -> None:
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
                block = self.piece_manager.file_assembler.read_block(
                    piece_index,
                    begin,
                    length,
                )
            except Exception:
                block = None

        if block is None or len(block) != length:
            self.logger.debug(
                "Cannot serve request %s:%s:%s to %s",
                piece_index,
                begin,
                length,
                connection.peer_info,
            )
            return

        # Send the piece block
        try:
            piece_msg = PieceMessage(piece_index, begin, block)
            await self._send_message(connection, piece_msg)
            self.logger.debug(
                "Served block %s:%s:%s to %s",
                piece_index,
                begin,
                length,
                connection.peer_info,
            )
        except Exception:
            self.logger.exception(
                "Failed to send piece to %s",
                connection.peer_info,
            )

    async def _handle_piece(
        self, connection: PeerConnection, message: PieceMessage
    ) -> None:
        """Handle piece message."""
        # Notify callback
        if self.on_piece_received:
            self.on_piece_received(connection, message)

        self.logger.debug(
            "Received piece %s block from %s",
            message.piece_index,
            connection.peer_info,
        )

    async def _handle_cancel(
        self,
        connection: PeerConnection,
        message: CancelMessage,
    ) -> None:
        """Handle cancel message."""
        # No queued sends implemented; treat as no-op for now
        self.logger.debug(
            "Peer %s cancelled request for piece %s",
            connection.peer_info,
            message.piece_index,
        )

    async def _send_message(
        self, connection: PeerConnection, message: PeerMessage
    ) -> None:
        """Send a message to a peer."""
        if connection.writer is None:
            return

        try:
            data = message.encode()
            connection.writer.write(data)
            await connection.writer.drain()
            connection.last_activity = time.time()
            self.logger.debug(
                "Sent %s to %s",
                message.__class__.__name__,
                connection.peer_info,
            )
        except Exception as e:
            self.logger.exception(
                "Failed to send message to %s",
                connection.peer_info,
            )
            await self._handle_connection_error(connection, f"Send error: {e}")

    async def _send_bitfield(self, connection: PeerConnection) -> None:
        """Send our bitfield to the peer."""
        if connection.writer is None:
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
                bitfield_bytes[byte_index] |= 1 << (7 - bit_index)
        bitfield_data = bytes(bitfield_bytes)

        if bitfield_data:
            bitfield_message = BitfieldMessage(bitfield_data)
            await self._send_message(connection, bitfield_message)
            connection.state = ConnectionState.BITFIELD_SENT

        self.logger.debug("Sent bitfield to %s", connection.peer_info)

    async def _send_unchoke(self, connection: PeerConnection) -> None:
        """Unchoke the peer to allow them to request blocks."""
        if connection.writer is None:
            return
        try:
            msg = UnchokeMessage()
            await self._send_message(connection, msg)
        except Exception as e:
            self.logger.debug(
                "Failed to send unchoke to %s: %s",
                connection.peer_info,
                e,
            )

    async def _handle_connection_error(
        self, connection: PeerConnection, error: str, lock_held: bool = False
    ) -> None:
        """Handle connection error and cleanup."""
        connection.state = ConnectionState.ERROR
        connection.error_message = error

        # Cancel connection task
        if connection.connection_task:
            connection.connection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection.connection_task

        # Close writer
        if connection.writer:
            try:
                connection.writer.close()
                await connection.writer.wait_closed()
            except (OSError, RuntimeError, asyncio.CancelledError):
                # Ignore cleanup errors when closing connection writer
                pass

        # Remove from connections (only if lock not already held)
        if not lock_held:
            async with self.connection_lock:
                peer_key = str(connection.peer_info)
                if peer_key in self.connections:
                    del self.connections[peer_key]
        else:
            # Lock already held, just remove directly
            peer_key = str(connection.peer_info)
            if peer_key in self.connections:
                del self.connections[peer_key]

        # Notify callback
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

        self.logger.error(
            "Connection error for peer %s: %s",
            connection.peer_info,
            error,
        )

    async def send_interested(self, connection: PeerConnection) -> None:
        """Send interested message to peer."""
        if connection.is_connected():
            message = InterestedMessage()
            await self._send_message(connection, message)
            connection.peer_state.am_interested = True

    async def send_not_interested(self, connection: PeerConnection) -> None:
        """Send not interested message to peer."""
        if connection.is_connected():
            message = NotInterestedMessage()
            await self._send_message(connection, message)
            connection.peer_state.am_interested = False

    async def request_piece(
        self,
        connection: PeerConnection,
        piece_index: int,
        begin: int,
        length: int,
    ) -> None:
        """Request a block from a peer."""
        if connection.is_connected() and not connection.peer_state.am_choking:
            message = RequestMessage(piece_index, begin, length)
            await self._send_message(connection, message)
            self.logger.debug(
                "Requested block %s:%s:%s from %s",
                piece_index,
                begin,
                length,
                connection.peer_info,
            )

    async def broadcast_have(self, piece_index: int) -> None:
        """Broadcast HAVE message to all connected peers for a verified piece."""
        have_msg = HaveMessage(piece_index)
        async with self.connection_lock:
            for connection in self.connections.values():
                if connection.is_connected():
                    await self._send_message(connection, have_msg)

    def get_connected_peers(self) -> list[PeerConnection]:
        """Get list of connected peers."""
        return [conn for conn in self.connections.values() if conn.is_connected()]

    def get_active_peers(self) -> list[PeerConnection]:
        """Get list of active peers (fully connected with bitfield exchanged)."""
        return [conn for conn in self.connections.values() if conn.is_active()]

    def get_peer_bitfields(self) -> dict[str, BitfieldMessage]:
        """Get bitfields for all connected peers."""
        result = {}
        for peer_key, connection in self.connections.items():
            if connection.peer_state.bitfield:
                result[peer_key] = connection.peer_state.bitfield
        return result

    async def disconnect_peer(self, peer_info: PeerInfo) -> None:
        """Disconnect from a specific peer."""
        peer_key = str(peer_info)
        async with self.connection_lock:
            if peer_key in self.connections:
                connection = self.connections[peer_key]
                await self._handle_connection_error(
                    connection, "Manual disconnect", lock_held=True
                )

    async def disconnect_all(self) -> None:
        """Disconnect from all peers."""
        async with self.connection_lock:
            for connection in list(self.connections.values()):
                await self._handle_connection_error(
                    connection, "Shutdown", lock_held=True
                )

    async def shutdown(self) -> None:
        """Shutdown the connection manager."""
        self.logger.info("Shutting down peer connection manager")
        await self.disconnect_all()

        # Wait for tasks to finish
        async with self.connection_lock:
            for connection in self.connections.values():
                if connection.connection_task and not connection.connection_task.done():
                    connection.connection_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await connection.connection_task

        self.logger.info("Peer connection manager shutdown complete")


# Backward compatibility
PeerConnectionManager = AsyncPeerConnectionManager
