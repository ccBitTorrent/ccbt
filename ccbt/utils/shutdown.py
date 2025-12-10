"""Global shutdown state management.

Provides a global flag to track shutdown state, allowing components
to suppress verbose logging and skip non-critical operations during shutdown.
"""

from __future__ import annotations

import threading
from typing import Any

# Global shutdown flag (thread-safe)
_shutdown_flag: threading.Event = threading.Event()
_shutdown_lock: threading.Lock = threading.Lock()


def is_shutting_down() -> bool:
    """Check if shutdown is in progress.
    
    Returns:
        True if shutdown has been initiated, False otherwise
    """
    return _shutdown_flag.is_set()


def set_shutdown() -> None:
    """Mark that shutdown has been initiated."""
    with _shutdown_lock:
        _shutdown_flag.set()


def clear_shutdown() -> None:
    """Clear shutdown flag (for testing)."""
    with _shutdown_lock:
        _shutdown_flag.clear()


def get_shutdown_event() -> threading.Event:
    """Get the shutdown event object (for direct access if needed).
    
    Returns:
        The shutdown Event object
    """
    return _shutdown_flag
















