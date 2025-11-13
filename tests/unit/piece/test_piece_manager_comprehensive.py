"""Comprehensive tests for piece_manager.py to achieve 95%+ coverage.

Covers missing lines:
- PieceData.add_block return False paths (line 80)
- PieceData.get_data data_buffer path (line 93)
- PieceData.verify_hash incomplete piece path (line 103)
- PieceManager.handle_piece_block validation and error paths (lines 188, 211)
- PieceManager._verify_piece_hash threading path (lines 207, 216-231)
- PieceManager._verify_piece_hash_sync failure path (lines 242-243)
- PieceManager._hash_piece_optimized data_buffer path (line 249)
- PieceManager._hash_piece_optimized large piece chunk size (line 260)
- PieceManager._hash_piece_optimized exception handling (lines 272-279)
- PieceManager.get_piece_data edge cases (line 303)
- PieceManager.get_download_progress edge case (line 316)
- PieceManager.request_piece_from_peers validation (lines 358, 362)
"""

from __future__ import annotations

import hashlib
import threading
import time
from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.piece.piece_manager import PieceBlock, PieceData, PieceManager, PieceState


class TestPieceDataCoverageGaps:
    """Test PieceData coverage gaps."""

    def test_add_block_returns_false_when_no_matching_block(self):
        """Test add_block returns False when no matching block (line 80)."""
        piece = PieceData(0, 16384)

        # Try to add block with wrong begin offset
        result = piece.add_block(100, b"x" * 16384)
        assert result is False

        # Try to add block that doesn't match any block
        result = piece.add_block(20000, b"x" * 1000)
        assert result is False

    def test_get_data_with_data_buffer(self):
        """Test get_data uses data_buffer when available (line 93)."""
        piece = PieceData(0, 100)
        piece.data_buffer = bytearray(b"test_data" * 12)  # 108 bytes, padded
        
        # Manually mark as complete
        piece.blocks[0].received = True
        piece.blocks[0].data = b"x" * 100
        piece.state = PieceState.COMPLETE

        # get_data should use data_buffer
        data = piece.get_data()
        assert len(data) == 108
        assert data.startswith(b"test_data")

    def test_verify_hash_incomplete_piece(self):
        """Test verify_hash returns False for incomplete piece (line 103)."""
        piece = PieceData(0, 100)
        # Piece is not complete
        piece.blocks[0].received = False

        expected_hash = hashlib.sha1(b"test").digest()  # nosec B324
        result = piece.verify_hash(expected_hash)

        assert result is False
        assert not piece.hash_verified


class TestPieceManagerCoverageGaps:
    """Test PieceManager coverage gaps."""

    def setup_method(self):
        """Set up test fixtures."""
        self.torrent_data = {
            "pieces_info": {
                "num_pieces": 4,
                "piece_length": 16384,
                "piece_hashes": [
                    hashlib.sha1(b"piece0_data").digest(),  # nosec B324
                    hashlib.sha1(b"piece1_data").digest(),  # nosec B324
                    hashlib.sha1(b"piece2_data").digest(),  # nosec B324
                    hashlib.sha1(b"piece3_data").digest(),  # nosec B324
                ],
            },
            "file_info": {
                "total_length": 65536,  # 4 * 16384
            },
        }
        self.manager = PieceManager(self.torrent_data)

    def test_handle_piece_block_invalid_piece_index(self):
        """Test handle_piece_block with invalid piece_index (line 188)."""
        # Try with piece_index >= num_pieces
        result = self.manager.handle_piece_block(999, 0, b"data")
        assert result is False

        # Try with negative piece_index
        result = self.manager.handle_piece_block(-1, 0, b"data")
        assert result is False

    def test_handle_piece_block_fails_when_add_block_fails(self):
        """Test handle_piece_block returns False when add_block fails (line 211)."""
        # Try to add block with wrong data
        result = self.manager.handle_piece_block(0, 0, b"wrong_length")
        assert result is False

    def test_verify_piece_hash_threading_path(self):
        """Test _verify_piece_hash threading path (lines 207, 216-231)."""
        # Disable test_mode to use threading path
        self.manager.test_mode = False

        # Complete a piece with correct hash
        piece_data = b"piece0_data" + b"x" * (16384 - 11)
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        # Set up callback to track verification
        verified_pieces = []

        def on_verified(piece_index):
            verified_pieces.append(piece_index)

        self.manager.on_piece_verified = on_verified

        # Handle piece block (should trigger async verification)
        self.manager.handle_piece_block(0, 0, piece_data)

        # Wait for thread to complete
        time.sleep(0.1)

        # Piece should eventually be verified
        assert 0 in self.manager.verified_pieces or len(verified_pieces) > 0

    def test_verify_piece_hash_threading_failure_path(self):
        """Test _verify_piece_hash threading path with hash failure (lines 216-231)."""
        # Disable test_mode to use threading path
        self.manager.test_mode = False

        # Complete a piece with wrong hash
        piece_data = b"wrong_data" + b"x" * (16384 - 10)
        # Keep original hash (will not match)
        # self.manager.piece_hashes[0] stays as original

        # Handle piece block (should trigger async verification)
        self.manager.handle_piece_block(0, 0, piece_data)

        # Wait for thread to complete
        time.sleep(0.1)

        # Piece should be marked as missing after failed verification
        assert self.manager.pieces[0].state == PieceState.MISSING
        assert 0 not in self.manager.verified_pieces

    def test_verify_piece_hash_sync_failure_path(self):
        """Test _verify_piece_hash_sync failure path (lines 242-243)."""
        self.manager.test_mode = True

        # Complete a piece with wrong hash
        piece_data = b"wrong_data" + b"x" * (16384 - 10)
        # Keep original hash (will not match)

        # Manually trigger sync verification
        piece = self.manager.pieces[0]
        piece.blocks[0].data = piece_data
        piece.blocks[0].received = True
        piece.state = PieceState.COMPLETE
        self.manager.completed_pieces.add(0)

        self.manager._verify_piece_hash_sync(piece)

        # Piece should be marked as missing
        assert piece.state == PieceState.MISSING
        assert 0 not in self.manager.completed_pieces
        assert 0 not in self.manager.verified_pieces

    def test_hash_piece_optimized_with_data_buffer(self):
        """Test _hash_piece_optimized with data_buffer (line 249)."""
        piece = PieceData(0, 100)
        piece.data_buffer = bytearray(b"test_data" * 15)  # 135 bytes
        
        # Mark piece as complete
        piece.blocks[0].received = True
        piece.blocks[0].data = b"x" * 100
        piece.state = PieceState.COMPLETE

        expected_hash = hashlib.sha1(piece.data_buffer).digest()  # nosec B324

        result = self.manager._hash_piece_optimized(piece, expected_hash)

        assert result is True
        assert piece.hash_verified
        assert piece.state == PieceState.VERIFIED

    def test_hash_piece_optimized_large_piece(self):
        """Test _hash_piece_optimized with large piece (>1MB) (line 260)."""
        # Create a piece larger than 1MB
        large_piece_length = 2 * 1024 * 1024  # 2MB
        piece = PieceData(0, large_piece_length)
        
        # Create data matching expected hash
        test_data = b"x" * large_piece_length
        expected_hash = hashlib.sha1(test_data).digest()  # nosec B324

        # Mark all blocks as received with test data
        offset = 0
        for block in piece.blocks:
            block.data = test_data[offset:offset+block.length]
            block.received = True
            offset += block.length
        piece.state = PieceState.COMPLETE

        result = self.manager._hash_piece_optimized(piece, expected_hash)

        assert result is True
        assert piece.hash_verified
        assert piece.state == PieceState.VERIFIED

    def test_hash_piece_optimized_exception_handling(self):
        """Test _hash_piece_optimized exception handling (lines 272-279)."""
        piece = PieceData(0, 100)
        
        # Mark piece as complete
        piece.blocks[0].received = True
        piece.blocks[0].data = b"x" * 100
        piece.state = PieceState.COMPLETE

        expected_hash = hashlib.sha1(b"test").digest()  # nosec B324

        # Mock get_data to raise exception
        with patch.object(piece, 'get_data', side_effect=Exception("Test error")):
            result = self.manager._hash_piece_optimized(piece, expected_hash)

        assert result is False
        assert not piece.hash_verified

    def test_get_piece_data_not_verified(self):
        """Test get_piece_data returns None for non-verified piece (line 303)."""
        piece = self.manager.pieces[0]
        piece.state = PieceState.COMPLETE  # Not verified

        result = self.manager.get_piece_data(0)
        assert result is None

    def test_get_download_progress_zero_pieces(self):
        """Test get_download_progress with zero pieces (line 316)."""
        # Create manager with zero pieces (edge case)
        torrent_data = {
            "pieces_info": {
                "num_pieces": 0,
                "piece_length": 16384,
                "piece_hashes": [],
            },
            "file_info": {
                "total_length": 0,
            },
        }
        manager = PieceManager(torrent_data)

        progress = manager.get_download_progress()
        assert progress == 1.0  # Should return 1.0 for zero pieces

    def test_request_piece_from_peers_invalid_index(self):
        """Test request_piece_from_peers with invalid piece_index (line 358)."""
        mock_peer_manager = Mock()

        # Try with piece_index >= num_pieces
        self.manager.request_piece_from_peers(999, mock_peer_manager)

        # Should not call peer_manager methods
        mock_peer_manager.get_active_peers.assert_not_called()

    def test_request_piece_from_peers_not_missing_state(self):
        """Test request_piece_from_peers when piece not in MISSING state (line 362)."""
        mock_peer_manager = Mock()

        # Mark piece as downloading (not missing)
        self.manager.pieces[0].state = PieceState.DOWNLOADING

        self.manager.request_piece_from_peers(0, mock_peer_manager)

        # Should not call peer_manager methods
        mock_peer_manager.get_active_peers.assert_not_called()

    def test_request_piece_from_peers_no_unchoked_peers(self):
        """Test request_piece_from_peers when all peers are choked."""
        mock_peer_manager = Mock()
        mock_connection = Mock()
        mock_connection.peer_state.am_choking = True  # Peer is choking
        mock_peer_manager.get_active_peers.return_value = [mock_connection]
        mock_peer_manager.request_piece = Mock()

        self.manager.request_piece_from_peers(0, mock_peer_manager)

        # Should mark as downloading
        assert self.manager.pieces[0].state == PieceState.DOWNLOADING

        # But should not request from choked peer
        mock_peer_manager.request_piece.assert_not_called()

    def test_request_piece_from_peers_peer_without_peer_state(self):
        """Test request_piece_from_peers when peer has no peer_state attribute."""
        mock_peer_manager = Mock()
        mock_connection = Mock()
        del mock_connection.peer_state  # Remove attribute
        mock_peer_manager.get_active_peers.return_value = [mock_connection]
        mock_peer_manager.request_piece = Mock()

        self.manager.request_piece_from_peers(0, mock_peer_manager)

        # Should mark as downloading
        assert self.manager.pieces[0].state == PieceState.DOWNLOADING

        # But should not request from peer without peer_state
        mock_peer_manager.request_piece.assert_not_called()

    def test_verify_piece_hash_thread_with_callback_none(self):
        """Test _verify_piece_hash when on_piece_verified is None (line 223)."""
        self.manager.test_mode = False
        self.manager.on_piece_verified = None

        # Complete a piece with correct hash
        piece_data = b"piece0_data" + b"x" * (16384 - 11)
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        # Handle piece block
        self.manager.handle_piece_block(0, 0, piece_data)

        # Wait for thread
        time.sleep(0.1)

        # Should still verify without error
        assert 0 in self.manager.verified_pieces or self.manager.pieces[0].state == PieceState.VERIFIED

    def test_verify_piece_hash_sync_with_callback_none(self):
        """Test _verify_piece_hash_sync when on_piece_verified is None (line 240)."""
        self.manager.test_mode = True
        self.manager.on_piece_verified = None

        # Complete a piece
        piece_data = b"piece0_data" + b"x" * (16384 - 11)
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        piece = self.manager.pieces[0]
        piece.blocks[0].data = piece_data
        piece.blocks[0].received = True
        piece.state = PieceState.COMPLETE
        self.manager.completed_pieces.add(0)

        # Should not error
        self.manager._verify_piece_hash_sync(piece)
        assert 0 in self.manager.verified_pieces

