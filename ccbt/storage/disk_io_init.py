"""Disk I/O initialization and lifecycle management for ccBitTorrent.

This module provides global disk I/O manager singleton with initialization
and shutdown functions, following the same pattern as metrics initialization.

Provides:
- get_disk_io_manager(): Get or create global DiskIOManager singleton
- init_disk_io(): Initialize and start disk I/O manager
- shutdown_disk_io(): Gracefully shutdown disk I/O manager
"""

from __future__ import annotations

import logging
from typing import Any

from ccbt.config.config import get_config
from ccbt.storage.disk_io import DiskIOManager

# Singleton pattern removed - DiskIOManager is now managed via AsyncSessionManager.disk_io_manager
# This ensures proper lifecycle management and prevents conflicts between multiple session managers
# Deprecated singleton kept for backward compatibility
_GLOBAL_DISK_IO_MANAGER: DiskIOManager | None = (
    None  # Deprecated - use session_manager.disk_io_manager
)


def get_disk_io_manager() -> DiskIOManager:
    """Return a process-global DiskIOManager to share resources across components.

    DEPRECATED: Singleton pattern removed. Use session_manager.disk_io_manager instead.
    This function is kept for backward compatibility but will log a warning.

    Returns:
        DiskIOManager: Singleton disk I/O manager instance (deprecated - use session_manager.disk_io_manager).

    Note:
        This function creates a new DiskIOManager if one doesn't exist.
        Use init_disk_io() to start disk I/O manager based on configuration.
        The manager is configured using values from config.disk.*.

    Example:
        ```python
        disk_io = get_disk_io_manager()  # Deprecated
        # Use session_manager.disk_io_manager instead
        ```

    """
    import warnings

    warnings.warn(
        "get_disk_io_manager() is deprecated. "
        "Use session_manager.disk_io_manager instead. "
        "Singleton pattern removed to ensure proper lifecycle management.",
        DeprecationWarning,
        stacklevel=2,
    )
    global _GLOBAL_DISK_IO_MANAGER

    if _GLOBAL_DISK_IO_MANAGER is None:
        config = get_config()

        # Get configuration values with defaults
        max_workers = config.disk.disk_workers
        queue_size = config.disk.disk_queue_size
        cache_size_mb = getattr(config.disk, "cache_size_mb", 256)

        _GLOBAL_DISK_IO_MANAGER = DiskIOManager(
            max_workers=max_workers,
            queue_size=queue_size,
            cache_size_mb=cache_size_mb,
        )

    return _GLOBAL_DISK_IO_MANAGER


async def init_disk_io(manager: Any | None = None) -> DiskIOManager | None:
    """Initialize and start disk I/O manager.

    CRITICAL FIX: Singleton pattern removed. This function now accepts an optional
    session_manager parameter. If provided, it will use the disk_io_manager from
    the session manager. Otherwise, it falls back to the deprecated singleton.

    Args:
        manager: Optional session manager instance. If provided, uses manager.disk_io_manager.

    This function:
    - Gets disk I/O manager from session manager if available, otherwise uses deprecated singleton
    - Starts the disk I/O manager background tasks
    - Handles errors gracefully (logs warnings, doesn't raise)
    - Returns None on failure instead of raising exceptions

    Returns:
        DiskIOManager | None: DiskIOManager instance if successfully started,
            None if initialization failed.

    Note:
        This function is safe to call multiple times. If the manager is already
        running, it will return the existing instance without re-initializing.

        Errors are logged but don't prevent the function from returning None,
        allowing callers to continue even if disk I/O initialization fails.

    Example:
        ```python
        disk_io = await init_disk_io(session_manager)
        if disk_io:
            # Disk I/O manager is active
            pass
        ```

    """
    logger = logging.getLogger(__name__)

    try:
        # CRITICAL FIX: Use disk I/O manager from session manager if available
        disk_io_manager = None
        if manager and hasattr(manager, "disk_io_manager") and manager.disk_io_manager:
            disk_io_manager = manager.disk_io_manager
            logger.debug("Using disk I/O manager from session manager")
        else:
            # Fallback to deprecated singleton for backward compatibility
            try:
                disk_io_manager = get_disk_io_manager()
            except (
                RuntimeError,
                Exception,
            ) as get_manager_error:  # pragma: no cover - Defensive: get_disk_io_manager() exception
                logger.warning(
                    "Failed to get disk I/O manager: %s",
                    get_manager_error,
                    exc_info=True,
                )
                return None

        # Check if already running
        if disk_io_manager._running:  # noqa: SLF001
            logger.debug("Disk I/O manager already running")
            return disk_io_manager

        # Start disk I/O manager
        await disk_io_manager.start()

        logger.info(
            "Disk I/O manager started (workers: %d, queue_size: %d, cache_size_mb: %d)",
            disk_io_manager.max_workers,
            disk_io_manager.queue_size,
            disk_io_manager.cache_size_mb,
        )
        return disk_io_manager

    except (
        RuntimeError
    ) as runtime_error:  # pragma: no cover - Defensive: get_config() exception
        logger.warning(
            "Failed to get configuration for disk I/O: %s",
            runtime_error,
            exc_info=True,
        )
        return None
    except (
        Exception
    ) as e:  # pragma: no cover - Defensive: any other exception during initialization
        logger.warning("Failed to initialize disk I/O manager: %s", e, exc_info=True)
        return None


async def shutdown_disk_io() -> None:
    """Gracefully shutdown disk I/O manager.

    This function:
    - Gets the global DiskIOManager singleton
    - Stops the disk I/O manager background tasks if running
    - Handles errors gracefully (logs warnings, doesn't raise)

    Note:
        This function is safe to call multiple times or when disk I/O
        is not running. It will perform a no-op in those cases.

    Example:
        ```python
        await shutdown_disk_io()
        ```

    """
    logger = logging.getLogger(__name__)

    try:
        global _GLOBAL_DISK_IO_MANAGER  # noqa: PLW0602

        if _GLOBAL_DISK_IO_MANAGER is None:
            logger.debug("Disk I/O manager not initialized, skipping shutdown")
            return

        # Check if running before stopping
        if not _GLOBAL_DISK_IO_MANAGER._running:  # noqa: SLF001
            logger.debug("Disk I/O manager not running, skipping shutdown")
            return

        # Stop disk I/O manager
        try:
            await _GLOBAL_DISK_IO_MANAGER.stop()
            logger.info("Disk I/O manager stopped")
        except (
            Exception
        ) as stop_error:  # pragma: no cover - Defensive: stop() exception handling
            logger.warning(
                "Error during disk I/O shutdown: %s", stop_error, exc_info=True
            )

        # Optional: Reset singleton for clean shutdown
        # Uncomment if you want to allow re-initialization after shutdown
        # _GLOBAL_DISK_IO_MANAGER = None

    except Exception as e:  # pragma: no cover - Defensive: shutdown exception handler
        logger.warning("Failed to shutdown disk I/O manager: %s", e, exc_info=True)
