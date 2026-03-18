"""Discover peers for XET workspace (cold tonic link).

Used when resolving a tonic?: link and the session has no cached metadata:
discover peers via source_peers (from link), DHT, and optionally trackers.

Tracker behaviour: BEP 15 (UDP Tracker Protocol) and BEP 41 (UDP Tracker Protocol
Extensions) are implemented in the UDP tracker client; the fixed BEP 15 announce
format uses 20-byte info_hash only, and BEP 41 adds URLData (path/query), not
32-byte hash. For 32-byte workspace_id we therefore use HTTP/HTTPS trackers only.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_PEERS = 50
_DEFAULT_TIMEOUT = 15.0
_DEFAULT_PORT = 6881

# 20-byte peer_id for cold-link tracker announces (same family as xet_cold_link_fetch)
_COLD_LINK_PEER_ID = b"-CCX01-" + b"0" * 14


def _parse_source_peers(source_peers: Optional[list[str]]) -> list[tuple[str, int]]:
    """Parse source_peers from link (e.g. 'ip:port' or 'ip') to (ip, port) list."""
    if not source_peers:
        return []
    result: list[tuple[str, int]] = []
    for entry in source_peers:
        if not isinstance(entry, str):
            continue
        s = entry.strip()
        if ":" in s:
            parts = s.rsplit(":", 1)
            try:
                ip, port = parts[0].strip(), int(parts[1].strip())
                result.append((ip, port))
            except (ValueError, IndexError):
                logger.debug("Cold link discovery: skip invalid source_peer %r", entry)
        elif s:
            result.append((s, _DEFAULT_PORT))
    return result


def _peers_from_response(response: Any) -> list[tuple[str, int]]:
    """Convert TrackerResponse.peers (PeerInfo or dict) to list of (ip, port)."""
    out: list[tuple[str, int]] = []
    peers = getattr(response, "peers", None) or []
    for p in peers:
        if hasattr(p, "ip") and hasattr(p, "port"):
            out.append((str(p.ip), int(p.port)))
        elif isinstance(p, dict):
            ip = p.get("ip") or p.get("host")
            port = p.get("port")
            if ip is not None and port is not None:
                out.append((str(ip), int(port)))
    return out


async def _announce_workspace_trackers(
    workspace_id: bytes,
    trackers: list[str],
    port: Optional[int] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[tuple[str, int]]:
    """Announce 32-byte workspace_id to HTTP/HTTPS trackers and return peer list.

    UDP trackers are skipped: BEP 15 fixed format uses 20-byte info_hash; BEP 41
    extends UDP with URLData only, not 32-byte. Uses AsyncTrackerClient without
    session_manager; only HTTP announce is performed.

    Args:
        workspace_id: 32-byte workspace (info) hash.
        trackers: List of tracker URLs from the link.
        port: Client listen port for announce; if None, from config.
        timeout: Per-tracker timeout in seconds.

    Returns:
        List of (ip, port) from all trackers.
    """
    if len(workspace_id) != 32 or not trackers:
        return []
    http_trackers = [
        u.strip()
        for u in trackers
        if isinstance(u, str) and u.strip().lower().startswith(("http://", "https://"))
    ]
    if not http_trackers:
        return []
    if port is None:
        try:
            from ccbt.config.config import get_config

            cfg = get_config()
            port = int(
                getattr(cfg.network, "listen_port_tcp", None)
                or getattr(cfg.network, "listen_port", _DEFAULT_PORT)
            )
        except Exception as e:
            logger.debug("Cold link discovery: could not get listen port: %s", e)
            port = _DEFAULT_PORT
    if not (1 <= port <= 65535):
        port = _DEFAULT_PORT

    from ccbt.discovery.tracker import AsyncTrackerClient

    client = AsyncTrackerClient()
    all_peers: list[tuple[str, int]] = []

    async def announce_one(url: str) -> Optional[Any]:
        torrent_data = {
            "announce": url,
            "info_hash": workspace_id,
            "peer_id": _COLD_LINK_PEER_ID,
        }
        try:
            return await asyncio.wait_for(
                client.announce(
                    torrent_data,
                    port=port,
                    uploaded=0,
                    downloaded=0,
                    left=0,
                    event="started",
                ),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(
                "Cold link discovery: tracker %s announce failed: %s",
                url[:60],
                e,
            )
            return None

    results = await asyncio.gather(
        *[announce_one(url) for url in http_trackers],
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, BaseException):
            logger.debug("Cold link discovery: tracker error: %s", r)
            continue
        if r is not None:
            all_peers.extend(_peers_from_response(r))
    return all_peers


async def discover_peers_for_workspace(
    workspace_id: bytes,
    trackers: Optional[list[str]] = None,
    source_peers: Optional[list[str]] = None,
    dht_client: Optional[Any] = None,
    max_peers: int = _DEFAULT_MAX_PEERS,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[tuple[str, int]]:
    """Discover peers for a workspace (32-byte info_hash).

    Combines source_peers from the link, DHT get_peers (if dht_client given),
    and tracker announce for HTTP/HTTPS trackers (32-byte supported).
    Returns deduplicated list of (ip, port), capped at max_peers.

    Args:
        workspace_id: 32-byte workspace (info) hash.
        trackers: Optional list of tracker URLs from the link (HTTP/HTTPS only for 32-byte).
        source_peers: Optional list of "ip:port" or "ip" from the link.
        dht_client: Optional DHT client with get_peers(info_hash, max_peers=...).
        max_peers: Maximum peers to return.
        timeout: Timeout for DHT/tracker operations.

    Returns:
        List of (ip, port) tuples.
    """
    seen: set[tuple[str, int]] = set()
    result: list[tuple[str, int]] = []

    # 1. Source peers from link (explicit)
    for ip, port in _parse_source_peers(source_peers):
        key = (ip, port)
        if key not in seen:
            seen.add(key)
            result.append(key)
            if len(result) >= max_peers:
                return result[:max_peers]

    # 2. DHT
    if dht_client is not None and len(workspace_id) == 32:
        get_peers = getattr(dht_client, "get_peers", None)
        if callable(get_peers):
            try:
                dht_peers = await asyncio.wait_for(
                    get_peers(workspace_id, max_peers=max_peers),
                    timeout=timeout,
                )
                for p in dht_peers:
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        ip, port = str(p[0]), int(p[1])
                    elif isinstance(p, dict):
                        ip = p.get("ip") or p.get("host")
                        port = p.get("port")
                        if ip is None or port is None:
                            continue
                        ip, port = str(ip), int(port)
                    else:
                        continue
                    key = (ip, port)
                    if key not in seen:
                        seen.add(key)
                        result.append(key)
                        if len(result) >= max_peers:
                            return result[:max_peers]
            except (asyncio.TimeoutError, Exception) as e:
                logger.debug("Cold link discovery: DHT get_peers failed: %s", e)

    # 3. Trackers (HTTP/HTTPS only; UDP does not support 32-byte info_hash)
    if trackers and len(workspace_id) == 32:
        try:
            tracker_peers = await _announce_workspace_trackers(
                workspace_id,
                trackers,
                port=None,
                timeout=timeout,
            )
            for ip, port in tracker_peers:
                key = (ip, port)
                if key not in seen:
                    seen.add(key)
                    result.append(key)
                    if len(result) >= max_peers:
                        return result[:max_peers]
        except Exception as e:
            logger.debug("Cold link discovery: tracker announce failed: %s", e)

    return result[:max_peers]
