"""Hybrid protocol implementation.

Combines multiple protocols (BitTorrent, WebTorrent, IPFS) for
optimal peer discovery and content distribution.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..events import Event, EventType, emit_event
from ..models import PeerInfo, TorrentInfo
from .base import Protocol, ProtocolCapabilities, ProtocolState, ProtocolType
from .bittorrent import BitTorrentProtocol
from .ipfs import IPFSProtocol
from .webtorrent import WebTorrentProtocol


@dataclass
class HybridStrategy:
    """Hybrid protocol strategy configuration."""
    use_bittorrent: bool = True
    use_webtorrent: bool = True
    use_ipfs: bool = True
    bittorrent_weight: float = 0.6
    webtorrent_weight: float = 0.3
    ipfs_weight: float = 0.1
    fallback_order: List[ProtocolType] = None

    def __post_init__(self):
        if self.fallback_order is None:
            self.fallback_order = [
                ProtocolType.BITTORRENT,
                ProtocolType.WEBTORRENT,
                ProtocolType.IPFS,
            ]


class HybridProtocol(Protocol):
    """Hybrid protocol combining multiple protocols."""

    def __init__(self, strategy: Optional[HybridStrategy] = None):
        super().__init__(ProtocolType.HYBRID)

        # Hybrid-specific capabilities
        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=True,
            supports_dht=True,
            supports_webrtc=True,
            supports_ipfs=True,
            max_connections=1000,
            supports_ipv6=True,
        )

        # Strategy configuration
        self.strategy = strategy or HybridStrategy()

        # Sub-protocols
        self.sub_protocols: Dict[ProtocolType, Protocol] = {}
        self.protocol_weights: Dict[ProtocolType, float] = {}
        self.protocol_performance: Dict[ProtocolType, float] = {}

        # Initialize sub-protocols
        self._initialize_sub_protocols()

    def _initialize_sub_protocols(self) -> None:
        """Initialize sub-protocols based on strategy."""
        if self.strategy.use_bittorrent:
            self.sub_protocols[ProtocolType.BITTORRENT] = BitTorrentProtocol()
            self.protocol_weights[ProtocolType.BITTORRENT] = self.strategy.bittorrent_weight

        if self.strategy.use_webtorrent:
            self.sub_protocols[ProtocolType.WEBTORRENT] = WebTorrentProtocol()
            self.protocol_weights[ProtocolType.WEBTORRENT] = self.strategy.webtorrent_weight

        if self.strategy.use_ipfs:
            self.sub_protocols[ProtocolType.IPFS] = IPFSProtocol()
            self.protocol_weights[ProtocolType.IPFS] = self.strategy.ipfs_weight

        # Initialize performance scores
        for protocol_type in self.sub_protocols:
            self.protocol_performance[protocol_type] = 1.0

    async def start(self) -> None:
        """Start hybrid protocol."""
        try:
            # Start all sub-protocols
            for protocol_type, protocol in self.sub_protocols.items():
                try:
                    await protocol.start()

                    # Emit sub-protocol started event
                    await emit_event(Event(
                        event_type=EventType.SUB_PROTOCOL_STARTED.value,
                        data={
                            "hybrid_protocol": "hybrid",
                            "sub_protocol": protocol_type.value,
                            "timestamp": time.time(),
                        },
                    ))

                except Exception as e:
                    # Emit sub-protocol error event
                    await emit_event(Event(
                        event_type=EventType.SUB_PROTOCOL_ERROR.value,
                        data={
                            "hybrid_protocol": "hybrid",
                            "sub_protocol": protocol_type.value,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ))

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STARTED.value,
                data={
                    "protocol_type": "hybrid",
                    "sub_protocols": list(self.sub_protocols.keys()),
                    "timestamp": time.time(),
                },
            ))

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop hybrid protocol."""
        try:
            # Stop all sub-protocols
            for protocol_type, protocol in self.sub_protocols.items():
                try:
                    await protocol.stop()

                    # Emit sub-protocol stopped event
                    await emit_event(Event(
                        event_type=EventType.SUB_PROTOCOL_STOPPED.value,
                        data={
                            "hybrid_protocol": "hybrid",
                            "sub_protocol": protocol_type.value,
                            "timestamp": time.time(),
                        },
                    ))

                except Exception as e:
                    # Emit sub-protocol error event
                    await emit_event(Event(
                        event_type=EventType.SUB_PROTOCOL_ERROR.value,
                        data={
                            "hybrid_protocol": "hybrid",
                            "sub_protocol": protocol_type.value,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ))

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(Event(
                event_type=EventType.PROTOCOL_STOPPED.value,
                data={
                    "protocol_type": "hybrid",
                    "timestamp": time.time(),
                },
            ))

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a peer using the best available protocol."""
        # Select best protocol for this peer
        best_protocol = self._select_best_protocol(peer_info)

        if not best_protocol:
            return False

        try:
            # Connect using selected protocol
            success = await best_protocol.connect_peer(peer_info)

            if success:
                # Update performance score
                self._update_protocol_performance(best_protocol.protocol_type, True)

                # Add peer to hybrid protocol
                self.add_peer(peer_info)

                # Update stats
                self.stats.connections_established += 1
                self.update_stats()

            return success

        except Exception as e:
            # Update performance score
            self._update_protocol_performance(best_protocol.protocol_type, False)

            # Emit connection error event
            await emit_event(Event(
                event_type=EventType.PEER_CONNECTION_FAILED.value,
                data={
                    "protocol_type": "hybrid",
                    "sub_protocol": best_protocol.protocol_type.value,
                    "peer_id": peer_info.peer_id.hex() if peer_info.peer_id else None,
                    "error": str(e),
                    "timestamp": time.time(),
                },
            ))

            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a peer."""
        # Disconnect from all sub-protocols
        for protocol in self.sub_protocols.values():
            try:
                await protocol.disconnect_peer(peer_id)
            except Exception:
                pass

        # Remove from hybrid protocol
        self.remove_peer(peer_id)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to peer using the best available protocol."""
        # Find which protocol has this peer
        best_protocol = self._find_protocol_for_peer(peer_id)

        if not best_protocol:
            return False

        try:
            # Send message using the protocol
            success = await best_protocol.send_message(peer_id, message)

            if success:
                # Update stats
                self.update_stats(bytes_sent=len(message), messages_sent=1)

            return success

        except Exception:
            self.update_stats(errors=1)
            return False

    async def receive_message(self, peer_id: str) -> Optional[bytes]:
        """Receive message from peer using the best available protocol."""
        # Find which protocol has this peer
        best_protocol = self._find_protocol_for_peer(peer_id)

        if not best_protocol:
            return None

        try:
            # Receive message using the protocol
            message = await best_protocol.receive_message(peer_id)

            if message:
                # Update stats
                self.update_stats(bytes_received=len(message), messages_received=1)

            return message

        except Exception:
            self.update_stats(errors=1)
            return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> List[PeerInfo]:
        """Announce torrent using all available protocols."""
        all_peers = []

        # Announce to all sub-protocols
        for protocol_type, protocol in self.sub_protocols.items():
            try:
                peers = await protocol.announce_torrent(torrent_info)
                all_peers.extend(peers)

                # Emit sub-protocol announce event
                await emit_event(Event(
                    event_type=EventType.SUB_PROTOCOL_ANNOUNCE.value,
                    data={
                        "hybrid_protocol": "hybrid",
                        "sub_protocol": protocol_type.value,
                        "peers_found": len(peers),
                        "timestamp": time.time(),
                    },
                ))

            except Exception as e:
                # Emit sub-protocol error event
                await emit_event(Event(
                    event_type=EventType.SUB_PROTOCOL_ERROR.value,
                    data={
                        "hybrid_protocol": "hybrid",
                        "sub_protocol": protocol_type.value,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

        # Remove duplicate peers
        unique_peers = self._deduplicate_peers(all_peers)

        # Emit hybrid announce event
        await emit_event(Event(
            event_type=EventType.HYBRID_ANNOUNCE.value,
            data={
                "protocol_type": "hybrid",
                "total_peers": len(unique_peers),
                "sub_protocols_used": len(self.sub_protocols),
                "timestamp": time.time(),
            },
        ))

        return unique_peers

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> Dict[str, int]:
        """Scrape torrent statistics using all available protocols."""
        combined_stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        # Scrape from all sub-protocols
        for protocol_type, protocol in self.sub_protocols.items():
            try:
                stats = await protocol.scrape_torrent(torrent_info)

                # Combine statistics
                combined_stats["seeders"] += stats.get("seeders", 0)
                combined_stats["leechers"] += stats.get("leechers", 0)
                combined_stats["completed"] += stats.get("completed", 0)

            except Exception as e:
                # Emit sub-protocol error event
                await emit_event(Event(
                    event_type=EventType.SUB_PROTOCOL_ERROR.value,
                    data={
                        "hybrid_protocol": "hybrid",
                        "sub_protocol": protocol_type.value,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

        return combined_stats

    def _select_best_protocol(self, peer_info: PeerInfo) -> Optional[Protocol]:
        """Select the best protocol for a peer."""
        # Calculate scores for each protocol
        protocol_scores = {}

        for protocol_type, protocol in self.sub_protocols.items():
            # Base score from weight
            base_score = self.protocol_weights.get(protocol_type, 0.0)

            # Performance score
            performance_score = self.protocol_performance.get(protocol_type, 1.0)

            # Combined score
            total_score = base_score * performance_score
            protocol_scores[protocol_type] = total_score

        # Select protocol with highest score
        if protocol_scores:
            best_protocol_type = max(protocol_scores, key=protocol_scores.get)
            return self.sub_protocols[best_protocol_type]

        return None

    def _find_protocol_for_peer(self, peer_id: str) -> Optional[Protocol]:
        """Find which protocol has a specific peer."""
        for protocol in self.sub_protocols.values():
            if protocol.is_connected(peer_id):
                return protocol

        return None

    def _update_protocol_performance(self, protocol_type: ProtocolType, success: bool) -> None:
        """Update protocol performance score."""
        if protocol_type not in self.protocol_performance:
            self.protocol_performance[protocol_type] = 1.0

        # Update performance score based on success/failure
        if success:
            # Increase performance score
            self.protocol_performance[protocol_type] = min(
                self.protocol_performance[protocol_type] * 1.1, 2.0,
            )
        else:
            # Decrease performance score
            self.protocol_performance[protocol_type] = max(
                self.protocol_performance[protocol_type] * 0.9, 0.1,
            )

    def _deduplicate_peers(self, peers: List[PeerInfo]) -> List[PeerInfo]:
        """Remove duplicate peers."""
        seen = set()
        unique_peers = []

        for peer in peers:
            peer_key = (peer.ip, peer.port)
            if peer_key not in seen:
                seen.add(peer_key)
                unique_peers.append(peer)

        return unique_peers

    def get_sub_protocols(self) -> Dict[ProtocolType, Protocol]:
        """Get sub-protocols."""
        return self.sub_protocols.copy()

    def get_protocol_weights(self) -> Dict[ProtocolType, float]:
        """Get protocol weights."""
        return self.protocol_weights.copy()

    def get_protocol_performance(self) -> Dict[ProtocolType, float]:
        """Get protocol performance scores."""
        return self.protocol_performance.copy()

    def update_strategy(self, strategy: HybridStrategy) -> None:
        """Update hybrid strategy."""
        self.strategy = strategy

        # Reinitialize sub-protocols if needed
        self._initialize_sub_protocols()

    def get_hybrid_stats(self) -> Dict[str, Any]:
        """Get hybrid protocol statistics."""
        sub_protocol_stats = {}

        for protocol_type, protocol in self.sub_protocols.items():
            sub_protocol_stats[protocol_type.value] = protocol.get_protocol_info()

        return {
            "protocol_type": "hybrid",
            "state": self.state.value,
            "strategy": {
                "use_bittorrent": self.strategy.use_bittorrent,
                "use_webtorrent": self.strategy.use_webtorrent,
                "use_ipfs": self.strategy.use_ipfs,
                "bittorrent_weight": self.strategy.bittorrent_weight,
                "webtorrent_weight": self.strategy.webtorrent_weight,
                "ipfs_weight": self.strategy.ipfs_weight,
            },
            "protocol_weights": {k.value: v for k, v in self.protocol_weights.items()},
            "protocol_performance": {k.value: v for k, v in self.protocol_performance.items()},
            "sub_protocols": sub_protocol_stats,
            "total_peers": len(self.peers),
            "active_connections": len(self.active_connections),
        }
