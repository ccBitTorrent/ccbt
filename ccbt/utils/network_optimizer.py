"""Advanced network I/O optimizations for ccBitTorrent.

from __future__ import annotations

Provides socket optimizations, connection pooling, and advanced networking
features for maximum performance in BitTorrent operations.
"""

from __future__ import annotations

import builtins
import contextlib
import socket
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ccbt.utils.exceptions import NetworkError
from ccbt.utils.logging_config import get_logger


class SocketType(Enum):
    """Socket types for different use cases."""

    PEER_CONNECTION = "peer_connection"
    TRACKER_HTTP = "tracker_http"
    TRACKER_UDP = "tracker_udp"
    DHT = "dht"
    LISTENER = "listener"


@dataclass
class SocketConfig:
    """Socket configuration for optimization."""

    socket_type: SocketType
    tcp_nodelay: bool = True
    tcp_cork: bool = False
    so_reuseport: bool = False
    so_reuseaddr: bool = True
    so_keepalive: bool = True
    so_rcvbuf: int = 256 * 1024  # 256KB
    so_sndbuf: int = 256 * 1024  # 256KB
    so_rcvtimeo: float = 30.0
    so_sndtimeo: float = 30.0
    tcp_keepalive_idle: int = 600
    tcp_keepalive_interval: int = 60
    tcp_keepalive_probes: int = 3


@dataclass
class ConnectionStats:
    """Connection statistics."""

    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    connection_time: float = 0.0
    last_activity: float = 0.0


class SocketOptimizer:
    """Optimizes socket settings for different use cases."""

    def __init__(self) -> None:
        """Initialize socket optimizer."""
        self.configs: dict[SocketType, SocketConfig] = {
            SocketType.PEER_CONNECTION: SocketConfig(
                socket_type=SocketType.PEER_CONNECTION,
                tcp_nodelay=True,
                so_rcvbuf=512 * 1024,  # 512KB for peer connections
                so_sndbuf=512 * 1024,
                so_rcvtimeo=60.0,
                so_sndtimeo=60.0,
            ),
            SocketType.TRACKER_HTTP: SocketConfig(
                socket_type=SocketType.TRACKER_HTTP,
                tcp_nodelay=True,
                so_rcvbuf=64 * 1024,  # 64KB for HTTP
                so_sndbuf=64 * 1024,
                so_rcvtimeo=30.0,
                so_sndtimeo=30.0,
            ),
            SocketType.TRACKER_UDP: SocketConfig(
                socket_type=SocketType.TRACKER_UDP,
                tcp_nodelay=False,  # Not applicable to UDP
                so_rcvbuf=32 * 1024,  # 32KB for UDP
                so_sndbuf=32 * 1024,
                so_rcvtimeo=10.0,
                so_sndtimeo=10.0,
            ),
            SocketType.DHT: SocketConfig(
                socket_type=SocketType.DHT,
                tcp_nodelay=True,
                so_rcvbuf=128 * 1024,  # 128KB for DHT
                so_sndbuf=128 * 1024,
                so_rcvtimeo=5.0,
                so_sndtimeo=5.0,
            ),
            SocketType.LISTENER: SocketConfig(
                socket_type=SocketType.LISTENER,
                tcp_nodelay=True,
                so_reuseport=True,
                so_rcvbuf=256 * 1024,
                so_sndbuf=256 * 1024,
                so_rcvtimeo=0.0,  # Non-blocking
                so_sndtimeo=0.0,
            ),
        }
        self.logger = get_logger(__name__)

    def optimize_socket(self, sock: socket.socket, socket_type: SocketType) -> None:
        """Optimize socket settings for the given type.

        Args:
            sock: Socket to optimize
            socket_type: Type of socket for optimization
        """
        config = self.configs.get(socket_type)
        if not config:
            self.logger.warning(
                "No configuration found for socket type: %s",
                socket_type,
            )
            return

        try:
            # Set socket options
            if config.tcp_nodelay:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            if config.tcp_cork:
                # Only set TCP_CORK if available on platform
                tcp_cork = getattr(socket, "TCP_CORK", None)
                if tcp_cork is not None:
                    sock.setsockopt(socket.IPPROTO_TCP, tcp_cork, 1)

            if config.so_reuseport:
                # Only set SO_REUSEPORT if available on platform
                so_reuseport = getattr(socket, "SO_REUSEPORT", None)
                if so_reuseport is not None:
                    sock.setsockopt(socket.SOL_SOCKET, so_reuseport, 1)

            if config.so_reuseaddr:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if config.so_keepalive:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                # Set TCP keepalive options if available
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    sock.setsockopt(
                        socket.IPPROTO_TCP,
                        socket.TCP_KEEPIDLE,
                        config.tcp_keepalive_idle,
                    )
                    sock.setsockopt(
                        socket.IPPROTO_TCP,
                        socket.TCP_KEEPINTVL,
                        config.tcp_keepalive_interval,
                    )
                    sock.setsockopt(
                        socket.IPPROTO_TCP,
                        socket.TCP_KEEPCNT,
                        config.tcp_keepalive_probes,
                    )
                except (AttributeError, OSError):
                    # Keepalive options not available on this platform
                    pass

            # Set buffer sizes
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, config.so_rcvbuf)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, config.so_sndbuf)

            # Set timeouts
            if config.so_rcvtimeo > 0:
                sock.settimeout(config.so_rcvtimeo)

            self.logger.debug("Optimized socket for %s", socket_type)

        except OSError as e:
            self.logger.warning("Failed to optimize socket: %s", e)
            msg = f"Socket optimization failed: {e}"
            raise NetworkError(msg) from e

    def create_optimized_socket(
        self,
        socket_type: SocketType,
        family: int = socket.AF_INET,
        sock_type: int = socket.SOCK_STREAM,
    ) -> socket.socket:
        """Create and optimize a new socket.

        Args:
            socket_type: Type of socket to create
            family: Socket family (AF_INET, AF_INET6)
            sock_type: Socket type (SOCK_STREAM, SOCK_DGRAM)

        Returns:
            Optimized socket
        """
        sock = socket.socket(family, sock_type)
        self.optimize_socket(sock, socket_type)
        return sock


class ConnectionPool:
    """Connection pool for efficient connection management."""

    def __init__(
        self,
        max_connections: int = 100,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,
    ) -> None:
        """Initialize connection pool.

        Args:
            max_connections: Maximum connections in pool
            connection_timeout: Connection timeout in seconds
            idle_timeout: Idle connection timeout in seconds
        """
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout

        self.connections: dict[tuple[str, int], list[socket.socket]] = {}
        self.connection_times: dict[socket.socket, float] = {}
        self.last_activity: dict[socket.socket, float] = {}
        self.stats = ConnectionStats()
        self.lock = threading.RLock()
        self.logger = get_logger(__name__)

        # Start cleanup task
        self._cleanup_task = threading.Thread(
            target=self._cleanup_connections,
            daemon=True,
        )
        self._cleanup_task.start()

    def get_connection(
        self,
        host: str,
        port: int,
        socket_type: SocketType = SocketType.PEER_CONNECTION,
    ) -> socket.socket | None:
        """Get a connection from the pool.

        Args:
            host: Target host
            port: Target port
            socket_type: Type of socket needed

        Returns:
            Socket connection or None if not available
        """
        key = (host, port)

        with self.lock:
            if self.connections.get(key):
                # Return existing connection
                sock = self.connections[key].pop()
                self.last_activity[sock] = time.time()
                self.stats.active_connections += 1
                self.logger.debug("Reused connection to %s:%s", host, port)
                return sock

            # Create new connection
            try:
                sock = self._create_connection(host, port, socket_type)
                if sock:
                    self.stats.total_connections += 1
                    self.stats.active_connections += 1
                    self.connection_times[sock] = time.time()
                    self.last_activity[sock] = time.time()
                    self.logger.debug("Created new connection to %s:%s", host, port)
            except Exception as e:
                self.stats.failed_connections += 1
                self.logger.warning(
                    "Failed to create connection to %s:%s: %s",
                    host,
                    port,
                    e,
                )
                return None
            else:
                return sock

    def return_connection(self, sock: socket.socket, host: str, port: int) -> None:
        """Return a connection to the pool.

        Args:
            sock: Socket to return
            host: Target host
            port: Target port
        """
        key = (host, port)

        with self.lock:
            if sock.fileno() == -1:  # Socket is closed
                self._remove_connection(sock)
                return

            if key not in self.connections:
                self.connections[key] = []

            if len(self.connections[key]) < self.max_connections:
                self.connections[key].append(sock)
                self.stats.active_connections -= 1
                self.logger.debug("Returned connection to %s:%s", host, port)
            else:
                # Pool is full, close connection
                self._remove_connection(sock)

    def _create_connection(
        self,
        host: str,
        port: int,
        socket_type: SocketType,
    ) -> socket.socket | None:
        """Create a new connection."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connection_timeout)

            # Optimize socket
            optimizer = SocketOptimizer()
            optimizer.optimize_socket(sock, socket_type)

            # Connect
            sock.connect((host, port))
        except Exception:
            self.logger.exception("Failed to create connection")
            return None
        else:
            return sock

    def _remove_connection(self, sock: socket.socket) -> None:
        """Remove a connection from tracking."""
        with contextlib.suppress(builtins.BaseException):
            sock.close()

        if sock in self.connection_times:
            del self.connection_times[sock]
        if sock in self.last_activity:
            del self.last_activity[sock]

    def _cleanup_connections(self) -> None:
        """Clean up idle and expired connections."""
        while True:
            try:
                time.sleep(60)  # Check every minute

                with self.lock:
                    current_time = time.time()
                    to_remove = []

                    for connections in self.connections.values():
                        for sock in connections[:]:
                            if (
                                sock in self.last_activity
                                and current_time - self.last_activity[sock]
                                > self.idle_timeout
                            ):
                                to_remove.append(sock)
                                connections.remove(sock)

                    for sock in to_remove:
                        self._remove_connection(sock)

            except Exception:
                self.logger.exception("Error in connection cleanup")

    def get_stats(self) -> ConnectionStats:
        """Get connection pool statistics."""
        with self.lock:
            return ConnectionStats(
                total_connections=self.stats.total_connections,
                active_connections=self.stats.active_connections,
                failed_connections=self.stats.failed_connections,
                bytes_sent=self.stats.bytes_sent,
                bytes_received=self.stats.bytes_received,
                connection_time=self.stats.connection_time,
                last_activity=self.stats.last_activity,
            )


class NetworkOptimizer:
    """Main network optimizer that coordinates all optimizations."""

    def __init__(self) -> None:
        """Initialize network optimizer."""
        self.socket_optimizer = SocketOptimizer()
        self.connection_pool = ConnectionPool()
        self.logger = get_logger(__name__)

    def optimize_peer_socket(self, sock: socket.socket) -> None:
        """Optimize socket for peer connections."""
        self.socket_optimizer.optimize_socket(sock, SocketType.PEER_CONNECTION)

    def optimize_tracker_socket(self, sock: socket.socket) -> None:
        """Optimize socket for tracker connections."""
        self.socket_optimizer.optimize_socket(sock, SocketType.TRACKER_HTTP)

    def optimize_dht_socket(self, sock: socket.socket) -> None:
        """Optimize socket for DHT connections."""
        self.socket_optimizer.optimize_socket(sock, SocketType.DHT)

    def get_connection(
        self,
        host: str,
        port: int,
        socket_type: SocketType = SocketType.PEER_CONNECTION,
    ) -> socket.socket | None:
        """Get an optimized connection."""
        return self.connection_pool.get_connection(host, port, socket_type)

    def return_connection(self, sock: socket.socket, host: str, port: int) -> None:
        """Return a connection to the pool."""
        self.connection_pool.return_connection(sock, host, port)

    def get_stats(self) -> dict[str, Any]:
        """Get optimization statistics."""
        return {
            "connection_pool": self.connection_pool.get_stats(),
            "socket_configs": {
                t.value: c for t, c in self.socket_optimizer.configs.items()
            },
        }


# Global network optimizer instance
_network_optimizer: NetworkOptimizer | None = None


def get_network_optimizer() -> NetworkOptimizer:
    """Get the global network optimizer."""
    global _network_optimizer
    if _network_optimizer is None:
        _network_optimizer = NetworkOptimizer()
    return _network_optimizer
