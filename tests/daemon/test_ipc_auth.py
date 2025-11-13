"""Tests for IPC server authentication.

from __future__ import annotations

Tests mandatory authentication on all IPC endpoints.
"""

from __future__ import annotations

import pytest

import aiohttp

from ccbt.daemon.ipc_protocol import API_BASE_PATH, API_KEY_HEADER
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
    )
    await server.start()
    # Get actual port
    actual_port = server.port
    yield server, api_key, actual_port
    await server.stop()


@pytest.mark.asyncio
async def test_status_endpoint_requires_auth(ipc_server):
    """Test that status endpoint requires authentication."""
    server, api_key, port = ipc_server

    # Request without API key
    async with aiohttp.ClientSession() as session:
        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/status"
        async with session.get(url) as resp:
            assert resp.status == 401
            data = await resp.json()
            assert data["error"] == "Unauthorized"
            assert data["code"] == "AUTH_REQUIRED"

    # Request with invalid API key
    async with aiohttp.ClientSession() as session:
        headers = {API_KEY_HEADER: "invalid-key"}
        async with session.get(url, headers=headers) as resp:
            assert resp.status == 401

    # Request with valid API key
    async with aiohttp.ClientSession() as session:
        headers = {API_KEY_HEADER: api_key}
        async with session.get(url, headers=headers) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "status" in data
            assert "pid" in data


@pytest.mark.asyncio
async def test_torrent_endpoints_require_auth(ipc_server):
    """Test that torrent management endpoints require authentication."""
    server, api_key, port = ipc_server
    base_url = f"http://127.0.0.1:{port}{API_BASE_PATH}"

    endpoints = [
        ("GET", f"{base_url}/torrents"),
        ("POST", f"{base_url}/torrents/add"),
        ("GET", f"{base_url}/torrents/abc123"),
        ("DELETE", f"{base_url}/torrents/abc123"),
        ("POST", f"{base_url}/torrents/abc123/pause"),
        ("POST", f"{base_url}/torrents/abc123/resume"),
    ]

    async with aiohttp.ClientSession() as session:
        for method, url in endpoints:
            # Without API key
            if method == "GET":
                async with session.get(url) as resp:
                    assert resp.status == 401
            elif method == "POST":
                async with session.post(url, json={}) as resp:
                    assert resp.status == 401
            elif method == "DELETE":
                async with session.delete(url) as resp:
                    assert resp.status == 401

            # With invalid API key
            headers = {API_KEY_HEADER: "invalid-key"}
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    assert resp.status == 401
            elif method == "POST":
                async with session.post(url, json={}, headers=headers) as resp:
                    assert resp.status == 401
            elif method == "DELETE":
                async with session.delete(url, headers=headers) as resp:
                    assert resp.status == 401


@pytest.mark.asyncio
async def test_config_endpoints_require_auth(ipc_server):
    """Test that config endpoints require authentication."""
    server, api_key, port = ipc_server
    base_url = f"http://127.0.0.1:{port}{API_BASE_PATH}"

    async with aiohttp.ClientSession() as session:
        # GET /config without auth
        async with session.get(f"{base_url}/config") as resp:
            assert resp.status == 401

        # PUT /config without auth
        async with session.put(f"{base_url}/config", json={}) as resp:
            assert resp.status == 401

        # With valid API key
        headers = {API_KEY_HEADER: api_key}
        async with session.get(f"{base_url}/config", headers=headers) as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_shutdown_endpoint_requires_auth(ipc_server):
    """Test that shutdown endpoint requires authentication."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/shutdown"

    async with aiohttp.ClientSession() as session:
        # Without API key
        async with session.post(url) as resp:
            assert resp.status == 401

        # With valid API key
        headers = {API_KEY_HEADER: api_key}
        async with session.post(url, headers=headers) as resp:
            assert resp.status == 200

