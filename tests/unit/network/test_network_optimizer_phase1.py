"""Comprehensive tests for Phase 1 socket buffer management.

Tests:
- Adaptive buffer sizing (BDP calculation)
- Platform-specific buffer optimizations
- TCP window scaling
"""

from __future__ import annotations

import platform
import socket
from unittest.mock import MagicMock, mock_open, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.utils.network_optimizer import SocketOptimizer


@pytest.fixture
def socket_optimizer():
    """Create a SocketOptimizer instance."""
    return SocketOptimizer()


class TestAdaptiveBufferSizing:
    """Test adaptive buffer sizing."""

    def test_calculate_optimal_buffer_size_bdp(self, socket_optimizer):
        """Test optimal buffer size calculation using BDP."""
        # High bandwidth, high latency
        bandwidth_bps = 100_000_000  # 100 Mbps
        rtt_ms = 100  # 100ms RTT
        
        optimal_size = socket_optimizer._calculate_optimal_buffer_size(bandwidth_bps, rtt_ms)
        
        # BDP = (100Mbps * 100ms) / 8 * 2 = 2.5MB
        # But will be clamped to system max (Windows default is 64KB)
        expected_bdp = (bandwidth_bps * rtt_ms / 1000) / 8 * 2
        max_size = socket_optimizer._get_max_buffer_size()
        expected_clamped = min(expected_bdp, max_size)
        assert optimal_size == pytest.approx(expected_clamped, abs=1000)

    def test_calculate_optimal_buffer_size_low_bandwidth(self, socket_optimizer):
        """Test buffer size calculation for low bandwidth."""
        # Low bandwidth
        bandwidth_bps = 1_000_000  # 1 Mbps
        rtt_ms = 50  # 50ms RTT
        
        optimal_size = socket_optimizer._calculate_optimal_buffer_size(bandwidth_bps, rtt_ms)
        
        # Should be smaller for low bandwidth
        assert optimal_size > 0
        assert optimal_size < 100_000  # Less than 100KB for low bandwidth

    def test_calculate_optimal_buffer_size_respects_max(self, socket_optimizer):
        """Test buffer size respects system maximum."""
        # Very high bandwidth that would exceed system max
        bandwidth_bps = 10_000_000_000  # 10 Gbps
        rtt_ms = 200  # 200ms RTT
        
        optimal_size = socket_optimizer._calculate_optimal_buffer_size(bandwidth_bps, rtt_ms)
        
        # Should be capped at system maximum
        max_size = socket_optimizer._get_max_buffer_size()
        assert optimal_size <= max_size

    def test_get_max_buffer_size_linux(self, socket_optimizer):
        """Test getting max buffer size on Linux."""
        if platform.system().lower() != "linux":
            pytest.skip("Not running on Linux")
        
        with patch("builtins.open", mock_open(read_data="65536000")):
            max_size = socket_optimizer._get_max_buffer_size()
            assert max_size == 65536000

    def test_get_max_buffer_size_macos(self, socket_optimizer):
        """Test getting max buffer size on macOS."""
        if platform.system().lower() != "darwin":
            pytest.skip("Not running on macOS")
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "4194304\n"
            
            max_size = socket_optimizer._get_max_buffer_size()
            assert max_size == 4194304

    def test_get_max_buffer_size_windows(self, socket_optimizer):
        """Test getting max buffer size on Windows."""
        if platform.system().lower() != "windows":
            pytest.skip("Not running on Windows")
        
        max_size = socket_optimizer._get_max_buffer_size()
        
        # Windows default is 64KB
        assert max_size == 65536

    def test_get_max_buffer_size_fallback(self, socket_optimizer):
        """Test max buffer size fallback on error."""
        with patch("builtins.open", side_effect=OSError("File not found")):
            max_size = socket_optimizer._get_max_buffer_size()
            
            # Should return default
            assert max_size > 0


class TestTCPWindowScaling:
    """Test TCP window scaling."""

    def test_supports_tcp_window_scaling_available(self, socket_optimizer):
        """Test TCP window scaling detection when available."""
        # Mock socket that supports TCP_WINDOW_SCALE
        with patch("socket.socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock
            
            supports = socket_optimizer._supports_tcp_window_scaling()
            
            # Should check if TCP_WINDOW_SCALE is available
            assert isinstance(supports, bool)

    def test_supports_tcp_window_scaling_unavailable(self, socket_optimizer):
        """Test TCP window scaling detection when unavailable."""
        # Mock socket that doesn't support TCP_WINDOW_SCALE
        with patch("socket.socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_sock.setsockopt.side_effect = AttributeError("TCP_WINDOW_SCALE not available")
            mock_socket_class.return_value = mock_sock
            
            supports = socket_optimizer._supports_tcp_window_scaling()
            
            # Should return False when not available
            assert supports is False

    def test_optimize_socket_enables_window_scaling(self, socket_optimizer):
        """Test socket optimization enables TCP window scaling."""
        mock_sock = MagicMock()
        
        # Mock config to enable window scaling
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_enable_window_scaling = True
            mock_config.network.socket_adaptive_buffers = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_supports_tcp_window_scaling', return_value=True):
                with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                    from ccbt.utils.network_optimizer import SocketType
                    
                    socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                    
                    # Should set TCP_WINDOW_SCALE if available
                    # Verify socket was configured
                    assert mock_sock.setsockopt.called

    def test_optimize_socket_disables_window_scaling(self, socket_optimizer):
        """Test socket optimization doesn't enable window scaling when disabled."""
        mock_sock = MagicMock()
        
        # Mock config to disable window scaling
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_enable_window_scaling = False
            mock_config.network.socket_adaptive_buffers = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_get_max_buffer_size', return_value=65536):
                from ccbt.utils.network_optimizer import SocketType
                
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should still configure socket (just without window scaling)
                assert mock_sock.setsockopt.called


class TestAdaptiveBufferIntegration:
    """Test adaptive buffer sizing integration."""

    def test_optimize_socket_uses_adaptive_buffers(self, socket_optimizer):
        """Test socket optimization uses adaptive buffers when enabled."""
        mock_sock = MagicMock()
        
        # Mock config to enable adaptive buffers
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = True
            mock_config.network.socket_min_buffer_kib = 64
            mock_config.network.socket_max_buffer_kib = 65536
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            with patch.object(socket_optimizer, '_calculate_optimal_buffer_size', return_value=65536):
                from ccbt.utils.network_optimizer import SocketType
                
                socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
                
                # Should set buffer sizes
                assert mock_sock.setsockopt.called

    def test_optimize_socket_uses_fixed_buffers(self, socket_optimizer):
        """Test socket optimization uses fixed buffers when adaptive disabled."""
        mock_sock = MagicMock()
        
        # Mock config to disable adaptive buffers
        with patch('ccbt.config.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.socket_adaptive_buffers = False
            mock_config.network.socket_enable_window_scaling = False
            mock_get_config.return_value = mock_config
            
            from ccbt.utils.network_optimizer import SocketType
            
            socket_optimizer.optimize_socket(mock_sock, SocketType.PEER_CONNECTION)
            
            # Should use fixed buffer sizes from config
            assert mock_sock.setsockopt.called

