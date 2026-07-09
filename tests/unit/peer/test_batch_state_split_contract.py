"""Split-state migration contract baselines (pre-refactor)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from typing_extensions import Self

import pytest

from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

pytestmark = [pytest.mark.unit, pytest.mark.peer]

_TORRENT = {
    "info_hash": b"test_info_hash_20byt",
    "pieces_info": {"num_pieces": 1},
}


def test_connection_batch_compatibility_flag_exists() -> None:
    """Compatibility ``_connection_batches_in_progress`` property remains available."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    assert hasattr(manager, "_connection_batches_in_progress")
    assert isinstance(manager._connection_batches_in_progress, bool)  # noqa: SLF001


def test_lock_objects_exist_for_future_lock_order_contract() -> None:
    """Peer manager exposes connect single-flight lock and distinct asyncio locks."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    manager._ensure_pending_queue_initialized()  # noqa: SLF001

    assert isinstance(manager._connect_to_peers_lock, asyncio.Lock)  # noqa: SLF001
    assert isinstance(manager.connection_lock, asyncio.Lock)
    assert isinstance(manager._pending_peer_queue_lock, asyncio.Lock)  # noqa: SLF001
    assert manager._connect_to_peers_lock is not manager.connection_lock  # noqa: SLF001
    assert manager.connection_lock is not manager._pending_peer_queue_lock  # noqa: SLF001


def test_split_batch_owner_and_dht_deferral_flags_exist() -> None:
    """Split-state: batch owner vs DHT deferral are independent writable fields."""
    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    assert hasattr(manager, "_batch_owner_active")
    assert hasattr(manager, "_dht_connect_deferral_active")
    assert isinstance(manager._batch_owner_active, bool)  # noqa: SLF001
    assert isinstance(manager._dht_connect_deferral_active, bool)  # noqa: SLF001


@pytest.mark.asyncio
async def test_reentrant_connect_acquires_lock_order_connect_then_pending() -> None:
    """Reentrant submit lock order: connect lock before pending queue lock."""

    class _TracingLock:
        def __init__(self, inner: asyncio.Lock, name: str, trace: list[str]) -> None:
            self._inner = inner
            self._name = name
            self._trace = trace

        async def __aenter__(self) -> Self:
            await self._inner.acquire()
            self._trace.append(self._name)
            return self

        async def __aexit__(self, *_args: object) -> None:
            self._inner.release()

    manager = AsyncPeerConnectionManager(
        torrent_data=_TORRENT,
        piece_manager=MagicMock(),
        max_peers_per_torrent=4,
    )
    await manager.start()
    try:
        trace: list[str] = []
        manager._connect_to_peers_lock = _TracingLock(  # noqa: SLF001
            asyncio.Lock(),
            "connect",
            trace,
        )
        manager._pending_peer_queue_lock = _TracingLock(  # noqa: SLF001
            asyncio.Lock(),
            "pending",
            trace,
        )
        manager._batch_owner_active = True  # noqa: SLF001
        manager._dht_connect_deferral_active = True  # noqa: SLF001
        result = await manager.connect_to_peers([{"ip": "192.0.2.44", "port": 6881}])
        assert result.status == "queued_reentrant"
        assert trace[:2] == ["connect", "pending"]
    finally:
        manager._batch_owner_active = False  # noqa: SLF001
        manager._dht_connect_deferral_active = False  # noqa: SLF001
        await manager.stop()
