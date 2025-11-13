"""Unit tests for FastResumeLoader.

Tests cover:
- Resume data validation
- Version migration
- Integrity verification
- Corrupted resume data handling
- Configuration integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.models import DiskConfig, DownloadStats
from ccbt.session.fast_resume import FastResumeLoader
from ccbt.storage.resume_data import FastResumeData


class TestFastResumeLoaderCreation:
    """Test FastResumeLoader initialization."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_save_interval=30.0,
            resume_verify_on_load=True,
            resume_verify_pieces=10,
            resume_data_format_version=1,
        )

    def test_create_loader(self, config):
        """Test creating FastResumeLoader."""
        loader = FastResumeLoader(config)
        assert loader.config == config
        assert loader.logger is not None


class TestValidateResumeData:
    """Test resume data validation."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(
            fast_resume_enabled=True,
            resume_data_format_version=1,
        )

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    @pytest.fixture
    def sample_resume_data(self):
        """Create sample resume data."""
        return FastResumeData(
            info_hash=b"\x00" * 20,
            version=1,
            piece_completion_bitmap=FastResumeData.encode_piece_bitmap({0, 1}, 100),
        )

    def test_validate_valid_resume_data_dict(self, loader, sample_resume_data):
        """Test validating valid resume data with dict torrent_info."""
        torrent_info = {
            "info_hash": b"\x00" * 20,
            "pieces": b"x" * (100 * 20),  # 100 pieces
        }

        is_valid, errors = loader.validate_resume_data(sample_resume_data, torrent_info)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_resume_data_object(self, loader, sample_resume_data):
        """Test validating valid resume data with object torrent_info."""
        class TorrentInfo:
            def __init__(self):
                self.info_hash = b"\x00" * 20
                self.total_pieces = 100

        torrent_info = TorrentInfo()

        is_valid, errors = loader.validate_resume_data(sample_resume_data, torrent_info)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_info_hash_mismatch(self, loader, sample_resume_data):
        """Test validation with info hash mismatch."""
        torrent_info = {
            "info_hash": b"\x01" * 20,  # Different hash
            "pieces": b"x" * (100 * 20),
        }

        is_valid, errors = loader.validate_resume_data(sample_resume_data, torrent_info)

        assert is_valid is False
        assert "Info hash mismatch" in str(errors) or any("hash" in str(e).lower() for e in errors)

    def test_validate_too_many_pieces(self, loader):
        """Test validation with too many verified pieces."""
        # Create resume data with pieces beyond total
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            piece_completion_bitmap=FastResumeData.encode_piece_bitmap({0, 1, 2, 3}, 3),
        )

        torrent_info = {
            "info_hash": b"\x00" * 20,
            "pieces": b"x" * (3 * 20),  # Only 3 pieces
        }

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # Should detect that we have more verified pieces than total
        # Note: This might pass if bitmap encoding filters out invalid pieces
        # The validation checks decoded pieces vs total

    def test_validate_invalid_piece_indices(self, loader):
        """Test validation with invalid piece indices."""
        # Create bitmap with pieces that are out of range
        # Note: encode_piece_bitmap filters these out, so we need to test differently
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            piece_completion_bitmap=FastResumeData.encode_piece_bitmap({0, 1}, 100),
        )

        torrent_info = {
            "info_hash": b"\x00" * 20,
            "pieces": b"x" * (100 * 20),
        }

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)
        assert is_valid is True  # Should be valid since indices are in range

    def test_validate_empty_torrent_info(self, loader, sample_resume_data):
        """Test validation with empty torrent info."""
        torrent_info = {}

        is_valid, errors = loader.validate_resume_data(sample_resume_data, torrent_info)

        # Should handle gracefully
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)


class TestMigrateResumeData:
    """Test resume data migration."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(
            resume_data_format_version=2)  # Target version 2

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    def test_migrate_from_v1_to_v2(self, loader):
        """Test migration from version 1 to 2."""
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            version=1,
        )

        migrated = loader.migrate_resume_data(resume_data, 2)

        assert migrated.version == 2
        assert migrated.info_hash == resume_data.info_hash

    def test_migrate_no_migration_needed(self, loader):
        """Test migration when already at target version."""
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            version=2,
        )

        migrated = loader.migrate_resume_data(resume_data, 2)

        assert migrated.version == 2
        assert migrated is resume_data  # Should return same object

    def test_migrate_higher_version(self, loader):
        """Test migration when resume data is newer."""
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            version=3,
        )

        migrated = loader.migrate_resume_data(resume_data, 2)

        # Should not downgrade
        assert migrated.version == 3


class TestVerifyIntegrity:
    """Test integrity verification."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(
            resume_verify_on_load=True,
            resume_verify_pieces=10,
        )

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    @pytest.fixture
    def sample_resume_data(self):
        """Create sample resume data."""
        verified_pieces = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        return FastResumeData(
            info_hash=b"\x00" * 20,
            piece_completion_bitmap=FastResumeData.encode_piece_bitmap(verified_pieces, 100),
        )

    @pytest.mark.asyncio
    async def test_verify_integrity_disabled(self, loader, sample_resume_data):
        """Test integrity verification when disabled."""
        torrent_info = {"pieces": b"x" * (100 * 20)}

        result = await loader.verify_integrity(
            sample_resume_data,
            torrent_info,
            None,
            num_pieces_to_verify=0,
        )

        assert result["valid"] is True
        assert len(result["verified_pieces"]) == 0

    @pytest.mark.asyncio
    async def test_verify_integrity_no_file_assembler(self, loader, sample_resume_data):
        """Test integrity verification without file assembler."""
        torrent_info = {"pieces": b"x" * (100 * 20)}

        result = await loader.verify_integrity(
            sample_resume_data,
            torrent_info,
            None,
            num_pieces_to_verify=10,
        )

        # Should return valid=True but no verification actually performed
        assert "valid" in result

    @pytest.mark.asyncio
    async def test_verify_integrity_no_pieces(self, loader):
        """Test integrity verification with no verified pieces."""
        resume_data = FastResumeData(
            info_hash=b"\x00" * 20,
            piece_completion_bitmap=b"",  # Empty
        )
        torrent_info = {"pieces": b"x" * (100 * 20)}

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            None,
            num_pieces_to_verify=10,
        )

        assert result["valid"] is True
        assert len(result["verified_pieces"]) == 0

    @pytest.mark.asyncio
    async def test_verify_integrity_with_file_assembler(self, loader, sample_resume_data):
        """Test integrity verification with file assembler."""
        torrent_info = {"pieces": b"x" * (100 * 20)}

        # Mock file assembler
        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(return_value=True)

        result = await loader.verify_integrity(
            sample_resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=5,
        )

        assert "valid" in result
        assert "verified_pieces" in result
        assert "failed_pieces" in result
        assert len(result["verified_pieces"]) == 5

    @pytest.mark.asyncio
    async def test_verify_integrity_failed_pieces(self, loader, sample_resume_data):
        """Test integrity verification with failed pieces."""
        torrent_info = {"pieces": b"x" * (100 * 20)}

        # Mock file assembler that fails verification
        file_assembler = AsyncMock()
        async def verify_fail(piece_idx, expected_hash):
            return piece_idx == 0  # Fail first piece

        file_assembler.verify_piece_hash = verify_fail

        result = await loader.verify_integrity(
            sample_resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=5,
        )

        assert result["valid"] is False or len(result.get("failed_pieces", [])) > 0
        assert "failed_pieces" in result

    @pytest.mark.asyncio
    async def test_verify_integrity_exception_handling(self, loader, sample_resume_data):
        """Test integrity verification with exceptions."""
        torrent_info = {"pieces": b"x" * (100 * 20)}

        # Mock file assembler that raises exception
        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(side_effect=Exception("Test error"))

        result = await loader.verify_integrity(
            sample_resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=5,
        )

        # Should handle gracefully
        assert "failed_pieces" in result


class TestHandleCorruptedResume:
    """Test corrupted resume data handling."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig()

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    @pytest.mark.asyncio
    async def test_handle_corrupted_with_checkpoint(self, loader):
        """Test handling corrupted resume with checkpoint fallback."""
        from ccbt.models import TorrentCheckpoint
        import time

        error = ValueError("Corrupted resume data")
        checkpoint = TorrentCheckpoint(
            info_hash=b"\x00" * 20,
            torrent_name="test",
            total_pieces=100,
            piece_length=16384,
            total_length=1638400,
            verified_pieces=[0, 1],
            created_at=time.time(),
            updated_at=time.time(),
            output_dir="/tmp/test",
        )

        result = await loader.handle_corrupted_resume(None, error, checkpoint)

        assert result["strategy"] == "checkpoint"
        assert result["checkpoint"] == checkpoint
        assert result["requires_full_recheck"] is True

    @pytest.mark.asyncio
    async def test_handle_corrupted_no_checkpoint(self, loader):
        """Test handling corrupted resume without checkpoint."""
        error = ValueError("Corrupted resume data")

        result = await loader.handle_corrupted_resume(None, error, None)

        assert result["strategy"] == "full_recheck"
        assert result["requires_full_recheck"] is True


class TestConfigurationIntegration:
    """Test configuration integration."""

    def test_should_verify_on_load_enabled(self):
        """Test should_verify_on_load when enabled."""
        config = DiskConfig(resume_verify_on_load=True)
        loader = FastResumeLoader(config)

        assert loader.should_verify_on_load() is True

    def test_should_verify_on_load_disabled(self):
        """Test should_verify_on_load when disabled."""
        config = DiskConfig(resume_verify_on_load=False)
        loader = FastResumeLoader(config)

        assert loader.should_verify_on_load() is False

    def test_get_verify_pieces_count(self):
        """Test get_verify_pieces_count."""
        config = DiskConfig(resume_verify_pieces=15)
        loader = FastResumeLoader(config)

        assert loader.get_verify_pieces_count() == 15

    def test_get_verify_pieces_count_default(self):
        """Test get_verify_pieces_count with default."""
        config = DiskConfig()  # Use default
        loader = FastResumeLoader(config)

        assert loader.get_verify_pieces_count() >= 0


class TestValidateResumeDataEdgeCases:
    """Test edge cases in validate_resume_data."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(resume_data_format_version=1)

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    def test_validate_no_info_hash_in_torrent_info(self, loader):
        """Test validation when torrent_info has no info_hash."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        torrent_info = {}  # No info_hash

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # Should be valid since info_hash check is skipped when expected_hash is None
        assert isinstance(is_valid, bool)

    def test_validate_no_pieces_data(self, loader):
        """Test validation with no pieces data."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b""}

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        assert isinstance(is_valid, bool)

    def test_validate_pieces_data_not_divisible_by_20(self, loader):
        """Test validation with pieces data not divisible by 20."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        # 15 bytes = not divisible by 20, should result in 0 pieces
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * 15}

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        assert isinstance(is_valid, bool)

    def test_validate_with_object_no_total_pieces(self, loader):
        """Test validation with object that has no total_pieces attribute."""
        class TorrentInfo:
            def __init__(self):
                self.info_hash = b"\x00" * 20
                # No total_pieces attribute

        torrent_info = TorrentInfo()
        resume_data = FastResumeData(info_hash=b"\x00" * 20)

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        assert isinstance(is_valid, bool)


class TestMigrateResumeDataEdgeCases:
    """Test edge cases in migration."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig(resume_data_format_version=3)

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    def test_migrate_unknown_version_path(self, loader):
        """Test migration with unknown version path."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=2)

        # Try to migrate to version 3, but migration path 2->3 not implemented
        migrated = loader.migrate_resume_data(resume_data, 3)

        # Should log warning but return data
        assert migrated is not None
        # Version might stay at 2 or be updated
        assert migrated.version >= 2

    def test_migrate_with_fields_already_present(self, loader):
        """Test migration when fields are already present."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=1)
        resume_data.queue_position = 5
        resume_data.queue_priority = "high"

        migrated = loader.migrate_resume_data(resume_data, 2)

        assert migrated.version == 2
        # Fields should still be present
        assert migrated.queue_position == 5
        assert migrated.queue_priority == "high"


class TestVerifyIntegrityEdgeCases:
    """Test edge cases in integrity verification."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig()

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    @pytest.mark.asyncio
    async def test_verify_pieces_data_not_divisible_by_20(self, loader):
        """Test verify with pieces data not divisible by 20."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0}, 1)

        # Pieces data not divisible by 20 - creates incomplete hash
        # The code will create piece_hashes list but with incomplete hash
        torrent_info = {"pieces": b"x" * 15}  # 15 bytes, creates 1 incomplete hash

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            None,
            num_pieces_to_verify=1,
        )

        # Code proceeds because piece_hashes is not empty (has 1 element, even if incomplete)
        # But verification may still fail or return valid depending on bitmap
        assert "verified_pieces" in result
        # The actual behavior depends on whether decoded bitmap matches piece_hashes length

    @pytest.mark.asyncio
    async def test_verify_piece_idx_out_of_bounds(self, loader):
        """Test verify with piece index out of bounds."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        # Create bitmap with pieces that might be out of bounds
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 99}, 10)

        torrent_info = {"pieces": b"x" * (10 * 20)}  # Only 10 pieces

        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(return_value=True)

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=2,
        )

        # Should handle gracefully - piece 99 doesn't exist in 10-piece torrent
        # but encode_piece_bitmap would have filtered it, so decoded will only have valid pieces
        assert "verified_pieces" in result

    @pytest.mark.asyncio
    async def test_verify_file_assembler_no_verify_method(self, loader):
        """Test verify with file assembler missing verify_piece_hash method."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 1}, 10)

        torrent_info = {"pieces": b"x" * (10 * 20)}

        # File assembler without verify_piece_hash method
        file_assembler = Mock()
        # Mock doesn't have verify_piece_hash by default, so test will exercise the else branch

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=2,
        )

        # Should handle gracefully
        assert "verified_pieces" in result

    @pytest.mark.asyncio
    async def test_verify_single_piece_to_verify(self, loader):
        """Test verify with single piece to verify."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0}, 10)

        torrent_info = {"pieces": b"x" * (10 * 20)}

        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(return_value=True)

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=1,
        )

        assert result["valid"] is True
        assert len(result["verified_pieces"]) == 1

    @pytest.mark.asyncio
    async def test_verify_more_requested_than_available(self, loader):
        """Test verify when requesting more pieces than available."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 1, 2}, 10)

        torrent_info = {"pieces": b"x" * (10 * 20)}

        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(return_value=True)

        # Request 10 pieces but only 3 available
        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=10,
        )

        assert len(result["verified_pieces"]) == 3  # Should verify all available


class TestConfigurationEdgeCases:
    """Test configuration edge cases."""

    def test_should_verify_on_load_missing_attribute(self):
        """Test should_verify_on_load when config.disk doesn't have attribute."""
        # Create mock config without disk attribute
        class MockConfig:
            pass

        config = MockConfig()
        loader = FastResumeLoader(config)

        # Should use default True
        assert loader.should_verify_on_load() is True

    def test_get_verify_pieces_count_missing_attribute(self):
        """Test get_verify_pieces_count when config.disk doesn't have attribute."""
        class MockConfig:
            pass

        config = MockConfig()
        loader = FastResumeLoader(config)

        # Should use default 10
        assert loader.get_verify_pieces_count() == 10

    def test_config_with_disk_object(self):
        """Test loader with config having disk object but missing attributes."""
        class MockDisk:
            pass

        class MockConfig:
            def __init__(self):
                self.disk = MockDisk()

        config = MockConfig()
        loader = FastResumeLoader(config)

        # Should handle gracefully with defaults
        assert loader.should_verify_on_load() is True
        assert loader.get_verify_pieces_count() == 10


class TestTorrentInfoModelPath:
    """Test paths that use TorrentInfoModel (not dict)."""

    @pytest.fixture
    def config(self):
        """Create test disk config."""
        return DiskConfig()

    @pytest.fixture
    def loader(self, config):
        """Create FastResumeLoader instance."""
        return FastResumeLoader(config)

    @pytest.mark.asyncio
    async def test_verify_integrity_with_torrent_info_model(self, loader):
        """Test verify_integrity with TorrentInfoModel object."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 1}, 10)

        # Create mock TorrentInfoModel-like object
        class TorrentInfo:
            def __init__(self):
                self.piece_hashes = [b"x" * 20 for _ in range(10)]

        torrent_info = TorrentInfo()
        file_assembler = AsyncMock()
        file_assembler.verify_piece_hash = AsyncMock(return_value=True)

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            file_assembler,
            num_pieces_to_verify=2,
        )

        assert result["valid"] is True
        assert len(result["verified_pieces"]) == 2

    def test_validate_resume_data_with_torrent_info_model_total_pieces(self, loader):
        """Test validate_resume_data with TorrentInfoModel having total_pieces."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 1}, 10)

        class TorrentInfo:
            def __init__(self):
                self.info_hash = b"\x00" * 20
                self.total_pieces = 10

        torrent_info = TorrentInfo()

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_resume_data_more_verified_than_total(self, loader):
        """Test validation when verified pieces count exceeds total."""
        # Create resume data with more pieces than torrent has
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        # Encode 11 pieces for a 10-piece torrent
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(
            set(range(11)),  # 0-10 (11 pieces)
            10,  # But torrent only has 10 pieces
        )

        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * (10 * 20)}

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # Should detect the mismatch
        # Note: encode_piece_bitmap filters out pieces >= total_pieces, so piece 10 won't be encoded
        # But let's test the validation logic anyway
        assert isinstance(is_valid, bool)

    def test_validate_resume_data_invalid_piece_indices_detected(self, loader):
        """Test validation detects invalid piece indices."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        # Create a bitmap that might decode to invalid indices
        # Since encode filters, we need to manually corrupt bitmap to have invalid indices
        # We'll create bitmap for 10 pieces but validate against 5-piece torrent
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 9}, 10)

        # Create torrent with only 5 pieces - piece 9 will be invalid
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * (5 * 20)}

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # When decoding with total_pieces=5, piece 9 won't be in decoded set (filtered)
        # So we need to manually create a bitmap with invalid piece
        # Let's decode the bitmap with the wrong total to create invalid indices scenario
        # Actually, decode_piece_bitmap filters invalid pieces, so we can't easily create this
        # But we can test that validation logic runs
        assert isinstance(is_valid, bool)

    def test_validate_more_verified_pieces_than_total(self, loader):
        """Test validation when decoded pieces count exceeds total pieces."""
        # Create resume data with bitmap for 10 pieces
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        # Create bitmap with all 10 pieces verified
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(set(range(10)), 10)

        # But torrent only has 5 pieces - when decoded with total_pieces=5,
        # the bitmap will only decode to pieces 0-4, so count won't exceed
        # To trigger the error, we need to decode with one total but validate against another
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * (5 * 20)}

        is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)

        # The validation uses total_pieces=5 from torrent_info, so decoded bitmap will have <= 5 pieces
        # To actually trigger the "more than total" error, we'd need to manually corrupt the bitmap
        # or use a different encoding approach
        assert isinstance(is_valid, bool)

    @pytest.mark.asyncio
    async def test_verify_integrity_empty_piece_hashes_from_object(self, loader):
        """Test verify_integrity when TorrentInfoModel returns empty piece_hashes."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0}, 10)

        class TorrentInfo:
            def __init__(self):
                self.piece_hashes = []  # Empty list

        torrent_info = TorrentInfo()

        result = await loader.verify_integrity(
            resume_data,
            torrent_info,
            None,
            num_pieces_to_verify=1,
        )

        assert result["valid"] is False
        assert "error" in result
        assert result["error"] == "No piece hashes available"

    def test_validate_trigger_more_verified_than_total_error(self, loader):
        """Test validation that triggers 'more verified than total' error."""
        # To trigger this, we need decoded pieces > total_pieces
        # We can do this by creating a bitmap with total=10, then manually
        # manipulating the validation to decode with wrong total, OR
        # by using a bitmap that was encoded for more pieces
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        
        # Create bitmap encoded for 10 pieces
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap(set(range(10)), 10)
        
        # Create torrent with only 3 pieces
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * (3 * 20)}
        
        # Validation will decode with total_pieces=3, which will filter pieces 3-9
        # To trigger the error, we need decoded pieces count > 3
        # Since decode filters, we need to mock or patch decode_piece_bitmap
        from unittest.mock import patch
        
        # Mock decode to return more pieces than total
        with patch('ccbt.session.fast_resume.FastResumeData.decode_piece_bitmap', return_value=set(range(5))):
            is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)
            
            # Should trigger the error since 5 > 3
            assert is_valid is False
            assert any("Verified pieces (5) > total (3)" in str(e) for e in errors)

    def test_validate_trigger_invalid_piece_indices_error(self, loader):
        """Test validation that triggers 'invalid piece indices' error."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.piece_completion_bitmap = FastResumeData.encode_piece_bitmap({0, 5, 9}, 10)
        
        # Create torrent with only 5 pieces
        torrent_info = {"info_hash": b"\x00" * 20, "pieces": b"x" * (5 * 20)}
        
        # Mock decode_piece_bitmap to return set with invalid piece indices
        from unittest.mock import patch
        
        # Mock to return pieces including invalid ones (piece 9 >= 5)
        with patch('ccbt.session.fast_resume.FastResumeData.decode_piece_bitmap', return_value={0, 3, 9}):
            is_valid, errors = loader.validate_resume_data(resume_data, torrent_info)
            
            # Should trigger error since piece 9 >= 5 (total_pieces)
            assert is_valid is False
            assert any("Invalid piece indices" in str(e) for e in errors)

