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
from typing import Any, Awaitable, Callable, Optional

from ccbt.storage.xet_hashing import XetHasher
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
    # Gossip sync (receive path: peer sends us gossip messages)
    GOSSIP_SYNC = 0x40  # Gossip message batch from peer (payload: JSON messages dict)


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
        folder_sync_handshake: Optional[Any] = None,  # XetHandshakeExtension
    ):
        """Initialize Xet Extension.

        Args:
            folder_sync_handshake: Optional XetHandshakeExtension for folder sync

        """
        self.pending_requests: dict[
            tuple[str, int], XetChunkRequest
        ] = {}  # (peer_id, request_id) -> request
        self.request_counter = 0
        self.chunk_provider: Optional[Callable[[bytes], Optional[bytes]]] = None
        self.folder_sync_handshake = folder_sync_handshake
        self.version_provider: Optional[Callable[[str], Optional[str]]] = None
        self.sync_mode_provider: Optional[Callable[[str], Optional[str]]] = None
        self.update_handler: Optional[
            Callable[
                [
                    str,
                    Optional[str],
                    str,
                    bytes,
                    Optional[str],
                    str,
                    Optional[str],
                    Optional[str],
                ],
                Awaitable[None] | None,
            ]
        ] = None
        self.bloom_provider: Optional[Callable[[str], bytes]] = None
        self.on_bloom_response: Optional[Callable[[str, bytes], None]] = None
        self.metadata_exchange: Optional[Any] = None
        self.message_sender: Optional[
            Callable[[str, bytes], Awaitable[bool] | bool]
        ] = None

    def set_chunk_provider(self, provider: Callable[[bytes], Optional[bytes]]) -> None:
        """Set function to provide chunks by hash.

        Args:
            provider: Callable that takes chunk_hash (32 bytes) and returns
                     chunk data bytes or None if not available

        """
        self.chunk_provider = provider

    def set_version_provider(self, provider: Callable[[str], Optional[str]]) -> None:
        """Set function that returns current folder version for a peer."""
        self.version_provider = provider

    def set_sync_mode_provider(self, provider: Callable[[str], Optional[str]]) -> None:
        """Set function that returns sync mode for a peer."""
        self.sync_mode_provider = provider

    def set_update_handler(
        self,
        handler: Callable[
            [
                str,
                Optional[str],
                str,
                bytes,
                Optional[str],
                str,
                Optional[str],
                Optional[str],
            ],
            Awaitable[None] | None,
        ],
    ) -> None:
        """Set callback for incoming folder update notifications."""
        self.update_handler = handler

    def set_bloom_provider(self, provider: Callable[[str], bytes]) -> None:
        """Set function that returns serialized bloom filter data for a peer."""
        self.bloom_provider = provider

    def set_metadata_exchange(self, metadata_exchange: Any) -> None:
        """Attach metadata exchange helper used for folder metadata messages."""
        self.metadata_exchange = metadata_exchange

    def set_message_sender(
        self, sender: Callable[[str, bytes], Awaitable[bool] | bool]
    ) -> None:
        """Attach a transport callback for outbound XET messages."""
        self.message_sender = sender

    async def send_message(self, peer_id: str, payload: bytes) -> bool:
        """Send an outbound XET message through the configured transport."""
        if self.message_sender is None:
            return False
        result = self.message_sender(peer_id, payload)
        if hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)

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
                "supports_folder_sync": True,
                "supports_delete_updates": True,
                "supports_metadata_exchange": True,
                "supports_bloom_filters": True,
                "supports_discovery_hints": True,
                "update_notify_version": 1,
                "hash_algorithm": XetHasher.get_hash_identity(),
            }
        }

        # Merge with folder sync handshake if available
        if (
            hasattr(self, "folder_sync_handshake")
            and self.folder_sync_handshake is not None
        ):
            folder_handshake = self.folder_sync_handshake.encode_handshake()  # type: ignore[attr-defined]
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
                    # Verify allowlist hash and freshness (replay check)
                    peer_allowlist_hash = handshake_info.get("allowlist_hash")
                    if not self.folder_sync_handshake.verify_peer_allowlist(
                        peer_id,
                        peer_allowlist_hash,
                        peer_public_key=handshake_info.get("ed25519_public_key"),
                        peer_workspace_id=handshake_info.get("workspace_id"),
                        peer_nonce=handshake_info.get("ed25519_nonce"),
                    ):
                        logger.warning(
                            "Peer %s failed allowlist verification, rejecting",
                            peer_id,
                        )
                        return False

                    if not self.folder_sync_handshake.verify_handshake_identity(
                        peer_id, handshake_info
                    ):
                        logger.warning(
                            "Peer %s failed XET identity verification, rejecting",
                            peer_id,
                        )
                        return False

                    logger.debug("Peer %s passed allowlist verification", peer_id)
            except Exception as e:
                logger.warning("Error verifying peer %s handshake: %s", peer_id, e)
                # If folder sync is required, reject on error
                # Otherwise, allow basic Xet extension
                if (
                    self.folder_sync_handshake
                    and self.folder_sync_handshake.allowlist_hash
                ):
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
            "hash_algorithm": XetHasher.get_hash_identity(),
            "pending_requests": len(self.pending_requests),
        }

    def encode_version_request(self) -> bytes:
        """Encode folder version request message.

        Returns:
            Encoded version request message

        """
        # Pack: <message_type>
        return struct.pack("!B", XetMessageType.FOLDER_VERSION_REQUEST)

    def encode_version_response(self, git_ref: Optional[str]) -> bytes:
        """Encode folder version response message.

        Args:
            git_ref: Git commit hash/ref or None

        Returns:
            Encoded version response message

        """
        # Pack: <message_type><has_ref><ref_length><ref_data>
        if git_ref:
            ref_bytes = git_ref.encode("utf-8")
            return (
                struct.pack("!BB", XetMessageType.FOLDER_VERSION_RESPONSE, 1)
                + struct.pack("!I", len(ref_bytes))
                + ref_bytes
            )
        return struct.pack("!BB", XetMessageType.FOLDER_VERSION_RESPONSE, 0)

    def decode_version_response(self, data: bytes) -> Optional[str]:
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
        self,
        file_path: str,
        chunk_hash: bytes,
        git_ref: Optional[str] = None,
        workspace_id: Optional[bytes] = None,
        operation: str = "upsert",
        metadata_version: Optional[str] = None,
        metadata_root: Optional[str] = None,
    ) -> bytes:
        """Encode folder update notification message.

        Args:
            file_path: Path to updated file
            chunk_hash: Hash of updated chunk
            git_ref: Optional git commit hash/ref
            workspace_id: Optional workspace identifier for routed updates
            operation: Operation kind (`upsert` or `delete`)
            metadata_version: Optional metadata snapshot version for validation
            metadata_root: Optional metadata root hash for validation

        Returns:
            Encoded update notification message

        """
        # Pack:
        # <message_type><version><operation><has_workspace><workspace_id?>
        # <file_path_length><file_path><file_root_hash><has_ref><ref_length?><ref_data?>
        # <has_metadata_version><metadata_version_length?><metadata_version?>
        # <has_metadata_root><metadata_root_length?><metadata_root?>
        #
        # Runtime contract:
        # - workspace_id should be present for routed workspace updates
        # - file_path + chunk_hash are required for remote materialization
        # - git_ref is advisory and may be omitted by older peers
        # - operation distinguishes create/update/delete on the wire
        file_path_bytes = file_path.encode("utf-8")
        operation_codes = {"upsert": 1, "delete": 2}
        operation_code = operation_codes.get(operation, 1)
        parts = [
            struct.pack("!B", XetMessageType.FOLDER_UPDATE_NOTIFY),
            struct.pack("!B", 1),
            struct.pack("!B", operation_code),
            struct.pack("!B", 1 if workspace_id is not None else 0),
        ]
        if workspace_id is not None:
            if len(workspace_id) != 32:
                msg = f"Workspace ID must be 32 bytes, got {len(workspace_id)}"
                raise ValueError(msg)
            parts.append(workspace_id)
        parts.extend(
            [
                struct.pack("!I", len(file_path_bytes)),
                file_path_bytes,
                chunk_hash,
            ]
        )

        if git_ref:
            ref_bytes = git_ref.encode("utf-8")
            parts.append(struct.pack("!BI", 1, len(ref_bytes)))
            parts.append(ref_bytes)
        else:
            parts.append(struct.pack("!B", 0))

        if metadata_version:
            metadata_version_bytes = metadata_version.encode("utf-8")
            parts.append(struct.pack("!BI", 1, len(metadata_version_bytes)))
            parts.append(metadata_version_bytes)
        else:
            parts.append(struct.pack("!B", 0))

        if metadata_root:
            metadata_root_bytes = metadata_root.encode("utf-8")
            parts.append(struct.pack("!BI", 1, len(metadata_root_bytes)))
            parts.append(metadata_root_bytes)
        else:
            parts.append(struct.pack("!B", 0))

        return b"".join(parts)

    def decode_update_notify(
        self, data: bytes
    ) -> tuple[
        Optional[str],
        str,
        bytes,
        Optional[str],
        str,
        Optional[str],
        Optional[str],
    ]:
        """Decode folder update notification message.

        Args:
            data: Encoded notification message

        Returns:
            Tuple of (workspace_id_hex, file_path, chunk_hash, git_ref, operation, metadata_version, metadata_root)

        """
        if len(data) < 1:
            msg = "Invalid update notify message"
            raise ValueError(msg)

        message_type = data[0]
        if message_type != XetMessageType.FOLDER_UPDATE_NOTIFY:
            msg = "Invalid message type for update notify"
            raise ValueError(msg)

        if len(data) < 2:
            msg = "Incomplete update notify message"
            raise ValueError(msg)

        offset = 1
        version = data[offset]
        offset += 1
        operation = "upsert"
        if version >= 1:
            if len(data) < offset + 2:
                msg = "Incomplete versioned update notify header"
                raise ValueError(msg)
            operation_code = data[offset]
            operation = "delete" if operation_code == 2 else "upsert"
            offset += 1
        has_workspace = data[offset]
        offset += 1

        workspace_id_hex: Optional[str] = None
        if has_workspace == 1:
            if len(data) < offset + 32:
                msg = "Incomplete workspace id in update notify"
                raise ValueError(msg)
            workspace_id_hex = data[offset : offset + 32].hex()
            offset += 32

        if len(data) < offset + 4:
            msg = "Incomplete file path length in update notify"
            raise ValueError(msg)
        file_path_length = struct.unpack("!I", data[offset : offset + 4])[0]
        offset += 4
        if len(data) < offset + file_path_length:
            msg = "Incomplete file path in update notify"
            raise ValueError(msg)

        file_path = data[offset : offset + file_path_length].decode("utf-8")
        offset += file_path_length

        if len(data) < offset + 32:
            msg = "Incomplete chunk hash in update notify"
            raise ValueError(msg)

        chunk_hash = data[offset : offset + 32]
        offset += 32

        git_ref: Optional[str] = None
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
                    offset += ref_length

        metadata_version: Optional[str] = None
        if len(data) > offset:
            has_metadata_version = data[offset]
            offset += 1
            if has_metadata_version == 1:
                if len(data) < offset + 4:
                    msg = "Incomplete metadata version in update notify"
                    raise ValueError(msg)
                metadata_length = struct.unpack("!I", data[offset : offset + 4])[0]
                offset += 4
                if len(data) < offset + metadata_length:
                    msg = "Incomplete metadata version payload in update notify"
                    raise ValueError(msg)
                metadata_version = data[offset : offset + metadata_length].decode(
                    "utf-8"
                )
                offset += metadata_length

        metadata_root: Optional[str] = None
        if len(data) > offset:
            has_metadata_root = data[offset]
            offset += 1
            if has_metadata_root == 1:
                if len(data) < offset + 4:
                    msg = "Incomplete metadata root in update notify"
                    raise ValueError(msg)
                metadata_root_length = struct.unpack("!I", data[offset : offset + 4])[0]
                offset += 4
                if len(data) < offset + metadata_root_length:
                    msg = "Incomplete metadata root payload in update notify"
                    raise ValueError(msg)
                metadata_root = data[offset : offset + metadata_root_length].decode(
                    "utf-8"
                )

        return (
            workspace_id_hex,
            file_path,
            chunk_hash,
            git_ref,
            operation,
            metadata_version,
            metadata_root,
        )

    def encode_sync_mode_request(self) -> bytes:
        """Encode folder sync mode request message."""
        return struct.pack("!B", XetMessageType.FOLDER_SYNC_MODE_REQUEST)

    def decode_sync_mode_request(self, data: bytes) -> bool:
        """Decode folder sync mode request message."""
        if len(data) < 1 or data[0] != XetMessageType.FOLDER_SYNC_MODE_REQUEST:
            msg = "Invalid sync mode request message"
            raise ValueError(msg)
        return True

    def encode_sync_mode_response(self, sync_mode: Optional[str]) -> bytes:
        """Encode folder sync mode response message."""
        if not sync_mode:
            return struct.pack("!BB", XetMessageType.FOLDER_SYNC_MODE_RESPONSE, 0)
        mode_bytes = sync_mode.encode("utf-8")
        return (
            struct.pack(
                "!BBI", XetMessageType.FOLDER_SYNC_MODE_RESPONSE, 1, len(mode_bytes)
            )
            + mode_bytes
        )

    def decode_sync_mode_response(self, data: bytes) -> Optional[str]:
        """Decode folder sync mode response message."""
        if len(data) < 2 or data[0] != XetMessageType.FOLDER_SYNC_MODE_RESPONSE:
            msg = "Invalid sync mode response message"
            raise ValueError(msg)
        if data[1] == 0:
            return None
        if len(data) < 6:
            msg = "Incomplete sync mode response message"
            raise ValueError(msg)
        mode_length = struct.unpack("!I", data[2:6])[0]
        if len(data) < 6 + mode_length:
            msg = "Incomplete sync mode response data"
            raise ValueError(msg)
        return data[6 : 6 + mode_length].decode("utf-8")

    async def handle_version_request(self, peer_id: str) -> bytes:
        """Build a version response for a peer."""
        git_ref = self.version_provider(peer_id) if self.version_provider else None
        return self.encode_version_response(git_ref)

    async def handle_update_notify(
        self,
        peer_id: str,
        workspace_id_hex: Optional[str],
        file_path: str,
        chunk_hash: bytes,
        git_ref: Optional[str],
        operation: str = "upsert",
        metadata_version: Optional[str] = None,
        metadata_root: Optional[str] = None,
    ) -> None:
        """Handle an incoming folder update notification."""
        if self.update_handler is None:
            return
        result = self.update_handler(
            peer_id,
            workspace_id_hex,
            file_path,
            chunk_hash,
            git_ref,
            operation,
            metadata_version,
            metadata_root,
        )
        if hasattr(result, "__await__"):
            await result

    async def handle_sync_mode_request(self, peer_id: str) -> bytes:
        """Build a sync mode response for a peer."""
        sync_mode = (
            self.sync_mode_provider(peer_id) if self.sync_mode_provider else None
        )
        return self.encode_sync_mode_response(sync_mode)

    async def handle_bloom_request(self, peer_id: str) -> bytes:
        """Build a bloom filter response for a peer."""
        bloom_data = self.bloom_provider(peer_id) if self.bloom_provider else b""
        return self.encode_bloom_response(bloom_data)

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

        return data[5 : 5 + bloom_size]
