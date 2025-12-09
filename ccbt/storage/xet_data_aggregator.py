"""Data aggregator for batch chunk operations in XET protocol.

This module provides efficient batch operations for chunk storage and retrieval,
optimizing I/O by batching multiple chunk operations together.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from ccbt.storage.xet_deduplication import XetDeduplication

logger = logging.getLogger(__name__)


class XetDataAggregator:
    """Data aggregator for batch chunk operations.

    Provides efficient batch operations for storing and reading chunks,
    optimizing I/O performance by batching multiple operations together.

    Attributes:
        dedup: XetDeduplication instance for chunk operations
        batch_size: Maximum number of chunks to process in a single batch
        logger: Logger instance

    """

    def __init__(
        self, dedup: XetDeduplication, batch_size: int = 100
    ):
        """Initialize data aggregator.

        Args:
            dedup: XetDeduplication instance for chunk operations
            batch_size: Maximum number of chunks to process in a single batch

        """
        self.dedup = dedup
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)

    async def aggregate_chunks(
        self, chunk_hashes: list[bytes]
    ) -> bytes:
        """Aggregate multiple chunks into a single byte stream.

        Reads multiple chunks in parallel and concatenates them.

        Args:
            chunk_hashes: List of chunk hashes to aggregate

        Returns:
            Concatenated chunk data as bytes

        """
        if not chunk_hashes:
            return b""

        # Read chunks in parallel
        chunk_data_list = await self.batch_read_chunks(chunk_hashes)

        # Concatenate in order
        result = b""
        for chunk_hash in chunk_hashes:
            chunk_data = chunk_data_list.get(chunk_hash)
            if chunk_data:
                result += chunk_data
            else:
                self.logger.warning(
                    "Missing chunk %s in aggregation",
                    chunk_hash.hex()[:16],
                )

        return result

    async def batch_store_chunks(
        self,
        chunks: list[tuple[bytes, bytes]],
        file_path: str | None = None,
        file_offsets: list[int] | None = None,
    ) -> list[Path]:
        """Store multiple chunks in a batch operation.

        Stores chunks in parallel for improved performance.

        Args:
            chunks: List of (chunk_hash, chunk_data) tuples
            file_path: Optional file path that references these chunks
            file_offsets: Optional list of offsets corresponding to chunks

        Returns:
            List of paths to stored chunks (in same order as input)

        """
        if not chunks:
            return []

        # Create tasks for parallel storage
        tasks = []
        for i, (chunk_hash, chunk_data) in enumerate(chunks):
            file_offset = file_offsets[i] if file_offsets and i < len(file_offsets) else None
            task = self.dedup.store_chunk(
                chunk_hash=chunk_hash,
                chunk_data=chunk_data,
                file_path=file_path,
                file_offset=file_offset,
            )
            tasks.append(task)

        # Execute in batches to avoid overwhelming the system
        results = []
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i : i + self.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)

        # Filter out exceptions and convert to paths
        paths = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning(
                    "Failed to store chunk in batch: %s", result
                )
                paths.append(Path())  # Placeholder for failed chunk
            else:
                paths.append(result)

        return paths

    async def batch_read_chunks(
        self, chunk_hashes: list[bytes]
    ) -> dict[bytes, bytes]:
        """Read multiple chunks in parallel.

        Reads chunks in parallel for improved performance.

        Args:
            chunk_hashes: List of chunk hashes to read

        Returns:
            Dictionary mapping chunk_hash to chunk_data

        """
        if not chunk_hashes:
            return {}

        # Create tasks for parallel reading
        tasks = []
        for chunk_hash in chunk_hashes:
            task = self._read_chunk_async(chunk_hash)
            tasks.append((chunk_hash, task))

        # Execute in batches
        results = {}
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i : i + self.batch_size]
            batch_hashes = [h for h, _ in batch]
            batch_tasks = [t for _, t in batch]

            batch_results = await asyncio.gather(
                *batch_tasks, return_exceptions=True
            )

            for chunk_hash, chunk_data in zip(batch_hashes, batch_results):
                if isinstance(chunk_data, Exception):
                    self.logger.warning(
                        "Failed to read chunk %s in batch: %s",
                        chunk_hash.hex()[:16],
                        chunk_data,
                    )
                    results[chunk_hash] = b""
                elif chunk_data:
                    results[chunk_hash] = chunk_data
                else:
                    results[chunk_hash] = b""

        return results

    async def _read_chunk_async(self, chunk_hash: bytes) -> bytes | None:
        """Read a single chunk asynchronously.

        Args:
            chunk_hash: Chunk hash to read

        Returns:
            Chunk data if found, None otherwise

        """
        try:
            chunk_path = await self.dedup.check_chunk_exists(chunk_hash)
            if not chunk_path or not chunk_path.exists():
                return None

            # Read chunk data in executor to avoid blocking
            loop = asyncio.get_event_loop()
            chunk_data = await loop.run_in_executor(
                None, chunk_path.read_bytes
            )
            return chunk_data
        except Exception as e:
            self.logger.debug(
                "Failed to read chunk %s: %s", chunk_hash.hex()[:16], e
            )
            return None

    async def optimize_storage_layout(
        self, chunk_hashes: list[bytes] | None = None
    ) -> dict[str, Any]:
        """Optimize storage layout for chunks.

        Reorganizes chunk storage to improve access patterns.
        This is a placeholder for future optimization logic.

        Args:
            chunk_hashes: Optional list of specific chunks to optimize

        Returns:
            Dictionary with optimization statistics

        """
        # Placeholder implementation
        # Future: Implement actual storage layout optimization
        self.logger.debug("Storage layout optimization not yet implemented")
        return {
            "chunks_optimized": 0,
            "storage_reorganized": 0,
            "access_improvement": 0.0,
        }





































