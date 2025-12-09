"""Wrapper widget to embed monitoring screens in the graphs section.

This allows existing MonitoringScreen classes to be used within the
tabbed interface graphs section without requiring full screen push.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        AsyncSessionManager = None  # type: ignore[assignment, misc]

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
        self._content_widget: Static | None = None
        self._monitoring_screen: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the monitoring wrapper."""
        with Vertical(id="monitoring-content"):
            yield Static("Loading...", id="monitoring-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the monitoring wrapper and start refresh."""
        try:
            self._content_widget = self.query_one("#monitoring-placeholder", Static)  # type: ignore[attr-defined]
            
            # Create appropriate monitoring screen instance
            self._monitoring_screen = self._create_monitoring_screen()
            
            # Start periodic refresh
            self.set_interval(2.0, self._refresh_content)  # type: ignore[attr-defined]
            # Initial refresh
            self.call_later(self._refresh_content)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting monitoring wrapper: %s", e)

    def _create_monitoring_screen(self) -> Any:  # pragma: no cover
        """Create the appropriate monitoring screen instance.

        Note: We don't actually mount the Screen - we just use it to call
        its _refresh_data method and extract content. Screens are meant
        to be pushed as full overlays, not embedded in containers.

        Returns:
            MonitoringScreen instance (for method calls only, not for mounting)
        """
        screen_map = {
            "disk_io": "DiskIOMetricsScreen",
            "system_resources": "SystemResourcesScreen",
            "network": "NetworkQualityScreen",
            "performance": "PerformanceMetricsScreen",
            "queue": "QueueMetricsScreen",
            "tracker": "TrackerMetricsScreen",
        }
        
        screen_class_name = screen_map.get(self._screen_type)
        if not screen_class_name:
            logger.warning("Unknown monitoring screen type: %s", self._screen_type)
            return None
        
        try:
            # Import the screen class
            # Note: We create the instance but don't mount it as a Screen
            # Instead, we call its methods to get data and render it ourselves
            if screen_class_name == "DiskIOMetricsScreen":
                from ccbt.interface.screens.monitoring.disk_io import DiskIOMetricsScreen
                return DiskIOMetricsScreen(self._session, refresh_interval=2.0)
            elif screen_class_name == "SystemResourcesScreen":
                from ccbt.interface.screens.monitoring.system_resources import SystemResourcesScreen
                return SystemResourcesScreen(self._session, refresh_interval=2.0)
            elif screen_class_name == "NetworkQualityScreen":
                from ccbt.interface.screens.monitoring.network import NetworkQualityScreen
                return NetworkQualityScreen(self._session, refresh_interval=2.0)
            elif screen_class_name == "PerformanceMetricsScreen":
                from ccbt.interface.screens.monitoring.performance import PerformanceMetricsScreen
                return PerformanceMetricsScreen(self._session, refresh_interval=2.0)
            elif screen_class_name == "QueueMetricsScreen":
                from ccbt.interface.screens.monitoring.queue import QueueMetricsScreen
                return QueueMetricsScreen(self._session, refresh_interval=2.0)
            elif screen_class_name == "TrackerMetricsScreen":
                from ccbt.interface.screens.monitoring.tracker import TrackerMetricsScreen
                return TrackerMetricsScreen(self._session, refresh_interval=2.0)
        except Exception as e:
            logger.debug("Error creating monitoring screen: %s", e)
            return None

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

    async def _get_monitoring_content(self) -> str | None:  # pragma: no cover
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
        """Get disk I/O metrics content.
        
        Uses the same logic as DiskIOMetricsScreen._refresh_data() but
        renders to a string for display in our container widget.
        """
        try:
            from ccbt.storage.disk_io_init import get_disk_io_manager
            
            # Get disk I/O manager (same as DiskIOMetricsScreen)
            try:
                disk_io = get_disk_io_manager()
            except Exception as e:
                return f"Disk I/O manager not available: {e}"
            
            # Get stats (matching DiskIOMetricsScreen logic)
            # DiskIOMetricsScreen uses disk_io.stats and disk_io.get_cache_stats()
            stats = disk_io.stats  # type: ignore[attr-defined]
            cache_stats_data = disk_io.get_cache_stats()  # type: ignore[attr-defined]
            
            # Extract I/O stats
            writes = stats.get("writes", 0)
            bytes_written = stats.get("bytes_written", 0)
            read_throughput = stats.get("read_throughput", 0.0)
            write_throughput = stats.get("write_throughput", 0.0)
            queue_depth = stats.get("queue_depth", 0)
            
            # Extract cache stats
            cache_entries = cache_stats_data.get("entries", 0)
            cache_total_size = cache_stats_data.get("total_size", 0)
            cache_hits = cache_stats_data.get("cache_hits", 0)
            cache_misses = cache_stats_data.get("cache_misses", 0)
            
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from io import StringIO
            
            # I/O Stats table (matching DiskIOMetricsScreen format)
            io_table = Table(title="Disk I/O Statistics", expand=True, show_header=True)
            io_table.add_column("Metric", style="cyan", ratio=1)
            io_table.add_column("Value", style="green", ratio=2)
            
            def format_speed(bps: float) -> str:
                """Format bytes per second."""
                for unit, factor in [("GB/s", 1024**3), ("MB/s", 1024**2), ("KB/s", 1024)]:
                    if bps >= factor:
                        return f"{bps / factor:.2f} {unit}"
                return f"{bps:.2f} B/s"
            
            io_table.add_row("Read Throughput", format_speed(read_throughput))
            io_table.add_row("Write Throughput", format_speed(write_throughput))
            io_table.add_row("Queue Depth", str(queue_depth))
            
            # Cache Stats table
            cache_table = Table(title="Cache Statistics", expand=True, show_header=True)
            cache_table.add_column("Metric", style="cyan", ratio=1)
            cache_table.add_column("Value", style="green", ratio=2)
            
            def format_bytes(b: float) -> str:
                """Format bytes in human-readable format."""
                b_int = int(b)
                if b_int >= 1024 * 1024 * 1024:
                    return f"{b_int / (1024**3):.2f} GB"
                if b_int >= 1024 * 1024:
                    return f"{b_int / (1024**2):.2f} MB"
                if b_int >= 1024:
                    return f"{b_int / 1024:.2f} KB"
                return f"{b_int} B"
            
            cache_table.add_row("Cache Entries", f"{cache_entries:,}")
            cache_table.add_row("Cache Size", format_bytes(cache_total_size))
            cache_table.add_row("Cache Hits", f"{cache_hits:,}")
            cache_table.add_row("Cache Misses", f"{cache_misses:,}")
            
            # Calculate hit rate if available
            total_accesses = cache_hits + cache_misses
            if total_accesses > 0:
                hit_rate = (cache_hits / total_accesses) * 100.0
                cache_table.add_row("Hit Rate", f"{hit_rate:.1f}%")
            
            # Render both tables
            console = Console(file=StringIO(), width=80, height=20)
            console.print(Panel(io_table, title="Disk I/O", border_style="blue"))
            console.print()
            console.print(Panel(cache_table, title="Cache", border_style="green"))
            
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error getting disk I/O content: %s", e)
            return f"Disk I/O Error: {e}"

    async def _get_system_resources_content(self) -> str:  # pragma: no cover
        """Get system resources content.
        
        Uses the same logic as SystemResourcesScreen._refresh_data() but
        renders to a string for display in our container widget.
        """
        try:
            from ccbt.monitoring import get_metrics_collector
            metrics_collector = get_metrics_collector()
            
            if not metrics_collector or not metrics_collector.running:
                from rich.panel import Panel
                from rich.console import Console
                from io import StringIO
                console = Console(file=StringIO(), width=60, height=5)
                console.print(Panel(
                    "Metrics collector not running. Enable metrics in configuration.",
                    title="System Resources",
                    border_style="yellow",
                ))
                return console.file.getvalue()  # type: ignore[attr-defined]
            
            system_metrics = metrics_collector.get_system_metrics()
            cpu = system_metrics.get("cpu_usage", 0.0)
            memory = system_metrics.get("memory_usage", 0.0)
            disk = system_metrics.get("disk_usage", 0.0)
            process_count = system_metrics.get("process_count", 0)
            
            # Network I/O
            network_io = system_metrics.get("network_io", {})
            bytes_sent = network_io.get("bytes_sent", 0)
            bytes_recv = network_io.get("bytes_recv", 0)
            
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from io import StringIO
            
            # Main metrics table (matching SystemResourcesScreen format)
            table = Table(title="System Resources", expand=True)
            table.add_column("Resource", style="cyan", ratio=2)
            table.add_column("Usage", style="green", ratio=2)
            table.add_column("Progress", style="yellow", ratio=4)
            
            def format_progress_bar(value: float, max_value: float = 100.0) -> str:
                """Create text progress bar (matching SystemResourcesScreen)."""
                percentage = min(100.0, max(0.0, (value / max_value) * 100.0))
                bar_length = 30
                filled = int((percentage / 100.0) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                return f"[{bar}] {percentage:.1f}%"
            
            table.add_row("CPU", f"{cpu:.1f}%", format_progress_bar(cpu, 100.0))
            table.add_row("Memory", f"{memory:.1f}%", format_progress_bar(memory, 100.0))
            table.add_row("Disk", f"{disk:.1f}%", format_progress_bar(disk, 100.0))
            table.add_row("Processes", str(process_count), "")
            
            # Network I/O table
            network_table = Table(
                title="Network I/O", expand=True, show_header=False, box=None
            )
            network_table.add_column("Direction", style="cyan", ratio=1)
            network_table.add_column("Bytes", style="green", ratio=2)
            network_table.add_column("Formatted", style="dim", ratio=2)
            
            def format_bytes(b: float) -> str:
                """Format bytes to human-readable format."""
                b_float = float(b)
                for unit in ["B", "KB", "MB", "GB", "TB"]:
                    if b_float < 1024.0:
                        return f"{b_float:.2f} {unit}"
                    b_float /= 1024.0
                return f"{b_float:.2f} PB"
            
            network_table.add_row("Sent", str(bytes_sent), format_bytes(bytes_sent))
            network_table.add_row("Received", str(bytes_recv), format_bytes(bytes_recv))
            
            # Render both tables
            console = Console(file=StringIO(), width=80, height=20)
            console.print(Panel(table, title="System Resources"))
            console.print()
            console.print(Panel(network_table, title="Network I/O"))
            
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
                total_peers += status.get("num_peers", 0)
                total_seeds += status.get("num_seeds", 0)
            
            global_table.add_row("Total Peers", str(total_peers))
            global_table.add_row("Total Seeds", str(total_seeds))
            
            # Render table
            console = Console(file=StringIO(), width=80, height=15)
            console.print(Panel(global_table, title="Network Quality", border_style="blue"))
            
            return console.file.getvalue()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error getting network content: %s", e)
            return f"Network Quality Error: {e}"

