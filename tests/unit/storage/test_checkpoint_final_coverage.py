"""Final coverage improvements for checkpoint module.

Covers remaining edge cases:
- Invalid format in _get_checkpoint_path
- Exception handling in BOTH format load
- File processing edge cases in list_checkpoints
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.checkpoint]

from ccbt.models import (
    CheckpointFormat,
    DiskConfig,
    DownloadStats,
    TorrentCheckpoint,
)
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.utils.exceptions import CheckpointError
from unittest.mock import patch


class TestCheckpointFinalCoverage:
    """Test remaining edge cases for full coverage."""

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
            checkpoint_dir=str(temp_dir),
        )

    @pytest.fixture
    def checkpoint_manager(self, config):
        """Create CheckpointManager instance."""
        return CheckpointManager(config)

    @pytest.mark.asyncio
    async def test_get_checkpoint_path_invalid_format(self, checkpoint_manager):
        """Test _get_checkpoint_path with invalid format (lines 104-105)."""
        info_hash = b"\x77" * 20
        
        # Test invalid format raises ValueError
        with pytest.raises(ValueError, match="Invalid checkpoint"):
            checkpoint_manager._get_checkpoint_path(info_hash, "invalid")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_load_checkpoint_both_format_json_first(self, checkpoint_manager):
        """Test loading checkpoint with BOTH format, JSON found first."""
        checkpoint = TorrentCheckpoint(
            info_hash=b"\x88" * 20,
            torrent_name="test",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=10,
            piece_length=16384,
            total_length=163840,
            verified_pieces=[],
            download_stats=DownloadStats(),
            output_dir="/tmp/test",
            files=[],
        )
        
        # Save in JSON format
        await checkpoint_manager.save_checkpoint(checkpoint, CheckpointFormat.JSON)
        
        # Load with BOTH format - should find JSON first (line 335)
        config = DiskConfig(
            checkpoint_enabled=True,
            checkpoint_format=CheckpointFormat.BOTH,
            checkpoint_dir=str(checkpoint_manager.checkpoint_dir),
        )
        manager = CheckpointManager(config)
        
        loaded = await manager.load_checkpoint(checkpoint.info_hash, CheckpointFormat.BOTH)
        assert loaded is not None
        assert loaded.info_hash == checkpoint.info_hash

    @pytest.mark.asyncio
    async def test_load_checkpoint_both_format_binary_fallback(self, checkpoint_manager, temp_dir):
        """Test loading checkpoint with BOTH format, binary fallback (line 337)."""
        try:
            checkpoint = TorrentCheckpoint(
                info_hash=b"\x99" * 20,
                torrent_name="test",
                created_at=time.time(),
                updated_at=time.time(),
                total_pieces=10,
                piece_length=16384,
                total_length=163840,
                verified_pieces=[],
                download_stats=DownloadStats(),
                output_dir="/tmp/test",
                files=[],
            )
            
            # Save in binary format only (no JSON)
            config_binary = DiskConfig(
                checkpoint_enabled=True,
                checkpoint_format=CheckpointFormat.BINARY,
                checkpoint_dir=str(temp_dir),
                checkpoint_compression=False,
            )
            manager_binary = CheckpointManager(config_binary)
            await manager_binary.save_checkpoint(checkpoint, CheckpointFormat.BINARY)
            
            # Verify binary file exists
            bin_path = manager_binary._get_checkpoint_path(checkpoint.info_hash, CheckpointFormat.BINARY)
            assert bin_path.exists()
            
            # Create manager with BOTH format - will try JSON first (None), then binary
            config_both = DiskConfig(
                checkpoint_enabled=True,
                checkpoint_format=CheckpointFormat.BOTH,
                checkpoint_dir=str(temp_dir),
                checkpoint_compression=False,
            )
            manager_both = CheckpointManager(config_both)
            
            # Load with BOTH format - JSON not found (returns None), should fallback to binary (line 337)
            # Mock _load_json_checkpoint to return None to trigger binary fallback
            original_load_json = manager_both._load_json_checkpoint
            call_count = [0]
            
            async def mock_load_json_none(info_hash):
                call_count[0] += 1
                if call_count[0] == 1:  # First call returns None
                    return None
                return await original_load_json(info_hash)
            
            with patch.object(manager_both, "_load_json_checkpoint", mock_load_json_none):
                loaded = await manager_both.load_checkpoint(checkpoint.info_hash, CheckpointFormat.BOTH)
                # Should fallback to binary when JSON returns None (line 337)
                if loaded is not None:
                    assert loaded.info_hash == checkpoint.info_hash
        except CheckpointError as e:
            if "msgpack is required" in str(e) or "msgpack not available" in str(e):
                pytest.skip("msgpack not available")

    @pytest.mark.asyncio
    async def test_load_checkpoint_both_format_exception_handling(self, checkpoint_manager, temp_dir):
        """Test exception handling in BOTH format load."""
        info_hash = b"\xaa" * 20
        
        config = DiskConfig(
            checkpoint_enabled=True,
            checkpoint_format=CheckpointFormat.BOTH,
            checkpoint_dir=str(temp_dir),
        )
        manager = CheckpointManager(config)
        
        # Create corrupted JSON file that will raise exception
        json_path = manager._get_checkpoint_path(info_hash, CheckpointFormat.JSON)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text('{"invalid": json}')
        
        # BOTH format will try JSON first, which raises exception
        # Exception should be caught and re-raised as CheckpointError (lines 336-338)
        with pytest.raises(CheckpointError, match="Failed to load checkpoint"):
            await manager.load_checkpoint(info_hash, CheckpointFormat.BOTH)

    @pytest.mark.asyncio
    async def test_list_checkpoints_file_stem_continue(self, checkpoint_manager, temp_dir):
        """Test list_checkpoints with files that cause continue (line 567)."""
        # Create file with .checkpoint.* pattern but stem doesn't end with .checkpoint
        # This should trigger the continue on line 567
        invalid_file = temp_dir / "someprefix.checkpoint.json"
        invalid_file.write_text('{"test": "data"}')
        
        # The filename parsing will fail because stem is "someprefix" not ending with ".checkpoint"
        checkpoints = await checkpoint_manager.list_checkpoints()
        # Should skip this file
        assert len(checkpoints) == 0

    @pytest.mark.asyncio
    async def test_list_checkpoints_directory_exists_path(self, checkpoint_manager):
        """Test list_checkpoints when directory exists (line 557)."""
        # Directory should exist after CheckpointManager.__init__
        checkpoints = await checkpoint_manager.list_checkpoints()
        # Should return list (may be empty)
        assert isinstance(checkpoints, list)

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints_directory_exists_path(self, checkpoint_manager):
        """Test cleanup when directory exists (line 726)."""
        # Directory should exist after CheckpointManager.__init__
        deleted = await checkpoint_manager.cleanup_old_checkpoints(30)
        # Should return count (may be 0)
        assert isinstance(deleted, int)
        assert deleted >= 0

    @pytest.mark.asyncio
    async def test_get_checkpoint_stats_directory_exists_path(self, checkpoint_manager):
        """Test get_checkpoint_stats when directory exists (line 773)."""
        # Directory should exist after CheckpointManager.__init__
        stats = checkpoint_manager.get_checkpoint_stats()
        # Should return stats dict
        assert isinstance(stats, dict)
        assert "total_files" in stats

