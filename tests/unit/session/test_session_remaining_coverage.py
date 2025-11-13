"""Tests for remaining uncovered paths in session module."""

import pytest
import time
from pathlib import Path

from ccbt.models import TorrentCheckpoint, CheckpointFormat
from ccbt.storage.checkpoint import CheckpointFileInfo


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_dict_parser_result(monkeypatch, tmp_path):
    """Test resume_from_checkpoint handles dict result from parser (line 1246)."""
    from ccbt.session import session as sess_mod
    from ccbt.session.session import AsyncSessionManager

    class _Parser:
        def parse(self, path):
            return {"info_hash": b"1" * 20, "name": "test"}  # Returns dict

    monkeypatch.setattr(sess_mod, "TorrentParser", lambda: _Parser())

    class _CPM:
        async def load_checkpoint(self, ih):
            return TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=time.time(),
                updated_at=time.time(),
                output_dir=str(tmp_path),
                torrent_file_path=str(tmp_path / "test.torrent"),
            )

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    torrent_file = tmp_path / "test.torrent"
    torrent_file.write_bytes(b"dummy")

    async def _validate(cp):
        return True

    async def _mock_add(path, resume=False):
        return (b"1" * 20).hex()

    mgr = AsyncSessionManager(str(tmp_path))
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)
    monkeypatch.setattr(mgr, "add_torrent", _mock_add)

    cp = await _CPM().load_checkpoint(b"1" * 20)
    await mgr.resume_from_checkpoint(b"1" * 20, cp, str(torrent_file))


@pytest.mark.asyncio
async def test_find_checkpoint_by_name_handles_exception(monkeypatch, tmp_path):
    """Test find_checkpoint_by_name handles exception during load (lines 1310-1316)."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/test"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                raise RuntimeError("load failed")

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    result = await mgr.find_checkpoint_by_name("test")

    assert result is None


@pytest.mark.asyncio
async def test_on_piece_verified_with_pex_manager(monkeypatch, tmp_path):
    """Test _on_piece_verified when pex_manager exists (line 417)."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    class _PEX:
        pass  # Just needs to exist

    session = AsyncTorrentSession(td, str(tmp_path))
    session.pex_manager = _PEX()
    session.config.disk.checkpoint_enabled = False  # Disable checkpoint to test PEX path

    # Should not raise
    await session._on_piece_verified(0)


@pytest.mark.asyncio
async def test_on_download_complete_checkpoint_delete_exception(monkeypatch, tmp_path):
    """Test _on_download_complete handles checkpoint delete exception (lines 403-404)."""
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

    # Should log warning but not raise
    await session._on_download_complete()


@pytest.mark.asyncio
async def test_cleanup_loop_executes(monkeypatch):
    """Test _cleanup_loop executes and cancels cleanly (lines 1095-1096, 1113-1123)."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    mgr._stop_event = type("Event", (), {"is_set": lambda: False})()
    mgr._cleanup_task = None

    # Mock cleanup_completed_checkpoints
    cleanup_called = []

    async def _mock_cleanup():
        cleanup_called.append(1)
        return 0

    mgr.cleanup_completed_checkpoints = _mock_cleanup

    import asyncio
    task = asyncio.create_task(mgr._cleanup_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    mgr._stop_event = type("Event", (), {"is_set": lambda: True})()

    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_metrics_loop_executes(monkeypatch):
    """Test _metrics_loop executes and cancels cleanly (lines 1127-1128, 1137-1138)."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    mgr._stop_event = type("Event", (), {"is_set": lambda: False})()
    mgr._metrics_task = None

    # Mock _emit_global_metrics
    metrics_called = []

    async def _mock_emit(stats):
        metrics_called.append(1)

    mgr._emit_global_metrics = _mock_emit
    mgr._aggregate_torrent_stats = lambda: {}

    import asyncio
    task = asyncio.create_task(mgr._metrics_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    mgr._stop_event = type("Event", (), {"is_set": lambda: True})()

    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_aggregate_torrent_stats_with_torrents(monkeypatch):
    """Test _aggregate_torrent_stats aggregates from multiple torrents (lines 1147-1162)."""
    from ccbt.session.session import AsyncSessionManager

    class _Session:
        def __init__(self, name):
            self.name = name

        @property
        def downloaded_bytes(self):
            return 1000

        @property
        def uploaded_bytes(self):
            return 500

        @property
        def left_bytes(self):
            return 2000

        @property
        def peers(self):
            # len() is called on peers, so return list for count
            return list(range(5))  # 5 peers

        @property
        def download_rate(self):
            return 100.0

        @property
        def upload_rate(self):
            return 50.0

    mgr = AsyncSessionManager(".")
    ih1 = b"1" * 20
    ih2 = b"2" * 20

    async with mgr.lock:
        mgr.torrents[ih1] = _Session("torrent1")
        mgr.torrents[ih2] = _Session("torrent2")

    # _aggregate_torrent_stats accesses torrents directly, not with lock
    # But we need to ensure torrents exist
    stats = mgr._aggregate_torrent_stats()

    assert stats["total_downloaded"] == 2000
    assert stats["total_uploaded"] == 1000
    assert stats["total_left"] == 4000
    assert stats["total_peers"] == 10
    assert stats["total_download_rate"] == 200.0
    assert stats["total_upload_rate"] == 100.0


@pytest.mark.asyncio
async def test_status_loop_with_callback_error(monkeypatch, tmp_path):
    """Test _status_loop handles callback errors (lines 344-353)."""
    from ccbt.session.session import AsyncTorrentSession

    class _DM:
        def get_status(self):
            return {"progress": 0.5}

    async def _failing_callback(status):
        raise RuntimeError("callback failed")

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, str(tmp_path))
    session.download_manager = _DM()
    session.on_status_update = _failing_callback
    import asyncio
    session._stop_event = asyncio.Event()

    task = asyncio.create_task(session._status_loop())
    await asyncio.sleep(0.02)
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not crash despite callback error

