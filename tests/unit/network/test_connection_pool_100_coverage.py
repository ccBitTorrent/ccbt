"""Tests to achieve 100% coverage for connection pool Phase 1 features."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

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
async def test_acquire_reuses_existing_healthy_connection(connection_pool):
    """Test acquire reuses existing healthy connection (lines 146-149)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Create healthy connection with full socket setup
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    
    mock_writer = MagicMock()
    mock_writer.is_closing.return_value = False
    mock_writer.closed = False
    
    # Add transport and socket for socket error check
    mock_transport = MagicMock()
    mock_sock = MagicMock()
    mock_sock.getsockopt.return_value = 0  # No error
    mock_writer._transport = mock_transport
    mock_transport._sock = mock_sock
    mock_conn.writer = mock_writer
    
    connection = {
        "peer_info": peer_info,
        "connection": mock_conn,
        "created_at": time.time()
    }
    
    connection_pool.pool[peer_id] = connection
    metrics = ConnectionMetrics(is_healthy=True)
    metrics.last_used = time.time() - 10  # Recently used
    connection_pool.metrics[peer_id] = metrics
    
    # Acquire should reuse
    result = await connection_pool.acquire(peer_info)
    
    assert result == connection
    assert metrics.usage_count == 1
    assert metrics.last_used > time.time() - 1


@pytest.mark.asyncio
async def test_acquire_handles_exception_during_connection_creation(connection_pool):
    """Test acquire handles exception during connection creation (lines 168-173)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_connection to raise exception
    async def mock_create_connection(peer_info):
        raise Exception("Connection creation failed")
    
    connection_pool._create_connection = mock_create_connection
    
    # Acquire semaphore first
    await connection_pool.semaphore.acquire()
    
    try:
        # Acquire should handle exception
        result = await connection_pool.acquire(peer_info)
        assert result is None
    finally:
        # Ensure semaphore is released
        if connection_pool.semaphore.locked():
            connection_pool.semaphore.release()


@pytest.mark.asyncio
async def test_release_logs_debug_message(connection_pool):
    """Test release logs debug message (line 201)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    connection = {
        "peer_info": peer_info,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    
    connection_pool.pool[peer_id] = connection
    metrics = ConnectionMetrics(usage_count=100)  # Below max
    connection_pool.metrics[peer_id] = metrics
    
    # Release connection
    with patch.object(connection_pool.logger, 'debug') as mock_debug:
        await connection_pool.release(peer_id, connection)
        mock_debug.assert_called_once()


@pytest.mark.asyncio
async def test_remove_connection_public_method(connection_pool):
    """Test remove_connection public method (lines 209-210)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Add connection
    connection = {
        "peer_info": peer_info,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    connection_pool.pool[peer_id] = connection
    connection_pool.metrics[peer_id] = ConnectionMetrics()
    
    # Acquire semaphore
    await connection_pool.semaphore.acquire()
    
    try:
        # Remove connection
        await connection_pool.remove_connection(peer_id)
        
        # Connection should be removed
        assert peer_id not in connection_pool.pool
        assert peer_id not in connection_pool.metrics
    finally:
        # Ensure semaphore is released
        if connection_pool.semaphore.locked():
            connection_pool.semaphore.release()


@pytest.mark.asyncio
async def test_create_peer_connection_warning(connection_pool):
    """Test _create_peer_connection returns None on failure (lines 338-421)."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock config to avoid dependency
    with patch("ccbt.config.config.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.connection_timeout = 1.0
        mock_get_config.return_value = mock_config
        
        # Mock connection to fail (connection will timeout or fail)
        with patch("asyncio.open_connection") as mock_open:
            mock_open.side_effect = OSError("Connection refused")
            
            result = await connection_pool._create_peer_connection(peer_info)
            
            # Should return None on failure
            assert result is None


@pytest.mark.asyncio
async def test_cleanup_stale_connections(connection_pool):
    """Test _cleanup_stale_connections removes stale connections (lines 487-501)."""
    peer_info1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer_info2 = PeerInfo(ip="127.0.0.1", port=6882)
    peer_id1 = f"{peer_info1.ip}:{peer_info1.port}"
    peer_id2 = f"{peer_info2.ip}:{peer_info2.port}"
    
    # Create stale connection (idle for more than max_idle_time * 2)
    connection1 = {
        "peer_info": peer_info1,
        "connection": MagicMock(),
        "created_at": time.time() - 200  # Very old
    }
    connection_pool.pool[peer_id1] = connection1
    metrics1 = ConnectionMetrics(last_used=time.time() - 200)
    connection_pool.metrics[peer_id1] = metrics1
    
    # Create fresh connection
    connection2 = {
        "peer_info": peer_info2,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    connection_pool.pool[peer_id2] = connection2
    metrics2 = ConnectionMetrics(last_used=time.time())
    connection_pool.metrics[peer_id2] = metrics2
    
    # Acquire semaphores
    await connection_pool.semaphore.acquire()
    await connection_pool.semaphore.acquire()
    
    try:
        # Cleanup stale connections
        with patch.object(connection_pool.logger, 'info') as mock_info:
            await connection_pool._cleanup_stale_connections()
            
            # Stale connection should be removed
            assert peer_id1 not in connection_pool.pool
            assert peer_id2 in connection_pool.pool  # Fresh connection should remain
            
            mock_info.assert_called_once()
    finally:
        # Release semaphores
        for _ in range(2):
            if connection_pool.semaphore.locked():
                connection_pool.semaphore.release()

