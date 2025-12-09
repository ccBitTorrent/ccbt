"""XET-specific multicast broadcasting for chunk and folder updates.

Provides multicast-based broadcasting for XET protocol updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class XetMulticastBroadcaster:
    """XET-specific multicast broadcaster.

    Broadcasts chunk announcements and folder updates via UDP multicast.

    Attributes:
        multicast_address: Multicast group address
        multicast_port: Multicast port
        running: Whether broadcaster is running
        message_handlers: Dictionary of message type -> handler function

    """

    def __init__(
        self,
        multicast_address: str = "239.255.255.250",
        multicast_port: int = 6882,
        chunk_callback: Callable[[bytes, str, int], None] | None = None,
        update_callback: Callable[[dict[str, Any], str, int], None] | None = None,
    ):
        """Initialize XET multicast broadcaster.

        Args:
            multicast_address: Multicast group address
            multicast_port: Multicast port
            chunk_callback: Optional callback for chunk announcements (chunk_hash, ip, port)
            update_callback: Optional callback for folder updates (update_data, ip, port)

        """
        self.multicast_address = multicast_address
        self.multicast_port = multicast_port
        self.chunk_callback = chunk_callback
        self.update_callback = update_callback
        self.running = False
        self._socket: socket.socket | None = None
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start multicast broadcaster."""
        if self.running:
            return

        try:
            # Create UDP socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Enable multicast loopback
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

            # Bind to multicast port
            self._socket.bind(("", self.multicast_port))

            # Join multicast group
            multicast_group = socket.inet_aton(self.multicast_address)
            mreq = struct.pack("4sL", multicast_group, socket.INADDR_ANY)
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            # Set socket to non-blocking
            self._socket.setblocking(False)

            self.running = True

            # Start listening for broadcasts
            self._listen_task = asyncio.create_task(self._listen_for_broadcasts())

            logger.info(
                "Started XET multicast broadcaster on %s:%d",
                self.multicast_address,
                self.multicast_port,
            )
        except Exception as e:
            logger.exception("Failed to start XET multicast broadcaster")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop multicast broadcaster."""
        if not self.running:
            return

        self.running = False

        # Cancel listen task
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        # Close socket
        if self._socket:
            try:
                # Leave multicast group
                multicast_group = socket.inet_aton(self.multicast_address)
                mreq = struct.pack("4sL", multicast_group, socket.INADDR_ANY)
                self._socket.setsockopt(
                    socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq
                )
                self._socket.close()
            except Exception as e:
                logger.warning("Error closing multicast socket: %s", e)
            finally:
                self._socket = None

        logger.info("Stopped XET multicast broadcaster")

    async def broadcast_chunk_announcement(
        self,
        chunk_hash: bytes,
        peer_ip: str | None = None,
        peer_port: int | None = None,
    ) -> None:
        """Broadcast chunk announcement.

        Args:
            chunk_hash: 32-byte chunk hash
            peer_ip: Optional peer IP (uses local IP if None)
            peer_port: Optional peer port

        """
        if not self.running or not self._socket:
            return

        if len(chunk_hash) != 32:
            logger.warning("Invalid chunk hash length: %d", len(chunk_hash))
            return

        try:
            # Message format: JSON with type, chunk_hash, peer info
            message = {
                "type": "chunk_announcement",
                "chunk_hash": chunk_hash.hex(),
                "timestamp": time.time(),
            }

            if peer_ip and peer_port:
                message["peer_ip"] = peer_ip
                message["peer_port"] = peer_port

            message_bytes = json.dumps(message).encode("utf-8")

            # Pack: <length><message>
            packed = struct.pack("!I", len(message_bytes)) + message_bytes

            # Send to multicast group
            self._socket.sendto(
                packed,
                (self.multicast_address, self.multicast_port),
            )

            logger.debug(
                "Broadcast chunk announcement: %s",
                chunk_hash.hex()[:16],
            )
        except Exception as e:
            logger.warning("Failed to broadcast chunk announcement: %s", e)

    async def broadcast_update(
        self,
        update_data: dict[str, Any],
        peer_ip: str | None = None,
        peer_port: int | None = None,
    ) -> None:
        """Broadcast folder update.

        Args:
            update_data: Update data dictionary
            peer_ip: Optional peer IP
            peer_port: Optional peer port

        """
        if not self.running or not self._socket:
            return

        try:
            # Message format: JSON with type, update data, peer info
            message = {
                "type": "folder_update",
                "update": update_data,
                "timestamp": time.time(),
            }

            if peer_ip and peer_port:
                message["peer_ip"] = peer_ip
                message["peer_port"] = peer_port

            message_bytes = json.dumps(message).encode("utf-8")

            # Pack: <length><message>
            packed = struct.pack("!I", len(message_bytes)) + message_bytes

            # Send to multicast group
            self._socket.sendto(
                packed,
                (self.multicast_address, self.multicast_port),
            )

            logger.debug("Broadcast folder update via multicast")
        except Exception as e:
            logger.warning("Failed to broadcast folder update: %s", e)

    async def _listen_for_broadcasts(self) -> None:
        """Listen for multicast broadcasts."""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                if not self._socket:
                    break

                # Wait for data
                data, addr = await loop.sock_recvfrom(self._socket, 4096)

                # Parse message
                try:
                    if len(data) < 4:
                        continue

                    # Unpack length
                    message_length = struct.unpack("!I", data[:4])[0]
                    if len(data) < 4 + message_length:
                        continue

                    # Parse JSON message
                    message_bytes = data[4 : 4 + message_length]
                    message = json.loads(message_bytes.decode("utf-8"))

                    message_type = message.get("type")
                    sender_ip = addr[0]
                    sender_port = addr[1]

                    if message_type == "chunk_announcement":
                        chunk_hash_hex = message.get("chunk_hash")
                        if chunk_hash_hex:
                            chunk_hash = bytes.fromhex(chunk_hash_hex)
                            peer_ip = message.get("peer_ip", sender_ip)
                            peer_port = message.get("peer_port", sender_port)

                            logger.debug(
                                "Received chunk announcement: %s from %s:%d",
                                chunk_hash.hex()[:16],
                                peer_ip,
                                peer_port,
                            )

                            if self.chunk_callback:
                                try:
                                    self.chunk_callback(chunk_hash, peer_ip, peer_port)
                                except Exception as e:
                                    logger.warning(
                                        "Error in chunk callback: %s", e
                                    )

                    elif message_type == "folder_update":
                        update_data = message.get("update", {})
                        peer_ip = message.get("peer_ip", sender_ip)
                        peer_port = message.get("peer_port", sender_port)

                        logger.debug(
                            "Received folder update from %s:%d",
                            peer_ip,
                            peer_port,
                        )

                        if self.update_callback:
                            try:
                                self.update_callback(update_data, peer_ip, peer_port)
                            except Exception as e:
                                logger.warning("Error in update callback: %s", e)

                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.debug("Invalid multicast message from %s: %s", addr, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in multicast listener: %s", e)
                await asyncio.sleep(1)



