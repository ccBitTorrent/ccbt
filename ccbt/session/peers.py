from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, cast

from ccbt.session.models import SessionContext
from ccbt.session.peer_events import PeerEventsBinder
from ccbt.session.types import PeerManagerProtocol

if TYPE_CHECKING:
    from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager


class PeerManagerInitializer:
    """Create and start the peer manager early, and wire session callbacks."""

    async def init_and_bind(
        self,
        download_manager: Any,
        *,
        is_private: bool,
        session_ctx: SessionContext,
        on_peer_connected: Callable[..., None] | None = None,
        on_peer_disconnected: Callable[..., None] | None = None,
        on_piece_received: Callable[..., None] | None = None,
        on_bitfield_received: Callable[..., None] | None = None,
        logger: Any | None = None,
    ) -> Any:
        """Ensure a running peer manager exists and is bound to callbacks.

        Returns:
            The initialized peer manager instance.

        """
        # Reuse existing peer manager when present
        pm = getattr(download_manager, "peer_manager", None)
        if pm is None:
            # Validate torrent_data
            td = getattr(download_manager, "torrent_data", None)
            if not isinstance(td, dict):
                if logger:
                    logger.error(
                        "Cannot initialize peer_manager early: torrent_data must be a dict, got %s",
                        type(td),
                    )
                raise TypeError(
                    "torrent_data must be a dict for peer manager initialization"
                )

            # Create new peer manager
            from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

            piece_manager = getattr(download_manager, "piece_manager", None)
            our_peer_id = getattr(download_manager, "our_peer_id", None)
            pm = AsyncPeerConnectionManager(td, piece_manager, our_peer_id)

            # Wire security/private flags if available
            if hasattr(download_manager, "security_manager"):
                pm._security_manager = download_manager.security_manager  # type: ignore[attr-defined]
            pm._is_private = is_private  # type: ignore[attr-defined]

            download_manager.peer_manager = pm

        # Bind session callbacks consistently via binder
        binder = PeerEventsBinder(session_ctx)
        binder.bind_peer_manager(
            cast("PeerManagerProtocol", pm),
            on_peer_connected=on_peer_connected,
            on_peer_disconnected=on_peer_disconnected,
            on_piece_received=on_piece_received,
            on_bitfield_received=on_bitfield_received,
        )

        # Start the peer manager if a start method exists
        if hasattr(pm, "start"):
            await pm.start()  # type: ignore[misc]

        return pm


class PeerManagerBinder:
    """Facade for binding piece manager events in a consistent way."""

    def bind_piece_manager(
        self,
        session_ctx: SessionContext,
        piece_manager: Any,
        *,
        on_piece_verified: Callable[[int], None] | None = None,
        on_download_complete: Callable[[], None] | None = None,
        on_piece_completed: Callable[[int], None] | None = None,
    ) -> None:
        binder = PeerEventsBinder(session_ctx)
        binder.bind_piece_manager(
            piece_manager,
            on_piece_completed=on_piece_completed,
            on_piece_verified=on_piece_verified,
            on_download_complete=on_download_complete,
        )


class PexBinder:
    """Bind and start PEX for a session, wiring callbacks and start."""

    async def bind_and_start(self, session: Any) -> None:
        # Do not enable on private torrents
        if session.is_private:
            session.logger.debug(
                "PEX disabled for private torrent: %s", session.info.name
            )
            return
        import asyncio

        from ccbt.discovery.pex import PEXManager

        session.logger.info("Setting up PEX manager for %s", session.info.name)
        session.pex_manager = PEXManager()

        # Send callback: forward PEX messages via extension protocol
        async def send_pex_message(
            peer_key: str, peer_data: bytes, is_added: bool = True
        ) -> bool:
            try:
                import struct

                from ccbt.extensions.manager import get_extension_manager
                from ccbt.extensions.pex import PEXMessageType
                from ccbt.extensions.protocol import ExtensionMessageType

                if not session.download_manager:
                    session.logger.debug("Download manager not available for PEX")
                    return False
                peer_manager = getattr(session.download_manager, "peer_manager", None)
                if not peer_manager:
                    session.logger.debug("Peer manager not available for PEX")
                    return False

                # Find connection by peer_key
                connection = None
                async with peer_manager.connection_lock:
                    for conn in peer_manager.connections.values():
                        if not conn.is_connected():
                            continue
                        if conn.peer_info:
                            peer_str = f"{conn.peer_info.ip}:{conn.peer_info.port}"
                            if peer_str == peer_key or str(conn.peer_info) == peer_key:
                                connection = conn
                                break
                if not connection or not connection.writer:
                    session.logger.debug(
                        "Peer connection not found or writer missing for PEX: %s",
                        peer_key,
                    )
                    return False

                extension_manager = get_extension_manager()
                extension_protocol = extension_manager.get_extension("protocol")
                if not extension_protocol:
                    session.logger.debug("Extension protocol not available for PEX")
                    return False
                pex_session = (
                    session.pex_manager.sessions.get(peer_key)
                    if session.pex_manager
                    else None
                )
                if not pex_session or not pex_session.ut_pex_id:
                    session.logger.debug(
                        "PEX session or ut_pex_id not found for %s", peer_key
                    )
                    return False
                if not peer_data:
                    return True

                pex_message_type = (
                    PEXMessageType.ADDED if is_added else PEXMessageType.DROPPED
                )
                payload = (
                    struct.pack("BB", pex_session.ut_pex_id, pex_message_type)
                    + peer_data
                )
                extension_message = extension_protocol.encode_extension_message(
                    ExtensionMessageType.EXTENDED, payload
                )
                connection.writer.write(extension_message)
                await connection.writer.drain()
                return True
            except Exception as e:
                session.logger.warning(
                    "Error in PEX send callback for %s: %s", peer_key, e
                )
                return False

        session.pex_manager.send_pex_callback = send_pex_message

        # Connected peers callback
        async def get_connected_peers() -> list[tuple[str, int]]:
            peers_list: list[tuple[str, int]] = []
            try:
                if session.download_manager:
                    peer_manager = getattr(
                        session.download_manager, "peer_manager", None
                    )
                    if peer_manager:
                        async with peer_manager.connection_lock:
                            peers_list.extend(
                                (conn.peer_info.ip, conn.peer_info.port)
                                for conn in peer_manager.connections.values()
                                if conn.is_connected() and conn.peer_info
                            )
            except Exception as e:
                session.logger.debug("Error getting connected peers for PEX: %s", e)
            return peers_list

        session.pex_manager.get_connected_peers_callback = get_connected_peers

        # Discovered peers handler
        async def on_pex_peers_discovered(pex_peers: list) -> None:
            try:
                session.logger.info(
                    "PEX discovered %d peer(s) for torrent %s",
                    len(pex_peers),
                    session.info.name,
                )
                peer_list = [
                    {"ip": p.ip, "port": p.port, "peer_source": "pex"}
                    for p in pex_peers
                    if hasattr(p, "ip") and hasattr(p, "port")
                ]
                if not peer_list:
                    return
                if not hasattr(session.download_manager, "_download_started"):
                    # Ensure download started
                    if not hasattr(session.download_manager, "_started") or not getattr(
                        session.download_manager, "_started", False
                    ):
                        await session.download_manager.start()
                    await session.download_manager.start_download(peer_list)
                    if session.download_manager.peer_manager:
                        pm = session.download_manager.peer_manager
                        # Use download_manager callbacks (they exist there, not on session)
                        if hasattr(session.download_manager, "_on_peer_connected"):
                            pm.on_peer_connected = session.download_manager._on_peer_connected
                        if hasattr(session.download_manager, "_on_peer_disconnected"):
                            pm.on_peer_disconnected = session.download_manager._on_peer_disconnected
                        if hasattr(session.download_manager, "_on_piece_received"):
                            pm.on_piece_received = session.download_manager._on_piece_received
                        if hasattr(session.download_manager, "_on_bitfield_received"):
                            pm.on_bitfield_received = session.download_manager._on_bitfield_received
                    setattr(session.download_manager, "_download_started", True)  # noqa: B010
                else:
                    helper = PeerConnectionHelper(session)
                    await helper.connect_peers_to_download(peer_list)
            except Exception as e:
                session.logger.warning(
                    "Error adding PEX-discovered peers: %s", e, exc_info=True
                )

        # Register PEX callback (manager expects sync callback)
        def pex_callback_wrapper(pex_peers: list) -> None:
            task = session._task_supervisor.create_task(
                on_pex_peers_discovered(pex_peers), name="pex_on_discovered"
            )  # type: ignore[attr-defined]
            _ = task

        session.pex_manager.pex_callbacks.append(pex_callback_wrapper)
        session.logger.info(
            "Registered PEX callback for %s (total callbacks: %d)",
            session.info.name,
            len(session.pex_manager.pex_callbacks),
        )

        # Start PEX manager
        try:
            await asyncio.wait_for(session.pex_manager.start(), timeout=5.0)
        except asyncio.TimeoutError:
            session.logger.warning("Timeout starting PEX manager (continuing anyway)")
        except Exception as e:
            session.logger.warning(
                "Error starting PEX manager: %s (continuing anyway)", e
            )


class PeerConnectionHelper:
    """Helper class for connecting peers to download manager."""

    def __init__(self, session: Any) -> None:
        """Initialize peer connection helper.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session
        self.logger = session.logger
        
        # IMPROVEMENT: Track peer quality ranking metrics
        self._peer_quality_metrics = {
            "total_rankings": 0,
            "total_peers_ranked": 0,
            "quality_scores": [],
            "last_ranking": {
                "timestamp": 0.0,
                "peers_ranked": 0,
                "average_score": 0.0,
                "high_quality_count": 0,
                "medium_quality_count": 0,
                "low_quality_count": 0,
            },
        }

    def _rank_peers_by_quality(
        self, peer_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Rank peers by quality before connection.
        
        Quality factors:
        1. Historical performance (if available from security manager)
        2. Connection success rate
        3. Geographic proximity (lower latency estimate)
        4. Upload/download ratio (if available)
        
        Args:
            peer_list: List of peer dictionaries
            
        Returns:
            Ranked list of peers (best quality first)
        """
        if not peer_list:
            return []
        
        # Get security manager for historical performance data
        security_manager = None
        if hasattr(self.session, "download_manager"):
            security_manager = getattr(
                self.session.download_manager, "security_manager", None
            )
        
        scored_peers = []
        for peer in peer_list:
            ip = peer.get("ip", "")
            port = peer.get("port", 0)
            peer_key = f"{ip}:{port}"
            
            score = 0.0
            factors = []
            
            # Factor 1: Historical performance (0.0-1.0, weight: 0.4)
            if security_manager and hasattr(security_manager, "get_peer_reputation"):
                try:
                    reputation = security_manager.get_peer_reputation(peer_key, ip)
                    if reputation:
                        # Use reputation score (0.0-1.0)
                        perf_score = reputation.reputation_score
                        score += perf_score * 0.4
                        factors.append(f"perf={perf_score:.2f}")
                        
                        # Penalize blacklisted peers
                        if reputation.is_blacklisted:
                            score = -1.0  # Strongly penalize
                            factors.append("blacklisted")
                except Exception:
                    pass  # No reputation data available
            
            # Factor 2: Connection success rate estimate (0.0-1.0, weight: 0.2)
            # For new peers, assume moderate success rate
            # For peers with history, use actual success rate
            success_rate = 0.5  # Default for unknown peers
            if security_manager and hasattr(security_manager, "get_peer_reputation"):
                try:
                    reputation = security_manager.get_peer_reputation(peer_key, ip)
                    if reputation and hasattr(reputation, "success_rate"):
                        success_rate = reputation.success_rate
                except Exception:
                    pass
            score += success_rate * 0.2
            factors.append(f"success={success_rate:.2f}")
            
            # Factor 3: Source quality (0.0-1.0, weight: 0.2)
            # DHT and tracker peers are generally more reliable than PEX
            source = peer.get("peer_source", "unknown")
            source_scores = {
                "tracker": 1.0,
                "dht": 0.9,
                "pex": 0.7,
                "incoming": 0.8,
                "dht_node": 0.6,
                "unknown": 0.5,
            }
            source_score = source_scores.get(source, 0.5)
            score += source_score * 0.2
            factors.append(f"source={source}")
            
            # Factor 4: Geographic proximity estimate (0.0-1.0, weight: 0.05 - reduced to allow distant peers)
            # RELAXED: Reduced weight from 0.2 to 0.05 to allow connecting to slower/distant peers
            # Simple heuristic: assume peers from same country/region have lower latency
            # For now, use a simple hash-based estimate (can be improved with GeoIP)
            # This is a placeholder - in production, use actual GeoIP lookup
            proximity_score = 0.5  # Default moderate proximity
            # TODO: Implement actual GeoIP lookup for better proximity estimation
            # RELAXED: Use minimal weight to avoid penalizing distant but useful peers
            proximity_weight = getattr(
                self.session.config.network,
                "peer_quality_proximity_weight",
                0.05,  # Default to 0.05 instead of 0.2
            )
            score += proximity_score * proximity_weight
            factors.append(f"proximity={proximity_score:.2f}(w={proximity_weight:.2f})")
            
            scored_peers.append((score, peer, factors))
        
        # Sort by score (descending) - best peers first
        scored_peers.sort(key=lambda x: x[0], reverse=True)
        
        # IMPROVEMENT: Track peer quality metrics
        current_time = time.time()
        quality_scores = [score for score, _, _ in scored_peers if score >= 0.0]
        high_quality = sum(1 for s in quality_scores if s > 0.7)
        medium_quality = sum(1 for s in quality_scores if 0.3 < s <= 0.7)
        low_quality = sum(1 for s in quality_scores if s <= 0.3)
        avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        self._peer_quality_metrics["total_rankings"] += 1
        self._peer_quality_metrics["total_peers_ranked"] += len(quality_scores)
        self._peer_quality_metrics["quality_scores"].extend(quality_scores)
        if len(self._peer_quality_metrics["quality_scores"]) > 1000:
            # Keep only last 1000 scores
            self._peer_quality_metrics["quality_scores"] = self._peer_quality_metrics["quality_scores"][-1000:]
        
        self._peer_quality_metrics["last_ranking"] = {
            "timestamp": current_time,
            "peers_ranked": len(quality_scores),
            "average_score": avg_score,
            "high_quality_count": high_quality,
            "medium_quality_count": medium_quality,
            "low_quality_count": low_quality,
        }
        
        # IMPROVEMENT: Emit event for peer quality ranking
        try:
            from ccbt.utils.events import emit_event, EventType, Event
            asyncio.create_task(emit_event(Event(
                event_type=EventType.PEER_QUALITY_RANKED.value,
                data={
                    "info_hash": self.session.info.info_hash.hex() if hasattr(self.session, "info") else "",
                    "torrent_name": self.session.info.name if hasattr(self.session, "info") else "",
                    "total_peers": len(quality_scores),
                    "average_score": avg_score,
                    "high_quality_count": high_quality,
                    "medium_quality_count": medium_quality,
                    "low_quality_count": low_quality,
                },
            )))
        except Exception as e:
            self.logger.debug("Failed to emit peer quality ranked event: %s", e)
        
        # Log top peers for debugging
        if scored_peers:
            top_5 = scored_peers[:5]
            self.logger.debug(
                "Top 5 ranked peers: %s",
                ", ".join(
                    [
                        f"{p[1].get('ip')}:{p[1].get('port')} (score={p[0]:.2f}, {', '.join(p[2])})"
                        for p in top_5
                    ]
                ),
            )
        
        # Return ranked peer list (without scores, filter out blacklisted)
        return [peer for score, peer, _ in scored_peers if score >= 0.0]

    async def connect_peers_to_download(self, peer_list: list[dict[str, Any]]) -> None:
        """Connect peers to the download manager after download has started.

        Args:
            peer_list: List of peer dictionaries with 'ip', 'port', and optionally 'peer_source'

        """
        if not peer_list:
            return

        # CRITICAL FIX: Validate peer_manager exists before attempting to connect
        # If peer_manager is not ready, queue peers for later connection
        peer_manager = getattr(self.session.download_manager, "peer_manager", None)
        if not peer_manager:
            self.session.logger.warning(
                "peer_manager not ready, queuing %d peer(s) for later connection",
                len(peer_list),
            )
            # Store peers for later connection (with timestamp for timeout)
            if not hasattr(self.session, "_queued_peers"):
                self.session._queued_peers = []
            # Add timestamp to each peer for timeout checking
            current_time = time.time()
            for peer in peer_list:
                peer["_queued_at"] = current_time
            self.session._queued_peers.extend(peer_list)
            self.session.logger.debug(
                "Queued %d peer(s) for later connection (total queued: %d)",
                len(peer_list),
                len(self.session._queued_peers),
            )
            return

        # IMPROVEMENT: Peer quality-based prioritization
        # Rank peers by quality before connecting
        self.session.logger.debug(
            "Ranking %d peer(s) by quality before connection for %s",
            len(peer_list),
            self.session.info.name if hasattr(self.session, "info") else "unknown",
        )
        ranked_peers = self._rank_peers_by_quality(peer_list)
        
        # CRITICAL FIX: Log quality filtering results
        filtered_count = len(peer_list) - len(ranked_peers)
        if filtered_count > 0:
            self.session.logger.debug(
                "Quality filter removed %d peer(s) (input: %d, output: %d) for %s",
                filtered_count,
                len(peer_list),
                len(ranked_peers),
                self.session.info.name if hasattr(self.session, "info") else "unknown",
            )
        
        # CRITICAL FIX: Add detailed logging for peer connection attempts
        peer_sources = {}
        for peer in ranked_peers:
            source = peer.get("peer_source", "unknown")
            peer_sources[source] = peer_sources.get(source, 0) + 1

        source_summary = ", ".join(
            [f"{count} from {source}" for source, count in peer_sources.items()]
        )
        self.session.logger.info(
            "Attempting to connect %d peer(s) to download (%s) - ranked by quality for %s",
            len(ranked_peers),
            source_summary,
            self.session.info.name if hasattr(self.session, "info") else "unknown",
        )
        
        # Use ranked peers instead of original list
        peer_list = ranked_peers

        # Update peer discovery metrics
        for peer in peer_list:
            source = peer.get("peer_source", "unknown")
            if (
                source
                in self.session._peer_discovery_metrics["peers_discovered_by_source"]
            ):
                self.session._peer_discovery_metrics["peers_discovered_by_source"][
                    source
                ] += 1
            else:
                self.session._peer_discovery_metrics["peers_discovered_by_source"][
                    "unknown"
                ] += 1
        self.session._peer_discovery_metrics["connection_attempts"] += len(peer_list)
        self.session._peer_discovery_metrics["last_peer_discovery_time"] = time.time()

        # Log first few peer addresses for debugging
        if len(peer_list) > 0:
            sample_peers = peer_list[:5]
            peer_addresses = [
                f"{p.get('ip', 'unknown')}:{p.get('port', 0)}" for p in sample_peers
            ]
            self.session.logger.debug(
                "Sample peer addresses to connect: %s%s",
                ", ".join(peer_addresses),
                "..." if len(peer_list) > 5 else "",
            )

        # CRITICAL FIX: Wait for peer_manager to be fully initialized if download has started
        # This handles the race condition where download is started but peer_manager isn't ready yet
        # CRITICAL FIX: Increased max_wait_attempts and wait_interval for better reliability
        max_wait_attempts = 20  # Increased from 10 to allow more time for initialization (10 seconds total)
        wait_interval = 0.5
        peer_manager: AsyncPeerConnectionManager | None = None  # type: ignore[assignment]
        peer_manager_source = "unknown"

        for attempt in range(max_wait_attempts):
            # Try to get peer_manager from download_manager first
            peer_manager = getattr(self.session.download_manager, "peer_manager", None)
            peer_manager_source = "download_manager"

            # CRITICAL FIX: Check if peer_manager is fully initialized (has required methods AND is started)
            if peer_manager and hasattr(peer_manager, "connect_to_peers"):
                # Verify peer_manager is started (has _running flag or connections dict)
                # Also check that connections dict exists and is accessible
                is_started = False
                has_connections = False

                # Check _running flag
                if getattr(peer_manager, "_running", False):
                    is_started = True

                # Check if connections dict exists and is accessible
                if hasattr(peer_manager, "connections"):
                    try:
                        connections = peer_manager.connections
                        # Verify connections is a dict-like object (has __len__ or is a dict)
                        if connections is not None and (
                            isinstance(connections, dict)
                            or hasattr(connections, "__len__")
                        ):
                            has_connections = True
                            is_started = True
                    except Exception as e:
                        self.session.logger.debug(
                            "Error checking peer_manager.connections (attempt %d/%d): %s",
                            attempt + 1,
                            max_wait_attempts,
                            e,
                        )

                if is_started and has_connections:
                    self.session.logger.debug(
                        "Peer manager is fully initialized (attempt %d/%d, has_connections=%s)",
                        attempt + 1,
                        max_wait_attempts,
                        has_connections,
                    )
                    break
                self.session.logger.debug(
                    "Peer manager exists but not fully started yet (attempt %d/%d, is_started=%s, has_connections=%s), waiting...",
                    attempt + 1,
                    max_wait_attempts,
                    is_started,
                    has_connections,
                )
                peer_manager = None

            # Fallback to session-level peer_manager if download_manager doesn't have one
            if not peer_manager:
                peer_manager = self.session.peer_manager
                peer_manager_source = "session"
                if peer_manager and hasattr(peer_manager, "connect_to_peers"):
                    # Same validation as above
                    is_started = getattr(peer_manager, "_running", False) or (
                        hasattr(peer_manager, "connections")
                        and peer_manager.connections is not None
                    )
                    if is_started:
                        break
                    peer_manager = None

            # Wait before retrying if peer_manager not ready
            if not peer_manager or not hasattr(peer_manager, "connect_to_peers"):
                if attempt < max_wait_attempts - 1:
                    self.session.logger.debug(
                        "Peer manager not ready yet (attempt %d/%d), waiting %.1fs...",
                        attempt + 1,
                        max_wait_attempts,
                        wait_interval,
                    )
                    await asyncio.sleep(wait_interval)
                else:
                    # CRITICAL FIX: If peer_manager still not ready after max attempts, log detailed diagnostics
                    self.session.logger.warning(
                        "Peer manager not initialized after %d attempts - cannot connect peers. "
                        "download_manager=%s, has_peer_manager=%s, peer_manager_type=%s, "
                        "session_peer_manager=%s",
                        max_wait_attempts,
                        self.session.download_manager is not None,
                        hasattr(self.session.download_manager, "peer_manager")
                        if self.session.download_manager
                        else False,
                        type(
                            getattr(self.session.download_manager, "peer_manager", None)
                        ).__name__
                        if self.session.download_manager
                        and hasattr(self.session.download_manager, "peer_manager")
                        else "None",
                        self.session.peer_manager is not None,
                    )

        if peer_manager and hasattr(peer_manager, "connect_to_peers"):
            self.session.logger.info(
                "Peer manager ready: connecting %d peer(s) from %s for %s",
                len(peer_list),
                peer_manager_source,
                self.session.info.name if hasattr(self.session, "info") else "unknown",
            )
            self.session.logger.debug(
                "Using peer_manager from %s to connect %d peers",
                peer_manager_source,
                len(peer_list),
            )

            # CRITICAL FIX: Process queued peers now that peer_manager is ready
            if hasattr(self.session, "_queued_peers") and self.session._queued_peers:
                queued_count = len(self.session._queued_peers)
                self.session.logger.info(
                    "Processing %d queued peer(s) now that peer_manager is ready",
                    queued_count,
                )
                # Process queued peers (with timeout check)
                current_time = time.time()
                valid_queued_peers = []
                for queued_peer in self.session._queued_peers:
                    # Check if peer was queued more than 60 seconds ago (timeout)
                    queued_time = queued_peer.get("_queued_at", current_time)
                    if current_time - queued_time < 60.0:
                        # Remove the internal timestamp before adding to peer_list
                        queued_peer_copy = queued_peer.copy()
                        queued_peer_copy.pop("_queued_at", None)
                        valid_queued_peers.append(queued_peer_copy)
                    else:
                        self.session.logger.debug(
                            "Rejecting queued peer %s:%d (timeout: queued %.1fs ago)",
                            queued_peer.get("ip", "unknown"),
                            queued_peer.get("port", 0),
                            current_time - queued_time,
                        )

                # Clear queued peers list
                self.session._queued_peers = []

                if valid_queued_peers:
                    # Add valid queued peers to current peer_list
                    peer_list = valid_queued_peers + peer_list
                    self.session.logger.info(
                        "Added %d valid queued peer(s) to connection list (total: %d)",
                        len(valid_queued_peers),
                        len(peer_list),
                    )
                else:
                    self.session.logger.debug("All queued peers expired (timeout)")

            try:
                # async_main.AsyncDownloadManager: peer_manager is already started by start_download()
                # Just connect the new peers
                self.session.logger.info(
                    "🔗 PEER CONNECTION: Calling connect_to_peers() with %d peer(s) for %s",
                    len(peer_list),
                    self.session.info.name if hasattr(self.session, "info") else "unknown",
                )
                await peer_manager.connect_to_peers(peer_list)  # type: ignore[attr-defined]
                self.session.logger.info(
                    "✅ PEER CONNECTION: connect_to_peers() completed for %d peer(s) for %s",
                    len(peer_list),
                    self.session.info.name if hasattr(self.session, "info") else "unknown",
                )
                # CRITICAL FIX: connect_to_peers() returns after scheduling tasks, not after connections complete
                # Wait a short time for connections to establish, then check actual connection count
                await asyncio.sleep(2.0)  # Give connections time to establish

                # Check actual connection count to see if any peers actually connected
                actual_peers = 0
                active_peers = 0
                if hasattr(peer_manager, "connections"):
                    connections = peer_manager.connections  # type: ignore[attr-defined]
                    actual_peers = len(connections)
                    # Count active connections (handshake completed)
                    if hasattr(peer_manager, "get_active_peers"):
                        active_peers = len(peer_manager.get_active_peers())  # type: ignore[attr-defined]
                    else:
                        # Fallback: count connections that are not in DISCONNECTED state
                        from ccbt.peer.async_peer_connection import ConnectionState

                        active_peers = sum(
                            1
                            for conn in connections.values()
                            if hasattr(conn, "state")
                            and conn.state != ConnectionState.DISCONNECTED
                        )

                    # Count connection errors
                    connection_errors = 0
                    for conn in connections.values():
                        if hasattr(conn, "error") and getattr(conn, "error", None):
                            connection_errors += 1

                # Enhanced logging for connection results
                if active_peers > 0:
                    self.session.logger.info(
                        "Successfully connected to %d/%d peer(s) (%d active, %d total connections, %d errors)",
                        active_peers,
                        len(peer_list),
                        active_peers,
                        actual_peers,
                        connection_errors,
                    )
                    # Update connection success metrics
                    self.session._peer_discovery_metrics["connection_successes"] += (
                        active_peers
                    )
                    self.session._peer_discovery_metrics[
                        "last_peer_connection_time"
                    ] = time.time()
                elif actual_peers > 0:
                    self.session.logger.warning(
                        "Connected to %d peer(s) but none are active yet (total connections: %d, errors: %d). "
                        "This may be normal if handshakes are still in progress.",
                        actual_peers,
                        actual_peers,
                        connection_errors,
                    )
                    # Partial success - count as successes for now (may become active later)
                    self.session._peer_discovery_metrics["connection_successes"] += (
                        actual_peers
                    )
                else:
                    self.session.logger.warning(
                        "Failed to connect to any of %d peer(s) (attempted via %s peer_manager). "
                        "This may indicate network issues, firewall blocking, or peers being unreachable.",
                        len(peer_list),
                        peer_manager_source,
                    )
                    # Update connection failure metrics
                    self.session._peer_discovery_metrics["connection_failures"] += len(
                        peer_list
                    )
                # Update cache with new peer count - but use actual connected count
                # connect_to_peers doesn't guarantee all peers connect, so we check actual connections
                if hasattr(peer_manager, "connections"):
                    actual_peers = len(peer_manager.connections)  # type: ignore[attr-defined]
                    self.session._cached_status["peers"] = actual_peers
                    self.session.logger.debug(
                        "Updated peer count: %d actual connections (attempted %d)",
                        actual_peers,
                        len(peer_list),
                    )
                else:
                    # Fallback: increment by list length (less accurate)
                    current_peers = self.session._cached_status.get("peers", 0)
                    self.session._cached_status["peers"] = current_peers + len(
                        peer_list
                    )
            except Exception as e:
                self.session.logger.warning(
                    "Failed to connect %d peers via %s peer_manager: %s",
                    len(peer_list),
                    peer_manager_source,
                    e,
                    exc_info=True,
                )
        elif hasattr(self.session.download_manager, "add_peers"):
            # Fallback: try add_peers method if available
            try:
                add_peers_method = self.session.download_manager.add_peers
                if asyncio.iscoroutinefunction(add_peers_method):
                    await add_peers_method(peer_list)  # type: ignore[arg-type]
                else:
                    add_peers_method(peer_list)  # type: ignore[arg-type]
                self.session.logger.info(
                    "Added %d peers via add_peers method", len(peer_list)
                )
            except Exception as e:
                self.session.logger.warning("Failed to add peers via add_peers: %s", e)
        else:
            # async_main.AsyncDownloadManager should have peer_manager after start_download()
            # If we get here, download hasn't been started yet
            self.session.logger.warning(
                "Cannot connect %d peers: No peer_manager available. "
                "Download manager type: %s, Has peer_manager: %s, Session peer_manager: %s. "
                "Download must be started with start_download() before connecting peers.",
                len(peer_list),
                type(self.session.download_manager).__name__,
                hasattr(self.session.download_manager, "peer_manager"),
                self.session.peer_manager is not None,
            )
