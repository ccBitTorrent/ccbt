"""Tests for piece management functionality.
"""

import hashlib
from unittest.mock import Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.piece_manager import PieceBlock, PieceData, PieceManager, PieceState


class TestPieceBlock:
    """Test cases for PieceBlock."""

    def test_creation(self):
        """Test creating a piece block."""
        block = PieceBlock(5, 1000, 16384)

        assert block.piece_index == 5
        assert block.begin == 1000
        assert block.length == 16384
        assert not block.received
        assert block.data == b""
        assert not block.is_complete()

    def test_complete_block(self):
        """Test completing a block."""
        block = PieceBlock(5, 1000, 10)
        data = b"x" * 10

        assert block.add_block(1000, data)
        assert block.received
        assert block.data == data
        assert block.is_complete()

    def test_add_wrong_data(self):
        """Test adding wrong data to block."""
        block = PieceBlock(5, 1000, 10)

        # Wrong length
        assert not block.add_block(1000, b"x" * 5)

        # Wrong begin offset
        assert not block.add_block(999, b"x" * 10)

        # Already received
        block.received = True
        assert not block.add_block(1000, b"x" * 10)


class TestPieceData:
    """Test cases for PieceData."""

    def test_creation_single_block(self):
        """Test creating piece with single block."""
        piece = PieceData(0, 1000)

        assert piece.piece_index == 0
        assert piece.length == 1000
        assert len(piece.blocks) == 1
        assert piece.blocks[0].begin == 0
        assert piece.blocks[0].length == 1000
        assert piece.state == PieceState.MISSING

    def test_creation_multiple_blocks(self):
        """Test creating piece with multiple blocks."""
        piece = PieceData(0, 50000)  # 50KB piece

        # Should create multiple 16KB blocks
        expected_blocks = (50000 + 16383) // 16384  # 4 blocks
        assert len(piece.blocks) == expected_blocks

        # Check block boundaries
        assert piece.blocks[0].begin == 0
        assert piece.blocks[0].length == 16384

        assert piece.blocks[1].begin == 16384
        assert piece.blocks[1].length == 16384

        assert piece.blocks[2].begin == 32768
        assert piece.blocks[2].length == 16384

        # Last block should be smaller
        assert piece.blocks[3].begin == 49152
        assert piece.blocks[3].length == 848  # 50000 - 49152

    def test_add_block(self):
        """Test adding blocks to piece."""
        piece = PieceData(0, 1000)

        # Add first block
        assert piece.add_block(0, b"x" * 1000)
        assert piece.blocks[0].received
        assert piece.state == PieceState.COMPLETE

    def test_get_data(self):
        """Test getting piece data."""
        piece = PieceData(0, 6)  # 6 bytes

        # Manually complete all blocks
        piece.blocks[0].data = b"hello!"  # 6 bytes to match piece length
        piece.blocks[0].received = True
        piece.state = PieceState.COMPLETE

        data = piece.get_data()
        assert data == b"hello!"

    def test_get_data_incomplete(self):
        """Test getting data from incomplete piece."""
        piece = PieceData(0, 1000)

        with pytest.raises(ValueError, match="Piece 0 is not complete"):
            piece.get_data()

    def test_verify_hash(self):
        """Test hash verification."""
        # Create piece with known data
        test_data = b"hello world test data"
        piece = PieceData(0, len(test_data))

        # Manually complete the piece
        piece.blocks[0].data = test_data
        piece.blocks[0].received = True
        piece.state = PieceState.COMPLETE

        # Calculate expected hash
        expected_hash = hashlib.sha1(test_data).digest()  # nosec B324

        # Verify hash
        assert piece.verify_hash(expected_hash)
        assert piece.hash_verified
        assert piece.state == PieceState.VERIFIED

    def test_verify_hash_fail(self):
        """Test hash verification failure."""
        piece = PieceData(0, 10)

        # Manually complete with wrong data
        piece.blocks[0].data = b"x" * 10
        piece.blocks[0].received = True
        piece.state = PieceState.COMPLETE

        # Wrong hash
        wrong_hash = hashlib.sha1(b"y" * 10).digest()  # nosec B324

        assert not piece.verify_hash(wrong_hash)
        assert not piece.hash_verified
        assert piece.state == PieceState.MISSING  # Should be marked as missing


class TestPieceManager:
    """Test cases for PieceManager."""

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
        self.manager.test_mode = True  # Enable synchronous verification for tests

    def test_creation(self):
        """Test creating piece manager."""
        assert self.manager.num_pieces == 4
        assert self.manager.piece_length == 16384
        assert len(self.manager.pieces) == 4
        assert len(self.manager.piece_hashes) == 4
        assert not self.manager.is_downloading
        assert not self.manager.download_complete

    def test_get_missing_pieces(self):
        """Test getting missing pieces."""
        # Initially all pieces are missing
        missing = self.manager.get_missing_pieces()
        assert len(missing) == 4
        assert missing == [0, 1, 2, 3]

        # Mark one piece as complete
        self.manager.pieces[1].state = PieceState.COMPLETE

        missing = self.manager.get_missing_pieces()
        assert len(missing) == 3
        assert missing == [0, 2, 3]

    def test_get_random_missing_piece(self):
        """Test getting random missing piece."""
        # Initially all pieces are missing
        piece = self.manager.get_random_missing_piece()
        assert piece in [0, 1, 2, 3]

        # Mark all pieces as complete
        for p in self.manager.pieces:
            p.state = PieceState.VERIFIED

        piece = self.manager.get_random_missing_piece()
        assert piece is None

    def test_handle_piece_block(self):
        """Test handling piece block."""
        # Handle complete piece data (must match expected hash and length)
        # The expected hash is for "piece0_data" (11 bytes), so we need to pad it to 16384 bytes
        piece_data = b"piece0_data" + b"x" * (16384 - 11)  # Pad to match piece length

        # Update the expected hash to match the actual piece data
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        # Should complete the piece
        self.manager.handle_piece_block(0, 0, piece_data)

        piece = self.manager.pieces[0]
        assert piece.state == PieceState.VERIFIED  # Should be verified after hash check
        assert 0 in self.manager.completed_pieces

        # Should trigger hash verification (synchronous in test mode)
        assert piece.hash_verified
        assert 0 in self.manager.verified_pieces

    def test_handle_piece_block_multiple_blocks(self):
        """Test handling piece with multiple blocks."""
        # Create piece that needs multiple blocks (30KB)
        piece_data = b"x" * 30000  # 30KB piece
        piece = PieceData(0, 30000)
        piece.state = PieceState.MISSING  # Ensure initial state
        self.manager.pieces[0] = piece

        # Update the expected hash to match the actual piece data
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        # Add first block (16KB)
        block1 = b"x" * 16384
        self.manager.handle_piece_block(0, 0, block1)

        # Piece should be in downloading state (not complete yet)
        assert piece.state in [PieceState.DOWNLOADING, PieceState.COMPLETE]
        # Should not be complete yet since only first block received
        if len(piece.blocks) > 1:
            assert not piece.is_complete()  # Multiple blocks, not all received

        # Add second block
        block2 = b"x" * 13616  # Remaining data
        self.manager.handle_piece_block(0, 16384, block2)

        # Piece should now be complete
        assert piece.state == PieceState.VERIFIED  # Should be verified after hash check
        assert piece.is_complete()

    def test_get_piece_data(self):
        """Test getting piece data."""
        # Complete a piece with data that matches the expected hash
        piece_data = b"piece0_data"
        piece = PieceData(0, len(piece_data))
        piece.blocks[0].data = piece_data
        piece.blocks[0].received = True
        piece.state = PieceState.VERIFIED
        self.manager.pieces[0] = piece
        self.manager.verified_pieces.add(0)

        # Get piece data
        data = self.manager.get_piece_data(0)
        assert data == piece_data

        # Get non-existent piece
        data = self.manager.get_piece_data(999)
        assert data is None

    def test_get_all_piece_data(self):
        """Test getting all piece data."""
        # Complete multiple pieces with matching hashes
        for i in range(2):
            piece_data = f"piece{i}_data".encode()
            piece = PieceData(i, len(piece_data))
            piece.blocks[0].data = piece_data
            piece.blocks[0].received = True
            piece.state = PieceState.VERIFIED
            self.manager.pieces[i] = piece
            self.manager.verified_pieces.add(i)

        # Get all data
        all_data = self.manager.get_all_piece_data()
        expected = b"piece0_datapiece1_data"
        assert all_data == expected

    def test_get_download_progress(self):
        """Test getting download progress."""
        # Initially no progress
        assert self.manager.get_download_progress() == 0.0

        # Complete one piece
        self.manager.verified_pieces.add(0)
        assert self.manager.get_download_progress() == 0.25  # 1/4 pieces

        # Complete all pieces
        self.manager.verified_pieces.update([0, 1, 2, 3])
        assert self.manager.get_download_progress() == 1.0

    def test_get_piece_status(self):
        """Test getting piece status."""
        # Initially all missing
        status = self.manager.get_piece_status()
        assert status["missing"] == 4
        assert status["complete"] == 0
        assert status["verified"] == 0

        # Complete one piece
        self.manager.pieces[0].state = PieceState.COMPLETE
        self.manager.completed_pieces.add(0)

        status = self.manager.get_piece_status()
        assert status["missing"] == 3
        assert status["complete"] == 1

        # Verify one piece
        self.manager.pieces[0].state = PieceState.VERIFIED
        self.manager.verified_pieces.add(0)

        status = self.manager.get_piece_status()
        assert status["missing"] == 3
        assert status["complete"] == 0
        assert status["verified"] == 1

    def test_reset(self):
        """Test resetting piece manager."""
        # Complete some pieces
        self.manager.pieces[0].state = PieceState.VERIFIED
        self.manager.pieces[1].state = PieceState.COMPLETE
        self.manager.completed_pieces.update([0, 1])
        self.manager.verified_pieces.add(0)
        self.manager.is_downloading = True

        # Reset
        self.manager.reset()

        # All should be back to initial state
        assert all(p.state == PieceState.MISSING for p in self.manager.pieces)
        assert len(self.manager.completed_pieces) == 0
        assert len(self.manager.verified_pieces) == 0
        assert not self.manager.is_downloading
        assert not self.manager.download_complete

        # Blocks should be reset
        for piece in self.manager.pieces:
            for block in piece.blocks:
                assert not block.received
                assert block.data == b""

    def test_callbacks(self):
        """Test callback functionality."""
        # Set up callbacks
        completed_pieces = []
        verified_pieces = []
        download_complete_called = []

        def on_completed(piece_index):
            completed_pieces.append(piece_index)

        def on_verified(piece_index):
            verified_pieces.append(piece_index)

        def on_complete():
            download_complete_called.append(True)

        self.manager.on_piece_completed = on_completed
        self.manager.on_piece_verified = on_verified
        self.manager.on_download_complete = on_complete

        # Complete a piece (must match expected hash and length)
        piece_data = b"piece0_data" + b"x" * (16384 - 11)

        # Update the expected hash to match the actual piece data
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        self.manager.piece_hashes[0] = expected_hash

        self.manager.handle_piece_block(0, 0, piece_data)

        # Check callbacks (verification is synchronous in test mode)
        assert 0 in completed_pieces
        assert 0 in verified_pieces

        # Complete all pieces to trigger download complete (each must match expected hash and length)
        for i in range(1, 4):
            piece_data = f"piece{i}_data".encode() + b"x" * (16384 - 11)
            # Update the expected hash to match the actual piece data
            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            self.manager.piece_hashes[i] = expected_hash
            self.manager.handle_piece_block(i, 0, piece_data)

        # All verifications are synchronous in test mode
        assert len(download_complete_called) == 1

    def test_request_piece_from_peers_no_peers(self):
        """Test requesting piece when no peers available."""
        # Mark piece as requested
        self.manager.pieces[0].state = PieceState.MISSING

        # Create mock peer manager with no active peers
        mock_peer_manager = Mock()
        mock_peer_manager.get_active_peers.return_value = []

        # Request piece
        self.manager.request_piece_from_peers(0, mock_peer_manager)

        # Piece should be marked as missing again
        assert self.manager.pieces[0].state == PieceState.MISSING

    def test_request_piece_from_peers_with_peers(self):
        """Test requesting piece when peers are available."""
        # Mark piece as requested
        self.manager.pieces[0].state = PieceState.MISSING

        # Create mock peer manager with unchoked peers
        mock_peer_manager = Mock()
        mock_connection = Mock()
        mock_connection.peer_state.am_choking = False
        mock_peer_manager.get_active_peers.return_value = [mock_connection]

        # Mock request_piece method
        mock_peer_manager.request_piece = Mock()

        # Request piece
        self.manager.request_piece_from_peers(0, mock_peer_manager)

        # Piece should be marked as downloading
        assert self.manager.pieces[0].state == PieceState.DOWNLOADING

        # Should have requested blocks from peer
        mock_peer_manager.request_piece.assert_called()

    def test_download_loop(self):
        """Test the download loop functionality."""
        # Create mock peer manager
        mock_peer_manager = Mock()
        mock_peer_manager.get_active_peers.return_value = []

        # Start download
        self.manager.start_download(mock_peer_manager)
        assert self.manager.is_downloading

        # Stop download
        self.manager.stop_download()
        assert not self.manager.is_downloading
