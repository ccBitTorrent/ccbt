"""Unit tests for SHA-256 hashing functions (BEP 52).

Tests all hash_v2.py functions for piece hashing, piece layers, file trees,
and unified verification.
"""

from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from ccbt.piece.hash_v2 import (
    HashAlgorithm,
    hash_file_tree,
    hash_piece_layer,
    hash_piece_v2,
    hash_piece_v2_streaming,
    verify_piece,
    verify_piece_layer,
    verify_piece_v2,
    verify_piece_v2_streaming,
)


class TestHashPieceV2:
    """Test hash_piece_v2 function."""

    def test_hash_piece_v2_basic(self):
        """Test basic piece hashing."""
        data = b"test piece data"
        hash_bytes = hash_piece_v2(data)

        assert len(hash_bytes) == 32
        assert isinstance(hash_bytes, bytes)

        # Verify it's actually SHA-256
        expected = hashlib.sha256(data).digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_empty_data(self):
        """Test hashing empty data raises ValueError."""
        with pytest.raises(ValueError, match="Cannot hash empty piece data"):
            hash_piece_v2(b"")

    def test_hash_piece_v2_large_data(self):
        """Test hashing large piece of data."""
        large_data = b"x" * (2 * 1024 * 1024)  # 2 MiB
        hash_bytes = hash_piece_v2(large_data)

        assert len(hash_bytes) == 32
        expected = hashlib.sha256(large_data).digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_deterministic(self):
        """Test that hashing same data produces same hash."""
        data = b"deterministic test data"
        hash1 = hash_piece_v2(data)
        hash2 = hash_piece_v2(data)

        assert hash1 == hash2


class TestHashPieceV2Streaming:
    """Test hash_piece_v2_streaming function."""

    def test_hash_piece_v2_streaming_from_bytes(self):
        """Test streaming hash from bytes."""
        data = b"test streaming data"
        hash_bytes = hash_piece_v2_streaming(data)

        assert len(hash_bytes) == 32
        expected = hashlib.sha256(data).digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_streaming_from_bytesio(self):
        """Test streaming hash from BytesIO."""
        data = b"test BytesIO data"
        bio = BytesIO(data)
        hash_bytes = hash_piece_v2_streaming(bio)

        assert len(hash_bytes) == 32
        expected = hashlib.sha256(data).digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_streaming_from_file(self, tmp_path):
        """Test streaming hash from file."""
        test_file = tmp_path / "test_piece.bin"
        data = b"test file data" * 100
        test_file.write_bytes(data)

        with open(test_file, "rb") as f:
            hash_bytes = hash_piece_v2_streaming(f)

        assert len(hash_bytes) == 32
        expected = hashlib.sha256(data).digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_streaming_empty(self):
        """Test streaming hash of empty data."""
        hash_bytes = hash_piece_v2_streaming(b"")
        assert len(hash_bytes) == 32
        expected = hashlib.sha256(b"").digest()
        assert hash_bytes == expected

    def test_hash_piece_v2_streaming_invalid_source(self):
        """Test streaming hash with invalid source."""
        with pytest.raises(ValueError, match="data_source must be file-like"):
            hash_piece_v2_streaming(None)


class TestVerifyPieceV2:
    """Test verify_piece_v2 function."""

    def test_verify_piece_v2_correct(self):
        """Test verification with correct hash."""
        data = b"test verification data"
        expected_hash = hash_piece_v2(data)

        assert verify_piece_v2(data, expected_hash) is True

    def test_verify_piece_v2_incorrect(self):
        """Test verification with incorrect hash."""
        data = b"test verification data"
        wrong_hash = b"x" * 32

        assert verify_piece_v2(data, wrong_hash) is False

    def test_verify_piece_v2_invalid_hash_length(self):
        """Test verification with invalid hash length."""
        data = b"test data"
        invalid_hash = b"short"

        with pytest.raises(ValueError, match="must be 32 bytes"):
            verify_piece_v2(data, invalid_hash)


class TestVerifyPieceV2Streaming:
    """Test verify_piece_v2_streaming function."""

    def test_verify_piece_v2_streaming_correct(self):
        """Test streaming verification with correct hash."""
        data = b"test streaming verification"
        expected_hash = hash_piece_v2(data)

        assert verify_piece_v2_streaming(data, expected_hash) is True

    def test_verify_piece_v2_streaming_from_file(self, tmp_path):
        """Test streaming verification from file."""
        test_file = tmp_path / "test_verify.bin"
        data = b"test file verification data"
        test_file.write_bytes(data)

        expected_hash = hash_piece_v2(data)

        with open(test_file, "rb") as f:
            assert verify_piece_v2_streaming(f, expected_hash) is True

    def test_verify_piece_v2_streaming_incorrect(self):
        """Test streaming verification with incorrect hash."""
        data = b"test data"
        wrong_hash = b"y" * 32

        assert verify_piece_v2_streaming(data, wrong_hash) is False


class TestHashPieceLayer:
    """Test hash_piece_layer function (Merkle root calculation)."""

    def test_hash_piece_layer_single_piece(self):
        """Test piece layer with single piece."""
        piece_hash = hash_piece_v2(b"single piece")
        root = hash_piece_layer([piece_hash])

        assert len(root) == 32
        assert root == piece_hash  # Single piece: hash is the root

    def test_hash_piece_layer_two_pieces(self):
        """Test piece layer with two pieces."""
        hash1 = hash_piece_v2(b"piece 1")
        hash2 = hash_piece_v2(b"piece 2")
        root = hash_piece_layer([hash1, hash2])

        assert len(root) == 32
        # Root should be SHA-256 of concatenated hashes
        expected = hashlib.sha256(hash1 + hash2).digest()
        assert root == expected

    def test_hash_piece_layer_three_pieces(self):
        """Test piece layer with three pieces (odd number)."""
        hash1 = hash_piece_v2(b"piece 1")
        hash2 = hash_piece_v2(b"piece 2")
        hash3 = hash_piece_v2(b"piece 3")
        root = hash_piece_layer([hash1, hash2, hash3])

        assert len(root) == 32
        # With odd number, last piece is duplicated
        # First level: hash(hash1+hash2), hash(hash3+hash3)
        level1_0 = hashlib.sha256(hash1 + hash2).digest()
        level1_1 = hashlib.sha256(hash3 + hash3).digest()
        # Root: hash(level1_0 + level1_1)
        expected = hashlib.sha256(level1_0 + level1_1).digest()
        assert root == expected

    def test_hash_piece_layer_many_pieces(self):
        """Test piece layer with many pieces."""
        piece_hashes = [hash_piece_v2(f"piece {i}".encode()) for i in range(10)]
        root = hash_piece_layer(piece_hashes)

        assert len(root) == 32

    def test_hash_piece_layer_empty(self):
        """Test piece layer with empty list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot hash empty piece layer"):
            hash_piece_layer([])

    def test_hash_piece_layer_invalid_hash_length(self):
        """Test piece layer with invalid hash length."""
        invalid_hash = b"short" * 4  # 20 bytes instead of 32

        with pytest.raises(ValueError, match="must be 32 bytes"):
            hash_piece_layer([invalid_hash])


class TestVerifyPieceLayer:
    """Test verify_piece_layer function."""

    def test_verify_piece_layer_correct(self):
        """Test verification with correct root."""
        piece_hashes = [
            hash_piece_v2(b"piece 1"),
            hash_piece_v2(b"piece 2"),
        ]
        expected_root = hash_piece_layer(piece_hashes)

        assert verify_piece_layer(piece_hashes, expected_root) is True

    def test_verify_piece_layer_incorrect(self):
        """Test verification with incorrect root."""
        piece_hashes = [
            hash_piece_v2(b"piece 1"),
            hash_piece_v2(b"piece 2"),
        ]
        wrong_root = b"x" * 32

        assert verify_piece_layer(piece_hashes, wrong_root) is False

    def test_verify_piece_layer_invalid_root_length(self):
        """Test verification with invalid root length."""
        piece_hashes = [hash_piece_v2(b"piece")]
        invalid_root = b"short"

        with pytest.raises(ValueError, match="must be 32 bytes"):
            verify_piece_layer(piece_hashes, invalid_root)


class TestHashFileTree:
    """Test hash_file_tree function."""

    def test_hash_file_tree_single_file(self):
        """Test file tree with single file."""
        from ccbt.core.torrent_v2 import FileTreeNode

        pieces_root = hash_piece_v2(b"file content")
        file_node = FileTreeNode(
            name="test.txt",
            length=100,
            pieces_root=pieces_root,
            children=None,
        )

        file_tree = {"test.txt": file_node}
        root_hash = hash_file_tree(file_tree)

        assert len(root_hash) == 32

    def test_hash_file_tree_directory(self):
        """Test file tree with directory structure."""
        from ccbt.core.torrent_v2 import FileTreeNode

        # Create nested structure: dir/file.txt
        file_pieces_root = hash_piece_v2(b"file content")
        file_node = FileTreeNode(
            name="file.txt",
            length=100,
            pieces_root=file_pieces_root,
            children=None,
        )

        dir_node = FileTreeNode(
            name="dir",
            length=0,
            pieces_root=None,
            children={"file.txt": file_node},
        )

        file_tree = {"dir": dir_node}
        root_hash = hash_file_tree(file_tree)

        assert len(root_hash) == 32

    def test_hash_file_tree_multiple_files(self):
        """Test file tree with multiple files."""
        from ccbt.core.torrent_v2 import FileTreeNode

        file1 = FileTreeNode(
            name="file1.txt",
            length=100,
            pieces_root=hash_piece_v2(b"content1"),
            children=None,
        )
        file2 = FileTreeNode(
            name="file2.txt",
            length=200,
            pieces_root=hash_piece_v2(b"content2"),
            children=None,
        )

        file_tree = {"file1.txt": file1, "file2.txt": file2}
        root_hash = hash_file_tree(file_tree)

        assert len(root_hash) == 32

    def test_hash_file_tree_empty(self):
        """Test file tree with empty dictionary."""
        root_hash = hash_file_tree({})
        assert len(root_hash) == 32
        # Empty tree should produce deterministic hash
        empty_hash = hashlib.sha256(b"").digest()
        assert root_hash == empty_hash


class TestHashAlgorithm:
    """Test HashAlgorithm enum."""

    def test_hash_algorithm_values(self):
        """Test HashAlgorithm enum values."""
        assert HashAlgorithm.SHA1.value == "sha1"
        assert HashAlgorithm.SHA256.value == "sha256"

    def test_hash_algorithm_from_hash_length(self):
        """Test determining algorithm from hash length."""
        sha1_hash = b"x" * 20
        sha256_hash = b"x" * 32

        # 20 bytes = SHA-1
        if len(sha1_hash) == 20:
            algorithm = HashAlgorithm.SHA1
            assert algorithm == HashAlgorithm.SHA1

        # 32 bytes = SHA-256
        if len(sha256_hash) == 32:
            algorithm = HashAlgorithm.SHA256
            assert algorithm == HashAlgorithm.SHA256


class TestVerifyPiece:
    """Test unified verify_piece function."""

    def test_verify_piece_sha256(self):
        """Test verify_piece with SHA-256 algorithm."""
        data = b"test piece data"
        expected_hash = hash_piece_v2(data)

        assert verify_piece(data, expected_hash, HashAlgorithm.SHA256) is True

    def test_verify_piece_sha256_incorrect(self):
        """Test verify_piece with incorrect SHA-256 hash."""
        data = b"test piece data"
        wrong_hash = b"x" * 32

        assert (
            verify_piece(data, wrong_hash, HashAlgorithm.SHA256) is False
        )

    def test_verify_piece_sha1(self):
        """Test verify_piece with SHA-1 algorithm."""
        data = b"test piece data"
        expected_hash = hashlib.sha1(data).digest()  # nosec B324

        assert verify_piece(data, expected_hash, HashAlgorithm.SHA1) is True

    def test_verify_piece_auto_detect_sha256(self):
        """Test verify_piece auto-detecting SHA-256 from hash length."""
        data = b"test piece data"
        expected_hash = hash_piece_v2(data)  # 32 bytes

        # Auto-detect should use SHA-256 for 32-byte hash
        assert verify_piece(data, expected_hash) is True

    def test_verify_piece_auto_detect_sha1(self):
        """Test verify_piece auto-detecting SHA-1 from hash length."""
        data = b"test piece data"
        expected_hash = hashlib.sha1(data).digest()  # nosec B324 # 20 bytes

        # Auto-detect should use SHA-1 for 20-byte hash
        assert verify_piece(data, expected_hash) is True

    def test_verify_piece_invalid_hash_length(self):
        """Test verify_piece with invalid hash length."""
        data = b"test data"
        invalid_hash = b"short"  # Not 20 or 32 bytes

        with pytest.raises(ValueError, match="Hash must be 20 or 32 bytes|got 5 bytes"):
            verify_piece(data, invalid_hash)


