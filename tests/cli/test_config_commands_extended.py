from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ccbt.cli.main import cli


def test_list_templates_shows_table() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["config-extended", "list-templates"])
    assert result.exit_code == 0
    assert "Available Templates" in result.output


def test_list_profiles_shows_table() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["config-extended", "list-profiles"])
    assert result.exit_code == 0
    assert "Available Profiles" in result.output


def test_capabilities_default_and_summary() -> None:
    runner = CliRunner()
    # Default (group with no subcommand) should show table
    res_default = runner.invoke(cli, ["config-extended", "capabilities"])
    assert res_default.exit_code == 0
    assert "System Capabilities" in res_default.output

    # Summary subcommand
    res_summary = runner.invoke(cli, ["config-extended", "capabilities", "summary"])
    assert res_summary.exit_code == 0
    assert "System Capabilities" in res_summary.output


def test_diff_json_output(tmp_path: Path) -> None:
    file1 = tmp_path / "a.toml"
    file2 = tmp_path / "b.toml"
    file1.write_text("[network]\nlisten_port=6881\n", encoding="utf-8")
    file2.write_text("[network]\nlisten_port=6882\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config-extended",
            "diff",
            str(file1),
            str(file2),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    # Should be valid JSON
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)


