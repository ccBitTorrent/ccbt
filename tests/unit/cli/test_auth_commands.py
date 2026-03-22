"""Unit tests for authenticated-swarm CLI command coverage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

cli_auth_commands = __import__("ccbt.cli.auth_commands", fromlist=["auth"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _build_auth_config_manager(
    tmp_path: Path, mode: str = "off"
) -> tuple[MagicMock, SimpleNamespace]:
    """Create a lightweight config manager and authenticated-swarms config."""
    auth_config = SimpleNamespace(
        mode=mode,
        discovery_mode="trackers_only",
        discovery_strict_for_strict_mode=True,
        trusted_swarm_ids=["aa11", "bb22"],
        fail_closed_on_parse_errors=False,
        trust_store_path=None,
        trust_store_refresh_interval_s=60.0,
        revocation_profile_path=None,
        revocation_refresh_interval_s=300.0,
    )
    security_config = SimpleNamespace(authenticated_swarms=auth_config)
    client_config = SimpleNamespace(security=security_config)
    manager = MagicMock()
    manager.config = client_config
    manager.config_file = tmp_path / "ccbt-auth.toml"
    manager.config_file.write_text("[security]\n", encoding="utf-8")
    manager.export = MagicMock(
        return_value="[security]\n[security.authenticated_swarms]\n"
    )
    return manager, auth_config


def _bind_cli_config_manager(monkeypatch, manager):
    """Patch config loading paths used by auth commands."""
    import sys
    config_module = __import__("ccbt.config.config", fromlist=["init_config"])

    main_module = sys.modules.get("ccbt.cli.main")
    if main_module is None:
        import ccbt.cli.main  # noqa: PLC0415
        main_module = sys.modules["ccbt.cli.main"]
    monkeypatch.setattr(main_module, "_get_config_from_context", lambda _ctx: manager)
    # If context is missing in future, init_config fallback path uses this.
    monkeypatch.setattr(config_module, "init_config", lambda: manager)
    auth_module = sys.modules.get("ccbt.cli.auth_commands")
    if auth_module is None:
        import ccbt.cli.auth_commands  # noqa: PLC0415
        auth_module = sys.modules["ccbt.cli.auth_commands"]
    monkeypatch.setattr(auth_module, "get_config", lambda: manager.config)


def test_auth_status_displays_values(monkeypatch, tmp_path):
    """status command prints values from authenticated swarms config."""
    manager, _ = _build_auth_config_manager(tmp_path, mode="strict")
    _bind_cli_config_manager(monkeypatch, manager)

    runner = CliRunner()
    result = runner.invoke(cli_auth_commands.auth, ["status"])

    assert result.exit_code == 0
    assert "Mode" in result.output
    assert "strict" in result.output
    assert "trackers_only" in result.output
    assert "Trust store path" in result.output


def test_auth_set_mode_updates_and_persists(monkeypatch, tmp_path):
    """set-mode updates runtime config and persists serialized toml."""
    manager, auth_config = _build_auth_config_manager(tmp_path, mode="off")
    _bind_cli_config_manager(monkeypatch, manager)

    runner = CliRunner()
    result = runner.invoke(cli_auth_commands.auth, ["set-mode", "strict"])

    assert result.exit_code == 0
    assert auth_config.mode == "strict"
    assert "Authenticated swarm mode set to strict" in result.output
    assert (tmp_path / "ccbt-auth.toml").exists()
    manager.export.assert_called_once()


def test_auth_set_trusted_ids_from_args(monkeypatch, tmp_path):
    """set-trusted-ids updates the trusted swarm list."""
    manager, auth_config = _build_auth_config_manager(tmp_path, mode="opportunistic")
    _bind_cli_config_manager(monkeypatch, manager)

    runner = CliRunner()
    result = runner.invoke(cli_auth_commands.auth, ["set-trusted-ids", "id-a", "id-b"])

    assert result.exit_code == 0
    assert auth_config.trusted_swarm_ids == ["id-a", "id-b"]
    assert "Updated trusted swarm IDs" in result.output

