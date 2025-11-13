"""Queue metrics monitoring screen."""

from __future__ import annotations

import time
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


class QueueMetricsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display queue metrics (position, priority, waiting time)."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #queue_stats {
        height: 1fr;
        min-height: 10;
    }
    #queue_table {
        height: 1fr;
        min-height: 10;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the queue metrics screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="queue_stats")
            yield Static(id="queue_table")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh queue metrics display."""
        try:
            content = self.query_one("#content", Static)
            queue_stats = self.query_one("#queue_stats", Static)
            queue_table = self.query_one("#queue_table", Static)

            # Get queue manager from session
            queue_manager = None
            if hasattr(self.session, "queue_manager"):
                queue_manager = self.session.queue_manager

            if not queue_manager:
                content.update(
                    Panel(
                        "Queue manager not available. Queue management may be disabled in configuration.",
                        title="Queue Metrics",
                        border_style="yellow",
                    )
                )
                queue_stats.update("")
                queue_table.update("")
                return

            # Get queue status
            try:
                queue_status = await queue_manager.get_queue_status()
            except Exception as e:
                content.update(
                    Panel(
                        f"Error getting queue status: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                return

            statistics = queue_status.get("statistics", {})
            entries = queue_status.get("entries", [])

            # Display queue statistics
            stats_table = Table(title="Queue Statistics", expand=True)
            stats_table.add_column("Metric", style="cyan", ratio=2)
            stats_table.add_column("Value", style="green", ratio=2)
            stats_table.add_column("Description", style="dim", ratio=4)

            stats_table.add_row(
                "Total Torrents",
                str(statistics.get("total_torrents", 0)),
                "Total torrents in queue",
            )
            stats_table.add_row(
                "Active Downloading",
                str(statistics.get("active_downloading", 0)),
                "Currently downloading torrents",
            )
            stats_table.add_row(
                "Active Seeding",
                str(statistics.get("active_seeding", 0)),
                "Currently seeding torrents",
            )
            stats_table.add_row(
                "Queued", str(statistics.get("queued", 0)), "Torrents waiting in queue"
            )
            stats_table.add_row(
                "Paused", str(statistics.get("paused", 0)), "Paused torrents"
            )

            # Priority distribution
            by_priority = statistics.get("by_priority", {})
            if by_priority:
                stats_table.add_row("", "", "")  # Separator
                stats_table.add_row("[bold]By Priority[/bold]", "", "")
                priority_order = ["maximum", "high", "normal", "low", "paused"]
                for priority in priority_order:
                    count = by_priority.get(priority, 0)
                    if count > 0:
                        stats_table.add_row(
                            f"  {priority.capitalize()}",
                            str(count),
                            f"Torrents with {priority} priority",
                        )

            content.update(Panel(stats_table))

            # Display queue entries table
            if entries:
                entries_table = Table(title="Queue Entries", expand=True)
                entries_table.add_column("Position", style="cyan", ratio=1)
                entries_table.add_column("Torrent", style="green", ratio=3)
                entries_table.add_column("Priority", style="yellow", ratio=1)
                entries_table.add_column("Status", style="blue", ratio=1)
                entries_table.add_column("Waiting Time", style="magenta", ratio=2)
                entries_table.add_column("Allocated Down", style="dim", ratio=1)
                entries_table.add_column("Allocated Up", style="dim", ratio=1)

                current_time = time.time()

                for entry in entries:
                    info_hash_hex = entry.get("info_hash", "")
                    position = entry.get("queue_position", 0)
                    priority = entry.get("priority", "normal")
                    status = entry.get("status", "unknown")
                    added_time = entry.get("added_time", current_time)
                    allocated_down = entry.get("allocated_down_kib", 0)
                    allocated_up = entry.get("allocated_up_kib", 0)

                    # Calculate waiting time
                    waiting_seconds = current_time - added_time
                    if waiting_seconds < 60:
                        waiting_str = f"{int(waiting_seconds)}s"
                    elif waiting_seconds < 3600:
                        waiting_str = (
                            f"{int(waiting_seconds // 60)}m {int(waiting_seconds % 60)}s"
                        )
                    else:
                        hours = int(waiting_seconds // 3600)
                        minutes = int((waiting_seconds % 3600) // 60)
                        waiting_str = f"{hours}h {minutes}m"

                    # Get torrent name from session
                    torrent_name = info_hash_hex[:16] + "..."
                    try:
                        info_hash_bytes = bytes.fromhex(info_hash_hex)
                        torrent_session = self.session.torrents.get(info_hash_bytes)
                        if torrent_session and hasattr(torrent_session, "info"):
                            torrent_name = torrent_session.info.name[
                                :40
                            ]  # Truncate long names
                    except Exception:
                        pass

                    # Format priority with color
                    priority_colors = {
                        "maximum": "[bold red]",
                        "high": "[yellow]",
                        "normal": "[white]",
                        "low": "[dim]",
                        "paused": "[strike]",
                    }
                    priority_color = priority_colors.get(priority.lower(), "")
                    priority_display = f"{priority_color}{priority.capitalize()}[/]"

                    # Format status with color
                    status_colors = {
                        "active": "[green]",
                        "downloading": "[green]",
                        "seeding": "[cyan]",
                        "queued": "[yellow]",
                        "paused": "[dim]",
                    }
                    status_color = status_colors.get(status.lower(), "")
                    status_display = f"{status_color}{status.capitalize()}[/]"

                    # Format allocated bandwidth
                    down_str = f"{allocated_down} KiB/s" if allocated_down > 0 else "-"
                    up_str = f"{allocated_up} KiB/s" if allocated_up > 0 else "-"

                    entries_table.add_row(
                        str(position),
                        torrent_name,
                        priority_display,
                        status_display,
                        waiting_str,
                        down_str,
                        up_str,
                    )

                queue_table.update(Panel(entries_table))
            else:
                queue_table.update(
                    Panel(
                        "No torrents in queue.",
                        title="Queue Entries",
                        border_style="dim",
                    )
                )

            # Queue length summary
            queue_length = len(entries)
            queued_count = statistics.get("queued", 0)
            active_count = statistics.get("active_downloading", 0) + statistics.get(
                "active_seeding", 0
            )

            summary_table = Table(
                title="Queue Summary", expand=True, show_header=False, box=None
            )
            summary_table.add_column("Metric", style="cyan", ratio=1)
            summary_table.add_column("Value", style="green", ratio=2)

            summary_table.add_row("Queue Length", str(queue_length))
            summary_table.add_row("Queued (Waiting)", str(queued_count))
            summary_table.add_row("Active", str(active_count))

            # Calculate average waiting time
            if entries:
                waiting_times = [
                    time.time() - e.get("added_time", time.time())
                    for e in entries
                    if e.get("status") == "queued"
                ]
                if waiting_times:
                    avg_waiting = sum(waiting_times) / len(waiting_times)
                    if avg_waiting < 60:
                        avg_str = f"{int(avg_waiting)}s"
                    elif avg_waiting < 3600:
                        avg_str = f"{int(avg_waiting // 60)}m"
                    else:
                        avg_str = f"{int(avg_waiting // 3600)}h"
                    summary_table.add_row("Avg Waiting Time", avg_str)

            queue_stats.update(Panel(summary_table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading queue metrics: {e}",
                    title="Error",
                    border_style="red",
                )
            )

