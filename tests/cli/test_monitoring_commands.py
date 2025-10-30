"""Tests for CLI monitoring commands (dashboard, alerts, metrics)."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.cli]

from ccbt.cli.monitoring_commands import alerts, dashboard, metrics
from ccbt.monitoring.alert_manager import AlertRule, AlertSeverity


class TestDashboardCommand:
    """Test dashboard CLI command."""

    @patch("ccbt.cli.monitoring_commands.run_dashboard")
    @patch("ccbt.cli.monitoring_commands.AsyncSessionManager")
    def test_dashboard_basic(self, mock_session_manager, mock_run_dashboard):
        """Test dashboard command without rules."""
        runner = CliRunner()
        with patch("ccbt.cli.monitoring_commands.get_alert_manager") as mock_get_am:
            result = runner.invoke(dashboard, ["--refresh", "1.0"])
        
        # Should not call alert manager without rules
        mock_get_am.assert_not_called()
        mock_run_dashboard.assert_called_once()

    @patch("ccbt.cli.monitoring_commands.run_dashboard")
    @patch("ccbt.cli.monitoring_commands.AsyncSessionManager")
    def test_dashboard_with_rules_success(self, mock_session_manager, mock_run_dashboard):
        """Test dashboard command with rules file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            rules_path = Path(f.name)
            json.dump({"rules": []}, f)
        
        try:
            am = MagicMock()
            runner = CliRunner()
            with patch("ccbt.cli.monitoring_commands.get_alert_manager", return_value=am):
                result = runner.invoke(dashboard, ["--refresh", "2.0", "--rules", str(rules_path)])
            
            am.load_rules_from_file.assert_called_once_with(rules_path)
            mock_run_dashboard.assert_called_once()
        finally:
            rules_path.unlink(missing_ok=True)

    @patch("ccbt.cli.monitoring_commands.run_dashboard")
    @patch("ccbt.cli.monitoring_commands.AsyncSessionManager")
    def test_dashboard_with_rules_failure(self, mock_session_manager, mock_run_dashboard):
        """Test dashboard command with invalid rules file."""
        am = MagicMock()
        am.load_rules_from_file.side_effect = ValueError("Invalid rules")
        
        runner = CliRunner()
        with patch("ccbt.cli.monitoring_commands.get_alert_manager", return_value=am):
            result = runner.invoke(dashboard, ["--refresh", "1.0", "--rules", "/nonexistent/rules.json"])
        
        # Dashboard should still run even if rules fail to load
        assert "Failed to load alert rules" in result.output
        mock_run_dashboard.assert_called_once()

    @patch("ccbt.cli.monitoring_commands.run_dashboard")
    @patch("ccbt.cli.monitoring_commands.AsyncSessionManager")
    def test_dashboard_error(self, mock_session_manager, mock_run_dashboard):
        """Test dashboard command with error."""
        mock_run_dashboard.side_effect = RuntimeError("Dashboard failed")
        
        runner = CliRunner()
        result = runner.invoke(dashboard, ["--refresh", "1.0"])
        
        assert result.exit_code != 0 or "Dashboard error" in result.output


class TestAlertsCommand:
    """Test alerts CLI command."""

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_list_empty(self, mock_get_am):
        """Test alerts --list with no rules."""
        am = MagicMock()
        am.alert_rules = {}
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--list"])
        
        assert "No alert rules defined" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_list_with_rules(self, mock_get_am):
        """Test alerts --list with rules."""
        rule = AlertRule(
            name="test_rule",
            metric_name="cpu_usage",
            condition="value > 80",
            severity=AlertSeverity.WARNING,
            description="Test rule",
        )
        am = MagicMock()
        am.alert_rules = {"test_rule": rule}
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--list"])
        
        assert "test_rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_list_active_empty(self, mock_get_am):
        """Test alerts --list-active with no active alerts."""
        am = MagicMock()
        am.active_alerts = {}
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--list-active"])
        
        assert "No active alerts" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_add_rule_missing_params(self, mock_get_am):
        """Test alerts --add with missing parameters."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--add"])
        
        assert "required to add a rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_add_rule_success(self, mock_get_am):
        """Test alerts --add with all parameters."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, [
            "--add", "--name", "test_rule", "--metric", "cpu_usage",
            "--condition", "value > 80", "--severity", "error"
        ])
        
        am.add_alert_rule.assert_called_once()
        assert "Added alert rule test_rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_remove_rule_missing_name(self, mock_get_am):
        """Test alerts --remove without name."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--remove"])
        
        assert "required to remove a rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_remove_rule_success(self, mock_get_am):
        """Test alerts --remove with name."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--remove", "--name", "test_rule"])
        
        am.remove_alert_rule.assert_called_once_with("test_rule")
        assert "Removed alert rule test_rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_alerts_clear_active_success(self, mock_asyncio_run, mock_get_am):
        """Test alerts --clear-active."""
        am = MagicMock()
        am.active_alerts = {
            "alert1": MagicMock(),
            "alert2": MagicMock(),
        }
        mock_get_am.return_value = am
        mock_asyncio_run.return_value = None
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--clear-active"])
        
        assert mock_asyncio_run.call_count == 2
        assert "Cleared all active alerts" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_clear_active_error(self, mock_get_am):
        """Test alerts --clear-active with error."""
        am = MagicMock()
        am.active_alerts = {"alert1": MagicMock()}
        mock_get_am.return_value = am
        
        runner = CliRunner()
        with patch("ccbt.cli.monitoring_commands.asyncio.run", side_effect=RuntimeError("Error")):
            result = runner.invoke(alerts, ["--clear-active"])
        
        assert "Failed to clear active alerts" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_test_missing_name(self, mock_get_am):
        """Test alerts --test without name."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--test", "--value", "85"])
        
        assert "required to test a rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_test_missing_value(self, mock_get_am):
        """Test alerts --test without value."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--test", "--name", "test_rule"])
        
        assert "required with --test" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_test_rule_not_found(self, mock_get_am):
        """Test alerts --test with nonexistent rule."""
        am = MagicMock()
        am.alert_rules = {}
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--test", "--name", "nonexistent", "--value", "85"])
        
        assert "Rule not found: nonexistent" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_alerts_test_success_numeric(self, mock_asyncio_run, mock_get_am):
        """Test alerts --test with numeric value."""
        rule = AlertRule(
            name="test_rule",
            metric_name="cpu_usage",
            condition="value > 80",
            severity=AlertSeverity.WARNING,
            description="Test rule",
        )
        am = MagicMock()
        am.alert_rules = {"test_rule": rule}
        mock_get_am.return_value = am
        mock_asyncio_run.return_value = None
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--test", "--name", "test_rule", "--value", "85.5"])
        
        mock_asyncio_run.assert_called_once()
        assert "Tested rule test_rule" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    @patch("ccbt.config.config.get_config")
    def test_alerts_load_success(self, mock_get_config, mock_get_am):
        """Test alerts --load."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            rules_path = Path(f.name)
            json.dump({"rules": []}, f)
        
        try:
            am = MagicMock()
            am.load_rules_from_file.return_value = 5
            mock_get_am.return_value = am
            
            config = MagicMock()
            config.observability.alerts_rules_path = ".ccbt/alerts.json"
            mock_get_config.return_value = config
            
            runner = CliRunner()
            result = runner.invoke(alerts, ["--load", str(rules_path)])
            
            am.load_rules_from_file.assert_called_once_with(rules_path)
            assert "Loaded 5 alert rules" in result.output
        finally:
            rules_path.unlink(missing_ok=True)

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_load_error(self, mock_get_am):
        """Test alerts --load with error."""
        am = MagicMock()
        am.load_rules_from_file.side_effect = ValueError("Invalid file")
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--load", "/nonexistent.json"])
        
        assert "Failed to load rules" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    @patch("ccbt.config.config.get_config")
    def test_alerts_save_success(self, mock_get_config, mock_get_am):
        """Test alerts --save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules.json"
            
            am = MagicMock()
            mock_get_am.return_value = am
            
            config = MagicMock()
            config.observability.alerts_rules_path = ".ccbt/alerts.json"
            mock_get_config.return_value = config
            
            runner = CliRunner()
            result = runner.invoke(alerts, ["--save", str(rules_path)])
            
            am.save_rules_to_file.assert_called_once_with(rules_path)
            assert "Saved alert rules" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_save_error(self, mock_get_am):
        """Test alerts --save with error."""
        am = MagicMock()
        am.save_rules_to_file.side_effect = IOError("Cannot write")
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, ["--save", "/readonly/rules.json"])
        
        assert "Failed to save rules" in result.output

    @patch("ccbt.cli.monitoring_commands.get_alert_manager")
    def test_alerts_no_action(self, mock_get_am):
        """Test alerts with no action specified."""
        am = MagicMock()
        mock_get_am.return_value = am
        
        runner = CliRunner()
        result = runner.invoke(alerts, [])
        
        assert "Use --list" in result.output



class TestMetricsCommand:
    """Test metrics CLI command."""

    def _setup_asyncio_run_mock(self, mock_asyncio_run):
        """Helper to setup asyncio.run mock that properly handles coroutines."""
        def mock_run(coro):
            # Actually run the coroutine to avoid "coroutine was never awaited" warnings
            import asyncio as real_asyncio
            # Try to get or create event loop
            try:
                loop = real_asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Loop is closed")
            except RuntimeError:
                loop = real_asyncio.new_event_loop()
                real_asyncio.set_event_loop(loop)
            
            # Run the coroutine with the mocked MetricsCollector in place
            result = loop.run_until_complete(coro)
            return result
        
        mock_asyncio_run.side_effect = mock_run

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_json_once(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with JSON format, one-shot."""
        mc = MagicMock()
        mc.get_all_metrics.return_value = {"test": 123}
        mock_mc_class.return_value = mc
        
        # Setup mock to properly run coroutines
        self._setup_asyncio_run_mock(mock_asyncio_run)
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "json"])
        
        assert result.exit_code == 0
        assert "test" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_json_with_output(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            mc = MagicMock()
            mc.get_all_metrics.return_value = {}
            mock_mc_class.return_value = mc
            self._setup_asyncio_run_mock(mock_asyncio_run)
            
            runner = CliRunner()
            result = runner.invoke(metrics, ["--format", "json", "--output", str(output_path)])
            
            assert result.exit_code == 0
            assert output_path.exists()
            assert "Wrote metrics" in result.output
        finally:
            output_path.unlink(missing_ok=True)

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_prometheus_format(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with Prometheus format."""
        mc = MagicMock()
        mc._export_prometheus_format.return_value = "# TYPE test_metric gauge\ntest_metric 123"
        mock_mc_class.return_value = mc
        self._setup_asyncio_run_mock(mock_asyncio_run)
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "prometheus"])
        
        assert result.exit_code == 0
        assert "test_metric" in result.output

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_with_duration(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with duration."""
        mc = MagicMock()
        mc.get_all_metrics.return_value = {}
        mock_mc_class.return_value = mc
        self._setup_asyncio_run_mock(mock_asyncio_run)
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "json", "--duration", "5.0", "--interval", "1.0"])
        
        assert result.exit_code == 0
        # Should have called asyncio.run with duration collection
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_with_system_metrics(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with include-system."""
        mc = MagicMock()
        mc.get_all_metrics.return_value = {"test": 123}
        mc.get_system_metrics.return_value = {"cpu": 50.0}
        mock_mc_class.return_value = mc
        self._setup_asyncio_run_mock(mock_asyncio_run)
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "json", "--include-system"])
        
        assert result.exit_code == 0
        assert "cpu" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_with_performance_metrics(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with include-performance."""
        mc = MagicMock()
        mc.get_all_metrics.return_value = {"test": 123}
        mc.get_performance_metrics.return_value = {"throughput": 1000}
        mock_mc_class.return_value = mc
        self._setup_asyncio_run_mock(mock_asyncio_run)
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "json", "--include-performance"])
        
        assert result.exit_code == 0
        assert "throughput" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.monitoring.MetricsCollector")
    @patch("ccbt.cli.monitoring_commands.asyncio.run")
    def test_metrics_error(self, mock_asyncio_run, mock_mc_class):
        """Test metrics command with error."""
        # Make MetricsCollector.start() raise an error
        mc = MagicMock()
        async def failing_start():
            raise RuntimeError("Collection failed")
        mc.start = failing_start
        mock_mc_class.return_value = mc
        
        def mock_run_with_error(coro):
            # Run coroutine to avoid warnings, but it will raise error
            import asyncio as real_asyncio
            try:
                loop = real_asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Loop is closed")
            except RuntimeError:
                loop = real_asyncio.new_event_loop()
                real_asyncio.set_event_loop(loop)
            
            # Actually run the coroutine, which will raise an error
            try:
                return loop.run_until_complete(coro)
            except RuntimeError as e:
                raise RuntimeError("Collection failed") from e
        
        mock_asyncio_run.side_effect = mock_run_with_error
        
        runner = CliRunner()
        result = runner.invoke(metrics, ["--format", "json"])
        
        assert result.exit_code != 0 or "Metrics error" in result.output

