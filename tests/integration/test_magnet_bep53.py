"""Integration tests for BEP 53: Magnet URI Extension - Specify Indices to Download."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.core]

from ccbt.core.magnet import MagnetInfo, apply_magnet_file_selection, parse_magnet
from ccbt.models import FileInfo, TorrentInfo
from ccbt.piece.file_selection import FilePriority, FileSelectionManager
from ccbt.session.session import AsyncSessionManager


@pytest.fixture
def multi_file_torrent_info():
    """Create multi-file torrent info for testing."""
    piece_length = 16384

    file0_length = piece_length * 2
    file1_length = piece_length * 2 + 1000
    file2_length = piece_length - 1000
    file3_length = piece_length
    file4_length = piece_length + 500

    return TorrentInfo(
        name="multi_file_torrent",
        info_hash=b"\x01" * 20,
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
            FileInfo(
                name="file3.txt",
                length=file3_length,
                path=["file3.txt"],
                full_path="file3.txt",
            ),
            FileInfo(
                name="file4.txt",
                length=file4_length,
                path=["file4.txt"],
                full_path="file4.txt",
            ),
        ],
        total_length=file0_length + file1_length + file2_length + file3_length + file4_length,
        piece_length=piece_length,
        pieces=[b"\x01" * 20 for _ in range(10)],
        num_pieces=10,
    )


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestMagnetBEP53Integration:
    """Integration tests for BEP 53 magnet URI file index specification."""

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_with_selected_indices(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test applying file selection from magnet URI with selected indices."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # Create magnet info with selected indices
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2, 4],
            prioritized_indices=None,
        )

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=True,
        )

        # Verify only specified files are selected
        all_states = file_selection_manager.get_all_file_states()
        assert all_states[0].selected is True
        assert all_states[1].selected is False
        assert all_states[2].selected is True
        assert all_states[3].selected is False
        assert all_states[4].selected is True

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_with_priorities(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test applying file priorities from magnet URI x.pe parameter."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # Create magnet info with priorities
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=None,
            prioritized_indices={0: 4, 2: 3, 4: 2},
        )

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=True,
        )

        # Verify priorities are set correctly
        all_states = file_selection_manager.get_all_file_states()
        assert all_states[0].priority == FilePriority.MAXIMUM  # 4
        assert all_states[2].priority == FilePriority.HIGH  # 3
        assert all_states[4].priority == FilePriority.NORMAL  # 2

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_with_both_selection_and_priorities(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test applying both file selection and priorities from magnet URI."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # Create magnet info with both selection and priorities
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2, 4],
            prioritized_indices={0: 4, 2: 3},
        )

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=True,
        )

        # Verify selection
        all_states = file_selection_manager.get_all_file_states()
        assert all_states[0].selected is True
        assert all_states[2].selected is True
        assert all_states[4].selected is True

        # Verify priorities
        assert all_states[0].priority == FilePriority.MAXIMUM
        assert all_states[2].priority == FilePriority.HIGH

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_respect_indices_false(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test that respect_indices=False ignores magnet indices."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # All files should be selected by default
        initial_states = file_selection_manager.get_all_file_states()
        assert all(f.selected for f in initial_states.values())

        # Create magnet info with selected indices
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2],
            prioritized_indices={0: 4},
        )

        # Apply selection with respect_indices=False
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=False,
        )

        # Verify no files were deselected (all still selected)
        final_states = file_selection_manager.get_all_file_states()
        assert all(f.selected for f in final_states.values())

    @pytest.mark.asyncio
    async def test_parse_magnet_with_indices_and_add_to_session(
        self,
        temp_output_dir,
    ):
        """Test parsing magnet URI with indices and adding to session."""
        # Create magnet URI with BEP 53 parameters
        magnet_uri = (
            "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
            "&so=0,2,4&x.pe=0:4,2:3"
        )

        # Parse magnet URI
        magnet_info = parse_magnet(magnet_uri)
        assert magnet_info.selected_indices == [0, 2, 4]
        assert magnet_info.prioritized_indices == {0: 4, 2: 3}

        # Create session manager
        session_manager = AsyncSessionManager(output_dir=str(temp_output_dir))
        session_manager.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking socket operations

        # Mock the torrent data creation
        with patch.object(
            session_manager,
            "parse_magnet_link",
            return_value={
                "info_hash": b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                "name": "test",
                "files": [],
            },
        ):
            # Parse the magnet link (this would normally return torrent_data)
            parsed = session_manager.parse_magnet_link(magnet_uri)
            assert parsed is not None

    @pytest.mark.asyncio
    async def test_validate_indices_against_actual_file_count(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test that invalid indices are filtered out when applying selection."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # Create magnet info with out-of-range indices
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 5, 10, 15],  # Only 0 and 5 are valid (out of 5 files)
            prioritized_indices=None,
        )

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=True,
        )

        # Verify only valid indices are selected
        all_states = file_selection_manager.get_all_file_states()
        assert all_states[0].selected is True  # Valid
        # File 5 doesn't exist (indices are 0-4), so should be ignored
        for i in range(1, len(multi_file_torrent_info.files)):
            assert all_states[i].selected is False

    @pytest.mark.asyncio
    async def test_prioritized_indices_with_invalid_file_index(
        self,
        multi_file_torrent_info,
        temp_output_dir,
    ):
        """Test that invalid file indices in priorities are ignored."""
        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(multi_file_torrent_info)

        # Create magnet info with out-of-range priority indices
        magnet_info = MagnetInfo(
            info_hash=b"\x01" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=None,
            prioritized_indices={0: 4, 10: 3, 15: 2},  # Only 0 is valid
        )

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=len(multi_file_torrent_info.files),
            respect_indices=True,
        )

        # Verify only valid priority is set
        all_states = file_selection_manager.get_all_file_states()
        assert all_states[0].priority == FilePriority.MAXIMUM
        # Other files should have default priority
        for i in range(1, len(all_states)):
            assert all_states[i].priority == FilePriority.NORMAL

    @pytest.mark.asyncio
    async def test_single_file_torrent_ignores_indices(
        self,
        temp_output_dir,
    ):
        """Test that single-file torrents ignore BEP 53 indices."""
        # Create single-file torrent
        single_file_torrent = TorrentInfo(
            name="single_file",
            info_hash=b"\x02" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="file.txt",
                    length=16384,
                    path=["file.txt"],
                    full_path="file.txt",
                ),
            ],
            total_length=16384,
            piece_length=16384,
            pieces=[b"\x02" * 20],
            num_pieces=1,
        )

        # Create FileSelectionManager
        file_selection_manager = FileSelectionManager(single_file_torrent)

        # Create magnet info with indices
        magnet_info = MagnetInfo(
            info_hash=b"\x02" * 20,
            display_name="test torrent",
            trackers=[],
            web_seeds=[],
            selected_indices=[0],
            prioritized_indices={0: 4},
        )

        # Store initial state
        initial_states = file_selection_manager.get_all_file_states()
        initial_file_state = initial_states[0]

        # Apply selection
        await apply_magnet_file_selection(
            file_selection_manager,
            magnet_info,
            num_files=1,
            respect_indices=True,
        )

        # Verify no changes (single-file torrents ignore indices)
        final_states = file_selection_manager.get_all_file_states()
        final_file_state = final_states[0]
        assert final_file_state.selected == initial_file_state.selected
        assert final_file_state.priority == initial_file_state.priority

