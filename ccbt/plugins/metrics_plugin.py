"""Metrics plugin for ccBitTorrent.

from __future__ import annotations

Collects and aggregates performance metrics from events.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ccbt.events import Event, EventHandler, EventType
from ccbt.logging_config import get_logger
from ccbt.plugins.base import Plugin


@dataclass
class Metric:
    """A performance metric."""

    name: str
    value: float
    unit: str
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricAggregate:
    """Aggregated metric statistics."""

    name: str
    count: int
    sum: float
    min: float
    max: float
    avg: float
    unit: str
    tags: dict[str, str] = field(default_factory=dict)


class MetricsCollector(EventHandler):
    """Collects metrics from events."""

    def __init__(self, max_metrics: int = 10000):
        """Initialize metrics collector."""
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.aggregates: dict[str, MetricAggregate] = {}
        self.logger = get_logger(__name__)

    async def handle(self, event: Event) -> None:
        """Collect metrics from events."""
        if event.event_type == EventType.PERFORMANCE_METRIC.value:
            await self._handle_performance_metric(event)
        elif event.event_type == EventType.PIECE_DOWNLOADED.value:
            await self._handle_piece_downloaded(event)
        elif event.event_type == EventType.TORRENT_COMPLETED.value:
            await self._handle_torrent_completed(event)

    async def _handle_performance_metric(self, event: Event) -> None:
        """Handle performance metric event."""
        data = event.data
        metric = Metric(
            name=data["metric_name"],
            value=data["metric_value"],
            unit=data["metric_unit"],
            timestamp=event.timestamp,
            tags=data.get("tags", {}),
        )

        self.metrics.append(metric)
        self._update_aggregate(metric)

    async def _handle_piece_downloaded(self, event: Event) -> None:
        """Handle piece downloaded event."""
        data = event.data
        piece_size = data["piece_size"]
        download_time = data["download_time"]

        # Calculate speed
        if download_time > 0:
            speed = piece_size / download_time
            metric = Metric(
                name="piece_download_speed",
                value=speed,
                unit="bytes/sec",
                timestamp=event.timestamp,
                tags={"peer_ip": data.get("peer_ip", "unknown")},
            )

            self.metrics.append(metric)
            self._update_aggregate(metric)

    async def _handle_torrent_completed(self, event: Event) -> None:
        """Handle torrent completed event."""
        data = event.data
        total_size = data["total_size"]
        download_time = data["download_time"]

        # Calculate average speed
        if download_time > 0:
            avg_speed = total_size / download_time
            metric = Metric(
                name="torrent_avg_speed",
                value=avg_speed,
                unit="bytes/sec",
                timestamp=event.timestamp,
                tags={"torrent_name": data["torrent_name"]},
            )

            self.metrics.append(metric)
            self._update_aggregate(metric)

    def _update_aggregate(self, metric: Metric) -> None:
        """Update metric aggregate."""
        key = f"{metric.name}:{':'.join(f'{k}={v}' for k, v in sorted(metric.tags.items()))}"

        if key not in self.aggregates:
            self.aggregates[key] = MetricAggregate(
                name=metric.name,
                count=0,
                sum=0.0,
                min=float("inf"),
                max=float("-inf"),
                avg=0.0,
                unit=metric.unit,
                tags=metric.tags,
            )

        agg = self.aggregates[key]
        agg.count += 1
        agg.sum += metric.value
        agg.min = min(agg.min, metric.value)
        agg.max = max(agg.max, metric.value)
        agg.avg = agg.sum / agg.count

    def get_metrics(
        self,
        name: str | None = None,
        tags: dict[str, str] | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        """Get metrics with optional filtering."""
        metrics = list(self.metrics)

        if name:
            metrics = [m for m in metrics if m.name == name]

        if tags:
            metrics = [
                m for m in metrics if all(m.tags.get(k) == v for k, v in tags.items())
            ]

        return metrics[-limit:] if limit > 0 else metrics

    def get_aggregates(self, name: str | None = None) -> list[MetricAggregate]:
        """Get metric aggregates."""
        aggregates = list(self.aggregates.values())

        if name:
            aggregates = [a for a in aggregates if a.name == name]

        return aggregates


class MetricsPlugin(Plugin):
    """Plugin for collecting and aggregating metrics."""

    def __init__(self, name: str = "metrics_plugin", max_metrics: int = 10000):
        """Initialize metrics plugin."""
        super().__init__(
            name=name,
            version="1.0.0",
            description="Performance metrics collection plugin",
        )
        self.max_metrics = max_metrics
        self.collector: MetricsCollector | None = None

    async def initialize(self) -> None:
        """Initialize the metrics plugin."""
        self.logger.info("Initializing metrics plugin")

    async def start(self) -> None:
        """Start the metrics plugin."""
        self.logger.info("Starting metrics plugin")

        # Create metrics collector
        self.collector = MetricsCollector(self.max_metrics)

        # Register event handler
        from ccbt.events import get_event_bus

        event_bus = get_event_bus()

        # Register for relevant event types
        event_bus.register_handler(EventType.PERFORMANCE_METRIC.value, self.collector)
        event_bus.register_handler(EventType.PIECE_DOWNLOADED.value, self.collector)
        event_bus.register_handler(EventType.TORRENT_COMPLETED.value, self.collector)

    async def stop(self) -> None:
        """Stop the metrics plugin."""
        self.logger.info("Stopping metrics plugin")

        if self.collector:
            from ccbt.events import get_event_bus

            event_bus = get_event_bus()

            # Unregister event handler
            event_bus.unregister_handler(
                EventType.PERFORMANCE_METRIC.value,
                self.collector,
            )
            event_bus.unregister_handler(
                EventType.PIECE_DOWNLOADED.value,
                self.collector,
            )
            event_bus.unregister_handler(
                EventType.TORRENT_COMPLETED.value,
                self.collector,
            )

    async def cleanup(self) -> None:
        """Cleanup metrics plugin resources."""
        self.logger.info("Cleaning up metrics plugin")
        self.collector = None

    def get_metrics(
        self,
        name: str | None = None,
        tags: dict[str, str] | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        """Get collected metrics."""
        if self.collector:
            return self.collector.get_metrics(name, tags, limit)
        return []

    def get_aggregates(self, name: str | None = None) -> list[MetricAggregate]:
        """Get metric aggregates."""
        if self.collector:
            return self.collector.get_aggregates(name)
        return []

    def get_stats(self) -> dict[str, Any]:
        """Get plugin statistics."""
        if self.collector:
            return {
                "total_metrics": len(self.collector.metrics),
                "total_aggregates": len(self.collector.aggregates),
                "max_metrics": self.max_metrics,
            }
        return {
            "total_metrics": 0,
            "total_aggregates": 0,
            "max_metrics": self.max_metrics,
        }
