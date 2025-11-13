"""Navigation menu screen for accessing all screens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.screen import ComposeResult
else:
    try:
        from textual.screen import ComposeResult
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Horizontal, Vertical
    from textual.screen import Screen
    from textual.widgets import DataTable, Footer, Header, Static
except ImportError:
    # Fallback for when Textual is not available
    class Screen:  # type: ignore[no-redef]
        """Screen class stub."""

    class Header:  # type: ignore[no-redef]
        """Header widget stub."""

    class Footer:  # type: ignore[no-redef]
        """Footer widget stub."""

    class Static:  # type: ignore[no-redef]
        """Static widget stub."""

    class DataTable:  # type: ignore[no-redef]
        """DataTable widget stub."""

        cursor_row_key = None

    class Horizontal:  # type: ignore[no-redef]
        """Horizontal layout widget stub."""

    class Vertical:  # type: ignore[no-redef]
        """Vertical layout widget stub."""

from rich.panel import Panel


class NavigationMenuScreen(Screen):  # type: ignore[misc]
    """Navigation menu/sidebar for accessing all screens."""

    CSS = """
    #menu_table {
        height: 1fr;
    }
    #info {
        height: 1fr;
        min-height: 5;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("enter", "select", "Select Screen"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the navigation menu screen."""
        yield Header()
        with Horizontal(), Vertical():
            yield DataTable(id="menu_table", zebra_stripes=True)
            yield Static(id="info")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the navigation menu and populate options."""
        menu_table = self.query_one("#menu_table", DataTable)
        info = self.query_one("#info", Static)

        menu_table.add_columns("Category", "Screen", "Shortcut")

        # Monitoring screens
        menu_table.add_row(
            "Monitoring", "System Resources", "s", key="system_resources"
        )
        menu_table.add_row(
            "Monitoring", "Performance Metrics", "m", key="performance_metrics"
        )
        menu_table.add_row("Monitoring", "Network Quality", "n", key="network_quality")
        menu_table.add_row(
            "Monitoring", "Historical Trends", "h", key="historical_trends"
        )
        menu_table.add_row(
            "Monitoring", "Alerts Dashboard", "a", key="alerts_dashboard"
        )
        menu_table.add_row(
            "Monitoring", "Metrics Explorer", "e", key="metrics_explorer"
        )
        menu_table.add_row("Monitoring", "DHT Metrics", "d", key="dht_metrics")
        menu_table.add_row("Monitoring", "Queue Metrics", "u", key="queue_metrics")
        menu_table.add_row("Monitoring", "Disk I/O Metrics", "j", key="disk_io_metrics")
        menu_table.add_row("Monitoring", "Tracker Metrics", "k", key="tracker_metrics")
        menu_table.add_row(
            "Monitoring", "Performance Analysis", "f", key="performance_analysis"
        )

        # Configuration screens
        menu_table.add_row("Configuration", "Global Config", "g", key="global_config")
        menu_table.add_row("Configuration", "Torrent Config", "t", key="torrent_config")

        # Protocol management screens
        menu_table.add_row(
            "Protocols", "Xet Management", "Ctrl+X", key="xet_management"
        )
        menu_table.add_row(
            "Protocols", "IPFS Management", "Ctrl+I", key="ipfs_management"
        )
        menu_table.add_row("Protocols", "SSL Config", "Ctrl+S", key="ssl_config")
        menu_table.add_row("Protocols", "Proxy Config", "Ctrl+P", key="proxy_config")
        menu_table.add_row(
            "Protocols", "Scrape Results", "Ctrl+R", key="scrape_results"
        )
        menu_table.add_row(
            "Protocols", "NAT Management", "Ctrl+N", key="nat_management"
        )
        menu_table.add_row("Protocols", "uTP Config", "Ctrl+U", key="utp_config")

        menu_table.cursor_type = "row"
        menu_table.focus()

        info.update(
            Panel(
                "Select a screen to open. Press Enter to navigate, Escape to go back.",
                title="Navigation Menu",
            )
        )

    async def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle menu selection."""
        await self._navigate_to_screen()

    async def action_select(self) -> None:  # pragma: no cover
        """Select and navigate to the selected screen."""
        await self._navigate_to_screen()

    async def on_key(self, event: Any) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle key presses."""
        if event.key == "enter":
            await self.action_select()
        # Other keys are handled by Textual's default behavior

    async def _navigate_to_screen(self) -> None:  # pragma: no cover
        """Navigate to selected screen."""
        menu_table = self.query_one("#menu_table", DataTable)
        if hasattr(menu_table, "cursor_row_key") and menu_table.cursor_row_key:
            screen_key = str(menu_table.cursor_row_key)

            # Map screen keys to action methods
            screen_map: dict[str, str] = {
                "system_resources": "system_resources",
                "performance_metrics": "performance_metrics",
                "network_quality": "network_quality",
                "historical_trends": "historical_trends",
                "alerts_dashboard": "alerts_dashboard",
                "metrics_explorer": "metrics_explorer",
                "dht_metrics": "dht_metrics",
                "queue_metrics": "queue_metrics",
                "disk_io_metrics": "disk_io_metrics",
                "tracker_metrics": "tracker_metrics",
                "performance_analysis": "performance_analysis",
                "global_config": "global_config",
                "torrent_config": "torrent_config",
                "xet_management": "xet_management",
                "ipfs_management": "ipfs_management",
                "ssl_config": "ssl_config",
                "proxy_config": "proxy_config",
                "scrape_results": "scrape_results",
                "nat_management": "nat_management",
                "utp_config": "utp_config",
            }

            action_name = screen_map.get(screen_key)
            if action_name:
                # Get the dashboard app (the root app, not this screen)
                app = self.app  # type: ignore[attr-defined]
                # The root app should be TerminalDashboard
                if hasattr(app, f"action_{action_name}"):
                    action_method = getattr(app, f"action_{action_name}")
                    # Close navigation menu before navigating
                    self.app.pop_screen()  # type: ignore[attr-defined]
                    # Call the action on the dashboard
                    await action_method()

    async def action_back(self) -> None:  # pragma: no cover
        """Go back to main dashboard."""
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def action_quit(self) -> None:  # pragma: no cover
        """Quit the application."""
        self.app.exit()  # type: ignore[attr-defined]

