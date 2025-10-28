"""High-performance connection pool for peer connections.

This module provides a connection pool with health checks, recycling,
and semaphore-based connection limits for optimal resource management.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.models import PeerInfo


@dataclass
class ConnectionMetrics:
    """Metrics for a connection in the pool."""

    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    usage_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    is_healthy: bool = True


class PeerConnectionPool:
    """Connection pool with health checks and recycling.

    Provides efficient connection reuse, health monitoring,
    and automatic cleanup of stale connections.
    """

    def __init__(
        self,
        max_connections: int = 200,
        max_idle_time: float = 300.0,  # 5 minutes
        health_check_interval: float = 60.0,  # 1 minute
        max_usage_count: int = 1000,
    ):
        """Initialize connection pool.

        Args:
            max_connections: Maximum number of concurrent connections
            max_idle_time: Maximum idle time before connection is closed
            health_check_interval: Interval for health checks
            max_usage_count: Maximum usage count before recycling connection
        """
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.health_check_interval = health_check_interval
        self.max_usage_count = max_usage_count

        # Connection management
        self.pool: dict[str, Any] = {}  # peer_id -> connection
        self.metrics: dict[str, ConnectionMetrics] = {}
        self.semaphore = asyncio.Semaphore(max_connections)

        # Background tasks
        self._health_check_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the connection pool."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self.logger.info(
            "Connection pool started with max_connections=%d", self.max_connections
        )

    async def stop(self) -> None:
        """Stop the connection pool and cleanup all connections."""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Close all connections
        await self._close_all_connections()

        self.logger.info("Connection pool stopped")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def acquire(self, peer_info: PeerInfo) -> Any | None:
        """Acquire a connection for a peer.

        Args:
            peer_info: Peer information

        Returns:
            Connection object or None if acquisition failed
        """
        peer_id = f"{peer_info.ip}:{peer_info.port}"

        # Check if we already have a healthy connection
        if peer_id in self.pool:
            connection = self.pool[peer_id]
            metrics = self.metrics[peer_id]

            if metrics.is_healthy and self._is_connection_valid(connection):
                metrics.last_used = time.time()
                metrics.usage_count += 1
                self.logger.debug("Reusing existing connection for %s", peer_id)
                return connection
            # Remove unhealthy connection
            await self._remove_connection(peer_id)

        # Try to acquire semaphore
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning("Failed to acquire connection slot for %s", peer_id)
            return None

        try:
            # Create new connection
            connection = await self._create_connection(peer_info)
            if connection:
                self.pool[peer_id] = connection
                self.metrics[peer_id] = ConnectionMetrics()
                self.logger.debug("Created new connection for %s", peer_id)
                return connection
            self.semaphore.release()
            return None
        except Exception:
            self.semaphore.release()
            self.logger.exception("Failed to create connection for %s", peer_id)
            return None

    async def release(self, peer_id: str, connection: Any) -> None:  # noqa: ARG002
        """Release a connection back to the pool.

        Args:
            peer_id: Peer identifier
            connection: Connection object
        """
        if peer_id not in self.pool:
            # Connection was already removed
            self.semaphore.release()
            return

        metrics = self.metrics.get(peer_id)
        if metrics:
            metrics.last_used = time.time()

            # Check if connection should be recycled
            if metrics.usage_count >= self.max_usage_count:
                self.logger.debug(
                    "Recycling connection for %s (usage_count=%d)",
                    peer_id,
                    metrics.usage_count,
                )
                await self._remove_connection(peer_id)
                self.semaphore.release()
            else:
                self.logger.debug("Released connection for %s", peer_id)

    async def remove_connection(self, peer_id: str) -> None:
        """Remove a specific connection from the pool.

        Args:
            peer_id: Peer identifier
        """
        await self._remove_connection(peer_id)
        self.semaphore.release()

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        total_connections = len(self.pool)
        healthy_connections = sum(1 for m in self.metrics.values() if m.is_healthy)

        return {
            "total_connections": total_connections,
            "healthy_connections": healthy_connections,
            "max_connections": self.max_connections,
            "available_slots": self.semaphore._value,  # noqa: SLF001
            "pool_utilization": (self.max_connections - self.semaphore._value)  # noqa: SLF001
            / self.max_connections,
            "average_usage_count": (
                sum(m.usage_count for m in self.metrics.values())
                / max(total_connections, 1)
            ),
            "total_bytes_sent": sum(m.bytes_sent for m in self.metrics.values()),
            "total_bytes_received": sum(
                m.bytes_received for m in self.metrics.values()
            ),
            "total_errors": sum(m.errors for m in self.metrics.values()),
        }

    async def _create_connection(self, peer_info: PeerInfo) -> Any | None:
        """Create a new connection to a peer.

        Args:
            peer_info: Peer information

        Returns:
            Connection object or None if creation failed
        """
        try:
            # This would be implemented by the actual connection manager
            # For now, return a placeholder
            return {"peer_info": peer_info, "created_at": time.time()}
        except Exception:
            self.logger.exception("Failed to create connection")
            return None

    def _is_connection_valid(self, connection: Any) -> bool:  # noqa: ARG002
        """Check if a connection is still valid.

        Args:
            connection: Connection object

        Returns:
            True if connection is valid
        """
        # This would check actual connection validity
        # For now, assume all connections are valid
        return True

    async def _remove_connection(self, peer_id: str) -> None:
        """Remove a connection from the pool.

        Args:
            peer_id: Peer identifier
        """
        if peer_id in self.pool:
            connection = self.pool[peer_id]

            # Close connection if it has a close method
            if hasattr(connection, "close"):
                try:
                    if asyncio.iscoroutinefunction(connection.close):
                        await connection.close()
                    else:
                        connection.close()
                except Exception as e:
                    self.logger.warning("Error closing connection %s: %s", peer_id, e)

            # Remove from pool
            del self.pool[peer_id]
            if peer_id in self.metrics:
                del self.metrics[peer_id]

            self.logger.debug("Removed connection for %s", peer_id)

    async def _close_all_connections(self) -> None:
        """Close all connections in the pool."""
        for peer_id in list(self.pool.keys()):
            await self._remove_connection(peer_id)

    async def _health_check_loop(self) -> None:
        """Background task for health checks."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in health check loop")

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup."""
        while self._running:
            try:
                await asyncio.sleep(30.0)  # Cleanup every 30 seconds
                await self._cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in cleanup loop")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        current_time = time.time()
        unhealthy_connections = []

        for peer_id, metrics in self.metrics.items():
            # Check if connection is idle too long
            if current_time - metrics.last_used > self.max_idle_time:
                self.logger.debug("Connection %s is idle too long", peer_id)
                metrics.is_healthy = False

            # Check usage count
            if metrics.usage_count >= self.max_usage_count:
                self.logger.debug("Connection %s exceeded usage count", peer_id)
                metrics.is_healthy = False

            # Check error rate
            if metrics.errors > 10:  # Arbitrary threshold
                self.logger.debug("Connection %s has too many errors", peer_id)
                metrics.is_healthy = False

            if not metrics.is_healthy:
                unhealthy_connections.append(peer_id)

        # Remove unhealthy connections
        for peer_id in unhealthy_connections:
            await self._remove_connection(peer_id)
            self.semaphore.release()

        if unhealthy_connections:
            self.logger.info(
                "Removed %d unhealthy connections", len(unhealthy_connections)
            )

    async def _cleanup_stale_connections(self) -> None:
        """Clean up stale connections."""
        current_time = time.time()
        stale_connections = []

        for peer_id, metrics in self.metrics.items():
            if current_time - metrics.last_used > self.max_idle_time * 2:
                stale_connections.append(peer_id)

        for peer_id in stale_connections:
            await self._remove_connection(peer_id)
            self.semaphore.release()

        if stale_connections:
            self.logger.info("Cleaned up %d stale connections", len(stale_connections))

    def update_connection_metrics(
        self,
        peer_id: str,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        errors: int = 0,
    ) -> None:
        """Update connection metrics.

        Args:
            peer_id: Peer identifier
            bytes_sent: Bytes sent
            bytes_received: Bytes received
            errors: Number of errors
        """
        if peer_id in self.metrics:
            metrics = self.metrics[peer_id]
            metrics.bytes_sent += bytes_sent
            metrics.bytes_received += bytes_received
            metrics.errors += errors
