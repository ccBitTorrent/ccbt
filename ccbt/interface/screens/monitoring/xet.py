"""Xet management monitoring screen."""

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
from ccbt.interface.screens.base import ConfirmationDialog, MonitoringScreen


class XetManagementScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to manage Xet protocol (content-defined chunking and deduplication)."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #status_panel {
        height: auto;
        min-height: 8;
    }
    #stats_table {
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
        ("e", "enable", "Enable"),
        ("d", "disable", "Disable"),
        ("c", "cache_info", "Cache Info"),
        ("x", "cleanup", "Cleanup"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the Xet management screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="stats_table")
            yield Static(id="performance_metrics")
            with Horizontal(id="actions"):
                yield Button("Enable", id="enable", variant="primary")
                yield Button("Disable", id="disable", variant="default")
                yield Button("Refresh", id="refresh", variant="default")
                yield Button("Cache Info", id="cache_info", variant="default")
                yield Button("Cleanup", id="cleanup", variant="warning")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh Xet protocol status and statistics."""
        try:
            if not hasattr(self, "_command_executor") or self._command_executor is None:
                self._command_executor = CommandExecutor(self.session)

            status_panel = self.query_one("#status_panel", Static)
            stats_table = self.query_one("#stats_table", Static)
            performance_metrics = self.query_one("#performance_metrics", Static)

            config_result = await self._command_executor.execute_command("xet.get_config")
            protocol_result = await self._command_executor.execute_command("protocol.get_xet")
            config_data = config_result.data if config_result.success else {}
            protocol_data = protocol_result.data if protocol_result.success else {}

            # Build status panel
            status_lines = [
                "[bold]Xet Protocol Status[/bold]\n",
                f"Enabled: {'[green]Yes[/green]' if config_data.get('protocol_enabled') else '[red]No[/red]'}",
                f"Workspace sync: {'[green]Enabled[/green]' if config_data.get('workspace_sync_enabled') else '[yellow]Disabled[/yellow]'}",
                f"Default sync mode: {config_data.get('default_sync_mode', 'N/A')}",
                f"Check interval: {config_data.get('check_interval', 'N/A')}",
                f"XET port: {config_data.get('xet_port', 'N/A')}",
            ]

            protocol = protocol_data.get("protocol")
            if protocol is not None:
                protocol_enabled = (
                    protocol.get("enabled", False)
                    if isinstance(protocol, dict)
                    else getattr(protocol, "enabled", False)
                )
                supports_dht = (
                    protocol.get("supports_dht", False)
                    if isinstance(protocol, dict)
                    else getattr(protocol, "supports_dht", False)
                )
                supports_pex = (
                    protocol.get("supports_pex", False)
                    if isinstance(protocol, dict)
                    else getattr(protocol, "supports_pex", False)
                )
                status_lines.append("\n[bold]Runtime Status:[/bold]")
                status_lines.append(
                    f"  Protocol enabled: {'[green]Yes[/green]' if protocol_enabled else '[yellow]No[/yellow]'}"
                )
                status_lines.append(
                    f"  Supports DHT: {'[green]Yes[/green]' if supports_dht else '[yellow]No[/yellow]'}"
                )
                status_lines.append(
                    f"  Supports PEX: {'[green]Yes[/green]' if supports_pex else '[yellow]No[/yellow]'}"
                )
            else:
                status_lines.append("\n[yellow]Runtime Status:[/yellow]")
                status_lines.append(
                    "  Protocol not active (session may not be running)"
                )

            status_panel.update(
                Panel("\n".join(status_lines), title="Xet Protocol Status")
            )

            # Build statistics table if enabled
            if config_data.get("protocol_enabled"):
                try:
                    stats_result = await self._command_executor.execute_command(
                        "xet.cache_stats"
                    )
                    if hasattr(stats_result, "success"):
                        if not stats_result.success:
                            msg = stats_result.error or "Failed to load cache statistics"
                            raise RuntimeError(msg)
                        stats = (stats_result.data or {}).get("stats", {})
                    else:
                        success, message, data = stats_result
                        if not success:
                            raise RuntimeError(message or "Failed to load cache statistics")
                        payload = data if isinstance(data, dict) else {}
                        stats = payload.get("stats", {})

                    table = Table(title="Xet Deduplication Cache Statistics", expand=True)
                    table.add_column("Metric", style="cyan", ratio=2)
                    table.add_column("Value", style="green", ratio=3)
                    table.add_row("Total chunks", str(stats.get("total_chunks", 0)))
                    table.add_row("Unique chunks", str(stats.get("unique_chunks", 0)))
                    table.add_row("Total size (bytes)", str(stats.get("total_size", 0)))
                    table.add_row("Cache size (bytes)", str(stats.get("cache_size", 0)))
                    table.add_row("Average chunk size", str(stats.get("avg_chunk_size", 0)))
                    dedup_ratio = stats.get("dedup_ratio", 0.0)
                    table.add_row("Deduplication ratio", f"{dedup_ratio:.2f}")

                    stats_table.update(Panel(table))
                    await self._refresh_xet_performance_metrics(performance_metrics, stats)
                except Exception as e:
                    stats_table.update(
                        Panel(
                            f"Error loading statistics: {e}",
                            title="Error",
                            border_style="red",
                        )
                    )
                    performance_metrics.update("")
            else:
                stats_table.update(
                    Panel(
                        "Xet protocol is disabled. Enable it to view statistics.",
                        title="Statistics",
                        border_style="yellow",
                    )
                )
                performance_metrics.update("")

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading Xet status: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def _refresh_xet_performance_metrics(
        self, widget: Static, cache_stats: dict[str, Any]
    ) -> None:  # pragma: no cover
        """Refresh Xet performance metrics."""
        try:
            table = Table(
                title="Xet Performance Metrics",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            total_chunks = cache_stats.get("total_chunks", 0)
            unique_chunks = cache_stats.get("unique_chunks", 0)
            total_size = cache_stats.get("total_size", 0)
            cache_size = cache_stats.get("cache_size", 0)
            dedup_ratio = cache_stats.get("dedup_ratio", 0.0)

            def format_bytes(b: int) -> str:
                if b >= 1024 * 1024 * 1024:
                    return f"{b / (1024**3):.2f} GB"
                if b >= 1024 * 1024:
                    return f"{b / (1024**2):.2f} MB"
                if b >= 1024:
                    return f"{b / 1024:.2f} KB"
                return f"{b} B"

            # Deduplication efficiency
            if total_chunks > 0:
                dedup_efficiency = (
                    ((total_chunks - unique_chunks) / total_chunks * 100)
                    if total_chunks > 0
                    else 0.0
                )
                table.add_row("Deduplication Efficiency", f"{dedup_efficiency:.1f}%")

            # Space savings
            if total_size > 0 and cache_size > 0:
                space_saved = total_size - cache_size
                savings_percent = (
                    (space_saved / total_size * 100) if total_size > 0 else 0.0
                )
                table.add_row(
                    "Space Saved",
                    f"{format_bytes(space_saved)} ({savings_percent:.1f}%)",
                )

            # Deduplication ratio
            table.add_row("Deduplication Ratio", f"{dedup_ratio:.2f}x")

            # Average chunk size
            avg_chunk_size = cache_stats.get("avg_chunk_size", 0)
            if avg_chunk_size > 0:
                table.add_row("Average Chunk Size", format_bytes(avg_chunk_size))

            widget.update(Panel(table))
        except Exception:
            widget.update("")

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

    async def action_enable(self) -> None:  # pragma: no cover
        """Enable Xet protocol."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        result = await self._command_executor.execute_command("xet.enable")
        if result.success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Xet protocol enabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
        elif self.statusbar:
            self.statusbar.update(
                Panel(
                    f"Failed to enable Xet protocol: {result.error}",
                    title="Error",
                    border_style="red",
                )
            )
        await self._refresh_data()

    async def action_disable(self) -> None:  # pragma: no cover
        """Disable Xet protocol."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        result = await self._command_executor.execute_command("xet.disable")
        if result.success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Xet protocol disabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
        elif self.statusbar:
            self.statusbar.update(
                Panel(
                    f"Failed to disable Xet protocol: {result.error}",
                    title="Error",
                    border_style="red",
                )
            )
        await self._refresh_data()

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh Xet status and statistics."""
        await self._refresh_data()

    async def action_cache_info(self) -> None:  # pragma: no cover
        """Show cache information dialog."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        result = await self._command_executor.execute_command("xet.cache_info", limit=20)
        if hasattr(result, "success"):
            success = result.success
            message = result.error
            data = result.data if result.success else {}
        else:
            success, message, data = result
            data = data if isinstance(data, dict) else {}

        if not success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Failed to get cache info: {message}",
                        title="Error",
                        border_style="red",
                    )
                )
            return

        stats = data.get("stats", {})
        chunks = data.get("sample_chunks", [])
        lines = [
            "[bold]Cache Overview[/bold]",
            f"Total chunks: {stats.get('total_chunks', 0)}",
            f"Cache size: {stats.get('cache_size', 0)} bytes",
            f"Dedup ratio: {stats.get('dedup_ratio', 0.0):.2f}",
            "",
            "[bold]Recent chunks[/bold]",
        ]
        for chunk in chunks[:10]:
            chunk_hash = str(chunk.get("hash", ""))
            lines.append(
                f"- {chunk_hash[:16]}... size={chunk.get('size', 0)} refs={chunk.get('ref_count', 0)}"
            )
        content = self.query_one("#stats_table", Static)
        content.update(
            Panel(
                "\n".join(lines),
                title="Cache Information",
                border_style="cyan",
            )
        )
        if self.statusbar:
            self.statusbar.update(
                Panel(
                    "Cache information refreshed",
                    title="Success",
                    border_style="green",
                )
            )

    async def action_cleanup(self) -> None:  # pragma: no cover
        """Clean up old/unused chunks."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show confirmation dialog
        confirmation = ConfirmationDialog(
            "Clean up old/unused chunks? This will remove chunks that haven't been accessed recently.",
        )
        result = await self.app.push_screen(confirmation)  # type: ignore[attr-defined]

        if result:
            success, message, _ = await self._command_executor.execute_click_command(
                "xet cleanup"
            )
            if self.statusbar:
                if success:
                    self.statusbar.update(
                        Panel(
                            "Cleanup completed successfully",
                            title="Success",
                            border_style="green",
                        )
                    )
                else:
                    self.statusbar.update(
                        Panel(
                            f"Cleanup failed: {message}",
                            title="Error",
                            border_style="red",
                        )
                    )
            await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "enable":
            await self.action_enable()
        elif event.button.id == "disable":
            await self.action_disable()
        elif event.button.id == "refresh":
            await self.action_refresh()
        elif event.button.id == "cache_info":
            await self.action_cache_info()
        elif event.button.id == "cleanup":
            await self.action_cleanup()

