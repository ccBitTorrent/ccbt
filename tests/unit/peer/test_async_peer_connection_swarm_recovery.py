"""Regression tests for swarm-recovery peer pipeline controls."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.peer.peer import PeerInfo


def _build_manager(max_peers: int = 2) -> AsyncPeerConnectionManager:
    torrent_data = {
        "info_hash": b"01234567890123456789",
        "pieces_info": {"num_pieces": 8},
    }
    piece_manager = MagicMock()
    piece_manager.verified_pieces = []
    return AsyncPeerConnectionManager(
        torrent_data=torrent_data,
        piece_manager=piece_manager,
        max_peers_per_torrent=max_peers,
    )


@pytest.mark.asyncio
async def test_resume_pending_batches_schedules_retry_when_full() -> None:
    manager = _build_manager(max_peers=1)
    manager._running = True

    peer = PeerInfo(ip="198.51.100.10", port=6881)
    manager._pending_peer_queue = [peer]
    manager._pending_peer_keys = {f"{peer.ip}:{peer.port}"}

    saturated_conn = MagicMock()
    saturated_conn.is_active.return_value = True
    manager.connections = {"saturated": saturated_conn}

    await manager._resume_pending_batches(reason="unit")

    assert manager._pending_resume_retry_task is not None
    assert not manager._pending_resume_retry_task.done()
    manager._pending_resume_retry_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await manager._pending_resume_retry_task


@pytest.mark.asyncio
async def test_plaintext_fallback_is_bounded_per_peer_window() -> None:
    manager = _build_manager(max_peers=4)
    manager._mse_plain_fallback_window_s = 60.0
    manager._mse_plain_fallback_max_per_window = 2

    peer = PeerInfo(ip="198.51.100.20", port=6881)

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout")
    manager._record_mse_plain_fallback(peer, "mse_timeout")

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout")
    manager._record_mse_plain_fallback(peer, "mse_timeout")

    assert manager._should_attempt_plain_fallback(peer, "mse_timeout") is False
