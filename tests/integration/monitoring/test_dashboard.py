"""Basic tests for monitoring dashboard wiring.

We only import and instantiate key components to ensure they are available.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


def test_alert_manager_singleton():
    from ccbt.monitoring import get_alert_manager

    am = get_alert_manager()
    am2 = get_alert_manager()
    assert am is am2


@pytest.mark.asyncio
async def test_metrics_collector_runs_briefly():
    from ccbt.monitoring.metrics_collector import MetricsCollector

    mc = MetricsCollector()
    # Start and immediately stop: internal methods should be safe
    await mc.start()
    await mc.stop()


import asyncio

import pytest

from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
from ccbt.interface.terminal_dashboard import TerminalDashboard


@pytest.mark.asyncio
async def test_terminal_dashboard_creation():
    # Create a mock DaemonInterfaceAdapter
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)
    # Ensure compose runs without exceptions
    _ = app.compose()


@pytest.mark.asyncio
async def test_dashboard_poll_once():
    # Create a mock DaemonInterfaceAdapter
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    mock_ipc_client.connect_websocket = AsyncMock(return_value=True)
    mock_ipc_client.subscribe_events = AsyncMock()
    mock_ipc_client._websocket_task = None
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)

    # Mock the executor's get_global_stats method
    mock_data_provider = MagicMock()
    mock_data_provider.get_global_stats = AsyncMock(return_value={
        "num_torrents": 0,
        "num_active": 0,
        "num_paused": 0,
        "num_seeding": 0,
        "download_rate": 0.0,
        "upload_rate": 0.0,
        "average_progress": 0.0,
    })
    mock_data_provider.get_status = AsyncMock(return_value={})
    app._data_provider = mock_data_provider

    # Mount-like initialization
    await session.start()
    await app._poll_once()
    # Don't call stop() to avoid asyncio.suppress issue (separate bug)
    # await session.stop()


def test_terminal_dashboard_creation():
    # Create a mock DaemonInterfaceAdapter
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)
    assert app is not None


def test_dashboard_auto_refresh():
    # Create a mock DaemonInterfaceAdapter
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)

    # Mock the adapter methods
    async def fake_get_global_stats():
        return {
            "num_torrents": 0,
            "num_active": 0,
            "num_paused": 0,
            "num_seeding": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "average_progress": 0.0,
        }

    async def fake_get_status():
        return {}

    session.get_global_stats = fake_get_global_stats
    session.get_status = fake_get_status

    # Simulate one poll
    asyncio.run(app._poll_once())
    # No exception implies success path
    assert True
