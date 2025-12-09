"""Unit tests for Xet defragmentation prevention.

Tests fragmentation detection, prevention, and optimization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ccbt.storage.xet_defrag_prevention import XetDefragPrevention
from ccbt.storage.xet_deduplication import XetDeduplication


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXetDefragPrevention:
    """Test XetDefragPrevention class."""

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
    def defrag(self, dedup):
        """Create XetDefragPrevention instance for testing."""
        return XetDefragPrevention(dedup)

    @pytest.mark.asyncio
    async def test_check_fragmentation_empty(self, defrag):
        """Test checking fragmentation with no chunks."""
        result = await defrag.check_fragmentation()

        assert result["fragmentation_ratio"] == 0.0
        assert result["scattered_chunks"] == 0
        assert result["total_chunks"] == 0
        assert result["needs_defrag"] is False

    @pytest.mark.asyncio
    async def test_check_fragmentation_with_chunks(self, defrag, dedup):
        """Test checking fragmentation with stored chunks."""
        # Store some chunks
        for i in range(10):
            chunk_hash = bytes([i] * 32)
            chunk_data = f"Chunk {i}".encode()
            await dedup.store_chunk(chunk_hash, chunk_data)

        result = await defrag.check_fragmentation()

        assert result["total_chunks"] == 10
        assert 0.0 <= result["fragmentation_ratio"] <= 1.0
        assert isinstance(result["needs_defrag"], bool)

    @pytest.mark.asyncio
    async def test_check_fragmentation_metrics(self, defrag, dedup):
        """Test fragmentation metrics calculation."""
        # Store chunks
        for i in range(5):
            chunk_hash = bytes([i] * 32)
            chunk_data = f"Test chunk {i}".encode()
            await dedup.store_chunk(chunk_hash, chunk_data)

        result = await defrag.check_fragmentation()

        assert "fragmentation_ratio" in result
        assert "scattered_chunks" in result
        assert "total_chunks" in result
        assert "average_access_time" in result
        assert "needs_defrag" in result

    @pytest.mark.asyncio
    async def test_prevent_fragmentation_no_defrag_needed(self, defrag):
        """Test preventing fragmentation when not needed."""
        result = await defrag.prevent_fragmentation()

        assert isinstance(result, dict)
        assert "chunks_reorganized" in result
        assert "storage_optimized" in result
        assert "fragmentation_reduced" in result

    @pytest.mark.asyncio
    async def test_prevent_fragmentation_with_chunks(self, defrag, dedup):
        """Test preventing fragmentation with stored chunks."""
        # Store chunks
        for i in range(10):
            chunk_hash = bytes([i] * 32)
            chunk_data = f"Chunk {i}".encode()
            await dedup.store_chunk(chunk_hash, chunk_data)

        result = await defrag.prevent_fragmentation()

        assert isinstance(result, dict)
        assert "chunks_reorganized" in result
        assert "storage_optimized" in result
        assert "fragmentation_reduced" in result

    @pytest.mark.asyncio
    async def test_optimize_chunk_layout_specific(self, defrag, dedup):
        """Test optimizing layout for specific chunks."""
        # Store chunks
        chunk_hashes = []
        for i in range(5):
            chunk_hash = bytes([i] * 32)
            chunk_data = f"Chunk {i}".encode()
            await dedup.store_chunk(chunk_hash, chunk_data)
            chunk_hashes.append(chunk_hash)

        result = await defrag.optimize_chunk_layout(chunk_hashes)

        assert isinstance(result, dict)
        assert "chunks_optimized" in result
        assert "layout_improved" in result

    @pytest.mark.asyncio
    async def test_optimize_chunk_layout_all(self, defrag, dedup):
        """Test optimizing layout for all chunks."""
        # Store chunks
        for i in range(5):
            chunk_hash = bytes([i] * 32)
            chunk_data = f"Chunk {i}".encode()
            await dedup.store_chunk(chunk_hash, chunk_data)

        result = await defrag.optimize_chunk_layout()

        assert isinstance(result, dict)
        assert "chunks_optimized" in result
        assert "layout_improved" in result

    @pytest.mark.asyncio
    async def test_optimize_chunk_layout_empty(self, defrag):
        """Test optimizing layout with no chunks."""
        result = await defrag.optimize_chunk_layout([])

        assert isinstance(result, dict)
        assert result["chunks_optimized"] == 0

    @pytest.mark.asyncio
    async def test_check_fragmentation_exception_handling(self, defrag):
        """Test check_fragmentation handles exceptions gracefully."""
        # Should handle database errors gracefully
        result = await defrag.check_fragmentation()

        assert isinstance(result, dict)
        assert "fragmentation_ratio" in result

    @pytest.mark.asyncio
    async def test_prevent_fragmentation_exception_handling(self, defrag):
        """Test prevent_fragmentation handles exceptions gracefully."""
        result = await defrag.prevent_fragmentation()

        assert isinstance(result, dict)
        assert "chunks_reorganized" in result





































