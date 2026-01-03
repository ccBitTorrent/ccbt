"""Pytest hooks for per-test timeout management.

This module provides hooks to apply different timeout values based on test markers,
allowing simple tests to have shorter timeouts while complex tests can have longer ones.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    """Modify test items to apply timeout markers based on test markers.
    
    This hook applies timeout values based on timeout marker categories:
    - timeout_fast: 5 seconds
    - timeout_medium: 30 seconds
    - timeout_long: 300 seconds
    
    Tests can also use @pytest.mark.timeout(value) directly for custom timeouts.
    """
    timeout_fast = pytest.mark.timeout(5)
    timeout_medium = pytest.mark.timeout(30)
    timeout_long = pytest.mark.timeout(300)
    
    for item in items:
        # Check for explicit timeout marker first (highest priority)
        if item.get_closest_marker("timeout"):
            continue  # Already has explicit timeout, don't override
        
        # Apply timeout based on category markers
        if item.get_closest_marker("timeout_fast"):
            item.add_marker(timeout_fast)
        elif item.get_closest_marker("timeout_medium"):
            item.add_marker(timeout_medium)
        elif item.get_closest_marker("timeout_long"):
            item.add_marker(timeout_long)
        # If no timeout marker, use global timeout (300s from pytest.ini)






