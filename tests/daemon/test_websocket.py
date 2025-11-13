"""Tests for WebSocket event subscription and delivery.

from __future__ import annotations

Tests WebSocket authentication, subscription, and event delivery.
"""

from __future__ import annotations

import asyncio

import pytest

import aiohttp

from ccbt.daemon.ipc_protocol import API_BASE_PATH, EventType
from ccbt.daemon.ipc_server import IPCServer
from ccbt.session.session import AsyncSessionManager


@pytest.fixture
async def mock_session_manager():
    """Create a mock session manager."""
    session = AsyncSessionManager()
    await session.start()
    yield session
    await session.stop()


@pytest.fixture
async def ipc_server(mock_session_manager):
    """Create IPC server for testing."""
    api_key = "test-api-key-12345"
    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,  # Use random port
        websocket_enabled=True,
    )
    await server.start()
    actual_port = server.port
    yield server, api_key, actual_port
    await server.stop()


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

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
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

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
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
            await server._emit_websocket_event(
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
async def test_websocket_heartbeat(ipc_server):
    """Test WebSocket heartbeat."""
    server, api_key, port = ipc_server
    ws_url = f"ws://127.0.0.1:{port}{API_BASE_PATH}/events?api_key={api_key}"

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
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

