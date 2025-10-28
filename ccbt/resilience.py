"""Resilience patterns for ccBitTorrent.

This module provides retry logic, circuit breakers, and timeout handling
for robust error handling across the application.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar, Union, cast

T = TypeVar("T")
AsyncFunc = Callable[..., Awaitable[T]]
SyncFunc = Callable[..., T]
Func = Union[AsyncFunc[T], SyncFunc[T]]


class RetryableError(Exception):
    """Errors that can be retried."""


class FatalError(Exception):
    """Errors that should terminate connection."""


class CircuitBreakerError(Exception):
    """Error raised when circuit breaker is open."""


def with_retry(
    retries: int = 3,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    max_delay: float = 60.0,
) -> Callable[[Func[T]], Func[T]]:
    """Decorator for retry logic with exponential backoff.

    Args:
        retries: Number of retry attempts
        backoff: Backoff multiplier
        exceptions: Exception types to retry on
        max_delay: Maximum delay between retries

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            delay = 1.0

            for attempt in range(retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await cast("Awaitable[T]", func(*args, **kwargs))
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == retries:
                        # Last attempt failed
                        break

                    # Wait before retry
                    await asyncio.sleep(min(delay, max_delay))
                    delay *= backoff

            # All retries failed
            if last_exception is not None:
                raise last_exception
            error_msg = "All retries failed"
            raise RuntimeError(error_msg)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            delay = 1.0

            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == retries:
                        # Last attempt failed
                        break

                    # Wait before retry
                    time.sleep(min(delay, max_delay))
                    delay *= backoff

            # All retries failed
            if last_exception is not None:
                raise last_exception
            error_msg = "All retries failed"
            raise RuntimeError(error_msg)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_timeout(seconds: float) -> Callable[[Func[T]], Func[T]]:
    """Decorator for timeout handling.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated function with timeout
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                error_msg = f"Operation timed out after {seconds} seconds"
                raise TimeoutError(error_msg) from None

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # For sync functions, we can't easily add timeout without threading
            # This is a placeholder - in practice, sync functions should be
            # converted to async or use threading for timeout
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before trying again
            expected_exception: Exception type to count as failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half-open

        self.logger = logging.getLogger(__name__)

    def __call__(self, func: Func[T]) -> Func[T]:
        """Make circuit breaker callable as decorator."""

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half-open"
                    self.logger.info("Circuit breaker moving to half-open state")
                else:
                    error_msg = "Circuit breaker is open"
                    raise CircuitBreakerError(error_msg)

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._on_success()
                return result

            except self.expected_exception:
                self._on_failure()
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half-open"
                    self.logger.info("Circuit breaker moving to half-open state")
                else:
                    error_msg = "Circuit breaker is open"
                    raise CircuitBreakerError(error_msg)

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result

            except self.expected_exception:
                self._on_failure()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def _on_success(self) -> None:
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == "half-open":
            self.state = "closed"
            self.logger.info("Circuit breaker closed after successful operation")

    def _on_failure(self) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(
                "Circuit breaker opened after %d failures", self.failure_count
            )

    def get_state(self) -> dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class RateLimiter:
    """Rate limiter for controlling request frequency."""

    def __init__(self, max_requests: int, time_window: float):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: list[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire permission to make a request.

        Returns:
            True if request is allowed, False if rate limited
        """
        async with self.lock:
            now = time.time()

            # Remove old requests outside time window
            self.requests = [
                req_time
                for req_time in self.requests
                if now - req_time < self.time_window
            ]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    async def wait_for_permission(self) -> None:
        """Wait until permission is granted."""
        while not await self.acquire():
            await asyncio.sleep(0.1)


def with_rate_limit(
    max_requests: int, time_window: float
) -> Callable[[Func[T]], Func[T]]:
    """Decorator for rate limiting.

    Args:
        max_requests: Maximum requests allowed in time window
        time_window: Time window in seconds

    Returns:
        Decorated function with rate limiting
    """
    rate_limiter = RateLimiter(max_requests, time_window)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            await rate_limiter.wait_for_permission()

            if asyncio.iscoroutinefunction(func):
                return await cast("Awaitable[T]", func(*args, **kwargs))
            return func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # For sync functions, we need to run the rate limiter in async context
            loop = asyncio.get_event_loop()
            loop.run_until_complete(rate_limiter.wait_for_permission())
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class BulkOperationManager:
    """Manages bulk operations with batching and error handling."""

    def __init__(self, batch_size: int = 100, max_concurrent: int = 10):
        """Initialize bulk operation manager.

        Args:
            batch_size: Size of each batch
            max_concurrent: Maximum concurrent batches
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batches(
        self,
        items: list[Any],
        operation: Callable[[list[Any]], Any],
        error_handler: Callable[[Exception, list[Any]], None] | None = None,
    ) -> list[Any]:
        """Process items in batches.

        Args:
            items: Items to process
            operation: Function to process each batch
            error_handler: Optional error handler

        Returns:
            List of results from successful batches
        """
        batches = [
            items[i : i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        async def process_batch(batch: list[Any]) -> Any:
            async with self.semaphore:
                try:
                    if asyncio.iscoroutinefunction(operation):
                        return await operation(batch)
                    return operation(batch)
                except Exception as e:
                    if error_handler:
                        error_handler(e, batch)
                    return None

        tasks = [process_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        return [
            result
            for result in results
            if result is not None and not isinstance(result, Exception)
        ]


# Convenience functions
def retry_on_network_error(
    retries: int = 3,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator specifically for network errors."""
    return with_retry(
        retries=retries,
        exceptions=(ConnectionError, TimeoutError, OSError),
        backoff=2.0,
        max_delay=30.0,
    )


def retry_on_tracker_error(
    retries: int = 3,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator specifically for tracker errors."""
    from ccbt.tracker import TrackerError

    return with_retry(
        retries=retries,
        exceptions=(TrackerError, ConnectionError, TimeoutError),
        backoff=2.0,
        max_delay=60.0,
    )


def timeout_for_connections(
    seconds: float = 30.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Timeout decorator for connection operations."""
    return with_timeout(seconds)


def timeout_for_tracker_requests(
    seconds: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Timeout decorator for tracker requests."""
    return with_timeout(seconds)
