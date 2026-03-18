"""Regression tests for DHT recovery deadlocks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ccbt.utils.events import PeerCountLowEvent


pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_peer_count_low_event_exposes_legacy_and_canonical_keys() -> None:
    """peer_count_low events should publish both active peer count key variants."""
    event = PeerCountLowEvent(active_peers=3, info_hash=b"\x01" * 20, total_peers=9)

    assert event.data["active_peers"] == 3
    assert event.data["active_peer_count"] == 3
    assert event.data["total_peers"] == 9


@pytest.mark.asyncio
async def test_dht_discovery_loop_bypasses_batch_wait_when_zero_peers(
    monkeypatch,
) -> None:
    """Zero active peers should bypass lingering batch state and reach DHT recovery immediately."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    sleep_calls = 0

    async def fast_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            session.stopped = True
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-zero-peer-test", info_hash=b"\x02" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=True,
                get_active_peers=lambda: [],
                connections={},
            )
        ),
        piece_manager=SimpleNamespace(_metadata_incomplete=False),
        torrent_data={"file_info": {"total_length": 16384}},
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                min_peers_before_dht=10,
                enable_dht=True,
                dht_normal_alpha=3,
                dht_normal_k=8,
                dht_normal_max_depth=8,
                dht_aggressive_alpha=6,
                dht_aggressive_k=16,
                dht_aggressive_max_depth=12,
            ),
            network=SimpleNamespace(
                enable_fail_fast_dht=True,
                fail_fast_dht_timeout=30.0,
                max_peers_per_torrent=50,
            ),
        ),
        session_manager=None,
        _low_peers_since=None,
    )

    async def fake_get_peers(*_args, **_kwargs):
        session.stopped = True
        return []

    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[object()]),
        get_peers=AsyncMock(side_effect=fake_get_peers),
        peer_callbacks=[],
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    dht_client.get_peers.assert_awaited_once()
