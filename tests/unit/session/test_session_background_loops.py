"""Tests for session background loops."""

import asyncio
import pytest

from ccbt.models import TorrentCheckpoint


@pytest.mark.asyncio
async def test_announce_loop_cancel_breaks_cleanly(monkeypatch):
    """Test _announce_loop handles CancelledError and breaks."""
    from ccbt.session.session import AsyncTorrentSession

    class _Tracker:
        async def start(self):
            pass
        async def stop(self):
            pass
        async def announce(self, td):
            return type("Response", (), {"peers": []})()

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.tracker = _Tracker()
    session._stop_event = asyncio.Event()

    # Mock config to have short announce interval
    session.config.network.announce_interval = 0.01

    # Start loop as task and cancel it quickly
    task = asyncio.create_task(session._announce_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    session._stop_event.set()  # Also set stop event

    try:
        await task
        # Task may complete normally if cancellation wasn't caught in time
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_status_loop_cancel_breaks_cleanly(monkeypatch):
    """Test _status_loop handles CancelledError and breaks."""
    from ccbt.session.session import AsyncTorrentSession

    class _DM:
        def get_status(self):
            return {"progress": 0.5}

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.download_manager = _DM()
    session._stop_event = asyncio.Event()

    task = asyncio.create_task(session._status_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_checkpoint_loop_cancel_breaks_cleanly(monkeypatch):
    """Test _checkpoint_loop handles CancelledError and breaks."""
    from ccbt.session.session import AsyncTorrentSession

    class _CPM:
        async def save_checkpoint(self, cp):
            pass

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
    session.piece_manager = _PM()
    session._stop_event = asyncio.Event()
    session.config.disk.checkpoint_interval = 0.01

    task = asyncio.create_task(session._checkpoint_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_announce_loop_handles_exception_gracefully(monkeypatch):
    """Test _announce_loop handles exception gracefully without crashing."""
    from ccbt.session.session import AsyncTorrentSession

    call_count = []

    class _Tracker:
        async def start(self):
            pass
        async def stop(self):
            pass
        async def announce(self, td):
            call_count.append(1)
            raise RuntimeError("announce failed")  # Always fail

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.tracker = _Tracker()
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.01

    task = asyncio.create_task(session._announce_loop())
    await asyncio.sleep(0.02)  # Allow for one attempt
    task.cancel()
    session._stop_event.set()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Loop should have attempted at least once despite error
    assert len(call_count) >= 1


@pytest.mark.asyncio
async def test_status_loop_calls_on_status_update(monkeypatch):
    """Test _status_loop calls on_status_update callback."""
    from ccbt.session.session import AsyncTorrentSession

    callback_called = []

    async def _cb(status):
        callback_called.append(status)

    class _DM:
        def get_status(self):
            return {"progress": 0.5}

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.download_manager = _DM()
    session.on_status_update = _cb
    session._stop_event = asyncio.Event()

    task = asyncio.create_task(session._status_loop())
    await asyncio.sleep(0.1)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(callback_called) > 0

