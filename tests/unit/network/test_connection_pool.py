"""Tests for connection pool implementation."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network, pytest.mark.connection]

from ccbt.peer.connection_pool import ConnectionMetrics, PeerConnectionPool
from ccbt.models import PeerInfo


@pytest.fixture
def peer_info():
    """Create a test peer info."""
    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest.fixture
async def connection_pool():
    """Create a test connection pool."""
    pool = PeerConnectionPool(max_connections=10, max_idle_time=60.0)
    await pool.start()
    yield pool
    await pool.stop()


@pytest.mark.asyncio
async def test_connection_pool_start_stop(peer_info):
    """Test connection pool start and stop."""
    pool = PeerConnectionPool()

    # Test start
    await pool.start()
    assert pool._running is True

    # Test stop
    await pool.stop()
    assert pool._running is False


@pytest.mark.asyncio
async def test_connection_pool_context_manager(peer_info):
    """Test connection pool as context manager."""
    async with PeerConnectionPool() as pool:
        assert pool._running is True
    assert pool._running is False


@pytest.mark.asyncio
async def test_acquire_connection(connection_pool, peer_info):
    """Test acquiring a connection."""
    # Mock the connection creation
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool._create_connection = AsyncMock(return_value=mock_connection)

    # Acquire connection
    connection = await connection_pool.acquire(peer_info)

    assert connection is not None
    assert str(peer_info) in connection_pool.pool
    assert str(peer_info) in connection_pool.metrics


@pytest.mark.asyncio
async def test_acquire_connection_failure(connection_pool, peer_info):
    """Test acquiring a connection when creation fails."""
    # Mock connection creation failure
    connection_pool._create_connection = AsyncMock(return_value=None)

    # Acquire connection should fail
    connection = await connection_pool.acquire(peer_info)

    assert connection is None
    assert str(peer_info) not in connection_pool.pool


@pytest.mark.asyncio
async def test_release_connection(connection_pool, peer_info):
    """Test releasing a connection."""
    # Create a mock connection
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool.pool[str(peer_info)] = mock_connection
    connection_pool.metrics[str(peer_info)] = ConnectionMetrics()

    # Release connection
    await connection_pool.release(str(peer_info), mock_connection)

    # Connection should still be in pool (not recycled)
    assert str(peer_info) in connection_pool.pool


@pytest.mark.asyncio
async def test_connection_recycling(connection_pool, peer_info):
    """Test connection recycling after max usage."""
    # Create a mock connection
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool.pool[str(peer_info)] = mock_connection

    # Set usage count to max
    metrics = ConnectionMetrics(usage_count=1000)
    connection_pool.metrics[str(peer_info)] = metrics

    # Release connection
    await connection_pool.release(str(peer_info), mock_connection)

    # Connection should be removed due to recycling
    assert str(peer_info) not in connection_pool.pool


@pytest.mark.asyncio
async def test_remove_connection(connection_pool, peer_info):
    """Test removing a connection."""
    # Create a mock connection with close method
    mock_connection = MagicMock()
    mock_connection.close = AsyncMock()

    connection_pool.pool[str(peer_info)] = mock_connection
    connection_pool.metrics[str(peer_info)] = ConnectionMetrics()

    # Remove connection
    await connection_pool.remove_connection(str(peer_info))

    # Connection should be removed
    assert str(peer_info) not in connection_pool.pool
    assert str(peer_info) not in connection_pool.metrics


@pytest.mark.asyncio
async def test_pool_stats(connection_pool, peer_info):
    """Test getting pool statistics."""
    # Add some mock connections
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool.pool[str(peer_info)] = mock_connection
    connection_pool.metrics[str(peer_info)] = ConnectionMetrics(
        bytes_sent=1000,
        bytes_received=2000,
        errors=1
    )

    stats = connection_pool.get_pool_stats()

    assert stats["total_connections"] == 1
    assert stats["healthy_connections"] == 1
    assert stats["max_connections"] == 10
    assert stats["total_bytes_sent"] == 1000
    assert stats["total_bytes_received"] == 2000
    assert stats["total_errors"] == 1


@pytest.mark.asyncio
async def test_update_connection_metrics(connection_pool, peer_info):
    """Test updating connection metrics."""
    # Create metrics
    metrics = ConnectionMetrics()
    connection_pool.metrics[str(peer_info)] = metrics

    # Update metrics
    connection_pool.update_connection_metrics(
        str(peer_info),
        bytes_sent=100,
        bytes_received=200,
        errors=1
    )

    assert metrics.bytes_sent == 100
    assert metrics.bytes_received == 200
    assert metrics.errors == 1


@pytest.mark.asyncio
async def test_max_connections_limit(peer_info):
    """Test that max connections limit is enforced."""
    pool = PeerConnectionPool(max_connections=2)
    await pool.start()

    try:
        # Mock connection creation
        mock_connection = {"peer_info": peer_info, "created_at": time.time()}
        pool._create_connection = AsyncMock(return_value=mock_connection)

        # Acquire connections up to limit
        peer1 = PeerInfo(ip="127.0.0.1", port=6881)
        peer2 = PeerInfo(ip="127.0.0.1", port=6882)
        peer3 = PeerInfo(ip="127.0.0.1", port=6883)

        conn1 = await pool.acquire(peer1)
        conn2 = await pool.acquire(peer2)
        conn3 = await pool.acquire(peer3)

        # First two should succeed, third should fail due to semaphore
        assert conn1 is not None
        assert conn2 is not None
        assert conn3 is None  # Should timeout due to semaphore limit

    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_health_check_removes_unhealthy_connections(connection_pool, peer_info):
    """Test that health checks remove unhealthy connections."""
    # Create an unhealthy connection
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool.pool[str(peer_info)] = mock_connection

    # Set metrics to indicate unhealthy state
    metrics = ConnectionMetrics(
        errors=20,  # Too many errors
        is_healthy=False
    )
    connection_pool.metrics[str(peer_info)] = metrics

    # Run health check
    await connection_pool._perform_health_checks()

    # Unhealthy connection should be removed
    assert str(peer_info) not in connection_pool.pool
    assert str(peer_info) not in connection_pool.metrics


@pytest.mark.asyncio
async def test_cleanup_removes_stale_connections(connection_pool, peer_info):
    """Test that cleanup removes stale connections."""
    # Create a stale connection
    mock_connection = {"peer_info": peer_info, "created_at": time.time()}
    connection_pool.pool[str(peer_info)] = mock_connection

    # Set metrics to indicate stale state
    metrics = ConnectionMetrics(last_used=time.time() - 200)  # Very old
    connection_pool.metrics[str(peer_info)] = metrics

    # Run cleanup
    await connection_pool._cleanup_stale_connections()

    # Stale connection should be removed
    assert str(peer_info) not in connection_pool.pool
    assert str(peer_info) not in connection_pool.metrics
