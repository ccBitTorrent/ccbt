#!/usr/bin/env python3
# ruff: noqa: D101, D102, D103, PERF203, PLC0415, PLR0912, PLR0915, S101, S105, S311, S603, S607, TRY300, UP045
"""Local live gate for the XET G9 claim flip (never run in CI).

Starts the real ccbt CAS/Hub servers on loopback, drives them with the
real hf_xet / huggingface_hub / git-lfs clients, optionally cross-tests
against a real external Xet CAS server (OpenXet), and writes an evidence
transcript. Exits non-zero if any gate step fails.

Examples:
    uv run python dev/scripts/run_xet_live_gate.py
    uv run python dev/scripts/run_xet_live_gate.py \
        --external-endpoint http://127.0.0.1:8080 --external-token TOKEN
    uv run python dev/scripts/run_xet_live_gate.py --provision-external ggoggam
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ccbt.discovery.xet_cas_http import CasHttpClient  # noqa: E402
from ccbt.storage.xet_chunking import GearhashChunker  # noqa: E402
from ccbt.storage.xet_hashing import XetHasher, hash_to_hex  # noqa: E402
from ccbt.storage.xet_shard import (  # noqa: E402
    FileInfo,
    FileTerm,
    XetShard,
    XorbChunkEntry,
    XorbInfo,
)
from ccbt.storage.xet_xorb import Xorb  # noqa: E402

WRITER_TOKEN = "writer-token"
FAR_FUTURE_EXP = 4611686018427387904


@dataclass
class Step:
    name: str
    status: str = "PASS"
    detail: str = ""
    seconds: float = 0.0


@dataclass
class Evidence:
    steps: list[Step] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)

    def record(self, name: str, fn) -> bool:
        print(f"[gate] {name} ...", flush=True)
        start = time.monotonic()
        try:
            detail = fn() or ""
        except Exception as exc:  # gate must report, not crash
            self.steps.append(
                Step(
                    name,
                    "FAIL",
                    f"{type(exc).__name__}: {exc}",
                    time.monotonic() - start,
                )
            )
            print(f"[gate] {name} FAIL: {exc}", flush=True)
            return False
        self.steps.append(Step(name, "PASS", str(detail), time.monotonic() - start))
        print(f"[gate] {name} PASS ({time.monotonic() - start:.1f}s)", flush=True)
        return True

    def ok(self) -> bool:
        return all(s.status == "PASS" for s in self.steps)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    last: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)  # noqa: S310 - loopback only
            return
        except Exception as exc:  # HTTPError still proves the server is up
            if exc.__class__.__name__ == "HTTPError":
                return
            last = exc
            time.sleep(0.2)
    msg = f"server at {url} did not come up: {last}"
    raise RuntimeError(msg)


def _payload(size: int = 3 * 1024 * 1024 + 12345) -> bytes:
    rng = random.Random(20261115)
    return (
        rng.randbytes(size // 2)
        + (b"ccbt-xet-live-gate " * (size // 38 + 1))[: size - size // 2]
    )


def _build(blob: bytes):
    chunks = GearhashChunker().chunk_buffer(blob)
    pairs = [(XetHasher.compute_chunk_hash(c), len(c)) for c in chunks]
    xorb = Xorb()
    for (_h, _s), chunk in zip(pairs, chunks):
        assert xorb.add_chunk(_h, chunk)
    info = FileInfo(
        file_hash=XetHasher.compute_file_hash(pairs),
        terms=[FileTerm(xorb.get_xorb_hash(), 0, len(blob), 0, len(chunks))],
        verification=[XetHasher.compute_range_hash([h for h, _ in pairs])],
    )
    shard = XetShard()
    shard.add_file_info(info)
    shard.add_xorb_info(
        XorbInfo(
            xorb.get_xorb_hash(),
            chunks=[XorbChunkEntry(h, 0, s) for h, s in pairs],
            num_bytes_on_disk=len(xorb.serialize()),
        )
    )
    return xorb, shard, info, pairs


async def _cas_roundtrip(
    base_url: str,
    token: Optional[str],
    blob: bytes,
    *,
    require_first_insert: bool = True,
) -> str:
    xorb, shard, info, pairs = _build(blob)
    client = CasHttpClient(base_url, token_provider=token)
    try:
        first_inserted = await client.upload_xorb(xorb)
        if require_first_insert:
            assert first_inserted is True, "first xorb upload not inserted"
        assert await client.upload_xorb(xorb) is False, "dedup re-upload inserted again"
        assert await client.upload_shard(shard) in (0, 1)
        assert await client.chunk_exists_remote(pairs[0][0]), (
            "global dedup query missed"
        )
        downloaded = await client.download_file(info.file_hash)
        assert downloaded == blob, "downloaded bytes differ"
        ranged = await client.get_reconstruction(info.file_hash, (0, 1023))
        assert ranged.terms, "ranged reconstruction returned no terms"
    finally:
        await client.close()
    return (
        f"file_hash={hash_to_hex(info.file_hash)} bytes={len(blob)} "
        f"chunks={len(pairs)} first_inserted={first_inserted}"
    )


_SERVER_LOG_HANDLES: list = []


def _start_server(kind: str, root: Path, port: int, log_dir: Path) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "ccbt.cli.main",
        kind,
        "serve",
        "--root",
        str(root),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--tokens",
        f"{WRITER_TOKEN}:read,write",
    ]
    # Log to a file, never a PIPE: a piped server blocks once the pipe
    # buffer fills with access logs and the gate hangs.
    log_dir.mkdir(parents=True, exist_ok=True)
    log_handle = (log_dir / f"{kind}-server.log").open("w", encoding="utf-8")
    _SERVER_LOG_HANDLES.append(log_handle)
    return subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=log_handle, stderr=subprocess.STDOUT, text=True
    )


def _hf_xet_roundtrip(
    endpoint: str, token: Optional[str], work: Path, blob: bytes
) -> str:
    import hf_xet

    src = work / "model.bin"
    src.write_bytes(blob)
    dest = work / "model.out.bin"
    cas = {
        "endpoint": endpoint,
        "token": token or "",
        "token_expiry_unix_secs": FAR_FUTURE_EXP,
    }
    session = hf_xet.XetSession()
    with session.new_upload_commit(**cas) as commit:
        upload = commit.start_upload_file(str(src))
    info = upload.result().xet_info
    with session.new_file_download_group(**cas) as group:
        group.start_download_file(
            hf_xet.XetFileInfo(info.hash, info.file_size), str(dest)
        )
    assert dest.read_bytes() == blob, "hf_xet download differs"
    return f"xet_hash={info.hash} bytes={info.file_size}"


def _hub_roundtrip(endpoint: str, work: Path, blob: bytes) -> str:
    import huggingface_hub

    api = huggingface_hub.HfApi(endpoint=endpoint, token=None)
    api.create_repo("alice/live-gate", repo_type="model", exist_ok=True)
    src = work / "hub-model.bin"
    src.write_bytes(blob)
    api.upload_file(
        path_or_fileobj=str(src),
        path_in_repo="hub-model.bin",
        repo_id="alice/live-gate",
        repo_type="model",
    )
    info = api.repo_info("alice/live-gate", repo_type="model")
    assert info.id == "alice/live-gate"
    downloaded = Path(
        huggingface_hub.hf_hub_download(
            "alice/live-gate",
            "hub-model.bin",
            repo_type="model",
            local_dir=str(work / "dl"),
            endpoint=endpoint,
        )
    )
    assert downloaded.read_bytes() == blob, "hub download differs"
    api.delete_repo("alice/live-gate", repo_type="model")
    return "repo=alice/live-gate upload+download byte-identical, repo deleted"


def _run(cmd: list[str], name: str, timeout: int = 1800) -> str:
    proc = subprocess.run(
        cmd, check=False, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-3000:]
        msg = f"{name} exited {proc.returncode}:\n{tail}"
        raise RuntimeError(msg)
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return lines[-1] if lines else "ok"


def _git_cmd_version(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=15
        ).stdout.strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def _provision_ggoggam(work: Path) -> tuple[str, Optional[str], subprocess.Popen]:
    clone = work / "ggoggam-openxet"
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/ggoggam/openxet.git",
            str(clone),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    sha = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    proc = subprocess.Popen(
        ["docker", "compose", "-f", "docker/compose.local.yaml", "up", "-d", "--build"],
        cwd=str(clone),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    endpoint = "http://127.0.0.1:8080"
    _wait_http(endpoint + "/v1/files", timeout=900)
    return endpoint, None, _ComposeCleanup(proc, clone, sha)


class _ComposeCleanup:
    def __init__(self, proc: subprocess.Popen, clone: Path, sha: str) -> None:
        self.proc = proc
        self.clone = clone
        self.sha = sha

    def terminate(self) -> None:
        subprocess.run(
            ["docker", "compose", "-f", "docker/compose.local.yaml", "down"],
            check=False,
            cwd=str(self.clone),
            capture_output=True,
            timeout=120,
        )


def _write_evidence(evidence: Evidence, args: argparse.Namespace) -> int:
    out = args.output or (ROOT / "xet-live-gate-evidence.txt")
    lines = ["XET live gate evidence", json.dumps(evidence.manifest, indent=2), ""]
    lines += [
        f"[{s.status}] {s.name} ({s.seconds:.1f}s) {s.detail}" for s in evidence.steps
    ]
    lines.append(f"OVERALL: {'PASS' if evidence.ok() else 'FAIL'}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"evidence written to {out}")
    return 0 if evidence.ok() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=None, help="evidence transcript path"
    )
    parser.add_argument(
        "--external-endpoint", default=os.environ.get("EXTERNAL_CAS_ENDPOINT")
    )
    parser.add_argument(
        "--external-token", default=os.environ.get("EXTERNAL_CAS_TOKEN")
    )
    parser.add_argument(
        "--external-note",
        default=None,
        help="free-text identity of the external CAS (repo URL + commit SHA)",
    )
    parser.add_argument(
        "--provision-external", choices=("none", "ggoggam", "stubbi"), default="none"
    )
    parser.add_argument("--skip-external", action="store_true")
    parser.add_argument("--skip-native", action="store_true")
    parser.add_argument("--skip-git", action="store_true")
    args = parser.parse_args()

    evidence = Evidence()
    try:
        import hf_xet
        import huggingface_hub

        hf_versions = (
            f"hf_xet={getattr(hf_xet, '__version__', 'unknown')} "
            f"huggingface_hub={huggingface_hub.__version__}"
        )
    except Exception as exc:
        hf_versions = f"unavailable: {exc}"
    evidence.manifest = {
        "commit": _git_cmd_version(["git", "rev-parse", "HEAD"]),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "hf": hf_versions,
        "git": _git_cmd_version(["git", "--version"]),
        "git_lfs": _git_cmd_version(["git", "lfs", "version"]),
        "docker": _git_cmd_version(["docker", "--version"]),
        "external_cas_endpoint": args.external_endpoint,
        "external_cas_note": args.external_note,
    }

    blob = _payload()
    blob_sha = hashlib.sha256(blob).hexdigest()
    servers: list[subprocess.Popen] = []
    external_cleanup = None
    with tempfile.TemporaryDirectory(
        prefix="xet-live-gate-", ignore_cleanup_errors=True
    ) as tmp:
        work = Path(tmp)
        cas_port, hub_port = _free_port(), _free_port()
        cas_url = f"http://127.0.0.1:{cas_port}"
        hub_url = f"http://127.0.0.1:{hub_port}"
        try:
            servers.append(_start_server("cas", work / "casroot", cas_port, work))
            servers.append(_start_server("hub", work / "hubroot", hub_port, work))
            if not evidence.record(
                "server-startup",
                lambda: (
                    _wait_http(cas_url + "/v1/reconstructions/" + "0" * 64),
                    _wait_http(hub_url + "/api/models/nope/nope"),
                    "cas+hub responding",
                )[-1],
            ):
                raise SystemExit(_write_evidence(evidence, args))

            evidence.record(
                "ccbt-cas-roundtrip",
                lambda: asyncio.run(_cas_roundtrip(cas_url, WRITER_TOKEN, blob))
                + f" sha256={blob_sha}",
            )
            evidence.record(
                "hf_xet-to-ccbt-cas",
                lambda: _hf_xet_roundtrip(cas_url, WRITER_TOKEN, work, blob),
            )
            evidence.record(
                "huggingface_hub-to-ccbt-hub",
                lambda: _hub_roundtrip(hub_url, work, blob),
            )
            if not args.skip_git:
                evidence.record(
                    "git-lfs-git-xet-roundtrip",
                    lambda: _run(
                        [
                            sys.executable,
                            "-m",
                            "pytest",
                            "-c",
                            "dev/pytest.ini",
                            "tests/unit/discovery/test_hub_git_xet.py::test_interop_git_xet_roundtrip",
                            "-q",
                            "--timeout=300",
                            "--timeout-method=thread",
                        ],
                        "git-xet pytest",
                        timeout=600,
                    ),
                )
            if not args.skip_native:
                evidence.record(
                    "native-golden-e2e-transport-consensus",
                    lambda: _run(
                        [
                            sys.executable,
                            "-m",
                            "pytest",
                            "-c",
                            "dev/pytest.ini",
                            "tests/unit/storage/test_xet_golden_codec.py",
                            "tests/integration/xet_e2e",
                            "tests/unit/session/test_xet_transport.py",
                            "tests/unit/consensus/test_consensus_raft_byzantine.py",
                            "-q",
                            "--timeout=600",
                            "--timeout-method=thread",
                        ],
                        "native pytest",
                        timeout=1800,
                    ),
                )

            endpoint = args.external_endpoint
            token = args.external_token
            if not args.skip_external:
                if endpoint is None and args.provision_external == "ggoggam":
                    endpoint, token, external_cleanup = _provision_ggoggam(work)
                elif endpoint is None and args.provision_external == "stubbi":
                    evidence.steps.append(
                        Step(
                            "external-cas-provision",
                            "FAIL",
                            "stubbi provisioning is manual: build stubbi/openxet "
                            "in a rust:1.97 Docker container, run `openxet serve "
                            "--port 0 --json`, then re-run with "
                            "--external-endpoint/--external-token",
                        )
                    )
                if endpoint:
                    evidence.record(
                        "ccbt-client-to-external-cas",
                        lambda: asyncio.run(
                            _cas_roundtrip(
                                endpoint, token, blob, require_first_insert=False
                            )
                        ),
                    )
                    evidence.record(
                        "hf_xet-to-external-cas",
                        lambda: _hf_xet_roundtrip(endpoint, token, work, blob),
                    )
                elif args.provision_external != "stubbi":
                    evidence.steps.append(
                        Step(
                            "external-cas",
                            "FAIL",
                            "no external endpoint: pass --external-endpoint or "
                            "--provision-external ggoggam (or --skip-external for a "
                            "loopback-only rehearsal, which cannot flip the gate)",
                        )
                    )
        finally:
            for proc in servers:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
            if external_cleanup is not None:
                external_cleanup.terminate()

    return _write_evidence(evidence, args)


if __name__ == "__main__":
    raise SystemExit(main())
