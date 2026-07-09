"""Tests for best-effort tracker event=stopped on torrent session shutdown."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_stop_sends_stopped_announce_when_tracker_started(tmp_path) -> None:
    """Session stop invokes announce_to_multiple with event=stopped before tracker.stop."""
    td = {
        "name": "t",
        "info_hash": b"x" * 20,
        "announce": "http://tracker.example.com/announce",
        "trackers": ["udp://tracker.example.org:1337/announce"],
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.disk.checkpoint_enabled = False
    session.download_manager.download_complete = True

    session.tracker.session = MagicMock()
    session.tracker.announce_to_multiple = AsyncMock(return_value=[])
    session.tracker.stop = AsyncMock()

    session.piece_manager.stop = AsyncMock()
    session.piece_manager.bytes_downloaded = 100
    session.download_manager.stop = AsyncMock()
    session.download_manager.peer_manager = MagicMock()
    session.download_manager.peer_manager.get_connected_peers.return_value = []

    session._announce_task = asyncio.create_task(asyncio.sleep(10))
    session._status_task = asyncio.create_task(asyncio.sleep(10))

    await session.stop()

    session.tracker.announce_to_multiple.assert_awaited_once()
    kwargs = session.tracker.announce_to_multiple.await_args.kwargs
    assert kwargs.get("event") == "stopped"
    session.tracker.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_skips_stopped_announce_when_trackers_disabled(tmp_path) -> None:
    """No stopped announce when HTTP and UDP trackers are disabled."""
    td = {
        "name": "t",
        "info_hash": b"x" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.disk.checkpoint_enabled = False
    session.download_manager.download_complete = True
    session.config.discovery.enable_http_trackers = False
    session.config.discovery.enable_udp_trackers = False

    session.tracker.session = MagicMock()
    session.tracker.announce_to_multiple = AsyncMock(return_value=[])
    session.tracker.stop = AsyncMock()
    session.piece_manager.stop = AsyncMock()
    session.download_manager.stop = AsyncMock()

    session._announce_task = asyncio.create_task(asyncio.sleep(10))
    session._status_task = asyncio.create_task(asyncio.sleep(10))

    await session.stop()

    session.tracker.announce_to_multiple.assert_not_awaited()
    session.tracker.stop.assert_awaited_once()
