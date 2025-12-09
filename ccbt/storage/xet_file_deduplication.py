"""File-level deduplication for XET protocol.

This module provides file-level deduplication operations, building on top
of chunk-level deduplication to identify and deduplicate entire files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ccbt.models import XetFileMetadata
from ccbt.storage.xet_deduplication import XetDeduplication

logger = logging.getLogger(__name__)


class XetFileDeduplication:
    """File-level deduplication manager.

    Provides file-level deduplication operations by computing file hashes
    (Merkle roots of chunks) and identifying duplicate files. Delegates
    chunk operations to XetDeduplication.

    Attributes:
        dedup: XetDeduplication instance for chunk operations
        logger: Logger instance

    """

    def __init__(self, dedup: XetDeduplication):
        """Initialize file deduplication manager.

        Args:
            dedup: XetDeduplication instance for chunk operations

        """
        self.dedup = dedup
        self.logger = logging.getLogger(__name__)

    async def deduplicate_file(
        self, file_path: Path
    ) -> dict[str, Any]:
        """Deduplicate a file at the file level.

        Computes the file hash (Merkle root of chunks) and checks if
        a file with the same hash already exists. If a duplicate is found,
        creates a reference instead of storing chunks.

        Args:
            file_path: Path to the file to deduplicate

        Returns:
            Dictionary with deduplication statistics:
            - duplicate_found: bool
            - duplicate_path: str | None
            - file_hash: bytes
            - chunks_skipped: int
            - storage_saved: int (bytes)

        """
        try:
            # Get file metadata if it exists
            file_metadata = await self.dedup.get_file_metadata(str(file_path))
            if not file_metadata:
                # File has no metadata, cannot deduplicate
                return {
                    "duplicate_found": False,
                    "duplicate_path": None,
                    "file_hash": bytes(32),
                    "chunks_skipped": 0,
                    "storage_saved": 0,
                }

            file_hash = file_metadata.file_hash

            # Check if another file with the same hash exists
            duplicate_path = await self._find_file_by_hash(file_hash, str(file_path))
            if duplicate_path:
                self.logger.info(
                    "Found duplicate file: %s matches %s",
                    file_path,
                    duplicate_path,
                )
                return {
                    "duplicate_found": True,
                    "duplicate_path": duplicate_path,
                    "file_hash": file_hash,
                    "chunks_skipped": len(file_metadata.chunk_hashes),
                    "storage_saved": file_metadata.total_size,
                }

            return {
                "duplicate_found": False,
                "duplicate_path": None,
                "file_hash": file_hash,
                "chunks_skipped": 0,
                "storage_saved": 0,
            }

        except Exception as e:
            self.logger.warning(
                "Failed to deduplicate file %s: %s", file_path, e, exc_info=True
            )
            return {
                "duplicate_found": False,
                "duplicate_path": None,
                "file_hash": bytes(32),
                "chunks_skipped": 0,
                "storage_saved": 0,
            }

    async def _find_file_by_hash(
        self, file_hash: bytes, exclude_path: str
    ) -> str | None:
        """Find a file with the given hash, excluding the specified path.

        Args:
            file_hash: File hash to search for
            exclude_path: Path to exclude from search

        Returns:
            Path to duplicate file if found, None otherwise

        """
        try:
            # Query database for files with matching hash
            cursor = self.dedup.db.execute(
                """SELECT file_path FROM file_metadata 
                   WHERE file_hash = ? AND file_path != ? 
                   LIMIT 1""",
                (file_hash, exclude_path),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
        except Exception as e:
            self.logger.debug("Failed to find file by hash: %s", e)
            return None

    async def get_file_deduplication_stats(self) -> dict[str, Any]:
        """Get statistics about file deduplication.

        Returns:
            Dictionary with deduplication statistics:
            - total_files: int
            - unique_files: int
            - duplicate_files: int
            - total_storage: int (bytes)
            - deduplicated_storage: int (bytes)
            - deduplication_ratio: float

        """
        try:
            cursor = self.dedup.db.execute(
                """SELECT 
                    COUNT(*) as total_files,
                    COUNT(DISTINCT file_hash) as unique_files,
                    SUM(total_size) as total_storage
                   FROM file_metadata"""
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "total_files": 0,
                    "unique_files": 0,
                    "duplicate_files": 0,
                    "total_storage": 0,
                    "deduplicated_storage": 0,
                    "deduplication_ratio": 0.0,
                }

            total_files = row[0] or 0
            unique_files = row[1] or 0
            total_storage = row[2] or 0

            # Calculate deduplicated storage (sum of unique file sizes)
            cursor = self.dedup.db.execute(
                """SELECT SUM(total_size) 
                   FROM (
                       SELECT DISTINCT file_hash, total_size 
                       FROM file_metadata
                   )"""
            )
            dedup_row = cursor.fetchone()
            deduplicated_storage = dedup_row[0] if dedup_row and dedup_row[0] else 0

            duplicate_files = total_files - unique_files
            deduplication_ratio = (
                (total_storage - deduplicated_storage) / total_storage
                if total_storage > 0
                else 0.0
            )

            return {
                "total_files": total_files,
                "unique_files": unique_files,
                "duplicate_files": duplicate_files,
                "total_storage": total_storage,
                "deduplicated_storage": deduplicated_storage,
                "deduplication_ratio": deduplication_ratio,
            }
        except Exception as e:
            self.logger.warning(
                "Failed to get file deduplication stats: %s", e, exc_info=True
            )
            return {
                "total_files": 0,
                "unique_files": 0,
                "duplicate_files": 0,
                "total_storage": 0,
                "deduplicated_storage": 0,
                "deduplication_ratio": 0.0,
            }

    async def find_duplicate_files(
        self, file_hash: bytes | None = None
    ) -> list[list[str]]:
        """Find groups of duplicate files.

        Args:
            file_hash: Optional specific file hash to find duplicates for

        Returns:
            List of groups, where each group is a list of file paths
            that have the same hash

        """
        try:
            if file_hash:
                # Find duplicates for specific hash
                cursor = self.dedup.db.execute(
                    """SELECT file_path FROM file_metadata 
                       WHERE file_hash = ? 
                       ORDER BY file_path""",
                    (file_hash,),
                )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    return [[row[0] for row in rows]]
                return []
            else:
                # Find all duplicate groups
                cursor = self.dedup.db.execute(
                    """SELECT file_hash, GROUP_CONCAT(file_path, ',') as paths
                       FROM file_metadata
                       GROUP BY file_hash
                       HAVING COUNT(*) > 1"""
                )
                groups = []
                for row in cursor.fetchall():
                    paths = row[1].split(",") if row[1] else []
                    if len(paths) > 1:
                        groups.append(paths)
                return groups
        except Exception as e:
            self.logger.warning(
                "Failed to find duplicate files: %s", e, exc_info=True
            )
            return []

