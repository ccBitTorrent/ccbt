"""Task helpers for tracking and cancelling background tasks."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine


class BackgroundTaskGroup:
    """Tracks background tasks for easier cancellation and cleanup."""

    def __init__(self) -> None:
        """Initialize empty task group."""
        self._tasks: set[asyncio.Task[Any]] = set()

    def create(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Create and track an asyncio task from a coroutine."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def cancel_and_wait(self, timeout: float | None = None) -> None:
        """Cancel all tracked tasks and wait for completion (with optional timeout)."""
        if not self._tasks:
            return
        for t in list(self._tasks):
            if not t.done():
                t.cancel()
        if timeout is None:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        else:
            import contextlib

            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=timeout,
                )
        self._tasks.clear()
