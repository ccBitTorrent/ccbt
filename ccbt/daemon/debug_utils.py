"""Debugging utilities for daemon process monitoring."""

from __future__ import annotations

import atexit
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

# Global debug state
_debug_enabled = False
_debug_log_file: Path | None = None
_debug_lock = threading.Lock()


def enable_debug_logging(log_file: Path | None = None) -> None:
    """Enable comprehensive debug logging to file.

    Args:
        log_file: Path to debug log file (default: ~/.ccbt/daemon/debug.log)

    """
    global _debug_enabled, _debug_log_file

    if log_file is None:
        log_file = Path.home() / ".ccbt" / "daemon" / "debug.log"

    log_file.parent.mkdir(parents=True, exist_ok=True)
    _debug_log_file = log_file
    _debug_enabled = True

    # Write initial debug entry
    _debug_write("=" * 80)
    _debug_write(f"DEBUG LOGGING ENABLED - PID {os.getpid()}")
    _debug_write(f"Python: {sys.version}")
    _debug_write(f"Platform: {sys.platform}")
    _debug_write(f"Time: {time.time()}")
    _debug_write("=" * 80)

    # Register exit handler to log when process exits
    atexit.register(_debug_exit_handler)

    # Hook into sys.excepthook to catch all unhandled exceptions
    original_excepthook = sys.excepthook

    def debug_excepthook(
        exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Any
    ) -> None:
        """Log all unhandled exceptions."""
        _debug_write("=" * 80)
        _debug_write(f"UNHANDLED EXCEPTION: {exc_type.__name__}: {exc_value}")
        _debug_write(
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        )
        _debug_write("=" * 80)
        # Call original handler
        original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = debug_excepthook


def _debug_write(message: str) -> None:
    """Write debug message to log file."""
    if not _debug_enabled or _debug_log_file is None:
        return

    try:
        with _debug_lock:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            with _debug_log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
                f.flush()
    except Exception:
        # Don't fail if debug logging fails
        pass


def _debug_exit_handler() -> None:
    """Log when process exits."""
    _debug_write("=" * 80)
    _debug_write(f"PROCESS EXITING - PID {os.getpid()}")
    _debug_write(f"Time: {time.time()}")

    # Get current stack trace
    _debug_write("Current stack trace:")
    for line in traceback.format_stack():
        _debug_write(line.rstrip())

    _debug_write("=" * 80)


def debug_log(message: str, *args: Any) -> None:
    """Log debug message.

    Args:
        message: Message format string
        *args: Format arguments

    """
    if _debug_enabled:
        formatted = message % args if args else message
        _debug_write(formatted)


def debug_log_exception(message: str, exc: Exception) -> None:
    """Log exception with full traceback.

    Args:
        message: Context message
        exc: Exception to log

    """
    if _debug_enabled:
        _debug_write(f"{message}: {exc}")
        _debug_write(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )


def debug_log_stack(message: str = "Stack trace") -> None:
    """Log current stack trace.

    Args:
        message: Context message

    """
    if _debug_enabled:
        _debug_write(f"{message}:")
        for line in traceback.format_stack():
            _debug_write(line.rstrip())


def debug_log_event_loop_state() -> None:
    """Log current event loop state."""
    if not _debug_enabled:
        return

    try:
        import asyncio

        loop = asyncio.get_running_loop()
        _debug_write(f"Event loop: {loop}")
        _debug_write(f"Event loop closed: {loop.is_closed()}")
        _debug_write(f"Event loop running: {loop.is_running()}")

        # Get all tasks
        tasks = asyncio.all_tasks(loop)
        _debug_write(f"Active tasks: {len(tasks)}")
        for task in tasks:
            _debug_write(
                f"  Task: {task}, done: {task.done()}, cancelled: {task.cancelled()}"
            )
    except RuntimeError as e:
        _debug_write(f"Could not get event loop: {e}")
    except Exception as e:
        _debug_write(f"Error logging event loop state: {e}")


def debug_log_process_state() -> None:
    """Log current process state."""
    if not _debug_enabled:
        return

    try:
        import psutil

        process = psutil.Process(os.getpid())
        _debug_write("Process state:")
        _debug_write(f"  PID: {process.pid}")
        _debug_write(f"  Status: {process.status()}")
        _debug_write(f"  Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        _debug_write(f"  CPU: {process.cpu_percent()}%")
        _debug_write(f"  Threads: {process.num_threads()}")
    except ImportError:
        _debug_write("psutil not available for process monitoring")
    except Exception as e:
        _debug_write(f"Error logging process state: {e}")
