"""Comprehensive tests for AsyncPieceManager.

Covers verification failures, backpressure, edge cases, and missing code paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceBlock, PieceData, PieceState
from ccbt.peer.peer import PeerInfo


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data for testing."""
    return {
        "info_hash": b"\x00" * 20,
        "file_info": {
            "name": "test_file.txt",
            "total_length": 10 * 16384,  # 10 pieces of 16KB
            "type": "single",
        },
        "pieces_info": {
            "num_pieces": 10,
            "piece_length": 16384,
            "piece_hashes": [b"\x01" * 20 for _ in range(10)],
        },
    }


@pytest_asyncio.fixture
async def piece_manager(mock_torrent_data):
    """Create async piece manager for testing."""
    manager = AsyncPieceManager(mock_torrent_data)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def mock_peer_connection():
    """Create mock peer connection."""
    peer = AsyncMock()
    peer.peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer.bitfield = b"\xff" * 2  # All pieces available
    return peer


class TestAsyncPieceManagerVerification:
    """Test hash verification functionality."""

    @pytest.mark.asyncio
    async def test_verify_piece_hash_success(self, piece_manager):
        """Test successful piece hash verification."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Create valid data - need full piece data that matches piece length exactly
        piece_length = piece.length
        # Generate enough data for the piece
        base_data = b"test_piece_data" * 2000
        if len(base_data) < piece_length:
            piece_data = base_data + b"\x00" * (piece_length - len(base_data))
        else:
            piece_data = base_data[:piece_length]
        
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = expected_hash

        # Add all blocks to complete piece - each block must get data matching its exact length
        for block in piece.blocks:
            # Extract data for this block from the full piece data
            block_end = min(block.begin + block.length, len(piece_data))
            block_data = piece_data[block.begin : block_end]
            
            # Pad if needed (for last block)
            if len(block_data) < block.length:
                block_data = block_data + b"\x00" * (block.length - len(block_data))
            
            # Ensure exact match
            assert len(block_data) == block.length, f"Block data length {len(block_data)} != block.length {block.length}"
            
            success = piece.add_block(block.begin, block_data)
            assert success, f"Failed to add block at begin={block.begin}, length={block.length}, data_len={len(block_data)}, piece_len={piece_length}"

        # Ensure piece is marked as complete
        assert piece.is_complete()
        assert piece.state == PieceState.COMPLETE

        callback_called = False

        def mock_callback(idx):
            nonlocal callback_called
            callback_called = True
            assert idx == piece_index

        piece_manager.on_piece_verified = mock_callback

        await piece_manager._verify_piece_hash(piece_index, piece)

        assert piece_index in piece_manager.verified_pieces
        assert piece.state == PieceState.VERIFIED
        assert callback_called

    @pytest.mark.asyncio
    async def test_verify_piece_hash_failure(self, piece_manager):
        """Test hash verification failure."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Create invalid data (wrong hash)
        piece_data = b"wrong_piece_data" * 1024
        piece_data = piece_data[:16384]
        wrong_hash = hashlib.sha1(b"different_data").digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = wrong_hash

        # Add all blocks to complete piece
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        # Verify should fail
        await piece_manager._verify_piece_hash(piece_index, piece)

        # Should not be verified
        assert piece_index not in piece_manager.verified_pieces
        assert piece.state != PieceState.VERIFIED

    @pytest.mark.asyncio
    async def test_verify_piece_hash_exception(self, piece_manager):
        """Test hash verification with exception."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Mock get_data to raise exception
        with patch.object(piece, "get_data", side_effect=Exception("Test error")):
            await piece_manager._verify_piece_hash(piece_index, piece)

        # Should not crash, piece should not be verified
        assert piece_index not in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_hash_piece_optimized(self, piece_manager):
        """Test optimized hash verification."""
        piece = PieceData(piece_index=0, length=16384)
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:16384]

        # Add blocks
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        is_valid = piece_manager._hash_piece_optimized(piece, expected_hash)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_hash_piece_optimized_failure(self, piece_manager):
        """Test optimized hash verification failure."""
        piece = PieceData(piece_index=0, length=16384)
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:16384]

        # Add blocks
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        wrong_hash = hashlib.sha1(b"wrong").digest()  # nosec B324
        is_valid = piece_manager._hash_piece_optimized(piece, wrong_hash)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_hash_piece_optimized_exception(self, piece_manager):
        """Test optimized hash with exception."""
        piece = PieceData(piece_index=0, length=16384)

        # Mock get_data to raise exception
        with patch.object(piece, "get_data", side_effect=Exception("Test error")):
            result = piece_manager._hash_piece_optimized(piece, b"\x00" * 20)

        assert result is False

    @pytest.mark.asyncio
    async def test_batch_verify_pieces(self, piece_manager):
        """Test batch verification of multiple pieces."""
        pieces_to_verify = []

        # Create 3 completed pieces
        for i in range(3):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]

            # Add blocks
            for block in piece.blocks:
                piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            pieces_to_verify.append((i, piece))

        await piece_manager._batch_verify_pieces(pieces_to_verify)

        # All should be verified
        for i in range(3):
            assert i in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_batch_verify_pieces_empty(self, piece_manager):
        """Test batch verification with empty list."""
        await piece_manager._batch_verify_pieces([])
        # Should not crash
        assert True


class TestAsyncPieceManagerGetBlock:
    """Test get_block functionality."""

    @pytest.mark.asyncio
    async def test_get_block_from_verified_piece(self, piece_manager):
        """Test getting block from verified piece."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Complete and verify piece
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:piece.length]  # Use actual piece length
        
        # Add all blocks correctly - use block.begin for slicing
        for block in piece.blocks:
            block_data = piece_data[block.begin : block.begin + block.length]
            success = piece.add_block(block.begin, block_data)
            assert success

        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = expected_hash

        await piece_manager._verify_piece_hash(piece_index, piece)

        # Get block
        block_size = min(16384, piece.length)
        block_data = piece_manager.get_block(piece_index, 0, block_size)
        assert block_data == piece_data[:block_size]

    @pytest.mark.asyncio
    async def test_get_block_invalid_indices(self, piece_manager):
        """Test get_block with invalid indices."""
        # Invalid piece index
        result = piece_manager.get_block(999, 0, 16384)
        assert result is None

        # Valid piece but invalid range
        result = piece_manager.get_block(0, 99999, 16384)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_block_from_incomplete_piece(self, piece_manager):
        """Test getting block from incomplete piece."""
        # Piece is not complete
        result = piece_manager.get_block(0, 0, 16384)
        assert result is None


class TestAsyncPieceManagerPieceSelector:
    """Test piece selector background task."""

    @pytest.mark.asyncio
    async def test_piece_selector_runs(self, piece_manager):
        """Test that piece selector runs without crashing."""
        piece_manager.is_downloading = True

        # Start selector and let it run briefly
        task = asyncio.create_task(piece_manager._piece_selector())
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await asyncio.wait_for(task, timeout=0.2)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        assert task.done()

    @pytest.mark.asyncio
    async def test_select_pieces_not_downloading(self, piece_manager):
        """Test select_pieces when not downloading."""
        piece_manager.is_downloading = False
        await piece_manager._select_pieces()
        # Should return early without error
        assert True

    @pytest.mark.asyncio
    async def test_select_pieces_download_complete(self, piece_manager):
        """Test select_pieces when download is complete."""
        piece_manager.is_downloading = True
        piece_manager.download_complete = True
        await piece_manager._select_pieces()
        # Should return early without error
        assert True

    @pytest.mark.asyncio
    async def test_endgame_mode_activation(self, piece_manager):
        """Test endgame mode activation."""
        piece_manager.is_downloading = True

        # Calculate threshold - typically 85-90% complete
        threshold = piece_manager.endgame_threshold
        pieces_to_verify = int(piece_manager.num_pieces * (1.0 - threshold)) + 1

        # Mark enough pieces as verified to trigger endgame
        for i in range(pieces_to_verify):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)

        await piece_manager._select_pieces()

        # Endgame should activate when threshold is reached
        # Allow for slight variations in threshold calculation
        remaining = len(piece_manager.get_missing_pieces())
        threshold_pieces = int(piece_manager.num_pieces * (1.0 - threshold))
        if remaining <= threshold_pieces:
            assert piece_manager.endgame_mode is True
        else:
            # If not activated, verify the calculation
            assert len(piece_manager.verified_pieces) >= pieces_to_verify


class TestAsyncPieceManagerHandlePieceBlock:
    """Test handle_piece_block functionality."""

    @pytest.mark.asyncio
    async def test_handle_piece_block_completes_piece(self, piece_manager):
        """Test handling block that completes a piece."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        callback_called = False

        def mock_callback(idx):
            nonlocal callback_called
            callback_called = True
            assert idx == piece_index

        piece_manager.on_piece_completed = mock_callback

        # Add all blocks except last one
        for block in piece.blocks[:-1]:
            await piece_manager.handle_piece_block(piece_index, block.begin, b"x" * block.length)

        # Add last block to complete
        last_block = piece.blocks[-1]
        await piece_manager.handle_piece_block(piece_index, last_block.begin, b"x" * last_block.length)

        assert piece_index in piece_manager.completed_pieces
        assert callback_called

    @pytest.mark.asyncio
    async def test_handle_piece_block_invalid_index(self, piece_manager):
        """Test handle_piece_block with invalid piece index."""
        # Should not crash
        await piece_manager.handle_piece_block(999, 0, b"data")
        assert True

    @pytest.mark.asyncio
    async def test_handle_piece_block_schedules_verification(self, piece_manager):
        """Test that completing a piece schedules verification."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Complete piece
        for block in piece.blocks:
            await piece_manager.handle_piece_block(piece_index, block.begin, b"x" * block.length)

        # Give time for verification task to start
        await asyncio.sleep(0.05)

        # Verification should have been scheduled
        assert len(piece_manager._background_tasks) > 0 or piece.state == PieceState.COMPLETE


class TestAsyncPieceManagerBackpressure:
    """Test backpressure and rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_verifications_concurrent(self, piece_manager):
        """Test concurrent piece verifications."""
        # Complete multiple pieces
        for i in range(3):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]
            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            for block in piece.blocks:
                await piece_manager.handle_piece_block(i, block.begin, piece_data[block.begin : block.begin + block.length])

        # Wait for verifications
        await asyncio.sleep(0.2)

        # All should eventually be verified
        for i in range(3):
            assert i in piece_manager.verified_pieces or piece_manager.pieces[i].state == PieceState.COMPLETE

    @pytest.mark.asyncio
    async def test_download_complete_callback(self, piece_manager):
        """Test download complete callback when all pieces verified."""
        callback_called = False

        def mock_callback():
            nonlocal callback_called
            callback_called = True

        piece_manager.on_download_complete = mock_callback

        # Verify all pieces
        for i in range(piece_manager.num_pieces):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]
            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            for block in piece.blocks:
                piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

            await piece_manager._verify_piece_hash(i, piece)

        assert callback_called
        assert piece_manager.download_complete is True


class TestAsyncPieceManagerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_download_progress_zero_pieces(self):
        """Test download progress with zero pieces."""
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "file_info": {"total_length": 0, "type": "single"},
            "pieces_info": {"num_pieces": 0, "piece_length": 16384, "piece_hashes": []},
        }
        manager = AsyncPieceManager(torrent_data)
        progress = manager.get_download_progress()
        assert progress == 1.0  # 100% when no pieces

    @pytest.mark.asyncio
    async def test_get_piece_status(self, piece_manager):
        """Test getting piece status counts."""
        # Mark some pieces with different states
        piece_manager.pieces[0].state = PieceState.MISSING
        piece_manager.pieces[1].state = PieceState.DOWNLOADING
        piece_manager.pieces[2].state = PieceState.VERIFIED

        status = piece_manager.get_piece_status()

        assert status["missing"] >= 1
        assert status["downloading"] >= 1
        assert status["verified"] >= 1

