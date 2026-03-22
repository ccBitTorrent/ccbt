"""Cross-version compatibility helpers."""

from __future__ import annotations

import asyncio
import functools
import hashlib
import sys
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def to_thread_compat(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking function in a worker thread across Python versions."""
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    bound = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, bound)


def sha1_compat(data: bytes, *, usedforsecurity: bool = True) -> Any:
    """Return a SHA-1 hash object with Python 3.8 compatibility."""
    if sys.version_info >= (3, 9):
        return hashlib.sha1(data, usedforsecurity=usedforsecurity)
    return hashlib.sha1(data)  # nosec B324 — Python 3.8 has no usedforsecurity kwarg


def md5_compat(data: bytes, *, usedforsecurity: bool = True) -> Any:
    """Return an MD5 hash object with Python 3.8 compatibility."""
    if sys.version_info >= (3, 9):
        return hashlib.md5(data, usedforsecurity=usedforsecurity)
    return hashlib.md5(data)  # nosec B324 — Python 3.8 has no usedforsecurity kwarg
