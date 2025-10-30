"""Rate Limiter for ccBitTorrent.

from __future__ import annotations

Provides adaptive rate limiting including:
- Per-peer rate limiting
- Global rate limiting
- Adaptive rate adjustment
- DDoS protection
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from ccbt.utils.events import Event, EventType, emit_event


class RateLimitType(Enum):
    """Types of rate limits."""

    CONNECTION = "connection"
    MESSAGE = "message"
    BYTES = "bytes"
    REQUESTS = "requests"
    PIECES = "pieces"


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms."""

    TOKEN_BUCKET = "token_bucket"  # nosec S105 - Enum value, not a password
    SLIDING_WINDOW = "sliding_window"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimit:
    """Rate limit configuration."""

    limit_type: RateLimitType
    max_requests: int
    time_window: float  # seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    burst_size: int = 0  # For token bucket
    decay_rate: float = 0.1  # For adaptive algorithm


@dataclass
class RateLimitStats:
    """Rate limit statistics."""

    peer_id: str
    ip: str
    limit_type: RateLimitType
    requests_count: int
    time_window: float
    last_request: float
    is_limited: bool
    limit_hits: int
    total_requests: int


class RateLimiter:
    """Adaptive rate limiter."""

    def __init__(self):
        """Initialize rate limiter."""
        self.rate_limits: dict[RateLimitType, RateLimit] = {}
        self.peer_stats: dict[str, dict[RateLimitType, RateLimitStats]] = defaultdict(
            dict,
        )
        self.global_stats: dict[RateLimitType, RateLimitStats] = {}

        # Token bucket state
        self.token_buckets: dict[str, dict[RateLimitType, float]] = defaultdict(dict)

        # Sliding window state
        self.sliding_windows: dict[str, dict[RateLimitType, deque]] = defaultdict(dict)

        # Adaptive rate adjustment
        self.adaptive_rates: dict[str, dict[RateLimitType, float]] = defaultdict(dict)
        # Store (timestamp, performance_metric) tuples per peer
        self.performance_history: dict[str, list[tuple[float, float]]] = defaultdict(
            list
        )

        # Configuration
        self.default_limits = {
            RateLimitType.CONNECTION: RateLimit(
                limit_type=RateLimitType.CONNECTION,
                max_requests=10,
                time_window=60.0,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                burst_size=5,
            ),
            RateLimitType.MESSAGE: RateLimit(
                limit_type=RateLimitType.MESSAGE,
                max_requests=100,
                time_window=60.0,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
            RateLimitType.BYTES: RateLimit(
                limit_type=RateLimitType.BYTES,
                max_requests=1024 * 1024,  # 1MB
                time_window=60.0,
                algorithm=RateLimitAlgorithm.ADAPTIVE,
            ),
            RateLimitType.REQUESTS: RateLimit(
                limit_type=RateLimitType.REQUESTS,
                max_requests=50,
                time_window=60.0,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            ),
            RateLimitType.PIECES: RateLimit(
                limit_type=RateLimitType.PIECES,
                max_requests=10,
                time_window=60.0,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
        }

        # Initialize default limits
        for limit_type, limit in self.default_limits.items():
            self.rate_limits[limit_type] = limit

    async def check_rate_limit(
        self,
        peer_id: str,
        ip: str,
        limit_type: RateLimitType,
        request_size: int = 1,
    ) -> tuple[bool, float]:
        """Check if request is within rate limit.

        Args:
            peer_id: Peer identifier
            ip: Peer IP address
            limit_type: Type of rate limit
            request_size: Size of the request

        Returns:
            Tuple of (is_allowed, wait_time)
        """
        # Get rate limit configuration
        rate_limit = self.rate_limits.get(limit_type)
        if not rate_limit:
            return True, 0.0

        # Check global rate limit first
        global_allowed, global_wait = await self._check_global_rate_limit(
            limit_type,
            request_size,
        )
        if not global_allowed:
            return False, global_wait

        # Check peer-specific rate limit
        peer_allowed, peer_wait = await self._check_peer_rate_limit(
            peer_id,
            ip,
            limit_type,
            request_size,
            rate_limit,
        )

        if not peer_allowed:
            return False, peer_wait

        # Update statistics
        self._update_rate_limit_stats(peer_id, ip, limit_type, request_size, True)

        return True, 0.0

    async def record_request(
        self,
        peer_id: str,
        ip: str,
        limit_type: RateLimitType,
        request_size: int = 1,
        success: bool = True,
    ) -> None:
        """Record a request for rate limiting."""
        # Update peer statistics
        self._update_rate_limit_stats(peer_id, ip, limit_type, request_size, success)

        # Update performance history for adaptive rate limiting
        if limit_type == RateLimitType.BYTES:
            self._update_performance_history(peer_id, request_size, success)

        # Adjust adaptive rates if needed
        if self.rate_limits[limit_type].algorithm == RateLimitAlgorithm.ADAPTIVE:
            await self._adjust_adaptive_rate(peer_id, limit_type)

    def set_rate_limit(
        self,
        limit_type: RateLimitType,
        max_requests: int,
        time_window: float,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET,
    ) -> None:
        """Set rate limit configuration."""
        self.rate_limits[limit_type] = RateLimit(
            limit_type=limit_type,
            max_requests=max_requests,
            time_window=time_window,
            algorithm=algorithm,
        )

    def get_rate_limit_stats(self, peer_id: str) -> dict[RateLimitType, RateLimitStats]:
        """Get rate limit statistics for a peer."""
        return self.peer_stats.get(peer_id, {}).copy()

    def get_global_rate_limit_stats(self) -> dict[RateLimitType, RateLimitStats]:
        """Get global rate limit statistics."""
        return self.global_stats.copy()

    def is_peer_limited(self, peer_id: str, limit_type: RateLimitType) -> bool:
        """Check if peer is currently rate limited."""
        if peer_id not in self.peer_stats:
            return False

        if limit_type not in self.peer_stats[peer_id]:
            return False

        return self.peer_stats[peer_id][limit_type].is_limited

    def get_peer_wait_time(self, peer_id: str, limit_type: RateLimitType) -> float:
        """Get wait time for peer to be unblocked."""
        if not self.is_peer_limited(peer_id, limit_type):
            return 0.0

        stats = self.peer_stats[peer_id][limit_type]
        time_since_last = time.time() - stats.last_request
        time_window = stats.time_window

        return max(0.0, time_window - time_since_last)

    def cleanup_old_stats(self, max_age_seconds: int = 3600) -> None:
        """Clean up old rate limit statistics."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up peer stats
        for peer_id in list(self.peer_stats.keys()):
            peer_stats = self.peer_stats[peer_id]
            for limit_type in list(peer_stats.keys()):
                stats = peer_stats[limit_type]
                if stats.last_request < cutoff_time:
                    del peer_stats[limit_type]

            if not peer_stats:
                del self.peer_stats[peer_id]

        # Clean up sliding windows
        for peer_id in list(self.sliding_windows.keys()):
            peer_windows = self.sliding_windows[peer_id]
            for limit_type in list(peer_windows.keys()):
                window = peer_windows[limit_type]
                while window and window[0] < cutoff_time:
                    window.popleft()

                if not window:
                    del peer_windows[limit_type]

            if not peer_windows:
                del self.sliding_windows[peer_id]

    async def _check_global_rate_limit(
        self,
        limit_type: RateLimitType,
        request_size: int,
    ) -> tuple[bool, float]:
        """Check global rate limit."""
        rate_limit = self.rate_limits[limit_type]

        if limit_type not in self.global_stats:
            self.global_stats[limit_type] = RateLimitStats(
                peer_id="global",
                ip="global",
                limit_type=limit_type,
                requests_count=0,
                time_window=rate_limit.time_window,
                last_request=time.time(),
                is_limited=False,
                limit_hits=0,
                total_requests=0,
            )

        stats = self.global_stats[limit_type]
        current_time = time.time()

        # Check if we're in the time window
        if current_time - stats.last_request > rate_limit.time_window:
            stats.requests_count = 0
            stats.is_limited = False

        # Check if we've exceeded the limit
        if stats.requests_count + request_size > rate_limit.max_requests:
            stats.limit_hits += 1
            stats.is_limited = True
            wait_time = rate_limit.time_window - (current_time - stats.last_request)
            return False, max(0.0, wait_time)

        # Update stats
        stats.requests_count += request_size
        stats.last_request = current_time
        stats.total_requests += request_size

        return True, 0.0

    async def _check_peer_rate_limit(
        self,
        peer_id: str,
        ip: str,
        limit_type: RateLimitType,
        request_size: int,
        rate_limit: RateLimit,
    ) -> tuple[bool, float]:
        """Check peer-specific rate limit."""
        # Initialize peer stats if needed
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = {}

        if limit_type not in self.peer_stats[peer_id]:
            self.peer_stats[peer_id][limit_type] = RateLimitStats(
                peer_id=peer_id,
                ip=ip,
                limit_type=limit_type,
                requests_count=0,
                time_window=rate_limit.time_window,
                last_request=time.time(),
                is_limited=False,
                limit_hits=0,
                total_requests=0,
            )

        self.peer_stats[peer_id][limit_type]

        # Use appropriate algorithm
        if rate_limit.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._check_token_bucket(
                peer_id,
                limit_type,
                request_size,
                rate_limit,
            )
        if rate_limit.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._check_sliding_window(
                peer_id,
                limit_type,
                request_size,
                rate_limit,
            )
        if rate_limit.algorithm == RateLimitAlgorithm.ADAPTIVE:
            return await self._check_adaptive(
                peer_id,
                limit_type,
                request_size,
                rate_limit,
            )
        return True, 0.0

    async def _check_token_bucket(
        self,
        peer_id: str,
        limit_type: RateLimitType,
        request_size: int,
        rate_limit: RateLimit,
    ) -> tuple[bool, float]:
        """Check token bucket rate limit."""
        current_time = time.time()

        # Initialize token bucket if needed
        if limit_type not in self.token_buckets[peer_id]:
            self.token_buckets[peer_id][limit_type] = float(rate_limit.max_requests)

        tokens = self.token_buckets[peer_id][limit_type]

        # Add tokens based on time elapsed
        time_elapsed = current_time - self.peer_stats[peer_id][limit_type].last_request
        tokens_to_add = time_elapsed * (
            rate_limit.max_requests / rate_limit.time_window
        )
        tokens = min(rate_limit.max_requests, tokens + tokens_to_add)

        # Check if we have enough tokens
        if tokens >= request_size:
            tokens -= request_size
            self.token_buckets[peer_id][limit_type] = tokens
            return True, 0.0
        # Calculate wait time
        wait_time = (request_size - tokens) * (
            rate_limit.time_window / rate_limit.max_requests
        )
        return False, wait_time

    async def _check_sliding_window(
        self,
        peer_id: str,
        limit_type: RateLimitType,
        request_size: int,
        rate_limit: RateLimit,
    ) -> tuple[bool, float]:
        """Check sliding window rate limit."""
        current_time = time.time()

        # Initialize sliding window if needed
        if limit_type not in self.sliding_windows[peer_id]:
            self.sliding_windows[peer_id][limit_type] = deque()

        window = self.sliding_windows[peer_id][limit_type]

        # Remove old requests outside the time window
        cutoff_time = current_time - rate_limit.time_window
        while window and window[0] < cutoff_time:
            window.popleft()

        # Check if we can add the request
        if len(window) + request_size <= rate_limit.max_requests:
            # Add request timestamps
            for _ in range(request_size):
                window.append(current_time)
            return True, 0.0
        # Calculate wait time
        if window:
            oldest_request = window[0]
            wait_time = rate_limit.time_window - (current_time - oldest_request)
        else:
            wait_time = 0.0

        return False, max(0.0, wait_time)

    async def _check_adaptive(
        self,
        peer_id: str,
        limit_type: RateLimitType,
        request_size: int,
        rate_limit: RateLimit,
    ) -> tuple[bool, float]:
        """Check adaptive rate limit."""
        # Get adaptive rate for this peer
        if limit_type not in self.adaptive_rates[peer_id]:
            self.adaptive_rates[peer_id][limit_type] = float(rate_limit.max_requests)

        adaptive_rate = self.adaptive_rates[peer_id][limit_type]

        # Use sliding window with adaptive rate
        current_time = time.time()

        if limit_type not in self.sliding_windows[peer_id]:
            self.sliding_windows[peer_id][limit_type] = deque()

        window = self.sliding_windows[peer_id][limit_type]

        # Remove old requests
        cutoff_time = current_time - rate_limit.time_window
        while window and window[0] < cutoff_time:
            window.popleft()

        # Check with adaptive rate
        if len(window) + request_size <= int(adaptive_rate):
            for _ in range(request_size):
                window.append(current_time)
            return True, 0.0
        # Calculate wait time
        if window:
            oldest_request = window[0]
            wait_time = rate_limit.time_window - (current_time - oldest_request)
        else:
            wait_time = 0.0

        return False, max(0.0, wait_time)

    def _update_rate_limit_stats(
        self,
        peer_id: str,
        ip: str,
        limit_type: RateLimitType,
        request_size: int,
        success: bool,
    ) -> None:
        """Update rate limit statistics."""
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = {}

        if limit_type not in self.peer_stats[peer_id]:
            self.peer_stats[peer_id][limit_type] = RateLimitStats(
                peer_id=peer_id,
                ip=ip,
                limit_type=limit_type,
                requests_count=0,
                time_window=self.rate_limits[limit_type].time_window,
                last_request=time.time(),
                is_limited=False,
                limit_hits=0,
                total_requests=0,
            )

        stats = self.peer_stats[peer_id][limit_type]
        stats.requests_count += request_size
        stats.last_request = time.time()
        stats.total_requests += request_size

        if not success:
            stats.limit_hits += 1
            stats.is_limited = True

    def _update_performance_history(
        self,
        peer_id: str,
        request_size: int,
        success: bool,
    ) -> None:
        """Update performance history for adaptive rate limiting."""
        if peer_id not in self.performance_history:
            self.performance_history[peer_id] = []

        # Record performance metric (bytes per second)
        current_time = time.time()
        performance_metric = request_size if success else 0

        self.performance_history[peer_id].append((current_time, performance_metric))

        # Keep only recent history (last hour)
        cutoff_time = current_time - 3600
        self.performance_history[peer_id] = [
            (timestamp, metric)
            for timestamp, metric in self.performance_history[peer_id]
            if timestamp > cutoff_time
        ]

    async def _adjust_adaptive_rate(
        self,
        peer_id: str,
        limit_type: RateLimitType,
    ) -> None:
        """Adjust adaptive rate based on performance history."""
        if peer_id not in self.performance_history:
            return

        if not self.performance_history[peer_id]:
            return

        # Calculate average performance
        performance_metrics = [
            metric for _, metric in self.performance_history[peer_id]
        ]
        if not performance_metrics:
            return

        avg_performance = statistics.mean(performance_metrics)

        # Get current adaptive rate
        current_rate = self.adaptive_rates[peer_id][limit_type]
        base_rate = self.rate_limits[limit_type].max_requests

        # Adjust rate based on performance
        if avg_performance > base_rate * 0.8:  # Good performance
            new_rate = min(base_rate * 1.2, current_rate * 1.1)
        elif avg_performance < base_rate * 0.4:  # Poor performance
            new_rate = max(base_rate * 0.5, current_rate * 0.9)
        else:  # Average performance
            new_rate = current_rate

        # Update adaptive rate
        self.adaptive_rates[peer_id][limit_type] = new_rate

        # Emit adaptive rate change event
        await emit_event(
            Event(
                event_type=EventType.RATE_LIMIT_ADAPTIVE_CHANGED.value,
                data={
                    "peer_id": peer_id,
                    "limit_type": limit_type.value,
                    "old_rate": current_rate,
                    "new_rate": new_rate,
                    "performance": avg_performance,
                    "timestamp": time.time(),
                },
            ),
        )
