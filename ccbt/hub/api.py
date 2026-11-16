"""Hub API (huggingface_hub subset) + Git LFS endpoints, composed with CAS.

One aiohttp app serves:
- CAS routes (ccbt.cas_server.routes)
- Hub routes: POST /api/repos/create, GET /api/{models|datasets|spaces}/{id},
  GET .../tree/{revision}, GET /{repo}/resolve/{revision}/{path},
  PUT .../upload/{path}, POST .../commit/{revision} (base64 + LFS ops)
- Git LFS: POST /{repo}.git/info/lfs/objects/batch,
  PUT/GET /lfs-objects/{oid}, POST /lfs-objects/{oid}/verify
- Xet transfer endpoints used by the git-xet agent:
  GET /api/xet-transfer/{repo}/download/{oid} -> {xet_file_hash,...}
  POST /api/xet-transfer/{repo}/upload/{oid}  {xet_file_hash, size}
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

from aiohttp import web

from ccbt.cas_server.auth import TokenAuth
from ccbt.cas_server.routes import AUTH_KEY, SECRET_KEY, STORE_KEY, register_routes
from ccbt.cas_server.store import CasStore
from ccbt.hub.lfs import LFS_CONTENT_TYPE, build_batch_response, verify_object_request
from ccbt.hub.repos import RepoFile, RepoStore, repo_type_path
from ccbt.storage.xet_hashing import hex_to_hash
from ccbt.storage.xet_reconstruction import reconstruct_verified

REPOS_KEY = web.AppKey("hub_repos", RepoStore)


def _err(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _repos(request: web.Request) -> RepoStore:
    return request.config_dict[REPOS_KEY]  # type: ignore[return-value]


def _repo_id(request: web.Request) -> str:
    namespace = request.match_info.get("namespace")
    name = request.match_info["name"]
    return f"{namespace}/{name}" if namespace else name


# -------------------------------------------------------------- hub repos
def _payload_repo_id(payload: dict) -> Optional[str]:
    """Resolve repo id from hub client payloads (name + organization split)."""
    name = payload.get("name") or payload.get("repo_id")
    organization = payload.get("organization") or payload.get("namespace")
    if name and organization and "/" not in str(name):
        return f"{organization}/{name}"
    return str(name) if name else None


async def delete_repo(request: web.Request) -> web.Response:
    """Public function."""
    try:
        payload = await request.json()
    except Exception:
        return _err("expected JSON body", 400)
    repo_id = _payload_repo_id(payload)
    if not repo_id:
        return _err("name is required", 400)
    if not _repos(request).delete_repo(repo_id):
        return _err("repo not found", 404)
    return web.json_response({"id": repo_id, "deleted": True})


async def create_repo(request: web.Request) -> web.Response:
    """Public function."""
    try:
        payload = await request.json()
    except Exception:
        return _err("expected JSON body", 400)
    # Modern huggingface_hub sends {"name": ..., "organization": ...}
    # separately; older clients send a single "namespace/name" string.
    name = _payload_repo_id(payload)
    if not name:
        return _err("name is required", 400)
    repo_type = payload.get("type", "model")
    try:
        repo_type_path(repo_type)
    except ValueError as e:
        return _err(str(e), 400)
    store = _repos(request)
    created = store.create_repo(name, repo_type, bool(payload.get("private", False)))
    base = str(request.url.origin())
    # huggingface_hub parses the returned url as a repo page URL
    # ({base}/{namespace}/{name}); an /api/... URL is rejected as an
    # invalid HF URI by newer hub versions.
    return web.json_response(
        {"id": name, "url": f"{base}/{name}"},
        status=201 if created else 200,
    )


async def repo_info(request: web.Request) -> web.Response:
    """Public function."""
    store = _repos(request)
    repo_id = _repo_id(request)
    if not store.repo_exists(repo_id):
        return _err("repo not found", 404)
    files = store.list_files(repo_id)
    return web.json_response(
        {
            "id": repo_id,
            "sha": "main",
            "siblings": [{"rfilename": f.path} for f in files],
            "private": False,
        }
    )


async def preupload(request: web.Request) -> web.Response:
    """huggingface_hub upload-mode probe (POST .../preupload/{revision}).

    Every file is answered "regular": content then arrives inline in the
    commit NDJSON, which `commit` already handles. The Xet/LFS transfer
    paths are exercised separately (hf_xet against the CAS, git-lfs with
    the git-xet agent), so they are not negotiated here.
    """
    store = _repos(request)
    repo_id = _repo_id(request)
    if not store.repo_exists(repo_id):
        return _err("repo not found", 404)
    try:
        payload = await request.json()
    except Exception:
        return _err("expected JSON body", 400)
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        return _err("files must be a list", 400)
    out = [
        {
            "path": str(f.get("path", "")),
            "uploadMode": "regular",
            "shouldIgnore": False,
        }
        for f in files
        if isinstance(f, dict)
    ]
    return web.json_response({"files": out})


async def repo_tree(request: web.Request) -> web.Response:
    """Public function."""
    store = _repos(request)
    repo_id = _repo_id(request)
    if not store.repo_exists(repo_id):
        return _err("repo not found", 404)
    out = []
    for f in store.list_files(repo_id):
        entry = {
            "type": "file",
            "path": f.path,
            "size": f.size,
            "oid": f.oid,
        }
        if f.size > 1024:  # huggingface_hub treats large files as LFS
            entry["lfs"] = {"oid": f.oid, "size": f.size}
        out.append(entry)
    return web.json_response(out)


async def upload_file_simple(request: web.Request) -> web.Response:
    """Public function."""
    store = _repos(request)
    repo_id = _repo_id(request)
    path = request.match_info["path"]
    data = await request.read()
    oid = hashlib.sha256(data).hexdigest()
    store.put_object_bytes(oid, data)
    store.put_file(repo_id, RepoFile(path=path, oid=oid, size=len(data)))
    return web.json_response({"path": path, "oid": oid, "size": len(data)})


async def commit(request: web.Request) -> web.Response:
    """Minimal commit endpoint: NDJSON header + file/lfsFile/deletedFile ops."""
    store = _repos(request)
    repo_id = _repo_id(request)
    store.ensure_repo(repo_id)
    body = (await request.read()).decode("utf-8", errors="replace")
    changed = 0
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            op = json.loads(line)
        except json.JSONDecodeError:
            return _err("invalid NDJSON in commit body", 400)
        key = op.get("key")
        value = op.get("value") or {}
        if key == "header":
            continue
        if key == "file":
            try:
                content = base64.b64decode(value.get("content", ""), validate=True)
            except (binascii.Error, ValueError):
                return _err("invalid base64 file content", 400)
            oid = hashlib.sha256(content).hexdigest()
            store.put_object_bytes(oid, content)
            store.put_file(
                repo_id, RepoFile(path=value["path"], oid=oid, size=len(content))
            )
            changed += 1
        elif key == "lfsFile":
            oid = str(value.get("oid", ""))
            info = store.get_object_info(oid)
            if info is None:
                return _err(f"LFS object {oid} not uploaded", 400)
            store.put_file(
                repo_id,
                RepoFile(
                    path=value["path"], oid=oid, size=info[0], xet_file_hash=info[1]
                ),
            )
            changed += 1
        elif key == "deletedFile":
            continue  # deletions tracked in WS8-style tombstones; accept + ignore here
        else:
            return _err(f"unsupported commit operation: {key}", 400)
    # huggingface_hub requires commitUrl + commitOid in the response.
    commit_oid = hashlib.sha256(body.encode("utf-8")).hexdigest()
    base = str(request.url.origin())
    return web.json_response(
        {
            "commitOid": commit_oid,
            "commitUrl": f"{base}/{repo_id}/commit/{commit_oid}",
            "changed": changed,
        }
    )


async def resolve_file(request: web.Request) -> web.Response:
    """Public function."""
    store = _repos(request)
    repo_id = _repo_id(request)
    path = request.match_info["path"]
    entry = store.get_file(repo_id, path)
    if entry is None:
        return _err("file not found", 404)
    data = store.get_object_bytes(entry.oid)
    if data is None and entry.xet_file_hash:
        # Reconstruct from CAS on demand.
        cas: CasStore = request.config_dict[STORE_KEY]  # type: ignore[assignment]
        shard = cas.shard_for_file(hex_to_hash(entry.xet_file_hash))
        if shard is not None:
            info = shard.get_file_reconstruction(hex_to_hash(entry.xet_file_hash))
            if info is not None:

                def fetch(xorb_hash: bytes) -> bytes:
                    raw = cas.get_xorb(xorb_hash)
                    if raw is None:
                        msg = "xorb missing"
                        raise ValueError(msg)
                    return raw

                data = reconstruct_verified(info, fetch)
    if data is None:
        return _err("file content unavailable", 404)
    return web.Response(
        body=data,
        headers={
            "X-Linked-Etag": entry.oid,
            "X-Repo-Commit": entry.oid,
            "ETag": entry.oid,
            "Content-Length": str(len(data)),
        },
        content_type="application/octet-stream",
    )


# ------------------------------------------------------------------- LFS
async def lfs_batch(request: web.Request) -> web.Response:
    """Public function."""
    repo_id = request.match_info["repo_id"]
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"message": "expected JSON"}, status=400)
    store = _repos(request)
    store.ensure_repo(repo_id)
    status, out = build_batch_response(
        store, repo_id, str(request.url.origin()), payload
    )
    return web.json_response(out, status=status, content_type=LFS_CONTENT_TYPE)


async def lfs_put_object(request: web.Request) -> web.Response:
    """Public function."""
    oid = request.match_info["oid"]
    data = await request.read()
    try:
        _repos(request).put_object_bytes(oid, data)
    except ValueError as e:
        return _err(str(e), 422)
    return web.Response(status=200)


async def lfs_get_object(request: web.Request) -> web.Response:
    """Public function."""
    oid = request.match_info["oid"]
    store = _repos(request)
    data = store.get_object_bytes(oid)
    if data is None:
        info = store.get_object_info(oid)
        if info is not None and info[1]:
            # Content lives in CAS; bytes are not mirrored locally.
            return _err("object stored in CAS; use xet transfer", 409)
        return _err("object not found", 404)
    return web.Response(body=data, content_type="application/octet-stream")


async def lfs_verify_object(request: web.Request) -> web.Response:
    """Public function."""
    oid = request.match_info["oid"]
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    error = verify_object_request(
        _repos(request), oid, payload.get("size") if isinstance(payload, dict) else None
    )
    if error:
        return _err(error, 422)
    return web.Response(status=200)


# --------------------------------------------------------- xet transfer
async def xet_transfer_download_info(request: web.Request) -> web.Response:
    """Public function."""
    repo_id = request.match_info["repo_id"]
    oid = request.match_info["oid"]
    store = _repos(request)
    info = store.get_object_info(oid)
    entry = store.find_file_by_oid(repo_id, oid)
    xet_hash = (info[1] if info else None) or (entry.xet_file_hash if entry else None)
    size = (info[0] if info else None) or (entry.size if entry else None)
    if not xet_hash:
        return _err("object not available via xet", 404)
    return web.json_response({"oid": oid, "xet_file_hash": xet_hash, "size": size})


async def xet_transfer_upload_register(request: web.Request) -> web.Response:
    """Public function."""
    repo_id = request.match_info["repo_id"]
    oid = request.match_info["oid"]
    try:
        payload = await request.json()
    except Exception:
        return _err("expected JSON {xet_file_hash, size}", 400)
    xet_hash = payload.get("xet_file_hash")
    size = int(payload.get("size", 0))
    if not xet_hash:
        return _err("xet_file_hash required", 400)
    store = _repos(request)
    cas: CasStore = request.config_dict[STORE_KEY]  # type: ignore[assignment]
    try:
        file_hash = hex_to_hash(str(xet_hash))
    except ValueError:
        return _err("malformed xet_file_hash", 400)
    if cas.get_file_info(file_hash) is None:
        return _err("xet file not present in CAS (upload shard first)", 422)
    store.ensure_repo(repo_id)
    store.register_object(oid, size, xet_file_hash=str(xet_hash))
    path = payload.get("path")
    if path:
        store.put_file(
            repo_id,
            RepoFile(path=str(path), oid=oid, size=size, xet_file_hash=str(xet_hash)),
        )
    return web.json_response({"oid": oid, "xet_file_hash": xet_hash, "size": size})


def register_hub_routes(app: web.Application) -> None:
    """Public function."""
    app.router.add_post("/api/repos/create", create_repo)
    app.router.add_delete("/api/repos/delete", delete_repo)
    app.router.add_post("/api/repos/delete", delete_repo)
    for prefix in ("models", "datasets", "spaces"):
        app.router.add_get(f"/api/{prefix}/{{namespace}}/{{name}}", repo_info)
        app.router.add_get(f"/api/{prefix}/{{name}}", repo_info)
        app.router.add_get(
            f"/api/{prefix}/{{namespace}}/{{name}}/tree/{{revision}}", repo_tree
        )
        app.router.add_get(f"/api/{prefix}/{{name}}/tree/{{revision}}", repo_tree)
        app.router.add_put(
            f"/api/{prefix}/{{namespace}}/{{name}}/upload/{{path:.*}}",
            upload_file_simple,
        )
        app.router.add_put(
            f"/api/{prefix}/{{name}}/upload/{{path:.*}}", upload_file_simple
        )
        app.router.add_post(
            f"/api/{prefix}/{{namespace}}/{{name}}/commit/{{revision}}", commit
        )
        app.router.add_post(f"/api/{prefix}/{{name}}/commit/{{revision}}", commit)
        app.router.add_post(
            f"/api/{prefix}/{{namespace}}/{{name}}/preupload/{{revision}}", preupload
        )
        app.router.add_post(f"/api/{prefix}/{{name}}/preupload/{{revision}}", preupload)
    app.router.add_get("/{namespace}/{name}/resolve/{revision}/{path:.*}", resolve_file)
    app.router.add_get("/{name}/resolve/{revision}/{path:.*}", resolve_file)
    # Git LFS (git-lfs derives several URL shapes depending on config)
    app.router.add_post("/{repo_id:.+}.git/info/lfs/objects/batch", lfs_batch)
    app.router.add_post("/{repo_id:.+}.git/objects/batch", lfs_batch)
    app.router.add_post("/{repo_id:.+}/info/lfs/objects/batch", lfs_batch)
    app.router.add_put("/lfs-objects/{oid}", lfs_put_object)
    app.router.add_get("/lfs-objects/{oid}", lfs_get_object)
    app.router.add_post("/lfs-objects/{oid}/verify", lfs_verify_object)
    # git-xet agent endpoints
    app.router.add_get(
        "/api/xet-transfer/{repo_id:.+}/download/{oid}", xet_transfer_download_info
    )
    app.router.add_post(
        "/api/xet-transfer/{repo_id:.+}/upload/{oid}", xet_transfer_upload_register
    )


def create_hub_app(
    root: Path,
    *,
    tokens: Optional[dict[str, set[str]]] = None,
    secret: Optional[bytes] = None,
) -> web.Application:
    """Public function."""
    root = Path(root)
    app = web.Application(client_max_size=1024 * 1024 * 1024)
    cas_store = CasStore(root / "cas")
    repo_store = RepoStore(root / "hub")
    app[STORE_KEY] = cas_store
    app[REPOS_KEY] = repo_store
    app[AUTH_KEY] = TokenAuth(tokens)
    app[SECRET_KEY] = secret or secrets.token_bytes(32)

    async def _close(_app: web.Application) -> None:
        cas_store.close()
        repo_store.close()

    app.on_cleanup.append(_close)
    register_routes(app)
    register_hub_routes(app)
    return app
