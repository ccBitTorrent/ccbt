"""Additional tests for connection pool Phase 1 to achieve 100% coverage.

Tests edge cases and error paths not covered by main tests.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

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
async def test_create_connection_exception_handling(connection_pool):
    """Test _create_connection handles exceptions."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_peer_connection to raise exception
    async def mock_create_peer_connection(peer_info):
        raise Exception("Connection failed")
    
    connection_pool._create_peer_connection = mock_create_peer_connection
    
    # Should return None on exception
    result = await connection_pool._create_connection(peer_info)
    assert result is None


@pytest.mark.asyncio
async def test_create_connection_no_connection_returned(connection_pool):
    """Test _create_connection when _create_peer_connection returns None."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_peer_connection to return None
    async def mock_create_peer_connection(peer_info):
        return None
    
    connection_pool._create_peer_connection = mock_create_peer_connection
    
    # Should return None
    result = await connection_pool._create_connection(peer_info)
    assert result is None


@pytest.mark.asyncio
async def test_create_connection_metrics_not_present(connection_pool):
    """Test _create_connection when metrics entry doesn't exist yet."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock _create_peer_connection to return connection
    async def mock_create_peer_connection(peer_info):
        return MagicMock()
    
    connection_pool._create_peer_connection = mock_create_peer_connection
    
    # Create connection (metrics won't exist yet)
    result = await connection_pool._create_connection(peer_info)
    
    # Should still create connection
    assert result is not None


@pytest.mark.asyncio
async def test_acquire_removes_unhealthy_connection(connection_pool):
    """Test acquire removes unhealthy connection before creating new one."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Add unhealthy connection
    connection_pool.pool[peer_id] = {"peer_info": peer_info}
    connection_pool.metrics[peer_id] = ConnectionMetrics(is_healthy=False)
    
    # Mock connection creation
    async def mock_create(peer_info):
        return {
            "peer_info": peer_info,
            "connection": MagicMock(),
            "created_at": time.time()
        }
    
    connection_pool._create_connection = mock_create
    
    # Acquire should remove unhealthy and create new
    result = await connection_pool.acquire(peer_info)
    assert result is not None


@pytest.mark.asyncio
async def test_acquire_semaphore_timeout(connection_pool):
    """Test acquire handles semaphore timeout."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Fill semaphore by acquiring all slots
    for i in range(connection_pool.max_connections):
        await connection_pool.semaphore.acquire()
    
    # Mock semaphore to timeout quickly
    original_acquire = connection_pool.semaphore.acquire
    
    async def timeout_acquire():
        raise asyncio.TimeoutError()
    
    connection_pool.semaphore.acquire = timeout_acquire
    
    # Should return None on timeout
    result = await connection_pool.acquire(peer_info)
    assert result is None
    
    # Restore semaphore
    connection_pool.semaphore.acquire = original_acquire
    # Release all slots
    for _ in range(connection_pool.max_connections):
        connection_pool.semaphore.release()


@pytest.mark.asyncio
async def test_release_connection_not_in_pool(connection_pool):
    """Test release when connection not in pool."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Release non-existent connection
    await connection_pool.release(peer_id, MagicMock())
    
    # Should release semaphore
    assert connection_pool.semaphore._value > 0  # noqa: SLF001


@pytest.mark.asyncio
async def test_remove_connection_with_close_method(connection_pool):
    """Test _remove_connection with connection that has close method."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Create connection with close method
    mock_connection = MagicMock()
    mock_connection.close = AsyncMock()
    
    connection_pool.pool[peer_id] = mock_connection
    connection_pool.metrics[peer_id] = ConnectionMetrics()
    
    # Remove connection
    await connection_pool._remove_connection(peer_id)
    
    # Connection should be removed
    assert peer_id not in connection_pool.pool
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_remove_connection_with_sync_close(connection_pool):
    """Test _remove_connection with sync close method."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Create connection with sync close method
    mock_connection = MagicMock()
    mock_connection.close = MagicMock()  # Sync method
    
    connection_pool.pool[peer_id] = mock_connection
    connection_pool.metrics[peer_id] = ConnectionMetrics()
    
    # Remove connection
    await connection_pool._remove_connection(peer_id)
    
    # Connection should be removed
    assert peer_id not in connection_pool.pool


@pytest.mark.asyncio
async def test_remove_connection_close_exception(connection_pool):
    """Test _remove_connection handles close exceptions."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Create connection with failing close
    mock_connection = MagicMock()
    mock_connection.close = AsyncMock(side_effect=Exception("Close failed"))
    
    connection_pool.pool[peer_id] = mock_connection
    connection_pool.metrics[peer_id] = ConnectionMetrics()
    
    # Should handle exception and still remove
    await connection_pool._remove_connection(peer_id)
    assert peer_id not in connection_pool.pool


@pytest.mark.asyncio
async def test_is_connection_valid_none_connection(connection_pool):
    """Test _is_connection_valid with None connection."""
    is_valid = connection_pool._is_connection_valid(None)
    assert not is_valid


@pytest.mark.asyncio
async def test_is_connection_valid_dict_no_connection_key(connection_pool):
    """Test _is_connection_valid with dict missing connection key."""
    connection = {"peer_info": PeerInfo(ip="127.0.0.1", port=6881)}
    is_valid = connection_pool._is_connection_valid(connection)
    assert not is_valid


@pytest.mark.asyncio
async def test_warmup_connections_skips_already_in_pool(connection_pool):
    """Test warmup skips peers already in pool."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Add peer to pool
    connection_pool.pool[peer_id] = {
        "peer_info": peer_info,
        "connection": MagicMock(),
        "created_at": time.time()
    }
    
    warmup_count = 0
    async def mock_acquire(peer_info):
        nonlocal warmup_count
        warmup_count += 1
    
    connection_pool.acquire = mock_acquire
    
    # Warmup should skip existing peer
    await connection_pool.warmup_connections([peer_info], max_count=1)
    
    # Should not attempt warmup
    assert warmup_count == 0


@pytest.mark.asyncio
async def test_warmup_single_connection_exception(connection_pool):
    """Test _warmup_single_connection handles exceptions."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    
    # Mock acquire to raise exception
    async def mock_acquire(peer_info):
        raise Exception("Warmup failed")
    
    connection_pool.acquire = mock_acquire
    
    # Should propagate exception
    with pytest.raises(Exception):
        await connection_pool._warmup_single_connection(peer_info)

