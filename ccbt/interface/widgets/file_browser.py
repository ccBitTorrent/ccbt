"""File browser widget for browsing filesystem and creating torrents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Button, DataTable, Input, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

from rich.panel import Panel

logger = logging.getLogger(__name__)


class FileBrowserWidget(Container):  # type: ignore[misc]
    """File browser widget for browsing filesystem and creating torrents."""

    DEFAULT_CSS = """
    FileBrowserWidget {
        height: 1fr;
        layout: vertical;
        overflow: hidden;
        min-width: 60;
        min-height: 15;
    }
    
    #browser-header {
        height: 3;
        min-height: 3;
        border: solid $primary;
    }
    
    #browser-content {
        height: 1fr;
        min-height: 12;
        layout: horizontal;
        overflow: hidden;
    }
    
    #file-tree {
        width: 3fr;
        min-width: 60;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    #file-actions {
        width: 35;
        min-width: 30;
        border-left: solid $primary;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    #path-input {
        height: 3;
        min-height: 3;
    }
    
    #action-buttons {
        height: auto;
        min-height: 5;
    }
    
    #file-table {
        height: 1fr;
        min-height: 10;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize file browser widget.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._current_path = Path.home()
        self._file_table: DataTable | None = None
        self._path_input: Input | None = None
        self._selected_files: list[Path] = []

    def compose(self) -> Any:  # pragma: no cover
        """Compose the file browser."""
        # Header with path input
        with Container(id="browser-header"):
            yield Static(_("File Browser - Select files to create torrents"), id="browser-title")
            yield Input(
                str(self._current_path),
                placeholder=_("Enter path..."),
                id="path-input",
            )

        # Main content area
        with Container(id="browser-content"):
            # File tree/table
            with Vertical(id="file-tree"):
                yield DataTable(id="file-table", zebra_stripes=True)

            # Action buttons
            with Vertical(id="file-actions"):
                yield Static(_("Actions"), id="actions-title")
                yield Button(_("Create Torrent"), id="create-torrent-btn", variant="primary")
                yield Button(_("Add to Session"), id="add-torrent-btn")
                yield Button(_("Refresh"), id="refresh-btn")
                yield Static("", id="status-message")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the file browser."""
        try:
            logger.info("FileBrowserWidget.on_mount: Starting mount process")
            self._file_table = self.query_one("#file-table", DataTable)  # type: ignore[attr-defined]
            self._path_input = self.query_one("#path-input", Input)  # type: ignore[attr-defined]
            logger.info("FileBrowserWidget.on_mount: Found _file_table: %s, _path_input: %s", 
                       self._file_table is not None, self._path_input is not None)
            
            # CRITICAL FIX: Add columns first, then populate after widget is fully rendered
            if self._file_table:
                self._file_table.add_columns("Type", "Name", "Size", "Modified")
                logger.debug("FileBrowserWidget.on_mount: Added columns to DataTable")
            
            # CRITICAL FIX: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            if self._file_table:
                self._file_table.display = True  # type: ignore[attr-defined]
            
            # Use call_after_refresh to ensure widget is fully mounted and visible
            self.call_after_refresh(self._refresh_file_list)  # type: ignore[attr-defined]
            logger.debug("FileBrowserWidget.on_mount: Scheduled refresh after mount")
        except Exception as e:
            logger.error("Error mounting file browser: %s", e, exc_info=True)
            # Try to schedule a retry
            try:
                self.call_after_refresh(self._refresh_file_list)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _refresh_file_list(self) -> None:  # pragma: no cover
        """Refresh the file list for current directory."""
        # CRITICAL FIX: Re-query _file_table if it's None (may happen if called before on_mount completes)
        if not self._file_table:
            try:
                self._file_table = self.query_one("#file-table", DataTable)  # type: ignore[attr-defined]
                logger.debug("FileBrowserWidget: Re-queried _file_table")
            except Exception as e:
                logger.warning("FileBrowserWidget: _file_table is None and cannot be queried: %s", e)
                # Schedule retry after widget is fully mounted
                self.call_after_refresh(self._refresh_file_list)  # type: ignore[attr-defined]
                return
        
        if not self._file_table:
            logger.warning("FileBrowserWidget: _file_table is None, cannot refresh")
            return

        # CRITICAL FIX: Ensure widget is visible before populating
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("FileBrowserWidget: Widget not attached or not visible, deferring refresh")
            # Schedule refresh for when widget becomes visible
            self.call_after_refresh(self._refresh_file_list)  # type: ignore[attr-defined]
            return

        try:
            # CRITICAL FIX: Ensure columns exist before clearing/adding rows
            # Textual DataTable requires columns to be added before rows
            if not self._file_table.columns:  # type: ignore[attr-defined]
                self._file_table.add_columns("Type", "Name", "Size", "Modified")
            
            self._file_table.clear()
            current = Path(self._current_path)
            
            logger.debug("FileBrowserWidget: Refreshing file list for path: %s", current)

            if not current.exists():
                self._file_table.add_row("Error", _("Path does not exist"), "", "", key="error")
                return

            # Add parent directory entry
            if current.parent != current:
                self._file_table.add_row(
                    "📁", "..", "", "", key=str(current.parent)
                )

            # List directories first
            try:
                for item in sorted(current.iterdir()):
                    if item.is_dir():
                        try:
                            # Count items in directory
                            count = len(list(item.iterdir()))
                            size_str = f"{count} items"
                        except PermissionError:
                            size_str = _("No access")
                        except Exception:
                            size_str = ""

                        self._file_table.add_row(
                            "📁",
                            item.name,
                            size_str,
                            "",
                            key=str(item),
                        )
            except PermissionError:
                self._file_table.add_row("Error", _("Permission denied"), "", "", key="permission-error")

            # List files
            try:
                for item in sorted(current.iterdir()):
                    if item.is_file():
                        try:
                            size = item.stat().st_size
                            if size >= 1024 * 1024 * 1024:
                                size_str = f"{size / (1024**3):.2f} GB"
                            elif size >= 1024 * 1024:
                                size_str = f"{size / (1024**2):.2f} MB"
                            elif size >= 1024:
                                size_str = f"{size / 1024:.2f} KB"
                            else:
                                size_str = f"{size} B"
                        except Exception:
                            size_str = _("Unknown")

                        self._file_table.add_row(
                            "📄",
                            item.name,
                            size_str,
                            "",
                            key=str(item),
                        )
            except PermissionError:
                pass  # Already handled above
            
            # CRITICAL FIX: Force DataTable refresh after adding rows
            # Textual DataTable may need explicit refresh to display new rows
            if hasattr(self._file_table, "refresh"):
                self._file_table.refresh()  # type: ignore[attr-defined]
            
            logger.debug("FileBrowserWidget: Refreshed file list, added rows to table")

        except Exception as e:
            logger.error("Error refreshing file list: %s", e, exc_info=True)
            if self._file_table:
                try:
                    self._file_table.add_row("Error", str(e), "", "", key="error")
                    if hasattr(self._file_table, "refresh"):
                        self._file_table.refresh()  # type: ignore[attr-defined]
                except Exception:
                    pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:  # pragma: no cover
        """Handle path input submission."""
        if event.input.id == "path-input":
            try:
                new_path = Path(event.value)
                if new_path.exists() and new_path.is_dir():
                    self._current_path = new_path
                    self._refresh_file_list()
                    if self._path_input:
                        self._path_input.value = str(self._current_path)
                else:
                    # Show error
                    status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
                    status.update(f"[red]Invalid path: {event.value}[/red]")
            except Exception as e:
                logger.debug("Error changing path: %s", e)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        """Handle file/directory selection."""
        try:
            row_key = event.cursor_row_key
            if not row_key:
                return

            selected_path = Path(str(row_key))

            if selected_path.is_dir():
                # Navigate to directory
                self._current_path = selected_path
                if self._path_input:
                    self._path_input.value = str(self._current_path)
                self._refresh_file_list()
            else:
                # Select file for torrent creation
                if selected_path in self._selected_files:
                    self._selected_files.remove(selected_path)
                else:
                    self._selected_files.append(selected_path)

                # Update status
                status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
                count = len(self._selected_files)
                status.update(f"[green]{count} file(s) selected[/green]")

        except Exception as e:
            logger.debug("Error handling file selection: %s", e)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "refresh-btn":
            self._refresh_file_list()
        elif event.button.id == "create-torrent-btn":
            await self._create_torrent()
        elif event.button.id == "add-torrent-btn":
            await self._add_torrent_to_session()

    async def _create_torrent(self) -> None:  # pragma: no cover
        """Create a torrent from selected files."""
        if not self._selected_files:
            status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
            status.update("[yellow]Please select files first[/yellow]")
            return

        # TODO: Open torrent creation dialog/modal
        # For now, show placeholder message
        status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
        status.update(f"[green]Creating torrent from {len(self._selected_files)} file(s)...[/green]")
        # In future: await self.app.push_screen(CreateTorrentScreen(self._selected_files))

    async def _add_torrent_to_session(self) -> None:  # pragma: no cover
        """Add selected torrent file to session."""
        # Find .torrent files in selection
        torrent_files = [f for f in self._selected_files if f.suffix == ".torrent"]

        if not torrent_files:
            status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
            status.update("[yellow]Please select .torrent file(s)[/yellow]")
            return

        # Add each torrent
        status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
        for torrent_file in torrent_files:
            try:
                result = await self._command_executor.execute_command(
                    "torrent.add",
                    path_or_magnet=str(torrent_file),
                )
                if result.success:
                    status.update(f"[green]Added: {torrent_file.name}[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")
            except Exception as e:
                logger.debug("Error adding torrent: %s", e)
                status.update(f"[red]Error: {e}[/red]")

