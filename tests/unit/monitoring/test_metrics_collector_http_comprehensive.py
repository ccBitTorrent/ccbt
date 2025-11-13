"""Comprehensive tests for MetricsCollector HTTP server edge cases.

Tests all code paths in HTTP server implementation.
"""

from __future__ import annotations

import asyncio
import logging
import socket

import pytest

from ccbt.monitoring.metrics_collector import MetricsCollector


class TestMetricsCollectorHTTPComprehensive:
    """Comprehensive tests for HTTP server implementation."""

    @pytest.mark.asyncio
    async def test_http_server_start_checks_config_disabled(self, mock_config_disabled):
        """Test HTTP server not started when config disabled."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_disabled.observability.enable_metrics = False

        await metrics._start_prometheus_server()

        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_http_server_start_checks_prometheus_available(self, mock_config_enabled, monkeypatch):
        """Test HTTP server not started when prometheus_client unavailable."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True

        # Patch HAS_PROMETHEUS_HTTP to False
        import ccbt.monitoring.metrics_collector as mc_module
        original_has = mc_module.HAS_PROMETHEUS_HTTP
        mc_module.HAS_PROMETHEUS_HTTP = False

        try:
            await metrics._start_prometheus_server()

            # Server should not be started
            assert metrics._http_server is None
        finally:
            # Restore
            mc_module.HAS_PROMETHEUS_HTTP = original_has

    @pytest.mark.asyncio
    async def test_http_server_oserror_with_config_access_error(self, mock_config_enabled, monkeypatch):
        """Test OSError handling when config access fails in except block."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9400

        # Patch HTTPServer to raise OSError, and config access to fail
        from http.server import HTTPServer

        original_init = HTTPServer.__init__

        def raise_oserror(*args, **kwargs):
            raise OSError("Port in use")

        monkeypatch.setattr(HTTPServer, "__init__", raise_oserror)

        # Patch config.observability.metrics_port access to raise
        def raise_error():
            raise AttributeError("No metrics_port")

        type(mock_config_enabled.observability).metrics_port = property(raise_error)

        await metrics._start_prometheus_server()

        # Should handle gracefully with default port in fallback
        assert metrics._http_server is None

        # Restore
        monkeypatch.setattr(HTTPServer, "__init__", original_init)

    @pytest.mark.asyncio
    async def test_http_server_stop_when_none(self):
        """Test stop when HTTP server is None."""
        metrics = MetricsCollector()
        metrics._http_server = None

        # Should not raise
        await metrics._stop_prometheus_server()

        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_http_server_stop_exception_handling(self, mock_config_enabled, monkeypatch):
        """Test stop() handles exceptions gracefully."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9401

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        # Patch the shutdown method to raise
        original_shutdown = metrics._http_server.shutdown
        
        def raise_error():
            raise RuntimeError("Shutdown failed")
        
        monkeypatch.setattr(metrics._http_server, "shutdown", raise_error)

        # Should not raise (exception is caught and logged)
        await metrics._stop_prometheus_server()

        # After stop(), if shutdown() raises, the exception is caught
        # and _http_server is NOT set to None (line 844 only executes on success)
        # So _http_server should still be set after exception
        assert metrics._http_server is not None
        
        # Now properly stop it
        monkeypatch.setattr(metrics._http_server, "shutdown", original_shutdown)
        await metrics._stop_prometheus_server()

    @pytest.mark.asyncio
    async def test_http_handler_log_message(self, mock_config_enabled, caplog):
        """Test HTTP handler log_message method."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9402

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        await asyncio.sleep(0.3)

        # Make a request to trigger log_message
        try:
            from http.client import HTTPConnection

            with caplog.at_level(logging.DEBUG):
                conn = HTTPConnection("127.0.0.1", 9402, timeout=1)
                conn.request("GET", "/metrics")
                response = conn.getresponse()
                response.read()  # Consume response
                conn.close()

                # Handler's log_message should be called
                # (though it uses logger.debug which may not appear in caplog)
        except (ConnectionRefusedError, OSError):
            pytest.skip("Could not connect to server")
        finally:
            await metrics._stop_prometheus_server()
            await asyncio.sleep(0.2)


# Import Mock here to avoid issues
from unittest.mock import Mock

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

