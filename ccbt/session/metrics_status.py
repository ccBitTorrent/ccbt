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
                connection_summary: Optional[dict[str, int]] = None
                local_requestable_from_summary: Optional[int] = None
                if peer_manager and hasattr(peer_manager, "connections"):
                    try:
                        if hasattr(peer_manager, "get_connection_summary"):
                            connection_summary = (
                                await peer_manager.get_connection_summary()
                            )  # type: ignore[attr-defined]
                            status["connected_peers"] = connection_summary.get(
                                "active_connections", 0
                            )
                            status["total_connections"] = connection_summary.get(
                                "total_connections", 0
                            )
                            status["requestable_peers"] = connection_summary.get(
                                "requestable_connections", 0
                            )
                            status["remote_choked_peers"] = connection_summary.get(
                                "remote_choked_connections", 0
                            )
                            status["pipeline_saturated_peers"] = connection_summary.get(
                                "pipeline_saturated_connections", 0
                            )
                            status["productive_peers"] = connection_summary.get(
                                "productive_connections", 0
                            )
                            status["handshake_complete_peers"] = connection_summary.get(
                                "handshake_complete_connections", 0
                            )
                            status["extension_capable_peers"] = connection_summary.get(
                                "extension_capable_connections", 0
                            )
                            status["metadata_capable_peers"] = connection_summary.get(
                                "metadata_capable_connections", 0
                            )
                            local_requestable_from_summary = int(
                                connection_summary.get("requestable_connections", 0)
                                or 0
                            )
                        else:
                            actual_peer_count = len(peer_manager.connections)  # type: ignore[attr-defined]
                            status["connected_peers"] = actual_peer_count
                            status["total_connections"] = actual_peer_count
                    except Exception as exc:
                        self.s.logger.debug(
                            "Failed to read peer connection summary for %s: %s",
                            getattr(self.s, "info_hash", getattr(self.s, "info", None)),
                            exc,
                        )

                connected_peers = status.get("connected_peers", 0)
                productive_peers = status.get("productive_peers", connected_peers)
                requestable_peers = status.get("requestable_peers", 0)
                remote_choked_peers = int(status.get("remote_choked_peers", 0) or 0)
                pipeline_saturated_peers = int(
                    status.get("pipeline_saturated_peers", 0) or 0
                )
                handshake_complete_peers = int(
                    status.get("handshake_complete_peers", 0) or 0
                )
                extension_capable_peers = int(
                    status.get("extension_capable_peers", 0) or 0
                )
                metadata_capable_peers = int(
                    status.get("metadata_capable_peers", 0) or 0
                )
                download_rate = status.get("download_rate", 0.0)
                upload_rate = status.get("upload_rate", 0.0)
                download_complete = status.get(
                    "download_complete", status.get("completed", False)
                )
                progress = status.get("progress", 0.0)
                peers_with_piece_info = 0
                piece_metrics: dict[str, Any] = {}
                if self.s.piece_manager:
                    with contextlib.suppress(Exception):
                        peers_with_piece_info = len(
                            getattr(self.s.piece_manager, "peer_availability", {})
                        )
                    with contextlib.suppress(Exception):
                        piece_metrics = (
                            self.s.piece_manager.get_piece_selection_metrics()
                        )
                if hasattr(self.s, "_get_swarm_recovery_state"):
                    with contextlib.suppress(Exception):
                        swarm_state = await self.s._get_swarm_recovery_state()  # noqa: SLF001
                        connected_from_swarm = int(
                            swarm_state.get("active_peers", 0) or 0
                        )
                        productive_from_swarm = int(
                            swarm_state.get("productive_peers", 0) or 0
                        )
                        requestable_from_swarm = int(
                            swarm_state.get("requestable_peers", 0) or 0
                        )
                        remote_choked_from_swarm = int(
                            swarm_state.get("remote_choked_peers", 0) or 0
                        )
                        pipeline_saturated_from_swarm = int(
                            swarm_state.get("pipeline_saturated_peers", 0) or 0
                        )
                        handshake_complete_from_swarm = int(
                            swarm_state.get("handshake_complete_peers", 0) or 0
                        )
                        extension_capable_from_swarm = int(
                            swarm_state.get("extension_capable_peers", 0) or 0
                        )
                        metadata_capable_from_swarm = int(
                            swarm_state.get("metadata_capable_peers", 0) or 0
                        )
                        piece_info_from_swarm = int(
                            swarm_state.get("peers_with_piece_info", 0) or 0
                        )
                        if connected_from_swarm > 0 or connected_peers == 0:
                            connected_peers = connected_from_swarm
                        if productive_from_swarm > 0 or productive_peers == 0:
                            productive_peers = productive_from_swarm
                        remote_choked_peers += remote_choked_from_swarm
                        pipeline_saturated_peers += pipeline_saturated_from_swarm
                        requestable_peers = max(
                            int(requestable_peers or 0),
                            int(local_requestable_from_summary or 0),
                            requestable_from_swarm,
                        )
                        if (
                            handshake_complete_from_swarm > 0
                            or handshake_complete_peers == 0
                        ):
                            handshake_complete_peers = handshake_complete_from_swarm
                        if (
                            extension_capable_from_swarm > 0
                            or extension_capable_peers == 0
                        ):
                            extension_capable_peers = extension_capable_from_swarm
                        if (
                            metadata_capable_from_swarm > 0
                            or metadata_capable_peers == 0
                        ):
                            metadata_capable_peers = metadata_capable_from_swarm
                        if piece_info_from_swarm > 0 or peers_with_piece_info == 0:
                            peers_with_piece_info = piece_info_from_swarm
                active_block_requests = int(
                    piece_metrics.get("active_block_requests", 0) or 0
                )
                hash_verification_failures = int(
                    piece_metrics.get("hash_verification_failures", 0) or 0
                )
                metadata_incomplete = bool(
                    self.s._metadata_is_incomplete()  # noqa: SLF001
                    if hasattr(self.s, "_metadata_is_incomplete")
                    else False
                )
                tracker_anomalies = 0
                tracker = getattr(self.s, "tracker", None)
                if tracker and hasattr(tracker, "get_session_metrics"):
                    with contextlib.suppress(Exception):
                        tracker_metrics = tracker.get_session_metrics()
                        tracker_anomalies = sum(
                            int(metrics.get("resolution_anomaly_count", 0) or 0)
                            for metrics in tracker_metrics.values()
                            if isinstance(metrics, dict)
                        )
                if tracker_anomalies > 0 and (
                    getattr(self.s, "_last_tracker_resolution_anomalies", None)
                    != tracker_anomalies
                ):
                    vars(self.s)["_last_tracker_resolution_anomalies"] = (
                        tracker_anomalies
                    )
                    self.s.logger.warning(
                        "TRACKER_RESOLUTION_ANOMALY: Detected %d tracker resolution anomaly/anomalies (public tracker hostname resolved to loopback/private address during fallback or connect).",
                        tracker_anomalies,
                    )

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
                    and productive_peers == 0
                    and download_rate == 0.0
                ):
                    self.s.logger.warning(
                        "Download appears stalled (connected=%d, productive=%d, requestable=%d, piece_info=%d, active_requests=%d, hash_failures=%d, rate=%.1f, summary=%s): %s. Progress: %.1f%%",
                        connected_peers,
                        productive_peers,
                        requestable_peers,
                        peers_with_piece_info,
                        active_block_requests,
                        hash_verification_failures,
                        download_rate,
                        connection_summary,
                        self.s.info.name,
                        progress * 100,
                    )
                    if connected_peers > 0 and peers_with_piece_info == 0:
                        no_piece_info_marker = (
                            connected_peers,
                            requestable_peers,
                            active_block_requests,
                            hash_verification_failures,
                        )
                        if (
                            getattr(self.s, "_last_no_piece_info_marker", None)
                            != no_piece_info_marker
                        ):
                            vars(self.s)["_last_no_piece_info_marker"] = (
                                no_piece_info_marker
                            )
                            self.s.logger.warning(
                                "STALL_MARKER[connected_no_availability]: metadata is complete but connected peers still have no piece availability "
                                "(connected=%d, requestable=%d, active_requests=%d, hash_failures=%d): %s",
                                connected_peers,
                                requestable_peers,
                                active_block_requests,
                                hash_verification_failures,
                                self.s.info.name,
                            )
                    if (
                        metadata_incomplete
                        and handshake_complete_peers > 0
                        and extension_capable_peers == 0
                    ):
                        handshake_no_extension_marker = (
                            connected_peers,
                            handshake_complete_peers,
                            metadata_capable_peers,
                        )
                        if (
                            getattr(self.s, "_last_handshake_no_extension_marker", None)
                            != handshake_no_extension_marker
                        ):
                            vars(self.s)["_last_handshake_no_extension_marker"] = (
                                handshake_no_extension_marker
                            )
                            self.s.logger.warning(
                                "STALL_MARKER[handshake_complete_but_no_extension]: peers are completing the base handshake but none advertise BEP 10 support "
                                "(connected=%d, handshake_complete=%d, metadata_capable=%d): %s",
                                connected_peers,
                                handshake_complete_peers,
                                metadata_capable_peers,
                                self.s.info.name,
                            )
                    if (
                        metadata_incomplete
                        and extension_capable_peers > 0
                        and metadata_capable_peers == 0
                    ):
                        extension_no_metadata_marker = (
                            connected_peers,
                            handshake_complete_peers,
                            extension_capable_peers,
                        )
                        if (
                            getattr(self.s, "_last_extension_no_metadata_marker", None)
                            != extension_no_metadata_marker
                        ):
                            vars(self.s)["_last_extension_no_metadata_marker"] = (
                                extension_no_metadata_marker
                            )
                            self.s.logger.warning(
                                "STALL_MARKER[extension_complete_but_no_metadata]: peers advertise extension support but none have progressed to ut_metadata capability "
                                "(connected=%d, handshake_complete=%d, extension_capable=%d): %s",
                                connected_peers,
                                handshake_complete_peers,
                                extension_capable_peers,
                                self.s.info.name,
                            )
                    if (
                        connected_peers > 0
                        and peers_with_piece_info > 0
                        and requestable_peers == 0
                    ):
                        no_requestable_marker = (
                            connected_peers,
                            peers_with_piece_info,
                            active_block_requests,
                            hash_verification_failures,
                        )
                        if (
                            getattr(self.s, "_last_no_requestable_marker", None)
                            != no_requestable_marker
                        ):
                            vars(self.s)["_last_no_requestable_marker"] = (
                                no_requestable_marker
                            )
                            self.s.logger.warning(
                                "STALL_MARKER[availability_no_requestable_peers]: peers have advertised availability but none are currently requestable "
                                "(connected=%d, piece_info=%d, active_requests=%d, hash_failures=%d): %s",
                                connected_peers,
                                peers_with_piece_info,
                                active_block_requests,
                                hash_verification_failures,
                                self.s.info.name,
                            )
                    dht_client = getattr(
                        getattr(self.s, "session_manager", None), "dht_client", None
                    )
                    routing_table_size = 0
                    if dht_client is not None:
                        with contextlib.suppress(Exception):
                            routing_table_size = len(
                                getattr(
                                    getattr(dht_client, "routing_table", None),
                                    "nodes",
                                    [],
                                )
                            )
                    if (
                        metadata_incomplete
                        and routing_table_size == 0
                        and connected_peers == 0
                        and productive_peers == 0
                    ):
                        zero_node_marker = (
                            connected_peers,
                            productive_peers,
                            routing_table_size,
                        )
                        if (
                            getattr(self.s, "_last_zero_node_dht_marker", None)
                            != zero_node_marker
                        ):
                            vars(self.s)["_last_zero_node_dht_marker"] = (
                                zero_node_marker
                            )
                            self.s.logger.warning(
                                "STALL_MARKER[zero_node_dht_lookup]: metadata is incomplete, no productive peers exist, and the DHT routing table is empty "
                                "(connected=%d, productive=%d, routing_table_size=%d): %s",
                                connected_peers,
                                productive_peers,
                                routing_table_size,
                                self.s.info.name,
                            )
                    if active_block_requests > 0:
                        stall_marker = (
                            connected_peers,
                            productive_peers,
                            requestable_peers,
                            peers_with_piece_info,
                            active_block_requests,
                            hash_verification_failures,
                        )
                        if getattr(self.s, "_last_stall_marker", None) != stall_marker:
                            vars(self.s)["_last_stall_marker"] = stall_marker
                            self.s.logger.warning(
                                "STALL_MARKER[requests_outstanding_no_productive_peers]: downloading with outstanding requests but zero productive peers "
                                "(connected=%d, requestable=%d, piece_info=%d, active_requests=%d, hash_failures=%d): %s",
                                connected_peers,
                                requestable_peers,
                                peers_with_piece_info,
                                active_block_requests,
                                hash_verification_failures,
                                self.s.info.name,
                            )
                    request_resume = (
                        getattr(peer_manager, "request_pending_resume", None)
                        if peer_manager is not None
                        else None
                    )
                    if callable(request_resume):
                        with contextlib.suppress(Exception):
                            request_resume(reason="status_loop_stall")

                with contextlib.suppress(Exception):
                    self.s._touch_swarm_usefulness_latency_metrics(  # noqa: SLF001
                        int(requestable_peers or 0),
                        int(productive_peers or 0),
                    )

                # Update cached status (canonical keys; preserve byte counters)
                # Use setattr to avoid SLF001 for internal cache
                cached_status = {
                    "downloaded": status.get("downloaded", 0),
                    "uploaded": status.get("uploaded", 0),
                    "left": status.get("left", 0),
                    "connected_peers": connected_peers,
                    "productive_peers": productive_peers,
                    "requestable_peers": requestable_peers,
                    "remote_choked_peers": remote_choked_peers,
                    "pipeline_saturated_peers": pipeline_saturated_peers,
                    "handshake_complete_peers": handshake_complete_peers,
                    "extension_capable_peers": extension_capable_peers,
                    "metadata_capable_peers": metadata_capable_peers,
                    "peers_with_piece_info": peers_with_piece_info,
                    "download_rate": download_rate,
                    "upload_rate": upload_rate,
                    "progress": progress,
                    "download_complete": download_complete,
                    "tracker_resolution_anomalies": tracker_anomalies,
                }
                self.s._cached_status = cached_status  # noqa: SLF001

                # Note: Safety check - if download is complete but files aren't finalized
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
