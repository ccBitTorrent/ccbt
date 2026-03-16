"""Tests for session background loops."""

import asyncio
import pytest

from ccbt.models import TorrentCheckpoint


@pytest.mark.asyncio
@pytest.mark.timeout_fast
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
@pytest.mark.timeout_fast
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
@pytest.mark.timeout_fast
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
@pytest.mark.timeout_fast
async def test_announce_loop_handles_exception_gracefully(monkeypatch):
    """Test _announce_loop handles exception gracefully without crashing."""
    from ccbt.session.session import AsyncTorrentSession

    call_count = []

    class _Tracker:
        async def start(self):
            pass
        async def stop(self):
            pass
        # CRITICAL FIX: Mock announce() method - loop will use this if announce_to_multiple doesn't exist
        async def announce(self, td, port=None, event=""):
            call_count.append(1)
            raise RuntimeError("announce failed")  # Always fail
        # Ensure announce_to_multiple doesn't exist so loop uses announce() instead

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",  # CRITICAL FIX: Need announce URL for loop to run
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.tracker = _Tracker()
    # CRITICAL FIX: _stop_event must NOT be set initially (is_stopped() checks this)
    # Create new event that is NOT set
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.01
    
    # CRITICAL FIX: Ensure session.info exists and has proper structure
    # The announce loop needs valid session state
    if not hasattr(session, 'info') or session.info is None:
        from ccbt.session.session import TorrentSessionInfo
        session.info = TorrentSessionInfo(
            info_hash=b"1" * 20,
            name="test",
            status="downloading"
        )

    task = asyncio.create_task(session._announce_loop())
    await asyncio.sleep(0.1)  # Allow more time for loop to run and make announce call
    # Now stop the loop
    session._stop_event.set()
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Loop should have attempted at least once despite error
    assert len(call_count) >= 1


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_status_loop_calls_on_status_update(monkeypatch):
    """Test _status_loop calls on_status_update callback."""
    from ccbt.session.session import AsyncTorrentSession

    callback_called = []

    async def _cb(status):
        callback_called.append(status)

    class _DM:
        async def get_status(self):
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
    
    # CRITICAL FIX: StatusLoop uses get_status() method on session (async method)
    # Mock get_status to return status dict
    async def mock_get_status():
        return {"progress": 0.5, "peers": 0, "connected_peers": 0, "download_rate": 0.0, "upload_rate": 0.0}
    session.get_status = mock_get_status
    
    # CRITICAL FIX: Ensure peer_manager doesn't cause AttributeError
    # StatusLoop checks: getattr(self.s.download_manager, "peer_manager", None) or self.s.peer_manager
    # Set it to None to avoid AttributeError
    session.peer_manager = None
    # Also ensure download_manager doesn't have peer_manager
    if hasattr(session.download_manager, 'peer_manager'):
        delattr(session.download_manager, 'peer_manager')

    task = asyncio.create_task(session._status_loop())
    await asyncio.sleep(0.15)  # Allow more time for loop to run
    session._stop_event.set()  # Stop the loop
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(callback_called) > 0


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_announce_loop_stays_alive_when_peers_queued_no_peer_manager(monkeypatch):
    """When tracker returns peers but peer_manager is not ready, loop queues peers and continues (does not exit)."""
    from ccbt.session.announce import AnnounceController, AnnounceLoop
    from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }
    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.05
    if not hasattr(session, "info") or session.info is None:
        session.info = TorrentSessionInfo(
            info_hash=b"1" * 20,
            name="test",
            status="downloading",
        )
    # download_manager exists but peer_manager is missing / None so peers get queued
    session.download_manager = type("DM", (), {})()
    session.download_manager.peer_manager = None
    session.download_manager._download_started = False
    # Tracker returns one response with peers
    peer_obj = type("P", (), {"ip": "192.0.2.1", "port": 6881, "ssl_capable": None})()
    response_with_peers = type("R", (), {"peers": [peer_obj]})()
    call_count = []

    async def announce_to_multiple(_td, _urls, port=None, event=""):
        call_count.append(1)
        return [response_with_peers]

    session.tracker = type("T", (), {"announce_to_multiple": announce_to_multiple})()
    # Ensure collect_trackers returns a URL so the loop reaches announce_to_multiple
    def collect_trackers(_td):
        return ["http://tracker.example.com/announce"]

    monkeypatch.setattr(
        AnnounceController,
        "collect_trackers",
        collect_trackers,
    )
    # Speed up the "wait for peer_manager" retries (4 * 0.5s) so test finishes quickly
    original_sleep = asyncio.sleep
    async def fast_sleep(secs):
        await original_sleep(min(secs, 0.01))
    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", fast_sleep)

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    # Allow time for one full iteration: announce -> get peers -> wait for peer_manager -> queue -> sleep(interval) -> continue
    await asyncio.sleep(0.3)
    # Loop must still be running (not exited) - main regression: loop no longer returns after queuing peers
    assert not task.done(), "Announce loop must stay alive after queuing peers when peer_manager not ready"
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

