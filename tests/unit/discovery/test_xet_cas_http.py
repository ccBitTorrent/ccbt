"""Contract-fixture tests for the CAS HTTP client (WS3 gate).

The stub server implements exactly the routes/response shapes pinned
in openapi/cas.openapi.yaml (huggingface/xet-core, see
dev/xet-conformance.lock.json).
"""

from __future__ import annotations

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ccbt.discovery.xet_cas_http import (
    CasHttpClient,
    CasNotFound,
    CasRangeError,
    is_global_dedup_eligible,
)
from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_hashing import XetHasher, hash_to_hex, hex_to_hash
from ccbt.storage.xet_shard import (
    FileInfo,
    FileTerm,
    XorbChunkEntry,
    XetShard,
    XorbInfo,
)
from ccbt.storage.xet_xorb import Xorb


class StubCas:
    def __init__(self) -> None:
        self.xorbs: dict[bytes, bytes] = {}
        self.files: dict[bytes, FileInfo] = {}
        self.shards: list[XetShard] = []
        self.fail_v2_shards = False
        self.auth_token = "good-token"

    def _auth(self, request: web.Request, scope: str) -> web.Response | None:
        if request.headers.get("Authorization") != f"Bearer {self.auth_token}":
            return web.json_response({"error": "unauthorized"}, status=401)
        return None

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/v1/chunks/{prefix}/{hash}", self.get_chunk)
        app.router.add_post("/v1/xorbs/{prefix}/{hash}", self.post_xorb)
        app.router.add_post("/v1/shards", self.post_shard_v1)
        app.router.add_post("/v2/shards", self.post_shard_v2)
        app.router.add_get("/v2/reconstructions/{file_id}", self.get_recon_v2)
        app.router.add_get("/v1/reconstructions/{file_id}", self.get_recon_v1)
        app.router.add_post("/v1/reconstructions", self.post_recon_batch)
        app.router.add_get("/xorbs/{prefix}/{hash}", self.get_xorb_bytes)
        return app

    async def get_chunk(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "read")) is not None:
            return r
        chunk_hash = hex_to_hash(request.match_info["hash"])
        for shard in self.shards:
            if shard.chunk_dedup_query(chunk_hash):
                return web.Response(body=shard.serialize(hmac_key=b"s" * 32))
        return web.json_response({"error": "not found"}, status=404)

    async def post_xorb(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "write")) is not None:
            return r
        xorb_hash = hex_to_hash(request.match_info["hash"])
        body = await request.read()
        parsed = Xorb.deserialize(body)
        if parsed.get_xorb_hash() != xorb_hash:
            return web.json_response({"error": "hash mismatch"}, status=400)
        inserted = xorb_hash not in self.xorbs
        self.xorbs[xorb_hash] = body
        return web.json_response({"was_inserted": inserted})

    def _register_shard(self, body: bytes) -> None:
        from ccbt.storage.xet_shard import parse_shard

        shard = parse_shard(body)
        self.shards.append(shard)
        for f in shard.files:
            self.files[f.file_hash] = f

    async def post_shard_v1(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "write")) is not None:
            return r
        self._register_shard(await request.read())
        return web.json_response({"result": 1})

    async def post_shard_v2(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "write")) is not None:
            return r
        if self.fail_v2_shards:
            return web.json_response({"error": "v2 unsupported"}, status=501)
        self._register_shard(await request.read())
        resp = web.StreamResponse(headers={"Content-Type": "application/x-ndjson"})
        await resp.prepare(request)
        await resp.write(b'{"type": "validating", "verified": 1, "total": 1}\n')
        await resp.write(b'{"type": "committing", "stage": "syncing"}\n')
        await resp.write(b'{"type": "result"}\n')
        await resp.write_eof()
        return resp

    def _file_terms_json(self, info: FileInfo) -> list[dict]:
        return [
            {
                "hash": hash_to_hex(t.xorb_hash),
                "range": {"start": t.chunk_index_start, "end": t.chunk_index_end},
                "unpacked_length": t.unpacked_length,
            }
            for t in info.terms
        ]

    async def get_recon_v2(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "read")) is not None:
            return r
        file_hash = hex_to_hash(request.match_info["file_id"])
        info = self.files.get(file_hash)
        if info is None:
            return web.json_response({"error": "not found"}, status=404)
        total = info.total_length
        rng = request.headers.get("Range")
        if rng:
            start = int(rng.removeprefix("bytes=").split("-")[0])
            if start > total:
                return web.json_response({"error": "range"}, status=416)
        xorbs: dict[str, list[dict]] = {}
        base = str(request.url.origin())
        for t in info.terms:
            raw = self.xorbs[t.xorb_hash]
            ranges = Xorb.chunk_byte_ranges(raw)
            sel = ranges[t.chunk_index_start : t.chunk_index_end]
            xorbs[hash_to_hex(t.xorb_hash)] = [
                {
                    "url": f"{base}/xorbs/default/{hash_to_hex(t.xorb_hash)}",
                    "ranges": [
                        {
                            "chunks": {"start": t.chunk_index_start, "end": t.chunk_index_end},
                            "bytes": {"start": sel[0][0], "end": sel[-1][1] - 1},
                        }
                    ],
                }
            ]
        return web.json_response(
            {
                "offset_into_first_range": 0,
                "terms": self._file_terms_json(info),
                "xorbs": xorbs,
            }
        )

    async def get_recon_v1(self, request: web.Request) -> web.Response:
        resp = await self.get_recon_v2(request)
        if resp.status != 200:
            return resp
        import json as _json

        payload = _json.loads(resp.text)
        fetch_info = {}
        for h, entries in payload["xorbs"].items():
            fetch_info[h] = [
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
                "offset_into_first_range": payload["offset_into_first_range"],
                "terms": payload["terms"],
                "fetch_info": fetch_info,
            }
        )

    async def post_recon_batch(self, request: web.Request) -> web.Response:
        if (r := self._auth(request, "read")) is not None:
            return r
        ids = await request.json()
        files = {}
        for hex_id in ids:
            info = self.files.get(hex_to_hash(hex_id))
            if info is not None:
                files[hex_id] = self._file_terms_json(info)
        return web.json_response({"files": files, "fetch_info": {}})

    async def get_xorb_bytes(self, request: web.Request) -> web.Response:
        xorb_hash = hex_to_hash(request.match_info["hash"])
        raw = self.xorbs.get(xorb_hash)
        if raw is None:
            return web.json_response({"error": "not found"}, status=404)
        rng = request.headers.get("Range", "")
        if rng.startswith("bytes="):
            start_s, end_s = rng[6:].split("-")
            start, end = int(start_s), int(end_s)
            return web.Response(
                body=raw[start : end + 1], status=206,
                headers={"Content-Range": f"bytes {start}-{end}/{len(raw)}"},
            )
        return web.Response(body=raw)


def _build_file(blob: bytes) -> tuple[Xorb, XetShard, FileInfo]:
    chunks = GearhashChunker().chunk_buffer(blob)
    pairs = [(XetHasher.compute_chunk_hash(c), len(c)) for c in chunks]
    xorb = Xorb()
    for (h, _s), c in zip(pairs, chunks):
        assert xorb.add_chunk(h, c)
    info = FileInfo(
        file_hash=XetHasher.compute_file_hash(pairs),
        terms=[FileTerm(xorb.get_xorb_hash(), 0, len(blob), 0, len(chunks))],
        verification=[XetHasher.compute_range_hash([h for h, _ in pairs])],
    )
    shard = XetShard()
    shard.add_file_info(info)
    shard.add_xorb_info(
        XorbInfo(
            xorb_hash=xorb.get_xorb_hash(),
            chunks=[XorbChunkEntry(h, 0, s) for h, s in pairs],
            num_bytes_on_disk=len(xorb.serialize()),
        )
    )
    return xorb, shard, info


@pytest.fixture()
async def stub():
    cas = StubCas()
    client = TestClient(TestServer(cas.app()))
    await client.start_server()
    yield cas, client
    await client.close()


def _client_for(test_client: TestClient, token: str = "good-token") -> CasHttpClient:
    return CasHttpClient(str(test_client.make_url("/")).rstrip("/"), token_provider=token)


async def test_interop_cas_contract_fixtures(stub) -> None:
    cas, tc = stub
    blob = bytes(range(256)) * 1500
    xorb, shard, info = _build_file(blob)
    client = _client_for(tc)
    try:
        # Xorb upload: inserted once, then dedup'd
        assert await client.upload_xorb(xorb) is True
        assert await client.upload_xorb(xorb) is False
        # Shard upload via v2 NDJSON
        assert await client.upload_shard(shard) == 1
        # Global dedup query finds first chunk; unknown chunk 404 -> False
        assert await client.chunk_exists_remote(info.terms and shard.xorbs[0].chunks[0].chunk_hash)
        unknown = XetHasher.compute_chunk_hash(b"never uploaded")
        assert await client.chunk_exists_remote(unknown) is False
        # Reconstruction + verified download
        recon = await client.get_reconstruction(info.file_hash)
        assert recon.terms[0][0] == info.terms[0].xorb_hash
        assert await client.download_file(info.file_hash) == blob
        # Batch reconstructions
        batch = await client.batch_reconstructions([info.file_hash, bytes(32)])
        assert info.file_hash in batch
        # Missing file -> 404
        with pytest.raises(CasNotFound):
            await client.get_reconstruction(XetHasher.compute_file_hash([(bytes(32), 1)]))
        # Range past EOF -> 416
        with pytest.raises(CasRangeError):
            await client.get_reconstruction(info.file_hash, byte_range=(10**9, 10**9 + 10))
    finally:
        await client.close()


async def test_interop_cas_shard_v1_fallback(stub) -> None:
    cas, tc = stub
    cas.fail_v2_shards = True
    _xorb, shard, _info = _build_file(b"fallback shard content" * 500)
    client = _client_for(tc)
    try:
        assert await client.upload_shard(shard) == 1
        assert cas.shards  # registered via v1
    finally:
        await client.close()


async def test_interop_cas_auth_refresh(stub) -> None:
    cas, tc = stub
    _xorb, shard, info = _build_file(b"auth refresh" * 400)
    calls = {"n": 0}

    def flaky_token() -> str:
        calls["n"] += 1
        return "bad-token" if calls["n"] == 1 else "good-token"

    client = CasHttpClient(str(tc.make_url("/")).rstrip("/"), token_provider=flaky_token)
    try:
        assert await client.upload_shard(shard) == 1
        assert calls["n"] >= 2  # refreshed after 401
    finally:
        await client.close()


def test_global_dedup_eligibility_rule() -> None:
    h = XetHasher.compute_chunk_hash(b"anything")
    assert is_global_dedup_eligible(h, is_first_chunk=True)
    from ccbt.storage.xet_hashing import truncate_hash

    assert is_global_dedup_eligible(h) == (truncate_hash(h) % 1024 == 0)
