"""Tabbed interface widgets for the refactored dashboard.

Provides widgets for the main tabbed interface structure.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

logger = logging.getLogger(__name__)

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
    from textual.containers import Container, Horizontal
    from textual.widgets import Static, Tabs, Tab
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Tabs:  # type: ignore[no-redef]
        pass

    class Tab:  # type: ignore[no-redef]
        pass


class MainTabsContainer(Container):  # type: ignore[misc]
    """Container for main tabs (Torrents, Per-Torrent, Preferences).

    This container holds the main tab navigation and content area.
    """

    DEFAULT_CSS = """
    MainTabsContainer {
        height: 1fr;
        layout: horizontal;
        overflow: hidden;
        min-width: 100;
        display: block;
    }
    
    /* Left pane: Workflow (File Browser + Controls) - CRITICAL FIX: Swapped to 2fr */
    #workflow-pane {
        width: 2fr;
        min-width: 80;
        layout: vertical;
        border: solid $primary;
        overflow: hidden;
        display: block;
    }
    
    #workflow-tabs {
        height: auto;
        min-height: 3;
        display: block;
    }
    
    #workflow-content {
        height: 1fr;
        min-height: 15;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    
    /* Right pane: Torrent Insight (Torrents + Per-Torrent) - CRITICAL FIX: Swapped to 1fr */
    #torrent-insight-pane {
        width: 1fr;
        min-width: 60;
        layout: vertical;
        border: solid $primary;
        overflow: hidden;
        display: block;
    }
    
    #torrent-insight-tabs {
        height: auto;
        min-height: 3;
        display: block;
    }
    
    #torrent-insight-content {
        height: 1fr;
        min-height: 15;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    """

    def __init__(
        self,
        session: AsyncSessionManager,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize main tabs container.

        Args:
            session: AsyncSessionManager instance
        """
        super().__init__(*args, **kwargs)
        self.session = session
        # Workflow pane tabs (left side)
        self._workflow_selector: Any | None = None  # ButtonSelector
        self._workflow_content: Container | None = None
        self._active_workflow_tab_id: str | None = None
        # Torrent Insight pane selector (right side)
        self._torrent_insight_selector: Any | None = None  # ButtonSelector
        self._torrent_insight_content: Container | None = None
        self._active_insight_tab_id: str | None = None
        # Shared selection model for cross-pane communication
        self._selected_torrent_hash: str | None = None
        # Create command executor first (like CLI uses)
        from ccbt.interface.commands.executor import CommandExecutor
        self._command_executor: CommandExecutor | None = CommandExecutor(session)
        # Create data provider with executor reference
        from ccbt.interface.data_provider import create_data_provider
        # Pass executor to data provider so it can use executor for commands
        executor_for_provider = self._command_executor._executor if self._command_executor and hasattr(self._command_executor, "_executor") else None
        self._data_provider: DataProvider | None = create_data_provider(session, executor_for_provider)

    def compose(self) -> Any:  # pragma: no cover
        """Compose the main tabs container with side-by-side panes.
        
        CRITICAL FIX: Replaced Tabs with ButtonSelector for better visibility control.
        """
        from ccbt.interface.widgets.button_selector import ButtonSelector
        
        # Left pane: Workflow (File Browser + Controls)
        with Container(id="workflow-pane"):
            yield ButtonSelector(
                [
                    ("tab-file-browser", _("File Browser")),
                    ("tab-controls", _("Controls")),
                ],
                initial_selection="tab-file-browser",
                id="workflow-selector",
            )
            with Container(id="workflow-content"):
                yield Static(_("Select a workflow tab"), id="workflow-placeholder")
        
        # Right pane: Torrent Insight (Torrents + Per-Torrent + Per-Peer)
        with Container(id="torrent-insight-pane"):
            yield ButtonSelector(
                [
                    ("tab-torrents", _("Torrents")),
                    ("tab-per-torrent", _("Per-Torrent")),
                    ("tab-per-peer", _("Per-Peer")),
                ],
                initial_selection="tab-torrents",
                id="torrent-insight-selector",
            )
            with Container(id="torrent-insight-content"):
                yield Static(_("Select a torrent insight tab"), id="insight-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the main tabs container."""
        try:
            from ccbt.interface.widgets.button_selector import ButtonSelector
            
            # Initialize workflow pane (left)
            self._workflow_selector = self.query_one("#workflow-selector", ButtonSelector)  # type: ignore[attr-defined]
            self._workflow_content = self.query_one("#workflow-content", Container)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure selector is active and content is visible
            if self._workflow_selector:
                self._workflow_selector.active = "tab-file-browser"  # type: ignore[attr-defined]
            # Load initial content for File Browser tab
            self._load_workflow_tab_content("tab-file-browser")
            # Ensure content area is visible
            if self._workflow_content:
                self._workflow_content.display = True  # type: ignore[attr-defined]
            
            # Initialize torrent insight pane (right)
            self._torrent_insight_selector = self.query_one("#torrent-insight-selector", ButtonSelector)  # type: ignore[attr-defined]
            self._torrent_insight_content = self.query_one("#torrent-insight-content", Container)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure selector is active and content is visible
            if self._torrent_insight_selector:
                self._torrent_insight_selector.active = "tab-torrents"  # type: ignore[attr-defined]
            # Load initial content for Torrents tab
            self._load_insight_tab_content("tab-torrents")
            # Ensure content area is visible
            if self._torrent_insight_content:
                self._torrent_insight_content.display = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting main tabs container: %s", e, exc_info=True)

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

            # Update workflow selector labels (ButtonSelector buttons update automatically via i18n)
            # No manual label update needed for ButtonSelector

            # Update torrent insight selector labels (ButtonSelector buttons update automatically via i18n)
            # No manual label update needed for ButtonSelector

            # Update placeholder text if visible
            try:
                workflow_placeholder = self.query_one("#workflow-placeholder", Static)  # type: ignore[attr-defined]
                if workflow_placeholder and workflow_placeholder.display:  # type: ignore[attr-defined]
                    workflow_placeholder.update(_("Select a workflow tab"))
            except Exception:
                pass

            try:
                insight_placeholder = self.query_one("#insight-placeholder", Static)  # type: ignore[attr-defined]
                if insight_placeholder and insight_placeholder.display:  # type: ignore[attr-defined]
                    insight_placeholder.update(_("Select a torrent insight tab"))
            except Exception:
                pass

            # Forward message to child widgets that may need to refresh
            try:
                # Forward to workflow content widgets
                if self._workflow_content:
                    for child in self._workflow_content.children:  # type: ignore[attr-defined]
                        if hasattr(child, "post_message"):
                            child.post_message(message)  # type: ignore[attr-defined]
                
                # Forward to insight content widgets
                if self._torrent_insight_content:
                    for child in self._torrent_insight_content.children:  # type: ignore[attr-defined]
                        if hasattr(child, "post_message"):
                            child.post_message(message)  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error forwarding language change to children: %s", e)

        except Exception as e:
            logger.debug("Error refreshing main tabs translations: %s", e)

    def _load_workflow_tab_content(self, tab_id: str) -> None:  # pragma: no cover
        """Load content for a workflow pane tab (File Browser or Controls).

        Args:
            tab_id: ID of the workflow tab to load
        """
        if not self._workflow_content:
            return
        if tab_id == self._active_workflow_tab_id:
            return
        
        # Clear existing content
        try:
            self._workflow_content.remove_children()  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Add new content based on tab
        if tab_id == "tab-file-browser":
            # Load File Browser widget
            from ccbt.interface.widgets.file_browser import FileBrowserWidget
            if self._data_provider and self._command_executor:
                try:
                    browser = FileBrowserWidget(
                        self._data_provider,
                        self._command_executor,
                        id="file-browser-widget"
                    )
                    self._workflow_content.mount(browser)  # type: ignore[attr-defined]
                    # CRITICAL FIX: Ensure widget is visible and properly mounted
                    browser.display = True  # type: ignore[attr-defined]
                    # CRITICAL FIX: Ensure workflow content container is visible
                    if self._workflow_content:
                        self._workflow_content.display = True  # type: ignore[attr-defined]
                    # Schedule refresh after mount completes
                    def refresh_after_mount() -> None:
                        try:
                            if hasattr(browser, "_refresh_file_list"):
                                browser._refresh_file_list()
                        except Exception:
                            pass
                    self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
                    logger.debug("FileBrowserWidget mounted and scheduled for refresh")
                except Exception as e:
                    logger.debug("Error mounting FileBrowserWidget: %s", e)
                    # Fallback: use placeholder
                    placeholder = Static(_("File Browser - Error: {error}").format(error=str(e)), id="file-browser-placeholder")
                    self._workflow_content.mount(placeholder)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("File Browser - Data provider or executor not available"), id="file-browser-placeholder")
                self._workflow_content.mount(placeholder)  # type: ignore[attr-defined]
            self._active_workflow_tab_id = tab_id
        elif tab_id == "tab-controls":
            # Load Controls widget
            from ccbt.interface.widgets.torrent_controls import TorrentControlsWidget
            if self._data_provider and self._command_executor:
                try:
                    controls = TorrentControlsWidget(
                        self._data_provider,
                        self._command_executor,
                        selected_hash_callback=self._on_torrent_selected_from_controls,
                        id="torrent-controls-widget"
                    )
                    self._workflow_content.mount(controls)  # type: ignore[attr-defined]
                    # CRITICAL FIX: Ensure widget is visible and properly mounted
                    controls.display = True  # type: ignore[attr-defined]
                    # Schedule refresh after mount completes
                    def refresh_after_mount() -> None:
                        import asyncio
                        try:
                            if hasattr(controls, "_refresh_torrent_list"):
                                asyncio.create_task(controls._refresh_torrent_list())
                        except Exception:
                            pass
                    self.call_later(refresh_after_mount)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("Error mounting TorrentControlsWidget: %s", e)
                    # Fallback: use placeholder
                    placeholder = Static(_("Torrent Controls - Error: {error}").format(error=str(e)), id="controls-placeholder")
                    self._workflow_content.mount(placeholder)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Torrent Controls - Data provider or executor not available"), id="controls-placeholder")
                self._workflow_content.mount(placeholder)  # type: ignore[attr-defined]
            self._active_workflow_tab_id = tab_id

    def _load_insight_tab_content(self, tab_id: str) -> None:  # pragma: no cover
        """Load content for a torrent insight pane tab (Torrents or Per-Torrent).

        Args:
            tab_id: ID of the insight tab to load
        """
        if not self._torrent_insight_content:
            return
        if tab_id == self._active_insight_tab_id:
            return
        
        # Clear existing content
        try:
            self._torrent_insight_content.remove_children()  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Add new content based on tab
        if tab_id == "tab-torrents":
            # Load TorrentsTabContent with nested sub-tabs
            from ccbt.interface.screens.torrents_tab import TorrentsTabContent
            if self._data_provider and self._command_executor:
                # Pass callback if TorrentsTabContent supports it (optional for backward compatibility)
                try:
                    content = TorrentsTabContent(
                        self._data_provider,
                        self._command_executor,
                        selected_hash_callback=self._on_torrent_selected_from_list,
                        id="torrents-content"
                    )
                except TypeError:
                    # Fallback if callback not supported yet
                    content = TorrentsTabContent(
                        self._data_provider,
                        self._command_executor,
                        id="torrents-content"
                    )
                self._torrent_insight_content.mount(content)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure widget is visible
                content.display = True  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Torrents tab - Data provider or executor not available"), id="torrents-content")
                self._torrent_insight_content.mount(placeholder)  # type: ignore[attr-defined]
            self._active_insight_tab_id = tab_id
        elif tab_id == "tab-per-torrent":
            # Load PerTorrentTabContent with executor
            from ccbt.interface.screens.per_torrent_tab import PerTorrentTabContent
            if self._data_provider and self._command_executor:
                # Pass selected_info_hash if supported (optional for backward compatibility)
                try:
                    content = PerTorrentTabContent(
                        self._data_provider,
                        self._command_executor,
                        selected_info_hash=self._selected_torrent_hash,
                        id="per-torrent-content"
                    )
                except TypeError:
                    # Fallback if selected_info_hash not supported yet
                    content = PerTorrentTabContent(
                        self._data_provider,
                        self._command_executor,
                        id="per-torrent-content"
                    )
                    # Set selected hash after creation if widget supports it
                    if hasattr(content, "_selected_info_hash"):
                        content._selected_info_hash = self._selected_torrent_hash
                self._torrent_insight_content.mount(content)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure widget is visible
                content.display = True  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Per-Torrent tab - Data provider or executor not available"), id="per-torrent-content")
                self._torrent_insight_content.mount(placeholder)  # type: ignore[attr-defined]
            self._active_insight_tab_id = tab_id
        elif tab_id == "tab-per-peer":
            # Load PerPeerTabContent
            from ccbt.interface.screens.per_peer_tab import PerPeerTabContent
            if self._data_provider and self._command_executor:
                content = PerPeerTabContent(
                    self._data_provider,
                    self._command_executor,
                    id="per-peer-content"
                )
                self._torrent_insight_content.mount(content)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure widget is visible
                content.display = True  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Per-Peer tab - Data provider or executor not available"), id="per-peer-content")
                self._torrent_insight_content.mount(placeholder)  # type: ignore[attr-defined]
            self._active_insight_tab_id = tab_id

    def _on_torrent_selected_from_controls(self, info_hash: str) -> None:  # pragma: no cover
        """Handle torrent selection from Controls tab.
        
        Args:
            info_hash: Selected torrent info hash
        """
        self._selected_torrent_hash = info_hash
        # Update Per-Torrent tab if it's already mounted
        try:
            per_torrent_content = self._torrent_insight_content.query_one("#per-torrent-content")  # type: ignore[attr-defined]
            if per_torrent_content and hasattr(per_torrent_content, "set_selected_info_hash"):
                per_torrent_content.set_selected_info_hash(info_hash)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Switch to Per-Torrent tab and update it
        if self._torrent_insight_selector:
            try:
                # Activate Per-Torrent selection
                self._torrent_insight_selector.active = "tab-per-torrent"  # type: ignore[attr-defined]
                self._load_insight_tab_content("tab-per-torrent")
            except Exception:
                pass

    def _on_torrent_selected_from_list(self, info_hash: str) -> None:  # pragma: no cover
        """Handle torrent selection from Torrents list tab.
        
        Args:
            info_hash: Selected torrent info hash
        """
        self._selected_torrent_hash = info_hash
        # Update Per-Torrent tab if it's already mounted
        try:
            per_torrent_content = self._torrent_insight_content.query_one("#per-torrent-content")  # type: ignore[attr-defined]
            if per_torrent_content and hasattr(per_torrent_content, "set_selected_info_hash"):
                per_torrent_content.set_selected_info_hash(info_hash)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Also reload if Per-Torrent tab is active
        if self._active_insight_tab_id == "tab-per-torrent":
            self._load_insight_tab_content("tab-per-torrent")

    def on_button_selector_selection_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle ButtonSelector selection change events.
        
        Args:
            event: ButtonSelector.SelectionChanged message
        """
        from ccbt.interface.widgets.button_selector import ButtonSelector
        
        if not hasattr(event, "selection_id"):
            return
        
        selection_id = event.selection_id
        selector = event.selector if hasattr(event, "selector") else None
        
        if not selector:
            return
        
        # Determine which pane this event came from
        selector_id = getattr(selector, "id", None)
        if selector_id == "workflow-selector":
            self._load_workflow_tab_content(selection_id)
            # CRITICAL FIX: Refresh content after loading and ensure visibility
            if selection_id == "tab-file-browser":
                try:
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    # Use try/except pattern instead
                    try:
                        file_browser = self._workflow_content.query_one("#file-browser-widget")  # type: ignore[attr-defined]
                        # Ensure widget is visible
                        file_browser.display = True  # type: ignore[attr-defined]
                        # Refresh file list after a brief delay to ensure widget is mounted
                        if hasattr(file_browser, "_refresh_file_list"):
                            self.call_later(file_browser._refresh_file_list)  # type: ignore[attr-defined]
                    except Exception:
                        # Widget not found yet, will be available after mount
                        pass
                except Exception as e:
                    logger.debug("Error refreshing file browser: %s", e)
            elif selection_id == "tab-controls":
                try:
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    # Use try/except pattern instead
                    try:
                        controls = self._workflow_content.query_one("#torrent-controls-widget")  # type: ignore[attr-defined]
                        # Ensure widget is visible
                        controls.display = True  # type: ignore[attr-defined]
                        # Refresh torrent list after a brief delay to ensure widget is mounted
                        if hasattr(controls, "_refresh_torrent_list"):
                            import asyncio
                            asyncio.create_task(controls._refresh_torrent_list())
                    except Exception:
                        # Widget not found yet, will be available after mount
                        pass
                except Exception as e:
                    logger.debug("Error refreshing torrent controls: %s", e)
        elif selector_id == "torrent-insight-selector":
            self._load_insight_tab_content(selection_id)
            # CRITICAL FIX: Ensure content area is visible
            if self._torrent_insight_content:
                self._torrent_insight_content.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Refresh content after loading
            if selection_id == "tab-torrents":
                try:
                    from ccbt.interface.screens.torrents_tab import TorrentsTabContent
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    torrents_content = self._torrent_insight_content.query_one(TorrentsTabContent)  # type: ignore[attr-defined]
                    if torrents_content:
                        # Trigger refresh of active sub-tab
                        try:
                            from ccbt.interface.screens.torrents_tab import GlobalTorrentsScreen
                            global_screen = torrents_content.query_one(GlobalTorrentsScreen)  # type: ignore[attr-defined]
                            if global_screen and hasattr(global_screen, "refresh_torrents"):
                                # CRITICAL FIX: refresh_torrents is async, use create_task
                                import asyncio
                                asyncio.create_task(global_screen.refresh_torrents())
                        except Exception:
                            pass
                except Exception:
                    pass
            elif selection_id == "tab-per-torrent":
                try:
                    from ccbt.interface.screens.per_torrent_tab import PerTorrentTabContent
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    per_torrent_content = self._torrent_insight_content.query_one(PerTorrentTabContent)  # type: ignore[attr-defined]
                    if per_torrent_content and hasattr(per_torrent_content, "refresh"):
                        self.call_later(per_torrent_content.refresh)  # type: ignore[attr-defined]
                except Exception:
                    pass

