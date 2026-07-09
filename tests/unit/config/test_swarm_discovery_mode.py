from __future__ import annotations

import pytest

from ccbt.models import AuthenticatedSwarmsConfig, SecurityConfig, SwarmDiscoveryMode


@pytest.mark.unit
def test_authenticated_swarms_discovery_mode_defaults_to_trackers_only() -> None:
    cfg = AuthenticatedSwarmsConfig()
    assert cfg.discovery_mode == SwarmDiscoveryMode.TRACKERS_ONLY


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected_mode",
    [
        ("full", SwarmDiscoveryMode.FULL),
        ("trackers_only", SwarmDiscoveryMode.TRACKERS_ONLY),
        ("dht_only", SwarmDiscoveryMode.DHT_ONLY),
        ("pex_off", SwarmDiscoveryMode.PEX_OFF),
        ("trackers-only", SwarmDiscoveryMode.TRACKERS_ONLY),
        ("dht-only", SwarmDiscoveryMode.DHT_ONLY),
        ("pex-off", SwarmDiscoveryMode.PEX_OFF),
    ],
)
def test_authenticated_swarms_discovery_mode_accepts_each_enum_value(
    value: str,
    expected_mode: SwarmDiscoveryMode,
) -> None:
    cfg = AuthenticatedSwarmsConfig(discovery_mode=value)
    assert cfg.discovery_mode == expected_mode


@pytest.mark.unit
def test_security_config_exposes_authenticated_swarm_discovery_mode() -> None:
    cfg = SecurityConfig(authenticated_swarms={"discovery_mode": "full"})
    assert cfg.authenticated_swarms.discovery_mode == SwarmDiscoveryMode.FULL
