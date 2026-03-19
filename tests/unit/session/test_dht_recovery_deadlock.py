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


@pytest.mark.asyncio
async def test_dht_discovery_records_query_zero_nodes_state(monkeypatch) -> None:
    """DHT loop should mark zero-node query state when lookups query no nodes."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-query-zero-nodes", info_hash=b"\x03" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
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
        _last_query_metrics={"depth": 0, "nodes_queried": 0},
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    assert setup._query_zero_nodes_cycles >= 1


@pytest.mark.asyncio
async def test_dht_discovery_empty_routing_triggers_rebootstrap(monkeypatch) -> None:
    """Repeated empty-routing cycles should trigger an explicit DHT rebootstrap."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-empty-routing", info_hash=b"\x04" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
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

    async def fake_rebootstrap() -> bool:
        session.stopped = True
        return False

    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[]),
        get_peers=AsyncMock(return_value=[]),
        rebootstrap=AsyncMock(side_effect=fake_rebootstrap),
        peer_callbacks=[],
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    dht_client.rebootstrap.assert_awaited()


@pytest.mark.asyncio
async def test_dht_discovery_query_zero_nodes_triggers_rebootstrap(monkeypatch) -> None:
    """Repeated zero-node lookups should trigger an explicit DHT rebootstrap."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-zero-query-rebootstrap", info_hash=b"\x05" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
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
        if dht_client.get_peers.await_count >= 2:
            session.stopped = True
        return []

    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[object()]),
        get_peers=AsyncMock(side_effect=fake_get_peers),
        rebootstrap=AsyncMock(return_value=True),
        peer_callbacks=[],
        _last_query_metrics={"depth": 0, "nodes_queried": 0},
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    dht_client.rebootstrap.assert_awaited()


@pytest.mark.asyncio
async def test_initial_query_skips_zero_node_lookup_after_failed_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initial magnet query should not call get_peers when bootstrap still has zero nodes."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    scheduled_tasks: list[asyncio.Task] = []
    real_create_task = asyncio.create_task

    def capture_task(coro):
        task = real_create_task(coro)
        scheduled_tasks.append(task)
        return task

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.create_task", capture_task)

    session = SimpleNamespace(
        info=SimpleNamespace(name="magnet-bootstrap-zero", info_hash=b"\x06" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        torrent_data={"is_magnet": True},
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                dht_normal_alpha=3,
                dht_normal_k=8,
                dht_normal_max_depth=8,
            ),
        ),
        session_manager=None,
        add_metadata_task=lambda _task: None,
        remove_metadata_task=lambda _task: None,
    )

    dht_client = SimpleNamespace(
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
        get_peers=AsyncMock(return_value=[]),
        bootstrap_success_count=0,
        bootstrap_failure_count=1,
        last_bootstrap_reason="rebootstrap",
        last_bootstrap_failure_reason="no_nodes_discovered",
        last_zero_node_lookup_at=0.0,
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._trigger_initial_query()
    await asyncio.gather(*scheduled_tasks)

    dht_client.get_peers.assert_not_awaited()
    assert setup._dht_query_metrics["bootstrap_failure_count"] == 1
    assert (
        setup._dht_query_metrics["last_bootstrap_failure_reason"]
        == "no_nodes_discovered"
    )


@pytest.mark.asyncio
async def test_dht_discovery_short_path_rebootstrap_on_low_requestable_peers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Very low or unusable peer state should run a short-path bootstrap recheck."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    calls = 0

    async def fake_rebootstrap() -> bool:
        nonlocal calls
        calls += 1
        session.stopped = True
        session.session_manager.dht_client.routing_table = SimpleNamespace(
            nodes=[object()]
        )
        return True

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-short-path", info_hash=b"\x07" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
                get_active_peers=lambda: [object()],
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
                enable_fail_fast_dht=False,
                fail_fast_dht_timeout=30.0,
                max_peers_per_torrent=50,
            ),
        ),
        session_manager=None,
        _low_peers_since=None,
    )
    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[object()]),
        get_peers=AsyncMock(side_effect=lambda *_a, **_k: []),
        rebootstrap=AsyncMock(side_effect=fake_rebootstrap),
        peer_callbacks=[],
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    assert calls == 1
