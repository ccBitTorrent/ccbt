"""Enhanced CLI for ccBitTorrent.

from __future__ import annotations

Provides comprehensive CLI functionality including:
- Rich interactive interface
- Progress bars and live stats
- Shell completion
- Configuration management
- Debug tools
"""

from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.main import main
from ccbt.cli.progress import ProgressManager

__all__ = [
    "InteractiveCLI",
    "ProgressManager",
    "main",
]
