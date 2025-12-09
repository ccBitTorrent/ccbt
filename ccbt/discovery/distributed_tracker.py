"""Distributed Tracker implementation (BEP 33).

Provides distributed tracker functionality using DHT for synchronization.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from ccbt.models import PeerInfo

logger = logging.getLogger(__name__)


class DistributedTracker:
    """Distributed tracker following BEP 33.

    Provides tracker functionality distributed across peers using DHT.

    Attributes:
        dht_client: DHT client for synchronization
        node_id: Unique identifier for this node
        tracker_data: Dictionary of info_hash -> peer list

    """

    def __init__(
        self,
        dht_client: Any,
        node_id: str,
        sync_interval: float = 300.0,  # 5 minutes
    ):
        """Initialize distributed tracker.

        Args:
            dht_client: DHT client instance
            node_id: Unique identifier for this node
            sync_interval: Interval for DHT synchronization in seconds

        """
        self.dht_client = dht_client
        self.node_id = node_id
        self.sync_interval = sync_interval

        # Tracker data: info_hash -> list of (ip, port, peer_id)
        self.tracker_data: dict[bytes, list[tuple[str, int, bytes | None]]] = {}
        self.last_sync = 0.0

    async def announce(
        self,
        info_hash: bytes,
        peer_ip: str,
        peer_port: int,
        peer_id: bytes | None = None,
    ) -> None:
        """Announce peer for torrent.

        Args:
            info_hash: Torrent info hash
            peer_ip: Peer IP address
            peer_port: Peer port
            peer_id: Optional peer ID

        """
        if info_hash not in self.tracker_data:
            self.tracker_data[info_hash] = []

        peer_entry = (peer_ip, peer_port, peer_id)
        if peer_entry not in self.tracker_data[info_hash]:
            self.tracker_data[info_hash].append(peer_entry)

        logger.debug(
            "Announced peer %s:%d for torrent %s",
            peer_ip,
            peer_port,
            info_hash.hex()[:16],
        )

    async def scrape(self, info_hash: bytes) -> dict[str, Any]:
        """Scrape torrent statistics.

        Args:
            info_hash: Torrent info hash

        Returns:
            Dictionary with complete, incomplete, downloaded counts

        """
        peers = self.tracker_data.get(info_hash, [])

        # Simplified scrape - would track more stats in production
        return {
            "complete": len(peers),
            "incomplete": 0,
            "downloaded": 0,
        }

    async def get_peers(
        self,
        info_hash: bytes,
        num_want: int = 50,
    ) -> list[PeerInfo]:
        """Get peers for torrent.

        Args:
            info_hash: Torrent info hash
            num_want: Number of peers to return

        Returns:
            List of peer information

        """
        peers = self.tracker_data.get(info_hash, [])[:num_want]

        # Convert to PeerInfo objects
        peer_infos = []
        for ip, port, peer_id in peers:
            peer_info = PeerInfo(ip=ip, port=port)
            if peer_id:
                peer_info.peer_id = peer_id
            peer_infos.append(peer_info)

        return peer_infos

    async def sync_with_peers(self) -> None:
        """Synchronize tracker data with other peers via DHT.

        Uses DHT (BEP 44) to store and retrieve tracker data.

        """
        current_time = time.time()
        if current_time - self.last_sync < self.sync_interval:
            return  # Too soon to sync again

        try:
            # Store tracker data in DHT
            # Use a tracker key based on node_id
            tracker_key = hashlib.sha256(
                f"distributed_tracker_{self.node_id}".encode()
            ).digest()

            # Serialize tracker data
            tracker_data_serialized = {
                "node_id": self.node_id,
                "timestamp": current_time,
                "torrents": {
                    info_hash.hex(): [
                        {"ip": ip, "port": port, "peer_id": peer_id.hex() if peer_id else None}
                        for ip, port, peer_id in peers
                    ]
                    for info_hash, peers in self.tracker_data.items()
                },
            }

            if hasattr(self.dht_client, "store"):
                await self.dht_client.store(tracker_key, tracker_data_serialized)
                self.last_sync = current_time
                logger.debug("Synchronized distributed tracker with DHT")

            # Also retrieve data from other peers
            if hasattr(self.dht_client, "get_value"):
                # Query for other tracker nodes
                # (Simplified - would query multiple nodes in production)
                try:
                    other_data = await self.dht_client.get_value(tracker_key)
                    if other_data and isinstance(other_data, dict):
                        # Merge with our data
                        other_torrents = other_data.get("torrents", {})
                        for info_hash_hex, peers_list in other_torrents.items():
                            info_hash = bytes.fromhex(info_hash_hex)
                            if info_hash not in self.tracker_data:
                                self.tracker_data[info_hash] = []

                            for peer_data in peers_list:
                                peer_entry = (
                                    peer_data["ip"],
                                    peer_data["port"],
                                    bytes.fromhex(peer_data["peer_id"])
                                    if peer_data.get("peer_id")
                                    else None,
                                )
                                if peer_entry not in self.tracker_data[info_hash]:
                                    self.tracker_data[info_hash].append(peer_entry)

                        logger.debug(
                            "Merged tracker data from DHT: %d torrents",
                            len(other_torrents),
                        )
                except Exception as e:
                    logger.debug("No other tracker data found in DHT: %s", e)

        except Exception as e:
            logger.warning("Failed to sync distributed tracker: %s", e)



