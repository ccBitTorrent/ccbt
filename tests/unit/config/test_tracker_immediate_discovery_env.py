"""Discovery tracker-immediate burst env mapping and model defaults."""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError

from ccbt.config.config import ConfigManager
from ccbt.models import Config, DiscoveryConfig

config_module = importlib.import_module("ccbt.config.config")


@pytest.mark.unit
def test_discovery_defaults_tracker_immediate_burst() -> None:
    """Immediate burst defaults limit tracker-callback connect pressure."""
    cfg = Config()
    assert cfg.discovery.tracker_immediate_connect_burst_total == 50
    assert cfg.discovery.tracker_immediate_connect_burst_per_source == 50


@pytest.mark.unit
def test_env_maps_tracker_immediate_connect_burst_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_* merge into discovery config."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_TOTAL", "48")
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_PER_SOURCE", "12")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict({})
    assert cfg.discovery.tracker_immediate_connect_burst_total == 48
    assert cfg.discovery.tracker_immediate_connect_burst_per_source == 12


@pytest.mark.unit
def test_discovery_defaults_tracker_immediate_window_and_per_source_mode() -> None:
    """Circuit-breaker window and per-source cap mode defaults match legacy behavior."""
    cfg = Config()
    assert cfg.discovery.tracker_immediate_connect_window_s == 20.0
    assert cfg.discovery.tracker_immediate_connect_window_cap == 6
    assert cfg.discovery.tracker_immediate_per_source_cap_mode == "full_max_peers"
    assert cfg.network.mse_initiator_timeout_scale_zero_active == 1.0


@pytest.mark.unit
def test_env_maps_tracker_immediate_window_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_* merge into discovery config."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_S", "35")
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_CAP", "8")
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_PER_SOURCE_CAP_MODE", "full_max_peers")
    monkeypatch.setenv("CCBT_MSE_INITIATOR_TIMEOUT_SCALE_ZERO_ACTIVE", "0.5")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict({})
    assert cfg.discovery.tracker_immediate_connect_window_s == 35.0
    assert cfg.discovery.tracker_immediate_connect_window_cap == 8
    assert cfg.discovery.tracker_immediate_per_source_cap_mode == "full_max_peers"
    assert cfg.network.mse_initiator_timeout_scale_zero_active == 0.5


@pytest.mark.unit
def test_env_maps_tracker_per_tracker_cooldown_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-tracker immediate cooldown flag should map via env merge."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    monkeypatch.setenv("CCBT_TRACKER_IMMEDIATE_PER_TRACKER_COOLDOWN_ENABLED", "false")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict({})
    assert cfg.discovery.tracker_immediate_per_tracker_cooldown_enabled is False


@pytest.mark.unit
def test_tracker_immediate_per_source_cap_mode_invalid() -> None:
    """Invalid per-source cap mode is rejected at validation."""
    with pytest.raises(ValidationError):
        DiscoveryConfig(tracker_immediate_per_source_cap_mode="invalid_mode")
