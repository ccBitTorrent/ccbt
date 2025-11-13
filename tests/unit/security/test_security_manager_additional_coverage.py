"""Additional tests for security_manager.py to cover remaining gaps."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.security.security_manager import SecurityManager, ThreatType


class TestSecurityManagerAdditionalCoverage:
    """Test additional coverage gaps in SecurityManager."""

    @pytest.mark.asyncio
    async def test_report_violation_rate_limit_severity(self):
        """Test report_violation with RATE_LIMIT_EXCEEDED severity (line 256)."""
        manager = SecurityManager()
        peer_id = "test_peer"
        ip = "192.168.1.100"

        # Report rate limit violation
        await manager.report_violation(
            peer_id=peer_id,
            ip=ip,
            violation=ThreatType.RATE_LIMIT_EXCEEDED,
            description="Rate limit exceeded",
        )

        # Verify reputation was updated
        reputation = manager.get_peer_reputation(peer_id, ip)
        assert reputation is not None
        assert ThreatType.RATE_LIMIT_EXCEEDED in reputation.violations

    @pytest.mark.asyncio
    async def test_add_to_blacklist_no_event_loop(self):
        """Test add_to_blacklist with no event loop (line 304)."""
        manager = SecurityManager()
        
        # Should not raise even without event loop
        manager.add_to_blacklist("192.168.1.100", "Test reason")
        
        # Verify IP was added
        assert "192.168.1.100" in manager.get_blacklisted_ips()

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_no_event_loop(self):
        """Test remove_from_blacklist with no event loop (line 329)."""
        manager = SecurityManager()
        manager.add_to_blacklist("192.168.1.100", "Test")
        
        # Should not raise even without event loop
        manager.remove_from_blacklist("192.168.1.100")
        
        # Verify IP was removed
        assert "192.168.1.100" not in manager.get_blacklisted_ips()

    @pytest.mark.asyncio
    async def test_add_to_whitelist_no_event_loop(self):
        """Test add_to_whitelist with no event loop (line 354)."""
        manager = SecurityManager()
        
        # Should not raise even without event loop
        manager.add_to_whitelist("192.168.1.100", "Test reason")
        
        # Verify IP was added
        assert "192.168.1.100" in manager.ip_whitelist

    @pytest.mark.asyncio
    async def test_remove_from_whitelist_no_event_loop(self):
        """Test remove_from_whitelist with no event loop (line 378)."""
        manager = SecurityManager()
        manager.add_to_whitelist("192.168.1.100", "Test")
        
        # Should not raise even without event loop
        manager.remove_from_whitelist("192.168.1.100")
        
        # Verify IP was removed
        assert "192.168.1.100" not in manager.ip_whitelist

