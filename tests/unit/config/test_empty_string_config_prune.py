"""Empty string scalars in merged config are dropped so Pydantic defaults apply."""

from __future__ import annotations

import importlib

import pytest

from ccbt.config.config import ConfigManager

config_module = importlib.import_module("ccbt.config.config")


@pytest.mark.unit
def test_simulate_load_drops_empty_strings_for_model_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``KEY=`` / whitespace from dotenv must not override defaults with ``''``."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {"xet_port": ""},
            "security": {"blacklist": {"default_expiration_hours": "  "}},
            "proxy": {"proxy_port": ""},
            "nat": {"map_xet_port": ""},
            "daemon": {"ipc_port": ""},
        },
    )
    assert cfg.network.xet_port is None
    assert cfg.security.blacklist.default_expiration_hours is None
    assert cfg.proxy.proxy_port is None
    assert cfg.nat.map_xet_port is True
    assert cfg.daemon.ipc_port == 64124
