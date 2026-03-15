"""Unit tests for daemon interface adapter realtime behavior."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

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
