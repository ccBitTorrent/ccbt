"""Xorb serialization (upstream Xet format).

A xorb is a bare sequence of chunks. Each chunk is an 8-byte header
(version u8 = 0, compressed size u24 LE, compression type u8,
uncompressed size u24 LE) followed by the payload. Compression types:
0 = None, 1 = LZ4 frame, 2 = ByteGrouping4 + LZ4 frame. There is no
container header, no stored chunk hashes, and no footer. A xorb holds
at most 8192 chunks and writers cut at about 64 MiB uncompressed.
Xorb identity is the aggregated Merkle root over (chunk_hash, size).
"""

from __future__ import annotations

import logging
from typing import Optional

from ccbt.storage.xet_hashing import XetHasher

try:
    import lz4.frame

    HAS_LZ4 = True
except ImportError:  # pragma: no cover
    HAS_LZ4 = False
    lz4 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

MAX_XORB_SIZE = 64 * 1024 * 1024
MAX_XORB_CHUNKS = 8192
CHUNK_HEADER_SIZE = 8

COMPRESSION_NONE = 0
COMPRESSION_LZ4 = 1
COMPRESSION_BG4_LZ4 = 2


def byte_grouping_4(data: bytes) -> bytes:
    """Reorder bytes into 4 position groups (upstream BG4)."""
    return b"".join(data[i::4] for i in range(4))


def byte_ungrouping_4(data: bytes, uncompressed_size: int) -> bytes:
    """Inverse of byte_grouping_4."""
    groups: list[bytes] = []
    offset = 0
    for i in range(4):
        group_len = (uncompressed_size - i + 3) // 4 if i < uncompressed_size else 0
        groups.append(data[offset : offset + group_len])
        offset += group_len
    out = bytearray(uncompressed_size)
    for i, group in enumerate(groups):
        out[i::4] = group
    return bytes(out)


def _compress_chunk(data: bytes) -> tuple[bytes, int]:
    """Pick the smallest encoding among None / LZ4 / BG4+LZ4."""
    best = (data, COMPRESSION_NONE)
    if HAS_LZ4 and lz4 is not None:
        try:
            lz = lz4.frame.compress(data)
            if len(lz) < len(best[0]):
                best = (lz, COMPRESSION_LZ4)
        except Exception:  # pragma: no cover - defensive
            logger.debug("LZ4 compression failed, storing raw", exc_info=True)
        try:
            bg = lz4.frame.compress(byte_grouping_4(data))
            if len(bg) < len(best[0]):
                best = (bg, COMPRESSION_BG4_LZ4)
        except Exception:  # pragma: no cover - defensive
            logger.debug("BG4 compression failed, storing raw", exc_info=True)
    return best


def _decompress_chunk(
    payload: bytes, compression: int, uncompressed_size: int
) -> bytes:
    if compression == COMPRESSION_NONE:
        out = payload
    elif compression in (COMPRESSION_LZ4, COMPRESSION_BG4_LZ4):
        if not HAS_LZ4 or lz4 is None:
            msg = "LZ4-compressed chunk but lz4 is not available"
            raise ValueError(msg)
        raw = lz4.frame.decompress(payload)
        out = (
            byte_ungrouping_4(raw, uncompressed_size)
            if compression == COMPRESSION_BG4_LZ4
            else raw
        )
    else:
        msg = f"Unknown xorb chunk compression type: {compression}"
        raise ValueError(msg)
    if len(out) != uncompressed_size:
        msg = f"chunk decompressed size mismatch: {len(out)} != {uncompressed_size}"
        raise ValueError(msg)
    return out


def encode_chunk_header(
    compressed_size: int, compression: int, uncompressed_size: int
) -> bytes:
    """Public function."""
    return (
        bytes([0])
        + compressed_size.to_bytes(3, "little")
        + bytes([compression])
        + uncompressed_size.to_bytes(3, "little")
    )


def decode_chunk_header(data: bytes, offset: int) -> tuple[int, int, int]:
    """Public function."""
    if len(data) < offset + CHUNK_HEADER_SIZE:
        msg = "xorb data too short for chunk header"
        raise ValueError(msg)
    version = data[offset]
    if version != 0:
        msg = f"unsupported xorb chunk version: {version}"
        raise ValueError(msg)
    compressed_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    compression = data[offset + 4]
    uncompressed_size = int.from_bytes(data[offset + 5 : offset + 8], "little")
    return compressed_size, compression, uncompressed_size


class Xorb:
    """A sequence of chunks in upstream xorb serialization."""

    def __init__(self) -> None:
        """Initialize instance."""
        self.chunks: list[tuple[bytes, bytes]] = []  # (hash, data)
        self.total_size = 0

    def add_chunk(self, chunk_hash: bytes, chunk_data: bytes) -> bool:
        """Public method."""
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)
        if len(self.chunks) >= MAX_XORB_CHUNKS:
            return False
        if self.total_size + len(chunk_data) > MAX_XORB_SIZE:
            return False
        self.chunks.append((chunk_hash, chunk_data))
        self.total_size += len(chunk_data)
        return True

    def serialize(self, compress: bool = False) -> bytes:
        """Public method."""
        out = bytearray()
        for _hash, data in self.chunks:
            if compress:
                payload, compression = _compress_chunk(data)
            else:
                payload, compression = data, COMPRESSION_NONE
            out += encode_chunk_header(len(payload), compression, len(data))
            out += payload
        return bytes(out)

    @staticmethod
    def chunk_byte_ranges(data: bytes) -> list[tuple[int, int]]:
        """Return [start, end) serialized byte ranges per chunk index."""
        ranges: list[tuple[int, int]] = []
        offset = 0
        while offset < len(data):
            compressed_size, _c, _u = decode_chunk_header(data, offset)
            end = offset + CHUNK_HEADER_SIZE + compressed_size
            if end > len(data):
                msg = "xorb chunk payload truncated"
                raise ValueError(msg)
            ranges.append((offset, end))
            offset = end
        return ranges

    @staticmethod
    def read_chunk(data: bytes, index: int) -> bytes:
        """Public method."""
        ranges = Xorb.chunk_byte_ranges(data)
        if index < 0 or index >= len(ranges):
            msg = f"xorb chunk index out of range: {index}"
            raise ValueError(msg)
        start, _end = ranges[index]
        compressed_size, compression, uncompressed_size = decode_chunk_header(
            data, start
        )
        payload = data[
            start + CHUNK_HEADER_SIZE : start + CHUNK_HEADER_SIZE + compressed_size
        ]
        return _decompress_chunk(payload, compression, uncompressed_size)

    @staticmethod
    def read_chunk_range(data: bytes, start_index: int, end_index: int) -> bytes:
        """Public method."""
        return b"".join(Xorb.read_chunk(data, i) for i in range(start_index, end_index))

    @staticmethod
    def deserialize(data: bytes) -> Xorb:
        """Public method."""
        xorb = Xorb()
        offset = 0
        while offset < len(data):
            compressed_size, compression, uncompressed_size = decode_chunk_header(
                data, offset
            )
            offset += CHUNK_HEADER_SIZE
            if len(data) < offset + compressed_size:
                msg = "xorb data too short for chunk payload"
                raise ValueError(msg)
            payload = data[offset : offset + compressed_size]
            offset += compressed_size
            chunk_data = _decompress_chunk(payload, compression, uncompressed_size)
            xorb.add_chunk(XetHasher.compute_chunk_hash(chunk_data), chunk_data)
        return xorb

    def get_chunk_by_hash(self, chunk_hash: bytes) -> Optional[bytes]:
        """Public method."""
        for h, data in self.chunks:
            if h == chunk_hash:
                return data
        return None

    def get_chunk_count(self) -> int:
        """Public method."""
        return len(self.chunks)

    def get_total_size(self) -> int:
        """Public method."""
        return self.total_size

    def is_full(self) -> bool:
        """Public method."""
        return self.total_size >= MAX_XORB_SIZE or len(self.chunks) >= MAX_XORB_CHUNKS

    def clear(self) -> None:
        """Public method."""
        self.chunks.clear()
        self.total_size = 0

    def get_xorb_hash(self) -> bytes:
        """Public method."""
        return XetHasher.compute_xorb_hash([(h, len(data)) for h, data in self.chunks])

    def get_compressed_size(self, compress: bool = True) -> int:
        """Public method."""
        return len(self.serialize(compress=compress))

    def get_compression_ratio(self) -> float:
        """Public method."""
        uncompressed = len(self.serialize(compress=False))
        if uncompressed == 0:
            return 1.0
        return len(self.serialize(compress=True)) / uncompressed
