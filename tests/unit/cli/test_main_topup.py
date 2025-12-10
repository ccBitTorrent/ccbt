"""Top-up tests to push ccbt.cli.main coverage further, aligned with code."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace, ModuleType
from typing import Any
import sys

import pytest
from click.testing import CliRunner

import importlib
cli_main = importlib.import_module("ccbt.cli.main")


pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_debug_error_path(monkeypatch):
    runner = CliRunner()

    def _cm_raise(*_a, **_k):
        raise RuntimeError("dbg-err")

    monkeypatch.setattr(cli_main, "ConfigManager", _cm_raise)
    result = runner.invoke(cli_main.cli, ["debug"]) 
    assert result.exit_code != 0
    assert "Error: dbg-err" in result.output


def test_resume_cli_success_with_checkpoint(monkeypatch):
    runner = CliRunner()

    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _CP:
        torrent_name = "t"
        verified_pieces: list[int] = []
        total_pieces = 0
        torrent_file_path = "t.torrent"
        magnet_uri = None

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    fake_mod = ModuleType("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    # Minimal session and resume_download pass-through
    class _Sess:
        pass

    async def _resume_download(*_a, **_k):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Sess())
    monkeypatch.setattr(cli_main, "resume_download", _resume_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    ih = (b"\x00" * 20).hex()
    result = runner.invoke(cli_main.cli, ["resume", ih]) 
    assert result.exit_code == 0


def test_resume_invalid_hex_and_no_checkpoint(monkeypatch):
    runner = CliRunner()

    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return None

    fake_mod = ModuleType("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    # invalid hex
    bad = runner.invoke(cli_main.cli, ["resume", "not-hex"]) 
    assert bad.exit_code != 0
    assert "Invalid info hash format" in bad.output

    # valid hex but no checkpoint
    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: object())
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)
    okhex = runner.invoke(cli_main.cli, ["resume", (b"\x00" * 20).hex()]) 
    assert okhex.exit_code != 0
    assert "No checkpoint found" in okhex.output


def test_resume_cannot_auto_resume(monkeypatch):
    runner = CliRunner()
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _CP:
        torrent_name = "t"
        verified_pieces: list[int] = []
        total_pieces = 0
        torrent_file_path = None
        magnet_uri = None

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    fake_mod = ModuleType("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: object())
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)
    res = runner.invoke(cli_main.cli, ["resume", (b"\x00" * 20).hex()]) 
    assert res.exit_code != 0
    assert "cannot be auto-resumed" in res.output


def test_magnet_interactive_path(monkeypatch):
    runner = CliRunner()
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=False, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr:
        def parse_magnet_link(self, _link: str):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _start_interactive(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_interactive_download", _start_interactive)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    res = runner.invoke(cli_main.cli, ["magnet", "magnet:?xt=urn:btih:abc", "-i"]) 
    assert res.exit_code == 0


def test_download_interactive_path(monkeypatch):
    runner = CliRunner()
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=False, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr:
        def load_torrent(self, _path):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _start_interactive(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_interactive_download", _start_interactive)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    res = runner.invoke(cli_main.cli, ["download", __file__, "-i"]) 
    assert res.exit_code == 0


def test_download_file_not_found_path(monkeypatch):
    runner = CliRunner()
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr:
        def load_torrent(self, _path):
            raise FileNotFoundError("missing.torrent")

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    res = runner.invoke(cli_main.cli, ["download", __file__]) 
    assert res.exit_code != 0
    assert "File not found" in res.output


def test_resume_download_stop_warning(monkeypatch, capsys):
    ih = (b"\x00" * 20).hex()

    class _Sess:
        async def start(self):
            return None

        async def stop(self):
            raise RuntimeError("stop err")

        async def resume_from_checkpoint(self, *_a, **_k):
            return ih

        async def get_torrent_status(self, *_a, **_k):
            return None

    cp = SimpleNamespace(torrent_name="t")
    console = cli_main.Console()
    _run_coro_locally(cli_main.resume_download(_Sess(), bytes.fromhex(ih), cp, False, console))  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Warning: Error stopping session" in out


def test_debug_happy_path(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)

    class _Sess:
        pass

    async def _start_debug(_s, _c):
        # Matches default implementation which prints a message
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Sess())
    monkeypatch.setattr(cli_main, "start_debug_mode", _start_debug)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)
    res = runner.invoke(cli_main.cli, ["debug"]) 
    assert res.exit_code == 0


def test_resume_download_interactive_branch(monkeypatch):
    ih = (b"\x00" * 20).hex()

    class _Sess:
        async def start(self):
            return None

        async def stop(self):
            return None

        async def resume_from_checkpoint(self, *_a, **_k):
            return ih

        async def get_torrent_status(self, *_a, **_k):
            return None

    class _FakeInteractive:
        def __init__(self, *_a, **_k):
            pass

        async def run(self):
            return None

    cp = SimpleNamespace(torrent_name="t")
    console = cli_main.Console()
    monkeypatch.setattr(cli_main, "InteractiveCLI", _FakeInteractive)
    _run_coro_locally(cli_main.resume_download(_Sess(), bytes.fromhex(ih), cp, True, console))  # type: ignore[arg-type]


def test_start_basic_download_with_object_torrent_data(monkeypatch):
    class _Sess:
        def __init__(self):
            self.calls = 0
            # Use bytes keys like real AsyncSessionManager
            self.torrents: dict[bytes, Any] = {}
            self.lock = asyncio.Lock()
            
        async def add_torrent(self, torrent_data, resume=False):
            """Mock add_torrent that populates torrents dict."""
            from unittest.mock import AsyncMock
            info_hash = b"\x00" * 20
            info_hash_hex = info_hash.hex()
            # Create mock torrent session
            mock_session = AsyncMock()
            mock_session.file_selection_manager = None
            self.torrents[info_hash] = mock_session
            return info_hash_hex

        async def get_torrent_status(self, *_a, **_k):
            self.calls += 1
            if self.calls == 1:
                return {"progress": 1.0, "status": "seeding"}
            return None

    class _TObj:
        name = "t"

    console = cli_main.Console()
    _run_coro_locally(cli_main.start_basic_download(_Sess(), _TObj(), console))  # type: ignore[arg-type]



