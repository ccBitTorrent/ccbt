from __future__ import annotations

import asyncio
from typing import Any, Awaitable


class TaskSupervisor:
    """Lightweight task supervisor to track and cancel background tasks safely."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def create_task(
        self, coro: Awaitable[Any], *, name: str | None = None
    ) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

    async def wait_all_cancelled(self, timeout: float = 5.0) -> None:
        if not self._tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout
            )
        except asyncio.TimeoutError:
            # Best-effort cancellation; remaining tasks may be daemon-like
            pass

    @property
    def tasks(self) -> set[asyncio.Task[Any]]:
        return set(self._tasks)
