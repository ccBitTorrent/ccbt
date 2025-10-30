"""BitTorrent protocol wrapper.

from __future__ import annotations

Provides a protocol abstraction for the existing BitTorrent implementation.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolState,
    ProtocolType,
)
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:
    from ccbt.models import PeerInfo, TorrentInfo


class BitTorrentProtocol(Protocol):
    """BitTorrent protocol wrapper."""

    def __init__(self, session_manager=None):
        """Initialize BitTorrent protocol."""
        super().__init__(ProtocolType.BITTORRENT)
        self.session_manager = session_manager
        self.peer_manager = None
        self.tracker_manager = None

        # BitTorrent-specific capabilities
        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=True,
            supports_dht=True,
            supports_webrtc=False,
            supports_ipfs=False,
            max_connections=200,
            supports_ipv6=True,
        )

        # BitTorrent components (would be injected in real implementation)
        self.peer_manager = None
        self.tracker_manager = None
        self.dht_manager = None

    async def start(self) -> None:
        """Start BitTorrent protocol."""
        try:
            # Initialize BitTorrent components
            if self.session_manager:
                await self.session_manager.start()

            # Initialize peer manager if available
            if hasattr(self.session_manager, "peer_manager"):
                self.peer_manager = self.session_manager.peer_manager

            # Initialize tracker manager if available
            if hasattr(self.session_manager, "tracker_manager"):
                self.tracker_manager = self.session_manager.tracker_manager

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop BitTorrent protocol."""
        try:
            # Stop BitTorrent components
            if self.session_manager:
                await self.session_manager.stop()

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "connect_peer"):
                success = await self.peer_manager.connect_peer(peer_info)
                if success:
                    self.stats.connections_established += 1
                    self.update_stats()
                    return True

            # Fallback to session manager
            if self.session_manager and hasattr(self.session_manager, "connect_peer"):
                success = await self.session_manager.connect_peer(peer_info)
                if success:
                    self.stats.connections_established += 1
                    self.update_stats()
                    return True

            return False

        except Exception as e:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTION_FAILED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "peer_id": peer_info.peer_id.hex()
                        if peer_info.peer_id
                        else None,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a BitTorrent peer."""
        # TODO: Implement BitTorrent peer disconnection
        self.remove_peer(peer_id)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "send_message"):
                success = await self.peer_manager.send_message(peer_id, message)
                if success:
                    self.update_stats(bytes_sent=len(message), messages_sent=1)
                    return True

            # Fallback to session manager
            if self.session_manager and hasattr(self.session_manager, "send_message"):
                success = await self.session_manager.send_message(peer_id, message)
                if success:
                    self.update_stats(bytes_sent=len(message), messages_sent=1)
                    return True

            return False

        except Exception:
            self.update_stats(errors=1)
            return False

    async def receive_message(self, peer_id: str) -> bytes | None:
        """Receive message from BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "receive_message"):
                message = await self.peer_manager.receive_message(peer_id)
                if message:
                    self.update_stats(bytes_received=len(message), messages_received=1)
                    return message

            # Fallback to session manager
            if self.session_manager and hasattr(
                self.session_manager, "receive_message"
            ):
                message = await self.session_manager.receive_message(peer_id)
                if message:
                    self.update_stats(bytes_received=len(message), messages_received=1)
                    return message

            return None

        except Exception:
            self.update_stats(errors=1)
            return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent to BitTorrent trackers."""
        peers = []

        try:
            # Use tracker manager if available
            if self.tracker_manager and hasattr(self.tracker_manager, "announce"):
                peers = await self.tracker_manager.announce(torrent_info)

            # Fallback to session manager
            elif self.session_manager and hasattr(
                self.session_manager, "announce_torrent"
            ):
                peers = await self.session_manager.announce_torrent(torrent_info)

            return peers

        except Exception as e:
            # Emit tracker error event
            await emit_event(
                Event(
                    event_type=EventType.TRACKER_ERROR.value,
                    data={
                        "protocol_type": "bittorrent",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return peers

    async def scrape_torrent(self, _torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics from BitTorrent trackers."""
        stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        try:
            # TODO: Implement BitTorrent tracker scraping
            # This would involve using the existing tracker scraping logic

            return stats

        except Exception as e:
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "bittorrent",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return stats

    def get_bittorrent_stats(self) -> dict[str, Any]:
        """Get BitTorrent-specific statistics."""
        return {
            "protocol_type": "bittorrent",
            "state": self.state.value,
            "peers_count": len(self.peers),
            "active_connections": len(self.active_connections),
            "stats": {
                "bytes_sent": self.stats.bytes_sent,
                "bytes_received": self.stats.bytes_received,
                "connections_established": self.stats.connections_established,
                "connections_failed": self.stats.connections_failed,
                "messages_sent": self.stats.messages_sent,
                "messages_received": self.stats.messages_received,
                "errors": self.stats.errors,
                "last_activity": self.stats.last_activity,
            },
        }
