"""MSE/PE (BEP 3) handshake — peer traffic obfuscation / ecosystem interop.

Message Stream Encryption and Protocol Encryption improve compatibility with
clients that expect encrypted or obfuscated peer streams. They do **not**
authenticate peer identity and are not a substitute for TLS to trackers
(HTTPS) or for optional experimental peer TLS (BEP 10 extension).
"""

from __future__ import annotations

import asyncio
import secrets
import struct
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any, NamedTuple, Optional, cast

from ccbt.security.ciphers.aes import AESCipher
from ccbt.security.ciphers.chacha20 import ChaCha20Cipher
from ccbt.security.ciphers.rc4 import RC4Cipher
from ccbt.security.dh_exchange import DHPeerExchange

if TYPE_CHECKING:
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


class MSEHandshakeReadFailureReason(Enum):
    """Typed reasons for MSE handshake message read failures."""

    NONE = "none"
    TIMEOUT = "timeout"
    INCOMPLETE = "incomplete_read"
    INVALID_LENGTH = "invalid_length"
    INVALID_FRAME = "invalid_frame"
    TRANSPORT_ERROR = "transport_error"


class MSEHandshakeResult(NamedTuple):
    """Result of MSE handshake."""

    success: bool
    cipher: Optional[CipherSuite]
    error: Optional[str] = None
    selected_method: Optional[str] = None
    resolved_info_hash: Optional[bytes] = None
    decrypted_initial_data: Optional[bytes] = None
    inbound_cipher: Optional[CipherSuite] = None
    outbound_cipher: Optional[CipherSuite] = None
    inbound_stream_state: Optional[dict[str, Any]] = None
    outbound_stream_state: Optional[dict[str, Any]] = None


class MSEHandshake:
    """MSE/PE handshake protocol handler.

    Supports both Message Stream Encryption (MSE) and Protocol Encryption (PE):
    - MSE: BitTorrent handshake (plain) → encryption handshake → encrypted messages
    - PE: Encryption handshake first → encrypted BitTorrent handshake → encrypted messages
    """

    _crypto_method_rc4 = 0x01
    _crypto_method_aes = 0x02
    _crypto_method_chacha20 = 0x04

    def __init__(
        self,
        dh_key_size: int = 768,
        prefer_rc4: bool = True,
        allowed_ciphers: Optional[list[CipherType]] = None,
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

    @staticmethod
    def _cipher_type_to_method_name(cipher_type: CipherType) -> str:
        """Map cipher type enum to a method name.

        Returns a fixed label for downstream metadata and logs.
        """
        if cipher_type == CipherType.RC4:
            return "RC4"
        if cipher_type == CipherType.AES:
            return "AES"
        if cipher_type == CipherType.CHACHA20:
            return "CHACHA20"
        return "UNKNOWN"

    @staticmethod
    def _stream_state_for_direction(direction: str, method: str) -> dict[str, Any]:
        """Create an opaque stream-state payload for a direction."""
        return {
            "direction": direction,
            "method": method,
            "initialized": True,
        }

    async def initiate_as_initiator(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
        initial_payload: bytes = b"",
        initial_payload_size: int = 0,
        initial_payload_timeout: float = 0.25,
    ) -> MSEHandshakeResult:
        """Initiate MSE handshake as connection initiator using BEP 3 transcript."""
        if len(info_hash) != 20:
            return MSEHandshakeResult(
                False, None, f"Info hash must be 20 bytes, got {len(info_hash)}"
            )

        try:
            our_keypair = self.dh_exchange.generate_keypair()
            our_public_key_bytes = self.dh_exchange.get_public_key_bytes(our_keypair)

            # Packet 1 (equivalent to legacy SKEYE): YA + PadC
            pad_c = self._select_handshake_padding()
            ske_message = self._build_handshake_message(our_public_key_bytes + pad_c)
            writer.write(ske_message)
            await writer.drain()

            # Packet 2: YB + PadD from peer
            rke_message, rke_failure = await self._read_handshake_message(
                reader, timeout=timeout
            )
            if rke_message is None:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Failed to read RKEYE message ({rke_failure.value})",
                )
            legacy_type = None
            if len(rke_message) > 0:
                try:
                    legacy_type = MSEHandshakeType(rke_message[0])
                except ValueError:
                    legacy_type = None
            if legacy_type in {
                MSEHandshakeType.SKEYE,
                MSEHandshakeType.CRYPTO,
            }:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected RKEYE message, got {legacy_type.name}",
                )
            dh_public_key_length = self._dh_public_key_length()
            peer_public_key_bytes = rke_message
            if legacy_type == MSEHandshakeType.RKEYE:
                peer_public_key_bytes = rke_message[1:]
            if (
                legacy_type == MSEHandshakeType.RKEYE
                and len(peer_public_key_bytes) == dh_public_key_length + 1
                and peer_public_key_bytes.startswith(b"\x00")
            ):
                peer_public_key_bytes = peer_public_key_bytes[1:]
            if len(peer_public_key_bytes) < 4:
                return MSEHandshakeResult(False, None, "Failed to decode RKEYE message")
            if len(peer_public_key_bytes) > dh_public_key_length:
                peer_public_key_bytes = peer_public_key_bytes[:dh_public_key_length]
            elif len(peer_public_key_bytes) > 0:
                peer_public_key_bytes = peer_public_key_bytes.rjust(
                    dh_public_key_length, b"\x00"
                )
            else:
                return MSEHandshakeResult(False, None, "Failed to decode RKEYE message")
            peer_public_key = self.dh_exchange.public_key_from_bytes(
                peer_public_key_bytes, our_keypair.private_key
            )

            # Shared secret and directional keys:
            # outbound key A -> our-to-peer, inbound key B -> peer-to-our.
            shared_secret = self.dh_exchange.compute_shared_secret(
                our_keypair.private_key, peer_public_key
            )
            outbound_key, inbound_key = self.dh_exchange.derive_stream_keys(
                shared_secret, info_hash
            )

            # Packet 3: req1 + req2xorreq3 + RC4(V C||crypto_provide||padc_len||padC||ia_len||IA)
            crypto_provide = self._build_crypto_provide_mask()
            request_payload = self._build_initiator_request_payload(
                shared_secret,
                info_hash,
                outbound_key,
                crypto_provide,
                pad_c,
                initial_payload,
            )
            crypto_request = self._build_handshake_message(request_payload)
            writer.write(crypto_request)
            await writer.drain()

            # Packet 4: RC4(V C||crypto_select||padD_len||PadD)
            crypto_response, crypto_failure = await self._read_handshake_message(
                reader, timeout=timeout
            )
            if crypto_response is None:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Failed to read CRYPTO message ({crypto_failure.value})",
                )
            legacy_crypto_type = None
            if len(crypto_response) > 0:
                try:
                    legacy_crypto_type = MSEHandshakeType(crypto_response[0])
                except ValueError:
                    legacy_crypto_type = None
            if (
                legacy_crypto_type is not None
                and legacy_crypto_type != MSEHandshakeType.CRYPTO
            ):
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected CRYPTO message, got {legacy_crypto_type.name}",
                )
            selected_cipher: Optional[CipherType] = None
            if len(crypto_response) == 2 and crypto_response[0] == int(
                MSEHandshakeType.CRYPTO
            ):
                legacy_crypto = self._decode_crypto_message(crypto_response[1:2])
                if legacy_crypto not in self.allowed_ciphers:
                    return MSEHandshakeResult(
                        False,
                        None,
                        f"Peer selected disallowed cipher: {legacy_crypto}",
                    )
                selected_cipher = legacy_crypto
            if selected_cipher is None:
                selected_cipher = self._decode_crypto_select_message(
                    crypto_response, inbound_key
                )
            if selected_cipher is None:
                return MSEHandshakeResult(
                    False, None, "Invalid crypto select value from peer"
                )

            # Create cipher instances per direction for post-handshake payload.
            inbound_cipher, outbound_cipher = self._create_cipher_pair(
                selected_cipher, inbound_key=inbound_key, outbound_key=outbound_key
            )
            method_name = self._cipher_type_to_method_name(selected_cipher)
            return MSEHandshakeResult(
                success=True,
                cipher=outbound_cipher,
                inbound_cipher=inbound_cipher,
                outbound_cipher=outbound_cipher,
                selected_method=method_name,
                resolved_info_hash=info_hash,
                decrypted_initial_data=await self._read_and_decrypt_initial_payload(
                    reader=reader,
                    cipher=inbound_cipher,
                    payload_size=initial_payload_size,
                    timeout=initial_payload_timeout,
                )
                if initial_payload_size > 0
                else None,
                inbound_stream_state=self._stream_state_for_direction(
                    "inbound", method_name
                ),
                outbound_stream_state=self._stream_state_for_direction(
                    "outbound", method_name
                ),
            )

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
        initial_payload_size: int = 0,
        initial_payload_timeout: float = 0.25,
        info_hash_candidates: Optional[list[bytes]] = None,
    ) -> MSEHandshakeResult:
        """Respond to MSE handshake as connection receiver using BEP 3 transcript."""
        if len(info_hash) != 20:
            return MSEHandshakeResult(
                False, None, f"Info hash must be 20 bytes, got {len(info_hash)}"
            )
        if info_hash_candidates is None:
            info_hash_candidates = [info_hash]

        try:
            # Packet 1: peer sends YA + PadC.
            ske_message, ske_failure = await self._read_handshake_message(
                reader, timeout=timeout
            )
            if ske_message is None:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Failed to read SKEYE message ({ske_failure.value})",
                )
            legacy_type = None
            if len(ske_message) > 0:
                try:
                    legacy_type = MSEHandshakeType(ske_message[0])
                except ValueError:
                    legacy_type = None
            if legacy_type in {
                MSEHandshakeType.RKEYE,
                MSEHandshakeType.CRYPTO,
            }:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected SKEYE message, got {legacy_type.name}",
                )
            dh_public_key_length = self._dh_public_key_length()
            peer_public_key_bytes = ske_message
            if legacy_type == MSEHandshakeType.SKEYE:
                peer_public_key_bytes = ske_message[1:]
            if (
                legacy_type == MSEHandshakeType.SKEYE
                and len(peer_public_key_bytes) == dh_public_key_length + 1
                and peer_public_key_bytes.startswith(b"\x00")
            ):
                peer_public_key_bytes = peer_public_key_bytes[1:]
            if len(peer_public_key_bytes) < 4:
                return MSEHandshakeResult(False, None, "Failed to decode SKEYE message")
            if len(peer_public_key_bytes) > dh_public_key_length:
                peer_public_key_bytes = peer_public_key_bytes[:dh_public_key_length]
            elif len(peer_public_key_bytes) > 0:
                peer_public_key_bytes = peer_public_key_bytes.rjust(
                    dh_public_key_length, b"\x00"
                )
            else:
                return MSEHandshakeResult(False, None, "Failed to decode SKEYE message")

            # Generate DH keypair and send our key with padding.
            our_keypair = self.dh_exchange.generate_keypair()
            our_public_key_bytes = self.dh_exchange.get_public_key_bytes(our_keypair)
            pad_d = self._select_handshake_padding()
            rke_message = self._build_handshake_message(our_public_key_bytes + pad_d)
            writer.write(rke_message)
            await writer.drain()

            peer_public_key = self.dh_exchange.public_key_from_bytes(
                peer_public_key_bytes, our_keypair.private_key
            )
            shared_secret = self.dh_exchange.compute_shared_secret(
                our_keypair.private_key, peer_public_key
            )

            # Packet 3 from peer: req1 + req2xorreq3 + RC4(VC + crypto_provide + lengths)
            crypto_message, crypto_failure = await self._read_handshake_message(
                reader, timeout=timeout
            )
            if crypto_message is None:
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Failed to read CRYPTO message ({crypto_failure.value})",
                )
            legacy_crypto_type = None
            if len(crypto_message) > 0:
                try:
                    legacy_crypto_type = MSEHandshakeType(crypto_message[0])
                except ValueError:
                    legacy_crypto_type = None
            if (
                legacy_crypto_type is not None
                and legacy_crypto_type != MSEHandshakeType.CRYPTO
            ):
                return MSEHandshakeResult(
                    False,
                    None,
                    f"Expected CRYPTO message, got {legacy_crypto_type.name}",
                )

            requested: Optional[tuple[int, bytes]] = None
            chosen_info_hash = info_hash
            outbound_key = inbound_key = None
            for candidate_info_hash in info_hash_candidates:
                if len(candidate_info_hash) != 20:
                    continue
                candidate_outbound_key, candidate_inbound_key = (
                    self.dh_exchange.derive_stream_keys(
                        shared_secret,
                        candidate_info_hash,
                    )
                )
                candidate_requested = self._parse_receiver_crypto_request(
                    crypto_message,
                    shared_secret,
                    candidate_info_hash,
                    candidate_outbound_key,
                )
                if candidate_requested is None:
                    continue
                requested = candidate_requested
                outbound_key = candidate_outbound_key
                inbound_key = candidate_inbound_key
                chosen_info_hash = candidate_info_hash
                break

            if requested is None or outbound_key is None or inbound_key is None:
                return MSEHandshakeResult(False, None, "Invalid crypto request payload")
            crypto_provide, initial_payload = requested
            selected_cipher = self._select_cipher_from_mask(crypto_provide)
            if selected_cipher not in self.allowed_ciphers:
                selected_cipher = self._select_cipher()

            # Packet 4: RC4(V C + crypto_select + padD len + padD)
            crypto_select = self._build_crypto_select(selected_cipher)
            pad_d_reply = self._select_handshake_padding()
            response_payload = self._build_receiver_crypto_response(
                inbound_key,
                crypto_select,
                pad_d_reply,
            )
            writer.write(self._build_handshake_message(response_payload))
            await writer.drain()

            inbound_cipher, outbound_cipher = self._create_cipher_pair(
                selected_cipher, inbound_key=inbound_key, outbound_key=outbound_key
            )

            method_name = self._cipher_type_to_method_name(selected_cipher)
            peer_initial_payload = initial_payload
            if initial_payload_size > 0 and not initial_payload:
                peer_initial_payload = await self._read_and_decrypt_initial_payload(
                    reader=reader,
                    cipher=inbound_cipher,
                    payload_size=initial_payload_size,
                    timeout=initial_payload_timeout,
                )

            return MSEHandshakeResult(
                success=True,
                cipher=outbound_cipher,
                inbound_cipher=inbound_cipher,
                outbound_cipher=outbound_cipher,
                selected_method=method_name,
                resolved_info_hash=bytes(chosen_info_hash),
                decrypted_initial_data=peer_initial_payload,
                inbound_stream_state=self._stream_state_for_direction(
                    "inbound", method_name
                ),
                outbound_stream_state=self._stream_state_for_direction(
                    "outbound", method_name
                ),
            )

        except asyncio.TimeoutError:
            return MSEHandshakeResult(False, None, "Handshake timeout")
        except Exception as e:
            return MSEHandshakeResult(False, None, str(e))

    async def initiate_as_initiator_with_initial_data(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
        initial_payload_size: int = 0,
        initial_payload_timeout: float = 0.25,
    ) -> MSEHandshakeResult:
        """Compatibility shim retained for call sites expecting a dedicated initial-data API."""
        result = await self.initiate_as_initiator(
            reader,
            writer,
            info_hash,
            timeout=timeout,
            initial_payload_size=initial_payload_size,
            initial_payload_timeout=initial_payload_timeout,
        )
        if (
            result.success
            and result.decrypted_initial_data is None
            and initial_payload_size > 0
        ):
            decrypt_cipher = (
                result.inbound_cipher
                if result.inbound_cipher is not None
                else result.cipher
            )
            result = result._replace(
                decrypted_initial_data=await self._read_and_decrypt_initial_payload(
                    reader=reader,
                    cipher=decrypt_cipher,
                    payload_size=initial_payload_size,
                    timeout=initial_payload_timeout,
                )
            )
        return result

    async def respond_as_receiver_with_initial_data(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        info_hash: bytes,
        timeout: float = 10.0,
        initial_payload_size: int = 0,
        initial_payload_timeout: float = 0.25,
        info_hash_candidates: Optional[list[bytes]] = None,
    ) -> MSEHandshakeResult:
        """Compatibility shim retained for call sites expecting a dedicated initial-data API."""
        result = await self.respond_as_receiver(
            reader,
            writer,
            info_hash,
            timeout=timeout,
            initial_payload_size=initial_payload_size,
            initial_payload_timeout=initial_payload_timeout,
            info_hash_candidates=info_hash_candidates,
        )
        if (
            result.success
            and result.decrypted_initial_data is None
            and initial_payload_size > 0
        ):
            decrypt_cipher = (
                result.inbound_cipher
                if result.inbound_cipher is not None
                else result.cipher
            )
            result = result._replace(
                decrypted_initial_data=await self._read_and_decrypt_initial_payload(
                    reader=reader,
                    cipher=decrypt_cipher,
                    payload_size=initial_payload_size,
                    timeout=initial_payload_timeout,
                )
            )
        return result

    async def _read_and_decrypt_initial_payload(
        self,
        reader: asyncio.StreamReader,
        cipher: Optional[CipherSuite],
        payload_size: int,
        timeout: float,
    ) -> Optional[bytes]:
        """Read and decrypt a fixed-size payload immediately after handshake."""
        if cipher is None:
            return None
        if payload_size <= 0:
            return None

        try:
            encrypted_payload = await asyncio.wait_for(
                reader.readexactly(payload_size), timeout=timeout
            )
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            return None
        except Exception:
            return None

        try:
            return cipher.decrypt(encrypted_payload)
        except Exception:
            return encrypted_payload

    @staticmethod
    def _dh_public_key_length_for_size(size: int) -> int:
        return (size + 7) // 8

    def _dh_public_key_length(self) -> int:
        return self._dh_public_key_length_for_size(self.dh_exchange.key_size)

    @staticmethod
    def _select_handshake_padding() -> bytes:
        """Select handshake padding for PadC/PadD.

        Bounded to 0..512 bytes to match BEP 3 limits.
        """
        pad_len = secrets.randbelow(513)
        return secrets.token_bytes(pad_len)

    @staticmethod
    def _build_handshake_message(payload: bytes) -> bytes:
        """Build a plain BEP 3 length-prefixed payload."""
        return struct.pack("!I", len(payload)) + payload

    async def _read_handshake_message(
        self, reader: asyncio.StreamReader, timeout: float
    ) -> tuple[Optional[bytes], MSEHandshakeReadFailureReason]:
        """Read a length-prefixed handshake payload and classify read outcomes."""
        try:
            length_bytes = await asyncio.wait_for(
                reader.readexactly(4), timeout=timeout
            )
            frame_length = struct.unpack("!I", length_bytes)[0]
            if frame_length <= 0:
                return None, MSEHandshakeReadFailureReason.INVALID_LENGTH
            if frame_length > 65535:
                return None, MSEHandshakeReadFailureReason.INVALID_LENGTH
            payload = await asyncio.wait_for(
                reader.readexactly(frame_length), timeout=timeout
            )
            return payload, MSEHandshakeReadFailureReason.NONE
        except asyncio.TimeoutError:
            return None, MSEHandshakeReadFailureReason.TIMEOUT
        except (asyncio.IncompleteReadError, ConnectionError):
            return None, MSEHandshakeReadFailureReason.INCOMPLETE
        except Exception:
            return None, MSEHandshakeReadFailureReason.TRANSPORT_ERROR

    def _select_cipher_from_mask(self, mask: int) -> CipherType:
        """Select an allowed cipher from the peer's `crypto_provide` or `crypto_select`."""
        if (
            mask & self._crypto_method_rc4
            and CipherType.RC4 in self.allowed_ciphers
            and self.prefer_rc4
        ):
            return CipherType.RC4
        if (
            mask & self._crypto_method_aes
            and CipherType.AES in self.allowed_ciphers
            and not self.prefer_rc4
        ):
            return CipherType.AES
        if (
            mask & self._crypto_method_chacha20
            and CipherType.CHACHA20 in self.allowed_ciphers
        ) and not self.prefer_rc4:
            return CipherType.CHACHA20

        # Fallback preference order from _select_cipher().
        if self.prefer_rc4 and CipherType.RC4 in self.allowed_ciphers:
            return CipherType.RC4
        if self._crypto_method_aes & mask and CipherType.AES in self.allowed_ciphers:
            return CipherType.AES
        if (
            self._crypto_method_chacha20 & mask
            and CipherType.CHACHA20 in self.allowed_ciphers
        ):
            return CipherType.CHACHA20
        return self._select_cipher()

    @staticmethod
    def _build_crypto_select(cipher_type: CipherType) -> bytes:
        if cipher_type == CipherType.AES:
            return struct.pack("!I", 0x02)
        if cipher_type == CipherType.CHACHA20:
            return struct.pack("!I", 0x04)
        return struct.pack("!I", 0x01)

    def _decode_crypto_select_message(
        self, payload: bytes, inbound_key: bytes
    ) -> Optional[CipherType]:
        if len(payload) < 12:
            return None
        rc4 = self._create_cipher(CipherType.RC4, inbound_key)
        if hasattr(rc4, "discard_keystream"):
            cast("Any", rc4).discard_keystream(1024)
        plain = rc4.decrypt(payload)
        if plain[:8] != self.dh_exchange.verification_constant():
            return None
        method_mask = struct.unpack("!I", plain[8:12])[0]
        return self._select_cipher_from_mask(method_mask)

    def _build_receiver_crypto_response(
        self, inbound_key: bytes, crypto_select: bytes, pad_d: bytes
    ) -> bytes:
        rc4 = self._create_cipher(CipherType.RC4, inbound_key)
        if hasattr(rc4, "discard_keystream"):
            cast("Any", rc4).discard_keystream(1024)
        return rc4.encrypt(
            self.dh_exchange.verification_constant()
            + crypto_select
            + struct.pack("!H", len(pad_d))
            + pad_d
        )

    def _build_initiator_request_payload(
        self,
        shared_secret: bytes,
        info_hash: bytes,
        outbound_key: bytes,
        crypto_provide: int,
        pad_c: bytes,
        initial_payload: bytes = b"",
    ) -> bytes:
        req1 = self.dh_exchange.req1_hash(shared_secret)
        req2_xor_req3 = bytes(
            a ^ b
            for a, b in zip(
                self.dh_exchange.req2_hash(info_hash),
                self.dh_exchange.req3_hash(shared_secret),
            )
        )
        rc4 = self._create_cipher(CipherType.RC4, outbound_key)
        if hasattr(rc4, "discard_keystream"):
            cast("Any", rc4).discard_keystream(1024)
        encrypted = rc4.encrypt(
            self.dh_exchange.verification_constant()
            + struct.pack("!I", crypto_provide)
            + struct.pack("!H", len(pad_c))
            + pad_c
            + struct.pack("!H", len(initial_payload))
            + initial_payload
        )
        return req1 + req2_xor_req3 + encrypted

    def _parse_receiver_crypto_request(
        self,
        payload: bytes,
        shared_secret: bytes,
        info_hash: bytes,
        outbound_key: bytes,
    ) -> Optional[tuple[int, bytes]]:
        if len(payload) == 2 and payload[0] == int(MSEHandshakeType.CRYPTO):
            try:
                requested_cipher = self._decode_crypto_message(payload[1:])
            except Exception:
                return None
            if requested_cipher == CipherType.RC4:
                method_mask = self._crypto_method_rc4
            elif requested_cipher == CipherType.AES:
                method_mask = self._crypto_method_aes
            elif requested_cipher == CipherType.CHACHA20:
                method_mask = self._crypto_method_chacha20
            else:
                return None
            return (method_mask, b"")
        if len(payload) < 56:
            return None
        req1 = payload[:20]
        req1_xor = payload[20:40]
        rc4_payload = payload[40:]
        expected_req1 = self.dh_exchange.req1_hash(shared_secret)
        expected_req2_xor_req3 = bytes(
            a ^ b
            for a, b in zip(
                self.dh_exchange.req2_hash(info_hash),
                self.dh_exchange.req3_hash(shared_secret),
            )
        )
        if req1 != expected_req1:
            return None
        if req1_xor != expected_req2_xor_req3:
            return None
        rc4 = self._create_cipher(CipherType.RC4, outbound_key)
        if hasattr(rc4, "discard_keystream"):
            cast("Any", rc4).discard_keystream(1024)
        decrypted = rc4.decrypt(rc4_payload)
        if len(decrypted) < 12:
            return None
        if decrypted[:8] != self.dh_exchange.verification_constant():
            return None
        crypto_provide = struct.unpack("!I", decrypted[8:12])[0]
        pad_c_len_offset = 12
        if len(decrypted) < pad_c_len_offset + 2:
            return None
        pad_c_len = struct.unpack(
            "!H", decrypted[pad_c_len_offset : pad_c_len_offset + 2]
        )[0]
        cursor = pad_c_len_offset + 2
        if len(decrypted) < cursor + pad_c_len + 2:
            return None
        # Skip peer pad for now; only validate structure.
        cursor += pad_c_len
        ia_len = struct.unpack("!H", decrypted[cursor : cursor + 2])[0]
        if len(decrypted) < cursor + 2 + ia_len:
            return None
        ia = decrypted[cursor + 2 : cursor + 2 + ia_len]
        return crypto_provide, ia

    def _build_transcript_message(
        self, msg_type: MSEHandshakeType, payload: bytes
    ) -> bytes:
        """Build a de-facto MSE/PE transcript frame."""
        frame_length = len(payload) + 1  # +1 for message type byte
        return struct.pack("!IB", frame_length, int(msg_type)) + payload

    def _parse_transcript_message(
        self, data: bytes
    ) -> Optional[tuple[MSEHandshakeType, bytes]]:
        """Parse a de-facto MSE/PE transcript frame."""
        if len(data) < 5:
            return None
        frame_length = struct.unpack("!I", data[:4])[0]
        if len(data) < frame_length + 4:
            return None
        if frame_length < 1:
            return None
        try:
            msg_type = MSEHandshakeType(data[4])
        except ValueError:
            return None
        payload = data[5 : 5 + frame_length - 1]
        return (msg_type, payload)

    def _build_crypto_provide_mask(self) -> int:
        """Build `crypto_provide` bitmap from allowed ciphers."""
        mask = 0
        if CipherType.RC4 in self.allowed_ciphers:
            mask |= self._crypto_method_rc4
        if CipherType.AES in self.allowed_ciphers:
            mask |= self._crypto_method_aes
        if CipherType.CHACHA20 in self.allowed_ciphers:
            mask |= self._crypto_method_chacha20
        return mask or self._crypto_method_rc4

    def _decode_crypto_provide_mask(self, data: bytes) -> int:
        """Decode `crypto_provide` bits from a peer message."""
        if len(data) >= 4:
            return struct.unpack("!I", data[:4])[0]
        if len(data) >= 1:
            return struct.unpack("!B", data[:1])[0]
        return 0

    async def _read_transcript_message(
        self, reader: asyncio.StreamReader
    ) -> Optional[bytes]:
        """Read a complete transcript frame."""
        return await self._read_transcript_payload(reader)

    async def _read_transcript_payload(
        self, reader: asyncio.StreamReader
    ) -> Optional[bytes]:
        """Read complete frame payload from the stream."""
        try:
            length_bytes = await reader.readexactly(4)
            frame_length = struct.unpack("!I", length_bytes)[0]
            frame = await reader.readexactly(frame_length)
            return length_bytes + frame
        except (asyncio.IncompleteReadError, ConnectionError):
            return None

    def _encode_transcript_message(
        self, msg_type: MSEHandshakeType, payload: bytes
    ) -> bytes:
        """Encode transcript-native MSE handshake message."""
        return self._build_transcript_message(msg_type, payload)

    def _encode_crypto_message(self, cipher_type: CipherType) -> bytes:
        """Encode CRYPTO message with cipher selection.

        Args:
            cipher_type: Selected cipher type

        Returns:
            Encoded CRYPTO message

        """
        payload = self._build_crypto_message_payload(cipher_type)
        return self._encode_transcript_message(MSEHandshakeType.CRYPTO, payload)

    def _build_crypto_message_payload(self, cipher_type: CipherType) -> bytes:
        """Build a minimal CRYPTO payload from selected cipher/capability."""
        if cipher_type == CipherType.RC4:
            return struct.pack("!B", self._crypto_method_rc4)
        if cipher_type == CipherType.AES:
            return struct.pack("!B", self._crypto_method_aes)
        if cipher_type == CipherType.CHACHA20:
            return struct.pack("!B", self._crypto_method_chacha20)
        return struct.pack("!B", int(cipher_type))

    def _decode_crypto_message(self, data: bytes) -> CipherType:
        """Decode CRYPTO message to get cipher type.

        Args:
            data: CRYPTO message payload

        Returns:
            Cipher type

        """
        if not data:
            return CipherType.RC4
        if len(data) == 1:
            cipher_value = struct.unpack("!B", data[:1])[0]
            if cipher_value == self._crypto_method_rc4:
                return CipherType.RC4
            if cipher_value == self._crypto_method_aes:
                return CipherType.AES
            if cipher_value == self._crypto_method_chacha20:
                return CipherType.CHACHA20
            return self._select_cipher()
        if len(data) >= 4:
            mask = self._decode_crypto_provide_mask(data)
            if mask & self._crypto_method_chacha20:
                return CipherType.CHACHA20
            if mask & self._crypto_method_aes:
                return CipherType.AES
            return CipherType.RC4
        return self._select_cipher()

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

    @staticmethod
    def _derive_stream_vector(source: bytes, size: int) -> bytes:
        """Derive a fixed-size stream vector (IV/nonce) deterministically."""
        if not source:
            return b"\x00" * size
        repeats = (size + len(source) - 1) // len(source)
        return (source * repeats)[:size]

    def _create_cipher_pair(
        self,
        cipher_type: CipherType,
        key: Optional[bytes] = None,
        inbound_key: Optional[bytes] = None,
        outbound_key: Optional[bytes] = None,
    ) -> tuple[CipherSuite, CipherSuite]:
        """Create independent inbound and outbound cipher instances."""
        if inbound_key is None and outbound_key is None:
            inbound_key = outbound_key = key
        elif key is not None:
            if inbound_key is None:
                inbound_key = key
            if outbound_key is None:
                outbound_key = key
        if inbound_key is None or outbound_key is None:
            msg = "inbound_key and outbound_key must be provided"
            raise ValueError(msg)
        inbound = self._create_cipher(cipher_type, inbound_key)
        outbound = self._create_cipher(cipher_type, outbound_key)
        if isinstance(inbound, RC4Cipher) and hasattr(inbound, "discard_keystream"):
            inbound.discard_keystream(1024)
        if isinstance(outbound, RC4Cipher) and hasattr(outbound, "discard_keystream"):
            outbound.discard_keystream(1024)
        return (inbound, outbound)

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
            nonce = self._derive_stream_vector(cipher_key, 16)
            return ChaCha20Cipher(cipher_key, nonce=nonce)

        # Use first 16 bytes of derived key for RC4/AES (SHA-1 produces 20 bytes)
        cipher_key = key[:16]

        if cipher_type == CipherType.RC4:
            return RC4Cipher(cipher_key)
        if cipher_type == CipherType.AES:
            # For AES, we might need to handle IV separately
            # For now, derive IV deterministically from key material.
            iv = self._derive_stream_vector(cipher_key, 16)
            return AESCipher(cipher_key, iv=iv)

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
            If is_pe is True, first_bytes should be put back (but StreamReader does not
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

            # Post-transcript lead lengths are raw DH payloads:
            # 96 (768-bit group), 128 (1024-bit group) plus optional pad.
            if 96 <= length <= 700:
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
        """Respond to PE (Protocol Encryption) handshake as receiver."""
        # PE mode is same as current respond_as_receiver behavior
        # (encryption handshake before BitTorrent protocol)
        return await self.respond_as_receiver(reader, writer, info_hash, timeout)
