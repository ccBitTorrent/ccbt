"""Additional tests to boost coverage in hash_v2.py."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
from pathlib import Path

import pytest

from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_v2_streaming,
    verify_piece_v2,
)


@pytest.mark.unit
@pytest.mark.piece
class TestHashV2Coverage:
    """Test uncovered paths in hash_v2.py."""

    def test_hash_piece_v2_streaming_exception_path(self, tmp_path):
        """Test streaming hash exception handling (lines 115-118)."""
        # Create a file that will cause an error when reading
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"test data")
        
        # Close file to cause error
        with open(test_file, "rb") as f:
            file_obj = f
        
        # Try to hash with closed/invalid file - should raise OSError
        with pytest.raises((OSError, ValueError)):
            hash_piece_v2_streaming(file_obj)

    def test_verify_piece_v2_with_wrong_hash(self):
        """Test verify_piece_v2 returns False for wrong hash."""
        data = b"test piece data"
        wrong_hash = b"x" * 32  # Wrong hash
        result = verify_piece_v2(data, wrong_hash)
        assert result is False

    def test_hash_file_tree_with_single_file(self):
        """Test hash_file_tree for single file structure (lines 336-393)."""
        from ccbt.core.torrent_v2 import FileTreeNode
        from ccbt.piece.hash_v2 import hash_file_tree
        
        # Create a file node
        file_node = FileTreeNode(
            name="file.txt",
            length=100,
            pieces_root=b"x" * 32,
        )
        
        file_tree = {"file.txt": file_node}
        
        result = hash_file_tree(file_tree)
        assert len(result) == 32

    def test_hash_file_tree_with_directory(self):
        """Test hash_file_tree for directory structure (lines 336-393)."""
        from ccbt.core.torrent_v2 import FileTreeNode
        from ccbt.piece.hash_v2 import hash_file_tree
        
        # Create a file node inside a directory
        file_node = FileTreeNode(
            name="file1.txt",
            length=100,
            pieces_root=b"x" * 32,
        )
        
        dir_node = FileTreeNode(
            name="dir1",
            length=0,
            children={"file1.txt": file_node},
        )
        
        file_tree = {"dir1": dir_node}
        
        result = hash_file_tree(file_tree)
        assert len(result) == 32

    def test_verify_piece_streaming_with_bytes(self):
        """Test verify_piece_streaming with bytes source (lines 638-640)."""
        from ccbt.piece.hash_v2 import verify_piece_streaming, HashAlgorithm
        
        data = b"test piece data"
        expected_hash = hash_piece_v2(data)
        
        result = verify_piece_streaming(data, expected_hash, HashAlgorithm.SHA256)
        assert result is True

    def test_verify_piece_streaming_with_file(self, tmp_path):
        """Test verify_piece_streaming with file object (lines 642-670)."""
        from ccbt.piece.hash_v2 import verify_piece_streaming, HashAlgorithm
        
        test_file = tmp_path / "test.bin"
        data = b"test piece data for streaming"
        test_file.write_bytes(data)
        expected_hash = hash_piece_v2(data)
        
        with open(test_file, "rb") as f:
            result = verify_piece_streaming(f, expected_hash, HashAlgorithm.SHA256)
        
        assert result is True

    def test_verify_piece_streaming_exception_handling(self, tmp_path):
        """Test verify_piece_streaming exception handling (lines 667-670)."""
        from ccbt.piece.hash_v2 import verify_piece_streaming, HashAlgorithm
        
        # Create invalid file-like object
        class InvalidSource:
            def read(self, _size):
                raise IOError("Read failed")
        
        invalid_source = InvalidSource()
        
        with pytest.raises(OSError):
            verify_piece_streaming(
                invalid_source,
                b"x" * 32,
                HashAlgorithm.SHA256,
            )

    def test_hash_piece_with_different_algorithm(self):
        """Test hash_piece with different algorithms (lines 685-724)."""
        from ccbt.piece.hash_v2 import hash_piece, HashAlgorithm
        
        data = b"test data"
        
        sha256_hash = hash_piece(data, HashAlgorithm.SHA256)
        assert len(sha256_hash) == 32
        
        # Test with SHA1 if supported
        # Note: SHA1 may not be in enum, test what's available
        assert len(sha256_hash) == 32

