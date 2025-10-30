"""Shared utilities and infrastructure.

This module contains common utilities used throughout the application.
"""

from __future__ import annotations

from ccbt.utils.events import Event, EventHandler, EventType, emit_event
from ccbt.utils.exceptions import (
    BencodeError,
    ConfigurationError,
    DiskError,
    NetworkError,
    TorrentError,
    ValidationError,
)
from ccbt.utils.logging_config import get_logger, setup_logging
from ccbt.utils.network_optimizer import NetworkOptimizer

# ResilienceManager is not a class in resilience.py - using BulkOperationManager and other functions directly

__all__ = [
    # Exceptions
    "BencodeError",
    "ConfigurationError",
    "DiskError",
    # Events
    "Event",
    "EventHandler",
    "EventType",
    "NetworkError",
    # Network
    "NetworkOptimizer",
    "TorrentError",
    "ValidationError",
    "emit_event",
    # Logging
    "get_logger",
    "setup_logging",
    # Resilience - functions and classes available directly from ccbt.utils.resilience
]
