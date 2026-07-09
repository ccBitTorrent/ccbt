"""Disk I/O initialization and lifecycle helpers for ccBitTorrent.

Historically these helpers exposed process-global manager state. The singleton
pattern is now deprecated in favor of session-owned managers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ccbt.config.config import get_config
from ccbt.storage.disk_io import DiskIOManager


def get_disk_io_manager() -> DiskIOManager:
    """Create a dedicated DiskIOManager instance for compatibility callers.

    DEPRECATED: Singleton pattern removed. Use session_manager.disk_io_manager instead.
    This function is kept for backward compatibility and now returns an
    independent manager instance to avoid shared state.

    Returns:
        DiskIOManager: Dedicated disk I/O manager instance (deprecated - use
            session_manager.disk_io_manager).

    Note:
        This function creates a new DiskIOManager on every call.
        Use init_disk_io() to start a manager based on configuration.
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
        "compatibility instances are now independent.",
        DeprecationWarning,
        stacklevel=2,
    )
    config = get_config()
    return DiskIOManager(
        max_workers=config.disk.disk_workers,
        queue_size=config.disk.disk_queue_size,
        cache_size_mb=getattr(config.disk, "cache_size_mb", 256),
    )


async def init_disk_io(manager: Optional[Any] = None) -> Optional[DiskIOManager]:
    """Initialize and start disk I/O manager.

    Note: Singleton pattern removed. This function now accepts an optional
    session_manager parameter. If provided, it will use the disk_io_manager from
    the session manager. Otherwise, it uses a compatibility manager instance.

    Args:
        manager: Optional session manager instance. If provided, uses manager.disk_io_manager.

    This function:
        - Gets disk I/O manager from session manager if available, otherwise uses
            a compatibility manager instance
    - Starts the disk I/O manager background tasks
    - Handles errors gracefully (logs warnings, doesn't raise)
    - Returns None on failure instead of raising exceptions

    Returns:
        Optional[DiskIOManager]: DiskIOManager instance if successfully started,
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
        # Note: Use disk I/O manager from session manager if available
        disk_io_manager = None
        if manager and hasattr(manager, "disk_io_manager") and manager.disk_io_manager:
            disk_io_manager = manager.disk_io_manager
            logger.debug("Using disk I/O manager from session manager")
        else:
            logger.debug("Using compatibility-created disk I/O manager")
            disk_io_manager = get_disk_io_manager()

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


async def shutdown_disk_io(manager: Optional[Any] = None) -> None:
    """Gracefully shutdown disk I/O manager.

    This function:
    - Stops a session-owned disk I/O manager if available
    - Logs and returns when no manager is provided (deprecated path)
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
        disk_io_manager = None
        if manager and hasattr(manager, "disk_io_manager") and manager.disk_io_manager:
            disk_io_manager = manager.disk_io_manager
            logger.debug("Using session-owned disk I/O manager for shutdown")
        if disk_io_manager is None:
            logger.debug(
                "No session-owned disk I/O manager provided to shutdown_disk_io()"
            )
            return

        # Check if running before stopping
        if not disk_io_manager._running:  # noqa: SLF001
            logger.debug("Disk I/O manager not running, skipping shutdown")
            return

        # Stop disk I/O manager
        try:
            await disk_io_manager.stop()
            logger.info("Disk I/O manager stopped")
        except (
            Exception
        ) as stop_error:  # pragma: no cover - Defensive: stop() exception handling
            logger.warning(
                "Error during disk I/O shutdown: %s", stop_error, exc_info=True
            )

    except Exception as e:  # pragma: no cover - Defensive: shutdown exception handler
        logger.warning("Failed to shutdown disk I/O manager: %s", e, exc_info=True)
