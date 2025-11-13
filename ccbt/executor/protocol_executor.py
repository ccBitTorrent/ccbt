"""Protocol command executor.

Handles protocol-related commands (get_xet_protocol, get_ipfs_protocol).
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class ProtocolExecutor(CommandExecutor):
    """Executor for protocol commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute protocol command.

        Args:
            command: Command name (e.g., "protocol.get_xet", "protocol.get_ipfs")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "protocol.get_xet":
            return await self._get_xet_protocol()
        if command == "protocol.get_ipfs":
            return await self._get_ipfs_protocol()
        return CommandResult(
            success=False,
            error=f"Unknown protocol command: {command}",
        )

    async def _get_xet_protocol(self) -> CommandResult:
        """Get Xet protocol information.

        Uses the adapter's get_xet_protocol method to retrieve protocol information.
        Works with both local and daemon adapters.
        """
        try:
            protocol_info = await self.adapter.get_xet_protocol()
            return CommandResult(
                success=True,
                data={"protocol": protocol_info},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get Xet protocol: {e}",
            )

    async def _get_ipfs_protocol(self) -> CommandResult:
        """Get IPFS protocol information.

        Uses the adapter's get_ipfs_protocol method to retrieve protocol information.
        Works with both local and daemon adapters.
        """
        try:
            protocol_info = await self.adapter.get_ipfs_protocol()
            return CommandResult(
                success=True,
                data={"protocol": protocol_info},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get IPFS protocol: {e}",
            )
