"""Tests for _normalize_torrent_data paths to boost coverage."""

from __future__ import annotations

import pytest

from ccbt.models import FileInfo, TorrentInfo
from ccbt.session.session import AsyncTorrentSession


@pytest.mark.unit
@pytest.mark.session
class TestNormalizeTorrentData:
    """Test _normalize_torrent_data with TorrentInfoModel and edge cases."""

    def test_normalize_torrent_info_model_with_meta_version(self, tmp_path):
        """Test _normalize_torrent_data with TorrentInfoModel including meta_version (lines 330-350)."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"x" * 20,
            announce="http://tracker.example.com",
            is_private=False,
            files=[
                FileInfo(name="file1.txt", length=16384, path=["file1.txt"]),
            ],
            total_length=16384,
            piece_length=16384,
            pieces=[b"x" * 20],
            num_pieces=1,
            meta_version=2,
            piece_layers={"file1.txt": [b"y" * 32]},
            file_tree={"": {"file1.txt": {"length": 16384}}},
        )
        
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        result = session._normalize_torrent_data(torrent_info)
        
        assert result["meta_version"] == 2
        assert "piece_layers" in result
        assert "file_tree" in result

    def test_normalize_dict_builds_pieces_info_missing(self, tmp_path):
        """Test _normalize_torrent_data builds pieces_info when missing (lines 292-305)."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            # Missing pieces_info but has legacy fields
            "pieces": [b"x" * 20],
            "piece_length": 16384,
            "num_pieces": 1,
            "total_length": 16384,
            "file_info": {"total_length": 16384},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        result = session._normalize_torrent_data(td)
        
        assert "pieces_info" in result
        assert result["pieces_info"]["piece_hashes"] == [b"x" * 20]
        assert result["pieces_info"]["piece_length"] == 16384

    def test_normalize_dict_rebuilds_invalid_pieces_info(self, tmp_path):
        """Test _normalize_torrent_data rebuilds invalid pieces_info (lines 308-322)."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {"piece_hashes": []},  # Incomplete pieces_info
            "pieces": [b"x" * 20],
            "piece_length": 16384,
            "num_pieces": 1,
            "total_length": 16384,
            "file_info": {"total_length": 16384},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        result = session._normalize_torrent_data(td)
        
        # Should rebuild pieces_info with all required fields
        assert "pieces_info" in result
        assert "piece_length" in result["pieces_info"]
        assert "num_pieces" in result["pieces_info"]

    def test_normalize_dict_adds_missing_file_info(self, tmp_path):
        """Test _normalize_torrent_data adds missing file_info (lines 323-327)."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            # Missing file_info
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        result = session._normalize_torrent_data(td)
        
        assert "file_info" in result
        assert result["file_info"]["total_length"] == 16384

