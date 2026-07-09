"""Wrapper widget to embed monitoring screens in the graphs section.

This allows existing MonitoringScreen classes to be used within the
tabbed interface graphs section without requiring full screen push.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from textual.containers import Container, Vertical
    from textual.reactive import reactive
    from textual.widgets import Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        def data_bind(self, **kwargs: Any) -> None:
            pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
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

logger = logging.getLogger(__name__)


class MonitoringScreenWrapper(Container):  # type: ignore[misc]
    """Wrapper to embed monitoring screen content in a container widget.
    
    This extracts the content from existing MonitoringScreen classes
    and displays it within the graphs section without requiring a full screen push.
    """

    # F2.6.12: optional local mirrors when bound to App reactives.
    disk_io_metrics: reactive = reactive({}, layout=False)  # type: ignore[assignment]
    system_metrics: reactive = reactive({}, layout=False)  # type: ignore[assignment]
    global_stats: reactive = reactive({}, layout=False)  # type: ignore[assignment]
    torrents_data: reactive = reactive([], layout=False)  # type: ignore[assignment]

    DEFAULT_CSS = """
    MonitoringScreenWrapper {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
    }
    
    #monitoring-content {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        screen_type: str,
        data_provider: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize monitoring screen wrapper.

        Args:
            screen_type: Type of monitoring screen (e.g., "disk_io", "network", "system_resources")
            data_provider: DataProvider instance for accessing data
        """
        super().__init__(*args, **kwargs)
        self._screen_type = screen_type
        self._data_provider = data_provider
        self._content_widget: Optional[Static] = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the monitoring wrapper."""
        with Vertical(id="monitoring-content"):
            yield Static("Loading...", id="monitoring-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the monitoring wrapper and bind App reactives (F2.6.12)."""
        try:
            self._content_widget = self.query_one("#monitoring-placeholder", Static)  # type: ignore[attr-defined]
            from ccbt.interface.terminal_dashboard import TerminalDashboard

            if self._screen_type == "disk_io":
                self.data_bind(disk_io_metrics=TerminalDashboard.disk_io_metrics)
            elif self._screen_type == "system_resources":
                self.data_bind(system_metrics=TerminalDashboard.system_metrics)
            elif self._screen_type == "network":
                self.data_bind(
                    global_stats=TerminalDashboard.global_stats,
                    torrents_data=TerminalDashboard.torrents_data,
                )
            else:
                self.call_later(self._refresh_content)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting monitoring wrapper: %s", e)

    def watch_disk_io_metrics(self, value: dict[str, Any]) -> None:  # pragma: no cover
        """Reactive watcher: render disk I/O panel (F2.6.12)."""
        if self._content_widget and isinstance(value, dict) and value:
            self._content_widget.update(self._render_disk_io_content(value))

    def watch_system_metrics(self, value: dict[str, Any]) -> None:  # pragma: no cover
        """Reactive watcher: render system resources panel (F2.6.12)."""
        if self._content_widget and isinstance(value, dict) and value:
            self._content_widget.update(self._render_system_resources_content(value))

    def watch_global_stats(self, value: dict[str, Any]) -> None:  # pragma: no cover
        """Reactive watcher: render network panel when stats update (F2.6.12)."""
        if self._screen_type == "network" and self._content_widget and isinstance(value, dict):
            torrents = self.torrents_data if isinstance(self.torrents_data, list) else []
            self._content_widget.update(self._render_network_content(value, torrents))

    def watch_torrents_data(self, value: list[dict[str, Any]]) -> None:  # pragma: no cover
        """Reactive watcher: re-render network panel when torrent list updates (F2.6.12)."""
        if self._screen_type == "network" and self._content_widget and isinstance(value, list):
            stats = self.global_stats if isinstance(self.global_stats, dict) else {}
            self._content_widget.update(self._render_network_content(stats, value))

    async def _refresh_content(self) -> None:  # pragma: no cover
        """Fallback refresh for unknown screen types."""
        if not self._content_widget:
            return
        self._content_widget.update(f"Monitoring: {self._screen_type}\n\nLoading metrics...")

    def _render_disk_io_content(self, metrics: dict[str, Any]) -> str:  # pragma: no cover
        """Render disk I/O metrics content from a metrics dict."""
        try:
            read_throughput = float(metrics.get("read_throughput", 0.0))
            write_throughput = float(metrics.get("write_throughput", 0.0))
            cache_hit_rate = float(metrics.get("cache_hit_rate", 0.0))
            timing_ms = float(metrics.get("timing_ms", 0.0))

            from io import StringIO

            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            def format_speed(kib_s: float) -> str:
                bps = kib_s * 1024.0
                for unit, factor in [("GB/s", 1024**3), ("MB/s", 1024**2), ("KB/s", 1024)]:
                    if bps >= factor:
                        return f"{bps / factor:.2f} {unit}"
                return f"{bps:.2f} B/s"

            io_table = Table(title="Disk I/O Statistics", expand=True, show_header=True)
            io_table.add_column("Metric", style="cyan", ratio=1)
            io_table.add_column("Value", style="green", ratio=2)
            io_table.add_row("Read Throughput", format_speed(read_throughput))
            io_table.add_row("Write Throughput", format_speed(write_throughput))
            io_table.add_row("Cache Hit Rate", f"{cache_hit_rate:.1f}%")
            io_table.add_row("Timing (avg ms)", f"{timing_ms:.2f}")

            console = Console(file=StringIO(), width=80, height=20)
            console.print(Panel(io_table, title="Disk I/O", border_style="blue"))
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error rendering disk I/O content: %s", e)
            return f"Disk I/O Error: {e}"

    def _render_system_resources_content(self, metrics: dict[str, Any]) -> str:  # pragma: no cover
        """Render system resources content from a metrics dict."""
        try:
            cpu = float(metrics.get("cpu_usage", 0.0))
            memory = float(metrics.get("memory_usage", 0.0))
            disk = float(metrics.get("disk_usage", 0.0))

            from io import StringIO

            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            def format_progress_bar(value: float, max_value: float = 100.0) -> str:
                percentage = min(100.0, max(0.0, (value / max_value) * 100.0))
                bar_length = 30
                filled = int((percentage / 100.0) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                return f"[{bar}] {percentage:.1f}%"

            table = Table(title="System Resources", expand=True)
            table.add_column("Resource", style="cyan", ratio=2)
            table.add_column("Usage", style="green", ratio=2)
            table.add_column("Progress", style="yellow", ratio=4)
            table.add_row("CPU", f"{cpu:.1f}%", format_progress_bar(cpu, 100.0))
            table.add_row("Memory", f"{memory:.1f}%", format_progress_bar(memory, 100.0))
            table.add_row("Disk", f"{disk:.1f}%", format_progress_bar(disk, 100.0))

            console = Console(file=StringIO(), width=80, height=20)
            console.print(Panel(table, title="System Resources", border_style="green"))
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error rendering system resources content: %s", e)
            return f"System Resources Error: {e}"

    def _render_network_content(
        self,
        stats: dict[str, Any],
        torrents: list[dict[str, Any]],
    ) -> str:  # pragma: no cover
        """Render network quality content from global stats and torrent list."""
        try:
            all_status = {t.get("info_hash", ""): t for t in torrents}

            from io import StringIO

            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            global_table = Table(
                title="Global Network Statistics",
                expand=True,
                show_header=False,
                box=None,
            )
            global_table.add_column("Metric", style="cyan", ratio=1)
            global_table.add_column("Value", style="green", ratio=2)

            def format_speed(s: float) -> str:
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            global_table.add_row("Total Torrents", str(stats.get("num_torrents", 0)))
            global_table.add_row("Active Torrents", str(stats.get("num_active", 0)))
            global_table.add_row("Total Download Rate", format_speed(stats.get("download_rate", 0.0)))
            global_table.add_row("Total Upload Rate", format_speed(stats.get("upload_rate", 0.0)))

            total_peers = 0
            total_seeds = 0
            for status in all_status.values():
                total_peers += status.get("connected_peers", 0)
                total_seeds += status.get("active_peers", 0)

            global_table.add_row("Total Peers", str(total_peers))
            global_table.add_row("Total Seeds", str(total_seeds))

            console = Console(file=StringIO(), width=80, height=15)
            console.print(Panel(global_table, title="Network Quality", border_style="blue"))
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error rendering network content: %s", e)
            return f"Network Quality Error: {e}"
