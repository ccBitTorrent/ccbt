"""Metrics and observability for ccBitTorrent.

from __future__ import annotations

Provides comprehensive performance monitoring with Prometheus metrics,
structured logging, and real-time statistics tracking.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

# Define at module level so they always exist for patching/mocking
CollectorRegistry: type | None = None  # type: ignore[assignment, misc]
Counter: type | None = None  # type: ignore[assignment, misc]
Gauge: type | None = None  # type: ignore[assignment, misc]
start_http_server: Callable | None = None  # type: ignore[assignment, misc]

try:
    from prometheus_client import (
        CollectorRegistry as _CollectorRegistry,
    )
    from prometheus_client import (
        Counter as _Counter,
    )
    from prometheus_client import (
        Gauge as _Gauge,
    )
    from prometheus_client import (
        start_http_server as _start_http_server,
    )

    # Assign imported values
    CollectorRegistry = _CollectorRegistry
    Counter = _Counter
    Gauge = _Gauge
    start_http_server = _start_http_server

    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover - Defensive check for missing prometheus_client, requires uninstalling dependency
    HAS_PROMETHEUS = False


def _get_config():
    """Lazy import to avoid circular dependency."""
    from ccbt.config.config import get_config

    return get_config


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricValue:
    """A metric value with timestamp."""

    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class PeerMetrics:
    """Metrics for a single peer connection."""

    peer_key: str
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    download_rate: float = 0.0  # bytes/second
    upload_rate: float = 0.0  # bytes/second
    request_latency: float = 0.0  # average latency in seconds
    consecutive_failures: int = 0
    last_activity: float = field(default_factory=time.time)
    connection_duration: float = 0.0
    pieces_served: int = 0
    pieces_received: int = 0
    
    # Enhanced metrics for optimization
    # Piece-level performance tracking
    piece_download_speeds: dict[int, float] = field(default_factory=dict)  # piece_index -> download_speed (bytes/sec)
    piece_download_times: dict[int, float] = field(default_factory=dict)  # piece_index -> download_time (seconds)
    pieces_per_second: float = 0.0  # Average pieces downloaded per second
    
    # Efficiency metrics
    bytes_per_connection: float = 0.0  # Total bytes / connection count
    efficiency_score: float = 0.0  # Calculated efficiency (0.0-1.0)
    bandwidth_utilization: float = 0.0  # Percentage of available bandwidth used
    
    # Connection quality metrics
    connection_quality_score: float = 0.0  # Overall quality score (0.0-1.0)
    error_rate: float = 0.0  # Percentage of failed requests
    success_rate: float = 1.0  # Percentage of successful requests
    average_block_latency: float = 0.0  # Average latency per block request
    
    # Historical performance
    peak_download_rate: float = 0.0  # Peak download rate achieved
    peak_upload_rate: float = 0.0  # Peak upload rate achieved
    performance_trend: str = "stable"  # "improving", "stable", "degrading"


@dataclass
class TorrentMetrics:
    """Metrics for a single torrent."""

    torrent_id: str
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    download_rate: float = 0.0
    upload_rate: float = 0.0
    pieces_completed: int = 0
    pieces_total: int = 0
    progress: float = 0.0
    connected_peers: int = 0
    active_peers: int = 0
    start_time: float = field(default_factory=time.time)
    
    # Enhanced metrics for optimization
    # Swarm health metrics
    piece_availability_distribution: dict[int, int] = field(default_factory=dict)  # availability_count -> number_of_pieces
    average_piece_availability: float = 0.0  # Average number of peers per piece
    rarest_piece_availability: int = 0  # Minimum availability across all pieces
    swarm_health_score: float = 0.0  # Overall swarm health (0.0-1.0)
    
    # Peer performance distribution
    peer_performance_distribution: dict[str, int] = field(default_factory=dict)  # performance_tier -> count
    peer_download_speeds: list[float] = field(default_factory=list)  # List of download speeds per peer
    average_peer_download_speed: float = 0.0
    median_peer_download_speed: float = 0.0
    fastest_peer_speed: float = 0.0
    slowest_peer_speed: float = 0.0
    
    # Piece completion metrics
    piece_completion_rate: float = 0.0  # Pieces per second
    estimated_time_remaining: float = 0.0  # Estimated seconds to completion
    pieces_per_second_history: list[float] = field(default_factory=list)  # Historical completion rates
    
    # Swarm efficiency
    swarm_efficiency: float = 0.0  # Overall swarm efficiency (0.0-1.0)
    peer_contribution_balance: float = 0.0  # How balanced peer contributions are (0.0-1.0)


class MetricsCollector:
    """Collects and manages metrics for the BitTorrent client."""

    def __init__(self):
        """Initialize metrics collector."""
        self.config = _get_config()()

        # Global metrics
        self.global_download_rate = 0.0
        self.global_upload_rate = 0.0
        
        # DHT metrics
        self.dht_stats: dict[str, Any] = {}
        self.global_bytes_downloaded = 0
        self.global_bytes_uploaded = 0

        # Per-torrent metrics
        self.torrent_metrics: dict[str, TorrentMetrics] = {}

        # Per-peer metrics
        self.peer_metrics: dict[str, PeerMetrics] = {}

        # System metrics
        self.disk_queue_depth = 0
        self.hash_queue_depth = 0
        self.connected_peers_total = 0
        self.active_peers_total = 0

        # Historical data for rate calculation
        self.rate_history: deque = deque(maxlen=60)  # 60 seconds of history

        # Prometheus metrics (if available)
        if HAS_PROMETHEUS and self.config.observability.enable_metrics:
            self._setup_prometheus_metrics()

        # Background tasks
        self._metrics_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Callbacks
        self.on_metrics_update: Callable[[dict[str, Any]], None] | None = None

        self.logger = logging.getLogger(__name__)

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics if available."""
        if (
            not HAS_PROMETHEUS
            or CollectorRegistry is None
            or Gauge is None
            or Counter is None
        ):
            return

        self.registry = CollectorRegistry()

        # Global metrics
        self.prom_download_rate = Gauge(
            "ccbt_download_rate_bytes_per_second",
            "Global download rate in bytes per second",
            registry=self.registry,
        )

        self.prom_upload_rate = Gauge(
            "ccbt_upload_rate_bytes_per_second",
            "Global upload rate in bytes per second",
            registry=self.registry,
        )

        self.prom_bytes_downloaded = Counter(
            "ccbt_bytes_downloaded_total",
            "Total bytes downloaded",
            registry=self.registry,
        )

        self.prom_bytes_uploaded = Counter(
            "ccbt_bytes_uploaded_total",
            "Total bytes uploaded",
            registry=self.registry,
        )

    async def start(self) -> None:
        """Start metrics collection."""
        self._metrics_task = asyncio.create_task(self._metrics_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Start Prometheus server if enabled
        if (
            HAS_PROMETHEUS
            and self.config.observability.enable_metrics
            and hasattr(self, "registry")
            and start_http_server is not None
        ):
            try:
                port = self.config.observability.metrics_port
                start_http_server(port, registry=self.registry)
                self.logger.info("Prometheus metrics server started on port %s", port)
            except Exception:
                self.logger.exception("Failed to start Prometheus server")

        self.logger.info("Metrics collector started")

    async def stop(self) -> None:
        """Stop metrics collection."""
        if self._metrics_task:
            self._metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._metrics_task

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        self.logger.info("Metrics collector stopped")

    async def _metrics_loop(self) -> None:
        """Background task to update metrics."""
        while True:
            try:
                interval = self.config.observability.metrics_interval
                await asyncio.sleep(interval)
                await self._update_metrics()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in metrics loop")

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in cleanup loop")

    async def _update_metrics(self) -> None:
        """Update all metrics."""
        current_time = time.time()

        # Calculate global rates
        await self._calculate_global_rates()

        # Update Prometheus metrics
        if HAS_PROMETHEUS and hasattr(self, "registry"):
            await self._update_prometheus_metrics()

        # Store rate history
        self.rate_history.append(
            {
                "timestamp": current_time,
                "download_rate": self.global_download_rate,
                "upload_rate": self.global_upload_rate,
            },
        )

        # Notify callbacks
        if self.on_metrics_update:
            metrics_data = self.get_metrics_summary()
            await self.on_metrics_update(metrics_data)

    async def _calculate_global_rates(self) -> None:
        """Calculate global download/upload rates from historical data.
        
        Uses the rate_history deque to calculate average rates over the last
        N seconds (where N is the size of the deque, typically 60 seconds).
        """
        if not self.rate_history or len(self.rate_history) < 2:
            # Not enough data yet, keep current values or set to 0
            if not hasattr(self, 'global_download_rate'):
                self.global_download_rate = 0.0
            if not hasattr(self, 'global_upload_rate'):
                self.global_upload_rate = 0.0
            return
        
        # Calculate average rates from history
        # Use exponential moving average for more recent data weighting
        total_download = 0.0
        total_upload = 0.0
        count = 0
        
        # Simple average over history window
        for entry in self.rate_history:
            total_download += entry.get("download_rate", 0.0)
            total_upload += entry.get("upload_rate", 0.0)
            count += 1
        
        if count > 0:
            self.global_download_rate = total_download / count
            self.global_upload_rate = total_upload / count
        else:
            self.global_download_rate = 0.0
            self.global_upload_rate = 0.0
        
        # Also calculate from per-torrent metrics if available (more accurate)
        total_torrent_download = 0.0
        total_torrent_upload = 0.0
        torrent_count = 0
        
        for torrent_metrics in self.torrent_metrics.values():
            if hasattr(torrent_metrics, 'download_rate') and torrent_metrics.download_rate > 0:
                total_torrent_download += torrent_metrics.download_rate
            if hasattr(torrent_metrics, 'upload_rate') and torrent_metrics.upload_rate > 0:
                total_torrent_upload += torrent_metrics.upload_rate
            torrent_count += 1
        
        # Use per-torrent aggregation if available (more accurate than history)
        if torrent_count > 0:
            # Prefer per-torrent aggregation, but blend with history for smoothing
            history_weight = 0.3
            torrent_weight = 0.7
            
            avg_torrent_download = total_torrent_download / torrent_count if torrent_count > 0 else 0.0
            avg_torrent_upload = total_torrent_upload / torrent_count if torrent_count > 0 else 0.0
            
            self.global_download_rate = (
                self.global_download_rate * history_weight +
                avg_torrent_download * torrent_weight
            )
            self.global_upload_rate = (
                self.global_upload_rate * history_weight +
                avg_torrent_upload * torrent_weight
            )

    async def _update_prometheus_metrics(self) -> None:
        """Update Prometheus metrics."""
        if not hasattr(self, "prom_download_rate"):
            return

        self.prom_download_rate.set(self.global_download_rate)
        self.prom_upload_rate.set(self.global_upload_rate)
        self.prom_bytes_downloaded._value._value = self.global_bytes_downloaded  # noqa: SLF001
        self.prom_bytes_uploaded._value._value = self.global_bytes_uploaded  # noqa: SLF001

    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metric data."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour

        # Clean up old peer metrics
        to_remove = []
        for peer_key, metrics in self.peer_metrics.items():
            if current_time - metrics.last_activity > cutoff_time:
                to_remove.append(peer_key)

        for peer_key in to_remove:
            del self.peer_metrics[peer_key]

    def update_torrent_status(self, torrent_id: str, status: dict[str, Any]) -> None:
        """Update metrics for a specific torrent."""
        if torrent_id not in self.torrent_metrics:
            self.torrent_metrics[torrent_id] = TorrentMetrics(torrent_id=torrent_id)

        metrics = self.torrent_metrics[torrent_id]
        metrics.bytes_downloaded = status.get("bytes_downloaded", 0)
        metrics.bytes_uploaded = status.get("bytes_uploaded", 0)
        metrics.download_rate = status.get("download_rate", 0.0)
        metrics.upload_rate = status.get("upload_rate", 0.0)
        metrics.pieces_completed = status.get("pieces_completed", 0)
        metrics.pieces_total = status.get("pieces_total", 0)
        metrics.progress = status.get("progress", 0.0)
        metrics.connected_peers = status.get("connected_peers", 0)
        metrics.active_peers = status.get("active_peers", 0)
        
        # Enhanced metrics updates
        # Swarm health metrics
        if "piece_availability" in status:
            # piece_availability is a list of availability counts per piece
            availability_list = status.get("piece_availability", [])
            if availability_list:
                # Calculate distribution
                from collections import Counter
                availability_counter = Counter(availability_list)
                metrics.piece_availability_distribution = dict(availability_counter)
                
                # Calculate average and rarest
                metrics.average_piece_availability = sum(availability_list) / len(availability_list) if availability_list else 0.0
                metrics.rarest_piece_availability = min(availability_list) if availability_list else 0
                
                # Calculate swarm health score (0.0-1.0)
                # Health = (average_availability / max(active_peers, 1)) * (1.0 - (rarest_availability == 0))
                if metrics.active_peers > 0:
                    availability_ratio = metrics.average_piece_availability / metrics.active_peers
                    completeness_penalty = 0.0 if metrics.rarest_piece_availability == 0 else 0.2
                    metrics.swarm_health_score = min(1.0, availability_ratio * (1.0 - completeness_penalty))
                else:
                    metrics.swarm_health_score = 0.0
        
        # Peer performance distribution
        if "peer_download_speeds" in status:
            metrics.peer_download_speeds = status.get("peer_download_speeds", [])
            if metrics.peer_download_speeds:
                metrics.average_peer_download_speed = sum(metrics.peer_download_speeds) / len(metrics.peer_download_speeds)
                sorted_speeds = sorted(metrics.peer_download_speeds)
                metrics.median_peer_download_speed = sorted_speeds[len(sorted_speeds) // 2] if sorted_speeds else 0.0
                metrics.fastest_peer_speed = max(metrics.peer_download_speeds) if metrics.peer_download_speeds else 0.0
                metrics.slowest_peer_speed = min(metrics.peer_download_speeds) if metrics.peer_download_speeds else 0.0
                
                # Categorize peers into performance tiers
                if metrics.average_peer_download_speed > 0:
                    from collections import Counter
                    tiers = {
                        "fast": 0,  # > 1.5x average
                        "medium": 0,  # 0.5x - 1.5x average
                        "slow": 0,  # < 0.5x average
                    }
                    for speed in metrics.peer_download_speeds:
                        if speed > metrics.average_peer_download_speed * 1.5:
                            tiers["fast"] += 1
                        elif speed < metrics.average_peer_download_speed * 0.5:
                            tiers["slow"] += 1
                        else:
                            tiers["medium"] += 1
                    metrics.peer_performance_distribution = tiers
        
        # Piece completion metrics
        if metrics.pieces_total > 0:
            elapsed_time = time.time() - metrics.start_time
            if elapsed_time > 0:
                metrics.piece_completion_rate = metrics.pieces_completed / elapsed_time
                
                # Estimate time remaining
                remaining_pieces = metrics.pieces_total - metrics.pieces_completed
                if metrics.piece_completion_rate > 0:
                    metrics.estimated_time_remaining = remaining_pieces / metrics.piece_completion_rate
                else:
                    metrics.estimated_time_remaining = 0.0
                
                # Update history (keep last 60 samples)
                metrics.pieces_per_second_history.append(metrics.piece_completion_rate)
                if len(metrics.pieces_per_second_history) > 60:
                    metrics.pieces_per_second_history.pop(0)
        
        # Swarm efficiency
        if metrics.active_peers > 0 and metrics.download_rate > 0:
            # Efficiency = (actual_download_rate) / (theoretical_max_rate)
            # Theoretical max assumes all peers contribute equally
            theoretical_max = metrics.active_peers * metrics.average_peer_download_speed if metrics.average_peer_download_speed > 0 else metrics.download_rate
            if theoretical_max > 0:
                metrics.swarm_efficiency = min(1.0, metrics.download_rate / theoretical_max)
            else:
                metrics.swarm_efficiency = 0.0
            
            # Peer contribution balance (coefficient of variation of peer speeds)
            if len(metrics.peer_download_speeds) > 1:
                import statistics
                mean_speed = statistics.mean(metrics.peer_download_speeds)
                if mean_speed > 0:
                    std_speed = statistics.stdev(metrics.peer_download_speeds)
                    cv = std_speed / mean_speed  # Coefficient of variation
                    # Lower CV = more balanced (invert and normalize to 0-1)
                    metrics.peer_contribution_balance = max(0.0, 1.0 - min(1.0, cv))
                else:
                    metrics.peer_contribution_balance = 0.0
            else:
                metrics.peer_contribution_balance = 1.0  # Single peer = perfectly balanced

    def update_peer_metrics(self, peer_key: str, metrics_data: dict[str, Any]) -> None:
        """Update metrics for a specific peer."""
        if peer_key not in self.peer_metrics:
            self.peer_metrics[peer_key] = PeerMetrics(peer_key=peer_key)

        metrics = self.peer_metrics[peer_key]
        metrics.bytes_downloaded = metrics_data.get("bytes_downloaded", 0)
        metrics.bytes_uploaded = metrics_data.get("bytes_uploaded", 0)
        metrics.download_rate = metrics_data.get("download_rate", 0.0)
        metrics.upload_rate = metrics_data.get("upload_rate", 0.0)
        metrics.request_latency = metrics_data.get("request_latency", 0.0)
        metrics.consecutive_failures = metrics_data.get("consecutive_failures", 0)
        metrics.last_activity = time.time()
        
        # Enhanced metrics updates
        if "connection_duration" in metrics_data:
            metrics.connection_duration = metrics_data.get("connection_duration", 0.0)
        if "pieces_served" in metrics_data:
            metrics.pieces_served = metrics_data.get("pieces_served", 0)
        if "pieces_received" in metrics_data:
            metrics.pieces_received = metrics_data.get("pieces_received", 0)
        
        # Piece-level performance tracking
        if "piece_download_speeds" in metrics_data:
            metrics.piece_download_speeds.update(metrics_data.get("piece_download_speeds", {}))
        if "piece_download_times" in metrics_data:
            metrics.piece_download_times.update(metrics_data.get("piece_download_times", {}))
        
        # Calculate pieces per second
        if metrics.connection_duration > 0 and metrics.pieces_received > 0:
            metrics.pieces_per_second = metrics.pieces_received / metrics.connection_duration
        
        # Efficiency metrics
        if "bytes_per_connection" in metrics_data:
            metrics.bytes_per_connection = metrics_data.get("bytes_per_connection", 0.0)
        if "efficiency_score" in metrics_data:
            metrics.efficiency_score = metrics_data.get("efficiency_score", 0.0)
        if "bandwidth_utilization" in metrics_data:
            metrics.bandwidth_utilization = metrics_data.get("bandwidth_utilization", 0.0)
        
        # Connection quality metrics
        if "connection_quality_score" in metrics_data:
            metrics.connection_quality_score = metrics_data.get("connection_quality_score", 0.0)
        if "error_rate" in metrics_data:
            metrics.error_rate = metrics_data.get("error_rate", 0.0)
        if "success_rate" in metrics_data:
            metrics.success_rate = metrics_data.get("success_rate", 1.0)
        if "average_block_latency" in metrics_data:
            metrics.average_block_latency = metrics_data.get("average_block_latency", 0.0)
        
        # Historical performance
        if metrics.download_rate > metrics.peak_download_rate:
            metrics.peak_download_rate = metrics.download_rate
        if metrics.upload_rate > metrics.peak_upload_rate:
            metrics.peak_upload_rate = metrics.upload_rate
        
        # Calculate performance trend (simplified: compare current rate to peak)
        if metrics.download_rate > 0:
            if metrics.download_rate >= metrics.peak_download_rate * 0.9:
                metrics.performance_trend = "improving"
            elif metrics.download_rate >= metrics.peak_download_rate * 0.7:
                metrics.performance_trend = "stable"
            else:
                metrics.performance_trend = "degrading"
        
        # Calculate efficiency score if not provided
        if metrics.efficiency_score == 0.0 and metrics.connection_duration > 0:
            # Efficiency = (bytes_downloaded / connection_duration) / max(peak_download_rate, 1)
            total_bytes = metrics.bytes_downloaded + metrics.bytes_uploaded
            if total_bytes > 0:
                efficiency = (total_bytes / metrics.connection_duration) / max(metrics.peak_download_rate + metrics.peak_upload_rate, 1.0)
                metrics.efficiency_score = min(1.0, efficiency)
        
        # Calculate connection quality score if not provided
        if metrics.connection_quality_score == 0.0:
            # Quality = weighted combination of success_rate, download_rate, and latency
            success_weight = 0.4
            rate_weight = 0.3
            latency_weight = 0.3
            
            # Normalize download rate (assume max 10MB/s = 1.0)
            normalized_rate = min(1.0, metrics.download_rate / (10 * 1024 * 1024))
            
            # Normalize latency (lower is better, assume max 1s = 0.0, min 0.01s = 1.0)
            normalized_latency = max(0.0, 1.0 - (metrics.request_latency / 1.0))
            
            metrics.connection_quality_score = (
                metrics.success_rate * success_weight +
                normalized_rate * rate_weight +
                normalized_latency * latency_weight
            )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "global": {
                "download_rate": self.global_download_rate,
                "upload_rate": self.global_upload_rate,
                "bytes_downloaded": self.global_bytes_downloaded,
                "bytes_uploaded": self.global_bytes_uploaded,
                "connected_peers": self.connected_peers_total,
                "active_peers": self.active_peers_total,
            },
            "system": {
                "disk_queue_depth": self.disk_queue_depth,
                "hash_queue_depth": self.hash_queue_depth,
            },
            "dht": self.get_dht_stats(),
            "torrents": len(self.torrent_metrics),
            "peers": len(self.peer_metrics),
        }

    def get_torrent_metrics(self, torrent_id: str) -> TorrentMetrics | None:
        """Get metrics for a specific torrent."""
        return self.torrent_metrics.get(torrent_id)

    def get_peer_metrics(self, peer_key: str) -> PeerMetrics | None:
        """Get metrics for a specific peer."""
        return self.peer_metrics.get(peer_key)

    def update_dht_stats(self, dht_stats: dict[str, Any]) -> None:
        """Update DHT statistics.
        
        Args:
            dht_stats: Dictionary containing DHT routing table statistics
                      (from routing_table.get_stats())
        """
        self.dht_stats = dht_stats.copy()
    
    def get_dht_stats(self) -> dict[str, Any]:
        """Get current DHT statistics."""
        return self.dht_stats.copy() if self.dht_stats else {}
    
    def get_global_peer_metrics(self) -> dict[str, Any]:
        """Get aggregated peer metrics across all torrents.
        
        Returns:
            Dictionary containing:
            - total_peers: Total number of peers across all torrents
            - active_peers: Number of active peers (with recent activity)
            - peers: List of peer metric dictionaries
        """
        total_peers = len(self.peer_metrics)
        active_peers = sum(
            1 for metrics in self.peer_metrics.values()
            if time.time() - metrics.last_activity < 300.0  # Active if activity in last 5 minutes
        )
        
        # Convert peer metrics to dictionaries
        peers = []
        for peer_key, metrics in self.peer_metrics.items():
            peer_dict = {
                "peer_key": peer_key,
                "bytes_downloaded": metrics.bytes_downloaded,
                "bytes_uploaded": metrics.bytes_uploaded,
                "download_rate": metrics.download_rate,
                "upload_rate": metrics.upload_rate,
                "request_latency": metrics.request_latency,
                "consecutive_failures": metrics.consecutive_failures,
                "connection_duration": metrics.connection_duration,
                "pieces_served": metrics.pieces_served,
                "pieces_received": metrics.pieces_received,
                "pieces_per_second": metrics.pieces_per_second,
                "bytes_per_connection": metrics.bytes_per_connection,
                "efficiency_score": metrics.efficiency_score,
                "bandwidth_utilization": metrics.bandwidth_utilization,
                "connection_quality_score": metrics.connection_quality_score,
                "error_rate": metrics.error_rate,
                "success_rate": metrics.success_rate,
                "average_block_latency": metrics.average_block_latency,
                "peak_download_rate": metrics.peak_download_rate,
                "peak_upload_rate": metrics.peak_upload_rate,
                "performance_trend": metrics.performance_trend,
                "last_activity": metrics.last_activity,
            }
            peers.append(peer_dict)
        
        return {
            "total_peers": total_peers,
            "active_peers": active_peers,
            "peers": peers,
        }
    
    def get_system_wide_efficiency(self) -> dict[str, Any]:
        """Get system-wide efficiency metrics.
        
        Returns:
            Dictionary containing:
            - overall_efficiency: Overall system efficiency (0.0-1.0)
            - average_peer_efficiency: Average efficiency across all peers
            - bandwidth_utilization: Overall bandwidth utilization
            - connection_quality_average: Average connection quality score
            - active_connection_ratio: Ratio of active to total connections
        """
        if not self.peer_metrics:
            return {
                "overall_efficiency": 0.0,
                "average_peer_efficiency": 0.0,
                "bandwidth_utilization": 0.0,
                "connection_quality_average": 0.0,
                "active_connection_ratio": 0.0,
            }
        
        # Calculate averages
        total_efficiency = sum(m.efficiency_score for m in self.peer_metrics.values())
        total_bandwidth_util = sum(m.bandwidth_utilization for m in self.peer_metrics.values())
        total_quality = sum(m.connection_quality_score for m in self.peer_metrics.values())
        
        num_peers = len(self.peer_metrics)
        active_peers = sum(
            1 for m in self.peer_metrics.values()
            if time.time() - m.last_activity < 300.0
        )
        
        return {
            "overall_efficiency": total_efficiency / num_peers if num_peers > 0 else 0.0,
            "average_peer_efficiency": total_efficiency / num_peers if num_peers > 0 else 0.0,
            "bandwidth_utilization": total_bandwidth_util / num_peers if num_peers > 0 else 0.0,
            "connection_quality_average": total_quality / num_peers if num_peers > 0 else 0.0,
            "active_connection_ratio": active_peers / num_peers if num_peers > 0 else 0.0,
        }

    def export_json_metrics(self) -> str:
        """Export metrics as JSON string."""
        summary = self.get_metrics_summary()
        summary["dht"] = self.get_dht_stats()
        return json.dumps(summary, indent=2)


# Alias for backward compatibility
Metrics = MetricsCollector
