"""Regression tests for magnet startup paths."""

from __future__ import annotations

import asyncio
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
async def test_tracker_metadata_exchange_uses_productive_summary_not_raw_active_count() -> None:
    """Non-productive active connections must not suppress standalone tracker metadata fetch."""
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

    loop = AnnounceLoop(session)
    await loop._maybe_trigger_tracker_metadata_exchange(
        [{"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"}],
        active_count=25,
        connection_summary={
            "active_connections": 25,
            "productive_connections": 0,
            "metadata_capable_connections": 0,
            "metadata_exchange_active": 0,
            "peers_with_piece_info": 0,
        },
    )

    session.handle_magnet_metadata_exchange.assert_awaited_once()


@pytest.mark.asyncio
async def test_tracker_metadata_exchange_skips_when_live_exchange_already_active() -> None:
    """Standalone tracker metadata fetch should not duplicate an already-running live exchange."""
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

    loop = AnnounceLoop(session)
    await loop._maybe_trigger_tracker_metadata_exchange(
        [{"ip": "192.0.2.1", "port": 6881, "peer_source": "tracker"}],
        active_count=1,
        connection_summary={
            "active_connections": 1,
            "productive_connections": 1,
            "metadata_capable_connections": 1,
            "metadata_exchange_active": 1,
            "peers_with_piece_info": 0,
        },
    )

    session.handle_magnet_metadata_exchange.assert_not_awaited()


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
async def test_magnet_checkpoint_restore_waits_for_metadata_geometry() -> None:
    """Checkpoint piece states should wait for final metadata before rebuilding layout."""
    torrent_data = {
        "info_hash": b"m" * 20,
        "name": "magnet-checkpoint-test",
        "announce": "http://tracker.example.com/announce",
        "_metadata_incomplete": True,
        "file_info": None,
        "pieces_info": None,
    }

    piece_manager = AsyncPieceManager(torrent_data)
    checkpoint = TorrentCheckpoint(
        info_hash=b"m" * 20,
        torrent_name="magnet-checkpoint-test",
        total_pieces=2,
        piece_length=16384,
        total_length=32768,
        verified_pieces=[0],
        piece_states={0: CheckpointPieceState.VERIFIED},
        download_stats=DownloadStats(bytes_downloaded=16384),
        output_dir=".",
    )

    await piece_manager.restore_from_checkpoint(checkpoint)

    assert piece_manager._deferred_checkpoint is not None
    assert piece_manager.pieces == []

    await piece_manager.update_from_metadata(
        {
            "info_hash": b"m" * 20,
            "name": "magnet-checkpoint-test",
            "announce": "http://tracker.example.com/announce",
            "_metadata_incomplete": False,
            "file_info": {
                "name": "magnet-checkpoint-test",
                "type": "single",
                "total_length": 524288,
            },
            "pieces_info": {
                "num_pieces": 2,
                "piece_length": 262144,
                "piece_hashes": [b"a" * 20, b"b" * 20],
                "total_length": 524288,
            },
        }
    )

    assert piece_manager._deferred_checkpoint is None
    assert piece_manager.pieces[0].length == 262144
    assert piece_manager.pieces[0].state == PieceState.MISSING


@pytest.mark.asyncio
async def test_selector_premarked_piece_still_issues_initial_request(
    monkeypatch,
) -> None:
    """Selector pre-marking must not suppress the first real piece request."""
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
    piece.last_request_time = 0.0
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
    assert piece_manager.pieces[0].last_request_time > 0.0


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


@pytest.mark.asyncio
async def test_piece_stays_requested_when_no_block_requests_are_sent(monkeypatch) -> None:
    """Pieces should remain retryable when peer selection produced no actual block requests."""
    from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState

    torrent_data = {
        "info_hash": b"6" * 20,
        "name": "no-op-request-test",
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
    piece_manager.peer_availability["198.51.100.10:6881"] = SimpleNamespace(pieces={0})

    async def fake_get_peers_for_piece(piece_index: int, _peer_manager: object):
        _ = piece_index, _peer_manager
        return [SimpleNamespace()]

    async def fake_request_blocks_normal(
        piece_index: int,
        missing_blocks: list[object],
        available_peers: list[object],
        _peer_manager: object,
    ) -> int:
        _ = piece_index, missing_blocks, available_peers, _peer_manager
        return 0

    monkeypatch.setattr(piece_manager, "_get_peers_for_piece", fake_get_peers_for_piece)
    monkeypatch.setattr(
        piece_manager,
        "_request_blocks_normal",
        fake_request_blocks_normal,
    )

    await piece_manager.request_piece_from_peers(0, SimpleNamespace(get_active_peers=lambda: []))

    assert piece_manager.pieces[0].state == PieceState.REQUESTED
    assert piece_manager.pieces[0].last_request_time == 0.0


@pytest.mark.asyncio
async def test_handle_peer_choked_requeues_piece_without_inflight_requests() -> None:
    """Choked peers should return inert pieces to a retryable state immediately."""
    from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState

    torrent_data = {
        "info_hash": b"7" * 20,
        "name": "choke-requeue-test",
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
    piece.state = PieceState.DOWNLOADING
    piece.last_request_time = 123.0
    piece.blocks[0].requested_from.add("198.51.100.10:6881")
    piece_manager._requested_pieces_per_peer["198.51.100.10:6881"] = {0}
    piece_manager._active_block_requests[0] = {"198.51.100.10:6881": [(0, 16384, 100.0)]}

    peer = SimpleNamespace(peer_info=SimpleNamespace(ip="198.51.100.10", port=6881))
    await piece_manager.handle_peer_choked(peer)

    assert piece.state == PieceState.MISSING
    assert piece.last_request_time == 0.0
    assert piece.blocks[0].requested_from == set()
    assert "198.51.100.10:6881" not in piece_manager._requested_pieces_per_peer
    assert 0 not in piece_manager._active_block_requests
