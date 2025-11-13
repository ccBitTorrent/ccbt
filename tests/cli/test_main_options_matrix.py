"""Option-matrix tests for ccbt.cli.main to cover override branches."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

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


def _cfg():
    return SimpleNamespace(
        network=SimpleNamespace(
            listen_port=6881,
            max_global_peers=50,
            max_peers_per_torrent=20,
            pipeline_depth=4,
            block_size_kib=16,
            connection_timeout=10.0,
            global_down_kib=0,
            global_up_kib=0,
            enable_ipv6=True,
            enable_tcp=True,
            enable_utp=True,
            enable_encryption=False,
            tcp_nodelay=False,
            socket_rcvbuf_kib=64,
            socket_sndbuf_kib=64,
        ),
        discovery=SimpleNamespace(
            enable_dht=True,
            dht_port=6881,
            enable_http_trackers=True,
            enable_udp_trackers=True,
            tracker_announce_interval=120.0,
            tracker_scrape_interval=300.0,
            pex_interval=120.0,
        ),
        strategy=SimpleNamespace(
            piece_selection="rarest_first",
            endgame_threshold=0.95,
            endgame_duplicates=2,
            streaming_mode=False,
        ),
        disk=SimpleNamespace(
            hash_workers=1,
            disk_workers=1,
            use_mmap=False,
            mmap_cache_mb=0,
            write_batch_kib=64,
            write_buffer_kib=128,
            preallocate="none",
            sparse_files=False,
            enable_io_uring=False,
            direct_io=False,
            sync_writes=False,
            checkpoint_enabled=False,
            checkpoint_dir="/tmp",
            download_path=".",
        ),
        observability=SimpleNamespace(
            log_level=SimpleNamespace(value="INFO"),
            enable_metrics=False,
        ),
    )


def test_download_with_override_flags_matrix(monkeypatch):
    runner = CliRunner()
    cfg = _cfg()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr:
        def load_torrent(self, _path):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _basic(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _basic)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    args = [
        "download",
        __file__,
        "--listen-port","9999",
        "--max-peers","10",
        "--max-peers-per-torrent","5",
        "--pipeline-depth","2",
        "--block-size-kib","32",
        "--connection-timeout","1.2",
        "--download-limit","100",
        "--upload-limit","50",
        "--listen-interface","lo",
        "--peer-timeout","3.5",
        "--dht-timeout","4.5",
        "--enable-tcp",
        "--disable-utp",
        "--enable-encryption",
        "--tcp-nodelay",
        "--socket-rcvbuf-kib",
        "128",
        "--socket-sndbuf-kib",
        "256",
        "--min-block-size-kib",
        "4",
        "--max-block-size-kib",
        "64",
        "--disable-http-trackers",
        "--disable-udp-trackers",
        "--enable-dht",
        "--dht-port",
        "8999",
        "--piece-selection",
        "rarest_first",
        "--endgame-threshold",
        "0.9",
        "--endgame-duplicates",
        "3",
        "--streaming-mode",
    ]

    result = runner.invoke(cli_main.cli, args)
    assert result.exit_code == 0


def test_magnet_with_override_flags_matrix(monkeypatch):
    runner = CliRunner()
    cfg = _cfg()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=cfg))

    class _Mgr:
        def parse_magnet_link(self, _link: str):
            return {"info_hash": b"\x00" * 20, "name": "t"}

    async def _basic(session, torrent_data, console, resume=False):
        return None

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _Mgr())
    monkeypatch.setattr(cli_main, "start_basic_download", _basic)
    monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

    args = [
        "magnet",
        "magnet:?xt=urn:btih:abc",
        "--disable-tcp",
        "--enable-utp",
        "--disable-encryption",
        "--no-tcp-nodelay",
        "--socket-rcvbuf-kib",
        "256",
        "--socket-sndbuf-kib",
        "128",
        "--disable-http-trackers",
        "--enable-udp-trackers",
        "--disable-dht",
        "--piece-selection","sequential",
        "--optimistic-unchoke-interval",
        "5",
        "--unchoke-interval",
        "10",
        "--metrics-interval",
        "30",
    ]

    result = runner.invoke(cli_main.cli, args)
    assert result.exit_code == 0


def test_status_error_branch(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli_main, "ConfigManager", lambda *_a, **_k: None)

    class _BadSession:
        # Missing expected attributes used by show_status, will cause AttributeError
        pass

    monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _BadSession())
    result = runner.invoke(cli_main.cli, ["status"]) 
    assert result.exit_code != 0
    assert "Error:" in result.output


