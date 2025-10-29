"""Tests for resilience patterns."""

import asyncio
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.resilience]

from ccbt.resilience import (
    BulkOperationManager,
    CircuitBreaker,
    CircuitBreakerError,
    RateLimiter,
    retry_on_network_error,
    retry_on_tracker_error,
    with_rate_limit,
    with_retry,
    with_timeout,
)


@pytest.mark.asyncio
async def test_with_retry_success():
    """Test retry decorator with successful operation."""
    call_count = 0

    @with_retry(retries=3)
    async def successful_operation():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await successful_operation()

    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_with_retry_failure_then_success():
    """Test retry decorator with initial failure then success."""
    call_count = 0

    @with_retry(retries=3, backoff=0.1)
    async def flaky_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Connection failed")
        return "success"

    result = await flaky_operation()

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_all_failures():
    """Test retry decorator when all attempts fail."""
    call_count = 0

    @with_retry(retries=2, backoff=0.1)
    async def failing_operation():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Always fails")

    with pytest.raises(ConnectionError):
        await failing_operation()

    assert call_count == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_with_retry_specific_exceptions():
    """Test retry decorator with specific exception types."""
    call_count = 0

    @with_retry(retries=2, exceptions=(ConnectionError,))
    async def operation_with_wrong_exception():
        nonlocal call_count
        call_count += 1
        raise ValueError("Wrong exception type")

    with pytest.raises(ValueError):
        await operation_with_wrong_exception()

    assert call_count == 1  # No retries for wrong exception type


@pytest.mark.asyncio
async def test_with_timeout_success():
    """Test timeout decorator with successful operation."""
    @with_timeout(1.0)
    async def quick_operation():
        await asyncio.sleep(0.1)
        return "success"

    result = await quick_operation()
    assert result == "success"


@pytest.mark.asyncio
async def test_with_timeout_failure():
    """Test timeout decorator with slow operation."""
    @with_timeout(0.1)
    async def slow_operation():
        await asyncio.sleep(1.0)
        return "success"

    with pytest.raises(TimeoutError):
        await slow_operation()


@pytest.mark.asyncio
async def test_circuit_breaker_closed_state():
    """Test circuit breaker in closed state."""
    breaker = CircuitBreaker(failure_threshold=2)

    call_count = 0

    @breaker
    async def successful_operation():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await successful_operation()

    assert result == "success"
    assert call_count == 1
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after threshold failures."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    call_count = 0

    @breaker
    async def failing_operation():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Always fails")

    # First failure
    with pytest.raises(ConnectionError):
        await failing_operation()

    # Second failure - should open circuit
    with pytest.raises(ConnectionError):
        await failing_operation()

    # Third call should be blocked by circuit breaker
    with pytest.raises(CircuitBreakerError):
        await failing_operation()

    assert call_count == 2  # Only first two calls executed
    assert breaker.state == "open"


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    """Test circuit breaker recovery in half-open state."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

    call_count = 0

    @breaker
    async def operation():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("First call fails")
        return "success"

    # First call fails, opens circuit
    with pytest.raises(ConnectionError):
        await operation()

    assert breaker.state == "open"

    # Wait for recovery timeout
    await asyncio.sleep(0.2)

    # Next call should succeed and close circuit
    result = await operation()

    assert result == "success"
    assert call_count == 2
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests():
    """Test rate limiter allows requests within limit."""
    limiter = RateLimiter(max_requests=3, time_window=1.0)

    # Should allow 3 requests
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True

    # Fourth request should be rate limited
    assert await limiter.acquire() is False


@pytest.mark.asyncio
async def test_rate_limiter_wait_for_permission():
    """Test rate limiter wait for permission."""
    limiter = RateLimiter(max_requests=1, time_window=0.1)

    # First request should succeed
    assert await limiter.acquire() is True

    # Second request should be rate limited
    assert await limiter.acquire() is False

    # Wait for permission should block until window resets
    start_time = time.time()
    await limiter.wait_for_permission()
    elapsed = time.time() - start_time

    # Should have waited approximately the time window
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_bulk_operation_manager():
    """Test bulk operation manager."""
    manager = BulkOperationManager(batch_size=2, max_concurrent=2)

    items = [1, 2, 3, 4, 5]
    results = []

    async def process_batch(batch):
        await asyncio.sleep(0.01)  # Simulate work
        return [x * 2 for x in batch]

    results = await manager.process_batches(items, process_batch)

    # Should process all items
    assert len(results) == 3  # 3 batches: [1,2], [3,4], [5]
    assert results[0] == [2, 4]
    assert results[1] == [6, 8]
    assert results[2] == [10]


@pytest.mark.asyncio
async def test_bulk_operation_manager_with_errors():
    """Test bulk operation manager with error handling."""
    manager = BulkOperationManager(batch_size=2, max_concurrent=2)

    items = [1, 2, 3, 4]
    error_count = 0

    async def process_batch(batch):
        if batch == [1, 2]:
            raise ValueError("Batch processing failed")
        return [x * 2 for x in batch]

    def error_handler(error, batch):
        nonlocal error_count
        error_count += 1

    results = await manager.process_batches(items, process_batch, error_handler)

    # Should process successful batches only
    assert len(results) == 1  # Only [3,4] batch succeeded
    assert results[0] == [6, 8]
    assert error_count == 1


@pytest.mark.asyncio
async def test_retry_on_network_error():
    """Test network error retry decorator."""
    call_count = 0

    @retry_on_network_error(retries=2)
    async def network_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Network error")
        return "success"

    result = await network_operation()

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_on_tracker_error():
    """Test tracker error retry decorator."""
    call_count = 0

    @retry_on_tracker_error(retries=2)
    async def tracker_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Tracker error")
        return "success"

    result = await tracker_operation()

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_get_state():
    """Test circuit breaker state information."""
    breaker = CircuitBreaker(failure_threshold=2)

    state = breaker.get_state()

    assert state["state"] == "closed"
    assert state["failure_count"] == 0
    assert state["failure_threshold"] == 2
    assert state["recovery_timeout"] == 60.0


@pytest.mark.asyncio
async def test_rate_limiter_with_decorator():
    """Test rate limiter decorator."""
    call_count = 0

    @with_rate_limit(max_requests=2, time_window=0.1)
    async def limited_operation():
        nonlocal call_count
        call_count += 1
        return f"call_{call_count}"

    # First two calls should succeed
    result1 = await limited_operation()
    result2 = await limited_operation()

    assert result1 == "call_1"
    assert result2 == "call_2"

    # Third call should be rate limited (will wait)
    start_time = time.time()
    result3 = await limited_operation()
    elapsed = time.time() - start_time

    assert result3 == "call_3"
    assert elapsed >= 0.1  # Should have waited for rate limit
