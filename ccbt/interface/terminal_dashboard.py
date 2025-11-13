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
from ccbt.interface.widgets import (
    Overview,
    PeersTable,
    SparklineGroup,
    SpeedSparklines,
    TorrentsTable,
)
from ccbt.monitoring import get_alert_manager, get_metrics_collector
from ccbt.storage.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

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
# Terminal Dashboard Application
# ============================================================================


class TerminalDashboard(App):  # type: ignore[misc]
    """Textual dashboard application."""

    CSS = """
    Screen { layout: vertical; }
    #body { layout: horizontal; height: 1fr; }
    #left, #right { width: 1fr; }
    #left { layout: vertical; }
    #right { layout: vertical; }
    #overview {
        height: 1fr;
        min-height: 8;
    }
    #speeds {
        height: 1fr;
        min-height: 5;
    }
    #torrents { height: 2fr; }
    #peers { height: 1fr; }
    #details { height: 1fr; }
    #logs { height: 1fr; }
    Footer {
        height: auto;
        min-height: 1;
        max-height: 10;
        overflow-y: auto;
        overflow-x: hidden;
    }
    """

    def __init__(
        self, session: AsyncSessionManager, refresh_interval: float = 1.0
    ):  # pragma: no cover
        """Initialize terminal dashboard."""
        super().__init__()
        self.session = session
        
        # Initialize translations
        try:
            config = get_config()
            TranslationManager(config)
        except Exception:
            # Fallback if config not available
            TranslationManager(None)
        
        # Detect if using DaemonInterfaceAdapter
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        self._is_daemon_session = isinstance(session, DaemonInterfaceAdapter)
        
        # Reduce polling frequency when using daemon (WebSocket provides real-time updates)
        if self._is_daemon_session:
            # Use longer refresh interval for daemon (WebSocket handles real-time updates)
            self.refresh_interval = max(2.0, float(refresh_interval) * 2.0)
        else:
            self.refresh_interval = max(0.2, float(refresh_interval))
        
        self.alert_manager = get_alert_manager()
        self.metrics_collector = get_metrics_collector()
        self._poll_task: asyncio.Task | None = None
        self._filter_input: Input | None = None
        self._filter_text: str = ""
        self._last_status: dict[str, dict[str, Any]] = {}
        self._compact = False
        # Command executor for CLI command integration
        self._command_executor = CommandExecutor(session)
        # Widget references will be set in on_mount after compose
        self.overview: Overview | None = None
        self.speeds: SpeedSparklines | None = None
        self.torrents: TorrentsTable | None = None
        self.peers: PeersTable | None = None
        self.details: Static | None = None
        self.statusbar: Static | None = None
        self.alerts: Static | None = None
        self.logs: RichLog | None = None

    def _format_bindings_display(self) -> Any:  # pragma: no cover
        """Format all key bindings grouped by category for display."""
        # Group bindings by category
        categories = {
            "Torrent Control": [
                ("p", "Pause torrent"),
                ("r", "Resume torrent"),
            ],
            "Add Torrents": [
                ("i", "Quick add torrent"),
                ("o", "Advanced add torrent"),
                ("b", "Browse and add torrent"),
            ],
            "Configuration": [
                ("g", "Global config"),
                ("t", "Torrent config"),
            ],
            "Monitoring": [
                ("s", "System resources"),
                ("m", "Performance metrics"),
                ("n", "Network quality"),
                ("h", "Historical trends"),
                ("a", "Alerts dashboard"),
                ("e", "Metrics explorer"),
            ],
            "Protocols (Ctrl+)": [
                ("Ctrl+X", "Xet management"),
                ("Ctrl+I", "IPFS management"),
                ("Ctrl+S", "SSL config"),
                ("Ctrl+P", "Proxy config"),
                ("Ctrl+R", "Scrape results"),
                ("Ctrl+N", "NAT management"),
                ("Ctrl+U", "uTP config"),
            ],
            "Navigation": [
                ("Ctrl+M", "Navigation menu"),
                ("?", "Help screen"),
            ],
            "General": [
                ("q", "Quit"),
                ("x", "Security scan"),
            ],
        }

        # Create a table with two columns for better layout
        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column("Key", style="cyan bold", ratio=1)
        table.add_column("Action", style="white", ratio=2)

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
        with Horizontal(id="body"):
            with Container(id="left"):
                yield Overview(id="overview")
                yield SpeedSparklines(id="speeds")
            with Container(id="right"):
                yield TorrentsTable(id="torrents")
                yield PeersTable(id="peers")
                yield Static(id="details")
                yield RichLog(id="logs")
        yield Static(id="statusbar")
        yield Container(Static(id="alerts"))
        yield Footer()

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("p", "pause_torrent", _("Pause")),
        ("r", "resume_torrent", _("Resume")),
        ("q", "quit", _("Quit")),
        ("i", "quick_add_torrent", _("Quick Add")),
        ("o", "advanced_add_torrent", _("Advanced Add")),
        ("b", "browse_add_torrent", _("Browse")),
        ("g", "global_config", _("Global Config")),
        ("t", "torrent_config", _("Torrent Config")),
        ("s", "system_resources", _("System Resources")),
        ("m", "performance_metrics", _("Performance")),
        ("n", "network_quality", _("Network")),
        ("h", "historical_trends", _("History")),
        ("a", "alerts_dashboard", _("Alerts")),
        ("e", "metrics_explorer", _("Explore")),
        ("x", "security_scan", _("Security Scan")),
        ("?", "help", _("Help")),
        ("ctrl+x", "xet_management", _("Xet")),
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
        # Get widget references after compose
        self.overview = self.query_one("#overview", Overview)
        self.speeds = self.query_one("#speeds", SpeedSparklines)
        self.torrents = self.query_one("#torrents", TorrentsTable)
        self.peers = self.query_one("#peers", PeersTable)
        self.details = self.query_one("#details", Static)
        self.statusbar = self.query_one("#statusbar", Static)
        self.alerts = self.query_one("#alerts", Static)
        self.logs = self.query_one("#logs", RichLog)

        # Set up custom logging handler to capture errors in RichLog widget
        self._setup_logging_handler()

        # Start the session and begin polling
        try:
            await self.session.start()
            
            # If using DaemonInterfaceAdapter, WebSocket subscription is already handled in adapter.start()
            # Register callbacks for real-time updates
            if self._is_daemon_session:
                # Set up event callbacks for WebSocket updates
                from ccbt.daemon.ipc_protocol import EventType
                
                def on_torrent_status_changed(data: dict[str, Any]) -> None:
                    """Handle torrent status change event."""
                    # Trigger UI refresh
                    self._schedule_poll()
                
                self.session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.TORRENT_STATUS_CHANGED,
                    on_torrent_status_changed,
                )
                logger.info("Daemon session adapter started with WebSocket subscription")
        except Exception as e:
            logger.exception("Failed to start session: %s", e)
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
        
        # Start polling (reduced frequency for daemon sessions)
        self.set_interval(self.refresh_interval, self._schedule_poll)
        
        # Update status bar with connection status
        self._update_connection_status()

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
                        
                        # Format message with Rich markup based on level
                        if record.levelno >= logging.ERROR:
                            formatted_msg = f"[red]{record.levelname}[/red] {record.getMessage()}"
                        elif record.levelno >= logging.WARNING:
                            formatted_msg = f"[yellow]{record.levelname}[/yellow] {record.getMessage()}"
                        else:
                            formatted_msg = f"{record.levelname} {record.getMessage()}"
                        
                        # Add correlation ID if available
                        if hasattr(record, "correlation_id"):
                            formatted_msg = f"[dim][{record.correlation_id}][/dim] {formatted_msg}"
                        
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

            # Handle DaemonInterfaceAdapter (can't access piece_manager directly)
            if self._is_daemon_session:
                # For DaemonInterfaceAdapter, torrents dict contains status objects, not sessions
                # We can't access piece_manager directly, so return limited metrics
                torrent_status = await self.session.get_torrent_status(info_hash_hex)
                if not torrent_status:
                    return {}
                # Return basic metrics from status
                return {
                    "status": torrent_status.get("status", "unknown"),
                    "progress": torrent_status.get("progress", 0.0),
                    "name": torrent_status.get("name", "Unknown"),
                    "download_rate": torrent_status.get("download_rate", 0.0),
                    "upload_rate": torrent_status.get("upload_rate", 0.0),
                    "total_downloaded_bytes": torrent_status.get("downloaded", 0),
                    "total_uploaded_bytes": torrent_status.get("uploaded", 0),
                    "connection_count": torrent_status.get("peers", 0),
                }
            
            # For AsyncSessionManager, get torrent session
            torrent_session = self.session.torrents.get(info_hash_bytes)
            if not torrent_session:
                return {}

            metrics: dict[str, Any] = {}

            # Get basic status
            status = await self.session.get_status()
            torrent_status = status.get(info_hash_hex, {})

            # Pieces information from piece manager
            if (
                hasattr(torrent_session, "piece_manager")
                and torrent_session.piece_manager
            ):
                try:
                    piece_stats = torrent_session.piece_manager.get_stats()
                    metrics["pieces_completed"] = piece_stats.get("completed_pieces", 0)
                    metrics["pieces_total"] = piece_stats.get("total_pieces", 0)
                    metrics["pieces_verified"] = piece_stats.get("verified_pieces", 0)
                    metrics["pieces_missing"] = piece_stats.get("missing_pieces", 0)
                    metrics["pieces_downloading"] = piece_stats.get(
                        "downloading_pieces", 0
                    )
                    metrics["piece_progress"] = piece_stats.get("progress", 0.0)
                    metrics["endgame_mode"] = piece_stats.get("endgame_mode", False)
                except Exception:
                    pass

            # Bytes downloaded/uploaded
            try:
                metrics["total_downloaded_bytes"] = torrent_session.downloaded_bytes()
                metrics["total_uploaded_bytes"] = torrent_session.uploaded_bytes()
                metrics["left_bytes"] = torrent_session.left_bytes()
            except Exception:
                metrics["total_downloaded_bytes"] = torrent_status.get(
                    "downloaded_bytes", 0
                )
                metrics["total_uploaded_bytes"] = torrent_status.get(
                    "uploaded_bytes", 0
                )
                metrics["left_bytes"] = torrent_status.get("left_bytes", 0)

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
                peers = await self.session.get_peers_for_torrent(info_hash_hex)
                metrics["connection_count"] = len(peers) if peers else 0
            except Exception:
                metrics["connection_count"] = torrent_status.get("peer_count", 0)

            # Piece availability (from piece manager if available)
            if (
                hasattr(torrent_session, "piece_manager")
                and torrent_session.piece_manager
                and hasattr(torrent_session.piece_manager, "peer_availability")
            ):
                try:
                    peer_availability = torrent_session.piece_manager.peer_availability
                    if peer_availability:
                        # Calculate average availability
                        total_pieces = metrics.get("pieces_total", 0)
                        if total_pieces > 0:
                            total_availability = sum(
                                len(peers) for peers in peer_availability.values()
                            )
                            metrics["piece_availability_avg"] = (
                                total_availability / total_pieces
                            )
                        else:
                            metrics["piece_availability_avg"] = 0.0
                    else:
                        metrics["piece_availability_avg"] = 0.0
                except Exception:
                    metrics["piece_availability_avg"] = None

            # Add status information
            metrics["status"] = torrent_status.get("status", "unknown")
            metrics["progress"] = torrent_status.get("progress", 0.0)
            metrics["name"] = torrent_status.get("name", "Unknown")

            return metrics

        except Exception as e:
            logger.debug("Error getting detailed metrics for %s: %s", info_hash_hex, e)
            return {}

    async def _poll_once(self) -> None:  # pragma: no cover
        # Background polling task - requires widget tree and full app context
        try:
            # Check daemon connection status if using DaemonInterfaceAdapter
            if self._is_daemon_session:
                try:
                    # Verify daemon is still accessible
                    if hasattr(self.session, "_client"):
                        is_running = await self.session._client.is_daemon_running()  # type: ignore[attr-defined]
                        if not is_running:
                            # Daemon connection lost
                            if self.statusbar:
                                self.statusbar.update(
                                    Panel(
                                        "[red]●[/red] Daemon connection lost - attempting to reconnect...",
                                        title="Status",
                                        border_style="red",
                                    )
                                )
                            logger.warning("Daemon connection lost during poll")
                            # Try to refresh cache (will attempt reconnection)
                            if hasattr(self.session, "_refresh_cache"):
                                await self.session._refresh_cache()  # type: ignore[attr-defined]
                except Exception as conn_error:
                    logger.debug("Error checking daemon connection: %s", conn_error)
            
            stats = await self.session.get_global_stats()
            # Some tests construct the app without mounting widgets; guard None
            if getattr(self, "overview", None) is not None:
                self.overview.update_from_stats(stats)
            if getattr(self, "speeds", None) is not None:
                self.speeds.update_from_stats(stats)
            all_status = await self.session.get_status()
            self._last_status = all_status
            self._apply_filter_and_update()
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
                    # For DaemonInterfaceAdapter, get_peers_for_torrent may return empty list
                    # This is expected as IPC doesn't provide detailed peer info
                    peers = await self.session.get_peers_for_torrent(ih)
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
                det.add_row("Tracker", tracker_status_display)

                # Show last tracker error if present
                last_tracker_error = st.get("last_tracker_error")
                if last_tracker_error:
                    det.add_row(
                        "Tracker Error", f"[red]{str(last_tracker_error)[:50]}[/red]"
                    )

                # Show last error if present
                last_error = st.get("last_error")
                if last_error:
                    det.add_row("Last Error", f"[red]{str(last_error)[:50]}[/red]")

                # Get scrape result (BEP 48)
                scrape_result = None
                with contextlib.suppress(Exception):
                    scrape_result = await self.session.get_scrape_result(ih)

                if scrape_result:
                    det.add_row("Seeders (Scrape)", str(scrape_result.seeders))
                    det.add_row("Leechers (Scrape)", str(scrape_result.leechers))
                    det.add_row("Completed (Scrape)", str(scrape_result.completed))
                    if hasattr(scrape_result, "scrape_count"):
                        det.add_row("Scrape Count", str(scrape_result.scrape_count))
                    if (
                        hasattr(scrape_result, "last_scrape_time")
                        and scrape_result.last_scrape_time > 0
                    ):
                        import time

                        elapsed = time.time() - scrape_result.last_scrape_time
                        det.add_row("Last Scrape", f"{elapsed:.0f}s ago")
                else:
                    det.add_row("Scrape", "[dim]No data (press 's' to scrape)[/dim]")

                if getattr(self, "details", None) is not None:
                    self.details.update(Panel(det, title="Details"))
            elif getattr(self, "details", None) is not None:
                # Show key bindings when no torrent is selected
                bindings_display = self._format_bindings_display()
                self.details.update(Panel(bindings_display, title="Key Bindings"))
            # Update status bar counters with connection status
            connection_status = self._get_connection_status()
            sb = f"{connection_status}  Torrents: {stats.get('num_torrents', 0)}  Active: {stats.get('num_active', 0)}  Paused: {stats.get('num_paused', 0)}  Seeding: {stats.get('num_seeding', 0)}  D: {float(stats.get('download_rate', 0.0)):.0f}B/s  U: {float(stats.get('upload_rate', 0.0)):.0f}B/s"
            if getattr(self, "statusbar", None) is not None:
                self.statusbar.update(Panel(sb, title="Status"))
            # Show alert rules and active alerts
            if getattr(self.alert_manager, "alert_rules", None):
                rules_table = Table(title=_("Alert Rules"), expand=True)
                rules_table.add_column("Name", style="cyan")
                rules_table.add_column("Metric")
                rules_table.add_column("Condition")
                rules_table.add_column("Severity", style="red")
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
                act_table.add_column("Severity", style="red")
                act_table.add_column("Rule", style="yellow")
                act_table.add_column("Value")
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
            logger.exception("Error in dashboard poll: %s", e)

            # Render error where overview goes but don't break the UI
            error_msg = f"Error: {str(e)[:100]}"
            if getattr(self, "overview", None) is not None:
                self.overview.update(
                    Panel(error_msg, title="Dashboard Error", border_style="red")
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
        
        # Stop session (DaemonInterfaceAdapter will close WebSocket and IPC connection)
        with contextlib.suppress(Exception):
            await self.session.stop()
        
        # Stop metrics collector
        with contextlib.suppress(Exception):
            await self.metrics_collector.stop()

    # Key bindings
    async def on_key(self, event: events.Key) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle key press events."""
        # Textual event handler - requires full event system and widget tree to test
        # Testing would require complex Textual app setup and event simulation
        if event.key in ("q", "Q"):
            await self.action_quit()
            return
        if event.key in ("delete",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                # Basic inline confirm: press 'y' to confirm deletion
                self.overview.update(
                    Panel(
                        f"Delete torrent {ih[:16]}…? Press 'y' to confirm or 'n' to cancel",
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
                    await self.session.remove(ih)
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
                    await self.session.pause_torrent(ih)
                    self.logs.write(f"Paused {ih}")
            return
        if event.key in ("r", "R"):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    await self.session.resume_torrent(ih)
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
                    ok = await self.session.force_announce(ih)
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
            # Force scrape (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.force_scrape(ih)
                self.statusbar.update(
                    Panel(_("Scrape: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                )
                self.logs.write(f"Scrape {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("e", "E"):
            # Refresh PEX (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.refresh_pex(ih)
                self.statusbar.update(
                    Panel(_("PEX: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                )
                self.logs.write(f"PEX {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("h", "H"):
            # Rehash (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.rehash_torrent(ih)
                self.statusbar.update(
                    Panel(_("Rehash: {status}").format(status=_("OK") if ok else _("Failed")), title=_("Status")),
                )
                self.logs.write(f"Rehash {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("x", "X"):
            # Export snapshot
            from pathlib import Path

            p = Path("dashboard_snapshot.json")
            try:
                await self.session.export_session_state(p)
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
                    await self.session.set_rate_limits(ih, 0, 0)
                    self.statusbar.update(Panel(_("Rate limits disabled"), title=_("Status")))
                    self.logs.write(f"Rate limits disabled for {ih}")
            return
        if event.key in ("2",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    await self.session.set_rate_limits(ih, 1024, 1024)
                    self.statusbar.update(
                        Panel(_("Rate limits set to 1024 KiB/s"), title=_("Status")),
                    )
                    self.logs.write(f"Rate limits set to 1024/1024 KiB/s for {ih}")
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
                    Panel(f"Metrics interval: {new_iv}s", title="Status"),
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
                Panel(f"UI refresh interval: {self.refresh_interval}s", title="Status"),
            )
            return
        if event.key in ("t", "T"):
            # Toggle light/dark theme
            with contextlib.suppress(Exception):
                self.dark = not self.dark  # type: ignore[attr-defined]
                self.statusbar.update(
                    Panel(f"Theme: {'Dark' if self.dark else 'Light'}", title="Status"),
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
            await self._process_add_torrent(path_or_magnet, {})
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
        elif message.input.id == "add_torrent_browse":
            path_or_magnet = message.value.strip()
            # CRITICAL FIX: Strip quotes from path (Windows paths may have quotes from copy/paste)
            if path_or_magnet and not path_or_magnet.startswith("magnet:"):
                path_or_magnet = path_or_magnet.strip('"').strip("'")
            message.input.display = False
            # Validate input before processing
            if not path_or_magnet:
                self.logs.write(
                    "[red]Error: No torrent path or magnet link provided[/red]"
                )
                return
            if not path_or_magnet.startswith("magnet:") and len(path_or_magnet) < 3:
                self.logs.write("[red]Error: Invalid torrent path or magnet link[/red]")
                return
            await self._process_add_torrent(path_or_magnet, {})

    def _apply_filter_and_update(self) -> None:  # pragma: no cover
        # UI helper method - requires widget tree to test properly
        status = self._last_status
        if not self._filter_text:
            self.torrents.update_from_status(status)
            return
        filt = self._filter_text.lower()
        filtered: dict[str, dict[str, Any]] = {}
        for ih, st in status.items():
            name = str(st.get("name", "")).lower()
            state = str(st.get("status", "")).lower()
            if (filt in name) or (filt in state):
                filtered[ih] = st
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
                                formatted or f"Command '{cmd}' executed successfully",
                                title="Success",
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed: {message}")
                    except Exception:
                        # Fallback to simple text
                        self.statusbar.update(
                            Panel(
                                message or f"Command '{cmd}' executed successfully",
                                title="Success",
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
                        message or f"Command '{cmd}' failed",
                        title="Error",
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
                                formatted or f"Command '{cmd}' executed successfully",
                                title="Success",
                                border_style="green",
                            )
                        )
                        self.logs.write(f"Command '{cmd}' executed: {message}")
                    except Exception:
                        # Fallback to simple text
                        self.statusbar.update(
                            Panel(
                                message or f"Command '{cmd}' executed successfully",
                                title="Success",
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
                        message or f"Command '{cmd}' failed",
                        title="Error",
                        border_style="red",
                    )
                )
                self.logs.write(f"Command '{cmd}' error: {message}")
            return

        # Legacy command handlers (for backward compatibility)
        try:
            if cmd == "pause" and ih:
                await self.session.pause_torrent(ih)
                self.logs.write(f"Paused {ih}")
            elif cmd == "resume" and ih:
                await self.session.resume_torrent(ih)
                self.logs.write(f"Resumed {ih}")
            elif cmd == "remove" and ih:
                await self.session.remove(ih)
                self.logs.write(f"Removed {ih}")
            elif cmd == "announce" and ih:
                await self.session.force_announce(ih)
                self.logs.write(f"Announce sent {ih}")
            elif cmd == "scrape" and ih:
                await self.session.force_scrape(ih)
                self.logs.write(f"Scrape requested {ih}")
            elif cmd == "pex" and ih:
                await self.session.refresh_pex(ih)
                self.logs.write(f"PEX refresh {ih}")
            elif cmd == "rehash" and ih:
                await self.session.rehash_torrent(ih)
                self.logs.write(f"Rehash {ih}")
            elif cmd == "limit" and ih and len(parts) >= 3:
                await self.session.set_rate_limits(ih, int(parts[1]), int(parts[2]))
                self.logs.write(f"Set limits {parts[1]}/{parts[2]} KiB/s for {ih}")
            elif cmd == "backup" and ih and len(parts) >= 2:
                from pathlib import Path

                await self.session.checkpoint_backup_torrent(ih, Path(parts[1]))
                self.logs.write(f"Backup checkpoint to {parts[1]} for {ih}")
            elif cmd == "restore" and len(parts) >= 2:
                # Restore checkpoint from backup file
                from pathlib import Path

                cm = CheckpointManager(self.session.config.disk)
                await cm.restore_checkpoint(Path(parts[1]))
                self.logs.write(f"Restored checkpoint from {parts[1]}")
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
        # Check if input widget already exists
        try:
            existing = self.query_one("#add_torrent", expect_type=Input)
            # If it exists, just focus it, clear it, and make sure it's visible
            existing.value = ""
            existing.display = True
            existing.focus()
            return
        except Exception:
            # Widget doesn't exist, create a new one
            pass

        input_widget = Input(placeholder="File path or magnet link", id="add_torrent")
        self.mount(input_widget)
        input_widget.focus()

    async def _advanced_add_torrent(self) -> None:  # pragma: no cover
        # UI interaction method - requires Textual Input widget and mount context
        """Advanced add torrent with configuration options."""
        # Use the new AddTorrentScreen for comprehensive options
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

    def _apply_torrent_options(
        self, options: dict[str, Any]
    ) -> None:  # pragma: no cover
        """Apply torrent-specific options to session config (matching CLI behavior).

        This applies the same overrides that the CLI uses via _apply_cli_overrides,
        ensuring the terminal dashboard matches CLI behavior.
        """
        try:
            # Import CLI override functions (may fail if circular import)
            from ccbt.cli.main import _apply_cli_overrides

            # Apply CLI overrides to session config
            # This matches the CLI behavior exactly
            # self.session.config is a ConfigManager, not a Config
            config_manager = self.session.config
            _apply_cli_overrides(config_manager, options)
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
        cfg = self.session.config.config

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
        """Process torrent addition with enhanced features.

        Supports:
        - File selection (files_selection, file_priorities)
        - Queue priority
        - Checkpoint resume detection
        - Private torrent warnings
        - Rate limits
        - All CLI options (via _apply_torrent_options)
        """
        # CRITICAL FIX: Ensure session manager is started to initialize DHT and other components
        # Check if session is already started by checking if background tasks exist
        if (
            not hasattr(self.session, "_cleanup_task")
            or self.session._cleanup_task is None
        ):
            self.logs.write("[yellow]Starting session manager...[/yellow]")
            await self.session.start()

        # UI helper - updates statusbar/logs widgets which require UI context
        # Validate input first
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
        # CRITICAL FIX: Strip quotes from path (Windows paths may have quotes from copy/paste)
        if path_or_magnet and not path_or_magnet.startswith("magnet:"):
            path_or_magnet = path_or_magnet.strip('"').strip("'")

        # Basic validation: must be magnet link or valid-looking path
        if not path_or_magnet.startswith("magnet:"):
            # Check if it looks like a valid file path (has extension or is absolute path)
            path_obj = Path(path_or_magnet)
            if (
                not path_obj.exists()
                and not path_obj.is_absolute()
                and "." not in path_obj.name
            ):
                self.logs.write(
                    f"[red]Error: Invalid torrent path: {path_or_magnet[:50]}[/red]"
                )
                self.statusbar.update(
                    Panel(
                        "Error: Invalid torrent path or magnet link",
                        title="Error",
                        border_style="red",
                    )
                )
                return

        # Log the addition attempt
        self.logs.write(f"Adding torrent: {path_or_magnet[:50]}...")

        # Apply config overrides BEFORE adding torrent (matching CLI behavior)
        try:
            self._apply_torrent_options(options)
        except Exception as e:
            # Log but don't fail - some options might not be applicable
            logger.debug("Failed to apply some torrent options: %s", e)

        try:
            # Step 1: Check for checkpoint if resume not explicitly set
            resume = options.get("resume", False)
            if not resume and self.session.config.disk.checkpoint_enabled:
                # Try to detect checkpoint before adding torrent
                # For file paths, we need to load torrent first to get info_hash
                try:
                    if not path_or_magnet.startswith("magnet:"):
                        # Load torrent to get info_hash (run in thread to avoid blocking UI)
                        loop = asyncio.get_event_loop()
                        torrent_data = await loop.run_in_executor(
                            None, self.session.load_torrent, Path(path_or_magnet)
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

                                checkpoint_manager = CheckpointManager(
                                    self.session.config.disk
                                )
                                # Add timeout to checkpoint loading to prevent hanging
                                try:
                                    checkpoint = await asyncio.wait_for(
                                        checkpoint_manager.load_checkpoint(
                                            info_hash_bytes
                                        ),
                                        timeout=10.0,  # 10 second timeout for checkpoint loading
                                    )
                                except asyncio.TimeoutError:
                                    self.logs.write(
                                        "Warning: Timeout loading checkpoint, continuing without resume"
                                    )
                                    checkpoint = None

                                if checkpoint:
                                    # Show checkpoint info and prompt - make it very visible
                                    verified = len(
                                        getattr(checkpoint, "verified_pieces", [])
                                    )
                                    total = getattr(checkpoint, "total_pieces", 0)
                                    torrent_name = getattr(
                                        checkpoint, "torrent_name", "Unknown"
                                    )
                                    progress_pct = (
                                        (verified / total * 100) if total > 0 else 0
                                    )

                                    # Show in both statusbar and logs for visibility
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
                                    self._pending_checkpoint_resume = (  # type: ignore[attr-defined]
                                        info_hash_bytes
                                    )
                                    self._pending_checkpoint_path = path_or_magnet  # type: ignore[attr-defined]
                                    self._pending_checkpoint_options = options.copy()  # type: ignore[attr-defined]

                                    # Auto-resume after 5 seconds if no user input
                                    async def auto_resume_after_timeout():
                                        await asyncio.sleep(5.0)
                                        # Check if still pending (user didn't respond)
                                        if (
                                            getattr(
                                                self, "_pending_checkpoint_resume", None
                                            )
                                            == info_hash_bytes
                                        ):
                                            self.logs.write(
                                                "Auto-resuming from checkpoint (no user response)"
                                            )
                                            options["resume"] = True
                                            self._pending_checkpoint_resume = None  # type: ignore[attr-defined]
                                            self._pending_checkpoint_path = None  # type: ignore[attr-defined]
                                            self._pending_checkpoint_options = None  # type: ignore[attr-defined]
                                            await self._process_add_torrent(
                                                path_or_magnet, options
                                            )

                                    # Start auto-resume task
                                    asyncio.create_task(auto_resume_after_timeout())

                                    # User can still confirm via key handler (y/n) before timeout
                                    return
                except Exception as e:
                    # If checkpoint check fails, continue with normal addition
                    logger.debug("Checkpoint check failed: %s", e)

            # Step 2: Check for private torrent warning (before adding)
            is_private = False
            try:
                if not path_or_magnet.startswith("magnet:"):
                    # Load torrent in thread to avoid blocking UI
                    loop = asyncio.get_event_loop()
                    torrent_data = await loop.run_in_executor(
                        None, self.session.load_torrent, Path(path_or_magnet)
                    )
                    if torrent_data:
                        is_private = (
                            torrent_data.get("is_private", False)
                            if isinstance(torrent_data, dict)
                            else getattr(torrent_data, "is_private", False)
                        )
            except Exception:
                pass  # Continue even if private check fails

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

            # Step 3: Add torrent
            # The async operations should yield properly, but we'll await directly
            # The blocking file I/O has been fixed, so this should be responsive
            # Add timeout to prevent indefinite hanging, but make it longer for large torrents
            # Calculate timeout based on torrent size (minimum 60s, up to 300s for very large torrents)
            if path_or_magnet.startswith("magnet:"):
                # For magnet links, we don't know the size yet, use a reasonable default
                timeout_seconds = 120.0  # 2 minutes for magnet links
            else:
                # For file torrents, calculate based on size
                torrent_size = (
                    torrent_data.get("file_info", {}).get("total_length", 0)
                    if torrent_data
                    else 0
                )
                # Base timeout of 60s, add 1s per 100MB (capped at 300s total)
                timeout_seconds = min(
                    60.0 + (torrent_size / (100 * 1024 * 1024)), 300.0
                )

            # Show progress message
            self.logs.write(f"Adding torrent (timeout: {timeout_seconds:.0f}s)...")
            self.statusbar.update(
                Panel(
                    "Adding torrent... This may take a moment for large torrents.",
                    title="Adding Torrent",
                    border_style="blue",
                )
            )

            # Handle output directory before adding torrent
            # Note: Session manager uses self.output_dir, so we temporarily set it
            # if a per-torrent output is specified
            original_output_dir = self.session.output_dir
            output_dir = options.get("output")
            if output_dir:
                # Temporarily change session output_dir for this torrent
                # This is a workaround since add_torrent doesn't accept output_dir parameter
                self.session.output_dir = str(output_dir)
                self.logs.write(f"Using output directory: {output_dir}")

            try:
                if path_or_magnet.startswith("magnet:"):
                    info_hash = await asyncio.wait_for(
                        self.session.add_magnet(
                            path_or_magnet,
                            resume=resume,
                        ),
                        timeout=timeout_seconds,
                    )
                else:
                    info_hash = await asyncio.wait_for(
                        self.session.add_torrent(
                            path_or_magnet,
                            resume=resume,
                        ),
                        timeout=timeout_seconds,
                    )
            except asyncio.TimeoutError:
                error_msg = (
                    f"Timeout adding torrent (operation took longer than {timeout_seconds:.0f} seconds). "
                    "This may happen with very large torrents or slow disk I/O. "
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
                # Restore original output_dir before returning
                if output_dir:
                    self.session.output_dir = original_output_dir
                # Don't raise - let the user know but don't crash the UI
                # The torrent might still be added, just taking longer
                return
            except ValueError as add_error:
                # Handle duplicate torrent/magnet errors gracefully
                error_msg = str(add_error)
                logger.warning(error_msg)
                self.statusbar.update(
                    Panel(
                        error_msg,
                        title="Torrent Already Exists",
                        border_style="yellow",
                    ),
                )
                self.logs.write(f"[yellow]Warning: {error_msg}[/yellow]")
                # Restore original output_dir before returning
                if output_dir:
                    self.session.output_dir = original_output_dir
                # Don't raise - show user-friendly message instead of crashing
                return
            except Exception as add_error:
                # Restore original output_dir before re-raising
                if output_dir:
                    self.session.output_dir = original_output_dir
                # Re-raise to be caught by outer exception handler
                raise
            finally:
                # Restore original output_dir after adding torrent (if not already restored)
                if output_dir and self.session.output_dir != original_output_dir:
                    self.session.output_dir = original_output_dir

            # Show immediate success message - torrent is added!
            self.statusbar.update(
                Panel(
                    f"Successfully added torrent: {info_hash[:12]}...\n"
                    f"Status: Download starting (checking peers...)",
                    title="Success",
                    border_style="green",
                ),
            )
            self.logs.write(f"✓ Successfully added torrent: {path_or_magnet}")

            # Wait a moment and check if download has started
            await asyncio.sleep(1.0)
            try:
                # Get torrent status to confirm it's downloading
                info_hash_bytes = bytes.fromhex(info_hash)
                async with self.session.lock:
                    torrent_session = self.session.torrents.get(info_hash_bytes)

                if torrent_session:
                    status = await torrent_session.get_status()
                    download_status = status.get("status", "unknown")
                    connected_peers = status.get("connected_peers", 0)

                    if download_status == "downloading":
                        self.logs.write(
                            f"✓ Download confirmed: {connected_peers} peer(s) connected"
                        )
                        self.statusbar.update(
                            Panel(
                                f"Download active: {connected_peers} peer(s) connected\n"
                                f"Status: {download_status}",
                                title="Download Status",
                                border_style="green",
                            ),
                        )
                    else:
                        self.logs.write(
                            f"Download status: {download_status} (may be initializing...)"
                        )
            except Exception as e:
                # Don't fail if status check fails - torrent might still be initializing
                logger.debug("Error checking download status: %s", e)

            # Step 4: Apply file selection if specified (with timeout to prevent hanging)
            # These are optional post-add configurations
            files_selection = options.get("files_selection")
            file_priorities = options.get("file_priorities")
            if files_selection or file_priorities:
                info_hash_bytes = bytes.fromhex(info_hash)
                try:
                    # Use timeout to prevent hanging on lock acquisition
                    async def _get_torrent_session():
                        async with self.session.lock:
                            return self.session.torrents.get(info_hash_bytes)

                    torrent_session = await asyncio.wait_for(
                        _get_torrent_session(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    self.logs.write(
                        "Warning: Timeout acquiring session lock for file selection"
                    )
                    torrent_session = None

                if torrent_session and torrent_session.file_selection_manager:
                    from ccbt.piece.file_selection import FilePriority

                    manager = torrent_session.file_selection_manager

                    # Apply file selections (with timeout)
                    try:

                        async def _apply_file_settings():
                            if files_selection:
                                await manager.deselect_all()
                                await manager.select_files(list(files_selection))
                                self.logs.write(
                                    f"Selected {len(files_selection)} file(s) for download"
                                )

                            # Apply file priorities
                            if file_priorities:
                                priority_map = {
                                    "maximum": FilePriority.MAXIMUM,
                                    "high": FilePriority.HIGH,
                                    "normal": FilePriority.NORMAL,
                                    "low": FilePriority.LOW,
                                    "do_not_download": FilePriority.DO_NOT_DOWNLOAD,
                                }
                                for priority_spec in file_priorities:
                                    try:
                                        file_idx_str, priority_str = (
                                            priority_spec.split("=", 1)
                                        )
                                        file_idx = int(file_idx_str.strip())
                                        priority_enum = priority_map[
                                            priority_str.strip().lower()
                                        ]
                                        await manager.set_file_priority(
                                            file_idx, priority_enum
                                        )
                                    except (ValueError, KeyError) as e:
                                        self.logs.write(
                                            f"Invalid priority spec '{priority_spec}': {e}"
                                        )

                        await asyncio.wait_for(_apply_file_settings(), timeout=10.0)
                    except asyncio.TimeoutError:
                        self.logs.write(
                            "Warning: Timeout applying file selection/priorities"
                        )

            # Step 5: Apply queue priority if specified (with timeout)
            queue_priority = options.get("queue_priority")
            if queue_priority and self.session.queue_manager:
                try:
                    from ccbt.models import TorrentPriority

                    priority = TorrentPriority(queue_priority.lower())
                    await asyncio.wait_for(
                        self.session.queue_manager.set_priority(
                            bytes.fromhex(info_hash),
                            priority,
                        ),
                        timeout=5.0,
                    )
                    self.logs.write(f"Set queue priority to {queue_priority}")
                except asyncio.TimeoutError:
                    self.logs.write("Warning: Timeout setting queue priority")
                except Exception as e:
                    self.logs.write(f"Warning: Failed to set queue priority: {e}")

            # Step 6: Apply rate limits if specified (with timeout)
            if "download_limit" in options or "upload_limit" in options:
                try:
                    await asyncio.wait_for(
                        self.session.set_rate_limits(
                            info_hash,
                            options.get("download_limit", 0),
                            options.get("upload_limit", 0),
                        ),
                        timeout=5.0,
                    )
                    self.logs.write(
                        f"Set rate limits: {options.get('download_limit', 0)}/"
                        f"{options.get('upload_limit', 0)} KiB/s"
                    )
                except asyncio.TimeoutError:
                    self.logs.write("Warning: Timeout setting rate limits")
                except Exception as e:
                    self.logs.write(f"Warning: Failed to set rate limits: {e}")

            # Step 7: Update success message with any additional details
            # (Success message was already shown immediately after add)
            success_details = [f"Torrent added: {info_hash[:12]}..."]

            # Add file selection info if applicable
            if files_selection:
                success_details.append(f"Selected {len(files_selection)} file(s)")
            if file_priorities:
                success_details.append(f"Set {len(file_priorities)} file priority(ies)")

            # Add queue priority info if applicable
            if queue_priority:
                success_details.append(f"Queue priority: {queue_priority}")

            # Add rate limit info if applicable
            if "download_limit" in options or "upload_limit" in options:
                down = options.get("download_limit", 0)
                up = options.get("upload_limit", 0)
                if down > 0 or up > 0:
                    success_details.append(f"Rate limits: {down}/{up} KiB/s")

            # Add resume info if applicable
            if resume:
                success_details.append("Resuming from checkpoint")

            # Step 8: Auto-scrape if requested
            if options.get("auto_scrape"):
                try:
                    if self._command_executor:
                        (
                            success,
                            _msg,
                            _,
                        ) = await self._command_executor.execute_click_command(
                            f"scrape torrent {info_hash} --force"
                        )
                        if success:
                            success_details.append("Auto-scraped tracker")
                            self.logs.write(f"Auto-scraped torrent {info_hash[:12]}...")
                except Exception as e:
                    logger.debug("Auto-scrape failed: %s", e)

            success_msg = "\n".join(success_details)

            # Update UI with detailed success message (if there are additional details)
            if len(success_details) > 1:  # Only update if there are additional details
                try:
                    self.statusbar.update(
                        Panel(
                            success_msg,
                            title="Success",
                            border_style="green",
                        ),
                    )
                except Exception as ui_error:
                    # If UI update fails, at least log it
                    logger.debug("Failed to update statusbar: %s", ui_error)
            if files_selection:
                self.logs.write(f"  Selected {len(files_selection)} file(s)")
            if queue_priority:
                self.logs.write(f"  Queue priority: {queue_priority}")
            if resume:
                self.logs.write("  Resuming from checkpoint")
            if options.get("auto_scrape"):
                self.logs.write("  Auto-scraped tracker")

        except Exception as e:
            # Log the full exception for debugging
            logger.exception("Failed to add torrent: %s", path_or_magnet)
            error_msg = str(e) or "Unknown error"
            self.statusbar.update(
                Panel(
                    f"Failed to add torrent: {error_msg}",
                    title="Error",
                    border_style="red",
                ),
            )
            self.logs.write(f"Error adding torrent: {error_msg}")
            # Re-raise to prevent silent failures, but UI has been updated
            raise

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
                await self.session.pause_torrent(ih)
                self.statusbar.update(Panel(f"Paused {ih[:12]}…", title="Action"))
            except Exception as e:
                self.statusbar.update(
                    Panel(f"Pause failed: {e}", title="Action", border_style="red"),
                )

    async def action_resume_torrent(self) -> None:  # pragma: no cover
        """Resume the selected torrent."""
        # Textual action handler - triggered via key bindings, requires full app context
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                await self.session.resume_torrent(ih)
                self.statusbar.update(Panel(f"Resumed {ih[:12]}…", title="Action"))
            except Exception as e:
                self.statusbar.update(
                    Panel(f"Resume failed: {e}", title="Action", border_style="red"),
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
        # TODO: Implement DHTMetricsScreen
        logger.warning("DHT metrics screen not yet implemented")

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
        # TODO: Implement SecurityScanScreen
        logger.warning("Security scan screen not yet implemented")

    async def action_xet_management(self) -> None:  # pragma: no cover
        """Open Xet protocol management screen."""
        await self.push_screen(XetManagementScreen(self.session))  # type: ignore[attr-defined]

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
    
    def _get_connection_status(self) -> str:
        """Get connection status string for status bar."""
        if self._is_daemon_session:
            # Check WebSocket connection status
            if hasattr(self.session, "_websocket_connected") and self.session._websocket_connected:  # type: ignore[attr-defined]
                return "[green]●[/green] Daemon (WebSocket)"
            else:
                return "[yellow]●[/yellow] Daemon (Polling)"
        else:
            return "[blue]●[/blue] Local"
    
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


async def _ensure_daemon_running() -> tuple[bool, Any | None]:
    """Ensure daemon is running, start if needed.
    
    Returns:
        Tuple of (success: bool, ipc_client: IPCClient | None)
        If daemon is running or successfully started, returns (True, IPCClient)
        If daemon start fails, returns (False, None)
    """
    import socket
    
    from ccbt.config.config import get_config, init_config
    from ccbt.daemon.daemon_manager import DaemonManager
    from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
    from ccbt.daemon.utils import generate_api_key
    from ccbt.models import DaemonConfig
    
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()
    
    # Check if daemon is already running
    if pid_file_exists:
        try:
            # Get API key from config
            config_manager = init_config()
            cfg = get_config()
            
            if not cfg.daemon or not cfg.daemon.api_key:
                # Generate API key and create daemon config
                api_key = generate_api_key()
                cfg.daemon = DaemonConfig(api_key=api_key)
                logger.warning("Daemon config not found, generated new API key")
            
            client = IPCClient(api_key=cfg.daemon.api_key)
            
            # Verify IPC server is actually listening (not just PID file exists)
            ipc_host = cfg.daemon.ipc_host if cfg.daemon else "127.0.0.1"
            ipc_port = cfg.daemon.ipc_port if cfg.daemon else 8080
            
            # Test socket connection to verify IPC server is listening
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            try:
                result = sock.connect_ex((ipc_host, ipc_port))
                sock.close()
                if result == 0:
                    # Socket is open, verify daemon is responding
                    if await client.is_daemon_running():
                        logger.info("Daemon is already running and IPC server is listening")
                        return (True, client)
                    else:
                        logger.warning("IPC server is listening but daemon is not responding")
                else:
                    logger.warning("IPC server is not listening on %s:%d", ipc_host, ipc_port)
            except Exception as sock_error:
                logger.debug("Error checking IPC server socket: %s", sock_error)
                sock.close()
            
            # PID file exists but daemon not responding - remove stale PID
            logger.warning("Stale PID file detected, removing")
            daemon_manager.remove_pid()
            await client.close()
        except Exception as e:
            logger.debug("Error checking daemon status: %s", e)
            if pid_file_exists:
                daemon_manager.remove_pid()
    
    # Daemon is not running - start it
    logger.info("Starting daemon...")
    try:
        # Ensure daemon config exists
        config_manager = init_config()
        cfg = get_config()
        
        if not cfg.daemon or not cfg.daemon.api_key:
            api_key = generate_api_key()
            cfg.daemon = DaemonConfig(api_key=api_key)
            logger.info("Generated new API key for daemon")
        
        # Start daemon in background
        pid = daemon_manager.start(foreground=False)
        if pid is None:
            logger.error("Failed to start daemon process")
            return (False, None)
        
        # Wait for daemon to be ready (increased timeout to 30 seconds)
        start_time = time.time()
        timeout = 30.0
        retry_delay = 0.5
        max_retry_delay = 2.0
        
        client = IPCClient(api_key=cfg.daemon.api_key)
        ipc_host = cfg.daemon.ipc_host if cfg.daemon else "127.0.0.1"
        ipc_port = cfg.daemon.ipc_port if cfg.daemon else 8080
        
        while time.time() - start_time < timeout:
            try:
                # First check if IPC server socket is listening
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                try:
                    result = sock.connect_ex((ipc_host, ipc_port))
                    sock.close()
                    if result == 0:
                        # Socket is open, verify daemon is responding
                        if await client.is_daemon_running():
                            logger.info("Daemon started successfully and IPC server is ready")
                            return (True, client)
                except Exception:
                    sock.close()
            except Exception:
                pass
            
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, max_retry_delay)  # Exponential backoff
        
        # Timeout
        logger.error("Daemon did not become ready within %d seconds", int(timeout))
        await client.close()
        return (False, None)
        
    except Exception as e:
        logger.exception("Failed to start daemon: %s", e)
        return (False, None)


def run_dashboard(  # pragma: no cover
    session: AsyncSessionManager | Any,  # Accept DaemonInterfaceAdapter too
    refresh: float | None = None,
) -> None:
    """Run the Textual dashboard App for the provided session."""
    # Entry point for dashboard - requires full Textual app run() context
    TerminalDashboard(session, refresh_interval=refresh or 1.0).run()


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
        "--no-daemon",
        action="store_true",
        help="Disable daemon auto-start and use local session (not recommended)",
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

    # CRITICAL: Always use daemon unless explicitly disabled with --no-daemon
    session: AsyncSessionManager | DaemonInterfaceAdapter | None = None
    
    if args.no_daemon:
        # User explicitly requested local session
        logger.warning(
            "Using local session (--no-daemon specified). "
            "Session state will not persist. "
            "Consider using daemon for persistent sessions."
        )
        session = AsyncSessionManager(".")  # type: ignore[call-arg]  # pragma: no cover - Session creation in CLI entry
    else:
        # ALWAYS use daemon - try to ensure it's running
        try:
            success, ipc_client = asyncio.run(_ensure_daemon_running())
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
                    "To start daemon manually: 'btbt daemon start'\n"
                    "To use local session (not recommended): 'bitonic --no-daemon'"
                )
                return 1
        except Exception as e:
            logger.exception(
                "Error ensuring daemon is running: %s. Cannot proceed without daemon.",
                e
            )
            return 1
    
    if session is None:
        logger.error("Failed to create session")
        return 1
    
    try:
        # TerminalDashboard.on_mount starts the session and metrics, but ensure availability
        run_dashboard(
            session, refresh=float(args.refresh)
        )  # pragma: no cover - Dashboard execution requires full app context
        return 0  # pragma: no cover - Same context
    finally:
        # Best-effort cleanup; on_unmount also stops services
        with contextlib.suppress(
            Exception
        ):  # pragma: no cover - Cleanup exception handling
            # AsyncSessionManager.stop is async; schedule via asyncio.run if needed
            import asyncio as _asyncio  # pragma: no cover - Same context

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
