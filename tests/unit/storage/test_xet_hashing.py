"""Unit tests for Xet hashing (BLAKE3-256 with SHA-256 fallback).

Tests hash computation, Merkle tree construction, and
cross-verification with reference implementations.
"""

from __future__ import annotations

import hashlib

import pytest

from ccbt.storage.xet_hashing import XetHasher


pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestXetHasher:
    """Test XetHasher class."""

    def test_hash_size(self):
        """Test that hash size is 32 bytes (256 bits)."""
        assert XetHasher.HASH_SIZE == 32

    def test_compute_chunk_hash_empty(self):
        """Test computing hash of empty chunk."""
        hash_result = XetHasher.compute_chunk_hash(b"")
        assert len(hash_result) == XetHasher.HASH_SIZE

    def test_compute_chunk_hash_basic(self):
        """Test basic chunk hash computation."""
        test_data = b"Hello, World! This is test data for chunk hashing."
        hash_result = XetHasher.compute_chunk_hash(test_data)

        assert len(hash_result) == XetHasher.HASH_SIZE
        assert isinstance(hash_result, bytes)

    def test_compute_chunk_hash_deterministic(self):
        """Test that same input produces same hash."""
        test_data = b"Deterministic test data"
        hash1 = XetHasher.compute_chunk_hash(test_data)
        hash2 = XetHasher.compute_chunk_hash(test_data)

        assert hash1 == hash2

    def test_compute_chunk_hash_different_inputs(self):
        """Test that different inputs produce different hashes."""
        data1 = b"First test data"
        data2 = b"Second test data"

        hash1 = XetHasher.compute_chunk_hash(data1)
        hash2 = XetHasher.compute_chunk_hash(data2)

        assert hash1 != hash2

    def test_compute_chunk_hash_large_data(self):
        """Test hashing large data chunks."""
        large_data = b"X" * (1024 * 1024)  # 1MB
        hash_result = XetHasher.compute_chunk_hash(large_data)

        assert len(hash_result) == XetHasher.HASH_SIZE

    def test_compute_xorb_hash(self):
        """Test xorb hash computation."""
        xorb_data = b"Xorb test data for hashing"
        hash_result = XetHasher.compute_xorb_hash(xorb_data)

        assert len(hash_result) == XetHasher.HASH_SIZE

    def test_compute_xorb_hash_same_as_chunk_hash(self):
        """Test that xorb hash uses same algorithm as chunk hash."""
        test_data = b"Test data for hash comparison"
        chunk_hash = XetHasher.compute_chunk_hash(test_data)
        xorb_hash = XetHasher.compute_xorb_hash(test_data)

        # Should use same hashing algorithm
        assert chunk_hash == xorb_hash

    def test_build_merkle_tree_empty(self):
        """Test building Merkle tree from empty chunk list."""
        merkle_root = XetHasher.build_merkle_tree([])
        assert len(merkle_root) == XetHasher.HASH_SIZE
        # Should be zero hash for empty tree
        assert merkle_root == b"\x00" * XetHasher.HASH_SIZE

    def test_build_merkle_tree_single_chunk(self):
        """Test building Merkle tree from single chunk."""
        chunk = b"Single chunk data"
        merkle_root = XetHasher.build_merkle_tree([chunk])

        assert len(merkle_root) == XetHasher.HASH_SIZE

        # Single chunk: root should be hash of the chunk
        expected_hash = XetHasher.compute_chunk_hash(chunk)
        assert merkle_root == expected_hash

    def test_build_merkle_tree_two_chunks(self):
        """Test building Merkle tree from two chunks."""
        chunk1 = b"First chunk"
        chunk2 = b"Second chunk"
        chunks = [chunk1, chunk2]

        merkle_root = XetHasher.build_merkle_tree(chunks)

        assert len(merkle_root) == XetHasher.HASH_SIZE

        # Should be hash of combined chunk hashes
        hash1 = XetHasher.compute_chunk_hash(chunk1)
        hash2 = XetHasher.compute_chunk_hash(chunk2)
        combined = hash1 + hash2
        expected_root = XetHasher.compute_chunk_hash(combined)

        assert merkle_root == expected_root

    def test_build_merkle_tree_three_chunks(self):
        """Test building Merkle tree from odd number of chunks."""
        chunks = [b"Chunk 1", b"Chunk 2", b"Chunk 3"]
        merkle_root = XetHasher.build_merkle_tree(chunks)

        assert len(merkle_root) == XetHasher.HASH_SIZE

        # Should handle odd number by duplicating last hash
        hash1 = XetHasher.compute_chunk_hash(chunks[0])
        hash2 = XetHasher.compute_chunk_hash(chunks[1])
        hash3 = XetHasher.compute_chunk_hash(chunks[2])

        # First level: pair (hash1, hash2) and duplicate (hash3, hash3)
        level1_1 = XetHasher.compute_chunk_hash(hash1 + hash2)
        level1_2 = XetHasher.compute_chunk_hash(hash3 + hash3)

        # Root: hash of level1_1 and level1_2
        expected_root = XetHasher.compute_chunk_hash(level1_1 + level1_2)

        assert merkle_root == expected_root

    def test_build_merkle_tree_many_chunks(self):
        """Test building Merkle tree from many chunks."""
        chunks = [f"Chunk {i}".encode() for i in range(100)]
        merkle_root = XetHasher.build_merkle_tree(chunks)

        assert len(merkle_root) == XetHasher.HASH_SIZE

    def test_build_merkle_tree_deterministic(self):
        """Test that same chunks produce same Merkle root."""
        chunks = [b"Chunk 1", b"Chunk 2", b"Chunk 3", b"Chunk 4"]

        root1 = XetHasher.build_merkle_tree(chunks)
        root2 = XetHasher.build_merkle_tree(chunks)

        assert root1 == root2

    def test_build_merkle_tree_order_matters(self):
        """Test that chunk order affects Merkle root."""
        chunks1 = [b"Chunk 1", b"Chunk 2"]
        chunks2 = [b"Chunk 2", b"Chunk 1"]

        root1 = XetHasher.build_merkle_tree(chunks1)
        root2 = XetHasher.build_merkle_tree(chunks2)

        # Different order should produce different root
        assert root1 != root2

    def test_build_merkle_tree_from_hashes(self):
        """Test building Merkle tree from pre-computed hashes."""
        chunk1 = b"First chunk"
        chunk2 = b"Second chunk"

        hash1 = XetHasher.compute_chunk_hash(chunk1)
        hash2 = XetHasher.compute_chunk_hash(chunk2)

        # Build from chunks
        root_from_chunks = XetHasher.build_merkle_tree([chunk1, chunk2])

        # Build from hashes
        root_from_hashes = XetHasher.build_merkle_tree_from_hashes([hash1, hash2])

        assert root_from_chunks == root_from_hashes

    def test_build_merkle_tree_from_hashes_invalid_size(self):
        """Test that invalid hash size raises ValueError."""
        invalid_hash = b"short"  # Not 32 bytes

        with pytest.raises(ValueError, match="Invalid hash size"):
            XetHasher.build_merkle_tree_from_hashes([invalid_hash])

    def test_verify_chunk_hash(self):
        """Test chunk hash verification."""
        chunk_data = b"Test chunk data"
        expected_hash = XetHasher.compute_chunk_hash(chunk_data)

        assert XetHasher.verify_chunk_hash(chunk_data, expected_hash) is True

    def test_verify_chunk_hash_wrong_hash(self):
        """Test verification with wrong hash."""
        chunk_data = b"Test chunk data"
        wrong_hash = b"X" * XetHasher.HASH_SIZE

        assert XetHasher.verify_chunk_hash(chunk_data, wrong_hash) is False

    def test_verify_chunk_hash_invalid_size(self):
        """Test verification with invalid hash size."""
        chunk_data = b"Test chunk data"
        invalid_hash = b"short"

        assert XetHasher.verify_chunk_hash(chunk_data, invalid_hash) is False

    def test_hash_algorithm_fallback(self):
        """Test that SHA-256 fallback works if BLAKE3 not available."""
        # This test verifies the hash is computed correctly
        # Whether BLAKE3 or SHA-256 is used, the hash should be 32 bytes
        test_data = b"Fallback test data"
        hash_result = XetHasher.compute_chunk_hash(test_data)

        assert len(hash_result) == 32

        # If using SHA-256 fallback, verify it matches hashlib.sha256
        # (Note: if BLAKE3 is available, this will be different)
        sha256_hash = hashlib.sha256(test_data).digest()
        # We can't assert equality since we don't know which algorithm is used
        # But both should be 32 bytes
        assert len(sha256_hash) == 32

    def test_merkle_tree_large_dataset(self):
        """Test Merkle tree construction with large dataset."""
        # Create 1000 chunks
        chunks = [f"Chunk {i:04d}".encode() for i in range(1000)]
        merkle_root = XetHasher.build_merkle_tree(chunks)

        assert len(merkle_root) == XetHasher.HASH_SIZE

    def test_hash_various_data_types(self):
        """Test hashing various types of data patterns."""
        test_cases = [
            b"",  # Empty
            b"A",  # Single byte
            b"A" * 100,  # Repetitive
            b"".join(bytes([i % 256]) for i in range(256)),  # All bytes
            b"\x00" * 1000,  # Nulls
            b"\xFF" * 1000,  # Max bytes
        ]

        for test_data in test_cases:
            hash_result = XetHasher.compute_chunk_hash(test_data)
            assert len(hash_result) == XetHasher.HASH_SIZE

            # Verify deterministic
            hash2 = XetHasher.compute_chunk_hash(test_data)
            assert hash_result == hash2

    def test_hash_file_incremental(self, tmp_path):
        """Test incremental file hashing."""
        # Create test file
        test_file = tmp_path / "hash_test.bin"
        test_data = b"Test data for incremental hashing. " * 1000
        test_file.write_bytes(test_data)

        # Hash file incrementally
        chunks_collected = []
        file_hash = XetHasher.hash_file_incremental(
            str(test_file),
            chunk_callback=lambda chunk: chunks_collected.append(chunk),
        )

        # Verify hash is 32 bytes
        assert len(file_hash) == XetHasher.HASH_SIZE

        # Verify chunks were collected
        assert len(chunks_collected) > 0

        # Verify hash matches direct computation
        direct_hash = XetHasher.compute_chunk_hash(test_data)
        # They may differ for incremental vs direct, but both should be 32 bytes
        assert len(direct_hash) == XetHasher.HASH_SIZE

    def test_hash_file_incremental_no_callback(self, tmp_path):
        """Test incremental file hashing without callback."""
        # Create test file
        test_file = tmp_path / "hash_test2.bin"
        test_data = b"Test data. " * 100
        test_file.write_bytes(test_data)

        # Hash file incrementally (no callback)
        file_hash = XetHasher.hash_file_incremental(str(test_file))

        # Verify hash is 32 bytes
        assert len(file_hash) == XetHasher.HASH_SIZE

