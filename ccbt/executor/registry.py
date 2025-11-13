"""Command registry for command executor.

Maps command names to executor methods.
"""

from __future__ import annotations

from typing import Any, Callable


class CommandRegistry:
    """Registry for command handlers.

    Maps command names (e.g., "torrent.add") to handler functions.
    """

    def __init__(self):
        """Initialize command registry."""
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, command: str, handler: Callable[..., Any]) -> None:
        """Register a command handler.

        Args:
            command: Command name (e.g., "torrent.add")
            handler: Handler function

        """
        self._handlers[command] = handler

    def get(self, command: str) -> Callable[..., Any] | None:
        """Get command handler.

        Args:
            command: Command name

        Returns:
            Handler function or None if not found

        """
        return self._handlers.get(command)

    def has(self, command: str) -> bool:
        """Check if command is registered.

        Args:
            command: Command name

        Returns:
            True if registered, False otherwise

        """
        return command in self._handlers

    def list_commands(self) -> list[str]:
        """List all registered commands.

        Returns:
            List of command names

        """
        return list(self._handlers.keys())
