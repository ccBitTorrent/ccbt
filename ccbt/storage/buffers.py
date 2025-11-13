"""High-performance buffer management for ccBitTorrent.

from __future__ import annotations

Provides ring buffers, memory pools, and zero-copy operations for optimal
memory usage and performance in network I/O and message processing.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from ccbt.utils.logging_config import get_logger


@dataclass
class BufferStats:
    """Statistics for buffer operations."""

    total_allocations: int = 0
    total_deallocations: int = 0
    peak_usage: int = 0
    current_usage: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


class RingBuffer:
    """High-performance ring buffer for zero-copy operations."""

    def __init__(self, size: int, alignment: int = 1) -> None:
        """Initialize ring buffer.

        Args:
            size: Buffer size in bytes
            alignment: Memory alignment requirement

        """
        self.size = size
        self.alignment = alignment
        self.buffer = bytearray(size)
        self.read_pos = 0
        self.write_pos = 0
        self.used = 0
        self.lock = threading.RLock()
        self.logger = get_logger(__name__)

    def write(self, data: bytes) -> int:
        """Write data to ring buffer.

        Args:
            data: Data to write

        Returns:
            Number of bytes written

        """
        with self.lock:
            if not data:
                return 0

            available = self.size - self.used
            to_write = min(len(data), available)

            if to_write == 0:
                return 0

            # Write data in one or two chunks
            first_chunk = min(to_write, self.size - self.write_pos)
            second_chunk = to_write - first_chunk

            # First chunk
            self.buffer[self.write_pos : self.write_pos + first_chunk] = data[
                :first_chunk
            ]

            # Second chunk (if buffer wraps around)
            if second_chunk > 0:
                self.buffer[:second_chunk] = data[
                    first_chunk : first_chunk + second_chunk
                ]
                self.write_pos = second_chunk
            else:
                self.write_pos = (self.write_pos + first_chunk) % self.size

            self.used += to_write
            return to_write

    def read(self, size: int) -> bytes:
        """Read data from ring buffer.

        Args:
            size: Number of bytes to read

        Returns:
            Data read from buffer

        """
        with self.lock:
            if self.used == 0 or size == 0:
                return b""

            to_read = min(size, self.used)
            result = bytearray(to_read)

            # Read data in one or two chunks
            first_chunk = min(to_read, self.size - self.read_pos)
            second_chunk = to_read - first_chunk

            # First chunk
            result[:first_chunk] = self.buffer[
                self.read_pos : self.read_pos + first_chunk
            ]

            # Second chunk (if buffer wraps around)
            if second_chunk > 0:
                result[first_chunk:] = self.buffer[:second_chunk]
                self.read_pos = second_chunk
            else:
                self.read_pos = (self.read_pos + first_chunk) % self.size

            self.used -= to_read
            return bytes(result)

    def peek_views(self, size: int | None = None) -> list[memoryview]:
        """Return up to two memoryviews representing current readable data without consuming it.

        Args:
            size: Optional maximum bytes to peek; defaults to all available.

        Returns:
            List of 1-2 memoryviews into the internal buffer.

        """
        with self.lock:
            if self.used == 0:
                return []
            to_read = self.used if size is None else min(size, self.used)
            first_chunk = min(to_read, self.size - self.read_pos)
            second_chunk = to_read - first_chunk
            views: list[memoryview] = []
            if first_chunk > 0:
                views.append(
                    memoryview(self.buffer)[
                        self.read_pos : self.read_pos + first_chunk
                    ],
                )
            if second_chunk > 0:
                views.append(memoryview(self.buffer)[:second_chunk])
            return views

    def consume(self, size: int) -> int:
        """Consume bytes from the buffer without returning them.

        Returns:
            Number of bytes actually consumed.

        """
        with self.lock:
            if size <= 0 or self.used == 0:
                return 0
            to_consume = min(size, self.used)
            first_chunk = min(to_consume, self.size - self.read_pos)
            second_chunk = to_consume - first_chunk
            # Advance read pointer accounting for wrap
            if second_chunk > 0:
                self.read_pos = second_chunk
            else:
                self.read_pos = (self.read_pos + first_chunk) % self.size
            self.used -= to_consume
            return to_consume

    def peek(self, size: int) -> bytes:
        """Peek at data without consuming it.

        Args:
            size: Number of bytes to peek

        Returns:
            Data at current read position

        """
        with self.lock:
            if self.used == 0 or size == 0:
                return b""

            to_read = min(size, self.used)
            result = bytearray(to_read)

            # Read data in one or two chunks
            first_chunk = min(to_read, self.size - self.read_pos)
            second_chunk = to_read - first_chunk

            # First chunk
            result[:first_chunk] = self.buffer[
                self.read_pos : self.read_pos + first_chunk
            ]

            # Second chunk (if buffer wraps around)
            if second_chunk > 0:
                result[first_chunk:] = self.buffer[:second_chunk]

            return bytes(result)

    def available(self) -> int:
        """Get available space in buffer."""
        with self.lock:
            return self.size - self.used

    def used_space(self) -> int:
        """Get used space in buffer."""
        with self.lock:
            return self.used

    def clear(self) -> None:
        """Clear the buffer."""
        with self.lock:
            self.read_pos = 0
            self.write_pos = 0
            self.used = 0


class MemoryPool:
    """Memory pool for efficient allocation/deallocation."""

    def __init__(
        self,
        size: int,
        count: int,
        factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialize memory pool.

        Args:
            size: Size of each object
            count: Number of objects in pool
            factory: Factory function to create objects

        """
        self.size = size
        self.count = count
        self.factory = factory or (lambda: bytearray(size))
        self.pool = deque()
        self.stats = BufferStats()
        self.lock = threading.Lock()
        self.logger = get_logger(__name__)

        # Pre-allocate objects
        for _ in range(count):
            self.pool.append(self.factory())
            self.stats.total_allocations += 1

    def get(self) -> Any:
        """Get an object from the pool."""
        with self.lock:
            if self.pool:
                obj = self.pool.popleft()
                self.stats.cache_hits += 1
                self.stats.current_usage += 1
                self.stats.peak_usage = max(
                    self.stats.peak_usage,
                    self.stats.current_usage,
                )
                return obj
            # Pool exhausted, create new object
            obj = self.factory()
            self.stats.cache_misses += 1
            self.stats.total_allocations += 1
            self.stats.current_usage += 1
            self.stats.peak_usage = max(self.stats.peak_usage, self.stats.current_usage)
            return obj

    def put(self, obj: Any) -> None:
        """Return an object to the pool."""
        with self.lock:
            if len(self.pool) < self.count:
                # Reset object state
                if hasattr(obj, "clear") and not isinstance(obj, bytearray):
                    # Use clear() for non-bytearray objects
                    obj.clear()
                elif isinstance(obj, bytearray):
                    # For bytearray, reset to original size filled with zeros
                    obj[:] = b"\x00" * len(obj)
                self.pool.append(obj)
                self.stats.current_usage -= 1
                self.stats.total_deallocations += 1
            else:
                # Pool full, discard object
                self.stats.current_usage -= 1
                self.stats.total_deallocations += 1

    def get_stats(self) -> BufferStats:
        """Get pool statistics."""
        with self.lock:
            return BufferStats(
                total_allocations=self.stats.total_allocations,
                total_deallocations=self.stats.total_deallocations,
                peak_usage=self.stats.peak_usage,
                current_usage=self.stats.current_usage,
                cache_hits=self.stats.cache_hits,
                cache_misses=self.stats.cache_misses,
            )


class ZeroCopyBuffer:
    """Zero-copy buffer for efficient data handling."""

    def __init__(self, size: int) -> None:
        """Initialize zero-copy buffer.

        Args:
            size: Buffer size in bytes

        """
        self.size = size
        self.buffer = bytearray(size)
        self.view = memoryview(self.buffer)
        self.pos = 0
        self.lock = threading.Lock()
        self.logger = get_logger(__name__)

    def write(self, data: bytes | memoryview) -> int:
        """Write data to buffer with zero-copy when possible.

        Args:
            data: Data to write

        Returns:
            Number of bytes written

        """
        with self.lock:
            if not data:
                return 0

            available = self.size - self.pos
            to_write = min(len(data), available)

            if to_write == 0:
                return 0

            # Use memoryview for zero-copy operation
            if isinstance(data, memoryview):
                self.view[self.pos : self.pos + to_write] = data[:to_write]
            else:
                self.buffer[self.pos : self.pos + to_write] = data[:to_write]

            self.pos += to_write
            return to_write

    def read(self, size: int) -> memoryview:
        """Read data from buffer as memoryview for zero-copy.

        Args:
            size: Number of bytes to read

        Returns:
            Memoryview of the data

        """
        with self.lock:
            if size == 0 or self.pos == 0:
                return memoryview(b"")

            to_read = min(size, self.pos)
            result = self.view[:to_read]
            self.pos -= to_read

            # Shift remaining data
            if self.pos > 0:
                self.buffer[: self.pos] = self.buffer[to_read : to_read + self.pos]

            return result

    def peek(self, size: int) -> memoryview:
        """Peek at data without consuming it.

        Args:
            size: Number of bytes to peek

        Returns:
            Memoryview of the data

        """
        with self.lock:
            if size == 0 or self.pos == 0:
                return memoryview(b"")

            to_read = min(size, self.pos)
            return self.view[:to_read]

    def available(self) -> int:
        """Get available space in buffer."""
        with self.lock:
            return self.size - self.pos

    def used_space(self) -> int:
        """Get used space in buffer."""
        with self.lock:
            return self.pos

    def clear(self) -> None:
        """Clear the buffer."""
        with self.lock:
            self.pos = 0


class BufferManager:
    """Manages multiple buffers and memory pools."""

    def __init__(self) -> None:
        """Initialize buffer manager."""
        self.ring_buffers: list[RingBuffer] = []
        self.memory_pools: list[MemoryPool] = []
        self.zero_copy_buffers: list[ZeroCopyBuffer] = []
        self.lock = threading.Lock()
        self.logger = get_logger(__name__)

    def create_ring_buffer(self, size: int, alignment: int = 1) -> RingBuffer:
        """Create a new ring buffer."""
        with self.lock:
            buffer = RingBuffer(size, alignment)
            self.ring_buffers.append(buffer)
            return buffer

    def create_memory_pool(
        self,
        size: int,
        count: int,
        factory: Callable[[], Any] | None = None,
    ) -> MemoryPool:
        """Create a new memory pool."""
        with self.lock:
            pool = MemoryPool(size, count, factory)
            self.memory_pools.append(pool)
            return pool

    def create_zero_copy_buffer(self, size: int) -> ZeroCopyBuffer:
        """Create a new zero-copy buffer."""
        with self.lock:
            buffer = ZeroCopyBuffer(size)
            self.zero_copy_buffers.append(buffer)
            return buffer

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for all buffers."""
        with self.lock:
            return {
                "ring_buffers": len(self.ring_buffers),
                "memory_pools": len(self.memory_pools),
                "zero_copy_buffers": len(self.zero_copy_buffers),
                "pool_stats": [pool.get_stats() for pool in self.memory_pools],
            }


# Global buffer manager instance
_buffer_manager: BufferManager | None = None


def get_buffer_manager() -> BufferManager:
    """Get the global buffer manager."""
    global _buffer_manager
    if _buffer_manager is None:
        _buffer_manager = BufferManager()
    return _buffer_manager
