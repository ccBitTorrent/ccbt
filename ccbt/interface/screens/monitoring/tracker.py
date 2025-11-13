"""Tracker metrics monitoring screen."""

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


class TrackerMetricsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display tracker metrics (announce/scrape success rates, response times)."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #tracker_stats {
        height: 1fr;
        min-height: 10;
    }
    #tracker_sessions {
        height: 1fr;
        min-height: 10;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the tracker metrics screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="tracker_stats")
            yield Static(id="tracker_sessions")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh tracker metrics display."""
        try:
            content = self.query_one("#content", Static)
            tracker_stats = self.query_one("#tracker_stats", Static)
            tracker_sessions = self.query_one("#tracker_sessions", Static)

            # Get tracker client from session
            tracker_client = None
            if hasattr(self.session, "tracker"):
                tracker_client = self.session.tracker
            elif hasattr(self.session, "tracker_client"):
                tracker_client = self.session.tracker_client

            if not tracker_client:
                content.update(
                    Panel(
                        "Tracker client not available. Tracker may not be initialized.",
                        title="Tracker Metrics",
                        border_style="yellow",
                    )
                )
                tracker_stats.update("")
                tracker_sessions.update("")
                return

            # Get session statistics
            try:
                session_stats = tracker_client.get_session_stats()
            except Exception as e:
                content.update(
                    Panel(
                        f"Error getting tracker stats: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                return

            # Get tracker sessions
            sessions = getattr(tracker_client, "sessions", {})

            # Display tracker statistics
            if session_stats:
                stats_table = Table(title="Tracker Statistics", expand=True)
                stats_table.add_column("Tracker", style="cyan", ratio=3)
                stats_table.add_column("Requests", style="green", ratio=1)
                stats_table.add_column("Avg Response", style="yellow", ratio=1)
                stats_table.add_column("Error Rate", style="red", ratio=1)
                stats_table.add_column("Connection Reuse", style="blue", ratio=1)

                for host, stats in session_stats.items():
                    request_count = stats.get("request_count", 0)
                    avg_response = stats.get("average_request_time", 0.0)
                    error_rate = stats.get("error_rate", 0.0)
                    conn_reuse = stats.get("connection_reuse_rate", 0.0)

                    # Format response time
                    if avg_response < 0.001:
                        response_str = f"{avg_response * 1000:.2f} ms"
                    else:
                        response_str = f"{avg_response:.3f} s"

                    # Color code error rate
                    if error_rate == 0:
                        error_display = "[green]0.00%[/green]"
                    elif error_rate < 10:
                        error_display = f"[yellow]{error_rate:.2f}%[/yellow]"
                    else:
                        error_display = f"[red]{error_rate:.2f}%[/red]"

                    stats_table.add_row(
                        host,
                        f"{request_count:,}",
                        response_str,
                        error_display,
                        f"{conn_reuse:.1f}%",
                    )

                content.update(Panel(stats_table))
            else:
                content.update(
                    Panel(
                        "No tracker statistics available yet. Trackers will be queried as torrents are added.",
                        title="Tracker Statistics",
                        border_style="dim",
                    )
                )

            # Display tracker sessions
            if sessions:
                sessions_table = Table(title="Tracker Sessions", expand=True)
                sessions_table.add_column("URL", style="cyan", ratio=3)
                sessions_table.add_column("Last Announce", style="green", ratio=2)
                sessions_table.add_column("Interval", style="yellow", ratio=1)
                sessions_table.add_column("Failures", style="red", ratio=1)
                sessions_table.add_column("Status", style="blue", ratio=1)

                current_time = time.time()

                for url, session in sessions.items():
                    last_announce = session.last_announce
                    interval = session.interval
                    failure_count = session.failure_count
                    backoff_delay = session.backoff_delay

                    # Calculate time since last announce
                    if last_announce > 0:
                        time_since = current_time - last_announce
                        if time_since < 60:
                            last_str = f"{int(time_since)}s ago"
                        elif time_since < 3600:
                            last_str = f"{int(time_since // 60)}m ago"
                        else:
                            hours = int(time_since // 3600)
                            last_str = f"{hours}h ago"
                    else:
                        last_str = "Never"

                    # Format interval
                    if interval < 60:
                        interval_str = f"{interval}s"
                    else:
                        interval_str = f"{interval // 60}m"

                    # Determine status
                    if failure_count == 0:
                        status = "[green]Healthy[/green]"
                    elif failure_count < 3:
                        status = "[yellow]Degraded[/yellow]"
                    else:
                        status = "[red]Failed[/red]"

                    # Show backoff if active
                    if backoff_delay > 1.0:
                        status += f" (backoff: {backoff_delay:.1f}s)"

                    sessions_table.add_row(
                        url,
                        last_str,
                        interval_str,
                        str(failure_count),
                        status,
                    )

                tracker_sessions.update(Panel(sessions_table))
            else:
                tracker_sessions.update(
                    Panel(
                        "No active tracker sessions.",
                        title="Tracker Sessions",
                        border_style="dim",
                    )
                )

            # Summary statistics
            if session_stats:
                total_requests = sum(
                    s.get("request_count", 0) for s in session_stats.values()
                )
                total_errors = sum(
                    int(s.get("request_count", 0) * s.get("error_rate", 0) / 100)
                    for s in session_stats.values()
                )
                avg_response_all = (
                    sum(
                        s.get("average_request_time", 0.0)
                        for s in session_stats.values()
                    )
                    / len(session_stats)
                    if session_stats
                    else 0.0
                )
                success_rate = (
                    ((total_requests - total_errors) / total_requests * 100)
                    if total_requests > 0
                    else 0.0
                )

                summary_table = Table(
                    title="Summary", expand=True, show_header=False, box=None
                )
                summary_table.add_column("Metric", style="cyan", ratio=1)
                summary_table.add_column("Value", style="green", ratio=2)

                summary_table.add_row("Total Trackers", str(len(session_stats)))
                summary_table.add_row("Total Requests", f"{total_requests:,}")
                summary_table.add_row("Total Errors", f"{total_errors:,}")
                summary_table.add_row("Success Rate", f"{success_rate:.2f}%")
                summary_table.add_row(
                    "Avg Response Time", f"{avg_response_all * 1000:.2f} ms"
                )

                tracker_stats.update(Panel(summary_table))
            else:
                tracker_stats.update("")

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading tracker metrics: {e}",
                    title="Error",
                    border_style="red",
                )
            )

