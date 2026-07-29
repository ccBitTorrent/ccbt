"""Info sub-tab screen for Per-Torrent tab.

Displays detailed information about a selected torrent.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from typing import TYPE_CHECKING, Any, ClassVar, Optional

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
    from textual.reactive import reactive
    from textual.widgets import Static, Switch
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        def data_bind(self, **kwargs: Any) -> None:  # type: ignore[no-redef]
            """No-op data_bind when textual is unavailable."""
            pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Switch:  # type: ignore[no-redef]
        pass

    class reactive:  # type: ignore[no-redef]
        """Stub reactive descriptor for textual compatibility."""

        def __init__(self, default: Any = None, *args: Any, **kwargs: Any) -> None:
            self.default = default

        def __class_getitem__(cls, item: Any) -> type:
            return cls

        def __set_name__(self, owner: Any, name: str) -> None:
            self._name = name

        def __get__(self, instance: Any, owner: Any) -> Any:
            if instance is None:
                return self
            return instance.__dict__.get(self._name, self.default)

        def __set__(self, instance: Any, value: Any) -> None:
            instance.__dict__[self._name] = value


from rich.panel import Panel
from rich.table import Table

from ccbt.i18n import _
from ccbt.interface.widgets.piece_availability_bar import PieceAvailabilityHealthBar
from ccbt.interface.widgets.piece_selection_widget import PieceSelectionStrategyWidget

logger = logging.getLogger(__name__)


class TorrentInfoScreen(Container):  # type: ignore[misc]
    """Screen for displaying detailed torrent information."""

    DEFAULT_CSS = """
    TorrentInfoScreen {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
    }
    
    #info-content {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("c", "copy_info_hash", _("Copy Info Hash")),
        ("o", "open_folder", _("Open Folder")),
        ("v", "verify_files", _("Verify Files")),
    ]

    # F2.4.2: reactives bound to TerminalDashboard selected_torrent_* via data_bind.
    selected_torrent_status: reactive = reactive(None, layout=False)  # type: ignore[assignment]
    aggressive_discovery_status: reactive = reactive(None, layout=False)  # type: ignore[assignment]

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        info_hash: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent info screen.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
            info_hash: Torrent info hash in hex format
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._info_hash = info_hash
        self._info_widget: Optional[Static] = None
        self._health_bar: Optional[PieceAvailabilityHealthBar] = None
        self._dht_aggressive_switch: Optional[Switch] = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the info screen."""
        with Vertical(id="info-content"):
            yield PieceAvailabilityHealthBar(id="piece-health-bar")
            with Horizontal(id="dht-controls"):
                yield Static(_("DHT Aggressive Mode:"), id="dht-label")
                yield Switch(id="dht-aggressive-switch")
            yield PieceSelectionStrategyWidget(
                info_hash=self._info_hash,
                data_provider=self._data_provider,
                id="piece-selection-widget",
            )
            yield Static(_("Loading torrent information..."), id="info-display")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the info screen."""
        try:
            self._info_widget = self.query_one("#info-display", Static)  # type: ignore[attr-defined]
            self._health_bar = self.query_one(
                "#piece-health-bar", PieceAvailabilityHealthBar
            )  # type: ignore[attr-defined]
            self._dht_aggressive_switch = self.query_one(
                "#dht-aggressive-switch", Switch
            )  # type: ignore[attr-defined]

            # F2.4.2: bind to the App selected_torrent_status and
            # aggressive_discovery_status reactives (replaces the
            # set_interval(2.0, self.refresh_info) self-poll). piece_health is
            # already bound on the PieceAvailabilityHealthBar widget (F2.1).
            try:
                from ccbt.interface.terminal_dashboard import TerminalDashboard

                self.data_bind(
                    selected_torrent_status=TerminalDashboard.selected_torrent_status,
                    aggressive_discovery_status=TerminalDashboard.aggressive_discovery_status,
                )
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive for non-mounted contexts
                logger.debug("TorrentInfoScreen data_bind skipped: %s", exc)
            # Initial refresh (fallback for contexts where the reactive has not
            # been populated yet; the reactive drives subsequent updates).
            self.call_later(self.refresh_info)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting info screen: %s", e)

    def watch_selected_torrent_status(self, value: Any) -> None:  # pragma: no cover
        """Reactive watcher: render the info table from the bound status (F2.4.2)."""
        if isinstance(value, dict):
            import asyncio as _asyncio

            _asyncio.create_task(self.refresh_info(status_override=value))

    def watch_aggressive_discovery_status(self, value: Any) -> None:  # pragma: no cover
        """Reactive watcher: sync the DHT aggressive switch from the bound status (F2.4.2)."""
        if isinstance(value, dict) and self._dht_aggressive_switch:
            try:
                self._dht_aggressive_switch.value = bool(value.get("enabled", False))  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error syncing DHT aggressive switch: %s", e)

    async def refresh_info(
        self, status_override: Optional[dict[str, Any]] = None
    ) -> None:  # pragma: no cover
        """Refresh info display with latest data.

        Args:
            status_override: When provided (from the selected_torrent_status
                reactive watcher), skip the ``get_torrent_status()`` fetch and
                render from this dict directly.
        """
        if not self._info_widget or not self._data_provider or not self._info_hash:
            return

        try:
            status = (
                status_override
                if status_override is not None
                else await self._data_provider.get_torrent_status(self._info_hash)
            )
            if not status:
                self._info_widget.update(
                    Panel(_("Torrent not found"), title=_("Error"), border_style="red")
                )
                return

            # Create info table
            table = Table(title=_("Torrent Information"), show_header=False, box=None)
            table.add_column(_("Field"), style="cyan", ratio=1)
            table.add_column(_("Value"), style="green", ratio=2)

            # General info
            table.add_row(_("Name"), status.get("name", _("Unknown")))
            table.add_row(_("Info Hash"), self._info_hash)
            table.add_row(_("Status"), str(status.get("status", "unknown")).title())

            # Size info
            total_size = status.get("total_size", 0)
            downloaded = status.get("downloaded", 0)
            uploaded = status.get("uploaded", 0)

            def format_size(size: int) -> str:
                """Format size in bytes."""
                if size >= 1024 * 1024 * 1024:
                    return f"{size / (1024**3):.2f} GB"
                if size >= 1024 * 1024:
                    return f"{size / (1024**2):.2f} MB"
                if size >= 1024:
                    return f"{size / 1024:.2f} KB"
                return f"{size} B"

            table.add_row(_("Total Size"), format_size(total_size))
            table.add_row(_("Downloaded"), format_size(downloaded))
            table.add_row(_("Uploaded"), format_size(uploaded))

            # Progress
            progress = status.get("progress", 0.0)
            table.add_row(_("Progress"), f"{progress * 100:.1f}%")

            # Piece availability health bar (F2.1.3): funnel through the App
            # selected_torrent_piece_health reactive so the health bar self-
            # renders via data_bind. Fall back to a direct push when the App
            # reactive is unavailable (non-mounted/test contexts).
            try:
                piece_health = await self._data_provider.get_piece_health(
                    self._info_hash
                )
                if piece_health:
                    app = getattr(self, "app", None)
                    pushed = False
                    if app is not None and hasattr(
                        app, "selected_torrent_piece_health"
                    ):
                        try:
                            app.selected_torrent_piece_health = piece_health
                            pushed = True
                        except Exception:
                            pushed = False
                    if not pushed and self._health_bar:
                        self._health_bar.update_from_piece_health(piece_health)
            except Exception as e:
                logger.debug("Error getting piece health: %s", e)

            # Speeds
            download_rate = status.get("download_rate", 0.0)
            upload_rate = status.get("upload_rate", 0.0)

            def format_speed(bps: float) -> str:
                """Format bytes per second."""
                if bps >= 1024 * 1024:
                    return f"{bps / (1024 * 1024):.2f} MB/s"
                if bps >= 1024:
                    return f"{bps / 1024:.2f} KB/s"
                return f"{bps:.2f} B/s"

            table.add_row(_("Download Speed"), format_speed(download_rate))
            table.add_row(_("Upload Speed"), format_speed(upload_rate))

            # Peers
            num_peers = status.get("connected_peers", 0)
            num_seeds = status.get("active_peers", 0)
            table.add_row(_("Peers"), str(num_peers))
            table.add_row(_("Seeds"), str(num_seeds))

            # Other info
            is_private = status.get("is_private", False)
            table.add_row(_("Private"), _("Yes") if is_private else _("No"))

            output_dir = status.get("output_dir", "")
            if output_dir:
                table.add_row(_("Output Directory"), output_dir)

            # Update DHT aggressive mode switch state
            try:
                aggressive_status = (
                    await self._data_provider.get_aggressive_discovery_status(
                        self._info_hash,
                    )
                )
                if aggressive_status and self._dht_aggressive_switch:
                    is_enabled = aggressive_status.get("enabled", False)
                    self._dht_aggressive_switch.value = bool(is_enabled)  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error getting DHT aggressive mode status: %s", e)

            # Update display
            self._info_widget.update(
                Panel(table, title=_("Torrent Information"), border_style="blue")
            )
        except Exception as e:
            logger.debug("Error refreshing info: %s", e)
            if self._info_widget:
                self._info_widget.update(
                    Panel(
                        _("Error loading info: {error}").format(error=e),
                        title=_("Error"),
                        border_style="red",
                    )
                )

    async def action_copy_info_hash(self) -> None:  # pragma: no cover
        """Copy info hash to clipboard."""
        if not self._info_hash:
            return

        try:
            # Try to use pyperclip if available
            try:
                import pyperclip

                pyperclip.copy(self._info_hash)
                if hasattr(self, "app"):
                    self.app.notify(
                        _("Info hash copied to clipboard"), severity="success"
                    )  # type: ignore[attr-defined]
                return
            except ImportError:
                pass

            # Fallback: Use platform-specific clipboard commands
            if platform.system() == "Windows":
                try:
                    import subprocess

                    subprocess.run(
                        ["clip"],
                        input=self._info_hash,
                        text=True,
                        check=True,
                    )
                    if hasattr(self, "app"):
                        self.app.notify(
                            _("Info hash copied to clipboard"), severity="success"
                        )  # type: ignore[attr-defined]
                    return
                except Exception:
                    pass
            elif platform.system() == "Darwin":  # macOS
                try:
                    subprocess.run(
                        ["pbcopy"],
                        input=self._info_hash,
                        text=True,
                        check=True,
                    )
                    if hasattr(self, "app"):
                        self.app.notify(
                            _("Info hash copied to clipboard"), severity="success"
                        )  # type: ignore[attr-defined]
                    return
                except Exception:
                    pass
            else:  # Linux
                try:
                    # Try xclip first
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=self._info_hash,
                        text=True,
                        check=True,
                    )
                    if hasattr(self, "app"):
                        self.app.notify(
                            _("Info hash copied to clipboard"), severity="success"
                        )  # type: ignore[attr-defined]
                    return
                except Exception:
                    try:
                        # Fallback to xsel
                        subprocess.run(
                            ["xsel", "--clipboard", "--input"],
                            input=self._info_hash,
                            text=True,
                            check=True,
                        )
                        if hasattr(self, "app"):
                            self.app.notify(
                                _("Info hash copied to clipboard"), severity="success"
                            )  # type: ignore[attr-defined]
                        return
                    except Exception:
                        pass

            # If all clipboard methods fail, show info hash in notification
            if hasattr(self, "app"):
                self.app.notify(  # type: ignore[attr-defined]
                    _("Info hash: {hash}").format(hash=self._info_hash),
                    severity="info",
                    timeout=10.0,  # Increased from 5.0 for better reliability
                )
        except Exception as e:
            logger.debug("Error copying info hash: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Failed to copy info hash: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]

    async def action_open_folder(self) -> None:  # pragma: no cover
        """Open torrent output directory in file manager."""
        if not self._data_provider or not self._info_hash:
            return

        try:
            status = await self._data_provider.get_torrent_status(self._info_hash)
            if not status:
                if hasattr(self, "app"):
                    self.app.notify(_("Torrent not found"), severity="warning")  # type: ignore[attr-defined]
                return

            output_dir = status.get("output_dir", "")
            if not output_dir:
                if hasattr(self, "app"):
                    self.app.notify(
                        _("Output directory not available"), severity="warning"
                    )  # type: ignore[attr-defined]
                return

            # Open folder using OS-specific command
            if platform.system() == "Windows":
                os.startfile(output_dir)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", output_dir], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", output_dir], check=False)

            if hasattr(self, "app"):
                self.app.notify(
                    _("Opened folder: {path}").format(path=output_dir),
                    severity="success",
                )  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error opening folder: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Error opening folder: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]

    async def action_verify_files(self) -> None:  # pragma: no cover
        """Verify torrent file integrity."""
        if not self._command_executor or not self._info_hash:
            return

        try:
            if hasattr(self, "app"):
                self.app.notify(_("Starting file verification..."), severity="info")  # type: ignore[attr-defined]

            result = await self._command_executor.execute_command(
                "file.verify",
                info_hash=self._info_hash,
            )

            if result and hasattr(result, "success") and result.success:
                data = result.data if hasattr(result, "data") else {}
                verified = data.get("verified", 0)
                failed = data.get("failed", 0)
                total = data.get("total", 0)

                if hasattr(self, "app"):
                    if failed == 0:
                        self.app.notify(  # type: ignore[attr-defined]
                            _("All {total} file(s) verified successfully").format(
                                total=total
                            ),
                            severity="success",
                        )
                    else:
                        self.app.notify(  # type: ignore[attr-defined]
                            _(
                                "Verification complete: {verified} verified, {failed} failed out of {total}"
                            ).format(verified=verified, failed=failed, total=total),
                            severity="warning",
                        )
            else:
                error_msg = (
                    result.error
                    if result and hasattr(result, "error")
                    else _("Unknown error")
                )
                if hasattr(self, "app"):
                    self.app.notify(
                        _("Verification failed: {error}").format(error=error_msg),
                        severity="error",
                    )  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error verifying files: %s", e)
            if hasattr(self, "app"):
                self.app.notify(
                    _("Error verifying files: {error}").format(error=str(e)),
                    severity="error",
                )  # type: ignore[attr-defined]

    async def on_switch_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle switch change events."""
        if event.switch.id == "dht-aggressive-switch" and self._dht_aggressive_switch:
            await self._on_dht_aggressive_changed(event.value)  # type: ignore[attr-defined]

    async def _on_dht_aggressive_changed(
        self, enabled: bool
    ) -> None:  # pragma: no cover
        """Handle DHT aggressive mode switch change."""
        if not self._command_executor or not self._info_hash:
            return

        try:
            result = await self._command_executor.execute_command(
                "torrent.set_dht_aggressive_mode",
                info_hash=self._info_hash,
                enabled=enabled,
            )
            if result and hasattr(result, "success") and result.success:
                if hasattr(self, "app"):
                    status_text = _("enabled") if enabled else _("disabled")
                    self.app.notify(  # type: ignore[attr-defined]
                        _("DHT aggressive mode {status}").format(status=status_text),
                        severity="success",
                    )
                return

            error_msg = (
                result.error
                if result and hasattr(result, "error")
                else _("Unknown error")
            )
            if hasattr(self, "app"):
                self.app.notify(  # type: ignore[attr-defined]
                    _("Failed to set DHT aggressive mode: {error}").format(
                        error=error_msg
                    ),
                    severity="error",
                )
            if self._dht_aggressive_switch:
                self._dht_aggressive_switch.value = not enabled  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error setting DHT aggressive mode: %s", e)
            if hasattr(self, "app"):
                self.app.notify(  # type: ignore[attr-defined]
                    _("Error setting DHT aggressive mode: {error}").format(
                        error=str(e)
                    ),
                    severity="error",
                )
            # Revert switch state on error
            if self._dht_aggressive_switch:
                self._dht_aggressive_switch.value = not enabled  # type: ignore[attr-defined]
