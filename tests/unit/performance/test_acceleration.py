"""Unit tests for download-acceleration helpers and wiring."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit]

from ccbt.extensions.manager import ExtensionManager
from ccbt.extensions.pex import PEXPeer, PeerExchange
from ccbt.peer.async_peer_connection import AsyncPeerConnection
from ccbt.peer.peer import PeerInfo
from ccbt.performance.acceleration import (
    BlockLatencyTracker,
    DuplicateBudget,
    RampMetrics,
    accel_enabled,
    adaptive_request_timeout,
    adaptive_upload_slots,
    is_dynamic_endgame,
    is_snubbed,
    peer_usefulness_score,
    race_first_success,
    ramp_choking_intervals,
    should_duplicate_block,
    strategy_flag,
    warm_pipeline_depth,
)
from ccbt.piece.async_piece_manager import AsyncPieceManager


def test_acceleration_on_by_default():
    from types import SimpleNamespace

    # Missing attribute (legacy/partial config) means enabled.
    assert accel_enabled(SimpleNamespace()) is True
    assert accel_enabled(SimpleNamespace(network=SimpleNamespace())) is True
    assert (
        accel_enabled(
            SimpleNamespace(
                network=SimpleNamespace(swarm_acceleration_enabled=False)
            )
        )
        is False
    )
    assert strategy_flag(SimpleNamespace(), "straggler_duplication_enabled") is True
    # Effective shipped config: enabled by default.
    from ccbt.config.config import get_config

    cfg = get_config()
    assert cfg.network.swarm_acceleration_enabled is True
    assert cfg.strategy.straggler_duplication_enabled is True
    assert cfg.discovery.min_peers_before_dht == 2


@pytest.mark.asyncio
async def test_race_first_success_picks_fastest_and_tolerates_failure():
    import asyncio

    async def fast():
        await asyncio.sleep(0.01)
        return "fast-result"

    async def slow():
        await asyncio.sleep(5)
        return "slow-result"

    async def broken():
        raise ConnectionError("nope")

    kind, payload = await race_first_success(
        {"slow": slow(), "broken": broken(), "fast": fast()}
    )
    assert (kind, payload) == ("fast", "fast-result")

    with pytest.raises(ConnectionError):
        await race_first_success({"broken": broken()})


def test_adaptive_timeout_clamps():
    assert adaptive_request_timeout(0) == 30.0
    assert adaptive_request_timeout(0.1) == 5.0  # floor
    assert adaptive_request_timeout(2.0) == 8.0
    assert adaptive_request_timeout(100.0) == 30.0  # ceiling


def test_duplicate_budget_caps_at_fraction():
    budget = DuplicateBudget(max_fraction=0.10)
    budget.record_useful(900)
    assert budget.allows(100)
    budget.record_duplicate(100)
    assert not budget.allows(1)
    assert budget.wasted_fraction == pytest.approx(0.1)


def test_should_duplicate_straggler_and_last_block():
    assert should_duplicate_block(
        block_age_s=5, swarm_p90_latency_s=1.0, blocks_remaining_in_piece=8,
        existing_copies=1,
    )
    assert should_duplicate_block(
        block_age_s=2, swarm_p90_latency_s=60.0, blocks_remaining_in_piece=1,
        existing_copies=1,
    )
    assert not should_duplicate_block(
        block_age_s=0.1, swarm_p90_latency_s=1.0, blocks_remaining_in_piece=8,
        existing_copies=1,
    )
    assert not should_duplicate_block(
        block_age_s=99, swarm_p90_latency_s=1.0, blocks_remaining_in_piece=8,
        existing_copies=3, max_copies=3,
    )
    assert not should_duplicate_block(
        block_age_s=99, swarm_p90_latency_s=1.0, blocks_remaining_in_piece=8,
        existing_copies=1, budget_allows=False,
    )


def test_dynamic_endgame():
    assert is_dynamic_endgame(remaining_pieces=5, total_pieces=1000)
    assert is_dynamic_endgame(remaining_pieces=50, total_pieces=1000)
    assert not is_dynamic_endgame(remaining_pieces=10, total_pieces=10)
    assert not is_dynamic_endgame(remaining_pieces=100, total_pieces=1000)
    assert is_dynamic_endgame(
        remaining_pieces=100, total_pieces=1000, all_remaining_stalled=True
    )


def test_snub_and_usefulness_and_slots():
    assert is_snubbed(
        seconds_since_payload=20, seconds_unchoked=20, others_delivering=True
    )
    assert not is_snubbed(
        seconds_since_payload=20, seconds_unchoked=20, others_delivering=False
    )
    good = peer_usefulness_score(has_needed_piece=True, historic_unchoke_rate=1.0)
    bad = peer_usefulness_score(seconds_since_failure=1.0, is_snubbed_peer=True)
    assert good > bad
    assert adaptive_upload_slots(
        base_slots=8, upload_rate_bps=5 * 512 * 1024,
        requestable_peers=0, requestable_target=10,
    ) > 8
    assert ramp_choking_intervals(
        requestable_peers=0, requestable_target=10
    ) == (5.0, 20.0)
    assert ramp_choking_intervals(
        requestable_peers=10, requestable_target=10
    ) == (10.0, 30.0)
    assert warm_pipeline_depth(current_depth=16) == 32
    assert warm_pipeline_depth(current_depth=16, bdp_blocks=64) == 64


def test_latency_tracker_and_ramp_metrics():
    tracker = BlockLatencyTracker()
    for v in (0.1, 0.2, 0.3, 10.0):
        tracker.record(v)
    assert tracker.p50 > 0
    assert tracker.p95 >= tracker.p50
    metrics = RampMetrics(started_monotonic=100.0)
    metrics.touch_requestable(3, now=104.0)
    metrics.touch_first_piece(now=106.0)
    metrics.touch_progress(0.55, now=120.0)
    snap = metrics.snapshot()
    assert snap["time_to_first_requestable_s"] == 4.0
    assert snap["time_to_first_piece_s"] == 6.0
    assert snap["time_to_50pct_s"] == 20.0
    assert snap["time_to_90pct_s"] is None


def _connection(ip="10.0.0.1", port=6881):
    conn = AsyncPeerConnection(
        peer_info=PeerInfo(ip=ip, port=port), torrent_data={}
    )
    from ccbt.peer.async_peer_connection import ConnectionState

    conn.state = ConnectionState.ACTIVE
    return conn


def test_allow_fast_bypasses_choke_only_for_allowed_piece():
    conn = _connection()
    conn.peer_choking = True
    assert conn.can_request() is False
    assert conn.can_request(piece_index=3) is False
    conn.peer_state.bep6_allowed_fast_pieces.add(3)
    assert conn.can_request(piece_index=3) is True
    assert conn.get_request_block_reason(piece_index=4) == "remote_choked"


def test_speculative_timeout_cap_skips_cold_start():
    """Deep queue alone must not shrink cold-start handshake budgets."""
    from types import SimpleNamespace

    from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

    manager = AsyncPeerConnectionManager(
        torrent_data={"info_hash": b"\x00" * 20},
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=10,
    )
    manager._pending_peer_queue = [object()] * 250  # noqa: SLF001
    # No active peers: legacy deep-queue cap (42s) applies, not the 20s
    # speculative cap.
    assert manager._cap_connect_task_timeout_s(130.0) == 42.0  # noqa: SLF001


@pytest.mark.asyncio
async def test_pex_callback_dials_new_peers():
    exchange = PeerExchange()
    seen = []
    exchange.add_peer_discovered_callback(seen.append)
    await exchange.handle_added_peers("peer-a", [PEXPeer("10.0.0.9", 6881)])
    assert seen and seen[0][0].ip == "10.0.0.9"
    # Second time: no new peers, callback not re-fired with duplicates.
    seen.clear()
    await exchange.handle_added_peers("peer-a", [PEXPeer("10.0.0.9", 6881)])
    assert seen == []

    manager = ExtensionManager()
    seen2 = []
    manager.register_pex_peer_callback(seen2.append)
    await manager.handle_pex_message("p", 0, b"")
    # manager path exercised without error; direct exchange covered above


@pytest.mark.asyncio
async def test_straggler_duplication_sends_one_extra_copy():
    torrent_data = {
        "info_hash": b"\x00" * 20,
        "pieces_info": {
            "num_pieces": 4,
            "piece_length": 65536,
            "piece_hashes": [b"\x00" * 20] * 4,
        },
    }
    manager = AsyncPieceManager(torrent_data)
    try:
        if not manager.pieces:
            manager._build_piece_layout()
        piece = manager.pieces[0]
        block = piece.blocks[0]
        manager._duplicate_budget.record_useful(10 * 1024 * 1024)
        old_key = "10.0.0.1:6881"
        block.requested_from.add(old_key)
        manager._active_block_requests[0] = {
            old_key: [(block.begin, block.length, time.time() - 100.0)]
        }
        candidate = Mock()
        candidate.peer_info = PeerInfo(ip="10.0.0.2", port=6881)
        candidate.can_request = Mock(return_value=True)
        peer_manager = Mock()
        peer_manager.request_piece = AsyncMock(return_value=True)

        sent = await manager._request_straggler_duplicates(
            0, [candidate], peer_manager
        )
        assert sent == 1
        peer_manager.request_piece.assert_awaited_once()
        assert manager._piece_selection_metrics["duplicate_requests"] == 1
        # Budget exhausted -> no further duplication.
        manager._duplicate_budget.record_useful(0)
        manager._duplicate_budget.duplicate_bytes = 10**9
        block2 = piece.blocks[1]
        block2.requested_from.add(old_key)
        manager._active_block_requests[0][old_key].append(
            (block2.begin, block2.length, time.time() - 100.0)
        )
        sent2 = await manager._request_straggler_duplicates(
            0, [candidate], peer_manager
        )
        assert sent2 == 0
    finally:
        await manager.stop()
