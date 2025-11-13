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
from typing import Awaitable, Callable

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

        # Callback for sending PEX messages via extension protocol
        # Signature: (peer_key: str, peer_data: bytes, is_added: bool) -> bool
        self.send_pex_callback: Callable[[str, bytes, bool], Awaitable[bool]] | None = (
            None
        )

        # Callback to get connected peers for PEX messages
        self.get_connected_peers_callback: (
            Callable[[], Awaitable[list[tuple[str, int]]]] | None
        ) = None

        # Track peers we've already sent to each session (to avoid duplicates)
        self.peers_sent_to_session: dict[str, set[tuple[str, int]]] = defaultdict(set)

        # Track previously known connected peers per session (for dropped peer detection)
        self.previous_connected_peers: dict[str, set[tuple[str, int]]] = defaultdict(
            set
        )

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
        while True:  # pragma: no cover - Background loop, tested via cancellation
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                await (
                    self._send_pex_messages()
                )  # pragma: no cover - Tested via direct calls
            except asyncio.CancelledError:
                break  # pragma: no cover - Cancellation tested separately
            except Exception:  # pragma: no cover - Exception handling tested separately
                self.logger.exception("PEX loop error")

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:  # pragma: no cover - Background loop, tested via cancellation
            try:
                await asyncio.sleep(60)  # Run every minute
                await (
                    self._cleanup_old_peers()
                )  # pragma: no cover - Tested via direct calls
            except asyncio.CancelledError:
                break  # pragma: no cover - Cancellation tested separately
            except Exception:  # pragma: no cover - Exception handling tested separately
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
        if not session.is_supported or not session.ut_pex_id:
            return

        if not self.send_pex_callback:
            self.logger.debug(
                "No PEX send callback registered, cannot send PEX to %s",
                session.peer_key,
            )
            return

        # Get peer lists for added and dropped
        added_peers, dropped_peers = await self._get_pex_peer_lists(session.peer_key)

        added_success = False
        dropped_success = False

        # Send added peers if any
        added_count = len(added_peers) // 6 if added_peers else 0
        if added_peers:
            self.logger.info(
                "PEX: Sending %d added peer(s) to %s",
                added_count,
                session.peer_key,
            )
            try:
                added_success = await self.send_pex_callback(
                    session.peer_key, added_peers, is_added=True
                )
                if not added_success:
                    session.consecutive_failures += 1
                    self.logger.warning(
                        "PEX: Failed to send added peers to %s", session.peer_key
                    )
                else:
                    self.logger.debug(
                        "PEX: Successfully sent %d added peer(s) to %s",
                        added_count,
                        session.peer_key,
                    )
            except Exception as e:
                self.logger.warning(
                    "PEX: Failed to send added peers to %s: %s", session.peer_key, e
                )
                session.consecutive_failures += 1

        # Send dropped peers if any
        dropped_count = len(dropped_peers) // 6 if dropped_peers else 0
        if dropped_peers:
            self.logger.info(
                "PEX: Sending %d dropped peer(s) to %s",
                dropped_count,
                session.peer_key,
            )
            try:
                dropped_success = await self.send_pex_callback(
                    session.peer_key, dropped_peers, is_added=False
                )
                if not dropped_success:
                    session.consecutive_failures += 1
                    self.logger.warning(
                        "PEX: Failed to send dropped peers to %s", session.peer_key
                    )
                else:
                    self.logger.debug(
                        "PEX: Successfully sent %d dropped peer(s) to %s",
                        dropped_count,
                        session.peer_key,
                    )
            except Exception as e:
                self.logger.warning(
                    "PEX: Failed to send dropped peers to %s: %s", session.peer_key, e
                )
                session.consecutive_failures += 1

        # If we sent at least one message successfully, reset failures
        if added_success or dropped_success:
            session.consecutive_failures = 0
            self.logger.info(
                "PEX: Successfully sent PEX to %s (%d added, %d dropped)",
                session.peer_key,
                added_count,
                dropped_count,
            )

    async def _get_pex_peer_lists(self, peer_key: str) -> tuple[bytes, bytes]:
        """Get PEX peer lists for added and dropped peers.

        Args:
            peer_key: The peer we're sending to (will exclude from peer list)

        Returns:
            Tuple of (added_peers_data, dropped_peers_data) as bytes
            Each is empty bytes if no peers of that type

        """
        try:
            from ccbt.extensions.pex import PeerExchange
            from ccbt.extensions.pex import PEXPeer as ExtPEXPeer

            # Get connected peers if callback available
            current_connected = set()
            if self.get_connected_peers_callback:
                try:
                    connected_peers = await self.get_connected_peers_callback()
                    current_connected = {
                        tuple(p) for p in connected_peers if len(p) >= 2
                    }
                except Exception as e:
                    self.logger.debug("Error getting connected peers for PEX: %s", e)

            # Parse peer_key to extract IP and port (format: "ip:port")
            target_ip = None
            target_port = None
            try:
                if ":" in peer_key:
                    parts = peer_key.rsplit(":", 1)
                    if len(parts) == 2:
                        target_ip = parts[0]
                        target_port = int(parts[1])
            except (ValueError, IndexError):
                pass

            # Remove target peer from current connected set
            if target_ip and target_port:
                current_connected.discard((target_ip, target_port))

            # Get previous connected peers for this session
            previous_connected = self.previous_connected_peers[peer_key]

            # Calculate added peers: currently connected but not previously known to this session
            added_peers_set = current_connected - previous_connected
            # Also exclude peers we've already sent to this session
            added_peers_set -= self.peers_sent_to_session[peer_key]

            # Calculate dropped peers: previously known but not currently connected
            dropped_peers_set = previous_connected - current_connected

            # Convert to PEX peer objects
            pex_peers_to_add: list[ExtPEXPeer] = []
            for ip, port in list(added_peers_set)[: self.max_peers_per_interval]:
                pex_peers_to_add.append(ExtPEXPeer(ip=ip, port=port, flags=0))

            pex_peers_to_drop: list[ExtPEXPeer] = []
            for ip, port in list(dropped_peers_set)[: self.max_peers_per_interval]:
                pex_peers_to_drop.append(ExtPEXPeer(ip=ip, port=port, flags=0))

            # Update tracking: mark added peers as sent
            for peer in pex_peers_to_add:
                self.peers_sent_to_session[peer_key].add((peer.ip, peer.port))

            # Update previous connected peers for next time
            self.previous_connected_peers[peer_key] = current_connected.copy()

            # Encode peer lists
            pex_exchange = PeerExchange()

            added_data = b""
            if pex_peers_to_add:
                added_data = pex_exchange.encode_peers_list(pex_peers_to_add)

            dropped_data = b""
            if pex_peers_to_drop:
                dropped_data = pex_exchange.encode_peers_list(pex_peers_to_drop)

            if added_data or dropped_data:
                self.logger.debug(
                    "Built PEX peer lists for %s: %d added, %d dropped",
                    peer_key,
                    len(pex_peers_to_add),
                    len(pex_peers_to_drop),
                )

            return added_data, dropped_data

        except Exception as e:
            self.logger.warning("Error building PEX peer lists: %s", e)
            return b"", b""

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

    async def refresh(self) -> None:
        """Manually trigger PEX refresh to all supported peers."""
        refreshed_count = 0

        # Reset last_pex_time for all sessions to allow immediate refresh
        for session in self.sessions.values():
            if session.is_supported:
                session.last_pex_time = 0.0  # Force immediate send
                refreshed_count += 1

        self.logger.info("PEX refresh triggered for %d peers", refreshed_count)

        try:
            await self._send_pex_messages()
        except Exception as e:
            self.logger.warning("Error during PEX refresh: %s", e)


# Alias for backward compatibility
PEXManager = AsyncPexManager
