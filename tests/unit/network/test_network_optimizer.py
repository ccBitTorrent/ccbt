"""Tests for network optimizer."""

import pytest
import socket
import time
from unittest.mock import MagicMock, patch

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.utils.network_optimizer import (
    ConnectionPool,
    ConnectionStats,
    NetworkOptimizer,
    SocketConfig,
    SocketOptimizer,
    SocketType,
    get_network_optimizer,
)


class TestSocketOptimizer:
    """Test cases for SocketOptimizer."""

    @pytest.fixture
    def socket_optimizer(self):
        """Create a SocketOptimizer instance."""
        return SocketOptimizer()

    def test_socket_optimizer_initialization(self, socket_optimizer):
        """Test socket optimizer initialization."""
        assert len(socket_optimizer.configs) == 5
        assert SocketType.PEER_CONNECTION in socket_optimizer.configs
        assert SocketType.TRACKER_HTTP in socket_optimizer.configs
        assert SocketType.TRACKER_UDP in socket_optimizer.configs
        assert SocketType.DHT in socket_optimizer.configs
        assert SocketType.LISTENER in socket_optimizer.configs

    def test_optimize_socket_peer_connection(self, socket_optimizer):
        """Test optimizing socket for peer connection."""
        sock = MagicMock(spec=socket.socket)
        
        socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)
        
        # Check that socket options were set
        sock.setsockopt.assert_called()
        sock.settimeout.assert_called()

    def test_optimize_socket_tracker_http(self, socket_optimizer):
        """Test optimizing socket for tracker HTTP."""
        sock = MagicMock(spec=socket.socket)
        
        socket_optimizer.optimize_socket(sock, SocketType.TRACKER_HTTP)
        
        # Check that socket options were set
        sock.setsockopt.assert_called()
        sock.settimeout.assert_called()

    def test_optimize_socket_tracker_udp(self, socket_optimizer):
        """Test optimizing socket for tracker UDP."""
        sock = MagicMock(spec=socket.socket)
        
        socket_optimizer.optimize_socket(sock, SocketType.TRACKER_UDP)
        
        # Check that socket options were set
        sock.setsockopt.assert_called()
        sock.settimeout.assert_called()

    def test_optimize_socket_dht(self, socket_optimizer):
        """Test optimizing socket for DHT."""
        sock = MagicMock(spec=socket.socket)
        
        socket_optimizer.optimize_socket(sock, SocketType.DHT)
        
        # Check that socket options were set
        sock.setsockopt.assert_called()
        sock.settimeout.assert_called()

    def test_optimize_socket_listener(self, socket_optimizer):
        """Test optimizing socket for listener."""
        sock = MagicMock(spec=socket.socket)
        
        socket_optimizer.optimize_socket(sock, SocketType.LISTENER)
        
        # Check that socket options were set
        sock.setsockopt.assert_called()

    def test_optimize_socket_unknown_type(self, socket_optimizer):
        """Test optimizing socket for unknown type."""
        sock = MagicMock(spec=socket.socket)
        
        # Should not raise exception
        socket_optimizer.optimize_socket(sock, "unknown_type")

    def test_optimize_socket_os_error(self, socket_optimizer):
        """Test optimizing socket with OSError."""
        sock = MagicMock(spec=socket.socket)
        sock.setsockopt.side_effect = OSError("Permission denied")
        
        with pytest.raises(Exception):  # Should raise NetworkError
            socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)

    def test_optimize_socket_tcp_cork_available(self, socket_optimizer):
        """Test optimizing socket with TCP_CORK available."""
        sock = MagicMock(spec=socket.socket)
        
        # Create config with tcp_cork enabled
        config = SocketConfig(SocketType.PEER_CONNECTION, tcp_cork=True)
        socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
        
        # Simulate TCP_CORK being available by adding it to socket module temporarily
        original_tcp_cork = getattr(socket, 'TCP_CORK', None)
        socket.TCP_CORK = 3  # Add TCP_CORK constant
        
        try:
            socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)
            
            # Verify TCP_CORK was set (check that setsockopt was called with TCP_CORK)
            tcp_cork_calls = [
                call for call in sock.setsockopt.call_args_list
                if len(call[0]) >= 2 and call[0][1] == 3  # TCP_CORK = 3
            ]
            assert len(tcp_cork_calls) > 0, "TCP_CORK should have been set"
        finally:
            # Restore original state
            if original_tcp_cork is None:
                if hasattr(socket, 'TCP_CORK'):
                    delattr(socket, 'TCP_CORK')
            else:
                socket.TCP_CORK = original_tcp_cork
    
    def test_optimize_socket_tcp_cork_unavailable(self, socket_optimizer):
        """Test optimizing socket with TCP_CORK unavailable."""
        sock = MagicMock(spec=socket.socket)
        
        # Create config with tcp_cork enabled
        config = SocketConfig(SocketType.PEER_CONNECTION, tcp_cork=True)
        socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
        
        # Ensure TCP_CORK doesn't exist
        original_tcp_cork = getattr(socket, 'TCP_CORK', None)
        if hasattr(socket, 'TCP_CORK'):
            delattr(socket, 'TCP_CORK')
        
        try:
            # Should work fine even if TCP_CORK doesn't exist (default behavior on Windows)
            socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)
            # Should not raise exception
            assert True
        finally:
            # Restore if it existed
            if original_tcp_cork is not None:
                socket.TCP_CORK = original_tcp_cork

    def test_optimize_socket_so_reuseport_available(self, socket_optimizer):
        """Test optimizing socket with SO_REUSEPORT available."""
        sock = MagicMock(spec=socket.socket)
        
        # LISTENER config has so_reuseport=True
        # Simulate SO_REUSEPORT being available by adding it to socket module temporarily
        original_so_reuseport = getattr(socket, 'SO_REUSEPORT', None)
        socket.SO_REUSEPORT = 15  # Add SO_REUSEPORT constant
        
        try:
            socket_optimizer.optimize_socket(sock, SocketType.LISTENER)
            
            # Verify SO_REUSEPORT was set
            so_reuseport_calls = [
                call for call in sock.setsockopt.call_args_list
                if len(call[0]) >= 2 and call[0][1] == 15  # SO_REUSEPORT = 15
            ]
            assert len(so_reuseport_calls) > 0, "SO_REUSEPORT should have been set"
        finally:
            # Restore original state
            if original_so_reuseport is None:
                if hasattr(socket, 'SO_REUSEPORT'):
                    delattr(socket, 'SO_REUSEPORT')
            else:
                socket.SO_REUSEPORT = original_so_reuseport
    
    def test_optimize_socket_keepalive_os_error(self, socket_optimizer):
        """Test optimizing socket when keepalive options raise OSError."""
        sock = MagicMock(spec=socket.socket)
        
        # Make TCP_KEEPIDLE raise OSError
        def mock_setsockopt(*args, **kwargs):
            if len(args) > 1 and args[1] == socket.TCP_KEEPIDLE:
                raise OSError("Option not supported")
            return MagicMock()
        
        sock.setsockopt.side_effect = mock_setsockopt
        
        # Should not raise exception
        socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)

    def test_create_optimized_socket(self, socket_optimizer):
        """Test creating optimized socket."""
        with patch('socket.socket') as mock_socket_class, \
             patch.object(socket_optimizer, '_supports_tcp_window_scaling', return_value=False):
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            
            sock = socket_optimizer.create_optimized_socket(SocketType.PEER_CONNECTION)
            
            assert sock == mock_sock
            mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
            mock_sock.setsockopt.assert_called()
            mock_sock.settimeout.assert_called()

    def test_create_optimized_socket_ipv6(self, socket_optimizer):
        """Test creating optimized socket with IPv6."""
        with patch('socket.socket') as mock_socket_class, \
             patch.object(socket_optimizer, '_supports_tcp_window_scaling', return_value=False):
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            
            sock = socket_optimizer.create_optimized_socket(
                SocketType.PEER_CONNECTION,
                family=socket.AF_INET6,
                sock_type=socket.SOCK_STREAM,
            )
            
            mock_socket_class.assert_called_once_with(socket.AF_INET6, socket.SOCK_STREAM)

    def test_create_optimized_socket_udp(self, socket_optimizer):
        """Test creating optimized socket with UDP."""
        with patch('socket.socket') as mock_socket_class, \
             patch.object(socket_optimizer, '_supports_tcp_window_scaling', return_value=False):
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            
            sock = socket_optimizer.create_optimized_socket(
                SocketType.TRACKER_UDP,
                family=socket.AF_INET,
                sock_type=socket.SOCK_DGRAM,
            )
            
            mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)


class TestConnectionPool:
    """Test cases for ConnectionPool."""

    @pytest.fixture
    def connection_pool(self):
        """Create a ConnectionPool instance."""
        return ConnectionPool(max_connections=10, connection_timeout=5.0, idle_timeout=60.0)

    def test_connection_pool_initialization(self, connection_pool):
        """Test connection pool initialization."""
        assert connection_pool.max_connections == 10
        assert connection_pool.connection_timeout == 5.0
        assert connection_pool.idle_timeout == 60.0
        assert len(connection_pool.connections) == 0
        assert len(connection_pool.connection_times) == 0
        assert len(connection_pool.last_activity) == 0

    def test_get_connection_new_connection(self, connection_pool):
        """Test getting new connection."""
        with patch.object(connection_pool, '_create_connection') as mock_create:
            mock_sock = MagicMock(spec=socket.socket)
            mock_sock.fileno.return_value = 1
            mock_create.return_value = mock_sock
            
            sock = connection_pool.get_connection("192.168.1.1", 6881)
            
            assert sock == mock_sock
            assert connection_pool.stats.total_connections == 1
            assert connection_pool.stats.active_connections == 1
            mock_create.assert_called_once_with("192.168.1.1", 6881, SocketType.PEER_CONNECTION)

    def test_get_connection_existing_connection(self, connection_pool):
        """Test getting existing connection from pool."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 1
        
        # Add connection to pool
        connection_pool.connections[("192.168.1.1", 6881)] = [mock_sock]
        
        sock = connection_pool.get_connection("192.168.1.1", 6881)
        
        assert sock == mock_sock
        assert connection_pool.stats.active_connections == 1
        assert len(connection_pool.connections[("192.168.1.1", 6881)]) == 0

    def test_get_connection_failed_creation(self, connection_pool):
        """Test getting connection when creation fails."""
        with patch.object(connection_pool, '_create_connection') as mock_create:
            mock_create.return_value = None
            
            sock = connection_pool.get_connection("192.168.1.1", 6881)
            
            assert sock is None
            # The implementation doesn't increment failed_connections when _create_connection returns None
            assert connection_pool.stats.failed_connections == 0

    def test_get_connection_exception(self, connection_pool):
        """Test getting connection when creation raises exception."""
        with patch.object(connection_pool, '_create_connection') as mock_create:
            mock_create.side_effect = Exception("Connection failed")
            
            sock = connection_pool.get_connection("192.168.1.1", 6881)
            
            assert sock is None
            assert connection_pool.stats.failed_connections == 1

    def test_return_connection_to_pool(self, connection_pool):
        """Test returning connection to pool."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 1
        
        connection_pool.stats.active_connections = 1
        
        connection_pool.return_connection(mock_sock, "192.168.1.1", 6881)
        
        assert ("192.168.1.1", 6881) in connection_pool.connections
        assert mock_sock in connection_pool.connections[("192.168.1.1", 6881)]
        assert connection_pool.stats.active_connections == 0

    def test_return_connection_closed_socket(self, connection_pool):
        """Test returning closed socket."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = -1  # Closed socket
        
        connection_pool.connection_times[mock_sock] = 1234567890
        connection_pool.last_activity[mock_sock] = 1234567890
        
        connection_pool.return_connection(mock_sock, "192.168.1.1", 6881)
        
        # Should be removed from tracking
        assert mock_sock not in connection_pool.connection_times
        assert mock_sock not in connection_pool.last_activity

    def test_return_connection_pool_full(self, connection_pool):
        """Test returning connection when pool is full."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.fileno.return_value = 1
        
        # Fill the pool
        key = ("192.168.1.1", 6881)
        connection_pool.connections[key] = [MagicMock() for _ in range(connection_pool.max_connections)]
        
        connection_pool.return_connection(mock_sock, "192.168.1.1", 6881)
        
        # Should not be added to pool
        assert len(connection_pool.connections[key]) == connection_pool.max_connections

    def test_create_connection_success(self, connection_pool):
        """Test successful connection creation."""
        with patch('socket.socket') as mock_socket_class, \
             patch('ccbt.network_optimizer.SocketOptimizer') as mock_optimizer_class:
            
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            mock_optimizer = MagicMock()
            mock_optimizer_class.return_value = mock_optimizer
            
            sock = connection_pool._create_connection("192.168.1.1", 6881, SocketType.PEER_CONNECTION)
            
            assert sock == mock_sock
            mock_sock.settimeout.assert_called_once_with(connection_pool.connection_timeout)
            mock_optimizer.optimize_socket.assert_called_once_with(mock_sock, SocketType.PEER_CONNECTION)
            mock_sock.connect.assert_called_once_with(("192.168.1.1", 6881))

    def test_create_connection_failure(self, connection_pool):
        """Test connection creation failure."""
        with patch('socket.socket') as mock_socket_class:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = Exception("Connection refused")
            mock_socket_class.return_value = mock_sock
            
            sock = connection_pool._create_connection("192.168.1.1", 6881, SocketType.PEER_CONNECTION)
            
            assert sock is None

    def test_remove_connection(self, connection_pool):
        """Test removing connection from tracking."""
        mock_sock = MagicMock()
        connection_pool.connection_times[mock_sock] = 1234567890
        connection_pool.last_activity[mock_sock] = 1234567890
        
        connection_pool._remove_connection(mock_sock)
        
        assert mock_sock not in connection_pool.connection_times
        assert mock_sock not in connection_pool.last_activity
        mock_sock.close.assert_called_once()

    def test_get_stats(self, connection_pool):
        """Test getting connection pool statistics."""
        connection_pool.stats.total_connections = 10
        connection_pool.stats.active_connections = 5
        connection_pool.stats.failed_connections = 2
        connection_pool.stats.bytes_sent = 1024
        connection_pool.stats.bytes_received = 2048
        connection_pool.stats.connection_time = 1.5
        connection_pool.stats.last_activity = 1234567890
        
        stats = connection_pool.get_stats()
        
        assert isinstance(stats, ConnectionStats)
        assert stats.total_connections == 10
        assert stats.active_connections == 5
        assert stats.failed_connections == 2
        assert stats.bytes_sent == 1024
        assert stats.bytes_received == 2048
        assert stats.connection_time == 1.5
        assert stats.last_activity == 1234567890


class TestNetworkOptimizer:
    """Test cases for NetworkOptimizer."""

    @pytest.fixture
    def network_optimizer(self):
        """Create a NetworkOptimizer instance."""
        return NetworkOptimizer()

    def test_network_optimizer_initialization(self, network_optimizer):
        """Test network optimizer initialization."""
        assert network_optimizer.socket_optimizer is not None
        assert network_optimizer.connection_pool is not None

    def test_optimize_peer_socket(self, network_optimizer):
        """Test optimizing peer socket."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.socket_optimizer, 'optimize_socket') as mock_optimize:
            network_optimizer.optimize_peer_socket(mock_sock)
            
            mock_optimize.assert_called_once_with(mock_sock, SocketType.PEER_CONNECTION)

    def test_optimize_tracker_socket(self, network_optimizer):
        """Test optimizing tracker socket."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.socket_optimizer, 'optimize_socket') as mock_optimize:
            network_optimizer.optimize_tracker_socket(mock_sock)
            
            mock_optimize.assert_called_once_with(mock_sock, SocketType.TRACKER_HTTP)

    def test_optimize_dht_socket(self, network_optimizer):
        """Test optimizing DHT socket."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.socket_optimizer, 'optimize_socket') as mock_optimize:
            network_optimizer.optimize_dht_socket(mock_sock)
            
            mock_optimize.assert_called_once_with(mock_sock, SocketType.DHT)

    def test_get_connection(self, network_optimizer):
        """Test getting connection."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.connection_pool, 'get_connection') as mock_get_connection:
            mock_get_connection.return_value = mock_sock
            
            sock = network_optimizer.get_connection("192.168.1.1", 6881)
            
            assert sock == mock_sock
            mock_get_connection.assert_called_once_with("192.168.1.1", 6881, SocketType.PEER_CONNECTION)

    def test_get_connection_with_socket_type(self, network_optimizer):
        """Test getting connection with specific socket type."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.connection_pool, 'get_connection') as mock_get_connection:
            mock_get_connection.return_value = mock_sock
            
            sock = network_optimizer.get_connection("192.168.1.1", 6881, SocketType.DHT)
            
            assert sock == mock_sock
            mock_get_connection.assert_called_once_with("192.168.1.1", 6881, SocketType.DHT)

    def test_return_connection(self, network_optimizer):
        """Test returning connection."""
        mock_sock = MagicMock()
        
        with patch.object(network_optimizer.connection_pool, 'return_connection') as mock_return_connection:
            network_optimizer.return_connection(mock_sock, "192.168.1.1", 6881)
            
            mock_return_connection.assert_called_once_with(mock_sock, "192.168.1.1", 6881)

    def test_get_stats(self, network_optimizer):
        """Test getting optimization statistics."""
        mock_stats = ConnectionStats(
            total_connections=10,
            active_connections=5,
            failed_connections=2,
            bytes_sent=1024,
            bytes_received=2048,
            connection_time=1.5,
            last_activity=1234567890,
        )
        
        with patch.object(network_optimizer.connection_pool, 'get_stats') as mock_get_stats:
            mock_get_stats.return_value = mock_stats
            
            stats = network_optimizer.get_stats()
            
            assert "connection_pool" in stats
            assert "socket_configs" in stats
            assert stats["connection_pool"] == mock_stats
            assert len(stats["socket_configs"]) == 5


def test_get_network_optimizer_singleton():
    """Test getting global network optimizer singleton."""
    # First call should create instance
    optimizer1 = get_network_optimizer()
    assert isinstance(optimizer1, NetworkOptimizer)
    
    # Second call should return same instance
    optimizer2 = get_network_optimizer()
    assert optimizer1 is optimizer2


def test_socket_config_initialization():
    """Test SocketConfig initialization."""
    config = SocketConfig(SocketType.PEER_CONNECTION)
    
    assert config.socket_type == SocketType.PEER_CONNECTION
    assert config.tcp_nodelay is True
    assert config.tcp_cork is False
    assert config.so_reuseport is False
    assert config.so_reuseaddr is True
    assert config.so_keepalive is True
    assert config.so_rcvbuf == 256 * 1024
    assert config.so_sndbuf == 256 * 1024
    assert config.so_rcvtimeo == 30.0
    assert config.so_sndtimeo == 30.0
    assert config.tcp_keepalive_idle == 600
    assert config.tcp_keepalive_interval == 60
    assert config.tcp_keepalive_probes == 3


def test_connection_stats_initialization():
    """Test ConnectionStats initialization."""
    stats = ConnectionStats()
    
    assert stats.total_connections == 0
    assert stats.active_connections == 0
    assert stats.failed_connections == 0
    assert stats.bytes_sent == 0
    assert stats.bytes_received == 0
    assert stats.connection_time == 0.0
    assert stats.last_activity == 0.0


def test_socket_type_enum():
    """Test SocketType enum values."""
    assert SocketType.PEER_CONNECTION.value == "peer_connection"
    assert SocketType.TRACKER_HTTP.value == "tracker_http"
    assert SocketType.TRACKER_UDP.value == "tracker_udp"
    assert SocketType.DHT.value == "dht"
    assert SocketType.LISTENER.value == "listener"
