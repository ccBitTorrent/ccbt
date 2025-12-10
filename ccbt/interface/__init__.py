"""Interface module for ccBitTorrent terminal dashboard."""

from __future__ import annotations

# Lazy imports to avoid breaking when terminal_dashboard has issues
try:
    from ccbt.interface.data_provider import (
        DataProvider,
        DaemonDataProvider,
        LocalDataProvider,
        create_data_provider,
    )
except ImportError:
    # Graceful degradation if data_provider has issues
    DataProvider = None  # type: ignore[assignment, misc]
    DaemonDataProvider = None  # type: ignore[assignment, misc]
    LocalDataProvider = None  # type: ignore[assignment, misc]
    create_data_provider = None  # type: ignore[assignment, misc]

try:
    from ccbt.interface.terminal_dashboard import TerminalDashboard
except (ImportError, TypeError):
    # Graceful degradation if terminal_dashboard has issues
    TerminalDashboard = None  # type: ignore[assignment, misc]

__all__ = [
    "DataProvider",
    "DaemonDataProvider",
    "LocalDataProvider",
    "TerminalDashboard",
    "create_data_provider",
]
