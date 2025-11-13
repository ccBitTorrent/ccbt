"""Historical trends monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Vertical
        from textual.widgets import (
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import MonitoringScreen
from ccbt.interface.widgets import SparklineGroup


class HistoricalTrendsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display historical trends for various metrics using sparklines."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #sparklines {
        height: 1fr;
    }
    """

    def __init__(
        self,
        session: AsyncSessionManager,
        refresh_interval: float = 2.0,
        *args: Any,
        **kwargs: Any,
    ):  # pragma: no cover
        """Initialize historical trends screen."""
        super().__init__(session, refresh_interval, *args, **kwargs)
        self._historical_data: dict[str, list[float]] = {}
        self._max_samples = 120

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the historical trends screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield SparklineGroup(id="sparklines")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh historical trends display."""
        try:
            content = self.query_one("#content", Static)
            sparklines = self.query_one("#sparklines", SparklineGroup)

            # Get current metrics
            stats = await self.session.get_global_stats()

            # Store historical data
            self._store_historical_metric(
                "download_rate", stats.get("download_rate", 0.0)
            )
            self._store_historical_metric("upload_rate", stats.get("upload_rate", 0.0))

            # Get system metrics if available
            if self.metrics_collector and self.metrics_collector.running:
                system_metrics = self.metrics_collector.get_system_metrics()
                self._store_historical_metric(
                    "cpu_usage", system_metrics.get("cpu_usage", 0.0)
                )
                self._store_historical_metric(
                    "memory_usage", system_metrics.get("memory_usage", 0.0)
                )

                perf_metrics = self.metrics_collector.get_performance_metrics()
                self._store_historical_metric(
                    "peer_connections", float(perf_metrics.get("peer_connections", 0))
                )

                # DHT metrics
                self._store_historical_metric(
                    "dht_nodes_discovered",
                    float(perf_metrics.get("dht_nodes_discovered", 0)),
                )

                # Queue metrics
                self._store_historical_metric(
                    "queue_length", float(perf_metrics.get("queue_length", 0))
                )

                # Disk I/O metrics
                self._store_historical_metric(
                    "disk_write_throughput",
                    perf_metrics.get("disk_write_throughput", 0.0),
                )
                self._store_historical_metric(
                    "disk_read_throughput",
                    perf_metrics.get("disk_read_throughput", 0.0),
                )

                # Tracker metrics
                self._store_historical_metric(
                    "tracker_average_response_time",
                    perf_metrics.get("tracker_average_response_time", 0.0),
                )

            # Update sparklines
            for metric_name, history in self._historical_data.items():
                sparklines.update_sparkline(
                    metric_name, history[-1] if history else 0.0
                )

            # Create summary table
            table = Table(title="Historical Trends (Last 2 minutes)", expand=True)
            table.add_column("Metric", style="cyan", ratio=2)
            table.add_column("Current", style="green", ratio=1)
            table.add_column("Min", style="dim", ratio=1)
            table.add_column("Max", style="dim", ratio=1)
            table.add_column("Avg", style="dim", ratio=1)
            table.add_column("Samples", style="dim", ratio=1)

            for metric_name, history in sorted(self._historical_data.items()):
                if history:
                    current = history[-1]
                    min_val = min(history)
                    max_val = max(history)
                    avg_val = sum(history) / len(history)

                    # Format based on metric type
                    if "rate" in metric_name or "speed" in metric_name:

                        def fmt(v: float) -> str:
                            if v >= 1024 * 1024:
                                return f"{v / (1024**2):.2f} MB/s"
                            if v >= 1024:
                                return f"{v / 1024:.2f} KB/s"
                            return f"{v:.2f} B/s"

                        table.add_row(
                            metric_name.replace("_", " ").title(),
                            fmt(current),
                            fmt(min_val),
                            fmt(max_val),
                            fmt(avg_val),
                            str(len(history)),
                        )
                    elif "usage" in metric_name or "cpu" in metric_name:
                        table.add_row(
                            metric_name.replace("_", " ").title(),
                            f"{current:.1f}%",
                            f"{min_val:.1f}%",
                            f"{max_val:.1f}%",
                            f"{avg_val:.1f}%",
                            str(len(history)),
                        )
                    else:
                        table.add_row(
                            metric_name.replace("_", " ").title(),
                            f"{current:.2f}",
                            f"{min_val:.2f}",
                            f"{max_val:.2f}",
                            f"{avg_val:.2f}",
                            str(len(history)),
                        )

            content.update(Panel(table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading historical trends: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    def _store_historical_metric(self, name: str, value: float) -> None:  # pragma: no cover
        """Store a historical metric value.

        Args:
            name: Metric name
            value: Metric value
        """
        if name not in self._historical_data:
            self._historical_data[name] = []
        self._historical_data[name].append(value)
        # Keep only last max_samples
        self._historical_data[name] = self._historical_data[name][-self._max_samples :]

