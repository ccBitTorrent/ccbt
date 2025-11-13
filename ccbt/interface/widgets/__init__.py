"""Widget components for the terminal dashboard."""

from __future__ import annotations

from ccbt.interface.widgets.core_widgets import (
    Overview,
    PeersTable,
    SpeedSparklines,
    TorrentsTable,
)
from ccbt.interface.widgets.reusable_widgets import (
    MetricsTableWidget,
    ProgressBarWidget,
    SparklineGroup,
)

__all__ = [
    "MetricsTableWidget",
    "Overview",
    "PeersTable",
    "ProgressBarWidget",
    "SparklineGroup",
    "SpeedSparklines",
    "TorrentsTable",
]
