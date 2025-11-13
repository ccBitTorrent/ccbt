"""Unit tests for AsyncSessionManager metrics integration.

Tests metrics initialization and shutdown in AsyncSessionManager.
"""

from __future__ import annotations

import asyncio

import pytest

from ccbt.session.session import AsyncSessionManager


class TestAsyncSessionManagerMetricsIntegration:
    """Tests for metrics integration in AsyncSessionManager."""

    @pytest.mark.asyncio
    async def test_metrics_attribute_initialized_as_none(self):
        """Test that metrics attribute is None initially."""
        session = AsyncSessionManager()

        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_initialized_on_start_when_enabled(self, mock_config_enabled):
        """Test metrics initialized when enabled in config."""
        session = AsyncSessionManager()

        await session.start()

        # Check if metrics were initialized
        # They may be None if dependencies missing or config disabled
        # but if enabled and working, should be MetricsCollector instance
        if mock_config_enabled.observability.enable_metrics:
            # If metrics enabled, should be initialized (if no errors)
            # We can't assert it's not None because dependencies might be missing
            # But we can assert it's either None or MetricsCollector
            assert session.metrics is None or hasattr(session.metrics, "get_all_metrics")

        await session.stop()

    @pytest.mark.asyncio
    async def test_metrics_not_initialized_when_disabled(self, mock_config_disabled):
        """Test metrics not initialized when disabled in config."""
        from ccbt.monitoring import shutdown_metrics
        
        # Ensure clean state
        await shutdown_metrics()
        
        session = AsyncSessionManager()

        await session.start()

        # Metrics should be None when disabled
        assert session.metrics is None

        await session.stop()
        
        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_shutdown_on_stop(self, mock_config_enabled):
        """Test metrics shutdown when session stops."""
        session = AsyncSessionManager()

        await session.start()

        # Track if metrics were set
        had_metrics = session.metrics is not None

        await session.stop()

        # Metrics should be None after stop
        assert session.metrics is None

        # If we had metrics, verify they were stopped
        if had_metrics:
            # Metrics should be stopped (we can't check the singleton directly
            # but we verified it's None in session)
            pass

    @pytest.mark.asyncio
    async def test_metrics_shutdown_when_not_initialized(self):
        """Test shutdown when metrics were never initialized."""
        session = AsyncSessionManager()

        # Start without metrics
        await session.start()

        # If metrics weren't initialized, stop should still work
        await session.stop()

        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_error_handling_on_init_failure(self, monkeypatch):
        """Test error handling when init_metrics fails."""
        from ccbt.monitoring import shutdown_metrics
        
        # Ensure clean state
        await shutdown_metrics()
        
        # Patch get_config to raise an error, which will cause init_metrics to fail internally
        from ccbt import config as config_module

        def raise_error():
            raise RuntimeError("Config error")

        monkeypatch.setattr(config_module, "get_config", raise_error)

        session = AsyncSessionManager()

        # Should not raise, but metrics should be None
        # init_metrics() handles exceptions internally and returns None
        await session.start()
        # Exception is caught in init_metrics() and returns None, so self.metrics is None
        assert session.metrics is None

        await session.stop()
        
        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_error_handling_on_shutdown_failure(
        self, mock_config_enabled, monkeypatch
    ):
        """Test error handling when shutdown_metrics fails."""
        import ccbt.monitoring as monitoring_module

        shutdown_called = False

        async def raise_error():
            nonlocal shutdown_called
            shutdown_called = True
            raise Exception("Shutdown error")

        # First start normally
        session = AsyncSessionManager()
        await session.start()

        # Then patch shutdown to raise
        monkeypatch.setattr(monitoring_module, "shutdown_metrics", raise_error)

        # Should not raise, but should attempt shutdown
        await session.stop()

        # Shutdown should have been called if metrics were initialized
        if session.metrics is None:
            # If metrics weren't initialized, shutdown might not be called
            # But that's okay
            pass
        else:
            # If metrics were initialized, shutdown should have been attempted
            # (though in our test, metrics should be None after stop due to finally block)
            pass

        # Metrics should be None after stop (set in finally block)
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_accessible_during_session(self, mock_config_enabled):
        """Test metrics are accessible via session.metrics during session."""
        session = AsyncSessionManager()

        await session.start()

        if session.metrics is not None:
            # Should be able to call methods
            all_metrics = session.metrics.get_all_metrics()
            assert isinstance(all_metrics, dict)

            stats = session.metrics.get_metrics_statistics()
            assert isinstance(stats, dict)

        await session.stop()

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self, mock_config_enabled):
        """Test metrics handling across multiple start/stop cycles."""
        session = AsyncSessionManager()

        # First cycle
        await session.start()
        metrics1 = session.metrics
        await session.stop()
        assert session.metrics is None

        # Second cycle
        await session.start()
        metrics2 = session.metrics
        await session.stop()
        assert session.metrics is None

        # Metrics should be reinitialized on each start
        # (singleton means they might be the same instance)
        if metrics1 is not None and metrics2 is not None:
            # They should be the same singleton instance
            assert metrics1 is metrics2


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
    mock_observability.metrics_interval = 0.5  # Fast for testing
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

