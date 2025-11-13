"""Shard format handler for Xet protocol.

Shards contain file metadata and CAS information for efficient retrieval.
This module provides serialization and deserialization of the shard binary format.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import struct

# No Optional needed - using X | None syntax

logger = logging.getLogger(__name__)

# Shard format constants
SHARD_MAGIC = b"SHAR"  # Magic bytes for shard format
SHARD_VERSION = 1  # Format version
SHARD_HEADER_SIZE = 24  # Header size in bytes
HMAC_SIZE = 32  # HMAC-SHA256 size


class XetShard:
    """Shard format handler for metadata storage.

    Shards group file metadata and CAS information for efficient retrieval.
    Each shard contains:
    - File information (paths, sizes, hashes)
    - Xorb references
    - Chunk hashes
    - HMAC for integrity verification

    Attributes:
        files: List of file metadata dictionaries
        xorbs: List of xorb hashes
        chunks: List of chunk hashes

    """

    def __init__(self):
        """Initialize empty shard."""
        self.files: list[dict] = []  # File metadata
        self.xorbs: list[bytes] = []  # Xorb hashes (32 bytes each)
        self.chunks: list[bytes] = []  # Chunk hashes (32 bytes each)

    def add_file_info(
        self,
        file_path: str,
        file_hash: bytes,
        xorb_refs: list[bytes],
        total_size: int,
    ) -> None:
        """Add file information to shard.

        Args:
            file_path: Path to the file
            file_hash: 32-byte Merkle root hash of the file
            xorb_refs: List of 32-byte xorb hashes that contain this file's chunks
            total_size: Total file size in bytes

        """
        if len(file_hash) != 32:
            msg = f"File hash must be 32 bytes, got {len(file_hash)}"
            raise ValueError(msg)

        for xorb_hash in xorb_refs:
            if len(xorb_hash) != 32:
                msg = f"Xorb hash must be 32 bytes, got {len(xorb_hash)}"
                raise ValueError(msg)

        self.files.append(
            {
                "path": file_path,
                "hash": file_hash,
                "xorbs": xorb_refs,
                "size": total_size,
            }
        )

    def add_chunk_hash(self, chunk_hash: bytes) -> None:
        """Add a chunk hash to the shard.

        Args:
            chunk_hash: 32-byte chunk hash

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        if chunk_hash not in self.chunks:
            self.chunks.append(chunk_hash)

    def add_xorb_hash(self, xorb_hash: bytes) -> None:
        """Add a xorb hash to the shard.

        Args:
            xorb_hash: 32-byte xorb hash

        """
        if len(xorb_hash) != 32:
            msg = f"Xorb hash must be 32 bytes, got {len(xorb_hash)}"
            raise ValueError(msg)

        if xorb_hash not in self.xorbs:
            self.xorbs.append(xorb_hash)

    def serialize(self, hmac_key: bytes | None = None) -> bytes:
        """Serialize shard to binary format with optional HMAC.

        Format:
        [Header: 24 bytes]
        - Magic: 4 bytes ("SHAR")
        - Version: 1 byte
        - Flags: 1 byte (HMAC flag, reserved bits)
        - Reserved: 2 bytes
        - File count: 4 bytes (uint32)
        - Xorb count: 4 bytes (uint32)
        - Chunk count: 4 bytes (uint32)
        - Reserved: 4 bytes

        [File Info Section: variable]
        - For each file:
          - Path length: 4 bytes (uint32)
          - Path: variable (UTF-8)
          - Hash: 32 bytes
          - Size: 8 bytes (uint64)
          - Xorb count: 4 bytes (uint32)
          - Xorb refs: variable (32 bytes each)

        [CAS Info Section: variable]
        - Xorb hashes: variable (32 bytes each)
        - Chunk hashes: variable (32 bytes each)

        [Footer with HMAC: variable]
        - HMAC: 32 bytes (if key provided)

        Args:
            hmac_key: Optional HMAC key for integrity verification

        Returns:
            Serialized shard data

        """
        # Build header
        header = self._serialize_header(hmac_key is not None)

        # Build file info section
        file_info = self._serialize_file_info()

        # Build CAS info section
        cas_info = self._serialize_cas_info()

        # Build footer with HMAC
        footer = self._serialize_footer(hmac_key, header + file_info + cas_info)

        return header + file_info + cas_info + footer

    def _serialize_header(self, has_hmac: bool) -> bytes:
        """Serialize shard header.

        Args:
            has_hmac: Whether HMAC is included

        Returns:
            24-byte header

        """
        flags = 0x01 if has_hmac else 0x00
        return struct.pack(
            "4sBB2sIII4s",
            SHARD_MAGIC,
            SHARD_VERSION,
            flags,
            b"\x00" * 2,  # Reserved
            len(self.files),
            len(self.xorbs),
            len(self.chunks),
            b"\x00" * 4,  # Reserved
        )

    def _serialize_file_info(self) -> bytes:
        """Serialize file information section.

        Returns:
            Serialized file info data

        """
        data = b""

        for file_info in self.files:
            # Path
            path_bytes = file_info["path"].encode("utf-8")
            data += struct.pack("I", len(path_bytes))  # Path length
            data += path_bytes  # Path

            # Hash
            data += file_info["hash"]

            # Size
            data += struct.pack("Q", file_info["size"])

            # Xorb refs
            xorb_refs = file_info["xorbs"]
            data += struct.pack("I", len(xorb_refs))
            for xorb_hash in xorb_refs:
                data += xorb_hash

        return data

    def _serialize_cas_info(self) -> bytes:
        """Serialize CAS information section.

        Returns:
            Serialized CAS info data

        """
        data = b""

        # Xorb hashes
        for xorb_hash in self.xorbs:
            data += xorb_hash

        # Chunk hashes
        for chunk_hash in self.chunks:
            data += chunk_hash

        return data

    def _serialize_footer(self, hmac_key: bytes | None, data: bytes) -> bytes:
        """Serialize footer with HMAC.

        Args:
            hmac_key: Optional HMAC key
            data: Data to compute HMAC over

        Returns:
            Footer data (HMAC if key provided, empty otherwise)

        """
        if hmac_key:
            return hmac.new(hmac_key, data, hashlib.sha256).digest()
        return b""

    @staticmethod
    def deserialize(data: bytes, hmac_key: bytes | None = None) -> XetShard:
        """Deserialize shard from binary format.

        Args:
            data: Serialized shard data
            hmac_key: Optional HMAC key for verification

        Returns:
            XetShard instance

        Raises:
            ValueError: If data is invalid or HMAC verification fails

        """
        if len(data) < SHARD_HEADER_SIZE:
            msg = (
                f"Shard data too short: {len(data)} bytes (minimum {SHARD_HEADER_SIZE})"
            )
            raise ValueError(msg)

        # Parse header
        header_data = data[:SHARD_HEADER_SIZE]
        (
            magic,
            version,
            flags,
            _reserved1,
            file_count,
            xorb_count,
            chunk_count,
            _reserved2,
        ) = struct.unpack("4sBB2sIII4s", header_data)

        if magic != SHARD_MAGIC:
            msg = f"Invalid shard magic: expected {SHARD_MAGIC}, got {magic}"
            raise ValueError(msg)

        if version != SHARD_VERSION:
            msg = f"Unsupported shard version: {version} (expected {SHARD_VERSION})"
            raise ValueError(msg)

        has_hmac = (flags & 0x01) != 0

        # Verify HMAC if present
        if has_hmac and hmac_key:
            if (
                len(data) < HMAC_SIZE
            ):  # pragma: no cover - Defensive check for corrupted data, tested in test_deserialize_short_data
                msg = "Shard data too short for HMAC"  # pragma: no cover - Same context
                raise ValueError(msg)  # pragma: no cover - Same context

            payload = data[:-HMAC_SIZE]
            expected_hmac = data[-HMAC_SIZE:]
            actual_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()

            if not hmac.compare_digest(expected_hmac, actual_hmac):
                msg = "Shard HMAC verification failed"
                raise ValueError(msg)

        # Parse file info section
        offset = SHARD_HEADER_SIZE
        shard = XetShard()

        for _ in range(file_count):
            # Parse path
            if len(data) < offset + 4:
                msg = "Shard data too short for path length"
                raise ValueError(msg)

            path_len = struct.unpack("I", data[offset : offset + 4])[0]
            offset += 4

            if len(data) < offset + path_len:
                msg = "Shard data too short for path"
                raise ValueError(msg)

            file_path = data[offset : offset + path_len].decode("utf-8")
            offset += path_len

            # Parse hash
            if len(data) < offset + 32:
                msg = "Shard data too short for file hash"
                raise ValueError(msg)

            file_hash = data[offset : offset + 32]
            offset += 32

            # Parse size
            if len(data) < offset + 8:
                msg = "Shard data too short for file size"
                raise ValueError(msg)

            file_size = struct.unpack("Q", data[offset : offset + 8])[0]
            offset += 8

            # Parse xorb refs
            if len(data) < offset + 4:
                msg = "Shard data too short for xorb count"
                raise ValueError(msg)

            xorb_ref_count = struct.unpack("I", data[offset : offset + 4])[0]
            offset += 4

            xorb_refs = []
            for _ in range(xorb_ref_count):
                if len(data) < offset + 32:
                    msg = "Shard data too short for xorb ref"
                    raise ValueError(msg)

                xorb_ref = data[offset : offset + 32]
                offset += 32
                xorb_refs.append(xorb_ref)

            shard.add_file_info(file_path, file_hash, xorb_refs, file_size)

        # Parse CAS info section
        # Xorb hashes
        for _ in range(xorb_count):
            if len(data) < offset + 32:
                msg = "Shard data too short for xorb hash"
                raise ValueError(msg)

            xorb_hash = data[offset : offset + 32]
            offset += 32
            shard.add_xorb_hash(xorb_hash)

        # Chunk hashes
        for _ in range(chunk_count):
            if len(data) < offset + 32:
                msg = "Shard data too short for chunk hash"
                raise ValueError(msg)

            chunk_hash = data[offset : offset + 32]
            offset += 32
            shard.add_chunk_hash(chunk_hash)

        return shard

    def get_file_count(self) -> int:
        """Get number of files in shard.

        Returns:
            Number of files

        """
        return len(self.files)

    def get_file_by_path(self, file_path: str) -> dict | None:
        """Get file information by path.

        Args:
            file_path: Path to file

        Returns:
            File info dictionary if found, None otherwise

        """
        for file_info in self.files:
            if file_info["path"] == file_path:
                return file_info
        return None
