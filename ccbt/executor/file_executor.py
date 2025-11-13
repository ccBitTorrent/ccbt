"""File command executor.

Handles file selection and prioritization commands.
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class FileExecutor(CommandExecutor):
    """Executor for file commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute file command.

        Args:
            command: Command name (e.g., "file.list", "file.select")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "file.list":
            return await self._get_torrent_files(**kwargs)
        if command == "file.select":
            return await self._select_files(**kwargs)
        if command == "file.deselect":
            return await self._deselect_files(**kwargs)
        if command == "file.priority":
            return await self._set_file_priority(**kwargs)
        if command == "file.verify":
            return await self._verify_files(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown file command: {command}",
        )

    async def _get_torrent_files(self, info_hash: str) -> CommandResult:
        """Get file list for a torrent."""
        try:
            file_list = await self.adapter.get_torrent_files(info_hash)
            return CommandResult(success=True, data={"files": file_list})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _select_files(
        self,
        info_hash: str,
        file_indices: list[int],
    ) -> CommandResult:
        """Select files for download."""
        try:
            result = await self.adapter.select_files(info_hash, file_indices)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _deselect_files(
        self,
        info_hash: str,
        file_indices: list[int],
    ) -> CommandResult:
        """Deselect files."""
        try:
            result = await self.adapter.deselect_files(info_hash, file_indices)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _set_file_priority(
        self,
        info_hash: str,
        file_index: int,
        priority: str,
    ) -> CommandResult:
        """Set file priority."""
        try:
            result = await self.adapter.set_file_priority(
                info_hash,
                file_index,
                priority,
            )
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _verify_files(self, info_hash: str) -> CommandResult:
        """Verify torrent files."""
        try:
            result = await self.adapter.verify_files(info_hash)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
