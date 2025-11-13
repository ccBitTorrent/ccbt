"""Time/clock abstraction to aid testability and deterministic sleeps."""

from __future__ import annotations

import asyncio
import time as _time


class Clock:
    """Clock abstraction to aid testability."""

    def now(self) -> float:
        """Return current wall-clock time in seconds."""
        return _time.time()

    async def sleep(self, seconds: float) -> None:
        """Async sleep for the specified number of seconds."""
        await asyncio.sleep(seconds)
