"""NAT management monitoring screen."""

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

from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import MonitoringScreen


class NATManagementScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to manage NAT traversal (NAT-PMP and UPnP)."""

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
    #mappings_panel {
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
        ("d", "discover", "Discover"),
        ("e", "external_ip", "External IP"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the NAT management screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="performance_metrics")
            yield Static(id="mappings_panel")
            with Horizontal(id="actions"):
                yield Button("Discover", id="discover", variant="primary")
                yield Button("Map Port", id="map_port", variant="default")
                yield Button("Unmap Port", id="unmap_port", variant="default")
                yield Button("External IP", id="external_ip", variant="default")
                yield Button("Refresh", id="refresh", variant="default")
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
        """Refresh NAT status and port mappings."""
        try:
            status_panel = self.query_one("#status_panel", Static)
            performance_metrics = self.query_one("#performance_metrics", Static)
            mappings_panel = self.query_one("#mappings_panel", Static)

            # Try to get status directly from session
            try:
                if not self.session.nat_manager:
                    status_panel.update(
                        Panel(
                            "NAT manager not initialized.\n"
                            "NAT traversal may be disabled in configuration.",
                            title="NAT Status",
                            border_style="yellow",
                        )
                    )
                    mappings_panel.update(
                        Panel(
                            "No port mappings available.",
                            title="Port Mappings",
                            border_style="dim",
                        )
                    )
                    return

                status = await self.session.nat_manager.get_status()

                # Build status panel
                status_lines = [
                    "[bold]NAT Traversal Status[/bold]\n",
                ]

                if status.get("active_protocol"):
                    status_lines.append(
                        f"[green]Active Protocol:[/green] {status['active_protocol'].upper()}"
                    )
                else:
                    status_lines.append(
                        "[yellow]Active Protocol:[/yellow] None (not discovered)"
                    )

                if status.get("external_ip"):
                    status_lines.append(
                        f"[green]External IP:[/green] {status['external_ip']}"
                    )
                else:
                    status_lines.append("[yellow]External IP:[/yellow] Not available")

                # Configuration info
                config = self.session.config
                if config and hasattr(config, "nat"):
                    nat_config = config.nat
                    status_lines.append("\n[bold]Configuration:[/bold]")
                    status_lines.append(
                        f"  Auto-map ports: {'[green]Yes[/green]' if nat_config.auto_map_ports else '[red]No[/red]'}"
                    )
                    status_lines.append(
                        f"  NAT-PMP enabled: {'[green]Yes[/green]' if nat_config.enable_nat_pmp else '[red]No[/red]'}"
                    )
                    status_lines.append(
                        f"  UPnP enabled: {'[green]Yes[/green]' if nat_config.enable_upnp else '[red]No[/red]'}"
                    )

                status_panel.update(Panel("\n".join(status_lines), title="NAT Status"))

                # Build mappings table
                mappings = status.get("mappings", [])
                if mappings:
                    table = Table(title="Active Port Mappings", expand=True)
                    table.add_column("Protocol", style="cyan", ratio=1)
                    table.add_column("Internal Port", style="magenta", ratio=1)
                    table.add_column("External Port", style="yellow", ratio=1)
                    table.add_column("Source", style="green", ratio=1)
                    table.add_column("Expires At", style="blue", ratio=2)

                    for mapping in mappings:
                        expires_str = (
                            mapping.get("expires_at", "Permanent")
                            if mapping.get("expires_at")
                            else "Permanent"
                        )
                        table.add_row(
                            mapping.get("protocol", "N/A").upper(),
                            str(mapping.get("internal_port", "N/A")),
                            str(mapping.get("external_port", "N/A")),
                            mapping.get("source", "N/A").upper(),
                            str(expires_str),
                        )

                    mappings_panel.update(Panel(table))
                else:
                    mappings_panel.update(
                        Panel(
                            "No active port mappings.\n\n"
                            "Use 'Map Port' to create a port mapping, or enable auto-map in configuration.",
                            title="Port Mappings",
                            border_style="dim",
                        )
                    )
            except Exception as e:
                status_panel.update(
                    Panel(
                        f"Error loading NAT status: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                mappings_panel.update(
                    Panel(
                        "Port mappings unavailable.",
                        title="Port Mappings",
                        border_style="red",
                    )
                )

            # Performance metrics placeholder
            performance_metrics.update("")

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error refreshing NAT status: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh NAT status."""
        await self._refresh_data()

    async def action_discover(self) -> None:  # pragma: no cover
        """Discover NAT devices."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        if self.statusbar:
            self.statusbar.update(
                Panel(
                    "Discovering NAT devices...",
                    title="NAT Discovery",
                    border_style="yellow",
                )
            )

        success, msg, _ = await self._command_executor.execute_click_command(
            "nat discover"
        )

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        f"Discovery complete: {msg[:200] if len(msg) > 200 else msg}",
                        title="NAT Discovery",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Discovery failed: {msg[:200] if len(msg) > 200 else msg}",
                        title="NAT Discovery",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def action_external_ip(self) -> None:  # pragma: no cover
        """Get external IP address."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        if self.statusbar:
            self.statusbar.update(
                Panel(
                    "Retrieving external IP...",
                    title="External IP",
                    border_style="yellow",
                )
            )

        success, msg, _ = await self._command_executor.execute_click_command(
            "nat external-ip"
        )

        if self.statusbar:
            if success:
                self.statusbar.update(
                    Panel(
                        f"External IP: {msg[:200] if len(msg) > 200 else msg}",
                        title="External IP",
                        border_style="green",
                    )
                )
            else:
                self.statusbar.update(
                    Panel(
                        f"Failed to get external IP: {msg[:200] if len(msg) > 200 else msg}",
                        title="External IP",
                        border_style="red",
                    )
                )

        await self._refresh_data()

    async def action_map_port(self) -> None:  # pragma: no cover
        """Map a port using NAT traversal."""
        # Step 1: Get port number
        port_input = Input(
            placeholder="Enter internal port number (e.g., 6881)",
            id="map_port_input",
        )
        self.mount(port_input)
        port_input.focus()

        # Store state for multi-step form
        self._map_port_state = {"step": 1}  # type: ignore[attr-defined]

    async def action_unmap_port(self) -> None:  # pragma: no cover
        """Unmap a port."""
        # Step 1: Get port number
        port_input = Input(
            placeholder="Enter external port number to unmap (e.g., 6881)",
            id="unmap_port_input",
        )
        self.mount(port_input)
        port_input.focus()

        # Store state for multi-step form
        self._unmap_port_state = {"step": 1}  # type: ignore[attr-defined]

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submissions for port mapping/unmapping."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        input_id = message.input.id
        value = message.value.strip()
        message.input.display = False

        # Port mapping flow
        if input_id == "map_port_input":
            try:
                port = int(value)
                self._map_port_state["port"] = port  # type: ignore[attr-defined]
                self._map_port_state["step"] = 2  # type: ignore[attr-defined]

                # Step 2: Get protocol
                protocol_input = Input(
                    placeholder="Enter protocol (tcp or udp, default: tcp)",
                    id="map_protocol_input",
                )
                self.mount(protocol_input)
                protocol_input.focus()

            except ValueError:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "Invalid port number. Please enter a number.",
                            title="Error",
                            border_style="red",
                        )
                    )

        elif input_id == "map_protocol_input":
            if hasattr(self, "_map_port_state"):
                protocol = value.lower() if value else "tcp"
                if protocol not in ("tcp", "udp"):
                    protocol = "tcp"

                # Store protocol in state before proceeding
                self._map_port_state["protocol"] = protocol  # type: ignore[attr-defined]
                port = self._map_port_state["port"]  # type: ignore[attr-defined]
                self._map_port_state["step"] = 3  # type: ignore[attr-defined]

                # Step 3: Get external port (optional)
                ext_port_input = Input(
                    placeholder="Enter external port (0 for automatic, or press Enter to skip)",
                    id="map_ext_port_input",
                )
                self.mount(ext_port_input)
                ext_port_input.focus()

        elif input_id == "map_ext_port_input":
            if hasattr(self, "_map_port_state"):
                port = self._map_port_state["port"]  # type: ignore[attr-defined]
                # Get protocol from state (should be stored in previous step)
                protocol = self._map_port_state.get("protocol", "tcp")  # type: ignore[attr-defined]

                external_port = 0
                if value:
                    try:
                        external_port = int(value)
                    except ValueError:
                        external_port = 0

                # Execute map command
                cmd = f"nat map --port {port} --protocol {protocol}"
                if external_port > 0:
                    cmd += f" --external-port {external_port}"

                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"Mapping {protocol.upper()} port {port}...",
                            title="Port Mapping",
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
                                f"Port mapping successful: {msg[:200] if len(msg) > 200 else msg}",
                                title="Port Mapping",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Port mapping failed: {msg[:200] if len(msg) > 200 else msg}",
                                title="Port Mapping",
                                border_style="red",
                            )
                        )

                # Clean up state
                delattr(self, "_map_port_state")
                await self._refresh_data()

        # Port unmapping flow
        elif input_id == "unmap_port_input":
            try:
                port = int(value)
                if hasattr(self, "_unmap_port_state"):
                    self._unmap_port_state["port"] = port  # type: ignore[attr-defined]
                    self._unmap_port_state["step"] = 2  # type: ignore[attr-defined]

                # Step 2: Get protocol
                protocol_input = Input(
                    placeholder="Enter protocol (tcp or udp, default: tcp)",
                    id="unmap_protocol_input",
                )
                self.mount(protocol_input)
                protocol_input.focus()

            except ValueError:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "Invalid port number. Please enter a number.",
                            title="Error",
                            border_style="red",
                        )
                    )

        elif input_id == "unmap_protocol_input":
            if hasattr(self, "_unmap_port_state"):
                port = self._unmap_port_state["port"]  # type: ignore[attr-defined]
                protocol = value.lower() if value else "tcp"
                if protocol not in ("tcp", "udp"):
                    protocol = "tcp"

                # Execute unmap command
                cmd = f"nat unmap --port {port} --protocol {protocol}"

                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"Unmapping {protocol.upper()} port {port}...",
                            title="Port Unmapping",
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
                                f"Port unmapping successful: {msg[:200] if len(msg) > 200 else msg}",
                                title="Port Unmapping",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Port unmapping failed: {msg[:200] if len(msg) > 200 else msg}",
                                title="Port Unmapping",
                                border_style="red",
                            )
                        )

                # Clean up state
                delattr(self, "_unmap_port_state")
                await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "discover":
            await self.action_discover()
        elif event.button.id == "map_port":
            await self.action_map_port()
        elif event.button.id == "unmap_port":
            await self.action_unmap_port()
        elif event.button.id == "external_ip":
            await self.action_external_ip()
        elif event.button.id == "refresh":
            await self.action_refresh()

