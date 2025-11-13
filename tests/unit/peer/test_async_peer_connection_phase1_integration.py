"""Integration tests for AsyncPeerConnectionManager Phase 1 features.

Tests connection pool, circuit breaker, adaptive timeout, and pipeline integration.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer, pytest.mark.network]

from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
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
    manager = MagicMock()
    manager.pieces = [False] * 100
    return manager


@pytest.mark.asyncio
async def test_connection_pool_started_in_manager(mock_torrent_data, mock_piece_manager):
    """Test connection pool is started when manager starts."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    # Start manager (should start connection pool)
    await manager.start()
    
    try:
        # Verify connection pool is running
        assert manager.connection_pool._running is True
    finally:
        await manager.stop()
        assert manager.connection_pool._running is False


@pytest.mark.asyncio
async def test_circuit_breaker_integration(mock_torrent_data, mock_piece_manager):
    """Test circuit breaker integration in connection manager."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    if manager.config.network.circuit_breaker_enabled:
        assert manager.circuit_breaker_manager is not None
        
        # Test circuit breaker is used
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        breaker = manager.circuit_breaker_manager.get_breaker(peer_id)
        
        # Verify breaker exists
        assert breaker is not None


@pytest.mark.asyncio
async def test_adaptive_timeout_used_in_connection(mock_torrent_data, mock_piece_manager):
    """Test adaptive timeout is calculated and used."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    # Create mock connection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    mock_connection = MagicMock(spec=AsyncPeerConnection)
    mock_connection.stats = MagicMock()
    mock_connection.stats.request_latency = 0.1  # 100ms RTT
    
    # Calculate timeout
    timeout = manager._calculate_timeout(mock_connection)
    
    # Should use RTT-based calculation
    assert timeout >= manager.config.network.timeout_min_seconds
    assert timeout <= manager.config.network.timeout_max_seconds


@pytest.mark.asyncio
async def test_adaptive_pipeline_depth_used(mock_torrent_data, mock_piece_manager):
    """Test adaptive pipeline depth is calculated and used."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    # Create mock connection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    mock_connection = MagicMock(spec=AsyncPeerConnection)
    mock_connection.stats = MagicMock()
    mock_connection.stats.request_latency = 0.05  # 50ms RTT
    
    # Calculate pipeline depth
    depth = manager._calculate_pipeline_depth(mock_connection)
    
    # Should be within bounds
    assert depth >= manager.config.network.pipeline_min_depth
    assert depth <= manager.config.network.pipeline_max_depth


@pytest.mark.asyncio
async def test_request_prioritization_used(mock_torrent_data, mock_piece_manager):
    """Test request prioritization is calculated."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    # Mock piece manager with availability
    def mock_get_piece_availability(piece_index):
        return 5 if piece_index < 10 else 20
    
    mock_piece_manager.get_piece_availability = mock_get_piece_availability
    
    # Calculate priority
    priority_rarest = manager._calculate_request_priority(0, mock_piece_manager)
    priority_common = manager._calculate_request_priority(50, mock_piece_manager)
    
    # Rarest should have higher priority
    assert priority_rarest > priority_common


@pytest.mark.asyncio
async def test_request_coalescing_used(mock_torrent_data, mock_piece_manager):
    """Test request coalescing is used."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager
    )
    
    # Create adjacent requests
    from ccbt.peer.async_peer_connection import RequestInfo
    
    requests = [
        RequestInfo(piece_index=0, begin=0, length=16384, timestamp=0.0),
        RequestInfo(piece_index=0, begin=16384, length=16384, timestamp=0.0),
    ]
    
    # Coalesce requests
    coalesced = manager._coalesce_requests(requests)
    
    # Should coalesce into fewer requests
    assert len(coalesced) <= len(requests)

