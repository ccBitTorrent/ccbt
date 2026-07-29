"""Shared fixtures for daemon IPC tests."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import patch

import pytest_asyncio

from ccbt.session.session import AsyncSessionManager


async def _cancel_stray_tasks() -> None:
    """Cancel tasks left running after manager/server teardown."""
    current = asyncio.current_task()
    pending = [task for task in asyncio.all_tasks() if task is not current and not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _stop_with_timeout(coro, timeout: float = 30.0) -> None:
    """Stop IPC/session helpers without hanging CI teardown."""
    with contextlib.suppress(asyncio.TimeoutError, Exception):
        await asyncio.wait_for(coro, timeout=timeout)


@pytest_asyncio.fixture(scope="function")
async def mock_session_manager(monkeypatch):
    """Create a lightweight session manager for IPC tests."""
    monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
    monkeypatch.setenv("CCBT_ENABLE_DHT", "0")

    session = AsyncSessionManager()
    session.config.network.enable_tcp = False
    session.config.network.enable_utp = False
    session.config.nat.auto_map_ports = False
    session.config.discovery.enable_dht = False
    session.config.network.listen_port = 0

    session._make_nat_manager = lambda: None  # type: ignore[method-assign]
    session._make_tcp_server = lambda: None  # type: ignore[method-assign]

    with patch.object(session, "_make_dht_client", return_value=None):
        await session.start()
        try:
            yield session
        finally:
            await _stop_with_timeout(session.stop())
            await _cancel_stray_tasks()


@pytest_asyncio.fixture(scope="function")
async def ipc_server(mock_session_manager):
    """Create an IPC server bound to an ephemeral port."""
    from ccbt.daemon.ipc_server import IPCServer

    api_key = "test-api-key-12345"
    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,
    )
    await server.start()
    actual_port = server.port
    try:
        yield server, api_key, actual_port
    finally:
        await _stop_with_timeout(server.stop())
        await _cancel_stray_tasks()
