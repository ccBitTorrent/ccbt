"""Unit tests for metrics helper functions.

Tests for get_metrics_collector(), init_metrics(), and shutdown_metrics()
from ccbt.monitoring module.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.monitoring import (
    MetricsCollector,
    get_metrics_collector,
    init_metrics,
    shutdown_metrics,
)


class TestGetMetricsCollector:
    """Tests for get_metrics_collector() singleton function."""

    def test_singleton_pattern(self):
        """Test that get_metrics_collector() returns same instance."""
        # Reset singleton by importing the module-level variable
        import ccbt.monitoring as monitoring_module

        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2
        assert isinstance(collector1, MetricsCollector)

    def test_creates_new_instance_if_none(self):
        """Test that new instance is created if singleton is None."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        collector = get_metrics_collector()
        assert collector is not None
        assert isinstance(collector, MetricsCollector)

    def test_set_session(self):
        """Test MetricsCollector.set_session method."""
        collector = MetricsCollector()
        mock_session = MagicMock()
        
        collector.set_session(mock_session)
        
        assert collector._session == mock_session

    @pytest.mark.asyncio
    async def test_collect_performance_metrics_with_session(self):
        """Test _collect_performance_metrics with session set."""
        collector = MetricsCollector()
        mock_session = MagicMock()
        
        # Mock DHT client - get_stats is not async, it's a property or regular method
        mock_dht_client = MagicMock()
        # get_stats returns a dict with routing_table as a dict (not an object)
        mock_dht_client.get_stats = Mock(return_value={
            "routing_table": {
                "total_nodes": 150,
            },
            "query_statistics": {
                "queries_sent": 200,
                "queries_received": 180,
                "queries_successful": 180,
            },
        })
        mock_session.dht_client = mock_dht_client
        
        # Mock queue manager - test with queued entries to cover wait_times path
        mock_queue_manager = MagicMock()
        import time
        current_time = time.time()
        mock_queue_manager.get_queue_status = AsyncMock(return_value={
            "statistics": {
                "queued": 5,
                "by_priority": {"high": 2, "normal": 3},
            },
            "entries": [
                {"status": "queued", "added_time": current_time - 100},  # 100 seconds ago
                {"status": "queued", "added_time": current_time - 200},  # 200 seconds ago
            ],
        })
        mock_session.queue_manager = mock_queue_manager
        
        # Mock tracker service - get_tracker_stats is async
        mock_tracker_service = MagicMock()
        # The code expects "success_rate" (not "announce_success_rate") and multiplies by 100
        # So we provide 0.955 which will become 95.5
        mock_tracker_service.get_tracker_stats = AsyncMock(return_value={
            "success_rate": 0.955,  # Will be multiplied by 100 to get 95.5
            "scrape_success_rate": 0.98,  # Will be multiplied by 100 to get 98.0
            "average_response_time": 0.5,
        })
        # Mock trackers dict for error count
        mock_tracker_conn = MagicMock()
        mock_tracker_conn.failure_count = 2
        mock_tracker_service.trackers = {"tracker1": mock_tracker_conn}
        mock_session.tracker_service = mock_tracker_service
        
        collector.set_session(mock_session)
        
        # Mock disk I/O manager with write_queue to test queue depth path
        with patch("ccbt.storage.disk_io_init.get_disk_io_manager") as mock_get_disk_io:
            mock_disk_io = MagicMock()
            mock_disk_io._running = True
            mock_disk_io._cache_stats_start_time = time.time() - 10  # 10 seconds ago
            mock_disk_io.stats = {"bytes_written": 1024 * 1024 * 100}
            mock_disk_io.get_cache_stats = MagicMock(return_value={"cache_bytes_served": 1024 * 1024 * 50})
            # Mock write_queue for queue depth
            from queue import Queue
            mock_queue = Queue()
            mock_queue.put(1)  # Add item to queue
            mock_queue.put(2)
            mock_disk_io.write_queue = mock_queue
            mock_get_disk_io.return_value = mock_disk_io
            
            # Call _collect_performance_metrics
            await collector._collect_performance_metrics()
            
            # Verify metrics were collected
            assert collector.performance_data["dht_nodes_discovered"] == 150
            assert collector.performance_data["dht_queries_sent"] == 200
            assert collector.performance_data["dht_queries_received"] == 180
            assert collector.performance_data["queue_length"] == 5
            assert collector.performance_data["queue_wait_time"] > 0  # Should be calculated from wait_times
            assert collector.performance_data["tracker_announce_success_rate"] == 95.5
            assert collector.performance_data["disk_queue_depth"] == 2  # Queue has 2 items

    @pytest.mark.asyncio
    async def test_collect_performance_metrics_queue_no_wait_times(self):
        """Test _collect_performance_metrics with queue manager but no queued entries."""
        collector = MetricsCollector()
        mock_session = MagicMock()
        
        # Mock queue manager with no queued entries
        mock_queue_manager = MagicMock()
        mock_queue_manager.get_queue_status = AsyncMock(return_value={
            "statistics": {
                "queued": 0,
                "by_priority": {},
            },
            "entries": [],  # No queued entries
        })
        mock_session.queue_manager = mock_queue_manager
        
        collector.set_session(mock_session)
        
        await collector._collect_performance_metrics()
        
        # queue_wait_time should be 0.0 when no wait_times
        assert collector.performance_data["queue_wait_time"] == 0.0

    @pytest.mark.asyncio
    async def test_collect_custom_metrics(self):
        """Test _collect_custom_metrics with registered collectors."""
        collector = MetricsCollector()
        
        # Register a sync collector
        sync_collector = Mock(return_value=42)
        collector.register_custom_collector("sync_metric", sync_collector)
        
        # Register an async collector
        async def async_collector():
            return 100
        collector.register_custom_collector("async_metric", async_collector)
        
        # Register a collector that raises an exception
        def failing_collector():
            raise ValueError("Test error")
        collector.register_custom_collector("failing_metric", failing_collector)
        
        # Call _collect_custom_metrics
        await collector._collect_custom_metrics()
        
        # Verify metrics were set
        assert collector.get_metric("custom_sync_metric") is not None
        assert collector.get_metric("custom_async_metric") is not None
        # Failing collector should not crash, but metric may not be set

    def test_record_histogram(self):
        """Test record_histogram method."""
        collector = MetricsCollector()
        
        # Record histogram values
        collector.record_histogram("test_histogram", 10.0)
        collector.record_histogram("test_histogram", 20.0)
        collector.record_histogram("test_histogram", 30.0)
        
        # Verify metric was created
        metric = collector.get_metric("test_histogram")
        assert metric is not None
        assert metric.metric_type.value == "histogram"
        assert len(metric.values) == 3

    def test_add_alert_rule(self):
        """Test add_alert_rule method."""
        collector = MetricsCollector()
        
        collector.add_alert_rule(
            "cpu_high",
            "system_cpu_usage",
            "value > 90",
            "critical",
            "CPU usage is too high"
        )
        
        assert "cpu_high" in collector.alert_rules
        rule = collector.alert_rules["cpu_high"]
        assert rule.metric_name == "system_cpu_usage"
        assert rule.condition == "value > 90"
        assert rule.severity == "critical"

    def test_get_metric_value_aggregations(self):
        """Test get_metric_value with different aggregation types."""
        from ccbt.monitoring.metrics_collector import AggregationType
        
        collector = MetricsCollector()
        
        # Record some values
        collector.record_metric("test_metric", 10.0)
        collector.record_metric("test_metric", 20.0)
        collector.record_metric("test_metric", 30.0)
        
        # Test different aggregation types
        assert collector.get_metric_value("test_metric", AggregationType.SUM) == 60.0
        assert collector.get_metric_value("test_metric", AggregationType.AVG) == 20.0
        assert collector.get_metric_value("test_metric", AggregationType.MIN) == 10.0
        assert collector.get_metric_value("test_metric", AggregationType.MAX) == 30.0
        assert collector.get_metric_value("test_metric", AggregationType.COUNT) == 3

    def test_get_metric_value_no_values(self):
        """Test get_metric_value when metric has no values."""
        from ccbt.monitoring.metrics_collector import MetricType
        
        collector = MetricsCollector()
        
        # Register a metric but don't record any values
        collector.register_metric("empty_metric", MetricType.GAUGE, "Empty metric")
        
        # Should return None when no values
        assert collector.get_metric_value("empty_metric") is None

    def test_get_all_metrics(self):
        """Test get_all_metrics method."""
        collector = MetricsCollector()
        
        # Record some metrics
        collector.record_metric("metric1", 10.0)
        collector.record_metric("metric2", 20.0)
        
        all_metrics = collector.get_all_metrics()
        
        assert "metric1" in all_metrics
        assert "metric2" in all_metrics
        assert all_metrics["metric1"]["current_value"] == 10.0
        assert all_metrics["metric2"]["current_value"] == 20.0

    def test_export_metrics_prometheus(self):
        """Test export_metrics with prometheus format."""
        from ccbt.monitoring.metrics_collector import MetricLabel
        
        collector = MetricsCollector()
        
        # Record a metric with MetricLabel objects
        collector.record_metric("test_metric", 42.0, labels=[MetricLabel(name="label1", value="value1")])
        
        # Export in prometheus format
        prometheus_output = collector.export_metrics("prometheus")
        
        assert "test_metric" in prometheus_output
        assert "42.0" in prometheus_output
        assert "label1" in prometheus_output
        assert "value1" in prometheus_output

    def test_cleanup_old_metrics(self):
        """Test cleanup_old_metrics method."""
        import time
        
        collector = MetricsCollector()
        
        # Record a metric with old timestamp
        old_time = time.time() - 4000  # 4000 seconds ago
        collector.record_metric("old_metric", 10.0)
        # Manually set old timestamp
        if collector.metrics["old_metric"].values:
            collector.metrics["old_metric"].values[0].timestamp = old_time
        
        # Record a metric with recent timestamp
        collector.record_metric("recent_metric", 20.0)
        
        # Cleanup metrics older than 3600 seconds
        collector.cleanup_old_metrics(max_age_seconds=3600)
        
        # Old metric should be removed, recent should remain
        old_metric = collector.get_metric("old_metric")
        recent_metric = collector.get_metric("recent_metric")
        
        assert old_metric is None or len(old_metric.values) == 0
        assert recent_metric is not None and len(recent_metric.values) > 0

    def test_unregister_custom_collector(self):
        """Test unregister_custom_collector method."""
        collector = MetricsCollector()
        
        def test_collector():
            return 42
        
        collector.register_custom_collector("test", test_collector)
        assert "test" in collector.collectors
        
        collector.unregister_custom_collector("test")
        assert "test" not in collector.collectors

    def test_evaluate_condition(self):
        """Test _evaluate_condition method."""
        collector = MetricsCollector()
        
        # Test various conditions
        assert collector._evaluate_condition("value > 10", 20.0) is True
        assert collector._evaluate_condition("value > 10", 5.0) is False
        assert collector._evaluate_condition("value < 10", 5.0) is True
        assert collector._evaluate_condition("value == 10", 10.0) is True
        assert collector._evaluate_condition("value != 10", 20.0) is True
        
        # Test invalid condition (should return False)
        assert collector._evaluate_condition("invalid syntax", 10.0) is False
        
        # Test edge cases in _evaluate_condition
        # Test with arithmetic operations
        assert collector._evaluate_condition("value + 5 > 10", 6.0) is True  # 6 + 5 = 11 > 10
        assert collector._evaluate_condition("value - 5 < 10", 14.0) is True  # 14 - 5 = 9 < 10
        assert collector._evaluate_condition("value * 2 == 20", 10.0) is True  # 10 * 2 = 20
        assert collector._evaluate_condition("value / 2 == 5", 10.0) is True  # 10 / 2 = 5
        
        # Test with unary operations
        assert collector._evaluate_condition("-value < 0", 10.0) is True  # -10 < 0
        assert collector._evaluate_condition("+value > 0", 10.0) is True  # +10 > 0
        
        # Test with multiple comparisons
        assert collector._evaluate_condition("value > 5 and value < 15", 10.0) is False  # "and" not supported, should return False
        
        # Test invalid node types (should return False)
        assert collector._evaluate_condition("invalid", 10.0) is False

    def test_export_prometheus_format(self):
        """Test _export_prometheus_format method."""
        from ccbt.monitoring.metrics_collector import MetricLabel
        
        collector = MetricsCollector()
        
        # Record metrics with MetricLabel objects
        collector.record_metric("test_metric", 42.0, labels=[MetricLabel(name="label1", value="value1"), MetricLabel(name="label2", value="value2")])
        collector.record_metric("another_metric", 100.0)
        
        prometheus_output = collector._export_prometheus_format()
        
        # Check for Prometheus format elements
        assert "# HELP" in prometheus_output
        assert "# TYPE" in prometheus_output
        assert "test_metric" in prometheus_output
        assert "another_metric" in prometheus_output
        assert "label1" in prometheus_output
        assert "value1" in prometheus_output

    def test_alert_evaluation_with_cooldown(self):
        """Test alert evaluation with cooldown period."""
        import time
        import asyncio
        from unittest.mock import patch, MagicMock
        
        collector = MetricsCollector()
        
        # Mock asyncio.create_task to avoid event loop issues
        mock_task = MagicMock()
        with patch("ccbt.monitoring.metrics_collector.asyncio.create_task", return_value=mock_task):
            # Add an alert rule
            collector.add_alert_rule(
                "test_alert",
                "test_metric",
                "value > 10",
                "warning",
                "Test alert",
                cooldown_seconds=300
            )
            
            # Record a value that should trigger the alert
            initial_alerts = collector.stats["alerts_triggered"]
            collector.record_metric("test_metric", 20.0)
            
            # Verify alert was triggered (stats should be incremented)
            assert collector.stats["alerts_triggered"] > initial_alerts
            
            # Set last_triggered to recent time (within cooldown)
            rule = collector.alert_rules["test_alert"]
            rule.last_triggered = time.time() - 10  # 10 seconds ago, cooldown is 300 seconds
            
            # Record another value - should NOT trigger alert (within cooldown)
            alerts_before = collector.stats["alerts_triggered"]
            collector.record_metric("test_metric", 25.0)
            
            # Alert count should not increase (cooldown active)
            assert collector.stats["alerts_triggered"] == alerts_before

    def test_alert_evaluation_different_metric(self):
        """Test alert evaluation when metric name doesn't match."""
        collector = MetricsCollector()
        
        # Add an alert rule for a different metric
        collector.add_alert_rule(
            "test_alert",
            "other_metric",
            "value > 10",
            "warning",
            "Test alert"
        )
        
        # Record a value for a different metric - should not trigger alert
        initial_alerts = collector.stats["alerts_triggered"]
        collector.record_metric("test_metric", 20.0)
        
        # Alert should not be triggered (metric name doesn't match)
        assert collector.stats["alerts_triggered"] == initial_alerts

    def test_alert_evaluation_disabled_rule(self):
        """Test alert evaluation when rule is disabled."""
        collector = MetricsCollector()
        
        # Add a disabled alert rule
        collector.add_alert_rule(
            "test_alert",
            "test_metric",
            "value > 10",
            "warning",
            "Test alert"
        )
        
        # Disable the rule
        rule = collector.alert_rules["test_alert"]
        rule.enabled = False
        
        # Record a value that would trigger the alert
        initial_alerts = collector.stats["alerts_triggered"]
        collector.record_metric("test_metric", 20.0)
        
        # Alert should not be triggered (rule is disabled)
        assert collector.stats["alerts_triggered"] == initial_alerts


class TestInitMetrics:
    """Tests for init_metrics() async function."""

    @pytest.mark.asyncio
    async def test_init_when_enabled_in_config(self, mock_config_enabled):
        """Test initialization when metrics enabled in config."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Mock config to enable metrics
        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_interval = 2.5

        # Mock start() to avoid actual async task creation
        async def mock_start(self):
            self.running = True

        with patch.object(MetricsCollector, "start", mock_start):
            metrics = await init_metrics()

            assert metrics is not None
            assert isinstance(metrics, MetricsCollector)
            assert metrics.collection_interval == 2.5
            # Check that start was called and running is set
            assert metrics.running is True

        # Cleanup
        await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_init_when_disabled_in_config(self, mock_config_disabled):
        """Test initialization returns None when metrics disabled in config."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Mock config to disable metrics
        mock_config_disabled.observability.enable_metrics = False

        metrics = await init_metrics()

        assert metrics is None

    @pytest.mark.asyncio
    async def test_init_handles_exceptions(self, monkeypatch):
        """Test that init_metrics() handles exceptions gracefully."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Patch get_config to raise exception
        def raise_error():
            raise Exception("Config error")

        from ccbt import config as config_module

        monkeypatch.setattr(config_module, "get_config", raise_error)

        # Should not raise, but return None
        metrics = await init_metrics()
        assert metrics is None

    @pytest.mark.asyncio
    async def test_collection_interval_configuration(self, mock_config_enabled):
        """Test that collection interval is configured from config."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True
        mock_config_enabled.observability.metrics_interval = 10.0

        # Mock start() to avoid actual async task creation
        async def mock_start(self):
            self.running = True

        with patch.object(MetricsCollector, "start", mock_start):
            metrics = await init_metrics()

            assert metrics is not None
            assert metrics.collection_interval == 10.0

        # Cleanup
        await shutdown_metrics()


class TestShutdownMetrics:
    """Tests for shutdown_metrics() async function."""

    @pytest.mark.asyncio
    async def test_shutdown_when_running(self, mock_config_enabled):
        """Test graceful shutdown when metrics are running."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Start metrics
        mock_config_enabled.observability.enable_metrics = True
        metrics = await init_metrics()
        assert metrics is not None
        assert metrics.running is True

        # Shutdown
        await shutdown_metrics()

        # Metrics should be stopped
        assert metrics.running is False

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self):
        """Test shutdown is no-op when metrics not running."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton to None
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Should not raise
        await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self):
        """Test shutdown when metrics collector not initialized."""
        import ccbt.monitoring as monitoring_module

        # Ensure singleton is None
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Should not raise
        await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_shutdown_handles_exceptions(self, mock_config_enabled, monkeypatch):
        """Test that shutdown_metrics() handles exceptions gracefully."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Start metrics
        mock_config_enabled.observability.enable_metrics = True
        metrics = await init_metrics()
        assert metrics is not None

        # Patch stop() to raise exception
        original_stop = metrics.stop

        async def raise_error():
            raise Exception("Stop error")

        monkeypatch.setattr(metrics, "stop", raise_error)

        # Should not raise, but log warning
        await shutdown_metrics()

    @pytest.mark.asyncio
    async def test_init_returns_none_on_config_error(self, monkeypatch):
        """Test init_metrics() returns None when config access fails."""
        import ccbt.monitoring as monitoring_module

        # Ensure clean state
        await shutdown_metrics()
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Patch get_config to raise exception
        def raise_config_error():
            raise RuntimeError("Config error")

        from ccbt import config as config_module

        monkeypatch.setattr(config_module, "get_config", raise_config_error)

        # Should return None, not raise
        result = await init_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_returns_none_on_start_error(self, mock_config_enabled, monkeypatch):
        """Test init_metrics() returns None when start() fails."""
        import ccbt.monitoring as monitoring_module

        # Reset singleton
        monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        mock_config_enabled.observability.enable_metrics = True

        # Patch start() to raise exception
        async def raise_error(self):
            raise Exception("Start error")

        with patch.object(MetricsCollector, "start", raise_error):
            # Should return None, not raise (exception is caught in init_metrics)
            result = await init_metrics()
            assert result is None


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

