"""Screen components for the terminal dashboard."""

from __future__ import annotations

from ccbt.interface.screens.base import (
    ConfigScreen,
    ConfirmationDialog,
    InputDialog,
    GlobalConfigScreen,
    MonitoringScreen,
    PerTorrentConfigScreen,
)
# Note: tabbed_base.py Screen classes are deprecated/unused.
# The new implementation uses Container widgets instead of Screen classes.
# from ccbt.interface.screens.tabbed_base import (
#     PerTorrentTabScreen,
#     PreferencesTabScreen,
#     TorrentsTabScreen,
# )

__all__ = [
    "ConfigScreen",
    "ConfirmationDialog",
    "InputDialog",
    "GlobalConfigScreen",
    "MonitoringScreen",
    "PerTorrentConfigScreen",
    # "PerTorrentTabScreen",  # Deprecated - use Container widgets instead
    # "PreferencesTabScreen",  # Deprecated - use Container widgets instead
    # "TorrentsTabScreen",  # Deprecated - use Container widgets instead
]
