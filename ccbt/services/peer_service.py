"""Peer service for ccBitTorrent.

from __future__ import annotations

Manages peer connections, handshakes, and peer communication
with health checks and circuit breaker protection.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ccbt.services.base import HealthCheck, Service
from ccbt.utils.logging_config import LoggingContext

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.models import PeerInfo


@dataclass
class PeerConnection:
    """Represents a peer connection."""

    peer_info: PeerInfo
    connected_at: float
    last_activity: float
    bytes_sent: int = 0
    bytes_received: int = 0
    pieces_downloaded: int = 0
    pieces_uploaded: int = 0
    connection_quality: float = 1.0


class PeerService(Service):
    """Service for managing peer connections."""

    def __init__(self, max_peers: int = 200, connection_timeout: float = 30.0):
        """Initialize peer service."""
        super().__init__(
            name="peer_service",
            version="1.0.0",
            description="Peer connection management service",
        )
        self.max_peers = max_peers
        self.connection_timeout = connection_timeout
        self.peers: dict[str, PeerConnection] = {}
        self.active_connections = 0
        self.total_connections = 0
        self.failed_connections = 0

        # Performance metrics
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.total_pieces_downloaded = 0
        self.total_pieces_uploaded = 0

        # Background task reference
        self._monitor_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the peer service."""
        self.logger.info("Starting peer service")
        from ccbt.services.base import ServiceState

        self.state = ServiceState.STARTING

        # Initialize peer management
        await self._initialize_peer_management()

        # Set state to running after successful initialization
        self.state = ServiceState.RUNNING
        self.logger.info("Peer service started successfully")

    async def stop(self) -> None:
        """Stop the peer service."""
        self.logger.info("Stopping peer service")
        from ccbt.services.base import ServiceState

        self.state = ServiceState.STOPPING

        # Cancel monitoring task if it exists
        if hasattr(self, "_monitor_task") and self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.debug("Error waiting for monitor task: %s", e)

        # Disconnect all peers
        await self._disconnect_all_peers()

        # Clear peer data
        self.peers.clear()
        self.active_connections = 0

        # Set state to stopped
        self.state = ServiceState.STOPPED
        self.logger.info("Peer service stopped")

    async def health_check(self) -> HealthCheck:
        """Perform health check."""
        start_time = time.time()

        try:
            # Check if we can manage peers
            healthy = (
                self.active_connections <= self.max_peers
                and self.failed_connections < self.max_peers * 0.5
            )

            # Calculate health score
            connection_ratio = self.active_connections / max(self.max_peers, 1)
            failure_ratio = self.failed_connections / max(self.total_connections, 1)
            health_score = max(0.0, 1.0 - connection_ratio - failure_ratio)

            response_time = time.time() - start_time

            return HealthCheck(
                service_name=self.name,
                healthy=healthy,
                score=health_score,
                message=f"Active: {self.active_connections}, Failed: {self.failed_connections}",
                timestamp=time.time(),
                response_time=response_time,
            )

        except Exception as e:
            return HealthCheck(
                service_name=self.name,
                healthy=False,
                score=0.0,
                message=f"Health check failed: {e}",
                timestamp=time.time(),
                response_time=time.time() - start_time,
            )

    async def _initialize_peer_management(self) -> None:
        """Initialize peer management systems."""
        self.logger.info("Initializing peer management")

        # Start peer monitoring task and store reference for cleanup
        self._monitor_task = asyncio.create_task(self._monitor_peers())

    async def _monitor_peers(self) -> None:
        """Monitor peer connections."""
        from ccbt.services.base import ServiceState

        while self.state == ServiceState.RUNNING:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Remove inactive peers
                current_time = time.time()
                inactive_peers = []

                for peer_id, connection in self.peers.items():
                    if current_time - connection.last_activity > 300:  # 5 minutes
                        inactive_peers.append(peer_id)

                for peer_id in inactive_peers:
                    await self.disconnect_peer(peer_id)

                self.logger.debug("Peer monitoring: %s active peers", len(self.peers))

            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                self.logger.debug("Peer monitoring task cancelled")
                break
            except Exception:  # pragma: no cover - Background loop exception handler, difficult to trigger reliably
                self.logger.exception("Error in peer monitoring")

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a peer.

        Args:
            peer_info: Peer information

        Returns:
            True if connection successful

        """
        peer_id = f"{peer_info.ip}:{peer_info.port}"

        try:
            with LoggingContext("peer_connect", peer_id=peer_id):
                # Check if already connected
                if peer_id in self.peers:
                    self.logger.warning("Already connected to peer: %s", peer_id)
                    return True

                # Check connection limit
                if self.active_connections >= self.max_peers:
                    self.logger.warning(
                        "Connection limit reached: %s",
                        self.max_peers,
                    )
                    return False

                # Create peer connection
                connection = PeerConnection(
                    peer_info=peer_info,
                    connected_at=time.time(),
                    last_activity=time.time(),
                )

                # Store connection
                self.peers[peer_id] = connection
                self.active_connections += 1
                self.total_connections += 1

                self.logger.info("Connected to peer: %s", peer_id)
                return True

        except Exception:
            self.failed_connections += 1
            self.logger.exception("Failed to connect to peer %s", peer_id)
            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect a peer.

        Args:
            peer_id: Peer identifier

        """
        try:
            with LoggingContext("peer_disconnect", peer_id=peer_id):
                if peer_id in self.peers:
                    connection = self.peers[peer_id]

                    # Update statistics
                    self.total_bytes_sent += connection.bytes_sent
                    self.total_bytes_received += connection.bytes_received
                    self.total_pieces_downloaded += connection.pieces_downloaded
                    self.total_pieces_uploaded += connection.pieces_uploaded

                    # Remove peer
                    del self.peers[peer_id]
                    self.active_connections -= 1

                    self.logger.info("Disconnected peer: %s", peer_id)

        except Exception:
            self.logger.exception("Error disconnecting peer %s", peer_id)

    async def get_peer(self, peer_id: str) -> PeerConnection | None:
        """Get peer connection by ID."""
        return self.peers.get(peer_id)

    async def list_peers(self) -> list[PeerConnection]:
        """List all peer connections."""
        return list(self.peers.values())

    async def get_peer_stats(self) -> dict[str, Any]:
        """Get peer service statistics."""
        return {
            "active_peers": len(self.peers),
            "max_peers": self.max_peers,
            "total_connections": self.total_connections,
            "failed_connections": self.failed_connections,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "total_pieces_downloaded": self.total_pieces_downloaded,
            "total_pieces_uploaded": self.total_pieces_uploaded,
            "connection_success_rate": (
                (self.total_connections - self.failed_connections)
                / max(self.total_connections, 1)
            ),
        }

    async def update_peer_activity(
        self,
        peer_id: str,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        pieces_downloaded: int = 0,
        pieces_uploaded: int = 0,
    ) -> None:
        """Update peer activity statistics."""
        if peer_id in self.peers:
            connection = self.peers[peer_id]
            connection.last_activity = time.time()
            connection.bytes_sent += bytes_sent
            connection.bytes_received += bytes_received
            connection.pieces_downloaded += pieces_downloaded
            connection.pieces_uploaded += pieces_uploaded

    async def get_best_peers(self, limit: int = 10) -> list[PeerConnection]:
        """Get the best performing peers."""
        peers = list(self.peers.values())

        # Sort by connection quality and activity
        peers.sort(
            key=lambda p: (
                p.connection_quality,
                p.pieces_downloaded + p.pieces_uploaded,
                p.last_activity,
            ),
            reverse=True,
        )

        return peers[:limit]

    async def _disconnect_all_peers(self) -> None:
        """Disconnect all peers."""
        for peer_id in list(self.peers.keys()):
            try:
                await self.disconnect_peer(peer_id)
            except Exception:
                # Log but don't fail - one peer disconnect error shouldn't block shutdown
                self.logger.warning(
                    "Failed to disconnect peer %s during shutdown",
                    peer_id,
                    exc_info=True,
                )
