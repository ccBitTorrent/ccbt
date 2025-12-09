"""Unit tests for Xet data aggregator.

Tests batch chunk operations, aggregation, and parallel processing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ccbt.storage.xet_data_aggregator import XetDataAggregator
from ccbt.storage.xet_deduplication import XetDeduplication


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXetDataAggregator:
    """Test XetDataAggregator class."""

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
    def aggregator(self, dedup):
        """Create XetDataAggregator instance for testing."""
        return XetDataAggregator(dedup, batch_size=10)

    @pytest.mark.asyncio
    async def test_aggregate_chunks_empty(self, aggregator):
        """Test aggregating empty chunk list."""
        result = await aggregator.aggregate_chunks([])

        assert result == b""

    @pytest.mark.asyncio
    async def test_aggregate_chunks_single(self, aggregator, dedup):
        """Test aggregating single chunk."""
        chunk_hash = b"SINGLE" * 5 + b"XX"
        chunk_data = b"Single chunk data"

        # Store chunk
        await dedup.store_chunk(chunk_hash, chunk_data)

        # Aggregate
        result = await aggregator.aggregate_chunks([chunk_hash])

        assert result == chunk_data

    @pytest.mark.asyncio
    async def test_aggregate_chunks_multiple(self, aggregator, dedup):
        """Test aggregating multiple chunks."""
        chunk_hashes = []
        chunk_data_list = [b"Chunk1", b"Chunk2", b"Chunk3"]

        # Store chunks
        for chunk_data in chunk_data_list:
            chunk_hash = bytes([len(chunk_hashes)] * 32)
            chunk_hashes.append(chunk_hash)
            await dedup.store_chunk(chunk_hash, chunk_data)

        # Aggregate
        result = await aggregator.aggregate_chunks(chunk_hashes)

        assert result == b"".join(chunk_data_list)

    @pytest.mark.asyncio
    async def test_aggregate_chunks_missing(self, aggregator, dedup):
        """Test aggregating chunks with missing chunk."""
        chunk_hash1 = b"MISS1" * 6 + b"XX"
        chunk_hash2 = b"MISS2" * 6 + b"XX"
        chunk_data1 = b"Chunk1 data"

        # Store only first chunk
        await dedup.store_chunk(chunk_hash1, chunk_data1)

        # Aggregate (second chunk is missing)
        result = await aggregator.aggregate_chunks([chunk_hash1, chunk_hash2])

        # Should contain first chunk, missing second
        assert chunk_data1 in result

    @pytest.mark.asyncio
    async def test_batch_store_chunks(self, aggregator, dedup):
        """Test batch storing chunks."""
        chunks = [
            (b"BATCH1" * 5 + b"XX", b"Batch chunk 1"),
            (b"BATCH2" * 5 + b"XX", b"Batch chunk 2"),
            (b"BATCH3" * 5 + b"XX", b"Batch chunk 3"),
        ]

        # Store in batch
        paths = await aggregator.batch_store_chunks(chunks)

        assert len(paths) == 3
        # Verify all chunks exist
        for chunk_hash, _ in chunks:
            chunk_path = await dedup.check_chunk_exists(chunk_hash)
            assert chunk_path is not None

    @pytest.mark.asyncio
    async def test_batch_store_chunks_with_file_context(self, aggregator, dedup):
        """Test batch storing chunks with file context."""
        chunks = [
            (b"FILE1" * 6 + b"XX", b"File chunk 1"),
            (b"FILE2" * 6 + b"XX", b"File chunk 2"),
        ]
        file_path = "/test/batch_file.txt"
        file_offsets = [0, 100]

        # Store in batch with file context
        paths = await aggregator.batch_store_chunks(
            chunks, file_path=file_path, file_offsets=file_offsets
        )

        assert len(paths) == 2

        # Verify file references created
        file_chunks = await dedup.get_file_chunks(file_path)
        assert len(file_chunks) == 2

    @pytest.mark.asyncio
    async def test_batch_store_chunks_empty(self, aggregator):
        """Test batch storing empty chunk list."""
        paths = await aggregator.batch_store_chunks([])

        assert paths == []

    @pytest.mark.asyncio
    async def test_batch_read_chunks(self, aggregator, dedup):
        """Test batch reading chunks."""
        chunk_hashes = []
        chunk_data_list = [b"Read chunk 1", b"Read chunk 2", b"Read chunk 3"]

        # Store chunks
        for chunk_data in chunk_data_list:
            chunk_hash = bytes([len(chunk_hashes)] * 32)
            chunk_hashes.append(chunk_hash)
            await dedup.store_chunk(chunk_hash, chunk_data)

        # Read in batch
        results = await aggregator.batch_read_chunks(chunk_hashes)

        assert len(results) == 3
        for i, chunk_hash in enumerate(chunk_hashes):
            assert chunk_hash in results
            assert results[chunk_hash] == chunk_data_list[i]

    @pytest.mark.asyncio
    async def test_batch_read_chunks_missing(self, aggregator, dedup):
        """Test batch reading with missing chunks."""
        chunk_hash1 = b"READ1" * 6 + b"XX"
        chunk_hash2 = b"READ2" * 6 + b"XX"
        chunk_data1 = b"Existing chunk"

        # Store only first chunk
        await dedup.store_chunk(chunk_hash1, chunk_data1)

        # Read in batch
        results = await aggregator.batch_read_chunks([chunk_hash1, chunk_hash2])

        assert chunk_hash1 in results
        assert results[chunk_hash1] == chunk_data1
        assert chunk_hash2 in results
        assert results[chunk_hash2] == b""  # Missing chunk returns empty

    @pytest.mark.asyncio
    async def test_batch_read_chunks_empty(self, aggregator):
        """Test batch reading empty chunk list."""
        results = await aggregator.batch_read_chunks([])

        assert results == {}

    @pytest.mark.asyncio
    async def test_optimize_storage_layout(self, aggregator):
        """Test storage layout optimization (placeholder)."""
        chunk_hashes = [b"OPT" * 10 + b"XX", b"OPT2" * 10 + b"XX"]

        result = await aggregator.optimize_storage_layout(chunk_hashes)

        assert isinstance(result, dict)
        assert "chunks_optimized" in result
        assert "storage_reorganized" in result
        assert "access_improvement" in result

    @pytest.mark.asyncio
    async def test_batch_store_chunks_large_batch(self, aggregator, dedup):
        """Test batch storing large number of chunks."""
        # Create 50 chunks
        chunks = [
            (bytes([i] * 32), f"Chunk {i}".encode()) for i in range(50)
        ]

        # Store in batch (should handle batching internally)
        paths = await aggregator.batch_store_chunks(chunks)

        assert len(paths) == 50

        # Verify all chunks stored
        for chunk_hash, _ in chunks:
            chunk_path = await dedup.check_chunk_exists(chunk_hash)
            assert chunk_path is not None





































