"""Tests for DHT extension integration with local bencode module."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.extensions.dht import DHTExtension, DHTNode
from ccbt.models import PeerInfo


class TestDHTIntegration:
    """Test cases for DHT extension integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.dht = DHTExtension()
        self.test_node_id = b"\x00" * 20
        self.test_info_hash = b"\x01" * 20

    def test_dht_initialization(self):
        """Test DHT extension initialization."""
        assert self.dht.node_id is not None
        assert len(self.dht.node_id) == 20
        assert isinstance(self.dht.nodes, dict)
        assert isinstance(self.dht.buckets, list)
        assert len(self.dht.buckets) == 160
        assert isinstance(self.dht.peer_storage, dict)
        assert isinstance(self.dht.peer_tokens, dict)

    def test_generate_node_id(self):
        """Test node ID generation."""
        node_id = self.dht._generate_node_id()
        assert isinstance(node_id, bytes)
        assert len(node_id) == 20

    def test_encode_decode_dht_message(self):
        """Test DHT message encoding and decoding."""
        # Test ping message
        message = {
            "t": "aa",
            "y": "q",
            "q": "ping",
            "a": {"id": self.test_node_id.hex()}
        }

        encoded = self.dht._encode_dht_message(message)
        assert isinstance(encoded, bytes)

        decoded = self.dht._decode_dht_message(encoded)
        assert decoded[b"t"] == b"aa"
        assert decoded[b"y"] == b"q"
        assert decoded[b"q"] == b"ping"

    def test_add_node(self):
        """Test adding nodes to DHT."""
        node = DHTNode(
            node_id=self.test_node_id,
            ip="127.0.0.1",
            port=6881
        )

        self.dht.add_node(node)
        assert self.test_node_id in self.dht.routing_table

    def test_find_closest_nodes(self):
        """Test finding closest nodes."""
        # Add some test nodes
        for i in range(5):
            node_id = bytes([i] * 20)
            node = DHTNode(node_id=node_id, ip=f"127.0.0.{i+1}", port=6881)
            self.dht.add_node(node)

        target_id = bytes([2] * 20)
        closest = self.dht.find_closest_nodes(target_id)
        
        assert isinstance(closest, list)
        assert len(closest) <= 8  # K=8 for closest nodes

    def test_generate_validate_token(self):
        """Test token generation and validation."""
        token = self.dht._generate_token(self.test_info_hash)
        assert isinstance(token, str)
        assert len(token) > 0

        # Token should be valid
        assert self.dht._validate_token(self.test_info_hash, token)

        # Invalid token should fail
        assert not self.dht._validate_token(self.test_info_hash, "invalid_token")

    def test_store_retrieve_peers(self):
        """Test peer storage and retrieval."""
        # Store a peer
        self.dht._store_peer(self.test_info_hash, "192.168.1.100", 6881)
        
        # Retrieve peers
        peers = self.dht._get_stored_peers(self.test_info_hash)
        assert len(peers) == 1
        assert ("192.168.1.100", 6881) in peers

    def test_compact_format_helpers(self):
        """Test compact format helper methods."""
        # Test adding nodes from compact format
        compact_data = b"\x00" * 26  # 20-byte ID + 4-byte IP + 2-byte port
        self.dht._add_nodes_from_compact_format(compact_data)
        
        # Test storing peers from compact format
        peer_data = [b"\xc0\xa8\x01\x64\x1a\xe1"]  # 192.168.1.100:6881
        self.dht._store_peers_from_compact_format(self.test_info_hash, peer_data)
        
        peers = self.dht._get_stored_peers(self.test_info_hash)
        assert ("192.168.1.100", 6881) in peers

    @pytest.mark.asyncio
    async def test_handle_query_ping(self):
        """Test handling ping query."""
        message = {
            "t": "aa",
            "y": "q",
            "q": "ping",
            "a": {"id": self.test_node_id.hex()}
        }

        response = await self.dht._handle_query("127.0.0.1", 6881, message)
        assert isinstance(response, bytes)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_handle_query_find_node(self):
        """Test handling find_node query."""
        message = {
            "t": "bb",
            "y": "q",
            "q": "find_node",
            "a": {"id": self.test_node_id.hex(), "target": self.test_node_id.hex()}
        }

        response = await self.dht._handle_query("127.0.0.1", 6881, message)
        assert isinstance(response, bytes)

    @pytest.mark.asyncio
    async def test_handle_query_get_peers(self):
        """Test handling get_peers query."""
        # Store some peers first
        self.dht._store_peer(self.test_info_hash, "192.168.1.100", 6881)
        
        message = {
            "t": "cc",
            "y": "q",
            "q": "get_peers",
            "a": {"id": self.test_node_id.hex(), "info_hash": self.test_info_hash.hex()}
        }

        response = await self.dht._handle_query("127.0.0.1", 6881, message)
        assert isinstance(response, bytes)

    @pytest.mark.asyncio
    async def test_handle_query_announce_peer(self):
        """Test handling announce_peer query."""
        # Generate a valid token first
        token = self.dht._generate_token(self.test_info_hash)
        
        message = {
            "t": "dd",
            "y": "q",
            "q": "announce_peer",
            "a": {
                "id": self.test_node_id.hex(),
                "info_hash": self.test_info_hash.hex(),
                "token": token,
                "port": 6881
            }
        }

        response = await self.dht._handle_query("127.0.0.1", 6881, message)
        assert isinstance(response, bytes)

    @pytest.mark.asyncio
    async def test_handle_query_invalid_token(self):
        """Test handling announce_peer with invalid token."""
        message = {
            "t": "dd",
            "y": "q",
            "q": "announce_peer",
            "a": {
                "id": self.test_node_id.hex(),
                "info_hash": self.test_info_hash.hex(),
                "token": "invalid_token",
                "port": 6881
            }
        }

        response = await self.dht._handle_query("127.0.0.1", 6881, message)
        assert isinstance(response, bytes)

    @pytest.mark.asyncio
    async def test_handle_response_ping(self):
        """Test handling ping response."""
        message = {
            "t": "aa",
            "y": "r",
            "r": {"id": self.test_node_id.hex()}
        }

        # Add node to routing table first
        node = DHTNode(node_id=self.test_node_id, ip="127.0.0.1", port=6881)
        self.dht.add_node(node)

        await self.dht._handle_response("127.0.0.1", 6881, message)
        
        # Node should be marked as alive
        assert self.test_node_id in self.dht.routing_table

    @pytest.mark.asyncio
    async def test_handle_response_find_node(self):
        """Test handling find_node response."""
        message = {
            "t": "bb",
            "y": "r",
            "r": {"id": self.test_node_id.hex(), "nodes": b"\x00" * 26}
        }

        await self.dht._handle_response("127.0.0.1", 6881, message)
        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_handle_response_get_peers(self):
        """Test handling get_peers response."""
        message = {
            "t": "cc",
            "y": "r",
            "r": {"id": self.test_node_id.hex(), "values": b"\xc0\xa8\x01\x64\x1a\xe1"},
            "a": {"info_hash": self.test_info_hash.hex()}
        }

        await self.dht._handle_response("127.0.0.1", 6881, message)
        
        # Peers should be stored
        peers = self.dht._get_stored_peers(self.test_info_hash)
        assert ("192.168.1.100", 6881) in peers

    def test_encode_ping_response(self):
        """Test encoding ping response."""
        transaction_id = b"aa"
        response = self.dht.encode_ping_response(transaction_id, self.test_node_id)
        assert isinstance(response, bytes)

    def test_encode_find_node_response(self):
        """Test encoding find_node response."""
        transaction_id = b"bb"
        closest_nodes = []
        response = self.dht.encode_find_node_response(transaction_id, closest_nodes)
        assert isinstance(response, bytes)

    def test_encode_get_peers_response(self):
        """Test encoding get_peers response."""
        transaction_id = b"cc"
        peers_list = [PeerInfo(ip="192.168.1.100", port=6881)]
        nodes_list = []
        token = "test_token"
        
        response = self.dht.encode_get_peers_response(transaction_id, peers_list, nodes_list, token)
        assert isinstance(response, bytes)

    def test_encode_error_response(self):
        """Test encoding error response."""
        transaction_id = b"dd"
        error_code = 203
        error_message = "Invalid token"
        
        response = self.dht.encode_error_response(transaction_id, error_code, error_message)
        assert isinstance(response, bytes)

    def test_bucket_index_calculation(self):
        """Test bucket index calculation."""
        # Test with different node IDs
        node_id1 = b"\x00" * 20
        node_id2 = b"\x01" * 20
        
        index1 = self.dht._get_bucket_index(node_id1)
        index2 = self.dht._get_bucket_index(node_id2)
        
        assert isinstance(index1, int)
        assert isinstance(index2, int)
        assert 0 <= index1 < 160
        assert 0 <= index2 < 160

    def test_distance_calculation(self):
        """Test distance calculation between node IDs."""
        node_id1 = b"\x00" * 20
        node_id2 = b"\x01" * 20
        
        distance = self.dht._calculate_distance(node_id1, node_id2)
        assert isinstance(distance, int)
        assert distance >= 0

    def test_peer_storage_cleanup(self):
        """Test peer storage cleanup."""
        # Store some peers
        self.dht._store_peer(self.test_info_hash, "192.168.1.100", 6881)
        self.dht._store_peer(self.test_info_hash, "192.168.1.101", 6882)
        
        # Verify they're stored
        peers = self.dht._get_stored_peers(self.test_info_hash)
        assert len(peers) == 2
        
        # Test cleanup (this would be called periodically)
        # For now, just verify the method exists
        assert hasattr(self.dht, '_cleanup_peer_storage')

    def test_routing_table_management(self):
        """Test routing table management."""
        # Add multiple nodes
        for i in range(10):
            node_id = bytes([i] * 20)
            node = DHTNode(node_id=node_id, ip=f"127.0.0.{i+1}", port=6881)
            self.dht.add_node(node)
        
        # Verify nodes are in routing table
        assert len(self.dht.routing_table) == 10
        
        # Test finding nodes
        target_id = bytes([5] * 20)
        closest = self.dht.find_closest_nodes(target_id)
        assert isinstance(closest, list)

    def test_dht_statistics(self):
        """Test DHT statistics collection."""
        # Add some nodes and peers
        node = DHTNode(node_id=self.test_node_id, ip="127.0.0.1", port=6881)
        self.dht.add_node(node)
        self.dht._store_peer(self.test_info_hash, "192.168.1.100", 6881)
        
        stats = self.dht.get_statistics()
        
        assert "nodes_count" in stats
        assert "buckets_count" in stats
        assert "peer_storage_count" in stats
        assert stats["nodes_count"] >= 1
        assert stats["peer_storage_count"] >= 1
