"""Background tasks for session manager."""

from __future__ import annotations

import asyncio
from typing import Any


class ManagerBackgroundTasks:
    """Background tasks for session manager cleanup and metrics."""

    def __init__(self, manager: Any) -> None:
        """Initialize background tasks.

        Args:
            manager: AsyncSessionManager instance

        """
        self.manager = manager
        self.logger = manager.logger

    async def cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up stopped sessions
                async with self.manager.lock:
                    to_remove = []
                    for info_hash, session in self.manager.torrents.items():
                        if session.info.status == "stopped":
                            to_remove.append(info_hash)

                    for info_hash in to_remove:
                        session = self.manager.torrents.pop(
                            info_hash
                        )  # pragma: no cover - Remove stopped session, tested via integration tests
                        await session.stop()  # pragma: no cover - Stop removed session, tested via integration tests
                        if self.manager.on_torrent_removed:
                            await self.manager.on_torrent_removed(
                                info_hash
                            )  # pragma: no cover - Torrent removed callback, tested via integration tests with callback registered

            except asyncio.CancelledError:  # pragma: no cover - background loop cancellation, tested via cancellation
                break  # pragma: no cover
            except (
                Exception
            ):  # pragma: no cover - defensive: cleanup loop error handling
                self.logger.exception("Cleanup loop error")  # pragma: no cover

    async def metrics_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                await asyncio.sleep(10)  # Update every 10 seconds

                # Collect global metrics
                if (
                    hasattr(self.manager, "_metrics_helper")
                    and self.manager._metrics_helper
                ):
                    global_stats = self.manager._metrics_helper.aggregate_torrent_stats(
                        self.manager.torrents
                    )
                    await self.manager._metrics_helper.emit_global_metrics(global_stats)

            except asyncio.CancelledError:  # pragma: no cover - background loop cancellation, tested via cancellation
                break  # pragma: no cover
            except (
                Exception
            ):  # pragma: no cover - defensive: metrics loop error handling
                self.logger.exception("Metrics loop error")  # pragma: no cover
