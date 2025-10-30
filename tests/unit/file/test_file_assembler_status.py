"""Tests for file assembler status calculation."""

import pytest
from unittest.mock import MagicMock, patch

pytestmark = [pytest.mark.unit, pytest.mark.file]

from ccbt.storage.file_assembler import AsyncDownloadManager, FileAssemblerError
from ccbt.models import TorrentInfo


class TestFileAssemblerStatus:
    """Test file assembler status calculation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            total_length=1024,
            piece_length=256,
            pieces=[b"piece1", b"piece2", b"piece3", b"piece4"],
            num_pieces=4
        )
        
        self.download_manager = AsyncDownloadManager(
            torrent_data=self.torrent_info,
            output_dir="."
        )

    def test_get_status_with_file_assembler(self):
        """Test get_status with file assembler present."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 100.0
        mock_file_assembler.upload_rate = 50.0
        mock_file_assembler.peers = ["peer1", "peer2", "peer3"]
        
        # Mock pieces with some completed
        mock_piece1 = MagicMock()
        mock_piece1.completed = True
        mock_piece2 = MagicMock()
        mock_piece2.completed = True
        mock_piece3 = MagicMock()
        mock_piece3.completed = False
        mock_piece4 = MagicMock()
        mock_piece4.completed = False
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2, mock_piece3, mock_piece4]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.5  # 2 out of 4 pieces completed
        assert status["download_rate"] == 100.0
        assert status["upload_rate"] == 50.0
        assert status["peers"] == 3
        assert status["pieces"] == 4
        assert status["completed"] is False

    def test_get_status_all_pieces_completed(self):
        """Test get_status with all pieces completed."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 200.0
        mock_file_assembler.upload_rate = 100.0
        mock_file_assembler.peers = ["peer1", "peer2"]
        
        # Mock pieces all completed
        mock_piece1 = MagicMock()
        mock_piece1.completed = True
        mock_piece2 = MagicMock()
        mock_piece2.completed = True
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 1.0  # All pieces completed
        assert status["download_rate"] == 200.0
        assert status["upload_rate"] == 100.0
        assert status["peers"] == 2
        assert status["pieces"] == 2
        assert status["completed"] is True

    def test_get_status_no_pieces(self):
        """Test get_status with no pieces."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 0.0
        mock_file_assembler.upload_rate = 0.0
        mock_file_assembler.peers = []
        mock_file_assembler.pieces = []
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.0  # No pieces, so 0 progress
        assert status["download_rate"] == 0.0
        assert status["upload_rate"] == 0.0
        assert status["peers"] == 0
        assert status["pieces"] == 0
        assert status["completed"] is True  # No pieces means completed

    def test_get_status_no_file_assembler(self):
        """Test get_status without file assembler."""
        # Ensure no file assembler
        self.download_manager.file_assembler = None
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify default status
        assert status["progress"] == 0.0
        assert status["download_rate"] == 0.0
        assert status["upload_rate"] == 0.0
        assert status["peers"] == 0
        assert status["pieces"] == 0
        assert status["completed"] is False

    def test_get_status_partial_progress(self):
        """Test get_status with partial progress."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 75.5
        mock_file_assembler.upload_rate = 25.3
        mock_file_assembler.peers = ["peer1"]
        
        # Mock pieces with 1 out of 3 completed
        mock_piece1 = MagicMock()
        mock_piece1.completed = True
        mock_piece2 = MagicMock()
        mock_piece2.completed = False
        mock_piece3 = MagicMock()
        mock_piece3.completed = False
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2, mock_piece3]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == pytest.approx(1/3, rel=1e-6)  # 1 out of 3 pieces
        assert status["download_rate"] == 75.5
        assert status["upload_rate"] == 25.3
        assert status["peers"] == 1
        assert status["pieces"] == 3
        assert status["completed"] is False

    def test_get_status_edge_case_single_piece(self):
        """Test get_status with single piece."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 50.0
        mock_file_assembler.upload_rate = 10.0
        mock_file_assembler.peers = ["peer1", "peer2", "peer3", "peer4"]
        
        # Mock single piece completed
        mock_piece = MagicMock()
        mock_piece.completed = True
        
        mock_file_assembler.pieces = [mock_piece]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 1.0  # Single piece completed
        assert status["download_rate"] == 50.0
        assert status["upload_rate"] == 10.0
        assert status["peers"] == 4
        assert status["pieces"] == 1
        assert status["completed"] is True

    def test_get_status_edge_case_single_piece_not_completed(self):
        """Test get_status with single piece not completed."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 25.0
        mock_file_assembler.upload_rate = 5.0
        mock_file_assembler.peers = []
        
        # Mock single piece not completed
        mock_piece = MagicMock()
        mock_piece.completed = False
        
        mock_file_assembler.pieces = [mock_piece]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.0  # Single piece not completed
        assert status["download_rate"] == 25.0
        assert status["upload_rate"] == 5.0
        assert status["peers"] == 0
        assert status["pieces"] == 1
        assert status["completed"] is False

    def test_get_status_large_number_of_pieces(self):
        """Test get_status with large number of pieces."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 1000.0
        mock_file_assembler.upload_rate = 500.0
        mock_file_assembler.peers = [f"peer{i}" for i in range(50)]
        
        # Mock 100 pieces with 75 completed
        pieces = []
        for i in range(100):
            mock_piece = MagicMock()
            mock_piece.completed = i < 75  # First 75 are completed
            pieces.append(mock_piece)
        
        mock_file_assembler.pieces = pieces
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.75  # 75 out of 100 pieces
        assert status["download_rate"] == 1000.0
        assert status["upload_rate"] == 500.0
        assert status["peers"] == 50
        assert status["pieces"] == 100
        assert status["completed"] is False

    def test_get_status_zero_rates(self):
        """Test get_status with zero download/upload rates."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 0.0
        mock_file_assembler.upload_rate = 0.0
        mock_file_assembler.peers = []
        
        # Mock pieces
        mock_piece1 = MagicMock()
        mock_piece1.completed = False
        mock_piece2 = MagicMock()
        mock_piece2.completed = False
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.0
        assert status["download_rate"] == 0.0
        assert status["upload_rate"] == 0.0
        assert status["peers"] == 0
        assert status["pieces"] == 2
        assert status["completed"] is False

    def test_get_status_high_rates(self):
        """Test get_status with high download/upload rates."""
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 999999.99
        mock_file_assembler.upload_rate = 888888.88
        mock_file_assembler.peers = ["peer1", "peer2", "peer3", "peer4", "peer5"]
        
        # Mock pieces
        mock_piece1 = MagicMock()
        mock_piece1.completed = True
        mock_piece2 = MagicMock()
        mock_piece2.completed = True
        mock_piece3 = MagicMock()
        mock_piece3.completed = True
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2, mock_piece3]
        
        # Set the file assembler
        self.download_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = self.download_manager.get_status()
        
        # Verify status
        assert status["progress"] == 1.0
        assert status["download_rate"] == 999999.99
        assert status["upload_rate"] == 888888.88
        assert status["peers"] == 5
        assert status["pieces"] == 3
        assert status["completed"] is True


class TestFileAssemblerStatusIntegration:
    """Test file assembler status integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.torrent_info = TorrentInfo(
            name="integration_test_torrent",
            info_hash=b"\x01" * 20,
            announce="http://tracker.example.com/announce",
            total_length=2048,
            piece_length=512,
            pieces=[b"piece1", b"piece2", b"piece3", b"piece4"],
            num_pieces=4
        )

    def test_status_consistency_across_calls(self):
        """Test that status remains consistent across multiple calls."""
        download_manager = AsyncDownloadManager(
            torrent_data=self.torrent_info,
            output_dir="."
        )
        
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 100.0
        mock_file_assembler.upload_rate = 50.0
        mock_file_assembler.peers = ["peer1", "peer2"]
        
        # Mock pieces
        mock_piece1 = MagicMock()
        mock_piece1.completed = True
        mock_piece2 = MagicMock()
        mock_piece2.completed = False
        
        mock_file_assembler.pieces = [mock_piece1, mock_piece2]
        
        # Set the file assembler
        download_manager.file_assembler = mock_file_assembler
        
        # Get status multiple times
        status1 = download_manager.get_status()
        status2 = download_manager.get_status()
        status3 = download_manager.get_status()
        
        # All statuses should be identical
        assert status1 == status2 == status3
        assert status1["progress"] == 0.5
        assert status1["pieces"] == 2
        assert status1["completed"] is False

    def test_status_with_different_torrent_sizes(self):
        """Test status calculation with different torrent sizes."""
        # Small torrent
        small_torrent = TorrentInfo(
            name="small_torrent",
            info_hash=b"\x02" * 20,
            announce="http://tracker.example.com/announce",
            total_length=256,
            piece_length=256,
            pieces=[b"piece1"],
            num_pieces=1
        )
        
        small_manager = AsyncDownloadManager(
            torrent_data=small_torrent,
            output_dir="."
        )
        
        # Mock file assembler for small torrent
        mock_small_assembler = MagicMock()
        mock_small_assembler.download_rate = 50.0
        mock_small_assembler.upload_rate = 25.0
        mock_small_assembler.peers = ["peer1"]
        
        mock_piece = MagicMock()
        mock_piece.completed = True
        mock_small_assembler.pieces = [mock_piece]
        
        small_manager.file_assembler = mock_small_assembler
        
        # Large torrent
        large_torrent = TorrentInfo(
            name="large_torrent",
            info_hash=b"\x03" * 20,
            announce="http://tracker.example.com/announce",
            total_length=1048576,  # 1MB
            piece_length=16384,  # 16KB pieces
            pieces=[b"piece" + str(i).encode() for i in range(64)],
            num_pieces=64
        )
        
        large_manager = AsyncDownloadManager(
            torrent_data=large_torrent,
            output_dir="."
        )
        
        # Mock file assembler for large torrent
        mock_large_assembler = MagicMock()
        mock_large_assembler.download_rate = 1000.0
        mock_large_assembler.upload_rate = 500.0
        mock_large_assembler.peers = [f"peer{i}" for i in range(20)]
        
        # Mock pieces with half completed
        pieces = []
        for i in range(64):
            mock_piece = MagicMock()
            mock_piece.completed = i < 32  # First half completed
            pieces.append(mock_piece)
        
        mock_large_assembler.pieces = pieces
        
        large_manager.file_assembler = mock_large_assembler
        
        # Get statuses
        small_status = small_manager.get_status()
        large_status = large_manager.get_status()
        
        # Verify small torrent status
        assert small_status["progress"] == 1.0
        assert small_status["pieces"] == 1
        assert small_status["peers"] == 1
        assert small_status["completed"] is True
        
        # Verify large torrent status
        assert large_status["progress"] == 0.5
        assert large_status["pieces"] == 64
        assert large_status["peers"] == 20
        assert large_status["completed"] is False

    def test_status_edge_case_empty_torrent(self):
        """Test status with empty torrent."""
        empty_torrent = TorrentInfo(
            name="empty_torrent",
            info_hash=b"\x04" * 20,
            announce="http://tracker.example.com/announce",
            total_length=0,
            piece_length=256,
            pieces=[],
            num_pieces=0
        )
        
        empty_manager = AsyncDownloadManager(
            torrent_data=empty_torrent,
            output_dir="."
        )
        
        # Mock file assembler
        mock_file_assembler = MagicMock()
        mock_file_assembler.download_rate = 0.0
        mock_file_assembler.upload_rate = 0.0
        mock_file_assembler.peers = []
        mock_file_assembler.pieces = []
        
        empty_manager.file_assembler = mock_file_assembler
        
        # Get status
        status = empty_manager.get_status()
        
        # Verify status
        assert status["progress"] == 0.0
        assert status["pieces"] == 0
        assert status["peers"] == 0
        assert status["completed"] is True  # No pieces means completed
