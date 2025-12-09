"""Unit tests for verbosity system.

Tests the VerbosityManager and verbosity level handling.
"""

from __future__ import annotations

import logging

import pytest

from ccbt.cli.verbosity import VerbosityLevel, VerbosityManager, get_verbosity_from_ctx

pytestmark = [pytest.mark.cli, pytest.mark.unit]


class TestVerbosityLevel:
    """Test VerbosityLevel enum."""

    def test_verbosity_level_values(self):
        """Test that verbosity levels have correct integer values."""
        assert VerbosityLevel.QUIET == 0
        assert VerbosityLevel.NORMAL == 1
        assert VerbosityLevel.VERBOSE == 2
        assert VerbosityLevel.DEBUG == 3
        assert VerbosityLevel.TRACE == 4

    def test_verbosity_level_comparison(self):
        """Test verbosity level comparisons."""
        assert VerbosityLevel.QUIET < VerbosityLevel.NORMAL
        assert VerbosityLevel.NORMAL < VerbosityLevel.VERBOSE
        assert VerbosityLevel.VERBOSE < VerbosityLevel.DEBUG
        assert VerbosityLevel.DEBUG < VerbosityLevel.TRACE


class TestVerbosityManager:
    """Test VerbosityManager class."""

    def test_from_count_default(self):
        """Test creating VerbosityManager with default count."""
        vm = VerbosityManager.from_count(0)
        assert vm.verbosity_count == 0
        assert vm.level == VerbosityLevel.NORMAL
        assert vm.logging_level == logging.INFO

    def test_from_count_verbose(self):
        """Test creating VerbosityManager with -v."""
        vm = VerbosityManager.from_count(1)
        assert vm.verbosity_count == 1
        assert vm.level == VerbosityLevel.VERBOSE
        assert vm.logging_level == logging.INFO

    def test_from_count_debug(self):
        """Test creating VerbosityManager with -vv."""
        vm = VerbosityManager.from_count(2)
        assert vm.verbosity_count == 2
        assert vm.level == VerbosityLevel.DEBUG
        assert vm.logging_level == logging.DEBUG

    def test_from_count_trace(self):
        """Test creating VerbosityManager with -vvv."""
        vm = VerbosityManager.from_count(3)
        assert vm.verbosity_count == 3
        assert vm.level == VerbosityLevel.TRACE
        assert vm.logging_level == logging.DEBUG

    def test_from_count_clamped(self):
        """Test that verbosity count is clamped to valid range."""
        vm_negative = VerbosityManager.from_count(-1)
        assert vm_negative.verbosity_count == 0

        vm_high = VerbosityManager.from_count(10)
        assert vm_high.verbosity_count == 3

    def test_should_log(self):
        """Test should_log method."""
        vm_normal = VerbosityManager.from_count(0)
        assert vm_normal.should_log(logging.ERROR)
        assert vm_normal.should_log(logging.WARNING)
        assert vm_normal.should_log(logging.INFO)
        assert not vm_normal.should_log(logging.DEBUG)

        vm_debug = VerbosityManager.from_count(2)
        assert vm_debug.should_log(logging.ERROR)
        assert vm_debug.should_log(logging.WARNING)
        assert vm_debug.should_log(logging.INFO)
        assert vm_debug.should_log(logging.DEBUG)

    def test_should_show_stack_trace(self):
        """Test should_show_stack_trace method."""
        vm_normal = VerbosityManager.from_count(0)
        assert not vm_normal.should_show_stack_trace()

        vm_trace = VerbosityManager.from_count(3)
        assert vm_trace.should_show_stack_trace()

    def test_is_verbose(self):
        """Test is_verbose method."""
        vm_normal = VerbosityManager.from_count(0)
        assert not vm_normal.is_verbose()

        vm_verbose = VerbosityManager.from_count(1)
        assert vm_verbose.is_verbose()

        vm_debug = VerbosityManager.from_count(2)
        assert vm_debug.is_verbose()

    def test_is_debug(self):
        """Test is_debug method."""
        vm_normal = VerbosityManager.from_count(0)
        assert not vm_normal.is_debug()

        vm_verbose = VerbosityManager.from_count(1)
        assert not vm_verbose.is_debug()

        vm_debug = VerbosityManager.from_count(2)
        assert vm_debug.is_debug()

        vm_trace = VerbosityManager.from_count(3)
        assert vm_trace.is_debug()

    def test_is_trace(self):
        """Test is_trace method."""
        vm_normal = VerbosityManager.from_count(0)
        assert not vm_normal.is_trace()

        vm_debug = VerbosityManager.from_count(2)
        assert not vm_debug.is_trace()

        vm_trace = VerbosityManager.from_count(3)
        assert vm_trace.is_trace()

    def test_get_logging_level(self):
        """Test get_logging_level method."""
        vm_normal = VerbosityManager.from_count(0)
        assert vm_normal.get_logging_level() == logging.INFO

        vm_debug = VerbosityManager.from_count(2)
        assert vm_debug.get_logging_level() == logging.DEBUG


class TestGetVerbosityFromCtx:
    """Test get_verbosity_from_ctx helper function."""

    def test_get_verbosity_from_ctx_with_verbosity(self):
        """Test getting verbosity from context with verbosity key."""
        ctx = {"verbosity": 2}
        vm = get_verbosity_from_ctx(ctx)
        assert vm.verbosity_count == 2
        assert vm.level == VerbosityLevel.DEBUG

    def test_get_verbosity_from_ctx_without_verbosity(self):
        """Test getting verbosity from context without verbosity key."""
        ctx = {}
        vm = get_verbosity_from_ctx(ctx)
        assert vm.verbosity_count == 0
        assert vm.level == VerbosityLevel.NORMAL

    def test_get_verbosity_from_ctx_none(self):
        """Test getting verbosity from None context."""
        vm = get_verbosity_from_ctx(None)
        assert vm.verbosity_count == 0
        assert vm.level == VerbosityLevel.NORMAL

    def test_get_verbosity_from_ctx_various_levels(self):
        """Test getting verbosity for various levels."""
        for count in range(4):
            ctx = {"verbosity": count}
            vm = get_verbosity_from_ctx(ctx)
            assert vm.verbosity_count == count


class TestVerbosityIntegration:
    """Integration tests for verbosity system."""

    def test_verbosity_level_mapping(self):
        """Test that verbosity levels map correctly to logging levels."""
        mappings = [
            (0, VerbosityLevel.NORMAL, logging.INFO),
            (1, VerbosityLevel.VERBOSE, logging.INFO),
            (2, VerbosityLevel.DEBUG, logging.DEBUG),
            (3, VerbosityLevel.TRACE, logging.DEBUG),
        ]

        for count, expected_level, expected_logging in mappings:
            vm = VerbosityManager.from_count(count)
            assert vm.level == expected_level
            assert vm.logging_level == expected_logging

    def test_verbosity_filtering(self):
        """Test that verbosity correctly filters log levels."""
        vm_normal = VerbosityManager.from_count(0)
        assert vm_normal.should_log(logging.ERROR)
        assert vm_normal.should_log(logging.WARNING)
        assert vm_normal.should_log(logging.INFO)
        assert not vm_normal.should_log(logging.DEBUG)

        vm_debug = VerbosityManager.from_count(2)
        assert vm_debug.should_log(logging.ERROR)
        assert vm_debug.should_log(logging.WARNING)
        assert vm_debug.should_log(logging.INFO)
        assert vm_debug.should_log(logging.DEBUG)





















































