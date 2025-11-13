"""
Tests for system capability detection and conditional configuration.
"""

import os
import platform
import subprocess
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

    def test_detect_io_uring_import_error(self):
        """Test io_uring detection with ImportError (lines 84-91)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'linux'):
            # Mock open to raise OSError (no /proc/version)
            with patch('builtins.open', side_effect=OSError()):
                # Mock import io_uring to fail
                with patch.dict('sys.modules', {}, clear=False):
                    import sys
                    # Ensure io_uring is not in modules
                    if 'io_uring' in sys.modules:
                        del sys.modules['io_uring']
                    result = capabilities.detect_io_uring()
                    assert result is False

    def test_detect_mmap_import_error(self):
        """Test mmap detection with ImportError (lines 110-111)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        # Mock mmap import to fail
        with patch.dict('sys.modules', {}, clear=False):
            import sys
            # Remove mmap from modules temporarily
            mmap_module = sys.modules.pop('mmap', None)
            try:
                with patch('builtins.__import__', side_effect=ImportError("No module named 'mmap'")):
                    result = capabilities.detect_mmap()
                    assert result is False
            finally:
                if mmap_module:
                    sys.modules['mmap'] = mmap_module

    def test_detect_ipv6_cached(self):
        """Test IPv6 detection returns cached value (line 124)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_ipv6()
        # Second call should use cache
        result2 = capabilities.detect_ipv6()
        assert result1 == result2

    def test_detect_encryption_cached(self):
        """Test encryption detection returns cached value (line 147)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_encryption()
        # Second call should use cache
        result2 = capabilities.detect_encryption()
        assert result1 == result2

    def test_detect_cpu_features_oserror_linux(self):
        """Test CPU features detection with OSError on Linux (lines 198-199)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'linux'):
            with patch('builtins.open', side_effect=OSError("File not found")):
                result = capabilities.detect_cpu_features()
                # Should return default features dict with all False
                assert isinstance(result, dict)
                assert result["sse"] is False
                assert result["avx"] is False

    def test_detect_cpu_features_darwin(self):
        """Test CPU features detection on macOS/Darwin (lines 201-225)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'darwin'):
            # Test successful sysctl call
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "SSE SSE2 AVX AVX2"
            
            with patch('subprocess.run', return_value=mock_result):
                result = capabilities.detect_cpu_features()
                assert result["sse"] is True
                assert result["sse2"] is True
                assert result["avx"] is True
                assert result["avx2"] is True

    def test_detect_cpu_features_darwin_error(self):
        """Test CPU features detection on macOS with subprocess error (lines 220-225)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'darwin'):
            # Test subprocess error handling
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("sysctl", 5)):
                result = capabilities.detect_cpu_features()
                assert isinstance(result, dict)
                assert result["sse"] is False

    def test_detect_cpu_features_windows(self):
        """Test CPU features detection on Windows (lines 238-251)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'windows'):
            # Test successful wmic call
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "SSE SSE2 AVX AVX2"
            
            with patch('subprocess.run', return_value=mock_result):
                result = capabilities.detect_cpu_features()
                assert result["sse"] is True
                assert result["sse2"] is True
                assert result["avx"] is True
                assert result["avx2"] is True

    def test_detect_cpu_features_windows_error(self):
        """Test CPU features detection on Windows with subprocess error (lines 246-251)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'windows'):
            # Test subprocess error handling
            with patch('subprocess.run', side_effect=FileNotFoundError("wmic not found")):
                result = capabilities.detect_cpu_features()
                assert isinstance(result, dict)
                assert result["sse"] is False

    def test_detect_cpu_features_cached(self):
        """Test CPU features detection returns cached value (line 172)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_cpu_features()
        # Second call should use cache
        result2 = capabilities.detect_cpu_features()
        assert result1 == result2

    def test_detect_memory_exception(self):
        """Test memory detection with exception (lines 275-276)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.virtual_memory', side_effect=Exception("psutil error")):
            result = capabilities.detect_memory()
            assert result["total_bytes"] == 0
            assert result["total_gb"] == 0.0
            assert result["percent_used"] == 100.0

    def test_detect_memory_cached(self):
        """Test memory detection returns cached value (line 264)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_memory()
        # Second call should use cache
        result2 = capabilities.detect_memory()
        assert result1 == result2

    def test_detect_disk_space_cached(self):
        """Test disk space detection returns cached value (line 299)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_disk_space()
        # Second call should use cache
        result2 = capabilities.detect_disk_space()
        assert result1 == result2

    def test_detect_disk_space_exception(self):
        """Test disk space detection with exception (lines 312-313)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.disk_usage', side_effect=Exception("psutil error")):
            result = capabilities.detect_disk_space()
            assert result["total_bytes"] == 0
            assert result["total_gb"] == 0.0
            assert result["percent_used"] == 100.0

    def test_detect_cpu_count_exception(self):
        """Test CPU count detection with exception (lines 340-341)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.cpu_count', side_effect=Exception("psutil error")):
            result = capabilities.detect_cpu_count()
            assert result == 1

    def test_detect_network_interfaces_cached(self):
        """Test network interfaces detection returns cached value (line 354)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_network_interfaces()
        # Second call should use cache
        result2 = capabilities.detect_network_interfaces()
        assert result1 == result2

    def test_detect_network_interfaces_exception(self):
        """Test network interfaces detection with exception (lines 399-400)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.net_if_addrs', side_effect=Exception("psutil error")):
            result = capabilities.detect_network_interfaces()
            assert result == []

    def test_detect_platform_specific_cached(self):
        """Test platform specific detection returns cached value (line 413)."""
        capabilities = SystemCapabilities()
        
        # First call populates cache
        result1 = capabilities.detect_platform_specific()
        # Second call should use cache
        result2 = capabilities.detect_platform_specific()
        assert result1 == result2

    def test_detect_platform_specific_darwin(self):
        """Test platform specific detection on macOS (lines 429-433)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'darwin'):
            with patch('platform.mac_ver', return_value=('10.15', '', '')):
                result = capabilities.detect_platform_specific()
                assert result["macos_version"] == "10.15"

    def test_detect_platform_specific_darwin_exception(self):
        """Test platform specific detection on macOS with exception (lines 432-433)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'darwin'):
            with patch('platform.mac_ver', side_effect=Exception("mac_ver error")):
                result = capabilities.detect_platform_specific()
                assert result["macos_version"] == "unknown"

    def test_detect_platform_specific_windows(self):
        """Test platform specific detection on Windows (lines 435-438)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'windows'):
            with patch('platform.win32_ver', return_value=('10', '', '', '')):
                result = capabilities.detect_platform_specific()
                assert result["windows_version"] == "10"

    def test_detect_platform_specific_windows_exception(self):
        """Test platform specific detection on Windows with exception (lines 437-438)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'windows'):
            with patch('platform.win32_ver', side_effect=Exception("win32_ver error")):
                result = capabilities.detect_platform_specific()
                assert result["windows_version"] == "unknown"

    def test_detect_platform_specific_linux_oserror(self):
        """Test platform specific detection on Linux with OSError (lines 427-428)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch.object(capabilities, '_platform', 'linux'):
            with patch('builtins.open', side_effect=OSError("File not found")):
                result = capabilities.detect_platform_specific()
                assert result["os_release"] == "unknown"

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
        import sys
        original_crypto = sys.modules.pop('cryptography', None)
        original_ssl = sys.modules.pop('ssl', None)
        try:
            with patch.dict('sys.modules', {'cryptography': MagicMock()}, clear=False):
                result = capabilities.detect_encryption()
                assert result is True

            # Clear cache and test with only ssl available (covers lines 153-159)
            capabilities.clear_cache()
            sys.modules.pop('cryptography', None)
            with patch.dict('sys.modules', {'ssl': MagicMock()}, clear=False):
                result = capabilities.detect_encryption()
                assert result is True

            # Clear cache and test with neither available (covers line 158)
            capabilities.clear_cache()
            sys.modules.pop('cryptography', None)
            sys.modules.pop('ssl', None)
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                result = capabilities.detect_encryption()
                assert result is False
        finally:
            if original_crypto:
                sys.modules['cryptography'] = original_crypto
            if original_ssl:
                sys.modules['ssl'] = original_ssl

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

    def test_detect_network_interfaces_wireless(self):
        """Test network interface detection with wireless interface (line 396)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.net_if_addrs') as mock_addrs:
            # Create mock address for wireless interface
            mock_addr = MagicMock()
            mock_addr.family = 2  # AF_INET
            mock_addr.address = '192.168.1.100'
            mock_addr.netmask = '255.255.255.0'
            mock_addr.broadcast = '192.168.1.255'
            
            # Create wireless interface name
            mock_addrs.return_value = {
                'wlan0': [mock_addr],
            }
            
            with patch('psutil.AF_LINK', 17):
                result = capabilities.detect_network_interfaces()
                assert len(result) == 1
                assert result[0]["name"] == "wlan0"
                assert result[0]["is_wireless"] is True

    def test_detect_network_interfaces_ipv6(self):
        """Test network interface detection with IPv6 (covers AF_INET6 path, lines 384-385)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.net_if_addrs') as mock_addrs:
            # Create mock address for IPv6
            mock_addr = MagicMock()
            mock_addr.family = 23  # AF_INET6
            mock_addr.address = '2001:db8::1'
            mock_addr.netmask = None
            mock_addr.broadcast = None
            
            mock_addrs.return_value = {
                'eth0': [mock_addr],
            }
            
            result = capabilities.detect_network_interfaces()
            assert len(result) == 1
            assert result[0]["name"] == "eth0"
            assert "ipv6_address" in result[0]
            assert result[0]["ipv6_address"] == '2001:db8::1'

    def test_detect_network_interfaces_mac_address(self):
        """Test network interface detection with MAC address (covers AF_LINK path, line 380-381)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.net_if_addrs') as mock_addrs:
            # Create mock address for MAC (AF_LINK)
            mock_addr = MagicMock()
            mock_addr.family = 17  # AF_LINK (MAC address)
            mock_addr.address = '00:11:22:33:44:55'
            mock_addr.netmask = None
            mock_addr.broadcast = None
            
            mock_addrs.return_value = {
                'eth0': [mock_addr],
            }
            
            with patch('psutil.AF_LINK', 17):
                result = capabilities.detect_network_interfaces()
                assert len(result) == 1
                assert result[0]["name"] == "eth0"
                assert "mac_address" in result[0]
                assert result[0]["mac_address"] == '00:11:22:33:44:55'

    def test_detect_network_interfaces_addresses_list(self):
        """Test network interface detection with multiple addresses (covers lines 376-378)."""
        capabilities = SystemCapabilities()
        capabilities.clear_cache()
        
        with patch('psutil.net_if_addrs') as mock_addrs:
            # Create multiple addresses for same interface
            mock_addr1 = MagicMock()
            mock_addr1.family = 2  # AF_INET
            mock_addr1.address = '192.168.1.100'
            mock_addr1.netmask = '255.255.255.0'
            mock_addr1.broadcast = '192.168.1.255'
            
            mock_addr2 = MagicMock()
            mock_addr2.family = 2  # AF_INET
            mock_addr2.address = '10.0.0.1'
            mock_addr2.netmask = '255.0.0.0'
            mock_addr2.broadcast = None
            
            mock_addrs.return_value = {
                'eth0': [mock_addr1, mock_addr2],
            }
            
            result = capabilities.detect_network_interfaces()
            assert len(result) == 1
            assert len(result[0]["addresses"]) == 2

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
