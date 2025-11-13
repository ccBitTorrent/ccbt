"""WebRTC connection manager for WebTorrent protocol.

Manages RTCPeerConnection instances, data channels, and connection lifecycle.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    # TYPE_CHECKING block is only evaluated by static type checkers, not at runtime.
    try:
        from aiortc import (
            RTCConfiguration,
            RTCDataChannel,
            RTCIceCandidate,
            RTCIceServer,
            RTCPeerConnection,
        )
    except ImportError:  # pragma: no cover - type checking only
        # aiortc may not be available during type checking
        RTCConfiguration = None  # type: ignore[assignment, misc]
        RTCDataChannel = None  # type: ignore[assignment, misc]
        RTCIceCandidate = None  # type: ignore[assignment, misc]
        RTCIceServer = None  # type: ignore[assignment, misc]
        RTCPeerConnection = None  # type: ignore[assignment, misc]
else:
    # Runtime imports - aiortc may not be installed
    try:
        from aiortc import (
            RTCConfiguration,
            RTCDataChannel,
            RTCIceCandidate,
            RTCIceServer,
            RTCPeerConnection,
        )
    except (
        ImportError
    ):  # pragma: no cover - defensive import fallback, tested via integration
        # aiortc not installed - create placeholders for runtime
        # This branch is only executed when aiortc is not installed.
        # We test this condition separately, but can't test both branches
        # in the same test run since aiortc is either installed or not.
        RTCPeerConnection = None  # type: ignore[assignment, misc]
        RTCConfiguration = None  # type: ignore[assignment, misc]
        RTCIceServer = None  # type: ignore[assignment, misc]
        RTCDataChannel = None  # type: ignore[assignment, misc]
        RTCIceCandidate = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


# Module will continue with WebRTCConnectionManager class implementation
# This is the header and imports section (lines 1-50 as specified)


class WebRTCConnectionManager:
    """Manages WebRTC peer connections and data channels."""

    def __init__(
        self,
        stun_servers: list[str] | None = None,
        turn_servers: list[str] | None = None,
        max_connections: int = 100,
    ):
        """Initialize WebRTC connection manager.

        Args:
            stun_servers: List of STUN server URLs (e.g., ["stun:stun.l.google.com:19302"])
            turn_servers: List of TURN server URLs
            max_connections: Maximum number of concurrent connections

        """
        if RTCPeerConnection is None:
            msg = "aiortc is not installed. Install with: uv sync --extra webrtc"
            raise ImportError(msg)

        # After None check, these are guaranteed to be valid classes
        # Type checker needs help understanding this
        # These checks are type guards for optional dependencies
        if RTCPeerConnection is None:
            msg = "RTCPeerConnection not available"
            raise RuntimeError(msg)
        if RTCDataChannel is None:
            msg = "RTCDataChannel not available"
            raise RuntimeError(msg)
        if RTCIceServer is None:
            msg = "RTCIceServer not available"
            raise RuntimeError(msg)
        if RTCConfiguration is None:
            msg = "RTCConfiguration not available"
            raise RuntimeError(msg)
        if RTCIceCandidate is None:
            msg = "RTCIceCandidate not available"
            raise RuntimeError(msg)

        # Connection storage
        self.connections: dict[str, RTCPeerConnection] = {}  # type: ignore[type-arg]
        self.data_channels: dict[str, RTCDataChannel] = {}  # type: ignore[type-arg]
        self.connection_stats: dict[str, dict[str, Any]] = {}

        # Configuration
        self.stun_servers = stun_servers or ["stun:stun.l.google.com:19302"]
        self.turn_servers = turn_servers or []
        self.max_connections = max_connections

        # Statistics
        self.total_connections: int = 0
        self.active_connections: int = 0
        self.failed_connections: int = 0
        self.total_bytes_sent: int = 0
        self.total_bytes_received: int = 0

        # ICE configuration
        self.ice_servers = self._build_ice_servers()

    def _build_ice_servers(self) -> list[Any]:  # type: ignore[type-arg]
        """Build ICE server configuration from STUN/TURN servers.

        Returns:
            List of RTCIceServer objects

        """
        # Assertions guarantee these are not None, but type checker needs help
        assert RTCIceServer is not None  # noqa: S101
        servers = [RTCIceServer(urls=stun_url) for stun_url in self.stun_servers]  # type: ignore[call-arg, misc]
        servers.extend(RTCIceServer(urls=turn_url) for turn_url in self.turn_servers)  # type: ignore[call-arg, misc]
        return servers

    async def create_peer_connection(
        self,
        peer_id: str,
        ice_candidate_callback: Any | None = None,
    ) -> Any:  # RTCPeerConnection, but type checker needs help
        """Create a new RTCPeerConnection instance.

        Args:
            peer_id: Unique identifier for the peer
            ice_candidate_callback: Optional callback for ICE candidates
                Callback signature: (peer_id: str, candidate: RTCIceCandidate) -> None

        Returns:
            RTCPeerConnection instance

        Raises:
            ValueError: If maximum connections exceeded

        """
        if len(self.connections) >= self.max_connections:
            msg = f"Maximum connections ({self.max_connections}) exceeded"
            raise ValueError(msg)

        if peer_id in self.connections:
            logger.warning("Connection for peer %s already exists", peer_id)
            return self.connections[peer_id]

        # Create RTCConfiguration
        # Assertions guarantee these are not None, but type checker needs help
        assert RTCConfiguration is not None  # noqa: S101
        assert RTCPeerConnection is not None  # noqa: S101
        config = RTCConfiguration(iceServers=self.ice_servers)  # type: ignore[call-arg, misc]

        # Create RTCPeerConnection
        pc = RTCPeerConnection(configuration=config)  # type: ignore[call-arg, misc]

        # Set up connection state change handler
        @pc.on(
            "connectionstatechange"
        )  # pragma: no cover - Event handler registered with RTCPeerConnection, actual invocation happens during real WebRTC events which are difficult to simulate in unit tests without full WebRTC stack
        async def on_connection_state_change():  # pragma: no cover - See above
            await self._handle_connection_state_change(peer_id, pc)

        # Set up ICE connection state change handler
        @pc.on(
            "iceconnectionstatechange"
        )  # pragma: no cover - Event handler registered with RTCPeerConnection, actual invocation happens during real WebRTC events
        async def on_ice_connection_state_change():  # pragma: no cover - See above
            await self._handle_ice_connection_state_change(peer_id, pc)

        # Set up ICE candidate handler
        @pc.on("icecandidate")
        async def on_ice_candidate(candidate: Any | None):  # RTCIceCandidate | None
            if candidate is None:
                # End of candidates
                if ice_candidate_callback:
                    await ice_candidate_callback(peer_id, None)
                return

            # Format candidate for WebSocket transmission
            candidate_dict = self._format_ice_candidate_for_websocket(candidate)

            # Call callback with formatted candidate
            if ice_candidate_callback:
                await ice_candidate_callback(peer_id, candidate_dict)

        # Store connection
        self.connections[peer_id] = pc
        self.connection_stats[peer_id] = {
            "created_at": time.time(),
            "connection_state": "new",
            "ice_connection_state": "new",
            "bytes_sent": 0,
            "bytes_received": 0,
        }

        self.total_connections += 1
        self.active_connections += 1

        logger.info("Created RTCPeerConnection for peer %s", peer_id)

        return pc

    async def _handle_connection_state_change(
        self,
        peer_id: str,
        pc: Any,  # RTCPeerConnection
    ) -> None:
        """Handle RTCPeerConnection state changes.

        Args:
            peer_id: Peer identifier
            pc: RTCPeerConnection instance

        """
        state = pc.connectionState
        if peer_id in self.connection_stats:
            self.connection_stats[peer_id]["connection_state"] = state

        logger.debug("Peer %s connection state changed to %s", peer_id, state)

        if state in {"failed", "closed"}:
            self.failed_connections += 1
            if self.active_connections > 0:
                self.active_connections -= 1

    async def _handle_ice_connection_state_change(
        self,
        peer_id: str,
        pc: Any,  # RTCPeerConnection
    ) -> None:
        """Handle ICE connection state changes.

        Args:
            peer_id: Peer identifier
            pc: RTCPeerConnection instance

        """
        state = pc.iceConnectionState
        if peer_id in self.connection_stats:
            self.connection_stats[peer_id]["ice_connection_state"] = state

        logger.debug("Peer %s ICE connection state changed to %s", peer_id, state)

        if state in {"failed", "closed"}:
            self.failed_connections += 1
            if self.active_connections > 0:
                self.active_connections -= 1

    async def close_peer_connection(self, peer_id: str) -> None:
        """Close a peer connection and clean up resources.

        Args:
            peer_id: Peer identifier

        """
        if peer_id not in self.connections:
            logger.warning("Connection for peer %s not found", peer_id)
            return

        pc = self.connections[peer_id]

        try:
            # Close data channel if exists
            if peer_id in self.data_channels:
                channel = self.data_channels[peer_id]
                channel.close()
                del self.data_channels[peer_id]

            # Close peer connection
            await pc.close()

            # Remove from tracking
            del self.connections[peer_id]
            if peer_id in self.connection_stats:
                del self.connection_stats[peer_id]

            if self.active_connections > 0:
                self.active_connections -= 1

            logger.info("Closed connection for peer %s", peer_id)

        except Exception:
            logger.exception("Error closing connection for peer %s", peer_id)

    def create_data_channel(
        self,
        peer_id: str,
        pc: Any,  # RTCPeerConnection
        channel_name: str = "webtorrent",
        ordered: bool = True,
    ) -> Any:  # RTCDataChannel
        """Create a data channel on a peer connection.

        Args:
            peer_id: Peer identifier
            pc: RTCPeerConnection instance
            channel_name: Name for the data channel
            ordered: Whether messages should be ordered

        Returns:
            RTCDataChannel instance

        """
        if peer_id not in self.connections:
            msg = f"Connection for peer {peer_id} not found"
            raise ValueError(msg)

        # Create data channel
        channel = pc.createDataChannel(channel_name, ordered=ordered)

        # Set up event handlers
        @channel.on(
            "open"
        )  # pragma: no cover - Event handler registered with RTCDataChannel, actual invocation happens during real WebRTC events
        def on_open():  # pragma: no cover - See above
            self._handle_data_channel_open(peer_id, channel)

        @channel.on(
            "close"
        )  # pragma: no cover - Event handler registered with RTCDataChannel, actual invocation happens during real WebRTC events
        def on_close():  # pragma: no cover - See above
            self._handle_data_channel_close(peer_id, channel)

        @channel.on(
            "message"
        )  # pragma: no cover - Event handler registered with RTCDataChannel, actual invocation happens during real WebRTC events
        def on_message(message):  # pragma: no cover - See above
            self._handle_data_channel_message(peer_id, channel, message)

        # Store channel
        self.data_channels[peer_id] = channel

        logger.info("Created data channel '%s' for peer %s", channel_name, peer_id)

        return channel

    def _handle_data_channel_open(
        self, peer_id: str, _channel: Any
    ) -> None:  # RTCDataChannel
        """Handle data channel open event.

        Args:
            peer_id: Peer identifier
            channel: RTCDataChannel instance

        """
        logger.info("Data channel opened for peer %s", peer_id)

    def _handle_data_channel_close(
        self, peer_id: str, _channel: Any
    ) -> None:  # RTCDataChannel
        """Handle data channel close event.

        Args:
            peer_id: Peer identifier
            channel: RTCDataChannel instance

        """
        logger.info("Data channel closed for peer %s", peer_id)
        if peer_id in self.data_channels:
            del self.data_channels[peer_id]

    def _handle_data_channel_message(
        self,
        peer_id: str,
        _channel: Any,  # RTCDataChannel
        message: Any,
    ) -> None:
        """Handle data channel message event.

        Args:
            peer_id: Peer identifier
            channel: RTCDataChannel instance
            message: Received message

        """
        # Update statistics
        if peer_id in self.connection_stats:
            message_size = (
                len(message) if isinstance(message, bytes) else len(str(message))
            )
            self.connection_stats[peer_id]["bytes_received"] += message_size
            self.total_bytes_received += message_size

        message_size = len(message) if isinstance(message, bytes) else "N/A"
        logger.debug("Received message from peer %s, size: %s", peer_id, message_size)

    def get_connection_stats(self, peer_id: str) -> dict[str, Any] | None:
        """Get connection statistics for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Statistics dictionary or None if peer not found

        """
        if peer_id not in self.connection_stats:
            return None

        stats = self.connection_stats[peer_id].copy()
        stats["peer_id"] = peer_id

        # Add current states from connection
        if peer_id in self.connections:
            pc = self.connections[peer_id]
            stats["connection_state"] = pc.connectionState
            stats["ice_connection_state"] = pc.iceConnectionState

        return stats

    def get_all_connections(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all connections.

        Returns:
            Dictionary mapping peer_id to statistics

        """
        all_stats = {}
        for peer_id in self.connection_stats:
            stats = self.get_connection_stats(peer_id)
            if stats:
                all_stats[peer_id] = stats
        return all_stats

    async def cleanup_stale_connections(self, timeout: float = 300.0) -> int:
        """Clean up stale connections that haven't been active.

        Args:
            timeout: Seconds of inactivity before considering connection stale

        Returns:
            Number of connections cleaned up

        """
        current_time = time.time()
        stale_peers: list[str] = []

        for peer_id, stats in self.connection_stats.items():
            created_at = stats.get("created_at", current_time)
            if current_time - created_at > timeout:
                stale_peers.append(peer_id)

        for peer_id in stale_peers:
            await self.close_peer_connection(peer_id)

        if stale_peers:
            logger.info("Cleaned up %s stale connections", len(stale_peers))

        return len(stale_peers)

    def _format_ice_candidate_for_websocket(
        self,
        candidate: Any,  # RTCIceCandidate
    ) -> dict[str, Any]:
        """Format ICE candidate for WebSocket transmission.

        Args:
            candidate: RTCIceCandidate instance

        Returns:
            Dictionary with candidate information formatted for WebSocket

        """
        return {
            "component": candidate.component,
            "foundation": candidate.foundation,
            "ip": candidate.ip,
            "port": candidate.port,
            "priority": candidate.priority,
            "protocol": candidate.protocol,
            "type": candidate.type,
            "sdpMid": candidate.sdpMid,
            "sdpMLineIndex": candidate.sdpMLineIndex,
        }
