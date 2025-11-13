"""Dialog screens for the terminal dashboard."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
    from textual.screen import ComposeResult
else:
    try:
        from textual.screen import ComposeResult
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, DataTable, Input, Select, Static, Switch
except ImportError:
    # Fallback for when Textual is not available
    class ModalScreen:  # type: ignore[no-redef]
        """ModalScreen class stub."""

    class Container:  # type: ignore[no-redef]
        """Container widget stub."""

    class Horizontal:  # type: ignore[no-redef]
        """Horizontal layout widget stub."""

    class Vertical:  # type: ignore[no-redef]
        """Vertical layout widget stub."""

    class Static:  # type: ignore[no-redef]
        """Static widget stub."""

    class Button:  # type: ignore[no-redef]
        """Button widget stub."""

    class DataTable:  # type: ignore[no-redef]
        """DataTable widget stub."""

    class Input:  # type: ignore[no-redef]
        """Input widget stub."""

    class Select:  # type: ignore[no-redef]
        """Select widget stub."""

    class Switch:  # type: ignore[no-redef]
        """Switch widget stub."""

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager


class AddTorrentScreen(ModalScreen):  # type: ignore[misc]
    """Advanced torrent addition screen with multi-step form.

    Provides comprehensive UI for adding torrents with all options:
    - Torrent path/magnet input
    - Output directory selection
    - File selection
    - Rate limits
    - Queue priority
    - Resume option
    """

    DEFAULT_CSS = """
    AddTorrentScreen {
        align: center middle;
    }
    #dialog {
        width: 80;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
    }
    #step_indicator {
        height: 3;
        margin: 1;
    }
    #content {
        height: 1fr;
        margin: 1;
        overflow-y: auto;
        overflow-x: hidden;
        scrollbar-size: 1 1;
    }
    #xet_switches, #ipfs_switches {
        height: auto;
        min-height: 5;
        width: 100%;
        display: block;
    }
    #xet_switches > Horizontal, #ipfs_switches > Horizontal {
        width: 100%;
        height: auto;
        min-height: 1;
        margin: 1;
        display: block;
    }
    Horizontal {
        width: 100%;
        height: auto;
        display: block;
    }
    Switch {
        width: auto;
        height: auto;
        display: block;
    }
    Static {
        width: 100%;
        height: auto;
    }
    #buttons {
        height: 3;
        align: center middle;
        margin: 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+n", "next", "Next Step"),
        ("ctrl+p", "previous", "Previous Step"),
        ("ctrl+s", "submit", "Submit"),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        dashboard: Any,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize add torrent screen.

        Args:
            session: Async session manager
            dashboard: TerminalDashboard instance for callbacks
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            *args, **kwargs
        )  # pragma: no cover - AddTorrentScreen initialization, tested via integration
        self.session = session  # pragma: no cover - AddTorrentScreen initialization
        self.dashboard = dashboard  # pragma: no cover - AddTorrentScreen initialization
        self.current_step = 1  # pragma: no cover - AddTorrentScreen initialization
        self.total_steps = 11  # Increased from 8 to 11 for Scrape, uTP, and NAT steps  # pragma: no cover - AddTorrentScreen initialization

        # Form data
        self.torrent_path: str = (
            ""  # pragma: no cover - AddTorrentScreen initialization
        )
        self.output_dir: str = "."  # pragma: no cover - AddTorrentScreen initialization
        self.files_selection: list[
            int
        ] = []  # pragma: no cover - AddTorrentScreen initialization
        self.file_priorities: dict[
            int, str
        ] = {}  # pragma: no cover - AddTorrentScreen initialization
        self.download_limit: int = (
            0  # pragma: no cover - AddTorrentScreen initialization
        )
        self.upload_limit: int = 0  # pragma: no cover - AddTorrentScreen initialization
        self.queue_priority: str = (
            "normal"  # pragma: no cover - AddTorrentScreen initialization
        )
        self.resume: bool = False  # pragma: no cover - AddTorrentScreen initialization

        # Xet options
        self.enable_xet: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )
        self.xet_deduplication: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )
        self.xet_p2p_cas: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )
        self.xet_compression: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )

        # IPFS options
        self.enable_ipfs: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )
        self.ipfs_pin: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )

        # Scrape options
        self.auto_scrape: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )

        # uTP options
        self.enable_utp: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )

        # NAT options
        self.enable_nat_mapping: bool = (
            False  # pragma: no cover - AddTorrentScreen initialization
        )

        # Torrent data (loaded after step 1)
        self.torrent_data: dict[str, Any] | None = (
            None  # pragma: no cover - AddTorrentScreen initialization
        )

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the add torrent screen."""
        with Container(id="dialog"):
            yield Static("", id="step_indicator")
            yield Container(id="content")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Previous", id="previous", variant="default")
                yield Button("Next", id="next", variant="primary")

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and show first step."""
        await self._show_step()

    async def _show_step(self) -> None:  # pragma: no cover
        """Show current step content."""
        # Update step indicator
        indicator = self.query_one("#step_indicator")
        steps = [
            f"{'✓' if i < self.current_step else str(i)}"
            for i in range(1, self.total_steps + 1)
        ]
        indicator.update(
            f"Step {self.current_step}/{self.total_steps}: {' → '.join(steps)}"
        )

        # Clear content
        content = self.query_one("#content", Container)
        try:
            content.remove_children()
        except Exception:
            # If remove_children fails, try clearing differently
            for child in list(content.children):
                try:
                    child.remove()
                except Exception:
                    pass

        # Show step-specific content
        if self.current_step == 1:
            await self._show_step1_torrent_input(content)
        elif self.current_step == 2:
            await self._show_step2_output_dir(content)
        elif self.current_step == 3:
            await self._show_step3_file_selection(content)
        elif self.current_step == 4:
            await self._show_step4_rate_limits(content)
        elif self.current_step == 5:
            await self._show_step5_queue_priority(content)
        elif self.current_step == 6:
            await self._show_step6_resume_option(content)
        elif self.current_step == 7:
            await self._show_step7_xet_options(content)
        elif self.current_step == 8:
            await self._show_step8_ipfs_options(content)
        elif self.current_step == 9:
            await self._show_step9_scrape_options(content)
        elif self.current_step == 10:
            await self._show_step10_utp_options(content)
        elif self.current_step == 11:
            await self._show_step11_nat_options(content)

        # Update button states
        prev_btn = self.query_one("#previous")
        next_btn = self.query_one("#next")
        prev_btn.disabled = self.current_step == 1  # type: ignore[attr-defined]
        if self.current_step == self.total_steps:
            next_btn.label = "Submit"  # type: ignore[attr-defined]
        else:
            next_btn.label = "Next"  # type: ignore[attr-defined]

    async def _show_step1_torrent_input(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 1: Torrent path/magnet input."""
        input_widget = Input(
            placeholder="Enter torrent file path or magnet link",
            value=self.torrent_path,
            id="torrent_input",
        )
        help_widget = Static(  # type: ignore[assignment]
            "Enter the path to a .torrent file or a magnet link:\n\n"
            "Examples:\n"
            "  /path/to/file.torrent\n"
            "  magnet:?xt=urn:btih:...",
            id="step1_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        content.mount(input_widget)  # type: ignore[attr-defined]
        input_widget.focus()

    async def _show_step2_output_dir(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 2: Output directory selection."""
        input_widget = Input(
            placeholder="Output directory (default: current directory)",
            value=self.output_dir,
            id="output_dir_input",
        )
        help_widget = Static(  # type: ignore[assignment]
            "Enter the directory where files should be downloaded:\n\n"
            "Leave empty to use current directory.",
            id="step2_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        content.mount(input_widget)  # type: ignore[attr-defined]
        input_widget.focus()

    async def _show_step3_file_selection(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 3: File selection (if torrent has files)."""
        if not self.torrent_data:
            error_widget = Static(  # type: ignore[assignment]
                "No torrent data loaded. Please go back to step 1.",
                id="step3_error",
            )
            content.mount(error_widget)  # type: ignore[attr-defined]
            return

        # Check if torrent has files
        files = self.torrent_data.get("files", [])
        if not files:
            no_files_widget = Static(  # type: ignore[assignment]
                "This torrent has no files to select.",
                id="step3_no_files",
            )
            content.mount(no_files_widget)  # type: ignore[attr-defined]
            return

        # Create file selection table
        table = DataTable(id="file_selection_table", zebra_stripes=True)
        table.add_columns("Select", "Priority", "Size", "File Name")

        for idx, file_info in enumerate(files):
            selected = "✓" if idx in self.files_selection else " "
            priority = self.file_priorities.get(idx, "normal")
            size = file_info.get("length", 0)
            size_str = (
                f"{size / (1024 * 1024):.2f} MB"
                if size > 1024 * 1024
                else f"{size / 1024:.2f} KB"
            )
            name = file_info.get("path", f"File {idx}")

            table.add_row(selected, priority, size_str, name, key=str(idx))

        help_widget = Static(  # type: ignore[assignment]
            "Select files to download and set priorities:\n"
            "  Space: Toggle selection\n"
            "  P: Change priority\n"
            "  A: Select all\n"
            "  D: Deselect all",
            id="step3_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        content.mount(table)  # type: ignore[attr-defined]
        table.focus()

    async def _show_step4_rate_limits(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 4: Rate limit configuration."""
        down_input = Input(
            placeholder="Download limit (KiB/s, 0 = unlimited)",
            value=str(self.download_limit) if self.download_limit > 0 else "",
            id="download_limit_input",
        )
        up_input = Input(
            placeholder="Upload limit (KiB/s, 0 = unlimited)",
            value=str(self.upload_limit) if self.upload_limit > 0 else "",
            id="upload_limit_input",
        )

        help_widget = Static(  # type: ignore[assignment]
            "Set rate limits for this torrent:\n\n"
            "Enter 0 or leave empty for unlimited.",
            id="step4_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        down_label = Static("Download Limit (KiB/s):", id="down_label")  # type: ignore[assignment]
        content.mount(down_label)  # type: ignore[attr-defined]
        content.mount(down_input)  # type: ignore[attr-defined]
        up_label = Static("Upload Limit (KiB/s):", id="up_label")  # type: ignore[assignment]
        content.mount(up_label)  # type: ignore[attr-defined]
        content.mount(up_input)  # type: ignore[attr-defined]
        down_input.focus()

    async def _show_step5_queue_priority(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 5: Queue priority selection."""
        priority_options = [
            ("Maximum", "maximum"),
            ("High", "high"),
            ("Normal", "normal"),
            ("Low", "low"),
            ("Paused", "paused"),
        ]

        select_widget = Select(
            options=priority_options,
            value=self.queue_priority,
            id="queue_priority_select",
        )

        help_widget = Static(  # type: ignore[assignment]
            "Select queue priority for this torrent:\n\n"
            "Higher priority torrents will be started first.",
            id="step5_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        content.mount(select_widget)  # type: ignore[attr-defined]
        select_widget.focus()

    async def _show_step6_resume_option(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 6: Resume option."""
        switch_widget = Switch(
            value=self.resume,
            id="resume_switch",
        )

        help_widget = Static(  # type: ignore[assignment]
            "Resume from checkpoint if available:\n\n"
            "If enabled, the download will resume from the last checkpoint.",
            id="step6_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined, arg-type]
        resume_label = Static("Resume from checkpoint:", id="resume_label")  # type: ignore[assignment]
        resume_row = Horizontal(  # type: ignore[attr-defined]
            resume_label,
            switch_widget,
        )
        content.mount(resume_row)  # type: ignore[attr-defined, arg-type]
        switch_widget.focus()

    async def _show_step7_xet_options(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 7: Xet protocol options."""
        help_widget = Static(  # type: ignore[assignment]
            "Xet Protocol Options:\n\n"
            "Xet enables content-defined chunking and deduplication.\n"
            "Useful for reducing storage when downloading similar content.",
            id="step7_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Create a vertical container for all switches to ensure they're visible
        switches_container = Vertical(id="xet_switches")  # type: ignore[assignment]
        # Mount the container first before adding children
        content.mount(switches_container)  # type: ignore[attr-defined, arg-type]

        # Enable Xet switch
        enable_xet_switch = Switch(
            value=self.enable_xet,
            id="enable_xet_switch",
        )
        enable_xet_label = Static("Enable Xet Protocol:", id="enable_xet_label")  # type: ignore[assignment]
        xet_row = Horizontal(  # type: ignore[attr-defined]
            enable_xet_label,
            enable_xet_switch,
        )
        switches_container.mount(xet_row)  # type: ignore[arg-type]

        # Deduplication switch
        dedup_switch = Switch(
            value=self.xet_deduplication,
            id="xet_deduplication_switch",
        )
        dedup_label = Static("Enable Deduplication:", id="xet_deduplication_label")  # type: ignore[assignment]
        dedup_row = Horizontal(  # type: ignore[attr-defined]
            dedup_label,
            dedup_switch,
        )
        switches_container.mount(dedup_row)  # type: ignore[arg-type]

        # P2P CAS switch
        p2p_cas_switch = Switch(
            value=self.xet_p2p_cas,
            id="xet_p2p_cas_switch",
        )
        p2p_cas_label = Static(
            "Enable P2P Content-Addressed Storage:", id="xet_p2p_cas_label"
        )  # type: ignore[assignment]
        p2p_cas_row = Horizontal(  # type: ignore[attr-defined]
            p2p_cas_label,
            p2p_cas_switch,
        )
        switches_container.mount(p2p_cas_row)  # type: ignore[arg-type]

        # Compression switch
        compression_switch = Switch(
            value=self.xet_compression,
            id="xet_compression_switch",
        )
        compression_label = Static("Enable Compression:", id="xet_compression_label")  # type: ignore[assignment]
        compression_row = Horizontal(  # type: ignore[attr-defined]
            compression_label,
            compression_switch,
        )
        switches_container.mount(compression_row)  # type: ignore[arg-type]

        # Add link to Xet management screen
        xet_help = Static(  # type: ignore[assignment]
            "\n[dim]Press Ctrl+X in main dashboard to manage Xet settings globally[/dim]",
            id="xet_help_link",
        )
        content.mount(xet_help)  # type: ignore[attr-defined]

        # Focus the first switch and refresh to ensure visibility
        enable_xet_switch.focus()
        self.refresh(layout=True)

    async def _show_step8_ipfs_options(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 8: IPFS protocol options."""
        help_widget = Static(  # type: ignore[assignment]
            "IPFS Protocol Options:\n\n"
            "IPFS enables content-addressed storage and peer-to-peer content sharing.\n"
            "Content can be accessed via IPFS CID after download.",
            id="step8_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Create a vertical container for all switches
        switches_container = Vertical(id="ipfs_switches")  # type: ignore[assignment]
        # Mount the container first before adding children
        content.mount(switches_container)  # type: ignore[attr-defined, arg-type]

        # Enable IPFS switch
        enable_ipfs_switch = Switch(
            value=self.enable_ipfs,
            id="enable_ipfs_switch",
        )
        enable_ipfs_label = Static("Enable IPFS Protocol:", id="enable_ipfs_label")  # type: ignore[assignment]
        ipfs_row = Horizontal(  # type: ignore[attr-defined]
            enable_ipfs_label,
            enable_ipfs_switch,
        )
        switches_container.mount(ipfs_row)  # type: ignore[arg-type]

        # Pin content switch
        pin_switch = Switch(
            value=self.ipfs_pin,
            id="ipfs_pin_switch",
        )
        pin_label = Static("Pin Content in IPFS:", id="ipfs_pin_label")  # type: ignore[assignment]
        pin_row = Horizontal(  # type: ignore[attr-defined]
            pin_label,
            pin_switch,
        )
        switches_container.mount(pin_row)  # type: ignore[arg-type]

        # Add link to IPFS management screen
        ipfs_help = Static(  # type: ignore[assignment]
            "\n[dim]Press Ctrl+I in main dashboard to manage IPFS content and peers[/dim]",
            id="ipfs_help_link",
        )
        content.mount(ipfs_help)  # type: ignore[attr-defined]

        enable_ipfs_switch.focus()
        self.refresh(layout=True)

    async def _show_step9_scrape_options(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 9: Scrape options."""
        help_widget = Static(  # type: ignore[assignment]
            "Scrape Options:\n\n"
            "Scraping queries tracker statistics (seeders, leechers, completed downloads).\n"
            "Auto-scrape will automatically scrape the tracker when the torrent is added.",
            id="step9_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Auto-scrape switch
        auto_scrape_switch = Switch(
            value=self.auto_scrape,
            id="auto_scrape_switch",
        )
        auto_scrape_label = Static("Auto-scrape on Add:", id="auto_scrape_label")  # type: ignore[assignment]
        auto_scrape_row = Horizontal(
            auto_scrape_label,
            auto_scrape_switch,
        )
        content.mount(auto_scrape_row)  # type: ignore[attr-defined, arg-type]

        # Add link to scrape results screen
        scrape_help = Static(  # type: ignore[assignment]
            "\n[dim]Press Ctrl+R in main dashboard to view scrape results[/dim]",
            id="scrape_help_link",
        )
        content.mount(scrape_help)  # type: ignore[attr-defined]

        auto_scrape_switch.focus()
        self.refresh(layout=True)

    async def _show_step10_utp_options(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 10: uTP protocol options."""
        help_widget = Static(  # type: ignore[assignment]
            "uTP (uTorrent Transport Protocol) Options:\n\n"
            "uTP provides reliable, ordered delivery over UDP with delay-based congestion control (BEP 29).\n"
            "Useful for better performance on networks with high latency or packet loss.",
            id="step10_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Enable uTP switch
        enable_utp_switch = Switch(
            value=self.enable_utp,
            id="enable_utp_switch",
        )
        enable_utp_label = Static("Enable uTP Transport:", id="enable_utp_label")  # type: ignore[assignment]
        utp_row = Horizontal(
            enable_utp_label,
            enable_utp_switch,
        )
        content.mount(utp_row)  # type: ignore[attr-defined, arg-type]

        # Add link to uTP management screen
        utp_help = Static(  # type: ignore[assignment]
            "\n[dim]Press Ctrl+U in main dashboard to configure uTP settings globally[/dim]",
            id="utp_help_link",
        )
        content.mount(utp_help)  # type: ignore[attr-defined]

        enable_utp_switch.focus()
        self.refresh(layout=True)

    async def _show_step11_nat_options(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 11: NAT traversal options."""
        help_widget = Static(  # type: ignore[assignment]
            "NAT Traversal Options:\n\n"
            "NAT traversal (NAT-PMP/UPnP) automatically maps ports on your router.\n"
            "This allows peers to connect to you directly, improving download speeds.",
            id="step11_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Enable NAT mapping switch
        enable_nat_switch = Switch(
            value=self.enable_nat_mapping,
            id="enable_nat_mapping_switch",
        )
        enable_nat_label = Static(
            "Enable NAT Port Mapping:", id="enable_nat_mapping_label"
        )  # type: ignore[assignment]
        nat_row = Horizontal(
            enable_nat_label,
            enable_nat_switch,
        )
        content.mount(nat_row)  # type: ignore[attr-defined, arg-type]

        # Add link to NAT management screen
        nat_help = Static(  # type: ignore[assignment]
            "\n[dim]Press Ctrl+N in main dashboard to manage NAT settings globally[/dim]",
            id="nat_help_link",
        )
        content.mount(nat_help)  # type: ignore[attr-defined]

        enable_nat_switch.focus()
        self.refresh(layout=True)

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "cancel":
            await self.action_cancel()
        elif event.button.id == "previous":
            await self.action_previous()
        elif event.button.id == "next":
            await self.action_next()

    async def action_cancel(self) -> None:  # pragma: no cover
        """Cancel torrent addition."""
        self.dismiss(None)  # type: ignore[attr-defined]

    async def action_previous(self) -> None:  # pragma: no cover
        """Go to previous step."""
        if self.current_step > 1:
            await self._save_current_step()
            self.current_step -= 1
            await self._show_step()

    async def action_next(self) -> None:  # pragma: no cover
        """Go to next step or submit."""
        if not await self._validate_current_step():
            return

        await self._save_current_step()

        if self.current_step < self.total_steps:
            self.current_step += 1
            await self._show_step()
        else:
            await self._submit()

    async def action_submit(self) -> None:  # pragma: no cover
        """Submit the form."""
        await self._submit()

    async def _validate_current_step(self) -> bool:  # pragma: no cover
        """Validate current step data."""
        if self.current_step == 1:
            torrent_input = self.query_one("#torrent_input")
            path = torrent_input.value.strip()  # type: ignore[attr-defined]
            if not path:
                self._show_error("Please enter a torrent path or magnet link")
                return False
            # Try to load torrent to validate (run in thread to avoid blocking UI)
            try:
                loop = asyncio.get_event_loop()
                if path.startswith("magnet:"):
                    self.torrent_data = await loop.run_in_executor(
                        None, self.session.parse_magnet_link, path
                    )
                else:
                    self.torrent_data = await loop.run_in_executor(
                        None, self.session.load_torrent, Path(path)
                    )
                if not self.torrent_data:
                    self._show_error(f"Could not load torrent: {path}")
                    return False
            except Exception as e:
                self._show_error(f"Error loading torrent: {e}")
                return False
        return True

    async def _save_current_step(self) -> None:  # pragma: no cover
        """Save data from current step."""
        if self.current_step == 1:
            torrent_input = self.query_one("#torrent_input")
            self.torrent_path = torrent_input.value.strip()  # type: ignore[attr-defined]
        elif self.current_step == 2:
            output_input = self.query_one("#output_dir_input")
            self.output_dir = output_input.value.strip() or "."  # type: ignore[attr-defined]
        elif self.current_step == 4:
            down_input = self.query_one("#download_limit_input")
            up_input = self.query_one("#upload_limit_input")
            try:
                self.download_limit = int(down_input.value.strip() or "0")  # type: ignore[attr-defined]
                self.upload_limit = int(up_input.value.strip() or "0")  # type: ignore[attr-defined]
            except ValueError:
                pass
        elif self.current_step == 5:
            priority_select = self.query_one("#queue_priority_select")
            self.queue_priority = priority_select.value  # type: ignore[attr-defined]
        elif self.current_step == 6:
            resume_switch = self.query_one("#resume_switch")
            self.resume = resume_switch.value  # type: ignore[attr-defined]
        elif self.current_step == 7:
            enable_xet_switch = self.query_one("#enable_xet_switch")
            self.enable_xet = enable_xet_switch.value  # type: ignore[attr-defined]
            dedup_switch = self.query_one("#xet_deduplication_switch")
            self.xet_deduplication = dedup_switch.value  # type: ignore[attr-defined]
            p2p_cas_switch = self.query_one("#xet_p2p_cas_switch")
            self.xet_p2p_cas = p2p_cas_switch.value  # type: ignore[attr-defined]
            compression_switch = self.query_one("#xet_compression_switch")
            self.xet_compression = compression_switch.value  # type: ignore[attr-defined]
        elif self.current_step == 8:
            enable_ipfs_switch = self.query_one("#enable_ipfs_switch")
            self.enable_ipfs = enable_ipfs_switch.value  # type: ignore[attr-defined]
            pin_switch = self.query_one("#ipfs_pin_switch")
            self.ipfs_pin = pin_switch.value  # type: ignore[attr-defined]
        elif self.current_step == 9:
            auto_scrape_switch = self.query_one("#auto_scrape_switch")
            self.auto_scrape = auto_scrape_switch.value  # type: ignore[attr-defined]
        elif self.current_step == 10:
            enable_utp_switch = self.query_one("#enable_utp_switch")
            self.enable_utp = enable_utp_switch.value  # type: ignore[attr-defined]
        elif self.current_step == 11:
            enable_nat_switch = self.query_one("#enable_nat_mapping_switch")
            self.enable_nat_mapping = enable_nat_switch.value  # type: ignore[attr-defined]

    def _show_error(self, message: str) -> None:  # pragma: no cover
        """Show error message."""
        content = self.query_one("#content")
        error_widget = Static(f"[red]Error: {message}[/red]", id="error_message")
        content.mount(error_widget)  # type: ignore[attr-defined]

    async def _submit(self) -> None:  # pragma: no cover
        """Submit the form and add torrent."""
        # Build options dict
        options: dict[str, Any] = {
            "resume": self.resume,
            "queue_priority": self.queue_priority,
        }

        # Add output directory (matching CLI --output option)
        if self.output_dir and self.output_dir != ".":
            options["output"] = self.output_dir

        if self.download_limit > 0:
            options["download_limit"] = self.download_limit
        if self.upload_limit > 0:
            options["upload_limit"] = self.upload_limit
        if self.files_selection:
            options["files_selection"] = self.files_selection
        if self.file_priorities:
            # Convert to list of "index=priority" strings
            options["file_priorities"] = [
                f"{idx}={pri}" for idx, pri in self.file_priorities.items()
            ]

        # Add Xet options (matching CLI option names)
        if self.enable_xet:
            options["enable_xet"] = True
        if self.xet_deduplication:
            options["xet_deduplication_enabled"] = True
        if self.xet_p2p_cas:
            options["xet_use_p2p_cas"] = True
        if self.xet_compression:
            options["xet_compression_enabled"] = True

        # Add IPFS options (note: IPFS options are not in CLI download command,
        # but we support them for consistency with advanced add screen)
        if self.enable_ipfs:
            options["enable_ipfs"] = True
        if self.ipfs_pin:
            options["ipfs_pin"] = True

        # Add Scrape options (note: auto_scrape is not a CLI option,
        # but we support it for consistency)
        if self.auto_scrape:
            options["auto_scrape"] = True

        # Add uTP options (matching CLI option names)
        if self.enable_utp:
            options["enable_utp"] = True

        # Add NAT options (matching CLI option names)
        if self.enable_nat_mapping:
            options["enable_nat_pmp"] = True
            options["enable_upnp"] = True
            options["auto_map_ports"] = True

        # Close screen and call dashboard's _process_add_torrent
        self.dismiss(True)  # type: ignore[attr-defined]
        # Access private method for internal dashboard functionality
        await self.dashboard._process_add_torrent(self.torrent_path, options)

