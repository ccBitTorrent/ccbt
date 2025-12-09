"""Widget for displaying global Key Performance Indicators (KPIs)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets import Static
else:
    try:
        from textual.app import ComposeResult  # type: ignore
        from textual.widgets import Static  # type: ignore
    except ImportError:  # pragma: no cover
        ComposeResult = Any  # type: ignore[assignment,misc]

        class Static:  # type: ignore[no-redef]
            """Fallback Static widget when Textual is unavailable."""

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ccbt.i18n import _

logger = logging.getLogger(__name__)

__all__ = ["GlobalKPIsPanel"]


class GlobalKPIsPanel(Static):  # type: ignore[misc]
    """Widget that displays global Key Performance Indicators across all torrents."""

    DEFAULT_CSS = """
    GlobalKPIsPanel {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: Any | None,
        refresh_interval: float = 2.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider
        self._refresh_interval = refresh_interval
        self._update_task: Any | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose widget layout."""
        yield Static(id="global-kpis-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Start periodic updates when the widget is mounted."""
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Stop periodic updates when the widget is removed."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Initialize refresh timer."""

        def schedule_update() -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.create_task(self._update_from_provider())

        try:
            self._update_task = self.set_interval(self._refresh_interval, schedule_update)  # type: ignore[attr-defined]
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("GlobalKPIsPanel: Failed to start update loop: %s", exc, exc_info=True)

    async def _update_from_provider(self) -> None:
        """Fetch global KPIs data and update widget output."""
        if not self._data_provider:
            self.update(
                Panel(
                    _("Global KPIs data is unavailable in the current mode."),
                    border_style="yellow",
                )
            )
            return

        try:
            kpis = await self._data_provider.get_global_kpis()
        except Exception as exc:
            logger.error("GlobalKPIsPanel: Error loading data: %s", exc, exc_info=True)
            self.update(
                Panel(
                    _("Failed to load global KPIs: {error}").format(error=str(exc)),
                    border_style="red",
                )
            )
            return

        self.update(self._render_kpis(kpis))

    def _render_kpis(self, kpis: dict[str, Any]) -> Panel:
        """Render global KPIs view."""
        # Network KPIs
        total_peers = int(kpis.get("total_peers", 0))
        avg_download_rate = float(kpis.get("average_download_rate", 0.0))
        avg_upload_rate = float(kpis.get("average_upload_rate", 0.0))
        total_downloaded = int(kpis.get("total_bytes_downloaded", 0))
        total_uploaded = int(kpis.get("total_bytes_uploaded", 0))
        shared_peers = int(kpis.get("shared_peers_count", 0))
        cross_torrent_sharing = float(kpis.get("cross_torrent_sharing", 0.0))

        # Efficiency KPIs
        overall_efficiency = float(kpis.get("overall_efficiency", 0.0))
        bandwidth_utilization = float(kpis.get("bandwidth_utilization", 0.0))
        connection_efficiency = float(kpis.get("connection_efficiency", 0.0))
        resource_utilization = float(kpis.get("resource_utilization", 0.0))
        peer_efficiency = float(kpis.get("peer_efficiency", 0.0))

        # System KPIs
        cpu_usage = float(kpis.get("cpu_usage", 0.0))
        memory_usage = float(kpis.get("memory_usage", 0.0))
        disk_usage = float(kpis.get("disk_usage", 0.0))

        # Format helper functions
        def _format_rate(rate: float) -> str:
            if rate >= 1024 * 1024:
                return f"{rate / (1024 * 1024):.1f} MiB/s"
            if rate >= 1024:
                return f"{rate / 1024:.1f} KiB/s"
            return f"{rate:.0f} B/s"

        def _format_bytes(bytes_val: int) -> str:
            if bytes_val >= 1024 * 1024 * 1024:
                return f"{bytes_val / (1024 * 1024 * 1024):.2f} GiB"
            if bytes_val >= 1024 * 1024:
                return f"{bytes_val / (1024 * 1024):.2f} MiB"
            if bytes_val >= 1024:
                return f"{bytes_val / 1024:.2f} KiB"
            return f"{bytes_val} B"

        def _format_percentage(value: float) -> str:
            return f"{value * 100:.1f}%"

        def _get_efficiency_color(value: float) -> str:
            if value >= 0.8:
                return "green"
            if value >= 0.6:
                return "yellow"
            if value >= 0.4:
                return "orange1"
            return "red"

        # Network KPIs Table
        network_table = Table(expand=True, box=None, pad_edge=False, title=_("Network Performance"))
        network_table.add_column(_("Metric"), ratio=2)
        network_table.add_column(_("Value"), justify="right", ratio=1)

        network_table.add_row(_("Total Peers"), f"[cyan]{total_peers}[/cyan]")
        network_table.add_row(_("Shared Peers"), f"[cyan]{shared_peers}[/cyan]")
        network_table.add_row(_("Avg Download Rate"), f"[green]{_format_rate(avg_download_rate)}[/green]")
        network_table.add_row(_("Avg Upload Rate"), f"[yellow]{_format_rate(avg_upload_rate)}[/yellow]")
        network_table.add_row(_("Total Downloaded"), _format_bytes(total_downloaded))
        network_table.add_row(_("Total Uploaded"), _format_bytes(total_uploaded))
        network_table.add_row(
            _("Cross-Torrent Sharing"),
            f"[{_get_efficiency_color(cross_torrent_sharing)}]{_format_percentage(cross_torrent_sharing)}[/{_get_efficiency_color(cross_torrent_sharing)}]",
        )

        # Efficiency KPIs Table
        efficiency_table = Table(expand=True, box=None, pad_edge=False, title=_("System Efficiency"))
        efficiency_table.add_column(_("Metric"), ratio=2)
        efficiency_table.add_column(_("Value"), justify="right", ratio=1)

        efficiency_table.add_row(
            _("Overall Efficiency"),
            f"[{_get_efficiency_color(overall_efficiency)}]{_format_percentage(overall_efficiency)}[/{_get_efficiency_color(overall_efficiency)}]",
        )
        efficiency_table.add_row(
            _("Bandwidth Utilization"),
            f"[{_get_efficiency_color(bandwidth_utilization)}]{_format_percentage(bandwidth_utilization)}[/{_get_efficiency_color(bandwidth_utilization)}]",
        )
        efficiency_table.add_row(
            _("Connection Efficiency"),
            f"[{_get_efficiency_color(connection_efficiency)}]{_format_percentage(connection_efficiency)}[/{_get_efficiency_color(connection_efficiency)}]",
        )
        efficiency_table.add_row(
            _("Resource Utilization"),
            f"[{_get_efficiency_color(resource_utilization)}]{_format_percentage(resource_utilization)}[/{_get_efficiency_color(resource_utilization)}]",
        )
        efficiency_table.add_row(
            _("Peer Efficiency"),
            f"[{_get_efficiency_color(peer_efficiency)}]{_format_percentage(peer_efficiency)}[/{_get_efficiency_color(peer_efficiency)}]",
        )

        # System Resources Table
        system_table = Table(expand=True, box=None, pad_edge=False, title=_("System Resources"))
        system_table.add_column(_("Resource"), ratio=1)
        system_table.add_column(_("Usage"), justify="right", ratio=1)

        system_table.add_row(
            _("CPU"),
            f"[{_get_efficiency_color(1.0 - cpu_usage)}]{_format_percentage(cpu_usage)}[/{_get_efficiency_color(1.0 - cpu_usage)}]",
        )
        system_table.add_row(
            _("Memory"),
            f"[{_get_efficiency_color(1.0 - memory_usage)}]{_format_percentage(memory_usage)}[/{_get_efficiency_color(1.0 - memory_usage)}]",
        )
        system_table.add_row(
            _("Disk"),
            f"[{_get_efficiency_color(1.0 - disk_usage)}]{_format_percentage(disk_usage)}[/{_get_efficiency_color(1.0 - disk_usage)}]",
        )

        content = Group(
            Panel(network_table, border_style="blue"),
            Panel(efficiency_table, border_style="cyan"),
            Panel(system_table, border_style="magenta"),
        )
        return Panel(content, title=_("Global Key Performance Indicators"), border_style="bright_cyan")




















































