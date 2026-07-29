"""Widget for displaying global Key Performance Indicators (KPIs)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets import Static
else:
    try:
        from textual.app import ComposeResult  # type: ignore
        from textual.reactive import reactive  # type: ignore
        from textual.widgets import Static  # type: ignore
    except ImportError:  # pragma: no cover
        ComposeResult = Any  # type: ignore[assignment,misc]

        class Static:  # type: ignore[no-redef]
            """Fallback Static widget when Textual is unavailable."""

            def data_bind(self, **kwargs: Any) -> None:
                """No-op data_bind when textual is unavailable."""
                pass

        class reactive:  # type: ignore[no-redef]
            def __init__(self, default: Any = None, *args: Any, **kwargs: Any) -> None:
                self.default = default

            def __class_getitem__(cls, item: Any) -> type:
                return cls

            def __set_name__(self, owner: Any, name: str) -> None:
                self._name = name

            def __get__(self, instance: Any, owner: Any) -> Any:
                if instance is None:
                    return self
                return instance.__dict__.get(self._name, self.default)

            def __set__(self, instance: Any, value: Any) -> None:
                instance.__dict__[self._name] = value

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

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

    # F2.6.2: bound to TerminalDashboard.global_kpis via data_bind.
    global_kpis: reactive = reactive({}, layout=False)  # type: ignore[assignment]

    def __init__(
        self,
        data_provider: Optional[Any],
        refresh_interval: float = 2.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose widget layout."""
        yield Static(id="global-kpis-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Bind to App global_kpis reactive (F2.6.2)."""
        try:
            from ccbt.interface.terminal_dashboard import TerminalDashboard

            self.data_bind(global_kpis=TerminalDashboard.global_kpis)
        except Exception as exc:  # pragma: no cover
            logger.debug("GlobalKPIsPanel data_bind skipped: %s", exc)

    def watch_global_kpis(self, value: dict[str, Any]) -> None:  # pragma: no cover
        """Reactive watcher: render KPIs from the bound dict (F2.6.2)."""
        if isinstance(value, dict):
            self.update(self._render_kpis(value))

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




















































