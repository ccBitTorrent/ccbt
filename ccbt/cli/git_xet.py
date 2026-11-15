"""git-xet: Git LFS custom transfer agent backed by the Xet CAS.

Implements the git-lfs custom transfer protocol (JSON lines on
stdin/stdout). Uploads chunk files into xorbs, uploads xorbs + shard
to the CAS, and registers the (oid -> xet file hash) mapping with the
Hub xet-transfer endpoint taken from the LFS action href (or from
GIT_XET_REPO/GIT_XET_HUB_ENDPOINT in standalone-transfer mode).
Downloads reverse the process and verify the SHA-256 oid.

Environment:
  GIT_XET_CAS_ENDPOINT  base URL of the CAS (required for xet mode)
  GIT_XET_HUB_ENDPOINT  base URL of the Hub (standalone mode)
  GIT_XET_REPO          repo id "namespace/name" (standalone mode)
  GIT_XET_TOKEN         bearer token for CAS + Hub (optional)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ccbt.discovery.xet_cas_http import CasHttpClient
from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_hashing import XetHasher, hash_to_hex, hex_to_hash
from ccbt.storage.xet_shard import (
    FileInfo,
    FileTerm,
    XetShard,
    XorbChunkEntry,
    XorbInfo,
)
from ccbt.storage.xet_xorb import MAX_XORB_SIZE, Xorb


def _env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    return value or None


def _require_http_url(url: str) -> str:
    """Reject non-HTTP(S) schemes before urllib.urlopen (bandit B310)."""
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        msg = f"Refusing non-HTTP(S) URL for git-xet transfer: {parsed.scheme!r}"
        raise ValueError(msg)
    return cleaned


def _http_json(method: str, url: str, payload: Optional[dict] = None) -> dict:
    safe_url = _require_http_url(url)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(safe_url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    token = _env("GIT_XET_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:  # nosec B310 — scheme validated above
        body = resp.read()
    return json.loads(body) if body else {}


async def _upload_to_cas(cas: CasHttpClient, path: Path) -> tuple[str, int]:
    """Chunk a file, upload xorbs + shard; return (file_hash_hex, size)."""
    chunker = GearhashChunker()
    shard = XetShard()
    terms: list[FileTerm] = []
    pairs: list[tuple[bytes, int]] = []
    xorb = Xorb()
    xorb_pairs: list[tuple[bytes, int]] = []

    async def flush_xorb() -> None:
        nonlocal xorb, xorb_pairs
        if not xorb.chunks:
            return
        start = len(pairs) - len(xorb_pairs)
        await cas.upload_xorb(xorb)
        raw_len = len(xorb.serialize())
        shard.add_xorb_info(
            XorbInfo(
                xorb_hash=xorb.get_xorb_hash(),
                chunks=[
                    XorbChunkEntry(chunk_hash=h, byte_range_start=0, unpacked_size=s)
                    for h, s in xorb_pairs
                ],
                num_bytes_on_disk=raw_len,
            )
        )
        terms.append(
            FileTerm(
                xorb_hash=xorb.get_xorb_hash(),
                cas_flags=0,
                unpacked_length=sum(s for _h, s in xorb_pairs),
                chunk_index_start=start,
                chunk_index_end=start + len(xorb_pairs),
            )
        )
        xorb = Xorb()
        xorb_pairs = []

    total = 0
    for chunk in chunker.chunk_file(str(path)):
        h = XetHasher.compute_chunk_hash(chunk)
        pairs.append((h, len(chunk)))
        total += len(chunk)
        if not xorb.add_chunk(h, chunk):
            await flush_xorb()
            if not xorb.add_chunk(h, chunk):
                msg = "failed to add chunk to empty xorb after flush"
                raise RuntimeError(msg)
        xorb_pairs.append((h, len(chunk)))
        if xorb.total_size >= MAX_XORB_SIZE:
            await flush_xorb()
    await flush_xorb()

    file_hash = XetHasher.compute_file_hash(pairs)
    # Verification hashes per term
    verification = []
    for term in terms:
        hashes = [
            pairs[i][0] for i in range(term.chunk_index_start, term.chunk_index_end)
        ]
        verification.append(XetHasher.compute_range_hash(hashes))
    shard.add_file_info(
        FileInfo(file_hash=file_hash, terms=terms, verification=verification)
    )
    await cas.upload_shard(shard)
    return hash_to_hex(file_hash), total


async def _do_upload(oid: str, path: str, action: Optional[dict]) -> dict:
    cas_endpoint = _env("GIT_XET_CAS_ENDPOINT")
    href = (action or {}).get("href")
    if not cas_endpoint:
        # Plain HTTP fallback to the LFS href (basic-transfer semantics).
        if not href:
            return {
                "event": "complete",
                "oid": oid,
                "error": {"code": 1, "message": "no CAS endpoint and no action href"},
            }
        data = Path(path).read_bytes()
        safe_href = _require_http_url(str(href))
        req = urllib.request.Request(safe_href, data=data, method="PUT")
        token = _env("GIT_XET_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req):  # nosec B310 — scheme validated above
            pass
        return {"event": "complete", "oid": oid, "path": path}

    async with CasHttpClient(cas_endpoint, token_provider=_env("GIT_XET_TOKEN")) as cas:
        file_hash_hex, size = await _upload_to_cas(cas, Path(path))
    register_url = href
    if not register_url:
        hub = _env("GIT_XET_HUB_ENDPOINT")
        repo = _env("GIT_XET_REPO")
        if not hub or not repo:
            return {
                "event": "complete",
                "oid": oid,
                "error": {
                    "code": 1,
                    "message": "standalone mode needs GIT_XET_HUB_ENDPOINT and GIT_XET_REPO",
                },
            }
        register_url = f"{hub.rstrip('/')}/api/xet-transfer/{repo}/upload/{oid}"
    _http_json(
        "POST",
        register_url,
        {"xet_file_hash": file_hash_hex, "size": size, "path": Path(path).name},
    )
    return {"event": "complete", "oid": oid, "path": path}


async def _do_download(oid: str, path: str, action: Optional[dict]) -> dict:
    cas_endpoint = _env("GIT_XET_CAS_ENDPOINT")
    href = (action or {}).get("href")
    if not cas_endpoint or not href:
        hub = _env("GIT_XET_HUB_ENDPOINT")
        repo = _env("GIT_XET_REPO")
        if cas_endpoint and hub and repo:
            href = f"{hub.rstrip('/')}/api/xet-transfer/{repo}/download/{oid}"
    if not cas_endpoint or not href:
        if href:  # plain HTTP fallback
            safe_href = _require_http_url(str(href))
            req = urllib.request.Request(safe_href, method="GET")
            token = _env("GIT_XET_TOKEN")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req) as resp:  # nosec B310 — scheme validated
                data = resp.read()
            Path(path).write_bytes(data)
            if hashlib.sha256(data).hexdigest() != oid:
                return {
                    "event": "complete",
                    "oid": oid,
                    "error": {"code": 2, "message": "sha256 mismatch"},
                }
            return {"event": "complete", "oid": oid, "path": path}
        return {
            "event": "complete",
            "oid": oid,
            "error": {"code": 1, "message": "no CAS endpoint and no action href"},
        }

    info = _http_json("GET", href)
    file_hash = hex_to_hash(str(info["xet_file_hash"]))
    async with CasHttpClient(cas_endpoint, token_provider=_env("GIT_XET_TOKEN")) as cas:
        data = await cas.download_file(file_hash)
    if hashlib.sha256(data).hexdigest() != oid:
        return {
            "event": "complete",
            "oid": oid,
            "error": {"code": 2, "message": "sha256 mismatch after CAS download"},
        }
    # Download events carry no path: the agent picks the output file
    # and reports it in the complete event.
    if not path:
        fd, tmp_name = tempfile.mkstemp(prefix="git-xet-", suffix=".bin")
        os.close(fd)
        path = tmp_name
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)
    return {"event": "complete", "oid": oid, "path": path}


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _debug_log(text: str) -> None:
    log_path = os.environ.get("GIT_XET_DEBUG_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> None:
    """git-lfs custom transfer agent entry point."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        _debug_log(f"recv: {line}")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = msg.get("event")
        if event == "init":
            _emit({})
        elif event == "terminate":
            _emit({})
            return
        elif event == "upload":
            oid = str(msg.get("oid", ""))
            try:
                result = asyncio.run(
                    _do_upload(oid, str(msg.get("path", "")), msg.get("action"))
                )
            except Exception as e:  # surface as LFS error, never crash agent
                result = {
                    "event": "complete",
                    "oid": oid,
                    "error": {"code": 1, "message": f"git-xet upload failed: {e}"},
                }
            _emit(result)
        elif event == "download":
            oid = str(msg.get("oid", ""))
            try:
                result = asyncio.run(
                    _do_download(oid, str(msg.get("path", "")), msg.get("action"))
                )
            except Exception as e:
                result = {
                    "event": "complete",
                    "oid": oid,
                    "error": {"code": 1, "message": f"git-xet download failed: {e}"},
                }
            _emit(result)
        else:
            _emit({})


if __name__ == "__main__":
    main()
