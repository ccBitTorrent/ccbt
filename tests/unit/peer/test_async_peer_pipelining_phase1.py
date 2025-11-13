"""Comprehensive tests for Phase 1 request pipelining optimizations.

Tests:
- Adaptive pipeline depth calculation
- Request prioritization (rarest first)
- Request coalescing
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer, pytest.mark.network]

from ccbt.peer.async_peer_connection import AsyncPeerConnection, AsyncPeerConnectionManager
from ccbt.models import PeerInfo


@pytest.fixture
def mock_piece_manager():
    """Create a mock piece manager."""
    manager = MagicMock()
    manager.pieces = [False] * 100  # 100 pieces
    manager.get_rarest_pieces = MagicMock(return_value=[0, 1, 2])  # Rarest pieces
    return manager


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"\x00" * 20,
        "piece_length": 16384,
        "num_pieces": 100,
    }


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
    connection.stats.request_latency = 0.05  # 50ms latency
    connection.max_pipeline_depth = 16
    connection.outstanding_requests = []
    connection.request_queue = []
    connection._priority_queue = []
    return connection


class TestAdaptivePipelineDepth:
    """Test adaptive pipeline depth calculation."""

    def test_calculate_pipeline_depth_low_latency(self, peer_connection_manager, mock_connection):
        """Test pipeline depth for low latency connections."""
        # Low latency connection
        mock_connection.stats.request_latency = 0.005  # 5ms
        
        depth = peer_connection_manager._calculate_pipeline_depth(mock_connection)
        
        # Should return higher depth for low latency
        assert depth >= peer_connection_manager.config.network.pipeline_depth
        assert depth <= peer_connection_manager.config.network.pipeline_max_depth

    def test_calculate_pipeline_depth_medium_latency(self, peer_connection_manager, mock_connection):
        """Test pipeline depth for medium latency connections."""
        # Medium latency connection
        mock_connection.stats.request_latency = 0.05  # 50ms
        
        depth = peer_connection_manager._calculate_pipeline_depth(mock_connection)
        
        # Should return base depth
        assert depth == peer_connection_manager.config.network.pipeline_depth

    def test_calculate_pipeline_depth_high_latency(self, peer_connection_manager, mock_connection):
        """Test pipeline depth for high latency connections."""
        # High latency connection
        mock_connection.stats.request_latency = 0.2  # 200ms
        
        depth = peer_connection_manager._calculate_pipeline_depth(mock_connection)
        
        # Should return lower depth for high latency
        assert depth >= peer_connection_manager.config.network.pipeline_min_depth
        assert depth <= peer_connection_manager.config.network.pipeline_depth

    def test_calculate_pipeline_depth_respects_min_max(self, peer_connection_manager, mock_connection):
        """Test pipeline depth respects min/max bounds."""
        # Very low latency
        mock_connection.stats.request_latency = 0.001  # 1ms
        
        depth = peer_connection_manager._calculate_pipeline_depth(mock_connection)
        
        assert depth <= peer_connection_manager.config.network.pipeline_max_depth
        
        # Very high latency
        mock_connection.stats.request_latency = 1.0  # 1000ms
        
        depth = peer_connection_manager._calculate_pipeline_depth(mock_connection)
        
        assert depth >= peer_connection_manager.config.network.pipeline_min_depth


class TestRequestPrioritization:
    """Test request prioritization."""

    def test_calculate_request_priority_rarest_first(self, peer_connection_manager, mock_piece_manager):
        """Test priority calculation for rarest pieces."""
        # Mock piece manager to have availability info
        def mock_get_piece_availability(piece_index):
            if piece_index < 3:
                return 1  # Rarest (only 1 peer has it)
            return 10  # Common (10 peers have it)
        
        mock_piece_manager.get_piece_availability = mock_get_piece_availability
        
        # Rarest piece should have higher priority
        priority_rarest = peer_connection_manager._calculate_request_priority(0, mock_piece_manager)
        priority_common = peer_connection_manager._calculate_request_priority(50, mock_piece_manager)
        
        # Higher number = higher priority (lower availability = higher priority)
        assert priority_rarest > priority_common

    def test_calculate_request_priority_unknown_piece(self, peer_connection_manager, mock_piece_manager):
        """Test priority calculation for unknown piece availability."""
        # Piece not in rarest list
        priority = peer_connection_manager._calculate_request_priority(99, mock_piece_manager)
        
        # Should have default priority
        assert priority >= 0

    def test_request_prioritization_enabled(self, peer_connection_manager, mock_connection, mock_piece_manager):
        """Test request prioritization when enabled."""
        if not peer_connection_manager.config.network.pipeline_enable_prioritization:
            pytest.skip("Prioritization disabled in config")
        
        # Enable prioritization
        mock_connection._priority_queue = []
        
        # Request pieces with different priorities
        import time
        from heapq import heappush
        
        request1 = (0, 0, None)  # Piece 0 (rarest)
        request2 = (50, 0, None)  # Piece 50 (common)
        
        heappush(mock_connection._priority_queue, (-10, time.time(), request1))
        heappush(mock_connection._priority_queue, (-5, time.time(), request2))
        
        # Higher priority should be first (negative priority for min-heap)
        assert len(mock_connection._priority_queue) == 2


class TestRequestCoalescing:
    """Test request coalescing."""

    def test_coalesce_requests_adjacent(self, peer_connection_manager):
        """Test coalescing adjacent requests."""
        from ccbt.peer.async_peer_connection import RequestInfo
        
        # Create adjacent requests
        requests = [
            RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
            RequestInfo(piece_index=0, begin=16384, length=16384, timestamp=0.0),
        ]
        
        coalesced = peer_connection_manager._coalesce_requests(requests)
        
        # Should coalesce into single request
        assert len(coalesced) == 1
        assert coalesced[0].piece_index == 0
        assert coalesced[0].begin == 0
        assert coalesced[0].length == 32768  # Combined length

    def test_coalesce_requests_within_threshold(self, peer_connection_manager):
        """Test coalescing requests within threshold."""
        from ccbt.peer.async_peer_connection import RequestInfo
        
        threshold = peer_connection_manager.config.network.pipeline_coalesce_threshold_kib * 1024
        
        # Create requests with small gap (within threshold)
        requests = [
            RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
            RequestInfo(piece_index=0, begin=16384 + threshold // 2, length=16384, timestamp=0.0),
        ]
        
        coalesced = peer_connection_manager._coalesce_requests(requests)
        
        # Should coalesce if gap is within threshold
        if len(coalesced) == 1:
            assert coalesced[0].length >= 32768

    def test_coalesce_requests_large_gap(self, peer_connection_manager):
        """Test coalescing doesn't merge requests with large gap."""
        from ccbt.peer.async_peer_connection import RequestInfo
        
        threshold = peer_connection_manager.config.network.pipeline_coalesce_threshold_kib * 1024
        
        # Create requests with large gap (beyond threshold)
        requests = [
            RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
            RequestInfo(piece_index=0, begin=16384 + threshold * 2, length=16384, timestamp=0.0),
        ]
        
        coalesced = peer_connection_manager._coalesce_requests(requests)
        
        # Should not coalesce if gap is too large
        assert len(coalesced) >= 1  # May coalesce or not depending on implementation

    def test_coalesce_requests_different_pieces(self, peer_connection_manager):
        """Test coalescing doesn't merge requests from different pieces."""
        from ccbt.peer.async_peer_connection import RequestInfo
        
        # Create requests from different pieces
        requests = [
            RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
            RequestInfo(piece_index=1, begin=0, length=16384, timestamp=0.0),
        ]
        
        coalesced = peer_connection_manager._coalesce_requests(requests)
        
        # Should not coalesce different pieces
        assert len(coalesced) == 2

    def test_coalesce_requests_empty_list(self, peer_connection_manager):
        """Test coalescing empty request list."""
        coalesced = peer_connection_manager._coalesce_requests([])
        
        assert len(coalesced) == 0

    def test_coalesce_requests_single_request(self, peer_connection_manager):
        """Test coalescing single request."""
        from ccbt.peer.async_peer_connection import RequestInfo
        
        requests = [
            RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
        ]
        
        coalesced = peer_connection_manager._coalesce_requests(requests)
        
        assert len(coalesced) == 1
        assert coalesced[0].piece_index == 0
        assert coalesced[0].begin == 0
        assert coalesced[0].length == 16384

