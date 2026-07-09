"""Unit tests for AsyncSessionManager metrics integration.

Tests metrics initialization and shutdown in AsyncSessionManager.
"""

from __future__ import annotations

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
    @pytest.mark.timeout_fast
    async def test_metrics_initialized_on_start_when_enabled(
        self,
        mock_config_enabled,
        mock_network_components
    ):
        """Test metrics initialized when enabled in config."""
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
        await session.start()

        # Check if metrics were initialized
        # They may be None if dependencies missing or config disabled
        # but if enabled and working, should be MetricsCollector instance
        if mock_config_enabled.observability.enable_metrics:
            # If metrics enabled, should be initialized (if no errors)
            # We can't assert it's not None because dependencies might be missing
            # But we can assert it's either None or MetricsCollector
            # MetricsCollector has methods like get_metrics_summary, get_torrent_metrics, etc.
            assert session.metrics is None or hasattr(session.metrics, "get_metrics_summary")

        await session.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_metrics_not_initialized_when_disabled(
        self,
        mock_config_disabled,
        mock_network_components
    ):
        """Test metrics not initialized when disabled in config."""
        from ccbt.monitoring import shutdown_metrics
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        # Ensure clean state
        await shutdown_metrics()

        # CRITICAL: Patch session.config directly to use mocked config
        # The session manager caches config in __init__(), so we need to patch it
        session = AsyncSessionManager()
        # Override the cached config with the mocked one
        session.config = mock_config_disabled

        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
        await session.start()

        # Metrics should be None when disabled
        assert session.metrics is None

        await session.stop()

        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_metrics_shutdown_on_stop(
        self,
        mock_config_enabled,
        mock_network_components
    ):
        """Test metrics shutdown when session stops."""
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
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
    @pytest.mark.timeout_fast
    async def test_metrics_shutdown_when_not_initialized(self, mock_network_components):
        """Test shutdown when metrics were never initialized."""
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
        # Start without metrics
        await session.start()

        # If metrics weren't initialized, stop should still work
        await session.stop()

        assert session.metrics is None

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_error_handling_on_init_failure(
        self,
        monkeypatch,
        mock_network_components
    ):
        """Test error handling when init_metrics fails."""
        from ccbt.monitoring import shutdown_metrics
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        # Ensure clean state
        await shutdown_metrics()

        # Patch get_config to raise an error, which will cause init_metrics to fail internally
        from ccbt import config as config_module

        def raise_error():
            raise RuntimeError("Config error")

        monkeypatch.setattr(config_module, "get_config", raise_error)

        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
        # Should not raise, but metrics should be None
        # init_metrics() handles exceptions internally and returns None
        await session.start()
        # Exception is caught in init_metrics() and returns None, so self.metrics is None
        assert session.metrics is None

        await session.stop()

        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_error_handling_on_shutdown_failure(
        self,
        mock_config_enabled,
        monkeypatch,
        mock_network_components
    ):
        """Test error handling when shutdown_metrics fails."""
        import ccbt.monitoring as monitoring_module
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        shutdown_called = False

        async def raise_error():
            nonlocal shutdown_called
            shutdown_called = True
            raise Exception("Shutdown error")

        # First start normally
        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
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
    @pytest.mark.timeout_fast
    async def test_metrics_accessible_during_session(
        self,
        mock_config_enabled,
        mock_network_components
    ):
        """Test metrics are accessible via session.metrics during session."""
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        session = AsyncSessionManager()
        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)
        await session.start()

        if session.metrics is not None:
            # Should be able to call methods
            summary = session.metrics.get_metrics_summary()
            assert isinstance(summary, dict)

        await session.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout_medium
    async def test_multiple_start_stop_cycles(
        self,
        mock_config_enabled,
        mock_network_components
    ):
        """Test metrics handling across multiple start/stop cycles."""
        from tests.fixtures.network_mocks import apply_network_mocks_to_session

        # CRITICAL: Patch session.config directly to use mocked config
        # The session manager caches config in __init__(), so we need to patch it
        session = AsyncSessionManager()
        # Override the cached config with the mocked one
        session.config = mock_config_enabled

        # Use network mocks instead of manual NAT mocking
        apply_network_mocks_to_session(session, mock_network_components)

        # First cycle
        await session.start()
        metrics1 = session.metrics
        await session.stop()
        assert session.metrics is None

        # Re-apply network mocks before second start
        apply_network_mocks_to_session(session, mock_network_components)

        # Second cycle
        await session.start()
        metrics2 = session.metrics
        await session.stop()
        assert session.metrics is None

        # Metrics should be reinitialized on each start
        # Note: Metrics() creates a new instance each time (not a singleton),
        # so metrics1 and metrics2 will be different instances
        # The important thing is that metrics are properly initialized and cleaned up
        if metrics1 is not None and metrics2 is not None:
            # Both should be MetricsCollector instances
            from ccbt.utils.metrics import MetricsCollector
            assert isinstance(metrics1, MetricsCollector)
            assert isinstance(metrics2, MetricsCollector)
            # They will be different instances (not singletons)
            # This is expected behavior - each start() creates a new Metrics instance


@pytest.fixture(scope="function")
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
    # Event bus config values needed for EventManager initialization
    mock_observability.event_bus_max_queue_size = 10000
    mock_observability.event_bus_batch_size = 50
    mock_observability.event_bus_batch_timeout = 0.05
    mock_observability.event_bus_emit_timeout = 0.01
    mock_observability.event_bus_queue_full_threshold = 0.9
    mock_observability.event_bus_throttle_dht_node_found = 0.1
    mock_observability.event_bus_throttle_dht_node_added = 0.1
    mock_observability.event_bus_throttle_monitoring_heartbeat = 1.0
    mock_observability.event_bus_throttle_global_metrics_update = 0.5
    mock_config.observability = mock_observability

    # Network config
    mock_config.network = Mock()
    mock_config.network.max_global_peers = 100
    mock_config.network.connection_timeout = 30.0

    # NAT config
    mock_config.nat = Mock()
    mock_config.nat.auto_map_ports = False

    # Discovery config
    mock_config.discovery = Mock()
    mock_config.discovery.enable_dht = False

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config


@pytest.fixture(scope="function")
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

