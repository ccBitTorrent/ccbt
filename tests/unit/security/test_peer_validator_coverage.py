"""Additional tests for peer_validator.py to achieve coverage for testable paths."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.models import PeerInfo
from ccbt.security.peer_validator import PeerValidator


class TestPeerValidatorCoverage:
    """Test coverage gaps in peer validator."""

    @pytest.mark.asyncio
    async def test_validate_handshake_exception_path(self):
        """Test handshake validation exception handling (line 123-125)."""
        validator = PeerValidator()
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)

        # Trigger exception by mocking _validate_info_hash to raise
        original_validate = validator._validate_info_hash
        validator._validate_info_hash = Mock(side_effect=ValueError("Test error"))

        # Use valid length handshake (68 bytes) to get past length and protocol checks
        # 19 (protocol) + 8 (reserved) + 20 (info_hash) + 20 (peer_id) + 1 = 68 bytes
        invalid_handshake = b"BitTorrent protocol" + b"\x00" * 8 + b"\x01" * 20 + b"\x02" * 20 + b"\x00"  # 68 bytes total

        is_valid, reason = await validator.validate_handshake(
            peer_info, invalid_handshake
        )

        assert is_valid is False
        assert "Handshake validation error" in reason

        # Restore
        validator._validate_info_hash = original_validate

    @pytest.mark.asyncio
    async def test_validate_message_exception_path(self):
        """Test message validation exception handling (line 158-160)."""
        validator = PeerValidator()
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)

        # Trigger exception with invalid message
        invalid_message = "not bytes"  # type: ignore[arg-type]

        is_valid, reason = await validator.validate_message(
            peer_info, invalid_message  # type: ignore[arg-type]
        )

        assert is_valid is False
        assert "Message validation error" in reason

    @pytest.mark.asyncio
    async def test_validate_message_format_decode_error(self):
        """Test message format validation decode error (lines 305-309)."""
        validator = PeerValidator()

        # Invalid message format that causes decode error
        # Use message with length that causes IndexError
        invalid_message = b"\x00\x00"  # Too short, will cause decode error

        result = validator._validate_message_format(invalid_message)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_info_hash_invalid_length(self):
        """Test info hash validation with wrong length."""
        validator = PeerValidator()

        # Wrong length info hash
        invalid_hash = b"short"  # Not 20 bytes
        result = validator._validate_info_hash(invalid_hash)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_info_hash_all_zeros(self):
        """Test info hash validation with all zeros."""
        validator = PeerValidator()

        # All zeros info hash
        zero_hash = b"\x00" * 20
        result = validator._validate_info_hash(zero_hash)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_info_hash_all_ffs(self):
        """Test info hash validation with all Fs."""
        validator = PeerValidator()

        # All Fs info hash
        ff_hash = b"\xff" * 20
        result = validator._validate_info_hash(ff_hash)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_peer_id_wrong_length(self):
        """Test peer ID validation with wrong length."""
        validator = PeerValidator()

        # Wrong length peer ID
        invalid_peer_id = b"short"
        result = validator._validate_peer_id(invalid_peer_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_assess_peer_quality_no_metrics(self):
        """Test assess_peer_quality when no metrics available (line 178-179)."""
        validator = PeerValidator()
        peer_info = PeerInfo(ip="192.168.1.100", port=6881, peer_id=b"test_peer_id_20_byte")

        quality_score, details = await validator.assess_peer_quality(peer_info)

        assert quality_score == 0.0
        assert "No validation data available" in details["reason"]
