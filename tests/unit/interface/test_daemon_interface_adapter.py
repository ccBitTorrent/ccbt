"""Unit tests for daemon interface adapter realtime behavior."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.interface.daemon_session_adapter import (
    WEBSOCKET_EVENT_SUBSCRIPTIONS,
    DaemonInterfaceAdapter,
)

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_websocket_reconnect_restores_full_subscription_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconnects should resubscribe to the full UI event surface."""
    ipc_client = MagicMock()
    ipc_client.receive_events_batch = AsyncMock(
        side_effect=[RuntimeError("boom"), asyncio.CancelledError()],
    )
    ipc_client.is_daemon_running = AsyncMock(return_value=True)
    ipc_client.connect_websocket = AsyncMock(return_value=True)
    ipc_client.subscribe_events = AsyncMock(return_value=True)

    adapter = DaemonInterfaceAdapter(ipc_client)
    adapter._websocket_connected = True

    async def _fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    await adapter._websocket_event_loop()

    ipc_client.subscribe_events.assert_awaited_once_with(
        list(WEBSOCKET_EVENT_SUBSCRIPTIONS),
    )


@pytest.mark.asyncio
async def test_websocket_reconnect_calls_resync_from_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After reconnect, adapter must resync caches from UI snapshot to avoid stale state."""
    ipc_client = MagicMock()
    ipc_client.receive_events_batch = AsyncMock(
        side_effect=[RuntimeError("connection lost"), asyncio.CancelledError()],
    )
    ipc_client.is_daemon_running = AsyncMock(return_value=True)
    ipc_client.connect_websocket = AsyncMock(return_value=True)
    ipc_client.subscribe_events = AsyncMock(return_value=True)

    adapter = DaemonInterfaceAdapter(ipc_client)
    adapter._websocket_connected = True
    resync_awaited = []

    async def _capture_resync() -> None:
        resync_awaited.append(1)

    adapter._resync_from_snapshot = _capture_resync  # type: ignore[assignment]

    async def _no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    await adapter._websocket_event_loop()

    assert len(resync_awaited) == 1, "Reconnect must trigger one _resync_from_snapshot"
    ipc_client.subscribe_events.assert_awaited()


@pytest.mark.asyncio
async def test_media_events_invalidate_media_cache_and_notify_callbacks() -> None:
    """Media WebSocket events should invalidate caches and reach UI callbacks."""
    ipc_client = MagicMock()
    adapter = DaemonInterfaceAdapter(ipc_client)
    adapter._media_status_cache["a" * 40] = {"state": "buffering"}
    adapter._media_status_cache["stream-1"] = {"state": "buffering"}
    adapter._torrent_status_cache["a" * 40] = {"progress": 0.2}

    received: list[dict[str, str]] = []

    async def _on_media_event(payload: dict[str, str]) -> None:
        received.append(payload)

    adapter.on_media_event = _on_media_event

    event = MagicMock(
        type=next(
            event_type
            for event_type in WEBSOCKET_EVENT_SUBSCRIPTIONS
            if event_type.value == "media_stream_ready"
        ),
        data={"info_hash": "a" * 40, "stream_id": "stream-1"},
    )

    await adapter._handle_websocket_event(event)

    assert "a" * 40 not in adapter._media_status_cache
    assert "stream-1" not in adapter._media_status_cache
    assert "a" * 40 not in adapter._torrent_status_cache
    assert received[0]["event"] == "media_stream_ready"


@pytest.mark.asyncio
async def test_is_started_on_current_loop_detects_dead_loop() -> None:
    """_is_started_on_current_loop must return False for a never-started or stale-loop adapter.

    This is the linchpin of the R1 fix: _ensure_adapter_ready uses this check to
    decide whether to restart the adapter on Textual's loop. If a prior start()
    bound tasks to a throwaway asyncio.run() loop that has since closed, the
    check must return False so the adapter restarts on the current loop instead
    of silently retaining a dead _websocket_connected=True state.
    """
    ipc_client = MagicMock()
    adapter = DaemonInterfaceAdapter(ipc_client)

    # Never started -> False
    assert adapter._is_started_on_current_loop() is False

    # Started on a different (closed) loop -> False
    other_loop = asyncio.new_event_loop()
    try:
        adapter._start_loop = other_loop
        assert adapter._is_started_on_current_loop() is False
    finally:
        other_loop.close()

    # Started on the current running loop with a live task -> True
    adapter._start_loop = asyncio.get_running_loop()
    live_task = asyncio.create_task(asyncio.sleep(10))
    try:
        adapter._websocket_task = live_task
        assert adapter._is_started_on_current_loop() is True
    finally:
        live_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await live_task
        adapter._websocket_task = None


@pytest.mark.asyncio
async def test_take_over_websocket_receive_cancels_client_receive_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_take_over_websocket_receive must cancel the IPC client's _websocket_task.

    This is the R2 fix: connect_websocket() spawns IPCClient._websocket_receive_loop()
    as IPCClient._websocket_task. If the adapter does not cancel it before running its
    own _websocket_event_loop(), two concurrent receive() calls race on the same
    aiohttp WebSocket ("Concurrent call to receive() is not allowed") and event flow
    stops mid-session.
    """
    ipc_client = MagicMock()
    client_task = asyncio.Future()  # never-completing stand-in for the receive loop
    ipc_client._websocket_task = client_task  # type: ignore[attr-defined]

    adapter = DaemonInterfaceAdapter(ipc_client)

    async def _fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    await adapter._take_over_websocket_receive()

    # The client's _websocket_task must be cancelled and cleared.
    assert client_task.cancelled() is True
    assert getattr(ipc_client, "_websocket_task", None) is None


@pytest.mark.asyncio
async def test_start_restarts_on_current_loop_after_dead_loop_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """start() must tear down stale resources and rebind to the current loop.

    Reproduces R1: a prior start() bound _websocket_connected=True and tasks to a
    now-closed loop (the throwaway asyncio.run() loop the CLI used to use). Calling
    start() on Textual's loop must stop the stale resources and re-bind, rather
    than skipping because _websocket_connected is already True.
    """
    ipc_client = MagicMock()
    ipc_client.is_daemon_running = AsyncMock(return_value=True)
    ipc_client.connect_websocket = AsyncMock(return_value=True)
    ipc_client.subscribe_events = AsyncMock(return_value=True)
    # Make stop()-driven cleanup awaitable on the MagicMock client.
    ipc_client._close_websocket = AsyncMock()  # type: ignore[attr-defined]
    ipc_client.close = AsyncMock()

    adapter = DaemonInterfaceAdapter(ipc_client)
    adapter._resync_from_snapshot = AsyncMock()  # type: ignore[assignment]
    adapter._refresh_cache = AsyncMock()  # type: ignore[assignment]
    # Replace the long-running event loops with awaitable no-ops so the tasks
    # created by start() complete instantly instead of looping forever.
    adapter._websocket_event_loop = AsyncMock()  # type: ignore[assignment]
    adapter._peers_update_loop = AsyncMock()  # type: ignore[assignment]

    # Simulate a prior start() on a now-closed loop (the R1 trap).
    dead_loop = asyncio.new_event_loop()
    dead_loop.close()
    adapter._start_loop = dead_loop
    adapter._websocket_connected = True
    stale_task = asyncio.Future()
    adapter._websocket_task = stale_task  # type: ignore[assignment]
    adapter._peers_update_task = None  # type: ignore[assignment]

    # Patch sleep so the take-over helper does not delay the test.
    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    await adapter.start()

    # Stale resources torn down, rebinding happened on the current loop.
    assert stale_task.cancelled() is True
    assert adapter._start_loop is asyncio.get_running_loop()
    assert adapter._websocket_task is not None
    assert adapter._websocket_task is not stale_task

    # Clean up the real tasks that start() scheduled so the test loop can exit.
    for task in (adapter._websocket_task, adapter._peers_update_task):
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
