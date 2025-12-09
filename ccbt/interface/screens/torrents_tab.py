"""Torrents tab screen implementation.

Implements the main Torrents tab with nested sub-tabs for different torrent states.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from ccbt.i18n import _
from ccbt.interface.widgets.core_widgets import GlobalTorrentMetricsPanel

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]
        DataProvider = None  # type: ignore[assignment, misc]
        AsyncSessionManager = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import DataTable, Input, Static, Tabs, Tab
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

    class Input:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Tabs:  # type: ignore[no-redef]
        pass

    class Tab:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class GlobalTorrentsScreen(Container):  # type: ignore[misc]
    """Screen for displaying all torrents (Global sub-tab)."""

    DEFAULT_CSS = """
    GlobalTorrentsScreen {
        height: 1fr;
        layout: vertical;
        overflow: hidden;
    }
    
    #torrents-search {
        height: 3;
        min-height: 3;
    }
    
    #torrents-table {
        height: 1fr;
        min-height: 10;
    }
    
    #global-metrics-panel {
        height: auto;
        min-height: 4;
        margin-bottom: 1;
    }
    
    #torrents-table-container {
        height: 1fr;
        layout: vertical;
    }
    
    #torrents-empty-message {
        height: auto;
        min-height: 3;
        padding: 1;
        border: dashed $primary;
        display: none;
        text-align: center;
    }
    """

    BINDINGS = [
        ("p", "pause_torrent", _("Pause")),
        ("r", "resume_torrent", _("Resume")),
        ("d", "remove_torrent", _("Remove")),
        ("e", "refresh_pex", _("Refresh PEX")),
    ]

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        selected_hash_callback: Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize global torrents screen.

        Args:
            data_provider: DataProvider instance for fetching data
            command_executor: CommandExecutor instance for executing commands
            selected_hash_callback: Optional callback when torrent is selected (info_hash: str) -> None
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._selected_hash_callback = selected_hash_callback
        self._torrents_table: DataTable | None = None
        self._search_input: Input | None = None
        self._metrics_panel: GlobalTorrentMetricsPanel | None = None
        self._empty_message: Static | None = None
        self._filter_text = ""

    def compose(self) -> Any:  # pragma: no cover
        """Compose the global torrents screen."""
        # Search/filter input
        with Horizontal(id="torrents-search"):
            yield Input(placeholder=_("Search torrents..."), id="search-input")
        
        yield GlobalTorrentMetricsPanel(id="global-metrics-panel")
        
        with Container(id="torrents-table-container"):
            yield DataTable(id="torrents-table")
            yield Static(
                _("No torrents yet. Use 'add' to start downloading."),
                id="torrents-empty-message",
            )

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the global torrents screen."""
        try:
            self._torrents_table = self.query_one("#torrents-table", DataTable)  # type: ignore[attr-defined]
            self._search_input = self.query_one("#search-input", Input)  # type: ignore[attr-defined]
            self._metrics_panel = self.query_one("#global-metrics-panel", GlobalTorrentMetricsPanel)  # type: ignore[attr-defined]
            self._empty_message = self.query_one("#torrents-empty-message", Static)  # type: ignore[attr-defined]
            if self._empty_message:
                self._empty_message.display = False  # type: ignore[attr-defined]
            
            # Set up table columns
            if self._torrents_table:
                self._torrents_table.add_columns(
                    "#",
                    _("Name"),
                    _("Size"),
                    _("Progress"),
                    _("Status"),
                    _("↓ Speed"),
                    _("↑ Speed"),
                    _("Peers"),
                    _("Seeds"),
                )
                self._torrents_table.zebra_stripes = True
            
            # CRITICAL FIX: Schedule initial refresh with proper async handling
            # set_interval doesn't work with async functions directly, use wrapper
            def schedule_refresh() -> None:
                import asyncio
                asyncio.create_task(self.refresh_torrents())
            
            self.set_interval(1.0, schedule_refresh)  # type: ignore[attr-defined]
            # Also refresh immediately
            schedule_refresh()
            
            # CRITICAL FIX: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            if self._torrents_table:
                self._torrents_table.display = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting global torrents screen: %s", e, exc_info=True)

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

            # Update search input placeholder
            if self._search_input:
                try:
                    self._search_input.placeholder = _("Search torrents...")  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Update table column headers
            if self._torrents_table:
                try:
                    # Clear and re-add columns with new translations
                    self._torrents_table.clear_columns()  # type: ignore[attr-defined]
                    self._torrents_table.add_columns(
                        "#",
                        _("Name"),
                        _("Size"),
                        _("Progress"),
                        _("Status"),
                        _("↓ Speed"),
                        _("↑ Speed"),
                        _("Peers"),
                        _("Seeds"),
                    )
                    # Trigger refresh to repopulate with new headers
                    self.call_later(self.refresh_torrents)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("Error updating table columns: %s", e)

        except Exception as e:
            logger.debug("Error refreshing torrents tab translations: %s", e)

    async def refresh_torrents(self) -> None:  # pragma: no cover
        """Refresh torrents table with latest data."""
        # CRITICAL FIX: Check if widget is visible and attached before refreshing
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("GlobalTorrentsScreen: Widget not attached or not visible, skipping refresh")
            return
        
        # CRITICAL FIX: Re-query _torrents_table if it's None (may happen if called before on_mount completes)
        if not self._torrents_table:
            try:
                self._torrents_table = self.query_one("#torrents-table", DataTable)  # type: ignore[attr-defined]
                if not self._torrents_table:
                    logger.warning("GlobalTorrentsScreen: Could not find torrents table, deferring refresh")
                    return
                # Set up columns if table was just found
                if not self._torrents_table.columns:  # type: ignore[attr-defined]
                    self._torrents_table.add_columns(
                        "#",
                        _("Name"),
                        _("Size"),
                        _("Progress"),
                        _("Status"),
                        _("↓ Speed"),
                        _("↑ Speed"),
                        _("Peers"),
                        _("Seeds"),
                    )
            except Exception as e:
                logger.debug("GlobalTorrentsScreen: Error re-querying table: %s", e)
                return
        
        # CRITICAL FIX: Re-query _data_provider if it's None (should be set in __init__, but check anyway)
        if not self._data_provider:
            logger.warning("GlobalTorrentsScreen: Missing data provider, cannot refresh")
            return
        
        stats: dict[str, Any] | None = None
        swarm_samples: list[dict[str, Any]] | None = None

        try:
            logger.debug("GlobalTorrentsScreen: Fetching torrents from data provider...")
            # CRITICAL FIX: Use wait_for directly (not wrapped in create_task) to avoid nested timeouts
            # This prevents CancelledError from propagating incorrectly
            try:
                # Fetch torrents first (most important)
                torrents = await asyncio.wait_for(
                    self._data_provider.list_torrents(),
                    timeout=10.0  # Increased from 5.0 for better reliability
                )
            except asyncio.TimeoutError:
                logger.debug("GlobalTorrentsScreen: Timeout fetching torrents, skipping refresh")
                return
            except asyncio.CancelledError:
                logger.debug("GlobalTorrentsScreen: Torrent fetch cancelled")
                return
            except Exception as e:
                logger.debug("GlobalTorrentsScreen: Error fetching torrents: %s", e)
                return
            
            # Fetch stats and swarm samples in parallel with proper timeout handling
            try:
                stats, swarm_samples = await asyncio.gather(
                    asyncio.wait_for(self._data_provider.get_global_stats(), timeout=5.0),
                    asyncio.wait_for(self._data_provider.get_swarm_health_samples(limit=3), timeout=5.0),
                    return_exceptions=True
                )
                # Handle exceptions from gather
                if isinstance(stats, Exception):
                    if isinstance(stats, asyncio.TimeoutError):
                        logger.debug("GlobalTorrentsScreen: Timeout fetching global stats")
                    elif isinstance(stats, asyncio.CancelledError):
                        logger.debug("GlobalTorrentsScreen: Global stats fetch cancelled")
                    else:
                        logger.debug("GlobalTorrentsScreen: Error fetching global stats: %s", stats)
                    stats = {}
                if isinstance(swarm_samples, Exception):
                    if isinstance(swarm_samples, asyncio.TimeoutError):
                        logger.debug("GlobalTorrentsScreen: Timeout fetching swarm health")
                    elif isinstance(swarm_samples, asyncio.CancelledError):
                        logger.debug("GlobalTorrentsScreen: Swarm health fetch cancelled")
                    else:
                        logger.debug("GlobalTorrentsScreen: Error fetching swarm health: %s", swarm_samples)
                    swarm_samples = []
            except Exception as e:
                logger.debug("GlobalTorrentsScreen: Error in gather for stats/swarm: %s", e)
                stats = {}
                swarm_samples = []
            logger.debug(
                "GlobalTorrentsScreen: Retrieved %d torrents",
                len(torrents) if torrents else 0,
            )
            if self._metrics_panel:
                self._metrics_panel.update_metrics(stats, swarm_samples or [])
            
            # Apply filter
            if self._filter_text:
                torrents = [
                    t for t in torrents
                    if self._filter_text.lower() in t.get("name", "").lower()
                ]
            
            if not torrents:
                if self._torrents_table:
                    self._torrents_table.clear()
                    self._torrents_table.display = False  # type: ignore[attr-defined]
                if self._empty_message:
                    self._empty_message.display = True  # type: ignore[attr-defined]
                return

            if self._empty_message:
                self._empty_message.display = False  # type: ignore[attr-defined]
            if self._torrents_table and not self._torrents_table.display:  # type: ignore[attr-defined]
                self._torrents_table.display = True  # type: ignore[attr-defined]
            
            if not self._torrents_table:
                return

            # Clear and repopulate table
            self._torrents_table.clear()
            # CRITICAL FIX: Ensure columns exist (clear() might remove them)
            if not self._torrents_table.columns:  # type: ignore[attr-defined]
                self._torrents_table.add_columns(
                    "#",
                    _("Name"),
                    _("Size"),
                    _("Progress"),
                    _("Status"),
                    _("↓ Speed"),
                    _("↑ Speed"),
                    _("Peers"),
                    _("Seeds"),
                )
            
            logger.debug("GlobalTorrentsScreen: Populating table with %d torrents", len(torrents))
            
            for idx, torrent in enumerate(torrents, 1):
                # Format size
                size = torrent.get("total_size", 0)
                if size >= 1024 * 1024 * 1024:
                    size_str = f"{size / (1024**3):.2f} GB"
                elif size >= 1024 * 1024:
                    size_str = f"{size / (1024**2):.2f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size} B"
                
                # Format progress
                progress = torrent.get("progress", 0.0) * 100
                progress_str = f"{progress:.1f}%"
                
                # Format speeds
                down_rate = torrent.get("download_rate", 0.0)
                if down_rate >= 1024 * 1024:
                    down_str = f"{down_rate / (1024 * 1024):.2f} MB/s"
                elif down_rate >= 1024:
                    down_str = f"{down_rate / 1024:.2f} KB/s"
                else:
                    down_str = f"{down_rate:.2f} B/s"
                
                up_rate = torrent.get("upload_rate", 0.0)
                if up_rate >= 1024 * 1024:
                    up_str = f"{up_rate / (1024 * 1024):.2f} MB/s"
                elif up_rate >= 1024:
                    up_str = f"{up_rate / 1024:.2f} KB/s"
                else:
                    up_str = f"{up_rate:.2f} B/s"
                
                info_hash = torrent.get("info_hash", "")
                self._torrents_table.add_row(
                    str(idx),
                    torrent.get("name", "Unknown"),
                    size_str,
                    progress_str,
                    torrent.get("status", "unknown"),
                    down_str,
                    up_str,
                    str(torrent.get("num_peers", 0)),
                    str(torrent.get("num_seeds", 0)),
                    key=info_hash,
                )
            
            logger.debug("GlobalTorrentsScreen: Added %d torrents to table", len(torrents))
            
            # CRITICAL FIX: Force table refresh and ensure visibility
            if hasattr(self._torrents_table, "refresh"):
                self._torrents_table.refresh()  # type: ignore[attr-defined]
            self._torrents_table.display = True  # type: ignore[attr-defined]
        except asyncio.CancelledError:
            logger.debug("GlobalTorrentsScreen: Refresh cancelled")
            raise  # Re-raise CancelledError to allow proper cleanup
        except Exception as e:
            logger.error("Error refreshing torrents: %s", e, exc_info=True)

    def on_input_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle search input change.

        Args:
            event: Input.Changed event
        """
        if event.input.id == "search-input":
            self._filter_text = event.value
            # Trigger immediate refresh with new filter
            self.call_later(self.refresh_torrents)  # type: ignore[attr-defined]

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        """Handle torrent row selection.

        Args:
            event: DataTable.RowSelected event
        """
        if self._selected_hash_callback and event.cursor_row_key:
            info_hash = str(event.cursor_row_key)
            self._selected_hash_callback(info_hash)

    async def action_pause_torrent(self) -> None:  # pragma: no cover
        """Pause the selected torrent using executor."""
        if not self._command_executor or not self._torrents_table:
            return
        
        selected_key = self._torrents_table.get_selected_key()
        if selected_key:
            try:
                # Use executor to pause torrent (consistent with CLI)
                result = await self._command_executor.execute_command(
                    "torrent.pause", info_hash=selected_key
                )
                if result and hasattr(result, "success") and result.success:
                    self.app.notify(_("Torrent paused"), severity="success")  # type: ignore[attr-defined]
                    # Refresh to show updated status
                    await self.refresh_torrents()
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    self.app.notify(_("Pause failed: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
            except Exception as e:
                self.app.notify(_("Pause failed: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_resume_torrent(self) -> None:  # pragma: no cover
        """Resume the selected torrent using executor."""
        if not self._command_executor or not self._torrents_table:
            return
        
        selected_key = self._torrents_table.get_selected_key()
        if selected_key:
            try:
                # Use executor to resume torrent (consistent with CLI)
                result = await self._command_executor.execute_command(
                    "torrent.resume", info_hash=selected_key
                )
                if result and hasattr(result, "success") and result.success:
                    self.app.notify(_("Torrent resumed"), severity="success")  # type: ignore[attr-defined]
                    # Refresh to show updated status
                    await self.refresh_torrents()
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    self.app.notify(_("Resume failed: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
            except Exception as e:
                self.app.notify(_("Resume failed: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_remove_torrent(self) -> None:  # pragma: no cover
        """Remove the selected torrent using executor."""
        if not self._command_executor or not self._torrents_table:
            return
        
        selected_key = self._torrents_table.get_selected_key()
        if selected_key:
            try:
                # Use executor to remove torrent (consistent with CLI)
                result = await self._command_executor.execute_command(
                    "torrent.remove", info_hash=selected_key
                )
                if result and hasattr(result, "success") and result.success:
                    self.app.notify(_("Torrent removed"), severity="success")  # type: ignore[attr-defined]
                    # Refresh to show updated list
                    await self.refresh_torrents()
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    self.app.notify(_("Remove failed: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
            except Exception as e:
                self.app.notify(_("Remove failed: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_refresh_pex(self) -> None:  # pragma: no cover
        """Trigger a Peer Exchange refresh for the selected torrent."""
        if not self._command_executor or not self._torrents_table:
            return

        selected_key = self._torrents_table.get_selected_key()
        if not selected_key:
            return

        try:
            result = await self._command_executor.execute_command(
                "torrent.refresh_pex",
                info_hash=selected_key,
            )
            success = bool(getattr(result, "success", False))
            if not success and isinstance(result, dict):
                success = bool(result.get("success"))

            if success:
                self.app.notify(_("PEX refresh requested"), severity="success")  # type: ignore[attr-defined]
            else:
                error_msg = getattr(result, "error", None)
                if isinstance(result, dict):
                    error_msg = error_msg or result.get("error")
                self.app.notify(  # type: ignore[attr-defined]
                    _("PEX refresh failed: {error}").format(error=error_msg or _("Unknown error")),
                    severity="error",
                )
        except Exception as e:
            self.app.notify(  # type: ignore[attr-defined]
                _("PEX refresh failed: {error}").format(error=str(e)),
                severity="error",
            )


class FilteredTorrentsScreen(Container):  # type: ignore[misc]
    """Base screen for filtered torrent views (Downloading, Seeding, etc.)."""

    DEFAULT_CSS = """
    FilteredTorrentsScreen {
        height: 1fr;
        layout: vertical;
    }
    
    #torrents-table {
        height: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        filter_status: str | None = None,
        selected_hash_callback: Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize filtered torrents screen.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance for executing commands
            filter_status: Status to filter by (e.g., "downloading", "seeding")
            selected_hash_callback: Optional callback when torrent is selected (info_hash: str) -> None
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._filter_status = filter_status
        self._selected_hash_callback = selected_hash_callback
        self._torrents_table: DataTable | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the filtered torrents screen."""
        yield DataTable(id="torrents-table")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the filtered torrents screen."""
        try:
            self._torrents_table = self.query_one("#torrents-table", DataTable)  # type: ignore[attr-defined]
            
            if self._torrents_table:
                self._torrents_table.add_columns(
                    "#",
                    _("Name"),
                    _("Size"),
                    _("Progress"),
                    _("Status"),
                    _("↓ Speed"),
                    _("↑ Speed"),
                    _("Peers"),
                    _("Seeds"),
                )
                self._torrents_table.zebra_stripes = True
            
            # CRITICAL FIX: Schedule periodic refresh with proper async handling
            def schedule_refresh() -> None:
                import asyncio
                asyncio.create_task(self.refresh_torrents())
            
            self.set_interval(1.0, schedule_refresh)  # type: ignore[attr-defined]
            # Also refresh immediately
            schedule_refresh()
            
            # CRITICAL FIX: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            if self._torrents_table:
                self._torrents_table.display = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting filtered torrents screen: %s", e, exc_info=True)

    async def refresh_torrents(self) -> None:  # pragma: no cover
        """Refresh torrents table with filtered data."""
        # CRITICAL FIX: Check if widget is visible and attached before refreshing
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("FilteredTorrentsScreen: Widget not attached or not visible, skipping refresh")
            return
        
        # CRITICAL FIX: Re-query _torrents_table if it's None (may happen if called before on_mount completes)
        if not self._torrents_table:
            try:
                self._torrents_table = self.query_one("#torrents-table", DataTable)  # type: ignore[attr-defined]
                if not self._torrents_table:
                    logger.warning("FilteredTorrentsScreen: Could not find torrents table, deferring refresh")
                    return
                # Set up columns if table was just found
                if not self._torrents_table.columns:  # type: ignore[attr-defined]
                    self._torrents_table.add_columns(
                        "#",
                        _("Name"),
                        _("Size"),
                        _("Progress"),
                        _("Status"),
                        _("↓ Speed"),
                        _("↑ Speed"),
                        _("Peers"),
                        _("Seeds"),
                    )
            except Exception as e:
                logger.debug("FilteredTorrentsScreen: Error re-querying table: %s", e)
                return
        
        # CRITICAL FIX: Re-query _data_provider if it's None (should be set in __init__, but check anyway)
        if not self._data_provider:
            logger.warning("FilteredTorrentsScreen: Missing data provider, cannot refresh")
            return
        
        try:
            logger.debug("FilteredTorrentsScreen: Fetching torrents from data provider (filter: %s)...", self._filter_status)
            # CRITICAL FIX: Add timeout to prevent UI hangs, handle CancelledError properly
            try:
                torrents = await asyncio.wait_for(
                    self._data_provider.list_torrents(),
                    timeout=10.0  # Increased from 5.0 for better reliability
                )
            except asyncio.TimeoutError:
                logger.debug("FilteredTorrentsScreen: Timeout fetching torrents, skipping refresh")
                return
            except asyncio.CancelledError:
                logger.debug("FilteredTorrentsScreen: Torrent fetch cancelled")
                raise  # Re-raise CancelledError to allow proper cleanup
            except Exception as e:
                logger.debug("FilteredTorrentsScreen: Error fetching torrents: %s", e)
                return
            logger.debug("FilteredTorrentsScreen: Retrieved %d torrents before filtering", len(torrents) if torrents else 0)
            
            # Apply status filter
            if self._filter_status:
                if self._filter_status == "active":
                    # Active = downloading or seeding
                    torrents = [
                        t for t in torrents
                        if t.get("status", "").lower() in ("downloading", "seeding")
                    ]
                elif self._filter_status == "inactive":
                    # Inactive = paused or stopped
                    torrents = [
                        t for t in torrents
                        if t.get("status", "").lower() in ("paused", "stopped")
                    ]
                elif self._filter_status == "completed":
                    # Completed = progress >= 1.0
                    torrents = [
                        t for t in torrents
                        if t.get("progress", 0.0) >= 1.0
                    ]
                else:
                    # Exact status match
                    torrents = [
                        t for t in torrents
                        if t.get("status", "").lower() == self._filter_status.lower()
                    ]
            
            # CRITICAL FIX: Ensure table is visible before populating
            if not self._torrents_table.is_attached or not self._torrents_table.display:  # type: ignore[attr-defined]
                logger.debug("FilteredTorrentsScreen: Table not attached or not visible, skipping population")
                return
            
            # Populate table (same logic as GlobalTorrentsScreen)
            self._torrents_table.clear()
            # CRITICAL FIX: Ensure columns exist (clear() might remove them)
            if not self._torrents_table.columns:  # type: ignore[attr-defined]
                self._torrents_table.add_columns(
                    "#",
                    _("Name"),
                    _("Size"),
                    _("Progress"),
                    _("Status"),
                    _("↓ Speed"),
                    _("↑ Speed"),
                    _("Peers"),
                    _("Seeds"),
                )
            
            logger.debug("FilteredTorrentsScreen: Filtered to %d torrents", len(torrents))
            
            for idx, torrent in enumerate(torrents, 1):
                size = torrent.get("total_size", 0)
                if size >= 1024 * 1024 * 1024:
                    size_str = f"{size / (1024**3):.2f} GB"
                elif size >= 1024 * 1024:
                    size_str = f"{size / (1024**2):.2f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size} B"
                
                progress = torrent.get("progress", 0.0) * 100
                progress_str = f"{progress:.1f}%"
                
                down_rate = torrent.get("download_rate", 0.0)
                if down_rate >= 1024 * 1024:
                    down_str = f"{down_rate / (1024 * 1024):.2f} MB/s"
                elif down_rate >= 1024:
                    down_str = f"{down_rate / 1024:.2f} KB/s"
                else:
                    down_str = f"{down_rate:.2f} B/s"
                
                up_rate = torrent.get("upload_rate", 0.0)
                if up_rate >= 1024 * 1024:
                    up_str = f"{up_rate / (1024 * 1024):.2f} MB/s"
                elif up_rate >= 1024:
                    up_str = f"{up_rate / 1024:.2f} KB/s"
                else:
                    up_str = f"{up_rate:.2f} B/s"
                
                info_hash = torrent.get("info_hash", "")
                self._torrents_table.add_row(
                    str(idx),
                    torrent.get("name", "Unknown"),
                    size_str,
                    progress_str,
                    torrent.get("status", "unknown"),
                    down_str,
                    up_str,
                    str(torrent.get("num_peers", 0)),
                    str(torrent.get("num_seeds", 0)),
                    key=info_hash,
                )
            
            logger.debug("FilteredTorrentsScreen: Added %d torrents to table", len(torrents))
            
            # CRITICAL FIX: Force table refresh and ensure visibility
            if hasattr(self._torrents_table, "refresh"):
                self._torrents_table.refresh()  # type: ignore[attr-defined]
            self._torrents_table.display = True  # type: ignore[attr-defined]
        except asyncio.CancelledError:
            logger.debug("FilteredTorrentsScreen: Refresh cancelled")
            raise  # Re-raise CancelledError to allow proper cleanup
        except Exception as e:
            logger.error("Error refreshing filtered torrents: %s", e, exc_info=True)

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        """Handle torrent row selection.

        Args:
            event: DataTable.RowSelected event
        """
        if self._selected_hash_callback and event.cursor_row_key:
            info_hash = str(event.cursor_row_key)
            self._selected_hash_callback(info_hash)


class TorrentsTabContent(Container):  # type: ignore[misc]
    """Main content container for Torrents tab with nested sub-tabs."""

    DEFAULT_CSS = """
    TorrentsTabContent {
        height: 1fr;
        layout: vertical;
        overflow: hidden;
    }
    
    #torrents-sub-tabs {
        height: auto;
        min-height: 3;
    }
    
    #torrents-sub-content {
        height: 1fr;
        min-height: 10;
        overflow-y: auto;
        overflow-x: hidden;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        selected_hash_callback: Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrents tab content.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance for executing commands
            selected_hash_callback: Optional callback when torrent is selected (info_hash: str) -> None
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._selected_hash_callback = selected_hash_callback
        self._sub_tabs: Tabs | None = None
        self._content_area: Container | None = None
        self._active_sub_tab_id: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the torrents tab with nested sub-tabs."""
        # Sub-tabs for different torrent states
        yield Tabs(
            Tab(_("Global"), id="sub-tab-global"),
            Tab(_("Downloading"), id="sub-tab-downloading"),
            Tab(_("Seeding"), id="sub-tab-seeding"),
            Tab(_("Completed"), id="sub-tab-completed"),
            Tab(_("Active"), id="sub-tab-active"),
            Tab(_("Inactive"), id="sub-tab-inactive"),
            id="torrents-sub-tabs",
        )
        
        # Content area for sub-tab content
        with Container(id="torrents-sub-content"):
            yield Static(_("Select a sub-tab to view torrents"), id="sub-content-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrents tab content."""
        try:
            self._sub_tabs = self.query_one("#torrents-sub-tabs", Tabs)  # type: ignore[attr-defined]
            self._content_area = self.query_one("#torrents-sub-content", Container)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure tab is active and content area is visible
            if self._sub_tabs:
                self._sub_tabs.active = "sub-tab-global"  # type: ignore[attr-defined]
            if self._content_area:
                self._content_area.display = True  # type: ignore[attr-defined]
            # Load initial content for Global sub-tab
            self._load_sub_tab_content("sub-tab-global")
        except Exception as e:
            logger.error("Error mounting torrents tab content: %s", e, exc_info=True)

    def _load_sub_tab_content(self, sub_tab_id: str) -> None:  # pragma: no cover
        """Load content for a specific sub-tab.

        Args:
            sub_tab_id: ID of the sub-tab to load
        """
        if not self._content_area or not self._data_provider:
            return
        if sub_tab_id == self._active_sub_tab_id:
            return
        
        # CRITICAL FIX: Properly remove existing widgets by ID to prevent duplicate ID errors
        # We need to check the parent's children list directly and remove all instances
        try:
            # Get all children and remove them individually to ensure proper cleanup
            # This is more reliable than query_one which might miss widgets in certain states
            children_to_remove = list(self._content_area.children)  # type: ignore[attr-defined]
            for child in children_to_remove:
                try:
                    child.remove()  # type: ignore[attr-defined]
                except Exception:
                    pass  # Widget might already be removed, ignore
            
            # Also explicitly remove by ID as a backup
            screen_ids = [
                "global-screen", "downloading-screen", "seeding-screen",
                "completed-screen", "active-screen", "inactive-screen"
            ]
            for screen_id in screen_ids:
                try:
                    # Try to find and remove by ID (might find duplicates)
                    existing_screens = list(self._content_area.query(f"#{screen_id}"))  # type: ignore[attr-defined]
                    for existing_screen in existing_screens:
                        try:
                            existing_screen.remove()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    pass  # Widget might not exist, ignore
            
            # Call remove_children() as final cleanup
            self._content_area.remove_children()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error removing existing content: %s", e)
        
        # Mount the new screen
        self._mount_sub_tab_screen(sub_tab_id)
    
    def _mount_sub_tab_screen(self, sub_tab_id: str) -> None:  # pragma: no cover
        """Mount the screen for a specific sub-tab.
        
        Args:
            sub_tab_id: ID of the sub-tab to load
        """
        if not self._content_area or not self._data_provider:
            return
        
        # CRITICAL FIX: Determine target screen ID and check if it already exists
        target_screen_id = None
        if sub_tab_id == "sub-tab-global":
            target_screen_id = "global-screen"
        elif sub_tab_id == "sub-tab-downloading":
            target_screen_id = "downloading-screen"
        elif sub_tab_id == "sub-tab-seeding":
            target_screen_id = "seeding-screen"
        elif sub_tab_id == "sub-tab-completed":
            target_screen_id = "completed-screen"
        elif sub_tab_id == "sub-tab-active":
            target_screen_id = "active-screen"
        elif sub_tab_id == "sub-tab-inactive":
            target_screen_id = "inactive-screen"
        
        # CRITICAL FIX: Double-check that no widget with the target ID exists before mounting
        # Check parent's children list directly to find all instances
        if target_screen_id:
            try:
                # Check all children for matching ID
                children_to_remove = []
                for child in self._content_area.children:  # type: ignore[attr-defined]
                    if hasattr(child, "id") and child.id == target_screen_id:  # type: ignore[attr-defined]
                        children_to_remove.append(child)
                
                # Remove all instances found
                for existing in children_to_remove:
                    try:
                        logger.debug("Removing existing widget with ID %s before mounting", target_screen_id)
                        existing.remove()  # type: ignore[attr-defined]
                    except Exception as e:
                        logger.debug("Error removing existing widget: %s", e)
                
                # Also try query as backup
                existing_screens = list(self._content_area.query(f"#{target_screen_id}"))  # type: ignore[attr-defined]
                for existing in existing_screens:
                    try:
                        existing.remove()  # type: ignore[attr-defined]
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Error checking for existing widget: %s", e)
        
        # Load appropriate screen based on sub-tab
        if sub_tab_id == "sub-tab-global":
            screen = GlobalTorrentsScreen(
                self._data_provider,
                self._command_executor,
                selected_hash_callback=self._selected_hash_callback,
                id="global-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-downloading":
            screen = FilteredTorrentsScreen(
                self._data_provider,
                self._command_executor,
                filter_status="downloading",
                selected_hash_callback=self._selected_hash_callback,
                id="downloading-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-seeding":
            screen = FilteredTorrentsScreen(
                self._data_provider,
                self._command_executor,
                filter_status="seeding",
                selected_hash_callback=self._selected_hash_callback,
                id="seeding-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-completed":
            # Completed = progress >= 1.0
            screen = FilteredTorrentsScreen(
                self._data_provider,
                self._command_executor,
                filter_status="completed",
                selected_hash_callback=self._selected_hash_callback,
                id="completed-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-active":
            # Active = downloading or seeding
            screen = FilteredTorrentsScreen(
                self._data_provider,
                self._command_executor,
                filter_status="active",
                selected_hash_callback=self._selected_hash_callback,
                id="active-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-inactive":
            # Inactive = paused or stopped
            screen = FilteredTorrentsScreen(
                self._data_provider,
                self._command_executor,
                filter_status="inactive",
                selected_hash_callback=self._selected_hash_callback,
                id="inactive-screen"
            )
            self._content_area.mount(screen)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure screen is visible
            screen.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Trigger refresh after mounting to populate data
            def refresh_after_mount() -> None:
                import asyncio
                if hasattr(screen, "refresh_torrents"):
                    asyncio.create_task(screen.refresh_torrents())
            self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        else:
            placeholder = Static(f"{sub_tab_id} content - Coming soon", id=f"{sub_tab_id}-content")
            self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:  # pragma: no cover
        """Handle activation events for the torrents sub-tabs."""
        tab = getattr(event, "tab", None)
        tab_id = getattr(tab, "id", None)
        if tab_id:
            self._load_sub_tab_content(tab_id)
            # CRITICAL FIX: Refresh content after loading sub-tab
            self.call_later(self._refresh_active_sub_tab)  # type: ignore[attr-defined]

    async def _refresh_active_sub_tab(self) -> None:  # pragma: no cover
        """Refresh the currently active sub-tab screen."""
        if not self._active_sub_tab_id:
            return
        
        try:
            if self._active_sub_tab_id == "sub-tab-global":
                # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                try:
                    screen = self.query_one(GlobalTorrentsScreen)  # type: ignore[attr-defined]
                    if screen and hasattr(screen, "refresh_torrents"):
                        await screen.refresh_torrents()
                except Exception:
                    pass
            else:
                # For filtered screens
                from ccbt.interface.screens.torrents_tab import FilteredTorrentsScreen
                screens = list(self.query(FilteredTorrentsScreen))  # type: ignore[attr-defined]
                for screen in screens:
                    if screen.display and hasattr(screen, "refresh_torrents"):  # type: ignore[attr-defined]
                        await screen.refresh_torrents()
                        break
        except Exception as e:
            logger.debug("Error refreshing active sub-tab: %s", e)

