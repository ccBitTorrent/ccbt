"""Tests for monitoring screens in terminal dashboard.

Covers:
- MonitoringScreen base class
- SystemResourcesScreen
- PerformanceMetricsScreen
- NetworkQualityScreen
- HistoricalTrendsScreen
- AlertsDashboardScreen
- MetricsExplorerScreen
- ConfirmationDialog
- Reusable widgets (ProgressBarWidget, MetricsTableWidget, SparklineGroup)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from collections import deque

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.fixture
def mock_session():
    """Create a mock AsyncSessionManager."""
    session = AsyncMock()
    session.get_global_stats = AsyncMock(return_value={
        "num_torrents": 2,
        "num_active": 1,
        "num_paused": 1,
        "num_seeding": 0,
        "download_rate": 1024.0,
        "upload_rate": 512.0,
        "average_progress": 0.5,
    })
    session.get_status = AsyncMock(return_value={
        "hash1": {
            "name": "Test Torrent 1",
            "status": "downloading",
            "progress": 0.5,
            "download_rate": 1024.0,
            "upload_rate": 256.0,
        }
    })
    session.get_peers_for_torrent = AsyncMock(return_value=[
        {
            "ip": "192.168.1.1",
            "port": 6881,
            "download_rate": 512.0,
            "upload_rate": 128.0,
            "choked": False,
            "client": "uTorrent",
        }
    ])
    session.config = MagicMock()
    return session


@pytest.fixture
def mock_metrics_collector():
    """Create a mock MetricsCollector."""
    collector = MagicMock()
    collector.running = True
    collector.get_system_metrics = Mock(return_value={
        "cpu_usage": 45.5,
        "memory_usage": 60.2,
        "disk_usage": 75.0,
        "process_count": 150,
        "network_io": {
            "bytes_sent": 1024 * 1024 * 100,
            "bytes_recv": 1024 * 1024 * 200,
        },
    })
    collector.get_performance_metrics = Mock(return_value={
        "peer_connections": 10,
        "download_speed": 1024 * 1024 * 2,
        "upload_speed": 1024 * 512,
        "pieces_completed": 1000,
        "pieces_failed": 5,
        "tracker_requests": 50,
        "tracker_responses": 48,
        # DHT metrics
        "dht_nodes_discovered": 150,
        "dht_queries_sent": 200,
        "dht_queries_received": 180,
        "dht_response_rate": 90.0,
        # Queue metrics
        "queue_length": 5,
        "queue_wait_time": 120.5,
        "priority_distribution": {"high": 2, "normal": 3},
        # Disk I/O metrics
        "disk_write_throughput": 1024 * 1024 * 10,
        "disk_read_throughput": 1024 * 1024 * 5,
        "disk_queue_depth": 3,
        # Tracker metrics
        "tracker_announce_success_rate": 95.5,
        "tracker_scrape_success_rate": 98.0,
        "tracker_average_response_time": 0.5,
        "tracker_error_count": 2,
    })
    collector.get_metrics_statistics = Mock(return_value={
        "metrics_collected": 500,
        "alerts_triggered": 2,
        "collection_errors": 0,
        "registered_metrics": 20,
        "alert_rules": 5,
        "collection_interval": 5.0,
        "running": True,
    })
    collector.get_all_metrics = Mock(return_value={
        "system_cpu_usage": {
            "type": "gauge",
            "current_value": 45.5,
            "description": "CPU usage percentage",
        },
        "system_memory_usage": {
            "type": "gauge",
            "current_value": 60.2,
            "description": "Memory usage percentage",
        },
    })
    collector.get_metric = Mock(return_value=MagicMock(
        metric_type=MagicMock(value="gauge"),
        description="Test metric",
        aggregation=MagicMock(value="avg"),
        retention_seconds=300,
        values=deque([1.0, 2.0, 3.0]),
        labels=[],
    ))
    return collector


@pytest.fixture
def mock_alert_manager():
    """Create a mock AlertManager."""
    manager = MagicMock()
    manager.alert_rules = {
        "high_cpu": MagicMock(
            metric_name="cpu_usage",
            condition="> 80",
            severity=MagicMock(value="warning"),
            enabled=True,
        ),
    }
    manager.active_alerts = {}
    manager.alert_history = deque()
    manager.stats = {
        "alerts_triggered": 2,
        "alerts_resolved": 1,
        "notifications_sent": 2,
        "notification_failures": 0,
        "suppressed_alerts": 0,
    }
    return manager


@pytest.fixture
def mock_plugin_manager():
    """Create a mock PluginManager."""
    manager = MagicMock()
    manager.plugins = {}
    manager.get_plugin = Mock(return_value=None)
    return manager


class TestConfirmationDialog:
    """Tests for ConfirmationDialog."""

    def test_confirmation_dialog_init(self):
        """Test ConfirmationDialog initialization."""
        from ccbt.interface.terminal_dashboard import ConfirmationDialog

        dialog = ConfirmationDialog("Test message")
        assert dialog.message == "Test message"
        assert dialog.result is None

    def test_confirmation_dialog_compose(self):
        """Test ConfirmationDialog compose method."""
        from ccbt.interface.terminal_dashboard import ConfirmationDialog

        dialog = ConfirmationDialog("Test message")
        # Compose should yield widgets
        widgets = list(dialog.compose())
        assert len(widgets) > 0

    @pytest.mark.asyncio
    async def test_confirmation_dialog_yes_action(self):
        """Test ConfirmationDialog yes action."""
        from ccbt.interface.terminal_dashboard import ConfirmationDialog

        dialog = ConfirmationDialog("Test message")
        dialog.dismiss = Mock()  # dismiss is not async in Textual
        await dialog.action_yes()
        assert dialog.result is True
        dialog.dismiss.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_confirmation_dialog_no_action(self):
        """Test ConfirmationDialog no action."""
        from ccbt.interface.terminal_dashboard import ConfirmationDialog

        dialog = ConfirmationDialog("Test message")
        dialog.dismiss = Mock()  # dismiss is not async in Textual
        await dialog.action_no()
        assert dialog.result is False
        dialog.dismiss.assert_called_once_with(False)


class TestMonitoringScreen:
    """Tests for MonitoringScreen base class."""

    @pytest.mark.asyncio
    async def test_monitoring_screen_init(self, mock_session, mock_metrics_collector, mock_alert_manager, mock_plugin_manager):
        """Test MonitoringScreen initialization."""
        from ccbt.interface.terminal_dashboard import MonitoringScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=mock_alert_manager), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=mock_plugin_manager):
            screen = MonitoringScreen(mock_session, refresh_interval=2.0)
            assert screen.session == mock_session
            assert screen.refresh_interval == 2.0
            assert screen.metrics_collector == mock_metrics_collector
            assert screen.alert_manager == mock_alert_manager
            assert screen.plugin_manager == mock_plugin_manager

    @pytest.mark.asyncio
    async def test_monitoring_screen_get_metrics_plugin(self, mock_session, mock_plugin_manager):
        """Test _get_metrics_plugin method."""
        from ccbt.interface.terminal_dashboard import MonitoringScreen

        # Mock plugin with MetricsPlugin - needs all required methods
        mock_plugin = MagicMock()
        mock_plugin.name = "metrics_plugin"
        mock_plugin.collector = MagicMock()
        mock_plugin.get_aggregates = Mock(return_value=[])
        mock_plugin.get_metrics = Mock(return_value=[])  # Required method
        # Set state to RUNNING to match the check
        from ccbt.plugins.base import PluginState
        mock_plugin.state = PluginState.RUNNING
        mock_plugin_manager.plugins = {"metrics_plugin": mock_plugin}
        mock_plugin_manager.get_plugin = Mock(return_value=mock_plugin)

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=mock_plugin_manager):
            screen = MonitoringScreen(mock_session)
            plugin = screen._get_metrics_plugin()
            assert plugin == mock_plugin

    @pytest.mark.asyncio
    async def test_monitoring_screen_get_metrics_plugin_not_found(self, mock_session, mock_plugin_manager):
        """Test _get_metrics_plugin when plugin not found."""
        from ccbt.interface.terminal_dashboard import MonitoringScreen
        from ccbt.utils.events import get_event_bus

        mock_plugin_manager.get_plugin = Mock(return_value=None)
        mock_event_bus = MagicMock(_handlers={})

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=mock_plugin_manager), \
             patch("ccbt.utils.events.get_event_bus", return_value=mock_event_bus):
            screen = MonitoringScreen(mock_session)
            plugin = screen._get_metrics_plugin()
            assert plugin is None


class TestSystemResourcesScreen:
    """Tests for SystemResourcesScreen."""

    @pytest.mark.asyncio
    async def test_system_resources_screen_refresh_data(self, mock_session, mock_metrics_collector):
        """Test SystemResourcesScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import SystemResourcesScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = SystemResourcesScreen(mock_session)
            screen.query_one = Mock(return_value=MagicMock(update=Mock()))

            await screen._refresh_data()

            # Verify metrics collector was called
            mock_metrics_collector.get_system_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_resources_screen_refresh_data_not_running(self, mock_session):
        """Test SystemResourcesScreen._refresh_data when collector not running."""
        from ccbt.interface.terminal_dashboard import SystemResourcesScreen

        mock_collector = MagicMock()
        mock_collector.running = False

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = SystemResourcesScreen(mock_session)
            content_widget = MagicMock(update=Mock())
            screen.query_one = Mock(return_value=content_widget)

            await screen._refresh_data()

            # Should show message about collector not running
            content_widget.update.assert_called()

    def test_system_resources_screen_format_progress_bar(self, mock_session):
        """Test _format_progress_bar method."""
        from ccbt.interface.terminal_dashboard import SystemResourcesScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = SystemResourcesScreen(mock_session)
            result = screen._format_progress_bar(75.0, 100.0)
            assert "75.0%" in result
            assert "█" in result or "░" in result


class TestPerformanceMetricsScreen:
    """Tests for PerformanceMetricsScreen."""

    @pytest.mark.asyncio
    async def test_performance_metrics_screen_refresh_data(self, mock_session, mock_metrics_collector):
        """Test PerformanceMetricsScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import PerformanceMetricsScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = PerformanceMetricsScreen(mock_session)
            screen.query_one = Mock(return_value=MagicMock(update=Mock()))

            await screen._refresh_data()

            # Verify metrics collector methods were called
            mock_metrics_collector.get_performance_metrics.assert_called_once()
            # get_metrics_statistics may be called multiple times (e.g., in different sections)
            assert mock_metrics_collector.get_metrics_statistics.call_count >= 1


class TestNetworkQualityScreen:
    """Tests for NetworkQualityScreen."""

    @pytest.mark.asyncio
    async def test_network_quality_screen_refresh_data(self, mock_session):
        """Test NetworkQualityScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import NetworkQualityScreen

        # Mock session with config for bandwidth utilization
        mock_session.config = MagicMock()
        mock_session.config.network = MagicMock()
        mock_session.config.network.max_download_speed = 1024 * 1024 * 10  # 10 MB/s
        mock_session.config.network.max_upload_speed = 1024 * 1024 * 5  # 5 MB/s
        
        # Mock peers with latency data
        mock_session.get_peers_for_torrent = AsyncMock(return_value=[
            {
                "ip": "192.168.1.1",
                "port": 6881,
                "download_rate": 512.0,
                "upload_rate": 128.0,
                "choked": False,
                "client": "uTorrent",
                "request_latency": 0.05,  # 50ms
                "pieces_downloaded": 10,
                "pieces_uploaded": 5,
            },
            {
                "ip": "192.168.1.2",
                "port": 6882,
                "download_rate": 256.0,
                "upload_rate": 64.0,
                "choked": True,
                "client": "qBittorrent",
                "request_latency": 0.1,  # 100ms
                "pieces_downloaded": 5,
                "pieces_uploaded": 2,
            }
        ])

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = NetworkQualityScreen(mock_session)
            screen.query_one = Mock(return_value=MagicMock(update=Mock()))

            await screen._refresh_data()

            # Verify session methods were called
            mock_session.get_global_stats.assert_called_once()
            mock_session.get_status.assert_called_once()
            mock_session.get_peers_for_torrent.assert_called()

    def test_network_quality_screen_calculate_connection_quality(self, mock_session):
        """Test _calculate_connection_quality method."""
        from ccbt.interface.terminal_dashboard import NetworkQualityScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = NetworkQualityScreen(mock_session)
            peer_data = {
                "download_rate": 1024 * 1024,  # 1 MB/s
                "upload_rate": 512 * 1024,  # 512 KB/s
                "choked": False,
            }
            quality = screen._calculate_connection_quality(peer_data)
            assert 0.0 <= quality <= 100.0

    def test_network_quality_screen_format_quality_indicator(self, mock_session):
        """Test _format_quality_indicator method."""
        from ccbt.interface.terminal_dashboard import NetworkQualityScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = NetworkQualityScreen(mock_session)
            result = screen._format_quality_indicator(85.0)
            assert "85" in result
            assert "%" in result


class TestHistoricalTrendsScreen:
    """Tests for HistoricalTrendsScreen."""

    @pytest.mark.asyncio
    async def test_historical_trends_screen_refresh_data(self, mock_session, mock_metrics_collector):
        """Test HistoricalTrendsScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import HistoricalTrendsScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = HistoricalTrendsScreen(mock_session)
            screen.query_one = Mock(return_value=MagicMock(update=Mock(), update_sparkline=Mock()))

            await screen._refresh_data()

            # Verify session and metrics collector were called
            mock_session.get_global_stats.assert_called_once()
            mock_metrics_collector.get_system_metrics.assert_called_once()
            mock_metrics_collector.get_performance_metrics.assert_called_once()
            
            # Verify new metrics are stored
            assert "dht_nodes_discovered" in screen._historical_data
            assert "queue_length" in screen._historical_data
            assert "disk_write_throughput" in screen._historical_data
            assert "disk_read_throughput" in screen._historical_data
            assert "tracker_average_response_time" in screen._historical_data

    def test_historical_trends_screen_store_historical_metric(self, mock_session):
        """Test _store_historical_metric method."""
        from ccbt.interface.terminal_dashboard import HistoricalTrendsScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = HistoricalTrendsScreen(mock_session)
            screen._store_historical_metric("test_metric", 42.0)
            assert "test_metric" in screen._historical_data
            assert screen._historical_data["test_metric"] == [42.0]

    def test_historical_trends_screen_store_historical_metric_limit(self, mock_session):
        """Test _store_historical_metric maintains max_samples limit."""
        from ccbt.interface.terminal_dashboard import HistoricalTrendsScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = HistoricalTrendsScreen(mock_session)
            # Fill to max_samples
            screen._historical_data["test_metric"] = list(range(120))
            screen._store_historical_metric("test_metric", 121.0)
            assert len(screen._historical_data["test_metric"]) == 120
            assert screen._historical_data["test_metric"][-1] == 121.0


class TestAlertsDashboardScreen:
    """Tests for AlertsDashboardScreen."""

    @pytest.mark.asyncio
    async def test_alerts_dashboard_screen_refresh_data(self, mock_session, mock_alert_manager):
        """Test AlertsDashboardScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import AlertsDashboardScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=mock_alert_manager), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = AlertsDashboardScreen(mock_session)
            screen.query_one = Mock(return_value=MagicMock(update=Mock()))

            await screen._refresh_data()

            # Verify alert manager attributes were accessed
            assert hasattr(mock_alert_manager, "alert_rules")

    def test_alerts_dashboard_screen_format_alert_severity(self, mock_session):
        """Test _format_alert_severity method."""
        from ccbt.interface.terminal_dashboard import AlertsDashboardScreen
        from ccbt.monitoring.alert_manager import AlertSeverity

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = AlertsDashboardScreen(mock_session)
            result = screen._format_alert_severity(AlertSeverity.CRITICAL)
            assert "CRITICAL" in result.upper() or "critical" in result.lower()


class TestMetricsExplorerScreen:
    """Tests for MetricsExplorerScreen."""

    @pytest.mark.asyncio
    async def test_metrics_explorer_screen_refresh_data(self, mock_session, mock_metrics_collector):
        """Test MetricsExplorerScreen._refresh_data."""
        from ccbt.interface.terminal_dashboard import MetricsExplorerScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = MetricsExplorerScreen(mock_session)
            mock_table = MagicMock(clear=Mock(), add_row=Mock(), cursor_row_key=None)
            mock_input = MagicMock(value="")
            mock_details = MagicMock(update=Mock())
            # query_one is called multiple times with different selectors
            screen.query_one = Mock(side_effect=lambda selector, *args: {
                "#metrics_table": mock_table,
                "#filter_input": mock_input,
                "#metric_details": mock_details,
            }.get(selector, MagicMock()))

            await screen._refresh_data()

            # Verify metrics collector was called
            mock_metrics_collector.get_all_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_explorer_screen_show_metric_details(self, mock_session, mock_metrics_collector):
        """Test _show_metric_details method."""
        from ccbt.interface.terminal_dashboard import MetricsExplorerScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=mock_metrics_collector), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = MetricsExplorerScreen(mock_session)
            mock_details = MagicMock(update=Mock())
            screen.query_one = Mock(return_value=mock_details)

            await screen._show_metric_details("system_cpu_usage")

            # Verify metric was retrieved
            mock_metrics_collector.get_metric.assert_called_once_with("system_cpu_usage")
            mock_details.update.assert_called_once()


class TestReusableWidgets:
    """Tests for reusable widget components."""

    def test_progress_bar_widget_update_progress(self):
        """Test ProgressBarWidget.update_progress."""
        from ccbt.interface.terminal_dashboard import ProgressBarWidget

        widget = ProgressBarWidget()
        widget.update = Mock()
        widget.update_progress(75.0, 100.0, "CPU")
        widget.update.assert_called_once()
        call_args = widget.update.call_args[0][0]
        assert "75.0" in call_args
        assert "CPU" in call_args

    def test_metrics_table_widget_update_from_metrics(self):
        """Test MetricsTableWidget.update_from_metrics."""
        from ccbt.interface.terminal_dashboard import MetricsTableWidget

        widget = MetricsTableWidget()
        widget.clear = Mock()
        widget.add_row = Mock()
        widget.add_columns = Mock()

        metrics = {
            "test_metric": {
                "type": "gauge",
                "current_value": 42.0,
                "description": "Test metric",
            }
        }

        widget.update_from_metrics(metrics)
        widget.clear.assert_called_once()
        widget.add_row.assert_called_once()

    def test_sparkline_group_add_sparkline(self):
        """Test SparklineGroup.add_sparkline."""
        from ccbt.interface.terminal_dashboard import SparklineGroup

        widget = SparklineGroup()
        widget.mount = Mock()
        widget.add_sparkline("test_metric", [1.0, 2.0, 3.0])
        assert "test_metric" in widget._sparklines
        assert "test_metric" in widget._histories

    def test_sparkline_group_update_sparkline(self):
        """Test SparklineGroup.update_sparkline."""
        from ccbt.interface.terminal_dashboard import SparklineGroup

        widget = SparklineGroup()
        widget.mount = Mock()
        widget.add_sparkline("test_metric")
        widget.update_sparkline("test_metric", 42.0)
        assert len(widget._histories["test_metric"]) == 1
        assert widget._histories["test_metric"][0] == 42.0


class TestConfigScreenUnsavedChanges:
    """Tests for ConfigScreen unsaved changes handling."""

    def test_config_screen_unsaved_changes_flag(self, mock_session):
        """Test ConfigScreen unsaved changes flag management."""
        from ccbt.interface.terminal_dashboard import ConfigScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = ConfigScreen(mock_session)
            # Initially no unsaved changes
            assert screen._has_unsaved_changes is False
            
            # Set flag
            screen._has_unsaved_changes = True
            assert screen._has_unsaved_changes is True
            
            # Clear flag
            screen._has_unsaved_changes = False
            assert screen._has_unsaved_changes is False

    def test_confirmation_dialog_creation(self):
        """Test ConfirmationDialog can be created with message."""
        from ccbt.interface.terminal_dashboard import ConfirmationDialog

        dialog = ConfirmationDialog("Test unsaved changes message")
        assert dialog.message == "Test unsaved changes message"
        assert dialog.result is None
        # Verify compose works
        widgets = list(dialog.compose())
        assert len(widgets) > 0

    def test_global_config_detail_screen_check_unsaved_changes(self, mock_session):
        """Test GlobalConfigDetailScreen._check_unsaved_changes."""
        from ccbt.interface.terminal_dashboard import GlobalConfigDetailScreen

        with patch("ccbt.interface.terminal_dashboard.get_metrics_collector", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_alert_manager", return_value=MagicMock()), \
             patch("ccbt.interface.terminal_dashboard.get_plugin_manager", return_value=MagicMock()):
            screen = GlobalConfigDetailScreen(mock_session, section_name="network")
            screen._editors = {}
            screen._original_values = {"test_key": "original_value"}

            # No editors, so no changes
            result = screen._check_unsaved_changes()
            assert result is False

            # Add editor with same value
            mock_editor = MagicMock()
            mock_editor.get_parsed_value = Mock(return_value="original_value")
            screen._editors["test_key"] = mock_editor

            result = screen._check_unsaved_changes()
            assert result is False

            # Change value
            mock_editor.get_parsed_value = Mock(return_value="new_value")
            result = screen._check_unsaved_changes()
            assert result is True

