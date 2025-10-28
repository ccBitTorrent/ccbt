"""Observability module for ccBitTorrent.

from __future__ import annotations

Provides comprehensive observability including:
- Request tracing
- Performance profiling
- Debug mode
- Memory profiling
- Log aggregation
"""

from ccbt.observability.profiler import Profiler

__all__ = [
    "Profiler",
]
