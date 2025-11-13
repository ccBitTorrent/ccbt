"""Per-torrent configuration screens.

Provides UI for configuring individual torrent settings including rate limits,
queue priority, file selection, and advanced options.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import PerTorrentConfigScreen

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - TYPE_CHECKING block
    from ccbt.session.session import AsyncSessionManager

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        Select,
        Static,
        Switch,
    )

    _TEXTUAL_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback when Textual isn't installed
    _TEXTUAL_AVAILABLE = False
    # Stub classes for when Textual is not available
    class Container:  # type: ignore[no-redef, misc]
        pass

    class Horizontal:  # type: ignore[no-redef, misc]
        pass

    class Vertical:  # type: ignore[no-redef, misc]
        pass

    class Button:  # type: ignore[no-redef, misc]
        pass

    class DataTable:  # type: ignore[no-redef, misc]
        pass

    class Footer:  # type: ignore[no-redef, misc]
        pass

    class Header:  # type: ignore[no-redef, misc]
        pass

    class Input:  # type: ignore[no-redef, misc]
        pass

    class Select:  # type: ignore[no-redef, misc]
        pass

    class Static:  # type: ignore[no-redef, misc]
        pass

    class Switch:  # type: ignore[no-redef, misc]
        pass


# Import FileSelectionScreen from terminal_dashboard for now
# TODO: Extract FileSelectionScreen to screens/dialogs.py and update this import
if TYPE_CHECKING:  # pragma: no cover
    from ccbt.interface.terminal_dashboard import FileSelectionScreen
else:
    try:
        from ccbt.interface.terminal_dashboard import FileSelectionScreen
    except ImportError:  # pragma: no cover
        FileSelectionScreen = None  # type: ignore[assignment, misc]


class PerTorrentConfigMainScreen(PerTorrentConfigScreen):  # type: ignore[misc]
    """Main screen for per-torrent configuration with torrent selector."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("enter", "select", "Select Torrent"),
    ]

    CSS = """
    #torrents {
        height: 1fr;
    }
    #info {
        height: 1fr;
        min-height: 5;
    }
    #stats {
        height: 1fr;
        min-height: 8;
    }
    """

    def compose(self) -> Any:  # pragma: no cover
        """Compose the per-torrent config main screen."""
        yield Header()
        with Horizontal():
            with Vertical():
                yield DataTable(id="torrents", zebra_stripes=True)
                yield Static(id="info")
            yield Static(id="stats")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and populate torrents."""
        torrents_table = self.query_one("#torrents", DataTable)
        torrents_table.add_columns(
            "Info Hash", "Name", "Status", "Progress", "Down Limit", "Up Limit"
        )

        # Get all torrents from session
        all_status = await self.session.get_status()
        for ih, status in all_status.items():
            # Get rate limits if set
            limits = getattr(self.session, "_per_torrent_limits", {}).get(
                bytes.fromhex(ih), {}
            )
            down_limit = limits.get("down_kib", 0)
            up_limit = limits.get("up_kib", 0)

            # Format progress
            progress = float(status.get("progress", 0.0)) * 100
            progress_str = f"{progress:.1f}%"

            torrents_table.add_row(
                ih[:12] + "...",
                str(status.get("name", "-"))[:40],
                str(status.get("status", "-")),
                progress_str,
                f"{down_limit} KiB/s" if down_limit > 0 else "Unlimited",
                f"{up_limit} KiB/s" if up_limit > 0 else "Unlimited",
                key=ih,
            )

        torrents_table.cursor_type = "row"
        torrents_table.focus()

        # Update info panel
        info = self.query_one("#info", Static)
        info.update(
            Panel(
                "Select a torrent to configure. Press Enter to edit, Escape to go back.\n"
                "Use arrow keys to navigate, '/' to filter.",
                title="Per-Torrent Configuration",
            )
        )

        # Update stats panel
        stats_widget = self.query_one("#stats", Static)
        await self._update_stats(stats_widget, None)

    async def _update_stats(
        self, stats_widget: Static, selected_ih: str | None
    ) -> None:  # pragma: no cover
        """Update stats panel with selected torrent information."""
        if selected_ih:
            all_status = await self.session.get_status()
            status = all_status.get(selected_ih, {})

            table = Table(
                title="Torrent Details", expand=True, show_header=False, box=None
            )
            table.add_column("Key", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            table.add_row("Name", str(status.get("name", "Unknown")))
            table.add_row("Status", str(status.get("status", "-")))
            table.add_row(
                "Progress", f"{float(status.get('progress', 0.0)) * 100:.1f}%"
            )
            table.add_row(
                "Download Rate", f"{float(status.get('download_rate', 0.0)):.0f} B/s"
            )
            table.add_row(
                "Upload Rate", f"{float(status.get('upload_rate', 0.0)):.0f} B/s"
            )

            # Get rate limits
            limits = getattr(self.session, "_per_torrent_limits", {}).get(
                bytes.fromhex(selected_ih), {}
            )
            down_limit = limits.get("down_kib", 0)
            up_limit = limits.get("up_kib", 0)
            table.add_row(
                "Down Limit", f"{down_limit} KiB/s" if down_limit > 0 else "Unlimited"
            )
            table.add_row(
                "Up Limit", f"{up_limit} KiB/s" if up_limit > 0 else "Unlimited"
            )

            stats_widget.update(Panel(table))
        else:
            # Show summary
            all_status = await self.session.get_status()
            total = len(all_status)
            with_limits = sum(
                1
                for ih in all_status
                if getattr(self.session, "_per_torrent_limits", {}).get(
                    bytes.fromhex(ih), {}
                )
            )

            table = Table(title="Summary", expand=True, show_header=False, box=None)
            table.add_column("Key", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)
            table.add_row("Total Torrents", str(total))
            table.add_row("With Rate Limits", str(with_limits))
            table.add_row("Without Limits", str(total - with_limits))

            stats_widget.update(Panel(table))

    async def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle torrent selection."""
        # Update stats when selection changes
        torrents_table = self.query_one("#torrents", DataTable)
        if hasattr(torrents_table, "cursor_row_key") and torrents_table.cursor_row_key:
            selected_ih = str(torrents_table.cursor_row_key)
            stats_widget = self.query_one("#stats", Static)
            await self._update_stats(stats_widget, selected_ih)

    async def on_data_table_cursor_row_changed(
        self, event: Any
    ) -> None:  # pragma: no cover
        """Handle cursor movement to update stats."""
        torrents_table = self.query_one("#torrents", DataTable)
        if hasattr(torrents_table, "cursor_row_key") and torrents_table.cursor_row_key:
            selected_ih = str(torrents_table.cursor_row_key)
            stats_widget = self.query_one("#stats", Static)
            await self._update_stats(stats_widget, selected_ih)
        else:
            stats_widget = self.query_one("#stats", Static)
            await self._update_stats(stats_widget, None)

    async def action_select(self) -> None:  # pragma: no cover
        """Select and navigate to the selected torrent."""
        await self._navigate_to_torrent()

    async def on_key(self, event: Any) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle key presses."""
        # Handle Enter key - DataTable might consume it, so we handle it at screen level
        if event.key == "enter":
            torrents_table = self.query_one("#torrents", DataTable)
            # Use cursor_row_key which is more reliable than cursor_row
            if (
                hasattr(torrents_table, "cursor_row_key")
                and torrents_table.cursor_row_key
            ):
                # Navigate directly
                await self._navigate_to_torrent()
            # If no key, let DataTable handle it (shouldn't happen, but safe fallback)
        # Other keys are handled by Textual's default behavior

    async def _navigate_to_torrent(self) -> None:  # pragma: no cover
        """Navigate to selected torrent's detail screen."""
        torrents_table = self.query_one("#torrents", DataTable)
        if hasattr(torrents_table, "cursor_row_key") and torrents_table.cursor_row_key:
            info_hash_hex = str(torrents_table.cursor_row_key)
            await self.app.push_screen(  # type: ignore[attr-defined]
                TorrentConfigDetailScreen(self.session, info_hash_hex=info_hash_hex)
            )


class TorrentConfigDetailScreen(PerTorrentConfigScreen):  # type: ignore[misc]
    """Detail screen for per-torrent configuration with enhanced information."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("a", "announce", "Announce"),
        ("s", "scrape", "Scrape"),
        ("e", "pex", "PEX"),
        ("h", "rehash", "Rehash"),
        ("p", "pause", "Pause"),
        ("r", "resume", "Resume"),
        ("f", "files", "File Selection"),
        ("o", "reorder", "Reorder Queue"),
    ]

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #info {
        height: 1fr;
        min-height: 8;
    }
    #performance_metrics {
        height: 1fr;
        min-height: 8;
    }
    #inputs {
        height: 1fr;
        min-height: 5;
    }
    #queue_section {
        height: 1fr;
        min-height: 5;
    }
    #files_section {
        height: 1fr;
        min-height: 5;
    }
    #operations {
        height: 1fr;
        min-height: 5;
    }
    #actions {
        height: 3;
    }
    #errors {
        height: 5;
        min-height: 3;
    }
    """

    def __init__(
        self,
        session: AsyncSessionManager,
        info_hash_hex: str,
        *args: Any,
        **kwargs: Any,
    ):  # pragma: no cover
        """Initialize torrent config detail screen."""
        super().__init__(session, *args, **kwargs)
        self.info_hash_hex = info_hash_hex

    def compose(self) -> Any:  # pragma: no cover
        """Compose the torrent config detail screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="info")
            yield Static(id="performance_metrics")
            yield Container(id="inputs")
            yield Static(id="queue_section")
            yield Static(id="files_section")
            yield Static(id="operations")
            yield Static(id="errors")
            with Horizontal(id="actions"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Reset Limits", id="reset", variant="default")
                yield Button("Manage Files", id="files", variant="default")
                yield Button("Cancel", id="cancel")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and populate torrent config."""
        content = self.query_one("#content", Static)
        info_widget = self.query_one("#info", Static)
        inputs_container = self.query_one("#inputs", Container)
        queue_section = self.query_one("#queue_section", Static)
        files_section = self.query_one("#files_section", Static)
        operations_section = self.query_one("#operations", Static)
        errors_widget = self.query_one("#errors", Static)

        # Get torrent session to access queue and file selection
        info_hash_bytes = bytes.fromhex(self.info_hash_hex)
        async with self.session.lock:
            torrent_session = self.session.torrents.get(info_hash_bytes)

        # Get current rate limits
        limits = getattr(self.session, "_per_torrent_limits", {}).get(
            info_hash_bytes, {}
        )
        down_limit = limits.get("down_kib", 0)
        up_limit = limits.get("up_kib", 0)

        # Get torrent status
        all_status = await self.session.get_status()
        torrent_status = all_status.get(self.info_hash_hex, {})
        torrent_name = torrent_status.get("name", "Unknown")
        progress = float(torrent_status.get("progress", 0.0)) * 100
        status_str = str(torrent_status.get("status", "-"))
        down_rate = float(torrent_status.get("download_rate", 0.0))
        up_rate = float(torrent_status.get("upload_rate", 0.0))

        # Create info table with torrent details
        info_table = Table(
            title=f"Torrent: {torrent_name[:60]}",
            expand=True,
            show_header=False,
            box=None,
        )
        info_table.add_column("Key", style="cyan", ratio=1)
        info_table.add_column("Value", style="green", ratio=2)

        info_table.add_row("Info Hash", self.info_hash_hex[:40] + "...")
        info_table.add_row("Status", status_str)
        info_table.add_row("Progress", f"{progress:.1f}%")
        info_table.add_row(
            "Current Down Rate", f"{down_rate:.0f} B/s ({down_rate / 1024:.1f} KiB/s)"
        )
        info_table.add_row(
            "Current Up Rate", f"{up_rate:.0f} B/s ({up_rate / 1024:.1f} KiB/s)"
        )

        info_widget.update(Panel(info_table))

        # Create configuration table for rate limits
        config_table = Table(title="Rate Limit Configuration", expand=True)
        config_table.add_column("Setting", style="cyan", ratio=2)
        config_table.add_column("Current Value", style="green", ratio=2)
        config_table.add_column("Description", style="dim", ratio=4)

        config_table.add_row(
            "Download Limit",
            f"{down_limit} KiB/s" if down_limit > 0 else "Unlimited (0)",
            "Per-torrent download rate limit in KiB/s. Set to 0 for unlimited.",
        )
        config_table.add_row(
            "Upload Limit",
            f"{up_limit} KiB/s" if up_limit > 0 else "Unlimited (0)",
            "Per-torrent upload rate limit in KiB/s. Set to 0 for unlimited.",
        )

        content.update(Panel(config_table))

        # Create input fields with labels
        down_label = Static("Download Limit (KiB/s, 0 = unlimited):", id="label_down")
        inputs_container.mount(down_label)

        down_input = Input(
            value=str(down_limit),
            placeholder="Enter download limit in KiB/s (0 for unlimited)",
            id="down_limit",
        )
        inputs_container.mount(down_input)

        up_label = Static("Upload Limit (KiB/s, 0 = unlimited):", id="label_up")
        inputs_container.mount(up_label)

        up_input = Input(
            value=str(up_limit),
            placeholder="Enter upload limit in KiB/s (0 for unlimited)",
            id="up_limit",
        )
        inputs_container.mount(up_input)

        # Queue priority section
        queue_info = ""
        if self.session.queue_manager and torrent_session:
            try:
                queue_state = await self.session.queue_manager.get_torrent_queue_state(
                    info_hash_bytes
                )
                if queue_state:
                    current_priority = queue_state.get("priority", "normal")
                    queue_position = queue_state.get("queue_position", "N/A")
                    queue_info = f"Priority: {current_priority.upper()}, Position: {queue_position}"
            except Exception:
                queue_info = "Queue info unavailable"

        if queue_info:
            queue_table = Table(
                title="Queue Configuration", expand=True, show_header=False, box=None
            )
            queue_table.add_column("Key", style="cyan", ratio=1)
            queue_table.add_column("Value", style="green", ratio=2)
            queue_table.add_row("Queue Status", queue_info)

            # Add priority selector
            priority_input = Input(
                value=queue_info.split(":")[1].split(",")[0].strip().lower()
                if ":" in queue_info
                else "normal",
                placeholder="Priority: maximum, high, normal, low, paused",
                id="queue_priority",
            )
            priority_label = Static("Queue Priority:", id="label_priority")
            inputs_container.mount(priority_label)
            inputs_container.mount(priority_input)

            queue_section.update(Panel(queue_table))
        else:
            queue_section.update("")

        # File selection section
        files_info = ""
        file_manager = None
        if (
            torrent_session
            and hasattr(torrent_session, "file_selection_manager")
            and torrent_session.file_selection_manager
        ):
            try:
                file_manager = torrent_session.file_selection_manager
                stats = file_manager.get_statistics()
                total = stats.get("total_files", 0)
                selected = stats.get("selected_files", 0)
                files_info = f"Files: {selected}/{total} selected"
            except Exception:
                files_info = "File selection unavailable"

        if files_info and file_manager:
            # Enhanced file selection display with more details
            all_states = file_manager.get_all_file_states()
            files_table = Table(
                title="File Selection", expand=True, show_header=False, box=None
            )
            files_table.add_column("Key", style="cyan", ratio=1)
            files_table.add_column("Value", style="green", ratio=2)

            files_table.add_row("Selection Status", files_info)

            # Add priority breakdown
            priority_counts: dict[str, int] = {}
            for state in all_states.values():
                pri_name = state.priority.name.lower()
                priority_counts[pri_name] = priority_counts.get(pri_name, 0) + 1

            if priority_counts:
                priority_str = ", ".join(
                    f"{k}: {v}" for k, v in sorted(priority_counts.items())
                )
                files_table.add_row("Priority Breakdown", priority_str)

            # Add progress info if available
            total_bytes = sum(state.bytes_total for state in all_states.values())
            downloaded_bytes = sum(
                state.bytes_downloaded for state in all_states.values()
            )
            if total_bytes > 0:
                progress_pct = (downloaded_bytes / total_bytes) * 100.0
                files_table.add_row("Overall Progress", f"{progress_pct:.1f}%")

            # Store file manager for later use
            self._file_manager = file_manager  # type: ignore[attr-defined]

            files_section.update(Panel(files_table))
        elif files_info:
            files_table = Table(
                title="File Selection", expand=True, show_header=False, box=None
            )
            files_table.add_column("Key", style="cyan", ratio=1)
            files_table.add_column("Value", style="green", ratio=2)
            files_table.add_row("Selection Status", files_info)
            files_section.update(Panel(files_table))
            self._file_manager = None  # type: ignore[attr-defined]
        else:
            files_section.update("")
            self._file_manager = None  # type: ignore[attr-defined]

        # Advanced configuration section
        advanced_table = Table(
            title="Advanced Configuration", expand=True, show_header=False, box=None
        )
        advanced_table.add_column("Setting", style="cyan", ratio=2)
        advanced_table.add_column("Current Value", style="green", ratio=2)
        advanced_table.add_column("Description", style="dim", ratio=4)

        # Get current torrent options if available
        torrent_options = (
            getattr(torrent_session, "options", {}) if torrent_session else {}
        )

        # Piece selection strategy
        piece_selection = torrent_options.get("piece_selection", "rarest_first")
        advanced_table.add_row(
            "Piece Selection",
            piece_selection,
            "Strategy: round_robin, rarest_first, sequential",
        )

        # Streaming mode
        streaming_mode = torrent_options.get("streaming_mode", False)
        advanced_table.add_row(
            "Streaming Mode",
            "Enabled" if streaming_mode else "Disabled",
            "Optimize for sequential download (media files)",
        )

        # Sequential window size
        seq_window = torrent_options.get("sequential_window_size", 5)
        advanced_table.add_row(
            "Sequential Window",
            str(seq_window),
            "Pieces ahead to download in sequential mode",
        )

        # Max peers per torrent
        max_peers = torrent_options.get("max_peers_per_torrent", None)
        max_peers_str = str(max_peers) if max_peers else "Global default"
        advanced_table.add_row(
            "Max Peers", max_peers_str, "Maximum peers for this torrent (0 = unlimited)"
        )

        # Protocol options
        enable_tcp = torrent_options.get("enable_tcp", True)
        enable_utp = torrent_options.get("enable_utp", True)
        enable_encryption = torrent_options.get("enable_encryption", False)

        advanced_table.add_row(
            "TCP Transport",
            "Enabled" if enable_tcp else "Disabled",
            "Use TCP for peer connections",
        )
        advanced_table.add_row(
            "uTP Transport",
            "Enabled" if enable_utp else "Disabled",
            "Use uTP (BEP 29) for peer connections",
        )
        advanced_table.add_row(
            "Encryption",
            "Enabled" if enable_encryption else "Disabled",
            "Enable protocol encryption (BEP 3)",
        )

        # Scrape options
        auto_scrape = torrent_options.get("auto_scrape", False)
        advanced_table.add_row(
            "Auto-scrape",
            "Enabled" if auto_scrape else "Disabled",
            "Automatically scrape tracker on torrent add",
        )

        # NAT options
        enable_nat = torrent_options.get("enable_nat_mapping", False)
        advanced_table.add_row(
            "NAT Mapping",
            "Enabled" if enable_nat else "Disabled",
            "Enable NAT port mapping for this torrent",
        )

        # Add inputs for editable settings
        piece_selection_input = Select(
            options=[
                ("round_robin", "Round Robin"),
                ("rarest_first", "Rarest First"),
                ("sequential", "Sequential"),
            ],
            value=piece_selection,
            id="piece_selection",
            prompt="Piece Selection Strategy",
        )
        piece_label = Static("Piece Selection Strategy:", id="label_piece_selection")
        inputs_container.mount(piece_label)
        inputs_container.mount(piece_selection_input)

        streaming_input = Switch(value=streaming_mode, id="streaming_mode")
        streaming_label = Static("Streaming Mode:", id="label_streaming")
        inputs_container.mount(streaming_label)
        inputs_container.mount(streaming_input)

        seq_window_input = Input(
            value=str(seq_window),
            placeholder="Sequential window size (pieces ahead)",
            id="sequential_window",
        )
        seq_label = Static("Sequential Window Size:", id="label_seq_window")
        inputs_container.mount(seq_label)
        inputs_container.mount(seq_window_input)

        max_peers_input = Input(
            value=str(max_peers) if max_peers else "",
            placeholder="Max peers (0 = unlimited, empty = global default)",
            id="max_peers",
        )
        max_peers_label = Static("Max Peers Per Torrent:", id="label_max_peers")
        inputs_container.mount(max_peers_label)
        inputs_container.mount(max_peers_input)

        tcp_switch = Switch(value=enable_tcp, id="enable_tcp")
        tcp_label = Static("Enable TCP:", id="label_tcp")
        inputs_container.mount(tcp_label)
        inputs_container.mount(tcp_switch)

        utp_switch = Switch(value=enable_utp, id="enable_utp")
        utp_label = Static("Enable uTP:", id="label_utp")
        inputs_container.mount(utp_label)
        inputs_container.mount(utp_switch)

        encryption_switch = Switch(value=enable_encryption, id="enable_encryption")
        encryption_label = Static("Enable Encryption:", id="label_encryption")
        inputs_container.mount(encryption_label)
        inputs_container.mount(encryption_switch)

        # Scrape switch
        auto_scrape_switch = Switch(value=auto_scrape, id="auto_scrape")
        auto_scrape_label = Static("Auto-scrape:", id="label_auto_scrape")
        inputs_container.mount(auto_scrape_label)
        inputs_container.mount(auto_scrape_switch)

        # NAT mapping switch
        enable_nat_switch = Switch(value=enable_nat, id="enable_nat_mapping")
        enable_nat_label = Static("Enable NAT Mapping:", id="label_nat_mapping")
        inputs_container.mount(enable_nat_label)
        inputs_container.mount(enable_nat_switch)

        # Store advanced config in a new section
        advanced_section = Static(id="advanced_section")
        advanced_section.update(Panel(advanced_table))
        # Insert before operations section
        operations_section = self.query_one("#operations", Static)
        operations_section.parent.mount(advanced_section, before=operations_section)  # type: ignore[attr-defined]

        # Performance metrics section
        await self._refresh_performance_metrics()
        self.set_interval(2.0, self._refresh_performance_metrics)  # type: ignore[attr-defined]

        # Scrape results section
        scrape_info = ""
        try:
            scrape_result = await self.session.get_scrape_result(self.info_hash_hex)
            if scrape_result:
                scrape_info = (
                    f"Seeders: {scrape_result.seeders} | "
                    f"Leechers: {scrape_result.leechers} | "
                    f"Completed: {scrape_result.completed} | "
                    f"Last Scrape: {scrape_result.last_scrape_time:.0f}s ago"
                )
            else:
                scrape_info = "No scrape data available. Press 's' to scrape."
        except Exception:
            scrape_info = "Scrape data unavailable"

        if scrape_info:
            scrape_table = Table(
                title="Scrape Results", expand=True, show_header=False, box=None
            )
            scrape_table.add_column("Info", style="cyan", ratio=1)
            scrape_table.add_column("Value", style="green", ratio=2)

            if scrape_result:
                scrape_table.add_row("Seeders", str(scrape_result.seeders))
                scrape_table.add_row("Leechers", str(scrape_result.leechers))
                scrape_table.add_row("Completed", str(scrape_result.completed))
                scrape_table.add_row("Scrape Count", str(scrape_result.scrape_count))
                scrape_table.add_row(
                    "Last Scrape", f"{scrape_result.last_scrape_time:.0f}s ago"
                )
            else:
                scrape_table.add_row("Status", "No cached scrape data")

            scrape_section = Static(id="scrape_section")
            scrape_section.update(Panel(scrape_table))
            operations_section.parent.mount(scrape_section, before=operations_section)  # type: ignore[attr-defined]

        # Operations section
        ops_table = Table(
            title="Torrent Operations", expand=True, show_header=False, box=None
        )
        ops_table.add_column("Operation", style="cyan", ratio=1)
        ops_table.add_column("Description", style="dim", ratio=2)

        ops_table.add_row(
            "Force Announce", "Manually trigger tracker announce (key: a)"
        )
        ops_table.add_row("Force Scrape", "Manually trigger tracker scrape (key: s)")
        ops_table.add_row("Refresh PEX", "Refresh peer exchange data (key: e)")
        ops_table.add_row("Rehash", "Re-verify torrent pieces (key: h)")
        ops_table.add_row("Pause", "Pause torrent download (key: p)")
        ops_table.add_row("Resume", "Resume paused torrent (key: r)")
        ops_table.add_row("Remove", "Remove torrent from session (key: delete)")

        operations_section.update(Panel(ops_table))

        errors_widget.update("")

        # Focus first input
        down_input.focus()

    async def _refresh_performance_metrics(self) -> None:  # pragma: no cover
        """Refresh per-torrent performance metrics display."""
        try:
            metrics_widget = self.query_one("#performance_metrics", Static)
            info_hash_bytes = bytes.fromhex(self.info_hash_hex)

            # Get detailed metrics using the helper from TerminalDashboard
            # We'll use the session to get torrent status and calculate metrics
            all_status = await self.session.get_status()
            torrent_status = all_status.get(self.info_hash_hex, {})

            # Get torrent session for piece manager access
            async with self.session.lock:
                torrent_session = self.session.torrents.get(info_hash_bytes)

            from rich.table import Table

            table = Table(
                title="Performance Metrics", expand=True, show_header=False, box=None
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            # Basic stats
            progress = float(torrent_status.get("progress", 0.0)) * 100
            down_rate = float(torrent_status.get("download_rate", 0.0))
            up_rate = float(torrent_status.get("upload_rate", 0.0))

            def format_speed(s: float) -> str:
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            table.add_row("Progress", f"{progress:.1f}%")
            table.add_row("Download Rate", format_speed(down_rate))
            table.add_row("Upload Rate", format_speed(up_rate))

            # Get piece statistics
            if torrent_session and hasattr(torrent_session, "piece_manager"):
                try:
                    piece_manager = torrent_session.piece_manager
                    if hasattr(piece_manager, "get_statistics"):
                        piece_stats = piece_manager.get_statistics()
                        pieces_completed = piece_stats.get("pieces_completed", 0)
                        pieces_total = piece_stats.get("pieces_total", 0)
                        pieces_failed = piece_stats.get("pieces_failed", 0)

                        table.add_row("", "")
                        table.add_row("[bold]Piece Statistics[/bold]", "")
                        table.add_row(
                            "Pieces Completed", f"{pieces_completed}/{pieces_total}"
                        )
                        if pieces_failed > 0:
                            table.add_row("Pieces Failed", str(pieces_failed))

                        # Calculate ETA
                        if down_rate > 0 and pieces_total > pieces_completed:
                            remaining_pieces = pieces_total - pieces_completed
                            # Estimate: assume average piece size
                            total_size = float(torrent_status.get("total_size", 0))
                            if total_size > 0 and pieces_total > 0:
                                avg_piece_size = total_size / pieces_total
                                remaining_bytes = remaining_pieces * avg_piece_size
                                eta_seconds = (
                                    remaining_bytes / down_rate if down_rate > 0 else 0
                                )

                                if eta_seconds > 0:
                                    if eta_seconds < 60:
                                        eta_str = f"{eta_seconds:.0f}s"
                                    elif eta_seconds < 3600:
                                        eta_str = f"{eta_seconds / 60:.1f}m"
                                    else:
                                        eta_str = f"{eta_seconds / 3600:.1f}h"
                                    table.add_row("Estimated ETA", eta_str)
                except Exception:
                    pass

            # Get connection count
            try:
                peers = await self.session.get_peers_for_torrent(self.info_hash_hex)
                connection_count = len(peers) if peers else 0
                table.add_row("", "")
                table.add_row("[bold]Connections[/bold]", "")
                table.add_row("Connected Peers", str(connection_count))
            except Exception:
                pass

            # Get total downloaded/uploaded
            total_downloaded = float(torrent_status.get("total_downloaded", 0))
            total_uploaded = float(torrent_status.get("total_uploaded", 0))

            def format_bytes(b: float) -> str:
                if b >= 1024 * 1024 * 1024:
                    return f"{b / (1024**3):.2f} GB"
                if b >= 1024 * 1024:
                    return f"{b / (1024**2):.2f} MB"
                if b >= 1024:
                    return f"{b / 1024:.2f} KB"
                return f"{b:.0f} B"

            table.add_row("", "")
            table.add_row("[bold]Totals[/bold]", "")
            table.add_row("Total Downloaded", format_bytes(total_downloaded))
            table.add_row("Total Uploaded", format_bytes(total_uploaded))

            metrics_widget.update(Panel(table))
        except Exception as e:
            logger.debug(f"Error refreshing performance metrics: {e}")
            # Silently fail to avoid disrupting config editing

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "save":
            await self._save_limits()
        elif event.button.id == "reset":
            await self._reset_limits()
        elif event.button.id == "files":
            await self._show_file_selection()
        elif event.button.id == "cancel":
            self.app.pop_screen()  # type: ignore[attr-defined]

    async def _save_limits(self) -> None:  # pragma: no cover
        """Save rate limits, queue priority, and advanced options."""
        errors_widget = self.query_one("#errors", Static)
        content = self.query_one("#content", Static)

        try:
            inputs_container = self.query_one("#inputs", Container)
            down_input = inputs_container.query_one("#down_limit", Input)
            up_input = inputs_container.query_one("#up_limit", Input)

            down_str = down_input.value.strip()
            up_str = up_input.value.strip()

            if not down_str:
                down_str = "0"
            if not up_str:
                up_str = "0"

            down_kib = int(down_str)
            up_kib = int(up_str)

            if down_kib < 0:
                raise ValueError("Download limit must be >= 0")
            if up_kib < 0:
                raise ValueError("Upload limit must be >= 0")

            success = await self.session.set_rate_limits(
                self.info_hash_hex, down_kib, up_kib
            )

            if not success:
                errors_widget.update(
                    Panel(
                        "Failed to save rate limits. Torrent may not exist.",
                        title="Error",
                        border_style="red",
                    )
                )
                return

            # Save queue priority if available
            if self.session.queue_manager:
                try:
                    # Check if priority input exists
                    priority_widgets = inputs_container.query(
                        "#queue_priority", Input
                    )
                    if priority_widgets:
                        priority_input = priority_widgets[0]
                        priority_str = priority_input.value.strip().lower()
                        valid_priorities = [
                            "maximum",
                            "high",
                            "normal",
                            "low",
                            "paused",
                        ]
                        if priority_str in valid_priorities:
                            from ccbt.models import TorrentPriority

                            priority_enum = TorrentPriority(priority_str)
                            info_hash_bytes = bytes.fromhex(self.info_hash_hex)
                            await self.session.queue_manager.set_priority(
                                info_hash_bytes, priority_enum
                            )
                except Exception:
                    # Queue priority update failed, but rate limits succeeded
                    pass

            # Save advanced options if available
            info_hash_bytes = bytes.fromhex(self.info_hash_hex)
            async with self.session.lock:
                torrent_session = self.session.torrents.get(info_hash_bytes)
                if torrent_session:
                    # Get advanced option values
                    try:
                        piece_selection_widgets = inputs_container.query(
                            "#piece_selection", Select
                        )
                        if piece_selection_widgets:
                            piece_selection = piece_selection_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["piece_selection"] = (
                                    piece_selection
                                )
                            # Try to set via piece manager if available
                            if hasattr(torrent_session, "piece_manager"):
                                try:
                                    # Set selection strategy as string (piece manager will handle conversion if needed)
                                    if hasattr(
                                        torrent_session.piece_manager,
                                        "selection_strategy",
                                    ):
                                        torrent_session.piece_manager.selection_strategy = piece_selection
                                    # Also try setting via config if available
                                    if hasattr(
                                        torrent_session.piece_manager, "config"
                                    ) and hasattr(
                                        torrent_session.piece_manager.config, "strategy"
                                    ):
                                        torrent_session.piece_manager.config.strategy.piece_selection = piece_selection
                                except Exception:
                                    pass

                        streaming_widgets = inputs_container.query(
                            "#streaming_mode", Switch
                        )
                        if streaming_widgets:
                            streaming_mode = streaming_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["streaming_mode"] = (
                                    streaming_mode
                                )

                        seq_window_widgets = inputs_container.query(
                            "#sequential_window", Input
                        )
                        if seq_window_widgets:
                            seq_window_str = seq_window_widgets[0].value.strip()
                            if seq_window_str:
                                try:
                                    seq_window = int(seq_window_str)
                                    if seq_window > 0:
                                        if hasattr(torrent_session, "options"):
                                            torrent_session.options[
                                                "sequential_window_size"
                                            ] = seq_window
                                except ValueError:
                                    pass

                        max_peers_widgets = inputs_container.query(
                            "#max_peers", Input
                        )
                        if max_peers_widgets:
                            max_peers_str = max_peers_widgets[0].value.strip()
                            if max_peers_str:
                                try:
                                    max_peers = int(max_peers_str)
                                    if max_peers >= 0 and hasattr(
                                        torrent_session, "options"
                                    ):
                                        torrent_session.options[
                                            "max_peers_per_torrent"
                                        ] = max_peers
                                except ValueError:
                                    pass

                        tcp_widgets = inputs_container.query("#enable_tcp", Switch)
                        if tcp_widgets:
                            enable_tcp = tcp_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["enable_tcp"] = enable_tcp

                        utp_widgets = inputs_container.query("#enable_utp", Switch)
                        if utp_widgets:
                            enable_utp = utp_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["enable_utp"] = enable_utp

                        encryption_widgets = inputs_container.query(
                            "#enable_encryption", Switch
                        )
                        if encryption_widgets:
                            enable_encryption = encryption_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["enable_encryption"] = (
                                    enable_encryption
                                )

                        auto_scrape_widgets = inputs_container.query(
                            "#auto_scrape", Switch
                        )
                        if auto_scrape_widgets:
                            auto_scrape = auto_scrape_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["auto_scrape"] = auto_scrape

                        enable_nat_widgets = inputs_container.query(
                            "#enable_nat_mapping", Switch
                        )
                        if enable_nat_widgets:
                            enable_nat = enable_nat_widgets[0].value
                            if hasattr(torrent_session, "options"):
                                torrent_session.options["enable_nat_mapping"] = (
                                    enable_nat
                                )
                    except Exception as e:
                        # Advanced options update failed, but rate limits succeeded
                        logger.debug("Failed to save advanced options: %s", e)

            errors_widget.update(
                Panel(
                    f"Configuration saved: Down={down_kib} KiB/s, Up={up_kib} KiB/s",
                    title="Success",
                    border_style="green",
                )
            )
            # Update content table
            config_table = Table(title="Rate Limit Configuration", expand=True)
            config_table.add_column("Setting", style="cyan", ratio=2)
            config_table.add_column("Current Value", style="green", ratio=2)
            config_table.add_column("Description", style="dim", ratio=4)
            config_table.add_row(
                "Download Limit",
                f"{down_kib} KiB/s" if down_kib > 0 else "Unlimited (0)",
                "Per-torrent download rate limit in KiB/s. Set to 0 for unlimited.",
            )
            config_table.add_row(
                "Upload Limit",
                f"{up_kib} KiB/s" if up_kib > 0 else "Unlimited (0)",
                "Per-torrent upload rate limit in KiB/s. Set to 0 for unlimited.",
            )
            content.update(Panel(config_table))

            # Close after brief delay
            await asyncio.sleep(1.5)
            self.app.pop_screen()  # type: ignore[attr-defined]
        except ValueError as e:
            errors_widget.update(
                Panel(str(e), title="Validation Error", border_style="red")
            )
        except Exception as e:
            errors_widget.update(
                Panel(
                    f"Unexpected error: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def _reset_limits(self) -> None:  # pragma: no cover
        """Reset rate limits to unlimited (0)."""
        inputs_container = self.query_one("#inputs", Container)
        down_input = inputs_container.query_one("#down_limit", Input)
        up_input = inputs_container.query_one("#up_limit", Input)
        down_input.value = "0"
        up_input.value = "0"
        down_input.focus()

    async def action_announce(self) -> None:  # pragma: no cover
        """Force announce to tracker."""
        errors_widget = self.query_one("#errors", Static)
        try:
            success = await self.session.force_announce(self.info_hash_hex)
            if success:
                errors_widget.update(
                    Panel(
                        "Announce sent successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                errors_widget.update(
                    Panel("Failed to send announce", title="Error", border_style="red")
                )
        except Exception as e:
            errors_widget.update(
                Panel(f"Announce error: {e}", title="Error", border_style="red")
            )

    async def action_scrape(self) -> None:  # pragma: no cover
        """Force scrape from tracker."""
        errors_widget = self.query_one("#errors", Static)
        try:
            # Try using CLI scrape command for better integration
            if hasattr(self, "_command_executor") and self._command_executor:
                success, msg, _ = await self._command_executor.execute_click_command(
                    f"scrape torrent {self.info_hash_hex} --force"
                )
                if success:
                    errors_widget.update(
                        Panel(
                            f"Scrape completed: {msg}",
                            title="Success",
                            border_style="green",
                        )
                    )
                    # Refresh scrape results display
                    await self._refresh_scrape_section()
                else:
                    errors_widget.update(
                        Panel(
                            f"Scrape failed: {msg}", title="Error", border_style="red"
                        )
                    )
            else:
                # Fallback to session method
                success = await self.session.force_scrape(self.info_hash_hex)
                if success:
                    errors_widget.update(
                        Panel(
                            "Scrape requested successfully",
                            title="Success",
                            border_style="green",
                        )
                    )
                    # Refresh scrape results display
                    await self._refresh_scrape_section()
                else:
                    errors_widget.update(
                        Panel(
                            "Failed to request scrape",
                            title="Error",
                            border_style="red",
                        )
                    )
        except Exception as e:
            errors_widget.update(
                Panel(f"Scrape error: {e}", title="Error", border_style="red")
            )

    async def _refresh_scrape_section(self) -> None:  # pragma: no cover
        """Refresh the scrape results section."""
        try:
            scrape_section_widgets = self.query("#scrape_section", Static)
            if not scrape_section_widgets:
                return

            scrape_section = scrape_section_widgets[0]
            scrape_result = await self.session.get_scrape_result(self.info_hash_hex)

            if scrape_result:
                scrape_table = Table(
                    title="Scrape Results", expand=True, show_header=False, box=None
                )
                scrape_table.add_column("Info", style="cyan", ratio=1)
                scrape_table.add_column("Value", style="green", ratio=2)

                scrape_table.add_row("Seeders", str(scrape_result.seeders))
                scrape_table.add_row("Leechers", str(scrape_result.leechers))
                scrape_table.add_row("Completed", str(scrape_result.completed))
                scrape_table.add_row("Scrape Count", str(scrape_result.scrape_count))
                scrape_table.add_row(
                    "Last Scrape", f"{scrape_result.last_scrape_time:.0f}s ago"
                )

                scrape_section.update(Panel(scrape_table))
            else:
                scrape_table = Table(
                    title="Scrape Results", expand=True, show_header=False, box=None
                )
                scrape_table.add_column("Info", style="cyan", ratio=1)
                scrape_table.add_column("Value", style="green", ratio=2)
                scrape_table.add_row("Status", "No cached scrape data")
                scrape_section.update(Panel(scrape_table))
        except Exception:
            pass  # Ignore errors refreshing scrape section

    async def action_pex(self) -> None:  # pragma: no cover
        """Refresh PEX data."""
        errors_widget = self.query_one("#errors", Static)
        try:
            success = await self.session.refresh_pex(self.info_hash_hex)
            if success:
                errors_widget.update(
                    Panel(
                        "PEX refreshed successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                errors_widget.update(
                    Panel("Failed to refresh PEX", title="Error", border_style="red")
                )
        except Exception as e:
            errors_widget.update(
                Panel(f"PEX error: {e}", title="Error", border_style="red")
            )

    async def action_rehash(self) -> None:  # pragma: no cover
        """Rehash torrent pieces."""
        errors_widget = self.query_one("#errors", Static)
        try:
            success = await self.session.rehash_torrent(self.info_hash_hex)
            if success:
                errors_widget.update(
                    Panel(
                        "Rehash started successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                errors_widget.update(
                    Panel("Failed to start rehash", title="Error", border_style="red")
                )
        except Exception as e:
            errors_widget.update(
                Panel(f"Rehash error: {e}", title="Error", border_style="red")
            )

    async def action_pause(self) -> None:  # pragma: no cover
        """Pause torrent."""
        errors_widget = self.query_one("#errors", Static)
        try:
            success = await self.session.pause_torrent(self.info_hash_hex)
            if success:
                errors_widget.update(
                    Panel(
                        "Torrent paused successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                errors_widget.update(
                    Panel("Failed to pause torrent", title="Error", border_style="red")
                )
        except Exception as e:
            errors_widget.update(
                Panel(f"Pause error: {e}", title="Error", border_style="red")
            )

    async def action_resume(self) -> None:  # pragma: no cover
        """Resume torrent."""
        errors_widget = self.query_one("#errors", Static)
        try:
            success = await self.session.resume_torrent(self.info_hash_hex)
            if success:
                errors_widget.update(
                    Panel(
                        "Torrent resumed successfully",
                        title="Success",
                        border_style="green",
                    )
                )
            else:
                errors_widget.update(
                    Panel("Failed to resume torrent", title="Error", border_style="red")
                )
        except Exception as e:
            errors_widget.update(
                Panel(f"Resume error: {e}", title="Error", border_style="red")
            )

    async def action_files(self) -> None:  # pragma: no cover
        """Open file selection management."""
        await self._show_file_selection()

    async def action_reorder(self) -> None:  # pragma: no cover
        """Reorder torrent in queue."""
        errors_widget = self.query_one("#errors", Static)
        if not self.session.queue_manager:
            errors_widget.update(
                Panel("Queue manager not available", title="Error", border_style="red")
            )
            return

        # Show input for new position
        position_input = Input(
            placeholder="Enter new queue position (0 = highest)", id="reorder_position"
        )
        self.mount(position_input)  # type: ignore[attr-defined]
        position_input.focus()
        self._pending_reorder = True  # type: ignore[attr-defined]

    async def on_input_submitted(self, message: Any) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle input submission events."""
        if message.input.id == "reorder_position":
            position_str = message.value.strip()
            message.input.display = False
            if hasattr(self, "_pending_reorder") and self._pending_reorder:
                errors_widget = self.query_one("#errors", Static)
                try:
                    position = int(position_str)
                    if position < 0:
                        msg = "Position must be >= 0"
                        raise ValueError(msg)

                    info_hash_bytes = bytes.fromhex(self.info_hash_hex)
                    success = await self.session.queue_manager.reorder_torrent(
                        info_hash_bytes, position
                    )

                    if success:
                        errors_widget.update(
                            Panel(
                                f"Moved torrent to position {position}",
                                title="Success",
                                border_style="green",
                            )
                        )
                    else:
                        errors_widget.update(
                            Panel(
                                "Failed to reorder torrent",
                                title="Error",
                                border_style="red",
                            )
                        )
                except ValueError as e:
                    errors_widget.update(
                        Panel(str(e), title="Validation Error", border_style="red")
                    )
                except Exception as e:
                    errors_widget.update(
                        Panel(f"Error: {e}", title="Error", border_style="red")
                    )
                finally:
                    self._pending_reorder = False  # type: ignore[attr-defined]

    async def on_key(self, event: Any) -> None:  # type: ignore[override]  # pragma: no cover
        """Handle key presses."""
        if event.key == "delete":
            # Remove torrent
            errors_widget = self.query_one("#errors", Static)
            try:
                success = await self.session.remove(self.info_hash_hex)
                if success:
                    errors_widget.update(
                        Panel(
                            "Torrent removed successfully",
                            title="Success",
                            border_style="green",
                        )
                    )
                    # Close screen after brief delay
                    await asyncio.sleep(1.0)
                    self.app.pop_screen()  # type: ignore[attr-defined]
                else:
                    errors_widget.update(
                        Panel(
                            "Failed to remove torrent",
                            title="Error",
                            border_style="red",
                        )
                    )
            except Exception as e:
                errors_widget.update(
                    Panel(f"Remove error: {e}", title="Error", border_style="red")
                )
        else:
            await super().on_key(event)  # type: ignore[misc]

    async def _show_file_selection(self) -> None:  # pragma: no cover
        """Show file selection management screen."""
        # Open dedicated FileSelectionScreen
        if FileSelectionScreen is None:  # type: ignore[comparison-overlap]
            errors_widget = self.query_one("#errors", Static)
            errors_widget.update(
                Panel(
                    "File selection screen not available",
                    title="Error",
                    border_style="red",
                )
            )
            return

        screen = FileSelectionScreen(self.session, self.info_hash_hex)
        await self.app.push_screen(screen)  # type: ignore[attr-defined]

