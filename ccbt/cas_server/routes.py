"""CAS HTTP routes implementing the pinned OpenXet contract."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional, Union

from aiohttp import web

from ccbt.cas_server.auth import (
    READ,
    WRITE,
    TokenAuth,
    sign_transfer_url,
    verify_transfer_signature,
)
from ccbt.cas_server.store import CasStore
from ccbt.storage.xet_hashing import hash_to_hex, hex_to_hash
from ccbt.storage.xet_xorb import Xorb

logger = logging.getLogger(__name__)

STORE_KEY = web.AppKey("cas_store", CasStore)
AUTH_KEY = web.AppKey("cas_auth", TokenAuth)
SECRET_KEY = web.AppKey("cas_secret", bytes)


def _err(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _parse_hash(value: str) -> Optional[bytes]:
    try:
        return hex_to_hash(value)
    except ValueError:
        return None


def _require(request: web.Request, scope: str) -> Optional[web.Response]:
    auth: TokenAuth = request.config_dict[AUTH_KEY]  # type: ignore[assignment]
    if auth.check(request.headers.get("Authorization"), scope):
        return None
    # Signed transfer URLs are capabilities for xorb byte routes only.
    if request.path.startswith("/xorbs/"):
        store_secret: bytes = request.config_dict[SECRET_KEY]  # type: ignore[assignment]
        xorb_hex = request.match_info.get("hash", "")
        if verify_transfer_signature(
            store_secret, xorb_hex, request.query.get("exp"), request.query.get("sig")
        ):
            return None
    return _err("unauthorized", 401)


def _store(request: web.Request) -> CasStore:
    return request.config_dict[STORE_KEY]  # type: ignore[return-value]


async def get_chunk_dedup(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    if request.match_info["prefix"] != "default-merkledb":
        return _err("unsupported prefix", 400)
    chunk_hash = _parse_hash(request.match_info["hash"])
    if chunk_hash is None:
        return _err("malformed hash", 400)
    shard = _store(request).shard_for_chunk(chunk_hash)
    if shard is None:
        return _err("chunk not tracked", 404)
    secret: bytes = request.config_dict[SECRET_KEY]  # type: ignore[assignment]
    key = hashlib.sha256(secret + b":shard-hmac").digest()
    return web.Response(
        body=shard.serialize(hmac_key=key), content_type="application/octet-stream"
    )


async def post_xorb(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, WRITE)) is not None:
        return r
    if request.match_info["prefix"] != "default":
        return _err("unsupported prefix", 400)
    xorb_hash = _parse_hash(request.match_info["hash"])
    if xorb_hash is None:
        return _err("malformed hash", 400)
    body = await request.read()
    try:
        inserted = _store(request).put_xorb(xorb_hash, body)
    except ValueError as e:
        return _err(str(e), 400)
    return web.json_response({"was_inserted": inserted})


async def head_xorb(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    xorb_hash = _parse_hash(request.match_info["hash"])
    if xorb_hash is None:
        return _err("malformed hash", 400)
    raw = _store(request).get_xorb(xorb_hash)
    if raw is None:
        return _err("xorb not found", 404)
    return web.Response(headers={"Content-Length": str(len(raw))})


async def get_xorb_bytes(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    xorb_hash = _parse_hash(request.match_info["hash"])
    if xorb_hash is None:
        return _err("malformed hash", 400)
    raw = _store(request).get_xorb(xorb_hash)
    if raw is None:
        return _err("xorb not found", 404)
    range_header = request.headers.get("Range", "")
    if range_header.startswith("bytes="):
        try:
            start_s, end_s = range_header[len("bytes=") :].split("-", 1)
            start = int(start_s)
            end = int(end_s) if end_s else len(raw) - 1
        except ValueError:
            return _err("malformed range", 400)
        if start >= len(raw):
            return _err("range not satisfiable", 416)
        end = min(end, len(raw) - 1)
        return web.Response(
            body=raw[start : end + 1],
            status=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{len(raw)}",
                "Accept-Ranges": "bytes",
            },
            content_type="application/octet-stream",
        )
    return web.Response(body=raw, content_type="application/octet-stream")


async def post_shard_v1(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, WRITE)) is not None:
        return r
    body = await request.read()
    try:
        result = _store(request).put_shard(body)
    except ValueError as e:
        return _err(str(e), 400)
    return web.json_response({"result": result})


async def post_shard_v2(
    request: web.Request,
) -> Union[web.StreamResponse, web.Response]:
    """Public function."""
    if (r := _require(request, WRITE)) is not None:
        return r
    body = await request.read()
    resp = web.StreamResponse(headers={"Content-Type": "application/x-ndjson"})
    await resp.prepare(request)
    # NDJSON frames follow the upstream ShardUploadEvent serde shape
    # (xet_client::cas_types): {"type": ...} tagged frames that stock
    # hf_xet parses. A {"status": ...} frame is rejected by hf_xet.
    try:
        await resp.write(b'{"type": "validating", "verified": 0, "total": 1}\n')
        _store(request).put_shard(body)
        await resp.write(b'{"type": "validating", "verified": 1, "total": 1}\n')
        await resp.write(b'{"type": "committing", "stage": "uploading"}\n')
        await resp.write(b'{"type": "committing", "stage": "syncing"}\n')
        await resp.write(b'{"type": "result"}\n')
    except ValueError as e:
        await resp.write(
            json.dumps(
                {"type": "error", "message": str(e), "retryable": False}
            ).encode()
            + b"\n"
        )
    await resp.write_eof()
    return resp


def _terms_json(info) -> list[dict]:
    return [
        {
            "hash": hash_to_hex(t.xorb_hash),
            "range": {"start": t.chunk_index_start, "end": t.chunk_index_end},
            "unpacked_length": t.unpacked_length,
        }
        for t in info.terms
    ]


def _check_range(request: web.Request, total: int) -> Optional[web.Response]:
    range_header = request.headers.get("Range", "")
    if range_header.startswith("bytes="):
        try:
            start = int(range_header[len("bytes=") :].split("-", 1)[0])
        except ValueError:
            return _err("malformed range", 400)
        if (start >= total > 0) or start > total:
            return _err("range not satisfiable", 416)
    return None


def _fetch_entries(request: web.Request, info) -> dict[str, list[dict]]:
    store = _store(request)
    secret: bytes = request.config_dict[SECRET_KEY]  # type: ignore[assignment]
    base = str(request.url.origin())
    out: dict[str, list[dict]] = {}
    for term in info.terms:
        raw = store.get_xorb(term.xorb_hash)
        if raw is None:
            continue
        ranges = Xorb.chunk_byte_ranges(raw)
        if term.chunk_index_end > len(ranges):
            continue
        sel = ranges[term.chunk_index_start : term.chunk_index_end]
        if not sel:
            continue
        xorb_hex = hash_to_hex(term.xorb_hash)
        url = f"{base}/xorbs/default/{xorb_hex}?{sign_transfer_url(secret, xorb_hex)}"
        out.setdefault(xorb_hex, []).append(
            {
                "url": url,
                "ranges": [
                    {
                        "chunks": {
                            "start": term.chunk_index_start,
                            "end": term.chunk_index_end,
                        },
                        "bytes": {"start": sel[0][0], "end": sel[-1][1] - 1},
                    }
                ],
            }
        )
    return out


async def get_reconstruction_v2(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    file_hash = _parse_hash(request.match_info["file_id"])
    if file_hash is None:
        return _err("malformed file id", 400)
    info = _store(request).get_file_info(file_hash)
    if info is None:
        return _err("file not found", 404)
    if (r := _check_range(request, info.total_length)) is not None:
        return r
    return web.json_response(
        {
            "offset_into_first_range": 0,
            "terms": _terms_json(info),
            "xorbs": _fetch_entries(request, info),
        }
    )


async def get_reconstruction_v1(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    file_hash = _parse_hash(request.match_info["file_id"])
    if file_hash is None:
        return _err("malformed file id", 400)
    info = _store(request).get_file_info(file_hash)
    if info is None:
        return _err("file not found", 404)
    if (r := _check_range(request, info.total_length)) is not None:
        return r
    fetch_info: dict[str, list[dict]] = {}
    for xorb_hex, entries in _fetch_entries(request, info).items():
        fetch_info[xorb_hex] = [
            {
                "url": e["url"],
                "url_range": {
                    "start": e["ranges"][0]["bytes"]["start"],
                    "end": e["ranges"][0]["bytes"]["end"],
                },
                "range": e["ranges"][0]["chunks"],
            }
            for e in entries
        ]
    return web.json_response(
        {
            "offset_into_first_range": 0,
            "terms": _terms_json(info),
            "fetch_info": fetch_info,
        }
    )


async def post_reconstructions_batch(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    try:
        ids = await request.json()
    except Exception:
        return _err("expected JSON array of file ids", 400)
    if not isinstance(ids, list):
        return _err("expected JSON array of file ids", 400)
    store = _store(request)
    files: dict[str, list[dict]] = {}
    for hex_id in ids:
        file_hash = _parse_hash(str(hex_id))
        if file_hash is None:
            continue
        info = store.get_file_info(file_hash)
        if info is not None:
            files[hash_to_hex(file_hash)] = _terms_json(info)
    return web.json_response({"files": files, "fetch_info": {}})


async def post_telemetry(request: web.Request) -> web.Response:
    """Public function."""
    if (r := _require(request, READ)) is not None:
        return r
    try:
        payload = await request.json()
    except Exception:
        return _err("invalid telemetry payload", 400)
    if not isinstance(payload, dict) or "time" not in payload or "event" not in payload:
        return _err("missing telemetry keys", 400)
    return web.json_response({"accepted": True})


def register_routes(app: web.Application) -> None:
    """Public function."""
    app.router.add_get("/v1/chunks/{prefix}/{hash}", get_chunk_dedup)
    app.router.add_post("/v1/xorbs/{prefix}/{hash}", post_xorb)
    app.router.add_head("/v1/xorbs/{prefix}/{hash}", head_xorb)
    app.router.add_get("/xorbs/{prefix}/{hash}", get_xorb_bytes)
    app.router.add_post("/v1/shards", post_shard_v1)
    app.router.add_post("/v2/shards", post_shard_v2)
    app.router.add_get("/v1/reconstructions/{file_id}", get_reconstruction_v1)
    app.router.add_get("/v2/reconstructions/{file_id}", get_reconstruction_v2)
    app.router.add_post("/v1/reconstructions", post_reconstructions_batch)
    app.router.add_post("/v1/telemetry", post_telemetry)
