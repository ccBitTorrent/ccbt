"""Console utilities for Rich output with i18n support.

This module provides console creation and error handling utilities.
For spinner utilities and helper functions, see ccbt.utils.console_utils.
"""

from __future__ import annotations

import sys

from rich.console import Console

# Re-export utilities from console_utils for convenience
from ccbt.utils.console_utils import (
    create_progress,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_table,
    print_warning,
    spinner,
)

__all__ = [
    "create_console",
    "create_progress",
    "print_error",
    "print_info",
    "print_panel",
    "print_success",
    "print_table",
    "print_warning",
    "safe_print_error",
    "spinner",
]


def create_console() -> Console:
    """Create a Rich Console with Windows encoding compatibility."""
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure") and callable(
                getattr(sys.stdout, "reconfigure", None)
            ):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            if hasattr(sys.stderr, "reconfigure") and callable(
                getattr(sys.stderr, "reconfigure", None)
            ):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    return Console(
        file=sys.stdout,
        force_terminal=None,
        legacy_windows=False,
        safe_box=True,
    )


def safe_print_error(
    console: Console, message: str, prefix: str = "[red]Error:[/red]"
) -> None:
    """Safely print error messages with encoding error handling.

    Note: For new code, prefer using print_error() from console_utils
    which includes i18n support.
    """
    try:
        try:
            message.encode("ascii")
            console.print(f"{prefix} {message}")
        except UnicodeEncodeError:
            safe_message = message.encode("ascii", errors="replace").decode("ascii")
            console.print(f"{prefix} {safe_message}")
    except Exception:
        try:
            safe_msg = str(message).encode("ascii", errors="replace").decode("ascii")
            print(f"Error: {safe_msg}")
        except Exception:
            print(
                "Error: An error occurred (details unavailable due to encoding issues)"
            )
