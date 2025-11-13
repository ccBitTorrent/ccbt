"""IPFS management monitoring screen."""

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


class IPFSManagementScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to manage IPFS protocol (content-addressed storage)."""

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
    #content_table {
        height: 1fr;
        min-height: 10;
    }
    #peers_table {
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
        ("a", "add", "Add File"),
        ("g", "get", "Get Content"),
        ("p", "pin", "Pin"),
        ("u", "unpin", "Unpin"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the IPFS management screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield Static(id="performance_metrics")
            with Horizontal():
                with Vertical():
                    yield Static(id="content_table")
                with Vertical():
                    yield Static(id="peers_table")
            with Horizontal(id="actions"):
                yield Button("Add File", id="add", variant="primary")
                yield Button("Get Content", id="get", variant="default")
                yield Button("Pin", id="pin", variant="default")
                yield Button("Unpin", id="unpin", variant="default")
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
        """Refresh IPFS protocol status, content, and peers."""
        try:
            status_panel = self.query_one("#status_panel", Static)
            performance_metrics = self.query_one("#performance_metrics", Static)
            content_table = self.query_one("#content_table", Static)
            peers_table = self.query_one("#peers_table", Static)

            # Get IPFS protocol instance
            protocol = await self._get_ipfs_protocol()

            # Build status panel
            status_lines = [
                "[bold]IPFS Protocol Status[/bold]\n",
            ]

            if protocol:
                status_lines.append("Connection: [green]Connected[/green]")
                status_lines.append(f"Protocol state: {protocol.state}")
                status_lines.append(f"IPFS API URL: {protocol.ipfs_api_url}")
                status_lines.append(f"Gateway URLs: {len(protocol.ipfs_gateway_urls)}")
                status_lines.append(
                    f"Connected: {'[green]Yes[/green]' if protocol._ipfs_connected else '[red]No[/red]'}"
                )

                # Get peer count
                try:
                    peers_dict = protocol.get_ipfs_peers()
                    peer_count = len(peers_dict)
                    status_lines.append(f"Connected peers: {peer_count}")
                except Exception:
                    status_lines.append("Connected peers: Unknown")

                # Get content count
                try:
                    content_dict = protocol.get_ipfs_content()
                    content_count = len(content_dict)
                    pinned_count = len(protocol._pinned_cids)
                    status_lines.append(f"Content items: {content_count}")
                    status_lines.append(f"Pinned items: {pinned_count}")
                except Exception:
                    status_lines.append("Content items: Unknown")
            else:
                status_lines.append("Connection: [red]Not Available[/red]")
                status_lines.append(
                    "\n[yellow]IPFS protocol not active (session may not be running)[/yellow]"
                )

            status_panel.update(
                Panel("\n".join(status_lines), title="IPFS Protocol Status")
            )

            # Build content table if protocol is available
            if protocol:
                try:
                    content_dict = protocol.get_ipfs_content()

                    if content_dict:
                        table = Table(title="IPFS Content", expand=True)
                        table.add_column("CID", style="cyan", ratio=3)
                        table.add_column("Size", style="green", ratio=2)
                        table.add_column("Pinned", style="yellow", ratio=1)
                        table.add_column("Last Accessed", style="blue", ratio=2)

                        # Sort by last accessed (most recent first)
                        sorted_content = sorted(
                            content_dict.items(),
                            key=lambda x: x[1].last_accessed
                            if hasattr(x[1], "last_accessed")
                            else 0,
                            reverse=True,
                        )

                        for cid, content in sorted_content[:20]:  # Show top 20
                            is_pinned = cid in protocol._pinned_cids
                            size_str = (
                                f"{content.size:,} bytes"
                                if hasattr(content, "size")
                                else "Unknown"
                            )
                            last_access = (
                                f"{content.last_accessed:.1f}s ago"
                                if hasattr(content, "last_accessed")
                                and content.last_accessed > 0
                                else "Never"
                            )
                            table.add_row(
                                cid[:40] + "..." if len(cid) > 40 else cid,
                                size_str,
                                "[green]Yes[/green]"
                                if is_pinned
                                else "[yellow]No[/yellow]",
                                last_access,
                            )

                        content_table.update(Panel(table))
                    else:
                        content_table.update(
                            Panel(
                                "No IPFS content available.",
                                title="IPFS Content",
                                border_style="yellow",
                            )
                        )
                except Exception as e:
                    content_table.update(
                        Panel(
                            f"Error loading content: {e}",
                            title="Error",
                            border_style="red",
                        )
                    )

                # Build peers table
                try:
                    peers_dict = protocol.get_ipfs_peers()

                    if peers_dict:
                        table = Table(title="IPFS Peers", expand=True)
                        table.add_column("Peer ID", style="cyan", ratio=2)
                        table.add_column("Multiaddr", style="green", ratio=3)
                        table.add_column("Protocols", style="yellow", ratio=2)

                        for peer_id, peer in list(peers_dict.items())[
                            :20
                        ]:  # Show top 20
                            protocols_str = (
                                ", ".join(peer.protocols) if peer.protocols else "None"
                            )
                            peer_id_short = (
                                peer_id[:20] + "..." if len(peer_id) > 20 else peer_id
                            )
                            multiaddr_short = (
                                peer.multiaddr[:40] + "..."
                                if len(peer.multiaddr) > 40
                                else peer.multiaddr
                            )
                            table.add_row(
                                peer_id_short,
                                multiaddr_short,
                                protocols_str,
                            )

                        peers_table.update(Panel(table))
                    else:
                        peers_table.update(
                            Panel(
                                "No IPFS peers connected.",
                                title="IPFS Peers",
                                border_style="yellow",
                            )
                        )
                except Exception as e:
                    peers_table.update(
                        Panel(
                            f"Error loading peers: {e}",
                            title="Error",
                            border_style="red",
                        )
                    )
            else:
                content_table.update(
                    Panel(
                        "IPFS protocol not available. Enable it to view content.",
                        title="IPFS Content",
                        border_style="yellow",
                    )
                )
                peers_table.update(
                    Panel(
                        "IPFS protocol not available. Enable it to view peers.",
                        title="IPFS Peers",
                        border_style="yellow",
                    )
                )
                performance_metrics.update("")

            # Refresh performance metrics
            await self._refresh_ipfs_performance_metrics(performance_metrics, protocol)

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading IPFS status: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def _refresh_ipfs_performance_metrics(
        self, widget: Static, protocol: Any | None
    ) -> None:  # pragma: no cover
        """Refresh IPFS performance metrics."""
        try:
            table = Table(
                title="IPFS Performance Metrics",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            if protocol:
                try:
                    peers_dict = protocol.get_ipfs_peers()
                    peer_count = len(peers_dict) if peers_dict else 0
                    table.add_row("Connected Peers", str(peer_count))
                except Exception:
                    table.add_row("Connected Peers", "Unknown")

                try:
                    content_dict = protocol.get_ipfs_content()
                    content_count = len(content_dict) if content_dict else 0
                    pinned_count = (
                        len(protocol._pinned_cids)
                        if hasattr(protocol, "_pinned_cids")
                        else 0
                    )
                    table.add_row("Content Items", str(content_count))
                    table.add_row("Pinned Items", str(pinned_count))
                except Exception:
                    table.add_row("Content Items", "Unknown")

                # Connection status
                is_connected = getattr(protocol, "_ipfs_connected", False)
                table.add_row(
                    "Connection Status",
                    "[green]Connected[/green]"
                    if is_connected
                    else "[red]Disconnected[/red]",
                )
            else:
                table.add_row("Status", "[yellow]Protocol not available[/yellow]")

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _get_ipfs_protocol(self) -> Any | None:  # pragma: no cover
        """Get IPFS protocol instance from session."""
        try:
            from ccbt.protocols.base import ProtocolType
            from ccbt.protocols.ipfs import IPFSProtocol

            # Try to get from session's protocol manager
            if hasattr(self.session, "protocol_manager"):
                protocol_manager = self.session.protocol_manager
                if protocol_manager:
                    ipfs_protocol = protocol_manager.get_protocol(ProtocolType.IPFS)
                    if isinstance(ipfs_protocol, IPFSProtocol):
                        return ipfs_protocol

            # Try to get from session's protocols list
            protocols = getattr(self.session, "protocols", [])
            if isinstance(protocols, list):
                for protocol in protocols:
                    if isinstance(protocol, IPFSProtocol):
                        return protocol
            elif isinstance(protocols, dict):
                for protocol in protocols.values():
                    if isinstance(protocol, IPFSProtocol):
                        return protocol

            return None
        except Exception:
            return None

    async def action_add(self) -> None:  # pragma: no cover
        """Add file to IPFS."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show input dialog for file path
        input_widget = Input(placeholder="Enter file path", id="ipfs_add_path")
        self.mount(input_widget)
        input_widget.focus()

    async def action_get(self) -> None:  # pragma: no cover
        """Get content from IPFS by CID."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show input dialog for CID
        input_widget = Input(placeholder="Enter CID", id="ipfs_get_cid")
        self.mount(input_widget)
        input_widget.focus()

    async def action_pin(self) -> None:  # pragma: no cover
        """Pin content in IPFS."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show input dialog for CID
        input_widget = Input(placeholder="Enter CID to pin", id="ipfs_pin_cid")
        self.mount(input_widget)
        input_widget.focus()

    async def action_unpin(self) -> None:  # pragma: no cover
        """Unpin content from IPFS."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        # Show input dialog for CID
        input_widget = Input(placeholder="Enter CID to unpin", id="ipfs_unpin_cid")
        self.mount(input_widget)
        input_widget.focus()

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh IPFS status, content, and peers."""
        await self._refresh_data()

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submissions for IPFS commands."""
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        input_id = message.input.id
        value = message.value.strip()
        message.input.display = False

        if input_id == "ipfs_add_path":
            if value:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ipfs-add {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"File added to IPFS: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to add file: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )
                await self._refresh_data()

        elif input_id == "ipfs_get_cid":
            if value:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ipfs-get {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"Content retrieved: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to get content: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )

        elif input_id == "ipfs_pin_cid":
            if value:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ipfs-pin {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"Content pinned: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to pin content: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )
                await self._refresh_data()

        elif input_id == "ipfs_unpin_cid":
            if value:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"ipfs-unpin {value}"
                )
                if self.statusbar:
                    if success:
                        self.statusbar.update(
                            Panel(
                                f"Content unpinned: {msg}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        self.statusbar.update(
                            Panel(
                                f"Failed to unpin content: {msg}",
                                title="Error",
                                border_style="red",
                            )
                        )
                await self._refresh_data()

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "add":
            await self.action_add()
        elif event.button.id == "get":
            await self.action_get()
        elif event.button.id == "pin":
            await self.action_pin()
        elif event.button.id == "unpin":
            await self.action_unpin()
        elif event.button.id == "refresh":
            await self.action_refresh()

