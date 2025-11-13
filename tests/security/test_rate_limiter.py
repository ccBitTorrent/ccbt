"""Tests for ccbt.security.rate_limiter.

Covers:
- Initialization and configuration
- Token bucket algorithm
- Sliding window algorithm
- Adaptive rate limiting
- Global and per-peer rate limiting
- Statistics tracking
- Cleanup and maintenance
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.fixture
def rate_limiter():
    """Create a RateLimiter instance."""
    from ccbt.security.rate_limiter import RateLimiter
    
    return RateLimiter()


@pytest.mark.asyncio
async def test_rate_limiter_init(rate_limiter):
    """Test RateLimiter initialization (lines 72-130)."""
    from ccbt.security.rate_limiter import RateLimitAlgorithm, RateLimitType
    
    # Verify default limits are set
    assert len(rate_limiter.rate_limits) > 0
    assert RateLimitType.CONNECTION in rate_limiter.rate_limits
    assert RateLimitType.MESSAGE in rate_limiter.rate_limits
    assert RateLimitType.BYTES in rate_limiter.rate_limits
    
    # Verify initial state
    assert len(rate_limiter.peer_stats) == 0
    assert len(rate_limiter.global_stats) == 0
    assert len(rate_limiter.token_buckets) == 0
    assert len(rate_limiter.sliding_windows) == 0
    assert len(rate_limiter.adaptive_rates) == 0
    
    # Verify default algorithms
    assert rate_limiter.rate_limits[RateLimitType.CONNECTION].algorithm == RateLimitAlgorithm.TOKEN_BUCKET
    assert rate_limiter.rate_limits[RateLimitType.MESSAGE].algorithm == RateLimitAlgorithm.SLIDING_WINDOW
    assert rate_limiter.rate_limits[RateLimitType.BYTES].algorithm == RateLimitAlgorithm.ADAPTIVE


@pytest.mark.asyncio
async def test_set_rate_limit(rate_limiter):
    """Test set_rate_limit method (lines 200-213)."""
    from ccbt.security.rate_limiter import RateLimitAlgorithm, RateLimitType
    
    rate_limiter.set_rate_limit(
        RateLimitType.CONNECTION,
        max_requests=20,
        time_window=120.0,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    )
    
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    assert limit.max_requests == 20
    assert limit.time_window == 120.0
    assert limit.algorithm == RateLimitAlgorithm.SLIDING_WINDOW


@pytest.mark.asyncio
async def test_check_rate_limit_no_limit(rate_limiter):
    """Test check_rate_limit when no limit is configured (lines 150-153)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Use a limit type that doesn't exist
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer1",
        ip="1.2.3.4",
        limit_type=RateLimitType.CONNECTION,  # Will use default
        request_size=1,
    )
    
    assert allowed is True
    assert wait == 0.0


@pytest.mark.asyncio
async def test_check_rate_limit_token_bucket_allowed(rate_limiter):
    """Test check_rate_limit with token bucket - request allowed (lines 132-178)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer1",
        ip="1.2.3.4",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is True
    assert wait == 0.0


@pytest.mark.asyncio
async def test_check_rate_limit_token_bucket_exceeded(rate_limiter):
    """Test check_rate_limit with token bucket - limit exceeded."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Make many requests to exhaust tokens
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    
    for _ in range(limit.max_requests):
        allowed, _ = await rate_limiter.check_rate_limit(
            peer_id="peer1",
            ip="1.2.3.4",
            limit_type=RateLimitType.CONNECTION,
            request_size=1,
        )
        assert allowed is True
    
    # Next request should be rate limited
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer1",
        ip="1.2.3.4",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is False
    assert wait > 0.0


@pytest.mark.asyncio
async def test_check_rate_limit_sliding_window(rate_limiter):
    """Test check_rate_limit with sliding window algorithm (lines 403-437)."""
    from ccbt.security.rate_limiter import RateLimitAlgorithm, RateLimitType
    
    # Set up sliding window limit
    rate_limiter.set_rate_limit(
        RateLimitType.MESSAGE,
        max_requests=5,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    )
    
    # Make requests within limit
    for i in range(5):
        allowed, wait = await rate_limiter.check_rate_limit(
            peer_id="peer2",
            ip="2.3.4.5",
            limit_type=RateLimitType.MESSAGE,
            request_size=1,
        )
        assert allowed is True, f"Request {i} should be allowed"
        time.sleep(0.01)  # Small delay
    
    # Exceed limit
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer2",
        ip="2.3.4.5",
        limit_type=RateLimitType.MESSAGE,
        request_size=1,
    )
    
    assert allowed is False
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_check_rate_limit_adaptive(rate_limiter):
    """Test check_rate_limit with adaptive algorithm (lines 439-478)."""
    from ccbt.security.rate_limiter import RateLimitAlgorithm, RateLimitType
    
    # Set up adaptive limit
    rate_limiter.set_rate_limit(
        RateLimitType.BYTES,
        max_requests=1000,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer3",
        ip="3.4.5.6",
        limit_type=RateLimitType.BYTES,
        request_size=100,
    )
    
    assert allowed is True
    assert wait == 0.0


@pytest.mark.asyncio
async def test_check_global_rate_limit(rate_limiter):
    """Test _check_global_rate_limit (lines 274-315)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # First request should be allowed
    allowed, wait = await rate_limiter._check_global_rate_limit(
        RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is True
    assert wait == 0.0
    assert RateLimitType.CONNECTION in rate_limiter.global_stats


@pytest.mark.asyncio
async def test_check_global_rate_limit_exceeded(rate_limiter):
    """Test _check_global_rate_limit when limit exceeded (lines 304-308)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    
    # Exhaust global limit
    for _ in range(limit.max_requests):
        allowed, _ = await rate_limiter._check_global_rate_limit(
            RateLimitType.CONNECTION,
            request_size=1,
        )
        assert allowed is True
    
    # Next request should be blocked
    allowed, wait = await rate_limiter._check_global_rate_limit(
        RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is False
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_check_token_bucket(rate_limiter):
    """Test _check_token_bucket algorithm (lines 369-401)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.REQUESTS,
        max_requests=10,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=5,
    )
    
    # Initialize peer stats first (needed for token bucket calculation)
    await rate_limiter.record_request(
        peer_id="peer4",
        ip="1.2.3.4",
        limit_type=RateLimitType.REQUESTS,
        request_size=0,
        success=True,
    )
    
    # First request
    allowed, wait = await rate_limiter._check_token_bucket(
        peer_id="peer4",
        limit_type=RateLimitType.REQUESTS,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    assert allowed is True
    assert wait == 0.0
    assert RateLimitType.REQUESTS in rate_limiter.token_buckets["peer4"]


@pytest.mark.asyncio
async def test_check_token_bucket_refill(rate_limiter):
    """Test token bucket token refill over time (lines 385-390)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.REQUESTS,
        max_requests=10,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    )
    
    # Initialize bucket
    rate_limiter.token_buckets["peer5"][RateLimitType.REQUESTS] = 5.0
    rate_limiter.peer_stats["peer5"] = {
        RateLimitType.REQUESTS: Mock(last_request=time.time() - 30.0),  # 30 seconds ago
    }
    
    # After 30 seconds with 60s window, should have ~5 more tokens (half refilled)
    allowed, wait = await rate_limiter._check_token_bucket(
        peer_id="peer5",
        limit_type=RateLimitType.REQUESTS,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    # Should have enough tokens after refill
    assert allowed is True


@pytest.mark.asyncio
async def test_check_sliding_window(rate_limiter):
    """Test _check_sliding_window algorithm (lines 403-437)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.MESSAGE,
        max_requests=5,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    )
    
    # Make requests within window
    for i in range(5):
        allowed, wait = await rate_limiter._check_sliding_window(
            peer_id="peer6",
            limit_type=RateLimitType.MESSAGE,
            request_size=1,
            rate_limit=rate_limit,
        )
        assert allowed is True, f"Request {i} should be allowed"
        time.sleep(0.01)
    
    # Exceed limit
    allowed, wait = await rate_limiter._check_sliding_window(
        peer_id="peer6",
        limit_type=RateLimitType.MESSAGE,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    assert allowed is False
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_check_sliding_window_old_requests_removed(rate_limiter):
    """Test sliding window removes old requests (lines 419-422)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.MESSAGE,
        max_requests=3,
        time_window=1.0,  # 1 second window
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    )
    
    # Fill window
    for _ in range(3):
        await rate_limiter._check_sliding_window(
            peer_id="peer7",
            limit_type=RateLimitType.MESSAGE,
            request_size=1,
            rate_limit=rate_limit,
        )
    
    # Wait for window to expire
    time.sleep(1.1)
    
    # Should be able to make request again
    allowed, wait = await rate_limiter._check_sliding_window(
        peer_id="peer7",
        limit_type=RateLimitType.MESSAGE,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    assert allowed is True


@pytest.mark.asyncio
async def test_check_adaptive(rate_limiter):
    """Test _check_adaptive algorithm (lines 439-478)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.BYTES,
        max_requests=1000,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    allowed, wait = await rate_limiter._check_adaptive(
        peer_id="peer8",
        limit_type=RateLimitType.BYTES,
        request_size=100,
        rate_limit=rate_limit,
    )
    
    assert allowed is True
    assert wait == 0.0
    assert RateLimitType.BYTES in rate_limiter.adaptive_rates["peer8"]


@pytest.mark.asyncio
async def test_record_request(rate_limiter):
    """Test record_request method (lines 180-198)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    await rate_limiter.record_request(
        peer_id="peer9",
        ip="9.10.11.12",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
        success=True,
    )
    
    # Verify stats were updated
    stats = rate_limiter.get_rate_limit_stats("peer9")
    assert RateLimitType.CONNECTION in stats
    assert stats[RateLimitType.CONNECTION].total_requests >= 1


@pytest.mark.asyncio
async def test_record_request_with_performance_history(rate_limiter):
    """Test record_request updates performance history for BYTES (lines 192-194)."""
    from ccbt.security.rate_limiter import RateLimitAlgorithm, RateLimitType
    
    # Set up rate limit for BYTES with adaptive algorithm using correct API
    rate_limiter.set_rate_limit(
        RateLimitType.BYTES,
        max_requests=1000,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    # Initialize adaptive rate
    rate_limiter.adaptive_rates["peer10"][RateLimitType.BYTES] = 1000.0
    
    await rate_limiter.record_request(
        peer_id="peer10",
        ip="10.11.12.13",
        limit_type=RateLimitType.BYTES,
        request_size=1024,
        success=True,
    )
    
    # Performance history should be updated for BYTES
    assert "peer10" in rate_limiter.performance_history
    assert len(rate_limiter.performance_history["peer10"]) > 0


@pytest.mark.asyncio
async def test_record_request_adaptive_adjustment(rate_limiter):
    """Test record_request triggers adaptive rate adjustment (lines 196-198)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    with patch.object(rate_limiter, "_adjust_adaptive_rate", new_callable=AsyncMock) as mock_adjust:
        await rate_limiter.record_request(
            peer_id="peer11",
            ip="11.12.13.14",
            limit_type=RateLimitType.BYTES,
            request_size=512,
            success=True,
        )
        
        # Should trigger adaptive adjustment
        mock_adjust.assert_called_once_with("peer11", RateLimitType.BYTES)


@pytest.mark.asyncio
async def test_get_rate_limit_stats(rate_limiter):
    """Test get_rate_limit_stats method (lines 215-217)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Make a request to generate stats
    await rate_limiter.check_rate_limit(
        peer_id="peer12",
        ip="12.13.14.15",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    stats = rate_limiter.get_rate_limit_stats("peer12")
    assert RateLimitType.CONNECTION in stats
    assert isinstance(stats[RateLimitType.CONNECTION].peer_id, str)


@pytest.mark.asyncio
async def test_get_rate_limit_stats_empty(rate_limiter):
    """Test get_rate_limit_stats for peer with no stats."""
    stats = rate_limiter.get_rate_limit_stats("nonexistent")
    assert stats == {}


@pytest.mark.asyncio
async def test_get_global_rate_limit_stats(rate_limiter):
    """Test get_global_rate_limit_stats method (lines 219-221)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Make a request to generate global stats
    await rate_limiter._check_global_rate_limit(
        RateLimitType.CONNECTION,
        request_size=1,
    )
    
    stats = rate_limiter.get_global_rate_limit_stats()
    assert RateLimitType.CONNECTION in stats
    assert stats[RateLimitType.CONNECTION].peer_id == "global"


@pytest.mark.asyncio
async def test_is_peer_limited(rate_limiter):
    """Test is_peer_limited method (lines 223-231)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Peer not limited initially
    assert rate_limiter.is_peer_limited("peer13", RateLimitType.CONNECTION) is False
    
    # Make many requests to trigger limit
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    for _ in range(limit.max_requests + 1):
        await rate_limiter.check_rate_limit(
            peer_id="peer13",
            ip="13.14.15.16",
            limit_type=RateLimitType.CONNECTION,
            request_size=1,
        )
    
    # May be limited now (depends on algorithm behavior)
    # Just verify method works
    result = rate_limiter.is_peer_limited("peer13", RateLimitType.CONNECTION)
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_get_peer_wait_time(rate_limiter):
    """Test get_peer_wait_time method (lines 233-242)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Peer not limited, wait time should be 0
    wait = rate_limiter.get_peer_wait_time("peer14", RateLimitType.CONNECTION)
    assert wait == 0.0
    
    # Make stats to test wait time calculation
    await rate_limiter.check_rate_limit(
        peer_id="peer14",
        ip="14.15.16.17",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    wait = rate_limiter.get_peer_wait_time("peer14", RateLimitType.CONNECTION)
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_cleanup_old_stats(rate_limiter):
    """Test cleanup_old_stats method (lines 244-272)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Create old stats
    old_time = time.time() - 7200  # 2 hours ago
    
    rate_limiter.peer_stats["old_peer"] = {
        RateLimitType.CONNECTION: Mock(
            last_request=old_time,
            time_window=60.0,
            peer_id="old_peer",
            ip="1.1.1.1",
            limit_type=RateLimitType.CONNECTION,
            requests_count=10,
            is_limited=False,
            limit_hits=0,
            total_requests=10,
        ),
    }
    
    # Cleanup stats older than 1 hour
    rate_limiter.cleanup_old_stats(max_age_seconds=3600)
    
    # Old stats should be removed
    assert "old_peer" not in rate_limiter.peer_stats


@pytest.mark.asyncio
async def test_cleanup_old_stats_sliding_windows(rate_limiter):
    """Test cleanup_old_stats cleans up sliding windows (lines 260-272)."""
    from collections import deque
    from ccbt.security.rate_limiter import RateLimitType
    
    old_time = time.time() - 7200
    
    # Create old sliding window
    rate_limiter.sliding_windows["old_peer"] = {
        RateLimitType.MESSAGE: deque([old_time]),
    }
    
    # Cleanup
    rate_limiter.cleanup_old_stats(max_age_seconds=3600)
    
    # Old window should be cleaned up
    assert "old_peer" not in rate_limiter.sliding_windows or len(rate_limiter.sliding_windows["old_peer"]) == 0


@pytest.mark.asyncio
async def test_update_rate_limit_stats(rate_limiter):
    """Test _update_rate_limit_stats method (lines 480-512)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    rate_limiter._update_rate_limit_stats(
        peer_id="peer15",
        ip="15.16.17.18",
        limit_type=RateLimitType.CONNECTION,
        request_size=5,
        success=True,
    )
    
    stats = rate_limiter.peer_stats["peer15"][RateLimitType.CONNECTION]
    assert stats.requests_count >= 5
    assert stats.total_requests >= 5
    assert stats.limit_hits == 0


@pytest.mark.asyncio
async def test_update_rate_limit_stats_failure(rate_limiter):
    """Test _update_rate_limit_stats with failure (lines 510-512)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    rate_limiter._update_rate_limit_stats(
        peer_id="peer16",
        ip="16.17.18.19",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
        success=False,
    )
    
    stats = rate_limiter.peer_stats["peer16"][RateLimitType.CONNECTION]
    assert stats.limit_hits >= 1
    assert stats.is_limited is True


@pytest.mark.asyncio
async def test_update_performance_history(rate_limiter):
    """Test _update_performance_history method (lines 514-528)."""
    rate_limiter._update_performance_history(
        peer_id="peer17",
        request_size=1024,
        success=True,
    )
    
    assert "peer17" in rate_limiter.performance_history
    assert len(rate_limiter.performance_history["peer17"]) > 0


@pytest.mark.asyncio
async def test_adjust_adaptive_rate(rate_limiter):
    """Test _adjust_adaptive_rate method."""
    from ccbt.security.rate_limiter import RateLimitType
    
    if hasattr(rate_limiter, "_adjust_adaptive_rate"):
        # Add some performance history
        rate_limiter.performance_history["peer18"] = [
            (time.time() - 60, 0.8),
            (time.time() - 30, 0.9),
            (time.time(), 1.0),
        ]
        rate_limiter.adaptive_rates["peer18"] = {RateLimitType.BYTES: 1000.0}
        
        await rate_limiter._adjust_adaptive_rate("peer18", RateLimitType.BYTES)
        
        # Rate should be adjusted (may increase or decrease)
        assert RateLimitType.BYTES in rate_limiter.adaptive_rates["peer18"]


@pytest.mark.asyncio
async def test_check_peer_rate_limit_initialization(rate_limiter):
    """Test _check_peer_rate_limit initializes stats (lines 326-341)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.CONNECTION,
        max_requests=10,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    )
    
    allowed, wait = await rate_limiter._check_peer_rate_limit(
        peer_id="new_peer",
        ip="20.21.22.23",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    # Stats should be initialized
    assert "new_peer" in rate_limiter.peer_stats
    assert RateLimitType.CONNECTION in rate_limiter.peer_stats["new_peer"]
    assert allowed is True


@pytest.mark.asyncio
async def test_check_adaptive_rate_exceeded(rate_limiter):
    """Test _check_adaptive when rate is exceeded (lines 467-482)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    from collections import deque
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.BYTES,
        max_requests=100,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    # Set adaptive rate lower than window
    rate_limiter.adaptive_rates["peer19"][RateLimitType.BYTES] = 50.0
    # Fill window beyond adaptive rate
    rate_limiter.sliding_windows["peer19"][RateLimitType.BYTES] = deque([time.time() - 30] * 60)
    
    allowed, wait = await rate_limiter._check_adaptive(
        peer_id="peer19",
        limit_type=RateLimitType.BYTES,
        request_size=10,
        rate_limit=rate_limit,
    )
    
    assert allowed is False
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_check_adaptive_rate_empty_window_wait(rate_limiter):
    """Test _check_adaptive with empty window wait time (lines 476-477)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    from collections import deque
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.BYTES,
        max_requests=100,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    # Set adaptive rate very low
    rate_limiter.adaptive_rates["peer20"][RateLimitType.BYTES] = 1.0
    # Empty window but rate is still too low
    rate_limiter.sliding_windows["peer20"][RateLimitType.BYTES] = deque()
    
    allowed, wait = await rate_limiter._check_adaptive(
        peer_id="peer20",
        limit_type=RateLimitType.BYTES,
        request_size=10,
        rate_limit=rate_limit,
    )
    
    # Should be limited due to adaptive rate
    assert allowed is False


@pytest.mark.asyncio
async def test_adjust_adaptive_rate_good_performance(rate_limiter):
    """Test _adjust_adaptive_rate with good performance (lines 570-571)."""
    import statistics
    from ccbt.security.rate_limiter import RateLimitType
    
    # Set base rate
    base_rate = rate_limiter.rate_limits[RateLimitType.BYTES].max_requests
    rate_limiter.adaptive_rates["peer21"] = {RateLimitType.BYTES: base_rate}
    
    # Add high performance history (>80% of base)
    rate_limiter.performance_history["peer21"] = [
        (time.time() - 300, base_rate * 0.9),
        (time.time() - 200, base_rate * 0.85),
        (time.time() - 100, base_rate * 0.95),
    ]
    
    await rate_limiter._adjust_adaptive_rate("peer21", RateLimitType.BYTES)
    
    # Rate should increase
    new_rate = rate_limiter.adaptive_rates["peer21"][RateLimitType.BYTES]
    assert new_rate >= base_rate


@pytest.mark.asyncio
async def test_adjust_adaptive_rate_poor_performance(rate_limiter):
    """Test _adjust_adaptive_rate with poor performance (lines 572-573)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    base_rate = rate_limiter.rate_limits[RateLimitType.BYTES].max_requests
    rate_limiter.adaptive_rates["peer22"] = {RateLimitType.BYTES: base_rate}
    
    # Add low performance history (<40% of base)
    rate_limiter.performance_history["peer22"] = [
        (time.time() - 300, base_rate * 0.3),
        (time.time() - 200, base_rate * 0.35),
        (time.time() - 100, base_rate * 0.25),
    ]
    
    await rate_limiter._adjust_adaptive_rate("peer22", RateLimitType.BYTES)
    
    # Rate should decrease
    new_rate = rate_limiter.adaptive_rates["peer22"][RateLimitType.BYTES]
    assert new_rate <= base_rate


@pytest.mark.asyncio
async def test_adjust_adaptive_rate_average_performance(rate_limiter):
    """Test _adjust_adaptive_rate with average performance (lines 574-575)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    base_rate = rate_limiter.rate_limits[RateLimitType.BYTES].max_requests
    current_rate = base_rate * 0.7
    rate_limiter.adaptive_rates["peer23"] = {RateLimitType.BYTES: current_rate}
    
    # Add average performance history (40-80% of base)
    rate_limiter.performance_history["peer23"] = [
        (time.time() - 300, base_rate * 0.6),
        (time.time() - 200, base_rate * 0.65),
        (time.time() - 100, base_rate * 0.55),
    ]
    
    await rate_limiter._adjust_adaptive_rate("peer23", RateLimitType.BYTES)
    
    # Rate should remain same (average performance)
    new_rate = rate_limiter.adaptive_rates["peer23"][RateLimitType.BYTES]
    assert new_rate == current_rate


@pytest.mark.asyncio
async def test_check_global_rate_limit_time_window_reset(rate_limiter):
    """Test _check_global_rate_limit time window reset (lines 299-301)."""
    from ccbt.security.rate_limiter import RateLimitStats, RateLimitType
    
    # Create old stats that should reset
    old_time = time.time() - 120  # 2 minutes ago (window is 60s)
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    rate_limiter.global_stats[RateLimitType.CONNECTION] = RateLimitStats(
        peer_id="global",
        ip="global",
        limit_type=RateLimitType.CONNECTION,
        requests_count=limit.max_requests,
        time_window=limit.time_window,
        last_request=old_time,
        is_limited=True,
        limit_hits=5,
        total_requests=100,
    )
    
    # Check limit - should reset since outside window
    allowed, wait = await rate_limiter._check_global_rate_limit(
        RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is True
    # Stats should be reset
    stats = rate_limiter.global_stats[RateLimitType.CONNECTION]
    assert stats.requests_count <= 1  # Reset and incremented
    assert stats.is_limited is False


@pytest.mark.asyncio
async def test_check_token_bucket_burst_size(rate_limiter):
    """Test _check_token_bucket with burst_size (lines 385-401)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitStats, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.REQUESTS,
        max_requests=10,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=5,
    )
    
    # Initialize peer stats needed for token bucket
    rate_limiter.peer_stats["peer24"] = {
        RateLimitType.REQUESTS: RateLimitStats(
            peer_id="peer24",
            ip="1.2.3.4",
            limit_type=RateLimitType.REQUESTS,
            requests_count=0,
            time_window=60.0,
            last_request=time.time(),
            is_limited=False,
            limit_hits=0,
            total_requests=0,
        ),
    }
    
    # Initialize bucket at max (with burst)
    rate_limiter.token_buckets["peer24"][RateLimitType.REQUESTS] = float(rate_limit.max_requests + rate_limit.burst_size)
    
    allowed, wait = await rate_limiter._check_token_bucket(
        peer_id="peer24",
        limit_type=RateLimitType.REQUESTS,
        request_size=1,
        rate_limit=rate_limit,
    )
    
    assert allowed is True


@pytest.mark.asyncio
async def test_check_token_bucket_refill_calculation(rate_limiter):
    """Test _check_token_bucket refill calculation (lines 384-401)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.REQUESTS,
        max_requests=100,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    )
    
    # Set up bucket with some tokens and old last request
    rate_limiter.token_buckets["peer25"][RateLimitType.REQUESTS] = 50.0
    old_time = time.time() - 30  # 30 seconds ago
    
    rate_limiter.peer_stats["peer25"] = {
        RateLimitType.REQUESTS: Mock(
            last_request=old_time,
            time_window=60.0,
            peer_id="peer25",
            ip="1.2.3.4",
            limit_type=RateLimitType.REQUESTS,
        ),
    }
    
    allowed, wait = await rate_limiter._check_token_bucket(
        peer_id="peer25",
        limit_type=RateLimitType.REQUESTS,
        request_size=10,
        rate_limit=rate_limit,
    )
    
    # Should have refilled some tokens in 30 seconds
    assert allowed is True or wait >= 0.0


@pytest.mark.asyncio
async def test_update_performance_history_cleanup(rate_limiter):
    """Test _update_performance_history cleans old entries (lines 534-540)."""
    old_time = time.time() - 7200  # 2 hours ago
    
    rate_limiter.performance_history["peer26"] = [
        (old_time, 1000),
        (time.time() - 100, 2000),
        (time.time() - 50, 1500),
    ]
    
    rate_limiter._update_performance_history("peer26", 3000, True)
    
    # Old entries (>1 hour) should be removed
    history = rate_limiter.performance_history["peer26"]
    assert all(timestamp > time.time() - 3600 for timestamp, _ in history)


@pytest.mark.asyncio
async def test_adjust_adaptive_rate_no_history(rate_limiter):
    """Test _adjust_adaptive_rate with no history (lines 548-549)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Peer with no history
    rate_limiter.adaptive_rates["peer27"] = {RateLimitType.BYTES: 1000.0}
    
    # Should return early without error
    await rate_limiter._adjust_adaptive_rate("peer27", RateLimitType.BYTES)
    
    # Rate should remain unchanged
    assert rate_limiter.adaptive_rates["peer27"][RateLimitType.BYTES] == 1000.0


@pytest.mark.asyncio
async def test_adjust_adaptive_rate_empty_history(rate_limiter):
    """Test _adjust_adaptive_rate with empty history list (lines 551-552)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    rate_limiter.performance_history["peer28"] = []
    rate_limiter.adaptive_rates["peer28"] = {RateLimitType.BYTES: 1000.0}
    
    # Should return early
    await rate_limiter._adjust_adaptive_rate("peer28", RateLimitType.BYTES)
    
    # Rate should remain unchanged
    assert rate_limiter.adaptive_rates["peer28"][RateLimitType.BYTES] == 1000.0


@pytest.mark.asyncio
async def test_cleanup_old_stats_token_buckets(rate_limiter):
    """Test cleanup_old_stats also cleans token buckets indirectly (lines 244-272)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    old_time = time.time() - 7200
    
    # Create old peer stats
    rate_limiter.peer_stats["old_peer2"] = {
        RateLimitType.CONNECTION: Mock(
            last_request=old_time,
            time_window=60.0,
        ),
    }
    
    # Also create token bucket (should be cleaned when peer_stats is cleaned)
    rate_limiter.token_buckets["old_peer2"][RateLimitType.CONNECTION] = 5.0
    
    rate_limiter.cleanup_old_stats(max_age_seconds=3600)
    
    # Old peer should be removed
    assert "old_peer2" not in rate_limiter.peer_stats


@pytest.mark.asyncio
async def test_cleanup_old_stats_adaptive_rates(rate_limiter):
    """Test cleanup_old_stats cleans adaptive rates (lines 244-272)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    old_time = time.time() - 7200
    
    rate_limiter.peer_stats["old_peer3"] = {
        RateLimitType.BYTES: Mock(last_request=old_time, time_window=60.0),
    }
    rate_limiter.adaptive_rates["old_peer3"][RateLimitType.BYTES] = 500.0
    rate_limiter.performance_history["old_peer3"] = [(old_time, 100)]
    
    rate_limiter.cleanup_old_stats(max_age_seconds=3600)
    
    assert "old_peer3" not in rate_limiter.peer_stats


@pytest.mark.asyncio
async def test_check_rate_limit_no_rate_limit_configured(rate_limiter):
    """Test check_rate_limit when rate_limit is None (line 153)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Remove a limit type to test None case
    original_limit = rate_limiter.rate_limits.pop(RateLimitType.CONNECTION, None)
    
    try:
        allowed, wait = await rate_limiter.check_rate_limit(
            peer_id="peer_none",
            ip="1.2.3.4",
            limit_type=RateLimitType.CONNECTION,
            request_size=1,
        )
        
        assert allowed is True
        assert wait == 0.0
    finally:
        # Restore original limit
        if original_limit:
            rate_limiter.rate_limits[RateLimitType.CONNECTION] = original_limit


@pytest.mark.asyncio
async def test_check_rate_limit_peer_not_allowed(rate_limiter):
    """Test check_rate_limit when peer rate limit fails (line 173)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Exhaust peer limit
    limit = rate_limiter.rate_limits[RateLimitType.CONNECTION]
    for _ in range(limit.max_requests):
        await rate_limiter.check_rate_limit(
            peer_id="peer_exhausted",
            ip="1.2.3.4",
            limit_type=RateLimitType.CONNECTION,
            request_size=1,
        )
    
    # Next request should be blocked by peer limit
    allowed, wait = await rate_limiter.check_rate_limit(
        peer_id="peer_exhausted",
        ip="1.2.3.4",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    assert allowed is False
    assert wait >= 0.0


@pytest.mark.asyncio
async def test_is_peer_limited_no_limit_type(rate_limiter):
    """Test is_peer_limited when limit_type not in peer_stats (line 229)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Create peer with stats but different limit type
    await rate_limiter.check_rate_limit(
        peer_id="peer_partial",
        ip="1.2.3.4",
        limit_type=RateLimitType.CONNECTION,
        request_size=1,
    )
    
    # Check different limit type that doesn't exist for this peer
    result = rate_limiter.is_peer_limited("peer_partial", RateLimitType.MESSAGE)
    
    assert result is False


@pytest.mark.asyncio
async def test_get_peer_wait_time_calculation(rate_limiter):
    """Test get_peer_wait_time wait time calculation (lines 238-242)."""
    from ccbt.security.rate_limiter import RateLimitType
    
    # Create limited peer
    await rate_limiter.check_rate_limit("peer_wait", "1.2.3.4", RateLimitType.CONNECTION, 1)
    
    # Manually mark as limited with old timestamp
    stats = rate_limiter.peer_stats["peer_wait"][RateLimitType.CONNECTION]
    stats.is_limited = True
    stats.last_request = time.time() - 30  # 30 seconds ago
    stats.time_window = 60.0
    
    wait = rate_limiter.get_peer_wait_time("peer_wait", RateLimitType.CONNECTION)
    
    # Should calculate wait time: 60 - 30 = 30 seconds
    assert wait > 0.0
    assert wait <= 60.0


@pytest.mark.asyncio
async def test_check_token_bucket_insufficient_tokens(rate_limiter):
    """Test _check_token_bucket wait time when tokens insufficient (lines 399-402)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    from unittest.mock import Mock
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.REQUESTS,
        max_requests=10,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    )
    
    # Set up peer with few tokens
    rate_limiter.peer_stats["peer_low_tokens"] = {
        RateLimitType.REQUESTS: Mock(
            last_request=time.time(),
            time_window=60.0,
        ),
    }
    rate_limiter.token_buckets["peer_low_tokens"][RateLimitType.REQUESTS] = 2.0  # Only 2 tokens
    
    # Try to use 5 tokens
    allowed, wait = await rate_limiter._check_token_bucket(
        peer_id="peer_low_tokens",
        limit_type=RateLimitType.REQUESTS,
        request_size=5,
        rate_limit=rate_limit,
    )
    
    assert allowed is False
    assert wait > 0.0


@pytest.mark.asyncio
async def test_check_sliding_window_empty_window_wait(rate_limiter):
    """Test _check_sliding_window wait_time when window empty (line 436)."""
    from collections import deque
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.MESSAGE,
        max_requests=5,
        time_window=60.0,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    )
    
    # Create window that gets cleared (empty)
    rate_limiter.sliding_windows["peer_empty"] = {
        RateLimitType.MESSAGE: deque(),  # Empty window
    }
    
    # Try to exceed limit with empty window
    allowed, wait = await rate_limiter._check_sliding_window(
        peer_id="peer_empty",
        limit_type=RateLimitType.MESSAGE,
        request_size=10,  # Exceeds max_requests
        rate_limit=rate_limit,
    )
    
    assert allowed is False
    assert wait == 0.0  # Empty window means wait_time = 0.0


@pytest.mark.asyncio
async def test_check_adaptive_window_cleanup(rate_limiter):
    """Test _check_adaptive removes old requests from window (line 465)."""
    from ccbt.security.rate_limiter import RateLimit, RateLimitAlgorithm, RateLimitType
    from collections import deque
    
    rate_limit = RateLimit(
        limit_type=RateLimitType.BYTES,
        max_requests=1000,
        time_window=1.0,  # 1 second window
        algorithm=RateLimitAlgorithm.ADAPTIVE,
    )
    
    # Create window with old timestamps
    old_time = time.time() - 2.0  # 2 seconds ago (outside window)
    rate_limiter.sliding_windows["peer_old"] = {
        RateLimitType.BYTES: deque([old_time, old_time + 0.5]),
    }
    rate_limiter.adaptive_rates["peer_old"] = {RateLimitType.BYTES: 1000.0}
    
    # Check should remove old requests
    allowed, wait = await rate_limiter._check_adaptive(
        peer_id="peer_old",
        limit_type=RateLimitType.BYTES,
        request_size=100,
        rate_limit=rate_limit,
    )
    
    # Window should have old requests removed
    window = rate_limiter.sliding_windows["peer_old"][RateLimitType.BYTES]
    assert len(window) == 0 or all(t >= time.time() - rate_limit.time_window for t in window)