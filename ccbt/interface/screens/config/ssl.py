"""SSL configuration screen."""

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


class SSLConfigScreen(ConfigScreen):  # type: ignore[misc]
    """Screen to manage SSL/TLS configuration."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #status_panel {
        height: auto;
        min-height: 8;
    }
    #config_table {
        height: 1fr;
        min-height: 8;
    }
    #performance_metrics {
        height: 1fr;
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
        ("1", "enable_trackers", "Enable Trackers"),
        ("2", "disable_trackers", "Disable Trackers"),
        ("3", "enable_peers", "Enable Peers"),
        ("4", "disable_peers", "Disable Peers"),
        ("v", "verify_on", "Verify On"),
        ("V", "verify_off", "Verify Off"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the SSL configuration screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="config_table")
            yield Static(id="performance_metrics")
            with Horizontal(id="actions"):
                yield Button("Enable Trackers", id="enable_trackers", variant="primary")
                yield Button(
                    "Disable Trackers", id="disable_trackers", variant="default"
                )
                yield Button("Enable Peers", id="enable_peers", variant="primary")
                yield Button("Disable Peers", id="disable_peers", variant="default")
                yield Button("Set CA Certs", id="set_ca_certs", variant="default")
                yield Button("Set Client Cert", id="set_client_cert", variant="default")
                yield Button("Set Protocol", id="set_protocol", variant="default")
                yield Button("Verify On", id="verify_on", variant="default")
                yield Button("Verify Off", id="verify_off", variant="default")
                yield Button("Refresh", id="refresh", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the SSL configuration screen and initialize command executor."""
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
        """Refresh SSL configuration status."""
        try:
            status_panel = self.query_one("#status_panel", Static)
            config_table = self.query_one("#config_table", Static)
            performance_metrics = self.query_one("#performance_metrics", Static)

            # Get configuration
            try:
                config = get_config()
            except Exception:
                config_manager = ConfigManager()
                config = config_manager.config

            ssl_config = config.security.ssl

            # Build status panel
            status_lines = [
                "[bold]SSL/TLS Configuration Status[/bold]\n",
                f"Tracker SSL: {'[green]Enabled[/green]' if ssl_config.enable_ssl_trackers else '[red]Disabled[/red]'}",
                f"Peer SSL: {'[green]Enabled[/green]' if ssl_config.enable_ssl_peers else '[red]Disabled[/red]'}",
                f"Certificate Verification: {'[green]Enabled[/green]' if ssl_config.ssl_verify_certificates else '[yellow]Disabled[/yellow]'}",
                f"Protocol Version: {ssl_config.ssl_protocol_version}",
                f"CA Certificates: {ssl_config.ssl_ca_certificates or '[dim]System default[/dim]'}",
                f"Client Certificate: {ssl_config.ssl_client_certificate or '[dim]Not set[/dim]'}",
                f"Client Key: {'[dim]Set[/dim]' if ssl_config.ssl_client_key else '[dim]Not set[/dim]'}",
                f"Allow Insecure Peers: {'[yellow]Yes[/yellow]' if ssl_config.ssl_allow_insecure_peers else '[green]No[/green]'}",
            ]

            if ssl_config.ssl_cipher_suites:
                status_lines.append(
                    f"Cipher Suites: {', '.join(ssl_config.ssl_cipher_suites)}"
                )
            else:
                status_lines.append("Cipher Suites: [dim]System default[/dim]")

            status_panel.update(Panel("\n".join(status_lines), title="SSL/TLS Status"))

            # Refresh performance metrics
            await self._refresh_ssl_performance_metrics(performance_metrics, ssl_config)

            # Build configuration table
            table = Table(title="SSL/TLS Configuration", expand=True)
            table.add_column("Setting", style="cyan", ratio=2)
            table.add_column("Current Value", style="green", ratio=3)
            table.add_column("Action", style="yellow", ratio=2)

            table.add_row(
                "Tracker SSL",
                "Enabled" if ssl_config.enable_ssl_trackers else "Disabled",
                "Press 1/2 to toggle",
            )
            table.add_row(
                "Peer SSL",
                "Enabled" if ssl_config.enable_ssl_peers else "Disabled",
                "Press 3/4 to toggle",
            )
            table.add_row(
                "Certificate Verification",
                "Enabled" if ssl_config.ssl_verify_certificates else "Disabled",
                "Press v/V to toggle",
            )
            table.add_row(
                "Protocol Version",
                ssl_config.ssl_protocol_version,
                "Click 'Set Protocol'",
            )
            table.add_row(
                "CA Certificates",
                ssl_config.ssl_ca_certificates or "System default",
                "Click 'Set CA Certs'",
            )
            table.add_row(
                "Client Certificate",
                ssl_config.ssl_client_certificate or "Not set",
                "Click 'Set Client Cert'",
            )

            config_table.update(Panel(table))

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading SSL configuration: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def _refresh_ssl_performance_metrics(
        self, performance_metrics: Static, ssl_config: Any
    ) -> None:  # pragma: no cover
        """Refresh SSL performance metrics display."""
        try:
            # Create a simple metrics table
            metrics_table = Table(title="SSL/TLS Performance Metrics", expand=True)
            metrics_table.add_column("Metric", style="cyan", ratio=2)
            metrics_table.add_column("Value", style="green", ratio=3)

            # For now, show basic status - can be enhanced with actual metrics later
            metrics_table.add_row(
                "Tracker SSL Status",
                "[green]Active[/green]"
                if ssl_config.enable_ssl_trackers
                else "[red]Inactive[/red]",
            )
            metrics_table.add_row(
                "Peer SSL Status",
                "[green]Active[/green]"
                if ssl_config.enable_ssl_peers
                else "[red]Inactive[/red]",
            )
            metrics_table.add_row(
                "Certificate Verification",
                "[green]Enabled[/green]"
                if ssl_config.ssl_verify_certificates
                else "[yellow]Disabled[/yellow]",
            )
            metrics_table.add_row("Protocol Version", ssl_config.ssl_protocol_version)

            # Try to get session metrics if available
            if hasattr(self, "session") and hasattr(self.session, "get_status"):
                try:
                    status = await self.session.get_status()
                    # Look for SSL-related metrics in status
                    # This is a placeholder - actual metrics would come from monitoring
                    metrics_table.add_row("SSL Connections", "N/A")
                    metrics_table.add_row("SSL Errors", "N/A")
                except Exception:
                    # If we can't get metrics, just show N/A
                    metrics_table.add_row("SSL Connections", "N/A")
                    metrics_table.add_row("SSL Errors", "N/A")
            else:
                metrics_table.add_row("SSL Connections", "N/A")
                metrics_table.add_row("SSL Errors", "N/A")

            performance_metrics.update(Panel(metrics_table))

        except Exception as e:
            # Show a simple message if metrics can't be loaded
            try:
                performance_metrics.update(
                    Panel(
                        "Performance metrics unavailable",
                        title="SSL/TLS Performance Metrics",
                        border_style="dim",
                    )
                )
            except Exception:
                pass

    async def action_enable_trackers(self) -> None:  # pragma: no cover
        """Enable SSL for trackers."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl enable-trackers"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "SSL for trackers enabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to enable SSL for trackers: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_disable_trackers(self) -> None:  # pragma: no cover
        """Disable SSL for trackers."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl disable-trackers"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "SSL for trackers disabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to disable SSL for trackers: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_enable_peers(self) -> None:  # pragma: no cover
        """Enable SSL for peers."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl enable-peers"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "SSL for peers enabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to enable SSL for peers: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_disable_peers(self) -> None:  # pragma: no cover
        """Disable SSL for peers."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl disable-peers"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "SSL for peers disabled successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to disable SSL for peers: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_set_ca_certs(self) -> None:  # pragma: no cover
        """Set CA certificates path."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        input_widget = Input(
            placeholder="Enter CA certificates path (file or directory)",
            id="ssl_ca_certs_path",
        )
        self.mount(input_widget)
        input_widget.focus()

    async def action_set_client_cert(self) -> None:  # pragma: no cover
        """Set client certificate and key."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show input for cert path
        cert_input = Input(
            placeholder="Enter client certificate path", id="ssl_client_cert_path"
        )
        self.mount(cert_input)
        cert_input.focus()
        # Note: We'll handle key path in a second input after cert is submitted

    async def action_set_protocol(self) -> None:  # pragma: no cover
        """Set TLS protocol version."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show selection dialog for protocol version
        input_widget = Input(
            placeholder="Enter protocol version (TLSv1.2, TLSv1.3, PROTOCOL_TLS)",
            id="ssl_protocol_version",
        )
        self.mount(input_widget)
        input_widget.focus()

    async def action_verify_on(self) -> None:  # pragma: no cover
        """Enable certificate verification."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl verify-on"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "Certificate verification enabled",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to enable verification: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_verify_off(self) -> None:  # pragma: no cover
        """Disable certificate verification."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        success, msg, _ = await self._command_executor.execute_click_command(
            "ssl verify-off"
        )
        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "Certificate verification disabled",
                        title="Warning",
                        border_style="yellow",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to disable verification: {msg}",
                        title="Error",
                        border_style="red",
                    )
                )
        await self._refresh_data()

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh SSL configuration status."""
        await self._refresh_data()

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submissions for SSL commands."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        input_id = message.input.id
        value = message.value.strip()
        message.input.display = False

        if input_id == "ssl_ca_certs_path":
            if value:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ssl set-ca-certs {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"CA certificates path set: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to set CA certificates: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )
                await self._refresh_data()

        elif input_id == "ssl_client_cert_path":
            if value:
                # Store cert path and prompt for key path
                self._ssl_client_cert_path = value  # type: ignore[attr-defined]
                key_input = Input(
                    placeholder="Enter client key path", id="ssl_client_key_path"
                )
                self.mount(key_input)
                key_input.focus()

        elif input_id == "ssl_client_key_path":
            if value and hasattr(self, "_ssl_client_cert_path"):
                cert_path = self._ssl_client_cert_path  # type: ignore[attr-defined]
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ssl set-client-cert {cert_path} {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"Client certificate set: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to set client certificate: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )
                delattr(self, "_ssl_client_cert_path")
                await self._refresh_data()

        elif input_id == "ssl_protocol_version":
            if value:
                if value.upper() in ["TLSV1.2", "TLSV1.3", "PROTOCOL_TLS"]:
                    (
                        success,
                        msg,
                        _,
                    ) = await self._command_executor.execute_click_command(
                        f"ssl set-protocol {value}"
                    )
                    if self.statusbar:
                        if success:
                            self.statusbar.update(
                                Panel(
                                    f"Protocol version set: {msg}",
                                    title="Success",
                                    border_style="green",
                                )
                            )
                        else:
                            self.statusbar.update(
                                Panel(
                                    f"Failed to set protocol version: {msg}",
                                    title="Error",
                                    border_style="red",
                                )
                            )
                    await self._refresh_data()
                elif self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "Invalid protocol version. Use: TLSv1.2, TLSv1.3, or PROTOCOL_TLS",
                            title="Error",
                            border_style="red",
                        )
                    )

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "enable_trackers":
            await self.action_enable_trackers()
        elif event.button.id == "disable_trackers":
            await self.action_disable_trackers()
        elif event.button.id == "enable_peers":
            await self.action_enable_peers()
        elif event.button.id == "disable_peers":
            await self.action_disable_peers()
        elif event.button.id == "set_ca_certs":
            await self.action_set_ca_certs()
        elif event.button.id == "set_client_cert":
            await self.action_set_client_cert()
        elif event.button.id == "set_protocol":
            await self.action_set_protocol()
        elif event.button.id == "verify_on":
            await self.action_verify_on()
        elif event.button.id == "verify_off":
            await self.action_verify_off()
        elif event.button.id == "refresh":
            await self.action_refresh()

