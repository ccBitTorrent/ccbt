"""XET-specific bloom filter wrapper for chunk availability.

Provides XET chunk-specific bloom filter operations including
peer bloom exchange and merging.
"""

from __future__ import annotations

import logging
from typing import Any

from ccbt.discovery.bloom_filter import BloomFilter

logger = logging.getLogger(__name__)


class XetChunkBloomFilter:
    """Bloom filter wrapper for XET chunk availability.

    Provides chunk-specific operations on top of generic BloomFilter.

    Attributes:
        bloom_filter: Underlying bloom filter
        chunk_size: Expected number of chunks (for false positive calculation)

    """

    def __init__(
        self,
        size: int = 1024 * 8,  # 1KB default
        hash_count: int = 3,
        chunk_size: int = 1000,
        bloom_filter: BloomFilter | None = None,
    ):
        """Initialize XET chunk bloom filter.

        Args:
            size: Size of bit array in bits
            hash_count: Number of hash functions
            chunk_size: Expected number of chunks (for optimization)
            bloom_filter: Existing bloom filter to wrap

        """
        if bloom_filter:
            self.bloom_filter = bloom_filter
        else:
            self.bloom_filter = BloomFilter(size=size, hash_count=hash_count)

        self.chunk_size = chunk_size

    def add_chunk(self, chunk_hash: bytes) -> None:
        """Add chunk hash to bloom filter.

        Args:
            chunk_hash: 32-byte chunk hash

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        self.bloom_filter.add(chunk_hash)

    def has_chunk(self, chunk_hash: bytes) -> bool:
        """Check if chunk hash might be in bloom filter.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            True if chunk might be available (may have false positives),
            False if chunk is definitely not available

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        return self.bloom_filter.contains(chunk_hash)

    def get_peer_bloom(self) -> bytes:
        """Get serialized bloom filter for peer exchange.

        Returns:
            Serialized bloom filter bytes

        """
        return self.bloom_filter.serialize()

    @classmethod
    def from_peer_bloom(cls, data: bytes, chunk_size: int = 1000) -> XetChunkBloomFilter:
        """Create bloom filter from peer's serialized data.

        Args:
            data: Serialized bloom filter data from peer
            chunk_size: Expected number of chunks

        Returns:
            XetChunkBloomFilter instance

        """
        bloom_filter = BloomFilter.deserialize(data)
        return cls(bloom_filter=bloom_filter, chunk_size=chunk_size)

    def merge_peer_blooms(self, peer_blooms: list[bytes]) -> XetChunkBloomFilter:
        """Merge multiple peer bloom filters.

        Args:
            peer_blooms: List of serialized bloom filters from peers

        Returns:
            New merged bloom filter

        """
        if not peer_blooms:
            return XetChunkBloomFilter(
                bloom_filter=BloomFilter(
                    size=self.bloom_filter.size,
                    hash_count=self.bloom_filter.hash_count,
                ),
                chunk_size=self.chunk_size,
            )

        # Deserialize first peer bloom
        merged = BloomFilter.deserialize(peer_blooms[0])

        # Union with remaining peer blooms
        for peer_bloom_data in peer_blooms[1:]:
            peer_bloom = BloomFilter.deserialize(peer_bloom_data)
            merged = merged.union(peer_bloom)

        return XetChunkBloomFilter(bloom_filter=merged, chunk_size=self.chunk_size)

    def get_false_positive_rate(self) -> float:
        """Get false positive rate for current chunk count.

        Returns:
            False positive probability (0.0 to 1.0)

        """
        return self.bloom_filter.false_positive_rate(self.chunk_size)

    def __len__(self) -> int:
        """Return number of chunks in filter."""
        return len(self.bloom_filter)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"XetChunkBloomFilter(chunks={len(self)}, fpr={self.get_false_positive_rate():.4f})"



