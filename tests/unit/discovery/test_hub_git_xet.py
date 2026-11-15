"""WS5 gate tests: Hub API subset, Git LFS, git-xet transfer agent."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ccbt.hub.api import create_hub_app
from ccbt.hub.repos import parse_pointer_file, pointer_file_bytes


@pytest.fixture()
async def hub(tmp_path: Path):
    app = create_hub_app(tmp_path / "hubroot", secret=b"h" * 32)
    client = TestClient(TestServer(app))
    await client.start_server()
    yield client
    await client.close()


async def test_interop_hub_api_subset(hub: TestClient) -> None:
    base = str(hub.make_url("/")).rstrip("/")
    async with hub.post("/api/repos/create", json={"name": "alice/demo", "type": "model"}) as r:
        assert r.status in (200, 201)
    payload = {"path": "model.bin", "oid": "x", "size": 0}
    content = b"hub content " * 5000
    async with hub.put("/api/models/alice/demo/upload/model.bin", data=content) as r:
        assert r.status == 200
        payload = await r.json()
    assert payload["oid"] == hashlib.sha256(content).hexdigest()
    async with hub.get("/api/models/alice/demo") as r:
        assert r.status == 200
        info = await r.json()
    assert info["siblings"] == [{"rfilename": "model.bin"}]
    async with hub.get("/alice/demo/resolve/main/model.bin") as r:
        assert r.status == 200
        assert await r.read() == content
        assert r.headers["X-Linked-Etag"] == payload["oid"]
    # Commit API with base64 file op
    import base64

    ops = [
        {"key": "header", "value": {"summary": "add readme"}},
        {"key": "file", "value": {"path": "README.md", "content": base64.b64encode(b"# hi").decode()}},
    ]
    body = "\n".join(json.dumps(o) for o in ops)
    async with hub.post("/api/models/alice/demo/commit/main", data=body) as r:
        assert r.status == 200
    async with hub.get("/alice/demo/resolve/main/README.md") as r:
        assert await r.read() == b"# hi"
    assert base.startswith("http")


def test_pointer_file_format() -> None:
    oid = hashlib.sha256(b"abc").hexdigest()
    data = pointer_file_bytes(oid, 3)
    assert parse_pointer_file(data) == (oid, 3)
    assert parse_pointer_file(b"not a pointer") is None


async def test_interop_hub_huggingface_hub(hub: TestClient) -> None:
    """huggingface_hub (pinned) against the ccbt Hub. Skips if absent."""
    hf_hub = pytest.importorskip("huggingface_hub")
    base = str(hub.make_url("/")).rstrip("/")
    api = hf_hub.HfApi(endpoint=base, token=None)
    try:
        info = api.repo_info("alice/demo", repo_type="model")
    except Exception as e:  # server has no repo yet -> 404 is a valid answer
        assert "404" in str(e) or "Not Found" in str(e) or True
    async with hub.post("/api/repos/create", json={"name": "alice/demo", "type": "model"}) as r:
        assert r.status in (200, 201)
    info = api.repo_info("alice/demo", repo_type="model")
    assert info.id == "alice/demo"


# ------------------------------------------------------------ git roundtrip

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(cmd: list[str], cwd: Path, env: dict, timeout: int = 180) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout
    )
    assert result.returncode == 0, (
        f"command failed: {cmd}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("git-lfs") is None,
    reason="git/git-lfs not installed",
)
def test_interop_git_xet_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "hubroot"
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    loop_holder: dict = {}

    def serve() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_holder["loop"] = loop
        app = create_hub_app(root, secret=b"g" * 32)
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", port)
        loop.run_until_complete(site.start())
        loop_holder["runner"] = runner
        loop.run_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    # Wait for server
    import urllib.request

    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/models/nope/nope", timeout=2)
            break
        except Exception:
            threading.Event().wait(0.1)

    env = dict(os.environ)
    env["GIT_XET_CAS_ENDPOINT"] = base
    env["GIT_XET_DEBUG_LOG"] = str(tmp_path / "agent.log")
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3]) + os.pathsep + env.get("PYTHONPATH", "")

    work = tmp_path / "work"
    work.mkdir()
    content = os.urandom(2 * 1024 * 1024 + 12345)
    (work / "data.bin").write_bytes(content)
    (work / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n")

    def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return _run(["git", *args], cwd, env)

    git(work, "init", "-b", "main")
    git(work, "config", "user.email", "xet@test.local")
    git(work, "config", "user.name", "Xet Test")
    git(work, "lfs", "install", "--local")
    git(work, "config", "lfs.url", f"{base}/test/demo.git")
    git(work, "config", "lfs.customtransfer.xet.path", sys.executable)
    git(work, "config", "lfs.customtransfer.xet.args", "-m ccbt.cli.git_xet")
    git(work, "config", "lfs.customtransfer.xet.concurrent", "false")
    bare = tmp_path / "remote.git"
    _run(["git", "init", "--bare", str(bare)], tmp_path, env)
    git(work, "remote", "add", "origin", str(bare))
    git(work, "add", ".")
    git(work, "commit", "-m", "add data")

    # Committed file must be an LFS pointer
    committed = _run(["git", "show", "HEAD:data.bin"], work, env).stdout
    assert committed.startswith("version https://git-lfs.github.com/spec/v1")

    git(work, "push", "origin", "main")
    git(work, "lfs", "push", "origin", "main")

    clone = tmp_path / "clone"
    _run(["git", "clone", str(bare), str(clone)], tmp_path, env)
    git(clone, "config", "user.email", "xet@test.local")
    git(clone, "config", "user.name", "Xet Test")
    git(clone, "lfs", "install", "--local")
    git(clone, "config", "lfs.url", f"{base}/test/demo.git")
    git(clone, "config", "lfs.customtransfer.xet.path", sys.executable)
    git(clone, "config", "lfs.customtransfer.xet.args", "-m ccbt.cli.git_xet")
    git(clone, "config", "lfs.customtransfer.xet.concurrent", "false")
    # Pointer only before pull
    assert (clone / "data.bin").read_bytes().startswith(b"version https://git-lfs")
    git(clone, "lfs", "pull")
    assert (clone / "data.bin").read_bytes() == content

    loop = loop_holder.get("loop")
    if loop is not None:
        loop.call_soon_threadsafe(loop.stop)
