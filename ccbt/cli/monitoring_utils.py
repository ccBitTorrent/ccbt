"""Monitoring utilities for the CLI.

This module provides utilities for displaying monitoring information,
metrics, and status updates in the terminal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ccbt.i18n import _

if TYPE_CHECKING:
    from rich.console import Console
from ccbt.monitoring import (
    AlertManager,
    DashboardManager,
    MetricsCollector,
    TracingManager,
)

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager


async def start_monitoring(_session: AsyncSessionManager, console: Console) -> None:
    """Start monitoring components."""
    metrics_collector = MetricsCollector()
    AlertManager()
    TracingManager()
    DashboardManager()
    await metrics_collector.start()
    console.print(_("[green]Monitoring started[/green]"))  # pragma: no cover
