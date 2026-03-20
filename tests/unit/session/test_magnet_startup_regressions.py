"""Regression tests for magnet startup paths."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ccbt.models import DownloadStats, PieceState as CheckpointPieceState, TorrentCheckpoint
from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_announce_loop_fetches_metadata_when_tracker_connects_stall(
    monkeypatch,
) -> None:
    """Tracker peers should trigger metadata exchange even when connection attempts do not error."""
    from ccbt.session.announce import AnnounceLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 0,
            "piece_length": 0,
            "piece_hashes": [],
            "total_length": 0,
        },
        "file_info": {"total_length": 0},
    }
    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    session.config.network.announce_interval = 0.01
    session.handle_magnet_metadata_exchange = AsyncMock(return_value=True)
    session.download_manager.peer_manager = SimpleNamespace(connections={})

    class _Tracker:
        async def announce_to_multiple(
            self, _td, _urls, port=None, event=""
        ) -> list[SimpleNamespace]:
            _ = port, event
            return [
                SimpleNamespace(
                    peers=[
                        SimpleNamespace(
                            ip="192.0.2.1",
                            port=6881,
                            ssl_capable=None,
                        )
                    ]
                )
            ]

    session.tracker = _Tracker()

    original_sleep = asyncio.sleep

    async def fast_sleep(seconds: float) -> None:
        await original_sleep(min(seconds, 0.01))

    mocked_time = 1000.0

    async def fake_recovery_state() -> dict[str, int | bool]:
        return {
            "metadata_incomplete": True,
            "active_peers": 1,
            "productive_peers": 1,
            "requestable_peers": 1,
            "peers_with_piece_info": 1,
            "handshake_complete_peers": 0,
            "extension_capable_peers": 0,
            "bitfield_complete_peers": 0,
            "metadata_capable_peers": 0,
            "active_block_requests": 0,
            "download_rate": 0.0,
            "has_metadata_progress_path": False,
            "has_usable_download_path": False,
            "degraded_swarm": False,
        }

    def fake_time() -> float:
        return mocked_time

    async def fake_connect_to_peers(
        self: object, peers: list[dict[str, object]]
    ) -> None:
        _ = self, peers

    monkeypatch.setattr(
        "ccbt.session.announce.asyncio.sleep",
        fast_sleep,
    )
    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper.connect_peers_to_download",
        fake_connect_to_peers,
    )

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    for _ in range(30):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count:
            break
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    session.handle_magnet_metadata_exchange.assert_awaited()


@pytest.mark.asyncio
async def test_tracker_metadata_exchange_still_runs_with_low_active_count() -> None:
    """A few active peers should not suppress direct tracker metadata fetch for magnets."""
    from ccbt.session.announce import AnnounceLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "pieces_info": None,
        "file_info": None,
    }
    session = AsyncTorrentSession(td, ".")
    session.handle_magnet_metadata_exchange = AsyncMock(return_value=True)
    session.config.discovery.min_peers_before_dht = 10

    loop = AnnounceLoop(session)
    await loop._maybe_trigger_tracker_metadata_exchange(
        [{"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"}],
        active_count=1,
    )

    session.handle_magnet_metadata_exchange.assert_awaited_once()


@pytest.mark.asyncio
async def test_peer_connection_helper_records_recovery_snapshot(monkeypatch) -> None:
    """Peer connection helper should record peer-count, requestable, and metadata state."""
    from ccbt.session.peers import PeerConnectionHelper
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "recovery-metrics-test",
        "info_hash": b"9" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, ".")
    session.piece_manager._metadata_incomplete = True
    connect_call_count = 0

    async def fake_connect_to_peers(peers):
        nonlocal connect_call_count
        connect_call_count += 1
        _ = peers

    session.download_manager.peer_manager = SimpleNamespace(
        connect_to_peers=AsyncMock(side_effect=fake_connect_to_peers),
        connections={},
        _connection_batches_in_progress=False,
        get_connection_summary=AsyncMock(
            return_value={
                "active_connections": 1,
                "productive_connections": 1,
                "requestable_connections": 2,
                "peers_with_piece_info": 1,
            }
        ),
    )

    helper = PeerConnectionHelper(session)
    original_sleep = asyncio.sleep

    async def fast_sleep(seconds: float) -> None:
        await original_sleep(min(seconds, 0.01))

    monkeypatch.setattr("ccbt.session.peers.asyncio.sleep", fast_sleep)
    await helper.connect_peers_to_download([{"ip": "203.0.113.1", "port": 6881}])

    assert connect_call_count == 1
    last_snapshot = session._peer_discovery_metrics["last_peer_connection_batch"]
    assert last_snapshot["attempted_peers"] == 1
    assert last_snapshot["requestable_connections"] == 2
    assert last_snapshot["metadata_incomplete"] is True
    assert last_snapshot["productive_connections"] == 1


@pytest.mark.asyncio
async def test_tracker_metadata_status_tracks_starvation_seconds() -> None:
    """Metadata status should track starvation duration when swarm is not usable."""
    from ccbt.session.announce import AnnounceLoop
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-starvation-test",
        "info_hash": b"4" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "pieces_info": None,
        "file_info": None,
    }
    session = AsyncTorrentSession(td, ".")
    session.handle_magnet_metadata_exchange = AsyncMock(return_value=False)
    session._peer_discovery_metrics["metadata_starvation_started_at"] = time.time() - 2.0

    loop = AnnounceLoop(session)
    await loop._maybe_trigger_tracker_metadata_exchange(
        [{"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"}],
        connection_summary={
            "active_connections": 0,
            "productive_connections": 0,
            "requestable_connections": 0,
            "metadata_capable_connections": 0,
            "metadata_exchange_active": 0,
            "peers_with_piece_info": 0,
        },
    )

    assert session._peer_discovery_metrics["metadata_starvation_seconds"] >= 1.0


def test_session_peer_source_metrics_use_ingress_and_live_connections() -> None:
    """Peer source metrics should track real ingress counts and live usable peers."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "metric-source-test",
        "info_hash": b"6" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, ".")

    session.record_discovered_peers(
        [
            {"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"},
            {"ip": "192.0.2.2", "port": 6882, "peer_source": "dht"},
            {"ip": "192.0.2.3", "port": 6883, "peer_source": "tracker"},
        ]
    )

    tracker_conn = SimpleNamespace(
        peer_info=SimpleNamespace(peer_source="tracker"),
        peer_state=SimpleNamespace(bitfield=b"\x80", pieces_we_have=set()),
        stats=SimpleNamespace(blocks_delivered=0, bytes_downloaded=0),
        can_request=lambda: True,
    )
    dht_conn = SimpleNamespace(
        peer_info=SimpleNamespace(peer_source="dht"),
        peer_state=SimpleNamespace(bitfield=None, pieces_we_have=set()),
        stats=SimpleNamespace(blocks_delivered=0, bytes_downloaded=0),
        can_request=lambda: False,
    )

    session.update_usable_live_peers_by_source(
        {"tracker-peer": tracker_conn, "dht-peer": dht_conn}
    )

    assert session._peer_discovery_metrics["peers_discovered_by_source"]["tracker"] == 2
    assert session._peer_discovery_metrics["peers_discovered_by_source"]["dht"] == 1
    assert session._peer_discovery_metrics["peers_returned_by_source"]["tracker"] == 2
    assert session._peer_discovery_metrics["peers_returned_by_source"]["dht"] == 1
    assert session._peer_discovery_metrics["usable_live_peers_by_source"]["tracker"] == 1
    assert session._peer_discovery_metrics["usable_live_peers_by_source"]["dht"] == 0
    assert (
        session._peer_discovery_metrics["payload_capable_live_peers_by_source"][
            "tracker"
        ]
        == 1
    )
    assert session._peer_discovery_metrics["usable_peers_formed_by_source"]["tracker"] == 1


@pytest.mark.asyncio
async def test_swarm_recovery_state_uses_live_bitfield_counts_not_event_totals() -> None:
    """Swarm state should use live bitfield-complete connections, not lifetime event counters."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "live-bitfield-metric-test",
        "info_hash": b"7" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, ".")

    peer_manager = SimpleNamespace(
        connections={},
        get_connection_summary=AsyncMock(
            return_value={
                "active_connections": 0,
                "productive_connections": 0,
                "requestable_connections": 0,
                "peers_with_piece_info": 0,
                "handshake_complete_connections": 1,
                "bitfield_complete_connections": 0,
                "metadata_capable_connections": 0,
                "bitfield_received_events": 4,
            }
        ),
    )
    session.download_manager.peer_manager = peer_manager

    state = await session.get_swarm_recovery_state()

    assert state["bitfield_complete_peers"] == 0


@pytest.mark.asyncio
async def test_immediate_tracker_connection_schedules_metadata_fallback(
    monkeypatch,
) -> None:
    """Immediate tracker batches should also schedule standalone metadata fetches for magnets."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "pieces_info": None,
        "file_info": None,
    }
    session = AsyncTorrentSession(td, ".")
    session.handle_magnet_metadata_exchange = AsyncMock(return_value=False)
    session.download_manager.peer_manager = SimpleNamespace(connections={})
    session.piece_manager._metadata_incomplete = True

    async def fake_connect_to_peers(
        self: object, peers: list[dict[str, object]]
    ) -> None:
        _ = self, peers

    original_sleep = asyncio.sleep

    async def fast_sleep(seconds: float) -> None:
        await original_sleep(min(seconds, 0.01))

    monkeypatch.setattr(
        "ccbt.session.session.asyncio.sleep",
        fast_sleep,
    )
    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper.connect_peers_to_download",
        fake_connect_to_peers,
    )

    session._register_immediate_connection_callback()
    callback = session.tracker.on_peers_received
    assert callback is not None

    await callback(
        [{"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"}],
        "udp://tracker.example:1337",
    )
    for _ in range(30):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count:
            break

    session.handle_magnet_metadata_exchange.assert_awaited_once()


@pytest.mark.asyncio
async def test_immediate_tracker_connection_enforces_batch_caps(monkeypatch) -> None:
    """Immediate callback should bound peer batch size by per-torrent capacity."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "cap-test",
        "info_hash": b"2" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": False,
        "pieces_info": {"pieces": b""},
        "file_info": {"total_length": 2048},
    }
    session = AsyncTorrentSession(td, ".")
    session.config.network.max_peers_per_torrent = 4
    session.piece_manager = SimpleNamespace(
        _metadata_incomplete=False,
        num_pieces=1,
        is_downloading=False,
        start_download=AsyncMock(return_value=None),
    )
    session.download_manager.peer_manager = SimpleNamespace(
        connections={"already:1": object(), "already:2": object()},
        _connection_batches_in_progress=False,
    )
    connect_to_download = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper.connect_peers_to_download",
        connect_to_download,
    )

    session._register_immediate_connection_callback()
    callback = session.tracker.on_peers_received
    assert callback is not None

    await callback(
        [
            {
                "ip": f"192.0.2.{i}",
                "port": 6881 + i,
                "peer_source": "tracker-a" if i % 2 == 0 else "tracker-b",
            }
            for i in range(8)
        ],
        "udp://tracker.example.com:6969",
    )
    for _ in range(30):
        await asyncio.sleep(0.01)
        if connect_to_download.await_count:
            break

    # With 2 existing connections and max peers 4, callback should attempt at most 2 peers.
    connect_to_download.assert_awaited_once()
    assert len(connect_to_download.await_args.args[0]) == 2


@pytest.mark.asyncio
async def test_immediate_tracker_connection_enforces_fallback_cooldown(
    monkeypatch,
) -> None:
    """Immediate callback should not retry metadata fallback until cooldown expires."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-cooldown-test",
        "info_hash": b"3" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "pieces_info": None,
        "file_info": None,
    }
    session = AsyncTorrentSession(td, ".")
    session.handle_magnet_metadata_exchange = AsyncMock(return_value=False)
    session.download_manager.peer_manager = SimpleNamespace(connections={})
    session.piece_manager._metadata_incomplete = True

    async def fake_connect_to_peers(
        self: object, peers: list[dict[str, object]]
    ) -> None:
        _ = self, peers

    original_sleep = asyncio.sleep

    async def fast_sleep(seconds: float) -> None:
        await original_sleep(min(seconds, 0.01))

    mocked_time = 1000.0

    async def fake_recovery_state() -> dict[str, int | bool]:
        return {
            "metadata_incomplete": True,
            "active_peers": 1,
            "requestable_peers": 1,
            "productive_peers": 1,
            "peers_with_piece_info": 1,
            "handshake_complete_peers": 0,
            "extension_capable_peers": 0,
            "bitfield_complete_peers": 0,
            "metadata_capable_peers": 0,
            "active_block_requests": 0,
            "download_rate": 0.0,
            "has_metadata_progress_path": False,
            "has_usable_download_path": False,
            "degraded_swarm": False,
        }

    def fake_time() -> float:
        return mocked_time

    monkeypatch.setattr(
        "ccbt.session.session.asyncio.sleep",
        fast_sleep,
    )
    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper.connect_peers_to_download",
        fake_connect_to_peers,
    )
    monkeypatch.setattr(session, "_get_swarm_recovery_state", fake_recovery_state)
    monkeypatch.setattr("time.time", fake_time)

    session._register_immediate_connection_callback()
    callback = session.tracker.on_peers_received
    assert callback is not None

    peers = [{"ip": "192.0.2.10", "port": 6881, "peer_source": "tracker"}]
    tracker_url = "udp://tracker.example:1337"

    await callback(peers, tracker_url)
    for _ in range(40):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count >= 1:
            break
    assert session.handle_magnet_metadata_exchange.await_count == 1

    await callback(peers, tracker_url)
    await original_sleep(0.02)
    assert session.handle_magnet_metadata_exchange.await_count == 1

    mocked_time = 1005.0
    await callback(peers, tracker_url)
    await original_sleep(0.02)
    assert session.handle_magnet_metadata_exchange.await_count == 1

    mocked_time = 1016.0
    await callback(peers, tracker_url)
    for _ in range(40):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count >= 2:
            break
    assert session.handle_magnet_metadata_exchange.await_count == 2


@pytest.mark.asyncio
async def test_immediate_tracker_connection_fallback_clears_in_progress_on_failure(
    monkeypatch,
) -> None:
    """Fallback guard flag must be cleared if the fallback task raises an error."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "magnet-fallback-failure-test",
        "info_hash": b"4" * 20,
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "pieces_info": None,
        "file_info": None,
    }
    session = AsyncTorrentSession(td, ".")
    session.handle_magnet_metadata_exchange = AsyncMock(side_effect=RuntimeError("boom"))
    session.download_manager.peer_manager = SimpleNamespace(connections={})
    session.piece_manager._metadata_incomplete = True

    async def fake_connect_to_peers(
        self: object, peers: list[dict[str, object]]
    ) -> None:
        _ = self, peers

    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds: float) -> None:
        await original_sleep(min(_seconds, 0.01))

    mocked_time = 1000.0

    async def fake_recovery_state() -> dict[str, int | bool]:
        return {
            "metadata_incomplete": True,
            "active_peers": 0,
            "requestable_peers": 0,
            "productive_peers": 0,
            "peers_with_piece_info": 0,
            "handshake_complete_peers": 0,
            "extension_capable_peers": 0,
            "bitfield_complete_peers": 0,
            "metadata_capable_peers": 0,
            "active_block_requests": 0,
            "download_rate": 0.0,
            "has_metadata_progress_path": False,
            "has_usable_download_path": False,
            "degraded_swarm": False,
        }

    def fake_time() -> float:
        return mocked_time

    monkeypatch.setattr(
        "ccbt.session.session.asyncio.sleep",
        fast_sleep,
    )
    monkeypatch.setattr(
        "ccbt.session.peers.PeerConnectionHelper.connect_peers_to_download",
        fake_connect_to_peers,
    )
    monkeypatch.setattr(session, "_get_swarm_recovery_state", fake_recovery_state)
    monkeypatch.setattr("time.time", fake_time)

    session._register_immediate_connection_callback()
    callback = session.tracker.on_peers_received
    assert callback is not None

    peers = [{"ip": "192.0.2.20", "port": 6881, "peer_source": "tracker"}]
    tracker_url = "udp://tracker.example:1337"

    await callback(peers, tracker_url)
    for _ in range(80):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count >= 1:
            break
    assert session.handle_magnet_metadata_exchange.await_count == 1
    assert session._tracker_metadata_fallback_in_progress is False

    mocked_time = 1016.0
    await callback(peers, tracker_url)
    for _ in range(80):
        await original_sleep(0.01)
        if session.handle_magnet_metadata_exchange.await_count >= 2:
            break
    assert session.handle_magnet_metadata_exchange.await_count == 2


@pytest.mark.asyncio
async def test_download_manager_marks_started_flags(monkeypatch) -> None:
    """Normal download manager startup should publish readiness flags for recovery logic."""
    from ccbt.session.download_manager import AsyncDownloadManager

    class FakePieceManager:
        def __init__(self, torrent_dict):
            self.torrent_data = torrent_dict
            self.on_piece_completed = None
            self.on_piece_verified = None
            self.on_download_complete = None

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def start_download(self, peer_manager) -> None:
            _ = peer_manager

    class FakePeerManager:
        def __init__(
            self,
            torrent_data,
            piece_manager,
            our_peer_id,
            max_peers_per_torrent=None,
        ) -> None:
            _ = torrent_data, piece_manager, our_peer_id, max_peers_per_torrent
            self.connections = {}
            self.on_peer_connected = None
            self.on_peer_disconnected = None
            self.on_piece_received = None
            self.on_bitfield_received = None

        def set_security_manager(self, _manager) -> None:
            return None

        def set_is_private(self, _is_private: bool) -> None:
            return None

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def connect_to_peers(self, peers) -> None:
            _ = peers

    monkeypatch.setattr(
        "ccbt.session.download_manager.AsyncPieceManager",
        FakePieceManager,
    )
    monkeypatch.setattr(
        "ccbt.session.download_manager.AsyncPeerConnectionManager",
        FakePeerManager,
    )

    torrent_data = {
        "info_hash": b"1" * 20,
        "name": "flag-test",
        "announce": "http://tracker.example.com/announce",
        "file_info": {"total_length": 16384},
        "pieces_info": {
            "piece_length": 16384,
            "num_pieces": 1,
            "piece_hashes": [b"x" * 20],
        },
    }

    download_manager = AsyncDownloadManager(torrent_data)
    assert download_manager._started is False
    assert download_manager._download_started is False

    await download_manager.start()
    await download_manager.start_download([])

    assert download_manager._started is True
    assert download_manager._download_started is True


def test_new_session_defaults_to_stopped() -> None:
    """Fresh sessions should be stoppable/startable by queue logic."""
    from ccbt.session.session import AsyncTorrentSession

    torrent_data = {
        "info_hash": b"2" * 20,
        "name": "initial-state-test",
        "announce": "http://tracker.example.com/announce",
        "file_info": {"total_length": 0},
        "pieces_info": {
            "piece_length": 0,
            "num_pieces": 0,
            "piece_hashes": [],
        },
    }

    session = AsyncTorrentSession(torrent_data, ".")

    assert session.info.status == "stopped"
    assert session._peer_discovery_metrics["connection_attempts"] == 0
    assert session.discovery_controller is None


@pytest.mark.asyncio
async def test_magnet_bitfield_does_not_promote_incomplete_metadata() -> None:
    """Bitfield parsing may infer an upper bound, but must not start full piece mode before metadata arrives."""
    from ccbt.piece.async_piece_manager import AsyncPieceManager

    torrent_data = {
        "info_hash": b"4" * 20,
        "name": "metadata-incomplete-test",
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "file_info": None,
        "pieces_info": None,
    }

    piece_manager = AsyncPieceManager(torrent_data)

    await piece_manager.update_peer_availability("198.51.100.10:6881", b"\xff\x00")

    assert piece_manager.num_pieces == 0
    assert piece_manager._metadata_incomplete is True
    assert "198.51.100.10:6881" in piece_manager.peer_availability
    assert len(piece_manager.peer_availability["198.51.100.10:6881"].pieces) == 8


@pytest.mark.asyncio
async def test_selector_premarked_piece_still_issues_initial_request(
    monkeypatch,
) -> None:
    """Selector pre-marking must not suppress the first real piece request."""
    import time

    from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState

    torrent_data = {
        "info_hash": b"5" * 20,
        "name": "request-race-test",
        "announce": "http://tracker.example.com/announce",
        "file_info": {"type": "single", "length": 16384, "name": "x", "total_length": 16384},
        "pieces_info": {
            "piece_length": 16384,
            "num_pieces": 1,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
    }

    piece_manager = AsyncPieceManager(torrent_data)
    await piece_manager.update_from_metadata(torrent_data)

    piece = piece_manager.pieces[0]
    piece.state = PieceState.REQUESTED
    piece.request_count = 1
    piece.last_request_time = time.time()
    piece_manager._pending_piece_requests.add(0)
    piece_manager.peer_availability["198.51.100.10:6881"] = SimpleNamespace(
        pieces={0}
    )

    peer_manager = SimpleNamespace(get_active_peers=lambda: [], connections={})
    request_calls: list[tuple[int, int]] = []

    async def fake_get_peers_for_piece(piece_index: int, _peer_manager: object):
        _ = _peer_manager
        return [SimpleNamespace()]

    async def fake_request_blocks_normal(
        piece_index: int,
        missing_blocks: list[object],
        available_peers: list[object],
        _peer_manager: object,
    ) -> int:
        _ = missing_blocks, _peer_manager
        request_calls.append((piece_index, len(available_peers)))
        return 1

    monkeypatch.setattr(piece_manager, "_get_peers_for_piece", fake_get_peers_for_piece)
    monkeypatch.setattr(
        piece_manager,
        "_request_blocks_normal",
        fake_request_blocks_normal,
    )

    await piece_manager.request_piece_from_peers(0, peer_manager)

    assert request_calls == [(0, 1)]
    assert 0 not in piece_manager._pending_piece_requests
    assert piece_manager.pieces[0].state == PieceState.DOWNLOADING


@pytest.mark.asyncio
async def test_emergency_tracker_path_attempts_metadata_exchange() -> None:
    """Emergency peer discovery should still try magnet metadata exchange before raw connects."""
    from ccbt.session.torrent_addition import TorrentAdditionHandler

    tracker_response = SimpleNamespace(
        peers=[SimpleNamespace(ip="192.0.2.10", port=6881)]
    )
    peer_manager = SimpleNamespace(connect_to_peers=AsyncMock())
    session = SimpleNamespace(
        info=SimpleNamespace(name="emergency-magnet", info_hash=b"3" * 20),
        torrent_data={
            "info_hash": b"3" * 20,
            "name": "emergency-magnet",
            "file_info": {"total_length": 0},
        },
        tracker=SimpleNamespace(
            start=AsyncMock(),
            announce=AsyncMock(return_value=tracker_response),
        ),
        config=SimpleNamespace(
            network=SimpleNamespace(listen_port_tcp=6881, listen_port=6881)
        ),
        session_manager=None,
        download_manager=SimpleNamespace(peer_manager=peer_manager),
        handle_magnet_metadata_exchange=AsyncMock(return_value=True),
        is_private=False,
    )
    handler = TorrentAdditionHandler(
        SimpleNamespace(logger=SimpleNamespace(info=lambda *a, **k: None,
                                               warning=lambda *a, **k: None,
                                               debug=lambda *a, **k: None),
                        config=SimpleNamespace())
    )

    await handler._setup_emergency_peer_discovery(session)
    await asyncio.sleep(0.05)

    session.handle_magnet_metadata_exchange.assert_awaited()
    peer_manager.connect_to_peers.assert_awaited()
