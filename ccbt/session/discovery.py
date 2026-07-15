"""Peer discovery coordination.

This module coordinates peer discovery across multiple sources including
trackers, DHT, PEX, and other discovery mechanisms.

Requestable-peer-driven orchestration (Project 7-E) lives in
`ccbt.session.dht_setup.DHTDiscoverySetup.tick_requestable_driven`, invoked from
the per-torrent DHT discovery loop so scheduling stays next to bootstrap and
get_peers rate limits.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, ClassVar, Iterable, Optional

from ccbt.session.tasks import TaskSupervisor

if TYPE_CHECKING:
    from ccbt.session.models import SessionContext
    from ccbt.session.types import DHTClientProtocol


@dataclass
class EndpointCandidate:
    """Freshness and delivery state for one discovered peer endpoint."""

    peer: dict[str, Any]
    first_seen: float
    last_seen: float
    sources: set[str] = field(default_factory=set)
    attempts: int = 0
    last_attempt: Optional[float] = None
    next_retry_at: float = 0.0
    accepted_at: Optional[float] = None
    state: str = "pending"


class EndpointCandidateStore:
    """Bounded, TTL-aware endpoint store used at discovery delivery boundaries."""

    _SOURCE_PRIORITY: ClassVar[dict[str, float]] = {
        "tracker": 1.0,
        "incoming": 0.8,
        "pex": 0.7,
        "dht": 0.6,
        "unknown": 0.5,
    }

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        accepted_refresh_seconds: float = 60.0,
        retry_base_seconds: float = 1.0,
        max_candidates: int = 2000,
    ) -> None:
        """Initialize candidate retention, retry, and capacity bounds."""
        self.ttl_seconds = max(1.0, ttl_seconds)
        self.accepted_refresh_seconds = max(0.0, accepted_refresh_seconds)
        self.retry_base_seconds = max(0.0, retry_base_seconds)
        self.max_candidates = max(1, max_candidates)
        self._records: dict[tuple[str, int], EndpointCandidate] = {}

    @staticmethod
    def _normalize(peer: Any, source: str) -> Optional[dict[str, Any]]:
        if isinstance(peer, dict):
            raw = dict(peer)
            ip = raw.get("ip")
            port = raw.get("port")
        elif isinstance(peer, (tuple, list)) and len(peer) >= 2:
            ip, port = peer[0], peer[1]
            raw = {}
        else:
            return None
        try:
            port_int = int(port)
        except (TypeError, ValueError):
            return None
        if not ip or port_int <= 0 or port_int > 65535:
            return None
        raw["ip"] = str(ip)
        raw["port"] = port_int
        raw.setdefault("peer_source", source)
        return raw

    @staticmethod
    def _key(peer: dict[str, Any]) -> tuple[str, int]:
        return str(peer["ip"]), int(peer["port"])

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, record in self._records.items()
            if now - record.last_seen > self.ttl_seconds
        ]
        for key in expired:
            self._records.pop(key, None)
        if len(self._records) <= self.max_candidates:
            return
        ranked = sorted(
            self._records.items(),
            key=lambda item: (
                item[1].state == "accepted",
                item[1].last_seen,
                self._priority(item[1]),
            ),
        )
        for key, _ in ranked[: len(self._records) - self.max_candidates]:
            self._records.pop(key, None)

    def _priority(self, record: EndpointCandidate) -> float:
        explicit = float(record.peer.get("_replacement_priority", 0.0) or 0.0)
        source = max(
            (self._SOURCE_PRIORITY.get(item, 0.5) for item in record.sources),
            default=0.5,
        )
        return explicit + source

    def observe(
        self,
        peers: Iterable[Any],
        *,
        source: str,
        now: Optional[float] = None,
    ) -> int:
        """Merge sightings while retaining source provenance and freshness."""
        seen_at = time.monotonic() if now is None else now
        self._prune(seen_at)
        added = 0
        for candidate in peers:
            peer = self._normalize(candidate, source)
            if peer is None:
                continue
            key = self._key(peer)
            actual_source = str(peer.get("peer_source", source) or source)
            record = self._records.get(key)
            if record is None:
                record = EndpointCandidate(
                    peer=peer,
                    first_seen=seen_at,
                    last_seen=seen_at,
                    sources={actual_source, source},
                )
                self._records[key] = record
                added += 1
            else:
                record.last_seen = seen_at
                record.sources.update({actual_source, source})
                record.peer.update(peer)
                if (
                    record.state == "accepted"
                    and record.accepted_at is not None
                    and seen_at - record.accepted_at >= self.accepted_refresh_seconds
                ):
                    record.state = "pending"
                    record.next_retry_at = seen_at
        self._prune(seen_at)
        return added

    def take_ready(
        self,
        *,
        limit: Optional[int] = None,
        now: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """Claim fresh candidates by value and freshness, never stale FIFO order."""
        claimed_at = time.monotonic() if now is None else now
        self._prune(claimed_at)
        ready = [
            record
            for record in self._records.values()
            if record.state == "pending" and record.next_retry_at <= claimed_at
        ]
        ready.sort(
            key=lambda record: (self._priority(record), record.last_seen),
            reverse=True,
        )
        if limit is not None:
            ready = ready[: max(0, limit)]
        result: list[dict[str, Any]] = []
        for record in ready:
            record.state = "attempting"
            record.attempts += 1
            record.last_attempt = claimed_at
            peer = dict(record.peer)
            peer["_candidate_first_seen"] = record.first_seen
            peer["_candidate_last_seen"] = record.last_seen
            peer["_candidate_sources"] = sorted(record.sources)
            peer["_candidate_attempts"] = record.attempts
            result.append(peer)
        return result

    def mark_accepted(
        self, peers: Iterable[Any], *, now: Optional[float] = None
    ) -> None:
        """Mark candidates complete only after downstream acceptance."""
        accepted_at = time.monotonic() if now is None else now
        for candidate in peers:
            peer = self._normalize(candidate, "unknown")
            if peer is None:
                continue
            record = self._records.get(self._key(peer))
            if record is not None:
                record.state = "accepted"
                record.accepted_at = accepted_at
                record.next_retry_at = 0.0

    def mark_retry(self, peers: Iterable[Any], *, now: Optional[float] = None) -> None:
        """Release failed delivery claims with bounded exponential retry delay."""
        failed_at = time.monotonic() if now is None else now
        for candidate in peers:
            peer = self._normalize(candidate, "unknown")
            if peer is None:
                continue
            record = self._records.get(self._key(peer))
            if record is None:
                continue
            delay = min(
                30.0,
                self.retry_base_seconds * (2 ** max(0, record.attempts - 1)),
            )
            record.state = "pending"
            record.next_retry_at = failed_at + delay

    def snapshot(self, *, now: Optional[float] = None) -> list[dict[str, Any]]:
        """Return fresh, non-accepted candidates without changing delivery state."""
        snapshot_at = time.monotonic() if now is None else now
        self._prune(snapshot_at)
        records = [
            record for record in self._records.values() if record.state != "accepted"
        ]
        records.sort(
            key=lambda record: (self._priority(record), record.last_seen),
            reverse=True,
        )
        return [dict(record.peer) for record in records]


class DiscoveryController:
    """Controller to orchestrate DHT/tracker/PEX peer discovery with dedup and scheduling."""

    def __init__(
        self, ctx: SessionContext, tasks: Optional[TaskSupervisor] = None
    ) -> None:
        """Initialize the discovery controller with session context and optional task supervisor."""
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()
        self._recent_lock = asyncio.Lock()
        self._candidates = EndpointCandidateStore()
        self._quality_filter_debug_log_cooldown_ms = 3000
        self._quality_filter_last_debug_log: float = 0.0

    def register_dht_callback(
        self,
        dht_client: DHTClientProtocol,
        on_peers_async: Callable[[list[tuple[str, int]]], Awaitable[Any]],
        *,
        info_hash: bytes,
    ) -> None:
        """Register a DHT callback that deduplicates and forwards to async handler."""

        async def retry_delivery(peers: list[tuple[str, int]]) -> None:
            for delay in (1.0, 2.0, 4.0, 8.0, 16.0):
                await asyncio.sleep(delay)
                try:
                    if await process_with_dedup(
                        peers,
                        schedule_retry=False,
                        observe_sighting=False,
                    ):
                        return
                except Exception:
                    logger = getattr(self._ctx, "logger", None)
                    if logger:
                        logger.debug(
                            "DHT candidate delivery retry failed; retaining candidate",
                            exc_info=True,
                        )
                    continue

        async def process_with_dedup(
            peers: list[tuple[str, int]],
            *,
            schedule_retry: bool = True,
            observe_sighting: bool = True,
        ) -> bool:
            if not peers:
                return True

            # Filter peers by quality before deduplication
            # Note: When peer count is very low, skip quality filtering to maximize connections
            filtered_peers = (
                await self._filter_peers_by_quality(peers)
                if observe_sighting
                else peers
            )

            # Note: If quality filtering removed too many peers and we have very few connections,
            # relax filtering or skip it entirely
            if len(filtered_peers) < len(peers) * 0.5:  # More than 50% filtered
                # Check current peer count - if very low, use all peers
                connected_peers = 0
                try:
                    if self._ctx.session_manager:
                        for session in self._ctx.session_manager.torrents.values():
                            if (
                                hasattr(session, "download_manager")
                                and session.download_manager
                                and hasattr(session.download_manager, "peer_manager")
                                and session.download_manager.peer_manager
                            ):
                                peer_manager = session.download_manager.peer_manager
                                if hasattr(peer_manager, "connections"):
                                    active_count = len(
                                        [
                                            c
                                            for c in peer_manager.connections.values()
                                            if hasattr(c, "is_active") and c.is_active()
                                        ]
                                    )
                                    connected_peers += active_count
                except Exception:
                    pass

                if connected_peers < 5:
                    # Very low peer count - use all peers, skip quality filtering
                    logger = getattr(self._ctx, "logger", None)
                    if logger:
                        logger.info(
                            "Quality filter removed %d/%d peers, but peer count is low (%d) - using all peers",
                            len(peers) - len(filtered_peers),
                            len(peers),
                            connected_peers,
                        )
                    filtered_peers = peers  # Use all peers when count is low

            async with self._recent_lock:
                if observe_sighting:
                    self._candidates.observe(filtered_peers, source="dht")
                ready = self._candidates.take_ready()
            new_peers = [(str(p["ip"]), int(p["port"])) for p in ready]

            if new_peers:
                logger = getattr(self._ctx, "logger", None)
                if logger:
                    logger.info(
                        "DHT discovery controller: processing %d new peer(s) (filtered: %d/%d, deduplicated: %d/%d)",
                        len(new_peers),
                        len(peers) - len(filtered_peers),
                        len(peers),
                        len(filtered_peers) - len(new_peers),
                        len(filtered_peers),
                    )
                try:
                    delivery = await on_peers_async(new_peers)
                except Exception:
                    async with self._recent_lock:
                        self._candidates.mark_retry(new_peers)
                    if schedule_retry:
                        self._tasks.create_task(
                            retry_delivery(new_peers),
                            name="dht_candidate_delivery_retry",
                        )
                    raise
                status = getattr(delivery, "status", None)
                accepted = delivery is not False and status not in {
                    "noop_empty",
                    "noop_shutdown",
                }
                async with self._recent_lock:
                    if accepted:
                        self._candidates.mark_accepted(new_peers)
                    else:
                        self._candidates.mark_retry(new_peers)
                if not accepted and schedule_retry:
                    self._tasks.create_task(
                        retry_delivery(new_peers),
                        name="dht_candidate_delivery_retry",
                    )
                return accepted
            logger = getattr(self._ctx, "logger", None)
            if logger:
                logger.debug(
                    "DHT discovery controller: no new peers after filtering/deduplication (input: %d, filtered: %d, deduplicated: %d)",
                    len(peers),
                    len(peers) - len(filtered_peers),
                    len(filtered_peers) - len(new_peers) if filtered_peers else 0,
                )
            return True

        def callback_wrapper(peers: list[tuple[str, int]]) -> None:
            """Create async task for peer processing from synchronous callback."""
            # Note: Add error handling for task creation and execution
            try:
                task = self._tasks.create_task(
                    process_with_dedup(peers), name="dht_peers_dedup"
                )

                # Note: Add done callback to log errors if task fails
                def task_done_callback(task: asyncio.Task) -> None:
                    """Handle task completion and log errors."""
                    try:
                        # Note: Check if task was cancelled before checking exception
                        # task.exception() raises CancelledError if task was cancelled
                        if task.cancelled():
                            # Task was cancelled (likely during shutdown) - don't log as error
                            from ccbt.utils.shutdown import is_shutting_down

                            if not is_shutting_down():
                                # Only log if not during shutdown (unexpected cancellation)
                                logger = getattr(self._ctx, "logger", None)
                                if logger:
                                    logger.debug(
                                        "DHT peer callback task cancelled for info_hash %s",
                                        info_hash.hex()[:16] + "...",
                                    )
                            return

                        # Check if task raised an exception (only if not cancelled)
                        if task.exception():
                            # Get logger from context if available
                            logger = getattr(self._ctx, "logger", None)
                            if logger:
                                from ccbt.utils.shutdown import is_shutting_down

                                if not is_shutting_down():
                                    # Only log errors if not during shutdown
                                    logger.error(
                                        "DHT peer callback task failed for info_hash %s: %s",
                                        info_hash.hex()[:16] + "...",
                                        task.exception(),
                                        exc_info=task.exception(),
                                    )
                            else:
                                # Fallback to print if no logger available (only if not shutdown)
                                from ccbt.utils.shutdown import is_shutting_down

                                if not is_shutting_down():
                                    pass
                    except Exception:
                        # If we can't log the error, at least print it (only if not shutdown)
                        from ccbt.utils.shutdown import is_shutting_down

                        if not is_shutting_down():
                            pass

                task.add_done_callback(task_done_callback)
            except Exception:
                # Log error if task creation fails
                logger = getattr(self._ctx, "logger", None)
                if logger:
                    logger.exception(
                        "Failed to create DHT peer callback task for info_hash %s",
                        info_hash.hex()[:16] + "...",
                    )
                else:
                    pass

        # Note: Pass info_hash to add_peer_callback to register callback per info_hash
        # This ensures callbacks are only invoked for the correct torrent
        # The callback wrapper already filters by info_hash via the discovery controller,
        # but registering with info_hash ensures better performance and correctness
        dht_client.add_peer_callback(callback_wrapper, info_hash=info_hash)

    async def _filter_peers_by_quality(
        self,
        peers: list[tuple[str, int]],
    ) -> list[tuple[str, int]]:
        """Filter peers by quality using SecurityManager reputation scores.

        Args:
            peers: List of (ip, port) tuples

        Returns:
            Filtered list of peers with acceptable quality

        """
        logger = getattr(self._ctx, "logger", None)
        # Get SecurityManager from session context
        security_manager = None
        if self._ctx.session_manager:
            security_manager = getattr(
                self._ctx.session_manager, "security_manager", None
            )

        # If no SecurityManager available, return all peers (no filtering)
        if not security_manager:
            return peers

        # Get quality threshold from config (default: 0.3, peers below this are filtered)
        base_quality_threshold = getattr(
            self._ctx.config.security
            if hasattr(self._ctx.config, "security")
            else None,
            "peer_quality_threshold",
            0.3,
        )

        # Relax quality filtering for new torrents (fewer than 5 connected peers)
        # This helps with initial peer discovery on popular torrents
        connected_peers = 0
        try:
            # Try to get connected peer count from session manager
            # Check if we can get peer count from any active torrent sessions
            # This is a best-effort check - if unavailable, use base threshold
            if self._ctx.session_manager and hasattr(
                self._ctx.session_manager, "torrents"
            ):
                for session in self._ctx.session_manager.torrents.values():
                    if (
                        hasattr(session, "download_manager")
                        and session.download_manager
                        and hasattr(session.download_manager, "peer_manager")
                        and session.download_manager.peer_manager
                    ):
                        peer_manager = session.download_manager.peer_manager
                        if hasattr(peer_manager, "connections"):
                            active_count = len(
                                [
                                    c
                                    for c in peer_manager.connections.values()
                                    if hasattr(c, "is_active") and c.is_active()
                                ]
                            )
                            connected_peers += active_count
        except Exception:
            # If we can't get peer count, use base threshold
            pass

        # RELAXED: Use very relaxed threshold to allow slower peers
        # Note: Ultra-relaxed threshold for ultra-low peer counts
        if connected_peers < 3:
            quality_threshold = (
                0.0  # No filtering for ultra-low peer count - accept all peers
            )
        elif connected_peers < 5:
            quality_threshold = (
                0.05  # Reduced from 0.1 to 0.05 - more permissive for initial discovery
            )
        elif connected_peers < 10:
            quality_threshold = (
                base_quality_threshold * 0.5
            )  # Half threshold for low peer counts
        else:
            quality_threshold = base_quality_threshold

        filtered_peers = []
        blacklisted_peers = 0
        low_score_peers = 0
        allowed_unknown = 0
        low_score_samples: list[tuple[str, int, float]] = []
        for ip, port in peers:
            # Generate peer_id from IP:port for reputation lookup
            # SecurityManager uses peer_id as key, but we can also check by IP
            peer_id = f"{ip}:{port}"

            # Try to get reputation by peer_id first
            reputation = security_manager.get_peer_reputation(peer_id, ip)

            if reputation:
                # Check if peer is blacklisted
                if reputation.is_blacklisted:
                    blacklisted_peers += 1
                    continue

                # Check reputation score
                if reputation.reputation_score < quality_threshold:
                    low_score_peers += 1
                    if len(low_score_samples) < 5:
                        low_score_samples.append(
                            (
                                ip,
                                port,
                                reputation.reputation_score,
                            )
                        )
                    continue

                # Peer passed quality filter
                filtered_peers.append((ip, port))
            else:
                # No reputation data - allow peer (new peer, give benefit of doubt)
                # But check if IP is in any blacklist
                # For now, allow unknown peers (they'll be evaluated after connection)
                allowed_unknown += 1
                filtered_peers.append((ip, port))

        filtered_count = len(filtered_peers)
        dropped_count = len(peers) - filtered_count
        if logger and dropped_count > 0:
            now_ms = time.time() * 1000
            info_hash = getattr(self._ctx, "info_hash", None)
            if isinstance(info_hash, (bytes, bytearray)):
                formatted_info_hash = bytes(info_hash).hex()[:16]
            else:
                formatted_info_hash = "unknown"
            if (
                now_ms - self._quality_filter_last_debug_log
                > self._quality_filter_debug_log_cooldown_ms
            ):
                self._quality_filter_last_debug_log = now_ms
                logger.debug(
                    "Quality filter removed %d/%d peers for info_hash=%s: blacklisted=%d, low_reputation=%d, threshold=%.3f, connected_peers=%d, accepted=%d (unknown=%d)",
                    dropped_count,
                    len(peers),
                    formatted_info_hash,
                    blacklisted_peers,
                    low_score_peers,
                    quality_threshold,
                    connected_peers,
                    filtered_count,
                    allowed_unknown,
                )
                if low_score_samples:
                    logger.debug(
                        "Quality filter low-reputation samples: %s",
                        ", ".join(
                            f"{ip}:{port}={score:.3f}"
                            for ip, port, score in low_score_samples
                        ),
                    )
                if blacklisted_peers > 0 and filtered_count == 0:
                    logger.warning(
                        "Quality filter dropped all discovered peers due to blacklist/score filtering. "
                        "Discovery fallback may be required."
                    )

        return filtered_peers
