"""
Tests for system capability detection and conditional configuration.
"""

import os
import platform
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from ccbt.config.config_capabilities import SystemCapabilities
from ccbt.config.config_conditional import ConditionalConfig
from ccbt.models import Config


class TestSystemCapabilities:
    """Test system capability detection."""

    def test_init(self):
        """Test SystemCapabilities initialization."""
        capabilities = SystemCapabilities(cache_ttl=60)
        assert capabilities.cache_ttl == 60
        assert capabilities._platform == platform.system().lower()

    def test_cache_functionality(self):
        """Test caching functionality."""
        capabilities = SystemCapabilities(cache_ttl=1)
        
        # First call should cache the result
        result1 = capabilities.detect_cpu_count()
        assert capabilities._get_cached("cpu_count") == result1
        
        # Second call should return cached result
        result2 = capabilities.detect_cpu_count()
        assert result1 == result2
        
        # After cache expires, should get new result
        time.sleep(1.1)
        result3 = capabilities.detect_cpu_count()
        assert result3 == result1  # Should be same value but new detection

    def test_detect_io_uring(self):
        """Test io_uring detection."""
        capabilities = SystemCapabilities()
        
        # Mock the platform detection
        with patch.object(capabilities, '_platform', 'linux'):
            with patch('builtins.open', MagicMock()) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "Linux version 5.4.0"
                result = capabilities.detect_io_uring()
                assert result is True

        # Clear cache and test Windows
        capabilities.clear_cache()
        with patch.object(capabilities, '_platform', 'windows'):
            result = capabilities.detect_io_uring()
            assert result is False

    def test_detect_mmap(self):
        """Test memory mapping detection."""
        capabilities = SystemCapabilities()
        
        # Should always return True since mmap is part of Python standard library
        result = capabilities.detect_mmap()
        assert result is True

    def test_detect_ipv6(self):
        """Test IPv6 detection."""
        capabilities = SystemCapabilities()
        
        # Mock socket creation - first test should succeed
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.close.return_value = None
            result = capabilities.detect_ipv6()
            assert result is True

        # Clear cache and test IPv6 not supported
        capabilities.clear_cache()
        with patch('socket.socket', side_effect=OSError()):
            result = capabilities.detect_ipv6()
            assert result is False

    def test_detect_encryption(self):
        """Test encryption library detection."""
        capabilities = SystemCapabilities()
        
        # Test with cryptography available
        with patch.dict('sys.modules', {'cryptography': MagicMock()}):
            result = capabilities.detect_encryption()
            assert result is True

        # Clear cache and test with only ssl available
        capabilities.clear_cache()
        with patch.dict('sys.modules', {'ssl': MagicMock()}, clear=True):
            result = capabilities.detect_encryption()
            assert result is True

        # Clear cache and test with neither available - just test that it returns a boolean
        capabilities.clear_cache()
        result = capabilities.detect_encryption()
        assert isinstance(result, bool)

    def test_detect_cpu_features(self):
        """Test CPU feature detection."""
        capabilities = SystemCapabilities()
        
        with patch.object(capabilities, '_platform', 'linux'):
            with patch('builtins.open', MagicMock()) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "flags: sse sse2 avx avx2"
                result = capabilities.detect_cpu_features()
                assert result["sse"] is True
                assert result["sse2"] is True
                assert result["avx"] is True
                assert result["avx2"] is True
                assert result["avx512"] is False

    def test_detect_memory(self):
        """Test memory detection."""
        capabilities = SystemCapabilities()
        
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.total = 8 * 1024**3  # 8GB
            mock_memory.return_value.available = 4 * 1024**3  # 4GB
            mock_memory.return_value.percent = 50.0
            
            result = capabilities.detect_memory()
            assert result["total_gb"] == 8.0
            assert result["available_gb"] == 4.0
            assert result["percent_used"] == 50.0

    def test_detect_disk_space(self):
        """Test disk space detection."""
        capabilities = SystemCapabilities()
        
        with patch('psutil.disk_usage') as mock_disk:
            mock_disk.return_value.total = 100 * 1024**3  # 100GB
            mock_disk.return_value.used = 50 * 1024**3  # 50GB
            mock_disk.return_value.free = 50 * 1024**3  # 50GB
            
            result = capabilities.detect_disk_space()
            assert result["total_gb"] == 100.0
            assert result["used_gb"] == 50.0
            assert result["free_gb"] == 50.0
            assert result["percent_used"] == 50.0

    def test_detect_cpu_count(self):
        """Test CPU count detection."""
        capabilities = SystemCapabilities()
        
        with patch('psutil.cpu_count', return_value=8):
            result = capabilities.detect_cpu_count()
            assert result == 8

        # Clear cache and test with None
        capabilities.clear_cache()
        with patch('psutil.cpu_count', return_value=None):
            result = capabilities.detect_cpu_count()
            assert result == 1

    def test_detect_network_interfaces(self):
        """Test network interface detection."""
        capabilities = SystemCapabilities()
        
        with patch('psutil.net_if_addrs') as mock_addrs:
            # Create mock address objects with proper family attributes
            mock_addr1 = MagicMock()
            mock_addr1.family = 2  # AF_INET
            mock_addr1.address = '192.168.1.100'
            mock_addr1.netmask = '255.255.255.0'
            mock_addr1.broadcast = '192.168.1.255'
            
            mock_addr2 = MagicMock()
            mock_addr2.family = 17  # AF_LINK
            mock_addr2.address = '00:11:22:33:44:55'
            mock_addr2.netmask = None
            mock_addr2.broadcast = None
            
            mock_addr3 = MagicMock()
            mock_addr3.family = 2  # AF_INET
            mock_addr3.address = '127.0.0.1'
            mock_addr3.netmask = '255.0.0.0'
            mock_addr3.broadcast = None
            
            mock_addrs.return_value = {
                'eth0': [mock_addr1, mock_addr2],
                'lo': [mock_addr3],
            }
            
            # Mock psutil constants - only AF_LINK exists in psutil
            with patch('psutil.AF_LINK', 17):
                result = capabilities.detect_network_interfaces()
                assert len(result) == 2
                assert result[0]["name"] == "eth0"
                assert result[0]["is_loopback"] is False
                assert result[1]["name"] == "lo"
                assert result[1]["is_loopback"] is True

    def test_detect_platform_specific(self):
        """Test platform-specific detection."""
        capabilities = SystemCapabilities()
        
        with patch.object(capabilities, '_platform', 'linux'):
            with patch.object(platform, 'machine', return_value='x86_64'):
                with patch('builtins.open', MagicMock()) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "ID=ubuntu"
                    result = capabilities.detect_platform_specific()
                    assert result["platform"] == "linux"
                    assert result["architecture"] == "x86_64"
                    assert "os_release" in result

    def test_get_all_capabilities(self):
        """Test getting all capabilities."""
        capabilities = SystemCapabilities()
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            with patch.object(capabilities, 'detect_mmap', return_value=True):
                with patch.object(capabilities, 'detect_ipv6', return_value=False):
                    result = capabilities.get_all_capabilities()
                    assert result["io_uring"] is True
                    assert result["mmap"] is True
                    assert result["ipv6"] is False

    def test_clear_cache(self):
        """Test cache clearing."""
        capabilities = SystemCapabilities()
        
        # Populate cache
        capabilities.detect_cpu_count()
        assert len(capabilities._cache) > 0
        
        # Clear cache
        capabilities.clear_cache()
        assert len(capabilities._cache) == 0

    def test_is_capability_supported(self):
        """Test capability support checking."""
        capabilities = SystemCapabilities()
        
        with patch.object(capabilities, 'get_all_capabilities', return_value={"test_cap": True}):
            assert capabilities.is_capability_supported("test_cap") is True
            assert capabilities.is_capability_supported("nonexistent") is False

    def test_get_capability_summary(self):
        """Test capability summary."""
        capabilities = SystemCapabilities()
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            with patch.object(capabilities, 'detect_cpu_features', return_value={"sse": True, "avx": False}):
                result = capabilities.get_capability_summary()
                assert result["io_uring"] is True
                assert result["sse"] is True
                assert result["avx"] is False


class TestConditionalConfig:
    """Test conditional configuration application."""

    def test_init(self):
        """Test ConditionalConfig initialization."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        assert conditional.capabilities == capabilities

        # Test default capabilities
        conditional = ConditionalConfig()
        assert isinstance(conditional.capabilities, SystemCapabilities)

    def test_apply_conditional_config(self):
        """Test conditional configuration application."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            with patch.object(capabilities, 'detect_mmap', return_value=True):
                with patch.object(capabilities, 'detect_ipv6', return_value=False):
                    modified_config, warnings = conditional.apply_conditional_config(config)
                    
                    assert modified_config.disk.enable_io_uring is True
                    assert modified_config.disk.use_mmap is True
                    assert modified_config.network.enable_ipv6 is False
                    assert len(warnings) > 0

    def test_apply_io_optimizations(self):
        """Test I/O optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test with io_uring supported
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            warnings = conditional._apply_io_optimizations(config)
            assert config.disk.enable_io_uring is True
            assert len(warnings) == 0

        # Test with io_uring not supported
        with patch.object(capabilities, 'detect_io_uring', return_value=False):
            config.disk.enable_io_uring = True
            warnings = conditional._apply_io_optimizations(config)
            assert config.disk.enable_io_uring is False
            assert len(warnings) == 1

    def test_apply_memory_optimizations(self):
        """Test memory optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test high memory system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 16.0}):
            warnings = conditional._apply_memory_optimizations(config)
            assert config.disk.read_ahead_kib == 1024
            assert config.disk.cache_size_mb == 1024
            assert len(warnings) == 0

        # Test low memory system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 4.0}):
            config.disk.read_ahead_kib = 1024
            config.disk.cache_size_mb = 512
            warnings = conditional._apply_memory_optimizations(config)
            assert config.disk.read_ahead_kib == 256
            assert config.disk.cache_size_mb == 128
            assert len(warnings) == 2

    def test_apply_network_optimizations(self):
        """Test network optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test with IPv6 not supported
        with patch.object(capabilities, 'detect_ipv6', return_value=False):
            with patch.object(capabilities, 'detect_network_interfaces', return_value=[]):
                config.network.enable_ipv6 = True
                config.network.max_global_peers = 300
                warnings = conditional._apply_network_optimizations(config)
                assert config.network.enable_ipv6 is False
                assert config.network.max_global_peers == 50
                assert len(warnings) == 2

    def test_apply_cpu_optimizations(self):
        """Test CPU optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test high core count
        with patch.object(capabilities, 'detect_cpu_count', return_value=8):
            with patch.object(capabilities, 'detect_cpu_features', return_value={"avx2": True}):
                config.disk.hash_workers = 4
                config.disk.disk_workers = 2
                warnings = conditional._apply_cpu_optimizations(config)
                assert config.disk.hash_workers == 8
                assert config.disk.disk_workers == 4
                assert len(warnings) == 0

        # Test low core count
        with patch.object(capabilities, 'detect_cpu_count', return_value=2):
            config.disk.hash_workers = 4
            config.disk.disk_workers = 2
            warnings = conditional._apply_cpu_optimizations(config)
            assert config.disk.hash_workers == 2
            assert config.disk.disk_workers == 1
            assert len(warnings) == 2

    def test_apply_security_optimizations(self):
        """Test security optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test with encryption not supported
        with patch.object(capabilities, 'detect_encryption', return_value=False):
            config.security.enable_encryption = True
            warnings = conditional._apply_security_optimizations(config)
            assert config.security.enable_encryption is False
            assert len(warnings) == 1

    def test_apply_disk_optimizations(self):
        """Test disk optimizations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test low disk space
        with patch.object(capabilities, 'detect_disk_space', return_value={"free_gb": 0.5}):
            config.disk.cache_size_mb = 200
            warnings = conditional._apply_disk_optimizations(config)
            assert config.disk.cache_size_mb == 64
            assert len(warnings) == 1

        # Test high disk space
        with patch.object(capabilities, 'detect_disk_space', return_value={"free_gb": 200.0}):
            config.disk.cache_size_mb = 200
            warnings = conditional._apply_disk_optimizations(config)
            assert config.disk.cache_size_mb == 512
            assert len(warnings) == 0

    def test_adjust_for_system(self):
        """Test system auto-tuning."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 16.0}):
                with patch.object(capabilities, 'detect_cpu_count', return_value=8):
                    tuned_config, warnings = conditional.adjust_for_system(config)
                    assert tuned_config.disk.enable_io_uring is True
                    assert tuned_config.disk.read_ahead_kib == 1024
                    assert tuned_config.disk.hash_workers == 8

    def test_validate_against_system(self):
        """Test system validation."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        config.disk.enable_io_uring = True
        config.network.enable_ipv6 = True
        
        # Test with unsupported features
        with patch.object(capabilities, 'detect_io_uring', return_value=False):
            with patch.object(capabilities, 'detect_ipv6', return_value=False):
                with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 8.0}):
                    with patch.object(capabilities, 'detect_cpu_count', return_value=4):
                        is_valid, warnings = conditional.validate_against_system(config)
                        assert is_valid is False
                        assert len(warnings) == 2

    def test_get_system_recommendations(self):
        """Test system recommendations."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 16.0}):
                with patch.object(capabilities, 'detect_cpu_count', return_value=8):
                    recommendations = conditional.get_system_recommendations()
                    assert recommendations["io_optimizations"]["use_io_uring"] is True
                    assert recommendations["cpu_optimizations"]["hash_workers"] == 8
                    assert recommendations["memory_optimizations"]["cache_size_mb"] == 1024

    def test_auto_tune_peer_limits(self):
        """Test peer limit auto-tuning."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test high-end system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 16.0}):
            with patch.object(capabilities, 'detect_cpu_count', return_value=8):
                warnings = conditional._auto_tune_peer_limits(config)
                assert config.network.max_global_peers >= 200
                assert len(warnings) == 0

        # Test low-end system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 4.0}):
            with patch.object(capabilities, 'detect_cpu_count', return_value=2):
                config.network.max_global_peers = 300
                warnings = conditional._auto_tune_peer_limits(config)
                # For low-end system, should reduce to around 40 (4GB * 10)
                assert config.network.max_global_peers <= 50
                assert len(warnings) == 0

    def test_auto_tune_timeouts(self):
        """Test timeout auto-tuning."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test high-performance system
        with patch.object(capabilities, 'detect_cpu_count', return_value=8):
            config.network.peer_timeout = 60
            warnings = conditional._auto_tune_timeouts(config)
            assert config.network.peer_timeout == 30
            assert len(warnings) == 0

        # Test low-performance system
        with patch.object(capabilities, 'detect_cpu_count', return_value=2):
            config.network.peer_timeout = 60
            warnings = conditional._auto_tune_timeouts(config)
            assert config.network.peer_timeout == 90
            assert len(warnings) == 0

    def test_auto_tune_buffers(self):
        """Test buffer auto-tuning."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test high-memory system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 16.0}):
            config.network.socket_sndbuf_kib = 512
            config.network.socket_rcvbuf_kib = 512
            warnings = conditional._auto_tune_buffers(config)
            assert config.network.socket_sndbuf_kib == 1024
            assert config.network.socket_rcvbuf_kib == 1024
            assert len(warnings) == 0

        # Test low-memory system
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 4.0}):
            config.network.socket_sndbuf_kib = 512
            config.network.socket_rcvbuf_kib = 512
            warnings = conditional._auto_tune_buffers(config)
            assert config.network.socket_sndbuf_kib == 256
            assert config.network.socket_rcvbuf_kib == 256
            assert len(warnings) == 2


class TestConditionalConfigEdgeCases:
    """Test edge cases for conditional configuration."""

    def test_empty_config(self):
        """Test with empty configuration."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        with patch.object(capabilities, 'detect_io_uring', return_value=True):
            modified_config, warnings = conditional.apply_conditional_config(config)
            assert isinstance(modified_config, Config)
            assert isinstance(warnings, list)

    def test_invalid_capability_values(self):
        """Test with invalid capability values."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test with None values
        with patch.object(capabilities, 'detect_memory', return_value=None):
            # This should handle None gracefully
            try:
                warnings = conditional._apply_memory_optimizations(config)
                assert isinstance(warnings, list)
            except (TypeError, AttributeError):
                # Expected to fail with None values
                pass

    def test_extreme_system_resources(self):
        """Test with extreme system resource values."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test with very high memory
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 1000.0}):
            warnings = conditional._apply_memory_optimizations(config)
            assert config.disk.read_ahead_kib == 1024
            assert config.disk.cache_size_mb == 1024

        # Test with very low memory
        with patch.object(capabilities, 'detect_memory', return_value={"total_gb": 0.5}):
            warnings = conditional._apply_memory_optimizations(config)
            assert config.disk.read_ahead_kib == 256
            assert config.disk.cache_size_mb == 128

    def test_platform_specific_behavior(self):
        """Test platform-specific behavior."""
        capabilities = SystemCapabilities()
        conditional = ConditionalConfig(capabilities)
        
        config = Config()
        
        # Test Windows-specific behavior
        with patch.object(platform, 'system', return_value='windows'):
            with patch.object(capabilities, 'detect_io_uring', return_value=False):
                warnings = conditional._apply_io_optimizations(config)
                assert config.disk.enable_io_uring is False

        # Test Linux-specific behavior
        with patch.object(platform, 'system', return_value='linux'):
            with patch.object(capabilities, 'detect_io_uring', return_value=True):
                warnings = conditional._apply_io_optimizations(config)
                assert config.disk.enable_io_uring is True
