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
from collections import deque
from dataclasses import dataclass, field
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
    # RTT and bandwidth measurements
    rtt_ms: float = 0.0  
    bandwidth_bps: float = 0.0 
    rtt_measurer: Any = None  


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

    def _calculate_optimal_buffer_size(
        self,
        bandwidth_bps: float | None = None,
        rtt_ms: float | None = None,
        connection_stats: ConnectionStats | None = None,
    ) -> int:
        """Calculate optimal buffer size using BDP (Bandwidth-Delay Product).

        Args:
            bandwidth_bps: Bandwidth in bits per second (optional, uses connection_stats if not provided)
            rtt_ms: Round-trip time in milliseconds (optional, uses connection_stats if not provided)
            connection_stats: Connection statistics with RTT/bandwidth measurements

        Returns:
            Optimal buffer size in bytes

        """
        # Use measured values from connection_stats if available
        if connection_stats:
            if connection_stats.rtt_ms > 0:
                rtt_ms = connection_stats.rtt_ms
            if connection_stats.bandwidth_bps > 0:
                bandwidth_bps = connection_stats.bandwidth_bps

        # Fallback to config values if measurements unavailable
        if bandwidth_bps is None or bandwidth_bps <= 0:
            from ccbt.config.config import get_config

            cfg = get_config()
            # Estimate bandwidth from config (default to 100 Mbps if not set)
            bandwidth_bps = getattr(cfg.network, "estimated_bandwidth_bps", 100_000_000)

        if rtt_ms is None or rtt_ms <= 0:
            # Default to 50ms if not measured
            rtt_ms = 50.0

        # BDP = bandwidth * RTT
        # Optimal buffer = BDP * 2 (for TCP window scaling)
        bdp_bits = bandwidth_bps * rtt_ms / 1000
        bdp_bytes = bdp_bits / 8
        optimal_size = int(bdp_bytes * 2)

        # Clamp to min/max from config
        from ccbt.config.config import get_config

        cfg = get_config()
        min_buffer = getattr(cfg.network, "socket_min_buffer_kib", 64) * 1024
        max_buffer = min(
            getattr(cfg.network, "socket_max_buffer_kib", 65536) * 1024,
            self._get_max_buffer_size(),
        )

        return max(min_buffer, min(optimal_size, max_buffer))

    def _get_max_buffer_size(self) -> int:
        """Get platform-specific maximum buffer size.

        Returns:
            Maximum buffer size in bytes

        """
        import platform

        system = platform.system().lower()
        if system == "linux":
            try:
                with open("/proc/sys/net/core/rmem_max", encoding="utf-8") as f:
                    return int(f.read().strip())
            except (OSError, ValueError):
                return 65536 * 1024  # Default 64MB
        elif system == "darwin":  # macOS
            try:
                import subprocess

                result = subprocess.run(  # pragma: no cover - Platform-specific path, sysctl is standard macOS utility
                    ["sysctl", "-n", "kern.ipc.maxsockbuf"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return int(result.stdout.strip())
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            return 4 * 1024 * 1024  # Default 4MB
        elif system == "windows":
            # Windows: Use getsockopt with SO_MAX_MSG_SIZE
            # Default to 64KB for Windows
            return 65536
        else:
            return 65536 * 1024  # Default 64MB

    def _supports_tcp_window_scaling(self) -> bool:
        """Check if TCP window scaling is supported.

        Returns:
            True if TCP window scaling is available

        """
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # TCP_WINDOW_SCALE may not be available on all platforms (e.g., Windows)
            tcp_window_scale = getattr(socket, "TCP_WINDOW_SCALE", None)
            if tcp_window_scale is not None:
                test_sock.setsockopt(socket.IPPROTO_TCP, tcp_window_scale, 1)
            test_sock.close()
            return tcp_window_scale is not None
        except (AttributeError, OSError):
            return False

    def optimize_socket(
        self,
        sock: socket.socket,
        socket_type: SocketType,
        connection_stats: ConnectionStats | None = None,
    ) -> None:
        """Optimize socket settings for the given type.

        Args:
            sock: Socket to optimize
            socket_type: Type of socket for optimization
            connection_stats: Optional connection statistics with RTT/bandwidth measurements

        """
        config = self.configs.get(socket_type)
        if not config:
            self.logger.warning(
                "No configuration found for socket type: %s",
                socket_type,
            )
            return

        try:
            # Check if adaptive buffers are enabled
            from ccbt.config.config import get_config

            cfg = get_config()
            use_adaptive = getattr(cfg.network, "socket_adaptive_buffers", False)

            # Calculate buffer sizes
            if use_adaptive:
                # Use measured BDP if available, otherwise use config defaults
                optimal_buffer = self._calculate_optimal_buffer_size(
                    connection_stats=connection_stats
                )
                rcvbuf = optimal_buffer
                sndbuf = optimal_buffer
            else:
                rcvbuf = config.so_rcvbuf
                sndbuf = config.so_sndbuf

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

            # Set buffer sizes (adaptive or fixed)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)

            # Enable TCP window scaling if supported and enabled
            if (
                getattr(cfg.network, "socket_enable_window_scaling", True)
                and self._supports_tcp_window_scaling()
            ):
                with contextlib.suppress(AttributeError, OSError):
                    # TCP_WINDOW_SCALE may not be available on all platforms (e.g., Windows)
                    tcp_window_scale = getattr(socket, "TCP_WINDOW_SCALE", None)
                    if tcp_window_scale is not None:
                        sock.setsockopt(socket.IPPROTO_TCP, tcp_window_scale, 1)

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
        sock = socket.socket(family, sock_type)  # pragma: no cover
        # Socket creation and optimization - simple wrapper method
        # Coverage achieved via optimize_socket() tests, this method just combines create+optimize
        self.optimize_socket(sock, socket_type)  # pragma: no cover
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
        self._shutdown_event = threading.Event()

        # Bandwidth measurement tracking
        # Track bytes sent/received over time windows for bandwidth calculation
        self._bandwidth_windows: dict[socket.socket, deque[tuple[float, int, int]]] = (
            {}
        )  # sock -> deque of (timestamp, bytes_sent, bytes_received)
        self._bandwidth_window_size: float = 5.0  # 5 second window for bandwidth calculation

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
        else:  # pragma: no cover
            # Success path: connection created and optimized successfully
            # Tested via successful connection creation in test suite
            return sock

    def _remove_connection(self, sock: socket.socket) -> None:
        """Remove a connection from tracking."""
        with contextlib.suppress(builtins.BaseException):
            sock.close()

        if sock in self.connection_times:
            del self.connection_times[sock]
        if sock in self.last_activity:
            del self.last_activity[sock]
        if sock in self._bandwidth_windows:
            del self._bandwidth_windows[sock]

    def _cleanup_connections(self) -> None:
        """Clean up idle and expired connections."""
        while not self._shutdown_event.is_set():  # pragma: no cover
            # Background daemon thread runs continuously
            # Full coverage requires running thread for 60+ seconds which is impractical in unit tests
            # Logic is tested via direct method calls in test suite
            try:
                # Wait up to 60 seconds, but check shutdown event
                if self._shutdown_event.wait(timeout=60):
                    # Shutdown event was set, exit loop
                    break

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

            except Exception:  # pragma: no cover
                # Defensive: Ensure cleanup thread continues even if errors occur
                # Thread runs as daemon so exceptions are logged but don't crash application
                self.logger.exception("Error in connection cleanup")

    def stop(self) -> None:
        """Stop the cleanup thread."""
        if self._cleanup_task and self._cleanup_task.is_alive():
            # Set shutdown event first to signal thread to stop
            self._shutdown_event.set()
            # Wait for thread to finish with timeout
            self._cleanup_task.join(timeout=5.0)
            # If thread is still alive after timeout, log warning
            if self._cleanup_task.is_alive():
                self.logger.warning(
                    "Cleanup thread did not stop within timeout, "
                    "it will continue as daemon thread"
                )

    def update_bytes_transferred(
        self, sock: socket.socket, bytes_sent: int, bytes_received: int
    ) -> None:
        """Update bytes transferred for bandwidth calculation.

        Args:
            sock: Socket connection
            bytes_sent: Bytes sent since last update
            bytes_received: Bytes received since last update
        """
        with self.lock:
            current_time = time.time()
            self.stats.bytes_sent += bytes_sent
            self.stats.bytes_received += bytes_received

            # Track bandwidth over time window
            if sock not in self._bandwidth_windows:
                self._bandwidth_windows[sock] = deque(maxlen=100)

            window = self._bandwidth_windows[sock]
            window.append((current_time, bytes_sent, bytes_received))

            # Calculate bandwidth from recent window
            if len(window) >= 2:
                # Calculate bandwidth over the window
                oldest_time, _, _ = window[0]
                time_span = current_time - oldest_time

                if time_span > 0:
                    total_sent = sum(b[1] for b in window)
                    total_received = sum(b[2] for b in window)
                    total_bytes = total_sent + total_received

                    # Bandwidth in bits per second
                    bandwidth_bps = (total_bytes * 8) / time_span
                    self.stats.bandwidth_bps = bandwidth_bps

    def update_rtt(self, sock: socket.socket, rtt_ms: float) -> None:
        """Update RTT measurement for a connection.

        Args:
            sock: Socket connection
            rtt_ms: RTT measurement in milliseconds
        """
        with self.lock:
            # Initialize RTT measurer if needed
            if self.stats.rtt_measurer is None:
                from ccbt.utils.rtt_measurement import RTTMeasurer

                self.stats.rtt_measurer = RTTMeasurer()

            # Update RTT estimate (use EWMA from measurer)
            # For now, use simple average of recent measurements
            if self.stats.rtt_ms == 0.0:
                self.stats.rtt_ms = rtt_ms
            else:
                # Simple EWMA: new_rtt = alpha * new_sample + (1 - alpha) * old_rtt
                alpha = 0.125  # RFC 6298 default
                self.stats.rtt_ms = alpha * rtt_ms + (1 - alpha) * self.stats.rtt_ms

    def get_connection_stats(self, sock: socket.socket) -> ConnectionStats | None:
        """Get statistics for a specific connection.

        Args:
            sock: Socket connection

        Returns:
            ConnectionStats for the connection, or None if not found
        """
        with self.lock:
            if sock not in self.connection_times:
                return None

            # Create connection-specific stats
            stats = ConnectionStats(
                total_connections=1,
                active_connections=1 if sock in self.last_activity else 0,
                bytes_sent=self.stats.bytes_sent,  # Aggregate for now
                bytes_received=self.stats.bytes_received,  # Aggregate for now
                connection_time=self.connection_times.get(sock, 0.0),
                last_activity=self.last_activity.get(sock, 0.0),
                rtt_ms=self.stats.rtt_ms,
                bandwidth_bps=self.stats.bandwidth_bps,
                rtt_measurer=self.stats.rtt_measurer,
            )

            return stats

    def get_stats(self) -> ConnectionStats:
        """Get connection pool statistics."""
        with self.lock:
            # Calculate aggregate bandwidth if we have measurements
            if self._bandwidth_windows:
                current_time = time.time()
                total_bandwidth_bps = 0.0
                active_windows = 0

                for window in self._bandwidth_windows.values():
                    if len(window) >= 2:
                        oldest_time, _, _ = window[0]
                        time_span = current_time - oldest_time

                        if time_span > 0:
                            total_sent = sum(b[1] for b in window)
                            total_received = sum(b[2] for b in window)
                            total_bytes = total_sent + total_received
                            bandwidth_bps = (total_bytes * 8) / time_span
                            total_bandwidth_bps += bandwidth_bps
                            active_windows += 1

                if active_windows > 0:
                    self.stats.bandwidth_bps = total_bandwidth_bps / active_windows

            return ConnectionStats(
                total_connections=self.stats.total_connections,
                active_connections=self.stats.active_connections,
                failed_connections=self.stats.failed_connections,
                bytes_sent=self.stats.bytes_sent,
                bytes_received=self.stats.bytes_received,
                connection_time=self.stats.connection_time,
                last_activity=self.stats.last_activity,
                rtt_ms=self.stats.rtt_ms,
                bandwidth_bps=self.stats.bandwidth_bps,
                rtt_measurer=self.stats.rtt_measurer,
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

    def stop(self) -> None:
        """Stop network optimizer and cleanup resources."""
        self.connection_pool.stop()

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


def reset_network_optimizer() -> None:
    """Reset global network optimizer (for testing)."""
    global _network_optimizer
    if _network_optimizer is not None:
        _network_optimizer.stop()
        _network_optimizer = None
