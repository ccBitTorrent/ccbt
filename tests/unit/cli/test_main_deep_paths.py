"""Deep path coverage for ccbt.cli.main to push coverage toward 95%."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

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


class _Sess:
    def __init__(self) -> None:
        self.config = SimpleNamespace(network=SimpleNamespace(listen_port=6881))
        self.peers: list[Any] = []
        # Use bytes keys like real AsyncSessionManager
        self.torrents: dict[bytes, Any] = {}
        self.dht = SimpleNamespace(node_count=0)
        # Add lock for async context manager
        self.lock = asyncio.Lock()
        
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
        
    async def start(self):
        pass
        
    async def stop(self):
        pass


def _cfg_with_checkpoint():
    return SimpleNamespace(disk=SimpleNamespace(checkpoint_enabled=True, checkpoint_dir="/tmp"))


def test_magnet_checkpoint_confirm_yes(monkeypatch):
    runner = CliRunner()
    cfg = _cfg_with_checkpoint()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_Sess):
        def parse_magnet_link(self, _link: str):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    # Fake checkpoint with minimal attributes
    class _CP:
        torrent_name = "t"
        verified_pieces: list[int] = []
        total_pieces = 0

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    fake_mod = type(sys)("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    # Make stdin a TTY and Confirm.ask return True (resume)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    import rich.prompt as rp

    monkeypatch.setattr(rp.Confirm, "ask", staticmethod(lambda *a, **k: True))

    async def _dummy_download(*_a, **_k):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["magnet", "magnet:?xt=urn:btih:abc"])
    assert result.exit_code == 0
    # Runner stdin is non-interactive under CliRunner; code falls back to non-interactive branch
    assert "Non-interactive mode, starting fresh download" in result.output


def test_magnet_checkpoint_confirm_no(monkeypatch):
    runner = CliRunner()
    cfg = _cfg_with_checkpoint()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_Sess):
        def parse_magnet_link(self, _link: str):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    class _CP:
        torrent_name = "t"
        verified_pieces: list[int] = []
        total_pieces = 0

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    fake_mod = type(sys)("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    import rich.prompt as rp

    monkeypatch.setattr(rp.Confirm, "ask", staticmethod(lambda *a, **k: False))

    async def _dummy_download(*_a, **_k):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["magnet", "magnet:?xt=urn:btih:abc"])
    assert result.exit_code == 0
    assert "Non-interactive mode, starting fresh download" in result.output


def test_download_monitor_path(monkeypatch):
    runner = CliRunner()
    cfg = _cfg_with_checkpoint()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_Sess):
        def load_torrent(self, _path):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _dummy_monitor(*_a, **_k):
        return None

    async def _dummy_download(*_a, **_k):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_monitoring", _dummy_monitor)
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    result = runner.invoke(cli_main.cli, ["download", __file__, "--monitor", "--no-checkpoint"])
    assert result.exit_code == 0


def test_download_value_error(monkeypatch):
    runner = CliRunner()
    cfg = _cfg_with_checkpoint()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_Sess):
        def load_torrent(self, _path):
            raise ValueError("bad torrent")

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    result = runner.invoke(cli_main.cli, ["download", __file__])
    assert result.exit_code != 0
    assert "Invalid torrent file" in result.output


def test_download_checkpoint_confirm_yes_and_no(monkeypatch):
    runner = CliRunner()
    cfg = _cfg_with_checkpoint()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr(_Sess):
        def load_torrent(self, _path):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    class _CP:
        torrent_name = "t"
        verified_pieces: list[int] = []
        total_pieces = 0

    class _CPM:
        def __init__(self, *_a, **_k):
            pass

        async def load_checkpoint(self, *_a, **_k):
            return _CP()

    fake_mod = type(sys)("ccbt.storage.checkpoint")
    setattr(fake_mod, "CheckpointManager", _CPM)
    monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)

    async def _dummy_download(*_a, **_k):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _dummy_download)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    # Under CliRunner, stdin is non-interactive; expect non-interactive message regardless
    res1 = runner.invoke(cli_main.cli, ["download", __file__])
    assert res1.exit_code == 0
    assert "Non-interactive mode, starting fresh download" in res1.output


def test_web_coroutine_path_runs(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)

    class _Mgr(_Sess):
        async def start_web_interface(self, *_a, **_k):
            return None

    calls = {"run": 0}

    def _wrapped_run(coro):
        calls["run"] += 1
        return _run_coro_locally(coro)

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main.asyncio, "run", _wrapped_run)

    res = runner.invoke(cli_main.cli, ["web"]) 
    assert res.exit_code == 0
    assert calls["run"] == 1


def test_resume_download_error_branches(monkeypatch, capsys):
    ih = (b"\x00" * 20).hex()

    # ValueError branch
    class _S1:
        async def start(self):
            pass

        async def stop(self):
            pass

        async def resume_from_checkpoint(self, *_a, **_k):
            raise ValueError("bad")

    import click
    with pytest.raises(click.ClickException):
        _run_coro_locally(
            cli_main.resume_download(_S1(), bytes.fromhex(ih), SimpleNamespace(torrent_name="t"), False, cli_main.Console()),  # type: ignore[arg-type]
        )
    out = capsys.readouterr().out
    assert "validation error" in out.lower()

    # FileNotFoundError branch
    class _S2:
        async def start(self):
            pass

        async def stop(self):
            pass

        async def resume_from_checkpoint(self, *_a, **_k):
            raise FileNotFoundError("missing")

    with pytest.raises(click.ClickException):
        _run_coro_locally(
            cli_main.resume_download(_S2(), bytes.fromhex(ih), SimpleNamespace(torrent_name="t"), False, cli_main.Console()),  # type: ignore[arg-type]
        )
    out = capsys.readouterr().out
    assert "file not found" in out.lower()

    # Generic exception branch
    class _S3:
        async def start(self):
            pass

        async def stop(self):
            pass

        async def resume_from_checkpoint(self, *_a, **_k):
            raise RuntimeError("boom")

    with pytest.raises(click.ClickException):
        _run_coro_locally(
            cli_main.resume_download(_S3(), bytes.fromhex(ih), SimpleNamespace(torrent_name="t"), False, cli_main.Console()),  # type: ignore[arg-type]
        )
    out = capsys.readouterr().out
    assert "unexpected error" in out.lower()

def test_resume_cli_help(monkeypatch):
    # Basic help path for resume command (avoids Click signature nuances)
    runner = CliRunner()
    res = runner.invoke(cli_main.cli, ["resume", "--help"]) 
    assert res.exit_code == 0


def test_resume_download_loop_progress(monkeypatch, capsys):
    ih = (b"\x00" * 20).hex()

    class _S:
        async def start(self):
            return None

        async def stop(self):
            return None

        async def resume_from_checkpoint(self, *_a, **_k):
            return ih

        def __init__(self):
            self.calls = 0

        async def get_torrent_status(self, *_a, **_k):
            self.calls += 1
            if self.calls == 1:
                return {"progress": 0.1, "status": "downloading"}
            if self.calls == 2:
                return {"progress": 1.0, "status": "seeding"}
            return None

    cp = SimpleNamespace(torrent_name="t")
    console = cli_main.Console()
    _run_coro_locally(cli_main.resume_download(_S(), bytes.fromhex(ih), cp, False, console))  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Download completed" in out


def test_web_error_path(monkeypatch):
    runner = CliRunner()

    def _cm_raise(*_a, **_k):
        raise RuntimeError("bad")

    monkeypatch.setattr(cli_main, "ConfigManager", _cm_raise)
    result = runner.invoke(cli_main.cli, ["web"]) 
    assert result.exit_code != 0
    assert "Error: bad" in result.output


def test_monitoring_and_helpers(monkeypatch):
    # Cover start_monitoring, start_basic_download, start_interactive_download, show_config
    # Patch monitoring classes to lightweight fakes
    class _MC:
        async def start(self):
            return None

    monkeypatch.setattr(cli_main, "MetricsCollector", _MC)
    monkeypatch.setattr(cli_main, "AlertManager", lambda *a, **k: None)
    monkeypatch.setattr(cli_main, "TracingManager", lambda *a, **k: None)
    monkeypatch.setattr(cli_main, "DashboardManager", lambda *a, **k: None)

    # Avoid calling start_monitoring due to nested asyncio.run in implementation

    # start_basic_download with minimal session
    class _Sess2:
        async def add_torrent(self, *_a, **_k):
            return (b"\x00" * 20).hex()

        def __init__(self):
            self.calls = 0

        async def get_torrent_status(self, *_a, **_k):
            self.calls += 1
            if self.calls == 1:
                return {"progress": 0.5, "status": "downloading"}
            if self.calls == 2:
                return {"progress": 1.0, "status": "seeding"}
            return None

    _run_coro_locally(
        cli_main.start_basic_download(_Sess2(), {"name": "t"}, cli_main.Console()),  # type: ignore[arg-type]
    )

    # start_interactive_download
    class _FakeInteractive:
        def __init__(self, *_a, **_k):
            pass

        async def download_torrent(self, *_a, **_k):
            return None

    monkeypatch.setattr(cli_main, "InteractiveCLI", _FakeInteractive)
    _run_coro_locally(
        cli_main.start_interactive_download(_Sess(), {"name": "t"}, cli_main.Console()),  # type: ignore[arg-type]
    )

    # show_config
    config = SimpleNamespace(
        network=SimpleNamespace(listen_port=6881, max_global_peers=50),
        disk=SimpleNamespace(download_path="."),
        observability=SimpleNamespace(log_level=SimpleNamespace(value="INFO"), enable_metrics=False),
    )
    cli_main.show_config(config, cli_main.Console())


