"""Read-only daemon diagnostics collection.

Single source of truth for peer/speed diagnosis: the ``btbt diagnose``
CLI and the TUI Peer Diagnostics view both render the dict produced
here, so they can never disagree. No engine state is mutated.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any, Optional


def _to_plain(value: Any) -> Any:
    """Convert pydantic models / nested structures to plain data."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {
            k: _to_plain(v) for k, v in vars(value).items() if not k.startswith("_")
        }
    return str(value)


async def _safe(coro_factory: Any) -> Any:
    """Run an IPC call, capturing failures as {"error": ...} sections."""
    try:
        return _to_plain(await coro_factory())
    except Exception as exc:  # diagnostics must never crash on one section
        return {"error": f"{type(exc).__name__}: {exc}"}


def daemon_log_tail(lines: int = 20) -> list[str]:
    """Return the last lines of the daemon startup log (if present)."""
    candidates = [
        Path.home() / ".ccbt" / "daemon" / "daemon_startup.log",
        Path.home() / ".ccbt" / "daemon" / "debug.log",
    ]
    for path in candidates:
        with contextlib.suppress(OSError):
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="ignore")
                return text.splitlines()[-lines:]
    return []


def daemon_heartbeat() -> dict[str, Any]:
    """Read the daemon heartbeat file (pid + last-write epoch).

    Lets diagnose distinguish "daemon died at T" (heartbeat file stale,
    IPC unreachable) from a live-but-slow daemon.
    """
    path = Path.home() / ".ccbt" / "daemon" / "daemon.heartbeat"
    try:
        text = path.read_text(encoding="utf-8").strip()
        pid_s, ts_s = text.split()
        age = max(0.0, time.time() - float(ts_s))
        return {
            "pid": int(pid_s),
            "last_beat_epoch": float(ts_s),
            "age_seconds": round(age, 1),
            "alive_recently": age < 45.0,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


async def collect_diagnostics(
    client: Any,
    info_hash: Optional[str] = None,
    *,
    log_lines: int = 20,
) -> dict[str, Any]:
    """Collect daemon-true diagnostics via an IPCClient-like object.

    Args:
        client: Object with IPCClient's read methods (get_status,
            list_torrents, get_torrent_status, get_peers_for_torrent /
            get_torrent_peers, get_torrent_trackers,
            get_torrent_dht_metrics, get_torrent_peer_quality,
            get_aggressive_discovery_status, get_nat_status,
            get_rate_samples).
        info_hash: Restrict per-torrent detail to this torrent; when
            None, every torrent is diagnosed.
        log_lines: Number of daemon log lines to include.

    Returns:
        Plain-data dict with daemon/nat/rates/log sections and one
        entry per torrent.
    """
    report: dict[str, Any] = {
        "daemon_heartbeat": daemon_heartbeat(),
        "daemon": await _safe(client.get_status),
        "nat": await _safe(client.get_nat_status),
        "rates": await _safe(lambda: client.get_rate_samples(seconds=120)),
        "daemon_log_tail": daemon_log_tail(log_lines),
        "torrents": [],
    }

    if info_hash:
        torrents = [await _safe(lambda: client.get_torrent_status(info_hash))]
        torrents = [t for t in torrents if t and "error" not in t]
        hashes = [info_hash]
    else:
        listed = await _safe(client.list_torrents)
        torrents = listed if isinstance(listed, list) else []
        hashes = [
            str(t.get("info_hash") or t.get("info_hash_hex") or "")
            for t in torrents
            if isinstance(t, dict)
        ]

    peers_getter = getattr(client, "get_peers_for_torrent", None) or getattr(
        client, "get_torrent_peers", None
    )

    for torrent, ih in zip(torrents, hashes):
        entry: dict[str, Any] = {"torrent": torrent}
        if ih:
            if peers_getter is not None:
                entry["peers"] = await _safe(lambda ih=ih: peers_getter(ih))
            if hasattr(client, "get_torrent_trackers"):
                entry["trackers"] = await _safe(
                    lambda ih=ih: client.get_torrent_trackers(ih)
                )
            if hasattr(client, "get_torrent_dht_metrics"):
                entry["dht"] = await _safe(
                    lambda ih=ih: client.get_torrent_dht_metrics(ih)
                )
            if hasattr(client, "get_torrent_peer_quality"):
                entry["peer_quality"] = await _safe(
                    lambda ih=ih: client.get_torrent_peer_quality(ih)
                )
            if hasattr(client, "get_aggressive_discovery_status"):
                entry["aggressive_discovery"] = await _safe(
                    lambda ih=ih: client.get_aggressive_discovery_status(ih)
                )
        report["torrents"].append(entry)
    return report


def _peer_key(p: dict[str, Any]) -> str:
    return str(
        p.get("peer_key")
        or p.get("peer_id")
        or f"{p.get('ip', '?')}:{p.get('port', '?')}"
    )


def _is_choked(p: dict[str, Any]) -> bool:
    return bool(
        p.get("is_choked")
        or p.get("remote_choked")
        or p.get("choked")
        or p.get("peer_choking")
    )


def summarize_torrent(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract the headline peer counts from one diagnostics torrent entry.

    When the daemon's aggregate productive/requestable counters read 0
    but peer rows show byte flow, computed-from-rows values are exposed
    alongside (suffixed ``_from_rows``) so the lie is visible rather
    than silently believed.
    """
    torrent = entry.get("torrent") or {}
    peers = entry.get("peers") or {}
    peer_rows = peers.get("peers", peers) if isinstance(peers, dict) else peers
    if not isinstance(peer_rows, list):
        peer_rows = []
    peer_rows = [p for p in peer_rows if isinstance(p, dict)]
    choked = sum(1 for p in peer_rows if _is_choked(p))
    productive_from_rows = sum(
        1 for p in peer_rows if float(p.get("download_rate", 0) or 0) > 0
    )
    requestable_from_rows = sum(1 for p in peer_rows if not _is_choked(p))
    dht = entry.get("dht") or {}
    return {
        "name": torrent.get("name", "?"),
        "info_hash": torrent.get("info_hash", ""),
        "status": torrent.get("status", "?"),
        "connected_peers": torrent.get(
            "connected_peers", torrent.get("num_peers", len(peer_rows))
        ),
        "active_peers": torrent.get("active_peers"),
        "productive_peers": torrent.get("productive_peers"),
        "requestable_peers": torrent.get("requestable_peers"),
        "productive_peers_from_rows": productive_from_rows,
        "requestable_peers_from_rows": requestable_from_rows,
        "seeds_connected": torrent.get("seeds_connected", torrent.get("num_seeds")),
        "peer_rows": len(peer_rows),
        "choked_peers": choked,
        "download_rate": torrent.get("download_rate"),
        "upload_rate": torrent.get("upload_rate"),
        "peers_detail": [
            {
                "peer_key": _peer_key(p),
                "choked": _is_choked(p),
                "download_rate": p.get("download_rate"),
                "upload_rate": p.get("upload_rate"),
                "client": p.get("client"),
            }
            for p in peer_rows[:50]
        ],
        "dht_last_bootstrap_failure_reason": dht.get(
            "last_bootstrap_failure_reason", ""
        ),
        "dht_bootstrap_zero_nodes_last_reason": dht.get(
            "bootstrap_zero_nodes_last_reason", ""
        ),
        "dht_routing_table_size": dht.get("routing_table_size"),
        "dht_bound_port": dht.get("bound_port", dht.get("listen_port")),
    }
