"""Background tasks for session manager."""

from __future__ import annotations

import asyncio
import time
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
                        session = self.manager.torrents.pop(info_hash)
                        # BEP 27: Remove from private_torrents set during cleanup
                        self.manager.private_torrents.discard(info_hash)
                        await session.stop()
                        if self.manager.on_torrent_removed:
                            await self.manager.on_torrent_removed(info_hash)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Cleanup loop error")

    async def metrics_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                start_time = time.time()

                # Collect global metrics
                global_stats = self._aggregate_torrent_stats()

                # Track per-second rate history for interface graphs
                sample = {
                    "timestamp": global_stats["timestamp"],
                    "download_rate": global_stats["total_download_rate"],
                    "upload_rate": global_stats["total_upload_rate"],
                }
                self.manager.get_rate_history().append(sample)

                # Emit lightweight heartbeat events periodically so observers can detect stalls
                self.manager.metrics_heartbeat_counter += 1
                if (
                    self.manager.metrics_heartbeat_counter
                    >= self.manager.metrics_heartbeat_interval
                ):
                    self.manager.metrics_heartbeat_counter = 0
                    try:
                        from ccbt.utils.events import Event, EventType, emit_event

                        await emit_event(
                            Event(
                                event_type=EventType.MONITORING_HEARTBEAT.value,
                                data={
                                    "timestamp": sample["timestamp"],
                                    "download_rate": sample["download_rate"],
                                    "upload_rate": sample["upload_rate"],
                                    "history_size": len(
                                        self.manager.get_rate_history()
                                    ),
                                },
                            ),
                        )
                    except Exception:  # pragma: no cover - best effort heartbeat
                        self.logger.debug(
                            "Failed to emit monitoring heartbeat", exc_info=True
                        )

                # Emit aggregated metrics at a lower frequency
                if (
                    global_stats["timestamp"] - self.manager.last_metrics_emit
                    >= self.manager.metrics_emit_interval
                ):
                    await self._emit_global_metrics(global_stats)
                    self.manager.last_metrics_emit = global_stats["timestamp"]

                sleep_for = max(
                    self.manager.metrics_sample_interval - (time.time() - start_time),
                    0.0,
                )
                await asyncio.sleep(sleep_for)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Metrics loop error")

    def _aggregate_torrent_stats(self) -> dict[str, Any]:
        """Aggregate statistics from all torrents."""
        total_downloaded = 0
        total_uploaded = 0
        total_left = 0
        total_peers = 0
        total_download_rate = 0.0
        total_upload_rate = 0.0

        for torrent in self.manager.torrents.values():
            total_downloaded += torrent.downloaded_bytes
            total_uploaded += torrent.uploaded_bytes
            total_left += torrent.left_bytes
            total_peers += len(torrent.peers)
            total_download_rate += torrent.download_rate
            total_upload_rate += torrent.upload_rate

        return {
            "total_torrents": len(self.manager.torrents),
            "total_downloaded": total_downloaded,
            "total_uploaded": total_uploaded,
            "total_left": total_left,
            "total_peers": total_peers,
            "total_download_rate": total_download_rate,
            "total_upload_rate": total_upload_rate,
            "timestamp": time.time(),
        }

    async def _emit_global_metrics(self, stats: dict[str, Any]) -> None:
        """Emit global metrics event.

        Args:
            stats: Dictionary with aggregated statistics

        """
        from ccbt.utils.events import Event, EventType, emit_event

        await emit_event(
            Event(
                event_type=EventType.GLOBAL_METRICS_UPDATE.value,
                data=stats,
            ),
        )
