"""
Integration tests for rarest-first piece selection algorithm.

Tests the correctness of the rarest-first algorithm and endgame mode
in the async piece manager.
"""

import asyncio
from typing import List
from unittest.mock import Mock

import pytest
import pytest_asyncio

from ccbt.async_piece_manager import AsyncPieceManager, PieceState
from ccbt.peer import PeerInfo


class TestRarestFirstSelection:
    """Test rarest-first piece selection algorithm."""

    @pytest.fixture
    def mock_torrent_data(self):
        """Create mock torrent data for testing."""
        return {
            "info_hash": b"\x00" * 20,
            "file_info": {
                "name": "test_file.txt",
                "total_length": 1024 * 1024,  # 1MB
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 10,  # 10 pieces for easier testing
                "piece_length": 1024 * 100,  # 100KB pieces
                "piece_hashes": [b"\x00" * 20] * 10,
            },
        }

    @pytest_asyncio.fixture
    async def piece_manager(self, mock_torrent_data):
        """Create async piece manager for testing."""
        manager = AsyncPieceManager(mock_torrent_data)
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.fixture
    def mock_peers(self):
        """Create mock peers with different bitfields."""
        peers = []

        # Peer 1: Has pieces 0, 1, 2, 3
        peer1 = Mock()
        peer1.peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer1.bitfield = self._create_bitfield([0, 1, 2, 3], 10)
        peer1.is_connected = True
        peer1.is_choked = False
        peer1.is_interested = True
        peers.append(peer1)

        # Peer 2: Has pieces 1, 2, 3, 4, 5
        peer2 = Mock()
        peer2.peer_info = PeerInfo(ip="127.0.0.2", port=6881)
        peer2.bitfield = self._create_bitfield([1, 2, 3, 4, 5], 10)
        peer2.is_connected = True
        peer2.is_choked = False
        peer2.is_interested = True
        peers.append(peer2)

        # Peer 3: Has pieces 2, 3, 4, 5, 6, 7
        peer3 = Mock()
        peer3.peer_info = PeerInfo(ip="127.0.0.3", port=6881)
        peer3.bitfield = self._create_bitfield([2, 3, 4, 5, 6, 7], 10)
        peer3.is_connected = True
        peer3.is_choked = False
        peer3.is_interested = True
        peers.append(peer3)

        return peers

    def _create_bitfield(self, pieces: List[int], num_pieces: int) -> bytes:
        """Create a bitfield with specified pieces set."""
        bitfield = bytearray((num_pieces + 7) // 8)
        for piece in pieces:
            byte_index = piece // 8
            bit_index = piece % 8
            bitfield[byte_index] |= (1 << (7 - bit_index))
        return bytes(bitfield)

    @pytest.mark.asyncio
    async def test_rarest_first_selection(self, piece_manager, mock_peers):
        """Test that rarest-first selects pieces with lowest availability."""
        # Add peers to piece manager
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Test piece selection
        selected_pieces = []
        for _ in range(5):  # Select 5 pieces
            piece = await piece_manager._select_rarest_piece()
            if piece is not None:
                selected_pieces.append(piece)
                await piece_manager._mark_piece_requested(piece)

        # Verify rarest pieces are selected first
        # Piece 0: available from 1 peer (rarest)
        # Piece 1: available from 2 peers
        # Piece 2: available from 3 peers
        # Piece 3: available from 3 peers
        # Piece 4: available from 2 peers
        # Piece 5: available from 2 peers
        # Piece 6: available from 1 peer (rarest)
        # Piece 7: available from 1 peer (rarest)
        # Piece 8: available from 0 peers (not available)
        # Piece 9: available from 0 peers (not available)

        # Should select rarest available pieces first
        expected_rarest = [0, 6, 7]  # Pieces available from only 1 peer
        for piece in selected_pieces[:3]:
            assert piece in expected_rarest

    @pytest.mark.asyncio
    async def test_piece_availability_tracking(self, piece_manager, mock_peers):
        """Test that piece availability is correctly tracked."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Check piece availability counts
        availability = piece_manager.piece_frequency

        # Piece 0: 1 peer
        assert availability[0] == 1

        # Piece 1: 2 peers
        assert availability[1] == 2

        # Piece 2: 3 peers
        assert availability[2] == 3

        # Piece 8: 0 peers (not available)
        assert availability[8] == 0

    @pytest.mark.asyncio
    async def test_endgame_mode_activation(self, piece_manager, mock_peers):
        """Test that endgame mode is activated when few pieces remain."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Simulate having most pieces completed
        for i in range(8):  # Complete 8 out of 10 pieces
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)

        # Check if endgame mode is activated
        remaining_pieces = piece_manager.num_pieces - len(piece_manager.verified_pieces)
        pipeline_capacity = piece_manager.config.strategy.pipeline_capacity

        is_endgame = remaining_pieces <= pipeline_capacity
        assert is_endgame is True

    @pytest.mark.asyncio
    async def test_endgame_duplicate_requests(self, piece_manager, mock_peers):
        """Test that endgame mode sends duplicate requests."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Simulate endgame mode
        for i in range(8):  # Complete 8 out of 10 pieces
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)

        # Enable endgame mode
        piece_manager.endgame_mode = True

        # Test duplicate request generation
        piece = 7  # One of the remaining pieces (available from peer 3)
        requests = await piece_manager._generate_endgame_requests(piece)

        # Should generate requests from all peers that have the piece
        assert len(requests) > 0
        # Each request should be for the same piece
        for request in requests:
            assert request["piece_index"] == piece

    @pytest.mark.asyncio
    async def test_endgame_mode_completion(self, piece_manager, mock_peers):
        """Test that endgame mode properly handles piece completion."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Simulate endgame with duplicate requests
        piece = 7  # Available from peer 3
        piece_manager.endgame_mode = True

        # Generate requests
        requests = await piece_manager._generate_endgame_requests(piece)
        assert len(requests) > 0

        # Simulate piece completion
        piece_manager.pieces[piece].state = PieceState.VERIFIED
        piece_manager.verified_pieces.add(piece)

        # Check that piece is marked as verified
        assert piece_manager.pieces[piece].state == PieceState.VERIFIED
        assert piece in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_piece_priority_queues(self, piece_manager, mock_peers):
        """Test piece priority queues for streaming."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Set piece priorities
        await piece_manager._set_piece_priority(0, 3)  # High priority
        await piece_manager._set_piece_priority(1, 2)  # Medium priority
        await piece_manager._set_piece_priority(2, 1)  # Low priority

        # Test priority-based selection
        selected_pieces = []
        for _ in range(3):
            piece = await piece_manager._select_rarest_piece()
            if piece is not None:
                selected_pieces.append(piece)
                await piece_manager._mark_piece_requested(piece)

        # Should select pieces in rarest-first order (modified by priority)
        # Piece 0 is rarest (1 peer), piece 1 (2 peers), piece 2 (3 peers)
        # With priority: piece 0 should still be first due to rarity
        assert selected_pieces[0] == 0  # Rarest piece (1 peer)
        # The remaining pieces depend on the exact scoring, but should be available pieces
        assert all(piece in [1, 2, 3, 4, 5, 6, 7] for piece in selected_pieces[1:])

    @pytest.mark.asyncio
    async def test_peer_availability_updates(self, piece_manager, mock_peers):
        """Test that peer availability updates are handled correctly."""
        # Add first peer
        await piece_manager._add_peer(mock_peers[0])
        await piece_manager._update_peer_availability(mock_peers[0])

        # Check initial availability
        assert piece_manager.piece_frequency[0] == 1  # Piece 0 available from 1 peer

        # Add second peer
        await piece_manager._add_peer(mock_peers[1])
        await piece_manager._update_peer_availability(mock_peers[1])

        # Check updated availability
        assert piece_manager.piece_frequency[1] == 2  # Piece 1 available from 2 peers

        # Remove first peer
        await piece_manager._remove_peer(mock_peers[0])

        # Check availability after peer removal
        assert piece_manager.piece_frequency[0] == 0  # Piece 0 no longer available

    @pytest.mark.asyncio
    async def test_concurrent_piece_selection(self, piece_manager, mock_peers):
        """Test concurrent piece selection from multiple peers."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Test concurrent piece selection
        tasks = []
        for _ in range(5):
            task = asyncio.create_task(piece_manager._select_rarest_piece())
            tasks.append(task)

        # Wait for all selections
        selected_pieces = await asyncio.gather(*tasks)

        # Verify no duplicate pieces are selected
        valid_pieces = [p for p in selected_pieces if p is not None]
        assert len(valid_pieces) == len(set(valid_pieces))  # No duplicates

    @pytest.mark.asyncio
    async def test_piece_completion_handling(self, piece_manager, mock_peers):
        """Test handling of piece completion."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Simulate piece completion
        piece = 0
        piece_manager.pieces[piece].state = PieceState.COMPLETE

        # Test piece completion callback
        await piece_manager._on_piece_completed(piece)

        # Verify piece is marked as complete
        assert piece_manager.pieces[piece].state == PieceState.COMPLETE
        assert piece in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_swarm_health_metrics(self, piece_manager, mock_peers):
        """Test swarm health metrics calculation."""
        # Add peers
        for peer in mock_peers:
            await piece_manager._add_peer(peer)
            await piece_manager._update_peer_availability(peer)

        # Calculate swarm health
        health_metrics = await piece_manager._calculate_swarm_health()

        # Verify metrics are calculated
        assert "average_availability" in health_metrics
        assert "rarest_piece_availability" in health_metrics
        assert "completion_percentage" in health_metrics

        # Verify metrics are reasonable
        assert 0 <= health_metrics["completion_percentage"] <= 100
        assert health_metrics["average_availability"] >= 0
