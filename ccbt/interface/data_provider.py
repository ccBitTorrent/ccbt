"""Unified data provider interface for the tabbed interface.

Provides a consistent interface for accessing torrent data, metrics, and statistics
from either a daemon IPC connection or a local session manager.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import mimetypes
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from ccbt.daemon.ipc_client import IPCClient
    from ccbt.daemon.ipc_protocol import EventType
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.daemon.ipc_client import IPCClient
        from ccbt.daemon.ipc_protocol import EventType
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        IPCClient = None  # type: ignore[assignment, misc]
        AsyncSessionManager = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

_MEDIA_EXTENSIONS = {
    ".avi",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


def _compute_dht_health_score(metrics: dict[str, Any]) -> tuple[float, str]:
    """Compute a normalized DHT health score and label."""
    peers_score = min(1.0, float(metrics.get("peers_found_per_query", 0.0)) / 2.0)
    depth_score = min(1.0, float(metrics.get("query_depth_achieved", 0.0)) / 8.0)
    nodes_score = min(1.0, float(metrics.get("nodes_queried_per_query", 0.0)) / 20.0)
    health_score = max(0.0, min(1.0, (peers_score + depth_score + nodes_score) / 3.0))

    if health_score >= 0.75:
        label = "excellent"
    elif health_score >= 0.55:
        label = "healthy"
    elif health_score >= 0.35:
        label = "degraded"
    else:
        label = "critical"
    return health_score, label


def _empty_dht_summary() -> dict[str, Any]:
    """Return an empty DHT health summary payload."""
    return {
        "updated_at": time.time(),
        "overall_health": 0.0,
        "torrents_with_dht": 0,
        "aggressive_enabled": 0,
        "total_queries": 0,
        "total_bootstrap_recovery_attempts": 0,
        "total_bootstrap_zero_state_count": 0,
        "bootstrap_health_state": "unknown",
        "items": [],
        "all_items": [],
    }


def _aggregate_bootstrap_health_state(states: list[str]) -> str:
    """Normalize bootstrap health states to the worst known state."""
    if not states:
        return "unknown"
    for state in ("critical", "stalled", "degraded", "healthy", "excellent"):
        if state in states:
            return state
    return "unknown"


def _to_int(value: Any, default: int = 0) -> int:
    """Best-effort integer coercion for provider read models."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float coercion for provider read models."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _guess_media_metadata(path: str) -> tuple[Optional[str], bool]:
    """Return a best-effort MIME type and playable-media flag."""
    mime_type, _encoding = mimetypes.guess_type(path)
    is_media = bool(
        Path(path).suffix.lower() in _MEDIA_EXTENSIONS
        or (
            mime_type is not None
            and (mime_type.startswith("audio/") or mime_type.startswith("video/"))
        )
    )
    return mime_type, is_media


def _normalize_torrent_read_model(
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a torrent status payload into the canonical UI schema.

    Internal session status uses canonical keys such as `connected_peers` and
    `active_peers`. IPC transport uses `num_peers` and `num_seeds`, which are
    normalized to canonical names here.
    """
    connected_peers = _to_int(
        raw.get("connected_peers", raw.get("num_peers", raw.get("peers", 0))),
    )
    active_peers = _to_int(
        raw.get("active_peers", raw.get("num_seeds", raw.get("seeds", 0))),
    )
    info_hash_raw = raw.get("info_hash") or raw.get("info_hash_hex") or ""
    if isinstance(info_hash_raw, bytes):
        info_hash_str = info_hash_raw.hex()
    else:
        info_hash_str = str(info_hash_raw or "")
    normalized = {
        "info_hash": info_hash_str,
        "name": raw.get("name", "Unknown"),
        "status": raw.get("status", "unknown"),
        "progress": _to_float(raw.get("progress", 0.0)),
        "download_rate": _to_float(raw.get("download_rate", 0.0)),
        "upload_rate": _to_float(raw.get("upload_rate", 0.0)),
        "connected_peers": connected_peers,
        "active_peers": active_peers,
        "downloaded": _to_int(raw.get("downloaded", 0)),
        "uploaded": _to_int(raw.get("uploaded", 0)),
        "left": _to_int(raw.get("left", 0)),
        "total_size": _to_int(raw.get("total_size", 0)),
        "pieces_completed": _to_int(raw.get("pieces_completed", 0)),
        "pieces_total": _to_int(raw.get("pieces_total", 0)),
        "is_private": bool(raw.get("is_private", False)),
        "output_dir": raw.get("output_dir"),
        "tracker_status": raw.get("tracker_status"),
        "last_tracker_error": raw.get("last_tracker_error"),
        "last_error": raw.get("last_error"),
        "productive_peers": _to_int(raw.get("productive_peers", 0)),
        "requestable_peers": _to_int(raw.get("requestable_peers", 0)),
        "handshake_complete_peers": _to_int(raw.get("handshake_complete_peers", 0)),
        "extension_capable_peers": _to_int(raw.get("extension_capable_peers", 0)),
        "metadata_capable_peers": _to_int(raw.get("metadata_capable_peers", 0)),
        "hash_verification_failures": _to_int(
            raw.get("hash_verification_failures", 0)
        ),
        "uptime": _to_float(raw.get("uptime", 0.0)),
        "added_time": _to_float(raw.get("added_time", 0.0)),
        "download_complete": bool(
            raw.get("download_complete", raw.get("completed", False)),
        ),
    }
    return normalized


def _normalize_global_stats_read_model(
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Normalize global stats into the canonical UI schema."""
    download_rate = _to_float(
        raw.get("download_rate", raw.get("total_download_rate", 0.0)),
    )
    upload_rate = _to_float(
        raw.get("upload_rate", raw.get("total_upload_rate", 0.0)),
    )
    normalized = dict(raw)
    normalized.update(
        {
            "num_torrents": _to_int(raw.get("num_torrents", raw.get("total_torrents", 0))),
            "num_active": _to_int(raw.get("num_active", 0)),
            "num_paused": _to_int(raw.get("num_paused", 0)),
            "num_seeding": _to_int(raw.get("num_seeding", 0)),
            "download_rate": download_rate,
            "upload_rate": upload_rate,
            "average_progress": _to_float(raw.get("average_progress", 0.0)),
            "total_downloaded": _to_int(raw.get("total_downloaded", 0)),
            "total_uploaded": _to_int(raw.get("total_uploaded", 0)),
            "total_left": _to_int(raw.get("total_left", 0)),
            "connected_peers": _to_int(raw.get("connected_peers", raw.get("total_peers", 0))),
            "uptime": _to_float(raw.get("uptime", 0.0)),
        },
    )
    normalized.pop("total_download_rate", None)
    normalized.pop("total_upload_rate", None)
    return normalized


def _normalize_xet_folder_read_model(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize an XET runtime record into the canonical UI schema."""
    status = raw.get("status", {})
    if not isinstance(status, dict):
        status = {}
    normalized = dict(status)
    normalized.update(
        {
            "folder_key": raw.get("folder_key", normalized.get("folder_key")),
            "folder_path": raw.get("folder_path", normalized.get("folder_path", "")),
            "workspace_id": raw.get("workspace_id"),
            "sync_mode": raw.get("sync_mode", normalized.get("sync_mode", "best_effort")),
            "bootstrap_pending": bool(raw.get("bootstrap_pending", False)),
            "metadata_source": raw.get("metadata_source"),
            "started": bool(raw.get("started", False)),
            "connected_peers": _to_int(
                normalized.get("connected_peers", raw.get("connected_peers", 0))
            ),
            "synced_peers": _to_int(
                normalized.get("synced_peers", raw.get("synced_peers", 0))
            ),
            "pending_changes": _to_int(
                normalized.get("pending_changes", raw.get("pending_changes", 0))
            ),
            "sync_progress": _to_float(
                normalized.get("sync_progress", raw.get("sync_progress", 0.0))
            ),
            "is_syncing": bool(normalized.get("is_syncing", raw.get("is_syncing", False))),
            "current_git_ref": normalized.get(
                "current_git_ref",
                raw.get("git_ref"),
            ),
            "error": normalized.get("error", raw.get("error")),
        }
    )
    return normalized


def _normalize_peer_metric(peer: dict[str, Any]) -> dict[str, Any]:
    """Normalize peer metrics to dashboard-friendly canonical rate keys."""
    normalized = dict(peer)
    normalized["download_rate"] = _to_float(
        peer.get("download_rate", peer.get("total_download_rate", 0.0))
    )
    normalized["upload_rate"] = _to_float(
        peer.get("upload_rate", peer.get("total_upload_rate", 0.0))
    )
    normalized.pop("total_download_rate", None)
    normalized.pop("total_upload_rate", None)
    return normalized


def _build_aggressive_discovery_status(
    info_hash_hex: str,
    status: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    """Compute a local aggressive-discovery summary matching daemon reads."""
    peer_count = _to_int(status.get("connected_peers", 0))
    download_rate = _to_float(status.get("download_rate", 0.0))
    discovery_config = getattr(config, "discovery", None)
    popular_threshold = _to_int(
        getattr(discovery_config, "aggressive_discovery_popular_threshold", 20),
        20,
    )
    active_threshold_kib = _to_float(
        getattr(discovery_config, "aggressive_discovery_active_threshold_kib", 1.0),
        1.0,
    )
    active_threshold_bytes = active_threshold_kib * 1024.0
    is_popular = peer_count >= popular_threshold
    is_active = download_rate >= active_threshold_bytes
    enabled = is_popular or is_active
    reason = "popular" if is_popular else ("active" if is_active else "normal")
    query_interval = _to_float(
        getattr(
            discovery_config,
            "aggressive_discovery_interval_popular" if is_popular else "aggressive_discovery_interval_active",
            60.0,
        ),
        60.0,
    )
    return {
        "info_hash": info_hash_hex,
        "enabled": enabled,
        "reason": reason,
        "current_peer_count": peer_count,
        "current_download_rate_kib": download_rate / 1024.0,
        "popular_threshold": popular_threshold,
        "active_threshold_kib": active_threshold_kib,
        "query_interval": query_interval,
    }


class DataProvider(ABC):
    """Abstract base class for data providers.

    Provides a unified interface for accessing torrent and metrics data
    regardless of whether the data comes from a daemon IPC or local session.
    """

    @abstractmethod
    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with global statistics including:
            - num_torrents, num_active, num_paused, num_seeding
            - download_rate, upload_rate
            - total_downloaded, total_uploaded
            - connected_peers, uptime
        """

    @abstractmethod
    async def get_torrent_status(self, info_hash_hex: str) -> Optional[dict[str, Any]]:
        """Get status for a specific torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            Dictionary with torrent status or None if not found
        """

    @abstractmethod
    async def get_aggressive_discovery_status(
        self,
        info_hash_hex: str,
    ) -> dict[str, Any]:
        """Get DHT aggressive discovery status for a specific torrent."""

    @abstractmethod
    async def list_torrents(self) -> list[dict[str, Any]]:
        """List all torrents.

        Returns:
            List of torrent status dictionaries
        """

    @abstractmethod
    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all active XET workspaces using the canonical runtime read model."""

    @abstractmethod
    async def get_xet_folder_status(self, folder_key: str) -> Optional[dict[str, Any]]:
        """Get the live status snapshot for a specific XET workspace."""

    @abstractmethod
    async def get_xet_discovery_status(self) -> dict[str, Any]:
        """Get shared XET discovery backend status."""

    @abstractmethod
    async def get_torrent_peers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get peers for a specific torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            List of peer dictionaries
        """

    @abstractmethod
    async def get_torrent_files(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get files for a specific torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            List of file dictionaries
        """

    @abstractmethod
    async def get_media_stream_status(
        self,
        info_hash_hex: str,
    ) -> Optional[dict[str, Any]]:
        """Get media stream status for a torrent if one is active."""

    @abstractmethod
    async def get_media_candidates(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return playable media candidates for the torrent."""

    @abstractmethod
    async def get_torrent_trackers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get trackers for a specific torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            List of tracker dictionaries with keys:
            - url: Tracker URL
            - status: Status string ("working", "error", "updating")
            - seeds: Number of seeds from last scrape
            - peers: Number of peers from last scrape
            - downloaders: Number of downloaders from last scrape
            - last_update: Last update timestamp (float)
            - error: Error message if any (Optional[str])
        """

    @abstractmethod
    async def get_torrent_piece_availability(self, info_hash_hex: str) -> list[int]:
        """Get piece availability array for a torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            List of integers representing how many peers have each piece.
            Index corresponds to piece index, value is peer count (0 = not available).
            Empty list if not available or torrent not found.
        """

    @abstractmethod
    async def get_peer_metrics(self) -> dict[str, Any]:
        """Get global peer metrics across all torrents.

        Returns:
            Dictionary with:
            - total_peers: Total number of unique peers
            - active_peers: Number of active peers
            - peers: List of peer metrics dictionaries
        """

    @abstractmethod
    async def get_dht_health_summary(self, limit: int = 8) -> dict[str, Any]:
        """Get aggregated DHT discovery health metrics.

        Args:
            limit: Number of torrents to include in the summarized items list.

        Returns:
            Dictionary containing:
                - updated_at: Timestamp of summary generation
                - overall_health: Average health score (0.0-1.0)
                - torrents_with_dht: Count of torrents with DHT metrics
                - aggressive_enabled: Count of torrents with aggressive mode enabled
                - total_queries: Total DHT queries observed
                - items: List of worst-performing torrents (length <= limit)
                - all_items: Full list of torrents with DHT metrics
        """

    @abstractmethod
    async def get_peer_quality_distribution(self) -> dict[str, Any]:
        """Get aggregated peer quality distribution across all torrents.
        
        Returns:
            Dictionary with:
            - total_peers: Total number of unique peers across all torrents
            - quality_tiers: Distribution by quality tier (excellent/good/fair/poor)
            - average_quality: Average quality score across all peers
            - top_peers: Top 10 highest quality peers with details
            - per_torrent: List of per-torrent quality summaries
        """

    @abstractmethod
    async def get_global_kpis(self) -> dict[str, Any]:
        """Get global Key Performance Indicators (KPIs) across all torrents.
        
        Returns:
            Dictionary with global KPIs including:
            - total_peers: Total number of unique peers
            - average_download_rate: Average download rate across all peers
            - average_upload_rate: Average upload rate across all peers
            - total_bytes_downloaded: Total bytes downloaded
            - total_bytes_uploaded: Total bytes uploaded
            - shared_peers_count: Number of peers shared across multiple torrents
            - cross_torrent_sharing: Cross-torrent sharing efficiency (0.0-1.0)
            - overall_efficiency: Overall system efficiency (0.0-1.0)
            - bandwidth_utilization: Bandwidth utilization (0.0-1.0)
            - connection_efficiency: Connection efficiency (0.0-1.0)
            - resource_utilization: Resource utilization (0.0-1.0)
            - peer_efficiency: Peer efficiency (0.0-1.0)
            - cpu_usage: CPU usage (0.0-1.0)
            - memory_usage: Memory usage (0.0-1.0)
            - disk_usage: Disk usage (0.0-1.0)
        """

    @abstractmethod
    async def get_metrics(self) -> dict[str, Any]:
        """Get metrics from metrics collector.

        Returns:
            Dictionary with metrics data
        """

    @abstractmethod
    async def get_rate_samples(self, seconds: int = 120) -> list[dict[str, Any]]:
        """Get recent upload/download rate samples for graphing."""

    @abstractmethod
    async def get_disk_io_metrics(self) -> dict[str, Any]:
        """Get disk I/O metrics for graph series.

        Returns:
            Dictionary with disk I/O metrics:
            - read_throughput: Read throughput in KiB/s
            - write_throughput: Write throughput in KiB/s
            - cache_hit_rate: Cache hit rate as percentage (0-100)
            - timing_ms: Average disk operation timing in milliseconds
        """

    @abstractmethod
    async def get_network_timing_metrics(self) -> dict[str, Any]:
        """Get network timing metrics for graph series.

        Returns:
            Dictionary with network timing metrics:
            - utp_delay_ms: Average uTP delay in milliseconds
            - network_overhead_rate: Network overhead rate in KiB/s
        """

    @abstractmethod
    async def get_system_metrics(self) -> dict[str, Any]:
        """Get system metrics (CPU, memory, disk) for graph series.

        Returns:
            Dictionary with system metrics:
            - cpu_usage: CPU usage as percentage (0-100)
            - memory_usage: Memory usage as percentage (0-100)
            - disk_usage: Disk usage as percentage (0-100)
        """

    @abstractmethod
    async def get_per_torrent_performance(self, info_hash_hex: str) -> dict[str, Any]:
        """Get per-torrent performance metrics.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            Dictionary with per-torrent performance metrics including:
            - download_rate, upload_rate, progress
            - pieces_completed, pieces_total
            - connected_peers, active_peers
            - top_peers (list of peer performance metrics)
            - piece_download_rate, swarm_availability
        """

    async def get_swarm_health_samples(
        self,
        info_hash_hex: Optional[str] = None,
        limit: int = 6,
        include_history: bool = False,
        history_seconds: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get swarm health samples for global or per-torrent views.
        
        Args:
            info_hash_hex: Optional torrent info hash for per-torrent view
            limit: Maximum number of torrents to return
            include_history: If True, include historical samples and pattern metadata
            history_seconds: Optional history window (defaults to 120s when not provided)
            
        Returns:
            List of swarm health samples with optional history and glyph metadata
        """
        import itertools

        limit = max(1, limit)
        history_window = history_seconds if history_seconds and history_seconds > 0 else 120
        history_window = max(30, history_window)
        if info_hash_hex:
            metrics = await self.get_per_torrent_performance(info_hash_hex)
            if not metrics:
                return []
            name = metrics.get("name") or info_hash_hex[:16]
            sample = {
                "info_hash": info_hash_hex,
                "name": name,
                "swarm_availability": float(metrics.get("swarm_availability", 0.0)),
                "download_rate": float(metrics.get("download_rate", 0.0)),
                "upload_rate": float(metrics.get("upload_rate", 0.0)),
                "connected_peers": int(metrics.get("connected_peers", 0)),
                "active_peers": int(metrics.get("active_peers", 0)),
            }
            if include_history:
                # Try to get historical samples from matrix endpoint
                if hasattr(self, "_client") and hasattr(self._client, "get_swarm_health_matrix"):
                    try:
                        matrix = await self._client.get_swarm_health_matrix(limit=limit, seconds=history_window)
                        torrent_samples = [
                            s for s in matrix.samples if s.info_hash == info_hash_hex
                        ]
                        if torrent_samples:
                            torrent_samples.sort(key=lambda s: s.timestamp)
                            sample["history"] = [
                                {
                                    "timestamp": s.timestamp,
                                    "swarm_availability": float(s.swarm_availability),
                                    "download_rate": float(s.download_rate),
                                    "upload_rate": float(s.upload_rate),
                                    "connected_peers": int(s.connected_peers),
                                    "active_peers": int(s.active_peers),
                                    "progress": float(s.progress),
                                }
                                for s in torrent_samples
                            ]
                            if len(torrent_samples) >= 2:
                                recent = torrent_samples[-1].swarm_availability
                                previous = torrent_samples[0].swarm_availability
                                if recent > previous:
                                    sample["trend"] = "improving"
                                elif recent < previous:
                                    sample["trend"] = "degrading"
                                else:
                                    sample["trend"] = "stable"
                                sample["trend_delta"] = recent - previous
                            if matrix.rarity_percentiles:
                                sample["rarity_percentiles"] = matrix.rarity_percentiles
                    except Exception as e:
                        logger.debug("Error fetching swarm health matrix: %s", e)
            return [sample]

        # Global view - try matrix endpoint first
        if include_history and hasattr(self, "_client") and hasattr(self._client, "get_swarm_health_matrix"):
            try:
                matrix = await self._client.get_swarm_health_matrix(limit=limit, seconds=history_window)
                grouped_samples: dict[str, list[Any]] = {}
                for sample in matrix.samples:
                    grouped_samples.setdefault(sample.info_hash, []).append(sample)
                # Sort torrents by most recent download rate to keep top performers
                sorted_groups = sorted(
                    grouped_samples.items(),
                    key=lambda item: item[1][-1].download_rate if item[1] else 0.0,
                    reverse=True,
                )
                samples: list[dict[str, Any]] = []
                for info_hash, torrent_samples in itertools.islice(sorted_groups, limit):
                    if not torrent_samples:
                        continue
                    torrent_samples.sort(key=lambda s: s.timestamp)
                    latest = torrent_samples[-1]
                    sample_dict: dict[str, Any] = {
                        "info_hash": info_hash,
                        "name": latest.name,
                        "swarm_availability": float(latest.swarm_availability),
                        "download_rate": float(latest.download_rate),
                        "upload_rate": float(latest.upload_rate),
                        "connected_peers": int(latest.connected_peers),
                        "active_peers": int(latest.active_peers),
                        "progress": float(latest.progress),
                        "timestamp": float(latest.timestamp),
                    }
                    sample_dict["history"] = [
                        {
                            "timestamp": s.timestamp,
                            "swarm_availability": float(s.swarm_availability),
                            "download_rate": float(s.download_rate),
                            "upload_rate": float(s.upload_rate),
                            "connected_peers": int(s.connected_peers),
                            "active_peers": int(s.active_peers),
                            "progress": float(s.progress),
                        }
                        for s in torrent_samples
                    ]
                    if len(torrent_samples) >= 2:
                        first = torrent_samples[0].swarm_availability
                        recent = torrent_samples[-1].swarm_availability
                        if recent > first:
                            sample_dict["trend"] = "improving"
                        elif recent < first:
                            sample_dict["trend"] = "degrading"
                        else:
                            sample_dict["trend"] = "stable"
                        sample_dict["trend_delta"] = recent - first
                    if matrix.rarity_percentiles:
                        sample_dict["rarity_percentiles"] = matrix.rarity_percentiles
                    samples.append(sample_dict)
                if samples:
                    return samples
            except Exception as e:
                logger.debug("Error fetching swarm health matrix, falling back to individual queries: %s", e)

        # Fallback to individual queries
        torrents = await self.list_torrents()
        if not torrents:
            return []

        top = sorted(
            torrents,
            key=lambda t: float(t.get("download_rate", 0.0)),
            reverse=True,
        )[:limit]
        samples: list[dict[str, Any]] = []
        for torrent in top:
            info_hash = torrent.get("info_hash")
            if not info_hash:
                continue
            perf = await self.get_per_torrent_performance(info_hash)
            if not perf:
                continue
            samples.append(
                {
                    "info_hash": info_hash,
                    "name": torrent.get("name") or info_hash[:16],
                    "swarm_availability": float(perf.get("swarm_availability", 0.0)),
                    "download_rate": float(perf.get("download_rate", 0.0)),
                    "upload_rate": float(perf.get("upload_rate", 0.0)),
                    "connected_peers": int(perf.get("connected_peers", 0)),
                    "active_peers": int(perf.get("active_peers", 0)),
                }
            )
        return samples

    @abstractmethod
    async def get_piece_health(self, info_hash_hex: str) -> dict[str, Any]:
        """Get piece availability and selection metrics for pictogram rendering."""

    @abstractmethod
    async def get_scrape_result(self, info_hash_hex: str) -> Optional[Any]:
        """Get cached scrape result (seeders/leechers/completed) for a torrent."""


class DaemonDataProvider(DataProvider):
    """Data provider for daemon IPC connection.
    
    CRITICAL: This is the ONLY way the interface should access the daemon.
    All daemon access MUST go through:
    1. IPC client (_client) for read operations
    2. Executor (_executor) for command execution
    
    Never access daemon session internals directly.
    """

    def __init__(self, ipc_client: IPCClient, executor: Optional[Any] = None, adapter: Optional[Any] = None) -> None:
        """Initialize daemon data provider.

        Args:
            ipc_client: IPC client instance
            executor: Optional executor instance for command execution
            adapter: Optional DaemonInterfaceAdapter instance for widget registration
        """
        self._client = ipc_client
        self._executor = executor
        self._adapter = adapter  # Store adapter for widget registration
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 1.0  # 1.0 second TTL - balanced for responsiveness and reduced redundant requests
        self._cache_lock = asyncio.Lock()
        self._cache_inflight: dict[str, asyncio.Task[Any]] = {}
        self._cache_invalidation_keys: set[str] = set()
        self._cache_invalidate_all: bool = False
        self._cache_invalidation_task: Optional[asyncio.Task[None]] = None

    def get_adapter(self) -> Optional[Any]:
        """Get the DaemonInterfaceAdapter instance for widget registration.
        
        Returns:
            DaemonInterfaceAdapter instance or None if not available
        """
        return self._adapter

    async def _get_cached(
        self, key: str, fetch_func: Any, ttl: Optional[float] = None
    ) -> Any:  # pragma: no cover
        """Get cached value or fetch if expired.

        Coalesces concurrent fetches for the same key and never holds the cache
        lock across IPC/network I/O (avoids blocking all provider reads).
        """
        if ttl is None:
            ttl = self._cache_ttl
        now = time.time()
        inflight: Optional[asyncio.Task[Any]] = None
        async with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                age = now - timestamp
                if ttl > 0 and age < ttl:
                    logger.debug(
                        "Cache hit for key=%s (age=%.3fs, ttl=%.3fs)",
                        key,
                        age,
                        ttl,
                    )
                    return value
            inflight = self._cache_inflight.get(key)

        if inflight is not None:
            return await inflight

        async def _run_fetch() -> Any:
            logger.debug("Fetching fresh value for cache key=%s", key)
            value = await fetch_func()
            async with self._cache_lock:
                self._cache[key] = (value, time.time())
                self._cache_inflight.pop(key, None)
            logger.debug("Cache updated for key=%s", key)
            return value

        task = asyncio.create_task(_run_fetch())
        async with self._cache_lock:
            existing = self._cache_inflight.get(key)
            if existing is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                return await existing
            self._cache_inflight[key] = task
        try:
            return await task
        except Exception:
            async with self._cache_lock:
                if self._cache_inflight.get(key) is task:
                    self._cache_inflight.pop(key, None)
            raise

    def seed_cache(
        self,
        key: str,
        value: Any,
        *,
        ttl: Optional[float] = None,
    ) -> None:
        """Pre-populate cache (e.g. rate samples from ui/snapshot)."""
        if ttl is None:
            ttl = self._cache_ttl
        self._cache[key] = (value, time.time())
        logger.debug("Cache seeded for key=%s (ttl=%.3fs)", key, ttl or 0.0)

    async def _flush_cache_invalidations(self) -> None:
        """Flush queued cache invalidations under a single lock."""
        try:
            while True:
                async with self._cache_lock:
                    if self._cache_invalidate_all:
                        self._cache_invalidate_all = False
                        self._cache_invalidation_keys.clear()
                        self._cache.clear()
                        logger.debug("Cache flush cleared all cache entries")
                        continue
                    if not self._cache_invalidation_keys:
                        break
                    keys_to_clear = set(self._cache_invalidation_keys)
                    self._cache_invalidation_keys.clear()
                for cache_key in keys_to_clear:
                    self._cache.pop(cache_key, None)
                    logger.debug("Cache key cleared: %s", cache_key)
            return
        finally:
            self._cache_invalidation_task = None

    def invalidate_cache(self, key: Optional[str] = None) -> None:  # pragma: no cover
        """Invalidate cache entry or all cache if key is None.

        Args:
            key: Cache key to invalidate, or None to invalidate all cache
        """
        # Aggregate invalidation requests so event bursts serialize predictably.
        if key is None:
            self._cache_invalidate_all = True
            self._cache_invalidation_keys.clear()
        else:
            self._cache_invalidation_keys.add(key)

        # Run in background if event loop is running.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if (
                    self._cache_invalidation_task is None
                    or self._cache_invalidation_task.done()
                ):
                    self._cache_invalidation_task = asyncio.create_task(
                        self._flush_cache_invalidations(),
                    )
            elif key is None:
                self._cache.clear()
            elif key in self._cache:
                self._cache.pop(key, None)
        except Exception:
            # If no event loop, just clear synchronously (not ideal but safe)
            if key is None:
                self._cache.clear()
            elif key in self._cache:
                del self._cache[key]

    @staticmethod
    def _normalize_event_type(
        event_type: Union[EventType, str],
    ) -> Optional[EventType]:
        """Normalize event type input from enum or string payloads."""
        if isinstance(event_type, EventType):
            return event_type
        if not isinstance(event_type, str):
            return None
        try:
            return EventType(event_type)
        except ValueError:
            event_type_name = event_type.upper()
            if event_type_name in EventType.__members__:
                return EventType[event_type_name]
        logger.debug("Unknown event type encountered in cache invalidation: %s", event_type)
        return None

    def invalidate_on_event(
        self, event_type: Union[EventType, str], info_hash: Optional[str] = None
    ) -> None:
        """Invalidate cache based on event type.
        
        Args:
            event_type: Event type (e.g., "PROGRESS_UPDATED", "PIECE_COMPLETED")
            info_hash: Optional torrent info hash for targeted invalidation
        """
        normalized_event_type = self._normalize_event_type(event_type)
        if normalized_event_type is None:
            return

        # Map event types to cache keys
        if normalized_event_type == EventType.PROGRESS_UPDATED:
            # Progress events - invalidate progress-related caches
            self.invalidate_cache("global_stats")  # Contains average progress
            self.invalidate_cache("swarm_health")  # May contain progress data
            if info_hash:
                self.invalidate_cache(f"torrent_status_{info_hash}")  # Contains progress
                self.invalidate_cache(f"per_torrent_performance_{info_hash}")  # Contains progress
                self.invalidate_cache(f"piece_health_{info_hash}")  # May be affected by progress
        elif normalized_event_type == EventType.GLOBAL_STATS_UPDATED:
            # Global stats updated - invalidate global stats and swarm health
            self.invalidate_cache("global_stats")
            self.invalidate_cache("swarm_health")
            if info_hash:
                self.invalidate_cache(f"per_torrent_performance_{info_hash}")
                self.invalidate_cache(f"piece_health_{info_hash}")
        elif normalized_event_type in (
            EventType.PIECE_REQUESTED,
            EventType.PIECE_DOWNLOADED,
            EventType.PIECE_VERIFIED,
            EventType.PIECE_COMPLETED,
        ):
            # All piece events - invalidate piece-related caches
            if info_hash:
                self.invalidate_cache(f"piece_health_{info_hash}")
                self.invalidate_cache(f"per_torrent_performance_{info_hash}")  # Contains piece counts
                # PIECE_COMPLETED also affects torrent status (piece counts)
                if normalized_event_type == EventType.PIECE_COMPLETED:
                    self.invalidate_cache(f"torrent_status_{info_hash}")
        elif normalized_event_type in (
            EventType.TORRENT_STATUS_CHANGED,
            EventType.TORRENT_ADDED,
            EventType.TORRENT_REMOVED,
            EventType.SEEDING_STARTED,
            EventType.SEEDING_STOPPED,
            EventType.SEEDING_STATS_UPDATED,
        ):
            # Invalidate torrent list and related caches
            self.invalidate_cache("torrent_list")
            self.invalidate_cache("swarm_health")
            if info_hash:
                self.invalidate_cache(f"per_torrent_performance_{info_hash}")
                self.invalidate_cache(f"piece_health_{info_hash}")
                self.invalidate_cache(f"torrent_status_{info_hash}")
                self.invalidate_cache(f"torrent_files_{info_hash}")
                self.invalidate_cache(f"trackers_{info_hash}")
        elif normalized_event_type in (
            EventType.TRACKER_ANNOUNCE_STARTED,
            EventType.TRACKER_ANNOUNCE_SUCCESS,
            EventType.TRACKER_ANNOUNCE_ERROR,
        ):
            if info_hash:
                self.invalidate_cache(f"trackers_{info_hash}")
                self.invalidate_cache(f"torrent_status_{info_hash}")
                self.invalidate_cache(f"per_torrent_performance_{info_hash}")
                self.invalidate_cache(f"torrent_files_{info_hash}")
        elif normalized_event_type in (
            EventType.METADATA_READY,
            EventType.METADATA_FETCH_STARTED,
            EventType.METADATA_FETCH_PROGRESS,
            EventType.METADATA_FETCH_COMPLETED,
            EventType.METADATA_FETCH_FAILED,
            EventType.FILE_SELECTION_CHANGED,
            EventType.FILE_PRIORITY_CHANGED,
        ):
            if info_hash:
                self.invalidate_cache(f"torrent_files_{info_hash}")
                self.invalidate_cache(f"torrent_status_{info_hash}")
                self.invalidate_cache(f"piece_health_{info_hash}")
        elif normalized_event_type in (
            EventType.XET_FOLDER_ADDED,
            EventType.XET_FOLDER_REMOVED,
            EventType.XET_FOLDER_CHANGED,
            EventType.XET_SYNC_PROGRESS,
            EventType.XET_SYNC_ERROR,
            EventType.XET_METADATA_READY,
        ):
            self.invalidate_cache("xet_folders")
            if info_hash:
                self.invalidate_cache(f"xet_folder_status_{info_hash}")
            self.invalidate_cache("global_stats")
        elif normalized_event_type in (
            EventType.MEDIA_STREAM_STARTED,
            EventType.MEDIA_STREAM_BUFFERING,
            EventType.MEDIA_STREAM_READY,
            EventType.MEDIA_STREAM_STOPPED,
            EventType.MEDIA_STREAM_ERROR,
        ):
            if info_hash:
                self.invalidate_cache(f"media_status_{info_hash}")
                self.invalidate_cache(f"torrent_status_{info_hash}")
                self.invalidate_cache(f"torrent_files_{info_hash}")
        # Broad caches often affected by event bursts
        self.invalidate_cache("metrics")
        self.invalidate_cache("global_kpis")
        self.invalidate_cache("peer_metrics")

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics from daemon."""
        async def _fetch() -> dict[str, Any]:
            stats_response = await self._client.get_global_stats()
            stats = dict(stats_response.stats or {})
            stats.update(
                {
                    "num_torrents": stats_response.num_torrents,
                    "num_active": stats_response.num_active,
                    "num_paused": stats_response.num_paused,
                    "download_rate": stats_response.total_download_rate,
                    "upload_rate": stats_response.total_upload_rate,
                    "total_downloaded": stats_response.total_downloaded,
                    "total_uploaded": stats_response.total_uploaded,
                },
            )
            return _normalize_global_stats_read_model(stats)
        return await self._get_cached("global_stats", _fetch)

    async def get_ui_snapshot(self) -> dict[str, Any]:
        """Get dashboard first-paint snapshot (global stats, torrents, services, rate samples, peers) from daemon."""
        async def _fetch() -> dict[str, Any]:
            response = await self._client.get_ui_snapshot()
            out = response.model_dump()
            # Normalize global_stats for UI schema
            if out.get("global_stats"):
                out["global_stats"] = _normalize_global_stats_read_model(
                    out["global_stats"],
                )
            # Normalize each torrent for UI schema
            if out.get("torrents"):
                out["torrents"] = [
                    _normalize_torrent_read_model(t) for t in out["torrents"]
                ]
            return out
        return await self._get_cached("ui_snapshot", _fetch, ttl=0.5)

    async def get_torrent_status(self, info_hash_hex: str) -> Optional[dict[str, Any]]:
        """Get torrent status from daemon."""
        try:
            status = await self._client.get_torrent_status(info_hash_hex)
            if not status:
                return None
            return _normalize_torrent_read_model(status.model_dump())
        except Exception as e:
            logger.debug("Error getting torrent status: %s", e)
            return None

    async def get_aggressive_discovery_status(
        self,
        info_hash_hex: str,
    ) -> dict[str, Any]:
        """Get DHT aggressive discovery status from daemon."""
        cache_key = f"aggressive_discovery_status_{info_hash_hex}"

        async def _fetch() -> dict[str, Any]:
            try:
                response = await self._client.get_aggressive_discovery_status(info_hash_hex)
                return response.model_dump()
            except Exception as e:
                logger.debug("Error getting aggressive discovery status: %s", e)
                return {}

        return await self._get_cached(cache_key, _fetch, ttl=1.0)

    async def list_torrents(self) -> list[dict[str, Any]]:
        """List all torrents from daemon."""
        async def _fetch() -> list[dict[str, Any]]:
            logger.debug("DaemonDataProvider.list_torrents: Fetching torrent list from IPC client...")
            try:
                torrent_list = await self._client.list_torrents()
                logger.debug("DaemonDataProvider.list_torrents: Received %d torrent(s) from IPC client", len(torrent_list) if torrent_list else 0)
                result = [
                    _normalize_torrent_read_model(t.model_dump())
                    for t in torrent_list
                ]
                logger.debug("DaemonDataProvider.list_torrents: Converted to %d dict(s)", len(result))
                return result
            except Exception as e:
                logger.error("DaemonDataProvider.list_torrents: Error fetching torrent list from IPC client: %s", e, exc_info=True)
                raise
        try:
            result = await self._get_cached("torrent_list", _fetch, ttl=0.5)  # Increased from 0.2s to 0.5s for better balance
            logger.debug("DaemonDataProvider.list_torrents: Returning %d torrent(s) (from cache or fresh fetch)", len(result) if result else 0)
            return result
        except Exception as e:
            logger.error("DaemonDataProvider.list_torrents: Error in list_torrents: %s", e, exc_info=True)
            raise

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List active XET workspaces from the daemon runtime."""
        async def _fetch() -> list[dict[str, Any]]:
            result = await self.execute_command("xet.list_xet_folders")
            if hasattr(result, "success"):
                if not result.success:
                    return []
                folders = result.data.get("folders", []) if isinstance(result.data, dict) else []
            else:
                success, _message, data = result
                if not success:
                    return []
                folders = data.get("folders", []) if isinstance(data, dict) else []
            return [
                _normalize_xet_folder_read_model(folder)
                for folder in folders
                if isinstance(folder, dict)
            ]

        return await self._get_cached("xet_folders", _fetch, ttl=0.5)

    async def get_xet_folder_status(self, folder_key: str) -> Optional[dict[str, Any]]:
        """Get a single XET workspace status from the daemon runtime."""
        cache_key = f"xet_folder_status_{folder_key}"

        async def _fetch() -> Optional[dict[str, Any]]:
            result = await self.execute_command(
                "xet.get_xet_folder_status",
                folder_key=folder_key,
            )
            if hasattr(result, "success"):
                if not result.success:
                    return None
                payload = result.data.get("status") if isinstance(result.data, dict) else None
            else:
                success, _message, data = result
                if not success:
                    return None
                payload = data.get("status") if isinstance(data, dict) else None
            if not isinstance(payload, dict):
                return None
            return _normalize_xet_folder_read_model(
                {"folder_key": folder_key, "status": payload}
            )

        return await self._get_cached(cache_key, _fetch, ttl=0.5)

    async def get_xet_discovery_status(self) -> dict[str, Any]:
        """Get shared XET discovery backend status from daemon runtime."""
        async def _fetch() -> dict[str, Any]:
            result = await self.execute_command("xet.get_xet_discovery_status")
            if hasattr(result, "success"):
                if not result.success:
                    return {}
                payload = (
                    result.data.get("backends")
                    if isinstance(result.data, dict)
                    else None
                )
            else:
                success, _message, data = result
                if not success:
                    return {}
                payload = data.get("backends") if isinstance(data, dict) else None
            return payload if isinstance(payload, dict) else {}

        return await self._get_cached("xet_discovery_status", _fetch, ttl=0.5)

    async def get_torrent_peers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get peers for a torrent from daemon."""
        try:
            peer_list = await self._client.get_torrent_peers(info_hash_hex)
            return [
                {
                    "ip": p.ip,
                    "port": p.port,
                    "download_rate": p.download_rate,
                    "upload_rate": p.upload_rate,
                    "choked": p.choked,
                    "client": p.client,
                    # Keep parity with local provider schema
                    "uploaded": 0,
                    "downloaded": 0,
                    "left": 0,
                    "state": "unknown",
                }
                for p in peer_list.peers
            ]
        except Exception as e:
            logger.debug("Error getting torrent peers: %s", e)
            return []

    async def get_torrent_files(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get files for a torrent from daemon."""
        async def _fetch() -> list[dict[str, Any]]:
            try:
                file_list = await self._client.get_torrent_files(info_hash_hex)
                return [
                    {
                        "index": f.index,
                        "name": f.name,
                        "size": f.size,
                        "selected": f.selected,
                        "priority": f.priority,
                        "progress": f.progress,
                        "attributes": f.attributes,
                        "path": f.path,
                        "mime_type": f.mime_type,
                        "is_media": f.is_media,
                    }
                    for f in file_list.files
                ]
            except Exception as e:
                logger.debug("Error getting torrent files: %s", e)
                return []

        # Cache file list responses briefly to avoid hammering the daemon endpoint
        cache_key = f"torrent_files_{info_hash_hex}"
        return await self._get_cached(cache_key, _fetch, ttl=2.0)

    async def get_media_stream_status(
        self,
        info_hash_hex: str,
    ) -> Optional[dict[str, Any]]:
        """Get media stream status from daemon."""

        async def _fetch() -> Optional[dict[str, Any]]:
            try:
                status = await self._client.get_media_stream_status(info_hash=info_hash_hex)
                return status.model_dump() if status is not None else None
            except Exception as e:
                logger.debug("Error getting media stream status: %s", e)
                return None

        return await self._get_cached(f"media_status_{info_hash_hex}", _fetch, ttl=1.0)

    async def get_media_candidates(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return playable media candidates for a torrent."""
        files = await self.get_torrent_files(info_hash_hex)
        return [file_info for file_info in files if file_info.get("is_media")]

    async def get_torrent_trackers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get trackers for a torrent from daemon."""
        async def _fetch() -> list[dict[str, Any]]:
            try:
                # Use IPC client to get trackers
                tracker_list = await self._client.get_torrent_trackers(info_hash_hex)
                return [
                    {
                        "url": t.url,
                        "status": t.status,
                        "tracker_status": t.status,
                        "seeds": t.seeds,
                        "peers": t.peers,
                        "downloaders": t.downloaders,
                        "last_update": t.last_update,
                        "last_announce": t.last_update,
                        "interval": 0,
                        "failure_count": 0,
                        "backoff_delay": 0.0,
                        "error": t.error,
                    }
                    for t in tracker_list.trackers
                ]
            except Exception as e:
                logger.debug("Error getting torrent trackers: %s", e)
                return []

        # Cache with 3 second TTL
        return await self._get_cached(f"trackers_{info_hash_hex}", _fetch, ttl=3.0)

    async def get_metrics(self) -> dict[str, Any]:
        """Get metrics from daemon metrics endpoint."""
        async def _fetch() -> dict[str, Any]:
            try:
                # Fetch Prometheus metrics
                prometheus_text = await self._client.get_metrics()
                # Parse Prometheus format into structured dict
                return self._parse_prometheus_metrics(prometheus_text)
            except Exception as e:
                logger.debug("Error fetching metrics: %s", e)
                return {}

        # Cache with 5 second TTL
        return await self._get_cached("metrics", _fetch, ttl=5.0)

    async def get_rate_samples(self, seconds: int = 120) -> list[dict[str, Any]]:
        """Get recent upload/download rate samples from daemon."""
        async def _fetch() -> list[dict[str, Any]]:
            max_retries = 2  # Reduced retries for faster failure
            retry_delay = 0.5

            for attempt in range(max_retries):
                try:
                    logger.debug("DaemonDataProvider: Fetching rate samples (seconds=%d) from IPC client (attempt %d/%d)",
                               seconds, attempt + 1, max_retries)
                    response = await self._client.get_rate_samples(seconds)
                    logger.debug("DaemonDataProvider: Received RateSamplesResponse with %d samples", len(response.samples) if response.samples else 0)

                    if not response.samples:
                        logger.warning("DaemonDataProvider: No samples in response from IPC client")
                        return []

                    # Convert RateSample objects to dicts
                    samples = [sample.model_dump() for sample in response.samples]
                    logger.debug("DaemonDataProvider: Converted %d samples to dicts", len(samples))
                    return samples
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Timeout fetching rate samples (attempt %d/%d), retrying in %.1fs...",
                                   attempt + 1, max_retries, retry_delay)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        continue
                    logger.warning("DaemonDataProvider: Timeout fetching rate samples after %d attempts", max_retries)
                    return []
                except Exception as e:
                    import aiohttp

                    if isinstance(
                        e,
                        (
                            aiohttp.ClientConnectorError,
                            aiohttp.ServerTimeoutError,
                            aiohttp.ClientOSError,
                        ),
                    ):
                        logger.debug(
                            "DaemonDataProvider: IPC unreachable fetching rate samples: %s",
                            e,
                        )
                        return []
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Error fetching rate samples (attempt %d/%d): %s, retrying...",
                                   attempt + 1, max_retries, e)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    logger.error("DaemonDataProvider: Error fetching rate samples after %d attempts: %s", max_retries, e, exc_info=True)
                    return []

            return []

        cache_key = f"rate_samples_{seconds}"
        return await self._get_cached(cache_key, _fetch, ttl=3.0)

    async def get_disk_io_metrics(self) -> dict[str, Any]:
        """Get disk I/O metrics from daemon."""
        async def _fetch() -> dict[str, Any]:
            max_retries = 2
            retry_delay = 0.5

            for attempt in range(max_retries):
                try:
                    logger.debug("DaemonDataProvider: Fetching disk I/O metrics from IPC client (attempt %d/%d)",
                               attempt + 1, max_retries)
                    response = await self._client.get_disk_io_metrics()
                    metrics = response.model_dump()
                    logger.debug("DaemonDataProvider: Received disk I/O metrics: %s", metrics)
                    return metrics
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Timeout fetching disk I/O metrics (attempt %d/%d), retrying...",
                                   attempt + 1, max_retries)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    logger.warning("DaemonDataProvider: Timeout fetching disk I/O metrics after %d attempts", max_retries)
                    return {
                        "read_throughput": 0.0,
                        "write_throughput": 0.0,
                        "cache_hit_rate": 0.0,
                        "timing_ms": 0.0,
                    }
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Error fetching disk I/O metrics (attempt %d/%d): %s, retrying...",
                                   attempt + 1, max_retries, e)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    logger.error("DaemonDataProvider: Error fetching disk I/O metrics after %d attempts: %s", max_retries, e, exc_info=True)
                    return {
                        "read_throughput": 0.0,
                        "write_throughput": 0.0,
                        "cache_hit_rate": 0.0,
                        "timing_ms": 0.0,
                    }

            return {
                "read_throughput": 0.0,
                "write_throughput": 0.0,
                "cache_hit_rate": 0.0,
                "timing_ms": 0.0,
            }

        return await self._get_cached("disk_io_metrics", _fetch, ttl=2.0)

    async def get_network_timing_metrics(self) -> dict[str, Any]:
        """Get network timing metrics from daemon."""
        async def _fetch() -> dict[str, Any]:
            max_retries = 2
            retry_delay = 0.5

            for attempt in range(max_retries):
                try:
                    logger.debug("DaemonDataProvider: Fetching network timing metrics from IPC client (attempt %d/%d)",
                               attempt + 1, max_retries)
                    response = await self._client.get_network_timing_metrics()
                    metrics = response.model_dump()
                    logger.debug("DaemonDataProvider: Received network timing metrics: %s", metrics)
                    return metrics
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Timeout fetching network timing metrics (attempt %d/%d), retrying...",
                                   attempt + 1, max_retries)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    logger.warning("DaemonDataProvider: Timeout fetching network timing metrics after %d attempts", max_retries)
                    return {
                        "utp_delay_ms": 0.0,
                        "network_overhead_rate": 0.0,
                    }
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug("DaemonDataProvider: Error fetching network timing metrics (attempt %d/%d): %s, retrying...",
                                   attempt + 1, max_retries, e)
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    logger.error("DaemonDataProvider: Error fetching network timing metrics after %d attempts: %s", max_retries, e, exc_info=True)
                    return {
                        "utp_delay_ms": 0.0,
                        "network_overhead_rate": 0.0,
                    }

            return {
                "utp_delay_ms": 0.0,
                "network_overhead_rate": 0.0,
            }

        return await self._get_cached("network_timing_metrics", _fetch, ttl=2.0)

    async def get_system_metrics(self) -> dict[str, Any]:
        """Get system metrics (CPU, memory, disk) from daemon.
        
        Returns:
            Dictionary with system metrics:
            - cpu_usage: CPU usage as percentage (0-100)
            - memory_usage: Memory usage as percentage (0-100)
            - disk_usage: Disk usage as percentage (0-100)
        """
        async def _fetch() -> dict[str, Any]:
            try:
                logger.debug("DaemonDataProvider: Fetching system metrics from IPC client")
                # Fetch Prometheus metrics and parse for system metrics
                prometheus_text = await self._client.get_metrics()
                parsed_metrics = self._parse_prometheus_metrics(prometheus_text)

                # Extract system metrics from parsed Prometheus data
                system_data = parsed_metrics.get("system", {})

                # Try to extract CPU, memory, and disk usage
                # Prometheus metrics may have various names, try common ones
                cpu_usage = 0.0
                memory_usage = 0.0
                disk_usage = 0.0

                # Look for CPU usage (common names: cpu_usage, cpu_usage_percent, system_cpu_usage)
                for key in ["cpu_usage", "cpu_usage_percent", "system_cpu_usage", "cpu_percent"]:
                    if key in system_data:
                        cpu_usage = float(system_data[key])
                        break

                # Look for memory usage (common names: memory_usage, memory_usage_percent, system_memory_usage)
                for key in ["memory_usage", "memory_usage_percent", "system_memory_usage", "memory_percent"]:
                    if key in system_data:
                        memory_usage = float(system_data[key])
                        break

                # Look for disk usage (common names: disk_usage, disk_usage_percent, system_disk_usage)
                for key in ["disk_usage", "disk_usage_percent", "system_disk_usage", "disk_percent"]:
                    if key in system_data:
                        disk_usage = float(system_data[key])
                        break

                # If not found in system metrics, try global metrics
                if cpu_usage == 0.0 or memory_usage == 0.0 or disk_usage == 0.0:
                    global_data = parsed_metrics.get("global", {})
                    if cpu_usage == 0.0:
                        for key in ["cpu_usage", "cpu_usage_percent"]:
                            if key in global_data:
                                cpu_usage = float(global_data[key])
                                break
                    if memory_usage == 0.0:
                        for key in ["memory_usage", "memory_usage_percent"]:
                            if key in global_data:
                                memory_usage = float(global_data[key])
                                break
                    if disk_usage == 0.0:
                        for key in ["disk_usage", "disk_usage_percent"]:
                            if key in global_data:
                                disk_usage = float(global_data[key])
                                break

                metrics = {
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "disk_usage": disk_usage,
                }
                logger.debug("DaemonDataProvider: Extracted system metrics: %s", metrics)
                return metrics
            except Exception as e:
                logger.error("DaemonDataProvider: Error fetching system metrics: %s", e, exc_info=True)
                return {
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "disk_usage": 0.0,
                }

        return await self._get_cached("system_metrics", _fetch, ttl=2.0)

    async def get_peer_metrics(self) -> dict[str, Any]:
        """Get global peer metrics across all torrents."""
        async def _fetch() -> dict[str, Any]:
            try:
                response = await self._client.get_peer_metrics()
                metrics = response.model_dump()
                peers = metrics.get("peers", [])
                if isinstance(peers, list):
                    normalized_peers = [
                        _normalize_peer_metric(peer)
                        if isinstance(peer, dict)
                        else peer
                        for peer in peers
                    ]
                    metrics["peers"] = normalized_peers
                return metrics
            except Exception as e:
                logger.error("Error fetching peer metrics: %s", e, exc_info=True)
                return {
                    "total_peers": 0,
                    "active_peers": 0,
                    "peers": [],
                }

        return await self._get_cached("peer_metrics", _fetch, ttl=2.0)

    async def get_dht_health_summary(self, limit: int = 8) -> dict[str, Any]:
        """Aggregate DHT discovery health metrics from the daemon."""

        async def _fetch() -> dict[str, Any]:
            torrents = await self.list_torrents()
            if not torrents:
                summary = _empty_dht_summary()
                summary["updated_at"] = time.time()
                return summary

            summary_items: list[dict[str, Any]] = []
            total_queries = 0
            total_bootstrap_recovery_attempts = 0
            total_bootstrap_zero_state_count = 0
            aggressive_enabled = 0
            worst_health_state = "unknown"

            for torrent in torrents:
                info_hash_hex = torrent.get("info_hash")
                if not info_hash_hex:
                    continue
                try:
                    metrics_response = await self._client.get_torrent_dht_metrics(info_hash_hex)
                except Exception as exc:
                    logger.debug(
                        "DaemonDataProvider: Error fetching DHT metrics for %s: %s",
                        info_hash_hex[:8],
                        exc,
                    )
                    continue

                if not metrics_response:
                    continue

                metrics = metrics_response.model_dump()
                metrics["info_hash"] = info_hash_hex
                metrics["name"] = torrent.get("name") or info_hash_hex[:12]
                metrics["status"] = torrent.get("status", "unknown")
                metrics["download_rate"] = float(torrent.get("download_rate", 0.0) or 0.0)
                metrics["upload_rate"] = float(torrent.get("upload_rate", 0.0) or 0.0)
                metrics["progress"] = float(torrent.get("progress", 0.0) or 0.0)

                health_score, health_label = _compute_dht_health_score(metrics)
                metrics["health_score"] = health_score
                metrics["health_label"] = health_label

                summary_items.append(metrics)
                total_queries += int(metrics.get("total_queries", 0) or 0)
                if metrics.get("aggressive_mode_enabled"):
                    aggressive_enabled += 1

            if not summary_items:
                summary = _empty_dht_summary()
                summary["updated_at"] = time.time()
                return summary

            worst_items = sorted(
                summary_items,
                key=lambda item: item.get("health_score", 0.0),
            )[: max(1, limit)]

            overall_health = sum(item["health_score"] for item in summary_items) / len(summary_items)

            return {
                "updated_at": time.time(),
                "overall_health": overall_health,
                "torrents_with_dht": len(summary_items),
                "aggressive_enabled": aggressive_enabled,
                "total_queries": total_queries,
                "items": worst_items,
                "all_items": summary_items,
            }

        return await self._get_cached("dht_health_summary", _fetch, ttl=2.0)

    async def get_nat_status(self) -> dict[str, Any]:
        """Get NAT status from daemon (DaemonDataProvider only)."""
        try:
            response = await self._client.get_nat_status()
            d = response.model_dump()
            d.setdefault("active_protocol", d.get("method"))
            return d
        except Exception as e:
            logger.debug("DaemonDataProvider: get_nat_status failed: %s", e)
            return {}

    async def get_peer_quality_distribution(self) -> dict[str, Any]:
        """Aggregate peer quality distribution metrics across all torrents.
        
        Returns:
            Dictionary with:
            - total_peers: Total number of unique peers across all torrents
            - quality_tiers: Distribution by quality tier (excellent/good/fair/poor)
            - average_quality: Average quality score across all peers
            - top_peers: Top 10 highest quality peers with details
            - per_torrent: List of per-torrent quality summaries
        """
        async def _fetch() -> dict[str, Any]:
            torrents = await self.list_torrents()
            if not torrents:
                return {
                    "total_peers": 0,
                    "quality_tiers": {
                        "excellent": 0,
                        "good": 0,
                        "fair": 0,
                        "poor": 0,
                    },
                    "average_quality": 0.0,
                    "top_peers": [],
                    "per_torrent": [],
                }

            all_peers: dict[str, dict[str, Any]] = {}  # peer_key -> peer data
            per_torrent_summaries: list[dict[str, Any]] = []
            total_quality_sum = 0.0
            total_peers_counted = 0

            for torrent in torrents:
                info_hash_hex = torrent.get("info_hash")
                if not info_hash_hex:
                    continue

                try:
                    peer_quality_response = await self._client.get_torrent_peer_quality(info_hash_hex)
                except Exception as exc:
                    logger.debug(
                        "DaemonDataProvider: Error fetching peer quality for %s: %s",
                        info_hash_hex[:8],
                        exc,
                    )
                    continue

                if not peer_quality_response:
                    continue

                quality_data = peer_quality_response.model_dump()

                # Aggregate per-torrent summary
                per_torrent_summaries.append({
                    "info_hash": info_hash_hex,
                    "name": torrent.get("name") or info_hash_hex[:12],
                    "total_peers_ranked": quality_data.get("total_peers_ranked", 0),
                    "average_quality_score": quality_data.get("average_quality_score", 0.0),
                    "high_quality_peers": quality_data.get("high_quality_peers", 0),
                    "medium_quality_peers": quality_data.get("medium_quality_peers", 0),
                    "low_quality_peers": quality_data.get("low_quality_peers", 0),
                })

                # Aggregate top peers (deduplicate by peer_key)
                top_peers = quality_data.get("top_quality_peers", [])
                for peer in top_peers:
                    peer_key = peer.get("peer_key") or f"{peer.get('ip', 'unknown')}:{peer.get('port', 0)}"
                    if peer_key not in all_peers:
                        all_peers[peer_key] = peer.copy()
                        all_peers[peer_key]["torrents"] = [info_hash_hex]
                    else:
                        # Update if this peer has better quality in this torrent
                        existing_score = all_peers[peer_key].get("quality_score", 0.0)
                        new_score = peer.get("quality_score", 0.0)
                        if new_score > existing_score:
                            all_peers[peer_key].update(peer)
                        if info_hash_hex not in all_peers[peer_key].get("torrents", []):
                            all_peers[peer_key].setdefault("torrents", []).append(info_hash_hex)

                # Aggregate quality scores
                avg_score = quality_data.get("average_quality_score", 0.0)
                peer_count = quality_data.get("total_peers_ranked", 0)
                if peer_count > 0:
                    total_quality_sum += avg_score * peer_count
                    total_peers_counted += peer_count

            # Calculate overall distribution
            quality_tiers = {
                "excellent": 0,
                "good": 0,
                "fair": 0,
                "poor": 0,
            }

            for peer_data in all_peers.values():
                score = float(peer_data.get("quality_score", 0.0))
                if score >= 0.7:
                    quality_tiers["excellent"] += 1
                elif score >= 0.5:
                    quality_tiers["good"] += 1
                elif score >= 0.3:
                    quality_tiers["fair"] += 1
                else:
                    quality_tiers["poor"] += 1

            # Calculate overall average quality
            average_quality = total_quality_sum / total_peers_counted if total_peers_counted > 0 else 0.0

            # Get top 10 peers by quality score
            top_peers_list = sorted(
                all_peers.values(),
                key=lambda p: float(p.get("quality_score", 0.0)),
                reverse=True,
            )[:10]

            return {
                "total_peers": len(all_peers),
                "quality_tiers": quality_tiers,
                "average_quality": average_quality,
                "top_peers": top_peers_list,
                "per_torrent": per_torrent_summaries,
            }

        return await self._get_cached("peer_quality_distribution", _fetch, ttl=2.0)

    async def get_global_kpis(self) -> dict[str, Any]:
        """Get global Key Performance Indicators from daemon."""
        async def _fetch() -> dict[str, Any]:
            try:
                response = await self._client.get_detailed_global_metrics()
                return response.model_dump()
            except Exception as e:
                logger.debug("Error fetching global KPIs: %s", e)
                # Return empty/default KPIs on error
                return {
                    "total_peers": 0,
                    "average_download_rate": 0.0,
                    "average_upload_rate": 0.0,
                    "total_bytes_downloaded": 0,
                    "total_bytes_uploaded": 0,
                    "shared_peers_count": 0,
                    "cross_torrent_sharing": 0.0,
                    "overall_efficiency": 0.0,
                    "bandwidth_utilization": 0.0,
                    "connection_efficiency": 0.0,
                    "resource_utilization": 0.0,
                    "peer_efficiency": 0.0,
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "disk_usage": 0.0,
                }

        return await self._get_cached("global_kpis", _fetch, ttl=2.0)

    async def get_per_torrent_performance(self, info_hash_hex: str) -> dict[str, Any]:
        """Get per-torrent performance metrics from daemon."""
        async def _fetch() -> dict[str, Any]:
            try:
                response = await self._client.get_per_torrent_performance(info_hash_hex)
                data = response.model_dump()
                # Provide additional derived metrics for visualization layers
                pieces_total = max(int(data.get("pieces_total", 0)), 1)
                pieces_completed = int(data.get("pieces_completed", 0))
                data["piece_completion_ratio"] = pieces_completed / pieces_total
                data["swarm_health_score"] = float(data.get("swarm_availability", 0.0))
                data.setdefault("info_hash", info_hash_hex)
                return data
            except Exception as e:
                logger.debug("Error fetching per-torrent performance: %s", e)
                return {}

        cache_key = f"per_torrent_performance_{info_hash_hex}"
        return await self._get_cached(cache_key, _fetch, ttl=2.0)

    def _parse_prometheus_metrics(self, prometheus_text: str) -> dict[str, Any]:
        """Parse Prometheus format metrics into structured dict.
        
        Args:
            prometheus_text: Prometheus format metrics text
            
        Returns:
            Dictionary with keys: global, per_torrent, system, performance
        """
        result: dict[str, Any] = {
            "global": {},
            "per_torrent": {},
            "system": {},
            "performance": {},
        }

        if not prometheus_text:
            return result

        try:
            lines = prometheus_text.strip().split("\n")
            current_metric_name = None
            current_metric_type = None

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    # Parse comments
                    if line.startswith("# TYPE "):
                        # Extract metric name and type
                        parts = line[7:].split()
                        if len(parts) >= 2:
                            current_metric_name = parts[0]
                            current_metric_type = parts[1]
                    continue

                # Parse metric line: metric_name{labels} value timestamp
                if "{" in line:
                    # Has labels
                    metric_part, rest = line.split("{", 1)
                    metric_name = metric_part.strip()
                    labels_part, value_part = rest.rsplit("}", 1)
                    labels_str = labels_part
                    value_str = value_part.strip()
                else:
                    # No labels
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    metric_name = parts[0]
                    labels_str = ""
                    value_str = " ".join(parts[1:])

                # Extract value (ignore timestamp)
                try:
                    value = float(value_str.split()[0])
                except (ValueError, IndexError):
                    continue

                # Parse labels
                labels: dict[str, str] = {}
                if labels_str:
                    for label_pair in labels_str.split(","):
                        if "=" in label_pair:
                            key, val = label_pair.split("=", 1)
                            # Remove quotes
                            labels[key.strip()] = val.strip('"')

                # Categorize metrics
                if "torrent" in metric_name.lower() or "info_hash" in labels:
                    # Per-torrent metric
                    info_hash = labels.get("info_hash", "unknown")
                    if info_hash not in result["per_torrent"]:
                        result["per_torrent"][info_hash] = {}
                    result["per_torrent"][info_hash][metric_name] = value
                elif any(keyword in metric_name.lower() for keyword in ["cpu", "memory", "disk", "network", "system"]):
                    # System metric
                    result["system"][metric_name] = value
                elif any(keyword in metric_name.lower() for keyword in ["performance", "speed", "rate", "throughput", "latency"]):
                    # Performance metric
                    result["performance"][metric_name] = value
                else:
                    # Global metric
                    result["global"][metric_name] = value

        except Exception as e:
            logger.debug("Error parsing Prometheus metrics: %s", e)

        return result

    async def get_torrent_piece_availability(self, info_hash_hex: str) -> list[int]:
        """Get piece availability array for a torrent from daemon."""
        try:
            response = await self._client.get_torrent_piece_availability(info_hash_hex)
            return response.availability
        except Exception as e:
            logger.debug("Error getting piece availability from daemon: %s", e)
            return []

    async def get_piece_health(self, info_hash_hex: str) -> dict[str, Any]:
        """Aggregate piece availability, selection, and swarm health metadata.
        
        Returns enhanced piece health data including:
        - Availability array and histogram
        - DHT success ratios
        - Prioritized piece IDs for coloring
        - Peer quality metrics
        """

        async def _fetch() -> dict[str, Any]:
            availability = await self.get_torrent_piece_availability(info_hash_hex)
            try:
                selection_metrics = await self._client.get_torrent_piece_selection_metrics(info_hash_hex)
            except Exception as exc:
                logger.debug("Error fetching piece selection metrics: %s", exc)
                selection_metrics = {}

            try:
                dht_metrics = await self._client.get_torrent_dht_metrics(info_hash_hex)
            except Exception as exc:
                logger.debug("Error fetching DHT metrics: %s", exc)
                dht_metrics = None

            try:
                peer_quality = await self._client.get_torrent_peer_quality(info_hash_hex)
            except Exception as exc:
                logger.debug("Error fetching peer quality metrics: %s", exc)
                peer_quality = None

            histogram = self._build_availability_histogram(availability)
            max_peers = max(availability) if availability else 0

            # Extract prioritized piece IDs from selection metrics
            prioritized_pieces: list[int] = []
            if selection_metrics:
                # Look for priority fields in selection metrics
                if isinstance(selection_metrics, dict):
                    # Common field names for prioritized pieces
                    for key in ["prioritized_pieces", "high_priority_pieces", "next_pieces"]:
                        if key in selection_metrics:
                            prioritized_pieces = selection_metrics[key]
                            break
                    # If not found, infer from piece selection strategy
                    if not prioritized_pieces and "strategy" in selection_metrics:
                        # For rarest-first, pieces with lowest availability are prioritized
                        if availability:
                            min_availability = min(availability)
                            prioritized_pieces = [
                                i for i, count in enumerate(availability)
                                if count == min_availability and count > 0
                            ][:10]  # Limit to top 10

            # Only expose a DHT success ratio when the backend provides an explicit
            # success counter. Derived guesses were misleading during stalled downloads.
            dht_success_ratio: Optional[float] = None
            if dht_metrics:
                dht_data = (
                    dht_metrics.model_dump()
                    if hasattr(dht_metrics, "model_dump")
                    else dht_metrics
                )
                queries_total = dht_data.get("total_queries", 0)
                queries_successful = dht_data.get("queries_successful")
                if queries_total > 0 and isinstance(queries_successful, (int, float)):
                    dht_success_ratio = queries_successful / queries_total

            return {
                "info_hash": info_hash_hex,
                "availability": availability,
                "max_peers": max_peers,
                "availability_histogram": histogram,
                "piece_selection": selection_metrics or {},
                "dht_metrics": dht_metrics.model_dump() if dht_metrics else {},
                "dht_success_ratio": dht_success_ratio,
                "peer_quality": peer_quality.model_dump() if peer_quality else {},
                "prioritized_pieces": prioritized_pieces,
            }

        cache_key = f"piece_health_{info_hash_hex}"
        return await self._get_cached(cache_key, _fetch, ttl=2.0)

    async def get_scrape_result(self, info_hash_hex: str) -> Optional[Any]:
        """Get cached scrape result from the daemon for a torrent."""
        try:
            return await self._client.get_scrape_result(info_hash_hex)
        except Exception as exc:
            logger.debug("Error getting scrape result for %s: %s", info_hash_hex, exc)
            return None

    @staticmethod
    def _build_availability_histogram(availability: list[int]) -> dict[str, int]:
        """Create simple histogram buckets describing piece availability."""
        histogram = {
            "missing": 0,
            "rare": 0,
            "common": 0,
            "abundant": 0,
        }
        for count in availability:
            if count <= 0:
                histogram["missing"] += 1
            elif count == 1:
                histogram["rare"] += 1
            elif count <= 3:
                histogram["common"] += 1
            else:
                histogram["abundant"] += 1
        return histogram

    async def execute_command(
        self, command: str, *args: Any, **kwargs: Any
    ) -> Any:  # pragma: no cover
        """Execute a command using executor (if available) or IPC client.

        Args:
            command: Command name (e.g., "torrent.pause", "torrent.resume", "torrent.batch_pause")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Command result
        """
        if self._executor:
            # Use executor for command execution (consistent with CLI)
            try:
                result = await self._executor.execute(command, *args, **kwargs)
                return result
            except Exception as e:
                logger.debug("Error executing command via executor: %s", e)
                # Fall back to IPC client if executor fails

        # Note: For batch operations and service status, try IPC client directly
        # if executor is not available or fails
        if command in ("torrent.batch_pause", "torrent.batch_resume", "torrent.batch_restart", "torrent.batch_remove"):
            try:
                if command == "torrent.batch_pause":
                    info_hashes = kwargs.get("info_hashes", [])
                    return await self._client.batch_pause_torrents(info_hashes)
                if command == "torrent.batch_resume":
                    info_hashes = kwargs.get("info_hashes", [])
                    return await self._client.batch_resume_torrents(info_hashes)
                if command == "torrent.batch_restart":
                    info_hashes = kwargs.get("info_hashes", [])
                    return await self._client.batch_restart_torrents(info_hashes)
                if command == "torrent.batch_remove":
                    info_hashes = kwargs.get("info_hashes", [])
                    remove_data = kwargs.get("remove_data", False)
                    return await self._client.batch_remove_torrents(info_hashes, remove_data=remove_data)
            except Exception as e:
                logger.debug("Error executing batch command via IPC client: %s", e)

        if command == "services.status":
            try:
                return await self._client.get_services_status()
            except Exception as e:
                logger.debug("Error getting services status via IPC client: %s", e)

        # Fallback: use IPC client directly for read operations
        # For write operations, we should use executor
        logger.debug("No executor available, command may not be supported via IPC client")
        return None


class LocalDataProvider(DataProvider):
    """Data provider for local session manager."""

    def __init__(self, session: AsyncSessionManager) -> None:
        """Initialize local data provider.

        Args:
            session: AsyncSessionManager instance
        """
        self._session = session
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 0.5  # 0.5 second TTL for local (faster updates)
        self._cache_lock = asyncio.Lock()

    async def _get_cached(
        self, key: str, fetch_func: Any, ttl: Optional[float] = None
    ) -> Any:  # pragma: no cover
        """Get cached value or fetch if expired."""
        ttl = ttl or self._cache_ttl
        now = time.time()
        async with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if now - timestamp < ttl:
                    return value
        value = await fetch_func()
        async with self._cache_lock:
            self._cache[key] = (value, time.time())
        return value

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics from local session."""
        async def _fetch() -> dict[str, Any]:
            stats = await self._session.get_global_stats()
            return _normalize_global_stats_read_model(stats)
        return await self._get_cached("global_stats", _fetch)

    async def get_torrent_status(self, info_hash_hex: str) -> Optional[dict[str, Any]]:
        """Get torrent status from local session."""
        try:
            status = await self._session.get_torrent_status(info_hash_hex)
            if not status:
                return None
            return _normalize_torrent_read_model(status)
        except Exception as e:
            logger.debug("Error getting torrent status: %s", e)
            return None

    async def get_aggressive_discovery_status(
        self,
        info_hash_hex: str,
    ) -> dict[str, Any]:
        """Get best-effort local aggressive discovery status."""
        cache_key = f"aggressive_discovery_status_{info_hash_hex}"

        async def _fetch() -> dict[str, Any]:
            status = await self.get_torrent_status(info_hash_hex)
            if not status:
                return {}
            return _build_aggressive_discovery_status(
                info_hash_hex,
                status,
                getattr(self._session, "config", None),
            )

        return await self._get_cached(cache_key, _fetch, ttl=1.0)

    async def list_torrents(self) -> list[dict[str, Any]]:
        """List all torrents from local session."""
        async def _fetch() -> list[dict[str, Any]]:
            status = await self._session.get_status()
            return [_normalize_torrent_read_model(torrent_status) for torrent_status in status.values()]
        return await self._get_cached("torrent_list", _fetch, ttl=0.5)  # Increased from 0.2s to 0.5s for better balance

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List active XET workspaces from the local runtime."""
        async def _fetch() -> list[dict[str, Any]]:
            folders = await self._session.list_xet_folders()
            return [
                _normalize_xet_folder_read_model(folder)
                for folder in folders
                if isinstance(folder, dict)
            ]

        return await self._get_cached("xet_folders", _fetch, ttl=0.5)

    async def get_xet_folder_status(self, folder_key: str) -> Optional[dict[str, Any]]:
        """Get a single XET workspace status from the local runtime."""
        cache_key = f"xet_folder_status_{folder_key}"

        async def _fetch() -> Optional[dict[str, Any]]:
            status = await self._session.get_xet_folder_status(folder_key)
            if status is None:
                return None
            return _normalize_xet_folder_read_model(
                {"folder_key": folder_key, "status": status}
            )

        return await self._get_cached(cache_key, _fetch, ttl=0.5)

    async def get_xet_discovery_status(self) -> dict[str, Any]:
        """Get shared XET discovery backend status from local runtime."""
        async def _fetch() -> dict[str, Any]:
            getter = getattr(self._session, "get_xet_discovery_status", None)
            if callable(getter):
                status = getter()
                return status if isinstance(status, dict) else {}
            return {}

        return await self._get_cached("xet_discovery_status", _fetch, ttl=0.5)

    async def get_torrent_peers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get peers for a torrent from local session."""
        try:
            peers = await self._session.get_peers_for_torrent(info_hash_hex)
            return [
                {
                    "ip": p.get("ip", ""),
                    "port": p.get("port", 0),
                    "download_rate": float(p.get("download_rate", 0.0)),
                    "upload_rate": float(p.get("upload_rate", 0.0)),
                    "choked": bool(p.get("choked", False)),
                    "client": p.get("client"),
                    "uploaded": p.get("uploaded", 0),
                    "downloaded": p.get("downloaded", 0),
                    "left": p.get("left", 0),
                    "state": p.get("state", "unknown"),
                }
                for p in peers
            ]
        except Exception as e:
            logger.debug("Error getting torrent peers: %s", e)
            return []

    async def get_torrent_files(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get files for a torrent from local session."""
        try:
            # Get torrent session from session manager
            info_hash = bytes.fromhex(info_hash_hex)
            async with self._session.lock:
                torrent_session = self._session.torrents.get(info_hash)

            if not torrent_session:
                logger.debug("Torrent session not found for info_hash: %s", info_hash_hex[:8])
                return []

            # Extract file information from torrent data
            files_list: list[dict[str, Any]] = []

            # Get torrent data (could be dict or TorrentInfoModel)
            torrent_data = torrent_session.torrent_data

            # Extract file_info from torrent_data
            file_info: Optional[dict[str, Any]] = None
            if isinstance(torrent_data, dict):
                file_info = torrent_data.get("file_info")
            elif hasattr(torrent_data, "file_info"):
                file_info = torrent_data.file_info
                if hasattr(file_info, "model_dump"):
                    file_info = file_info.model_dump()

            if not file_info:
                logger.debug("No file_info found in torrent data for %s", info_hash_hex[:8])
                return []

            # Handle single-file and multi-file torrents
            if file_info.get("type") == "single":
                # Single-file torrent
                file_name = file_info.get("name", "Unknown")
                file_size = file_info.get("length", 0)
                file_path = str(torrent_session.output_dir / file_name)

                # Calculate progress from piece manager if available
                progress = 0.0
                if torrent_session.piece_manager:
                    try:
                        total_pieces = len(torrent_session.piece_manager.pieces)
                        if total_pieces > 0:
                            verified_pieces = sum(
                                1 for p in torrent_session.piece_manager.pieces
                                if p.state.name == "VERIFIED"  # type: ignore[attr-defined]
                            )
                            progress = verified_pieces / total_pieces
                    except Exception:
                        pass

                files_list.append({
                    "index": 0,
                    "path": file_path,
                    "name": file_name,
                    "size": file_size,
                    "progress": progress,
                    "priority": "normal",  # Default priority
                    "selected": True,  # Single file is always selected
                    "attributes": None,
                    "mime_type": _guess_media_metadata(file_path)[0],
                    "is_media": _guess_media_metadata(file_path)[1],
                })
            elif file_info.get("type") == "multi":
                # Multi-file torrent
                files = file_info.get("files", [])
                base_path = torrent_session.output_dir

                for idx, file_data in enumerate(files):
                    # Extract file path
                    if isinstance(file_data, dict):
                        path_parts = file_data.get("path", [])
                        if isinstance(path_parts, str):
                            file_name = path_parts
                        elif isinstance(path_parts, list):
                            file_name = "/".join(str(p) for p in path_parts)
                        else:
                            file_name = f"file_{idx}"

                        file_size = file_data.get("length", 0)
                        full_path = str(base_path / file_name)

                        # Calculate progress (simplified - would need piece-to-file mapping for accuracy)
                        progress = 0.0
                        if torrent_session.piece_manager:
                            try:
                                total_pieces = len(torrent_session.piece_manager.pieces)
                                if total_pieces > 0:
                                    verified_pieces = sum(
                                        1 for p in torrent_session.piece_manager.pieces
                                        if p.state.name == "VERIFIED"  # type: ignore[attr-defined]
                                    )
                                    # Approximate: assume uniform distribution
                                    progress = verified_pieces / total_pieces
                            except Exception:
                                pass

                        files_list.append({
                            "index": idx,
                            "path": full_path,
                            "name": file_name,
                            "size": file_size,
                            "progress": progress,
                            "priority": "normal",  # Default priority
                            "selected": True,  # Default to selected
                            "attributes": file_data.get("attributes"),
                            "mime_type": _guess_media_metadata(full_path)[0],
                            "is_media": _guess_media_metadata(full_path)[1],
                        })

            return files_list
        except Exception as e:
            logger.debug("Error getting torrent files: %s", e)
            return []

    async def get_media_stream_status(
        self,
        info_hash_hex: str,
    ) -> Optional[dict[str, Any]]:
        """Get media stream status from local session state."""
        try:
            return await self._session.get_media_stream_status(info_hash_hex=info_hash_hex)
        except Exception as e:
            logger.debug("Error getting local media status: %s", e)
            return None

    async def get_media_candidates(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return playable media candidates for a torrent."""
        files = await self.get_torrent_files(info_hash_hex)
        return [file_info for file_info in files if file_info.get("is_media")]

    async def get_torrent_trackers(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get trackers for a torrent from local session."""
        try:
            # Get torrent session from session manager
            info_hash = bytes.fromhex(info_hash_hex)
            async with self._session.lock:
                torrent_session = self._session.torrents.get(info_hash)

            if not torrent_session:
                logger.debug("Torrent session not found for info_hash: %s", info_hash_hex[:8])
                return []

            # Extract tracker URLs from torrent data
            trackers_list: list[dict[str, Any]] = []

            # Get torrent data (could be dict or TorrentInfoModel)
            torrent_data = torrent_session.torrent_data

            # Extract announce URLs
            announce_urls: list[str] = []
            if isinstance(torrent_data, dict):
                # Get announce_list if available (list of lists for tiers)
                announce_list = torrent_data.get("announce_list", [])
                if announce_list:
                    # Flatten list of lists
                    for tier in announce_list:
                        if isinstance(tier, list):
                            announce_urls.extend(tier)
                        elif isinstance(tier, str):
                            announce_urls.append(tier)

                # Fallback to single announce URL
                if not announce_urls:
                    announce = torrent_data.get("announce")
                    if announce:
                        announce_urls.append(announce)
            elif hasattr(torrent_data, "announce_list"):
                # TorrentInfoModel
                if torrent_data.announce_list:
                    for tier in torrent_data.announce_list:
                        if tier:
                            announce_urls.extend(tier)
                if not announce_urls and hasattr(torrent_data, "announce"):
                    announce_urls.append(torrent_data.announce)

            # Build tracker list with basic status
            # Note: Full tracker status (seeds, peers, last_update) would require
            # accessing tracker client state, which may not be directly available
            for url in announce_urls:
                if url:  # Skip empty URLs
                    trackers_list.append({
                        "url": url,
                        "status": "unknown",  # Would need tracker client to get actual status
                        "seeds": 0,  # Would need last scrape response
                        "peers": 0,  # Would need last scrape response
                        "downloaders": 0,  # Would need last scrape response
                        "last_update": 0.0,  # Would need last announce time
                        "error": None,  # Would need tracker error state
                    })

            return trackers_list
        except Exception as e:
            logger.debug("Error getting torrent trackers: %s", e)
            return []

    async def get_torrent_piece_availability(self, info_hash_hex: str) -> list[int]:
        """Get piece availability using local session state."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return []

        async with self._session.lock:
            torrent_session = self._session.torrents.get(info_hash)

        if not torrent_session:
            return []

        piece_manager = getattr(torrent_session, "piece_manager", None)
        if not piece_manager:
            return []

        num_pieces = getattr(piece_manager, "num_pieces", 0)
        if not num_pieces and hasattr(piece_manager, "pieces"):
            num_pieces = len(piece_manager.pieces)
        if num_pieces <= 0:
            return []

        availability = [0] * num_pieces
        piece_frequency = getattr(piece_manager, "piece_frequency", {})
        try:
            items = piece_frequency.items()
        except AttributeError:
            items = []
        for index, count in items:
            if isinstance(index, int) and 0 <= index < num_pieces:
                availability[index] = int(count)
        return availability

    async def get_piece_health(self, info_hash_hex: str) -> dict[str, Any]:
        """Aggregate piece availability and selection metrics locally.
        
        Returns enhanced piece health data including:
        - Availability array and histogram
        - Prioritized piece IDs for coloring
        - Peer quality metrics (if available from session)
        """
        availability = await self.get_torrent_piece_availability(info_hash_hex)

        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            info_hash = None

        piece_selection: dict[str, Any] = {}
        if info_hash is not None:
            async with self._session.lock:
                torrent_session = self._session.torrents.get(info_hash)
            piece_manager = getattr(torrent_session, "piece_manager", None) if torrent_session else None
            if piece_manager and hasattr(piece_manager, "get_piece_selection_metrics"):
                try:
                    piece_selection = piece_manager.get_piece_selection_metrics()
                except Exception as exc:
                    logger.debug("Error collecting local piece selection metrics: %s", exc)

        histogram = self._build_availability_histogram(availability)

        # Extract prioritized piece IDs from selection metrics
        prioritized_pieces: list[int] = []
        if piece_selection:
            for key in ["prioritized_pieces", "high_priority_pieces", "next_pieces"]:
                if key in piece_selection:
                    prioritized_pieces = piece_selection[key]
                    break
            # If not found, infer from piece selection strategy
            if not prioritized_pieces and availability:
                min_availability = min(availability)
                prioritized_pieces = [
                    i for i, count in enumerate(availability)
                    if count == min_availability and count > 0
                ][:10]  # Limit to top 10

        return {
            "info_hash": info_hash_hex,
            "availability": availability,
            "max_peers": max(availability) if availability else 0,
            "availability_histogram": histogram,
            "piece_selection": piece_selection,
            "dht_metrics": {},
            "dht_success_ratio": 0.0,  # Not available in local mode
            "peer_quality": {},
            "prioritized_pieces": prioritized_pieces,
        }

    async def get_scrape_result(self, info_hash_hex: str) -> Optional[Any]:
        """Get cached scrape result from the local session for a torrent."""
        try:
            return await self._session.get_scrape_result(info_hash_hex)
        except Exception as exc:
            logger.debug("Error getting scrape result for %s: %s", info_hash_hex, exc)
            return None

    async def get_metrics(self) -> dict[str, Any]:
        """Get metrics from local metrics collector."""
        try:
            from ccbt.monitoring import get_metrics_collector
            collector = get_metrics_collector()
            if collector:
                return {
                    "system": collector.get_system_metrics(),
                    "performance": collector.get_performance_metrics(),
                    "all_metrics": collector.get_all_metrics(),
                }
            return {}
        except Exception as e:
            logger.debug("Error getting metrics: %s", e)
            return {}

    async def get_rate_samples(self, seconds: int = 120) -> list[dict[str, Any]]:
        """Get recent rate samples directly from local session."""
        try:
            return await self._session.get_rate_samples(seconds)
        except Exception as e:
            logger.debug("Error getting rate samples: %s", e)
            return []

    async def get_disk_io_metrics(self) -> dict[str, Any]:
        """Get disk I/O metrics from local session manager."""
        try:
            return self._session.get_disk_io_metrics()
        except Exception as e:
            logger.debug("Error getting disk I/O metrics: %s", e)
            return {
                "read_throughput": 0.0,
                "write_throughput": 0.0,
                "cache_hit_rate": 0.0,
                "timing_ms": 0.0,
            }

    async def get_network_timing_metrics(self) -> dict[str, Any]:
        """Get network timing metrics from local session manager."""
        try:
            return await self._session.get_network_timing_metrics()
        except Exception as e:
            logger.debug("Error getting network timing metrics: %s", e)
            return {
                "utp_delay_ms": 0.0,
                "network_overhead_rate": 0.0,
            }

    async def get_system_metrics(self) -> dict[str, Any]:
        """Get system metrics from local metrics collector."""
        try:
            from ccbt.monitoring import get_metrics_collector
            metrics_collector = get_metrics_collector()
            if metrics_collector:
                system_metrics = metrics_collector.get_system_metrics()
                return {
                    "cpu_usage": system_metrics.get("cpu_usage", 0.0),
                    "memory_usage": system_metrics.get("memory_usage", 0.0),
                    "disk_usage": system_metrics.get("disk_usage", 0.0),
                }
            return {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "disk_usage": 0.0,
            }
        except Exception as e:
            logger.debug("Error getting system metrics: %s", e)
            return {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "disk_usage": 0.0,
            }

    async def get_peer_metrics(self) -> dict[str, Any]:
        """Get global peer metrics across all torrents from local session."""
        async def _fetch() -> dict[str, Any]:
            try:
                return await self._session.get_global_peer_metrics()
            except Exception as e:
                logger.error("Error fetching peer metrics: %s", e, exc_info=True)
                return {
                    "total_peers": 0,
                    "active_peers": 0,
                    "peers": [],
                }

        return await self._get_cached("peer_metrics", _fetch, ttl=0.5)

    async def get_dht_health_summary(self, limit: int = 8) -> dict[str, Any]:
        """Aggregate DHT health metrics directly from the local session."""

        async def _fetch() -> dict[str, Any]:
            torrents = await self.list_torrents()
            if not torrents:
                summary = _empty_dht_summary()
                summary["updated_at"] = time.time()
                return summary

            summary_items: list[dict[str, Any]] = []
            total_queries = 0
            total_bootstrap_recovery_attempts = 0
            total_bootstrap_zero_state_count = 0
            aggressive_enabled = 0
            bootstrap_health_states: list[str] = []

            async with self._session.lock:
                torrent_sessions = dict(self._session.torrents)

            for torrent in torrents:
                info_hash_hex = torrent.get("info_hash")
                if not info_hash_hex:
                    continue
                try:
                    info_hash_bytes = bytes.fromhex(info_hash_hex)
                except ValueError:
                    continue
                torrent_session = torrent_sessions.get(info_hash_bytes)
                if not torrent_session:
                    continue

                dht_setup = getattr(torrent_session, "_dht_setup", None)
                if not dht_setup:
                    continue

                dht_metrics = getattr(dht_setup, "_dht_query_metrics", None)
                aggressive_mode = getattr(dht_setup, "_aggressive_mode", False)

                metrics = {
                    "info_hash": info_hash_hex,
                    "name": torrent.get("name") or info_hash_hex[:12],
                    "status": torrent.get("status", "unknown"),
                    "download_rate": float(torrent.get("download_rate", 0.0) or 0.0),
                    "upload_rate": float(torrent.get("upload_rate", 0.0) or 0.0),
                    "progress": float(torrent.get("progress", 0.0) or 0.0),
                    "peers_found_per_query": 0.0,
                    "query_depth_achieved": 0.0,
                    "nodes_queried_per_query": 0.0,
                    "total_queries": 0,
                    "total_peers_found": 0,
                    "aggressive_mode_enabled": aggressive_mode,
                    "last_query_duration": 0.0,
                    "last_query_peers_found": 0,
                    "last_query_depth": 0,
                    "last_query_nodes_queried": 0,
                    "routing_table_size": 0,
                    "bootstrap_success_count": 0,
                    "bootstrap_failure_count": 0,
                    "rebootstrap_attempt_count": 0,
                    "rebootstrap_success_count": 0,
                    "rebootstrap_failure_count": 0,
                    "rebootstrap_last_outcome": "not_attempted",
                    "rebootstrap_last_reason": "",
                    "rebootstrap_last_source": "",
                    "rebootstrap_health_state": "unknown",
                    "bootstrap_recovery_attempts": 0,
                    "bootstrap_health_state": "unknown",
                    "bootstrap_zero_state_count": 0,
                    "bootstrap_zero_nodes_last_reason": "",
                    "rebootstrap_consecutive_failures": 0,
                    "last_bootstrap_reason": "",
                    "last_bootstrap_failure_reason": "",
                    "last_zero_node_lookup_at": 0.0,
                }

                if dht_metrics:
                    total_q = dht_metrics.get("total_queries", 0)
                    total_peers = dht_metrics.get("total_peers_found", 0)
                    query_depths = dht_metrics.get("query_depths", [])
                    nodes_queried = dht_metrics.get("nodes_queried", [])
                    last_query = dht_metrics.get("last_query", {})

                    metrics["total_queries"] = total_q
                    metrics["total_peers_found"] = total_peers
                    metrics["peers_found_per_query"] = total_peers / total_q if total_q > 0 else 0.0
                    metrics["query_depth_achieved"] = sum(query_depths) / len(query_depths) if query_depths else 0.0
                    metrics["nodes_queried_per_query"] = sum(nodes_queried) / len(nodes_queried) if nodes_queried else 0.0
                    metrics["last_query_duration"] = last_query.get("duration", 0.0)
                    metrics["last_query_peers_found"] = last_query.get("peers_found", 0)
                    metrics["last_query_depth"] = last_query.get("depth", 0)
                    metrics["last_query_nodes_queried"] = last_query.get("nodes_queried", 0)
                    metrics["bootstrap_success_count"] = dht_metrics.get(
                        "bootstrap_success_count", 0
                    )
                    metrics["bootstrap_failure_count"] = dht_metrics.get(
                        "bootstrap_failure_count", 0
                    )
                    metrics["bootstrap_recovery_attempts"] = dht_metrics.get(
                        "bootstrap_recovery_attempts", 0
                    )
                    metrics["bootstrap_health_state"] = dht_metrics.get(
                        "bootstrap_health_state", "unknown"
                    )
                    metrics["bootstrap_zero_state_count"] = dht_metrics.get(
                        "bootstrap_zero_state_count", 0
                    )
                    metrics["bootstrap_zero_nodes_last_reason"] = dht_metrics.get(
                        "bootstrap_zero_nodes_last_reason", ""
                    )
                    metrics["rebootstrap_attempt_count"] = dht_metrics.get(
                        "rebootstrap_attempt_count", 0
                    )
                    metrics["rebootstrap_success_count"] = dht_metrics.get(
                        "rebootstrap_success_count", 0
                    )
                    metrics["rebootstrap_failure_count"] = dht_metrics.get(
                        "rebootstrap_failure_count", 0
                    )
                    metrics["rebootstrap_last_outcome"] = dht_metrics.get(
                        "rebootstrap_last_outcome", "not_attempted"
                    )
                    metrics["rebootstrap_last_reason"] = dht_metrics.get(
                        "rebootstrap_last_reason", ""
                    )
                    metrics["rebootstrap_last_source"] = dht_metrics.get(
                        "rebootstrap_last_source", ""
                    )
                    metrics["rebootstrap_health_state"] = dht_metrics.get(
                        "rebootstrap_health_state", "unknown"
                    )
                    metrics["rebootstrap_consecutive_failures"] = dht_metrics.get(
                        "rebootstrap_consecutive_failures", 0
                    )
                    metrics["last_bootstrap_reason"] = dht_metrics.get(
                        "last_bootstrap_reason", ""
                    )
                    metrics["last_bootstrap_failure_reason"] = dht_metrics.get(
                        "last_bootstrap_failure_reason", ""
                    )
                    metrics["last_zero_node_lookup_at"] = dht_metrics.get(
                        "last_zero_node_lookup_at", 0.0
                    )
                    state = str(metrics.get("bootstrap_health_state", "unknown"))
                    bootstrap_health_states.append(state)
                    total_bootstrap_recovery_attempts += int(
                        metrics.get("bootstrap_recovery_attempts", 0) or 0
                    )
                    total_bootstrap_zero_state_count += int(
                        metrics.get("bootstrap_zero_state_count", 0) or 0
                    )

                dht_client = getattr(torrent_session, "dht_client", None)
                if not dht_client and hasattr(torrent_session, "session_manager"):
                    dht_client = getattr(torrent_session.session_manager, "dht_client", None)
                if dht_client and hasattr(dht_client, "routing_table"):
                    routing_table = getattr(dht_client.routing_table, "nodes", None)
                    try:
                        metrics["routing_table_size"] = len(routing_table) if routing_table is not None else 0
                    except TypeError:
                        metrics["routing_table_size"] = getattr(dht_client.routing_table, "size", 0)

                health_score, health_label = _compute_dht_health_score(metrics)
                metrics["health_score"] = health_score
                metrics["health_label"] = health_label

                summary_items.append(metrics)
                total_queries += int(metrics.get("total_queries", 0) or 0)
                if metrics.get("aggressive_mode_enabled"):
                    aggressive_enabled += 1

            if not summary_items:
                summary = _empty_dht_summary()
                summary["updated_at"] = time.time()
                return summary

            worst_items = sorted(
                summary_items,
                key=lambda item: item.get("health_score", 0.0),
            )[: max(1, limit)]

            overall_health = sum(item["health_score"] for item in summary_items) / len(summary_items)

            return {
                "updated_at": time.time(),
                "overall_health": overall_health,
                "torrents_with_dht": len(summary_items),
                "aggressive_enabled": aggressive_enabled,
                "total_queries": total_queries,
                "total_bootstrap_recovery_attempts": total_bootstrap_recovery_attempts,
                "total_bootstrap_zero_state_count": total_bootstrap_zero_state_count,
                "bootstrap_health_state": _aggregate_bootstrap_health_state(
                    bootstrap_health_states
                ),
                "items": worst_items,
                "all_items": summary_items,
            }

        return await self._get_cached("dht_health_summary", _fetch, ttl=1.0)

    async def get_peer_quality_distribution(self) -> dict[str, Any]:
        """Aggregate peer quality distribution metrics from local session.
        
        Note: Local session may not have detailed peer quality metrics.
        This implementation aggregates from available peer data.
        """
        async def _fetch() -> dict[str, Any]:
            torrents = await self.list_torrents()
            if not torrents:
                return {
                    "total_peers": 0,
                    "quality_tiers": {
                        "excellent": 0,
                        "good": 0,
                        "fair": 0,
                        "poor": 0,
                    },
                    "average_quality": 0.0,
                    "top_peers": [],
                    "per_torrent": [],
                }

            all_peers: dict[str, dict[str, Any]] = {}
            per_torrent_summaries: list[dict[str, Any]] = []
            total_quality_sum = 0.0
            total_peers_counted = 0

            for torrent in torrents:
                info_hash_hex = torrent.get("info_hash")
                if not info_hash_hex:
                    continue

                try:
                    peers = await self.get_torrent_peers(info_hash_hex)
                except Exception as exc:
                    logger.debug(
                        "LocalDataProvider: Error fetching peers for %s: %s",
                        info_hash_hex[:8],
                        exc,
                    )
                    continue

                if not peers:
                    continue

                # Calculate quality scores from peer metrics
                # Quality is based on download/upload rates and connection stability
                peer_qualities: list[float] = []
                high_quality = 0
                medium_quality = 0
                low_quality = 0

                for peer in peers:
                    download_rate = float(peer.get("download_rate", 0.0) or 0.0)
                    upload_rate = float(peer.get("upload_rate", 0.0) or 0.0)

                    # Simple quality score: based on rates (normalized)
                    # Higher rates = better quality
                    total_rate = download_rate + upload_rate
                    # Normalize to 0-1 scale (assuming max 10 MiB/s = 1.0)
                    quality_score = min(total_rate / (10 * 1024 * 1024), 1.0)

                    peer_qualities.append(quality_score)

                    peer_key = f"{peer.get('ip', 'unknown')}:{peer.get('port', 0)}"
                    if peer_key not in all_peers:
                        all_peers[peer_key] = {
                            "peer_key": peer_key,
                            "ip": peer.get("ip", "unknown"),
                            "port": peer.get("port", 0),
                            "quality_score": quality_score,
                            "download_rate": download_rate,
                            "upload_rate": upload_rate,
                            "torrents": [info_hash_hex],
                        }
                    else:
                        # Update if better quality
                        if quality_score > all_peers[peer_key].get("quality_score", 0.0):
                            all_peers[peer_key].update({
                                "quality_score": quality_score,
                                "download_rate": download_rate,
                                "upload_rate": upload_rate,
                            })
                        if info_hash_hex not in all_peers[peer_key].get("torrents", []):
                            all_peers[peer_key].setdefault("torrents", []).append(info_hash_hex)

                    # Categorize
                    if quality_score >= 0.7:
                        high_quality += 1
                    elif quality_score >= 0.3:
                        medium_quality += 1
                    else:
                        low_quality += 1

                avg_quality = sum(peer_qualities) / len(peer_qualities) if peer_qualities else 0.0
                total_quality_sum += avg_quality * len(peers)
                total_peers_counted += len(peers)

                per_torrent_summaries.append({
                    "info_hash": info_hash_hex,
                    "name": torrent.get("name") or info_hash_hex[:12],
                    "total_peers_ranked": len(peers),
                    "average_quality_score": avg_quality,
                    "high_quality_peers": high_quality,
                    "medium_quality_peers": medium_quality,
                    "low_quality_peers": low_quality,
                })

            # Calculate overall distribution
            quality_tiers = {
                "excellent": 0,
                "good": 0,
                "fair": 0,
                "poor": 0,
            }

            for peer_data in all_peers.values():
                score = float(peer_data.get("quality_score", 0.0))
                if score >= 0.7:
                    quality_tiers["excellent"] += 1
                elif score >= 0.5:
                    quality_tiers["good"] += 1
                elif score >= 0.3:
                    quality_tiers["fair"] += 1
                else:
                    quality_tiers["poor"] += 1

            # Calculate overall average quality
            average_quality = total_quality_sum / total_peers_counted if total_peers_counted > 0 else 0.0

            # Get top 10 peers by quality score
            top_peers_list = sorted(
                all_peers.values(),
                key=lambda p: float(p.get("quality_score", 0.0)),
                reverse=True,
            )[:10]

            return {
                "total_peers": len(all_peers),
                "quality_tiers": quality_tiers,
                "average_quality": average_quality,
                "top_peers": top_peers_list,
                "per_torrent": per_torrent_summaries,
            }

        return await self._get_cached("peer_quality_distribution", _fetch, ttl=2.0)

    async def get_global_kpis(self) -> dict[str, Any]:
        """Get global Key Performance Indicators from local session.
        
        Note: Local session may not have all detailed global metrics.
        This implementation aggregates from available session data.
        """
        async def _fetch() -> dict[str, Any]:
            try:
                # Get global stats
                global_stats = await self._session.get_global_stats()

                # Get system metrics
                system_metrics = await self.get_system_metrics()

                # Get peer metrics
                peer_metrics = await self.get_peer_metrics()

                # Aggregate KPIs
                total_peers = int(peer_metrics.get("total_peers", 0))
                active_peers = int(peer_metrics.get("active_peers", 0))
                peers = peer_metrics.get("peers", []) or []

                # Calculate average rates
                total_download_rate = 0.0
                total_upload_rate = 0.0
                total_bytes_downloaded = 0
                total_bytes_uploaded = 0

                for peer in peers:
                    total_download_rate += float(peer.get("download_rate", 0.0) or 0.0)
                    total_upload_rate += float(peer.get("upload_rate", 0.0) or 0.0)
                    total_bytes_downloaded += int(peer.get("bytes_downloaded", 0) or 0)
                    total_bytes_uploaded += int(peer.get("bytes_uploaded", 0) or 0)

                avg_download_rate = total_download_rate / len(peers) if peers else 0.0
                avg_upload_rate = total_upload_rate / len(peers) if peers else 0.0

                # Calculate efficiency metrics (simplified)
                bandwidth_utilization = min(1.0, (total_download_rate + total_upload_rate) / (10 * 1024 * 1024)) if peers else 0.0
                connection_efficiency = active_peers / max(total_peers, 1) if total_peers > 0 else 0.0
                overall_efficiency = (bandwidth_utilization + connection_efficiency) / 2.0

                return {
                    "total_peers": total_peers,
                    "average_download_rate": avg_download_rate,
                    "average_upload_rate": avg_upload_rate,
                    "total_bytes_downloaded": total_bytes_downloaded,
                    "total_bytes_uploaded": total_bytes_uploaded,
                    "shared_peers_count": 0,  # Not easily available in local mode
                    "cross_torrent_sharing": 0.0,  # Not easily available in local mode
                    "overall_efficiency": overall_efficiency,
                    "bandwidth_utilization": bandwidth_utilization,
                    "connection_efficiency": connection_efficiency,
                    "resource_utilization": float(system_metrics.get("cpu_usage", 0.0)) / 100.0,
                    "peer_efficiency": connection_efficiency,
                    "cpu_usage": float(system_metrics.get("cpu_usage", 0.0)) / 100.0,
                    "memory_usage": float(system_metrics.get("memory_usage", 0.0)) / 100.0,
                    "disk_usage": float(system_metrics.get("disk_usage", 0.0)) / 100.0,
                }
            except Exception as e:
                logger.debug("Error fetching global KPIs from local session: %s", e)
                return {
                    "total_peers": 0,
                    "average_download_rate": 0.0,
                    "average_upload_rate": 0.0,
                    "total_bytes_downloaded": 0,
                    "total_bytes_uploaded": 0,
                    "shared_peers_count": 0,
                    "cross_torrent_sharing": 0.0,
                    "overall_efficiency": 0.0,
                    "bandwidth_utilization": 0.0,
                    "connection_efficiency": 0.0,
                    "resource_utilization": 0.0,
                    "peer_efficiency": 0.0,
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "disk_usage": 0.0,
                }

        return await self._get_cached("global_kpis", _fetch, ttl=2.0)

    async def get_per_torrent_performance(self, info_hash_hex: str) -> dict[str, Any]:
        """Get per-torrent performance metrics from local session manager."""
        try:
            # Get torrent status
            status = await self.get_torrent_status(info_hash_hex)
            if not status:
                return {}

            # Get peers
            peers = await self.get_torrent_peers(info_hash_hex)

            # Get metrics collector for peer performance
            from ccbt.monitoring import get_metrics_collector
            metrics_collector = get_metrics_collector()

            top_peers = []
            for peer in peers[:10]:  # Top 10 peers
                peer_key = f"{peer.get('ip', 'unknown')}:{peer.get('port', 0)}"
                peer_metrics_data = {
                    "download_rate": peer.get("download_rate", 0.0),
                    "upload_rate": peer.get("upload_rate", 0.0),
                    "request_latency": 0.0,
                    "pieces_served": 0,
                    "pieces_received": 0,
                    "connection_duration": 0.0,
                    "consecutive_failures": 0,
                    "bytes_downloaded": 0,
                    "bytes_uploaded": 0,
                }

                # Try to get detailed metrics from metrics collector
                if metrics_collector:
                    peer_metrics = metrics_collector.get_peer_metrics(peer_key)
                    if peer_metrics:
                        peer_metrics_data.update({
                            "request_latency": peer_metrics.request_latency,
                            "pieces_served": peer_metrics.pieces_served,
                            "pieces_received": peer_metrics.pieces_received,
                            "connection_duration": peer_metrics.connection_duration,
                            "consecutive_failures": peer_metrics.consecutive_failures,
                            "bytes_downloaded": peer_metrics.bytes_downloaded,
                            "bytes_uploaded": peer_metrics.bytes_uploaded,
                        })

                top_peers.append({
                    "peer_key": peer_key,
                    **peer_metrics_data,
                })

            # Sort by download rate
            top_peers.sort(key=lambda p: p.get("download_rate", 0.0), reverse=True)

            # Calculate piece download rate (estimate)
            piece_size = 16384  # Default piece size
            piece_download_rate = status.get("download_rate", 0.0) / piece_size if piece_size > 0 else 0.0

            return {
                "info_hash": info_hash_hex,
                "download_rate": status.get("download_rate", 0.0),
                "upload_rate": status.get("upload_rate", 0.0),
                "progress": status.get("progress", 0.0),
                "pieces_completed": status.get("pieces_completed", 0),
                "pieces_total": status.get("pieces_total", 0),
                "connected_peers": status.get("connected_peers", 0),
                "active_peers": status.get("active_peers", 0),
                "top_peers": top_peers,
                "bytes_downloaded": status.get("downloaded", 0),
                "bytes_uploaded": status.get("uploaded", 0),
                "piece_download_rate": piece_download_rate,
                "swarm_availability": 0.0,  # Would need piece manager access
            }
        except Exception as e:
            logger.debug("Error getting per-torrent performance: %s", e)
            return {}


def create_data_provider(session: AsyncSessionManager, executor: Optional[Any] = None) -> DataProvider:
    """Create appropriate data provider based on session type.

    Args:
        session: AsyncSessionManager or DaemonInterfaceAdapter instance
        executor: Optional executor instance for command execution

    Returns:
        DataProvider instance (DaemonDataProvider or LocalDataProvider)
    """
    from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter

    if isinstance(session, DaemonInterfaceAdapter):
        # Get IPC client from adapter
        if hasattr(session, "_client"):
            # Try to get executor from CommandExecutor if available
            if executor is None:
                # Try to get executor from session if it has one
                if hasattr(session, "_executor"):
                    executor = session._executor  # type: ignore[attr-defined]
            # Pass adapter to data provider for widget registration
            return DaemonDataProvider(session._client, executor, adapter=session)  # type: ignore[attr-defined]
        # Fallback: create a new IPC client
        from ccbt.daemon.ipc_client import IPCClient
        ipc_client = IPCClient()
        return DaemonDataProvider(ipc_client, executor, adapter=session)
    return LocalDataProvider(session)

