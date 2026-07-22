"""Enhanced CLI for ccBitTorrent.

Provides comprehensive CLI functionality including:
- Rich interactive interface
- Progress bars and live stats
- Shell completion
- Configuration management
- Debug tools
"""

from __future__ import annotations

import importlib

from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.progress import ProgressManager

_cli_main = importlib.import_module("ccbt.cli.main")


def __getattr__(name: str):
    """Lazy exports so ccbt.cli.main stays the module for unittest.patch."""
    if name == "main":
        return _cli_main.main
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)


__all__ = [
    "InteractiveCLI",
    "ProgressManager",
    "main",
]
