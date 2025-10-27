"""Tests for configuration CLI commands."""

from pathlib import Path

from click.testing import CliRunner

from ccbt.cli.config_commands import config as config_group


def test_config_show_and_get_json():
	runner = CliRunner()
	with runner.isolated_filesystem():
		# show default (toml) should succeed
		res1 = runner.invoke(config_group, ["show", "--format", "json"])
		assert res1.exit_code == 0, res1.output
		assert "network" in res1.output
		# get dotted key
		res2 = runner.invoke(config_group, ["get", "network.listen_port"])
		assert res2.exit_code == 0, res2.output


def test_config_set_get_and_reset():
	runner = CliRunner()
	with runner.isolated_filesystem():
		# set a value
		res_set = runner.invoke(
			config_group,
			["set", "network.listen_port", "7000", "--local"],
		)
		assert res_set.exit_code == 0, res_set.output
		assert Path("ccbt.toml").exists()
		# get reflects value
		res_get = runner.invoke(config_group, ["get", "network.listen_port"])
		assert res_get.exit_code == 0
		assert "7000" in res_get.output
		# reset
		res_reset = runner.invoke(config_group, ["reset", "--confirm"])
		assert res_reset.exit_code == 0
		# after reset, file exists but may be cleared; getting still works from defaults
		res_get2 = runner.invoke(config_group, ["get", "network.listen_port"])
		assert res_get2.exit_code == 0


def test_config_validate_and_migrate():
	runner = CliRunner()
	with runner.isolated_filesystem():
		# Create a minimal toml
		Path("ccbt.toml").write_text("[network]\nlisten_port=6881\n", encoding="utf-8")
		# validate
		res_val = runner.invoke(config_group, ["validate", "--config", "ccbt.toml"])
		assert res_val.exit_code == 0
		assert "VALID" in res_val.output
		# migrate (no-op)
		res_mig = runner.invoke(config_group, ["migrate", "--config", "ccbt.toml"]) 
		assert res_mig.exit_code == 0
		assert "MIGRATED" in res_mig.output


