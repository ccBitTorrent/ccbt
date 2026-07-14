"""Cold-start connect funnel regression tests."""

from __future__ import annotations

import asyncio
import contextlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.models import EncryptionMode
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
    _connect_batch_process_timeout_s,
    _is_expected_outbound_connect_failure,
)
from ccbt.peer.peer import PeerInfo
from ccbt.utils.exceptions import PeerConnectionError

pytestmark = [pytest.mark.unit, pytest.mark.peer]


def _minimal_peer_manager() -> AsyncPeerConnectionManager:
    torrent_data = {
        "info_hash": b"\xaa" * 20,
        "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": []},
    }
    piece_manager = MagicMock()
    piece_manager._metadata_incomplete = MagicMock(return_value=True)
    piece_manager.num_pieces = 0
    pm = AsyncPeerConnectionManager(
        torrent_data=torrent_data,
        piece_manager=piece_manager,
        max_peers_per_torrent=50,
    )
    pm.config = SimpleNamespace(
        network=SimpleNamespace(
            max_concurrent_connection_attempts=20,
            metadata_phase_plaintext_connect_attempts=1,
            handshake_timeout=5.0,
            connection_timeout=10.0,
            max_peers_per_torrent=50,
            connect_to_peers_parallel_batches=1,
            connection_pool_warmup_enabled=False,
            enable_encryption=True,
            encryption_mode="preferred",
        ),
        discovery=SimpleNamespace(
            tracker_ingress_hold_pending_queue_threshold=1,
        ),
        security=SimpleNamespace(enable_encryption=True, encryption_mode="preferred"),
    )
    pm._running = True
    pm._security_manager = None
    return pm


@pytest.mark.asyncio
async def test_open_tcp_with_semaphore_exists_and_is_callable() -> None:
    pm = _minimal_peer_manager()
    assert hasattr(pm, "_open_tcp_with_semaphore")
    assert callable(pm._open_tcp_with_semaphore)


def test_resolve_outbound_encryption_plaintext_during_metadata_cold_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pm = _minimal_peer_manager()
    monkeypatch.setattr(pm, "_security_enable_encryption_effective", lambda: True)
    monkeypatch.setattr(pm, "_get_configured_encryption_mode", lambda: EncryptionMode.PREFERRED)
    peer = PeerInfo(ip="192.0.2.1", port=6881, peer_source="tracker")
    mode = pm._resolve_outbound_encryption_mode(peer)
    assert mode == EncryptionMode.DISABLED


def test_resolve_outbound_encryption_reverts_after_first_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pm = _minimal_peer_manager()
    pm._metadata_cold_start_handshake_complete = True
    monkeypatch.setattr(pm, "_security_enable_encryption_effective", lambda: True)
    monkeypatch.setattr(pm, "_get_configured_encryption_mode", lambda: EncryptionMode.PREFERRED)
    peer = PeerInfo(ip="192.0.2.1", port=6881, peer_source="tracker")
    mode = pm._resolve_outbound_encryption_mode(peer)
    assert mode == EncryptionMode.PREFERRED


@pytest.mark.asyncio
async def test_resume_pending_batches_overrides_active_batch_when_starving() -> None:
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = [
        PeerInfo(ip=f"192.0.2.{i}", port=6880 + i) for i in range(2, 7)
    ]
    pm._pending_peer_keys = {f"192.0.2.{i}:{6880 + i}" for i in range(2, 7)}
    now = time.monotonic()
    pm._pending_peer_enqueued_at = dict.fromkeys(pm._pending_peer_keys, now)
    pm.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="owner_started")
    )

    await pm._resume_pending_batches("test_starvation_override")

    pm.connect_to_peers.assert_awaited_once()


@pytest.mark.asyncio
async def test_schedule_pending_resume_deferred_while_connect_batch_active() -> None:
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._schedule_pending_resume("overflow")
    assert pm._pending_resume_requested is True
    assert pm._pending_resume_task is None


@pytest.mark.asyncio
async def test_queue_edge_resume_deferred_while_connect_batch_active() -> None:
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = []
    peer = PeerInfo(ip="192.0.2.10", port=6881)
    enqueued = await pm._queue_pending_peers([peer], reason="tracker_immediate_overflow")
    assert enqueued == 1
    assert pm._pending_resume_requested is True
    assert pm._pending_resume_task is None


def test_connect_batch_process_timeout_exceeds_connection_budget() -> None:
    timeout = _connect_batch_process_timeout_s(
        30.0,
        low_peer_recovery_mode=True,
        active_peer_count=0,
        max_batch_duration=45.0,
    )
    assert timeout >= 45.0
    assert timeout > 30.0


@pytest.mark.asyncio
async def test_peer_evaluation_releases_connection_lock_for_connect_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Peer evaluation must not self-deadlock on connection_lock (cold start)."""
    pm = _minimal_peer_manager()
    pm.event_bus = None
    monkeypatch.setattr(
        "ccbt.peer.async_peer_connection.asyncio.sleep",
        AsyncMock(return_value=None),
    )

    eval_task = asyncio.create_task(pm._peer_evaluation_loop())
    try:
        async with asyncio.timeout(2.0):
            async with pm.connection_lock:
                pass
    finally:
        eval_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await eval_task


def test_is_expected_outbound_connect_failure_detects_tcp_timeout() -> None:
    error = PeerConnectionError(
        "Failed to establish TCP connection to 1.2.3.4:6881 after 2 attempt(s): "
        "[Errno 10060] Connect call failed ('1.2.3.4', 6881)"
    )
    assert _is_expected_outbound_connect_failure(error) is True


def test_is_expected_outbound_connect_failure_rejects_handshake_errors() -> None:
    error = PeerConnectionError(
        "Handshake incomplete read during prefix: expected 28 bytes, got 0"
    )
    assert _is_expected_outbound_connect_failure(error) is False


@pytest.mark.asyncio
async def test_recycle_skips_choked_peer_with_bitfield() -> None:
    """Do not recycle the only choked peer that advertised piece availability."""
    pm = _minimal_peer_manager()
    pm.config.network.requestable_deficit_stale_recycle_seconds = 45.0
    pm.config.network.requestable_deficit_post_handshake_grace_seconds = 90.0
    pm.config.network.requestable_deficit_choked_recycle_grace_seconds = 120.0
    peer = PeerInfo(ip="185.98.171.164", port=59977, peer_source="tracker")
    connection = AsyncPeerConnection(peer, pm.torrent_data)
    connection.state = ConnectionState.BITFIELD_SENT
    connection.peer_choking = True
    connection.stats.bytes_downloaded = 0
    connection.stats.blocks_delivered = 0
    connection.connection_start_time = time.time() - 60.0
    connection.stats.last_activity = time.time() - 60.0
    connection.peer_state.bitfield = bytearray(160)
    pm.connections[str(peer)] = connection
    pm._disconnect_peer = AsyncMock()

    await pm._recycle_stagnant_nonrequestable_peers("requestable_peer_deficit")

    pm._disconnect_peer.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_pending_batches_overrides_when_payload_starved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drain pending queue even while a batch owner runs when nobody is requestable."""
    pm = _minimal_peer_manager()
    pm.config.discovery = SimpleNamespace(
        tracker_ingress_hold_pending_queue_threshold=5,
    )
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.0.0.{i}", port=6880 + i) for i in range(1, 12)
    ]
    pm._pending_peer_keys = {f"10.0.0.{i}:{6880 + i}" for i in range(1, 12)}
    monkeypatch.setattr(pm, "_metadata_is_incomplete", lambda: False)
    monkeypatch.setattr(
        pm,
        "_snapshot_connection_counts",
        lambda: (3, 3, 0),
    )
    pm.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="owner_started")
    )

    await pm._resume_pending_batches("payload_starvation")

    pm.connect_to_peers.assert_awaited_once()
    assert pm.connect_to_peers.await_args.kwargs.get("_from_pending_queue") is True
    assert len(pm.connect_to_peers.await_args.args[0]) >= 8


@pytest.mark.asyncio
async def test_recycle_choked_peer_with_bitfield_after_grace() -> None:
    """Recycle remote-choked peers with bitfields after grace so pending queue can drain."""
    pm = _minimal_peer_manager()
    pm.config.network.requestable_deficit_stale_recycle_seconds = 45.0
    pm.config.network.requestable_deficit_post_handshake_grace_seconds = 90.0
    pm.config.network.requestable_deficit_choked_recycle_grace_seconds = 120.0
    peer = PeerInfo(ip="10.0.0.1", port=6881, peer_source="tracker")
    connection = AsyncPeerConnection(peer, pm.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.peer_choking = True
    connection.stats.bytes_downloaded = 0
    connection.connection_start_time = time.time() - 200.0
    connection.stats.last_activity = time.time() - 200.0
    connection.peer_state.bitfield = bytearray(160)
    pm.connections[str(peer)] = connection
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.0.0.{i}", port=6880 + i) for i in range(2, 50)
    ]
    pm._pending_peer_keys = {f"10.0.0.{i}:{6880 + i}" for i in range(2, 50)}
    pm._disconnect_peer = AsyncMock()

    await pm._recycle_stagnant_nonrequestable_peers("requestable_peer_deficit")

    pm._disconnect_peer.assert_awaited_once()


@pytest.mark.asyncio
async def test_recycle_choked_peer_after_partial_delivery_when_requestable_zero() -> None:
    """Recycle a previously productive peer that is now remote-choked and idle."""
    pm = _minimal_peer_manager()
    pm.config.network.requestable_deficit_stale_recycle_seconds = 45.0
    pm.config.network.requestable_deficit_post_handshake_grace_seconds = 90.0
    pm.config.network.requestable_deficit_choked_recycle_grace_seconds = 120.0
    peer = PeerInfo(ip="10.0.0.1", port=6881, peer_source="tracker")
    connection = AsyncPeerConnection(peer, pm.torrent_data)
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.stats.bytes_downloaded = 65536
    connection.stats.blocks_delivered = 12
    connection.connection_start_time = time.time() - 600.0
    connection.stats.last_activity = time.time() - 120.0
    connection.peer_state.bitfield = bytearray(160)
    pm.connections[str(peer)] = connection
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.0.0.{i}", port=6880 + i) for i in range(2, 50)
    ]
    pm._pending_peer_keys = {f"10.0.0.{i}:{6880 + i}" for i in range(2, 50)}
    pm._disconnect_peer = AsyncMock()

    await pm._recycle_stagnant_nonrequestable_peers("requestable_peer_deficit")

    pm._disconnect_peer.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_does_not_retrigger_on_cold_start_requeue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid post_batch_completion spin when pending resume is deferred at cold start."""
    pm = _minimal_peer_manager()
    pm.config.discovery = SimpleNamespace(
        tracker_ingress_hold_pending_queue_threshold=5,
    )
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.0.0.{i}", port=6880 + i) for i in range(1, 12)
    ]
    pm._pending_peer_keys = {f"10.0.0.{i}:{6880 + i}" for i in range(1, 12)}
    monkeypatch.setattr(pm, "_metadata_is_incomplete", lambda: False)
    monkeypatch.setattr(
        pm,
        "_snapshot_connection_counts",
        lambda: (0, 0, 0),
    )
    pm.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="queued_reentrant")
    )
    request_resume = MagicMock()
    monkeypatch.setattr(pm, "request_pending_resume", request_resume)

    await pm._resume_pending_batches("payload_starvation")

    pm.connect_to_peers.assert_awaited_once()
    request_resume.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_pending_resume_bypasses_batch_owner_on_payload_starvation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending resume worker starts even when batches are active during payload starvation."""
    pm = _minimal_peer_manager()
    pm.config.discovery = SimpleNamespace(
        tracker_ingress_hold_pending_queue_threshold=5,
    )
    pm._connect_batch_active_count = 2
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.0.0.{i}", port=6880 + i) for i in range(1, 12)
    ]
    pm._pending_peer_keys = {f"10.0.0.{i}:{6880 + i}" for i in range(1, 12)}
    monkeypatch.setattr(pm, "_metadata_is_incomplete", lambda: False)
    monkeypatch.setattr(
        pm,
        "_snapshot_connection_counts",
        lambda: (2, 2, 0),
    )
    resume_batches = AsyncMock()
    monkeypatch.setattr(pm, "_resume_pending_batches", resume_batches)

    pm._schedule_pending_resume("requestable_peer_deficit")

    assert pm._pending_resume_task is not None
    await pm._pending_resume_task
    resume_batches.assert_awaited()


@pytest.mark.asyncio
async def test_pending_resume_bypasses_cold_start_single_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending resume may become batch owner while another cold-start batch is active."""
    pm = _minimal_peer_manager()
    pm.config.network.connect_to_peers_parallel_batches = 2
    pm._connect_batch_active_count = 1
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))
    monkeypatch.setattr(pm, "_remember_discovered_peers_for_retry", AsyncMock())
    monkeypatch.setattr(pm, "_prune_probation_peers", AsyncMock())
    enqueue = AsyncMock(return_value=1)
    monkeypatch.setattr(pm, "enqueue_peer_dicts_pending", enqueue)

    peer_dicts = [{"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"}]
    allowed = await pm.connect_to_peers(peer_dicts, _from_pending_queue=False)
    assert allowed.status == "owner_started"
    assert enqueue.await_count == 0

    pm._connect_batch_active_count = 2
    enqueue.reset_mock()
    deferred = await pm.connect_to_peers(peer_dicts, _from_pending_queue=False)
    assert deferred.status == "queued_reentrant"
    assert enqueue.await_count == 1

    pm._connect_batch_active_count = 1
    enqueue.reset_mock()
    pending_owner = await pm.connect_to_peers(peer_dicts, _from_pending_queue=True)
    assert pending_owner.status == "owner_started"
    assert enqueue.await_count == 0
