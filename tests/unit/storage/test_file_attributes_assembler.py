"""Tests for file assembler BEP 47 attribute handling.

Tests cover:
- Padding file skipping in file segment building
- Attribute application on file completion
- Symlink creation
- Executable bit setting
- Hidden attribute handling
- Attribute restoration from checkpoints
"""

from __future__ import annotations

import os
import platform
import stat

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.storage]

from ccbt.models import FileCheckpoint, FileInfo, TorrentCheckpoint, TorrentInfo
from ccbt.storage.file_assembler import AsyncFileAssembler


def make_torrent_info_with_attributes() -> TorrentInfo:
    """Create TorrentInfo with BEP 47 attributes for testing."""
    return TorrentInfo(
        name="test_torrent_attrs",
        info_hash=b"\x00" * 20,
        announce="http://tracker.example.com/announce",
        files=[
            FileInfo(
                name="normal.txt",
                length=1000,
                path=["normal.txt"],
                full_path="normal.txt",
                attributes=None,
            ),
            FileInfo(
                name="executable.sh",
                length=2000,
                path=["executable.sh"],
                full_path="executable.sh",
                attributes="x",  # Executable
            ),
            FileInfo(
                name="padding",
                length=500,
                path=["padding"],
                full_path="padding",
                attributes="p",  # Padding file
            ),
        ],
        total_length=3500,
        piece_length=16384,
        pieces=[b"\x01" * 20],
        num_pieces=1,
    )


class TestPaddingFileSkipping:
    """Test that padding files are skipped in file segment building."""

    @pytest.mark.asyncio
    async def test_padding_files_excluded_from_segments(self, tmp_path):
        """Test that padding files don't create file segments."""
        torrent_info = make_torrent_info_with_attributes()

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Check that file segments exclude padding files
            segment_paths = {seg.file_path for seg in assembler.file_segments}

            # Normal and executable files should be in segments
            assert "normal.txt" in segment_paths or os.path.join(
                str(tmp_path), "normal.txt"
            ) in segment_paths
            assert "executable.sh" in segment_paths or os.path.join(
                str(tmp_path), "executable.sh"
            ) in segment_paths

            # Padding file should NOT be in segments
            # Check by exact filename match (basename)
            padding_segments = [
                seg
                for seg in assembler.file_segments
                if os.path.basename(seg.file_path) == "padding"
            ]
            assert len(padding_segments) == 0, (
                f"Padding file segments found: {[(s.file_path, os.path.basename(s.file_path)) for s in padding_segments]}"
            )

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_padding_files_accounted_in_total_length(self, tmp_path):
        """Test that padding files are still counted in total_length."""
        torrent_info = make_torrent_info_with_attributes()

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Total length should include padding files (for piece alignment)
            assert assembler.total_length == 3500  # Includes padding file

        finally:
            await assembler.__aexit__(None, None, None)


class TestAttributeApplication:
    """Test file attribute application."""

    @pytest.mark.asyncio
    async def test_apply_executable_bit(self, tmp_path):
        """Test applying executable bit to file."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        # Create file first
        test_file = tmp_path / "executable.sh"
        test_file.write_bytes(b"#!/bin/bash\necho test")

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="executable.sh",
                    length=20,
                    path=["executable.sh"],
                    full_path=str(test_file),
                    attributes="x",
                ),
            ],
            total_length=20,
            piece_length=16384,
            pieces=[b"\x01" * 20],
            num_pieces=1,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Clear execute bits first
            os.chmod(test_file, 0o644)

            # Apply attributes
            await assembler._apply_file_attributes(
                torrent_info.files[0], str(test_file)
            )

            # Check execute bit is set
            file_stat = os.stat(test_file)
            assert file_stat.st_mode & stat.S_IXUSR

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_apply_symlink(self, tmp_path):
        """Test creating symlink."""
        if platform.system() == "Windows":
            pytest.skip("Symlink creation requires admin privileges on Windows")
        target_file = tmp_path / "target.txt"
        target_file.write_text("target content")

        link_file = tmp_path / "link.lnk"
        link_file.write_text("placeholder")  # Must exist first

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="link.lnk",
                    length=0,
                    path=["link.lnk"],
                    full_path=str(link_file),
                    attributes="l",
                    symlink_path=str(target_file),
                ),
            ],
            total_length=0,
            piece_length=16384,
            pieces=[b"\x01" * 20],
            num_pieces=1,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Apply attributes (creates symlink)
            await assembler._apply_file_attributes(
                torrent_info.files[0], str(link_file)
            )

            # Verify symlink was created
            assert link_file.is_symlink()
            assert link_file.readlink() == target_file

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_apply_no_attributes(self, tmp_path):
        """Test that files without attributes are unchanged."""
        test_file = tmp_path / "normal.txt"
        test_file.write_text("normal content")

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="normal.txt",
                    length=14,
                    path=["normal.txt"],
                    full_path=str(test_file),
                    attributes=None,
                ),
            ],
            total_length=14,
            piece_length=16384,
            pieces=[b"\x01" * 20],
            num_pieces=1,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Apply attributes (should do nothing)
            await assembler._apply_file_attributes(
                torrent_info.files[0], str(test_file)
            )

            # File should still exist with same content
            assert test_file.exists()
            assert test_file.read_text() == "normal content"

        finally:
            await assembler.__aexit__(None, None, None)


class TestFinalizeFiles:
    """Test finalize_files method applies attributes."""

    @pytest.mark.asyncio
    async def test_finalize_applies_attributes(self, tmp_path):
        """Test that finalize_files applies attributes to all files."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        # Create files
        exec_file = tmp_path / "executable.sh"
        exec_file.write_bytes(b"#!/bin/bash")

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="executable.sh",
                    length=12,
                    path=["executable.sh"],
                    full_path=str(exec_file),
                    attributes="x",
                ),
            ],
            total_length=12,
            piece_length=16384,
            pieces=[b"\x01" * 20],
            num_pieces=1,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Clear execute bits
            os.chmod(exec_file, 0o644)

            # Finalize files (applies attributes)
            await assembler.finalize_files()

            # Check execute bit is set
            file_stat = os.stat(exec_file)
            assert file_stat.st_mode & stat.S_IXUSR

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_finalize_skips_padding_files(self, tmp_path):
        """Test that finalize_files skips padding files."""
        torrent_info = make_torrent_info_with_attributes()

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Should not raise - padding files are skipped
            await assembler.finalize_files()

            # Padding file should not exist
            padding_path = tmp_path / "padding"
            assert not padding_path.exists()

        finally:
            await assembler.__aexit__(None, None, None)


class TestRestoreAttributesFromCheckpoint:
    """Test restoring attributes from checkpoint."""

    @pytest.mark.asyncio
    async def test_restore_attributes(self, tmp_path):
        """Test restoring file attributes from checkpoint."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        # Create file
        exec_file = tmp_path / "executable.sh"
        exec_file.write_bytes(b"#!/bin/bash")

        # Create checkpoint with attributes
        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"\x00" * 20,
            torrent_name="test",
            created_at=1000.0,
            updated_at=2000.0,
            total_pieces=1,
            piece_length=16384,
            total_length=12,
            verified_pieces=[0],
            piece_states={},
            files=[
                FileCheckpoint(
                    path=str(exec_file),
                    size=12,
                    exists=True,
                    attributes="x",
                    symlink_path=None,
                    file_sha1=None,
                ),
            ],
        )

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[
                FileInfo(
                    name="executable.sh",
                    length=12,
                    path=["executable.sh"],
                    full_path=str(exec_file),
                    attributes="x",
                ),
            ],
            total_length=12,
            piece_length=16384,
            pieces=[b"\x01" * 20],
            num_pieces=1,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Clear execute bits
            os.chmod(exec_file, 0o644)

            # Restore attributes from checkpoint
            await assembler.restore_attributes_from_checkpoint(checkpoint)

            # Check execute bit is set
            file_stat = os.stat(exec_file)
            assert file_stat.st_mode & stat.S_IXUSR

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_restore_attributes_empty_checkpoint(self, tmp_path):
        """Test restoring from checkpoint with no files."""
        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"\x00" * 20,
            torrent_name="test",
            created_at=1000.0,
            updated_at=2000.0,
            total_pieces=1,
            piece_length=16384,
            total_length=0,
            verified_pieces=[],
            piece_states={},
            files=[],
            output_dir=str(tmp_path),
        )

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Should not raise
            await assembler.restore_attributes_from_checkpoint(checkpoint)

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_restore_attributes_missing_file(self, tmp_path):
        """Test restoring attributes when file doesn't exist."""
        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"\x00" * 20,
            torrent_name="test",
            created_at=1000.0,
            updated_at=2000.0,
            total_pieces=1,
            piece_length=16384,
            total_length=100,
            verified_pieces=[],
            piece_states={},
            files=[
                FileCheckpoint(
                    path=str(tmp_path / "nonexistent.txt"),
                    size=100,
                    exists=False,
                    attributes="x",
                    symlink_path=None,
                    file_sha1=None,
                ),
            ],
            output_dir=str(tmp_path),
        )

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))
        await assembler.__aenter__()

        try:
            # Should not raise - missing files are skipped
            await assembler.restore_attributes_from_checkpoint(checkpoint)

        finally:
            await assembler.__aexit__(None, None, None)

