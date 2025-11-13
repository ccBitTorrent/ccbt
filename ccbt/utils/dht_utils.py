"""DHT helper utilities for bootstrap and peer discovery with timeouts."""

from __future__ import annotations

import asyncio
from typing import Any


async def wait_for_bootstrap(dht_client: Any, timeout: float) -> bool:
    """Wait for DHT bootstrap to complete with timeout if supported."""
    if hasattr(dht_client, "wait_for_bootstrap"):
        try:
            return await asyncio.wait_for(
                dht_client.wait_for_bootstrap(timeout=timeout), timeout=timeout
            )
        except asyncio.TimeoutError:
            return False
    # Fallback: assume started if no explicit bootstrap API
    return True


async def get_peers_with_timeout(
    dht_client: Any, info_hash: bytes, max_peers: int, timeout: float
) -> list[tuple[str, int]]:
    """Query DHT for peers with timeout."""
    if not hasattr(dht_client, "get_peers"):
        return []
    try:
        peers = await asyncio.wait_for(
            dht_client.get_peers(info_hash, max_peers=max_peers), timeout=timeout
        )
    except asyncio.TimeoutError:
        return []
    return list(peers or [])
