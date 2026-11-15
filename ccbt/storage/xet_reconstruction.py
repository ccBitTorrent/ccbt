"""Verified file reconstruction from xorb terms.

Given a FileInfo (from an MDB shard), fetch each referenced xorb,
extract the chunk range, verify the term range hash (when verification
entries are present) and finally the whole-file hash, then deliver the
bytes (in memory or atomically to a path via write-tmp + rename).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ccbt.storage.xet_hashing import XetHasher
from ccbt.storage.xet_xorb import Xorb

if TYPE_CHECKING:
    from ccbt.storage.xet_shard import FileInfo, FileTerm


class ReconstructionError(ValueError):
    """Raised when reconstruction verification fails."""


FetchXorb = Callable[[bytes], bytes]  # xorb_hash -> serialized xorb bytes


def _check_xorb(term: FileTerm, raw: bytes) -> Xorb:
    xorb = Xorb.deserialize(raw)
    if xorb.get_xorb_hash() != term.xorb_hash:
        msg = "fetched xorb hash does not match term xorb hash"
        raise ReconstructionError(msg)
    return xorb


def verify_term(
    info: FileInfo, term_index: int, term: FileTerm, xorb: Xorb
) -> tuple[bytes, list[tuple[bytes, int]]]:
    """Extract and verify one term; returns (bytes, [(hash, size)])."""
    pairs: list[tuple[bytes, int]] = []
    parts: list[bytes] = []
    for i in range(term.chunk_index_start, term.chunk_index_end):
        if i < 0 or i >= len(xorb.chunks):
            msg = f"term chunk index {i} out of range for xorb"
            raise ReconstructionError(msg)
        h, d = xorb.chunks[i]
        pairs.append((h, len(d)))
        parts.append(d)
    data = b"".join(parts)
    if len(data) != term.unpacked_length:
        msg = f"term length mismatch: got {len(data)}, want {term.unpacked_length}"
        raise ReconstructionError(msg)
    if info.verification:
        got = XetHasher.compute_range_hash([h for h, _s in pairs])
        if got != info.verification[term_index]:
            msg = "term range hash verification failed"
            raise ReconstructionError(msg)
    return data, pairs


def reconstruct_verified(info: FileInfo, fetch_xorb: FetchXorb) -> bytes:
    """Reconstruct, verifying xorb hashes, term range hashes, file hash."""
    out = bytearray()
    chunk_hashes: list[tuple[bytes, int]] = []
    for ti, term in enumerate(info.terms):
        xorb = _check_xorb(term, fetch_xorb(term.xorb_hash))
        data, pairs = verify_term(info, ti, term, xorb)
        chunk_hashes.extend(pairs)
        out += data
    if XetHasher.compute_file_hash(chunk_hashes) != info.file_hash:
        msg = "file hash verification failed"
        raise ReconstructionError(msg)
    return bytes(out)


def reconstruct_to_path(info: FileInfo, fetch_xorb: FetchXorb, dest: Path) -> Path:
    """Stream reconstruction to dest atomically (tmp file + rename)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".xet-tmp")
    chunk_hashes: list[tuple[bytes, int]] = []
    try:
        with tmp.open("wb") as fh:
            for ti, term in enumerate(info.terms):
                xorb = _check_xorb(term, fetch_xorb(term.xorb_hash))
                data, pairs = verify_term(info, ti, term, xorb)
                chunk_hashes.extend(pairs)
                fh.write(data)
        if XetHasher.compute_file_hash(chunk_hashes) != info.file_hash:
            msg = "file hash verification failed"
            raise ReconstructionError(msg)
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return dest
