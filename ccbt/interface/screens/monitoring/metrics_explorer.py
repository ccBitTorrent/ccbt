"""Metrics explorer monitoring screen."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import DataTable, Footer, Header, Input, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Vertical
        from textual.widgets import (
            DataTable,
            Footer,
            Header,
            Input,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        DataTable = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Input = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import MonitoringScreen

logger = logging.getLogger(__name__)


class MetricsExplorerScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to explore all available metrics with filtering and export."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("e", "export_json", "Export JSON"),
        ("p", "export_prometheus", "Export Prometheus"),
    ]

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #metrics_table {
        height: 1fr;
    }
    #metric_details {
        height: 1fr;
        min-height: 8;
    }
    #filter_input {
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the metrics explorer screen."""
        yield Header()
        with Vertical():
            yield Input(
                placeholder="Filter metrics (name or description)...", id="filter_input"
            )
            yield DataTable(id="metrics_table", zebra_stripes=True)
            yield Static(id="metric_details")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and populate metrics."""
        # Set up widgets first
        metrics_table = self.query_one("#metrics_table", DataTable)
        metrics_table.add_columns("Metric Name", "Type", "Current Value", "Description")
        metrics_table.cursor_type = "row"
        metrics_table.focus()

        filter_input = self.query_one("#filter_input", Input)
        filter_input.value = ""

        # Then call super to start refresh interval
        await super().on_mount()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh metrics explorer display."""
        try:
            if not self.metrics_collector or not self.metrics_collector.running:
                metrics_table = self.query_one("#metrics_table", DataTable)
                metrics_table.clear()
                metrics_table.add_row(
                    "Metrics collector not running",
                    "N/A",
                    "N/A",
                    "Enable metrics in configuration",
                    key="no_metrics",
                )
                return

            all_metrics = self.metrics_collector.get_all_metrics()
            metrics_table = self.query_one("#metrics_table", DataTable)
            filter_input = self.query_one("#filter_input", Input)
            filter_query = filter_input.value.strip().lower()

            # Clear and repopulate
            metrics_table.clear()

            # Filter metrics
            filtered_metrics = {}
            if filter_query:
                for name, metric_data in all_metrics.items():
                    if (
                        filter_query in name.lower()
                        or filter_query in metric_data.get("description", "").lower()
                    ):
                        filtered_metrics[name] = metric_data
            else:
                filtered_metrics = all_metrics

            # Populate table
            for name, metric_data in sorted(filtered_metrics.items()):
                metric_type = metric_data.get("type", "unknown")
                current_value = metric_data.get("current_value", "N/A")
                description = metric_data.get("description", "")[:50]

                # Format value
                if isinstance(current_value, (int, float)):
                    if abs(current_value) >= 1024 * 1024 * 1024:
                        value_str = f"{current_value / (1024**3):.2f} GB"
                    elif abs(current_value) >= 1024 * 1024:
                        value_str = f"{current_value / (1024**2):.2f} MB"
                    elif abs(current_value) >= 1024:
                        value_str = f"{current_value / 1024:.2f} KB"
                    else:
                        value_str = f"{current_value:.2f}"
                else:
                    value_str = str(current_value)

                metrics_table.add_row(
                    name, metric_type, value_str, description, key=name
                )

            # Update details when selection changes
            if (
                hasattr(metrics_table, "cursor_row_key")
                and metrics_table.cursor_row_key
            ):
                await self._show_metric_details(str(metrics_table.cursor_row_key))

        except Exception as e:
            metrics_table = self.query_one("#metrics_table", DataTable)
            metrics_table.clear()
            metrics_table.add_row(
                f"Error: {e}",
                "N/A",
                "N/A",
                "Error loading metrics",
                key="error",
            )

    async def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle metric selection."""
        metrics_table = self.query_one("#metrics_table", DataTable)
        if hasattr(metrics_table, "cursor_row_key") and metrics_table.cursor_row_key:
            await self._show_metric_details(str(metrics_table.cursor_row_key))

    async def on_data_table_cursor_row_changed(
        self, event: Any
    ) -> None:  # pragma: no cover
        """Handle cursor movement to update details."""
        metrics_table = self.query_one("#metrics_table", DataTable)
        if hasattr(metrics_table, "cursor_row_key") and metrics_table.cursor_row_key:
            await self._show_metric_details(str(metrics_table.cursor_row_key))

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle filter input submission."""
        if message.input.id == "filter_input":
            await self._refresh_data()

    async def _show_metric_details(self, metric_name: str) -> None:  # pragma: no cover
        """Display detailed information for selected metric."""
        try:
            if not self.metrics_collector:
                return

            metric = self.metrics_collector.get_metric(metric_name)
            metric_details = self.query_one("#metric_details", Static)

            if not metric:
                metric_details.update(Panel("Metric not found", title="Metric Details"))
                return

            # Get all metrics to find current value
            all_metrics = self.metrics_collector.get_all_metrics()
            metric_data = all_metrics.get(metric_name, {})

            details_table = Table(
                title=f"Metric Details: {metric_name}",
                expand=True,
                show_header=False,
                box=None,
            )
            details_table.add_column("Property", style="cyan", ratio=1)
            details_table.add_column("Value", style="green", ratio=2)

            details_table.add_row("Name", metric_name)
            details_table.add_row("Type", metric.metric_type.value)
            details_table.add_row("Description", metric.description)
            details_table.add_row("Aggregation", metric.aggregation.value)
            details_table.add_row("Retention", f"{metric.retention_seconds}s")
            details_table.add_row("Value Count", str(len(metric.values)))
            details_table.add_row(
                "Current Value", str(metric_data.get("current_value", "N/A"))
            )
            details_table.add_row(
                "Aggregated Value", str(metric_data.get("aggregated_value", "N/A"))
            )

            if metric.labels:
                labels_str = ", ".join(f"{l.name}={l.value}" for l in metric.labels)
                details_table.add_row("Labels", labels_str)

            metric_details.update(Panel(details_table))

        except Exception as e:
            metric_details = self.query_one("#metric_details", Static)
            metric_details.update(
                Panel(
                    f"Error loading metric details: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_export_metrics(
        self, format: str = "json"
    ) -> None:  # pragma: no cover
        """Export metrics in specified format to file."""
        try:
            if not self.metrics_collector:
                metric_details = self.query_one("#metric_details", Static)
                metric_details.update(
                    Panel(
                        "Metrics collector not available. Cannot export metrics.",
                        title="Export Error",
                        border_style="red",
                    )
                )
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Determine file extension based on format
            ext_map = {
                "json": ".json",
                "prometheus": ".txt",
            }
            extension = ext_map.get(format, ".txt")

            # Create export directory if it doesn't exist
            export_dir = Path(".ccbt/exports")
            export_dir.mkdir(parents=True, exist_ok=True)

            filename = f"metrics_export_{timestamp}{extension}"
            file_path = export_dir / filename

            # Export metrics from MetricsCollector
            exported_data = self.metrics_collector.export_metrics(format)

            # If JSON format, enhance with additional data
            if format == "json":
                try:
                    metrics_dict = json.loads(exported_data)

                    # Add system metrics if available
                    if self.metrics_collector.running:
                        try:
                            metrics_dict["system_metrics"] = (
                                self.metrics_collector.get_system_metrics()
                            )
                        except Exception:
                            pass

                        try:
                            metrics_dict["performance_metrics"] = (
                                self.metrics_collector.get_performance_metrics()
                            )
                        except Exception:
                            pass

                        try:
                            metrics_dict["statistics"] = (
                                self.metrics_collector.get_metrics_statistics()
                            )
                        except Exception:
                            pass

                    # Add MetricsPlugin aggregates if available
                    plugin_aggregates = self.get_metrics_plugin_aggregates()
                    if plugin_aggregates:
                        metrics_dict["event_driven_metrics"] = plugin_aggregates
                        plugin_stats = self.get_metrics_plugin_stats()
                        if plugin_stats:
                            metrics_dict["event_driven_stats"] = plugin_stats

                    # Add export metadata
                    metrics_dict["export_metadata"] = {
                        "timestamp": time.time(),
                        "format": format,
                        "version": "1.0",
                    }

                    exported_data = json.dumps(metrics_dict, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to enhance JSON export: {e}")

            # Write to file
            file_path.write_text(exported_data, encoding="utf-8")

            # Show success message
            metric_details = self.query_one("#metric_details", Static)
            success_msg = (
                f"Metrics exported successfully!\n\n"
                f"Format: {format.upper()}\n"
                f"File: {file_path}\n"
                f"Size: {len(exported_data):,} bytes\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            metric_details.update(
                Panel(
                    success_msg,
                    title="Export Success",
                    border_style="green",
                )
            )

            logger.info(
                f"Exported metrics to {file_path} ({len(exported_data):,} bytes)"
            )

        except ValueError as e:
            # Invalid format
            metric_details = self.query_one("#metric_details", Static)
            metric_details.update(
                Panel(
                    f"Invalid export format: {format}\n\nSupported formats: json, prometheus",
                    title="Export Error",
                    border_style="red",
                )
            )
            logger.error(f"Invalid export format: {e}")
        except Exception as e:
            metric_details = self.query_one("#metric_details", Static)
            metric_details.update(
                Panel(
                    f"Error exporting metrics: {e}\n\nPlease check file permissions and disk space.",
                    title="Export Error",
                    border_style="red",
                )
            )
            logger.exception("Error exporting metrics")

    async def action_export_json(self) -> None:  # pragma: no cover
        """Export metrics in JSON format."""
        await self.action_export_metrics("json")

    async def action_export_prometheus(self) -> None:  # pragma: no cover
        """Export metrics in Prometheus format."""
        await self.action_export_metrics("prometheus")

