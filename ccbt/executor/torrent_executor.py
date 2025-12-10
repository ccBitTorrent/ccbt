"""Torrent command executor.

Handles torrent-related commands (add, remove, list, status, pause, resume).
"""

from __future__ import annotations

import asyncio
from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class TorrentExecutor(CommandExecutor):
    """Executor for torrent commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute torrent command.

        Args:
            command: Command name (e.g., "torrent.add", "torrent.list")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "torrent.add":
            return await self._add_torrent(**kwargs)
        if command == "torrent.remove":
            return await self._remove_torrent(**kwargs)
        if command == "torrent.list":
            return await self._list_torrents()
        if command == "torrent.status":
            return await self._get_torrent_status(**kwargs)
        if command == "torrent.pause":
            return await self._pause_torrent(**kwargs)
        if command == "torrent.resume":
            return await self._resume_torrent(**kwargs)
        if command == "torrent.get_peers":
            return await self._get_peers_for_torrent(**kwargs)
        if command == "torrent.set_rate_limits":
            return await self._set_rate_limits(**kwargs)
        if command == "torrent.force_announce":
            return await self._force_announce(**kwargs)
        if command == "torrent.refresh_pex":
            return await self._refresh_pex(**kwargs)
        if command == "torrent.rehash":
            return await self._rehash_torrent(**kwargs)
        if command == "torrent.export_session_state":
            return await self._export_session_state(**kwargs)
        if command == "torrent.import_session_state":
            return await self._import_session_state(**kwargs)
        if command == "torrent.resume_from_checkpoint":
            return await self._resume_from_checkpoint(**kwargs)
        if command == "torrent.add_tracker":
            return await self._add_tracker(**kwargs)
        if command == "torrent.remove_tracker":
            return await self._remove_tracker(**kwargs)
        if command == "torrent.restart":
            return await self._restart_torrent(**kwargs)
        if command == "torrent.cancel":
            return await self._cancel_torrent(**kwargs)
        if command == "torrent.force_start":
            return await self._force_start_torrent(**kwargs)
        if command == "torrent.get_metadata_status":
            return await self._get_metadata_status(**kwargs)
        # Batch operations
        if command == "torrent.batch_pause":
            return await self._batch_pause_torrents(**kwargs)
        if command == "torrent.batch_resume":
            return await self._batch_resume_torrents(**kwargs)
        if command == "torrent.batch_restart":
            return await self._batch_restart_torrents(**kwargs)
        if command == "torrent.batch_remove":
            return await self._batch_remove_torrents(**kwargs)
        # Global operations
        if command == "torrent.global_pause_all":
            return await self._global_pause_all(**kwargs)
        if command == "torrent.global_resume_all":
            return await self._global_resume_all(**kwargs)
        if command == "torrent.global_force_start_all":
            return await self._global_force_start_all(**kwargs)
        if command == "torrent.global_set_rate_limits":
            return await self._global_set_rate_limits(**kwargs)
        # Per-peer operations
        if command == "peer.set_rate_limit":
            return await self._set_per_peer_rate_limit(**kwargs)
        if command == "peer.get_rate_limit":
            return await self._get_per_peer_rate_limit(**kwargs)
        if command == "peer.set_all_rate_limits":
            return await self._set_all_peers_rate_limit(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown torrent command: {command}",
        )

    async def _add_torrent(
        self,
        path_or_magnet: str,
        output_dir: str | None = None,
        resume: bool = False,
    ) -> CommandResult:
        """Add torrent or magnet."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            # CRITICAL FIX: Wrap adapter call in try-except to prevent daemon crashes
            # Align timeout with IPC server timeout (120s for magnets, 60s for torrents)
            # This prevents conflicts between executor and IPC server timeouts
            try:
                timeout_seconds = (
                    120.0 if path_or_magnet.startswith("magnet:") else 60.0
                )
                info_hash = await asyncio.wait_for(
                    self.adapter.add_torrent(
                        path_or_magnet,
                        output_dir=output_dir,
                        resume=resume,
                    ),
                    timeout=timeout_seconds,
                )
                return CommandResult(success=True, data={"info_hash": info_hash})
            except asyncio.TimeoutError:
                timeout_seconds = (
                    120.0 if path_or_magnet.startswith("magnet:") else 60.0
                )
                logger.error(
                    "Timeout adding torrent/magnet '%s' (operation took >%.0fs)",
                    path_or_magnet[:100]
                    if len(path_or_magnet) > 100
                    else path_or_magnet,
                    timeout_seconds,
                )
                return CommandResult(
                    success=False,
                    error=f"Operation timed out after {timeout_seconds:.0f}s - torrent may still be processing in background",
                )
            except Exception as adapter_error:
                # Log the exception with full traceback for debugging
                logger.error(
                    "Failed to add torrent/magnet '%s': %s",
                    path_or_magnet[:100]
                    if len(path_or_magnet) > 100
                    else path_or_magnet,
                    adapter_error,
                    exc_info=True,
                )
                # Preserve exception details in error message
                error_msg = str(adapter_error)
                if not error_msg:
                    error_msg = f"{type(adapter_error).__name__}: {adapter_error}"
                return CommandResult(success=False, error=error_msg)
        except Exception as e:
            # Catch any unexpected errors in the executor itself
            logger.exception(
                "Unexpected error in torrent executor _add_torrent: %s",
                e,
            )
            return CommandResult(
                success=False,
                error=f"Unexpected error: {e!s}",
            )

    async def _remove_torrent(self, info_hash: str) -> CommandResult:
        """Remove torrent."""
        try:
            success = await self.adapter.remove_torrent(info_hash)
            return CommandResult(success=success, data={"removed": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _list_torrents(self) -> CommandResult:
        """List all torrents."""
        try:
            torrents = await self.adapter.list_torrents()
            return CommandResult(success=True, data={"torrents": torrents})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_torrent_status(self, info_hash: str) -> CommandResult:
        """Get torrent status."""
        try:
            status = await self.adapter.get_torrent_status(info_hash)
            return CommandResult(success=True, data={"status": status})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _pause_torrent(self, info_hash: str) -> CommandResult:
        """Pause torrent."""
        try:
            success = await self.adapter.pause_torrent(info_hash)
            # Check if checkpoint was saved
            checkpoint_saved = False
            if success:
                # Try to verify checkpoint exists
                try:
                    from ccbt.storage.checkpoint import CheckpointManager
                    from ccbt.config.config import get_config

                    config = get_config()
                    checkpoint_manager = CheckpointManager(config.disk)
                    info_hash_bytes = bytes.fromhex(info_hash)
                    checkpoint = await checkpoint_manager.load_checkpoint(info_hash_bytes)
                    checkpoint_saved = checkpoint is not None
                except Exception:
                    pass  # Ignore checkpoint check errors

            return CommandResult(
                success=success,
                data={"paused": success, "checkpoint_saved": checkpoint_saved},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _resume_torrent(self, info_hash: str) -> CommandResult:
        """Resume torrent."""
        try:
            success = await self.adapter.resume_torrent(info_hash)
            # Check if checkpoint was restored
            checkpoint_restored = False
            checkpoint_not_found = False
            if success:
                try:
                    from ccbt.storage.checkpoint import CheckpointManager
                    from ccbt.config.config import get_config

                    config = get_config()
                    checkpoint_manager = CheckpointManager(config.disk)
                    info_hash_bytes = bytes.fromhex(info_hash)
                    checkpoint = await checkpoint_manager.load_checkpoint(info_hash_bytes)
                    if checkpoint:
                        checkpoint_restored = True
                    else:
                        checkpoint_not_found = True
                except Exception:
                    pass  # Ignore checkpoint check errors

            return CommandResult(
                success=success,
                data={
                    "resumed": success,
                    "checkpoint_restored": checkpoint_restored,
                    "checkpoint_not_found": checkpoint_not_found,
                },
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_peers_for_torrent(self, info_hash: str) -> CommandResult:
        """Get list of peers for a torrent."""
        try:
            peers = await self.adapter.get_peers_for_torrent(info_hash)
            return CommandResult(success=True, data={"peers": peers})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _set_rate_limits(
        self,
        info_hash: str,
        download_kib: int,
        upload_kib: int,
    ) -> CommandResult:
        """Set per-torrent rate limits."""
        try:
            success = await self.adapter.set_rate_limits(
                info_hash, download_kib, upload_kib
            )
            return CommandResult(success=success, data={"set": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _force_announce(self, info_hash: str) -> CommandResult:
        """Force a tracker announce for a torrent."""
        try:
            success = await self.adapter.force_announce(info_hash)
            return CommandResult(success=success, data={"announced": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _refresh_pex(self, info_hash: str) -> CommandResult:
        """Refresh PEX (Peer Exchange) for a torrent."""
        try:
            result = await self.adapter.refresh_pex(info_hash)
            return CommandResult(success=result.get("success", False), data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _rehash_torrent(self, info_hash: str) -> CommandResult:
        """Rehash all pieces for a torrent."""
        try:
            result = await self.adapter.rehash_torrent(info_hash)
            return CommandResult(success=result.get("success", False), data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _add_tracker(self, info_hash: str, tracker_url: str) -> CommandResult:
        """Add a tracker to a torrent."""
        try:
            result = await self.adapter.add_tracker(info_hash, tracker_url)
            return CommandResult(success=result.get("success", False), data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _remove_tracker(self, info_hash: str, tracker_url: str) -> CommandResult:
        """Remove a tracker from a torrent."""
        try:
            result = await self.adapter.remove_tracker(info_hash, tracker_url)
            return CommandResult(success=result.get("success", False), data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _export_session_state(self, path: str) -> CommandResult:
        """Export session state to a file."""
        try:
            await self.adapter.export_session_state(path)
            return CommandResult(success=True, data={"exported": True})
        except NotImplementedError as e:
            return CommandResult(success=False, error=str(e))
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _import_session_state(self, path: str) -> CommandResult:
        """Import session state from a file."""
        try:
            state = await self.adapter.import_session_state(path)
            return CommandResult(success=True, data={"state": state})
        except NotImplementedError as e:
            return CommandResult(success=False, error=str(e))
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> CommandResult:
        """Resume download from checkpoint."""
        try:
            info_hash_hex = await self.adapter.resume_from_checkpoint(
                info_hash,
                checkpoint,
                torrent_path=torrent_path,
            )
            return CommandResult(success=True, data={"info_hash": info_hash_hex})
        except NotImplementedError as e:
            return CommandResult(success=False, error=str(e))
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _restart_torrent(self, info_hash: str) -> CommandResult:
        """Restart torrent (pause + resume)."""
        try:
            # Pause first
            pause_result = await self._pause_torrent(info_hash)
            if not pause_result.success:
                return pause_result
            
            # Small delay
            await asyncio.sleep(0.1)
            
            # Resume
            resume_result = await self._resume_torrent(info_hash)
            if resume_result.success:
                return CommandResult(success=True, data={"restarted": True})
            return resume_result
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _cancel_torrent(self, info_hash: str) -> CommandResult:
        """Cancel torrent (pause but keep in session)."""
        try:
            success = await self.adapter.cancel_torrent(info_hash)
            # Check if checkpoint was saved
            checkpoint_saved = False
            if success:
                # Try to verify checkpoint exists
                try:
                    from ccbt.storage.checkpoint import CheckpointManager
                    from ccbt.config.config import get_config

                    config = get_config()
                    checkpoint_manager = CheckpointManager(config.disk)
                    info_hash_bytes = bytes.fromhex(info_hash)
                    checkpoint = await checkpoint_manager.load_checkpoint(info_hash_bytes)
                    checkpoint_saved = checkpoint is not None
                except Exception:
                    pass  # Ignore checkpoint check errors

            return CommandResult(
                success=success,
                data={"cancelled": success, "checkpoint_saved": checkpoint_saved},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _force_start_torrent(self, info_hash: str) -> CommandResult:
        """Force start torrent (bypass queue limits)."""
        try:
            success = await self.adapter.force_start_torrent(info_hash)
            return CommandResult(success=success, data={"force_started": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _global_pause_all(self) -> CommandResult:
        """Pause all torrents."""
        try:
            result = await self.adapter.global_pause_all()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _global_resume_all(self) -> CommandResult:
        """Resume all paused torrents."""
        try:
            result = await self.adapter.global_resume_all()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _global_force_start_all(self) -> CommandResult:
        """Force start all torrents."""
        try:
            result = await self.adapter.global_force_start_all()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _global_set_rate_limits(
        self, download_kib: int, upload_kib: int
    ) -> CommandResult:
        """Set global rate limits."""
        try:
            success = await self.adapter.global_set_rate_limits(download_kib, upload_kib)
            return CommandResult(success=success, data={"set": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _set_per_peer_rate_limit(
        self, info_hash: str, peer_key: str, upload_limit_kib: int
    ) -> CommandResult:
        """Set per-peer upload rate limit."""
        try:
            success = await self.adapter.set_per_peer_rate_limit(
                info_hash, peer_key, upload_limit_kib
            )
            return CommandResult(success=success, data={"set": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_per_peer_rate_limit(
        self, info_hash: str, peer_key: str
    ) -> CommandResult:
        """Get per-peer upload rate limit."""
        try:
            limit = await self.adapter.get_per_peer_rate_limit(info_hash, peer_key)
            if limit is None:
                return CommandResult(success=False, error="Peer or torrent not found")
            return CommandResult(success=True, data={"upload_limit_kib": limit})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _set_all_peers_rate_limit(
        self, upload_limit_kib: int
    ) -> CommandResult:
        """Set per-peer upload rate limit for all peers."""
        try:
            updated_count = await self.adapter.set_all_peers_rate_limit(upload_limit_kib)
            return CommandResult(
                success=True, data={"updated_count": updated_count, "upload_limit_kib": upload_limit_kib}
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_metadata_status(self, info_hash: str) -> CommandResult:
        """Get metadata fetch status for magnet link."""
        try:
            # Check if adapter has get_metadata_status method
            if hasattr(self.adapter, "get_metadata_status"):
                status = await self.adapter.get_metadata_status(info_hash)
                return CommandResult(success=True, data=status)
            
            # Fallback: Check if torrent has files (indicates metadata is ready)
            status = await self.adapter.get_torrent_status(info_hash)
            if status:
                files = await self.adapter.get_torrent_files(info_hash)
                metadata_available = files is not None and len(files) > 0
                return CommandResult(
                    success=True,
                    data={
                        "info_hash": info_hash,
                        "available": metadata_available,
                        "ready": metadata_available,
                    },
                )
            
            return CommandResult(
                success=False,
                error="Torrent not found",
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _batch_pause_torrents(
        self, info_hashes: list[str]
    ) -> CommandResult:
        """Pause multiple torrents."""
        try:
            # Check if adapter supports batch operations
            if hasattr(self.adapter, "batch_pause_torrents"):
                result = await self.adapter.batch_pause_torrents(info_hashes)
                return CommandResult(success=True, data=result)
            
            # Fallback: Execute individually
            results = []
            for info_hash in info_hashes:
                success = await self.adapter.pause_torrent(info_hash)
                results.append({"info_hash": info_hash, "success": success})
            return CommandResult(success=True, data={"results": results})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _batch_resume_torrents(
        self, info_hashes: list[str]
    ) -> CommandResult:
        """Resume multiple torrents."""
        try:
            # Check if adapter supports batch operations
            if hasattr(self.adapter, "batch_resume_torrents"):
                result = await self.adapter.batch_resume_torrents(info_hashes)
                return CommandResult(success=True, data=result)
            
            # Fallback: Execute individually
            results = []
            for info_hash in info_hashes:
                success = await self.adapter.resume_torrent(info_hash)
                results.append({"info_hash": info_hash, "success": success})
            return CommandResult(success=True, data={"results": results})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _batch_restart_torrents(
        self, info_hashes: list[str]
    ) -> CommandResult:
        """Restart multiple torrents."""
        try:
            # Check if adapter supports batch operations
            if hasattr(self.adapter, "batch_restart_torrents"):
                result = await self.adapter.batch_restart_torrents(info_hashes)
                return CommandResult(success=True, data=result)
            
            # Fallback: Execute individually
            results = []
            for info_hash in info_hashes:
                # Pause then resume
                pause_success = await self.adapter.pause_torrent(info_hash)
                await asyncio.sleep(0.1)
                resume_success = await self.adapter.resume_torrent(info_hash)
                results.append({
                    "info_hash": info_hash,
                    "success": pause_success and resume_success,
                })
            return CommandResult(success=True, data={"results": results})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _batch_remove_torrents(
        self, info_hashes: list[str], remove_data: bool = False
    ) -> CommandResult:
        """Remove multiple torrents."""
        try:
            # Check if adapter supports batch operations
            if hasattr(self.adapter, "batch_remove_torrents"):
                result = await self.adapter.batch_remove_torrents(
                    info_hashes, remove_data=remove_data
                )
                return CommandResult(success=True, data=result)
            
            # Fallback: Execute individually
            results = []
            for info_hash in info_hashes:
                success = await self.adapter.remove_torrent(info_hash)
                results.append({"info_hash": info_hash, "success": success})
            return CommandResult(success=True, data={"results": results})
        except Exception as e:
            return CommandResult(success=False, error=str(e))
