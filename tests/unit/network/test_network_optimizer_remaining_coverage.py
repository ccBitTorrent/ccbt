"""Additional tests to cover remaining network optimizer lines."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.utils.network_optimizer import SocketOptimizer, SocketType


@pytest.fixture
def socket_optimizer():
    """Create a test socket optimizer."""
    return SocketOptimizer()


def test_optimize_socket_rcvtimeo(socket_optimizer):
    """Test optimize_socket sets receive timeout (line 280-281)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 5.0  # Non-zero timeout
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    with patch('ccbt.config.config.get_config') as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.socket_adaptive_buffers = False
        mock_config.network.socket_enable_window_scaling = False
        mock_get_config.return_value = mock_config
        
        with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
            socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
            
            # Should set timeout
            mock_sock.settimeout.assert_called_once_with(5.0)


def test_optimize_socket_oserror_handling(socket_optimizer):
    """Test optimize_socket handles OSError (lines 285-288)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    with patch('ccbt.config.config.get_config') as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.socket_adaptive_buffers = False
        mock_config.network.socket_enable_window_scaling = False
        mock_get_config.return_value = mock_config
        
        with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
            # Make setsockopt raise OSError
            mock_sock.setsockopt.side_effect = OSError("Permission denied")
            
            from ccbt.utils.network_optimizer import NetworkError
            with pytest.raises(NetworkError):
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)


def test_optimize_socket_window_scaling_oserror(socket_optimizer):
    """Test optimize_socket handles OSError when setting window scaling (lines 275-277)."""
    mock_sock = MagicMock()
    config = MagicMock()
    config.tcp_cork = False
    config.tcp_nodelay = False
    config.so_reuseport = False
    config.so_reuseaddr = False
    config.so_keepalive = False
    config.so_rcvbuf = 65536
    config.so_sndbuf = 65536
    config.so_rcvtimeo = 0
    config.so_sndtimeo = 0
    socket_optimizer.configs[SocketType.PEER_CONNECTION] = config
    
    with patch('ccbt.config.config.get_config') as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.socket_adaptive_buffers = False
        mock_config.network.socket_enable_window_scaling = True
        mock_get_config.return_value = mock_config
        
        with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
            with patch.object(socket_optimizer, '_supports_tcp_window_scaling', return_value=True):
                # Make setsockopt raise OSError for TCP_WINDOW_SCALE
                import socket
                call_count = 0
                def side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    # Check if it's TCP_WINDOW_SCALE call
                    if len(args) >= 3 and args[0] == socket.IPPROTO_TCP:
                        try:
                            if args[1] == socket.TCP_WINDOW_SCALE:
                                raise OSError("TCP_WINDOW_SCALE not supported")
                        except AttributeError:
                            pass
                    return None
                
                mock_sock.setsockopt.side_effect = side_effect
                
                # Should handle error gracefully
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should still set other options
                assert mock_sock.setsockopt.called

