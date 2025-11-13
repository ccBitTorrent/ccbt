"""Unit tests for Xet Shard format.

Tests format compliance, HMAC verification, file metadata
serialization, and CAS information tracking.
"""

from __future__ import annotations

import hmac
import hashlib
import struct

import pytest

from ccbt.storage.xet_shard import (
    HMAC_SIZE,
    SHARD_HEADER_SIZE,
    SHARD_MAGIC,
    SHARD_VERSION,
    XetShard,
)


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXetShard:
    """Test XetShard class."""

    def test_shard_initialization(self):
        """Test shard initialization."""
        shard = XetShard()
        assert len(shard.files) == 0
        assert len(shard.xorbs) == 0
        assert len(shard.chunks) == 0

    def test_add_file_info(self):
        """Test adding file information."""
        shard = XetShard()
        file_hash = b"X" * 32
        xorb_refs = [b"Y" * 32, b"Z" * 32]

        shard.add_file_info(
            file_path="/path/to/file.txt",
            file_hash=file_hash,
            xorb_refs=xorb_refs,
            total_size=1024,
        )

        assert len(shard.files) == 1
        assert shard.files[0]["path"] == "/path/to/file.txt"
        assert shard.files[0]["hash"] == file_hash
        assert shard.files[0]["xorbs"] == xorb_refs
        assert shard.files[0]["size"] == 1024

    def test_add_file_info_invalid_hash(self):
        """Test that invalid file hash size raises ValueError."""
        shard = XetShard()
        invalid_hash = b"short"  # Not 32 bytes

        with pytest.raises(ValueError, match="File hash must be 32 bytes"):
            shard.add_file_info(
                file_path="/path/to/file.txt",
                file_hash=invalid_hash,
                xorb_refs=[],
                total_size=1024,
            )

    def test_add_file_info_invalid_xorb_hash(self):
        """Test that invalid xorb hash size raises ValueError."""
        shard = XetShard()
        file_hash = b"X" * 32
        invalid_xorb = b"short"  # Not 32 bytes

        with pytest.raises(ValueError, match="Xorb hash must be 32 bytes"):
            shard.add_file_info(
                file_path="/path/to/file.txt",
                file_hash=file_hash,
                xorb_refs=[invalid_xorb],
                total_size=1024,
            )

    def test_add_chunk_hash(self):
        """Test adding chunk hash."""
        shard = XetShard()
        chunk_hash = b"A" * 32

        shard.add_chunk_hash(chunk_hash)

        assert len(shard.chunks) == 1
        assert chunk_hash in shard.chunks

    def test_add_chunk_hash_duplicate(self):
        """Test that duplicate chunk hashes are not added."""
        shard = XetShard()
        chunk_hash = b"B" * 32

        shard.add_chunk_hash(chunk_hash)
        shard.add_chunk_hash(chunk_hash)  # Duplicate

        assert len(shard.chunks) == 1

    def test_add_chunk_hash_invalid_size(self):
        """Test that invalid chunk hash size raises ValueError."""
        shard = XetShard()
        invalid_hash = b"short"

        with pytest.raises(ValueError, match="Chunk hash must be 32 bytes"):
            shard.add_chunk_hash(invalid_hash)

    def test_add_xorb_hash(self):
        """Test adding xorb hash."""
        shard = XetShard()
        xorb_hash = b"C" * 32

        shard.add_xorb_hash(xorb_hash)

        assert len(shard.xorbs) == 1
        assert xorb_hash in shard.xorbs

    def test_add_xorb_hash_duplicate(self):
        """Test that duplicate xorb hashes are not added."""
        shard = XetShard()
        xorb_hash = b"D" * 32

        shard.add_xorb_hash(xorb_hash)
        shard.add_xorb_hash(xorb_hash)  # Duplicate

        assert len(shard.xorbs) == 1

    def test_add_xorb_hash_invalid_size(self):
        """Test that invalid xorb hash size raises ValueError."""
        shard = XetShard()
        invalid_hash = b"short"

        with pytest.raises(ValueError, match="Xorb hash must be 32 bytes"):
            shard.add_xorb_hash(invalid_hash)

    def test_serialize_empty(self):
        """Test serializing empty shard."""
        shard = XetShard()
        serialized = shard.serialize()

        # Should produce valid format even when empty
        assert len(serialized) > 0

    def test_serialize_with_hmac(self):
        """Test serialization with HMAC key."""
        shard = XetShard()
        shard.add_file_info(
            file_path="/test/file.txt",
            file_hash=b"X" * 32,
            xorb_refs=[b"Y" * 32],
            total_size=100,
        )

        hmac_key = b"test_key_32_bytes_long_!!"  # 32 bytes
        serialized = shard.serialize(hmac_key=hmac_key)

        # Should include HMAC
        assert len(serialized) > SHARD_HEADER_SIZE + HMAC_SIZE

    def test_serialize_deserialize(self):
        """Test serialization and deserialization round-trip."""
        shard = XetShard()

        # Add file info
        shard.add_file_info(
            file_path="/path/to/file1.txt",
            file_hash=b"A" * 32,
            xorb_refs=[b"B" * 32, b"C" * 32],
            total_size=2048,
        )

        # Add chunk and xorb hashes
        shard.add_chunk_hash(b"D" * 32)
        shard.add_chunk_hash(b"E" * 32)
        shard.add_xorb_hash(b"F" * 32)

        # Serialize
        serialized = shard.serialize()

        # Deserialize
        deserialized = XetShard.deserialize(serialized)

        # Verify files match
        assert len(deserialized.files) == len(shard.files)
        assert deserialized.files[0]["path"] == shard.files[0]["path"]
        assert deserialized.files[0]["hash"] == shard.files[0]["hash"]

        # Verify chunks and xorbs match
        assert len(deserialized.chunks) == len(shard.chunks)
        assert len(deserialized.xorbs) == len(shard.xorbs)

    def test_deserialize_invalid_magic(self):
        """Test deserialization with invalid magic bytes."""
        invalid_data = b"INVALID" * 100

        with pytest.raises(ValueError, match="Invalid shard magic"):
            XetShard.deserialize(invalid_data)

    def test_deserialize_invalid_version(self):
        """Test deserialization with invalid version."""
        # Create valid-looking data but with wrong version
        shard = XetShard()
        shard.add_file_info(
            file_path="/test.txt",
            file_hash=b"X" * 32,
            xorb_refs=[],
            total_size=100,
        )
        data = shard.serialize()

        # Corrupt version byte
        data = bytearray(data)
        data[4] = 99  # Invalid version
        data = bytes(data)

        with pytest.raises(ValueError, match="Unsupported shard version"):
            XetShard.deserialize(data)

    def test_deserialize_with_hmac_verification(self):
        """Test deserialization with HMAC verification."""
        shard = XetShard()
        shard.add_file_info(
            file_path="/test/file.txt",
            file_hash=b"X" * 32,
            xorb_refs=[],
            total_size=100,
        )

        hmac_key = b"test_key_32_bytes_long_!!"  # 32 bytes
        serialized = shard.serialize(hmac_key=hmac_key)

        # Deserialize with correct key
        deserialized = XetShard.deserialize(serialized, hmac_key=hmac_key)

        assert len(deserialized.files) == 1

        # Deserialize with wrong key should fail
        wrong_key = b"wrong_key_32_bytes_long_!!"  # 32 bytes
        with pytest.raises(ValueError, match="HMAC verification failed"):
            XetShard.deserialize(serialized, hmac_key=wrong_key)

    def test_deserialize_corrupted_hmac(self):
        """Test deserialization with corrupted HMAC."""
        shard = XetShard()
        shard.add_file_info(
            file_path="/test/file.txt",
            file_hash=b"X" * 32,
            xorb_refs=[],
            total_size=100,
        )

        hmac_key = b"test_key_32_bytes_long_!!"  # 32 bytes
        serialized = shard.serialize(hmac_key=hmac_key)

        # Corrupt HMAC
        data = bytearray(serialized)
        data[-HMAC_SIZE:] = b"X" * HMAC_SIZE  # Corrupt HMAC
        corrupted_data = bytes(data)

        with pytest.raises(ValueError, match="HMAC verification failed"):
            XetShard.deserialize(corrupted_data, hmac_key=hmac_key)

    def test_multiple_files(self):
        """Test shard with multiple files."""
        shard = XetShard()

        for i in range(5):
            shard.add_file_info(
                file_path=f"/file{i}.txt",
                file_hash=bytes([i] * 32),
                xorb_refs=[bytes([i + 10] * 32)],
                total_size=1000 * (i + 1),
            )

        assert len(shard.files) == 5

        # Serialize and deserialize
        serialized = shard.serialize()
        deserialized = XetShard.deserialize(serialized)

        assert len(deserialized.files) == 5
        for i in range(5):
            assert deserialized.files[i]["path"] == f"/file{i}.txt"

    def test_large_shard(self):
        """Test shard with many chunks and xorbs."""
        shard = XetShard()

        # Add many chunks
        for i in range(100):
            shard.add_chunk_hash(bytes([i % 256] * 32))

        # Add many xorbs
        for i in range(50):
            shard.add_xorb_hash(bytes([i % 256] * 32))

        assert len(shard.chunks) == 100
        assert len(shard.xorbs) == 50

        # Serialize and deserialize
        serialized = shard.serialize()
        deserialized = XetShard.deserialize(serialized)

        assert len(deserialized.chunks) == 100
        assert len(deserialized.xorbs) == 50

    def test_serialize_without_hmac(self):
        """Test serialization without HMAC key."""
        shard = XetShard()
        shard.add_file_info(
            file_path="/test/file.txt",
            file_hash=b"X" * 32,
            xorb_refs=[],
            total_size=100,
        )

        serialized = shard.serialize()

        # Should still be deserializable (without HMAC verification)
        deserialized = XetShard.deserialize(serialized)

        assert len(deserialized.files) == 1

    def test_file_info_with_multiple_xorbs(self):
        """Test file info with multiple xorb references."""
        shard = XetShard()
        xorb_refs = [bytes([i] * 32) for i in range(10)]

        shard.add_file_info(
            file_path="/large/file.txt",
            file_hash=b"X" * 32,
            xorb_refs=xorb_refs,
            total_size=1024 * 1024,
        )

        assert len(shard.files[0]["xorbs"]) == 10

        # Serialize and deserialize
        serialized = shard.serialize()
        deserialized = XetShard.deserialize(serialized)

        assert len(deserialized.files[0]["xorbs"]) == 10

    def test_deserialize_short_data(self):
        """Test deserialization with data too short."""
        short_data = b"SHAR" + b"X" * 10

        with pytest.raises(ValueError, match="too short"):
            XetShard.deserialize(short_data)

    def test_deserialize_invalid_data_structure(self):
        """Test deserialization with invalid data structure."""
        # Create invalid shard data (wrong structure)
        invalid_data = b"SHAR" + bytes([1]) + b"X" * 100

        # Should raise ValueError
        with pytest.raises((ValueError, struct.error)):
            XetShard.deserialize(invalid_data)

    def test_deserialize_short_path_length(self):
        """Test deserialization with short path length."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)
        data = shard.serialize()

        # Truncate data to make path length read fail
        truncated = data[:SHARD_HEADER_SIZE + 3]  # Not enough for path length

        with pytest.raises(ValueError, match="too short for path length"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_path(self):
        """Test deserialization with short path data."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)
        data = shard.serialize()

        # Corrupt path length to be larger than available data
        data = bytearray(data)
        # Header structure: magic (4) + version (1) + flags (1) + reserved1 (2) + file_count (4) + xorb_count (4) + chunk_count (4) + reserved2 (4) = 24 bytes
        # After header (24 bytes), file info section starts
        # For each file: path_len (4), path, hash (32), size (8), xorb_count (4), xorbs (32 each)
        # path_len is at offset 24 (after header)
        offset = SHARD_HEADER_SIZE  # 24 bytes (start of file info section)
        struct.pack_into("I", data, offset, 999999)  # Corrupt path_len (first 4 bytes after header)
        data = bytes(data)

        with pytest.raises(ValueError, match="too short for path"):
            XetShard.deserialize(data)

    def test_deserialize_short_file_hash(self):
        """Test deserialization with short file hash."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)
        data = shard.serialize()

        # Truncate after path but before file hash
        truncated = data[:SHARD_HEADER_SIZE + 4 + len("test.txt") + 31]  # 31 bytes for hash (need 32)

        with pytest.raises(ValueError, match="too short for file hash"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_file_size(self):
        """Test deserialization with short file size."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)
        data = shard.serialize()

        # Truncate after hash but before file size
        truncated = data[:SHARD_HEADER_SIZE + 4 + len("test.txt") + 32 + 7]  # 7 bytes for size (need 8)

        with pytest.raises(ValueError, match="too short for file size"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_xorb_count(self):
        """Test deserialization with short xorb count."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [b"Y" * 32], 100)
        data = shard.serialize()

        # Truncate after file size but before xorb count
        offset = SHARD_HEADER_SIZE + 4 + len("test.txt") + 32 + 8
        truncated = data[:offset + 3]  # 3 bytes for xorb count (need 4)

        with pytest.raises(ValueError, match="too short for xorb count"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_xorb_ref(self):
        """Test deserialization with short xorb ref."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [b"Y" * 32], 100)
        data = shard.serialize()

        # Truncate after xorb count but before xorb ref
        offset = SHARD_HEADER_SIZE + 4 + len("test.txt") + 32 + 8 + 4  # After xorb count
        truncated = data[:offset + 31]  # 31 bytes for xorb ref (need 32)

        with pytest.raises(ValueError, match="too short for xorb ref"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_xorb_hash(self):
        """Test deserialization with short xorb hash."""
        shard = XetShard()
        shard.add_xorb_hash(b"X" * 32)
        data = shard.serialize()

        # Truncate after file section but before xorb hash
        offset = SHARD_HEADER_SIZE  # After header
        truncated = data[:offset + 31]  # 31 bytes for xorb hash (need 32)

        with pytest.raises(ValueError, match="too short for xorb hash"):
            XetShard.deserialize(truncated)

    def test_deserialize_short_chunk_hash(self):
        """Test deserialization with short chunk hash."""
        shard = XetShard()
        shard.add_chunk_hash(b"X" * 32)
        data = shard.serialize()

        # Truncate after header but before chunk hash
        # Header structure: magic (4) + version (1) + flags (1) + reserved1 (2) + file_count (4) + xorb_count (4) + chunk_count (4) + reserved2 (4) = 24 bytes
        # After header: file_count=0, xorb_count=0, chunk_count=1 are in the header
        # CAS info section starts after file info section (which is empty since file_count=0)
        # So chunk hashes start right after header (24 bytes)
        # Truncate at 24 + 31 = 55 bytes (need 56 for full chunk hash)
        offset = SHARD_HEADER_SIZE  # 24 bytes (start of CAS info section)
        truncated = data[:offset + 31]  # 31 bytes for chunk hash (need 32)

        with pytest.raises(ValueError, match="too short for chunk hash"):
            XetShard.deserialize(truncated)

    def test_get_file_by_path(self):
        """Test getting file by path."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)

        file_info = shard.get_file_by_path("test.txt")

        assert file_info is not None
        assert file_info["path"] == "test.txt"

    def test_get_file_by_path_not_found(self):
        """Test getting file by path that doesn't exist."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)

        file_info = shard.get_file_by_path("nonexistent.txt")

        assert file_info is None

    def test_deserialize_with_hmac_no_key(self):
        """Test deserializing shard with HMAC but no key provided."""
        shard = XetShard()
        shard.add_file_info("test.txt", b"X" * 32, [], 100)
        
        # Serialize with HMAC
        hmac_key = b"test_key_123456789012345678901234567890"  # 32 bytes
        data = shard.serialize(hmac_key=hmac_key)

        # Deserialize without key (should not verify but should parse)
        deserialized = XetShard.deserialize(data, hmac_key=None)

        # Should deserialize but HMAC not verified
        assert len(deserialized.files) == 1

    def test_get_file_count(self):
        """Test getting file count."""
        shard = XetShard()
        shard.add_file_info("file1.txt", b"X" * 32, [], 100)
        shard.add_file_info("file2.txt", b"Y" * 32, [], 200)

        count = shard.get_file_count()

        assert count == 2

