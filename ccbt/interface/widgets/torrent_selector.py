"""Torrent selector widget for Per-Torrent tab.

Provides a dropdown/select widget for choosing which torrent to view details for.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Optional

from ccbt.interface.content_load import schedule_widget_worker

if TYPE_CHECKING:
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widgets import Input, Select, Static
    from textual.widgets.select import InvalidSelectValueError
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        def data_bind(self, **kwargs: Any) -> None:  # type: ignore[no-redef]
            """No-op data_bind when textual is unavailable."""

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        NULL = object()

    class InvalidSelectValueError(Exception):  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
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


logger = logging.getLogger(__name__)


class TorrentSelector(Container):  # type: ignore[misc]
    """Widget for selecting a torrent to view details."""

    DEFAULT_CSS = """
    TorrentSelector {
        height: auto;
        min-height: 3;
        layout: horizontal;
        display: block;
        margin: 1;
    }
    
    #torrent-select-label {
        width: 20;
        margin-right: 1;
    }
    
    #torrent-select {
        width: 1fr;
        min-width: 30;
    }
    """

    # F2.3.3: reactive bound to TerminalDashboard.torrents_data via data_bind.
    torrents_data: reactive = reactive([])  # type: ignore[assignment]

    def __init__(
        self,
        data_provider: DataProvider,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent selector.

        Args:
            data_provider: DataProvider instance for fetching torrent list
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._selected_info_hash: Optional[str] = None
        self._torrent_options: list[tuple[str, str]] = []  # (display_name, info_hash)
        self._select_widget: Optional[Select] = None
        self._pending_torrents_override: Optional[list[dict[str, Any]]] = None

    @staticmethod
    def _info_hash_from_torrent(torrent: dict[str, Any]) -> str:
        ih = torrent.get("info_hash") or torrent.get("info_hash_hex") or ""
        if isinstance(ih, bytes):
            return ih.hex()
        return str(ih or "")

    def _set_select_value(self, info_hash: str) -> None:
        """Set the Select to an option value (Textual 8 uses values, not indices)."""
        if not self._select_widget or not info_hash:
            return
        try:
            self._select_widget.value = info_hash  # type: ignore[attr-defined]
            if hasattr(self._select_widget, "refresh"):
                self._select_widget.refresh()  # type: ignore[attr-defined]
        except (InvalidSelectValueError, TypeError, ValueError) as exc:
            logger.debug(
                "TorrentSelector: could not set select value %s: %s",
                info_hash[:8],
                exc,
            )

    def _clear_select_value(self) -> None:
        """Clear the Select when no torrent should be selected."""
        if not self._select_widget:
            return
        with contextlib.suppress(Exception):
            if hasattr(self._select_widget, "clear"):
                self._select_widget.clear()  # type: ignore[attr-defined]
            elif hasattr(Select, "NULL"):
                self._select_widget.value = Select.NULL  # type: ignore[attr-defined]

    def compose(self) -> Any:  # pragma: no cover
        """Compose the torrent selector."""
        with Horizontal():
            yield Static("Torrent:", id="torrent-select-label")
            # Note: Removed search input - no longer necessary
            yield Select(
                [("Loading...", "")], id="torrent-select", prompt="Select torrent"
            )

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrent selector."""
        try:
            # Note: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            self._select_widget = self.query_one("#torrent-select", Select)  # type: ignore[attr-defined]
            # Note: Ensure child widget is visible
            if self._select_widget:
                self._select_widget.display = True  # type: ignore[attr-defined]
            # F2.3.3: bind via App message pump (child on_mount data_bind fails on Textual 8).
            from ccbt.interface.reactive_bridge import request_lazy_bind

            request_lazy_bind(self)
            # Load torrent list once on mount (the reactive drives subsequent
            # updates via watch_torrents_data).
            try:
                schedule_widget_worker(
                    self,
                    self._refresh_torrent_list(),
                    group="TorrentSelector_mount",
                )
            except Exception:
                self.call_later(self._deferred_refresh_torrent_list)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting torrent selector: %s", e, exc_info=True)

    def watch_torrents_data(
        self, value: list[dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Reactive watcher: repopulate the Select from the bound list (F2.3.3)."""
        self._pending_torrents_override = list(value or [])
        if not self._select_widget:
            self.call_later(self._deferred_refresh_torrent_list)  # type: ignore[attr-defined]
            return
        schedule_widget_worker(
            self,
            self._refresh_torrent_list(torrents_override=self._pending_torrents_override),
            group="TorrentSelector_torrents",
            exclusive=False,
        )
        self._pending_torrents_override = None

    def _deferred_refresh_torrent_list(self) -> None:  # pragma: no cover
        """Retry refresh after mount when the Select child was not ready yet."""
        if not self._select_widget:
            with contextlib.suppress(Exception):
                self._select_widget = self.query_one("#torrent-select", Select)  # type: ignore[attr-defined]
        override = self._pending_torrents_override
        self._pending_torrents_override = None
        schedule_widget_worker(
            self,
            self._refresh_torrent_list(torrents_override=override),
            group="TorrentSelector_deferred",
        )

    async def _refresh_torrent_list(
        self, torrents_override: Optional[list[dict[str, Any]]] = None
    ) -> None:  # pragma: no cover
        """Refresh the list of available torrents.

        Args:
            torrents_override: When provided (from the torrents_data reactive
                watcher), skip the ``list_torrents()`` fetch and use this list.
        """
        if not self._data_provider:
            return
        if not self._select_widget:
            self._pending_torrents_override = torrents_override
            self.call_later(self._deferred_refresh_torrent_list)  # type: ignore[attr-defined]
            return

        try:
            if torrents_override is not None:
                torrents = list(torrents_override)
            else:
                app = getattr(self, "app", None)
                bound = (
                    list(getattr(app, "torrents_data", []) or [])
                    if app is not None
                    else []
                )
                if bound:
                    torrents = bound
                else:
                    torrents = await self._data_provider.list_torrents()
            logger.debug(
                "TorrentSelector: Retrieved %d torrents from data provider",
                len(torrents) if torrents else 0,
            )

            # Build options list
            options: list[tuple[str, str]] = []
            for torrent in torrents:
                name = torrent.get("name", "Unknown")
                info_hash = self._info_hash_from_torrent(torrent)
                if not info_hash:
                    continue
                status = torrent.get("status", "unknown")
                # Format: "Name (Status)"
                display_name = f"{name} ({status})"
                options.append((display_name, info_hash))

            self._torrent_options = options
            logger.debug("TorrentSelector: Built %d options for dropdown", len(options))

            current_value = self._selected_info_hash
            # Update Select widget
            if options:
                try:
                    self._select_widget.set_options(options)  # type: ignore[attr-defined]
                    logger.debug(
                        "TorrentSelector: Set %d options in Select widget", len(options)
                    )
                    if hasattr(self._select_widget, "refresh"):
                        self._select_widget.refresh()  # type: ignore[attr-defined]
                    # Textual 8 Select values are option payloads (info_hash), not indices.
                    if current_value and any(ih == current_value for _, ih in options):
                        self._set_select_value(current_value)
                    else:
                        self._clear_select_value()
                except Exception as e:
                    logger.error("Error setting Select options: %s", e, exc_info=True)
            else:
                try:
                    self._select_widget.set_options([("No torrents", "")])  # type: ignore[attr-defined]
                    self._clear_select_value()
                except Exception as e:
                    logger.debug("Error setting empty Select options: %s", e)
                logger.debug(
                    "TorrentSelector: No torrents available, showing placeholder"
                )
        except Exception as e:
            logger.error("Error refreshing torrent list: %s", e, exc_info=True)

    def on_select_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle torrent selection change.

        Args:
            event: Select.Changed event
        """
        if not hasattr(event, "value"):
            logger.debug("TorrentSelector: Select.Changed event has no value attribute")
            return

        event_value = event.value
        if event_value is getattr(Select, "NULL", None):
            return
        if type(event_value).__name__ == "NoSelection":
            return

        logger.debug(
            "TorrentSelector: Select.Changed event.value = %r (type: %s)",
            event_value,
            type(event_value).__name__,
        )

        info_hash: Optional[str] = None

        # Handle different value formats from Textual Select
        if isinstance(event_value, tuple) and len(event_value) == 2:
            # Tuple format: (display_name, info_hash)
            _, info_hash = event_value
            logger.debug(
                "TorrentSelector: Extracted info_hash from tuple: %s",
                info_hash[:8] if info_hash else "None",
            )
        elif isinstance(event_value, int):
            # Integer index: Look up in _torrent_options
            if 0 <= event_value < len(self._torrent_options):
                _, info_hash = self._torrent_options[event_value]
                logger.debug(
                    "TorrentSelector: Extracted info_hash from index %d: %s",
                    event_value,
                    info_hash[:8] if info_hash else "None",
                )
            else:
                logger.warning(
                    "TorrentSelector: Index %d out of range (options: %d)",
                    event_value,
                    len(self._torrent_options),
                )
        elif isinstance(event_value, str):
            # Textual 8: event.value is the option payload (info_hash).
            if not event_value:
                logger.debug(
                    "TorrentSelector: Empty string value (placeholder), ignoring"
                )
                return
            if any(ih == event_value for _, ih in self._torrent_options):
                info_hash = event_value
                logger.debug(
                    "TorrentSelector: Matched option value as info_hash: %s",
                    info_hash[:8],
                )
            else:
                # Legacy: display_name or partial match
                for display_name, ih in self._torrent_options:
                    if display_name == event_value or ih == event_value:
                        info_hash = ih
                        logger.debug(
                            "TorrentSelector: Matched string value, info_hash: %s",
                            info_hash[:8] if info_hash else "None",
                        )
                        break

        # Only emit event if we have a valid info_hash
        if info_hash:
            self._selected_info_hash = info_hash
            logger.debug(
                "TorrentSelector: Emitting TorrentSelected event for info_hash: %s",
                info_hash[:8],
            )
            # F2.3.3: drive the App selected_torrent_info_hash reactive so the
            # per-torrent screens self-render (kept the TorrentSelected message
            # for any external consumer).
            try:
                app = getattr(self, "app", None)
                if app is not None and hasattr(app, "selected_torrent_info_hash"):
                    app.selected_torrent_info_hash = info_hash
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive for non-mounted contexts
                logger.debug(
                    "TorrentSelector: could not set app.selected_torrent_info_hash: %s",
                    exc,
                )
            # Emit custom event for parent to handle
            self.post_message(self.TorrentSelected(info_hash))  # type: ignore[attr-defined]
        else:
            logger.warning(
                "TorrentSelector: Could not extract info_hash from event.value = %r",
                event_value,
            )

    def get_selected_info_hash(self) -> Optional[str]:
        """Get the currently selected torrent info hash.

        Returns:
            Info hash in hex format or None
        """
        return self._selected_info_hash

    def set_value(self, info_hash: str) -> None:  # pragma: no cover
        """Set the selected torrent by info hash.

        Args:
            info_hash: Info hash to select
        """
        if not self._select_widget:
            return
        self._selected_info_hash = info_hash
        for _, ih in self._torrent_options:
            if ih == info_hash:
                self._set_select_value(info_hash)
                break

    class TorrentSelected(Message):  # type: ignore[misc]
        """Event emitted when a torrent is selected."""

        def __init__(self, info_hash: str) -> None:
            """Initialize torrent selected event.

            Args:
                info_hash: Selected torrent info hash
            """
            super().__init__()
            self.info_hash = info_hash
