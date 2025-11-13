"""Additional tests to improve coverage for HTTP server edge cases.

Specifically targets missing coverage lines in metrics_collector.py.
"""

from __future__ import annotations

import pytest

from ccbt.monitoring.metrics_collector import MetricsCollector


class TestMetricsCollectorHTTPCoverage:
    """Tests to improve HTTP server code coverage."""

    @pytest.mark.asyncio
    async def test_oserror_with_config_port_access_failure(self, mock_config_enabled, monkeypatch):
        """Test coverage for lines 829-830: Exception handler when config.observability.metrics_port access fails.
        
        This tests the fallback to default port 9090 when accessing config.observability.metrics_port
        raises an exception within the OSError handler.
        """
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True

        # Patch HTTPServer to raise OSError
        from http.server import HTTPServer

        original_init = HTTPServer.__init__

        def raise_oserror(*args, **kwargs):
            raise OSError("Port in use")

        monkeypatch.setattr(HTTPServer, "__init__", raise_oserror)

        # Patch config.observability.metrics_port to raise when accessed in except block
        # We need to make accessing metrics_port raise an exception
        # Create a property that raises
        class ConfigWithRaise:
            def __init__(self, mock_obs):
                self.observability = mock_obs

        class ObsWithRaise:
            def __init__(self):
                self.enable_metrics = True
                self.metrics_interval = 5.0

            @property
            def metrics_port(self):
                raise AttributeError("Cannot access metrics_port")

        config_with_raise = ConfigWithRaise(ObsWithRaise())

        from ccbt import config as config_module

        original_get_config = config_module.get_config

        def get_config_with_raise():
            return config_with_raise

        monkeypatch.setattr(config_module, "get_config", get_config_with_raise)

        try:
            await metrics._start_prometheus_server()

            # Should handle gracefully with default port 9090 in fallback (line 830)
            assert metrics._http_server is None
        finally:
            # Restore
            monkeypatch.setattr(HTTPServer, "__init__", original_init)
            monkeypatch.setattr(config_module, "get_config", original_get_config)

    @pytest.mark.asyncio
    async def test_start_when_disabled_returns_early(self, mock_config_disabled):
        """Test that _start_prometheus_server() returns early when disabled (line 769)."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_disabled.observability.enable_metrics = False

        await metrics._start_prometheus_server()

        # Should return early, server should be None
        assert metrics._http_server is None

    @pytest.mark.asyncio
    async def test_start_when_prometheus_unavailable_returns_early(self, mock_config_enabled, monkeypatch):
        """Test that _start_prometheus_server() returns early when prometheus_client unavailable (line 774)."""
        metrics = MetricsCollector()
        metrics.collection_interval = 5.0

        mock_config_enabled.observability.enable_metrics = True

        # Patch HAS_PROMETHEUS_HTTP to False
        import ccbt.monitoring.metrics_collector as mc_module
        original_has = mc_module.HAS_PROMETHEUS_HTTP
        mc_module.HAS_PROMETHEUS_HTTP = False

        try:
            await metrics._start_prometheus_server()

            # Should return early, server should be None
            assert metrics._http_server is None
        finally:
            # Restore
            mc_module.HAS_PROMETHEUS_HTTP = original_has


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

