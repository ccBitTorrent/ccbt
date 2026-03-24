"""Regression tests for DHT recovery deadlocks."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ccbt.utils.events import EventBus, PeerCountLowEvent

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_peer_count_low_event_exposes_legacy_and_canonical_keys() -> None:
    """peer_count_low events should publish both active peer count key variants."""
    event = PeerCountLowEvent(active_peers=3, info_hash=b"\x01" * 20, total_peers=9)

    assert event.data["active_peers"] == 3
    assert event.data["active_peer_count"] == 3
    assert event.data["total_peers"] == 9


@pytest.mark.asyncio
async def test_peer_count_low_dispatch_invokes_handler_without_can_handle_errors(
    tmp_path,
) -> None:
    """Event bus dispatch should run peer_count_low handler without can_handle failures."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "peer-count-dispatch",
        "info_hash": b"\x12" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    assert session._peer_count_low_handler is not None

    bus = EventBus()
    bus.register_handler("peer_count_low", session._peer_count_low_handler)

    dispatched_payloads: list[dict[str, object]] = []

    async def _schedule(event_data: dict[str, object]) -> None:
        dispatched_payloads.append(event_data)

    session._schedule_peer_count_low_recovery = _schedule  # type: ignore[method-assign]

    await bus._handle_event(PeerCountLowEvent(active_peers=0, info_hash=session.info.info_hash))

    assert dispatched_payloads == [
        {"active_peers": 0, "active_peer_count": 0, "total_peers": 0, "info_hash": session.info.info_hash.hex()}
    ]


def test_peer_count_low_handler_implements_event_handler_contract(tmp_path) -> None:
    """Peer count low handlers should expose both can_handle and handle."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "peer-count-handler-contract",
        "info_hash": b"\x13" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    handler = session._create_peer_count_low_handler()
    assert callable(getattr(handler, "can_handle", None))
    assert callable(getattr(handler, "handle", None))


@pytest.mark.asyncio
async def test_peer_count_low_queues_tracker_peers_when_peer_manager_unavailable_and_triggers_dht(
    tmp_path,
) -> None:
    """Tracker handoff with no peer manager should queue peers and still run immediate DHT fallback."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "queued-peer-recovery",
        "info_hash": b"\x0b" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))

    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    session.config.discovery.enable_dht = True
    session.config.network.enable_fail_fast_dht = False
    session.config.network.fail_fast_dht_timeout = 30.0

    # Ensure recovery methods stay deterministic for this regression path.
    session._low_peer_threshold = lambda: 1  # type: ignore[method-assign]
    session._low_peer_suppression_window_s = lambda: 0.0  # type: ignore[method-assign]
    session._swarm_requires_fast_recovery = lambda _state: False  # type: ignore[method-assign]
    session._get_swarm_recovery_state = AsyncMock(
        return_value={
            "metadata_incomplete": False,
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
            "active_block_requests": 0,
        }
    )
    session._collect_trackers = lambda _td: ["udp://tracker.example:80"]  # type: ignore[method-assign]

    class _TrackerPeer:
        def __init__(self) -> None:
            self.ip = "127.0.0.1"
            self.port = 6881

    async def _announce(_td, _urls, port):  # type: ignore[unused-argument]
        return [SimpleNamespace(peers=[_TrackerPeer()])]

    session.tracker.announce_to_multiple = AsyncMock(side_effect=_announce)  # type: ignore[method-assign]

    dht_client = SimpleNamespace(
        get_peers=AsyncMock(return_value=[("203.0.113.5", 6881)]),
    )
    session._dht_setup = SimpleNamespace(
        _ensure_bootstrap_ready=AsyncMock(return_value=1)
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    # Force no peer manager readiness so queued-path is selected.
    session.download_manager.peer_manager = None

    # No active announce loop means immediate_announce should still be attempted.
    session._announce_task = None
    session._low_peer_recovery_suppressed_until = 0.0

    handler = session._peer_count_low_handler
    assert handler is not None
    await handler.handle(PeerCountLowEvent(active_peers=0, info_hash=session.info.info_hash))
    recovery_task = session._peer_count_low_recovery_task
    assert recovery_task is not None
    await asyncio.wait_for(recovery_task, timeout=2.0)

    queued_peers = session.get_queued_peers()
    assert len(queued_peers) >= 1
    queued_sources = {str(peer.get("peer_source", "")) for peer in queued_peers}
    assert "tracker" in queued_sources
    assert "dht_immediate" in queued_sources
    dht_client.get_peers.assert_awaited_once()


@pytest.mark.asyncio
async def test_peer_count_low_suppression_reports_non_negative_retry_window(
    tmp_path,
) -> None:
    """Suppressed low-peer recovery should emit a clamped, non-negative retry window."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "suppression-window-test",
        "info_hash": b"\x0e" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    session._low_peer_threshold = lambda: 1  # type: ignore[method-assign]
    session._low_peer_suppression_window_s = lambda: 30.0  # type: ignore[method-assign]
    session._get_swarm_recovery_state = AsyncMock(
        return_value={
            "metadata_incomplete": False,
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
            "active_block_requests": 0,
        }
    )
    session._low_peer_recovery_suppressed_until = time.monotonic() + 5.0

    await session._recover_from_peer_count_low(
        {
            "active_peers": 0,
            "active_peer_count": 0,
            "info_hash": session.info.info_hash.hex(),
        }
    )

    cycle = session._peer_discovery_metrics["last_peer_count_low_recovery_cycle"]
    assert cycle["decision"] == "suppressed"
    assert cycle["retry_plan"] == "suppress_until_low_peer_window"
    assert cycle["retry_in_s"] >= 0.0
    assert cycle["retry_in_s"] <= 5.1


@pytest.mark.asyncio
async def test_peer_count_low_handler_schedules_single_background_recovery_per_session(
    tmp_path,
) -> None:
    """Concurrent peer_count_low events should coalesce to one active recovery task."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "dedupe-peer-low-recovery",
        "info_hash": b"\x0c" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))

    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    started = asyncio.Event()
    release = asyncio.Event()
    recovery_calls: list[dict[str, object]] = []

    async def slow_recovery(event_payload: dict[str, object]) -> None:
        recovery_calls.append(event_payload)
        started.set()
        await release.wait()

    session._recover_from_peer_count_low = slow_recovery  # type: ignore[method-assign]

    handler = session._peer_count_low_handler
    assert handler is not None

    await handler.handle(PeerCountLowEvent(active_peers=0, info_hash=session.info.info_hash))
    await started.wait()
    await handler.handle(PeerCountLowEvent(active_peers=0, info_hash=session.info.info_hash))
    await asyncio.sleep(0)

    assert len(recovery_calls) == 1
    release.set()
    if session._peer_count_low_recovery_task:
        await session._peer_count_low_recovery_task

    assert len(recovery_calls) == 1


@pytest.mark.asyncio
async def test_peer_count_low_recovery_is_keyed_by_info_hash(
    tmp_path,
) -> None:
    """Different info_hash values should not block each other's background recovery tasks."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "dedupe-peer-low-recovery",
        "info_hash": b"\x0c" * 20,
        "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"x" * 20], "total_length": 16384},
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )

    hash_one = b"\x0c" * 20
    hash_two = b"\x0d" * 20
    started = 0
    release = asyncio.Event()
    recovery_calls: list[bytes] = []

    async def slow_recovery(event_payload: dict[str, object]) -> None:
        nonlocal started
        started += 1
        recovery_calls.append(event_payload.get("info_hash", b"") if isinstance(event_payload.get("info_hash", b""), bytes) else b"")
        if started >= 2:
            release.set()
        await release.wait()

    session._recover_from_peer_count_low = slow_recovery  # type: ignore[method-assign]

    handler = session._peer_count_low_handler
    assert handler is not None

    await handler.handle(PeerCountLowEvent(active_peers=0, info_hash=hash_one))
    await handler.handle(PeerCountLowEvent(active_peers=0, info_hash=hash_two))

    await asyncio.wait_for(release.wait(), timeout=1)
    assert started == 2

    if session._peer_count_low_recovery_task:
        await session._peer_count_low_recovery_task
    if session._peer_count_low_recovery_tasks_by_info_hash:
        await asyncio.gather(*session._peer_count_low_recovery_tasks_by_info_hash.values())

    assert len(recovery_calls) == 2


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
                get_active_peers=list,
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
                get_active_peers=list,
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
                get_active_peers=list,
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
async def test_dht_discovery_empty_routing_immediate_recovery_is_bounded(monkeypatch) -> None:
    """Empty-routing recovery should attempt bounded immediate retries before hard backoff."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-empty-routing-immediate", info_hash=b"\x09" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
                get_active_peers=list,
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

    rebootstrap_calls = 0

    async def fake_rebootstrap() -> bool:
        nonlocal rebootstrap_calls
        rebootstrap_calls += 1
        if rebootstrap_calls >= 2:
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

    assert rebootstrap_calls == 2


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
                get_active_peers=list,
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


def test_dht_discovery_query_zero_nodes_waits_for_zero_state_cap() -> None:
    """Zero-state cap helper should always emit bounded positive jitter values."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    base_wait = 10.0
    for _ in range(20):
        wait = DHTDiscoverySetup._add_jittered_wait(base_wait)
        assert 8.0 <= wait <= 12.0
        assert wait > 0

    assert DHTDiscoverySetup._add_jittered_wait(0.0) == 0.0


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
    # _ensure_bootstrap_ready runs _run_bootstrap_with_fallback; with no bootstrap_nodes
    # on the stub client, seed candidates are empty and the failure reason is set to
    # "{reason}:no_seed_candidates" (reason includes initial_query + session name).
    assert setup._dht_query_metrics["last_bootstrap_failure_reason"] == (
        "initial_query:magnet-bootstrap-zero:no_seed_candidates"
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


@pytest.mark.asyncio
async def test_dht_discovery_forces_progress_after_repeated_batch_wait(monkeypatch) -> None:
    """DHT discovery should not wait indefinitely while batch state remains active."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fast_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-batch-wait-cap", info_hash=b"\x08" * 20),
        logger=SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=True,
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
                dht_batch_wait_defer_cycles=2,
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
    calls = 0

    async def fake_get_peers(*_args: object, **_kwargs: object) -> list[tuple[str, int]]:
        nonlocal calls
        calls += 1
        session.stopped = True
        return []

    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[object()]),
        get_peers=AsyncMock(side_effect=fake_get_peers),
        rebootstrap=AsyncMock(return_value=False),
        peer_callbacks=[],
        bootstrap_success_count=0,
        bootstrap_failure_count=0,
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    assert calls == 1


@pytest.mark.asyncio
async def test_tracker_wait_is_shortened_when_no_tracker_progress(monkeypatch) -> None:
    """DHT should shorten tracker-gated wait when tracker peers have not produced usable connections."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("ccbt.session.dht_setup.asyncio.sleep", fake_sleep)

    session = SimpleNamespace(
        stopped=False,
        info=SimpleNamespace(name="dht-tracker-gating", info_hash=b"\x0C" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                _connection_batches_in_progress=False,
                get_active_peers=list,
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
                dht_batch_wait_defer_cycles=2,
            ),
            network=SimpleNamespace(
                enable_fail_fast_dht=True,
                fail_fast_dht_timeout=30.0,
                max_peers_per_torrent=50,
            ),
        ),
        session_manager=None,
        _low_peers_since=None,
        _tracker_peers_connecting_until=time.time() + 2.0,
    )

    calls = 0

    async def fake_get_peers(*_args: object, **_kwargs: object) -> list[tuple[str, int]]:
        nonlocal calls
        calls += 1
        session.stopped = True
        return []

    dht_client = SimpleNamespace(
        wait_for_bootstrap=AsyncMock(return_value=True),
        routing_table=SimpleNamespace(nodes=[object()]),
        get_peers=AsyncMock(side_effect=fake_get_peers),
        rebootstrap=AsyncMock(return_value=False),
        peer_callbacks=[],
        bootstrap_success_count=0,
        bootstrap_failure_count=0,
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    setup = DHTDiscoverySetup(session)
    await setup._run_discovery_loop(dht_client)

    assert calls == 1
    assert sleep_calls[0] <= 0.5


@pytest.mark.asyncio
async def test_ensure_bootstrap_ready_replays_seed_bootstrap_on_rebootstrap_failure() -> None:
    """When rebootstrap returns zero nodes, seeded bootstrap replay should be used."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-seed-replay", info_hash=b"\x09" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                get_active_peers=list,
                connections={},
            )
        ),
        config=SimpleNamespace(
            discovery=SimpleNamespace(),
        ),
    )

    dht_client = SimpleNamespace(
        bootstrap_nodes=[("127.0.0.1", 6881)],
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
    )

    async def fake_bootstrap(reason: str) -> bool:
        dht_client.routing_table.nodes.append(object())
        return True

    dht_client._bootstrap = AsyncMock(side_effect=fake_bootstrap)

    setup = DHTDiscoverySetup(session)
    size = await setup._ensure_bootstrap_ready(
        dht_client,
        reason="bootstrap-ready-test",
        timeout=0.1,
        min_nodes=1,
    )

    assert size == 1
    assert dht_client.rebootstrap.await_count == 1
    assert dht_client._bootstrap.await_count == 1
    assert setup._dht_query_metrics["bootstrap_recovery_attempts"] >= 2
    assert (
        setup._dht_query_metrics["bootstrap_recovery_history"][-1]["reason"]
        == "bootstrap-ready-test:seed_replay"
    )
    assert setup._dht_query_metrics["bootstrap_recovery_history"][-1]["success"] is True


@pytest.mark.asyncio
async def test_bootstrap_zero_nodes_records_recovery_history_and_metric() -> None:
    """Bootstrap completion with zero nodes should record explicit history and metric."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-zero-nodes", info_hash=b"\x0A" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(
                get_active_peers=list,
                connections={},
            )
        ),
        config=SimpleNamespace(
            discovery=SimpleNamespace(),
        ),
    )

    dht_client = SimpleNamespace(
        bootstrap_nodes=[],
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
    )

    setup = DHTDiscoverySetup(session)
    size = await setup._ensure_bootstrap_ready(
        dht_client,
        reason="zero-nodes-test",
        timeout=0.1,
        min_nodes=1,
    )

    assert size == 0
    assert setup._dht_query_metrics["bootstrap_recovery_history"]
    assert any(
        attempt["source"] == "rebootstrap"
        and attempt["success"] is False
        for attempt in setup._dht_query_metrics["bootstrap_recovery_history"]
    )
    assert setup._dht_query_metrics.get("bootstrap_zero_state_count", 0) >= 1


@pytest.mark.asyncio
async def test_rebootstrap_outcome_counters_track_failure_and_success() -> None:
    """Rebootstrap attempts should update explicit success/failure counters."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-rebootstrap-counters", info_hash=b"\x0B" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=4,
                dht_bootstrap_retries_max=3,
                dht_bootstrap_memo_ttl_s=0.0,
                bootstrap_retry_memo_ttl_s=0.0,
            ),
            network=SimpleNamespace(
                enable_fail_fast_dht=True,
            ),
        ),
    )

    dht_client = SimpleNamespace(
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
    )
    setup = DHTDiscoverySetup(session)
    await setup._run_bootstrap_with_fallback(
        dht_client,
        reason="counter-failure",
        timeout=0.1,
        min_nodes=1,
    )
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 1
    assert setup._dht_query_metrics["rebootstrap_failure_count"] == 1
    assert setup._dht_query_metrics["rebootstrap_success_count"] == 0
    assert setup._dht_query_metrics["rebootstrap_health_state"] == "degraded"

    dht_client.rebootstrap = AsyncMock(return_value=True)
    await setup._run_bootstrap_with_fallback(
        dht_client,
        reason="counter-success",
        timeout=0.1,
        min_nodes=1,
        force_bootstrap=True,
    )
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 2
    assert setup._dht_query_metrics["rebootstrap_failure_count"] == 1
    assert setup._dht_query_metrics["rebootstrap_success_count"] == 1
    assert setup._dht_query_metrics["rebootstrap_health_state"] == "healthy"
    assert setup._dht_query_metrics["rebootstrap_last_outcome"] == "success"


@pytest.mark.asyncio
async def test_rebootstrap_cooldown_blocks_immediate_repeat_attempts(monkeypatch) -> None:
    """Cooldown should suppress immediate duplicate rebootstrap attempts for the same reason."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-rebootstrap-cooldown", info_hash=b"\x0C" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=4,
                dht_bootstrap_retries_max=5,
                dht_bootstrap_memo_ttl_s=60.0,
                bootstrap_retry_memo_ttl_s=0.0,
            ),
            network=SimpleNamespace(
                enable_fail_fast_dht=True,
            ),
        ),
    )

    monotonic_time = 500.0

    def fixed_time() -> float:
        return monotonic_time

    monkeypatch.setattr("ccbt.session.dht_setup.time.monotonic", fixed_time)

    dht_client = SimpleNamespace(
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
    )
    setup = DHTDiscoverySetup(session)
    setup._rebootstrap_cooldown = 1.0

    first_result = await setup._maybe_rebootstrap(dht_client, reason="query_zero_nodes cycle=1")
    assert first_result is False
    assert dht_client.rebootstrap.await_count == 1
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 1

    # Repeated attempt with same reason right away should be rate limited.
    second_result = await setup._maybe_rebootstrap(dht_client, reason="query_zero_nodes cycle=1")
    assert second_result is False
    assert dht_client.rebootstrap.await_count == 1
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 1

    monotonic_time += 2.0
    third_result = await setup._maybe_rebootstrap(dht_client, reason="query_zero_nodes cycle=1")
    assert third_result is False
    assert dht_client.rebootstrap.await_count == 2
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 2


@pytest.mark.asyncio
async def test_rebootstrap_zero_state_reasons_share_caps(monkeypatch) -> None:
    """Empty-routing and query-zero-node zero-state reasons share one retry cap."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-zero-state-cap", info_hash=b"\x0F" * 20),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
        config=SimpleNamespace(
            discovery=SimpleNamespace(
                bootstrap_seed_replay_limit=4,
                dht_bootstrap_retries_max=1,
                dht_bootstrap_memo_ttl_s=60.0,
                bootstrap_retry_memo_ttl_s=0.0,
            )
        ),
    )

    monotonic_time = 500.0

    def fixed_time() -> float:
        return monotonic_time

    monkeypatch.setattr("ccbt.session.dht_setup.time.monotonic", fixed_time)

    dht_client = SimpleNamespace(
        routing_table=SimpleNamespace(nodes=[]),
        rebootstrap=AsyncMock(return_value=False),
    )
    setup = DHTDiscoverySetup(session)
    setup._rebootstrap_cooldown = 0.0

    first_attempt = await setup._maybe_rebootstrap(
        dht_client, reason="empty_routing_table cycle=1"
    )
    assert first_attempt is False
    assert dht_client.rebootstrap.await_count == 1
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 1

    monotonic_time += 1.0
    second_attempt = await setup._maybe_rebootstrap(
        dht_client, reason="query_zero_nodes cycle=1"
    )
    assert second_attempt is False
    assert dht_client.rebootstrap.await_count == 1
    assert setup._dht_query_metrics["rebootstrap_attempt_count"] == 1
    assert (
        setup._dht_query_metrics["bootstrap_zero_state_recovery_capped"] is True
    )
    assert (
        setup._dht_query_metrics["rebootstrap_last_block_reason"]
        == "retry_limit:zero_node_recovery"
    )


def test_rebootstrap_health_summary_includes_bootstrap_metrics() -> None:
    """Health summaries should include bootstrap recovery context."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = SimpleNamespace(
        info=SimpleNamespace(name="dht-health-summary", info_hash=b"\x0E" * 20),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )
    setup = DHTDiscoverySetup(session)
    setup._record_bootstrap_recovery_attempt(
        reason="summary-test",
        source="rebootstrap",
        before_nodes=0,
        after_nodes=0,
        attempts=2,
        timeout=0.2,
        success=False,
        min_nodes=1,
    )
    setup._set_health_state("stalled")

    summary = setup._get_rebootstrap_health_summary()

    assert summary["bootstrap_recovery_attempts"] == 1
    assert summary["bootstrap_zero_state_count"] == 1
    assert summary["bootstrap_zero_nodes_last_reason"] == "summary-test"
    assert summary["bootstrap_health_state"] == "stalled"
    assert summary["rebootstrap_attempt_count"] == 0


@pytest.mark.asyncio
async def test_get_swarm_recovery_state_projects_block_reasons(tmp_path) -> None:
    """Recovery state should include requestable and request-block reason counters."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "recovery-state-requests",
        "info_hash": b"\x0D" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = SimpleNamespace(
        _metadata_incomplete=False,
        peer_availability={},
    )

    async def _connection_summary() -> dict[str, int]:
        return {
            "active_connections": 2,
            "remote_choked_connections": 1,
            "pipeline_saturated_connections": 1,
            "requestable_connections": 0,
            "productive_connections": 1,
            "handshake_complete_connections": 2,
            "extension_capable_connections": 1,
            "metadata_capable_connections": 1,
            "metadata_exchange_active": 0,
            "peers_with_piece_info": 0,
            "bitfield_complete_connections": 2,
        }

    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            get_connection_summary=AsyncMock(side_effect=_connection_summary),
            connections={},
            get_active_peers=lambda: [object(), object()],
        )
    )

    state = await session._get_swarm_recovery_state()  # type: ignore[attr-defined]

    assert state["active_peers"] == 2
    assert state["peer_manager_swarm_inputs"] is True
    assert state["summary_active_connections"] == 2
    assert state["transport_live_peers"] == 2
    assert state["remote_choked_peers"] == 1
    assert state["pipeline_saturated_peers"] == 1
    assert state["requestable_peers"] == 0
    assert state["productive_peers"] == 1


@pytest.mark.asyncio
async def test_get_swarm_recovery_state_prefers_transport_live_over_summary_active(
    tmp_path,
) -> None:
    """When summary active_connections is inflated vs live streams, use transport count."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "recovery-transport-skew",
        "info_hash": b"\x0E" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.piece_manager = SimpleNamespace(
        _metadata_incomplete=False,
        peer_availability={"a": object()},
    )

    async def _skewed_summary() -> dict[str, int]:
        return {
            "active_connections": 3,
            "remote_choked_connections": 0,
            "pipeline_saturated_connections": 0,
            "requestable_connections": 0,
            "productive_connections": 0,
            "handshake_complete_connections": 3,
            "extension_capable_connections": 0,
            "metadata_capable_connections": 0,
            "metadata_exchange_active": 0,
            "peers_with_piece_info": 0,
            "bitfield_complete_connections": 0,
        }

    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            get_connection_summary=AsyncMock(side_effect=_skewed_summary),
            connections={},
            get_active_peers=lambda: [object()],
        )
    )

    state = await session._get_swarm_recovery_state()  # type: ignore[attr-defined]

    assert state["summary_active_connections"] == 3
    assert state["transport_live_peers"] == 1
    assert state["peer_manager_swarm_inputs"] is True
    assert state["active_peers"] == 1
    assert state["peer_availability_entries"] == 1
    assert state["peers_with_piece_info"] == 0


@pytest.mark.asyncio
async def test_peer_count_low_skips_dht_when_usability_improves_without_active_growth(
    tmp_path,
) -> None:
    """Usability improvement (not active-count growth) should still take skip path."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "peer-count-skip-usable-no-growth",
        "info_hash": b"\x21" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    session.config.discovery.enable_dht = True
    session.config.discovery.min_peers_before_dht = 10
    session.config.discovery.peer_count_low_skip_dht_requires_usable_path = True
    session.config.network.enable_fail_fast_dht = True
    session.config.network.fail_fast_dht_timeout = 0.01
    session._collect_trackers = lambda _td: []  # type: ignore[method-assign]
    session._swarm_requires_fast_recovery = lambda _state: False  # type: ignore[method-assign]

    session._get_swarm_recovery_state = AsyncMock(
        side_effect=[
            {
                "metadata_incomplete": False,
                "active_peers": 2,
                "productive_peers": 0,
                "requestable_peers": 0,
                "peers_with_piece_info": 0,
                "active_block_requests": 0,
                "has_usable_download_path": False,
            },
            {
                "metadata_incomplete": False,
                "active_peers": 2,
                "productive_peers": 1,
                "requestable_peers": 1,
                "peers_with_piece_info": 0,
                "active_block_requests": 0,
                "has_usable_download_path": True,
            },
        ]
    )
    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            _dht_connect_deferral_active=False,
            get_connection_summary=AsyncMock(
                return_value={
                    "active_connections": 2,
                    "requestable_connections": 1,
                    "productive_connections": 1,
                    "peers_with_piece_info": 0,
                }
            ),
            connections={},
            get_active_peers=list,
        )
    )
    session._dht_setup = SimpleNamespace(_ensure_bootstrap_ready=AsyncMock(return_value=1))
    dht_client = SimpleNamespace(get_peers=AsyncMock(return_value=[]))
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    await session._recover_from_peer_count_low(
        {
            "active_peers": 2,
            "active_peer_count": 2,
            "info_hash": session.info.info_hash.hex(),
        }
    )

    cycle = session._peer_discovery_metrics["last_peer_count_low_recovery_cycle"]
    assert cycle["decision"] == "skip_dht_after_tracker_success"
    dht_client.get_peers.assert_not_awaited()


@pytest.mark.asyncio
async def test_peer_count_low_triggers_dht_when_active_unchanged_and_not_more_usable(
    tmp_path,
) -> None:
    """No active-count growth and no usability gain should not take skip path."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "peer-count-trigger-no-usable-growth",
        "info_hash": b"\x22" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    session.config.discovery.enable_dht = True
    session.config.discovery.min_peers_before_dht = 10
    session.config.discovery.peer_count_low_skip_dht_requires_usable_path = True
    session.config.network.enable_fail_fast_dht = True
    session.config.network.fail_fast_dht_timeout = 0.01
    session._collect_trackers = lambda _td: []  # type: ignore[method-assign]
    session._swarm_requires_fast_recovery = lambda _state: False  # type: ignore[method-assign]
    session._low_peer_threshold = lambda: 1  # type: ignore[method-assign]
    session._low_peer_suppression_window_s = lambda: 0.0  # type: ignore[method-assign]

    _stuck_swarm_row = {
        "metadata_incomplete": False,
        "active_peers": 2,
        "productive_peers": 0,
        "requestable_peers": 0,
        "peers_with_piece_info": 0,
        "active_block_requests": 0,
        "has_usable_download_path": False,
    }
    session._get_swarm_recovery_state = AsyncMock(return_value=_stuck_swarm_row)
    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            _dht_connect_deferral_active=False,
            get_connection_summary=AsyncMock(
                return_value={
                    "active_connections": 2,
                    "requestable_connections": 0,
                    "productive_connections": 0,
                    "peers_with_piece_info": 0,
                }
            ),
            connections={},
            get_active_peers=list,
        )
    )
    session._dht_setup = SimpleNamespace(_ensure_bootstrap_ready=AsyncMock(return_value=1))
    dht_client = SimpleNamespace(get_peers=AsyncMock(return_value=[]))
    session.session_manager = SimpleNamespace(dht_client=dht_client)

    await session._recover_from_peer_count_low(
        {
            "active_peers": 2,
            "active_peer_count": 2,
            "info_hash": session.info.info_hash.hex(),
        }
    )

    cycle = session._peer_discovery_metrics["last_peer_count_low_recovery_cycle"]
    assert cycle["decision"] != "skip_dht_after_tracker_success"
    dht_client.get_peers.assert_awaited_once()


@pytest.mark.asyncio
async def test_peer_count_low_reentrant_tracker_submit_still_triggers_dht(
    tmp_path,
    monkeypatch,
) -> None:
    """queued_reentrant tracker submit must not short-circuit recovery; DHT tier still runs."""
    from ccbt.session.session import AsyncTorrentSession, PeerConnectionHelper

    td = {
        "name": "reentrant-then-dht",
        "info_hash": b"\x23" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    session.config.discovery.enable_dht = True
    session.config.discovery.min_peers_before_dht = 10
    session.config.network.enable_fail_fast_dht = False
    session.config.network.fail_fast_dht_timeout = 30.0
    session._low_peer_threshold = lambda: 1  # type: ignore[method-assign]
    session._low_peer_suppression_window_s = lambda: 0.0  # type: ignore[method-assign]
    session._swarm_requires_fast_recovery = lambda _state: False  # type: ignore[method-assign]
    session._get_swarm_recovery_state = AsyncMock(
        return_value={
            "metadata_incomplete": False,
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
            "active_block_requests": 0,
            "has_usable_download_path": True,
        }
    )
    session._collect_trackers = lambda _td: ["udp://tracker.example:80"]  # type: ignore[method-assign]

    class _TrackerPeer:
        def __init__(self) -> None:
            self.ip = "127.0.0.1"
            self.port = 6881

    async def _announce(_td, _urls, port):  # type: ignore[unused-argument]
        return [SimpleNamespace(peers=[_TrackerPeer()])]

    session.tracker.announce_to_multiple = AsyncMock(side_effect=_announce)  # type: ignore[method-assign]

    dht_client = SimpleNamespace(
        get_peers=AsyncMock(return_value=[("203.0.113.5", 6881)]),
    )
    session._dht_setup = SimpleNamespace(
        _ensure_bootstrap_ready=AsyncMock(return_value=1)
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)
    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            _dht_connect_deferral_active=False,
            connections={},
            get_active_peers=list,
        )
    )
    session._announce_task = None
    session._low_peer_recovery_suppressed_until = 0.0

    monkeypatch.setattr(
        PeerConnectionHelper,
        "connect_peers_to_download",
        AsyncMock(return_value=SimpleNamespace(status="queued_reentrant")),
    )

    await session._recover_from_peer_count_low(
        {
            "active_peers": 0,
            "active_peer_count": 0,
            "info_hash": session.info.info_hash.hex(),
        }
    )

    assert session._peer_discovery_metrics["last_peer_count_low_recovery_cycle"][
        "tracker_outcome"
    ] == "tracker_handoff_submit_reentrant"
    dht_client.get_peers.assert_awaited_once()


@pytest.mark.asyncio
async def test_peer_count_low_skips_immediate_dht_until_requestable_deficit_persists(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Swarm at/above DHT threshold but non-requestable should defer immediate get_peers briefly."""
    from ccbt.session.session import AsyncTorrentSession, PeerConnectionHelper

    td = {
        "name": "deficit-gate-dht",
        "info_hash": b"\x24" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    session.config.discovery.enable_dht = True
    session.config.discovery.min_peers_before_dht = 10
    session.config.discovery.peer_count_low_skip_dht_requires_usable_path = False
    session.config.network.enable_fail_fast_dht = True
    session.config.network.fail_fast_dht_timeout = 30.0
    session._recovery_requestable_deficit_window_s = 12.0
    session._low_peer_threshold = lambda: 1  # type: ignore[method-assign]
    session._low_peer_suppression_window_s = lambda: 0.0  # type: ignore[method-assign]
    session._swarm_requires_fast_recovery = lambda _state: False  # type: ignore[method-assign]

    stuck_swarm = {
        "metadata_incomplete": False,
        "active_peers": 12,
        "productive_peers": 0,
        "requestable_peers": 0,
        "peers_with_piece_info": 1,
        "active_block_requests": 0,
        "has_usable_download_path": True,
    }
    session._get_swarm_recovery_state = AsyncMock(return_value=stuck_swarm)

    class _Tp:
        ip = "198.51.100.2"
        port = 6882

    session._collect_trackers = lambda _td: ["udp://tracker.example:80"]  # type: ignore[method-assign]
    session.tracker.announce_to_multiple = AsyncMock(
        return_value=[SimpleNamespace(peers=[_Tp()])]
    )

    dht_client = SimpleNamespace(get_peers=AsyncMock(return_value=[]))
    session._dht_setup = SimpleNamespace(
        _ensure_bootstrap_ready=AsyncMock(return_value=1)
    )
    session.session_manager = SimpleNamespace(dht_client=dht_client)
    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(
            _dht_connect_deferral_active=False,
            get_connection_summary=AsyncMock(
                return_value={
                    "active_connections": 12,
                    "requestable_connections": 0,
                    "productive_connections": 0,
                    "peers_with_piece_info": 1,
                }
            ),
            connections={},
            get_active_peers=lambda: [object()] * 12,
        )
    )
    session._announce_task = None
    session._low_peer_recovery_suppressed_until = 0.0

    async def _connect(_self, peer_list: list) -> SimpleNamespace:  # type: ignore[no-untyped-def]
        assert peer_list
        return SimpleNamespace(status="queued_reentrant")

    monkeypatch.setattr(PeerConnectionHelper, "connect_peers_to_download", _connect)

    await session._recover_from_peer_count_low(
        {
            "active_peers": 12,
            "active_peer_count": 12,
            "info_hash": session.info.info_hash.hex(),
        }
    )

    cycle = session._peer_discovery_metrics["last_peer_count_low_recovery_cycle"]
    assert cycle["decision"] == "skip_dht_deficit_not_persistent"
    assert cycle["dht_outcome"] == "skipped_requestable_deficit_window"
    dht_client.get_peers.assert_not_awaited()
