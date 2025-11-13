"""Base screen classes for the terminal dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.screen import ModalScreen, Screen
    from textual.widgets import Button, Static

    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from textual.screen import ModalScreen, Screen
        from textual.widgets import Button, Static
    except ImportError:
        # Fallback for when textual is not available
        class Screen:  # type: ignore[no-redef]
            pass

        class ModalScreen:  # type: ignore[no-redef]
            pass

        class Button:  # type: ignore[no-redef]
            pass

        class Static:  # type: ignore[no-redef]
            pass


try:
    from textual.app import ComposeResult
    from textual.containers import (
        Container,
        Horizontal,
    )
except ImportError:
    from typing import Any as ComposeResult  # type: ignore[assignment, misc]

    Container = None  # type: ignore[assignment, misc]
    Horizontal = None  # type: ignore[assignment, misc]

from ccbt.monitoring import get_alert_manager, get_metrics_collector
from ccbt.plugins import get_plugin_manager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager


class ConfigScreen(Screen):  # type: ignore[misc]
    """Base class for configuration screens with common navigation."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, session: AsyncSessionManager, *args: Any, **kwargs: Any):
        """Initialize configuration screen."""
        super().__init__(*args, **kwargs)
        self.session = session
        self.config_manager = session.config if hasattr(session, "config") else None
        self._has_unsaved_changes = False

    async def action_back(self) -> None:  # pragma: no cover
        """Navigate back to previous screen."""
        # Check for unsaved changes (either flag or actual value comparison)
        has_changes = self._has_unsaved_changes
        if hasattr(self, "_check_unsaved_changes"):
            has_changes = has_changes or self._check_unsaved_changes()

        if has_changes:
            # Show confirmation dialog
            dialog = ConfirmationDialog(
                "You have unsaved changes. Are you sure you want to go back?",
            )
            result = await self.app.push_screen(dialog)  # type: ignore[attr-defined]
            if not result:
                # User cancelled, stay on screen
                return
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def action_quit(self) -> None:  # pragma: no cover
        """Quit the configuration screen."""
        await self.action_back()


class ConfirmationDialog(ModalScreen):  # type: ignore[misc]
    """Modal dialog for confirmation prompts."""

    DEFAULT_CSS = """
    ConfirmationDialog {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
    }
    #message {
        height: auto;
        margin: 1;
    }
    #buttons {
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, message: str, *args: Any, **kwargs: Any):
        """Initialize confirmation dialog.

        Args:
            message: Message to display
        """
        super().__init__(*args, **kwargs)
        self.message = message
        self.result: bool | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the confirmation dialog."""
        yield Container(
            Static(self.message, id="message"),
            Horizontal(
                Button("Yes", id="yes", variant="primary"),
                Button("No", id="no", variant="default"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "yes":
            self.result = True
        elif event.button.id == "no":
            self.result = False
        self.dismiss(self.result)  # type: ignore[attr-defined]

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("y", "yes", "Yes"),
        ("n", "no", "No"),
        ("escape", "no", "No"),
    ]

    async def action_yes(self) -> None:  # pragma: no cover
        """Confirm action."""
        self.result = True
        self.dismiss(True)  # type: ignore[attr-defined]

    async def action_no(self) -> None:  # pragma: no cover
        """Cancel action."""
        self.result = False
        self.dismiss(False)  # type: ignore[attr-defined]


class GlobalConfigScreen(ConfigScreen):  # type: ignore[misc]
    """Base class for global configuration screens."""


class PerTorrentConfigScreen(ConfigScreen):  # type: ignore[misc]
    """Base class for per-torrent configuration screens."""


class MonitoringScreen(Screen):  # type: ignore[misc]
    """Base class for monitoring screens with common functionality."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        refresh_interval: float = 2.0,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize monitoring screen.

        Args:
            session: AsyncSessionManager instance (can be DaemonInterfaceAdapter)
            refresh_interval: Refresh interval in seconds (default 2.0)
        """
        super().__init__(*args, **kwargs)
        self.session = session
        
        # Detect if using DaemonInterfaceAdapter
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        self._is_daemon_session = isinstance(session, DaemonInterfaceAdapter)
        
        # Adjust refresh interval for daemon sessions (WebSocket provides real-time updates)
        if self._is_daemon_session:
            # Use longer refresh interval for daemon (WebSocket handles real-time updates)
            self.refresh_interval = max(3.0, float(refresh_interval) * 1.5)
        else:
            self.refresh_interval = max(0.5, float(refresh_interval))
        
        self.metrics_collector = get_metrics_collector()
        self.alert_manager = get_alert_manager()
        self.plugin_manager = get_plugin_manager()
        self._refresh_task: asyncio.Task | None = None
        self._refresh_interval_id: Any | None = None
        # Command executor for executing CLI commands (will be set in on_mount to avoid circular import)
        self._command_executor: Any | None = None
        # Status bar reference (will be set in on_mount if available)
        self.statusbar: Static | None = None

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and start refresh interval."""
        # Initialize command executor (import here to avoid circular import)
        if self._command_executor is None:
            # Import CommandExecutor from commands module
            try:
                from ccbt.interface.commands.executor import CommandExecutor

                self._command_executor = CommandExecutor(self.session)
            except ImportError:
                # CommandExecutor not yet extracted, will be set later
                pass
        # Try to get statusbar reference if available
        try:
            self.statusbar = self.query_one("#statusbar", Static)
        except Exception:
            # Statusbar not available, try to get from app if it's TerminalDashboard
            try:
                app = self.app
                if hasattr(app, "statusbar"):
                    self.statusbar = app.statusbar
            except Exception:
                pass
        # Initial data load
        await self._refresh_data()

        # Set up periodic refresh
        self._refresh_interval_id = self.set_interval(
            self.refresh_interval, self._schedule_refresh
        )

    async def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the screen and stop refresh."""
        if self._refresh_interval_id:
            self._refresh_interval_id.stop()  # type: ignore[attr-defined]
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task

    def _schedule_refresh(self) -> None:  # pragma: no cover
        """Schedule a data refresh."""
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(self._refresh_data())

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh screen data. Override in subclasses."""
        # Default implementation does nothing
    
    def _get_cached_status(self) -> dict[str, Any]:
        """Get cached status from DaemonInterfaceAdapter if available.
        
        Returns:
            Cached status dict, or empty dict if not using DaemonInterfaceAdapter
        """
        if self._is_daemon_session:
            # Access cached status from DaemonInterfaceAdapter
            if hasattr(self.session, "_cached_torrents"):
                # Return a copy to avoid modification
                import asyncio
                try:
                    # Try to get cached status synchronously (if lock is not held)
                    if hasattr(self.session, "_cache_lock"):
                        # For async access, we'd need to await, but this is called from sync context
                        # Return empty dict and let async refresh handle it
                        return {}
                except Exception:
                    pass
        return {}

    async def action_back(self) -> None:  # pragma: no cover
        """Navigate back to previous screen."""
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def action_quit(self) -> None:  # pragma: no cover
        """Quit the monitoring screen."""
        await self.action_back()

    def _get_metrics_plugin(self) -> Any | None:  # pragma: no cover
        """Get MetricsPlugin instance if available.

        Tries multiple methods:
        1. PluginManager.get_plugin() with various name variations
        2. Event bus handlers (MetricsPlugin's collector)
        3. Session plugins attribute (if exists)
        4. Direct import and instantiation check

        Returns:
            MetricsPlugin instance if found and running, None otherwise
        """
        try:
            # Method 1: Try PluginManager with various name patterns
            if self.plugin_manager:
                # Try different possible names
                for name in [
                    "MetricsPlugin",
                    "metrics_plugin",
                    "MetricsCollector",
                    "metrics",
                ]:
                    plugin = self.plugin_manager.get_plugin(name)
                    if plugin:
                        # Verify it's a MetricsPlugin by checking for required methods
                        if (
                            hasattr(plugin, "get_aggregates")
                            and hasattr(plugin, "get_metrics")
                            and hasattr(plugin, "collector")
                        ):
                            # Check if plugin is running (state check)
                            if hasattr(plugin, "state"):
                                from ccbt.plugins.base import PluginState

                                if plugin.state == PluginState.RUNNING:
                                    return plugin
                            elif plugin.collector is not None:
                                # If no state attribute, check collector exists
                                return plugin

            # Method 2: Try via event bus handlers
            from ccbt.utils.events import get_event_bus

            event_bus = get_event_bus()
            handlers = getattr(event_bus, "_handlers", {})
            for handler_list in handlers.values():
                for handler in handler_list:
                    if hasattr(handler, "name") and handler.name == "metrics_collector":
                        # Found MetricsPlugin's collector (EventHandler)
                        # Check plugin manager for plugin with this collector
                        if self.plugin_manager:
                            for plugin in self.plugin_manager.plugins.values():
                                if (
                                    hasattr(plugin, "collector")
                                    and plugin.collector == handler
                                    and hasattr(plugin, "get_aggregates")
                                ):
                                    return plugin

            # Method 3: Check session for plugins attribute
            if hasattr(self.session, "plugins"):
                plugins = getattr(self.session, "plugins", [])
                if isinstance(plugins, (list, dict)):
                    if isinstance(plugins, dict):
                        plugins = list(plugins.values())
                    for plugin in plugins:
                        if (
                            hasattr(plugin, "name")
                            and plugin.name
                            in ("metrics_plugin", "MetricsPlugin", "metrics")
                            and hasattr(plugin, "collector")
                            and hasattr(plugin, "get_aggregates")
                        ):
                            return plugin

            # Method 4: Try to find by iterating all plugins and checking type
            if self.plugin_manager:
                try:
                    from ccbt.plugins.metrics_plugin import MetricsPlugin

                    for plugin in self.plugin_manager.plugins.values():
                        if isinstance(plugin, MetricsPlugin):
                            if hasattr(plugin, "state"):
                                from ccbt.plugins.base import PluginState

                                if plugin.state == PluginState.RUNNING:
                                    return plugin
                            elif (
                                hasattr(plugin, "collector")
                                and plugin.collector is not None
                            ):
                                return plugin
                except ImportError:
                    pass  # MetricsPlugin not available

            return None
        except Exception:
            return None

    def get_metrics_plugin_aggregates(self) -> dict[str, Any]:  # pragma: no cover
        """Get metrics aggregates from MetricsPlugin if available.

        Returns:
            Dictionary of metric aggregates, empty dict if plugin not available
        """
        plugin = self._get_metrics_plugin()
        if plugin and hasattr(plugin, "get_aggregates"):
            try:
                aggregates = plugin.get_aggregates()
                # Convert to dict format for easier consumption
                result = {}
                for agg in aggregates:
                    if hasattr(agg, "name"):
                        result[agg.name] = {
                            "count": getattr(agg, "count", 0),
                            "sum": getattr(agg, "sum", 0.0),
                            "min": getattr(agg, "min", 0.0),
                            "max": getattr(agg, "max", 0.0),
                            "avg": getattr(agg, "avg", 0.0),
                            "unit": getattr(agg, "unit", ""),
                            "tags": getattr(agg, "tags", {}),
                        }
                return result
            except Exception:
                return {}
        return {}

    def get_metrics_plugin_stats(self) -> dict[str, Any]:  # pragma: no cover
        """Get MetricsPlugin statistics if available.

        Returns:
            Dictionary with plugin stats, empty dict if plugin not available
        """
        plugin = self._get_metrics_plugin()
        if plugin and hasattr(plugin, "get_stats"):
            try:
                return plugin.get_stats()
            except Exception:
                return {}
        return {}
