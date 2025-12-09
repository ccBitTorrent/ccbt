"""Unit tests for tonic file format.

Tests creation, parsing, round-trip, info hash calculation, and file tree encoding.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]


class TestTonicFormat:
    """Test TonicFile format compliance."""

    @pytest.fixture
    def tonic_file(self):
        """Create TonicFile instance."""
        from ccbt.core.tonic import TonicFile

        return TonicFile()

    @pytest.fixture
    def sample_xet_metadata(self):
        """Create sample XET metadata."""
        from ccbt.models import XetFileMetadata, XetTorrentMetadata

        file_metadata = [
            XetFileMetadata(
                file_path="test1.txt",
                file_hash=b"1" * 32,
                chunk_hashes=[b"a" * 32, b"b" * 32],
                total_size=100,
            ),
            XetFileMetadata(
                file_path="folder/test2.txt",
                file_hash=b"2" * 32,
                chunk_hashes=[b"c" * 32],
                total_size=50,
            ),
        ]

        return XetTorrentMetadata(
            chunk_hashes=[b"a" * 32, b"b" * 32, b"c" * 32],
            file_metadata=file_metadata,
            piece_metadata=[],
            xorb_hashes=[],
        )

    def test_tonic_create(self, tonic_file, sample_xet_metadata):
        """Test creating tonic file."""
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
            sync_mode="best_effort",
        )

        assert isinstance(tonic_data, bytes)
        assert len(tonic_data) > 0

    def test_tonic_parse(self, tonic_file, sample_xet_metadata, tmp_path):
        """Test parsing tonic file."""
        # Create tonic file
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
            sync_mode="best_effort",
        )

        # Write to file
        tonic_path = tmp_path / "test.tonic"
        tonic_path.write_bytes(tonic_data)

        # Parse
        parsed = tonic_file.parse(tonic_path)

        assert parsed["info"]["name"] == "test_folder"
        assert parsed["sync_mode"] == "best_effort"
        assert len(parsed["xet_metadata"]["chunk_hashes"]) == 3

    def test_tonic_round_trip(self, tonic_file, sample_xet_metadata, tmp_path):
        """Test round-trip: create -> parse -> verify."""
        # Create with all fields
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
            git_refs=["abc123", "def456"],
            sync_mode="consensus",
            source_peers=["peer1", "peer2"],
            allowlist_hash=b"x" * 32,
            announce="http://tracker.example.com/announce",
        )

        # Write and parse
        tonic_path = tmp_path / "test.tonic"
        tonic_path.write_bytes(tonic_data)
        parsed = tonic_file.parse(tonic_path)

        # Verify all fields
        assert parsed["info"]["name"] == "test_folder"
        assert parsed["sync_mode"] == "consensus"
        assert parsed["git_refs"] == ["abc123", "def456"]
        assert parsed["source_peers"] == ["peer1", "peer2"]
        assert parsed["allowlist_hash"] == b"x" * 32
        assert parsed["announce"] == "http://tracker.example.com/announce"

    def test_tonic_info_hash_calculation(self, tonic_file, sample_xet_metadata):
        """Test info hash calculation."""
        # Create tonic file
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
        )

        # Write and parse
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tonic") as f:
            f.write(tonic_data)
            tonic_path = f.name

        try:
            parsed = tonic_file.parse(tonic_path)
            info_hash = tonic_file.get_info_hash(parsed)

            # Verify hash is SHA-256 (32 bytes)
            assert len(info_hash) == 32

            # Verify hash is deterministic
            info_hash2 = tonic_file.get_info_hash(parsed)
            assert info_hash == info_hash2

            # Verify hash changes when info changes
            parsed2 = parsed.copy()
            parsed2["info"]["name"] = "different_folder"
            info_hash3 = tonic_file.get_info_hash(parsed2)
            assert info_hash != info_hash3
        finally:
            Path(tonic_path).unlink(missing_ok=True)

    def test_tonic_file_tree_encoding(self, tonic_file, sample_xet_metadata):
        """Test file tree encoding."""
        # Create tonic file
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
        )

        # Write and parse
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tonic") as f:
            f.write(tonic_data)
            tonic_path = f.name

        try:
            parsed = tonic_file.parse(tonic_path)
            file_tree = tonic_file.get_file_tree(parsed)

            # Verify file tree structure
            assert "test1.txt" in file_tree
            assert "folder" in file_tree
            assert "test2.txt" in file_tree["folder"]

            # Verify file metadata
            test1_info = file_tree["test1.txt"]
            if isinstance(test1_info, dict) and "" in test1_info:
                assert test1_info[""]["length"] == 100
        finally:
            Path(tonic_path).unlink(missing_ok=True)

    def test_tonic_file_tree_decoding(self, tonic_file, sample_xet_metadata):
        """Test file tree decoding."""
        # Create tonic file
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
        )

        # Write and parse
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tonic") as f:
            f.write(tonic_data)
            tonic_path = f.name

        try:
            parsed = tonic_file.parse(tonic_path)
            file_tree = tonic_file.get_file_tree(parsed)

            # Verify nested structure
            assert isinstance(file_tree, dict)
            assert "folder" in file_tree
            assert isinstance(file_tree["folder"], dict)
        finally:
            Path(tonic_path).unlink(missing_ok=True)

    def test_tonic_validation(self, tonic_file):
        """Test tonic file validation."""
        from ccbt.core.tonic import TonicError

        # Test missing info
        invalid_data = {b"xet metadata": {b"chunk hashes": []}}
        with pytest.raises(TonicError):
            tonic_file._validate_tonic(invalid_data)

        # Test missing xet metadata
        invalid_data = {b"info": {b"name": b"test"}}
        with pytest.raises(TonicError):
            tonic_file._validate_tonic(invalid_data)

        # Test invalid sync mode
        invalid_data = {
            b"info": {b"name": b"test"},
            b"xet metadata": {b"chunk hashes": []},
            b"sync mode": b"invalid_mode",
        }
        with pytest.raises(TonicError):
            tonic_file._validate_tonic(invalid_data)

        # Test invalid allowlist hash length
        invalid_data = {
            b"info": {b"name": b"test"},
            b"xet metadata": {b"chunk hashes": []},
            b"allowlist hash": b"short",
        }
        with pytest.raises(TonicError):
            tonic_file._validate_tonic(invalid_data)

    def test_tonic_parse_bytes(self, tonic_file, sample_xet_metadata):
        """Test parsing from bytes."""
        # Create tonic file
        tonic_data = tonic_file.create(
            folder_name="test_folder",
            xet_metadata=sample_xet_metadata,
        )

        # Parse from bytes
        parsed = tonic_file.parse_bytes(tonic_data)

        assert parsed["info"]["name"] == "test_folder"
        assert len(parsed["xet_metadata"]["chunk_hashes"]) == 3









