"""Pending resume/reentry contract baselines (pre-refactor)."""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.models import ConnectSubmitResult
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

pytestmark = [pytest.mark.unit, pytest.mark.peer]

_TORRENT = {
    "info_hash": b"test_info_hash_20byt",
    "pieces_info": {"num_pieces": 1},
}


def test_peer_disconnected_wrapper_schedules_pending_resume() -> None:
    """Baseline: disconnect path triggers pending-resume scheduling hook."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    manager._schedule_pending_resume = MagicMock()  # noqa: SLF001
    conn = SimpleNamespace(ip="127.0.0.1", port=6881)

    manager._peer_disconnected_wrapper(conn)  # noqa: SLF001

    manager._schedule_pending_resume.assert_called_once_with(  # noqa: SLF001
        reason="peer_disconnected"
    )


@pytest.mark.asyncio
async def test_resume_pending_batches_skips_while_owner_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending drain must not call connect_to_peers while batch owner is active.

    Baseline for split-state migration: `_batch_owner_active` gates resume.
    """
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        connect_mock = AsyncMock()
        monkeypatch.setattr(manager, "connect_to_peers", connect_mock)
        manager._batch_owner_active = True  # noqa: SLF001
        manager._dht_connect_deferral_active = True  # noqa: SLF001
        enq = await manager.enqueue_peer_dicts_pending(
            [{"ip": "192.0.2.1", "port": 6881}],
            reason="contract_baseline",
        )
        assert enq == 1
        await manager._resume_pending_batches(reason="contract_baseline")  # noqa: SLF001
        connect_mock.assert_not_awaited()
    finally:
        manager.connections = {}
        await manager.stop()


@pytest.mark.asyncio
async def test_resume_pending_batches_skips_while_pending_resume_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: only one pending-resume worker at a time (pre-refactor baseline)."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        connect_mock = AsyncMock()
        monkeypatch.setattr(manager, "connect_to_peers", connect_mock)
        manager._batch_owner_active = False  # noqa: SLF001
        manager._pending_resume_in_progress = True  # noqa: SLF001
        await manager.enqueue_peer_dicts_pending(
            [{"ip": "192.0.2.2", "port": 6882}],
            reason="contract_baseline",
        )
        await manager._resume_pending_batches(reason="contract_baseline")  # noqa: SLF001
        connect_mock.assert_not_awaited()
    finally:
        manager.connections = {}
        await manager.stop()


@pytest.mark.asyncio
async def test_schedule_pending_resume_uses_create_task_not_inline_await(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deferred drain: resume is scheduled on the loop, not awaited synchronously."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    await manager.start()
    try:
        loop = asyncio.get_running_loop()
        create_calls: list[Any] = []
        real_create = loop.create_task

        def wrap_create_task(
            coro: object,
            *,
            name: str | None = None,
        ) -> asyncio.Task[Any]:
            if name is not None and name.startswith("pending_resume:"):
                create_calls.append(coro)
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            return real_create(asyncio.sleep(0), name=name)

        monkeypatch.setattr(loop, "create_task", wrap_create_task)
        add_spy = MagicMock(side_effect=manager.add_background_task)
        monkeypatch.setattr(manager, "add_background_task", add_spy)
        manager._schedule_pending_resume(reason="contract_inline")  # noqa: SLF001

        assert len(create_calls) == 1
        add_spy.assert_called_once()
        pending = add_spy.call_args[0][0]
        assert isinstance(pending, asyncio.Task)
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pending
    finally:
        manager.connections = {}
        await manager.stop()


@pytest.mark.asyncio
async def test_schedule_pending_resume_deduplicates_active_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only one pending-resume worker should be active at a time."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    await manager.start()
    try:
        loop = asyncio.get_running_loop()
        create_count = 0
        real_create = loop.create_task
        gate = asyncio.Event()

        async def never_finishes() -> None:
            await gate.wait()

        async def fake_resume(*, reason: str) -> None:  # noqa: ARG001
            await never_finishes()

        monkeypatch.setattr(manager, "_resume_pending_batches", fake_resume)

        def wrap_create_task(
            coro: object,
            *,
            name: str | None = None,
        ) -> asyncio.Task[Any]:
            nonlocal create_count
            if name is not None and name.startswith("pending_resume:"):
                create_count += 1
            return real_create(coro, name=name)

        monkeypatch.setattr(loop, "create_task", wrap_create_task)

        manager._schedule_pending_resume(reason="first")  # noqa: SLF001
        manager._schedule_pending_resume(reason="second")  # noqa: SLF001
        await asyncio.sleep(0)
        assert create_count == 1
        gate.set()
        pending = manager._pending_resume_task  # noqa: SLF001
        if pending is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await pending
    finally:
        manager.connections = {}
        await manager.stop()


@pytest.mark.asyncio
async def test_queue_edge_triggers_public_pending_resume_request() -> None:
    """Queue transition 0->nonzero should trigger a resume request edge."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    await manager.start()
    try:
        manager.request_pending_resume = MagicMock()  # type: ignore[method-assign]
        enq = await manager.enqueue_peer_dicts_pending(
            [{"ip": "192.0.2.21", "port": 6881}],
            reason="contract_queue_edge",
        )
        assert enq == 1
        manager.request_pending_resume.assert_called_once_with(  # type: ignore[attr-defined]
            reason="contract_queue_edge:queue_edge"
        )
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_inflight_drain_with_pending_queue_triggers_resume() -> None:
    """Inflight set draining to zero with queued peers should request resume."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    await manager.start()
    try:
        manager.request_pending_resume = MagicMock()  # type: ignore[method-assign]
        manager._pending_peer_queue = [  # noqa: SLF001
            SimpleNamespace(ip="192.0.2.22", port=6882)
        ]
        manager._inflight_peer_connects = set()  # noqa: SLF001
        manager._on_inflight_peer_discarded(reason="contract_drain")  # noqa: SLF001
        manager.request_pending_resume.assert_called_once_with(  # type: ignore[attr-defined]
            reason="inflight_drained:contract_drain"
        )
    finally:
        await manager.stop()


def test_notify_capacity_change_requires_blocked_or_retry_edge() -> None:
    """Capacity notification should only trigger on blocked/retry edges."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    manager._running = True  # noqa: SLF001
    manager._pending_peer_queue = [SimpleNamespace(ip="192.0.2.10", port=6881)]  # noqa: SLF001
    manager._pending_capacity_blocked = False  # noqa: SLF001
    manager._pending_resume_retry_task = None  # noqa: SLF001
    manager._schedule_pending_resume = MagicMock()  # noqa: SLF001

    manager.notify_capacity_change()

    manager._schedule_pending_resume.assert_not_called()  # noqa: SLF001


def test_notify_capacity_change_schedules_when_blocked_edge() -> None:
    """Capacity-open edge should schedule pending resume once."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    manager._running = True  # noqa: SLF001
    manager._pending_peer_queue = [SimpleNamespace(ip="192.0.2.11", port=6882)]  # noqa: SLF001
    manager._pending_capacity_blocked = True  # noqa: SLF001
    manager._pending_resume_retry_task = None  # noqa: SLF001
    manager._schedule_pending_resume = MagicMock()  # noqa: SLF001

    manager.notify_capacity_change()

    manager._schedule_pending_resume.assert_called_once_with(  # noqa: SLF001
        reason="capacity_change"
    )


@pytest.mark.asyncio
async def test_resume_pending_batches_drains_bounded_slice_then_retriggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume pass drains a bounded chunk and asks for continuation when backlog remains."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=10,
    )
    await manager.start()
    try:
        manager.connections = {
            f"198.51.100.{i}:6881": SimpleNamespace(
                is_active=lambda: True,
                can_request=lambda: True,
                connection_task=None,
            )
            for i in range(1, 9)
        }
        enq = await manager.enqueue_peer_dicts_pending(
            [
                {"ip": f"203.0.113.{i}", "port": 7000 + i}
                for i in range(1, 13)
            ],
            reason="bounded_resume_contract",
        )
        assert enq == 12
        connect_mock = AsyncMock(
            return_value=ConnectSubmitResult(status="owner_started"),
        )
        monkeypatch.setattr(manager, "connect_to_peers", connect_mock)
        manager.request_pending_resume = MagicMock()  # type: ignore[method-assign]

        await manager._resume_pending_batches(reason="bounded_resume_contract")  # noqa: SLF001

        connect_mock.assert_awaited_once()
        resumed_peer_dicts = connect_mock.await_args.args[0]
        assert len(resumed_peer_dicts) == 8
        assert len(manager._pending_peer_queue) == 4  # noqa: SLF001
        manager.request_pending_resume.assert_called_once_with(  # type: ignore[attr-defined]
            reason="post_batch_completion"
        )
    finally:
        manager.connections = {}
        await manager.stop()


@pytest.mark.asyncio
async def test_resume_pending_batches_continues_until_queue_drained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successive resume passes continue from pending queue remainder."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=10,
    )
    await manager.start()
    try:
        manager.connections = {
            f"198.51.100.{i}:6881": SimpleNamespace(
                is_active=lambda: True,
                can_request=lambda: True,
                connection_task=None,
            )
            for i in range(1, 9)
        }
        enq = await manager.enqueue_peer_dicts_pending(
            [
                {"ip": f"203.0.113.{i}", "port": 7100 + i}
                for i in range(1, 13)
            ],
            reason="bounded_resume_contract",
        )
        assert enq == 12
        connect_mock = AsyncMock(
            return_value=ConnectSubmitResult(status="owner_started"),
        )
        monkeypatch.setattr(manager, "connect_to_peers", connect_mock)
        manager.request_pending_resume = MagicMock()  # type: ignore[method-assign]

        await manager._resume_pending_batches(reason="first_pass")  # noqa: SLF001
        await manager._resume_pending_batches(reason="second_pass")  # noqa: SLF001

        assert connect_mock.await_count == 2
        first_batch = connect_mock.await_args_list[0].args[0]
        second_batch = connect_mock.await_args_list[1].args[0]
        assert len(first_batch) == 8
        assert len(second_batch) == 4
        assert len(manager._pending_peer_queue) == 0  # noqa: SLF001
    finally:
        manager.connections = {}
        await manager.stop()
