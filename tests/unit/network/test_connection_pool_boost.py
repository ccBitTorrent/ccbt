"""Additional tests for connection pool to boost coverage to 90%+."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network, pytest.mark.connection]

from ccbt.peer.connection_pool import ConnectionMetrics, PeerConnectionPool
from ccbt.models import PeerInfo


@pytest.mark.asyncio
async def test_start_when_already_running():
    """Test start() when pool is already running."""
    pool = PeerConnectionPool()
    await pool.start()
    assert pool._running is True
    
    # Try to start again - should return early
    await pool.start()
    assert pool._running is True
    
    await pool.stop()


@pytest.mark.asyncio
async def test_stop_when_not_running():
    """Test stop() when pool is not running."""
    pool = PeerConnectionPool()
    assert pool._running is False
    
    # Stop when not running should return early
    await pool.stop()
    assert pool._running is False


@pytest.mark.asyncio
async def test_acquire_existing_unhealthy_connection():
    """Test acquire() when connection exists but is unhealthy."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Add unhealthy connection to pool
        mock_connection = {"peer_info": peer_info, "connection": MagicMock()}
        pool.pool[peer_id] = mock_connection
        metrics = ConnectionMetrics(is_healthy=False)
        pool.metrics[peer_id] = metrics
        
        # Mock _is_connection_valid to return True
        pool._is_connection_valid = MagicMock(return_value=True)
        
        # Mock _create_connection to return new connection
        new_connection = {"peer_info": peer_info, "created_at": time.time()}
        pool._create_connection = AsyncMock(return_value=new_connection)
        
        # Acquire should remove old connection and create new one
        connection = await pool.acquire(peer_info)
        
        # Should have new connection
        assert connection is not None
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_acquire_exception_handling():
    """Test exception handling in acquire()."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        
        # Mock semaphore acquire to succeed
        async def mock_acquire():
            return None
        pool.semaphore.acquire = mock_acquire
        
        # Mock _create_connection to raise exception
        pool._create_connection = AsyncMock(side_effect=RuntimeError("Connection failed"))
        
        # Acquire should handle exception gracefully
        connection = await pool.acquire(peer_info)
        
        assert connection is None
        # Semaphore should be released on exception
        assert pool.semaphore._value > 0  # noqa: SLF001
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_release_when_peer_not_in_pool():
    """Test release() when peer_id is not in pool."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        # Release non-existent connection
        await pool.release("nonexistent:1234", MagicMock())
        
        # Semaphore should be released
        assert pool.semaphore._value > 0  # noqa: SLF001
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_create_connection_exception():
    """Test _create_connection exception handling."""
    pool = PeerConnectionPool()
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_peer_connection to raise exception
    pool._create_peer_connection = AsyncMock(side_effect=RuntimeError("Connection error"))
    
    # Should handle exception and return None
    connection = await pool._create_connection(peer_info)
    assert connection is None


@pytest.mark.asyncio
async def test_create_peer_connection_warning():
    """Test _create_peer_connection warning path."""
    pool = PeerConnectionPool()
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Call _create_peer_connection directly - should log warning and return None
    with patch.object(pool.logger, 'warning') as mock_warning:
        result = await pool._create_peer_connection(peer_info)
        assert result is None
        mock_warning.assert_called_once()


@pytest.mark.asyncio
async def test_remove_connection_sync_close():
    """Test _remove_connection with synchronous close method."""
    pool = PeerConnectionPool()
    peer_id = "127.0.0.1:6881"
    
    # Create mock connection with sync close
    mock_connection = MagicMock()
    mock_connection.close = MagicMock()  # Not async
    
    pool.pool[peer_id] = mock_connection
    pool.metrics[peer_id] = ConnectionMetrics()
    
    await pool._remove_connection(peer_id)
    
    mock_connection.close.assert_called_once()
    assert peer_id not in pool.pool


@pytest.mark.asyncio
async def test_remove_connection_close_exception():
    """Test _remove_connection when close() raises exception."""
    pool = PeerConnectionPool()
    peer_id = "127.0.0.1:6881"
    
    # Create mock connection with close that raises
    mock_connection = MagicMock()
    mock_connection.close = AsyncMock(side_effect=RuntimeError("Close failed"))
    
    pool.pool[peer_id] = mock_connection
    pool.metrics[peer_id] = ConnectionMetrics()
    
    # Should handle exception and still remove connection
    with patch.object(pool.logger, 'warning') as mock_warning:
        await pool._remove_connection(peer_id)
        mock_warning.assert_called_once()
    
    assert peer_id not in pool.pool


@pytest.mark.asyncio
async def test_health_check_loop_exception():
    """Test health check loop exception handling."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        # Mock _perform_health_checks to raise exception
        pool._perform_health_checks = AsyncMock(side_effect=RuntimeError("Health check failed"))
        
        # Wait a bit for loop to run
        await asyncio.sleep(0.1)
        
        # Loop should still be running (exception handled)
        assert pool._health_check_task is not None
        assert not pool._health_check_task.done()
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_cleanup_loop_exception():
    """Test cleanup loop exception handling."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        # Mock _cleanup_stale_connections to raise exception
        pool._cleanup_stale_connections = AsyncMock(side_effect=RuntimeError("Cleanup failed"))
        
        # Wait a bit for loop to run
        await asyncio.sleep(0.1)
        
        # Loop should still be running (exception handled)
        assert pool._cleanup_task is not None
        assert not pool._cleanup_task.done()
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_perform_health_checks_idle_timeout():
    """Test health checks for idle timeout."""
    pool = PeerConnectionPool(max_idle_time=1.0)
    await pool.start()
    try:
        peer_id = "127.0.0.1:6881"
        mock_connection = {"peer_info": PeerInfo(ip="127.0.0.1", port=6881)}
        pool.pool[peer_id] = mock_connection
        
        # Set last_used to be beyond max_idle_time
        metrics = ConnectionMetrics(last_used=time.time() - 2.0)
        pool.metrics[peer_id] = metrics
        
        await pool._perform_health_checks()
        
        # Connection should be marked unhealthy and removed
        assert peer_id not in pool.pool
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_perform_health_checks_usage_count():
    """Test health checks for max usage count."""
    pool = PeerConnectionPool(max_usage_count=100)
    await pool.start()
    try:
        peer_id = "127.0.0.1:6881"
        mock_connection = {"peer_info": PeerInfo(ip="127.0.0.1", port=6881)}
        pool.pool[peer_id] = mock_connection
        
        # Set usage_count beyond max
        metrics = ConnectionMetrics(usage_count=101)
        pool.metrics[peer_id] = metrics
        
        await pool._perform_health_checks()
        
        # Connection should be marked unhealthy and removed
        assert peer_id not in pool.pool
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_perform_health_checks_error_threshold():
    """Test health checks for error threshold."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        peer_id = "127.0.0.1:6881"
        mock_connection = {"peer_info": PeerInfo(ip="127.0.0.1", port=6881)}
        pool.pool[peer_id] = mock_connection
        
        # Set errors above threshold (10)
        metrics = ConnectionMetrics(errors=11)
        pool.metrics[peer_id] = metrics
        
        await pool._perform_health_checks()
        
        # Connection should be marked unhealthy and removed
        assert peer_id not in pool.pool
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_cleanup_stale_connections():
    """Test cleanup of stale connections."""
    pool = PeerConnectionPool(max_idle_time=1.0)
    await pool.start()
    try:
        peer_id = "127.0.0.1:6881"
        mock_connection = {"peer_info": PeerInfo(ip="127.0.0.1", port=6881)}
        pool.pool[peer_id] = mock_connection
        
        # Set last_used to be beyond 2x max_idle_time
        metrics = ConnectionMetrics(last_used=time.time() - 3.0)
        pool.metrics[peer_id] = metrics
        
        await pool._cleanup_stale_connections()
        
        # Stale connection should be removed
        assert peer_id not in pool.pool
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_context_manager():
    """Test context manager __aenter__ and __aexit__."""
    async with PeerConnectionPool() as pool:
        assert pool._running is True
        # __aexit__ should be called on exit
    assert pool._running is False


@pytest.mark.asyncio
async def test_acquire_reuse_healthy_connection():
    """Test acquire() reusing existing healthy connection."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Add healthy connection to pool
        mock_connection = {"peer_info": peer_info, "connection": MagicMock()}
        pool.pool[peer_id] = mock_connection
        metrics = ConnectionMetrics(is_healthy=True)
        pool.metrics[peer_id] = metrics
        
        # Mock _is_connection_valid to return True
        pool._is_connection_valid = MagicMock(return_value=True)
        
        # Acquire should reuse existing connection
        connection = await pool.acquire(peer_info)
        
        # Should return existing connection and update metrics
        assert connection == mock_connection
        assert metrics.usage_count == 1
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_acquire_timeout():
    """Test acquire() timeout handling."""
    pool = PeerConnectionPool(max_connections=1)
    await pool.start()
    try:
        peer_info1 = PeerInfo(ip="127.0.0.1", port=6881)
        peer_info2 = PeerInfo(ip="127.0.0.2", port=6881)
        
        # Acquire first connection
        mock_conn = {"peer_info": peer_info1, "created_at": time.time()}
        pool._create_connection = AsyncMock(return_value=mock_conn)
        await pool.acquire(peer_info1)
        
        # Try to acquire second connection - should timeout
        pool._create_connection = AsyncMock(return_value=mock_conn)
        connection = await pool.acquire(peer_info2)
        
        # Should return None due to timeout
        assert connection is None
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_release_normal_path():
    """Test release() normal path (not recycling)."""
    pool = PeerConnectionPool(max_usage_count=1000)
    await pool.start()
    try:
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Create connection and add to pool
        mock_connection = {"peer_info": peer_info, "created_at": time.time()}
        pool.pool[peer_id] = mock_connection
        metrics = ConnectionMetrics(usage_count=500)  # Below max
        pool.metrics[peer_id] = metrics
        
        # Release connection
        await pool.release(peer_id, mock_connection)
        
        # Connection should still be in pool (not recycled)
        assert peer_id in pool.pool
        assert metrics.last_used > 0
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_remove_connection_public_method():
    """Test remove_connection() public method."""
    pool = PeerConnectionPool()
    await pool.start()
    try:
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer_id = f"{peer_info.ip}:{peer_info.port}"
        
        # Add connection
        mock_connection = {"peer_info": peer_info, "connection": MagicMock()}
        pool.pool[peer_id] = mock_connection
        pool.metrics[peer_id] = ConnectionMetrics()
        
        # Acquire semaphore first
        await pool.semaphore.acquire()
        
        # Remove connection
        await pool.remove_connection(peer_id)
        
        # Connection should be removed and semaphore released
        assert peer_id not in pool.pool
        assert pool.semaphore._value > 0  # noqa: SLF001
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_create_connection_success():
    """Test _create_connection success path."""
    pool = PeerConnectionPool()
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_peer_connection to return connection
    mock_peer_conn = MagicMock()
    pool._create_peer_connection = AsyncMock(return_value=mock_peer_conn)
    
    # Should create connection successfully
    connection = await pool._create_connection(peer_info)
    
    assert connection is not None
    assert connection["peer_info"] == peer_info
    assert "created_at" in connection


@pytest.mark.asyncio
async def test_is_connection_valid():
    """Test _is_connection_valid default behavior."""
    pool = PeerConnectionPool()
    mock_connection = MagicMock()
    
    # Should return True by default
    result = pool._is_connection_valid(mock_connection)
    assert result is True


@pytest.mark.asyncio
async def test_update_connection_metrics():
    """Test update_connection_metrics method."""
    pool = PeerConnectionPool()
    peer_id = "127.0.0.1:6881"
    
    # Create metrics
    metrics = ConnectionMetrics()
    pool.metrics[peer_id] = metrics
    
    # Update metrics
    pool.update_connection_metrics(
        peer_id,
        bytes_sent=100,
        bytes_received=200,
        errors=1
    )
    
    assert metrics.bytes_sent == 100
    assert metrics.bytes_received == 200
    assert metrics.errors == 1
    
    # Update again (accumulate)
    pool.update_connection_metrics(
        peer_id,
        bytes_sent=50,
        bytes_received=75,
        errors=0
    )
    
    assert metrics.bytes_sent == 150
    assert metrics.bytes_received == 275
    assert metrics.errors == 1


@pytest.mark.asyncio
async def test_update_connection_metrics_nonexistent():
    """Test update_connection_metrics with nonexistent peer."""
    pool = PeerConnectionPool()
    
    # Should not raise exception
    pool.update_connection_metrics("nonexistent", bytes_sent=100)

