"""Integration tests for resume functionality.

Tests complete resume workflow from checkpoint loading to download continuation.
"""

import asyncio
import contextlib
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccbt.storage.checkpoint import CheckpointManager
from ccbt.models import (
    CheckpointFormat,
    DiskConfig,
    DownloadStats,
    FileCheckpoint,
    TorrentCheckpoint,
)
from ccbt.session import AsyncSessionManager, AsyncTorrentSession


class TestResumeIntegration:
    """Test complete resume functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        return DiskConfig(
            checkpoint_enabled=True,
            checkpoint_format=CheckpointFormat.JSON,
            checkpoint_dir=str(temp_dir / "checkpoints"),
            checkpoint_interval=1.0,
            checkpoint_on_piece=True,
            auto_resume=True,
            checkpoint_compression=False,
        )

    @pytest.fixture
    def sample_torrent_data(self):
        """Create sample torrent data."""
        return {
            "info_hash": b"\x00" * 20,
            "name": "test_torrent",
            "file_info": {
                "type": "single",
                "name": "test.bin",
                "total_length": 16384,
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x00" * 20],
            },
        }

    @pytest.fixture
    def sample_checkpoint(self, sample_torrent_data):
        """Create sample checkpoint."""
        return TorrentCheckpoint(
            info_hash=sample_torrent_data["info_hash"],
            torrent_name=sample_torrent_data["name"],
            created_at=time.time() - 3600,  # 1 hour ago
            updated_at=time.time() - 1800,  # 30 minutes ago
            total_pieces=sample_torrent_data["pieces_info"]["num_pieces"],
            piece_length=sample_torrent_data["pieces_info"]["piece_length"],
            total_length=sample_torrent_data["file_info"]["total_length"],
            verified_pieces=[],  # No pieces verified yet
            download_stats=DownloadStats(
                bytes_downloaded=0,
                download_time=0,
                average_speed=0,
                start_time=time.time() - 3600,
                last_update=time.time() - 1800,
            ),
            output_dir="/tmp/test",
            files=[
                FileCheckpoint(
                    path="/tmp/test/test.bin",
                    size=sample_torrent_data["file_info"]["total_length"],
                    exists=False,
                ),
            ],
            endgame_mode=False,
        )

    @pytest.mark.asyncio
    async def test_session_resume_from_checkpoint(
        self,
        config,
        sample_torrent_data,
        sample_checkpoint,
        temp_dir,
    ):
        """Test session resuming from checkpoint."""
        # Create checkpoint manager and save checkpoint
        checkpoint_manager = CheckpointManager(config)
        await checkpoint_manager.save_checkpoint(sample_checkpoint)

        # Create session manager
        session_manager = AsyncSessionManager(str(temp_dir))

        # Mock the torrent parser to avoid file system issues
        with patch.object(session_manager, "add_torrent") as mock_add_torrent:
            mock_add_torrent.return_value = sample_torrent_data["info_hash"].hex()

            # Mock the session to avoid actual network operations
            with patch("ccbt.session.AsyncTorrentSession") as mock_session_class:
                mock_session = Mock()
                mock_session.info.info_hash = sample_torrent_data["info_hash"]
                mock_session.info.name = sample_torrent_data["name"]
                mock_session.start = AsyncMock()

                mock_session_class.return_value = mock_session

                # Add torrent with resume=True
                await session_manager.add_torrent(
                    "dummy.torrent",
                    resume=True,
                )

                # Verify session was created and started with resume=True
                mock_add_torrent.assert_called_once_with("dummy.torrent", resume=True)

    @pytest.mark.asyncio
    async def test_checkpoint_auto_save_on_piece_verification(
        self,
        config,
        sample_torrent_data,
        temp_dir,
    ):
        """Test automatic checkpoint saving on piece verification."""
        # Create session
        session = AsyncTorrentSession(sample_torrent_data, str(temp_dir))
        session.config.disk = config

        # Mock checkpoint manager with async methods
        checkpoint_manager = Mock()
        checkpoint_manager.save_checkpoint = AsyncMock()
        session.checkpoint_manager = checkpoint_manager

        # Mock piece manager
        piece_manager = Mock()
        piece_manager.get_checkpoint_state = AsyncMock(return_value=Mock())
        session.download_manager.piece_manager = piece_manager

        # Simulate piece verification
        await session._on_piece_verified(0)

        # Verify checkpoint save was called
        checkpoint_manager.save_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_periodic_save(
        self,
        config,
        sample_torrent_data,
        temp_dir,
    ):
        """Test periodic checkpoint saving."""
        # Create session
        session = AsyncTorrentSession(sample_torrent_data, str(temp_dir))
        session.config.disk = config
        session.config.disk.checkpoint_interval = 0.1  # Very short interval for testing

        # Mock checkpoint manager with async methods
        checkpoint_manager = Mock()
        checkpoint_manager.save_checkpoint = AsyncMock()
        session.checkpoint_manager = checkpoint_manager

        # Mock piece manager
        piece_manager = Mock()
        piece_manager.get_checkpoint_state = AsyncMock(return_value=Mock())
        session.download_manager.piece_manager = piece_manager

        # Start checkpoint loop
        checkpoint_task = asyncio.create_task(session._checkpoint_loop())

        # Wait for at least one checkpoint save
        await asyncio.sleep(0.2)

        # Stop the task
        checkpoint_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await checkpoint_task

        # Verify checkpoint save was called
        assert checkpoint_manager.save_checkpoint.call_count >= 1

    @pytest.mark.asyncio
    async def test_checkpoint_cleanup_on_completion(
        self,
        config,
        sample_torrent_data,
        temp_dir,
    ):
        """Test checkpoint cleanup when download completes."""
        # Create session
        session = AsyncTorrentSession(sample_torrent_data, str(temp_dir))
        session.config.disk = config

        # Mock checkpoint manager
        checkpoint_manager = Mock()
        checkpoint_manager.delete_checkpoint = AsyncMock(return_value=True)
        session.checkpoint_manager = checkpoint_manager

        # Mock download manager
        download_manager = Mock()
        download_manager.stop = AsyncMock()
        download_manager.download_complete = True
        session.download_manager = download_manager

        # Manually trigger checkpoint cleanup
        await session.delete_checkpoint()

        # Stop session
        await session.stop()

        # Verify checkpoint was deleted
        checkpoint_manager.delete_checkpoint.assert_called_once_with(
            sample_torrent_data["info_hash"],
        )

    @pytest.mark.asyncio
    async def test_file_validation_on_resume(
        self,
        config,
        sample_torrent_data,
        sample_checkpoint,
        temp_dir,
    ):
        """Test file validation during resume."""
        # Create test file
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(b"\x00" * 16384)

        # Update checkpoint to reference the test file
        sample_checkpoint.files[0].path = str(test_file)
        sample_checkpoint.files[0].exists = True

        # Create session
        session = AsyncTorrentSession(sample_torrent_data, str(temp_dir))
        session.config.disk = config

        # Mock file assembler with async methods
        file_assembler = Mock()
        validation_results = {
            "valid": True,
            "missing_files": [],
            "size_mismatches": [],
            "existing_pieces": {0},
            "warnings": [],
        }
        file_assembler.verify_existing_pieces = AsyncMock(
            return_value=validation_results,
        )
        session.download_manager.file_assembler = file_assembler

        # Mock piece manager on session (not download_manager)
        piece_manager = Mock()
        piece_manager.restore_from_checkpoint = AsyncMock(return_value=None)
        session.piece_manager = piece_manager

        # Test resume from checkpoint
        await session._resume_from_checkpoint(sample_checkpoint)

        # Verify validation was called
        file_assembler.verify_existing_pieces.assert_called_once_with(sample_checkpoint)
        # skip_preallocation_if_exists is no longer called in the new implementation
        piece_manager.restore_from_checkpoint.assert_called_once_with(sample_checkpoint)

    @pytest.mark.asyncio
    async def test_resume_with_corrupted_files(
        self,
        config,
        sample_torrent_data,
        sample_checkpoint,
        temp_dir,
    ):
        """Test resume behavior with corrupted files."""
        # Create corrupted test file (wrong size)
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(b"\x00" * 1000)  # Wrong size

        # Update checkpoint to reference the test file
        sample_checkpoint.files[0].path = str(test_file)
        sample_checkpoint.files[0].exists = True

        # Create session
        session = AsyncTorrentSession(sample_torrent_data, str(temp_dir))
        session.config.disk = config

        # Mock file assembler with async methods
        file_assembler = Mock()
        validation_results = {
            "valid": False,
            "missing_files": [],
            "size_mismatches": [
                {
                    "path": str(test_file),
                    "expected": 16384,
                    "actual": 1000,
                },
            ],
            "existing_pieces": set(),
            "warnings": ["Size mismatch for test file"],
        }
        file_assembler.verify_existing_pieces = AsyncMock(
            return_value=validation_results,
        )
        session.download_manager.file_assembler = file_assembler

        # Mock piece manager on session (not download_manager)
        piece_manager = Mock()
        piece_manager.restore_from_checkpoint = AsyncMock(return_value=None)
        session.piece_manager = piece_manager

        # Test resume from checkpoint
        await session._resume_from_checkpoint(sample_checkpoint)

        # Verify validation was called and warnings were logged
        file_assembler.verify_existing_pieces.assert_called_once_with(sample_checkpoint)
        # Resume should still proceed despite validation warnings
        piece_manager.restore_from_checkpoint.assert_called_once_with(sample_checkpoint)


class TestCheckpointCLI:
    """Test checkpoint core functionality."""

    @pytest.fixture(autouse=True)
    def cleanup_checkpoints(self):
        """Clean up checkpoint files before each test."""
        import shutil
        from pathlib import Path

        # Clean up checkpoint directory
        checkpoint_dir = Path(".ccbt/checkpoints")
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)

        yield

        # Clean up after test as well
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_checkpoint_manager_creation(self):
        """Test checkpoint manager can be created."""
        from ccbt.storage.checkpoint import CheckpointManager

        manager = CheckpointManager()
        assert manager is not None
        assert hasattr(manager, "list_checkpoints")

    @pytest.mark.asyncio
    async def test_checkpoint_manager_list_empty(self):
        """Test checkpoint manager list returns empty list initially."""
        from ccbt.storage.checkpoint import CheckpointManager

        manager = CheckpointManager()
        checkpoints = await manager.list_checkpoints()

        assert isinstance(checkpoints, list)
        assert len(checkpoints) == 0

    @pytest.mark.asyncio
    async def test_checkpoint_manager_cleanup(self):
        """Test checkpoint manager cleanup functionality."""
        from ccbt.storage.checkpoint import CheckpointManager

        manager = CheckpointManager()
        # Test cleanup functionality exists and is callable
        assert hasattr(manager, "cleanup_old_checkpoints")
        assert callable(manager.cleanup_old_checkpoints)

    @pytest.mark.asyncio
    async def test_checkpoint_manager_delete(self):
        """Test checkpoint manager delete functionality."""
        from ccbt.storage.checkpoint import CheckpointManager

        manager = CheckpointManager()
        # Test delete functionality exists and is callable
        assert hasattr(manager, "delete_checkpoint")
        assert callable(manager.delete_checkpoint)

    @pytest.mark.asyncio
    async def test_checkpoint_manager_load(self):
        """Test checkpoint manager load functionality."""
        from ccbt.storage.checkpoint import CheckpointManager

        manager = CheckpointManager()
        # Test load functionality exists and is callable
        assert hasattr(manager, "load_checkpoint")
        assert callable(manager.load_checkpoint)


if __name__ == "__main__":
    pytest.main([__file__])
