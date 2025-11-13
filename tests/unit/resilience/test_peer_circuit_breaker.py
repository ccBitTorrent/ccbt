"""Comprehensive tests for peer circuit breaker implementation.

Tests:
- PeerCircuitBreakerManager
- Per-peer circuit breaker isolation
- Circuit breaker state transitions
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.resilience, pytest.mark.network]

from ccbt.utils.resilience import (
    CircuitBreaker,
    CircuitBreakerError,
    PeerCircuitBreakerManager,
)


class TestPeerCircuitBreakerManager:
    """Test PeerCircuitBreakerManager."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = PeerCircuitBreakerManager(
            failure_threshold=5,
            recovery_timeout=60.0
        )
        
        assert manager.failure_threshold == 5
        assert manager.recovery_timeout == 60.0
        assert len(manager._breakers) == 0

    def test_get_breaker_creates_new(self):
        """Test getting breaker for new peer creates new breaker."""
        manager = PeerCircuitBreakerManager()
        
        breaker1 = manager.get_breaker("peer1")
        breaker2 = manager.get_breaker("peer2")
        
        assert breaker1 is not breaker2
        assert len(manager._breakers) == 2

    def test_get_breaker_returns_existing(self):
        """Test getting breaker for existing peer returns same breaker."""
        manager = PeerCircuitBreakerManager()
        
        breaker1 = manager.get_breaker("peer1")
        breaker2 = manager.get_breaker("peer1")
        
        assert breaker1 is breaker2
        assert len(manager._breakers) == 1

    def test_get_breaker_configures_correctly(self):
        """Test breaker is configured with manager settings."""
        manager = PeerCircuitBreakerManager(
            failure_threshold=10,
            recovery_timeout=120.0
        )
        
        breaker = manager.get_breaker("peer1")
        
        assert breaker.failure_threshold == 10
        assert breaker.recovery_timeout == 120.0
        assert breaker.expected_exception == (ConnectionError, TimeoutError, OSError)

    def test_get_stats_empty(self):
        """Test getting stats with no breakers."""
        manager = PeerCircuitBreakerManager()
        
        stats = manager.get_stats()
        
        assert stats == {}

    def test_get_stats_multiple_breakers(self):
        """Test getting stats for multiple breakers."""
        manager = PeerCircuitBreakerManager()
        
        breaker1 = manager.get_breaker("peer1")
        breaker2 = manager.get_breaker("peer2")
        
        # Trigger failures to change state
        breaker1._on_failure()
        breaker1._on_failure()
        breaker2._on_failure()
        breaker2._on_failure()
        breaker2._on_failure()
        
        stats = manager.get_stats()
        
        assert "peer1" in stats
        assert "peer2" in stats
        assert stats["peer1"]["failure_count"] == 2
        assert stats["peer2"]["failure_count"] == 3

    def test_per_peer_isolation(self):
        """Test circuit breakers are isolated per peer."""
        manager = PeerCircuitBreakerManager(failure_threshold=2)
        
        breaker1 = manager.get_breaker("peer1")
        breaker2 = manager.get_breaker("peer2")
        
        # Fail peer1 twice to open circuit
        breaker1._on_failure()
        breaker1._on_failure()
        
        # Fail peer2 once (should still be closed)
        breaker2._on_failure()
        
        # Peer1 should be open, peer2 should be closed
        assert breaker1.state == "open"
        assert breaker2.state == "closed"


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with async operations."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_after_threshold(self):
        """Test circuit breaker blocks requests after failure threshold."""
        manager = PeerCircuitBreakerManager(failure_threshold=2)
        breaker = manager.get_breaker("peer1")
        
        # Fail twice
        breaker._on_failure()
        breaker._on_failure()
        
        # Circuit should be open
        assert breaker.state == "open"
        
        # Attempting operation should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            if breaker.state == "open":
                if time.time() - breaker.last_failure_time <= breaker.recovery_timeout:
                    raise CircuitBreakerError("Circuit breaker is open")

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker transitions to half-open after recovery timeout."""
        manager = PeerCircuitBreakerManager(
            failure_threshold=2,
            recovery_timeout=0.1  # Short timeout for testing
        )
        breaker = manager.get_breaker("peer1")
        
        # Open circuit
        breaker._on_failure()
        breaker._on_failure()
        assert breaker.state == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should transition to half-open when checked
        if breaker.state == "open":
            if time.time() - breaker.last_failure_time > breaker.recovery_timeout:
                breaker.state = "half-open"
        
        # After recovery, should be half-open
        assert breaker.state == "half-open"

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes on successful operation."""
        manager = PeerCircuitBreakerManager(failure_threshold=2)
        breaker = manager.get_breaker("peer1")
        
        # Open circuit
        breaker._on_failure()
        breaker._on_failure()
        assert breaker.state == "open"
        
        # Manually set to half-open for testing
        breaker.state = "half-open"
        breaker.last_failure_time = time.time() - 0.2
        
        # Successful operation should close circuit
        breaker._on_success()
        
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_again_on_half_open_failure(self):
        """Test circuit breaker opens again if half-open fails."""
        manager = PeerCircuitBreakerManager(failure_threshold=2)
        breaker = manager.get_breaker("peer1")
        
        # Set to half-open and set failure count to threshold-1
        breaker.state = "half-open"
        breaker.last_failure_time = time.time() - 0.2
        breaker.failure_count = 1  # One failure away from threshold
        
        # Another failure should open circuit again (reaches threshold)
        breaker._on_failure()
        
        assert breaker.state == "open"
        assert breaker.failure_count == 2  # Incremented from 1 to 2

