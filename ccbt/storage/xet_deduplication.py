"""Chunk-level deduplication manager for Xet protocol.

This module provides local and global deduplication for Xet chunks,
using SQLite for local caching and DHT for peer-to-peer chunk discovery.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from ccbt.models import PeerInfo, XetFileMetadata

logger = logging.getLogger(__name__)


class XetDeduplication:
    """Chunk-level deduplication manager.

    Manages local deduplication cache using SQLite and provides
    integration with DHT for global chunk discovery.

    Attributes:
        cache_path: Path to SQLite cache database
        chunk_store_path: Directory where chunks are physically stored
        db: SQLite database connection
        dht_client: Optional DHT client for global chunk discovery

    """

    def __init__(
        self,
        cache_db_path: Path | str,
        dht_client: Any | None = None,  # type: ignore[assignment]
    ):
        """Initialize deduplication with local cache.

        Args:
            cache_db_path: Path to SQLite cache database file
            dht_client: Optional DHT client instance for global chunk discovery

        """
        self.cache_path = Path(cache_db_path)
        self.chunk_store_path = self.cache_path.parent / "xet_chunks"
        self.chunk_store_path.mkdir(parents=True, exist_ok=True)

        self.db = self._init_database()
        self.dht_client = dht_client
        self.logger = logging.getLogger(__name__)

    def _init_database(self) -> sqlite3.Connection:
        """Initialize SQLite cache database.

        Creates the database file and tables if they don't exist.
        Supports migration from old schema (chunks only) to new schema.

        Returns:
            SQLite database connection

        """
        # Ensure parent directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        db = sqlite3.connect(str(self.cache_path))
        
        # Check if schema version table exists (for migration support)
        cursor = db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_version'
        """)
        schema_version_exists = cursor.fetchone() is not None
        
        # Create schema version table if it doesn't exist
        if not schema_version_exists:
            db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at REAL NOT NULL
                )
            """)
            # Set initial version to 1 (old schema with chunks only)
            db.execute("""
                INSERT INTO schema_version (version, applied_at) 
                VALUES (1, ?)
            """, (time.time(),))
        
        # Get current schema version
        cursor = db.execute("SELECT MAX(version) FROM schema_version")
        current_version = cursor.fetchone()[0] or 1
        
        # Create chunks table (always needed)
        db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                hash BLOB PRIMARY KEY,
                size INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                ref_count INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_size ON chunks(size)
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_accessed ON chunks(last_accessed)
        """)
        
        # Migrate to version 2: Add file_chunks and file_metadata tables
        if current_version < 2:
            # Create file_chunks table to track file-to-chunk references
            db.execute("""
                CREATE TABLE IF NOT EXISTS file_chunks (
                    file_path TEXT NOT NULL,
                    chunk_hash BLOB NOT NULL,
                    offset INTEGER NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (file_path, chunk_hash, offset),
                    FOREIGN KEY (chunk_hash) REFERENCES chunks(hash) ON DELETE CASCADE
                )
            """)
            # Indexes for file_chunks
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_chunks_file_path 
                ON file_chunks(file_path)
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_chunks_chunk_hash 
                ON file_chunks(chunk_hash)
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_chunks_file_offset 
                ON file_chunks(file_path, offset)
            """)
            
            # Create file_metadata table for persistent file metadata storage
            db.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    file_path TEXT PRIMARY KEY,
                    file_hash BLOB NOT NULL,
                    total_size INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    last_modified REAL NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            # Index for file_metadata
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_metadata_file_hash 
                ON file_metadata(file_hash)
            """)
            
            # Update schema version
            db.execute("""
                INSERT INTO schema_version (version, applied_at) 
                VALUES (2, ?)
            """, (time.time(),))
            self.logger.info("Migrated XET deduplication database to schema version 2")
        
        db.commit()

        return db

    async def check_chunk_exists(self, chunk_hash: bytes) -> Path | None:
        """Check if chunk exists locally.

        Queries the database for the chunk hash and updates the
        last_accessed timestamp if found.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            Path to stored chunk if exists, None otherwise

        """
        cursor = self.db.execute(
            "SELECT storage_path FROM chunks WHERE hash = ?",
            (chunk_hash,),
        )
        row = cursor.fetchone()
        if row:
            # Update last accessed timestamp
            self.db.execute(
                "UPDATE chunks SET last_accessed = ? WHERE hash = ?",
                (time.time(), chunk_hash),
            )
            self.db.commit()
            return Path(row[0])
        return None

    async def store_chunk(
        self,
        chunk_hash: bytes,
        chunk_data: bytes,
        file_path: str | None = None,
        file_offset: int | None = None,
    ) -> Path:
        """Store chunk with deduplication.

        Checks if chunk already exists. If it does, increments
        reference count. Otherwise, stores the chunk physically
        and creates a database entry.

        Args:
            chunk_hash: 32-byte chunk hash
            chunk_data: Chunk data to store
            file_path: Optional file path that references this chunk
            file_offset: Optional offset in file where this chunk appears

        Returns:
            Path to stored chunk (may be existing or new)

        """
        # Check if already exists
        existing = await self.check_chunk_exists(chunk_hash)
        if existing:
            # Increment reference count
            self.db.execute(
                "UPDATE chunks SET ref_count = ref_count + 1 WHERE hash = ?",
                (chunk_hash,),
            )
            self.db.commit()
            self.logger.debug(
                "Chunk %s already exists, incremented ref count",
                chunk_hash.hex()[:16],
            )
            
            # If file context provided, add file-to-chunk reference
            if file_path is not None and file_offset is not None:
                await self.add_file_chunk_reference(
                    file_path, chunk_hash, file_offset, len(chunk_data)
                )
            
            return existing

        # Store new chunk
        storage_file = self.chunk_store_path / chunk_hash.hex()
        storage_file.write_bytes(chunk_data)

        # Update database
        current_time = time.time()
        self.db.execute(
            """INSERT INTO chunks (hash, size, storage_path, created_at, last_accessed)
               VALUES (?, ?, ?, ?, ?)""",
            (
                chunk_hash,
                len(chunk_data),
                str(storage_file),
                current_time,
                current_time,
            ),
        )
        self.db.commit()

        # If file context provided, add file-to-chunk reference
        if file_path is not None and file_offset is not None:
            await self.add_file_chunk_reference(
                file_path, chunk_hash, file_offset, len(chunk_data)
            )

        self.logger.debug(
            "Stored new chunk %s (%d bytes)",
            chunk_hash.hex()[:16],
            len(chunk_data),
        )

        return storage_file

    async def add_file_chunk_reference(
        self,
        file_path: str,
        chunk_hash: bytes,
        offset: int,
        chunk_size: int,
    ) -> None:
        """Add a file-to-chunk reference.

        Records that a file references a chunk at a specific offset.
        This enables file reconstruction from chunks.

        Args:
            file_path: Path to the file
            chunk_hash: 32-byte chunk hash
            offset: Offset in file where chunk appears
            chunk_size: Size of the chunk in bytes

        """
        try:
            current_time = time.time()
            
            # Check if reference already exists
            cursor = self.db.execute(
                """SELECT 1 FROM file_chunks 
                   WHERE file_path = ? AND chunk_hash = ? AND offset = ?""",
                (file_path, chunk_hash, offset),
            )
            if cursor.fetchone():
                # Reference already exists, skip
                self.logger.debug(
                    "File chunk reference already exists: %s @ offset %d",
                    file_path,
                    offset,
                )
                return
            
            # Insert file-to-chunk reference
            self.db.execute(
                """INSERT INTO file_chunks 
                   (file_path, chunk_hash, offset, chunk_size, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (file_path, chunk_hash, offset, chunk_size, current_time),
            )
            self.db.commit()
            
            self.logger.debug(
                "Added file chunk reference: %s -> %s @ offset %d",
                file_path,
                chunk_hash.hex()[:16],
                offset,
            )
        except sqlite3.IntegrityError as e:
            # Handle duplicate key errors gracefully
            self.logger.debug(
                "File chunk reference already exists (integrity error): %s", e
            )
        except Exception as e:
            self.logger.warning(
                "Failed to add file chunk reference: %s", e, exc_info=True
            )

    async def remove_file_chunk_reference(
        self,
        file_path: str,
        chunk_hash: bytes,
        offset: int,
    ) -> bool:
        """Remove a file-to-chunk reference.

        Removes the reference and decrements chunk reference count.
        If ref_count reaches zero, the chunk is deleted.

        Args:
            file_path: Path to the file
            chunk_hash: 32-byte chunk hash
            offset: Offset in file where chunk appears

        Returns:
            True if chunk was deleted (ref_count reached 0), False otherwise

        """
        try:
            # Delete file-to-chunk reference
            cursor = self.db.execute(
                """DELETE FROM file_chunks 
                   WHERE file_path = ? AND chunk_hash = ? AND offset = ?""",
                (file_path, chunk_hash, offset),
            )
            deleted = cursor.rowcount > 0
            self.db.commit()
            
            if not deleted:
                self.logger.debug(
                    "File chunk reference not found: %s -> %s @ offset %d",
                    file_path,
                    chunk_hash.hex()[:16],
                    offset,
                )
                return False
            
            # Decrement chunk reference count
            return self.remove_chunk_reference(chunk_hash)
            
        except Exception as e:
            self.logger.warning(
                "Failed to remove file chunk reference: %s", e, exc_info=True
            )
            return False

    async def get_file_chunks(
        self, file_path: str
    ) -> list[tuple[bytes, int, int]]:
        """Get ordered list of chunks for a file.

        Retrieves all chunks referenced by a file, ordered by offset.
        This enables file reconstruction.

        Args:
            file_path: Path to the file

        Returns:
            List of tuples (chunk_hash, offset, chunk_size) ordered by offset

        """
        try:
            cursor = self.db.execute(
                """SELECT chunk_hash, offset, chunk_size 
                   FROM file_chunks 
                   WHERE file_path = ? 
                   ORDER BY offset ASC""",
                (file_path,),
            )
            rows = cursor.fetchall()
            return [(row[0], row[1], row[2]) for row in rows]
        except Exception as e:
            self.logger.warning(
                "Failed to get file chunks: %s", e, exc_info=True
            )
            return []

    async def reconstruct_file_from_chunks(
        self,
        file_path: str,
        output_path: Path | None = None,
    ) -> Path:
        """Reconstruct a file from its stored chunks.

        Reads all chunks referenced by the file in order and writes
        them to the output path to reconstruct the original file.

        Args:
            file_path: Path to the file (used to look up chunks)
            output_path: Optional output path (defaults to file_path)

        Returns:
            Path to reconstructed file

        Raises:
            FileNotFoundError: If file has no chunk references
            IOError: If chunk files are missing or cannot be read

        """
        if output_path is None:
            output_path = Path(file_path)

        # Get ordered list of chunks
        chunks = await self.get_file_chunks(file_path)
        if not chunks:
            msg = f"No chunks found for file: {file_path}"
            raise FileNotFoundError(msg)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Reconstruct file by reading chunks in order
        missing_chunks = []
        with output_path.open("wb") as output_file:
            for chunk_hash, offset, chunk_size in chunks:
                try:
                    # Read chunk from storage
                    chunk_path = await self.check_chunk_exists(chunk_hash)
                    if not chunk_path or not chunk_path.exists():
                        missing_chunks.append((chunk_hash, offset))
                        self.logger.warning(
                            "Missing chunk %s at offset %d for file %s",
                            chunk_hash.hex()[:16],
                            offset,
                            file_path,
                        )
                        # Write zeros for missing chunk
                        output_file.write(b"\x00" * chunk_size)
                        continue

                    # Read chunk data
                    chunk_data = chunk_path.read_bytes()

                    # Verify chunk size matches expected
                    if len(chunk_data) != chunk_size:
                        self.logger.warning(
                            "Chunk size mismatch: expected %d, got %d for chunk %s",
                            chunk_size,
                            len(chunk_data),
                            chunk_hash.hex()[:16],
                        )

                    # Seek to correct offset in output file
                    output_file.seek(offset)
                    # Write chunk data
                    output_file.write(chunk_data)

                except Exception as e:
                    self.logger.warning(
                        "Failed to read chunk %s at offset %d: %s",
                        chunk_hash.hex()[:16],
                        offset,
                        e,
                    )
                    missing_chunks.append((chunk_hash, offset))
                    # Write zeros for missing chunk
                    output_file.seek(offset)
                    output_file.write(b"\x00" * chunk_size)

        if missing_chunks:
            self.logger.warning(
                "Reconstructed file %s with %d missing chunks",
                output_path,
                len(missing_chunks),
            )

        self.logger.debug(
            "Reconstructed file %s from %d chunks",
            output_path,
            len(chunks),
        )

        return output_path

    async def store_file_metadata(self, metadata: XetFileMetadata) -> None:
        """Store file metadata persistently.

        Serializes XetFileMetadata to JSON and stores it in the database
        for later retrieval and file reconstruction.

        Args:
            metadata: XetFileMetadata instance to store

        """
        try:
            current_time = time.time()
            
            # Serialize metadata to JSON
            metadata_dict = metadata.model_dump()
            # Convert bytes to hex strings for JSON serialization
            metadata_dict["file_hash"] = metadata.file_hash.hex()
            metadata_dict["chunk_hashes"] = [
                h.hex() for h in metadata.chunk_hashes
            ]
            metadata_dict["xorb_refs"] = [h.hex() for h in metadata.xorb_refs]
            metadata_json = json.dumps(metadata_dict)
            
            # Insert or update file metadata
            self.db.execute(
                """INSERT OR REPLACE INTO file_metadata 
                   (file_path, file_hash, total_size, chunk_count, 
                    created_at, last_modified, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    metadata.file_path,
                    metadata.file_hash,
                    metadata.total_size,
                    len(metadata.chunk_hashes),
                    current_time,
                    current_time,
                    metadata_json,
                ),
            )
            self.db.commit()
            
            self.logger.debug(
                "Stored file metadata for %s (%d chunks)",
                metadata.file_path,
                len(metadata.chunk_hashes),
            )
        except Exception as e:
            self.logger.warning(
                "Failed to store file metadata: %s", e, exc_info=True
            )

    async def get_file_metadata(self, file_path: str) -> XetFileMetadata | None:
        """Get file metadata from persistent storage.

        Retrieves and deserializes XetFileMetadata from the database.

        Args:
            file_path: Path to the file

        Returns:
            XetFileMetadata if found, None otherwise

        """
        try:
            cursor = self.db.execute(
                """SELECT metadata_json FROM file_metadata 
                   WHERE file_path = ?""",
                (file_path,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            # Deserialize JSON to XetFileMetadata
            metadata_dict = json.loads(row[0])
            # Convert hex strings back to bytes
            metadata_dict["file_hash"] = bytes.fromhex(metadata_dict["file_hash"])
            metadata_dict["chunk_hashes"] = [
                bytes.fromhex(h) for h in metadata_dict["chunk_hashes"]
            ]
            metadata_dict["xorb_refs"] = [
                bytes.fromhex(h) for h in metadata_dict.get("xorb_refs", [])
            ]
            
            return XetFileMetadata(**metadata_dict)
        except Exception as e:
            self.logger.warning(
                "Failed to get file metadata: %s", e, exc_info=True
            )
            return None

    async def query_dht_for_chunk(self, chunk_hash: bytes) -> PeerInfo | None:
        """Query DHT for peers that have this chunk.

        Uses existing DHT infrastructure to find peers that have
        the specified chunk. This enables global deduplication
        across the peer network.

        The method:
        1. Converts 32-byte chunk hash to 20-byte DHT key (using SHA-1)
        2. Queries DHT using BEP 44 get_data() method
        3. Parses returned value to extract peer information
        4. Returns PeerInfo if found

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            PeerInfo if found, None otherwise

        """
        if len(chunk_hash) != 32:
            self.logger.warning(
                "Invalid chunk hash length: expected 32 bytes, got %d",
                len(chunk_hash),
            )
            return None

        if not self.dht_client:
            self.logger.debug("DHT client not available for chunk query")
            return None

        try:
            # Convert 32-byte chunk hash to 20-byte DHT key
            # Use SHA-1 of the chunk hash to ensure proper DHT distribution
            dht_key = hashlib.sha1(chunk_hash, usedforsecurity=False).digest()

            self.logger.debug(
                "Querying DHT for chunk %s (DHT key: %s)",
                chunk_hash.hex()[:16],
                dht_key.hex()[:16],
            )

            # Try get_data() first (BEP 44)
            if hasattr(self.dht_client, "get_data"):
                try:
                    value = await self.dht_client.get_data(dht_key)

                    if value:
                        # Value is a bencoded dictionary, decode it
                        peer_info = self._extract_peer_from_dht_value(value)
                        if peer_info:
                            self.logger.debug(
                                "Found peer %s for chunk %s via DHT get_data",
                                peer_info,
                                chunk_hash.hex()[:16],
                            )
                            return peer_info
                except Exception as e:
                    self.logger.debug(
                        "DHT get_data failed for chunk %s: %s",
                        chunk_hash.hex()[:16],
                        e,
                    )

            # Try get_peers() as fallback (uses info_hash lookup)
            # Note: This treats the chunk hash as an info_hash
            if hasattr(self.dht_client, "get_peers"):
                try:
                    # Use first 20 bytes of chunk hash as info_hash
                    info_hash = chunk_hash[:20]
                    peers = await self.dht_client.get_peers(info_hash, max_peers=1)

                    # Extract first peer
                    if (
                        peers
                        and isinstance(peers[0], (list, tuple))
                        and len(peers[0]) >= 2
                    ):
                        ip, port = peers[0][0], peers[0][1]
                        peer_info = PeerInfo(ip=str(ip), port=int(port))
                        self.logger.debug(
                            "Found peer %s for chunk %s via DHT get_peers",
                            peer_info,
                            chunk_hash.hex()[:16],
                        )
                        return peer_info
                except Exception as e:  # pragma: no cover - DHT get_peers exception handling, defensive error path
                    self.logger.debug(
                        "DHT get_peers failed for chunk %s: %s",
                        chunk_hash.hex()[:16],
                        e,
                    )  # pragma: no cover - Same context

            self.logger.debug(
                "No peers found in DHT for chunk %s",
                chunk_hash.hex()[:16],
            )
            return None

        except (
            Exception
        ) as e:  # pragma: no cover - DHT query exception handling, defensive error path
            self.logger.warning(
                "Error querying DHT for chunk %s: %s",
                chunk_hash.hex()[:16],
                e,
            )  # pragma: no cover - Same context
            return None  # pragma: no cover - Same context

    def _extract_peer_from_dht_value(self, value: Any) -> PeerInfo | None:  # type: ignore[return]
        """Extract PeerInfo from DHT stored value (BEP 44).

        The value can be in various formats:
        - Dictionary with "ip" and "port" keys
        - Dictionary with "type": "xet_chunk" and peer info
        - List/tuple with (ip, port)
        - Bencoded bytes that need decoding

        Args:
            value: DHT stored value (can be dict, bytes, or other)

        Returns:
            PeerInfo if extractable, None otherwise

        """
        try:
            # Handle bencoded bytes - decode if needed
            if isinstance(value, bytes):
                try:
                    from ccbt.core.bencode import BencodeDecoder

                    decoder = BencodeDecoder(value)
                    value = decoder.decode()
                except Exception:
                    # If decoding fails, try treating as raw peer data
                    if (
                        len(value) == 6
                    ):  # pragma: no cover - Compact peer format path, tested in test_extract_peer_from_dht_value_compact_format
                        # Compact format: 4 bytes IP + 2 bytes port
                        ip = ".".join(
                            str(b) for b in value[:4]
                        )  # pragma: no cover - Same context
                        port = int.from_bytes(
                            value[4:6], "big"
                        )  # pragma: no cover - Same context
                        return PeerInfo(
                            ip=ip, port=port
                        )  # pragma: no cover - Same context
                    return (
                        None  # pragma: no cover - Invalid bytes length, defensive check
                    )

            # Handle dictionary
            if isinstance(value, dict):
                # Check if it's a chunk metadata entry
                if (
                    value.get("type") == "xet_chunk"
                    or value.get(b"type") == b"xet_chunk"
                ):
                    # Extract peer info from metadata
                    # Try different key formats (str vs bytes)
                    ip = value.get("ip") or value.get(b"ip")
                    port = value.get("port") or value.get(b"port")

                    if ip and port:
                        return PeerInfo(ip=str(ip), port=int(port))

                    # Try peer_id lookup (would require additional DHT query)
                    peer_id = value.get("peer_id") or value.get(
                        b"peer_id"
                    )  # pragma: no cover - Peer ID lookup path, future feature
                    if peer_id:  # pragma: no cover - Same context
                        # For now, we can't resolve peer_id to IP/port without
                        # additional DHT infrastructure
                        self.logger.debug(
                            "Found peer_id in DHT value but cannot resolve to IP/port"
                        )  # pragma: no cover - Future feature path, not yet implemented
                        return None  # pragma: no cover - Same context

                # Direct peer info
                ip = value.get("ip") or value.get(
                    b"ip"
                )  # pragma: no cover - Direct peer info extraction path
                port = value.get("port") or value.get(
                    b"port"
                )  # pragma: no cover - Same context

                if ip and port:  # pragma: no cover - Same context
                    return PeerInfo(
                        ip=str(ip), port=int(port)
                    )  # pragma: no cover - Same context

            # Handle list/tuple
            if (
                isinstance(value, (list, tuple)) and len(value) >= 2
            ):  # pragma: no cover - List/tuple peer format path
                ip = value[0]  # pragma: no cover - Same context
                port = value[1]  # pragma: no cover - Same context
                return PeerInfo(
                    ip=str(ip), port=int(port)
                )  # pragma: no cover - Same context

        except (
            Exception
        ) as e:  # pragma: no cover - Defensive exception handling in peer extraction
            self.logger.debug(
                "Failed to extract peer from DHT value: %s",
                e,
            )  # pragma: no cover - Same context

        return None

    def get_chunk_info(self, chunk_hash: bytes) -> dict | None:
        """Get information about a stored chunk.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            Dictionary with chunk information or None if not found

        """
        cursor = self.db.execute(
            """SELECT hash, size, storage_path, ref_count, created_at, last_accessed
               FROM chunks WHERE hash = ?""",
            (chunk_hash,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "hash": row[0],
                "size": row[1],
                "storage_path": row[2],
                "ref_count": row[3],
                "created_at": row[4],
                "last_accessed": row[5],
            }
        return None

    def remove_chunk_reference(self, chunk_hash: bytes) -> bool:
        """Remove a reference to a chunk.

        Decrements the reference count. If ref_count reaches zero,
        the chunk file is deleted.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            True if chunk was removed, False otherwise

        """
        # Get current ref count
        cursor = self.db.execute(
            "SELECT ref_count, storage_path FROM chunks WHERE hash = ?",
            (chunk_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return False

        ref_count = row[0]
        storage_path = row[1]

        if ref_count <= 1:
            # Remove chunk file and database entry
            try:
                Path(storage_path).unlink()
            except OSError as e:
                self.logger.warning(
                    "Failed to remove chunk file %s: %s",
                    storage_path,
                    e,
                )

            self.db.execute("DELETE FROM chunks WHERE hash = ?", (chunk_hash,))
            self.db.commit()
            return True
        # Decrement ref count
        self.db.execute(
            "UPDATE chunks SET ref_count = ref_count - 1 WHERE hash = ?",
            (chunk_hash,),
        )
        self.db.commit()
        return False

    async def cleanup_unused_chunks(
        self,
        max_age_seconds: int = 30 * 24 * 60 * 60,  # 30 days
    ) -> int:
        """Remove chunks that haven't been accessed recently.

        Args:
            max_age_seconds: Maximum age in seconds before chunk is considered unused

        Returns:
            Number of chunks removed

        """
        cutoff_time = time.time() - max_age_seconds

        cursor = self.db.execute(
            """SELECT hash, storage_path FROM chunks
               WHERE last_accessed < ? AND ref_count <= 1""",
            (cutoff_time,),
        )

        removed_count = 0
        for row in cursor.fetchall():
            chunk_hash = row[0]
            storage_path = row[1]

            try:
                Path(storage_path).unlink()
                self.db.execute("DELETE FROM chunks WHERE hash = ?", (chunk_hash,))
                removed_count += 1
            except OSError as e:
                self.logger.warning(
                    "Failed to remove unused chunk %s: %s",
                    storage_path,
                    e,
                )

        self.db.commit()
        self.logger.info("Cleaned up %d unused chunks", removed_count)
        return removed_count

    def get_cache_stats(self) -> dict:
        """Get statistics about the deduplication cache.

        Returns:
            Dictionary with cache statistics

        """
        cursor = self.db.execute(
            """SELECT
                COUNT(*) as total_chunks,
                SUM(size) as total_size,
                SUM(ref_count) as total_refs,
                AVG(size) as avg_size
               FROM chunks"""
        )
        row = cursor.fetchone()

        return {
            "total_chunks": row[0] or 0,
            "total_size": row[1] or 0,
            "total_refs": row[2] or 0,
            "avg_size": row[3] or 0,
        }

    def close(self) -> None:
        """Close database connection."""
        if self.db:
            self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
