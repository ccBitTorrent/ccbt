"""Peer Exchange (PEX) implementation for BitTorrent (BEP 11).

from __future__ import annotations

Provides peer discovery through connected peers using ut_pex extended messages,
with deduplication, throttling, and reliability scoring.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable

from ccbt.config import get_config


@dataclass
class PexPeer:
    """Represents a peer in PEX."""

    ip: str
    port: int
    peer_id: bytes | None = None
    added_time: float = field(default_factory=time.time)
    source: str = "pex"  # Source of this peer (pex, tracker, dht, etc.)
    reliability_score: float = 1.0


@dataclass
class PexSession:
    """PEX session with a single peer."""

    peer_key: str
    ut_pex_id: int | None = None
    last_pex_time: float = 0.0
    pex_interval: float = 30.0
    is_supported: bool = False
    reliability_score: float = 1.0
    consecutive_failures: int = 0


class AsyncPexManager:
    """High-performance async PEX manager."""

    def __init__(self):
        """Initialize PEX manager."""
        self.config = get_config()

        # PEX sessions per peer
        self.sessions: dict[str, PexSession] = {}

        # Peer tracking
        self.known_peers: dict[tuple[str, int], PexPeer] = {}
        self.peer_sources: dict[tuple[str, int], set[str]] = defaultdict(set)

        # PEX message handling
        self.pex_callbacks: list[Callable[[list[PexPeer]], None]] = []

        # Throttling
        self.peer_add_throttle: deque = deque(maxlen=100)
        self.max_peers_per_interval = 50
        self.throttle_interval = 10.0

        # Background tasks
        self._pex_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start PEX manager."""
        self._pex_task = asyncio.create_task(self._pex_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("PEX manager started")

    async def stop(self) -> None:
        """Stop PEX manager."""
        if self._pex_task:
            self._pex_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pex_task

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        self.logger.info("PEX manager stopped")

    async def _pex_loop(self) -> None:
        """Background task for PEX operations."""
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                await self._send_pex_messages()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("PEX loop error")

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_old_peers()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Cleanup loop error")

    async def _send_pex_messages(self) -> None:
        """Send PEX messages to supported peers."""
        current_time = time.time()

        for session in self.sessions.values():
            if not session.is_supported:
                continue

            # Check if it's time to send PEX
            if current_time - session.last_pex_time < session.pex_interval:
                continue

            try:
                # Send PEX message
                await self._send_pex_to_peer(session)
                session.last_pex_time = current_time
            except Exception as e:
                self.logger.warning("Failed to send PEX to %s: %s", session.peer_key, e)
                session.consecutive_failures += 1

    async def _send_pex_to_peer(self, session: PexSession) -> None:
        """Send PEX message to a specific peer."""
        # This would be implemented to send actual PEX messages
        # For now, just log the action
        self.logger.debug("Sending PEX to %s", session.peer_key)

    async def _cleanup_old_peers(self) -> None:
        """Clean up old peer entries."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour

        to_remove = []
        for peer_key, peer in self.known_peers.items():
            if peer.added_time < cutoff_time:
                to_remove.append(peer_key)

        for peer_key in to_remove:
            del self.known_peers[peer_key]
            if peer_key in self.peer_sources:
                del self.peer_sources[peer_key]

    def add_peer_callback(self, callback: Callable[[list[PexPeer]], None]) -> None:
        """Add callback for new peers discovered via PEX."""
        self.pex_callbacks.append(callback)

    def get_known_peers(self) -> list[PexPeer]:
        """Get list of known peers from PEX."""
        return list(self.known_peers.values())

    def get_peer_count(self) -> int:
        """Get number of known peers."""
        return len(self.known_peers)


# Alias for backward compatibility
PEXManager = AsyncPexManager
