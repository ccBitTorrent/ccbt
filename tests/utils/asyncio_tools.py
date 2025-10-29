from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable


@asynccontextmanager
async def fast_sleep(scale: float = 0.0) -> AsyncIterator[None]:
    """Temporarily patch asyncio.sleep to run faster.

    Args:
        scale: seconds to sleep instead of the requested duration (default 0)
    """
    original_sleep: Callable[[float], asyncio.Future] = asyncio.sleep

    async def _patched(delay: float) -> None:  # type: ignore[override]
        # Ignore requested delay and sleep a tiny amount
        await original_sleep(scale)

    asyncio.sleep = _patched  # type: ignore[assignment]
    try:
        yield
    finally:
        asyncio.sleep = original_sleep  # type: ignore[assignment]


