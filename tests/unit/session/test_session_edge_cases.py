"""Tests for session edge cases and error paths."""

import pytest
import time
import asyncio

from ccbt.models import TorrentCheckpoint, TorrentInfo


@pytest.mark.asyncio
async def test_pause_handles_checkpoint_save_error(monkeypatch, tmp_path):
    """Test pause handles checkpoint save errors gracefully."""
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
    session._stop_event = asyncio.Event()
    session._announce_task = None
    session._status_task = None
    session._checkpoint_task = None

    # Mock components
    class _Tracker:
        async def stop(self):
            pass

    class _DM:
        async def stop(self):
            pass

    session.tracker = _Tracker()
    session.download_manager = _DM()

    # Should not raise, should log warning
    await session.pause()
    assert session.info.status == "paused"


@pytest.mark.asyncio
async def test_pause_stops_pex_manager(monkeypatch, tmp_path):
    """Test pause stops pex_manager when present."""
    from ccbt.session.session import AsyncTorrentSession

    pex_stopped = []

    class _PEX:
        async def stop(self):
            pex_stopped.append(1)

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.disk.checkpoint_enabled = False
    session._stop_event = asyncio.Event()
    session._announce_task = None
    session._status_task = None
    session._checkpoint_task = None
    session.pex_manager = _PEX()

    class _Tracker:
        async def stop(self):
            pass

    class _DM:
        async def stop(self):
            pass

    session.tracker = _Tracker()
    session.download_manager = _DM()

    await session.pause()

    assert len(pex_stopped) == 1


@pytest.mark.asyncio
async def test_resume_propagates_exception(monkeypatch, tmp_path):
    """Test resume propagates exceptions from start."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))

    # Mock start to raise
    async def _failing_start(resume=False):
        raise RuntimeError("start failed")

    session.start = _failing_start

    with pytest.raises(RuntimeError):
        await session.resume()


@pytest.mark.asyncio
async def test_announce_loop_with_torrent_info_model(monkeypatch, tmp_path):
    """Test _announce_loop handles TorrentInfoModel torrent_data."""
    from ccbt.session.session import AsyncTorrentSession
    from ccbt.models import TorrentInfo

    announce_called = []
    announce_data = []

    class _Tracker:
        async def start(self):
            pass

        async def stop(self):
            pass

        async def announce(self, td):
            announce_called.append(1)
            announce_data.append(td)

    # Create TorrentInfo model (not dict)
    class _TorrentInfoModel:
        def __init__(self):
            self.info_hash = b"1" * 20
            self.name = "model-torrent"
            self.announce = "http://tracker.example.com/announce"

    td_model = _TorrentInfoModel()

    session = AsyncTorrentSession({"name": "test", "info_hash": b"1" * 20, "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0}, "file_info": {"total_length": 0}}, str(tmp_path))
    session.torrent_data = td_model  # Set as model
    session.tracker = _Tracker()
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.01

    task = asyncio.create_task(session._announce_loop())
    await asyncio.sleep(0.02)
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have attempted announce with model data
    assert len(announce_called) >= 1 or len(announce_data) >= 1


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_validation_failure(monkeypatch, tmp_path):
    """Test _resume_from_checkpoint handles validation failure."""
    from ccbt.session.session import AsyncTorrentSession

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

    class _PM:
        async def restore_from_checkpoint(self, checkpoint):
            pass

    class _FA:
        def get_written_pieces(self):
            return set()

        async def verify_existing_pieces(self, checkpoint):
            return {
                "valid": False,
                "missing_files": ["file1.txt"],
                "corrupted_pieces": [1],
            }

    class _DM:
        def __init__(self):
            self.file_assembler = _FA()

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()
    session.download_manager = _DM()

    # Should log warnings but not raise
    await session._resume_from_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_missing_files_only(monkeypatch, tmp_path):
    """Test _resume_from_checkpoint handles missing files but valid pieces."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    checkpoint = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="test",
        total_pieces=1,
        piece_length=16384,
        total_length=16384,
        verified_pieces=[0],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    class _PM:
        async def restore_from_checkpoint(self, checkpoint):
            pass

    class _FA:
        def get_written_pieces(self):
            return set()

        async def verify_existing_pieces(self, checkpoint):
            return {
                "valid": False,
                "missing_files": ["file1.txt"],
                # No corrupted_pieces
            }

    class _DM:
        def __init__(self):
            self.file_assembler = _FA()

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()
    session.download_manager = _DM()

    await session._resume_from_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_corrupted_pieces_only(monkeypatch, tmp_path):
    """Test _resume_from_checkpoint handles corrupted pieces but no missing files."""
    from ccbt.session.session import AsyncTorrentSession

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

    class _PM:
        async def restore_from_checkpoint(self, checkpoint):
            pass

    class _FA:
        def get_written_pieces(self):
            return set()

        async def verify_existing_pieces(self, checkpoint):
            return {
                "valid": False,
                # No missing_files
                "corrupted_pieces": [1],
            }

    class _DM:
        def __init__(self):
            self.file_assembler = _FA()

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()
    session.download_manager = _DM()

    await session._resume_from_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_without_file_assembler(monkeypatch, tmp_path):
    """Test _resume_from_checkpoint works when file_assembler is None."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    checkpoint = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="test",
        total_pieces=1,
        piece_length=16384,
        total_length=16384,
        verified_pieces=[0],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    class _PM:
        async def restore_from_checkpoint(self, checkpoint):
            pass

    class _DM:
        def __init__(self):
            self.file_assembler = None  # No file assembler

    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = _PM()
    session.download_manager = _DM()

    # Should work without file_assembler
    await session._resume_from_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_checkpoint_loop_handles_save_error(monkeypatch, tmp_path):
    """Test _checkpoint_loop handles save errors gracefully."""
    from ccbt.session.session import AsyncTorrentSession

    class _CPM:
        async def save_checkpoint(self, cp):
            raise RuntimeError("save failed")

    class _PM:
        async def get_checkpoint_state(self, name, ih, path):
            raise RuntimeError("get state failed")

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.checkpoint_manager = _CPM()
    session.piece_manager = _PM()
    session._stop_event = asyncio.Event()
    session.config.disk.checkpoint_interval = 0.01

    task = asyncio.create_task(session._checkpoint_loop())
    await asyncio.sleep(0.02)
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not crash despite errors

