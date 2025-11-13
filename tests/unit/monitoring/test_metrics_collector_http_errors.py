"""Unit tests for MetricsCollector HTTP server error handling.

Tests error paths and edge cases in HTTP server implementation.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from ccbt.monitoring.metrics_collector import MetricsCollector


class TestMetricsCollectorHTTPErrorHandling:
    """Tests for HTTP server error handling paths."""

    @pytest.mark.asyncio
    async def test_http_server_oserror_handling(self, mock_config_enabled, monkeypatch):
        """Test graceful handling of OSError when port is in use."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9300

        # Patch HTTPServer to raise OSError
        from http.server import HTTPServer

        original_init = HTTPServer.__init__

        def raise_oserror(*args, **kwargs):
            raise OSError("Address already in use")

        monkeypatch.setattr(HTTPServer, "__init__", raise_oserror)

        await metrics._start_prometheus_server()

        # Server should be None due to error
        assert metrics._http_server is None

        # Restore
        monkeypatch.setattr(HTTPServer, "__init__", original_init)

    @pytest.mark.asyncio
    async def test_http_server_generic_exception_handling(self, mock_config_enabled, monkeypatch):
        """Test graceful handling of generic exceptions in server startup."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9301

        # Patch HTTPServer to raise generic exception
        from http.server import HTTPServer

        original_init = HTTPServer.__init__

        def raise_error(*args, **kwargs):
            raise ValueError("Unexpected error")

        monkeypatch.setattr(HTTPServer, "__init__", raise_error)

        await metrics._start_prometheus_server()

        # Server should be None due to error
        assert metrics._http_server is None

        # Restore
        monkeypatch.setattr(HTTPServer, "__init__", original_init)

    @pytest.mark.asyncio
    async def test_http_server_stop_error_handling(self, mock_config_enabled, monkeypatch):
        """Test graceful handling of errors when stopping HTTP server."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9302

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        # Patch shutdown to raise exception
        
        original_shutdown = metrics._http_server.shutdown

        def raise_error():
            raise RuntimeError("Shutdown error")

        monkeypatch.setattr(metrics._http_server, "shutdown", raise_error)

        # Should not raise
        await metrics._stop_prometheus_server()

        # Server reference should still be cleared (or attempted)
        # The error is logged but doesn't raise

    @pytest.mark.asyncio
    async def test_http_handler_export_error(self, mock_config_enabled, monkeypatch):
        """Test HTTP handler error handling when _export_prometheus_format() fails."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9303

        # Patch _export_prometheus_format to raise
        original_export = metrics._export_prometheus_format

        def raise_error():
            raise RuntimeError("Export error")

        monkeypatch.setattr(metrics, "_export_prometheus_format", raise_error)

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        await asyncio.sleep(0.3)  # Wait for server to start

        # Try to connect and make request - should return 500
        try:
            from http.client import HTTPConnection

            conn = HTTPConnection("127.0.0.1", 9303, timeout=2)
            conn.request("GET", "/metrics")
            response = conn.getresponse()

            # Should return 500 due to export error
            assert response.status == 500

            body = response.read().decode("utf-8")
            assert "Error" in body

            conn.close()
        except (ConnectionRefusedError, OSError):
            pytest.skip("Could not connect to server")
        finally:
            await metrics._stop_prometheus_server()
            await asyncio.sleep(0.2)

        # Restore
        monkeypatch.setattr(metrics, "_export_prometheus_format", original_export)

    @pytest.mark.asyncio
    async def test_http_handler_404_for_invalid_path(self, mock_config_enabled):
        """Test HTTP handler returns 404 for invalid paths."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9304

        await metrics._start_prometheus_server()

        if metrics._http_server is None:
            pytest.skip("HTTP server not started")

        await asyncio.sleep(0.3)

        try:
            from http.client import HTTPConnection

            conn = HTTPConnection("127.0.0.1", 9304, timeout=2)
            conn.request("GET", "/invalid-path")
            response = conn.getresponse()

            assert response.status == 404

            conn.close()
        except (ConnectionRefusedError, OSError):
            pytest.skip("Could not connect to server")
        finally:
            await metrics._stop_prometheus_server()
            await asyncio.sleep(0.2)


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

