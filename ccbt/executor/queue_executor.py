"""Queue command executor.

Handles queue management commands.
"""

from __future__ import annotations

from ccbt.executor.base import CommandExecutor, CommandResult


class QueueExecutor(CommandExecutor):
    """Executor for queue commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute queue command.

        Args:
            command: Command name (e.g., "queue.list", "queue.add")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "queue.list":
            return await self._get_queue()
        if command == "queue.add":
            return await self._add_to_queue(**kwargs)
        if command == "queue.remove":
            return await self._remove_from_queue(**kwargs)
        if command == "queue.move":
            return await self._move_in_queue(**kwargs)
        if command == "queue.clear":
            return await self._clear_queue()
        if command == "queue.pause":
            return await self._pause_torrent_in_queue(**kwargs)
        if command == "queue.resume":
            return await self._resume_torrent_in_queue(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown queue command: {command}",
        )

    async def _get_queue(self) -> CommandResult:
        """Get queue status."""
        try:
            queue_list = await self.adapter.get_queue()
            return CommandResult(success=True, data={"queue": queue_list})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _add_to_queue(self, info_hash: str, priority: str) -> CommandResult:
        """Add torrent to queue."""
        try:
            result = await self.adapter.add_to_queue(info_hash, priority)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _remove_from_queue(self, info_hash: str) -> CommandResult:
        """Remove torrent from queue."""
        try:
            result = await self.adapter.remove_from_queue(info_hash)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _move_in_queue(
        self,
        info_hash: str,
        new_position: int,
    ) -> CommandResult:
        """Move torrent in queue."""
        try:
            result = await self.adapter.move_in_queue(info_hash, new_position)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _clear_queue(self) -> CommandResult:
        """Clear queue."""
        try:
            result = await self.adapter.clear_queue()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _pause_torrent_in_queue(self, info_hash: str) -> CommandResult:
        """Pause torrent in queue."""
        try:
            result = await self.adapter.pause_torrent_in_queue(info_hash)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _resume_torrent_in_queue(self, info_hash: str) -> CommandResult:
        """Resume torrent in queue."""
        try:
            result = await self.adapter.resume_torrent_in_queue(info_hash)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
