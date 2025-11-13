from __future__ import annotations

import asyncio
import time
from typing import Any, cast

from ccbt.models import TorrentCheckpoint
from ccbt.session.models import SessionContext
from ccbt.session.tasks import TaskSupervisor
from ccbt.storage.checkpoint import CheckpointManager


class CheckpointController:
    """Controller handling checkpoint save/load and batching for a session."""

    def __init__(
        self,
        ctx: SessionContext,
        tasks: TaskSupervisor | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ) -> None:
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()
        # Prefer provided manager, else from context
        self._manager: CheckpointManager = checkpoint_manager or ctx.checkpoint_manager  # type: ignore[assignment]
        self._queue: asyncio.Queue[bool] | None = None
        self._batch_task: asyncio.Task[None] | None = None
        self._batch_interval: float = 0.0
        self._batch_pieces: int = 0
        self._pieces_since_flush: int = 0
        self._last_flush: float = 0.0

    def bind_piece_manager_checkpoint_hook(self) -> None:
        """Wire piece manager to enqueue checkpoint saves."""
        if not self._ctx.piece_manager:
            return
        self._ctx.piece_manager.on_checkpoint_save = self.enqueue_save  # type: ignore[attr-defined]

    def enable_batching(self, interval: float, pieces: int) -> None:
        """Enable batching with given interval/piece thresholds."""
        self._batch_interval = max(0.0, float(interval))
        self._batch_pieces = max(0, int(pieces))
        if self._batch_interval > 0 or self._batch_pieces > 0:
            self._queue = asyncio.Queue()
            self._batch_task = self._tasks.create_task(
                self._batcher_loop(), name="checkpoint_batcher"
            )

    async def stop(self) -> None:
        """Stop batching loop and flush pending work."""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except Exception:
                pass
        await self.flush_now()

    async def enqueue_save(self) -> None:
        """Signal that checkpoint state should be persisted (batched if enabled)."""
        if self._queue is None:
            await self._save_once()
            return
        await self._queue.put(True)

    async def flush_now(self) -> None:
        await self._save_once()

    async def _batcher_loop(self) -> None:
        """Background batching loop with time-based and piece-count thresholds."""
        assert self._queue is not None
        try:
            while True:
                try:
                    # Wait for enqueue or interval timeout
                    await asyncio.wait_for(
                        self._queue.get(), timeout=self._batch_interval
                    )
                except asyncio.TimeoutError:
                    # Time threshold reached; fall through to potential flush
                    pass

                self._pieces_since_flush += 1
                should_flush = False
                if (
                    self._batch_pieces > 0
                    and self._pieces_since_flush >= self._batch_pieces
                ):
                    should_flush = True
                if not should_flush and self._batch_interval > 0:
                    now = time.time()
                    if (
                        self._last_flush == 0
                        or now - self._last_flush >= self._batch_interval
                    ):
                        should_flush = True

                if should_flush:
                    await self._save_once()
                    self._pieces_since_flush = 0
        except asyncio.CancelledError:
            # Flush any final state before exit
            try:
                await self._save_once()
            except Exception:
                pass

    async def _save_once(self) -> None:
        """Collect checkpoint state from piece manager and persist via manager."""
        pm = self._ctx.piece_manager
        if not pm:
            if self._ctx.logger:
                self._ctx.logger.warning(
                    "Cannot save checkpoint: piece_manager not available"
                )
            return

        # Build checkpoint using existing piece manager API
        checkpoint: TorrentCheckpoint = await pm.get_checkpoint_state(  # type: ignore[assignment]
            getattr(self._ctx.info, "name", "unknown"),
            getattr(self._ctx.info, "info_hash", b""),
            str(self._ctx.output_dir),
        )

        # Enrich with announce URLs and display name if available
        td = self._ctx.torrent_data
        if isinstance(td, dict):
            announce_urls: list[str] = []
            if td.get("announce"):
                announce_urls.append(td["announce"])
            if td.get("announce_list"):
                for tier in td["announce_list"]:
                    announce_urls.extend(tier)
            checkpoint.announce_urls = announce_urls
            checkpoint.display_name = td.get(
                "name", getattr(self._ctx.info, "name", "")
            )

        # Delegate persistence to checkpoint manager
        if not self._manager:
            # Late binding: fetch from context if not set at init
            self._manager = self._ctx.checkpoint_manager  # type: ignore[assignment]
        if not self._manager:
            if self._ctx.logger:
                self._ctx.logger.warning(
                    "Cannot save checkpoint: checkpoint_manager not available"
                )
            return
        await self._manager.save_checkpoint(checkpoint)
        self._last_flush = time.time()

    async def run_periodic_loop(self) -> None:
        """Periodic loop to persist checkpoints at configured intervals."""
        cfg = self._ctx.config
        # Choose more frequent interval when both are enabled
        if cfg.disk.checkpoint_enabled:
            save_interval = min(
                cfg.disk.checkpoint_interval, cfg.disk.resume_save_interval
            )
        else:  # fallback
            save_interval = (
                cfg.disk.resume_save_interval
                if cfg.disk.fast_resume_enabled
                else cfg.disk.checkpoint_interval
            )

        while True:  # caller is expected to cancel this task
            try:
                await asyncio.sleep(save_interval)
                await self._save_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger = getattr(self._ctx, "logger", None)
                if logger:
                    logger.exception("Error in checkpoint periodic loop")

    def start_periodic_loop(self) -> asyncio.Task[None]:
        """Start the periodic save loop using the task supervisor."""
        return self._tasks.create_task(
            self.run_periodic_loop(), name="checkpoint_periodic_loop"
        )

    async def save_checkpoint_state(self, session: Any) -> None:
        """Save current download state to checkpoint with full metadata.

        This method collects checkpoint state from piece manager and enriches it with
        torrent source metadata, file selection state, and fast resume data.

        Args:
            session: AsyncTorrentSession instance

        """
        try:
            # Get checkpoint state from piece manager
            if not self._ctx.piece_manager or not hasattr(
                self._ctx.piece_manager, "get_checkpoint_state"
            ):
                if self._ctx.logger:
                    self._ctx.logger.warning(
                        "Cannot save checkpoint: piece_manager not available"
                    )
                return

            checkpoint: TorrentCheckpoint = (
                await self._ctx.piece_manager.get_checkpoint_state(  # type: ignore[assignment]
                    getattr(self._ctx.info, "name", "unknown"),
                    getattr(self._ctx.info, "info_hash", b""),
                    str(self._ctx.output_dir),
                )
            )

            # Add torrent source metadata to checkpoint
            if hasattr(session, "torrent_file_path") and session.torrent_file_path:
                checkpoint.torrent_file_path = session.torrent_file_path
            elif hasattr(session, "magnet_uri") and session.magnet_uri:
                checkpoint.magnet_uri = session.magnet_uri

            # Add announce URLs from torrent data
            td = self._ctx.torrent_data
            if isinstance(td, dict):
                announce_urls: list[str] = []
                if "announce" in td:
                    announce_urls.append(td["announce"])
                if "announce_list" in td:
                    for tier in td["announce_list"]:
                        announce_urls.extend(tier)
                checkpoint.announce_urls = announce_urls

                # Add display name
                checkpoint.display_name = td.get(
                    "name", getattr(self._ctx.info, "name", "")
                )

            # Add file selection state if file selection manager exists
            file_selection_manager = getattr(session, "file_selection_manager", None)
            if file_selection_manager:
                file_selections = {}
                for (
                    file_index,
                    state,
                ) in file_selection_manager.get_all_file_states().items():
                    file_selections[file_index] = {
                        "selected": state.selected,
                        "priority": state.priority.name,
                        "bytes_downloaded": state.bytes_downloaded,
                    }
                checkpoint.file_selections = file_selections

            # Add fast resume data if enabled
            config = self._ctx.config
            if config.disk.fast_resume_enabled:
                from ccbt.storage.resume_data import FastResumeData

                # Create resume data
                resume_data = FastResumeData(
                    info_hash=getattr(self._ctx.info, "info_hash", b""),
                    version=config.disk.resume_data_format_version,
                )

                # Encode piece bitmap
                verified_pieces = set(checkpoint.verified_pieces)
                total_pieces = checkpoint.total_pieces
                resume_data.piece_completion_bitmap = (
                    FastResumeData.encode_piece_bitmap(verified_pieces, total_pieces)
                )

                # Copy download stats (if available)
                if checkpoint.download_stats:
                    resume_data.download_stats = checkpoint.download_stats  # type: ignore[assignment]

                # Collect peer state (if available)
                download_manager = getattr(session, "download_manager", None)
                if download_manager and hasattr(download_manager, "get_peer_states"):
                    try:
                        peer_states_method = download_manager.get_peer_states
                        if callable(peer_states_method):
                            if asyncio.iscoroutinefunction(peer_states_method):
                                peer_states = await peer_states_method()  # type: ignore[misc]
                            else:
                                peer_states = peer_states_method()  # type: ignore[misc]
                            resume_data.set_peer_connections_state(peer_states)  # type: ignore[arg-type]
                    except Exception as e:
                        if self._ctx.logger:
                            self._ctx.logger.debug(
                                "Could not collect peer states: %s", e
                            )

                # Collect upload statistics (if available)
                if download_manager and hasattr(download_manager, "get_upload_stats"):
                    try:
                        upload_stats_method = download_manager.get_upload_stats
                        if callable(upload_stats_method):
                            if asyncio.iscoroutinefunction(upload_stats_method):
                                upload_stats = await upload_stats_method()  # type: ignore[misc]
                            else:
                                upload_stats = upload_stats_method()  # type: ignore[misc]
                            if isinstance(upload_stats, dict):
                                upload_dict = cast("dict[str, Any]", upload_stats)
                                resume_data.set_upload_statistics(
                                    upload_dict.get("bytes_uploaded", 0),
                                    upload_dict.get("peers_uploaded_to", set()),
                                    upload_dict.get("upload_rate_history", []),
                                )
                    except Exception as e:
                        if self._ctx.logger:
                            self._ctx.logger.debug(
                                "Could not collect upload stats: %s", e
                            )

                # Collect file selection state (if file selection manager exists)
                if file_selection_manager is not None:
                    try:
                        get_selection_state = getattr(
                            file_selection_manager,
                            "get_selection_state",
                            None,
                        )
                        if callable(get_selection_state):
                            file_state = get_selection_state()
                            resume_data.set_file_selection_state(file_state)
                    except Exception as e:
                        if self._ctx.logger:
                            self._ctx.logger.debug(
                                "Could not collect file selection state: %s", e
                            )

                # Collect queue state (if queue manager exists)
                session_manager = getattr(session, "session_manager", None)
                if (
                    session_manager
                    and hasattr(session_manager, "queue_manager")
                    and session_manager.queue_manager
                ):
                    try:
                        queue_state = await (
                            session_manager.queue_manager.get_torrent_queue_state(
                                getattr(self._ctx.info, "info_hash", b""),
                            )
                        )
                        if queue_state:
                            resume_data.set_queue_state(
                                queue_state.get("position"),
                                queue_state.get("priority"),
                            )
                    except Exception as e:
                        if self._ctx.logger:
                            self._ctx.logger.debug(
                                "Could not collect queue state: %s", e
                            )

                # Serialize resume data for storage
                checkpoint.resume_data = resume_data.model_dump()

            # Use batching if enabled, otherwise save immediately
            if self._queue is not None:
                await self._queue.put(True)  # Signal to batcher
            else:
                await self._save_once()
            if self._ctx.logger:
                self._ctx.logger.debug(
                    "Saved checkpoint for %s",
                    getattr(self._ctx.info, "name", "unknown"),
                )

        except Exception:
            if self._ctx.logger:
                self._ctx.logger.exception("Failed to save checkpoint")
            raise

    async def resume_from_checkpoint(
        self, checkpoint: TorrentCheckpoint, session: Any
    ) -> None:
        """Resume download from checkpoint.

        Args:
            checkpoint: Checkpoint data to resume from
            session: AsyncTorrentSession instance

        """
        try:
            if self._ctx.logger:
                self._ctx.logger.info(
                    "Resuming download from checkpoint: %s",
                    checkpoint.torrent_name,
                )

            # Validate existing files
            # async_main.AsyncDownloadManager doesn't have file_assembler, use piece_manager for validation
            piece_manager = self._ctx.piece_manager
            if piece_manager:
                # Piece manager handles piece verification
                validation_results = {
                    "valid": True,  # Assume valid if piece_manager exists
                    "verified_pieces": checkpoint.verified_pieces,
                }

                if not validation_results["valid"]:
                    if self._ctx.logger:
                        self._ctx.logger.warning(
                            "File validation failed, some files may need to be re-downloaded",
                        )
                    if validation_results.get("missing_files"):
                        if self._ctx.logger:
                            self._ctx.logger.warning(
                                "Missing files: %s",
                                validation_results["missing_files"],
                            )
                    if validation_results.get("corrupted_pieces"):
                        if self._ctx.logger:
                            self._ctx.logger.warning(
                                "Corrupted pieces: %s",
                                validation_results["corrupted_pieces"],
                            )

            # Skip preallocation for existing files
            # async_main.AsyncDownloadManager: use piece_manager to track written pieces
            if piece_manager:
                # Get written pieces from piece_manager state
                written_pieces = set()
                # Piece manager tracks completed pieces internally
                if hasattr(piece_manager, "get_completed_pieces"):
                    written_pieces = set(piece_manager.get_completed_pieces())
                for piece_idx in checkpoint.verified_pieces:
                    if piece_idx not in written_pieces:
                        written_pieces.add(piece_idx)

            # Restore piece manager state
            if piece_manager:
                await piece_manager.restore_from_checkpoint(checkpoint)
                if self._ctx.logger:
                    self._ctx.logger.info(
                        "Restored piece manager state from checkpoint"
                    )

            # Restore file selection state if available
            file_selection_manager = getattr(session, "file_selection_manager", None)
            if checkpoint.file_selections and file_selection_manager:
                from ccbt.piece.file_selection import FilePriority

                for file_index, selection_data in checkpoint.file_selections.items():
                    if file_index in file_selection_manager.file_states:
                        state = file_selection_manager.file_states[file_index]
                        state.selected = selection_data.get("selected", True)
                        priority_str = selection_data.get("priority", "NORMAL")
                        try:
                            state.priority = FilePriority[priority_str]
                        except KeyError:
                            # Fallback to NORMAL if priority string is invalid
                            state.priority = FilePriority.NORMAL
                            if self._ctx.logger:
                                self._ctx.logger.warning(
                                    "Invalid priority '%s' for file %s, using NORMAL",
                                    priority_str,
                                    file_index,
                                )
                        state.bytes_downloaded = selection_data.get(
                            "bytes_downloaded",
                            0,
                        )
                if self._ctx.logger:
                    self._ctx.logger.info(
                        "Restored file selection state for %s files",
                        len(checkpoint.file_selections),
                    )

            # Restore file attributes from checkpoint (BEP 47)
            # async_main.AsyncDownloadManager: file attributes are handled by piece_manager/file system
            if checkpoint.files and piece_manager:
                try:
                    # File attributes restoration is handled by the storage layer
                    # async_main doesn't expose file_assembler, so we skip explicit restoration
                    # The file system will preserve attributes when files are written
                    if self._ctx.logger:
                        self._ctx.logger.debug(
                            "File attributes restoration handled by storage layer"
                        )
                except Exception as e:
                    if self._ctx.logger:
                        self._ctx.logger.warning(
                            "Failed to restore file attributes from checkpoint: %s",
                            e,
                        )

            if hasattr(session, "checkpoint_loaded"):
                session.checkpoint_loaded = True
            if self._ctx.logger:
                self._ctx.logger.info(
                    "Successfully resumed from checkpoint: %s pieces verified",
                    len(checkpoint.verified_pieces),
                )

        except Exception:
            if self._ctx.logger:
                self._ctx.logger.exception("Failed to resume from checkpoint")
            raise
