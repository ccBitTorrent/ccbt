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


class MetricsCollector:
    """Collects and manages metrics for the BitTorrent client."""

    def __init__(self):
        """Initialize metrics collector."""
        self.config = _get_config()()

        # Global metrics
        self.global_download_rate = 0.0
        self.global_upload_rate = 0.0
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
        """Calculate global download/upload rates."""
        # This would calculate rates based on historical data
        # For now, just set placeholder values
        self.global_download_rate = 0.0
        self.global_upload_rate = 0.0

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
            "torrents": len(self.torrent_metrics),
            "peers": len(self.peer_metrics),
        }

    def get_torrent_metrics(self, torrent_id: str) -> TorrentMetrics | None:
        """Get metrics for a specific torrent."""
        return self.torrent_metrics.get(torrent_id)

    def get_peer_metrics(self, peer_key: str) -> PeerMetrics | None:
        """Get metrics for a specific peer."""
        return self.peer_metrics.get(peer_key)

    def export_json_metrics(self) -> str:
        """Export metrics as JSON string."""
        return json.dumps(self.get_metrics_summary(), indent=2)


# Alias for backward compatibility
Metrics = MetricsCollector
