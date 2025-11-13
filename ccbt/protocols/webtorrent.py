"""WebTorrent protocol implementation.

from __future__ import annotations

Provides WebRTC-based peer-to-peer communication
compatible with WebTorrent clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import web

from ccbt.models import PeerInfo, TorrentInfo
from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolState,
    ProtocolType,
)
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from aiohttp.web import Application, WebSocketResponse

logger = logging.getLogger(__name__)


@dataclass
class WebRTCConnection:
    """WebRTC connection information."""

    peer_id: str
    data_channel: Any | None = None  # RTCDataChannel
    connection_state: str = "new"
    ice_connection_state: str = "new"
    last_activity: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0


class WebTorrentProtocol(Protocol):
    """WebTorrent protocol implementation."""

    def __init__(self, session_manager: Any | None = None):
        """Initialize WebTorrent protocol.

        Args:
            session_manager: Optional session manager reference for accessing shared components

        """
        super().__init__(ProtocolType.WEBTORRENT)

        # CRITICAL FIX: Store session manager reference
        # This allows protocol to use shared components (WebSocket server, WebRTC manager)
        self.session_manager = session_manager

        # WebTorrent-specific capabilities
        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=True,
            supports_dht=False,
            supports_webrtc=True,
            supports_ipfs=False,
            max_connections=100,
            supports_ipv6=True,
        )

        # WebRTC connections
        self.webrtc_connections: dict[str, WebRTCConnection] = {}
        self.data_channels: dict[str, Any] = {}

        # Message queue for received messages
        self._message_queue: dict[str, asyncio.Queue[bytes]] = {}

        # Message buffer for handling partial messages
        self._message_buffer: dict[str, bytes] = {}

        # Pending messages for connecting data channels
        self._pending_messages: dict[str, list[bytes]] = {}

        # Background task for retrying pending messages
        self._retry_task: asyncio.Task | None = None

        # CRITICAL FIX: WebSocket server is now managed at daemon startup
        # Use shared server from session manager instead of creating new one
        # This prevents port conflicts and socket recreation issues
        self.websocket_server: Application | None = None
        self.websocket_connections: set[WebSocketResponse] = set()
        self.websocket_connections_by_peer: dict[str, WebSocketResponse] = {}

        # CRITICAL FIX: WebRTC connection manager is now initialized at daemon startup
        # Use shared manager from session manager instead of creating new one
        # This ensures proper resource management and prevents duplicate managers
        self.webrtc_manager: Any | None = None

        # Tracker URLs for WebTorrent
        self.tracker_urls: list[str] = []

    def _get_webrtc_manager(self) -> Any | None:
        """Get WebRTC manager from session manager.

        CRITICAL FIX: WebRTC manager should be initialized at daemon startup.
        This method ensures we use the shared manager from session manager.

        Returns:
            WebRTCConnectionManager instance or None if not available

        """
        # Use cached reference if available
        if self.webrtc_manager is not None:
            return self.webrtc_manager

        # Try to get from session manager
        if self.session_manager and hasattr(self.session_manager, "webrtc_manager"):
            self.webrtc_manager = self.session_manager.webrtc_manager
            if self.webrtc_manager:
                logger.debug("Retrieved shared WebRTC manager from session manager")
            else:
                logger.warning(
                    "WebRTC manager not initialized at daemon startup. "
                    "WebTorrent WebRTC features will not work."
                )
            return self.webrtc_manager

        logger.warning(
            "WebRTC manager not available and session manager not accessible. "
            "This should not happen in normal daemon operation."
        )
        return None

    async def start(self) -> None:
        """Start WebTorrent protocol."""
        try:
            # CRITICAL FIX: Use shared WebSocket server from session manager
            # WebSocket server should have been initialized at daemon startup
            # If not available, log warning but continue (may be disabled)
            if self.session_manager and hasattr(
                self.session_manager, "webtorrent_websocket_server"
            ):
                ws_server_info = self.session_manager.webtorrent_websocket_server
                if ws_server_info and isinstance(ws_server_info, dict):
                    self.websocket_server = ws_server_info.get("app")
                    logger.info(
                        "Using shared WebSocket server from session manager (host=%s, port=%d)",
                        ws_server_info.get("host", "unknown"),
                        ws_server_info.get("port", 0),
                    )
                else:
                    logger.warning(
                        "WebTorrent WebSocket server not initialized at daemon startup. "
                        "WebTorrent signaling may not work. "
                        "Ensure WebTorrent is enabled in config and daemon was started properly."
                    )
            else:
                logger.warning(
                    "Session manager not available or WebSocket server not initialized. "
                    "WebTorrent signaling may not work."
                )

            # CRITICAL FIX: Use shared WebRTC manager from session manager
            # WebRTC manager should have been initialized at daemon startup
            if self.session_manager and hasattr(self.session_manager, "webrtc_manager"):
                self.webrtc_manager = self.session_manager.webrtc_manager
                if self.webrtc_manager:
                    logger.info(
                        "Using shared WebRTC connection manager from session manager"
                    )
                else:
                    logger.warning(
                        "WebRTC manager not initialized at daemon startup. "
                        "WebTorrent WebRTC features may not work. "
                        "Ensure aiortc is installed and WebTorrent is enabled."
                    )
            else:
                logger.warning(
                    "Session manager not available or WebRTC manager not initialized. "
                    "WebTorrent WebRTC features may not work."
                )

            # CRITICAL FIX: Register this protocol instance with session manager
            # The shared WebSocket handler will route connections to registered protocols
            if self.websocket_server and self.session_manager:
                # Register this protocol instance for WebSocket routing
                if not hasattr(self.session_manager, "_webtorrent_protocols"):
                    self.session_manager._webtorrent_protocols = []  # type: ignore[attr-defined]
                if self not in self.session_manager._webtorrent_protocols:  # type: ignore[attr-defined]
                    self.session_manager._webtorrent_protocols.append(self)  # type: ignore[attr-defined]
                    logger.debug(
                        "Registered WebTorrent protocol instance with session manager for WebSocket routing"
                    )

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": "webtorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop WebTorrent protocol."""
        try:
            # Cancel retry task if running
            if self._retry_task and not self._retry_task.done():
                self._retry_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._retry_task

            # Close all WebRTC connections
            for connection in self.webrtc_connections.values():
                if connection.data_channel:
                    connection.data_channel.close()

            # Clear pending messages
            self._pending_messages.clear()

            # CRITICAL FIX: Unregister this protocol instance from session manager
            if self.session_manager and hasattr(
                self.session_manager, "_webtorrent_protocols"
            ):
                if self in self.session_manager._webtorrent_protocols:  # type: ignore[attr-defined]
                    self.session_manager._webtorrent_protocols.remove(self)  # type: ignore[attr-defined]
                    logger.debug(
                        "Unregistered WebTorrent protocol instance from session manager"
                    )

            # CRITICAL FIX: Don't close shared WebSocket server
            # The server is managed at daemon level, not per-protocol instance
            # Just clear our connections but leave the server running
            self.websocket_connections.clear()
            self.websocket_connections_by_peer.clear()

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": "webtorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def _start_websocket_server(self) -> None:
        """Start WebSocket server for signaling.

        CRITICAL FIX: This method is deprecated - WebSocket server should be initialized
        at daemon startup via start_webtorrent_components(). This method now uses the
        shared server from session manager if available, or logs a warning.
        """
        # CRITICAL FIX: Use shared WebSocket server from session manager
        # Server should have been initialized at daemon startup
        if self.session_manager and hasattr(
            self.session_manager, "webtorrent_websocket_server"
        ):
            ws_server_info = self.session_manager.webtorrent_websocket_server
            if ws_server_info and isinstance(ws_server_info, dict):
                self.websocket_server = ws_server_info.get("app")
                logger.info(
                    "Using shared WebSocket server from session manager (host=%s, port=%d)",
                    ws_server_info.get("host", "unknown"),
                    ws_server_info.get("port", 0),
                )
                # Register handler with shared server
                if self.websocket_server:
                    self.websocket_server.router.add_get(
                        "/signaling", self._websocket_handler
                    )
                return

        # Fallback: log warning if shared server not available
        # This should not happen in normal daemon operation
        logger.warning(
            "WebSocket server not available from session manager. "
            "WebTorrent signaling will not work. "
            "Ensure WebTorrent is enabled in config and daemon was started properly. "
            "This method should not be called directly - server is initialized at daemon startup."
        )
        self.websocket_server = None

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:  # type: ignore[attr-defined]
        """Handle WebSocket connections for signaling."""
        ws = web.WebSocketResponse()  # type: ignore[attr-defined]
        await ws.prepare(request)

        self.websocket_connections.add(ws)
        peer_id: str | None = None

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # Try to extract peer_id from message for tracking
                    try:
                        data = json.loads(msg.data)
                        msg_peer_id = data.get("peer_id")
                        if msg_peer_id:
                            peer_id = msg_peer_id
                            self.websocket_connections_by_peer[peer_id] = ws
                    except (json.JSONDecodeError, KeyError):
                        pass  # Not all messages have peer_id

                    await self._handle_signaling_message(ws, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.debug("WebSocket error: %s", ws.exception())
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.debug("WebSocket connection closed")
                    break
        finally:
            self.websocket_connections.discard(ws)
            # Clean up peer mapping
            if peer_id and peer_id in self.websocket_connections_by_peer:
                del self.websocket_connections_by_peer[peer_id]

        return ws

    async def _handle_signaling_message(
        self,
        ws: web.WebSocketResponse,  # type: ignore[attr-defined]
        message: str,
    ) -> None:
        """Handle WebRTC signaling messages."""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "offer":
                await self._handle_offer(ws, data)
            elif message_type == "answer":
                await self._handle_answer(ws, data)
            elif message_type == "ice-candidate":
                await self._handle_ice_candidate(ws, data)
            elif message_type == "peer-info":
                await self._handle_peer_info(ws, data)

        except Exception as e:
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "webtorrent",
                        "error": f"Signaling error: {e!s}",
                        "timestamp": time.time(),
                    },
                ),
            )

    async def _handle_offer(
        self,
        ws: web.WebSocketResponse,  # type: ignore[attr-defined]
        data: dict[str, Any],
    ) -> None:
        """Handle WebRTC offer.

        Args:
            ws: WebSocket connection
            data: Offer data containing SDP and peer_id

        """
        try:
            # Extract offer SDP from message
            offer_sdp = data.get("sdp", {})
            peer_id = data.get("peer_id", "")

            # Validate offer format
            if not offer_sdp or not isinstance(offer_sdp, dict):
                logger.warning("Invalid offer format: missing or invalid SDP")
                await ws.send_json({"type": "error", "message": "Invalid offer format"})
                return

            if "type" not in offer_sdp or offer_sdp.get("type") != "offer":
                logger.warning("Invalid offer type")
                await ws.send_json({"type": "error", "message": "Invalid offer type"})
                return

            if not peer_id:
                logger.warning("Missing peer_id in offer")
                await ws.send_json({"type": "error", "message": "Missing peer_id"})
                return

            # CRITICAL FIX: Use shared WebRTC manager from session manager
            self.webrtc_manager = self._get_webrtc_manager()

            # Type check: webrtc_manager should not be None here
            if self.webrtc_manager is None:
                await ws.send_json(
                    {"type": "error", "message": "WebRTC manager not initialized"}
                )
                return

            # Create RTCPeerConnection with timeout
            try:
                # Use asyncio.wait_for for timeout (Python 3.8+ compatible)
                async def _handle_offer_async():
                    # Create peer connection
                    if self.webrtc_manager is None:
                        msg = "WebRTC manager not initialized"
                        raise RuntimeError(msg)
                    pc = await self.webrtc_manager.create_peer_connection(peer_id)

                    # Set remote description (offer)
                    try:
                        from aiortc import (
                            RTCSessionDescription,
                        )
                    except ImportError:  # pragma: no cover - optional webrtc dependency
                        msg = (
                            "aiortc not available, install with: uv sync --extra webrtc"
                        )
                        raise RuntimeError(msg) from None

                    offer = RTCSessionDescription(
                        sdp=offer_sdp.get("sdp", ""),
                        type=offer_sdp.get("type", "offer"),
                    )
                    await pc.setRemoteDescription(offer)

                    # Create data channel
                    if self.webrtc_manager is None:
                        msg = "WebRTC manager not initialized"
                        raise RuntimeError(msg)
                    data_channel = self.webrtc_manager.create_data_channel(
                        peer_id,
                        pc,
                        channel_name="webtorrent",
                        ordered=True,
                    )

                    # Set up message handler for data channel
                    @data_channel.on("message")
                    def on_message(message):
                        # Process message with framing support
                        message_bytes = (
                            message if isinstance(message, bytes) else message.encode()
                        )
                        # Use asyncio to call async method from sync callback
                        _task = asyncio.create_task(
                            self._process_received_data(peer_id, message_bytes)
                        )
                        # Store task reference to avoid garbage collection
                        del _task  # Task runs in background, no need to keep reference

                    # Generate answer
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)

                    # Store WebSocket connection for this peer
                    self.websocket_connections_by_peer[peer_id] = ws

                    # Store connection
                    connection = WebRTCConnection(
                        peer_id=peer_id,
                        data_channel=data_channel,
                        connection_state="connecting",
                        ice_connection_state="new",
                        last_activity=time.time(),
                    )
                    self.webrtc_connections[peer_id] = connection

                    # Send answer via WebSocket
                    answer_data = {
                        "type": "answer",
                        "sdp": {
                            "type": answer.type,
                            "sdp": answer.sdp,
                        },
                        "peer_id": self._generate_peer_id(),
                    }
                    await ws.send_json(answer_data)

                    logger.info("Handled offer from peer %s, sent answer", peer_id)

                # Execute with 30 second timeout
                await asyncio.wait_for(_handle_offer_async(), timeout=30.0)

            except asyncio.TimeoutError:
                logger.exception("Timeout handling offer from peer %s", peer_id)
                await ws.send_json(
                    {"type": "error", "message": "Offer processing timeout"}
                )
                # Cleanup
                if peer_id in self.webrtc_connections:
                    await self.webrtc_manager.close_peer_connection(peer_id)
                    del self.webrtc_connections[peer_id]
                return
            except Exception as e:
                logger.exception("Error handling offer from peer %s", peer_id)
                await ws.send_json({"type": "error", "message": str(e)})
                # Cleanup
                if peer_id in self.webrtc_connections:
                    await self.webrtc_manager.close_peer_connection(peer_id)
                    del self.webrtc_connections[peer_id]
                return

        except Exception:
            logger.exception("Unexpected error in _handle_offer")
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "error", "message": "Internal error"})

    async def _handle_answer(
        self,
        _ws: web.WebSocketResponse,  # type: ignore[attr-defined]
        data: dict[str, Any],
    ) -> None:
        """Handle WebRTC answer.

        Args:
            ws: WebSocket connection
            data: Answer data containing SDP and peer_id

        """
        try:
            # Extract answer SDP
            answer_sdp = data.get("sdp", {})
            peer_id = data.get("peer_id", "")

            # Find existing connection
            if peer_id not in self.webrtc_connections:
                logger.warning("Answer for unknown peer: %s", peer_id)
                return

            connection = self.webrtc_connections[peer_id]

            # Validate answer format
            if not answer_sdp or not isinstance(answer_sdp, dict):
                logger.warning("Invalid answer format: missing or invalid SDP")
                return

            if "type" not in answer_sdp or answer_sdp.get("type") != "answer":
                logger.warning("Invalid answer type")
                return

            # CRITICAL FIX: Use shared WebRTC manager from session manager
            self.webrtc_manager = self._get_webrtc_manager()
            # CRITICAL FIX: Use shared WebRTC manager from session manager
            self.webrtc_manager = self._get_webrtc_manager()
            if self.webrtc_manager is None:
                logger.error("WebRTC manager not initialized")
                return

            # Get RTCPeerConnection from manager
            if peer_id not in self.webrtc_manager.connections:
                logger.warning(
                    "Peer connection not found in manager for peer %s", peer_id
                )
                return

            pc = self.webrtc_manager.connections[peer_id]

            # Set remote description (answer)
            try:
                from aiortc import RTCSessionDescription
            except ImportError:
                msg = "aiortc is not installed. Install with: uv sync --extra webrtc"
                raise ImportError(msg) from None

            answer = RTCSessionDescription(
                sdp=answer_sdp.get("sdp", ""),
                type=answer_sdp.get("type", "answer"),
            )
            await pc.setRemoteDescription(answer)

            # Update connection state
            connection.connection_state = "connected"
            connection.last_activity = time.time()

            # Emit connection established event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTED.value,
                    data={
                        "protocol_type": "webtorrent",
                        "peer_id": peer_id,
                        "timestamp": time.time(),
                    },
                ),
            )

            logger.info("Handled answer from peer %s, connection established", peer_id)

        except Exception:
            logger.exception("Error handling answer")

    async def _handle_ice_candidate(
        self,
        _ws: web.WebSocketResponse,  # type: ignore[attr-defined]
        data: dict[str, Any],
    ) -> None:
        """Handle ICE candidate.

        Args:
            ws: WebSocket connection
            data: ICE candidate data containing candidate information and peer_id

        """
        try:
            # Extract candidate
            candidate_dict = data.get("candidate", {})
            peer_id = data.get("peer_id", "")

            # Find connection
            if peer_id not in self.webrtc_connections:
                logger.debug("ICE candidate for unknown peer: %s", peer_id)
                return

            # CRITICAL FIX: Use shared WebRTC manager from session manager
            self.webrtc_manager = self._get_webrtc_manager()
            if self.webrtc_manager is None:
                logger.error("WebRTC manager not initialized")
                return

            # Get RTCPeerConnection from manager
            if peer_id not in self.webrtc_manager.connections:
                logger.debug(
                    "Peer connection not found in manager for peer %s", peer_id
                )
                return

            pc = self.webrtc_manager.connections[peer_id]

            # Create RTCIceCandidate
            try:
                from aiortc import RTCIceCandidate
            except ImportError:
                msg = "aiortc is not installed. Install with: uv sync --extra webrtc"
                raise ImportError(msg) from None

            candidate = RTCIceCandidate(
                component=candidate_dict.get("component", 1),
                foundation=candidate_dict.get("foundation", ""),
                ip=candidate_dict.get("ip", ""),
                port=candidate_dict.get("port", 0),
                priority=candidate_dict.get("priority", 0),
                protocol=candidate_dict.get("protocol", "udp"),
                type=candidate_dict.get("type", "host"),
                sdpMid=candidate_dict.get("sdpMid"),
                sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            )

            # Add candidate to peer connection
            await pc.addIceCandidate(candidate)

            logger.debug(
                "Added ICE candidate for peer %s: %s %s:%s",
                peer_id,
                candidate.type,
                candidate.ip,
                candidate.port,
            )

        except Exception:
            logger.exception("Error handling ICE candidate")

    async def _handle_peer_info(
        self,
        _ws: web.WebSocketResponse,  # type: ignore[attr-defined]
        data: dict[str, Any],
    ) -> None:
        """Handle peer information."""
        peer_id = data.get("peer_id")
        if peer_id:
            # Create peer info
            peer_info = PeerInfo(
                ip="webrtc",  # WebRTC doesn't use traditional IP addresses
                port=0,
                peer_id=peer_id.encode(),
            )

            self.add_peer(peer_info)

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a WebTorrent peer.

        Args:
            peer_info: Peer information to connect to

        Returns:
            True if connection initiated successfully, False otherwise

        """
        from ccbt.config.config import get_config

        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""
        if not peer_id:
            logger.warning("Cannot connect to peer without peer_id")
            return False

        try:
            # CRITICAL FIX: Use shared WebRTC manager from session manager
            # Manager should have been initialized at daemon startup
            if self.webrtc_manager is None:
                if self.session_manager and hasattr(
                    self.session_manager, "webrtc_manager"
                ):
                    self.webrtc_manager = self.session_manager.webrtc_manager
                    if self.webrtc_manager:
                        logger.debug(
                            "Using shared WebRTC manager from session manager in connect_peer"
                        )
                    else:
                        logger.warning(
                            "WebRTC manager not initialized at daemon startup. "
                            "WebTorrent WebRTC features will not work."
                        )
                        self.stats.connections_failed += 1
                        return False
                else:
                    logger.warning(
                        "WebRTC manager not available and session manager not accessible. "
                        "This should not happen in normal daemon operation."
                    )
                    self.stats.connections_failed += 1
                    return False

            # Create ICE candidate callback to send via WebSocket
            async def ice_candidate_callback(
                peer_id: str, candidate: dict[str, Any] | None
            ):
                """Send ICE candidate via WebSocket."""
                if candidate is None:
                    return  # End of candidates

                ws = self.websocket_connections_by_peer.get(peer_id)
                if ws and not ws.closed:
                    candidate_data = {
                        "type": "ice-candidate",
                        "candidate": candidate,
                        "peer_id": peer_id,
                    }
                    try:
                        await ws.send_json(candidate_data)
                    except Exception as e:
                        logger.debug("Failed to send ICE candidate: %s", e)

            # Create RTCPeerConnection
            pc = await self.webrtc_manager.create_peer_connection(
                peer_id,
                ice_candidate_callback=ice_candidate_callback,
            )

            # Create data channel
            data_channel = self.webrtc_manager.create_data_channel(
                peer_id,
                pc,
                channel_name="webtorrent",
                ordered=True,
            )

            # Set up message handler for data channel
            @data_channel.on("message")
            def on_message(message):
                # Process message with framing support
                message_bytes = (
                    message if isinstance(message, bytes) else message.encode()
                )
                # Use asyncio to call async method from sync callback
                _task = asyncio.create_task(
                    self._process_received_data(peer_id, message_bytes)
                )
                # Store task reference to avoid garbage collection
                del _task  # Task runs in background, no need to keep reference

            # Set up data channel state handlers
            @data_channel.on("open")
            def on_open():
                if peer_id in self.webrtc_connections:
                    conn = self.webrtc_connections[peer_id]
                    conn.connection_state = "connected"

            @data_channel.on("close")
            def on_close():
                if peer_id in self.webrtc_connections:
                    conn = self.webrtc_connections[peer_id]
                    conn.connection_state = "closed"

            # Generate WebRTC offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            # Store connection
            connection = WebRTCConnection(
                peer_id=peer_id,
                data_channel=data_channel,
                connection_state="connecting",
                ice_connection_state="new",
                last_activity=time.time(),
            )
            self.webrtc_connections[peer_id] = connection

            # Send offer via WebSocket signaling
            offer_data = {
                "type": "offer",
                "sdp": {
                    "type": offer.type,
                    "sdp": offer.sdp,
                },
                "peer_id": peer_id,
            }

            # Try to find existing WebSocket connection or create new one
            ws = self.websocket_connections_by_peer.get(peer_id)
            if not ws or ws.closed:
                # If no WebSocket connection exists, we need to connect to signaling server
                # For now, log and wait for answer to come via signaling
                logger.warning(
                    "No WebSocket connection for peer %s, offer queued", peer_id
                )
                # Store pending offer to send when WebSocket connects
                # In a full implementation, we'd connect to the signaling server here
            else:
                await ws.send_json(offer_data)

            # Wait for answer and ICE candidates (with timeout)
            config = get_config()
            timeout = config.network.webtorrent.webtorrent_connection_timeout

            try:
                # Wait for connection to be established
                async def wait_for_connection():
                    while True:
                        if peer_id in self.webrtc_connections:
                            conn = self.webrtc_connections[peer_id]
                            if conn.connection_state == "connected":
                                return True
                            if conn.connection_state in {"failed", "closed"}:
                                return False
                        await asyncio.sleep(0.1)

                connected = await asyncio.wait_for(
                    wait_for_connection(), timeout=timeout
                )
                if connected:
                    self.stats.connections_established += 1
                    self.update_stats()
                    logger.info("Successfully connected to WebTorrent peer %s", peer_id)
                    return True
                self.stats.connections_failed += 1
                self.update_stats(errors=1)
                return False

            except asyncio.TimeoutError:
                logger.warning(
                    "Connection to peer %s timed out after %s s", peer_id, timeout
                )
                self.stats.connections_failed += 1
                self.update_stats(errors=1)
                # Cleanup
                await self.disconnect_peer(peer_id)
                return False

        except Exception as e:
            logger.exception("Error connecting to WebTorrent peer %s", peer_id)
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTION_FAILED.value,
                    data={
                        "protocol_type": "webtorrent",
                        "peer_id": peer_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            # Cleanup on failure
            if peer_id in self.webrtc_connections:
                await self.disconnect_peer(peer_id)

            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a WebTorrent peer."""
        if peer_id in self.webrtc_connections:
            connection = self.webrtc_connections[peer_id]

            # Close data channel
            if connection.data_channel:
                connection.data_channel.close()

            # Clean up buffers and queues
            self._cleanup_peer_buffers(peer_id)

            # Remove connection
            del self.webrtc_connections[peer_id]
            self.remove_peer(peer_id)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to WebTorrent peer.

        Args:
            peer_id: Peer identifier
            message: Message bytes to send

        Returns:
            True if message sent successfully, False otherwise

        """
        if peer_id not in self.webrtc_connections:
            logger.debug("Peer %s not in connections", peer_id)
            return False

        connection = self.webrtc_connections[peer_id]

        # Verify data channel exists and is open
        if not connection.data_channel:
            logger.debug("Data channel not available for peer %s", peer_id)
            return False

        # Check data channel state (aiortc uses 'readyState' attribute)
        try:
            # aiortc data channels have 'readyState' property
            channel_state = getattr(connection.data_channel, "readyState", None)
            if channel_state != "open":
                logger.debug(
                    "Data channel not open for peer %s, state: %s",
                    peer_id,
                    channel_state,
                )
                # Queue message for later if channel is connecting
                if channel_state == "connecting":
                    # Queue message for retry when channel opens
                    if peer_id not in self._pending_messages:
                        self._pending_messages[peer_id] = []
                    self._pending_messages[peer_id].append(message)
                    logger.debug(
                        "Queued message for peer %s (channel connecting)", peer_id
                    )
                    # Start retry task if not already running
                    if self._retry_task is None or self._retry_task.done():
                        self._retry_task = asyncio.create_task(
                            self._retry_pending_messages()
                        )
                return False
        except AttributeError:
            # Fallback: try to send anyway if readyState not available
            logger.debug("Could not check data channel state for peer %s", peer_id)

        try:
            # Send message through data channel
            # Note: aiortc data channels are synchronous, but we wrap in try/except
            connection.data_channel.send(message)
            connection.bytes_sent += len(message)
            connection.last_activity = time.time()

            self.update_stats(bytes_sent=len(message), messages_sent=1)

            return True

        except Exception as e:
            logger.debug("Error sending message to peer %s: %s", peer_id, e)
            self.update_stats(errors=1)

            # Check if channel closed and update state
            try:
                if connection.data_channel:
                    channel_state = getattr(connection.data_channel, "readyState", None)
                    if channel_state == "closed":
                        connection.connection_state = "closed"
            except Exception:
                pass

            return False

    async def _retry_pending_messages(self) -> None:
        """Retry sending pending messages when data channels become open.

        Periodically checks pending messages and attempts to send them
        when the data channel state becomes 'open'.
        """
        while True:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms

                # Process pending messages for each peer
                peers_to_remove = []
                for peer_id, messages in list(self._pending_messages.items()):
                    if not messages:
                        peers_to_remove.append(peer_id)
                        continue

                    # Check if peer connection exists
                    if peer_id not in self.webrtc_connections:
                        peers_to_remove.append(peer_id)
                        continue

                    connection = self.webrtc_connections[peer_id]

                    # Check if data channel is now open
                    if connection.data_channel:
                        try:
                            channel_state = getattr(
                                connection.data_channel, "readyState", None
                            )
                            if channel_state == "open":
                                # Send all pending messages
                                while messages:
                                    message = messages.pop(0)
                                    try:
                                        connection.data_channel.send(message)
                                        connection.bytes_sent += len(message)
                                        connection.last_activity = time.time()
                                        self.update_stats(
                                            bytes_sent=len(message), messages_sent=1
                                        )
                                        logger.debug(
                                            "Sent queued message to peer %s", peer_id
                                        )
                                    except Exception as e:
                                        logger.debug(
                                            "Error sending queued message to peer %s: %s",
                                            peer_id,
                                            e,
                                        )
                                        # Put message back at front for retry
                                        messages.insert(0, message)
                                        break

                                # Remove peer from pending if all messages sent
                                if not messages:
                                    peers_to_remove.append(peer_id)
                        except AttributeError:
                            # readyState not available, skip this peer
                            pass

                # Clean up peers with no pending messages
                for peer_id in peers_to_remove:
                    self._pending_messages.pop(peer_id, None)

                # Stop if no pending messages
                if not self._pending_messages:
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Error in retry pending messages: %s", e)
                await asyncio.sleep(1)  # Wait longer on error

    async def _process_received_data(self, peer_id: str, data: bytes) -> None:
        """Process received data and handle message framing.

        Handles multi-message packets and partial messages by:
        1. Appending to buffer
        2. Parsing BitTorrent message format (4-byte length prefix)
        3. Extracting complete messages
        4. Queuing complete messages for receive_message()

        Args:
            peer_id: Peer identifier
            data: Raw data received from data channel

        """
        # Initialize buffer if needed
        if peer_id not in self._message_buffer:
            self._message_buffer[peer_id] = b""

        # Append new data to buffer
        self._message_buffer[peer_id] += data

        # Initialize queue if needed
        if peer_id not in self._message_queue:
            self._message_queue[peer_id] = asyncio.Queue()

        buffer = self._message_buffer[peer_id]

        # Process complete messages from buffer
        while len(buffer) >= 4:
            # Read message length (4 bytes, big-endian)
            message_length = int.from_bytes(buffer[0:4], "big")

            # Check for keep-alive message (length 0)
            if message_length == 0:
                # Keep-alive: consume 4 bytes and continue
                buffer = buffer[4:]
                self._message_buffer[peer_id] = buffer
                # Update activity but don't queue keep-alive
                if peer_id in self.webrtc_connections:
                    self.webrtc_connections[peer_id].last_activity = time.time()
                continue

            # Check if we have complete message
            message_size = 4 + message_length  # length prefix + payload
            if len(buffer) < message_size:
                # Partial message - keep in buffer for next packet
                break

            # Extract complete message (including length prefix)
            complete_message = buffer[0:message_size]
            buffer = buffer[message_size:]

            # Queue complete message
            self._message_queue[peer_id].put_nowait(complete_message)

            # Update connection stats
            if peer_id in self.webrtc_connections:
                conn = self.webrtc_connections[peer_id]
                conn.bytes_received += len(complete_message)
                conn.last_activity = time.time()

            # Update buffer
            self._message_buffer[peer_id] = buffer

        # Update buffer even if no messages extracted
        self._message_buffer[peer_id] = buffer

    async def receive_message(self, peer_id: str) -> bytes | None:
        """Receive message from WebTorrent peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Complete BitTorrent message bytes (with 4-byte length prefix) or None

        """
        if peer_id not in self.webrtc_connections:
            return None

        connection = self.webrtc_connections[peer_id]

        # Check if data channel is open
        if not connection.data_channel:
            return None

        # Check message queue
        if peer_id not in self._message_queue:
            return None

        queue = self._message_queue[peer_id]

        try:
            # Get message from queue with timeout (1 second)
            message = await asyncio.wait_for(queue.get(), timeout=1.0)

            # Update stats
            self.update_stats(bytes_received=len(message), messages_received=1)

            # Return complete message (already includes 4-byte length prefix)
            return message

        except asyncio.TimeoutError:
            # No message available within timeout - this is normal
            return None
        except Exception:
            logger.exception("Error receiving message from peer %s", peer_id)
            self.update_stats(errors=1)
            return None

    def _cleanup_peer_buffers(self, peer_id: str) -> None:
        """Clean up message buffers and queues for a peer.

        Args:
            peer_id: Peer identifier

        """
        if peer_id in self._message_buffer:
            del self._message_buffer[peer_id]
        if peer_id in self._message_queue:
            # Clear queue
            queue = self._message_queue[peer_id]
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent to WebTorrent trackers."""
        peers = []

        # Use WebTorrent trackers
        for tracker_url in self.tracker_urls:
            try:
                tracker_peers = await self._announce_to_tracker(
                    tracker_url,
                    torrent_info,
                )
                peers.extend(tracker_peers)
            except Exception as e:
                # Emit tracker error event
                await emit_event(
                    Event(
                        event_type=EventType.TRACKER_ERROR.value,
                        data={
                            "protocol_type": "webtorrent",
                            "tracker_url": tracker_url,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

        return peers

    async def _announce_to_tracker(
        self,
        tracker_url: str,
        torrent_info: TorrentInfo,
    ) -> list[PeerInfo]:
        """Announce to a specific WebTorrent tracker."""
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare announce data
                announce_data = {
                    "info_hash": torrent_info.info_hash.hex(),
                    "peer_id": self._generate_peer_id(),
                    "port": 8080,  # WebSocket port
                    "uploaded": 0,
                    "downloaded": 0,
                    "left": torrent_info.total_length,
                    "compact": 0,  # WebTorrent doesn't use compact format
                    "event": "started",
                }

                # Make announce request
                async with session.get(tracker_url, params=announce_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_tracker_response(data)
                    return []

        except Exception:
            return []

    def _parse_tracker_response(self, data: dict[str, Any]) -> list[PeerInfo]:
        """Parse WebTorrent tracker response."""
        peers = []

        # WebTorrent trackers return peer information in JSON format
        if "peers" in data:
            for peer_data in data["peers"]:
                if isinstance(peer_data, dict):
                    peer_info = PeerInfo(
                        ip=peer_data.get("ip", ""),
                        port=peer_data.get("port", 0),
                        peer_id=peer_data.get("peer_id", "").encode()
                        if peer_data.get("peer_id")
                        else None,
                    )
                    peers.append(peer_info)

        return peers

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics from WebTorrent trackers."""
        stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        for tracker_url in self.tracker_urls:
            try:
                tracker_stats = await self._scrape_tracker(tracker_url, torrent_info)
                stats["seeders"] += tracker_stats.get("seeders", 0)
                stats["leechers"] += tracker_stats.get("leechers", 0)
                stats["completed"] += tracker_stats.get("completed", 0)
            except Exception as e:
                logger.debug("Failed to aggregate tracker stats: %s", e)
                continue

        return stats

    async def _scrape_tracker(
        self,
        tracker_url: str,
        torrent_info: TorrentInfo,
    ) -> dict[str, int]:
        """Scrape statistics from a specific tracker."""
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare scrape data
                scrape_data = {
                    "info_hash": torrent_info.info_hash.hex(),
                }

                # Make scrape request
                async with session.get(tracker_url, params=scrape_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "seeders": data.get("seeders", 0),
                            "leechers": data.get("leechers", 0),
                            "completed": data.get("completed", 0),
                        }
                    return {}

        except Exception:
            return {}

    def _generate_peer_id(self) -> str:
        """Generate WebTorrent peer ID."""
        # WebTorrent uses a specific peer ID format
        return f"-WT0001-{hashlib.sha1(str(time.time()).encode()).hexdigest()[:12]}"  # nosec B324 - SHA-1 for peer ID generation, not security-sensitive

    def add_tracker(self, tracker_url: str) -> None:
        """Add WebTorrent tracker."""
        if tracker_url not in self.tracker_urls:
            self.tracker_urls.append(tracker_url)

    def remove_tracker(self, tracker_url: str) -> None:
        """Remove WebTorrent tracker."""
        if tracker_url in self.tracker_urls:
            self.tracker_urls.remove(tracker_url)

    def get_webrtc_connections(self) -> dict[str, WebRTCConnection]:
        """Get WebRTC connections."""
        return self.webrtc_connections.copy()

    def get_connection_stats(self, peer_id: str) -> dict[str, Any] | None:
        """Get connection statistics for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Statistics dictionary or None if peer not found

        """
        if peer_id not in self.webrtc_connections:
            return None

        connection = self.webrtc_connections[peer_id]

        stats = {
            "peer_id": peer_id,
            "connection_state": connection.connection_state,
            "ice_connection_state": connection.ice_connection_state,
            "last_activity": connection.last_activity,
            "bytes_sent": connection.bytes_sent,
            "bytes_received": connection.bytes_received,
        }

        # Integrate with metrics collector
        try:
            from ccbt.monitoring import get_metrics_collector

            metrics = get_metrics_collector()
            if metrics:
                # Record WebRTC-specific metrics
                # Note: Skip labels for simplicity (can be enhanced later)
                metrics.record_metric(
                    "webrtc_peer_bytes_sent", float(connection.bytes_sent)
                )
                metrics.record_metric(
                    "webrtc_peer_bytes_received", float(connection.bytes_received)
                )
        except (ImportError, AttributeError):
            pass  # Metrics collector not available

        return stats

    def get_all_connection_stats(self) -> dict[str, dict[str, Any]]:
        """Get connection statistics for all peers.

        Returns:
            Dictionary mapping peer_id to statistics

        """
        stats = {}

        for peer_id, connection in self.webrtc_connections.items():
            stats[peer_id] = {
                "connection_state": connection.connection_state,
                "ice_connection_state": connection.ice_connection_state,
                "last_activity": connection.last_activity,
                "bytes_sent": connection.bytes_sent,
                "bytes_received": connection.bytes_received,
            }

        # Record aggregate metrics
        try:
            from ccbt.monitoring import get_metrics_collector

            metrics = get_metrics_collector()
            if metrics:
                active_connections = sum(
                    1
                    for conn in self.webrtc_connections.values()
                    if conn.connection_state == "connected"
                )
                total_bytes_sent = sum(
                    conn.bytes_sent for conn in self.webrtc_connections.values()
                )
                total_bytes_received = sum(
                    conn.bytes_received for conn in self.webrtc_connections.values()
                )

                metrics.record_metric(
                    "webrtc_active_connections", float(active_connections)
                )
                metrics.record_metric(
                    "webrtc_total_bytes_sent", float(total_bytes_sent)
                )
                metrics.record_metric(
                    "webrtc_total_bytes_received", float(total_bytes_received)
                )
        except (ImportError, AttributeError):
            pass  # Metrics collector not available

        return stats
