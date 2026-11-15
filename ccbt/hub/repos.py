"""Hub repository store: repos, file manifests, and LFS objects.

Files are tracked by their Git-LFS identity (SHA-256 oid + size) and,
when uploaded through Xet, by their Xet file hash in the CAS. LFS
object bytes are also kept so plain (non-Xet) LFS clients work.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_TYPES = ("models", "datasets", "spaces")


def repo_type_path(repo_type: str) -> str:
    """Public function."""
    mapping = {"model": "models", "dataset": "datasets", "space": "spaces"}
    if repo_type in REPO_TYPES:
        return repo_type
    if repo_type in mapping:
        return mapping[repo_type]
    msg = f"unknown repo type: {repo_type}"
    raise ValueError(msg)


@dataclass
class RepoFile:
    """Public class."""

    path: str
    oid: str  # sha256 hex of content (Git-LFS identity)
    size: int
    xet_file_hash: Optional[str] = None  # Merkle hex, when stored in CAS


class RepoStore:
    """Public class."""

    def __init__(self, root: Path) -> None:
        """Initialize instance."""
        self.root = Path(root)
        self.objects_dir = self.root / "lfs-objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(self.root / "hub.db"), check_same_thread=False)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS repos (
                   repo_id TEXT PRIMARY KEY,
                   repo_type TEXT NOT NULL,
                   private INTEGER NOT NULL DEFAULT 0,
                   created_at REAL NOT NULL
               )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS repo_files (
                   repo_id TEXT NOT NULL,
                   path TEXT NOT NULL,
                   oid TEXT NOT NULL,
                   size INTEGER NOT NULL,
                   xet_file_hash TEXT,
                   PRIMARY KEY (repo_id, path)
               )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS lfs_objects (
                   oid TEXT PRIMARY KEY,
                   size INTEGER NOT NULL,
                   xet_file_hash TEXT,
                   created_at REAL NOT NULL
               )"""
        )
        self.db.commit()

    def close(self) -> None:
        """Public method."""
        self.db.close()

    # --------------------------------------------------------------- repos
    def create_repo(
        self, repo_id: str, repo_type: str = "model", private: bool = False
    ) -> bool:
        """Public method."""
        repo_type_path(repo_type)  # validates
        with self._lock:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO repos (repo_id, repo_type, private, created_at) VALUES (?, ?, ?, ?)",
                (repo_id, repo_type, int(private), time.time()),
            )
            self.db.commit()
            return cur.rowcount > 0

    def repo_exists(self, repo_id: str) -> bool:
        """Public method."""
        with self._lock:
            return (
                self.db.execute(
                    "SELECT 1 FROM repos WHERE repo_id = ?", (repo_id,)
                ).fetchone()
                is not None
            )

    def ensure_repo(self, repo_id: str) -> None:
        """Public method."""
        if not self.repo_exists(repo_id):
            self.create_repo(repo_id)

    # --------------------------------------------------------------- files
    def put_file(self, repo_id: str, entry: RepoFile) -> None:
        """Public method."""
        self.ensure_repo(repo_id)
        with self._lock:
            self.db.execute(
                """INSERT OR REPLACE INTO repo_files
                   (repo_id, path, oid, size, xet_file_hash) VALUES (?, ?, ?, ?, ?)""",
                (repo_id, entry.path, entry.oid, entry.size, entry.xet_file_hash),
            )
            self.db.commit()

    def list_files(self, repo_id: str) -> list[RepoFile]:
        """Public method."""
        with self._lock:
            rows = self.db.execute(
                "SELECT path, oid, size, xet_file_hash FROM repo_files WHERE repo_id = ? ORDER BY path",
                (repo_id,),
            ).fetchall()
        return [RepoFile(r[0], r[1], r[2], r[3]) for r in rows]

    def get_file(self, repo_id: str, path: str) -> Optional[RepoFile]:
        """Public method."""
        with self._lock:
            row = self.db.execute(
                "SELECT path, oid, size, xet_file_hash FROM repo_files WHERE repo_id = ? AND path = ?",
                (repo_id, path),
            ).fetchone()
        return RepoFile(*row) if row else None

    def find_file_by_oid(self, repo_id: str, oid: str) -> Optional[RepoFile]:
        """Public method."""
        with self._lock:
            row = self.db.execute(
                "SELECT path, oid, size, xet_file_hash FROM repo_files WHERE repo_id = ? AND oid = ? LIMIT 1",
                (repo_id, oid),
            ).fetchone()
        return RepoFile(*row) if row else None

    # --------------------------------------------------------- LFS objects
    def register_object(
        self, oid: str, size: int, xet_file_hash: Optional[str] = None
    ) -> None:
        """Public method."""
        with self._lock:
            self.db.execute(
                """INSERT INTO lfs_objects (oid, size, xet_file_hash, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(oid) DO UPDATE SET
                     xet_file_hash = COALESCE(excluded.xet_file_hash, lfs_objects.xet_file_hash),
                     size = excluded.size""",
                (oid, size, xet_file_hash, time.time()),
            )
            self.db.commit()

    def get_object_info(self, oid: str) -> Optional[tuple[int, Optional[str]]]:
        """Public method."""
        with self._lock:
            row = self.db.execute(
                "SELECT size, xet_file_hash FROM lfs_objects WHERE oid = ?", (oid,)
            ).fetchone()
        return (row[0], row[1]) if row else None

    def object_path(self, oid: str) -> Path:
        """Public method."""
        return self.objects_dir / oid

    def put_object_bytes(self, oid: str, data: bytes) -> None:
        """Public method."""
        if hashlib.sha256(data).hexdigest() != oid:
            msg = "LFS object bytes do not match oid"
            raise ValueError(msg)
        path = self.object_path(oid)
        tmp = path.with_name(oid + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        self.register_object(oid, len(data))

    def get_object_bytes(self, oid: str) -> Optional[bytes]:
        """Public method."""
        path = self.object_path(oid)
        return path.read_bytes() if path.exists() else None


def pointer_file_bytes(oid: str, size: int) -> bytes:
    """Canonical Git-LFS pointer file content."""
    return (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {size}\n"
    ).encode()


def parse_pointer_file(data: bytes) -> Optional[tuple[str, int]]:
    """Public function."""
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return None
    if not text.startswith("version https://git-lfs.github.com/spec/v1"):
        return None
    oid: Optional[str] = None
    size: Optional[int] = None
    for line in text.splitlines()[1:]:
        if line.startswith("oid sha256:"):
            oid = line[len("oid sha256:") :].strip()
        elif line.startswith("size "):
            size = int(line[len("size ") :].strip())
    if oid is None or size is None:
        return None
    return oid, size


def manifest_json(store: RepoStore, repo_id: str) -> str:
    """Public function."""
    return json.dumps(
        [
            {"path": f.path, "oid": f.oid, "size": f.size, "xet": f.xet_file_hash}
            for f in store.list_files(repo_id)
        ]
    )
