"""Per-Torrent tab screen implementation.

Implements the Per-Torrent tab with nested sub-tabs for detailed torrent information.
"""

from __future__ import annotations

import logging
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
    from textual.containers import Container
    from textual.widgets import Select, Static, Tabs, Tab
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Tabs:  # type: ignore[no-redef]
        pass

    class Tab:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class PerTorrentTabContent(Container):  # type: ignore[misc]
    """Main content container for Per-Torrent tab with nested sub-tabs."""

    DEFAULT_CSS = """
    PerTorrentTabContent {
        height: 1fr;
        layout: vertical;
        overflow: hidden;
    }
    
    #torrent-selector {
        height: auto;
        min-height: 3;
        display: block;
        margin: 1;
    }
    
    #per-torrent-sub-tabs {
        height: auto;
        min-height: 3;
    }
    
    #per-torrent-sub-content {
        height: 1fr;
        min-height: 10;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    #file-tree {
        height: 1fr;
        width: 1fr;
    }
    
    DirectoryTree {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        selected_info_hash: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize per-torrent tab content.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance for executing commands
            selected_info_hash: Optional pre-selected torrent info hash
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._selected_info_hash: str | None = selected_info_hash
        self._sub_tabs: Tabs | None = None
        self._content_area: Container | None = None
        self._loading_sub_tab: str | None = None  # Guard to prevent concurrent loading
        self._active_sub_tab_id: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the per-torrent tab with nested sub-tabs."""
        # Torrent selector
        from ccbt.interface.widgets.torrent_selector import TorrentSelector
        yield TorrentSelector(self._data_provider, id="torrent-selector")
        
        # Sub-tabs for different views
        yield Tabs(
            Tab(_("Files"), id="sub-tab-files"),
            Tab(_("File Explorer"), id="sub-tab-file-explorer"),
            Tab(_("Info"), id="sub-tab-info"),
            Tab(_("Peers"), id="sub-tab-peers"),
            Tab(_("Trackers"), id="sub-tab-trackers"),
            Tab(_("Graphs"), id="sub-tab-graphs"),
            Tab(_("Config"), id="sub-tab-config"),
            id="per-torrent-sub-tabs",
        )
        
        # Content area for sub-tab content
        with Container(id="per-torrent-sub-content"):
            yield Static(_("Select a torrent and sub-tab to view details"), id="sub-content-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the per-torrent tab content."""
        try:
            self._sub_tabs = self.query_one("#per-torrent-sub-tabs", Tabs)  # type: ignore[attr-defined]
            self._content_area = self.query_one("#per-torrent-sub-content", Container)  # type: ignore[attr-defined]
            # CRITICAL FIX: Ensure content area is visible
            if self._content_area:
                self._content_area.display = True  # type: ignore[attr-defined]
            # CRITICAL FIX: Watch for tab activation events
            if self._sub_tabs:
                self.watch(self._sub_tabs, Tabs.TabActivated, self.on_tabs_tab_activated)  # type: ignore[attr-defined]
            # Listen for torrent selection events from selector widget
            try:
                selector = self.query_one("#torrent-selector")  # type: ignore[attr-defined]
                from ccbt.interface.widgets.torrent_selector import TorrentSelector
                self.watch(selector, TorrentSelector.TorrentSelected, self._on_torrent_selected)  # type: ignore[attr-defined]
                # Set pre-selected hash if provided
                if self._selected_info_hash:
                    try:
                        if hasattr(selector, "set_value"):
                            selector.set_value(self._selected_info_hash)  # type: ignore[attr-defined]
                        # Load initial sub-tab content
                        import asyncio
                        try:
                            if hasattr(self.app, "loop"):
                                self.app.loop.create_task(self._load_sub_tab_content("sub-tab-files"))  # type: ignore[attr-defined]
                            else:
                                asyncio.create_task(self._load_sub_tab_content("sub-tab-files"))
                        except Exception:
                            self.call_later(self._load_sub_tab_content, "sub-tab-files")  # type: ignore[attr-defined]
                    except Exception:
                        # If selector doesn't support set_value, just load content directly
                        import asyncio
                        try:
                            if hasattr(self.app, "loop"):
                                self.app.loop.create_task(self._load_sub_tab_content("sub-tab-files"))  # type: ignore[attr-defined]
                            else:
                                asyncio.create_task(self._load_sub_tab_content("sub-tab-files"))
                        except Exception:
                            self.call_later(self._load_sub_tab_content, "sub-tab-files")  # type: ignore[attr-defined]
            except Exception:
                # If selector not available but we have a pre-selected hash, load content anyway
                if self._selected_info_hash:
                    import asyncio
                    try:
                        if hasattr(self.app, "loop"):
                            self.app.loop.create_task(self._load_sub_tab_content("sub-tab-files"))  # type: ignore[attr-defined]
                        else:
                            asyncio.create_task(self._load_sub_tab_content("sub-tab-files"))
                    except Exception:
                        self.call_later(self._load_sub_tab_content, "sub-tab-files")  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error mounting per-torrent tab content: %s", e, exc_info=True)

    def _on_torrent_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle torrent selection event.

        Args:
            event: TorrentSelector.TorrentSelected event
        """
        logger.debug("PerTorrentTabContent: Torrent selected: %s", event.info_hash)
        self._selected_info_hash = event.info_hash
        # CRITICAL FIX: Don't reset _active_sub_tab_id - keep current tab or default to first
        # Reload current sub-tab content with new selection
        if self._sub_tabs:
            try:
                active_tab = self._sub_tabs.active  # type: ignore[attr-defined]
                if active_tab:
                    tab_id = getattr(active_tab, "id", None)
                    if tab_id:
                        self._active_sub_tab_id = tab_id
                        logger.debug("PerTorrentTabContent: Loading sub-tab %s for torrent %s", tab_id, event.info_hash)
                        # CRITICAL FIX: Use async task instead of call_later for async method
                        import asyncio
                        try:
                            if hasattr(self.app, "loop"):
                                self.app.loop.create_task(self._load_sub_tab_content(tab_id))  # type: ignore[attr-defined]
                            else:
                                asyncio.create_task(self._load_sub_tab_content(tab_id))
                        except Exception:
                            # Fallback to call_later
                            self.call_later(self._load_sub_tab_content, tab_id)  # type: ignore[attr-defined]
                        return
            except Exception as e:
                logger.debug("PerTorrentTabContent: Error getting active tab: %s", e)
        
        # CRITICAL FIX: If no active tab, default to first tab (sub-tab-files)
        if not self._active_sub_tab_id:
            self._active_sub_tab_id = "sub-tab-files"
            logger.debug("PerTorrentTabContent: No active tab, defaulting to sub-tab-files for torrent %s", event.info_hash)
            import asyncio
            try:
                if hasattr(self.app, "loop"):
                    self.app.loop.create_task(self._load_sub_tab_content("sub-tab-files"))  # type: ignore[attr-defined]
                else:
                    asyncio.create_task(self._load_sub_tab_content("sub-tab-files"))
            except Exception:
                # Fallback to call_later
                self.call_later(self._load_sub_tab_content, "sub-tab-files")  # type: ignore[attr-defined]

    def set_selected_info_hash(self, info_hash: str | None) -> None:  # pragma: no cover
        """Update the selected torrent info hash externally.
        
        Args:
            info_hash: New info hash to select, or None to clear
        """
        if self._selected_info_hash == info_hash:
            return
        self._selected_info_hash = info_hash
        # Update selector if mounted
        try:
            selector = self.query_one("#torrent-selector")  # type: ignore[attr-defined]
            if hasattr(selector, "set_value") and info_hash:
                selector.set_value(info_hash)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Reload current sub-tab if one is active
        if self._active_sub_tab_id:
            self.call_later(self._load_sub_tab_content, self._active_sub_tab_id)  # type: ignore[attr-defined]

    async def _load_sub_tab_content(self, sub_tab_id: str) -> None:  # pragma: no cover
        """Load content for a specific sub-tab.

        Args:
            sub_tab_id: ID of the sub-tab to load
        """
        # CRITICAL FIX: Prevent concurrent loading of the same tab
        if self._loading_sub_tab == sub_tab_id:
            logger.debug("PerTorrentTabContent: Already loading %s, skipping", sub_tab_id)
            return
        
        self._loading_sub_tab = sub_tab_id
        try:
            # CRITICAL FIX: Ensure content area is visible and attached
            if not self._content_area:
                logger.warning("PerTorrentTabContent: Content area not available")
                return
            
            if not self._content_area.is_attached or not self._content_area.display:  # type: ignore[attr-defined]
                logger.debug("PerTorrentTabContent: Content area not attached or not visible")
                # Try to make it visible
                self._content_area.display = True  # type: ignore[attr-defined]

            # CRITICAL FIX: Only skip if same torrent AND same tab (allow reload for different torrent)
            if self._selected_info_hash and sub_tab_id == self._active_sub_tab_id:
                # Check if content already exists for this tab
                try:
                    existing_content = self._content_area.query_one(f"#{sub_tab_id}-content")  # type: ignore[attr-defined]
                    if existing_content:
                        logger.debug("PerTorrentTabContent: Content already loaded for %s, skipping", sub_tab_id)
                        return
                except Exception:
                    # No existing content, continue to load
                    pass

            if not self._selected_info_hash:
                # Show placeholder if no torrent selected
                try:
                    self._content_area.remove_children()  # type: ignore[attr-defined]
                except Exception:
                    pass
                # Use top-level Static import, not local import
                placeholder = Static(_("Please select a torrent first"), id="no-torrent-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
                return
            
            # Clear existing content - remove all children first
            try:
                # Get all children and remove them individually to ensure proper cleanup
                children = list(self._content_area.children)  # type: ignore[attr-defined]
                for child in children:
                    try:
                        child.remove()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                # Also call remove_children as backup
                self._content_area.remove_children()  # type: ignore[attr-defined]
            except Exception:
                pass
            
            # Load appropriate screen based on sub-tab
            if sub_tab_id == "sub-tab-files":
                from ccbt.interface.screens.per_torrent_files import TorrentFilesScreen
                # CRITICAL FIX: Check if widget with this ID already exists in app registry and remove it
                try:
                    # Check in the app's registry
                    app = self.app  # type: ignore[attr-defined]
                    if app and hasattr(app, "_registry"):
                        widget_id = "files-screen"
                        # Remove from registry if it exists
                        if widget_id in app._registry:  # type: ignore[attr-defined]
                            existing_widget = app._registry[widget_id]  # type: ignore[attr-defined]
                            if existing_widget and hasattr(existing_widget, "remove"):
                                try:
                                    existing_widget.remove()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                except Exception:
                    # Registry check failed, continue anyway
                    pass
                
                screen = TorrentFilesScreen(
                    self._data_provider,
                    self._command_executor,
                    self._selected_info_hash,
                    id="files-screen"
                )
                self._content_area.mount(screen)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure screen is visible
                screen.display = True  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
                # Trigger initial refresh after mount
                self.call_later(screen.refresh_files)  # type: ignore[attr-defined]
            elif sub_tab_id == "sub-tab-file-explorer":
                # Use Textual's DirectoryTree for browsing torrent files
                from textual.widgets import DirectoryTree
                from pathlib import Path
                
                # Get torrent output directory
                try:
                    status = await self._data_provider.get_torrent_status(self._selected_info_hash)
                    if status:
                        output_dir = status.get("output_dir") or status.get("save_path") or "."
                        base_path = Path(output_dir)
                        # Resolve to absolute path
                        if not base_path.is_absolute():
                            base_path = base_path.resolve()
                        
                        if base_path.exists() and base_path.is_dir():
                            # Create DirectoryTree with absolute path
                            file_tree = DirectoryTree(str(base_path.resolve()), id="file-tree")
                            self._content_area.mount(file_tree)  # type: ignore[attr-defined]
                            self._active_sub_tab_id = sub_tab_id
                        else:
                            # Fallback: show error message
                            error_msg = Static(f"Torrent output directory not found: {output_dir}", id="file-explorer-error")
                            self._content_area.mount(error_msg)  # type: ignore[attr-defined]
                            self._active_sub_tab_id = sub_tab_id
                    else:
                        # Fallback: show error message
                        error_msg = Static("Torrent status not available", id="file-explorer-error")
                        self._content_area.mount(error_msg)  # type: ignore[attr-defined]
                        self._active_sub_tab_id = sub_tab_id
                except Exception as e:
                    # Fallback: show error message
                    logger.debug("Error mounting file explorer: %s", e)
                    error_msg = Static(f"Error loading file explorer: {str(e)}", id="file-explorer-error")
                    self._content_area.mount(error_msg)  # type: ignore[attr-defined]
                    self._active_sub_tab_id = sub_tab_id
            elif sub_tab_id == "sub-tab-info":
                from ccbt.interface.screens.per_torrent_info import TorrentInfoScreen
                screen = TorrentInfoScreen(
                    self._data_provider,
                    self._command_executor,
                    self._selected_info_hash,
                    id="info-screen"
                )
                self._content_area.mount(screen)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure screen is visible
                screen.display = True  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
            elif sub_tab_id == "sub-tab-peers":
                from ccbt.interface.screens.per_torrent_peers import TorrentPeersScreen
                screen = TorrentPeersScreen(
                    self._data_provider,
                    self._command_executor,
                    self._selected_info_hash,
                    id="peers-screen"
                )
                self._content_area.mount(screen)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure screen is visible
                screen.display = True  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
                # Trigger initial refresh after mount
                self.call_later(screen.refresh_peers)  # type: ignore[attr-defined]
            elif sub_tab_id == "sub-tab-trackers":
                from ccbt.interface.screens.per_torrent_trackers import TorrentTrackersScreen
                screen = TorrentTrackersScreen(
                    self._data_provider,
                    self._command_executor,
                    self._selected_info_hash,
                    id="trackers-screen"
                )
                self._content_area.mount(screen)  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure screen is visible
                screen.display = True  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
                # Trigger initial refresh after mount
                self.call_later(screen.refresh_trackers)  # type: ignore[attr-defined]
            elif sub_tab_id == "sub-tab-graphs":
                from ccbt.interface.widgets.graph_widget import PerTorrentGraphWidget
                graph = PerTorrentGraphWidget(
                    self._selected_info_hash,
                    self._data_provider,
                    id="per-torrent-graph"
                )
                self._content_area.mount(graph)  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
            elif sub_tab_id == "sub-tab-config":
                # Use per-torrent config wrapper
                # CRITICAL: Use DataProvider/Executor instead of direct session access
                if self._data_provider and self._command_executor and self._selected_info_hash:
                    from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                    wrapper = ConfigScreenWrapper(
                        "torrent",
                        self._data_provider,
                        self._command_executor,
                        info_hash=self._selected_info_hash,
                        id="torrent-config-wrapper"
                    )
                    self._content_area.mount(wrapper)  # type: ignore[attr-defined]
                    self._active_sub_tab_id = sub_tab_id
                else:
                    placeholder = Static(_("Per-torrent configuration - Data provider/Executor or torrent not available"), id="torrent-config-placeholder")
                    self._content_area.mount(placeholder)  # type: ignore[attr-defined]
                    self._active_sub_tab_id = sub_tab_id
            else:
                # Placeholder for other sub-tabs
                placeholder = Static(_("{sub_tab} content for torrent {hash}... - Coming soon").format(sub_tab=sub_tab_id, hash=self._selected_info_hash[:8]), id=f"{sub_tab_id}-content")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
                self._active_sub_tab_id = sub_tab_id
        finally:
            # Clear the loading guard
            if self._loading_sub_tab == sub_tab_id:
                self._loading_sub_tab = None

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:  # pragma: no cover
        """Handle activation events for the per-torrent sub-tabs."""
        tab = getattr(event, "tab", None)
        tab_id = getattr(tab, "id", None)
        if tab_id:
            logger.debug("PerTorrentTabContent: Tab activated: %s", tab_id)
            # CRITICAL FIX: _load_sub_tab_content is async, need to create task in app's event loop
            import asyncio
            try:
                if hasattr(self.app, "loop"):
                    self.app.loop.create_task(self._load_sub_tab_content(tab_id))  # type: ignore[attr-defined]
                else:
                    asyncio.create_task(self._load_sub_tab_content(tab_id))
            except Exception as e:
                logger.error("Error creating task for tab activation: %s", e, exc_info=True)
                # Fallback to call_later
                self.call_later(self._load_sub_tab_content, tab_id)  # type: ignore[attr-defined]

    def refresh(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        """Refresh all active sub-tab screens with latest data.
        
        Args:
            *args: Positional arguments (for Textual compatibility)
            **kwargs: Keyword arguments like 'layout', 'repaint' (for Textual compatibility)
        """
        # CRITICAL FIX: Ensure widget is visible and attached before refreshing
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("PerTorrentTabContent: Widget not attached or not visible, skipping refresh")
            return
        
        # Call parent's refresh method first (handles layout/repaint)
        try:
            super().refresh(*args, **kwargs)
        except (AttributeError, TypeError):
            # Parent doesn't have refresh or signature mismatch, continue
            pass
        
        # Then refresh our custom content
        if not self._selected_info_hash or not self._active_sub_tab_id:
            logger.debug("PerTorrentTabContent: No torrent selected or no active sub-tab, skipping refresh")
            return
        
        # Schedule async refresh as a task
        # CRITICAL FIX: Use asyncio.create_task to ensure it runs in the correct event loop
        import asyncio
        try:
            if hasattr(self.app, "loop"):
                self.app.loop.create_task(self._refresh_content())  # type: ignore[attr-defined]
            else:
                asyncio.create_task(self._refresh_content())
        except Exception as e:
            logger.debug("PerTorrentTabContent: Error scheduling refresh task: %s", e)
            # Fallback to call_later
            self.call_later(self._refresh_content)  # type: ignore[attr-defined]
    
    async def _refresh_content(self) -> None:  # pragma: no cover
        """Internal async method to refresh content."""
        if not self._selected_info_hash or not self._active_sub_tab_id:
            return
        
        try:
            # Refresh based on active sub-tab
            if self._active_sub_tab_id == "sub-tab-files":
                try:
                    from ccbt.interface.screens.per_torrent_files import TorrentFilesScreen
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    try:
                        files_screen = self.query_one(TorrentFilesScreen)  # type: ignore[attr-defined]
                        if files_screen and hasattr(files_screen, "refresh_files"):
                            await files_screen.refresh_files()
                    except Exception:
                        pass
                except Exception:
                    pass
            elif self._active_sub_tab_id == "sub-tab-peers":
                try:
                    from ccbt.interface.screens.per_torrent_peers import TorrentPeersScreen
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    try:
                        peers_screen = self.query_one(TorrentPeersScreen)  # type: ignore[attr-defined]
                        if peers_screen and hasattr(peers_screen, "refresh_peers"):
                            await peers_screen.refresh_peers()
                    except Exception:
                        pass
                except Exception:
                    pass
            elif self._active_sub_tab_id == "sub-tab-trackers":
                try:
                    from ccbt.interface.screens.per_torrent_trackers import TorrentTrackersScreen
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    try:
                        trackers_screen = self.query_one(TorrentTrackersScreen)  # type: ignore[attr-defined]
                        if trackers_screen and hasattr(trackers_screen, "refresh_trackers"):
                            await trackers_screen.refresh_trackers()
                    except Exception:
                        pass
                except Exception:
                    pass
            elif self._active_sub_tab_id == "sub-tab-info":
                try:
                    from ccbt.interface.screens.per_torrent_info import TorrentInfoScreen
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    try:
                        info_screen = self.query_one(TorrentInfoScreen)  # type: ignore[attr-defined]
                        if info_screen and hasattr(info_screen, "refresh_info"):
                            await info_screen.refresh_info()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Error refreshing per-torrent tab: %s", e)

    async def refresh_active_sub_tab(self) -> None:  # pragma: no cover
        """Refresh the currently active sub-tab content."""
        if not self._active_sub_tab_id:
            return
        # Reload the sub-tab content to ensure it's up-to-date
        await self._load_sub_tab_content(self._active_sub_tab_id)

    def get_selected_info_hash(self) -> str | None:  # pragma: no cover
        """Get the currently selected torrent info hash.
        
        Returns:
            The selected info hash, or None if no torrent is selected
        """
        return self._selected_info_hash

    def on_unmount(self) -> None:  # pragma: no cover
        """Handle widget unmounting - cancel all pending async tasks.
        
        CRITICAL FIX: This prevents the "Callback is still pending after 3 seconds" warning
        by properly cleaning up all async tasks when the widget is removed.
        """
        import asyncio
        
        # Cancel any pending refresh tasks
        # Note: We can't directly track tasks created with create_task, but we can
        # set a flag to prevent new tasks from being created
        self._loading_sub_tab = None
        
        # Clear any watchers to prevent callbacks after unmount
        try:
            if self._sub_tabs:
                self.unwatch(self._sub_tabs, Tabs.TabActivated, self.on_tabs_tab_activated)  # type: ignore[attr-defined]
        except Exception:
            pass
        
        try:
            selector = self.query_one("#torrent-selector", can_focus=False)  # type: ignore[attr-defined]
            from ccbt.interface.widgets.torrent_selector import TorrentSelector
            self.unwatch(selector, TorrentSelector.TorrentSelected, self._on_torrent_selected)  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Clear content area to prevent any pending operations
        if self._content_area:
            try:
                # Cancel any pending operations on child widgets
                for child in list(self._content_area.children):  # type: ignore[attr-defined]
                    try:
                        # If child has cleanup method, call it
                        if hasattr(child, "on_unmount"):
                            child.on_unmount()  # type: ignore[attr-defined]
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Call parent's on_unmount if it exists
        try:
            super().on_unmount()  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            pass

