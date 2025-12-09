"""Gossip protocol implementation for epidemic-style message propagation.

Provides anti-entropy and rumor mongering strategies for distributed updates.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class GossipProtocol:
    """Gossip protocol for epidemic-style message propagation.

    Implements anti-entropy and rumor mongering strategies.

    Attributes:
        node_id: Unique identifier for this node
        fanout: Number of peers to gossip to per round
        interval: Gossip interval in seconds
        peers: Set of peer identifiers
        messages: Dictionary of message_id -> message data
        message_ttl: Time-to-live for messages in seconds

    """

    def __init__(
        self,
        node_id: str,
        fanout: int = 3,
        interval: float = 5.0,
        message_ttl: float = 300.0,  # 5 minutes
        peer_callback: Callable[[str], list[str]] | None = None,
    ):
        """Initialize gossip protocol.

        Args:
            node_id: Unique identifier for this node
            fanout: Number of peers to gossip to per round
            interval: Gossip interval in seconds
            message_ttl: Time-to-live for messages
            peer_callback: Optional callback to get list of peer IDs

        """
        self.node_id = node_id
        self.fanout = fanout
        self.interval = interval
        self.message_ttl = message_ttl
        self.peer_callback = peer_callback

        self.peers: set[str] = set()
        self.messages: dict[str, dict[str, Any]] = {}
        self.message_timestamps: dict[str, float] = {}
        self.received_messages: set[str] = set()  # For deduplication

        self.running = False
        self._gossip_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start gossip protocol."""
        if self.running:
            return

        self.running = True

        # Start gossip task
        self._gossip_task = asyncio.create_task(self._gossip_loop())

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Started gossip protocol (node_id: %s)", self.node_id)

    async def stop(self) -> None:
        """Stop gossip protocol."""
        if not self.running:
            return

        self.running = False

        # Cancel tasks
        if self._gossip_task:
            self._gossip_task.cancel()
            try:
                await self._gossip_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped gossip protocol")

    def add_peer(self, peer_id: str) -> None:
        """Add peer to gossip network.

        Args:
            peer_id: Peer identifier

        """
        if peer_id != self.node_id:
            self.peers.add(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        """Remove peer from gossip network.

        Args:
            peer_id: Peer identifier

        """
        self.peers.discard(peer_id)

    def get_peers(self) -> list[str]:
        """Get list of peer IDs.

        Returns:
            List of peer identifiers

        """
        if self.peer_callback:
            try:
                return self.peer_callback(self.node_id)
            except Exception as e:
                logger.warning("Error in peer callback: %s", e)

        return list(self.peers)

    def _generate_message_id(self, message: dict[str, Any]) -> str:
        """Generate unique message ID.

        Args:
            message: Message data

        Returns:
            Message ID (hash)

        """
        # Create deterministic hash from message content
        message_str = str(sorted(message.items()))
        return hashlib.sha256(message_str.encode()).hexdigest()[:16]

    async def gossip_update(self, message: dict[str, Any]) -> None:
        """Gossip an update to peers.

        Args:
            message: Message data to gossip

        """
        message_id = self._generate_message_id(message)

        # Add to our messages
        self.messages[message_id] = message
        self.message_timestamps[message_id] = time.time()
        self.received_messages.add(message_id)

        logger.debug("Gossiping message %s", message_id[:8])

    async def receive_gossip(
        self, peer_id: str, messages: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Receive gossip from peer (anti-entropy).

        Args:
            peer_id: Peer identifier
            messages: Dictionary of message_id -> message data from peer

        Returns:
            Dictionary of message_id -> message data that peer doesn't have

        """
        # Add peer if not already known
        self.add_peer(peer_id)

        # Find messages we have that peer doesn't
        our_messages: dict[str, dict[str, Any]] = {}
        for msg_id, msg in self.messages.items():
            if msg_id not in messages:
                our_messages[msg_id] = msg

        # Add new messages from peer
        for msg_id, msg in messages.items():
            if msg_id not in self.received_messages:
                self.messages[msg_id] = msg
                self.message_timestamps[msg_id] = time.time()
                self.received_messages.add(msg_id)
                logger.debug("Received new message %s from %s", msg_id[:8], peer_id)

        return our_messages

    async def _gossip_loop(self) -> None:
        """Main gossip loop (rumor mongering)."""
        while self.running:
            try:
                await asyncio.sleep(self.interval)

                if not self.messages:
                    continue

                # Get random peers to gossip to
                available_peers = self.get_peers()
                if not available_peers:
                    continue

                # Select random peers (fanout)
                num_peers = min(self.fanout, len(available_peers))
                selected_peers = random.sample(available_peers, num_peers)

                # Gossip recent messages to selected peers
                recent_messages = {
                    msg_id: msg
                    for msg_id, msg in self.messages.items()
                    if time.time() - self.message_timestamps[msg_id] < self.message_ttl
                }

                if recent_messages:
                    for peer_id in selected_peers:
                        try:
                            # This would typically call a network method to send gossip
                            # For now, we just log it
                            logger.debug(
                                "Gossiping %d messages to %s",
                                len(recent_messages),
                                peer_id,
                            )
                        except Exception as e:
                            logger.warning("Error gossiping to %s: %s", peer_id, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in gossip loop: %s", e)
                await asyncio.sleep(1)

    async def _cleanup_loop(self) -> None:
        """Cleanup expired messages."""
        while self.running:
            try:
                await asyncio.sleep(60.0)  # Cleanup every minute

                current_time = time.time()
                expired_messages = [
                    msg_id
                    for msg_id, timestamp in self.message_timestamps.items()
                    if current_time - timestamp > self.message_ttl
                ]

                for msg_id in expired_messages:
                    del self.messages[msg_id]
                    del self.message_timestamps[msg_id]

                if expired_messages:
                    logger.debug("Cleaned up %d expired messages", len(expired_messages))

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in cleanup loop: %s", e)
                await asyncio.sleep(1)



