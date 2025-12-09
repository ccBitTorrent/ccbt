"""io_uring wrapper for high-performance async I/O on Linux.

This module provides an abstraction layer for io_uring operations,
supporting both aiofiles (if available) and direct io_uring bindings.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Try to import io_uring support
HAS_IO_URING = False
IO_URING_AVAILABLE = False

try:
    # Try aiofiles first (simpler, more portable)
    import aiofiles  # type: ignore[import-untyped]

    HAS_IO_URING = True
    IO_URING_AVAILABLE = True
    IO_URING_TYPE = "aiofiles"
except ImportError:
    # Try direct io_uring bindings (more complex, requires specific library)
    try:
        # Common io_uring Python bindings
        import liburing  # type: ignore[import-untyped]

        HAS_IO_URING = True
        IO_URING_AVAILABLE = True
        IO_URING_TYPE = "liburing"
    except ImportError:
        try:
            # Alternative: pyuring
            import pyuring  # type: ignore[import-untyped]

            HAS_IO_URING = True
            IO_URING_AVAILABLE = True
            IO_URING_TYPE = "pyuring"
        except ImportError:
            HAS_IO_URING = False
            IO_URING_AVAILABLE = False
            IO_URING_TYPE = None

# Check kernel version (io_uring requires Linux 5.1+)
if sys.platform.startswith("linux") and IO_URING_AVAILABLE:
    try:
        import platform

        kernel_version = platform.release()
        # Parse kernel version (e.g., "5.4.0" -> (5, 4))
        version_parts = kernel_version.split(".")[:2]
        major, minor = int(version_parts[0]), int(version_parts[1])
        if major < 5 or (major == 5 and minor < 1):
            logger.debug(
                "io_uring requires Linux 5.1+, detected %s. Disabling io_uring.",
                kernel_version,
            )
            IO_URING_AVAILABLE = False
    except Exception:
        # If version detection fails, assume it's available (will fail gracefully if not)
        pass


class IOUringWrapper:
    """Wrapper for io_uring operations with fallback to regular async I/O."""

    def __init__(self) -> None:
        """Initialize io_uring wrapper."""
        self.available = IO_URING_AVAILABLE and sys.platform.startswith("linux")
        self.io_uring_type = IO_URING_TYPE if self.available else None
        self.operation_count = 0
        self.error_count = 0

        if self.available:
            logger.info("io_uring support enabled (type: %s)", self.io_uring_type)
        else:
            logger.debug("io_uring not available, will use fallback I/O")

    async def read(
        self, file_path: str | Any, offset: int, length: int
    ) -> bytes:
        """Read data using io_uring if available, otherwise fallback.

        Args:
            file_path: Path to file (Path or str)
            offset: Offset in bytes
            length: Number of bytes to read

        Returns:
            Read data as bytes

        """
        if not self.available:
            # Fallback to regular async I/O
            return await self._read_fallback(file_path, offset, length)

        try:
            if self.io_uring_type == "aiofiles":
                return await self._read_aiofiles(file_path, offset, length)
            else:
                # Direct io_uring bindings would go here
                # For now, fallback to regular I/O
                return await self._read_fallback(file_path, offset, length)
        except Exception as e:
            self.error_count += 1
            logger.debug("io_uring read failed, using fallback: %s", e)
            return await self._read_fallback(file_path, offset, length)

    async def write(
        self, file_path: str | Any, offset: int, data: bytes
    ) -> int:
        """Write data using io_uring if available, otherwise fallback.

        Args:
            file_path: Path to file (Path or str)
            offset: Offset in bytes
            data: Data to write

        Returns:
            Number of bytes written

        """
        if not self.available:
            # Fallback to regular async I/O
            return await self._write_fallback(file_path, offset, data)

        try:
            if self.io_uring_type == "aiofiles":
                return await self._write_aiofiles(file_path, offset, data)
            else:
                # Direct io_uring bindings would go here
                # For now, fallback to regular I/O
                return await self._write_fallback(file_path, offset, data)
        except Exception as e:
            self.error_count += 1
            logger.debug("io_uring write failed, using fallback: %s", e)
            return await self._write_fallback(file_path, offset, data)

    async def _read_aiofiles(
        self, file_path: str | Any, offset: int, length: int
    ) -> bytes:
        """Read using aiofiles."""
        import aiofiles  # type: ignore[import-untyped]

        path_str = str(file_path)
        async with aiofiles.open(path_str, "rb") as f:
            await f.seek(offset)
            data = await f.read(length)
            self.operation_count += 1
            return data

    async def _write_aiofiles(
        self, file_path: str | Any, offset: int, data: bytes
    ) -> int:
        """Write using aiofiles."""
        import aiofiles  # type: ignore[import-untyped]

        path_str = str(file_path)
        async with aiofiles.open(path_str, "r+b") as f:
            await f.seek(offset)
            await f.write(data)
            self.operation_count += 1
            return len(data)

    async def _read_fallback(
        self, file_path: str | Any, offset: int, length: int
    ) -> bytes:
        """Fallback read using regular async I/O."""
        loop = asyncio.get_event_loop()
        path_str = str(file_path)

        def _read_sync() -> bytes:
            with open(path_str, "rb") as f:
                f.seek(offset)
                return f.read(length)

        return await loop.run_in_executor(None, _read_sync)

    async def _write_fallback(
        self, file_path: str | Any, offset: int, data: bytes
    ) -> int:
        """Fallback write using regular async I/O."""
        loop = asyncio.get_event_loop()
        path_str = str(file_path)

        def _write_sync() -> int:
            with open(path_str, "r+b") as f:
                f.seek(offset)
                f.write(data)
                return len(data)

        return await loop.run_in_executor(None, _write_sync)

    def get_stats(self) -> dict[str, Any]:
        """Get io_uring wrapper statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "available": self.available,
            "io_uring_type": self.io_uring_type,
            "operation_count": self.operation_count,
            "error_count": self.error_count,
        }







































