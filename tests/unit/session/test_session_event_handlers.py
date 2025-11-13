"""Tests for session event handlers."""

import pytest
import time

from ccbt.models import TorrentCheckpoint


@pytest.mark.asyncio
async def test_on_download_complete_sets_seeding_status(monkeypatch, tmp_path):
    """Test _on_download_complete sets status to seeding."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.info.status = "downloading"

    await session._on_download_complete()

    assert session.info.status == "seeding"


@pytest.mark.asyncio
async def test_on_download_complete_deletes_checkpoint_when_configured(monkeypatch, tmp_path):
    """Test _on_download_complete deletes checkpoint when auto_delete enabled."""
    from ccbt.session.session import AsyncTorrentSession

    checkpoint_deleted = []

    class _CPM:
        async def delete_checkpoint(self, ih):
            checkpoint_deleted.append(ih)

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.checkpoint_manager = _CPM()
    session.config.disk.checkpoint_enabled = True
    session.config.disk.auto_delete_checkpoint_on_complete = True

    await session._on_download_complete()

    assert len(checkpoint_deleted) == 1


@pytest.mark.asyncio
async def test_on_download_complete_calls_callback(monkeypatch, tmp_path):
    """Test _on_download_complete calls on_complete callback."""
    from ccbt.session.session import AsyncTorrentSession

    callback_called = []

    async def _callback():
        callback_called.append(1)

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.on_complete = _callback

    await session._on_download_complete()

    assert len(callback_called) == 1


@pytest.mark.asyncio
async def test_on_download_complete_handles_checkpoint_delete_error(monkeypatch, tmp_path):
    """Test _on_download_complete handles checkpoint delete errors gracefully."""
    from ccbt.session.session import AsyncTorrentSession

    class _CPM:
        async def delete_checkpoint(self, ih):
            raise RuntimeError("delete failed")

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.checkpoint_manager = _CPM()
    session.config.disk.checkpoint_enabled = True
    session.config.disk.auto_delete_checkpoint_on_complete = True

    # Should not raise
    await session._on_download_complete()


@pytest.mark.asyncio
async def test_on_piece_verified_saves_checkpoint_when_configured(monkeypatch, tmp_path):
    """Test _on_piece_verified saves checkpoint when checkpoint_on_piece enabled."""
    from ccbt.session.session import AsyncTorrentSession

    checkpoint_saved = []

    class _CPM:
        async def save_checkpoint(self, cp):
            checkpoint_saved.append(cp)

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
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

    session = AsyncTorrentSession(td, str(tmp_path))
    session.checkpoint_manager = _CPM()
    session.piece_manager = _PM()
    session.config.disk.checkpoint_enabled = True
    session.config.disk.checkpoint_on_piece = True

    await session._on_piece_verified(0)

    assert len(checkpoint_saved) == 1


@pytest.mark.asyncio
async def test_on_piece_verified_handles_save_error(monkeypatch, tmp_path):
    """Test _on_piece_verified handles checkpoint save errors gracefully."""
    from ccbt.session.session import AsyncTorrentSession

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
            raise RuntimeError("save failed")

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()
    session.config.disk.checkpoint_enabled = True
    session.config.disk.checkpoint_on_piece = True

    # Should not raise
    await session._on_piece_verified(0)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_in_session_loads_state(monkeypatch, tmp_path):
    """Test _resume_from_checkpoint loads piece states correctly."""
    from ccbt.session.session import AsyncTorrentSession

    class _PM:
        async def restore_from_checkpoint(self, checkpoint):
            pass

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 2, "piece_length": 16384, "piece_hashes": [b"x" * 20, b"y" * 20], "total_length": 32768},
        "file_info": {"total_length": 32768},
    }

    checkpoint = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="test",
        total_pieces=2,
        piece_length=16384,
        total_length=32768,
        verified_pieces=[0],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()

    # Mock download manager with file_assembler
    class _FA:
        async def verify_existing_pieces(self, checkpoint):
            return {"valid": True}
        
        def get_written_pieces(self):
            return set()

    class _DM:
        def __init__(self):
            self.file_assembler = _FA()

    session.download_manager = _DM()

    await session._resume_from_checkpoint(checkpoint)

