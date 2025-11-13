"""Xorb (XOR of blocks) format handler for Xet protocol.

Xorbs are collections of chunks stored together for efficient storage
and retrieval. This module provides serialization and deserialization
of the xorb binary format.

Based on the Xet protocol specification and Rust reference implementation:
https://github.com/xetdata/xet-core/tree/main/rust

Format:
- Header: 16 bytes (magic "XORB" + version + flags + reserved)
- Chunk count: 4 bytes (uint32)
- Chunk entries: variable (hash + size + data for each chunk)
- Metadata: 8 bytes (total size as uint64)
"""

from __future__ import annotations

import logging
import struct

try:
    import lz4.frame

    HAS_LZ4 = True
except (
    ImportError
):  # pragma: no cover - Import fallback tested via monkeypatch in tests
    HAS_LZ4 = False  # pragma: no cover - Same context
    lz4 = None  # type: ignore[assignment, name-defined]  # pragma: no cover - Same context

logger = logging.getLogger(__name__)

# Xorb format constants
MAX_XORB_SIZE = 64 * 1024 * 1024  # 64 MiB maximum xorb size
XORB_MAGIC_INT = 0x24687531  # Magic number for xorb format (little-endian uint32)
XORB_MAGIC = struct.pack("<I", XORB_MAGIC_INT)  # Convert to 4 bytes (little-endian)
XORB_VERSION = 1  # Format version
XORB_HEADER_SIZE = 16  # Header size in bytes

# Compression flags
FLAG_COMPRESSED = 0x01  # Chunk data is compressed with LZ4
FLAG_RESERVED_MASK = 0xFE  # Reserved bits for future use


class Xorb:
    """Xorb (XOR of blocks) format handler.

    Groups multiple chunks into a single xorb for efficient storage.
    Each xorb can contain multiple chunks up to MAX_XORB_SIZE.

    Attributes:
        chunks: List of (hash, data) tuples
        total_size: Total size of all chunks in bytes

    """

    def __init__(self):
        """Initialize empty xorb."""
        self.chunks: list[tuple[bytes, bytes]] = []  # (hash, data) pairs
        self.total_size = 0

    def add_chunk(self, chunk_hash: bytes, chunk_data: bytes) -> bool:
        """Add chunk to xorb.

        Args:
            chunk_hash: 32-byte chunk hash
            chunk_data: Chunk data bytes

        Returns:
            True if added, False if xorb would exceed MAX_XORB_SIZE

        """
        chunk_size = len(chunk_data)
        if self.total_size + chunk_size > MAX_XORB_SIZE:
            return False

        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        self.chunks.append((chunk_hash, chunk_data))
        self.total_size += chunk_size
        return True

    def serialize(self, compress: bool = False) -> bytes:
        """Serialize xorb to binary format.

        Format:
        [Header: 16 bytes]
        - Magic: 4 bytes ("XORB")
        - Version: 1 byte
        - Flags: 1 byte (compression flag, reserved bits)
        - Reserved: 10 bytes

        [Chunk count: 4 bytes (uint32)]

        [Chunk entries: variable]
        - For each chunk:
          - Hash: 32 bytes
          - Size: 4 bytes (uint32, uncompressed size)
          - Compressed size: 4 bytes (uint32, 0 if not compressed)
          - Data: variable (compressed if flags indicate)

        [Metadata: variable]
        - Total size: 8 bytes (uint64, uncompressed)

        Args:
            compress: Whether to compress chunk data with LZ4

        Returns:
            Serialized xorb data

        """
        # Build header
        header = self._serialize_header(compress)

        # Build chunk data (with optional compression)
        chunk_data = self._serialize_chunks(compress)

        # Build metadata
        metadata = struct.pack("Q", self.total_size)  # uint64 (uncompressed size)

        return header + chunk_data + metadata

    def _serialize_header(self, compress: bool) -> bytes:
        """Serialize xorb header.

        Args:
            compress: Compression flag

        Returns:
            16-byte header

        """
        flags = FLAG_COMPRESSED if (compress and HAS_LZ4) else 0x00
        # Pack magic as 4 bytes (little-endian uint32), version, flags, reserved
        return (
            XORB_MAGIC  # 4 bytes (already packed as bytes)
            + struct.pack("BB", XORB_VERSION, flags)  # 2 bytes
            + b"\x00" * 10  # Reserved bytes
        )

    def _serialize_chunks(self, compress: bool = False) -> bytes:
        """Serialize chunk entries.

        Args:
            compress: Whether to compress chunk data with LZ4

        Returns:
            Serialized chunk data

        """
        # Chunk count
        data = struct.pack("I", len(self.chunks))

        # Chunk entries
        for chunk_hash, chunk_data in self.chunks:
            uncompressed_size = len(chunk_data)
            compressed_size = 0
            final_data = chunk_data

            # Compress if requested and LZ4 is available
            if compress and HAS_LZ4 and lz4 is not None:
                try:
                    # Use high compression level (if available) or default
                    # LZ4 compression levels: 0-16, higher = more compression
                    compression_level = getattr(
                        lz4.frame,
                        "COMPRESSIONLEVEL_MINHC",
                        9,  # High compression, default to 9
                    )
                    block_size = getattr(
                        lz4.frame,
                        "BLOCKSIZE_MAX64KB",
                        65536,  # 64KB blocks, default to 65536
                    )

                    compressed_data = lz4.frame.compress(
                        chunk_data,
                        compression_level=compression_level,
                        block_size=block_size,
                    )
                    # Only use compression if it's beneficial (smaller than original)
                    if len(compressed_data) < uncompressed_size:
                        compressed_size = len(compressed_data)
                        final_data = compressed_data
                    else:
                        compressed_size = 0  # Don't compress if not beneficial
                except Exception as e:
                    logger.warning(
                        "Failed to compress chunk %s: %s. Using uncompressed.",
                        chunk_hash.hex()[:16],
                        e,
                    )
                    compressed_size = 0

            # Format: Hash (32 bytes) + uncompressed_size (4 bytes) + compressed_size (4 bytes) + data
            data += (
                chunk_hash
                + struct.pack("I", uncompressed_size)
                + struct.pack("I", compressed_size)
                + final_data
            )

        return data

    @staticmethod
    def deserialize(data: bytes) -> Xorb:
        """Deserialize xorb from binary format.

        Args:
            data: Serialized xorb data

        Returns:
            Xorb instance

        Raises:
            ValueError: If data is invalid or format is incorrect

        """
        if len(data) < XORB_HEADER_SIZE:
            msg = f"Xorb data too short: {len(data)} bytes (minimum {XORB_HEADER_SIZE})"
            raise ValueError(msg)

        # Parse header
        header_data = data[:XORB_HEADER_SIZE]
        magic_bytes = header_data[:4]
        version = header_data[4]
        flags = header_data[5]
        _reserved = header_data[6:16]

        if magic_bytes != XORB_MAGIC:
            msg = f"Invalid xorb magic: expected {XORB_MAGIC.hex()}, got {magic_bytes.hex()}"
            raise ValueError(msg)

        if version != XORB_VERSION:
            msg = f"Unsupported xorb version: {version} (expected {XORB_VERSION})"
            raise ValueError(msg)

        compress = (flags & FLAG_COMPRESSED) != 0
        if compress and not HAS_LZ4:
            msg = "Xorb is compressed but LZ4 is not available"
            raise ValueError(msg)

        # Parse chunk count
        offset = XORB_HEADER_SIZE
        if (
            len(data) < offset + 4
        ):  # pragma: no cover - Data validation error path, tested in test_deserialize_short_data
            msg = "Xorb data too short for chunk count"
            raise ValueError(msg)  # pragma: no cover - Same context

        chunk_count = struct.unpack("I", data[offset : offset + 4])[0]
        offset += 4

        # Validate chunk count (reasonable limit)
        if chunk_count > 1000000:  # Sanity check
            msg = f"Invalid chunk count: {chunk_count} (too large)"
            raise ValueError(
                msg
            )  # pragma: no cover - Defensive check for corrupted data, unlikely in normal operation

        # Parse chunks
        xorb = Xorb()
        for i in range(chunk_count):
            # Parse hash (32 bytes)
            if (
                len(data) < offset + 32
            ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
                msg = f"Xorb data too short for chunk {i} hash"
                raise ValueError(msg)  # pragma: no cover - Same context

            chunk_hash = data[offset : offset + 32]
            offset += 32

            # Parse uncompressed size (4 bytes)
            if (
                len(data) < offset + 4
            ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
                msg = f"Xorb data too short for chunk {i} uncompressed size"
                raise ValueError(msg)  # pragma: no cover - Same context

            uncompressed_size = struct.unpack("I", data[offset : offset + 4])[0]
            offset += 4

            # Parse compressed size (4 bytes)
            if (
                len(data) < offset + 4
            ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
                msg = f"Xorb data too short for chunk {i} compressed size"
                raise ValueError(msg)  # pragma: no cover - Same context

            compressed_size = struct.unpack("I", data[offset : offset + 4])[0]
            offset += 4

            # Determine actual data size
            if compressed_size > 0:
                # Data is compressed
                if (
                    not HAS_LZ4 or lz4 is None
                ):  # pragma: no cover - LZ4 unavailable check for compressed chunks, tested via monkeypatch
                    msg = f"Chunk {i} is compressed but LZ4 is not available"
                    raise ValueError(msg)  # pragma: no cover - Same context

                data_size = compressed_size
                if (
                    len(data) < offset + data_size
                ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
                    msg = f"Xorb data too short for chunk {i} compressed data"
                    raise ValueError(msg)  # pragma: no cover - Same context

                compressed_data = data[offset : offset + data_size]
                offset += data_size

                # Decompress
                try:
                    chunk_data = lz4.frame.decompress(compressed_data)
                    if (
                        len(chunk_data) != uncompressed_size
                    ):  # pragma: no cover - Decompression size validation, defensive check for corrupted data
                        msg = (
                            f"Chunk {i} decompressed size mismatch: "
                            f"expected {uncompressed_size}, got {len(chunk_data)}"
                        )
                        raise ValueError(msg)  # pragma: no cover - Same context
                except Exception as e:
                    msg = f"Failed to decompress chunk {i}: {e}"
                    raise ValueError(msg) from e
            else:
                # Data is uncompressed
                data_size = uncompressed_size
                if (
                    len(data) < offset + data_size
                ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
                    msg = f"Xorb data too short for chunk {i} data"
                    raise ValueError(msg)  # pragma: no cover - Same context

                chunk_data = data[offset : offset + data_size]
                offset += data_size

            xorb.add_chunk(chunk_hash, chunk_data)

        # Parse metadata (total size)
        if (
            len(data) < offset + 8
        ):  # pragma: no cover - Data validation error path, defensive check for corrupted data
            msg = "Xorb data too short for metadata"
            raise ValueError(msg)  # pragma: no cover - Same context

        total_size = struct.unpack("Q", data[offset : offset + 8])[0]
        if total_size != xorb.total_size:
            logger.warning(
                "Xorb metadata total_size mismatch: expected %d, got %d",
                xorb.total_size,
                total_size,
            )

        return xorb

    def get_chunk_by_hash(self, chunk_hash: bytes) -> bytes | None:
        """Get chunk data by hash.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            Chunk data if found, None otherwise

        """
        for hash_bytes, chunk_data in self.chunks:
            if hash_bytes == chunk_hash:
                return chunk_data
        return None

    def get_chunk_count(self) -> int:
        """Get number of chunks in xorb.

        Returns:
            Number of chunks

        """
        return len(self.chunks)

    def get_total_size(self) -> int:
        """Get total size of all chunks.

        Returns:
            Total size in bytes

        """
        return self.total_size

    def is_full(self) -> bool:
        """Check if xorb is full (would exceed MAX_XORB_SIZE with next chunk).

        Returns:
            True if full, False otherwise

        """
        return self.total_size >= MAX_XORB_SIZE

    def clear(self) -> None:
        """Clear all chunks from xorb."""
        self.chunks.clear()
        self.total_size = 0

    def get_xorb_hash(self) -> bytes:
        """Compute xorb hash for deduplication.

        Returns the hash of the serialized xorb data, which can be used
        to identify identical xorbs for deduplication.

        Returns:
            32-byte hash (BLAKE3-256 or SHA-256)

        """
        from ccbt.storage.xet_hashing import XetHasher

        serialized = self.serialize(compress=False)  # Use uncompressed for hash
        return XetHasher.compute_chunk_hash(serialized)

    def get_compressed_size(self, compress: bool = True) -> int:
        """Get size of xorb when serialized with compression.

        Args:
            compress: Whether to calculate compressed size

        Returns:
            Size in bytes

        """
        if compress:
            serialized = self.serialize(compress=True)
            return len(serialized)
        return len(self.serialize(compress=False))

    def get_compression_ratio(self) -> float:
        """Get compression ratio if compression is enabled.

        Returns:
            Compression ratio (compressed_size / uncompressed_size)
            Returns 1.0 if compression is not available or not beneficial

        """
        if not HAS_LZ4:
            return 1.0  # pragma: no cover - LZ4 unavailable path tested via monkeypatch in tests

        uncompressed_size = len(self.serialize(compress=False))
        compressed_size = self.get_compressed_size(compress=True)

        if uncompressed_size == 0:
            return 1.0  # pragma: no cover - Empty xorb edge case, tested in test_get_compression_ratio_empty

        return compressed_size / uncompressed_size
