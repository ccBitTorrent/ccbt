"""Bloom filter implementation for efficient set membership testing.

Provides space-efficient probabilistic data structure for testing whether
an element is a member of a set. False positives are possible, but false
negatives are not.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from typing import Any

logger = logging.getLogger(__name__)


def _murmur_hash3_32(data: bytes, seed: int = 0) -> int:
    """Compute MurmurHash3 32-bit hash.

    Args:
        data: Data to hash
        seed: Hash seed

    Returns:
        32-bit hash value

    """
    # Simplified MurmurHash3 implementation
    # For production, consider using mmh3 library: pip install mmh3
    c1 = 0xCC9E2D51
    c2 = 0x1B873593
    length = len(data)
    h1 = seed

    # Process 4-byte chunks
    for i in range(0, length - 3, 4):
        k1 = struct.unpack("<I", data[i : i + 4])[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    # Handle remaining bytes
    tail = data[length - (length % 4) :]
    k1 = 0
    if len(tail) >= 3:
        k1 ^= tail[2] << 16
    if len(tail) >= 2:
        k1 ^= tail[1] << 8
    if len(tail) >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    # Finalize
    h1 ^= length
    h1 ^= h1 >> 16
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= h1 >> 16

    return h1 & 0xFFFFFFFF


class BloomFilter:
    """Bloom filter for efficient set membership testing.

    Attributes:
        bit_array: Bit array for storing filter data
        size: Size of bit array in bits
        hash_count: Number of hash functions to use
        count: Number of elements added to filter

    """

    def __init__(
        self,
        size: int = 1024 * 8,  # 1KB default
        hash_count: int = 3,
        bit_array: bytearray | None = None,
    ):
        """Initialize bloom filter.

        Args:
            size: Size of bit array in bits (must be power of 2 or multiple of 8)
            hash_count: Number of hash functions to use (default 3)
            bit_array: Existing bit array to use (for deserialization)

        """
        if size < 8:
            msg = "Bloom filter size must be at least 8 bits"
            raise ValueError(msg)
        if hash_count < 1:
            msg = "Hash count must be at least 1"
            raise ValueError(msg)

        self.size = size
        self.hash_count = hash_count
        self.count = 0

        if bit_array:
            if len(bit_array) * 8 != size:
                msg = f"Bit array size mismatch: expected {size} bits, got {len(bit_array) * 8}"
                raise ValueError(msg)
            self.bit_array = bit_array
        else:
            # Initialize bit array (size in bytes)
            self.bit_array = bytearray(size // 8)

    def _hash_functions(self, data: bytes) -> list[int]:
        """Compute hash values for data using multiple hash functions.

        Args:
            data: Data to hash

        Returns:
            List of hash values (one per hash function)

        """
        hashes = []

        # Use different hash functions/seeds
        for i in range(self.hash_count):
            # Method 1: MurmurHash3 with different seeds
            hash1 = _murmur_hash3_32(data, seed=i)

            # Method 2: SHA-256 with different prefixes
            hasher = hashlib.sha256()
            hasher.update(struct.pack("!I", i))
            hasher.update(data)
            hash2 = int.from_bytes(hasher.digest()[:4], byteorder="big")

            # Combine hashes
            combined = (hash1 ^ hash2) & 0xFFFFFFFF
            hashes.append(combined)

        return hashes

    def add(self, item: bytes) -> None:
        """Add item to bloom filter.

        Args:
            item: Item to add (bytes)

        """
        hashes = self._hash_functions(item)

        for hash_value in hashes:
            bit_index = hash_value % self.size
            byte_index = bit_index // 8
            bit_offset = bit_index % 8

            # Set bit
            self.bit_array[byte_index] |= 1 << bit_offset

        self.count += 1

    def contains(self, item: bytes) -> bool:
        """Check if item is in bloom filter.

        Args:
            item: Item to check (bytes)

        Returns:
            True if item might be in filter (may have false positives),
            False if item is definitely not in filter

        """
        hashes = self._hash_functions(item)

        for hash_value in hashes:
            bit_index = hash_value % self.size
            byte_index = bit_index // 8
            bit_offset = bit_index % 8

            # Check if bit is set
            if not (self.bit_array[byte_index] & (1 << bit_offset)):
                return False

        return True

    def union(self, other: BloomFilter) -> BloomFilter:
        """Create union of two bloom filters.

        Args:
            other: Another bloom filter to union with

        Returns:
            New bloom filter containing union

        Raises:
            ValueError: If filters have different sizes or hash counts

        """
        if self.size != other.size:
            msg = "Cannot union bloom filters with different sizes"
            raise ValueError(msg)
        if self.hash_count != other.hash_count:
            msg = "Cannot union bloom filters with different hash counts"
            raise ValueError(msg)

        result = BloomFilter(size=self.size, hash_count=self.hash_count)
        result.bit_array = bytearray(self.bit_array)

        # OR the bit arrays
        for i in range(len(result.bit_array)):
            result.bit_array[i] |= other.bit_array[i]

        # Approximate count (may be overestimated)
        result.count = max(self.count, other.count)

        return result

    def intersection(self, other: BloomFilter) -> BloomFilter:
        """Create intersection of two bloom filters.

        Args:
            other: Another bloom filter to intersect with

        Returns:
            New bloom filter containing intersection

        Raises:
            ValueError: If filters have different sizes or hash counts

        """
        if self.size != other.size:
            msg = "Cannot intersect bloom filters with different sizes"
            raise ValueError(msg)
        if self.hash_count != other.hash_count:
            msg = "Cannot intersect bloom filters with different hash counts"
            raise ValueError(msg)

        result = BloomFilter(size=self.size, hash_count=self.hash_count)
        result.bit_array = bytearray(self.bit_array)

        # AND the bit arrays
        for i in range(len(result.bit_array)):
            result.bit_array[i] &= other.bit_array[i]

        # Approximate count (may be underestimated)
        result.count = min(self.count, other.count)

        return result

    def false_positive_rate(self, expected_items: int | None = None) -> float:
        """Calculate false positive rate.

        Args:
            expected_items: Expected number of items (uses self.count if None)

        Returns:
            False positive probability (0.0 to 1.0)

        """
        n = expected_items if expected_items is not None else self.count
        if n == 0:
            return 0.0

        # Formula: (1 - e^(-k*n/m))^k
        # where k = hash_count, n = items, m = size
        import math

        m = self.size
        k = self.hash_count

        return (1 - math.exp(-k * n / m)) ** k

    def serialize(self) -> bytes:
        """Serialize bloom filter to bytes.

        Returns:
            Serialized bloom filter data

        """
        # Format: <size (4 bytes)><hash_count (1 byte)><count (4 bytes)><bit_array>
        return (
            struct.pack("!IBI", self.size, self.hash_count, self.count)
            + bytes(self.bit_array)
        )

    @classmethod
    def deserialize(cls, data: bytes) -> BloomFilter:
        """Deserialize bloom filter from bytes.

        Args:
            data: Serialized bloom filter data

        Returns:
            BloomFilter instance

        Raises:
            ValueError: If data is invalid

        """
        if len(data) < 9:
            msg = "Invalid bloom filter data: too short"
            raise ValueError(msg)

        size, hash_count, count = struct.unpack("!IBI", data[:9])
        bit_array_data = data[9:]

        if len(bit_array_data) * 8 != size:
            msg = f"Invalid bloom filter data: size mismatch (expected {size} bits, got {len(bit_array_data) * 8})"
            raise ValueError(msg)

        filter_obj = cls(size=size, hash_count=hash_count, bit_array=bytearray(bit_array_data))
        filter_obj.count = count

        return filter_obj

    def __len__(self) -> int:
        """Return number of items added to filter."""
        return self.count

    def __repr__(self) -> str:
        """Return string representation."""
        return f"BloomFilter(size={self.size}, hash_count={self.hash_count}, count={self.count})"



