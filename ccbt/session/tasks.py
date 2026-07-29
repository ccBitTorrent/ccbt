"""Task supervision and management.

This module provides task supervision utilities for managing background tasks,
including task cancellation, timeout handling, and task lifecycle management.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Awaitable, Optional


class TaskSupervisor:
    """Lightweight task supervisor to track and cancel background tasks safely."""

    def __init__(self) -> None:
        """Initialize the task supervisor with an empty task set."""
        self._tasks: set[asyncio.Task[Any]] = set()

    def create_task(
        self, coro: Awaitable[Any], *, name: Optional[str] = None
    ) -> asyncio.Task[Any]:
        """Create and track a new async task.

        Args:
            coro: Coroutine to run as a task
            name: Optional name for the task

        Returns:
            The created asyncio task

        """
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def cancel_all(self) -> None:
        """Cancel all tracked tasks."""
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

    async def wait_all_cancelled(self, timeout: float = 5.0) -> None:
        """Wait for all tasks to be cancelled or complete.

        Args:
            timeout: Maximum time to wait in seconds

        """
        if not self._tasks:
            return
        with contextlib.suppress(asyncio.TimeoutError):
            # Best-effort cancellation; remaining tasks may be daemon-like
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout
            )

    @property
    def tasks(self) -> set[asyncio.Task[Any]]:
        """Get a copy of all tracked tasks.

        Returns:
            Set of all tracked asyncio tasks

        """
        return set(self._tasks)
