"""Scrape results monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

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

from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import MonitoringScreen


class ScrapeResultsScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to view all cached scrape results."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #results_table {
        height: 1fr;
        min-height: 10;
    }
    #actions {
        height: 3;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the scrape results screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="results_table")
            with Horizontal(id="actions"):
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Scrape All", id="scrape_all", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and initialize command executor."""
        # Initialize command executor
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Try to get statusbar reference if available
        try:
            self.statusbar = self.query_one("#statusbar", Static)
        except Exception:
            # Statusbar not available, try to get from app if it's TerminalDashboard
            try:
                app = self.app
                if hasattr(app, "statusbar"):
                    self.statusbar = app.statusbar
            except Exception:
                self.statusbar = None
        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh scrape results from cache."""
        try:
            status_panel = self.query_one("#status_panel", Static)
            results_table = self.query_one("#results_table", Static)

            # Get all cached scrape results
            # CRITICAL FIX: Handle both AsyncSessionManager and DaemonInterfaceAdapter
            scrape_results = []
            if hasattr(self.session, "scrape_cache_lock") and hasattr(self.session, "scrape_cache"):
                # Direct session manager access
                async with self.session.scrape_cache_lock:
                    scrape_results = list(self.session.scrape_cache.values())
            elif hasattr(self.session, "_executor_adapter"):
                # DaemonInterfaceAdapter - use executor adapter to get scrape results
                from ccbt.executor.session_adapter import DaemonSessionAdapter
                if isinstance(self.session._executor_adapter, DaemonSessionAdapter):
                    # Use IPC client to get scrape results
                    try:
                        scrape_list_response = await self.session._executor_adapter.list_scrape_results()
                        if scrape_list_response and hasattr(scrape_list_response, "results"):
                            scrape_results = scrape_list_response.results
                    except Exception as e:
                        logger.debug("Error getting scrape results via executor: %s", e)
                        # Fallback: try to get via command executor
                        if hasattr(self, "_command_executor") and self._command_executor:
                            try:
                                result = await self._command_executor.execute_command("scrape.list")
                                if result and hasattr(result, "results"):
                                    scrape_results = result.results
                            except Exception:
                                pass

            # Build status panel
            status_lines = [
                "[bold]Scrape Results Cache[/bold]\n",
                f"Total cached results: {len(scrape_results)}",
                "\n[dim]Scrape results show tracker statistics (seeders, leechers, completed downloads).[/dim]",
                "[dim]Results are cached to avoid excessive tracker requests.[/dim]",
            ]

            status_panel.update(
                Panel("\n".join(status_lines), title="Scrape Cache Status")
            )

            # Build results table
            if scrape_results:
                table = Table(title="Cached Scrape Results", expand=True)
                table.add_column("Info Hash", style="cyan", ratio=3)
                table.add_column("Seeders", style="green", ratio=1)
                table.add_column("Leechers", style="yellow", ratio=1)
                table.add_column("Completed", style="blue", ratio=1)
                table.add_column("Scrape Count", style="magenta", ratio=1)
                table.add_column("Last Scrape", style="dim", ratio=2)

                # Sort by last scrape time (most recent first)
                sorted_results = sorted(
                    scrape_results,
                    key=lambda r: r.last_scrape_time
                    if hasattr(r, "last_scrape_time")
                    else 0,
                    reverse=True,
                )

                for result in sorted_results[:50]:  # Show top 50
                    info_hash_hex = (
                        result.info_hash.hex()
                        if hasattr(result, "info_hash")
                        else "Unknown"
                    )
                    seeders = (
                        str(result.seeders) if hasattr(result, "seeders") else "N/A"
                    )
                    leechers = (
                        str(result.leechers) if hasattr(result, "leechers") else "N/A"
                    )
                    completed = (
                        str(result.completed) if hasattr(result, "completed") else "N/A"
                    )
                    scrape_count = (
                        str(result.scrape_count)
                        if hasattr(result, "scrape_count")
                        else "0"
                    )
                    last_scrape = (
                        f"{result.last_scrape_time:.0f}s ago"
                        if hasattr(result, "last_scrape_time")
                        and result.last_scrape_time > 0
                        else "Never"
                    )

                    table.add_row(
                        info_hash_hex[:40] + "..."
                        if len(info_hash_hex) > 40
                        else info_hash_hex,
                        seeders,
                        leechers,
                        completed,
                        scrape_count,
                        last_scrape,
                    )

                results_table.update(Panel(table))
            else:
                results_table.update(
                    Panel(
                        "No cached scrape results available.\n\n"
                        "Scrape results are cached when trackers are scraped.\n"
                        "Use 'scrape torrent <info_hash>' to scrape a specific torrent.",
                        title="No Results",
                        border_style="yellow",
                    )
                )

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading scrape results: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh scrape results."""
        await self._refresh_data()

    async def action_scrape_all(self) -> None:  # pragma: no cover
        """Scrape all active torrents."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        # Get all active torrents
        all_status = await self.session.get_status()
        if not all_status:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "No active torrents to scrape",
                        title="Info",
                        border_style="yellow",
                    )
                )
            return

        # Scrape each torrent
        scraped = 0
        failed = 0

        for info_hash_hex in all_status:
            try:
                success, _, _ = await self._command_executor.execute_click_command(
                    f"scrape torrent {info_hash_hex} --force"
                )
                if success:
                    scraped += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        if self.statusbar:
            self.statusbar.update(
                Panel(
                    f"Scraped {scraped} torrents, {failed} failed",
                    title="Scrape All Complete",
                    border_style="green" if failed == 0 else "yellow",
                )
            )

        await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "refresh":
            await self.action_refresh()
        elif event.button.id == "scrape_all":
            await self.action_scrape_all()

