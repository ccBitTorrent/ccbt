"""File selection dialog for torrent files.

Allows users to select/deselect files after adding a torrent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.screen import ComposeResult
else:
    try:
        from textual.screen import ComposeResult
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Checkbox, Static
except ImportError:
    # Fallback for when Textual is not available
    class ModalScreen:  # type: ignore[no-redef]
        """ModalScreen class stub."""

    class Container:  # type: ignore[no-redef]
        """Container widget stub."""

    class Horizontal:  # type: ignore[no-redef]
        """Horizontal layout widget stub."""

    class Vertical:  # type: ignore[no-redef]
        """Vertical layout widget stub."""

    class Static:  # type: ignore[no-redef]
        """Static widget stub."""

    class Button:  # type: ignore[no-redef]
        """Button widget stub."""

    class Checkbox:  # type: ignore[no-redef]
        """Checkbox widget stub."""

from ccbt.i18n import _

logger = logging.getLogger(__name__)


class FileSelectionDialog(ModalScreen):  # type: ignore[misc]
    """Dialog for selecting files in a torrent."""

    DEFAULT_CSS = """
    FileSelectionDialog {
        align: center middle;
    }
    #dialog {
        width: 80;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    #title {
        text-align: center;
        text-style: bold;
        margin: 1;
    }
    #files-container {
        height: 1fr;
        overflow-y: auto;
        margin: 1;
    }
    #file-checkbox {
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
        ("a", "select_all", _("Select All")),
        ("d", "deselect_all", _("Deselect All")),
    ]

    def __init__(
        self,
        files: list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize file selection dialog.

        Args:
            files: List of file dicts with keys: index, name, size, selected
        """
        super().__init__(*args, **kwargs)
        self._files = files
        self._checkboxes: dict[int, Checkbox] = {}

    def compose(self) -> ComposeResult:  # type: ignore[override]  # pragma: no cover
        """Compose the file selection dialog."""
        with Vertical(id="dialog"):
            yield Static(_("Select Files to Download"), id="title")
            with Vertical(id="files-container"):
                for file_info in self._files:
                    file_index = file_info.get("index", 0)
                    file_name = file_info.get("name", file_info.get("path", "Unknown"))
                    file_size = file_info.get("size", 0)
                    is_selected = file_info.get("selected", True)
                    
                    # Format file size
                    size_str = self._format_size(file_size)
                    
                    checkbox_id = f"file-checkbox-{file_index}"
                    checkbox = Checkbox(
                        f"{file_name} ({size_str})",
                        value=is_selected,
                        id=checkbox_id,
                    )
                    self._checkboxes[file_index] = checkbox
                    yield checkbox
            
            with Horizontal(id="buttons"):
                yield Button(_("Select All"), id="select-all", variant="default")
                yield Button(_("Deselect All"), id="deselect-all", variant="default")
                yield Button(_("Confirm"), id="confirm", variant="primary")
                yield Button(_("Cancel"), id="cancel", variant="default")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "confirm":
            selected_indices = [
                idx
                for idx, checkbox in self._checkboxes.items()
                if checkbox.value
            ]
            self.dismiss(selected_indices)  # type: ignore[attr-defined]
        elif event.button.id == "cancel":
            self.dismiss(None)  # type: ignore[attr-defined]
        elif event.button.id == "select-all":
            await self.action_select_all()
        elif event.button.id == "deselect-all":
            await self.action_deselect_all()

    async def action_select_all(self) -> None:  # pragma: no cover
        """Select all files."""
        for checkbox in self._checkboxes.values():
            checkbox.value = True  # type: ignore[attr-defined]

    async def action_deselect_all(self) -> None:  # pragma: no cover
        """Deselect all files."""
        for checkbox in self._checkboxes.values():
            checkbox.value = False  # type: ignore[attr-defined]

    async def action_confirm(self) -> None:  # pragma: no cover
        """Confirm file selection."""
        selected_indices = [
            idx
            for idx, checkbox in self._checkboxes.items()
            if checkbox.value  # type: ignore[attr-defined]
        ]
        self.dismiss(selected_indices)  # type: ignore[attr-defined]

    async def action_cancel(self) -> None:  # pragma: no cover
        """Cancel file selection."""
        self.dismiss(None)  # type: ignore[attr-defined]




















