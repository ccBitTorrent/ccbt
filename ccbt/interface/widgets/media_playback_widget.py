"""Per-torrent media playback control surface for the Textual UI."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Optional

from ccbt.i18n import _

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Button, Select, Static

    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.widgets import Button, Select, Static
    except ImportError:
        ComposeResult = Any  # type: ignore[assignment, misc]
        Container = object  # type: ignore[assignment, misc]
        Horizontal = object  # type: ignore[assignment, misc]
        Vertical = object  # type: ignore[assignment, misc]
        Button = object  # type: ignore[assignment, misc]
        Select = object  # type: ignore[assignment, misc]
        Static = object  # type: ignore[assignment, misc]

    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        CommandExecutor = Any  # type: ignore[assignment, misc]
        DataProvider = Any  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


class MediaPlaybackWidget(Container):  # type: ignore[misc]
    """Embedded Textual control surface for torrent media playback."""

    DEFAULT_CSS = """
    MediaPlaybackWidget {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
        min-height: 16;
    }

    #media-status {
        height: auto;
        border: solid $primary;
        padding: 0 1;
    }

    #media-file-select {
        height: 3;
    }

    #media-actions {
        height: auto;
        layout: horizontal;
    }

    #media-diagnostics {
        height: auto;
        border: solid $secondary;
        padding: 0 1;
    }

    #media-launch-status {
        height: auto;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        info_hash_hex: str,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize widget state for a single torrent."""
        super().__init__(*args, **kwargs)
        self._info_hash_hex = info_hash_hex
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._selected_file_index: Optional[int] = None
        self._media_candidates: list[dict[str, Any]] = []
        self._stream_status: Optional[dict[str, Any]] = None
        self._refresh_task: Optional[Any] = None
        self._refresh_work_task: Optional[Any] = None
        self._adapter: Optional[Any] = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the widget."""
        yield Static(_("Media Playback"), id="media-header")
        yield Static("", id="media-status")
        yield Select([], prompt=_("Select playable file"), id="media-file-select")
        with Horizontal(id="media-actions"):
            yield Button(_("Start Stream"), id="media-start", variant="primary")
            yield Button(_("Open in VLC"), id="media-open", variant="success")
            yield Button(_("Stop Stream"), id="media-stop", variant="warning")
            yield Button(_("Refresh"), id="media-refresh")
        yield Static("", id="media-diagnostics")
        yield Static("", id="media-launch-status")

    async def on_mount(self) -> None:  # type: ignore[override]
        """Initialize refresh hooks."""
        self._adapter = getattr(self._data_provider, "get_adapter", lambda: None)()
        if self._adapter is not None and hasattr(self._adapter, "register_widget"):
            with contextlib.suppress(Exception):
                self._adapter.register_widget(self)

        def schedule_refresh() -> None:
            with contextlib.suppress(Exception):
                if self._refresh_work_task is not None and not self._refresh_work_task.done():
                    self._refresh_work_task.cancel()
                self._refresh_work_task = asyncio.create_task(
                    self.refresh_media_state()
                )

        self._refresh_task = self.set_interval(1.5, schedule_refresh)  # type: ignore[attr-defined]
        await self.refresh_media_state()

    def on_unmount(self) -> None:  # pragma: no cover
        """Clean up event subscriptions and refresh task."""
        if self._refresh_task is not None:
            with contextlib.suppress(Exception):
                self._refresh_task.stop()
        if self._refresh_work_task is not None and not self._refresh_work_task.done():
            with contextlib.suppress(Exception):
                self._refresh_work_task.cancel()
        if self._adapter is not None and hasattr(self._adapter, "unregister_widget"):
            with contextlib.suppress(Exception):
                self._adapter.unregister_widget(self)

    async def refresh_media_state(self) -> None:
        """Refresh file candidates and active stream state."""
        try:
            self._media_candidates = await self._data_provider.get_media_candidates(
                self._info_hash_hex
            )
            if not self._media_candidates:
                self._media_candidates = []
            if self._selected_file_index is None and self._media_candidates:
                self._selected_file_index = int(self._media_candidates[0]["index"])
            self._stream_status = await self._data_provider.get_media_stream_status(
                self._info_hash_hex
            )
            self._update_file_selector()
            self._render_status()
        except Exception as exc:
            logger.debug("Error refreshing media widget: %s", exc)
            self.query_one("#media-status", Static).update(
                _("Failed to refresh media state: {error}").format(error=exc)
            )

    def _update_file_selector(self) -> None:
        """Populate the playable-file selector."""
        selector = self.query_one("#media-file-select", Select)
        if not self._media_candidates:
            selector.set_options([(_("No playable files"), "")])  # type: ignore[attr-defined]
            return

        options: list[tuple[str, int]] = []
        for file_info in self._media_candidates:
            label = f'{file_info.get("name", "Unknown")} ({file_info.get("size", 0)} bytes)'
            options.append((label, int(file_info.get("index", 0))))
        selector.set_options(options)  # type: ignore[attr-defined]
        if self._selected_file_index is not None:
            for _label, value in options:
                if value == self._selected_file_index:
                    with contextlib.suppress(Exception):
                        selector.value = value  # type: ignore[attr-defined]
                    break

    def _render_status(self) -> None:
        """Render the current status and diagnostics panels."""
        status_widget = self.query_one("#media-status", Static)
        diagnostics_widget = self.query_one("#media-diagnostics", Static)

        if not self._media_candidates:
            status_widget.update(
                _("No playable media files were detected for this torrent.")
            )
            diagnostics_widget.update(
                _("Supported MVP playback targets include common audio/video files.")
            )
            return

        if not self._stream_status:
            status_widget.update(
                _("State: stopped\nSelected file index: {index}").format(
                    index=self._selected_file_index
                )
            )
            diagnostics_widget.update(
                _(
                    "Start a stream to expose a localhost HTTP URL for VLC or another "
                    "external player. Native in-terminal video embedding is out of scope."
                )
            )
            return

        status_widget.update(
            _(
                "State: {state}\nURL: {url}\nBuffer readiness: {buffer:.0%}"
            ).format(
                state=self._stream_status.get("state", "unknown"),
                url=self._stream_status.get("stream_url") or _("not ready yet"),
                buffer=float(self._stream_status.get("buffer_progress", 0.0)),
            )
        )
        diagnostics_widget.update(
            _(
                "File: {name}\nPort: {port}\nBytes served: {bytes_served}\n"
                "Clients: {clients}\nLast range: {start} - {end}\n"
                "Readable bytes: {available}\nLast error: {error}"
            ).format(
                name=self._stream_status.get("file_name", _("unknown")),
                port=self._stream_status.get("bind_port", 0),
                bytes_served=self._stream_status.get("bytes_served", 0),
                clients=self._stream_status.get("client_count", 0),
                start=self._stream_status.get("current_range_start", "-"),
                end=self._stream_status.get("current_range_end", "-"),
                available=self._stream_status.get("available_bytes", 0),
                error=self._stream_status.get("last_error") or _("none"),
            )
        )

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle action buttons."""
        button_id = getattr(getattr(event, "button", None), "id", None)
        if button_id == "media-start":
            await self._start_stream()
        elif button_id == "media-open":
            await self._open_in_vlc()
        elif button_id == "media-stop":
            await self._stop_stream()
        elif button_id == "media-refresh":
            await self.refresh_media_state()

    def on_select_changed(self, event: Any) -> None:  # pragma: no cover
        """Track selected playable file."""
        if getattr(getattr(event, "select", None), "id", None) != "media-file-select":
            return
        value = getattr(event, "value", None)
        if isinstance(value, tuple) and len(value) == 2:
            value = value[1]
        elif isinstance(value, int) and 0 <= value < len(self._media_candidates):
            value = self._media_candidates[value].get("index")
        if value in ("", None):
            return
        with contextlib.suppress(TypeError, ValueError):
            self._selected_file_index = int(value)

    async def _start_stream(self) -> None:
        """Start a media stream for the current selection."""
        if self._selected_file_index is None:
            self._set_launch_status(_("Choose a playable file first."))
            return
        result = await self._command_executor.execute_command(
            "media.start",
            info_hash=self._info_hash_hex,
            file_index=self._selected_file_index,
        )
        if hasattr(result, "success") and result.success:
            self._set_launch_status(_("Media stream started."))
            await self.refresh_media_state()
            return
        error = getattr(result, "error", _("Failed to start media stream"))
        self._set_launch_status(str(error))

    async def _open_in_vlc(self) -> None:
        """Launch the local media player against the active stream URL."""
        if not self._stream_status or not self._stream_status.get("stream_url"):
            await self.refresh_media_state()
        stream_url = self._stream_status.get("stream_url") if self._stream_status else None
        if not stream_url:
            self._set_launch_status(_("Start the stream before opening VLC."))
            return
        result = await self._command_executor.execute_command(
            "media.launch_vlc",
            stream_url=stream_url,
        )
        if hasattr(result, "success") and result.success:
            method = getattr(result, "data", {}).get("method", "external_player")
            self._set_launch_status(
                _("Opened stream in external player via {method}.").format(method=method)
            )
            return
        error = getattr(result, "error", _("Failed to launch media player"))
        self._set_launch_status(str(error))

    async def _stop_stream(self) -> None:
        """Stop the active media stream."""
        stream_id = self._stream_status.get("stream_id") if self._stream_status else None
        if not stream_id:
            self._set_launch_status(_("No active stream to stop."))
            return
        result = await self._command_executor.execute_command(
            "media.stop",
            stream_id=stream_id,
        )
        if hasattr(result, "success") and result.success:
            self._set_launch_status(_("Media stream stopped."))
            await self.refresh_media_state()
            return
        error = getattr(result, "error", _("Failed to stop media stream"))
        self._set_launch_status(str(error))

    def on_media_event(self, _event_type: str, event_data: dict[str, Any]) -> None:
        """Handle event-driven media updates from the daemon adapter."""
        if event_data.get("info_hash") != self._info_hash_hex:
            return
        with contextlib.suppress(Exception):
            if self._refresh_work_task is not None and not self._refresh_work_task.done():
                self._refresh_work_task.cancel()
            self._refresh_work_task = asyncio.create_task(self.refresh_media_state())

    def _set_launch_status(self, text: str) -> None:
        """Update the launch-status line."""
        self.query_one("#media-launch-status", Static).update(text)
