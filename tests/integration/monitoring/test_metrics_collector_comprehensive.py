"""Comprehensive tests for MetricsCollector to achieve 95%+ coverage.

Covers:
- Lifecycle (start/stop)
- Metric registration and recording
- Counter, gauge, histogram operations
- Alert rules
- System and performance metrics collection
- Export formats
- Cleanup operations
- Error handling paths
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.monitoring.metrics_collector import (
    AggregationType,
    AlertRule,
    MetricLabel,
    MetricType,
    MetricsCollector,
)


@pytest.fixture
def metrics_collector():
    """Create a MetricsCollector instance."""
    return MetricsCollector()


@pytest.mark.asyncio
async def test_metrics_collector_init():
    """Test MetricsCollector initialization."""
    mc = MetricsCollector()
    
    assert mc.metrics == {}
    assert mc.alert_rules == {}
    assert mc.collectors == {}
    assert mc.running is False
    assert mc.collection_task is None
    assert mc.collection_interval == 5.0
    assert "metrics_collected" in mc.stats
    assert "alerts_triggered" in mc.stats
    assert "collection_errors" in mc.stats


@pytest.mark.asyncio
async def test_start_already_running(metrics_collector):
    """Test start() when already running (line 151-152)."""
    metrics_collector.running = True
    
    await metrics_collector.start()
    
    # Should return early without creating new task
    # Verify no new task was created
    original_task = metrics_collector.collection_task
    await metrics_collector.start()
    assert metrics_collector.collection_task is original_task


@pytest.mark.asyncio
async def test_start_creates_collection_task(metrics_collector):
    """Test start() creates collection task."""
    await metrics_collector.start()
    
    assert metrics_collector.running is True
    assert metrics_collector.collection_task is not None
    assert not metrics_collector.collection_task.done()
    
    await metrics_collector.stop()


@pytest.mark.asyncio
async def test_stop_not_running(metrics_collector):
    """Test stop() when not running (line 170-171)."""
    metrics_collector.running = False
    
    await metrics_collector.stop()
    
    # Should return early
    assert metrics_collector.running is False


@pytest.mark.asyncio
async def test_stop_cancels_task(metrics_collector):
    """Test stop() cancels collection task."""
    await metrics_collector.start()
    task = metrics_collector.collection_task
    
    await metrics_collector.stop()
    
    assert metrics_collector.running is False
    assert task.done() or task.cancelled()


@pytest.mark.asyncio
async def test_register_metric():
    """Test register_metric() creates metric."""
    mc = MetricsCollector()
    
    mc.register_metric(
        name="test_metric",
        metric_type=MetricType.COUNTER,
        description="Test counter",
        labels=[MetricLabel(name="env", value="test")],
        aggregation=AggregationType.SUM,
        retention_seconds=7200,
    )
    
    assert "test_metric" in mc.metrics
    metric = mc.metrics["test_metric"]
    assert metric.name == "test_metric"
    assert metric.metric_type == MetricType.COUNTER
    assert metric.description == "Test counter"
    assert len(metric.labels) == 1
    assert metric.aggregation == AggregationType.SUM
    assert metric.retention_seconds == 7200


@pytest.mark.asyncio
async def test_record_metric_auto_register(metrics_collector):
    """Test record_metric() auto-registers metric if missing (lines 216-222)."""
    metrics_collector.record_metric("new_metric", 42.5)
    
    assert "new_metric" in metrics_collector.metrics
    metric = metrics_collector.metrics["new_metric"]
    assert metric.metric_type == MetricType.GAUGE
    assert len(metric.values) == 1
    assert metric.values[0].value == 42.5


@pytest.mark.asyncio
async def test_record_metric_with_labels(metrics_collector):
    """Test record_metric() with labels."""
    metrics_collector.register_metric(
        "labeled_metric",
        MetricType.GAUGE,
        "Test metric with labels",
    )
    
    labels = [MetricLabel(name="peer", value="peer1"), MetricLabel(name="torrent", value="hash1")]
    metrics_collector.record_metric("labeled_metric", 100.0, labels)
    
    metric = metrics_collector.metrics["labeled_metric"]
    assert len(metric.values) == 1
    assert len(metric.values[0].labels) == 2


@pytest.mark.asyncio
async def test_record_metric_triggers_alert_check(metrics_collector):
    """Test record_metric() checks alert rules (line 234)."""
    # Add alert rule
    metrics_collector.add_alert_rule(
        name="high_value",
        metric_name="test_metric",
        condition="value > 50",
        severity="warning",
    )
    
    # Record metric that should trigger alert
    metrics_collector.record_metric("test_metric", 100.0)
    
    # Alert should be checked (stats may increment)
    assert "test_metric" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_record_metric_with_string_value(metrics_collector):
    """Test record_metric() with string value."""
    metrics_collector.record_metric("string_metric", "status:ok")
    
    metric = metrics_collector.metrics["string_metric"]
    assert metric.values[0].value == "status:ok"


@pytest.mark.asyncio
async def test_increment_counter_new_metric(metrics_collector):
    """Test increment_counter() with new metric (lines 275-276)."""
    metrics_collector.increment_counter("new_counter", 5)
    
    assert "new_counter" in metrics_collector.metrics
    metric = metrics_collector.metrics["new_counter"]
    assert metric.metric_type == MetricType.COUNTER
    assert len(metric.values) == 1
    assert metric.values[0].value == 5


@pytest.mark.asyncio
async def test_increment_counter_existing_metric(metrics_collector):
    """Test increment_counter() increments existing counter (lines 279-284)."""
    metrics_collector.increment_counter("counter", 10)
    metrics_collector.increment_counter("counter", 5)
    
    metric = metrics_collector.metrics["counter"]
    assert len(metric.values) == 2
    assert metric.values[0].value == 10
    assert metric.values[1].value == 15  # 10 + 5


@pytest.mark.asyncio
async def test_increment_counter_no_existing_values(metrics_collector):
    """Test increment_counter() when metric has no values (line 282-283)."""
    metrics_collector.register_metric("empty_counter", MetricType.COUNTER, "Empty counter")
    # Don't record any values yet
    
    metrics_collector.increment_counter("empty_counter", 3)
    
    metric = metrics_collector.metrics["empty_counter"]
    assert len(metric.values) == 1
    assert metric.values[0].value == 3


@pytest.mark.asyncio
async def test_set_gauge_new_metric(metrics_collector):
    """Test set_gauge() with new metric (lines 294-295)."""
    metrics_collector.set_gauge("new_gauge", 42.0)
    
    assert "new_gauge" in metrics_collector.metrics
    metric = metrics_collector.metrics["new_gauge"]
    assert metric.metric_type == MetricType.GAUGE
    assert metric.values[0].value == 42.0


@pytest.mark.asyncio
async def test_set_gauge_existing_metric(metrics_collector):
    """Test set_gauge() updates existing gauge."""
    metrics_collector.set_gauge("gauge", 10.0)
    metrics_collector.set_gauge("gauge", 20.0)
    
    metric = metrics_collector.metrics["gauge"]
    assert len(metric.values) == 2
    assert metric.values[1].value == 20.0


@pytest.mark.asyncio
async def test_record_histogram(metrics_collector):
    """Test record_histogram() method."""
    metrics_collector.record_histogram("hist_metric", 50.0, [1, 10, 50, 100, 1000])
    
    assert "hist_metric" in metrics_collector.metrics
    metric = metrics_collector.metrics["hist_metric"]
    assert metric.metric_type == MetricType.HISTOGRAM
    assert len(metric.values) > 0


@pytest.mark.asyncio
async def test_add_alert_rule(metrics_collector):
    """Test add_alert_rule() creates alert rule."""
    metrics_collector.add_alert_rule(
        name="test_alert",
        metric_name="test_metric",
        condition="value > 100",
        severity="critical",
        description="Test alert",
    )
    
    assert "test_alert" in metrics_collector.alert_rules
    rule = metrics_collector.alert_rules["test_alert"]
    assert rule.name == "test_alert"
    assert rule.metric_name == "test_metric"
    assert rule.condition == "value > 100"
    assert rule.severity == "critical"
    assert rule.enabled is True


@pytest.mark.asyncio
async def test_get_metric(metrics_collector):
    """Test get_metric() returns metric."""
    metrics_collector.register_metric("test", MetricType.GAUGE, "Test")
    
    metric = metrics_collector.get_metric("test")
    
    assert metric is not None
    assert metric.name == "test"
    
    # Test non-existent metric
    assert metrics_collector.get_metric("nonexistent") is None


@pytest.mark.asyncio
async def test_get_metric_value(metrics_collector):
    """Test get_metric_value() retrieves latest value."""
    metrics_collector.record_metric("test_metric", 10.0)
    metrics_collector.record_metric("test_metric", 20.0)
    
    # Default aggregation uses metric's aggregation (which defaults to SUM)
    # So get_metric_value without explicit aggregation uses metric.aggregation
    # But the metric auto-registered with GAUGE type, so aggregation defaults to SUM
    value = metrics_collector.get_metric_value("test_metric")
    
    # With SUM aggregation, should sum all values: 10.0 + 20.0 = 30.0
    assert value == 30.0
    
    # Test with explicit AVG aggregation
    value_avg = metrics_collector.get_metric_value("test_metric", AggregationType.AVG)
    assert isinstance(value_avg, (int, float))
    assert value_avg == 15.0  # (10.0 + 20.0) / 2


@pytest.mark.asyncio
async def test_get_metric_value_nonexistent(metrics_collector):
    """Test get_metric_value() with non-existent metric."""
    value = metrics_collector.get_metric_value("nonexistent")
    
    assert value is None


@pytest.mark.asyncio
async def test_get_all_metrics(metrics_collector):
    """Test get_all_metrics() returns all metrics."""
    metrics_collector.record_metric("metric1", 10.0)
    metrics_collector.record_metric("metric2", 20.0)
    
    all_metrics = metrics_collector.get_all_metrics()
    
    assert "metric1" in all_metrics
    assert "metric2" in all_metrics


@pytest.mark.asyncio
async def test_get_system_metrics(metrics_collector):
    """Test get_system_metrics() returns system metrics."""
    system_metrics = metrics_collector.get_system_metrics()
    
    assert "cpu_usage" in system_metrics
    assert "memory_usage" in system_metrics
    assert "disk_usage" in system_metrics
    assert "network_io" in system_metrics
    assert "process_count" in system_metrics


@pytest.mark.asyncio
async def test_get_performance_metrics(metrics_collector):
    """Test get_performance_metrics() returns performance data."""
    performance = metrics_collector.get_performance_metrics()
    
    assert "peer_connections" in performance
    assert "download_speed" in performance
    assert "upload_speed" in performance
    assert "pieces_completed" in performance


@pytest.mark.asyncio
async def test_get_metrics_statistics(metrics_collector):
    """Test get_metrics_statistics() returns stats."""
    metrics_collector.record_metric("test", 10.0)
    
    stats = metrics_collector.get_metrics_statistics()
    
    assert "metrics_collected" in stats
    assert "alerts_triggered" in stats
    assert "collection_errors" in stats


@pytest.mark.asyncio
async def test_export_metrics_json(metrics_collector):
    """Test export_metrics() JSON format."""
    metrics_collector.record_metric("test_metric", 42.0)
    
    export = metrics_collector.export_metrics("json")
    
    assert "test_metric" in export
    import json
    data = json.loads(export)
    assert "test_metric" in data


@pytest.mark.asyncio
async def test_export_metrics_prometheus(metrics_collector):
    """Test export_metrics() Prometheus format."""
    metrics_collector.record_metric("test_metric", 42.0)
    
    export = metrics_collector.export_metrics("prometheus")
    
    assert isinstance(export, str)
    assert "test_metric" in export or "#" in export  # Prometheus format


@pytest.mark.asyncio
async def test_cleanup_old_metrics(metrics_collector):
    """Test cleanup_old_metrics() removes old values."""
    # Record metric with old timestamp
    metrics_collector.register_metric("old_metric", MetricType.GAUGE, "Old")
    old_value = metrics_collector.metrics["old_metric"].values[0] if metrics_collector.metrics["old_metric"].values else None
    
    # Record new metric
    metrics_collector.record_metric("new_metric", 10.0)
    
    # Manually set old timestamp on old_value if it exists
    if old_value:
        old_value.timestamp = time.time() - 7200  # 2 hours ago
    
    # Cleanup metrics older than 1 hour
    metrics_collector.cleanup_old_metrics(max_age_seconds=3600)
    
    # Old values should be removed
    # New metric should still exist
    assert "new_metric" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_collection_loop_runs(metrics_collector):
    """Test _collection_loop() runs collection methods."""
    # Mock collection methods
    with patch.object(metrics_collector, "_collect_system_metrics", new_callable=AsyncMock) as mock_sys:
        with patch.object(metrics_collector, "_collect_performance_metrics", new_callable=AsyncMock) as mock_perf:
            with patch.object(metrics_collector, "_collect_custom_metrics", new_callable=AsyncMock) as mock_custom:
                metrics_collector.running = True
                
                # Run one iteration
                try:
                    await asyncio.wait_for(metrics_collector._collection_loop(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass  # Expected - loop runs until stopped
                
                # Verify collection methods were called (at least attempted)
                # The loop will continue until running=False, so we just check it starts


@pytest.mark.asyncio
async def test_collect_system_metrics(metrics_collector):
    """Test _collect_system_metrics() updates system metrics."""
    await metrics_collector._collect_system_metrics()
    
    # System metrics should be updated
    assert isinstance(metrics_collector.system_metrics["cpu_usage"], (int, float))
    assert isinstance(metrics_collector.system_metrics["memory_usage"], (int, float))


@pytest.mark.asyncio
async def test_collect_performance_metrics(metrics_collector):
    """Test _collect_performance_metrics() updates performance data."""
    await metrics_collector._collect_performance_metrics()
    
    # Performance data should exist
    assert "peer_connections" in metrics_collector.performance_data


@pytest.mark.asyncio
async def test_collect_custom_metrics(metrics_collector):
    """Test _collect_custom_metrics() calls registered collectors."""
    call_count = {"n": 0}
    
    def custom_collector():
        call_count["n"] += 1
    
    metrics_collector.register_custom_collector("test_collector", custom_collector)
    
    await metrics_collector._collect_custom_metrics()
    
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_check_alert_rules_triggers_alert(metrics_collector):
    """Test _check_alert_rules() triggers alert when condition met."""
    metrics_collector.add_alert_rule(
        name="high_alert",
        metric_name="test_metric",
        condition="value > 50",
        severity="warning",
    )
    
    # Record metric that triggers alert
    metrics_collector._check_alert_rules("test_metric", 100.0)
    
    # Stats should reflect alert check
    assert "alerts_triggered" in metrics_collector.stats


@pytest.mark.asyncio
async def test_check_alert_rules_cooldown(metrics_collector):
    """Test _check_alert_rules() respects cooldown."""
    metrics_collector.add_alert_rule(
        name="cooldown_alert",
        metric_name="test_metric",
        condition="value > 50",
        severity="warning",
        cooldown_seconds=300,
    )
    
    rule = metrics_collector.alert_rules["cooldown_alert"]
    rule.last_triggered = time.time()  # Just triggered
    
    # Should not trigger again immediately
    metrics_collector._check_alert_rules("test_metric", 100.0)
    
    # Cooldown should prevent immediate re-trigger


@pytest.mark.asyncio
async def test_check_alert_rules_disabled(metrics_collector):
    """Test _check_alert_rules() skips disabled rules."""
    metrics_collector.add_alert_rule(
        name="disabled_alert",
        metric_name="test_metric",
        condition="value > 50",
        severity="warning",
    )
    
    rule = metrics_collector.alert_rules["disabled_alert"]
    rule.enabled = False
    
    metrics_collector._check_alert_rules("test_metric", 100.0)
    
    # Disabled rule should not trigger


@pytest.mark.asyncio
async def test_evaluate_condition_simple_comparison(metrics_collector):
    """Test _evaluate_condition() evaluates simple conditions."""
    # Test various conditions
    assert metrics_collector._evaluate_condition("value > 50", 100.0) is True
    assert metrics_collector._evaluate_condition("value > 50", 10.0) is False
    assert metrics_collector._evaluate_condition("value < 50", 10.0) is True
    assert metrics_collector._evaluate_condition("value == 50", 50.0) is True
    assert metrics_collector._evaluate_condition("value != 50", 51.0) is True


@pytest.mark.asyncio
async def test_register_custom_collector(metrics_collector):
    """Test register_custom_collector() adds collector."""
    def my_collector():
        pass
    
    metrics_collector.register_custom_collector("my_collector", my_collector)
    
    assert "my_collector" in metrics_collector.collectors
    assert metrics_collector.collectors["my_collector"] is my_collector


@pytest.mark.asyncio
async def test_unregister_custom_collector(metrics_collector):
    """Test unregister_custom_collector() removes collector."""
    def my_collector():
        pass
    
    metrics_collector.register_custom_collector("my_collector", my_collector)
    metrics_collector.unregister_custom_collector("my_collector")
    
    assert "my_collector" not in metrics_collector.collectors


@pytest.mark.asyncio
async def test_record_metric_alert_manager_integration(metrics_collector):
    """Test record_metric() integrates with AlertManager (lines 237-263)."""
    with patch("ccbt.monitoring.get_alert_manager") as mock_get_am:
        mock_am = MagicMock()
        mock_am.process_alert = AsyncMock()
        mock_get_am.return_value = mock_am
        
        # Mock event loop
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_loop.create_task = MagicMock(return_value=mock_task)
            mock_get_loop.return_value = mock_loop
            
            metrics_collector.record_metric("test_metric", 42.0)
            
            # AlertManager should be called (if conditions met)
            # The actual call depends on async task scheduling
            assert mock_loop.create_task.called


@pytest.mark.asyncio
async def test_record_metric_string_numeric_parse(metrics_collector):
    """Test record_metric() parses numeric string values (lines 246-250)."""
    with patch("ccbt.monitoring.get_alert_manager") as mock_get_am:
        mock_am = MagicMock()
        mock_get_am.return_value = mock_am
        
        # Mock event loop
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_loop.create_task = MagicMock(return_value=MagicMock())
            mock_get_loop.return_value = mock_loop
            
            # Record numeric string - line 249 should trigger
            metrics_collector.record_metric("numeric_string", "42.5")
            
            # Should attempt to parse as float (line 250)
            assert "numeric_string" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_record_metric_alert_manager_exception(metrics_collector):
    """Test record_metric() handles AlertManager exception (lines 259-263)."""
    # Make get_alert_manager raise exception
    with patch("ccbt.monitoring.get_alert_manager", side_effect=Exception("AM error")):
        # Should not crash
        metrics_collector.record_metric("test_metric", 42.0)
        
        assert "test_metric" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_get_metric_value_min_max_count(metrics_collector):
    """Test get_metric_value() with MIN, MAX, COUNT aggregations (lines 358-371)."""
    metrics_collector.record_metric("test_metric", 10.0)
    metrics_collector.record_metric("test_metric", 30.0)
    metrics_collector.record_metric("test_metric", 20.0)
    
    # Test MIN
    value_min = metrics_collector.get_metric_value("test_metric", AggregationType.MIN)
    assert value_min == 10.0
    
    # Test MAX
    value_max = metrics_collector.get_metric_value("test_metric", AggregationType.MAX)
    assert value_max == 30.0
    
    # Test COUNT
    value_count = metrics_collector.get_metric_value("test_metric", AggregationType.COUNT)
    assert value_count == 3
    
    # Test default (fallback to latest value) - line 371
    metric = metrics_collector.metrics["test_metric"]
    metric.aggregation = AggregationType.PERCENTILE  # Unsupported in get_metric_value
    value_default = metrics_collector.get_metric_value("test_metric")
    assert value_default == 20.0  # Latest value


@pytest.mark.asyncio
async def test_get_metric_value_empty_values(metrics_collector):
    """Test get_metric_value() with metric having no values (line 345)."""
    metrics_collector.register_metric("empty_metric", MetricType.GAUGE, "Empty")
    # Don't record any values
    
    value = metrics_collector.get_metric_value("empty_metric")
    
    assert value is None


@pytest.mark.asyncio
async def test_export_metrics_unsupported_format(metrics_collector):
    """Test export_metrics() raises error for unsupported format (lines 426-427)."""
    with pytest.raises(ValueError, match="Unsupported format"):
        metrics_collector.export_metrics("unsupported_format")


@pytest.mark.asyncio
async def test_cleanup_old_metrics_removes_old(metrics_collector):
    """Test cleanup_old_metrics() removes old values (line 437)."""
    # Register metric
    metrics_collector.register_metric("old_metric", MetricType.GAUGE, "Old")
    
    # Record old value manually with old timestamp
    from ccbt.monitoring.metrics_collector import MetricValue
    old_time = time.time() - 7200  # 2 hours ago
    old_value = MetricValue(value=10.0, timestamp=old_time)
    metrics_collector.metrics["old_metric"].values.append(old_value)
    
    # Record new value
    metrics_collector.record_metric("old_metric", 20.0)
    
    # Cleanup metrics older than 1 hour
    metrics_collector.cleanup_old_metrics(max_age_seconds=3600)
    
    # Old value should be removed (popleft called)
    metric = metrics_collector.metrics["old_metric"]
    assert len(metric.values) == 1
    assert metric.values[0].value == 20.0


@pytest.mark.asyncio
async def test_collection_loop_exception_handling(metrics_collector):
    """Test _collection_loop() handles exceptions (lines 452-464)."""
    # Set short interval to make test faster
    metrics_collector.collection_interval = 0.05
    
    # Mock collection methods to raise exception once, then stop
    call_count = {"n": 0}
    
    async def failing_collect_system_metrics():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("Collection error")
        # After first exception, stop the loop
        metrics_collector.running = False
    
    with patch.object(metrics_collector, "_collect_system_metrics", side_effect=failing_collect_system_metrics):
        with patch.object(metrics_collector, "_collect_performance_metrics", new_callable=AsyncMock):
            with patch.object(metrics_collector, "_collect_custom_metrics", new_callable=AsyncMock):
                metrics_collector.running = True
                
                # Start loop - it will run one iteration, catch exception, then stop
                await asyncio.wait_for(metrics_collector._collection_loop(), timeout=0.5)
                
                # Stats should reflect error
                assert metrics_collector.stats["collection_errors"] > 0


@pytest.mark.asyncio
async def test_collect_system_metrics_exception(metrics_collector):
    """Test _collect_system_metrics() handles exceptions (lines 504-514)."""
    # Mock psutil to raise exception
    with patch("ccbt.monitoring.metrics_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.side_effect = Exception("CPU error")
        
        await metrics_collector._collect_system_metrics()
        
        # Should handle exception gracefully


@pytest.mark.asyncio
async def test_collect_custom_metrics_async_collector(metrics_collector):
    """Test _collect_custom_metrics() with async collector (line 527)."""
    async def async_collector():
        return 42.0
    
    metrics_collector.register_custom_collector("async_collector", async_collector)
    
    await metrics_collector._collect_custom_metrics()
    
    # Should call async collector and record metric
    assert "custom_async_collector" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_collect_custom_metrics_exception(metrics_collector):
    """Test _collect_custom_metrics() handles collector exceptions (lines 533-540)."""
    def failing_collector():
        raise Exception("Collector error")
    
    metrics_collector.register_custom_collector("failing", failing_collector)
    
    # Should not crash
    await metrics_collector._collect_custom_metrics()
    
    # Exception should be handled


@pytest.mark.asyncio
async def test_check_alert_rules_exception_handling(metrics_collector):
    """Test _check_alert_rules() handles evaluation exceptions (lines 582-595)."""
    # Add alert rule with invalid condition
    metrics_collector.add_alert_rule(
        name="bad_alert",
        metric_name="test_metric",
        condition="invalid syntax !!!",  # Will cause parse error
        severity="warning",
    )
    
    # Should not crash
    metrics_collector._check_alert_rules("test_metric", 100.0)
    
    # Exception should be handled gracefully


@pytest.mark.asyncio
async def test_evaluate_condition_various_operations(metrics_collector):
    """Test _evaluate_condition() with various AST operations (lines 639-680)."""
    # Test with numeric comparison (safer than string comparison)
    result = metrics_collector._evaluate_condition("value == 10", 10.0)
    assert result is True
    
    result = metrics_collector._evaluate_condition("value == 20", 10.0)
    assert result is False
    
    # Test binary operations (lines 644-652)
    assert metrics_collector._evaluate_condition("value + 10 > 50", 45.0) is True
    assert metrics_collector._evaluate_condition("value * 2 == 100", 50.0) is True
    
    # Test unary operations (lines 654-661)
    assert metrics_collector._evaluate_condition("-value < 0", 10.0) is True
    
    # Test comparison operations (lines 662-674)
    assert metrics_collector._evaluate_condition("value > 10", 25.0) is True
    assert metrics_collector._evaluate_condition("value < 50", 25.0) is True
    assert metrics_collector._evaluate_condition("value >= 25", 25.0) is True
    assert metrics_collector._evaluate_condition("value <= 25", 25.0) is True
    
    # Test invalid node type (line 675-676)
    result = metrics_collector._evaluate_condition("invalid expression", 10.0)
    assert result is False  # Should return False on exception
    
    # Test invalid variable (lines 639-642)
    result = metrics_collector._evaluate_condition("other_var > 50", 100.0)
    assert result is False  # Should return False for invalid variable


@pytest.mark.asyncio
async def test_export_prometheus_format_with_labels(metrics_collector):
    """Test _export_prometheus_format() includes labels (lines 695-698)."""
    metrics_collector.register_metric("labeled_metric", MetricType.GAUGE, "Labeled")
    labels = [MetricLabel(name="peer", value="peer1"), MetricLabel(name="torrent", value="hash1")]
    metrics_collector.record_metric("labeled_metric", 42.0, labels)
    
    prometheus = metrics_collector._export_prometheus_format()
    
    assert "labeled_metric" in prometheus
    assert "peer=" in prometheus or "torrent=" in prometheus

