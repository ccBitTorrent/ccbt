"""XET-specific gossip manager for folder and chunk updates.

Wraps generic gossip protocol for XET-specific message types.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from ccbt.discovery.gossip import GossipProtocol

logger = logging.getLogger(__name__)


class XetGossipManager:
    """XET-specific gossip manager.

    Manages gossip propagation for XET chunk and folder updates.

    Attributes:
        gossip_protocol: Underlying gossip protocol instance
        chunk_callbacks: List of callbacks for chunk updates
        folder_callbacks: List of callbacks for folder updates

    """

    def __init__(
        self,
        node_id: str,
        fanout: int = 3,
        interval: float = 5.0,
        peer_callback: Callable[[str], list[str]] | None = None,
    ):
        """Initialize XET gossip manager.

        Args:
            node_id: Unique identifier for this node
            fanout: Gossip fanout (number of peers to gossip to)
            interval: Gossip interval in seconds
            peer_callback: Optional callback to get list of peer IDs

        """
        self.gossip_protocol = GossipProtocol(
            node_id=node_id,
            fanout=fanout,
            interval=interval,
            peer_callback=peer_callback,
        )

        self.chunk_callbacks: list[Callable[[bytes, str, int], None]] = []
        self.folder_callbacks: list[Callable[[dict[str, Any], str, int], None]] = []

    async def start(self) -> None:
        """Start gossip manager."""
        await self.gossip_protocol.start()

    async def stop(self) -> None:
        """Stop gossip manager."""
        await self.gossip_protocol.stop()

    def add_peer(self, peer_id: str) -> None:
        """Add peer to gossip network.

        Args:
            peer_id: Peer identifier

        """
        self.gossip_protocol.add_peer(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        """Remove peer from gossip network.

        Args:
            peer_id: Peer identifier

        """
        self.gossip_protocol.remove_peer(peer_id)

    async def propagate_chunk_update(
        self,
        chunk_hash: bytes,
        peer_ip: str | None = None,
        peer_port: int | None = None,
    ) -> None:
        """Propagate chunk update via gossip.

        Args:
            chunk_hash: 32-byte chunk hash
            peer_ip: Optional peer IP
            peer_port: Optional peer port

        """
        if len(chunk_hash) != 32:
            logger.warning("Invalid chunk hash length: %d", len(chunk_hash))
            return

        message = {
            "type": "chunk_update",
            "chunk_hash": chunk_hash.hex(),
            "peer_ip": peer_ip,
            "peer_port": peer_port,
        }

        await self.gossip_protocol.gossip_update(message)

    async def propagate_folder_update(
        self,
        update_data: dict[str, Any],
        peer_ip: str | None = None,
        peer_port: int | None = None,
    ) -> None:
        """Propagate folder update via gossip.

        Args:
            update_data: Update data dictionary
            peer_ip: Optional peer IP
            peer_port: Optional peer port

        """
        message = {
            "type": "folder_update",
            "update": update_data,
            "peer_ip": peer_ip,
            "peer_port": peer_port,
        }

        await self.gossip_protocol.gossip_update(message)

    async def handle_gossip_message(
        self, peer_id: str, messages: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Handle gossip messages from peer.

        Args:
            peer_id: Peer identifier
            messages: Dictionary of message_id -> message data

        Returns:
            Dictionary of messages to send back to peer

        """
        # Process received messages
        for msg_id, msg in messages.items():
            msg_type = msg.get("type")

            if msg_type == "chunk_update":
                chunk_hash_hex = msg.get("chunk_hash")
                if chunk_hash_hex:
                    chunk_hash = bytes.fromhex(chunk_hash_hex)
                    peer_ip = msg.get("peer_ip")
                    peer_port = msg.get("peer_port")

                    # Call chunk callbacks
                    for callback in self.chunk_callbacks:
                        try:
                            callback(chunk_hash, peer_ip or "", peer_port or 0)
                        except Exception as e:
                            logger.warning("Error in chunk callback: %s", e)

            elif msg_type == "folder_update":
                update_data = msg.get("update", {})
                peer_ip = msg.get("peer_ip")
                peer_port = msg.get("peer_port")

                # Call folder callbacks
                for callback in self.folder_callbacks:
                    try:
                        callback(update_data, peer_ip or "", peer_port or 0)
                    except Exception as e:
                        logger.warning("Error in folder callback: %s", e)

        # Return our messages that peer doesn't have (anti-entropy)
        return await self.gossip_protocol.receive_gossip(peer_id, messages)



