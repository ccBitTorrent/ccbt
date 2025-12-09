"""Additional aligned CLI tests to raise ccbt.cli.main coverage."""

from __future__ import annotations

import asyncio
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


def test_config_command_shows_table(monkeypatch):
    runner = CliRunner()
    # Minimal config object with expected attributes
    config = SimpleNamespace(
        network=SimpleNamespace(listen_port=6881, max_global_peers=50),
        disk=SimpleNamespace(download_path="."),
        observability=SimpleNamespace(log_level=SimpleNamespace(value="INFO"), enable_metrics=False),
    )
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=config))
    result = runner.invoke(cli_main.cli, ["config", "--help"]) 
    assert result.exit_code == 0


def test_status_command_happy_and_error(monkeypatch):
    runner = CliRunner()

    # Happy path
    class _Session:
        def __init__(self):
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
            self.peers = []
            # Use bytes keys like real AsyncSessionManager
            self.torrents: dict[bytes, Any] = {}
            self.dht = SimpleNamespace(
                node_count=0,
                get_stats=lambda: {"routing_table": {"total_nodes": 0}}
            )
            # Add lock for async context manager
            import asyncio
            self.lock = asyncio.Lock()
            # Scrape cache attributes (BEP 48)
            self.scrape_cache: dict[bytes, Any] = {}
            self.scrape_cache_lock = asyncio.Lock()

    # Mock ConfigManager to return a valid object
    class _MockConfigManager:
        def __init__(self, *args, **kwargs):
            pass
    monkeypatch.setattr(cli_main, "ConfigManager", _MockConfigManager)
    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Session())
    monkeypatch.setattr(cli_main.asyncio, "run", lambda c: _run_coro_locally(c))
    ok = runner.invoke(cli_main.cli, ["status"])
    if ok.exit_code != 0:
        print(f"Command output: {ok.output}")
        print(f"Command exception: {ok.exception}")
    assert ok.exit_code == 0
    assert "ccBitTorrent Status" in ok.output

    # Error path
    def _cm_raise(*_a, **_k):
        raise RuntimeError("stat-err")

    monkeypatch.setattr(cli_main, "ConfigManager", _cm_raise)
    err = runner.invoke(cli_main.cli, ["status"]) 
    assert err.exit_code != 0
    assert "Error: stat-err" in err.output


