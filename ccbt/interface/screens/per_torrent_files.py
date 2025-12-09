"""Files sub-tab screen for Per-Torrent tab.

Displays file list for a selected torrent with file selection and priority controls.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

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
    from textual.screen import ModalScreen
    from textual.widgets import DataTable, Static, Button, Select
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class ModalScreen:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        pass

from ccbt.interface.widgets.reusable_table import ReusableDataTable
from ccbt.i18n import _

logger = logging.getLogger(__name__)


class TorrentFilesScreen(Container):  # type: ignore[misc]
    """Screen for displaying torrent files with selection and priority controls."""

    DEFAULT_CSS = """
    TorrentFilesScreen {
        height: 1fr;
        layout: vertical;
    }
    
    #files-table {
        height: 1fr;
    }
    
    #file-actions {
        height: auto;
        padding: 1;
        align-horizontal: center;
    }
    
    #file-actions Button {
        margin-right: 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("s", "select_all_files", _("Select All")),
        ("u", "deselect_all_files", _("Deselect All")),
        ("p", "set_file_priority", _("Set Priority")),
    ]

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        info_hash: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent files screen.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
            info_hash: Torrent info hash in hex format
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._info_hash = info_hash
        self._files_table: DataTable | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the files screen."""
        yield ReusableDataTable(id="files-table")
        with Horizontal(id="file-actions"):
            yield Button(_("Select All"), id="select-all-button", variant="primary")
            yield Button(_("Deselect All"), id="deselect-all-button", variant="default")
            yield Button(_("Set Priority"), id="set-priority-button", variant="default")
            yield Button(_("Open Folder"), id="open-folder-button", variant="default")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the files screen."""
        try:
            self._files_table = self.query_one("#files-table", DataTable)  # type: ignore[attr-defined]
            
            if self._files_table:
                self._files_table.add_columns(
                    _("Path"),
                    _("Size"),
                    _("Progress"),
                    _("Priority"),
                    _("Selected"),
                )
                self._files_table.zebra_stripes = True
                self._files_table.cursor_type = "row"
            
            # Schedule periodic refresh
            self.set_interval(2.0, self.refresh_files)  # type: ignore[attr-defined]
            # Initial refresh
            self.call_later(self.refresh_files)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting files screen: %s", e)

    async def refresh_files(self) -> None:  # pragma: no cover
        """Refresh files table with latest data."""
        if not self._files_table or not self._data_provider or not self._info_hash:
            return
        
        try:
            files = await self._data_provider.get_torrent_files(self._info_hash)
            
            # Clear and repopulate table
            self._files_table.clear()
            for file_info in files:
                path = file_info.get("path", "Unknown")
                size = file_info.get("size", 0)
                progress = file_info.get("progress", 0.0)
                priority = file_info.get("priority", "normal")
                selected = file_info.get("selected", True)
                
                # Format size
                if size >= 1024 * 1024 * 1024:
                    size_str = f"{size / (1024**3):.2f} GB"
                elif size >= 1024 * 1024:
                    size_str = f"{size / (1024**2):.2f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size} B"
                
                # Format progress
                progress_str = f"{progress * 100:.1f}%"
                
                # Format priority
                priority_str = str(priority).title()
                
                # Format selected
                selected_str = "✓" if selected else "✗"
                
                # Use path as key for row identification
                self._files_table.add_row(
                    path,
                    size_str,
                    progress_str,
                    priority_str,
                    selected_str,
                    key=path,
                )
        except Exception as e:
            logger.debug("Error refreshing files: %s", e)

    async def action_select_all_files(self) -> None:  # pragma: no cover
        """Select all files."""
        if not self._files_table or not self._command_executor or not self._info_hash:
            return
        
        try:
            # Get all file indices from the files list
            files = await self._data_provider.get_torrent_files(self._info_hash)
            file_indices = [file_info.get("index", idx) for idx, file_info in enumerate(files)]
            
            if not file_indices:
                self.app.notify(_("No files to select"), severity="warning")  # type: ignore[attr-defined]
                return
            
            # Use executor to select all files
            result = await self._command_executor.execute_command(
                "file.select",
                info_hash=self._info_hash,
                file_indices=file_indices,
            )
            
            if result and hasattr(result, "success") and result.success:
                self.app.notify(_("Selected {count} file(s)").format(count=len(file_indices)), severity="success")  # type: ignore[attr-defined]
                # Refresh to show updated selection
                await self.refresh_files()
            else:
                error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                self.app.notify(_("Failed to select files: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            self.app.notify(_("Error selecting files: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_deselect_all_files(self) -> None:  # pragma: no cover
        """Deselect all files."""
        if not self._files_table or not self._command_executor or not self._info_hash:
            return
        
        try:
            # Get all file indices from the files list
            files = await self._data_provider.get_torrent_files(self._info_hash)
            file_indices = [file_info.get("index", idx) for idx, file_info in enumerate(files)]
            
            if not file_indices:
                self.app.notify(_("No files to deselect"), severity="warning")  # type: ignore[attr-defined]
                return
            
            # Use executor to deselect all files
            result = await self._command_executor.execute_command(
                "file.deselect",
                info_hash=self._info_hash,
                file_indices=file_indices,
            )
            
            if result and hasattr(result, "success") and result.success:
                self.app.notify(_("Deselected {count} file(s)").format(count=len(file_indices)), severity="success")  # type: ignore[attr-defined]
                # Refresh to show updated selection
                await self.refresh_files()
            else:
                error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                self.app.notify(_("Failed to deselect files: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            self.app.notify(_("Error deselecting files: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_set_file_priority(self) -> None:  # pragma: no cover
        """Set priority for selected files."""
        if not self._files_table or not self._command_executor or not self._info_hash:
            return
        
        try:
            # Get selected file key (path)
            selected_key = self._files_table.get_selected_key()
            if not selected_key:
                self.app.notify(_("No file selected"), severity="warning")  # type: ignore[attr-defined]
                return
            
            # Get file index from the files list
            files = await self._data_provider.get_torrent_files(self._info_hash)
            file_index = None
            current_priority = "normal"
            for idx, file_info in enumerate(files):
                if file_info.get("path") == selected_key:
                    file_index = file_info.get("index", idx)
                    current_priority = file_info.get("priority", "normal")
                    break
            
            if file_index is None:
                self.app.notify(_("Could not find file index"), severity="error")  # type: ignore[attr-defined]
                return
            
            # Show priority selection dialog
            dialog = PrioritySelectDialog(current_priority)
            priority = await self.app.push_screen_wait(dialog)  # type: ignore[attr-defined]
            
            if priority is None:
                return  # User cancelled
            
            # Use executor to set file priority
            result = await self._command_executor.execute_command(
                "file.priority",
                info_hash=self._info_hash,
                file_index=file_index,
                priority=priority,
            )
            
            if result and hasattr(result, "success") and result.success:
                self.app.notify(_("Set priority to {priority} for file").format(priority=priority), severity="success")  # type: ignore[attr-defined]
                # Refresh to show updated priority
                await self.refresh_files()
            else:
                error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                self.app.notify(_("Failed to set priority: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            self.app.notify(_("Error setting file priority: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "select-all-button":
            await self.action_select_all_files()
        elif event.button.id == "deselect-all-button":
            await self.action_deselect_all_files()
        elif event.button.id == "set-priority-button":
            await self.action_set_file_priority()
        elif event.button.id == "open-folder-button":
            # Open folder using OS-specific command
            try:
                import subprocess
                import platform
                import os
                
                # Get output directory from torrent status
                status = await self._data_provider.get_torrent_status(self._info_hash)
                if status:
                    output_dir = status.get("output_dir", ".")
                    if platform.system() == "Windows":
                        os.startfile(output_dir)  # type: ignore[attr-defined]
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", output_dir])
                    else:  # Linux
                        subprocess.run(["xdg-open", output_dir])
                    self.app.notify(_("Opened folder: {path}").format(path=output_dir), severity="success")  # type: ignore[attr-defined]
                else:
                    self.app.notify(_("Could not get torrent output directory"), severity="warning")  # type: ignore[attr-defined]
            except Exception as e:
                self.app.notify(_("Error opening folder: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]


class PrioritySelectDialog(ModalScreen):  # type: ignore[misc]
    """Dialog for selecting file priority."""

    DEFAULT_CSS = """
    PrioritySelectDialog {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    #priority-select {
        width: 1fr;
        margin: 1;
    }
    #buttons {
        height: 3;
        align: center middle;
        margin: 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", _("Cancel")),
        ("enter", "confirm", _("Confirm")),
    ]

    def __init__(
        self,
        current_priority: str = "normal",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize priority selection dialog.

        Args:
            current_priority: Current priority value (default: "normal")
        """
        super().__init__(*args, **kwargs)
        self._current_priority = current_priority
        self._selected_priority: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the priority selection dialog."""
        with Vertical(id="dialog"):
            yield Static(_("Select File Priority"), id="title")
            # Priority options matching FilePriority enum
            priority_options = [
                (_("Maximum"), "maximum"),
                (_("High"), "high"),
                (_("Normal"), "normal"),
                (_("Low"), "low"),
                (_("Do Not Download"), "do_not_download"),
            ]
            yield Select(
                priority_options,
                value=self._current_priority,
                id="priority-select",
                prompt=_("Select Priority"),
            )
            with Horizontal(id="buttons"):
                yield Button(_("Confirm"), id="confirm", variant="primary")
                yield Button(_("Cancel"), id="cancel", variant="default")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the dialog and focus the select widget."""
        try:
            select_widget = self.query_one("#priority-select", Select)  # type: ignore[attr-defined]
            select_widget.focus()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting priority dialog: %s", e)

    def on_select_changed(self, event: Select.Changed) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle priority selection change."""
        if hasattr(event, "value") and event.value:
            self._selected_priority = event.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "confirm":
            try:
                select_widget = self.query_one("#priority-select", Select)  # type: ignore[attr-defined]
                priority = select_widget.value or self._current_priority  # type: ignore[attr-defined]
                self.dismiss(priority)  # type: ignore[attr-defined]
            except Exception:
                self.dismiss(self._current_priority)  # type: ignore[attr-defined]
        elif event.button.id == "cancel":
            self.dismiss(None)  # type: ignore[attr-defined]

    async def action_confirm(self) -> None:  # pragma: no cover
        """Confirm priority selection."""
        try:
            select_widget = self.query_one("#priority-select", Select)  # type: ignore[attr-defined]
            priority = select_widget.value or self._current_priority  # type: ignore[attr-defined]
            self.dismiss(priority)  # type: ignore[attr-defined]
        except Exception:
            self.dismiss(self._current_priority)  # type: ignore[attr-defined]

    async def action_cancel(self) -> None:  # pragma: no cover
        """Cancel priority selection."""
        self.dismiss(None)  # type: ignore[attr-defined]
