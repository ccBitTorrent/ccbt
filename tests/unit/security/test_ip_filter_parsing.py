"""Unit tests for IP filter parsing functionality."""

import pytest

from ccbt.security.ip_filter import FilterMode, IPFilter


class TestIPFilterParsing:
    """Tests for IP range parsing in IPFilter."""

    @pytest.fixture
    def ip_filter(self):
        """Create IP filter instance."""
        return IPFilter(enabled=True, mode=FilterMode.BLOCK)

    def test_parse_cidr_ipv4(self, ip_filter):
        """Test parsing CIDR notation for IPv4."""
        network, is_ipv4 = ip_filter._parse_ip_range("192.168.0.0/24")
        assert is_ipv4 is True
        assert str(network) == "192.168.0.0/24"
        assert network.num_addresses == 256

    def test_parse_cidr_ipv6(self, ip_filter):
        """Test parsing CIDR notation for IPv6."""
        network, is_ipv4 = ip_filter._parse_ip_range("2001:db8::/32")
        assert is_ipv4 is False
        assert str(network) == "2001:db8::/32"

    def test_parse_range_notation_ipv4(self, ip_filter):
        """Test parsing range notation for IPv4."""
        network, is_ipv4 = ip_filter._parse_ip_range("192.168.0.0-192.168.255.255")
        assert is_ipv4 is True
        assert network.network_address == ip_filter._parse_ip_range("192.168.0.0/16")[0].network_address
        assert network.broadcast_address == ip_filter._parse_ip_range("192.168.0.0/16")[0].broadcast_address

    def test_parse_range_notation_ipv6(self, ip_filter):
        """Test parsing range notation for IPv6."""
        network, is_ipv4 = ip_filter._parse_ip_range("2001:db8::1-2001:db8::100")
        assert is_ipv4 is False

    def test_parse_single_ipv4(self, ip_filter):
        """Test parsing single IPv4 address."""
        network, is_ipv4 = ip_filter._parse_ip_range("192.168.1.1")
        assert is_ipv4 is True
        assert network.prefixlen == 32
        assert str(network.network_address) == "192.168.1.1"

    def test_parse_single_ipv6(self, ip_filter):
        """Test parsing single IPv6 address."""
        network, is_ipv4 = ip_filter._parse_ip_range("2001:db8::1")
        assert is_ipv4 is False
        assert network.prefixlen == 128

    def test_parse_invalid_cidr(self, ip_filter):
        """Test parsing invalid CIDR notation."""
        with pytest.raises(ValueError, match="Invalid CIDR"):
            ip_filter._parse_ip_range("192.168.1.1/999")

    def test_parse_invalid_range_start_after_end(self, ip_filter):
        """Test parsing range where start > end."""
        with pytest.raises(ValueError, match="Range start must be"):
            ip_filter._parse_ip_range("192.168.1.100-192.168.1.50")

    def test_parse_invalid_range_mixed_versions(self, ip_filter):
        """Test parsing range with mixed IP versions."""
        with pytest.raises(TypeError, match="same IP version"):
            ip_filter._parse_ip_range("192.168.1.1-2001:db8::1")

    def test_parse_invalid_range_format(self, ip_filter):
        """Test parsing invalid range format."""
        with pytest.raises(ValueError, match="Invalid IP range"):
            ip_filter._parse_ip_range("192.168.1.1-192.168.1.2-192.168.1.3")

    def test_parse_invalid_ip(self, ip_filter):
        """Test parsing invalid IP address."""
        with pytest.raises(ValueError):
            ip_filter._parse_ip_range("not.an.ip.address")

    def test_parse_empty_string(self, ip_filter):
        """Test parsing empty string."""
        with pytest.raises(ValueError):
            ip_filter._parse_ip_range("")

    def test_parse_whitespace(self, ip_filter):
        """Test parsing IP range with whitespace."""
        network, is_ipv4 = ip_filter._parse_ip_range("  192.168.1.1/24  ")
        assert is_ipv4 is True
        assert str(network) == "192.168.1.0/24"

    def test_parse_cidr_non_strict(self, ip_filter):
        """Test parsing CIDR with host bits set (non-strict mode)."""
        # Non-strict mode should normalize the network
        network, is_ipv4 = ip_filter._parse_ip_range("192.168.1.5/24")
        assert is_ipv4 is True
        # Should normalize to network address
        assert str(network.network_address) == "192.168.1.0"

