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


@dataclass
class XetChunkRequest:
    """Xet chunk request information."""

    chunk_hash: bytes
    request_id: int
    timestamp: float


class XetExtension:
    """Xet Protocol Extension implementation."""

    def __init__(self):
        """Initialize Xet Extension."""
        self.pending_requests: dict[
            tuple[str, int], XetChunkRequest
        ] = {}  # (peer_id, request_id) -> request
        self.request_counter = 0
        self.chunk_provider: Callable[[bytes], bytes | None] | None = None

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
        return {
            "xet": {
                "version": "1.0",
                "supports_chunk_requests": True,
                "supports_p2p_cas": True,
            }
        }

    def decode_handshake(self, data: dict[str, Any]) -> bool:
        """Decode Xet extension handshake data.

        Args:
            data: Extension handshake data dictionary

        Returns:
            True if peer supports Xet extension

        """
        xet_data = data.get("xet", {})
        if isinstance(xet_data, dict):
            return xet_data.get("supports_chunk_requests", False)
        return False

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
            "version": "1.0",
            "pending_requests": len(self.pending_requests),
        }
