"""Unit tests for the media playback widget."""
# ruff: noqa: INP001, SLF001

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

textual = pytest.importorskip("textual")

from textual.app import App

from ccbt.executor.base import CommandResult
from ccbt.interface.widgets.media_playback_widget import MediaPlaybackWidget

pytestmark = [pytest.mark.unit, pytest.mark.interface]


class _Provider:
    def __init__(self) -> None:
        self.get_media_candidates = AsyncMock(
            return_value=[
                {
                    "index": 0,
                    "name": "clip.mp4",
                    "size": 10,
                    "path": "C:/downloads/clip.mp4",
                    "is_media": True,
                }
            ]
        )
        self.get_media_stream_status = AsyncMock(
            side_effect=[
                None,
                {
                    "stream_id": "stream-1",
                    "info_hash": "a" * 40,
                    "state": "ready",
                    "stream_url": "http://127.0.0.1:9999/stream?token=test",
                    "buffer_progress": 1.0,
                    "file_name": "clip.mp4",
                    "bind_port": 9999,
                    "bytes_served": 128,
                    "client_count": 1,
                    "current_range_start": 0,
                    "current_range_end": 127,
                    "available_bytes": 128,
                    "last_error": None,
                },
            ]
        )

    def get_adapter(self):
        return None


class _App(App[None]):
    def __init__(self, provider: _Provider, executor: AsyncMock) -> None:
        super().__init__()
        self._provider = provider
        self._executor = executor

    def compose(self):  # pragma: no cover
        yield MediaPlaybackWidget(
            "a" * 40,
            self._provider,
            self._executor,
        )


@pytest.mark.asyncio
async def test_media_playback_widget_executes_media_commands() -> None:
    """Widget controls should route through the media executor surface."""
    provider = _Provider()
    executor = AsyncMock()
    executor.execute_command = AsyncMock(
        side_effect=[
            CommandResult(success=True, data={"stream_id": "stream-1"}),
            CommandResult(success=True, data={"method": "vlc"}),
            CommandResult(success=True, data={"stopped": True}),
        ]
    )

    app = _App(provider, executor)
    async with app.run_test():
        widget = app.query_one(MediaPlaybackWidget)
        await widget._start_stream()
        await widget.refresh_media_state()
        await widget._open_in_vlc()
        await widget._stop_stream()

    assert executor.execute_command.await_args_list[0].args[0] == "media.start"
    assert executor.execute_command.await_args_list[1].args[0] == "media.launch_vlc"
    assert executor.execute_command.await_args_list[2].args[0] == "media.stop"
