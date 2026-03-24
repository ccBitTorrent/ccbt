"""Effective max_peers precedence: file, profile, env, Windows clamp, per-torrent helper."""

from __future__ import annotations

import importlib

import pytest

from ccbt.config.config import (
    ConfigManager,
    resolve_effective_max_peers_per_torrent,
)
from ccbt.models import OptimizationProfile

config_module = importlib.import_module("ccbt.config.config")


@pytest.mark.unit
def test_profile_overlays_file_base_before_env() -> None:
    """Balanced profile replaces lower file cap before env merge."""
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {"max_peers_per_torrent": 40},
            "optimization": {"profile": "balanced"},
        }
    )
    assert cfg.optimization.profile == OptimizationProfile.BALANCED
    assert cfg.network.max_peers_per_torrent == 50


@pytest.mark.unit
def test_custom_profile_skips_overlay_keeping_file() -> None:
    """CUSTOM does not apply built-in network caps from other profiles."""
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {"max_peers_per_torrent": 41},
            "optimization": {"profile": "custom"},
        }
    )
    assert cfg.optimization.profile == OptimizationProfile.CUSTOM
    assert cfg.network.max_peers_per_torrent == 41


@pytest.mark.unit
def test_env_wins_over_profile_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment overrides profile-chosen caps (after overlay, env merge last)."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    monkeypatch.setenv("CCBT_MAX_PEERS_PER_TORRENT", "17")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "optimization": {"profile": "speed"},
        }
    )
    assert cfg.optimization.profile == OptimizationProfile.SPEED
    assert cfg.network.max_peers_per_torrent == 17


@pytest.mark.unit
def test_windows_clamp_after_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows compatibility clamp applies after env sets a high value."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", True)
    monkeypatch.delenv("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", raising=False)
    monkeypatch.setenv("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", "true")
    monkeypatch.setenv("CCBT_MAX_PEERS_PER_TORRENT", "500")
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict({})
    assert cfg.network.max_peers_per_torrent == 100


@pytest.mark.unit
def test_speed_profile_overrides_conflicting_file_network_intent() -> None:
    """Profile overlay wins over contradictions in the same file dict."""
    manager = ConfigManager.__new__(ConfigManager)
    cfg = manager.simulate_load_from_file_dict(
        {
            "network": {"max_peers_per_torrent": 25},
            "optimization": {"profile": "speed"},
        }
    )
    assert cfg.network.max_peers_per_torrent == 100


@pytest.mark.unit
def test_resolve_effective_per_torrent_replaces_network_cap() -> None:
    """Per-torrent option is final cap for the peer manager when provided."""
    assert (
        resolve_effective_max_peers_per_torrent(network_cap=80, per_torrent=12) == 12
    )
    assert (
        resolve_effective_max_peers_per_torrent(network_cap=80, per_torrent=None) == 80
    )


@pytest.mark.unit
def test_simulate_load_records_provenance_env_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provenance records when CCBT_MAX_PEERS_PER_TORRENT is set."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", False)
    monkeypatch.setenv("CCBT_MAX_PEERS_PER_TORRENT", "33")
    manager = ConfigManager.__new__(ConfigManager)
    manager.max_peers_per_torrent_provenance = None
    cfg = manager.simulate_load_from_file_dict(
        {"optimization": {"profile": "balanced"}}
    )
    prov = manager.max_peers_per_torrent_provenance
    assert prov is not None
    assert prov.final == cfg.network.max_peers_per_torrent == 33
    assert prov.env_ccbt_max_peers_per_torrent_set is True
    assert prov.windows_platform_clamp_applied_to_mpt is False


@pytest.mark.unit
def test_simulate_load_records_provenance_windows_mpt_clamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provenance flags Windows clamp when env pushes MPT above strict cap."""
    monkeypatch.setattr(config_module, "IS_WINDOWS", True)
    monkeypatch.delenv("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", raising=False)
    monkeypatch.setenv("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", "true")
    monkeypatch.setenv("CCBT_MAX_PEERS_PER_TORRENT", "500")
    manager = ConfigManager.__new__(ConfigManager)
    manager.max_peers_per_torrent_provenance = None
    cfg = manager.simulate_load_from_file_dict({})
    prov = manager.max_peers_per_torrent_provenance
    assert prov is not None
    assert cfg.network.max_peers_per_torrent == 100
    assert prov.final == 100
    assert prov.windows_platform_clamp_applied_to_mpt is True
    assert prov.value_after_env == 500
    assert prov.value_after_platform_clamp == 100
