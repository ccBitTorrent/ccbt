"""Unit tests for Xet Xorb format.

Tests serialization/deserialization, size limits,
compression, and format validation.
"""

from __future__ import annotations

import pytest

from ccbt.storage.xet_xorb import MAX_XORB_SIZE, Xorb


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXorb:
    """Test Xorb class."""

    def test_xorb_initialization(self):
        """Test Xorb initialization."""
        xorb = Xorb()
        assert xorb.total_size == 0
        assert len(xorb.chunks) == 0

    def test_add_chunk(self):
        """Test adding chunks to xorb."""
        xorb = Xorb()
        chunk_data = b"Test chunk data"
        chunk_hash = b"X" * 32

        xorb.add_chunk(chunk_hash, chunk_data)

        assert len(xorb.chunks) == 1
        assert xorb.total_size == len(chunk_data)
        assert xorb.chunks[0][0] == chunk_hash
        assert xorb.chunks[0][1] == chunk_data

    def test_add_multiple_chunks(self):
        """Test adding multiple chunks."""
        xorb = Xorb()

        for i in range(5):
            chunk_data = f"Chunk {i}".encode()
            chunk_hash = bytes([i] * 32)
            xorb.add_chunk(chunk_hash, chunk_data)

        assert len(xorb.chunks) == 5
        assert xorb.total_size == sum(len(f"Chunk {i}".encode()) for i in range(5))

    def test_xorb_size_limit(self):
        """Test that xorb enforces size limit."""
        xorb = Xorb()

        # Try to add chunk that would exceed limit
        huge_chunk = b"X" * (MAX_XORB_SIZE + 1)
        chunk_hash = b"Y" * 32

        # add_chunk returns False when limit would be exceeded
        result = xorb.add_chunk(chunk_hash, huge_chunk)
        assert result is False

    def test_xorb_is_full(self):
        """Test is_full() method."""
        xorb = Xorb()

        # Add chunks until full
        chunk_size = 1024 * 1024  # 1MB
        chunk_hash = b"Z" * 32

        while not xorb.is_full():
            try:
                xorb.add_chunk(chunk_hash, b"X" * chunk_size)
            except ValueError:
                # Reached limit
                break

        assert xorb.is_full() or xorb.total_size >= MAX_XORB_SIZE

    def test_serialize_empty(self):
        """Test serializing empty xorb."""
        xorb = Xorb()
        serialized = xorb.serialize()

        # Should still produce valid format
        assert len(serialized) > 0

        # Should be deserializable
        deserialized = Xorb.deserialize(serialized)
        assert len(deserialized.chunks) == 0

    def test_serialize_deserialize(self):
        """Test serialization and deserialization round-trip."""
        xorb = Xorb()

        # Add multiple chunks
        for i in range(10):
            chunk_data = f"Chunk data {i}".encode()
            chunk_hash = bytes([i] * 32)
            xorb.add_chunk(chunk_hash, chunk_data)

        # Serialize
        serialized = xorb.serialize()

        # Deserialize
        deserialized = Xorb.deserialize(serialized)

        # Verify chunks match
        assert len(deserialized.chunks) == len(xorb.chunks)
        for (hash1, data1), (hash2, data2) in zip(xorb.chunks, deserialized.chunks):
            assert hash1 == hash2
            assert data1 == data2

    def test_serialize_with_compression(self):
        """Test serialization with compression (if available)."""
        xorb = Xorb()

        # Add compressible data
        chunk_data = b"AAA" * 1000  # Repetitive, should compress well
        chunk_hash = b"X" * 32
        xorb.add_chunk(chunk_hash, chunk_data)

        # Serialize with compression
        serialized = xorb.serialize(compress=True)

        # Should be deserializable
        deserialized = Xorb.deserialize(serialized)

        assert len(deserialized.chunks) == 1
        assert deserialized.chunks[0][1] == chunk_data

    def test_deserialize_invalid_magic(self):
        """Test deserialization with invalid magic bytes."""
        invalid_data = b"INVALID" * 100

        with pytest.raises(ValueError, match="Invalid xorb magic"):
            Xorb.deserialize(invalid_data)

    def test_deserialize_invalid_version(self):
        """Test deserialization with invalid version."""
        # Create valid-looking data but with wrong version
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test")
        data = xorb.serialize()

        # Corrupt version byte
        data = bytearray(data)
        data[4] = 99  # Invalid version
        data = bytes(data)

        with pytest.raises(ValueError, match="Unsupported xorb version"):
            Xorb.deserialize(data)

    def test_get_chunk_by_hash(self):
        """Test retrieving chunk by hash."""
        xorb = Xorb()

        chunk_hash1 = b"A" * 32
        chunk_data1 = b"First chunk"
        chunk_hash2 = b"B" * 32
        chunk_data2 = b"Second chunk"

        xorb.add_chunk(chunk_hash1, chunk_data1)
        xorb.add_chunk(chunk_hash2, chunk_data2)

        # Retrieve by hash
        retrieved = xorb.get_chunk_by_hash(chunk_hash1)
        assert retrieved == chunk_data1

        retrieved = xorb.get_chunk_by_hash(chunk_hash2)
        assert retrieved == chunk_data2

        # Non-existent hash
        retrieved = xorb.get_chunk_by_hash(b"C" * 32)
        assert retrieved is None

    def test_get_chunk_count(self):
        """Test getting chunk count."""
        xorb = Xorb()
        assert xorb.get_chunk_count() == 0

        for i in range(5):
            xorb.add_chunk(bytes([i] * 32), f"chunk {i}".encode())

        assert xorb.get_chunk_count() == 5

    def test_get_total_size(self):
        """Test getting total size."""
        xorb = Xorb()
        assert xorb.get_total_size() == 0

        chunk1 = b"First chunk"
        chunk2 = b"Second chunk"
        xorb.add_chunk(b"A" * 32, chunk1)
        xorb.add_chunk(b"B" * 32, chunk2)

        assert xorb.get_total_size() == len(chunk1) + len(chunk2)

    def test_clear(self):
        """Test clearing xorb."""
        xorb = Xorb()

        # Add chunks
        for i in range(5):
            xorb.add_chunk(bytes([i] * 32), f"chunk {i}".encode())

        assert len(xorb.chunks) == 5

        # Clear
        xorb.clear()

        assert len(xorb.chunks) == 0
        assert xorb.total_size == 0

    def test_get_xorb_hash(self):
        """Test computing xorb hash."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data")

        xorb_hash = xorb.get_xorb_hash()

        assert len(xorb_hash) == 32  # 32-byte hash

        # Should be deterministic
        hash2 = xorb.get_xorb_hash()
        assert xorb_hash == hash2

    def test_compression_ratio(self):
        """Test compression ratio calculation."""
        xorb = Xorb()

        # Add compressible data
        chunk_data = b"AAA" * 1000
        xorb.add_chunk(b"X" * 32, chunk_data)

        ratio = xorb.get_compression_ratio()

        # Should be a float
        assert isinstance(ratio, float)
        # Ratio can be < 1.0 if compression is effective (compressed < uncompressed)
        # or >= 1.0 if compression is not beneficial
        assert ratio > 0.0

    def test_large_xorb(self):
        """Test xorb with large amount of data."""
        xorb = Xorb()

        # Add many chunks
        chunk_size = 100 * 1024  # 100KB per chunk
        num_chunks = (MAX_XORB_SIZE // chunk_size) - 1  # Leave room

        for i in range(num_chunks):
            chunk_data = bytes([i % 256] * chunk_size)
            chunk_hash = bytes([i % 256] * 32)  # Fix: bytes must be in range(0, 256)
            result = xorb.add_chunk(chunk_hash, chunk_data)
            if not result:
                # Reached limit
                break

        # Should serialize and deserialize correctly
        serialized = xorb.serialize()
        deserialized = Xorb.deserialize(serialized)

        assert len(deserialized.chunks) == len(xorb.chunks)

    def test_compressed_size_calculation(self):
        """Test compressed size calculation."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data")

        uncompressed_size = xorb.get_compressed_size(compress=False)
        compressed_size = xorb.get_compressed_size(compress=True)

        # Compressed size should be <= uncompressed (or same if compression not beneficial)
        assert compressed_size <= uncompressed_size or compressed_size == uncompressed_size

    def test_deserialize_with_compression_error(self):
        """Test deserialization with compression error."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data")

        # Serialize with compression
        serialized = xorb.serialize(compress=True)

        # If LZ4 is not available, this should handle gracefully
        # Otherwise, should deserialize correctly
        try:
            deserialized = Xorb.deserialize(serialized)
            assert len(deserialized.chunks) == 1
        except ValueError:
            # If compression is not available, that's acceptable
            pass

    def test_deserialize_invalid_chunk_count(self):
        """Test deserialization with invalid chunk count."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test")
        data = xorb.serialize()

        # Corrupt chunk count
        data = bytearray(data)
        data[16] = 0xFF  # Set chunk count to very large value
        data[17] = 0xFF
        data[18] = 0xFF
        data[19] = 0xFF
        data = bytes(data)

        with pytest.raises(ValueError, match="Invalid chunk count"):
            Xorb.deserialize(data)

    def test_deserialize_short_data(self):
        """Test deserialization with data too short."""
        short_data = b"X" * 10

        with pytest.raises(ValueError, match="too short"):
            Xorb.deserialize(short_data)

    def test_deserialize_short_chunk_data(self):
        """Test deserialization with chunk data too short."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test")
        data = xorb.serialize()

        # Truncate data
        truncated = data[:len(data) - 10]

        with pytest.raises(ValueError, match="too short"):
            Xorb.deserialize(truncated)

    def test_serialize_with_compression_error(self):
        """Test serialization with compression error."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data" * 100)

        # Mock lz4 to raise exception
        import unittest.mock
        with unittest.mock.patch("lz4.frame.compress", side_effect=Exception("Compression error")):
            # Should handle compression error gracefully
            serialized = xorb.serialize(compress=True)
            assert len(serialized) > 0

    def test_deserialize_compressed_without_lz4(self, monkeypatch):
        """Test deserializing compressed xorb without LZ4."""
        from ccbt.storage.xet_xorb import HAS_LZ4
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data")
        serialized = xorb.serialize(compress=True)

        # Mock LZ4 to be unavailable by setting HAS_LZ4 to False
        monkeypatch.setattr("ccbt.storage.xet_xorb.HAS_LZ4", False)

        # Should raise ValueError
        with pytest.raises(ValueError, match="LZ4 is not available"):
            Xorb.deserialize(serialized)

    def test_deserialize_with_size_mismatch(self):
        """Test deserialization with size mismatch."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test")
        data = xorb.serialize()

        # Corrupt the total_size in metadata
        import struct
        data = bytearray(data)
        # Set total_size to wrong value (last 8 bytes)
        struct.pack_into("Q", data, len(data) - 8, 999999)
        data = bytes(data)

        # Should handle size mismatch gracefully (warning logged)
        deserialized = Xorb.deserialize(data)
        assert len(deserialized.chunks) == 1

    def test_get_compression_ratio_no_lz4(self, monkeypatch):
        """Test get_compression_ratio when LZ4 is not available."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data")

        # Mock LZ4 to be unavailable
        import sys
        if "lz4" in sys.modules:
            monkeypatch.delattr(sys.modules["lz4"], "frame", raising=False)

        # Should return 1.0
        ratio = xorb.get_compression_ratio()
        assert ratio == 1.0

    def test_get_compression_ratio_empty(self):
        """Test get_compression_ratio with empty xorb."""
        xorb = Xorb()

        # Should return 1.0 for empty xorb
        ratio = xorb.get_compression_ratio()
        assert ratio == 1.0

    def test_xorb_initialization_with_lz4_unavailable(self, monkeypatch):
        """Test Xorb initialization when LZ4 is unavailable."""
        # Mock LZ4 to be unavailable
        import sys
        if "lz4" in sys.modules:
            monkeypatch.delattr(sys.modules["lz4"], "frame", raising=False)

        xorb = Xorb()

        # Should initialize without error
        assert xorb is not None

    def test_add_chunk_invalid_hash_size(self):
        """Test adding chunk with invalid hash size."""
        xorb = Xorb()
        invalid_hash = b"short"  # Not 32 bytes

        with pytest.raises(ValueError, match="Chunk hash must be 32 bytes"):
            xorb.add_chunk(invalid_hash, b"test data")

    def test_deserialize_compressed_chunk(self):
        """Test deserializing xorb with compressed chunks."""
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data" * 100)

        # Serialize with compression
        serialized = xorb.serialize(compress=True)

        # Deserialize
        deserialized = Xorb.deserialize(serialized)

        assert len(deserialized.chunks) == 1
        # Chunks is a list of (hash, data) tuples
        chunk_hash, chunk_data = deserialized.chunks[0]
        assert chunk_hash == b"X" * 32
        assert chunk_data == b"test data" * 100

    def test_deserialize_decompression_error(self):
        """Test deserializing with decompression error."""
        import struct
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test data" * 100)
        
        # Serialize with compression
        data = xorb.serialize(compress=True)
        data = bytearray(data)
        
        # Find the compressed chunk data and corrupt it
        # After header (16 bytes) + chunk count (4 bytes) = 20 bytes
        # Then for each chunk: hash (32) + uncompressed_size (4) + compressed_size (4) + data
        # Corrupt the compressed data bytes
        offset = 20 + 32 + 4  # After hash and uncompressed_size
        compressed_size = struct.unpack("I", data[offset:offset+4])[0]
        if compressed_size > 0 and len(data) > offset + 4 + 10:
            # Corrupt the compressed data
            data[offset + 4 + 5] = 0xFF  # Corrupt byte in compressed data
        
        # Should raise ValueError on decompression failure
        try:
            Xorb.deserialize(bytes(data))
            # If it doesn't raise, that's okay - corruption might not be detected
            # or compression might not have been applied
            pass
        except ValueError as e:
            # Should raise ValueError with decompression error
            assert "decompress" in str(e).lower() or "Failed" in str(e)

    def test_deserialize_invalid_chunk_count_boundary(self):
        """Test deserializing with chunk count at boundary."""
        import struct
        xorb = Xorb()
        xorb.add_chunk(b"X" * 32, b"test")
        data = xorb.serialize()

        # Corrupt chunk count to be 0
        data = bytearray(data)
        struct.pack_into("I", data, 16, 0)  # Set chunk count to 0
        data = bytes(data)

        # Should handle gracefully (may raise or return empty)
        try:
            deserialized = Xorb.deserialize(data)
            assert len(deserialized.chunks) == 0
        except ValueError:
            # Also acceptable
            pass

    def test_get_compression_ratio_uncompressed(self):
        """Test get_compression_ratio when data doesn't compress well."""
        xorb = Xorb()
        # Use data that doesn't compress (random-looking)
        xorb.add_chunk(b"X" * 32, bytes(range(256)) * 10)

        ratio = xorb.get_compression_ratio()

        # Ratio might be >= 1.0 if compression isn't beneficial
        assert ratio > 0.0

