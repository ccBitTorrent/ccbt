"""Contract baselines for connect_to_peers submit behavior (pre-refactor)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.models import ConnectSubmitResult
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

pytestmark = [pytest.mark.unit, pytest.mark.peer]

_TORRENT = {
    "info_hash": b"test_info_hash_20byt",
    "pieces_info": {"num_pieces": 1},
}


@pytest.mark.asyncio
async def test_connect_to_peers_noop_when_not_running_returns_shutdown() -> None:
    """Non-running manager returns noop_shutdown without owning connect."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=8,
    )
    manager._running = False  # noqa: SLF001

    result = await manager.connect_to_peers([{"ip": "127.0.0.1", "port": 6881}])

    assert isinstance(result, ConnectSubmitResult)
    assert result.status == "noop_shutdown"


@pytest.mark.asyncio
async def test_connect_to_peers_empty_input_is_noop() -> None:
    """Current contract baseline: empty input returns without state transitions."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        manager._connection_batches_in_progress = False  # noqa: SLF001
        result = await manager.connect_to_peers([])
        assert isinstance(result, ConnectSubmitResult)
        assert result.status == "noop_empty"
        assert manager._connection_batches_in_progress is False  # noqa: SLF001
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_connect_to_peers_clears_batch_flag_after_run_for_dht_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch compatibility flag clears when connect_to_peers finishes (``finally``).

    Production may clear DHT deferral earlier via duration/heuristics.
    """
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        monkeypatch.setattr(
            asyncio,
            "open_connection",
            AsyncMock(side_effect=ConnectionError("contract baseline")),
        )
        manager._connection_batches_in_progress = False  # noqa: SLF001 — observe transition
        done = await manager.connect_to_peers(
            [{"ip": "192.0.2.10", "port": 6881, "peer_source": "tracker"}],
        )
        assert isinstance(done, ConnectSubmitResult)
        assert done.status == "owner_started"
        assert manager._connection_batches_in_progress is False  # noqa: SLF001
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_connect_to_peers_reentrant_queues_while_owner_active() -> None:
    """While owner is active, a second submit queues peers (``queued_reentrant``)."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        manager._batch_owner_active = True  # noqa: SLF001
        manager._dht_connect_deferral_active = True  # noqa: SLF001
        res = await manager.connect_to_peers(
            [{"ip": "192.0.2.20", "port": 6881, "peer_source": "tracker"}],
        )
        assert res.status == "queued_reentrant"
        assert res.queued_peer_count >= 1
        assert res.queue_depth_after >= 1
    finally:
        manager._batch_owner_active = False  # noqa: SLF001
        manager._dht_connect_deferral_active = False  # noqa: SLF001
        await manager.stop()
