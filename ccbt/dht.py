"""Enhanced DHT (BEP 5) client with full Kademlia implementation.

Provides high-performance peer discovery using Kademlia routing table,
iterative lookups, token verification, and continuous refresh.
"""

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .bencode import BencodeDecoder, BencodeEncoder
from .config import get_config

DEFAULT_BOOTSTRAP = [
    ("router.bittorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("router.utorrent.com", 6881),
    ("dht.libtorrent.org", 25401),
]


@dataclass
class DHTNode:
    """Represents a DHT node."""
    node_id: bytes
    ip: str
    port: int
    last_seen: float = field(default_factory=time.time)
    last_ping: float = 0.0
    is_good: bool = True
    failed_queries: int = 0
    successful_queries: int = 0

    def __hash__(self):
        return hash((self.node_id, self.ip, self.port))

    def __eq__(self, other):
        if not isinstance(other, DHTNode):
            return False
        return (self.node_id == other.node_id and
                self.ip == other.ip and
                self.port == other.port)


@dataclass
class DHTToken:
    """DHT token for announce_peer verification."""
    token: bytes
    info_hash: bytes
    created_time: float = field(default_factory=time.time)
    expires_time: float = field(default_factory=lambda: time.time() + 900.0)  # 15 minutes


class KademliaRoutingTable:
    """Kademlia routing table with k-buckets."""

    def __init__(self, node_id: bytes, k: int = 8):
        self.node_id = node_id
        self.k = k
        self.buckets: List[List[DHTNode]] = [[] for _ in range(160)]  # 160-bit keyspace
        self.nodes: Dict[bytes, DHTNode] = {}

    def _distance(self, node_id1: bytes, node_id2: bytes) -> int:
        """Calculate XOR distance between two node IDs."""
        if len(node_id1) != len(node_id2):
            return 0

        distance = 0
        for i in range(len(node_id1)):
            xor = node_id1[i] ^ node_id2[i]
            if xor == 0:
                distance += 8
            else:
                distance += 8 - (xor.bit_length() - 1)
                break

        return distance

    def _bucket_index(self, node_id: bytes) -> int:
        """Get bucket index for a node ID."""
        distance = self._distance(self.node_id, node_id)
        return min(distance, 159)

    def add_node(self, node: DHTNode) -> bool:
        """Add a node to the routing table."""
        if node.node_id == self.node_id:
            return False

        bucket_idx = self._bucket_index(node.node_id)
        bucket = self.buckets[bucket_idx]

        # Update existing node
        if node.node_id in self.nodes:
            existing_node = self.nodes[node.node_id]
            existing_node.ip = node.ip
            existing_node.port = node.port
            existing_node.last_seen = node.last_seen
            existing_node.is_good = node.is_good
            return True

        # Add new node if bucket has space
        if len(bucket) < self.k:
            bucket.append(node)
            self.nodes[node.node_id] = node
            return True

        # Replace bad node if available
        for i, existing_node in enumerate(bucket):
            if not existing_node.is_good:
                bucket[i] = node
                self.nodes[node.node_id] = node
                return True

        # Bucket is full of good nodes, can't add
        return False

    def get_closest_nodes(self, target_id: bytes, count: int = 8) -> List[DHTNode]:
        """Get closest nodes to target ID."""
        all_nodes = list(self.nodes.values())
        all_nodes.sort(key=lambda n: self._distance(n.node_id, target_id))
        return all_nodes[:count]

    def remove_node(self, node_id: bytes) -> None:
        """Remove a node from the routing table."""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            bucket_idx = self._bucket_index(node_id)
            bucket = self.buckets[bucket_idx]

            if node in bucket:
                bucket.remove(node)
            del self.nodes[node_id]

    def mark_node_bad(self, node_id: bytes) -> None:
        """Mark a node as bad."""
        if node_id in self.nodes:
            self.nodes[node_id].is_good = False
            self.nodes[node_id].failed_queries += 1

    def mark_node_good(self, node_id: bytes) -> None:
        """Mark a node as good."""
        if node_id in self.nodes:
            self.nodes[node_id].is_good = True
            self.nodes[node_id].successful_queries += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get routing table statistics."""
        total_nodes = len(self.nodes)
        good_nodes = sum(1 for n in self.nodes.values() if n.is_good)
        non_empty_buckets = sum(1 for bucket in self.buckets if bucket)

        return {
            "total_nodes": total_nodes,
            "good_nodes": good_nodes,
            "non_empty_buckets": non_empty_buckets,
            "buckets": [len(bucket) for bucket in self.buckets if bucket],
        }


class AsyncDHTClient:
    """High-performance async DHT client with full Kademlia support."""

    def __init__(self, bind_ip: str = "0.0.0.0", bind_port: int = 0):
        """Initialize DHT client."""
        self.config = get_config()

        # Node identity
        self.node_id = self._generate_node_id()

        # Network
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.socket: Optional[asyncio.DatagramProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None

        # Routing table
        self.routing_table = KademliaRoutingTable(self.node_id)

        # Bootstrap nodes
        self.bootstrap_nodes = DEFAULT_BOOTSTRAP.copy()

        # Pending queries
        self.pending_queries: Dict[bytes, asyncio.Future] = {}
        self.query_timeout = 5.0

        # Tokens for announce_peer
        self.tokens: Dict[bytes, DHTToken] = {}
        self.token_secret = os.urandom(20)

        # Background tasks
        self._refresh_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Callbacks
        self.peer_callbacks: List[Callable[[List[Tuple[str, int]]], None]] = []

        self.logger = logging.getLogger(__name__)

    def _generate_node_id(self) -> bytes:
        """Generate a random node ID."""
        # Generate ID that's not too close to our own
        while True:
            node_id = os.urandom(20)
            # Ensure it's not all zeros or all ones
            if node_id != b"\x00" * 20 and node_id != b"\xff" * 20:
                return node_id

    async def start(self) -> None:
        """Start the DHT client."""
        # Create UDP socket
        loop = asyncio.get_event_loop()
        self.transport, self.socket = await loop.create_datagram_endpoint(
            lambda: DHTProtocol(self),
            local_addr=(self.bind_ip, self.bind_port),
        )

        # Start background tasks
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Bootstrap
        await self._bootstrap()

        self.logger.info(f"DHT client started on {self.bind_ip}:{self.bind_port}")

    async def stop(self) -> None:
        """Stop the DHT client."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self.transport:
            self.transport.close()

        self.logger.info("DHT client stopped")

    async def _bootstrap(self) -> None:
        """Bootstrap the DHT by finding initial nodes."""
        self.logger.info("Bootstrapping DHT...")

        # Try to find nodes from bootstrap servers
        for host, port in self.bootstrap_nodes:
            try:
                addr = (socket.gethostbyname(host), port)
                await self._find_nodes(addr, self.node_id)
            except Exception as e:
                self.logger.debug(f"Bootstrap failed for {host}:{port}: {e}")

        # If we still don't have enough nodes, try to find more
        if len(self.routing_table.nodes) < 8:
            await self._refresh_routing_table()

    async def _find_nodes(self, addr: Tuple[str, int], target_id: bytes) -> List[DHTNode]:
        """Find nodes close to target ID."""
        try:
            # Send find_node query
            response = await self._send_query(addr, "find_node", {
                b"id": self.node_id,
                b"target": target_id,
            })

            if not response or response.get(b"y") != b"r":
                return []

            # Parse nodes from response
            nodes = []
            r = response.get(b"r", {})
            nodes_data = r.get(b"nodes", b"")

            # Parse compact node format (26 bytes per node: 20 ID + 4 IP + 2 port)
            for i in range(0, len(nodes_data), 26):
                if i + 26 <= len(nodes_data):
                    node_data = nodes_data[i:i+26]
                    node_id = node_data[:20]
                    ip = ".".join(str(b) for b in node_data[20:24])
                    port = int.from_bytes(node_data[24:26], "big")

                    node = DHTNode(node_id, ip, port)
                    nodes.append(node)

            # Add nodes to routing table
            for node in nodes:
                self.routing_table.add_node(node)

            return nodes

        except Exception as e:
            self.logger.debug(f"find_node failed for {addr}: {e}")
            return []

    async def get_peers(self, info_hash: bytes, max_peers: int = 50) -> List[Tuple[str, int]]:
        """Get peers for an info hash using iterative lookup.
        
        Args:
            info_hash: Torrent info hash
            max_peers: Maximum number of peers to return
            
        Returns:
            List of (ip, port) tuples
        """
        peers = []
        queried_nodes = set()

        # Get closest nodes to info hash
        closest_nodes = self.routing_table.get_closest_nodes(info_hash, 8)

        # Query nodes iteratively
        for node in closest_nodes:
            if node.node_id in queried_nodes:
                continue

            queried_nodes.add(node.node_id)

            try:
                # Send get_peers query
                response = await self._send_query((node.ip, node.port), "get_peers", {
                    b"id": self.node_id,
                    b"info_hash": info_hash,
                })

                if not response or response.get(b"y") != b"r":
                    continue

                r = response.get(b"r", {})

                # Check for peers (values)
                values = r.get(b"values", [])
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, bytes) and len(value) == 6:
                            ip = ".".join(str(b) for b in value[:4])
                            port = int.from_bytes(value[4:6], "big")
                            peers.append((ip, port))

                            if len(peers) >= max_peers:
                                break

                # Check for nodes to query
                nodes_data = r.get(b"nodes", b"")
                if nodes_data:
                    # Parse and add new nodes
                    for i in range(0, len(nodes_data), 26):
                        if i + 26 <= len(nodes_data):
                            node_data = nodes_data[i:i+26]
                            node_id = node_data[:20]
                            ip = ".".join(str(b) for b in node_data[20:24])
                            port = int.from_bytes(node_data[24:26], "big")

                            new_node = DHTNode(node_id, ip, port)
                            self.routing_table.add_node(new_node)

                # Store token for announce_peer
                token = r.get(b"token")
                if token:
                    self.tokens[info_hash] = DHTToken(token, info_hash)

                # Mark node as good
                self.routing_table.mark_node_good(node.node_id)

            except Exception as e:
                self.logger.debug(f"get_peers failed for {node.ip}:{node.port}: {e}")
                self.routing_table.mark_node_bad(node.node_id)

        # Notify callbacks
        if peers:
            for callback in self.peer_callbacks:
                try:
                    callback(peers)
                except Exception as e:
                    self.logger.error(f"Peer callback error: {e}")

        return peers

    async def announce_peer(self, info_hash: bytes, port: int) -> bool:
        """Announce our peer to the DHT.
        
        Args:
            info_hash: Torrent info hash
            port: Our port
            
        Returns:
            True if announcement was successful
        """
        # Get token for this info hash
        if info_hash not in self.tokens:
            # Try to get token by doing a get_peers query
            await self.get_peers(info_hash, 1)

        if info_hash not in self.tokens:
            self.logger.debug(f"No token available for {info_hash.hex()}")
            return False

        token = self.tokens[info_hash]

        # Check if token is still valid
        if time.time() > token.expires_time:
            del self.tokens[info_hash]
            return False

        # Find closest nodes to announce to
        closest_nodes = self.routing_table.get_closest_nodes(info_hash, 8)

        success_count = 0
        for node in closest_nodes:
            try:
                response = await self._send_query((node.ip, node.port), "announce_peer", {
                    b"id": self.node_id,
                    b"info_hash": info_hash,
                    b"port": port,
                    b"token": token.token,
                })

                if response and response.get(b"y") == b"r":
                    success_count += 1
                    self.routing_table.mark_node_good(node.node_id)
                else:
                    self.routing_table.mark_node_bad(node.node_id)

            except Exception as e:
                self.logger.debug(f"announce_peer failed for {node.ip}:{node.port}: {e}")
                self.routing_table.mark_node_bad(node.node_id)

        return success_count > 0

    async def _send_query(self, addr: Tuple[str, int], query: str, args: Dict[bytes, Any]) -> Optional[Dict[bytes, Any]]:
        """Send a DHT query and wait for response."""
        # Generate transaction ID
        tid = os.urandom(2)

        # Build query message
        message = {
            b"t": tid,
            b"y": b"q",
            b"q": query.encode("ascii"),
            b"a": args,
        }

        # Send message
        data = BencodeEncoder().encode(message)
        self.transport.sendto(data, addr)

        # Wait for response
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(tid),
                timeout=self.query_timeout,
            )
            return response
        except asyncio.TimeoutError:
            self.logger.debug(f"Query timeout for {addr}")
            return None

    async def _wait_for_response(self, tid: bytes) -> Dict[bytes, Any]:
        """Wait for response with given transaction ID."""
        future = asyncio.Future()
        self.pending_queries[tid] = future

        try:
            response = await future
            return response
        finally:
            self.pending_queries.pop(tid, None)

    def handle_response(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming DHT response."""
        try:
            # Decode message
            decoder = BencodeDecoder(data)
            message = decoder.decode()

            # Check if it's a response
            if message.get(b"y") != b"r":
                return

            # Get transaction ID
            tid = message.get(b"t")
            if not tid or tid not in self.pending_queries:
                return

            # Set response
            future = self.pending_queries[tid]
            if not future.done():
                future.set_result(message)

        except Exception as e:
            self.logger.debug(f"Failed to parse DHT response: {e}")

    async def _refresh_loop(self) -> None:
        """Background task to refresh routing table."""
        while True:
            try:
                await asyncio.sleep(600.0)  # Refresh every 10 minutes
                await self._refresh_routing_table()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in refresh loop: {e}")

    async def _refresh_routing_table(self) -> None:
        """Refresh routing table by finding nodes."""
        # Generate random target IDs to find nodes
        for _ in range(8):
            target_id = os.urandom(20)
            closest_nodes = self.routing_table.get_closest_nodes(target_id, 8)

            for node in closest_nodes:
                await self._find_nodes((node.ip, node.port), target_id)

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old data."""
        while True:
            try:
                await asyncio.sleep(300.0)  # Clean every 5 minutes
                await self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_old_data(self) -> None:
        """Clean up old tokens and bad nodes."""
        current_time = time.time()

        # Clean up expired tokens
        expired_tokens = [
            info_hash for info_hash, token in self.tokens.items()
            if current_time > token.expires_time
        ]
        for info_hash in expired_tokens:
            del self.tokens[info_hash]

        # Remove bad nodes
        bad_nodes = [
            node_id for node_id, node in self.routing_table.nodes.items()
            if not node.is_good and node.failed_queries >= 3
        ]
        for node_id in bad_nodes:
            self.routing_table.remove_node(node_id)

    def add_peer_callback(self, callback: Callable[[List[Tuple[str, int]]], None]) -> None:
        """Add callback for new peers."""
        self.peer_callbacks.append(callback)

    def remove_peer_callback(self, callback: Callable[[List[Tuple[str, int]]], None]) -> None:
        """Remove peer callback."""
        if callback in self.peer_callbacks:
            self.peer_callbacks.remove(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get DHT statistics."""
        return {
            "node_id": self.node_id.hex(),
            "routing_table": self.routing_table.get_stats(),
            "tokens": len(self.tokens),
            "pending_queries": len(self.pending_queries),
        }


class DHTProtocol(asyncio.DatagramProtocol):
    """DHT protocol handler."""

    def __init__(self, client: AsyncDHTClient):
        self.client = client

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        self.client.handle_response(data, addr)

    def error_received(self, exc: Exception) -> None:
        """Handle UDP error."""
        self.client.logger.debug(f"DHT error: {exc}")


# Global DHT client instance
_dht_client: Optional[AsyncDHTClient] = None


def get_dht_client() -> AsyncDHTClient:
    """Get the global DHT client."""
    global _dht_client
    if _dht_client is None:
        _dht_client = AsyncDHTClient()
    return _dht_client


async def init_dht() -> AsyncDHTClient:
    """Initialize global DHT client."""
    global _dht_client
    _dht_client = AsyncDHTClient()
    await _dht_client.start()
    return _dht_client


async def shutdown_dht() -> None:
    """Shutdown global DHT client."""
    global _dht_client
    if _dht_client:
        await _dht_client.stop()
        _dht_client = None


