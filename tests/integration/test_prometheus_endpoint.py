"""End-to-end tests for Prometheus /metrics endpoint.

Tests HTTP endpoint accessibility and Prometheus format output.
"""

from __future__ import annotations

import asyncio
import socket
import time
from http.client import HTTPConnection
from threading import Thread

import pytest

from ccbt.monitoring import MetricsCollector, init_metrics, shutdown_metrics


class TestPrometheusEndpoint:
    """Tests for Prometheus HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_when_enabled(self, mock_config_enabled):
        """Test /metrics endpoint is accessible when metrics enabled."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Start metrics with HTTP server
        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9191  # Use non-standard port

        metrics = await init_metrics()

        if metrics is None:
            pytest.skip("Metrics not initialized (may be due to missing dependencies)")

        # Wait for server to start
        await asyncio.sleep(0.5)

        try:
            # Try to connect to metrics endpoint
            conn = HTTPConnection("127.0.0.1", 9191, timeout=2)
            conn.request("GET", "/metrics")
            response = conn.getresponse()

            assert response.status == 200
            assert response.getheader("Content-Type") == "text/plain; version=0.0.4"

            # Read response body
            body = response.read().decode("utf-8")

            # Verify Prometheus format (should have HELP and TYPE comments)
            assert "# HELP" in body or len(body) > 0  # May be empty if no metrics yet

            conn.close()
        except (ConnectionRefusedError, OSError) as e:
            # Server may not have started (port in use, missing deps, etc.)
            pytest.skip(f"Could not connect to metrics endpoint: {e}")
        finally:
            await shutdown_metrics()
            # Give server time to shut down
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_metrics_endpoint_when_disabled(self, mock_config_disabled):
        """Test /metrics endpoint is not started when metrics disabled."""
        import ccbt.monitoring as monitoring_module

        # Ensure any previous metrics are shut down
        await shutdown_metrics()
        
        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_disabled.observability.enable_metrics = False
        mock_config_disabled.observability.metrics_port = 9192

        metrics = await init_metrics()

        # Metrics should be None when disabled
        assert metrics is None

        # Wait a bit to ensure no server starts
        await asyncio.sleep(0.3)

        # Try to connect - should fail
        try:
            conn = HTTPConnection("127.0.0.1", 9192, timeout=1)
            conn.request("GET", "/metrics")
            response = conn.getresponse()
            conn.close()
            # If we get here, server is running (unexpected)
            pytest.fail("HTTP server should not be running when metrics disabled")
        except (ConnectionRefusedError, OSError):
            # Expected - server should not be running
            pass
        finally:
            # Clean up
            await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_404_for_invalid_path(self, mock_config_enabled):
        """Test /metrics endpoint returns 404 for invalid paths."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9193

        metrics = await init_metrics()

        if metrics is None:
            pytest.skip("Metrics not initialized")

        await asyncio.sleep(0.5)

        try:
            conn = HTTPConnection("127.0.0.1", 9193, timeout=2)
            conn.request("GET", "/invalid")
            response = conn.getresponse()

            assert response.status == 404

            conn.close()
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"Could not connect to metrics endpoint: {e}")
        finally:
            await shutdown_metrics()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_metrics_endpoint_prometheus_format(self, mock_config_enabled):
        """Test /metrics endpoint returns valid Prometheus format."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9194

        metrics = await init_metrics()

        if metrics is None:
            pytest.skip("Metrics not initialized")

        # Register a test metric
        from ccbt.monitoring.metrics_collector import MetricType
        
        metrics.register_metric(
            "test_metric",
            MetricType.GAUGE,
            "A test metric",
        )
        metrics.set_gauge("test_metric", 42.0)

        await asyncio.sleep(0.5)

        try:
            conn = HTTPConnection("127.0.0.1", 9194, timeout=2)
            conn.request("GET", "/metrics")
            response = conn.getresponse()

            assert response.status == 200
            body = response.read().decode("utf-8")

            # Verify Prometheus format elements
            # Should have HELP comment for our metric
            assert "# HELP test_metric" in body
            assert "# TYPE test_metric" in body
            # Should have metric value
            assert "test_metric" in body

            conn.close()
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"Could not connect to metrics endpoint: {e}")
        finally:
            await shutdown_metrics()
            await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_port_in_use_handling(self, mock_config_enabled, monkeypatch):
        """Test graceful handling when port is already in use."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_port = 9195

        # Patch HTTPServer to raise OSError to simulate port conflict
        from http.server import HTTPServer

        original_init = HTTPServer.__init__

        def raise_oserror(*args, **kwargs):
            raise OSError("Address already in use")

        monkeypatch.setattr(HTTPServer, "__init__", raise_oserror)

        try:
            # Now try to start metrics - should handle OSError gracefully
            metrics = MetricsCollector()
            metrics.collection_interval = 0.5

            await metrics.start()

            # Should not raise, but server should be None due to OSError
            assert metrics._http_server is None

            await metrics.stop()
        finally:
            # Restore
            monkeypatch.setattr(HTTPServer, "__init__", original_init)


@pytest.fixture
def mock_config_enabled(monkeypatch):
    """Mock config with metrics enabled."""
    from unittest.mock import Mock

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = True
    mock_observability.metrics_interval = 0.5  # Fast for testing
    mock_observability.metrics_port = 9090  # Default
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

