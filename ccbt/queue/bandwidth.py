"""Bandwidth allocation for torrent queue."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from collections import OrderedDict

from ccbt.models import (
    BandwidthAllocationMode,
    QueueConfig,
    QueueEntry,
)

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.session.session import AsyncSessionManager


class BandwidthAllocator:
    """Allocates bandwidth to torrents based on priority and mode."""

    def __init__(self, config: QueueConfig):
        """Initialize bandwidth allocator.

        Args:
            config: Queue configuration

        """
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def allocate(
        self,
        queue: OrderedDict[bytes, QueueEntry],
        session_manager: AsyncSessionManager,
    ) -> None:
        """Allocate bandwidth to active torrents.

        Args:
            queue: Queue dictionary
            session_manager: Session manager for applying limits

        """
        # Get global limits from config
        global_down = session_manager.config.limits.global_down_kib
        global_up = session_manager.config.limits.global_up_kib

        # Get active torrents (downloading and seeding)
        active_torrents = [
            (info_hash, entry)
            for info_hash, entry in queue.items()
            if entry.status == "active"
        ]

        if not active_torrents:
            return

        # Allocate based on mode
        if (
            self.config.bandwidth_allocation_mode
            == BandwidthAllocationMode.PROPORTIONAL
        ):
            await self._allocate_proportional(
                active_torrents,
                global_down,
                global_up,
                session_manager,
            )
        elif self.config.bandwidth_allocation_mode == BandwidthAllocationMode.EQUAL:
            await self._allocate_equal(
                active_torrents,
                global_down,
                global_up,
                session_manager,
            )
        elif self.config.bandwidth_allocation_mode == BandwidthAllocationMode.FIXED:
            await self._allocate_fixed(
                active_torrents,
                global_down,
                global_up,
                session_manager,
            )
        elif self.config.bandwidth_allocation_mode == BandwidthAllocationMode.MANUAL:
            # Manual mode: use per-torrent limits from queue entries
            await self._allocate_manual(
                active_torrents,
                session_manager,
            )

    async def _allocate_proportional(
        self,
        active_torrents: list[tuple[bytes, QueueEntry]],
        global_down: int,
        global_up: int,
        session_manager: AsyncSessionManager,
    ) -> None:
        """Allocate bandwidth proportionally based on priority weights."""
        # Calculate total weight
        total_weight = sum(
            self.config.priority_weights.get(entry.priority, 1.0)
            for _, entry in active_torrents
        )

        if total_weight == 0:
            return

        # Allocate download bandwidth
        if global_down > 0:
            for _info_hash, entry in active_torrents:
                weight = self.config.priority_weights.get(entry.priority, 1.0)
                allocated = int((weight / total_weight) * global_down)
                entry.allocated_down_kib = max(0, allocated)

        # Allocate upload bandwidth (same logic)
        if global_up > 0:
            for _info_hash, entry in active_torrents:
                weight = self.config.priority_weights.get(entry.priority, 1.0)
                allocated = int((weight / total_weight) * global_up)
                entry.allocated_up_kib = max(0, allocated)

        # Apply limits to session manager (do both together)
        for info_hash, entry in active_torrents:
            await session_manager.set_rate_limits(
                info_hash.hex(),
                entry.allocated_down_kib,
                entry.allocated_up_kib,
            )

    async def _allocate_equal(
        self,
        active_torrents: list[tuple[bytes, QueueEntry]],
        global_down: int,
        global_up: int,
        session_manager: AsyncSessionManager,
    ) -> None:
        """Allocate bandwidth equally to all active torrents."""
        num_active = len(active_torrents)
        if (
            num_active == 0
        ):  # Defensive check (unreachable via public API, but safe to test)
            return

        down_per_torrent = global_down // num_active if global_down > 0 else 0
        up_per_torrent = global_up // num_active if global_up > 0 else 0

        for info_hash, entry in active_torrents:
            entry.allocated_down_kib = down_per_torrent
            entry.allocated_up_kib = up_per_torrent

            await session_manager.set_rate_limits(
                info_hash.hex(),
                entry.allocated_down_kib,
                entry.allocated_up_kib,
            )

    async def _allocate_fixed(
        self,
        active_torrents: list[tuple[bytes, QueueEntry]],
        global_down: int,
        global_up: int,
        session_manager: AsyncSessionManager,
    ) -> None:
        """Allocate fixed bandwidth per priority level."""
        for info_hash, entry in active_torrents:
            # Get fixed bandwidth for this priority
            fixed_down = self.config.priority_bandwidth_kib.get(
                entry.priority,
                0,
            )
            fixed_up = self.config.priority_bandwidth_kib.get(
                entry.priority,
                0,
            )

            # Cap at global limits
            entry.allocated_down_kib = min(
                fixed_down,
                global_down if global_down > 0 else fixed_down,
            )
            entry.allocated_up_kib = min(
                fixed_up,
                global_up if global_up > 0 else fixed_up,
            )

            await session_manager.set_rate_limits(
                info_hash.hex(),
                entry.allocated_down_kib,
                entry.allocated_up_kib,
            )

    async def _allocate_manual(
        self,
        active_torrents: list[tuple[bytes, QueueEntry]],
        session_manager: AsyncSessionManager,
    ) -> None:
        """Use manually set bandwidth from queue entries."""
        for info_hash, entry in active_torrents:
            await session_manager.set_rate_limits(
                info_hash.hex(),
                entry.allocated_down_kib,
                entry.allocated_up_kib,
            )
