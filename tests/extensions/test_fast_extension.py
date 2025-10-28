"""Tests for Fast Extension (BEP 6).
"""

import struct

import pytest

from ccbt.extensions.fast import FastCapabilities, FastExtension, FastMessageType


class TestFastExtension:
    """Tests for Fast Extension."""

    @pytest.fixture
    def fast_extension(self):
        """Create Fast Extension instance."""
        return FastExtension()

    def test_capabilities_creation(self):
        """Test FastCapabilities creation."""
        caps = FastCapabilities(
            suggest=True,
            have_all=True,
            have_none=True,
            reject=True,
            allow_fast=True,
        )

        assert caps.suggest
        assert caps.have_all
        assert caps.have_none
        assert caps.reject
        assert caps.allow_fast

    def test_encode_handshake(self, fast_extension):
        """Test handshake encoding."""
        data = fast_extension.encode_handshake()
        assert isinstance(data, bytes)
        assert len(data) == 8

        # Check that Fast Extension bit is set
        extension_bits = struct.unpack("!Q", data)[0]
        assert (extension_bits & 0x04) != 0

    def test_decode_handshake(self, fast_extension):
        """Test handshake decoding."""
        # Create test handshake data
        extension_bits = 0x1F  # All bits set
        data = struct.pack("!Q", extension_bits)

        caps = fast_extension.decode_handshake(data)
        assert caps.suggest
        assert caps.have_all
        assert caps.have_none
        assert caps.reject
        assert caps.allow_fast

    def test_encode_suggest(self, fast_extension):
        """Test Suggest message encoding."""
        piece_index = 42
        data = fast_extension.encode_suggest(piece_index)

        assert isinstance(data, bytes)
        assert len(data) == 5

        message_type, decoded_index = struct.unpack("!BI", data)
        assert message_type == FastMessageType.SUGGEST
        assert decoded_index == piece_index

    def test_decode_suggest(self, fast_extension):
        """Test Suggest message decoding."""
        piece_index = 42
        data = struct.pack("!BI", FastMessageType.SUGGEST, piece_index)

        decoded_index = fast_extension.decode_suggest(data)
        assert decoded_index == piece_index

    def test_encode_have_all(self, fast_extension):
        """Test Have All message encoding."""
        data = fast_extension.encode_have_all()

        assert isinstance(data, bytes)
        assert len(data) == 1
        assert data[0] == FastMessageType.HAVE_ALL

    def test_decode_have_all(self, fast_extension):
        """Test Have All message decoding."""
        data = struct.pack("!B", FastMessageType.HAVE_ALL)

        result = fast_extension.decode_have_all(data)
        assert result

    def test_encode_have_none(self, fast_extension):
        """Test Have None message encoding."""
        data = fast_extension.encode_have_none()

        assert isinstance(data, bytes)
        assert len(data) == 1
        assert data[0] == FastMessageType.HAVE_NONE

    def test_decode_have_none(self, fast_extension):
        """Test Have None message decoding."""
        data = struct.pack("!B", FastMessageType.HAVE_NONE)

        result = fast_extension.decode_have_none(data)
        assert result

    def test_encode_reject(self, fast_extension):
        """Test Reject message encoding."""
        index, begin, length = 1, 2, 3
        data = fast_extension.encode_reject(index, begin, length)

        assert isinstance(data, bytes)
        assert len(data) == 13

        message_type, decoded_index, decoded_begin, decoded_length = struct.unpack(
            "!BIII",
            data,
        )
        assert message_type == FastMessageType.REJECT
        assert decoded_index == index
        assert decoded_begin == begin
        assert decoded_length == length

    def test_decode_reject(self, fast_extension):
        """Test Reject message decoding."""
        index, begin, length = 1, 2, 3
        data = struct.pack("!BIII", FastMessageType.REJECT, index, begin, length)

        decoded_index, decoded_begin, decoded_length = fast_extension.decode_reject(
            data,
        )
        assert decoded_index == index
        assert decoded_begin == begin
        assert decoded_length == length

    def test_encode_allow_fast(self, fast_extension):
        """Test Allow Fast message encoding."""
        piece_index = 42
        data = fast_extension.encode_allow_fast(piece_index)

        assert isinstance(data, bytes)
        assert len(data) == 5

        message_type, decoded_index = struct.unpack("!BI", data)
        assert message_type == FastMessageType.ALLOW_FAST
        assert decoded_index == piece_index

    def test_decode_allow_fast(self, fast_extension):
        """Test Allow Fast message decoding."""
        piece_index = 42
        data = struct.pack("!BI", FastMessageType.ALLOW_FAST, piece_index)

        decoded_index = fast_extension.decode_allow_fast(data)
        assert decoded_index == piece_index

    def test_invalid_message_types(self, fast_extension):
        """Test invalid message types."""
        # Test invalid Suggest message
        with pytest.raises(ValueError, match="Invalid Suggest message"):
            fast_extension.decode_suggest(b"")

        # Test invalid Reject message
        with pytest.raises(ValueError, match="Invalid Reject message"):
            fast_extension.decode_reject(b"")

        # Test invalid Allow Fast message
        with pytest.raises(ValueError, match="Invalid Allow Fast message"):
            fast_extension.decode_allow_fast(b"")

    def test_suggested_pieces_management(self, fast_extension):
        """Test suggested pieces management."""
        # Initially empty
        assert len(fast_extension.get_suggested_pieces()) == 0

        # Add suggestions
        fast_extension.suggested_pieces.add(1)
        fast_extension.suggested_pieces.add(2)

        suggested = fast_extension.get_suggested_pieces()
        assert len(suggested) == 2
        assert 1 in suggested
        assert 2 in suggested

        # Clear suggestions
        fast_extension.clear_suggestions()
        assert len(fast_extension.get_suggested_pieces()) == 0

    def test_allowed_fast_management(self, fast_extension):
        """Test allowed fast pieces management."""
        # Initially empty
        assert len(fast_extension.get_allowed_fast_pieces()) == 0

        # Add allowed fast pieces
        fast_extension.allowed_fast.add(1)
        fast_extension.allowed_fast.add(2)

        allowed = fast_extension.get_allowed_fast_pieces()
        assert len(allowed) == 2
        assert 1 in allowed
        assert 2 in allowed

        # Test is_piece_allowed_fast
        assert fast_extension.is_piece_allowed_fast(1)
        assert fast_extension.is_piece_allowed_fast(2)
        assert not fast_extension.is_piece_allowed_fast(3)

        # Clear allowed fast pieces
        fast_extension.clear_allowed_fast()
        assert len(fast_extension.get_allowed_fast_pieces()) == 0

    def test_rejected_requests_management(self, fast_extension):
        """Test rejected requests management."""
        # Initially empty
        assert len(fast_extension.get_rejected_requests()) == 0

        # Add rejected requests
        fast_extension.rejected_requests.add((1, 2, 3))
        fast_extension.rejected_requests.add((4, 5, 6))

        rejected = fast_extension.get_rejected_requests()
        assert len(rejected) == 2
        assert (1, 2, 3) in rejected
        assert (4, 5, 6) in rejected

        # Test is_request_rejected
        assert fast_extension.is_request_rejected(1, 2, 3)
        assert fast_extension.is_request_rejected(4, 5, 6)
        assert not fast_extension.is_request_rejected(7, 8, 9)

        # Clear rejected requests
        fast_extension.clear_rejected_requests()
        assert len(fast_extension.get_rejected_requests()) == 0

    def test_capabilities_management(self, fast_extension):
        """Test capabilities management."""
        # Get default capabilities
        caps = fast_extension.get_capabilities()
        assert isinstance(caps, FastCapabilities)

        # Set new capabilities
        new_caps = FastCapabilities(
            suggest=True,
            have_all=True,
            have_none=True,
            reject=True,
            allow_fast=True,
        )
        fast_extension.set_capabilities(new_caps)

        updated_caps = fast_extension.get_capabilities()
        assert updated_caps.suggest
        assert updated_caps.have_all
        assert updated_caps.have_none
        assert updated_caps.reject
        assert updated_caps.allow_fast

    def test_roundtrip_encoding(self, fast_extension):
        """Test roundtrip encoding/decoding."""
        # Test Suggest
        piece_index = 42
        encoded = fast_extension.encode_suggest(piece_index)
        decoded = fast_extension.decode_suggest(encoded)
        assert decoded == piece_index

        # Test Reject
        index, begin, length = 1, 2, 3
        encoded = fast_extension.encode_reject(index, begin, length)
        decoded_index, decoded_begin, decoded_length = fast_extension.decode_reject(
            encoded,
        )
        assert decoded_index == index
        assert decoded_begin == begin
        assert decoded_length == length

        # Test Allow Fast
        piece_index = 42
        encoded = fast_extension.encode_allow_fast(piece_index)
        decoded = fast_extension.decode_allow_fast(encoded)
        assert decoded == piece_index
