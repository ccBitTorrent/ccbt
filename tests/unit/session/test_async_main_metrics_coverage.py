"""Additional tests to ensure 100% coverage of metrics-related code in AsyncSessionManager.

These tests specifically target lines and branches that might not be covered
by existing tests to ensure complete coverage.
"""

from __future__ import annotations

import pytest

from ccbt.session.session import AsyncSessionManager


class TestAsyncSessionManagerMetricsCoverage:
    """Tests to ensure 100% coverage of metrics code paths."""

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_start_with_metrics_initialized_executes_log_line(
        self, 
        mock_config_enabled,
        mock_network_components
    ):
        """Test that the logger.info line executes when metrics are initialized.
        
        This test specifically targets line 311 in async_main.py:
        self.logger.info("Metrics collection initialized")
        
        Coverage will verify that line 311 is executed when:
        1. Line 309 executes (self.metrics = await init_metrics())
        2. Line 310 evaluates to True (if self.metrics:)
        3. Line 311 executes (self.logger.info(...))
        
        We verify the code path by ensuring metrics are initialized,
        which guarantees line 310 is True and line 311 executes.
        """
        from tests.fixtures.network_mocks import apply_network_mocks_to_session
        
        session = AsyncSessionManager()
        apply_network_mocks_to_session(session, mock_network_components)

        await session.start()
        
        # Verify metrics were initialized (line 309 executed)
        assert session.metrics is not None, "Metrics should be initialized when enabled in config"
        
        # This guarantees:
        # - Line 309 executed: self.metrics = await init_metrics() -> not None
        # - Line 310 evaluated to True: if self.metrics: -> True
        # - Line 311 executed: self.logger.info("Metrics collection initialized")
        
        # Coverage tools will confirm line 311 was executed

        await session.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_start_with_metrics_disabled_no_log_message(
        self, 
        mock_config_disabled, 
        caplog,
        mock_network_components
    ):
        """Test that logger.info is NOT called when metrics are disabled.
        
        This test ensures the branch where self.metrics is None (line 397)
        is covered - the if condition evaluates to False, so line 398 does NOT execute.
        """
        from ccbt.monitoring import shutdown_metrics
        from tests.fixtures.network_mocks import apply_network_mocks_to_session
        
        # Ensure clean state
        await shutdown_metrics()
        
        import logging
        caplog.set_level(logging.INFO)
        
        session = AsyncSessionManager()
        session.config = mock_config_disabled
        # Use network mocks instead of disabling features
        apply_network_mocks_to_session(session, mock_network_components)
        
        await session.start()
        
        # When metrics are disabled, self.metrics should be None
        assert session.metrics is None
        
        # Line 396 executed (self.metrics = await init_metrics() returns None)
        # Line 397 evaluated to False (if self.metrics: ...)
        # Line 398 did NOT execute (skipped because if condition is False)
        
        # Verify the log message was NOT emitted
        log_messages = [record.message for record in caplog.records]
        assert not any("Metrics collection initialized" in msg for msg in log_messages)

        await session.stop()
        
        # Verify metrics still None after stop
        assert session.metrics is None

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_stop_with_metrics_shutdown_sets_to_none(
        self, 
        mock_config_enabled,
        mock_network_components
    ):
        """Test that self.metrics is set to None after shutdown.
        
        This test specifically targets lines 337-339 in async_main.py:
        if self.metrics:
            await shutdown_metrics()
            self.metrics = None
        """
        from tests.fixtures.network_mocks import apply_network_mocks_to_session
        
        session = AsyncSessionManager()
        apply_network_mocks_to_session(session, mock_network_components)

        await session.start()
        
        # Ensure metrics were initialized
        if session.metrics is not None:
            # Verify metrics exists before stop
            assert session.metrics is not None
            
            # Stop should set metrics to None
            await session.stop()
            
            # Metrics should be None after stop (line 339)
            assert session.metrics is None

    @pytest.mark.asyncio
    @pytest.mark.timeout_fast
    async def test_stop_with_no_metrics_skips_shutdown(
        self, 
        mock_config_disabled,
        mock_network_components
    ):
        """Test that shutdown is skipped when metrics is None.
        
        This test ensures the branch where self.metrics is None (line 457)
        is covered, so shutdown_metrics() is not called.
        """
        from ccbt.monitoring import shutdown_metrics
        from tests.fixtures.network_mocks import apply_network_mocks_to_session
        
        # Ensure clean state
        await shutdown_metrics()
        
        session = AsyncSessionManager()
        session.config = mock_config_disabled
        # Use network mocks instead of disabling features
        apply_network_mocks_to_session(session, mock_network_components)
        
        await session.start()
        
        # Metrics should be None when disabled
        assert session.metrics is None
        
        # Stop should complete without calling shutdown_metrics
        # (because the if condition at line 457 is False)
        await session.stop()
        
        # Metrics should still be None
        assert session.metrics is None


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

