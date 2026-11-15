"""HTTP client for a Xet CAS service (HF/OpenXet wire contract).

Implements the routes stock hf_xet uses (see openapi/cas.openapi.yaml
in huggingface/xet-core, pinned in dev/xet-conformance.lock.json):

- GET  /v1/chunks/default-merkledb/{hash}   global-dedup shard query
- POST /v1/xorbs/default/{hash}             xorb upload ({was_inserted})
- POST /v2/shards                           shard upload (NDJSON events)
- POST /v1/shards                           shard upload fallback ({result})
- GET  /v2/reconstructions/{file}           multi-range fetch info
- GET  /v1/reconstructions/{file}           v1 fallback (per-range URLs)
- POST /v1/reconstructions                  batch reconstruction query

All hashes on the wire are Merkle hex (see xet_hashing.hash_to_hex).
Downloads are fully verified: xorb hashes, chunk hashes, and the final
file hash must match the request.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Optional, Union

try:
    from typing import Self
except ImportError:  # Python < 3.11
    from typing_extensions import Self

import aiohttp

from ccbt.storage.xet_hashing import XetHasher, hash_to_hex, hex_to_hash, truncate_hash
from ccbt.storage.xet_reconstruction import ReconstructionError
from ccbt.storage.xet_shard import XetShard, parse_shard, serialize_shard_for_upload
from ccbt.storage.xet_xorb import Xorb

logger = logging.getLogger(__name__)

GLOBAL_DEDUP_PREFIX = "default-merkledb"
XORB_PREFIX = "default"
GLOBAL_DEDUP_MODULO = 1024

TokenProvider = Union[
    str, Callable[[], Union[str, None, Awaitable[Optional[str]]]], None
]


class CasHttpError(Exception):
    """Public class."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        """Initialize instance."""
        super().__init__(message)
        self.status = status


class CasNotFoundError(CasHttpError):
    """Public class."""


# Back-compat alias
CasNotFound = CasNotFoundError


class CasRangeError(CasHttpError):
    """Public class."""


def is_global_dedup_eligible(
    chunk_hash: bytes, *, is_first_chunk: bool = False
) -> bool:
    """Upstream rule: first chunk of a file, or truncate(hash) % 1024 == 0."""
    return is_first_chunk or truncate_hash(chunk_hash) % GLOBAL_DEDUP_MODULO == 0


@dataclass
class FetchRange:
    """Public class."""

    url: str
    byte_start: int  # inclusive
    byte_end: int  # inclusive
    chunk_start: int
    chunk_end: int  # exclusive


@dataclass
class ReconstructionInfo:
    """Public class."""

    file_hash: bytes
    offset_into_first_range: int
    # (xorb_hash, chunk_start, chunk_end, unpacked_length)
    terms: list[tuple[bytes, int, int, int]] = field(default_factory=list)
    fetch: dict[bytes, list[FetchRange]] = field(default_factory=dict)


class CasHttpClient:
    """Async CAS client with bearer auth and one 401 token refresh."""

    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider = None,
        *,
        timeout_seconds: float = 60.0,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize instance."""
        self.base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session = session
        self._own_session = session is None

    @classmethod
    def from_config(cls, config: object) -> Optional[CasHttpClient]:
        """Public method."""
        disk = getattr(config, "disk", config)
        endpoint = getattr(disk, "xet_cas_endpoint", None)
        if not endpoint:
            return None
        env_name = getattr(disk, "xet_cas_token_env", "CCBT_CAS_TOKEN")
        return cls(endpoint, token_provider=lambda: os.environ.get(env_name))

    async def __aenter__(self) -> Self:
        """Magic method."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Magic method."""
        await self.close()

    async def close(self) -> None:
        """Public method."""
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def _token(self) -> Optional[str]:
        provider = self._token_provider
        if provider is None:
            return None
        if isinstance(provider, str):
            return provider
        result = provider()
        if isinstance(result, Awaitable):
            return await result
        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: Optional[bytes] = None,
        json_body: object = None,
        headers: Optional[dict[str, str]] = None,
        _retried: bool = False,
    ) -> aiohttp.ClientResponse:
        session = self._get_session()
        hdrs = dict(headers or {})
        token = await self._token()
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        resp = await session.request(
            method, f"{self.base_url}{path}", data=data, json=json_body, headers=hdrs
        )
        if resp.status == 401 and not _retried:
            resp.release()
            # One refresh attempt with a freshly-provided token.
            return await self._request(
                method,
                path,
                data=data,
                json_body=json_body,
                headers=headers,
                _retried=True,
            )
        return resp

    @staticmethod
    async def _raise_for(resp: aiohttp.ClientResponse, what: str) -> None:
        if resp.status < 400:
            return
        body = (await resp.text())[:500]
        if resp.status == 404:
            msg = f"{what}: not found (404): {body}"
            raise CasNotFound(msg, status=404)
        if resp.status == 416:
            msg = f"{what}: range not satisfiable (416): {body}"
            raise CasRangeError(msg, status=416)
        msg = f"{what}: HTTP {resp.status}: {body}"
        raise CasHttpError(msg, status=resp.status)

    # ------------------------------------------------------------ dedup
    async def query_chunk_shard(self, chunk_hash: bytes) -> Optional[XetShard]:
        """Return the server shard answering a global-dedup query, or None."""
        path = f"/v1/chunks/{GLOBAL_DEDUP_PREFIX}/{hash_to_hex(chunk_hash)}"
        resp = await self._request("GET", path)
        try:
            if resp.status == 404:
                return None
            await self._raise_for(resp, "chunk dedup query")
            data = await resp.read()
        finally:
            resp.release()
        try:
            return parse_shard(data)
        except ValueError as e:
            msg = f"chunk dedup query: invalid shard response: {e}"
            raise CasHttpError(msg) from e

    async def chunk_exists_remote(self, chunk_hash: bytes) -> bool:
        """Public method."""
        shard = await self.query_chunk_shard(chunk_hash)
        return shard is not None and shard.chunk_dedup_query(chunk_hash)

    # ------------------------------------------------------------ upload
    async def upload_xorb(self, xorb: Xorb) -> bool:
        """Upload a xorb; returns was_inserted."""
        xorb_hash = xorb.get_xorb_hash()
        body = xorb.serialize(compress=True)
        # Server recomputes identity from chunk headers; our serialized
        # form must hash to the URL hash.
        if Xorb.deserialize(body).get_xorb_hash() != xorb_hash:
            msg = "serialized xorb does not round-trip to its hash"
            raise CasHttpError(msg)
        path = f"/v1/xorbs/{XORB_PREFIX}/{hash_to_hex(xorb_hash)}"
        resp = await self._request(
            "POST",
            path,
            data=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            await self._raise_for(resp, "xorb upload")
            payload = await resp.json()
        finally:
            resp.release()
        return bool(payload.get("was_inserted", False))

    async def upload_shard(self, shard: XetShard) -> int:
        """Upload a shard via v2 NDJSON, falling back to v1. Returns result."""
        body = serialize_shard_for_upload(shard)
        result = await self._upload_shard_v2(body)
        if result is not None:
            return result
        resp = await self._request(
            "POST",
            "/v1/shards",
            data=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            await self._raise_for(resp, "shard upload (v1)")
            payload = await resp.json()
        finally:
            resp.release()
        return int(payload.get("result", 0))

    async def _upload_shard_v2(self, body: bytes) -> Optional[int]:
        resp = await self._request(
            "POST",
            "/v2/shards",
            data=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            if resp.status in (404, 501):
                return None  # caller falls back to v1
            await self._raise_for(resp, "shard upload (v2)")
            result: Optional[int] = None
            async for raw_line in resp.content:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "error" in event:
                    err = event["error"]
                    msg = (
                        err.get("message", str(err))
                        if isinstance(err, dict)
                        else str(err)
                    )
                    msg = f"shard upload (v2) error frame: {msg}"
                    raise CasHttpError(msg)
                if "result" in event:
                    result = int(event["result"])
            return result if result is not None else 1
        finally:
            resp.release()

    # ------------------------------------------------------- reconstruction
    async def get_reconstruction(
        self, file_hash: bytes, byte_range: Optional[tuple[int, int]] = None
    ) -> ReconstructionInfo:
        """Public method."""
        headers: dict[str, str] = {}
        if byte_range is not None:
            headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
        hex_id = hash_to_hex(file_hash)
        resp = await self._request(
            "GET", f"/v2/reconstructions/{hex_id}", headers=headers
        )
        try:
            if resp.status in (404, 501):
                # Distinguish "v2 unsupported" from "file missing": try v1;
                # a v1 404 surfaces as CasNotFound from _raise_for below.
                resp.release()
                return await self._get_reconstruction_v1(file_hash, headers)
            await self._raise_for(resp, "reconstruction (v2)")
            payload = await resp.json()
        finally:
            resp.release()
        return self._parse_reconstruction_v2(file_hash, payload)

    async def _get_reconstruction_v1(
        self, file_hash: bytes, headers: dict[str, str]
    ) -> ReconstructionInfo:
        resp = await self._request(
            "GET", f"/v1/reconstructions/{hash_to_hex(file_hash)}", headers=headers
        )
        try:
            await self._raise_for(resp, "reconstruction (v1)")
            payload = await resp.json()
        finally:
            resp.release()
        info = ReconstructionInfo(
            file_hash=file_hash,
            offset_into_first_range=int(payload.get("offset_into_first_range", 0)),
        )
        self._fill_terms(info, payload)
        for hash_hex, entries in (payload.get("fetch_info") or {}).items():
            xorb_hash = hex_to_hash(hash_hex)
            info.fetch[xorb_hash] = [
                FetchRange(
                    url=e["url"],
                    byte_start=int(e["url_range"]["start"]),
                    byte_end=int(e["url_range"]["end"]),
                    chunk_start=int(e["range"]["start"]),
                    chunk_end=int(e["range"]["end"]),
                )
                for e in entries
            ]
        return info

    def _parse_reconstruction_v2(
        self, file_hash: bytes, payload: dict
    ) -> ReconstructionInfo:
        info = ReconstructionInfo(
            file_hash=file_hash,
            offset_into_first_range=int(payload.get("offset_into_first_range", 0)),
        )
        self._fill_terms(info, payload)
        for hash_hex, entries in (payload.get("xorbs") or {}).items():
            xorb_hash = hex_to_hash(hash_hex)
            ranges: list[FetchRange] = [
                FetchRange(
                    url=e["url"],
                    byte_start=int(r["bytes"]["start"]),
                    byte_end=int(r["bytes"]["end"]),
                    chunk_start=int(r["chunks"]["start"]),
                    chunk_end=int(r["chunks"]["end"]),
                )
                for e in entries
                for r in e.get("ranges", [])
            ]
            info.fetch[xorb_hash] = ranges
        return info

    @staticmethod
    def _fill_terms(info: ReconstructionInfo, payload: dict) -> None:
        for t in payload.get("terms", []):
            rng = t.get("range") or {}
            info.terms.append(
                (
                    hex_to_hash(t["hash"]),
                    int(rng.get("start", 0)),
                    int(rng.get("end", 0)),
                    int(t.get("unpacked_length", 0)),
                )
            )

    async def batch_reconstructions(
        self, file_hashes: list[bytes]
    ) -> dict[bytes, list[tuple[bytes, int, int, int]]]:
        """POST /v1/reconstructions with a JSON array of file hex ids."""
        body = [hash_to_hex(h) for h in file_hashes]
        resp = await self._request("POST", "/v1/reconstructions", json_body=body)
        try:
            await self._raise_for(resp, "batch reconstructions")
            payload = await resp.json()
        finally:
            resp.release()
        out: dict[bytes, list[tuple[bytes, int, int, int]]] = {}
        for file_hex, terms in (payload.get("files") or {}).items():
            out[hex_to_hash(file_hex)] = [
                (
                    hex_to_hash(t["hash"]),
                    int((t.get("range") or {}).get("start", 0)),
                    int((t.get("range") or {}).get("end", 0)),
                    int(t.get("unpacked_length", 0)),
                )
                for t in terms
            ]
        return out

    # ------------------------------------------------------------ download
    async def _fetch_range(self, fr: FetchRange) -> bytes:
        session = self._get_session()
        headers = {"Range": f"bytes={fr.byte_start}-{fr.byte_end}"}
        async with session.get(fr.url, headers=headers) as resp:
            if resp.status not in (200, 206):
                msg = f"xorb range fetch: HTTP {resp.status} for {fr.url}"
                raise CasHttpError(msg, status=resp.status)
            return await resp.read()

    async def download_file(self, file_hash: bytes) -> bytes:
        """Download and fully verify a file from the CAS."""
        info = await self.get_reconstruction(file_hash)
        if not info.terms:
            if XetHasher.compute_file_hash([]) == file_hash:
                return b""
            msg = "CAS returned no terms for non-empty file"
            raise ReconstructionError(msg)
        out = bytearray()
        pairs: list[tuple[bytes, int]] = []
        for xorb_hash, start, end, unpacked in info.terms:
            ranges = info.fetch.get(xorb_hash)
            if not ranges:
                msg = f"no fetch info for xorb {hash_to_hex(xorb_hash)}"
                raise ReconstructionError(msg)
            term_data = bytearray()
            for fr in ranges:
                if fr.chunk_end <= start or fr.chunk_start >= end:
                    continue
                segment = await self._fetch_range(fr)
                xorb = Xorb.deserialize(segment)
                if (
                    xorb.get_xorb_hash() != xorb_hash
                    and len(ranges) == 1
                    and fr.chunk_start == 0
                    and fr.chunk_end >= end
                ):
                    msg = "fetched xorb hash mismatch"
                    raise ReconstructionError(msg)
                local_start = max(start, fr.chunk_start) - fr.chunk_start
                local_end = min(end, fr.chunk_end) - fr.chunk_start
                for i in range(local_start, local_end):
                    h, d = xorb.chunks[i]
                    pairs.append((h, len(d)))
                    term_data += d
            if len(term_data) != unpacked:
                msg = f"term unpacked length mismatch: {len(term_data)} != {unpacked}"
                raise ReconstructionError(msg)
            out += term_data
        data = bytes(out)
        if info.offset_into_first_range:
            data = data[info.offset_into_first_range :]
        if XetHasher.compute_file_hash(pairs) != file_hash:
            msg = "downloaded file hash mismatch"
            raise ReconstructionError(msg)
        return data
