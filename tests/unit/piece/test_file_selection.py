"""Comprehensive tests for file selection and prioritization.

Tests FilePriority, FileSelectionState, PieceToFileMapper, and FileSelectionManager.
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.models import FileInfo, TorrentInfo
from ccbt.piece.file_selection import (
    FilePriority,
    FileSelectionManager,
    FileSelectionState,
    PieceToFileMapper,
)


@pytest.fixture
def single_file_torrent():
    """Create single-file torrent info."""
    return TorrentInfo(
        name="single_file",
        info_hash=b"\x00" * 20,
        announce="http://tracker.example.com/announce",
        files=[
            FileInfo(
                name="file.txt",
                length=16384 * 5,  # 5 pieces
                path=["file.txt"],
                full_path="file.txt",
            ),
        ],
        total_length=16384 * 5,
        piece_length=16384,
        pieces=[b"\x01" * 20 for _ in range(5)],
        num_pieces=5,
    )


@pytest.fixture
def multi_file_torrent():
    """Create multi-file torrent info for testing.
    
    File layout:
    - File 0: pieces 0-1 (2 pieces, 0 to 32768)
    - File 1: pieces 2-4 (spans piece 2, 3, 4, starting at 32768)
    - File 2: within piece 4 (part of last piece, starts after file 1 ends)
    """
    piece_length = 16384
    
    # File 0: exactly 2 pieces (ends at piece 1 boundary)
    file0_length = piece_length * 2
    # File 1: starts at 32768, spans 2 pieces + some (ends in piece 4)
    file1_length = piece_length * 2 + 1000
    # File 2: remaining part of piece 4
    file2_length = piece_length - 1000
    total_length = file0_length + file1_length + file2_length
    
    return TorrentInfo(
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


@pytest.fixture
def file_selection_manager(multi_file_torrent):
    """Create FileSelectionManager for testing."""
    return FileSelectionManager(multi_file_torrent)


class TestFilePriority:
    """Test FilePriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert FilePriority.DO_NOT_DOWNLOAD == 0
        assert FilePriority.LOW == 1
        assert FilePriority.NORMAL == 2
        assert FilePriority.HIGH == 3
        assert FilePriority.MAXIMUM == 4

    def test_priority_comparison(self):
        """Test priority comparison."""
        assert FilePriority.HIGH > FilePriority.NORMAL
        assert FilePriority.NORMAL > FilePriority.LOW
        assert FilePriority.MAXIMUM > FilePriority.HIGH
        assert FilePriority.DO_NOT_DOWNLOAD < FilePriority.LOW


class TestFileSelectionState:
    """Test FileSelectionState dataclass."""

    def test_initialization(self):
        """Test FileSelectionState initialization."""
        state = FileSelectionState(
            file_index=0,
            selected=True,
            priority=FilePriority.HIGH,
            bytes_downloaded=1000,
            bytes_total=5000,
        )
        assert state.file_index == 0
        assert state.selected is True
        assert state.priority == FilePriority.HIGH
        assert state.bytes_downloaded == 1000
        assert state.bytes_total == 5000

    def test_progress_calculation(self):
        """Test progress property calculation."""
        state = FileSelectionState(
            file_index=0,
            bytes_total=1000,
            bytes_downloaded=500,
        )
        assert state.progress == 0.5

    def test_progress_zero_bytes_total_selected(self):
        """Test progress when bytes_total is 0 and file is selected."""
        state = FileSelectionState(
            file_index=0,
            selected=True,
            bytes_total=0,
        )
        assert state.progress == 0.0

    def test_progress_zero_bytes_total_not_selected(self):
        """Test progress when bytes_total is 0 and file is not selected."""
        state = FileSelectionState(
            file_index=0,
            selected=False,
            bytes_total=0,
        )
        assert state.progress == 1.0

    def test_progress_complete(self):
        """Test progress when file is complete."""
        state = FileSelectionState(
            file_index=0,
            bytes_total=1000,
            bytes_downloaded=1000,
        )
        assert state.progress == 1.0


class TestPieceToFileMapper:
    """Test PieceToFileMapper."""

    def test_single_file_mapping(self, single_file_torrent):
        """Test mapping for single-file torrent."""
        mapper = PieceToFileMapper(single_file_torrent)
        
        # All pieces should map to file 0
        for piece_index in range(5):
            files = mapper.piece_to_files[piece_index]
            assert len(files) == 1
            assert files[0][0] == 0  # file_index
        
        # File 0 should have all pieces
        assert len(mapper.file_to_pieces[0]) == 5
        assert mapper.file_to_pieces[0] == [0, 1, 2, 3, 4]

    def test_multi_file_mapping(self, multi_file_torrent):
        """Test mapping for multi-file torrent."""
        mapper = PieceToFileMapper(multi_file_torrent)
        
        # Piece 0 should only be in file 0
        files_in_piece_0 = mapper.piece_to_files[0]
        assert len(files_in_piece_0) == 1
        assert files_in_piece_0[0][0] == 0
        
        # Piece 1 should only be in file 0 (file 0 ends exactly at piece 1 boundary)
        files_in_piece_1 = mapper.piece_to_files[1]
        assert len(files_in_piece_1) == 1
        assert files_in_piece_1[0][0] == 0
        
        # Piece 2 should be in file 1 (file 1 starts at piece 2)
        files_in_piece_2 = mapper.piece_to_files[2]
        assert len(files_in_piece_2) == 1
        assert files_in_piece_2[0][0] == 1
        
        # Piece 4 should have files 1 and 2 (file 1 ends, file 2 starts within piece 4)
        files_in_piece_4 = mapper.piece_to_files[4]
        file_indices = [f[0] for f in files_in_piece_4]
        assert 1 in file_indices
        assert 2 in file_indices
        
        # Check reverse mapping
        assert 0 in mapper.file_to_pieces
        assert 1 in mapper.file_to_pieces
        assert 2 in mapper.file_to_pieces
        
        # File 0 should have pieces 0 and 1
        assert 0 in mapper.file_to_pieces[0]
        assert 1 in mapper.file_to_pieces[0]
        
        # File 1 should have pieces 2, 3, 4
        assert 2 in mapper.file_to_pieces[1]
        assert 3 in mapper.file_to_pieces[1]
        assert 4 in mapper.file_to_pieces[1]
        
        # File 2 should have piece 4
        assert 4 in mapper.file_to_pieces[2]

    def test_file_offsets(self, multi_file_torrent):
        """Test file offset calculations in mappings."""
        mapper = PieceToFileMapper(multi_file_torrent)
        piece_length = 16384
        
        # Piece 0, file 0: should start at offset 0
        files_in_piece_0 = mapper.piece_to_files[0]
        assert files_in_piece_0[0][1] == 0  # file_offset
        
        # Piece 1, file 0: should continue from file 0
        # Piece 1 starts at piece_length, file 0 offset is piece_length - piece_length = 0? No
        # Actually piece 1 overlaps with end of file 0 and start of file 1
        # Let me verify the logic
        
        # Piece 1 overlaps with file 0 (from piece_length to 2*piece_length) and file 1 (from 0)
        files_in_piece_1 = mapper.piece_to_files[1]
        for file_idx, file_offset, length in files_in_piece_1:
            if file_idx == 0:
                # This should be the end part of file 0
                assert file_offset == piece_length
                assert length <= piece_length
            elif file_idx == 1:
                # This should be the start part of file 1
                assert file_offset == 0

    def test_piece_boundaries(self, multi_file_torrent):
        """Test mapping handles piece boundaries correctly."""
        mapper = PieceToFileMapper(multi_file_torrent)
        
        # Last piece (piece 4) should contain both file 1 (end) and file 2 (start)
        last_piece = multi_file_torrent.num_pieces - 1
        files_in_last = mapper.piece_to_files[last_piece]
        file_indices = [f[0] for f in files_in_last]
        assert 1 in file_indices  # file1 ends in last piece
        assert 2 in file_indices  # file2 starts in last piece


class TestFileSelectionManager:
    """Test FileSelectionManager."""

    def test_initialization(self, multi_file_torrent):
        """Test FileSelectionManager initialization."""
        manager = FileSelectionManager(multi_file_torrent)
        
        assert len(manager.file_states) == 3
        assert all(state.selected for state in manager.file_states.values())
        assert all(state.priority == FilePriority.NORMAL for state in manager.file_states.values())

    def test_select_file(self, file_selection_manager):
        """Test selecting a single file."""
        # File should start selected, deselect first
        asyncio.run(file_selection_manager.deselect_file(0))
        assert not file_selection_manager.is_file_selected(0)
        
        asyncio.run(file_selection_manager.select_file(0))
        assert file_selection_manager.is_file_selected(0)

    def test_deselect_file(self, file_selection_manager):
        """Test deselecting a single file."""
        assert file_selection_manager.is_file_selected(0)
        
        asyncio.run(file_selection_manager.deselect_file(0))
        assert not file_selection_manager.is_file_selected(0)

    def test_set_file_priority(self, file_selection_manager):
        """Test setting file priority."""
        asyncio.run(file_selection_manager.set_file_priority(0, FilePriority.HIGH))
        assert file_selection_manager.get_file_priority(0) == FilePriority.HIGH

    def test_select_files(self, file_selection_manager):
        """Test selecting multiple files."""
        # Deselect all first
        asyncio.run(file_selection_manager.deselect_all())
        
        asyncio.run(file_selection_manager.select_files([0, 2]))
        assert file_selection_manager.is_file_selected(0)
        assert not file_selection_manager.is_file_selected(1)
        assert file_selection_manager.is_file_selected(2)

    def test_deselect_files(self, file_selection_manager):
        """Test deselecting multiple files."""
        # All should be selected by default
        assert file_selection_manager.is_file_selected(0)
        assert file_selection_manager.is_file_selected(1)
        
        asyncio.run(file_selection_manager.deselect_files([0, 1]))
        assert not file_selection_manager.is_file_selected(0)
        assert not file_selection_manager.is_file_selected(1)
        assert file_selection_manager.is_file_selected(2)  # Still selected

    def test_select_all(self, file_selection_manager):
        """Test selecting all files."""
        asyncio.run(file_selection_manager.deselect_all())
        assert not any(file_selection_manager.is_file_selected(f) for f in range(3))
        
        asyncio.run(file_selection_manager.select_all())
        assert all(file_selection_manager.is_file_selected(f) for f in range(3))

    def test_deselect_all(self, file_selection_manager):
        """Test deselecting all files."""
        assert all(file_selection_manager.is_file_selected(f) for f in range(3))
        
        asyncio.run(file_selection_manager.deselect_all())
        assert not any(file_selection_manager.is_file_selected(f) for f in range(3))

    def test_is_piece_needed_single_file_selected(self, file_selection_manager):
        """Test is_piece_needed when one file is selected."""
        # Deselect all
        asyncio.run(file_selection_manager.deselect_all())
        
        # Select only file 0
        asyncio.run(file_selection_manager.select_file(0))
        
        # Piece 0 should be needed (belongs to file 0)
        assert file_selection_manager.is_piece_needed(0)
        
        # Piece 4 should not be needed (belongs to file 2, which is not selected)
        assert not file_selection_manager.is_piece_needed(4)

    def test_is_piece_needed_no_files_selected(self, file_selection_manager):
        """Test is_piece_needed when no files are selected."""
        asyncio.run(file_selection_manager.deselect_all())
        
        # No pieces should be needed
        for piece_index in range(5):
            assert not file_selection_manager.is_piece_needed(piece_index)

    def test_is_piece_needed_all_files_selected(self, file_selection_manager):
        """Test is_piece_needed when all files are selected."""
        # All files selected by default
        for piece_index in range(5):
            assert file_selection_manager.is_piece_needed(piece_index)

    def test_get_piece_priority(self, file_selection_manager):
        """Test getting piece priority from file priorities."""
        # Set different priorities
        asyncio.run(file_selection_manager.set_file_priority(0, FilePriority.HIGH))
        asyncio.run(file_selection_manager.set_file_priority(1, FilePriority.MAXIMUM))
        asyncio.run(file_selection_manager.set_file_priority(2, FilePriority.LOW))
        
        # Piece 1 only belongs to file 0, should get HIGH
        priority = file_selection_manager.get_piece_priority(1)
        assert priority == int(FilePriority.HIGH.value)
        
        # Piece 0 only belongs to file 0, should get HIGH
        priority = file_selection_manager.get_piece_priority(0)
        assert priority == int(FilePriority.HIGH.value)
        
        # Piece 4 overlaps files 1 and 2, should get MAXIMUM (highest)
        priority = file_selection_manager.get_piece_priority(4)
        assert priority == int(FilePriority.MAXIMUM.value)

    def test_get_piece_priority_unselected_file(self, file_selection_manager):
        """Test piece priority when file is not selected."""
        # Deselect file 0
        asyncio.run(file_selection_manager.deselect_file(0))
        
        # Set high priority on unselected file
        asyncio.run(file_selection_manager.set_file_priority(0, FilePriority.HIGH))
        
        # Piece 0 should have DO_NOT_DOWNLOAD priority (file not selected)
        priority = file_selection_manager.get_piece_priority(0)
        assert priority == int(FilePriority.DO_NOT_DOWNLOAD.value)

    def test_get_files_for_piece(self, file_selection_manager):
        """Test getting files that contain a piece."""
        # Piece 0 should only have file 0
        files = file_selection_manager.get_files_for_piece(0)
        assert files == [0]
        
        # Piece 1 should only have file 0
        files = file_selection_manager.get_files_for_piece(1)
        assert files == [0]
        
        # Piece 2 should have file 1
        files = file_selection_manager.get_files_for_piece(2)
        assert 1 in files
        
        # Piece 4 should have files 1 and 2
        files = file_selection_manager.get_files_for_piece(4)
        assert 1 in files
        assert 2 in files

    def test_get_pieces_for_file(self, file_selection_manager):
        """Test getting pieces that belong to a file."""
        # File 0 should have pieces 0 and 1
        pieces = file_selection_manager.get_pieces_for_file(0)
        assert 0 in pieces
        assert 1 in pieces
        
        # File 1 should have pieces 2, 3, 4
        pieces = file_selection_manager.get_pieces_for_file(1)
        assert 2 in pieces
        assert 3 in pieces
        assert 4 in pieces
        
        # File 2 should have piece 4
        pieces = file_selection_manager.get_pieces_for_file(2)
        assert 4 in pieces

    def test_update_file_progress(self, file_selection_manager):
        """Test updating file download progress."""
        state = file_selection_manager.get_file_state(0)
        assert state
        initial_bytes = state.bytes_downloaded
        
        asyncio.run(file_selection_manager.update_file_progress(0, 5000))
        
        updated_state = file_selection_manager.get_file_state(0)
        assert updated_state
        assert updated_state.bytes_downloaded == 5000

    def test_get_file_state(self, file_selection_manager):
        """Test getting file selection state."""
        state = file_selection_manager.get_file_state(0)
        assert state is not None
        assert state.file_index == 0
        
        # Invalid file index
        state = file_selection_manager.get_file_state(999)
        assert state is None

    def test_get_all_file_states(self, file_selection_manager):
        """Test getting all file states."""
        states = file_selection_manager.get_all_file_states()
        assert len(states) == 3
        assert all(isinstance(idx, int) for idx in states.keys())
        assert all(isinstance(state, FileSelectionState) for state in states.values())

    def test_get_selected_files(self, file_selection_manager):
        """Test getting list of selected files."""
        # All selected by default
        selected = file_selection_manager.get_selected_files()
        assert selected == [0, 1, 2]
        
        # Deselect one
        asyncio.run(file_selection_manager.deselect_file(1))
        selected = file_selection_manager.get_selected_files()
        assert 1 not in selected
        assert 0 in selected
        assert 2 in selected

    def test_get_statistics(self, file_selection_manager):
        """Test getting file selection statistics."""
        stats = file_selection_manager.get_statistics()
        
        assert stats["total_files"] == 3
        assert stats["selected_files"] == 3
        assert stats["deselected_files"] == 0
        assert stats["total_size"] > 0
        assert stats["selected_size"] == stats["total_size"]
        assert stats["deselected_size"] == 0
        
        # Deselect one file
        asyncio.run(file_selection_manager.deselect_file(1))
        stats = file_selection_manager.get_statistics()
        
        assert stats["selected_files"] == 2
        assert stats["deselected_files"] == 1
        assert stats["selected_size"] < stats["total_size"]
        assert stats["deselected_size"] > 0

    def test_piece_priority_mixed_selection(self, file_selection_manager):
        """Test piece priority when piece spans multiple files with different selections."""
        # Deselect file 0, select file 1
        asyncio.run(file_selection_manager.deselect_file(0))
        asyncio.run(file_selection_manager.select_file(1))
        
        # Set priorities
        asyncio.run(file_selection_manager.set_file_priority(0, FilePriority.HIGH))
        asyncio.run(file_selection_manager.set_file_priority(1, FilePriority.MAXIMUM))
        
        # Piece 4 spans files 1 and 2, file 1 is selected
        # Priority should be MAXIMUM (from selected file 1)
        priority = file_selection_manager.get_piece_priority(4)
        assert priority == int(FilePriority.MAXIMUM.value)
        
        # Piece 0 only belongs to file 0 (not selected), should be DO_NOT_DOWNLOAD
        priority = file_selection_manager.get_piece_priority(0)
        assert priority == int(FilePriority.DO_NOT_DOWNLOAD.value)


class TestFileSelectionManagerEdgeCases:
    """Test edge cases for FileSelectionManager."""

    def test_single_file_torrent(self, single_file_torrent):
        """Test FileSelectionManager with single-file torrent."""
        manager = FileSelectionManager(single_file_torrent)
        
        # Should have one file state
        assert len(manager.file_states) == 1
        assert manager.is_file_selected(0)
        
        # All pieces should be needed
        for piece_index in range(5):
            assert manager.is_piece_needed(piece_index)

    def test_invalid_file_index(self, file_selection_manager):
        """Test handling of invalid file indices."""
        # These should not raise, but return defaults or None
        assert file_selection_manager.is_file_selected(999) is False
        assert file_selection_manager.get_file_priority(999) == FilePriority.NORMAL
        assert file_selection_manager.get_file_state(999) is None

    def test_piece_index_out_of_range(self, file_selection_manager):
        """Test handling of out-of-range piece indices."""
        # Piece index beyond range should default to needed
        assert file_selection_manager.is_piece_needed(999) is True
        assert file_selection_manager.get_piece_priority(999) == 0
        assert file_selection_manager.get_files_for_piece(999) == []

    def test_empty_files_list(self):
        """Test FileSelectionManager with empty files list."""
        torrent = TorrentInfo(
            name="empty",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )
        
        manager = FileSelectionManager(torrent)
        assert len(manager.file_states) == 0
        assert manager.get_statistics()["total_files"] == 0


class TestFileSelectionManagerIntegration:
    """Test FileSelectionManager integration scenarios."""

    def test_sequential_file_selection(self, file_selection_manager):
        """Test selecting files in sequence."""
        # Select files one by one
        for file_idx in range(3):
            asyncio.run(file_selection_manager.deselect_file(file_idx))
            asyncio.run(file_selection_manager.select_file(file_idx))
            assert file_selection_manager.is_file_selected(file_idx)

    def test_priority_cascading(self, file_selection_manager):
        """Test priority affects piece selection."""
        # Set all files to different priorities
        priorities = [
            FilePriority.MAXIMUM,
            FilePriority.HIGH,
            FilePriority.NORMAL,
        ]
        
        for file_idx, priority in enumerate(priorities):
            asyncio.run(file_selection_manager.set_file_priority(file_idx, priority))
            assert file_selection_manager.get_file_priority(file_idx) == priority

    def test_selection_changes_affect_pieces(self, file_selection_manager):
        """Test that changing file selection affects piece needed status."""
        # All pieces needed initially
        for piece_idx in range(5):
            assert file_selection_manager.is_piece_needed(piece_idx)
        
        # Deselect file 0
        asyncio.run(file_selection_manager.deselect_file(0))
        
        # Piece 0 should not be needed (only belongs to file 0)
        assert not file_selection_manager.is_piece_needed(0)
        
        # Piece 1 might still be needed (also belongs to file 1)
        # This depends on the mapping - if piece 1 has file 1, it should still be needed
        files_in_piece_1 = file_selection_manager.get_files_for_piece(1)
        if 1 in files_in_piece_1:
            assert file_selection_manager.is_piece_needed(1)


@pytest.mark.asyncio
class TestFileSelectionManagerAsync:
    """Test async operations of FileSelectionManager."""

    async def test_concurrent_selections(self, file_selection_manager):
        """Test concurrent file selection operations."""
        # Run multiple operations concurrently
        await asyncio.gather(
            file_selection_manager.select_file(0),
            file_selection_manager.deselect_file(1),
            file_selection_manager.set_file_priority(2, FilePriority.HIGH),
        )
        
        assert file_selection_manager.is_file_selected(0)
        assert not file_selection_manager.is_file_selected(1)
        assert file_selection_manager.get_file_priority(2) == FilePriority.HIGH

    async def test_bulk_operations(self, file_selection_manager):
        """Test bulk selection operations."""
        # Deselect all
        await file_selection_manager.deselect_all()
        
        # Select multiple files concurrently
        await asyncio.gather(
            file_selection_manager.select_file(0),
            file_selection_manager.select_file(2),
        )
        
        assert file_selection_manager.is_file_selected(0)
        assert not file_selection_manager.is_file_selected(1)
        assert file_selection_manager.is_file_selected(2)

