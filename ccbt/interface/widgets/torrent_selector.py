"""Torrent selector widget for Per-Torrent tab.

Provides a dropdown/select widget for choosing which torrent to view details for.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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
    from textual.widgets import Input, Select, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

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
        self._selected_info_hash: str | None = None
        self._torrent_options: list[tuple[str, str]] = []  # (display_name, info_hash)
        self._select_widget: Select | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the torrent selector."""
        with Horizontal():
            yield Static("Torrent:", id="torrent-select-label")
            # CRITICAL FIX: Removed search input - no longer necessary
            yield Select([("Loading...", "")], id="torrent-select", prompt="Select torrent")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrent selector."""
        try:
            # CRITICAL FIX: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            self._select_widget = self.query_one("#torrent-select", Select)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure child widget is visible
            if self._select_widget:
                self._select_widget.display = True  # type: ignore[attr-defined]
            # Load torrent list
            self.call_later(self._refresh_torrent_list)  # type: ignore[attr-defined]
            # Schedule periodic refresh
            self.set_interval(2.0, self._refresh_torrent_list)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting torrent selector: %s", e, exc_info=True)

    async def _refresh_torrent_list(self) -> None:  # pragma: no cover
        """Refresh the list of available torrents."""
        if not self._data_provider or not self._select_widget:
            return
        
        try:
            torrents = await self._data_provider.list_torrents()
            logger.debug("TorrentSelector: Retrieved %d torrents from data provider", len(torrents) if torrents else 0)
            
            # Build options list
            options: list[tuple[str, str]] = []
            for torrent in torrents:
                name = torrent.get("name", "Unknown")
                info_hash = torrent.get("info_hash", "")
                status = torrent.get("status", "unknown")
                # Format: "Name (Status)"
                display_name = f"{name} ({status})"
                options.append((display_name, info_hash))
            
            self._torrent_options = options
            logger.debug("TorrentSelector: Built %d options for dropdown", len(options))
            
            # Update Select widget
            if options:
                # Get current selection
                current_value = self._selected_info_hash
                # CRITICAL FIX: Clear and repopulate - use set_options with proper format
                try:
                    self._select_widget.set_options(options)  # type: ignore[attr-defined]
                    logger.debug("TorrentSelector: Set %d options in Select widget", len(options))
                    # CRITICAL FIX: Force refresh of Select widget to ensure it displays
                    if hasattr(self._select_widget, "refresh"):
                        self._select_widget.refresh()  # type: ignore[attr-defined]
                    # Restore selection if still valid
                    if current_value and any(ih == current_value for _, ih in options):
                        # Find index of current selection
                        for idx, (_, ih) in enumerate(options):
                            if ih == current_value:
                                # CRITICAL FIX: Textual Select expects index or tuple value
                                try:
                                    self._select_widget.value = idx  # type: ignore[attr-defined]
                                except (TypeError, ValueError):
                                    # Fallback: try setting tuple value
                                    self._select_widget.value = options[idx]  # type: ignore[attr-defined]
                                break
                except Exception as e:
                    logger.error("Error setting Select options: %s", e, exc_info=True)
            else:
                self._select_widget.set_options([("No torrents", "")])  # type: ignore[attr-defined]
                logger.debug("TorrentSelector: No torrents available, showing placeholder")
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
        logger.debug("TorrentSelector: Select.Changed event.value = %r (type: %s)", event_value, type(event_value).__name__)
        
        info_hash: str | None = None
        
        # Handle different value formats from Textual Select
        if isinstance(event_value, tuple) and len(event_value) == 2:
            # Tuple format: (display_name, info_hash)
            _, info_hash = event_value
            logger.debug("TorrentSelector: Extracted info_hash from tuple: %s", info_hash[:8] if info_hash else "None")
        elif isinstance(event_value, int):
            # Integer index: Look up in _torrent_options
            if 0 <= event_value < len(self._torrent_options):
                _, info_hash = self._torrent_options[event_value]
                logger.debug("TorrentSelector: Extracted info_hash from index %d: %s", event_value, info_hash[:8] if info_hash else "None")
            else:
                logger.warning("TorrentSelector: Index %d out of range (options: %d)", event_value, len(self._torrent_options))
        elif isinstance(event_value, str):
            # String: Could be info_hash directly, or empty string from "Loading..." option
            if event_value:
                # Try to match as info_hash
                for _, ih in self._torrent_options:
                    if ih == event_value:
                        info_hash = event_value
                        logger.debug("TorrentSelector: Matched string value as info_hash: %s", info_hash[:8])
                        break
                if not info_hash:
                    # Try to match as display_name
                    for display_name, ih in self._torrent_options:
                        if display_name == event_value:
                            info_hash = ih
                            logger.debug("TorrentSelector: Matched string value as display_name, info_hash: %s", info_hash[:8] if info_hash else "None")
                            break
            else:
                # Empty string - likely from "Loading..." option, ignore
                logger.debug("TorrentSelector: Empty string value (likely 'Loading...' option), ignoring")
                return
        
        # Only emit event if we have a valid info_hash
        if info_hash:
            self._selected_info_hash = info_hash
            logger.debug("TorrentSelector: Emitting TorrentSelected event for info_hash: %s", info_hash[:8])
            # Emit custom event for parent to handle
            self.post_message(self.TorrentSelected(info_hash))  # type: ignore[attr-defined]
        else:
            logger.warning("TorrentSelector: Could not extract info_hash from event.value = %r", event_value)


    def get_selected_info_hash(self) -> str | None:
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
        # Find and set the option matching this info hash
        for idx, (display_name, ih) in enumerate(self._torrent_options):
            if ih == info_hash:
                try:
                    # CRITICAL FIX: Textual Select expects index, not tuple
                    self._select_widget.value = idx  # type: ignore[attr-defined]
                    # Force refresh
                    if hasattr(self._select_widget, "refresh"):
                        self._select_widget.refresh()  # type: ignore[attr-defined]
                except (TypeError, ValueError):
                    # Fallback: try tuple value
                    try:
                        self._select_widget.value = (display_name, info_hash)  # type: ignore[attr-defined]
                    except Exception:
                        pass
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



















