"""Windows network limit clamps must tolerate string values from TOML/env merge."""

from __future__ import annotations

import importlib

import pytest

from ccbt.config.config import ConfigManager

config_module = importlib.import_module("ccbt.config.config")

_WIN_CAP_GLOBAL = 200
_WIN_CAP_POOL = 150
_WIN_CAP_PER_TORRENT = 100


@pytest.mark.unit
def test_windows_clamp_parses_string_max_global_peers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """String max_global_peers must not raise before Pydantic builds Config."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", True)
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {"network": {"max_global_peers": "500"}},
    )
    assert cfg.network.max_global_peers == _WIN_CAP_GLOBAL


@pytest.mark.unit
def test_simulate_load_strips_inline_comment_suffix_from_quoted_toml_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mis-quoted ``value  # doc`` fragments must coerce like plain numbers."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {
                "max_global_peers": "5000  # Maximum global peers (1-10000)",
                "listen_port": "64122  # Listen port (1024-65535)",
            },
        },
    )
    assert cfg.network.max_global_peers == 5000
    assert cfg.network.listen_port == 64122


@pytest.mark.unit
def test_windows_clamp_parses_string_connection_pool_and_per_torrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """String pool / per-torrent limits coerce for Windows caps."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", True)
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {
                "connection_pool_max_connections": "300",
                "max_peers_per_torrent": "150",
            },
        },
    )
    assert cfg.network.connection_pool_max_connections == _WIN_CAP_POOL
    assert cfg.network.max_peers_per_torrent == _WIN_CAP_PER_TORRENT


@pytest.mark.unit
def test_windows_clamp_can_be_disabled_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_module, "IS_WINDOWS", True)
    monkeypatch.setenv("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", "false")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {
                "max_global_peers": 500,
                "connection_pool_max_connections": 300,
                "max_peers_per_torrent": 150,
            },
        },
    )
    assert cfg.network.max_global_peers == 500
    assert cfg.network.connection_pool_max_connections == 300
    assert cfg.network.max_peers_per_torrent == 150
