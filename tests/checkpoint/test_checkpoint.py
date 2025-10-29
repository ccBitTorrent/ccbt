"""Tests for checkpoint functionality.

Tests checkpoint save/load, resume validation, and CLI commands.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.checkpoint]

from ccbt.checkpoint import CheckpointFileInfo, CheckpointManager
from ccbt.exceptions import CheckpointError
from ccbt.models import (
    CheckpointFormat,
    DiskConfig,
    DownloadStats,
    FileCheckpoint,
    PieceState,
    TorrentCheckpoint,
)


class TestCheckpointManager:
    """Test CheckpointManager functionality."""

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
            checkpoint_format=CheckpointFormat.BOTH,
            checkpoint_dir=str(temp_dir),
            checkpoint_interval=1.0,
            checkpoint_on_piece=True,
            auto_resume=True,
            checkpoint_compression=True,
        )

    @pytest.fixture
    def checkpoint_manager(self, config):
        """Create CheckpointManager instance."""
        return CheckpointManager(config)

    @pytest.fixture
    def sample_checkpoint(self):
        """Create sample checkpoint data."""
        return TorrentCheckpoint(
            info_hash=b"\x00" * 20,
            torrent_name="test_torrent",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=[0, 1, 2, 5, 10],
            piece_states={0: PieceState.VERIFIED, 1: PieceState.VERIFIED},
            download_stats=DownloadStats(
                bytes_downloaded=81920,
                download_time=60.0,
                average_speed=1365.33,
                start_time=time.time() - 60,
                last_update=time.time(),
            ),
            output_dir="/tmp/test",
            files=[
                FileCheckpoint(path="/tmp/test/file.bin", size=1638400, exists=True),
            ],
            peer_info={"peer_count": 5},
            endgame_mode=False,
        )

    @pytest.mark.asyncio
    async def test_save_json_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test saving checkpoint in JSON format."""
        path = await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        assert path.exists()
        assert path.suffix == ".json"

        # Verify JSON content
        with open(path) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert data["info_hash"] == sample_checkpoint.info_hash.hex()
        assert data["torrent_name"] == sample_checkpoint.torrent_name
        assert data["total_pieces"] == sample_checkpoint.total_pieces
        assert data["verified_pieces"] == sample_checkpoint.verified_pieces

    @pytest.mark.asyncio
    async def test_load_json_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test loading checkpoint from JSON format."""
        # Save checkpoint first
        await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        # Load checkpoint
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(
            sample_checkpoint.info_hash,
            CheckpointFormat.JSON,
        )

        assert loaded_checkpoint is not None
        assert loaded_checkpoint.info_hash == sample_checkpoint.info_hash
        assert loaded_checkpoint.torrent_name == sample_checkpoint.torrent_name
        assert loaded_checkpoint.total_pieces == sample_checkpoint.total_pieces
        assert loaded_checkpoint.verified_pieces == sample_checkpoint.verified_pieces

    @pytest.mark.asyncio
    async def test_save_binary_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test saving checkpoint in binary format."""
        try:
            path = await checkpoint_manager.save_checkpoint(
                sample_checkpoint,
                CheckpointFormat.BINARY,
            )

            assert path.exists()
            assert path.suffix in [".bin", ".gz"]

            # Verify binary content starts with magic bytes
            with open(path, "rb") as f:
                if path.suffix == ".gz":
                    import gzip

                    with gzip.open(path, "rb") as gz:
                        magic = gz.read(4)
                else:
                    magic = f.read(4)

            assert magic == b"CCBT"
        except CheckpointError as e:
            if "msgpack is required" in str(e):
                pytest.skip("msgpack not available for binary checkpoint format")
            else:
                raise

    @pytest.mark.asyncio
    async def test_load_binary_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test loading checkpoint from binary format."""
        try:
            # Save checkpoint first
            await checkpoint_manager.save_checkpoint(
                sample_checkpoint,
                CheckpointFormat.BINARY,
            )

            # Load checkpoint
            loaded_checkpoint = await checkpoint_manager.load_checkpoint(
                sample_checkpoint.info_hash,
                CheckpointFormat.BINARY,
            )

            assert loaded_checkpoint is not None
            assert loaded_checkpoint.info_hash == sample_checkpoint.info_hash
            assert loaded_checkpoint.torrent_name == sample_checkpoint.torrent_name
            assert loaded_checkpoint.total_pieces == sample_checkpoint.total_pieces
            assert (
                loaded_checkpoint.verified_pieces == sample_checkpoint.verified_pieces
            )
        except CheckpointError as e:
            if "msgpack is required" in str(e):
                pytest.skip("msgpack not available for binary checkpoint format")
            else:
                raise

    @pytest.mark.asyncio
    async def test_save_both_formats(self, checkpoint_manager, sample_checkpoint):
        """Test saving checkpoint in both formats."""
        try:
            path = await checkpoint_manager.save_checkpoint(
                sample_checkpoint,
                CheckpointFormat.BOTH,
            )

            # Should return JSON path
            assert path.suffix == ".json"

            # Both files should exist
            json_path = path
            bin_path = path.with_suffix(".bin.gz")

            assert json_path.exists()
            assert bin_path.exists()
        except CheckpointError as e:
            if "msgpack is required" in str(e):
                pytest.skip("msgpack not available for binary checkpoint format")
            else:
                raise

    @pytest.mark.asyncio
    async def test_load_checkpoint_not_found(self, checkpoint_manager):
        """Test loading non-existent checkpoint."""
        info_hash = b"\xff" * 20
        checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test deleting checkpoint."""
        try:
            # Save checkpoint in both formats
            await checkpoint_manager.save_checkpoint(
                sample_checkpoint,
                CheckpointFormat.BOTH,
            )

            # Delete checkpoint
            deleted = await checkpoint_manager.delete_checkpoint(
                sample_checkpoint.info_hash,
            )

            assert deleted is True

            # Verify files are deleted
            json_path = checkpoint_manager._get_checkpoint_path(
                sample_checkpoint.info_hash,
                CheckpointFormat.JSON,
            )
            bin_path = checkpoint_manager._get_checkpoint_path(
                sample_checkpoint.info_hash,
                CheckpointFormat.BINARY,
            )

            assert not json_path.exists()
            assert not bin_path.exists()
        except CheckpointError as e:
            if "msgpack is required" in str(e):
                pytest.skip("msgpack not available for binary checkpoint format")
            else:
                raise

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, checkpoint_manager, sample_checkpoint):
        """Test listing checkpoints."""
        # Save checkpoint
        await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        # List checkpoints
        checkpoints = await checkpoint_manager.list_checkpoints()

        assert len(checkpoints) == 1
        assert isinstance(checkpoints[0], CheckpointFileInfo)
        assert checkpoints[0].info_hash == sample_checkpoint.info_hash
        assert checkpoints[0].checkpoint_format == CheckpointFormat.JSON

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self, checkpoint_manager, sample_checkpoint):
        """Test cleaning up old checkpoints."""
        # Save checkpoint
        await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        # Mock old timestamp
        old_time = time.time() - (31 * 24 * 60 * 60)  # 31 days ago

        # Modify file timestamp
        json_path = checkpoint_manager._get_checkpoint_path(
            sample_checkpoint.info_hash,
            CheckpointFormat.JSON,
        )
        os.utime(json_path, (old_time, old_time))

        # Cleanup checkpoints older than 30 days
        deleted_count = await checkpoint_manager.cleanup_old_checkpoints(30)

        assert deleted_count == 1
        assert not json_path.exists()

    @pytest.mark.asyncio
    async def test_checkpoint_stats(self, checkpoint_manager, sample_checkpoint):
        """Test checkpoint statistics."""
        # Save checkpoint
        await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        # Get stats
        stats = checkpoint_manager.get_checkpoint_stats()

        assert stats["total_files"] == 1
        assert stats["json_files"] == 1
        assert stats["binary_files"] == 0
        assert stats["total_size"] > 0
        assert stats["oldest_checkpoint"] is not None
        assert stats["newest_checkpoint"] is not None

    @pytest.mark.asyncio
    async def test_corrupted_json_checkpoint(self, checkpoint_manager, temp_dir):
        """Test handling corrupted JSON checkpoint."""
        # Create corrupted JSON file
        info_hash = b"\x00" * 20
        json_path = checkpoint_manager._get_checkpoint_path(
            info_hash,
            CheckpointFormat.JSON,
        )

        with open(json_path, "w") as f:
            f.write('{"invalid": json}')  # Invalid JSON

        # Try to load corrupted checkpoint
        with pytest.raises(CheckpointError):
            await checkpoint_manager.load_checkpoint(info_hash, CheckpointFormat.JSON)

    @pytest.mark.asyncio
    async def test_version_mismatch(self, checkpoint_manager, sample_checkpoint):
        """Test handling version mismatch."""
        # Save checkpoint
        await checkpoint_manager.save_checkpoint(
            sample_checkpoint,
            CheckpointFormat.JSON,
        )

        # Modify version in JSON file
        json_path = checkpoint_manager._get_checkpoint_path(
            sample_checkpoint.info_hash,
            CheckpointFormat.JSON,
        )

        with open(json_path) as f:
            data = json.load(f)

        data["version"] = "2.0"  # Incompatible version

        with open(json_path, "w") as f:
            json.dump(data, f)

        # Try to load checkpoint with wrong version
        with pytest.raises(CheckpointError):
            await checkpoint_manager.load_checkpoint(
                sample_checkpoint.info_hash,
                CheckpointFormat.JSON,
            )

    @pytest.mark.asyncio
    async def test_disabled_checkpointing(self, temp_dir):
        """Test behavior when checkpointing is disabled."""
        config = DiskConfig(
            checkpoint_enabled=False,
            checkpoint_dir=str(temp_dir),
        )
        checkpoint_manager = CheckpointManager(config)

        sample_checkpoint = TorrentCheckpoint(
            info_hash=b"\x00" * 20,
            torrent_name="test",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=10,
            piece_length=16384,
            total_length=163840,
            output_dir=tempfile.gettempdir(),
        )

        # Should raise error when trying to save
        with pytest.raises(CheckpointError):
            await checkpoint_manager.save_checkpoint(sample_checkpoint)

        # Should return None when trying to load
        checkpoint = await checkpoint_manager.load_checkpoint(
            sample_checkpoint.info_hash,
        )
        assert checkpoint is None


class TestCheckpointIntegration:
    """Test checkpoint integration with other components."""

    @pytest.mark.asyncio
    async def test_piece_manager_checkpoint_state(self):
        """Test piece manager checkpoint state generation."""
        from ccbt.async_piece_manager import AsyncPieceManager

        # Mock torrent data
        torrent_data = {
            "pieces_info": {
                "num_pieces": 10,
                "piece_length": 16384,
                "piece_hashes": [b"\x00" * 20] * 10,
            },
            "file_info": {
                "total_length": 163840,
            },
        }

        piece_manager = AsyncPieceManager(torrent_data)

        # Mock some verified pieces
        piece_manager.verified_pieces = {0, 1, 2}
        piece_manager.bytes_downloaded = 49152

        # Get checkpoint state
        checkpoint = await piece_manager.get_checkpoint_state(
            "test_torrent",
            b"\x00" * 20,
            tempfile.gettempdir(),
        )

        assert checkpoint.torrent_name == "test_torrent"
        assert checkpoint.total_pieces == 10
        assert checkpoint.verified_pieces == [0, 1, 2]
        assert checkpoint.download_stats.bytes_downloaded == 49152

    @pytest.mark.asyncio
    async def test_file_assembler_resume_validation(self):
        """Test file assembler resume validation."""
        from ccbt.file_assembler import AsyncFileAssembler

        # Mock torrent data
        torrent_data = {
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

        # Mock DiskIOManager to avoid ThreadPoolExecutor issues
        with patch("ccbt.file_assembler.DiskIOManager") as mock_disk_io:
            mock_disk_io.return_value = Mock()

            file_assembler = AsyncFileAssembler(torrent_data, tempfile.gettempdir())

            # Create test checkpoint
            checkpoint = TorrentCheckpoint(
                info_hash=b"\x00" * 20,
                torrent_name="test",
                created_at=time.time(),
                updated_at=time.time(),
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[0],
                output_dir=tempfile.gettempdir(),
                files=[
                    FileCheckpoint(path="/tmp/test.bin", size=16384, exists=True),
                ],
            )

            # Test validation (file doesn't exist, so should fail)
            validation_results = await file_assembler.verify_existing_pieces(checkpoint)

            assert not validation_results["valid"]
            assert len(validation_results["missing_files"]) == 1


if __name__ == "__main__":
    pytest.main([__file__])
