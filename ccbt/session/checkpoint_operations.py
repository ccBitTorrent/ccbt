"""Checkpoint operations for session manager."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ccbt.models import PieceState, TorrentCheckpoint
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.utils.exceptions import ValidationError

# Constants
INFO_HASH_LENGTH = 20  # SHA-1 hash length in bytes


class CheckpointOperations:
    """Operations for managing checkpoints at the session manager level."""

    def __init__(self, manager: Any) -> None:
        """Initialize checkpoint operations.

        Args:
            manager: AsyncSessionManager instance

        """
        self.manager = manager
        self.config = manager.config
        self.logger = manager.logger

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: TorrentCheckpoint,
        torrent_path: Optional[str] = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            ValueError: If torrent source cannot be determined
            FileNotFoundError: If torrent file doesn't exist
            ValidationError: If checkpoint is invalid

        """
        try:
            # Validate checkpoint
            if not await self.validate(checkpoint):
                error_msg = "Invalid checkpoint data"
                raise ValidationError(error_msg)

            # Priority order: explicit path -> stored file path -> magnet URI
            torrent_source = None
            source_type = None

            if torrent_path and Path(torrent_path).exists():
                torrent_source = torrent_path
                source_type = "file"
                self.logger.info("Using explicit torrent file: %s", torrent_path)
            elif (
                checkpoint.torrent_file_path
                and Path(checkpoint.torrent_file_path).exists()
            ):
                torrent_source = checkpoint.torrent_file_path
                source_type = "file"
                self.logger.info(
                    "Using stored torrent file: %s",
                    checkpoint.torrent_file_path,
                )
            elif checkpoint.magnet_uri:
                torrent_source = checkpoint.magnet_uri
                source_type = "magnet"
                self.logger.info("Using stored magnet URI: %s", checkpoint.magnet_uri)
            else:
                error_msg = (
                    f"Cannot resume torrent {info_hash.hex()}: "
                    "No valid torrent source found in checkpoint. "
                    "Please provide torrent file or magnet link."
                )
                raise ValueError(error_msg)

            # Validate info hash matches if using explicit torrent file
            if source_type == "file" and torrent_source:
                from ccbt.session import session as session_module

                parser = session_module.TorrentParser()
                torrent_data_model = parser.parse(torrent_source)
                if isinstance(torrent_data_model, dict):
                    torrent_info_hash = torrent_data_model.get("info_hash")
                else:
                    torrent_info_hash = getattr(torrent_data_model, "info_hash", None)
                torrent_data = {
                    "info_hash": torrent_info_hash,
                }
                if torrent_data["info_hash"] != info_hash:
                    torrent_hash_hex = (
                        torrent_data["info_hash"].hex()
                        if torrent_data["info_hash"] is not None
                        else "None"
                    )
                    error_msg = (
                        f"Info hash mismatch: checkpoint is for {info_hash.hex()}, "
                        f"but torrent file is for {torrent_hash_hex}"
                    )
                    raise ValueError(error_msg)

            # Add torrent/magnet with resume=True
            if source_type == "file":
                return await self.manager.add_torrent(torrent_source, resume=True)
            return await self.manager.add_magnet(torrent_source, resume=True)

        except Exception:
            self.logger.exception("Failed to resume from checkpoint")
            raise

    async def list_resumable(self) -> list[TorrentCheckpoint]:
        """List all checkpoints that can be auto-resumed."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        resumable = []
        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and (
                    checkpoint.torrent_file_path or checkpoint.magnet_uri
                ):
                    resumable.append(checkpoint)
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return resumable

    async def find_by_name(self, name: str) -> Optional[TorrentCheckpoint]:
        """Find checkpoint by torrent name."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and checkpoint.torrent_name == name:
                    return checkpoint
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return None

    async def get_info(self, info_hash: bytes) -> Optional[dict[str, Any]]:
        """Get checkpoint summary information."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        if not checkpoint:
            return None

        return {
            "info_hash": info_hash.hex(),
            "name": checkpoint.torrent_name,
            "progress": len(checkpoint.verified_pieces) / checkpoint.total_pieces
            if checkpoint.total_pieces > 0
            else 0,
            "verified_pieces": len(checkpoint.verified_pieces),
            "total_pieces": checkpoint.total_pieces,
            "total_size": checkpoint.total_length,
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
            "can_resume": bool(checkpoint.torrent_file_path or checkpoint.magnet_uri),
            "torrent_file_path": checkpoint.torrent_file_path,
            "magnet_uri": checkpoint.magnet_uri,
        }

    async def validate(self, checkpoint: TorrentCheckpoint) -> bool:
        """Validate checkpoint integrity."""
        try:
            # Basic validation
            if (
                not checkpoint.info_hash
                or len(checkpoint.info_hash) != INFO_HASH_LENGTH
            ):
                return False

            if checkpoint.total_pieces <= 0 or checkpoint.piece_length <= 0:
                return False

            if checkpoint.total_length <= 0:
                return False

            # Validate verified pieces are within bounds
            for piece_idx in checkpoint.verified_pieces:
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False

            # Validate piece states
            for piece_idx, state in checkpoint.piece_states.items():
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False
                if not isinstance(state, PieceState):
                    return False

        except Exception:
            return False
        else:
            return True

    async def cleanup_completed(self) -> int:
        """Remove checkpoints for completed downloads."""
        # Note: Use checkpoint manager from session manager instead of creating new instance
        # This allows tests to properly mock the checkpoint manager
        checkpoint_manager = getattr(self.manager, "checkpoint_manager", None)
        if not checkpoint_manager:
            checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        cleaned = 0

        async def process_checkpoint(checkpoint_info):
            """Process a single checkpoint."""
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if (
                    checkpoint
                    and len(checkpoint.verified_pieces) == checkpoint.total_pieces
                ):
                    # Download is complete, delete checkpoint
                    await checkpoint_manager.delete_checkpoint(
                        checkpoint_info.info_hash,
                    )
                    self.logger.info(
                        "Cleaned up completed checkpoint: %s",
                        checkpoint.torrent_name,
                    )
                    return True
            except Exception as e:
                self.logger.warning(
                    "Failed to process checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
            return False

        for checkpoint_info in checkpoints:
            if await process_checkpoint(checkpoint_info):
                cleaned += 1

        return cleaned

    async def refresh_checkpoint(
        self,
        info_hash: bytes,
        reload_peers: bool = True,
        reload_trackers: bool = True,
    ) -> bool:
        """Reload checkpoint and refresh session state without full restart.

        Args:
            info_hash: Torrent info hash
            reload_peers: Whether to reconnect to peers from checkpoint
            reload_trackers: Whether to refresh tracker state

        Returns:
            True if refresh successful, False otherwise

        """
        try:
            # Load checkpoint
            checkpoint_manager = CheckpointManager(self.config.disk)
            checkpoint = await checkpoint_manager.load_checkpoint(info_hash)
            if not checkpoint:
                self.logger.warning("No checkpoint found for %s", info_hash.hex()[:8])
                return False

            # Get session
            session = self.manager.torrents.get(info_hash)
            if not session:
                self.logger.warning(
                    "No active session found for %s", info_hash.hex()[:8]
                )
                return False

            # Refresh session state from checkpoint
            if (
                hasattr(session, "checkpoint_controller")
                and session.checkpoint_controller
            ):
                # Use checkpoint controller to restore state
                await session.checkpoint_controller.resume_from_checkpoint(
                    checkpoint, session
                )

                # Optionally reconnect peers
                if reload_peers and checkpoint.connected_peers:
                    download_manager = getattr(session, "download_manager", None)
                    if download_manager:
                        peer_manager = getattr(download_manager, "peer_manager", None)
                        if peer_manager and hasattr(peer_manager, "connect_to_peers"):
                            peer_list = [
                                {
                                    "ip": peer_data.get("ip"),
                                    "port": peer_data.get("port"),
                                    "peer_source": peer_data.get(
                                        "peer_source", "checkpoint"
                                    ),
                                }
                                for peer_data in checkpoint.connected_peers
                            ]
                            if peer_list:
                                submit = await peer_manager.connect_to_peers(peer_list)
                                if (
                                    getattr(submit, "status", None)
                                    == "queued_reentrant"
                                ):
                                    self.logger.info(
                                        "Checkpoint refresh queued %d peers "
                                        "(queue_depth=%s)",
                                        len(peer_list),
                                        getattr(submit, "queue_depth_after", None),
                                    )
                                else:
                                    self.logger.info(
                                        "Refreshed %d peers from checkpoint",
                                        len(peer_list),
                                    )

                # Optionally refresh trackers
                if reload_trackers and checkpoint.tracker_health:
                    # Tracker state is restored by checkpoint controller
                    self.logger.info("Refreshed tracker state from checkpoint")

                self.logger.info(
                    "Successfully refreshed checkpoint for %s",
                    checkpoint.torrent_name,
                )
                return True
            self.logger.warning("Session has no checkpoint controller for refresh")
            return False

        except Exception:
            self.logger.exception("Failed to refresh checkpoint")
            return False

    async def quick_reload(
        self,
        info_hash: bytes,
    ) -> bool:
        """Quick reload checkpoint using incremental checkpointing.

        Args:
            info_hash: Torrent info hash

        Returns:
            True if reload successful, False otherwise

        """
        try:
            checkpoint_manager = CheckpointManager(self.config.disk)

            # Load current checkpoint as base
            base_checkpoint = await checkpoint_manager.load_checkpoint(info_hash)
            if not base_checkpoint:
                self.logger.warning(
                    "No checkpoint found for quick reload: %s", info_hash.hex()[:8]
                )
                return False

            # Load incremental checkpoint (if exists, otherwise use full)
            checkpoint = await checkpoint_manager.load_incremental_checkpoint(  # type: ignore[attr-defined]
                info_hash, base_checkpoint
            )
            if not checkpoint:
                checkpoint = base_checkpoint

            # Get session
            session = self.manager.torrents.get(info_hash)
            if not session:
                self.logger.warning(
                    "No active session found for quick reload: %s",
                    info_hash.hex()[:8],
                )
                return False

            # Quick reload: only restore critical state (peers, trackers)
            if (
                hasattr(session, "checkpoint_controller")
                and session.checkpoint_controller
            ):
                # Restore only peer and tracker lists (skip piece verification)
                if checkpoint.connected_peers:
                    download_manager = getattr(session, "download_manager", None)
                    if download_manager:
                        peer_manager = getattr(download_manager, "peer_manager", None)
                        if peer_manager and hasattr(peer_manager, "connect_to_peers"):
                            peer_list = [
                                {
                                    "ip": peer_data.get("ip"),
                                    "port": peer_data.get("port"),
                                    "peer_source": peer_data.get(
                                        "peer_source", "checkpoint"
                                    ),
                                }
                                for peer_data in checkpoint.connected_peers
                            ]
                            if peer_list:
                                submit = await peer_manager.connect_to_peers(peer_list)
                                if (
                                    getattr(submit, "status", None)
                                    == "queued_reentrant"
                                ):
                                    self.logger.debug(
                                        "Quick reload queued %d peers (queue_depth=%s)",
                                        len(peer_list),
                                        getattr(submit, "queue_depth_after", None),
                                    )

                # Restore tracker state
                restore_method = getattr(
                    session.checkpoint_controller, "_restore_tracker_lists", None
                )
                if restore_method:
                    await restore_method(checkpoint, session)

                self.logger.info(
                    "Quick reload completed for %s", checkpoint.torrent_name
                )
                return True
            self.logger.warning("Session has no checkpoint controller for quick reload")
            return False

        except Exception:
            self.logger.exception("Failed to quick reload checkpoint")
            return False
