"""Direct tests for tracker peer_source marking (lines 634, 973)."""

from __future__ import annotations

import pytest

from ccbt.discovery.tracker import AsyncTrackerClient


def test_parse_compact_peers_adds_peer_source():
    """Test _parse_compact_peers adds peer_source='tracker' (line 634)."""
    tracker = AsyncTrackerClient()
    
    # Binary format: 6 bytes per peer (4 bytes IP + 2 bytes port)
    binary_peers = (
        b"\xc0\xa8\x01\x01" + b"\x1a\xe1" +  # 192.168.1.1:6881
        b"\xc0\xa8\x01\x02" + b"\x1a\xe2"   # 192.168.1.2:6882
    )
    
    peers = tracker._parse_compact_peers(binary_peers)
    
    # Verify peer_source is set (line 634)
    assert len(peers) == 2
    assert peers[0]["peer_source"] == "tracker"
    assert peers[1]["peer_source"] == "tracker"


def test_parse_announce_response_dictionary_peers_peer_source():
    """Test dictionary peer parsing adds peer_source='tracker' via _parse_response_async."""
    from ccbt.core.bencode import encode
    
    tracker = AsyncTrackerClient()
    
    # Create response with dictionary peer format
    response_data = encode({
        b"interval": 1800,
        b"peers": [
            {b"ip": b"192.168.1.3", b"port": 6883},
            {b"ip": b"192.168.1.4", b"port": 6884},
        ]
    })
    
    # Parse response using _parse_response_async (which now handles dictionary format)
    response = tracker._parse_response_async(response_data)
    
    # Verify peer_source is set for all peers
    assert len(response.peers) == 2
    assert response.peers[0]["peer_source"] == "tracker"
    assert response.peers[1]["peer_source"] == "tracker"
    assert response.peers[0]["ip"] == "192.168.1.3"
    assert response.peers[0]["port"] == 6883
    assert response.peers[1]["ip"] == "192.168.1.4"
    assert response.peers[1]["port"] == 6884

