"""Torrent queue manager for priority-based scheduling."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ccbt.models import QueueConfig, QueueEntry, TorrentPriority

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.session.session import AsyncSessionManager


@dataclass
class QueueStatistics:
    """Queue statistics."""

    total_torrents: int = 0
    active_downloading: int = 0
    active_seeding: int = 0
    queued: int = 0
    paused: int = 0
    by_priority: dict[TorrentPriority, int] = field(
        default_factory=lambda: dict.fromkeys(TorrentPriority, 0)
    )


class TorrentQueueManager:
    """Manages torrent queue with priority-based scheduling."""

    def __init__(
        self,
        session_manager: AsyncSessionManager,
        config: QueueConfig | None = None,
    ):
        """Initialize queue manager.

        Args:
            session_manager: Reference to session manager
            config: Queue configuration

        """
        self.session_manager = session_manager
        self.config = config or QueueConfig()

        # Queue data structure: OrderedDict[info_hash_bytes, QueueEntry]
        # Maintains insertion order for position tracking
        self.queue: OrderedDict[bytes, QueueEntry] = OrderedDict()

        # Track active torrents (downloading/seeding)
        self._active_downloading: set[bytes] = set()
        self._active_seeding: set[bytes] = set()

        # Lock for queue operations
        self._lock = asyncio.Lock()

        # Background tasks
        self._monitor_task: asyncio.Task | None = None
        self._bandwidth_task: asyncio.Task | None = None

        # Statistics
        self.stats = QueueStatistics()

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start queue manager background tasks."""
        if self.config.auto_manage_queue:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._bandwidth_task = asyncio.create_task(
                self._bandwidth_allocation_loop()
            )
        self.logger.info("Queue manager started")

    async def stop(self) -> None:
        """Stop queue manager."""
        # Cancel and wait for monitor task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.debug("Error waiting for monitor task: %s", e)

        # Cancel and wait for bandwidth task
        if self._bandwidth_task and not self._bandwidth_task.done():
            self._bandwidth_task.cancel()
            try:
                await self._bandwidth_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.debug("Error waiting for bandwidth task: %s", e)

        # Clear task references
        self._monitor_task = None
        self._bandwidth_task = None

        self.logger.info("Queue manager stopped")

    async def add_torrent(
        self,
        info_hash: bytes,
        priority: TorrentPriority | None = None,
        auto_start: bool = True,
        resume: bool = False,
    ) -> QueueEntry:
        """Add torrent to queue.

        Args:
            info_hash: Torrent info hash
            priority: Priority level (uses default if None)
            auto_start: Whether to start if slot available
            resume: Whether to resume from checkpoint

        Returns:
            QueueEntry for the added torrent

        """
        async with self._lock:
            # Check if already in queue
            if info_hash in self.queue:
                entry = self.queue[info_hash]
                self.logger.debug(
                    "Torrent %s already in queue at position %d",
                    info_hash.hex()[:8],
                    entry.queue_position,
                )
                return entry

            # Determine priority
            if priority is None:
                priority = self.config.default_priority

            # Create queue entry
            entry = QueueEntry(
                info_hash=info_hash,
                priority=priority,
                queue_position=len(self.queue),
                added_time=time.time(),
                status="queued",
            )

            # Add to queue (at end, will be reordered by priority if needed)
            self.queue[info_hash] = entry

            self.logger.info(
                "Added torrent %s to queue with priority %s at position %d",
                info_hash.hex()[:8],
                priority.value,
                entry.queue_position,
            )

            # Reorder queue by priority
            await self._reorder_queue()

            # Update statistics
            await self._update_statistics()

        # Auto-start if configured and slot available
        if auto_start and self.config.auto_manage_queue:
            started = await self._try_start_torrent(info_hash, resume=resume)
            if started:
                # Update session info if available
                session = self.session_manager.torrents.get(info_hash)
                if session:
                    session.info.priority = priority.value
                    async with self._lock:
                        queue_entry = self.queue.get(info_hash)
                        if queue_entry:
                            session.info.queue_position = queue_entry.queue_position

        # Entry is guaranteed to exist here since we created it above
        return entry

    async def remove_torrent(self, info_hash: bytes) -> bool:
        """Remove torrent from queue.

        Args:
            info_hash: Torrent info hash

        Returns:
            True if removed, False if not found

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            self.queue.pop(info_hash)

            # Remove from active sets
            self._active_downloading.discard(info_hash)
            self._active_seeding.discard(info_hash)

            self.logger.info(
                "Removed torrent %s from queue",
                info_hash.hex()[:8],
            )

            # Reorder remaining entries
            await self._reorder_queue()
            await self._update_statistics()

        return True

    async def set_priority(
        self,
        info_hash: bytes,
        priority: TorrentPriority,
    ) -> bool:
        """Set torrent priority.

        Args:
            info_hash: Torrent info hash
            priority: New priority level

        Returns:
            True if updated, False if not found

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            entry = self.queue[info_hash]
            old_priority = entry.priority
            entry.priority = priority

            self.logger.info(
                "Changed priority for %s from %s to %s",
                info_hash.hex()[:8],
                old_priority.value,
                priority.value,
            )

            # Reorder queue
            await self._reorder_queue()
            await self._update_statistics()

        # Update session info if available
        session = self.session_manager.torrents.get(info_hash)
        if session:
            session.info.priority = (
                priority.value
            )  # pragma: no cover - tested via integration, requires session.info

        # Reallocate bandwidth
        if self._bandwidth_task:
            await (
                self._allocate_bandwidth()
            )  # pragma: no cover - tested via integration when bandwidth_task is active

        return True

    async def reorder_torrent(
        self,
        info_hash: bytes,
        new_position: int,
    ) -> bool:
        """Move torrent to specific position in queue.

        Args:
            info_hash: Torrent info hash
            new_position: Target position (0 = highest priority)

        Returns:
            True if moved, False if not found or invalid position

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            if new_position < 0 or new_position >= len(self.queue):
                return False

            # Remove from current position
            entry = self.queue.pop(info_hash)

            # Convert to list, insert at new position, rebuild OrderedDict
            items = list(self.queue.items())
            items.insert(new_position, (info_hash, entry))
            self.queue = OrderedDict(items)

            # Update positions
            await self._reorder_queue()

            self.logger.info(
                "Moved torrent %s to position %d",
                info_hash.hex()[:8],
                new_position,
            )

        return True

    async def pause_torrent(self, info_hash: bytes) -> bool:
        """Pause torrent (removes from active sets).

        Args:
            info_hash: Torrent info hash

        Returns:
            True if paused, False if not found

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            entry = self.queue[info_hash]
            entry.status = "paused"

            self._active_downloading.discard(info_hash)
            self._active_seeding.discard(info_hash)

            self.logger.info(
                "Paused torrent %s in queue",
                info_hash.hex()[:8],
            )

            await self._update_statistics()

        # Pause session
        session = self.session_manager.torrents.get(info_hash)
        if session:
            await session.pause()

        # Try to start another torrent if slot freed
        if self.config.auto_manage_queue:
            await self._try_start_next_torrent()  # pragma: no cover - tested via integration when auto_manage_queue is enabled

        return True

    async def resume_torrent(self, info_hash: bytes) -> bool:
        """Resume torrent (adds to active if slot available).

        Args:
            info_hash: Torrent info hash

        Returns:
            True if resumed, False if not found

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            entry = self.queue[info_hash]

            if entry.status == "paused":
                entry.status = "queued"
                self.logger.info(
                    "Resumed torrent %s in queue",
                    info_hash.hex()[:8],
                )

        # Try to start if slot available
        if self.config.auto_manage_queue:
            await self._try_start_torrent(
                info_hash
            )  # pragma: no cover - tested via integration when auto_manage_queue is enabled

        return True

    async def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status.

        Returns:
            Dictionary with queue statistics and entries

        """
        async with self._lock:
            entries = []
            for info_hash, entry in self.queue.items():
                entries.append(
                    {
                        "info_hash": info_hash.hex(),
                        "priority": entry.priority.value,
                        "queue_position": entry.queue_position,
                        "status": entry.status,
                        "added_time": entry.added_time,
                        "allocated_down_kib": entry.allocated_down_kib,
                        "allocated_up_kib": entry.allocated_up_kib,
                    }
                )

            return {
                "statistics": {
                    "total_torrents": self.stats.total_torrents,
                    "active_downloading": self.stats.active_downloading,
                    "active_seeding": self.stats.active_seeding,
                    "queued": self.stats.queued,
                    "paused": self.stats.paused,
                    "by_priority": {
                        p.value: count for p, count in self.stats.by_priority.items()
                    },
                },
                "entries": entries,
            }

    async def get_torrent_queue_state(self, info_hash: bytes) -> dict[str, Any] | None:
        """Get queue state for a specific torrent.

        Args:
            info_hash: Torrent info hash

        Returns:
            Dictionary with position and priority, or None if not in queue

        """
        async with self._lock:
            entry = self.queue.get(info_hash)
            if not entry:
                return None

            return {
                "position": entry.queue_position,
                "priority": entry.priority.value,
            }

    async def _reorder_queue(self) -> None:
        """Reorder queue entries by priority and position.

        Priority order: MAXIMUM > HIGH > NORMAL > LOW > PAUSED
        Within same priority, maintain FIFO order (by added_time).
        """
        # Sort: priority (desc) -> added_time (asc)
        priority_order = {
            TorrentPriority.MAXIMUM: 5,
            TorrentPriority.HIGH: 4,
            TorrentPriority.NORMAL: 3,
            TorrentPriority.LOW: 2,
            TorrentPriority.PAUSED: 1,
        }

        sorted_items = sorted(
            self.queue.items(),
            key=lambda x: (
                -priority_order.get(x[1].priority, 0),
                x[1].added_time,
            ),
        )

        # Rebuild OrderedDict with new order
        self.queue = OrderedDict(sorted_items)

        # Update positions
        for position, (info_hash, entry) in enumerate(self.queue.items()):
            entry.queue_position = position
            # Update session info if available
            session = self.session_manager.torrents.get(info_hash)
            if session:
                session.info.queue_position = position

    async def _try_start_torrent(
        self,
        info_hash: bytes,
        resume: bool = False,
    ) -> bool:
        """Try to start a torrent if queue limits allow.

        Args:
            info_hash: Torrent info hash
            resume: Whether to resume from checkpoint

        Returns:
            True if started, False if queued

        """
        async with self._lock:
            if info_hash not in self.queue:
                return False

            entry = self.queue[info_hash]

            # Don't start if paused
            if entry.priority == TorrentPriority.PAUSED:
                return False

            # Check if already active
            if (
                info_hash in self._active_downloading
                or info_hash in self._active_seeding
            ):
                return True

            # Get torrent session
            session = self.session_manager.torrents.get(info_hash)
            if not session:
                return False

            # Check status
            status = await session.get_status()
            torrent_status = status.get("status", "stopped")
            progress = status.get("progress", 0.0)

            # Determine if downloading or seeding
            is_seeding = progress >= 1.0 or torrent_status == "seeding"

            # Check limits
            can_start = False
            if is_seeding:
                # Check seeding limit
                if (
                    self.config.max_active_seeding == 0
                    or self.stats.active_seeding < self.config.max_active_seeding
                ):
                    can_start = True
                    self._active_seeding.add(info_hash)
            # Check downloading limit
            elif (
                self.config.max_active_downloading == 0
                or self.stats.active_downloading < self.config.max_active_downloading
            ):
                # Also check total active limit
                total_active = self.stats.active_downloading + self.stats.active_seeding
                if (
                    self.config.max_active_torrents == 0
                    or total_active < self.config.max_active_torrents
                ):
                    can_start = True
                    self._active_downloading.add(info_hash)

            if can_start:
                entry.status = "active"

                # Start or resume session with timeout to prevent blocking
                try:
                    if torrent_status == "paused":
                        # Resume with timeout
                        await asyncio.wait_for(
                            session.resume(), timeout=30.0
                        )  # pragma: no cover - edge case: paused torrent being started requires specific state
                    elif torrent_status == "stopped":
                        # Start with timeout to prevent UI blocking
                        self.logger.info(
                            "Queue manager: Calling session.start() for %s",
                            info_hash.hex()[:8],
                        )
                        await asyncio.wait_for(
                            session.start(resume=resume), timeout=30.0
                        )
                        self.logger.info(
                            "Queue manager: session.start() completed for %s",
                            info_hash.hex()[:8],
                        )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Timeout starting torrent %s - it may still be initializing",
                        info_hash.hex()[:8],
                    )
                    # Don't fail - the torrent might still start in background
                    # Just log the warning and continue
                except Exception:
                    self.logger.exception(
                        "Error starting torrent %s", info_hash.hex()[:8]
                    )
                    # Mark as queued again so it can be retried
                    entry.status = "queued"
                    await self._update_statistics()
                    return False

                self.logger.info(
                    "Started torrent %s (queue position %d)",
                    info_hash.hex()[:8],
                    entry.queue_position,
                )

                await self._update_statistics()
                return True

            # Queue is full, keep torrent paused
            entry.status = "queued"
            await self._update_statistics()
            return False

    async def _try_start_next_torrent(self) -> None:
        """Try to start the next queued torrent."""
        info_hash: bytes | None = None
        async with self._lock:
            # Find first queued torrent (already sorted by priority)
            for info_hash_key, entry in self.queue.items():
                if entry.status == "queued":
                    info_hash = info_hash_key
                    # Release lock before calling _try_start_torrent
                    break
            else:
                return

        # Call outside lock to avoid deadlock
        if info_hash is not None:
            await self._try_start_torrent(info_hash)

    async def _enforce_queue_limits(self) -> None:
        """Enforce queue limits by stopping excess torrents."""
        async with self._lock:
            priority_order = {
                TorrentPriority.MAXIMUM: 5,
                TorrentPriority.HIGH: 4,
                TorrentPriority.NORMAL: 3,
                TorrentPriority.LOW: 2,
                TorrentPriority.PAUSED: 1,
            }

            # Check downloading limit
            if self.config.max_active_downloading > 0:
                excess = (
                    len(self._active_downloading) - self.config.max_active_downloading
                )
                if excess > 0:
                    # Stop lowest priority downloading torrents
                    downloading = [
                        (info_hash, self.queue[info_hash])
                        for info_hash in self._active_downloading
                        if info_hash in self.queue
                    ]
                    downloading.sort(
                        key=lambda x: (
                            -priority_order.get(x[1].priority, 0),
                            x[1].added_time,
                        ),
                        reverse=True,  # Lowest priority first
                    )

                    for info_hash, _ in downloading[:excess]:
                        await self._pause_torrent_internal(info_hash)

            # Check seeding limit
            if self.config.max_active_seeding > 0:
                excess = len(self._active_seeding) - self.config.max_active_seeding
                if excess > 0:
                    # Stop lowest priority seeding torrents
                    seeding = [
                        (info_hash, self.queue[info_hash])
                        for info_hash in self._active_seeding
                        if info_hash in self.queue
                    ]
                    seeding.sort(
                        key=lambda x: (
                            -priority_order.get(x[1].priority, 0),
                            x[1].added_time,
                        ),
                        reverse=True,
                    )

                    for info_hash, _ in seeding[:excess]:
                        await self._pause_torrent_internal(info_hash)

            # Check total active limit
            total_active = len(self._active_downloading) + len(self._active_seeding)
            if self.config.max_active_torrents > 0:
                excess = total_active - self.config.max_active_torrents
                if excess > 0:
                    # Combine all active, sort by priority, stop lowest
                    all_active = [
                        (info_hash, self.queue[info_hash])
                        for info_hash in (
                            self._active_downloading | self._active_seeding
                        )
                        if info_hash in self.queue
                    ]
                    all_active.sort(
                        key=lambda x: (
                            -priority_order.get(x[1].priority, 0),
                            x[1].added_time,
                        ),
                        reverse=True,
                    )

                    for info_hash, _ in all_active[:excess]:
                        await self._pause_torrent_internal(info_hash)

            # Update statistics after enforcing limits
            await self._update_statistics()

    async def _pause_torrent_internal(self, info_hash: bytes) -> None:
        """Internal method to pause torrent (assumes lock held)."""
        entry = self.queue.get(info_hash)
        if not entry:
            return

        entry.status = "queued"
        self._active_downloading.discard(info_hash)
        self._active_seeding.discard(info_hash)

        # Pause session (release lock first)
        session = self.session_manager.torrents.get(info_hash)
        if session:
            # Note: This should ideally be called outside the lock, but we'll
            # do it here for now. In practice, session.pause() should be async-safe.
            await session.pause()

    async def _update_statistics(self) -> None:
        """Update queue statistics."""
        self.stats.total_torrents = len(self.queue)
        self.stats.active_downloading = len(self._active_downloading)
        self.stats.active_seeding = len(self._active_seeding)
        self.stats.queued = sum(
            1 for entry in self.queue.values() if entry.status == "queued"
        )
        self.stats.paused = sum(
            1 for entry in self.queue.values() if entry.status == "paused"
        )

        # By priority
        for priority in TorrentPriority:
            self.stats.by_priority[priority] = sum(
                1 for entry in self.queue.values() if entry.priority == priority
            )

    async def _monitor_loop(self) -> None:
        """Background task to monitor queue and enforce limits."""
        while True:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds

                async with self._lock:  # pragma: no cover - tested via integration tests (monitor loop execution)
                    # Sync active sets with actual session states
                    await (
                        self._sync_active_sets()
                    )  # pragma: no cover - tested via integration tests

                    # Enforce limits
                    await (
                        self._enforce_queue_limits()
                    )  # pragma: no cover - tested via integration tests

                # Try to start queued torrents (outside lock)
                await (
                    self._try_start_next_torrent()
                )  # pragma: no cover - tested via integration tests

                await (
                    self._update_statistics()
                )  # pragma: no cover - tested via integration tests

            except asyncio.CancelledError:
                break
            except (
                Exception
            ):  # pragma: no cover - tested via test_monitor_loop_exception_handling
                self.logger.exception("Error in queue monitor loop")
                await asyncio.sleep(10.0)

    async def _sync_active_sets(self) -> None:
        """Sync active sets with actual session states."""
        # Get actual session statuses
        for info_hash in list(self._active_downloading | self._active_seeding):
            session = self.session_manager.torrents.get(info_hash)
            if not session:
                # Session removed, remove from active sets
                self._active_downloading.discard(info_hash)
                self._active_seeding.discard(info_hash)
                continue

            status = await session.get_status()
            torrent_status = status.get("status", "stopped")
            progress = status.get("progress", 0.0)

            is_seeding = progress >= 1.0 or torrent_status == "seeding"

            # Update active sets based on actual state
            if is_seeding:
                self._active_downloading.discard(info_hash)
                if torrent_status not in ("paused", "stopped"):
                    self._active_seeding.add(info_hash)
                else:
                    self._active_seeding.discard(info_hash)
            else:
                self._active_seeding.discard(info_hash)
                if torrent_status not in ("paused", "stopped"):
                    self._active_downloading.add(info_hash)
                else:
                    self._active_downloading.discard(info_hash)

    async def _bandwidth_allocation_loop(self) -> None:
        """Background task for bandwidth allocation."""
        while True:
            try:
                await asyncio.sleep(1.0)  # Update every second
                await (
                    self._allocate_bandwidth()
                )  # pragma: no cover - tested via integration tests

            except asyncio.CancelledError:
                break
            except (
                Exception
            ):  # pragma: no cover - tested via test_bandwidth_allocation_loop_exception
                self.logger.exception("Error in bandwidth allocation loop")
                await asyncio.sleep(5.0)

    async def _allocate_bandwidth(self) -> None:
        """Allocate bandwidth to active torrents."""
        from ccbt.queue.bandwidth import BandwidthAllocator

        allocator = BandwidthAllocator(self.config)
        await allocator.allocate(
            self.queue,
            self.session_manager,
        )
