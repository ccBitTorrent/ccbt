"""Basic tests for monitoring dashboard wiring.

We only import and instantiate key components to ensure they are available.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


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

from ccbt.interface.terminal_dashboard import TerminalDashboard
from ccbt.session.session import AsyncSessionManager


@pytest.mark.asyncio
async def test_terminal_dashboard_creation():
    session = AsyncSessionManager(".")
    app = TerminalDashboard(session, refresh_interval=0.5)
    # Ensure compose runs without exceptions
    _ = app.compose()


@pytest.mark.asyncio
async def test_dashboard_poll_once(monkeypatch):
    # Mock DHT client to avoid bootstrapping delays
    with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
        mock_dht = mock_dht_class.return_value
        mock_dht.start = AsyncMock()
        mock_dht.stop = AsyncMock()
        mock_dht.wait_for_bootstrap = AsyncMock(return_value=True)
        mock_dht.routing_table = MagicMock()
        mock_dht.routing_table.nodes = {}
        
        from ccbt.interface.terminal_dashboard import TerminalDashboard
        from ccbt.session.session import AsyncSessionManager
        
        session = AsyncSessionManager(".")
        app = TerminalDashboard(session, refresh_interval=0.5)

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

        monkeypatch.setattr(session, "get_global_stats", fake_get_global_stats)
        monkeypatch.setattr(session, "get_status", fake_get_status)

        # Mount-like initialization
        await session.start()
        await app._poll_once()
        await session.stop()


def test_terminal_dashboard_creation():
    session = AsyncSessionManager(".")
    app = TerminalDashboard(session, refresh_interval=0.5)
    assert app is not None


def test_dashboard_auto_refresh():
    session = AsyncSessionManager(".")
    app = TerminalDashboard(session, refresh_interval=0.5)

    # Simulate one poll
    asyncio.run(app._poll_once())
    # No exception implies success path
    assert True
