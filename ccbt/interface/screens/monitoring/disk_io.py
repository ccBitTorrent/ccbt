"""Disk I/O metrics monitoring screen."""

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


class DiskIOMetricsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display disk I/O statistics (throughput, queue depth, cache stats)."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #io_stats {
        height: 1fr;
        min-height: 10;
    }
    #cache_stats {
        height: 1fr;
        min-height: 10;
    }
    #config_info {
        height: 1fr;
        min-height: 8;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the disk I/O metrics screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="io_stats")
            yield Static(id="cache_stats")
            yield Static(id="config_info")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh disk I/O metrics display."""
        try:
            from ccbt.storage.disk_io_init import get_disk_io_manager

            content = self.query_one("#content", Static)
            io_stats = self.query_one("#io_stats", Static)
            cache_stats = self.query_one("#cache_stats", Static)
            config_info = self.query_one("#config_info", Static)

            # Get disk I/O manager
            try:
                disk_io = get_disk_io_manager()
            except Exception as e:
                content.update(
                    Panel(
                        f"Disk I/O manager not available: {e}\n\n"
                        "Disk I/O manager may not be initialized.",
                        title="Disk I/O Metrics",
                        border_style="yellow",
                    )
                )
                io_stats.update("")
                cache_stats.update("")
                config_info.update("")
                return

            if not disk_io or not disk_io._running:  # type: ignore[attr-defined]
                content.update(
                    Panel(
                        "Disk I/O manager is not running. Start it to collect metrics.",
                        title="Disk I/O Metrics",
                        border_style="yellow",
                    )
                )
                io_stats.update("")
                cache_stats.update("")
                config_info.update("")
                return

            # Get I/O statistics
            stats = disk_io.stats
            cache_stats_data = disk_io.get_cache_stats()

            # Display I/O statistics
            io_table = Table(title="Disk I/O Statistics", expand=True)
            io_table.add_column("Metric", style="cyan", ratio=2)
            io_table.add_column("Value", style="green", ratio=2)
            io_table.add_column("Description", style="dim", ratio=4)

            # Write statistics
            writes = stats.get("writes", 0)
            bytes_written = stats.get("bytes_written", 0)
            queue_full_errors = stats.get("queue_full_errors", 0)
            preallocations = stats.get("preallocations", 0)

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

            io_table.add_row(
                "Total Writes", f"{writes:,}", "Number of write operations"
            )
            io_table.add_row(
                "Bytes Written",
                format_bytes(bytes_written),
                "Total bytes written to disk",
            )
            io_table.add_row(
                "Queue Full Errors",
                f"{queue_full_errors:,}",
                "Times write queue was full",
            )
            io_table.add_row(
                "Preallocations", f"{preallocations:,}", "File preallocation operations"
            )

            # Advanced I/O features
            io_uring_ops = stats.get("io_uring_operations", 0)
            direct_io_ops = stats.get("direct_io_operations", 0)
            nvme_optimizations = stats.get("nvme_optimizations", 0)

            if io_uring_ops > 0:
                io_table.add_row(
                    "io_uring Operations",
                    f"{io_uring_ops:,}",
                    "Operations using io_uring",
                )
            if direct_io_ops > 0:
                io_table.add_row(
                    "Direct I/O Operations",
                    f"{direct_io_ops:,}",
                    "Operations using O_DIRECT",
                )
            if nvme_optimizations > 0:
                io_table.add_row(
                    "NVMe Optimizations",
                    f"{nvme_optimizations:,}",
                    "NVMe-specific optimizations",
                )

            # Queue depth (approximate from queue size)
            queue_size = getattr(disk_io, "queue_size", 0)
            if hasattr(disk_io, "write_queue") and disk_io.write_queue:
                try:
                    queue_depth = disk_io.write_queue.qsize()
                    io_table.add_row(
                        "Queue Depth",
                        f"{queue_depth}/{queue_size}",
                        "Current queue depth / max size",
                    )
                except Exception:
                    pass

            content.update(Panel(io_table))

            # Display cache statistics
            cache_table = Table(title="Cache Statistics", expand=True)
            cache_table.add_column("Metric", style="cyan", ratio=2)
            cache_table.add_column("Value", style="green", ratio=2)
            cache_table.add_column("Description", style="dim", ratio=4)

            cache_entries = cache_stats_data.get("entries", 0)
            cache_total_size = cache_stats_data.get("total_size", 0)
            cache_hits = cache_stats_data.get("cache_hits", 0)
            cache_misses = cache_stats_data.get("cache_misses", 0)
            cache_evictions = cache_stats_data.get("cache_evictions", 0)
            hit_rate = cache_stats_data.get("hit_rate_percent", 0.0)
            eviction_rate = cache_stats_data.get("eviction_rate_per_sec", 0.0)
            cache_efficiency = cache_stats_data.get("cache_efficiency_percent", 0.0)
            total_accesses = cache_stats_data.get("total_accesses", 0)
            bytes_served = cache_stats_data.get("cache_bytes_served", 0)

            cache_table.add_row(
                "Cache Entries", f"{cache_entries:,}", "Number of cached files"
            )
            cache_table.add_row(
                "Cache Size",
                format_bytes(cache_total_size),
                "Total size of cached data",
            )
            cache_table.add_row(
                "Cache Hits", f"{cache_hits:,}", "Successful cache lookups"
            )
            cache_table.add_row(
                "Cache Misses", f"{cache_misses:,}", "Failed cache lookups"
            )
            cache_table.add_row(
                "Total Accesses", f"{total_accesses:,}", "Total cache access attempts"
            )
            cache_table.add_row("Hit Rate", f"{hit_rate:.2f}%", "Cache hit percentage")
            cache_table.add_row(
                "Bytes Served", format_bytes(bytes_served), "Bytes served from cache"
            )
            cache_table.add_row(
                "Cache Efficiency",
                f"{cache_efficiency:.2f}%",
                "Cache efficiency percentage",
            )
            cache_table.add_row(
                "Evictions", f"{cache_evictions:,}", "Cache entries evicted"
            )
            if eviction_rate > 0:
                cache_table.add_row(
                    "Eviction Rate",
                    f"{eviction_rate:.2f} /sec",
                    "Cache evictions per second",
                )

            cache_stats.update(Panel(cache_table))

            # Display configuration information
            config_table = Table(
                title="Disk I/O Configuration", expand=True, show_header=False, box=None
            )
            config_table.add_column("Setting", style="cyan", ratio=1)
            config_table.add_column("Value", style="green", ratio=2)

            config_table.add_row("Max Workers", str(getattr(disk_io, "max_workers", 0)))
            config_table.add_row("Queue Size", str(getattr(disk_io, "queue_size", 0)))
            config_table.add_row(
                "Cache Size", f"{getattr(disk_io, 'cache_size_mb', 0)} MB"
            )
            config_table.add_row(
                "Storage Type", getattr(disk_io, "storage_type", "unknown").upper()
            )
            config_table.add_row(
                "io_uring Enabled",
                "Yes" if getattr(disk_io, "io_uring_enabled", False) else "No",
            )
            config_table.add_row(
                "Direct I/O Enabled",
                "Yes" if getattr(disk_io, "direct_io_enabled", False) else "No",
            )
            config_table.add_row(
                "NVMe Optimized",
                "Yes" if getattr(disk_io, "nvme_optimized", False) else "No",
            )
            config_table.add_row(
                "Write Cache Enabled",
                "Yes" if getattr(disk_io, "write_cache_enabled", True) else "No",
            )

            # Adaptive configuration status
            if (
                hasattr(disk_io, "_worker_adjustment_task")
                and disk_io._worker_adjustment_task
            ):
                config_table.add_row("Adaptive Workers", "[green]Active[/green]")
            else:
                config_table.add_row("Adaptive Workers", "[dim]Inactive[/dim]")

            config_info.update(Panel(config_table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading disk I/O metrics: {e}",
                    title="Error",
                    border_style="red",
                )
            )

