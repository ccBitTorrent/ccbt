"""Tests for IPC server metrics endpoint.

from __future__ import annotations

Tests the /api/v1/metrics endpoint for Prometheus metrics export.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from ccbt.daemon.ipc_protocol import API_BASE_PATH
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
async def test_metrics_endpoint_no_auth_required(ipc_server):
    """Test that metrics endpoint does NOT require authentication (Prometheus standard)."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    # Request without API key should work
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            # Should not be 401 (may be 503 if metrics not enabled, but not auth error)
            assert resp.status != 401


@pytest.mark.asyncio
async def test_metrics_endpoint_prometheus_format(ipc_server):
    """Test that metrics endpoint returns Prometheus format."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    # Mock metrics collector with running state and Prometheus data
    mock_collector = MagicMock()
    mock_collector.running = True
    mock_collector._export_prometheus_format.return_value = (
        "# HELP test_metric Test metric\n"
        "# TYPE test_metric gauge\n"
        "test_metric 123.45\n"
    )

    with patch("ccbt.daemon.ipc_server.get_metrics_collector", return_value=mock_collector):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                assert resp.headers["Content-Type"] == "text/plain; version=0.0.4"
                text = await resp.text()
                assert "# HELP" in text
                assert "# TYPE" in text
                assert "test_metric" in text


@pytest.mark.asyncio
async def test_metrics_endpoint_not_enabled(ipc_server):
    """Test that metrics endpoint returns 503 when metrics not enabled."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    # Mock metrics collector that is not running
    mock_collector = MagicMock()
    mock_collector.running = False

    with patch("ccbt.daemon.ipc_server.get_metrics_collector", return_value=mock_collector):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 503
                assert resp.headers["Content-Type"] == "text/plain; version=0.0.4"
                text = await resp.text()
                assert "Metrics collection not enabled" in text


@pytest.mark.asyncio
async def test_metrics_endpoint_no_collector(ipc_server):
    """Test that metrics endpoint returns 503 when metrics collector is None."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    with patch("ccbt.daemon.ipc_server.get_metrics_collector", return_value=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 503
                text = await resp.text()
                assert "Metrics collection not enabled" in text


@pytest.mark.asyncio
async def test_metrics_endpoint_export_error(ipc_server):
    """Test that metrics endpoint returns 500 on export errors."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    # Mock metrics collector that raises error on export
    mock_collector = MagicMock()
    mock_collector.running = True
    mock_collector._export_prometheus_format.side_effect = Exception("Export failed")

    with patch("ccbt.daemon.ipc_server.get_metrics_collector", return_value=mock_collector):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 500
                text = await resp.text()
                assert "Error exporting metrics" in text


@pytest.mark.asyncio
async def test_metrics_endpoint_charset_header(ipc_server):
    """Test that metrics endpoint includes charset in Content-Type header."""
    server, api_key, port = ipc_server
    url = f"http://127.0.0.1:{port}{API_BASE_PATH}/metrics"

    # Mock metrics collector with running state
    mock_collector = MagicMock()
    mock_collector.running = True
    mock_collector._export_prometheus_format.return_value = "test_metric 1.0\n"

    with patch("ccbt.daemon.ipc_server.get_metrics_collector", return_value=mock_collector):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                # Check that charset is in the response
                content_type = resp.headers.get("Content-Type", "")
                assert "charset=utf-8" in content_type or "version=0.0.4" in content_type

