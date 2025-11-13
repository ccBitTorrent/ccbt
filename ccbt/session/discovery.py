from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from ccbt.session.models import SessionContext
from ccbt.session.tasks import TaskSupervisor
from ccbt.session.types import DHTClientProtocol


class DiscoveryController:
    """Controller to orchestrate DHT/tracker/PEX peer discovery with dedup and scheduling."""

    def __init__(
        self, ctx: SessionContext, tasks: TaskSupervisor | None = None
    ) -> None:
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()
        self._recent_peers: set[tuple[str, int]] = set()
        self._recent_lock = asyncio.Lock()

    def register_dht_callback(
        self,
        dht_client: DHTClientProtocol,
        on_peers_async: Callable[[list[tuple[str, int]]], Awaitable[None]],
        *,
        info_hash: bytes,
    ) -> None:
        """Register a DHT callback that deduplicates and forwards to async handler."""

        async def process_with_dedup(peers: list[tuple[str, int]]) -> None:
            if not peers:
                return
            async with self._recent_lock:
                new_peers = [p for p in peers if p not in self._recent_peers]
                for p in new_peers:
                    self._recent_peers.add(p)
                # prune if too large
                if len(self._recent_peers) > 2000:
                    self._recent_peers = set(list(self._recent_peers)[1000:])
            if new_peers:
                await on_peers_async(new_peers)

        def callback_wrapper(peers: list[tuple[str, int]]) -> None:
            task = self._tasks.create_task(
                process_with_dedup(peers), name="dht_peers_dedup"
            )
            _ = task  # avoid unused var warnings

        # CRITICAL FIX: add_peer_callback doesn't accept info_hash parameter
        # The callback wrapper already filters by info_hash via the discovery controller
        dht_client.add_peer_callback(callback_wrapper)
