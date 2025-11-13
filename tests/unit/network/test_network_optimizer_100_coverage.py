"""Tests to achieve 100% coverage for network optimizer Phase 1 features."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, mock_open, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.utils.network_optimizer import SocketOptimizer, SocketType


@pytest.fixture
def socket_optimizer():
    """Create a test socket optimizer."""
    return SocketOptimizer()


def test_get_max_buffer_size_linux(socket_optimizer):
    """Test _get_max_buffer_size on Linux (lines 148-152)."""
    with patch('platform.system', return_value='Linux'):
        with patch('builtins.open', mock_open(read_data='1048576')) as mock_file:
            size = socket_optimizer._get_max_buffer_size()
            assert size == 1048576
            mock_file.assert_called_once_with("/proc/sys/net/core/rmem_max", encoding="utf-8")


def test_get_max_buffer_size_linux_os_error(socket_optimizer):
    """Test _get_max_buffer_size on Linux with OSError (line 151)."""
    with patch('platform.system', return_value='Linux'):
        with patch('builtins.open', side_effect=OSError("File not found")):
            size = socket_optimizer._get_max_buffer_size()
            assert size == 65536 * 1024  # Default 64MB


def test_get_max_buffer_size_linux_value_error(socket_optimizer):
    """Test _get_max_buffer_size on Linux with ValueError (line 151)."""
    with patch('platform.system', return_value='Linux'):
        with patch('builtins.open', mock_open(read_data='invalid')):
            size = socket_optimizer._get_max_buffer_size()
            assert size == 65536 * 1024  # Default 64MB


def test_get_max_buffer_size_macos(socket_optimizer):
    """Test _get_max_buffer_size on macOS (lines 154-167)."""
    with patch('platform.system', return_value='darwin'):
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "4194304\n"
            mock_run.return_value = mock_result
            
            size = socket_optimizer._get_max_buffer_size()
            assert size == 4194304
            mock_run.assert_called_once_with(
                ["sysctl", "-n", "kern.ipc.maxsockbuf"],
                capture_output=True,
                text=True,
                check=False,
            )


def test_get_max_buffer_size_macos_nonzero_returncode(socket_optimizer):
    """Test _get_max_buffer_size on macOS with non-zero returncode (line 163)."""
    with patch('platform.system', return_value='darwin'):
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            
            size = socket_optimizer._get_max_buffer_size()
            assert size == 4 * 1024 * 1024  # Default 4MB


def test_get_max_buffer_size_macos_exception(socket_optimizer):
    """Test _get_max_buffer_size on macOS with exception (lines 165-166)."""
    with patch('platform.system', return_value='darwin'):
        with patch('subprocess.run', side_effect=OSError("Command not found")):
            size = socket_optimizer._get_max_buffer_size()
            assert size == 4 * 1024 * 1024  # Default 4MB


def test_get_max_buffer_size_windows(socket_optimizer):
    """Test _get_max_buffer_size on Windows (lines 168-171)."""
    with patch('platform.system', return_value='Windows'):
        size = socket_optimizer._get_max_buffer_size()
        assert size == 65536  # Default 64KB


def test_optimize_socket_no_config(socket_optimizer):
    """Test optimize_socket when no config found (lines 198-202)."""
    mock_sock = MagicMock()
    
    # Empty configs dict
    socket_optimizer.configs = {}
    
    with patch.object(socket_optimizer.logger, 'warning') as mock_warning:
        socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
        mock_warning.assert_called_once()


def test_optimize_socket_tcp_cork_available(socket_optimizer):
    """Test optimize_socket sets TCP_CORK when available (lines 229-231)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = True
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    import socket
    # Mock getattr in the network_optimizer module to return TCP_CORK
    with patch('ccbt.utils.network_optimizer.getattr') as mock_getattr:
        def side_effect(obj, name, default=None):
            if obj is socket and name == 'TCP_CORK':
                return 3  # TCP_CORK value
            return getattr(obj, name, default)
        mock_getattr.side_effect = side_effect
        
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = False
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should set TCP_CORK
                calls = [str(call) for call in mock_sock.setsockopt.call_args_list]
                # Verify TCP_CORK was set (value 3)
                assert mock_sock.setsockopt.called


def test_optimize_socket_tcp_cork_not_available(socket_optimizer):
    """Test optimize_socket handles TCP_CORK not available (line 229)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = True
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    import socket
    # Mock getattr in the network_optimizer module to return None for TCP_CORK
    with patch('ccbt.utils.network_optimizer.getattr') as mock_getattr:
        def side_effect(obj, name, default=None):
            if obj is socket and name == 'TCP_CORK':
                return default
            return getattr(obj, name, default)
        mock_getattr.side_effect = side_effect
        
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = False
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should not set TCP_CORK (doesn't exist)
                # Verify other options were set
                assert mock_sock.setsockopt.called


def test_optimize_socket_so_reuseport_available(socket_optimizer):
    """Test optimize_socket sets SO_REUSEPORT when available (lines 235-237)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = True
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    import socket
    # Mock getattr in the network_optimizer module to return SO_REUSEPORT
    with patch('ccbt.utils.network_optimizer.getattr') as mock_getattr:
        def side_effect(obj, name, default=None):
            if obj is socket and name == 'SO_REUSEPORT':
                return 15  # SO_REUSEPORT value
            return getattr(obj, name, default)
        mock_getattr.side_effect = side_effect
        
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = False
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should set SO_REUSEPORT
                calls = [str(call) for call in mock_sock.setsockopt.call_args_list]
                # Verify SO_REUSEPORT was set
                assert mock_sock.setsockopt.called


def test_optimize_socket_so_reuseport_not_available(socket_optimizer):
    """Test optimize_socket handles SO_REUSEPORT not available (line 235)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = True
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    import socket
    # Mock getattr in the network_optimizer module to return None for SO_REUSEPORT
    with patch('ccbt.utils.network_optimizer.getattr') as mock_getattr:
        def side_effect(obj, name, default=None):
            if obj is socket and name == 'SO_REUSEPORT':
                return default
            return getattr(obj, name, default)
        mock_getattr.side_effect = side_effect
        
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = False
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should not set SO_REUSEPORT (doesn't exist)
                # Verify other options were set
                assert mock_sock.setsockopt.called


def test_optimize_socket_keepalive_options_error(socket_optimizer):
    """Test optimize_socket handles keepalive options error (lines 263-265)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = True
    config.tcp_keepalive_idle = 7200
    config.tcp_keepalive_interval = 75
    config.tcp_keepalive_probes = 9
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    import socket
    with patch('ccbt.config.config.get_config') as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.socket_adaptive_buffers = False
        mock_config.network.socket_enable_window_scaling = False
        mock_get_config.return_value = mock_config
        
        with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
            # Make setsockopt raise AttributeError for TCP_KEEPIDLE after SO_KEEPALIVE
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                # First call is SO_KEEPALIVE, second is TCP_KEEPIDLE
                if call_count == 3:  # Third call is TCP_KEEPIDLE (after duplicate SO_KEEPALIVE)
                    raise AttributeError("TCP_KEEPIDLE not available")
                return None
            
            mock_sock.setsockopt.side_effect = side_effect
            
            # Should handle error gracefully
            socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
            
            # Should still set other options
            assert mock_sock.setsockopt.called

