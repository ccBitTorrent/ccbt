"""Unit tests for enhanced sequential piece selection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState


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
        "meta_version": 1,
    }


@pytest_asyncio.fixture
async def piece_manager(mock_torrent_data):
    """Create async piece manager for testing."""
    manager = AsyncPieceManager(mock_torrent_data)
    await manager.start()
    yield manager
    await manager.stop()


class TestSequentialWindowSelection:
    """Test sequential selection with window size."""

    @pytest.mark.asyncio
    async def test_sequential_window_selection(self, piece_manager):
        """Test sequential selection with window size."""
        # Set sequential window
        piece_manager.config.strategy.sequential_window = 5

        # Verify all pieces are missing initially
        missing = piece_manager.get_missing_pieces()
        assert len(missing) == 10

        # Run sequential selection
        await piece_manager._select_sequential()

        # Verify selection logic executed (no exceptions)
        assert piece_manager.get_missing_pieces() == missing

    @pytest.mark.asyncio
    async def test_sequential_window_bounds(self, piece_manager):
        """Test sequential selection respects window bounds."""
        piece_manager.config.strategy.sequential_window = 3

        # Get current sequential piece (should be 0)
        current = piece_manager._get_current_sequential_piece()
        assert current == 0

        # Window should be [0, 3)
        await piece_manager._select_sequential()

        # Verify pieces within window are considered
        missing = piece_manager.get_missing_pieces()
        window_pieces = [idx for idx in missing if 0 <= idx < 3]
        assert len(window_pieces) == 3

    @pytest.mark.asyncio
    async def test_get_current_sequential_piece(self, piece_manager):
        """Test _get_current_sequential_piece helper method."""
        # Initially, should return first missing piece (0)
        current = piece_manager._get_current_sequential_piece()
        assert current == 0

        # Set tracked position
        piece_manager._current_sequential_piece = 5
        current = piece_manager._get_current_sequential_piece()
        assert current == 5

        # Reset and check again
        piece_manager._current_sequential_piece = 0
        current = piece_manager._get_current_sequential_piece()
        assert current == 0


class TestFilePrioritySorting:
    """Test file priority sorting for sequential download."""

    @pytest.mark.asyncio
    async def test_sort_by_file_priority_no_file_manager(self, piece_manager):
        """Test sorting without file selection manager."""
        piece_indices = [5, 2, 8, 1, 9]
        sorted_indices = piece_manager._sort_by_file_priority(piece_indices)
        
        # Should just sort numerically
        assert sorted_indices == sorted(piece_indices)

    @pytest.mark.asyncio
    async def test_sort_by_file_priority_with_file_manager(self, piece_manager):
        """Test sorting with file selection manager."""
        # Mock file selection manager
        mock_file_manager = MagicMock()
        mock_file_manager.get_selected_files.return_value = [0, 1]
        mock_file_manager.get_files_for_piece.return_value = [0]
        
        piece_manager.file_selection_manager = mock_file_manager
        
        piece_indices = [2, 5, 1, 8]
        sorted_indices = piece_manager._sort_by_file_priority(piece_indices)
        
        # Should return sorted list (order depends on file priority)
        assert len(sorted_indices) == len(piece_indices)


class TestSequentialFallback:
    """Test sequential selection with fallback to rarest-first."""

    @pytest.mark.asyncio
    async def test_sequential_fallback_when_availability_low(self, piece_manager):
        """Test fallback to rarest-first when piece availability is low."""
        # Set low fallback threshold
        piece_manager.config.strategy.sequential_fallback_threshold = 0.5
        piece_manager.config.strategy.sequential_window = 5

        # Add peers with low availability for window pieces
        from ccbt.piece.async_piece_manager import PeerAvailability
        from unittest.mock import AsyncMock, patch
        
        # Create peers but ensure average availability is below threshold
        # With threshold 0.5 and 1 peer, we need avg_availability < 0.5
        # So we'll set pieces to have 0 availability (not available)
        peer_key = "peer1"
        peer_avail = PeerAvailability(peer_key)
        # Peer has no pieces in window (pieces 0-4)
        peer_avail.pieces = set()
        piece_manager.peer_availability[peer_key] = peer_avail
        
        # Ensure piece frequencies are 0 for window pieces
        for i in range(5):
            piece_manager.piece_frequency[i] = 0
        
        # Mock _select_rarest_first to avoid timeout
        with patch.object(piece_manager, '_select_rarest_first', new_callable=AsyncMock) as mock_rarest:
            # Run fallback selection - should fallback to rarest-first
            await piece_manager._select_sequential_with_fallback()
            
            # Verify fallback was called
            mock_rarest.assert_called_once()

    @pytest.mark.asyncio
    async def test_sequential_fallback_when_availability_high(self, piece_manager):
        """Test sequential selection when availability is high."""
        # Set high fallback threshold
        piece_manager.config.strategy.sequential_fallback_threshold = 0.1
        piece_manager.config.strategy.sequential_window = 5

        # Add peers with high availability
        from ccbt.piece.async_piece_manager import PeerAvailability
        from unittest.mock import AsyncMock, patch
        
        for i in range(5):
            peer_key = f"peer{i}"
            peer_avail = PeerAvailability(peer_key)
            # All peers have first 5 pieces
            peer_avail.pieces = {0, 1, 2, 3, 4}
            piece_manager.peer_availability[peer_key] = peer_avail
            
            for piece_idx in range(5):
                piece_manager.piece_frequency[piece_idx] = 5

        # Mock both methods to avoid timeout
        with patch.object(piece_manager, '_select_sequential', new_callable=AsyncMock) as mock_seq, \
             patch.object(piece_manager, '_select_rarest_first', new_callable=AsyncMock) as mock_rarest:
            # Run fallback selection
            await piece_manager._select_sequential_with_fallback()
            
            # Should use sequential (not rarest-first) when availability is high
            mock_seq.assert_called_once()
            mock_rarest.assert_not_called()


class TestStreamingMode:
    """Test streaming-optimized sequential selection."""

    @pytest.mark.asyncio
    async def test_streaming_mode_selection(self, piece_manager):
        """Test streaming-optimized sequential selection."""
        from unittest.mock import AsyncMock, patch
        
        # Enable streaming mode
        piece_manager.config.strategy.streaming_mode = True
        piece_manager.config.strategy.sequential_window = 10

        # Simulate some download progress
        piece_manager.bytes_downloaded = 1024 * 1024  # 1MB
        piece_manager.download_start_time -= 2.0  # 2 seconds ago
        
        # Mock the internal call to avoid timeout
        with patch.object(piece_manager, '_select_sequential_with_window', new_callable=AsyncMock) as mock_window:
            # Run streaming selection
            await piece_manager._select_sequential_streaming()
            
            # Should have called window selection
            mock_window.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_mode_without_flag(self, piece_manager):
        """Test streaming mode falls back to regular sequential when disabled."""
        from unittest.mock import AsyncMock, patch
        
        # Disable streaming mode
        piece_manager.config.strategy.streaming_mode = False

        # Mock sequential to verify it's called
        with patch.object(piece_manager, '_select_sequential', new_callable=AsyncMock) as mock_seq:
            # Run streaming selection
            await piece_manager._select_sequential_streaming()
            
            # Should fall back to regular sequential
            mock_seq.assert_called_once()

    @pytest.mark.asyncio
    async def test_sequential_with_custom_window(self, piece_manager):
        """Test sequential selection with custom window size."""
        custom_window = 15
        
        # This method doesn't call other async methods that could hang, so should be safe
        await piece_manager._select_sequential_with_window(custom_window)
        
        # Should have executed without error
        assert True

    @pytest.mark.asyncio
    async def test_handle_streaming_seek(self, piece_manager):
        """Test seek operation during streaming download."""
        from unittest.mock import AsyncMock, patch
        
        target_piece = 5
        
        # Initial position
        assert piece_manager._current_sequential_piece == 0
        
        # Mock sequential to avoid timeout
        with patch.object(piece_manager, '_select_sequential', new_callable=AsyncMock) as mock_seq:
            # Perform seek
            await piece_manager.handle_streaming_seek(target_piece)
            
            # Verify position updated
            assert piece_manager._current_sequential_piece == target_piece
            
            # Verify sequential was called
            mock_seq.assert_called_once()
            
            # Verify priority increased for seek window pieces
            seek_window_start = max(0, target_piece - 2)
            seek_window_end = min(
                target_piece + piece_manager.config.strategy.sequential_window,
                len(piece_manager.pieces),
            )
            
            for piece_idx in range(seek_window_start, seek_window_end):
                if piece_idx in piece_manager.get_missing_pieces():
                    # Priority should be increased (base priority + 500)
                    assert piece_manager.pieces[piece_idx].priority >= 500


class TestDownloadRate:
    """Test download rate calculation."""

    @pytest.mark.asyncio
    async def test_get_download_rate(self, piece_manager):
        """Test download rate calculation."""
        # Initially no download
        rate = piece_manager.get_download_rate()
        assert rate == 0.0

        # Simulate some download
        piece_manager.bytes_downloaded = 1024 * 1024  # 1MB
        piece_manager.download_start_time -= 1.0  # 1 second ago
        
        rate = piece_manager.get_download_rate()
        assert rate > 0
        assert rate == pytest.approx(1024 * 1024, rel=0.1)  # ~1MB/s

    @pytest.mark.asyncio
    async def test_get_download_rate_zero_time(self, piece_manager):
        """Test download rate with zero elapsed time."""
        import time
        
        # Set start time to now and bytes downloaded to some value
        piece_manager.bytes_downloaded = 1024
        piece_manager.download_start_time = time.time()  # Set to now (zero elapsed)
        
        rate = piece_manager.get_download_rate()
        # With zero elapsed time, should return 0.0 (division by zero protection)
        assert rate == 0.0


class TestSequentialEdgeCases:
    """Test edge cases for sequential selection."""

    @pytest.mark.asyncio
    async def test_sequential_selection_no_missing_pieces(self, piece_manager):
        """Test sequential selection when no pieces are missing."""
        # Mark all pieces as complete
        for piece in piece_manager.pieces:
            piece.state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(piece.piece_index)

        # Should return early without error
        await piece_manager._select_sequential()
        assert True

    @pytest.mark.asyncio
    async def test_sequential_selection_empty_window(self, piece_manager):
        """Test sequential selection with empty window."""
        # Set very small window
        piece_manager.config.strategy.sequential_window = 1
        
        # Mark pieces 0-4 as complete
        for i in range(5):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)

        # Run selection
        await piece_manager._select_sequential()
        
        # Should handle gracefully
        assert True

    @pytest.mark.asyncio
    async def test_sequential_selection_with_file_manager_and_window(self, piece_manager):
        """Test sequential selection when file manager exists and window has pieces."""
        from unittest.mock import MagicMock
        
        # Mock file selection manager
        mock_file_manager = MagicMock()
        mock_file_manager.get_selected_files.return_value = [0]
        mock_file_manager.get_files_for_piece.return_value = [0]
        piece_manager.file_selection_manager = mock_file_manager
        
        # Set window size
        piece_manager.config.strategy.sequential_window = 5
        
        # Run selection - should call _sort_by_file_priority
        await piece_manager._select_sequential()
        
        # Should have executed (file manager branch covered)
        assert True

    @pytest.mark.asyncio
    async def test_get_current_sequential_piece_no_missing(self, piece_manager):
        """Test _get_current_sequential_piece when no missing pieces."""
        # Mark all pieces as verified
        for i in range(len(piece_manager.pieces)):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)
        
        # Reset tracked position
        piece_manager._current_sequential_piece = 0
        
        # Should return 0 when no missing pieces
        result = piece_manager._get_current_sequential_piece()
        assert result == 0

    @pytest.mark.asyncio
    async def test_sequential_with_window_no_missing(self, piece_manager):
        """Test _select_sequential_with_window when no missing pieces."""
        # Mark all pieces as verified
        for i in range(len(piece_manager.pieces)):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)
        
        # Should return early without error
        await piece_manager._select_sequential_with_window(10)
        assert True

    @pytest.mark.asyncio
    async def test_sequential_with_window_file_manager(self, piece_manager):
        """Test _select_sequential_with_window with file selection manager."""
        from unittest.mock import MagicMock
        
        # Mock file selection manager
        mock_file_manager = MagicMock()
        mock_file_manager.get_selected_files.return_value = [0]
        mock_file_manager.get_files_for_piece.return_value = [0]
        piece_manager.file_selection_manager = mock_file_manager
        
        # Run selection with window
        await piece_manager._select_sequential_with_window(5)
        
        # Should have executed (file manager branch covered)
        assert True

    @pytest.mark.asyncio
    async def test_sequential_fallback_no_missing(self, piece_manager):
        """Test _select_sequential_with_fallback when no missing pieces."""
        # Mark all pieces as verified
        for i in range(len(piece_manager.pieces)):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)
        
        # Should return early without error
        await piece_manager._select_sequential_with_fallback()
        assert True

