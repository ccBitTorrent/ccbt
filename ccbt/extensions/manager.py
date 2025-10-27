"""Extension Manager for coordinating all BitTorrent extensions.

Provides a unified interface for managing and coordinating
all BitTorrent protocol extensions.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..events import Event, EventType, emit_event
from ..models import PeerInfo, PieceInfo
from .compact import CompactPeerLists
from .dht import DHTExtension
from .fast import FastExtension
from .pex import PeerExchange
from .protocol import ExtensionProtocol
from .webseed import WebSeedExtension


class ExtensionStatus(Enum):
    """Extension status."""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class ExtensionState:
    """Extension state information."""
    name: str
    status: ExtensionStatus
    capabilities: Dict[str, Any]
    last_activity: float
    error_count: int = 0
    last_error: Optional[str] = None


class ExtensionManager:
    """Manages all BitTorrent extensions."""

    def __init__(self):
        self.extensions: Dict[str, Any] = {}
        self.extension_states: Dict[str, ExtensionState] = {}
        self.peer_extensions: Dict[str, Dict[str, Any]] = {}  # peer_id -> extensions

        # Initialize extensions
        self._initialize_extensions()

    def _initialize_extensions(self) -> None:
        """Initialize all extensions."""
        # Fast Extension
        self.extensions["fast"] = FastExtension()
        self.extension_states["fast"] = ExtensionState(
            name="fast",
            status=ExtensionStatus.ENABLED,
            capabilities={"suggest": True, "have_all": True, "have_none": True, "reject": True, "allow_fast": True},
            last_activity=0.0,
        )

        # Extension Protocol
        self.extensions["protocol"] = ExtensionProtocol()
        self.extension_states["protocol"] = ExtensionState(
            name="protocol",
            status=ExtensionStatus.ENABLED,
            capabilities={"extensions": {}},
            last_activity=0.0,
        )

        # Peer Exchange
        self.extensions["pex"] = PeerExchange()
        self.extension_states["pex"] = ExtensionState(
            name="pex",
            status=ExtensionStatus.ENABLED,
            capabilities={"added_peers": 0, "dropped_peers": 0},
            last_activity=0.0,
        )

        # DHT
        self.extensions["dht"] = DHTExtension()
        self.extension_states["dht"] = ExtensionState(
            name="dht",
            status=ExtensionStatus.ENABLED,
            capabilities={"nodes": 0, "buckets": 0},
            last_activity=0.0,
        )

        # WebSeed
        self.extensions["webseed"] = WebSeedExtension()
        self.extension_states["webseed"] = ExtensionState(
            name="webseed",
            status=ExtensionStatus.ENABLED,
            capabilities={"webseeds": 0, "active_webseeds": 0},
            last_activity=0.0,
        )

    async def start(self) -> None:
        """Start all extensions."""
        for name, extension in self.extensions.items():
            try:
                if hasattr(extension, "start"):
                    await extension.start()

                self.extension_states[name].status = ExtensionStatus.ACTIVE
                self.extension_states[name].last_activity = time.time()

                # Emit event for extension started
                await emit_event(Event(
                    event_type=EventType.EXTENSION_STARTED.value,
                    data={
                        "extension_name": name,
                        "timestamp": time.time(),
                    },
                ))

            except Exception as e:
                self.extension_states[name].status = ExtensionStatus.ERROR
                self.extension_states[name].error_count += 1
                self.extension_states[name].last_error = str(e)

                # Emit event for extension error
                await emit_event(Event(
                    event_type=EventType.EXTENSION_ERROR.value,
                    data={
                        "extension_name": name,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

    async def stop(self) -> None:
        """Stop all extensions."""
        for name, extension in self.extensions.items():
            try:
                if hasattr(extension, "stop"):
                    await extension.stop()

                self.extension_states[name].status = ExtensionStatus.DISABLED

                # Emit event for extension stopped
                await emit_event(Event(
                    event_type=EventType.EXTENSION_STOPPED.value,
                    data={
                        "extension_name": name,
                        "timestamp": time.time(),
                    },
                ))

            except Exception as e:
                # Emit event for extension error
                await emit_event(Event(
                    event_type=EventType.EXTENSION_ERROR.value,
                    data={
                        "extension_name": name,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

    def get_extension(self, name: str) -> Optional[Any]:
        """Get extension by name."""
        return self.extensions.get(name)

    def get_extension_state(self, name: str) -> Optional[ExtensionState]:
        """Get extension state."""
        return self.extension_states.get(name)

    def list_extensions(self) -> List[str]:
        """List all extension names."""
        return list(self.extensions.keys())

    def list_active_extensions(self) -> List[str]:
        """List active extension names."""
        return [name for name, state in self.extension_states.items()
                if state.status == ExtensionStatus.ACTIVE]

    def is_extension_active(self, name: str) -> bool:
        """Check if extension is active."""
        state = self.extension_states.get(name)
        return state is not None and state.status == ExtensionStatus.ACTIVE

    def enable_extension(self, name: str) -> bool:
        """Enable extension."""
        if name in self.extension_states:
            self.extension_states[name].status = ExtensionStatus.ENABLED
            return True
        return False

    def disable_extension(self, name: str) -> bool:
        """Disable extension."""
        if name in self.extension_states:
            self.extension_states[name].status = ExtensionStatus.DISABLED
            return True
        return False

    # Fast Extension methods
    async def handle_fast_extension(self, peer_id: str, message_type: int, data: bytes) -> None:
        """Handle Fast Extension message."""
        if not self.is_extension_active("fast"):
            return

        fast_ext = self.extensions["fast"]

        try:
            if message_type == 0x0D:  # Suggest
                piece_index = fast_ext.decode_suggest(data)
                await fast_ext.handle_suggest(peer_id, piece_index)
            elif message_type == 0x0E:  # Have All
                await fast_ext.handle_have_all(peer_id)
            elif message_type == 0x0F:  # Have None
                await fast_ext.handle_have_none(peer_id)
            elif message_type == 0x10:  # Reject
                index, begin, length = fast_ext.decode_reject(data)
                await fast_ext.handle_reject(peer_id, index, begin, length)
            elif message_type == 0x11:  # Allow Fast
                piece_index = fast_ext.decode_allow_fast(data)
                await fast_ext.handle_allow_fast(peer_id, piece_index)

            self.extension_states["fast"].last_activity = time.time()

        except Exception as e:
            self.extension_states["fast"].error_count += 1
            self.extension_states["fast"].last_error = str(e)

    # Extension Protocol methods
    async def handle_extension_protocol(self, peer_id: str, message_type: int, data: bytes) -> None:
        """Handle Extension Protocol message."""
        if not self.is_extension_active("protocol"):
            return

        protocol_ext = self.extensions["protocol"]

        try:
            await protocol_ext.handle_extension_message(peer_id, message_type, data)
            self.extension_states["protocol"].last_activity = time.time()

        except Exception as e:
            self.extension_states["protocol"].error_count += 1
            self.extension_states["protocol"].last_error = str(e)

    # PEX methods
    async def handle_pex_message(self, peer_id: str, message_type: int, data: bytes) -> None:
        """Handle PEX message."""
        if not self.is_extension_active("pex"):
            return

        pex_ext = self.extensions["pex"]

        try:
            if message_type == 0:  # Added
                peers = pex_ext.decode_peers_list(data, is_ipv6=False)
                await pex_ext.handle_added_peers(peer_id, peers)
            elif message_type == 1:  # Dropped
                peers = pex_ext.decode_peers_list(data, is_ipv6=False)
                await pex_ext.handle_dropped_peers(peer_id, peers)

            self.extension_states["pex"].last_activity = time.time()

        except Exception as e:
            self.extension_states["pex"].error_count += 1
            self.extension_states["pex"].last_error = str(e)

    # DHT methods
    async def handle_dht_message(self, peer_ip: str, peer_port: int, data: bytes) -> Optional[bytes]:
        """Handle DHT message."""
        if not self.is_extension_active("dht"):
            return None

        dht_ext = self.extensions["dht"]

        try:
            response = await dht_ext.handle_dht_message(peer_ip, peer_port, data)
            self.extension_states["dht"].last_activity = time.time()
            return response

        except Exception as e:
            self.extension_states["dht"].error_count += 1
            self.extension_states["dht"].last_error = str(e)
            return None

    # WebSeed methods
    async def download_piece_from_webseed(self, webseed_id: str, piece_info: PieceInfo) -> Optional[bytes]:
        """Download piece from WebSeed."""
        if not self.is_extension_active("webseed"):
            return None

        webseed_ext = self.extensions["webseed"]

        try:
            data = await webseed_ext.download_piece(webseed_id, piece_info, b"")
            self.extension_states["webseed"].last_activity = time.time()
            return data

        except Exception as e:
            self.extension_states["webseed"].error_count += 1
            self.extension_states["webseed"].last_error = str(e)
            return None

    def add_webseed(self, url: str, name: Optional[str] = None) -> str:
        """Add WebSeed."""
        if not self.is_extension_active("webseed"):
            raise RuntimeError("WebSeed extension not active")

        webseed_ext = self.extensions["webseed"]
        return webseed_ext.add_webseed(url, name)

    def remove_webseed(self, webseed_id: str) -> None:
        """Remove WebSeed."""
        if not self.is_extension_active("webseed"):
            return

        webseed_ext = self.extensions["webseed"]
        webseed_ext.remove_webseed(webseed_id)

    # Compact Peer Lists methods
    def encode_peers_compact(self, peers: List[PeerInfo]) -> bytes:
        """Encode peers in compact format."""
        compact_peers = [CompactPeerLists.convert_peer_info_to_compact(peer) for peer in peers]
        return CompactPeerLists.encode_peers_list(compact_peers)

    def decode_peers_compact(self, data: bytes, is_ipv6: bool = False) -> List[PeerInfo]:
        """Decode peers from compact format."""
        compact_peers = CompactPeerLists.decode_peers_list(data, is_ipv6)
        return [peer.to_peer_info() for peer in compact_peers]

    # Statistics and monitoring
    def get_extension_statistics(self) -> Dict[str, Any]:
        """Get extension statistics."""
        stats = {}

        for name, state in self.extension_states.items():
            stats[name] = {
                "status": state.status.value,
                "last_activity": state.last_activity,
                "error_count": state.error_count,
                "last_error": state.last_error,
                "capabilities": state.capabilities,
            }

        return stats

    def get_peer_extensions(self, peer_id: str) -> Dict[str, Any]:
        """Get extensions supported by peer."""
        return self.peer_extensions.get(peer_id, {})

    def set_peer_extensions(self, peer_id: str, extensions: Dict[str, Any]) -> None:
        """Set peer extensions."""
        self.peer_extensions[peer_id] = extensions

    def peer_supports_extension(self, peer_id: str, extension_name: str) -> bool:
        """Check if peer supports extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        return extension_name in peer_extensions

    def get_extension_capabilities(self, extension_name: str) -> Dict[str, Any]:
        """Get extension capabilities."""
        if extension_name in self.extensions:
            ext = self.extensions[extension_name]
            if hasattr(ext, "get_capabilities"):
                return ext.get_capabilities()
            if hasattr(ext, "get_extension_statistics"):
                return ext.get_extension_statistics()

        return {}

    def get_all_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all extensions."""
        stats = {
            "total_extensions": len(self.extensions),
            "active_extensions": len(self.list_active_extensions()),
            "extensions": self.get_extension_statistics(),
            "peers_with_extensions": len(self.peer_extensions),
        }

        # Add specific extension statistics
        for name, extension in self.extensions.items():
            if hasattr(extension, "get_extension_statistics"):
                stats[f"{name}_stats"] = extension.get_extension_statistics()
            elif hasattr(extension, "get_all_statistics"):
                stats[f"{name}_stats"] = extension.get_all_statistics()

        return stats


# Global extension manager instance
_extension_manager: Optional[ExtensionManager] = None


def get_extension_manager() -> ExtensionManager:
    """Get the global extension manager."""
    global _extension_manager
    if _extension_manager is None:
        _extension_manager = ExtensionManager()
    return _extension_manager
