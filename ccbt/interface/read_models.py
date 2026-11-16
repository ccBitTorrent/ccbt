"""Typed read models for the TUI. Only constructors are the normalisers in data_provider."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass(frozen=True)
class TorrentRow:
    info_hash: str = ""
    name: str = "Unknown"
    status: str = "unknown"
    progress: float = 0.0
    download_rate: float = 0.0
    upload_rate: float = 0.0
    peers_connected: int = 0
    seeds_connected: int = 0
    peers_swarm: int = 0
    seeds_swarm: int = 0
    downloaded: int = 0
    uploaded: int = 0
    left: int = 0
    total_size: int = 0
    pieces_completed: int = 0
    pieces_total: int = 0
    eta_seconds: float = 0.0
    ratio: float = 0.0
    availability: float = 0.0
    queue_position: int = -1
    is_private: bool = False
    output_dir: Optional[str] = None
    magnet_uri: Optional[str] = None
    comment: Optional[str] = None
    error: Optional[str] = None
    added_time: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TorrentRow:
        peers = int(d.get("peers_connected", d.get("connected_peers", d.get("num_peers", 0))) or 0)
        # Seeds must come from a real seed field — never from active_peers.
        seeds = int(d.get("seeds_connected", d.get("num_seeds", d.get("seeds", 0))) or 0)
        downloaded = int(d.get("downloaded", 0) or 0); uploaded = int(d.get("uploaded", 0) or 0)
        left = int(d.get("left", 0) or 0); rate = float(d.get("download_rate", 0) or 0)
        eta = float(d.get("eta_seconds", d.get("eta", 0)) or 0)
        if not eta and left > 0 and rate > 0: eta = left / rate
        ratio = float(d.get("ratio", 0) or 0)
        if not ratio and downloaded > 0: ratio = uploaded / downloaded
        return cls(
            info_hash=str(d.get("info_hash") or d.get("info_hash_hex") or ""),
            name=str(d.get("name", "Unknown")), status=str(d.get("status", "unknown")),
            progress=float(d.get("progress", 0) or 0), download_rate=rate,
            upload_rate=float(d.get("upload_rate", 0) or 0),
            peers_connected=peers, seeds_connected=seeds,
            peers_swarm=int(d.get("peers_swarm", d.get("leechers", peers)) or 0),
            seeds_swarm=int(d.get("seeds_swarm", d.get("seeders", seeds)) or 0),
            downloaded=downloaded, uploaded=uploaded, left=left,
            total_size=int(d.get("total_size", 0) or 0),
            pieces_completed=int(d.get("pieces_completed", 0) or 0),
            pieces_total=int(d.get("pieces_total", 0) or 0),
            eta_seconds=eta, ratio=ratio,
            availability=float(d.get("availability", d.get("swarm_availability", 0)) or 0),
            queue_position=int(d.get("queue_position", -1) if d.get("queue_position") is not None else -1),
            is_private=bool(d.get("is_private", False)), output_dir=d.get("output_dir") or d.get("save_path"),
            magnet_uri=d.get("magnet_uri"), comment=d.get("comment"),
            error=d.get("last_error") or d.get("error"), added_time=float(d.get("added_time", 0) or 0),
        )
    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        # Back-compat aliases for legacy widgets
        d["connected_peers"] = self.peers_connected; d["seeds_connected"] = self.seeds_connected
        d["info_hash_hex"] = self.info_hash; d["eta_seconds"] = self.eta_seconds
        return d

@dataclass(frozen=True)
class PeerRow:
    peer_key: str = ""; ip: str = ""; port: int = 0; client: str = "?"
    download_rate: float = 0.0; upload_rate: float = 0.0
    choked: bool = False; interested: bool = False
    total_downloaded: int = 0; total_uploaded: int = 0
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PeerRow:
        return cls(peer_key=str(d.get("peer_key") or f"{d.get('ip','')}:{d.get('port','')}"),
            ip=str(d.get("ip","")), port=int(d.get("port",0) or 0), client=str(d.get("client") or "?"),
            download_rate=float(d.get("download_rate",0) or 0), upload_rate=float(d.get("upload_rate",0) or 0),
            choked=bool(d.get("choked",False)), interested=bool(d.get("interested",False)),
            total_downloaded=int(d.get("total_bytes_downloaded", d.get("downloaded",0)) or 0),
            total_uploaded=int(d.get("total_bytes_uploaded", d.get("uploaded",0)) or 0))

@dataclass(frozen=True)
class FileRow:
    index: int = 0; path: str = ""; size: int = 0; downloaded: int = 0; priority: int = 1; selected: bool = True
    @property
    def progress(self) -> float: return (self.downloaded / self.size) if self.size else 0.0
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileRow:
        return cls(index=int(d.get("index",0) or 0), path=str(d.get("path") or d.get("name","")),
            size=int(d.get("size",0) or 0), downloaded=int(d.get("downloaded",0) or 0),
            priority=int(d.get("priority",1) or 0), selected=bool(d.get("selected", True)))

@dataclass(frozen=True)
class TrackerRow:
    url: str = ""; status: str = "unknown"; seeders: int = 0; leechers: int = 0; error: Optional[str] = None
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrackerRow:
        return cls(url=str(d.get("url","")), status=str(d.get("status","unknown")),
            seeders=int(d.get("seeders", d.get("seeds",0)) or 0), leechers=int(d.get("leechers", d.get("peers",0)) or 0),
            error=d.get("error") or d.get("last_error"))

@dataclass(frozen=True)
class GlobalKpis:
    num_torrents: int = 0; num_active: int = 0; num_paused: int = 0; num_seeding: int = 0
    download_rate: float = 0.0; upload_rate: float = 0.0; total_downloaded: int = 0; total_uploaded: int = 0
    connected_peers: int = 0
    @property
    def ratio(self) -> float: return (self.total_uploaded / self.total_downloaded) if self.total_downloaded else 0.0
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GlobalKpis:
        return cls(num_torrents=int(d.get("num_torrents",0) or 0), num_active=int(d.get("num_active",0) or 0),
            num_paused=int(d.get("num_paused",0) or 0), num_seeding=int(d.get("num_seeding",0) or 0),
            download_rate=float(d.get("download_rate",0) or 0), upload_rate=float(d.get("upload_rate",0) or 0),
            total_downloaded=int(d.get("total_downloaded",0) or 0), total_uploaded=int(d.get("total_uploaded",0) or 0),
            connected_peers=int(d.get("connected_peers",0) or 0))

@dataclass(frozen=True)
class XetFolderRow:
    folder_key: str = ""; folder_path: str = ""; sync_mode: str = "best_effort"; status: str = "unknown"
    connected_peers: int = 0; sync_progress: float = 0.0; pending_changes: int = 0; error: Optional[str] = None
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> XetFolderRow:
        s = d.get("status") if isinstance(d.get("status"), dict) else d
        return cls(folder_key=str(d.get("folder_key") or s.get("folder_key","")), folder_path=str(d.get("folder_path") or s.get("folder_path","")),
            sync_mode=str(d.get("sync_mode") or s.get("sync_mode","best_effort")), status=str(s.get("status","unknown") if isinstance(s,dict) else "unknown"),
            connected_peers=int(s.get("connected_peers",0) or 0), sync_progress=float(s.get("sync_progress",0) or 0),
            pending_changes=int(s.get("pending_changes",0) or 0), error=s.get("error"))

@dataclass(frozen=True)
class QueueRow:
    position: int = 0; info_hash: str = ""; name: str = ""; status: str = "queued"; priority: int = 0
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QueueRow:
        return cls(position=int(d.get("position", d.get("queue_position",0)) or 0), info_hash=str(d.get("info_hash","")),
            name=str(d.get("name","")), status=str(d.get("status","queued")), priority=int(d.get("priority",0) or 0))

# Aliases used in plan text
TorrentDetail = TorrentRow
XetStatus = XetFolderRow
