"""Discovery ingress contract baselines for immediate tracker deferral path."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
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
    session = SimpleNamespace(
        info=SimpleNamespace(name="contract-torrent"),
        download_manager=SimpleNamespace(peer_manager=pm),
        logger=logging.getLogger("test_discovery_ingress_contract"),
        record_discovered_peers=MagicMock(),
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
    session = SimpleNamespace(
        info=SimpleNamespace(name="contract-torrent"),
        download_manager=SimpleNamespace(peer_manager=pm),
        logger=logging.getLogger("test_discovery_ingress_contract"),
        record_discovered_peers=MagicMock(),
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
