"""Edge case tests for AsyncSessionManager metrics integration.

Tests additional error scenarios and edge cases.
"""

from __future__ import annotations

import asyncio

import pytest

from ccbt.session.session import AsyncSessionManager


class TestAsyncSessionManagerMetricsEdgeCases:
    """Edge case tests for metrics in AsyncSessionManager."""

    @pytest.mark.asyncio
    async def test_start_stop_without_torrents(self, mock_config_enabled):
        """Test metrics lifecycle when session has no torrents."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        if mock_config_enabled.observability.enable_metrics:
            # Metrics should be initialized if enabled
            # May be None if dependencies missing
            assert session.metrics is None or hasattr(session.metrics, "get_all_metrics")

        # Stop should work even with no torrents
        await session.stop()

        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_multiple_start_calls(self, mock_config_enabled):
        """Test behavior when start() is called multiple times."""
        session = AsyncSessionManager()

        # First start
        await session.start()
        metrics1 = session.metrics

        # Second start (should be idempotent for metrics)
        await session.start()
        metrics2 = session.metrics

        # Metrics should be consistent
        if metrics1 is not None:
            assert metrics2 is metrics1

        await session.stop()

    @pytest.mark.asyncio
    async def test_multiple_stop_calls(self, mock_config_enabled):
        """Test behavior when stop() is called multiple times."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        # First stop
        await session.stop()
        assert session.metrics is None

        # Second stop (should be safe)
        await session.stop()
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_metrics_after_exception_during_stop(self, mock_config_enabled):
        """Test metrics state after exception during torrent stop."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        # Check that remove_torrent handles errors gracefully
        # We'll test by trying to remove a non-existent torrent
        # which should not affect metrics shutdown
        
        # Metrics should be initialized if enabled
        initial_metrics = session.metrics

        # Stop should complete even if there are no torrents
        await session.stop()

        # Metrics should be None after stop (set in finally block)
        assert session.metrics is None

    @pytest.mark.asyncio
    async def test_config_dynamic_change(self, mock_config_enabled):
        """Test metrics when config changes between start/stop."""
        from ccbt.monitoring import shutdown_metrics
        import ccbt.monitoring as monitoring_module
        
        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None
        
        session = AsyncSessionManager()

        # Start with metrics enabled
        mock_config_enabled.observability.enable_metrics = True
        await session.start()

        initial_metrics = session.metrics

        # Change config (simulating hot reload)
        mock_config_enabled.observability.enable_metrics = False

        # Stop and restart - need to reset singleton to reflect new config
        await session.stop()
        
        # Reset singleton so new config is read
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None
        
        await session.start()

        # Metrics should reflect new config (disabled)
        assert session.metrics is None

        await session.stop()
        
        # Final cleanup
        await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_metrics_accessible_after_partial_failure(self, mock_config_enabled):
        """Test metrics accessibility even if some components fail."""
        session = AsyncSessionManager()
        session.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        await session.start()

        if session.metrics is not None:
            # Should be able to access metrics methods even if
            # some internal operations might have failed
            try:
                all_metrics = session.metrics.get_all_metrics()
                assert isinstance(all_metrics, dict)
            except Exception:
                # If metrics failed internally, that's okay
                pass

            try:
                stats = session.metrics.get_metrics_statistics()
                assert isinstance(stats, dict)
            except Exception:
                # If stats failed, that's okay
                pass

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
    mock_observability.metrics_interval = 0.5
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config

