"""Tests for piece block metadata updates in download manager callbacks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import PeerInfo
from ccbt.session.download_manager import AsyncDownloadManager


pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.fixture
def torrent_data() -> dict[str, object]:
    """Create minimal torrent metadata for manager initialization."""
    return {
        "info_hash": b"i" * 20,
        "name": "test_torrent",
        "announce": "http://tracker",
        "pieces_info": {
            "piece_length": 16,
            "num_pieces": 1,
            "piece_hashes": [b"h" * 20],
        },
        "file_info": {"total_length": 16},
    }


@pytest.fixture
def download_manager(torrent_data):
    """Create AsyncDownloadManager with mocked piece manager."""
    piece_manager = AsyncMock()
    piece_manager.update_peer_have = AsyncMock()
    piece_manager.handle_piece_block = AsyncMock()

    with patch("ccbt.session.download_manager.get_config", return_value=MagicMock()):
        with patch(
            "ccbt.session.download_manager.AsyncPieceManager", return_value=piece_manager
        ):
            manager = AsyncDownloadManager(torrent_data)
            manager.piece_manager = piece_manager
            yield manager


async def _wait_for_background_tasks(download_manager: AsyncDownloadManager) -> None:
    """Wait for all background tasks spawned by piece callbacks."""
    tasks = list(download_manager._background_tasks)
    if tasks:
        await asyncio.gather(*tasks)


class _PieceMessage:
    piece_index = 0
    begin = 0
    block = b"abcd"


@pytest.mark.asyncio
async def test_on_piece_received_updates_known_peer_metadata(download_manager: AsyncDownloadManager):
    """Piece block updates should resolve explicit peer info into stable peer_key."""
    connection = SimpleNamespace(peer_info=PeerInfo(ip="127.0.0.1", port=6881))
    piece_message = _PieceMessage()

    download_manager._on_piece_received(connection, piece_message)
    await _wait_for_background_tasks(download_manager)

    download_manager.piece_manager.update_peer_have.assert_awaited_once_with(
        "127.0.0.1:6881",
        0,
    )
    download_manager.piece_manager.handle_piece_block.assert_awaited_once_with(
        0,
        0,
        b"abcd",
        peer_key="127.0.0.1:6881",
    )


@pytest.mark.asyncio
async def test_on_piece_received_uses_fallback_for_missing_peer_metadata(
    download_manager: AsyncDownloadManager,
):
    """Missing peer metadata should not block piece handling; fallback to unknown peer key."""
    connection = SimpleNamespace(peer_info=None)
    piece_message = _PieceMessage()

    download_manager._on_piece_received(connection, piece_message)
    await _wait_for_background_tasks(download_manager)

    download_manager.piece_manager.update_peer_have.assert_awaited_once_with(
        "unknown_peer",
        0,
    )
    download_manager.piece_manager.handle_piece_block.assert_awaited_once_with(
        0,
        0,
        b"abcd",
        peer_key=None,
    )


@pytest.mark.asyncio
async def test_on_piece_received_isolation_of_individual_update_failures(
    download_manager: AsyncDownloadManager,
):
    """Failure in peer availability updates should not prevent block handling."""
    download_manager.piece_manager.update_peer_have.side_effect = ValueError("stale")
    download_manager.piece_manager.handle_piece_block = AsyncMock()
    connection = SimpleNamespace(peer_info=PeerInfo(ip="127.0.0.2", port=6999))
    piece_message = _PieceMessage()

    download_manager._on_piece_received(connection, piece_message)
    await _wait_for_background_tasks(download_manager)

    download_manager.piece_manager.update_peer_have.assert_awaited_once_with(
        "127.0.0.2:6999",
        0,
    )
    download_manager.piece_manager.handle_piece_block.assert_awaited_once_with(
        0,
        0,
        b"abcd",
        peer_key="127.0.0.2:6999",
    )
