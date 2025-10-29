"""Tests for ML adaptive limiter."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from ccbt.ml.adaptive_limiter import (
    AdaptiveLimiter,
    BandwidthEstimate,
    CongestionControl,
    CongestionState,
    LimiterType,
    RateLimit,
)


class TestAdaptiveLimiter:
    """Test cases for AdaptiveLimiter."""

    @pytest.fixture
    def limiter(self):
        """Create an AdaptiveLimiter instance."""
        return AdaptiveLimiter()

    @pytest.mark.asyncio
    async def test_estimate_bandwidth_empty_samples(self, limiter):
        """Test bandwidth estimation with empty samples."""
        result = await limiter.estimate_bandwidth("peer1", [])
        
        assert result.estimated_bandwidth == 0.0
        assert result.confidence == 0.0
        assert result.sample_count == 0
        assert result.variance == 0.0

    @pytest.mark.asyncio
    async def test_estimate_bandwidth_single_sample(self, limiter):
        """Test bandwidth estimation with single sample."""
        samples = [(time.time(), 1000)]
        result = await limiter.estimate_bandwidth("peer1", samples)
        
        assert result.estimated_bandwidth == 0.0
        assert result.confidence == 0.0
        assert result.sample_count == 0

    @pytest.mark.asyncio
    async def test_estimate_bandwidth_valid_samples(self, limiter):
        """Test bandwidth estimation with valid samples."""
        current_time = time.time()
        samples = [
            (current_time, 0),
            (current_time + 1.0, 1024),  # 1KB in 1 second = 1KB/s
            (current_time + 2.0, 2048),  # 1KB in 1 second = 1KB/s
        ]
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await limiter.estimate_bandwidth("peer1", samples)
        
        assert result.estimated_bandwidth == 1024.0  # 1KB/s
        assert result.confidence > 0.0
        assert result.sample_count == 2
        assert result.variance == 0.0  # Same bandwidth for both samples

    @pytest.mark.asyncio
    async def test_estimate_bandwidth_variable_samples(self, limiter):
        """Test bandwidth estimation with variable samples."""
        current_time = time.time()
        samples = [
            (current_time, 0),
            (current_time + 1.0, 1000),  # 1KB/s
            (current_time + 2.0, 3000),  # 2KB/s
            (current_time + 3.0, 6000),  # 3KB/s
        ]
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await limiter.estimate_bandwidth("peer1", samples)
        
        assert result.estimated_bandwidth == 2000.0  # Average of 1KB/s and 2KB/s
        assert result.confidence > 0.0
        assert result.sample_count == 3
        assert result.variance > 0.0  # Should have variance

    @pytest.mark.asyncio
    async def test_adjust_rate_limit_new_peer(self, limiter):
        """Test rate limit adjustment for new peer."""
        performance = {"error_rate": 0.1, "latency": 0.05, "throughput": 1000}
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            new_rate = await limiter.adjust_rate_limit(
                "peer1", LimiterType.PER_PEER, performance
            )
        
        # Should return default rate since no bandwidth estimate exists
        assert new_rate == 1024 * 1024  # 1MB/s default

    @pytest.mark.asyncio
    async def test_adjust_rate_limit_with_bandwidth_estimate(self, limiter):
        """Test rate limit adjustment with bandwidth estimate."""
        # First create a bandwidth estimate
        current_time = time.time()
        samples = [
            (current_time, 0),
            (current_time + 1.0, 2048),  # 2KB/s
        ]
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            await limiter.estimate_bandwidth("peer1", samples)
            
            performance = {"error_rate": 0.1, "latency": 0.05, "throughput": 1000}
            new_rate = await limiter.adjust_rate_limit(
                "peer1", LimiterType.PER_PEER, performance
            )
        
        assert new_rate > 0
        assert new_rate <= 1024 * 1024  # Should not exceed max rate

    @pytest.mark.asyncio
    async def test_update_congestion_control_new_peer(self, limiter):
        """Test congestion control update for new peer."""
        congestion_data = {
            "rtt": 0.1,
            "packet_loss": 0.05,
            "congestion_event": "packet_loss"
        }
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            await limiter.update_congestion_control("peer1", congestion_data)
        
        state = limiter.get_congestion_state("peer1")
        assert state is not None
        assert state.rtt == 0.1
        assert state.packet_loss_rate == 0.05
        assert state.in_recovery is True

    @pytest.mark.asyncio
    async def test_update_congestion_control_existing_peer(self, limiter):
        """Test congestion control update for existing peer."""
        # Create initial state
        congestion_data = {"rtt": 0.1, "packet_loss": 0.05}
        await limiter.update_congestion_control("peer1", congestion_data)
        
        # Update with new data
        new_congestion_data = {
            "rtt": 0.2,
            "packet_loss": 0.1,
            "congestion_event": "timeout"
        }
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            await limiter.update_congestion_control("peer1", new_congestion_data)
        
        state = limiter.get_congestion_state("peer1")
        assert state.rtt == 0.2
        assert state.packet_loss_rate == 0.1
        assert state.in_recovery is True

    @pytest.mark.asyncio
    async def test_implement_fair_queuing_empty_peers(self, limiter):
        """Test fair queuing with empty peer list."""
        result = await limiter.implement_fair_queuing([], 1000)
        assert result == {}

    @pytest.mark.asyncio
    async def test_implement_fair_queuing_single_peer(self, limiter):
        """Test fair queuing with single peer."""
        result = await limiter.implement_fair_queuing(["peer1"], 1000)
        assert result["peer1"] == 1000.0

    @pytest.mark.asyncio
    async def test_implement_fair_queuing_multiple_peers(self, limiter):
        """Test fair queuing with multiple peers."""
        peers = ["peer1", "peer2", "peer3"]
        total_bandwidth = 3000
        
        result = await limiter.implement_fair_queuing(peers, total_bandwidth)
        
        assert len(result) == 3
        assert sum(result.values()) == total_bandwidth
        # Each peer should get equal share initially
        assert result["peer1"] == 1000.0
        assert result["peer2"] == 1000.0
        assert result["peer3"] == 1000.0

    @pytest.mark.asyncio
    async def test_implement_fair_queuing_with_performance_history(self, limiter):
        """Test fair queuing with performance history."""
        # Add performance history for peer1
        limiter.performance_history["peer1"] = [500, 600, 700]  # Good performance
        limiter.performance_history["peer2"] = [100, 150, 200]  # Poor performance
        
        peers = ["peer1", "peer2"]
        total_bandwidth = 2000
        
        result = await limiter.implement_fair_queuing(peers, total_bandwidth)
        
        assert len(result) == 2
        assert sum(result.values()) == total_bandwidth
        # peer1 should get more bandwidth due to better performance
        assert result["peer1"] > result["peer2"]

    def test_get_rate_limit_existing(self, limiter):
        """Test getting existing rate limit."""
        # Create a rate limit
        limiter.rate_limits["peer1_per_peer"] = RateLimit(
            limiter_type=LimiterType.PER_PEER,
            max_rate=1024 * 1024,
            current_rate=512 * 1024
        )
        
        result = limiter.get_rate_limit("peer1", LimiterType.PER_PEER)
        assert result is not None
        assert result.current_rate == 512 * 1024

    def test_get_rate_limit_nonexistent(self, limiter):
        """Test getting non-existent rate limit."""
        result = limiter.get_rate_limit("peer1", LimiterType.PER_PEER)
        assert result is None

    def test_get_bandwidth_estimate_existing(self, limiter):
        """Test getting existing bandwidth estimate."""
        estimate = BandwidthEstimate(
            estimated_bandwidth=1024.0,
            confidence=0.8,
            measurement_time=time.time(),
            sample_count=10,
            variance=0.1
        )
        limiter.bandwidth_estimates["peer1"] = estimate
        
        result = limiter.get_bandwidth_estimate("peer1")
        assert result is not None
        assert result.estimated_bandwidth == 1024.0

    def test_get_bandwidth_estimate_nonexistent(self, limiter):
        """Test getting non-existent bandwidth estimate."""
        result = limiter.get_bandwidth_estimate("peer1")
        assert result is None

    def test_get_congestion_state_existing(self, limiter):
        """Test getting existing congestion state."""
        state = CongestionState(
            cwnd=10.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time()
        )
        limiter.congestion_states["peer1"] = state
        
        result = limiter.get_congestion_state("peer1")
        assert result is not None
        assert result.cwnd == 10.0

    def test_get_congestion_state_nonexistent(self, limiter):
        """Test getting non-existent congestion state."""
        result = limiter.get_congestion_state("peer1")
        assert result is None

    def test_get_ml_statistics(self, limiter):
        """Test getting ML statistics."""
        # Add some data
        limiter.bandwidth_estimates["peer1"] = BandwidthEstimate(
            estimated_bandwidth=1024.0,
            confidence=0.8,
            measurement_time=time.time(),
            sample_count=10,
            variance=0.1
        )
        limiter.rate_limits["peer1_per_peer"] = RateLimit(
            limiter_type=LimiterType.PER_PEER,
            max_rate=1024 * 1024
        )
        
        stats = limiter.get_ml_statistics()
        
        assert "total_adjustments" in stats
        assert "successful_adjustments" in stats
        assert "bandwidth_estimates" in stats
        assert "congestion_events" in stats
        assert "tracked_peers" in stats
        assert "active_rate_limits" in stats
        assert stats["tracked_peers"] == 1
        assert stats["active_rate_limits"] == 1

    def test_cleanup_old_data(self, limiter):
        """Test cleanup of old data."""
        current_time = time.time()
        old_time = current_time - 4000  # 4000 seconds ago
        
        # Add old bandwidth estimate
        old_estimate = BandwidthEstimate(
            estimated_bandwidth=1024.0,
            confidence=0.8,
            measurement_time=old_time,
            sample_count=10,
            variance=0.1
        )
        limiter.bandwidth_estimates["old_peer"] = old_estimate
        
        # Add recent bandwidth estimate
        recent_estimate = BandwidthEstimate(
            estimated_bandwidth=2048.0,
            confidence=0.9,
            measurement_time=current_time,
            sample_count=20,
            variance=0.05
        )
        limiter.bandwidth_estimates["recent_peer"] = recent_estimate
        
        # Add performance history for old peer
        limiter.performance_history["old_peer"] = [100, 200, 300]
        
        # Cleanup data older than 1 hour
        limiter.cleanup_old_data(max_age_seconds=3600)
        
        # Old peer should be removed
        assert "old_peer" not in limiter.bandwidth_estimates
        assert "old_peer" not in limiter.performance_history
        
        # Recent peer should remain
        assert "recent_peer" in limiter.bandwidth_estimates

    @pytest.mark.asyncio
    async def test_calculate_adaptive_rate(self, limiter):
        """Test adaptive rate calculation."""
        rate_limit = RateLimit(
            limiter_type=LimiterType.PER_PEER,
            max_rate=1024 * 1024,
            current_rate=512 * 1024
        )
        
        bandwidth_estimate = BandwidthEstimate(
            estimated_bandwidth=1024.0,
            confidence=0.8,
            measurement_time=time.time(),
            sample_count=10,
            variance=0.1
        )
        
        congestion_state = CongestionState(
            cwnd=10.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=False
        )
        
        performance = {"error_rate": 0.1, "latency": 0.05, "throughput": 1000}
        
        new_rate = await limiter._calculate_adaptive_rate(
            rate_limit, bandwidth_estimate, congestion_state, performance
        )
        
        assert new_rate > 0
        assert new_rate <= rate_limit.max_rate
        assert new_rate >= 1024  # Minimum rate

    def test_calculate_congestion_factor_recovery(self, limiter):
        """Test congestion factor calculation in recovery."""
        state = CongestionState(
            cwnd=5.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=True
        )
        
        factor = limiter._calculate_congestion_factor(state)
        assert factor == 0.5

    def test_calculate_congestion_factor_slow_start(self, limiter):
        """Test congestion factor calculation in slow start."""
        state = CongestionState(
            cwnd=10.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=False
        )
        
        factor = limiter._calculate_congestion_factor(state)
        assert factor < 1.0
        assert factor > 0.0

    def test_calculate_congestion_factor_congestion_avoidance(self, limiter):
        """Test congestion factor calculation in congestion avoidance."""
        state = CongestionState(
            cwnd=100.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=False
        )
        
        factor = limiter._calculate_congestion_factor(state)
        assert factor == 0.8

    def test_calculate_performance_factor(self, limiter):
        """Test performance factor calculation."""
        performance = {
            "error_rate": 0.1,
            "latency": 0.05,
            "throughput": 1000
        }
        
        factor = limiter._calculate_performance_factor(performance)
        assert factor > 0.0
        assert factor <= 2.0

    def test_calculate_fairness_factor_high_utilization(self, limiter):
        """Test fairness factor calculation with high utilization."""
        rate_limit = RateLimit(
            limiter_type=LimiterType.PER_PEER,
            max_rate=1000,
            current_rate=900  # 90% utilization
        )
        
        factor = limiter._calculate_fairness_factor(rate_limit)
        assert factor < 1.0

    def test_calculate_fairness_factor_low_utilization(self, limiter):
        """Test fairness factor calculation with low utilization."""
        rate_limit = RateLimit(
            limiter_type=LimiterType.PER_PEER,
            max_rate=1000,
            current_rate=100  # 10% utilization
        )
        
        factor = limiter._calculate_fairness_factor(rate_limit)
        assert factor > 1.0

    @pytest.mark.asyncio
    async def test_handle_congestion_event_packet_loss(self, limiter):
        """Test handling packet loss congestion event."""
        state = CongestionState(
            cwnd=20.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=0.0,
            recovery_start_time=0.0,
            in_recovery=False
        )
        
        await limiter._handle_congestion_event("peer1", state, "packet_loss")
        
        assert state.cwnd == 10.0  # Should be halved
        assert state.ssthresh == 10.0  # Should be set to cwnd
        assert state.in_recovery is True
        assert state.last_loss_time > 0
        assert state.recovery_start_time > 0

    @pytest.mark.asyncio
    async def test_handle_congestion_event_timeout(self, limiter):
        """Test handling timeout congestion event."""
        state = CongestionState(
            cwnd=20.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=0.0,
            recovery_start_time=0.0,
            in_recovery=False
        )
        
        await limiter._handle_congestion_event("peer1", state, "timeout")
        
        assert state.cwnd == 1.0  # Should be reset
        assert state.ssthresh == 2.0  # Should be max(2.0, cwnd * 0.5) = max(2.0, 1.0 * 0.5) = 2.0
        assert state.in_recovery is True
        assert state.recovery_start_time > 0

    @pytest.mark.asyncio
    async def test_handle_congestion_event_duplicate_ack(self, limiter):
        """Test handling duplicate ACK congestion event."""
        state = CongestionState(
            cwnd=20.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=0.0,
            recovery_start_time=0.0,
            in_recovery=False
        )
        
        await limiter._handle_congestion_event("peer1", state, "duplicate_ack")
        
        assert state.cwnd == 10.0  # Should be halved
        assert state.in_recovery is True
        assert state.recovery_start_time > 0

    @pytest.mark.asyncio
    async def test_update_congestion_window_slow_start(self, limiter):
        """Test congestion window update in slow start."""
        state = CongestionState(
            cwnd=10.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=False
        )
        
        await limiter._update_congestion_window("peer1", state, {})
        
        assert state.cwnd == 20.0  # Should double in slow start

    @pytest.mark.asyncio
    async def test_update_congestion_window_congestion_avoidance(self, limiter):
        """Test congestion window update in congestion avoidance."""
        state = CongestionState(
            cwnd=100.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time(),
            in_recovery=False
        )
        
        await limiter._update_congestion_window("peer1", state, {})
        
        assert state.cwnd == 100.01  # Should increase by 1/cwnd = 1/100 = 0.01

    @pytest.mark.asyncio
    async def test_update_congestion_window_recovery(self, limiter):
        """Test congestion window update in recovery."""
        state = CongestionState(
            cwnd=10.0,
            ssthresh=64.0,
            rtt=0.1,
            rtt_variance=0.01,
            packet_loss_rate=0.05,
            last_loss_time=time.time(),
            recovery_start_time=time.time() - 0.5,  # Recovery started 0.5s ago
            in_recovery=True
        )
        
        await limiter._update_congestion_window("peer1", state, {})
        
        # Should exit recovery after 3 RTTs (0.3s)
        assert state.in_recovery is False
