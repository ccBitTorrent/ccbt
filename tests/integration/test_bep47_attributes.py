"""End-to-end integration tests for BEP 47: Padding Files and Extended File Attributes.

Tests complete workflows including:
- Downloading torrents with attributes
- Padding file handling
- Symlink creation
- Executable bit setting
- Attribute preservation on resume
"""

from __future__ import annotations

import os
import platform
import stat
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

from ccbt.core.bencode import encode
from ccbt.core.torrent import TorrentParser
from ccbt.piece.file_selection import FileSelectionManager
from ccbt.storage.file_assembler import AsyncFileAssembler


def create_torrent_with_attributes(
    temp_dir: Path, name: str, files_with_attrs: list[dict[str, any]]
) -> str:
    """Create a torrent file with BEP 47 attributes."""
    torrent_data = {
        b"announce": b"http://tracker.example.com:6969/announce",
        b"info": {
            b"name": name.encode("utf-8"),
            b"piece length": 16384,
            b"pieces": b"x" * 20,  # 1 piece
            b"files": [],
        },
    }

    # Add files with attributes
    for file_data in files_with_attrs:
        file_entry = {
            b"length": file_data["length"],
            b"path": [part.encode("utf-8") for part in file_data["path"]],
        }
        if "attr" in file_data:
            file_entry[b"attr"] = file_data["attr"].encode("utf-8")
        if "symlink_path" in file_data:
            file_entry[b"symlink path"] = file_data["symlink_path"].encode("utf-8")
        if "sha1" in file_data:
            file_entry[b"sha1"] = file_data["sha1"]

        torrent_data[b"info"][b"files"].append(file_entry)

    # Encode and save
    encoded_data = encode(torrent_data)
    torrent_file = temp_dir / f"{name}.torrent"
    torrent_file.write_bytes(encoded_data)

    return str(torrent_file)


class TestDownloadWithAttributes:
    """Test downloading torrents with BEP 47 attributes."""

    @pytest.mark.asyncio
    async def test_download_with_executable_files(self, tmp_path):
        """Test downloading torrent with executable files."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        # Create torrent with executable file
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "executable_torrent",
            [
                {
                    "path": ["script.sh"],
                    "length": 100,
                    "attr": "x",  # Executable
                },
            ],
        )

        # Parse torrent
        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        # Verify attributes parsed
        assert len(torrent_info.files) == 1
        assert torrent_info.files[0].attributes == "x"
        assert torrent_info.files[0].is_executable is True

        # Use file assembler to test attribute application
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        assembler = AsyncFileAssembler(torrent_info, str(output_dir))
        await assembler.__aenter__()

        try:
            # Create file manually (simulating download)
            script_file = output_dir / "script.sh"
            script_file.write_bytes(b"#!/bin/bash\necho test")

            # Clear execute bits
            os.chmod(script_file, 0o644)

            # Apply attributes
            await assembler._apply_file_attributes(
                torrent_info.files[0], str(script_file)
            )

            # Verify execute bit is set
            file_stat = os.stat(script_file)
            assert file_stat.st_mode & stat.S_IXUSR

        finally:
            await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_download_with_symlinks(self, tmp_path):
        """Test downloading torrent with symlinks."""
        if platform.system() == "Windows":
            pytest.skip("Symlink creation requires admin privileges on Windows")
        # Create target file
        target_file = tmp_path / "target.txt"
        target_file.write_text("target content")

        # Create torrent with symlink
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "symlink_torrent",
            [
                {
                    "path": ["link.lnk"],
                    "length": 0,
                    "attr": "l",  # Symlink
                    "symlink_path": str(target_file),
                },
            ],
        )

        # Parse torrent
        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        # Verify symlink parsed
        assert torrent_info.files[0].is_symlink is True
        assert torrent_info.files[0].symlink_path == str(target_file)

        # Use file assembler to test symlink creation
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        assembler = AsyncFileAssembler(torrent_info, str(output_dir))
        await assembler.__aenter__()

        try:
            # Create placeholder file (must exist before creating symlink)
            link_file = output_dir / "link.lnk"
            link_file.write_text("placeholder")

            # Apply attributes (creates symlink)
            await assembler._apply_file_attributes(
                torrent_info.files[0], str(link_file)
            )

            # Verify symlink created
            assert link_file.is_symlink()
            assert link_file.readlink() == target_file

        finally:
            await assembler.__aexit__(None, None, None)


class TestPaddingFileHandling:
    """Test padding file handling in complete workflow."""

    @pytest.mark.asyncio
    async def test_padding_files_not_downloaded(self, tmp_path):
        """Test that padding files are not created on disk."""
        # Create torrent with normal and padding files
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "with_padding",
            [
                {
                    "path": ["normal.txt"],
                    "length": 1000,
                },
                {
                    "path": ["padding"],
                    "length": 500,
                    "attr": "p",  # Padding file
                },
            ],
        )

        # Parse torrent
        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        # Verify padding file identified
        padding_files = [f for f in torrent_info.files if f.is_padding]
        normal_files = [f for f in torrent_info.files if not f.is_padding]

        assert len(padding_files) == 1
        assert len(normal_files) == 1

        # Test file selection manager skips padding files
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        file_manager = FileSelectionManager(torrent_info)

        # Check statistics
        stats = file_manager.get_statistics()

        # Should count only non-padding files
        assert stats["total_files"] == 1  # Only normal.txt
        assert stats["padding_files"] == 1
        assert stats["padding_size"] == 500

    @pytest.mark.asyncio
    async def test_padding_files_excluded_from_segments(self, tmp_path):
        """Test that padding files don't create file segments."""
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "with_padding",
            [
                {
                    "path": ["normal.txt"],
                    "length": 1000,
                },
                {
                    "path": ["padding"],
                    "length": 500,
                    "attr": "p",
                },
            ],
        )

        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        assembler = AsyncFileAssembler(torrent_info, str(output_dir))
        await assembler.__aenter__()

        try:
            # Check file segments exclude padding files
            segment_paths = {seg.file_path for seg in assembler.file_segments}

            # Padding file should not be in segments (check by basename)
            padding_segments = [
                seg
                for seg in assembler.file_segments
                if os.path.basename(seg.file_path) == "padding"
            ]
            assert len(padding_segments) == 0

        finally:
            await assembler.__aexit__(None, None, None)


class TestAttributePreservation:
    """Test that attributes are preserved on resume."""

    @pytest.mark.asyncio
    async def test_attributes_preserved_on_resume(self, tmp_path):
        """Test that file attributes are preserved when resuming download."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        # Create torrent with executable file
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "resume_test",
            [
                {
                    "path": ["script.sh"],
                    "length": 100,
                    "attr": "x",
                },
            ],
        )

        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        assembler = AsyncFileAssembler(torrent_info, str(output_dir))
        await assembler.__aenter__()

        try:
            # Create file
            script_file = output_dir / "script.sh"
            script_file.write_bytes(b"#!/bin/bash")

            # Set execute bit
            os.chmod(script_file, 0o755)

            # Verify execute bit is set
            file_stat = os.stat(script_file)
            assert file_stat.st_mode & stat.S_IXUSR

            # Simulate resume: restore attributes from checkpoint
            from ccbt.models import FileCheckpoint, TorrentCheckpoint

            checkpoint = TorrentCheckpoint(
                version="1.0",
                info_hash=torrent_info.info_hash,
                torrent_name=torrent_info.name,
                created_at=1000.0,
                updated_at=2000.0,
                total_pieces=1,
                piece_length=torrent_info.piece_length,
                total_length=torrent_info.total_length,
                verified_pieces=[],
                piece_states={},
                files=[
                    FileCheckpoint(
                        path=str(script_file),
                        size=100,
                        exists=True,
                        attributes="x",
                        symlink_path=None,
                        file_sha1=None,
                    ),
                ],
                output_dir=str(output_dir),
            )

            # Clear execute bits
            os.chmod(script_file, 0o644)

            # Restore attributes
            await assembler.restore_attributes_from_checkpoint(checkpoint)

            # Verify execute bit restored
            file_stat = os.stat(script_file)
            assert file_stat.st_mode & stat.S_IXUSR

        finally:
            await assembler.__aexit__(None, None, None)


class TestMixedAttributes:
    """Test torrents with mixed attribute types."""

    @pytest.mark.asyncio
    async def test_mixed_attributes_workflow(self, tmp_path):
        """Test complete workflow with mixed attributes."""
        # Create target for symlink
        target_file = tmp_path / "target.txt"
        target_file.write_text("target")

        # Create torrent with various attributes
        torrent_file = create_torrent_with_attributes(
            tmp_path,
            "mixed_attrs",
            [
                {
                    "path": ["normal.txt"],
                    "length": 100,
                },
                {
                    "path": ["exec.sh"],
                    "length": 200,
                    "attr": "x",
                },
                {
                    "path": ["padding"],
                    "length": 300,
                    "attr": "p",
                },
                {
                    "path": ["link.lnk"],
                    "length": 0,
                    "attr": "l",
                    "symlink_path": str(target_file),
                },
            ],
        )

        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        # Verify all attributes parsed correctly
        assert len(torrent_info.files) == 4
        assert torrent_info.files[0].attributes is None
        assert torrent_info.files[1].attributes == "x"
        assert torrent_info.files[2].attributes == "p"
        assert torrent_info.files[3].attributes == "l"

        # Verify properties
        assert not torrent_info.files[0].is_padding
        assert torrent_info.files[1].is_executable
        assert torrent_info.files[2].is_padding
        assert torrent_info.files[3].is_symlink

        # Test file selection manager
        file_manager = FileSelectionManager(torrent_info)
        stats = file_manager.get_statistics()

        # Should count only non-padding files
        assert stats["total_files"] == 3  # normal, exec, link (no padding)
        assert stats["padding_files"] == 1
        assert stats["padding_size"] == 300

