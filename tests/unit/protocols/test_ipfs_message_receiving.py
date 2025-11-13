"""Unit tests for IPFS message receiving with Bitswap protocol."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.protocols.ipfs import IPFSProtocol


@pytest.fixture
def mock_ipfs_client():
    """Create a mock IPFS client."""
    client = MagicMock()
    client.id.return_value = {"ID": "test-peer-id", "Addresses": []}
    client.pubsub.subscribe.return_value = iter([])
    return client


@pytest.fixture
def ipfs_protocol(mock_ipfs_client):
    """Create IPFS protocol instance with mocked client."""
    protocol = IPFSProtocol()
    
    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        return_value=mock_ipfs_client,
    ):
        protocol._ipfs_client = mock_ipfs_client
        protocol._ipfs_connected = True
    
    return protocol


@pytest.mark.asyncio
async def test_parse_bitswap_message_basic(ipfs_protocol):
    """Test basic Bitswap message parsing."""
    message = b"test message"
    formatted = ipfs_protocol._format_bitswap_message(message)
    parsed = ipfs_protocol._parse_bitswap_message(formatted)
    
    assert parsed["payload"] == message
    assert parsed["want_list"] == []
    assert parsed["blocks"] == {}


@pytest.mark.asyncio
async def test_parse_bitswap_message_with_want_list(ipfs_protocol):
    """Test Bitswap message parsing with want_list."""
    message = b"test message"
    want_list = ["QmTestCID1", "QmTestCID2"]
    formatted = ipfs_protocol._format_bitswap_message(message, want_list=want_list)
    parsed = ipfs_protocol._parse_bitswap_message(formatted)
    
    assert parsed["want_list"] == want_list
    assert parsed["payload"] == message


@pytest.mark.asyncio
async def test_parse_bitswap_message_with_blocks(ipfs_protocol):
    """Test Bitswap message parsing with blocks."""
    message = b"test message"
    blocks = {"QmBlock1": b"block1 data", "QmBlock2": b"block2 data"}
    formatted = ipfs_protocol._format_bitswap_message(message, blocks=blocks)
    parsed = ipfs_protocol._parse_bitswap_message(formatted)
    
    assert parsed["blocks"]["QmBlock1"] == blocks["QmBlock1"]
    assert parsed["blocks"]["QmBlock2"] == blocks["QmBlock2"]


@pytest.mark.asyncio
async def test_parse_bitswap_message_invalid_json(ipfs_protocol):
    """Test parsing invalid JSON message."""
    invalid_message = b"not valid json"
    parsed = ipfs_protocol._parse_bitswap_message(invalid_message)
    
    # Should return empty result
    assert parsed["payload"] == b""
    assert parsed["want_list"] == []
    assert parsed["blocks"] == {}


@pytest.mark.asyncio
async def test_parse_bitswap_message_invalid_encoding(ipfs_protocol):
    """Test parsing message with invalid encoding."""
    # Binary data that's not valid UTF-8
    invalid_message = b"\xff\xfe\x00\x01"
    parsed = ipfs_protocol._parse_bitswap_message(invalid_message)
    
    # Should return empty result
    assert parsed["payload"] == b""
    assert parsed["want_list"] == []
    assert parsed["blocks"] == {}


@pytest.mark.asyncio
async def test_receive_message_basic(ipfs_protocol):
    """Test basic message receiving."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol.ipfs_peers[peer_id].bytes_received = 0
    ipfs_protocol.ipfs_peers[peer_id].last_seen = 0.0
    
    # Setup message queue
    message_queue = asyncio.Queue()
    ipfs_protocol._peer_message_queues[peer_id] = message_queue
    
    test_message = b"test message"
    await message_queue.put(test_message)
    
    received = await ipfs_protocol.receive_message(peer_id)
    assert received == test_message


@pytest.mark.asyncio
async def test_receive_message_bitswap(ipfs_protocol):
    """Test receiving Bitswap formatted message."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol.ipfs_peers[peer_id].bytes_received = 0
    ipfs_protocol.ipfs_peers[peer_id].last_seen = 0.0
    
    message_queue = asyncio.Queue()
    ipfs_protocol._peer_message_queues[peer_id] = message_queue
    
    # Create Bitswap formatted message
    payload = b"test payload"
    formatted = ipfs_protocol._format_bitswap_message(payload)
    await message_queue.put(formatted)
    
    received = await ipfs_protocol.receive_message(peer_id, parse_bitswap=True)
    assert received == payload


@pytest.mark.asyncio
async def test_receive_message_no_parse_bitswap(ipfs_protocol):
    """Test receiving message without Bitswap parsing."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol.ipfs_peers[peer_id].bytes_received = 0
    ipfs_protocol.ipfs_peers[peer_id].last_seen = 0.0
    
    message_queue = asyncio.Queue()
    ipfs_protocol._peer_message_queues[peer_id] = message_queue
    
    formatted = ipfs_protocol._format_bitswap_message(b"test")
    await message_queue.put(formatted)
    
    received = await ipfs_protocol.receive_message(peer_id, parse_bitswap=False)
    # Should return raw formatted message
    assert received == formatted


@pytest.mark.asyncio
async def test_receive_message_peer_not_found(ipfs_protocol):
    """Test receiving message from non-existent peer."""
    result = await ipfs_protocol.receive_message("unknown-peer")
    assert result is None


@pytest.mark.asyncio
async def test_receive_message_not_connected(ipfs_protocol):
    """Test receiving message when not connected."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    result = await ipfs_protocol.receive_message(peer_id)
    assert result is None


@pytest.mark.asyncio
async def test_receive_message_timeout(ipfs_protocol):
    """Test message receiving timeout."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol.ipfs_peers[peer_id].bytes_received = 0
    ipfs_protocol.ipfs_peers[peer_id].last_seen = 0.0
    
    message_queue = asyncio.Queue()
    ipfs_protocol._peer_message_queues[peer_id] = message_queue
    
    # Queue is empty, should timeout
    result = await ipfs_protocol.receive_message(peer_id)
    assert result is None


@pytest.mark.asyncio
async def test_receive_message_partial_handling(ipfs_protocol):
    """Test handling of partial messages."""
    peer_id = "test-peer-id"
    ipfs_protocol.ipfs_peers[peer_id] = MagicMock()
    ipfs_protocol.ipfs_peers[peer_id].bytes_received = 0
    ipfs_protocol.ipfs_peers[peer_id].last_seen = 0.0
    
    message_queue = asyncio.Queue()
    ipfs_protocol._peer_message_queues[peer_id] = message_queue
    
    # Put incomplete JSON (partial message)
    partial_message = b'{"payload": "incomplete'
    await message_queue.put(partial_message)
    
    received = await ipfs_protocol.receive_message(peer_id)
    # Should handle gracefully (return raw or empty)
    assert received is not None

