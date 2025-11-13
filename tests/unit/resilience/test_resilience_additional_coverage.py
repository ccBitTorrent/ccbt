"""Additional tests for resilience.py to increase coverage.

Covers missing paths:
- CircuitBreaker async_wrapper open state paths
- CircuitBreaker _on_success and _on_failure
- RateLimiter acquire return False path
- with_rate_limit async_wrapper await func path
- Decorator return paths
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.resilience]

from ccbt.utils.resilience import (
    CircuitBreaker,
    CircuitBreakerError,
    RateLimiter,
    with_rate_limit,
)


class TestCircuitBreakerAsyncWrapperOpenState:
    """Test CircuitBreaker async_wrapper open state paths (lines 220-225)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_open_raises_immediately(self):
        """Test CircuitBreaker async_wrapper - open state raises immediately (lines 223-225)."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        
        # Open the circuit
        breaker.failure_count = 1
        breaker.state = "open"
        breaker.last_failure_time = time.time()
        
        @breaker
        async def async_func():
            return "success"
        
        # Should raise immediately (line 225)
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is open"):
            await async_func()

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_open_transitions_to_half_open(self):
        """Test CircuitBreaker async_wrapper - open state transitions to half-open (lines 220-222)."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit but with expired timeout
        breaker.failure_count = 1
        breaker.state = "open"
        breaker.last_failure_time = time.time() - 1.0  # Expired
        
        @breaker
        async def async_func():
            return "success"
        
        # Should transition to half-open and succeed (line 221)
        result = await async_func()
        assert result == "success"
        assert breaker.state == "closed"  # Closed after success

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_await_func_path(self):
        """Test CircuitBreaker async_wrapper - await func path (line 229)."""
        breaker = CircuitBreaker(failure_threshold=5)
        
        @breaker
        async def async_func():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_func()
        assert result == "async_result"
        assert breaker.state == "closed"


class TestCircuitBreakerInternalMethods:
    """Test CircuitBreaker internal methods for coverage."""

    def test_on_success_half_open_state(self):
        """Test CircuitBreaker._on_success() - half-open state transition (lines 271-273)."""
        breaker = CircuitBreaker(failure_threshold=5)
        breaker.state = "half-open"
        breaker.failure_count = 3
        
        breaker._on_success()
        
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_on_success_closed_state(self):
        """Test CircuitBreaker._on_success() - closed state (line 270)."""
        breaker = CircuitBreaker(failure_threshold=5)
        breaker.state = "closed"
        breaker.failure_count = 2
        
        breaker._on_success()
        
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_on_failure_below_threshold(self):
        """Test CircuitBreaker._on_failure() - below threshold (lines 277-278)."""
        breaker = CircuitBreaker(failure_threshold=5)
        breaker.state = "closed"
        initial_time = time.time()
        
        breaker._on_failure()
        
        assert breaker.failure_count == 1
        assert breaker.state == "closed"
        assert breaker.last_failure_time >= initial_time

    def test_on_failure_opens_circuit(self):
        """Test CircuitBreaker._on_failure() - opens circuit at threshold (lines 280-284)."""
        breaker = CircuitBreaker(failure_threshold=2)
        breaker.state = "closed"
        breaker.failure_count = 1
        
        breaker._on_failure()
        
        assert breaker.failure_count == 2
        assert breaker.state == "open"

    def test_get_state(self):
        """Test CircuitBreaker.get_state() - returns all state fields (lines 286-294)."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        breaker.failure_count = 2
        breaker.last_failure_time = 1234567890.0
        breaker.state = "half-open"
        
        state = breaker.get_state()
        
        assert state["state"] == "half-open"
        assert state["failure_count"] == 2
        assert state["last_failure_time"] == 1234567890.0
        assert state["failure_threshold"] == 5
        assert state["recovery_timeout"] == 60.0


class TestRateLimiterAcquire:
    """Test RateLimiter.acquire() return False path (line 332)."""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_returns_false_when_limited(self):
        """Test RateLimiter.acquire() - returns False when rate limited (line 332)."""
        limiter = RateLimiter(max_requests=2, time_window=1.0)
        
        # Fill up the rate limit
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        
        # Next request should be rate limited (line 332)
        assert await limiter.acquire() is False


class TestWithRateLimitAsyncWrapper:
    """Test with_rate_limit async_wrapper await func path (line 362)."""

    @pytest.mark.asyncio
    async def test_with_rate_limit_async_wrapper_await_func(self):
        """Test with_rate_limit async_wrapper - await func path (line 362)."""
        @with_rate_limit(max_requests=10, time_window=1.0)
        async def async_func():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_func()
        assert result == "async_result"


class TestDecoratorReturnPaths:
    """Test decorator return paths for wrapper selection."""

    def test_with_rate_limit_returns_sync_wrapper(self):
        """Test with_rate_limit returns sync_wrapper for sync function (line 376)."""
        @with_rate_limit(max_requests=10, time_window=1.0)
        def sync_func():
            return "sync_result"
        
        # Should return sync_wrapper
        result = sync_func()
        assert result == "sync_result"

    def test_circuit_breaker_returns_sync_wrapper(self):
        """Test CircuitBreaker returns sync_wrapper for sync function (line 266)."""
        breaker = CircuitBreaker()
        
        @breaker
        def sync_func():
            return "sync_result"
        
        result = sync_func()
        assert result == "sync_result"

    def test_with_timeout_returns_sync_wrapper(self):
        """Test with_timeout returns sync_wrapper for sync function (line 183)."""
        from ccbt.utils.resilience import with_timeout
        
        @with_timeout(1.0)
        def sync_func():
            return "sync_result"
        
        result = sync_func()
        assert result == "sync_result"

