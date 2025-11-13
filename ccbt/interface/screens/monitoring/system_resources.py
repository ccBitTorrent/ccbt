"""System resources monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Vertical
        from textual.widgets import (
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import MonitoringScreen


class SystemResourcesScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display system resource usage (CPU, memory, disk, network)."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #metrics_table {
        height: 1fr;
    }
    #network_info {
        height: 1fr;
        min-height: 5;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the system resources screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="network_info")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh system metrics display."""
        try:
            if not self.metrics_collector or not self.metrics_collector.running:
                content = self.query_one("#content", Static)
                content.update(
                    Panel(
                        "Metrics collector not running. Enable metrics in configuration.",
                        title="System Resources",
                        border_style="yellow",
                    )
                )
                return

            system_metrics = self.metrics_collector.get_system_metrics()
            content = self.query_one("#content", Static)
            network_info = self.query_one("#network_info", Static)

            # Create metrics table
            table = Table(title="System Resources", expand=True)
            table.add_column("Resource", style="cyan", ratio=2)
            table.add_column("Usage", style="green", ratio=2)
            table.add_column("Progress", style="yellow", ratio=4)

            # CPU
            cpu = system_metrics.get("cpu_usage", 0.0)
            cpu_bar = self._format_progress_bar(cpu, 100.0)
            table.add_row("CPU", f"{cpu:.1f}%", cpu_bar)

            # Memory
            memory = system_metrics.get("memory_usage", 0.0)
            mem_bar = self._format_progress_bar(memory, 100.0)
            table.add_row("Memory", f"{memory:.1f}%", mem_bar)

            # Disk
            disk = system_metrics.get("disk_usage", 0.0)
            disk_bar = self._format_progress_bar(disk, 100.0)
            table.add_row("Disk", f"{disk:.1f}%", disk_bar)

            # Process count
            process_count = system_metrics.get("process_count", 0)
            table.add_row("Processes", str(process_count), "")

            content.update(Panel(table))

            # Network I/O
            network_io = system_metrics.get("network_io", {})
            bytes_sent = network_io.get("bytes_sent", 0)
            bytes_recv = network_io.get("bytes_recv", 0)

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

            network_info.update(Panel(network_table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading system metrics: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    def _format_progress_bar(
        self, value: float, max_value: float = 100.0
    ) -> str:  # pragma: no cover
        """Create text progress bar.

        Args:
            value: Current value
            max_value: Maximum value

        Returns:
            Progress bar string
        """
        percentage = min(100.0, max(0.0, (value / max_value) * 100.0))
        bar_length = 30
        filled = int((percentage / 100.0) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"[{bar}] {percentage:.1f}%"
