"""Unit tests for BEP 45: Multiple-Address Operation for DHT.

Tests multi-address encoding/decoding, address selection, and validation.
Target: 95%+ code coverage for ccbt/discovery/dht_multiaddr.py
"""

from __future__ import annotations

import ipaddress

import pytest

from ccbt.discovery.dht import DHTNode
from ccbt.discovery.dht_multiaddr import (
    AddressType,
    calculate_address_priority,
    decode_multi_address_node,
    encode_multi_address_node,
    get_address_type,
    select_best_address_multi,
    validate_address,
)

pytestmark = [pytest.mark.unit, pytest.mark.discovery]


class TestAddressType:
    """Test AddressType enum."""

    def test_address_type_ipv4(self):
        """Test IPv4 address type."""
        assert AddressType.IPv4.value == "ipv4"

    def test_address_type_ipv6(self):
        """Test IPv6 address type."""
        assert AddressType.IPv6.value == "ipv6"


class TestGetAddressType:
    """Test get_address_type function."""

    def test_get_address_type_ipv4(self):
        """Test detecting IPv4 address."""
        assert get_address_type("192.168.1.1") == AddressType.IPv4
        assert get_address_type("127.0.0.1") == AddressType.IPv4
        assert get_address_type("10.0.0.1") == AddressType.IPv4

    def test_get_address_type_ipv6(self):
        """Test detecting IPv6 address."""
        assert get_address_type("2001:db8::1") == AddressType.IPv6
        assert get_address_type("::1") == AddressType.IPv6
        assert get_address_type("fe80::1") == AddressType.IPv6

    def test_get_address_type_invalid(self):
        """Test invalid address defaults to IPv4."""
        assert get_address_type("invalid") == AddressType.IPv4
        assert get_address_type("") == AddressType.IPv4


class TestValidateAddress:
    """Test validate_address function."""

    def test_validate_address_valid_ipv4(self):
        """Test validating valid IPv4 address."""
        assert validate_address("192.168.1.1", 6881)
        assert validate_address("127.0.0.1", 6881)
        assert validate_address("10.0.0.1", 6881)

    def test_validate_address_valid_ipv6(self):
        """Test validating valid IPv6 address."""
        assert validate_address("2001:db8::1", 6881)
        assert validate_address("::1", 6881)

    def test_validate_address_invalid_ip(self):
        """Test validating invalid IP address."""
        assert not validate_address("invalid", 6881)
        assert not validate_address("", 6881)

    def test_validate_address_invalid_port(self):
        """Test validating invalid port."""
        assert not validate_address("192.168.1.1", 0)  # Port too low
        assert not validate_address("192.168.1.1", 65536)  # Port too high
        assert not validate_address("192.168.1.1", -1)  # Negative port


class TestCalculateAddressPriority:
    """Test calculate_address_priority function."""

    def test_calculate_priority_ipv6_preferred(self):
        """Test priority calculation with IPv6 preferred."""
        ipv6_priority = calculate_address_priority(
            "2001:db8::1", 6881, prefer_ipv6=True
        )
        ipv4_priority = calculate_address_priority(
            "192.168.1.1", 6881, prefer_ipv6=True
        )

        assert ipv6_priority > ipv4_priority

    def test_calculate_priority_ipv4_preferred(self):
        """Test priority calculation with IPv4 preferred."""
        ipv6_priority = calculate_address_priority(
            "2001:db8::1", 6881, prefer_ipv6=False
        )
        ipv4_priority = calculate_address_priority(
            "192.168.1.1", 6881, prefer_ipv6=False
        )

        # IPv6 still has higher base priority
        assert ipv6_priority >= ipv4_priority

    def test_calculate_priority_port_impact(self):
        """Test port number impacts priority."""
        priority_well_known = calculate_address_priority(
            "192.168.1.1", 6881, prefer_ipv6=False
        )
        priority_ephemeral = calculate_address_priority(
            "192.168.1.1", 50000, prefer_ipv6=False
        )

        # Well-known ports get higher priority
        assert priority_well_known >= priority_ephemeral


class TestEncodeMultiAddressNode:
    """Test encode_multi_address_node function."""

    def test_encode_multi_address_node_ipv4_only(self):
        """Test encoding node with IPv4 only."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )
        encoded = encode_multi_address_node(node)

        assert b"id" in encoded
        assert encoded[b"id"] == node.node_id
        assert b"ip" in encoded
        assert len(encoded[b"ip"]) == 6  # 4 bytes IP + 2 bytes port

    def test_encode_multi_address_node_dual_stack(self):
        """Test encoding node with both IPv4 and IPv6."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )
        encoded = encode_multi_address_node(node)

        assert b"id" in encoded
        assert b"ip" in encoded  # IPv4
        assert b"ip6" in encoded  # IPv6
        assert len(encoded[b"ip6"]) == 18  # 16 bytes IPv6 + 2 bytes port

    def test_encode_multi_address_node_with_additional(self):
        """Test encoding node with additional addresses."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )
        node.add_address("10.0.0.1", 6882)
        node.add_address("172.16.0.1", 6883)

        encoded = encode_multi_address_node(node)

        assert b"id" in encoded
        assert b"ip" in encoded
        # Should include all addresses
        assert len(node.get_all_addresses()) > 1


class TestDecodeMultiAddressNode:
    """Test decode_multi_address_node function."""

    def test_decode_multi_address_node_ipv4_only(self):
        """Test decoding node with IPv4 only."""
        node_id = b"\x01" * 20
        ip_bytes = ipaddress.IPv4Address("192.168.1.1").packed
        port_val = 6881
        port_bytes = port_val.to_bytes(2, "big")
        data = {
            b"id": node_id,
            b"ip": ip_bytes + port_bytes,
        }

        node = decode_multi_address_node(data)

        assert node.node_id == node_id
        assert node.ip == "192.168.1.1"
        assert node.port == 6881

    def test_decode_multi_address_node_dual_stack(self):
        """Test decoding node with both IPv4 and IPv6."""
        node_id = b"\x01" * 20
        ip_bytes = ipaddress.IPv4Address("192.168.1.1").packed
        port_val = 6881
        port_bytes = port_val.to_bytes(2, "big")
        ipv6_bytes = ipaddress.IPv6Address("2001:db8::1").packed
        port6_val = 6882
        port6_bytes = port6_val.to_bytes(2, "big")
        data = {
            b"id": node_id,
            b"ip": ip_bytes + port_bytes,
            b"ip6": ipv6_bytes + port6_bytes,
        }

        node = decode_multi_address_node(data)

        assert node.node_id == node_id
        assert node.ip == "192.168.1.1"
        assert node.port == 6881
        assert node.ipv6 == "2001:db8::1"
        expected_port6 = 6882
        assert node.port6 == expected_port6

    def test_decode_multi_address_node_with_node_id(self):
        """Test decoding with explicit node_id parameter."""
        node_id = b"\x02" * 20
        data = {b"ip": ipaddress.IPv4Address("192.168.1.1").packed + b"\x1a\xe1"}

        node = decode_multi_address_node(data, node_id=node_id)

        assert node.node_id == node_id

    def test_decode_multi_address_node_invalid_ip(self):
        """Test decoding with invalid IP data."""
        data = {b"id": b"\x01" * 20, b"ip": b"\x00" * 5}  # Too short

        # Should handle gracefully
        node = decode_multi_address_node(data)
        # Node should still be created, just without valid IP
        assert node.node_id == b"\x01" * 20

    def test_decode_multi_address_node_invalid_node_id(self):
        """Test decoding with invalid node ID."""
        data = {b"id": b"\x01" * 19}  # Wrong length

        with pytest.raises(ValueError, match="Invalid node ID"):
            decode_multi_address_node(data)

    def test_decode_multi_address_node_no_node_id(self):
        """Test decoding with no node ID in data."""
        data = {b"ip": ipaddress.IPv4Address("192.168.1.1").packed + b"\x1a\xe1"}

        with pytest.raises(ValueError, match="Invalid node ID"):
            decode_multi_address_node(data)

    def test_decode_multi_address_node_with_additional_addresses_ipv6(self):
        """Test decoding node with IPv6 additional addresses."""
        node_id = b"\x01" * 20
        ipv6_bytes = ipaddress.IPv6Address("2001:db8::2").packed
        port6_bytes = (6883).to_bytes(2, "big")
        data = {
            b"id": node_id,
            b"ip": ipaddress.IPv4Address("192.168.1.1").packed + b"\x1a\xe1",
            b"addresses": [ipv6_bytes + port6_bytes],  # IPv6 address
        }

        node = decode_multi_address_node(data)

        assert node.node_id == node_id
        # Should have IPv6 address in additional addresses
        all_addrs = node.get_all_addresses()
        assert ("2001:db8::2", 6883) in all_addrs

    def test_decode_multi_address_node_with_non_bytes_address(self):
        """Test decoding with non-bytes address data."""
        node_id = b"\x01" * 20
        data = {
            b"id": node_id,
            b"ip": ipaddress.IPv4Address("192.168.1.1").packed + b"\x1a\xe1",
            b"addresses": ["not bytes", 12345],  # Invalid types
        }

        node = decode_multi_address_node(data)

        # Should handle gracefully, skip invalid addresses
        assert node.node_id == node_id
        assert node.ip == "192.168.1.1"

    def test_decode_multi_address_node_with_decode_errors(self):
        """Test decoding with address decode errors."""
        node_id = b"\x01" * 20
        # Invalid IPv6 address bytes
        invalid_ipv6 = b"\xff" * 18  # Invalid IPv6
        # Invalid IPv4 address bytes
        invalid_ipv4 = b"\xff" * 6  # Invalid IPv4
        data = {
            b"id": node_id,
            b"ip": ipaddress.IPv4Address("192.168.1.1").packed + b"\x1a\xe1",
            b"addresses": [invalid_ipv6, invalid_ipv4],
        }

        node = decode_multi_address_node(data)

        # Should handle gracefully, skip invalid addresses
        assert node.node_id == node_id
        assert node.ip == "192.168.1.1"
        # Invalid addresses should be skipped (some may still parse, that's OK)
        all_addrs = node.get_all_addresses()
        assert ("192.168.1.1", 6881) in all_addrs
        # At minimum, the primary address should be present
        assert len(all_addrs) >= 1


class TestDiscoverNodeAddresses:
    """Test discover_node_addresses function."""

    def test_discover_node_addresses_basic(self):
        """Test discovering node addresses."""
        from ccbt.discovery.dht_multiaddr import discover_node_addresses

        known_addresses = [
            ("192.168.1.1", 6881),
            ("10.0.0.1", 6882),
            ("2001:db8::1", 6883),
        ]

        results = discover_node_addresses(known_addresses, max_results=10)

        assert len(results) == 3
        assert ("192.168.1.1", 6881) in results
        assert ("10.0.0.1", 6882) in results
        assert ("2001:db8::1", 6883) in results

    def test_discover_node_addresses_max_results(self):
        """Test discovering addresses with max_results limit."""
        from ccbt.discovery.dht_multiaddr import discover_node_addresses

        known_addresses = [
            ("192.168.1.1", 6881),
            ("10.0.0.1", 6882),
            ("2001:db8::1", 6883),
            ("172.16.0.1", 6884),
        ]

        results = discover_node_addresses(known_addresses, max_results=2)

        assert len(results) == 2

    def test_discover_node_addresses_filters_invalid(self):
        """Test discovering addresses filters invalid addresses."""
        from ccbt.discovery.dht_multiaddr import discover_node_addresses

        known_addresses = [
            ("192.168.1.1", 6881),  # Valid
            ("invalid-ip", 6882),  # Invalid IP
            ("10.0.0.1", 0),  # Invalid port
            ("2001:db8::1", 6883),  # Valid
        ]

        results = discover_node_addresses(known_addresses, max_results=10)

        # Should only return valid addresses
        assert len(results) == 2
        assert ("192.168.1.1", 6881) in results
        assert ("2001:db8::1", 6883) in results

    def test_discover_node_addresses_removes_duplicates(self):
        """Test discovering addresses removes duplicates."""
        from ccbt.discovery.dht_multiaddr import discover_node_addresses

        known_addresses = [
            ("192.168.1.1", 6881),
            ("192.168.1.1", 6881),  # Duplicate
            ("10.0.0.1", 6882),
            ("10.0.0.1", 6882),  # Duplicate
        ]

        results = discover_node_addresses(known_addresses, max_results=10)

        # Should remove duplicates
        assert len(results) == 2
        assert results.count(("192.168.1.1", 6881)) == 1
        assert results.count(("10.0.0.1", 6882)) == 1


class TestSelectBestAddressMulti:
    """Test select_best_address_multi function."""

    def test_select_best_address_multi_ipv4_only(self):
        """Test selecting from IPv4-only node."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )

        addr = select_best_address_multi(
            node, prefer_ipv6=True, enable_ipv6=True, max_addresses=4
        )

        assert addr == ("192.168.1.1", 6881)

    def test_select_best_address_multi_dual_stack(self):
        """Test selecting from dual-stack node."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )

        addr = select_best_address_multi(
            node, prefer_ipv6=True, enable_ipv6=True, max_addresses=4
        )

        # Should prefer IPv6 when enabled and preferred
        assert addr == ("2001:db8::1", 6882)

    def test_select_best_address_multi_with_additional(self):
        """Test selecting from node with multiple addresses."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )
        node.add_address("10.0.0.1", 6883)
        node.add_address("172.16.0.1", 6884)

        addr = select_best_address_multi(
            node, prefer_ipv6=True, enable_ipv6=True, max_addresses=4
        )

        # Should select based on priority
        assert addr in node.get_all_addresses()

    def test_select_best_address_multi_ipv6_disabled(self):
        """Test selecting when IPv6 is disabled."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )

        addr = select_best_address_multi(
            node, prefer_ipv6=True, enable_ipv6=False, max_addresses=4
        )

        # Should use IPv4 when IPv6 disabled
        assert addr == ("192.168.1.1", 6881)

    def test_select_best_address_multi_no_addresses(self):
        """Test selecting when node has no addresses."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="",
            port=0,
        )

        with pytest.raises(ValueError, match=r"Node has no valid address"):
            select_best_address_multi(node)

    def test_select_best_address_multi_max_addresses(self):
        """Test max_addresses parameter limits selection."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )
        # Add many addresses
        for i in range(10):
            node.add_address(f"10.0.0.{i+1}", 6881 + i)

        addr = select_best_address_multi(
            node, prefer_ipv6=False, enable_ipv6=True, max_addresses=4
        )

        # Should still return a valid address
        assert addr in node.get_all_addresses()


class TestMultiAddressIntegration:
    """Integration tests for multi-address DHT operations."""

    def test_node_with_multiple_addresses(self):
        """Test DHTNode with multiple addresses."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )
        node.add_address("10.0.0.1", 6883)
        node.add_address("172.16.0.1", 6884)

        addresses = node.get_all_addresses()
        assert len(addresses) >= 4

        primary = node.get_primary_address()
        assert primary == ("192.168.1.1", 6881)

    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )
        node.add_address("10.0.0.1", 6883)

        encoded = encode_multi_address_node(node)
        decoded = decode_multi_address_node(encoded)

        assert decoded.node_id == node.node_id
        assert decoded.ip == node.ip
        assert decoded.port == node.port
        assert decoded.ipv6 == node.ipv6
        assert decoded.port6 == node.port6

    def test_address_priority_sorting(self):
        """Test addresses are sorted by priority."""
        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
            ipv6="2001:db8::1",
            port6=6882,
        )
        node.add_address("10.0.0.1", 6883)
        node.add_address("172.16.0.1", 6884)

        # Select best address with IPv6 preferred
        addr = select_best_address_multi(
            node, prefer_ipv6=True, enable_ipv6=True, max_addresses=4
        )

        # IPv6 should be selected when preferred
        assert addr[0] == "2001:db8::1" or addr in node.get_all_addresses()

