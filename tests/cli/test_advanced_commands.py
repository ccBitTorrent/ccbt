"""Basic tests for advanced CLI commands.

These ensure the commands are invokable and do not crash under normal flags.
"""

from pathlib import Path

from click.testing import CliRunner

from ccbt.cli.advanced_commands import performance, security, recover


def test_performance_analyze_invokes():
	runner = CliRunner()
	result = runner.invoke(performance, ["--analyze"])
	assert result.exit_code == 0, result.output


def test_security_scan_invokes():
	runner = CliRunner()
	result = runner.invoke(security, ["--scan"])
	assert result.exit_code == 0, result.output


def test_recover_verify_with_dummy_info_hash():
	runner = CliRunner()
	# 20-byte (40 hex chars) zero info hash
	ih = "0" * 40
	result = runner.invoke(recover, [ih, "--verify"])
	assert result.exit_code == 0, result.output


def test_placeholder_no_docs_command():
	# The docs command has been removed
	assert True


