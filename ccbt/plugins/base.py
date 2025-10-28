"""Base plugin system for ccBitTorrent.

from __future__ import annotations

Provides the foundation for a flexible plugin architecture that allows
extending functionality with custom plugins.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ccbt.exceptions import CCBTError
from ccbt.logging_config import get_logger


class PluginState(Enum):
    """Plugin lifecycle states."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class PluginError(CCBTError):
    """Exception raised for plugin-related errors."""


@dataclass
class PluginInfo:
    """Information about a plugin."""

    name: str
    version: str
    description: str
    author: str
    dependencies: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    state: PluginState = PluginState.UNLOADED
    error: str | None = None


class Plugin(ABC):
    """Base class for all plugins."""

    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        """Initialize plugin.

        Args:
            name: Plugin name
            version: Plugin version
            description: Plugin description
        """
        self.name = name
        self.version = version
        self.description = description
        self.state = PluginState.UNLOADED
        self.error: str | None = None
        self.logger = get_logger(f"plugin.{name}")
        self._hooks: dict[str, list[Callable]] = {}
        self._dependencies: list[str] = []

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin."""

    @abstractmethod
    async def start(self) -> None:
        """Start the plugin."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the plugin."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources."""

    def get_info(self) -> PluginInfo:
        """Get plugin information."""
        return PluginInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            author=getattr(self, "author", "Unknown"),
            dependencies=self._dependencies,
            hooks=list(self._hooks.keys()),
            state=self.state,
        )

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a hook callback."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
        self.logger.debug("Registered hook '%s'", hook_name)

    def unregister_hook(self, hook_name: str, callback: Callable) -> None:
        """Unregister a hook callback."""
        if hook_name in self._hooks:
            try:
                self._hooks[hook_name].remove(callback)
                self.logger.debug("Unregistered hook '%s'", hook_name)
            except ValueError:
                pass

    async def emit_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """Emit a hook and collect results."""
        results = []
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        result = await callback(*args, **kwargs)
                    else:
                        result = callback(*args, **kwargs)
                    results.append(result)
                except Exception:
                    self.logger.exception("Hook '%s' failed", hook_name)
        return results

    def add_dependency(self, dependency: str) -> None:
        """Add a plugin dependency."""
        if dependency not in self._dependencies:
            self._dependencies.append(dependency)

    def has_dependency(self, dependency: str) -> bool:
        """Check if plugin has a dependency."""
        return dependency in self._dependencies


class PluginManager:
    """Manages plugin lifecycle and communication."""

    def __init__(self) -> None:
        """Initialize plugin manager."""
        self.plugins: dict[str, Plugin] = {}
        self.plugin_info: dict[str, PluginInfo] = {}
        self.global_hooks: dict[str, list[Callable]] = {}
        self.logger = get_logger(__name__)

    async def load_plugin(
        self,
        plugin_class: type[Plugin],
        config: dict[str, Any] | None = None,
    ) -> str:
        """Load a plugin.

        Args:
            plugin_class: Plugin class to load
            config: Plugin configuration

        Returns:
            Plugin name
        """
        plugin = plugin_class(name=plugin_class.__name__)
        plugin_name = plugin.name

        if plugin_name in self.plugins:
            msg = f"Plugin '{plugin_name}' is already loaded"
            raise PluginError(msg)

        try:
            plugin.state = PluginState.LOADING
            self.logger.info("Loading plugin: %s", plugin_name)

            # Set configuration if provided
            if config:
                for key, value in config.items():
                    setattr(plugin, key, value)

            # Initialize plugin
            await plugin.initialize()

            # Register global hooks
            for hook_name, callbacks in plugin._hooks.items():  # noqa: SLF001
                if hook_name not in self.global_hooks:
                    self.global_hooks[hook_name] = []
                self.global_hooks[hook_name].extend(callbacks)

            # Store plugin
            self.plugins[plugin_name] = plugin
            self.plugin_info[plugin_name] = plugin.get_info()
            plugin.state = PluginState.LOADED

            self.logger.info("Plugin '%s' loaded successfully", plugin_name)
        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error = str(e)
            self.logger.exception("Failed to load plugin '%s'", plugin_name)
            msg = f"Failed to load plugin '{plugin_name}': {e}"
            raise PluginError(msg) from e
        else:
            return plugin_name

    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin.

        Args:
            plugin_name: Name of plugin to unload
        """
        if plugin_name not in self.plugins:
            msg = f"Plugin '{plugin_name}' is not loaded"
            raise PluginError(msg)

        plugin = self.plugins[plugin_name]

        try:
            # Stop plugin if running
            if plugin.state == PluginState.RUNNING:
                await self.stop_plugin(plugin_name)

            # Cleanup plugin
            await plugin.cleanup()

            # Remove global hooks
            for hook_name, callbacks in plugin._hooks.items():  # noqa: SLF001
                if hook_name in self.global_hooks:
                    for callback in callbacks:
                        with contextlib.suppress(ValueError):
                            self.global_hooks[hook_name].remove(callback)

            # Remove plugin
            del self.plugins[plugin_name]
            del self.plugin_info[plugin_name]
            plugin.state = PluginState.UNLOADED

            self.logger.info("Plugin '%s' unloaded successfully", plugin_name)

        except Exception as e:
            self.logger.exception("Failed to unload plugin '%s'", plugin_name)
            msg = f"Failed to unload plugin '{plugin_name}': {e}"
            raise PluginError(msg) from e

    async def start_plugin(self, plugin_name: str) -> None:
        """Start a plugin.

        Args:
            plugin_name: Name of plugin to start
        """
        if plugin_name not in self.plugins:
            msg = f"Plugin '{plugin_name}' is not loaded"
            raise PluginError(msg)

        plugin = self.plugins[plugin_name]

        if plugin.state != PluginState.LOADED:
            msg = f"Plugin '{plugin_name}' is not in loaded state"
            raise PluginError(msg)

        try:
            plugin.state = PluginState.STARTING
            await plugin.start()
            plugin.state = PluginState.RUNNING
            self.logger.info("Plugin '%s' started successfully", plugin_name)

        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error = str(e)
            self.logger.exception("Failed to start plugin '%s'", plugin_name)
            msg = f"Failed to start plugin '{plugin_name}': {e}"
            raise PluginError(msg) from e

    async def stop_plugin(self, plugin_name: str) -> None:
        """Stop a plugin.

        Args:
            plugin_name: Name of plugin to stop
        """
        if plugin_name not in self.plugins:
            msg = f"Plugin '{plugin_name}' is not loaded"
            raise PluginError(msg)

        plugin = self.plugins[plugin_name]

        if plugin.state != PluginState.RUNNING:
            msg = f"Plugin '{plugin_name}' is not running"
            raise PluginError(msg)

        try:
            plugin.state = PluginState.STOPPING
            await plugin.stop()
            plugin.state = PluginState.STOPPED
            self.logger.info("Plugin '%s' stopped successfully", plugin_name)

        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error = str(e)
            self.logger.exception("Failed to stop plugin '%s'", plugin_name)
            msg = f"Failed to stop plugin '{plugin_name}': {e}"
            raise PluginError(msg) from e

    async def emit_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """Emit a global hook.

        Args:
            hook_name: Name of hook to emit
            *args: Hook arguments
            **kwargs: Hook keyword arguments

        Returns:
            List of hook results
        """
        results = []
        if hook_name in self.global_hooks:
            for callback in self.global_hooks[hook_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        result = await callback(*args, **kwargs)
                    else:
                        result = callback(*args, **kwargs)
                    results.append(result)
                except Exception:
                    self.logger.exception("Global hook '%s' failed", hook_name)
        return results

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)

    def get_plugin_info(self, plugin_name: str) -> PluginInfo | None:
        """Get plugin information."""
        return self.plugin_info.get(plugin_name)

    def list_plugins(self) -> list[PluginInfo]:
        """List all loaded plugins."""
        return list(self.plugin_info.values())

    def get_plugin_dependencies(self, plugin_name: str) -> list[str]:
        """Get plugin dependencies."""
        if plugin_name in self.plugin_info:
            return self.plugin_info[plugin_name].dependencies
        return []

    async def load_plugin_from_module(
        self,
        module_path: str,
        plugin_class_name: str = "Plugin",
        config: dict[str, Any] | None = None,
    ) -> str:
        """Load a plugin from a module.

        Args:
            module_path: Path to plugin module
            plugin_class_name: Name of plugin class
            config: Plugin configuration

        Returns:
            Plugin name
        """
        try:
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, plugin_class_name)

            if not issubclass(plugin_class, Plugin):
                msg = f"Class '{plugin_class_name}' is not a Plugin"
                raise PluginError(msg)

            return await self.load_plugin(plugin_class, config)

        except Exception as e:
            self.logger.exception(
                "Failed to load plugin from module '%s'",
                module_path,
            )
            msg = f"Failed to load plugin from module '{module_path}': {e}"
            raise PluginError(msg) from e

    async def shutdown(self) -> None:
        """Shutdown all plugins."""
        self.logger.info("Shutting down plugin manager")

        # Stop all running plugins
        for plugin_name in list(self.plugins.keys()):
            try:
                if self.plugins[plugin_name].state == PluginState.RUNNING:
                    await self.stop_plugin(plugin_name)
                await self.unload_plugin(plugin_name)
            except Exception:
                self.logger.exception(
                    "Error shutting down plugin '%s'",
                    plugin_name,
                )

        self.logger.info("Plugin manager shutdown complete")
