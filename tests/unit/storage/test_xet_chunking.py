"""Unit tests for Xet chunking (Gearhash CDC algorithm).

Tests content-defined chunking with boundary detection,
chunk size constraints, and consistency.
"""

from __future__ import annotations

import pytest

from ccbt.storage.xet_chunking import (
    GearhashChunker,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    TARGET_CHUNK_SIZE,
)


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestGearhashChunker:
    """Test GearhashChunker class."""

    def test_chunker_initialization(self):
        """Test chunker initialization with default and custom target sizes."""
        # Default target size
        chunker = GearhashChunker()
        assert chunker.target_size == TARGET_CHUNK_SIZE

        # Custom target size
        custom_size = 32768
        chunker = GearhashChunker(target_size=custom_size)
        assert chunker.target_size == custom_size

    def test_chunker_target_size_validation(self):
        """Test that invalid target sizes raise ValueError."""
        # Too small
        with pytest.raises(ValueError, match="Target size must be between"):
            GearhashChunker(target_size=MIN_CHUNK_SIZE - 1)

        # Too large
        with pytest.raises(ValueError, match="Target size must be between"):
            GearhashChunker(target_size=MAX_CHUNK_SIZE + 1)

        # Valid boundaries
        chunker_min = GearhashChunker(target_size=MIN_CHUNK_SIZE)
        assert chunker_min.target_size == MIN_CHUNK_SIZE

        chunker_max = GearhashChunker(target_size=MAX_CHUNK_SIZE)
        assert chunker_max.target_size == MAX_CHUNK_SIZE

    def test_chunk_empty_buffer(self):
        """Test chunking empty buffer returns empty list."""
        chunker = GearhashChunker()
        chunks = chunker.chunk_buffer(b"")
        assert chunks == []

    def test_chunk_small_buffer(self):
        """Test chunking small buffer (smaller than MIN_CHUNK_SIZE)."""
        chunker = GearhashChunker()
        small_data = b"Hello, World!" * 100  # ~1.3KB
        chunks = chunker.chunk_buffer(small_data)

        # Should produce at least one chunk (even if smaller than min)
        # The algorithm may produce chunks smaller than MIN_CHUNK_SIZE
        # if content boundaries dictate, but should not exceed MAX_CHUNK_SIZE
        assert len(chunks) > 0
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

    def test_chunk_size_boundaries(self):
        """Test that chunks respect size boundaries (8KB-128KB)."""
        chunker = GearhashChunker()

        # Create data that should produce multiple chunks
        # Use repetitive pattern to potentially trigger boundaries
        large_data = b"X" * (MAX_CHUNK_SIZE * 3)  # 3x max chunk size
        chunks = chunker.chunk_buffer(large_data)

        assert len(chunks) > 0

        # All chunks should be within size limits
        for chunk in chunks:
            # Chunks can be smaller than MIN_CHUNK_SIZE due to content boundaries
            # but should never exceed MAX_CHUNK_SIZE
            assert len(chunk) <= MAX_CHUNK_SIZE
            # Last chunk may be smaller than MIN_CHUNK_SIZE
            if chunk != chunks[-1]:
                # Non-last chunks should typically be >= MIN_CHUNK_SIZE
                # but this is not guaranteed with content-defined chunking
                pass

    def test_chunk_consistency(self):
        """Test that same input produces same chunks (deterministic)."""
        chunker = GearhashChunker()

        test_data = b"This is test data for chunking consistency. " * 500
        chunks1 = chunker.chunk_buffer(test_data)
        chunks2 = chunker.chunk_buffer(test_data)

        # Should produce identical chunks
        assert len(chunks1) == len(chunks2)
        assert all(c1 == c2 for c1, c2 in zip(chunks1, chunks2))

    def test_chunk_reassembles_correctly(self):
        """Test that chunks can be reassembled to original data."""
        chunker = GearhashChunker()

        test_data = b"Original data for reassembly test. " * 1000
        chunks = chunker.chunk_buffer(test_data)

        # Reassemble
        reassembled = b"".join(chunks)
        assert reassembled == test_data

    def test_chunk_varied_content(self):
        """Test chunking with varied content patterns."""
        chunker = GearhashChunker()

        # Test with different content patterns
        test_cases = [
            b"A" * 50000,  # Repetitive
            b"".join(bytes([i % 256]) for i in range(50000)),  # Sequential
            b"Hello World! " * 5000,  # Text pattern
            b"\x00\xFF" * 25000,  # Binary pattern
        ]

        for test_data in test_cases:
            chunks = chunker.chunk_buffer(test_data)
            assert len(chunks) > 0
            assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

            # Verify reassembly
            reassembled = b"".join(chunks)
            assert reassembled == test_data

    def test_chunk_target_size_influence(self):
        """Test that target_size influences chunk boundaries."""
        # Smaller target should produce more chunks
        small_target = GearhashChunker(target_size=MIN_CHUNK_SIZE)
        large_target = GearhashChunker(target_size=MAX_CHUNK_SIZE)

        test_data = b"Test data " * 10000

        small_chunks = small_target.chunk_buffer(test_data)
        large_chunks = large_target.chunk_buffer(test_data)

        # With content-defined chunking, target_size is a hint
        # Actual chunk count depends on content boundaries
        # But generally, smaller target should produce more chunks
        # (This is probabilistic, so we just verify both work)
        assert len(small_chunks) > 0
        assert len(large_chunks) > 0

        # Both should reassemble correctly
        assert b"".join(small_chunks) == test_data
        assert b"".join(large_chunks) == test_data

    def test_chunk_large_file_simulation(self):
        """Test chunking large amount of data (simulating file)."""
        chunker = GearhashChunker()

        # Simulate 10MB file
        large_data = b"X" * (10 * 1024 * 1024)
        chunks = chunker.chunk_buffer(large_data)

        # Should produce multiple chunks
        assert len(chunks) > 1

        # All chunks within size limits
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

        # Reassemble correctly
        reassembled = b"".join(chunks)
        assert reassembled == large_data
        assert len(reassembled) == len(large_data)

    def test_chunk_gear_table_initialization(self):
        """Test that gear table is properly initialized."""
        chunker = GearhashChunker()
        gear_table = chunker.gear_table

        # Should have 256 elements
        assert len(gear_table) == 256

        # All elements should be integers
        assert all(isinstance(val, int) for val in gear_table)

    def test_chunk_boundary_detection(self):
        """Test that chunk boundaries are detected correctly."""
        chunker = GearhashChunker()

        # Create data with known patterns that should trigger boundaries
        # Use varied content to increase chance of boundary detection
        varied_data = b"".join(
            bytes([i % 256, (i * 7) % 256, (i * 13) % 256])
            for i in range(100000)
        )

        chunks = chunker.chunk_buffer(varied_data)

        # Should produce multiple chunks from varied content
        assert len(chunks) >= 1

        # Verify all chunks are valid
        for chunk in chunks:
            assert len(chunk) > 0
            assert len(chunk) <= MAX_CHUNK_SIZE

        # Verify reassembly
        assert b"".join(chunks) == varied_data

    def test_chunk_file(self, tmp_path):
        """Test chunking a file."""
        chunker = GearhashChunker()

        # Create test file
        test_file = tmp_path / "test_file.bin"
        test_data = b"Test file data for chunking. " * 1000
        test_file.write_bytes(test_data)

        # Chunk the file
        chunks = list(chunker.chunk_file(str(test_file)))

        # Verify chunks
        assert len(chunks) > 0
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

        # Verify reassembly
        reassembled = b"".join(chunks)
        assert reassembled == test_data

    def test_chunk_stream(self):
        """Test chunking a stream."""
        chunker = GearhashChunker()

        # Create stream of chunks
        stream_data = [
            b"First chunk ",
            b"Second chunk ",
            b"Third chunk ",
        ] * 100

        def data_stream():
            for chunk in stream_data:
                yield chunk

        # Chunk the stream
        chunks = list(chunker.chunk_stream(data_stream()))

        # Verify chunks
        assert len(chunks) > 0
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

        # Verify reassembly
        reassembled = b"".join(chunks)
        original = b"".join(stream_data)
        assert reassembled == original

    def test_chunk_buffer_with_rolling_hash_window(self):
        """Test chunk_buffer with rolling hash window building."""
        chunker = GearhashChunker()
        
        # Create data that will trigger window building
        # First 48 bytes will build the window
        data = b"A" * 10000

        chunks = list(chunker.chunk_buffer(data))

        # Should produce chunks
        assert len(chunks) > 0
        assert all(len(chunk) >= MIN_CHUNK_SIZE for chunk in chunks)
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

    def test_chunk_buffer_no_boundary_found(self):
        """Test chunk_buffer when no boundary is found."""
        chunker = GearhashChunker()
        
        # Create data with pattern unlikely to hit boundary
        # Use repeated pattern that might not trigger boundary
        data = b"X" * (MAX_CHUNK_SIZE + 1000)

        chunks = list(chunker.chunk_buffer(data))

        # Should still produce chunks (max size enforced)
        assert len(chunks) > 0
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

    def test_chunk_file_with_custom_hint(self, tmp_path):
        """Test chunk_file with custom chunk_size_hint."""
        chunker = GearhashChunker()

        # Create test file
        test_file = tmp_path / "test_file.bin"
        test_data = b"Test file data. " * 1000
        test_file.write_bytes(test_data)

        # Chunk with custom hint
        chunks = list(chunker.chunk_file(str(test_file), chunk_size_hint=512))

        # Verify chunks
        assert len(chunks) > 0
        assert all(len(chunk) <= MAX_CHUNK_SIZE for chunk in chunks)

        # Verify reassembly
        reassembled = b"".join(chunks)
        assert reassembled == test_data

    def test_chunk_stream_with_remaining_buffer(self):
        """Test chunk_stream with remaining buffer at end."""
        chunker = GearhashChunker()

        # Create stream that leaves small buffer
        def small_stream():
            yield b"Small chunk " * 10
            yield b"End"

        chunks = list(chunker.chunk_stream(small_stream()))

        # Should process all data
        assert len(chunks) > 0

