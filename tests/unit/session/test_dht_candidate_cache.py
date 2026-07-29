from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _torrent_data() -> dict:
    return {
        "name": "dht-cache-test",
        "info_hash": b"3" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }


async def test_record_dht_candidate_intel_tracks_confidence_and_prunes(tmp_path) -> None:
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session._dht_candidate_cache_ttl_s = 0.1
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.1", "port": 6881, "peer_source": "dht"}],
        source="dht_callback",
    )
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"}],
        source="tracker",
    )
    key = "10.0.0.1:6881"
    assert key in session._dht_candidate_cache
    assert session._dht_candidate_cache[key]["confidence"] > 0.3
    session.prune_dht_candidate_intel(now=time.time() + 31.0)
    assert key not in session._dht_candidate_cache


async def test_select_dht_candidate_promotions_requires_deficit(tmp_path) -> None:
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.3", "port": 6999, "peer_source": "dht"}],
        source="dht_callback",
    )
    session._get_swarm_recovery_state = AsyncMock(  # type: ignore[method-assign]
        return_value={"requestable_peers": 0, "productive_peers": 0}
    )
    promoted = await session.select_dht_candidate_promotions(existing_peers=[])
    assert len(promoted) == 1
    assert promoted[0]["ip"] == "10.0.0.3"
    session._get_swarm_recovery_state = AsyncMock(  # type: ignore[method-assign]
        return_value={"requestable_peers": 1, "productive_peers": 1}
    )
    blocked = await session.select_dht_candidate_promotions(existing_peers=[])
    assert blocked == []


async def test_corroborated_candidate_outranks_dht_only(tmp_path) -> None:
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session._get_swarm_recovery_state = AsyncMock(  # type: ignore[method-assign]
        return_value={"requestable_peers": 0, "productive_peers": 0}
    )
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.10", "port": 7000}], source="dht_callback"
    )
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.11", "port": 7001}], source="dht_callback"
    )
    session.record_dht_candidate_intel(
        [{"ip": "10.0.0.11", "port": 7001}], source="tracker"
    )
    promoted = await session.select_dht_candidate_promotions(existing_peers=[])
    assert promoted
    assert promoted[0]["ip"] == "10.0.0.11"


async def test_dht_only_repeated_failures_get_penalized(tmp_path) -> None:
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session._get_swarm_recovery_state = AsyncMock(  # type: ignore[method-assign]
        return_value={"requestable_peers": 0, "productive_peers": 0}
    )
    peer = {"ip": "10.0.0.20", "port": 7010}
    session.record_dht_candidate_intel([peer], source="dht_callback")
    baseline = await session.select_dht_candidate_promotions(existing_peers=[])
    assert baseline and baseline[0]["ip"] == "10.0.0.20"
    session.record_dht_candidate_failure([peer], reason="connect_timeout")
    session.record_dht_candidate_failure([peer], reason="connect_timeout")
    session.record_dht_candidate_failure([peer], reason="connect_timeout")
    penalized = await session.select_dht_candidate_promotions(existing_peers=[])
    assert penalized == [] or penalized[0].get("_dht_candidate_score", 1.0) < baseline[0].get(
        "_dht_candidate_score", 0.0
    )


async def test_dht_only_source_cap_is_enforced(tmp_path) -> None:
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session._dht_candidate_promotion_cap = 6
    session._dht_candidate_promotion_cap_dht_only = 2
    session._get_swarm_recovery_state = AsyncMock(  # type: ignore[method-assign]
        return_value={"requestable_peers": 0, "productive_peers": 0}
    )
    for idx in range(6):
        session.record_dht_candidate_intel(
            [{"ip": f"10.0.1.{idx+1}", "port": 7100 + idx}], source="dht_callback"
        )
    promoted = await session.select_dht_candidate_promotions(existing_peers=[])
    assert len(promoted) == 2
