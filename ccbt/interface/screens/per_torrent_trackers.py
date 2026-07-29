"""Trackers sub-tab screen for Per-Torrent tab.

Displays tracker information for a selected torrent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Optional

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
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import Button, DataTable, Input, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        def data_bind(self, **kwargs: Any) -> None:  # type: ignore[no-redef]
            """No-op data_bind when textual is unavailable."""
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

    class reactive:  # type: ignore[no-redef]
        """Stub reactive descriptor for textual compatibility."""

        def __init__(self, default: Any = None, *args: Any, **kwargs: Any) -> None:
            self.default = default

        def __class_getitem__(cls, item: Any) -> type:
            return cls

        def __set_name__(self, owner: Any, name: str) -> None:
            self._name = name

        def __get__(self, instance: Any, owner: Any) -> Any:
            if instance is None:
                return self
            return instance.__dict__.get(self._name, self.default)

        def __set__(self, instance: Any, value: Any) -> None:
            instance.__dict__[self._name] = value

    class Button:  # type: ignore[no-redef]
        pass

    class ModalScreen:  # type: ignore[no-redef]
        pass


from ccbt.i18n import _
from ccbt.interface.widgets.reusable_table import ReusableDataTable

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

    # F2.4.5: reactive bound to TerminalDashboard.selected_torrent_trackers.
    selected_torrent_trackers: reactive = reactive([], layout=False)  # type: ignore[assignment]

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
        self._trackers_table: Optional[DataTable] = None

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
                    _("Error"),
                )
                self._trackers_table.zebra_stripes = True

            # F2.4.5: bind to the App selected_torrent_trackers reactive
            # (replaces the set_interval(5.0, self.refresh_trackers) self-poll).
            try:
                from ccbt.interface.terminal_dashboard import TerminalDashboard

                self.data_bind(
                    selected_torrent_trackers=TerminalDashboard.selected_torrent_trackers
                )
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive for non-mounted contexts
                logger.debug("TorrentTrackersScreen data_bind skipped: %s", exc)
            # Initial refresh (fallback for contexts where the reactive has not
            # been populated yet; the reactive drives subsequent updates).
            self.call_later(self.refresh_trackers)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting trackers screen: %s", e)

    def watch_selected_torrent_trackers(
        self, value: list[dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Reactive watcher: render the trackers table from the bound list (F2.4.5)."""
        if isinstance(value, list):
            import asyncio as _asyncio

            _asyncio.create_task(self.refresh_trackers(trackers_override=value))

    async def refresh_trackers(
        self, trackers_override: Optional[list[dict[str, Any]]] = None
    ) -> None:  # pragma: no cover
        """Refresh trackers table with latest data.

        Args:
            trackers_override: When provided (from the selected_torrent_trackers
                reactive watcher), skip the ``get_torrent_trackers()`` fetch and
                render from this list directly.
        """
        if not self._trackers_table or not self._data_provider or not self._info_hash:
            return

        try:
            # Use DataProvider to get tracker information
            trackers = (
                trackers_override
                if trackers_override is not None
                else await self._data_provider.get_torrent_trackers(self._info_hash)
            )
            self._trackers_table.clear()

            if not trackers:
                self._trackers_table.add_row(
                    _("N/A"),
                    _("N/A"),
                    _("N/A"),
                    _("N/A"),
                    _("N/A"),
                    _("N/A"),
                    _("No trackers found"),
                )
                return

            for idx, tracker in enumerate(trackers):
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
                        last_update_str = datetime.fromtimestamp(last_update).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
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
                    key=f"{url}|{idx}",
                )
        except Exception as e:
            logger.debug("Error refreshing torrent trackers: %s", e)
            self._trackers_table.clear()
            self._trackers_table.add_row(
                _("Error"),
                _("Error"),
                _("Error"),
                _("Error"),
                _("Error"),
                _("Error"),
                _("Error: {error}").format(error=str(e)),
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
                error_msg = (
                    result.error
                    if result and hasattr(result, "error")
                    else _("Unknown error")
                )
                if hasattr(self, "app"):
                    self.app.notify(
                        _("Failed to announce: {error}").format(error=error_msg),
                        severity="error",
                    )  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error forcing announce: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Error forcing announce: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]

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
                            self.app.notify(
                                _(
                                    "Invalid tracker URL format. Must start with http://, https://, or udp://"
                                ),
                                severity="error",
                            )  # type: ignore[attr-defined]
                        return

                    # Add tracker via executor
                    result = await self._command_executor.execute_command(
                        "torrent.add_tracker",
                        info_hash=self._info_hash,
                        tracker_url=tracker_url,
                    )

                    if result and hasattr(result, "success") and result.success:
                        if hasattr(self, "app"):
                            self.app.notify(
                                _("Tracker added: {url}").format(url=tracker_url),
                                severity="success",
                            )  # type: ignore[attr-defined]
                        # Refresh trackers list
                        await self.refresh_trackers()
                    else:
                        error_msg = (
                            result.error
                            if result and hasattr(result, "error")
                            else _("Unknown error")
                        )
                        if hasattr(self, "app"):
                            self.app.notify(
                                _("Failed to add tracker: {error}").format(
                                    error=error_msg
                                ),
                                severity="error",
                            )  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error adding tracker: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Error adding tracker: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]

    async def action_remove_tracker(self) -> None:  # pragma: no cover
        """Remove selected tracker from the torrent."""
        if (
            not self._trackers_table
            or not self._command_executor
            or not self._info_hash
        ):
            return

        try:
            # Get selected tracker URL
            selected_key = self._trackers_table.get_selected_key()
            if not selected_key:
                if hasattr(self, "app"):
                    self.app.notify(_("No tracker selected"), severity="warning")  # type: ignore[attr-defined]
                return
            tracker_url = selected_key.split("|", 1)[0]
            if not tracker_url:
                if hasattr(self, "app"):
                    self.app.notify(_("Invalid tracker selection"), severity="error")  # type: ignore[attr-defined]
                return

            # Try to use executor command if available
            # Note: This may not exist yet - will need to be implemented
            try:
                result = await self._command_executor.execute_command(
                    "torrent.remove_tracker",
                    info_hash=self._info_hash,
                    tracker_url=tracker_url,
                )

                if result and hasattr(result, "success") and result.success:
                    if hasattr(self, "app"):
                        self.app.notify(
                            _("Tracker removed: {url}").format(url=tracker_url),
                            severity="success",
                        )  # type: ignore[attr-defined]
                    # Refresh trackers list
                    await self.refresh_trackers()
                else:
                    error_msg = (
                        result.error
                        if result and hasattr(result, "error")
                        else _("Unknown error")
                    )
                    if hasattr(self, "app"):
                        self.app.notify(
                            _("Failed to remove tracker: {error}").format(
                                error=error_msg
                            ),
                            severity="error",
                        )  # type: ignore[attr-defined]
            except Exception as e:
                # Executor command may not exist - log and show message
                logger.warning("Remove tracker command not available: %s", e)
                if hasattr(self, "app"):
                    self.app.notify(  # type: ignore[attr-defined]
                        _(
                            "Remove tracker not yet implemented. Selected tracker: {url}"
                        ).format(url=selected_key),
                        severity="info",
                    )
        except Exception as e:
            logger.debug("Error removing tracker: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Error removing tracker: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]


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

    async def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:  # pragma: no cover
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
