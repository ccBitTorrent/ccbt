"""Comprehensive tests for ccbt.plugins.base to achieve 95%+ coverage.

Covers missing lines:
- Plugin hook operations (lines 104-107, 111-116, 120-131)
- Plugin dependency operations (lines 135-136, 140)
- PluginManager load_plugin operations (lines 171-172, 180-181, 188-190, 198-203)
- PluginManager unload_plugin operations (lines 214-215, 222, 229-232, 241-244)
- PluginManager start_plugin operations (lines 253-254, 259-260, 268-273)
- PluginManager stop_plugin operations (lines 282-283, 288-289, 297-302)
- PluginManager emit_hook operations (lines 315-326)
- PluginManager get_plugin_dependencies (lines 342-344)
- PluginManager load_plugin_from_module (lines 362-378)
- PluginManager shutdown (lines 388, 390-391)
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.plugins.base import (
    Plugin,
    PluginError,
    PluginInfo,
    PluginManager,
    PluginState,
)

pytestmark = [pytest.mark.unit]


class TestPluginClass(Plugin):
    """Test plugin implementation."""

    __test__ = False  # Prevent pytest from collecting this as a test class

    async def initialize(self) -> None:
        """Initialize the plugin."""
        pass

    async def start(self) -> None:
        """Start the plugin."""
        pass

    async def stop(self) -> None:
        """Stop the plugin."""
        pass

    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass


class TestPluginHookOperations:
    """Test Plugin hook operations."""

    def test_register_hook_new_hook_name(self):
        """Test register_hook when hook_name not in _hooks (lines 104-107)."""
        plugin = TestPluginClass("test_plugin")
        callback = Mock()

        # Register hook for first time - should create list
        plugin.register_hook("test_hook", callback)
        assert "test_hook" in plugin._hooks
        assert callback in plugin._hooks["test_hook"]

        # Register another callback for same hook
        callback2 = Mock()
        plugin.register_hook("test_hook", callback2)
        assert len(plugin._hooks["test_hook"]) == 2

    def test_unregister_hook_valueerror_handling(self):
        """Test unregister_hook with ValueError handling (lines 111-116)."""
        plugin = TestPluginClass("test_plugin")
        callback = Mock()
        callback2 = Mock()

        # Register hook
        plugin.register_hook("test_hook", callback)

        # Unregister non-existent callback - should not raise (ValueError suppressed)
        plugin.unregister_hook("test_hook", callback2)
        assert callback in plugin._hooks["test_hook"]

        # Unregister existing callback
        plugin.unregister_hook("test_hook", callback)
        assert callback not in plugin._hooks["test_hook"]

        # Unregister from non-existent hook - should not raise
        plugin.unregister_hook("non_existent_hook", callback)

    @pytest.mark.asyncio
    async def test_emit_hook_async_and_sync_callbacks(self):
        """Test emit_hook with async and sync callbacks including exceptions (lines 120-131)."""
        plugin = TestPluginClass("test_plugin")

        # Test with sync callback
        sync_callback = Mock(return_value="sync_result")
        plugin.register_hook("test_hook", sync_callback)

        results = await plugin.emit_hook("test_hook", arg1="value1")
        assert results == ["sync_result"]
        sync_callback.assert_called_once_with(arg1="value1")

        # Test with async callback
        async_callback = AsyncMock(return_value="async_result")
        plugin.register_hook("test_hook", async_callback)

        results = await plugin.emit_hook("test_hook", arg1="value1")
        assert "async_result" in results

        # Test with callback that raises exception
        failing_callback = Mock(side_effect=Exception("Callback error"))
        plugin.register_hook("test_hook", failing_callback)

        # Should not raise, exception should be caught and logged
        results = await plugin.emit_hook("test_hook")
        # Failing callback should still be called
        failing_callback.assert_called_once()

        # Test with non-existent hook
        results = await plugin.emit_hook("non_existent_hook")
        assert results == []


class TestPluginDependencyOperations:
    """Test Plugin dependency operations."""

    def test_add_dependency_edge_cases(self):
        """Test add_dependency edge cases (line 135-136)."""
        plugin = TestPluginClass("test_plugin")

        # Add dependency
        plugin.add_dependency("dep1")
        assert "dep1" in plugin._dependencies

        # Add same dependency again - should not duplicate
        plugin.add_dependency("dep1")
        assert plugin._dependencies.count("dep1") == 1

        # Add multiple dependencies
        plugin.add_dependency("dep2")
        plugin.add_dependency("dep3")
        assert len(plugin._dependencies) == 3

    def test_has_dependency(self):
        """Test has_dependency (line 140)."""
        plugin = TestPluginClass("test_plugin")

        # No dependencies initially
        assert not plugin.has_dependency("dep1")

        # Add dependency
        plugin.add_dependency("dep1")
        assert plugin.has_dependency("dep1")
        assert not plugin.has_dependency("dep2")


class TestPluginManagerLoadPlugin:
    """Test PluginManager load_plugin operations."""

    @pytest.mark.asyncio
    async def test_load_plugin_already_loaded(self):
        """Test load_plugin with already loaded plugin (lines 171-172)."""
        manager = PluginManager()
        plugin_class = TestPluginClass

        # Load plugin first time
        plugin_name = await manager.load_plugin(plugin_class)
        assert plugin_name == "TestPluginClass"

        # Try to load again - should raise PluginError
        with pytest.raises(PluginError, match="already loaded"):
            await manager.load_plugin(plugin_class)

    @pytest.mark.asyncio
    async def test_load_plugin_config_assignment(self):
        """Test load_plugin config assignment (lines 180-181)."""
        manager = PluginManager()
        plugin_class = TestPluginClass
        config = {"custom_param": "value", "another_param": 123}

        plugin_name = await manager.load_plugin(plugin_class, config=config)

        plugin = manager.get_plugin(plugin_name)
        assert plugin.custom_param == "value"
        assert plugin.another_param == 123

    @pytest.mark.asyncio
    async def test_load_plugin_global_hook_registration(self):
        """Test load_plugin global hook registration (lines 188-190)."""
        manager = PluginManager()

        # Create a plugin class that registers hooks in initialize
        class HookPlugin(TestPluginClass):
            async def initialize(self) -> None:
                callback1 = Mock()
                callback2 = Mock()
                self.register_hook("hook1", callback1)
                self.register_hook("hook2", callback2)

        # Load plugin - hooks will be registered during initialization
        plugin_name = await manager.load_plugin(HookPlugin)

        # Check global hooks
        assert "hook1" in manager.global_hooks
        assert "hook2" in manager.global_hooks
        assert len(manager.global_hooks["hook1"]) > 0
        assert len(manager.global_hooks["hook2"]) > 0

    @pytest.mark.asyncio
    async def test_load_plugin_exception_handling_and_error_state(self):
        """Test load_plugin exception handling and error state (lines 198-203)."""
        manager = PluginManager()

        class FailingPlugin(Plugin):
            async def initialize(self) -> None:
                raise Exception("Initialization failed")

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        # Load plugin should raise PluginError
        with pytest.raises(PluginError, match="Failed to load plugin"):
            await manager.load_plugin(FailingPlugin)

        # Plugin should be in ERROR state (but not stored since exception raised)
        # Let's test with a plugin that partially fails after being added
        class PartialFailingPlugin(Plugin):
            async def initialize(self) -> None:
                # Add hooks first
                self.register_hook("hook1", Mock())
                # Then fail
                raise Exception("Partial failure")

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        # Should raise and not store plugin
        with pytest.raises(PluginError):
            await manager.load_plugin(PartialFailingPlugin)

        assert "PartialFailingPlugin" not in manager.plugins


class TestPluginManagerUnloadPlugin:
    """Test PluginManager unload_plugin operations."""

    @pytest.mark.asyncio
    async def test_unload_plugin_not_loaded(self):
        """Test unload_plugin when plugin not loaded (lines 214-215)."""
        manager = PluginManager()

        # Try to unload non-existent plugin
        with pytest.raises(PluginError, match="is not loaded"):
            await manager.unload_plugin("non_existent_plugin")

    @pytest.mark.asyncio
    async def test_unload_plugin_stop_if_running(self):
        """Test unload_plugin stop plugin if running (line 222)."""
        manager = PluginManager()

        # Load and start plugin
        plugin_name = await manager.load_plugin(TestPluginClass)
        await manager.start_plugin(plugin_name)

        # Verify plugin is running
        plugin = manager.get_plugin(plugin_name)
        assert plugin.state == PluginState.RUNNING

        # Unload should stop plugin first
        await manager.unload_plugin(plugin_name)

        # Plugin should be unloaded
        assert plugin_name not in manager.plugins

    @pytest.mark.asyncio
    async def test_unload_plugin_global_hook_removal_with_suppress(self):
        """Test unload_plugin global hook removal with suppress (lines 229-232)."""
        manager = PluginManager()

        # Create a plugin class that registers hooks in initialize
        callback = Mock()

        class HookPlugin(TestPluginClass):
            async def initialize(self) -> None:
                self.register_hook("test_hook", callback)

        plugin_name = await manager.load_plugin(HookPlugin)

        # Verify hooks are in global_hooks
        assert "test_hook" in manager.global_hooks
        assert callback in manager.global_hooks["test_hook"]

        # Unload plugin
        await manager.unload_plugin(plugin_name)

        # Hooks should be removed
        # Note: if suppress works, removing non-existent callback should not raise
        assert "test_hook" not in manager.global_hooks or callback not in manager.global_hooks.get("test_hook", [])

    @pytest.mark.asyncio
    async def test_unload_plugin_exception_handling(self):
        """Test unload_plugin exception handling (lines 241-244)."""
        manager = PluginManager()

        class CleanupFailingPlugin(Plugin):
            async def initialize(self) -> None:
                pass

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def cleanup(self) -> None:
                raise Exception("Cleanup failed")

        plugin_name = await manager.load_plugin(CleanupFailingPlugin)

        # Unload should raise PluginError
        with pytest.raises(PluginError, match="Failed to unload plugin"):
            await manager.unload_plugin(plugin_name)


class TestPluginManagerStartPlugin:
    """Test PluginManager start_plugin operations."""

    @pytest.mark.asyncio
    async def test_start_plugin_not_loaded(self):
        """Test start_plugin with plugin not loaded (lines 253-254)."""
        manager = PluginManager()

        # Try to start non-existent plugin
        with pytest.raises(PluginError, match="is not loaded"):
            await manager.start_plugin("non_existent_plugin")

    @pytest.mark.asyncio
    async def test_start_plugin_invalid_state(self):
        """Test start_plugin with invalid state (lines 259-260)."""
        manager = PluginManager()

        # Load plugin but don't start
        plugin_name = await manager.load_plugin(TestPluginClass)

        # Try to start when already running (after starting once)
        await manager.start_plugin(plugin_name)

        # Plugin state should be RUNNING, try to start again
        # This should fail because plugin is not in LOADED state
        plugin = manager.get_plugin(plugin_name)
        plugin.state = PluginState.ERROR  # Set to invalid state

        with pytest.raises(PluginError, match="is not in loaded state"):
            await manager.start_plugin(plugin_name)

    @pytest.mark.asyncio
    async def test_start_plugin_exception_handling(self):
        """Test start_plugin exception handling (lines 268-273)."""
        manager = PluginManager()

        class StartFailingPlugin(Plugin):
            async def initialize(self) -> None:
                pass

            async def start(self) -> None:
                raise Exception("Start failed")

            async def stop(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        plugin_name = await manager.load_plugin(StartFailingPlugin)

        # Start should raise PluginError
        with pytest.raises(PluginError, match="Failed to start plugin"):
            await manager.start_plugin(plugin_name)

        # Plugin should be in ERROR state
        plugin = manager.get_plugin(plugin_name)
        assert plugin.state == PluginState.ERROR
        assert plugin.error == "Start failed"


class TestPluginManagerStopPlugin:
    """Test PluginManager stop_plugin operations."""

    @pytest.mark.asyncio
    async def test_stop_plugin_not_loaded(self):
        """Test stop_plugin with plugin not loaded (lines 282-283)."""
        manager = PluginManager()

        # Try to stop non-existent plugin
        with pytest.raises(PluginError, match="is not loaded"):
            await manager.stop_plugin("non_existent_plugin")

    @pytest.mark.asyncio
    async def test_stop_plugin_invalid_state(self):
        """Test stop_plugin with invalid state (lines 288-289)."""
        manager = PluginManager()

        # Load plugin but don't start
        plugin_name = await manager.load_plugin(TestPluginClass)

        # Try to stop when not running
        with pytest.raises(PluginError, match="is not running"):
            await manager.stop_plugin(plugin_name)

    @pytest.mark.asyncio
    async def test_stop_plugin_exception_handling(self):
        """Test stop_plugin exception handling (lines 297-302)."""
        manager = PluginManager()

        class StopFailingPlugin(Plugin):
            async def initialize(self) -> None:
                pass

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                raise Exception("Stop failed")

            async def cleanup(self) -> None:
                pass

        plugin_name = await manager.load_plugin(StopFailingPlugin)
        await manager.start_plugin(plugin_name)

        # Stop should raise PluginError
        with pytest.raises(PluginError, match="Failed to stop plugin"):
            await manager.stop_plugin(plugin_name)

        # Plugin should be in ERROR state
        plugin = manager.get_plugin(plugin_name)
        assert plugin.state == PluginState.ERROR
        assert plugin.error == "Stop failed"


class TestPluginManagerEmitHook:
    """Test PluginManager emit_hook operations."""

    @pytest.mark.asyncio
    async def test_emit_hook_async_sync_callbacks_and_exceptions(self):
        """Test emit_hook with async/sync callbacks and exceptions (lines 315-326)."""
        manager = PluginManager()

        # Test with sync callback
        sync_callback = Mock(return_value="sync_result")
        manager.global_hooks["test_hook"] = [sync_callback]

        results = await manager.emit_hook("test_hook", arg1="value1")
        assert results == ["sync_result"]
        sync_callback.assert_called_once_with(arg1="value1")

        # Test with async callback
        async_callback = AsyncMock(return_value="async_result")
        manager.global_hooks["test_hook"].append(async_callback)

        results = await manager.emit_hook("test_hook", arg1="value1")
        assert "sync_result" in results
        assert "async_result" in results

        # Test with callback that raises exception
        failing_callback = Mock(side_effect=Exception("Callback error"))
        manager.global_hooks["test_hook"].append(failing_callback)

        # Should not raise, exception should be caught and logged
        results = await manager.emit_hook("test_hook")
        # Failing callback should still be called
        failing_callback.assert_called_once()

        # Test with non-existent hook
        results = await manager.emit_hook("non_existent_hook")
        assert results == []


class TestPluginManagerGetPluginDependencies:
    """Test PluginManager get_plugin_dependencies."""

    @pytest.mark.asyncio
    async def test_get_plugin_dependencies(self):
        """Test get_plugin_dependencies (lines 342-344)."""
        manager = PluginManager()

        # Plugin with no dependencies
        plugin_name = await manager.load_plugin(TestPluginClass)
        deps = manager.get_plugin_dependencies(plugin_name)
        assert deps == []

        # Plugin with dependencies
        class DepPlugin(TestPluginClass):
            async def initialize(self) -> None:
                self.add_dependency("dep1")
                self.add_dependency("dep2")

        # Unload first plugin to avoid conflicts
        await manager.unload_plugin(plugin_name)

        plugin_name2 = await manager.load_plugin(DepPlugin)
        deps = manager.get_plugin_dependencies(plugin_name2)
        assert "dep1" in deps
        assert "dep2" in deps

        # Non-existent plugin
        deps = manager.get_plugin_dependencies("non_existent")
        assert deps == []

    @pytest.mark.asyncio
    async def test_get_plugin_info(self):
        """Test get_plugin_info (line 334)."""
        manager = PluginManager()

        # Load a plugin
        plugin_name = await manager.load_plugin(TestPluginClass)

        # Get plugin info
        info = manager.get_plugin_info(plugin_name)
        assert info is not None
        assert info.name == plugin_name

        # Non-existent plugin
        info = manager.get_plugin_info("non_existent")
        assert info is None

    def test_list_plugins(self):
        """Test list_plugins (line 338)."""
        manager = PluginManager()

        # Empty list initially
        plugins = manager.list_plugins()
        assert plugins == []

        # Load some plugins and verify list
        async def load_and_check():
            plugin_name1 = await manager.load_plugin(TestPluginClass)
            plugins = manager.list_plugins()
            assert len(plugins) == 1
            assert any(p.name == plugin_name1 for p in plugins)

            # Unload and verify empty
            await manager.unload_plugin(plugin_name1)
            plugins = manager.list_plugins()
            assert len(plugins) == 0

        # Run async test
        import asyncio
        asyncio.run(load_and_check())


class TestPluginManagerLoadPluginFromModule:
    """Test PluginManager load_plugin_from_module."""

    @pytest.mark.asyncio
    async def test_load_plugin_from_module_invalid_class_and_exceptions(self):
        """Test load_plugin_from_module with invalid class and exceptions (lines 362-378)."""
        manager = PluginManager()

        # Test with non-existent module
        with pytest.raises(PluginError, match="Failed to load plugin from module"):
            await manager.load_plugin_from_module("non_existent.module")

        # Test with module that doesn't have Plugin class
        # The actual code uses getattr which will raise AttributeError
        with patch("importlib.import_module") as mock_import:
            # Create a module mock that raises AttributeError when accessing Plugin
            class MockModuleWithoutPlugin:
                def __getattr__(self, name):
                    if name == "Plugin":
                        raise AttributeError("Plugin")
                    return MagicMock()
            
            mock_import.return_value = MockModuleWithoutPlugin()
            
            # This will raise AttributeError when accessing Plugin, which gets caught
            # and re-raised as PluginError with "Failed to load plugin from module"
            with pytest.raises(PluginError, match="Failed to load plugin from module"):
                await manager.load_plugin_from_module("some.module")

        # Test with module that has non-Plugin class
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()

            class NotAPlugin:
                pass

            mock_module.Plugin = NotAPlugin
            mock_import.return_value = mock_module

            with pytest.raises(PluginError, match="is not a Plugin"):
                await manager.load_plugin_from_module("some.module", plugin_class_name="Plugin")

        # Test with valid module but exception during load
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.TestPluginClass = TestPluginClass
            mock_import.return_value = mock_module

            with patch.object(manager, "load_plugin", side_effect=Exception("Load error")):
                with pytest.raises(PluginError, match="Failed to load plugin from module"):
                    await manager.load_plugin_from_module("some.module", plugin_class_name="TestPluginClass")


class TestPluginManagerShutdown:
    """Test PluginManager shutdown operations."""

    @pytest.mark.asyncio
    async def test_shutdown_with_running_plugins_and_error_handling(self):
        """Test shutdown with running plugins and error handling (lines 388, 390-391)."""
        manager = PluginManager()

        # Load and start a plugin
        plugin_name = await manager.load_plugin(TestPluginClass)
        await manager.start_plugin(plugin_name)

        # Verify plugin is running
        plugin = manager.get_plugin(plugin_name)
        assert plugin.state == PluginState.RUNNING

        # Shutdown should stop and unload plugin
        await manager.shutdown()

        # Plugin should be unloaded
        assert plugin_name not in manager.plugins

        # Test with plugin that fails to stop
        class StopFailingPlugin(Plugin):
            async def initialize(self) -> None:
                pass

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                raise Exception("Stop failed")

            async def cleanup(self) -> None:
                pass

        manager2 = PluginManager()
        plugin_name2 = await manager2.load_plugin(StopFailingPlugin)
        await manager2.start_plugin(plugin_name2)

        # Shutdown should handle exception
        await manager2.shutdown()
        # Should complete without raising

        # Test with plugin that fails to unload
        class UnloadFailingPlugin(Plugin):
            async def initialize(self) -> None:
                pass

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def cleanup(self) -> None:
                raise Exception("Cleanup failed")

        manager3 = PluginManager()
        plugin_name3 = await manager3.load_plugin(UnloadFailingPlugin)
        await manager3.start_plugin(plugin_name3)

        # Shutdown should handle exception
        await manager3.shutdown()
        # Should complete without raising

