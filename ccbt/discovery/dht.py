"""Enhanced DHT (BEP 5) client with full Kademlia implementation.

from __future__ import annotations

Provides high-performance peer discovery using Kademlia routing table,
iterative lookups, token verification, and continuous refresh.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ccbt.config.config import get_config
from ccbt.core.bencode import BencodeDecoder, BencodeEncoder

# Error message constants
_ERROR_DHT_TRANSPORT_NOT_INITIALIZED = "DHT transport is not initialized"

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
    # IPv6 support
    ipv6: str | None = None
    port6: int | None = None
    has_ipv6: bool = False
    additional_addresses: list[tuple[str, int]] = field(default_factory=list)
    
    # Quality metrics for optimization
    response_times: list[float] = field(default_factory=list)  # List of recent response times
    average_response_time: float = 0.0  # Average response time in seconds
    success_rate: float = 1.0  # Success rate (0.0-1.0)
    quality_score: float = 1.0  # Overall quality score (0.0-1.0)
    last_response_time: float = 0.0  # Last measured response time
    query_count: int = 0  # Total queries made to this node

    def __hash__(self):
        """Return hash of the node."""
        return hash((self.node_id, self.ip, self.port))

    def __eq__(self, other):
        """Check equality with another node."""
        if not isinstance(other, DHTNode):
            return False
        return (
            self.node_id == other.node_id
            and self.ip == other.ip
            and self.port == other.port
        )

    def get_all_addresses(self) -> list[tuple[str, int]]:
        """Get all addresses (IPv4 and IPv6) for this node.
        
        Returns:
            List of (ip, port) tuples

        """
        addresses = [(self.ip, self.port)]
        if self.has_ipv6 and self.ipv6 and self.port6:
            addresses.append((self.ipv6, self.port6))
        addresses.extend(self.additional_addresses)
        return addresses

    def add_address(self, ip: str, port: int) -> None:
        """Add an additional address to this node.
        
        Args:
            ip: IP address
            port: Port number

        """
        addr = (ip, port)
        if addr not in self.additional_addresses:
            self.additional_addresses.append(addr)


@dataclass
class DHTToken:
    """DHT token for announce_peer verification."""

    token: bytes
    info_hash: bytes
    created_time: float = field(default_factory=time.time)
    expires_time: float = field(
        default_factory=lambda: time.time() + 900.0,
    )  # 15 minutes


class KademliaRoutingTable:
    """Kademlia routing table with k-buckets."""

    def __init__(self, node_id: bytes, k: int = 8):
        """Initialize Kademlia routing table.

        Args:
            node_id: This node's ID
            k: Bucket size (default 8)

        """
        self.node_id = node_id
        self.k = k
        self.buckets: list[list[DHTNode]] = [[] for _ in range(160)]  # 160-bit keyspace
        self.nodes: dict[bytes, DHTNode] = {}

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

    def _assess_node_reachability(self, node: DHTNode) -> float:
        """Assess node reachability using socket address validation.
        
        Args:
            node: DHT node to assess
            
        Returns:
            Reachability score (0.0-1.0), higher = more reachable
        """
        try:
            # Validate IP address format
            import ipaddress
            try:
                ipaddress.ip_address(node.ip)
            except ValueError:
                # Invalid IP address
                return 0.0
            
            # Validate port range
            if not (1 <= node.port <= 65535):
                return 0.0
            
            # Check if node has been seen recently (more recent = more reachable)
            current_time = time.time()
            time_since_seen = current_time - node.last_seen
            
            # Nodes seen in last hour = 1.0, older = decreasing
            if time_since_seen < 3600:
                recency_score = 1.0
            elif time_since_seen < 86400:  # Last 24 hours
                recency_score = 0.7
            elif time_since_seen < 604800:  # Last week
                recency_score = 0.4
            else:
                recency_score = 0.1
            
            # Combine with quality score
            reachability_score = (recency_score * 0.6) + (node.quality_score * 0.4)
            
            return reachability_score
        except Exception:
            # On any error, assume moderate reachability
            return 0.5

    def get_closest_nodes(self, target_id: bytes, count: int = 8) -> list[DHTNode]:
        """Get closest nodes to target ID, prioritizing high-quality and reachable nodes.
        
        Nodes are sorted by:
        1. Distance to target (closer is better)
        2. Reachability score (higher is better)
        3. Quality score (higher is better)
        4. Good status (good nodes preferred)
        """
        all_nodes = list(self.nodes.values())
        
        # Calculate reachability for each node
        for node in all_nodes:
            if not hasattr(node, 'reachability_score'):
                node.reachability_score = self._assess_node_reachability(node)  # type: ignore[attr-defined]
        
        # Sort by distance first, then by reachability (descending), then by quality score (descending), then by good status
        all_nodes.sort(
            key=lambda n: (
                self._distance(n.node_id, target_id),
                -getattr(n, 'reachability_score', 0.5),  # Negative for descending order
                -n.quality_score,  # Negative for descending order
                not n.is_good,  # Good nodes first (False < True)
            )
        )
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

    def mark_node_bad(self, node_id: bytes, response_time: float | None = None) -> None:
        """Mark a node as bad and update quality metrics.
        
        Args:
            node_id: Node ID to mark as bad
            response_time: Optional response time for this failed query
        """
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.is_good = False
            node.failed_queries += 1
            node.query_count += 1
            
            # Update quality metrics if enabled
            if hasattr(self, 'config') and self.config.discovery.dht_quality_tracking_enabled:
                # Update success rate
                if node.query_count > 0:
                    node.success_rate = node.successful_queries / node.query_count
                
                # Update quality score (weighted by success rate and response time)
                if response_time is not None:
                    node.last_response_time = response_time
                    # Add to response times list (keep configured window size)
                    max_window = getattr(self.config.discovery, 'dht_quality_response_time_window', 10)
                    node.response_times.append(response_time)
                    if len(node.response_times) > max_window:
                        node.response_times.pop(0)
                    # Update average
                    if node.response_times:
                        node.average_response_time = sum(node.response_times) / len(node.response_times)
                
                # Quality score: success_rate * (1.0 / (1.0 + avg_response_time))
                # Faster nodes with higher success rates get better scores
                if node.average_response_time > 0:
                    time_factor = 1.0 / (1.0 + node.average_response_time)
                else:
                    time_factor = 1.0
                node.quality_score = node.success_rate * time_factor

    def mark_node_good(self, node_id: bytes, response_time: float | None = None) -> None:
        """Mark a node as good and update quality metrics.
        
        Args:
            node_id: Node ID to mark as good
            response_time: Optional response time for this successful query
        """
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.is_good = True
            node.successful_queries += 1
            node.query_count += 1
            
            # Update quality metrics if enabled
            if hasattr(self, 'config') and self.config.discovery.dht_quality_tracking_enabled:
                # Update success rate
                if node.query_count > 0:
                    node.success_rate = node.successful_queries / node.query_count
                
                # Update quality score (weighted by success rate and response time)
                if response_time is not None:
                    node.last_response_time = response_time
                    # Add to response times list (keep configured window size)
                    max_window = getattr(self.config.discovery, 'dht_quality_response_time_window', 10)
                    node.response_times.append(response_time)
                    if len(node.response_times) > max_window:
                        node.response_times.pop(0)
                    # Update average
                    if node.response_times:
                        node.average_response_time = sum(node.response_times) / len(node.response_times)
                
                # Quality score: success_rate * (1.0 / (1.0 + avg_response_time))
                # Faster nodes with higher success rates get better scores
                if node.average_response_time > 0:
                    time_factor = 1.0 / (1.0 + node.average_response_time)
                else:
                    time_factor = 1.0
                node.quality_score = node.success_rate * time_factor

    def get_stats(self) -> dict[str, Any]:
        """Get routing table statistics including quality metrics."""
        total_nodes = len(self.nodes)
        good_nodes = sum(1 for n in self.nodes.values() if n.is_good)
        non_empty_buckets = sum(1 for bucket in self.buckets if bucket)
        
        # Calculate quality metrics
        quality_scores = [n.quality_score for n in self.nodes.values() if n.query_count > 0]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        response_times = [n.average_response_time for n in self.nodes.values() if n.average_response_time > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        success_rates = [n.success_rate for n in self.nodes.values() if n.query_count > 0]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

        return {
            "total_nodes": total_nodes,
            "good_nodes": good_nodes,
            "non_empty_buckets": non_empty_buckets,
            "buckets": [len(bucket) for bucket in self.buckets if bucket],
            "avg_quality_score": avg_quality_score,
            "avg_response_time": avg_response_time,
            "avg_success_rate": avg_success_rate,
            "swarm_health": good_nodes / total_nodes if total_nodes > 0 else 0.0,
        }


class AsyncDHTClient:
    """High-performance async DHT client with full Kademlia support."""

    def __init__(self, bind_ip: str = "0.0.0.0", bind_port: int = 0):  # nosec B104
        """Initialize DHT client."""
        self.config = get_config()

        # Node identity
        self.node_id = self._generate_node_id()

        # Network
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.socket: asyncio.DatagramProtocol | None = None
        self.transport: asyncio.DatagramTransport | None = None

        # Routing table
        self.routing_table = KademliaRoutingTable(self.node_id)

        # Bootstrap nodes - CRITICAL FIX: Use config instead of hardcoded defaults
        # Parse bootstrap nodes from config (format: "host:port")
        # Initialize logger first for error reporting
        self.logger = logging.getLogger(__name__)
        
        config_bootstrap = self.config.discovery.dht_bootstrap_nodes if hasattr(self.config, 'discovery') else []
        if config_bootstrap:
            self.bootstrap_nodes = []
            for node_str in config_bootstrap:
                if ":" in node_str:
                    try:
                        host, port_str = node_str.rsplit(":", 1)
                        port = int(port_str)
                        self.bootstrap_nodes.append((host, port))
                    except (ValueError, IndexError):
                        self.logger.warning("Invalid bootstrap node format: %s (expected host:port)", node_str)
                else:
                    self.logger.warning("Invalid bootstrap node format: %s (expected host:port)", node_str)
            if not self.bootstrap_nodes:
                # Fallback to defaults if all config nodes are invalid
                self.logger.warning("No valid bootstrap nodes in config, using defaults")
                self.bootstrap_nodes = DEFAULT_BOOTSTRAP.copy()
        else:
            # No bootstrap nodes in config, use defaults
            self.bootstrap_nodes = DEFAULT_BOOTSTRAP.copy()
        
        # Bootstrap node performance tracking
        # Maps (host, port) -> performance metrics
        self.bootstrap_performance: dict[tuple[str, int], dict[str, Any]] = {}

        # Pending queries
        self.pending_queries: dict[bytes, asyncio.Future] = {}
        # Initialize query_timeout from config (default from network.dht_timeout)
        self.query_timeout = self.config.network.dht_timeout
        
        # Peer manager reference for health tracking (optional)
        self.peer_manager: Any | None = None
        
        # Adaptive timeout calculator (lazy initialization)
        self._timeout_calculator: Any | None = None

        # Tokens for announce_peer
        self.tokens: dict[bytes, DHTToken] = {}
        self.token_secret = os.urandom(20)

        # Background tasks
        self._refresh_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Callbacks with info_hash filtering
        # Maps info_hash -> list of callbacks, or None for global callbacks
        self.peer_callbacks: list[Callable[[list[tuple[str, int]]], None]] = []
        self.peer_callbacks_by_hash: dict[bytes, list[Callable[[list[tuple[str, int]]], None]]] = {}

        # BEP 27: Callback to check if a torrent is private
        self.is_private_torrent: Callable[[bytes], bool] | None = None

    def _generate_node_id(self) -> bytes:
        """Generate a random node ID."""
        # Generate ID that's not too close to our own
        while True:
            node_id = os.urandom(20)
            # Ensure it's not all zeros or all ones
            if node_id not in (b"\x00" * 20, b"\xff" * 20):
                return node_id

    async def start(self) -> None:
        """Start the DHT client."""
        # Create UDP socket
        loop = asyncio.get_event_loop()
        try:
            self.transport, self.socket = await loop.create_datagram_endpoint(
                lambda: DHTProtocol(self),
                local_addr=(self.bind_ip, self.bind_port),
            )
        except OSError as e:
            # CRITICAL FIX: Enhanced port conflict error handling
            error_code = e.errno if hasattr(e, "errno") else None
            import sys

            if sys.platform == "win32":
                if error_code == 10048:  # WSAEADDRINUSE
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(self.bind_port, "udp")
                    error_msg = (
                        f"DHT UDP port {self.bind_port} is already in use.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.exception("DHT UDP port %d is already in use", self.bind_port)
                    raise RuntimeError(error_msg) from e
                if error_code == 10013:  # WSAEACCES
                    error_msg = (
                        f"Permission denied binding to {self.bind_ip}:{self.bind_port}.\n"
                        f"Error: {e}\n\n"
                        f"Resolution: Run with administrator privileges or change the port."
                    )
                    self.logger.exception("Permission denied binding to %s:%d", self.bind_ip, self.bind_port)
                    raise RuntimeError(error_msg) from e
            elif error_code == 98:  # EADDRINUSE
                from ccbt.utils.port_checker import get_port_conflict_resolution

                resolution = get_port_conflict_resolution(self.bind_port, "udp")
                error_msg = (
                    f"DHT UDP port {self.bind_port} is already in use.\n"
                    f"Error: {e}\n\n"
                    f"{resolution}"
                )
                self.logger.exception("DHT UDP port %d is already in use", self.bind_port)
                raise RuntimeError(error_msg) from e
            elif error_code == 13:  # EACCES
                error_msg = (
                    f"Permission denied binding to {self.bind_ip}:{self.bind_port}.\n"
                    f"Error: {e}\n\n"
                    f"Resolution: Run with root privileges or change the port to >= 1024."
                )
                self.logger.exception("Permission denied binding to %s:%d", self.bind_ip, self.bind_port)
                raise RuntimeError(error_msg) from e
            # Re-raise other OSErrors as-is
            raise

        # Start background tasks
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Bootstrap
        await self._bootstrap()

        self.logger.info("DHT client started on %s:%s", self.bind_ip, self.bind_port)

    async def stop(self) -> None:
        """Stop the DHT client."""
        if self._refresh_task:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        if self.transport:
            self.transport.close()

        self.logger.info("DHT client stopped")

    async def wait_for_bootstrap(self, timeout: float = 10.0) -> bool:
        """Wait for DHT bootstrap to complete.
        
        Args:
            timeout: Maximum time to wait for bootstrap in seconds
            
        Returns:
            True if bootstrap completed, False if timeout

        """
        import asyncio
        import time

        start_time = time.time()
        # Check if we have enough nodes in routing table (bootstrap is complete)
        while time.time() - start_time < timeout:
            if len(self.routing_table.nodes) >= 8:
                return True
            await asyncio.sleep(0.1)

        # Return True if we have any nodes (partial bootstrap), False otherwise
        return len(self.routing_table.nodes) > 0

    async def _bootstrap(self) -> None:
        """Bootstrap the DHT by finding initial nodes."""
        self.logger.info("Bootstrapping DHT...")

        # Try to find nodes from bootstrap servers
        for host, port in self.bootstrap_nodes:
            if not await self._bootstrap_step(host, port):
                continue

        # If we still don't have enough nodes, try to find more
        if len(self.routing_table.nodes) < 8:
            await self._refresh_routing_table()

    async def _bootstrap_step(self, host: str, port: int) -> bool:
        """Attempt to bootstrap from a single host:port. Returns False on error.
        
        Tracks performance for dynamic bootstrap node selection.
        """
        bootstrap_key = (host, port)
        start_time = time.time()
        
        try:
            addr = (socket.gethostbyname(host), port)
            await self._find_nodes(addr, self.node_id)
            
            # Track successful bootstrap
            response_time = time.time() - start_time
            if bootstrap_key not in self.bootstrap_performance:
                self.bootstrap_performance[bootstrap_key] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "response_times": [],
                    "last_success": 0.0,
                    "last_failure": 0.0,
                }
            
            perf = self.bootstrap_performance[bootstrap_key]
            perf["success_count"] += 1
            perf["last_success"] = time.time()
            perf["response_times"].append(response_time)
            if len(perf["response_times"]) > 10:
                perf["response_times"].pop(0)
            
            return True
        except Exception as e:
            self.logger.debug("Bootstrap failed for %s:%s: %s", host, port, e)
            
            # Track failed bootstrap
            response_time = time.time() - start_time
            if bootstrap_key not in self.bootstrap_performance:
                self.bootstrap_performance[bootstrap_key] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "response_times": [],
                    "last_success": 0.0,
                    "last_failure": 0.0,
                }
            
            perf = self.bootstrap_performance[bootstrap_key]
            perf["failure_count"] += 1
            perf["last_failure"] = time.time()
            perf["response_times"].append(response_time)
            if len(perf["response_times"]) > 10:
                perf["response_times"].pop(0)
            
            return False
    
    def _rank_bootstrap_nodes(
        self,
        bootstrap_nodes: list[tuple[str, int]],
    ) -> list[tuple[str, int]]:
        """Rank bootstrap nodes by performance.
        
        Args:
            bootstrap_nodes: List of (host, port) tuples
            
        Returns:
            List of bootstrap nodes sorted by performance (best first)
        """
        node_scores = []
        
        for host, port in bootstrap_nodes:
            bootstrap_key = (host, port)
            perf = self.bootstrap_performance.get(bootstrap_key, {})
            
            # Calculate performance score
            success_count = perf.get("success_count", 0)
            failure_count = perf.get("failure_count", 0)
            total_attempts = success_count + failure_count
            
            if total_attempts > 0:
                success_rate = success_count / total_attempts
            else:
                success_rate = 0.5  # Unknown = neutral
            
            # Average response time (lower is better)
            response_times = perf.get("response_times", [])
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                # Normalize: 0.1s = 1.0, 5.0s = 0.0
                time_score = max(0.0, 1.0 - (avg_response_time - 0.1) / 4.9)
            else:
                time_score = 0.5  # Unknown = neutral
            
            # Recency (more recent success = better)
            last_success = perf.get("last_success", 0.0)
            current_time = time.time()
            if last_success > 0:
                age = current_time - last_success
                recency_score = max(0.0, 1.0 - (age / 3600.0))  # Decay over 1 hour
            else:
                recency_score = 0.0  # Never succeeded = 0
            
            # Combined score
            performance_score = (success_rate * 0.5) + (time_score * 0.3) + (recency_score * 0.2)
            
            node_scores.append((performance_score, (host, port)))
        
        # Sort by performance score (descending)
        node_scores.sort(reverse=True, key=lambda x: x[0])
        
        # Return ranked nodes
        return [node for _, node in node_scores]

    async def _find_nodes(
        self,
        addr: tuple[str, int],
        target_id: bytes,
    ) -> list[DHTNode]:
        """Find nodes close to target ID, tracking response time for quality metrics."""
        start_time = time.time()
        try:
            # Send find_node query
            response = await self._send_query(
                addr,
                "find_node",
                {
                    b"id": self.node_id,
                    b"target": target_id,
                },
            )
            
            response_time = time.time() - start_time

            if not response or response.get(b"y") != b"r":
                # Mark node as bad if query failed
                # Try to find node by address
                for node_id, node in list(self.routing_table.nodes.items()):
                    if (node.ip, node.port) == addr:
                        self.routing_table.mark_node_bad(node_id, response_time)
                        break
                return []

            # Mark node as good if query succeeded
            for node_id, node in list(self.routing_table.nodes.items()):
                if (node.ip, node.port) == addr:
                    self.routing_table.mark_node_good(node_id, response_time)
                    break

            # Parse nodes from response
            nodes = []
            r = response.get(b"r", {})
            nodes_data = r.get(b"nodes", b"")

            # Parse compact node format (26 bytes per node: 20 ID + 4 IP + 2 port)
            for i in range(0, len(nodes_data), 26):
                if i + 26 <= len(nodes_data):
                    node_data = nodes_data[i : i + 26]
                    node_id = node_data[:20]
                    ip = ".".join(str(b) for b in node_data[20:24])
                    port = int.from_bytes(node_data[24:26], "big")

                    node = DHTNode(node_id, ip, port)
                    nodes.append(node)

            # Add nodes to routing table
            for node in nodes:
                self.routing_table.add_node(node)

        except Exception as e:
            self.logger.debug("find_node failed for %s: %s", addr, e)
            # Mark node as bad on exception
            response_time = time.time() - start_time
            for node_id, node in list(self.routing_table.nodes.items()):
                if (node.ip, node.port) == addr:
                    self.routing_table.mark_node_bad(node_id, response_time)
                    break
            return []
        else:
            return nodes

    async def _query_node_for_peers(
        self,
        node: DHTNode,
        info_hash: bytes,
    ) -> dict[bytes, Any] | None:
        """Query a single node for peers.
        
        Args:
            node: DHT node to query
            info_hash: Torrent info hash
            
        Returns:
            Response dict or None on failure
        """
        try:
            response = await self._send_query(
                (node.ip, node.port),
                "get_peers",
                {
                    b"id": self.node_id,
                    b"info_hash": info_hash,
                },
            )
            
            if response and response.get(b"y") == b"r":
                self.routing_table.mark_node_good(node.node_id)
                return response
            else:
                self.routing_table.mark_node_bad(node.node_id)
                return None
        except Exception as e:
            self.logger.debug(
                "get_peers query failed for %s:%s: %s",
                node.ip,
                node.port,
                e,
            )
            self.routing_table.mark_node_bad(node.node_id)
            return None

    def _is_closer(
        self,
        node_id1: bytes,
        node_id2: bytes,
        target_id: bytes,
    ) -> bool:
        """Check if node_id1 is closer to target than node_id2.
        
        Args:
            node_id1: First node ID
            node_id2: Second node ID
            target_id: Target ID (info_hash)
            
        Returns:
            True if node_id1 is closer to target than node_id2
        """
        dist1 = self.routing_table._distance(node_id1, target_id)
        dist2 = self.routing_table._distance(node_id2, target_id)
        return dist1 < dist2

    async def get_peers(
        self,
        info_hash: bytes,
        max_peers: int = 50,
        alpha: int = 3,  # Parallel queries (BEP 5)
        k: int = 8,      # Bucket size
        max_depth: int | None = None,  # Override max depth (default: 10)
    ) -> list[tuple[str, int]]:
        """Get peers for an info hash using proper Kademlia iterative lookup (BEP 5).

        Implements iterative lookup algorithm:
        1. Query α closest unqueried nodes in parallel
        2. Collect peers from responses
        3. Update closest nodes set with returned nodes
        4. Continue until k nodes queried or no closer nodes found

        Args:
            info_hash: Torrent info hash
            max_peers: Maximum number of peers to return
            alpha: Number of parallel queries (default 3, BEP 5)
            k: Bucket size (default 8, BEP 5)

        Returns:
            List of (ip, port) tuples

        """
        # BEP 27: Private torrents must not use DHT for peer discovery
        if self.is_private_torrent and self.is_private_torrent(info_hash):
            self.logger.debug(
                "Skipping DHT get_peers for private torrent %s (BEP 27)",
                info_hash.hex()[:8],
            )
            return []

        # Use a set to track unique peers (deduplication)
        peers_set: set[tuple[str, int]] = set()
        queried_nodes: set[bytes] = set()
        
        # Get initial k closest nodes
        closest_nodes = self.routing_table.get_closest_nodes(info_hash, k)
        closest_set: set[DHTNode] = set(closest_nodes)
        
        # Track query depth for logging
        query_depth = 0
        # Use provided max_depth or default to 10 (safety limit to prevent infinite loops)
        effective_max_depth = max_depth if max_depth is not None else 10
        nodes_queried_count = 0  # Track total nodes queried
        
        # Store query start time for metrics
        self._query_start_time = time.time()
        
        self.logger.debug(
            "Starting DHT iterative lookup for %s (initial closest nodes: %d, alpha=%d, k=%d, max_depth=%d)",
            info_hash.hex()[:8],
            len(closest_set),
            alpha,
            k,
            effective_max_depth,
        )

        # Iterative lookup loop
        # Continue until we've queried enough nodes OR found enough peers OR reached max depth
        max_nodes_to_query = max(k * 2, 50)  # Query at least k*2 nodes, up to 50 for better coverage
        while len(queried_nodes) < max_nodes_to_query and closest_set and query_depth < effective_max_depth:
            query_depth += 1
            
            # Get α closest unqueried nodes
            unqueried = [
                n for n in closest_set
                if n.node_id not in queried_nodes
            ]
            
            if not unqueried:
                # Try to get more nodes from routing table
                additional_nodes = self.routing_table.get_closest_nodes(info_hash, k * 3)
                for new_node in additional_nodes:
                    if new_node.node_id not in queried_nodes and new_node not in closest_set:
                        closest_set.add(new_node)
                        unqueried.append(new_node)
                
                if not unqueried:
                    self.logger.debug(
                        "No unqueried nodes remaining for %s (queried: %d, closest: %d, routing table: %d)",
                        info_hash.hex()[:8],
                        len(queried_nodes),
                        len(closest_set),
                        len(self.routing_table.nodes),
                    )
                    break
            
            # Select α nodes for parallel query
            query_nodes = unqueried[:alpha]
            
            self.logger.debug(
                "DHT query depth %d for %s: querying %d nodes in parallel (total queried: %d, peers found: %d)",
                query_depth,
                info_hash.hex()[:8],
                len(query_nodes),
                len(queried_nodes),
                len(peers_set),
            )
            
            # Query nodes in parallel
            nodes_queried_count += len(query_nodes)
            tasks = [
                self._query_node_for_peers(node, info_hash)
                for node in query_nodes
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Track if we found closer nodes in this iteration
            found_closer_nodes = False
            
            # Process responses
            for node, response in zip(query_nodes, responses):
                queried_nodes.add(node.node_id)
                
                if isinstance(response, Exception):
                    self.logger.debug(
                        "DHT query exception for %s:%s: %s",
                        node.ip,
                        node.port,
                        response,
                    )
                    continue
                
                if not response:
                    continue
                
                r = response.get(b"r", {})
                
                # Collect peers (values field)
                values = r.get(b"values", [])
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, bytes) and len(value) == 6:
                            ip = ".".join(str(b) for b in value[:4])
                            port = int.from_bytes(value[4:6], "big")
                            peer_addr = (ip, port)
                            
                                # Only add if not already seen (deduplication)
                            if peer_addr not in peers_set:
                                peers_set.add(peer_addr)
                                
                                # CRITICAL FIX: Invoke callbacks immediately when peers are found
                                # This ensures peers are connected as soon as they're discovered
                                # rather than waiting until the entire query completes
                                try:
                                    self._invoke_peer_callbacks([peer_addr], info_hash)
                                    self.logger.debug(
                                        "DHT peer found and callback invoked: %s:%d (info_hash: %s, depth: %d)",
                                        ip,
                                        port,
                                        info_hash.hex()[:8],
                                        query_depth,
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        "Failed to invoke DHT peer callback for %s:%d: %s",
                                        ip,
                                        port,
                                        e,
                                    )
                                
                                # Emit DHT peer found event
                                try:
                                    from ccbt.utils.events import Event, emit_event
                                    await emit_event(
                                        Event(
                                            event_type="dht_peer_found",
                                            data={
                                                "ip": ip,
                                                "port": port,
                                                "info_hash": info_hash.hex() if isinstance(info_hash, bytes) else str(info_hash),
                                                "node_ip": node.ip,
                                                "node_port": node.port,
                                                "query_depth": query_depth,
                                            },
                                        )
                                    )
                                except Exception as e:
                                    self.logger.debug("Failed to emit DHT peer_found event: %s", e)
                                
                                if len(peers_set) >= max_peers:
                                    break
                
                # Process returned nodes (nodes field)
                nodes_data = r.get(b"nodes", b"")
                if nodes_data:
                    # Parse compact node format (26 bytes per node: 20 ID + 4 IP + 2 port)
                    for i in range(0, len(nodes_data), 26):
                        if i + 26 <= len(nodes_data):
                            node_data = nodes_data[i : i + 26]
                            node_id = node_data[:20]
                            ip = ".".join(str(b) for b in node_data[20:24])
                            port = int.from_bytes(node_data[24:26], "big")
                            
                            new_node = DHTNode(node_id, ip, port)
                            was_added = self.routing_table.add_node(new_node)
                            
                            # Check if this node should be added to closest_set
                            # Add if closest_set has fewer than k nodes, or if this node is closer than the farthest
                            new_distance = self.routing_table._distance(node_id, info_hash)
                            
                            if len(closest_set) < k:
                                # Always add if we haven't reached k nodes yet
                                closest_set.add(new_node)
                                found_closer_nodes = True
                            elif closest_set:
                                # Check if this node is closer than the farthest node in closest_set
                                # CRITICAL FIX: Use list() to avoid set modification during iteration
                                farthest_node = max(
                                    list(closest_set),
                                    key=lambda n: self.routing_table._distance(n.node_id, info_hash),
                                )
                                farthest_distance = self.routing_table._distance(
                                    farthest_node.node_id, info_hash
                                )
                                
                                if new_distance < farthest_distance:
                                    # Replace farthest with this closer node
                                    # CRITICAL FIX: Check if node still exists before removing (race condition fix)
                                    if farthest_node in closest_set:
                                        closest_set.remove(farthest_node)
                                    closest_set.add(new_node)
                                    found_closer_nodes = True
                            
                            # Emit DHT node found/added event
                            if was_added:
                                try:
                                    from ccbt.utils.events import Event, emit_event
                                    await emit_event(
                                        Event(
                                            event_type="dht_node_found",
                                            data={
                                                "node_id": node_id.hex() if isinstance(node_id, bytes) else str(node_id),
                                                "ip": ip,
                                                "port": port,
                                                "info_hash": info_hash.hex() if isinstance(info_hash, bytes) else str(info_hash),
                                            },
                                        )
                                    )
                                    await emit_event(
                                        Event(
                                            event_type="dht_node_added",
                                            data={
                                                "node_id": node_id.hex() if isinstance(node_id, bytes) else str(node_id),
                                                "ip": ip,
                                                "port": port,
                                            },
                                        )
                                    )
                                except Exception as e:
                                    self.logger.debug("Failed to emit DHT node event: %s", e)
                
                # Store token for announce_peer
                token = r.get(b"token")
                if token:
                    self.tokens[info_hash] = DHTToken(token, info_hash)
            
            # Stop if we have enough peers
            if len(peers_set) >= max_peers:
                self.logger.debug(
                    "DHT iterative lookup for %s found %d peers (max reached), stopping",
                    info_hash.hex()[:8],
                    len(peers_set),
                )
                break
            
            # Continue searching even if no closer nodes found
            # This helps find peers in sparse DHT networks
            if not found_closer_nodes and len(queried_nodes) >= k:
                # Try to get more nodes from routing table to continue search
                # This is important because the initial closest nodes might not have peers
                additional_nodes = self.routing_table.get_closest_nodes(info_hash, k * 3)
                added_new_nodes = False
                for new_node in additional_nodes:
                    if new_node.node_id not in queried_nodes and new_node not in closest_set:
                        closest_set.add(new_node)
                        found_closer_nodes = True
                        added_new_nodes = True
                
                if not added_new_nodes:
                    # No more unqueried nodes available, but continue if we haven't queried enough yet
                    if len(queried_nodes) < max_nodes_to_query and query_depth < effective_max_depth:
                        # Try to expand search by getting nodes from different buckets
                        all_routing_nodes = list(self.routing_table.nodes.values())
                        for node in all_routing_nodes:
                            if node.node_id not in queried_nodes and node not in closest_set:
                                closest_set.add(node)
                                found_closer_nodes = True
                                break
                    
                    if not found_closer_nodes:
                        # Only stop if we've queried enough nodes OR reached max depth
                        if len(queried_nodes) >= max_nodes_to_query or query_depth >= effective_max_depth:
                            self.logger.debug(
                                "DHT iterative lookup for %s converged (no closer nodes, queried: %d/%d, depth: %d/%d, peers: %d)",
                                info_hash.hex()[:8],
                                len(queried_nodes),
                                max_nodes_to_query,
                                query_depth,
                                effective_max_depth,
                                len(peers_set),
                            )
                            break

        # Convert set back to list for return value
        peers = list(peers_set)
        
        # Notify callbacks with info_hash filtering (even if peers list is empty, 
        # callbacks might have been invoked during the query via incoming messages)
        # CRITICAL FIX: Always invoke callbacks with final peer list, even if empty
        # This ensures callbacks are notified when query completes
        # Also invoke with all discovered peers (not just new ones) to ensure all peers are processed
        if peers:
            self.logger.info(
                "DHT get_peers query completed: invoking callbacks with %d peer(s) for info_hash %s",
                len(peers),
                info_hash.hex()[:16],
            )
            self._invoke_peer_callbacks(peers, info_hash)
        else:
            self.logger.debug(
                "DHT get_peers query completed: no peers found for info_hash %s (callbacks may have been invoked during query)",
                info_hash.hex()[:16],
            )
        
        # Emit DHT query complete event
        try:
            from ccbt.utils.events import Event, emit_event
            await emit_event(
                Event(
                    event_type="dht_query_complete",
                    data={
                        "info_hash": info_hash.hex() if isinstance(info_hash, bytes) else str(info_hash),
                        "peers_found": len(peers),
                        "nodes_queried": len(queried_nodes),
                        "query_depth": query_depth,
                        "iterative_lookup": True,
                    },
                )
            )
        except Exception as e:
            self.logger.debug("Failed to emit DHT query_complete event: %s", e)

        self.logger.info(
            "DHT iterative lookup for %s completed: found %d peers, queried %d nodes, depth %d (alpha=%d, k=%d, max_depth=%d)",
            info_hash.hex()[:8],
            len(peers),
            len(queried_nodes),
            query_depth,
            alpha,
            k,
            effective_max_depth,
        )
        
        # Store query metrics for external access
        if not hasattr(self, '_last_query_metrics'):
            self._last_query_metrics = {}
        query_duration = time.time() - getattr(self, '_query_start_time', time.time())
        self._last_query_metrics = {
            "duration": query_duration,
            "peers_found": len(peers),
            "depth": query_depth,
            "nodes_queried": len(queried_nodes),
            "alpha": alpha,
            "k": k,
            "max_depth": effective_max_depth,
        }

        return peers

    async def announce_peer(self, info_hash: bytes, port: int) -> bool:
        """Announce our peer to the DHT.

        Args:
            info_hash: Torrent info hash
            port: Our port

        Returns:
            True if announcement was successful

        """
        # BEP 27: Private torrents must not use DHT for peer announcements
        if self.is_private_torrent and self.is_private_torrent(info_hash):
            self.logger.debug(
                "Skipping DHT announce_peer for private torrent %s (BEP 27)",
                info_hash.hex()[:8],
            )
            return False

        # Get token for this info hash
        if info_hash not in self.tokens:
            # Try to get token by doing a get_peers query
            await self.get_peers(info_hash, 1)

        if info_hash not in self.tokens:
            self.logger.debug("No token available for %s", info_hash.hex())
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
                response = await self._send_query(
                    (node.ip, node.port),
                    "announce_peer",
                    {
                        b"id": self.node_id,
                        b"info_hash": info_hash,
                        b"port": port,
                        b"token": token.token,
                    },
                )

                if response and response.get(b"y") == b"r":
                    success_count += 1
                    self.routing_table.mark_node_good(node.node_id)
                else:
                    self.routing_table.mark_node_bad(node.node_id)

            except Exception as e:
                self.logger.debug(
                    "announce_peer failed for %s:%s: %s",
                    node.ip,
                    node.port,
                    e,
                )
                self.routing_table.mark_node_bad(node.node_id)

        return success_count > 0

    async def get_data(
        self,
        key: bytes,
        public_key: bytes | None = None,
    ) -> bytes | None:
        """Get data from DHT using BEP 44 get_mutable query.
        
        Args:
            key: Data key (20 bytes)
            public_key: Optional public key for mutable data verification
            
        Returns:
            Retrieved data bytes, or None if not found

        """
        # TODO: Implement BEP 44 get_mutable query
        # This is a stub implementation - should be properly implemented
        # using BEP 44 protocol for mutable data storage
        self.logger.debug("get_data called for key: %s", key.hex()[:16])
        # For now, return None (data not found)
        return None

    async def put_data(
        self,
        key: bytes,
        value: bytes,
    ) -> int:
        """Put data to DHT using BEP 44 put_mutable query.
        
        Args:
            key: Data key (20 bytes)
            value: Data value to store
            
        Returns:
            Number of successful storage operations (0 if failed)

        """
        # TODO: Implement BEP 44 put_mutable query
        # This is a stub implementation - should be properly implemented
        # using BEP 44 protocol for mutable data storage
        self.logger.debug("put_data called for key: %s, value size: %d", key.hex()[:16], len(value))
        # For now, return 0 (not implemented)
        return 0

    def _calculate_adaptive_query_timeout(self) -> float:
        """Calculate adaptive DHT query timeout based on peer health.
        
        Returns:
            Timeout in seconds
        """
        # Lazy initialization of timeout calculator
        if self._timeout_calculator is None:
            from ccbt.utils.timeout_adapter import AdaptiveTimeoutCalculator
            
            self._timeout_calculator = AdaptiveTimeoutCalculator(
                config=self.config,
                peer_manager=self.peer_manager,
            )
        
        return self._timeout_calculator.calculate_dht_timeout()

    def set_peer_manager(self, peer_manager: Any) -> None:
        """Set peer manager reference for health tracking.
        
        Args:
            peer_manager: Peer manager instance for health metrics
        """
        self.peer_manager = peer_manager
        # Reset timeout calculator to pick up new peer_manager
        self._timeout_calculator = None

    async def _send_query(
        self,
        addr: tuple[str, int],
        query: str,
        args: dict[bytes, Any],
    ) -> dict[bytes, Any] | None:
        """Send a DHT query and wait for response, tracking response time for quality metrics."""
        # Calculate adaptive timeout based on peer health
        query_timeout = self._calculate_adaptive_query_timeout()
        
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
        if self.transport is None:
            msg = _ERROR_DHT_TRANSPORT_NOT_INITIALIZED
            raise RuntimeError(msg)
        self.transport.sendto(data, addr)

        # Track response time for quality metrics
        start_time = time.time()
        response_time: float | None = None

        # Wait for response
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(tid),
                timeout=query_timeout,
            )
            response_time = time.time() - start_time
            return response
        except asyncio.TimeoutError:
            self.logger.debug(
                "Query timeout for %s (timeout=%.1fs)", addr, query_timeout
            )
            response_time = query_timeout  # Use timeout as response time for failed queries
            return None
        finally:
            # Update node quality metrics if we can identify the node
            # Try to find node by address
            if response_time is not None:
                node_id = None
                # Try to find node by address in routing table
                for nid, node in self.routing_table.nodes.items():
                    if (node.ip, node.port) == addr:
                        node_id = nid
                        break
                    # Also check IPv6 and additional addresses
                    if node.has_ipv6 and node.ipv6 and node.port6 and (node.ipv6, node.port6) == addr:
                        node_id = nid
                        break
                    for add_addr in node.additional_addresses:
                        if add_addr == addr:
                            node_id = nid
                            break
                
                # Update quality metrics if node found
                if node_id is not None:
                    # Determine if query was successful based on whether we got a response
                    # (response will be None if timeout, non-None if successful)
                    # We'll update this in the calling code, but track response time here
                    pass  # Response time tracking is done, actual good/bad marking happens in calling code

    async def _wait_for_response(self, tid: bytes) -> dict[bytes, Any]:
        """Wait for response with given transaction ID."""
        future = asyncio.Future()
        self.pending_queries[tid] = future

        try:
            return await future
        finally:
            self.pending_queries.pop(tid, None)

    def handle_response(self, data: bytes, _addr: tuple[str, int]) -> None:
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
            self.logger.debug("Failed to parse DHT response: %s", e)

    def _calculate_adaptive_interval(self) -> float:
        """Calculate adaptive lookup interval based on peer count and swarm health.
        
        Returns:
            Interval in seconds (from config min/max bounds)
        """
        # Check if adaptive intervals are enabled
        if not self.config.discovery.dht_adaptive_interval_enabled:
            return self.config.discovery.dht_base_refresh_interval
        
        # Base interval from config
        base_interval = self.config.discovery.dht_base_refresh_interval
        
        # Get current peer count from routing table
        total_nodes = len(self.routing_table.nodes)
        good_nodes = sum(1 for n in self.routing_table.nodes.values() if n.is_good)
        
        # Calculate swarm health (ratio of good nodes)
        swarm_health = good_nodes / total_nodes if total_nodes > 0 else 0.0
        
        # Adaptive calculation:
        # - More peers (>= 50) = longer interval (less frequent lookups)
        # - Fewer peers (< 20) = shorter interval (more frequent lookups)
        # - Poor swarm health (< 0.5) = shorter interval (more frequent lookups)
        # - Good swarm health (>= 0.8) = longer interval (less frequent lookups)
        
        if total_nodes >= 50 and swarm_health >= 0.8:
            # Healthy swarm with many peers - reduce lookup frequency
            multiplier = 1.5
        elif total_nodes < 20 or swarm_health < 0.5:
            # Small swarm or poor health - increase lookup frequency
            multiplier = 0.5
        else:
            # Moderate state - use base interval
            multiplier = 1.0
        
        adaptive_interval = base_interval * multiplier
        
        # Clamp to config bounds
        min_interval = self.config.discovery.dht_adaptive_interval_min
        max_interval = self.config.discovery.dht_adaptive_interval_max
        adaptive_interval = max(min_interval, min(max_interval, adaptive_interval))
        
        return adaptive_interval

    async def _refresh_loop(self) -> None:
        """Background task to refresh routing table with adaptive intervals."""
        while True:
            try:
                # Calculate adaptive interval based on swarm health
                interval = self._calculate_adaptive_interval()
                await asyncio.sleep(interval)
                await self._refresh_routing_table()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in refresh loop")

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
            except Exception:
                self.logger.exception("Error in cleanup loop")

    async def _cleanup_old_data(self) -> None:
        """Clean up old tokens and bad nodes."""
        current_time = time.time()

        # Clean up expired tokens
        expired_tokens = [
            info_hash
            for info_hash, token in self.tokens.items()
            if current_time > token.expires_time
        ]
        for info_hash in expired_tokens:
            del self.tokens[info_hash]

        # Remove bad nodes
        bad_nodes = [
            node_id
            for node_id, node in self.routing_table.nodes.items()
            if not node.is_good and node.failed_queries >= 3
        ]
        for node_id in bad_nodes:
            node = self.routing_table.nodes.get(node_id)
            if node:
                # Emit DHT node removed event before removal
                try:
                    from ccbt.utils.events import Event, emit_event
                    await emit_event(
                        Event(
                            event_type="dht_node_removed",
                            data={
                                "node_id": node_id.hex() if isinstance(node_id, bytes) else str(node_id),
                                "ip": node.ip,
                                "port": node.port,
                                "reason": "bad_node",
                                "failed_queries": node.failed_queries,
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit DHT node_removed event: %s", e)
            self.routing_table.remove_node(node_id)

    def _invoke_peer_callbacks(
        self,
        peers: list[tuple[str, int]],
        info_hash: bytes,
    ) -> None:
        """Invoke peer callbacks with info_hash filtering.
        
        Args:
            peers: List of discovered peers
            info_hash: Info hash to filter callbacks
        """
        # CRITICAL FIX: Add logging to verify callback invocations
        global_callback_count = len(self.peer_callbacks)
        hash_specific_count = len(self.peer_callbacks_by_hash.get(info_hash, []))
        
        if global_callback_count > 0 or hash_specific_count > 0:
            self.logger.info(
                "Invoking DHT peer callbacks: %d peer(s), info_hash=%s, "
                "global_callbacks=%d, hash_specific_callbacks=%d",
                len(peers),
                info_hash.hex()[:16] + "...",
                global_callback_count,
                hash_specific_count,
            )
        else:
            self.logger.warning(
                "No DHT peer callbacks registered for info_hash %s (peers=%d) - peers will not be connected! "
                "This may indicate callback registration failed or session is not ready.",
                info_hash.hex()[:16] + "...",
                len(peers),
            )
        
        # Invoke global callbacks (no info_hash filtering)
        for idx, callback in enumerate(self.peer_callbacks):
            try:
                callback(peers)
                self.logger.info(
                    "Invoked global DHT peer callback #%d for info_hash %s (%d peers)",
                    idx + 1,
                    info_hash.hex()[:16] + "...",
                    len(peers),
                )
            except Exception as e:
                self.logger.exception(
                    "Peer callback error (global callback #%d, info_hash=%s): %s",
                    idx + 1,
                    info_hash.hex()[:16] + "...",
                    e,
                )
        
        # Invoke info_hash-specific callbacks
        if info_hash in self.peer_callbacks_by_hash:
            for idx, callback in enumerate(self.peer_callbacks_by_hash[info_hash]):
                try:
                    callback(peers)
                    self.logger.info(
                        "Invoked info_hash-specific DHT peer callback #%d for info_hash %s (%d peers)",
                        idx + 1,
                        info_hash.hex()[:16] + "...",
                        len(peers),
                    )
                except Exception as e:
                    self.logger.exception(
                        "Peer callback error (info_hash=%s, callback #%d): %s",
                        info_hash.hex()[:8],
                        idx + 1,
                        e,
                    )

    def add_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: bytes | None = None,
    ) -> None:
        """Add callback for new peers.
        
        Args:
            callback: Callback function to invoke when peers are discovered
            info_hash: Optional info hash to filter callbacks. If provided, callback
                      is only invoked for peers matching this info_hash. If None,
                      callback is invoked for all peer discoveries (global callback).
        """
        if info_hash is not None:
            if info_hash not in self.peer_callbacks_by_hash:
                self.peer_callbacks_by_hash[info_hash] = []
            self.peer_callbacks_by_hash[info_hash].append(callback)
            self.logger.debug(
                "Registered DHT peer callback for info_hash %s (total callbacks for this hash: %d)",
                info_hash.hex()[:8],
                len(self.peer_callbacks_by_hash[info_hash]),
            )
        else:
            self.peer_callbacks.append(callback)
            self.logger.debug(
                "Registered global DHT peer callback (total global callbacks: %d)",
                len(self.peer_callbacks),
            )

    def remove_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: bytes | None = None,
    ) -> None:
        """Remove peer callback.
        
        Args:
            callback: Callback function to remove
            info_hash: Optional info hash. If provided, removes callback from
                      info_hash-specific list. If None, removes from global list.
        """
        if info_hash is not None:
            if info_hash in self.peer_callbacks_by_hash:
                if callback in self.peer_callbacks_by_hash[info_hash]:
                    self.peer_callbacks_by_hash[info_hash].remove(callback)
                    if not self.peer_callbacks_by_hash[info_hash]:
                        del self.peer_callbacks_by_hash[info_hash]
        else:
            if callback in self.peer_callbacks:
                self.peer_callbacks.remove(callback)

    def get_stats(self) -> dict[str, Any]:
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
        """Initialize DHT protocol handler."""
        self.client = client

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        self.client.handle_response(data, addr)

    def error_received(self, exc: Exception) -> None:
        """Handle UDP error."""
        self.client.logger.debug("DHT error: %s", exc)


# Global DHT client instance
_dht_client: AsyncDHTClient | None = None


def get_dht_client() -> AsyncDHTClient:
    """Get the global DHT client."""
    global _dht_client
    if _dht_client is None:
        _dht_client = AsyncDHTClient()
    return _dht_client


async def init_dht() -> AsyncDHTClient:
    """Initialize global DHT client."""
    _dht_client = AsyncDHTClient()
    await _dht_client.start()
    return _dht_client


# Export the main DHT client class
DHTClient = AsyncDHTClient


async def shutdown_dht() -> None:
    """Shutdown global DHT client."""
    global _dht_client
    if _dht_client:
        await _dht_client.stop()
        _dht_client = None
