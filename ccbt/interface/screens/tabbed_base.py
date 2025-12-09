"""Base screen classes for tabbed interface.

DEPRECATED: This module is no longer used. The new tabbed interface implementation
uses Container widgets instead of Screen classes. See:
- ccbt.interface.screens.torrents_tab.TorrentsTabContent (Container)
- ccbt.interface.screens.per_torrent_tab.PerTorrentTabContent (Container)
- ccbt.interface.screens.preferences_tab.PreferencesTabContent (Container)

This file is kept for backward compatibility but should not be used in new code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        AsyncSessionManager = None  # type: ignore[assignment, misc]

try:
    from textual.screen import Screen
    from textual.widgets import Static
except ImportError:
    # Fallback for when textual is not available
    class Screen:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

from ccbt.interface.screens.base import MonitoringScreen

logger = logging.getLogger(__name__)


class TorrentsTabScreen(MonitoringScreen):  # type: ignore[misc]
    """Base class for Torrents tab screens.

    This is the main tab for displaying torrent lists with nested sub-tabs
    for different torrent states (Global, Downloading, Seeding, etc.).
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize Torrents tab screen.

        Args:
            session: AsyncSessionManager instance
        """
        super().__init__(session, *args, **kwargs)


class PerTorrentTabScreen(MonitoringScreen):  # type: ignore[misc]
    """Base class for Per-Torrent tab screens.

    This tab displays detailed information about a selected torrent with
    nested sub-tabs (Files, Info, Peers, Trackers, Graphs, Config).
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        selected_info_hash: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize Per-Torrent tab screen.

        Args:
            session: AsyncSessionManager instance
            selected_info_hash: Currently selected torrent info hash (hex)
        """
        super().__init__(session, *args, **kwargs)
        self.selected_info_hash = selected_info_hash


class PreferencesTabScreen(MonitoringScreen):  # type: ignore[misc]
    """Base class for Preferences tab screens.

    This tab displays configuration options with nested sub-tabs for
    different configuration categories.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("s", "save", "Save"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize Preferences tab screen.

        Args:
            session: AsyncSessionManager instance
        """
        super().__init__(session, *args, **kwargs)
        self._has_unsaved_changes = False

    async def action_save(self) -> None:  # pragma: no cover
        """Save configuration changes."""
        # Override in subclasses
        logger.debug("Save action called (not implemented)")


