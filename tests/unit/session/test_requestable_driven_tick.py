"""Requestable-driven discovery tick (Project 7-E)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.session.dht_setup import DHTDiscoverySetup


@pytest.mark.asyncio
async def test_tick_requestable_driven_ensure_bootstrap_when_zero_requestable() -> None:
    disc = SimpleNamespace(
        requestable_driven_discovery_enabled=True,
        enable_dht=True,
        target_requestable_peers=8,
        requestable_tick_interval_s=15.0,
        requestable_force_dht_when_zero=True,
        max_connect_burst_per_tick=8,
    )
    session = SimpleNamespace(
        info=SimpleNamespace(name="t1", private=False),
        logger=logging.getLogger("test_rq_tick"),
        config=SimpleNamespace(discovery=disc),
        is_private=False,
        download_manager=SimpleNamespace(
            peer_manager=MagicMock(
                _resume_pending_batches=AsyncMock(return_value=None),
            )
        ),
        stopped=False,
    )

    async def _swarm() -> dict[str, object]:
        return {
            "requestable_peers": 0,
            "active_peers": 2,
            "metadata_incomplete": False,
        }

    session.get_swarm_recovery_state = _swarm

    setup = DHTDiscoverySetup(session)
    dht = MagicMock()
    dht.routing_table = SimpleNamespace(nodes={})

    with patch.object(
        DHTDiscoverySetup,
        "_ensure_bootstrap_ready",
        new_callable=AsyncMock,
        return_value=1,
    ) as mock_ensure:
        await setup.tick_requestable_driven(dht, reason="unit")

    mock_ensure.assert_awaited_once()
    session.download_manager.peer_manager._resume_pending_batches.assert_awaited()


@pytest.mark.asyncio
async def test_tick_requestable_driven_recovers_below_redundancy_floor() -> None:
    """Two suppliers should still trigger DHT and complementary discovery pressure."""
    disc = SimpleNamespace(
        requestable_driven_discovery_enabled=True,
        enable_dht=True,
        target_requestable_peers=8,
        requestable_tick_interval_s=15.0,
        requestable_force_dht_when_zero=True,
        max_connect_burst_per_tick=8,
    )
    peer_manager = MagicMock(_resume_pending_batches=AsyncMock(return_value=None))
    session = SimpleNamespace(
        info=SimpleNamespace(name="t2", private=False),
        logger=logging.getLogger("test_rq_redundancy"),
        config=SimpleNamespace(discovery=disc),
        is_private=False,
        download_manager=SimpleNamespace(peer_manager=peer_manager),
        stopped=False,
    )

    async def _swarm() -> dict[str, object]:
        return {
            "requestable_peers": 2,
            "active_peers": 3,
            "metadata_incomplete": False,
        }

    session.get_swarm_recovery_state = _swarm
    setup = DHTDiscoverySetup(session)
    dht = MagicMock()
    dht.routing_table = SimpleNamespace(nodes={})

    with (
        patch.object(
            DHTDiscoverySetup,
            "_ensure_bootstrap_ready",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_ensure,
        patch.object(
            DHTDiscoverySetup,
            "_maybe_run_discovery_complements",
            new_callable=AsyncMock,
        ) as mock_complements,
    ):
        await setup.tick_requestable_driven(dht, reason="unit")

    mock_ensure.assert_awaited_once()
    mock_complements.assert_awaited_once_with("requestable_driven_redundancy_shortfall")
    peer_manager._resume_pending_batches.assert_awaited()
