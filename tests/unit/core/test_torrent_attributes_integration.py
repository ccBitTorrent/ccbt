"""Integration tests for BEP 47 attributes in torrent parser.

Tests that verify the TorrentParser correctly extracts BEP 47 attributes
from torrent metadata and creates FileInfo objects with attribute fields.
"""

from __future__ import annotations

import hashlib
import os
import tempfile

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]

from ccbt.core.bencode import encode
from ccbt.core.torrent import TorrentParser


class TestSingleFileTorrentWithAttributes:
    """Test parsing single-file torrents with BEP 47 attributes."""

    def test_parse_single_file_with_executable_attr(self):
        """Test parsing single-file torrent with executable attribute."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"executable.sh",
                b"length": 12345,
                b"piece length": 16384,
                b"pieces": b"x" * 20,  # 1 piece
                b"attr": b"x",  # Executable attribute
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Check file info
            assert len(result.files) == 1
            file_info = result.files[0]
            assert file_info.name == "executable.sh"
            assert file_info.length == 12345
            assert file_info.attributes == "x"
            assert file_info.is_executable is True
            assert file_info.is_padding is False

        finally:
            os.unlink(temp_path)

    def test_parse_single_file_with_file_sha1(self):
        """Test parsing single-file torrent with SHA-1 hash."""
        file_content = b"test file content"
        file_sha1 = hashlib.sha1(file_content).digest()  # nosec B324

        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"test_file.txt",
                b"length": len(file_content),
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"sha1": file_sha1,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            file_info = result.files[0]
            assert file_info.file_sha1 == file_sha1
            assert len(file_info.file_sha1) == 20

        finally:
            os.unlink(temp_path)

    def test_parse_single_file_with_padding_attr(self):
        """Test parsing single-file torrent with padding attribute."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"padding_file",
                b"length": 1000,
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"attr": b"p",  # Padding file
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            file_info = result.files[0]
            assert file_info.attributes == "p"
            assert file_info.is_padding is True

        finally:
            os.unlink(temp_path)


class TestMultiFileTorrentWithAttributes:
    """Test parsing multi-file torrents with BEP 47 attributes."""

    def test_parse_multi_file_with_mixed_attributes(self):
        """Test parsing multi-file torrent with various attributes."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"MixedAttributes",
                b"piece length": 32768,
                b"pieces": b"x" * 60,  # 3 pieces
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"normal_file.txt"],
                        # No attributes - normal file
                    },
                    {
                        b"length": 2000,
                        b"path": [b"executable.sh"],
                        b"attr": b"x",  # Executable
                    },
                    {
                        b"length": 500,
                        b"path": [b"padding"],
                        b"attr": b"p",  # Padding file
                    },
                    {
                        b"length": 0,
                        b"path": [b"symlink.lnk"],
                        b"attr": b"l",  # Symlink
                        b"symlink path": b"/target/file.txt",
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Check file count
            assert len(result.files) == 4

            # Check normal file (no attributes)
            file0 = result.files[0]
            assert file0.name == "normal_file.txt"
            assert file0.attributes is None
            assert file0.is_padding is False

            # Check executable file
            file1 = result.files[1]
            assert file1.name == "executable.sh"
            assert file1.attributes == "x"
            assert file1.is_executable is True
            assert file1.is_padding is False

            # Check padding file
            file2 = result.files[2]
            assert file2.name == "padding"
            assert file2.attributes == "p"
            assert file2.is_padding is True

            # Check symlink file
            file3 = result.files[3]
            assert file3.name == "symlink.lnk"
            assert file3.attributes == "l"
            assert file3.is_symlink is True
            assert file3.symlink_path == "/target/file.txt"

        finally:
            os.unlink(temp_path)

    def test_parse_multi_file_with_file_sha1(self):
        """Test parsing multi-file torrent with SHA-1 hashes."""
        content1 = b"file1 content"
        content2 = b"file2 content"
        sha1_1 = hashlib.sha1(content1).digest()  # nosec B324
        sha1_2 = hashlib.sha1(content2).digest()  # nosec B324

        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"Sha1Files",
                b"piece length": 32768,
                b"pieces": b"x" * 40,  # 2 pieces
                b"files": [
                    {
                        b"length": len(content1),
                        b"path": [b"file1.txt"],
                        b"sha1": sha1_1,
                    },
                    {
                        b"length": len(content2),
                        b"path": [b"file2.txt"],
                        b"sha1": sha1_2,
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            assert result.files[0].file_sha1 == sha1_1
            assert result.files[1].file_sha1 == sha1_2

        finally:
            os.unlink(temp_path)

    def test_parse_multi_file_with_combined_attributes(self):
        """Test parsing files with combined attributes (e.g., 'px', 'lh')."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"CombinedAttributes",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"executable_hidden"],
                        b"attr": b"xh",  # Executable + Hidden
                    },
                    {
                        b"length": 500,
                        b"path": [b"padding_executable"],
                        b"attr": b"px",  # Padding + Executable
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Check combined attributes
            file0 = result.files[0]
            assert file0.attributes == "xh"
            assert file0.is_executable is True
            assert file0.is_hidden is True
            assert file0.is_padding is False

            file1 = result.files[1]
            assert file1.attributes == "px"
            assert file1.is_padding is True
            assert file1.is_executable is True

        finally:
            os.unlink(temp_path)


class TestPaddingFileDetection:
    """Test padding file detection in parsed torrents."""

    def test_padding_files_identified_correctly(self):
        """Test that padding files are correctly identified."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"WithPadding",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"normal.txt"],
                    },
                    {
                        b"length": 500,
                        b"path": [b"padding"],
                        b"attr": b"p",
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Count padding vs normal files
            padding_files = [f for f in result.files if f.is_padding]
            normal_files = [f for f in result.files if not f.is_padding]

            assert len(padding_files) == 1
            assert len(normal_files) == 1
            assert padding_files[0].name == "padding"
            assert normal_files[0].name == "normal.txt"

        finally:
            os.unlink(temp_path)

    def test_padding_files_in_total_length(self):
        """Test that padding files are included in total_length calculation."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"WithPadding",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"normal.txt"],
                    },
                    {
                        b"length": 500,
                        b"path": [b"padding"],
                        b"attr": b"p",
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Total length should include padding files
            # (they're used for piece alignment)
            assert result.total_length == 1500

            # Verify individual file lengths
            assert result.files[0].length == 1000
            assert result.files[1].length == 500

        finally:
            os.unlink(temp_path)


class TestSymlinkParsing:
    """Test symlink parsing from torrent metadata."""

    def test_symlink_with_target_path(self):
        """Test parsing symlink with target path."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"WithSymlink",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"files": [
                    {
                        b"length": 0,
                        b"path": [b"link.lnk"],
                        b"attr": b"l",
                        b"symlink path": b"/absolute/target/path",
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            file_info = result.files[0]
            assert file_info.is_symlink is True
            assert file_info.symlink_path == "/absolute/target/path"
            assert file_info.length == 0

        finally:
            os.unlink(temp_path)

    def test_symlink_with_relative_path(self):
        """Test parsing symlink with relative target path."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"WithSymlink",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                b"files": [
                    {
                        b"length": 0,
                        b"path": [b"link.lnk"],
                        b"attr": b"l",
                        b"symlink path": b"../relative/target",
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            file_info = result.files[0]
            assert file_info.is_symlink is True
            assert file_info.symlink_path == "../relative/target"

        finally:
            os.unlink(temp_path)


class TestBackwardCompatibility:
    """Test backward compatibility with torrents without BEP 47 attributes."""

    def test_parse_torrent_without_attributes(self):
        """Test parsing torrent without BEP 47 attributes works normally."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"LegacyTorrent",
                b"length": 12345,
                b"piece length": 16384,
                b"pieces": b"x" * 20,
                # No attr, symlink path, or sha1 fields
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            file_info = result.files[0]
            assert file_info.attributes is None
            assert file_info.symlink_path is None
            assert file_info.file_sha1 is None
            assert file_info.is_padding is False
            assert file_info.is_symlink is False

        finally:
            os.unlink(temp_path)

    def test_parse_multi_file_torrent_without_attributes(self):
        """Test parsing multi-file torrent without attributes."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"LegacyMultiFile",
                b"piece length": 32768,
                b"pieces": b"x" * 40,
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"file1.txt"],
                        # No attributes
                    },
                    {
                        b"length": 2000,
                        b"path": [b"file2.txt"],
                        # No attributes
                    },
                ],
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            for file_info in result.files:
                assert file_info.attributes is None
                assert file_info.is_padding is False

        finally:
            os.unlink(temp_path)

