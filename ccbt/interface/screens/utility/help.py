"""Help screen for displaying keyboard shortcuts and help information."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from textual.screen import ComposeResult
else:
    try:
        from textual.screen import ComposeResult
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Vertical
    from textual.screen import Screen
    from textual.widgets import Footer, Header, Static
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

    class Vertical:  # type: ignore[no-redef]
        """Vertical layout widget stub."""

from rich.panel import Panel


class HelpScreen(Screen):  # type: ignore[misc]
    """Screen to display keyboard shortcuts and help information."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #shortcuts_table {
        height: 1fr;
        min-height: 10;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the help screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="shortcuts_table")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the help screen and populate shortcuts."""
        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh help content."""
        try:
            from rich.table import Table

            content = self.query_one("#content", Static)
            shortcuts_table = self.query_one("#shortcuts_table", Static)

            # Build help content
            help_text = (
                "[bold]ccBitTorrent Terminal Dashboard Help[/bold]\n\n"
                "This dashboard provides a comprehensive interface for managing BitTorrent downloads.\n"
                "Use keyboard shortcuts to quickly access features and manage torrents.\n"
            )

            content.update(Panel(help_text, title="Help"))

            # Build shortcuts table
            table = Table(title="Keyboard Shortcuts", expand=True)
            table.add_column("Key", style="cyan", ratio=1)
            table.add_column("Action", style="green", ratio=2)
            table.add_column("Description", style="dim", ratio=3)

            # Main dashboard shortcuts
            table.add_row("q", "Quit", "Exit the dashboard")
            table.add_row("p", "Pause", "Pause selected torrent")
            table.add_row("r", "Resume", "Resume selected torrent")
            table.add_row(
                "s",
                "System Resources",
                "View system resource usage (when no torrent selected)",
            )
            table.add_row("i", "Quick Add", "Quick add torrent (file path or magnet)")
            table.add_row("o", "Advanced Add", "Advanced add torrent with options")
            table.add_row("b", "Browse", "Browse for torrent file")
            table.add_row("g", "Global Config", "Open global configuration")
            table.add_row("t", "Torrent Config", "Open per-torrent configuration")
            table.add_row("x", "Security Scan", "Run security scan")
            table.add_row("?", "Help", "Show this help screen")

            # Monitoring screens
            table.add_row("", "", "")
            table.add_row("[bold]Monitoring Screens[/bold]", "", "")
            table.add_row("s", "System Resources", "View system resource usage")
            table.add_row("m", "Performance Metrics", "View performance metrics")
            table.add_row("n", "Network Quality", "View network quality metrics")
            table.add_row("h", "Historical Trends", "View historical trends")
            table.add_row("a", "Alerts Dashboard", "View alerts and rules")
            table.add_row("e", "Metrics Explorer", "Explore metrics")

            # Protocol management (Ctrl+ combinations)
            table.add_row("", "", "")
            table.add_row("[bold]Protocol Management[/bold]", "", "")
            table.add_row(
                "Ctrl+X", "Xet Management", "Manage Xet protocol (deduplication)"
            )
            table.add_row("Ctrl+I", "IPFS Management", "Manage IPFS protocol")
            table.add_row("Ctrl+S", "SSL Config", "Configure SSL/TLS settings")
            table.add_row("Ctrl+P", "Proxy Config", "Configure proxy settings")
            table.add_row("Ctrl+R", "Scrape Results", "View cached scrape results")
            table.add_row(
                "Ctrl+N", "NAT Management", "Manage NAT traversal (port mapping)"
            )
            table.add_row("Ctrl+U", "uTP Config", "Configure uTP transport protocol")

            # Navigation
            table.add_row("", "", "")
            table.add_row("[bold]Navigation[/bold]", "", "")
            table.add_row("Ctrl+M", "Navigation Menu", "Open navigation menu")
            table.add_row("↑/↓", "Navigate", "Navigate torrent/peer lists")
            table.add_row("Enter", "Select", "Select torrent or open details")
            table.add_row("Escape", "Back", "Go back or close screen")
            table.add_row("/", "Filter", "Filter torrents by name/status")
            table.add_row(
                "Delete", "Remove", "Remove selected torrent (with confirmation)"
            )

            shortcuts_table.update(Panel(table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading help: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_back(self) -> None:  # pragma: no cover
        """Go back to main dashboard."""
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def action_quit(self) -> None:  # pragma: no cover
        """Quit the application."""
        self.app.exit()  # type: ignore[attr-defined]

