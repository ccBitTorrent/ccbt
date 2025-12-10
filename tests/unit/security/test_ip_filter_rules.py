"""Unit tests for IP filter rule management."""

import pytest

from ccbt.security.ip_filter import FilterMode, IPFilter


class TestIPFilterRules:
    """Tests for IP filter rule management."""

    @pytest.fixture
    def ip_filter(self):
        """Create IP filter instance."""
        return IPFilter(enabled=True, mode=FilterMode.BLOCK)

    def test_add_rule_cidr(self, ip_filter):
        """Test adding CIDR rule."""
        result = ip_filter.add_rule("192.168.1.0/24")
        assert result is True
        assert len(ip_filter.rules) == 1
        assert len(ip_filter.ipv4_ranges) == 1

    def test_add_rule_range(self, ip_filter):
        """Test adding range rule."""
        result = ip_filter.add_rule("192.168.0.0-192.168.255.255")
        assert result is True
        assert len(ip_filter.rules) == 1

    def test_add_rule_single_ip(self, ip_filter):
        """Test adding single IP rule."""
        result = ip_filter.add_rule("192.168.1.100")
        assert result is True
        assert len(ip_filter.rules) == 1

    def test_add_rule_with_mode(self, ip_filter):
        """Test adding rule with specific mode."""
        result = ip_filter.add_rule("192.168.1.0/24", mode=FilterMode.ALLOW)
        assert result is True
        assert ip_filter.rules[0].mode == FilterMode.ALLOW

    def test_add_rule_with_priority(self, ip_filter):
        """Test adding rule with priority."""
        result = ip_filter.add_rule("192.168.1.0/24", priority=10)
        assert result is True
        assert ip_filter.rules[0].priority == 10

    def test_add_rule_with_source(self, ip_filter):
        """Test adding rule with source."""
        result = ip_filter.add_rule("192.168.1.0/24", source="test_file.txt")
        assert result is True
        assert ip_filter.rules[0].source == "test_file.txt"

    def test_add_rule_invalid_range(self, ip_filter):
        """Test adding invalid IP range."""
        result = ip_filter.add_rule("invalid.range")
        assert result is False
        assert len(ip_filter.rules) == 0

    def test_add_multiple_rules(self, ip_filter):
        """Test adding multiple rules."""
        ip_filter.add_rule("192.168.1.0/24")
        ip_filter.add_rule("10.0.0.0/8")
        ip_filter.add_rule("172.16.0.0/12")
        assert len(ip_filter.rules) == 3
        assert len(ip_filter.ipv4_ranges) == 3

    def test_add_rule_maintains_sorted_ranges(self, ip_filter):
        """Test that ranges stay sorted after adding."""
        ip_filter.add_rule("10.0.0.0/8")
        ip_filter.add_rule("192.168.0.0/16")
        ip_filter.add_rule("172.16.0.0/12")
        
        # Check that ranges are sorted
        network_addresses = [int(n.network_address) for n in ip_filter.ipv4_ranges]
        assert network_addresses == sorted(network_addresses)

    def test_remove_rule_existing(self, ip_filter):
        """Test removing existing rule."""
        ip_filter.add_rule("192.168.1.0/24")
        result = ip_filter.remove_rule("192.168.1.0/24")
        assert result is True
        assert len(ip_filter.rules) == 0
        assert len(ip_filter.ipv4_ranges) == 0

    def test_remove_rule_nonexistent(self, ip_filter):
        """Test removing non-existent rule."""
        result = ip_filter.remove_rule("192.168.1.0/24")
        assert result is False

    def test_remove_rule_partial_match(self, ip_filter):
        """Test removing rule that partially matches."""
        ip_filter.add_rule("192.168.1.0/24")
        # Try to remove with different CIDR notation
        result = ip_filter.remove_rule("192.168.1.0/24")
        assert result is True

    def test_clear_all_rules(self, ip_filter):
        """Test clearing all rules."""
        ip_filter.add_rule("192.168.1.0/24")
        ip_filter.add_rule("10.0.0.0/8")
        ip_filter.add_rule("2001:db8::/32")
        
        ip_filter.clear()
        
        assert len(ip_filter.rules) == 0
        assert len(ip_filter.ipv4_ranges) == 0
        assert len(ip_filter.ipv6_ranges) == 0
        assert ip_filter.stats["matches"] == 0
        assert ip_filter.stats["blocks"] == 0

    def test_get_rules(self, ip_filter):
        """Test getting all rules."""
        ip_filter.add_rule("192.168.1.0/24")
        ip_filter.add_rule("10.0.0.0/8")
        
        rules = ip_filter.get_rules()
        assert len(rules) == 2
        # Should return a copy
        rules.append("dummy")
        assert len(ip_filter.get_rules()) == 2

    def test_get_filter_statistics(self, ip_filter):
        """Test getting filter statistics."""
        ip_filter.add_rule("192.168.1.0/24")
        ip_filter.add_rule("2001:db8::/32")
        ip_filter.is_blocked("192.168.1.10")
        
        stats = ip_filter.get_filter_statistics()
        assert stats["total_rules"] == 2
        assert stats["ipv4_ranges"] == 1
        assert stats["ipv6_ranges"] == 1
        assert stats["matches"] == 1
        assert stats["blocks"] == 1

    def test_remove_rule_invalid_range(self, ip_filter):
        """Test removing rule with invalid range."""
        result = ip_filter.remove_rule("invalid.range")
        assert result is False

    def test_add_rule_default_mode(self, ip_filter):
        """Test that rule uses filter default mode if not specified."""
        ip_filter.mode = FilterMode.ALLOW
        ip_filter.add_rule("192.168.1.0/24")
        assert ip_filter.rules[0].mode == FilterMode.ALLOW

