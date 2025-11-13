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
        if command == "torrent.export_session_state":
            return await self._export_session_state(**kwargs)
        if command == "torrent.import_session_state":
            return await self._import_session_state(**kwargs)
        if command == "torrent.resume_from_checkpoint":
            return await self._resume_from_checkpoint(**kwargs)
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
            return CommandResult(success=success, data={"paused": success})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _resume_torrent(self, info_hash: str) -> CommandResult:
        """Resume torrent."""
        try:
            success = await self.adapter.resume_torrent(info_hash)
            return CommandResult(success=success, data={"resumed": success})
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
