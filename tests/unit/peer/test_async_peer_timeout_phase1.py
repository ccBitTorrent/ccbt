"""Comprehensive tests for Phase 1 timeout optimizations.

Tests:
- Adaptive timeout calculation
- Timeout bounds (min/max)
- RTT-based timeout calculation
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer, pytest.mark.network]

from ccbt.peer.async_peer_connection import AsyncPeerConnection, AsyncPeerConnectionManager
from ccbt.models import PeerInfo


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"\x00" * 20,
        "piece_length": 16384,
        "num_pieces": 100,
    }


@pytest.fixture
def mock_piece_manager():
    """Create a mock piece manager."""
    return MagicMock()


@pytest.fixture
def peer_connection_manager(mock_torrent_data, mock_piece_manager):
    """Create a peer connection manager."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    return manager


@pytest.fixture
def mock_connection():
    """Create a mock peer connection."""
    connection = MagicMock(spec=AsyncPeerConnection)
    connection.peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    connection.stats = MagicMock()
    connection.stats.request_latency = 0.05  # 50ms RTT
    return connection


class TestAdaptiveTimeout:
    """Test adaptive timeout calculation."""

    def test_calculate_timeout_based_on_rtt(self, peer_connection_manager, mock_connection):
        """Test timeout calculation based on RTT."""
        # Set RTT
        mock_connection.stats.request_latency = 0.1  # 100ms RTT
        
        timeout = peer_connection_manager._calculate_timeout(mock_connection)
        
        # Should be RTT * multiplier, clamped to min/max
        expected = 0.1 * peer_connection_manager.config.network.timeout_rtt_multiplier
        min_timeout = peer_connection_manager.config.network.timeout_min_seconds
        max_timeout = peer_connection_manager.config.network.timeout_max_seconds
        expected_clamped = min(max(expected, min_timeout), max_timeout)
        assert timeout == pytest.approx(expected_clamped, abs=0.01)

    def test_calculate_timeout_respects_min(self, peer_connection_manager, mock_connection):
        """Test timeout respects minimum bound."""
        # Very low RTT
        mock_connection.stats.request_latency = 0.001  # 1ms RTT
        
        timeout = peer_connection_manager._calculate_timeout(mock_connection)
        
        # Should be at least min timeout
        assert timeout >= peer_connection_manager.config.network.timeout_min_seconds

    def test_calculate_timeout_respects_max(self, peer_connection_manager, mock_connection):
        """Test timeout respects maximum bound."""
        # Very high RTT
        mock_connection.stats.request_latency = 10.0  # 10s RTT
        
        timeout = peer_connection_manager._calculate_timeout(mock_connection)
        
        # Should be at most max timeout
        assert timeout <= peer_connection_manager.config.network.timeout_max_seconds

    def test_calculate_timeout_no_connection(self, peer_connection_manager):
        """Test timeout calculation with no connection."""
        timeout = peer_connection_manager._calculate_timeout(None)
        
        # Should use default timeout
        assert timeout == peer_connection_manager.config.network.connection_timeout

    def test_calculate_timeout_zero_rtt(self, peer_connection_manager, mock_connection):
        """Test timeout calculation with zero RTT."""
        # Zero RTT
        mock_connection.stats.request_latency = 0.0
        
        timeout = peer_connection_manager._calculate_timeout(mock_connection)
        
        # Should use default timeout when RTT is 0
        assert timeout == peer_connection_manager.config.network.connection_timeout

    def test_calculate_timeout_negative_rtt(self, peer_connection_manager, mock_connection):
        """Test timeout calculation with negative RTT."""
        # Negative RTT (invalid, should use default)
        mock_connection.stats.request_latency = -0.1
        
        timeout = peer_connection_manager._calculate_timeout(mock_connection)
        
        # Should use default timeout for invalid RTT
        assert timeout == peer_connection_manager.config.network.connection_timeout

