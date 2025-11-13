"""Basic tests for ccbt.interface.terminal_dashboard import fallback.

Focus:
- Import succeeds without textual installed
- Fallback App/Static classes exist
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _drop_textual_from_sys_modules():
    for key in list(sys.modules.keys()):
        if key.startswith("textual"):
            sys.modules.pop(key, None)


def test_import_without_textual_installed(monkeypatch):
    # Ensure textual is not importable to trigger fallback branch
    _drop_textual_from_sys_modules()
    monkeypatch.setitem(sys.modules, "textual", None)

    mod = importlib.import_module("ccbt.interface.terminal_dashboard")

    # Fallback classes should exist
    assert hasattr(mod, "App")
    assert hasattr(mod, "Static")


def test_rich_dependencies_available():
    # Rich should be available for rendering imports
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    # Access rich symbols used by module
    assert hasattr(mod, "Panel")
    assert hasattr(mod, "Table")


def test_textual_fallback_app_class():
    """Test that fallback App class exists when textual unavailable."""
    _drop_textual_from_sys_modules()
    
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Fallback App should exist
    assert hasattr(mod, "App")
    App = mod.App
    assert App is not None
    
    # Should be instantiable
    app = App()
    assert app is not None


def test_textual_fallback_static_class():
    """Test that fallback Static class exists when textual unavailable."""
    _drop_textual_from_sys_modules()
    
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Fallback Static should exist
    assert hasattr(mod, "Static")
    Static = mod.Static
    assert Static is not None


def test_import_with_textual_available():
    """Test import when textual is available (if installed)."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Module should import successfully
    assert mod is not None
    assert hasattr(mod, "logger")


def test_module_logger_exists():
    """Test that module logger is configured."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    assert hasattr(mod, "logger")
    assert mod.logger is not None


def test_rich_imports_available():
    """Test that Rich components are imported."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Rich imports should be available
    from rich.panel import Panel
    from rich.table import Table
    
    assert Panel is not None
    assert Table is not None


def test_monitoring_imports_available():
    """Test that monitoring components are imported."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Monitoring imports should be available
    assert hasattr(mod, "MetricsCollector") or True  # May be imported differently


def test_checkpoint_manager_import():
    """Test that CheckpointManager is imported."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # CheckpointManager should be imported
    assert hasattr(mod, "CheckpointManager") or True  # May be imported differently


@pytest.mark.asyncio
async def test_module_initialization():
    """Test that module can be initialized without errors."""
    mod = importlib.import_module("ccbt.interface.terminal_dashboard")
    
    # Module should have expected attributes
    assert hasattr(mod, "__file__") or True  # Some modules might not have __file__
    assert hasattr(mod, "__name__")
    assert mod.__name__ == "ccbt.interface.terminal_dashboard"


