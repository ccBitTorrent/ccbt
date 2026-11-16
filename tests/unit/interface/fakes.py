"""Fake DataProvider / CommandExecutor fixtures for headless TUI tests."""
from __future__ import annotations
from typing import Any

HASH_A = "a" * 40
HASH_B = "b" * 40

def torrent_payload(info_hash=HASH_A, name="ubuntu.iso", **over):
    base = {"info_hash": info_hash, "name": name, "status": "downloading", "progress": 0.42,
        "download_rate": 2048.0, "upload_rate": 512.0, "num_peers": 12, "num_seeds": 3,
        "downloaded": 420_000_000, "uploaded": 84_000_000, "left": 580_000_000,
        "total_size": 1_000_000_000, "pieces_completed": 42, "pieces_total": 100,
        "output_dir": "/downloads", "is_private": False}
    base.update(over); return base

def make_torrents(n=1):
    if n == 0: return []
    if n == 1: return [torrent_payload()]
    return [torrent_payload(f"{i:040x}", f"torrent-{i}.iso", progress=(i % 100)/100) for i in range(n)]

class FakeExecutor:
    """Records executor commands; returns success CommandResult-like objects."""
    def __init__(self): self.calls: list[tuple[str, dict]] = []
    async def execute_command(self, command, *args, **kwargs):
        self.calls.append((command, kwargs))
        from types import SimpleNamespace
        data = {"info_hash": HASH_A, "folders": [], "stats": {"total_chunks": 10, "unique_chunks": 8, "dedup_ratio": 1.25}}
        return SimpleNamespace(success=True, error=None, data=data)
    # alias used by screens calling .execute
    async def execute(self, command, *args, **kwargs): return await self.execute_command(command, *args, **kwargs)

class FakeDataProvider:
    def __init__(self, torrents=None, error=False):
        self._torrents = torrents if torrents is not None else make_torrents(1)
        self._error = error
    def _check(self):
        if self._error: raise RuntimeError("daemon unreachable")
    async def list_torrents(self): self._check(); return list(self._torrents)
    async def get_global_stats(self):
        self._check(); return {"num_torrents": len(self._torrents), "num_active": len(self._torrents),
            "num_paused": 0, "num_seeding": 0, "download_rate": 2048.0, "upload_rate": 512.0,
            "total_downloaded": 420_000_000, "total_uploaded": 84_000_000, "connected_peers": 12}
    async def get_ui_snapshot(self): return {"global_stats": await self.get_global_stats(), "torrents": await self.list_torrents(), "rate_samples": []}
    async def get_torrent_status(self, h): return next((t for t in self._torrents if t["info_hash"] == h), None)
    async def get_torrent_peers(self, h): return [{"peer_key": f"1.2.3.4:6881", "ip": "1.2.3.4", "port": 6881, "client": "qBittorrent", "download_rate": 1024.0, "upload_rate": 256.0}] if h == HASH_A else [{"peer_key": "5.6.7.8:6881", "ip": "5.6.7.8", "port": 6881, "client": "Transmission", "download_rate": 0.0, "upload_rate": 0.0}]
    async def get_torrent_files(self, h): return [{"index": 0, "path": "file-a.mkv" if h == HASH_A else "file-b.mkv", "size": 1000, "downloaded": 500, "priority": 1, "selected": True}]
    async def get_torrent_trackers(self, h): return [{"url": "udp://tracker.example:80", "status": "ok", "seeders": 3, "leechers": 12}]
    async def get_piece_health(self, h): return {"availability": 0.9, "pieces_completed": 42, "pieces_total": 100}
    async def get_aggressive_discovery_status(self, h): return {"enabled": False, "reason": "normal"}
    async def get_media_candidates(self, h): return []
    async def get_media_stream_status(self, h): return None
    async def get_global_kpis(self): return await self.get_global_stats()
    async def get_dht_health_summary(self, limit=8): return {"nodes": 120, "health": "good"}
    async def get_peer_quality_distribution(self): return {}
    async def get_disk_io_metrics(self): return {}
    async def get_system_metrics(self): return {"cpu_usage": 10.0}
    async def get_rate_samples(self, seconds=120): return []
    async def get_network_timing_metrics(self): return {}
    async def get_swarm_health_samples(self, limit=10): return []
    async def get_peer_metrics(self): return {"total_peers": 1, "active_peers": 1, "peers": await self.get_torrent_peers(HASH_A)}
    async def list_xet_folders(self): return [{"folder_key": "ws1", "folder_path": "/data/shared", "sync_mode": "best_effort", "status": {"status": "syncing", "connected_peers": 2, "sync_progress": 0.5}}]
    async def get_xet_folder_status(self, k): return (await self.list_xet_folders())[0]
    async def get_xet_discovery_status(self): return {"mechanisms": {"dht": "enabled"}}
    async def get_per_torrent_performance(self, h): return {}
    async def get_torrent_piece_availability(self, h): return [1, 2, 3]

# Scenario factories
def empty_provider(): return FakeDataProvider([])
def one_torrent_provider(): return FakeDataProvider(make_torrents(1))
def many_torrents_provider(): return FakeDataProvider(make_torrents(100))
def error_provider(): return FakeDataProvider(error=True)
def two_torrent_provider(): return FakeDataProvider([torrent_payload(HASH_A, "a.iso"), torrent_payload(HASH_B, "b.iso")])
