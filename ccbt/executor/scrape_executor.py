"""Scrape command executor.

Handles tracker scraping commands.
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class ScrapeExecutor(CommandExecutor):
    """Executor for scrape commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute scrape command.

        Args:
            command: Command name (e.g., "scrape.torrent", "scrape.list")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "scrape.torrent":
            return await self._scrape_torrent(**kwargs)
        if command == "scrape.list":
            return await self._list_scrape_results()
        if command == "scrape.get_result":
            return await self._get_scrape_result(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown scrape command: {command}",
        )

    async def _scrape_torrent(
        self,
        info_hash: str,
        force: bool = False,
    ) -> CommandResult:
        """Scrape a torrent."""
        try:
            result = await self.adapter.scrape_torrent(info_hash, force=force)
            return CommandResult(success=True, data={"result": result})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _list_scrape_results(self) -> CommandResult:
        """List all cached scrape results."""
        try:
            results = await self.adapter.list_scrape_results()
            return CommandResult(success=True, data={"results": results})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_scrape_result(self, info_hash: str) -> CommandResult:
        """Get cached scrape result for a torrent."""
        try:
            result = await self.adapter.get_scrape_result(info_hash)
            if result is None:
                return CommandResult(
                    success=False,
                    error=f"Scrape result not found for {info_hash}",
                )
            return CommandResult(success=True, data={"result": result})
        except Exception as e:
            return CommandResult(success=False, error=str(e))
