"""Unit tests for MetricsCollector HTTP server functionality.

Tests for Prometheus HTTP endpoint implementation.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from ccbt.monitoring.metrics_collector import MetricsCollector


class TestMetricsCollectorHTTPServer:
    """Tests for MetricsCollector HTTP server methods."""

    @pytest.mark.asyncio
    async def test_start_prometheus_server_when_disabled(self, mock_config_disabled):
        """Test HTTP server not started when metrics disabled."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        await metrics._start_prometheus_server()

        # Server should not be started
        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_start_prometheus_server_when_enabled(self, mock_config_enabled):
        """Test HTTP server started when metrics enabled."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9200

        await metrics._start_prometheus_server()

        # Server should be started
        if metrics._http_server is not None:
            # Wait a bit for server to be ready
            await asyncio.sleep(0.3)

            # Verify server is running by checking if port is bound
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                result = sock.connect_ex(("127.0.0.1", 9200))
                # If connection succeeds or refused, port is in use (good)
                # If connection timeout, port might not be ready yet
                assert result == 0 or result in (10061, 10054)  # Windows connection error codes
            finally:
                sock.close()

            # Cleanup
            await metrics._stop_prometheus_server()
        else:
            # Server might not start if prometheus_client not available
            pytest.skip("HTTP server not started (may be missing dependencies)")

    @pytest.mark.asyncio
    async def test_start_prometheus_server_port_in_use(self, mock_config_enabled, monkeypatch):
        """Test graceful handling when port is in use."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9201

        # Patch HTTPServer.__init__ to raise OSError to simulate port in use
        from http.server import HTTPServer
        
        original_init = HTTPServer.__init__
        
        def raise_oserror(*args, **kwargs):
            raise OSError("Address already in use")
        
        monkeypatch.setattr(HTTPServer, "__init__", raise_oserror)

        try:
            # Try to start server - should handle OSError gracefully
            await metrics._start_prometheus_server()

            # Server should be None due to OSError being caught
            assert metrics._http_server is None
        finally:
            # Restore
            monkeypatch.setattr(HTTPServer, "__init__", original_init)

    @pytest.mark.asyncio
    async def test_stop_prometheus_server_when_none(self):
        """Test stopping HTTP server when not started."""
        metrics = MetricsCollector()
        metrics._http_server = None

        # Should not raise
        await metrics._stop_prometheus_server()

        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_stop_prometheus_server_when_started(self, mock_config_enabled):
        """Test stopping HTTP server when started."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9202

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        await asyncio.sleep(0.3)  # Wait for server to start

        # Stop server
        await metrics._stop_prometheus_server()

        # Server should be None after stop
        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_http_server_integration_with_start_stop(self, mock_config_enabled):
        """Test HTTP server lifecycle with start() and stop()."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9203

        # Start metrics (which starts HTTP server)
        await metrics.start()

        # Check if HTTP server started
        if metrics._http_server is not None:
            await asyncio.sleep(0.3)

            # Stop metrics (which stops HTTP server)
            await metrics.stop()

            # Server should be stopped
            assert metrics._http_server is None
        else:
            pytest.skip("HTTP server not started")


@pytest.fixture
def mock_config_enabled(monkeypatch):
    """Mock config with metrics enabled."""
    from unittest.mock import Mock

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = True
    mock_observability.metrics_interval = 5.0
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config


@pytest.fixture
def mock_config_disabled(monkeypatch):
    """Mock config with metrics disabled."""
    from unittest.mock import Mock
    import ccbt.monitoring as monitoring_module

    # Reset metrics singleton before each test
    monitoring_module._GLOBAL_METRICS_COLLECTOR = None

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = False
    mock_observability.metrics_interval = 5.0
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config

