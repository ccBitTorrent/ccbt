"""Regression tests for swarm-recovery peer pipeline controls."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.peer.peer import PeerInfo


def _build_manager(max_peers: int = 2) -> AsyncPeerConnectionManager:
    torrent_data = {
        "info_hash": b"01234567890123456789",
        "pieces_info": {"num_pieces": 8},
    }
    piece_manager = MagicMock()
    piece_manager.verified_pieces = []
    return AsyncPeerConnectionManager(
        torrent_data=torrent_data,
        piece_manager=piece_manager,
        max_peers_per_torrent=max_peers,
    )


async def _cancel_reconnection_task(manager: AsyncPeerConnectionManager) -> None:
    task = manager._reconnection_task
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    manager._reconnection_task = None


async def _cancel_stray_connect_tasks() -> None:
    pending = [
        task
        for task in asyncio.all_tasks()
        if not task.done() and task.get_name().startswith("connect_peer:")
    ]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def _disable_pool_warmup_for_tests(
    manager: AsyncPeerConnectionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager.config.network.connection_pool_warmup_enabled = False
    monkeypatch.setattr(
        manager.connection_pool,
        "warmup_connections",
        AsyncMock(return_value=None),
    )


async def _start_manager_for_tests(
    manager: AsyncPeerConnectionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_pool_warmup_for_tests(manager, monkeypatch)
    await manager.start()
    await _cancel_reconnection_task(manager)


async def _stop_manager_for_tests(manager: AsyncPeerConnectionManager) -> None:
    await _cancel_reconnection_task(manager)
    await _cancel_stray_connect_tasks()
    await manager.stop()


@pytest.mark.asyncio
async def test_resume_pending_batches_schedules_retry_when_full() -> None:
    manager = _build_manager(max_peers=1)
    manager._running = True

    peer = PeerInfo(ip="198.51.100.10", port=6881)
    manager._pending_peer_queue = [peer]
    manager._pending_peer_keys = {f"{peer.ip}:{peer.port}"}

    saturated_conn = MagicMock()
    saturated_conn.is_active.return_value = True
    manager.connections = {"saturated": saturated_conn}

    await manager._resume_pending_batches(reason="unit")

    assert manager._pending_resume_retry_task is not None
    assert not manager._pending_resume_retry_task.done()
    manager._pending_resume_retry_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await manager._pending_resume_retry_task


@pytest.mark.asyncio
async def test_pending_resume_retry_prefers_earlier_deadline() -> None:
    manager = _build_manager(max_peers=1)
    manager._running = True

    manager._schedule_pending_resume_retry(delay_s=3.0, reason="long_backoff")
    first_task = manager._pending_resume_retry_task
    first_due = manager._pending_resume_retry_due_at
    assert first_task is not None
    assert first_due is not None

    manager._schedule_pending_resume_retry(delay_s=0.3, reason="short_backoff")
    second_task = manager._pending_resume_retry_task
    second_due = manager._pending_resume_retry_due_at
    assert second_task is not None
    assert second_due is not None
    assert second_task is not first_task
    assert second_due < first_due

    await asyncio.sleep(0)
    assert first_task.done() or first_task.cancelled()

    second_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second_task


@pytest.mark.asyncio
async def test_plaintext_fallback_is_bounded_per_peer_window() -> None:
    manager = _build_manager(max_peers=4)
    manager._mse_plain_fallback_window_s = 60.0
    manager._mse_plain_fallback_max_per_window = 2

    peer = PeerInfo(ip="198.51.100.20", port=6881)

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout")
    manager._record_mse_plain_fallback(peer, "mse_timeout")

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout")
    manager._record_mse_plain_fallback(peer, "mse_timeout")

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout") is False


@pytest.mark.asyncio
async def test_inflight_dedup_uses_delayed_pending_retry(monkeypatch) -> None:
    manager = _build_manager(max_peers=4)
    await _start_manager_for_tests(manager, monkeypatch)
    try:
        manager._running = True
        manager.max_peers_per_torrent = 4
        manager._inflight_peer_connects = {"198.51.100.30:6881"}
        manager._queue_pending_peers = AsyncMock(return_value=1)
        manager._schedule_pending_resume_retry = MagicMock()

        result = await manager.connect_to_peers(
            [{"ip": "198.51.100.30", "port": 6881}]
        )

        assert result.status == "owner_started"
        manager._queue_pending_peers.assert_awaited_once()
        manager._schedule_pending_resume_retry.assert_called_with(
            delay_s=0.5,
            reason="inflight_dedup",
        )
    finally:
        await _stop_manager_for_tests(manager)


@pytest.mark.asyncio
async def test_inflight_dedup_retry_backoff_is_bounded_exponential(monkeypatch) -> None:
    manager = _build_manager(max_peers=4)
    await _start_manager_for_tests(manager, monkeypatch)
    try:
        manager._running = True
        manager.max_peers_per_torrent = 4
        manager._inflight_peer_connects = {"198.51.100.31:6881"}
        manager._queue_pending_peers = AsyncMock(return_value=1)
        manager._schedule_pending_resume_retry = MagicMock()
        manager._inflight_dedup_retry_backoff_s = 0.5
        manager._inflight_dedup_retry_backoff_max_s = 1.0

        await manager.connect_to_peers([{"ip": "198.51.100.31", "port": 6881}])
        await manager.connect_to_peers([{"ip": "198.51.100.31", "port": 6881}])
        await manager.connect_to_peers([{"ip": "198.51.100.31", "port": 6881}])

        calls = manager._schedule_pending_resume_retry.call_args_list
        assert calls[0].kwargs["delay_s"] == 0.5
        assert calls[1].kwargs["delay_s"] == 1.0
        assert calls[2].kwargs["delay_s"] == 1.0
    finally:
        await _stop_manager_for_tests(manager)


@pytest.mark.asyncio
async def test_resume_pending_batches_prunes_expired_pending_peers(monkeypatch) -> None:
    manager = _build_manager(max_peers=4)
    await _start_manager_for_tests(manager, monkeypatch)
    try:
        manager._running = True
        manager._pending_peer_queue_max_age_s = 1.0
        stale = PeerInfo(ip="198.51.100.40", port=6881)
        manager._pending_peer_queue = [stale]
        manager._pending_peer_keys = {f"{stale.ip}:{stale.port}"}
        manager._pending_peer_enqueued_at = {
            f"{stale.ip}:{stale.port}": asyncio.get_running_loop().time() - 5.0
        }
        manager.connect_to_peers = AsyncMock()

        await manager._resume_pending_batches(reason="expiry_test")

        manager.connect_to_peers.assert_not_awaited()
        assert manager._pending_peer_queue == []
        assert manager._pending_peer_keys == set()
    finally:
        await _stop_manager_for_tests(manager)
