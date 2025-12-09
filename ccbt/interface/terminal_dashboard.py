"""Textual-based terminal dashboard for ccBitTorrent.

Provides a live view of global session stats and per-torrent status.

"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if (
    TYPE_CHECKING
):  # pragma: no cover - TYPE_CHECKING block, only evaluated by type checkers
    from textual import (
        events,  # pragma: no cover - TYPE_CHECKING import
    )
    from textual.app import App  # pragma: no cover - TYPE_CHECKING import
    from textual.widgets import Static  # pragma: no cover - TYPE_CHECKING import
else:
    # Runtime imports - textual may not be available
    try:
        from textual.app import App
        from textual.widgets import Static
    except ImportError:  # pragma: no cover - Import error fallback when textual unavailable, difficult to test without breaking imports
        # Fallback classes for when textual is not available
        class App:  # type: ignore[misc]  # pragma: no cover - Fallback class definition
            """Fallback App class when textual is not available."""

        class Static:  # type: ignore[misc]  # pragma: no cover - Fallback class definition
            """Fallback Static class when textual is not available."""


from rich.panel import Panel
from rich.table import Table

from ccbt.config.config import get_config, set_config
from ccbt.i18n import _
from ccbt.i18n.manager import TranslationManager
from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import (
    ConfigScreen,
    ConfirmationDialog,
    GlobalConfigScreen,
    MonitoringScreen,
    PerTorrentConfigScreen,
)
from ccbt.interface.screens.config.global_config import (
    GlobalConfigDetailScreen,
    GlobalConfigMainScreen,
)
from ccbt.interface.screens.config.proxy import ProxyConfigScreen
from ccbt.interface.screens.config.ssl import SSLConfigScreen
from ccbt.interface.screens.config.torrent_config import (
    PerTorrentConfigMainScreen,
    TorrentConfigDetailScreen,
)
from ccbt.interface.screens.config.utp import UTPConfigScreen
from ccbt.interface.screens.dialogs import AddTorrentScreen
from ccbt.interface.screens.monitoring.alerts import AlertsDashboardScreen
from ccbt.interface.screens.utility import (
    FileSelectionScreen,
    HelpScreen,
    NavigationMenuScreen,
)
from ccbt.interface.screens.file_selection_dialog import FileSelectionDialog
from ccbt.interface.screens.monitoring.disk_analysis import DiskAnalysisScreen
from ccbt.interface.screens.monitoring.disk_io import DiskIOMetricsScreen
from ccbt.interface.screens.monitoring.historical import HistoricalTrendsScreen
from ccbt.interface.screens.monitoring.ipfs import IPFSManagementScreen
from ccbt.interface.screens.monitoring.metrics_explorer import MetricsExplorerScreen
from ccbt.interface.screens.monitoring.nat import NATManagementScreen
from ccbt.interface.screens.monitoring.network import NetworkQualityScreen
from ccbt.interface.screens.monitoring.performance import PerformanceMetricsScreen
from ccbt.interface.screens.monitoring.performance_analysis import (
    PerformanceAnalysisScreen,
)
from ccbt.interface.screens.monitoring.queue import QueueMetricsScreen
from ccbt.interface.screens.monitoring.scrape import ScrapeResultsScreen
from ccbt.interface.screens.monitoring.system_resources import SystemResourcesScreen
from ccbt.interface.screens.monitoring.tracker import TrackerMetricsScreen
from ccbt.interface.screens.monitoring.xet import XetManagementScreen
from ccbt.interface.screens.monitoring.xet_folder_sync import XetFolderSyncScreen
from ccbt.interface.widgets import (
    GraphsSectionContainer,
    MainTabsContainer,
    Overview,
    PeersTable,
    SparklineGroup,
    SpeedSparklines,
    TorrentsTable,
)
from ccbt.monitoring import get_alert_manager, get_metrics_collector
from ccbt.storage.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

# Import rainbow theme
try:
    from ccbt.interface.themes.rainbow import create_rainbow_theme
except ImportError:
    # Fallback if themes module not available
    def create_rainbow_theme() -> Any:  # type: ignore[misc]
        """Fallback rainbow theme creator."""
        return None

if (
    TYPE_CHECKING
):  # pragma: no cover - TYPE_CHECKING block, only evaluated by type checkers
    from ccbt.session.session import (
        AsyncSessionManager,  # pragma: no cover - TYPE_CHECKING import
    )

try:
    from textual.app import App, ComposeResult
    from textual.containers import (
        Container,
        Horizontal,
        Vertical,
    )
    from textual.logging import TextualHandler
    from textual.screen import ModalScreen, Screen
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        RichLog,
        Select,
        Sparkline,
        Static,
        Switch,
    )

    _TEXTUAL_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when Textual isn't installed
    _TEXTUAL_AVAILABLE = False

    class _Stub:
        def __init__(self, *_args, **kwargs):
            self.id = kwargs.get("id", "")
            self.display = True

        def update(self, *args, **kwargs):
            pass

        def write(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            pass

        def add_columns(self, *args, **kwargs):
            pass

        def clear(self, *args, **kwargs):
            pass

        def focus(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class App:  # type: ignore[no-redef]
        """Application class for terminal dashboard."""

        def __init__(self, *args, **kwargs):
            """Initialize app (stub method)."""

        def run(self, *args, **kwargs):
            """Run the app (stub method)."""

        def set_interval(self, *args, **kwargs):
            """Set interval (stub method)."""

        def query_one(self, *_args, **_kwargs):
            """Query one element (stub method)."""
            return _Stub()

        def refresh(self, *args, **kwargs):
            """Refresh the app (stub method)."""

        def mount(self, *args, **kwargs):
            """Mount a widget (stub method)."""

    class ComposeResult:  # type: ignore[no-redef]
        """Result of compose operation."""

    class Container(_Stub):
        """Container widget for terminal dashboard."""

    class Horizontal(_Stub):
        """Horizontal layout widget."""

    class Header(_Stub):
        """Header widget stub for textual compatibility."""

        def __init__(self, *_args, **_kwargs):
            """Initialize header widget."""
            super().__init__()

    class Footer(_Stub):
        """Footer widget stub for textual compatibility."""

    class Static(_Stub):
        """Static widget stub for textual compatibility."""

    class DataTable(_Stub):
        """Data table widget stub for textual compatibility."""

        cursor_row_key = None

    class Sparkline(_Stub):
        """Sparkline widget stub for textual compatibility."""

        data: ClassVar[list[float]] = []

    class Input(_Stub):
        """Input widget stub for textual compatibility."""

        class Submitted:  # minimal shim for type
            """Submitted event stub for textual compatibility."""

            def __init__(self):
                """Initialize submitted event."""
                self.input = _Stub()
                self.value = ""

    class RichLog(_Stub):
        """Rich log widget stub for textual compatibility."""

    class Button(_Stub):
        """Button widget stub for textual compatibility."""

    class Screen(_Stub):
        """Screen class stub for textual compatibility."""

    class ModalScreen(_Stub):
        """ModalScreen class stub for textual compatibility."""

    class Vertical(_Stub):
        """Vertical layout widget stub."""

    class Events:  # type: ignore[no-redef]
        """Events stub for textual compatibility."""

        class Key:  # minimal shim
            """Key event stub for textual compatibility."""

            def __init__(self, key: str = ""):
                """Initialize key event."""
                self.key = key


# ============================================================================
# Custom Footer Widget
# ============================================================================


class CustomFooter(Container):  # type: ignore[misc]
    """Custom footer that displays all bindings in organized rows."""
    
    DEFAULT_CSS = """
    CustomFooter {
        height: auto;
        min-height: 3;
        max-height: 6;
        border-top: solid $primary;
        background: $surface-darken-1;
        padding: 0 1;
        layout: vertical;
        overflow-x: auto;
        overflow-y: hidden;
    }
    CustomFooter #footer-content {
        width: 1fr;
        height: auto;
        min-height: 3;
        layout: vertical;
        overflow-x: auto;
        overflow-y: hidden;
    }
    CustomFooter .footer-row {
        height: 1;
        layout: horizontal;
        margin: 0;
        padding: 0;
    }
    CustomFooter .footer-item {
        margin: 0 1;
        width: auto;
        height: 1;
    }
    """
    
    def __init__(self, bindings: list[tuple[str, str, str]], *args: Any, **kwargs: Any) -> None:
        """Initialize custom footer with all bindings.
        
        Args:
            bindings: List of (key, action, description) tuples to display
"""
        super().__init__(*args, **kwargs)
        self._bindings = bindings
    
    def compose(self) -> Any:  # pragma: no cover
        """Compose the custom footer with multi-row layout."""
        from textual.containers import Horizontal
        
        if not self._bindings:
            yield Static(_("No commands available"), id="footer-content")
            return
        
        # Group bindings into rows (max 12 commands per row for readability)
        commands_per_row = 12
        rows = []
        current_row = []
        
        for key, action, description in self._bindings:
            current_row.append((key, action, description))
            if len(current_row) >= commands_per_row:
                rows.append(current_row)
                current_row = []
        
        # Add remaining row
        if current_row:
            rows.append(current_row)
        
        # Create rows with horizontal layout
        with Container(id="footer-content"):
            for row in rows:
                with Horizontal(classes="footer-row"):
                    for key, action, description in row:
                        yield Static(
                            f"[cyan]{key}[/cyan] {description}",
                            classes="footer-item",
                            markup=True
                        )


# ============================================================================
# Terminal Dashboard Application
# ============================================================================


class TerminalDashboard(App):  # type: ignore[misc]
    """Textual dashboard application."""

    CSS = """
    Screen { 
        layout: vertical; 
    }
    
    /* Split layout: 45% graphs, 40% bottom section, 15% for menus/footers */
    /* Use fractional units to ensure footers always have space */
    /* Total: 20fr - main-content gets 17fr, footers get 3fr */
    #main-content {
        layout: vertical;
        height: 17fr;  /* 17 out of 20 fractional units - leaves 3fr for footers */
        min-height: 20;
        display: block;
    }
    
    /* Graphs section: 45% of main-content (9fr out of 20fr total) */
    #graphs-section {
        height: 9fr;
        min-height: 12;
        display: block;
    }
    
    /* Main tabs section: 40% of main-content (8fr out of 20fr total) */
    #main-tabs-section {
        height: 8fr;
        min-height: 10;
        display: block;
    }
    
    /* Legacy layout (hidden - kept for backward compatibility) */
    .legacy-layout {
        display: none;
    }
    
    /* Status bar - ensure it's visible and not truncated */
    #statusbar {
        height: 1;
        min-height: 1;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        border-top: solid $primary;
        text-wrap: nowrap;
    }
    
    /* Overview footer - ensure it's visible and not truncated */
    #overview-footer {
        height: 2;
        min-height: 2;
        border-top: solid $primary;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        text-wrap: nowrap;
    }
    
    /* Custom footer - ensure it's visible and can accommodate multiple lines if needed */
    CustomFooter {
        height: auto;
        min-height: 2;
        max-height: 3;
        border-top: solid $primary;
        background: $surface-darken-1;
        padding: 0 1;
        overflow-x: auto;
        overflow-y: hidden;
    }
    
    CustomFooter #footer-content {
        width: 1fr;
        height: auto;
        min-height: 2;
        overflow-x: auto;
        overflow-y: hidden;
        text-wrap: wrap;
    }
    
    /* Rainbow theme border classes - sequential rainbow colors */
    /* Note: Textual uses 'border: <style> <color>' syntax, not 'border-color' */
    .rainbow-1 {
        border: solid $primary;
    }
    .rainbow-2 {
        border: solid $secondary;
    }
    .rainbow-3 {
        border: solid $accent;
    }
    .rainbow-4 {
        border: solid $success;
    }
    .rainbow-5 {
        border: solid $warning;
    }
    .rainbow-6 {
        border: solid $error;
    }
    .rainbow-7 {
        border: solid #8B00FF;  /* Violet color - hardcoded since $info is not available as CSS variable */
    }
    
    /* Note: Rainbow theme borders are applied programmatically via _apply_rainbow_borders() method
       using the .rainbow-1 through .rainbow-7 classes defined above. Attribute selectors
       like TerminalDashboard[theme="rainbow"] are not supported in Textual CSS. */
    """

    def __init__(
        self, session: Any, refresh_interval: float = 1.0, splash_manager: Any | None = None
    ):  # pragma: no cover
        """Initialize terminal dashboard.
        
        Args:
            session: DaemonInterfaceAdapter instance (daemon session required)
            refresh_interval: UI refresh interval in seconds
            splash_manager: Splash manager to end when dashboard is fully rendered
            
        Raises:
            ValueError: If session is not a DaemonInterfaceAdapter
        """
        super().__init__()
        
        # CRITICAL: Dashboard ONLY works with daemon - no local sessions allowed
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        if not isinstance(session, DaemonInterfaceAdapter):
            raise ValueError(
                "TerminalDashboard requires a DaemonInterfaceAdapter. "
                "Local sessions are not supported. Please ensure the daemon is running."
            )
        
        self.session = session
        self._splash_manager = splash_manager
        self._splash_ended = False
        
        # Initialize translations
        try:
            config = get_config()
            TranslationManager(config)
        except Exception:
            # Fallback if config not available
            TranslationManager(None)
        
        # Dashboard always uses daemon - WebSocket provides real-time updates, polling is backup
        # CRITICAL FIX: Use refresh_interval directly (no multiplier) for tighter integration
        self.refresh_interval = max(0.5, float(refresh_interval))
        
        self.alert_manager = get_alert_manager()
        self.metrics_collector = get_metrics_collector()
        self._poll_task: asyncio.Task | None = None
        self._filter_input: Input | None = None
        self._filter_text: str = ""
        self._last_status: dict[str, dict[str, Any]] = {}
        self._compact = False
        # Command executor for CLI command integration
        self._command_executor = CommandExecutor(session)
        # Data provider for unified data access (IPC client for daemon, direct for local)
        from ccbt.interface.data_provider import create_data_provider
        executor_for_provider = self._command_executor._executor if hasattr(self._command_executor, "_executor") else None
        self._data_provider = create_data_provider(session, executor_for_provider)
        # CRITICAL DEBUG: Log data provider initialization
        logger.debug("TerminalDashboard: Data provider initialized: %s", type(self._data_provider).__name__)
        if hasattr(self._data_provider, "_client"):
            logger.debug("TerminalDashboard: Data provider has IPC client: %s", type(self._data_provider._client).__name__)
        else:
            logger.warning("TerminalDashboard: Data provider does not have IPC client!")
        # Reactive update manager for WebSocket events
        self._reactive_manager: Any | None = None
        # Widget references will be set in on_mount after compose
        self.overview: Overview | None = None
        self.overview_footer: Overview | None = None
        self.speeds: SpeedSparklines | None = None
        self.torrents: TorrentsTable | None = None
        self.peers: PeersTable | None = None
        self.details: Static | None = None
        self.statusbar: Static | None = None
        self.alerts: Static | None = None
        self.logs: RichLog | None = None
        # New tabbed interface widgets
        self.graphs_section: GraphsSectionContainer | None = None

    def _format_bindings_display(self) -> Any:  # pragma: no cover
        """Format all key bindings grouped by category for display."""
        # Group bindings by category
        categories = {
            _("Torrent Control"): [
                ("p", _("Pause torrent")),
                ("r", _("Resume torrent")),
            ],
            _("Add Torrents"): [
                ("i", _("Quick add torrent")),
                ("o", _("Advanced add torrent")),
                ("b", _("Browse and add torrent")),
            ],
            _("Configuration"): [
                ("g", _("Global config")),
                ("t", _("Torrent config")),
            ],
            _("Monitoring"): [
                ("s", _("System resources")),
                ("m", _("Performance metrics")),
                ("n", _("Network quality")),
                ("h", _("Historical trends")),
                ("a", _("Alerts dashboard")),
                ("e", _("Metrics explorer")),
            ],
            _("Protocols (Ctrl+)"): [
                ("Ctrl+X", _("Xet management")),
                ("Ctrl+I", _("IPFS management")),
                ("Ctrl+S", _("SSL config")),
                ("Ctrl+P", _("Proxy config")),
                ("Ctrl+R", _("Scrape results")),
                ("Ctrl+N", _("NAT management")),
                ("Ctrl+U", _("uTP config")),
            ],
            _("Navigation"): [
                ("Ctrl+M", _("Navigation menu")),
                ("?", _("Help screen")),
            ],
            _("General"): [
                ("q", _("Quit")),
                ("x", _("Security scan")),
            ],
        }

        # Create a table with two columns for better layout
        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column(_("Key"), style="cyan bold", ratio=1)
        table.add_column(_("Action"), style="white", ratio=2)

        # Add bindings grouped by category
        for category, bindings in categories.items():
            table.add_row(
                f"[bold yellow]{category}[/bold yellow]", "", end_section=True
            )
            for key, action in bindings:
                table.add_row(f"  {key}", action)

        return table

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the dashboard layout."""
        # Textual UI composition method - requires full Textual app context to test
        # Testing would require mocking entire Textual framework or integration tests
        yield Header(show_clock=True)
        
        # Main content area with split layout
        with Container(id="main-content"):
            # Top half: Always-visible graphs section
            yield GraphsSectionContainer(self._data_provider, id="graphs-section")
            
            # Bottom half: Main tabs
            yield MainTabsContainer(self.session, id="main-tabs-section")
        
        # Legacy layout (kept for backward compatibility during transition)
        # TODO: Remove once new layout is fully implemented
        with Horizontal(id="body", classes="legacy-layout"):
            with Container(id="left"):
                yield Overview(id="overview")
                yield SpeedSparklines(id="speeds")
            with Container(id="right"):
                yield TorrentsTable(id="torrents")
                yield PeersTable(id="peers")
                yield Static(id="details")
                yield RichLog(id="logs")
        
        yield Static(id="statusbar")
        
        # Activity bar (overview) above commands
        yield Overview(id="overview-footer")
        
        # Comprehensive custom footer with all commands including Textual system bindings
        yield CustomFooter(self.ALL_FOOTER_BINDINGS)

    # All footer bindings - comprehensive list including Textual system bindings
    ALL_FOOTER_BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        # Core torrent actions
        ("p", "pause_torrent", _("Pause")),
        ("r", "resume_torrent", _("Resume")),
        ("q", "quit", _("Quit")),
        # Torrent addition
        ("i", "quick_add_torrent", _("Quick Add")),
        ("o", "advanced_add_torrent", _("Advanced Add")),
        ("b", "browse_add_torrent", _("Browse")),
        # Configuration
        ("g", "global_config", _("Global Config")),
        ("t", "torrent_config", _("Torrent Config")),
        # Monitoring screens
        ("s", "system_resources", _("System Resources")),
        ("m", "performance_metrics", _("Performance")),
        ("n", "network_quality", _("Network")),
        ("h", "historical_trends", _("History")),
        ("a", "alerts_dashboard", _("Alerts")),
        ("e", "metrics_explorer", _("Explore")),
        ("x", "security_scan", _("Security Scan")),
        # Settings
        ("l", "language_selection", _("Language")),
        ("ctrl+t", "theme_selection", _("Theme")),
        ("?", "help", _("Help")),
        # Protocol management (Ctrl+ combinations)
        ("ctrl+x", "xet_management", _("Xet")),
        ("ctrl+f", "xet_folder_sync", _("XET Folders")),
        ("ctrl+i", "ipfs_management", _("IPFS")),
        ("ctrl+s", "ssl_config", _("SSL Config")),
        ("ctrl+p", "proxy_config", _("Proxy Config")),
        ("ctrl+r", "scrape_results", _("Scrape Results")),
        ("ctrl+n", "nat_management", _("NAT Management")),
        ("ctrl+u", "utp_config", _("uTP Config")),
        ("ctrl+m", "navigation_menu", _("Menu")),
        # Textual system bindings
        ("ctrl+t", "toggle_dark", _("Toggle Dark/Light")),
        ("ctrl+d", "dark_mode", _("Dark Mode")),
        ("ctrl+shift+d", "light_mode", _("Light Mode")),
    ]
    
    # All bindings combined (for action routing)
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = ALL_FOOTER_BINDINGS
    
    # Legacy bindings (kept for backward compatibility)
    FOOTER_BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("p", "pause_torrent", _("Pause")),
        ("r", "resume_torrent", _("Resume")),
        ("q", "quit", _("Quit")),
        ("i", "quick_add_torrent", _("Quick Add")),
        ("o", "advanced_add_torrent", _("Advanced Add")),
        ("b", "browse_add_torrent", _("Browse")),
        ("g", "global_config", _("Global Config")),
    ]
    
    COMMAND_BARS_BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("t", "torrent_config", _("Torrent Config")),
        ("s", "system_resources", _("System Resources")),
        ("m", "performance_metrics", _("Performance")),
        ("n", "network_quality", _("Network")),
        ("h", "historical_trends", _("History")),
        ("a", "alerts_dashboard", _("Alerts")),
        ("e", "metrics_explorer", _("Explore")),
        ("x", "security_scan", _("Security Scan")),
        ("l", "language_selection", _("Language")),
        ("?", "help", _("Help")),
        ("ctrl+x", "xet_management", _("Xet")),
        ("ctrl+f", "xet_folder_sync", _("XET Folders")),
        ("ctrl+i", "ipfs_management", _("IPFS")),
        ("ctrl+s", "ssl_config", _("SSL Config")),
        ("ctrl+p", "proxy_config", _("Proxy Config")),
        ("ctrl+r", "scrape_results", _("Scrape Results")),
        ("ctrl+n", "nat_management", _("NAT Management")),
        ("ctrl+u", "utp_config", _("uTP Config")),
        ("ctrl+m", "navigation_menu", _("Menu")),
    ]

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the dashboard and start session polling."""
        # Textual lifecycle method - requires full app mount context to test
        
        # Register rainbow theme
        try:
            rainbow_theme = create_rainbow_theme()
            if rainbow_theme:
                self.register_theme(rainbow_theme)  # type: ignore[attr-defined]
                logger.debug("Rainbow theme registered")
        except Exception as e:
            logger.debug("Error registering rainbow theme: %s", e)
        
        # Get widget references after compose
        # Legacy widgets (for backward compatibility)
        try:
            try:
                self.overview = self.query_one("#overview", Overview)
            except Exception:
                self.overview = None
            self.overview_footer = self.query_one("#overview-footer", Overview)
            self.speeds = self.query_one("#speeds", SpeedSparklines)
            self.torrents = self.query_one("#torrents", TorrentsTable)
            self.peers = self.query_one("#peers", PeersTable)
            self.details = self.query_one("#details", Static)
        except Exception:
            # Legacy widgets may not be present in new layout
            pass
        
        # Prefer new top-pane logs widget, fall back to legacy RichLog
        self.logs = None
        try:
            self.logs = self.query_one("#top-logs", RichLog)
        except Exception:
            with contextlib.suppress(Exception):
                self.logs = self.query_one("#logs", RichLog)
        
        # New tabbed interface widgets
        try:
            self.graphs_section = self.query_one("#graphs-section", GraphsSectionContainer)
        except Exception:
            logger.warning("Graphs section not found, continuing without it")
            self.graphs_section = None
        
        # Status bar and alerts (always present)
        self.statusbar = self.query_one("#statusbar", Static)
        self.alerts = None
        for selector in ("#top-alerts", "#alerts"):
            with contextlib.suppress(Exception):
                self.alerts = self.query_one(selector, Static)
                if self.alerts:
                    break

        # Set up custom logging handler to capture errors in RichLog widget
        self._setup_logging_handler()

        # Start the session and begin polling
        try:
            # CRITICAL: Dashboard only works with daemon - start is handled by DaemonInterfaceAdapter
            # WebSocket subscription is already handled in adapter.start()
            # Register callbacks for real-time updates
            # Set up event callbacks for WebSocket updates
            from ccbt.daemon.ipc_protocol import EventType
            
            def on_torrent_status_changed(data: dict[str, Any]) -> None:
                """Handle torrent status change event."""
                # Use enhanced invalidate_on_event method
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        info_hash = data.get("info_hash", "")
                        self._data_provider.invalidate_on_event(
                            EventType.TORRENT_STATUS_CHANGED.value,
                            info_hash if info_hash else None,
                        )
                    elif hasattr(self._data_provider, "invalidate_cache"):
                        # Fallback to manual invalidation
                        self._data_provider.invalidate_cache("torrent_list")
                        self._data_provider.invalidate_cache("global_stats")
                # Trigger UI refresh (includes graphs section)
                self._schedule_poll()
                # CRITICAL FIX: Also explicitly refresh active torrent screens
                try:
                    from ccbt.interface.screens.torrents_tab import (
                        GlobalTorrentsScreen,
                        FilteredTorrentsScreen,
                    )
                    # Find and refresh active screen
                    # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                    try:
                        global_screen = self.query_one(GlobalTorrentsScreen)  # type: ignore[attr-defined]
                        if global_screen and hasattr(global_screen, "refresh_torrents"):
                            self.call_later(global_screen.refresh_torrents)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    # Try filtered screens
                    try:
                        filtered_screens = list(self.query(FilteredTorrentsScreen))  # type: ignore[attr-defined]
                        for screen in filtered_screens:
                            if screen.display and hasattr(screen, "refresh_torrents"):  # type: ignore[attr-defined]
                                self.call_later(screen.refresh_torrents)  # type: ignore[attr-defined]
                                break
                    except Exception:
                        pass
                except Exception:
                    pass
            
            def on_global_stats_updated(data: dict[str, Any]) -> None:
                """Handle global stats update event."""
                # Use enhanced invalidate_on_event method
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        self._data_provider.invalidate_on_event(
                            EventType.GLOBAL_STATS_UPDATED.value,
                            None,
                        )
                # Update graphs section immediately
                if self.graphs_section:
                    # Update graphs with event data
                    self.graphs_section.update_from_stats(data)
            
            def on_piece_completed(data: dict[str, Any]) -> None:
                """Handle piece completion event."""
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        info_hash = data.get("info_hash", "")
                        self._data_provider.invalidate_on_event(
                            EventType.PIECE_COMPLETED.value,
                            info_hash if info_hash else None,
                        )
            
            def on_progress_updated(data: dict[str, Any]) -> None:
                """Handle progress update event."""
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        info_hash = data.get("info_hash", "")
                        self._data_provider.invalidate_on_event(
                            EventType.PROGRESS_UPDATED.value,
                            info_hash if info_hash else None,
                        )
            
            # CRITICAL FIX: Register torrent added event callback
            def on_torrent_added(data: dict[str, Any]) -> None:
                """Handle torrent added event."""
                # Use enhanced invalidate_on_event method
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        info_hash = data.get("info_hash", "")
                        self._data_provider.invalidate_on_event(
                            EventType.TORRENT_ADDED.value,
                            info_hash if info_hash else None,
                        )
                    elif hasattr(self._data_provider, "invalidate_cache"):
                        # Fallback to manual invalidation
                        self._data_provider.invalidate_cache("torrent_list")
                        self._data_provider.invalidate_cache("swarm_health")
                # CRITICAL FIX: Refresh torrent list screens immediately
                try:
                    from ccbt.interface.screens.torrents_tab import (
                        GlobalTorrentsScreen,
                        FilteredTorrentsScreen,
                    )
                    # Find and refresh active screen
                    try:
                        global_screen = self.query_one(GlobalTorrentsScreen)  # type: ignore[attr-defined]
                        if global_screen and hasattr(global_screen, "refresh_torrents"):
                            # Use asyncio.create_task for async method
                            asyncio.create_task(global_screen.refresh_torrents())
                    except Exception:
                        pass
                    # Try filtered screens
                    try:
                        filtered_screens = list(self.query(FilteredTorrentsScreen))  # type: ignore[attr-defined]
                        for screen in filtered_screens:
                            if screen.display and hasattr(screen, "refresh_torrents"):  # type: ignore[attr-defined]
                                asyncio.create_task(screen.refresh_torrents())
                                break
                    except Exception:
                        pass
                    # CRITICAL FIX: Also refresh torrent controls widget
                    try:
                        from ccbt.interface.widgets.torrent_controls import TorrentControlsWidget
                        controls = self.query_one(TorrentControlsWidget, can_focus=False)  # type: ignore[attr-defined]
                        if controls and hasattr(controls, "_refresh_torrent_list"):
                            asyncio.create_task(controls._refresh_torrent_list())
                    except Exception:
                        pass
                    # CRITICAL FIX: Also refresh torrent selector in Per-Torrent tab
                    try:
                        from ccbt.interface.widgets.torrent_selector import TorrentSelector
                        selectors = list(self.query(TorrentSelector))  # type: ignore[attr-defined]
                        for selector in selectors:
                            if selector.is_attached and hasattr(selector, "_refresh_torrent_list"):  # type: ignore[attr-defined]
                                asyncio.create_task(selector._refresh_torrent_list())
                                # CRITICAL FIX: If this is a newly added torrent, auto-select it
                                info_hash = data.get("info_hash", "")
                                if info_hash:
                                    # Wait a moment for the selector to refresh, then set the value
                                    async def auto_select_new_torrent() -> None:
                                        await asyncio.sleep(0.5)  # Give selector time to refresh
                                        if selector.is_attached and hasattr(selector, "set_value"):  # type: ignore[attr-defined]
                                            selector.set_value(info_hash)  # type: ignore[attr-defined]
                                    asyncio.create_task(auto_select_new_torrent())
                    except Exception:
                        pass
                except Exception:
                    pass
                # Trigger UI refresh
                self._schedule_poll()
            
            # Register TORRENT_ADDED callback if session supports it
            if hasattr(self.session, "register_event_callback"):
                try:
                    self.session.register_event_callback(  # type: ignore[attr-defined]
                        EventType.TORRENT_ADDED,
                        on_torrent_added,
                    )
                except Exception:
                    pass
            # Also set up callback for daemon session adapter if available
            if hasattr(self.session, "on_torrent_added"):
                async def daemon_on_torrent_added(info_hash: bytes, name: str) -> None:
                    """Handle torrent added from daemon adapter."""
                    # Convert to dict format for consistency
                    info_hash_hex = info_hash.hex()
                    logger.debug(
                        "TerminalDashboard: daemon_on_torrent_added called - info_hash: %s, name: %s",
                        info_hash_hex,
                        name,
                    )
                    try:
                        on_torrent_added({"info_hash": info_hash_hex, "name": name})
                        logger.debug(
                            "TerminalDashboard: on_torrent_added callback completed for %s",
                            info_hash_hex,
                        )
                    except Exception as e:
                        logger.error(
                            "TerminalDashboard: Error in on_torrent_added callback: %s",
                            e,
                            exc_info=True,
                        )
                self.session.on_torrent_added = daemon_on_torrent_added  # type: ignore[assignment]
                logger.debug("TerminalDashboard: Registered daemon_on_torrent_added callback")
            
            self.session.register_event_callback(  # type: ignore[attr-defined]
                EventType.TORRENT_STATUS_CHANGED,
                on_torrent_status_changed,
            )
            
            # CRITICAL FIX: Register completion event callback to show user-facing dialog
            def on_torrent_completed(data: dict[str, Any]) -> None:
                """Handle torrent completion event and show dialog."""
                # Use enhanced invalidate_on_event method
                if hasattr(self, "_data_provider") and self._data_provider:
                    if hasattr(self._data_provider, "invalidate_on_event"):
                        info_hash = data.get("info_hash", "")
                        self._data_provider.invalidate_on_event(
                            EventType.TORRENT_COMPLETED.value,
                            info_hash if info_hash else None,
                        )
                    elif hasattr(self._data_provider, "invalidate_cache"):
                        # Fallback to manual invalidation
                        self._data_provider.invalidate_cache("torrent_list")
                        self._data_provider.invalidate_cache("global_stats")
                info_hash_hex = data.get("info_hash", "")
                name = data.get("name", "")
                if info_hash_hex and name:
                    # Schedule async dialog display
                    asyncio.create_task(self._show_completion_dialog(name, info_hash_hex))
                # Trigger UI refresh
                self._schedule_poll()
            
            self.session.register_event_callback(  # type: ignore[attr-defined]
                EventType.TORRENT_COMPLETED,
                on_torrent_completed,
            )
            
            # Register additional event callbacks for swarm/piece health updates
            self.session.register_event_callback(  # type: ignore[attr-defined]
                EventType.PIECE_COMPLETED,
                on_piece_completed,
            )
            
            self.session.register_event_callback(  # type: ignore[attr-defined]
                EventType.PROGRESS_UPDATED,
                on_progress_updated,
            )
            
            self.session.register_event_callback(  # type: ignore[attr-defined]
                EventType.GLOBAL_STATS_UPDATED,
                on_global_stats_updated,
            )
            # Note: Global stats events may not be available, but we'll poll for updates
            logger.info("Daemon session adapter started with WebSocket subscription")
            
            # Set up reactive update manager for graphs section
            try:
                from ccbt.interface.reactive_updates import ReactiveUpdateManager
                if self._data_provider:
                    # Create reactive update manager
                    self._reactive_manager = ReactiveUpdateManager(self._data_provider)
                    await self._reactive_manager.start()
                    await self._reactive_manager.setup_websocket_subscriptions(self.session)
                    
                    adapter = None
                    if hasattr(self._data_provider, "get_adapter"):
                        adapter = self._data_provider.get_adapter()
                    if adapter:
                        self._reactive_manager.subscribe_to_adapter(adapter)
                    
                    # Helper to refresh per-torrent tab when a specific info hash is impacted
                    async def _refresh_per_torrent_tab(info_hash: str | None) -> None:
                        if not info_hash:
                            return
                        try:
                            from ccbt.interface.screens.per_torrent_tab import PerTorrentTabContent
                            per_torrent_tab = self.query_one(PerTorrentTabContent)  # type: ignore[attr-defined]
                        except Exception:
                            per_torrent_tab = None
                        if not per_torrent_tab or not per_torrent_tab.is_attached or not per_torrent_tab.display:  # type: ignore[attr-defined]
                            return
                        selected = per_torrent_tab.get_selected_info_hash()
                        if not selected or selected.lower() != info_hash.lower():
                            return
                        if hasattr(per_torrent_tab, "refresh_active_sub_tab"):
                            try:
                                if hasattr(self, "loop"):
                                    self.loop.create_task(per_torrent_tab.refresh_active_sub_tab())  # type: ignore[attr-defined]
                                else:
                                    asyncio.create_task(per_torrent_tab.refresh_active_sub_tab())
                            except Exception:
                                await per_torrent_tab.refresh_active_sub_tab()

                    # Subscribe UI widgets to reactive events
                    def on_stats_update(event: Any) -> None:
                        """Handle stats update event for graphs."""
                        stats = getattr(event, "data", {}) or {}
                        if self.graphs_section:
                            self.graphs_section.update_from_stats(stats)
                        if getattr(self, "overview", None):
                            self.overview.update_from_stats(stats)
                        if getattr(self, "overview_footer", None):
                            self.overview_footer.update_from_stats(stats)
                        if getattr(self, "speeds", None):
                            self.speeds.update_from_stats(stats)
                    
                    async def on_torrent_delta(event: Any) -> None:
                        """Patch torrents table with incremental updates."""
                        if not hasattr(event, "data"):
                            return
                        info_hash = event.data.get("info_hash")
                        if not info_hash:
                            return
                        removed = event.data.get("event") == EventType.TORRENT_REMOVED.value
                        if not hasattr(self, "_last_status"):
                            self._last_status = {}
                        if removed:
                            self._last_status.pop(info_hash, None)
                        else:
                            status = await self._data_provider.get_torrent_status(info_hash)
                            if status:
                                self._last_status[info_hash] = status
                        self._apply_filter_and_update()
                    
                    async def on_peer_metrics(event: Any) -> None:
                        """Refresh peer widget from peer metric events."""
                        if not hasattr(event, "data"):
                            return
                        info_hash = event.data.get("info_hash")
                        if not info_hash or not getattr(self, "peers", None):
                            return
                        peers = await self._data_provider.get_torrent_peers(info_hash)
                        self.peers.update_from_peers(peers)

                    async def on_tracker_event(event: Any) -> None:
                        """Refresh tracker views on tracker events."""
                        data = getattr(event, "data", {}) or {}
                        await _refresh_per_torrent_tab(data.get("info_hash"))

                    async def on_metadata_event(event: Any) -> None:
                        """Refresh metadata-dependent views."""
                        data = getattr(event, "data", {}) or {}
                        await _refresh_per_torrent_tab(data.get("info_hash"))
                    
                    self._reactive_manager.subscribe("global_stats_updated", on_stats_update)
                    self._reactive_manager.subscribe("torrent_delta", on_torrent_delta)
                    self._reactive_manager.subscribe("peer_metrics", on_peer_metrics)
                    self._reactive_manager.subscribe("tracker_event", on_tracker_event)
                    self._reactive_manager.subscribe("metadata_event", on_metadata_event)
            except Exception as reactive_error:
                logger.debug("Error setting up reactive updates: %s", reactive_error)
                # Continue without reactive updates - polling will still work
                self._reactive_manager = None
        except Exception as e:
            logger.exception("Failed to start session")
            # Show error in status bar
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"[red]Failed to start session: {e}[/red]",
                        title="Error",
                        border_style="red",
                    )
                )
            raise
        
        with contextlib.suppress(Exception):
            await self.metrics_collector.start()
            # Set session reference so metrics collector can access DHT, queue, disk I/O, and tracker services
            if hasattr(self.metrics_collector, "set_session"):
                self.metrics_collector.set_session(self.session)
        # Auto-load alert rules from configured path or default if present
        try:
            from pathlib import Path

            default_path = getattr(
                getattr(self.session, "config", None),
                "observability",
                None,
            )
            rules_path = None
            if default_path and getattr(default_path, "alerts_rules_path", None):
                rules_path = Path(default_path.alerts_rules_path)
            else:
                rules_path = Path(".ccbt/alerts.json")
            default_rules = rules_path
            if default_rules.exists():
                self.alert_manager.load_rules_from_file(default_rules)  # type: ignore[attr-defined]
        except Exception:
            # Ignore alert manager initialization errors
            logger.debug("Alert manager initialization failed", exc_info=True)
        
        # Start polling (reduced frequency when WebSocket updates are active)
        fallback_interval = self.refresh_interval
        if self._reactive_manager:
            fallback_interval = max(self.refresh_interval, 30.0)
            self.refresh_interval = fallback_interval
        self.set_interval(fallback_interval, self._schedule_poll)
        
        # Trigger initial poll immediately to load torrents and stats
        self.call_later(self._schedule_poll)  # type: ignore[attr-defined]
        
        # Update status bar with connection status
        self._update_connection_status()
        
        # End splash screen after dashboard is mounted and first render is scheduled
        # Use multiple fallback mechanisms to ensure splash ends reliably
        if self._splash_manager and not self._splash_ended:
            # Method 1: Schedule splash end after refresh (primary method)
            try:
                self.call_after_refresh(self._end_splash)  # type: ignore[attr-defined]
            except Exception:
                pass
            
            # Method 2: Use set_timer as backup (after 0.5 seconds)
            # This is more reliable than call_later with delay
            try:
                self.set_timer(0.5, self._end_splash, name="splash_end_short")  # type: ignore[attr-defined]
            except Exception:
                pass
            
            # Method 3: Fallback timeout - end splash after 3 seconds maximum
            # This ensures splash always ends even if other methods fail
            try:
                self.set_timer(3.0, self._end_splash, name="splash_end_fallback")  # type: ignore[attr-defined]
            except Exception:
                pass
            
            # Method 4: Also try call_later without delay (immediate, but after current call stack)
            try:
                self.call_later(self._end_splash)  # type: ignore[attr-defined]
            except Exception:
                pass
        
        # Apply rainbow borders if rainbow theme is active
        self.call_later(self._apply_rainbow_borders)  # type: ignore[attr-defined]

    def _setup_logging_handler(self) -> None:  # pragma: no cover
        """Set up Textual logging handler to capture errors in RichLog widget.

        Uses RichHandler with correlation ID support for better formatting.
        """
        try:
            # Set up a custom handler to write to RichLog widget directly
            # This gives us more control over what appears in the logs widget
            class RichLogHandler(logging.Handler):
                """Custom handler that writes directly to RichLog widget with Rich formatting."""

                def __init__(self, rich_log_widget: RichLog, app_instance: Any):
                    super().__init__()
                    self.rich_log = rich_log_widget
                    self.app = app_instance
                    self.setLevel(logging.WARNING)  # Only capture warnings and errors

                def emit(self, record: logging.LogRecord) -> None:
                    """Emit log record to RichLog widget with Rich formatting."""
                    try:
                        # Use Rich formatting for better display
                        from ccbt.utils.rich_logging import CorrelationRichHandler
                        from rich.console import Console
                        from rich.logging import RichHandler
                        
                        # Create a console that writes to StringIO to capture formatted output
                        from io import StringIO
                        console = Console(file=StringIO(), width=120, force_terminal=False)
                        
                        # Format message with Rich markup based on level (icons removed)
                        from ccbt.utils.rich_logging import CorrelationRichHandler
                        
                        # Use colors from CorrelationRichHandler (icons removed)
                        colors = CorrelationRichHandler.LEVEL_COLORS
                        
                        level_name = record.levelname
                        color = colors.get(level_name, "white")
                        func_name = getattr(record, "funcName", "unknown")
                        original_msg = record.getMessage()
                        
                        # Colorize action text (like CorrelationRichHandler does)
                        handler = CorrelationRichHandler()
                        colored_msg = handler._colorize_action_text(original_msg)
                        
                        # Format: [color]LEVEL[/color] [#ff69b4]method_name[/#ff69b4] message
                        # Using hex color #ff69b4 (hot pink) as Rich doesn't have "pink" as a named color
                        formatted_msg = f"[{color}]{level_name}[/{color}] [#ff69b4]{func_name}[/#ff69b4] {colored_msg}"
                        
                        # Add correlation ID if available
                        if hasattr(record, "correlation_id") and record.correlation_id:
                            formatted_msg = f"[dim][{record.correlation_id}][/dim] {formatted_msg}"
                        
                        # Add timestamp for DEBUG/TRACE levels
                        if record.levelno <= logging.DEBUG:
                            import datetime
                            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            formatted_msg = f"[dim]{timestamp}[/dim] {formatted_msg}"
                        
                        # Write directly to RichLog - Textual handles thread safety
                        if self.rich_log:
                            try:
                                self.rich_log.write(formatted_msg)
                            except Exception:
                                # If direct write fails, try using app's call_later
                                if self.app and hasattr(self.app, "call_later"):
                                    try:
                                        self.app.call_later(
                                            self._write_sync, formatted_msg
                                        )
                                    except Exception:
                                        pass
                    except Exception:
                        # Fallback to simple formatting
                        try:
                            msg = self.format(record)
                            if self.rich_log:
                                self.rich_log.write(msg)
                        except Exception:
                            pass

                def _write_sync(self, msg: str) -> None:
                    """Write message synchronously (called from UI thread)."""
                    try:
                        if self.rich_log:
                            self.rich_log.write(msg)
                    except Exception:
                        pass

            # Add custom handler for RichLog widget
            rich_log_handler = RichLogHandler(self.logs, self)
            rich_log_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%H:%M:%S",
                )
            )

            # Add to root logger to capture all errors
            root_logger = logging.getLogger()
            root_logger.addHandler(rich_log_handler)
            root_logger.setLevel(logging.WARNING)  # Set root logger level
            self._rich_log_handler = rich_log_handler

            # Also try to use TextualHandler if available
            try:
                textual_handler = TextualHandler()
                textual_handler.setLevel(logging.WARNING)
                textual_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                        datefmt="%H:%M:%S",
                    )
                )
                root_logger.addHandler(textual_handler)
                self._log_handler = textual_handler
            except ImportError:
                # TextualHandler not available, that's okay
                self._log_handler = None

            # Write initial message to confirm logging is working
            self.logs.write(
                "[green]Logging initialized - errors and warnings will appear here[/green]"
            )

        except Exception as e:
            logger.debug("Error setting up logging handler: %s", e, exc_info=True)
            # Still try to write initial message
            try:
                if self.logs:
                    self.logs.write(
                        "[yellow]Logging handler setup had issues, but basic logging should work[/yellow]"
                    )
            except Exception:
                pass

    def _end_splash(self) -> None:
        """End splash screen when dashboard is fully rendered."""
        if self._splash_manager and not self._splash_ended:
            try:
                logger.debug("Ending splash screen - dashboard is ready")
                # Use stop_splash() which clears console and stops animation
                if hasattr(self._splash_manager, 'stop_splash'):
                    self._splash_manager.stop_splash()
                else:
                    # Fallback to clear_progress_messages
                    self._splash_manager.clear_progress_messages()
                
                # CRITICAL: Add a small delay to ensure splash screen is fully cleared
                # before Textual renders. This prevents the splash from leaking into the dashboard.
                import time
                time.sleep(0.1)  # 100ms delay to ensure terminal is ready
                
                self._splash_ended = True
                
                # Restore original log level if it was suppressed
                import logging
                root_logger = logging.getLogger()
                if hasattr(self._splash_manager, '_original_log_level'):
                    root_logger.setLevel(self._splash_manager._original_log_level)
                    logger.debug("Restored original log level: %s", self._splash_manager._original_log_level)
            except Exception as e:
                logger.debug("Error ending splash screen: %s", e, exc_info=True)
                # Mark as ended even if clear failed to prevent infinite retries
                self._splash_ended = True
    
    def _schedule_poll(self) -> None:  # pragma: no cover
        # UI refresh scheduler - requires Textual set_interval and task management
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_once())

    async def _get_torrent_detailed_metrics(
        self, info_hash_hex: str
    ) -> dict[str, Any]:  # pragma: no cover
        """Get detailed metrics for a specific torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format

        Returns:
            Dictionary with detailed metrics including:
            - pieces_completed, pieces_total
            - eta_seconds
            - total_downloaded_bytes, total_uploaded_bytes
            - connection_count
            - piece_availability
            - download_rate, upload_rate
        """
        try:
            # Convert hex to bytes
            info_hash_bytes = bytes.fromhex(info_hash_hex)

            # CRITICAL: Dashboard only works with daemon - use DataProvider for all data access
            # For DaemonInterfaceAdapter, we can't access piece_manager directly
            torrent_status = await self._data_provider.get_torrent_status(info_hash_hex)
            if not torrent_status:
                return {}
            
            # Return metrics from status data
            metrics: dict[str, Any] = {
                "status": torrent_status.get("status", "unknown"),
                "progress": torrent_status.get("progress", 0.0),
                "name": torrent_status.get("name", "Unknown"),
                "download_rate": torrent_status.get("download_rate", 0.0),
                "upload_rate": torrent_status.get("upload_rate", 0.0),
                "total_downloaded_bytes": torrent_status.get("downloaded", 0),
                "total_uploaded_bytes": torrent_status.get("uploaded", 0),
                "connection_count": torrent_status.get("peers", 0),
            }
            
            # Piece stats would need to be added to DataProvider if needed
            # For now, we rely on status data from DataProvider

            # Bytes downloaded/uploaded
            # CRITICAL: Use DataProvider data instead of direct session access
            metrics["total_downloaded_bytes"] = torrent_status.get("downloaded", 0)
            metrics["total_uploaded_bytes"] = torrent_status.get("uploaded", 0)
            total_size = torrent_status.get("total_size", 0)
            downloaded = torrent_status.get("downloaded", 0)
            metrics["left_bytes"] = max(0, total_size - downloaded)

            # Download/upload rates
            metrics["download_rate"] = torrent_status.get("download_rate", 0.0)
            metrics["upload_rate"] = torrent_status.get("upload_rate", 0.0)

            # Calculate ETA
            left_bytes = metrics.get("left_bytes", 0)
            download_rate = metrics.get("download_rate", 0.0)
            if download_rate > 0 and left_bytes > 0:
                metrics["eta_seconds"] = left_bytes / download_rate
            else:
                metrics["eta_seconds"] = None

            # Connection count
            try:
                # CRITICAL: Use DataProvider for read operations
                peers = await self._data_provider.get_torrent_peers(info_hash_hex)
                metrics["connection_count"] = len(peers) if peers else 0
            except Exception:
                metrics["connection_count"] = torrent_status.get("peer_count", 0)

            # Piece availability is not currently used in the interface
            # If needed in the future, it can be added to DataProvider

            # Add status information
            metrics["status"] = torrent_status.get("status", "unknown")
            metrics["progress"] = torrent_status.get("progress", 0.0)
            metrics["name"] = torrent_status.get("name", "Unknown")

            return metrics

        except Exception as e:
            logger.debug("Error getting detailed metrics for %s: %s", info_hash_hex, e)
            return {}

    async def _poll_once(self) -> None:  # pragma: no cover
        # Background polling task - requires widget tree and full app context.
        # Current polling responsibilities:
        #   1. get_global_stats() -> overview, speeds, graphs_section.
        #   2. list_torrents()    -> torrents table + _last_status snapshot.
        #   3. get_torrent_peers() for selected torrent -> peers widget.
        #   4. get_torrent_status() via _get_torrent_detailed_metrics().
        #   5. get_rate_samples()/disk/network metrics indirectly via widgets.
        # These will be replaced by WebSocket-driven updates where possible.
        
        # End splash after first successful poll (dashboard is rendered and has data)
        if self._splash_manager and not self._splash_ended:
            self._end_splash()
        
        try:
            # CRITICAL FIX: Verify data provider is available
            if not self._data_provider:
                logger.error("Data provider is None - cannot poll for updates")
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "[red]●[/red] Data provider not initialized",
                            title="Status",
                            border_style="red",
                        )
                    )
                return
            
            # Check daemon connection status
            # CRITICAL: Use DataProvider/IPC client instead of direct session access
            try:
                # Verify daemon is still accessible via data provider
                # DataProvider will handle connection checks internally
                stats = await self._data_provider.get_global_stats()
                if not stats:
                    # Daemon connection may be lost
                    logger.warning("Daemon connection lost during poll - no stats returned")
                    if self.statusbar:
                        self.statusbar.update(
                            Panel(
                                "[red]●[/red] Daemon connection lost - attempting to reconnect...",
                                title="Status",
                                border_style="red",
                            )
                        )
                    return
                logger.debug("Poll: Retrieved global stats successfully")
                
                # CRITICAL: End splash after successful data retrieval (dashboard is fully ready)
                # This is the most reliable indicator that dashboard has data and is rendered
                if self._splash_manager and not self._splash_ended:
                    self._end_splash()
            except Exception as conn_error:
                logger.error("Error checking daemon connection: %s", conn_error, exc_info=True)
                # Connection error - daemon may be down
                if self.statusbar:
                    self.statusbar.update(
                        Panel(
                            "[red]●[/red] Daemon connection error - check daemon status",
                            title="Status",
                            border_style="red",
                        )
                    )
                return
            
            # CRITICAL: Use DataProvider for all read operations (routes through IPC for daemon)
            # CRITICAL FIX: Add timeout to prevent UI hangs
            try:
                stats = await asyncio.wait_for(
                    self._data_provider.get_global_stats(),
                    timeout=10.0  # Increased from 5.0 for better reliability
                )
            except asyncio.TimeoutError:
                logger.debug("Poll: Timeout getting global stats, skipping this poll cycle")
                return
            except Exception as e:
                logger.debug("Poll: Error getting global stats: %s", e)
                return
            if not stats:
                logger.warning("Poll: No stats returned from data provider")
                return
            # Some tests construct the app without mounting widgets; guard None
            if getattr(self, "overview", None) is not None:
                self.overview.update_from_stats(stats)
            if getattr(self, "overview_footer", None) is not None:
                self.overview_footer.update_from_stats(stats)
            if getattr(self, "speeds", None) is not None:
                self.speeds.update_from_stats(stats)
            # Update graphs section (new tabbed interface)
            # This ensures graphs section gets updates via polling
            if getattr(self, "graphs_section", None) is not None:
                self.graphs_section.update_from_stats(stats)
            
            # Also update graphs section via WebSocket events if available
            # (handled in on_mount event callbacks)
            # CRITICAL: Use DataProvider instead of direct session access
            # CRITICAL FIX: Add timeout to prevent UI hangs
            all_status: dict[str, dict[str, Any]] = {}
            try:
                logger.debug("Poll: Calling data_provider.list_torrents()...")
                if not self._data_provider:
                    logger.error("Poll: _data_provider is None!")
                    return
                torrents_list = await asyncio.wait_for(
                    self._data_provider.list_torrents(),
                    timeout=10.0  # Increased from 5.0 for better reliability
                )
                logger.debug("Poll: Retrieved %d torrents from data provider", len(torrents_list) if torrents_list else 0)
                if not torrents_list:
                    logger.warning("Poll: list_torrents() returned empty list or None!")
                all_status_dict: dict[str, dict[str, Any]] = {}
                for torrent in torrents_list or []:
                    info_hash = torrent.get("info_hash", "")
                    if info_hash:
                        all_status_dict[info_hash] = torrent
                all_status = all_status_dict
                self._last_status = all_status
                self._apply_filter_and_update()
            except asyncio.TimeoutError:
                logger.debug("Poll: Timeout getting torrent list, skipping this poll cycle")
                # Use last known status if available
                all_status = self._last_status if hasattr(self, "_last_status") else {}
                return
            except Exception as torrent_error:
                logger.error("Error fetching torrent list: %s", torrent_error, exc_info=True)
                # Continue with empty list to avoid breaking the UI
                self._last_status = {}
                all_status = {}
                self._apply_filter_and_update()
            
            # CRITICAL FIX: Refresh per-torrent tab if active
            try:
                from ccbt.interface.screens.per_torrent_tab import PerTorrentTabContent
                # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
                try:
                    per_torrent_tab = self.query_one(PerTorrentTabContent)  # type: ignore[attr-defined]
                except Exception:
                    per_torrent_tab = None
                if per_torrent_tab and per_torrent_tab.is_attached and per_torrent_tab.display:  # type: ignore[attr-defined]
                    selected_ih = per_torrent_tab.get_selected_info_hash()
                    if selected_ih:
                        # Refresh the active sub-tab to ensure it's up-to-date
                        # Use asyncio.create_task for async method
                        if hasattr(per_torrent_tab, "refresh_active_sub_tab"):
                            # CRITICAL FIX: Use app's event loop for task creation
                            try:
                                if hasattr(self, "loop"):
                                    self.loop.create_task(per_torrent_tab.refresh_active_sub_tab())  # type: ignore[attr-defined]
                                else:
                                    asyncio.create_task(per_torrent_tab.refresh_active_sub_tab())
                            except Exception:
                                asyncio.create_task(per_torrent_tab.refresh_active_sub_tab())
                        elif hasattr(per_torrent_tab, "refresh"):
                            # Fallback to refresh if refresh_active_sub_tab not available
                            # refresh() is now synchronous and schedules async work internally
                            per_torrent_tab.refresh()
            except Exception as e:
                logger.debug("Error refreshing per-torrent tab: %s", e)
            
            # CRITICAL FIX: Refresh per-peer tab if active
            try:
                from ccbt.interface.screens.per_peer_tab import PerPeerTabContent
                try:
                    per_peer_tab = self.query_one(PerPeerTabContent)  # type: ignore[attr-defined]
                except Exception:
                    per_peer_tab = None
                if per_peer_tab and per_peer_tab.is_attached and per_peer_tab.display:  # type: ignore[attr-defined]
                    # Per-peer tab has its own update loop, but we can trigger a manual update
                    if hasattr(per_peer_tab, "_update_peer_data"):
                        try:
                            if hasattr(self, "loop"):
                                self.loop.create_task(per_peer_tab._update_peer_data())  # type: ignore[attr-defined]
                            else:
                                asyncio.create_task(per_peer_tab._update_peer_data())
                        except Exception:
                            asyncio.create_task(per_peer_tab._update_peer_data())
            except Exception as e:
                logger.debug("Error refreshing per-peer tab: %s", e)
            
            # Evaluate alert rules using current system metrics if available
            # Attempt to feed system CPU usage if present via MetricsCollector
            with contextlib.suppress(Exception):
                sys_cpu = None
                if hasattr(self.metrics_collector, "get_system_metrics"):
                    sm = self.metrics_collector.get_system_metrics()  # type: ignore[attr-defined]
                    sys_cpu = sm.get("cpu_usage") if isinstance(sm, dict) else None
                # If we have a CPU rule, evaluate it with current value
                if sys_cpu is not None and getattr(
                    self.alert_manager,
                    "alert_rules",
                    None,
                ):
                    for _rn, rule in list(self.alert_manager.alert_rules.items()):
                        if rule.metric_name in ("system_cpu_usage", "cpu_usage"):
                            await self.alert_manager.process_alert(
                                rule.metric_name,
                                float(sys_cpu),
                            )  # type: ignore[attr-defined]
            # Update peers for the selected torrent (if any)
            ih = self.torrents.get_selected_info_hash()
            peers: list[dict[str, Any]] = []
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use DataProvider instead of direct session access
                    peers = await self._data_provider.get_torrent_peers(ih)
            if getattr(self, "peers", None) is not None:
                self.peers.update_from_peers(peers)
            # Update details panel for selected torrent
            if ih and ih in all_status:
                st = all_status[ih]
                det = Table(show_header=False, box=None, expand=True)
                det.add_column("k", ratio=1)
                det.add_column("v", ratio=2)
                det.add_row("Name", str(st.get("name", "-")))
                det.add_row("Status", str(st.get("status", "-")))
                det.add_row("Progress", f"{float(st.get('progress', 0.0)) * 100:.1f}%")
                det.add_row("Down", f"{float(st.get('download_rate', 0.0)):.0f} B/s")
                det.add_row("Up", f"{float(st.get('upload_rate', 0.0)):.0f} B/s")

                # Show peer connection statistics
                connected_peers = st.get("connected_peers", 0)
                active_peers = st.get("active_peers", 0)
                det.add_row("Connected Peers", str(connected_peers))
                det.add_row("Active Peers", str(active_peers))

                # Show diagnostic info if download isn't progressing
                download_rate = float(st.get("download_rate", 0.0))
                progress = float(st.get("progress", 0.0))
                status_str = str(st.get("status", "unknown"))

                if (
                    status_str == "downloading"
                    and download_rate == 0.0
                    and progress < 1.0
                ):
                    # Download is active but not progressing
                    if connected_peers == 0:
                        det.add_row("⚠ Warning", "[yellow]No peers connected[/yellow]")
                    elif active_peers == 0:
                        det.add_row("⚠ Warning", "[yellow]No active peers[/yellow]")
                    else:
                        det.add_row("⚠ Warning", "[yellow]Download stalled[/yellow]")

                # Show tracker connection status
                tracker_status = st.get("tracker_status", "unknown")
                tracker_status_display = tracker_status
                if tracker_status == "connected":
                    tracker_status_display = "[green]connected[/green]"
                elif tracker_status == "error":
                    tracker_status_display = "[red]error[/red]"
                elif tracker_status == "timeout":
                    tracker_status_display = "[yellow]timeout[/yellow]"
                elif tracker_status == "connecting":
                    tracker_status_display = "[yellow]connecting...[/yellow]"
                det.add_row(_("Tracker"), tracker_status_display)

                # Show last tracker error if present
                last_tracker_error = st.get("last_tracker_error")
                if last_tracker_error:
                    det.add_row(
                        _("Tracker Error"), f"[red]{str(last_tracker_error)[:50]}[/red]"
                    )

                # Show last error if present
                last_error = st.get("last_error")
                if last_error:
                    det.add_row(_("Last Error"), f"[red]{str(last_error)[:50]}[/red]")

                # Get scrape result (BEP 48)
                scrape_result = None
                with contextlib.suppress(Exception):
                    # CRITICAL: Use executor for scrape result
                    result = await self._command_executor.execute_command("scrape.get_result", info_hash=ih)
                    if result and hasattr(result, "data") and result.data:
                        scrape_result = result.data

                if scrape_result:
                    det.add_row(_("Seeders (Scrape)"), str(scrape_result.seeders))
                    det.add_row(_("Leechers (Scrape)"), str(scrape_result.leechers))
                    det.add_row(_("Completed (Scrape)"), str(scrape_result.completed))
                    if hasattr(scrape_result, "scrape_count"):
                        det.add_row(_("Scrape Count"), str(scrape_result.scrape_count))
                    if (
                        hasattr(scrape_result, "last_scrape_time")
                        and scrape_result.last_scrape_time > 0
                    ):
                        import time

                        elapsed = time.time() - scrape_result.last_scrape_time
                        det.add_row(_("Last Scrape"), _("{elapsed:.0f}s ago").format(elapsed=elapsed))
                else:
                    det.add_row(_("Scrape"), _("[dim]No data (press 's' to scrape)[/dim]"))

                if getattr(self, "details", None) is not None:
                    self.details.update(Panel(det, title=_("Details")))
            elif getattr(self, "details", None) is not None:
                # Show key bindings when no torrent is selected
                bindings_display = self._format_bindings_display()
                self.details.update(Panel(bindings_display, title=_("Key Bindings")))
            # Update status bar counters with connection status
            connection_status = self._get_connection_status()
            sb = _("{connection}  Torrents: {torrents}  Active: {active}  Paused: {paused}  Seeding: {seeding}  D: {download}B/s  U: {upload}B/s").format(
                connection=connection_status,
                torrents=stats.get('num_torrents', 0),
                active=stats.get('num_active', 0),
                paused=stats.get('num_paused', 0),
                seeding=stats.get('num_seeding', 0),
                download=f"{float(stats.get('download_rate', 0.0)):.0f}",
                upload=f"{float(stats.get('upload_rate', 0.0)):.0f}"
            )
            if getattr(self, "statusbar", None) is not None:
                self.statusbar.update(Panel(sb, title=_("Status")))
            # Show alert rules and active alerts
            if getattr(self.alert_manager, "alert_rules", None):
                rules_table = Table(title=_("Alert Rules"), expand=True)
                rules_table.add_column(_("Name"), style="cyan")
                rules_table.add_column(_("Metric"))
                rules_table.add_column(_("Condition"))
                rules_table.add_column(_("Severity"), style="red")
                for rn, rule in self.alert_manager.alert_rules.items():
                    rules_table.add_row(
                        rn,
                        rule.metric_name,
                        rule.condition,
                        getattr(rule.severity, "value", str(rule.severity)),
                    )
                rules_renderable = rules_table
            else:
                rules_renderable = Panel(
                    _("No alert rules configured"), title=_("Alert Rules")
                )

            if getattr(self.alert_manager, "active_alerts", None):
                act_table = Table(title=_("Active Alerts"), expand=True)
                act_table.add_column(_("Severity"), style="red")
                act_table.add_column(_("Rule"), style="yellow")
                act_table.add_column(_("Value"))
                for a in self.alert_manager.active_alerts.values():
                    act_table.add_row(
                        getattr(a.severity, "value", str(a.severity)),
                        a.rule_name,
                        str(a.value),
                    )
                act_renderable = act_table
            else:
                act_renderable = Panel(_("No active alerts"), title=_("Active Alerts"))

            # Compose a Rich layout (Table.grid) and update Static with a renderable
            from rich.table import Table as RichTable

            alerts_grid = RichTable.grid(expand=True)
            alerts_grid.add_column(ratio=1)
            alerts_grid.add_column(ratio=1)
            alerts_grid.add_row(rules_renderable, act_renderable)
            if getattr(self, "alerts", None) is not None:
                self.alerts.update(Panel(alerts_grid, title=_("Alerts")))
        except Exception as e:
            # Log the error for debugging
            logger.exception("Error in dashboard poll")

            # Render error where overview goes but don't break the UI
            error_msg = _("Error: {error}").format(error=str(e)[:100])
            if getattr(self, "overview", None) is not None:
                self.overview.update(
                    Panel(error_msg, title=_("Dashboard Error"), border_style="red")
                )

            # Try to continue with cached data if available
            if self._last_status:
                try:
                    self._apply_filter_and_update()
                except Exception:
                    # If even cached data fails, just log it
                    logger.debug("Error applying cached status", exc_info=True)

    async def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the dashboard and stop session."""
        # Textual lifecycle method - requires full app unmount context to test
        
        # Cancel polling task
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        
        # CRITICAL FIX: On Windows, add delay before cleanup to prevent socket buffer exhaustion
        import sys
        if sys.platform == "win32":
            await asyncio.sleep(0.3)  # Increased wait time to allow socket buffers to drain
        
        # Stop session (DaemonInterfaceAdapter will close WebSocket and IPC connection)
        # CRITICAL: Dashboard only works with daemon - stop is handled by DaemonInterfaceAdapter
        if hasattr(self, "session") and self.session:
            try:
                # DaemonInterfaceAdapter.stop() closes IPC client connections
                if hasattr(self.session, "stop"):
                    await self.session.stop()
            except Exception as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully during cleanup
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    logger.warning(
                        "WinError 10055 (socket buffer exhaustion) during session cleanup. "
                        "This is a transient Windows issue. Continuing cleanup..."
                    )
                else:
                    logger.debug("Error stopping session during unmount: %s", e)
        
        # Stop metrics collector
        with contextlib.suppress(Exception):
            await self.metrics_collector.stop()

    # Key bindings
    # Note: Using on_key() method instead of @on(events.Key) for flexibility
    # This allows handling multiple keys in one method and custom logic
    async def on_key(self, event: events.Key) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle key press events.
        
        This method handles custom key bindings that aren't covered by action methods.
        For standard actions, use action_* methods which are automatically bound via BINDINGS.
        """
        # Textual event handler - requires full event system and widget tree to test
        # Testing would require complex Textual app setup and event simulation
        if event.key in ("q", "Q"):
            await self.action_quit()
            return
        if event.key in ("delete",):
            # Guard against missing widgets
            if not hasattr(self, "torrents") or not self.torrents:
                return
            ih = self.torrents.get_selected_info_hash()
            if ih:
                # Basic inline confirm: press 'y' to confirm deletion
                if hasattr(self, "overview") and self.overview:
                    self.overview.update(
                        Panel(
                            _("Delete torrent {info_hash}…? Press 'y' to confirm or 'n' to cancel").format(info_hash=ih[:16]),
                            title=_("Confirm"),
                            border_style="yellow",
                        ),
                    )
                self._pending_delete = ih  # type: ignore[attr-defined]
            return
        if event.key in ("y", "Y"):
            # Handle checkpoint resume confirmation
            pending_checkpoint = getattr(self, "_pending_checkpoint_resume", None)
            if pending_checkpoint:
                # Resume from checkpoint
                pending_path = getattr(self, "_pending_checkpoint_path", None)  # type: ignore[attr-defined]
                if pending_path:
                    # Re-run _process_add_torrent with resume=True
                    options = getattr(self, "_pending_checkpoint_options", {})  # type: ignore[attr-defined]
                    options["resume"] = True
                    self._pending_checkpoint_resume = None  # type: ignore[attr-defined]
                    self._pending_checkpoint_path = None  # type: ignore[attr-defined]
                    self._pending_checkpoint_options = None  # type: ignore[attr-defined]
                    await self._process_add_torrent(pending_path, options)
                return

            # Handle delete confirmation
            ih = getattr(self, "_pending_delete", None)
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use CommandExecutor for all write operations
                    await self._command_executor.execute_command("torrent.remove", info_hash=ih)
                self._pending_delete = None  # type: ignore[attr-defined]
            return
        if event.key in ("n", "N"):
            # Handle checkpoint resume cancellation
            if getattr(self, "_pending_checkpoint_resume", None):
                pending_path = getattr(self, "_pending_checkpoint_path", None)  # type: ignore[attr-defined]
                if pending_path:
                    # Re-run _process_add_torrent with resume=False
                    options = getattr(self, "_pending_checkpoint_options", {})  # type: ignore[attr-defined]
                    options["resume"] = False
                    self._pending_checkpoint_resume = None  # type: ignore[attr-defined]
                    self._pending_checkpoint_path = None  # type: ignore[attr-defined]
                    self._pending_checkpoint_options = None  # type: ignore[attr-defined]
                    await self._process_add_torrent(pending_path, options)
                return

            # Handle delete cancellation
            if getattr(self, "_pending_delete", None):
                self._pending_delete = None  # type: ignore[attr-defined]
            return
        if event.key in ("p", "P"):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use CommandExecutor for all write operations
                    await self._command_executor.execute_command("torrent.pause", info_hash=ih)
                    self.logs.write(f"Paused {ih}")
            return
        if event.key in ("r", "R"):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use CommandExecutor for all write operations
                    await self._command_executor.execute_command("torrent.resume", info_hash=ih)
                    self.logs.write(f"Resumed {ih}")
            return
        if event.key == "/":
            # Command palette lite: filter by name/status
            if not self._filter_input:
                self._filter_input = Input(
                    placeholder="Filter (name or status), press Enter to apply",
                    id="filter",
                )
                self.mount(self._filter_input)
                self._filter_input.focus()
            else:
                self._filter_input.display = True
                self._filter_input.focus()
            return
        if event.key in (":",):
            # Simple command palette:
            # pause|resume|remove|announce|scrape|pex|rehash|limit <down> <up>|backup <path>|restore <path>
            self._cmd_input = Input(placeholder="> command", id="cmd")
            self.mount(self._cmd_input)
            self._cmd_input.focus()
            return
        if event.key in ("a", "A"):
            # Force announce
            ih = self.torrents.get_selected_info_hash()
            if ih:
                try:
                    # CRITICAL: Use CommandExecutor for all write operations
                    result = await self._command_executor.execute_command("torrent.force_announce", info_hash=ih)
                    ok = result.success if result and hasattr(result, "success") else False
                    self.statusbar.update(
                        Panel(_("Announce: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                    )
                    self.logs.write(f"Announce {'OK' if ok else 'Failed'} for {ih}")
                except Exception:
                    self.statusbar.update(
                        Panel(_("Announce: Failed"), title=_("Status"), border_style="red"),
                    )
            return
        if event.key in ("s", "S"):
            # Force scrape
            ih = self.torrents.get_selected_info_hash()
            if ih:
                try:
                    # CRITICAL: Use CommandExecutor for all write operations
                    result = await self._command_executor.execute_command("scrape.torrent", info_hash=ih, force=True)
                    ok = result.success if result and hasattr(result, "success") else False
                    self.statusbar.update(
                        Panel(_("Scrape: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                    )
                    self.logs.write(f"Scrape {'OK' if ok else 'Failed'} for {ih}")
                except Exception:
                    self.statusbar.update(
                        Panel(_("Scrape: Failed"), title=_("Status"), border_style="red"),
                    )
            return
        if event.key in ("e", "E"):
            # Refresh PEX
            ih = self.torrents.get_selected_info_hash()
            if ih:
                try:
                    # CRITICAL: Use CommandExecutor for all write operations
                    # Use executor for PEX refresh
                    result = await self._command_executor.execute_command(
                        "torrent.refresh_pex",
                        info_hash=ih
                    )
                    ok = result.get("success", False) if isinstance(result, dict) else False
                    self.statusbar.update(
                        Panel(_("PEX: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                    )
                    self.logs.write(f"PEX {'OK' if ok else 'Failed'} for {ih}")
                except Exception:
                    self.statusbar.update(
                        Panel(_("PEX: Failed"), title=_("Status"), border_style="red"),
                    )
            return
        if event.key in ("h", "H"):
            # Rehash
            ih = self.torrents.get_selected_info_hash()
            if ih:
                try:
                    # Use executor for rehash
                    result = await self._command_executor.execute_command(
                        "torrent.rehash",
                        info_hash=ih
                    )
                    ok = result.get("success", False) if isinstance(result, dict) else False
                    self.statusbar.update(
                        Panel(_("Rehash: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                    )
                    self.logs.write(f"Rehash {'OK' if ok else 'Failed'} for {ih}")
                except Exception:
                    self.statusbar.update(
                        Panel(_("Rehash: Failed"), title=_("Status"), border_style="red"),
                    )
            return
        if event.key in ("x", "X"):
            # Export snapshot
            from pathlib import Path

            p = Path("dashboard_snapshot.json")
            try:
                # Use executor for export
                result = await self._command_executor.execute_command(
                    "torrent.export_session_state",
                    path=str(p)
                )
                if not result.get("success", False) if isinstance(result, dict) else False:
                    raise RuntimeError(result.get("error", "Export failed") if isinstance(result, dict) else "Export failed")
                self.statusbar.update(Panel(_("Snapshot saved to {path}").format(path=p), title=_("Status")))
                self.logs.write(f"Snapshot saved to {p}")
            except Exception as e:
                self.statusbar.update(
                    Panel(_("Snapshot failed: {error}").format(error=e), title=_("Status"), border_style="red"),
                )
            return
        if event.key in ("1",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use CommandExecutor for all write operations
                    await self._command_executor.execute_command("torrent.set_rate_limits", info_hash=ih, download_kib=0, upload_kib=0)
                    self.statusbar.update(Panel(_("Rate limits disabled"), title=_("Status")))
                    self.logs.write(f"Rate limits disabled for {ih}")
            return
        if event.key in ("2",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    # CRITICAL: Use executor for all write operations
                    result = await self._command_executor.execute_command(
                        "torrent.set_rate_limits",
                        info_hash=ih,
                        download_kib=1024,
                        upload_kib=1024,
                    )
                    if result and hasattr(result, "success") and result.success:
                        self.statusbar.update(
                            Panel(_("Rate limits set to 1024 KiB/s"), title=_("Status")),
                        )
                        self.logs.write(f"Rate limits set to 1024/1024 KiB/s for {ih}")
                    else:
                        error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                        self.logs.write(f"Failed to set rate limits: {error_msg}")
            return
        if event.key in ("m", "M"):
            # Toggle metrics collection interval among 1, 5, 10 seconds
            next_map = {1.0: 5.0, 5.0: 10.0, 10.0: 1.0}
            current = float(getattr(self.metrics_collector, "collection_interval", 5.0))
            if current not in next_map:
                current = 5.0
            new_iv = next_map[current]
            with contextlib.suppress(Exception):
                self.metrics_collector.collection_interval = new_iv
                self.statusbar.update(
                    Panel(_("Metrics interval: {interval}s").format(interval=new_iv), title=_("Status")),
                )
                self.logs.write(f"Metrics interval set to {new_iv}s")
            return
        if event.key in ("R",):
            # Toggle dashboard refresh interval among 0.5, 1.0, 2.0
            next_map = {0.5: 1.0, 1.0: 2.0, 2.0: 0.5}
            current = self.refresh_interval
            # pick nearest bucket
            if current not in next_map:
                current = 1.0
            self.refresh_interval = next_map[current]
            # Reset interval
            self.set_interval(self.refresh_interval, self._schedule_poll)
            self.statusbar.update(
                Panel(_("UI refresh interval: {interval}s").format(interval=self.refresh_interval), title=_("Status")),
            )
            return
        if event.key in ("t", "T"):
            # Toggle light/dark theme
            with contextlib.suppress(Exception):
                self.dark = not self.dark  # type: ignore[attr-defined]
                theme_name = _("Dark") if self.dark else _("Light")
                self.statusbar.update(
                    Panel(_("Theme: {theme}").format(theme=theme_name), title=_("Status")),
                )
            return
        if event.key in ("c", "C"):
            # Toggle compact mode (adjust panel proportions)
            self._compact = not self._compact
            with contextlib.suppress(Exception):
                torrents = self.query_one("#torrents")
                peers = self.query_one("#peers")
                details = self.query_one("#details")
                logs = self.query_one("#logs")
                # Increase torrents area when compact
                if self._compact:
                    torrents.styles.height = "3fr"  # type: ignore[attr-defined]
                    peers.styles.height = "1fr"  # type: ignore[attr-defined]
                    details.display = False  # type: ignore[attr-defined]
                    logs.display = False  # type: ignore[attr-defined]
                else:
                    torrents.styles.height = "2fr"  # type: ignore[attr-defined]
                    peers.styles.height = "1fr"  # type: ignore[attr-defined]
                    details.display = True  # type: ignore[attr-defined]
                    logs.display = True  # type: ignore[attr-defined]
                self.refresh(layout=True)  # type: ignore[call-arg]
            return
        if event.key in ("i", "I"):
            # Quick add torrent
            await self._quick_add_torrent()
            return
        if event.key in ("o", "O"):
            # Advanced add torrent
            await self._advanced_add_torrent()
            return
        if event.key in ("b", "B"):
            # Browse for torrent file
            await self._browse_add_torrent()
            return
        if event.key in ("enter",):
            # Handle file browser selection
            with contextlib.suppress(Exception):
                browser = self.query_one("#file_browser")
                if browser and browser.display:
                    selected_key = getattr(browser, "cursor_row_key", None)
                    if selected_key:
                        await self._handle_file_browser_selection(selected_key)
                    return
        if event.key in ("k", "K"):
            # Acknowledge (resolve) all active alerts
            with contextlib.suppress(Exception):
                for aid in list(
                    getattr(self.alert_manager, "active_alerts", {}).keys(),
                ):
                    await self.alert_manager.resolve_alert(aid)  # type: ignore[attr-defined]
                self.logs.write("Acknowledged all alerts")
            return

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submission events."""
        # Textual input event handler - requires full widget and event system
        if message.input.id == "filter":
            self._filter_text = message.value.strip()
            if self._filter_input:
                self._filter_input.display = False
            self._apply_filter_and_update()
        elif message.input.id == "cmd":
            cmdline = message.value.strip()
            message.input.display = False
            await self._run_command(cmdline)
        elif message.input.id == "add_torrent":
            path_or_magnet = message.value.strip()
            # CRITICAL FIX: Strip quotes from path (Windows paths may have quotes from copy/paste)
            if path_or_magnet and not path_or_magnet.startswith("magnet:"):
                path_or_magnet = path_or_magnet.strip('"').strip("'")
            # Remove the input widget after submission
            try:
                message.input.remove()  # type: ignore[attr-defined]
            except Exception:
                pass
            # Validate input before processing
            if not path_or_magnet:
                self.logs.write(
                    "[red]Error: No torrent path or magnet link provided[/red]"
                )
                return
            # Basic validation: must be magnet link or non-empty path
            if not path_or_magnet.startswith("magnet:") and len(path_or_magnet) < 3:
                self.logs.write("[red]Error: Invalid torrent path or magnet link[/red]")
                return
            # Run torrent addition in background to avoid blocking UI thread
            # This prevents the "Callback is still pending after 3 seconds" warning
            asyncio.create_task(self._process_add_torrent(path_or_magnet, {}))
        elif message.input.id == "add_torrent_advanced_step1":
            path_or_magnet = message.value.strip()
            # CRITICAL FIX: Strip quotes from path (Windows paths may have quotes from copy/paste)
            if path_or_magnet and not path_or_magnet.startswith("magnet:"):
                path_or_magnet = path_or_magnet.strip('"').strip("'")
            message.input.display = False
            if path_or_magnet:
                await self._show_advanced_options(path_or_magnet)
        elif message.input.id == "add_torrent_advanced_step2":
            output_dir = message.value.strip() or "."
            message.input.display = False
            await self._process_advanced_options(output_dir)

    def on_language_changed(
        self, message: Any
    ) -> None:  # pragma: no cover
        """Handle language change event from LanguageSelectorWidget.

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

            new_locale = message.locale
            logger.info("Language changed to: %s, refreshing interface widgets", new_locale)

            # Query and refresh all widgets that use translations
            # The message will bubble up through the widget tree, so widgets
            # can handle it individually, but we also coordinate here

            # Refresh main tabs container if it exists
            try:
                from ccbt.interface.widgets.tabbed_interface import (
                    MainTabsContainer,
                )

                main_tabs = self.query_one(MainTabsContainer, can_focus=False)  # type: ignore[attr-defined]
                if main_tabs:
                    # Post message to main tabs so it can handle its own refresh
                    main_tabs.post_message(message)  # type: ignore[attr-defined]
            except Exception:
                pass  # Main tabs may not be mounted yet

            # Refresh graphs section if it exists
            if self.graphs_section:
                try:
                    self.graphs_section.post_message(message)  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Trigger a refresh of visible widgets
            # Widgets that handle the message will update themselves
            # For widgets that don't handle it, we can trigger a general refresh
            self.call_later(self._refresh_translated_widgets)  # type: ignore[attr-defined]

        except Exception as e:
            logger.debug("Error handling language change: %s", e)

    def _refresh_translated_widgets(self) -> None:  # pragma: no cover
        """Refresh widgets that use translations but don't handle language change events."""
        try:
            from ccbt.i18n import _

            # Refresh status bar if it exists
            if self.statusbar:
                # Status bar content is usually dynamic, so it will update on next poll
                pass

            # Refresh logs if needed (usually dynamic)
            if self.logs:
                pass

            # Force a refresh of the app to update any remaining widgets
            # This is a fallback for widgets that don't handle the message
            self.refresh(layout=False)  # type: ignore[attr-defined]

        except Exception as e:
            logger.debug("Error refreshing translated widgets: %s", e)

    def on_language_changed(
        self, message: Any
    ) -> None:  # pragma: no cover
        """Handle language change event from LanguageSelectorWidget.

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

            new_locale = message.locale
            logger.info("Language changed to: %s, refreshing interface widgets", new_locale)

            # Query and refresh all widgets that use translations
            # The message will bubble up through the widget tree, so widgets
            # can handle it individually, but we also coordinate here

            # Refresh main tabs container if it exists
            try:
                from ccbt.interface.widgets.tabbed_interface import (
                    MainTabsContainer,
                )

                main_tabs = self.query_one(MainTabsContainer, can_focus=False)  # type: ignore[attr-defined]
                if main_tabs:
                    # Post message to main tabs so it can handle its own refresh
                    main_tabs.post_message(message)  # type: ignore[attr-defined]
            except Exception:
                pass  # Main tabs may not be mounted yet

            # Refresh graphs section if it exists
            if self.graphs_section:
                try:
                    self.graphs_section.post_message(message)  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Trigger a refresh of visible widgets
            # Widgets that handle the message will update themselves
            # For widgets that don't handle it, we can trigger a general refresh
            self.call_later(self._refresh_translated_widgets)  # type: ignore[attr-defined]

        except Exception as e:
            logger.debug("Error handling language change: %s", e)

    def _refresh_translated_widgets(self) -> None:  # pragma: no cover
        """Refresh widgets that use translations but don't handle language change events."""
        try:
            from ccbt.i18n import _

            # Refresh status bar if it exists
            if self.statusbar:
                # Status bar content is usually dynamic, so it will update on next poll
                pass

            # Refresh logs if needed (usually dynamic)
            if self.logs:
                pass

            # Force a refresh of the app to update any remaining widgets
            # This is a fallback for widgets that don't handle the message
            self.refresh(layout=False)  # type: ignore[attr-defined]

        except Exception as e:
            logger.debug("Error refreshing translated widgets: %s", e)

    def _apply_filter_and_update(self) -> None:  # pragma: no cover
        # UI helper method - requires widget tree to test properly
        # CRITICAL FIX: Update new tabbed interface screens instead of legacy widget
        try:
            # Try to find active torrent screen in new tabbed interface
            from ccbt.interface.screens.torrents_tab import (
                GlobalTorrentsScreen,
                FilteredTorrentsScreen,
            )
            
            # Query for active screen (either GlobalTorrentsScreen or FilteredTorrentsScreen)
            # CRITICAL FIX: query_one() doesn't accept can_be_none parameter in Textual
            try:
                # Try GlobalTorrentsScreen first
                global_screen = self.query_one(GlobalTorrentsScreen)  # type: ignore[attr-defined]
                if global_screen and hasattr(global_screen, "refresh_torrents"):
                    # Schedule refresh (async method)
                    self.call_later(global_screen.refresh_torrents)  # type: ignore[attr-defined]
                    return
            except Exception:
                pass
            
            # Try FilteredTorrentsScreen
            try:
                filtered_screens = list(self.query(FilteredTorrentsScreen))  # type: ignore[attr-defined]
                for screen in filtered_screens:
                    if screen.display and hasattr(screen, "refresh_torrents"):  # type: ignore[attr-defined]
                        # Schedule refresh (async method)
                        self.call_later(screen.refresh_torrents)  # type: ignore[attr-defined]
                        return
            except Exception:
                pass
        except Exception:
            pass
        
        # Fallback to legacy widget if new interface not found
        status = self._last_status
        if not self._filter_text:
            if hasattr(self, "torrents") and self.torrents:
                self.torrents.update_from_status(status)
            return
        filt = self._filter_text.lower()
        filtered: dict[str, dict[str, Any]] = {}
        for ih, st in status.items():
            name = str(st.get("name", "")).lower()
            state = str(st.get("status", "")).lower()
            if (filt in name) or (filt in state):
                filtered[ih] = st
        if hasattr(self, "torrents") and self.torrents:
            self.torrents.update_from_status(filtered)

    async def _run_command(self, cmdline: str) -> None:  # pragma: no cover
        # Command handler - requires widget tree and UI context
        parts = cmdline.split()
        if not parts:
            return
        cmd = parts[0].lower()
        ih = self.torrents.get_selected_info_hash()

        # Check if this is a Click command group (e.g., "xet", "ipfs", "ssl", "proxy", etc.)
        click_command_groups = [
            "xet",
            "ipfs",
            "ssl",
            "proxy",
            "scrape",
            "nat",
            "utp",
            "config",
            "queue",
            "files",
            "filter",
            "resume-tools",
            "checkpoints",
        ]

        if cmd in click_command_groups:
            # This is a Click command group, use execute_click_command
            command_path = " ".join(parts)  # Full command path (e.g., "xet status")
            (
                success,
                message,
                result,
            ) = await self._command_executor.execute_click_command(command_path)

            if success:
                # Display success message
                if message:
                    try:
                        from io import StringIO

                        from rich.console import Console

                        console = Console(file=StringIO(), width=120)
                        console.print(message)
                        formatted = console.file.getvalue()  # type: ignore[attr-defined]
                        self.statusbar.update(
                            Panel(
                                formatted or _("Command '{cmd}' executed successfully").format(cmd=cmd),
                                title=_("Success"),
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed: {message}")
                    except Exception:
                        # Fallback to simple text
                        self.statusbar.update(
                            Panel(
                                message or _("Command '{cmd}' executed successfully").format(cmd=cmd),
                                title=_("Success"),
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed")
                else:
                    self.logs.write(f"Command '{cmd}' executed successfully")
            else:
                # Display error message
                self.statusbar.update(
                    Panel(
                        message or _("Command '{cmd}' failed").format(cmd=cmd),
                        title=_("Error"),
                        border_style="red",
                    )
                )
                self.logs.write(f"Command '{cmd}' error: {message}")
            return

        # Check if this is a CLI command that should be handled by CommandExecutor
        available_commands = self._command_executor.get_available_commands()
        if cmd in available_commands:
            # Use CommandExecutor for CLI commands
            args = parts[1:] if len(parts) > 1 else []
            success, message, _result = await self._command_executor.execute_command(
                cmd, args, current_info_hash=ih
            )

            if success:
                # Display success message
                if message:
                    # Try to parse Rich renderables from message
                    try:
                        from io import StringIO

                        from rich.console import Console

                        console = Console(file=StringIO(), width=120)
                        console.print(message)
                        formatted = console.file.getvalue()  # type: ignore[attr-defined]
                        self.statusbar.update(
                            Panel(
                                formatted or _("Command '{cmd}' executed successfully").format(cmd=cmd),
                                title=_("Success"),
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed: {message}")
                    except Exception:
                        # Fallback to simple text
                        self.statusbar.update(
                            Panel(
                                message or _("Command '{cmd}' executed successfully").format(cmd=cmd),
                                title=_("Success"),
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed")
                else:
                    self.logs.write(f"Command '{cmd}' executed successfully")
            else:
                # Display error message
                self.statusbar.update(
                    Panel(
                        message or _("Command '{cmd}' failed").format(cmd=cmd),
                        title=_("Error"),
                        border_style="red",
                    )
                )
                self.logs.write(f"Command '{cmd}' error: {message}")
            return

        # Legacy command handlers (for backward compatibility)
        # CRITICAL: All commands must use CommandExecutor
        try:
            if cmd == "pause" and ih:
                result = await self._command_executor.execute_command("torrent.pause", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Paused {ih}")
                else:
                    self.logs.write(f"Failed to pause {ih}")
            elif cmd == "resume" and ih:
                result = await self._command_executor.execute_command("torrent.resume", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Resumed {ih}")
                else:
                    self.logs.write(f"Failed to resume {ih}")
            elif cmd == "remove" and ih:
                result = await self._command_executor.execute_command("torrent.remove", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Removed {ih}")
                else:
                    self.logs.write(f"Failed to remove {ih}")
            elif cmd == "announce" and ih:
                result = await self._command_executor.execute_command("torrent.force_announce", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Announce sent {ih}")
                else:
                    self.logs.write(f"Failed to announce {ih}")
            elif cmd == "scrape" and ih:
                result = await self._command_executor.execute_command("scrape.torrent", info_hash=ih, force=True)
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Scrape requested {ih}")
                else:
                    self.logs.write(f"Failed to scrape {ih}")
            elif cmd == "pex" and ih:
                # CRITICAL: Use executor for all write operations
                # Note: PEX refresh may not have executor command yet, but try executor first
                result = await self._command_executor.execute_command(
                    "torrent.refresh_pex",
                    info_hash=ih,
                )
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"PEX refresh {ih}")
                else:
                    # Fallback: executor command may not exist yet
                    self.logs.write(f"PEX refresh not yet available via executor for {ih}")
            elif cmd == "rehash" and ih:
                # CRITICAL: Use executor for all write operations
                result = await self._command_executor.execute_command(
                    "torrent.rehash",
                    info_hash=ih,
                )
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Rehash {ih}")
                else:
                    error_msg = result.error if result and hasattr(result, "error") else "Unknown error"
                    self.logs.write(f"Failed to rehash: {error_msg}")
            elif cmd == "limit" and ih and len(parts) >= 3:
                result = await self._command_executor.execute_command(
                    "torrent.set_rate_limits",
                    info_hash=ih,
                    download_kib=int(parts[1]),
                    upload_kib=int(parts[2]),
                )
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Set limits {parts[1]}/{parts[2]} KiB/s for {ih}")
                else:
                    self.logs.write(f"Failed to set limits for {ih}")
            elif cmd == "backup" and ih and len(parts) >= 2:
                from pathlib import Path
                # CRITICAL: Use executor for all write operations
                # Note: Checkpoint backup may not have executor command yet, but try executor first
                result = await self._command_executor.execute_command(
                    "checkpoint.backup",
                    info_hash=ih,
                    backup_path=str(Path(parts[1])),
                )
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Backup checkpoint to {parts[1]} for {ih}")
                else:
                    # Fallback: executor command may not exist yet
                    self.logs.write(f"Checkpoint backup not yet available via executor for {ih}")
            elif cmd == "restore" and len(parts) >= 2:
                # CRITICAL: Use executor for all write operations
                from pathlib import Path
                result = await self._command_executor.execute_command(
                    "checkpoint.restore",
                    backup_path=str(Path(parts[1])),
                )
                if result and hasattr(result, "success") and result.success:
                    self.logs.write(f"Restored checkpoint from {parts[1]}")
                else:
                    error_msg = result.error if result and hasattr(result, "error") else "Unknown error"
                    self.logs.write(f"Failed to restore checkpoint: {error_msg}")
            else:
                self.statusbar.update(
                    Panel(
                        f"Unknown command: {cmd}. Type 'help' for available commands.",
                        title="Error",
                        border_style="yellow",
                    )
                )
                self.logs.write(f"Unknown command: {cmd}")
        except Exception as e:
            self.statusbar.update(
                Panel(
                    f"Command error: {e}",
                    title="Error",
                    border_style="red",
                )
            )
            self.logs.write(f"Command error: {e}")

    async def _quick_add_torrent(self) -> None:  # pragma: no cover
        # UI interaction method - requires Textual Input widget and mount context
        """Quick add torrent with default settings."""
        # Use simple input dialog for quick add
        from ccbt.interface.screens.dialogs import QuickAddTorrentScreen
        screen = QuickAddTorrentScreen(self.session, self)
        
        # CRITICAL FIX: Use push_screen (non-blocking) to avoid recursion errors
        # The screen will handle the torrent addition and dismiss with info_hash
        # We'll handle the refresh via WebSocket events and a message handler
        await self.push_screen(screen)  # type: ignore[attr-defined]
        
        # Note: The QuickAddTorrentScreen will add the torrent via command executor
        # and the TORRENT_ADDED event callback we registered will handle refreshing the UI
        # We also have a message handler below to catch the dismiss result for immediate refresh

    async def _advanced_add_torrent(self) -> None:  # pragma: no cover
        # UI interaction method - requires Textual Input widget and mount context
        """Advanced add torrent with configuration options."""
        # Use the comprehensive AddTorrentScreen for advanced options
        from ccbt.interface.screens.dialogs import AddTorrentScreen
        screen = AddTorrentScreen(self.session, self)
        await self.push_screen(screen)  # type: ignore[attr-defined]

    async def _browse_add_torrent(self) -> None:  # pragma: no cover
        # File browser UI - requires DataTable widget and mount context
        """Browse for torrent file."""
        try:
            current_dir = Path.cwd()

            # Create a simple file browser using DataTable
            browser_table = DataTable(zebra_stripes=True, id="file_browser")
            browser_table.add_columns("Name", "Type", "Size")

            # Add parent directory entry
            browser_table.add_row("..", "Directory", "", key="..")

            # List directory contents
            try:
                for item in sorted(current_dir.iterdir()):
                    if item.is_dir():
                        browser_table.add_row(item.name, "Directory", "", key=str(item))
                    elif item.suffix.lower() == ".torrent":
                        size = item.stat().st_size
                        size_str = (
                            f"{size:,} bytes"
                            if size < 1024
                            else f"{size / 1024:.1f} KB"
                        )
                        browser_table.add_row(
                            item.name,
                            "Torrent",
                            size_str,
                            key=str(item),
                        )
            except PermissionError:
                browser_table.add_row("Permission denied", "Error", "", key="error")

            # Mount the browser
            self.mount(browser_table)
            browser_table.focus()

            # Store current directory for navigation
            self._browser_current_dir = current_dir  # type: ignore[attr-defined]

        except Exception as e:
            # Fallback to text input
            input_widget = Input(
                placeholder=f"Enter torrent file path (browse failed: {e})",
                id="add_torrent_browse",
            )
            self.mount(input_widget)
            input_widget.focus()

    async def _apply_torrent_options(
        self, options: dict[str, Any]
    ) -> None:  # pragma: no cover
        """Apply torrent-specific options to session config (matching CLI behavior).

        This applies the same overrides that the CLI uses via _apply_cli_overrides,
        ensuring the terminal dashboard matches CLI behavior.
        """
        try:
            # Import CLI override functions (may fail if circular import)
            from ccbt.cli.main import _apply_cli_overrides

            # Apply CLI overrides to config via executor
            # This matches the CLI behavior exactly
            # CRITICAL: Get config via executor instead of direct session access
            try:
                config_result = await self._command_executor.execute_command("config.get")
                if config_result and hasattr(config_result, "data") and isinstance(config_result.data, dict):
                    config_dict = config_result.data.get("config", {})
                    # Create a temporary config manager for applying overrides
                    from ccbt.config.config import ConfigManager
                    from ccbt.config.config_templates import ConfigTemplates
                    config_manager = ConfigManager(ConfigTemplates.create_default_config())
                    config_manager.config = config_manager.config.model_validate(config_dict)
                    _apply_cli_overrides(config_manager, options)
                    # Update config via executor
                    await self._command_executor.execute_command(
                        "config.update",
                        config_dict=config_manager.config.model_dump(mode="json"),
                    )
            except Exception as e:
                logger.debug(f"Could not apply CLI overrides via executor: {e}")
                # Fallback to manual application
                self._apply_torrent_options_manual(options)
        except (ImportError, AttributeError) as e:
            # If import fails (circular dependency or module not available),
            # apply options manually to match CLI behavior
            logger.debug(
                "Could not import CLI override functions, applying options manually: %s",
                e,
            )
            self._apply_torrent_options_manual(options)

        # Also apply per-torrent specific options that don't go through config
        # (These are handled separately after torrent is added)

    def _apply_torrent_options_manual(
        self, options: dict[str, Any]
    ) -> None:  # pragma: no cover
        """Manually apply torrent options when CLI imports are not available."""
        # CRITICAL: Get config via get_config() instead of direct session access
        from ccbt.config.config import get_config
        cfg = get_config()

        # Apply output directory (set in config for future torrents)
        # Note: Per-torrent output_dir requires session manager changes
        if options.get("output"):
            try:
                cfg.disk.download_path = str(options["output"])  # type: ignore[attr-defined]
            except Exception:
                pass  # download_path may not be settable

        # Apply Xet options
        if options.get("enable_xet"):
            cfg.disk.xet_enabled = True
        if options.get("xet_deduplication_enabled") is not None:
            cfg.disk.xet_deduplication_enabled = bool(
                options["xet_deduplication_enabled"]
            )
        if options.get("xet_use_p2p_cas") is not None:
            cfg.disk.xet_use_p2p_cas = bool(options["xet_use_p2p_cas"])
        if options.get("xet_compression_enabled") is not None:
            cfg.disk.xet_compression_enabled = bool(options["xet_compression_enabled"])

        # Apply uTP options
        if options.get("enable_utp"):
            cfg.network.enable_utp = True

        # Apply NAT options
        if options.get("enable_nat_pmp"):
            cfg.nat.enable_nat_pmp = True
        if options.get("enable_upnp"):
            cfg.nat.enable_upnp = True
        if options.get("auto_map_ports") is not None:
            cfg.nat.auto_map_ports = bool(options["auto_map_ports"])

        # Apply io_uring option
        if options.get("enable_io_uring"):
            try:
                cfg.disk.enable_io_uring = True  # type: ignore[attr-defined]
            except Exception:
                pass  # io_uring may not be available on this platform
        if options.get("disable_io_uring"):
            try:
                cfg.disk.enable_io_uring = False  # type: ignore[attr-defined]
            except Exception:
                pass

    async def _process_add_torrent(  # pragma: no cover
        self,
        path_or_magnet: str,
        options: dict[str, Any],
    ) -> None:
        """Process torrent addition with UI/UX features while using CLI executor commands.
        
        UI Features:
        - Checkpoint resume detection and user prompts
        - Private torrent warnings
        - File selection dialog for multi-file torrents
        - Status updates and progress messages
        
        All actual operations use CLI executor commands to match CLI behavior exactly.
        """
        # Basic validation
        if not path_or_magnet or not path_or_magnet.strip():
            self.logs.write("[red]Error: Empty torrent path or magnet link[/red]")
            self.statusbar.update(
                Panel(
                    "Error: No torrent path or magnet link provided",
                    title="Error",
                    border_style="red",
                )
            )
            return

        path_or_magnet = path_or_magnet.strip()
        # Strip quotes from path (Windows paths may have quotes from copy/paste)
        if path_or_magnet and not path_or_magnet.startswith("magnet:"):
            path_or_magnet = path_or_magnet.strip('"').strip("'")

        # Log the addition attempt
        self.logs.write(f"Adding torrent: {path_or_magnet[:50]}...")

        # UI FEATURE: Check for checkpoint if resume not explicitly set
        # SKIP for magnet links - they can't be parsed as files
        resume = options.get("resume", False)
        is_magnet = path_or_magnet.startswith("magnet:")
        
        if not resume and not is_magnet:
            try:
                # Get config to check if checkpoint is enabled
                config_result = await self._command_executor.execute_command("config.get")
                checkpoint_enabled = False
                if config_result and hasattr(config_result, "data") and isinstance(config_result.data, dict):
                    config_dict = config_result.data.get("config", {})
                    disk_config = config_dict.get("disk", {})
                    checkpoint_enabled = disk_config.get("checkpoint_enabled", False)
                
                if checkpoint_enabled:
                    # Try to detect checkpoint before adding torrent (UI feature)
                    try:
                        from ccbt.core.torrent import TorrentParser
                        from ccbt.storage.checkpoint import CheckpointManager
                        from ccbt.config.config import get_config
                        
                        loop = asyncio.get_event_loop()
                        parser = TorrentParser()
                        torrent_data = await loop.run_in_executor(
                            None, parser.parse, Path(path_or_magnet)
                        )
                        if torrent_data:
                            info_hash = (
                                torrent_data.get("info_hash")
                                if isinstance(torrent_data, dict)
                                else getattr(torrent_data, "info_hash", None)
                            )
                            if info_hash:
                                if isinstance(info_hash, str):
                                    info_hash_bytes = bytes.fromhex(info_hash)
                                else:
                                    info_hash_bytes = info_hash

                                # Check for checkpoint
                                config = get_config()
                                checkpoint_manager = CheckpointManager(config.disk)
                                try:
                                    checkpoint = await asyncio.wait_for(
                                        checkpoint_manager.load_checkpoint(info_hash_bytes),
                                        timeout=10.0  # Increased from 5.0 for better reliability,  # Reduced timeout
                                    )
                                except asyncio.TimeoutError:
                                    checkpoint = None

                                if checkpoint:
                                    # UI: Show checkpoint info and prompt user
                                    verified = len(getattr(checkpoint, "verified_pieces", []))
                                    total = getattr(checkpoint, "total_pieces", 0)
                                    torrent_name = getattr(checkpoint, "torrent_name", "Unknown")
                                    progress_pct = (verified / total * 100) if total > 0 else 0

                                    checkpoint_msg = (
                                        f"Found checkpoint for: {torrent_name}\n"
                                        f"Progress: {verified}/{total} pieces ({progress_pct:.1f}%)\n"
                                        f"Press 'y' to RESUME or 'n' to START FRESH (auto-resuming in 5s...)"
                                    )
                                    self.statusbar.update(
                                        Panel(
                                            checkpoint_msg,
                                            title="⚠️ Checkpoint Found - Action Required",
                                            border_style="yellow",
                                        )
                                    )
                                    self.logs.write(
                                        f"⚠️ Checkpoint found for {torrent_name}: {verified}/{total} pieces ({progress_pct:.1f}%)"
                                    )
                                    self.logs.write(
                                        "Press 'y' to resume or 'n' to start fresh (will auto-resume in 5 seconds)"
                                    )

                                    # Store checkpoint info for user confirmation
                                    self._pending_checkpoint_resume = info_hash_bytes  # type: ignore[attr-defined]
                                    self._pending_checkpoint_path = path_or_magnet  # type: ignore[attr-defined]
                                    self._pending_checkpoint_options = options.copy()  # type: ignore[attr-defined]

                                    # Auto-resume after 5 seconds if no user input
                                    # CRITICAL FIX: Use create_task to avoid blocking
                                    async def auto_resume_after_timeout():
                                        try:
                                            await asyncio.sleep(5.0)
                                            if (
                                                getattr(self, "_pending_checkpoint_resume", None)
                                                == info_hash_bytes
                                            ):
                                                self.logs.write("Auto-resuming from checkpoint (no user response)")
                                                options["resume"] = True
                                                self._pending_checkpoint_resume = None  # type: ignore[attr-defined]
                                                self._pending_checkpoint_path = None  # type: ignore[attr-defined]
                                                self._pending_checkpoint_options = None  # type: ignore[attr-defined]
                                                # CRITICAL FIX: Use create_task to avoid blocking UI
                                                asyncio.create_task(self._process_add_torrent(path_or_magnet, options))
                                        except Exception as e:
                                            logger.error("Error in auto-resume timeout: %s", e, exc_info=True)

                                    asyncio.create_task(auto_resume_after_timeout())
                                    return
                    except Exception as e:
                        logger.debug("Checkpoint check failed: %s", e)
            except Exception as e:
                logger.debug("Error checking checkpoint: %s", e)

        # UI FEATURE: Check for private torrent warning (before adding)
        # SKIP for magnet links - they can't be parsed as files
        is_private = False
        if not is_magnet:
            try:
                from ccbt.core.torrent import TorrentParser
                loop = asyncio.get_event_loop()
                parser = TorrentParser()
                torrent_data = await loop.run_in_executor(
                    None, parser.parse, Path(path_or_magnet)
                )
                if torrent_data:
                    is_private = (
                        torrent_data.get("is_private", False)
                        if isinstance(torrent_data, dict)
                        else getattr(torrent_data, "is_private", False)
                    )
            except Exception:
                pass

        if is_private:
            self.statusbar.update(
                Panel(
                    "⚠ Warning: Private torrent detected (BEP 27)\n"
                    "DHT, PEX, and LSD are disabled for this torrent.\n"
                    "Only tracker-provided peers will be used.",
                    title="Private Torrent",
                    border_style="yellow",
                )
            )
            self.logs.write("Private torrent detected (BEP 27)")

        # Show progress message
        self.statusbar.update(
            Panel(
                "Adding torrent... This may take a moment for large torrents.",
                title="Adding Torrent",
                border_style="blue",
            )
        )

        # CRITICAL: Use executor command exactly like CLI does
        # All actual operations go through executor - no direct session access
        # CRITICAL FIX: Ensure command executor is available
        if not hasattr(self, "_command_executor") or not self._command_executor:
            error_msg = "Command executor not available. Cannot add torrent."
            self.logs.write(f"[red]Error: {error_msg}[/red]")
            self.statusbar.update(
                Panel(
                    error_msg,
                    title="Error",
                    border_style="red",
                )
            )
            logger.error("_process_add_torrent: Command executor not available")
            return
        
        try:
            output_dir = options.get("output")
            if output_dir:
                self.logs.write(f"Using output directory: {output_dir}")

            # Use timeout similar to CLI (120s for magnets, 60s for files)
            timeout_seconds = 120.0 if path_or_magnet.startswith("magnet:") else 60.0
            
            # CRITICAL: Use executor command - matches CLI behavior exactly
            # CRITICAL FIX: Wrap in try-except to handle timeout and other errors gracefully
            try:
                result = await asyncio.wait_for(
                    self._command_executor.execute_command(
                        "torrent.add",
                        path_or_magnet=path_or_magnet,
                        resume=resume,
                        output_dir=output_dir,
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                error_msg = f"Timeout adding torrent (exceeded {timeout_seconds}s). The torrent may be very large or the connection may be slow."
                self.logs.write(f"[red]Error: {error_msg}[/red]")
                self.statusbar.update(
                    Panel(
                        error_msg,
                        title="Timeout Error",
                        border_style="red",
                    )
                )
                logger.error("_process_add_torrent: Timeout adding torrent")
                return
            except Exception as e:
                error_msg = f"Error executing torrent.add command: {str(e)}"
                self.logs.write(f"[red]Error: {error_msg}[/red]")
                self.statusbar.update(
                    Panel(
                        error_msg,
                        title="Command Error",
                        border_style="red",
                    )
                )
                logger.error("_process_add_torrent: Error executing command", exc_info=True)
                return
            
            # Extract info_hash from result
            if result and hasattr(result, "data"):
                if isinstance(result.data, dict):
                    info_hash = result.data.get("info_hash", "")
                else:
                    info_hash = str(result.data) if result.data else ""
            elif result and hasattr(result, "success") and result.success:
                info_hash = getattr(result, "info_hash", None) or ""
            else:
                error_msg = result.error if result and hasattr(result, "error") else "Unknown error"
                raise ValueError(f"Failed to add torrent: {error_msg}")
            
            if not info_hash:
                raise ValueError("Failed to add torrent: No info_hash returned")
            
            # Success - show message
            self.statusbar.update(
                Panel(
                    f"Successfully added torrent: {info_hash[:12]}...\n"
                    f"Status: Download starting...",
                    title="Success",
                    border_style="green",
                ),
            )
            self.logs.write(f"✓ Successfully added torrent: {path_or_magnet}")
            
            # CRITICAL: Force immediate announce to start download (like CLI does)
            try:
                await self._command_executor.execute_command(
                    "torrent.force_announce",
                    info_hash=info_hash,
                )
                self.logs.write("✓ Triggered immediate tracker announce")
            except Exception as e:
                logger.debug("Error forcing announce: %s", e)

            # UI FEATURE: Enhanced download flow
            # For magnet links, show metadata loading screen and then file selection
            if is_magnet:
                # Show metadata loading screen (non-blocking with continue option)
                from ccbt.interface.screens.dialogs import MetadataLoadingScreen
                result = await self.push_screen_wait(  # type: ignore[attr-defined]
                    MetadataLoadingScreen(
                        info_hash,
                        self.session,
                        self,
                    )
                )
                # Handle result: if user clicked continue with all_files, select all files
                if result and isinstance(result, dict) and result.get("continue") and result.get("all_files"):
                    try:
                        files = await self._data_provider.get_torrent_files(info_hash)
                        if files:
                            file_indices = [f.get("index") for f in files if f.get("index") is not None]
                            if file_indices:
                                await self._command_executor.execute_command(
                                    "file.select",
                                    info_hash=info_hash,
                                    file_indices=file_indices
                                )
                    except Exception as e:
                        logger.debug("Error selecting all files: %s", e)
                # CRITICAL FIX: After metadata loading screen, try to show file selection dialog
                # if metadata is now available and torrent has multiple files
                try:
                    # Wait a moment for metadata to be fully processed
                    await asyncio.sleep(0.5)
                    files = await asyncio.wait_for(
                        self._data_provider.get_torrent_files(info_hash),
                        timeout=10.0  # Increased from 5.0 for better reliability,
                    )
                    # Only show dialog if torrent has multiple files
                    if len(files) > 1:
                        from ccbt.interface.screens.file_selection_dialog import FileSelectionDialog
                        dialog = FileSelectionDialog(files)
                        selected_indices = await self.app.push_screen_wait(dialog)  # type: ignore[attr-defined]
                        
                        if selected_indices is not None:
                            # Deselect all files first
                            all_indices = [f.get("index", idx) for idx, f in enumerate(files)]
                            await self._command_executor.execute_command(
                                "file.deselect",
                                info_hash=info_hash,
                                file_indices=all_indices,
                            )
                            
                            # Then select the chosen files
                            if selected_indices:
                                await self._command_executor.execute_command(
                                    "file.select",
                                    info_hash=info_hash,
                                    file_indices=selected_indices,
                                )
                                self.logs.write(f"Selected {len(selected_indices)} file(s) for download")
                            else:
                                self.logs.write("No files selected for download")
                except asyncio.TimeoutError:
                    # Metadata not ready yet - start background task to show dialog later
                    logger.debug("Metadata not ready yet, will show file selection dialog when available")
                    async def try_file_selection_later():
                        """Try to show file selection dialog after metadata is available."""
                        # Wait for metadata to be available (up to 30 seconds)
                        max_wait = 30.0
                        start_time = asyncio.get_event_loop().time()
                        
                        while (asyncio.get_event_loop().time() - start_time) < max_wait:
                            try:
                                files = await asyncio.wait_for(
                                    self._data_provider.get_torrent_files(info_hash),
                                    timeout=2.0,
                                )
                                
                                # Only show dialog if torrent has multiple files
                                if len(files) > 1:
                                    from ccbt.interface.screens.file_selection_dialog import FileSelectionDialog
                                    dialog = FileSelectionDialog(files)
                                    selected_indices = await self.app.push_screen_wait(dialog)  # type: ignore[attr-defined]
                                    
                                    if selected_indices is not None:
                                        # Deselect all files first
                                        all_indices = [f.get("index", idx) for idx, f in enumerate(files)]
                                        await self._command_executor.execute_command(
                                            "file.deselect",
                                            info_hash=info_hash,
                                            file_indices=all_indices,
                                        )
                                        
                                        # Then select the chosen files
                                        if selected_indices:
                                            await self._command_executor.execute_command(
                                                "file.select",
                                                info_hash=info_hash,
                                                file_indices=selected_indices,
                                            )
                                            self.logs.write(f"Selected {len(selected_indices)} file(s) for download")
                                        else:
                                            self.logs.write("No files selected for download")
                                    return  # Success - exit loop
                            except (asyncio.TimeoutError, ValueError, KeyError):
                                # Metadata not ready yet, wait and retry
                                await asyncio.sleep(1.0)
                            except Exception as e:
                                logger.debug("Error in background file selection: %s", e)
                                return  # Give up on errors
                    
                    # Start background task
                    asyncio.create_task(try_file_selection_later())
                except Exception as e:
                    logger.debug("Error showing file selection dialog for magnet link: %s", e)
            # For file torrents, wait a moment for torrent to be fully initialized
            else:
                # File torrent - can check files immediately
                await asyncio.sleep(0.5)  # Reduced wait time
                
                try:
                    files = await asyncio.wait_for(
                        self._data_provider.get_torrent_files(info_hash),
                        timeout=10.0  # Increased from 5.0 for better reliability,  # Timeout to avoid hanging
                    )
                    
                    # Only show dialog if torrent has multiple files
                    if len(files) > 1:
                        from ccbt.interface.screens.file_selection_dialog import FileSelectionDialog
                        dialog = FileSelectionDialog(files)
                        selected_indices = await self.app.push_screen_wait(dialog)  # type: ignore[attr-defined]
                        
                        if selected_indices is not None:
                            # Deselect all files first
                            all_indices = [f.get("index", idx) for idx, f in enumerate(files)]
                            await self._command_executor.execute_command(
                                "file.deselect",
                                info_hash=info_hash,
                                file_indices=all_indices,
                            )
                            
                            # Then select the chosen files
                            if selected_indices:
                                await self._command_executor.execute_command(
                                    "file.select",
                                    info_hash=info_hash,
                                    file_indices=selected_indices,
                                )
                                self.logs.write(f"Selected {len(selected_indices)} file(s) for download")
                            else:
                                self.logs.write("No files selected for download")
                except asyncio.TimeoutError:
                    logger.debug("Timeout getting torrent files for file selection dialog")
                except Exception as e:
                    logger.debug("Error showing file selection dialog: %s", e)
            
            # Apply optional post-add configurations via executor (if specified)
            # These match exactly what the CLI does in downloads.py
            
            # File selection from options
            files_selection = options.get("files_selection")
            if files_selection:
                try:
                    await self._command_executor.execute_command(
                        "file.select",
                        info_hash=info_hash,
                        file_indices=list(files_selection),
                    )
                    self.logs.write(f"Selected {len(files_selection)} file(s)")
                except Exception as e:
                    logger.debug("Error applying file selection: %s", e)
            
            # File priorities
            file_priorities = options.get("file_priorities")
            if file_priorities:
                try:
                    for priority_spec in file_priorities:
                        file_index = priority_spec.get("index")
                        priority = priority_spec.get("priority", "normal")
                        if file_index is not None:
                            await self._command_executor.execute_command(
                                "file.priority",
                                info_hash=info_hash,
                                file_index=file_index,
                                priority=priority,
                            )
                except Exception as e:
                    logger.debug("Error applying file priorities: %s", e)
            
            # Queue priority
            queue_priority = options.get("queue_priority")
            if queue_priority:
                try:
                    await self._command_executor.execute_command(
                        "queue.add",
                        info_hash=info_hash,
                        priority=queue_priority.lower(),
                    )
                    self.logs.write(f"Set queue priority to {queue_priority}")
                except Exception as e:
                    logger.debug("Error setting queue priority: %s", e)
            
            # Rate limits
            if "download_limit" in options or "upload_limit" in options:
                try:
                    await self._command_executor.execute_command(
                        "torrent.set_rate_limits",
                        info_hash=info_hash,
                        download_kib=options.get("download_limit", 0),
                        upload_kib=options.get("upload_limit", 0),
                    )
                    self.logs.write(
                        f"Set rate limits: {options.get('download_limit', 0)}/"
                        f"{options.get('upload_limit', 0)} KiB/s"
                    )
                except Exception as e:
                    logger.debug("Error setting rate limits: %s", e)
                    
        except asyncio.TimeoutError:
            error_msg = (
                f"Timeout adding torrent (operation took longer than {timeout_seconds:.0f} seconds). "
                "The torrent may still be processing in the background."
            )
            logger.error(error_msg)
            self.statusbar.update(
                Panel(
                    error_msg,
                    title="Timeout Warning",
                    border_style="yellow",
                ),
            )
            self.logs.write(f"Warning: {error_msg}")
            return
        except ValueError as add_error:
            # Handle duplicate torrent/magnet errors gracefully
            error_msg = str(add_error)
            logger.warning(error_msg)
            self.statusbar.update(
                Panel(
                    error_msg,
                    title="Error",
                    border_style="yellow",
                ),
            )
            self.logs.write(f"[yellow]Warning: {error_msg}[/yellow]")
            return
        except Exception as add_error:
            # Re-raise to be caught by outer exception handler
            logger.exception("Error adding torrent: %s", add_error)
            self.statusbar.update(
                Panel(
                    f"Error adding torrent: {add_error}",
                    title="Error",
                    border_style="red",
                ),
            )
            self.logs.write(f"[red]Error: {add_error}[/red]")
            raise

    async def _show_completion_dialog(
        self, name: str, info_hash_hex: str
    ) -> None:  # pragma: no cover
        """Show completion dialog for finished torrent.
        
        Args:
            name: Torrent name
            info_hash_hex: Torrent info hash as hex string
        """
        try:
            from ccbt.interface.screens.base import ConfirmationDialog
            
            # Create a simple message dialog
            message = f"[green]✓ Download Complete![/green]\n\n"
            message += f"Torrent: {name}\n"
            message += f"Info Hash: {info_hash_hex[:16]}...\n\n"
            message += "Files have been written to disk and are ready to use."
            
            # Use a simple notification dialog (non-blocking)
            dialog = ConfirmationDialog(message)
            dialog.title = "Download Complete"
            # Auto-dismiss after 5 seconds
            async def auto_dismiss():
                await asyncio.sleep(5.0)
                try:
                    if hasattr(dialog, "dismiss"):
                        dialog.dismiss(True)  # type: ignore[attr-defined]
                except Exception:
                    pass
            
            # Show dialog and auto-dismiss
            asyncio.create_task(auto_dismiss())
            await self.push_screen(dialog)  # type: ignore[attr-defined]
            
            # Also log to logs widget
            if hasattr(self, "logs") and self.logs:
                self.logs.write(
                    f"[green]✓ Torrent completed: {name}[/green]"
                )
        except Exception as e:
            logger.warning(
                "Failed to show completion dialog: %s", e, exc_info=True
            )
            # Fallback: just log to logs widget
            if hasattr(self, "logs") and self.logs:
                self.logs.write(
                    f"[green]✓ Torrent completed: {name}[/green]"
                )

    async def _show_advanced_options(
        self, path_or_magnet: str
    ) -> None:  # pragma: no cover
        # UI dialog method - requires Input widget and mount context
        """Show advanced options dialog for torrent addition."""
        # Create a simple options dialog using multiple input prompts
        # For now, we'll use a simple approach with separate prompts

        # Step 2: Output directory
        input_widget = Input(
            placeholder="Output directory (default: .)",
            id="add_torrent_advanced_step2",
            value=".",
        )
        self.mount(input_widget)
        input_widget.focus()

        # Store the torrent path for later use
        self._pending_torrent_path = path_or_magnet  # type: ignore[attr-defined]

    async def _process_advanced_options(
        self, output_dir: str
    ) -> None:  # pragma: no cover
        # UI helper - updates statusbar/logs widgets
        """Process advanced options and add torrent."""
        try:
            path_or_magnet = getattr(self, "_pending_torrent_path", "")
            if not path_or_magnet:
                self.statusbar.update(
                    Panel(
                        "Error: No torrent path found",
                        title="Error",
                        border_style="red",
                    ),
                )
                return

            # For now, use default options except output directory
            options = {
                "output_dir": output_dir,
                "resume": False,
                "download_limit": 0,
                "upload_limit": 0,
            }

            await self._process_add_torrent(path_or_magnet, options)

            # Clean up
            self._pending_torrent_path = None  # type: ignore[attr-defined]

        except Exception as e:
            self.statusbar.update(
                Panel(
                    f"Error processing options: {e}",
                    title="Error",
                    border_style="red",
                ),
            )
            self.logs.write(f"Error processing advanced options: {e}")

    async def _handle_file_browser_selection(
        self, selected_key: str
    ) -> None:  # pragma: no cover
        # File browser UI handler - requires widget tree and navigation context
        """Handle file browser selection."""
        try:
            if selected_key == "..":
                # Navigate to parent directory
                current_dir = getattr(self, "_browser_current_dir", Path.cwd())
                parent_dir = current_dir.parent
                if parent_dir != current_dir:  # Not at root
                    await self._navigate_to_directory(parent_dir)
                return

            if selected_key == "error":
                # Permission error, fallback to text input
                self.query_one("#file_browser").display = False
                input_widget = Input(
                    placeholder="Enter torrent file path manually",
                    id="add_torrent_browse",
                )
                self.mount(input_widget)
                input_widget.focus()
                return

            selected_path = Path(selected_key)

            if selected_path.is_dir():
                # Navigate to directory
                await self._navigate_to_directory(selected_path)
            elif selected_path.suffix.lower() == ".torrent":
                # Select torrent file
                self.query_one("#file_browser").display = False
                await self._process_add_torrent(str(selected_path), {})
            else:
                # Not a torrent file, show error
                self.statusbar.update(
                    Panel(
                        f"Selected file is not a torrent: {selected_path.name}",
                        title="Error",
                        border_style="red",
                    ),
                )

        except Exception as e:
            self.statusbar.update(
                Panel(
                    f"Error handling selection: {e}",
                    title="Error",
                    border_style="red",
                ),
            )
            self.logs.write(f"Error handling file browser selection: {e}")

    async def _navigate_to_directory(self, new_dir: Path) -> None:  # pragma: no cover
        # File browser navigation - requires DataTable widget and mount context
        """Navigate to a new directory in the file browser."""
        try:
            # Remove old browser
            old_browser = self.query_one("#file_browser")
            if old_browser:
                old_browser.display = False

            # Create new browser for the directory
            browser_table = DataTable(zebra_stripes=True, id="file_browser")
            browser_table.add_columns("Name", "Type", "Size")

            # Add parent directory entry
            browser_table.add_row("..", "Directory", "", key="..")

            # List directory contents
            try:
                for item in sorted(new_dir.iterdir()):
                    if item.is_dir():
                        browser_table.add_row(item.name, "Directory", "", key=str(item))
                    elif item.suffix.lower() == ".torrent":
                        size = item.stat().st_size
                        size_str = (
                            f"{size:,} bytes"
                            if size < 1024
                            else f"{size / 1024:.1f} KB"
                        )
                        browser_table.add_row(
                            item.name,
                            "Torrent",
                            size_str,
                            key=str(item),
                        )
            except PermissionError:
                browser_table.add_row("Permission denied", "Error", "", key="error")

            # Mount the new browser
            self.mount(browser_table)
            browser_table.focus()

            # Update current directory
            self._browser_current_dir = new_dir  # type: ignore[attr-defined]

        except Exception as e:
            self.statusbar.update(
                Panel(
                    f"Error navigating to directory: {e}",
                    title="Error",
                    border_style="red",
                ),
            )

    # Actions
    async def action_pause_torrent(self) -> None:  # pragma: no cover
        """Pause the selected torrent."""
        # Textual action handler - triggered via key bindings, requires full app context
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                # CRITICAL: Use CommandExecutor for all write operations
                result = await self._command_executor.execute_command("torrent.pause", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.statusbar.update(Panel(_("Paused {info_hash}…").format(info_hash=ih[:12]), title=_("Action")))
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    self.statusbar.update(
                        Panel(_("Pause failed: {error}").format(error=error_msg), title=_("Action"), border_style="red"),
                    )
            except Exception as e:
                self.statusbar.update(
                    Panel(_("Pause failed: {error}").format(error=e), title=_("Action"), border_style="red"),
                )

    async def action_resume_torrent(self) -> None:  # pragma: no cover
        """Resume the selected torrent."""
        # Textual action handler - triggered via key bindings, requires full app context
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                # CRITICAL: Use CommandExecutor for all write operations
                result = await self._command_executor.execute_command("torrent.resume", info_hash=ih)
                if result and hasattr(result, "success") and result.success:
                    self.statusbar.update(Panel(_("Resumed {info_hash}…").format(info_hash=ih[:12]), title=_("Action")))
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    self.statusbar.update(
                        Panel(_("Resume failed: {error}").format(error=error_msg), title=_("Action"), border_style="red"),
                    )
            except Exception as e:
                self.statusbar.update(
                    Panel(_("Resume failed: {error}").format(error=e), title=_("Action"), border_style="red"),
                )

    async def action_scrape_selected(self) -> None:  # pragma: no cover
        """Scrape the selected torrent."""
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"scrape torrent {ih} --force"
                )
                if success:
                    self.statusbar.update(
                        Panel(
                            f"Scraped {ih[:12]}… successfully",
                            title="Scrape Success",
                            border_style="green",
                        )
                    )
                    # Trigger a poll to refresh details panel with new scrape data
                    self._schedule_poll()
                else:
                    self.statusbar.update(
                        Panel(
                            f"Scrape failed for {ih[:12]}…: {msg[:100] if len(msg) > 100 else msg}",
                            title="Scrape Error",
                            border_style="red",
                        )
                    )
            except Exception as e:
                self.statusbar.update(
                    Panel(
                        f"Scrape error: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
        else:
            self.statusbar.update(
                Panel(
                    "No torrent selected. Select a torrent first.",
                    title="Info",
                    border_style="yellow",
                )
            )

    async def action_global_config(self) -> None:  # pragma: no cover
        """Open global configuration screen."""
        # Textual action handler - requires full app context
        # CRITICAL FIX: Add timeout and error handling to prevent hanging
        try:
            # Write to logs immediately
            if self.logs:
                self.logs.write("[yellow]Opening global config screen...[/yellow]")

            # Add timeout to prevent indefinite hanging
            await asyncio.wait_for(
                self.push_screen(GlobalConfigMainScreen(self.session)),  # type: ignore[attr-defined]
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            error_msg = "Global config screen timed out after 5 seconds"
            logger.error(error_msg)
            if self.logs:
                self.logs.write(f"[red]ERROR: {error_msg}[/red]")
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        "Global config screen timed out. This may indicate a configuration loading issue.",
                        title="Timeout Error",
                        border_style="red",
                    )
                )
        except AttributeError as e:
            # Catch "list object has no attribute get" errors
            error_msg = str(e)
            logger.error(
                "CRITICAL: AttributeError opening global config: %s",
                error_msg,
                exc_info=True,
            )
            if self.logs:
                self.logs.write(
                    f"[red]CRITICAL ERROR opening global config: {error_msg}[/red]"
                )
                self.logs.write("[red]Error type: AttributeError[/red]")
                self.logs.write(
                    "[red]This may indicate a list was passed where a dict was expected[/red]"
                )
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Error opening global config: {error_msg}\n\nCheck logs for details.",
                        title="Configuration Error",
                        border_style="red",
                    )
                )
        except Exception as e:
            error_msg = f"Failed to open global config: {e}"
            logger.exception(error_msg)
            if self.logs:
                self.logs.write(f"[red]ERROR: {error_msg}[/red]")
            if self.statusbar:
                self.statusbar.update(
                    Panel(
                        f"Error opening global config: {e}",
                        title="Error",
                        border_style="red",
                    )
                )

    async def action_torrent_config(self) -> None:  # pragma: no cover
        """Open per-torrent configuration screen."""
        # Textual action handler - requires full app context
        await self.push_screen(PerTorrentConfigMainScreen(self.session))  # type: ignore[attr-defined]

    async def action_system_resources(self) -> None:  # pragma: no cover
        """Open system resources monitoring screen."""
        await self.push_screen(SystemResourcesScreen(self.session))  # type: ignore[attr-defined]

    async def action_performance_metrics(self) -> None:  # pragma: no cover
        """Open performance metrics monitoring screen."""
        await self.push_screen(PerformanceMetricsScreen(self.session))  # type: ignore[attr-defined]

    async def action_network_quality(self) -> None:  # pragma: no cover
        """Open network quality monitoring screen."""
        await self.push_screen(NetworkQualityScreen(self.session))  # type: ignore[attr-defined]

    async def action_historical_trends(self) -> None:  # pragma: no cover
        """Open historical trends monitoring screen."""
        await self.push_screen(HistoricalTrendsScreen(self.session))  # type: ignore[attr-defined]

    async def action_alerts_dashboard(self) -> None:  # pragma: no cover
        """Open alerts dashboard screen."""
        await self.push_screen(AlertsDashboardScreen(self.session))  # type: ignore[attr-defined]

    async def action_metrics_explorer(self) -> None:  # pragma: no cover
        """Open metrics explorer screen."""
        await self.push_screen(MetricsExplorerScreen(self.session))  # type: ignore[attr-defined]

    async def action_dht_metrics(self) -> None:  # pragma: no cover
        """Open DHT metrics screen."""
        from ccbt.interface.screens.monitoring.dht_metrics import DHTMetricsScreen
        await self.push_screen(DHTMetricsScreen(self.session))  # type: ignore[attr-defined]

    async def action_queue_metrics(self) -> None:  # pragma: no cover
        """Open queue metrics screen."""
        await self.push_screen(QueueMetricsScreen(self.session))  # type: ignore[attr-defined]

    async def action_disk_io_metrics(self) -> None:  # pragma: no cover
        """Open disk I/O metrics screen."""
        await self.push_screen(DiskIOMetricsScreen(self.session))  # type: ignore[attr-defined]

    async def action_tracker_metrics(self) -> None:  # pragma: no cover
        """Open tracker metrics screen."""
        await self.push_screen(TrackerMetricsScreen(self.session))  # type: ignore[attr-defined]

    async def action_performance_analysis(self) -> None:  # pragma: no cover
        """Open performance analysis screen."""
        await self.push_screen(PerformanceAnalysisScreen(self.session))  # type: ignore[attr-defined]

    async def action_security_scan(self) -> None:  # pragma: no cover
        """Open security scan screen."""
        from ccbt.interface.screens.monitoring.security_scan import SecurityScanScreen
        await self.push_screen(SecurityScanScreen(self.session))  # type: ignore[attr-defined]

    async def action_xet_management(self) -> None:  # pragma: no cover
        """Open Xet protocol management screen."""
        await self.push_screen(XetManagementScreen(self.session))  # type: ignore[attr-defined]

    async def action_xet_folder_sync(self) -> None:  # pragma: no cover
        """Open XET folder synchronization screen."""
        await self.push_screen(XetFolderSyncScreen(self.session))  # type: ignore[attr-defined]

    async def action_ipfs_management(self) -> None:  # pragma: no cover
        """Open IPFS protocol management screen."""
        await self.push_screen(IPFSManagementScreen(self.session))  # type: ignore[attr-defined]

    async def action_ssl_config(self) -> None:  # pragma: no cover
        """Open SSL/TLS configuration screen."""
        await self.push_screen(SSLConfigScreen(self.session))  # type: ignore[attr-defined]

    async def action_proxy_config(self) -> None:  # pragma: no cover
        """Open proxy configuration screen."""
        await self.push_screen(ProxyConfigScreen(self.session))  # type: ignore[attr-defined]

    async def action_scrape_results(self) -> None:  # pragma: no cover
        """Open scrape results screen."""
        await self.push_screen(ScrapeResultsScreen(self.session))  # type: ignore[attr-defined]

    async def action_nat_management(self) -> None:  # pragma: no cover
        """Open NAT management screen."""
        await self.push_screen(NATManagementScreen(self.session))  # type: ignore[attr-defined]

    async def action_utp_config(self) -> None:  # pragma: no cover
        """Open uTP configuration screen."""
        await self.push_screen(UTPConfigScreen(self.session))  # type: ignore[attr-defined]

    async def action_help(self) -> None:  # pragma: no cover
        """Open help screen."""
        await self.push_screen(HelpScreen())  # type: ignore[attr-defined]

    async def action_navigation_menu(self) -> None:  # pragma: no cover
        """Open navigation menu."""
        await self.push_screen(NavigationMenuScreen())  # type: ignore[attr-defined]
    
    async def action_language_selection(self) -> None:  # pragma: no cover
        """Open language selection screen."""
        from ccbt.interface.screens.language_selection_screen import LanguageSelectionScreen
        
        # Push screen (do not wait for result, as language change is handled by message propagation)
        self.push_screen(  # type: ignore[attr-defined]
            LanguageSelectionScreen(
                data_provider=self._data_provider,
                command_executor=self._command_executor,
            )
        )
    
    # Textual system actions
    async def action_toggle_dark(self) -> None:  # pragma: no cover
        """Toggle dark/light theme (Textual system action)."""
        self.dark = not self.dark  # type: ignore[attr-defined]
    
    async def action_light_mode(self) -> None:  # pragma: no cover
        """Switch to light mode (Textual system action)."""
        self.dark = False  # type: ignore[attr-defined]
    
    async def action_dark_mode(self) -> None:  # pragma: no cover
        """Switch to dark mode (Textual system action)."""
        self.dark = True  # type: ignore[attr-defined]
    
    def _apply_rainbow_borders(self) -> None:
        """Apply rainbow border classes to containers when rainbow theme is active.
        
        This method applies sequential rainbow colors to major containers
        when the rainbow theme is selected.
        """
        try:
            from ccbt.interface.themes.rainbow import apply_rainbow_border_class
            
            # Check if rainbow theme is active
            current_theme = getattr(self, "theme", None)
            if current_theme != "rainbow":
                return
            
            # Apply rainbow borders to major containers in sequence
            containers = [
                ("#main-content", 0),      # Red (rainbow-1)
                ("#graphs-section", 1),     # Orange (rainbow-2)
                ("#main-tabs-section", 2), # Yellow (rainbow-3)
                ("#workflow-pane", 3),     # Green (rainbow-4)
                ("#torrent-insight-pane", 4), # Blue (rainbow-5)
                ("#statusbar", 5),          # Indigo (rainbow-6)
                ("#overview-footer", 5),   # Indigo (rainbow-6)
            ]
            
            for selector, index in containers:
                try:
                    widget = self.query_one(selector)  # type: ignore[attr-defined]
                    apply_rainbow_border_class(widget, index)
                except Exception:
                    # Widget may not exist, skip
                    pass
        except Exception as e:
            logger.debug("Error applying rainbow borders: %s", e)
    
    async def action_theme_selection(self) -> None:  # pragma: no cover
        """Open theme selection screen."""
        from ccbt.interface.screens.theme_selection_screen import ThemeSelectionScreen
        
        # Push screen (theme is applied directly in ThemeSelectionScreen)
        self.push_screen(ThemeSelectionScreen())  # type: ignore[attr-defined]
        
        # Apply rainbow borders after a short delay to allow theme to be applied
        # The CSS should handle most of it, but this ensures classes are applied
        self.call_later(self._apply_rainbow_borders)  # type: ignore[attr-defined]
    
    def _get_connection_status(self) -> str:
        """Get connection status string for status bar."""
        # Dashboard only works with daemon - check WebSocket connection status
        if hasattr(self.session, "_websocket_connected") and self.session._websocket_connected:  # type: ignore[attr-defined]
            return "[green]●[/green] Daemon (WebSocket)"
        else:
            return "[yellow]●[/yellow] Daemon (Polling)"
    
    def _update_connection_status(self) -> None:
        """Update connection status in status bar."""
        if self.statusbar:
            connection_status = self._get_connection_status()
            # Initial status update
            self.statusbar.update(
                Panel(
                    f"{connection_status}  Initializing...",
                    title="Status",
                )
            )


async def _wait_for_daemon_health_check(
    ipc_client: Any,
    timeout: float = 90.0,
    check_interval: float = 1.0,
) -> bool:
    """Wait for daemon to be healthy using only IPC client health checks.
    
    This function ONLY uses IPC client health checks (is_daemon_running) and does NOT
    rely on PID files or process checks. This ensures we detect when the daemon is
    actually ready to accept connections, not just when the process is running.
    
    Args:
        ipc_client: IPCClient instance to use for health checks
        timeout: Maximum time to wait in seconds (default: 90.0)
        check_interval: Time between health checks in seconds (default: 1.0)
        
    Returns:
        True if daemon is healthy and ready, False if timeout exceeded
    """
    logger.info(
        "Waiting for daemon to be healthy via IPC health checks (timeout: %.0f seconds)...",
        timeout
    )
    logger.info(
        "This may take up to 90 seconds (NAT discovery ~35s, DHT bootstrap ~8s, IPC server startup)"
    )
    
    start_time = time.time()
    last_log_time = start_time
    log_interval = 5.0  # Log progress every 5 seconds
    
    while time.time() - start_time < timeout:
        elapsed = time.time() - start_time
        
        # Log progress every 5 seconds
        if time.time() - last_log_time >= log_interval:
            logger.info("Still waiting for daemon health check... (%.1f seconds elapsed)", elapsed)
            last_log_time = time.time()
        
        try:
            # CRITICAL: Only use IPC client health check - no PID file or process checks
            # This ensures we detect when daemon is actually ready, not just when process exists
            is_running = await ipc_client.is_daemon_running()
            if is_running:
                elapsed = time.time() - start_time
                logger.info(
                    "Daemon is healthy and ready via IPC health check (took %.1f seconds)",
                    elapsed
                )
                return True
            else:
                # Log at INFO level every 5 seconds to help diagnose issues
                if int(elapsed) % 5 == 0:
                    logger.info(
                        "Daemon health check returned False (base_url=%s, elapsed=%.1fs). "
                        "This may indicate: wrong port, API key mismatch, or daemon not ready.",
                        ipc_client.base_url,
                        elapsed
                    )
                else:
                    logger.debug("Daemon health check failed, retrying in %.1f seconds...", check_interval)
        except Exception as check_error:
            # Log exceptions at INFO level to help diagnose connection/auth issues
            logger.info(
                "Daemon health check exception (base_url=%s, elapsed=%.1fs): %s",
                ipc_client.base_url,
                elapsed,
                check_error
            )
            logger.debug("Full exception details:", exc_info=check_error)
        
        # Wait before next check
        try:
            await asyncio.wait_for(asyncio.sleep(check_interval), timeout=check_interval + 0.1)
        except asyncio.TimeoutError:
            break
    
    # Timeout - daemon did not become healthy
    elapsed = time.time() - start_time
    logger.error(
        "Daemon did not become healthy within %.0f seconds (waited %.1f seconds)",
        timeout,
        elapsed
    )
    return False


async def _scan_for_daemon_port(
    api_key: str,
    ports_to_try: list[int],
    timeout_per_port: float = 1.0,
) -> tuple[int | None, Any | None]:
    """Scan multiple ports to find where the daemon is actually listening.
    
    Args:
        api_key: API key for authentication
        ports_to_try: List of ports to try
        timeout_per_port: Timeout per port in seconds
        
    Returns:
        Tuple of (port_number, IPCClient) if found, (None, None) if not found
    """
    from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
    
    client_host = "127.0.0.1"
    
    for port in ports_to_try:
        base_url = f"http://{client_host}:{port}"
        client = IPCClient(api_key=api_key, base_url=base_url)
        
        try:
            # Quick health check with timeout
            is_running = await asyncio.wait_for(
                client.is_daemon_running(),
                timeout=timeout_per_port
            )
            if is_running:
                logger.info("Found daemon listening on port %d", port)
                return (port, client)
        except asyncio.TimeoutError:
            logger.debug("Timeout checking port %d", port)
        except Exception as e:
            logger.debug("Error checking port %d: %s", port, e)
        finally:
            # Close client if it didn't work
            try:
                await client.close()
            except Exception:
                pass
    
    return (None, None)


def _show_startup_splash(
    no_splash: bool = False,
    verbosity_count: int = 0,
    console: Any | None = None,
) -> tuple[Any | None, Any | None]:
    """Show splash screen for terminal interface startup.
    
    Args:
        no_splash: Whether to disable splash screen
        verbosity_count: Verbosity count (0 = NORMAL, 1+ = verbose)
        console: Rich Console instance (optional)
        
    Returns:
        Tuple of (splash_manager, splash_thread) or (None, None) if not shown
    """
    # Only show splash when verbosity is NORMAL (no -v flags) AND --no-splash is not set
    if verbosity_count > 0 or no_splash:
        return (None, None)
    
    try:
        from ccbt.interface.splash.splash_manager import SplashManager
        from ccbt.cli.task_detector import get_detector
        import threading
        import logging
        
        # Temporarily suppress INFO-level logs during splash (splash screen visually hides them anyway)
        # Store original level to restore later
        root_logger = logging.getLogger()
        original_level = root_logger.level
        # Only suppress if not already at a higher level
        if original_level <= logging.INFO:
            root_logger.setLevel(logging.WARNING)
        
        detector = get_detector()
        # Register dashboard startup as a long-running task if not already registered
        if not detector.get_task_info("dashboard.start"):
            detector.register_command(
                command_name="dashboard.start",
                expected_duration=90.0,  # Up to 90s for daemon startup + dashboard init
                min_duration=2.0,
                description="Starting dashboard (daemon health checks, initialization)",
                show_splash=True,
            )
        
        if detector.should_show_splash("dashboard.start"):
            splash_manager = SplashManager.from_verbosity_count(verbosity_count, console=console)
            expected_duration = detector.get_expected_duration("dashboard.start")
            
            # Store original log level in splash manager for restoration
            splash_manager._original_log_level = original_level  # type: ignore[attr-defined]
            
            # Start splash screen in background thread
            def run_splash() -> None:
                try:
                    asyncio.run(
                        splash_manager.show_splash_for_task(
                            task_name="dashboard start",
                            max_duration=expected_duration,
                            show_progress=True,
                        )
                    )
                except Exception:
                    # Ignore errors in splash thread
                    pass
                finally:
                    # Restore original log level when splash ends (if not already restored)
                    try:
                        if hasattr(splash_manager, '_original_log_level'):
                            root_logger.setLevel(splash_manager._original_log_level)
                    except Exception:
                        pass
            
            splash_thread = threading.Thread(target=run_splash, daemon=True)
            splash_thread.start()
            return (splash_manager, splash_thread)
        else:
            # Restore log level if splash not shown
            root_logger.setLevel(original_level)
    except Exception:
        # If splash system fails, continue without it
        pass
    
    return (None, None)


async def _ensure_daemon_running(
    splash_manager: Any | None = None,
) -> tuple[bool, Any | None]:
    """Ensure daemon is running, start if needed.
    
    CRITICAL: This function ONLY uses IPC client health checks (is_daemon_running)
    to determine if the daemon is healthy. It does NOT rely on PID files or process
    checks. This ensures we detect when the daemon is actually ready to accept
    connections, not just when the process is running.
    
    Returns:
        Tuple of (success: bool, ipc_client: IPCClient | None)
        If daemon is running or successfully started, returns (True, IPCClient)
        If daemon start fails, returns (False, None)
    """
    from ccbt.config.config import get_config, init_config
    from ccbt.daemon.daemon_manager import DaemonManager
    from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
    from ccbt.daemon.utils import generate_api_key
    from ccbt.models import DaemonConfig
    
    config_manager = init_config()
    cfg = get_config()
    
    if not cfg.daemon or not cfg.daemon.api_key:
        # Generate API key and create daemon config
        api_key = generate_api_key()
        cfg.daemon = DaemonConfig(api_key=api_key)
        logger.warning("Daemon config not found, generated new API key")
    
    # CRITICAL FIX: Use _get_daemon_ipc_port() helper to get the correct IPC port
    # This ensures we use the daemon's actual port (from daemon config file) rather than
    # the main config port, which may be different
    from ccbt.cli.main import _get_daemon_ipc_port
    from ccbt.daemon.daemon_manager import _get_daemon_home_dir
    import json
    
    # Diagnostic: Check if daemon config file exists
    home_dir = _get_daemon_home_dir()
    daemon_config_file = home_dir / ".ccbt" / "daemon" / "config.json"
    daemon_config_exists = daemon_config_file.exists()
    
    ipc_port = _get_daemon_ipc_port(cfg)
    client_host = "127.0.0.1"  # Always use 127.0.0.1 for client connections
    
    # Update splash if available
    if splash_manager:
        try:
            splash_manager.update_progress_message("Checking daemon status...")
        except Exception:
            pass  # Ignore errors updating splash
    
    # CRITICAL: If daemon config file doesn't exist, we may be using the wrong port
    # Try multiple ports: first the port from config, then default 8080
    ports_to_try = [ipc_port]
    if not daemon_config_exists:
        # Daemon config file doesn't exist - try default port as fallback
        default_port = 8080
        if default_port not in ports_to_try:
            ports_to_try.append(default_port)
        logger.info(
            "Daemon config file not found at %s. Will try ports: %s",
            daemon_config_file,
            ports_to_try
        )
        
        # CRITICAL: Use port scanning to find daemon if config file doesn't exist
        # This is especially useful when daemon is running in another terminal
        logger.info("Scanning for daemon on ports %s...", ports_to_try)
        found_port, found_client = await _scan_for_daemon_port(
            cfg.daemon.api_key,
            ports_to_try,
            timeout_per_port=2.0
        )
        
        if found_port and found_client:
            logger.info("Successfully found daemon on port %d via port scanning", found_port)
            if splash_manager:
                try:
                    splash_manager.update_progress_message("Daemon ready!")
                except Exception:
                    pass
            return (True, found_client)
        else:
            logger.info("Port scanning did not find daemon on any of the tried ports")
    else:
        try:
            with open(daemon_config_file, encoding="utf-8") as f:
                daemon_config = json.load(f)
                logger.info("Daemon config file found: ipc_port=%s, api_key present=%s",
                           daemon_config.get("ipc_port"), bool(daemon_config.get("api_key")))
        except Exception as e:
            logger.debug("Could not read daemon config file for diagnostics: %s", e)
    
    # Try each port with detailed health checks (fallback if port scanning didn't work)
    for port in ports_to_try:
        base_url = f"http://{client_host}:{port}"
        logger.info("Trying IPC port %d (base_url=%s, api_key present=%s)", 
                    port, base_url, bool(cfg.daemon and cfg.daemon.api_key))
        
        client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)
        
        # CRITICAL: First check if daemon is already healthy using ONLY IPC health check
        # This works even if PID file is missing or stale (e.g., daemon running in foreground)
        # We use a quick check first (5 seconds) to avoid unnecessary delays if daemon is ready
        logger.info("Checking if daemon is already healthy via IPC health check (base_url=%s)...", base_url)
        try:
            is_running = await client.is_daemon_running()
            if is_running:
                logger.info("Daemon is already running and healthy via IPC health check on port %d", port)
                if splash_manager:
                    try:
                        splash_manager.update_progress_message("Daemon ready!")
                    except Exception:
                        pass
                return (True, client)
            else:
                # Health check returned False - try to get more details by attempting a direct status call
                import aiohttp
                try:
                    status = await asyncio.wait_for(client.get_status(), timeout=2.0)
                    # If we got here, the connection worked but is_daemon_running returned False
                    # This shouldn't happen, but log it
                    logger.warning(
                        "get_status() succeeded but is_daemon_running() returned False on port %d. "
                        "This may indicate a daemon state issue.",
                        port
                    )
                except aiohttp.ClientResponseError as e:
                    if e.status in (401, 403):
                        logger.warning(
                            "Authentication failed on port %d (HTTP %d). API key mismatch detected. "
                            "The daemon may be using a different API key than the config.",
                            port, e.status
                        )
                    else:
                        logger.info(
                            "HTTP error %d on port %d: %s",
                            e.status, port, e.message
                        )
                except aiohttp.ClientConnectorError as e:
                    logger.info(
                        "Connection refused on port %d: %s. Daemon may not be listening on this port.",
                        port, e
                    )
                except Exception as e:
                    logger.info(
                        "Error checking daemon status on port %d: %s",
                        port, e
                    )
                
                logger.info(
                    "Daemon health check returned False (base_url=%s). "
                    "Possible causes: wrong port, API key mismatch, or daemon not ready.",
                    base_url
                )
        except Exception as check_error:
            logger.info(
                "Initial daemon health check exception (base_url=%s): %s",
                base_url,
                check_error
            )
            logger.debug("Full exception details:", exc_info=check_error)
        
        # Quick retry loop (2 seconds per port) in case daemon is starting up
        max_initial_wait = 2.0
        start_time = time.time()
        retry_delay = 0.5
        
        while time.time() - start_time < max_initial_wait:
            try:
                is_running = await client.is_daemon_running()
                if is_running:
                    logger.info("Daemon is already running and healthy via IPC health check on port %d", port)
                    if splash_manager:
                        try:
                            splash_manager.update_progress_message("Daemon ready!")
                        except Exception:
                            pass
                    return (True, client)
                else:
                    logger.debug(
                        "Daemon health check returned False (base_url=%s, attempt %d/%d)",
                        base_url,
                        int((time.time() - start_time) / retry_delay) + 1,
                        int(max_initial_wait / retry_delay)
                    )
            except Exception as check_error:
                logger.debug(
                    "Daemon health check exception during retry (base_url=%s): %s",
                    base_url,
                    check_error
                )
            
            await asyncio.sleep(retry_delay)
        
        # This port didn't work, close the client and try next port
        try:
            await client.close()
        except Exception:
            pass
    
    # None of the ports worked - create client with the primary port for the start attempt
    base_url = f"http://{client_host}:{ipc_port}"
    logger.info("None of the tried ports responded. Using primary port %d for daemon start attempt.", ipc_port)
    client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)
    
    # CRITICAL: If initial health check failed, daemon is not running
    # We do NOT check PID files or process status - ONLY IPC health checks
    # This ensures we only proceed when daemon is actually ready, not just when process exists
    logger.info("Daemon is not healthy via IPC health check, starting daemon...")
    
    if splash_manager:
        try:
            splash_manager.update_progress_message("Starting daemon...")
        except Exception:
            pass
    
    try:
        # Ensure daemon config exists
        config_manager = init_config()
        cfg = get_config()
        
        if not cfg.daemon or not cfg.daemon.api_key:
            api_key = generate_api_key()
            cfg.daemon = DaemonConfig(api_key=api_key)
            logger.info("Generated new API key for daemon")
        
        # Start daemon using CLI command for better isolation and error handling
        # This avoids SIGINT issues when starting as subprocess directly
        import subprocess
        import sys
        import shutil
        
        logger.info("Starting daemon using CLI command...")
        
        # Try to find the CLI command - prefer 'uv' if available
        # NOTE: We use --no-wait so CLI returns immediately after starting the process
        # Then we do our own health check loop that waits up to 90 seconds
        cli_command = None
        if shutil.which("uv"):
            cli_command = ["uv", "run", "btbt", "daemon", "start", "--no-wait"]
        elif shutil.which("btbt"):
            cli_command = ["btbt", "daemon", "start", "--no-wait"]
        else:
            # Fallback to Python module
            cli_command = [sys.executable, "-m", "ccbt.cli.main", "daemon", "start", "--no-wait"]
        
        logger.debug("Using CLI command: %s", " ".join(cli_command))
        logger.info("Starting daemon process...")
        
        # Start the CLI command in the background (don't wait for it to complete)
        # The CLI command will start the daemon process and return, but we don't wait for it
        # Instead, we use ONLY IPC health checks to detect when daemon is ready
        try:
            # Start the process without waiting
            process = subprocess.Popen(
                cli_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            # Give the CLI command a moment to start the daemon process
            await asyncio.sleep(2.0)
            
            # Check if CLI process completed with error
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                if process.returncode != 0:
                    error_output = stderr or stdout or "Unknown error"
                    # Check if error indicates daemon is already running
                    is_already_running_error = (
                        "already running" in error_output.lower() or
                        "aborted" in error_output.lower() or
                        process.returncode in (1, 130)
                    )
                    if is_already_running_error:
                        logger.info("CLI detected daemon is already running")
                    else:
                        logger.warning("CLI command returned error (exit code %d): %s", process.returncode, error_output[:200])
        except Exception as e:
            # CLI command failed, but daemon might have started anyway
            logger.warning("Error starting daemon via CLI: %s", e)
        
        # CRITICAL: Wait for daemon to be fully ready using ONLY IPC client health checks
        # The daemon can take up to 90 seconds to be ready (NAT discovery ~35s, DHT bootstrap ~8s, etc.)
        # We ONLY use IPC client health checks - no PID file or process checks
        # This ensures the interface only starts after daemon is confirmed healthy and ready
        
        # CRITICAL FIX: Wait for daemon config file to be created (up to 5 seconds)
        # The daemon writes its actual IPC port to the config file when it starts
        # This ensures we use the correct port for the health check
        logger.info("Waiting for daemon config file to be created...")
        config_wait_timeout = 5.0
        config_wait_start = time.time()
        actual_port = None
        
        while time.time() - config_wait_start < config_wait_timeout:
            if daemon_config_file.exists():
                try:
                    with open(daemon_config_file, encoding="utf-8") as f:
                        daemon_config = json.load(f)
                        actual_port = daemon_config.get("ipc_port")
                        if actual_port:
                            logger.info("Daemon config file created with port %d", actual_port)
                            break
                except Exception as e:
                    logger.debug("Error reading daemon config file: %s", e)
            await asyncio.sleep(0.2)
        
        # Use the port from daemon config file if available, otherwise fall back
        if actual_port:
            ipc_port = actual_port
            logger.info("Using IPC port %d from daemon config file", ipc_port)
        else:
            # Fallback: try to get port from helper (may still use main config)
            from ccbt.cli.main import _get_daemon_ipc_port
            ipc_port = _get_daemon_ipc_port(cfg)
            logger.info("Daemon config file not created yet, using port %d from config", ipc_port)
        
        client_host = "127.0.0.1"  # Always use 127.0.0.1 for client connections
        base_url = f"http://{client_host}:{ipc_port}"
        logger.info("Using IPC port %d for health check after daemon start (base_url=%s)", ipc_port, base_url)
        client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)
        
        # Update splash message before health check
        if splash_manager:
            try:
                splash_manager.update_progress_message("Waiting for daemon to be ready...")
            except Exception:
                pass
        
        # Use dedicated health check function that only uses IPC client
        is_healthy = await _wait_for_daemon_health_check(
            client,
            timeout=90.0,  # Full timeout for slow daemon startup (up to 90 seconds)
            check_interval=1.0,  # Check every second
        )
        
        if is_healthy:
            if splash_manager:
                try:
                    splash_manager.update_progress_message("Daemon ready!")
                except Exception:
                    pass
            return (True, client)
        else:
            # Timeout - daemon did not become healthy
            logger.error("Daemon did not become healthy within 90 seconds")
            await client.close()
            return (False, None)
        
    except Exception as e:
        logger.exception("Failed to start daemon")
        return (False, None)


def run_dashboard(  # pragma: no cover
    session: Any,  # DaemonInterfaceAdapter required
    refresh: float | None = None,
    dev_mode: bool = False,  # Enable Textual development mode
    splash_manager: Any | None = None,  # Splash manager to end when dashboard is rendered
) -> None:
    """Run the Textual dashboard App for the provided daemon session.
    
    Args:
        session: DaemonInterfaceAdapter instance (daemon session required)
        refresh: UI refresh interval in seconds
        dev_mode: Enable Textual development mode (live CSS editing, console integration)
        splash_manager: Splash manager to end when dashboard is fully rendered
        
    Raises:
        ValueError: If session is not a DaemonInterfaceAdapter
    """
    app = TerminalDashboard(session, refresh_interval=refresh or 1.0, splash_manager=splash_manager)
    
    if dev_mode:
        # Enable dev mode via environment variable (Textual checks this)
        import os
        os.environ["TEXTUAL_DEV"] = "1"
        # Also try using Textual's dev mode API if available
        try:
            from textual.dev import run_dev
            run_dev(app)
        except ImportError:
            # Fallback: run with dev environment variable set
            app.run()
    else:
        app.run()


def main() -> (
    int
):  # pragma: no cover - CLI entry point, requires full application context to test properly
    """Console entry for launching the TUI dashboard.

    Creates a session, optionally accepts --refresh, and starts the dashboard.
    ALWAYS uses daemon if available, auto-starts daemon if not running.
    """
    import argparse  # pragma: no cover - CLI entry point setup

    from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
    from ccbt.session.session import (
        AsyncSessionManager,  # pragma: no cover - Same context
    )

    parser = argparse.ArgumentParser(
        prog="bitonic", description="ccBT Terminal Dashboard"
    )  # pragma: no cover - Same context
    parser.add_argument(
        "--refresh", type=float, default=1.0, help="UI refresh interval in seconds"
    )  # pragma: no cover - Same context
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable Textual development mode (live CSS editing, console integration)",
    )  # pragma: no cover - Same context
    parser.add_argument(
        "--no-daemon",
        action="store_true",
        help="[DEPRECATED] Dashboard requires daemon - this option is ignored",
    )  # pragma: no cover - Same context
    parser.add_argument(
        "--no-splash",
        "-a",
        action="store_true",
        help="Disable splash screen (useful for debugging)",
    )  # pragma: no cover - Same context
    args = parser.parse_args()  # pragma: no cover - Same context

    # If Textual isn't available, provide a helpful message
    try:
        available = _TEXTUAL_AVAILABLE  # type: ignore[name-defined]  # pragma: no cover - Textual availability check, requires runtime environment
    except Exception:  # pragma: no cover - Exception handling for availability check
        available = False  # pragma: no cover - Same context
    if not available:  # pragma: no cover - Textual unavailable path, difficult to test without breaking imports
        _logger = logging.getLogger(__name__)  # pragma: no cover - Same context
        _logger.warning(
            "Textual is not installed. Install with: pip install 'textual>=0.73.0'"
        )  # pragma: no cover - Same context
        return 1  # pragma: no cover - Same context

    # CRITICAL: Dashboard ONLY works with daemon - no local sessions allowed
    session: DaemonInterfaceAdapter | None = None
    
    if args.no_daemon:
        # User requested --no-daemon but dashboard requires daemon
        logger.error(
            "Dashboard requires daemon to be running. "
            "Local sessions are not supported. "
            "Please ensure the daemon is running or start it with 'bitonic daemon start'"
        )
        return 1
    
    # Start splash screen if enabled
    splash_manager = None
    splash_thread = None
    if not args.no_splash:
        # Get verbosity count (defaults to 0 = NORMAL)
        verbosity_count = 0  # bitonic doesn't have verbosity flags, always NORMAL
        # Create a console for splash screen (will be cleared before Textual starts)
        from rich.console import Console
        splash_console = Console()
        splash_manager, splash_thread = _show_startup_splash(
            no_splash=args.no_splash,
            verbosity_count=verbosity_count,
            console=splash_console,  # Use console for splash, will be cleared before Textual
        )
    
    # ALWAYS use daemon - try to ensure it's running
    try:
        success, ipc_client = asyncio.run(_ensure_daemon_running(splash_manager=splash_manager))
        if success and ipc_client:
            # Create daemon interface adapter
            session = DaemonInterfaceAdapter(ipc_client)
            logger.info("Using daemon session via IPC")
        else:
            # Daemon start failed - show error and exit
            logger.error(
                "Failed to start daemon. Cannot proceed without daemon.\n"
                "Please check:\n"
                "  1. Daemon logs for startup errors\n"
                "  2. Port conflicts (check if port is already in use)\n"
                "  3. Permissions (ensure you have permission to start daemon)\n\n"
                "To start daemon manually: 'bitonic daemon start'"
            )
            return 1
    except Exception as e:
        logger.exception(
            "Error ensuring daemon is running: %s. Cannot proceed without daemon.",
            e
        )
        logger.error(
            "Dashboard requires daemon to be running. "
            "Please start the daemon with 'bitonic daemon start'"
        )
        return 1
    
    if session is None:
        logger.error("Failed to create session")
        return 1
    
    try:
        # TerminalDashboard.on_mount starts the session and metrics, but ensure availability
        run_dashboard(
            session, refresh=float(args.refresh), dev_mode=args.dev, splash_manager=splash_manager
        )  # pragma: no cover - Dashboard execution requires full app context
        return 0  # pragma: no cover - Same context
    finally:
        # Clear splash on exit
        if splash_manager:
            try:
                splash_manager.clear_progress_messages()
                # Restore log level if it was suppressed
                import logging
                root_logger = logging.getLogger()
                if hasattr(splash_manager, '_original_log_level'):
                    root_logger.setLevel(splash_manager._original_log_level)
            except Exception:
                pass
        
        # Best-effort cleanup; on_unmount also stops services
        with contextlib.suppress(
            Exception
        ):  # pragma: no cover - Cleanup exception handling
            # CRITICAL FIX: Proper cleanup for Windows socket buffer exhaustion
            import asyncio as _asyncio
            import sys
            
            # On Windows, add delay before cleanup to allow socket buffers to drain
            if sys.platform == "win32":
                try:
                    # Small delay to allow socket cleanup
                    # Note: Can't use await in finally block, so only delay if loop is not running
                    if not _asyncio.get_event_loop_policy().get_event_loop().is_running():
                        _asyncio.run(asyncio.sleep(0.1))
                except Exception:
                    pass  # Ignore errors during delay
            
            # AsyncSessionManager.stop is async; schedule via asyncio.run if needed
            if (
                _asyncio.get_event_loop_policy().get_event_loop().is_running()
            ):  # pragma: no cover - Event loop check in cleanup
                # In case we're inside a running loop (rare for console entry), create a task
                task = _asyncio.create_task(session.stop())  # type: ignore[attr-defined]  # pragma: no cover - Same context
                task.add_done_callback(
                    lambda _t: None
                )  # pragma: no cover - Same context
            else:
                _asyncio.run(session.stop())  # type: ignore[attr-defined]  # pragma: no cover - Same context

