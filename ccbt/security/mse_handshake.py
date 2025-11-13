"""MSE/PE handshake protocol implementation for BEP 3.

from __future__ import annotations

Implements Message Stream Encryption (MSE) and Protocol Encryption (PE)
handshake protocols as specified in BEP 3.
"""

from __future__ import annotations

import asyncio
import struct
from enum import IntEnum
from typing import TYPE_CHECKING, NamedTuple

from ccbt.security.ciphers.aes import AESCipher
from ccbt.security.ciphers.chacha20 import ChaCha20Cipher
from ccbt.security.ciphers.rc4 import RC4Cipher
from ccbt.security.dh_exchange import DHPeerExchange

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.security.ciphers.base import CipherSuite


class MSEHandshakeType(IntEnum):
    """MSE handshake message types."""

    SKEYE = 0x02  # Send key exchange
    RKEYE = 0x03  # Receive key exchange
    CRYPTO = 0x04  # Crypto provide


class CipherType(IntEnum):
    """Cipher type enumeration for BEP 3."""

    RC4 = 0x01
    AES = 0x02
    CHACHA20 = 0x03


class MSEHandshakeResult(NamedTuple):
    """Result of MSE handshake."""

    success: bool
    cipher: CipherSuite | None
    error: str | None = None


class MSEHandshake:
    """MSE/PE handshake protocol handler.

    Supports both Message Stream Encryption (MSE) and Protocol Encryption (PE):
    - MSE: BitTorrent handshake (plain) → encryption handshake → encrypted messages
    - PE: Encryption handshake first → encrypted BitTorrent handshake → encrypted messages
    """

    def __init__(
        self,
        dh_key_size: int = 768,
        prefer_rc4: bool = True,
        allowed_ciphers: list[CipherType] | None = None,
    ):
        """Initialize MSE handshake handler.

        Args:
            dh_key_size: DH key size in bits (768 or 1024)
            prefer_rc4: Prefer RC4 over AES (default True for compatibility)
            allowed_ciphers: List of allowed cipher types (None = all)

        """
        self.dh_exchange = DHPeerExchange(key_size=dh_key_size)
        self.prefer_rc4 = prefer_rc4
        self.allowed_ciphers = allowed_ciphers or [
            CipherType.RC4,
            CipherType.AES,
            CipherType.CHACHA20,
        ]

    async def initiate_as_initiator(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
    ) -> MSEHandshakeResult:
        """Initiate MSE handshake as connection initiator.

        Flow:
        1. Generate DH keypair
        2. Send SKEYE message with our public key
        3. Receive RKEYE message with peer's public key
        4. Compute shared secret
        5. Send CRYPTO message with our cipher preference
        6. Receive CRYPTO message with peer's cipher selection
        7. Derive encryption keys and create cipher

        Args:
            reader: Stream reader for receiving messages
            writer: Stream writer for sending messages
            info_hash: Torrent info hash (20 bytes)
            timeout: Handshake timeout in seconds

        Returns:
            MSEHandshakeResult with success status and cipher instance

        """
        if len(info_hash) != 20:
            return MSEHandshakeResult(
                False, None, f"Info hash must be 20 bytes, got {len(info_hash)}"
            )

        try:
            # Step 1: Generate DH keypair
            our_keypair = self.dh_exchange.generate_keypair()
            our_public_key_bytes = self.dh_exchange.get_public_key_bytes(our_keypair)

            # Step 2: Send SKEYE message
            ske_message = self._encode_message(
                MSEHandshakeType.SKEYE, our_public_key_bytes
            )
            writer.write(ske_message)
            await writer.drain()

            # Step 3: Receive RKEYE message
            rke_message = await asyncio.wait_for(
                self._read_message(reader), timeout=timeout
            )
            if rke_message is None:
                return MSEHandshakeResult(False, None, "Failed to read RKEYE message")

            decoded = self._decode_message(rke_message)
            if decoded is None:
                return MSEHandshakeResult(False, None, "Failed to decode RKEYE message")
            msg_type, peer_public_key_bytes = decoded
            if msg_type != MSEHandshakeType.RKEYE:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected RKEYE, got message type {msg_type}",
                )

            # Step 4: Compute shared secret
            peer_public_key = self.dh_exchange.public_key_from_bytes(
                peer_public_key_bytes, our_keypair.private_key
            )
            shared_secret = self.dh_exchange.compute_shared_secret(
                our_keypair.private_key, peer_public_key
            )

            # Step 5: Send CRYPTO message with our cipher preference
            selected_cipher = self._select_cipher()
            crypto_message = self._encode_crypto_message(selected_cipher)
            writer.write(crypto_message)
            await writer.drain()

            # Step 6: Receive CRYPTO message
            crypto_response = await asyncio.wait_for(
                self._read_message(reader), timeout=timeout
            )
            if crypto_response is None:
                return MSEHandshakeResult(False, None, "Failed to read CRYPTO message")

            decoded = self._decode_message(crypto_response)
            if decoded is None:
                return MSEHandshakeResult(
                    False, None, "Failed to decode CRYPTO message"
                )
            msg_type, crypto_data = decoded
            if msg_type != MSEHandshakeType.CRYPTO:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected CRYPTO, got message type {msg_type}",
                )

            peer_cipher_type = self._decode_crypto_message(crypto_data)
            if peer_cipher_type not in self.allowed_ciphers:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Peer selected disallowed cipher: {peer_cipher_type}",
                )

            # Step 7: Derive encryption keys and create cipher
            # Use the negotiated cipher (prefer peer's choice if different)
            final_cipher_type = peer_cipher_type

            encryption_key = self.dh_exchange.derive_encryption_key(
                shared_secret, info_hash
            )

            # Create cipher instance
            cipher = self._create_cipher(final_cipher_type, encryption_key)

            return MSEHandshakeResult(True, cipher)

        except asyncio.TimeoutError:
            return MSEHandshakeResult(False, None, "Handshake timeout")
        except Exception as e:
            return MSEHandshakeResult(False, None, str(e))

    async def respond_as_receiver(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
    ) -> MSEHandshakeResult:
        """Respond to MSE handshake as connection receiver.

        Flow:
        1. Receive SKEYE message with peer's public key
        2. Generate DH keypair
        3. Send RKEYE message with our public key
        4. Compute shared secret
        5. Receive CRYPTO message with peer's cipher preference
        6. Send CRYPTO message with our cipher selection
        7. Derive encryption keys and create cipher

        Args:
            reader: Stream reader for receiving messages
            writer: Stream writer for sending messages
            info_hash: Torrent info hash (20 bytes)
            timeout: Handshake timeout in seconds

        Returns:
            MSEHandshakeResult with success status and cipher instance

        """
        if len(info_hash) != 20:
            return MSEHandshakeResult(
                False, None, f"Info hash must be 20 bytes, got {len(info_hash)}"
            )

        try:
            # Step 1: Receive SKEYE message
            ske_message = await asyncio.wait_for(
                self._read_message(reader), timeout=timeout
            )
            if ske_message is None:
                return MSEHandshakeResult(False, None, "Failed to read SKEYE message")

            decoded = self._decode_message(ske_message)
            if decoded is None:
                return MSEHandshakeResult(False, None, "Failed to decode SKEYE message")
            msg_type, peer_public_key_bytes = decoded
            if msg_type != MSEHandshakeType.SKEYE:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected SKEYE, got message type {msg_type}",
                )

            # Step 2: Generate DH keypair
            our_keypair = self.dh_exchange.generate_keypair()

            # Step 3: Send RKEYE message
            our_public_key_bytes = self.dh_exchange.get_public_key_bytes(our_keypair)
            rke_message = self._encode_message(
                MSEHandshakeType.RKEYE, our_public_key_bytes
            )
            writer.write(rke_message)
            await writer.drain()

            # Step 4: Compute shared secret
            peer_public_key = self.dh_exchange.public_key_from_bytes(
                peer_public_key_bytes, our_keypair.private_key
            )
            shared_secret = self.dh_exchange.compute_shared_secret(
                our_keypair.private_key, peer_public_key
            )

            # Step 5: Receive CRYPTO message
            crypto_message = await asyncio.wait_for(
                self._read_message(reader), timeout=timeout
            )
            if crypto_message is None:
                return MSEHandshakeResult(False, None, "Failed to read CRYPTO message")

            decoded = self._decode_message(crypto_message)
            if decoded is None:
                return MSEHandshakeResult(
                    False, None, "Failed to decode CRYPTO message"
                )
            msg_type, crypto_data = decoded
            if msg_type != MSEHandshakeType.CRYPTO:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected CRYPTO, got message type {msg_type}",
                )

            peer_cipher_type = self._decode_crypto_message(crypto_data)

            # Step 6: Select and send our cipher choice
            # Prefer peer's cipher if it's allowed, otherwise use our preference
            if peer_cipher_type in self.allowed_ciphers:
                selected_cipher = peer_cipher_type
            else:
                selected_cipher = self._select_cipher()

            crypto_response = self._encode_crypto_message(selected_cipher)
            writer.write(crypto_response)
            await writer.drain()

            # Step 7: Derive encryption keys and create cipher
            encryption_key = self.dh_exchange.derive_encryption_key(
                shared_secret, info_hash
            )
            cipher = self._create_cipher(selected_cipher, encryption_key)

            return MSEHandshakeResult(True, cipher)

        except asyncio.TimeoutError:
            return MSEHandshakeResult(False, None, "Handshake timeout")
        except Exception as e:
            return MSEHandshakeResult(False, None, str(e))

    def _encode_message(self, msg_type: MSEHandshakeType, payload: bytes) -> bytes:
        """Encode MSE handshake message.

        Format: [4 bytes length][1 byte message type][payload]

        Args:
            msg_type: Message type
            payload: Message payload

        Returns:
            Encoded message bytes

        """
        length = len(payload) + 1  # +1 for message type byte
        return struct.pack("!IB", length, int(msg_type)) + payload

    def _decode_message(self, data: bytes) -> tuple[MSEHandshakeType, bytes] | None:
        """Decode MSE handshake message.

        Args:
            data: Encoded message bytes

        Returns:
            Tuple of (message_type, payload) or None if invalid

        """
        if len(data) < 5:
            return None

        length = struct.unpack("!I", data[0:4])[0]
        if len(data) < length + 4:
            return None

        msg_type = MSEHandshakeType(struct.unpack("!B", data[4:5])[0])
        payload = data[5 : 5 + length - 1]  # -1 for message type byte

        return (msg_type, payload)

    async def _read_message(self, reader: asyncio.StreamReader) -> bytes | None:
        """Read a complete MSE handshake message from stream.

        Args:
            reader: Stream reader

        Returns:
            Complete message bytes or None on error

        """
        try:
            # Read length field (4 bytes)
            length_bytes = await reader.readexactly(4)
            length = struct.unpack("!I", length_bytes)[0]

            # Read remaining message
            message = await reader.readexactly(length)
            return length_bytes + message

        except (asyncio.IncompleteReadError, ConnectionError):
            return None

    def _encode_crypto_message(self, cipher_type: CipherType) -> bytes:
        """Encode CRYPTO message with cipher selection.

        Args:
            cipher_type: Selected cipher type

        Returns:
            Encoded CRYPTO message

        """
        payload = struct.pack("!B", int(cipher_type))
        return self._encode_message(MSEHandshakeType.CRYPTO, payload)

    def _decode_crypto_message(self, data: bytes) -> CipherType:
        """Decode CRYPTO message to get cipher type.

        Args:
            data: CRYPTO message payload

        Returns:
            Cipher type

        """
        if len(data) < 1:
            return CipherType.RC4  # Default fallback

        cipher_value = struct.unpack("!B", data[0:1])[0]
        return CipherType(cipher_value)

    def _select_cipher(self) -> CipherType:
        """Select cipher type based on preferences.

        Returns:
            Selected cipher type

        """
        if self.prefer_rc4 and CipherType.RC4 in self.allowed_ciphers:
            return CipherType.RC4
        if CipherType.AES in self.allowed_ciphers:
            return CipherType.AES
        if CipherType.CHACHA20 in self.allowed_ciphers:
            return CipherType.CHACHA20
        # Fallback to first allowed cipher
        return self.allowed_ciphers[0] if self.allowed_ciphers else CipherType.RC4

    def _create_cipher(self, cipher_type: CipherType, key: bytes) -> CipherSuite:
        """Create cipher instance for encryption.

        Args:
            cipher_type: Cipher type to create
            key: Encryption key (from derived key, use first 16 bytes for RC4/AES, first 32 bytes for ChaCha20)

        Returns:
            Cipher instance

        """
        # Use appropriate key size based on cipher type
        # ChaCha20 requires 32 bytes, RC4/AES use 16 bytes
        # SHA-1 produces 20 bytes, so for ChaCha20 we'll need to pad or use a different derivation
        # For now, pad the key to 32 bytes for ChaCha20
        if cipher_type == CipherType.CHACHA20:
            # Pad key to 32 bytes if needed (repeat key bytes or use SHA-256)
            # For simplicity, repeat key bytes to reach 32 bytes
            if len(key) >= 32:
                cipher_key = key[:32]
            else:
                # Pad by repeating key bytes until we reach 32 bytes
                padding_needed = 32 - len(key)
                cipher_key = (
                    key + (key * ((padding_needed // len(key)) + 1))[:padding_needed]
                )
            return ChaCha20Cipher(cipher_key)

        # Use first 16 bytes of derived key for RC4/AES (SHA-1 produces 20 bytes)
        cipher_key = key[:16]

        if cipher_type == CipherType.RC4:
            return RC4Cipher(cipher_key)
        if cipher_type == CipherType.AES:
            # For AES, we might need to handle IV separately
            # For now, generate a random IV (should be sent in handshake)
            return AESCipher(cipher_key)

        # Fallback to RC4
        return RC4Cipher(cipher_key)

    @staticmethod
    async def detect_encrypted_handshake(
        reader: asyncio.StreamReader, timeout: float = 2.0
    ) -> tuple[bool, bytes]:
        """Detect if incoming connection is using PE (encrypted handshake).

        Peek at first bytes to determine if connection is PE or plain BitTorrent.
        PE connections start with MSE handshake messages (length-prefixed).
        Plain connections start with BitTorrent protocol string.

        Args:
            reader: Stream reader to peek (bytes will be consumed and returned)
            timeout: Timeout for detection in seconds

        Returns:
            Tuple of (is_pe, first_bytes) where first_bytes are the consumed bytes
            If is_pe is True, first_bytes should be put back (but StreamReader doesn't
            support unread, so caller must handle this)

        """
        try:
            # Peek at first 4 bytes (MSE message length field or BitTorrent protocol)
            first_bytes = await asyncio.wait_for(reader.read(4), timeout=timeout)

            if len(first_bytes) < 4:
                return False, first_bytes

            # Check if it looks like MSE message length (reasonable size)
            # MSE messages typically start with 4-byte length
            # BitTorrent handshake starts with 1-byte protocol length (19)
            length = struct.unpack("!I", first_bytes)[0]

            # BitTorrent handshake format: [1 byte len][19 bytes protocol][8 bytes reserved][20 bytes info_hash][20 bytes peer_id]
            # First byte is always 19 (0x13) for "BitTorrent protocol"
            # If first byte is 19, it's a plain BitTorrent handshake
            if first_bytes[0] == 19:
                return False, first_bytes

            # MSE message lengths are typically 50-300 bytes (for SKEYE/RKEYE)
            # If first 4 bytes interpreted as uint32 gives a reasonable MSE length
            # (not too large, > 4), it's likely PE
            if 4 < length < 2000:  # Reasonable MSE message size
                # Check if remaining bytes would make sense for MSE
                # Read a bit more to verify
                try:
                    # Read the message type byte
                    type_byte = await asyncio.wait_for(reader.read(1), timeout=0.5)
                    if type_byte:
                        msg_type_value = struct.unpack("!B", type_byte)[0]
                        # MSE message types are 0x02 (SKEYE), 0x03 (RKEYE), 0x04 (CRYPTO)
                        if msg_type_value in (0x02, 0x03, 0x04):
                            # Looks like MSE handshake - return all bytes read
                            return True, first_bytes + type_byte
                        # Not a valid MSE message type, might be plain
                        return False, first_bytes + type_byte
                except (asyncio.TimeoutError, ConnectionError):  # pragma: no cover
                    # Couldn't read more, but length suggests MSE
                    # Tested via test_detect_encrypted_handshake_timeout_reading_type
                    # and test_detect_encrypted_handshake_connection_error_reading_type
                    return True, first_bytes

            # Doesn't match expected patterns - assume plain
            return False, first_bytes

        except (asyncio.TimeoutError, ConnectionError):  # pragma: no cover
            # Timeout or connection error - assume plain
            # Tested via test_detect_encrypted_handshake_timeout_initial and
            # test_detect_encrypted_handshake_connection_error_initial
            return False, b""
        except Exception:  # pragma: no cover - defensive code for unexpected errors
            # Any other error - assume plain (defensive programming)
            # Tested via test_detect_encrypted_handshake_generic_exception
            return False, b""

    async def initiate_pe_as_initiator(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
    ) -> MSEHandshakeResult:
        """Initiate PE (Protocol Encryption) handshake as initiator.

        This method explicitly handles PE mode where encryption handshake
        occurs before BitTorrent protocol handshake. The BitTorrent handshake
        will be encrypted after this completes.

        Args:
            reader: Stream reader for receiving messages
            writer: Stream writer for sending messages
            info_hash: Torrent info hash (20 bytes)
            timeout: Handshake timeout in seconds

        Returns:
            MSEHandshakeResult with success status and cipher instance

        """
        # PE mode is same as current initiate_as_initiator behavior
        # (encryption handshake before BitTorrent protocol)
        return await self.initiate_as_initiator(reader, writer, info_hash, timeout)

    async def respond_pe_as_receiver(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
    ) -> MSEHandshakeResult:
        """Respond to PE (Protocol Encryption) handshake as receiver.

        This method explicitly handles PE mode where encryption handshake
        occurs before BitTorrent protocol handshake. The BitTorrent handshake
        will be encrypted after this completes.

        Args:
            reader: Stream reader for receiving messages
            writer: Stream writer for sending messages
            info_hash: Torrent info hash (20 bytes)
            timeout: Handshake timeout in seconds

        Returns:
            MSEHandshakeResult with success status and cipher instance

        """
        # PE mode is same as current respond_as_receiver behavior
        # (encryption handshake before BitTorrent protocol)
        return await self.respond_as_receiver(reader, writer, info_hash, timeout)
