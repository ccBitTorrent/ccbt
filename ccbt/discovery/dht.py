"""Enhanced DHT (BEP 5) client with full Kademlia implementation.

Provides high-performance peer discovery using Kademlia routing table,
iterative lookups, token verification, and continuous refresh.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from ccbt.config.config import get_config
from ccbt.core.bencode import BencodeDecoder, BencodeEncoder
from ccbt.models import PeerInfo
from ccbt.utils.shutdown import is_shutting_down

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
    ipv6: Optional[str] = None
    port6: Optional[int] = None
    has_ipv6: bool = False
    additional_addresses: list[tuple[str, int]] = field(default_factory=list)

    # Quality metrics for optimization
    response_times: list[float] = field(
        default_factory=list
    )  # List of recent response times
    average_response_time: float = 0.0  # Average response time in seconds
    success_rate: float = 1.0  # Success rate (0.0-1.0)
    quality_score: float = 1.0  # Overall quality score (0.0-1.0)
    last_response_time: float = 0.0  # Last measured response time
    query_count: int = 0  # Total queries made to this node

    def __post_init__(self) -> None:
        """Post-initialization: auto-set has_ipv6 flag when IPv6 data is provided."""
        # Auto-set has_ipv6=True when both ipv6 and port6 are provided
        if self.ipv6 is not None and self.port6 is not None:
            self.has_ipv6 = True

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
    node_addr: tuple[str, int] = ("", 0)
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

    def distance(self, node_id1: bytes, node_id2: bytes) -> int:
        """Calculate XOR distance between two node IDs (public API).

        Args:
            node_id1: First node ID
            node_id2: Second node ID

        Returns:
            XOR distance between the two node IDs

        """
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

    def _distance(self, node_id1: bytes, node_id2: bytes) -> int:
        """Calculate XOR distance between two node IDs (private, use distance() instead)."""
        return self.distance(node_id1, node_id2)

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
            return (recency_score * 0.6) + (node.quality_score * 0.4)

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
            if not hasattr(node, "reachability_score"):
                node.reachability_score = self._assess_node_reachability(node)  # type: ignore[attr-defined]

        # Sort by distance first, then by reachability (descending), then by quality score (descending), then by good status
        all_nodes.sort(
            key=lambda n: (
                self.distance(n.node_id, target_id),
                -getattr(n, "reachability_score", 0.5),  # Negative for descending order
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

    def mark_node_bad(
        self, node_id: bytes, response_time: Optional[float] = None
    ) -> None:
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
            if (
                hasattr(self, "config")
                and self.config.discovery.dht_quality_tracking_enabled  # type: ignore[union-attr]
            ):
                # Update success rate
                if node.query_count > 0:
                    node.success_rate = node.successful_queries / node.query_count

                # Update quality score (weighted by success rate and response time)
                if response_time is not None:
                    node.last_response_time = response_time
                    # Add to response times list (keep configured window size)
                    discovery_config = getattr(self.config, "discovery", None)
                    if discovery_config is not None:
                        max_window = getattr(
                            discovery_config,
                            "dht_quality_response_time_window",
                            10,
                        )
                    else:
                        max_window = 10
                    node.response_times.append(response_time)
                    if len(node.response_times) > max_window:
                        node.response_times.pop(0)
                    # Update average
                    if node.response_times:
                        node.average_response_time = sum(node.response_times) / len(
                            node.response_times
                        )

                # Quality score: success_rate * (1.0 / (1.0 + avg_response_time))
                # Faster nodes with higher success rates get better scores
                if node.average_response_time > 0:
                    time_factor = 1.0 / (1.0 + node.average_response_time)
                else:
                    time_factor = 1.0
                node.quality_score = node.success_rate * time_factor

    def mark_node_good(
        self, node_id: bytes, response_time: Optional[float] = None
    ) -> None:
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
            if (
                hasattr(self, "config")
                and self.config.discovery.dht_quality_tracking_enabled  # type: ignore[union-attr]
            ):
                # Update success rate
                if node.query_count > 0:
                    node.success_rate = node.successful_queries / node.query_count

                # Update quality score (weighted by success rate and response time)
                if response_time is not None:
                    node.last_response_time = response_time
                    # Add to response times list (keep configured window size)
                    discovery_config = getattr(self.config, "discovery", None)
                    if discovery_config is not None:
                        max_window = getattr(
                            discovery_config,
                            "dht_quality_response_time_window",
                            10,
                        )
                    else:
                        max_window = 10
                    node.response_times.append(response_time)
                    if len(node.response_times) > max_window:
                        node.response_times.pop(0)
                    # Update average
                    if node.response_times:
                        node.average_response_time = sum(node.response_times) / len(
                            node.response_times
                        )

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
        quality_scores = [
            n.quality_score for n in self.nodes.values() if n.query_count > 0
        ]
        avg_quality_score = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )

        response_times = [
            n.average_response_time
            for n in self.nodes.values()
            if n.average_response_time > 0
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        success_rates = [
            n.success_rate for n in self.nodes.values() if n.query_count > 0
        ]
        avg_success_rate = (
            sum(success_rates) / len(success_rates) if success_rates else 0.0
        )

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

    def __init__(
        self,
        bind_ip: str = "0.0.0.0",
        bind_port: int = 0,
        read_only: bool = False,  # nosec B104
    ):
        """Initialize DHT client.

        Args:
            bind_ip: IP address to bind to
            bind_port: Port to bind to (0 for auto-assign)
            read_only: If True, node operates in read-only mode (BEP 43)

        """
        self.config = get_config()
        self.read_only = read_only

        # Node identity
        self.node_id = self._generate_node_id()

        # Network
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.socket: Optional[asyncio.DatagramProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None

        # Routing table
        self.routing_table = KademliaRoutingTable(self.node_id)

        # Bootstrap nodes - Note: Use config instead of hardcoded defaults
        # Parse bootstrap nodes from config (format: "host:port")
        # Initialize logger first for error reporting
        self.logger = logging.getLogger(__name__)

        config_bootstrap = (
            self.config.discovery.dht_bootstrap_nodes
            if hasattr(self.config, "discovery")
            else []
        )
        if config_bootstrap:
            self.bootstrap_nodes = []
            for node_str in config_bootstrap:
                if ":" in node_str:
                    try:
                        host, port_str = node_str.rsplit(":", 1)
                        port = int(port_str)
                        self.bootstrap_nodes.append((host, port))
                    except (ValueError, IndexError):
                        self.logger.warning(
                            "Invalid bootstrap node format: %s (expected host:port)",
                            node_str,
                        )
                else:
                    self.logger.warning(
                        "Invalid bootstrap node format: %s (expected host:port)",
                        node_str,
                    )
            if not self.bootstrap_nodes:
                # Fallback to defaults if all config nodes are invalid
                self.logger.warning(
                    "No valid bootstrap nodes in config, using defaults"
                )
                self.bootstrap_nodes = DEFAULT_BOOTSTRAP.copy()
        else:
            # No bootstrap nodes in config, use defaults
            self.bootstrap_nodes = DEFAULT_BOOTSTRAP.copy()

        # Bootstrap node performance tracking
        # Maps (host, port) -> performance metrics
        self.bootstrap_performance: dict[tuple[str, int], dict[str, Any]] = {}
        self._bootstrap_attempt_failures: dict[tuple[str, int], int] = {}
        self._bootstrap_attempt_timestamps: dict[tuple[str, int], float] = {}
        discovery_cfg = getattr(self.config, "discovery", None)
        self._dht_bootstrap_retries_max = int(
            getattr(discovery_cfg, "dht_bootstrap_retries_max", 3)
        )
        self._dht_bootstrap_memo_ttl_s = float(
            getattr(discovery_cfg, "dht_bootstrap_memo_ttl_s", 120.0)
        )
        self._dht_bootstrap_timeout_s = float(
            getattr(discovery_cfg, "dht_bootstrap_timeout_s", 30.0) or 30.0
        )
        # Host-level DNS failure backoff (memoized per hostname; monotonic deadlines)
        self._dht_dns_host_backoff_until: dict[str, float] = {}
        self._dht_dns_host_fail_streak: dict[str, int] = {}
        self._dht_dns_host_backoff_initial_s = float(
            getattr(discovery_cfg, "dht_dns_host_backoff_initial_s", 2.0) or 2.0
        )
        self._dht_dns_host_backoff_max_s = float(
            getattr(discovery_cfg, "dht_dns_host_backoff_max_s", 120.0) or 120.0
        )
        self._dht_dns_host_backoff_multiplier = float(
            getattr(discovery_cfg, "dht_dns_host_backoff_multiplier", 2.0) or 2.0
        )
        self.bootstrap_success_count = 0
        self.bootstrap_failure_count = 0
        self.last_bootstrap_reason = "not_started"
        self.last_bootstrap_failure_reason = ""
        self.last_zero_node_lookup_at = 0.0
        self.last_bootstrap_state = "idle"
        self.last_lookup_state = "idle"
        self._empty_table_rebootstrap_attempts = 0
        self._max_empty_table_rebootstrap_attempts = 3
        self._last_empty_table_rebootstrap_at = 0.0
        self._empty_table_rebootstrap_backoff = 1.0

        # Pending queries
        self.pending_queries: dict[bytes, asyncio.Future] = {}
        # Initialize query_timeout from config (default from network.dht_timeout)
        self.query_timeout = self.config.network.dht_timeout

        # Peer manager reference for health tracking (optional)
        self.peer_manager: Optional[Any] = None

        # Adaptive timeout calculator (lazy initialization)
        self._timeout_calculator: Optional[Any] = None

        # Tokens for announce_peer, keyed by (info_hash, node_addr) or legacy info_hash
        self.tokens: dict[Union[bytes, tuple[bytes, tuple[str, int]]], DHTToken] = {}
        self.token_secret = os.urandom(20)

        # Background tasks
        self._refresh_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._bootstrap_task: Optional[asyncio.Task] = None

        # Callbacks with info_hash filtering
        # Maps info_hash -> list of callbacks, or None for global callbacks
        self.peer_callbacks: list[Callable[[list[tuple[str, int]]], None]] = []
        self.peer_callbacks_by_hash: dict[
            bytes, list[Callable[[list[tuple[str, int]]], None]]
        ] = {}
        self.callback_metrics: dict[str, int] = {
            "peers_found_without_callbacks": 0,
            "peers_delivered_to_callbacks": 0,
            "callback_exceptions": 0,
            "callbacks_registered": 0,
        }

        # BEP 27: Callback to check if a torrent is private
        self.is_private_torrent: Optional[Callable[[bytes], bool]] = None
        # Authenticated swarms discovery policy callback: return True when DHT should be suppressed
        self.is_swarm_discovery_disabled: Optional[Callable[[bytes], bool]] = None
        self._xet_mutable_store: dict[bytes, bytes] = {}
        # BEP 44: storage write tokens from get responses: key -> ([(token, addr), ...], expires_at)
        self._storage_tokens: dict[
            bytes, tuple[list[tuple[bytes, tuple[str, int]]], float]
        ] = {}
        # BEP 44 server: (addr, target_key) -> (token, expires_at) for put validation
        self._storage_write_tokens: dict[
            tuple[tuple[str, int], bytes], tuple[bytes, float]
        ] = {}
        # BEP 44 server: key -> seq for mutable put seq check
        self._storage_seq: dict[bytes, int] = {}
        # BEP 5 server: (addr, info_hash) -> (token, expires_at) for announce_peer
        self._get_peers_tokens: dict[
            tuple[tuple[str, int], bytes], tuple[bytes, float]
        ] = {}
        # BEP 5 server: info_hash -> list of (ip, port)
        self._peers_store: dict[bytes, list[tuple[str, int]]] = {}

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
            # Note: Enhanced port conflict error handling
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
                    self.logger.exception(
                        "DHT UDP port %d is already in use", self.bind_port
                    )
                    raise RuntimeError(error_msg) from e
                if error_code == 10013:  # WSAEACCES
                    error_msg = (
                        f"Permission denied binding to {self.bind_ip}:{self.bind_port}.\n"
                        f"Error: {e}\n\n"
                        f"Resolution: Run with administrator privileges or change the port."
                    )
                    self.logger.exception(
                        "Permission denied binding to %s:%d",
                        self.bind_ip,
                        self.bind_port,
                    )
                    raise RuntimeError(error_msg) from e
            elif error_code == 98:  # EADDRINUSE
                from ccbt.utils.port_checker import get_port_conflict_resolution

                resolution = get_port_conflict_resolution(self.bind_port, "udp")
                error_msg = (
                    f"DHT UDP port {self.bind_port} is already in use.\n"
                    f"Error: {e}\n\n"
                    f"{resolution}"
                )
                self.logger.exception(
                    "DHT UDP port %d is already in use", self.bind_port
                )
                raise RuntimeError(error_msg) from e
            elif error_code == 13:  # EACCES
                error_msg = (
                    f"Permission denied binding to {self.bind_ip}:{self.bind_port}.\n"
                    f"Error: {e}\n\n"
                    f"Resolution: Run with root privileges or change the port to >= 1024."
                )
                self.logger.exception(
                    "Permission denied binding to %s:%d", self.bind_ip, self.bind_port
                )
                raise RuntimeError(error_msg) from e
            # Re-raise other OSErrors as-is
            raise

        # Start background tasks
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Bootstrap in background so daemon startup is not blocked (up to 30s when nodes unreachable)
        self._bootstrap_task = asyncio.create_task(self._bootstrap())

        self.logger.info("DHT client started on %s:%s", self.bind_ip, self.bind_port)

    async def stop(self) -> None:
        """Stop the DHT client.

        Ensures proper cleanup order to prevent port conflicts on Windows:
        1. Cancel background tasks
        2. Close transport
        3. Wait for transport to fully close (Windows timing issue)
        4. Clear socket reference
        5. Clear transport reference
        """
        # Release in-flight query waiters immediately (avoids 60s tails during shutdown)
        if self.pending_queries:
            for _tid, fut in list(self.pending_queries.items()):
                if not fut.done():
                    fut.cancel()
            self.pending_queries.clear()

        if self._refresh_task:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        if self._bootstrap_task:
            self._bootstrap_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bootstrap_task
            self._bootstrap_task = None

        # Proper cleanup order: close transport first, then handle socket
        if self.transport:
            self.transport.close()
            # Note: Wait for transport to fully close (Windows timing issue)
            # On Windows, UDP sockets may not be immediately released after close()
            # This prevents "WinError 10048: Only one usage of each socket address" errors
            import sys

            if sys.platform == "win32":
                await asyncio.sleep(0.2)  # Longer wait on Windows
            else:
                await asyncio.sleep(0.1)  # Shorter wait on Unix

        # ENHANCEMENT: Explicitly close socket if it exists and has a close method
        # This ensures immediate port release
        if self.socket:
            try:
                # If socket is a protocol instance, it may have a close method
                if hasattr(self.socket, "close") and callable(self.socket.close):
                    self.socket.close()
                # If socket has _closed attribute, check it
                elif (
                    hasattr(self.socket, "_closed")
                    and not getattr(self.socket, "_closed", True)
                    and self.transport
                    and hasattr(self.transport, "get_extra_info")
                ):
                    # Try to close via transport if available
                    sock = self.transport.get_extra_info("socket")
                    if (
                        sock
                        and hasattr(sock, "close")
                        and not getattr(sock, "_closed", True)
                    ):
                        sock.close()
            except Exception as e:
                self.logger.debug("Error closing socket during stop: %s", e)

        # Clear references to ensure garbage collection
        # The socket is a DatagramProtocol instance managed by the transport
        # The transport.close() should handle it, but we clear references
        self.transport = None
        self.socket = None

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

    async def _bootstrap(self, reason: str = "bootstrap") -> None:
        """Bootstrap the DHT by finding initial nodes."""
        self.last_bootstrap_reason = reason
        self.last_bootstrap_failure_reason = ""
        self.last_bootstrap_state = f"starting:{reason}"
        self.logger.info("Bootstrapping DHT...")
        self.last_zero_node_lookup_at = 0.0
        start_time = time.time()
        self._prune_bootstrap_attempt_state(start_time)

        # Overall bootstrap wall clock (config: discovery.dht_bootstrap_timeout_s)
        bootstrap_timeout = self._dht_bootstrap_timeout_s

        try:
            # Try to find nodes from bootstrap servers
            for host, port in self.bootstrap_nodes:
                # Check if we've exceeded overall timeout
                if time.time() - start_time > bootstrap_timeout:
                    self.logger.warning(
                        "Bootstrap timeout (%.1fs) - continuing with %d nodes",
                        bootstrap_timeout,
                        len(self.routing_table.nodes),
                    )
                    self.last_bootstrap_failure_reason = "bootstrap_timeout"
                    self.last_bootstrap_state = "failed:bootstrap_timeout"
                    break

                if not await self._bootstrap_step(host, port):
                    continue

                # If we have enough nodes, we can stop early
                if len(self.routing_table.nodes) >= 8:
                    self.bootstrap_success_count += 1
                    self.logger.info(
                        "Bootstrap complete: found %d nodes",
                        len(self.routing_table.nodes),
                    )
                    return

            # If we still don't have enough nodes, try to find more (with timeout check)
            if (
                len(self.routing_table.nodes) < 8
                and time.time() - start_time < bootstrap_timeout
            ):
                try:
                    await asyncio.wait_for(
                        self._refresh_routing_table(),
                        timeout=max(
                            1.0, bootstrap_timeout - (time.time() - start_time)
                        ),
                    )
                except asyncio.TimeoutError:
                    self.logger.debug("Refresh routing table timeout during bootstrap")
                    self.last_bootstrap_failure_reason = "routing_refresh_timeout"

            if len(self.routing_table.nodes) > 0:
                self.bootstrap_success_count += 1
                self._empty_table_rebootstrap_attempts = 0
                self._empty_table_rebootstrap_backoff = 1.0
                self.last_bootstrap_state = "succeeded"
            else:
                self.bootstrap_failure_count += 1
                if not self.last_bootstrap_failure_reason:
                    self.last_bootstrap_failure_reason = "no_nodes_discovered"
                self.last_bootstrap_state = (
                    f"failed:{self.last_bootstrap_failure_reason}"
                )
        except asyncio.CancelledError:
            if not self.last_bootstrap_failure_reason:
                self.last_bootstrap_failure_reason = "bootstrap_cancelled_or_timeout"
            raise

        self.logger.info(
            "Bootstrap completed with %d nodes", len(self.routing_table.nodes)
        )

    async def rebootstrap(self) -> bool:
        """Retry bootstrap using ranked bootstrap nodes.

        Returns:
            True if at least one node is present after rebootstrap, False otherwise.
        """
        ranked_nodes = self._rank_bootstrap_nodes(self.bootstrap_nodes)
        original_nodes = self.bootstrap_nodes
        if ranked_nodes:
            self.bootstrap_nodes = ranked_nodes
        try:
            await self._bootstrap(reason="rebootstrap")
        finally:
            self.bootstrap_nodes = original_nodes
        return len(self.routing_table.nodes) > 0

    def _can_attempt_bootstrap_node(self, bootstrap_key: tuple[str, int]) -> bool:
        """Return whether a bootstrap node can be retried now."""
        now = time.time()
        failure_count = self._bootstrap_attempt_failures.get(bootstrap_key, 0)
        last_failure = self._bootstrap_attempt_timestamps.get(bootstrap_key, 0.0)
        if failure_count < self._dht_bootstrap_retries_max:
            return True
        if now - last_failure > self._dht_bootstrap_memo_ttl_s:
            self._bootstrap_attempt_failures.pop(bootstrap_key, None)
            self._bootstrap_attempt_timestamps.pop(bootstrap_key, None)
            return True
        return False

    def _mark_bootstrap_attempt_failed(self, bootstrap_key: tuple[str, int]) -> None:
        """Track failed bootstrap attempts for deduplication."""
        self._bootstrap_attempt_failures[bootstrap_key] = (
            self._bootstrap_attempt_failures.get(bootstrap_key, 0) + 1
        )
        self._bootstrap_attempt_timestamps[bootstrap_key] = time.time()

    def _mark_bootstrap_attempt_succeeded(self, bootstrap_key: tuple[str, int]) -> None:
        """Reset cached bootstrap failure state after a successful bootstrap."""
        self._bootstrap_attempt_failures.pop(bootstrap_key, None)
        self._bootstrap_attempt_timestamps.pop(bootstrap_key, None)

    def _prune_bootstrap_attempt_state(self, now: Optional[float] = None) -> None:
        """Prune stale bootstrap failure records."""
        current_time = now if now is not None else time.time()
        stale_keys = [
            bootstrap_key
            for bootstrap_key, last_failure in self._bootstrap_attempt_timestamps.items()
            if current_time - last_failure > self._dht_bootstrap_memo_ttl_s
        ]
        for bootstrap_key in stale_keys:
            self._bootstrap_attempt_failures.pop(bootstrap_key, None)
            self._bootstrap_attempt_timestamps.pop(bootstrap_key, None)

    @staticmethod
    def _normalize_dht_dns_host(host: str) -> str:
        """Normalize hostname for DNS backoff keys (case-insensitive)."""
        return host.strip().lower()

    def _is_dns_host_in_backoff(self, host: str) -> bool:
        """Return True if this hostname should skip resolver calls until backoff expires."""
        host_key = self._normalize_dht_dns_host(host)
        until = self._dht_dns_host_backoff_until.get(host_key)
        if until is None:
            return False
        now_m = time.monotonic()
        if now_m >= until:
            self._dht_dns_host_backoff_until.pop(host_key, None)
            return False
        return True

    def _dns_host_backoff_remaining_s(self, host: str) -> float:
        """Seconds remaining in host-level DNS backoff, or 0.0 if none."""
        host_key = self._normalize_dht_dns_host(host)
        until = self._dht_dns_host_backoff_until.get(host_key)
        if until is None:
            return 0.0
        return max(0.0, until - time.monotonic())

    def _record_dns_host_failure(self, host: str) -> None:
        """Apply exponential per-host backoff after DNS timeout or resolver error."""
        host_key = self._normalize_dht_dns_host(host)
        streak = self._dht_dns_host_fail_streak.get(host_key, 0) + 1
        self._dht_dns_host_fail_streak[host_key] = streak
        initial = max(0.5, self._dht_dns_host_backoff_initial_s)
        mult = max(1.0, self._dht_dns_host_backoff_multiplier)
        max_s = max(initial, self._dht_dns_host_backoff_max_s)
        delay = min(max_s, initial * (mult ** (streak - 1)))
        self._dht_dns_host_backoff_until[host_key] = time.monotonic() + delay
        self.logger.debug(
            "DHT DNS host backoff scheduled: host=%s streak=%d delay=%.1fs",
            host_key,
            streak,
            delay,
        )

    def _clear_dns_host_backoff(self, host: str) -> None:
        """Clear memoized DNS failure state after a successful resolve."""
        host_key = self._normalize_dht_dns_host(host)
        self._dht_dns_host_backoff_until.pop(host_key, None)
        self._dht_dns_host_fail_streak.pop(host_key, None)

    def _empty_routing_operational_context(self) -> str:
        """Compact diagnostics for empty-routing warnings (bind, DHT IP prefs, bootstrap)."""
        discovery = getattr(self.config, "discovery", None)
        ipv6 = bool(getattr(discovery, "dht_enable_ipv6", False))
        prefer6 = bool(getattr(discovery, "dht_prefer_ipv6", False))
        fr = self.last_bootstrap_failure_reason or "unset"
        return (
            f"bind={self.bind_ip}:{self.bind_port} "
            f"dht_ipv6_enabled={ipv6} dht_prefer_ipv6={prefer6} "
            f"bootstrap_nodes={len(self.bootstrap_nodes)} "
            f"last_bootstrap_failure_reason={fr!r}"
        )

    def _log_empty_routing_warning(self, summary: str) -> None:
        """Emit one WARNING line with operational context for empty routing table."""
        self.logger.warning("%s %s", summary, self._empty_routing_operational_context())

    def _schedule_zero_node_rebootstrap(
        self, reason: str = "empty_routing_table"
    ) -> bool:
        """Schedule a bounded rebootstrap when routing table is empty."""
        now = time.monotonic()
        if (
            self._empty_table_rebootstrap_attempts
            >= self._max_empty_table_rebootstrap_attempts
        ):
            self.logger.debug(
                "DHT empty routing rebootstrap suppressed after %d attempts: %s",
                self._empty_table_rebootstrap_attempts,
                reason,
            )
            self.last_bootstrap_state = "suppressed:rebootstrap_limit_reached"
            return False

        cooldown = self._empty_table_rebootstrap_backoff
        if now - self._last_empty_table_rebootstrap_at < cooldown:
            self.logger.debug(
                "DHT empty routing rebootstrap skipped due cooldown %.1fs (%s)",
                cooldown - (now - self._last_empty_table_rebootstrap_at),
                reason,
            )
            self.last_bootstrap_state = "suppressed:empty_table_cooldown"
            return False

        self._last_empty_table_rebootstrap_at = now
        self._empty_table_rebootstrap_attempts += 1
        self._empty_table_rebootstrap_backoff = min(
            self._empty_table_rebootstrap_backoff * 2.0, 60.0
        )
        self.last_bootstrap_state = "scheduled:empty_table_rebootstrap"
        self.logger.warning(
            "DHT bootstrap retries: scheduling bounded rebootstrap %d/%d for %s",
            self._empty_table_rebootstrap_attempts,
            self._max_empty_table_rebootstrap_attempts,
            reason,
        )

        async def _run() -> None:
            try:
                await self.rebootstrap()
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.debug("DHT scheduled rebootstrap failed: %s", exc)
                self.last_bootstrap_state = f"failed:{type(exc).__name__}"

        bootstrap_task = asyncio.create_task(_run())
        _ = bootstrap_task
        return True

    async def _bootstrap_step(self, host: str, port: int) -> bool:
        """Attempt to bootstrap from a single host:port. Returns False on error.

        Tracks performance for dynamic bootstrap node selection.
        """
        bootstrap_key = (host, port)
        if not self._can_attempt_bootstrap_node(bootstrap_key):
            self.logger.debug(
                "Skipping bootstrap node %s:%s due recent duplicate failures",
                host,
                port,
            )
            self.last_bootstrap_failure_reason = (
                f"bootstrap_retry_suppressed:{host}:{port}"
            )
            return False
        if self._is_dns_host_in_backoff(host):
            remaining = self._dns_host_backoff_remaining_s(host)
            self.last_bootstrap_failure_reason = f"dns_host_backoff:{host}"
            self.logger.debug(
                "Skipping bootstrap DNS for %s:%s: host-level backoff active (%.1fs remaining)",
                host,
                port,
                remaining,
            )
            return False
        start_time = time.time()

        try:
            # Note: Use async DNS resolution with timeout to prevent hanging
            # socket.gethostbyname() is blocking and can hang indefinitely
            try:
                # Use asyncio.to_thread() to run blocking DNS resolution in thread pool
                # This prevents blocking the event loop and allows timeout
                if hasattr(asyncio, "to_thread"):
                    # Python 3.9+
                    addr_info = await asyncio.wait_for(
                        asyncio.to_thread(
                            socket.getaddrinfo,
                            host,
                            port,
                            family=socket.AF_INET,
                            type=socket.SOCK_DGRAM,
                        ),
                        timeout=5.0,
                    )
                else:
                    # Python 3.7-3.8: use run_in_executor
                    loop = asyncio.get_event_loop()
                    addr_info = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            socket.getaddrinfo,
                            host,
                            port,
                            socket.AF_INET,
                            socket.SOCK_DGRAM,
                        ),
                        timeout=5.0,
                    )
                # Extract IPv4 address from first result
                addr = (addr_info[0][4][0], port)
                self._clear_dns_host_backoff(host)
            except asyncio.TimeoutError:
                self.last_bootstrap_failure_reason = f"dns_timeout:{host}:{port}"
                self._record_dns_host_failure(host)
                self._mark_bootstrap_attempt_failed(bootstrap_key)
                self.logger.debug(
                    "DNS resolution timeout for bootstrap node %s:%s", host, port
                )
                return False
            except Exception as dns_error:
                self.last_bootstrap_failure_reason = (
                    f"dns_failed:{host}:{port}:{type(dns_error).__name__}"
                )
                self._record_dns_host_failure(host)
                self._mark_bootstrap_attempt_failed(bootstrap_key)
                self.logger.debug(
                    "DNS resolution failed for bootstrap node %s:%s: %s",
                    host,
                    port,
                    dns_error,
                )
                return False

            # Use query_timeout for _find_nodes (already has timeout via asyncio.wait_for)
            await self._find_nodes(addr, self.node_id)

            # Track successful bootstrap
            response_time = time.time() - start_time
            self._mark_bootstrap_attempt_succeeded(bootstrap_key)
            if bootstrap_key not in self.bootstrap_performance:
                self.bootstrap_performance[bootstrap_key] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "response_times": [],
                    "last_success": 0.0,
                    "last_failure": 0.0,
                    "last_failure_reason": "",
                }

            perf = self.bootstrap_performance[bootstrap_key]
            perf["success_count"] += 1
            perf["last_success"] = time.time()
            perf["last_failure_reason"] = ""
            perf["response_times"].append(response_time)
            if len(perf["response_times"]) > 10:
                perf["response_times"].pop(0)

            return True
        except Exception as e:
            self.logger.debug("Bootstrap failed for %s:%s: %s", host, port, e)
            self.last_bootstrap_failure_reason = (
                f"bootstrap_failed:{host}:{port}:{type(e).__name__}"
            )
            self._mark_bootstrap_attempt_failed(bootstrap_key)

            # Track failed bootstrap
            response_time = time.time() - start_time
            if bootstrap_key not in self.bootstrap_performance:
                self.bootstrap_performance[bootstrap_key] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "response_times": [],
                    "last_success": 0.0,
                    "last_failure": 0.0,
                    "last_failure_reason": "",
                }

            perf = self.bootstrap_performance[bootstrap_key]
            perf["failure_count"] += 1
            perf["last_failure"] = time.time()
            perf["last_failure_reason"] = type(e).__name__
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

            success_rate = (
                success_count / total_attempts if total_attempts > 0 else 0.5
            )  # Unknown = neutral

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
            performance_score = (
                (success_rate * 0.5) + (time_score * 0.3) + (recency_score * 0.2)
            )

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
    ) -> Optional[dict[bytes, Any]]:
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

    async def _query_node_for_get(
        self,
        node: DHTNode,
        key: bytes,
        _public_key: Optional[bytes] = None,
        seq: Optional[int] = None,
    ) -> Optional[dict[bytes, Any]]:
        """Query a single node for BEP 44 get (find_value).

        Args:
            node: DHT node to query
            key: 20-byte target key (SHA-1 of value for immutable, SHA-1(pubkey+salt) for mutable)
            public_key: Optional public key for mutable get (seq filter not yet used)
            seq: Optional sequence number for mutable get (only return if stored seq > seq)

        Returns:
            Response dict or None on failure
        """
        try:
            args: dict[bytes, Any] = {
                b"id": self.node_id,
                b"target": key,
            }
            if seq is not None:
                args[b"seq"] = seq
            response = await self._send_query(
                (node.ip, node.port),
                "get",
                args,
            )
            if response and response.get(b"y") == b"r":
                self.routing_table.mark_node_good(node.node_id)
                return response
            self.routing_table.mark_node_bad(node.node_id)
            return None
        except Exception as e:
            self.logger.debug(
                "get (BEP 44) query failed for %s:%s: %s",
                node.ip,
                node.port,
                e,
            )
            self.routing_table.mark_node_bad(node.node_id)
            return None

    def _parse_get_response(
        self,
        response: dict[bytes, Any],
        target_key: bytes,
        _public_key: Optional[bytes] = None,
        salt: Optional[bytes] = None,
    ) -> Optional[tuple[Optional[bytes], Optional[bytes], bytes, bytes]]:
        """Parse BEP 44 get response and validate value.

        For mutable items, salt is not returned by the node (BEP 44); pass salt
        if the item was stored with salt so signature verification can succeed.

        Returns:
            (value_bytes, token, nodes, nodes6) or None if invalid.
            value_bytes may be None if node had no value but returned token and nodes.
        """
        if response.get(b"y") != b"r":
            return None
        r = response.get(b"r", {})
        if not isinstance(r, dict):
            return None
        token = r.get(b"token")
        nodes = r.get(b"nodes", b"")
        nodes6 = r.get(b"nodes6", b"")
        if not isinstance(nodes, bytes):
            nodes = b""
        if not isinstance(nodes6, bytes):
            nodes6 = b""

        v = r.get(b"v")
        if v is None:
            return (None, token, nodes, nodes6)

        # Mutable: response has top-level k, v, seq, sig (salt not in response)
        k = r.get(b"k")
        if k is not None:
            from ccbt.core.bencode import BencodeEncoder
            from ccbt.discovery.dht_storage import (
                calculate_mutable_key,
                verify_mutable_data_signature,
            )

            seq = r.get(b"seq")
            sig = r.get(b"sig")
            data = v if isinstance(v, bytes) else BencodeEncoder().encode(v)
            if not isinstance(data, bytes):
                return None
            salt_b = salt if salt is not None else b""
            key_calc = calculate_mutable_key(k, salt_b)
            if key_calc != target_key:
                return None
            if seq is None or not sig:
                return None
            if not verify_mutable_data_signature(data, k, sig, seq, salt_b):
                return None
            value_bytes = data if isinstance(v, bytes) else BencodeEncoder().encode(v)
            return (value_bytes, token, nodes, nodes6)

        # Immutable: key = SHA-1(v)
        from ccbt.core.bencode import BencodeEncoder
        from ccbt.discovery.dht_storage import calculate_immutable_key

        value_bytes = v if isinstance(v, bytes) else BencodeEncoder().encode(v)
        key_calc = calculate_immutable_key(value_bytes)
        if key_calc != target_key:
            return None
        return (value_bytes, token, nodes, nodes6)

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
        dist1 = self.routing_table.distance(node_id1, target_id)
        dist2 = self.routing_table.distance(node_id2, target_id)
        return dist1 < dist2

    async def _get_data_iterative(
        self,
        key: bytes,
        public_key: Optional[bytes] = None,
        salt: Optional[bytes] = None,
        alpha: int = 3,
        k: int = 8,
        max_depth: int = 10,
    ) -> tuple[Optional[bytes], list[tuple[bytes, tuple[str, int]]]]:
        """Iterative BEP 44 get (find_value): find key in DHT and collect tokens for put.

        Returns:
            (value_bytes or None, list of (token, (ip, port)) for nodes that responded)
        """
        queried_nodes: set[bytes] = set()
        closest_nodes = self.routing_table.get_closest_nodes(key, k)
        closest_set: set[DHTNode] = set(closest_nodes)
        found_value: Optional[bytes] = None
        tokens_with_addr: list[tuple[bytes, tuple[str, int]]] = []
        token_expires = time.time() + 900.0

        for _ in range(max_depth):
            unqueried = [n for n in closest_set if n.node_id not in queried_nodes]
            if not unqueried:
                break
            query_nodes = unqueried[:alpha]
            responses = await asyncio.gather(
                *[
                    self._query_node_for_get(node, key, public_key, None)
                    for node in query_nodes
                ]
            )
            for node, response in zip(query_nodes, responses):
                queried_nodes.add(node.node_id)
                if response is None:
                    continue
                parsed = self._parse_get_response(response, key, public_key, salt)
                if parsed is None:
                    continue
                value_bytes, token, nodes_b, _nodes6_b = parsed
                if token:
                    tokens_with_addr.append((token, (node.ip, node.port)))
                if value_bytes is not None:
                    found_value = value_bytes
                # Merge nodes from response into routing table and closest set
                for i in range(0, len(nodes_b), 26):
                    if i + 26 <= len(nodes_b):
                        node_data = nodes_b[i : i + 26]
                        nid = node_data[:20]
                        ip_str = ".".join(str(b) for b in node_data[20:24])
                        port_val = int.from_bytes(node_data[24:26], "big")
                        new_node = DHTNode(nid, ip_str, port_val)
                        self.routing_table.add_node(new_node)
                        if len(closest_set) < k * 2:
                            closest_set.add(new_node)
                        else:
                            farthest = max(
                                list(closest_set),
                                key=lambda n: self.routing_table.distance(
                                    n.node_id, key
                                ),
                            )
                            if self.routing_table.distance(
                                nid, key
                            ) < self.routing_table.distance(farthest.node_id, key):
                                closest_set.discard(farthest)
                                closest_set.add(new_node)
            if found_value is not None:
                break
            if len(queried_nodes) >= k * 2:
                break

        if tokens_with_addr:
            self._storage_tokens[key] = (tokens_with_addr, token_expires)
        return (found_value, tokens_with_addr)

    async def _get_storage_tokens_for_key(
        self,
        key: bytes,
        min_count: int = 1,
        public_key: Optional[bytes] = None,
        salt: Optional[bytes] = None,
    ) -> list[tuple[bytes, tuple[str, int]]]:
        """Get write tokens for key by running BEP 44 get if needed.

        Returns list of (token, (ip, port)) for nodes that responded (for put).
        """
        if key in self._storage_tokens:
            tokens_list, expires_at = self._storage_tokens[key]
            if time.time() < expires_at and len(tokens_list) >= min_count:
                return tokens_list[:8]
        _value, tokens_with_addr = await self._get_data_iterative(
            key, public_key=public_key, salt=salt
        )
        return tokens_with_addr[:8]

    async def _send_put(
        self,
        addr: tuple[str, int],
        _key: bytes,  # unused for BEP 44 message; used by caller for token lookup
        token: bytes,
        value: bytes,
        is_mutable: bool = False,
        public_key: Optional[bytes] = None,
        seq: int = 0,
        signature: Optional[bytes] = None,
        salt: Optional[bytes] = None,
    ) -> bool:
        """Send BEP 44 put request to one node. Returns True if stored successfully."""
        if len(value) > 1000:
            self.logger.debug("BEP 44 put: value too large (%d > 1000)", len(value))
            return False
        args: dict[bytes, Any] = {
            b"id": self.node_id,
            b"token": token,
            b"v": value,
        }
        if is_mutable and public_key is not None and signature is not None:
            args[b"k"] = public_key
            args[b"seq"] = seq
            args[b"sig"] = signature
            if salt:
                args[b"salt"] = salt
        try:
            response = await self._send_query(addr, "put", args)
            if response is None:
                return False
            if response.get(b"y") == b"e":
                err = response.get(b"e", [])
                code = err[0] if isinstance(err, (list, tuple)) and err else None
                self.logger.debug(
                    "BEP 44 put error from %s:%s: %s", addr[0], addr[1], code
                )
                return False
            return response.get(b"y") == b"r"
        except Exception as e:
            self.logger.debug("BEP 44 put failed for %s:%s: %s", addr[0], addr[1], e)
            return False

    async def _put_data_iterative(
        self,
        key: bytes,
        value: bytes,
        is_mutable: bool = False,
        public_key: Optional[bytes] = None,
        seq: int = 0,
        signature: Optional[bytes] = None,
        salt: Optional[bytes] = None,
    ) -> int:
        """Replicate value to DHT via BEP 44 put to nodes that returned tokens for key.

        For immutable, key is ignored for token lookup; tokens are for target=SHA-1(value).
        Returns number of nodes that accepted the put.
        """
        if len(value) > 1000:
            self.logger.debug("BEP 44 put_data_iterative: value too large")
            return 0
        if is_mutable and (public_key is None or signature is None):
            self.logger.debug("BEP 44 mutable put requires public_key and signature")
            return 0

        if is_mutable:
            token_keys = await self._get_storage_tokens_for_key(
                key, min_count=1, public_key=public_key, salt=salt
            )
        else:
            from ccbt.discovery.dht_storage import calculate_immutable_key

            target = calculate_immutable_key(value)
            token_keys = await self._get_storage_tokens_for_key(target, min_count=1)
        if not token_keys:
            self.logger.debug("BEP 44 put_data_iterative: no tokens for key")
            return 0

        success = 0
        for token, addr in token_keys:
            ok = await self._send_put(
                addr,
                key,
                token,
                value,
                is_mutable=is_mutable,
                public_key=public_key,
                seq=seq,
                signature=signature,
                salt=salt,
            )
            if ok:
                success += 1
        return success

    async def get_peers(
        self,
        info_hash: bytes,
        max_peers: int = 50,
        alpha: int = 3,  # Parallel queries (BEP 5)
        k: int = 8,  # Bucket size
        max_depth: Optional[int] = None,  # Override max depth (default: 10)
    ) -> list[tuple[str, int]]:
        """Get peers for an info hash using proper Kademlia iterative lookup (BEP 5).

        Implements iterative lookup algorithm:
        1. Query alpha closest unqueried nodes in parallel
        2. Collect peers from responses
        3. Update closest nodes set with returned nodes
        4. Continue until k nodes queried or no closer nodes found

        Args:
            info_hash: Torrent info hash
            max_peers: Maximum number of peers to return
            alpha: Number of parallel queries (default 3, BEP 5)
            k: Bucket size (default 8, BEP 5)
            max_depth: Maximum recursion depth (default 10, None for unlimited)

        Returns:
            List of (ip, port) tuples

        """
        # BEP 27: Private torrents must not use DHT for peer discovery
        if self.is_private_torrent and self.is_private_torrent(info_hash):
            self.logger.debug(
                "Skipping DHT get_peers for private torrent %s (BEP 27)",
                info_hash.hex()[:8],
            )
            self.last_lookup_state = "skipped_private"
            return []
        if self.is_swarm_discovery_disabled and self.is_swarm_discovery_disabled(
            info_hash
        ):
            self.logger.debug(
                "Skipping DHT get_peers for authenticated strict discovery mode %s",
                info_hash.hex()[:8],
            )
            try:
                from ccbt.monitoring import get_metrics_collector
                from ccbt.monitoring.metrics_collector import MetricLabel
                from ccbt.security import SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL

                get_metrics_collector().increment_counter(
                    SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL,
                    labels=[
                        MetricLabel(name="mode", value="strict"),
                        MetricLabel(name="component", value="dht"),
                    ],
                )
            except Exception:  # pragma: no cover - optional metrics path
                pass
            self.last_lookup_state = "swarm_discovery_disabled"
            return []

        # Use a set to track unique peers (deduplication)
        peers_set: set[tuple[str, int]] = set()
        queried_nodes: set[bytes] = set()
        self.last_lookup_state = "started"

        # Get initial k closest nodes
        closest_nodes = self.routing_table.get_closest_nodes(info_hash, k)
        closest_set: set[DHTNode] = set(closest_nodes)
        if not closest_set:
            self.last_lookup_state = "empty_routing_table"
            self.last_zero_node_lookup_at = time.time()
            self._log_empty_routing_warning(
                f"DHT lookup for {info_hash.hex()[:8]} cannot start because the routing table "
                f"is empty (queried 0 nodes). Bootstrap is missing, blocked, or has not completed yet."
            )
            self._last_query_metrics = {
                "duration": 0.0,
                "peers_found": 0,
                "depth": 0,
                "nodes_queried": 0,
                "alpha": alpha,
                "k": k,
                "max_depth": max_depth if max_depth is not None else 10,
                "empty_result_reason": "empty_routing_table",
                "zero_node_lookup": True,
                "lookup_state": self.last_lookup_state,
                "empty_table_retry_scheduled": self._schedule_zero_node_rebootstrap(
                    reason=f"get_peers:{info_hash.hex()[:8]}"
                ),
            }
            return []

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
        max_nodes_to_query = max(
            k * 2, 50
        )  # Query at least k*2 nodes, up to 50 for better coverage
        while (
            len(queried_nodes) < max_nodes_to_query
            and closest_set
            and query_depth < effective_max_depth
        ):
            query_depth += 1

            # Get alpha closest unqueried nodes
            unqueried = [n for n in closest_set if n.node_id not in queried_nodes]

            if not unqueried:
                # Try to get more nodes from routing table
                additional_nodes = self.routing_table.get_closest_nodes(
                    info_hash, k * 3
                )
                for new_node in additional_nodes:
                    if (
                        new_node.node_id not in queried_nodes
                        and new_node not in closest_set
                    ):
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

            # Select alpha nodes for parallel query
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
                self._query_node_for_peers(node, info_hash) for node in query_nodes
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

                                # Note: Invoke callbacks immediately when peers are found
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
                                                "info_hash": info_hash.hex()
                                                if isinstance(info_hash, bytes)
                                                else str(info_hash),
                                                "node_ip": node.ip,
                                                "node_port": node.port,
                                                "query_depth": query_depth,
                                            },
                                        )
                                    )
                                except Exception as e:
                                    self.logger.debug(
                                        "Failed to emit DHT peer_found event: %s", e
                                    )

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
                            new_distance = self.routing_table.distance(
                                node_id, info_hash
                            )

                            if len(closest_set) < k:
                                # Always add if we haven't reached k nodes yet
                                closest_set.add(new_node)
                                found_closer_nodes = True
                            elif closest_set:
                                # Check if this node is closer than the farthest node in closest_set
                                # Note: Use list() to avoid set modification during iteration
                                farthest_node = max(
                                    list(closest_set),
                                    key=lambda n: self.routing_table.distance(
                                        n.node_id, info_hash
                                    ),
                                )
                                farthest_distance = self.routing_table.distance(
                                    farthest_node.node_id, info_hash
                                )

                                if new_distance < farthest_distance:
                                    # Replace farthest with this closer node
                                    # Note: Check if node still exists before removing (race condition fix)
                                    closest_set.discard(farthest_node)
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
                                                "node_id": node_id.hex()
                                                if isinstance(node_id, bytes)
                                                else str(node_id),
                                                "ip": ip,
                                                "port": port,
                                                "info_hash": info_hash.hex()
                                                if isinstance(info_hash, bytes)
                                                else str(info_hash),
                                            },
                                        )
                                    )
                                    await emit_event(
                                        Event(
                                            event_type="dht_node_added",
                                            data={
                                                "node_id": node_id.hex()
                                                if isinstance(node_id, bytes)
                                                else str(node_id),
                                                "ip": ip,
                                                "port": port,
                                            },
                                        )
                                    )
                                except Exception as e:
                                    self.logger.debug(
                                        "Failed to emit DHT node event: %s", e
                                    )

                # Store token for announce_peer
                token = r.get(b"token")
                if token:
                    token_entry = DHTToken(
                        token,
                        info_hash,
                        (node.ip, node.port),
                    )
                    self.tokens[(info_hash, (node.ip, node.port))] = token_entry
                    # Keep a legacy info_hash alias for compatibility with older
                    # diagnostics/tests while scoped tokens remain authoritative.
                    self.tokens[info_hash] = token_entry

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
                additional_nodes = self.routing_table.get_closest_nodes(
                    info_hash, k * 3
                )
                added_new_nodes = False
                for new_node in additional_nodes:
                    if (
                        new_node.node_id not in queried_nodes
                        and new_node not in closest_set
                    ):
                        closest_set.add(new_node)
                        found_closer_nodes = True
                        added_new_nodes = True

                if not added_new_nodes:
                    # No more unqueried nodes available, but continue if we haven't queried enough yet
                    if (
                        len(queried_nodes) < max_nodes_to_query
                        and query_depth < effective_max_depth
                    ):
                        # Try to expand search by getting nodes from different buckets
                        all_routing_nodes = list(self.routing_table.nodes.values())
                        for node in all_routing_nodes:
                            if (
                                node.node_id not in queried_nodes
                                and node not in closest_set
                            ):
                                closest_set.add(node)
                                found_closer_nodes = True
                                break

                    # Only stop if we've queried enough nodes OR reached max depth
                    if not found_closer_nodes and (
                        len(queried_nodes) >= max_nodes_to_query
                        or query_depth >= effective_max_depth
                    ):
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
        # Note: Always invoke callbacks with final peer list, even if empty
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
            if nodes_queried_count > 0:
                routing_table_size = len(self.routing_table.nodes)
                self.logger.info(
                    "DHT get_peers for %s returned 0 peers after querying %d nodes (depth=%d, routing table=%d nodes). This usually indicates a thin swarm or peers not currently announcing.",
                    info_hash.hex()[:16],
                    nodes_queried_count,
                    query_depth,
                    routing_table_size,
                )
            else:
                self.logger.debug(
                    "DHT get_peers for %s returned 0 peers because no nodes could be queried.",
                    info_hash.hex()[:16],
                )

        # Emit DHT query complete event
        try:
            from ccbt.utils.events import Event, emit_event

            await emit_event(
                Event(
                    event_type="dht_query_complete",
                    data={
                        "info_hash": info_hash.hex()
                        if isinstance(info_hash, bytes)
                        else str(info_hash),
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
        if not hasattr(self, "_last_query_metrics"):
            self._last_query_metrics = {}
        query_duration = time.time() - getattr(self, "_query_start_time", time.time())
        self._last_query_metrics = {
            "duration": query_duration,
            "peers_found": len(peers),
            "depth": query_depth,
            "nodes_queried": len(queried_nodes),
            "alpha": alpha,
            "k": k,
            "max_depth": effective_max_depth,
            "empty_result_reason": (
                "query_zero_nodes" if nodes_queried_count == 0 else "empty_peer_set"
            ),
            "zero_node_lookup": len(queried_nodes) == 0,
        }
        if len(queried_nodes) == 0:
            self.last_lookup_state = "query_zero_nodes"
        elif not peers:
            self.last_lookup_state = "empty_peer_set"
        else:
            self.last_lookup_state = "peers_found"

        self._last_query_metrics["lookup_state"] = self.last_lookup_state
        if len(queried_nodes) == 0:
            self.last_zero_node_lookup_at = time.time()
            self.logger.warning(
                "DHT lookup for %s completed with queried 0 nodes. Treating this as bootstrap-missing rather than a normal empty peer result.",
                info_hash.hex()[:8],
            )

        return peers

    async def announce_peer(self, info_hash: bytes, port: int) -> int:
        """Announce our peer to the DHT.

        Args:
            info_hash: Torrent info hash
            port: Our port

        Returns:
            Number of peers announced (0 if failed or read-only, 1 if successful)

        """
        # BEP 43: Read-only nodes skip announce_peer
        if self.read_only:
            self.logger.debug(
                "Skipping DHT announce_peer for read-only node (BEP 43)",
            )
            return 0

        # BEP 27: Private torrents must not use DHT for peer announcements
        if self.is_private_torrent and self.is_private_torrent(info_hash):
            self.logger.debug(
                "Skipping DHT announce_peer for private torrent %s (BEP 27)",
                info_hash.hex()[:8],
            )
            return 0
        if self.is_swarm_discovery_disabled and self.is_swarm_discovery_disabled(
            info_hash
        ):
            self.logger.debug(
                "Skipping DHT announce_peer for authenticated strict discovery mode %s",
                info_hash.hex()[:8],
            )
            try:
                from ccbt.monitoring import get_metrics_collector
                from ccbt.monitoring.metrics_collector import MetricLabel
                from ccbt.security import SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL

                get_metrics_collector().increment_counter(
                    SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL,
                    labels=[
                        MetricLabel(name="mode", value="strict"),
                        MetricLabel(name="component", value="dht"),
                    ],
                )
            except Exception:  # pragma: no cover - optional metrics path
                pass
            return 0

        # Get token(s) for this info hash
        token_entries = [
            token
            for token in self.tokens.values()
            if getattr(token, "info_hash", None) == info_hash
        ]
        if not token_entries:
            # Try to get token by doing a get_peers query
            await self.get_peers(info_hash, 1)
            token_entries = [
                token
                for token in self.tokens.values()
                if getattr(token, "info_hash", None) == info_hash
            ]

        if not token_entries:
            self.logger.debug("No token available for %s", info_hash.hex())
            return 0

        # Find closest nodes to announce to
        closest_nodes = self.routing_table.get_closest_nodes(info_hash, 8)
        has_scoped_tokens = any(
            isinstance(token_key, tuple)
            and len(token_key) == 2
            and token_key[0] == info_hash
            for token_key in self.tokens
        )

        success_count = 0
        for node in closest_nodes:
            try:
                token_key: Union[bytes, tuple[bytes, tuple[str, int]]] = (
                    info_hash,
                    (node.ip, node.port),
                )
                token = self.tokens.get(token_key)
                if token is None and not has_scoped_tokens:
                    token_key = info_hash
                    token = self.tokens.get(info_hash)
                if token is None:
                    continue
                if time.time() > token.expires_time:
                    del self.tokens[token_key]
                    continue
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

        return success_count

    def _xet_chunk_dht_key(self, chunk_hash: bytes) -> bytes:
        """Derive 20-byte DHT key from XET chunk hash (32 bytes).

        Uses first 20 bytes of chunk_hash so store_chunk_hash and get_chunk_peers
        use the same key for DHT and local store.
        """
        if len(chunk_hash) >= 20:
            return chunk_hash[:20]
        return chunk_hash + b"\x00" * (20 - len(chunk_hash))

    async def get_data(
        self,
        key: bytes,
        _public_key: Optional[bytes] = None,
        _salt: Optional[bytes] = None,
    ) -> Optional[bytes]:
        """Get data from DHT (BEP 44) or local XET mutable store.

        When dht_enable_storage is True, performs iterative BEP 44 get in the DHT
        and returns the value if found; otherwise falls back to local store.

        Args:
            key: Data key (20 bytes)
            _public_key: Optional public key for mutable data verification
            _salt: Optional salt for mutable items (not returned by nodes per BEP 44)

        Returns:
            Retrieved data bytes, or None if not found

        """
        self.logger.debug("get_data called for key: %s", key.hex()[:16])
        try:
            if get_config().discovery.dht_enable_storage and len(key) == 20:
                value, _ = await self._get_data_iterative(
                    key, public_key=_public_key, salt=_salt
                )
                if value is not None:
                    self._xet_mutable_store[key] = value
                    return value
        except Exception as e:
            self.logger.debug("DHT get_data iterative failed: %s", e)
        return self._xet_mutable_store.get(key)

    async def put_data(
        self,
        key: bytes,
        value: Union[bytes, dict[bytes, bytes]],
    ) -> int:
        """Put data into local store and optionally replicate via BEP 44 DHT put.

        When dht_enable_storage is True and not read-only, also performs BEP 44
        immutable put to the DHT (get tokens for SHA-1(value), then put to nodes).

        Args:
            key: Data key (20 bytes) for local store
            value: Data value to store (bytes or dict for BEP 44 format)

        Returns:
            Number of successful storage operations (1 if stored locally, plus DHT count)

        """
        # BEP 43: Read-only nodes skip put_data
        if self.read_only:
            self.logger.debug(
                "Skipping DHT put_data for read-only node (BEP 43)",
            )
            return 0

        self.logger.debug(
            "put_data called for key: %s, value size: %d",
            key.hex()[:16],
            len(value) if isinstance(value, bytes) else len(str(value)),
        )
        if isinstance(value, bytes):
            encoded_value = value
        else:
            # BEP 44: immutable key is SHA-1(bencode(v)); use bencoding for
            # cross-node interoperability (JSON would yield a different key).
            encoded_value = BencodeEncoder().encode(value)
        self._xet_mutable_store[key] = encoded_value
        local_count = 1

        try:
            if get_config().discovery.dht_enable_storage and len(encoded_value) <= 1000:
                dht_count = await self._put_data_iterative(
                    key, encoded_value, is_mutable=False
                )
                return local_count + dht_count
        except Exception as e:
            self.logger.debug("DHT put_data iterative failed: %s", e)

        self.logger.debug(
            "put_data stored locally only (no DHT replication): dht_enable_storage=%s, value_size=%d (BEP 44 limit 1000)",
            get_config().discovery.dht_enable_storage,
            len(encoded_value),
        )
        return local_count

    async def store_chunk_hash(
        self, chunk_hash: bytes, metadata: dict[str, Any]
    ) -> int:
        """Store XET chunk availability metadata under a stable chunk key."""
        key = self._xet_chunk_dht_key(chunk_hash)
        existing_records: list[dict[str, Any]] = []
        existing = await self.get_data(key)
        if existing is not None:
            with contextlib.suppress(Exception):
                parsed_existing = json.loads(existing.decode("utf-8"))
                if isinstance(parsed_existing, list):
                    existing_records = [
                        record for record in parsed_existing if isinstance(record, dict)
                    ]
        existing_records.append(dict(metadata))
        encoded = json.dumps(
            existing_records,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return await self.put_data(key, encoded)

    async def get_chunk_peers(self, chunk_hash: bytes) -> list[PeerInfo]:
        """Return XET chunk peers stored under the chunk key."""
        key = self._xet_chunk_dht_key(chunk_hash)
        encoded = await self.get_data(key)
        if encoded is None:
            return []
        try:
            parsed = json.loads(encoded.decode("utf-8"))
        except Exception:
            self.logger.debug("Failed to decode XET chunk peers", exc_info=True)
            return []
        if not isinstance(parsed, list):
            return []
        peers: list[PeerInfo] = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            ip = entry.get("ip")
            port = entry.get("port")
            if isinstance(ip, str) and isinstance(port, int):
                peers.append(
                    PeerInfo(
                        ip=ip,
                        port=port,
                        peer_source="dht-xet",
                    )
                )
        return peers

    async def index_infohash(
        self,
        info_hash: bytes,
        name: str,
        size: int,
        public_key: bytes,
        private_key: bytes,
        salt: bytes = b"",
    ) -> bytes:
        """Index an infohash in the DHT (BEP 51).

        Args:
            info_hash: Torrent info hash (20 bytes)
            name: Torrent name
            size: Torrent size in bytes
            public_key: Public key for signing
            private_key: Private key for signing
            salt: Optional salt

        Returns:
            Index key (20 bytes)

        """
        from ccbt.discovery.dht_indexing import store_infohash_sample

        return await store_infohash_sample(
            info_hash=info_hash,
            name=name,
            size=size,
            public_key=public_key,
            private_key=private_key,
            salt=salt,
            dht_client=self,
        )

    async def query_infohash_index(
        self,
        query: str,
        max_results: int = 50,
        public_key: Optional[bytes] = None,
    ) -> list:
        """Query the infohash index (BEP 51).

        Args:
            query: Query string (e.g., torrent name)
            max_results: Maximum number of results to return
            public_key: Optional public key for querying mutable items

        Returns:
            List of matching infohash samples

        """
        from ccbt.discovery.dht_indexing import query_index

        return await query_index(
            query=query,
            max_results=max_results,
            dht_client=self,
            public_key=public_key,
        )

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
    ) -> Optional[dict[bytes, Any]]:
        """Send a DHT query and wait for response, tracking response time for quality metrics."""
        # Calculate adaptive timeout based on peer health
        query_timeout = self._calculate_adaptive_query_timeout()
        if is_shutting_down():
            query_timeout = min(query_timeout, 1.0)

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
        response_time: Optional[float] = None

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
            response_time = (
                query_timeout  # Use timeout as response time for failed queries
            )
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
                    if (
                        node.has_ipv6
                        and node.ipv6
                        and node.port6
                        and (node.ipv6, node.port6) == addr
                    ):
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
        """Handle incoming DHT response (legacy; use handle_datagram)."""
        self.handle_datagram(data, _addr)

    def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram: dispatch query (y=q) or response (y=r/e)."""
        try:
            message = BencodeDecoder(data).decode()
        except Exception as e:
            self.logger.debug("Failed to parse DHT datagram: %s", e)
            return
        y = message.get(b"y")
        if y == b"q":
            self._handle_request(message, addr)
            return
        if y in (b"r", b"e"):
            tid = message.get(b"t")
            if tid and tid in self.pending_queries:
                future = self.pending_queries[tid]
                if not future.done():
                    future.set_result(message)
            return

    def _handle_request(self, message: dict[bytes, Any], addr: tuple[str, int]) -> None:
        """Dispatch incoming DHT query to get/put/find_node/get_peers/announce_peer."""
        a = message.get(b"a")
        t = message.get(b"t")
        if not isinstance(a, dict) or t is None:
            return
        node_id = a.get(b"id")
        if node_id is not None and len(node_id) == 20:
            with contextlib.suppress(Exception):
                self.routing_table.add_node(DHTNode(node_id, addr[0], addr[1]))
        q = message.get(b"q")
        if q == b"get":
            if not get_config().discovery.dht_enable_storage:
                return
            self._handle_get_request(a, t, addr)
        elif q == b"put":
            if not get_config().discovery.dht_enable_storage:
                return
            self._handle_put_request(a, t, addr)
        elif q == b"find_node":
            self._handle_find_node_request(a, t, addr)
        elif q == b"get_peers":
            self._handle_get_peers_request(a, t, addr)
        elif q == b"announce_peer":
            self._handle_announce_peer_request(a, t, addr)

    def _send_error(
        self,
        t: Any,
        addr: tuple[str, int],
        code: int,
        msg: bytes,
    ) -> None:
        """Send BEP 44/5 error response (y=e, e=[code, msg])."""
        if self.transport is None:
            return
        try:
            err_msg = {
                b"t": t,
                b"y": b"e",
                b"e": [code, msg],
            }
            self.transport.sendto(BencodeEncoder().encode(err_msg), addr)
        except Exception as e:
            self.logger.debug("Failed to send DHT error: %s", e)

    def _issue_storage_token(self, addr: tuple[str, int], target: bytes) -> bytes:
        """Issue and store a BEP 44 write token for (addr, target)."""
        raw = (addr[0] + str(addr[1])).encode() + target
        token = hmac.new(self.token_secret, raw, digestmod="sha256").digest()[:32]
        self._storage_write_tokens[(addr, target)] = (
            token,
            time.time() + 900.0,
        )
        return token

    def _build_compact_nodes(
        self, target_id: bytes, count: int = 8
    ) -> tuple[bytes, bytes]:
        """Build compact nodes (26 bytes/node) and nodes6 (38 bytes/node) for target."""
        closest = self.routing_table.get_closest_nodes(target_id, count)
        nodes_list: list[bytes] = []
        for n in closest:
            with contextlib.suppress(OSError, ValueError):
                nodes_list.append(
                    n.node_id
                    + socket.inet_pton(socket.AF_INET, n.ip)
                    + n.port.to_bytes(2, "big")
                )
        nodes = b"".join(nodes_list)
        nodes6_list: list[bytes] = []
        for n in closest:
            ipv6_str = getattr(n, "ipv6", None)
            port6_val = getattr(n, "port6", None)
            if (
                getattr(n, "has_ipv6", False)
                and ipv6_str is not None
                and port6_val is not None
            ):
                with contextlib.suppress(OSError, ValueError):
                    nodes6_list.append(
                        n.node_id
                        + socket.inet_pton(socket.AF_INET6, ipv6_str)
                        + port6_val.to_bytes(2, "big")
                    )
        nodes6 = b"".join(nodes6_list)
        return (nodes, nodes6)

    def _handle_get_request(
        self,
        a: dict[bytes, Any],
        t: Any,
        addr: tuple[str, int],
    ) -> None:
        """Handle BEP 44 get: return token, nodes, nodes6, and value if stored."""
        target = a.get(b"target")
        if not target or len(target) != 20:
            self._send_error(t, addr, 203, b"invalid target")
            return
        token = self._issue_storage_token(addr, target)
        nodes, nodes6 = self._build_compact_nodes(target)
        r: dict[bytes, Any] = {
            b"id": self.node_id,
            b"token": token,
            b"nodes": nodes,
            b"nodes6": nodes6,
        }
        if target in self._xet_mutable_store:
            r[b"v"] = self._xet_mutable_store[target]
        if self.transport is None:
            return
        try:
            msg = {b"t": t, b"y": b"r", b"r": r}
            self.transport.sendto(BencodeEncoder().encode(msg), addr)
        except Exception as e:
            self.logger.debug("Failed to send get response: %s", e)

    def _handle_put_request(
        self,
        a: dict[bytes, Any],
        t: Any,
        addr: tuple[str, int],
    ) -> None:
        """Handle BEP 44 put: verify token/size/signature/seq, store value, send success or error."""
        if self.read_only:
            self._send_error(t, addr, 203, b"read-only node")
            return
        token = a.get(b"token")
        v = a.get(b"v")
        if token is None or v is None:
            self._send_error(t, addr, 203, b"missing token or value")
            return
        from ccbt.discovery.dht_storage import (
            MAX_STORAGE_VALUE_SIZE,
            calculate_immutable_key,
            calculate_mutable_key,
            verify_mutable_data_signature,
        )

        max_size = getattr(get_config().discovery, "dht_max_storage_size", None)
        if max_size is None:
            max_size = MAX_STORAGE_VALUE_SIZE
        value_bytes = v if isinstance(v, bytes) else BencodeEncoder().encode(v)
        if len(value_bytes) > max_size:
            self._send_error(t, addr, 205, b"message too big")
            return
        salt_val = a.get(b"salt")
        if salt_val is not None and len(salt_val) > 64:
            self._send_error(t, addr, 207, b"salt too big")
            return
        is_mutable = a.get(b"k") is not None
        if is_mutable:
            key = calculate_mutable_key(a[b"k"], a.get(b"salt", b""))
        else:
            key = calculate_immutable_key(value_bytes)
        lookup_key = (addr, key)
        if (
            lookup_key not in self._storage_write_tokens
            or self._storage_write_tokens[lookup_key][0] != token
        ):
            self._send_error(t, addr, 203, b"invalid token")
            return
        if is_mutable:
            k = a.get(b"k")
            seq = a.get(b"seq")
            sig = a.get(b"sig")
            salt_b = a.get(b"salt", b"")
            if k is None or seq is None or sig is None:
                self._send_error(t, addr, 203, b"missing k/seq/sig")
                return
            if not verify_mutable_data_signature(value_bytes, k, sig, seq, salt_b):
                self._send_error(t, addr, 206, b"invalid signature")
                return
            cas = a.get(b"cas")
            if cas is not None and self._storage_seq.get(key, 0) != cas:
                self._send_error(t, addr, 301, b"cas mismatch")
                return
            if seq <= self._storage_seq.get(key, 0):
                self._send_error(t, addr, 302, b"sequence number less than current")
                return
        self._xet_mutable_store[key] = value_bytes
        if is_mutable:
            self._storage_seq[key] = seq
        if self.transport is None:
            return
        try:
            success_msg = {
                b"t": t,
                b"y": b"r",
                b"r": {b"id": self.node_id},
            }
            self.transport.sendto(BencodeEncoder().encode(success_msg), addr)
        except Exception as e:
            self.logger.debug("Failed to send put response: %s", e)

    def _handle_find_node_request(
        self,
        a: dict[bytes, Any],
        t: Any,
        addr: tuple[str, int],
    ) -> None:
        """Handle BEP 5 find_node: return nodes and nodes6."""
        target = a.get(b"target")
        if not target or len(target) != 20:
            return
        nodes, nodes6 = self._build_compact_nodes(target)
        r = {
            b"id": self.node_id,
            b"nodes": nodes,
            b"nodes6": nodes6,
        }
        if self.transport is None:
            return
        try:
            self.transport.sendto(
                BencodeEncoder().encode({b"t": t, b"y": b"r", b"r": r}),
                addr,
            )
        except Exception as e:
            self.logger.debug("Failed to send find_node response: %s", e)

    def _issue_get_peers_token(self, addr: tuple[str, int], info_hash: bytes) -> bytes:
        """Issue and store a BEP 5 get_peers token for (addr, info_hash)."""
        raw = (addr[0] + str(addr[1])).encode() + info_hash
        token = hmac.new(self.token_secret, raw, digestmod="sha256").digest()[:32]
        self._get_peers_tokens[(addr, info_hash)] = (
            token,
            time.time() + 900.0,
        )
        return token

    def _handle_get_peers_request(
        self,
        a: dict[bytes, Any],
        t: Any,
        addr: tuple[str, int],
    ) -> None:
        """Handle BEP 5 get_peers: return token, nodes, nodes6, and values if stored."""
        info_hash = a.get(b"info_hash")
        if not info_hash or len(info_hash) != 20:
            return
        token = self._issue_get_peers_token(addr, info_hash)
        nodes, nodes6 = self._build_compact_nodes(info_hash)
        peers = self._peers_store.get(info_hash, [])[:50]
        values = []
        for ip, port in peers:
            with contextlib.suppress(OSError, ValueError):
                values.append(
                    socket.inet_pton(socket.AF_INET, ip) + port.to_bytes(2, "big")
                )
        r: dict[bytes, Any] = {
            b"id": self.node_id,
            b"token": token,
            b"nodes": nodes,
            b"nodes6": nodes6,
        }
        if values:
            r[b"values"] = values
        if self.transport is None:
            return
        try:
            self.transport.sendto(
                BencodeEncoder().encode({b"t": t, b"y": b"r", b"r": r}),
                addr,
            )
        except Exception as e:
            self.logger.debug("Failed to send get_peers response: %s", e)

    def _handle_announce_peer_request(
        self,
        a: dict[bytes, Any],
        t: Any,
        addr: tuple[str, int],
    ) -> None:
        """Handle BEP 5 announce_peer: verify token, store peer, send success."""
        info_hash = a.get(b"info_hash")
        token = a.get(b"token")
        port = a.get(b"port")
        if not info_hash or len(info_hash) != 20 or not token:
            return
        if not isinstance(port, int):
            return
        key = (addr, info_hash)
        if key not in self._get_peers_tokens or self._get_peers_tokens[key][0] != token:
            return
        peer = (addr[0], port)
        self._peers_store.setdefault(info_hash, [])
        if peer not in self._peers_store[info_hash]:
            self._peers_store[info_hash].append(peer)
        self._peers_store[info_hash] = self._peers_store[info_hash][-100:]
        if self.transport is None:
            return
        try:
            self.transport.sendto(
                BencodeEncoder().encode(
                    {
                        b"t": t,
                        b"y": b"r",
                        b"r": {b"id": self.node_id},
                    }
                ),
                addr,
            )
        except Exception as e:
            self.logger.debug("Failed to send announce_peer response: %s", e)

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
        return max(min_interval, min(max_interval, adaptive_interval))

    async def _refresh_loop(self) -> None:
        """Background task to refresh routing table with adaptive intervals."""
        while True:
            try:
                # Calculate adaptive interval based on swarm health
                interval = self._calculate_adaptive_interval()
                await asyncio.sleep(interval)
                if len(self.routing_table.nodes) == 0:
                    self._log_empty_routing_warning(
                        "DHT refresh detected empty routing table; triggering rebootstrap."
                    )
                    await self.rebootstrap()
                    continue
                await self._refresh_routing_table()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in refresh loop")

    async def _refresh_routing_table(self) -> None:
        """Refresh routing table by finding nodes."""
        if len(self.routing_table.nodes) == 0:
            self.logger.debug(
                "Skipping routing-table refresh because no nodes are currently available"
            )
            return
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
            token_key
            for token_key, token in self.tokens.items()
            if current_time > token.expires_time
        ]
        for token_key in expired_tokens:
            del self.tokens[token_key]

        # Clean up expired BEP 44 storage tokens
        expired_storage = [
            key
            for key, (_, expires_at) in self._storage_tokens.items()
            if current_time > expires_at
        ]
        for key in expired_storage:
            del self._storage_tokens[key]

        # Clean up expired BEP 44 server write tokens
        expired_write = [
            k
            for k, (_, exp) in self._storage_write_tokens.items()
            if current_time > exp
        ]
        for k in expired_write:
            del self._storage_write_tokens[k]

        # Clean up expired BEP 5 get_peers tokens
        expired_gp = [
            k for k, (_, exp) in self._get_peers_tokens.items() if current_time > exp
        ]
        for k in expired_gp:
            del self._get_peers_tokens[k]

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
                                "node_id": node_id.hex()
                                if isinstance(node_id, bytes)
                                else str(node_id),
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
        # Note: Add logging to verify callback invocations
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
            self.callback_metrics["peers_found_without_callbacks"] += len(peers)

        # Invoke global callbacks (no info_hash filtering)
        for idx, callback in enumerate(self.peer_callbacks):
            try:
                callback(peers)
                self.callback_metrics["peers_delivered_to_callbacks"] += len(peers)
                self.logger.info(
                    "Invoked global DHT peer callback #%d for info_hash %s (%d peers)",
                    idx + 1,
                    info_hash.hex()[:16] + "...",
                    len(peers),
                )
            except Exception:
                self.callback_metrics["callback_exceptions"] += 1
                self.logger.exception(
                    "Peer callback error (global callback #%d, info_hash=%s)",
                    idx + 1,
                    info_hash.hex()[:16] + "...",
                )

        # Invoke info_hash-specific callbacks
        if info_hash in self.peer_callbacks_by_hash:
            for idx, callback in enumerate(self.peer_callbacks_by_hash[info_hash]):
                try:
                    callback(peers)
                    self.callback_metrics["peers_delivered_to_callbacks"] += len(peers)
                    self.logger.info(
                        "Invoked info_hash-specific DHT peer callback #%d for info_hash %s (%d peers)",
                        idx + 1,
                        info_hash.hex()[:16] + "...",
                        len(peers),
                    )
                except Exception:
                    self.callback_metrics["callback_exceptions"] += 1
                    self.logger.exception(
                        "Peer callback error (info_hash=%s, callback #%d)",
                        info_hash.hex()[:8],
                        idx + 1,
                    )

    def add_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: Optional[bytes] = None,
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
            self.callback_metrics["callbacks_registered"] += 1
            self.logger.debug(
                "Registered DHT peer callback for info_hash %s (total callbacks for this hash: %d)",
                info_hash.hex()[:8],
                len(self.peer_callbacks_by_hash[info_hash]),
            )
        else:
            self.peer_callbacks.append(callback)
            self.callback_metrics["callbacks_registered"] += 1
            self.logger.debug(
                "Registered global DHT peer callback (total global callbacks: %d)",
                len(self.peer_callbacks),
            )

    def remove_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: Optional[bytes] = None,
    ) -> None:
        """Remove peer callback.

        Args:
            callback: Callback function to remove
            info_hash: Optional info hash. If provided, removes callback from
                      info_hash-specific list. If None, removes from global list.

        """
        if (
            info_hash is not None
            and info_hash in self.peer_callbacks_by_hash
            and callback in self.peer_callbacks_by_hash[info_hash]
        ):
            self.peer_callbacks_by_hash[info_hash].remove(callback)
            if not self.peer_callbacks_by_hash[info_hash]:
                del self.peer_callbacks_by_hash[info_hash]
        elif callback in self.peer_callbacks:
            self.peer_callbacks.remove(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get DHT statistics."""
        return {
            "node_id": self.node_id.hex(),
            "routing_table": self.routing_table.get_stats(),
            "tokens": len(self.tokens),
            "pending_queries": len(self.pending_queries),
            "empty_table_rebootstrap_attempts": self._empty_table_rebootstrap_attempts,
            "max_empty_table_rebootstrap_attempts": self._max_empty_table_rebootstrap_attempts,
            "empty_table_rebootstrap_backoff": self._empty_table_rebootstrap_backoff,
            "bootstrap_success_count": self.bootstrap_success_count,
            "bootstrap_failure_count": self.bootstrap_failure_count,
            "last_bootstrap_reason": self.last_bootstrap_reason,
            "last_bootstrap_failure_reason": self.last_bootstrap_failure_reason,
            "last_bootstrap_state": self.last_bootstrap_state,
            "last_lookup_state": self.last_lookup_state,
            "last_zero_node_lookup_at": self.last_zero_node_lookup_at,
        }


class DHTProtocol(asyncio.DatagramProtocol):
    """DHT protocol handler."""

    def __init__(self, client: AsyncDHTClient):
        """Initialize DHT protocol handler."""
        self.client = client

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        self.client.handle_datagram(data, addr)

    def error_received(self, exc: Exception) -> None:
        """Handle UDP error."""
        self.client.logger.debug("DHT error: %s", exc)


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
