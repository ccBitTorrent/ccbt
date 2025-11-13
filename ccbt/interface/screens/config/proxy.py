"""Proxy configuration screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Footer, Header, Input, Static
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
            Input,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Horizontal = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Button = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Input = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.config.config import ConfigManager, get_config
from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import ConfigScreen


class ProxyConfigScreen(ConfigScreen):  # type: ignore[misc]
    """Screen to manage proxy configuration."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #status_panel {
        height: auto;
        min-height: 8;
    }
    #performance_metrics {
        height: 1fr;
        min-height: 8;
    }
    #stats_panel {
        height: auto;
        min-height: 8;
    }
    #actions {
        height: 3;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("t", "test", "Test Connection"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the proxy configuration screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="stats_panel")
            with Horizontal(id="actions"):
                yield Button("Set Proxy", id="set_proxy", variant="primary")
                yield Button("Test Connection", id="test", variant="default")
                yield Button("Disable", id="disable", variant="warning")
                yield Button("Refresh", id="refresh", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the proxy configuration screen and initialize command executor."""
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
        # Initial data load
        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh proxy configuration status."""
        try:
            # Import ProxyClient
            try:
                from ccbt.proxy.client import ProxyClient
            except ImportError:
                ProxyClient = None  # type: ignore[assignment, misc]

            status_panel = self.query_one("#status_panel", Static)
            stats_panel = self.query_one("#stats_panel", Static)

            # Get configuration
            try:
                config = get_config()
            except Exception:
                config_manager = ConfigManager()
                config = config_manager.config

            proxy_config = config.proxy

            # Build status panel
            status_lines = [
                "[bold]Proxy Configuration Status[/bold]\n",
                f"Enabled: {'[green]Yes[/green]' if proxy_config.enable_proxy else '[red]No[/red]'}",
                f"Type: {proxy_config.proxy_type or 'N/A'}",
                f"Host: {proxy_config.proxy_host or 'N/A'}",
                f"Port: {proxy_config.proxy_port or 'N/A'}",
                f"Username: {proxy_config.proxy_username or '[dim]Not set[/dim]'}",
                f"Password: {'[dim]***[/dim]' if proxy_config.proxy_password else '[dim]Not set[/dim]'}",
                f"For Trackers: {'[green]Yes[/green]' if proxy_config.proxy_for_trackers else '[red]No[/red]'}",
                f"For Peers: {'[green]Yes[/green]' if proxy_config.proxy_for_peers else '[red]No[/red]'}",
                f"For WebSeeds: {'[green]Yes[/green]' if proxy_config.proxy_for_webseeds else '[red]No[/red]'}",
            ]

            if proxy_config.proxy_bypass_list:
                status_lines.append(
                    f"Bypass List: {', '.join(proxy_config.proxy_bypass_list)}"
                )
            else:
                status_lines.append("Bypass List: [dim]None[/dim]")

            status_panel.update(Panel("\n".join(status_lines), title="Proxy Status"))

            # Build statistics panel
            try:
                if ProxyClient is None:
                    stats_panel.update(
                        Panel(
                            "Proxy statistics not available (ProxyClient not found).",
                            title="Proxy Statistics",
                            border_style="yellow",
                        )
                    )
                    return
                proxy_client = ProxyClient()
                stats = proxy_client.get_stats()

                if stats.connections_total > 0:
                    stats_table = Table(title="Proxy Statistics", expand=True)
                    stats_table.add_column("Metric", style="cyan", ratio=2)
                    stats_table.add_column("Value", style="green", ratio=3)

                    stats_table.add_row(
                        "Total Connections", str(stats.connections_total)
                    )
                    stats_table.add_row(
                        "Successful", f"[green]{stats.connections_successful}[/green]"
                    )
                    stats_table.add_row(
                        "Failed", f"[red]{stats.connections_failed}[/red]"
                    )
                    stats_table.add_row("Auth Failures", str(stats.auth_failures))
                    stats_table.add_row("Timeouts", str(stats.timeouts))
                    stats_table.add_row("Bytes Sent", f"{stats.bytes_sent:,}")
                    stats_table.add_row("Bytes Received", f"{stats.bytes_received:,}")

                    stats_panel.update(Panel(stats_table))
                else:
                    stats_panel.update(
                        Panel(
                            "No proxy statistics available yet.",
                            title="Proxy Statistics",
                            border_style="yellow",
                        )
                    )
            except Exception:
                stats_panel.update(
                    Panel(
                        "Proxy statistics not available.",
                        title="Proxy Statistics",
                        border_style="yellow",
                    )
                )

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading proxy configuration: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_set_proxy(self) -> None:  # pragma: no cover
        """Show proxy configuration form."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show multi-step form for proxy configuration
        # Step 1: Host
        input_widget = Input(
            placeholder="Enter proxy host (e.g., proxy.example.com)", id="proxy_host"
        )
        self.mount(input_widget)
        input_widget.focus()

    async def action_test(self) -> None:  # pragma: no cover
        """Test proxy connection."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "proxy test"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        f"Proxy connection test successful: {msg}",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Proxy connection test failed: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_disable(self) -> None:  # pragma: no cover
        """Disable proxy."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "proxy disable"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "Proxy disabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to disable proxy: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh proxy configuration status."""
        await self._refresh_data()

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submissions for proxy configuration."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        input_id = message.input.id
        value = message.value.strip()
        message.input.display = False

        # Multi-step proxy configuration
        if input_id == "proxy_host":
            if value:
                self._proxy_host = value  # type: ignore[attr-defined]
                port_input = Input(
                    placeholder="Enter proxy port (e.g., 8080)", id="proxy_port"
                )
                self.mount(port_input)
                port_input.focus()

        elif input_id == "proxy_port":
            if value and hasattr(self, "_proxy_host"):
                try:
                    port = int(value)
                    self._proxy_port = port  # type: ignore[attr-defined]
                    # Ask for proxy type
                    type_input = Input(
                        placeholder="Enter proxy type (http, socks4, socks5)",
                        id="proxy_type",
                    )
                    self.mount(type_input)
                    type_input.focus()
                except ValueError:
                    if self.statusbar:
                        self.statusbar.update(
                            Panel(
                                "Invalid port number. Please enter a number.",
                                title="Error",
                                border_style="red",
                            )
                        )

        elif input_id == "proxy_type":
            if value and hasattr(self, "_proxy_host") and hasattr(self, "_proxy_port"):
                if value.lower() in ["http", "socks4", "socks5"]:
                    self._proxy_type = value.lower()  # type: ignore[attr-defined]
                    # Ask for username (optional)
                    user_input = Input(
                        placeholder="Enter username (optional, press Enter to skip)",
                        id="proxy_username",
                    )
                    self.mount(user_input)
                    user_input.focus()
                elif self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "Invalid proxy type. Use: http, socks4, or socks5",
                            title="Error",
                            border_style="red",
                        )
                    )

        elif input_id == "proxy_username":
            if (
                hasattr(self, "_proxy_host")
                and hasattr(self, "_proxy_port")
                and hasattr(self, "_proxy_type")
            ):
                self._proxy_username = value if value else None  # type: ignore[attr-defined]
                # Ask for password (optional)
                pass_input = Input(
                    placeholder="Enter password (optional, press Enter to skip)",
                    id="proxy_password",
                    password=True,
                )
                self.mount(pass_input)
                pass_input.focus()

        elif input_id == "proxy_password":
            if (
                hasattr(self, "_proxy_host")
                and hasattr(self, "_proxy_port")
                and hasattr(self, "_proxy_type")
            ):
                self._proxy_password = value if value else None  # type: ignore[attr-defined]
                # Build proxy set command
                cmd_parts = [
                    "proxy set",
                    f"--host {self._proxy_host}",  # type: ignore[attr-defined]
                    f"--port {self._proxy_port}",  # type: ignore[attr-defined]
                    f"--type {self._proxy_type}",  # type: ignore[attr-defined]
                ]
                if hasattr(self, "_proxy_username") and self._proxy_username:  # type: ignore[attr-defined]
                    cmd_parts.append(f"--user {self._proxy_username}")  # type: ignore[attr-defined]
                if hasattr(self, "_proxy_password") and self._proxy_password:  # type: ignore[attr-defined]
                    cmd_parts.append(f"--pass {self._proxy_password}")  # type: ignore[attr-defined]

                # Use defaults for trackers/peers/webseeds (can be enhanced later)
                cmd = " ".join(cmd_parts)

                success, msg, _ = await self._command_executor.execute_click_command(
                    cmd
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"Proxy configuration set: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to set proxy: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )

                # Clean up stored values
                for attr in [
                    "_proxy_host",
                    "_proxy_port",
                    "_proxy_type",
                    "_proxy_username",
                    "_proxy_password",
                ]:
                    if hasattr(self, attr):
                        delattr(self, attr)

                await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "set_proxy":
            await self.action_set_proxy()
        elif event.button.id == "test":
            await self.action_test()
        elif event.button.id == "disable":
            await self.action_disable()
        elif event.button.id == "refresh":
            await self.action_refresh()

