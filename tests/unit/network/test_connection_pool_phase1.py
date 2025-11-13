"""Comprehensive tests for Phase 1 connection pool enhancements.

Tests:
- Connection validation improvements (socket error checking)
- Connection warmup strategy
- Extended metrics (reuse rate, lifetime, establishment time, warmup success rate)
"""

from __future__ import annotations

import asyncio
import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.network, pytest.mark.connection]

from ccbt.peer.connection_pool import ConnectionMetrics, PeerConnectionPool
from ccbt.models import PeerInfo


@pytest.fixture
def peer_info():
    """Create a test peer info."""
    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest_asyncio.fixture
async def connection_pool():
    """Create a test connection pool."""
    pool = PeerConnectionPool(max_connections=10, max_idle_time=60.0)
    await pool.start()
    yield pool
    await pool.stop()


class TestConnectionValidation:
    """Test connection validation improvements."""

    @pytest.mark.asyncio
    async def test_connection_validation_with_socket_error(self, connection_pool):
        """Test connection validation detects socket errors."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create mock connection with socket error
        mock_writer = MagicMock()
        mock_transport = MagicMock()
        mock_sock = MagicMock()
        mock_sock.getsockopt.return_value = 104  # ECONNRESET error code (non-zero)
        
        mock_writer._transport = mock_transport
        mock_transport._sock = mock_sock
        
        mock_conn = MagicMock()
        mock_conn.writer = mock_writer
        
        connection = {"connection": mock_conn, "created_at": time.time()}
        
        # Should detect socket error
        is_valid = connection_pool._is_connection_valid(connection)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_connection_validation_with_closed_reader(self, connection_pool):
        """Test connection validation detects closed reader."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create mock connection with closed reader
        mock_reader = MagicMock()
        mock_reader.is_closing.return_value = True
        
        mock_conn = MagicMock()
        mock_conn.reader = mock_reader
        
        connection = {"connection": mock_conn, "created_at": time.time()}
        
        # Should detect closed reader
        is_valid = connection_pool._is_connection_valid(connection)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_connection_validation_with_closed_writer(self, connection_pool):
        """Test connection validation detects closed writer."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create mock connection with closed writer
        mock_writer = MagicMock()
        mock_writer.closed = True
        
        mock_conn = MagicMock()
        mock_conn.writer = mock_writer
        
        connection = {"connection": mock_conn, "created_at": time.time()}
        
        # Should detect closed writer
        is_valid = connection_pool._is_connection_valid(connection)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_connection_validation_with_idle_timeout(self, connection_pool):
        """Test connection validation detects idle timeout."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create connection that's too old
        connection = {
            "connection": MagicMock(),
            "created_at": time.time() - (connection_pool.max_idle_time + 10)
        }
        
        # Should detect idle timeout
        is_valid = connection_pool._is_connection_valid(connection)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_connection_validation_with_socket_error_handling(self, connection_pool):
        """Test connection validation handles socket error checking gracefully."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create mock connection that raises OSError when checking socket
        mock_reader = MagicMock()
        mock_reader.is_closing.return_value = False
        mock_reader.closed = False
        
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.closed = False
        mock_transport = MagicMock()
        mock_sock = MagicMock()
        mock_sock.getsockopt.side_effect = OSError("Permission denied")
        
        mock_writer._transport = mock_transport
        mock_transport._sock = mock_sock
        
        mock_conn = MagicMock()
        mock_conn.reader = mock_reader
        mock_conn.writer = mock_writer
        
        connection = {"connection": mock_conn, "created_at": time.time()}
        
        # Should handle error gracefully and assume valid (since reader/writer are OK)
        is_valid = connection_pool._is_connection_valid(connection)
        assert is_valid  # Assumes valid when can't check socket error

    @pytest.mark.asyncio
    async def test_connection_validation_with_valid_connection(self, connection_pool):
        """Test connection validation with valid connection."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Create valid mock connection
        mock_reader = MagicMock()
        mock_reader.is_closing.return_value = False
        mock_reader.closed = False
        
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.closed = False
        
        mock_transport = MagicMock()
        mock_sock = MagicMock()
        mock_sock.getsockopt.return_value = 0  # No error
        
        mock_writer._transport = mock_transport
        mock_transport._sock = mock_sock
        
        mock_conn = MagicMock()
        mock_conn.reader = mock_reader
        mock_conn.writer = mock_writer
        
        connection = {"connection": mock_conn, "created_at": time.time()}
        
        # Should be valid
        is_valid = connection_pool._is_connection_valid(connection)
        assert is_valid


class TestConnectionWarmup:
    """Test connection warmup strategy."""

    @pytest.mark.asyncio
    async def test_warmup_connections_success(self, connection_pool):
        """Test successful connection warmup."""
        peer_list = [
            PeerInfo(ip="127.0.0.1", port=6881),
            PeerInfo(ip="127.0.0.1", port=6882),
            PeerInfo(ip="127.0.0.1", port=6883),
        ]
        
        # Mock successful connection creation
        async def mock_create(peer_info):
            return {
                "peer_info": peer_info,
                "connection": MagicMock(),
                "created_at": time.time()
            }
        
        connection_pool._create_connection = mock_create
        
        # Mock acquire to return connections
        original_acquire = connection_pool.acquire
        async def mock_acquire(peer_info):
            peer_id = f"{peer_info.ip}:{peer_info.port}"
            if peer_id not in connection_pool.pool:
                conn = await original_acquire(peer_info)
                return conn
            return connection_pool.pool[peer_id]
        
        connection_pool.acquire = mock_acquire
        
        # Warmup connections
        await connection_pool.warmup_connections(peer_list, max_count=3)
        
        # Verify warmup metrics
        assert connection_pool._warmup_attempts == 3
        assert connection_pool._warmup_successes == 3

    @pytest.mark.asyncio
    async def test_warmup_connections_partial_failure(self, connection_pool):
        """Test connection warmup with partial failures."""
        peer_list = [
            PeerInfo(ip="127.0.0.1", port=6881),
            PeerInfo(ip="127.0.0.1", port=6882),
            PeerInfo(ip="127.0.0.1", port=6883),
        ]
        
        # Mock acquire with failures
        call_count = 0
        async def mock_acquire(peer_info):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Connection failed")
            return {
                "peer_info": peer_info,
                "connection": MagicMock(),
                "created_at": time.time()
            }
        
        connection_pool.acquire = mock_acquire
        
        # Warmup connections
        await connection_pool.warmup_connections(peer_list, max_count=3)
        
        # Verify warmup metrics (2 successes, 1 failure)
        assert connection_pool._warmup_attempts == 3
        assert connection_pool._warmup_successes == 2

    @pytest.mark.asyncio
    async def test_warmup_connections_empty_list(self, connection_pool):
        """Test warmup with empty peer list."""
        await connection_pool.warmup_connections([], max_count=10)
        
        # Should not attempt warmup
        assert connection_pool._warmup_attempts == 0
        assert connection_pool._warmup_successes == 0

    @pytest.mark.asyncio
    async def test_warmup_connections_max_count_limit(self, connection_pool):
        """Test warmup respects max_count limit."""
        peer_list = [PeerInfo(ip="127.0.0.1", port=6881 + i) for i in range(10)]
        
        warmup_count = 0
        async def mock_acquire(peer_info):
            nonlocal warmup_count
            warmup_count += 1
            return {
                "peer_info": peer_info,
                "connection": MagicMock(),
                "created_at": time.time()
            }
        
        connection_pool.acquire = mock_acquire
        
        # Warmup with max_count=5
        await connection_pool.warmup_connections(peer_list, max_count=5)
        
        # Should only warmup 5 connections
        assert warmup_count == 5
        assert connection_pool._warmup_attempts == 5

    @pytest.mark.asyncio
    async def test_warmup_connections_skips_existing(self, connection_pool):
        """Test warmup skips peers already in pool."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Add existing connection
        connection_pool.pool[peer_id] = {
            "peer_info": peer_info,
            "connection": MagicMock(),
            "created_at": time.time()
        }
        
        warmup_count = 0
        async def mock_acquire(peer_info):
            nonlocal warmup_count
            warmup_count += 1
            return None
        
        connection_pool.acquire = mock_acquire
        
        # Warmup should skip existing peer
        await connection_pool.warmup_connections([peer_info], max_count=1)
        
        # Should not attempt warmup for existing peer
        assert warmup_count == 0


class TestExtendedMetrics:
    """Test extended connection pool metrics."""

    @pytest.mark.asyncio
    async def test_pool_stats_reuse_rate(self, connection_pool):
        """Test reuse rate calculation."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Create connection with usage
        connection = {
            "peer_info": peer_info,
            "connection": MagicMock(),
            "created_at": time.time()
        }
        connection_pool.pool[peer_id] = connection
        metrics = ConnectionMetrics(usage_count=10)
        connection_pool.metrics[peer_id] = metrics
        
        stats = connection_pool.get_pool_stats()
        
        # Reuse rate = (10 - 1) / 10 * 100 = 90%
        assert stats["reuse_rate"] == pytest.approx(90.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_pool_stats_average_lifetime(self, connection_pool):
        """Test average connection lifetime calculation."""
        peer_info1 = PeerInfo(ip="127.0.0.1", port=6881)
        peer_info2 = PeerInfo(ip="127.0.0.1", port=6882)
        
        peer_id1 = f"{peer_info1.ip}:{peer_info1.port}"
        peer_id2 = f"{peer_info2.ip}:{peer_info2.port}"
        
        # Create connections with different ages
        created_at1 = time.time() - 100
        created_at2 = time.time() - 200
        
        connection1 = {
            "peer_info": peer_info1,
            "connection": MagicMock(),
            "created_at": created_at1
        }
        connection2 = {
            "peer_info": peer_info2,
            "connection": MagicMock(),
            "created_at": created_at2
        }
        
        connection_pool.pool[peer_id1] = connection1
        connection_pool.pool[peer_id2] = connection2
        # Set created_at in metrics for lifetime calculation
        connection_pool.metrics[peer_id1] = ConnectionMetrics(created_at=created_at1)
        connection_pool.metrics[peer_id2] = ConnectionMetrics(created_at=created_at2)
        
        stats = connection_pool.get_pool_stats()
        
        # Average lifetime should be around 150 seconds
        assert stats["average_connection_lifetime"] == pytest.approx(150.0, abs=10.0)

    @pytest.mark.asyncio
    async def test_pool_stats_establishment_time(self, connection_pool):
        """Test connection establishment time tracking."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Create connection with establishment time
        connection = {
            "peer_info": peer_info,
            "connection": MagicMock(),
            "created_at": time.time()
        }
        connection_pool.pool[peer_id] = connection
        metrics = ConnectionMetrics(establishment_time=0.5)
        connection_pool.metrics[peer_id] = metrics
        
        stats = connection_pool.get_pool_stats()
        
        assert stats["connection_establishment_time"] == 0.5

    @pytest.mark.asyncio
    async def test_pool_stats_warmup_success_rate(self, connection_pool):
        """Test warmup success rate calculation."""
        # Set warmup metrics
        connection_pool._warmup_attempts = 10
        connection_pool._warmup_successes = 8
        
        stats = connection_pool.get_pool_stats()
        
        # Success rate = 8/10 * 100 = 80%
        assert stats["warmup_success_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_pool_stats_warmup_no_attempts(self, connection_pool):
        """Test warmup success rate with no attempts."""
        # No warmup attempts
        connection_pool._warmup_attempts = 0
        connection_pool._warmup_successes = 0
        
        stats = connection_pool.get_pool_stats()
        
        # Should return 0.0 when no attempts
        assert stats["warmup_success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_pool_stats_all_metrics(self, connection_pool):
        """Test all metrics are present in stats."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Create connection with various metrics
        connection = {
            "peer_info": peer_info,
            "connection": MagicMock(),
            "created_at": time.time() - 50
        }
        connection_pool.pool[peer_id] = connection
        metrics = ConnectionMetrics(
            usage_count=5,
            bytes_sent=1000,
            bytes_received=2000,
            errors=1,
            establishment_time=0.3
        )
        connection_pool.metrics[peer_id] = metrics
        connection_pool._warmup_attempts = 5
        connection_pool._warmup_successes = 4
        
        stats = connection_pool.get_pool_stats()
        
        # Verify all metrics are present
        assert "reuse_rate" in stats
        assert "average_connection_lifetime" in stats
        assert "connection_establishment_time" in stats
        assert "warmup_success_rate" in stats
        assert stats["total_bytes_sent"] == 1000
        assert stats["total_bytes_received"] == 2000
        assert stats["total_errors"] == 1


class TestConnectionEstablishmentTracking:
    """Test connection establishment time tracking."""

    @pytest.mark.asyncio
    async def test_establishment_time_tracked(self, connection_pool):
        """Test establishment time is tracked during connection creation."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Mock _create_peer_connection to simulate delay
        async def mock_create_peer_connection(peer_info):
            await asyncio.sleep(0.1)  # Simulate connection delay
            return MagicMock()
        
        connection_pool._create_peer_connection = mock_create_peer_connection
        
        # Pre-create metrics entry so establishment time can be set
        connection_pool.metrics[peer_id] = ConnectionMetrics()
        
        # Create connection
        connection = await connection_pool._create_connection(peer_info)
        
        # Verify establishment time is tracked
        assert connection is not None
        assert peer_id in connection_pool.metrics
        assert connection_pool.metrics[peer_id].establishment_time > 0.0
        assert connection_pool.metrics[peer_id].establishment_time >= 0.1

