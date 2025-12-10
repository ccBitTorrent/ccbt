"""XET folder synchronization management screen.

Provides interface for managing XET folder sync sessions (similar to torrent management).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, DataTable, Footer, Header, Input, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import (
            Button,
            DataTable,
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
        DataTable = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Input = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import ConfirmationDialog, MonitoringScreen


class XetFolderSyncScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to manage XET folder synchronization sessions."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #folders_table {
        height: 1fr;
        min-height: 10;
    }
    #status_panel {
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
        ("a", "add_folder", "Add Folder"),
        ("d", "remove_folder", "Remove Folder"),
        ("s", "sync_status", "Status"),
        ("w", "manage_allowlist", "Allowlist"),
        ("l", "list_aliases", "List Aliases"),
        ("n", "add_alias", "Add Alias"),
        ("x", "remove_alias", "Remove Alias"),
    ]

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the XET folder sync screen."""
        yield Header()
        with Vertical():
            yield Static(id="status_panel")
            yield DataTable(id="folders_table")
            with Horizontal(id="actions"):
                yield Button("Add Folder", id="add_folder", variant="primary")
                yield Button("Remove Folder", id="remove_folder", variant="warning")
                yield Button("Refresh", id="refresh", variant="default")
                yield Button("Status", id="status", variant="default")
                yield Button("Allowlist", id="allowlist", variant="default")
                yield Button("Aliases", id="aliases", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and initialize command executor."""
        # Initialize command executor
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)

        # Setup folders table
        folders_table = self.query_one("#folders_table", DataTable)
        folders_table.add_columns(
            "Folder Key",
            "Folder Path",
            "Sync Mode",
            "Status",
            "Peers",
            "Progress",
            "Git Ref",
        )

        # Try to get statusbar reference if available
        try:
            self.statusbar = self.query_one("#statusbar", Static)
        except Exception:
            try:
                app = self.app
                if hasattr(app, "statusbar"):
                    self.statusbar = app.statusbar
            except Exception:
                self.statusbar = None

        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh XET folder sync sessions."""
        try:
            # Get XET folders from session
            result = await self._command_executor.execute_command(
                "xet.list_xet_folders"
            )

            status_panel = self.query_one("#status_panel", Static)
            folders_table = self.query_one("#folders_table", DataTable)

            # Handle both CommandResult and tuple return formats
            if hasattr(result, "success"):
                # CommandResult format
                if not result.success:
                    status_panel.update(
                        Panel(
                            f"Error loading XET folders: {result.error}",
                            title="Error",
                            border_style="red",
                        )
                    )
                    folders_table.clear()
                    return
                folder_list = result.data.get("folders", [])
            else:
                # Tuple format (legacy)
                success, message, data = result
                if not success:
                    status_panel.update(
                        Panel(
                            f"Error loading XET folders: {message}",
                            title="Error",
                            border_style="red",
                        )
                    )
                    folders_table.clear()
                    return
                folder_list = data.get("folders", []) if isinstance(data, dict) else []

            if not folder_list:
                folder_list = []

            # Update status panel
            status_lines = [
                "[bold]XET Folder Synchronization[/bold]\n",
                f"Active folders: {len(folder_list)}",
            ]

            # Get XET config
            config_result = await self._command_executor.execute_command(
                "xet.get_config"
            )
            # Handle both CommandResult and tuple return formats
            if hasattr(config_result, "success"):
                config_success = config_result.success
                config_data = config_result.data if config_result.success else {}
            else:
                config_success, _, config_data = config_result
                config_data = config_data if isinstance(config_data, dict) else {}
            
            if config_success:
                status_lines.append(
                    f"XET enabled: {'[green]Yes[/green]' if config_data.get('enable_xet') else '[red]No[/red]'}"
                )
                status_lines.append(
                    f"Check interval: {config_data.get('check_interval', 'N/A')}s"
                )
                status_lines.append(
                    f"Default sync mode: {config_data.get('default_sync_mode', 'N/A')}"
                )

            status_panel.update(Panel("\n".join(status_lines), title="XET Folder Sync Status"))

            # Update folders table
            folders_table.clear()
            for folder in folder_list:
                folder_key = folder.get("folder_key", "N/A")
                folder_path = folder.get("folder_path", "N/A")
                sync_mode = folder.get("sync_mode", "N/A")
                is_syncing = folder.get("is_syncing", False)
                connected_peers = folder.get("connected_peers", 0)
                sync_progress = folder.get("sync_progress", 0.0)
                git_ref = folder.get("current_git_ref", "N/A")

                status = "[green]Syncing[/green]" if is_syncing else "[yellow]Idle[/yellow]"
                progress_str = f"{sync_progress:.1f}%" if sync_progress is not None else "N/A"

                folders_table.add_row(
                    folder_key[:16] + "..." if len(folder_key) > 16 else folder_key,
                    str(Path(folder_path).name) if folder_path != "N/A" else "N/A",
                    sync_mode,
                    status,
                    str(connected_peers),
                    progress_str,
                    git_ref[:8] + "..." if git_ref and git_ref != "N/A" and len(git_ref) > 8 else (git_ref or "N/A"),
                )

        except Exception as e:
            status_panel = self.query_one("#status_panel", Static)
            status_panel.update(
                Panel(
                    f"Error loading XET folders: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def action_add_folder(self) -> None:  # pragma: no cover
        """Add XET folder for synchronization."""
        # Show input dialog for folder path
        from ccbt.interface.screens.dialogs import InputDialog

        dialog = InputDialog(
            "Add XET Folder",
            "Enter folder path or tonic?: link:",
            placeholder="path/to/folder or tonic?:...",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if result:
            folder_input = result.strip()
            if not folder_input:
                return

            # Determine if it's a tonic link or folder path
            if folder_input.startswith("tonic?:"):
                result = await self._command_executor.execute_command(
                    "xet.add_xet_folder",
                    folder_path=".",
                    tonic_link=folder_input,
                )
            else:
                # Check if it's a .tonic file
                if folder_input.endswith(".tonic"):
                    result = await self._command_executor.execute_command(
                        "xet.add_xet_folder",
                        folder_path=".",
                        tonic_file=folder_input,
                    )
                else:
                    # Regular folder path
                    result = await self._command_executor.execute_command(
                        "xet.add_xet_folder",
                        folder_path=folder_input,
                    )

            # Handle both CommandResult and tuple return formats
            if hasattr(result, "success"):
                success = result.success
                error = result.error
                data = result.data if result.success else {}
            else:
                success, message, data = result
                error = message if not success else None
                data = data if isinstance(data, dict) else {}

            if success:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"XET folder added successfully: {data.get('folder_key', folder_input)}",
                            title="Success",
                            border_style="green",
                        )
                    )
            else:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"Failed to add XET folder: {error}",
                            title="Error",
                            border_style="red",
                        )
                    )

            await self._refresh_data()

    async def action_remove_folder(self) -> None:  # pragma: no cover
        """Remove XET folder from synchronization."""
        folders_table = self.query_one("#folders_table", DataTable)
        cursor_row = folders_table.cursor_row

        if cursor_row is None or cursor_row < 0:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Please select a folder to remove",
                        title="Info",
                        border_style="yellow",
                    )
                )
            return

        # Get folder key from selected row
        folder_key = folders_table.get_row_at(cursor_row)[0]

        # Show confirmation
        confirmation = ConfirmationDialog(
            f"Remove XET folder '{folder_key}' from synchronization?",
        )
        result = await self.app.push_screen(confirmation)  # type: ignore[attr-defined]

        if result:
            remove_result = await self._command_executor.execute_command(
                "xet.remove_xet_folder",
                folder_key=folder_key,
            )

            # Handle both CommandResult and tuple return formats
            if hasattr(remove_result, "success"):
                success = remove_result.success
                error = remove_result.error
            else:
                success, message, _ = remove_result
                error = message if not success else None

            if success:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"XET folder removed successfully: {folder_key}",
                            title="Success",
                            border_style="green",
                        )
                    )
            else:
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            f"Failed to remove XET folder: {error}",
                            title="Error",
                            border_style="red",
                        )
                    )

            await self._refresh_data()

    async def action_refresh(self) -> None:  # pragma: no cover
        """Refresh XET folder list."""
        await self._refresh_data()

    async def action_sync_status(self) -> None:  # pragma: no cover
        """Show detailed sync status for selected folder."""
        folders_table = self.query_one("#folders_table", DataTable)
        cursor_row = folders_table.cursor_row

        if cursor_row is None or cursor_row < 0:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Please select a folder to view status",
                        title="Info",
                        border_style="yellow",
                    )
                )
            return

        # Get folder key from selected row
        folder_key = folders_table.get_row_at(cursor_row)[0]

        # Get detailed status
        status_result = await self._command_executor.execute_command(
            "xet.get_xet_folder_status",
            folder_key=folder_key,
        )

        # Handle both CommandResult and tuple return formats
        if hasattr(status_result, "success"):
            success = status_result.success
            error = status_result.error
            result_data = status_result.data if status_result.success else {}
        else:
            success, message, result_data = status_result
            error = message if not success else None
            result_data = result_data if isinstance(result_data, dict) else {}

        if success:
            status_data = result_data.get("status", {})
            status_panel = self.query_one("#status_panel", Static)

            status_lines = [
                f"[bold]XET Folder Status: {folder_key}[/bold]\n",
                f"Folder path: {status_data.get('folder_path', 'N/A')}",
                f"Sync mode: {status_data.get('sync_mode', 'N/A')}",
                f"Status: {'[green]Syncing[/green]' if status_data.get('is_syncing') else '[yellow]Idle[/yellow]'}",
                f"Connected peers: {status_data.get('connected_peers', 0)}",
                f"Sync progress: {status_data.get('sync_progress', 0.0):.1f}%",
                f"Current git ref: {status_data.get('current_git_ref', 'N/A')}",
                f"Last sync time: {status_data.get('last_sync_time', 'N/A')}",
            ]

            status_panel.update(Panel("\n".join(status_lines), title="Folder Status"))
        else:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Failed to get folder status: {error}",
                        title="Error",
                        border_style="red",
                    )
                )

    async def action_manage_allowlist(self) -> None:  # pragma: no cover
        """Manage allowlist for selected folder."""
        folders_table = self.query_one("#folders_table", DataTable)
        cursor_row = folders_table.cursor_row

        if cursor_row is None or cursor_row < 0:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Please select a folder to manage allowlist",
                        title="Info",
                        border_style="yellow",
                    )
                )
            return

        # Get folder key from selected row
        folder_key = folders_table.get_row_at(cursor_row)[0]

        # Show input dialog for allowlist path
        from ccbt.interface.screens.base import InputDialog

        dialog = InputDialog(
            "Allowlist Path",
            "Enter allowlist file path:",
            placeholder="path/to/allowlist.json",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if result:
            allowlist_path = result.strip()
            if not allowlist_path:
                return

            # Show allowlist management options
            await self._show_allowlist_menu(allowlist_path)

    async def action_list_aliases(self) -> None:  # pragma: no cover
        """List all aliases in allowlist."""
        # Show input dialog for allowlist path
        from ccbt.interface.screens.base import InputDialog

        dialog = InputDialog(
            "Allowlist Path",
            "Enter allowlist file path:",
            placeholder="path/to/allowlist.json",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if result:
            allowlist_path = result.strip()
            if not allowlist_path:
                return

            await self._list_aliases(allowlist_path)

    async def _show_allowlist_menu(self, allowlist_path: str) -> None:  # pragma: no cover
        """Show allowlist management menu."""
        # Get allowlist peers
        result = await self._command_executor.execute_command(
            "xet.allowlist_list",
            allowlist_path=allowlist_path,
        )

        # Handle both CommandResult and tuple return formats
        if hasattr(result, "success"):
            success = result.success
            error = result.error
            data = result.data if result.success else {}
        else:
            success, message, data = result
            error = message if not success else None
            data = data if isinstance(data, dict) else {}

        if not success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Failed to load allowlist: {error}",
                        title="Error",
                        border_style="red",
                    )
                )
            return

        peers = data.get("peers", [])
        status_panel = self.query_one("#status_panel", Static)

        # Create allowlist table
        from rich.table import Table as RichTable

        table = RichTable(show_header=True, header_style="bold")
        table.add_column("Peer ID", style="cyan")
        table.add_column("Alias", style="yellow")
        table.add_column("Public Key", style="green")
        table.add_column("Added At", style="blue")

        import time

        for peer in peers:
            peer_id = peer.get("peer_id", "N/A")
            alias = peer.get("alias") or "-"
            public_key = peer.get("public_key", "")
            added_at = peer.get("added_at", 0)

            public_key_str = (
                public_key[:16] + "..." if public_key and len(public_key) > 16 else (public_key or "None")
            )
            added_at_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(added_at))
                if added_at
                else "Unknown"
            )

            table.add_row(peer_id, alias, public_key_str, added_at_str)

        status_lines = [
            "[bold]XET Allowlist Management[/bold]\n",
            f"Allowlist path: {allowlist_path}",
            f"Total peers: {len(peers)}",
            "",
            "[yellow]Commands:[/yellow]",
            "  [l] List aliases",
            "  [n] Add/Set alias (select peer first)",
            "  [x] Remove alias (select peer first)",
        ]

        status_panel.update(Panel("\n".join(status_lines) + "\n\n" + str(table), title="Allowlist"))
        
        # Store allowlist path for later use
        self._current_allowlist_path = allowlist_path  # type: ignore[attr-defined]

    async def _list_aliases(self, allowlist_path: str) -> None:  # pragma: no cover
        """List all aliases in allowlist."""
        result = await self._command_executor.execute_command(
            "xet.allowlist_alias_list",
            allowlist_path=allowlist_path,
        )

        # Handle both CommandResult and tuple return formats
        if hasattr(result, "success"):
            success = result.success
            error = result.error
            data = result.data if result.success else {}
        else:
            success, message, data = result
            error = message if not success else None
            data = data if isinstance(data, dict) else {}

        status_panel = self.query_one("#status_panel", Static)

        if not success:
            status_panel.update(
                Panel(
                    f"Failed to list aliases: {error}",
                    title="Error",
                    border_style="red",
                )
            )
            return

        aliases = data.get("aliases", [])

        if not aliases:
            status_panel.update(
                Panel(
                    "No aliases found in allowlist",
                    title="Info",
                    border_style="yellow",
                )
            )
            return

        from rich.table import Table as RichTable

        table = RichTable(show_header=True, header_style="bold")
        table.add_column("Peer ID", style="cyan")
        table.add_column("Alias", style="yellow")

        for alias_entry in aliases:
            peer_id = alias_entry.get("peer_id", "N/A")
            alias = alias_entry.get("alias", "N/A")
            table.add_row(peer_id, alias)

        status_panel.update(
            Panel(
                f"[bold]Aliases ({len(aliases)}):[/bold]\n\n" + str(table),
                title="Allowlist Aliases",
            )
        )

    async def action_add_alias(self) -> None:  # pragma: no cover
        """Add or update alias for a peer in allowlist."""
        # Check if we have a current allowlist path
        if not hasattr(self, "_current_allowlist_path") or not self._current_allowlist_path:
            # Prompt for allowlist path
            from ccbt.interface.screens.dialogs import InputDialog

            dialog = InputDialog(
                "Allowlist Path",
                "Enter allowlist file path:",
                placeholder="path/to/allowlist.json",
            )
            result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

            if not result or not result.strip():
                return

            allowlist_path = result.strip()
        else:
            allowlist_path = self._current_allowlist_path

        # Prompt for peer ID
        from ccbt.interface.screens.dialogs import InputDialog

        dialog = InputDialog(
            "Peer ID",
            "Enter peer ID to set alias for:",
            placeholder="peer_id_here",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if not result:
            return

        peer_id = result.strip()
        if not peer_id:
            return

        # Prompt for alias
        dialog = InputDialog(
            "Set Alias",
            f"Enter alias for peer {peer_id}:",
            placeholder="e.g., Alice's Computer",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if result:
            alias = result.strip()
            if not alias:
                return

            await self._add_alias(allowlist_path, peer_id, alias)

    async def action_remove_alias(self) -> None:  # pragma: no cover
        """Remove alias for a peer in allowlist."""
        # Check if we have a current allowlist path
        if not hasattr(self, "_current_allowlist_path") or not self._current_allowlist_path:
            # Prompt for allowlist path
            from ccbt.interface.screens.dialogs import InputDialog

            dialog = InputDialog(
                "Allowlist Path",
                "Enter allowlist file path:",
                placeholder="path/to/allowlist.json",
            )
            result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

            if not result or not result.strip():
                return

            allowlist_path = result.strip()
        else:
            allowlist_path = self._current_allowlist_path

        # Prompt for peer ID
        from ccbt.interface.screens.dialogs import InputDialog

        dialog = InputDialog(
            "Peer ID",
            "Enter peer ID to remove alias for:",
            placeholder="peer_id_here",
        )
        result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]

        if not result:
            return

        peer_id = result.strip()
        if not peer_id:
            return

        await self._remove_alias(allowlist_path, peer_id)

    async def _add_alias(self, allowlist_path: str, peer_id: str, alias: str) -> None:  # pragma: no cover
        """Add or update alias for a peer."""
        alias_result = await self._command_executor.execute_command(
            "xet.allowlist_alias_add",
            allowlist_path=allowlist_path,
            peer_id=peer_id,
            alias=alias,
        )

        # Handle both CommandResult and tuple return formats
        if hasattr(alias_result, "success"):
            success = alias_result.success
            error = alias_result.error
        else:
            success, message, _ = alias_result
            error = message if not success else None

        if success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Set alias '{alias}' for peer {peer_id}",
                        title="Success",
                        border_style="green",
                    )
                )
            # Refresh allowlist display if currently showing it
            if hasattr(self, "_current_allowlist_path") and self._current_allowlist_path == allowlist_path:
                await self._show_allowlist_menu(allowlist_path)
        else:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Failed to set alias: {error}",
                        title="Error",
                        border_style="red",
                    )
                )

    async def _remove_alias(self, allowlist_path: str, peer_id: str) -> None:  # pragma: no cover
        """Remove alias for a peer."""
        alias_result = await self._command_executor.execute_command(
            "xet.allowlist_alias_remove",
            allowlist_path=allowlist_path,
            peer_id=peer_id,
        )

        # Handle both CommandResult and tuple return formats
        if hasattr(alias_result, "success"):
            success = alias_result.success
            error = alias_result.error
        else:
            success, message, _ = alias_result
            error = message if not success else None

        if success:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Removed alias for peer {peer_id}",
                        title="Success",
                        border_style="green",
                    )
                )
            # Refresh allowlist display if currently showing it
            if hasattr(self, "_current_allowlist_path") and self._current_allowlist_path == allowlist_path:
                await self._show_allowlist_menu(allowlist_path)
        else:
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Failed to remove alias: {error}",
                        title="Error",
                        border_style="red",
                    )
                )

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "add_folder":
            await self.action_add_folder()
        elif event.button.id == "remove_folder":
            await self.action_remove_folder()
        elif event.button.id == "refresh":
            await self.action_refresh()
        elif event.button.id == "status":
            await self.action_sync_status()
        elif event.button.id == "allowlist":
            await self.action_manage_allowlist()
        elif event.button.id == "aliases":
            await self.action_list_aliases()

