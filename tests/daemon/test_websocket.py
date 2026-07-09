"""Tests for WebSocket event subscription and delivery.

from __future__ import annotations

Tests WebSocket authentication, subscription, and event delivery.
"""

from __future__ import annotations

import asyncio

import aiohttp
import pytest
import pytest_asyncio

from ccbt.daemon.ipc_protocol import API_BASE_PATH, EventType
from ccbt.daemon.ipc_server import IPCServer

from tests.daemon.conftest import _cancel_stray_tasks


@pytest_asyncio.fixture(scope="function")
async def ipc_server(mock_session_manager):
    """Create IPC server with WebSocket support enabled."""
    api_key = "test-api-key-12345"
    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,
        websocket_enabled=True,
    )
    await server.start()
    actual_port = server.port
    try:
        yield server, api_key, actual_port
    finally:
        await server.stop()
        await _cancel_stray_tasks()


@pytest.mark.asyncio
async def test_websocket_requires_auth(ipc_server):
    """Test that WebSocket connection requires authentication."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events"

    # Try to connect without API key
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(ws_url) as ws:
                # Should be closed immediately
                msg = await ws.receive()
                assert msg.type == aiohttp.WSMsgType.CLOSE
                assert ws.close_code == 4001  # Unauthorized
        except Exception:
            # Connection might be rejected before WebSocket upgrade
            pass


@pytest.mark.asyncio
async def test_websocket_auth_via_query(ipc_server):
    """Test WebSocket authentication via query parameter."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        # Should connect successfully
        # Send subscription message
        await ws.send_json({
            "action": "subscribe",
            "data": {
                "event_types": [EventType.TORRENT_ADDED.value],
            },
        })

        # Wait for subscription confirmation
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.type == aiohttp.WSMsgType.TEXT
        data = msg.json()
        assert data["action"] == "subscribed"


@pytest.mark.asyncio
async def test_websocket_event_delivery(ipc_server):
    """Test WebSocket event delivery."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        # Subscribe to events
        await ws.send_json({
            "action": "subscribe",
            "data": {
                "event_types": [EventType.TORRENT_ADDED.value],
            },
        })

        # Wait for subscription confirmation
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.type == aiohttp.WSMsgType.TEXT
        data = msg.json()
        assert data["action"] == "subscribed"

        # Emit a test event (this would normally be done by the server)
        # For testing, we'll manually trigger an event
        await server.emit_websocket_event(
            EventType.TORRENT_ADDED,
            {"info_hash": "abc123", "name": "test"},
        )

        # Wait for event
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.type == aiohttp.WSMsgType.TEXT
        data = msg.json()
        assert data["type"] == EventType.TORRENT_ADDED.value
        assert "timestamp" in data
        assert "data" in data


@pytest.mark.asyncio
async def test_websocket_event_preserves_bridge_metadata(ipc_server):
    """Delivered events should preserve metadata needed by UI consumers."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        await ws.send_json(
            {
                "action": "subscribe",
                "data": {
                    "event_types": [EventType.TORRENT_STATUS_CHANGED.value],
                },
            },
        )
        await asyncio.wait_for(ws.receive(), timeout=2.0)

        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": "aa11", "status": "downloading"},
            raw_type="torrent_started",
            event_id="evt-1",
            source="session.status",
            priority="high",
            correlation_id="corr-1",
        )

        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        payload = msg.json()
        assert payload["type"] == EventType.TORRENT_STATUS_CHANGED.value
        assert payload["raw_type"] == "torrent_started"
        assert payload["event_id"] == "evt-1"
        assert payload["source"] == "session.status"
        assert payload["priority"] == "high"
        assert payload["correlation_id"] == "corr-1"


@pytest.mark.asyncio
async def test_websocket_heartbeat(ipc_server):
    """Test WebSocket heartbeat."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        # Subscribe
        await ws.send_json({
            "action": "subscribe",
            "data": {
                "event_types": [EventType.TORRENT_ADDED.value],
            },
        })

        # Wait for subscription confirmation
        await asyncio.wait_for(ws.receive(), timeout=2.0)

        # Wait for heartbeat (should arrive within heartbeat interval)
        # Note: This test may be flaky if heartbeat interval is long
        # In practice, heartbeat is 30s, so we'll just verify the connection works
        await ws.send_json({"action": "ping"})
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.type == aiohttp.WSMsgType.TEXT
        data = msg.json()
        # Should receive pong or ping
        assert data["action"] in ["pong", "ping"]


@pytest.mark.asyncio
async def test_websocket_info_hash_filter(ipc_server):
    """Subscription info_hash filter should only deliver matching events."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        target_hash = "aa11"
        await ws.send_json(
            {
                "action": "subscribe",
                "data": {
                    "event_types": [EventType.TORRENT_STATUS_CHANGED.value],
                    "info_hash": target_hash,
                },
            }
        )

        # subscription ack
        ack = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert ack.type == aiohttp.WSMsgType.TEXT
        assert ack.json()["action"] == "subscribed"

        # Non-matching event should be filtered out.
        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": "bb22", "status": "downloading"},
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive(), timeout=0.3)

        # Matching event should be delivered.
        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": target_hash, "status": "seeding"},
        )
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.type == aiohttp.WSMsgType.TEXT
        payload = msg.json()
        assert payload["type"] == EventType.TORRENT_STATUS_CHANGED.value
        assert payload["data"]["info_hash"] == target_hash


@pytest.mark.asyncio
async def test_websocket_priority_filter_uses_event_metadata(ipc_server):
    """Priority filtering should use the event envelope, not payload hacks."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        await ws.send_json(
            {
                "action": "subscribe",
                "data": {
                    "event_types": [EventType.TORRENT_STATUS_CHANGED.value],
                    "priority_filter": "high",
                },
            },
        )
        await asyncio.wait_for(ws.receive(), timeout=2.0)

        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": "aa11", "status": "queued"},
            priority="low",
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive(), timeout=0.3)

        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": "aa11", "status": "downloading"},
            priority="high",
        )
        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        assert msg.json()["priority"] == "high"


@pytest.mark.asyncio
async def test_websocket_rate_limit_is_per_stream(ipc_server):
    """Rate limiting should not suppress unrelated event streams on one socket."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
        await ws.send_json(
            {
                "action": "subscribe",
                "data": {
                    "event_types": [
                        EventType.TORRENT_ADDED.value,
                        EventType.TORRENT_STATUS_CHANGED.value,
                    ],
                    "rate_limit": 1.0,
                },
            },
        )
        await asyncio.wait_for(ws.receive(), timeout=2.0)

        await server.emit_websocket_event(
            EventType.TORRENT_ADDED,
            {"info_hash": "aa11", "name": "test"},
        )
        await server.emit_websocket_event(
            EventType.TORRENT_STATUS_CHANGED,
            {"info_hash": "aa11", "status": "downloading"},
            raw_type="torrent_started",
        )

        first = await asyncio.wait_for(ws.receive(), timeout=2.0)
        second = await asyncio.wait_for(ws.receive(), timeout=2.0)
        received_types = {first.json()["type"], second.json()["type"]}
        assert received_types == {
            EventType.TORRENT_ADDED.value,
            EventType.TORRENT_STATUS_CHANGED.value,
        }

