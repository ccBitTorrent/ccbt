"""Candidate-store contracts for discovery and startup delivery."""

# ruff: noqa: SLF001

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import ConnectSubmitResult
from ccbt.session.discovery import DiscoveryController, EndpointCandidateStore
from ccbt.session.peers import PeerManagerInitializer
from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit, pytest.mark.session]
EXPECTED_TWO = 2


def _torrent_data() -> dict:
    return {
        "name": "candidate-store",
        "info_hash": b"c" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }


def test_candidate_store_refreshes_accepted_endpoint_after_window() -> None:
    """Accepted endpoints become eligible again after the refresh window."""
    store = EndpointCandidateStore(
        ttl_seconds=30.0,
        accepted_refresh_seconds=5.0,
    )
    endpoint = ("192.0.2.1", 6881)

    assert store.observe([endpoint], source="dht", now=10.0) == 1
    first = store.take_ready(now=10.0)
    assert first[0]["_candidate_attempts"] == 1
    store.mark_accepted(first, now=10.0)

    store.observe([endpoint], source="dht", now=14.9)
    assert store.take_ready(now=14.9) == []

    store.observe([endpoint], source="dht", now=15.0)
    refreshed = store.take_ready(now=15.0)
    assert len(refreshed) == 1
    assert refreshed[0]["_candidate_attempts"] == EXPECTED_TWO


def test_candidate_store_retries_and_merges_source_provenance() -> None:
    """Failed endpoints retain attempts and all observed source provenance."""
    store = EndpointCandidateStore(retry_base_seconds=2.0)
    peer = {"ip": "198.51.100.2", "port": 51413, "peer_source": "dht"}
    store.observe([peer], source="dht", now=20.0)
    attempted = store.take_ready(now=20.0)
    store.mark_retry(attempted, now=20.0)

    store.observe(
        [{"ip": peer["ip"], "port": peer["port"], "peer_source": "tracker"}],
        source="announce_loop",
        now=20.5,
    )
    assert store.take_ready(now=21.9) == []
    retried = store.take_ready(now=22.0)

    assert retried[0]["_candidate_attempts"] == EXPECTED_TWO
    assert set(retried[0]["_candidate_sources"]) >= {
        "dht",
        "tracker",
        "announce_loop",
    }


def test_candidate_store_drops_stale_and_prioritizes_fresh_value() -> None:
    """Expired FIFO entries cannot block a fresh, high-value endpoint."""
    store = EndpointCandidateStore(ttl_seconds=5.0)
    store.observe(
        [{"ip": "203.0.113.1", "port": 1, "_replacement_priority": 0.0}],
        source="dht",
        now=1.0,
    )
    store.observe(
        [{"ip": "203.0.113.2", "port": 2, "_replacement_priority": 1.0}],
        source="tracker",
        now=7.0,
    )

    ready = store.take_ready(now=7.0)
    assert [(peer["ip"], peer["port"]) for peer in ready] == [
        ("203.0.113.2", 2)
    ]


@pytest.mark.asyncio
async def test_dht_delivery_retries_until_queue_accepts() -> None:
    """DHT delivery remains pending until the downstream queue accepts it."""
    class Tasks:
        def __init__(self) -> None:
            self.tasks: list[asyncio.Task] = []

        def create_task(self, coro, *, name):
            task = asyncio.create_task(coro, name=name)
            self.tasks.append(task)
            return task

    class DHT:
        def add_peer_callback(self, callback, *, info_hash):
            self.callback = callback
            self.info_hash = info_hash

    tasks = Tasks()
    context = SimpleNamespace(session_manager=None, logger=MagicMock())
    controller = DiscoveryController(context, tasks)  # type: ignore[arg-type]
    controller._candidates = EndpointCandidateStore(retry_base_seconds=0.0)
    dht = DHT()
    delivery = AsyncMock(
        side_effect=[
            ConnectSubmitResult(status="noop_empty"),
            ConnectSubmitResult(
                status="queued_reentrant",
                upstream_peer_count=1,
                queued_peer_count=1,
                queue_depth_after=1,
            ),
        ]
    )
    controller.register_dht_callback(
        dht,  # type: ignore[arg-type]
        delivery,
        info_hash=b"d" * 20,
    )

    dht.callback([("192.0.2.99", 6881)])
    await asyncio.sleep(1.1)

    assert delivery.await_count == EXPECTED_TWO
    assert controller._candidates.snapshot() == []
    for task in tasks.tasks:
        if not task.done():
            task.cancel()


@pytest.mark.asyncio
async def test_peer_initializer_runs_readiness_drain() -> None:
    """Peer-manager readiness immediately triggers the startup candidate drain."""
    peer_manager = SimpleNamespace(start=AsyncMock())
    download_manager = SimpleNamespace(peer_manager=peer_manager)
    context = SimpleNamespace(peer_manager=None)
    drain = AsyncMock(return_value=2)

    with patch("ccbt.session.peers.PeerEventsBinder") as binder:
        binder.return_value.bind_peer_manager = MagicMock()
        result = await PeerManagerInitializer().init_and_bind(
            download_manager,
            is_private=False,
            session_ctx=context,
            on_ready=drain,
        )

    assert result is peer_manager
    peer_manager.start.assert_awaited_once()
    drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_startup_drain_marks_only_accepted_submission(tmp_path) -> None:
    """A queue-accepted startup drain removes delivered candidate state."""
    session = AsyncTorrentSession(_torrent_data(), str(tmp_path))
    session.add_queued_peer(
        {
            "ip": "192.0.2.20",
            "port": 6881,
            "peer_source": "tracker",
            "_replacement_priority": 1.0,
        }
    )
    session.add_queued_peer(
        {"ip": "192.0.2.21", "port": 6882, "peer_source": "dht"}
    )
    session.logger = logging.getLogger("test_session_startup_drain")

    accepted = ConnectSubmitResult(
        status="queued_reentrant",
        upstream_peer_count=2,
        queued_peer_count=2,
        queue_depth_after=2,
    )
    with patch(
        "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
        new=AsyncMock(return_value=accepted),
    ) as connect:
        drained = await session._drain_queued_peers()

    assert drained == EXPECTED_TWO
    submitted = connect.await_args.args[0]
    assert submitted[0]["peer_source"] == "tracker"
    assert session.get_queued_peers() == []
