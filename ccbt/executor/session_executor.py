"""Session-level command executor.

Handles session-level operations (get_global_stats, etc.).
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class SessionExecutor(CommandExecutor):
    """Executor for session-level commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute session command.

        Args:
            command: Command name (e.g., "session.get_global_stats")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "session.get_global_stats":
            return await self._get_global_stats()
        return CommandResult(
            success=False,
            error=f"Unknown session command: {command}",
        )

    async def _get_global_stats(self) -> CommandResult:
        """Get global statistics across all torrents."""
        try:
            stats = await self.adapter.get_global_stats()
            return CommandResult(success=True, data={"stats": stats})
        except Exception as e:
            return CommandResult(success=False, error=str(e))
