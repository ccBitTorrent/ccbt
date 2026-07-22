"""Tests for multi-peer piece selection and pipeline-aware batch sizing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.peer.peer import PeerInfo
from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState


def _build_peer(
    ip: str,
    port: int,
    *,
    pieces: set[int],
    outstanding: int = 0,
    max_depth: int = 12,
    choking: bool = False,
    can_request: bool = True,
) -> MagicMock:
    peer = MagicMock()
    peer.peer_info = PeerInfo(ip=ip, port=port)
    peer.peer_choking = choking
    peer.can_request.return_value = can_request
    peer.max_pipeline_depth = max_depth
    peer.outstanding_requests = {i: object() for i in range(outstanding)}
    peer.is_active.return_value = True
    peer.peer_state = SimpleNamespace(pieces_we_have=pieces, bitfield=b"\xff")
    return peer


@pytest.fixture
def torrent_data() -> dict:
    return {
        "info_hash": b"\x00" * 20,
        "file_info": {
            "name": "test_file.txt",
            "total_length": 10 * 16384,
            "type": "single",
        },
        "pieces_info": {
            "num_pieces": 10,
            "piece_length": 16384,
            "piece_hashes": [b"\x01" * 20 for _ in range(10)],
        },
    }


@pytest.fixture
def piece_manager(torrent_data: dict) -> AsyncPieceManager:
    return AsyncPieceManager(torrent_data)


class TestSwarmPipelineHelpers:
    def test_swarm_pipeline_budget_counts_free_slots(self) -> None:
        peers = [
            _build_peer("1.1.1.1", 6881, pieces={0}, outstanding=10, max_depth=12),
            _build_peer("2.2.2.2", 6882, pieces={0}, outstanding=12, max_depth=12),
            _build_peer("3.3.3.3", 6883, pieces={0}, choking=True),
        ]
        free, capacity = AsyncPieceManager._swarm_pipeline_budget(peers)
        assert free == 2
        assert capacity == 24

    def test_compute_adaptive_request_count_caps_by_pipeline(self) -> None:
        count = AsyncPieceManager._compute_adaptive_request_count(
            5,
            pipeline_free_slots=8,
            blocks_per_piece_estimate=4,
        )
        assert count == 2

    def test_compute_adaptive_request_count_scales_with_requestable_peers(
        self,
    ) -> None:
        count = AsyncPieceManager._compute_adaptive_request_count(
            3,
            pipeline_free_slots=100,
        )
        assert count == 11

    def test_round_robin_rotates_peers(self, piece_manager: AsyncPieceManager) -> None:
        peers = [
            _build_peer("1.1.1.1", 6881, pieces={0}),
            _build_peer("2.2.2.2", 6882, pieces={0}),
            _build_peer("3.3.3.3", 6883, pieces={0}),
        ]
        first = piece_manager._round_robin_pick_peer(peers)
        second = piece_manager._round_robin_pick_peer(peers)
        third = piece_manager._round_robin_pick_peer(peers)
        fourth = piece_manager._round_robin_pick_peer(peers)
        assert first is peers[0]
        assert second is peers[1]
        assert third is peers[2]
        assert fourth is peers[0]

    def test_peers_with_piece_pipeline_room_prefers_more_headroom(
        self, piece_manager: AsyncPieceManager
    ) -> None:
        peer_a = _build_peer("1.1.1.1", 6881, pieces={0}, outstanding=2, max_depth=12)
        peer_b = _build_peer("2.2.2.2", 6882, pieces={0}, outstanding=8, max_depth=12)
        piece_manager.peer_availability["1.1.1.1:6881"] = SimpleNamespace(
            pieces={0},
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )
        piece_manager.peer_availability["2.2.2.2:6882"] = SimpleNamespace(
            pieces={0},
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )

        ordered = piece_manager._peers_with_piece_pipeline_room(
            [peer_b, peer_a],
            0,
            low_peer_leniency=False,
        )
        assert ordered[0] is peer_a
        assert ordered[1] is peer_b

    def test_should_not_throttle_two_peer_swarm(self) -> None:
        assert (
            AsyncPieceManager._should_throttle_swarm_requests(
                active_peer_count=2,
                requestable_peer_count=2,
                peers_with_availability=2,
            )
            is False
        )

    def test_effective_pipeline_cap_full_depth_for_two_peers(self) -> None:
        peer = _build_peer("1.1.1.1", 6881, pieces={0}, max_depth=12)
        cap = AsyncPieceManager._peer_effective_pipeline_cap(
            peer,
            active_peer_count=2,
            throttle_requests=False,
        )
        assert cap == 12

    def test_effective_pipeline_cap_honest_budget_at_saturation(self) -> None:
        peers = [
            _build_peer("1.1.1.1", 6881, pieces={0}, outstanding=6, max_depth=12),
            _build_peer("2.2.2.2", 6882, pieces={0}, outstanding=6, max_depth=12),
        ]
        free, capacity = AsyncPieceManager._swarm_pipeline_budget(
            peers,
            active_peer_count=2,
            throttle_requests=False,
        )
        assert free == 12
        assert capacity == 24

    def test_throttle_reduces_cap_for_mid_sized_swarm(self) -> None:
        peer = _build_peer("1.1.1.1", 6881, pieces={0}, max_depth=12)
        cap = AsyncPieceManager._peer_effective_pipeline_cap(
            peer,
            active_peer_count=5,
            throttle_requests=True,
        )
        assert cap == 6


class TestPipelineBlockedRetry:
    @pytest.mark.asyncio
    async def test_retry_pipeline_blocked_peers_cleans_saturated(
        self, piece_manager: AsyncPieceManager
    ) -> None:
        saturated = _build_peer(
            "1.1.1.1",
            6881,
            pieces={0},
            outstanding=12,
            max_depth=12,
            can_request=False,
        )
        underloaded = _build_peer(
            "2.2.2.2",
            6882,
            pieces={0},
            outstanding=0,
            max_depth=12,
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [saturated, underloaded],
            _cleanup_timed_out_requests=AsyncMock(),
        )
        piece_manager._peer_manager = peer_manager
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.peer_availability["2.2.2.2:6882"] = SimpleNamespace(
            pieces={0},
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )
        piece_manager.request_piece_from_peers = AsyncMock()

        await piece_manager._retry_pipeline_blocked_peers()

        peer_manager._cleanup_timed_out_requests.assert_any_await(saturated)
        assert piece_manager.request_piece_from_peers.await_count >= 1


class TestAdaptiveBatchInSelection:
    @pytest.mark.asyncio
    async def test_saturated_pipeline_defers_new_selection(
        self, piece_manager: AsyncPieceManager
    ) -> None:
        saturated = _build_peer(
            "1.1.1.1",
            6881,
            pieces={0, 1, 2, 3, 4},
            outstanding=12,
            max_depth=12,
            can_request=True,
        )
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [saturated]
        )
        piece_manager._metadata_incomplete = False
        piece_manager.peer_availability["1.1.1.1:6881"] = SimpleNamespace(
            pieces={0, 1, 2, 3, 4},
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )
        for idx in range(5):
            piece_manager.pieces[idx].state = PieceState.MISSING

        piece_manager.request_piece_from_peers = AsyncMock()
        piece_manager._retry_pipeline_blocked_peers = AsyncMock()

        await piece_manager._select_rarest_first()
        await asyncio.sleep(0)

        piece_manager.request_piece_from_peers.assert_not_awaited()
        piece_manager._retry_pipeline_blocked_peers.assert_awaited_once()


class TestPeerAvailabilitySync:
    @pytest.mark.asyncio
    async def test_sync_active_peer_availability_from_bitfield(
        self, piece_manager: AsyncPieceManager
    ) -> None:
        """Empty peer_availability entries are repopulated from connection bitfields."""
        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="10.0.0.5", port=6881)
        peer.bitfield = b"\xff\xff"
        peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"\xff\xff")

        piece_manager.peer_availability["10.0.0.5:6881"] = SimpleNamespace(
            pieces=set(),
            last_updated=0.0,
        )
        piece_manager.num_pieces = 10

        synced = await piece_manager._sync_active_peer_availability_from_connections(
            [peer]
        )

        assert synced == 1
        assert len(piece_manager.peer_availability["10.0.0.5:6881"].pieces) > 0

    @pytest.mark.asyncio
    async def test_optimistic_selection_when_pipeline_saturated(
        self, torrent_data: dict
    ) -> None:
        """Optimistic fallback still selects pieces when pipeline batch cap is zero."""
        manager = AsyncPieceManager(torrent_data)
        manager._metadata_incomplete = False
        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="10.0.0.5", port=6881)
        peer.can_request.return_value = True
        peer.peer_choking = False
        peer.max_pipeline_depth = 12
        peer.outstanding_requests = {}
        peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        peer.is_active.return_value = True

        manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [peer])
        manager.peer_availability["10.0.0.5:6881"] = SimpleNamespace(
            pieces=set(),
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )
        for piece in manager.pieces:
            piece.state = PieceState.MISSING

        manager.request_piece_from_peers = AsyncMock()
        manager._retry_pipeline_blocked_peers = AsyncMock()

        await manager._sync_active_peer_availability_from_connections([peer])
        await manager._select_rarest_first()
        await asyncio.sleep(0)

        assert manager.request_piece_from_peers.await_count >= 1
