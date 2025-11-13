"""Disk analysis monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Footer, Header, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import (
            Horizontal,
            Vertical,
        )
        from textual.widgets import (
            Button,
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Horizontal = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Button = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.config.config import get_config
from ccbt.config.config_capabilities import SystemCapabilities
from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import MonitoringScreen
from ccbt.storage.disk_io_init import get_disk_io_manager


class DiskAnalysisScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display disk analysis from disk-detect and disk-stats commands."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #detection_results {
        height: 1fr;
        min-height: 8;
    }
    #io_stats {
        height: 1fr;
        min-height: 8;
    }
    #recommendations {
        height: 1fr;
        min-height: 8;
    }
    #actions {
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the disk analysis screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="detection_results")
            yield Static(id="io_stats")
            yield Static(id="recommendations")
            with Horizontal(id="actions"):
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Run Detection", id="detect", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and initialize command executor."""
        # Initialize command executor
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh disk analysis display."""
        try:
            content = self.query_one("#content", Static)
            detection_results = self.query_one("#detection_results", Static)
            io_stats = self.query_one("#io_stats", Static)
            recommendations = self.query_one("#recommendations", Static)

            config = get_config()
            capabilities = SystemCapabilities()

            # Get download path
            download_path = config.disk.download_path or "."

            # Detect storage information
            storage_type = capabilities.detect_storage_type(download_path)
            storage_speed = capabilities.detect_storage_speed(download_path)
            write_cache = capabilities.detect_write_cache(download_path)

            # Display detection results
            detect_table = Table(
                title="Storage Device Detection",
                expand=True,
                show_header=False,
                box=None,
            )
            detect_table.add_column("Property", style="cyan", ratio=1)
            detect_table.add_column("Value", style="green", ratio=2)

            detect_table.add_row("Storage Type", storage_type.upper())
            detect_table.add_row(
                "Speed Category", storage_speed.get("speed_category", "unknown")
            )
            detect_table.add_row(
                "Estimated Read Speed",
                f"{storage_speed.get('estimated_read_mbps', 0):.0f} MB/s",
            )
            detect_table.add_row(
                "Estimated Write Speed",
                f"{storage_speed.get('estimated_write_mbps', 0):.0f} MB/s",
            )
            detect_table.add_row(
                "Write-Back Cache",
                "[green]Enabled[/green]" if write_cache else "[dim]Disabled[/dim]",
            )
            detect_table.add_row("Download Path", download_path)

            detection_results.update(Panel(detect_table))

            # Get disk I/O statistics
            try:
                disk_io = get_disk_io_manager()
                if disk_io and disk_io._running:  # type: ignore[attr-defined]
                    stats = disk_io.stats
                    cache_stats = disk_io.get_cache_stats()

                    io_table = Table(
                        title="Disk I/O Statistics",
                        expand=True,
                        show_header=False,
                        box=None,
                    )
                    io_table.add_column("Metric", style="cyan", ratio=1)
                    io_table.add_column("Value", style="green", ratio=2)

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

                    io_table.add_row("Total Writes", f"{stats.get('writes', 0):,}")
                    io_table.add_row(
                        "Bytes Written", format_bytes(stats.get("bytes_written", 0))
                    )
                    io_table.add_row(
                        "Queue Full Errors", f"{stats.get('queue_full_errors', 0):,}"
                    )
                    io_table.add_row(
                        "Preallocations", f"{stats.get('preallocations', 0):,}"
                    )

                    # Cache statistics
                    cache_entries = cache_stats.get("entries", 0)
                    cache_total_size = cache_stats.get("total_size", 0)
                    cache_hits = cache_stats.get("cache_hits", 0)
                    cache_misses = cache_stats.get("cache_misses", 0)
                    hit_rate = cache_stats.get("hit_rate_percent", 0.0)

                    io_table.add_row("", "")  # Separator
                    io_table.add_row("[bold]Cache Statistics[/bold]", "")
                    io_table.add_row("Cache Entries", f"{cache_entries:,}")
                    io_table.add_row("Cache Size", format_bytes(cache_total_size))
                    io_table.add_row("Cache Hits", f"{cache_hits:,}")
                    io_table.add_row("Cache Misses", f"{cache_misses:,}")
                    io_table.add_row("Hit Rate", f"{hit_rate:.2f}%")

                    io_stats.update(Panel(io_table))
                else:
                    io_stats.update(
                        Panel(
                            "Disk I/O manager not running. Start it to collect statistics.",
                            title="Disk I/O Statistics",
                            border_style="yellow",
                        )
                    )
            except Exception as e:
                io_stats.update(
                    Panel(
                        f"Error getting disk I/O stats: {e}",
                        title="Error",
                        border_style="red",
                    )
                )

            # Show recommendations based on storage type
            rec_table = Table(title="Recommended Settings", expand=True)
            rec_table.add_column("Setting", style="cyan", ratio=2)
            rec_table.add_column("Recommended", style="green", ratio=2)
            rec_table.add_column("Current", style="yellow", ratio=2)

            if storage_type == "nvme":
                rec_table.add_row(
                    "Write Batch Timeout",
                    "0.1 ms (adaptive)",
                    f"{config.disk.write_batch_timeout_ms} ms",
                )
                rec_table.add_row("Disk Workers", "4-8", str(config.disk.disk_workers))
                rec_table.add_row(
                    "Hash Chunk Size",
                    "1 MB (adaptive)",
                    f"{config.disk.hash_chunk_size // 1024} KB",
                )
            elif storage_type == "ssd":
                rec_table.add_row(
                    "Write Batch Timeout",
                    "5 ms (adaptive)",
                    f"{config.disk.write_batch_timeout_ms} ms",
                )
                rec_table.add_row("Disk Workers", "2-4", str(config.disk.disk_workers))
                rec_table.add_row(
                    "Hash Chunk Size",
                    "512 KB (adaptive)",
                    f"{config.disk.hash_chunk_size // 1024} KB",
                )
            else:  # hdd
                rec_table.add_row(
                    "Write Batch Timeout",
                    "50 ms (adaptive)",
                    f"{config.disk.write_batch_timeout_ms} ms",
                )
                rec_table.add_row("Disk Workers", "1-2", str(config.disk.disk_workers))
                rec_table.add_row(
                    "Hash Chunk Size",
                    "64 KB (adaptive)",
                    f"{config.disk.hash_chunk_size // 1024} KB",
                )

            # Add adaptive configuration status
            rec_table.add_row("", "", "")  # Separator
            rec_table.add_row("[bold]Adaptive Features[/bold]", "", "")
            rec_table.add_row(
                "Write Batch Timeout Adaptive",
                "[green]Recommended[/green]",
                "[green]Enabled[/green]"
                if config.disk.write_batch_timeout_adaptive
                else "[dim]Disabled[/dim]",
            )
            rec_table.add_row(
                "MMap Cache Adaptive",
                "[green]Recommended[/green]",
                "[green]Enabled[/green]"
                if config.disk.mmap_cache_adaptive
                else "[dim]Disabled[/dim]",
            )
            rec_table.add_row(
                "Disk Workers Adaptive",
                "[green]Recommended[/green]",
                "[green]Enabled[/green]"
                if config.disk.disk_workers_adaptive
                else "[dim]Disabled[/dim]",
            )
            rec_table.add_row(
                "Read Ahead Adaptive",
                "[green]Recommended[/green]",
                "[green]Enabled[/green]"
                if config.disk.read_ahead_adaptive
                else "[dim]Disabled[/dim]",
            )
            rec_table.add_row(
                "Hash Chunk Size Adaptive",
                "[green]Recommended[/green]",
                "[green]Enabled[/green]"
                if config.disk.hash_chunk_size_adaptive
                else "[dim]Disabled[/dim]",
            )

            recommendations.update(Panel(rec_table))

            content.update(
                Panel(
                    f"Disk analysis complete. Detected storage type: {storage_type.upper()}. Review detection results, I/O statistics, and recommendations below.",
                    title="Disk Analysis",
                    border_style="green",
                )
            )

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading disk analysis: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "refresh":
            await self._refresh_data()
        elif event.button.id == "detect":
            await self._run_detection()

    async def _run_detection(self) -> None:  # pragma: no cover
        """Run storage device detection."""
        content = self.query_one("#content", Static)
        content.update(
            Panel(
                "Running storage device detection...",
                title="Detection",
                border_style="yellow",
            )
        )

        try:
            if not hasattr(self, "_command_executor") or self._command_executor is None:
                self._command_executor = CommandExecutor(self.session)

            # Execute disk-detect command
            success, output, _ = await self._command_executor.execute_click_command(
                "disk-detect", []
            )

            if success:
                content.update(
                    Panel(
                        f"Detection completed:\n\n{output}",
                        title="Detection Results",
                        border_style="green",
                    )
                )
            else:
                content.update(
                    Panel(
                        f"Detection failed: {output}",
                        title="Error",
                        border_style="red",
                    )
                )
            # Refresh data to update display
            await self._refresh_data()
        except Exception as e:
            content.update(
                Panel(
                    f"Error running detection: {e}",
                    title="Error",
                    border_style="red",
                )
            )

