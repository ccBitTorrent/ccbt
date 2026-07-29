"""Integration regression: magnet cold start should not collapse swarm queue."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.session]


@pytest.mark.asyncio
async def test_magnet_cold_start_metadata_before_bulk_enqueue(tmp_path) -> None:
    """Metadata fetch should be scheduled before bulk overflow when metadata is missing."""
    from ccbt.session.session import AsyncTorrentSession

    td = {
        "name": "cold-magnet",
        "info_hash": b"\x01" * 20,
        "announce": "http://tracker.example/announce",
        "pieces_info": {
            "num_pieces": 0,
            "piece_length": 0,
            "piece_hashes": [],
            "total_length": 0,
        },
        "file_info": {"total_length": 0},
    }
    session = AsyncTorrentSession(td, str(tmp_path))
    session.config.discovery.tracker_ingress_hold_pending_queue_threshold = 5
    session.config.discovery.tracker_immediate_pending_budget_max = 2
    session.config.discovery.tracker_immediate_connect_burst_total = 20
    session.tracker = SimpleNamespace(on_peers_received=None)

    metadata_calls: list[int] = []
    connect_calls: list[int] = []

    async def fake_metadata(peers: list[object], **_kwargs: object) -> bool:
        metadata_calls.append(len(peers))
        return False

    async def fake_connect(_session: object, peers: list[dict[str, object]]) -> SimpleNamespace:
        connect_calls.append(len(peers))
        return SimpleNamespace(status="owner_started", upstream_peer_count=len(peers))

    peer_manager = MagicMock()
    peer_manager.get_active_peers = MagicMock(return_value=[])
    peer_manager.connections = {}
    peer_manager._pending_peer_queue = []
    peer_manager._pending_peer_queue_lock = asyncio.Lock()
    peer_manager._batch_owner_active = False
    session.download_manager.peer_manager = peer_manager
    session.handle_magnet_metadata_exchange = AsyncMock(side_effect=fake_metadata)
    session._get_swarm_recovery_state = AsyncMock(
        return_value={
            "metadata_incomplete": True,
            "requestable_peers": 0,
            "productive_peers": 0,
            "peers_with_piece_info": 0,
            "active_peers": 0,
        }
    )

    peers = [
        {"ip": f"10.0.0.{i}", "port": 6881 + i, "peer_source": "tracker"}
        for i in range(1, 12)
    ]

    session._register_immediate_connection_callback()  # noqa: SLF001
    callback = session.tracker.on_peers_received
    assert callback is not None

    with patch(
        "ccbt.session.session.PeerConnectionHelper.connect_peers_to_download",
        new=AsyncMock(side_effect=fake_connect),
    ):
        await callback(peers, "udp://tracker:80")
        await asyncio.sleep(0.05)

    assert metadata_calls, "metadata fallback should run during magnet cold start"
    assert metadata_calls[0] > 0
    session.handle_magnet_metadata_exchange.assert_awaited()
