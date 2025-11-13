"""Unit tests for FastResumeData model.

Tests cover:
- Model creation and validation
- Piece bitmap encoding/decoding
- Serialization/deserialization
- Peer state management
- Upload statistics
- File selection state
- Queue state
- Version compatibility
"""

from __future__ import annotations

import gzip
import time
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.storage]

from ccbt.models import DownloadStats
from ccbt.storage.resume_data import FastResumeData


class TestFastResumeDataCreation:
    """Test FastResumeData model creation."""

    def test_create_minimal_resume_data(self):
        """Test creating minimal resume data."""
        info_hash = b"\x00" * 20
        resume_data = FastResumeData(info_hash=info_hash)

        assert resume_data.info_hash == info_hash
        assert resume_data.version == 1
        assert resume_data.piece_completion_bitmap == b""
        assert resume_data.peer_connections_state == {}
        assert resume_data.upload_statistics == {}
        assert resume_data.file_selection_state == {}
        assert resume_data.queue_position is None
        assert resume_data.queue_priority is None
        assert resume_data.created_at > 0
        assert resume_data.updated_at > 0

    def test_create_with_all_fields(self):
        """Test creating resume data with all fields."""
        info_hash = b"\x01" * 20
        resume_data = FastResumeData(
            info_hash=info_hash,
            version=1,
            piece_completion_bitmap=b"test_bitmap",
            peer_connections_state={"peers": []},
            upload_statistics={"bytes_uploaded": 1000},
            file_selection_state={0: {"selected": True}},
            queue_position=0,
            queue_priority="high",
        )

        assert resume_data.info_hash == info_hash
        assert resume_data.version == 1
        assert resume_data.piece_completion_bitmap == b"test_bitmap"
        assert resume_data.queue_position == 0
        assert resume_data.queue_priority == "high"

    def test_info_hash_validation(self):
        """Test info hash validation."""
        # Valid 20-byte hash
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        assert resume_data.info_hash == b"\x00" * 20

        # Invalid hash length
        with pytest.raises(Exception):  # Pydantic validation error
            FastResumeData(info_hash=b"\x00" * 19)

        with pytest.raises(Exception):
            FastResumeData(info_hash=b"\x00" * 21)

    def test_version_validation(self):
        """Test version field validation."""
        # Valid version
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=1)
        assert resume_data.version == 1

        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=100)
        assert resume_data.version == 100

        # Invalid version (too low)
        with pytest.raises(Exception):
            FastResumeData(info_hash=b"\x00" * 20, version=0)

        # Invalid version (too high)
        with pytest.raises(Exception):
            FastResumeData(info_hash=b"\x00" * 20, version=101)


class TestPieceBitmapEncoding:
    """Test piece bitmap encoding and decoding."""

    def test_encode_empty_pieces(self):
        """Test encoding empty piece set."""
        bitmap = FastResumeData.encode_piece_bitmap(set(), 100)
        assert isinstance(bitmap, bytes)
        assert len(bitmap) > 0  # Should be compressed

        # Decode should return empty set
        decoded = FastResumeData.decode_piece_bitmap(bitmap, 100)
        assert decoded == set()

    def test_encode_single_piece(self):
        """Test encoding single piece."""
        verified = {0}
        total = 100
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_multiple_pieces(self):
        """Test encoding multiple pieces."""
        verified = {0, 1, 5, 10, 99}
        total = 100
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_all_pieces(self):
        """Test encoding all pieces."""
        total = 100
        verified = set(range(total))
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_large_torrent(self):
        """Test encoding large torrent (10000 pieces)."""
        total = 10000
        verified = {0, 100, 5000, 9999}
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_zero_total_pieces(self):
        """Test encoding with zero total pieces."""
        bitmap = FastResumeData.encode_piece_bitmap(set(), 0)
        assert isinstance(bitmap, bytes)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, 0)
        assert decoded == set()

    def test_decode_corrupted_bitmap(self):
        """Test decoding corrupted bitmap."""
        # Invalid gzip data
        corrupted = b"not_valid_gzip"
        decoded = FastResumeData.decode_piece_bitmap(corrupted, 100)
        assert decoded == set()  # Should return empty set on error

        # Empty data
        decoded = FastResumeData.decode_piece_bitmap(b"", 100)
        assert decoded == set()

    def test_encode_out_of_range_pieces(self):
        """Test encoding with out-of-range piece indices."""
        total = 100
        # Include invalid indices - they should be filtered
        verified = {0, 1, 150, -1}  # 150 and -1 are invalid
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == {0, 1}  # Only valid pieces


class TestPeerConnectionsState:
    """Test peer connections state management."""

    def test_set_peer_connections_state(self):
        """Test setting peer connections state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        peer_states = [
            {"peer_key": "peer1", "pieces": {0, 1, 2}},
            {"peer_key": "peer2", "pieces": {3, 4, 5}},
        ]

        time.sleep(0.01)  # Ensure timestamp changes
        resume_data.set_peer_connections_state(peer_states)

        state = resume_data.peer_connections_state
        assert state["peers"] == peer_states
        assert state["total_peers"] == 2
        assert "timestamp" in state
        assert resume_data.updated_at > initial_time

    def test_get_peer_connections_state(self):
        """Test getting peer connections state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        peer_states = [
            {"peer_key": "peer1", "pieces": {0, 1}},
        ]
        resume_data.set_peer_connections_state(peer_states)

        retrieved = resume_data.get_peer_connections_state()
        assert retrieved == peer_states

    def test_get_empty_peer_connections_state(self):
        """Test getting empty peer state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        retrieved = resume_data.get_peer_connections_state()
        assert retrieved == []


class TestUploadStatistics:
    """Test upload statistics management."""

    def test_set_upload_statistics(self):
        """Test setting upload statistics."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        bytes_uploaded = 10000
        peers_uploaded_to = {"peer1", "peer2"}
        upload_rate_history = [10.5, 20.3, 15.2]

        time.sleep(0.01)
        resume_data.set_upload_statistics(
            bytes_uploaded,
            peers_uploaded_to,
            upload_rate_history,
        )

        stats = resume_data.get_upload_statistics()
        assert stats["bytes_uploaded"] == bytes_uploaded
        assert stats["peers_uploaded_to"] == list(peers_uploaded_to)
        assert stats["upload_rate_history"] == upload_rate_history
        assert "average_upload_rate" in stats
        assert "last_updated" in stats
        assert resume_data.updated_at > initial_time

    def test_set_upload_statistics_large_history(self):
        """Test setting upload statistics with large history."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)

        # Create history with more than 100 entries
        upload_rate_history = [float(i) for i in range(150)]

        resume_data.set_upload_statistics(1000, set(), upload_rate_history)

        stats = resume_data.get_upload_statistics()
        # Should keep only last 100
        assert len(stats["upload_rate_history"]) == 100
        assert stats["upload_rate_history"] == upload_rate_history[-100:]

    def test_set_upload_statistics_empty_history(self):
        """Test setting upload statistics with empty history."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)

        resume_data.set_upload_statistics(1000, set(), [])

        stats = resume_data.get_upload_statistics()
        assert stats["average_upload_rate"] == 0.0


class TestFileSelectionState:
    """Test file selection state management."""

    def test_set_file_selection_state(self):
        """Test setting file selection state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        file_state = {
            0: {"selected": True, "priority": "high"},
            1: {"selected": False, "priority": "normal"},
        }

        time.sleep(0.01)
        resume_data.set_file_selection_state(file_state)

        assert resume_data.get_file_selection_state() == file_state
        assert resume_data.updated_at > initial_time

    def test_get_empty_file_selection_state(self):
        """Test getting empty file selection state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        state = resume_data.get_file_selection_state()
        assert state == {}


class TestQueueState:
    """Test queue state management."""

    def test_set_queue_state(self):
        """Test setting queue state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        time.sleep(0.01)
        resume_data.set_queue_state(5, "high")

        position, priority = resume_data.get_queue_state()
        assert position == 5
        assert priority == "high"
        assert resume_data.updated_at > initial_time

    def test_get_empty_queue_state(self):
        """Test getting empty queue state."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        position, priority = resume_data.get_queue_state()
        assert position is None
        assert priority is None


class TestVersionCompatibility:
    """Test version compatibility checks."""

    def test_is_compatible(self):
        """Test compatibility check."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=1)

        assert resume_data.is_compatible(1) is True
        assert resume_data.is_compatible(2) is True
        assert resume_data.is_compatible(100) is True

    def test_needs_migration(self):
        """Test migration check."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=1)

        assert resume_data.needs_migration(2) is True
        assert resume_data.needs_migration(1) is False
        assert resume_data.needs_migration(0) is False

    def test_update_timestamp(self):
        """Test timestamp update."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        time.sleep(0.01)
        resume_data.update_timestamp()

        assert resume_data.updated_at > initial_time


class TestSerialization:
    """Test serialization and deserialization."""

    def test_model_dump(self):
        """Test Pydantic model_dump."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.set_upload_statistics(1000, {"peer1"}, [10.0])
        resume_data.set_queue_state(0, "high")

        dumped = resume_data.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["info_hash"] == b"\x00" * 20
        assert dumped["version"] == 1
        assert dumped["queue_position"] == 0
        assert dumped["queue_priority"] == "high"

    def test_model_dump_json(self):
        """Test model_dump with JSON-compatible mode."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)

        dumped = resume_data.model_dump(mode="json")

        assert isinstance(dumped, dict)
        # JSON mode converts bytes to base64 or similar
        assert "info_hash" in dumped

    def test_from_dict(self):
        """Test creating from dictionary."""
        data: dict[str, Any] = {
            "info_hash": b"\x01" * 20,
            "version": 1,
            "queue_position": 5,
            "queue_priority": "normal",
        }

        resume_data = FastResumeData(**data)

        assert resume_data.info_hash == b"\x01" * 20
        assert resume_data.queue_position == 5

    def test_roundtrip_serialization(self):
        """Test roundtrip serialization."""
        original = FastResumeData(info_hash=b"\x00" * 20)
        original.set_upload_statistics(5000, {"peer1", "peer2"}, [10.0, 20.0])
        original.set_queue_state(3, "low")

        # Serialize
        dumped = original.model_dump()

        # Deserialize
        dumped_dict: dict[str, Any] = dumped  # Type hint for linter
        restored = FastResumeData(**dumped_dict)

        assert restored.info_hash == original.info_hash
        assert restored.version == original.version
        assert restored.get_upload_statistics()["bytes_uploaded"] == 5000
        position, priority = restored.get_queue_state()
        assert position == 3
        assert priority == "low"


class TestEdgeCases:
    """Test edge cases and error paths."""

    def test_encode_piece_bitmap_byte_bounds(self):
        """Test encoding with pieces at byte boundaries."""
        # Test pieces at byte boundaries (7, 8, 15, 16, etc.)
        verified = {0, 7, 8, 15, 16, 23, 24}
        total = 32
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_piece_bitmap_all_bits_in_byte(self):
        """Test encoding with all bits set in a byte."""
        # All 8 pieces in first byte
        verified = {0, 1, 2, 3, 4, 5, 6, 7}
        total = 8
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_encode_piece_bitmap_out_of_bounds_filtering(self):
        """Test that out-of-bounds pieces are filtered during encoding."""
        total = 10
        verified = {-1, 0, 5, 10, 100}  # -1, 10, 100 are out of bounds
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == {0, 5}  # Only valid pieces

    def test_decode_piece_bitmap_invalid_gzip(self):
        """Test decoding with invalid gzip data."""
        invalid_data = b"not_valid_gzip_data_12345"
        decoded = FastResumeData.decode_piece_bitmap(invalid_data, 100)
        assert decoded == set()

    def test_decode_piece_bitmap_empty_gzip(self):
        """Test decoding empty compressed data."""
        empty_compressed = gzip.compress(b"")
        decoded = FastResumeData.decode_piece_bitmap(empty_compressed, 100)
        assert decoded == set()

    def test_decode_piece_bitmap_short_bitfield(self):
        """Test decoding with bitfield shorter than expected."""
        # Create valid bitmap but with shorter bitfield
        verified = {0, 1}
        total = 100  # Large total but only 2 pieces set
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_decode_piece_bitmap_exact_byte_boundary(self):
        """Test decoding at exact byte boundaries."""
        # Test with total_pieces exactly divisible by 8
        verified = {0, 8, 16, 24, 32, 40, 48, 56, 64, 72}
        total = 80  # Exactly 10 bytes
        bitmap = FastResumeData.encode_piece_bitmap(verified, total)

        decoded = FastResumeData.decode_piece_bitmap(bitmap, total)
        assert decoded == verified

    def test_set_peer_connections_state_empty_list(self):
        """Test setting peer state with empty list."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.set_peer_connections_state([])

        state = resume_data.peer_connections_state
        assert state["peers"] == []
        assert state["total_peers"] == 0

    def test_get_peer_connections_state_malformed_dict(self):
        """Test getting peer state with malformed dictionary."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.peer_connections_state = {"invalid": "structure"}

        # Should handle gracefully
        retrieved = resume_data.get_peer_connections_state()
        assert retrieved == []

    def test_set_upload_statistics_single_entry(self):
        """Test setting upload stats with single history entry."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.set_upload_statistics(1000, {"peer1"}, [15.5])

        stats = resume_data.get_upload_statistics()
        assert stats["average_upload_rate"] == 15.5

    def test_compatibility_version_edge_cases(self):
        """Test version compatibility edge cases."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=1)

        # Test various version combinations
        assert resume_data.is_compatible(1) is True
        assert resume_data.is_compatible(2) is True
        assert resume_data.is_compatible(100) is True
        # Version 0 is invalid, but if somehow checked
        assert resume_data.is_compatible(0) is False  # version (1) > current_version (0)

        # Test needs_migration
        assert resume_data.needs_migration(2) is True
        assert resume_data.needs_migration(1) is False
        assert resume_data.needs_migration(0) is False

    def test_compatibility_newer_version(self):
        """Test compatibility with newer resume data version."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20, version=5)

        # Should be compatible if current supports up to 5
        assert resume_data.is_compatible(5) is True
        assert resume_data.is_compatible(10) is True
        # Not compatible if current version is lower
        assert resume_data.is_compatible(3) is False  # version (5) > current_version (3)

    def test_update_timestamp_multiple_times(self):
        """Test timestamp updates multiple times."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        initial_time = resume_data.updated_at

        time.sleep(0.01)
        resume_data.update_timestamp()
        first_update = resume_data.updated_at

        time.sleep(0.01)
        resume_data.update_timestamp()
        second_update = resume_data.updated_at

        assert first_update > initial_time
        assert second_update > first_update

    def test_model_dump_with_all_fields_set(self):
        """Test model_dump with all optional fields set."""
        resume_data = FastResumeData(info_hash=b"\x00" * 20)
        resume_data.set_upload_statistics(5000, {"peer1"}, [10.0])
        resume_data.set_file_selection_state({0: {"selected": True}})
        resume_data.set_queue_state(1, "high")
        resume_data.set_peer_connections_state([{"peer_key": "peer1"}])

        dumped = resume_data.model_dump()

        assert "upload_statistics" in dumped
        assert "file_selection_state" in dumped
        assert "queue_position" in dumped
        assert "queue_priority" in dumped
        assert "peer_connections_state" in dumped

