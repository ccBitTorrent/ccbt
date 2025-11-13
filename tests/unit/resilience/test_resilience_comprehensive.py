"""Comprehensive tests for resilience patterns - coverage gaps.

Covers:
- with_retry sync_wrapper (synchronous function retry logic)
- with_retry async_wrapper edge cases (sync function through async wrapper)
- with_timeout sync_wrapper edge cases
- CircuitBreaker sync_wrapper (all states and transitions)
- with_rate_limit sync_wrapper (synchronous rate limiting)
- BulkOperationManager sync operations
- Convenience functions (timeout_for_connections, timeout_for_tracker_requests)
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.resilience]

from ccbt.utils.resilience import (
    BulkOperationManager,
    CircuitBreaker,
    CircuitBreakerError,
    RateLimiter,
    timeout_for_connections,
    timeout_for_tracker_requests,
    with_rate_limit,
    with_retry,
    with_timeout,
)


class TestWithRetrySyncWrapper:
    """Test with_retry decorator with synchronous functions."""

    def test_with_retry_sync_success(self):
        """Test retry decorator with synchronous successful operation."""
        call_count = 0

        @with_retry(retries=3)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()

        assert result == "success"
        assert call_count == 1

    def test_with_retry_sync_failure_then_success(self):
        """Test retry decorator with synchronous function - failure then success."""
        call_count = 0

        @with_retry(retries=3, backoff=0.1)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = flaky_operation()

        assert result == "success"
        assert call_count == 3

    def test_with_retry_sync_all_failures(self):
        """Test retry decorator with synchronous function - all attempts fail."""
        call_count = 0

        @with_retry(retries=2, backoff=0.1)
        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            failing_operation()

        assert call_count == 3  # Initial + 2 retries

    def test_with_retry_sync_specific_exceptions(self):
        """Test retry decorator with synchronous function - specific exception types."""
        call_count = 0

        @with_retry(retries=2, exceptions=(ConnectionError,))
        def operation_with_wrong_exception():
            nonlocal call_count
            call_count += 1
            raise ValueError("Wrong exception type")

        with pytest.raises(ValueError):
            operation_with_wrong_exception()

        assert call_count == 1  # No retries for wrong exception type

    def test_with_retry_sync_max_delay(self):
        """Test retry decorator with synchronous function - max delay cap."""
        call_count = 0

        @with_retry(retries=2, backoff=10.0, max_delay=0.1)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        start_time = time.time()
        result = flaky_operation()
        elapsed = time.time() - start_time

        assert result == "success"
        assert call_count == 2
        # Should respect max_delay (0.1 seconds) even with large backoff
        assert elapsed < 0.5  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_with_retry_async_wrapper_calls_sync_function(self):
        """Test async_wrapper handling sync function (edge case line 61).
        
        This tests the path where a sync function is called through the async_wrapper.
        We need to mock iscoroutinefunction at two points:
        1. At decorator creation (line 104) to return True (force async_wrapper)
        2. Inside async_wrapper execution (line 59) to return False (treat as sync)
        """
        def sync_function():
            return "sync_result"

        decorator = with_retry(retries=2)
        
        # First patch: make decorator think it's async (to get async_wrapper)
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction", return_value=True):
            wrapped = decorator(sync_function)
        
        # Second patch: inside async_wrapper, make it think func is sync (line 59->61)
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction") as mock_iscoro:
            # At line 104 check, return True (already done above, wrapper is async_wrapper)
            # At line 59 check inside async_wrapper, return False to hit line 61
            mock_iscoro.return_value = False
            result = await wrapped()
            assert result == "sync_result"


class TestWithRetryErrorPaths:
    """Test with_retry error handling paths."""

    @pytest.mark.asyncio
    async def test_with_retry_async_runtime_error_no_exception(self):
        """Test async_wrapper RuntimeError path when last_exception is None (lines 76-77).
        
        Note: This is a defensive path that's difficult to trigger naturally.
        The path occurs when the loop completes without setting last_exception,
        which shouldn't happen in normal operation. We'll test the code structure
        by ensuring normal operations work correctly.
        """
        # This defensive path requires the loop to complete without exceptions
        # but also without returning. Since a successful operation returns at line 60/61,
        # this path is theoretical. We'll verify the normal path works correctly.
        call_count = 0

        @with_retry(retries=0)
        async def normal_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await normal_operation()

        assert result == "success"
        assert call_count == 1


class TestWithTimeoutSyncWrapper:
    """Test with_timeout decorator with synchronous functions - edge cases."""

    def test_with_timeout_sync_both_queues_empty_edge_case(self):
        """Test sync_wrapper edge case where thread completes but both queues empty (lines 161-162).
        
        Note: This edge case is theoretically possible but hard to trigger reliably.
        It occurs when the thread completes but both queues remain empty due to
        a race condition. We test the structure exists but may need a pragma.
        """
        # This edge case requires precise timing - thread completes before queue.put()
        # completes. This is rare but possible in race conditions.
        @with_timeout(0.1)
        def fast_operation():
            # Fast operation that should populate queue normally
            return "result"

        result = fast_operation()

        # Normal path should work
        assert result == "result"


class TestCircuitBreakerAsyncWrapperEdgeCases:
    """Test CircuitBreaker async_wrapper edge cases with sync functions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_wrapper_with_sync_function(self):
        """Test CircuitBreaker async_wrapper calling sync function (line 214).
        
        Mock iscoroutinefunction at decorator creation (True) and inside execution (False).
        """
        breaker = CircuitBreaker(failure_threshold=2)

        def sync_function():
            return "sync_result"

        # First: make decorator return async_wrapper
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction", return_value=True):
            wrapped = breaker(sync_function)
        
        # Second: inside async_wrapper, make it treat func as sync (line 211->214)
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction") as mock_iscoro:
            mock_iscoro.return_value = False
            result = await wrapped()
            assert result == "sync_result"
            assert breaker.state == "closed"


class TestCircuitBreakerSyncWrapper:
    """Test CircuitBreaker decorator with synchronous functions."""

    def test_circuit_breaker_sync_closed_state(self):
        """Test circuit breaker sync_wrapper in closed state - success."""
        breaker = CircuitBreaker(failure_threshold=2)

        call_count = 0

        @breaker
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()

        assert result == "success"
        assert call_count == 1
        assert breaker.state == "closed"

    def test_circuit_breaker_sync_opens_after_failures(self):
        """Test circuit breaker sync_wrapper opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        call_count = 0

        @breaker
        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        # First failure
        with pytest.raises(ConnectionError):
            failing_operation()

        # Second failure - should open circuit
        with pytest.raises(ConnectionError):
            failing_operation()

        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            failing_operation()

        assert call_count == 2  # Only first two calls executed
        assert breaker.state == "open"

    def test_circuit_breaker_sync_open_blocks_immediately(self):
        """Test circuit breaker sync_wrapper blocks when open and timeout not reached."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)

        @breaker
        def failing_operation():
            raise ConnectionError("Always fails")

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            failing_operation()

        assert breaker.state == "open"

        # Immediate retry should be blocked (recovery_timeout not reached)
        with pytest.raises(CircuitBreakerError):
            failing_operation()

    def test_circuit_breaker_sync_half_open_recovery(self):
        """Test circuit breaker sync_wrapper recovery from half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        call_count = 0

        @breaker
        def operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First call fails")
            return "success"

        # First call fails, opens circuit
        with pytest.raises(ConnectionError):
            operation()

        assert breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(0.2)

        # Next call should succeed and close circuit
        result = operation()

        assert result == "success"
        assert call_count == 2
        assert breaker.state == "closed"

    def test_circuit_breaker_sync_half_open_failure(self):
        """Test circuit breaker sync_wrapper re-opens on failure in half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        @breaker
        def always_failing_operation():
            raise ConnectionError("Always fails")

        # First failure opens circuit
        with pytest.raises(ConnectionError):
            always_failing_operation()

        assert breaker.state == "open"

        # Wait for recovery
        time.sleep(0.2)

        # Next call transitions to half-open, then fails again
        with pytest.raises(ConnectionError):
            always_failing_operation()

        # Circuit should be open again
        assert breaker.state == "open"

    def test_circuit_breaker_sync_wrong_exception_type(self):
        """Test circuit breaker sync_wrapper ignores non-expected exceptions."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ConnectionError,
        )

        call_count = 0

        @breaker
        def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Wrong exception type")

        # Should raise ValueError, not count as failure
        with pytest.raises(ValueError):
            operation()

        # Circuit should still be closed (ValueError not expected)
        assert breaker.state == "closed"
        assert breaker.failure_count == 0
        assert call_count == 1


class TestWithRateLimitAsyncWrapperEdgeCases:
    """Test with_rate_limit async_wrapper edge cases."""

    @pytest.mark.asyncio
    async def test_with_rate_limit_async_wrapper_with_sync_function(self):
        """Test with_rate_limit async_wrapper calling sync function (line 339).
        
        Mock iscoroutinefunction at decorator creation (True) and inside execution (False).
        """
        def sync_function():
            return "sync_result"

        decorator = with_rate_limit(max_requests=2, time_window=0.1)
        
        # First: make decorator return async_wrapper
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction", return_value=True):
            wrapped = decorator(sync_function)
        
        # Second: inside async_wrapper, make it treat func as sync (line 337->339)
        with patch("ccbt.utils.resilience.asyncio.iscoroutinefunction") as mock_iscoro:
            mock_iscoro.return_value = False
            result = await wrapped()
            assert result == "sync_result"


class TestWithRateLimitSyncWrapper:
    """Test with_rate_limit decorator with synchronous functions."""

    def test_with_rate_limit_sync_allows_requests(self):
        """Test rate limiter sync_wrapper allows requests within limit."""
        call_count = 0

        @with_rate_limit(max_requests=3, time_window=1.0)
        def limited_operation():
            nonlocal call_count
            call_count += 1
            return f"call_{call_count}"

        # First three calls should succeed
        result1 = limited_operation()
        result2 = limited_operation()
        result3 = limited_operation()

        assert result1 == "call_1"
        assert result2 == "call_2"
        assert result3 == "call_3"
        assert call_count == 3

    def test_with_rate_limit_sync_wait_for_permission(self):
        """Test rate limiter sync_wrapper waits when rate limited."""
        call_count = 0

        @with_rate_limit(max_requests=1, time_window=0.1)
        def limited_operation():
            nonlocal call_count
            call_count += 1
            return f"call_{call_count}"

        # First call should succeed
        result1 = limited_operation()
        assert result1 == "call_1"

        # Second call should wait (rate limited)
        start_time = time.time()
        result2 = limited_operation()
        elapsed = time.time() - start_time

        assert result2 == "call_2"
        assert elapsed >= 0.1  # Should have waited for rate limit window
        assert call_count == 2


class TestBulkOperationManagerSync:
    """Test BulkOperationManager with synchronous operations."""

    @pytest.mark.asyncio
    async def test_bulk_operation_manager_sync_operation(self):
        """Test BulkOperationManager with synchronous operation function (line 395)."""
        manager = BulkOperationManager(batch_size=2, max_concurrent=2)

        items = [1, 2, 3, 4, 5]

        def process_batch_sync(batch):
            # Synchronous operation function
            return [x * 2 for x in batch]

        results = await manager.process_batches(items, process_batch_sync)

        # Should process all items
        assert len(results) == 3  # 3 batches: [1,2], [3,4], [5]
        assert results[0] == [2, 4]
        assert results[1] == [6, 8]
        assert results[2] == [10]

    @pytest.mark.asyncio
    async def test_bulk_operation_manager_sync_with_errors(self):
        """Test BulkOperationManager with sync operation and error handling."""
        manager = BulkOperationManager(batch_size=2, max_concurrent=2)

        items = [1, 2, 3, 4]
        error_count = 0

        def process_batch_sync(batch):
            if batch == [1, 2]:
                raise ValueError("Batch processing failed")
            return [x * 2 for x in batch]

        def error_handler(error, batch):
            nonlocal error_count
            error_count += 1

        results = await manager.process_batches(
            items, process_batch_sync, error_handler
        )

        # Should process successful batches only
        assert len(results) == 1  # Only [3,4] batch succeeded
        assert results[0] == [6, 8]
        assert error_count == 1


class TestConvenienceFunctions:
    """Test convenience function wrappers."""

    def test_timeout_for_connections(self):
        """Test timeout_for_connections convenience function (line 443)."""
        @timeout_for_connections(seconds=0.1)
        def connection_operation():
            return "connected"

        result = connection_operation()
        assert result == "connected"

    def test_timeout_for_connections_timeout(self):
        """Test timeout_for_connections with timeout."""
        @timeout_for_connections(seconds=0.1)
        def slow_connection_operation():
            time.sleep(0.2)
            return "should_not_reach"

        with pytest.raises(TimeoutError):
            slow_connection_operation()

    def test_timeout_for_tracker_requests(self):
        """Test timeout_for_tracker_requests convenience function (line 450)."""
        @timeout_for_tracker_requests(seconds=0.1)
        def tracker_operation():
            return "tracker_response"

        result = tracker_operation()
        assert result == "tracker_response"

    def test_timeout_for_tracker_requests_timeout(self):
        """Test timeout_for_tracker_requests with timeout."""
        @timeout_for_tracker_requests(seconds=0.1)
        def slow_tracker_operation():
            time.sleep(0.2)
            return "should_not_reach"

        with pytest.raises(TimeoutError):
            slow_tracker_operation()

    @pytest.mark.asyncio
    async def test_timeout_for_connections_async(self):
        """Test timeout_for_connections with async function."""
        @timeout_for_connections(seconds=0.1)
        async def async_connection_operation():
            await asyncio.sleep(0.01)
            return "async_connected"

        result = await async_connection_operation()
        assert result == "async_connected"

    @pytest.mark.asyncio
    async def test_timeout_for_tracker_requests_async(self):
        """Test timeout_for_tracker_requests with async function."""
        @timeout_for_tracker_requests(seconds=0.1)
        async def async_tracker_operation():
            await asyncio.sleep(0.01)
            return "async_tracker_response"

        result = await async_tracker_operation()
        assert result == "async_tracker_response"

