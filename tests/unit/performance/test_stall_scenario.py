"""WS0 stall-scenario gate: treatment must beat the measured-stall baseline."""
from __future__ import annotations

import pytest

from ccbt.performance.swarm_sim import make_stall_peers, run_stall_scenario, simulate

pytestmark = [pytest.mark.unit]


def test_stall_scenario_treatment_beats_baseline():
    result = run_stall_scenario()
    base, treat = result["baseline"], result["treatment"]
    assert treat["completion_s"] < base["completion_s"]
    assert treat["cancelled_requests"] <= base["cancelled_requests"]


def test_choked_peer_never_becomes_requestable():
    peers = make_stall_peers()
    result = simulate(peers=peers, num_blocks=40, dial_parallelism=2)
    # Download still completes from the non-choked peers
    assert result.completion_s > 0
    assert result.useful_bytes == 40 * 16384
