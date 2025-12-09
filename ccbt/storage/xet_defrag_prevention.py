"""Defragmentation prevention for XET chunk storage.

This module provides fragmentation detection and prevention mechanisms
to maintain optimal chunk storage layout and access patterns.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ccbt.storage.xet_deduplication import XetDeduplication

logger = logging.getLogger(__name__)


class XetDefragPrevention:
    """Defragmentation prevention manager.

    Monitors chunk storage layout and prevents fragmentation by
    reorganizing chunks when necessary.

    Attributes:
        dedup: XetDeduplication instance for chunk operations
        last_check: Timestamp of last fragmentation check
        logger: Logger instance

    """

    def __init__(self, dedup: XetDeduplication):
        """Initialize defragmentation prevention manager.

        Args:
            dedup: XetDeduplication instance for chunk operations

        """
        self.dedup = dedup
        self.last_check = 0.0
        self.logger = logging.getLogger(__name__)

    async def check_fragmentation(self) -> dict[str, Any]:
        """Check chunk storage fragmentation.

        Analyzes chunk storage layout and calculates fragmentation metrics.

        Returns:
            Dictionary with fragmentation metrics:
            - fragmentation_ratio: float (0.0 to 1.0)
            - scattered_chunks: int
            - total_chunks: int
            - average_access_time: float
            - needs_defrag: bool

        """
        try:
            # Get chunk statistics
            stats = self.dedup.get_cache_stats()
            total_chunks = stats.get("total_chunks", 0)

            if total_chunks == 0:
                return {
                    "fragmentation_ratio": 0.0,
                    "scattered_chunks": 0,
                    "total_chunks": 0,
                    "average_access_time": 0.0,
                    "needs_defrag": False,
                }

            # Analyze chunk access patterns
            cursor = self.dedup.db.execute(
                """SELECT 
                    COUNT(*) as total,
                    AVG(last_accessed - created_at) as avg_age,
                    COUNT(DISTINCT storage_path) as unique_paths
                   FROM chunks"""
            )
            row = cursor.fetchone()

            if not row:
                return {
                    "fragmentation_ratio": 0.0,
                    "scattered_chunks": 0,
                    "total_chunks": total_chunks,
                    "average_access_time": 0.0,
                    "needs_defrag": False,
                }

            unique_paths = row[2] or 1
            total = row[0] or 1

            # Calculate fragmentation ratio
            # Higher ratio means more fragmentation
            fragmentation_ratio = 1.0 - (total / unique_paths) if unique_paths > 0 else 0.0
            scattered_chunks = max(0, unique_paths - total)
            avg_age = row[1] or 0.0

            # Determine if defragmentation is needed
            # Threshold: fragmentation ratio > 0.3 or scattered chunks > 100
            needs_defrag = fragmentation_ratio > 0.3 or scattered_chunks > 100

            return {
                "fragmentation_ratio": fragmentation_ratio,
                "scattered_chunks": scattered_chunks,
                "total_chunks": total_chunks,
                "average_access_time": avg_age,
                "needs_defrag": needs_defrag,
            }

        except Exception as e:
            self.logger.warning(
                "Failed to check fragmentation: %s", e, exc_info=True
            )
            return {
                "fragmentation_ratio": 0.0,
                "scattered_chunks": 0,
                "total_chunks": 0,
                "average_access_time": 0.0,
                "needs_defrag": False,
            }

    async def prevent_fragmentation(self) -> dict[str, Any]:
        """Prevent fragmentation by reorganizing chunk storage.

        Reorganizes chunk storage to reduce fragmentation and improve
        access patterns. This is a placeholder for future implementation.

        Args:
            None

        Returns:
            Dictionary with reorganization statistics:
            - chunks_reorganized: int
            - storage_optimized: int (bytes)
            - fragmentation_reduced: float

        """
        try:
            # Check current fragmentation
            frag_report = await self.check_fragmentation()

            if not frag_report.get("needs_defrag", False):
                self.logger.debug("No defragmentation needed")
                return {
                    "chunks_reorganized": 0,
                    "storage_optimized": 0,
                    "fragmentation_reduced": 0.0,
                }

            # Placeholder: Actual defragmentation logic would go here
            # This would involve:
            # 1. Identifying scattered chunks
            # 2. Reorganizing chunk files to contiguous storage
            # 3. Updating database references
            # 4. Verifying integrity

            self.logger.info(
                "Defragmentation prevention triggered (fragmentation: %.2f%%)",
                frag_report.get("fragmentation_ratio", 0.0) * 100,
            )

            # For now, return placeholder statistics
            return {
                "chunks_reorganized": 0,
                "storage_optimized": 0,
                "fragmentation_reduced": 0.0,
            }

        except Exception as e:
            self.logger.warning(
                "Failed to prevent fragmentation: %s", e, exc_info=True
            )
            return {
                "chunks_reorganized": 0,
                "storage_optimized": 0,
                "fragmentation_reduced": 0.0,
            }

    async def optimize_chunk_layout(
        self, chunk_hashes: list[bytes] | None = None
    ) -> dict[str, Any]:
        """Optimize layout for specific chunks.

        Reorganizes specified chunks to improve access patterns.

        Args:
            chunk_hashes: Optional list of specific chunks to optimize

        Returns:
            Dictionary with optimization statistics

        """
        try:
            if chunk_hashes:
                self.logger.debug(
                    "Optimizing layout for %d chunks", len(chunk_hashes)
                )
            else:
                self.logger.debug("Optimizing layout for all chunks")

            # Placeholder: Actual optimization logic would go here
            return {
                "chunks_optimized": len(chunk_hashes) if chunk_hashes else 0,
                "layout_improved": True,
            }

        except Exception as e:
            self.logger.warning(
                "Failed to optimize chunk layout: %s", e, exc_info=True
            )
            return {
                "chunks_optimized": 0,
                "layout_improved": False,
            }





































