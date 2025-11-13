"""Config command executor.

Handles configuration commands.
"""

from __future__ import annotations

from ccbt.executor.base import CommandExecutor, CommandResult


class ConfigExecutor(CommandExecutor):
    """Executor for config commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute config command.

        Args:
            command: Command name (e.g., "config.get", "config.update")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "config.get":
            return await self._get_config()
        if command == "config.update":
            return await self._update_config(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown config command: {command}",
        )

    async def _get_config(self) -> CommandResult:
        """Get current config."""
        try:
            config = await self.adapter.get_config()
            return CommandResult(success=True, data={"config": config})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _update_config(self, config_dict: dict) -> CommandResult:
        """Update config."""
        try:
            result = await self.adapter.update_config(config_dict)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
