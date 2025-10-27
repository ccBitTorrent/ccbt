"""DHT (Distributed Hash Table) extension implementation.

Provides support for:
- DHT peer discovery
- DHT node management
- DHT message handling
"""

import hashlib
import random
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set

from ..events import Event, EventType, emit_event
from ..models import PeerInfo


class DHTMessageType(IntEnum):
    """DHT message types."""
    QUERY = 0
    RESPONSE = 1
    ERROR = 2


class DHTQueryType(IntEnum):
    """DHT query types."""
    PING = 0
    FIND_NODE = 1
    GET_PEERS = 2
    ANNOUNCE_PEER = 3


@dataclass
class DHTNode:
    """DHT node information."""
    node_id: bytes
    ip: str
    port: int
    last_seen: float = 0.0

    def __hash__(self):
        return hash((self.node_id, self.ip, self.port))

    def __eq__(self, other):
        if not isinstance(other, DHTNode):
            return False
        return (self.node_id == other.node_id and
                self.ip == other.ip and
                self.port == other.port)


class DHTExtension:
    """DHT (Distributed Hash Table) implementation."""

    def __init__(self, node_id: Optional[bytes] = None):
        self.node_id = node_id or self._generate_node_id()
        self.nodes: Dict[bytes, DHTNode] = {}
        self.buckets: List[Set[DHTNode]] = [[] for _ in range(160)]  # 160-bit ID space
        self.routing_table: Dict[bytes, DHTNode] = {}

    def _generate_node_id(self) -> bytes:
        """Generate random node ID."""
        return hashlib.sha1(str(random.random()).encode()).digest()

    def _calculate_distance(self, id1: bytes, id2: bytes) -> int:
        """Calculate XOR distance between two node IDs."""
        if len(id1) != len(id2):
            raise ValueError("Node IDs must have same length")

        distance = 0
        for i in range(len(id1)):
            distance ^= id1[i] ^ id2[i]

        return distance

    def _get_bucket_index(self, node_id: bytes) -> int:
        """Get bucket index for node ID."""
        distance = self._calculate_distance(self.node_id, node_id)
        return distance.bit_length() - 1 if distance > 0 else 0

    def add_node(self, node: DHTNode) -> None:
        """Add node to routing table."""
        if node.node_id == self.node_id:
            return  # Don't add self

        bucket_index = self._get_bucket_index(node.node_id)
        if bucket_index >= len(self.buckets):
            bucket_index = len(self.buckets) - 1

        # Add to bucket
        self.buckets[bucket_index].add(node)
        self.routing_table[node.node_id] = node

        # Emit event for new node
        emit_event(Event(
            event_type=EventType.DHT_NODE_ADDED.value,
            data={
                "node_id": node.node_id.hex(),
                "ip": node.ip,
                "port": node.port,
                "bucket_index": bucket_index,
                "timestamp": time.time(),
            },
        ))

    def remove_node(self, node_id: bytes) -> None:
        """Remove node from routing table."""
        if node_id in self.routing_table:
            node = self.routing_table[node_id]
            bucket_index = self._get_bucket_index(node_id)

            if bucket_index < len(self.buckets):
                self.buckets[bucket_index].discard(node)

            del self.routing_table[node_id]

            # Emit event for node removal
            emit_event(Event(
                event_type=EventType.DHT_NODE_REMOVED.value,
                data={
                    "node_id": node_id.hex(),
                    "timestamp": time.time(),
                },
            ))

    def find_closest_nodes(self, target_id: bytes, count: int = 8) -> List[DHTNode]:
        """Find closest nodes to target ID."""
        all_nodes = list(self.routing_table.values())
        all_nodes.sort(key=lambda n: self._calculate_distance(n.node_id, target_id))
        return all_nodes[:count]

    def encode_ping_query(self, transaction_id: bytes) -> bytes:
        """Encode PING query."""
        query_data = {
            "t": transaction_id.decode(),
            "y": "q",
            "q": "ping",
            "a": {"id": self.node_id.hex()},
        }

        return self._encode_dht_message(query_data)

    def encode_find_node_query(self, transaction_id: bytes, target_id: bytes) -> bytes:
        """Encode FIND_NODE query."""
        query_data = {
            "t": transaction_id.decode(),
            "y": "q",
            "q": "find_node",
            "a": {
                "id": self.node_id.hex(),
                "target": target_id.hex(),
            },
        }

        return self._encode_dht_message(query_data)

    def encode_get_peers_query(self, transaction_id: bytes, info_hash: bytes) -> bytes:
        """Encode GET_PEERS query."""
        query_data = {
            "t": transaction_id.decode(),
            "y": "q",
            "q": "get_peers",
            "a": {
                "id": self.node_id.hex(),
                "info_hash": info_hash.hex(),
            },
        }

        return self._encode_dht_message(query_data)

    def encode_announce_peer_query(self, transaction_id: bytes, info_hash: bytes, port: int, token: str) -> bytes:
        """Encode ANNOUNCE_PEER query."""
        query_data = {
            "t": transaction_id.decode(),
            "y": "q",
            "q": "announce_peer",
            "a": {
                "id": self.node_id.hex(),
                "info_hash": info_hash.hex(),
                "port": port,
                "token": token,
            },
        }

        return self._encode_dht_message(query_data)

    def encode_ping_response(self, transaction_id: bytes, node_id: bytes) -> bytes:
        """Encode PING response."""
        response_data = {
            "t": transaction_id.decode(),
            "y": "r",
            "r": {"id": node_id.hex()},
        }

        return self._encode_dht_message(response_data)

    def encode_find_node_response(self, transaction_id: bytes, nodes: List[DHTNode]) -> bytes:
        """Encode FIND_NODE response."""
        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "id": node.node_id.hex(),
                "ip": node.ip,
                "port": node.port,
            })

        response_data = {
            "t": transaction_id.decode(),
            "y": "r",
            "r": {
                "id": self.node_id.hex(),
                "nodes": nodes_data,
            },
        }

        return self._encode_dht_message(response_data)

    def encode_get_peers_response(self, transaction_id: bytes, peers: List[PeerInfo], nodes: List[DHTNode], token: str) -> bytes:
        """Encode GET_PEERS response."""
        peers_data = []
        for peer in peers:
            peers_data.append({
                "ip": peer.ip,
                "port": peer.port,
            })

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "id": node.node_id.hex(),
                "ip": node.ip,
                "port": node.port,
            })

        response_data = {
            "t": transaction_id.decode(),
            "y": "r",
            "r": {
                "id": self.node_id.hex(),
                "peers": peers_data,
                "nodes": nodes_data,
                "token": token,
            },
        }

        return self._encode_dht_message(response_data)

    def _encode_dht_message(self, data: Dict[str, Any]) -> bytes:
        """Encode DHT message to bencoded format."""
        import bencodepy
        return bencodepy.encode(data)

    def _decode_dht_message(self, data: bytes) -> Dict[str, Any]:
        """Decode DHT message from bencoded format."""
        import bencodepy
        return bencodepy.decode(data)

    async def handle_dht_message(self, peer_ip: str, peer_port: int, data: bytes) -> Optional[bytes]:
        """Handle incoming DHT message."""
        try:
            message = self._decode_dht_message(data)

            if message.get("y") == "q":  # Query
                return await self._handle_query(peer_ip, peer_port, message)
            if message.get("y") == "r":  # Response
                await self._handle_response(peer_ip, peer_port, message)
            elif message.get("y") == "e":  # Error
                await self._handle_error(peer_ip, peer_port, message)

        except Exception as e:
            # Emit event for DHT error
            await emit_event(Event(
                event_type=EventType.DHT_ERROR.value,
                data={
                    "peer_ip": peer_ip,
                    "peer_port": peer_port,
                    "error": str(e),
                    "timestamp": time.time(),
                },
            ))

        return None

    async def _handle_query(self, peer_ip: str, peer_port: int, message: Dict[str, Any]) -> bytes:
        """Handle DHT query."""
        query_type = message.get("q")
        transaction_id = message.get("t", "").encode()

        if query_type == "ping":
            return self.encode_ping_response(transaction_id, self.node_id)
        if query_type == "find_node":
            target_id = bytes.fromhex(message.get("a", {}).get("target", ""))
            closest_nodes = self.find_closest_nodes(target_id)
            return self.encode_find_node_response(transaction_id, closest_nodes)
        if query_type == "get_peers":
            info_hash = bytes.fromhex(message.get("a", {}).get("info_hash", ""))
            # TODO: Implement peer storage and retrieval
            return self.encode_get_peers_response(transaction_id, [], [], "")
        if query_type == "announce_peer":
            # TODO: Implement peer announcement
            return self.encode_ping_response(transaction_id, self.node_id)

        return b""

    async def _handle_response(self, peer_ip: str, peer_port: int, message: Dict[str, Any]) -> None:
        """Handle DHT response."""
        # TODO: Implement response handling

    async def _handle_error(self, peer_ip: str, peer_port: int, message: Dict[str, Any]) -> None:
        """Handle DHT error."""
        error_code = message.get("e", [0, "Unknown error"])
        error_message = error_code[1] if len(error_code) > 1 else "Unknown error"

        await emit_event(Event(
            event_type=EventType.DHT_ERROR.value,
            data={
                "peer_ip": peer_ip,
                "peer_port": peer_port,
                "error_code": error_code[0],
                "error_message": error_message,
                "timestamp": time.time(),
            },
        ))

    def get_routing_table_size(self) -> int:
        """Get routing table size."""
        return len(self.routing_table)

    def get_bucket_sizes(self) -> List[int]:
        """Get bucket sizes."""
        return [len(bucket) for bucket in self.buckets]

    def get_node_statistics(self) -> Dict[str, Any]:
        """Get node statistics."""
        return {
            "total_nodes": len(self.routing_table),
            "bucket_sizes": self.get_bucket_sizes(),
            "node_id": self.node_id.hex(),
        }


# Import time module for timestamps
import time
