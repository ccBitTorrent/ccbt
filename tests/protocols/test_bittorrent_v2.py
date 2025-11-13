"""Unit tests for BitTorrent Protocol v2 (BEP 52) communication.

Tests for protocol handshake, version negotiation, and v2-specific messages.
Target: 95%+ code coverage for ccbt/protocols/bittorrent_v2.py
"""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.protocols]

from ccbt.protocols.bittorrent_v2 import (
    HANDSHAKE_V1_SIZE,
    HANDSHAKE_V2_SIZE,
    INFO_HASH_V1_LEN,
    INFO_HASH_V2_LEN,
    MESSAGE_ID_FILE_TREE_REQUEST,
    MESSAGE_ID_FILE_TREE_RESPONSE,
    MESSAGE_ID_PIECE_LAYER_REQUEST,
    MESSAGE_ID_PIECE_LAYER_RESPONSE,
    PEER_ID_LEN,
    PROTOCOL_STRING,
    PROTOCOL_STRING_LEN,
    RESERVED_BYTES_LEN,
    FileTreeRequest,
    FileTreeResponse,
    PieceLayerRequest,
    PieceLayerResponse,
    ProtocolVersion,
    ProtocolVersionError,
    create_hybrid_handshake,
    create_v2_handshake,
    detect_protocol_version,
    handle_v2_handshake,
    negotiate_protocol_version,
    parse_v2_handshake,
    send_hybrid_handshake,
    send_v2_handshake,
    upgrade_to_v2,
)


class TestProtocolVersion:
    """Test ProtocolVersion enum."""

    def test_protocol_version_v1(self):
        """Test V1 protocol version."""
        assert ProtocolVersion.V1.value == 1

    def test_protocol_version_v2(self):
        """Test V2 protocol version."""
        assert ProtocolVersion.V2.value == 2

    def test_protocol_version_hybrid(self):
        """Test HYBRID protocol version."""
        assert ProtocolVersion.HYBRID.value == 3

    def test_protocol_version_enum_members(self):
        """Test all enum members are present."""
        versions = [v for v in ProtocolVersion]
        assert len(versions) == 3
        assert ProtocolVersion.V1 in versions
        assert ProtocolVersion.V2 in versions
        assert ProtocolVersion.HYBRID in versions


class TestProtocolVersionError:
    """Test ProtocolVersionError exception."""

    def test_protocol_version_error_creation(self):
        """Test creating ProtocolVersionError."""
        error = ProtocolVersionError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_protocol_version_error_raise(self):
        """Test raising ProtocolVersionError."""
        with pytest.raises(ProtocolVersionError, match="test error"):
            raise ProtocolVersionError("test error")


class TestDetectProtocolVersion:
    """Test detect_protocol_version function."""

    def test_detect_v1_handshake(self):
        """Test detecting v1 handshake (68 bytes, no v2 bit)."""
        # v1 handshake: 1 + 19 + 8 + 20 + 20 = 68 bytes
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN  # No v2 bit set
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        assert len(handshake) == HANDSHAKE_V1_SIZE
        version = detect_protocol_version(handshake)
        assert version == ProtocolVersion.V1

    def test_detect_v2_handshake(self):
        """Test detecting v2 handshake (80 bytes, v2 bit set)."""
        # v2 handshake: 1 + 19 + 8 + 32 + 20 = 80 bytes
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01  # Set bit 0 for v2 support

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        assert len(handshake) == HANDSHAKE_V2_SIZE
        version = detect_protocol_version(handshake)
        assert version == ProtocolVersion.V2

    def test_detect_hybrid_handshake_v1_size(self):
        """Test detecting hybrid handshake (68 bytes with v2 bit)."""
        # Hybrid handshake with v1 hash but v2 support bit set
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01  # Set bit 0 for v2 support

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        assert len(handshake) == HANDSHAKE_V1_SIZE
        version = detect_protocol_version(handshake)
        assert version == ProtocolVersion.HYBRID

    def test_detect_hybrid_handshake_extended(self):
        """Test detecting extended hybrid handshake (both hashes)."""
        # Extended hybrid: 1 + 19 + 8 + 20 + 32 + 20 = 100 bytes
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * INFO_HASH_V1_LEN
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        assert len(handshake) == 100
        version = detect_protocol_version(handshake)
        assert version == ProtocolVersion.HYBRID

    def test_detect_handshake_too_short(self):
        """Test detecting handshake that is too short."""
        handshake = b"short"
        with pytest.raises(ProtocolVersionError, match="Handshake too short"):
            detect_protocol_version(handshake)

    def test_detect_invalid_protocol_string_length(self):
        """Test detecting handshake with invalid protocol string length."""
        handshake = struct.pack("B", 15) + b"x" * 50
        with pytest.raises(ProtocolVersionError, match="Invalid protocol string length"):
            detect_protocol_version(handshake)

    def test_detect_invalid_protocol_string(self):
        """Test detecting handshake with invalid protocol string."""
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + b"Invalid Protocol!!"
            + b"x" * 50
        )
        with pytest.raises(ProtocolVersionError, match="Invalid protocol string"):
            detect_protocol_version(handshake)

    def test_detect_handshake_missing_reserved_bytes(self):
        """Test detecting handshake missing reserved bytes."""
        handshake = struct.pack("B", PROTOCOL_STRING_LEN) + PROTOCOL_STRING + b"xx"
        with pytest.raises(ProtocolVersionError, match="too short for reserved bytes"):
            detect_protocol_version(handshake)

    def test_detect_handshake_invalid_size(self):
        """Test detecting handshake with invalid size."""
        # Size between v1 and v2 (not 68, not 80, not 100)
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + b"x" * 25  # Invalid size
        )
        with pytest.raises(ProtocolVersionError, match="Invalid handshake size"):
            detect_protocol_version(handshake)

    def test_detect_handshake_too_short_for_protocol_string(self):
        """Test detecting handshake too short for protocol string."""
        # Handshake that passes initial length check (>=20) but fails protocol string check
        # Need exactly 20 bytes: 1 (length) + 19 (protocol) = 20 minimum
        # But protocol string extraction happens after initial check
        handshake = struct.pack("B", PROTOCOL_STRING_LEN) + b"x" * 15  # 16 bytes total, but protocol string needs 19
        # This will fail with "Handshake too short" at initial check, not at protocol string check
        with pytest.raises(ProtocolVersionError):
            detect_protocol_version(handshake)


class TestParseV2Handshake:
    """Test parse_v2_handshake function."""

    def test_parse_v2_only_handshake(self):
        """Test parsing v2-only handshake."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        result = parse_v2_handshake(handshake)

        assert result["protocol"] == PROTOCOL_STRING
        assert result["reserved_bytes"] == bytes(reserved)
        assert result["info_hash_v2"] == info_hash_v2
        assert result["peer_id"] == peer_id
        assert result["version"] == ProtocolVersion.V2
        assert "info_hash_v1" not in result or result.get("info_hash_v1") is None

    def test_parse_hybrid_handshake_both_hashes(self):
        """Test parsing hybrid handshake with both v1 and v2 hashes."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v1
            + info_hash_v2
            + peer_id
        )

        result = parse_v2_handshake(handshake)

        assert result["version"] == ProtocolVersion.HYBRID
        assert result["info_hash_v1"] == info_hash_v1
        assert result["info_hash_v2"] == info_hash_v2
        assert result["peer_id"] == peer_id

    def test_parse_hybrid_handshake_v1_only(self):
        """Test parsing hybrid handshake with v1 hash only."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v1
            + peer_id
        )

        result = parse_v2_handshake(handshake)

        assert result["version"] == ProtocolVersion.HYBRID
        assert result["info_hash_v1"] == info_hash_v1
        assert result["peer_id"] == peer_id

    def test_parse_v1_handshake(self):
        """Test parsing v1 handshake."""
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + info_hash_v1
            + peer_id
        )

        result = parse_v2_handshake(handshake)

        assert result["version"] == ProtocolVersion.V1
        assert result["info_hash_v1"] == info_hash_v1
        assert result["peer_id"] == peer_id

    def test_parse_handshake_too_short(self):
        """Test parsing handshake that is too short."""
        with pytest.raises(ProtocolVersionError, match="Handshake too short"):
            parse_v2_handshake(b"short")

    def test_parse_handshake_invalid_protocol_length(self):
        """Test parsing handshake with invalid protocol length."""
        handshake = struct.pack("B", 15) + b"x" * 100
        with pytest.raises(ProtocolVersionError, match="Invalid protocol string length"):
            parse_v2_handshake(handshake)

    def test_parse_handshake_invalid_protocol_string(self):
        """Test parsing handshake with invalid protocol string."""
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + b"Wrong protocol str!"
            + b"x" * 100
        )
        with pytest.raises(ProtocolVersionError, match="Invalid protocol string"):
            parse_v2_handshake(handshake)

    def test_parse_v2_handshake_too_short_for_hash(self):
        """Test parsing v2 handshake too short for info hash."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        # Create handshake that passes initial size check but fails version detection
        # Must be at least 68 bytes to pass initial check, but not 80 bytes for v2
        # 1 + 19 + 8 + 31 + 20 = 79 bytes (needs 80 for v2)
        # Version detection will fail because remaining = 51 (not 52 for v2)
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * 31  # 31 bytes instead of 32 for info_hash_v2
            + b"p" * PEER_ID_LEN  # Full peer_id
        )
        # detect_protocol_version fails before parse_v2_handshake gets to version-specific checks
        with pytest.raises(ProtocolVersionError, match="Invalid handshake size"):
            parse_v2_handshake(handshake)

    def test_parse_hybrid_handshake_too_short_for_hash(self):
        """Test parsing hybrid handshake too short for info hash."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        # Create handshake that fails initial size check
        # 1 + 19 + 8 + 19 + 20 = 67 bytes (needs 68 minimum)
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * 19  # 19 bytes instead of 20 for info_hash_v1
            + b"p" * PEER_ID_LEN  # Full peer_id
        )
        # Fails initial size check before version detection
        with pytest.raises(ProtocolVersionError, match="Handshake too short.*minimum 68"):
            parse_v2_handshake(handshake)

    def test_parse_v1_handshake_too_short_for_hash(self):
        """Test parsing v1 handshake too short for info hash."""
        # Create handshake that fails initial size check
        # 1 + 19 + 8 + 19 + 20 = 67 bytes (needs 68 minimum)
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + b"x" * 19  # 19 bytes instead of 20 for info_hash_v1
            + b"p" * PEER_ID_LEN  # Full peer_id
        )
        # Fails initial size check before version detection
        with pytest.raises(ProtocolVersionError, match="Handshake too short.*minimum 68"):
            parse_v2_handshake(handshake)


class TestCreateV2Handshake:
    """Test create_v2_handshake function."""

    def test_create_v2_handshake(self):
        """Test creating v2 handshake."""
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = create_v2_handshake(info_hash_v2, peer_id)

        assert len(handshake) == HANDSHAKE_V2_SIZE
        assert handshake[0] == PROTOCOL_STRING_LEN
        assert handshake[1:20] == PROTOCOL_STRING

        # Check reserved bytes (bit 0 should be set)
        reserved_bytes = handshake[20:28]
        assert reserved_bytes[0] & 0x01 == 1  # v2 bit set

        # Check info_hash_v2
        assert handshake[28:60] == info_hash_v2

        # Check peer_id
        assert handshake[60:80] == peer_id

    def test_create_v2_handshake_reserved_bytes(self):
        """Test v2 handshake has correct reserved bytes."""
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = create_v2_handshake(info_hash_v2, peer_id)

        # Extract reserved bytes
        reserved_bytes = handshake[20:28]

        # Bit 0 should be set for v2 support
        assert reserved_bytes[0] & 0x01 == 1

    def test_create_v2_handshake_invalid_info_hash_length(self):
        """Test creating v2 handshake with invalid info_hash length."""
        info_hash_v2 = b"i" * 31  # Wrong length
        peer_id = b"p" * PEER_ID_LEN

        with pytest.raises(ProtocolVersionError, match="info_hash_v2 must be 32 bytes"):
            create_v2_handshake(info_hash_v2, peer_id)

    def test_create_v2_handshake_invalid_peer_id_length(self):
        """Test creating v2 handshake with invalid peer_id length."""
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * 19  # Wrong length

        with pytest.raises(ProtocolVersionError, match="peer_id must be 20 bytes"):
            create_v2_handshake(info_hash_v2, peer_id)


class TestCreateHybridHandshake:
    """Test create_hybrid_handshake function."""

    def test_create_hybrid_handshake(self):
        """Test creating hybrid handshake with both hashes."""
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = create_hybrid_handshake(info_hash_v1, info_hash_v2, peer_id)

        # Extended hybrid handshake: 1 + 19 + 8 + 20 + 32 + 20 = 100 bytes
        assert len(handshake) == 100

        # Check structure
        assert handshake[0] == PROTOCOL_STRING_LEN
        assert handshake[1:20] == PROTOCOL_STRING

        # Check reserved bytes (bit 0 set)
        reserved_bytes = handshake[20:28]
        assert reserved_bytes[0] & 0x01 == 1

        # Check info_hash_v1
        assert handshake[28:48] == info_hash_v1

        # Check info_hash_v2
        assert handshake[48:80] == info_hash_v2

        # Check peer_id
        assert handshake[80:100] == peer_id

    def test_create_hybrid_handshake_reserved_bytes(self):
        """Test hybrid handshake has correct reserved bytes."""
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake = create_hybrid_handshake(info_hash_v1, info_hash_v2, peer_id)

        reserved_bytes = handshake[20:28]
        assert reserved_bytes[0] & 0x01 == 1  # v2 bit set

    def test_create_hybrid_handshake_invalid_v1_hash(self):
        """Test creating hybrid handshake with invalid v1 hash."""
        info_hash_v1 = b"x" * 19  # Wrong length
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        with pytest.raises(ProtocolVersionError, match="info_hash_v1 must be 20 bytes"):
            create_hybrid_handshake(info_hash_v1, info_hash_v2, peer_id)

    def test_create_hybrid_handshake_invalid_v2_hash(self):
        """Test creating hybrid handshake with invalid v2 hash."""
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * 31  # Wrong length
        peer_id = b"p" * PEER_ID_LEN

        with pytest.raises(ProtocolVersionError, match="info_hash_v2 must be 32 bytes"):
            create_hybrid_handshake(info_hash_v1, info_hash_v2, peer_id)

    def test_create_hybrid_handshake_invalid_peer_id(self):
        """Test creating hybrid handshake with invalid peer_id."""
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * 19  # Wrong length

        with pytest.raises(ProtocolVersionError, match="peer_id must be 20 bytes"):
            create_hybrid_handshake(info_hash_v1, info_hash_v2, peer_id)


class TestNegotiateProtocolVersion:
    """Test negotiate_protocol_version function."""

    def test_negotiate_with_v1_peer(self):
        """Test negotiation with v1-only peer."""
        # Create v1 handshake
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We support hybrid
        supported = [ProtocolVersion.HYBRID, ProtocolVersion.V1]
        result = negotiate_protocol_version(handshake, supported)

        assert result == ProtocolVersion.HYBRID  # Can use hybrid with v1 peer

    def test_negotiate_with_v2_peer(self):
        """Test negotiation with v2-only peer."""
        # Create v2 handshake
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        # We support v2
        supported = [ProtocolVersion.V2]
        result = negotiate_protocol_version(handshake, supported)

        assert result == ProtocolVersion.V2

    def test_negotiate_with_hybrid_peer(self):
        """Test negotiation with hybrid peer."""
        # Create hybrid handshake
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We support hybrid
        supported = [ProtocolVersion.HYBRID]
        result = negotiate_protocol_version(handshake, supported)

        assert result == ProtocolVersion.HYBRID

    def test_negotiate_incompatible_versions(self):
        """Test negotiation with incompatible versions."""
        # Peer is v1-only
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We only support v2
        supported = [ProtocolVersion.V2]
        result = negotiate_protocol_version(handshake, supported)

        # Should return None for incompatible
        assert result is None

    def test_negotiate_version_priority_hybrid_over_v2(self):
        """Test that HYBRID is preferred over V2."""
        # Peer is hybrid
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We support both
        supported = [ProtocolVersion.V2, ProtocolVersion.HYBRID]
        result = negotiate_protocol_version(handshake, supported)

        # Should prefer HYBRID
        assert result == ProtocolVersion.HYBRID

    def test_negotiate_version_priority_v2_over_v1(self):
        """Test that V2 is preferred over V1."""
        # Peer is hybrid (supports both)
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We support v1 and v2 but not hybrid - should return None
        # because peer is HYBRID and requires exact match or HYBRID compatibility
        supported = [ProtocolVersion.V1, ProtocolVersion.V2]
        result = negotiate_protocol_version(handshake, supported)

        # No common version - peer is HYBRID, we don't support HYBRID
        assert result is None

        # But if we support HYBRID, it should work
        supported = [ProtocolVersion.HYBRID, ProtocolVersion.V2, ProtocolVersion.V1]
        result = negotiate_protocol_version(handshake, supported)
        assert result == ProtocolVersion.HYBRID

    def test_negotiate_invalid_handshake(self):
        """Test negotiation with invalid handshake."""
        handshake = b"invalid"
        supported = [ProtocolVersion.V1]
        result = negotiate_protocol_version(handshake, supported)

        assert result is None

    def test_negotiate_v2_peer_with_only_hybrid_supported(self):
        """Test negotiation with v2 peer when only HYBRID is supported."""
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        # We only support HYBRID
        supported = [ProtocolVersion.HYBRID]
        result = negotiate_protocol_version(handshake, supported)

        # Should return HYBRID (compatible with v2 peer)
        assert result == ProtocolVersion.HYBRID

    def test_negotiate_v2_peer_with_hybrid_only_returns_hybrid(self):
        """Test negotiation with v2 peer when only HYBRID is supported."""
        # This tests line 472: when v2 peer and we only support HYBRID
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        # We only support HYBRID (not V2 explicitly)
        supported = [ProtocolVersion.HYBRID]
        result = negotiate_protocol_version(handshake, supported)

        # Should return HYBRID (compatible with v2 peer)
        assert result == ProtocolVersion.HYBRID

    def test_negotiate_v2_peer_no_hybrid_support_returns_none(self):
        """Test negotiation with v2 peer when HYBRID not supported."""
        # This tests line 473: v2 peer but HYBRID not in supported list
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + b"y" * INFO_HASH_V2_LEN
            + b"p" * PEER_ID_LEN
        )

        # We only support V1 (not V2 or HYBRID)
        supported = [ProtocolVersion.V1]
        result = negotiate_protocol_version(handshake, supported)

        # Should return None (incompatible)
        assert result is None

    def test_negotiate_v1_peer_no_support_returns_none(self):
        """Test negotiation with v1 peer when neither V1 nor HYBRID supported."""
        # This tests line 481: v1 peer but neither HYBRID nor V1 in supported
        handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + b"x" * INFO_HASH_V1_LEN
            + b"p" * PEER_ID_LEN
        )

        # We only support V2 (not V1 or HYBRID)
        supported = [ProtocolVersion.V2]
        result = negotiate_protocol_version(handshake, supported)

        # Should return None (incompatible)
        assert result is None


class TestV2Messages:
    """Test v2-specific message types."""

    def test_piece_layer_request_creation(self):
        """Test creating PieceLayerRequest."""
        pieces_root = b"r" * 32
        request = PieceLayerRequest(pieces_root)

        assert request.message_id == MESSAGE_ID_PIECE_LAYER_REQUEST
        assert request.pieces_root == pieces_root

    def test_piece_layer_request_invalid_root_length(self):
        """Test PieceLayerRequest with invalid pieces_root length."""
        pieces_root = b"r" * 31  # Wrong length
        with pytest.raises(ProtocolVersionError, match="pieces_root must be 32 bytes"):
            PieceLayerRequest(pieces_root)

    def test_piece_layer_request_serialization(self):
        """Test PieceLayerRequest serialization."""
        pieces_root = b"r" * 32
        request = PieceLayerRequest(pieces_root)
        data = request.serialize()

        # Check length prefix (4 bytes)
        length = struct.unpack("!I", data[0:4])[0]
        assert length == 33  # 1 byte ID + 32 bytes pieces_root

        # Check message ID
        assert data[4] == MESSAGE_ID_PIECE_LAYER_REQUEST

        # Check pieces_root
        assert data[5:37] == pieces_root

    def test_piece_layer_request_deserialization(self):
        """Test PieceLayerRequest deserialization."""
        pieces_root = b"r" * 32
        data = struct.pack("B", MESSAGE_ID_PIECE_LAYER_REQUEST) + pieces_root

        request = PieceLayerRequest.deserialize(data)

        assert request.pieces_root == pieces_root
        assert request.message_id == MESSAGE_ID_PIECE_LAYER_REQUEST

    def test_piece_layer_request_deserialize_too_short(self):
        """Test PieceLayerRequest deserialization with too short data."""
        # Too short - need at least 33 bytes (1 ID + 32 pieces_root)
        data = struct.pack("B", MESSAGE_ID_PIECE_LAYER_REQUEST) + b"x" * 31
        with pytest.raises(ProtocolVersionError, match="Piece layer request too short"):
            PieceLayerRequest.deserialize(data)

    def test_piece_layer_request_deserialize_invalid_message_id(self):
        """Test PieceLayerRequest deserialization with invalid message ID."""
        pieces_root = b"r" * 32
        # Wrong message ID
        data = struct.pack("B", 99) + pieces_root
        with pytest.raises(ProtocolVersionError, match="Invalid message ID"):
            PieceLayerRequest.deserialize(data)

    def test_piece_layer_response_creation(self):
        """Test creating PieceLayerResponse."""
        pieces_root = b"r" * 32
        piece_hashes = [b"h1" + b"\x00" * 30, b"h2" + b"\x00" * 30]
        response = PieceLayerResponse(pieces_root, piece_hashes)

        assert response.message_id == MESSAGE_ID_PIECE_LAYER_RESPONSE
        assert response.pieces_root == pieces_root
        assert response.piece_hashes == piece_hashes

    def test_piece_layer_response_invalid_root(self):
        """Test PieceLayerResponse with invalid pieces_root."""
        pieces_root = b"r" * 31  # Wrong length
        piece_hashes = [b"h" * 32]
        with pytest.raises(ProtocolVersionError, match="pieces_root must be 32 bytes"):
            PieceLayerResponse(pieces_root, piece_hashes)

    def test_piece_layer_response_invalid_hash(self):
        """Test PieceLayerResponse with invalid piece hash."""
        pieces_root = b"r" * 32
        piece_hashes = [b"h" * 31]  # Wrong length
        with pytest.raises(ProtocolVersionError, match="Piece hash .* must be 32 bytes"):
            PieceLayerResponse(pieces_root, piece_hashes)

    def test_piece_layer_response_serialization(self):
        """Test PieceLayerResponse serialization."""
        pieces_root = b"r" * 32
        piece_hashes = [b"h1" + b"\x00" * 30, b"h2" + b"\x00" * 30]
        response = PieceLayerResponse(pieces_root, piece_hashes)
        data = response.serialize()

        # Check length prefix
        length = struct.unpack("!I", data[0:4])[0]
        assert length == 1 + 32 + 64  # 1 ID + 32 root + 2*32 hashes

        # Check message ID
        assert data[4] == MESSAGE_ID_PIECE_LAYER_RESPONSE

        # Check pieces_root
        assert data[5:37] == pieces_root

        # Check piece hashes
        assert data[37:69] == piece_hashes[0]
        assert data[69:101] == piece_hashes[1]

    def test_piece_layer_response_deserialization(self):
        """Test PieceLayerResponse deserialization."""
        pieces_root = b"r" * 32
        piece_hashes = [b"h1" + b"\x00" * 30, b"h2" + b"\x00" * 30]
        data = (
            struct.pack("B", MESSAGE_ID_PIECE_LAYER_RESPONSE)
            + pieces_root
            + b"".join(piece_hashes)
        )

        response = PieceLayerResponse.deserialize(data)

        assert response.pieces_root == pieces_root
        assert len(response.piece_hashes) == 2
        assert response.piece_hashes[0] == piece_hashes[0]
        assert response.piece_hashes[1] == piece_hashes[1]

    def test_piece_layer_response_deserialize_too_short(self):
        """Test PieceLayerResponse deserialization with too short data."""
        # Too short - need at least 33 bytes (1 ID + 32 pieces_root)
        data = struct.pack("B", MESSAGE_ID_PIECE_LAYER_RESPONSE) + b"x" * 31
        with pytest.raises(ProtocolVersionError, match="Piece layer response too short"):
            PieceLayerResponse.deserialize(data)

    def test_piece_layer_response_deserialize_invalid_message_id(self):
        """Test PieceLayerResponse deserialization with invalid message ID."""
        pieces_root = b"r" * 32
        piece_hashes = [b"h" * 32]
        # Wrong message ID
        data = struct.pack("B", 99) + pieces_root + b"".join(piece_hashes)
        with pytest.raises(ProtocolVersionError, match="Invalid message ID"):
            PieceLayerResponse.deserialize(data)

    def test_piece_layer_response_deserialize_invalid_length(self):
        """Test PieceLayerResponse deserialization with invalid piece layer length."""
        pieces_root = b"r" * 32
        # Piece layer data length must be multiple of 32, but we give 33 bytes
        invalid_pieces = b"x" * 33
        data = (
            struct.pack("B", MESSAGE_ID_PIECE_LAYER_RESPONSE)
            + pieces_root
            + invalid_pieces
        )
        with pytest.raises(ProtocolVersionError, match="Piece layer data length must be multiple of 32"):
            PieceLayerResponse.deserialize(data)

    def test_file_tree_request_creation(self):
        """Test creating FileTreeRequest."""
        request = FileTreeRequest()
        assert request.message_id == MESSAGE_ID_FILE_TREE_REQUEST

    def test_file_tree_request_serialization(self):
        """Test FileTreeRequest serialization."""
        request = FileTreeRequest()
        data = request.serialize()

        # Check length prefix
        length = struct.unpack("!I", data[0:4])[0]
        assert length == 1  # Only message ID

        # Check message ID
        assert data[4] == MESSAGE_ID_FILE_TREE_REQUEST

    def test_file_tree_request_deserialization(self):
        """Test FileTreeRequest deserialization."""
        data = struct.pack("B", MESSAGE_ID_FILE_TREE_REQUEST)
        request = FileTreeRequest.deserialize(data)
        assert request.message_id == MESSAGE_ID_FILE_TREE_REQUEST

    def test_file_tree_request_deserialize_too_short(self):
        """Test FileTreeRequest deserialization with empty data."""
        # Empty data
        data = b""
        with pytest.raises(ProtocolVersionError, match="File tree request too short"):
            FileTreeRequest.deserialize(data)

    def test_file_tree_request_deserialize_invalid_message_id(self):
        """Test FileTreeRequest deserialization with invalid message ID."""
        # Wrong message ID
        data = struct.pack("B", 99)
        with pytest.raises(ProtocolVersionError, match="Invalid message ID"):
            FileTreeRequest.deserialize(data)

    def test_file_tree_response_creation(self):
        """Test creating FileTreeResponse."""
        file_tree = b"d4:test6:value1e"  # Bencoded data
        response = FileTreeResponse(file_tree)

        assert response.message_id == MESSAGE_ID_FILE_TREE_RESPONSE
        assert response.file_tree == file_tree

    def test_file_tree_response_empty_tree(self):
        """Test FileTreeResponse with empty file tree."""
        with pytest.raises(ProtocolVersionError, match="File tree data cannot be empty"):
            FileTreeResponse(b"")

    def test_file_tree_response_serialization(self):
        """Test FileTreeResponse serialization."""
        file_tree = b"d4:test6:value1e"
        response = FileTreeResponse(file_tree)
        data = response.serialize()

        # Check length prefix
        length = struct.unpack("!I", data[0:4])[0]
        assert length == 1 + len(file_tree)

        # Check message ID
        assert data[4] == MESSAGE_ID_FILE_TREE_RESPONSE

        # Check file tree
        assert data[5:] == file_tree

    def test_file_tree_response_deserialization(self):
        """Test FileTreeResponse deserialization."""
        file_tree = b"d4:test6:value1e"
        data = struct.pack("B", MESSAGE_ID_FILE_TREE_RESPONSE) + file_tree
        response = FileTreeResponse.deserialize(data)

        assert response.file_tree == file_tree
        assert response.message_id == MESSAGE_ID_FILE_TREE_RESPONSE

    def test_file_tree_response_deserialize_too_short(self):
        """Test FileTreeResponse deserialization with empty data."""
        # Empty data
        data = b""
        with pytest.raises(ProtocolVersionError, match="File tree response too short"):
            FileTreeResponse.deserialize(data)

    def test_file_tree_response_deserialize_invalid_message_id(self):
        """Test FileTreeResponse deserialization with invalid message ID."""
        file_tree = b"d4:test6:value1e"
        # Wrong message ID
        data = struct.pack("B", 99) + file_tree
        with pytest.raises(ProtocolVersionError, match="Invalid message ID"):
            FileTreeResponse.deserialize(data)

    def test_file_tree_response_deserialize_empty_tree(self):
        """Test FileTreeResponse deserialization with empty file tree."""
        # Valid message ID but empty file tree data
        data = struct.pack("B", MESSAGE_ID_FILE_TREE_RESPONSE)  # No file tree data
        with pytest.raises(ProtocolVersionError, match="File tree data is empty"):
            FileTreeResponse.deserialize(data)


@pytest.mark.asyncio
class TestAsyncHandshakeFunctions:
    """Test async handshake functions."""

    async def test_send_v2_handshake(self):
        """Test sending v2 handshake."""
        writer = AsyncMock(spec=asyncio.StreamWriter)
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        await send_v2_handshake(writer, info_hash_v2, peer_id)

        # Verify write was called
        writer.write.assert_called_once()
        written_data = writer.write.call_args[0][0]

        # Verify handshake structure
        assert len(written_data) == HANDSHAKE_V2_SIZE
        assert written_data[28:60] == info_hash_v2
        assert written_data[60:80] == peer_id

        # Verify drain was called
        writer.drain.assert_awaited_once()

    async def test_send_hybrid_handshake(self):
        """Test sending hybrid handshake."""
        writer = AsyncMock(spec=asyncio.StreamWriter)
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        await send_hybrid_handshake(writer, info_hash_v1, info_hash_v2, peer_id)

        # Verify write was called
        writer.write.assert_called_once()
        written_data = writer.write.call_args[0][0]

        # Verify handshake structure
        assert len(written_data) == 100
        assert written_data[28:48] == info_hash_v1
        assert written_data[48:80] == info_hash_v2
        assert written_data[80:100] == peer_id

        # Verify drain was called
        writer.drain.assert_awaited_once()

    async def test_handle_v2_handshake_v2_only(self):
        """Test handling incoming v2 handshake."""
        # Create v2 handshake
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake_data = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        # Mock reader
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(return_value=handshake_data)

        writer = MagicMock(spec=asyncio.StreamWriter)

        version, returned_peer_id, parsed = await handle_v2_handshake(
            reader, writer, our_info_hash_v2=info_hash_v2
        )

        assert version == ProtocolVersion.V2
        assert returned_peer_id == peer_id
        assert parsed["info_hash_v2"] == info_hash_v2

    async def test_handle_v2_handshake_info_hash_mismatch(self):
        """Test handling handshake with info_hash mismatch."""
        # Create handshake with wrong info_hash
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        wrong_hash = b"w" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake_data = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + wrong_hash
            + peer_id
        )

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(return_value=handshake_data)

        writer = MagicMock(spec=asyncio.StreamWriter)

        # Expect ValueError for info_hash mismatch
        with pytest.raises(ValueError, match="Info hash v2 mismatch"):
            await handle_v2_handshake(
                reader, writer, our_info_hash_v2=b"i" * INFO_HASH_V2_LEN
            )

    async def test_handle_v2_handshake_v1_hash_mismatch(self):
        """Test handling handshake with v1 info_hash mismatch."""
        # Create v1 handshake with wrong info_hash
        wrong_hash_v1 = b"w" * INFO_HASH_V1_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake_data = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + b"\x00" * RESERVED_BYTES_LEN
            + wrong_hash_v1
            + peer_id
        )

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(return_value=handshake_data)

        writer = MagicMock(spec=asyncio.StreamWriter)

        # Expect ValueError for v1 info_hash mismatch
        with pytest.raises(ValueError, match="Info hash v1 mismatch"):
            await handle_v2_handshake(
                reader, writer, our_info_hash_v1=b"x" * INFO_HASH_V1_LEN
            )

    async def test_handle_v2_handshake_hybrid_v1_hash_mismatch(self):
        """Test handling hybrid handshake with v1 info_hash mismatch."""
        # Create hybrid handshake with wrong v1 hash
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        wrong_hash_v1 = b"w" * INFO_HASH_V1_LEN
        info_hash_v2 = b"y" * INFO_HASH_V2_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake_data = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + wrong_hash_v1
            + peer_id
        )

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(return_value=handshake_data)

        writer = MagicMock(spec=asyncio.StreamWriter)

        # Expect ValueError for v1 info_hash mismatch
        with pytest.raises(ValueError, match="Info hash v1 mismatch"):
            await handle_v2_handshake(
                reader,
                writer,
                our_info_hash_v1=b"x" * INFO_HASH_V1_LEN,
                our_info_hash_v2=info_hash_v2,
            )

    async def test_handle_v2_handshake_v1_hash_extraction(self):
        """Test v1 hash extraction from hybrid handshake."""
        # Create hybrid handshake (v1-only hash format) where parsed dict doesn't have v1 hash
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v1 = b"x" * INFO_HASH_V1_LEN
        peer_id = b"p" * PEER_ID_LEN

        handshake_data = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v1
            + peer_id
        )

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(return_value=handshake_data)

        writer = MagicMock(spec=asyncio.StreamWriter)

        # Should successfully extract v1 hash even if not in parsed dict (tests lines 553-554)
        version, received_peer_id, parsed = await handle_v2_handshake(
            reader, writer, our_info_hash_v1=info_hash_v1
        )

        assert version == ProtocolVersion.HYBRID
        assert received_peer_id == peer_id

    async def test_handle_v2_handshake_incomplete_read_error(self):
        """Test handling handshake with IncompleteReadError."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        
        # First call (v2 size) raises IncompleteReadError, second call also raises it
        from asyncio import IncompleteReadError
        incomplete_error = IncompleteReadError(b"partial", 80)
        reader.readexactly = AsyncMock(side_effect=[
            incomplete_error,  # First try (v2 size)
            IncompleteReadError(b"more partial", 68),  # Second try (v1 size)
        ])

        writer = MagicMock(spec=asyncio.StreamWriter)

        with pytest.raises(ProtocolVersionError, match="Incomplete handshake read"):
            await handle_v2_handshake(reader, writer)

    async def test_handle_v2_handshake_timeout(self):
        """Test handling handshake with timeout."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        writer = MagicMock(spec=asyncio.StreamWriter)

        with pytest.raises(asyncio.TimeoutError):
            await handle_v2_handshake(reader, writer, timeout=0.1)

    async def test_upgrade_to_v2_success(self):
        """Test successful protocol upgrade to v2."""
        # Mock connection with reader/writer
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)

        # Mock reader to return v2 handshake response
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN

        response_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        connection.reader = AsyncMock(spec=asyncio.StreamReader)
        connection.reader.readexactly = AsyncMock(return_value=response_handshake)

        result = await upgrade_to_v2(connection, info_hash_v2)

        assert result is True
        connection.writer.write.assert_called_once()
        connection.writer.drain.assert_awaited_once()

    async def test_upgrade_to_v2_no_writer(self):
        """Test protocol upgrade with no writer."""
        connection = MagicMock()
        connection.writer = None

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_to_v2_timeout(self):
        """Test protocol upgrade with timeout."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)
        connection.reader = AsyncMock(spec=asyncio.StreamReader)
        connection.reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_to_v2_hash_mismatch(self):
        """Test protocol upgrade with hash mismatch."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)

        # Mock reader to return handshake with wrong hash
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        wrong_hash = b"w" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN

        response_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + wrong_hash
            + peer_id
        )

        connection.reader = AsyncMock(spec=asyncio.StreamReader)
        connection.reader.readexactly = AsyncMock(return_value=response_handshake)

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_to_v2_general_exception(self):
        """Test protocol upgrade with general exception."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)
        connection.reader = AsyncMock(spec=asyncio.StreamReader)
        
        # Mock reader to raise general exception
        connection.reader.readexactly = AsyncMock(side_effect=Exception("Unexpected error"))

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_to_v2_exception_during_send(self):
        """Test protocol upgrade with exception during handshake send."""
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        
        # Mock writer to raise exception on write
        writer = AsyncMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock(side_effect=Exception("Write error"))
        connection.writer = writer
        
        connection.reader = AsyncMock(spec=asyncio.StreamReader)

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

    async def test_upgrade_to_v2_default_peer_id_generation(self):
        """Test protocol upgrade uses default peer_id when connection has none."""
        # This tests line 608: default peer_id generation
        connection = MagicMock()
        connection.our_peer_id = None  # No peer_id set
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)

        # Mock reader to return successful response
        reserved = bytearray(RESERVED_BYTES_LEN)
        reserved[0] |= 0x01
        info_hash_v2 = b"i" * INFO_HASH_V2_LEN
        peer_id = b"q" * PEER_ID_LEN

        response_handshake = (
            struct.pack("B", PROTOCOL_STRING_LEN)
            + PROTOCOL_STRING
            + bytes(reserved)
            + info_hash_v2
            + peer_id
        )

        connection.reader = AsyncMock(spec=asyncio.StreamReader)
        connection.reader.readexactly = AsyncMock(return_value=response_handshake)

        result = await upgrade_to_v2(connection, info_hash_v2)

        # Should succeed, and default peer_id should be used
        assert result is True
        # Verify that write was called (with default peer_id)
        connection.writer.write.assert_called_once()

    async def test_upgrade_to_v2_no_reader_returns_false(self):
        """Test protocol upgrade returns False when no reader."""
        # This tests line 639: return False path
        connection = MagicMock()
        connection.our_peer_id = b"p" * PEER_ID_LEN
        connection.writer = AsyncMock(spec=asyncio.StreamWriter)
        connection.reader = None  # No reader

        result = await upgrade_to_v2(connection, b"i" * INFO_HASH_V2_LEN)

        assert result is False

