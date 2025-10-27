"""Enhanced CLI for ccBitTorrent.

Provides comprehensive CLI functionality including:
- Rich interactive interface
- Progress bars and live stats
- Shell completion
- Configuration management
- Debug tools
"""

from .interactive import InteractiveCLI
from .main import main
from .progress import ProgressManager

__all__ = [
    "InteractiveCLI",
    "ProgressManager",
    "main",
]
