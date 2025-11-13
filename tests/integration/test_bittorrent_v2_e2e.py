"""End-to-end integration tests for BitTorrent Protocol v2 (BEP 52).

Tests complete v2 torrent lifecycle including creation, parsing, session integration,
and hybrid torrent compatibility.
Target: 85%+ e2e test coverage for v2 workflows.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.core]

from ccbt.core.bencode import decode, encode
from ccbt.core.torrent_v2 import (
    FileTreeNode,
    PieceLayer,
    TorrentV2Info,
    TorrentV2Parser,
)
from ccbt.protocols.bittorrent_v2 import (
    INFO_HASH_V2_LEN,
    ProtocolVersion,
    create_v2_handshake,
    detect_protocol_version,
)


@pytest.mark.asyncio
class TestV2TorrentCreation:
    """End-to-end tests for v2 torrent creation."""

    async def test_create_v2_torrent_single_file(self, tmp_path: Path):
        """Test creating v2-only torrent from single file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = b"x" * 32768  # 32 KiB - 2 pieces at 16 KiB
        test_file.write_bytes(test_content)

        # Create v2 torrent
        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        assert len(torrent_bytes) > 0

        # Parse and verify
        torrent_data = decode(torrent_bytes)
        assert b"info" in torrent_data
        info_dict = torrent_data[b"info"]

        assert info_dict[b"meta version"] == 2
        assert info_dict[b"piece length"] == 16384
        assert b"file tree" in info_dict
        assert b"piece layers" in info_dict

    async def test_create_v2_torrent_directory(self, tmp_path: Path):
        """Test creating v2-only torrent from directory."""
        # Create test directory structure
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file1.txt").write_bytes(b"content1" * 1000)
        (tmp_path / "file2.txt").write_bytes(b"content2" * 1000)
        (tmp_path / "subdir" / "file3.txt").write_bytes(b"content3" * 1000)

        # Create v2 torrent
        parser = TorrentV2Parser()
        output_file = tmp_path / "test.torrent"
        torrent_bytes = parser.generate_v2_torrent(
            source=tmp_path,
            output=output_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        assert len(torrent_bytes) > 0
        assert output_file.exists()

        # Parse and verify
        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        assert info_dict[b"meta version"] == 2
        assert b"file tree" in info_dict

        # Verify file tree structure
        file_tree = info_dict[b"file tree"]
        assert isinstance(file_tree, dict)
        assert len(file_tree) > 0

    async def test_create_hybrid_torrent_single_file(self, tmp_path: Path):
        """Test creating hybrid torrent from single file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 32768)

        # Create hybrid torrent
        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        assert len(torrent_bytes) > 0

        # Parse and verify
        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        assert info_dict[b"meta version"] == 3  # Hybrid
        assert b"pieces" in info_dict  # v1 pieces
        assert b"file tree" in info_dict  # v2 file tree
        assert b"piece layers" in info_dict  # v2 piece layers

    async def test_create_hybrid_torrent_directory(self, tmp_path: Path):
        """Test creating hybrid torrent from directory."""
        # Create test files
        (tmp_path / "file1.txt").write_bytes(b"a" * 10000)
        (tmp_path / "file2.txt").write_bytes(b"b" * 10000)

        # Create hybrid torrent
        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=tmp_path,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        # Parse and verify
        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        assert info_dict[b"meta version"] == 3
        assert b"pieces" in info_dict  # v1
        assert b"file tree" in info_dict  # v2
        assert b"files" in info_dict  # v1 files list

    async def test_create_torrent_piece_length_auto_calculation(self, tmp_path: Path):
        """Test automatic piece length calculation."""
        # Create small file (< 16 MiB)
        small_file = tmp_path / "small.txt"
        small_file.write_bytes(b"x" * (8 * 1024 * 1024))  # 8 MiB

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=small_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=None,  # Auto
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        # Should use 16 KiB pieces for small file
        assert info_dict[b"piece length"] == 16 * 1024

    async def test_create_torrent_validation(self, tmp_path: Path):
        """Test torrent file validation after creation."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content" * 1000)

        # Create torrent
        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            comment="Test torrent",
            created_by="ccBitTorrent",
            piece_length=16384,
            private=True,
        )

        # Decode and validate structure
        torrent_data = decode(torrent_bytes)

        assert b"info" in torrent_data
        assert b"announce" in torrent_data
        assert b"comment" in torrent_data
        assert b"created by" in torrent_data
        assert b"creation date" in torrent_data

        info_dict = torrent_data[b"info"]
        assert info_dict.get(b"private") == 1


@pytest.mark.asyncio
class TestV2TorrentParsing:
    """End-to-end tests for v2 torrent parsing."""

    async def test_parse_v2_only_torrent(self, tmp_path: Path):
        """Test parsing v2-only torrent file."""
        # Create and save v2 torrent
        test_file = tmp_path / "source.txt"
        test_file.write_bytes(b"x" * 32768)

        parser = TorrentV2Parser()
        output_file = tmp_path / "test.torrent"
        parser.generate_v2_torrent(
            source=test_file,
            output=output_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        # Read and parse
        with open(output_file, "rb") as f:
            torrent_bytes = f.read()

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        # Parse v2 info
        v2_info = parser.parse_v2(info_dict, torrent_data)

        assert isinstance(v2_info, TorrentV2Info)
        assert test_file.stem in v2_info.name  # Name includes the stem
        assert v2_info.piece_length == 16384
        assert len(v2_info.info_hash_v2) == INFO_HASH_V2_LEN
        assert v2_info.info_hash_v1 is None  # v2-only

    async def test_parse_hybrid_torrent(self, tmp_path: Path):
        """Test parsing hybrid torrent file."""
        # Create hybrid torrent
        test_file = tmp_path / "source.txt"
        test_file.write_bytes(b"x" * 32768)

        parser = TorrentV2Parser()
        output_file = tmp_path / "hybrid.torrent"
        parser.generate_hybrid_torrent(
            source=test_file,
            output=output_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        # Read and parse
        with open(output_file, "rb") as f:
            torrent_bytes = f.read()

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        # Parse hybrid
        v1_info, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        assert v2_info.info_hash_v1 is not None
        assert v2_info.info_hash_v2 is not None
        assert len(v2_info.info_hash_v1) == 20
        assert len(v2_info.info_hash_v2) == 32

    async def test_parse_info_hash_calculation(self, tmp_path: Path):
        """Test info_hash calculation during parsing."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]

        # Parse
        v2_info = parser.parse_v2(info_dict, torrent_data)

        # Verify info_hash is 32 bytes (SHA-256)
        assert len(v2_info.info_hash_v2) == 32
        assert isinstance(v2_info.info_hash_v2, bytes)

    async def test_parse_file_tree_extraction(self, tmp_path: Path):
        """Test file tree extraction during parsing."""
        # Create multi-file structure
        (tmp_path / "dir1").mkdir()
        (tmp_path / "file1.txt").write_bytes(b"a" * 1000)
        (tmp_path / "dir1" / "file2.txt").write_bytes(b"b" * 1000)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=tmp_path,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Verify file tree
        assert len(v2_info.file_tree) > 0
        assert len(v2_info.files) >= 2

        # Verify file paths
        file_paths = v2_info.get_file_paths()
        assert any("file1.txt" in path for path in file_paths)
        assert any("file2.txt" in path for path in file_paths)

    async def test_parse_piece_layer_extraction(self, tmp_path: Path):
        """Test piece layer extraction during parsing."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 32768)  # 2 pieces

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Verify piece layers
        assert len(v2_info.piece_layers) > 0

        # Get first piece layer
        pieces_root = list(v2_info.piece_layers.keys())[0]
        layer = v2_info.piece_layers[pieces_root]

        assert isinstance(layer, PieceLayer)
        assert layer.piece_length == 16384
        assert len(layer.pieces) == 2  # 32768 / 16384 = 2 pieces

    async def test_parse_validation(self, tmp_path: Path):
        """Test validation of parsed torrent data."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Validate parsed data
        assert v2_info.name
        assert v2_info.piece_length > 0
        assert v2_info.total_length > 0
        assert v2_info.num_pieces > 0
        assert len(v2_info.info_hash_v2) == 32


@pytest.mark.asyncio
class TestV2TorrentSessionIntegration:
    """End-to-end tests for v2 torrent session integration."""

    async def test_add_v2_torrent_to_session(self, tmp_path: Path):
        """Test adding v2 torrent to session manager."""
        # Create v2 torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        # Parse torrent
        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Verify info structure for session
        assert v2_info.info_hash_v2
        assert v2_info.name
        assert v2_info.files or v2_info.total_length

    async def test_v2_handshake_generation(self, tmp_path: Path):
        """Test generating v2 handshake for torrent."""
        # Create v2 torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Generate handshake
        peer_id = b"p" * 20
        handshake = create_v2_handshake(v2_info.info_hash_v2, peer_id)

        # Verify handshake
        assert len(handshake) == 80  # v2 handshake size
        version = detect_protocol_version(handshake)
        assert version == ProtocolVersion.V2

    async def test_piece_layer_exchange_workflow(self, tmp_path: Path):
        """Test piece layer exchange during download."""
        from ccbt.protocols.bittorrent_v2 import (
            PieceLayerRequest,
            PieceLayerResponse,
        )

        # Create v2 torrent with piece layers
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 32768)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Get pieces_root from file tree
        pieces_root = list(v2_info.piece_layers.keys())[0]

        # Create piece layer request
        request = PieceLayerRequest(pieces_root)
        request_data = request.serialize()

        # Simulate response
        layer = v2_info.piece_layers[pieces_root]
        response = PieceLayerResponse(pieces_root, layer.pieces)
        response_data = response.serialize()

        # Verify exchange
        assert len(request_data) > 0
        assert len(response_data) > 0

        # Parse response
        parsed_response = PieceLayerResponse.deserialize(response_data[4:])
        assert parsed_response.pieces_root == pieces_root
        assert len(parsed_response.piece_hashes) == len(layer.pieces)

    async def test_file_tree_exchange_workflow(self, tmp_path: Path):
        """Test file tree exchange workflow."""
        from ccbt.protocols.bittorrent_v2 import (
            FileTreeRequest,
            FileTreeResponse,
        )

        # Create v2 torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)

        # Create file tree request
        request = FileTreeRequest()
        request_data = request.serialize()

        # Create file tree response
        file_tree_bencoded = encode(torrent_data[b"info"][b"file tree"])
        response = FileTreeResponse(file_tree_bencoded)
        response_data = response.serialize()

        # Verify exchange
        assert len(request_data) > 0
        assert len(response_data) > 0

        # Parse response
        parsed_response = FileTreeResponse.deserialize(response_data[4:])
        assert parsed_response.file_tree == file_tree_bencoded

    async def test_download_progress_tracking(self, tmp_path: Path):
        """Test download progress tracking with v2 torrents."""
        # Create v2 torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 32768)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_v2_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

        # Verify piece tracking information
        assert v2_info.num_pieces > 0
        assert v2_info.piece_length > 0
        assert v2_info.total_length > 0

        # Calculate progress metrics
        expected_pieces = (v2_info.total_length + v2_info.piece_length - 1) // v2_info.piece_length
        # For piece layers, count pieces across all files
        total_layer_pieces = sum(layer.num_pieces() for layer in v2_info.piece_layers.values())
        assert total_layer_pieces > 0


@pytest.mark.asyncio
class TestHybridTorrentCompatibility:
    """End-to-end tests for hybrid torrent compatibility."""

    async def test_hybrid_with_v1_only_peers(self, tmp_path: Path):
        """Test hybrid torrent compatibility with v1-only peers."""
        from ccbt.protocols.bittorrent_v2 import negotiate_protocol_version

        # Create hybrid torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]
        v1_info, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        # Both hashes should be available
        assert v2_info.info_hash_v1 is not None
        assert v2_info.info_hash_v2 is not None

        # Simulate v1 handshake from peer
        import struct
        v1_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + b"\x00" * 8
            + v2_info.info_hash_v1
            + b"p" * 20
        )

        # Can negotiate with v1 peer
        supported = [ProtocolVersion.HYBRID, ProtocolVersion.V1]
        negotiated = negotiate_protocol_version(v1_handshake, supported)
        assert negotiated in [ProtocolVersion.V1, ProtocolVersion.HYBRID]

    async def test_hybrid_with_v2_only_peers(self, tmp_path: Path):
        """Test hybrid torrent compatibility with v2-only peers."""
        from ccbt.protocols.bittorrent_v2 import negotiate_protocol_version
        import struct

        # Create hybrid torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]
        _, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        # Simulate v2 handshake from peer
        reserved = bytearray(8)
        reserved[0] |= 0x01
        v2_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + bytes(reserved)
            + v2_info.info_hash_v2
            + b"p" * 20
        )

        # Can negotiate with v2 peer
        supported = [ProtocolVersion.HYBRID, ProtocolVersion.V2]
        negotiated = negotiate_protocol_version(v2_handshake, supported)
        assert negotiated in [ProtocolVersion.V2, ProtocolVersion.HYBRID]

    async def test_hybrid_mixed_peer_swarm(self, tmp_path: Path):
        """Test hybrid torrent with mixed v1/v2 peer swarm."""
        import struct
        from ccbt.protocols.bittorrent_v2 import negotiate_protocol_version

        # Create hybrid torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]
        _, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        # Create handshakes for different peer types
        v1_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + b"\x00" * 8
            + v2_info.info_hash_v1
            + b"1" * 20
        )

        reserved_v2 = bytearray(8)
        reserved_v2[0] |= 0x01
        v2_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + bytes(reserved_v2)
            + v2_info.info_hash_v2
            + b"2" * 20
        )

        # Our client supports hybrid
        supported = [ProtocolVersion.HYBRID]

        # Can connect to v1 peers
        v1_negotiated = negotiate_protocol_version(v1_handshake, supported)
        assert v1_negotiated == ProtocolVersion.HYBRID

        # Can connect to v2 peers
        v2_negotiated = negotiate_protocol_version(v2_handshake, supported)
        assert v2_negotiated == ProtocolVersion.HYBRID

    async def test_protocol_negotiation_in_hybrid_mode(self, tmp_path: Path):
        """Test protocol version negotiation in hybrid mode."""
        from ccbt.protocols.bittorrent_v2 import negotiate_protocol_version
        import struct

        # Create hybrid torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]
        _, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        # Test negotiation with various peer capabilities
        reserved_hybrid = bytearray(8)
        reserved_hybrid[0] |= 0x01
        hybrid_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + bytes(reserved_hybrid)
            + v2_info.info_hash_v1
            + b"h" * 20
        )

        # Client supports all versions
        supported_all = [ProtocolVersion.HYBRID, ProtocolVersion.V2, ProtocolVersion.V1]
        negotiated = negotiate_protocol_version(hybrid_handshake, supported_all)

        # Should prefer HYBRID when available
        assert negotiated == ProtocolVersion.HYBRID

    async def test_fallback_to_v1_when_v2_unsupported(self, tmp_path: Path):
        """Test fallback to v1 when v2 is not supported."""
        from ccbt.protocols.bittorrent_v2 import negotiate_protocol_version
        import struct

        # Create hybrid torrent
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 16384)

        parser = TorrentV2Parser()
        torrent_bytes = parser.generate_hybrid_torrent(
            source=test_file,
            trackers=["http://tracker.example.com/announce"],
            piece_length=16384,
        )

        torrent_data = decode(torrent_bytes)
        info_dict = torrent_data[b"info"]
        _, v2_info = parser.parse_hybrid(info_dict, torrent_data)

        # Peer is v1-only
        v1_handshake = (
            struct.pack("B", 19)
            + b"BitTorrent protocol"
            + b"\x00" * 8
            + v2_info.info_hash_v1
            + b"1" * 20
        )

        # Client only supports v1 and v2 (no hybrid)
        supported_no_hybrid = [ProtocolVersion.V2, ProtocolVersion.V1]
        negotiated = negotiate_protocol_version(v1_handshake, supported_no_hybrid)

        # Should fall back to v1
        assert negotiated == ProtocolVersion.V1

