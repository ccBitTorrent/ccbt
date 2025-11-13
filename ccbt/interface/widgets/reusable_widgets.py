"""Reusable widget components for the terminal dashboard."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import DataTable, Sparkline, Static
else:
    try:
        from textual.widgets import DataTable, Sparkline, Static
    except ImportError:
        # Fallback for when textual is not available
        class DataTable:  # type: ignore[no-redef]
            pass

        class Sparkline:  # type: ignore[no-redef]
            pass

        class Static:  # type: ignore[no-redef]
            pass


class ProgressBarWidget(Static):  # type: ignore[misc]
    """Widget to display progress bars for percentages."""

    def update_progress(
        self, value: float, max_value: float = 100.0, label: str = ""
    ) -> None:  # pragma: no cover
        """Update progress bar display.

        Args:
            value: Current value
            max_value: Maximum value (default 100.0)
            label: Optional label for the progress bar
        """
        percentage = min(100.0, max(0.0, (value / max_value) * 100.0))
        bar_length = 20
        filled = int((percentage / 100.0) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        if label:
            text = f"{label}: {value:.1f}/{max_value:.1f} ({percentage:.1f}%) [{bar}]"
        else:
            text = f"{value:.1f}/{max_value:.1f} ({percentage:.1f}%) [{bar}]"

        self.update(text)


class MetricsTableWidget(DataTable):  # type: ignore[misc]
    """Widget to display metrics in table format."""

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the metrics table widget."""
        self.zebra_stripes = True
        self.add_columns("Metric", "Value", "Type", "Description")

    def update_from_metrics(self, metrics: dict[str, Any]) -> None:  # pragma: no cover
        """Update table with metrics data.

        Args:
            metrics: Dictionary of metrics with structure:
                {
                    "metric_name": {
                        "type": "gauge|counter|histogram",
                        "current_value": value,
                        "description": "...",
                        ...
                    }
                }
        """
        self.clear()
        for name, metric_data in metrics.items():
            metric_type = metric_data.get("type", "unknown")
            current_value = metric_data.get("current_value", "N/A")
            description = metric_data.get("description", "")[
                :60
            ]  # Truncate long descriptions

            # Format value based on type
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

            self.add_row(name, value_str, metric_type, description, key=name)


class SparklineGroup(Static):  # type: ignore[misc]
    """Widget to group multiple sparklines with labels."""

    def __init__(self, *args: Any, **kwargs: Any):  # pragma: no cover
        """Initialize sparkline group."""
        super().__init__(*args, **kwargs)
        self._sparklines: dict[str, Sparkline] = {}
        self._histories: dict[str, list[float]] = {}
        self._max_samples = 120

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the sparkline group widget."""
        # Will be populated by add_sparkline calls

    def add_sparkline(
        self, name: str, data: list[float] | None = None
    ) -> None:  # pragma: no cover
        """Add or update a sparkline.

        Args:
            name: Name/label for the sparkline
            data: Historical data points (optional, can be updated later)
        """
        if name not in self._sparklines:
            sparkline = Sparkline()
            self._sparklines[name] = sparkline
            self._histories[name] = []
            self.mount(sparkline)

        if data is not None:
            self._histories[name] = data[-self._max_samples :]
            with contextlib.suppress(Exception):
                self._sparklines[name].data = self._histories[name]  # type: ignore[attr-defined]

    def update_sparkline(self, name: str, value: float) -> None:  # pragma: no cover
        """Update sparkline with new value.

        Args:
            name: Sparkline name
            value: New value to append
        """
        if name not in self._histories:
            self.add_sparkline(name)

        self._histories[name].append(value)
        self._histories[name] = self._histories[name][-self._max_samples :]

        with contextlib.suppress(Exception):
            self._sparklines[name].data = self._histories[name]  # type: ignore[attr-defined]
