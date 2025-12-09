from __future__ import annotations

from rich.console import Console

from ccbt.i18n import _
from ccbt.monitoring import (
    AlertManager,
    DashboardManager,
    MetricsCollector,
    TracingManager,
)
from ccbt.session.session import AsyncSessionManager


async def start_monitoring(_session: AsyncSessionManager, console: Console) -> None:
    """Start monitoring components."""
    metrics_collector = MetricsCollector()
    AlertManager()
    TracingManager()
    DashboardManager()
    await metrics_collector.start()
    console.print(_("[green]Monitoring started[/green]"))  # pragma: no cover

