"""Tests for media stream IPC endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_asyncio

from ccbt.daemon.ipc_protocol import API_BASE_PATH, API_KEY_HEADER
from ccbt.daemon.ipc_server import IPCServer
from ccbt.session.session import AsyncSessionManager

pytestmark = [pytest.mark.daemon]
HTTP_OK = 200
STREAM_PORT = 9999


@pytest_asyncio.fixture
async def media_ipc_server():
    """Create an IPC server backed by a lightweight session manager."""
    session = AsyncSessionManager()
    session.config.nat.auto_map_ports = False
    session.config.discovery.enable_dht = False
    await session.start()
    session.start_media_stream = AsyncMock(
        return_value={
            "stream_id": "stream-1",
            "info_hash": "a" * 40,
            "file_index": 0,
            "state": "buffering",
            "stream_url": f"http://127.0.0.1:{STREAM_PORT}/stream?token=test",
            "launched_external": False,
        }
    )
    session.get_media_stream_status = AsyncMock(
        return_value={
            "stream_id": "stream-1",
            "info_hash": "a" * 40,
            "file_index": 0,
            "file_name": "clip.mp4",
            "file_path": "C:/downloads/clip.mp4",
            "file_size": 10,
            "state": "ready",
            "stream_url": f"http://127.0.0.1:{STREAM_PORT}/stream?token=test",
            "bind_host": "127.0.0.1",
            "bind_port": STREAM_PORT,
            "token_expires_at": 123.0,
            "bytes_served": 64,
            "client_count": 1,
            "current_range_start": 0,
            "current_range_end": 63,
            "available_bytes": 64,
            "buffer_progress": 1.0,
            "last_error": None,
        }
    )
    session.stop_media_stream = AsyncMock(return_value=True)

    server = IPCServer(
        session_manager=session,
        api_key="test-api-key-12345",
        host="127.0.0.1",
        port=0,
        websocket_enabled=False,
    )
    await server.start()
    try:
        yield server
    finally:
        await server.stop()
        await session.stop()


@pytest.mark.asyncio
async def test_media_stream_ipc_routes(media_ipc_server) -> None:
    """Media start/status/stop endpoints should route through executor/session."""
    port = media_ipc_server.port
    headers = {API_KEY_HEADER: "test-api-key-12345"}
    base_url = f"http://127.0.0.1:{port}{API_BASE_PATH}"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/torrents/{'a' * 40}/media/start",
            json={"file_index": 0},
            headers=headers,
        ) as response:
            assert response.status == HTTP_OK
            payload = await response.json()
            assert payload["stream_id"] == "stream-1"

        async with session.get(
            f"{base_url}/torrents/{'a' * 40}/media/status",
            headers=headers,
        ) as response:
            assert response.status == HTTP_OK
            payload = await response.json()
            assert payload["state"] == "ready"
            assert payload["bind_port"] == STREAM_PORT

        async with session.post(
            f"{base_url}/media/stream-1/stop",
            headers=headers,
        ) as response:
            assert response.status == HTTP_OK
            payload = await response.json()
            assert payload["stopped"] is True
