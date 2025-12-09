"""Preferences tab screen implementation.

Implements the Preferences tab with nested sub-tabs for configuration options.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container
    from textual.widgets import Static, Tabs, Tab
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Tabs:  # type: ignore[no-redef]
        pass

    class Tab:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class PreferencesTabContent(Container):  # type: ignore[misc]
    """Main content container for Preferences tab with nested sub-tabs."""

    DEFAULT_CSS = """
    PreferencesTabContent {
        height: 1fr;
        layout: vertical;
    }
    
    #preferences-sub-tabs {
        height: auto;
        min-height: 3;
    }
    
    #preferences-sub-content {
        height: 1fr;
    }
    """

    def __init__(
        self,
        command_executor: CommandExecutor,
        session: Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize preferences tab content.

        Args:
            command_executor: CommandExecutor instance for executing commands
            session: Optional session instance (will be retrieved from app if not provided)
        """
        super().__init__(*args, **kwargs)
        self._command_executor = command_executor
        self._session = session
        self._sub_tabs: Tabs | None = None
        self._content_area: Container | None = None
        self._active_sub_tab_id: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the preferences tab with nested sub-tabs."""
        # Sub-tabs for different configuration categories
        yield Tabs(
            Tab(_("General"), id="sub-tab-general"),
            Tab(_("Network"), id="sub-tab-network"),
            Tab(_("Bandwidth"), id="sub-tab-bandwidth"),
            Tab(_("Storage"), id="sub-tab-storage"),
            Tab(_("Security"), id="sub-tab-security"),
            Tab(_("Advanced"), id="sub-tab-advanced"),
            id="preferences-sub-tabs",
        )
        
        # Content area for sub-tab content
        with Container(id="preferences-sub-content"):
            yield Static(_("Select a sub-tab to view configuration options"), id="sub-content-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the preferences tab content."""
        try:
            self._sub_tabs = self.query_one("#preferences-sub-tabs", Tabs)  # type: ignore[attr-defined]
            self._content_area = self.query_one("#preferences-sub-content", Container)  # type: ignore[attr-defined]
            # Load initial content for first tab
            self._load_sub_tab_content("sub-tab-general")
        except Exception as e:
            logger.debug("Error mounting preferences tab content: %s", e)

    def _load_sub_tab_content(self, sub_tab_id: str) -> None:  # pragma: no cover
        """Load content for a specific sub-tab.

        Args:
            sub_tab_id: ID of the sub-tab to load
        """
        if not self._content_area:
            return
        if sub_tab_id == self._active_sub_tab_id:
            return
        
        # Clear existing content
        try:
            self._content_area.remove_children()  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Get data provider and command executor from parent (TerminalDashboard or MainTabsContainer)
        data_provider = None
        command_executor = None
        try:
            app = self.app  # type: ignore[attr-defined]
            if hasattr(app, "_data_provider"):
                data_provider = app._data_provider  # type: ignore[attr-defined]
            if hasattr(app, "_command_executor"):
                command_executor = app._command_executor  # type: ignore[attr-defined]
            # Also check parent container (MainTabsContainer)
            if not data_provider or not command_executor:
                parent = self.parent  # type: ignore[attr-defined]
                if parent and hasattr(parent, "_data_provider"):
                    data_provider = parent._data_provider  # type: ignore[attr-defined]
                if parent and hasattr(parent, "_command_executor"):
                    command_executor = parent._command_executor  # type: ignore[attr-defined]
        except Exception:
            pass
        
        # Load appropriate screen based on sub-tab
        if sub_tab_id == "sub-tab-general":
            # General tab: Show language selector and global config
            if data_provider and command_executor:
                from ccbt.interface.widgets.language_selector import LanguageSelectorWidget
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                
                # Language selector at top
                lang_selector = LanguageSelectorWidget(
                    data_provider,
                    command_executor,
                    id="language-selector"
                )
                self._content_area.mount(lang_selector)  # type: ignore[attr-defined]
                
                # Global config wrapper below
                wrapper = ConfigScreenWrapper(
                    "global",
                    data_provider,
                    command_executor,
                    id="global-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("General configuration - Data provider/Executor not available"), id="general-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-network":
            if data_provider and command_executor:
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                wrapper = ConfigScreenWrapper(
                    "network",
                    data_provider,
                    command_executor,
                    id="network-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Network configuration - Data provider/Executor not available"), id="network-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-bandwidth":
            if data_provider and command_executor:
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                wrapper = ConfigScreenWrapper(
                    "bandwidth",
                    data_provider,
                    command_executor,
                    id="bandwidth-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Bandwidth configuration - Data provider/Executor not available"), id="bandwidth-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-storage":
            if data_provider and command_executor:
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                wrapper = ConfigScreenWrapper(
                    "storage",
                    data_provider,
                    command_executor,
                    id="storage-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Storage configuration - Data provider/Executor not available"), id="storage-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-security":
            if data_provider and command_executor:
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                wrapper = ConfigScreenWrapper(
                    "security",
                    data_provider,
                    command_executor,
                    id="security-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Security configuration - Data provider/Executor not available"), id="security-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        elif sub_tab_id == "sub-tab-advanced":
            if data_provider and command_executor:
                from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
                wrapper = ConfigScreenWrapper(
                    "advanced",
                    data_provider,
                    command_executor,
                    id="advanced-config-wrapper"
                )
                self._content_area.mount(wrapper)  # type: ignore[attr-defined]
            else:
                placeholder = Static(_("Advanced configuration - Data provider/Executor not available"), id="advanced-config-placeholder")
                self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id
        else:
            placeholder = Static(_("{sub_tab} configuration - Coming soon").format(sub_tab=sub_tab_id), id=f"{sub_tab_id}-content")
            self._content_area.mount(placeholder)  # type: ignore[attr-defined]
            self._active_sub_tab_id = sub_tab_id

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:  # pragma: no cover
        """Handle activation events for preferences sub-tabs."""
        tab = getattr(event, "tab", None)
        tab_id = getattr(tab, "id", None)
        if tab_id:
            self._load_sub_tab_content(tab_id)

