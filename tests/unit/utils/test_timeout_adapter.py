"""Tests for adaptive timeout calculator (swarm health signals)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from ccbt.models import AdaptiveTimeoutHealthPeerSource, SwarmTimeoutSignals
from ccbt.peer.async_peer_connection import ConnectionState
from ccbt.utils.timeout_adapter import AdaptiveTimeoutCalculator


def _config(
    *,
    health_source: str
    | AdaptiveTimeoutHealthPeerSource = AdaptiveTimeoutHealthPeerSource.EFFECTIVE,
    desperation_max: int = 5,
    normal_max: int = 20,
    dht_adaptive: bool = True,
    handshake_adaptive: bool = True,
) -> SimpleNamespace:
    network = SimpleNamespace(
        handshake_adaptive_timeout_enabled=handshake_adaptive,
        handshake_timeout_desperation_min=10.0,
        handshake_timeout_desperation_max=20.0,
        handshake_timeout_normal_min=15.0,
        handshake_timeout_normal_max=30.0,
        handshake_timeout_healthy_min=20.0,
        handshake_timeout_healthy_max=40.0,
        handshake_timeout=10.0,
        dht_timeout=2.0,
        adaptive_timeout_health_peer_source=health_source,
        adaptive_timeout_desperation_max_peers=desperation_max,
        adaptive_timeout_normal_max_peers=normal_max,
        handshake_timeout_desperation_interpolate=False,
    )
    discovery = SimpleNamespace(
        dht_adaptive_timeout_enabled=dht_adaptive,
        dht_timeout_desperation_min=30.0,
        dht_timeout_desperation_max=60.0,
        dht_timeout_normal_min=5.0,
        dht_timeout_normal_max=15.0,
        dht_timeout_healthy_min=10.0,
        dht_timeout_healthy_max=30.0,
    )
    return SimpleNamespace(network=network, discovery=discovery)


def test_handshake_desperation_interpolates_when_enabled() -> None:
    """Zero effective peers use min timeout; mid-desperation scales toward max."""

    class _PM:
        def get_swarm_timeout_signals(self) -> SwarmTimeoutSignals:
            return SwarmTimeoutSignals(
                active_post_handshake_count=0,
                transport_live_count=0,
                requestable_count=0,
                total_connections=0,
            )

    cfg = _config()
    cfg.network.handshake_timeout_desperation_interpolate = True
    cfg.network.handshake_timeout_desperation_min = 25.0
    cfg.network.handshake_timeout_desperation_max = 45.0
    calc = AdaptiveTimeoutCalculator(cfg, peer_manager=_PM())
    assert calc.calculate_handshake_timeout() == pytest.approx(25.0)

    class _PM2:
        def get_swarm_timeout_signals(self) -> SwarmTimeoutSignals:
            return SwarmTimeoutSignals(
                active_post_handshake_count=2,
                transport_live_count=0,
                requestable_count=0,
                total_connections=2,
            )

    calc2 = AdaptiveTimeoutCalculator(cfg, peer_manager=_PM2())
    # desperation_max=5 -> span=4, effective=2 -> ratio 0.5 -> 25 + 20*0.5 = 35
    assert calc2.calculate_handshake_timeout() == pytest.approx(35.0)


def test_handshake_desperation_interpolate_false_uses_band_max_only() -> None:
    """Interpolate=False uses desperation max only (legacy band behavior)."""

    class _PM:
        def get_swarm_timeout_signals(self) -> SwarmTimeoutSignals:
            return SwarmTimeoutSignals(
                active_post_handshake_count=0,
                transport_live_count=0,
                requestable_count=0,
                total_connections=0,
            )

    cfg = _config()
    cfg.network.handshake_timeout_desperation_interpolate = False
    cfg.network.handshake_timeout_desperation_min = 25.0
    cfg.network.handshake_timeout_desperation_max = 55.0
    calc = AdaptiveTimeoutCalculator(cfg, peer_manager=_PM())
    assert calc.calculate_handshake_timeout() == pytest.approx(55.0)


def test_handshake_timeout_uses_transport_when_effective() -> None:
    """Handshake batch in flight: transport_live lifts health out of desperation."""

    class _PM:
        def get_swarm_timeout_signals(self) -> SwarmTimeoutSignals:
            return SwarmTimeoutSignals(
                active_post_handshake_count=0,
                transport_live_count=8,
                requestable_count=0,
                total_connections=8,
            )

    calc = AdaptiveTimeoutCalculator(_config(), peer_manager=_PM())
    t = calc.calculate_handshake_timeout()
    # normal band: ratio (8-5)/15 -> interpolate between 15 and 30
    assert t == pytest.approx(18.0)


def test_handshake_timeout_active_only_ignores_transport() -> None:
    class _PM:
        def get_swarm_timeout_signals(self) -> SwarmTimeoutSignals:
            return SwarmTimeoutSignals(
                active_post_handshake_count=0,
                transport_live_count=8,
                requestable_count=0,
                total_connections=8,
            )

    calc = AdaptiveTimeoutCalculator(
        _config(health_source=AdaptiveTimeoutHealthPeerSource.ACTIVE_ONLY),
        peer_manager=_PM(),
    )
    t = calc.calculate_handshake_timeout()
    assert t == 20.0  # desperation max


def test_fallback_get_active_peers_without_swarm_signals() -> None:
    class _PM:
        def get_active_peers(self) -> list[object]:
            return [object()]

    calc = AdaptiveTimeoutCalculator(_config(), peer_manager=_PM())
    t = calc.calculate_handshake_timeout()
    assert t == 20.0  # single active peer -> desperation band max


def test_fallback_connections_dict() -> None:
    conn = MagicMock()
    conn.state = ConnectionState.CONNECTING
    conn.reader = object()
    conn.writer = object()

    class _PM:
        connections = {"a": conn}

    calc = AdaptiveTimeoutCalculator(_config(), peer_manager=_PM())
    t = calc.calculate_dht_timeout()
    assert t == 60.0  # one connection -> desperation uses max DHT timeout


def test_no_peer_manager_uses_base_dht_timeout() -> None:
    cfg = _config(dht_adaptive=False)
    calc = AdaptiveTimeoutCalculator(cfg, peer_manager=None)
    assert calc.calculate_dht_timeout() == 2.0


def test_dht_timeout_capped_when_shutting_down_non_adaptive() -> None:
    from ccbt.utils.shutdown import clear_shutdown, set_shutdown

    set_shutdown()
    try:
        cfg = _config(dht_adaptive=False)
        calc = AdaptiveTimeoutCalculator(cfg, peer_manager=None)
        assert calc.calculate_dht_timeout() == 1.0
    finally:
        clear_shutdown()


def test_dht_timeout_capped_when_shutting_down_adaptive() -> None:
    from ccbt.utils.shutdown import clear_shutdown, set_shutdown

    set_shutdown()
    try:
        calc = AdaptiveTimeoutCalculator(_config(), peer_manager=None)
        assert calc.calculate_dht_timeout() == 1.0
    finally:
        clear_shutdown()
