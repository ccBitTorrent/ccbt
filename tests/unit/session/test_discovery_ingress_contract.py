"""Discovery ingress contract baselines for immediate tracker deferral path.

Legacy: tests that pass ``SimpleNamespace(_peer_discovery_metrics={})`` are minimal stubs;
production sessions initialize full metric keys in ``AsyncTorrentSession.__init__``.
"""

from __future__ import annotations

import asyncio
import logging
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit]


@pytest.mark.asyncio
async def test_deferred_immediate_ingress_enqueues_and_requests_resume() -> None:
    """Baseline: deferred immediate path enqueues and requests pending resume."""
    peers = [{"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"}]
    pm = MagicMock()
    pm.enqueue_peer_dicts_pending = AsyncMock(return_value=1)
    pm.request_pending_resume = MagicMock()
    pm._pending_peer_queue = []
    pm._pending_peer_queue_lock = asyncio.Lock()
    session = SimpleNamespace(
        info=SimpleNamespace(name="contract-torrent"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(tracker_immediate_pending_budget_max=400)
        ),
        _peer_discovery_metrics={},
        download_manager=SimpleNamespace(peer_manager=pm),
        logger=logging.getLogger("test_discovery_ingress_contract"),
        record_discovered_peers=MagicMock(),
    )
    session._refresh_outbound_pending_peer_queue_metric = MethodType(  # type: ignore[method-assign]
        AsyncTorrentSession._refresh_outbound_pending_peer_queue_metric,
        session,
    )

    enq = await AsyncTorrentSession._defer_immediate_tracker_peers_to_pending(  # noqa: SLF001
        session,
        peers,
        reason="contract_baseline",
        tracker_url="udp://tracker.example:80",
    )

    assert enq == 1
    pm.enqueue_peer_dicts_pending.assert_awaited_once()
    pm.request_pending_resume.assert_called_once_with(reason="contract_baseline")


@pytest.mark.asyncio
async def test_deferred_immediate_zero_enqueue_skips_pending_resume() -> None:
    """Avoid false churn: no resume scheduling when nothing was enqueued."""
    peers = [{"ip": "10.0.0.2", "port": 6882, "peer_source": "tracker"}]
    pm = MagicMock()
    pm.enqueue_peer_dicts_pending = AsyncMock(return_value=0)
    pm.request_pending_resume = MagicMock()
    pm._pending_peer_queue = []
    pm._pending_peer_queue_lock = asyncio.Lock()
    session = SimpleNamespace(
        info=SimpleNamespace(name="contract-torrent"),
        config=SimpleNamespace(
            discovery=SimpleNamespace(tracker_immediate_pending_budget_max=400)
        ),
        _peer_discovery_metrics={},
        download_manager=SimpleNamespace(peer_manager=pm),
        logger=logging.getLogger("test_discovery_ingress_contract"),
        record_discovered_peers=MagicMock(),
    )
    session._refresh_outbound_pending_peer_queue_metric = MethodType(  # type: ignore[method-assign]
        AsyncTorrentSession._refresh_outbound_pending_peer_queue_metric,
        session,
    )

    enq = await AsyncTorrentSession._defer_immediate_tracker_peers_to_pending(  # noqa: SLF001
        session,
        peers,
        reason="contract_zero_enqueue",
        tracker_url="udp://tracker.example:80",
    )

    assert enq == 0
    pm.request_pending_resume.assert_not_called()


@pytest.mark.asyncio
async def test_tracker_ingress_coalesces_and_submits_once_per_window(tmp_path) -> None:
    """Immediate + announce peers coalesce into one submit with endpoint dedupe."""
    td = {
        "name": "contract-torrent",
        "info_hash": b"1" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session._tracker_discovery_coalesce_window_s = 0.05

    connect_mock = AsyncMock()
    with patch(
        "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
        connect_mock,
    ):
        merged_a = await session._ingest_tracker_discovery_peers(  # noqa: SLF001
            [
                {"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"},
                {"ip": "10.0.0.2", "port": 6882, "peer_source": "tracker"},
            ],
            tracker_url="udp://tracker-a:80",
            ingress_source="tracker_immediate",
        )
        merged_b = await session._ingest_tracker_discovery_peers(  # noqa: SLF001
            [
                {"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"},
            ],
            tracker_url="udp://tracker-b:80",
            ingress_source="announce_loop",
        )
        assert merged_a == 2
        assert merged_b == 0
        await asyncio.sleep(0.1)

    connect_mock.assert_awaited_once()
    submitted = connect_mock.await_args.args[0]
    keys = {(p["ip"], p["port"]) for p in submitted}
    assert keys == {("10.0.0.1", 6881), ("10.0.0.2", 6882)}


@pytest.mark.asyncio
async def test_tracker_ingress_preserves_source_provenance(tmp_path) -> None:
    """Coalesced peers retain merged discovery source metadata."""
    td = {
        "name": "contract-torrent",
        "info_hash": b"2" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session._tracker_discovery_coalesce_window_s = 0.05

    connect_mock = AsyncMock()
    with patch(
        "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
        connect_mock,
    ):
        await session._ingest_tracker_discovery_peers(  # noqa: SLF001
            [{"ip": "10.0.0.9", "port": 6999, "peer_source": "tracker"}],
            tracker_url="udp://tracker-a:80",
            ingress_source="tracker_immediate",
        )
        await session._ingest_tracker_discovery_peers(  # noqa: SLF001
            [{"ip": "10.0.0.9", "port": 6999, "peer_source": "tracker"}],
            tracker_url="udp://tracker-b:80",
            ingress_source="announce_loop",
        )
        await asyncio.sleep(0.1)

    peer = connect_mock.await_args.args[0][0]
    assert set(peer["_discovery_sources"]) >= {"tracker_immediate", "announce_loop"}
    assert set(peer["_discovery_trackers"]) >= {
        "udp://tracker-a:80",
        "udp://tracker-b:80",
    }


@pytest.mark.asyncio
async def test_per_tracker_immediate_cooldown_scoping(tmp_path) -> None:
    """Tracker cooldown lookups should be tracker-scoped when enabled."""
    td = {
        "name": "cooldown-torrent",
        "info_hash": b"3" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session._set_tracker_immediate_cooldown(  # noqa: SLF001
        until=123.0,
        reason="test",
        tracker_url="udp://tracker-a:80",
    )
    assert (
        session._get_tracker_immediate_cooldown_until("udp://tracker-a:80")  # noqa: SLF001
        == 123.0
    )
    assert (
        session._get_tracker_immediate_cooldown_until("udp://tracker-b:80")  # noqa: SLF001
        is None
    )


@pytest.mark.asyncio
async def test_tracker_ingress_holds_new_peers_when_pending_queue_deep(
    tmp_path,
) -> None:
    """Back-pressure: skip new ingress keys when pending connect queue exceeds threshold."""
    td = {
        "name": "hold-torrent",
        "info_hash": b"4" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.discovery.tracker_ingress_hold_pending_queue_threshold = 1

    class _PM:
        def __init__(self) -> None:
            self._pending_peer_queue = [object()]
            self._pending_peer_queue_lock = asyncio.Lock()
            self._peer_discovery_metrics_ref: dict[str, int] = {}

    pm = _PM()
    session.download_manager.peer_manager = pm

    merged = await session._ingest_tracker_discovery_peers(  # noqa: SLF001
        [{"ip": "10.0.0.88", "port": 6888, "peer_source": "tracker"}],
        tracker_url="udp://tracker-hold:80",
        ingress_source="announce_loop",
    )
    assert merged == 0
    assert int(session._peer_discovery_metrics.get("ingress_hold_deferred_total", 0)) >= 1
    assert ("10.0.0.88", 6888) in session._tracker_ingress_hold_buffer


@pytest.mark.asyncio
async def test_tracker_ingress_admits_new_peers_when_requestable_zero(
    tmp_path,
) -> None:
    """Bypass ingress hold when no requestable peers remain and capacity exists."""
    td = {
        "name": "hold-bypass-torrent",
        "info_hash": b"5" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.discovery.tracker_ingress_hold_pending_queue_threshold = 1

    class _PM:
        def __init__(self) -> None:
            self._pending_peer_queue = [object(), object()]
            self._pending_peer_queue_lock = asyncio.Lock()
            self.max_peers_per_torrent = 50

        def _snapshot_connection_counts(self) -> tuple[int, int, int]:
            return 1, 1, 0

    session.download_manager.peer_manager = _PM()

    merged = await session._ingest_tracker_discovery_peers(  # noqa: SLF001
        [{"ip": "10.0.0.99", "port": 6999, "peer_source": "tracker"}],
        tracker_url="udp://tracker-bypass:80",
        ingress_source="tracker_immediate",
    )
    assert merged == 1
    assert ("10.0.0.99", 6999) in session._tracker_discovery_ingress_pending


@pytest.mark.asyncio
async def test_tracker_ingress_hold_effective_threshold_scales_with_mpt(
    tmp_path,
) -> None:
    """Large configured hold threshold is capped so it engages under low MPT + burst."""
    td = {
        "name": "hold-adaptive-torrent",
        "info_hash": b"7" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.discovery.tracker_ingress_hold_pending_queue_threshold = 200
    session.config.network.max_peers_per_torrent = 35
    session.config.discovery.tracker_immediate_connect_burst_total = 16
    # min(200, max(64, 35*2 + 16*3)) == min(200, 118) == 118
    assert session._effective_tracker_ingress_hold_pending_threshold() == 118

    class _PM:
        def __init__(self) -> None:
            self._pending_peer_queue = [object()] * 120
            self._pending_peer_queue_lock = asyncio.Lock()
            self._peer_discovery_metrics_ref: dict[str, int] = {}

    session.download_manager.peer_manager = _PM()

    merged = await session._ingest_tracker_discovery_peers(
        [{"ip": "10.0.0.99", "port": 6899, "peer_source": "tracker"}],
        tracker_url="udp://tracker-adaptive:80",
        ingress_source="announce_loop",
    )
    assert merged == 0
    assert int(session._peer_discovery_metrics.get("ingress_hold_deferred_total", 0)) >= 1
    """Outbound pending depth must reflect peer-manager queue, not ingress coalescer."""
    td = {
        "name": "metric-torrent",
        "info_hash": b"5" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))

    class _PM:
        def __init__(self) -> None:
            self._pending_peer_queue = [object()] * 42
            self._pending_peer_queue_lock = asyncio.Lock()

    session.download_manager.peer_manager = _PM()
    session._peer_discovery_metrics["ingress_coalescer_depth"] = 7
    depth = await session._refresh_outbound_pending_peer_queue_metric()  # noqa: SLF001
    assert depth == 42
    assert (
        int(session._peer_discovery_metrics["outbound_pending_peer_queue_depth"]) == 42
    )
    assert int(session._peer_discovery_metrics["pending_depth"]) == 42
    assert int(session._peer_discovery_metrics["ingress_coalescer_depth"]) == 7


@pytest.mark.asyncio
async def test_tracker_ingress_flush_reentrant_uses_pm_queue_for_non_progress(
    tmp_path,
) -> None:
    """Reentrant non-progress compares successive PM queue depths (not coalescer size)."""
    td = {
        "name": "reentrant-torrent",
        "info_hash": b"6" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session._tracker_discovery_ingress_pending[("9.9.9.9", 9)] = {
        "ip": "9.9.9.9",
        "port": 9,
        "peer_source": "tracker",
    }
    session._tracker_discovery_last_pm_queue_depth = 100

    with (
        patch(
            "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    status="queued_reentrant",
                    queue_depth_after=100,
                )
            ),
        ),
        patch.object(asyncio, "sleep", new=AsyncMock()),
    ):
        await session._flush_tracker_discovery_ingress()  # noqa: SLF001

    assert session._tracker_reentrant_non_progress_cycles == 1
    assert session._tracker_discovery_last_pm_queue_depth == 100

    session._tracker_discovery_ingress_pending[("8.8.8.8", 8)] = {
        "ip": "8.8.8.8",
        "port": 8,
        "peer_source": "tracker",
    }
    with (
        patch(
            "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    status="queued_reentrant",
                    queue_depth_after=90,
                )
            ),
        ),
        patch.object(asyncio, "sleep", new=AsyncMock()),
    ):
        await session._flush_tracker_discovery_ingress()  # noqa: SLF001

    assert session._tracker_reentrant_non_progress_cycles == 0
    assert session._tracker_discovery_last_pm_queue_depth == 90


@pytest.mark.asyncio
async def test_tracker_ingress_first_reentrant_does_not_spike_cycles(tmp_path) -> None:
    """First PM depth observation after None must not accumulate bogus cycles."""
    td = {
        "name": "first-pm-torrent",
        "info_hash": b"7" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session._tracker_discovery_ingress_pending[("1.2.3.4", 5)] = {
        "ip": "1.2.3.4",
        "port": 5,
        "peer_source": "tracker",
    }
    session._tracker_discovery_last_pm_queue_depth = None

    with (
        patch(
            "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    status="queued_reentrant",
                    queue_depth_after=500,
                )
            ),
        ),
        patch.object(asyncio, "sleep", new=AsyncMock()),
    ):
        await session._flush_tracker_discovery_ingress()  # noqa: SLF001

    assert session._tracker_reentrant_non_progress_cycles == 0
    assert session._tracker_discovery_last_pm_queue_depth == 500


@pytest.mark.asyncio
async def test_tracker_ingress_hold_buffer_flushes_when_depth_drops(tmp_path) -> None:
    """Deferred hold-buffer peers replay when pending depth falls below threshold."""
    td = {
        "name": "hold-flush-torrent",
        "info_hash": b"8" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.discovery.tracker_ingress_hold_pending_queue_threshold = 10
    session.config.discovery.tracker_ingress_hold_buffer_max = 50
    session._tracker_ingress_hold_buffer[("10.0.0.50", 5050)] = {
        "ip": "10.0.0.50",
        "port": 5050,
        "peer_source": "tracker",
    }

    class _PM:
        def __init__(self) -> None:
            self._pending_peer_queue: list[object] = []
            self._pending_peer_queue_lock = asyncio.Lock()

    session.download_manager.peer_manager = _PM()

    flushed = await session._flush_tracker_ingress_hold_buffer()  # noqa: SLF001
    assert flushed == 1
    assert ("10.0.0.50", 5050) not in session._tracker_ingress_hold_buffer
    assert ("10.0.0.50", 5050) in session._tracker_discovery_ingress_pending
