"""Tests for Security Manager.
"""

import pytest

from ccbt.models import PeerInfo
from ccbt.security.security_manager import SecurityManager, ThreatType


class TestSecurityManager:
    """Tests for SecurityManager class."""

    @pytest.fixture
    def security_manager(self):
        """Create security manager instance."""
        return SecurityManager()

    @pytest.fixture
    def sample_peer_info(self):
        """Create sample peer info."""
        return PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"test_peer_id")

    def test_security_manager_creation(self, security_manager):
        """Test security manager creation."""
        assert len(security_manager.peer_reputations) == 0
        assert len(security_manager.ip_blacklist) == 0
        assert len(security_manager.ip_whitelist) == 0
        assert len(security_manager.security_events) == 0
        assert security_manager.max_connections_per_minute == 10
        assert security_manager.max_messages_per_minute == 100
        assert security_manager.max_bytes_per_minute == 1024 * 1024

    @pytest.mark.asyncio
    async def test_validate_peer_success(self, security_manager, sample_peer_info):
        """Test successful peer validation."""
        is_valid, reason = await security_manager.validate_peer(sample_peer_info)

        assert is_valid
        assert reason == "Valid peer"
        assert security_manager.stats["total_connections"] == 1

    @pytest.mark.asyncio
    async def test_validate_peer_blacklisted(self, security_manager, sample_peer_info):
        """Test validation of blacklisted peer."""
        # Add peer to blacklist
        security_manager.add_to_blacklist(sample_peer_info.ip, "Test blacklist")

        is_valid, reason = await security_manager.validate_peer(sample_peer_info)

        assert not is_valid
        assert reason == "IP is blacklisted"
        assert (
            security_manager.stats["blocked_connections"] == 0
        )  # Not counted as blocked yet

    @pytest.mark.asyncio
    async def test_validate_peer_rate_limited(self, security_manager, sample_peer_info):
        """Test validation of rate-limited peer."""
        # Simulate rate limiting by adding many connections
        for _ in range(15):  # Exceed max_connections_per_minute
            security_manager._update_connection_rate(sample_peer_info.ip)

        is_valid, reason = await security_manager.validate_peer(sample_peer_info)

        assert not is_valid
        assert reason == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_record_peer_activity(self, security_manager, sample_peer_info):
        """Test recording peer activity."""
        peer_id = sample_peer_info.peer_id.hex() if sample_peer_info.peer_id else ""

        # Record successful activity
        await security_manager.record_peer_activity(
            peer_id,
            sample_peer_info.ip,
            True,
            1000,
            2000,
        )

        # Check reputation was created
        reputation = security_manager.get_peer_reputation(peer_id, sample_peer_info.ip)
        assert reputation is not None
        assert reputation.successful_connections == 1
        assert reputation.bytes_sent == 1000
        assert reputation.bytes_received == 2000

    @pytest.mark.asyncio
    async def test_report_violation(self, security_manager, sample_peer_info):
        """Test reporting security violation."""
        peer_id = sample_peer_info.peer_id.hex() if sample_peer_info.peer_id else ""

        # Report violation
        await security_manager.report_violation(
            peer_id,
            sample_peer_info.ip,
            ThreatType.MALICIOUS_PEER,
            "Test violation",
        )

        # Check reputation was updated
        reputation = security_manager.get_peer_reputation(peer_id, sample_peer_info.ip)
        assert reputation is not None
        assert len(reputation.violations) == 1
        assert reputation.violations[0] == ThreatType.MALICIOUS_PEER
        assert reputation.is_blacklisted

    def test_add_to_blacklist(self, security_manager):
        """Test adding IP to blacklist."""
        ip = "192.168.1.100"

        security_manager.add_to_blacklist(ip, "Test reason")

        assert ip in security_manager.ip_blacklist
        assert security_manager.stats["blacklisted_peers"] == 1

    def test_remove_from_blacklist(self, security_manager):
        """Test removing IP from blacklist."""
        ip = "192.168.1.100"

        # Add to blacklist first
        security_manager.add_to_blacklist(ip, "Test reason")
        assert ip in security_manager.ip_blacklist

        # Remove from blacklist
        security_manager.remove_from_blacklist(ip)
        assert ip not in security_manager.ip_blacklist

    def test_add_to_whitelist(self, security_manager):
        """Test adding IP to whitelist."""
        ip = "192.168.1.100"

        security_manager.add_to_whitelist(ip, "Test reason")

        assert ip in security_manager.ip_whitelist
        assert security_manager.stats["whitelisted_peers"] == 1

    def test_remove_from_whitelist(self, security_manager):
        """Test removing IP from whitelist."""
        ip = "192.168.1.100"

        # Add to whitelist first
        security_manager.add_to_whitelist(ip, "Test reason")
        assert ip in security_manager.ip_whitelist

        # Remove from whitelist
        security_manager.remove_from_whitelist(ip)
        assert ip not in security_manager.ip_whitelist

    def test_get_peer_reputation(self, security_manager, sample_peer_info):
        """Test getting peer reputation."""
        peer_id = sample_peer_info.peer_id.hex() if sample_peer_info.peer_id else ""

        # No reputation yet
        reputation = security_manager.get_peer_reputation(peer_id, sample_peer_info.ip)
        assert reputation is None

        # Create reputation by recording activity
        security_manager._get_peer_reputation(peer_id, sample_peer_info.ip)
        reputation = security_manager.get_peer_reputation(peer_id, sample_peer_info.ip)
        assert reputation is not None
        assert reputation.peer_id == peer_id
        assert reputation.ip == sample_peer_info.ip

    def test_get_blacklisted_ips(self, security_manager):
        """Test getting blacklisted IPs."""
        # No blacklisted IPs initially
        blacklisted = security_manager.get_blacklisted_ips()
        assert len(blacklisted) == 0

        # Add some IPs to blacklist
        security_manager.add_to_blacklist("192.168.1.1", "Test 1")
        security_manager.add_to_blacklist("192.168.1.2", "Test 2")

        blacklisted = security_manager.get_blacklisted_ips()
        assert len(blacklisted) == 2
        assert "192.168.1.1" in blacklisted
        assert "192.168.1.2" in blacklisted

    def test_get_whitelisted_ips(self, security_manager):
        """Test getting whitelisted IPs."""
        # No whitelisted IPs initially
        whitelisted = security_manager.get_whitelisted_ips()
        assert len(whitelisted) == 0

        # Add some IPs to whitelist
        security_manager.add_to_whitelist("192.168.1.1", "Test 1")
        security_manager.add_to_whitelist("192.168.1.2", "Test 2")

        whitelisted = security_manager.get_whitelisted_ips()
        assert len(whitelisted) == 2
        assert "192.168.1.1" in whitelisted
        assert "192.168.1.2" in whitelisted

    def test_is_ip_blacklisted(self, security_manager):
        """Test checking if IP is blacklisted."""
        ip = "192.168.1.100"

        # Not blacklisted initially
        assert not security_manager.is_ip_blacklisted(ip)

        # Add to blacklist
        security_manager.add_to_blacklist(ip, "Test reason")
        assert security_manager.is_ip_blacklisted(ip)

    def test_is_ip_whitelisted(self, security_manager):
        """Test checking if IP is whitelisted."""
        ip = "192.168.1.100"

        # Not whitelisted initially
        assert not security_manager.is_ip_whitelisted(ip)

        # Add to whitelist
        security_manager.add_to_whitelist(ip, "Test reason")
        assert security_manager.is_ip_whitelisted(ip)

    def test_get_security_events(self, security_manager):
        """Test getting security events."""
        # No events initially
        events = security_manager.get_security_events()
        assert len(events) == 0

        # Add some events (this would normally happen through validation)
        # For now, just test the method
        events = security_manager.get_security_events(limit=10)
        assert len(events) == 0

    def test_get_security_statistics(self, security_manager):
        """Test getting security statistics."""
        stats = security_manager.get_security_statistics()

        assert "total_connections" in stats
        assert "blocked_connections" in stats
        assert "security_events" in stats
        assert "blacklisted_peers" in stats
        assert "whitelisted_peers" in stats
        assert "blacklist_size" in stats
        assert "whitelist_size" in stats
        assert "reputation_tracking" in stats

        # Initial values
        assert stats["total_connections"] == 0
        assert stats["blocked_connections"] == 0
        assert stats["security_events"] == 0
        assert stats["blacklist_size"] == 0
        assert stats["whitelist_size"] == 0
        assert stats["reputation_tracking"] == 0

    def test_cleanup_old_data(self, security_manager):
        """Test cleaning up old data."""
        # This is a basic test - in a real scenario, we'd need to create
        # old data and verify it gets cleaned up

        # Test that cleanup doesn't crash
        security_manager.cleanup_old_data(max_age_seconds=1)

        # Verify basic structure is maintained
        assert len(security_manager.peer_reputations) == 0
        assert len(security_manager.ip_blacklist) == 0
        assert len(security_manager.ip_whitelist) == 0
