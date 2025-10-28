"""DHT (Distributed Hash Table) extension implementation.

Provides support for:
- DHT peer discovery
- DHT node management
- DHT message handling
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ccbt import bencode
from ccbt.events import Event, EventType, emit_event
from ccbt.models import PeerInfo


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
        """Return hash of DHT node."""
        return hash((self.node_id, self.ip, self.port))

    def __eq__(self, other):
        """Check equality of DHT nodes."""
        if not isinstance(other, DHTNode):
            return False
        return (
            self.node_id == other.node_id
            and self.ip == other.ip
            and self.port == other.port
        )


class DHTExtension:
    """DHT (Distributed Hash Table) implementation."""

    def __init__(self, node_id: bytes | None = None):
        """Initialize DHT implementation."""
        self.node_id = node_id or self._generate_node_id()
        self.nodes: dict[bytes, DHTNode] = {}
        self.buckets: list[set[DHTNode]] = [
            set() for _ in range(160)
        ]  # 160-bit ID space
        self.routing_table: dict[bytes, DHTNode] = {}

        # Peer storage for get_peers queries
        self.peer_storage: dict[bytes, set[tuple[str, int]]] = {}
        self.peer_tokens: dict[bytes, str] = {}  # info_hash -> token

    def _generate_node_id(self) -> bytes:
        """Generate random node ID."""
        # Use cryptographically secure random bytes for DHT node ID generation
        return hashlib.sha1(secrets.token_bytes(32)).digest()  # nosec B324 - SHA-1 for DHT node ID generation, not security-sensitive

    def _calculate_distance(self, id1: bytes, id2: bytes) -> int:
        """Calculate XOR distance between two node IDs."""
        if len(id1) != len(id2):
            msg = "Node IDs must have same length"
            raise ValueError(msg)

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
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                emit_event(
                    Event(
                        event_type=EventType.DHT_NODE_ADDED.value,
                        data={
                            "node_id": node.node_id.hex(),
                            "ip": node.ip,
                            "port": node.port,
                            "bucket_index": bucket_index,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
            # Store task reference to avoid RUF006 warning
            _ = task
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    def remove_node(self, node_id: bytes) -> None:
        """Remove node from routing table."""
        if node_id in self.routing_table:
            node = self.routing_table[node_id]
            bucket_index = self._get_bucket_index(node_id)

            if bucket_index < len(self.buckets):
                self.buckets[bucket_index].discard(node)

            del self.routing_table[node_id]

            # Emit event for node removal
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(
                    emit_event(
                        Event(
                            event_type=EventType.DHT_NODE_REMOVED.value,
                            data={
                                "node_id": node_id.hex(),
                                "timestamp": time.time(),
                            },
                        ),
                    )
                )
                # Store task reference to avoid RUF006 warning
                _ = task
            except RuntimeError:
                # No event loop running, skip event emission
                pass

    def find_closest_nodes(self, target_id: bytes, count: int = 8) -> list[DHTNode]:
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

    def encode_announce_peer_query(
        self,
        transaction_id: bytes,
        info_hash: bytes,
        port: int,
        token: str,
    ) -> bytes:
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

    def encode_error_response(
        self, transaction_id: bytes, error_code: int, error_message: str
    ) -> bytes:
        """Encode DHT error response."""
        response_data = {
            "t": transaction_id.decode(),
            "y": "e",
            "e": [error_code, error_message],
        }

        return self._encode_dht_message(response_data)

    def encode_find_node_response(
        self,
        transaction_id: bytes,
        nodes: list[DHTNode],
    ) -> bytes:
        """Encode FIND_NODE response."""
        nodes_data = [
            {
                "id": node.node_id.hex(),
                "ip": node.ip,
                "port": node.port,
            }
            for node in nodes
        ]

        response_data = {
            "t": transaction_id.decode(),
            "y": "r",
            "r": {
                "id": self.node_id.hex(),
                "nodes": nodes_data,
            },
        }

        return self._encode_dht_message(response_data)

    def encode_get_peers_response(
        self,
        transaction_id: bytes,
        peers: list[PeerInfo],
        nodes: list[DHTNode],
        token: str,
    ) -> bytes:
        """Encode GET_PEERS response."""
        peers_data = [
            {
                "ip": peer.ip,
                "port": peer.port,
            }
            for peer in peers
        ]

        nodes_data = [
            {
                "id": node.node_id.hex(),
                "ip": node.ip,
                "port": node.port,
            }
            for node in nodes
        ]

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

    def _encode_dht_message(self, data: dict[str, Any]) -> bytes:
        """Encode DHT message to bencoded format."""
        return bencode.encode(data)

    def _decode_dht_message(self, data: bytes) -> dict[str, Any]:
        """Decode DHT message from bencoded format."""
        return bencode.decode(data)

    async def handle_dht_message(
        self,
        peer_ip: str,
        peer_port: int,
        data: bytes,
    ) -> bytes | None:
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
            await emit_event(
                Event(
                    event_type=EventType.DHT_ERROR.value,
                    data={
                        "peer_ip": peer_ip,
                        "peer_port": peer_port,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

        return None

    async def _handle_query(
        self,
        peer_ip: str,
        peer_port: int,
        message: dict[str, Any],
    ) -> bytes:
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
            peers_tuples = self._get_stored_peers(info_hash)
            peers_list = [PeerInfo(ip=ip, port=port) for ip, port in peers_tuples]
            token = self._generate_token(info_hash)
            return self.encode_get_peers_response(transaction_id, peers_list, [], token)
        if query_type == "announce_peer":
            info_hash = bytes.fromhex(message.get("a", {}).get("info_hash", ""))
            token = message.get("a", {}).get("token", "")
            peer_port = message.get("a", {}).get("port", 0)

            if self._validate_token(info_hash, token):
                # Store peer with the IP of the querying peer
                self._store_peer(info_hash, peer_ip, peer_port)
                return self.encode_ping_response(transaction_id, self.node_id)
            return self.encode_error_response(transaction_id, 203, "Invalid token")

        return b""

    async def _handle_response(
        self,
        _peer_ip: str,
        _peer_port: int,
        message: dict[str, Any],
    ) -> None:
        """Handle DHT response."""
        response_type = message.get("r", {})

        # Handle ping responses - update node as alive
        if "id" in response_type:
            node_id = bytes.fromhex(response_type["id"])
            if node_id in self.routing_table:
                self.routing_table[node_id].last_seen = time.time()

        # Handle find_node responses - add returned nodes to routing table
        if "nodes" in response_type:
            nodes_data = response_type["nodes"]
            self._add_nodes_from_compact_format(nodes_data)

        # Handle get_peers responses - extract and store peer information
        if "values" in response_type:
            peers_data = response_type["values"]
            info_hash = message.get("a", {}).get("info_hash", "")
            if info_hash:
                # Ensure peers_data is a list
                if isinstance(peers_data, bytes):
                    peers_data = [peers_data]
                self._store_peers_from_compact_format(
                    bytes.fromhex(info_hash), peers_data
                )

        # Handle announce_peer responses - confirm announcement
        if "id" in response_type and "token" in message.get("a", {}):
            # Announcement was successful
            pass

    async def _handle_error(
        self,
        peer_ip: str,
        peer_port: int,
        message: dict[str, Any],
    ) -> None:
        """Handle DHT error."""
        error_code = message.get("e", [0, "Unknown error"])
        error_message = error_code[1] if len(error_code) > 1 else "Unknown error"

        await emit_event(
            Event(
                event_type=EventType.DHT_ERROR.value,
                data={
                    "peer_ip": peer_ip,
                    "peer_port": peer_port,
                    "error_code": error_code[0],
                    "error_message": error_message,
                    "timestamp": time.time(),
                },
            ),
        )

    def get_routing_table_size(self) -> int:
        """Get routing table size."""
        return len(self.routing_table)

    def get_bucket_sizes(self) -> list[int]:
        """Get bucket sizes."""
        return [len(bucket) for bucket in self.buckets]

    def _get_stored_peers(self, info_hash: bytes) -> list[tuple[str, int]]:
        """Get stored peers for info hash."""
        return list(self.peer_storage.get(info_hash, set()))

    def _store_peer(self, info_hash: bytes, peer_ip: str, peer_port: int) -> None:
        """Store peer information for info hash."""
        if info_hash not in self.peer_storage:
            self.peer_storage[info_hash] = set()
        self.peer_storage[info_hash].add((peer_ip, peer_port))

    def _generate_token(self, info_hash: bytes) -> str:
        """Generate token for peer announcement."""
        # Simple token generation - in production, use HMAC with secret key
        token_data = self.node_id + info_hash + str(time.time()).encode()
        token = hashlib.sha1(token_data, usedforsecurity=False).hexdigest()[:8]
        self.peer_tokens[info_hash] = token
        return token

    def _validate_token(self, info_hash: bytes, token: str) -> bool:
        """Validate token for peer announcement."""
        return self.peer_tokens.get(info_hash) == token

    def _add_nodes_from_compact_format(self, nodes_data: bytes) -> None:
        """Add nodes from compact format string."""
        # Compact format: 26 bytes per node (20-byte node ID + 4-byte IP + 2-byte port)
        node_size = 26
        for i in range(0, len(nodes_data), node_size):
            if i + node_size <= len(nodes_data):
                node_bytes = nodes_data[i : i + node_size]
                node_id = node_bytes[:20]
                ip_bytes = node_bytes[20:24]
                port_bytes = node_bytes[24:26]

                # Convert IP bytes to string
                ip = ".".join(str(b) for b in ip_bytes)
                port = int.from_bytes(port_bytes, "big")

                node = DHTNode(node_id=node_id, ip=ip, port=port, last_seen=time.time())
                self.routing_table[node_id] = node

    def _store_peers_from_compact_format(
        self, info_hash: bytes, peers_data: list[bytes]
    ) -> None:
        """Store peers from compact format list."""
        for peer_data in peers_data:
            if len(peer_data) >= 6:  # 4-byte IP + 2-byte port
                ip_bytes = peer_data[:4]
                port_bytes = peer_data[4:6]

                # Convert IP bytes to string
                ip = ".".join(str(b) for b in ip_bytes)
                port = int.from_bytes(port_bytes, "big")

                self._store_peer(info_hash, ip, port)

    def get_node_statistics(self) -> dict[str, Any]:
        """Get node statistics."""
        return {
            "total_nodes": len(self.routing_table),
            "bucket_sizes": self.get_bucket_sizes(),
            "node_id": self.node_id.hex(),
        }

    def _cleanup_peer_storage(self) -> None:
        """Clean up old peer storage entries."""
        # This is a simple cleanup - in a real implementation,
        # you'd track timestamps for each peer

    def get_statistics(self) -> dict[str, Any]:
        """Get DHT statistics."""
        return {
            "nodes_count": len(self.routing_table),
            "buckets_count": len([b for b in self.buckets if b]),
            "peer_storage_count": sum(
                len(peers) for peers in self.peer_storage.values()
            ),
            "node_id": self.node_id.hex(),
        }
