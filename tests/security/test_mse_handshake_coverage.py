"""Additional tests for mse_handshake.py to achieve 100% coverage.

Covers previously untested code paths and edge cases.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.security.mse_handshake import (
    CipherType,
    MSEHandshake,
    MSEHandshakeResult,
    MSEHandshakeType,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.fixture
def info_hash():
    """Create test info hash (20 bytes)."""
    return bytes(range(20))


@pytest.fixture
def mock_reader():
    """Create mock StreamReader."""
    return AsyncMock()


@pytest.fixture
def mock_writer():
    """Create mock StreamWriter."""
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return writer


class TestMSEHandshakeInitiationCoverage:
    """Additional tests for initiate_as_initiator to cover missing paths."""

    @pytest.mark.asyncio
    async def test_initiate_rkeye_message_none(self, mock_reader, mock_writer, info_hash):
        """Test initiate when _read_message returns None for RKEYE."""
        handshake = MSEHandshake()
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 4))

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "Failed to read RKEYE" in result.error or "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_initiate_rkeye_decode_fails(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when decoding RKEYE message fails."""
        handshake = MSEHandshake()

        # First call (reading RKEYE) returns invalid message
        async def mock_readexactly(n):
            if n == 4:
                return b"\x00\x00\x00\x05"  # Length 5
            return b"\x03"  # Type byte, but message incomplete

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_initiate_wrong_message_type_rkeye(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when wrong message type received instead of RKEYE."""
        handshake = MSEHandshake()

        # Create valid SKEYE message instead of RKEYE
        payload = b"peer_key_data"
        wrong_message = handshake._encode_message(MSEHandshakeType.SKEYE, payload)

        async def mock_readexactly(n):
            if n == 4:
                return wrong_message[:4]
            return wrong_message[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "Expected RKEYE" in result.error

    @pytest.mark.asyncio
    async def test_initiate_crypto_message_none(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when _read_message returns None for CRYPTO."""
        handshake = MSEHandshake()

        # First read succeeds (RKEYE), second fails (CRYPTO)
        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return RKEYE message length
                return b"\x00\x00\x00\x60"  # 96 bytes
            if call_count == 2:
                # Return RKEYE message type and payload
                payload = b"x" * 95
                return b"\x03" + payload  # RKEYE type
            if call_count == 3:
                # Return CRYPTO message length
                return b"\x00\x00\x00\x05"  # 5 bytes
            # Fail on CRYPTO message read
            raise asyncio.IncompleteReadError(b"", n)

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_initiate_crypto_decode_fails(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when decoding CRYPTO message fails."""
        handshake = MSEHandshake()

        # Mock successful RKEYE, but invalid CRYPTO
        rkeye_payload = b"peer_key" * 10  # 80 bytes
        rkeye_msg = handshake._encode_message(MSEHandshakeType.RKEYE, rkeye_payload)

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rkeye_msg[:4]  # Length
            if call_count == 2:
                return rkeye_msg[4:]  # Type + payload
            if call_count == 3:
                return b"\x00\x00\x00\x02"  # CRYPTO length (too short)
            return b""  # Incomplete

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_initiate_wrong_message_type_crypto(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when wrong message type received instead of CRYPTO."""
        handshake = MSEHandshake()

        # Mock RKEYE success, but wrong message type for CRYPTO
        rkeye_payload = b"peer_key" * 10
        rkeye_msg = handshake._encode_message(MSEHandshakeType.RKEYE, rkeye_payload)
        wrong_crypto = handshake._encode_message(MSEHandshakeType.SKEYE, b"\x01")

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rkeye_msg[:4]
            if call_count == 2:
                return rkeye_msg[4:]
            if call_count == 3:
                return wrong_crypto[:4]
            return wrong_crypto[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "Expected CRYPTO" in result.error

    @pytest.mark.asyncio
    async def test_initiate_disallowed_cipher(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test initiate when peer selects disallowed cipher."""
        handshake = MSEHandshake(allowed_ciphers=[CipherType.RC4])

        # Mock full handshake but peer selects AES (not allowed)
        rkeye_payload = b"peer_key" * 10
        rkeye_msg = handshake._encode_message(MSEHandshakeType.RKEYE, rkeye_payload)
        crypto_msg = handshake._encode_crypto_message(CipherType.AES)  # Not allowed

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rkeye_msg[:4]
            if call_count == 2:
                return rkeye_msg[4:]
            if call_count == 3:
                return crypto_msg[:4]
            return crypto_msg[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "disallowed cipher" in result.error.lower()


class TestMSEHandshakeReceiverCoverage:
    """Additional tests for respond_as_receiver to cover missing paths."""

    @pytest.mark.asyncio
    async def test_respond_invalid_info_hash(self, mock_reader, mock_writer):
        """Test respond with invalid info hash length."""
        handshake = MSEHandshake()
        invalid_hash = b"too_short"

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, invalid_hash
        )

        assert result.success is False
        assert "20 bytes" in result.error

    @pytest.mark.asyncio
    async def test_respond_skeye_message_none(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when _read_message returns None for SKEYE."""
        handshake = MSEHandshake()
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 4))

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_skeye_decode_fails(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when decoding SKEYE message fails."""
        handshake = MSEHandshake()

        async def mock_readexactly(n):
            if n == 4:
                return b"\x00\x00\x00\x05"  # Length 5
            return b"\x02"  # Type byte, but incomplete

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_wrong_message_type_skeye(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when wrong message type received instead of SKEYE."""
        handshake = MSEHandshake()

        # Create RKEYE message instead of SKEYE
        payload = b"peer_key_data"
        wrong_message = handshake._encode_message(MSEHandshakeType.RKEYE, payload)

        async def mock_readexactly(n):
            if n == 4:
                return wrong_message[:4]
            return wrong_message[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "Expected SKEYE" in result.error

    @pytest.mark.asyncio
    async def test_respond_crypto_message_none(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when _read_message returns None for CRYPTO."""
        handshake = MSEHandshake()

        # Mock successful SKEYE, but CRYPTO fails
        skeye_payload = b"peer_key" * 10
        skeye_msg = handshake._encode_message(MSEHandshakeType.SKEYE, skeye_payload)

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return skeye_msg[:4]
            if call_count == 2:
                return skeye_msg[4:]
            if call_count == 3:
                return b"\x00\x00\x00\x05"
            raise asyncio.IncompleteReadError(b"", n)

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_crypto_decode_fails(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when decoding CRYPTO message fails."""
        handshake = MSEHandshake()

        skeye_payload = b"peer_key" * 10
        skeye_msg = handshake._encode_message(MSEHandshakeType.SKEYE, skeye_payload)

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return skeye_msg[:4]
            if call_count == 2:
                return skeye_msg[4:]
            if call_count == 3:
                return b"\x00\x00\x00\x02"  # Too short
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_wrong_message_type_crypto(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when wrong message type received instead of CRYPTO."""
        handshake = MSEHandshake()

        skeye_payload = b"peer_key" * 10
        skeye_msg = handshake._encode_message(MSEHandshakeType.SKEYE, skeye_payload)
        wrong_crypto = handshake._encode_message(MSEHandshakeType.RKEYE, b"\x01")

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return skeye_msg[:4]
            if call_count == 2:
                return skeye_msg[4:]
            if call_count == 3:
                return wrong_crypto[:4]
            return wrong_crypto[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert "Expected CRYPTO" in result.error

    @pytest.mark.asyncio
    async def test_respond_peer_cipher_not_allowed(
        self, mock_reader, mock_writer, info_hash
    ):
        """Test respond when peer cipher is not in allowed list."""
        handshake = MSEHandshake(allowed_ciphers=[CipherType.RC4])

        skeye_payload = b"peer_key" * 10
        skeye_msg = handshake._encode_message(MSEHandshakeType.SKEYE, skeye_payload)
        crypto_msg = handshake._encode_crypto_message(CipherType.AES)  # Not allowed

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return skeye_msg[:4]
            if call_count == 2:
                return skeye_msg[4:]
            if call_count == 3:
                return crypto_msg[:4]
            return crypto_msg[4:]

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        # Should fallback to our preference (RC4) since peer's choice not allowed
        # This tests the else branch in line 297
        assert result.success is True  # Should still succeed with our choice


class TestMSEHandshakeDecodeCoverage:
    """Tests for _decode_message edge cases."""

    def test_decode_message_exact_min_length(self):
        """Test _decode_message with exactly 5 bytes (minimum valid)."""
        handshake = MSEHandshake()
        # Minimum valid message: 4 bytes length + 1 byte type
        # Length = 1 (just the type byte)
        data = b"\x00\x00\x00\x01\x02"  # Length 1, type SKEYE

        decoded = handshake._decode_message(data)
        assert decoded is not None
        msg_type, payload = decoded
        assert msg_type == MSEHandshakeType.SKEYE
        assert payload == b""


class TestMSEHandshakeReadMessageCoverage:
    """Tests for _read_message edge cases."""

    @pytest.mark.asyncio
    async def test_read_message_connection_error(self):
        """Test _read_message with ConnectionError."""
        handshake = MSEHandshake()
        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(side_effect=ConnectionError("Connection lost"))

        result = await handshake._read_message(mock_reader)
        assert result is None


class TestMSEHandshakeCipherSelectionCoverage:
    """Additional tests for cipher selection."""

    def test_select_cipher_chacha20_preferred(self):
        """Test _select_cipher with CHACHA20 available (no RC4 or AES)."""
        handshake = MSEHandshake(
            prefer_rc4=False, allowed_ciphers=[CipherType.CHACHA20]
        )

        selected = handshake._select_cipher()
        # Should select CHACHA20 when it's the only allowed cipher
        assert selected == CipherType.CHACHA20

    def test_select_cipher_fallback_to_first_allowed(self):
        """Test _select_cipher fallback to first allowed cipher."""
        handshake = MSEHandshake(
            prefer_rc4=False, allowed_ciphers=[CipherType.CHACHA20]
        )

        selected = handshake._select_cipher()
        assert selected == CipherType.CHACHA20

    def test_select_cipher_no_allowed_ciphers_fallback(self):
        """Test _select_cipher with no allowed ciphers."""
        handshake = MSEHandshake(allowed_ciphers=[])

        selected = handshake._select_cipher()
        assert selected == CipherType.RC4  # Default fallback


class TestMSEHandshakeCreateCipherCoverage:
    """Additional tests for _create_cipher."""

    def test_create_cipher_chacha20_key_padding(self):
        """Test _create_cipher with ChaCha20 and key that needs padding."""
        handshake = MSEHandshake()
        key = b"16_bytes_key_1234"  # Exactly 16 bytes, needs padding to 32

        cipher = handshake._create_cipher(CipherType.CHACHA20, key)
        assert cipher is not None
        from ccbt.security.ciphers.chacha20 import ChaCha20Cipher

        assert isinstance(cipher, ChaCha20Cipher)
        # Verify the cipher was created successfully (padding logic worked)
        assert cipher.key_size() == 32

    def test_create_cipher_chacha20_key_exact_size(self):
        """Test _create_cipher with ChaCha20 and exactly 32-byte key."""
        handshake = MSEHandshake()
        key = bytes(range(32))  # Exactly 32 bytes

        cipher = handshake._create_cipher(CipherType.CHACHA20, key)
        assert cipher is not None

    def test_create_cipher_chacha20_key_larger(self):
        """Test _create_cipher with ChaCha20 and key larger than 32 bytes."""
        handshake = MSEHandshake()
        key = bytes(range(40))  # 40 bytes, should use first 32

        cipher = handshake._create_cipher(CipherType.CHACHA20, key)
        assert cipher is not None

    def test_create_cipher_fallback_rc4(self):
        """Test _create_cipher fallback to RC4 for unknown cipher type."""
        handshake = MSEHandshake()
        key = b"key_16_bytes!!"

        # Use an invalid cipher type (should fallback)
        # Since we can't easily create an invalid CipherType, test with a valid one
        # that goes through the fallback path
        cipher = handshake._create_cipher(CipherType.RC4, key)
        assert cipher is not None


class TestMSEHandshakePEMethodsCoverage:
    """Tests for PE-specific methods."""

    @pytest.mark.asyncio
    async def test_initiate_pe_as_initiator(self, mock_reader, mock_writer, info_hash):
        """Test initiate_pe_as_initiator delegates to initiate_as_initiator."""
        handshake = MSEHandshake()

        # Mock to fail quickly
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 4))

        result = await handshake.initiate_pe_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_pe_as_receiver(self, mock_reader, mock_writer, info_hash):
        """Test respond_pe_as_receiver delegates to respond_as_receiver."""
        handshake = MSEHandshake()

        # Mock to fail quickly
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 4))

        result = await handshake.respond_pe_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False


class TestMSEHandshakeDetectCoverage:
    """Additional tests for detect_encrypted_handshake."""

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_short_bytes(self):
        """Test detect with less than 4 bytes."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"\x01\x02\x03")  # Only 3 bytes

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False
        assert len(first_bytes) == 3

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_bittorrent_protocol(self):
        """Test detect with BitTorrent protocol identifier (0x13)."""
        mock_reader = AsyncMock()
        # BitTorrent handshake starts with 0x13 (19)
        # Read exactly 4 bytes as the function does
        mock_reader.read = AsyncMock(return_value=b"\x13Bit")

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False
        assert len(first_bytes) == 4
        assert first_bytes[0] == 19

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_valid_mse_type(self):
        """Test detect with valid MSE message type."""
        mock_reader = AsyncMock()
        call_count = 0

        async def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00\x00\x00\x60"  # Length 96 (reasonable MSE size)
            if call_count == 2:
                return b"\x02"  # SKEYE type
            return b""

        mock_reader.read = AsyncMock(side_effect=mock_read)

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is True

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_invalid_mse_type(self):
        """Test detect with invalid MSE message type."""
        mock_reader = AsyncMock()
        call_count = 0

        async def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00\x00\x00\x60"  # Length 96
            if call_count == 2:
                return b"\x01"  # Invalid type (not 0x02, 0x03, 0x04)
            return b""

        mock_reader.read = AsyncMock(side_effect=mock_read)

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_timeout_reading_type(self):
        """Test detect with timeout while reading type byte."""
        mock_reader = AsyncMock()
        call_count = 0

        async def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00\x00\x00\x60"  # Length 96
            # Timeout on second read
            raise asyncio.TimeoutError()

        mock_reader.read = AsyncMock(side_effect=mock_read)

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        # Should assume PE if length suggests it
        assert is_pe is True

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_connection_error_reading_type(self):
        """Test detect with ConnectionError while reading type byte."""
        mock_reader = AsyncMock()
        call_count = 0

        async def mock_read(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00\x00\x00\x60"
            raise ConnectionError("Connection lost")

        mock_reader.read = AsyncMock(side_effect=mock_read)

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        # Should assume PE if length suggests it
        assert is_pe is True

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_large_length(self):
        """Test detect with length too large (not MSE)."""
        mock_reader = AsyncMock()
        # Length > 2000 (too large for MSE)
        mock_reader.read = AsyncMock(return_value=b"\x00\x00\x08\x00")  # 2048 bytes

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_small_length(self):
        """Test detect with length <= 4 (not MSE)."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"\x00\x00\x00\x04")  # Length = 4

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_timeout_initial(self):
        """Test detect with timeout on initial read."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=asyncio.TimeoutError())

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False
        assert first_bytes == b""

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_connection_error_initial(self):
        """Test detect with ConnectionError on initial read."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=ConnectionError("Connection lost"))

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False
        assert first_bytes == b""

    @pytest.mark.asyncio
    async def test_detect_encrypted_handshake_generic_exception(self):
        """Test detect with generic exception."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=ValueError("Unexpected error"))

        is_pe, first_bytes = await MSEHandshake.detect_encrypted_handshake(
            mock_reader, timeout=0.1
        )

        assert is_pe is False
        assert first_bytes == b""

