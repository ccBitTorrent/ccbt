"""Integration tests for IP filter with SecurityManager."""

import pytest

from ccbt.models import Config, IPFilterConfig, PeerInfo, SecurityConfig
from ccbt.security.ip_filter import FilterMode
from ccbt.security.security_manager import SecurityManager


class TestIPFilterIntegration:
    """Integration tests for IP filter with SecurityManager."""

    @pytest.fixture
    def security_manager(self):
        """Create security manager instance."""
        return SecurityManager()

    @pytest.fixture
    def config_with_ip_filter(self):
        """Create config with IP filter enabled."""
        ip_filter_config = IPFilterConfig(
            enable_ip_filter=True,
            filter_mode="block",
            filter_files=[],
            filter_urls=[],
        )
        security_config = SecurityConfig(ip_filter=ip_filter_config)
        config = Config()
        config.security = security_config
        return config

    @pytest.mark.asyncio
    async def test_security_manager_load_ip_filter(self, security_manager, config_with_ip_filter):
        """Test loading IP filter in SecurityManager."""
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        assert security_manager.ip_filter is not None
        assert security_manager.ip_filter.enabled is True
        assert security_manager.ip_filter.mode == FilterMode.BLOCK

    @pytest.mark.asyncio
    async def test_validate_peer_with_ip_filter(self, security_manager, config_with_ip_filter):
        """Test peer validation with IP filter."""
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        # Add a blocked IP
        security_manager.ip_filter.add_rule("192.168.1.0/24")
        
        # Test blocked peer
        blocked_peer = PeerInfo(ip="192.168.1.10", port=6881)
        is_valid, reason = await security_manager.validate_peer(blocked_peer)
        assert is_valid is False
        assert "filter" in reason.lower()

    @pytest.mark.asyncio
    async def test_validate_peer_allowed_by_filter(self, security_manager, config_with_ip_filter):
        """Test peer validation when IP is allowed by filter."""
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        # Add a blocked range, but test an IP outside it
        security_manager.ip_filter.add_rule("192.168.1.0/24")
        
        # Test allowed peer
        allowed_peer = PeerInfo(ip="10.0.0.1", port=6881)
        is_valid, reason = await security_manager.validate_peer(allowed_peer)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_peer_filter_disabled(self, security_manager, config_with_ip_filter):
        """Test peer validation when filter is disabled."""
        config_with_ip_filter.security.ip_filter.enable_ip_filter = False
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        # Add a blocked IP, but filter is disabled
        security_manager.ip_filter.add_rule("192.168.1.0/24")
        
        blocked_peer = PeerInfo(ip="192.168.1.10", port=6881)
        is_valid, reason = await security_manager.validate_peer(blocked_peer)
        # Should be valid because filter is disabled
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_add_to_blacklist_syncs_with_filter(self, security_manager, config_with_ip_filter):
        """Test that adding to blacklist also adds to IP filter."""
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        # Add IP to blacklist
        security_manager.add_to_blacklist("192.168.1.100", "Test")
        
        # Check that it's in the filter
        assert security_manager.ip_filter.is_blocked("192.168.1.100") is True

    @pytest.mark.asyncio
    async def test_ip_filter_with_blacklist_interaction(self, security_manager, config_with_ip_filter):
        """Test interaction between IP filter and blacklist."""
        await security_manager.load_ip_filter(config_with_ip_filter)
        
        # Add IP to blacklist
        security_manager.add_to_blacklist("192.168.1.50", "Test")
        
        # Add different IP to filter
        security_manager.ip_filter.add_rule("10.0.0.0/8")
        
        # Both should be blocked
        peer1 = PeerInfo(ip="192.168.1.50", port=6881)
        peer2 = PeerInfo(ip="10.0.0.1", port=6881)
        
        is_valid1, _ = await security_manager.validate_peer(peer1)
        is_valid2, _ = await security_manager.validate_peer(peer2)
        
        assert is_valid1 is False  # Blocked by blacklist
        assert is_valid2 is False  # Blocked by filter

    @pytest.mark.asyncio
    async def test_ip_filter_allow_mode(self, security_manager):
        """Test IP filter in ALLOW mode."""
        ip_filter_config = IPFilterConfig(
            enable_ip_filter=True,
            filter_mode="allow",
            filter_files=[],
            filter_urls=[],
        )
        security_config = SecurityConfig(ip_filter=ip_filter_config)
        config = Config()
        config.security = security_config
        
        await security_manager.load_ip_filter(config)
        
        # Add allowed range
        security_manager.ip_filter.add_rule("192.168.1.0/24")
        
        # IP in range should be allowed
        allowed_peer = PeerInfo(ip="192.168.1.10", port=6881)
        is_valid, _ = await security_manager.validate_peer(allowed_peer)
        assert is_valid is True
        
        # IP outside range should be blocked
        blocked_peer = PeerInfo(ip="10.0.0.1", port=6881)
        is_valid, _ = await security_manager.validate_peer(blocked_peer)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_load_ip_filter_with_files(self, security_manager, tmp_path):
        """Test loading IP filter with file paths."""
        # Create a filter file
        filter_file = tmp_path / "filter.txt"
        filter_file.write_text("192.168.1.0/24\n10.0.0.0/8\n")
        
        ip_filter_config = IPFilterConfig(
            enable_ip_filter=True,
            filter_mode="block",
            filter_files=[str(filter_file)],
            filter_urls=[],
        )
        security_config = SecurityConfig(ip_filter=ip_filter_config)
        config = Config()
        config.security = security_config
        
        await security_manager.load_ip_filter(config)
        
        # Check that rules were loaded
        assert len(security_manager.ip_filter.rules) == 2
        assert security_manager.ip_filter.is_blocked("192.168.1.10") is True

