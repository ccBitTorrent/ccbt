"""Xet Protocol Extension (BEP 10) implementation.

Provides support for:
- Xet chunk requests via protocol extension
- Cross-torrent chunk deduplication
- P2P Content Addressable Storage
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable

from ccbt.utils.events import Event, EventType, emit_event

logger = logging.getLogger(__name__)


class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
    # Folder sync messages
    FOLDER_VERSION_REQUEST = 0x10  # Request folder version (git ref)
    FOLDER_VERSION_RESPONSE = 0x11  # Response with folder version
    FOLDER_UPDATE_NOTIFY = 0x12  # Notify peer of folder update
    FOLDER_SYNC_MODE_REQUEST = 0x13  # Request sync mode
    FOLDER_SYNC_MODE_RESPONSE = 0x14  # Response with sync mode
    # Metadata exchange messages
    FOLDER_METADATA_REQUEST = 0x20  # Request folder metadata (.tonic file)
    FOLDER_METADATA_RESPONSE = 0x21  # Response with folder metadata piece
    FOLDER_METADATA_NOT_FOUND = 0x22  # Metadata not available
    # Bloom filter messages
    BLOOM_FILTER_REQUEST = 0x30  # Request peer's bloom filter
    BLOOM_FILTER_RESPONSE = 0x31  # Response with bloom filter data


@dataclass
class XetChunkRequest:
    """Xet chunk request information."""

    chunk_hash: bytes
    request_id: int
    timestamp: float


class XetExtension:
    """Xet Protocol Extension implementation."""

    def __init__(
        self,
        folder_sync_handshake: Any | None = None,  # XetHandshakeExtension
    ):
        """Initialize Xet Extension.

        Args:
            folder_sync_handshake: Optional XetHandshakeExtension for folder sync
        """
        self.pending_requests: dict[
            tuple[str, int], XetChunkRequest
        ] = {}  # (peer_id, request_id) -> request
        self.request_counter = 0
        self.chunk_provider: Callable[[bytes], bytes | None] | None = None
        self.folder_sync_handshake = folder_sync_handshake

    def set_chunk_provider(self, provider: Callable[[bytes], bytes | None]) -> None:
        """Set function to provide chunks by hash.

        Args:
            provider: Callable that takes chunk_hash (32 bytes) and returns
                     chunk data bytes or None if not available

        """
        self.chunk_provider = provider

    def encode_handshake(self) -> dict[str, Any]:
        """Encode Xet extension handshake data.

        Returns:
            Dictionary containing Xet extension capabilities

        """
        handshake = {
            "xet": {
                "version": "1.0",
                "supports_chunk_requests": True,
                "supports_p2p_cas": True,
                "supports_folder_sync": True,  # New: folder sync support
            }
        }

        # Merge with folder sync handshake if available
        if hasattr(self, "folder_sync_handshake"):
            folder_handshake = self.folder_sync_handshake.encode_handshake()
            handshake.update(folder_handshake)

        return handshake

    def decode_handshake(self, peer_id: str, data: dict[str, Any]) -> bool:
        """Decode Xet extension handshake data.

        Args:
            peer_id: Peer identifier
            data: Extension handshake data dictionary

        Returns:
            True if peer supports Xet extension and passes allowlist verification

        """
        xet_data = data.get("xet", {})
        if not isinstance(xet_data, dict):
            return False

        if not xet_data.get("supports_chunk_requests", False):
            return False

        # Verify folder sync handshake if available
        if self.folder_sync_handshake:
            try:
                # Decode folder sync handshake
                handshake_info = self.folder_sync_handshake.decode_handshake(
                    peer_id, data
                )

                if handshake_info:
                    # Verify allowlist hash
                    peer_allowlist_hash = handshake_info.get("allowlist_hash")
                    if not self.folder_sync_handshake.verify_peer_allowlist(
                        peer_id, peer_allowlist_hash
                    ):
                        logger.warning(
                            "Peer %s failed allowlist verification, rejecting",
                            peer_id,
                        )
                        return False

                    # Verify peer identity if public key provided
                    public_key = handshake_info.get("ed25519_public_key")
                    if public_key and self.folder_sync_handshake.key_manager:
                        # Note: Full signature verification would happen during
                        # actual message exchange, not just handshake
                        logger.debug(
                            "Peer %s provided Ed25519 public key for verification",
                            peer_id,
                        )

                    logger.debug(
                        "Peer %s passed allowlist verification", peer_id
                    )
            except Exception as e:
                logger.warning(
                    "Error verifying peer %s handshake: %s", peer_id, e
                )
                # If folder sync is required, reject on error
                # Otherwise, allow basic Xet extension
                if self.folder_sync_handshake and self.folder_sync_handshake.allowlist_hash:
                    return False

        return True

    def encode_chunk_request(self, chunk_hash: bytes) -> bytes:
        """Encode chunk request message.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            Encoded request message

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        self.request_counter += 1
        request_id = self.request_counter

        # Pack: <message_type><request_id><chunk_hash>
        return struct.pack("!BI", XetMessageType.CHUNK_REQUEST, request_id) + chunk_hash

    def decode_chunk_request(self, data: bytes) -> tuple[int, bytes]:
        """Decode chunk request message.

        Args:
            data: Encoded request message

        Returns:
            Tuple of (request_id, chunk_hash)

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 37:  # 1 byte type + 4 bytes request_id + 32 bytes hash
            msg = "Invalid Xet chunk request message"
            raise ValueError(msg)

        message_type, request_id = struct.unpack("!BI", data[:5])
        if message_type != XetMessageType.CHUNK_REQUEST:
            msg = "Invalid message type for chunk request"
            raise ValueError(msg)

        chunk_hash = data[5:37]
        if len(chunk_hash) != 32:
            msg = "Invalid chunk hash length"
            raise ValueError(msg)

        return request_id, chunk_hash

    def encode_chunk_response(self, request_id: int, chunk_data: bytes) -> bytes:
        """Encode chunk response message.

        Args:
            request_id: Request ID to respond to
            chunk_data: Chunk data bytes

        Returns:
            Encoded response message

        """
        # Pack: <message_type><request_id><chunk_size><chunk_data>
        return (
            struct.pack(
                "!BII",
                XetMessageType.CHUNK_RESPONSE,
                request_id,
                len(chunk_data),
            )
            + chunk_data
        )

    def decode_chunk_response(self, data: bytes) -> tuple[int, bytes]:
        """Decode chunk response message.

        Args:
            data: Encoded response message

        Returns:
            Tuple of (request_id, chunk_data)

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 9:  # 1 byte type + 4 bytes request_id + 4 bytes size
            msg = "Invalid Xet chunk response message"
            raise ValueError(msg)

        message_type, request_id, chunk_size = struct.unpack("!BII", data[:9])
        if message_type != XetMessageType.CHUNK_RESPONSE:
            msg = "Invalid message type for chunk response"
            raise ValueError(msg)

        if len(data) < 9 + chunk_size:
            msg = "Incomplete chunk data in response"
            raise ValueError(msg)

        chunk_data = data[9 : 9 + chunk_size]
        return request_id, chunk_data

    def encode_chunk_not_found(self, request_id: int) -> bytes:
        """Encode chunk not found message.

        Args:
            request_id: Request ID

        Returns:
            Encoded not found message

        """
        # Pack: <message_type><request_id>
        return struct.pack("!BI", XetMessageType.CHUNK_NOT_FOUND, request_id)

    def encode_chunk_error(self, request_id: int, error_code: int = 0) -> bytes:
        """Encode chunk error message.

        Args:
            request_id: Request ID
            error_code: Error code (0 = generic error)

        Returns:
            Encoded error message

        """
        # Pack: <message_type><request_id><error_code>
        return struct.pack("!BII", XetMessageType.CHUNK_ERROR, request_id, error_code)

    async def handle_chunk_request(
        self, peer_id: str, request_id: int, chunk_hash: bytes
    ) -> bytes:
        """Handle chunk request from peer.

        Args:
            peer_id: Peer identifier
            request_id: Request ID
            chunk_hash: 32-byte chunk hash

        Returns:
            Response message (chunk data, not found, or error)

        """
        # Store request
        self.pending_requests[(peer_id, request_id)] = XetChunkRequest(
            chunk_hash=chunk_hash,
            request_id=request_id,
            timestamp=time.time(),
        )

        # Try to get chunk from provider
        if self.chunk_provider:
            try:
                chunk_data = self.chunk_provider(chunk_hash)
                if chunk_data is not None:
                    # Emit event
                    await emit_event(
                        Event(
                            event_type=EventType.XET_CHUNK_PROVIDED.value,
                            data={
                                "peer_id": peer_id,
                                "request_id": request_id,
                                "chunk_hash": chunk_hash.hex(),
                                "chunk_size": len(chunk_data),
                                "timestamp": time.time(),
                            },
                        ),
                    )
                    return self.encode_chunk_response(request_id, chunk_data)
            except Exception as e:
                logger.warning(
                    "Error providing chunk %s: %s",
                    chunk_hash.hex()[:16],
                    e,
                )
                # Emit event
                await emit_event(
                    Event(
                        event_type=EventType.XET_CHUNK_ERROR.value,
                        data={
                            "peer_id": peer_id,
                            "request_id": request_id,
                            "chunk_hash": chunk_hash.hex(),
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )
                return self.encode_chunk_error(request_id, 1)

        # Chunk not found
        await emit_event(
            Event(
                event_type=EventType.XET_CHUNK_NOT_FOUND.value,
                data={
                    "peer_id": peer_id,
                    "request_id": request_id,
                    "chunk_hash": chunk_hash.hex(),
                    "timestamp": time.time(),
                },
            ),
        )
        return self.encode_chunk_not_found(request_id)

    async def handle_chunk_response(
        self, peer_id: str, request_id: int, chunk_data: bytes
    ) -> None:
        """Handle chunk response from peer.

        Args:
            peer_id: Peer identifier
            request_id: Request ID
            chunk_data: Chunk data bytes

        """
        # Remove from pending requests
        key = (peer_id, request_id)
        if key in self.pending_requests:
            request = self.pending_requests.pop(key)
            # Emit event
            await emit_event(
                Event(
                    event_type=EventType.XET_CHUNK_RECEIVED.value,
                    data={
                        "peer_id": peer_id,
                        "request_id": request_id,
                        "chunk_hash": request.chunk_hash.hex(),
                        "chunk_size": len(chunk_data),
                        "timestamp": time.time(),
                    },
                ),
            )

    def get_capabilities(self) -> dict[str, Any]:
        """Get Xet extension capabilities.

        Returns:
            Capabilities dictionary

        """
        return {
            "supports_chunk_requests": True,
            "supports_p2p_cas": True,
            "supports_folder_sync": True,
            "version": "1.0",
            "pending_requests": len(self.pending_requests),
        }

    def encode_version_request(self) -> bytes:
        """Encode folder version request message.

        Returns:
            Encoded version request message

        """
        # Pack: <message_type>
        return struct.pack("!B", XetMessageType.FOLDER_VERSION_REQUEST)

    def encode_version_response(self, git_ref: str | None) -> bytes:
        """Encode folder version response message.

        Args:
            git_ref: Git commit hash/ref or None

        Returns:
            Encoded version response message

        """
        # Pack: <message_type><has_ref><ref_length><ref_data>
        if git_ref:
            ref_bytes = git_ref.encode("utf-8")
            return struct.pack("!BB", XetMessageType.FOLDER_VERSION_RESPONSE, 1) + struct.pack("!I", len(ref_bytes)) + ref_bytes
        return struct.pack("!BB", XetMessageType.FOLDER_VERSION_RESPONSE, 0)

    def decode_version_response(self, data: bytes) -> str | None:
        """Decode folder version response message.

        Args:
            data: Encoded response message

        Returns:
            Git commit hash/ref or None

        """
        if len(data) < 2:
            msg = "Invalid version response message"
            raise ValueError(msg)

        message_type, has_ref = struct.unpack("!BB", data[:2])
        if message_type != XetMessageType.FOLDER_VERSION_RESPONSE:
            msg = "Invalid message type for version response"
            raise ValueError(msg)

        if has_ref == 0:
            return None

        if len(data) < 6:
            msg = "Incomplete version response message"
            raise ValueError(msg)

        ref_length = struct.unpack("!I", data[2:6])[0]
        if len(data) < 6 + ref_length:
            msg = "Incomplete version response data"
            raise ValueError(msg)

        ref_bytes = data[6 : 6 + ref_length]
        return ref_bytes.decode("utf-8")

    def encode_update_notify(
        self, file_path: str, chunk_hash: bytes, git_ref: str | None = None
    ) -> bytes:
        """Encode folder update notification message.

        Args:
            file_path: Path to updated file
            chunk_hash: Hash of updated chunk
            git_ref: Optional git commit hash/ref

        Returns:
            Encoded update notification message

        """
        # Pack: <message_type><file_path_length><file_path><chunk_hash><has_ref><ref_length><ref_data>
        file_path_bytes = file_path.encode("utf-8")
        parts = [
            struct.pack("!B", XetMessageType.FOLDER_UPDATE_NOTIFY),
            struct.pack("!I", len(file_path_bytes)),
            file_path_bytes,
            chunk_hash,
        ]

        if git_ref:
            ref_bytes = git_ref.encode("utf-8")
            parts.append(struct.pack("!BI", 1, len(ref_bytes)))
            parts.append(ref_bytes)
        else:
            parts.append(struct.pack("!B", 0))

        return b"".join(parts)

    def decode_update_notify(self, data: bytes) -> tuple[str, bytes, str | None]:
        """Decode folder update notification message.

        Args:
            data: Encoded notification message

        Returns:
            Tuple of (file_path, chunk_hash, git_ref)

        """
        if len(data) < 1:
            msg = "Invalid update notify message"
            raise ValueError(msg)

        message_type = data[0]
        if message_type != XetMessageType.FOLDER_UPDATE_NOTIFY:
            msg = "Invalid message type for update notify"
            raise ValueError(msg)

        if len(data) < 5:
            msg = "Incomplete update notify message"
            raise ValueError(msg)

        file_path_length = struct.unpack("!I", data[1:5])[0]
        if len(data) < 5 + file_path_length:
            msg = "Incomplete file path in update notify"
            raise ValueError(msg)

        file_path = data[5 : 5 + file_path_length].decode("utf-8")
        offset = 5 + file_path_length

        if len(data) < offset + 32:
            msg = "Incomplete chunk hash in update notify"
            raise ValueError(msg)

        chunk_hash = data[offset : offset + 32]
        offset += 32

        git_ref: str | None = None
        if len(data) > offset:
            has_ref = data[offset]
            offset += 1
            if has_ref == 1:
                if len(data) < offset + 4:
                    msg = "Incomplete git ref in update notify"
                    raise ValueError(msg)
                ref_length = struct.unpack("!I", data[offset : offset + 4])[0]
                offset += 4
                if len(data) >= offset + ref_length:
                    git_ref = data[offset : offset + ref_length].decode("utf-8")

        return file_path, chunk_hash, git_ref

    def encode_bloom_request(self) -> bytes:
        """Encode bloom filter request message.

        Returns:
            Encoded bloom filter request message

        """
        # Pack: <message_type>
        return struct.pack("!B", XetMessageType.BLOOM_FILTER_REQUEST)

    def decode_bloom_request(self, data: bytes) -> bool:
        """Decode bloom filter request message.

        Args:
            data: Encoded request message

        Returns:
            True if message is valid bloom filter request

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 1:
            msg = "Invalid bloom filter request message"
            raise ValueError(msg)

        message_type = data[0]
        if message_type != XetMessageType.BLOOM_FILTER_REQUEST:
            msg = "Invalid message type for bloom filter request"
            raise ValueError(msg)

        return True

    def encode_bloom_response(self, bloom_data: bytes) -> bytes:
        """Encode bloom filter response message.

        Args:
            bloom_data: Serialized bloom filter data

        Returns:
            Encoded bloom filter response message

        """
        # Pack: <message_type><bloom_size><bloom_data>
        return (
            struct.pack("!BI", XetMessageType.BLOOM_FILTER_RESPONSE, len(bloom_data))
            + bloom_data
        )

    def decode_bloom_response(self, data: bytes) -> bytes:
        """Decode bloom filter response message.

        Args:
            data: Encoded response message

        Returns:
            Bloom filter data bytes

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 5:
            msg = "Invalid bloom filter response message"
            raise ValueError(msg)

        message_type, bloom_size = struct.unpack("!BI", data[:5])
        if message_type != XetMessageType.BLOOM_FILTER_RESPONSE:
            msg = "Invalid message type for bloom filter response"
            raise ValueError(msg)

        if len(data) < 5 + bloom_size:
            msg = "Incomplete bloom filter data in response"
            raise ValueError(msg)

        bloom_data = data[5 : 5 + bloom_size]
        return bloom_data
