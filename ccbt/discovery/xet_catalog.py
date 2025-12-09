"""Chunk catalog for bulk queries and indexing.

Provides efficient indexing of chunk-to-peer mappings for fast bulk queries.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class XetChunkCatalog:
    """Catalog for indexing chunk availability across peers.

    Maintains mappings between chunks and peers, with support for
    persistent storage and synchronization via DHT (BEP 44).

    Attributes:
        chunk_to_peers: Dictionary mapping chunk_hash -> set of (ip, port) tuples
        peer_to_chunks: Dictionary mapping (ip, port) -> set of chunk_hashes
        last_sync: Timestamp of last DHT synchronization
        catalog_path: Path to persistent catalog storage

    """

    def __init__(
        self,
        catalog_path: Path | str | None = None,
        sync_interval: float = 300.0,  # 5 minutes
    ):
        """Initialize chunk catalog.

        Args:
            catalog_path: Path to persistent catalog file (optional)
            sync_interval: Interval for DHT synchronization in seconds

        """
        self.chunk_to_peers: dict[bytes, set[tuple[str, int]]] = {}
        self.peer_to_chunks: dict[tuple[str, int], set[bytes]] = {}
        self.last_sync = 0.0
        self.sync_interval = sync_interval
        self.catalog_path = Path(catalog_path) if catalog_path else None
        self._lock = asyncio.Lock()

    async def add_chunk(
        self,
        chunk_hash: bytes,
        peer_info: tuple[str, int] | None = None,
    ) -> None:
        """Add chunk to catalog.

        Args:
            chunk_hash: 32-byte chunk hash
            peer_info: Optional (ip, port) tuple of peer that has this chunk

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        async with self._lock:
            if chunk_hash not in self.chunk_to_peers:
                self.chunk_to_peers[chunk_hash] = set()

            if peer_info:
                self.chunk_to_peers[chunk_hash].add(peer_info)

                if peer_info not in self.peer_to_chunks:
                    self.peer_to_chunks[peer_info] = set()
                self.peer_to_chunks[peer_info].add(chunk_hash)

    async def remove_chunk(
        self,
        chunk_hash: bytes,
        peer_info: tuple[str, int] | None = None,
    ) -> None:
        """Remove chunk from catalog.

        Args:
            chunk_hash: 32-byte chunk hash
            peer_info: Optional (ip, port) tuple of peer to remove

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        async with self._lock:
            if peer_info:
                # Remove specific peer from chunk
                if chunk_hash in self.chunk_to_peers:
                    self.chunk_to_peers[chunk_hash].discard(peer_info)

                # Remove chunk from peer
                if peer_info in self.peer_to_chunks:
                    self.peer_to_chunks[peer_info].discard(chunk_hash)
                    if not self.peer_to_chunks[peer_info]:
                        del self.peer_to_chunks[peer_info]

                # Clean up empty chunk entries
                if chunk_hash in self.chunk_to_peers and not self.chunk_to_peers[chunk_hash]:
                    del self.chunk_to_peers[chunk_hash]
            else:
                # Remove all peers for this chunk
                if chunk_hash in self.chunk_to_peers:
                    peers = self.chunk_to_peers[chunk_hash].copy()
                    for peer in peers:
                        if peer in self.peer_to_chunks:
                            self.peer_to_chunks[peer].discard(chunk_hash)
                            if not self.peer_to_chunks[peer]:
                                del self.peer_to_chunks[peer]
                    del self.chunk_to_peers[chunk_hash]

    async def get_chunks_by_peer(
        self, peer_info: tuple[str, int]
    ) -> set[bytes]:
        """Get all chunks available from a peer.

        Args:
            peer_info: (ip, port) tuple

        Returns:
            Set of chunk hashes available from this peer

        """
        async with self._lock:
            return self.peer_to_chunks.get(peer_info, set()).copy()

    async def get_peers_by_chunks(
        self, chunk_hashes: list[bytes]
    ) -> dict[bytes, set[tuple[str, int]]]:
        """Get peers for multiple chunks.

        Args:
            chunk_hashes: List of chunk hashes

        Returns:
            Dictionary mapping chunk_hash -> set of (ip, port) tuples

        """
        async with self._lock:
            result: dict[bytes, set[tuple[str, int]]] = {}
            for chunk_hash in chunk_hashes:
                if len(chunk_hash) != 32:
                    continue
                result[chunk_hash] = self.chunk_to_peers.get(chunk_hash, set()).copy()
            return result

    async def query_catalog(
        self,
        chunk_hashes: list[bytes] | None = None,
        peer_info: tuple[str, int] | None = None,
    ) -> dict[bytes, set[tuple[str, int]]]:
        """Query catalog for chunk-to-peer mappings.

        Args:
            chunk_hashes: Optional list of chunk hashes to query
            peer_info: Optional peer to filter by

        Returns:
            Dictionary mapping chunk_hash -> set of (ip, port) tuples

        """
        async with self._lock:
            if chunk_hashes:
                # Query specific chunks
                result: dict[bytes, set[tuple[str, int]]] = {}
                for chunk_hash in chunk_hashes:
                    if len(chunk_hash) != 32:
                        continue
                    peers = self.chunk_to_peers.get(chunk_hash, set())
                    if peer_info:
                        # Filter by peer
                        if peer_info in peers:
                            result[chunk_hash] = {peer_info}
                    else:
                        result[chunk_hash] = peers.copy()
                return result

            # Query all chunks
            if peer_info:
                # Filter by peer
                result = {}
                peer_chunks = self.peer_to_chunks.get(peer_info, set())
                for chunk_hash in peer_chunks:
                    result[chunk_hash] = {peer_info}
                return result

            # Return all mappings
            return {
                chunk_hash: peers.copy()
                for chunk_hash, peers in self.chunk_to_peers.items()
            }

    async def sync_with_dht(self, dht_client: Any) -> None:
        """Synchronize catalog with DHT (BEP 44).

        Args:
            dht_client: DHT client instance

        """
        current_time = time.time()
        if current_time - self.last_sync < self.sync_interval:
            return  # Too soon to sync again

        try:
            # Store catalog metadata in DHT
            # Format: {"type": "xet_catalog", "chunks": [...], "timestamp": ...}
            catalog_data = {
                "type": "xet_catalog",
                "timestamp": current_time,
                "chunk_count": len(self.chunk_to_peers),
            }

            # Use a catalog hash as the DHT key
            import hashlib

            catalog_key = hashlib.sha256(
                json.dumps(catalog_data, sort_keys=True).encode()
            ).digest()

            if hasattr(dht_client, "store"):
                await dht_client.store(catalog_key, catalog_data)
                self.last_sync = current_time
                logger.debug("Synchronized catalog with DHT")
        except Exception as e:
            logger.warning("Failed to sync catalog with DHT: %s", e)

    async def load(self) -> None:
        """Load catalog from persistent storage."""
        if not self.catalog_path or not self.catalog_path.exists():
            return

        try:
            async with self._lock:
                with open(self.catalog_path, "rb") as f:
                    data = json.loads(f.read())

                # Deserialize catalog
                self.chunk_to_peers = {}
                self.peer_to_chunks = {}

                for chunk_hex, peers_list in data.get("chunk_to_peers", {}).items():
                    chunk_hash = bytes.fromhex(chunk_hex)
                    peers = {tuple(p) for p in peers_list}  # Convert to tuples
                    self.chunk_to_peers[chunk_hash] = peers

                    for peer in peers:
                        if peer not in self.peer_to_chunks:
                            self.peer_to_chunks[peer] = set()
                        self.peer_to_chunks[peer].add(chunk_hash)

                logger.info(
                    "Loaded catalog: %d chunks, %d peers",
                    len(self.chunk_to_peers),
                    len(self.peer_to_chunks),
                )
        except Exception as e:
            logger.warning("Failed to load catalog: %s", e)

    async def save(self) -> None:
        """Save catalog to persistent storage."""
        if not self.catalog_path:
            return

        try:
            async with self._lock:
                # Ensure directory exists
                self.catalog_path.parent.mkdir(parents=True, exist_ok=True)

                # Serialize catalog
                data = {
                    "chunk_to_peers": {
                        chunk_hash.hex(): list(peers)
                        for chunk_hash, peers in self.chunk_to_peers.items()
                    },
                    "peer_to_chunks": {
                        f"{ip}:{port}": [chunk.hex() for chunk in chunks]
                        for (ip, port), chunks in self.peer_to_chunks.items()
                    },
                }

                with open(self.catalog_path, "wb") as f:
                    f.write(json.dumps(data, indent=2).encode())

                logger.debug("Saved catalog to %s", self.catalog_path)
        except Exception as e:
            logger.warning("Failed to save catalog: %s", e)

    def __len__(self) -> int:
        """Return number of chunks in catalog."""
        return len(self.chunk_to_peers)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"XetChunkCatalog(chunks={len(self)}, peers={len(self.peer_to_chunks)})"



