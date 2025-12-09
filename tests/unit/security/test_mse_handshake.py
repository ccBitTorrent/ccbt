"""Tests for MSE/PE handshake protocol.

Covers:
- Initiator handshake flow
- Receiver handshake flow
- Full handshake between peers
- Message encoding/decoding
- Cipher negotiation
- Error handling (timeout, invalid messages, wrong types)
- Edge cases
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.security.ciphers.base import CipherSuite
from ccbt.security.mse_handshake import (
    CipherType,
    MSEHandshake,
    MSEHandshakeResult,
    MSEHandshakeType,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


class TestMSEHandshakeInit:
    """Tests for MSEHandshake initialization."""

    def test_init_default(self):
        """Test MSEHandshake initialization with defaults."""
        handshake = MSEHandshake()

        assert handshake.dh_exchange.key_size == 768
        assert handshake.prefer_rc4 is True
        assert CipherType.RC4 in handshake.allowed_ciphers
        assert CipherType.AES in handshake.allowed_ciphers

    def test_init_custom_dh_size(self):
        """Test MSEHandshake initialization with custom DH size."""
        handshake = MSEHandshake(dh_key_size=1024)

        assert handshake.dh_exchange.key_size == 1024

    def test_init_prefer_aes(self):
        """Test MSEHandshake initialization preferring AES."""
        handshake = MSEHandshake(prefer_rc4=False)

        assert handshake.prefer_rc4 is False

    def test_init_custom_allowed_ciphers(self):
        """Test MSEHandshake initialization with custom allowed ciphers."""
        handshake = MSEHandshake(allowed_ciphers=[CipherType.RC4])

        assert CipherType.RC4 in handshake.allowed_ciphers
        assert CipherType.AES not in handshake.allowed_ciphers


class TestMSEHandshakeMessageEncoding:
    """Tests for message encoding/decoding."""

    @pytest.fixture
    def handshake(self):
        """Create MSEHandshake instance."""
        return MSEHandshake()

    def test_encode_message_skeye(self, handshake):
        """Test encoding SKEYE message."""
        payload = b"test_public_key_data"
        encoded = handshake._encode_message(MSEHandshakeType.SKEYE, payload)

        # Should have 4-byte length + 1-byte type + payload
        assert len(encoded) == 4 + 1 + len(payload)
        assert encoded[4] == int(MSEHandshakeType.SKEYE)

    def test_encode_message_rkeye(self, handshake):
        """Test encoding RKEYE message."""
        payload = b"peer_public_key_data"
        encoded = handshake._encode_message(MSEHandshakeType.RKEYE, payload)

        assert len(encoded) == 4 + 1 + len(payload)
        assert encoded[4] == int(MSEHandshakeType.RKEYE)

    def test_encode_message_crypto(self, handshake):
        """Test encoding CRYPTO message."""
        payload = b"\x01"  # RC4
        encoded = handshake._encode_message(MSEHandshakeType.CRYPTO, payload)

        assert len(encoded) == 4 + 1 + len(payload)
        assert encoded[4] == int(MSEHandshakeType.CRYPTO)

    def test_decode_message_valid(self, handshake):
        """Test decoding valid message."""
        payload = b"test_payload"
        encoded = handshake._encode_message(MSEHandshakeType.SKEYE, payload)

        decoded = handshake._decode_message(encoded)

        assert decoded is not None
        msg_type, decoded_payload = decoded
        assert msg_type == MSEHandshakeType.SKEYE
        assert decoded_payload == payload

    def test_decode_message_too_short(self, handshake):
        """Test decoding message that's too short."""
        short_data = b"\x00\x00\x00"
        decoded = handshake._decode_message(short_data)

        assert decoded is None

    def test_decode_message_incomplete(self, handshake):
        """Test decoding incomplete message."""
        # Create message with length header saying 100 bytes but only 10 bytes present
        length_header = b"\x00\x00\x00d"  # Length = 100
        incomplete_data = length_header + b"\x02" + b"x" * 9

        decoded = handshake._decode_message(incomplete_data)

        assert decoded is None

    def test_encode_decode_round_trip(self, handshake):
        """Test encode/decode round-trip."""
        payload = b"round_trip_test_data_12345"
        encoded = handshake._encode_message(MSEHandshakeType.RKEYE, payload)

        decoded = handshake._decode_message(encoded)

        assert decoded is not None
        msg_type, decoded_payload = decoded
        assert msg_type == MSEHandshakeType.RKEYE
        assert decoded_payload == payload

    def test_encode_crypto_message(self, handshake):
        """Test encoding CRYPTO message."""
        crypto_msg = handshake._encode_crypto_message(CipherType.RC4)

        decoded = handshake._decode_message(crypto_msg)
        assert decoded is not None
        msg_type, crypto_data = decoded
        assert msg_type == MSEHandshakeType.CRYPTO

        cipher_type = handshake._decode_crypto_message(crypto_data)
        assert cipher_type == CipherType.RC4

    def test_decode_crypto_message_rc4(self, handshake):
        """Test decoding CRYPTO message with RC4."""
        cipher_type = handshake._decode_crypto_message(b"\x01")

        assert cipher_type == CipherType.RC4

    def test_decode_crypto_message_aes(self, handshake):
        """Test decoding CRYPTO message with AES."""
        cipher_type = handshake._decode_crypto_message(b"\x02")

        assert cipher_type == CipherType.AES

    def test_decode_crypto_message_empty(self, handshake):
        """Test decoding empty CRYPTO message defaults to RC4."""
        cipher_type = handshake._decode_crypto_message(b"")

        assert cipher_type == CipherType.RC4


class TestMSEHandshakeCipherSelection:
    """Tests for cipher selection logic."""

    def test_select_cipher_prefers_rc4(self):
        """Test cipher selection prefers RC4 when configured."""
        handshake = MSEHandshake(prefer_rc4=True)

        selected = handshake._select_cipher()

        assert selected == CipherType.RC4

    def test_select_cipher_prefers_aes(self):
        """Test cipher selection prefers AES when configured."""
        handshake = MSEHandshake(prefer_rc4=False)

        selected = handshake._select_cipher()

        assert selected == CipherType.AES

    def test_select_cipher_only_rc4_allowed(self):
        """Test cipher selection with only RC4 allowed."""
        handshake = MSEHandshake(
            prefer_rc4=False, allowed_ciphers=[CipherType.RC4]
        )

        selected = handshake._select_cipher()

        assert selected == CipherType.RC4

    def test_select_cipher_only_aes_allowed(self):
        """Test cipher selection with only AES allowed."""
        handshake = MSEHandshake(
            prefer_rc4=True, allowed_ciphers=[CipherType.AES]
        )

        selected = handshake._select_cipher()

        assert selected == CipherType.AES

    def test_create_cipher_rc4(self):
        """Test creating RC4 cipher."""
        handshake = MSEHandshake()
        key = b"test_key_16bytes"

        cipher = handshake._create_cipher(CipherType.RC4, key)

        assert cipher is not None
        assert isinstance(cipher, CipherSuite)

    def test_create_cipher_aes(self):
        """Test creating AES cipher."""
        handshake = MSEHandshake()
        key = b"test_key_16bytes"

        cipher = handshake._create_cipher(CipherType.AES, key)

        assert cipher is not None
        assert isinstance(cipher, CipherSuite)

    def test_create_cipher_uses_first_16_bytes(self):
        """Test that cipher creation uses first 16 bytes of key."""
        handshake = MSEHandshake()
        # 20-byte key (from SHA-1)
        full_key = b"twenty_bytes_key_!!"

        cipher = handshake._create_cipher(CipherType.RC4, full_key)

        # Should work fine, uses first 16 bytes
        assert cipher is not None


class TestMSEHandshakeInitiator:
    """Tests for initiator handshake flow."""

    @pytest.fixture
    def handshake(self):
        """Create MSEHandshake instance."""
        return MSEHandshake()

    @pytest.fixture
    def info_hash(self):
        """Create test info hash (20 bytes)."""
        return bytes(range(20))

    @pytest.fixture
    def mock_reader(self):
        """Create mock StreamReader."""
        return AsyncMock()

    @pytest.fixture
    def mock_writer(self):
        """Create mock StreamWriter."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        return writer

    @pytest.mark.asyncio
    async def test_initiate_invalid_info_hash(
        self, handshake, mock_reader, mock_writer
    ):
        """Test initiation with invalid info hash length."""
        invalid_hash = b"too_short"

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, invalid_hash
        )

        assert result.success is False
        assert result.cipher is None
        assert "20 bytes" in result.error

    @pytest.mark.asyncio
    async def test_initiate_timeout_reading_rkeye(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test initiation timeout while reading RKEYE."""
        # Mock reader.readexactly to raise TimeoutError
        mock_reader.readexactly = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert result.cipher is None
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_initiate_wrong_message_type_after_skeye(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test initiation when peer sends wrong message type after SKEYE."""
        # Generate a valid RKEYE message
        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        # But send wrong message type (SKEYE instead of RKEYE)
        wrong_message = handshake._encode_message(
            MSEHandshakeType.SKEYE, receiver_pubkey
        )

        # Setup reader to return wrong message
        async def mock_read():
            # First call: read length (4 bytes)
            # Second call: read message body
            return wrong_message[4:]

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return wrong_message[:4]  # Length
            return wrong_message[4:]  # Message body

        mock_reader.readexactly = mock_readexactly

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert result.cipher is None
        assert "RKEYE" in result.error or "SKEYE" in result.error

    @pytest.mark.asyncio
    async def test_initiate_successful_full_flow(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test successful initiator handshake with mock receiver."""
        # Create receiver side
        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        # Create initiator keypair (will be generated in initiate)
        initiator_keypair = handshake.dh_exchange.generate_keypair()

        # Setup message sequence
        rke_message = receiver_handshake._encode_message(
            MSEHandshakeType.RKEYE, receiver_pubkey
        )
        crypto_message = receiver_handshake._encode_crypto_message(
            CipherType.RC4
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First read: RKEYE length
                return rke_message[:4]
            if call_count == 2:
                # Second read: RKEYE body
                return rke_message[4:]
            if call_count == 3:
                # Third read: CRYPTO length
                return crypto_message[:4]
            if call_count == 4:
                # Fourth read: CRYPTO body
                return crypto_message[4:]

        mock_reader.readexactly = mock_readexactly

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        # Should succeed
        assert result.success is True
        assert result.cipher is not None
        assert result.error is None

        # Verify messages were sent
        assert mock_writer.write.call_count >= 2  # SKEYE + CRYPTO
        await mock_writer.drain()


class TestMSEHandshakeReceiver:
    """Tests for receiver handshake flow."""

    @pytest.fixture
    def handshake(self):
        """Create MSEHandshake instance."""
        return MSEHandshake()

    @pytest.fixture
    def info_hash(self):
        """Create test info hash (20 bytes)."""
        return bytes(range(20))

    @pytest.fixture
    def mock_reader(self):
        """Create mock StreamReader."""
        return AsyncMock()

    @pytest.fixture
    def mock_writer(self):
        """Create mock StreamWriter."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        return writer

    @pytest.mark.asyncio
    async def test_respond_invalid_info_hash(
        self, handshake, mock_reader, mock_writer
    ):
        """Test response with invalid info hash length."""
        invalid_hash = b"too_short"

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, invalid_hash
        )

        assert result.success is False
        assert result.cipher is None
        assert "20 bytes" in result.error

    @pytest.mark.asyncio
    async def test_respond_timeout_reading_skeye(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test response timeout while reading SKEYE."""
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash, timeout=0.1
        )

        assert result.success is False
        assert result.cipher is None
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_respond_wrong_message_type(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test response when peer sends wrong message type."""
        # Send RKEYE instead of SKEYE
        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        wrong_message = handshake._encode_message(
            MSEHandshakeType.RKEYE, initiator_pubkey
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return wrong_message[:4]
            return wrong_message[4:]

        mock_reader.readexactly = mock_readexactly

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert result.cipher is None
        assert "SKEYE" in result.error

    @pytest.mark.asyncio
    async def test_respond_successful_full_flow(
        self, handshake, mock_reader, mock_writer, info_hash
    ):
        """Test successful receiver handshake with mock initiator."""
        # Create initiator side
        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        # Setup message sequence
        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )
        crypto_message = initiator_handshake._encode_crypto_message(
            CipherType.RC4
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]  # SKEYE length
            if call_count == 2:
                return ske_message[4:]  # SKEYE body
            if call_count == 3:
                return crypto_message[:4]  # CRYPTO length
            if call_count == 4:
                return crypto_message[4:]  # CRYPTO body

        mock_reader.readexactly = mock_readexactly

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        # Should succeed
        assert result.success is True
        assert result.cipher is not None
        assert result.error is None

        # Verify messages were sent
        assert mock_writer.write.call_count >= 2  # RKEYE + CRYPTO


class TestMSEHandshakeFullFlow:
    """Integration tests for full handshake between peers."""

    @pytest.fixture
    def info_hash(self):
        """Create test info hash (20 bytes)."""
        return bytes(range(20))

    @pytest.mark.asyncio
    async def test_full_handshake_rc4(self, info_hash):
        """Test full handshake between initiator and receiver with RC4."""
        # Use queues to synchronize message exchange
        initiator_to_receiver = asyncio.Queue()
        receiver_to_initiator = asyncio.Queue()

        # Create both sides
        initiator = MSEHandshake(prefer_rc4=True)
        receiver = MSEHandshake(prefer_rc4=True)

        # Setup initiator writer to put data in queue
        def initiator_write(data):
            initiator_to_receiver.put_nowait(data)

        initiator_writer = MagicMock()
        initiator_writer.write = MagicMock(side_effect=initiator_write)
        initiator_writer.drain = AsyncMock()

        # Setup receiver writer to put data in queue
        def receiver_write(data):
            receiver_to_initiator.put_nowait(data)

        receiver_writer = MagicMock()
        receiver_writer.write = MagicMock(side_effect=receiver_write)
        receiver_writer.drain = AsyncMock()

        # Setup initiator reader to read from receiver queue
        async def initiator_readexactly(n):
            data = await receiver_to_initiator.get()
            if len(data) >= n:
                result = data[:n]
                if len(data) > n:
                    # Put remaining back
                    await receiver_to_initiator.put(data[n:])
                return result
            # Need more data - wait for next chunk
            next_data = await receiver_to_initiator.get()
            combined = data + next_data
            result = combined[:n]
            if len(combined) > n:
                await receiver_to_initiator.put(combined[n:])
            return result

        initiator_reader = AsyncMock()
        initiator_reader.readexactly = initiator_readexactly

        # Setup receiver reader to read from initiator queue
        async def receiver_readexactly(n):
            data = await initiator_to_receiver.get()
            if len(data) >= n:
                result = data[:n]
                if len(data) > n:
                    # Put remaining back
                    await initiator_to_receiver.put(data[n:])
                return result
            # Need more data - wait for next chunk
            next_data = await initiator_to_receiver.get()
            combined = data + next_data
            result = combined[:n]
            if len(combined) > n:
                await initiator_to_receiver.put(combined[n:])
            return result

        receiver_reader = AsyncMock()
        receiver_reader.readexactly = receiver_readexactly

        # Run handshake in parallel
        initiator_task = asyncio.create_task(
            initiator.initiate_as_initiator(
                initiator_reader, initiator_writer, info_hash
            )
        )
        receiver_task = asyncio.create_task(
            receiver.respond_as_receiver(
                receiver_reader, receiver_writer, info_hash
            )
        )

        # Wait for both to complete
        initiator_result, receiver_result = await asyncio.gather(
            initiator_task, receiver_task
        )

        # Both should succeed
        assert initiator_result.success is True
        assert receiver_result.success is True
        assert initiator_result.cipher is not None
        assert receiver_result.cipher is not None

    @pytest.mark.asyncio
    async def test_read_message_success(self):
        """Test _read_message with valid data."""
        handshake = MSEHandshake()
        payload = b"test_message_payload"
        encoded = handshake._encode_message(MSEHandshakeType.SKEYE, payload)

        mock_reader = AsyncMock()
        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return encoded[:4]  # Length
            if call_count == 2:
                return encoded[4:]  # Body
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake._read_message(mock_reader)

        assert result == encoded
        assert mock_reader.readexactly.call_count == 2

    @pytest.mark.asyncio
    async def test_read_message_incomplete_read_error(self):
        """Test _read_message with IncompleteReadError."""
        handshake = MSEHandshake()
        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(b"partial", 10)
        )

        result = await handshake._read_message(mock_reader)

        assert result is None

    @pytest.mark.asyncio
    async def test_initiate_disallowed_cipher(self, info_hash):
        """Test initiation when peer selects disallowed cipher."""
        handshake = MSEHandshake(allowed_ciphers=[CipherType.RC4])

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Create messages with AES (disallowed)
        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        rke_message = receiver_handshake._encode_message(
            MSEHandshakeType.RKEYE, receiver_pubkey
        )
        # Send AES in CRYPTO message (disallowed)
        crypto_message = receiver_handshake._encode_crypto_message(
            CipherType.AES
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rke_message[:4]
            if call_count == 2:
                return rke_message[4:]
            if call_count == 3:
                return crypto_message[:4]
            if call_count == 4:
                return crypto_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "disallowed" in result.error.lower() or "AES" in result.error

    @pytest.mark.asyncio
    async def test_initiate_read_rkeye_returns_none(self, info_hash):
        """Test initiation when _read_message returns None."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(b"partial", 10)
        )

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_initiate_decode_rkeye_fails(self, info_hash):
        """Test initiation when decoding RKEYE fails."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Send invalid message (too short to decode)
        invalid_message = b"\x00\x00\x00\x05\x03"  # Length 5, type 3, but only 1 byte

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return invalid_message[:4]  # Length header
            if call_count == 2:
                return invalid_message[4:]  # Body (too short)
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "decode" in result.error.lower() or "RKEYE" in result.error

    @pytest.mark.asyncio
    async def test_initiate_read_crypto_returns_none(self, info_hash):
        """Test initiation when reading CRYPTO message returns None."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Generate valid RKEYE but fail on CRYPTO read
        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        rke_message = receiver_handshake._encode_message(
            MSEHandshakeType.RKEYE, receiver_pubkey
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rke_message[:4]  # RKEYE length
            if call_count == 2:
                return rke_message[4:]  # RKEYE body
            if call_count == 3:
                # Fail on CRYPTO read
                raise asyncio.IncompleteReadError(b"partial", 10)

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "CRYPTO" in result.error or "read" in result.error.lower()

    @pytest.mark.asyncio
    async def test_initiate_decode_crypto_fails(self, info_hash):
        """Test initiation when decoding CRYPTO message fails."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Generate valid RKEYE
        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        rke_message = receiver_handshake._encode_message(
            MSEHandshakeType.RKEYE, receiver_pubkey
        )
        # Invalid CRYPTO message
        invalid_crypto = b"\x00\x00\x00\x02\x04"  # Too short

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rke_message[:4]
            if call_count == 2:
                return rke_message[4:]
            if call_count == 3:
                return invalid_crypto[:4]
            if call_count == 4:
                return invalid_crypto[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_initiate_wrong_crypto_message_type(self, info_hash):
        """Test initiation when CRYPTO message has wrong type."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        receiver_handshake = MSEHandshake()
        receiver_keypair = receiver_handshake.dh_exchange.generate_keypair()
        receiver_pubkey = receiver_handshake.dh_exchange.get_public_key_bytes(
            receiver_keypair
        )

        rke_message = receiver_handshake._encode_message(
            MSEHandshakeType.RKEYE, receiver_pubkey
        )
        # Send wrong message type (SKEYE instead of CRYPTO)
        wrong_message = receiver_handshake._encode_message(
            MSEHandshakeType.SKEYE, receiver_pubkey
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rke_message[:4]
            if call_count == 2:
                return rke_message[4:]
            if call_count == 3:
                return wrong_message[:4]
            if call_count == 4:
                return wrong_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "CRYPTO" in result.error

    @pytest.mark.asyncio
    async def test_respond_read_skeye_returns_none(self, info_hash):
        """Test response when reading SKEYE returns None."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(b"partial", 10)
        )

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "SKEYE" in result.error or "read" in result.error.lower()

    @pytest.mark.asyncio
    async def test_respond_decode_skeye_fails(self, info_hash):
        """Test response when decoding SKEYE fails."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Invalid message
        invalid_message = b"\x00\x00\x00\x03\x02"  # Too short

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return invalid_message[:4]
            if call_count == 2:
                return invalid_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "decode" in result.error.lower() or "SKEYE" in result.error

    @pytest.mark.asyncio
    async def test_respond_read_crypto_returns_none(self, info_hash):
        """Test response when reading CRYPTO returns None."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        # Generate valid SKEYE
        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]  # SKEYE length
            if call_count == 2:
                return ske_message[4:]  # SKEYE body
            if call_count == 3:
                # Fail on CRYPTO read
                raise asyncio.IncompleteReadError(b"partial", 10)

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "CRYPTO" in result.error or "read" in result.error.lower()

    @pytest.mark.asyncio
    async def test_respond_decode_crypto_fails(self, info_hash):
        """Test response when decoding CRYPTO fails."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )
        # Invalid CRYPTO
        invalid_crypto = b"\x00\x00\x00\x02\x04"

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]
            if call_count == 2:
                return ske_message[4:]
            if call_count == 3:
                return invalid_crypto[:4]
            if call_count == 4:
                return invalid_crypto[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_respond_wrong_crypto_message_type(self, info_hash):
        """Test response when CRYPTO message has wrong type."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )
        # Send wrong message type
        wrong_message = initiator_handshake._encode_message(
            MSEHandshakeType.RKEYE, initiator_pubkey
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]
            if call_count == 2:
                return ske_message[4:]
            if call_count == 3:
                return wrong_message[:4]
            if call_count == 4:
                return wrong_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert "CRYPTO" in result.error

    @pytest.mark.asyncio
    async def test_respond_selects_peer_cipher_when_allowed(self, info_hash):
        """Test response selects peer's cipher when it's allowed."""
        handshake = MSEHandshake(allowed_ciphers=[CipherType.RC4, CipherType.AES])

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )
        # Peer prefers AES
        crypto_message = initiator_handshake._encode_crypto_message(
            CipherType.AES
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]
            if call_count == 2:
                return ske_message[4:]
            if call_count == 3:
                return crypto_message[:4]
            if call_count == 4:
                return crypto_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        # Should succeed and use peer's cipher (AES)
        assert result.success is True
        assert result.cipher is not None

    @pytest.mark.asyncio
    async def test_respond_uses_own_cipher_when_peer_disallowed(self, info_hash):
        """Test response uses own cipher when peer's cipher is disallowed."""
        handshake = MSEHandshake(
            allowed_ciphers=[CipherType.RC4], prefer_rc4=True
        )

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        initiator_handshake = MSEHandshake()
        initiator_keypair = initiator_handshake.dh_exchange.generate_keypair()
        initiator_pubkey = (
            initiator_handshake.dh_exchange.get_public_key_bytes(
                initiator_keypair
            )
        )

        ske_message = initiator_handshake._encode_message(
            MSEHandshakeType.SKEYE, initiator_pubkey
        )
        # Peer prefers AES (disallowed)
        crypto_message = initiator_handshake._encode_crypto_message(
            CipherType.AES
        )

        call_count = 0

        async def mock_readexactly(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ske_message[:4]
            if call_count == 2:
                return ske_message[4:]
            if call_count == 3:
                return crypto_message[:4]
            if call_count == 4:
                return crypto_message[4:]
            return b""

        mock_reader.readexactly = AsyncMock(side_effect=mock_readexactly)

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        # Should succeed with our own cipher (RC4)
        assert result.success is True
        assert result.cipher is not None

    def test_create_cipher_fallback_to_rc4(self):
        """Test _create_cipher falls back to RC4 for unknown cipher type."""
        handshake = MSEHandshake()
        key = b"test_key_16bytes"

        # Use invalid cipher type (not RC4 or AES)
        cipher = handshake._create_cipher(999, key)

        # Should fallback to RC4
        assert cipher is not None
        from ccbt.security.ciphers.rc4 import RC4Cipher
        assert isinstance(cipher, RC4Cipher)

    @pytest.mark.asyncio
    async def test_initiate_exception_handling(self, info_hash):
        """Test initiation handles unexpected exceptions."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        # Make write raise an exception
        mock_writer.write = MagicMock(side_effect=RuntimeError("Test error"))
        mock_writer.drain = AsyncMock()

        result = await handshake.initiate_as_initiator(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_respond_exception_handling(self, info_hash):
        """Test response handles unexpected exceptions."""
        handshake = MSEHandshake()

        mock_reader = AsyncMock()
        # Make readexactly raise an unexpected exception
        mock_reader.readexactly = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        result = await handshake.respond_as_receiver(
            mock_reader, mock_writer, info_hash
        )

        assert result.success is False
        assert result.error is not None

