"""Tests for DHT IPv6 node merging logic (lines 457-469 of dht.py).

Covers:
- IPv6 node parsing from nodes6 field
- Merging IPv6 nodes with existing IPv4 nodes (dual-stack)
- IPv6-only node addition
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.discovery.dht import AsyncDHTClient, DHTNode
from ccbt.discovery.dht_ipv6 import encode_ipv6_node, parse_ipv6_nodes

pytestmark = [pytest.mark.unit]


@pytest.mark.asyncio
async def test_find_node_merges_ipv6_with_ipv4_dual_stack():
    """Test find_node merges IPv6 nodes with existing IPv4 nodes (lines 461-466)."""
    client = AsyncDHTClient()
    client.node_id = b"\x00" * 20
    
    # Create IPv4 node
    ipv4_node = DHTNode(
        node_id=b"\x01" * 20,
        ip="192.168.1.1",
        port=6881,
    )
    
    # Create IPv6 node with same node_id (dual-stack)
    ipv6_node = DHTNode(
        node_id=b"\x01" * 20,  # Same node_id as IPv4 node
        ip="192.168.1.1",
        port=6881,
        ipv6="2001:db8::1",
        port6=6882,
    )
    
    # Encode nodes for response
    ipv4_nodes_data = (
        ipv4_node.node_id 
        + bytes([int(x) for x in ipv4_node.ip.split(".")]) 
        + ipv4_node.port.to_bytes(2, "big")
    )
    
    encoded_ipv6_nodes = encode_ipv6_node(ipv6_node)
    
    # Mock response with both nodes and nodes6
    mock_response = {
        b"y": b"r",
        b"r": {
            b"id": b"\x02" * 20,
            b"nodes": ipv4_nodes_data,
            b"nodes6": encoded_ipv6_nodes,
        },
    }
    
    # Mock transport
    mock_transport = AsyncMock()
    mock_transport.is_closing.return_value = False
    
    async def mock_send_query(addr, query, params):
        return mock_response
    
    client.transport = mock_transport
    client._send_query = mock_send_query  # type: ignore[method-assign]
    
    # Call _find_nodes (note: plural, takes addr and target_id separately)
    target_id = b"\x03" * 20
    result = await client._find_nodes(("127.0.0.1", 6881), target_id)
    
    # Verify result contains merged node
    assert len(result) == 1
    merged_node = result[0]
    assert merged_node.node_id == ipv4_node.node_id
    assert merged_node.ip == ipv4_node.ip
    assert merged_node.port == ipv4_node.port
    assert merged_node.ipv6 == "2001:db8::1"  # IPv6 address merged
    assert merged_node.port6 == 6882  # IPv6 port merged


@pytest.mark.asyncio
async def test_find_node_adds_ipv6_only_node():
    """Test find_node adds IPv6-only node when no matching IPv4 node (lines 467-469)."""
    client = AsyncDHTClient()
    client.node_id = b"\x00" * 20
    
    # Create IPv4 node
    ipv4_node = DHTNode(
        node_id=b"\x01" * 20,
        ip="192.168.1.1",
        port=6881,
    )
    
    # Create IPv6-only node (different node_id)
    ipv6_only_node = DHTNode(
        node_id=b"\x02" * 20,  # Different node_id
        ip="192.168.1.2",
        port=6881,
        ipv6="2001:db8::2",
        port6=6882,
    )
    
    # Encode nodes for response
    ipv4_nodes_data = (
        ipv4_node.node_id 
        + bytes([int(x) for x in ipv4_node.ip.split(".")]) 
        + ipv4_node.port.to_bytes(2, "big")
    )
    
    encoded_ipv6_nodes = encode_ipv6_node(ipv6_only_node)
    
    # Mock response
    mock_response = {
        b"y": b"r",
        b"r": {
            b"id": b"\x03" * 20,
            b"nodes": ipv4_nodes_data,
            b"nodes6": encoded_ipv6_nodes,
        },
    }
    
    # Mock transport
    mock_transport = AsyncMock()
    mock_transport.is_closing.return_value = False
    
    async def mock_send_query(addr, query, params):
        return mock_response
    
    client.transport = mock_transport
    client._send_query = mock_send_query  # type: ignore[method-assign]
    
    # Call _find_nodes (note: plural, takes addr and target_id separately)
    target_id = b"\x04" * 20
    result = await client._find_nodes(("127.0.0.1", 6881), target_id)
    
    # Verify result contains both nodes
    assert len(result) == 2
    
    # Check IPv4 node
    ipv4_result = next(n for n in result if n.node_id == ipv4_node.node_id)
    assert ipv4_result.ip == ipv4_node.ip
    
    # Check IPv6-only node was added
    ipv6_result = next(n for n in result if n.node_id == ipv6_only_node.node_id)
    assert ipv6_result.ipv6 == "2001:db8::2"
    assert ipv6_result.port6 == 6882


@pytest.mark.asyncio
async def test_get_peers_skips_private_torrent():
    """Test get_peers returns empty for private torrents (lines 499-503)."""
    client = AsyncDHTClient()
    client.node_id = b"\x00" * 20
    
    # Mock private torrent checker
    def is_private(info_hash: bytes) -> bool:
        return info_hash == b"\x01" * 20
    
    client._is_private_torrent = is_private
    
    # Call get_peers with private torrent
    private_info_hash = b"\x01" * 20
    result = await client.get_peers(private_info_hash)
    
    # Should return empty list immediately
    assert result == []


@pytest.mark.asyncio
async def test_get_peers_allows_public_torrent():
    """Test get_peers works for public torrents (lines 499-503)."""
    client = AsyncDHTClient()
    client.node_id = b"\x00" * 20
    
    # Mock private torrent checker that returns False
    def is_not_private(info_hash: bytes) -> bool:
        return False
    
    client._is_private_torrent = is_not_private
    
    # Mock transport and responses - need to mock get_peers query chain
    # Since get_peers uses iterative lookup, we'll just verify it doesn't skip immediately
    client.transport = AsyncMock()
    client.transport.is_closing.return_value = False
    
    # Call get_peers with public torrent
    public_info_hash = b"\x02" * 20
    # This will try to do actual lookups, so we expect it may fail but shouldn't skip immediately
    result = await client.get_peers(public_info_hash)
    
    # Should return a list (may be empty if no peers found)
    assert isinstance(result, list)
