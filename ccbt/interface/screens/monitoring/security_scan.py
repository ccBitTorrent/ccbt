"""Security scan monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

from ccbt.i18n import _
from ccbt.interface.screens.base import MonitoringScreen


class SecurityScanScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display security scan results and statistics."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #security_stats {
        height: 1fr;
        min-height: 5;
    }
    #security_events {
        height: 1fr;
    }
    #blacklist_info {
        height: 1fr;
        min-height: 5;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the security scan screen."""
        yield Header()
        with Vertical():
            yield Static(id="security_stats")
            yield Static(id="blacklist_info")
            yield Static(id="content")
            yield Static(id="security_events")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh security scan metrics display."""
        try:
            security_stats_widget = self.query_one("#security_stats", Static)
            blacklist_info_widget = self.query_one("#blacklist_info", Static)
            content = self.query_one("#content", Static)
            security_events_widget = self.query_one("#security_events", Static)

            # Get security manager from session
            security_manager = None
            if hasattr(self.session, "security_manager"):
                security_manager = self.session.security_manager
            elif hasattr(self.session, "download_manager"):
                download_manager = self.session.download_manager
                if hasattr(download_manager, "security_manager"):
                    security_manager = download_manager.security_manager

            if not security_manager:
                content.update(
                    Panel(
                        _("Security manager not available. Security scanning requires local session mode."),
                        title=_("Security Scan"),
                        border_style="yellow",
                    )
                )
                return

            # Get security statistics
            stats = security_manager.get_security_statistics()
            
            # Security statistics table
            stats_table = Table(
                title=_("Security Statistics"),
                expand=True,
                show_header=False,
                box=None,
            )
            stats_table.add_column(_("Metric"), style="cyan", ratio=1)
            stats_table.add_column(_("Value"), style="green", ratio=2)

            stats_table.add_row(_("Total Connections"), str(stats.get("total_connections", 0)))
            stats_table.add_row(_("Blocked Connections"), str(stats.get("blocked_connections", 0)))
            stats_table.add_row(_("Security Events"), str(stats.get("security_events", 0)))
            stats_table.add_row(_("Blacklisted Peers"), str(stats.get("blacklisted_peers", 0)))
            stats_table.add_row(_("Whitelisted Peers"), str(stats.get("whitelisted_peers", 0)))
            stats_table.add_row(_("Blacklist Size"), str(stats.get("blacklist_size", 0)))
            stats_table.add_row(_("Whitelist Size"), str(stats.get("whitelist_size", 0)))
            stats_table.add_row(_("Reputation Tracking"), str(stats.get("reputation_tracking", 0)))

            security_stats_widget.update(Panel(stats_table, border_style="blue"))

            # Blacklist information
            blacklist_ips = security_manager.get_blacklisted_ips()
            blacklist_table = Table(
                title=_("Blacklisted IPs ({count})").format(count=len(blacklist_ips)),
                expand=True,
                show_header=True,
                box=None,
            )
            blacklist_table.add_column(_("IP Address"), style="red", ratio=1)
            
            # Show up to 20 blacklisted IPs
            for ip in list(blacklist_ips)[:20]:
                blacklist_table.add_row(ip)
            
            if len(blacklist_ips) > 20:
                blacklist_table.add_row(_("... and {count} more").format(count=len(blacklist_ips) - 20))

            blacklist_info_widget.update(Panel(blacklist_table, border_style="red"))

            # Recent security events
            events = security_manager.get_security_events(limit=50)
            events_table = Table(
                title=_("Recent Security Events ({count})").format(count=len(events)),
                expand=True,
                show_header=True,
                box=None,
            )
            events_table.add_column(_("Time"), style="dim", ratio=1)
            events_table.add_column(_("Type"), style="yellow", ratio=1)
            events_table.add_column(_("IP"), style="cyan", ratio=1)
            events_table.add_column(_("Description"), style="white", ratio=2)

            from datetime import datetime
            for event in events[-20:]:  # Show last 20 events
                time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
                events_table.add_row(
                    time_str,
                    event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                    event.ip,
                    event.description[:60] if len(event.description) > 60 else event.description,
                )

            if events:
                security_events_widget.update(Panel(events_table, border_style="yellow"))
            else:
                security_events_widget.update(
                    Panel(
                        _("No recent security events."),
                        title=_("Security Events"),
                        border_style="green",
                    )
                )

            # Overall status
            if stats.get("blocked_connections", 0) > 0 or stats.get("security_events", 0) > 0:
                status_msg = _("Security scan completed. {blocked} blocked connections, {events} security events detected.").format(
                    blocked=stats.get("blocked_connections", 0),
                    events=stats.get("security_events", 0),
                )
                status_style = "yellow"
            else:
                status_msg = _("Security scan completed. No issues detected.")
                status_style = "green"

            content.update(
                Panel(
                    status_msg,
                    title=_("Security Scan Status"),
                    border_style=status_style,
                )
            )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error refreshing security scan data: %s", e)
            try:
                content = self.query_one("#content", Static)
                content.update(
                    Panel(
                        _("Error loading security data: {error}").format(error=str(e)),
                        title=_("Error"),
                        border_style="red",
                    )
                )
            except Exception:
                pass




















