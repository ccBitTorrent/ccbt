"""Unified command executor.

Routes commands to appropriate domain executors.
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult
from ccbt.executor.config_executor import ConfigExecutor
from ccbt.executor.file_executor import FileExecutor
from ccbt.executor.nat_executor import NATExecutor
from ccbt.executor.protocol_executor import ProtocolExecutor
from ccbt.executor.queue_executor import QueueExecutor
from ccbt.executor.scrape_executor import ScrapeExecutor
from ccbt.executor.security_executor import SecurityExecutor
from ccbt.executor.session_adapter import SessionAdapter
from ccbt.executor.session_executor import SessionExecutor
from ccbt.executor.torrent_executor import TorrentExecutor


class UnifiedCommandExecutor(CommandExecutor):
    """Unified executor that routes commands to domain executors."""

    def __init__(self, adapter: SessionAdapter):
        """Initialize unified command executor.

        Args:
            adapter: Session adapter (local or daemon)

        """
        super().__init__(adapter)
        # Initialize domain executors
        self.torrent_executor = TorrentExecutor(adapter)
        self.file_executor = FileExecutor(adapter)
        self.queue_executor = QueueExecutor(adapter)
        self.nat_executor = NATExecutor(adapter)
        self.scrape_executor = ScrapeExecutor(adapter)
        self.config_executor = ConfigExecutor(adapter)
        self.protocol_executor = ProtocolExecutor(adapter)
        self.session_executor = SessionExecutor(adapter)
        self.security_executor = SecurityExecutor(adapter)

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute command by routing to appropriate domain executor.

        Args:
            command: Command name (e.g., "torrent.add", "file.list")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        # Route to appropriate executor based on command prefix
        if command.startswith("torrent."):
            return await self.torrent_executor.execute(command, *args, **kwargs)
        if command.startswith("file."):
            return await self.file_executor.execute(command, *args, **kwargs)
        if command.startswith("queue."):
            return await self.queue_executor.execute(command, *args, **kwargs)
        if command.startswith("nat."):
            return await self.nat_executor.execute(command, *args, **kwargs)
        if command.startswith("scrape."):
            return await self.scrape_executor.execute(command, *args, **kwargs)
        if command.startswith("config."):
            return await self.config_executor.execute(command, *args, **kwargs)
        if command.startswith("protocol."):
            return await self.protocol_executor.execute(command, *args, **kwargs)
        if command.startswith("session."):
            return await self.session_executor.execute(command, *args, **kwargs)
        if command.startswith("security."):
            return await self.security_executor.execute(command, *args, **kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown command: {command}",
        )
