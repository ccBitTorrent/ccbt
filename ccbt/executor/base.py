"""Base classes for command executor.

Provides abstract base classes and data structures for command execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ccbt.executor.session_adapter import SessionAdapter


@dataclass
class CommandContext:
    """Context for command execution.

    Carries session adapter, configuration, and request metadata.
    """

    adapter: SessionAdapter
    config: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Typed result container for command execution.

    Args:
        success: Whether the command succeeded
        data: Result data (type depends on command)
        error: Error message if command failed
        metadata: Additional metadata about the execution

    """

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CommandExecutor(ABC):
    """Abstract base class for command executors.

    Provides unified interface for executing commands through session adapters.
    """

    def __init__(self, adapter: SessionAdapter):
        """Initialize command executor.

        Args:
            adapter: Session adapter (local or daemon)

        """
        self.adapter = adapter

    @abstractmethod
    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute a command.

        Args:
            command: Command name (e.g., "torrent.add", "file.list")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """

    def create_context(self, **metadata: Any) -> CommandContext:
        """Create command context.

        Args:
            **metadata: Additional metadata for context

        Returns:
            CommandContext instance

        """
        config = getattr(self.adapter, "config", None)
        return CommandContext(
            adapter=self.adapter,
            config=config,
            metadata=metadata,
        )
