"""File selection screen for managing torrent file selection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
    from textual.screen import ComposeResult
else:
    try:
        from textual.screen import ComposeResult
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]

try:
    from textual.screen import Screen
    from textual.widgets import DataTable, Input, Static
except ImportError:
    # Fallback for when Textual is not available
    class Screen:  # type: ignore[no-redef]
        """Screen class stub."""

    class Static:  # type: ignore[no-redef]
        """Static widget stub."""

    class DataTable:  # type: ignore[no-redef]
        """DataTable widget stub."""

        cursor_row_key = None

    class Input:  # type: ignore[no-redef]
        """Input widget stub."""

        class Submitted:  # minimal shim for type
            """Submitted event stub."""

            def __init__(self):
                """Initialize submitted event."""
                self.input = None
                self.value = ""

from rich.panel import Panel

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager


class FileSelectionScreen(Screen):  # type: ignore[misc]
    """Dedicated screen for file selection management.

    Provides interactive UI for selecting/deselecting files and setting priorities.
    Similar to InteractiveCLI's _interactive_file_selection but using Textual widgets.
    """

    CSS = """
    FileSelectionScreen {
        layout: vertical;
    }
    #header {
        height: 3;
        border: thick $primary;
    }
    #files_table {
        height: 1fr;
        min-height: 10;
    }
    #status {
        height: 3;
        border: thick $primary;
    }
    #commands {
        height: 3;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("space", "toggle_selection", "Toggle Selection"),
        ("a", "select_all", "Select All"),
        ("d", "deselect_all", "Deselect All"),
        ("p", "set_priority", "Set Priority"),
        ("s", "save", "Save Changes"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        info_hash_hex: str,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize file selection screen.

        Args:
            session: Async session manager
            info_hash_hex: Torrent info hash (hex string)
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            *args, **kwargs
        )  # pragma: no cover - UI initialization, tested via integration
        self.session = session  # pragma: no cover - UI initialization
        self.info_hash_hex = info_hash_hex  # pragma: no cover - UI initialization
        self.info_hash_bytes = bytes.fromhex(
            info_hash_hex
        )  # pragma: no cover - UI initialization
        self.file_manager: Any | None = None  # pragma: no cover - UI initialization
        self._refresh_task: asyncio.Task | None = (
            None  # pragma: no cover - UI initialization
        )

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the file selection screen."""
        yield Static("File Selection", id="header")
        yield DataTable(id="files_table", zebra_stripes=True)
        yield Static("", id="status")
        yield Static(
            "Commands: Space=Toggle, A=Select All, D=Deselect All, P=Priority, S=Save, Esc=Back",
            id="commands",
        )

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and load file data."""
        # Get torrent session and file manager
        async with self.session.lock:
            torrent_session = self.session.torrents.get(self.info_hash_bytes)
            if torrent_session and torrent_session.file_selection_manager:
                self.file_manager = torrent_session.file_selection_manager
            else:
                status_widget = self.query_one("#status", Static)
                status_widget.update(
                    Panel(
                        "File selection not available for this torrent",
                        title="Error",
                        border_style="red",
                    )
                )
                return

        await self._refresh_table()

        # Schedule periodic refresh
        self._refresh_task = self.set_interval(2.0, self._refresh_table)  # type: ignore[attr-defined]

    async def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the screen and cleanup."""
        if self._refresh_task:
            self._refresh_task.stop()  # type: ignore[attr-defined]

    async def _refresh_table(self) -> None:  # pragma: no cover
        """Refresh the files table with current state."""
        if not self.file_manager:
            return

        try:
            all_states = self.file_manager.get_all_file_states()
            table = self.query_one("#files_table", DataTable)
            status_widget = self.query_one("#status", Static)

            # Clear and rebuild table
            table.clear()
            # Always add columns (clear() removes them)
            table.add_columns(
                "#", "Selected", "Priority", "Progress", "Size", "File Name"
            )

            # Get statistics
            stats = self.file_manager.get_statistics()
            total = stats.get("total_files", 0)
            selected = stats.get("selected_files", 0)

            # Add rows
            for file_idx in sorted(all_states.keys()):
                state = all_states[file_idx]
                file_info = self.file_manager.torrent_info.files[file_idx]

                selected_mark = "✓" if state.selected else " "
                priority_str = state.priority.name.lower()

                # Calculate progress
                progress_pct = 0.0
                if state.bytes_total > 0:
                    progress_pct = (state.bytes_downloaded / state.bytes_total) * 100.0

                # Format size
                size_mb = file_info.length / (1024 * 1024)
                size_str = (
                    f"{size_mb:.2f} MB"
                    if size_mb >= 1
                    else f"{file_info.length / 1024:.2f} KB"
                )

                table.add_row(
                    str(file_idx),
                    selected_mark,
                    priority_str,
                    f"{progress_pct:.1f}%",
                    size_str,
                    file_info.name,
                    key=str(file_idx),
                )

            # Update status
            status_text = f"Total: {total} | Selected: {selected} | Deselected: {total - selected}"
            status_widget.update(
                Panel(status_text, title="File Selection Status", border_style="blue")
            )

        except Exception as e:
            status_widget = self.query_one("#status", Static)
            status_widget.update(
                Panel(f"Error refreshing table: {e}", title="Error", border_style="red")
            )

    async def action_back(self) -> None:  # pragma: no cover
        """Navigate back."""
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def action_quit(self) -> None:  # pragma: no cover
        """Quit the screen."""
        await self.action_back()

    async def action_toggle_selection(self) -> None:  # pragma: no cover
        """Toggle selection of currently selected file."""
        if not self.file_manager:
            return

        table = self.query_one("#files_table", DataTable)
        selected_key = getattr(table, "cursor_row_key", None)
        if not selected_key:
            return

        try:
            file_idx = int(selected_key)
            all_states = self.file_manager.get_all_file_states()
            if file_idx not in all_states:
                return

            state = all_states[file_idx]
            if state.selected:
                await self.file_manager.deselect_file(file_idx)
            else:
                await self.file_manager.select_file(file_idx)

            await self._refresh_table()
        except (ValueError, KeyError):
            pass

    async def action_select_all(self) -> None:  # pragma: no cover
        """Select all files."""
        if not self.file_manager:
            return
        await self.file_manager.select_all()
        await self._refresh_table()

    async def action_deselect_all(self) -> None:  # pragma: no cover
        """Deselect all files."""
        if not self.file_manager:
            return
        await self.file_manager.deselect_all()
        await self._refresh_table()

    async def action_set_priority(self) -> None:  # pragma: no cover
        """Set priority for currently selected file."""
        if not self.file_manager:
            return

        table = self.query_one("#files_table", DataTable)
        selected_key = getattr(table, "cursor_row_key", None)
        if not selected_key:
            return

        try:
            file_idx = int(selected_key)

            # Show priority selection input
            priority_input = Input(
                placeholder="Priority: do_not_download/low/normal/high/maximum",
                id="priority_input",
            )
            self.mount(priority_input)  # type: ignore[attr-defined]
            priority_input.focus()
            self._pending_priority_file = file_idx  # type: ignore[attr-defined]

        except (ValueError, KeyError):
            pass

    async def action_save(self) -> None:  # pragma: no cover
        """Save changes (no-op, changes are applied immediately)."""
        status_widget = self.query_one("#status", Static)
        status_widget.update(
            Panel("Changes saved", title="Success", border_style="green")
        )

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submission for priority setting."""
        if message.input.id == "priority_input":
            priority_str = message.value.strip().lower()
            message.input.display = False

            file_idx = getattr(self, "_pending_priority_file", None)
            if file_idx is None or not self.file_manager:
                return

            from ccbt.piece.file_selection import FilePriority

            priority_map = {
                "do_not_download": FilePriority.DO_NOT_DOWNLOAD,
                "low": FilePriority.LOW,
                "normal": FilePriority.NORMAL,
                "high": FilePriority.HIGH,
                "maximum": FilePriority.MAXIMUM,
            }

            if priority_str in priority_map:
                await self.file_manager.set_file_priority(
                    file_idx, priority_map[priority_str]
                )
                await self._refresh_table()
                self._pending_priority_file = None  # type: ignore[attr-defined]
            else:
                status_widget = self.query_one("#status", Static)
                status_widget.update(
                    Panel(
                        f"Invalid priority: {priority_str}. Use: do_not_download/low/normal/high/maximum",
                        title="Error",
                        border_style="red",
                    )
                )

