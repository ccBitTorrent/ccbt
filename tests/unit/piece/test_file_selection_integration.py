"""Integration tests for file selection with AsyncPieceManager.

Tests that AsyncPieceManager correctly respects file selection when selecting pieces.
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.models import FileInfo, TorrentInfo
from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceState
from ccbt.piece.file_selection import FilePriority, FileSelectionManager


@pytest.fixture
def multi_file_torrent_data():
    """Create multi-file torrent data for testing."""
    piece_length = 16384
    
    file0_length = piece_length * 2
    file1_length = piece_length * 2 + 1000
    file2_length = piece_length - 1000
    total_length = file0_length + file1_length + file2_length
    
    torrent_info = TorrentInfo(
        name="multi_file_torrent",
        info_hash=b"\x00" * 20,
        announce="http://tracker.example.com/announce",
        files=[
            FileInfo(
                name="file0.txt",
                length=file0_length,
                path=["file0.txt"],
                full_path="file0.txt",
            ),
            FileInfo(
                name="file1.txt",
                length=file1_length,
                path=["file1.txt"],
                full_path="file1.txt",
            ),
            FileInfo(
                name="file2.txt",
                length=file2_length,
                path=["file2.txt"],
                full_path="file2.txt",
            ),
        ],
        total_length=total_length,
        piece_length=piece_length,
        pieces=[b"\x01" * 20 for _ in range(5)],
        num_pieces=5,
    )
    
    # Convert to dict format for AsyncPieceManager
    return {
        "info_hash": torrent_info.info_hash,
        "name": torrent_info.name,
        "pieces_info": {
            "num_pieces": torrent_info.num_pieces,
            "piece_length": torrent_info.piece_length,
            "piece_hashes": torrent_info.pieces,
        },
        "file_info": {
            "type": "multi",
            "name": torrent_info.name,
            "total_length": torrent_info.total_length,
            "files": [
                {
                    "name": f.name,
                    "length": f.length,
                    "path": f.path,
                }
                for f in torrent_info.files
            ],
        },
    }, torrent_info


@pytest_asyncio.fixture
async def piece_manager_with_selection(multi_file_torrent_data):
    """Create piece manager with file selection manager."""
    torrent_dict, torrent_info = multi_file_torrent_data
    
    file_selection_manager = FileSelectionManager(torrent_info)
    piece_manager = AsyncPieceManager(torrent_dict, file_selection_manager=file_selection_manager)
    
    await piece_manager.start()
    yield piece_manager, file_selection_manager
    await piece_manager.stop()


@pytest.mark.asyncio
class TestAsyncPieceManagerFileSelection:
    """Test AsyncPieceManager integration with file selection."""

    async def test_get_missing_pieces_respects_file_selection(
        self,
        piece_manager_with_selection,
    ):
        """Test that get_missing_pieces filters out pieces for unselected files."""
        piece_manager, file_selection_manager = piece_manager_with_selection
        
        # All files selected initially
        missing = piece_manager.get_missing_pieces()
        assert len(missing) == 5  # All pieces missing
        
        # Deselect file 0 (pieces 0, 1)
        await file_selection_manager.deselect_file(0)
        
        # Now pieces 0 and 1 should not be in missing list
        missing = piece_manager.get_missing_pieces()
        assert 0 not in missing
        assert 1 not in missing
        # But pieces 2, 3, 4 should still be missing
        assert 2 in missing or 3 in missing or 4 in missing

    async def test_get_missing_pieces_all_deselected(
        self,
        piece_manager_with_selection,
    ):
        """Test get_missing_pieces when all files are deselected."""
        piece_manager, file_selection_manager = piece_manager_with_selection
        
        # Deselect all files
        await file_selection_manager.deselect_all()
        
        missing = piece_manager.get_missing_pieces()
        assert len(missing) == 0  # No pieces should be needed

    async def test_piece_priority_inherited_from_files(self, multi_file_torrent_data):
        """Test that piece priorities are set based on file priorities."""
        torrent_dict, torrent_info = multi_file_torrent_data
        
        # Create file selection manager and set priorities BEFORE creating piece manager
        file_selection_manager = FileSelectionManager(torrent_info)
        await file_selection_manager.set_file_priority(0, FilePriority.HIGH)
        await file_selection_manager.set_file_priority(1, FilePriority.MAXIMUM)
        
        # Now create piece manager with file selection manager that has priorities set
        piece_manager = AsyncPieceManager(torrent_dict, file_selection_manager=file_selection_manager)
        await piece_manager.start()
        
        try:
            # Check that piece priorities are set correctly
            # Piece 0 belongs to file 0, should have HIGH priority
            piece_0 = piece_manager.pieces[0]
            # Priority calculation: max(file_priority * 100, existing_priority)
            # File priority HIGH (3) * 100 = 300, should be >= 300
            assert piece_0.priority >= 300
            
            # Piece 4 belongs to files 1 and 2, should have at least MAXIMUM priority
            piece_4 = piece_manager.pieces[4]
            # File priority MAXIMUM (4) * 100 = 400
            assert piece_4.priority >= 400
        finally:
            await piece_manager.stop()

    async def test_handle_piece_block_updates_file_progress(
        self,
        piece_manager_with_selection,
    ):
        """Test that completing a piece updates file progress."""
        piece_manager, file_selection_manager = piece_manager_with_selection
        
        # Get initial state
        file_state = file_selection_manager.get_file_state(0)
        assert file_state
        initial_bytes = file_state.bytes_downloaded
        
        # Complete piece 0 (which belongs to file 0)
        piece_length = piece_manager.piece_length
        block_size = 16384
        
        # Add all blocks for piece 0
        for offset in range(0, piece_length, block_size):
            block_data = b"x" * min(block_size, piece_length - offset)
            await piece_manager.handle_piece_block(0, offset, block_data)
        
        # File 0 progress should have increased
        updated_state = file_selection_manager.get_file_state(0)
        assert updated_state
        assert updated_state.bytes_downloaded > initial_bytes

    async def test_sequential_selection_respects_file_order(
        self,
        piece_manager_with_selection,
    ):
        """Test that sequential selection respects file selection order."""
        piece_manager, file_selection_manager = piece_manager_with_selection
        
        # Deselect all, then select only file 0
        await file_selection_manager.deselect_all()
        await file_selection_manager.select_file(0)
        
        # Set to sequential mode
        piece_manager.piece_selection_strategy = "sequential"
        
        # Missing pieces should only include pieces for file 0 (pieces 0, 1)
        missing = piece_manager.get_missing_pieces()
        assert all(piece_idx in [0, 1] for piece_idx in missing)
        assert len(missing) == 2

    async def test_rarest_first_with_file_priorities(
        self,
        piece_manager_with_selection,
    ):
        """Test rarest-first selection with file priorities."""
        piece_manager, file_selection_manager = piece_manager_with_selection
        
        # Set priorities
        await file_selection_manager.set_file_priority(0, FilePriority.HIGH)
        await file_selection_manager.set_file_priority(1, FilePriority.NORMAL)
        
        # Set to rarest-first mode
        piece_manager.piece_selection_strategy = "rarest_first"
        
        # Create mock peer bitfields
        # This is a simplified test - in real scenario we'd have actual peers
        missing = piece_manager.get_missing_pieces()
        assert len(missing) > 0
        
        # Pieces for file 0 should have higher priority
        piece_0 = piece_manager.pieces[0]
        piece_2 = piece_manager.pieces[2]  # Belongs to file 1
        # HIGH (3) * 100 = 300, NORMAL (2) * 100 = 200
        assert piece_0.priority >= piece_2.priority


@pytest.mark.asyncio
class TestFileSelectionWithoutManager:
    """Test that piece manager works without file selection manager."""

    async def test_piece_manager_without_file_selection(self, multi_file_torrent_data):
        """Test AsyncPieceManager without file selection manager."""
        torrent_dict, _ = multi_file_torrent_data
        
        piece_manager = AsyncPieceManager(torrent_dict, file_selection_manager=None)
        await piece_manager.start()
        
        try:
            # Should work normally without file selection
            missing = piece_manager.get_missing_pieces()
            assert len(missing) == 5  # All pieces missing
            
            # Pieces should have default priorities
            for piece in piece_manager.pieces:
                assert piece.priority >= 0
        finally:
            await piece_manager.stop()

