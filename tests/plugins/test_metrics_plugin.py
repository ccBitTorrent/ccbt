from __future__ import annotations

import pytest

from ccbt.utils.events import Event, EventType, get_event_bus
from ccbt.plugins.metrics_plugin import Metric, MetricAggregate, MetricsCollector, MetricsPlugin


class TestMetricsCollector:
    """Test MetricsCollector event handling."""

    @pytest.mark.asyncio
    async def test_handle_performance_metric(self):
        """Test handling performance metric events."""
        collector = MetricsCollector(max_metrics=100)
        event = Event(
            event_type=EventType.PERFORMANCE_METRIC.value,
            data={
                "metric_name": "download_speed",
                "metric_value": 1024.5,
                "metric_unit": "bytes/sec",
                "tags": {"peer": "test-peer"},
            },
            timestamp=1234567890.0,
        )

        await collector.handle(event)

        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "download_speed"
        assert metric.value == 1024.5
        assert metric.unit == "bytes/sec"
        assert metric.tags == {"peer": "test-peer"}

    @pytest.mark.asyncio
    async def test_handle_piece_downloaded(self):
        """Test handling piece downloaded events."""
        collector = MetricsCollector()
        event = Event(
            event_type=EventType.PIECE_DOWNLOADED.value,
            data={
                "piece_size": 16384,
                "download_time": 0.5,
                "peer_ip": "192.168.1.1",
            },
            timestamp=1234567890.0,
        )

        await collector.handle(event)

        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "piece_download_speed"
        assert metric.value == 16384 / 0.5
        assert metric.unit == "bytes/sec"
        assert metric.tags == {"peer_ip": "192.168.1.1"}

    @pytest.mark.asyncio
    async def test_handle_piece_downloaded_zero_time(self):
        """Test handling piece downloaded with zero time."""
        collector = MetricsCollector()
        event = Event(
            event_type=EventType.PIECE_DOWNLOADED.value,
            data={"piece_size": 16384, "download_time": 0.0, "peer_ip": "192.168.1.1"},
            timestamp=1234567890.0,
        )

        await collector.handle(event)

        assert len(collector.metrics) == 0

    @pytest.mark.asyncio
    async def test_handle_torrent_completed(self):
        """Test handling torrent completed events."""
        collector = MetricsCollector()
        event = Event(
            event_type=EventType.TORRENT_COMPLETED.value,
            data={
                "total_size": 1000000,
                "download_time": 10.0,
                "torrent_name": "test.torrent",
            },
            timestamp=1234567890.0,
        )

        await collector.handle(event)

        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "torrent_avg_speed"
        assert metric.value == 100000.0
        assert metric.unit == "bytes/sec"
        assert metric.tags == {"torrent_name": "test.torrent"}

    def test_update_aggregate(self):
        """Test metric aggregation."""
        collector = MetricsCollector()
        metric1 = Metric("test_metric", 10.0, "bytes", 1234567890.0, {"tag": "a"})
        metric2 = Metric("test_metric", 20.0, "bytes", 1234567890.1, {"tag": "a"})

        collector._update_aggregate(metric1)
        collector._update_aggregate(metric2)

        assert len(collector.aggregates) == 1
        agg = list(collector.aggregates.values())[0]
        assert agg.name == "test_metric"
        assert agg.count == 2
        assert agg.sum == 30.0
        assert agg.min == 10.0
        assert agg.max == 20.0
        assert agg.avg == 15.0

    def test_get_metrics_by_name(self):
        """Test filtering metrics by name."""
        collector = MetricsCollector()
        metric1 = Metric("metric_a", 1.0, "bytes", 1234567890.0)
        metric2 = Metric("metric_b", 2.0, "bytes", 1234567890.1)
        collector.metrics.append(metric1)
        collector.metrics.append(metric2)

        results = collector.get_metrics(name="metric_a")
        assert len(results) == 1
        assert results[0].name == "metric_a"

    def test_get_metrics_by_tags(self):
        """Test filtering metrics by tags."""
        collector = MetricsCollector()
        metric1 = Metric("test", 1.0, "bytes", 1234567890.0, {"peer": "a"})
        metric2 = Metric("test", 2.0, "bytes", 1234567890.1, {"peer": "b"})
        collector.metrics.append(metric1)
        collector.metrics.append(metric2)

        results = collector.get_metrics(tags={"peer": "a"})
        assert len(results) == 1
        assert results[0].tags["peer"] == "a"

    def test_get_metrics_limit(self):
        """Test limiting returned metrics."""
        collector = MetricsCollector()
        for i in range(10):
            metric = Metric(f"metric_{i}", float(i), "bytes", 1234567890.0 + i)
            collector.metrics.append(metric)

        results = collector.get_metrics(limit=5)
        assert len(results) == 5
        assert results[0].name == "metric_5"  # Last 5

    def test_get_aggregates_by_name(self):
        """Test filtering aggregates by name."""
        collector = MetricsCollector()
        metric1 = Metric("metric_a", 1.0, "bytes", 1234567890.0)
        metric2 = Metric("metric_b", 2.0, "bytes", 1234567890.1)
        collector._update_aggregate(metric1)
        collector._update_aggregate(metric2)

        results = collector.get_aggregates(name="metric_a")
        assert len(results) == 1
        assert results[0].name == "metric_a"


class TestMetricsPlugin:
    """Test MetricsPlugin lifecycle and event handling."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test plugin initialization."""
        plugin = MetricsPlugin()
        await plugin.initialize()

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test plugin start and stop."""
        plugin = MetricsPlugin()
        await plugin.initialize()
        await plugin.start()
        assert plugin.collector is not None

        await plugin.stop()
        await plugin.cleanup()
        assert plugin.collector is None

    @pytest.mark.asyncio
    async def test_event_handling(self):
        """Test that plugin collects metrics from events."""
        plugin = MetricsPlugin()
        await plugin.initialize()
        await plugin.start()

        # Directly call the collector handler to test event handling
        assert plugin.collector is not None
        
        event = Event(
            event_type=EventType.PERFORMANCE_METRIC.value,
            data={
                "metric_name": "test_metric",
                "metric_value": 42.0,
                "metric_unit": "bytes",
            },
            timestamp=1234567890.0,
        )

        await plugin.collector.handle(event)

        metrics = plugin.get_metrics()
        assert len(metrics) >= 1
        assert any(m.name == "test_metric" for m in metrics)

        await plugin.stop()
        await plugin.cleanup()

    def test_get_stats(self):
        """Test plugin statistics."""
        plugin = MetricsPlugin(max_metrics=500)
        stats = plugin.get_stats()
        assert stats["total_metrics"] == 0
        assert stats["max_metrics"] == 500

        plugin.collector = MetricsCollector()
        plugin.collector.metrics.append(Metric("test", 1.0, "bytes", 1234567890.0))
        stats = plugin.get_stats()
        assert stats["total_metrics"] == 1

    def test_get_metrics_without_collector(self):
        """Test getting metrics when collector not started."""
        plugin = MetricsPlugin()
        assert plugin.get_metrics() == []

    def test_get_aggregates_without_collector(self):
        """Test getting aggregates when collector not started."""
        plugin = MetricsPlugin()
        assert plugin.get_aggregates() == []

