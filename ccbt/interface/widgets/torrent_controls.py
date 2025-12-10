"""Torrent controls widget for managing torrents."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable

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
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Button, DataTable, Input, Select, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

from rich.panel import Panel

logger = logging.getLogger(__name__)


class TorrentControlsWidget(Container):  # type: ignore[misc]
    """Torrent controls widget for pause, resume, verify, and other operations."""

    DEFAULT_CSS = """
    TorrentControlsWidget {
        height: 1fr;
        layout: vertical;
        overflow: hidden;
        min-width: 60;
        min-height: 15;
    }
    
    #controls-header {
        height: 3;
        min-height: 3;
        border: solid $primary;
    }
    
    #torrent-selector {
        height: 3;
        min-height: 3;
    }
    
    #controls-content {
        height: 1fr;
        min-height: 12;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    #action-buttons {
        height: auto;
        min-height: 8;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
    }
    
    #rate-limits {
        height: auto;
        min-height: 5;
        border: solid $primary;
    }
    
    #status-message {
        height: 3;
        min-height: 3;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        selected_hash_callback: Callable[[str], None] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent controls widget.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
            selected_hash_callback: Callback when torrent is selected
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._selected_hash_callback = selected_hash_callback
        self._selected_info_hash: str | None = None
        self._torrent_selector: Select | None = None
        self._refresh_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the torrent controls."""
        # Header
        yield Static(_("Torrent Controls"), id="controls-header")

        # Torrent selector
        yield Select([], prompt=_("Select torrent..."), id="torrent-selector")

        # Controls content
        with Container(id="controls-content"):
            # Action buttons grid
            with Container(id="action-buttons"):
                yield Button(_("▶ Resume"), id="resume-btn", variant="success")
                yield Button(_("⏸ Pause"), id="pause-btn", variant="warning")
                yield Button(_("✓ Verify"), id="verify-btn")
                yield Button(_("🔄 Reannounce"), id="reannounce-btn")
                yield Button(_("🗑 Remove"), id="remove-btn", variant="error")
                yield Button(_("📊 Refresh PEX"), id="pex-btn")
                yield Button(_("🔍 Rehash"), id="rehash-btn")
                yield Button(_("📥 Export State"), id="export-btn")

            # Rate limits section
            with Container(id="rate-limits"):
                yield Static(_("Rate Limits (KiB/s)"), id="limits-title")
                with Horizontal():
                    yield Static(_("Download:"), id="down-label")
                    yield Input("0", placeholder="0 = unlimited", id="down-limit-input")
                with Horizontal():
                    yield Static(_("Upload:"), id="up-label")
                    yield Input("0", placeholder="0 = unlimited", id="up-limit-input")
                yield Button(_("Set Limits"), id="set-limits-btn")

            # Status message
            yield Static("", id="status-message")

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrent controls."""
        try:
            logger.info("TorrentControlsWidget.on_mount: Starting mount process")
            # CRITICAL FIX: Re-query selector if not found
            if not self._torrent_selector:
                try:
                    self._torrent_selector = self.query_one("#torrent-selector", Select)  # type: ignore[attr-defined]
                    logger.info("TorrentControlsWidget.on_mount: Found _torrent_selector: %s", self._torrent_selector is not None)
                except Exception as e:
                    logger.error("TorrentControlsWidget.on_mount: Error querying selector: %s", e, exc_info=True)
                    # Try again after a brief delay
                    self.call_after_refresh(lambda: self._retry_selector_query())  # type: ignore[attr-defined]
                    return
            
            # CRITICAL FIX: Verify data provider is available
            if not self._data_provider:
                logger.warning("TorrentControlsWidget.on_mount: Data provider is None")
                return
            
            # CRITICAL FIX: Initial refresh on mount - only if both are available
            if self._torrent_selector and self._data_provider:
                await self._refresh_torrent_list()
            
            # Set up periodic refresh with proper async handling
            import asyncio
            
            def schedule_refresh() -> None:
                """Schedule async refresh (wrapper for set_interval)."""
                try:
                    # CRITICAL FIX: Only schedule if widget is properly initialized
                    if self._torrent_selector and self._data_provider:
                        asyncio.create_task(self._refresh_torrent_list())
                    else:
                        logger.debug("TorrentControlsWidget: Skipping refresh - selector or data provider not available")
                except Exception as e:
                    logger.debug("Error scheduling torrent list refresh: %s", e)
            
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # Only set up refresh task if widget is properly initialized
            if self._torrent_selector and self._data_provider:
                # CRITICAL FIX: Reduced interval from 5.0s to 1.0s for tighter updates
                self._refresh_task = self.set_interval(1.0, schedule_refresh)  # type: ignore[attr-defined]
                logger.debug("TorrentControlsWidget.on_mount: Set up periodic refresh")
        except Exception as e:
            logger.error("Error mounting torrent controls: %s", e, exc_info=True)
    
    def _retry_selector_query(self) -> None:  # pragma: no cover
        """Retry querying the selector after widget is fully mounted."""
        try:
            if not self._torrent_selector:
                self._torrent_selector = self.query_one("#torrent-selector", Select)  # type: ignore[attr-defined]
                logger.info("TorrentControlsWidget: Successfully queried selector on retry")
                # Now set up the refresh task
                if self._torrent_selector and self._data_provider:
                    import asyncio
                    def schedule_refresh() -> None:
                        try:
                            if self._torrent_selector and self._data_provider:
                                asyncio.create_task(self._refresh_torrent_list())
                        except Exception as e:
                            logger.debug("Error scheduling torrent list refresh: %s", e)
                    # CRITICAL FIX: Reduced interval from 5.0s to 1.0s for tighter updates
                    self._refresh_task = self.set_interval(1.0, schedule_refresh)  # type: ignore[attr-defined]
                    # Trigger initial refresh
                    asyncio.create_task(self._refresh_torrent_list())
        except Exception as e:
            logger.error("TorrentControlsWidget: Error retrying selector query: %s", e, exc_info=True)

    async def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount and cleanup."""
        if self._refresh_task:
            try:
                self._refresh_task.stop()  # type: ignore[attr-defined]
            except Exception:
                pass

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

            # Update header
            try:
                header = self.query_one("#controls-header", Static)  # type: ignore[attr-defined]
                header.update(_("Torrent Controls"))
            except Exception:
                pass

            # Update select prompt
            if self._torrent_selector:
                try:
                    self._torrent_selector.prompt = _("Select torrent...")  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Update button labels
            try:
                resume_btn = self.query_one("#resume-btn", Button)  # type: ignore[attr-defined]
                resume_btn.label = _("▶ Resume")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                pause_btn = self.query_one("#pause-btn", Button)  # type: ignore[attr-defined]
                pause_btn.label = _("⏸ Pause")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                verify_btn = self.query_one("#verify-btn", Button)  # type: ignore[attr-defined]
                verify_btn.label = _("✓ Verify")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                reannounce_btn = self.query_one("#reannounce-btn", Button)  # type: ignore[attr-defined]
                reannounce_btn.label = _("🔄 Reannounce")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                remove_btn = self.query_one("#remove-btn", Button)  # type: ignore[attr-defined]
                remove_btn.label = _("🗑 Remove")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                pex_btn = self.query_one("#pex-btn", Button)  # type: ignore[attr-defined]
                pex_btn.label = _("📊 Refresh PEX")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                rehash_btn = self.query_one("#rehash-btn", Button)  # type: ignore[attr-defined]
                rehash_btn.label = _("🔍 Rehash")  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                export_btn = self.query_one("#export-btn", Button)  # type: ignore[attr-defined]
                export_btn.label = _("📥 Export State")  # type: ignore[attr-defined]
            except Exception:
                pass

            # Update rate limits section
            try:
                limits_title = self.query_one("#limits-title", Static)  # type: ignore[attr-defined]
                limits_title.update(_("Rate Limits (KiB/s)"))
            except Exception:
                pass

            try:
                down_label = self.query_one("#down-label", Static)  # type: ignore[attr-defined]
                down_label.update(_("Download:"))
            except Exception:
                pass

            try:
                up_label = self.query_one("#up-label", Static)  # type: ignore[attr-defined]
                up_label.update(_("Upload:"))
            except Exception:
                pass

            try:
                set_limits_btn = self.query_one("#set-limits-btn", Button)  # type: ignore[attr-defined]
                set_limits_btn.label = _("Set Limits")  # type: ignore[attr-defined]
            except Exception:
                pass

        except Exception as e:
            logger.debug("Error refreshing torrent controls translations: %s", e)

    async def _refresh_torrent_list(self) -> None:  # pragma: no cover
        """Refresh the torrent selector list."""
        # CRITICAL FIX: Check if widget is visible and attached before refreshing
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("TorrentControlsWidget: Widget not attached or not visible, skipping refresh")
            return
        
        # CRITICAL FIX: Re-query selector if it's None (may happen if called before on_mount completes)
        if not self._torrent_selector:
            try:
                self._torrent_selector = self.query_one("#torrent-selector", Select)  # type: ignore[attr-defined]
                logger.debug("TorrentControlsWidget: Re-queried _torrent_selector")
            except Exception as e:
                logger.debug("TorrentControlsWidget: Cannot query selector: %s", e)
                # Schedule retry after widget is fully mounted
                self.call_after_refresh(self._retry_selector_query)  # type: ignore[attr-defined]
                return
        
        if not self._torrent_selector or not self._data_provider:
            logger.debug("TorrentControlsWidget: Missing selector or data provider (selector: %s, provider: %s)", 
                        self._torrent_selector is not None, self._data_provider is not None)
            return

        try:
            logger.debug("TorrentControlsWidget: Fetching torrents from data provider...")
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            try:
                torrents = await asyncio.wait_for(
                    self._data_provider.list_torrents(),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("TorrentControlsWidget: List torrents timed out, keeping existing options")
                # Keep existing options, don't update - prevents UI hang
                return
            except Exception as e:
                logger.debug("TorrentControlsWidget: Error fetching torrent list (will retry next cycle): %s", e)
                # Keep existing options, don't update
                return
            
            logger.debug("TorrentControlsWidget: Retrieved %d torrents", len(torrents) if torrents else 0)
            
            options: list[tuple[str, str]] = []
            for torrent in torrents:
                info_hash = torrent.get("info_hash", "")
                name = torrent.get("name", info_hash[:8])
                options.append((name, info_hash))

            # CRITICAL FIX: Ensure selector is visible before updating
            if not self._torrent_selector.is_attached or not self._torrent_selector.display:  # type: ignore[attr-defined]
                logger.debug("TorrentControlsWidget: Selector not attached or not visible")
                return

            # Update selector if options changed
            current_value = self._torrent_selector.value if hasattr(self._torrent_selector, "value") else None
            self._torrent_selector.set_options(options)  # type: ignore[attr-defined]
            # Restore selection if still valid
            if current_value and any(opt[1] == current_value for opt in options):
                self._torrent_selector.value = current_value  # type: ignore[attr-defined]
            
            logger.debug("TorrentControlsWidget: Updated selector with %d options", len(options))

        except Exception as e:
            logger.error("Error refreshing torrent list: %s", e, exc_info=True)

    async def on_select_changed(self, event: Select.Changed) -> None:  # pragma: no cover
        """Handle torrent selection change."""
        if event.select.id == "torrent-selector":
            self._selected_info_hash = event.value
            if self._selected_hash_callback and self._selected_info_hash:
                self._selected_hash_callback(self._selected_info_hash)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        # CRITICAL FIX: Ensure widget is still attached and valid before accessing
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("TorrentControlsWidget: Widget not attached or not visible, ignoring button press")
            return
        
        if not self._selected_info_hash:
            try:
                status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]
                if status and status.is_attached:  # type: ignore[attr-defined]
                    status.update("[yellow]Please select a torrent first[/yellow]")
            except Exception:
                pass
            return

        button_id = event.button.id
        status = self.query_one("#status-message", Static)  # type: ignore[attr-defined]

        try:
            if button_id == "resume-btn":
                result = await self._command_executor.execute_command(
                    "torrent.resume",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Torrent resumed[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "pause-btn":
                result = await self._command_executor.execute_command(
                    "torrent.pause",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Torrent paused[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "verify-btn":
                result = await self._command_executor.execute_command(
                    "torrent.rehash",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Verification started[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "reannounce-btn":
                result = await self._command_executor.execute_command(
                    "torrent.force_announce",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Reannounce triggered[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "remove-btn":
                result = await self._command_executor.execute_command(
                    "torrent.remove",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Torrent removed[/green]")
                    self._selected_info_hash = None
                    if self._torrent_selector:
                        self._torrent_selector.value = None  # type: ignore[attr-defined]
                    await self._refresh_torrent_list()
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "pex-btn":
                result = await self._command_executor.execute_command(
                    "torrent.refresh_pex",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]PEX refreshed[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "rehash-btn":
                result = await self._command_executor.execute_command(
                    "torrent.rehash",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]Rehash started[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "export-btn":
                result = await self._command_executor.execute_command(
                    "torrent.export_session_state",
                    info_hash=self._selected_info_hash,
                )
                if result.success:
                    status.update("[green]State exported[/green]")
                else:
                    status.update(f"[red]Failed: {result.error}[/red]")

            elif button_id == "set-limits-btn":
                down_input = self.query_one("#down-limit-input", Input)  # type: ignore[attr-defined]
                up_input = self.query_one("#up-limit-input", Input)  # type: ignore[attr-defined]
                try:
                    down_limit = int(down_input.value or "0")
                    up_limit = int(up_input.value or "0")
                    result = await self._command_executor.execute_command(
                        "torrent.set_rate_limits",
                        info_hash=self._selected_info_hash,
                        download_limit_kib=down_limit,
                        upload_limit_kib=up_limit,
                    )
                    if result.success:
                        status.update(f"[green]Limits set: ↓{down_limit} ↑{up_limit} KiB/s[/green]")
                    else:
                        status.update(f"[red]Failed: {result.error}[/red]")
                except ValueError:
                    status.update("[red]Invalid limit values[/red]")

        except Exception as e:
            logger.debug("Error executing control action: %s", e)
            status.update(f"[red]Error: {e}[/red]")





