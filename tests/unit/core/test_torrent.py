"""Tests for torrent file parsing functionality.
"""

import os
import tempfile

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]

from ccbt.core.bencode import encode
from ccbt.core.torrent import TorrentError, TorrentParser


class TestTorrentParser:
    """Test cases for TorrentParser."""

    def test_parse_single_file_torrent(self):
        """Test parsing a single file torrent."""
        # Create a mock torrent data
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"test_file.txt",
                b"length": 12345,
                b"piece length": 16384,
                b"pieces": b"x" * 40,  # 2 pieces * 20 bytes each
            },
        }

        # Encode as bencode
        encoded_data = encode(torrent_data)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Check basic structure
            assert hasattr(result, "announce")
            assert hasattr(result, "info_hash")
            assert hasattr(result, "files")
            assert hasattr(result, "pieces")

            # Check announce URL
            assert result.announce == "http://tracker.example.com:6969/announce"

            # Check file info
            assert len(result.files) == 1
            file_info = result.files[0]
            assert file_info.length == 12345
            assert file_info.name == "test_file.txt"

            # Check pieces info
            assert result.piece_length == 16384
            assert result.num_pieces == 2
            assert len(result.pieces) == 2

        finally:
            os.unlink(temp_path)

    def test_parse_multi_file_torrent(self):
        """Test parsing a multi-file torrent."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"TestDirectory",
                b"piece length": 32768,
                b"pieces": b"x" * 60,  # 3 pieces * 20 bytes each
                b"files": [
                    {
                        b"length": 1000,
                        b"path": [b"file1.txt"],
                    },
                    {
                        b"length": 2000,
                        b"path": [b"subdir", b"file2.txt"],
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

            # Check file info
            assert len(result.files) == 2
            assert result.name == "TestDirectory"
            assert result.total_length == 3000

            # Check first file
            assert result.files[0].length == 1000
            assert result.files[0].name == "file1.txt"

            # Check second file
            assert result.files[1].length == 2000
            assert result.files[1].name == "file2.txt"

        finally:
            os.unlink(temp_path)

    def test_parse_invalid_torrent_missing_announce(self):
        """Test parsing torrent missing announce key."""
        torrent_data = {
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"piece length": 16384,
                b"pieces": b"x" * 20,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(TorrentError, match="Missing required key"):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_invalid_torrent_missing_info(self):
        """Test parsing torrent missing info key."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(TorrentError, match="Missing required key"):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_invalid_torrent_no_length_or_files(self):
        """Test parsing torrent with neither length nor files."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(
                TorrentError,
                match="Torrent must specify either length",
            ):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_torrent_missing_piece_length(self):
        """Test parsing torrent missing piece length."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"pieces": b"x" * 20,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(TorrentError, match="Missing piece length"):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_torrent_missing_pieces(self):
        """Test parsing torrent missing pieces."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"piece length": 16384,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(TorrentError, match="Missing pieces"):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_torrent_invalid_pieces_length(self):
        """Test parsing torrent with invalid pieces length."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"piece length": 16384,
                b"pieces": b"x" * 15,  # Not multiple of 20
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            with pytest.raises(TorrentError, match="Invalid pieces data length"):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = TorrentParser()
        with pytest.raises(TorrentError, match="not found"):
            parser.parse("non_existent_file.torrent")

    def test_get_info_hash(self):
        """Test getting info hash."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"piece length": 16384,
                b"pieces": b"x" * 20,
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            info_hash = parser.get_info_hash(result)
            assert isinstance(info_hash, bytes)
            assert len(info_hash) == 20  # SHA-1 is 20 bytes

        finally:
            os.unlink(temp_path)

    def test_utility_methods(self):
        """Test utility methods."""
        torrent_data = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"info": {
                b"name": b"tests/data/test.txt",
                b"length": 1000,
                b"piece length": 16384,
                b"pieces": b"x" * 40,  # 2 pieces
            },
        }

        encoded_data = encode(torrent_data)

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(encoded_data)
            temp_path = f.name

        try:
            parser = TorrentParser()
            result = parser.parse(temp_path)

            # Test utility methods
            assert (
                parser.get_announce_url(result)
                == "http://tracker.example.com:6969/announce"
            )
            assert parser.get_total_length(result) == 1000
            assert parser.get_piece_length(result) == 16384
            assert parser.get_num_pieces(result) == 2

            # Test piece hash retrieval
            hash1 = parser.get_piece_hash(result, 0)
            hash2 = parser.get_piece_hash(result, 1)
            assert len(hash1) == 20
            assert len(hash2) == 20

            # Test invalid piece index
            with pytest.raises(TorrentError, match="Invalid piece index"):
                parser.get_piece_hash(result, 2)

        finally:
            os.unlink(temp_path)
