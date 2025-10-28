"""Adaptive Rate Limiter for ccBitTorrent.

from __future__ import annotations

Provides ML-based adaptive rate limiting including:
- Bandwidth estimation
- Congestion control algorithms
- Fair queuing
- Dynamic rate adjustment
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ccbt.events import Event, EventType, emit_event


class LimiterType(Enum):
    """Types of rate limiters."""

    GLOBAL = "global"
    PER_PEER = "per_peer"
    PER_TORRENT = "per_torrent"
    PER_CONNECTION = "per_connection"


class CongestionControl(Enum):
    """Congestion control algorithms."""

    TCP_RENO = "tcp_reno"
    TCP_CUBIC = "tcp_cubic"
    BBR = "bbr"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimit:
    """Rate limit configuration."""

    limiter_type: LimiterType
    max_rate: float  # bytes per second
    current_rate: float = 0.0
    burst_size: float = 0.0
    congestion_window: float = 1.0
    rtt: float = 0.0
    packet_loss: float = 0.0
    last_update: float = 0.0


@dataclass
class BandwidthEstimate:
    """Bandwidth estimation."""

    estimated_bandwidth: float
    confidence: float
    measurement_time: float
    sample_count: int
    variance: float


@dataclass
class CongestionState:
    """Congestion control state."""

    cwnd: float  # Congestion window
    ssthresh: float  # Slow start threshold
    rtt: float  # Round trip time
    rtt_variance: float
    packet_loss_rate: float
    last_loss_time: float
    recovery_start_time: float
    in_recovery: bool = False


class AdaptiveLimiter:
    """ML-based adaptive rate limiter."""

    def __init__(self):
        """Initialize adaptive rate limiter."""
        self.rate_limits: dict[str, RateLimit] = {}
        self.bandwidth_estimates: dict[str, BandwidthEstimate] = {}
        self.congestion_states: dict[str, CongestionState] = {}

        # ML models
        self.bandwidth_model: dict[str, Any] = {}
        self.congestion_model: dict[str, Any] = {}
        self.fairness_model: dict[str, Any] = {}

        # Learning parameters
        self.learning_rate = 0.01
        self.min_samples = 10
        self.max_samples = 1000

        # Performance tracking
        self.performance_history: dict[str, list[float]] = defaultdict(list)
        self.rate_adjustments: dict[str, list[float]] = defaultdict(list)

        # Statistics
        self.stats = {
            "total_adjustments": 0,
            "successful_adjustments": 0,
            "bandwidth_estimates": 0,
            "congestion_events": 0,
        }

    async def estimate_bandwidth(
        self,
        peer_id: str,
        samples: list[tuple[float, float]],
    ) -> BandwidthEstimate:
        """Estimate bandwidth using ML.

        Args:
            peer_id: Peer identifier
            samples: List of (time, bytes) samples

        Returns:
            Bandwidth estimate
        """
        if len(samples) < 2:
            return BandwidthEstimate(
                estimated_bandwidth=0.0,
                confidence=0.0,
                measurement_time=time.time(),
                sample_count=0,
                variance=0.0,
            )

        # Calculate bandwidth from samples
        bandwidths = []
        for i in range(1, len(samples)):
            time_diff = samples[i][0] - samples[i - 1][0]
            bytes_diff = samples[i][1] - samples[i - 1][1]

            if time_diff > 0:
                bandwidth = bytes_diff / time_diff
                bandwidths.append(bandwidth)

        if not bandwidths:
            return BandwidthEstimate(
                estimated_bandwidth=0.0,
                confidence=0.0,
                measurement_time=time.time(),
                sample_count=0,
                variance=0.0,
            )

        # Calculate statistics
        estimated_bandwidth = statistics.mean(bandwidths)
        variance = statistics.variance(bandwidths) if len(bandwidths) > 1 else 0.0
        confidence = min(
            1.0,
            len(bandwidths) / 10.0,
        )  # More samples = higher confidence

        # Create bandwidth estimate
        estimate = BandwidthEstimate(
            estimated_bandwidth=estimated_bandwidth,
            confidence=confidence,
            measurement_time=time.time(),
            sample_count=len(bandwidths),
            variance=variance,
        )

        # Store estimate
        self.bandwidth_estimates[peer_id] = estimate

        # Update statistics
        self.stats["bandwidth_estimates"] += 1

        # Emit bandwidth estimate event
        await emit_event(
            Event(
                event_type=EventType.ML_BANDWIDTH_ESTIMATED.value,
                data={
                    "peer_id": peer_id,
                    "estimated_bandwidth": estimated_bandwidth,
                    "confidence": confidence,
                    "sample_count": len(bandwidths),
                    "variance": variance,
                    "timestamp": time.time(),
                },
            ),
        )

        return estimate

    async def adjust_rate_limit(
        self,
        peer_id: str,
        limiter_type: LimiterType,
        current_performance: dict[str, Any],
    ) -> float:
        """Adjust rate limit using ML.

        Args:
            peer_id: Peer identifier
            limiter_type: Type of rate limiter
            current_performance: Current performance metrics

        Returns:
            New rate limit
        """
        limiter_key = f"{peer_id}_{limiter_type.value}"

        # Get current rate limit
        if limiter_key not in self.rate_limits:
            self.rate_limits[limiter_key] = RateLimit(
                limiter_type=limiter_type,
                max_rate=1024 * 1024,  # 1MB/s default
                current_rate=1024 * 1024,
            )

        rate_limit = self.rate_limits[limiter_key]

        # Get bandwidth estimate
        bandwidth_estimate = self.bandwidth_estimates.get(peer_id)
        if not bandwidth_estimate:
            return rate_limit.current_rate

        # Get congestion state
        congestion_state = self.congestion_states.get(peer_id)
        if not congestion_state:
            congestion_state = CongestionState(
                cwnd=1.0,
                ssthresh=64.0,
                rtt=0.1,
                rtt_variance=0.01,
                packet_loss_rate=0.0,
                last_loss_time=0.0,
                recovery_start_time=0.0,
            )
            self.congestion_states[peer_id] = congestion_state

        # Calculate new rate limit
        new_rate = await self._calculate_adaptive_rate(
            rate_limit,
            bandwidth_estimate,
            congestion_state,
            current_performance,
        )

        # Update rate limit
        old_rate = rate_limit.current_rate
        rate_limit.current_rate = new_rate
        rate_limit.last_update = time.time()

        # Record rate adjustment
        self.rate_adjustments[peer_id].append(new_rate)
        if len(self.rate_adjustments[peer_id]) > self.max_samples:
            self.rate_adjustments[peer_id] = self.rate_adjustments[peer_id][
                -self.max_samples :
            ]

        # Update statistics
        self.stats["total_adjustments"] += 1

        # Emit rate adjustment event
        await emit_event(
            Event(
                event_type=EventType.ML_RATE_ADJUSTED.value,
                data={
                    "peer_id": peer_id,
                    "limiter_type": limiter_type.value,
                    "old_rate": old_rate,
                    "new_rate": new_rate,
                    "bandwidth_estimate": bandwidth_estimate.estimated_bandwidth,
                    "congestion_window": congestion_state.cwnd,
                    "timestamp": time.time(),
                },
            ),
        )

        return new_rate

    async def update_congestion_control(
        self,
        peer_id: str,
        congestion_data: dict[str, Any],
    ) -> None:
        """Update congestion control state.

        Args:
            peer_id: Peer identifier
            congestion_data: Congestion control data
        """
        if peer_id not in self.congestion_states:
            self.congestion_states[peer_id] = CongestionState(
                cwnd=1.0,
                ssthresh=64.0,
                rtt=0.1,
                rtt_variance=0.01,
                packet_loss_rate=0.0,
                last_loss_time=0.0,
                recovery_start_time=0.0,
            )

        state = self.congestion_states[peer_id]

        # Update RTT
        if "rtt" in congestion_data:
            old_rtt = state.rtt
            new_rtt = congestion_data["rtt"]
            state.rtt = new_rtt
            state.rtt_variance = abs(new_rtt - old_rtt)

        # Update packet loss rate
        if "packet_loss" in congestion_data:
            state.packet_loss_rate = congestion_data["packet_loss"]

        # Handle congestion events
        if "congestion_event" in congestion_data:
            await self._handle_congestion_event(
                peer_id,
                state,
                congestion_data["congestion_event"],
            )

        # Update congestion window
        await self._update_congestion_window(peer_id, state, congestion_data)

        # Update statistics
        self.stats["congestion_events"] += 1

    async def implement_fair_queuing(
        self,
        peers: list[str],
        total_bandwidth: float,
    ) -> dict[str, float]:
        """Implement fair queuing across peers.

        Args:
            peers: List of peer identifiers
            total_bandwidth: Total available bandwidth

        Returns:
            Dictionary of peer_id -> allocated_bandwidth
        """
        if not peers:
            return {}

        # Calculate fair share
        fair_share = total_bandwidth / len(peers)

        # Allocate bandwidth based on peer performance
        allocations = {}
        for peer_id in peers:
            # Get peer performance
            performance = self.performance_history.get(peer_id, [])
            if not performance:
                # Default allocation for new peers
                allocations[peer_id] = fair_share
                continue

            # Calculate performance score
            avg_performance = (
                statistics.mean(performance[-10:])
                if len(performance) >= 10
                else statistics.mean(performance)
            )
            performance_score = min(1.0, avg_performance / 1000.0)  # Normalize to 0-1

            # Allocate bandwidth based on performance
            allocated_bandwidth = fair_share * (0.5 + 0.5 * performance_score)
            allocations[peer_id] = allocated_bandwidth

        # Normalize allocations to total bandwidth
        total_allocated = sum(allocations.values())
        if total_allocated > 0:
            scale_factor = total_bandwidth / total_allocated
            for peer_id in allocations:
                allocations[peer_id] *= scale_factor

        return allocations

    def get_rate_limit(
        self,
        peer_id: str,
        limiter_type: LimiterType,
    ) -> RateLimit | None:
        """Get rate limit for a peer."""
        limiter_key = f"{peer_id}_{limiter_type.value}"
        return self.rate_limits.get(limiter_key)

    def get_bandwidth_estimate(self, peer_id: str) -> BandwidthEstimate | None:
        """Get bandwidth estimate for a peer."""
        return self.bandwidth_estimates.get(peer_id)

    def get_congestion_state(self, peer_id: str) -> CongestionState | None:
        """Get congestion state for a peer."""
        return self.congestion_states.get(peer_id)

    def get_ml_statistics(self) -> dict[str, Any]:
        """Get ML statistics."""
        return {
            "total_adjustments": self.stats["total_adjustments"],
            "successful_adjustments": self.stats["successful_adjustments"],
            "bandwidth_estimates": self.stats["bandwidth_estimates"],
            "congestion_events": self.stats["congestion_events"],
            "tracked_peers": len(self.bandwidth_estimates),
            "active_rate_limits": len(self.rate_limits),
        }

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> None:
        """Clean up old ML data."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up old bandwidth estimates
        to_remove = []
        for peer_id, estimate in self.bandwidth_estimates.items():
            if estimate.measurement_time < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.bandwidth_estimates[peer_id]

        # Clean up old performance history
        for peer_id in list(self.performance_history.keys()):
            if peer_id not in self.bandwidth_estimates:
                del self.performance_history[peer_id]

    async def _calculate_adaptive_rate(
        self,
        rate_limit: RateLimit,
        bandwidth_estimate: BandwidthEstimate,
        congestion_state: CongestionState,
        performance: dict[str, Any],
    ) -> float:
        """Calculate adaptive rate limit."""
        # Base rate from bandwidth estimate
        base_rate = (
            bandwidth_estimate.estimated_bandwidth * bandwidth_estimate.confidence
        )

        # Apply congestion control
        congestion_factor = self._calculate_congestion_factor(congestion_state)
        base_rate *= congestion_factor

        # Apply performance adjustments
        performance_factor = self._calculate_performance_factor(performance)
        base_rate *= performance_factor

        # Apply fairness constraints
        fairness_factor = self._calculate_fairness_factor(rate_limit)
        base_rate *= fairness_factor

        # Ensure rate is within reasonable bounds
        min_rate = 1024  # 1KB/s minimum
        max_rate = rate_limit.max_rate

        return max(min_rate, min(max_rate, base_rate))

    def _calculate_congestion_factor(self, congestion_state: CongestionState) -> float:
        """Calculate congestion control factor."""
        # TCP-like congestion control
        if congestion_state.in_recovery:
            # Recovery phase - slow growth
            return 0.5
        if congestion_state.cwnd < congestion_state.ssthresh:
            # Slow start phase
            return min(1.0, congestion_state.cwnd / congestion_state.ssthresh)
        # Congestion avoidance phase
        return 0.8

    def _calculate_performance_factor(self, performance: dict[str, Any]) -> float:
        """Calculate performance-based adjustment factor."""
        # This is a simplified calculation
        # In a real implementation, this would use more sophisticated ML

        # Get performance metrics
        error_rate = performance.get("error_rate", 0.0)
        latency = performance.get("latency", 0.1)
        throughput = performance.get("throughput", 0.0)

        # Calculate performance score
        error_factor = 1.0 - error_rate
        latency_factor = 1.0 / (1.0 + latency)
        throughput_factor = min(1.0, throughput / 1000.0)  # Normalize to 1MB/s

        # Combined performance factor
        performance_factor = (error_factor + latency_factor + throughput_factor) / 3.0

        return max(0.1, min(2.0, performance_factor))

    def _calculate_fairness_factor(self, rate_limit: RateLimit) -> float:
        """Calculate fairness adjustment factor."""
        # This is a simplified fairness calculation
        # In a real implementation, this would consider multiple peers

        # Base fairness factor
        fairness_factor = 1.0

        # Adjust based on current rate vs max rate
        if rate_limit.max_rate > 0:
            utilization = rate_limit.current_rate / rate_limit.max_rate
            if utilization > 0.8:  # High utilization
                fairness_factor *= 0.9
            elif utilization < 0.2:  # Low utilization
                fairness_factor *= 1.1

        return max(0.5, min(1.5, fairness_factor))

    async def _handle_congestion_event(
        self,
        _peer_id: str,
        state: CongestionState,
        event_type: str,
    ) -> None:
        """Handle congestion events."""
        if event_type == "packet_loss":
            # Reduce congestion window
            state.cwnd = max(1.0, state.cwnd * 0.5)
            state.ssthresh = max(2.0, state.cwnd)
            state.in_recovery = True
            state.recovery_start_time = time.time()
            state.last_loss_time = time.time()

        elif event_type == "timeout":
            # Reset congestion window
            state.cwnd = 1.0
            state.ssthresh = max(2.0, state.cwnd * 0.5)
            state.in_recovery = True
            state.recovery_start_time = time.time()

        elif event_type == "duplicate_ack":
            # Fast retransmit
            state.cwnd = max(1.0, state.cwnd * 0.5)
            state.in_recovery = True
            state.recovery_start_time = time.time()

    async def _update_congestion_window(
        self,
        _peer_id: str,
        state: CongestionState,
        _congestion_data: dict[str, Any],
    ) -> None:
        """Update congestion window."""
        if state.in_recovery:
            # Check if recovery period is over
            recovery_duration = time.time() - state.recovery_start_time
            if recovery_duration > state.rtt * 3:  # 3 RTTs
                state.in_recovery = False

        if not state.in_recovery:
            if state.cwnd < state.ssthresh:
                # Slow start phase
                state.cwnd = min(state.cwnd * 2, state.ssthresh)
            else:
                # Congestion avoidance phase
                state.cwnd += 1.0 / state.cwnd

        # Apply congestion window limits
        state.cwnd = max(1.0, min(1000.0, state.cwnd))
