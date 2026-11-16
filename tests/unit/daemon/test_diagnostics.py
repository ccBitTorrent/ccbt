"""Daemon-true diagnostics collector + detection fallback tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ccbt.daemon.diagnostics import collect_diagnostics, summarize_torrent

pytestmark = [pytest.mark.unit]


class _FakeClient:
    async def get_status(self):
        return SimpleNamespace(status="running", pid=42, uptime=10.0, num_torrents=1)

    async def get_nat_status(self):
        return {"enabled": False, "method": None, "mappings": []}

    async def get_rate_samples(self, seconds=120):
        return {"samples": []}

    async def list_torrents(self):
        return [
            {
                "info_hash": "a" * 40,
                "name": "t.iso",
                "status": "downloading",
                "connected_peers": 2,
                "active_peers": 1,
                "seeds_connected": 0,
                "num_peers": 2,
                "num_seeds": 0,
            }
        ]

    async def get_peers_for_torrent(self, ih):
        return {"peers": [{"peer_key": "1.2.3.4:6881", "is_choked": True}]}

    async def get_torrent_trackers(self, ih):
        return {"trackers": [{"url": "udp://t:80", "status": "ok"}]}

    async def get_torrent_dht_metrics(self, ih):
        return {"routing_table_size": 0}

    async def get_torrent_peer_quality(self, ih):
        return {"total_peers_ranked": 1}

    async def get_aggressive_discovery_status(self, ih):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_collect_diagnostics_tolerates_section_failure():
    report = await collect_diagnostics(_FakeClient(), log_lines=0)
    assert report["daemon"]["pid"] == 42
    (entry,) = report["torrents"]
    assert entry["aggressive_discovery"]["error"].startswith("RuntimeError")
    summary = summarize_torrent(entry)
    assert summary["connected_peers"] == 2
    assert summary["peer_rows"] == 1
    assert summary["choked_peers"] == 1


@pytest.mark.asyncio
async def test_collect_diagnostics_single_torrent():
    client = _FakeClient()

    async def _status(ih):
        return {"info_hash": ih, "name": "one", "status": "seeding"}

    client.get_torrent_status = _status  # type: ignore[attr-defined]
    report = await collect_diagnostics(client, "b" * 40, log_lines=0)
    assert [t["torrent"]["name"] for t in report["torrents"]] == ["one"]


def test_is_running_falls_back_to_ipc_listening(monkeypatch, tmp_path):
    """PID file gone but IPC port listening => daemon counts as running."""
    import ccbt.daemon.daemon_manager as dm

    manager = dm.DaemonManager(state_dir=tmp_path)
    monkeypatch.setattr(manager, "get_pid", lambda: None)
    monkeypatch.setattr(
        dm, "resolve_daemon_connection_params", lambda cfg=None: (64124, None, tmp_path)
    )
    monkeypatch.setattr(dm, "is_daemon_ipc_listening", lambda port, **kw: True)
    assert manager.is_running() is True
    monkeypatch.setattr(dm, "is_daemon_ipc_listening", lambda port, **kw: False)
    assert manager.is_running() is False
