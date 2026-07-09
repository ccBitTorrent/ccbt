"""Tests for MSE/encryption env overrides vs TOML (ConfigManager merge order)."""

from __future__ import annotations

import pytest

from ccbt.config.config import ConfigManager


@pytest.mark.unit
def test_ccbt_enable_encryption_env_overrides_toml_false(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env enables MSE when TOML has security.enable_encryption false."""
    monkeypatch.delenv("CCBT_ENABLE_ENCRYPTION", raising=False)
    config_file = tmp_path / "ccbt.toml"
    config_file.write_text(
        """
[security]
enable_encryption = false
encryption_mode = "preferred"

[network]
listen_port_tcp = 50000
listen_port_udp = 50000
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CCBT_ENABLE_ENCRYPTION", "true")

    manager = ConfigManager(config_file=config_file)

    assert manager.config.security.enable_encryption is True
    assert manager.config.network.enable_encryption is True


@pytest.mark.unit
def test_ccbt_enable_encryption_false_env_overrides_toml_true(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env false overrides TOML true for enable_encryption."""
    monkeypatch.delenv("CCBT_ENABLE_ENCRYPTION", raising=False)
    config_file = tmp_path / "ccbt.toml"
    config_file.write_text(
        """
[security]
enable_encryption = true
encryption_mode = "preferred"

[network]
listen_port_tcp = 50001
listen_port_udp = 50001
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CCBT_ENABLE_ENCRYPTION", "false")

    manager = ConfigManager(config_file=config_file)

    assert manager.config.security.enable_encryption is False


@pytest.mark.unit
def test_peer_quality_probation_timeout_env_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CCBT_PEER_QUALITY_PROBATION_TIMEOUT overrides [network] value."""
    monkeypatch.delenv("CCBT_PEER_QUALITY_PROBATION_TIMEOUT", raising=False)
    config_file = tmp_path / "ccbt.toml"
    config_file.write_text(
        """
[security]
enable_encryption = false

[network]
listen_port_tcp = 50002
listen_port_udp = 50002
peer_quality_probation_timeout = 45.0
""",
        encoding="utf-8",
    )
    expected_timeout = 120.0
    monkeypatch.setenv(
        "CCBT_PEER_QUALITY_PROBATION_TIMEOUT",
        str(int(expected_timeout)),
    )

    manager = ConfigManager(config_file=config_file)

    assert manager.config.network.peer_quality_probation_timeout == expected_timeout
