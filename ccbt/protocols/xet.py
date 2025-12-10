"""Xet protocol implementation.

from __future__ import annotations

Provides Xet protocol integration for content-defined chunking,
deduplication, and peer-to-peer Content Addressable Storage.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from ccbt.discovery.xet_cas import P2PCASClient
from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolState,
    ProtocolType,
)
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ccbt.models import PeerInfo, TorrentInfo


class XetProtocol(Protocol):
    """Xet protocol implementation for content-defined chunking and P2P CAS."""

    def __init__(
        self,
        dht_client=None,
        tracker_client=None,
        pex_manager=None,
        lpd_client=None,
        multicast_broadcaster=None,
        gossip_manager=None,
        flooding_client=None,
        catalog=None,
        bloom_filter=None,
    ):
        """Initialize Xet protocol.

        Args:
            dht_client: Optional DHT client for chunk discovery
            tracker_client: Optional tracker client for chunk announcements
            pex_manager: Optional PEX manager for peer exchange
            lpd_client: Optional Local Peer Discovery client
            multicast_broadcaster: Optional multicast broadcaster for local network
            gossip_manager: Optional gossip protocol manager
            flooding_client: Optional controlled flooding client
            catalog: Optional chunk catalog for bulk queries
            bloom_filter: Optional bloom filter for chunk availability

        """
        super().__init__(ProtocolType.XET)

        # Xet-specific capabilities
        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=True,
            supports_dht=True,
            supports_webrtc=False,
            supports_ipfs=False,
            supports_xet=True,
            max_connections=200,
            supports_ipv6=True,
        )

        # Dependencies
        self.dht_client = dht_client
        self.tracker_client = tracker_client
        self.pex_manager = pex_manager
        self.lpd_client = lpd_client
        self.multicast_broadcaster = multicast_broadcaster
        self.gossip_manager = gossip_manager
        self.flooding_client = flooding_client
        self.catalog = catalog
        self.bloom_filter = bloom_filter

        # P2P CAS client
        self.cas_client: P2PCASClient | None = None

        # Logger
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start Xet protocol."""
        try:
            # Initialize P2P CAS client with all discovery mechanisms
            if self.dht_client or self.tracker_client:
                self.cas_client = P2PCASClient(
                    dht_client=self.dht_client,
                    tracker_client=self.tracker_client,
                    bloom_filter=self.bloom_filter,
                    catalog=self.catalog,
                )
                self.logger.info("Xet P2P CAS client initialized")

            # Start discovery mechanisms if available
            if self.lpd_client:
                try:
                    await self.lpd_client.start()
                    self.logger.info("Local Peer Discovery started")
                except Exception as e:
                    self.logger.warning("Failed to start LPD: %s", e)

            if self.gossip_manager:
                try:
                    await self.gossip_manager.start()
                    self.logger.info("Gossip protocol started")
                except Exception as e:
                    self.logger.warning("Failed to start gossip: %s", e)

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": "xet",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop Xet protocol."""
        try:
            # Clean up CAS client if needed
            if self.cas_client:
                # CAS client cleanup if needed
                self.cas_client = None

            # Stop discovery mechanisms
            if self.lpd_client:
                try:
                    await self.lpd_client.stop()
                except Exception as e:
                    self.logger.warning("Error stopping LPD: %s", e)

            if self.gossip_manager:
                try:
                    await self.gossip_manager.stop()
                except Exception as e:
                    self.logger.warning("Error stopping gossip: %s", e)

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": "xet",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a peer for Xet chunk exchange.

        Args:
            peer_info: Peer information

        Returns:
            True if connection successful, False otherwise

        """
        try:
            # For Xet, peer connections are primarily for chunk exchange
            # The actual connection is managed through the connection manager
            # and BitTorrent protocol extension

            # Add peer to protocol
            self.add_peer(peer_info)
            self.stats.connections_established += 1
            self.update_stats()

            # Emit peer connected event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTED.value,
                    data={
                        "protocol_type": "xet",
                        "peer_id": peer_info.peer_id.hex()
                        if peer_info.peer_id
                        else None,
                        "timestamp": time.time(),
                    },
                ),
            )

            return True

        except Exception as e:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTION_FAILED.value,
                    data={
                        "protocol_type": "xet",
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
        """Disconnect from a peer.

        Args:
            peer_id: Peer identifier

        """
        try:
            # Remove peer from protocol
            self.remove_peer(peer_id)

            # Emit peer disconnected event
            await emit_event(
                Event(
                    event_type=EventType.PEER_DISCONNECTED.value,
                    data={
                        "protocol_type": "xet",
                        "peer_id": peer_id,
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.logger.exception("Error disconnecting peer %s", peer_id)
            self.update_stats(errors=1)

    async def send_message(self, _peer_id: str, message: bytes) -> bool:
        """Send message to peer.

        Note: Xet uses BitTorrent protocol extension for chunk messages,
        so this is primarily for future protocol-level messages.

        Args:
            peer_id: Peer identifier
            message: Message bytes

        Returns:
            True if sent successfully, False otherwise

        """
        try:
            # For Xet, messages are sent via BitTorrent extension protocol
            # This method is kept for protocol compatibility
            # Actual chunk requests/responses use extension protocol

            self.update_stats(bytes_sent=len(message), messages_sent=1)
            return True

        except Exception:
            self.update_stats(errors=1)
            return False

    async def receive_message(self, _peer_id: str) -> bytes | None:
        """Receive message from peer.

        Note: Xet uses BitTorrent protocol extension for chunk messages,
        so this is primarily for future protocol-level messages.

        Args:
            peer_id: Peer identifier

        Returns:
            Message bytes if available, None otherwise

        """
        try:
            # For Xet, messages are received via BitTorrent extension protocol
            # This method is kept for protocol compatibility
            # Actual chunk requests/responses use extension protocol

            return None

        except Exception:
            self.update_stats(errors=1)
            return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent and discover peers.

        For Xet, this discovers peers that have chunks for the torrent's content.
        It uses multiple strategies:
        1. Query DHT using torrent info_hash for Xet-enabled peers
        2. Query trackers for peers that support Xet
        3. If Xet metadata is available, query for specific chunk hashes
        4. Use heuristics to discover chunks from piece hashes

        Args:
            torrent_info: Torrent information

        Returns:
            List of peers that may have chunks

        """
        try:
            peers = []
            discovered_chunks: set[bytes] = set()

            if not self.cas_client:
                self.logger.debug(
                    "Xet CAS client not initialized, skipping chunk discovery"
                )
                return []

            # Strategy 1: Query DHT for peers using torrent info_hash
            # This finds peers that have announced this torrent
            if self.dht_client:
                try:
                    # Query DHT for peers with this torrent
                    if hasattr(self.dht_client, "get_peers"):
                        dht_peers = await self.dht_client.get_peers(
                            torrent_info.info_hash
                        )
                        if dht_peers:
                            # Filter for peers that might support Xet
                            # (In practice, we'd check extension handshake)
                            peers.extend(dht_peers)
                            self.logger.debug(
                                "Found %d peers via DHT for torrent %s",
                                len(dht_peers),
                                torrent_info.name,
                            )
                except Exception as e:
                    self.logger.warning("Error querying DHT for torrent peers: %s", e)

            # Strategy 2: Query tracker for peers
            if self.tracker_client:
                try:
                    if hasattr(self.tracker_client, "announce"):
                        # Announce to tracker and get peers
                        tracker_response = await self.tracker_client.announce(
                            torrent_info.info_hash,
                            event="started",
                        )
                        if tracker_response and hasattr(tracker_response, "peers"):
                            tracker_peers = tracker_response.peers
                            peers.extend(tracker_peers)
                            self.logger.debug(
                                "Found %d peers via tracker for torrent %s",
                                len(tracker_peers),
                                torrent_info.name,
                            )
                except Exception as e:
                    self.logger.warning(
                        "Error querying tracker for torrent peers: %s", e
                    )

            # Strategy 2b: Local Peer Discovery (LPD) for local network
            if self.lpd_client:
                try:
                    if hasattr(self.lpd_client, "discover_peers"):
                        lpd_peers = await self.lpd_client.discover_peers(timeout=2.0)
                        if lpd_peers:
                            from ccbt.models import PeerInfo
                            for ip, port in lpd_peers:
                                peers.append(PeerInfo(ip=ip, port=port))
                            self.logger.debug(
                                "Found %d peers via LPD for torrent %s",
                                len(lpd_peers),
                                torrent_info.name,
                            )
                except Exception as e:
                    self.logger.warning("Error querying LPD for peers: %s", e)

            # Strategy 2c: Peer Exchange (PEX) for chunk availability
            if self.pex_manager and chunk_hashes_to_query:
                try:
                    if hasattr(self.pex_manager, "get_peers_with_chunks"):
                        pex_peers = await self.pex_manager.get_peers_with_chunks(
                            chunk_hashes_to_query[:20]  # Limit queries
                        )
                        if pex_peers:
                            peers.extend(pex_peers)
                            self.logger.debug(
                                "Found %d peers via PEX for torrent %s",
                                len(pex_peers),
                                torrent_info.name,
                            )
                except Exception as e:
                    self.logger.warning("Error querying PEX for peers: %s", e)

            # Strategy 3: Extract chunk hashes from Xet metadata if available
            # This is the primary method for chunk discovery when Xet is enabled
            chunk_hashes_to_query: list[bytes] = []

            if torrent_info.xet_metadata:
                xet_meta = torrent_info.xet_metadata
                # Use chunk hashes from Xet metadata (primary source)
                if xet_meta.chunk_hashes:
                    chunk_hashes_to_query.extend(xet_meta.chunk_hashes)
                    self.logger.debug(
                        "Found %d chunk hashes in Xet metadata for torrent %s",
                        len(xet_meta.chunk_hashes),
                        torrent_info.name,
                    )
                else:
                    # Fallback: extract chunk hashes from piece metadata
                    for piece_meta in xet_meta.piece_metadata:
                        chunk_hashes_to_query.extend(piece_meta.chunk_hashes)
                    self.logger.debug(
                        "Extracted chunk hashes from %d pieces in Xet metadata",
                        len(xet_meta.piece_metadata),
                    )

            # Strategy 4: Use BitTorrent v2 piece layers for chunk discovery
            # For v2 torrents, piece layers contain SHA-256 hashes that can be used
            # as identifiers for content discovery (though not perfect, since Xet chunks
            # are content-defined, not piece-aligned)
            if not chunk_hashes_to_query and torrent_info.piece_layers:
                # For v2 torrents, use piece layer roots as potential chunk identifiers
                # This is more accurate than v1 piece hashes since they're SHA-256
                piece_layer_roots = list(torrent_info.piece_layers.keys())
                # Limit to first 20 piece layers to avoid excessive queries
                chunk_hashes_to_query.extend(piece_layer_roots[:20])
                self.logger.debug(
                    "Using %d piece layer roots from v2 torrent for chunk discovery",
                    len(chunk_hashes_to_query),
                )

            # Strategy 3b: Pre-filter using Bloom Filters
            if self.bloom_filter and chunk_hashes_to_query:
                try:
                    # Filter chunks that might be available based on bloom filter
                    filtered_chunks = []
                    for chunk_hash in chunk_hashes_to_query:
                        if self.bloom_filter.has_chunk(chunk_hash):
                            filtered_chunks.append(chunk_hash)
                    if filtered_chunks:
                        chunk_hashes_to_query = filtered_chunks
                        self.logger.debug(
                            "Bloom filter filtered to %d potentially available chunks",
                            len(filtered_chunks),
                        )
                except Exception as e:
                    self.logger.warning("Error using bloom filter: %s", e)

            # Query for peers that have specific chunks
            if chunk_hashes_to_query:
                try:
                    # Check catalog first for fast bulk lookup
                    if self.catalog or (
                        hasattr(self.cas_client, "catalog") and self.cas_client.catalog
                    ):
                        catalog_to_use = self.catalog or self.cas_client.catalog
                        try:
                            catalog_results = await catalog_to_use.get_peers_by_chunks(
                                chunk_hashes_to_query[:50]
                            )
                            # Add catalog results
                            for chunk_hash, catalog_peers in catalog_results.items():
                                if catalog_peers:
                                    from ccbt.models import PeerInfo

                                    for ip, port in catalog_peers:
                                        peers.append(PeerInfo(ip=ip, port=port))
                                    discovered_chunks.add(chunk_hash)
                            self.logger.debug(
                                "Found %d chunks in catalog",
                                len(catalog_results),
                            )
                        except Exception as e:
                            self.logger.warning("Error querying catalog: %s", e)

                    # Use batch query if available, otherwise parallel queries
                    if hasattr(self.cas_client, "find_chunks_peers_batch"):
                        # Batch query for better performance
                        chunk_peer_map = await self.cas_client.find_chunks_peers_batch(
                            chunk_hashes_to_query[:50]  # Configurable limit
                        )
                        # Flatten results
                        for chunk_hash, chunk_peers in chunk_peer_map.items():
                            peers.extend(chunk_peers)
                            discovered_chunks.add(chunk_hash)
                    else:
                        # Fallback to parallel queries with semaphore for rate limiting
                        from asyncio import Semaphore

                        semaphore = Semaphore(50)  # Max 50 concurrent queries

                        async def query_with_limit(chunk_hash: bytes) -> list[PeerInfo]:
                            async with semaphore:
                                return await self.cas_client.find_chunk_peers(chunk_hash)

                        chunk_peer_tasks = [
                            query_with_limit(chunk_hash)
                            for chunk_hash in chunk_hashes_to_query[:50]  # Configurable limit
                        ]
                        chunk_peer_results = await asyncio.gather(
                            *chunk_peer_tasks, return_exceptions=True
                        )

                        for i, result in enumerate(chunk_peer_results):
                            if isinstance(result, list):
                                peers.extend(result)
                                if i < len(chunk_hashes_to_query):
                                    discovered_chunks.add(chunk_hashes_to_query[i])
                                    # Track discovered chunks
                                    for peer in result:
                                        if hasattr(peer, "chunk_hashes"):
                                            discovered_chunks.update(peer.chunk_hashes)  # type: ignore[attr-defined]
                except Exception as e:
                    self.logger.warning("Error during chunk discovery: %s", e)

            self.logger.debug(
                "Found %d peers via chunk discovery for torrent %s",
                len(peers),
                torrent_info.name,
            )

            # Strategy 4: Broadcast chunk announcements via multicast if enabled
            if self.multicast_broadcaster and chunk_hashes_to_query:
                try:
                    for chunk_hash in chunk_hashes_to_query[:10]:  # Limit broadcasts
                        await self.multicast_broadcaster.broadcast_chunk_announcement(
                            chunk_hash
                        )
                    self.logger.debug(
                        "Broadcast %d chunk announcements via multicast",
                        min(10, len(chunk_hashes_to_query)),
                    )
                except Exception as e:
                    self.logger.warning("Error broadcasting chunk announcements: %s", e)

            # Strategy 5: Gossip protocol for chunk availability propagation
            if self.gossip_manager and chunk_hashes_to_query:
                try:
                    for chunk_hash in chunk_hashes_to_query[:5]:  # Limit gossip
                        await self.gossip_manager.propagate_chunk_update(chunk_hash)
                    self.logger.debug(
                        "Propagated %d chunk updates via gossip",
                        min(5, len(chunk_hashes_to_query)),
                    )
                except Exception as e:
                    self.logger.warning("Error propagating chunk updates via gossip: %s", e)

            # Strategy 6: Controlled flooding for urgent chunk announcements
            if self.flooding_client and chunk_hashes_to_query:
                try:
                    # Only flood high-priority chunks (first few)
                    urgent_chunks = chunk_hashes_to_query[:3]
                    for chunk_hash in urgent_chunks:
                        await self.flooding_client.flood_message(
                            {
                                "type": "chunk_announcement",
                                "chunk_hash": chunk_hash.hex(),
                                "torrent_info_hash": torrent_info.info_hash.hex(),
                            },
                            ttl=3,  # Limit propagation distance
                        )
                    self.logger.debug(
                        "Flooded %d urgent chunk announcements",
                        len(urgent_chunks),
                    )
                except Exception as e:
                    self.logger.warning("Error flooding chunk announcements: %s", e)

            # Strategy 7: Query using info_hash_v2 if available (BEP 52)
            # Protocol v2 torrents have better structure for Xet integration
            # since they use SHA-256 hashes which align with Xet's BLAKE3-256 format
            if torrent_info.info_hash_v2:
                try:
                    if self.dht_client and hasattr(self.dht_client, "get_peers"):
                        v2_peers = await self.dht_client.get_peers(
                            torrent_info.info_hash_v2
                        )
                        if v2_peers:
                            peers.extend(v2_peers)
                            self.logger.debug(
                                "Found %d peers via DHT v2 for torrent %s",
                                len(v2_peers),
                                torrent_info.name,
                            )
                except Exception as e:
                    self.logger.warning(
                        "Error querying DHT v2 for torrent peers: %s", e
                    )

            # Remove duplicate peers
            unique_peers = self._deduplicate_peers(peers)

            # Update stats
            self.stats.announces += 1
            self.update_stats()

            self.logger.info(
                "Xet announce for torrent %s: found %d unique peers, %d chunks discovered",
                torrent_info.name,
                len(unique_peers),
                len(discovered_chunks),
            )

            # Emit announce event
            await emit_event(
                Event(
                    event_type=EventType.SUB_PROTOCOL_ANNOUNCE.value,
                    data={
                        "protocol_type": "xet",
                        "torrent_name": torrent_info.name,
                        "torrent_info_hash": torrent_info.info_hash.hex(),
                        "peers_found": len(unique_peers),
                        "chunks_discovered": len(discovered_chunks),
                        "timestamp": time.time(),
                    },
                ),
            )

            return unique_peers

        except Exception:
            self.logger.exception("Error announcing torrent")
            self.update_stats(errors=1)
            return []

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics.

        For Xet, this provides statistics about chunk availability by:
        1. Querying trackers (HTTP/UDP) for standard torrent statistics
        2. Querying DHT for chunk-based peer discovery
        3. Calculating chunk availability statistics

        Args:
            torrent_info: Torrent information

        Returns:
            Dictionary with statistics (seeders, leechers, completed)

        """
        stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        try:
            # Strategy 1: Scrape from trackers (HTTP/UDP)
            tracker_stats = await self._scrape_from_trackers(torrent_info)
            if tracker_stats:
                stats["seeders"] = tracker_stats.get("seeders", 0)
                stats["leechers"] = tracker_stats.get("leechers", 0)
                stats["completed"] = tracker_stats.get("completed", 0)

                # If we got good tracker stats, use them and enhance with DHT
                if stats["seeders"] > 0 or stats["leechers"] > 0:
                    self.logger.debug(
                        "Got tracker stats: seeders=%d, leechers=%d, completed=%d",
                        stats["seeders"],
                        stats["leechers"],
                        stats["completed"],
                    )

            # Strategy 2: Query DHT for chunk-based statistics
            # This provides XET-specific chunk availability information
            dht_stats = await self._scrape_from_dht(torrent_info)
            if dht_stats:
                # Use DHT stats if tracker stats are unavailable or enhance with DHT
                if stats["seeders"] == 0 and stats["leechers"] == 0:
                    # Use DHT stats as primary source
                    stats["seeders"] = dht_stats.get("seeders", 0)
                    stats["leechers"] = dht_stats.get("leechers", 0)
                    stats["completed"] = dht_stats.get("completed", 0)
                    self.logger.debug(
                        "Using DHT stats: seeders=%d, leechers=%d",
                        stats["seeders"],
                        stats["leechers"],
                    )
                else:
                    # Enhance tracker stats with DHT chunk availability info
                    # Take the maximum to avoid double-counting
                    stats["seeders"] = max(
                        stats["seeders"], dht_stats.get("seeders", 0)
                    )
                    stats["leechers"] = max(
                        stats["leechers"], dht_stats.get("leechers", 0)
                    )

            # Update protocol stats
            self.stats.announces += 1
            self.update_stats()

            self.logger.info(
                "Xet scrape for torrent %s: seeders=%d, leechers=%d, completed=%d",
                torrent_info.name,
                stats["seeders"],
                stats["leechers"],
                stats["completed"],
            )

            return stats

        except Exception:
            self.logger.exception("Error scraping torrent")
            self.update_stats(errors=1)
            return {
                "seeders": 0,
                "leechers": 0,
                "completed": 0,
            }

    async def _scrape_from_trackers(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape statistics from HTTP/UDP trackers.

        Args:
            torrent_info: Torrent information

        Returns:
            Dictionary with tracker statistics, or empty dict if unavailable

        """
        tracker_stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        # Get tracker URLs from torrent info
        tracker_urls = self._get_tracker_urls(torrent_info)
        if not tracker_urls:
            self.logger.debug("No tracker URLs found for scraping")
            return {}

        # Convert TorrentInfo to tracker data format
        torrent_data = self._torrent_info_to_dict(torrent_info)

        # Try scraping from each tracker until we get a successful result
        for tracker_url in tracker_urls:
            try:
                # Determine tracker type
                is_udp = tracker_url.startswith("udp://")
                is_http = tracker_url.startswith(("http://", "https://"))

                if not is_udp and not is_http:
                    self.logger.debug("Unsupported tracker URL scheme: %s", tracker_url)
                    continue

                # Create tracker data dict for this tracker
                tracker_data = torrent_data.copy()
                tracker_data["announce"] = tracker_url

                # Scrape using appropriate client
                if is_udp:
                    from ccbt.discovery.tracker_udp_client import (
                        AsyncUDPTrackerClient,
                    )

                    udp_client = AsyncUDPTrackerClient()
                    await udp_client.start()

                    try:
                        scrape_result = await udp_client.scrape(tracker_data)
                        if scrape_result:
                            tracker_stats["seeders"] = scrape_result.get("seeders", 0)
                            tracker_stats["leechers"] = scrape_result.get("leechers", 0)
                            tracker_stats["completed"] = scrape_result.get(
                                "completed", 0
                            )

                            # Success! Return first successful result
                            if (
                                tracker_stats["seeders"] > 0
                                or tracker_stats["leechers"] > 0
                            ):
                                self.logger.debug(
                                    "Successfully scraped from UDP tracker: %s "
                                    "(seeders: %d, leechers: %d)",
                                    tracker_url,
                                    tracker_stats["seeders"],
                                    tracker_stats["leechers"],
                                )
                                return tracker_stats
                    finally:
                        await udp_client.stop()

                else:  # HTTP/HTTPS
                    from ccbt.discovery.tracker import AsyncTrackerClient

                    http_client = AsyncTrackerClient()
                    await http_client.start()

                    try:
                        scrape_result = await http_client.scrape(tracker_data)
                        if scrape_result:
                            tracker_stats["seeders"] = scrape_result.get("seeders", 0)
                            tracker_stats["leechers"] = scrape_result.get("leechers", 0)
                            tracker_stats["completed"] = scrape_result.get(
                                "completed", 0
                            )

                            # Success! Return first successful result
                            if (
                                tracker_stats["seeders"] > 0
                                or tracker_stats["leechers"] > 0
                            ):
                                self.logger.debug(
                                    "Successfully scraped from HTTP tracker: %s "
                                    "(seeders: %d, leechers: %d)",
                                    tracker_url,
                                    tracker_stats["seeders"],
                                    tracker_stats["leechers"],
                                )
                                return tracker_stats
                    finally:
                        await http_client.stop()

            except Exception as e:
                # Log error but continue to next tracker
                self.logger.debug(
                    "Failed to scrape from tracker %s: %s", tracker_url, e
                )
                continue

        # If we get here, no tracker returned successful results
        return {}

    async def _scrape_from_dht(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape statistics from DHT based on chunk availability.

        For XET, this queries DHT for peers that have chunks for this torrent
        and calculates statistics based on chunk availability.

        Args:
            torrent_info: Torrent information

        Returns:
            Dictionary with DHT-based statistics, or empty dict if unavailable

        """
        dht_stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        if not self.dht_client:
            self.logger.debug("DHT client not available for scraping")
            return {}

        try:
            # Get all unique peers for this torrent via DHT
            all_peers: set[tuple[str, int]] = set()

            # Query DHT for peers using torrent info_hash
            if hasattr(self.dht_client, "get_peers"):
                try:
                    dht_peers = await self.dht_client.get_peers(torrent_info.info_hash)
                    for peer in dht_peers:
                        if isinstance(peer, tuple) and len(peer) >= 2:
                            all_peers.add((str(peer[0]), int(peer[1])))
                        elif hasattr(peer, "ip") and hasattr(peer, "port"):
                            all_peers.add((peer.ip, peer.port))
                except Exception as e:
                    self.logger.debug("Error querying DHT for torrent peers: %s", e)

            # Also query using info_hash_v2 if available (BEP 52)
            if torrent_info.info_hash_v2:
                try:
                    if hasattr(self.dht_client, "get_peers"):
                        v2_peers = await self.dht_client.get_peers(
                            torrent_info.info_hash_v2
                        )
                        for peer in v2_peers:
                            if isinstance(peer, tuple) and len(peer) >= 2:
                                all_peers.add((str(peer[0]), int(peer[1])))
                            elif hasattr(peer, "ip") and hasattr(peer, "port"):
                                all_peers.add((peer.ip, peer.port))
                except Exception as e:
                    self.logger.debug("Error querying DHT v2 for torrent peers: %s", e)

            # Query for chunk-specific peers if XET metadata is available
            chunk_peers: set[tuple[str, int]] = set()
            chunk_hashes_to_query: list[bytes] = []

            if torrent_info.xet_metadata and self.cas_client:
                xet_meta = torrent_info.xet_metadata
                # Get chunk hashes from XET metadata
                if xet_meta.chunk_hashes:
                    chunk_hashes_to_query.extend(
                        xet_meta.chunk_hashes[:10]
                    )  # Limit queries
                else:
                    # Extract from piece metadata
                    for piece_meta in xet_meta.piece_metadata[:5]:  # Limit queries
                        chunk_hashes_to_query.extend(piece_meta.chunk_hashes[:2])

                # Query for peers for each chunk
                for chunk_hash in chunk_hashes_to_query:
                    try:
                        peers = await self.cas_client.find_chunk_peers(chunk_hash)
                        for peer in peers:
                            if hasattr(peer, "ip") and hasattr(peer, "port"):
                                chunk_peers.add((peer.ip, peer.port))
                    except Exception as e:
                        self.logger.debug(
                            "Error querying chunk peers for %s: %s",
                            chunk_hash.hex()[:16],
                            e,
                        )

            # Combine all discovered peers
            all_peers.update(chunk_peers)

            # Calculate statistics based on peer count
            # For XET, we estimate:
            # - Seeders: peers that have all chunks (we can't verify this without connecting,
            #   so we use a heuristic: if we found peers via chunk discovery, they likely have chunks)
            # - Leechers: peers that have some but not all chunks
            total_peers = len(all_peers)

            if total_peers > 0:
                # Heuristic: if we found peers via chunk discovery, they're likely seeders
                # Peers found only via torrent hash might be leechers
                chunk_seeder_count = len(chunk_peers)
                regular_peer_count = total_peers - chunk_seeder_count

                # Estimate seeders as peers with chunk availability
                dht_stats["seeders"] = max(chunk_seeder_count, total_peers // 2)
                # Estimate leechers as remaining peers
                dht_stats["leechers"] = max(0, total_peers - dht_stats["seeders"])

                self.logger.debug(
                    "DHT scrape found %d total peers (%d via chunks, %d via torrent hash)",
                    total_peers,
                    chunk_seeder_count,
                    regular_peer_count,
                )

            return dht_stats

        except Exception as e:
            self.logger.warning("Error scraping from DHT: %s", e)
            return {}

    def _torrent_info_to_dict(self, torrent_info: TorrentInfo) -> dict[str, Any]:
        """Convert TorrentInfo model to torrent_data dict format.

        Args:
            torrent_info: TorrentInfo model

        Returns:
            Dictionary in format expected by tracker clients

        """
        # Build announce_list (flattened list)
        announce_list = []
        if torrent_info.announce_list:
            for tier in torrent_info.announce_list:
                announce_list.extend(tier)

        # Build file_info dict
        file_info = {
            "type": "multi" if len(torrent_info.files) > 1 else "single",
            "total_length": torrent_info.total_length,
            "name": torrent_info.name,
        }

        if torrent_info.files:
            if len(torrent_info.files) == 1:
                file_info["length"] = torrent_info.files[0].length
            else:
                file_info["files"] = [
                    {
                        "length": f.length,
                        "path": f.path or [],
                        "full_path": f.full_path or "",
                    }
                    for f in torrent_info.files
                ]

        return {
            "announce": torrent_info.announce,
            "announce_list": announce_list,
            "info_hash": torrent_info.info_hash,
            "name": torrent_info.name,
            "file_info": file_info,
            "total_length": torrent_info.total_length,
        }

    def _get_tracker_urls(self, torrent_info: TorrentInfo) -> list[str]:
        """Extract all tracker URLs from TorrentInfo.

        Args:
            torrent_info: TorrentInfo model

        Returns:
            List of tracker URLs (announce + all from announce_list)

        """
        urls = []

        # Add primary announce URL
        if torrent_info.announce:
            urls.append(torrent_info.announce)

        # Add URLs from announce_list
        if torrent_info.announce_list:
            for tier in torrent_info.announce_list:
                urls.extend(tier)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _deduplicate_peers(self, peers: list[PeerInfo]) -> list[PeerInfo]:
        """Remove duplicate peers based on IP and port.

        Args:
            peers: List of peers to deduplicate

        Returns:
            List of unique peers

        """
        seen = set()
        unique_peers = []

        for peer in peers:
            peer_key = (peer.ip, peer.port)
            if peer_key not in seen:
                seen.add(peer_key)
                unique_peers.append(peer)

        return unique_peers
