"""Tests for session checkpoint operations."""

import asyncio
import pytest

from ccbt.models import TorrentCheckpoint, PieceState


@pytest.mark.asyncio
async def test_save_checkpoint_enriches_announce_and_display_name(monkeypatch):
    """Test _save_checkpoint enriches checkpoint with announce URLs and display name."""
    from ccbt.session.session import AsyncTorrentSession

    checkpoint_saved = []

    class _CPM:
        async def save_checkpoint(self, cp):
            checkpoint_saved.append(cp)

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
            import time
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name=name,
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=time.time(),
                updated_at=time.time(),
                output_dir=path,
            )
            return cp

    class _DM:
        def __init__(self):
            self.piece_manager = _PM()

    td = {
        "name": "test-torrent",
        "info_hash": b"1" * 20,
        "announce": "http://tracker1.example.com:8080/announce",
        "announce_list": [
            ["http://tracker2.example.com/announce"],
            ["http://tracker3.example.com/announce"],
        ],
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {
            "total_length": 16384,
        },
    }

    session = AsyncTorrentSession(td, ".")
    session.checkpoint_manager = _CPM()
    session.download_manager = _DM()
    session.info.name = "test-torrent"

    await session._save_checkpoint()

    assert len(checkpoint_saved) == 1
    cp = checkpoint_saved[0]
    assert len(cp.announce_urls) > 0
    assert cp.display_name == "test-torrent"


@pytest.mark.asyncio
async def test_delete_checkpoint_returns_false_on_error(monkeypatch):
    """Test delete_checkpoint returns False when checkpoint manager raises."""
    from ccbt.session.session import AsyncTorrentSession

    class _CPM:
        async def delete_checkpoint(self, ih):
            raise RuntimeError("delete failed")

    td = {
        "name": "t",
        "info_hash": b"2" * 20,
        "pieces_info": {
            "num_pieces": 0,
            "piece_length": 0,
            "piece_hashes": [],
            "total_length": 0,
        },
        "file_info": {
            "total_length": 0,
        },
    }
    session = AsyncTorrentSession(td, ".")
    session.checkpoint_manager = _CPM()

    result = await session.delete_checkpoint()
    assert result is False


@pytest.mark.asyncio
async def test_get_torrent_status_missing_returns_none():
    """Test get_torrent_status returns None for missing torrent."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    status = await mgr.get_torrent_status("aa" * 20)
    assert status is None


@pytest.mark.asyncio
async def test_save_checkpoint_with_torrent_file_path(monkeypatch):
    """Test _save_checkpoint sets torrent_file_path when available."""
    from ccbt.session.session import AsyncTorrentSession

    checkpoint_saved = []

    class _CPM:
        async def save_checkpoint(self, cp):
            checkpoint_saved.append(cp)

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
            import time
            return TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name=name,
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=time.time(),
                updated_at=time.time(),
                output_dir=path,
            )

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, ".")
    session.checkpoint_manager = _CPM()
    session.download_manager = type("_DM", (), {"piece_manager": _PM()})()
    session.torrent_file_path = "/path/to/torrent.torrent"

    await session._save_checkpoint()

    assert len(checkpoint_saved) == 1
    assert checkpoint_saved[0].torrent_file_path == "/path/to/torrent.torrent"


@pytest.mark.asyncio
async def test_save_checkpoint_exception_logs(monkeypatch):
    """Test _save_checkpoint logs exception and re-raises."""
    from ccbt.session.session import AsyncTorrentSession

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
            raise RuntimeError("get_checkpoint_state failed")

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.download_manager = type("_DM", (), {"piece_manager": _PM()})()
    
    with pytest.raises(RuntimeError):
        await session._save_checkpoint()

