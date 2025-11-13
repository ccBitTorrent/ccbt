"""Base protocol abstraction for ccBitTorrent.

from __future__ import annotations

Provides a unified interface for different protocols including
BitTorrent, WebTorrent, and IPFS.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:  # pragma: no cover - TYPE_CHECKING blocks are not executed at runtime
    from ccbt.models import PeerInfo, TorrentInfo


class ProtocolType(Enum):
    """Supported protocol types."""

    BITTORRENT = "bittorrent"
    WEBTORRENT = "webtorrent"
    IPFS = "ipfs"
    XET = "xet"
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
    supports_xet: bool = False
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
        """Initialize protocol."""
        self.protocol_type = protocol_type
        self.state = ProtocolState.DISCONNECTED
        self.capabilities = ProtocolCapabilities()
        self.stats = ProtocolStats()
        self.peers: dict[str, PeerInfo] = {}
        self.active_connections: set[str] = set()

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
    async def receive_message(self, peer_id: str) -> bytes | None:
        """Receive message from peer."""

    @abstractmethod
    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent and get peers."""

    @abstractmethod
    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics."""

    def get_capabilities(self) -> ProtocolCapabilities:
        """Get protocol capabilities."""
        return self.capabilities

    def get_stats(self) -> ProtocolStats:
        """Get protocol statistics."""
        return self.stats

    def get_peers(self) -> dict[str, PeerInfo]:
        """Get connected peers."""
        return self.peers.copy()

    def get_peer(self, peer_id: str) -> PeerInfo | None:
        """Get specific peer."""
        return self.peers.get(peer_id)

    def is_connected(self, peer_id: str) -> bool:
        """Check if peer is connected."""
        return peer_id in self.active_connections

    def get_state(self) -> ProtocolState:
        """Get protocol state."""
        return self.state

    def set_state(self, state: ProtocolState) -> None:
        """Set protocol state synchronously."""
        self.state = state

        # Emit state change event in background if event loop exists
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.PROTOCOL_STATE_CHANGED.value,
                        data={
                            "protocol_type": self.protocol_type.value,
                            "state": state.value,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    def update_stats(
        self,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        messages_sent: int = 0,
        messages_received: int = 0,
        errors: int = 0,
    ) -> None:
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

        # Emit peer added event in background if event loop exists
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.PEER_ADDED.value,
                        data={
                            "protocol_type": self.protocol_type.value,
                            "peer_info": {
                                "ip": peer_info.ip,
                                "port": peer_info.port,
                                "peer_id": peer_info.peer_id.hex()
                                if peer_info.peer_id
                                else None,
                            },
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    def remove_peer(self, peer_id: str) -> None:
        """Remove peer from protocol."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.active_connections.discard(peer_id)

            # Emit peer removed event in background if event loop exists
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(  # noqa: RUF006  # noqa: RUF006
                    emit_event(
                        Event(
                            event_type=EventType.PEER_REMOVED.value,
                            data={
                                "protocol_type": self.protocol_type.value,
                                "peer_id": peer_id,
                                "timestamp": time.time(),
                            },
                        ),
                    )
                )
            except RuntimeError:  # pragma: no cover - Defensive: event loop not available in test contexts
                # No event loop running, skip event emission
                pass

    async def health_check(self) -> bool:
        """Perform async health check. Override in subclasses if needed."""
        return self.state in [ProtocolState.CONNECTED, ProtocolState.ACTIVE]

    def is_healthy(self) -> bool:
        """Synchronous health check wrapper."""
        return self.state in [ProtocolState.CONNECTED, ProtocolState.ACTIVE]

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    def get_protocol_info(self) -> dict[str, Any]:
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
                "supports_xet": self.capabilities.supports_xet,
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
    """Manages multiple protocols with enhanced features."""

    def __init__(self):
        """Initialize protocol manager."""
        self.protocols: dict[ProtocolType, Protocol] = {}
        self.active_protocols: set[ProtocolType] = set()
        self.protocol_stats: dict[ProtocolType, ProtocolStats] = {}

        # Circuit breaker state
        self.circuit_breaker_state: dict[ProtocolType, dict[str, Any]] = {}
        self.failure_threshold = 5
        self.recovery_timeout = 60.0  # seconds

        # Performance metrics
        self.protocol_performance: dict[ProtocolType, float] = {}

    def register_protocol(self, protocol: Protocol) -> None:
        """Register a protocol."""
        self.protocols[protocol.protocol_type] = protocol
        self.protocol_stats[protocol.protocol_type] = ProtocolStats()

        # Emit protocol registered event
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.PROTOCOL_REGISTERED.value,
                        data={
                            "protocol_type": protocol.protocol_type.value,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    async def unregister_protocol(self, protocol_type: ProtocolType) -> None:
        """Unregister a protocol."""
        if protocol_type in self.protocols:
            del self.protocols[protocol_type]
            if protocol_type in self.protocol_stats:
                del self.protocol_stats[protocol_type]

            # Emit protocol unregistered event
            with contextlib.suppress(RuntimeError):
                # No event loop running, skip event emission
                await emit_event(
                    Event(
                        event_type=EventType.PROTOCOL_UNREGISTERED.value,
                        data={
                            "protocol_type": protocol_type.value,
                            "timestamp": time.time(),
                        },
                    ),
                )

    def get_protocol(self, protocol_type: ProtocolType) -> Protocol | None:
        """Get protocol by type."""
        return self.protocols.get(protocol_type)

    def list_protocols(self) -> list[ProtocolType]:
        """List all registered protocols."""
        return list(self.protocols.keys())

    def list_active_protocols(self) -> list[ProtocolType]:
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
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": protocol_type.value,
                        "timestamp": time.time(),
                    },
                ),
            )
        except Exception as e:
            # Emit protocol error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": protocol_type.value,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False
        else:
            return True

    async def stop_protocol(self, protocol_type: ProtocolType) -> bool:
        """Stop a protocol."""
        protocol = self.protocols.get(protocol_type)
        if not protocol:
            return False

        try:
            await protocol.stop()
            self.active_protocols.discard(protocol_type)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": protocol_type.value,
                        "timestamp": time.time(),
                    },
                ),
            )

            return True

        except Exception as e:
            # Emit protocol error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": protocol_type.value,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False
        else:
            return True

    async def start_all_protocols(self) -> dict[ProtocolType, bool]:
        """Start all protocols."""
        results = {}

        for protocol_type in self.protocols:
            results[protocol_type] = await self.start_protocol(protocol_type)

        return results

    async def stop_all_protocols(self) -> dict[ProtocolType, bool]:
        """Stop all protocols."""
        results = {}

        for protocol_type in list(self.active_protocols):
            results[protocol_type] = await self.stop_protocol(protocol_type)

        return results

    def get_protocol_statistics(self) -> dict[str, Any]:
        """Get statistics for all protocols."""
        stats = {}

        for protocol_type, protocol in self.protocols.items():
            stats[protocol_type.value] = protocol.get_protocol_info()

        return stats

    async def connect_peers_batch(
        self, peers: list[PeerInfo], preferred_protocol: ProtocolType | None = None
    ) -> dict[ProtocolType, list[PeerInfo]]:
        """Connect to multiple peers using the best available protocols.

        Args:
            peers: List of peers to connect to
            preferred_protocol: Preferred protocol type (optional)

        Returns:
            Dictionary mapping protocol types to successfully connected peers

        """
        results: dict[ProtocolType, list[PeerInfo]] = {}

        # Group peers by protocol preference
        protocol_groups = self._group_peers_by_protocol(peers, preferred_protocol)

        # Connect peers concurrently for each protocol
        tasks = []
        for protocol_type, peer_group in protocol_groups.items():
            if protocol_type in self.active_protocols:
                task = asyncio.create_task(
                    self._connect_peers_for_protocol(protocol_type, peer_group)
                )
                tasks.append((protocol_type, task))

        # Wait for all connection attempts
        for protocol_type, task in tasks:
            try:
                connected_peers = await task
                results[protocol_type] = connected_peers
            except Exception:  # pragma: no cover - Rare edge case: task creation/cancellation failures difficult to simulate reliably
                # Update circuit breaker state
                self._record_protocol_failure(protocol_type)
                results[protocol_type] = []

        return results

    async def _connect_peers_for_protocol(
        self, protocol_type: ProtocolType, peers: list[PeerInfo]
    ) -> list[PeerInfo]:
        """Connect peers using a specific protocol."""
        if not self._is_protocol_available(protocol_type):
            return []

        protocol = self.protocols[protocol_type]
        connected_peers = []

        # Connect to peers concurrently
        tasks = [protocol.connect_peer(peer) for peer in peers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for peer, result in zip(peers, results):
            if isinstance(result, bool) and result:
                connected_peers.append(peer)
                self._record_protocol_success(protocol_type)
            else:
                self._record_protocol_failure(protocol_type)

        return connected_peers

    def _group_peers_by_protocol(
        self, peers: list[PeerInfo], preferred_protocol: ProtocolType | None
    ) -> dict[ProtocolType, list[PeerInfo]]:
        """Group peers by their preferred protocol."""
        groups: dict[ProtocolType, list[PeerInfo]] = {}

        for peer in peers:
            # Select best protocol for this peer
            best_protocol = self._select_best_protocol_for_peer(
                peer, preferred_protocol
            )
            if best_protocol:
                if best_protocol not in groups:
                    groups[best_protocol] = []
                groups[best_protocol].append(peer)

        return groups

    def _select_best_protocol_for_peer(
        self,
        _peer: PeerInfo,
        preferred_protocol: ProtocolType | None,
    ) -> ProtocolType | None:
        """Select the best protocol for a peer."""
        # Use preferred protocol if available and healthy
        if preferred_protocol and self._is_protocol_available(preferred_protocol):
            return preferred_protocol

        # Select based on performance scores
        available_protocols = [
            p for p in self.active_protocols if self._is_protocol_available(p)
        ]

        if not available_protocols:
            return None

        # Sort by performance score (higher is better)
        available_protocols.sort(
            key=lambda p: self.protocol_performance.get(p, 1.0), reverse=True
        )

        return available_protocols[0]

    def _is_protocol_available(self, protocol_type: ProtocolType) -> bool:
        """Check if a protocol is available (not circuit-broken)."""
        if protocol_type not in self.circuit_breaker_state:
            return True

        state = self.circuit_breaker_state[protocol_type]

        if state["state"] == "closed":
            return True
        if state["state"] == "open":
            # Check if recovery timeout has passed
            if time.time() - state["last_failure"] > self.recovery_timeout:
                # Move to half-open state
                state["state"] = "half-open"
                return True
            return False
        if state["state"] == "half-open":
            return True

        return True  # pragma: no cover - Defensive: fallback return, all states already handled above

    def _record_protocol_success(self, protocol_type: ProtocolType) -> None:
        """Record a successful protocol operation."""
        if protocol_type not in self.circuit_breaker_state:
            self.circuit_breaker_state[protocol_type] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure": 0.0,
            }

        state = self.circuit_breaker_state[protocol_type]
        state["failure_count"] = 0
        state["state"] = "closed"

        # Update performance score
        current_score = self.protocol_performance.get(protocol_type, 1.0)
        self.protocol_performance[protocol_type] = min(current_score * 1.1, 2.0)

    def _record_protocol_failure(self, protocol_type: ProtocolType) -> None:
        """Record a failed protocol operation."""
        if protocol_type not in self.circuit_breaker_state:
            self.circuit_breaker_state[protocol_type] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure": 0.0,
            }

        state = self.circuit_breaker_state[protocol_type]
        state["failure_count"] += 1
        state["last_failure"] = time.time()

        # Update performance score
        current_score = self.protocol_performance.get(protocol_type, 1.0)
        self.protocol_performance[protocol_type] = max(current_score * 0.9, 0.1)

        # Check if circuit should be opened
        if state["failure_count"] >= self.failure_threshold:
            state["state"] = "open"

    async def announce_torrent_batch(
        self, torrent_infos: list[TorrentInfo]
    ) -> dict[ProtocolType, dict[str, list[PeerInfo]]]:
        """Announce multiple torrents concurrently.

        Args:
            torrent_infos: List of torrents to announce

        Returns:
            Dictionary mapping protocol types to torrent announcements

        """
        results: dict[ProtocolType, dict[str, list[PeerInfo]]] = {}

        # Create announce tasks for all active protocols
        tasks = []
        for protocol_type in self.active_protocols:
            protocol = self.protocols[protocol_type]

            # Create tasks for each torrent
            torrent_tasks = [
                asyncio.create_task(protocol.announce_torrent(torrent_info))
                for torrent_info in torrent_infos
            ]

            tasks.append((protocol_type, torrent_tasks))

        # Wait for all announces to complete
        for protocol_type, torrent_tasks in tasks:
            try:
                torrent_results = await asyncio.gather(
                    *torrent_tasks, return_exceptions=True
                )

                protocol_results = {}
                for torrent_info, result in zip(torrent_infos, torrent_results):
                    if isinstance(result, list):
                        protocol_results[torrent_info.name] = result
                    else:
                        protocol_results[torrent_info.name] = []
                        self._record_protocol_failure(protocol_type)

                results[protocol_type] = protocol_results

            except Exception:  # pragma: no cover - Rare edge case: gather() wrapper exceptions difficult to simulate without breaking internal task structure
                # All torrents failed for this protocol
                protocol_results = {
                    torrent_info.name: [] for torrent_info in torrent_infos
                }
                results[protocol_type] = protocol_results
                self._record_protocol_failure(protocol_type)

        return results

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status for all protocols."""
        status = {}

        for protocol_type, state in self.circuit_breaker_state.items():
            status[protocol_type.value] = {
                "state": state["state"],
                "failure_count": state["failure_count"],
                "last_failure": state["last_failure"],
                "performance_score": self.protocol_performance.get(protocol_type, 1.0),
            }

        return status

    def get_combined_peers(self) -> dict[str, PeerInfo]:
        """Get all peers from all protocols combined."""
        all_peers = {}

        for protocol_type in self.active_protocols:
            protocol = self.protocols.get(protocol_type)
            if protocol:
                all_peers.update(protocol.get_peers())

        return all_peers

    async def announce_torrent_all(
        self,
        torrent_info: TorrentInfo,
    ) -> dict[ProtocolType, list[PeerInfo]]:
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
                    await emit_event(
                        Event(
                            event_type=EventType.PROTOCOL_ERROR.value,
                            data={
                                "protocol_type": protocol_type.value,
                                "error": str(e),
                                "timestamp": time.time(),
                            },
                        ),
                    )
                    results[protocol_type] = []

        return results

    async def health_check_all(self) -> dict[ProtocolType, bool]:
        """Perform health check on all protocols."""
        results = {}

        for protocol_type, protocol in self.protocols.items():
            try:
                results[protocol_type] = await protocol.health_check()
            except Exception:
                results[protocol_type] = False

        return results

    def health_check_all_sync(self) -> dict[ProtocolType, bool]:
        """Perform synchronous health check on all protocols."""
        results = {}

        for protocol_type, protocol in self.protocols.items():
            try:
                results[protocol_type] = protocol.is_healthy()
            except Exception:
                results[protocol_type] = False

        return results


# Singleton pattern removed - ProtocolManager is now managed via AsyncSessionManager.protocol_manager
# This ensures proper lifecycle management and prevents conflicts between multiple session managers
