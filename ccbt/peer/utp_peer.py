"""uTP Peer Connection Wrapper.

Wraps UTPConnection to provide AsyncPeerConnection-compatible interface
for integration with the existing peer connection manager.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    ConnectionState,
    PeerStats,
)
from ccbt.peer.peer import PeerState
from ccbt.transport.utp import (
    UTPConnection,
    UTPConnectionState,
)

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Callable

logger = logging.getLogger(__name__)


class UTPStreamReader:
    """Stream reader adapter for uTP connections."""

    def __init__(self, utp_connection: UTPConnection):
        """Initialize stream reader.

        Args:
            utp_connection: Underlying uTP connection

        """
        self.utp_connection = utp_connection
        self._buffer = bytearray()

    async def read(self, n: int = -1) -> bytes:
        """Read data from uTP connection.

        Args:
            n: Number of bytes to read (-1 for all available)

        Returns:
            Read data bytes

        """
        if n < 0:
            # Read all available
            if len(self._buffer) > 0:
                data = bytes(self._buffer)
                self._buffer.clear()
                return data
            return await self.utp_connection.receive(-1)

        # Read exactly n bytes
        while len(self._buffer) < n:
            # Get more data from uTP connection
            chunk = await self.utp_connection.receive(n - len(self._buffer))
            if not chunk:
                # Connection closed
                break
            self._buffer.extend(chunk)

        # Return requested amount
        data = bytes(self._buffer[:n])
        self._buffer = self._buffer[n:]
        return data

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes.

        Args:
            n: Exact number of bytes to read

        Returns:
            Exactly n bytes

        Raises:
            EOFError: If connection closed before n bytes available

        """
        data = await self.read(n)
        if len(data) < n:
            msg = f"Connection closed: expected {n} bytes, got {len(data)}"
            raise EOFError(msg)
        return data


class UTPStreamWriter:
    """Stream writer adapter for uTP connections."""

    def __init__(self, utp_connection: UTPConnection):
        """Initialize stream writer.

        Args:
            utp_connection: Underlying uTP connection

        """
        self.utp_connection = utp_connection
        self._closed = False

    async def write(self, data: bytes) -> None:
        """Write data to uTP connection.

        Args:
            data: Data bytes to write

        Raises:
            RuntimeError: If connection is closed

        """
        if self._closed:
            msg = "Cannot write to closed connection"
            raise RuntimeError(msg)

        if self.utp_connection is None:
            msg = "uTP connection not initialized"
            raise RuntimeError(msg)

        await self.utp_connection.send(data)

    async def drain(self) -> None:
        """Wait for send buffer to drain."""
        # uTP handles flow control internally via congestion control
        # Just wait a small amount to allow packets to be sent
        await asyncio.sleep(0.01)

    async def close(self) -> None:
        """Close the stream writer."""
        self._closed = True

    def is_closing(self) -> bool:
        """Check if writer is closing or closed."""
        return self._closed


@dataclass
class UTPPeerConnection(AsyncPeerConnection):
    """uTP peer connection wrapper.

    Provides AsyncPeerConnection-compatible interface while using uTP
    transport protocol underneath.
    """

    # uTP-specific fields
    utp_connection: UTPConnection | None = None

    # Callbacks for compatibility with AsyncPeerConnection interface
    on_peer_connected: Callable[[AsyncPeerConnection], None] | None = None
    on_peer_disconnected: Callable[[AsyncPeerConnection], None] | None = None
    on_bitfield_received: Callable[[AsyncPeerConnection, Any], None] | None = None
    on_piece_received: Callable[[AsyncPeerConnection, Any], None] | None = None

    def __post_init__(self) -> None:
        """Initialize uTP peer connection."""
        # Initialize base class fields manually (dataclass compatibility)
        if not hasattr(self, "peer_state"):
            self.peer_state = PeerState()  # pragma: no cover - Dataclass initialization fallback, tested via normal initialization paths
        if not hasattr(self, "stats"):
            self.stats = PeerStats()  # pragma: no cover - Dataclass initialization fallback, tested via normal initialization paths
        if not hasattr(self, "message_decoder"):
            from ccbt.peer.peer import MessageDecoder

            self.message_decoder = MessageDecoder()  # pragma: no cover - Dataclass initialization fallback, tested via normal initialization paths

        self.state = ConnectionState.DISCONNECTED

        # Map uTP states to ConnectionState
        self._state_map = {
            UTPConnectionState.IDLE: ConnectionState.DISCONNECTED,
            UTPConnectionState.SYN_SENT: ConnectionState.CONNECTING,
            UTPConnectionState.SYN_RECEIVED: ConnectionState.CONNECTING,
            UTPConnectionState.CONNECTED: ConnectionState.CONNECTED,
            UTPConnectionState.FIN_SENT: ConnectionState.DISCONNECTED,
            UTPConnectionState.FIN_RECEIVED: ConnectionState.DISCONNECTED,
            UTPConnectionState.CLOSED: ConnectionState.DISCONNECTED,
            UTPConnectionState.RESET: ConnectionState.ERROR,
        }

    async def connect(self) -> None:
        """Connect to peer via uTP.

        Establishes uTP connection and creates stream reader/writer adapters.
        """
        self.state = ConnectionState.CONNECTING

        try:
            # Create uTP connection
            self.utp_connection = UTPConnection(
                remote_addr=(self.peer_info.ip, self.peer_info.port),
            )

            # Initialize transport (gets socket manager and registers connection)
            await self.utp_connection.initialize_transport()

            # Connect uTP connection
            await self.utp_connection.connect()

            # Wait for connection to be established
            # The connect() method handles SYN/SYN-ACK internally
            # We need to wait a bit for the handshake to complete
            timeout = 30.0
            start_time = time.perf_counter()
            while (
                self.utp_connection.state != UTPConnectionState.CONNECTED
                and time.perf_counter() - start_time < timeout
            ):
                await asyncio.sleep(0.1)

            if self.utp_connection.state != UTPConnectionState.CONNECTED:
                msg = "uTP connection failed to establish"
                raise ConnectionError(msg)

            # Create stream adapters
            self.reader = UTPStreamReader(self.utp_connection)  # type: ignore[assignment]
            self.writer = UTPStreamWriter(self.utp_connection)  # type: ignore[assignment]

            # Update state
            self.state = ConnectionState.CONNECTED
            self.stats.last_activity = time.time()

            # Start message receiving task
            self.connection_task = asyncio.create_task(self._receive_messages())

            logger.info(
                "uTP peer connection established to %s:%s",
                self.peer_info.ip,
                self.peer_info.port,
            )

        except Exception as e:
            self.state = ConnectionState.ERROR
            self.error_message = str(e)
            logger.exception(
                "Failed to establish uTP connection to %s:%s",
                self.peer_info.ip,
                self.peer_info.port,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from peer and clean up resources."""
        if self.utp_connection:
            try:
                await self.utp_connection.close()
            except Exception as e:
                logger.warning("Error closing uTP connection: %s", e)

        if self.connection_task:
            self.connection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.connection_task

        self.state = ConnectionState.DISCONNECTED
        self.reader = None
        self.writer = None

    async def _receive_messages(self) -> None:
        """Background task to receive messages from uTP connection."""
        if self.reader is None:
            return

        try:
            while self.state == ConnectionState.CONNECTED:
                # Read message length (4 bytes)
                length_data = await self.reader.readexactly(4)
                if not length_data:  # pragma: no cover - Defensive: readexactly should raise EOFError, but handle empty return gracefully
                    break

                message_length = int.from_bytes(length_data, byteorder="big")
                if message_length == 0:
                    # Keep-alive message
                    continue

                # Read message data
                message_data = await self.reader.readexactly(message_length)
                if not message_data:  # pragma: no cover - Defensive: readexactly should raise EOFError, but handle empty return gracefully
                    break

                # Feed to message decoder
                await self.message_decoder.feed_data(length_data + message_data)

                # Update statistics
                self.stats.last_activity = time.time()

        except (EOFError, ConnectionError) as e:
            logger.debug("uTP connection closed during receive: %s", e)
            self.state = ConnectionState.DISCONNECTED
        except Exception as e:
            logger.exception("Error in uTP receive loop")
            self.state = ConnectionState.ERROR
            self.error_message = str(e)

    def update_stats(self) -> None:
        """Update statistics from uTP connection."""
        if self.utp_connection:
            # Update bytes transferred
            self.stats.bytes_downloaded = self.utp_connection.bytes_received
            self.stats.bytes_uploaded = self.utp_connection.bytes_sent

            # Calculate rates (simplified - would need time-based tracking)
            # For now, just use basic values
            if self.stats.last_activity > 0:
                elapsed = time.time() - self.stats.last_activity
                if (
                    elapsed > 0
                ):  # pragma: no cover - Defensive: elapsed should always be > 0 when last_activity is set, but guard against edge cases
                    self.stats.download_rate = (
                        self.utp_connection.bytes_received / elapsed
                    )
                    self.stats.upload_rate = self.utp_connection.bytes_sent / elapsed

            # Map uTP connection state
            utp_state = self.utp_connection.state
            mapped_state = self._state_map.get(
                utp_state,
                ConnectionState.DISCONNECTED,  # pragma: no cover - Defensive: fallback for unknown uTP states
            )
            if mapped_state != self.state:
                self.state = mapped_state

    def is_connected(self) -> bool:
        """Check if uTP connection is established."""
        if self.utp_connection is None:
            return False
        return self.utp_connection.state == UTPConnectionState.CONNECTED

    def has_timed_out(self, timeout: float = 60.0) -> bool:
        """Check if connection has timed out."""
        if self.utp_connection is None:
            return True

        # Check uTP connection's last activity
        if self.utp_connection.last_recv_time > 0:
            elapsed = time.perf_counter() - self.utp_connection.last_recv_time
            return elapsed > timeout

        return super().has_timed_out(timeout)

    @classmethod
    async def accept(
        cls, utp_connection: UTPConnection, peer_info: Any
    ) -> UTPPeerConnection:
        """Accept an incoming uTP connection (passive connection).

        Args:
            utp_connection: Already established uTP connection (from socket manager)
            peer_info: Peer information (extracted from connection or provided)

        Returns:
            UTPPeerConnection instance for the accepted connection

        """
        # Create peer connection wrapper
        peer_conn = cls(
            peer_info=peer_info,
            torrent_data={},  # Will be set by caller if needed
        )

        # Set the uTP connection
        peer_conn.utp_connection = utp_connection

        # Wait for connection to be fully established (if still in handshake)
        if utp_connection.state == UTPConnectionState.SYN_RECEIVED:
            timeout = 30.0
            start_time = time.perf_counter()
            while (
                utp_connection.state != UTPConnectionState.CONNECTED
                and time.perf_counter() - start_time < timeout
            ):
                await asyncio.sleep(0.1)

            if utp_connection.state != UTPConnectionState.CONNECTED:
                msg = "uTP passive connection failed to complete handshake"
                raise ConnectionError(msg)

        # Create stream adapters
        peer_conn.reader = UTPStreamReader(utp_connection)  # type: ignore[assignment]
        peer_conn.writer = UTPStreamWriter(utp_connection)  # type: ignore[assignment]

        # Update state
        peer_conn.state = ConnectionState.CONNECTED
        peer_conn.stats.last_activity = time.time()

        # Start message receiving task
        peer_conn.connection_task = asyncio.create_task(peer_conn._receive_messages())

        logger.info(
            "Accepted uTP peer connection from %s:%s",
            peer_info.ip,
            peer_info.port,
        )

        return peer_conn
