"""Contract baselines for connect_to_peers submit behavior (pre-refactor)."""

from __future__ import annotations

import asyncio
import importlib
import warnings
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.models import ConnectSubmitResult

async_peer_connection_module = importlib.import_module(
    "ccbt.peer.async_peer_connection",
)
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
)
from ccbt.peer.peer import PeerInfo
from ccbt.config.config import get_config as global_get_config

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


@pytest.mark.asyncio
async def test_connect_to_peers_parallel_batches_allow_concurrent_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With connect_to_peers_parallel_batches>1, a second submit can start while first is in flight."""
    hang = asyncio.Event()
    tcp_attempts = 0

    async def _first_hangs_then_fail(*_a: object, **_k: object) -> None:
        nonlocal tcp_attempts
        tcp_attempts += 1
        if tcp_attempts == 1:
            await hang.wait()
        raise ConnectionError("contract parallel batch")

    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    manager.config = manager.config.model_copy(
        update={
            "network": manager.config.network.model_copy(
                update={"connect_to_peers_parallel_batches": 2},
            ),
        },
    )
    await manager.start()
    try:
        monkeypatch.setattr(asyncio, "open_connection", _first_hangs_then_fail)
        first = asyncio.create_task(
            manager.connect_to_peers(
                [{"ip": "192.0.2.30", "port": 6881, "peer_source": "tracker"}],
            ),
        )
        await asyncio.sleep(0.05)
        second = await manager.connect_to_peers(
            [{"ip": "192.0.2.31", "port": 6881, "peer_source": "dht"}],
        )
        assert second.status == "owner_started"
        hang.set()
        first_result = await asyncio.wait_for(first, timeout=5.0)
        assert first_result.status == "owner_started"
    finally:
        hang.set()
        await manager.stop()


@pytest.mark.asyncio
async def test_parallel_batches_share_global_connection_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All connect batches use one semaphore capped by max_concurrent_connection_attempts."""
    cfg = global_get_config().model_copy(
        update={
            "network": global_get_config().network.model_copy(
                update={
                    "connect_to_peers_parallel_batches": 2,
                    "max_concurrent_connection_attempts": 7,
                },
            ),
        },
    )
    monkeypatch.setattr(async_peer_connection_module, "get_config", lambda: cfg)
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        assert manager._global_connection_semaphore._value == 7  # noqa: SLF001
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_disconnect_peer_preserves_batch_owner_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disconnect path keeps batch owner; connect_to_peers finally clears it."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    await manager.start()
    try:
        monkeypatch.setattr(manager.connection_pool, "release", AsyncMock())
        conn = AsyncPeerConnection(
            peer_info=PeerInfo(ip="192.0.2.77", port=6881),
            torrent_data=_TORRENT,
            state=ConnectionState.CONNECTED,
        )
        manager.connections[str(conn.peer_info)] = conn
        manager._batch_owner_active = True  # noqa: SLF001
        await manager._disconnect_peer(conn)  # noqa: SLF001
        assert manager._batch_owner_active is True  # noqa: SLF001
    finally:
        manager._batch_owner_active = False  # noqa: SLF001
        await manager.stop()


@pytest.mark.asyncio
async def test_legacy_strict_tracker_connect_priority_emits_deprecation_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy strict=False emits one DeprecationWarning per process."""
    warn_state = (
        async_peer_connection_module._LEGACY_STRICT_TRACKER_SOURCE_PRIORITY_FALSE_WARN_STATE  # noqa: SLF001
    )
    monkeypatch.setitem(warn_state, "emitted", False)
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=SimpleNamespace(),
        max_peers_per_torrent=8,
    )
    manager.config.discovery = manager.config.discovery.model_copy(
        update={"strict_tracker_source_connect_priority": False},
    )
    other: AsyncPeerConnectionManager | None = None
    try:
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            await manager.start()
        dep = [
            w
            for w in recorded
            if issubclass(w.category, DeprecationWarning)
            and "strict_tracker_source_connect_priority" in str(w.message)
        ]
        assert len(dep) == 1

        with warnings.catch_warnings(record=True) as recorded2:
            warnings.simplefilter("always")
            await manager.start()
        dep2 = [
            w
            for w in recorded2
            if issubclass(w.category, DeprecationWarning)
            and "strict_tracker_source_connect_priority" in str(w.message)
        ]
        assert not dep2

        other = AsyncPeerConnectionManager(
            torrent_data=_TORRENT,
            piece_manager=SimpleNamespace(),
            max_peers_per_torrent=8,
        )
        other.config.discovery = other.config.discovery.model_copy(
            update={"strict_tracker_source_connect_priority": False},
        )
        with warnings.catch_warnings(record=True) as recorded3:
            warnings.simplefilter("always")
            await other.start()
        dep3 = [
            w
            for w in recorded3
            if issubclass(w.category, DeprecationWarning)
            and "strict_tracker_source_connect_priority" in str(w.message)
        ]
        assert not dep3
    finally:
        if other is not None:
            await other.stop()
        await manager.stop()
