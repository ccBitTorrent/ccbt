"""Unit tests for Xet file-level deduplication.

Tests file-level deduplication operations, duplicate detection,
and file deduplication statistics.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ccbt.models import XetFileMetadata
from ccbt.storage.xet_deduplication import XetDeduplication
from ccbt.storage.xet_file_deduplication import XetFileDeduplication


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXetFileDeduplication:
    """Test XetFileDeduplication class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name
        yield db_path
        # Cleanup
        import os
        import time
        for _ in range(5):
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
                break
            except (PermissionError, OSError):
                time.sleep(0.1)

    @pytest.fixture
    def dedup(self, temp_db_path):
        """Create XetDeduplication instance for testing."""
        dedup = XetDeduplication(cache_db_path=temp_db_path)
        yield dedup
        dedup.close()

    @pytest.fixture
    def file_dedup(self, dedup):
        """Create XetFileDeduplication instance for testing."""
        return XetFileDeduplication(dedup)

    @pytest.mark.asyncio
    async def test_deduplicate_file_no_metadata(self, file_dedup, tmp_path):
        """Test deduplicating file with no metadata."""
        file_path = tmp_path / "no_metadata.txt"

        result = await file_dedup.deduplicate_file(file_path)

        assert result["duplicate_found"] is False
        assert result["duplicate_path"] is None
        assert result["chunks_skipped"] == 0
        assert result["storage_saved"] == 0

    @pytest.mark.asyncio
    async def test_deduplicate_file_no_duplicate(self, file_dedup, dedup, tmp_path):
        """Test deduplicating file with no duplicate."""
        file_path = tmp_path / "unique_file.txt"

        # Create and store file metadata
        file_metadata = XetFileMetadata(
            file_path=str(file_path),
            file_hash=b"UNIQUE" * 5 + b"XX",
            chunk_hashes=[b"CHUNK1" * 5 + b"XX"],
            xorb_refs=[],
            total_size=100,
        )
        await dedup.store_file_metadata(file_metadata)

        result = await file_dedup.deduplicate_file(file_path)

        assert result["duplicate_found"] is False
        assert result["duplicate_path"] is None

    @pytest.mark.asyncio
    async def test_deduplicate_file_with_duplicate(self, file_dedup, dedup, tmp_path):
        """Test deduplicating file with duplicate."""
        file_path1 = tmp_path / "file1.txt"
        file_path2 = tmp_path / "file2.txt"
        file_hash = b"DUPLICATE" * 3 + b"XX"

        # Store metadata for first file
        metadata1 = XetFileMetadata(
            file_path=str(file_path1),
            file_hash=file_hash,
            chunk_hashes=[b"CHUNK1" * 5 + b"XX", b"CHUNK2" * 5 + b"XX"],
            xorb_refs=[],
            total_size=200,
        )
        await dedup.store_file_metadata(metadata1)

        # Store metadata for second file (same hash)
        metadata2 = XetFileMetadata(
            file_path=str(file_path2),
            file_hash=file_hash,
            chunk_hashes=[b"CHUNK1" * 5 + b"XX", b"CHUNK2" * 5 + b"XX"],
            xorb_refs=[],
            total_size=200,
        )
        await dedup.store_file_metadata(metadata2)

        # Deduplicate second file (should find first as duplicate)
        result = await file_dedup.deduplicate_file(file_path2)

        assert result["duplicate_found"] is True
        assert result["duplicate_path"] == str(file_path1)
        assert result["file_hash"] == file_hash
        assert result["chunks_skipped"] == 2
        assert result["storage_saved"] == 200

    @pytest.mark.asyncio
    async def test_get_file_deduplication_stats(self, file_dedup, dedup):
        """Test getting file deduplication statistics."""
        # Store some file metadata
        for i in range(5):
            file_metadata = XetFileMetadata(
                file_path=f"/test/file{i}.txt",
                file_hash=bytes([i] * 32),
                chunk_hashes=[bytes([i] * 32)],
                xorb_refs=[],
                total_size=100 * (i + 1),
            )
            await dedup.store_file_metadata(file_metadata)

        # Add a duplicate (same hash as file 0)
        duplicate_metadata = XetFileMetadata(
            file_path="/test/duplicate.txt",
            file_hash=bytes([0] * 32),
            chunk_hashes=[bytes([0] * 32)],
            xorb_refs=[],
            total_size=100,
        )
        await dedup.store_file_metadata(duplicate_metadata)

        stats = await file_dedup.get_file_deduplication_stats()

        assert stats["total_files"] == 6
        assert stats["unique_files"] == 5
        assert stats["duplicate_files"] == 1
        assert stats["total_storage"] > 0
        assert stats["deduplicated_storage"] > 0
        assert 0.0 <= stats["deduplication_ratio"] <= 1.0

    @pytest.mark.asyncio
    async def test_get_file_deduplication_stats_empty(self, file_dedup):
        """Test getting stats when no files exist."""
        stats = await file_dedup.get_file_deduplication_stats()

        assert stats["total_files"] == 0
        assert stats["unique_files"] == 0
        assert stats["duplicate_files"] == 0
        assert stats["total_storage"] == 0
        assert stats["deduplicated_storage"] == 0
        assert stats["deduplication_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_find_duplicate_files_specific_hash(self, file_dedup, dedup):
        """Test finding duplicates for specific file hash."""
        file_hash = b"FINDME" * 5 + b"XX"

        # Store multiple files with same hash
        for i in range(3):
            metadata = XetFileMetadata(
                file_path=f"/test/duplicate{i}.txt",
                file_hash=file_hash,
                chunk_hashes=[b"CHUNK" * 5 + b"XX"],
                xorb_refs=[],
                total_size=100,
            )
            await dedup.store_file_metadata(metadata)

        # Find duplicates for specific hash
        duplicates = await file_dedup.find_duplicate_files(file_hash)

        assert len(duplicates) == 1
        assert len(duplicates[0]) == 3

    @pytest.mark.asyncio
    async def test_find_duplicate_files_all(self, file_dedup, dedup):
        """Test finding all duplicate file groups."""
        # Store files with some duplicates
        file_hashes = [
            b"HASH1" * 6 + b"XX",
            b"HASH1" * 6 + b"XX",  # Duplicate
            b"HASH2" * 6 + b"XX",
            b"HASH2" * 6 + b"XX",  # Duplicate
            b"HASH2" * 6 + b"XX",  # Another duplicate
            b"HASH3" * 6 + b"XX",  # Unique
        ]

        for i, file_hash in enumerate(file_hashes):
            metadata = XetFileMetadata(
                file_path=f"/test/file{i}.txt",
                file_hash=file_hash,
                chunk_hashes=[b"CHUNK" * 5 + b"XX"],
                xorb_refs=[],
                total_size=100,
            )
            await dedup.store_file_metadata(metadata)

        # Find all duplicates
        duplicate_groups = await file_dedup.find_duplicate_files()

        # Should have 2 groups (HASH1 with 2 files, HASH2 with 3 files)
        assert len(duplicate_groups) == 2
        # Verify group sizes
        group_sizes = [len(group) for group in duplicate_groups]
        assert 2 in group_sizes
        assert 3 in group_sizes

    @pytest.mark.asyncio
    async def test_find_duplicate_files_no_duplicates(self, file_dedup, dedup):
        """Test finding duplicates when none exist."""
        # Store unique files
        for i in range(5):
            metadata = XetFileMetadata(
                file_path=f"/test/unique{i}.txt",
                file_hash=bytes([i] * 32),
                chunk_hashes=[bytes([i] * 32)],
                xorb_refs=[],
                total_size=100,
            )
            await dedup.store_file_metadata(metadata)

        duplicates = await file_dedup.find_duplicate_files()

        assert duplicates == []

    @pytest.mark.asyncio
    async def test_deduplicate_file_exception_handling(self, file_dedup, tmp_path):
        """Test deduplicate_file handles exceptions gracefully."""
        # Create file path that will cause issues
        file_path = tmp_path / "error_file.txt"

        # Should handle gracefully even if metadata retrieval fails
        result = await file_dedup.deduplicate_file(file_path)

        assert isinstance(result, dict)
        assert "duplicate_found" in result





































