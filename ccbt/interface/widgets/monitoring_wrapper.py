"""Wrapper widget to embed monitoring screens in the graphs section.

This allows existing MonitoringScreen classes to be used within the
tabbed interface graphs section without requiring full screen push.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from textual.containers import Container, Vertical
    from textual.widgets import Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class MonitoringScreenWrapper(Container):  # type: ignore[misc]
    """Wrapper to embed monitoring screen content in a container widget.
    
    This extracts the content from existing MonitoringScreen classes
    and displays it within the graphs section without requiring a full screen push.
    """

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
        """Mount the monitoring wrapper and start refresh."""
        try:
            self._content_widget = self.query_one("#monitoring-placeholder", Static)  # type: ignore[attr-defined]
            # Content is refreshed via DataProvider only (no Screen instances)
            self.set_interval(2.0, self._refresh_content)  # type: ignore[attr-defined]
            self.call_later(self._refresh_content)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting monitoring wrapper: %s", e)

    async def _refresh_content(self) -> None:  # pragma: no cover
        """Refresh the monitoring content.
        
        Note: We can't directly mount Screen classes in containers.
        Instead, we extract the data and render it ourselves using the
        same logic as the monitoring screens, but without Header/Footer.
        """
        if not self._content_widget:
            return
        
        try:
            # Get monitoring content using the same data fetching logic
            # as the monitoring screens, but render it in our container
            content = await self._get_monitoring_content()
            if content:
                self._content_widget.update(content)
            else:
                self._content_widget.update(f"Monitoring: {self._screen_type}\n\nLoading metrics...")
        except Exception as e:
            logger.debug("Error refreshing monitoring content: %s", e)
            if self._content_widget:
                self._content_widget.update(f"Error loading {self._screen_type}: {e}")

    async def _get_monitoring_content(self) -> Optional[str]:  # pragma: no cover
        """Get monitoring content based on screen type.

        Returns:
            Formatted content string or None
        """
        try:
            if self._screen_type == "disk_io":
                return await self._get_disk_io_content()
            elif self._screen_type == "system_resources":
                return await self._get_system_resources_content()
            elif self._screen_type == "network":
                return await self._get_network_content()
            else:
                return f"Monitoring: {self._screen_type}"
        except Exception as e:
            logger.debug("Error getting monitoring content: %s", e)
            return None

    async def _get_disk_io_content(self) -> str:  # pragma: no cover
        """Get disk I/O metrics content from DataProvider (daemon or local)."""
        try:
            if not self._data_provider:
                return "Data provider not available."
            metrics = await self._data_provider.get_disk_io_metrics()
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
            logger.debug("Error getting disk I/O content: %s", e)
            return f"Disk I/O Error: {e}"

    async def _get_system_resources_content(self) -> str:  # pragma: no cover
        """Get system resources content from DataProvider (daemon or local)."""
        try:
            if not self._data_provider:
                return "Data provider not available."
            metrics = await self._data_provider.get_system_metrics()
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
            logger.debug("Error getting system resources content: %s", e)
            return f"System Resources Error: {e}"

    async def _get_network_content(self) -> str:  # pragma: no cover
        """Get network quality content.
        
        Uses the same logic as NetworkQualityScreen._refresh_data() but
        renders to a string for display in our container widget.
        """
        try:
            # CRITICAL: Use DataProvider instead of direct session access
            stats = await self._data_provider.get_global_stats()
            # Get all torrents status
            torrents = await self._data_provider.list_torrents()
            # Convert to dict format expected by monitoring screens
            all_status = {t.get("info_hash", ""): t for t in torrents}
            
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from io import StringIO
            
            # Global network stats table (matching NetworkQualityScreen format)
            global_table = Table(
                title="Global Network Statistics",
                expand=True,
                show_header=False,
                box=None,
            )
            global_table.add_column("Metric", style="cyan", ratio=1)
            global_table.add_column("Value", style="green", ratio=2)
            
            def format_speed(s: float) -> str:
                """Format speed (matching NetworkQualityScreen)."""
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"
            
            global_table.add_row("Total Torrents", str(stats.get("num_torrents", 0)))
            global_table.add_row("Active Torrents", str(stats.get("num_active", 0)))
            global_table.add_row("Total Download Rate", format_speed(stats.get("total_download_rate", 0.0)))
            global_table.add_row("Total Upload Rate", format_speed(stats.get("total_upload_rate", 0.0)))
            
            # Calculate peer statistics
            total_peers = 0
            total_seeds = 0
            for status in all_status.values():
                total_peers += status.get("connected_peers", status.get("num_peers", 0))
                total_seeds += status.get("active_peers", status.get("num_seeds", 0))
            
            global_table.add_row("Total Peers", str(total_peers))
            global_table.add_row("Total Seeds", str(total_seeds))
            
            # Render table
            console = Console(file=StringIO(), width=80, height=15)
            console.print(Panel(global_table, title="Network Quality", border_style="blue"))
            
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error getting network content: %s", e)
            return f"Network Quality Error: {e}"

