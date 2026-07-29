"""Cold-start connect funnel regression tests."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.models import EncryptionMode
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
    _connect_batch_max_duration_s,
    _connect_batch_process_timeout_s,
    _count_remote_choked_actives,
    _is_expected_outbound_connect_failure,
    _mid_swarm_patience_extension_applies,
    _min_successful_for_early_batch_exit,
    _mse_handshake_retry_slack_s,
    _should_detach_inflight_on_batch_timeout,
    _productive_swarm_pause_min_requestable,
    _swarm_growth_target,
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
async def test_resume_pending_batches_overrides_active_batch_when_starving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero actives + active batch owner defers unless the owner is stale."""
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = [
        PeerInfo(ip=f"192.0.2.{i}", port=6880 + i) for i in range(2, 7)
    ]
    pm._pending_peer_keys = {f"192.0.2.{i}:{6880 + i}" for i in range(2, 7)}
    now = time.monotonic()
    pm._pending_peer_enqueued_at = dict.fromkeys(pm._pending_peer_keys, now)
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))
    pm.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="owner_started")
    )

    await pm._resume_pending_batches("test_starvation_override")

    # Fresh batch owners are protected: defer zero-peer drain rather than stacking.
    pm.connect_to_peers.assert_not_awaited()

    # Stale-owner reset requires a deeper pending queue (>=50) and elapsed wall time.
    pm._pending_peer_queue = [
        PeerInfo(ip=f"192.0.2.{i % 200}", port=7000 + i) for i in range(60)
    ]
    pm._pending_peer_keys = {
        f"{p.ip}:{p.port}" for p in pm._pending_peer_queue
    }
    pm._last_connect_batch_wall_start = time.time() - 120.0
    pm.request_pending_resume = MagicMock()
    await pm._resume_pending_batches("test_starvation_override_stale")
    pm.request_pending_resume.assert_called_once_with(reason="stale_batch_owner_reset")


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
async def test_peer_evaluation_releases_connection_lock_for_connect_batch() -> None:
    """Connect path can acquire connection_lock after a brief evaluation hold.

    Uses wait_for (not asyncio.timeout) for py3.9 CI compatibility. Avoids
    starting the full evaluation loop, which can starve the lock under a
    zero-delay sleep mock.
    """
    pm = _minimal_peer_manager()
    held = asyncio.Event()
    released = asyncio.Event()

    async def _brief_evaluation_hold() -> None:
        async with pm.connection_lock:
            held.set()
            await asyncio.sleep(0.01)
        released.set()

    holder = asyncio.create_task(_brief_evaluation_hold())
    try:
        await asyncio.wait_for(held.wait(), timeout=2.0)

        async def _touch_lock() -> None:
            async with pm.connection_lock:
                return None

        await asyncio.wait_for(_touch_lock(), timeout=2.0)
        await asyncio.wait_for(released.wait(), timeout=2.0)
    finally:
        holder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await holder


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

    pm.connect_to_peers.assert_not_awaited()
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
    """At zero actives only one connect batch owner may run."""
    pm = _minimal_peer_manager()
    pm.config.network.connect_to_peers_parallel_batches = 2
    pm._connect_batch_active_count = 0
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))
    monkeypatch.setattr(pm, "_remember_discovered_peers_for_retry", AsyncMock())
    monkeypatch.setattr(pm, "_prune_probation_peers", AsyncMock())
    enqueue = AsyncMock(return_value=1)
    monkeypatch.setattr(pm, "enqueue_peer_dicts_pending", enqueue)

    peer_dicts = [{"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"}]
    allowed = await pm.connect_to_peers(peer_dicts, _from_pending_queue=False)
    assert allowed.status == "owner_started"
    assert enqueue.await_count == 0

    pm._connect_batch_active_count = 1
    enqueue.reset_mock()
    deferred = await pm.connect_to_peers(peer_dicts, _from_pending_queue=False)
    assert deferred.status == "queued_reentrant"
    assert enqueue.await_count == 1

    pm._connect_batch_active_count = 1
    enqueue.reset_mock()
    pending_owner = await pm.connect_to_peers(peer_dicts, _from_pending_queue=True)
    assert pending_owner.status == "queued_reentrant"
    assert enqueue.await_count == 1


def test_min_successful_for_early_batch_exit_detaches_durably_when_sparse() -> None:
    threshold = _min_successful_for_early_batch_exit(
        20,
        active_peer_count=5,
        early_exit_min_active_peers=10,
    )
    assert threshold == 5


def test_min_successful_for_early_batch_exit_enabled_when_swarm_healthy() -> None:
    threshold = _min_successful_for_early_batch_exit(
        20,
        active_peer_count=12,
        early_exit_min_active_peers=10,
    )
    assert threshold == 5


def test_connect_batch_max_duration_zero_active_uses_extended_budget() -> None:
    assert _connect_batch_max_duration_s(0) == 60.0
    assert _connect_batch_max_duration_s(0, zero_active_max_duration_s=75.0) == 75.0
    assert _connect_batch_max_duration_s(1) == 45.0


def test_connect_batch_process_timeout_zero_active_covers_handshakes() -> None:
    timeout = _connect_batch_process_timeout_s(
        30.0,
        low_peer_recovery_mode=False,
        active_peer_count=0,
        max_batch_duration=60.0,
    )
    assert timeout >= 90.0


def test_connect_batch_process_timeout_choked_swarm_covers_mse() -> None:
    timeout = _connect_batch_process_timeout_s(
        80.0,
        low_peer_recovery_mode=True,
        active_peer_count=1,
        max_batch_duration=45.0,
        requestable_peer_count=0,
    )
    assert timeout >= 90.0


def test_mse_handshake_retry_slack_when_encryption_preferred() -> None:
    security = SimpleNamespace(
        enable_encryption=True,
        encryption_mode="prefer",
        encryption_allow_plain_fallback=True,
    )
    slack = _mse_handshake_retry_slack_s(
        security, tcp_budget=20.0, handshake_budget=30.0
    )
    assert slack >= 50.0


def test_should_detach_inflight_on_batch_timeout() -> None:
    assert _should_detach_inflight_on_batch_timeout(
        active_peer_count=0, requestable_peer_count=0
    )
    assert _should_detach_inflight_on_batch_timeout(
        active_peer_count=1, requestable_peer_count=0
    )
    assert _should_detach_inflight_on_batch_timeout(
        active_peer_count=3, requestable_peer_count=2
    )


def test_productive_swarm_pause_min_requestable_scales_with_cap() -> None:
    assert _productive_swarm_pause_min_requestable(50) == 8
    assert _productive_swarm_pause_min_requestable(50, configured_min=12) == 12
    assert _productive_swarm_pause_min_requestable(16, configured_min=8) == 5


@pytest.mark.asyncio
async def test_bypass_pending_resume_on_restart_collapse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deep pending + zero actives may bypass batch-owner gate once drain proceeds."""
    pm = _minimal_peer_manager()
    pm.config.discovery = SimpleNamespace(
        tracker_ingress_hold_pending_queue_threshold=200,
    )
    pm._connect_batch_active_count = 2
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.1.0.{i}", port=6880 + i) for i in range(250)
    ]
    pm._pending_peer_keys = {f"10.1.0.{i}:{6880 + i}" for i in range(250)}
    monkeypatch.setattr(pm, "_metadata_is_incomplete", lambda: False)
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))
    pm.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="owner_started")
    )

    assert pm._should_bypass_batch_owner_for_pending_resume() is True

    # Zero-active + active owners still hits the early deferral path first.
    drain = AsyncMock()
    monkeypatch.setattr(pm, "_connect_batch_from_pending", drain)
    await pm._resume_pending_batches("restart_collapse")
    assert drain.await_count == 0
    pm.connect_to_peers.assert_not_awaited()

    # Once at least one active peer exists, bypass allows a parallel pending drain.
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (1, 1, 0))
    created: list[Any] = []

    def _capture_task(coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        created.append(coro)
        return asyncio.get_running_loop().create_task(coro)

    monkeypatch.setattr(asyncio, "create_task", _capture_task)
    await pm._resume_pending_batches("restart_collapse_with_active")
    for task in created:
        await task
    assert drain.await_count == 1


@pytest.mark.asyncio
async def test_maybe_reset_stale_batch_owner_clears_stuck_funnel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._last_connect_batch_wall_start = time.time() - 60.0
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.3.0.{i}", port=6880 + i) for i in range(120)
    ]
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))

    assert pm._maybe_reset_stale_batch_owner() is True
    assert pm._connect_batch_active_count == 0
    assert pm._dht_connect_deferral_active is False


def test_maybe_reset_stale_batch_owner_faster_when_queue_deep() -> None:
    pm = _minimal_peer_manager()
    pm._connect_batch_active_count = 1
    pm._last_connect_batch_wall_start = time.time() - 25.0
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.5.0.{i}", port=6880 + i) for i in range(600)
    ]
    monkeypatch_stub = lambda: (0, 0, 0)  # noqa: E731
    pm._snapshot_connection_counts = monkeypatch_stub  # type: ignore[method-assign]
    assert pm._maybe_reset_stale_batch_owner() is True


def test_cap_connect_task_timeout_s_shortens_deep_pending_queue() -> None:
    pm = _minimal_peer_manager()
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.4.0.{i}", port=6880 + i) for i in range(250)
    ]
    capped = pm._cap_connect_task_timeout_s(130.0)
    assert capped <= 42.0


@pytest.mark.asyncio
async def test_zero_active_reentrant_waits_for_batch_owner_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tracker overflow queues peers until the sole cold-start owner completes."""
    pm = _minimal_peer_manager()
    pm.config.network.connect_to_peers_parallel_batches = 1
    pm.config.discovery = SimpleNamespace(
        tracker_ingress_hold_pending_queue_threshold=200,
    )
    pm._connect_batch_active_count = 1
    pm._pending_peer_queue = [
        PeerInfo(ip=f"10.2.0.{i}", port=6880 + i) for i in range(210)
    ]
    monkeypatch.setattr(pm, "_snapshot_connection_counts", lambda: (0, 0, 0))
    monkeypatch.setattr(pm, "request_pending_resume", MagicMock())
    monkeypatch.setattr(
        pm,
        "enqueue_peer_dicts_pending",
        AsyncMock(return_value=1),
    )

    peer_dicts = [{"ip": "10.2.0.99", "port": 6881, "peer_source": "tracker"}]
    result = await pm.connect_to_peers(peer_dicts)

    assert result.status == "queued_reentrant"
    pm.request_pending_resume.assert_not_called()


def test_swarm_growth_target_scales_with_cap() -> None:
    assert _swarm_growth_target(50) == 12
    assert _swarm_growth_target(16) == 4


def test_count_remote_choked_actives_ignores_pipeline_saturated() -> None:
    productive = MagicMock()
    productive.is_active.return_value = True
    productive.peer_choking = False

    choked = MagicMock()
    choked.is_active.return_value = True
    choked.peer_choking = True

    assert _count_remote_choked_actives([productive, choked]) == 1


def test_mid_swarm_patience_not_for_pipeline_only_stall() -> None:
    assert not _mid_swarm_patience_extension_applies(
        15,
        requestable_peer_count=0,
        pending_queue_depth=500,
        inflight_peer_connects=10,
        remote_choked_active_count=0,
        max_peers_per_torrent=50,
    )


def test_mid_swarm_patience_for_remote_choked_stall() -> None:
    assert _mid_swarm_patience_extension_applies(
        10,
        requestable_peer_count=0,
        pending_queue_depth=500,
        inflight_peer_connects=10,
        remote_choked_active_count=2,
        max_peers_per_torrent=50,
    )


def test_connect_batch_max_duration_below_growth_target() -> None:
    assert _connect_batch_max_duration_s(4, max_peers_per_torrent=50) == 45.0


def test_should_skip_pending_requeue_after_hard_disconnect() -> None:
    pm = _minimal_peer_manager()
    peer = PeerInfo(ip="1.2.3.4", port=6881)
    assert not pm._should_skip_pending_requeue(peer)
    pm._mark_hard_disconnected_peer(peer)
    assert pm._should_skip_pending_requeue(peer)
