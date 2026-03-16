"""Unit tests for media stream runtime behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest

from ccbt.models import PieceSelectionStrategy, PieceState
from ccbt.session.media_stream_runtime import MediaStreamRuntime

pytestmark = [pytest.mark.unit, pytest.mark.session]
HTTP_PARTIAL_CONTENT = 206
HTTP_UNAUTHORIZED = 401
TOKEN_ERROR_MESSAGE = "Invalid or expired media stream token"


@pytest.mark.asyncio
async def test_media_stream_runtime_serves_http_ranges(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Runtime should expose a tokenized localhost range endpoint."""
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"abcdefghij")

    strategy = SimpleNamespace(
        streaming_mode=False,
        piece_selection=PieceSelectionStrategy.RAREST_FIRST,
    )
    piece_manager = SimpleNamespace(
        piece_length=4,
        config=SimpleNamespace(strategy=strategy),
        pieces=[
            SimpleNamespace(state=PieceState.VERIFIED),
            SimpleNamespace(state=PieceState.VERIFIED),
            SimpleNamespace(state=PieceState.VERIFIED),
        ],
        handle_streaming_seek=AsyncMock(),
    )
    mapper = SimpleNamespace(
        piece_to_files={
            0: [(0, 0, 4)],
            1: [(0, 4, 4)],
            2: [(0, 8, 2)],
        }
    )
    file_selection_manager = SimpleNamespace(
        mapper=mapper,
        get_pieces_for_file=lambda _file_index: [0, 1, 2],
    )
    emitted_events: list[str] = []

    async def _fake_emit(event) -> None:
        emitted_events.append(event.event_type)

    monkeypatch.setattr(
        "ccbt.session.media_stream_runtime.emit_event",
        _fake_emit,
    )

    runtime = MediaStreamRuntime(
        stream_id="stream-1",
        info_hash_hex="a" * 40,
        file_index=0,
        file_name="clip.mp4",
        file_path=media_file,
        file_size=10,
        file_offset=0,
        bind_host="127.0.0.1",
        requested_port=0,
        token_ttl_seconds=60.0,
        startup_buffer_seconds=1.0,
        request_wait_timeout_seconds=0.5,
        assumed_bitrate_bytes_per_second=4,
        chunk_size=4,
        torrent_session=SimpleNamespace(),
        session_manager=SimpleNamespace(),
        piece_manager=piece_manager,
        file_selection_manager=file_selection_manager,
    )

    await runtime.start()
    assert runtime.stream_url is not None

    async with aiohttp.ClientSession() as session, session.get(
        runtime.stream_url,
        headers={"Range": "bytes=2-5"},
    ) as response:
        assert response.status == HTTP_PARTIAL_CONTENT
        assert response.headers["Content-Range"] == "bytes 2-5/10"
        assert await response.read() == b"cdef"

    await runtime.stop()

    assert "media_stream_started" in emitted_events
    assert "media_stream_ready" in emitted_events
    assert "media_stream_stopped" in emitted_events
    piece_manager.handle_streaming_seek.assert_awaited_once_with(0)
    assert strategy.streaming_mode is False
    assert strategy.piece_selection == PieceSelectionStrategy.RAREST_FIRST


@pytest.mark.asyncio
async def test_media_stream_validate_token_single_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Invalid or expired token returns one message (no information leak)."""
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"x")
    strategy = SimpleNamespace(
        streaming_mode=False,
        piece_selection=PieceSelectionStrategy.RAREST_FIRST,
    )
    piece_manager = SimpleNamespace(
        piece_length=1,
        config=SimpleNamespace(strategy=strategy),
        pieces=[SimpleNamespace(state=PieceState.VERIFIED)],
        handle_streaming_seek=AsyncMock(),
    )
    mapper = SimpleNamespace(
        piece_to_files={0: [(0, 0, 1)]},
        get_pieces_for_file=lambda _: [0],
    )
    monkeypatch.setattr(
        "ccbt.session.media_stream_runtime.emit_event",
        AsyncMock(),
    )
    runtime = MediaStreamRuntime(
        stream_id="s1",
        info_hash_hex="a" * 40,
        file_index=0,
        file_name="clip.mp4",
        file_path=media_file,
        file_size=1,
        file_offset=0,
        bind_host="127.0.0.1",
        requested_port=0,
        token_ttl_seconds=60.0,
        startup_buffer_seconds=0.1,
        request_wait_timeout_seconds=0.1,
        assumed_bitrate_bytes_per_second=1,
        chunk_size=1,
        torrent_session=SimpleNamespace(),
        session_manager=SimpleNamespace(),
        piece_manager=piece_manager,
        file_selection_manager=SimpleNamespace(
            mapper=mapper, get_pieces_for_file=lambda _: [0]
        ),
    )
    await runtime.start()
    base_url = runtime.stream_url.split("?")[0]

    async with aiohttp.ClientSession() as session:
        # Missing token: same message as wrong token (no leak)
        resp = await session.get(base_url)
        assert resp.status == HTTP_UNAUTHORIZED
        assert (await resp.text()) == TOKEN_ERROR_MESSAGE
        # Wrong token: same message
        resp2 = await session.get(f"{base_url}?token=wrong")
        assert resp2.status == HTTP_UNAUTHORIZED
        assert (await resp2.text()) == TOKEN_ERROR_MESSAGE

    await runtime.stop()
