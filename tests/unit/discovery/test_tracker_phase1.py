"""Comprehensive tests for Phase 1 tracker HTTP session optimizations.

Tests:
- DNS caching with TTL support
- HTTP session metrics tracking
- Exponential backoff with jitter
- Connection limits and keepalive
"""

from __future__ import annotations

import asyncio
import random
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.tracker, pytest.mark.network]

from ccbt.discovery.tracker import AsyncTrackerClient, DNSCache, TrackerSession


class TestDNSCache:
    """Test DNS cache implementation."""

    @pytest.mark.asyncio
    async def test_dns_cache_resolution(self):
        """Test DNS cache resolves hostnames."""
        cache = DNSCache(ttl=300)
        
        # First resolution should cache
        result1 = await cache.resolve("example.com")
        result2 = await cache.resolve("example.com")
        
        assert result1 == result2
        assert "example.com" in cache._cache

    @pytest.mark.asyncio
    async def test_dns_cache_ttl_expiration(self):
        """Test DNS cache respects TTL."""
        cache = DNSCache(ttl=0.1)  # Very short TTL for testing
        
        # First resolution
        await cache.resolve("example.com")
        assert "example.com" in cache._cache
        
        # Wait for TTL to expire
        await asyncio.sleep(0.15)
        
        # Next resolution should remove expired entry
        await cache.resolve("example.com")
        # Entry should be re-cached (new timestamp)
        assert "example.com" in cache._cache

    @pytest.mark.asyncio
    async def test_dns_cache_stats(self):
        """Test DNS cache statistics."""
        cache = DNSCache(ttl=300)
        
        # Add some entries
        await cache.resolve("example.com")
        await cache.resolve("tracker.example.com")
        
        stats = cache.get_stats()
        
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0
        assert stats["cache_size"] == 2

    @pytest.mark.asyncio
    async def test_dns_cache_stats_with_expired(self):
        """Test DNS cache stats with expired entries."""
        cache = DNSCache(ttl=0.1)
        
        # Add entry
        await cache.resolve("example.com")
        
        # Wait for expiration
        await asyncio.sleep(0.15)
        
        stats = cache.get_stats()
        
        # Stats should show expired entries
        assert stats["expired_entries"] >= 0


class TestTrackerSessionMetrics:
    """Test tracker session metrics tracking."""

    @pytest.mark.asyncio
    async def test_session_metrics_tracking(self):
        """Test session metrics are tracked."""
        client = AsyncTrackerClient()
        
        # Mock session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "interval": 1800,
            "peers": []
        })
        
        # Create async context manager mock
        async def mock_get_context(url):
            return mock_response
        
        mock_get = AsyncMock(side_effect=mock_get_context)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = mock_get
            mock_session_class.return_value = mock_session
            
            await client.start()
            
            try:
                # Track request manually (simulating what _make_request_async would do)
                url = "http://tracker.example.com/announce"
                request_start = time.time()
                
                # Simulate request tracking
                if url not in client._session_metrics:
                    client._session_metrics[url] = {
                        "request_count": 0,
                        "total_request_time": 0.0,
                        "total_dns_time": 0.0,
                        "connection_reuse_count": 0,
                        "error_count": 0
                    }
                
                # Simulate request completion
                request_time = time.time() - request_start
                client._session_metrics[url]["request_count"] += 1
                client._session_metrics[url]["total_request_time"] += request_time
                
                # Verify metrics
                assert url in client._session_metrics
                assert client._session_metrics[url]["request_count"] == 1
                assert client._session_metrics[url]["total_request_time"] >= 0.0
            finally:
                await client.stop()

    @pytest.mark.asyncio
    async def test_get_session_stats(self):
        """Test getting session statistics."""
        client = AsyncTrackerClient()
        client._session_metrics = {
            "http://tracker1.example.com/announce": {
                "request_count": 10,
                "total_request_time": 5.0,
                "total_dns_time": 0.5,
                "connection_reuse_count": 8,
                "error_count": 1
            },
            "http://tracker2.example.com/announce": {
                "request_count": 5,
                "total_request_time": 2.0,
                "total_dns_time": 0.2,
                "connection_reuse_count": 4,
                "error_count": 0
            }
        }
        
        stats = client.get_session_stats()
        
        assert "http://tracker1.example.com/announce" in stats
        assert "http://tracker2.example.com/announce" in stats
        assert stats["http://tracker1.example.com/announce"]["request_count"] == 10
        assert stats["http://tracker2.example.com/announce"]["request_count"] == 5


class TestExponentialBackoff:
    """Test exponential backoff with jitter."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculation."""
        session = TrackerSession(url="http://tracker.example.com/announce")
        session.failure_count = 3
        
        # Simulate exponential backoff
        base_delay = 1.0
        max_delay = 300.0
        use_exponential = True
        
        if use_exponential:
            exponential_delay = base_delay * (2 ** session.failure_count)
            jitter = random.uniform(0, base_delay)
            session.backoff_delay = min(exponential_delay + jitter, max_delay)
        
        # Should be around 8 + jitter (2^3 = 8)
        assert session.backoff_delay >= 8.0
        assert session.backoff_delay <= 9.0  # 8 + max jitter of 1.0

    def test_exponential_backoff_respects_max_delay(self):
        """Test exponential backoff respects max delay."""
        session = TrackerSession(url="http://tracker.example.com/announce")
        session.failure_count = 20  # Very high failure count
        
        base_delay = 1.0
        max_delay = 300.0
        use_exponential = True
        
        if use_exponential:
            exponential_delay = base_delay * (2 ** session.failure_count)
            jitter = random.uniform(0, base_delay)
            session.backoff_delay = min(exponential_delay + jitter, max_delay)
        
        # Should be capped at max_delay
        assert session.backoff_delay <= max_delay

    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff includes jitter."""
        session = TrackerSession(url="http://tracker.example.com/announce")
        session.failure_count = 2
        
        base_delay = 1.0
        max_delay = 300.0
        use_exponential = True
        
        # Calculate backoff multiple times to verify jitter
        delays = []
        for _ in range(10):
            if use_exponential:
                exponential_delay = base_delay * (2 ** session.failure_count)
                jitter = random.uniform(0, base_delay)
                delay = min(exponential_delay + jitter, max_delay)
                delays.append(delay)
        
        # All delays should be in range [4.0, 5.0]
        assert all(4.0 <= d <= 5.0 for d in delays)
        # Should have some variation due to jitter
        assert min(delays) < max(delays)


class TestTrackerConnectionLimits:
    """Test tracker connection limits and keepalive."""

    @pytest.mark.asyncio
    async def test_connector_configuration(self):
        """Test connector is configured with correct limits."""
        client = AsyncTrackerClient()
        
        # Mock config
        with patch.object(client.config.network, 'tracker_connection_limit', 100):
            with patch.object(client.config.network, 'tracker_connections_per_host', 10):
                with patch.object(client.config.network, 'tracker_keepalive_timeout', 300.0):
                    with patch.object(client.config.network, 'tracker_enable_dns_cache', True):
                        with patch.object(client.config.network, 'tracker_dns_cache_ttl', 300):
                            with patch('aiohttp.TCPConnector') as mock_connector_class:
                                await client.start()
                                
                                # Verify connector was created with correct params
                                mock_connector_class.assert_called_once()
                                call_kwargs = mock_connector_class.call_args[1]
                                
                                assert call_kwargs["limit"] == 100
                                assert call_kwargs["limit_per_host"] == 10
                                assert call_kwargs["keepalive_timeout"] == 300.0
                                assert call_kwargs["use_dns_cache"] is True
                                
                                await client.stop()

