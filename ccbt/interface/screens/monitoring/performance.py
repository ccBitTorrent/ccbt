"""Performance metrics monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


class PerformanceMetricsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display performance metrics from MetricsCollector and MetricsPlugin."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #performance_table {
        height: 1fr;
    }
    #event_metrics {
        height: 1fr;
        min-height: 5;
    }
    #statistics {
        height: 1fr;
        min-height: 5;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the performance metrics screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="event_metrics")
            yield Static(id="statistics")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh performance metrics display."""
        try:
            content = self.query_one("#content", Static)
            event_metrics = self.query_one("#event_metrics", Static)
            statistics = self.query_one("#statistics", Static)

            # Get performance metrics from MetricsCollector
            perf_metrics = {}
            if self.metrics_collector and self.metrics_collector.running:
                perf_metrics = self.metrics_collector.get_performance_metrics()
                metrics_stats = self.metrics_collector.get_metrics_statistics()
            else:
                content.update(
                    Panel(
                        "Metrics collector not running. Enable metrics in configuration.",
                        title="Performance Metrics",
                        border_style="yellow",
                    )
                )
                return

            # Create performance metrics table
            table = Table(title="Performance Metrics", expand=True)
            table.add_column("Metric", style="cyan", ratio=2)
            table.add_column("Value", style="green", ratio=2)
            table.add_column("Description", style="dim", ratio=4)

            # Peer connections
            peer_conn = perf_metrics.get("peer_connections", 0)
            table.add_row("Peer Connections", str(peer_conn), "Total connected peers")

            # Download/Upload speeds
            down_speed = perf_metrics.get("download_speed", 0.0)
            up_speed = perf_metrics.get("upload_speed", 0.0)

            def format_speed(s: float) -> str:
                """Format speed in bytes/sec."""
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            table.add_row(
                "Download Speed", format_speed(down_speed), "Global download rate"
            )
            table.add_row("Upload Speed", format_speed(up_speed), "Global upload rate")

            # Pieces
            pieces_completed = perf_metrics.get("pieces_completed", 0)
            pieces_failed = perf_metrics.get("pieces_failed", 0)
            table.add_row(
                "Pieces Completed",
                str(pieces_completed),
                "Successfully downloaded pieces",
            )
            table.add_row("Pieces Failed", str(pieces_failed), "Failed piece downloads")

            # Tracker stats
            tracker_requests = perf_metrics.get("tracker_requests", 0)
            tracker_responses = perf_metrics.get("tracker_responses", 0)
            success_rate = (
                (tracker_responses / tracker_requests * 100)
                if tracker_requests > 0
                else 0.0
            )
            table.add_row(
                "Tracker Requests", str(tracker_requests), "Total tracker requests"
            )
            table.add_row(
                "Tracker Responses",
                str(tracker_responses),
                "Successful tracker responses",
            )
            table.add_row(
                "Tracker Success Rate", f"{success_rate:.1f}%", "Response success rate"
            )

            content.update(Panel(table))

            # Event-driven metrics from MetricsPlugin (if available)
            plugin_aggregates = self.get_metrics_plugin_aggregates()
            plugin_stats = self.get_metrics_plugin_stats()

            if plugin_aggregates:
                event_table = Table(
                    title="Event-Driven Metrics (MetricsPlugin)", expand=True
                )
                event_table.add_column("Metric", style="cyan", ratio=2)
                event_table.add_column("Count", style="green", ratio=1)
                event_table.add_column("Avg", style="yellow", ratio=1)
                event_table.add_column("Min", style="blue", ratio=1)
                event_table.add_column("Max", style="red", ratio=1)
                event_table.add_column("Sum", style="magenta", ratio=1)
                event_table.add_column("Unit", style="dim", ratio=1)

                # Sort by count (most active metrics first) and limit to top 15
                sorted_metrics = sorted(
                    plugin_aggregates.items(),
                    key=lambda x: x[1].get("count", 0),
                    reverse=True,
                )[:15]

                for metric_name, agg_data in sorted_metrics:
                    count = agg_data.get("count", 0)
                    avg = agg_data.get("avg", 0.0)
                    min_val = agg_data.get("min", 0.0)
                    max_val = agg_data.get("max", 0.0)
                    sum_val = agg_data.get("sum", 0.0)
                    unit = agg_data.get("unit", "")

                    # Format values based on unit
                    if unit == "bytes/sec" or "speed" in metric_name.lower():

                        def format_speed(s: float) -> str:
                            if s >= 1024 * 1024:
                                return f"{s / (1024**2):.2f} MB/s"
                            if s >= 1024:
                                return f"{s / 1024:.2f} KB/s"
                            return f"{s:.2f} B/s"

                        avg_str = format_speed(avg)
                        min_str = format_speed(min_val)
                        max_str = format_speed(max_val)
                        sum_str = format_speed(sum_val)
                    else:
                        avg_str = f"{avg:.2f}"
                        min_str = f"{min_val:.2f}"
                        max_str = f"{max_val:.2f}"
                        sum_str = f"{sum_val:.2f}"

                    event_table.add_row(
                        metric_name,
                        str(count),
                        avg_str,
                        min_str,
                        max_str,
                        sum_str,
                        unit,
                    )

                    event_metrics.update(Panel(event_table))
            else:
                event_metrics.update(
                    Panel(
                        "MetricsPlugin not available or no event metrics collected yet.\n\n"
                        "Enable MetricsPlugin in your configuration to collect event-driven metrics.",
                        title="Event-Driven Metrics",
                        border_style="dim",
                    )
                )

            # Statistics - combine MetricsCollector and MetricsPlugin stats
            stats_table = Table(
                title="Metrics Collection Statistics",
                expand=True,
                show_header=False,
                box=None,
            )
            stats_table.add_column("Statistic", style="cyan", ratio=1)
            stats_table.add_column("Value", style="green", ratio=2)

            # MetricsCollector statistics
            metrics_stats = (
                self.metrics_collector.get_metrics_statistics()
                if self.metrics_collector
                else {}
            )
            stats_table.add_row(
                "Metrics Collected", str(metrics_stats.get("metrics_collected", 0))
            )
            stats_table.add_row(
                "Alerts Triggered", str(metrics_stats.get("alerts_triggered", 0))
            )
            stats_table.add_row(
                "Collection Errors", str(metrics_stats.get("collection_errors", 0))
            )
            stats_table.add_row(
                "Registered Metrics", str(metrics_stats.get("registered_metrics", 0))
            )
            stats_table.add_row("Alert Rules", str(metrics_stats.get("alert_rules", 0)))
            stats_table.add_row(
                "Collection Interval",
                f"{metrics_stats.get('collection_interval', 0):.1f}s",
            )
            stats_table.add_row(
                "Running", "Yes" if metrics_stats.get("running", False) else "No"
            )

            # MetricsPlugin statistics if available
            if plugin_stats:
                stats_table.add_row("", "")  # Separator
                stats_table.add_row("[bold]MetricsPlugin Stats[/bold]", "")
                stats_table.add_row(
                    "Total Metrics", str(plugin_stats.get("total_metrics", 0))
                )
                stats_table.add_row(
                    "Total Aggregates", str(plugin_stats.get("total_aggregates", 0))
                )
                stats_table.add_row(
                    "Max Metrics", str(plugin_stats.get("max_metrics", 0))
                )
                stats_table.add_row(
                    "Plugin Running",
                    "Yes" if plugin_stats.get("running", False) else "No",
                )

            statistics.update(Panel(stats_table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading performance metrics: {e}",
                    title="Error",
                    border_style="red",
                )
            )

