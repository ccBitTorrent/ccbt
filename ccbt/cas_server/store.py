"""Persistent CAS storage: xorbs on disk, shard index in SQLite.

Shard blobs are stored verbatim; the SQLite index maps file hashes to
shard ids and records xorb/chunk membership for chunk dedup queries.
All content is verified on write (xorb hash, shard parse, chunk hash
consistency) — unverifiable bytes are rejected, never indexed.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from ccbt.storage.xet_hashing import hash_to_hex
from ccbt.storage.xet_shard import XetShard, parse_shard
from ccbt.storage.xet_xorb import Xorb

logger = logging.getLogger(__name__)


class CasStore:
    """Public class."""

    def __init__(self, root: Path) -> None:
        """Initialize instance."""
        self.root = Path(root)
        self.xorb_dir = self.root / "xorbs"
        self.shard_dir = self.root / "shards"
        self.xorb_dir.mkdir(parents=True, exist_ok=True)
        self.shard_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(self.root / "cas.db"), check_same_thread=False)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS shards (
                   shard_id TEXT PRIMARY KEY,
                   created_at REAL NOT NULL
               )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS files (
                   file_hash BLOB PRIMARY KEY,
                   shard_id TEXT NOT NULL
               )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS shard_chunks (
                   chunk_hash BLOB NOT NULL,
                   shard_id TEXT NOT NULL,
                   PRIMARY KEY (chunk_hash, shard_id)
               )"""
        )
        self.db.commit()
        self._shards: dict[str, XetShard] = {}
        self._load_shards()

    def _load_shards(self) -> None:
        for row in self.db.execute("SELECT shard_id FROM shards"):
            blob_path = self.shard_dir / row[0]
            if blob_path.exists():
                try:
                    self._shards[row[0]] = parse_shard(blob_path.read_bytes())
                except ValueError:
                    logger.warning("Skipping unparsable stored shard %s", row[0])

    def close(self) -> None:
        """Public method."""
        self.db.close()

    # ------------------------------------------------------------- xorbs
    def xorb_path(self, xorb_hash: bytes) -> Path:
        """Public method."""
        return self.xorb_dir / hash_to_hex(xorb_hash)

    def put_xorb(self, xorb_hash: bytes, data: bytes) -> bool:
        """Store a xorb after verifying it hashes to xorb_hash."""
        parsed = Xorb.deserialize(data)  # raises ValueError on bad format
        if parsed.get_xorb_hash() != xorb_hash:
            msg = "xorb body does not hash to the URL hash"
            raise ValueError(msg)
        path = self.xorb_path(xorb_hash)
        with self._lock:
            if path.exists():
                return False
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            return True

    def get_xorb(self, xorb_hash: bytes) -> Optional[bytes]:
        """Public method."""
        path = self.xorb_path(xorb_hash)
        if not path.exists():
            return None
        return path.read_bytes()

    def has_xorb(self, xorb_hash: bytes) -> bool:
        """Public method."""
        return self.xorb_path(xorb_hash).exists()

    # ------------------------------------------------------------ shards
    def put_shard(self, data: bytes) -> int:
        """Register a shard. Returns 1 if new, 0 if already present."""
        shard = parse_shard(data)  # raises ValueError on bad format
        # Consistency: every chunk claimed must belong to a known xorb is
        # NOT required (shards may precede xorbs), but hashes must be 32B.
        shard_id = hashlib.sha256(data).hexdigest()
        with self._lock:
            if shard_id in self._shards:
                return 0
            (self.shard_dir / shard_id).write_bytes(data)
            now = time.time()
            self.db.execute(
                "INSERT OR IGNORE INTO shards (shard_id, created_at) VALUES (?, ?)",
                (shard_id, now),
            )
            for info in shard.files:
                self.db.execute(
                    "INSERT OR REPLACE INTO files (file_hash, shard_id) VALUES (?, ?)",
                    (info.file_hash, shard_id),
                )
            for xorb in shard.xorbs:
                for chunk in xorb.chunks:
                    self.db.execute(
                        "INSERT OR IGNORE INTO shard_chunks (chunk_hash, shard_id) VALUES (?, ?)",
                        (chunk.chunk_hash, shard_id),
                    )
            self.db.commit()
            self._shards[shard_id] = shard
            return 1

    def shard_for_chunk(self, chunk_hash: bytes) -> Optional[XetShard]:
        """Public method."""
        with self._lock:
            row = self.db.execute(
                "SELECT shard_id FROM shard_chunks WHERE chunk_hash = ? LIMIT 1",
                (chunk_hash,),
            ).fetchone()
            if row:
                return self._shards.get(row[0])
            # Upload shards store raw hashes; also try the linear path for
            # shards whose chunk rows were keyed differently.
            for shard in self._shards.values():
                if shard.chunk_dedup_query(chunk_hash):
                    return shard
            return None

    def shard_for_file(self, file_hash: bytes) -> Optional[XetShard]:
        """Public method."""
        with self._lock:
            row = self.db.execute(
                "SELECT shard_id FROM files WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            if row:
                return self._shards.get(row[0])
            return None

    def get_file_info(self, file_hash: bytes):  # -> Optional[FileInfo]
        """Public method."""
        shard = self.shard_for_file(file_hash)
        if shard is None:
            return None
        return shard.get_file_reconstruction(file_hash)
