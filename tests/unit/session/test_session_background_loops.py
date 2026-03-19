"""Tests for session background loops."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
async def test_status_loop_emits_structured_stall_marker(monkeypatch):
    """Status loop should emit the richer stall marker when requests are active but peers are unproductive."""
    from ccbt.session.metrics_status import StatusLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "stall-test",
        "info_hash": b"3" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    session.info.status = "downloading"
    session.logger = MagicMock()
    session.download_manager = SimpleNamespace(_download_started=True)
    session.peer_manager = SimpleNamespace(_schedule_pending_resume=MagicMock())
    session.piece_manager = SimpleNamespace(
        peer_availability={"198.51.100.1:6881": object()},
        get_piece_selection_metrics=lambda: {
            "active_block_requests": 4,
            "hash_verification_failures": 2,
        },
    )

    async def mock_get_status():
        return {
            "progress": 0.25,
            "connected_peers": 3,
            "productive_peers": 0,
            "requestable_peers": 1,
            "download_rate": 0.0,
            "upload_rate": 0.0,
        }

    async def fast_sleep(_seconds: float):
        session._stop_event.set()

    session.get_status = mock_get_status
    monkeypatch.setattr("ccbt.session.metrics_status.asyncio.sleep", fast_sleep)

    await StatusLoop(session).run()

    assert any(
        call.args and "STALL_MARKER" in call.args[0]
        for call in session.logger.warning.call_args_list
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_status_loop_emits_no_piece_info_marker(monkeypatch):
    """Status loop should flag payload starvation when peers never advertise availability."""
    from ccbt.session.metrics_status import StatusLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "piece-info-stall",
        "info_hash": b"4" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    session.info.status = "downloading"
    session.logger = MagicMock()
    session.download_manager = SimpleNamespace(_download_started=True)
    session.peer_manager = SimpleNamespace(_schedule_pending_resume=MagicMock())
    session.piece_manager = SimpleNamespace(
        peer_availability={},
        get_piece_selection_metrics=lambda: {
            "active_block_requests": 0,
            "hash_verification_failures": 0,
        },
    )

    async def mock_get_status():
        return {
            "progress": 0.25,
            "connected_peers": 1,
            "productive_peers": 0,
            "requestable_peers": 1,
            "download_rate": 0.0,
            "upload_rate": 0.0,
        }

    async def fast_sleep(_seconds: float):
        session._stop_event.set()

    session.get_status = mock_get_status
    monkeypatch.setattr("ccbt.session.metrics_status.asyncio.sleep", fast_sleep)

    await StatusLoop(session).run()

    assert any(
        call.args and "no piece availability" in call.args[0]
        for call in session.logger.warning.call_args_list
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_status_loop_logs_tracker_resolution_anomaly(monkeypatch):
    """Status loop should surface tracker resolution anomalies once they are observed."""
    from ccbt.session.metrics_status import StatusLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "tracker-anomaly",
        "info_hash": b"6" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    session.info.status = "downloading"
    session.logger = MagicMock()
    session.download_manager = SimpleNamespace(_download_started=True)
    session.peer_manager = SimpleNamespace(_schedule_pending_resume=MagicMock())
    session.piece_manager = SimpleNamespace(
        peer_availability={},
        get_piece_selection_metrics=lambda: {
            "active_block_requests": 0,
            "hash_verification_failures": 0,
        },
    )
    session.tracker = SimpleNamespace(
        get_session_metrics=lambda: {
            "tracker.example.com": {"resolution_anomaly_count": 2}
        }
    )

    async def mock_get_status():
        return {
            "progress": 0.0,
            "connected_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
        }

    async def fast_sleep(_seconds: float):
        session._stop_event.set()

    session.get_status = mock_get_status
    monkeypatch.setattr("ccbt.session.metrics_status.asyncio.sleep", fast_sleep)

    await StatusLoop(session).run()

    assert any(
        call.args and "TRACKER_RESOLUTION_ANOMALY" in call.args[0]
        for call in session.logger.warning.call_args_list
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_session_stop_cancels_metadata_tasks() -> None:
    """Session stop should cancel tracked metadata tasks before shutdown completes."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "stop-test",
        "info_hash": b"5" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }

    session = AsyncTorrentSession(td, ".")
    session.config.disk.checkpoint_enabled = False
    session.lifecycle_controller = SimpleNamespace(on_stop=AsyncMock())
    session.download_manager = SimpleNamespace(
        stop=AsyncMock(),
        download_complete=False,
    )
    session.piece_manager = SimpleNamespace(stop=AsyncMock())
    session.tracker = SimpleNamespace(stop=AsyncMock(), session=None)
    session.pex_manager = None
    session._incoming_queue_task = None
    session._dht_discovery_task = None

    metadata_task = asyncio.create_task(asyncio.sleep(30))
    session.add_metadata_task(metadata_task)

    await session.stop()

    assert metadata_task.cancelled()
    session.lifecycle_controller.on_stop.assert_awaited_once()


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
        # Note: Mock announce() method - loop will use this if announce_to_multiple doesn't exist
        async def announce(self, td, port=None, event=""):
            call_count.append(1)
            raise RuntimeError("announce failed")  # Always fail
        # Ensure announce_to_multiple doesn't exist so loop uses announce() instead

    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",  # Note: Need announce URL for loop to run
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
        "file_info": {"total_length": 0},
    }

    session = AsyncTorrentSession(td, ".")
    session.tracker = _Tracker()
    # Note: _stop_event must NOT be set initially (is_stopped() checks this)
    # Create new event that is NOT set
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.01
    
    # Note: Ensure session.info exists and has proper structure
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
    
    # Note: StatusLoop uses get_status() method on session (async method)
    # Mock get_status to return status dict
    async def mock_get_status():
        return {"progress": 0.5, "peers": 0, "connected_peers": 0, "download_rate": 0.0, "upload_rate": 0.0}
    session.get_status = mock_get_status
    
    # Note: Ensure peer_manager doesn't cause AttributeError
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
async def test_announce_loop_prioritizes_tracker_replacement_peers(monkeypatch):
    """Higher-utility tracker peers from higher-seed-ratio responses should stay ahead of others."""
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
    session.config.network.announce_interval = 0.01
    if not hasattr(session, "info") or session.info is None:
        session.info = TorrentSessionInfo(
            info_hash=b"1" * 20,
            name="test",
            status="downloading",
        )

    low_ratio_peer = SimpleNamespace(ip="9.0.0.1", port=6882, ssl_capable=False)
    high_ratio_peer = SimpleNamespace(ip="1.0.0.1", port=6881, ssl_capable=False)
    high_ratio_response = SimpleNamespace(
        peers=[high_ratio_peer], complete=100, incomplete=0, interval=30
    )
    low_ratio_response = SimpleNamespace(
        peers=[low_ratio_peer], complete=0, incomplete=100, interval=30
    )

    async def announce_to_multiple(self, _td, _urls, port=None, event=""):
        return [high_ratio_response, low_ratio_response]

    session.tracker = type("T", (), {"announce_to_multiple": announce_to_multiple})()
    # Ensure collect_trackers returns a URL so loop reaches announce_to_multiple
    def collect_trackers(self, _td):
        return ["http://tracker.example.com/announce"]

    monkeypatch.setattr(
        AnnounceController,
        "collect_trackers",
        collect_trackers,
    )
    session.get_swarm_recovery_state = AsyncMock(
        return_value={
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
        }
    )

    connected_peer_lists = []

    class _MockPeerConnectionHelper:
        def __init__(self, _session):  # noqa: ARG002
            # keep lightweight helper stub
            pass

        async def connect_peers_to_download(self, peers):
            connected_peer_lists.append(peers)

    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper",
        _MockPeerConnectionHelper,
    )

    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(),
        _download_started=True,
    )

    # Keep this test fast and deterministic in the presence of sleeps.
    original_sleep = asyncio.sleep

    async def fast_sleep(secs):
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", fast_sleep)

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await asyncio.sleep(0.05)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(connected_peer_lists) == 1
    first_batch = connected_peer_lists[0]
    assert first_batch[0]["ip"] == high_ratio_peer.ip
    assert first_batch[1]["ip"] == low_ratio_peer.ip
    assert first_batch[0]["_replacement_priority"] > first_batch[1]["_replacement_priority"]


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

    async def announce_to_multiple(self, _td, _urls, port=None, event=""):
        call_count.append(1)
        return [response_with_peers]

    session.tracker = type("T", (), {"announce_to_multiple": announce_to_multiple})()
    # Ensure collect_trackers returns a URL so the loop reaches announce_to_multiple
    def collect_trackers(self, _td):
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

