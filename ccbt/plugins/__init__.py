"""Plugin system for ccBitTorrent.

from __future__ import annotations

Provides a flexible plugin architecture for extending functionality
with custom plugins for logging, metrics, and other features.
"""

from ccbt.plugins.base import Plugin, PluginError, PluginManager

__all__ = ["Plugin", "PluginError", "PluginManager"]
