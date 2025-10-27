"""Observability module for ccBitTorrent.

Provides comprehensive observability including:
- Request tracing
- Performance profiling
- Debug mode
- Memory profiling
- Log aggregation
"""

from .profiler import Profiler

__all__ = [
    "Profiler",
]
