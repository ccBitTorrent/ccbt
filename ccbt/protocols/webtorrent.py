"""WebTorrent protocol implementation.

Provides WebRTC-based peer-to-peer communication
compatible with WebTorrent clients.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import aiohttp
from aiohttp import web

from ..events import Event, EventType, emit_event
from ..models import PeerInfo, TorrentInfo
from .base import Protocol, ProtocolCapabilities, ProtocolState, ProtocolType


@dataclass
class WebRTCConnection:
    """WebRTC connection information."""
    peer_id: str
    data_channel: Optional[Any] = None  # RTCDataChannel
    connection_state: str = "new"
    ice_connection_state: str = "new"
    last_activity: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0


class WebTorrentProtocol(Protocol):
    """WebTorrent protocol implementation."""

    def __init__(self):
        super().__init__(ProtocolType.WEBTORRENT)

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
        self.webrtc_connections: Dict[str, WebRTCConnection] = {}
        self.data_channels: Dict[str, Any] = {}

        # WebSocket server for signaling
        self.websocket_server: Optional[web.Application] = None
        self.websocket_connections: Set[web.WebSocketResponse] = set()

        # Tracker URLs for WebTorrent
        self.tracker_urls: List[str] = []

    async def start(self) -> None:
        """Start WebTorrent protocol."""
        try:
            # Start WebSocket server for signaling
            await self._start_websocket_server()

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STARTED.value,
                data={
                    "protocol_type": "webtorrent",
                    "timestamp": time.time(),
                },
            ))

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop WebTorrent protocol."""
        try:
            # Close all WebRTC connections
            for connection in self.webrtc_connections.values():
                if connection.data_channel:
                    connection.data_channel.close()

            # Close WebSocket server
            if self.websocket_server:
                await self.websocket_server.cleanup()

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STOPPED.value,
                data={
                    "protocol_type": "webtorrent",
                    "timestamp": time.time(),
                },
            ))

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def _start_websocket_server(self) -> None:
        """Start WebSocket server for signaling."""
        app = web.Application()

        # WebSocket endpoint for signaling
        app.router.add_get("/signaling", self._websocket_handler)

        # Start server
        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", 8080)
        await site.start()

        self.websocket_server = app

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for signaling."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websocket_connections.add(ws)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_signaling_message(ws, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self.websocket_connections.discard(ws)

        return ws

    async def _handle_signaling_message(self, ws: web.WebSocketResponse, message: str) -> None:
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
            await emit_event(Event(
                event_type=EventType.PROTOCOL_ERROR.value,
                data={
                    "protocol_type": "webtorrent",
                    "error": f"Signaling error: {e!s}",
                    "timestamp": time.time(),
                },
            ))

    async def _handle_offer(self, ws: web.WebSocketResponse, data: Dict[str, Any]) -> None:
        """Handle WebRTC offer."""
        # TODO: Implement WebRTC offer handling
        # This would involve creating an RTCPeerConnection and handling the offer

    async def _handle_answer(self, ws: web.WebSocketResponse, data: Dict[str, Any]) -> None:
        """Handle WebRTC answer."""
        # TODO: Implement WebRTC answer handling

    async def _handle_ice_candidate(self, ws: web.WebSocketResponse, data: Dict[str, Any]) -> None:
        """Handle ICE candidate."""
        # TODO: Implement ICE candidate handling

    async def _handle_peer_info(self, ws: web.WebSocketResponse, data: Dict[str, Any]) -> None:
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
        """Connect to a WebTorrent peer."""
        try:
            # Create WebRTC connection
            connection = WebRTCConnection(
                peer_id=peer_info.peer_id.hex() if peer_info.peer_id else "",
                last_activity=time.time(),
            )

            self.webrtc_connections[peer_info.ip] = connection

            # TODO: Implement actual WebRTC connection
            # This would involve creating an RTCPeerConnection and establishing a data channel

            self.stats.connections_established += 1
            self.update_stats()

            return True

        except Exception as e:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(Event(
                event_type=EventType.PEER_CONNECTION_FAILED.value,
                data={
                    "protocol_type": "webtorrent",
                    "peer_id": peer_info.peer_id.hex() if peer_info.peer_id else None,
                    "error": str(e),
                    "timestamp": time.time(),
                },
            ))

            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a WebTorrent peer."""
        if peer_id in self.webrtc_connections:
            connection = self.webrtc_connections[peer_id]

            # Close data channel
            if connection.data_channel:
                connection.data_channel.close()

            # Remove connection
            del self.webrtc_connections[peer_id]
            self.remove_peer(peer_id)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to WebTorrent peer."""
        if peer_id not in self.webrtc_connections:
            return False

        connection = self.webrtc_connections[peer_id]

        if not connection.data_channel or connection.data_channel.readyState != "open":
            return False

        try:
            # Send message through data channel
            connection.data_channel.send(message)
            connection.bytes_sent += len(message)
            connection.last_activity = time.time()

            self.update_stats(bytes_sent=len(message), messages_sent=1)

            return True

        except Exception:
            self.update_stats(errors=1)
            return False

    async def receive_message(self, peer_id: str) -> Optional[bytes]:
        """Receive message from WebTorrent peer."""
        if peer_id not in self.webrtc_connections:
            return None

        connection = self.webrtc_connections[peer_id]

        if not connection.data_channel or connection.data_channel.readyState != "open":
            return None

        try:
            # TODO: Implement message receiving from data channel
            # This would involve listening to the data channel's message event
            # For now, return None as a placeholder

            connection.last_activity = time.time()
            self.update_stats(messages_received=1)

            return None

        except Exception:
            self.update_stats(errors=1)
            return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> List[PeerInfo]:
        """Announce torrent to WebTorrent trackers."""
        peers = []

        # Use WebTorrent trackers
        for tracker_url in self.tracker_urls:
            try:
                tracker_peers = await self._announce_to_tracker(tracker_url, torrent_info)
                peers.extend(tracker_peers)
            except Exception as e:
                # Emit tracker error event
                await emit_event(Event(
                    event_type=EventType.TRACKER_ERROR.value,
                    data={
                        "protocol_type": "webtorrent",
                        "tracker_url": tracker_url,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

        return peers

    async def _announce_to_tracker(self, tracker_url: str, torrent_info: TorrentInfo) -> List[PeerInfo]:
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

    def _parse_tracker_response(self, data: Dict[str, Any]) -> List[PeerInfo]:
        """Parse WebTorrent tracker response."""
        peers = []

        # WebTorrent trackers return peer information in JSON format
        if "peers" in data:
            for peer_data in data["peers"]:
                if isinstance(peer_data, dict):
                    peer_info = PeerInfo(
                        ip=peer_data.get("ip", ""),
                        port=peer_data.get("port", 0),
                        peer_id=peer_data.get("peer_id", "").encode() if peer_data.get("peer_id") else None,
                    )
                    peers.append(peer_info)

        return peers

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> Dict[str, int]:
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
            except Exception:
                continue

        return stats

    async def _scrape_tracker(self, tracker_url: str, torrent_info: TorrentInfo) -> Dict[str, int]:
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
        return f"-WT0001-{hashlib.sha1(str(time.time()).encode()).hexdigest()[:12]}"

    def add_tracker(self, tracker_url: str) -> None:
        """Add WebTorrent tracker."""
        if tracker_url not in self.tracker_urls:
            self.tracker_urls.append(tracker_url)

    def remove_tracker(self, tracker_url: str) -> None:
        """Remove WebTorrent tracker."""
        if tracker_url in self.tracker_urls:
            self.tracker_urls.remove(tracker_url)

    def get_webrtc_connections(self) -> Dict[str, WebRTCConnection]:
        """Get WebRTC connections."""
        return self.webrtc_connections.copy()

    def get_connection_stats(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get connection statistics for a peer."""
        if peer_id not in self.webrtc_connections:
            return None

        connection = self.webrtc_connections[peer_id]

        return {
            "peer_id": peer_id,
            "connection_state": connection.connection_state,
            "ice_connection_state": connection.ice_connection_state,
            "last_activity": connection.last_activity,
            "bytes_sent": connection.bytes_sent,
            "bytes_received": connection.bytes_received,
        }

    def get_all_connection_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get connection statistics for all peers."""
        stats = {}

        for peer_id, connection in self.webrtc_connections.items():
            stats[peer_id] = {
                "connection_state": connection.connection_state,
                "ice_connection_state": connection.ice_connection_state,
                "last_activity": connection.last_activity,
                "bytes_sent": connection.bytes_sent,
                "bytes_received": connection.bytes_received,
            }

        return stats
