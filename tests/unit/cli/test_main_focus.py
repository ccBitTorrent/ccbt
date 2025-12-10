"""Focused tests to raise coverage for ccbt.cli.main.

Covers:
- status/debug happy path and error handling
- magnet invalid link error guard
- download checkpoint non-interactive branch
- web command: guard against un-awaited coroutine when start_web_interface is mocked
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace, ModuleType
from typing import Any

import pytest
from click.testing import CliRunner

import importlib
cli_main = importlib.import_module("ccbt.cli.main")


pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeSession:
    def __init__(self) -> None:
        # Minimal attributes for show_status
        self.config = SimpleNamespace(
            network=SimpleNamespace(
                listen_port=6881,
                enable_utp=False,
                protocol_v2=SimpleNamespace(enable_v2=False, prefer_v2=False),
                webtorrent=SimpleNamespace(
                    enable_webtorrent=False,
                    webtorrent_host="localhost",
                    webtorrent_port=8080,
                    webtorrent_stun_servers=[]
                )
            ),
            discovery=SimpleNamespace(tracker_auto_scrape=False)
        )
        self.peers: list[Any] = []
        # Use bytes keys like real AsyncSessionManager
        self.torrents: dict[bytes, Any] = {}
        self.dht = SimpleNamespace(
            node_count=0,
            get_stats=lambda: {"routing_table": {"total_nodes": 0}}
        )
        # Add lock for async context manager
        self.lock = asyncio.Lock()
        # Scrape cache attributes (BEP 48)
        self.scrape_cache: dict[bytes, Any] = {}
        self.scrape_cache_lock = asyncio.Lock()
        
    async def add_torrent(self, torrent_data, resume=False):
        """Mock add_torrent that populates torrents dict."""
        from unittest.mock import AsyncMock
        info_hash = torrent_data.get("info_hash", b"\x00" * 20)
        if isinstance(info_hash, str):
            info_hash = bytes.fromhex(info_hash)
        elif len(info_hash) != 20:
            info_hash = info_hash[:20] if len(info_hash) > 20 else info_hash + b"\x00" * (20 - len(info_hash))
        info_hash_hex = info_hash.hex()
        # Create mock torrent session
        mock_session = AsyncMock()
        mock_session.file_selection_manager = None
        self.torrents[info_hash] = mock_session
        return info_hash_hex


def test_status_command_happy_path(monkeypatch):
    runner = CliRunner()

    # Patch ConfigManager to avoid touching real config
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace()))
    # Patch AsyncSessionManager to our fake
    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())

    # Patch asyncio.run to actually run the coroutine we pass (show_status)
    def _run(coro):
        return _run_coro_locally(coro)

    monkeypatch.setattr(cli_main.asyncio, "run", _run)

    result = runner.invoke(cli_main.cli, ["status"]) 
    assert result.exit_code == 0
    # Basic smoke: table title present
    assert "ccBitTorrent Status" in result.output


def test_status_command_error_path(monkeypatch):
    runner = CliRunner()

    # Make ConfigManager raise to exercise error branch
    def _cm_raise(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "ConfigManager", _cm_raise)

    result = runner.invoke(cli_main.cli, ["status"]) 
    assert result.exit_code != 0
    assert "Error: boom" in result.output


def test_debug_command_happy_path(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)
    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())

    # Ensure asyncio.run executes the async debug function
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["debug"]) 
    assert result.exit_code == 0
    assert "Debug mode" in result.output


def test_magnet_invalid_link_error(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace(disk=SimpleNamespace())))

    class _FakeMgr(_FakeSession):
        def parse_magnet_link(self, _link: str):
            # Simulate parse error
            raise ValueError("bad magnet")

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeMgr())

    result = runner.invoke(cli_main.cli, ["magnet", "magnet:?xt=urn:btih:bad"])
    assert result.exit_code != 0
    assert "Invalid magnet link" in result.output or "Error" in result.output


def test_download_checkpoint_noninteractive(monkeypatch):
    runner = CliRunner()

    # Fake config with checkpoint enabled
    disk_cfg = SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp")
    cfg = SimpleNamespace(disk=disk_cfg)
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _FakeMgr(_FakeSession):
        async def start(self):
            pass
            
        async def stop(self):
            pass
            
        def load_torrent(self, _path):
            # Minimal torrent-like dict expected by code
            return {"info_hash": b"\x00" * 20, "name": "t"}

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeMgr())

    # Inject a fake CheckpointManager module with async load_checkpoint
    fake_mod = ModuleType("ccbt.storage.checkpoint")

    class _CP:
        def __init__(self):
            self.torrent_name = "t"
            self.verified_pieces = []
            self.total_pieces = 0

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    # Force non-interactive branch by making stdin not a TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    # Patch asyncio.run to actually consume coroutines created by download flow
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    # Provide an existing file path by pointing to this test file; exists=True check passes
    result = runner.invoke(cli_main.cli, ["download", __file__]) 
    # Should hit non-interactive checkpoint path regardless of later download errors
    assert result.exit_code in (0, 1)
    assert "Non-interactive mode, starting fresh download" in result.output


def test_web_command_does_not_await_when_not_coroutine(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)

    class _FakeMgr(_FakeSession):
        def start_web_interface(self, *_a, **_k):
            # Return a non-coroutine sentinel to ensure asyncio.run is NOT called
            return "started"

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeMgr())

    called = {"run": 0}

    def _fake_run(_coro):
        called["run"] += 1
        return None

    monkeypatch.setattr(cli_main.asyncio, "run", _fake_run)

    result = runner.invoke(cli_main.cli, ["web", "--host", "127.0.0.1", "--port", "9090"]) 
    assert result.exit_code == 0
    # Ensure asyncio.run was not invoked for non-coroutine
    assert called["run"] == 0


def test_interactive_command_runs_cli(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)

    class _FakeMgr(_FakeSession):
        pass

    class _FakeInteractive:
        def __init__(self, *_a, **_k):
            pass

        async def run(self):
            return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeMgr())
    monkeypatch.setattr(cli_main, "InteractiveCLI", _FakeInteractive)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["interactive"]) 
    assert result.exit_code == 0


def test_magnet_happy_path_noninteractive(monkeypatch):
    runner = CliRunner()
    # Provide config with disk
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_FakeSession):
        async def start(self):
            pass
            
        async def stop(self):
            pass
            
        def parse_magnet_link(self, _link: str):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _dummy_download(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["magnet", "magnet:?xt=urn:btih:abc", "--no-checkpoint"]) 
    assert result.exit_code == 0


def test_download_happy_path_noninteractive(monkeypatch):
    runner = CliRunner()
    cfg = SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_FakeSession):
        async def start(self):
            pass
            
        async def stop(self):
            pass
            
        def load_torrent(self, _path):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _dummy_download(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["download", __file__, "--no-checkpoint"]) 
    assert result.exit_code == 0


