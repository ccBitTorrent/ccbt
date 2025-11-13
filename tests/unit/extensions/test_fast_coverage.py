"""Additional tests for extensions/fast.py to achieve coverage."""

from __future__ import annotations

import struct

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.extensions]

from ccbt.extensions.fast import FastExtension, FastMessageType


class TestFastExtensionCoverage:
    """Test coverage gaps in Fast Extension."""

    def test_decode_handshake_short_data(self):
        """Test decode_handshake with short data (line 67)."""
        extension = FastExtension()
        result = extension.decode_handshake(b"short")
        assert result == extension.capabilities.__class__()

    def test_decode_suggest_invalid_message_type(self):
        """Test decode_suggest with invalid message type (line 92-95)."""
        extension = FastExtension()
        # Use wrong message type
        invalid_data = struct.pack("!BI", FastMessageType.HAVE_ALL, 123)
        
        with pytest.raises(ValueError, match="Invalid message type for Suggest"):
            extension.decode_suggest(invalid_data)

    def test_decode_have_all_short_data(self):
        """Test decode_have_all with short data (line 105)."""
        extension = FastExtension()
        result = extension.decode_have_all(b"")
        assert result is False

    def test_decode_have_none_short_data(self):
        """Test decode_have_none with short data (line 116)."""
        extension = FastExtension()
        result = extension.decode_have_none(b"")
        assert result is False

    def test_decode_reject_invalid_message_type(self):
        """Test decode_reject with invalid message type (line 133-136)."""
        extension = FastExtension()
        # Use wrong message type
        invalid_data = struct.pack("!BIII", FastMessageType.HAVE_ALL, 0, 0, 1024)
        
        with pytest.raises(ValueError, match="Invalid message type for Reject"):
            extension.decode_reject(invalid_data)

    def test_decode_allow_fast_short_data(self):
        """Test decode_allow_fast with short data (line 146-148)."""
        extension = FastExtension()
        with pytest.raises(ValueError):
            extension.decode_allow_fast(b"short")

    def test_decode_allow_fast_invalid_message_type(self):
        """Test decode_allow_fast with invalid message type (line 152-155)."""
        extension = FastExtension()
        # Use wrong message type
        invalid_data = struct.pack("!BI", FastMessageType.HAVE_ALL, 123)
        
        with pytest.raises(ValueError, match="Invalid message type for Allow Fast"):
            extension.decode_allow_fast(invalid_data)

