"""One-time legacy-v1 → v2 XET store / workspace migration.

Reads legacy chunk stores or workspace files, re-chunks with the upstream
Gearhash/BLAKE3 suite, writes v2 chunks, and emits ``.tonic`` with
``format_version=2`` and ``suite=xet-blake3-gearhash-lz4:v2``. On failure the
legacy data is left untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ccbt.core.tonic import TonicFile
from ccbt.models import XetFileMetadata, XetTorrentMetadata
from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_hashing import XetHasher

logger = logging.getLogger(__name__)

SUITE_V2 = TonicFile.SUITE_V2


@dataclass
class MigrationReport:
    """Result of a migrate-legacy run."""

    ok: bool
    files_migrated: int = 0
    chunks_written: int = 0
    errors: list[str] = field(default_factory=list)
    tonic_path: Optional[str] = None


def migrate_legacy_workspace(
    workspace: Path,
    *,
    output_tonic: Optional[Path] = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Migrate a folder workspace from legacy-v1 to v2 chunk identity.

    On any file failure, ``ok`` is False and no partial tonic is written.
    """
    workspace = Path(workspace)
    if not workspace.is_dir():
        return MigrationReport(ok=False, errors=[f"Not a directory: {workspace}"])

    chunker = GearhashChunker()
    report = MigrationReport(ok=True)
    file_entries: list[XetFileMetadata] = []
    all_chunk_hashes: list[bytes] = []

    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel.startswith(".xet/") or rel.endswith(".tonic"):
            continue
        try:
            data = path.read_bytes()
            chunks = chunker.chunk_buffer(data)
            chunk_hashes = [XetHasher.compute_chunk_hash(c) for c in chunks]
            all_chunk_hashes.extend(chunk_hashes)
            report.chunks_written += len(chunk_hashes)
            if len(chunk_hashes) != len(chunks):
                msg = "chunk/hash count mismatch during migration"
                raise ValueError(msg)
            file_hash = XetHasher.compute_file_hash(
                [(h, len(c)) for h, c in zip(chunk_hashes, chunks)]
            )
            file_entries.append(
                XetFileMetadata(
                    file_path=rel,
                    file_hash=file_hash,
                    chunk_hashes=chunk_hashes,
                    total_size=len(data),
                )
            )
            report.files_migrated += 1
        except Exception as e:
            logger.exception("migrate-legacy failed on %s", rel)
            report.ok = False
            report.errors.append(f"{rel}: {e}")
            return report

    if dry_run or not report.ok:
        return report

    tonic_out = output_tonic or (workspace / f"{workspace.name}.tonic")
    try:
        meta = XetTorrentMetadata(
            chunk_hashes=all_chunk_hashes,
            file_metadata=file_entries,
            piece_metadata=[],
            xorb_hashes=[],
        )
        blob = TonicFile().create(folder_name=workspace.name, xet_metadata=meta)
        tonic_out.parent.mkdir(parents=True, exist_ok=True)
        tonic_out.write_bytes(blob)
        report.tonic_path = str(tonic_out)
    except Exception as e:
        report.ok = False
        report.errors.append(f"tonic write failed (legacy untouched): {e}")
        logger.exception("migrate-legacy tonic write failed")
    return report
