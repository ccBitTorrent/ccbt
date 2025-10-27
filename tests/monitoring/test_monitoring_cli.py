"""Tests for monitoring CLI commands."""

from click.testing import CliRunner

from ccbt.cli.monitoring_commands import alerts, metrics


def test_alerts_list_and_add_remove(tmp_path):
	runner = CliRunner()
	# list should work with no rules
	res = runner.invoke(alerts, ["--list"])
	assert res.exit_code == 0, res.output
	# add a rule
	res_add = runner.invoke(alerts, [
		"--add",
		"--name", "cpu_high",
		"--metric", "system.cpu",
		"--condition", "value > 80",
		"--severity", "warning",
	])
	assert res_add.exit_code == 0, res_add.output
	# list now should contain rule
	res_list = runner.invoke(alerts, ["--list"])
	assert res_list.exit_code == 0
	assert "cpu_high" in res_list.output
	# remove
	res_rm = runner.invoke(alerts, ["--remove", "--name", "cpu_high"])
	assert res_rm.exit_code == 0


def test_metrics_json_snapshot(tmp_path):
	runner = CliRunner()
	res = runner.invoke(metrics, ["--format", "json", "--include-system", "--include-performance"])
	assert res.exit_code == 0, res.output


