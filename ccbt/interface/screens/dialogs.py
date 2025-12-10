"""Dialog screens for the terminal dashboard."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ccbt.i18n import _

logger = logging.getLogger(__name__)

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
    from textual.widgets import Button, DataTable, Input, Select, Static, Switch, Checkbox
    from textual import log
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

    class Checkbox:  # type: ignore[no-redef]
        """Checkbox widget stub."""

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager


class QuickAddTorrentScreen(ModalScreen):  # type: ignore[misc]
    """Quick torrent addition screen with simple input.

    Provides a simple UI for quickly adding torrents with default settings.
    """

    DEFAULT_CSS = """
    QuickAddTorrentScreen {
        align: center middle;
    }
    #dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
    }
    #content {
        height: auto;
        margin: 1;
    }
    #buttons {
        height: 3;
        align: center middle;
        margin: 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", _("Cancel")),
        ("ctrl+s", "submit", _("Add")),
    ]

    def __init__(
        self,
        session: AsyncSessionManager,
        dashboard: Any,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize quick add torrent screen.

        Args:
            session: Async session manager
            dashboard: TerminalDashboard instance for callbacks
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.session = session
        self.dashboard = dashboard
        self.torrent_path: str = ""

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the quick add torrent screen."""
        with Container(id="dialog"):
            with Container(id="content"):
                yield Static(_("Quick Add Torrent"), id="title")
                yield Static(_("Enter torrent file path or magnet link:"), id="label")
                yield Input(placeholder=_("Path or magnet://..."), id="torrent-input")
            with Horizontal(id="buttons"):
                yield Button(_("Cancel"), id="cancel", variant="default")
                yield Button(_("Add"), id="submit", variant="primary")

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and focus input."""
        try:
            input_widget = self.query_one("#torrent-input", Input)  # type: ignore[attr-defined]
            input_widget.focus()  # type: ignore[attr-defined]
        except Exception:
            pass

    async def action_cancel(self) -> None:  # pragma: no cover
        """Cancel and close screen."""
        try:
            self.dismiss(None)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error dismissing QuickAddTorrentScreen: %s", e)
            # Fallback: try to close the screen directly
            try:
                if hasattr(self, "app") and self.app:  # type: ignore[attr-defined]
                    await self.app.pop_screen()  # type: ignore[attr-defined]
            except Exception:
                pass

    async def action_submit(self) -> None:  # pragma: no cover
        """Submit and add torrent."""
        try:
            input_widget = self.query_one("#torrent-input", Input)  # type: ignore[attr-defined]
            path = input_widget.value.strip()  # type: ignore[attr-defined]
            
            if not path:
                return
            
            # CRITICAL FIX: Use command executor for daemon compatibility
            # Check if dashboard has command executor (daemon mode) or use session directly (local mode)
            if hasattr(self.dashboard, "_command_executor") and self.dashboard._command_executor:
                # Daemon mode: use command executor
                try:
                    result = await self.dashboard._command_executor.execute_command(
                        "torrent.add",
                        path_or_magnet=path,
                        output_dir=None,
                        resume=False,
                    )
                    if result and result.success:
                        info_hash_hex = result.data.get("info_hash", "") if result.data else ""
                        if info_hash_hex:
                            logger.debug("QuickAddTorrentScreen: Torrent added successfully, info_hash: %s", info_hash_hex)
                            # CRITICAL FIX: Dismiss with info_hash and trigger immediate UI refresh
                            try:
                                self.dismiss(info_hash_hex)  # type: ignore[attr-defined]
                                # Trigger immediate UI refresh after dismiss
                                # The WebSocket event should also trigger refresh, but this ensures it happens
                                if hasattr(self.dashboard, "_schedule_poll"):
                                    self.dashboard._schedule_poll()  # type: ignore[attr-defined]
                                # Also invalidate cache to force refresh
                                if hasattr(self.dashboard, "_data_provider") and self.dashboard._data_provider:
                                    if hasattr(self.dashboard._data_provider, "invalidate_cache"):
                                        self.dashboard._data_provider.invalidate_cache("torrent_list")
                                        self.dashboard._data_provider.invalidate_cache("global_stats")
                            except Exception as dismiss_error:
                                logger.error("Error dismissing QuickAddTorrentScreen: %s", dismiss_error, exc_info=True)
                                # Fallback: try to close the screen directly
                                try:
                                    if hasattr(self, "app") and self.app:  # type: ignore[attr-defined]
                                        await self.app.pop_screen()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                        else:
                            # Show error - no info hash returned
                            from rich.text import Text
                            error_msg = "Error: Torrent added but no info hash returned"
                            try:
                                label = self.query_one("#label", Static)  # type: ignore[attr-defined]
                                label.update(Text(error_msg, style="red"))  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    else:
                        # Show error from executor
                        from rich.text import Text
                        error_msg = f"Error: {result.error if result else 'Failed to add torrent'}"
                        try:
                            label = self.query_one("#label", Static)  # type: ignore[attr-defined]
                            label.update(Text(error_msg, style="red"))  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception as e:
                    # Show error
                    from rich.text import Text
                    error_msg = f"Error: {str(e)}"
                    try:
                        label = self.query_one("#label", Static)  # type: ignore[attr-defined]
                        label.update(Text(error_msg, style="red"))  # type: ignore[attr-defined]
                    except Exception:
                        pass
            else:
                # Local mode: use session directly
                try:
                    info_hash_hex = await self.session.add_torrent(path, resume=False)
                    if info_hash_hex:
                        self.dismiss(info_hash_hex)
                except Exception as e:
                    # Show error
                    from rich.text import Text
                    error_msg = f"Error: {str(e)}"
                    try:
                        label = self.query_one("#label", Static)  # type: ignore[attr-defined]
                        label.update(Text(error_msg, style="red"))  # type: ignore[attr-defined]
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Error in quick add: %s", e)
            # Show error
            from rich.text import Text
            error_msg = f"Error: {str(e)}"
            try:
                label = self.query_one("#label", Static)  # type: ignore[attr-defined]
                label.update(Text(error_msg, style="red"))  # type: ignore[attr-defined]
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses.
        
        CRITICAL FIX: Use call_later to avoid blocking UI thread.
        Button press handlers should return immediately to prevent screen freezes.
        """
        if event.button.id == "cancel":
            # Schedule cancel action asynchronously
            async def cancel_async() -> None:
                try:
                    await self.action_cancel()
                except Exception as e:
                    logger.error("Error in async cancel: %s", e, exc_info=True)
            asyncio.create_task(cancel_async())
        elif event.button.id == "submit":
            # CRITICAL FIX: Schedule async work without blocking
            # Create task immediately to prevent UI freeze
            async def submit_async() -> None:
                try:
                    await self.action_submit()
                except Exception as e:
                    logger.error("Error in async submit: %s", e, exc_info=True)
            # Create task immediately - this returns immediately and doesn't block
            asyncio.create_task(submit_async())


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
        ("escape", "cancel", _("Cancel")),
        ("ctrl+n", "next", _("Next Step")),
        ("ctrl+p", "previous", _("Previous Step")),
        ("ctrl+s", "submit", _("Submit")),
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
                yield Button(_("Cancel"), id="cancel", variant="default")
                yield Button(_("Previous"), id="previous", variant="default")
                yield Button(_("Next"), id="next", variant="primary")

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
            _("Step {current}/{total}: {steps}").format(
                current=self.current_step,
                total=self.total_steps,
                steps=" → ".join(steps),
            )
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
            next_btn.label = _("Submit")  # type: ignore[attr-defined]
        else:
            next_btn.label = _("Next")  # type: ignore[attr-defined]

    async def _show_step1_torrent_input(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 1: Torrent path/magnet input."""
        input_widget = Input(
            placeholder=_("Enter torrent file path or magnet link"),
            value=self.torrent_path,
            id="torrent_input",
        )
        help_widget = Static(  # type: ignore[assignment]
            _(
                "Enter the path to a .torrent file or a magnet link:\n\n"
                "Examples:\n"
                "  /path/to/file.torrent\n"
                "  magnet:?xt=urn:btih:..."
            ),
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
            placeholder=_("Output directory (default: current directory)"),
            value=self.output_dir,
            id="output_dir_input",
        )
        help_widget = Static(  # type: ignore[assignment]
            _(
                "Enter the directory where files should be downloaded:\n\n"
                "Leave empty to use current directory."
            ),
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
                _("No torrent data loaded. Please go back to step 1."),
                id="step3_error",
            )
            content.mount(error_widget)  # type: ignore[attr-defined]
            return

        # Check if torrent has files
        files = self.torrent_data.get("files", [])
        if not files:
            no_files_widget = Static(  # type: ignore[assignment]
                _("This torrent has no files to select."),
                id="step3_no_files",
            )
            content.mount(no_files_widget)  # type: ignore[attr-defined]
            return

        # Create file selection table
        table = DataTable(id="file_selection_table", zebra_stripes=True)
        table.add_columns(_("Select"), _("Priority"), _("Size"), _("File Name"))

        for idx, file_info in enumerate(files):
            selected = "✓" if idx in self.files_selection else " "
            priority = self.file_priorities.get(idx, "normal")
            size = file_info.get("length", 0)
            size_str = (
                f"{size / (1024 * 1024):.2f} MB"
                if size > 1024 * 1024
                else f"{size / 1024:.2f} KB"
            )
            name = file_info.get("path", _("File {number}").format(number=idx))

            table.add_row(selected, priority, size_str, name, key=str(idx))

        help_widget = Static(  # type: ignore[assignment]
            _(
                "Select files to download and set priorities:\n"
                "  Space: Toggle selection\n"
                "  P: Change priority\n"
                "  A: Select all\n"
                "  D: Deselect all"
            ),
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
            placeholder=_("Download limit (KiB/s, 0 = unlimited)"),
            value=str(self.download_limit) if self.download_limit > 0 else "",
            id="download_limit_input",
        )
        up_input = Input(
            placeholder=_("Upload limit (KiB/s, 0 = unlimited)"),
            value=str(self.upload_limit) if self.upload_limit > 0 else "",
            id="upload_limit_input",
        )

        help_widget = Static(  # type: ignore[assignment]
            _("Set rate limits for this torrent:\n\nEnter 0 or leave empty for unlimited."),
            id="step4_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]
        down_label = Static(_("Download Limit (KiB/s):"), id="down_label")  # type: ignore[assignment]
        content.mount(down_label)  # type: ignore[attr-defined]
        content.mount(down_input)  # type: ignore[attr-defined]
        up_label = Static(_("Upload Limit (KiB/s):"), id="up_label")  # type: ignore[assignment]
        content.mount(up_label)  # type: ignore[attr-defined]
        content.mount(up_input)  # type: ignore[attr-defined]
        down_input.focus()

    async def _show_step5_queue_priority(
        self, content: Container
    ) -> None:  # pragma: no cover
        """Show step 5: Queue priority selection."""
        priority_options = [
            (_("Maximum"), "maximum"),
            (_("High"), "high"),
            (_("Normal"), "normal"),
            (_("Low"), "low"),
            (_("Paused"), "paused"),
        ]

        select_widget = Select(
            options=priority_options,
            value=self.queue_priority,
            id="queue_priority_select",
        )

        help_widget = Static(  # type: ignore[assignment]
            _(
                "Select queue priority for this torrent:\n\n"
                "Higher priority torrents will be started first."
            ),
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
            _(
                "Resume from checkpoint if available:\n\n"
                "If enabled, the download will resume from the last checkpoint."
            ),
            id="step6_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined, arg-type]
        resume_label = Static(_("Resume from checkpoint:"), id="resume_label")  # type: ignore[assignment]
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
            _(
                "Xet Protocol Options:\n\n"
                "Xet enables content-defined chunking and deduplication.\n"
                "Useful for reducing storage when downloading similar content."
            ),
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
        enable_xet_label = Static(_("Enable Xet Protocol:"), id="enable_xet_label")  # type: ignore[assignment]
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
        dedup_label = Static(_("Enable Deduplication:"), id="xet_deduplication_label")  # type: ignore[assignment]
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
            _("Enable P2P Content-Addressed Storage:"), id="xet_p2p_cas_label"
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
        compression_label = Static(_("Enable Compression:"), id="xet_compression_label")  # type: ignore[assignment]
        compression_row = Horizontal(  # type: ignore[attr-defined]
            compression_label,
            compression_switch,
        )
        switches_container.mount(compression_row)  # type: ignore[arg-type]

        # Add link to Xet management screen
        xet_help = Static(  # type: ignore[assignment]
            _("\n[dim]Press Ctrl+X in main dashboard to manage Xet settings globally[/dim]"),
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
            _(
                "IPFS Protocol Options:\n\n"
                "IPFS enables content-addressed storage and peer-to-peer content sharing.\n"
                "Content can be accessed via IPFS CID after download."
            ),
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
        enable_ipfs_label = Static(_("Enable IPFS Protocol:"), id="enable_ipfs_label")  # type: ignore[assignment]
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
        pin_label = Static(_("Pin Content in IPFS:"), id="ipfs_pin_label")  # type: ignore[assignment]
        pin_row = Horizontal(  # type: ignore[attr-defined]
            pin_label,
            pin_switch,
        )
        switches_container.mount(pin_row)  # type: ignore[arg-type]

        # Add link to IPFS management screen
        ipfs_help = Static(  # type: ignore[assignment]
            _("\n[dim]Press Ctrl+I in main dashboard to manage IPFS content and peers[/dim]"),
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
            _(
                "Scrape Options:\n\n"
                "Scraping queries tracker statistics (seeders, leechers, completed downloads).\n"
                "Auto-scrape will automatically scrape the tracker when the torrent is added."
            ),
            id="step9_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Auto-scrape switch
        auto_scrape_switch = Switch(
            value=self.auto_scrape,
            id="auto_scrape_switch",
        )
        auto_scrape_label = Static(_("Auto-scrape on Add:"), id="auto_scrape_label")  # type: ignore[assignment]
        auto_scrape_row = Horizontal(
            auto_scrape_label,
            auto_scrape_switch,
        )
        content.mount(auto_scrape_row)  # type: ignore[attr-defined, arg-type]

        # Add link to scrape results screen
        scrape_help = Static(  # type: ignore[assignment]
            _("\n[dim]Press Ctrl+R in main dashboard to view scrape results[/dim]"),
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
            _(
                "uTP (uTorrent Transport Protocol) Options:\n\n"
                "uTP provides reliable, ordered delivery over UDP with delay-based congestion control (BEP 29).\n"
                "Useful for better performance on networks with high latency or packet loss."
            ),
            id="step10_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Enable uTP switch
        enable_utp_switch = Switch(
            value=self.enable_utp,
            id="enable_utp_switch",
        )
        enable_utp_label = Static(_("Enable uTP Transport:"), id="enable_utp_label")  # type: ignore[assignment]
        utp_row = Horizontal(
            enable_utp_label,
            enable_utp_switch,
        )
        content.mount(utp_row)  # type: ignore[attr-defined, arg-type]

        # Add link to uTP management screen
        utp_help = Static(  # type: ignore[assignment]
            _("\n[dim]Press Ctrl+U in main dashboard to configure uTP settings globally[/dim]"),
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
            _(
                "NAT Traversal Options:\n\n"
                "NAT traversal (NAT-PMP/UPnP) automatically maps ports on your router.\n"
                "This allows peers to connect to you directly, improving download speeds."
            ),
            id="step11_help",
        )
        content.mount(help_widget)  # type: ignore[attr-defined]

        # Enable NAT mapping switch
        enable_nat_switch = Switch(
            value=self.enable_nat_mapping,
            id="enable_nat_mapping_switch",
        )
        enable_nat_label = Static(
            _("Enable NAT Port Mapping:"), id="enable_nat_mapping_label"
        )  # type: ignore[assignment]
        nat_row = Horizontal(
            enable_nat_label,
            enable_nat_switch,
        )
        content.mount(nat_row)  # type: ignore[attr-defined, arg-type]

        # Add link to NAT management screen
        nat_help = Static(  # type: ignore[assignment]
            _("\n[dim]Press Ctrl+N in main dashboard to manage NAT settings globally[/dim]"),
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
                self._show_error(_("Please enter a torrent path or magnet link"))
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
                    self._show_error(_("Could not load torrent: {path}").format(path=path))
                    return False
            except Exception as e:
                self._show_error(_("Error loading torrent: {error}").format(error=e))
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
        try:
            # CRITICAL FIX: Validate torrent path before proceeding
            if not self.torrent_path or not self.torrent_path.strip():
                self._show_error(_("Please enter a torrent path or magnet link"))
                return
            
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
            # CRITICAL FIX: Use asyncio.create_task to avoid blocking UI
            import asyncio
            asyncio.create_task(self.dashboard._process_add_torrent(self.torrent_path, options))
        except Exception as e:
            logger.error("Error submitting add torrent form: %s", e, exc_info=True)
            self._show_error(_("Error submitting form: {error}").format(error=str(e)))


class MetadataLoadingScreen(ModalScreen):  # type: ignore[misc]
    """Loading screen shown while fetching metadata for magnet links."""

    DEFAULT_CSS = """
    MetadataLoadingScreen {
        align: center middle;
    }
    #dialog {
        width: 70;
        height: auto;
        min-height: 20;
        border: thick $primary;
        background: $surface;
    }
    #content {
        height: 1fr;
        margin: 1;
        align: center middle;
    }
    #spinner {
        height: 3;
        margin: 1;
        text-align: center;
    }
    #status {
        height: 3;
        margin: 1;
        text-align: center;
    }
    #progress {
        height: 1;
        margin: 1;
    }
    #info-message {
        height: 2;
        margin: 1;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    #skip-message {
        height: 2;
        margin: 1;
        text-align: center;
        text-style: dim;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", _("Cancel")),
    ]

    def __init__(
        self,
        info_hash_hex: str,
        session: AsyncSessionManager,
        dashboard: Any,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize metadata loading screen.

        Args:
            info_hash_hex: Torrent info hash in hex format
            session: Async session manager
            dashboard: TerminalDashboard instance
        """
        super().__init__(*args, **kwargs)
        self.info_hash_hex = info_hash_hex
        self.session = session
        self.dashboard = dashboard
        self._status_widget: Static | None = None
        self._progress_widget: Static | None = None
        self._check_task: Any | None = None
        self._cancelled = False
        self._all_files_selected = True  # Default to selecting all files

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the loading screen."""
        with Container(id="dialog"):
            with Vertical(id="content"):
                yield Static(_("Fetching Metadata..."), id="spinner")
                yield Static(_("Connecting to peers..."), id="status")
                yield Static("", id="progress")
                yield Static(_("Metadata is loading. File selection will appear when available."), id="info-message")
                yield Static(_("You can skip waiting and continue with all files selected."), id="skip-message")
                from textual.widgets import Checkbox
                yield Checkbox(_("Skip waiting and select all files"), id="skip-checkbox", value=False)
                with Horizontal(id="buttons"):
                    yield Button(_("Skip & Continue"), id="skip-button", variant="default")
                    yield Button(_("Wait for Metadata"), id="wait-button", variant="primary")
                    yield Button(_("Cancel"), id="cancel-button", variant="error")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the loading screen and start event-based metadata monitoring."""
        try:
            self._status_widget = self.query_one("#status", Static)  # type: ignore[attr-defined]
            self._progress_widget = self.query_one("#progress", Static)  # type: ignore[attr-defined]
            
            # CRITICAL FIX: Register event callback for METADATA_READY
            # Handle both AsyncSessionManager and DaemonInterfaceAdapter
            if hasattr(self.session, "register_event_callback"):
                from ccbt.daemon.ipc_protocol import EventType
                
                def on_metadata_ready(data: dict[str, Any]) -> None:
                    """Handle metadata ready event."""
                    event_info_hash = data.get("info_hash", "")
                    if event_info_hash == self.info_hash_hex:
                        # CRITICAL FIX: Event callbacks may run in app thread or different thread
                        # Use create_task which works in both cases (Textual handles thread safety)
                        import asyncio
                        asyncio.create_task(self._handle_metadata_ready())
                
                self.session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.METADATA_READY,
                    on_metadata_ready,
                )
            elif hasattr(self.session, "_event_callbacks"):
                # DaemonInterfaceAdapter - register via adapter
                from ccbt.daemon.ipc_protocol import EventType
                
                def on_metadata_ready(data: dict[str, Any]) -> None:
                    """Handle metadata ready event."""
                    event_info_hash = data.get("info_hash", "")
                    if event_info_hash == self.info_hash_hex:
                        # CRITICAL FIX: Event callbacks may run in app thread or different thread
                        # Use create_task which works in both cases (Textual handles thread safety)
                        import asyncio
                        asyncio.create_task(self._handle_metadata_ready())
                
                if EventType.METADATA_READY not in self.session._event_callbacks:  # type: ignore[attr-defined]
                    self.session._event_callbacks[EventType.METADATA_READY] = []  # type: ignore[attr-defined]
                self.session._event_callbacks[EventType.METADATA_READY].append(on_metadata_ready)  # type: ignore[attr-defined]
            
            # Fallback: Use polling with reduced frequency (every 2 seconds instead of 1)
            def schedule_check() -> None:
                """Schedule async check."""
                import asyncio
                asyncio.create_task(self._check_metadata_status())
            
            self._check_task = self.set_interval(2.0, schedule_check)  # type: ignore[attr-defined]
            
            # Also check immediately
            schedule_check()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error mounting metadata loading screen: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount and stop checking."""
        if self._check_task:
            self._check_task.stop()  # type: ignore[attr-defined]
            self._check_task = None

    async def _handle_metadata_ready(self) -> None:  # pragma: no cover
        """Handle metadata ready event - show file selection."""
        if self._cancelled:
            return

        try:
            # Stop polling
            if self._check_task:
                self._check_task.stop()  # type: ignore[attr-defined]
                self._check_task = None
            
            # Update status
            if self._status_widget:
                self._status_widget.update("Metadata loaded! Opening file selection...")
            
            # Dismiss and show file selection
            self.dismiss(True)  # type: ignore[attr-defined]
            await self.dashboard.push_screen(  # type: ignore[attr-defined]
                FileSelectionScreen(
                    self.info_hash_hex,
                    self.session,
                    self.dashboard,
                )
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error handling metadata ready: %s", e)

    async def _check_metadata_status(self) -> None:  # pragma: no cover
        """Check if metadata has been loaded (fallback polling method)."""
        if self._cancelled:
            return

        try:
            # Check torrent status to see if metadata is available
            status = await self.dashboard._data_provider.get_torrent_status(self.info_hash_hex)
            
            if status:
                # Check if we have file list (indicates metadata is loaded)
                files = await self.dashboard._data_provider.get_torrent_files(self.info_hash_hex)
                
                if files and len(files) > 0:
                    # Metadata is loaded - automatically show file selection screen
                    await self._handle_metadata_ready()
                    return
            
            # Update status message
            if self._status_widget:
                peers = status.get("num_peers", 0) if status else 0
                self._status_widget.update(f"Connected to {peers} peer(s), fetching metadata...")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error checking metadata status: %s", e)
            if self._status_widget:
                self._status_widget.update(f"Error: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "skip-button":
            # User wants to skip waiting and continue with all files selected
            if self._check_task:
                self._check_task.stop()  # type: ignore[attr-defined]
            self._cancelled = True
            # Dismiss and indicate all files should be selected
            self.dismiss({"continue": True, "all_files": True, "skip": True})  # type: ignore[attr-defined]
        elif event.button.id == "wait-button":
            # User wants to wait for metadata - do nothing, just keep checking
            if self._status_widget:
                self._status_widget.update("Waiting for metadata... (File selection will appear automatically)")
        elif event.button.id == "cancel-button":
            self._cancelled = True
            if self._check_task:
                self._check_task.stop()  # type: ignore[attr-defined]
            self.dismiss(False)  # type: ignore[attr-defined]

    def action_cancel(self) -> None:  # pragma: no cover
        """Cancel metadata fetching."""
        self._cancelled = True
        self.dismiss(False)  # type: ignore[attr-defined]


class FileSelectionScreen(ModalScreen):  # type: ignore[misc]
    """File selection screen shown after metadata is loaded."""

    DEFAULT_CSS = """
    FileSelectionScreen {
        align: center middle;
    }
    #dialog {
        width: 90;
        height: 80%;
        border: thick $primary;
        background: $surface;
    }
    #title {
        height: 3;
        margin: 1;
        text-align: center;
    }
    #file-table {
        height: 1fr;
        margin: 1;
    }
    #buttons {
        height: 3;
        margin: 1;
        align: center middle;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", _("Cancel")),
        ("ctrl+s", "submit", _("Submit")),
        ("ctrl+a", "select_all", _("Select All")),
        ("ctrl+d", "deselect_all", _("Deselect All")),
    ]

    def __init__(
        self,
        info_hash_hex: str,
        session: AsyncSessionManager,
        dashboard: Any,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize file selection screen.

        Args:
            info_hash_hex: Torrent info hash in hex format
            session: Async session manager
            dashboard: TerminalDashboard instance
        """
        super().__init__(*args, **kwargs)
        self.info_hash_hex = info_hash_hex
        self.session = session
        self.dashboard = dashboard
        self._file_table: DataTable | None = None
        self._selected_files: set[int] = set()

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the file selection screen."""
        with Container(id="dialog"):
            yield Static(_("Select Files to Download"), id="title")
            yield DataTable(id="file-table", zebra_stripes=True)
            with Horizontal(id="buttons"):
                yield Button(_("Select All"), id="select-all-button")
                yield Button(_("Deselect All"), id="deselect-all-button")
                yield Button(_("Submit"), id="submit-button", variant="primary")
                yield Button(_("Cancel"), id="cancel-button", variant="error")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the file selection screen and load files."""
        try:
            self._file_table = self.query_one("#file-table", DataTable)  # type: ignore[attr-defined]
            if self._file_table:
                self._file_table.add_columns(_("Select"), _("Name"), _("Size"), _("Priority"))
                self._file_table.zebra_stripes = True
            
            self.call_later(self._load_files)  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error mounting file selection screen: %s", e)

    async def _load_files(self) -> None:  # pragma: no cover
        """Load files from torrent."""
        if not self._file_table or not self.dashboard._data_provider:
            return

        try:
            files = await self.dashboard._data_provider.get_torrent_files(self.info_hash_hex)
            
            if not files:
                return

            # Clear existing rows
            self._file_table.clear()
            
            # Add files to table
            for file_info in files:
                file_index = file_info.get("index", -1)
                file_name = file_info.get("name", "Unknown")
                file_size = file_info.get("size", 0)
                file_selected = file_info.get("selected", True)
                file_priority = file_info.get("priority", "normal")
                
                # Format size
                if file_size > 1024 * 1024 * 1024:
                    size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
                elif file_size > 1024 * 1024:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                elif file_size > 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size} B"
                
                # Add checkbox for selection
                checkbox = "☑" if file_selected else "☐"
                
                self._file_table.add_row(
                    checkbox,
                    file_name,
                    size_str,
                    file_priority,
                    key=str(file_index),
                )
                
                if file_selected:
                    self._selected_files.add(file_index)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error loading files: %s", e)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        """Handle file row selection (toggle checkbox)."""
        if not self._file_table:
            return

        try:
            row_key = str(event.row_key)
            file_index = int(row_key)
            
            # Toggle selection
            if file_index in self._selected_files:
                self._selected_files.discard(file_index)
                checkbox = "☐"
            else:
                self._selected_files.add(file_index)
                checkbox = "☑"
            
            # Update row
            row = self._file_table.get_row(row_key)  # type: ignore[attr-defined]
            if row:
                row[0] = checkbox  # Update checkbox column
                self._file_table.update_cell(row_key, "Select", checkbox)  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error toggling file selection: %s", e)

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "select-all-button":
            self.action_select_all()
        elif event.button.id == "deselect-all-button":
            self.action_deselect_all()
        elif event.button.id == "submit-button":
            self.action_submit()
        elif event.button.id == "cancel-button":
            self.action_cancel()

    def action_select_all(self) -> None:  # pragma: no cover
        """Select all files."""
        if not self._file_table:
            return
        
        try:
            # Get all file indices from table
            for row_key in self._file_table.rows:  # type: ignore[attr-defined]
                file_index = int(str(row_key))
                self._selected_files.add(file_index)
                self._file_table.update_cell(row_key, "Select", "☑")  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error selecting all files: %s", e)

    def action_deselect_all(self) -> None:  # pragma: no cover
        """Deselect all files."""
        if not self._file_table:
            return
        
        try:
            # Clear selection
            self._selected_files.clear()
            
            # Update all rows
            for row_key in self._file_table.rows:  # type: ignore[attr-defined]
                self._file_table.update_cell(row_key, "Select", "☐")  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error deselecting all files: %s", e)

    async def action_submit(self) -> None:  # pragma: no cover
        """Submit file selection."""
        try:
            # Apply file selection via executor
            if hasattr(self.dashboard, "_command_executor") and self.dashboard._command_executor:
                # First, deselect all files
                try:
                    # Get all files to deselect unselected ones
                    files = await self.dashboard._data_provider.get_torrent_files(self.info_hash_hex)
                    all_indices = [f.get("index", -1) for f in files if f.get("index", -1) >= 0]
                    unselected_indices = [idx for idx in all_indices if idx not in self._selected_files]
                    
                    if unselected_indices:
                        await self.dashboard._command_executor.execute_command(
                            "file.deselect",
                            info_hash=self.info_hash_hex,
                            file_indices=unselected_indices,
                        )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug("Error deselecting files: %s", e)
                
                # Then, select chosen files
                file_indices = list(self._selected_files)
                if file_indices:
                    result = await self.dashboard._command_executor.execute_command(
                        "file.select",
                        info_hash=self.info_hash_hex,
                        file_indices=file_indices,
                    )
                    if not result or not result.success:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning("Failed to set file selection: %s", result.error if result else "Unknown error")
            
            self.dismiss(True)  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Error submitting file selection: %s", e)
            self.dismiss(True)  # type: ignore[attr-defined]

    def action_cancel(self) -> None:  # pragma: no cover
        """Cancel file selection."""
        self.dismiss(False)  # type: ignore[attr-defined]

