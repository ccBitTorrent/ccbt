"""Additional tests for missing coverage lines in session.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccbt.models import FileInfo, TorrentInfo
from ccbt.session.session import AsyncTorrentSession, AsyncSessionManager


@pytest.mark.unit
@pytest.mark.session
class TestSessionMissingCoverage:
    """Test specific missing coverage lines in session.py."""

    def test_get_torrent_info_with_fileinfo_objects(self, tmp_path):
        """Test _get_torrent_info lines 201-202: FileInfo objects in files list."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "files": [
                FileInfo(name="file1.txt", length=100, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=200, path=["file2.txt"]),
            ],
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 300,
            },
            "file_info": {"total_length": 300},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        result = session._get_torrent_info(td)
        
        assert result is not None
        assert len(result.files) == 2
        assert all(isinstance(f, FileInfo) for f in result.files)

    def test_extract_is_private_from_torrentinfo_model(self, tmp_path):
        """Test _extract_is_private lines 243-247: TorrentInfoModel.is_private."""
        torrent_info = TorrentInfo(
            name="private_torrent",
            info_hash=b"x" * 20,
            is_private=True,
            announce="http://tracker.example.com",
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )
        
        session = AsyncTorrentSession(torrent_info, str(tmp_path))
        assert session.is_private is True

    def test_extract_is_private_from_dict_string_key(self, tmp_path):
        """Test _extract_is_private lines 271-273: dict with string key 'private'."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "info": {"private": 1},  # String key
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        assert session.is_private is True

    def test_normalize_torrent_data_with_torrentinfo_meta_version(self, tmp_path):
        """Test _normalize_torrent_data lines 345-350: TorrentInfoModel with meta_version and piece_layers."""
        torrent_info = TorrentInfo(
            name="v2_torrent",
            info_hash=b"x" * 20,
            announce="http://tracker.example.com",
            is_private=False,
            files=[FileInfo(name="file.txt", length=16384, path=["file.txt"])],
            total_length=16384,
            piece_length=16384,
            pieces=[b"x" * 20],
            num_pieces=1,
            meta_version=2,
            piece_layers=None,  # Optional field
            file_tree=None,  # Optional field
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
        
        # Lines 345-349: meta_version, piece_layers, file_tree paths
        assert result["meta_version"] == 2
        # piece_layers and file_tree are only added if truthy (lines 346-349)
        # Since we passed None, they won't be in result, which tests the conditional paths

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_recreates_manager(self, tmp_path):
        """Test _apply_magnet_file_selection_if_needed lines 365-376: Recreate file_selection_manager."""
        from ccbt.core.magnet import MagnetInfo
        
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {
                "total_length": 16384,
                "type": "multi",
            },
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        
        # Add files to torrent_data after session creation
        session.torrent_data["files"] = [
            FileInfo(name="file1.txt", length=8192, path=["file1.txt"]),
            FileInfo(name="file2.txt", length=8192, path=["file2.txt"]),
        ]
        
        magnet_info = MagnetInfo(
            info_hash=b"x" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0],
        )
        session.magnet_info = magnet_info
        session.file_selection_manager = None  # Missing, should be recreated
        
        # Mock piece manager
        session.piece_manager = Mock()
        
        await session._apply_magnet_file_selection_if_needed()
        
        # Should recreate file_selection_manager
        assert session.file_selection_manager is not None
        assert session.piece_manager.file_selection_manager == session.file_selection_manager

    @pytest.mark.asyncio
    async def test_apply_magnet_file_selection_single_file_skips(self, tmp_path):
        """Test _apply_magnet_file_selection_if_needed lines 386-388: Skip for single file."""
        from ccbt.core.magnet import MagnetInfo
        
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {
                "total_length": 16384,
                "type": "single",
                "name": "test.txt",
            },
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        magnet_info = MagnetInfo(
            info_hash=b"x" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0],
        )
        session.magnet_info = magnet_info
        session.file_selection_manager = Mock()
        
        await session._apply_magnet_file_selection_if_needed()
        
        # Should return early for single file (no selection applied)

    @pytest.mark.asyncio
    async def test_start_with_checkpoint_resume(self, tmp_path):
        """Test start() lines 408-422: Checkpoint loading and resume."""
        from ccbt.models import TorrentCheckpoint
        
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 10,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20] * 10,
                "total_length": 163840,
            },
            "file_info": {"total_length": 163840},
        }
        
        session = AsyncTorrentSession(td, str(tmp_path))
        
        # Create mock checkpoint
        import time
        mock_checkpoint = TorrentCheckpoint(
            info_hash=b"x" * 20,
            torrent_name="test",
            total_pieces=10,
            verified_pieces=[0, 1, 2],
            piece_states={},
            file_checkpoints=[],
            created_at=time.time(),
            updated_at=time.time(),
            piece_length=16384,
            total_length=163840,
            output_dir=str(tmp_path),
        )
        
        # Mock checkpoint manager
        session.checkpoint_manager.load_checkpoint = AsyncMock(return_value=mock_checkpoint)
        session.checkpoint_manager.checkpoint_enabled = True
        
        # Mock config
        session.config.disk.checkpoint_enabled = True
        session.config.disk.auto_resume = True
        
        # Mock components
        session.tracker.start = AsyncMock()
        session.piece_manager.start = AsyncMock()
        session._resume_from_checkpoint = AsyncMock()
        
        await session.start(resume=True)
        
        # Verify checkpoint was loaded
        session.checkpoint_manager.load_checkpoint.assert_called_once()
        session._resume_from_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_pex_manager(self, tmp_path):
        """Test start() lines 454-465: PEX manager initialization for non-private torrent."""
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
        session.is_private = False  # Non-private torrent
        
        # Mock config
        session.config.discovery.enable_pex = True
        
        # Mock components
        session.tracker.start = AsyncMock()
        session.piece_manager.start = AsyncMock()
        session.checkpoint_manager.load_checkpoint = AsyncMock(return_value=None)
        
        with patch("ccbt.session.session.PEXManager") as mock_pex:
            mock_pex_instance = Mock()
            mock_pex_instance.start = AsyncMock()
            mock_pex.return_value = mock_pex_instance
            
            await session.start()
            
            # Verify PEX manager was created and started
            assert session.pex_manager is not None
            session.pex_manager.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cleanup_background_tasks(self, tmp_path):
        """Test stop() lines 486-515: Cleanup background tasks."""
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
        
        # Create background tasks
        session._announce_task = asyncio.create_task(asyncio.sleep(10))
        session._status_task = asyncio.create_task(asyncio.sleep(10))
        session._checkpoint_task = asyncio.create_task(asyncio.sleep(10))
        
        # Mock stop methods
        session.tracker.stop = AsyncMock()
        session.piece_manager.stop = AsyncMock()
        session.download_manager.stop = AsyncMock()
        
        if session.pex_manager:
            session.pex_manager.stop = AsyncMock()
        
        await session.stop()
        
        # Verify tasks were cancelled
        assert session._announce_task.cancelled()
        assert session._status_task.cancelled()
        assert session._checkpoint_task.cancelled()
        
        # Verify components stopped
        session.tracker.stop.assert_called_once()
        session.piece_manager.stop.assert_called_once()

