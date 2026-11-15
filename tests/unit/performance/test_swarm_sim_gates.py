"""Acceptance gates for the virtual-swarm benchmark (plan Phase 7)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit]

from ccbt.performance.swarm_sim import make_peers, run_scenario, simulate


@pytest.mark.parametrize("peer_count", [20, 50, 100])
def test_acceleration_gates(peer_count):
    result = run_scenario(peer_count, seed=1234)
    base, treat = result["baseline"], result["treatment"]
    # Treatment must finish the straggler tail materially faster and
    # grow the requestable cohort faster, within the waste budget.
    assert treat["completion_s"] < base["completion_s"] * 0.75
    assert treat["time_to_first_requestable_s"] <= base["time_to_first_requestable_s"]
    assert treat["wasted_fraction"] <= 0.10


def test_deterministic():
    peers = make_peers(20, seed=99)
    a = simulate(peers=peers, duplicate_stragglers=True, dial_parallelism=24)
    b = simulate(peers=peers, duplicate_stragglers=True, dial_parallelism=24)
    assert a.as_dict() == b.as_dict()
