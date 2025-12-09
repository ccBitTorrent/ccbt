"""DHT metrics monitoring screen."""

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


class DHTMetricsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display DHT metrics and statistics."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #dht_stats {
        height: 1fr;
        min-height: 5;
    }
    #routing_table {
        height: 1fr;
    }
    #node_info {
        height: 1fr;
        min-height: 5;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the DHT metrics screen."""
        yield Header()
        with Vertical():
            yield Static(id="dht_stats")
            yield Static(id="routing_table")
            yield Static(id="content")
            yield Static(id="node_info")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh DHT metrics display."""
        try:
            dht_stats_widget = self.query_one("#dht_stats", Static)
            routing_table_widget = self.query_one("#routing_table", Static)
            content = self.query_one("#content", Static)
            node_info_widget = self.query_one("#node_info", Static)

            # Get DHT client
            dht_client = None
            try:
                from ccbt.discovery.dht import get_dht_client
                dht_client = get_dht_client()
            except Exception:
                # Try to get from session
                if hasattr(self.session, "dht_client"):
                    dht_client = self.session.dht_client
                elif hasattr(self.session, "dht"):
                    dht_client = self.session.dht

            if not dht_client:
                content.update(
                    Panel(
                        _("DHT client not available. DHT metrics require DHT to be enabled and running."),
                        title=_("DHT Metrics"),
                        border_style="yellow",
                    )
                )
                return

            # Get DHT statistics
            try:
                stats = dht_client.get_stats()
            except Exception as e:
                content.update(
                    Panel(
                        _("Error getting DHT stats: {error}").format(error=str(e)),
                        title=_("Error"),
                        border_style="red",
                    )
                )
                return

            # DHT statistics table
            stats_table = Table(
                title=_("DHT Statistics"),
                expand=True,
                show_header=False,
                box=None,
            )
            stats_table.add_column(_("Metric"), style="cyan", ratio=1)
            stats_table.add_column(_("Value"), style="green", ratio=2)

            # Extract stats
            total_nodes = stats.get("total_nodes", 0)
            active_nodes = stats.get("active_nodes", 0)
            queries_sent = stats.get("queries_sent", 0)
            queries_received = stats.get("queries_received", 0)
            responses_received = stats.get("responses_received", 0)
            errors = stats.get("errors", 0)
            peers_found = stats.get("peers_found", 0)
            is_running = stats.get("is_running", False)

            stats_table.add_row(_("Status"), _("Running") if is_running else _("Stopped"))
            stats_table.add_row(_("Total Nodes"), str(total_nodes))
            stats_table.add_row(_("Active Nodes"), str(active_nodes))
            stats_table.add_row(_("Queries Sent"), str(queries_sent))
            stats_table.add_row(_("Queries Received"), str(queries_received))
            stats_table.add_row(_("Responses Received"), str(responses_received))
            stats_table.add_row(_("Errors"), str(errors))
            stats_table.add_row(_("Peers Found"), str(peers_found))

            dht_stats_widget.update(Panel(stats_table, border_style="blue"))

            # Routing table information
            routing_table_stats = stats.get("routing_table", {})
            if routing_table_stats:
                routing_table_info = Table(
                    title=_("Routing Table"),
                    expand=True,
                    show_header=False,
                    box=None,
                )
                routing_table_info.add_column(_("Metric"), style="cyan", ratio=1)
                routing_table_info.add_column(_("Value"), style="green", ratio=2)

                routing_table_info.add_row(
                    _("Total Buckets"),
                    str(routing_table_stats.get("total_buckets", 0))
                )
                routing_table_info.add_row(
                    _("Non-Empty Buckets"),
                    str(routing_table_stats.get("non_empty_buckets", 0))
                )
                routing_table_info.add_row(
                    _("Total Nodes"),
                    str(routing_table_stats.get("total_nodes", 0))
                )
                routing_table_info.add_row(
                    _("Closest Nodes"),
                    str(routing_table_stats.get("closest_nodes", 0))
                )

                routing_table_widget.update(Panel(routing_table_info, border_style="cyan"))
            else:
                routing_table_widget.update(
                    Panel(
                        _("Routing table statistics not available."),
                        title=_("Routing Table"),
                        border_style="dim",
                    )
                )

            # Node information
            if hasattr(dht_client, "node_id"):
                node_id = dht_client.node_id
                node_id_hex = node_id.hex() if isinstance(node_id, bytes) else str(node_id)
                
                node_table = Table(
                    title=_("Local Node Information"),
                    expand=True,
                    show_header=False,
                    box=None,
                )
                node_table.add_column(_("Property"), style="cyan", ratio=1)
                node_table.add_column(_("Value"), style="green", ratio=2)

                node_table.add_row(_("Node ID"), node_id_hex[:32] + "..." if len(node_id_hex) > 32 else node_id_hex)
                
                if hasattr(dht_client, "port"):
                    node_table.add_row(_("Port"), str(dht_client.port))
                
                if hasattr(dht_client, "bootstrap_nodes"):
                    bootstrap_count = len(dht_client.bootstrap_nodes) if dht_client.bootstrap_nodes else 0
                    node_table.add_row(_("Bootstrap Nodes"), str(bootstrap_count))

                node_info_widget.update(Panel(node_table, border_style="green"))
            else:
                node_info_widget.update(
                    Panel(
                        _("Node information not available."),
                        title=_("Node Information"),
                        border_style="dim",
                    )
                )

            # Overall status
            if is_running:
                if active_nodes > 0:
                    status_msg = _("DHT is running. {active} active nodes, {peers} peers found.").format(
                        active=active_nodes,
                        peers=peers_found,
                    )
                    status_style = "green"
                else:
                    status_msg = _("DHT is running but no active nodes yet.")
                    status_style = "yellow"
            else:
                status_msg = _("DHT is not running.")
                status_style = "red"

            content.update(
                Panel(
                    status_msg,
                    title=_("DHT Status"),
                    border_style=status_style,
                )
            )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error refreshing DHT metrics data: %s", e)
            try:
                content = self.query_one("#content", Static)
                content.update(
                    Panel(
                        _("Error loading DHT data: {error}").format(error=str(e)),
                        title=_("Error"),
                        border_style="red",
                    )
                )
            except Exception:
                pass




















