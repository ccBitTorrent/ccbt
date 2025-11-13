"""UTP configuration screen."""

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


class UTPConfigScreen(ConfigScreen):  # type: ignore[misc]
    """Screen to manage uTP (uTorrent Transport Protocol) configuration."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #status_panel {
        height: auto;
        min-height: 10;
    }
    #config_panel {
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
        ("e", "enable", "Enable"),
        ("d", "disable", "Disable"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the uTP configuration screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="config_panel")
            with Horizontal(id="actions"):
                yield Button("Enable", id="enable", variant="primary")
                yield Button("Disable", id="disable", variant="warning")
                yield Button("Config Get", id="config_get", variant="default")
                yield Button("Config Set", id="config_set", variant="default")
                yield Button("Config Reset", id="config_reset", variant="default")
                yield Button("Refresh", id="refresh", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the uTP configuration screen and initialize command executor."""
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
        """Refresh uTP configuration status."""
        try:
            status_panel = self.query_one("#status_panel", Static)
            config_panel = self.query_one("#config_panel", Static)

            # Get configuration
            try:
                config = get_config()
            except Exception:
                config_manager = ConfigManager()
                config = config_manager.config

            utp_config = config.network.utp
            enable_utp = config.network.enable_utp

            # Build status panel
            status_lines = [
                "[bold]uTP (uTorrent Transport Protocol) Status[/bold]\n",
                f"Enabled: {'[green]Yes[/green]' if enable_utp else '[red]No[/red]'}",
                "\n[dim]uTP provides reliable, ordered delivery over UDP with delay-based congestion control (BEP 29).[/dim]",
            ]

            status_panel.update(Panel("\n".join(status_lines), title="uTP Status"))

            # Build configuration table
            table = Table(title="uTP Configuration", expand=True)
            table.add_column("Setting", style="cyan", ratio=2)
            table.add_column("Value", style="green", ratio=2)
            table.add_column("Description", style="dim", ratio=4)

            table.add_row(
                "Prefer over TCP",
                str(utp_config.prefer_over_tcp),
                "Prefer uTP when both TCP and uTP are available",
            )
            table.add_row(
                "Connection Timeout",
                f"{utp_config.connection_timeout}s",
                "Connection timeout in seconds",
            )
            table.add_row(
                "Max Window Size",
                f"{utp_config.max_window_size:,} bytes",
                "Maximum receive window size",
            )
            table.add_row(
                "MTU",
                f"{utp_config.mtu} bytes",
                "Maximum UDP packet size",
            )
            table.add_row(
                "Initial Rate",
                f"{utp_config.initial_rate:,} B/s",
                "Initial send rate",
            )
            table.add_row(
                "Min Rate",
                f"{utp_config.min_rate:,} B/s",
                "Minimum send rate",
            )
            table.add_row(
                "Max Rate",
                f"{utp_config.max_rate:,} B/s",
                "Maximum send rate",
            )
            table.add_row(
                "ACK Interval",
                f"{utp_config.ack_interval}s",
                "ACK packet send interval",
            )
            table.add_row(
                "Retransmit Timeout Factor",
                str(utp_config.retransmit_timeout_factor),
                "RTT multiplier for retransmit timeout",
            )
            table.add_row(
                "Max Retransmits",
                str(utp_config.max_retransmits),
                "Maximum retransmission attempts",
            )

            config_panel.update(Panel(table))

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading uTP configuration: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh uTP configuration."""
        await self._refresh_data()

    async def action_enable(self) -> None:  # pragma: no cover
        """Enable uTP transport."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        success, msg, _ = await self._command_executor.execute_click_command(
            "utp enable"
        )

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "uTP transport enabled",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to enable uTP: {msg[:200] if len(msg) > 200 else msg}",
                        title="Error",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def action_disable(self) -> None:  # pragma: no cover
        """Disable uTP transport."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        success, msg, _ = await self._command_executor.execute_click_command(
            "utp disable"
        )

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "uTP transport disabled",
                        title="Success",
                        border_style="yellow",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to disable uTP: {msg[:200] if len(msg) > 200 else msg}",
                        title="Error",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def action_config_get(self) -> None:  # pragma: no cover
        """Get uTP configuration values."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        # Show all configuration
        success, msg, _ = await self._command_executor.execute_click_command("utp show")

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        f"uTP configuration retrieved: {msg[:300] if len(msg) > 300 else msg}",
                        title="uTP Config",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to get uTP config: {msg[:200] if len(msg) > 200 else msg}",
                        title="Error",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def action_config_set(self) -> None:  # pragma: no cover
        """Set uTP configuration value."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        # Step 1: Get configuration key
        key_input = Input(
            placeholder="Enter config key (e.g., mtu, max_window_size, prefer_over_tcp)",
            id="utp_config_key_input",
        )
        self.mount(key_input)
        key_input.focus()

        # Store state for multi-step form
        self._utp_config_state = {"step": 1}  # type: ignore[attr-defined]

    async def action_config_reset(self) -> None:  # pragma: no cover
        """Reset uTP configuration to defaults."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        if self.statusbar:
            self.statusbar.update(
                Panel(
                    "Resetting uTP configuration to defaults...",
                    title="uTP Config Reset",
                    border_style="yellow",
                )
            )

        success, msg, _ = await self._command_executor.execute_click_command(
            "utp config reset"
        )

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        "uTP configuration reset to defaults",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to reset uTP config: {msg[:200] if len(msg) > 200 else msg}",
                        title="Error",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submissions for uTP configuration."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        input_id = message.input.id
        value = message.value.strip()
        message.input.display = False

        # uTP config set flow
        if input_id == "utp_config_key_input":
            if value:
                self._utp_config_state["key"] = value  # type: ignore[attr-defined]
                self._utp_config_state["step"] = 2  # type: ignore[attr-defined]

                # Step 2: Get configuration value
                value_input = Input(
                    placeholder=f"Enter value for {value}",
                    id="utp_config_value_input",
                )
                self.mount(value_input)
                value_input.focus()

        elif input_id == "utp_config_value_input":
            if hasattr(self, "_utp_config_state"):
                key = self._utp_config_state["key"]  # type: ignore[attr-defined]
                config_value = value

                # Execute config set command
                cmd = f"utp config set {key} {config_value}"

                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"Setting uTP config {key} = {config_value}...",
                            title="uTP Config Set",
                            border_style="yellow",
                        )
                    )

                success, msg, _ = await self._command_executor.execute_click_command(
                    cmd
                )

                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"uTP config set: {key} = {config_value}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to set uTP config: {msg[:200] if len(msg) > 200 else msg}",
                                title="Error",
                                border_style="red",
                            )
                        )

                # Clean up state
                delattr(self, "_utp_config_state")
                await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "enable":
            await self.action_enable()
        elif event.button.id == "disable":
            await self.action_disable()
        elif event.button.id == "config_get":
            await self.action_config_get()
        elif event.button.id == "config_set":
            await self.action_config_set()
        elif event.button.id == "config_reset":
            await self.action_config_reset()
        elif event.button.id == "refresh":
            await self.action_refresh()

