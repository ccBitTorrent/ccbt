"""Torrent file explorer widget for browsing downloaded files from torrent metadata."""

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
    from textual.widgets import DataTable, Static, Button, Input
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)


class TorrentFileExplorerWidget(Container):  # type: ignore[misc]
    """File explorer widget for browsing torrent files using metadata."""

    DEFAULT_CSS = """
    TorrentFileExplorerWidget {
        height: 1fr;
        layout: vertical;
    }
    
    #explorer-header {
        height: 3;
        layout: horizontal;
        border-bottom: solid $primary;
    }
    
    #path-display {
        width: 1fr;
        height: 1;
        margin: 0 1;
    }
    
    #explorer-content {
        height: 1fr;
        layout: horizontal;
    }
    
    #file-table {
        width: 2fr;
        height: 1fr;
        border-right: solid $primary;
    }
    
    #file-details {
        width: 3fr;
        height: 1fr;
        layout: vertical;
    }
    
    #details-table {
        height: 1fr;
    }
    
    #explorer-actions {
        height: auto;
        padding: 1;
        border-top: solid $primary;
    }
    
    #explorer-actions Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        info_hash_hex: str,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent file explorer widget.

        Args:
            info_hash_hex: Torrent info hash in hex format
            data_provider: DataProvider instance for accessing torrent data
            command_executor: CommandExecutor instance for executing commands
        """
        super().__init__(*args, **kwargs)
        self._info_hash = info_hash_hex
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._file_table: DataTable | None = None
        self._details_table: DataTable | None = None
        self._path_display: Static | None = None
        self._files_data: list[dict[str, Any]] = []
        self._base_path: Path | None = None
        self._selected_file: dict[str, Any] | None = None
        self._expanded_dirs: set[str] = set()

    def compose(self) -> Any:  # pragma: no cover
        """Compose the file explorer widget."""
        # Header with path display
        with Container(id="explorer-header"):
            yield Static(_("Torrent File Explorer"), id="explorer-title")
            yield Static("", id="path-display")
        
        # Main content area
        with Container(id="explorer-content"):
            # File tree (left side) - using DataTable for hierarchical display
            yield DataTable(id="file-table", zebra_stripes=True)
            
            # File details (right side)
            with Container(id="file-details"):
                yield DataTable(id="details-table", zebra_stripes=True)
        
        # Action buttons
        with Horizontal(id="explorer-actions"):
            yield Button(_("Refresh"), id="refresh-button", variant="default")
            yield Button(_("Open Folder"), id="open-folder-button", variant="default")
            yield Button(_("Open File"), id="open-file-button", variant="primary")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the file explorer widget."""
        try:
            self._file_table = self.query_one("#file-table", DataTable)  # type: ignore[attr-defined]
            self._details_table = self.query_one("#details-table", DataTable)  # type: ignore[attr-defined]
            self._path_display = self.query_one("#path-display", Static)  # type: ignore[attr-defined]
            
            if self._file_table:
                self._file_table.add_columns(
                    _("Name"),
                    _("Size"),
                    _("Progress"),
                    _("Status"),
                )
                self._file_table.zebra_stripes = True
                self._file_table.cursor_type = "row"
            
            if self._details_table:
                self._details_table.add_columns(
                    _("Property"),
                    _("Value"),
                )
                self._details_table.zebra_stripes = True
            
            # Load files and build tree
            self.set_interval(3.0, self._refresh_files)  # type: ignore[attr-defined]
            self.call_later(self._refresh_files)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting torrent file explorer: %s", e)

    def on_language_changed(self, message: Any) -> None:  # pragma: no cover
        """Handle language change event.

        Args:
            message: LanguageChanged message with new locale
        """
        try:
            from ccbt.interface.widgets.language_selector import (
                LanguageSelectorWidget,
            )

            # Verify this is a LanguageChanged message
            if not hasattr(message, "locale"):
                return

            # Update title
            try:
                title = self.query_one("#explorer-title", Static)  # type: ignore[attr-defined]
                title.update(_("Torrent File Explorer"))
            except Exception:
                pass

            # Update file table column headers
            if self._file_table:
                try:
                    self._file_table.clear_columns()  # type: ignore[attr-defined]
                    self._file_table.add_columns(
                        _("Name"),
                        _("Size"),
                        _("Progress"),
                        _("Status"),
                    )
                    # Trigger refresh to repopulate with new headers
                    self.call_later(self._refresh_files)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("Error updating file table columns: %s", e)

            # Update details table column headers
            if self._details_table:
                try:
                    self._details_table.clear_columns()  # type: ignore[attr-defined]
                    self._details_table.add_columns(
                        _("Property"),
                        _("Value"),
                    )
                    # Refresh details if a file is selected
                    if self._selected_file:
                        self._update_file_details(self._selected_file)
                except Exception as e:
                    logger.debug("Error updating details table columns: %s", e)

            # Update button labels
            try:
                refresh_btn = self.query_one("#refresh-button", Button)  # type: ignore[attr-defined]
                refresh_btn.label = _("Refresh")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                open_folder_btn = self.query_one("#open-folder-button", Button)  # type: ignore[attr-defined]
                open_folder_btn.label = _("Open Folder")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                open_file_btn = self.query_one("#open-file-button", Button)  # type: ignore[attr-defined]
                open_file_btn.label = _("Open File")  # type: ignore[attr-defined]
            except Exception:
                pass

        except Exception as e:
            logger.debug("Error refreshing file explorer translations: %s", e)

    async def _refresh_files(self) -> None:  # pragma: no cover
        """Refresh file list from data provider."""
        if not self._data_provider or not self._info_hash:
            return
        
        try:
            # Get torrent files
            files = await self._data_provider.get_torrent_files(self._info_hash)
            self._files_data = files
            
            # Get torrent status to find base path
            status = await self._data_provider.get_torrent_status(self._info_hash)
            if status:
                # Try to get output directory from status
                output_dir = status.get("output_dir") or status.get("save_path")
                if output_dir:
                    self._base_path = Path(output_dir)
            
            # Fallback: extract base path from file paths
            if not self._base_path and files:
                # Find common base path from all file paths
                absolute_paths = []
                for file_info in files:
                    path_str = file_info.get("path", "")
                    if path_str:
                        path = Path(path_str)
                        if path.is_absolute():
                            absolute_paths.append(path)
                
                if absolute_paths:
                    # Find common parent directory
                    if len(absolute_paths) == 1:
                        self._base_path = absolute_paths[0].parent
                    else:
                        # Find common prefix
                        common_parts = []
                        for parts in zip(*[p.parts for p in absolute_paths]):
                            if len(set(parts)) == 1:
                                common_parts.append(parts[0])
                            else:
                                break
                        if common_parts:
                            self._base_path = Path(*common_parts)
                        else:
                            # Use parent of first file
                            self._base_path = absolute_paths[0].parent
            
            # Build file tree
            self._build_file_tree()
            
            # Update path display
            if self._path_display and self._base_path:
                self._path_display.update(f"Base Path: {self._base_path}")
        except Exception as e:
            logger.debug("Error refreshing files: %s", e)

    def _build_file_tree(self) -> None:  # pragma: no cover
        """Build hierarchical file list from torrent files."""
        if not self._file_table or not self._files_data:
            return
        
        try:
            # Clear existing table
            self._file_table.clear()
            
            # Organize files into directory structure
            file_tree: dict[str, Any] = {}
            
            for file_info in self._files_data:
                path_str = file_info.get("path", "")
                if not path_str:
                    continue
                
                # Handle both absolute and relative paths
                if Path(path_str).is_absolute():
                    path = Path(path_str)
                else:
                    # Relative path - use as is
                    path = Path(path_str)
                
                # Get relative path from base if available
                if self._base_path and path.is_absolute():
                    try:
                        rel_path = path.relative_to(self._base_path)
                    except ValueError:
                        rel_path = path
                else:
                    rel_path = path
                
                # Build tree structure
                parts = rel_path.parts
                if not parts:
                    continue
                
                current = file_tree
                
                # Navigate/create directory structure
                for part in parts[:-1]:  # All but the last part (filename)
                    if part not in current:
                        current[part] = {"_type": "dir", "_children": {}}
                    elif current[part].get("_type") != "dir":
                        # Convert to directory if it was a file (shouldn't happen, but handle it)
                        current[part] = {"_type": "dir", "_children": {}}
                    current = current[part]["_children"]
                
                # Add file to current directory
                filename = parts[-1] if parts else str(path.name)
                current[filename] = {"_type": "file", "_info": file_info, "_path": rel_path}
            
            # Recursively add rows to table
            self._add_table_rows(file_tree, depth=0, path_prefix="")
        except Exception as e:
            logger.debug("Error building file tree: %s", e)

    def _add_table_rows(self, tree_data: dict[str, Any], depth: int = 0, path_prefix: str = "") -> None:  # pragma: no cover
        """Recursively add rows to the table.
        
        Args:
            tree_data: Dictionary representing directory structure
            depth: Current depth in the tree (for indentation)
            path_prefix: Path prefix for this level
        """
        if not self._file_table:
            return
        
        for name, value in sorted(tree_data.items()):
            if isinstance(value, dict):
                if value.get("_type") == "file":
                    # This is a file
                    file_info = value.get("_info", {})
                    size = file_info.get("size", 0)
                    progress = file_info.get("progress", 0.0)
                    selected = file_info.get("selected", True)
                    
                    # Format display
                    indent = "  " * depth
                    size_str = self._format_size(size)
                    progress_str = f"{progress * 100:.1f}%"
                    status_icon = "✓" if selected else "✗"
                    name_display = f"{indent}📄 {name}"
                    
                    row_key = str(value.get("_path", name))
                    self._file_table.add_row(
                        name_display,
                        size_str,
                        progress_str,
                        status_icon,
                        key=row_key,
                    )
                elif value.get("_type") == "dir":
                    # This is a directory
                    indent = "  " * depth
                    dir_path = f"{path_prefix}/{name}" if path_prefix else name
                    name_display = f"{indent}📁 {name}/"
                    
                    # Add directory row (non-selectable, just for display)
                    self._file_table.add_row(
                        name_display,
                        "",
                        "",
                        "",
                        key=f"dir:{dir_path}",
                    )
                    
                    # Recursively add children
                    children = value.get("_children", {})
                    if children:
                        self._add_table_rows(children, depth + 1, dir_path)

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size >= 1024 * 1024 * 1024:
            return f"{size / (1024**3):.2f} GB"
        elif size >= 1024 * 1024:
            return f"{size / (1024**2):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} B"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        """Handle file selection in table."""
        row_key = str(event.row_key) if event.row_key else ""
        
        # Skip directory rows
        if row_key.startswith("dir:"):
            return
        
        # Find file info by matching the row key (which is the relative path)
        for file_info in self._files_data:
            path_str = file_info.get("path", "")
            if not path_str:
                continue
            
            # Get relative path for comparison
            if Path(path_str).is_absolute():
                path = Path(path_str)
                if self._base_path:
                    try:
                        rel_path = str(path.relative_to(self._base_path))
                    except ValueError:
                        rel_path = str(path)
                else:
                    rel_path = str(path)
            else:
                rel_path = path_str
            
            # Match by relative path
            if rel_path == row_key or str(Path(rel_path)) == str(Path(row_key)):
                self._selected_file = file_info
                self._update_file_details(file_info)
                return

    def _update_file_details(self, file_info: dict[str, Any]) -> None:  # pragma: no cover
        """Update file details table.
        
        Args:
            file_info: Dictionary containing file information
        """
        if not self._details_table:
            return
        
        try:
            self._details_table.clear()
            
            # Add file details
            details = [
                (_("Path"), file_info.get("path", "Unknown")),
                (_("Size"), self._format_size(file_info.get("size", 0))),
                (_("Progress"), f"{file_info.get('progress', 0.0) * 100:.1f}%"),
                (_("Priority"), str(file_info.get("priority", "normal")).title()),
                (_("Selected"), "Yes" if file_info.get("selected", True) else "No"),
                (_("Index"), str(file_info.get("index", "Unknown"))),
            ]
            
            # Add downloaded bytes if available
            if "downloaded" in file_info:
                details.append((_("Downloaded"), self._format_size(file_info.get("downloaded", 0))))
            
            # Add file path on disk if available
            file_path = file_info.get("path", "")
            if file_path:
                path_obj = Path(file_path)
                if path_obj.is_absolute():
                    details.append((_("Full Path"), str(path_obj)))
                    details.append((_("Exists"), "Yes" if path_obj.exists() else "No"))
            
            for key, value in details:
                self._details_table.add_row(key, str(value), key=key)
        except Exception as e:
            logger.debug("Error updating file details: %s", e)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "refresh-button":
            await self._refresh_files()
        elif event.button.id == "open-folder-button":
            if self._base_path and self._base_path.exists():
                import platform
                import subprocess
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(["explorer", str(self._base_path)])
                elif system == "Darwin":
                    subprocess.Popen(["open", str(self._base_path)])
                else:
                    subprocess.Popen(["xdg-open", str(self._base_path)])
        elif event.button.id == "open-file-button":
            if self._selected_file:
                file_path = self._selected_file.get("path", "")
                if file_path:
                    path_obj = Path(file_path)
                    if path_obj.exists():
                        import platform
                        import subprocess
                        system = platform.system()
                        if system == "Windows":
                            subprocess.Popen(["start", "", str(path_obj)], shell=True)
                        elif system == "Darwin":
                            subprocess.Popen(["open", str(path_obj)])
                        else:
                            subprocess.Popen(["xdg-open", str(path_obj)])

