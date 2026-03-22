"""Regression tests for DHT bootstrap seed replay behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from ccbt.session.dht_setup import DHTDiscoverySetup


class _RoutingTable:
    def __init__(self) -> None:
        self.nodes: dict[tuple[str, int], object] = {}


class _DHTClient:
    def __init__(self, seeds: list[tuple[str, int]]) -> None:
        self.routing_table = _RoutingTable()
        self.bootstrap_nodes = seeds
        self.bootstrap_calls: list[tuple[str, list[tuple[str, int]]]] = []

    async def _bootstrap(self, reason: str) -> None:
        self.bootstrap_calls.append((reason, list(self.bootstrap_nodes)))


@pytest.mark.asyncio
async def test_dht_bootstrap_configuration_controls_are_honored() -> None:
    """Session discovery settings should flow into DHT bootstrap timeout controls."""
    session = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
        info=SimpleNamespace(name="dht-config-controls"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                dht_rebootstrap_timeout_s=11.0,
                dht_bootstrap_timeout_s=13.0,
                bootstrap_seed_replay_limit=4,
                dht_bootstrap_retries_max=5,
                bootstrap_retry_memo_ttl_s=44.0,
                dht_bootstrap_memo_ttl_s=160.0,
                dht_empty_state_backoff_factor=2.0,
                dht_zero_state_reprobe_wait_s=52.0,
                low_peer_threshold=2,
                low_peer_suppression_window_s=12.0,
            )
        ),
    )
    setup = DHTDiscoverySetup(session)

    assert setup._dht_rebootstrap_timeout_s == 11.0
    assert setup._dht_bootstrap_timeout_s == 13.0
    assert setup._bootstrap_seed_replay_limit == 4
    assert setup._dht_bootstrap_retries_max == 5
    assert setup._dht_empty_state_backoff_factor == 2.0


@pytest.mark.asyncio
async def test_dht_bootstrap_seed_replay_rotates_after_failures() -> None:
    """Repeated bootstrap seed replays should rotate candidate order to spread load."""
    session = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
        info=SimpleNamespace(name="seed-replay-test"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(bootstrap_seed_replay_limit=6),
        ),
    )
    setup = DHTDiscoverySetup(session)

    seeds = [
        ("198.51.100.1", 6881),
        ("198.51.100.2", 6881),
        ("198.51.100.3", 6881),
    ]
    client = _DHTClient(seeds)

    await setup._run_bootstrap_with_fallback(
        client,
        reason="empty_routing_table unit",
        timeout=0.1,
        min_nodes=1,
        force_bootstrap=True,
    )
    await setup._run_bootstrap_with_fallback(
        client,
        reason="empty_routing_table unit",
        timeout=0.1,
        min_nodes=1,
        force_bootstrap=True,
    )

    assert client.bootstrap_calls == [
        ("empty_routing_table unit:seed_replay", seeds),
        (
            "empty_routing_table unit:seed_replay",
            [seeds[1], seeds[2], seeds[0]],
        ),
    ]
    summary = setup._get_rebootstrap_health_summary()
    assert summary["routing_table_size"] == 0
    assert summary["rebootstrap_last_before_nodes"] == 0
    assert summary["rebootstrap_last_after_nodes"] == 0
    assert summary["rebootstrap_last_attempted_nodes"] == 3
    assert summary["rebootstrap_last_source"] == "seed_replay"
    assert summary["rebootstrap_last_reason"].endswith(":seed_replay")


@pytest.mark.asyncio
async def test_dht_bootstrap_no_response_triggers_seed_fallback() -> None:
    """Rebootstrap timeout should force seed replay fallback and report seed_fallback."""

    class _NoResponseClient:
        def __init__(self, seeds: list[tuple[str, int]]) -> None:
            self.bootstrap_nodes = seeds
            self.routing_table = SimpleNamespace(nodes={})
            self.bootstrap_calls: list[tuple[str, list[tuple[str, int]]]] = []
            self.rebootstrap_calls = 0

        async def rebootstrap(self) -> None:
            self.rebootstrap_calls += 1
            await asyncio.sleep(1.0)

        async def _bootstrap(self, reason: str) -> None:
            self.bootstrap_calls.append((reason, list(self.bootstrap_nodes)))

    session = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
        info=SimpleNamespace(name="bootstrap-no-response"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=6,
            )
        ),
    )
    setup = DHTDiscoverySetup(session)
    client = _NoResponseClient([("198.51.100.8", 6881)])

    succeeded = await setup._run_bootstrap_with_fallback(
        client,
        reason="empty_routing_table unit",
        timeout=0.05,
        min_nodes=1,
        force_bootstrap=True,
    )
    summary = setup._get_rebootstrap_health_summary()

    assert succeeded is False
    assert client.rebootstrap_calls == 1
    assert client.bootstrap_calls == [
        ("empty_routing_table unit:seed_replay", [("198.51.100.8", 6881)])
    ]
    assert summary["rebootstrap_last_source"] == "seed_replay"
    assert summary["rebootstrap_last_reason"].endswith(":seed_fallback")
    assert summary["rebootstrap_last_before_nodes"] == 0
    assert summary["rebootstrap_last_after_nodes"] == 0
    assert summary["rebootstrap_last_attempted_nodes"] == 1
    assert summary["routing_table_size"] == 0


@pytest.mark.asyncio
async def test_dht_bootstrap_zero_node_fallback_records_failure() -> None:
    """No discovered nodes should return false and report seed fallback state."""

    class _ZeroNodeClient:
        def __init__(self, seeds: list[tuple[str, int]]) -> None:
            self.bootstrap_nodes = seeds
            self.routing_table = SimpleNamespace(nodes={})
            self.bootstrap_calls: list[str] = []
            self.wait_for_bootstrap_calls = 0

        async def wait_for_bootstrap(self, timeout: float) -> bool:
            self.wait_for_bootstrap_calls += 1
            return False

        async def _bootstrap(self, reason: str) -> None:
            self.bootstrap_calls.append(reason)

    session = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
        info=SimpleNamespace(name="bootstrap-zero-nodes"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=6,
            )
        ),
    )
    setup = DHTDiscoverySetup(session)
    client = _ZeroNodeClient([("198.51.100.9", 6881), ("198.51.100.10", 6881)])

    succeeded = await setup._run_bootstrap_with_fallback(
        client,
        reason="query_zero_nodes unit",
        timeout=0.05,
        min_nodes=1,
        force_bootstrap=True,
    )
    summary = setup._get_rebootstrap_health_summary()

    assert succeeded is False
    assert client.wait_for_bootstrap_calls == 1
    assert client.bootstrap_calls == ["query_zero_nodes unit:seed_replay"]
    assert summary["rebootstrap_last_source"] == "seed_replay"
    assert summary["rebootstrap_last_reason"].endswith(":seed_fallback")
    assert summary["rebootstrap_last_before_nodes"] == 0
    assert summary["rebootstrap_last_after_nodes"] == 0
    assert summary["rebootstrap_last_attempted_nodes"] == 2
    assert summary["routing_table_size"] == 0


@pytest.mark.asyncio
async def test_dht_bootstrap_delayed_seed_replay_eventually_succeeds() -> None:
    """Seed replay with delayed node insertion should still be recovered within bootstrap timeout."""

    class _DelayedNodeClient:
        def __init__(self, seeds: list[tuple[str, int]]) -> None:
            self.bootstrap_nodes = seeds
            self.routing_table = SimpleNamespace(nodes={})
            self.bootstrap_calls: list[str] = []
            self.wait_for_bootstrap_calls = 0

        async def wait_for_bootstrap(self, timeout: float) -> bool:
            self.wait_for_bootstrap_calls += 1
            return False

        async def _bootstrap(self, reason: str) -> None:
            self.bootstrap_calls.append(reason)
            await asyncio.sleep(0.01)
            self.routing_table.nodes[("198.51.100.11", 6881)] = object()

    session = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
        info=SimpleNamespace(name="bootstrap-delayed-node"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=6,
            )
        ),
    )
    setup = DHTDiscoverySetup(session)
    client = _DelayedNodeClient([("198.51.100.11", 6881)])

    succeeded = await setup._run_bootstrap_with_fallback(
        client,
        reason="query_zero_nodes unit",
        timeout=0.25,
        min_nodes=1,
        force_bootstrap=True,
    )
    summary = setup._get_rebootstrap_health_summary()

    assert succeeded is True
    assert client.wait_for_bootstrap_calls == 1
    assert client.bootstrap_calls == ["query_zero_nodes unit:seed_replay"]
    assert len(client.routing_table.nodes) == 1
    assert summary["rebootstrap_last_source"] == "seed_replay"
    assert summary["rebootstrap_last_reason"].endswith(":seed_replay")
    assert summary["rebootstrap_last_after_nodes"] == 1
    assert summary["routing_table_size"] == 1

