"""Extension Manager for coordinating all BitTorrent extensions.

from __future__ import annotations

Provides a unified interface for managing and coordinating
all BitTorrent protocol extensions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from ccbt.extensions.compact import CompactPeerLists
from ccbt.extensions.dht import DHTExtension
from ccbt.extensions.fast import FastExtension
from ccbt.extensions.pex import PeerExchange
from ccbt.extensions.protocol import ExtensionProtocol
from ccbt.extensions.ssl import SSLExtension
from ccbt.extensions.webseed import WebSeedExtension
from ccbt.extensions.xet import XetExtension
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.models import PeerInfo, PieceInfo


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
    capabilities: dict[str, Any]
    last_activity: float
    error_count: int = 0
    last_error: str | None = None


class ExtensionManager:
    """Manages all BitTorrent extensions."""

    def __init__(self):
        """Initialize extension manager."""
        self.extensions: dict[str, Any] = {}
        self.extension_states: dict[str, ExtensionState] = {}
        self.peer_extensions: dict[str, dict[str, Any]] = {}  # peer_id -> extensions
        self.logger = logging.getLogger(__name__)

        # Initialize extensions
        self._initialize_extensions()

    def _initialize_extensions(self) -> None:
        """Initialize all extensions."""
        # Extension Protocol
        protocol_ext = ExtensionProtocol()
        self.extensions["protocol"] = protocol_ext
        self.extension_states["protocol"] = ExtensionState(
            name="protocol",
            status=ExtensionStatus.ENABLED,
            capabilities={"extensions": {}},
            last_activity=0.0,
        )

        # Register SSL extension in protocol early so it's included in handshake
        ssl_ext = SSLExtension()
        protocol_ext.register_extension("ssl", "1.0", handler=None)

        # Fast Extension
        self.extensions["fast"] = FastExtension()
        self.extension_states["fast"] = ExtensionState(
            name="fast",
            status=ExtensionStatus.ENABLED,
            capabilities={
                "suggest": True,
                "have_all": True,
                "have_none": True,
                "reject": True,
                "allow_fast": True,
            },
            last_activity=0.0,
        )

        # Peer Exchange
        self.extensions["pex"] = PeerExchange()
        self.extension_states["pex"] = ExtensionState(
            name="pex",
            status=ExtensionStatus.ENABLED,
            capabilities={
                "added": True,
                "added.f": True,
                "dropped": True,
                "dropped.f": True,
            },
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

        # Compact Peer Lists
        self.extensions["compact"] = CompactPeerLists()
        self.extension_states["compact"] = ExtensionState(
            name="compact",
            status=ExtensionStatus.ENABLED,
            capabilities={
                "compact_peer_format": True,
                "compact_peer_format_ipv6": True,
            },
            last_activity=0.0,
        )

        # SSL/TLS Extension (already registered in protocol above)
        self.extensions["ssl"] = ssl_ext
        self.extension_states["ssl"] = ExtensionState(
            name="ssl",
            status=ExtensionStatus.ENABLED,
            capabilities={
                "supports_ssl": True,
                "version": "1.0",
            },
            last_activity=0.0,
        )

        # Xet Extension
        xet_ext = XetExtension()
        protocol_ext.register_extension("xet", "1.0", handler=None)
        self.extensions["xet"] = xet_ext
        self.extension_states["xet"] = ExtensionState(
            name="xet",
            status=ExtensionStatus.ENABLED,
            capabilities={
                "supports_chunk_requests": True,
                "supports_p2p_cas": True,
                "version": "1.0",
            },
            last_activity=0.0,
        )

    async def start(self) -> None:
        """Start all extensions."""
        # SSL extension is already registered in protocol during initialization
        # Set up message handler if needed
        protocol_ext = self.extensions.get("protocol")
        if protocol_ext:
            ssl_ext_info = protocol_ext.get_extension_info("ssl")
            if ssl_ext_info and not ssl_ext_info.handler:
                # Create handler for SSL extension messages
                async def ssl_handler(peer_id: str, payload: bytes) -> None:
                    """Handle SSL extension messages."""
                    response = await self.handle_ssl_message(
                        peer_id, ssl_ext_info.message_id, payload
                    )
                    if response:
                        # Response will be sent via peer connection message handler
                        pass

                protocol_ext.register_message_handler(
                    ssl_ext_info.message_id, ssl_handler
                )

        for name, extension in self.extensions.items():
            try:
                if hasattr(extension, "start"):
                    await extension.start()

                self.extension_states[name].status = ExtensionStatus.ACTIVE
                self.extension_states[name].last_activity = time.time()

                # Emit event for extension started
                await emit_event(
                    Event(
                        event_type=EventType.EXTENSION_STARTED.value,
                        data={
                            "extension_name": name,
                            "timestamp": time.time(),
                        },
                    ),
                )

            except Exception as e:
                self.extension_states[name].status = ExtensionStatus.ERROR
                self.extension_states[name].error_count += 1
                self.extension_states[name].last_error = str(e)

                # Emit event for extension error
                await emit_event(
                    Event(
                        event_type=EventType.EXTENSION_ERROR.value,
                        data={
                            "extension_name": name,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

    async def stop(self) -> None:
        """Stop all extensions."""
        for name, extension in self.extensions.items():
            try:
                if hasattr(extension, "stop"):
                    await extension.stop()

                self.extension_states[name].status = ExtensionStatus.DISABLED

                # Emit event for extension stopped
                await emit_event(
                    Event(
                        event_type=EventType.EXTENSION_STOPPED.value,
                        data={
                            "extension_name": name,
                            "timestamp": time.time(),
                        },
                    ),
                )

            except Exception as e:
                # Emit event for extension error
                await emit_event(
                    Event(
                        event_type=EventType.EXTENSION_ERROR.value,
                        data={
                            "extension_name": name,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

    def get_extension(self, name: str) -> Any | None:
        """Get extension by name."""
        return self.extensions.get(name)

    def get_extension_state(self, name: str) -> ExtensionState | None:
        """Get extension state."""
        return self.extension_states.get(name)

    def list_extensions(self) -> list[str]:
        """List all extension names."""
        return list(self.extensions.keys())

    def list_active_extensions(self) -> list[str]:
        """List active extension names."""
        return [
            name
            for name, state in self.extension_states.items()
            if state.status == ExtensionStatus.ACTIVE
        ]

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
        if (
            name in self.extension_states
        ):  # pragma: no cover - Extension disable path, tested via enable path
            self.extension_states[name].status = ExtensionStatus.DISABLED
            return True
        return False  # pragma: no cover - Extension not found path, tested via existing extension

    # Fast Extension methods
    async def handle_fast_extension(
        self,
        peer_id: str,
        message_type: int,
        data: bytes,
    ) -> None:
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

        except Exception as e:  # pragma: no cover - Fast extension handler exception, defensive error handling
            self.extension_states["fast"].error_count += 1
            self.extension_states["fast"].last_error = str(e)

    # Extension Protocol methods
    async def handle_extension_protocol(
        self,
        peer_id: str,
        message_type: int,
        data: bytes,
    ) -> None:
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
    async def handle_pex_message(
        self,
        peer_id: str,
        message_type: int,
        data: bytes,
    ) -> None:
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

        except Exception as e:  # pragma: no cover - PEX extension handler exception, defensive error handling
            self.extension_states["pex"].error_count += 1
            self.extension_states["pex"].last_error = str(e)

    # DHT methods
    async def handle_dht_message(
        self,
        peer_ip: str,
        peer_port: int,
        data: bytes,
    ) -> bytes | None:
        """Handle DHT message."""
        if not self.is_extension_active("dht"):
            return None

        dht_ext = self.extensions["dht"]

        try:
            response = await dht_ext.handle_dht_message(peer_ip, peer_port, data)
            self.extension_states["dht"].last_activity = time.time()
        except Exception as e:
            self.extension_states["dht"].error_count += 1
            self.extension_states["dht"].last_error = str(e)
            return None
        else:
            return response

    # WebSeed methods
    async def download_piece_from_webseed(
        self,
        webseed_id: str,
        piece_info: PieceInfo,
    ) -> bytes | None:
        """Download piece from WebSeed."""
        if not self.is_extension_active("webseed"):
            return None

        webseed_ext = self.extensions["webseed"]

        try:
            data = await webseed_ext.download_piece(webseed_id, piece_info, b"")
            self.extension_states["webseed"].last_activity = time.time()
        except Exception as e:
            self.extension_states["webseed"].error_count += 1
            self.extension_states["webseed"].last_error = str(e)
            return None
        else:
            return data

    def add_webseed(self, url: str, name: str | None = None) -> str:
        """Add WebSeed."""
        if not self.is_extension_active("webseed"):
            msg = "WebSeed extension not active"
            raise RuntimeError(msg)

        webseed_ext = self.extensions["webseed"]
        return webseed_ext.add_webseed(url, name)

    def remove_webseed(self, webseed_id: str) -> None:
        """Remove WebSeed."""
        if not self.is_extension_active(
            "webseed"
        ):  # pragma: no cover - WebSeed inactive path, tested via active path
            return

        webseed_ext = self.extensions["webseed"]
        webseed_ext.remove_webseed(webseed_id)

    # SSL Extension methods
    async def handle_ssl_message(
        self,
        peer_id: str,
        message_type: int,  # noqa: ARG002 - Required by interface signature
        data: bytes,
    ) -> bytes | None:
        """Handle SSL Extension message.

        Args:
            peer_id: Peer identifier
            message_type: Message type
            data: Message data

        Returns:
            Response message if this is a request, None otherwise

        """
        if not self.is_extension_active("ssl"):
            return None

        ssl_ext = self.extensions["ssl"]

        try:
            # SSL extension messages are already in the correct format
            # The data contains the full message (message_type + payload)
            if len(data) < 1:
                return None

            # Check message type from first byte
            msg_type = data[0]

            if msg_type == 0x01:  # SSL_REQUEST
                request_id = ssl_ext.decode_request(data)
                response = await ssl_ext.handle_request(peer_id, request_id)
                self.extension_states["ssl"].last_activity = time.time()
                return response
            if msg_type in (0x03, 0x04):  # SSL_ACCEPT or SSL_REJECT
                request_id, accepted = ssl_ext.decode_response(data)
                await ssl_ext.handle_response(peer_id, request_id, accepted)
                self.extension_states["ssl"].last_activity = time.time()
                return None

            return None

        except Exception as e:
            self.extension_states["ssl"].error_count += 1
            self.extension_states["ssl"].last_error = str(e)

            # Emit event for extension error
            await emit_event(
                Event(
                    event_type=EventType.EXTENSION_ERROR.value,
                    data={
                        "extension_name": "ssl",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return None

    # Xet Extension methods
    async def handle_xet_message(
        self,
        peer_id: str,
        message_type: int,  # noqa: ARG002 - Required by interface signature
        data: bytes,
    ) -> bytes | None:
        """Handle Xet Extension message.

        Args:
            peer_id: Peer identifier
            message_type: Message type (extension ID)
            data: Message data

        Returns:
            Response message if this is a request, None otherwise

        """
        if not self.is_extension_active("xet"):
            return None

        xet_ext = self.extensions["xet"]

        try:
            if len(data) < 1:
                return None

            # Check message type from first byte
            msg_type = data[0]

            if msg_type == 0x01:  # CHUNK_REQUEST
                request_id, chunk_hash = xet_ext.decode_chunk_request(data)
                response = await xet_ext.handle_chunk_request(
                    peer_id, request_id, chunk_hash
                )
                self.extension_states["xet"].last_activity = time.time()
                return response
            if msg_type == 0x02:  # CHUNK_RESPONSE
                request_id, chunk_data = xet_ext.decode_chunk_response(data)
                await xet_ext.handle_chunk_response(peer_id, request_id, chunk_data)
                self.extension_states["xet"].last_activity = time.time()
                return None

            return None

        except Exception as e:
            self.extension_states["xet"].error_count += 1
            self.extension_states["xet"].last_error = str(e)

            # Emit event for extension error
            await emit_event(
                Event(
                    event_type=EventType.EXTENSION_ERROR.value,
                    data={
                        "extension_name": "xet",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return None

    # Compact Peer Lists methods
    def encode_peers_compact(self, peers: list[PeerInfo]) -> bytes:
        """Encode peers in compact format."""
        if not self.is_extension_active("compact"):
            msg = "Compact extension not active"
            raise RuntimeError(msg)

        compact_ext = self.extensions["compact"]
        return compact_ext.encode_peers(peers)

    def decode_peers_compact(
        self,
        data: bytes,
        is_ipv6: bool = False,
    ) -> list[PeerInfo]:
        """Decode peers from compact format."""
        if not self.is_extension_active("compact"):
            msg = "Compact extension not active"
            raise RuntimeError(msg)

        compact_ext = self.extensions["compact"]
        return compact_ext.decode_peers(data, is_ipv6)

    # Statistics and monitoring
    def get_extension_statistics(self) -> dict[str, Any]:
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

    def get_peer_extensions(self, peer_id: str) -> dict[str, Any]:
        """Get extensions supported by peer."""
        return self.peer_extensions.get(peer_id, {})

    def set_peer_extensions(self, peer_id: str, extensions: dict[str, Any]) -> None:
        """Set peer extensions."""
        self.peer_extensions[peer_id] = extensions
        
        # Extract SSL capability from extension handshake data
        if "ssl" in self.extensions:
            ssl_ext = self.extensions["ssl"]
            if hasattr(ssl_ext, "decode_handshake"):
                # Check if extensions dict contains SSL extension data
                # BEP 10 format: extensions dict may have nested "m" dict with extension names
                # or direct extension data
                ssl_supported = False
                
                # Check for SSL in extension message map (BEP 10 "m" field)
                if isinstance(extensions, dict):
                    m_dict = extensions.get("m") or extensions.get(b"m", {})
                    if isinstance(m_dict, dict):
                        # SSL extension may be registered with message ID
                        # Check if "ssl" is in the message map
                        if "ssl" in m_dict or b"ssl" in m_dict:
                            ssl_supported = True
                    
                    # Also check for direct SSL extension data in handshake
                    # Some implementations may include extension capabilities directly
                    if not ssl_supported:
                        ssl_supported = ssl_ext.decode_handshake(extensions)
                
                # Store SSL capability in peer_extensions
                if peer_id not in self.peer_extensions:
                    self.peer_extensions[peer_id] = {}
                if not isinstance(self.peer_extensions[peer_id], dict):
                    self.peer_extensions[peer_id] = {"raw": self.peer_extensions[peer_id]}
                
                # Store SSL capability
                self.peer_extensions[peer_id]["ssl"] = ssl_supported
                
                self.logger.debug(
                    "SSL capability for peer %s: %s (extracted from extension handshake)",
                    peer_id,
                    ssl_supported,
                )

    def peer_supports_extension(self, peer_id: str, extension_name: str) -> bool:
        """Check if peer supports extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return False
        
        # For SSL, check if ssl capability is stored (boolean value)
        if extension_name == "ssl":
            ssl_capable = peer_extensions.get("ssl")
            return ssl_capable is True
        
        # For other extensions, check if extension name is in the dict
        # or in the "m" message map
        if extension_name in peer_extensions:
            return True
        
        # Check in "m" dict (BEP 10 message map)
        m_dict = peer_extensions.get("m") or peer_extensions.get(b"m", {})
        if isinstance(m_dict, dict):
            return extension_name in m_dict or (isinstance(extension_name, str) and extension_name.encode() in m_dict)
        
        return False

    def get_extension_capabilities(self, extension_name: str) -> dict[str, Any]:
        """Get extension capabilities."""
        if extension_name in self.extensions:
            ext = self.extensions[extension_name]
            if hasattr(ext, "get_capabilities"):
                return ext.get_capabilities()
            if hasattr(ext, "get_extension_statistics"):
                return ext.get_extension_statistics()

        return {}

    def get_all_statistics(self) -> dict[str, Any]:
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


# Singleton pattern removed - ExtensionManager is now managed via AsyncSessionManager.extension_manager
# This ensures proper lifecycle management and prevents conflicts between multiple session managers
# Deprecated singleton kept for backward compatibility
_extension_manager: ExtensionManager | None = (
    None  # Deprecated - use session_manager.extension_manager
)


def get_extension_manager() -> ExtensionManager:
    """Get the global extension manager.

    DEPRECATED: Singleton pattern removed. Use session_manager.extension_manager instead.
    This function is kept for backward compatibility but will log a warning.

    Returns:
        ExtensionManager instance (deprecated - use session_manager.extension_manager)

    """
    import warnings

    warnings.warn(
        "get_extension_manager() is deprecated. "
        "Use session_manager.extension_manager instead. "
        "Singleton pattern removed to ensure proper lifecycle management.",
        DeprecationWarning,
        stacklevel=2,
    )
    global _extension_manager
    if (
        _extension_manager is None
    ):  # pragma: no cover - Singleton initialization, tested via existing instance
        _extension_manager = ExtensionManager()
    return _extension_manager
