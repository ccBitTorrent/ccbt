"""Tracker service for ccBitTorrent.

Manages communication with BitTorrent trackers with health checks
and circuit breaker protection.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..logging_config import LoggingContext
from ..models import PeerInfo
from .base import HealthCheck, Service


@dataclass
class TrackerConnection:
    """Represents a tracker connection."""
    url: str
    last_announce: float
    last_success: float
    failure_count: int
    response_time: float
    is_healthy: bool = True


class TrackerService(Service):
    """Service for managing tracker communication."""

    def __init__(self, max_trackers: int = 10, announce_interval: float = 1800.0):
        super().__init__(
            name="tracker_service",
            version="1.0.0",
            description="Tracker communication service",
        )
        self.max_trackers = max_trackers
        self.announce_interval = announce_interval
        self.trackers: Dict[str, TrackerConnection] = {}
        self.active_trackers = 0
        self.total_announces = 0
        self.successful_announces = 0
        self.failed_announces = 0

        # Performance metrics
        self.total_peers_discovered = 0
        self.average_response_time = 0.0

    async def start(self) -> None:
        """Start the tracker service."""
        self.logger.info("Starting tracker service")

        # Initialize tracker management
        await self._initialize_tracker_management()

    async def stop(self) -> None:
        """Stop the tracker service."""
        self.logger.info("Stopping tracker service")

        # Clear tracker data
        self.trackers.clear()
        self.active_trackers = 0

    async def health_check(self) -> HealthCheck:
        """Perform health check."""
        start_time = time.time()

        try:
            # Check if we have healthy trackers
            healthy_trackers = sum(1 for t in self.trackers.values() if t.is_healthy)
            total_trackers = len(self.trackers)

            healthy = (
                total_trackers > 0 and
                healthy_trackers > 0 and
                self.failed_announces < self.total_announces * 0.5
            )

            # Calculate health score
            if total_trackers == 0:
                health_score = 0.0
            else:
                health_score = healthy_trackers / total_trackers

            response_time = time.time() - start_time

            return HealthCheck(
                service_name=self.name,
                healthy=healthy,
                score=health_score,
                message=f"Trackers: {healthy_trackers}/{total_trackers}, Success rate: {self.successful_announces}/{self.total_announces}",
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

    async def _initialize_tracker_management(self) -> None:
        """Initialize tracker management systems."""
        self.logger.info("Initializing tracker management")

        # Start tracker monitoring task
        asyncio.create_task(self._monitor_trackers())

    async def _monitor_trackers(self) -> None:
        """Monitor tracker health."""
        while self.state.value == "running":
            try:
                await asyncio.sleep(60)  # Check every minute

                # Check tracker health
                current_time = time.time()
                for tracker_url, connection in self.trackers.items():
                    # Mark as unhealthy if no successful announce in 2x interval
                    if current_time - connection.last_success > self.announce_interval * 2:
                        connection.is_healthy = False
                        self.logger.warning(f"Tracker marked as unhealthy: {tracker_url}")

                self.logger.debug(f"Tracker monitoring: {len(self.trackers)} trackers")

            except Exception as e:
                self.logger.error(f"Error in tracker monitoring: {e}")

    async def add_tracker(self, url: str) -> bool:
        """Add a tracker.
        
        Args:
            url: Tracker URL
            
        Returns:
            True if tracker added successfully
        """
        try:
            with LoggingContext("tracker_add", url=url):
                if url in self.trackers:
                    self.logger.warning(f"Tracker already exists: {url}")
                    return True

                if len(self.trackers) >= self.max_trackers:
                    self.logger.warning(f"Tracker limit reached: {self.max_trackers}")
                    return False

                # Create tracker connection
                connection = TrackerConnection(
                    url=url,
                    last_announce=0.0,
                    last_success=0.0,
                    failure_count=0,
                    response_time=0.0,
                )

                # Store tracker
                self.trackers[url] = connection
                self.active_trackers += 1

                self.logger.info(f"Added tracker: {url}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to add tracker {url}: {e}")
            return False

    async def remove_tracker(self, url: str) -> None:
        """Remove a tracker.
        
        Args:
            url: Tracker URL
        """
        try:
            with LoggingContext("tracker_remove", url=url):
                if url in self.trackers:
                    del self.trackers[url]
                    self.active_trackers -= 1
                    self.logger.info(f"Removed tracker: {url}")

        except Exception as e:
            self.logger.error(f"Error removing tracker {url}: {e}")

    async def announce(self, info_hash: bytes, peer_id: bytes,
                      port: int, uploaded: int = 0, downloaded: int = 0,
                      left: int = 0, event: str = "started") -> List[PeerInfo]:
        """Announce to trackers.
        
        Args:
            info_hash: Torrent info hash
            peer_id: Our peer ID
            port: Our port
            uploaded: Bytes uploaded
            downloaded: Bytes downloaded
            left: Bytes left to download
            event: Announce event
            
        Returns:
            List of discovered peers
        """
        all_peers = []

        for tracker_url, connection in self.trackers.items():
            if not connection.is_healthy:
                continue

            try:
                with LoggingContext("tracker_announce", url=tracker_url):
                    # Simulate tracker announce (would use actual tracker client)
                    peers = await self._announce_to_tracker(
                        tracker_url, info_hash, peer_id, port,
                        uploaded, downloaded, left, event,
                    )

                    # Update tracker stats
                    connection.last_announce = time.time()
                    connection.last_success = time.time()
                    connection.failure_count = 0
                    connection.is_healthy = True

                    self.successful_announces += 1
                    all_peers.extend(peers)

                    self.logger.debug(f"Announced to tracker {tracker_url}: {len(peers)} peers")

            except Exception as e:
                connection.failure_count += 1
                self.failed_announces += 1
                self.logger.error(f"Failed to announce to tracker {tracker_url}: {e}")

                # Mark as unhealthy after multiple failures
                if connection.failure_count >= 3:
                    connection.is_healthy = False

            self.total_announces += 1

        # Update metrics
        self.total_peers_discovered += len(all_peers)

        return all_peers

    async def _announce_to_tracker(self, url: str, info_hash: bytes, peer_id: bytes,
                                 port: int, uploaded: int, downloaded: int,
                                 left: int, event: str) -> List[PeerInfo]:
        """Announce to a specific tracker."""
        # This would use the actual tracker client
        # For now, return empty list
        return []

    async def get_tracker_stats(self) -> Dict[str, Any]:
        """Get tracker service statistics."""
        healthy_trackers = sum(1 for t in self.trackers.values() if t.is_healthy)

        return {
            "total_trackers": len(self.trackers),
            "healthy_trackers": healthy_trackers,
            "active_trackers": self.active_trackers,
            "total_announces": self.total_announces,
            "successful_announces": self.successful_announces,
            "failed_announces": self.failed_announces,
            "total_peers_discovered": self.total_peers_discovered,
            "average_response_time": self.average_response_time,
            "success_rate": (
                self.successful_announces / max(self.total_announces, 1)
            ),
        }

    async def get_healthy_trackers(self) -> List[str]:
        """Get list of healthy trackers."""
        return [url for url, conn in self.trackers.items() if conn.is_healthy]

    async def get_tracker_info(self, url: str) -> Optional[TrackerConnection]:
        """Get tracker connection info."""
        return self.trackers.get(url)
