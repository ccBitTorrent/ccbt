"""Integration tests for AsyncSessionManager metrics lifecycle.

Tests metrics initialization, shutdown, and collection during session lifecycle.
"""

from __future__ import annotations

import asyncio
import pytest

from ccbt.session.session import AsyncSessionManager


class TestAsyncSessionManagerMetrics:
    """Tests for metrics integration in AsyncSessionManager."""

    @pytest.mark.asyncio
    async def test_metrics_initialized_in_start(self, mock_config_enabled):
        """Test that metrics are initialized in start() method."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        # Metrics should be None initially
        assert session.metrics is None

        # Start session
        await session.start()

        # Metrics should be initialized if enabled
        if mock_config_enabled.observability.enable_metrics:
            assert session.metrics is not None
        else:
            assert session.metrics is None

        # Cleanup
        await session.stop()

    @pytest.mark.asyncio
    async def test_metrics_shutdown_in_stop(self, mock_config_enabled):
        """Test that metrics are shut down in stop() method."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        if mock_config_enabled.observability.enable_metrics:
            assert session.metrics is not None
            assert session.metrics.running is True

        # Stop session
        await session.stop()

        # Metrics should be None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_not_started_when_disabled(self, mock_config_disabled):
        """Test metrics not started when disabled in config."""
        # Fixture already resets singleton, no need to call shutdown_metrics
        
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        # Metrics should be None when disabled
        assert session.metrics is None

        await session.stop()
        
        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_error_handling_on_init_failure(self, monkeypatch):
        """Test error handling when metrics initialization fails."""
        # Reset singleton via fixture pattern
        import ccbt.monitoring as monitoring_module
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None
        
        # Patch get_config to raise an error, which will cause init_metrics to fail
        from ccbt import config as config_module

        def raise_error():
            raise RuntimeError("Config error")

        monkeypatch.setattr(config_module, "get_config", raise_error)

        session = AsyncSessionManager()

        # Should not raise, but metrics should be None (caught in try/except)
        # init_metrics() handles exceptions internally and returns None
        await session.start()
        # The exception is caught in init_metrics() and returns None, so self.metrics is None
        assert session.metrics is None

        await session.stop()
        
        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_error_handling_on_shutdown_failure(
        self, mock_config_enabled, monkeypatch
    ):
        """Test error handling when metrics shutdown fails."""
        import ccbt.monitoring as monitoring_module

        # Patch shutdown_metrics to raise exception
        async def raise_error():
            raise Exception("Shutdown error")

        monkeypatch.setattr(monitoring_module, "shutdown_metrics", raise_error)

        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        if mock_config_enabled.observability.enable_metrics:
            assert session.metrics is not None

        # Should not raise on shutdown failure
        await session.stop()

        # Metrics should still be None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_collection_during_session_lifecycle(
        self, mock_config_enabled
    ):
        """Test metrics collection during full session lifecycle."""
        session = AsyncSessionManager()

        # Start session
        await session.start()

        if mock_config_enabled.observability.enable_metrics:
            assert session.metrics is not None
            assert session.metrics.running is True

            # Wait a bit for some metrics to be collected
            await asyncio.sleep(0.1)

            # Check that metrics are accessible
            assert session.metrics.get_all_metrics() is not None
            assert isinstance(session.metrics.get_all_metrics(), dict)

        # Stop session
        await session.stop()

        # Metrics should be None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_accessible_via_session_attribute(
        self, mock_config_enabled
    ):
        """Test that metrics are accessible via session.metrics attribute."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        if mock_config_enabled.observability.enable_metrics:
            # Metrics should be accessible
            metrics = session.metrics
            assert metrics is not None

            # Can call methods on metrics
            all_metrics = metrics.get_all_metrics()
            assert isinstance(all_metrics, dict)

            stats = metrics.get_metrics_statistics()
            assert isinstance(stats, dict)

        await session.stop()


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
    mock_observability.metrics_interval = 0.5  # Fast interval for testing
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability
    # Disable NAT to prevent blocking socket operations in tests
    mock_nat = Mock()
    mock_nat.auto_map_ports = False
    mock_config.nat = mock_nat

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
    # Disable NAT to prevent blocking socket operations in tests
    mock_nat = Mock()
    mock_nat.auto_map_ports = False
    mock_config.nat = mock_nat

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config

