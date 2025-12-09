"""Controlled flooding implementation for urgent message propagation.

Provides TTL-based flooding with duplicate detection to prevent loops.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ControlledFlooding:
    """Controlled flooding for urgent message propagation.

    Implements flooding with TTL and duplicate detection to prevent loops.

    Attributes:
        node_id: Unique identifier for this node
        max_hops: Maximum number of hops (TTL)
        message_handlers: Dictionary of message type -> handler function
        seen_messages: Set of seen message IDs (for deduplication)

    """

    def __init__(
        self,
        node_id: str,
        max_hops: int = 10,
        message_callback: Callable[[dict[str, Any], str, int], None] | None = None,
    ):
        """Initialize controlled flooding.

        Args:
            node_id: Unique identifier for this node
            max_hops: Maximum number of hops (TTL)
            message_callback: Optional callback for received messages

        """
        self.node_id = node_id
        self.max_hops = max_hops
        self.message_callback = message_callback
        self.seen_messages: set[str] = set()
        self._cleanup_interval = 300.0  # Clean up seen messages after 5 minutes
        self._message_timestamps: dict[str, float] = {}

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

    async def flood_message(
        self,
        message: dict[str, Any],
        priority: int = 0,
        target_peers: list[str] | None = None,
    ) -> None:
        """Flood a message to peers.

        Args:
            message: Message data to flood
            priority: Message priority (higher = more urgent)
            target_peers: Optional list of peer IDs to flood to

        """
        message_id = self._generate_message_id(message)

        # Add to seen messages
        self.seen_messages.add(message_id)
        self._message_timestamps[message_id] = time.time()

        # Add flooding metadata
        flood_message = {
            **message,
            "_flood_metadata": {
                "message_id": message_id,
                "ttl": self.max_hops,
                "hops": 0,
                "sender": self.node_id,
                "priority": priority,
            },
        }

        logger.debug("Flooding message %s (priority: %d)", message_id[:8], priority)

        # Forward to target peers (this would typically call network methods)
        if target_peers:
            for peer_id in target_peers:
                try:
                    # This would typically send the message to the peer
                    logger.debug("Forwarding flood message to %s", peer_id)
                except Exception as e:
                    logger.warning("Error forwarding to %s: %s", peer_id, e)

    async def receive_flood(
        self, peer_id: str, message: dict[str, Any]
    ) -> bool:
        """Receive a flooded message.

        Args:
            peer_id: Peer identifier that sent the message
            message: Message data with flooding metadata

        Returns:
            True if message was new and should be forwarded, False otherwise

        """
        flood_metadata = message.get("_flood_metadata", {})
        message_id = flood_metadata.get("message_id")
        ttl = flood_metadata.get("ttl", self.max_hops)
        hops = flood_metadata.get("hops", 0)
        sender = flood_metadata.get("sender")

        if not message_id:
            logger.warning("Received flood message without message_id")
            return False

        # Check if we've seen this message
        if message_id in self.seen_messages:
            logger.debug("Duplicate flood message %s, ignoring", message_id[:8])
            return False

        # Check TTL
        if hops >= ttl:
            logger.debug("Flood message %s exceeded TTL", message_id[:8])
            return False

        # Add to seen messages
        self.seen_messages.add(message_id)
        self._message_timestamps[message_id] = time.time()

        # Remove flooding metadata for callback
        clean_message = {k: v for k, v in message.items() if k != "_flood_metadata"}

        # Call message callback
        if self.message_callback:
            try:
                self.message_callback(clean_message, peer_id, hops)
            except Exception as e:
                logger.warning("Error in flood message callback: %s", e)

        # Forward to other peers (decrement TTL, increment hops)
        new_hops = hops + 1
        if new_hops < ttl:
            # Update metadata for forwarding
            forward_message = {
                **message,
                "_flood_metadata": {
                    **flood_metadata,
                    "hops": new_hops,
                    "sender": self.node_id,
                },
            }

            logger.debug(
                "Forwarding flood message %s (hops: %d/%d)",
                message_id[:8],
                new_hops,
                ttl,
            )

            return True

        return False

    def set_ttl(self, ttl: int) -> None:
        """Set maximum TTL for flooding.

        Args:
            ttl: Time-to-live (max hops)

        """
        if ttl < 1:
            msg = "TTL must be at least 1"
            raise ValueError(msg)
        self.max_hops = ttl

    def set_max_hops(self, max_hops: int) -> None:
        """Set maximum hops (alias for set_ttl).

        Args:
            max_hops: Maximum number of hops

        """
        self.set_ttl(max_hops)

    async def _cleanup_seen_messages(self) -> None:
        """Clean up old seen messages."""
        current_time = time.time()
        expired_messages = [
            msg_id
            for msg_id, timestamp in self._message_timestamps.items()
            if current_time - timestamp > self._cleanup_interval
        ]

        for msg_id in expired_messages:
            self.seen_messages.discard(msg_id)
            del self._message_timestamps[msg_id]

        if expired_messages:
            logger.debug("Cleaned up %d seen messages", len(expired_messages))



