"""Monitoring screens for the terminal dashboard."""

from __future__ import annotations

from ccbt.interface.screens.monitoring.alerts import AlertsDashboardScreen
from ccbt.interface.screens.monitoring.disk_analysis import DiskAnalysisScreen
from ccbt.interface.screens.monitoring.disk_io import DiskIOMetricsScreen
from ccbt.interface.screens.monitoring.historical import HistoricalTrendsScreen
from ccbt.interface.screens.monitoring.ipfs import IPFSManagementScreen
from ccbt.interface.screens.monitoring.metrics_explorer import MetricsExplorerScreen
from ccbt.interface.screens.monitoring.nat import NATManagementScreen
from ccbt.interface.screens.monitoring.network import NetworkQualityScreen
from ccbt.interface.screens.monitoring.performance import PerformanceMetricsScreen
from ccbt.interface.screens.monitoring.performance_analysis import (
    PerformanceAnalysisScreen,
)
from ccbt.interface.screens.monitoring.queue import QueueMetricsScreen
from ccbt.interface.screens.monitoring.scrape import ScrapeResultsScreen
from ccbt.interface.screens.monitoring.system_resources import SystemResourcesScreen
from ccbt.interface.screens.monitoring.tracker import TrackerMetricsScreen
from ccbt.interface.screens.monitoring.xet import XetManagementScreen
from ccbt.interface.screens.monitoring.security_scan import SecurityScanScreen
from ccbt.interface.screens.monitoring.dht_metrics import DHTMetricsScreen

__all__ = [
    "AlertsDashboardScreen",
    "DiskAnalysisScreen",
    "DiskIOMetricsScreen",
    "DHTMetricsScreen",
    "HistoricalTrendsScreen",
    "IPFSManagementScreen",
    "MetricsExplorerScreen",
    "NATManagementScreen",
    "NetworkQualityScreen",
    "PerformanceAnalysisScreen",
    "PerformanceMetricsScreen",
    "QueueMetricsScreen",
    "ScrapeResultsScreen",
    "SecurityScanScreen",
    "SystemResourcesScreen",
    "TrackerMetricsScreen",
    "XetManagementScreen",
]
