"""XET metadata exchange extension (similar to ut_metadata for torrents).

This module implements metadata exchange for XET folders, allowing peers
to request and receive folder structure and file information from .tonic files.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Callable
from typing import Any

from ccbt.extensions.xet import XetExtension, XetMessageType

logger = logging.getLogger(__name__)


class XetMetadataExchange:
    """XET metadata exchange handler (similar to ut_metadata)."""

    def __init__(self, extension: XetExtension) -> None:
        """Initialize metadata exchange.

        Args:
            extension: XetExtension instance

        """
        self.extension = extension
        self.logger = logging.getLogger(__name__)

        # Metadata state per peer
        self.metadata_state: dict[str, dict[str, Any]] = {}

        # Metadata provider callback
        self.metadata_provider: Callable[[bytes], bytes | None] | None = None

    def set_metadata_provider(
        self, provider: Callable[[bytes], bytes | None]
    ) -> None:
        """Set function to provide metadata by info_hash.

        Args:
            provider: Callable that takes info_hash (32 bytes) and returns
                     bencoded .tonic file data or None if not available

        """
        self.metadata_provider = provider

    def encode_metadata_request(self, info_hash: bytes, piece: int = 0) -> bytes:
        """Encode metadata request message.

        Args:
            info_hash: 32-byte info hash
            piece: Piece index (0 for full metadata, or piece number)

        Returns:
            Encoded request message

        """
        # Format: <message_type><info_hash><piece_index>
        return (
            struct.pack("!B", XetMessageType.FOLDER_METADATA_REQUEST)
            + info_hash
            + struct.pack("!I", piece)
        )

    def decode_metadata_request(self, data: bytes) -> tuple[bytes, int]:
        """Decode metadata request message.

        Args:
            data: Encoded request message

        Returns:
            Tuple of (info_hash, piece_index)

        """
        if len(data) < 37:  # 1 byte message type + 32 bytes hash + 4 bytes piece
            msg = "Invalid metadata request message"
            raise ValueError(msg)

        message_type = data[0]
        if message_type != XetMessageType.FOLDER_METADATA_REQUEST:
            msg = "Invalid message type for metadata request"
            raise ValueError(msg)

        info_hash = data[1:33]
        piece_index = struct.unpack("!I", data[33:37])[0]

        return info_hash, piece_index

    def encode_metadata_response(
        self, info_hash: bytes, piece: int, total_pieces: int, data: bytes
    ) -> bytes:
        """Encode metadata response message.

        Args:
            info_hash: 32-byte info hash
            piece: Piece index
            total_pieces: Total number of pieces
            data: Piece data (bencoded .tonic file data or piece)

        Returns:
            Encoded response message

        """
        # Format: <message_type><info_hash><piece_index><total_pieces><data_length><data>
        return (
            struct.pack("!B", XetMessageType.FOLDER_METADATA_RESPONSE)
            + info_hash
            + struct.pack("!III", piece, total_pieces, len(data))
            + data
        )

    def decode_metadata_response(
        self, data: bytes
    ) -> tuple[bytes, int, int, bytes]:
        """Decode metadata response message.

        Args:
            data: Encoded response message

        Returns:
            Tuple of (info_hash, piece_index, total_pieces, piece_data)

        """
        if len(data) < 45:  # 1 + 32 + 4 + 4 + 4
            msg = "Invalid metadata response message"
            raise ValueError(msg)

        message_type = data[0]
        if message_type != XetMessageType.FOLDER_METADATA_RESPONSE:
            msg = "Invalid message type for metadata response"
            raise ValueError(msg)

        info_hash = data[1:33]
        piece_index, total_pieces, data_length = struct.unpack("!III", data[33:45])

        if len(data) < 45 + data_length:
            msg = "Incomplete metadata response data"
            raise ValueError(msg)

        piece_data = data[45 : 45 + data_length]

        return info_hash, piece_index, total_pieces, piece_data

    async def handle_metadata_request(
        self, peer_id: str, info_hash: bytes, piece: int
    ) -> None:
        """Handle incoming metadata request.

        Args:
            peer_id: Peer identifier
            info_hash: Info hash requested
            piece: Piece index requested

        """
        if not self.metadata_provider:
            self.logger.warning(
                "Metadata request from %s but no provider set", peer_id
            )
            return

        # Get metadata
        metadata_bytes = self.metadata_provider(info_hash)
        if not metadata_bytes:
            self.logger.debug(
                "Metadata not available for info_hash %s", info_hash.hex()[:16]
            )
            # Send not found response
            await self._send_metadata_not_found(peer_id, info_hash)
            return

        # For now, send full metadata (can be extended to support piece-based)
        # Calculate total pieces (if metadata is large, split into pieces)
        piece_size = 16 * 1024  # 16 KiB per piece
        total_pieces = (len(metadata_bytes) + piece_size - 1) // piece_size

        if piece >= total_pieces:
            self.logger.warning(
                "Invalid piece index %d (total: %d) from %s", piece, total_pieces, peer_id
            )
            return

        # Extract piece data
        start = piece * piece_size
        end = min(start + piece_size, len(metadata_bytes))
        piece_data = metadata_bytes[start:end]

        # Send response
        response = self.encode_metadata_response(
            info_hash, piece, total_pieces, piece_data
        )
        await self.extension.send_message(peer_id, response)

        self.logger.debug(
            "Sent metadata piece %d/%d to %s (size: %d)",
            piece + 1,
            total_pieces,
            peer_id,
            len(piece_data),
        )

    async def _send_metadata_not_found(self, peer_id: str, info_hash: bytes) -> None:
        """Send metadata not found response.

        Args:
            peer_id: Peer identifier
            info_hash: Info hash

        """
        # Format: <message_type><info_hash>
        not_found_msg = (
            struct.pack("!B", XetMessageType.FOLDER_METADATA_NOT_FOUND) + info_hash
        )
        await self.extension.send_message(peer_id, not_found_msg)

    async def handle_metadata_response(
        self, peer_id: str, info_hash: bytes, piece: int, total_pieces: int, data: bytes
    ) -> None:
        """Handle incoming metadata response.

        Args:
            peer_id: Peer identifier
            info_hash: Info hash
            piece: Piece index
            total_pieces: Total number of pieces
            data: Piece data

        """
        # Initialize state if needed
        state_key = f"{peer_id}:{info_hash.hex()}"
        if state_key not in self.metadata_state:
            self.metadata_state[state_key] = {
                "info_hash": info_hash,
                "total_pieces": total_pieces,
                "pieces": {},
                "received_pieces": set(),
            }

        state = self.metadata_state[state_key]

        # Store piece
        state["pieces"][piece] = data
        state["received_pieces"].add(piece)

        self.logger.debug(
            "Received metadata piece %d/%d from %s (received: %d/%d)",
            piece + 1,
            total_pieces,
            peer_id,
            len(state["received_pieces"]),
            total_pieces,
        )

        # Check if all pieces received
        if len(state["received_pieces"]) >= total_pieces:
            # Reconstruct full metadata
            pieces = [state["pieces"][i] for i in range(total_pieces)]
            full_metadata = b"".join(pieces)

            # Parse and validate
            try:
                from ccbt.core.tonic import TonicFile

                tonic_parser = TonicFile()
                parsed_data = tonic_parser.parse_bytes(full_metadata)

                self.logger.info(
                    "Received complete metadata from %s (info_hash: %s)",
                    peer_id,
                    info_hash.hex()[:16],
                )

                # Emit event
                from ccbt.utils.events import Event, EventType, emit_event

                await emit_event(
                    Event(
                        event_type=EventType.XET_METADATA_RECEIVED.value,
                        data={
                            "peer_id": peer_id,
                            "info_hash": info_hash.hex(),
                            "metadata": parsed_data,
                        },
                    )
                )

                # Clean up state
                del self.metadata_state[state_key]

            except Exception as e:
                self.logger.exception("Failed to parse received metadata: %s", e)
                # Request all pieces again
                await self._request_all_pieces(peer_id, info_hash, total_pieces)

    async def _request_all_pieces(
        self, peer_id: str, info_hash: bytes, total_pieces: int
    ) -> None:
        """Request all metadata pieces.

        Args:
            peer_id: Peer identifier
            info_hash: Info hash
            total_pieces: Total number of pieces

        """
        for piece in range(total_pieces):
            request = self.encode_metadata_request(info_hash, piece)
            await self.extension.send_message(peer_id, request)
            # Small delay between requests
            await asyncio.sleep(0.1)

