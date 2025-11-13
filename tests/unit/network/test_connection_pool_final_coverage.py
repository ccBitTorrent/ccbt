"""Final tests to achieve 100% coverage for connection pool."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.network, pytest.mark.connection]

from ccbt.peer.connection_pool import ConnectionMetrics, PeerConnectionPool
from ccbt.models import PeerInfo


@pytest_asyncio.fixture
async def connection_pool():
    """Create a test connection pool."""
    pool = PeerConnectionPool(max_connections=10, max_idle_time=60.0)
    await pool.start()
    yield pool
    await pool.stop()


@pytest.mark.asyncio
async def test_is_connection_valid_writer_closed(connection_pool):
    """Test _is_connection_valid detects closed writer (line 374)."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    
    mock_writer = MagicMock()
    mock_writer.is_closing.return_value = False
    mock_writer.closed = True  # Closed writer
    mock_conn.writer = mock_writer
    
    connection = {"connection": mock_conn, "created_at": time.time()}
    
    is_valid = connection_pool._is_connection_valid(connection)
    assert not is_valid


@pytest.mark.asyncio
async def test_is_connection_valid_socket_error_nonzero(connection_pool):
    """Test _is_connection_valid detects socket error (line 387)."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    
    mock_writer = MagicMock()
    mock_writer.is_closing.return_value = False
    mock_writer.closed = False
    
    mock_transport = MagicMock()
    mock_sock = MagicMock()
    mock_sock.getsockopt.return_value = 104  # Non-zero error
    mock_writer._transport = mock_transport
    mock_transport._sock = mock_sock
    mock_conn.writer = mock_writer
    
    connection = {"connection": mock_conn, "created_at": time.time()}
    
    is_valid = connection_pool._is_connection_valid(connection)
    assert not is_valid


@pytest.mark.asyncio
async def test_cleanup_loop_exception_handling(connection_pool):
    """Test _cleanup_loop handles exceptions (lines 439-440)."""
    # Mock _cleanup_stale_connections to raise exception
    async def mock_cleanup():
        raise Exception("Cleanup failed")
    
    connection_pool._cleanup_stale_connections = mock_cleanup
    
    # Run cleanup loop briefly
    try:
        await asyncio.wait_for(connection_pool._cleanup_loop(), timeout=0.1)
    except asyncio.TimeoutError:
        pass  # Expected - loop runs indefinitely
    
    # Should handle exception gracefully
    assert True


@pytest.mark.asyncio
async def test_perform_health_checks_logs_unhealthy(connection_pool):
    """Test _perform_health_checks logs unhealthy connections (lines 466-467, 471-472)."""
    peer_info1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer_info2 = PeerInfo(ip="127.0.0.1", port=6882)
    peer_id1 = f"{peer_info1.ip}:{peer_info1.port}"
    peer_id2 = f"{peer_info2.ip}:{peer_info2.port}"
    
    # Create connection with high usage count
    connection1 = {
        "peer_info": peer_info1,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    connection_pool.pool[peer_id1] = connection1
    metrics1 = ConnectionMetrics(usage_count=1001)  # Exceeds max
    connection_pool.metrics[peer_id1] = metrics1
    
    # Create connection with many errors
    connection2 = {
        "peer_info": peer_info2,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    connection_pool.pool[peer_id2] = connection2
    metrics2 = ConnectionMetrics(errors=11)  # Exceeds threshold
    connection_pool.metrics[peer_id2] = metrics2
    
    # Acquire semaphores
    await connection_pool.semaphore.acquire()
    await connection_pool.semaphore.acquire()
    
    try:
        with patch.object(connection_pool.logger, 'debug') as mock_debug:
            await connection_pool._perform_health_checks()
            
            # Should log about unhealthy connections
            assert mock_debug.called
    finally:
        # Release semaphores
        for _ in range(2):
            if connection_pool.semaphore.locked():
                connection_pool.semaphore.release()


@pytest.mark.asyncio
async def test_update_connection_metrics(connection_pool):
    """Test update_connection_metrics updates metrics (lines 518-522)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    metrics = ConnectionMetrics()
    connection_pool.metrics[peer_id] = metrics
    
    # Update metrics
    connection_pool.update_connection_metrics(peer_id, 1000, 2000, 5)
    
    assert metrics.bytes_sent == 1000
    assert metrics.bytes_received == 2000
    assert metrics.errors == 5


@pytest.mark.asyncio
async def test_update_connection_metrics_no_metrics(connection_pool):
    """Test update_connection_metrics when metrics don't exist."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Update metrics for non-existent peer
    connection_pool.update_connection_metrics(peer_id, 1000, 2000, 5)
    
    # Should not crash
    assert True

