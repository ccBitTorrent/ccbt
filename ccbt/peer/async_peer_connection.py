"""Async peer connection management for BitTorrent client.

from __future__ import annotations

High-performance asyncio-based peer connections with request pipelining,
tit-for-tat choking, and adaptive block sizing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ccbt.config.config import get_config
from ccbt.models import MessageType
from ccbt.peer.peer import (
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    HaveMessage,
    InterestedMessage,
    KeepAliveMessage,
    MessageDecoder,
    MessageError,
    NotInterestedMessage,
    PeerInfo,
    PeerMessage,
    PeerState,
    PieceMessage,
    RequestMessage,
    UnchokeMessage,
)

# Error message constants
_ERROR_READER_NOT_INITIALIZED = "Reader is not initialized"


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
class RequestInfo:
    """Information about an outstanding request."""

    piece_index: int
    begin: int
    length: int
    timestamp: float
    retry_count: int = 0


@dataclass
class PeerStats:
    """Statistics for a peer connection."""

    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    download_rate: float = 0.0  # bytes/second
    upload_rate: float = 0.0  # bytes/second
    request_latency: float = 0.0  # average latency in seconds
    last_activity: float = field(default_factory=time.time)
    snub_count: int = 0
    consecutive_failures: int = 0


@dataclass
class AsyncPeerConnection:
    """Async peer connection with request pipelining."""

    peer_info: PeerInfo
    torrent_data: dict[str, Any]
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    peer_state: PeerState = field(default_factory=PeerState)
    message_decoder: MessageDecoder = field(default_factory=MessageDecoder)
    stats: PeerStats = field(default_factory=PeerStats)

    # Request pipeline
    outstanding_requests: dict[tuple[int, int, int], RequestInfo] = field(
        default_factory=dict,
    )
    request_queue: deque = field(default_factory=deque)
    max_pipeline_depth: int = 16

    # Choking state
    am_choking: bool = True
    peer_choking: bool = True
    am_interested: bool = False
    peer_interested: bool = False

    # Connection management
    connection_task: asyncio.Task | None = None
    error_message: str | None = None

    def __str__(self):
        """Return string representation of the connection."""
        return f"AsyncPeerConnection({self.peer_info}, state={self.state.value})"

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
        """Check if connection is fully active."""
        return self.state in [ConnectionState.ACTIVE, ConnectionState.CHOKED]

    def has_timed_out(self, timeout: float = 60.0) -> bool:
        """Check if connection has timed out."""
        return time.time() - self.stats.last_activity > timeout

    def can_request(self) -> bool:
        """Check if we can make new requests."""
        return (
            self.is_active()
            and not self.peer_choking
            and len(self.outstanding_requests) < self.max_pipeline_depth
        )

    def get_available_pipeline_slots(self) -> int:
        """Get number of available pipeline slots."""
        return max(0, self.max_pipeline_depth - len(self.outstanding_requests))


class AsyncPeerConnectionManager:
    """Async peer connection manager with advanced features."""

    def __init__(
        self,
        torrent_data: dict[str, Any],
        piece_manager: Any,
        peer_id: bytes | None = None,
    ):
        """Initialize async peer connection manager.

        Args:
            torrent_data: Parsed torrent data
            piece_manager: Piece manager instance
            peer_id: Our peer ID (20 bytes)
        """
        self.torrent_data = torrent_data
        self.piece_manager = piece_manager
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Connection management
        self.connections: dict[str, AsyncPeerConnection] = {}
        self.connection_lock = asyncio.Lock()

        # Choking management
        self.upload_slots: list[AsyncPeerConnection] = []
        self.optimistic_unchoke: AsyncPeerConnection | None = None
        self.optimistic_unchoke_time: float = 0.0

        # Background tasks
        self._choking_task: asyncio.Task | None = None
        self._stats_task: asyncio.Task | None = None

        # Callbacks
        self.on_peer_connected: Callable[[AsyncPeerConnection], None] | None = None
        self.on_peer_disconnected: Callable[[AsyncPeerConnection], None] | None = None
        self.on_bitfield_received: (
            Callable[[AsyncPeerConnection, BitfieldMessage], None] | None
        ) = None
        self.on_piece_received: (
            Callable[[AsyncPeerConnection, PieceMessage], None] | None
        ) = None

        # Message handlers
        self.message_handlers: dict[
            MessageType,
            Callable[[AsyncPeerConnection, PeerMessage], None],
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

        self.logger = logging.getLogger(__name__)

    def _raise_info_hash_mismatch(self, expected: bytes, got: bytes) -> None:
        """Raise PeerConnectionError for info hash mismatch."""
        msg = f"Info hash mismatch: expected {expected.hex()}, got {got.hex()}"
        raise PeerConnectionError(msg)

    async def start(self) -> None:
        """Start background tasks."""
        self._choking_task = asyncio.create_task(self._choking_loop())
        self._stats_task = asyncio.create_task(self._stats_loop())
        self.logger.info("Async peer connection manager started")

    async def stop(self) -> None:
        """Stop background tasks and disconnect all peers."""
        if self._choking_task:
            self._choking_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._choking_task

        if self._stats_task:
            self._stats_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stats_task

        # Disconnect all peers
        async with self.connection_lock:
            for connection in list(self.connections.values()):
                await self._disconnect_peer(connection)

        self.logger.info("Async peer connection manager stopped")

    async def shutdown(self) -> None:
        """Alias for stop method for backward compatibility."""
        await self.stop()

    async def connect_to_peers(self, peer_list: list[dict[str, Any]]) -> None:
        """Connect to a list of peers concurrently.

        Args:
            peer_list: List of peer dictionaries from tracker response
        """
        config = self.config.network
        max_connections = min(config.max_peers_per_torrent, len(peer_list))

        # Create connection tasks
        tasks = []
        for _i, peer_data in enumerate(peer_list[:max_connections]):
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
            connection = AsyncPeerConnection(peer_info, self.torrent_data)
            connection.state = ConnectionState.CONNECTING
            connection.max_pipeline_depth = self.config.network.pipeline_depth

            # Establish TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(peer_info.ip, peer_info.port),
                timeout=self.config.network.connection_timeout,
            )

            connection.reader = reader
            connection.writer = writer
            connection.state = ConnectionState.HANDSHAKE_SENT

            # Send handshake
            info_hash = self.torrent_data["info_hash"]
            handshake = Handshake(info_hash, self.our_peer_id)
            handshake_data = handshake.encode()
            writer.write(handshake_data)
            await writer.drain()

            # Receive and validate handshake
            peer_handshake_data = await reader.readexactly(68)
            peer_handshake = Handshake.decode(peer_handshake_data)
            connection.peer_info.peer_id = peer_handshake.peer_id
            connection.state = ConnectionState.HANDSHAKE_RECEIVED

            # Validate handshake
            if peer_handshake.info_hash != info_hash:
                self._raise_info_hash_mismatch(info_hash, peer_handshake.info_hash)

            # Send our bitfield and unchoke
            await self._send_bitfield(connection)
            await self._send_unchoke(connection)

            # Start message handling
            connection.connection_task = asyncio.create_task(
                self._handle_peer_messages(connection),
            )

            # Add to connections
            async with self.connection_lock:
                self.connections[str(peer_info)] = connection

            # Notify callback
            if self.on_peer_connected:
                self.on_peer_connected(connection)

            self.logger.info("Connected to peer %s", peer_info)

        except Exception:
            self.logger.exception("Failed to connect to peer %s", peer_info)
            await self._disconnect_peer(connection)

    async def _handle_peer_messages(self, connection: AsyncPeerConnection) -> None:
        """Handle incoming messages from a peer."""
        try:
            while connection.is_connected():
                if connection.reader is None:
                    msg = _ERROR_READER_NOT_INITIALIZED
                    raise RuntimeError(msg)
                # Read message length
                length_data = await connection.reader.readexactly(4)
                length = int.from_bytes(length_data, "big")

                if length == 0:
                    # Keep-alive message
                    connection.stats.last_activity = time.time()
                    continue

                # Read message payload
                payload = await connection.reader.readexactly(length)
                connection.stats.last_activity = time.time()

                # Decode message
                message_data = length_data + payload
                try:
                    await connection.message_decoder.feed_data(message_data)
                    message = await connection.message_decoder.get_message()
                    if message:
                        await self._handle_message(connection, message)
                except (MessageError, IndexError) as e:
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
                "Error handling messages from %s",
                connection.peer_info,
            )
        finally:
            await self._disconnect_peer(connection)

    async def _handle_message(
        self,
        connection: AsyncPeerConnection,
        message: PeerMessage,
    ) -> None:
        """Handle a single message from a peer."""
        try:
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
                    connection.peer_choking = True
                    connection.state = ConnectionState.CHOKED
                elif isinstance(message, UnchokeMessage):
                    connection.peer_choking = False
                    connection.state = ConnectionState.ACTIVE
                elif isinstance(message, InterestedMessage):
                    connection.peer_interested = True
                elif isinstance(message, NotInterestedMessage):
                    connection.peer_interested = False

                self.logger.debug(
                    "Received %s from %s",
                    message.__class__.__name__,
                    connection.peer_info,
                )

        except Exception:
            self.logger.exception(
                "Error handling message from %s",
                connection.peer_info,
            )

    async def _handle_choke(
        self,
        connection: AsyncPeerConnection,
        _message: ChokeMessage,
    ) -> None:
        """Handle choke message."""
        connection.peer_choking = True
        connection.state = ConnectionState.CHOKED
        self.logger.debug("Peer %s choked us", connection.peer_info)

    async def _handle_unchoke(
        self,
        connection: AsyncPeerConnection,
        _message: UnchokeMessage,
    ) -> None:
        """Handle unchoke message."""
        connection.peer_choking = False
        connection.state = ConnectionState.ACTIVE
        self.logger.debug("Peer %s unchoked us", connection.peer_info)

    async def _handle_interested(
        self,
        connection: AsyncPeerConnection,
        _message: InterestedMessage,
    ) -> None:
        """Handle interested message."""
        connection.peer_interested = True
        self.logger.debug("Peer %s is interested", connection.peer_info)

    async def _handle_not_interested(
        self,
        connection: AsyncPeerConnection,
        _message: NotInterestedMessage,
    ) -> None:
        """Handle not interested message."""
        connection.peer_interested = False
        self.logger.debug("Peer %s is not interested", connection.peer_info)

    async def _handle_have(
        self,
        connection: AsyncPeerConnection,
        message: HaveMessage,
    ) -> None:
        """Handle have message."""
        piece_index = message.piece_index
        connection.peer_state.pieces_we_have.add(piece_index)
        self.logger.debug("Peer %s has piece %s", connection.peer_info, piece_index)

    async def _handle_bitfield(
        self,
        connection: AsyncPeerConnection,
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
        connection: AsyncPeerConnection,
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
            connection.stats.bytes_uploaded += len(block)
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
        self,
        connection: AsyncPeerConnection,
        message: PieceMessage,
    ) -> None:
        """Handle piece message."""
        # Update download stats
        connection.stats.bytes_downloaded += len(message.block)

        # Remove from outstanding requests
        request_key = (message.piece_index, message.begin, len(message.block))
        if request_key in connection.outstanding_requests:
            del connection.outstanding_requests[request_key]

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
        connection: AsyncPeerConnection,
        message: CancelMessage,
    ) -> None:
        """Handle cancel message."""
        # Remove from outstanding requests
        request_key = (message.piece_index, message.begin, message.length)
        if request_key in connection.outstanding_requests:
            del connection.outstanding_requests[request_key]

        self.logger.debug(
            "Peer %s cancelled request for piece %s",
            connection.peer_info,
            message.piece_index,
        )

    async def _send_message(
        self,
        connection: AsyncPeerConnection,
        message: PeerMessage,
    ) -> None:
        """Send a message to a peer."""
        if connection.writer is None:
            return

        try:
            data = message.encode()
            connection.writer.write(data)
            await connection.writer.drain()
            connection.stats.last_activity = time.time()
            self.logger.debug(
                "Sent %s to %s",
                message.__class__.__name__,
                connection.peer_info,
            )
        except Exception:
            self.logger.exception(
                "Failed to send message to %s",
                connection.peer_info,
            )
            await self._disconnect_peer(connection)

    async def _send_bitfield(self, connection: AsyncPeerConnection) -> None:
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

    async def _send_unchoke(self, connection: AsyncPeerConnection) -> None:
        """Unchoke the peer to allow them to request blocks."""
        if connection.writer is None:
            return

        try:
            msg = UnchokeMessage()
            await self._send_message(connection, msg)
            connection.am_choking = False
        except Exception as e:
            self.logger.debug(
                "Failed to send unchoke to %s: %s",
                connection.peer_info,
                e,
            )

    async def _disconnect_peer(self, connection: AsyncPeerConnection) -> None:
        """Disconnect from a peer."""
        connection.state = ConnectionState.ERROR

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
                pass  # Connection writer cleanup errors are expected

        # Remove from connections
        async with self.connection_lock:
            peer_key = str(connection.peer_info)
            if peer_key in self.connections:
                del self.connections[peer_key]

        # Remove from upload slots
        if connection in self.upload_slots:
            self.upload_slots.remove(connection)

        # Clear optimistic unchoke if this peer
        if self.optimistic_unchoke == connection:
            self.optimistic_unchoke = None

        # Notify callback
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

        self.logger.info("Disconnected from peer %s", connection.peer_info)

    async def _choking_loop(self) -> None:
        """Background task for choking/unchoking management."""
        while await self._choking_loop_step():
            pass

    async def _choking_loop_step(self) -> bool:
        """Execute one choking loop iteration. Return False to stop the loop."""
        try:
            await asyncio.sleep(self.config.network.unchoke_interval)
            await self._update_choking()
            return True
        except asyncio.CancelledError:
            return False
        except Exception:
            self.logger.exception("Error in choking loop")
            return True

    async def _update_choking(self) -> None:
        """Update choking/unchoking based on tit-for-tat."""
        async with self.connection_lock:
            active_peers = [
                conn for conn in self.connections.values() if conn.is_active()
            ]

            if not active_peers:
                return

            # Sort by upload rate (descending)
            active_peers.sort(key=lambda p: p.stats.upload_rate, reverse=True)

            # Unchoke top uploaders
            max_slots = self.config.network.max_upload_slots
            new_upload_slots = active_peers[:max_slots]

            # Choke peers not in new slots
            for peer in self.upload_slots:
                if peer not in new_upload_slots:
                    await self._choke_peer(peer)

            # Unchoke new peers
            for peer in new_upload_slots:
                if peer not in self.upload_slots:
                    await self._unchoke_peer(peer)

            self.upload_slots = new_upload_slots

            # Optimistic unchoke
            await self._update_optimistic_unchoke()

    async def _update_optimistic_unchoke(self) -> None:
        """Update optimistic unchoke peer."""
        current_time = time.time()
        interval = self.config.network.optimistic_unchoke_interval

        # Check if we need a new optimistic unchoke
        if (
            self.optimistic_unchoke is None
            or current_time - self.optimistic_unchoke_time > interval
        ):
            # Choke current optimistic unchoke if not in upload slots
            if (
                self.optimistic_unchoke
                and self.optimistic_unchoke not in self.upload_slots
            ):
                await self._choke_peer(self.optimistic_unchoke)

            # Select new optimistic unchoke
            async with self.connection_lock:
                available_peers = [
                    conn
                    for conn in self.connections.values()
                    if (
                        conn.is_active()
                        and conn not in self.upload_slots
                        and conn.peer_interested
                    )
                ]

            if available_peers:
                self.optimistic_unchoke = random.choice(available_peers)  # nosec B311 - Peer selection is not security-sensitive
                await self._unchoke_peer(self.optimistic_unchoke)
                self.optimistic_unchoke_time = current_time
                self.logger.debug(
                    "New optimistic unchoke: %s",
                    self.optimistic_unchoke.peer_info,
                )

    async def _choke_peer(self, connection: AsyncPeerConnection) -> None:
        """Choke a peer."""
        if not connection.am_choking:
            await self._send_message(connection, ChokeMessage())
            connection.am_choking = True
            self.logger.debug("Choked peer %s", connection.peer_info)

    async def _unchoke_peer(self, connection: AsyncPeerConnection) -> None:
        """Unchoke a peer."""
        if connection.am_choking:
            await self._send_message(connection, UnchokeMessage())
            connection.am_choking = False
            self.logger.debug("Unchoked peer %s", connection.peer_info)

    async def _stats_loop(self) -> None:
        """Background task for updating peer statistics."""
        while await self._stats_loop_step():
            pass

    async def _stats_loop_step(self) -> bool:
        """Execute one stats loop iteration. Return False to stop the loop."""
        try:
            await asyncio.sleep(5.0)  # Update every 5 seconds
            await self._update_peer_stats()
            return True
        except asyncio.CancelledError:
            return False
        except Exception:
            self.logger.exception("Error in stats loop")
            return True

    async def _update_peer_stats(self) -> None:
        """Update peer statistics."""
        current_time = time.time()

        async with self.connection_lock:
            for connection in self.connections.values():
                # Calculate rates
                time_diff = current_time - connection.stats.last_activity
                if time_diff > 0:
                    connection.stats.download_rate = (
                        connection.stats.bytes_downloaded / time_diff
                    )
                    connection.stats.upload_rate = (
                        connection.stats.bytes_uploaded / time_diff
                    )

                # Reset counters
                connection.stats.bytes_downloaded = 0
                connection.stats.bytes_uploaded = 0
                connection.stats.last_activity = current_time

    async def request_piece(
        self,
        connection: AsyncPeerConnection,
        piece_index: int,
        begin: int,
        length: int,
    ) -> None:
        """Request a block from a peer."""
        if connection.can_request():
            request_key = (piece_index, begin, length)
            request_info = RequestInfo(piece_index, begin, length, time.time())

            connection.outstanding_requests[request_key] = request_info

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
        """Broadcast HAVE message to all connected peers."""
        have_msg = HaveMessage(piece_index)
        async with self.connection_lock:
            for connection in self.connections.values():
                if connection.is_connected():
                    await self._send_message(connection, have_msg)

    def get_connected_peers(self) -> list[AsyncPeerConnection]:
        """Get list of connected peers."""
        return [conn for conn in self.connections.values() if conn.is_connected()]

    def get_active_peers(self) -> list[AsyncPeerConnection]:
        """Get list of active peers."""
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
        async with self.connection_lock:
            peer_key = str(peer_info)
            if peer_key in self.connections:
                connection = self.connections[peer_key]
                await self._disconnect_peer(connection)

    async def disconnect_all(self) -> None:
        """Disconnect from all peers."""
        async with self.connection_lock:
            for connection in list(self.connections.values()):
                await self._disconnect_peer(connection)
