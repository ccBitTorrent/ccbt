"""Core widget components for the terminal dashboard."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from textual.widgets import DataTable, RichLog, Sparkline, Static
else:
    try:
        from textual.widgets import DataTable, RichLog, Sparkline, Static
    except ImportError:
        # Fallback for when textual is not available
        class DataTable:  # type: ignore[no-redef]
            pass

        class RichLog:  # type: ignore[no-redef]
            pass

        class Sparkline:  # type: ignore[no-redef]
            pass

        class Static:  # type: ignore[no-redef]
            pass


from rich.panel import Panel
from rich.table import Table

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Tabs, Tab
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Tabs:  # type: ignore[no-redef]
        pass

    class Tab:  # type: ignore[no-redef]
        pass


class Overview(Static):  # type: ignore[misc]
    """Simple widget to render global stats."""
    
    DEFAULT_CSS = """
    Overview {
        height: 2;
        min-height: 2;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        text-wrap: nowrap;  /* Prevent text wrapping */
        width: 1fr;  /* Take full width */
    }
    """

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update dashboard with statistics."""
        # Format all stats in a single row with proper formatting
        torrents = str(stats.get("num_torrents", 0))
        active = str(stats.get("num_active", 0))
        paused = str(stats.get("num_paused", 0))
        seeding = str(stats.get("num_seeding", 0))
        
        # Format download rate
        down_rate_val = float(stats.get("download_rate", 0.0))
        if down_rate_val >= 1024 * 1024:
            down_rate = f"{down_rate_val / (1024 * 1024):.1f} MB/s"
        elif down_rate_val >= 1024:
            down_rate = f"{down_rate_val / 1024:.1f} KB/s"
        else:
            down_rate = f"{down_rate_val:.1f} B/s"
        
        # Format upload rate
        up_rate_val = float(stats.get("upload_rate", 0.0))
        if up_rate_val >= 1024 * 1024:
            up_rate = f"{up_rate_val / (1024 * 1024):.1f} MB/s"
        elif up_rate_val >= 1024:
            up_rate = f"{up_rate_val / 1024:.1f} KB/s"
        else:
            up_rate = f"{up_rate_val:.1f} B/s"
        
        avg_progress = f"{stats.get('average_progress', 0.0) * 100:.1f}%"
        
        # Get connected peer count if available
        connected_peers = stats.get("connected_peers", 0)
        peers_str = f"[cyan]Peers:[/cyan] {connected_peers}" if connected_peers > 0 else ""
        
        # Create single-line display with proper spacing
        overview_parts = [
            f"[cyan]Torrents:[/cyan] {torrents}",
            f"[cyan]Active:[/cyan] {active}",
            f"[cyan]Paused:[/cyan] {paused}",
            f"[cyan]Seeding:[/cyan] {seeding}",
            f"[cyan]Down Rate:[/cyan] {down_rate}",
            f"[cyan]Up Rate:[/cyan] {up_rate}",
            f"[cyan]Avg Progress:[/cyan] {avg_progress}",
        ]
        if peers_str:
            overview_parts.insert(4, peers_str)  # Insert after seeding
        
        overview_text = " | ".join(overview_parts)
        self.update(overview_text)


class TorrentsTable(DataTable):  # type: ignore[misc]
    """Widget to render per-torrent status table.
    
    Note: This is the legacy widget. New code should use ReusableDataTable
    from reusable_table.py for better consistency.
    """

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrents table widget."""
        # Textual widget lifecycle - requires widget mounting context
        self.zebra_stripes = True
        self.add_columns(_("Info Hash"), _("Name"), _("Status"), _("Progress"), _("Down/Up (B/s)"))

    def update_from_status(
        self, status: dict[str, dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Update torrents table with current status."""
        self.clear()
        for ih, st in status.items():
            progress = f"{float(st.get('progress', 0.0)) * 100:.1f}%"
            rates = f"{float(st.get('download_rate', 0.0)):.0f} / {float(st.get('upload_rate', 0.0)):.0f}"
            self.add_row(
                ih,
                str(st.get("name", "-")),
                str(st.get("status", "-")),
                progress,
                rates,
                key=ih,
            )

    def get_selected_info_hash(self) -> str | None:  # pragma: no cover
        """Get the info hash of the currently selected torrent."""
        if hasattr(self, "cursor_row_key"):
            with contextlib.suppress(Exception):
                row_key = self.cursor_row_key
                return None if row_key is None else str(row_key)
        return None


class PeersTable(DataTable):  # type: ignore[misc]
    """Widget to render peers for selected torrent.
    
    Note: This is the legacy widget. New code should use ReusableDataTable
    from reusable_table.py for better consistency.
    """

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the peers table widget."""
        # Textual widget lifecycle - requires widget mounting context
        self.zebra_stripes = True
        self.add_columns(
            _("IP"),
            _("Port"),
            _("Down (B/s)"),
            _("Up (B/s)"),
            _("Latency"),
            _("Quality"),
            _("Health"),
            _("Choked"),
            _("Client"),
        )

    def _calculate_connection_quality(
        self, peer_data: dict[str, Any]
    ) -> float:  # pragma: no cover
        """Calculate connection quality score (0-100).

        Args:
            peer_data: Peer data dictionary

        Returns:
            Quality score (0-100)
        """
        down = float(peer_data.get("download_rate", 0.0))
        up = float(peer_data.get("upload_rate", 0.0))
        choked = peer_data.get("choked", True)

        # Simple quality calculation
        # Higher speeds and unchoked = better quality
        quality = 0.0
        if not choked:
            quality += 50.0

        # Speed contribution (normalized, max 50 points)
        total_speed = down + up
        if total_speed > 0:
            # Assume 1 MB/s = 50 points (max)
            speed_score = min(50.0, (total_speed / (1024 * 1024)) * 50.0)
            quality += speed_score

        return min(100.0, max(0.0, quality))

    def _format_quality_indicator(self, quality: float) -> str:  # pragma: no cover
        """Format quality as visual indicator.

        Args:
            quality: Quality score (0-100)

        Returns:
            Formatted quality string
        """
        if quality >= 80:
            return f"[green]{quality:.0f}%[/green]"
        if quality >= 60:
            return f"[yellow]{quality:.0f}%[/yellow]"
        if quality >= 40:
            return f"[orange1]{quality:.0f}%[/orange1]"
        return f"[red]{quality:.0f}%[/red]"

    def _get_health_status(self, quality: float) -> str:  # pragma: no cover
        """Get health status string based on quality score.

        Args:
            quality: Quality score (0-100)

        Returns:
            Health status string
        """
        if quality >= 80:
            return "[green]Excellent[/green]"
        if quality >= 60:
            return "[yellow]Good[/yellow]"
        if quality >= 40:
            return "[orange1]Fair[/orange1]"
        return "[red]Poor[/red]"

    def update_from_peers(
        self, peers: list[dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Update peers table with current peer data."""
        self.clear()
        for p in peers or []:
            # Calculate quality score
            quality = self._calculate_connection_quality(p)
            quality_str = self._format_quality_indicator(quality)
            health_status = self._get_health_status(quality)

            # Get latency
            latency = p.get("request_latency", 0.0)
            if latency and latency > 0:
                latency_str = f"{latency * 1000:.1f} ms"
            else:
                latency_str = "N/A"

            self.add_row(
                str(p.get("ip", "-")),
                str(p.get("port", "-")),
                f"{float(p.get('download_rate', 0.0)):.0f}",
                f"{float(p.get('upload_rate', 0.0)):.0f}",
                latency_str,
                quality_str,
                health_status,
                str(p.get("choked", False)),
                str(p.get("client", "?")),
            )


class SpeedSparklines(Static):  # type: ignore[misc]
    """Widget to show download/upload speed history."""

    DEFAULT_CSS = """
    SpeedSparklines {
        height: auto;
        layout: vertical;
    }
    
    Sparkline {
        height: 5;
        min-height: 5;
        width: 1fr;
        margin: 1;
    }
    """

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the speed sparklines widget."""
        # Textual widget lifecycle - requires widget mounting context
        self._down = Sparkline()
        self._up = Sparkline()
        self._down_history: list[float] = []
        self._up_history: list[float] = []
        # Initialize with zero data so graphs render immediately
        self._down.data = [0.0] * 10  # type: ignore[attr-defined]
        self._up.data = [0.0] * 10  # type: ignore[attr-defined]
        # Mount sparklines as children instead of wrapping in Container
        self.mount(self._down, self._up)
        # Update with a simple title instead of Panel
        self.update(_("Speeds"))

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update sparklines with current speed statistics."""
        self._down_history.append(float(stats.get("download_rate", 0.0)))
        self._up_history.append(float(stats.get("upload_rate", 0.0)))
        # Keep last 120 samples (~2 minutes at 1s)
        self._down_history = self._down_history[-120:]
        self._up_history = self._up_history[-120:]
        with contextlib.suppress(Exception):
            self._down.data = self._down_history  # type: ignore[attr-defined]
            self._up.data = self._up_history  # type: ignore[attr-defined]


class SummaryCards(Static):  # type: ignore[misc]
    """Widget to display summary cards for key metrics."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize summary cards widget."""
        super().__init__(*args, **kwargs)
        self._cards: dict[str, dict[str, Any]] = {}

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update summary cards with statistics.

        Args:
            stats: Dictionary containing global statistics
        """
        # Format download speed
        down_rate = float(stats.get("download_rate", 0.0))
        if down_rate >= 1024 * 1024:
            down_str = f"{down_rate / (1024 * 1024):.2f} MB/s"
        elif down_rate >= 1024:
            down_str = f"{down_rate / 1024:.2f} KB/s"
        else:
            down_str = f"{down_rate:.2f} B/s"

        # Format upload speed
        up_rate = float(stats.get("upload_rate", 0.0))
        if up_rate >= 1024 * 1024:
            up_str = f"{up_rate / (1024 * 1024):.2f} MB/s"
        elif up_rate >= 1024:
            up_str = f"{up_rate / 1024:.2f} KB/s"
        else:
            up_str = f"{up_rate:.2f} B/s"

        # Create cards table
        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column("Card 1", style="cyan", ratio=1)
        table.add_column("Card 2", style="green", ratio=1)
        table.add_column("Card 3", style="yellow", ratio=1)
        table.add_column("Card 4", style="magenta", ratio=1)

        table.add_row(
            f"[bold]↓ Download[/bold]\n{down_str}",
            f"[bold]↑ Upload[/bold]\n{up_str}",
            f"[bold]Active[/bold]\n{stats.get('num_active', 0)}",
            f"[bold]Peers[/bold]\n{stats.get('connected_peers', 0)}",
        )

        self.update(Panel(table, title=_("Summary"), border_style="blue"))


class QuickStatsPanel(Static):  # type: ignore[misc]
    """Widget to display quick statistics panel."""

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update quick stats panel with statistics.

        Args:
            stats: Dictionary containing global statistics
        """
        # Format total downloaded
        total_downloaded = int(stats.get("total_downloaded", 0))
        if total_downloaded >= 1024 * 1024 * 1024:
            down_str = f"{total_downloaded / (1024**3):.2f} GB"
        elif total_downloaded >= 1024 * 1024:
            down_str = f"{total_downloaded / (1024**2):.2f} MB"
        elif total_downloaded >= 1024:
            down_str = f"{total_downloaded / 1024:.2f} KB"
        else:
            down_str = f"{total_downloaded:.2f} B"

        # Format total uploaded
        total_uploaded = int(stats.get("total_uploaded", 0))
        if total_uploaded >= 1024 * 1024 * 1024:
            up_str = f"{total_uploaded / (1024**3):.2f} GB"
        elif total_uploaded >= 1024 * 1024:
            up_str = f"{total_uploaded / (1024**2):.2f} MB"
        elif total_uploaded >= 1024:
            up_str = f"{total_uploaded / 1024:.2f} KB"
        else:
            up_str = f"{total_uploaded:.2f} B"

        # Calculate share ratio
        share_ratio = 0.0
        if total_downloaded > 0:
            share_ratio = total_uploaded / total_downloaded

        # Format uptime (if available)
        uptime = stats.get("uptime", 0.0)
        if uptime:
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"
        else:
            uptime_str = "N/A"

        # Create stats table
        table = Table(show_header=False, box=None, expand=True)
        table.add_column("Stat", style="cyan", ratio=1)
        table.add_column("Value", style="white", ratio=2)

        table.add_row(_("Total Downloaded"), down_str)
        table.add_row(_("Total Uploaded"), up_str)
        table.add_row(_("Share Ratio"), f"{share_ratio:.2f}")
        table.add_row(_("Uptime"), uptime_str)

        self.update(Panel(table, title=_("Quick Stats"), border_style="green"))


class GlobalTorrentMetricsPanel(Static):  # type: ignore[misc]
    """Compact panel displaying aggregated torrent metrics."""

    DEFAULT_CSS = """
    GlobalTorrentMetricsPanel {
        height: auto;
        min-height: 4;
        padding: 0 1;
    }
    """

    def update_metrics(
        self,
        stats: dict[str, Any] | None,
        swarm_samples: list[dict[str, Any]] | None = None,
    ) -> None:  # pragma: no cover
        """Render aggregated torrent metrics."""
        if not stats:
            self.update(Panel(_("No metrics available"), border_style="red"))
            return

        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column("Col1", ratio=1)
        table.add_column("Col2", ratio=1)
        table.add_column("Col3", ratio=1)
        table.add_column("Col4", ratio=2)

        total = stats.get("num_torrents", 0)
        active = stats.get("num_active", 0)
        paused = stats.get("num_paused", 0)
        seeding = stats.get("num_seeding", 0)

        down_rate = self._format_rate(float(stats.get("download_rate", 0.0)))
        up_rate = self._format_rate(float(stats.get("upload_rate", 0.0)))
        total_down = self._format_bytes(int(stats.get("total_downloaded", 0)))
        total_up = self._format_bytes(int(stats.get("total_uploaded", 0)))
        avg_progress = stats.get("average_progress", 0.0) * 100
        connected_peers = stats.get("connected_peers", 0)

        highlight = self._format_swarm_highlight(swarm_samples or [])

        table.add_row(
            f"[bold]Torrents[/bold]\n{total}",
            f"[bold]Active[/bold]\n{active}",
            f"[bold]Paused[/bold]\n{paused}",
            f"[bold]Seeding[/bold]\n{seeding}",
        )
        table.add_row(
            f"[bold]↓[/bold] {down_rate}",
            f"[bold]↑[/bold] {up_rate}",
            f"[bold]Avg %[/bold] {avg_progress:.1f}%",
            f"[bold]Swarm[/bold]\n{highlight}",
        )
        table.add_row(
            f"[bold]Total ↓[/bold]\n{total_down}",
            f"[bold]Total ↑[/bold]\n{total_up}",
            f"[bold]Peers[/bold]\n{connected_peers}",
            "",
        )

        self.update(Panel(table, title=_("Global Torrent Metrics"), border_style="blue"))

    @staticmethod
    def _format_rate(rate: float) -> str:
        if rate >= 1024 * 1024:
            return f"{rate / (1024 * 1024):.2f} MB/s"
        if rate >= 1024:
            return f"{rate / 1024:.1f} KB/s"
        return f"{rate:.0f} B/s"

    @staticmethod
    def _format_bytes(value: int) -> str:
        if value >= 1024 ** 3:
            return f"{value / (1024 ** 3):.2f} GB"
        if value >= 1024 ** 2:
            return f"{value / (1024 ** 2):.2f} MB"
        if value >= 1024:
            return f"{value / 1024:.2f} KB"
        return f"{value} B"

    def _format_swarm_highlight(self, samples: list[dict[str, Any]]) -> str:
        if not samples:
            return _("No swarm samples")
        sample = max(samples, key=lambda s: float(s.get("swarm_availability", 0.0)))
        availability = float(sample.get("swarm_availability", 0.0)) * 100
        name = sample.get("name") or sample.get("info_hash", "")
        rate = self._format_rate(float(sample.get("download_rate", 0.0)))
        # Highlight critical torrents
        if availability < 25:
            return f"[red]{name}[/red] • {availability:.0f}% • ↓ {rate}"
        return f"{name} • {availability:.0f}% • ↓ {rate}"


class SwarmHotspotsTable(DataTable):  # type: ignore[misc]
    """Table showing torrents sorted by poor swarm availability (swarm hotspots)."""
    
    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the swarm hotspots table widget."""
        self.zebra_stripes = True
        self.add_columns(_("Torrent"), _("Availability"), _("Peers"), _("Rates"), _("Status"))
    
    def update_from_swarm_samples(
        self, samples: list[dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Update table with swarm samples sorted by poor availability.
        
        Args:
            samples: List of swarm health samples from DataProvider
        """
        self.clear()
        if not samples:
            return
        
        # Sort by availability (lowest first) to show hotspots
        sorted_samples = sorted(
            samples,
            key=lambda s: float(s.get("swarm_availability", 0.0)),
        )
        
        for sample in sorted_samples:
            name = sample.get("name") or sample.get("info_hash", "unknown")[:16]
            availability = float(sample.get("swarm_availability", 0.0))
            availability_pct = availability * 100
            connected_peers = int(sample.get("connected_peers", 0))
            active_peers = int(sample.get("active_peers", 0))
            download_rate = float(sample.get("download_rate", 0.0))
            upload_rate = float(sample.get("upload_rate", 0.0))
            
            # Format availability with color
            if availability_pct < 25:
                avail_str = f"[red]{availability_pct:.1f}%[/red]"
                status_str = "[red]Critical[/red]"
            elif availability_pct < 50:
                avail_str = f"[orange1]{availability_pct:.1f}%[/orange1]"
                status_str = "[orange1]Fragile[/orange1]"
            elif availability_pct < 80:
                avail_str = f"[yellow]{availability_pct:.1f}%[/yellow]"
                status_str = "[yellow]Healthy[/yellow]"
            else:
                avail_str = f"[green]{availability_pct:.1f}%[/green]"
                status_str = "[green]Excellent[/green]"
            
            # Format rates
            def _format_rate(rate: float) -> str:
                if rate >= 1024 * 1024:
                    return f"{rate / (1024 * 1024):.1f} MiB/s"
                if rate >= 1024:
                    return f"{rate / 1024:.1f} KiB/s"
                return f"{rate:.0f} B/s"
            
            rates_str = f"↓ {_format_rate(download_rate)} • ↑ {_format_rate(upload_rate)}"
            peers_str = f"{active_peers}/{connected_peers}"
            
            self.add_row(name, avail_str, peers_str, rates_str, status_str)


class GraphsSectionContainer(Container):  # type: ignore[misc]
    """Always-visible graphs section container for top half of screen.

    This container holds the graphs section with summary cards, quick stats,
    and graph sub-tabs. It remains visible when switching between main tabs.
    """

    DEFAULT_CSS = """
    GraphsSectionContainer {
        height: 1fr;
        layout: vertical;
        border: solid $primary;
        overflow: hidden;
        min-width: 80;
        min-height: 20;
        display: block;
    }
    
    #top-pane-content {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
        overflow: hidden;
        min-height: 15;
        display: block;
    }
    
    /* CRITICAL FIX: Graphs pane always visible */
    #top-pane-graphs {
        height: 1fr;
        overflow-y: auto;
        overflow-x: hidden;
        min-height: 12;
        display: block;
    }
    
    /* Graph selector container - always visible */
    #graphs-selector-container {
        height: auto;
        min-height: 3;
        border-bottom: solid $primary;
        display: block;
    }
    
    #graph-display-area {
        height: 1fr;
        min-height: 20;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    """

    def __init__(
        self,
        data_provider: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize graphs section container.
        
        Args:
            data_provider: DataProvider instance for accessing data
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._graph_selector: Any | None = None  # ButtonSelector
        self._active_graph_tab_id: str | None = None
        self._registered_widgets: list[Any] = []  # Track registered widgets for cleanup

    def compose(self) -> Any:  # pragma: no cover
        """Compose the graphs section layout.
        
        CRITICAL FIX: Replaced Tabs with ButtonSelector for better visibility control.
        All content is always mounted and visible, with manual visibility management.
        """
        from ccbt.interface.widgets.button_selector import ButtonSelector
        
        # CRITICAL FIX: Removed alerts and logs tabs - only graphs now
        # Graphs pane - Always visible (no selector needed)
        with Container(id="top-pane-content"):
            with Container(id="top-pane-graphs"):
                # Graph sub-selector (always visible)
                with Container(id="graphs-selector-container"):
                    yield ButtonSelector(
                        [
                            ("graph-tab-performance", _("Performance")),
                            ("graph-tab-disk", _("Disk IO")),
                            ("graph-tab-system", _("System Resources")),
                            ("graph-tab-network", _("Network")),
                            ("graph-tab-swarm", _("Swarm Health")),
                            ("graph-tab-peers", _("Peer Quality")),
                            ("graph-tab-peer-dist", _("Peer Distribution")),
                            ("graph-tab-dht", _("DHT Health")),
                            ("graph-tab-swarm-timeline", _("Swarm Timeline")),
                            ("graph-tab-global-kpis", _("Global KPIs")),
                        ],
                        initial_selection="graph-tab-performance",
                        id="graph-sub-selector",
                    )
                with Container(id="graph-display-area"):
                    yield Static(_("Select a graph type to view"), id="graph-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the graphs section container."""
        logger.debug("GraphsSectionContainer.on_mount: Starting mount process (id=%s)", self.id if hasattr(self, "id") else "unknown")
        # Get widget references
        try:
            from ccbt.interface.widgets.button_selector import ButtonSelector
            
            logger.debug("GraphsSectionContainer.on_mount: Querying widgets...")
            self._graph_selector = self.query_one("#graph-sub-selector", ButtonSelector)  # type: ignore[attr-defined]
            logger.debug("GraphsSectionContainer.on_mount: Found graph_selector: %s", self._graph_selector is not None)
            
            # CRITICAL FIX: Ensure graph display area is visible
            try:
                graph_area = self.query_one("#graph-display-area", Container)  # type: ignore[attr-defined]
                if graph_area:
                    graph_area.display = True  # type: ignore[attr-defined]
                    logger.debug("GraphsSectionContainer: Graph display area is visible")
            except Exception as e:
                logger.error("Error ensuring graph area visibility: %s", e, exc_info=True)
            
            # CRITICAL FIX: Set active graph selection first, then load content
            if self._graph_selector:
                try:
                    # Set active selection to trigger initial load
                    self._graph_selector.active = "graph-tab-performance"  # type: ignore[attr-defined]
                    logger.debug("GraphsSectionContainer: Set active graph selection to performance")
                except Exception as e:
                    logger.error("Error setting active graph selection: %s", e, exc_info=True)
            
            # Load graph content explicitly
            self._load_graph_content("graph-tab-performance")
            logger.debug("GraphsSectionContainer: Loaded initial graph content")
            
            # Also schedule a refresh-based initialization as backup
            def init_visibility_refresh() -> None:
                try:
                    logger.debug("GraphsSectionContainer: Refresh-based initialization")
                    self._load_graph_content("graph-tab-performance")
                except Exception as e:
                    logger.error("Error in refresh-based init: %s", e, exc_info=True)
            
            self.call_after_refresh(init_visibility_refresh)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting graphs section container: %s", e, exc_info=True)

    def on_language_changed(self, message: Any) -> None:  # pragma: no cover
        """Handle language change event.

        Args:
            message: LanguageChanged message with new locale
        """
        try:
            from ccbt.interface.widgets.language_selector import (
                LanguageSelectorWidget,
            )

            # Verify this is a LanguageChanged message
            if not hasattr(message, "locale"):
                return

            # Update graph sub-tab labels (ButtonSelector doesn't need label updates)
            # Labels are set in compose() and don't change with language

            # Update static text
            try:
                placeholder = self.query_one("#graph-placeholder", Static)  # type: ignore[attr-defined]
                placeholder.update(_("Select a graph type to view"))
            except Exception:
                pass

        except Exception as e:
            logger.debug("Error refreshing graphs section translations: %s", e)


    def _load_graph_content(self, graph_tab_id: str) -> None:  # pragma: no cover
        """Load content for a specific graph tab.

        Args:
            graph_tab_id: ID of the graph tab to load
        """
        try:
            graph_area = self.query_one("#graph-display-area", Container)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure graph area is visible
            if graph_area:
                graph_area.display = True  # type: ignore[attr-defined]
            
            if graph_tab_id == self._active_graph_tab_id:
                return
            
            # CRITICAL FIX: Clear existing content before loading new graph
            # Unregister widgets before removing them
            try:
                for widget in self._registered_widgets:
                    try:
                        if self._data_provider and hasattr(self._data_provider, "get_adapter"):
                            adapter = self._data_provider.get_adapter()
                            if adapter and hasattr(adapter, "unregister_widget"):
                                adapter.unregister_widget(widget)
                    except Exception as e:
                        logger.debug("Error unregistering widget: %s", e)
                self._registered_widgets.clear()
            except Exception as e:
                logger.debug("Error unregistering widgets: %s", e)
            
            try:
                graph_area.remove_children()  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error removing graph children: %s", e)
            
            # CRITICAL FIX: Verify data provider is available and valid
            if not self._data_provider:
                logger.warning("Data provider not available for graph loading")
                placeholder = Static(
                    _("{graph_tab_id} - Data provider not available").format(graph_tab_id=graph_tab_id),
                    id=f"{graph_tab_id}-placeholder"
                )
                graph_area.mount(placeholder)  # type: ignore[attr-defined]
                self._active_graph_tab_id = graph_tab_id
                return
            
            # CRITICAL FIX: Verify data provider has required methods
            if not hasattr(self._data_provider, "get_adapter"):
                logger.warning("Data provider missing get_adapter method")
                placeholder = Static(
                    _("{graph_tab_id} - Data provider configuration error").format(graph_tab_id=graph_tab_id),
                    id=f"{graph_tab_id}-placeholder"
                )
                graph_area.mount(placeholder)  # type: ignore[attr-defined]
                self._active_graph_tab_id = graph_tab_id
                return
            
            # Load appropriate graph widget based on tab
            if graph_tab_id == "graph-tab-performance":
                # Performance graph with upload/download only
                try:
                    logger.debug("GraphsSectionContainer: Loading performance graph widget")
                    from ccbt.interface.widgets.graph_widget import PerformanceGraphWidget
                    graph = PerformanceGraphWidget(
                        data_provider=self._data_provider,
                        id="performance-graph"
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    # CRITICAL FIX: Ensure graph is visible and trigger refresh after mount
                    graph.display = True  # type: ignore[attr-defined]
                    # Ensure graph area is visible
                    graph_area.display = True  # type: ignore[attr-defined]
                    # Register widget for event-driven updates
                    self._register_widget(graph)
                    # Use call_after_refresh to ensure widget is fully mounted before starting updates
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("GraphsSectionContainer: Performance graph widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting performance graph: %s", e, exc_info=True)
                    placeholder = Static(_("Performance metrics - Error: {error}").format(error=e), id="performance-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-disk":
                # Disk I/O graph
                try:
                    from ccbt.interface.widgets.graph_widget import DiskGraphWidget
                    graph = DiskGraphWidget(
                        data_provider=self._data_provider,
                        id="disk-graph"
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Disk graph widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting disk graph: %s", e, exc_info=True)
                    placeholder = Static(_("Disk I/O metrics - Error: {error}").format(error=e), id="disk-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-system":
                # System resources graph
                try:
                    from ccbt.interface.widgets.graph_widget import SystemResourcesGraphWidget
                    graph = SystemResourcesGraphWidget(
                        data_provider=self._data_provider,
                        id="system-graph"
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("System resources graph widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting system resources graph: %s", e, exc_info=True)
                    placeholder = Static(_("System resources - Error: {error}").format(error=e), id="system-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-network":
                # Network graph
                try:
                    from ccbt.interface.widgets.graph_widget import NetworkGraphWidget
                    graph = NetworkGraphWidget(
                        data_provider=self._data_provider,
                        id="network-graph"
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Network graph widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting network graph: %s", e, exc_info=True)
                    placeholder = Static(_("Network quality - Error: {error}").format(error=e), id="network-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-swarm":
                try:
                    from ccbt.interface.widgets.graph_widget import SwarmHealthDotPlot
                    graph = SwarmHealthDotPlot(
                        data_provider=self._data_provider,
                        id="swarm-health-graph",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Swarm health graph mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting swarm health graph: %s", e, exc_info=True)
                    placeholder = Static(_("Swarm health - Error: {error}").format(error=e), id="swarm-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-peers":
                try:
                    from ccbt.interface.widgets.graph_widget import PeerQualitySummaryWidget
                    graph = PeerQualitySummaryWidget(
                        data_provider=self._data_provider,
                        id="peer-quality-graph",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Peer quality widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting peer quality widget: %s", e, exc_info=True)
                    placeholder = Static(_("Peer quality - Error: {error}").format(error=e), id="peer-quality-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-peer-dist":
                try:
                    from ccbt.interface.widgets.peer_quality_distribution_widget import (
                        PeerQualityDistributionWidget,
                    )
                    graph = PeerQualityDistributionWidget(
                        data_provider=self._data_provider,
                        id="peer-quality-distribution-widget",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Peer quality distribution widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting peer quality distribution widget: %s", e, exc_info=True)
                    placeholder = Static(_("Peer distribution - Error: {error}").format(error=e), id="peer-dist-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-dht":
                try:
                    from ccbt.interface.widgets.dht_health_widget import DHTHealthWidget

                    graph = DHTHealthWidget(
                        data_provider=self._data_provider,
                        id="dht-health-widget",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("DHT health widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting DHT health widget: %s", e, exc_info=True)
                    placeholder = Static(f"DHT health - Error: {e}", id="dht-health-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-swarm-timeline":
                try:
                    from ccbt.interface.widgets.swarm_timeline_widget import SwarmTimelineWidget

                    graph = SwarmTimelineWidget(
                        data_provider=self._data_provider,
                        id="swarm-timeline-widget",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Swarm timeline widget mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting swarm timeline widget: %s", e, exc_info=True)
                    placeholder = Static(_("Swarm timeline - Error: {error}").format(error=e), id="swarm-timeline-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            elif graph_tab_id == "graph-tab-global-kpis":
                try:
                    from ccbt.interface.widgets.global_kpis_panel import GlobalKPIsPanel

                    graph = GlobalKPIsPanel(
                        data_provider=self._data_provider,
                        id="global-kpis-panel",
                    )
                    graph_area.mount(graph)  # type: ignore[attr-defined]
                    graph.display = True  # type: ignore[attr-defined]
                    graph_area.display = True  # type: ignore[attr-defined]
                    self._register_widget(graph)
                    self.call_after_refresh(lambda: self._ensure_graph_visible(graph))  # type: ignore[attr-defined]
                    logger.debug("Global KPIs panel mounted successfully")
                    self._active_graph_tab_id = graph_tab_id
                except Exception as e:
                    logger.error("Error mounting global KPIs panel: %s", e, exc_info=True)
                    placeholder = Static(f"Global KPIs - Error: {e}", id="global-kpis-placeholder")
                    graph_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_graph_tab_id = graph_tab_id
            else:
                # Placeholder for other graph types
                placeholder = Static(f"{graph_tab_id} graph - Coming soon", id=f"{graph_tab_id}-graph")
                graph_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_graph_tab_id = graph_tab_id
        except Exception as e:
            logger.error("Error loading graph content for %s: %s", graph_tab_id, e, exc_info=True)
    
    def _register_widget(self, widget: Any) -> None:
        """Register widget with adapter for event-driven updates.
        
        Args:
            widget: Widget instance to register with data provider adapter
        """
        if not widget:
            logger.debug("GraphsSectionContainer: Cannot register None widget")
            return
        
        # Add to registered widgets list for cleanup
        if widget not in self._registered_widgets:
            self._registered_widgets.append(widget)
        
        try:
            # CRITICAL FIX: Verify data provider and adapter are available
            if not self._data_provider:
                logger.warning("GraphsSectionContainer: Data provider not available for widget registration")
                return
            
            if not hasattr(self._data_provider, "get_adapter"):
                logger.warning("GraphsSectionContainer: Data provider missing get_adapter method")
                return
            
            adapter = self._data_provider.get_adapter()
            if not adapter:
                logger.debug("GraphsSectionContainer: Adapter not available (may be normal for local mode)")
                return
            
            if not hasattr(adapter, "register_widget"):
                logger.debug("GraphsSectionContainer: Adapter missing register_widget method")
                return
            
            # Register widget with adapter
            adapter.register_widget(widget)
            logger.debug(
                "GraphsSectionContainer: Successfully registered widget %s with adapter",
                getattr(widget, "id", type(widget).__name__)
            )
        except Exception as exc:
            logger.warning(
                "GraphsSectionContainer: Error registering widget %s: %s",
                getattr(widget, "id", type(widget).__name__),
                exc,
                exc_info=True
            )

    def _ensure_graph_visible(self, graph_widget: Any) -> None:  # pragma: no cover
        """Ensure graph widget is visible and trigger initial update.
        
        Args:
            graph_widget: Graph widget instance to make visible
        """
        try:
            if graph_widget:
                graph_widget.display = True  # type: ignore[attr-defined]
                # Trigger refresh to ensure widget repaints
                graph_widget.refresh()  # type: ignore[attr-defined]
                logger.debug("Ensured graph widget is visible: %s", graph_widget.id if hasattr(graph_widget, "id") else "unknown")
        except Exception as e:
            logger.debug("Error ensuring graph visibility: %s", e)

    def on_button_selector_selection_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle ButtonSelector selection change events.
        
        Args:
            event: ButtonSelector.SelectionChanged message
        """
        from ccbt.interface.widgets.button_selector import ButtonSelector
        
        if not hasattr(event, "selection_id"):
            return
        
        selection_id = event.selection_id
        selector = event.selector if hasattr(event, "selector") else None
        
        # Determine which selector this is from
        if selector:
            selector_id = getattr(selector, "id", None)
            if selector_id == "graph-sub-selector":
                # Graph sub-selection
                logger.debug("GraphsSectionContainer: Graph sub-selection changed to %s", selection_id)
                self._load_graph_content(selection_id)
                # Also ensure the graph display area is visible
                try:
                    graph_area = self.query_one("#graph-display-area", Container)  # type: ignore[attr-defined]
                    if graph_area:
                        graph_area.display = True  # type: ignore[attr-defined]
                        logger.debug("GraphsSectionContainer: Graph display area is visible")
                    else:
                        logger.warning("GraphsSectionContainer: Could not find graph-display-area")
                except Exception as e:
                    logger.error("GraphsSectionContainer: Error ensuring graph area visibility: %s", e, exc_info=True)
    
    def on_selection_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle ButtonSelector.SelectionChanged message (Textual message handler naming convention).
        
        Textual automatically routes messages to handlers named on_<message_class_name>.
        For ButtonSelector.SelectionChanged, this should be on_selection_changed.
        
        Args:
            event: ButtonSelector.SelectionChanged message
        """
        from ccbt.interface.widgets.button_selector import ButtonSelector
        
        # Verify this is a SelectionChanged message from ButtonSelector
        if not isinstance(event, ButtonSelector.SelectionChanged):
            return
        
        if not hasattr(event, "selection_id"):
            return
        
        selection_id = event.selection_id
        selector = getattr(event, "selector", None)
        
        # Determine which selector this is from
        if selector:
            selector_id = getattr(selector, "id", None)
            if selector_id == "graph-sub-selector":
                # Graph sub-selection
                logger.debug("GraphsSectionContainer: Graph sub-selection changed to %s (via on_selection_changed)", selection_id)
                self._load_graph_content(selection_id)
                # Also ensure the graph display area is visible
                try:
                    graph_area = self.query_one("#graph-display-area", Container)  # type: ignore[attr-defined]
                    if graph_area:
                        graph_area.display = True  # type: ignore[attr-defined]
                        logger.debug("GraphsSectionContainer: Graph display area is visible")
                    else:
                        logger.warning("GraphsSectionContainer: Could not find graph-display-area")
                except Exception as e:
                    logger.error("GraphsSectionContainer: Error ensuring graph area visibility: %s", e, exc_info=True)

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update graphs section with statistics.

        Args:
            stats: Dictionary containing global statistics
        """
        # Note: _summary_cards and _quick_stats are not part of GraphsSectionContainer
        # They may exist in other containers, but not here
        
        # Update active graph widget - try multiple widget types
        try:
            graph_area = self.query_one("#graph-display-area", Container)  # type: ignore[attr-defined]
            
            # Try PerformanceGraphWidget first (which wraps UploadDownloadGraphWidget)
            from ccbt.interface.widgets.graph_widget import PerformanceGraphWidget, UploadDownloadGraphWidget
            try:
                perf_widget = graph_area.query_one(PerformanceGraphWidget)  # type: ignore[attr-defined]
                if perf_widget:
                    perf_widget.update_from_stats(stats)
                    logger.debug("GraphsSectionContainer: Updated PerformanceGraphWidget from stats")
                    return
            except Exception as e:
                logger.debug("GraphsSectionContainer: PerformanceGraphWidget not found: %s", e)
            
            # Fallback: Try UploadDownloadGraphWidget directly
            try:
                graph_widget = graph_area.query_one(UploadDownloadGraphWidget)  # type: ignore[attr-defined]
                if graph_widget:
                    graph_widget.update_from_stats(stats)
                    logger.debug("GraphsSectionContainer: Updated UploadDownloadGraphWidget from stats")
                    return
            except Exception as e:
                logger.debug("GraphsSectionContainer: UploadDownloadGraphWidget not found: %s", e)
            
            # Try other graph widget types that might support update_from_stats
            try:
                from ccbt.interface.widgets.graph_widget import DiskGraphWidget, NetworkGraphWidget, SystemResourcesGraphWidget
                for widget_class in [DiskGraphWidget, NetworkGraphWidget, SystemResourcesGraphWidget]:
                    try:
                        widget = graph_area.query_one(widget_class)  # type: ignore[attr-defined]
                        if widget and hasattr(widget, "update_from_stats"):
                            widget.update_from_stats(stats)  # type: ignore[attr-defined]
                            logger.debug("GraphsSectionContainer: Updated %s from stats", widget_class.__name__)
                            return
                    except Exception:
                        continue
            except Exception as e:
                logger.debug("GraphsSectionContainer: Error querying other graph widgets: %s", e)
                
        except Exception as e:
            # Graph widget may not be mounted or may be a different type
            logger.debug("GraphsSectionContainer: Error updating graph widgets from stats: %s", e)
