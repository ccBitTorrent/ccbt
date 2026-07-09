"""Contract tests for IPC shutdown endpoint semantics."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest
import pytest_asyncio

from ccbt.daemon.ipc_protocol import API_BASE_PATH, API_KEY_HEADER
from ccbt.daemon.ipc_server import IPCServer
from ccbt.session.session import AsyncSessionManager


@pytest_asyncio.fixture(scope="function")
async def mock_session_manager(monkeypatch):
    """Create lightweight session manager for IPC contract tests."""
    from unittest.mock import patch

    monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
    monkeypatch.setenv("CCBT_ENABLE_DHT", "0")

    session = AsyncSessionManager()
    session.config.network.enable_tcp = False
    session.config.nat.auto_map_ports = False
    session.config.discovery.enable_dht = False
    session._make_nat_manager = lambda: None  # type: ignore[method-assign]
    session._make_tcp_server = lambda: None  # type: ignore[method-assign]

    with patch.object(session, "_make_dht_client", return_value=None):
        await session.start()
        yield session
        await session.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_shutdown_contract_accepted_triggers_event(mock_session_manager):
    """Accepted shutdown request should trigger daemon shutdown event."""
    api_key = "test-api-key-12345"
    shutdown_event = asyncio.Event()

    async def shutdown_callback() -> None:
        shutdown_event.set()

    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,
        shutdown_callback=shutdown_callback,
        shutdown_event=shutdown_event,
    )
    await server.start()
    try:
        url = f"http://127.0.0.1:{server.port}{API_BASE_PATH}/shutdown"
        headers = {API_KEY_HEADER: api_key}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("accepted") is True
                assert data.get("status") == "shutting_down"

        await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
        assert shutdown_event.is_set()
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_shutdown_contract_rejected_without_bridge(mock_session_manager):
    """Shutdown request should be rejected when no bridge is configured."""
    api_key = "test-api-key-12345"
    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,
    )
    await server.start()
    try:
        url = f"http://127.0.0.1:{server.port}{API_BASE_PATH}/shutdown"
        headers = {API_KEY_HEADER: api_key}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                assert resp.status == 503
                data = await resp.json()
                assert data.get("accepted") is False
                assert data.get("status") == "rejected"
                assert "fallback_hint" in data
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_shutdown_contract_duplicate_is_idempotent(mock_session_manager):
    """Duplicate shutdown requests should stay accepted and idempotent."""
    api_key = "test-api-key-12345"
    shutdown_event = asyncio.Event()

    async def shutdown_callback() -> None:
        shutdown_event.set()

    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,
        shutdown_callback=shutdown_callback,
        shutdown_event=shutdown_event,
    )
    await server.start()
    try:
        url = f"http://127.0.0.1:{server.port}{API_BASE_PATH}/shutdown"
        headers = {API_KEY_HEADER: api_key}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                assert resp.status == 200
                first = await resp.json()
                assert first.get("accepted") is True

            await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)

            async with session.post(url, headers=headers) as resp:
                assert resp.status == 200
                second = await resp.json()
                assert second.get("accepted") is True
                assert second.get("status") == "already_shutting_down"
    finally:
        await server.stop()
