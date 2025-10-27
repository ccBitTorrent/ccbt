"""Base protocol abstraction for ccBitTorrent.

Provides a unified interface for different protocols including
BitTorrent, WebTorrent, and IPFS.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..events import Event, EventType, emit_event
from ..models import PeerInfo, TorrentInfo


class ProtocolType(Enum):
    """Supported protocol types."""
    BITTORRENT = "bittorrent"
    WEBTORRENT = "webtorrent"
    IPFS = "ipfs"
    HYBRID = "hybrid"


class ProtocolState(Enum):
    """Protocol connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    HANDSHAKE = "handshake"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class ProtocolCapabilities:
    """Protocol capabilities."""
    supports_encryption: bool = False
    supports_metadata: bool = False
    supports_pex: bool = False
    supports_dht: bool = False
    supports_webrtc: bool = False
    supports_ipfs: bool = False
    max_connections: int = 0
    supports_ipv6: bool = True


@dataclass
class ProtocolStats:
    """Protocol statistics."""
    bytes_sent: int = 0
    bytes_received: int = 0
    connections_established: int = 0
    connections_failed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    announces: int = 0
    errors: int = 0
    last_activity: float = 0.0


class Protocol(ABC):
    """Base protocol interface."""

    def __init__(self, protocol_type: ProtocolType):
        self.protocol_type = protocol_type
        self.state = ProtocolState.DISCONNECTED
        self.capabilities = ProtocolCapabilities()
        self.stats = ProtocolStats()
        self.peers: Dict[str, PeerInfo] = {}
        self.active_connections: Set[str] = set()

    @abstractmethod
    async def start(self) -> None:
        """Start the protocol."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the protocol."""

    @abstractmethod
    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a peer."""

    @abstractmethod
    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a peer."""

    @abstractmethod
    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to peer."""

    @abstractmethod
    async def receive_message(self, peer_id: str) -> Optional[bytes]:
        """Receive message from peer."""

    @abstractmethod
    async def announce_torrent(self, torrent_info: TorrentInfo) -> List[PeerInfo]:
        """Announce torrent and get peers."""

    @abstractmethod
    async def scrape_torrent(self, torrent_info: TorrentInfo) -> Dict[str, int]:
        """Scrape torrent statistics."""

    def get_capabilities(self) -> ProtocolCapabilities:
        """Get protocol capabilities."""
        return self.capabilities

    def get_stats(self) -> ProtocolStats:
        """Get protocol statistics."""
        return self.stats

    def get_peers(self) -> Dict[str, PeerInfo]:
        """Get connected peers."""
        return self.peers.copy()

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        """Get specific peer."""
        return self.peers.get(peer_id)

    def is_connected(self, peer_id: str) -> bool:
        """Check if peer is connected."""
        return peer_id in self.active_connections

    def get_state(self) -> ProtocolState:
        """Get protocol state."""
        return self.state

    def set_state(self, state: ProtocolState) -> None:
        """Set protocol state."""
        self.state = state

        # Emit state change event
        emit_event(Event(
            event_type=EventType.PROTOCOL_STATE_CHANGED.value,
            data={
                "protocol_type": self.protocol_type.value,
                "state": state.value,
                "timestamp": time.time(),
            },
        ))

    def update_stats(self, bytes_sent: int = 0, bytes_received: int = 0,
                    messages_sent: int = 0, messages_received: int = 0,
                    errors: int = 0) -> None:
        """Update protocol statistics."""
        self.stats.bytes_sent += bytes_sent
        self.stats.bytes_received += bytes_received
        self.stats.messages_sent += messages_sent
        self.stats.messages_received += messages_received
        self.stats.errors += errors
        self.stats.last_activity = time.time()

    def add_peer(self, peer_info: PeerInfo) -> None:
        """Add peer to protocol."""
        self.peers[peer_info.ip] = peer_info
        self.active_connections.add(peer_info.ip)

        # Emit peer added event
        emit_event(Event(
            event_type=EventType.PEER_ADDED.value,
            data={
                "protocol_type": self.protocol_type.value,
                "peer_info": {
                    "ip": peer_info.ip,
                    "port": peer_info.port,
                    "peer_id": peer_info.peer_id.hex() if peer_info.peer_id else None,
                },
                "timestamp": time.time(),
            },
        ))

    def remove_peer(self, peer_id: str) -> None:
        """Remove peer from protocol."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.active_connections.discard(peer_id)

            # Emit peer removed event
            emit_event(Event(
                event_type=EventType.PEER_REMOVED.value,
                data={
                    "protocol_type": self.protocol_type.value,
                    "peer_id": peer_id,
                    "timestamp": time.time(),
                },
            ))

    async def health_check(self) -> bool:
        """Perform health check."""
        return self.state in [ProtocolState.CONNECTED, ProtocolState.ACTIVE]

    def is_healthy(self) -> bool:
        """Synchronous health check."""
        return self.state in [ProtocolState.CONNECTED, ProtocolState.ACTIVE]

    def get_protocol_info(self) -> Dict[str, Any]:
        """Get protocol information."""
        return {
            "protocol_type": self.protocol_type.value,
            "state": self.state.value,
            "capabilities": {
                "supports_encryption": self.capabilities.supports_encryption,
                "supports_metadata": self.capabilities.supports_metadata,
                "supports_pex": self.capabilities.supports_pex,
                "supports_dht": self.capabilities.supports_dht,
                "supports_webrtc": self.capabilities.supports_webrtc,
                "supports_ipfs": self.capabilities.supports_ipfs,
                "max_connections": self.capabilities.max_connections,
                "supports_ipv6": self.capabilities.supports_ipv6,
            },
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
            "peers_count": len(self.peers),
            "active_connections": len(self.active_connections),
        }


class ProtocolManager:
    """Manages multiple protocols."""

    def __init__(self):
        self.protocols: Dict[ProtocolType, Protocol] = {}
        self.active_protocols: Set[ProtocolType] = set()
        self.protocol_stats: Dict[ProtocolType, ProtocolStats] = {}

    def register_protocol(self, protocol: Protocol) -> None:
        """Register a protocol."""
        self.protocols[protocol.protocol_type] = protocol
        self.protocol_stats[protocol.protocol_type] = ProtocolStats()

        # Emit protocol registered event
        emit_event(Event(
            event_type=EventType.PROTOCOL_REGISTERED.value,
            data={
                "protocol_type": protocol.protocol_type.value,
                "timestamp": time.time(),
            },
        ))

    def unregister_protocol(self, protocol_type: ProtocolType) -> None:
        """Unregister a protocol."""
        if protocol_type in self.protocols:
            del self.protocols[protocol_type]
            if protocol_type in self.protocol_stats:
                del self.protocol_stats[protocol_type]

            # Emit protocol unregistered event
            emit_event(Event(
                event_type=EventType.PROTOCOL_UNREGISTERED.value,
                data={
                    "protocol_type": protocol_type.value,
                    "timestamp": time.time(),
                },
            ))

    def get_protocol(self, protocol_type: ProtocolType) -> Optional[Protocol]:
        """Get protocol by type."""
        return self.protocols.get(protocol_type)

    def list_protocols(self) -> List[ProtocolType]:
        """List all registered protocols."""
        return list(self.protocols.keys())

    def list_active_protocols(self) -> List[ProtocolType]:
        """List active protocols."""
        return list(self.active_protocols)

    async def start_protocol(self, protocol_type: ProtocolType) -> bool:
        """Start a protocol."""
        protocol = self.protocols.get(protocol_type)
        if not protocol:
            return False

        try:
            await protocol.start()
            self.active_protocols.add(protocol_type)

            # Emit protocol started event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STARTED.value,
                data={
                    "protocol_type": protocol_type.value,
                    "timestamp": time.time(),
                },
            ))

            return True

        except Exception as e:
            # Emit protocol error event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_ERROR.value,
                data={
                    "protocol_type": protocol_type.value,
                    "error": str(e),
                    "timestamp": time.time(),
                },
            ))

            return False

    async def stop_protocol(self, protocol_type: ProtocolType) -> bool:
        """Stop a protocol."""
        protocol = self.protocols.get(protocol_type)
        if not protocol:
            return False

        try:
            await protocol.stop()
            self.active_protocols.discard(protocol_type)

            # Emit protocol stopped event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STOPPED.value,
                data={
                    "protocol_type": protocol_type.value,
                    "timestamp": time.time(),
                },
            ))

            return True

        except Exception as e:
            # Emit protocol error event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_ERROR.value,
                data={
                    "protocol_type": protocol_type.value,
                    "error": str(e),
                    "timestamp": time.time(),
                },
            ))

            return False

    async def start_all_protocols(self) -> Dict[ProtocolType, bool]:
        """Start all protocols."""
        results = {}

        for protocol_type in self.protocols:
            results[protocol_type] = await self.start_protocol(protocol_type)

        return results

    async def stop_all_protocols(self) -> Dict[ProtocolType, bool]:
        """Stop all protocols."""
        results = {}

        for protocol_type in list(self.active_protocols):
            results[protocol_type] = await self.stop_protocol(protocol_type)

        return results

    def get_protocol_statistics(self) -> Dict[str, Any]:
        """Get statistics for all protocols."""
        stats = {}

        for protocol_type, protocol in self.protocols.items():
            stats[protocol_type.value] = protocol.get_protocol_info()

        return stats

    def get_combined_peers(self) -> Dict[str, PeerInfo]:
        """Get peers from all active protocols."""
        all_peers = {}

        for protocol_type in self.active_protocols:
            protocol = self.protocols.get(protocol_type)
            if protocol:
                all_peers.update(protocol.get_peers())

        return all_peers

    async def announce_torrent_all(self, torrent_info: TorrentInfo) -> Dict[ProtocolType, List[PeerInfo]]:
        """Announce torrent on all active protocols."""
        results = {}

        for protocol_type in self.active_protocols:
            protocol = self.protocols.get(protocol_type)
            if protocol:
                try:
                    peers = await protocol.announce_torrent(torrent_info)
                    results[protocol_type] = peers
                except Exception as e:
                    # Emit protocol error event
                    await emit_event(Event(
                        event_type=EventType.PROTOCOL_ERROR.value,
                        data={
                            "protocol_type": protocol_type.value,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ))
                    results[protocol_type] = []

        return results

    async def health_check_all(self) -> Dict[ProtocolType, bool]:
        """Perform health check on all protocols."""
        results = {}

        for protocol_type, protocol in self.protocols.items():
            try:
                results[protocol_type] = await protocol.health_check()
            except Exception:
                results[protocol_type] = False

        return results

    def health_check_all_sync(self) -> Dict[ProtocolType, bool]:
        """Perform synchronous health check on all protocols."""
        results = {}

        for protocol_type, protocol in self.protocols.items():
            try:
                results[protocol_type] = protocol.is_healthy()
            except Exception:
                results[protocol_type] = False

        return results


# Global protocol manager instance
_protocol_manager: Optional[ProtocolManager] = None


def get_protocol_manager() -> ProtocolManager:
    """Get the global protocol manager."""
    global _protocol_manager
    if _protocol_manager is None:
        _protocol_manager = ProtocolManager()
    return _protocol_manager
