"""Additional edge case tests for metrics helper functions.

Tests edge cases and error paths not covered in main test file.
"""

from __future__ import annotations

import asyncio

import pytest

from ccbt.monitoring import (
    MetricsCollector,
    get_metrics_collector,
    init_metrics,
    shutdown_metrics,
)


class TestHelperFunctionsEdgeCases:
    """Edge case tests for helper functions."""

    @pytest.mark.asyncio
    async def test_shutdown_when_singleton_none(self):
        """Test shutdown_metrics() when singleton is None."""
        import ccbt.monitoring as monitoring_module

        # Ensure singleton is None
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Should not raise
        await shutdown_metrics()

        # Singleton should still be None
        assert monitoring_module._GLOBAL_METRICS_COLLECTOR is None

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running_but_initialized(self, mock_config_enabled):
        """Test shutdown when metrics collector exists but is not running."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Create collector but don't start it
        collector = get_metrics_collector()
        assert collector.running is False

        # Shutdown should be no-op
        await shutdown_metrics()

        # Collector should still exist (singleton not reset)
        assert monitoring_module._GLOBAL_METRICS_COLLECTOR is not None

    @pytest.mark.asyncio
    async def test_shutdown_exception_handling(self, mock_config_enabled, monkeypatch):
        """Test shutdown_metrics() handles exceptions from stop()."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Start metrics
        mock_config_enabled.observability.enable_metrics = True
        metrics = await init_metrics()
        assert metrics is not None
        assert metrics.running is True

        # Patch stop() to raise exception
        original_stop = metrics.stop

        async def raise_error():
            raise RuntimeError("Stop failed")

        monkeypatch.setattr(metrics, "stop", raise_error)

        # Should not raise, but log warning
        await shutdown_metrics()

        # Metrics should still be running (stop failed)
        # But shutdown_metrics() should have handled it gracefully

        # Restore and properly stop
        monkeypatch.setattr(metrics, "stop", original_stop)
        await metrics.stop()

    @pytest.mark.asyncio
    async def test_init_get_config_exception(self, monkeypatch):
        """Test init_metrics() handles get_config() exceptions."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Patch get_config to raise
        from ccbt import config as config_module

        def raise_error():
            raise RuntimeError("Config access failed")

        monkeypatch.setattr(config_module, "get_config", raise_error)

        # Should return None, not raise
        result = await init_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_collector_start_exception(self, mock_config_enabled, monkeypatch):
        """Test init_metrics() handles collector.start() exceptions."""
        import ccbt.monitoring as monitoring_module

        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True

        # Get collector and patch start()
        collector = get_metrics_collector()

        async def raise_error():
            raise RuntimeError("Start failed")

        monkeypatch.setattr(collector, "start", raise_error)

        # Should return None, not raise
        result = await init_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_config_attribute_error(self, monkeypatch):
        """Test init_metrics() handles missing config attributes."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        from unittest.mock import Mock, PropertyMock

        # Create mock config that raises AttributeError when accessing observability
        mock_config = Mock(spec=[])  # Use spec=[] to prevent auto-creation of attributes
        # Use PropertyMock to raise AttributeError when accessing observability
        # Set it as a property on the class
        type(mock_config).observability = PropertyMock(side_effect=AttributeError("observability"))

        from ccbt import config as config_module

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        # Should return None when accessing config.observability fails
        result = await init_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_get_metrics_collector_calls(self):
        """Test that multiple calls to get_metrics_collector() return same instance."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        collector3 = get_metrics_collector()

        # All should be the same instance
        assert collector1 is collector2
        assert collector2 is collector3
        assert collector1 is collector3

    @pytest.mark.asyncio
    async def test_init_then_shutdown_then_init_again(self, mock_config_enabled):
        """Test metrics lifecycle: init -> shutdown -> init again."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True

        # First init
        metrics1 = await init_metrics()
        assert metrics1 is not None
        assert metrics1.running is True

        # Shutdown
        await shutdown_metrics()
        assert metrics1.running is False

        # Second init (should reuse singleton)
        metrics2 = await init_metrics()
        assert metrics2 is not None
        assert metrics2.running is True

        # Should be same instance (singleton)
        assert metrics1 is metrics2

        # Cleanup
        await shutdown_metrics()


@pytest.fixture
def mock_config_enabled(monkeypatch):
    """Mock config with metrics enabled."""
    from unittest.mock import Mock
    import ccbt.monitoring as monitoring_module

    # Reset metrics singleton before each test
    monitoring_module._GLOBAL_METRICS_COLLECTOR = None

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = True
    mock_observability.metrics_interval = 5.0
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config

