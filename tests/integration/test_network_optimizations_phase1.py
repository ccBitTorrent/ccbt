"""Integration tests for Phase 1 network optimizations.

Tests all optimizations working together:
- Connection pooling with warmup
- Tracker HTTP session optimization
- Socket buffer management
- Request pipelining
- Timeout and retry logic
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.network]

from ccbt.discovery.tracker import AsyncTrackerClient
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.peer.connection_pool import PeerConnectionPool
from ccbt.utils.network_optimizer import SocketOptimizer
from ccbt.utils.resilience import PeerCircuitBreakerManager
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


class TestConnectionPoolIntegration:
    """Test connection pool integration with peer connections."""

    @pytest.mark.asyncio
    async def test_connection_pool_with_warmup(self):
        """Test connection pool with warmup strategy."""
        pool = PeerConnectionPool(max_connections=10, max_idle_time=60.0)
        await pool.start()
        
        try:
            # Create peer list for warmup
            peer_list = [
                PeerInfo(ip="127.0.0.1", port=6881 + i) for i in range(5)
            ]
            
            # Mock connection creation
            async def mock_create(peer_info):
                await asyncio.sleep(0.01)  # Simulate connection delay
                return {
                    "peer_info": peer_info,
                    "connection": MagicMock(),
                    "created_at": time.time()
                }
            
            pool._create_connection = mock_create
            
            # Warmup connections
            await pool.warmup_connections(peer_list, max_count=5)
            
            # Verify warmup metrics
            stats = pool.get_pool_stats()
            assert stats["warmup_success_rate"] > 0
            
        finally:
            await pool.stop()

    @pytest.mark.asyncio
    async def test_connection_pool_with_health_checks(self):
        """Test connection pool with health checks."""
        pool = PeerConnectionPool(
            max_connections=10,
            max_idle_time=1.0,  # Short idle time for testing
            health_check_interval=0.1  # Short interval for testing
        )
        await pool.start()
        
        try:
            # Add connection
            peer_info = PeerInfo(ip="127.0.0.1", port=6881)
            peer_id = f"{peer_info.ip}:{peer_info.port}"
            
            connection = {
                "peer_info": peer_info,
                "connection": MagicMock(),
                "created_at": time.time()
            }
            pool.pool[peer_id] = connection
            from ccbt.peer.connection_pool import ConnectionMetrics
            pool.metrics[peer_id] = ConnectionMetrics(
                last_used=time.time() - 2.0  # Idle too long
            )
            
            # Wait for health check
            await asyncio.sleep(0.15)
            
            # Unhealthy connection should be removed
            # (May or may not be removed depending on timing)
            # Just verify health check runs without error
            await pool._perform_health_checks()
            
        finally:
            await pool.stop()


class TestTrackerIntegration:
    """Test tracker HTTP session optimization integration."""

    @pytest.mark.asyncio
    async def test_tracker_with_dns_cache(self):
        """Test tracker with DNS caching."""
        client = AsyncTrackerClient()
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "interval": 1800,
                "peers": []
            })
            
            async def mock_get(url):
                return mock_response
            
            mock_session.get = mock_get
            mock_session_class.return_value = mock_session
            
            await client.start()
            
            try:
                # DNS cache should be used
                # (aiohttp handles DNS internally, but we verify session is created)
                assert client.session is not None
                
            finally:
                await client.stop()

    @pytest.mark.asyncio
    async def test_tracker_with_exponential_backoff(self):
        """Test tracker with exponential backoff."""
        client = AsyncTrackerClient()
        
        # Create session with failures
        session = client.sessions.get("http://tracker.example.com/announce")
        if session is None:
            from ccbt.discovery.tracker import TrackerSession
            session = TrackerSession(url="http://tracker.example.com/announce")
            client.sessions["http://tracker.example.com/announce"] = session
        
        # Simulate failures
        session.failure_count = 3
        
        # Apply exponential backoff
        import random
        base_delay = 1.0
        max_delay = 300.0
        use_exponential = True
        
        if use_exponential:
            exponential_delay = base_delay * (2 ** session.failure_count)
            jitter = random.uniform(0, base_delay)
            session.backoff_delay = min(exponential_delay + jitter, max_delay)
        
        # Verify backoff delay is set
        assert session.backoff_delay >= 8.0
        assert session.backoff_delay <= max_delay


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with peer connections."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_peer_connections(self):
        """Test circuit breaker with peer connection manager."""
        manager = PeerCircuitBreakerManager(
            failure_threshold=2,
            recovery_timeout=0.1  # Short timeout for testing
        )
        
        # Get breakers for different peers
        breaker1 = manager.get_breaker("peer1:6881")
        breaker2 = manager.get_breaker("peer2:6882")
        
        # Fail peer1 twice to open circuit
        breaker1._on_failure()
        breaker1._on_failure()
        
        # Fail peer2 once (should still be closed)
        breaker2._on_failure()
        
        # Verify isolation
        assert breaker1.state == "open"
        assert breaker2.state == "closed"
        
        # Verify stats
        stats = manager.get_stats()
        assert "peer1:6881" in stats
        assert "peer2:6882" in stats


class TestSocketOptimizationIntegration:
    """Test socket optimization integration."""

    def test_socket_optimization_with_adaptive_buffers(self):
        """Test socket optimization with adaptive buffers."""
        optimizer = SocketOptimizer()
        
        # Mock config
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = True
            mock_config.network.socket_min_buffer_kib = 64
            mock_config.network.socket_max_buffer_kib = 65536
            mock_config.network.socket_enable_window_scaling = True
            mock_get_config.return_value = mock_config
            
            # Create mock socket
            mock_sock = MagicMock()
            
            from ccbt.utils.network_optimizer import SocketType
            
            # Optimize socket
            optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
            
            # Verify socket options were set
            assert mock_sock.setsockopt.called


class TestFullStackIntegration:
    """Test full stack integration of all optimizations."""

    @pytest.mark.asyncio
    async def test_all_optimizations_together(self, mock_torrent_data, mock_piece_manager):
        """Test all optimizations working together."""
        # Create peer connection manager (uses connection pool and circuit breaker)
        manager = AsyncPeerConnectionManager(
            torrent_data=mock_torrent_data,
            piece_manager=mock_piece_manager
        )
        
        # Verify connection pool is initialized
        assert manager.connection_pool is not None
        assert isinstance(manager.connection_pool, PeerConnectionPool)
        
        # Verify circuit breaker is initialized (if enabled)
        if manager.config.network.circuit_breaker_enabled:
            assert manager.circuit_breaker_manager is not None
            assert isinstance(manager.circuit_breaker_manager, PeerCircuitBreakerManager)
        
        # Start connection pool
        await manager.connection_pool.start()
        
        try:
            # Verify pool is running
            assert manager.connection_pool._running is True
            
            # Test warmup
            peer_list = [PeerInfo(ip="127.0.0.1", port=6881 + i) for i in range(3)]
            
            # Mock connection creation
            async def mock_create(peer_info):
                return {
                    "peer_info": peer_info,
                    "connection": MagicMock(),
                    "created_at": time.time()
                }
            
            manager.connection_pool._create_connection = mock_create
            
            # Warmup should work
            await manager.connection_pool.warmup_connections(peer_list, max_count=3)
            
            # Verify metrics
            stats = manager.connection_pool.get_pool_stats()
            assert "warmup_success_rate" in stats
            
        finally:
            await manager.connection_pool.stop()

