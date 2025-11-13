"""Tests for plugin manager singleton.

Covers:
- get_plugin_manager() function
- Singleton behavior
- PluginManager.get_plugin() method
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.plugins]


def test_get_plugin_manager_returns_singleton():
    """Test that get_plugin_manager returns the same instance."""
    from ccbt.plugins import get_plugin_manager

    manager1 = get_plugin_manager()
    manager2 = get_plugin_manager()

    assert manager1 is manager2
    assert isinstance(manager1, type(manager2))


def test_get_plugin_manager_initializes_once():
    """Test that PluginManager is only initialized once."""
    from ccbt.plugins import get_plugin_manager
    from ccbt.plugins.base import PluginManager

    # Clear any existing instance
    import ccbt.plugins.base as base_module
    base_module._plugin_manager = None  # type: ignore[attr-defined]

    manager1 = get_plugin_manager()
    assert isinstance(manager1, PluginManager)

    manager2 = get_plugin_manager()
    assert manager1 is manager2


def test_plugin_manager_get_plugin():
    """Test PluginManager.get_plugin method."""
    from ccbt.plugins import get_plugin_manager
    from ccbt.plugins.base import Plugin

    manager = get_plugin_manager()

    # Test with non-existent plugin
    result = manager.get_plugin("nonexistent")
    assert result is None

    # Test with existing plugin
    mock_plugin = MagicMock(spec=Plugin)
    mock_plugin.name = "test_plugin"
    manager.plugins["test_plugin"] = mock_plugin

    result = manager.get_plugin("test_plugin")
    assert result == mock_plugin


def test_plugin_manager_get_plugin_variations():
    """Test PluginManager.get_plugin with different name variations."""
    from ccbt.plugins import get_plugin_manager
    from ccbt.plugins.base import Plugin

    manager = get_plugin_manager()

    # Create mock plugin with different name variations
    mock_plugin = MagicMock(spec=Plugin)
    mock_plugin.name = "metrics_plugin"
    mock_plugin.get_aggregates = MagicMock(return_value=[])
    mock_plugin.collector = MagicMock()
    manager.plugins["metrics_plugin"] = mock_plugin

    # Test different name variations
    assert manager.get_plugin("metrics_plugin") == mock_plugin
    assert manager.get_plugin("MetricsPlugin") is None  # Case sensitive
    assert manager.get_plugin("MetricsCollector") is None


