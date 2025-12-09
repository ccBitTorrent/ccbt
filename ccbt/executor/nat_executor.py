"""NAT command executor.

Handles NAT traversal commands.
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult
from ccbt.executor.session_adapter import LocalSessionAdapter


class NATExecutor(CommandExecutor):
    """Executor for NAT commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute NAT command.

        Args:
            command: Command name (e.g., "nat.status", "nat.discover")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "nat.status":
            return await self._get_nat_status()
        if command == "nat.discover":
            return await self._discover_nat()
        if command == "nat.map":
            return await self._map_nat_port(**kwargs)
        if command == "nat.unmap":
            return await self._unmap_nat_port(**kwargs)
        if command == "nat.refresh":
            return await self._refresh_nat_mappings()
        if command == "nat.get_external_ip":
            return await self._get_external_ip()
        if command == "nat.get_external_port":
            return await self._get_external_port(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown NAT command: {command}",
        )

    async def _get_nat_status(self) -> CommandResult:
        """Get NAT status."""
        try:
            status = await self.adapter.get_nat_status()
            return CommandResult(success=True, data={"status": status})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _discover_nat(self) -> CommandResult:
        """Discover NAT devices."""
        try:
            result = await self.adapter.discover_nat()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _map_nat_port(
        self,
        internal_port: int,
        external_port: int | None = None,
        protocol: str = "tcp",
    ) -> CommandResult:
        """Map a port via NAT."""
        try:
            result = await self.adapter.map_nat_port(
                internal_port,
                external_port,
                protocol,
            )
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _unmap_nat_port(self, port: int, protocol: str = "tcp") -> CommandResult:
        """Unmap a port via NAT."""
        try:
            result = await self.adapter.unmap_nat_port(port, protocol)
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _refresh_nat_mappings(self) -> CommandResult:
        """Refresh NAT mappings."""
        try:
            result = await self.adapter.refresh_nat_mappings()
            return CommandResult(success=True, data=result)
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_external_ip(self) -> CommandResult:
        """Get external IP address."""
        try:
            if not isinstance(self.adapter, LocalSessionAdapter):
                # For daemon, get from status
                status = await self.adapter.get_nat_status()
                external_ip = status.external_ip if status else None
                return CommandResult(
                    success=True,
                    data={"external_ip": str(external_ip) if external_ip else None},
                )

            session = self.adapter.session_manager
            nat_manager = getattr(session, "nat_manager", None)
            if not nat_manager:
                return CommandResult(
                    success=False,
                    error="NAT manager not available",
                )

            external_ip = await nat_manager.get_external_ip()
            return CommandResult(
                success=True,
                data={"external_ip": str(external_ip) if external_ip else None},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_external_port(
        self,
        internal_port: int,
        protocol: str = "tcp",
    ) -> CommandResult:
        """Get external port for an internal port."""
        try:
            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="get_external_port only available in local mode",
                )

            session = self.adapter.session_manager
            nat_manager = getattr(session, "nat_manager", None)
            if not nat_manager:
                return CommandResult(
                    success=False,
                    error="NAT manager not available",
                )

            external_port = await nat_manager.get_external_port(internal_port, protocol)
            return CommandResult(
                success=True,
                data={"external_port": external_port},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))
