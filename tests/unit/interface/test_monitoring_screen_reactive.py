"""Monitoring screen reactive binding tests (F2.7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.screens.monitoring.dht_metrics import DHTMetricsScreen
from ccbt.interface.screens.monitoring.disk_io import DiskIOMetricsScreen
from ccbt.interface.screens.monitoring.historical import HistoricalTrendsScreen
from ccbt.interface.screens.monitoring.network import NetworkQualityScreen
from ccbt.interface.screens.monitoring.performance import PerformanceMetricsScreen
from ccbt.interface.screens.monitoring.system_resources import SystemResourcesScreen

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.parametrize(
    ("screen_cls", "reactive_sources"),
    [
        (SystemResourcesScreen, ("system_metrics",)),
        (NetworkQualityScreen, ("global_stats", "torrents_data")),
        (DHTMetricsScreen, ("dht_health_summary",)),
        (DiskIOMetricsScreen, ("disk_io_metrics",)),
        (HistoricalTrendsScreen, ("global_stats", "system_metrics")),
        (PerformanceMetricsScreen, ("global_stats",)),
    ],
)
def test_monitoring_screen_declares_reactive_sources(
    screen_cls: type,
    reactive_sources: tuple[str, ...],
) -> None:
    """Each mapped monitoring screen declares _reactive_sources (F2.7.2)."""
    assert getattr(screen_cls, "_reactive_sources", ()) == reactive_sources
    for name in reactive_sources:
        assert hasattr(screen_cls, name)


@pytest.mark.asyncio
async def test_system_resources_refresh_uses_metrics_override() -> None:
    """_refresh_data renders from system_metrics_override without collector (F2.7.2)."""
    screen = SystemResourcesScreen.__new__(SystemResourcesScreen)
    screen.metrics_collector = None
    content = MagicMock()
    network_info = MagicMock()
    screen.query_one = MagicMock(side_effect=[content, network_info])  # type: ignore[method-assign]

    await screen._refresh_data(
        system_metrics_override={"cpu_usage": 10.0, "memory_usage": 20.0, "disk_usage": 30.0}
    )

    content.update.assert_called_once()
    network_info.update.assert_called_once_with("")


@pytest.mark.asyncio
async def test_disk_io_refresh_uses_metrics_override() -> None:
    """_refresh_data renders provider disk metrics without disk_io_manager (F2.7.2)."""
    screen = DiskIOMetricsScreen.__new__(DiskIOMetricsScreen)
    content = MagicMock()
    io_stats = MagicMock()
    cache_stats = MagicMock()
    config_info = MagicMock()
    screen.query_one = MagicMock(  # type: ignore[method-assign]
        side_effect=[content, io_stats, cache_stats, config_info]
    )

    await screen._refresh_data(
        disk_io_metrics_override={
            "read_throughput": 1024.0,
            "write_throughput": 512.0,
            "cache_hit_rate": 90.0,
            "timing_ms": 1.5,
        }
    )

    content.update.assert_called_once()
    io_stats.update.assert_called_once_with("")
    cache_stats.update.assert_called_once_with("")
    config_info.update.assert_called_once_with("")


@pytest.mark.asyncio
async def test_historical_refresh_uses_global_stats_override() -> None:
    """_refresh_data appends history from global_stats_override (F2.7.2)."""
    screen = HistoricalTrendsScreen.__new__(HistoricalTrendsScreen)
    screen._historical_data = {}
    screen._max_samples = 120
    screen.metrics_collector = None
    screen.session = MagicMock()
    screen.session.get_global_stats = AsyncMock(return_value={})
    content = MagicMock()
    sparklines = MagicMock()
    screen.query_one = MagicMock(side_effect=[content, sparklines])  # type: ignore[method-assign]

    await screen._refresh_data(
        global_stats_override={"download_rate": 2048.0, "upload_rate": 1024.0}
    )

    assert screen._historical_data.get("download_rate") == [2048.0]
    assert screen._historical_data.get("upload_rate") == [1024.0]
    screen.session.get_global_stats.assert_not_awaited()
