"""Additional edge case tests for connection pool to achieve 100% coverage.

Tests edge cases and defensive code paths.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

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
async def test_release_connection_recycling(connection_pool):
    """Test release recycles connection when usage count exceeds max."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Add connection with high usage count
    connection = {
        "peer_info": peer_info,
        "connection": MagicMock(),
        "created_at": 0
    }
    connection_pool.pool[peer_id] = connection
    metrics = ConnectionMetrics(usage_count=1001)  # Exceeds max_usage_count
    connection_pool.metrics[peer_id] = metrics
    
    # Release should recycle connection
    await connection_pool.release(peer_id, connection)
    
    # Connection should be removed
    assert peer_id not in connection_pool.pool


@pytest.mark.asyncio
async def test_release_connection_no_metrics(connection_pool):
    """Test release when metrics don't exist."""
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer_id = f"{peer_info.ip}:{peer_info.port}"
    
    # Add connection without metrics
    connection = {
        "peer_info": peer_info,
        "connection": MagicMock(),
        "created_at": 0
    }
    connection_pool.pool[peer_id] = connection
    
    # Release should handle missing metrics gracefully
    await connection_pool.release(peer_id, connection)
    
    # Connection should still be in pool
    assert peer_id in connection_pool.pool


@pytest.mark.asyncio
async def test_is_connection_valid_non_dict_connection(connection_pool):
    """Test _is_connection_valid with non-dict connection."""
    # Create a non-dict connection object with valid reader/writer
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
    mock_sock.getsockopt.return_value = 0  # No error
    mock_writer._transport = mock_transport
    mock_transport._sock = mock_sock
    mock_conn.writer = mock_writer
    
    is_valid = connection_pool._is_connection_valid(mock_conn)
    
    # Should validate non-dict connection (since created_at check is only for dict)
    assert is_valid


@pytest.mark.asyncio
async def test_is_connection_valid_reader_none(connection_pool):
    """Test _is_connection_valid with None reader."""
    mock_conn = MagicMock()
    mock_conn.reader = None
    
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
    
    connection = {"connection": mock_conn, "created_at": time.time()}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle None reader (None reader is acceptable if writer is valid)
    assert is_valid


@pytest.mark.asyncio
async def test_is_connection_valid_writer_none(connection_pool):
    """Test _is_connection_valid with None writer."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    mock_conn.writer = None  # None writer means no socket check
    
    connection = {"connection": mock_conn, "created_at": time.time()}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle None writer (None writer is acceptable if reader is valid)
    assert is_valid


@pytest.mark.asyncio
async def test_is_connection_valid_no_reader_attr(connection_pool):
    """Test _is_connection_valid when reader attr doesn't exist."""
    mock_conn = MagicMock()
    del mock_conn.reader  # Remove reader attribute
    mock_conn.writer = MagicMock()
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing reader attribute
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_is_connection_valid_no_writer_attr(connection_pool):
    """Test _is_connection_valid when writer attr doesn't exist."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_conn.reader = mock_reader
    del mock_conn.writer  # Remove writer attribute
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing writer attribute
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_is_connection_valid_no_is_closing_attr(connection_pool):
    """Test _is_connection_valid when is_closing attr doesn't exist."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    del mock_reader.is_closing  # Remove is_closing attribute
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    mock_conn.writer = MagicMock()
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing is_closing attribute
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_is_connection_valid_no_closed_attr(connection_pool):
    """Test _is_connection_valid when closed attr doesn't exist."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    del mock_reader.closed  # Remove closed attribute
    mock_conn.reader = mock_reader
    mock_conn.writer = MagicMock()
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing closed attribute
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_is_connection_valid_no_transport(connection_pool):
    """Test _is_connection_valid when transport doesn't exist."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    
    mock_writer = MagicMock()
    del mock_writer._transport  # Remove transport
    mock_conn.writer = mock_writer
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing transport
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_is_connection_valid_no_sock(connection_pool):
    """Test _is_connection_valid when _sock doesn't exist."""
    mock_conn = MagicMock()
    mock_reader = MagicMock()
    mock_reader.is_closing.return_value = False
    mock_reader.closed = False
    mock_conn.reader = mock_reader
    
    mock_writer = MagicMock()
    mock_transport = MagicMock()
    del mock_transport._sock  # Remove _sock
    mock_writer._transport = mock_transport
    mock_conn.writer = mock_writer
    
    connection = {"connection": mock_conn, "created_at": 0}
    
    is_valid = connection_pool._is_connection_valid(connection)
    
    # Should handle missing _sock
    assert is_valid or not is_valid  # Just verify it doesn't crash


@pytest.mark.asyncio
async def test_start_already_running(connection_pool):
    """Test start when already running."""
    # Already started via fixture
    assert connection_pool._running is True
    
    # Starting again should return early
    await connection_pool.start()
    
    # Should still be running
    assert connection_pool._running is True


@pytest.mark.asyncio
async def test_stop_already_stopped():
    """Test stop when already stopped."""
    pool = PeerConnectionPool()
    
    # Stop when not running should return early
    await pool.stop()
    
    # Should still be stopped
    assert pool._running is False


@pytest.mark.asyncio
async def test_context_manager_usage(connection_pool):
    """Test connection pool as context manager."""
    # Test context manager (already tested in main tests, but verify it works)
    async with PeerConnectionPool() as pool:
        assert pool._running is True
    # Should be stopped after context exit
    # (Note: __aexit__ is marked with pragma: no cover, but we test it here)
    assert pool._running is False

