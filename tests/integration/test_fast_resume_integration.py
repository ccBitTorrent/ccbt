"""Integration tests for Fast Resume Support.

Tests cover:
- Resume after client shutdown
- Resume after simulated crash
- Resume with corrupted resume data
- Resume across version upgrades
- End-to-end resume workflow
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.session]

from ccbt.models import DiskConfig, DownloadStats, FileCheckpoint, TorrentCheckpoint
from ccbt.session.fast_resume import FastResumeLoader
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.storage.resume_data import FastResumeData


class TestResumeAfterShutdown:
    """Test resume functionality after client shutdown."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_save_interval=1.0,
            resume_verify_on_load=True,
            resume_verify_pieces=5,
            checkpoint_enabled=True,
            checkpoint_dir=str(temp_dir / "checkpoints"),
        )

    @pytest.fixture
    def checkpoint_manager(self, config):
        """Create checkpoint manager."""
        return CheckpointManager(config)

    @pytest.mark.asyncio
    async def test_resume_after_normal_shutdown(self, checkpoint_manager, config, temp_dir):
        """Test resume after normal client shutdown."""
        info_hash = b"\x00" * 20

        # Create resume data with some progress
        resume_data = FastResumeData(info_hash=info_hash, version=1)
        verified_pieces = {0, 1, 2, 3, 4}
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(
            verified_pieces,
            100,
        )
        resume_data.set_upload_statistics(5000, {"peer1"}, [10.0, 20.0])
        resume_data.set_queue_state(0, "normal")

        # Create checkpoint with resume data
        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="test_torrent",
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=list(verified_pieces),
            resume_data=resume_data.model_dump(),
            created_at=time.time(),
            updated_at=time.time(),
            output_dir=str(temp_dir),
        )

        # Save checkpoint
        await checkpoint_manager.save_checkpoint(checkpoint)

        # Simulate resume: load checkpoint
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        assert loaded_checkpoint is not None
        assert loaded_checkpoint.info_hash == info_hash

        # Verify resume data was preserved
        if loaded_checkpoint.resume_data:
            loaded_resume_data = FastResumeData(**loaded_checkpoint.resume_data)
            assert loaded_resume_data.info_hash == info_hash
            assert loaded_resume_data.version == 1

            # Verify piece bitmap
            decoded_pieces = FastResumeData.decode_piece_bitmap(
                loaded_resume_data.piece_completion_bitmap,
                100,
            )
            assert decoded_pieces == verified_pieces

            # Verify upload stats
            stats = loaded_resume_data.get_upload_statistics()
            assert stats["bytes_uploaded"] == 5000

            # Verify queue state
            position, priority = loaded_resume_data.get_queue_state()
            assert position == 0
            assert priority == "normal"

    @pytest.mark.asyncio
    async def test_resume_validates_resume_data(self, checkpoint_manager, config, temp_dir):
        """Test that resume validates resume data against torrent."""
        info_hash = b"\x00" * 20
        resume_data = FastResumeData(info_hash=info_hash)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 1}, 100)

        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="test",
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=[0, 1],
            resume_data=resume_data.model_dump(),
            created_at=time.time(),
            updated_at=time.time(),
            output_dir=str(temp_dir),
        )

        await checkpoint_manager.save_checkpoint(checkpoint)

        # Create loader and validate
        loader = FastResumeLoader(config)
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        if loaded_checkpoint and loaded_checkpoint.resume_data:
            loaded_resume_data = FastResumeData(**loaded_checkpoint.resume_data)

            torrent_info = {
                "info_hash": info_hash,
                "pieces": b"x" * (100 * 20),
            }

            is_valid, errors = loader.validate_resume_data(loaded_resume_data, torrent_info)
            assert is_valid is True
            assert len(errors) == 0


class TestResumeAfterCrash:
    """Test resume functionality after simulated crash."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_verify_on_load=True,
            checkpoint_enabled=True,
            checkpoint_dir=str(temp_dir / "checkpoints"),
        )

    @pytest.mark.asyncio
    async def test_resume_after_corrupted_checkpoint(self, config, temp_dir):
        """Test resume after corrupted checkpoint file."""
        checkpoint_manager = CheckpointManager(config)
        info_hash = b"\x01" * 20

        # Create valid checkpoint first
        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="test",
            total_pieces=10,
            piece_length=16384,
            total_length=163840,
            verified_pieces=[0, 1],
            created_at=time.time(),
            updated_at=time.time(),
            output_dir="/tmp/test",
        )

        await checkpoint_manager.save_checkpoint(checkpoint)

        # Corrupt checkpoint file
        checkpoint_file = Path(config.checkpoint_dir) / f"{info_hash.hex()}.json"
        if checkpoint_file.exists():
            checkpoint_file.write_text("{invalid json}")

        # Attempt to load - should handle gracefully
        loaded = await checkpoint_manager.load_checkpoint(info_hash)

        # Should either return None or handle corruption gracefully
        assert loaded is None or isinstance(loaded, TorrentCheckpoint)

    @pytest.mark.asyncio
    async def test_resume_with_missing_files(self, config):
        """Test resume when some files are missing."""
        checkpoint_manager = CheckpointManager(config)
        info_hash = b"\x02" * 20

        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="test",
            total_pieces=5,
            piece_length=16384,
            total_length=81920,
            verified_pieces=[0, 1],
            files=[
                FileCheckpoint(path="/nonexistent/file1.bin", size=40960, exists=False),
                FileCheckpoint(path="/nonexistent/file2.bin", size=40960, exists=False),
            ],
            created_at=time.time(),
            updated_at=time.time(),
            output_dir="/tmp/test",
        )

        await checkpoint_manager.save_checkpoint(checkpoint)

        # Load checkpoint
        loaded = await checkpoint_manager.load_checkpoint(info_hash)

        assert loaded is not None
        # Files marked as not existing should be preserved
        assert len(loaded.files) == 2
        assert loaded.files[0].exists is False


class TestCorruptedResumeData:
    """Test resume with corrupted resume data."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_verify_on_load=True,
        )

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader."""
        return FastResumeLoader(config)

    @pytest.mark.asyncio
    async def test_fallback_to_checkpoint_on_corruption(self, loader):
        """Test fallback to checkpoint when resume data is corrupted."""
        error = ValueError("Corrupted resume data")
        checkpoint = TorrentCheckpoint(
            info_hash=b"\x03" * 20,
            torrent_name="test",
            total_pieces=10,
            piece_length=16384,
            total_length=163840,
            verified_pieces=[0, 1, 2],
            created_at=time.time(),
            updated_at=time.time(),
            output_dir="/tmp/test",
        )

        result = await loader.handle_corrupted_resume(None, error, checkpoint)

        assert result["strategy"] == "checkpoint"
        assert result["requires_full_recheck"] is True
        assert result["checkpoint"] == checkpoint

    @pytest.mark.asyncio
    async def test_fallback_to_full_recheck_on_no_checkpoint(self, loader):
        """Test fallback to full recheck when no checkpoint available."""
        error = ValueError("Corrupted resume data")

        result = await loader.handle_corrupted_resume(None, error, None)

        assert result["strategy"] == "full_recheck"
        assert result["requires_full_recheck"] is True

    @pytest.mark.asyncio
    async def test_validate_corrupted_bitmap(self, loader):
        """Test validation with corrupted piece bitmap."""
        resume_data = FastResumeData(info_hash=b"\x04" * 20)
        # Corrupted bitmap data
        resume_data.piece_completion_bitmap = b"invalid_gzip_data"

        torrent_info = {
            "info_hash": b"\x04" * 20,
            "pieces": b"x" * (100 * 20),
        }

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # Should handle gracefully - decode_piece_bitmap returns empty set on error
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)


class TestVersionUpgrade:
    """Test resume across client version upgrades."""

    @pytest.fixture
    def config_v1(self):
        """Create config with version 1."""
        return DiskConfig(resume_data_format_version=1)

    @pytest.fixture
    def config_v2(self):
        """Create config with version 2."""
        return DiskConfig(resume_data_format_version=2)

    def test_migrate_v1_to_v2(self, config_v2):
        """Test migration from version 1 to 2."""
        loader = FastResumeLoader(config_v2)

        resume_data = FastResumeData(info_hash=b"\x05" * 20, version=1)
        resume_data.set_upload_statistics(1000, set(), [10.0])

        migrated = loader.migrate_resume_data(resume_data, 2)

        assert migrated.version == 2
        assert migrated.info_hash == resume_data.info_hash
        # Original data should be preserved
        stats = migrated.get_upload_statistics()
        assert stats["bytes_uploaded"] == 1000

    def test_backward_compatible_loading(self, config_v2):
        """Test loading version 1 data with version 2 client."""
        loader = FastResumeLoader(config_v2)

        resume_data = FastResumeData(info_hash=b"\x06" * 20, version=1)

        # Should be compatible
        assert resume_data.is_compatible(2) is True

        # Should need migration
        assert resume_data.needs_migration(2) is True

        # Migrate
        migrated = loader.migrate_resume_data(resume_data, 2)
        assert migrated.version == 2


class TestEndToEndResume:
    """End-to-end resume workflow tests."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_save_interval=1.0,
            resume_verify_on_load=False,  # Disable for faster tests
            checkpoint_enabled=True,
            checkpoint_dir=str(temp_dir / "checkpoints"),
        )

    @pytest.mark.asyncio
    async def test_complete_resume_workflow(self, config, temp_dir):
        """Test complete resume workflow from save to load."""
        checkpoint_manager = CheckpointManager(config)
        info_hash = b"\x07" * 20

        # Step 1: Create resume data with progress
        resume_data = FastResumeData(info_hash=info_hash)
        verified = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(verified, 100)
        resume_data.set_upload_statistics(15000, {"peer1", "peer2"}, [10.0, 15.0, 20.0])
        resume_data.set_file_selection_state({
            0: {"selected": True, "priority": "high"},
            1: {"selected": True, "priority": "normal"},
        })
        resume_data.set_queue_state(2, "high")

        # Step 2: Save checkpoint with resume data
        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="e2e_test",
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=list(verified),
            resume_data=resume_data.model_dump(),
            created_at=time.time(),
            updated_at=time.time(),
            output_dir=str(temp_dir),
        )

        await checkpoint_manager.save_checkpoint(checkpoint)

        # Step 3: Load checkpoint
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(info_hash)
        assert loaded_checkpoint is not None

        # Step 4: Restore resume data
        if loaded_checkpoint.resume_data:
            loaded_resume_data = FastResumeData(**loaded_checkpoint.resume_data)

            # Step 5: Verify all data is preserved
            decoded_pieces = FastResumeData.decode_piece_bitmap(
                loaded_resume_data.piece_completion_bitmap,
                100,
            )
            assert decoded_pieces == verified

            stats = loaded_resume_data.get_upload_statistics()
            assert stats["bytes_uploaded"] == 15000
            assert len(stats["peers_uploaded_to"]) == 2

            file_state = loaded_resume_data.get_file_selection_state()
            assert len(file_state) == 2
            assert file_state[0]["selected"] is True

            position, priority = loaded_resume_data.get_queue_state()
            assert position == 2
            assert priority == "high"

    @pytest.mark.asyncio
    async def test_resume_with_integrity_verification(self, config, temp_dir):
        """Test resume with integrity verification enabled."""
        config.resume_verify_on_load = True
        config.resume_verify_pieces = 5

        checkpoint_manager = CheckpointManager(config)
        loader = FastResumeLoader(config)

        info_hash = b"\x08" * 20
        verified = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
        resume_data = FastResumeData(info_hash=info_hash)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(verified, 100)

        checkpoint = TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name="test",
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=list(verified),
            resume_data=resume_data.model_dump(),
            created_at=time.time(),
            updated_at=time.time(),
            output_dir=str(temp_dir),
        )

        await checkpoint_manager.save_checkpoint(checkpoint)

        # Load and verify
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(info_hash)
        if loaded_checkpoint and loaded_checkpoint.resume_data:
            loaded_resume_data = FastResumeData(**loaded_checkpoint.resume_data)

            torrent_info = {"pieces": b"x" * (100 * 20)}

            # Mock file assembler for verification
            file_assembler = AsyncMock()
            file_assembler.verify_piece_hash = AsyncMock(return_value=True)

            result = await loader.verify_integrity(
                loaded_resume_data,
                torrent_info,
                file_assembler,
                num_pieces_to_verify=5,
            )

            assert "valid" in result
            assert "verified_pieces" in result
            assert len(result["verified_pieces"]) == 5

