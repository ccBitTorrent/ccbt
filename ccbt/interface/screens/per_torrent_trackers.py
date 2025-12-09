"""Trackers sub-tab screen for Per-Torrent tab.

Displays tracker information for a selected torrent.
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
    from textual.containers import Container, Vertical, Horizontal
    from textual.widgets import DataTable, Static, Input, Button
    from textual.screen import ModalScreen
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class ModalScreen:  # type: ignore[no-redef]
        pass

from ccbt.interface.widgets.reusable_table import ReusableDataTable
from ccbt.i18n import _

logger = logging.getLogger(__name__)


class TorrentTrackersScreen(Container):  # type: ignore[misc]
    """Screen for displaying torrent trackers."""

    DEFAULT_CSS = """
    TorrentTrackersScreen {
        height: 1fr;
        layout: vertical;
    }
    
    #trackers-table {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("a", "add_tracker", _("Add Tracker")),
        ("r", "remove_tracker", _("Remove Tracker")),
        ("f", "force_announce", _("Force Announce")),
    ]

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        info_hash: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent trackers screen.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
            info_hash: Torrent info hash in hex format
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._info_hash = info_hash
        self._trackers_table: DataTable | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the trackers screen."""
        yield ReusableDataTable(id="trackers-table")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the trackers screen."""
        try:
            self._trackers_table = self.query_one("#trackers-table", DataTable)  # type: ignore[attr-defined]
            
            if self._trackers_table:
                self._trackers_table.add_columns(
                    _("URL"),
                    _("Status"),
                    _("Seeds"),
                    _("Peers"),
                    _("Downloaders"),
                    _("Last Update"),
                )
                self._trackers_table.zebra_stripes = True
            
            # Schedule periodic refresh
            self.set_interval(5.0, self.refresh_trackers)  # type: ignore[attr-defined]
            # Initial refresh
            self.call_later(self.refresh_trackers)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting trackers screen: %s", e)

    async def refresh_trackers(self) -> None:  # pragma: no cover
        """Refresh trackers table with latest data."""
        if not self._trackers_table or not self._data_provider or not self._info_hash:
            return
        
        try:
            # Use DataProvider to get tracker information
            trackers = await self._data_provider.get_torrent_trackers(self._info_hash)
            self._trackers_table.clear()
            
            if not trackers:
                self._trackers_table.add_row(
                    _("N/A"), _("N/A"), _("N/A"), _("N/A"), _("N/A"), _("N/A"), _("No trackers found")
                )
                return
            
            for tracker in trackers:
                url = tracker.get("url", "N/A")
                status = tracker.get("status", "unknown")
                seeds = tracker.get("seeds", 0)
                peers = tracker.get("peers", 0)
                downloaders = tracker.get("downloaders", 0)
                last_update = tracker.get("last_update", 0.0)
                error = tracker.get("error")
                
                # Format last update time
                if last_update and last_update > 0:
                    from datetime import datetime
                    try:
                        last_update_str = datetime.fromtimestamp(last_update).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        last_update_str = _("N/A")
                else:
                    last_update_str = _("Never")
                
                error_str = error if error else ""
                
                self._trackers_table.add_row(
                    url,
                    status,
                    str(seeds),
                    str(peers),
                    str(downloaders),
                    last_update_str,
                    error_str,
                    key=url,
                )
        except Exception as e:
            logger.debug("Error refreshing torrent trackers: %s", e)
            self._trackers_table.clear()
            self._trackers_table.add_row(
                _("Error"), _("Error"), _("Error"), _("Error"), _("Error"), _("Error"), _("Error: {error}").format(error=str(e))
            )

    async def action_force_announce(self) -> None:  # pragma: no cover
        """Force announce to selected tracker."""
        if not self._command_executor or not self._info_hash:
            return
        
        try:
            result = await self._command_executor.execute_command(
                "torrent.force_announce",
                info_hash=self._info_hash,
            )
            
            if result and hasattr(result, "success") and result.success:
                if hasattr(self, "app"):
                    self.app.notify(_("Announce sent"), severity="success")  # type: ignore[attr-defined]
                # Refresh trackers to show updated status
                await self.refresh_trackers()
            else:
                error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                if hasattr(self, "app"):
                    self.app.notify(_("Failed to announce: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error forcing announce: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error forcing announce: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_add_tracker(self) -> None:  # pragma: no cover
        """Add a tracker URL to the torrent."""
        if not self._command_executor or not self._info_hash:
            return
        
        try:
            # Show input dialog for tracker URL
            if hasattr(self, "app"):
                dialog = TrackerInputDialog()
                tracker_url = await self.app.push_screen(dialog)  # type: ignore[attr-defined]
                
                if tracker_url:
                    # Validate URL format (basic check)
                    if not tracker_url.startswith(("http://", "https://", "udp://")):
                        if hasattr(self, "app"):
                            self.app.notify(_("Invalid tracker URL format. Must start with http://, https://, or udp://"), severity="error")  # type: ignore[attr-defined]
                        return
                    
                    # Add tracker via executor
                    result = await self._command_executor.execute_command(
                        "torrent.add_tracker",
                        info_hash=self._info_hash,
                        tracker_url=tracker_url,
                    )
                    
                    if result and hasattr(result, "success") and result.success:
                        if hasattr(self, "app"):
                            self.app.notify(_("Tracker added: {url}").format(url=tracker_url), severity="success")  # type: ignore[attr-defined]
                        # Refresh trackers list
                        await self.refresh_trackers()
                    else:
                        error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                        if hasattr(self, "app"):
                            self.app.notify(_("Failed to add tracker: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error adding tracker: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error adding tracker: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_remove_tracker(self) -> None:  # pragma: no cover
        """Remove selected tracker from the torrent."""
        if not self._trackers_table or not self._command_executor or not self._info_hash:
            return
        
        try:
            # Get selected tracker URL
            selected_key = self._trackers_table.get_selected_key()
            if not selected_key:
                if hasattr(self, "app"):
                    self.app.notify(_("No tracker selected"), severity="warning")  # type: ignore[attr-defined]
                return
            
            # Try to use executor command if available
            # Note: This may not exist yet - will need to be implemented
            try:
                result = await self._command_executor.execute_command(
                    "torrent.remove_tracker",
                    info_hash=self._info_hash,
                    tracker_url=selected_key,
                )
                
                if result and hasattr(result, "success") and result.success:
                    if hasattr(self, "app"):
                        self.app.notify(_("Tracker removed: {url}").format(url=selected_key), severity="success")  # type: ignore[attr-defined]
                    # Refresh trackers list
                    await self.refresh_trackers()
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    if hasattr(self, "app"):
                        self.app.notify(_("Failed to remove tracker: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
            except Exception as e:
                # Executor command may not exist - log and show message
                logger.warning("Remove tracker command not available: %s", e)
                if hasattr(self, "app"):
                    self.app.notify(  # type: ignore[attr-defined]
                        _("Remove tracker not yet implemented. Selected tracker: {url}").format(url=selected_key),
                        severity="info",
                    )
        except Exception as e:
            logger.debug("Error removing tracker: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error removing tracker: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]


class TrackerInputDialog(ModalScreen):  # type: ignore[misc]
    """Dialog for entering tracker URL."""

    DEFAULT_CSS = """
    TrackerInputDialog {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    #tracker-input {
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

    def compose(self) -> Any:  # pragma: no cover
        """Compose the tracker input dialog."""
        with Vertical(id="dialog"):
            yield Static(_("Enter Tracker URL"), id="title")
            yield Input(
                placeholder=_("http://tracker.example.com:8080/announce"),
                id="tracker-input",
            )
            with Horizontal(id="buttons"):
                yield Button(_("Confirm"), id="confirm", variant="primary")
                yield Button(_("Cancel"), id="cancel", variant="default")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the dialog and focus input."""
        try:
            input_widget = self.query_one("#tracker-input", Input)  # type: ignore[attr-defined]
            input_widget.focus()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting tracker input dialog: %s", e)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "confirm":
            try:
                input_widget = self.query_one("#tracker-input", Input)  # type: ignore[attr-defined]
                tracker_url = input_widget.value.strip()  # type: ignore[attr-defined]
                if tracker_url:
                    self.dismiss(tracker_url)  # type: ignore[attr-defined]
                else:
                    self.dismiss(None)  # type: ignore[attr-defined]
            except Exception:
                self.dismiss(None)  # type: ignore[attr-defined]
        elif event.button.id == "cancel":
            self.dismiss(None)  # type: ignore[attr-defined]

    async def action_confirm(self) -> None:  # pragma: no cover
        """Confirm tracker URL input."""
        try:
            input_widget = self.query_one("#tracker-input", Input)  # type: ignore[attr-defined]
            tracker_url = input_widget.value.strip()  # type: ignore[attr-defined]
            if tracker_url:
                self.dismiss(tracker_url)  # type: ignore[attr-defined]
            else:
                self.dismiss(None)  # type: ignore[attr-defined]
        except Exception:
            self.dismiss(None)  # type: ignore[attr-defined]

    async def action_cancel(self) -> None:  # pragma: no cover
        """Cancel tracker URL input."""
        self.dismiss(None)  # type: ignore[attr-defined]

