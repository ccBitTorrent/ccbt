"""Metrics and status monitoring for torrent sessions."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any, Optional

from ccbt.session.tasks import TaskSupervisor

if TYPE_CHECKING:
    from ccbt.session.models import SessionContext


class MetricsAndStatus:
    """Status aggregation and metrics emission helper for session/manager."""

    def __init__(
        self, ctx: SessionContext, tasks: Optional[TaskSupervisor] = None
    ) -> None:
        """Initialize the metrics and status helper with session context and optional task supervisor."""
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()

    def aggregate_torrent_stats(self, torrents: dict[bytes, Any]) -> dict[str, Any]:
        """Aggregate statistics from all torrents.

        Args:
            torrents: Dictionary mapping info_hash to AsyncTorrentSession instances

        Returns:
            Dictionary with aggregated statistics

        """
        total_downloaded = 0
        total_uploaded = 0
        total_left = 0
        total_peers = 0
        total_download_rate = 0.0
        total_upload_rate = 0.0

        for torrent in torrents.values():
            total_downloaded += torrent.downloaded_bytes
            total_uploaded += torrent.uploaded_bytes
            total_left += torrent.left_bytes
            # Session.peers is {"count": n}; use count, not len(dict)
            total_peers += (getattr(torrent, "peers", None) or {}).get("count", 0)
            total_download_rate += torrent.download_rate
            total_upload_rate += torrent.upload_rate

        return {
            "total_torrents": len(torrents),
            "total_downloaded": total_downloaded,
            "total_uploaded": total_uploaded,
            "total_left": total_left,
            "total_peers": total_peers,
            "total_download_rate": total_download_rate,
            "total_upload_rate": total_upload_rate,
            "timestamp": time.time(),
        }

    async def emit_global_metrics(self, stats: dict[str, Any]) -> None:
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


class StatusLoop:
    """Periodic status monitor loop extracted from session."""

    def __init__(self, session: Any) -> None:
        """Initialize the status loop with an AsyncTorrentSession instance."""
        self.s = session  # AsyncTorrentSession instance

    async def run(self) -> None:
        """Run the status monitoring loop."""
        consecutive_errors = 0
        max_consecutive_errors = 10
        while not self.s.is_stopped():
            try:
                if not self.s.download_manager:
                    self.s.logger.debug(
                        "Status loop: download_manager not available, skipping"
                    )
                    await asyncio.sleep(5)
                    continue

                try:
                    status = await self.s.get_status()
                    consecutive_errors = 0
                except AttributeError as e:
                    consecutive_errors += 1
                    self.s.logger.debug("Status loop: get_status not available: %s", e)
                    if consecutive_errors >= max_consecutive_errors:
                        self.s.logger.exception(
                            "Status loop: Too many consecutive errors (%d), stopping loop",
                            consecutive_errors,
                        )
                        break
                    await asyncio.sleep(5)
                    continue
                except Exception as e:
                    consecutive_errors += 1
                    self.s.logger.warning(
                        "Status loop: Error getting status: %s", e, exc_info=True
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        self.s.logger.exception(
                            "Status loop: Too many consecutive errors (%d), stopping loop",
                            consecutive_errors,
                        )
                        break
                    backoff_time = min(5 * (2 ** min(consecutive_errors, 3)), 30)
                    await asyncio.sleep(backoff_time)
                    continue

                if not isinstance(status, dict):
                    self.s.logger.error(
                        "Status loop: status is not a dict, got %s. Skipping update.",
                        type(status),
                    )
                    await asyncio.sleep(5)
                    continue

                # refresh peer counts
                peer_manager = (
                    getattr(self.s.download_manager, "peer_manager", None)
                    or self.s.peer_manager
                )
                if peer_manager and hasattr(peer_manager, "connections"):
                    try:
                        actual_peer_count = len(peer_manager.connections)  # type: ignore[attr-defined]
                        status["connected_peers"] = actual_peer_count
                    except Exception:
                        pass

                connected_peers = status.get("connected_peers", 0)
                download_rate = status.get("download_rate", 0.0)
                upload_rate = status.get("upload_rate", 0.0)
                download_complete = status.get(
                    "download_complete", status.get("completed", False)
                )
                progress = status.get("progress", 0.0)

                if hasattr(self.s.download_manager, "download_complete"):
                    try:
                        dm_complete = self.s.download_manager.download_complete
                        if isinstance(dm_complete, bool):
                            download_complete = download_complete or dm_complete
                    except Exception:
                        pass

                if download_complete:
                    if self.s.info.status != "seeding":
                        self.s.info.status = "seeding"
                        self.s.logger.info(
                            "Download complete, status changed to seeding: %s",
                            self.s.info.name,
                        )
                elif progress >= 1.0:
                    if self.s.info.status == "downloading":
                        if self.s.piece_manager:
                            verified_count = (
                                len(self.s.piece_manager.verified_pieces)
                                if hasattr(self.s.piece_manager, "verified_pieces")
                                else 0
                            )
                            total_pieces = (
                                self.s.piece_manager.num_pieces
                                if hasattr(self.s.piece_manager, "num_pieces")
                                else 0
                            )
                            if (
                                verified_count == total_pieces
                                and total_pieces > 0
                                and (
                                    download_rate > 0
                                    or connected_peers > 0
                                    or hasattr(self.s, "_download_start_time")
                                )
                            ):
                                self.s.info.status = "seeding"
                                self.s.logger.info(
                                    "Download progress 100%%, status changed to seeding: %s",
                                    self.s.info.name,
                                )
                        else:
                            self.s.logger.warning(
                                "Progress reports 100%% but piece_manager not available for %s. Not switching to seeding.",
                                self.s.info.name,
                            )
                elif self.s.info.status == "starting":
                    download_started = hasattr(
                        self.s.download_manager, "_download_started"
                    ) and getattr(self.s.download_manager, "_download_started", False)
                    if download_started or connected_peers > 0 or download_rate > 0:
                        self.s.info.status = "downloading"
                        self.s.logger.info(
                            "Status changed to downloading: %s (download_started=%s, peers=%d, rate=%.1f)",
                            self.s.info.name,
                            download_started,
                            connected_peers,
                            download_rate,
                        )
                elif (
                    self.s.info.status == "downloading"
                    and connected_peers == 0
                    and download_rate == 0.0
                ):
                    self.s.logger.debug(
                        "Download appears idle (no peers, no rate): %s. Progress: %.1f%%",
                        self.s.info.name,
                        progress * 100,
                    )

                # Update cached status (canonical keys; preserve byte counters)
                # Use setattr to avoid SLF001 for internal cache
                cached_status = {
                    "downloaded": status.get("downloaded", 0),
                    "uploaded": status.get("uploaded", 0),
                    "left": status.get("left", 0),
                    "connected_peers": connected_peers,
                    "download_rate": download_rate,
                    "upload_rate": upload_rate,
                    "progress": progress,
                    "download_complete": download_complete,
                }
                self.s._cached_status = cached_status  # noqa: SLF001

                # CRITICAL FIX: Safety check - if download is complete but files aren't finalized
                # This catches cases where completion was detected but finalization failed or was missed
                if (
                    self.s.piece_manager
                    and len(self.s.piece_manager.verified_pieces)
                    == self.s.piece_manager.num_pieces
                    and hasattr(self.s.download_manager, "file_assembler")
                    and self.s.download_manager.file_assembler is not None
                ):
                    file_assembler = self.s.download_manager.file_assembler
                    written_count = len(file_assembler.written_pieces)
                    total_pieces = file_assembler.num_pieces

                    # If all pieces are verified and written, but status is still downloading, finalize
                    if written_count == total_pieces and self.s.info.status not in {
                        "seeding",
                        "completed",
                    }:
                        self.s.logger.info(
                            "Safety check: All pieces verified and written, but status is '%s'. "
                            "Finalizing files now.",
                            self.s.info.status,
                        )
                        try:
                            await file_assembler.finalize_files()
                            self.s.info.status = "seeding"
                            self.s.logger.info(
                                "Files finalized via safety check for: %s",
                                self.s.info.name,
                            )
                        except Exception as e:
                            self.s.logger.warning(
                                "Safety check finalization failed: %s",
                                e,
                                exc_info=True,
                            )

                if self.s.on_status_update:
                    with contextlib.suppress(Exception):
                        await self.s.on_status_update(status)

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                self.s.logger.exception("Status loop error")
                await asyncio.sleep(5)
