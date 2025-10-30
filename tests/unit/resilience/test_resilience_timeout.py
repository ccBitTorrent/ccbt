"""Tests for resilience timeout functionality."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.resilience]

from ccbt.utils.resilience import with_timeout, with_retry, CircuitBreaker, RateLimiter


class TestResilienceTimeout:
    """Test cases for resilience timeout functionality."""

    def test_sync_function_timeout_success(self):
        """Test synchronous function with timeout - success case."""
        @with_timeout(1.0)
        def sync_function():
            return "success"

        result = sync_function()
        assert result == "success"

    def test_sync_function_timeout_failure(self):
        """Test synchronous function with timeout - timeout case."""
        @with_timeout(0.1)
        def slow_sync_function():
            time.sleep(0.2)  # Longer than timeout
            return "should_not_reach_here"

        with pytest.raises(TimeoutError, match="Operation timed out after 0.1 seconds"):
            slow_sync_function()

    def test_sync_function_timeout_exception(self):
        """Test synchronous function with timeout - exception case."""
        @with_timeout(1.0)
        def failing_sync_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_sync_function()

    def test_sync_function_timeout_threading(self):
        """Test that synchronous timeout uses threading correctly."""
        @with_timeout(0.1)
        def sync_function():
            # This should run in a separate thread
            assert threading.current_thread() != threading.main_thread()
            return "thread_success"

        result = sync_function()
        assert result == "thread_success"

    @pytest.mark.asyncio
    async def test_async_function_timeout_success(self):
        """Test asynchronous function with timeout - success case."""
        @with_timeout(1.0)
        async def async_function():
            await asyncio.sleep(0.1)
            return "async_success"

        result = await async_function()
        assert result == "async_success"

    @pytest.mark.asyncio
    async def test_async_function_timeout_failure(self):
        """Test asynchronous function with timeout - timeout case."""
        @with_timeout(0.1)
        async def slow_async_function():
            await asyncio.sleep(0.2)  # Longer than timeout
            return "should_not_reach_here"

        with pytest.raises(TimeoutError, match="Operation timed out after 0.1 seconds"):
            await slow_async_function()

    @pytest.mark.asyncio
    async def test_async_function_timeout_exception(self):
        """Test asynchronous function with timeout - exception case."""
        @with_timeout(1.0)
        async def failing_async_function():
            raise ValueError("Async test error")

        with pytest.raises(ValueError, match="Async test error"):
            await failing_async_function()

    def test_timeout_decorator_preserves_function_metadata(self):
        """Test that timeout decorator preserves function metadata."""
        @with_timeout(1.0)
        def test_function():
            """Test function docstring."""
            return "test"

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_timeout_with_different_timeout_values(self):
        """Test timeout decorator with different timeout values."""
        @with_timeout(0.05)
        def quick_function():
            return "quick"

        @with_timeout(1.0)
        def slow_function():
            time.sleep(0.1)
            return "slow"

        # Both should succeed
        assert quick_function() == "quick"
        assert slow_function() == "slow"

    def test_timeout_with_zero_timeout(self):
        """Test timeout decorator with zero timeout."""
        @with_timeout(0.0)
        def instant_function():
            return "instant"

        # Should still work for very fast functions
        result = instant_function()
        assert result == "instant"

    def test_timeout_with_very_small_timeout(self):
        """Test timeout decorator with very small timeout."""
        @with_timeout(0.001)
        def micro_function():
            return "micro"

        # Should work for very fast functions
        result = micro_function()
        assert result == "micro"

    def test_timeout_thread_cleanup(self):
        """Test that timeout threads are properly cleaned up."""
        initial_thread_count = threading.active_count()

        @with_timeout(0.1)
        def test_function():
            return "test"

        # Run function multiple times
        for _ in range(5):
            result = test_function()
            assert result == "test"

        # Thread count should not grow significantly
        # Allow some tolerance for other threads
        final_thread_count = threading.active_count()
        assert final_thread_count <= initial_thread_count + 2

    def test_timeout_with_complex_return_value(self):
        """Test timeout decorator with complex return values."""
        @with_timeout(1.0)
        def complex_function():
            return {
                "data": [1, 2, 3],
                "nested": {"key": "value"},
                "tuple": (1, 2, 3),
            }

        result = complex_function()
        assert result["data"] == [1, 2, 3]
        assert result["nested"]["key"] == "value"
        assert result["tuple"] == (1, 2, 3)

    def test_timeout_with_side_effects(self):
        """Test timeout decorator preserves side effects."""
        side_effect_list = []

        @with_timeout(1.0)
        def function_with_side_effects():
            side_effect_list.append("executed")
            return len(side_effect_list)

        result = function_with_side_effects()
        assert result == 1
        assert side_effect_list == ["executed"]

    def test_timeout_with_nested_functions(self):
        """Test timeout decorator with nested function calls."""
        @with_timeout(1.0)
        def outer_function():
            @with_timeout(0.5)
            def inner_function():
                return "inner_success"
            
            return inner_function()

        result = outer_function()
        assert result == "inner_success"
