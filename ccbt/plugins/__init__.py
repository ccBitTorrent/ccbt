"""Plugin system for ccBitTorrent.

Provides a flexible plugin architecture for extending functionality
with custom plugins for logging, metrics, and other features.
"""

from .base import Plugin, PluginError, PluginManager

__all__ = ["Plugin", "PluginError", "PluginManager"]
