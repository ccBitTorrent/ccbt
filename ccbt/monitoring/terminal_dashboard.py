"""Textual-based terminal dashboard for ccBitTorrent.

Provides a live view of global session stats and per-torrent status.

References:
- Textual framework documentation: https://textual.textualize.io/
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual import events  # type: ignore[import-not-found]
    from textual.app import App
    from textual.widgets import Static
else:
    # Runtime imports - textual may not be available
    try:
        from textual.app import App
        from textual.widgets import Static
    except ImportError:
        # Fallback classes for when textual is not available
        class App:  # type: ignore[misc]
            """Fallback App class when textual is not available."""

        class Static:  # type: ignore[misc]
            """Fallback Static class when textual is not available."""


from rich.panel import Panel
from rich.table import Table

from ccbt.checkpoint import CheckpointManager
from ccbt.monitoring import MetricsCollector, get_alert_manager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ccbt.session import AsyncSessionManager

try:
    from textual.app import App, ComposeResult  # type: ignore[import-not-found]
    from textual.containers import (  # type: ignore[import-not-found]
        Container,
        Horizontal,
    )
    from textual.widgets import (  # type: ignore[import-not-found]
        DataTable,
        Footer,
        Header,
        Input,
        RichLog,
        Sparkline,
        Static,
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

    class Events:  # type: ignore[no-redef]
        """Events stub for textual compatibility."""

        class Key:  # minimal shim
            """Key event stub for textual compatibility."""

            def __init__(self, key: str = ""):
                """Initialize key event."""
                self.key = key


class Overview(Static):  # type: ignore[misc]
    """Simple widget to render global stats."""

    def update_from_stats(self, stats: dict[str, Any]) -> None:
        """Update dashboard with statistics."""
        rows = [
            ("Torrents", str(stats.get("num_torrents", 0))),
            ("Active", str(stats.get("num_active", 0))),
            ("Paused", str(stats.get("num_paused", 0))),
            ("Seeding", str(stats.get("num_seeding", 0))),
            ("Down Rate", f"{stats.get('download_rate', 0.0):.1f} B/s"),
            ("Up Rate", f"{stats.get('upload_rate', 0.0):.1f} B/s"),
            ("Avg Progress", f"{stats.get('average_progress', 0.0) * 100:.1f}%"),
        ]
        t = Table(show_header=False, box=None, expand=True)
        t.add_column("Key", style="cyan", ratio=1)
        t.add_column("Value", style="green", ratio=2)
        for k, v in rows:
            t.add_row(k, v)
        self.update(Panel(t, title="Overview"))


class TorrentsTable(Static):  # type: ignore[misc]
    """Widget to render per-torrent status table."""

    def on_mount(self) -> None:  # type: ignore[override]
        """Mount the torrents table widget."""
        self._dt = DataTable(zebra_stripes=True)
        self._dt.add_columns("Info Hash", "Name", "Status", "Progress", "Down/Up (B/s)")
        self.update(self._dt)

    def update_from_status(self, status: dict[str, dict[str, Any]]) -> None:
        """Update torrents table with current status."""
        dt: DataTable = self._dt
        dt.clear()
        for ih, st in status.items():
            progress = f"{float(st.get('progress', 0.0)) * 100:.1f}%"
            rates = f"{float(st.get('download_rate', 0.0)):.0f} / {float(st.get('upload_rate', 0.0)):.0f}"
            dt.add_row(
                ih,
                str(st.get("name", "-")),
                str(st.get("status", "-")),
                progress,
                rates,
                key=ih,
            )

    def get_selected_info_hash(self) -> str | None:
        """Get the info hash of the currently selected torrent."""
        if hasattr(self._dt, "cursor_row_key"):
            with contextlib.suppress(Exception):
                row_key = self._dt.cursor_row_key
                return None if row_key is None else str(row_key)
        return None


class PeersTable(Static):  # type: ignore[misc]
    """Widget to render peers for selected torrent."""

    def on_mount(self) -> None:  # type: ignore[override]
        """Mount the peers table widget."""
        self._dt = DataTable(zebra_stripes=True)
        self._dt.add_columns("IP", "Port", "Down (B/s)", "Up (B/s)", "Choked", "Client")
        self.update(self._dt)

    def update_from_peers(self, peers: list[dict[str, Any]]) -> None:
        """Update peers table with current peer data."""
        dt: DataTable = self._dt
        dt.clear()
        for p in peers or []:
            dt.add_row(
                str(p.get("ip", "-")),
                str(p.get("port", "-")),
                f"{float(p.get('download_rate', 0.0)):.0f}",
                f"{float(p.get('upload_rate', 0.0)):.0f}",
                str(p.get("choked", False)),
                str(p.get("client", "?")),
            )


class SpeedSparklines(Static):  # type: ignore[misc]
    """Widget to show download/upload speed history."""

    def on_mount(self) -> None:  # type: ignore[override]
        """Mount the speed sparklines widget."""
        self._down = Sparkline()
        self._up = Sparkline()
        self._down_history: list[float] = []
        self._up_history: list[float] = []
        cont = Container(self._down, self._up)
        self.update(Panel(cont, title="Speeds"))

    def update_from_stats(self, stats: dict[str, Any]) -> None:
        """Update sparklines with current speed statistics."""
        self._down_history.append(float(stats.get("download_rate", 0.0)))
        self._up_history.append(float(stats.get("upload_rate", 0.0)))
        # Keep last 120 samples (~2 minutes at 1s)
        self._down_history = self._down_history[-120:]
        self._up_history = self._up_history[-120:]
        with contextlib.suppress(Exception):
            self._down.data = self._down_history  # type: ignore[attr-defined]
            self._up.data = self._up_history  # type: ignore[attr-defined]


class TerminalDashboard(App):  # type: ignore[misc]
    """Textual dashboard application."""

    CSS = """
    Screen { layout: vertical; }
    #body { layout: horizontal; height: 1fr; }
    #left, #right { width: 1fr; }
    #left { layout: vertical; }
    #right { layout: vertical; }
    #torrents { height: 2fr; }
    #peers { height: 1fr; }
    """

    def __init__(self, session: AsyncSessionManager, refresh_interval: float = 1.0):
        """Initialize terminal dashboard."""
        super().__init__()
        self.session = session
        self.refresh_interval = max(0.2, float(refresh_interval))
        self.overview = Overview(id="overview")
        self.speeds = SpeedSparklines(id="speeds")
        self.torrents = TorrentsTable(id="torrents")
        self.peers = PeersTable(id="peers")
        self.details = Static(id="details")
        self.statusbar = Static(id="statusbar")
        self.alerts = Static(id="alerts")
        self.alert_manager = get_alert_manager()
        self.metrics_collector = MetricsCollector()
        self._poll_task: asyncio.Task | None = None
        self._filter_input: Input | None = None
        self._filter_text: str = ""
        self._last_status: dict[str, dict[str, Any]] = {}
        self.logs = RichLog(id="logs")
        self._compact = False

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield Container(self.overview, self.speeds, id="left")
            yield Container(
                self.torrents,
                self.peers,
                self.details,
                self.logs,
                id="right",
            )
        yield self.statusbar
        yield Container(self.alerts)
        yield Footer()

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("p", "pause_torrent", "Pause"),
        ("r", "resume_torrent", "Resume"),
        ("q", "quit", "Quit"),
        ("i", "quick_add_torrent", "Quick Add"),
        ("o", "advanced_add_torrent", "Advanced Add"),
        ("b", "browse_add_torrent", "Browse"),
    ]

    async def on_mount(self) -> None:  # type: ignore[override]
        """Mount the dashboard and start session polling."""
        # Start the session and begin polling
        await self.session.start()
        with contextlib.suppress(Exception):
            await self.metrics_collector.start()
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
        self.set_interval(self.refresh_interval, self._schedule_poll)

    def _schedule_poll(self) -> None:
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_once())

    async def _poll_once(self) -> None:
        try:
            stats = await self.session.get_global_stats()
            self.overview.update_from_stats(stats)
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
                    peers = await self.session.get_peers_for_torrent(ih)
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
                self.details.update(Panel(det, title="Details"))
            else:
                self.details.update(
                    Panel("Select a torrent for details", title="Details"),
                )
            # Update status bar counters
            sb = f"Torrents: {stats.get('num_torrents', 0)}  Active: {stats.get('num_active', 0)}  Paused: {stats.get('num_paused', 0)}  Seeding: {stats.get('num_seeding', 0)}  D: {float(stats.get('download_rate', 0.0)):.0f}B/s  U: {float(stats.get('upload_rate', 0.0)):.0f}B/s"
            self.statusbar.update(Panel(sb, title="Status"))
            # Show alert rules and active alerts
            if getattr(self.alert_manager, "alert_rules", None):
                rules = Table(title="Alert Rules", expand=True)
                rules.add_column("Name", style="cyan")
                rules.add_column("Metric")
                rules.add_column("Condition")
                rules.add_column("Severity", style="red")
                for rn, rule in self.alert_manager.alert_rules.items():
                    rules.add_row(
                        rn,
                        rule.metric_name,
                        rule.condition,
                        getattr(rule.severity, "value", str(rule.severity)),
                    )
            else:
                rules = Panel("No alert rules configured", title="Alert Rules")

            if getattr(self.alert_manager, "active_alerts", None):
                act = Table(title="Active Alerts", expand=True)
                act.add_column("Severity", style="red")
                act.add_column("Rule", style="yellow")
                act.add_column("Value")
                for a in self.alert_manager.active_alerts.values():
                    act.add_row(
                        getattr(a.severity, "value", str(a.severity)),
                        a.rule_name,
                        str(a.value),
                    )
            else:
                act = Panel("No active alerts", title="Active Alerts")

            # Ensure we pass Widgets to Container
            # Wrap both in Static to satisfy Textual's Widget expectations
            self.alerts.update(Container(Static(rules), Static(act)))
        except Exception as e:
            # Render error where overview goes
            self.overview.update(Panel(str(e), title="Error", border_style="red"))

    async def on_unmount(self) -> None:  # type: ignore[override]
        """Unmount the dashboard and stop session."""
        with contextlib.suppress(Exception):
            await self.session.stop()
        with contextlib.suppress(Exception):
            await self.metrics_collector.stop()

    # Key bindings
    async def on_key(self, event: events.Key) -> None:  # type: ignore[override]
        """Handle key press events."""
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
                        title="Confirm",
                        border_style="yellow",
                    ),
                )
                self._pending_delete = ih  # type: ignore[attr-defined]
            return
        if event.key in ("y", "Y"):
            ih = getattr(self, "_pending_delete", None)
            if ih:
                with contextlib.suppress(Exception):
                    await self.session.remove(ih)
                self._pending_delete = None  # type: ignore[attr-defined]
            return
        if event.key in ("n", "N"):
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
                        Panel(f"Announce: {'OK' if ok else 'Failed'}", title="Status"),
                    )
                    self.logs.write(f"Announce {'OK' if ok else 'Failed'} for {ih}")
                except Exception:
                    self.statusbar.update(
                        Panel("Announce: Failed", title="Status", border_style="red"),
                    )
            return
        if event.key in ("s", "S"):
            # Force scrape (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.force_scrape(ih)
                self.statusbar.update(
                    Panel(f"Scrape: {'OK' if ok else 'Failed'}", title="Status"),
                )
                self.logs.write(f"Scrape {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("e", "E"):
            # Refresh PEX (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.refresh_pex(ih)
                self.statusbar.update(
                    Panel(f"PEX: {'OK' if ok else 'Failed'}", title="Status"),
                )
                self.logs.write(f"PEX {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("h", "H"):
            # Rehash (placeholder)
            ih = self.torrents.get_selected_info_hash()
            if ih:
                ok = await self.session.rehash_torrent(ih)
                self.statusbar.update(
                    Panel(f"Rehash: {'OK' if ok else 'Failed'}", title="Status"),
                )
                self.logs.write(f"Rehash {'OK' if ok else 'Failed'} for {ih}")
            return
        if event.key in ("x", "X"):
            # Export snapshot
            from pathlib import Path

            p = Path("dashboard_snapshot.json")
            try:
                await self.session.export_session_state(p)
                self.statusbar.update(Panel(f"Snapshot saved to {p}", title="Status"))
                self.logs.write(f"Snapshot saved to {p}")
            except Exception as e:
                self.statusbar.update(
                    Panel(f"Snapshot failed: {e}", title="Status", border_style="red"),
                )
            return
        if event.key in ("1",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    await self.session.set_rate_limits(ih, 0, 0)
                    self.statusbar.update(Panel("Rate limits disabled", title="Status"))
                    self.logs.write(f"Rate limits disabled for {ih}")
            return
        if event.key in ("2",):
            ih = self.torrents.get_selected_info_hash()
            if ih:
                with contextlib.suppress(Exception):
                    await self.session.set_rate_limits(ih, 1024, 1024)
                    self.statusbar.update(
                        Panel("Rate limits set to 1024 KiB/s", title="Status"),
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

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]
        """Handle input submission events."""
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
            message.input.display = False
            await self._process_add_torrent(path_or_magnet, {})
        elif message.input.id == "add_torrent_advanced_step1":
            path_or_magnet = message.value.strip()
            message.input.display = False
            if path_or_magnet:
                await self._show_advanced_options(path_or_magnet)
        elif message.input.id == "add_torrent_advanced_step2":
            output_dir = message.value.strip() or "."
            message.input.display = False
            await self._process_advanced_options(output_dir)
        elif message.input.id == "add_torrent_browse":
            path_or_magnet = message.value.strip()
            message.input.display = False
            await self._process_add_torrent(path_or_magnet, {})

    def _apply_filter_and_update(self) -> None:
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

    async def _run_command(self, cmdline: str) -> None:
        parts = cmdline.split()
        if not parts:
            return
        cmd = parts[0].lower()
        ih = self.torrents.get_selected_info_hash()
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
        except Exception as e:
            self.logs.write(f"Command error: {e}")

    async def _quick_add_torrent(self) -> None:
        """Quick add torrent with default settings."""
        input_widget = Input(placeholder="File path or magnet link", id="add_torrent")
        self.mount(input_widget)
        input_widget.focus()

    async def _advanced_add_torrent(self) -> None:
        """Advanced add torrent with configuration options."""
        # Step 1: Get torrent path/magnet
        input_widget = Input(
            placeholder="File path or magnet link",
            id="add_torrent_advanced_step1",
        )
        self.mount(input_widget)
        input_widget.focus()

    async def _browse_add_torrent(self) -> None:
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

    async def _process_add_torrent(
        self,
        path_or_magnet: str,
        options: dict[str, Any],
    ) -> None:
        """Process torrent addition."""
        try:
            # Determine if file or magnet
            if path_or_magnet.startswith("magnet:"):
                info_hash = await self.session.add_magnet(
                    path_or_magnet,
                    resume=options.get("resume", False),
                )
            else:
                info_hash = await self.session.add_torrent(
                    path_or_magnet,
                    resume=options.get("resume", False),
                )

            # Apply rate limits if specified
            if "download_limit" in options or "upload_limit" in options:
                await self.session.set_rate_limits(
                    info_hash,
                    options.get("download_limit", 0),
                    options.get("upload_limit", 0),
                )

            self.statusbar.update(
                Panel(
                    f"Added torrent: {info_hash[:12]}...",
                    title="Success",
                    border_style="green",
                ),
            )
            self.logs.write(f"Added torrent: {path_or_magnet}")
        except Exception as e:
            self.statusbar.update(
                Panel(
                    f"Failed to add torrent: {e}",
                    title="Error",
                    border_style="red",
                ),
            )
            self.logs.write(f"Error adding torrent: {e}")

    async def _show_advanced_options(self, path_or_magnet: str) -> None:
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

    async def _process_advanced_options(self, output_dir: str) -> None:
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

    async def _handle_file_browser_selection(self, selected_key: str) -> None:
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

    async def _navigate_to_directory(self, new_dir: Path) -> None:
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
    async def action_pause_torrent(self) -> None:
        """Pause the selected torrent."""
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                await self.session.pause_torrent(ih)
                self.statusbar.update(Panel(f"Paused {ih[:12]}…", title="Action"))
            except Exception as e:
                self.statusbar.update(
                    Panel(f"Pause failed: {e}", title="Action", border_style="red"),
                )

    async def action_resume_torrent(self) -> None:
        """Resume the selected torrent."""
        ih = self.torrents.get_selected_info_hash()
        if ih:
            try:
                await self.session.resume_torrent(ih)
                self.statusbar.update(Panel(f"Resumed {ih[:12]}…", title="Action"))
            except Exception as e:
                self.statusbar.update(
                    Panel(f"Resume failed: {e}", title="Action", border_style="red"),
                )


def run_dashboard(
    session: AsyncSessionManager,
    refresh: float | None = None,
) -> None:
    """Run the Textual dashboard App for the provided session."""
    TerminalDashboard(session, refresh_interval=refresh or 1.0).run()
