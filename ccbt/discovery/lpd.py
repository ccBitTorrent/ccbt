"""Local Peer Discovery (LPD) implementation (BEP 14).

Provides local network peer discovery using UDP multicast.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# BEP 14 standard multicast address and port
LPD_MULTICAST_ADDRESS = "239.192.152.143"
LPD_MULTICAST_PORT = 6771


class LocalPeerDiscovery:
    """Local Peer Discovery (BEP 14) implementation.

    Discovers peers on the local network using UDP multicast announcements.

    Attributes:
        multicast_address: Multicast group address
        multicast_port: Multicast port
        listen_port: Our listen port to announce
        peer_callback: Callback for discovered peers
        running: Whether LPD is running

    """

    def __init__(
        self,
        listen_port: int,
        multicast_address: str = LPD_MULTICAST_ADDRESS,
        multicast_port: int = LPD_MULTICAST_PORT,
        peer_callback: Callable[[str, int], None] | None = None,
    ):
        """Initialize Local Peer Discovery.

        Args:
            listen_port: Our listen port to announce
            multicast_address: Multicast group address (default: BEP 14 standard)
            multicast_port: Multicast port (default: BEP 14 standard)
            peer_callback: Optional callback for discovered peers (ip, port)

        """
        self.listen_port = listen_port
        self.multicast_address = multicast_address
        self.multicast_port = multicast_port
        self.peer_callback = peer_callback
        self.running = False
        self._socket: socket.socket | None = None
        self._listen_task: asyncio.Task | None = None
        self._announce_task: asyncio.Task | None = None
        self._announce_interval = 300.0  # 5 minutes (BEP 14 recommendation)

    async def start(self) -> None:
        """Start LPD service."""
        if self.running:
            return

        try:
            # Create UDP socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Enable multicast loopback (for testing on same machine)
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

            # Start listening for announcements
            self._listen_task = asyncio.create_task(self._listen())

            # Start periodic announcements
            self._announce_task = asyncio.create_task(self._announce_periodic())

            logger.info(
                "Started Local Peer Discovery on %s:%d",
                self.multicast_address,
                self.multicast_port,
            )
        except Exception as e:
            logger.exception("Failed to start LPD")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop LPD service."""
        if not self.running:
            return

        self.running = False

        # Cancel tasks
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._announce_task:
            self._announce_task.cancel()
            try:
                await self._announce_task
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
                logger.warning("Error closing LPD socket: %s", e)
            finally:
                self._socket = None

        logger.info("Stopped Local Peer Discovery")

    async def announce(self, info_hash: bytes) -> None:
        """Announce torrent to local network.

        Args:
            info_hash: 20-byte info hash (v1) or 32-byte info hash (v2)

        """
        if not self.running or not self._socket:
            return

        try:
            # BEP 14 format: "BT-SEARCH * HTTP/1.1\r\nHost: <multicast_address>:<port>\r\nPort: <listen_port>\r\nInfohash: <info_hash_hex>\r\n\r\n"
            # For v2 (32-byte), we use the first 20 bytes for compatibility
            if len(info_hash) == 32:
                info_hash_v1 = info_hash[:20]
            elif len(info_hash) == 20:
                info_hash_v1 = info_hash
            else:
                logger.warning("Invalid info hash length: %d", len(info_hash))
                return

            message = (
                f"BT-SEARCH * HTTP/1.1\r\n"
                f"Host: {self.multicast_address}:{self.multicast_port}\r\n"
                f"Port: {self.listen_port}\r\n"
                f"Infohash: {info_hash_v1.hex()}\r\n"
                f"\r\n"
            ).encode("utf-8")

            # Send to multicast group
            self._socket.sendto(
                message,
                (self.multicast_address, self.multicast_port),
            )

            logger.debug(
                "Announced torrent %s via LPD",
                info_hash_v1.hex()[:16],
            )
        except Exception as e:
            logger.warning("Failed to send LPD announcement: %s", e)

    async def _listen(self) -> None:
        """Listen for LPD announcements."""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                if not self._socket:
                    break

                # Wait for data
                data, addr = await loop.sock_recvfrom(self._socket, 1024)

                # Parse announcement
                try:
                    message = data.decode("utf-8", errors="ignore")
                    lines = message.split("\r\n")

                    port = None
                    info_hash_hex = None

                    for line in lines:
                        if line.startswith("Port:"):
                            port = int(line.split(":", 1)[1].strip())
                        elif line.startswith("Infohash:"):
                            info_hash_hex = line.split(":", 1)[1].strip()

                    if port and info_hash_hex:
                        peer_ip = addr[0]
                        peer_port = port

                        logger.debug(
                            "Discovered peer %s:%d via LPD (torrent: %s)",
                            peer_ip,
                            peer_port,
                            info_hash_hex[:16],
                        )

                        # Call callback if provided
                        if self.peer_callback:
                            try:
                                self.peer_callback(peer_ip, peer_port)
                            except Exception as e:
                                logger.warning("Error in LPD peer callback: %s", e)

                except (ValueError, IndexError) as e:
                    logger.debug("Invalid LPD message from %s: %s", addr, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in LPD listener: %s", e)
                await asyncio.sleep(1)

    async def _announce_periodic(self) -> None:
        """Periodically announce our presence."""
        # Note: This is a placeholder - actual announcements should be
        # triggered by torrent additions via the announce() method
        while self.running:
            try:
                await asyncio.sleep(self._announce_interval)
                # Periodic announcements are handled by calling announce() for each torrent
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in LPD announcer: %s", e)

    async def discover_peers(self, timeout: float = 5.0) -> list[tuple[str, int]]:
        """Discover peers on local network.

        Args:
            timeout: Timeout in seconds

        Returns:
            List of (ip, port) tuples

        """
        discovered: list[tuple[str, int]] = []
        discovered_set: set[tuple[str, int]] = set()

        def peer_callback(ip: str, port: int) -> None:
            peer_key = (ip, port)
            if peer_key not in discovered_set:
                discovered.append((ip, port))
                discovered_set.add(peer_key)

        # Temporarily set callback
        old_callback = self.peer_callback
        self.peer_callback = peer_callback

        try:
            await asyncio.sleep(timeout)
        finally:
            self.peer_callback = old_callback

        return discovered
