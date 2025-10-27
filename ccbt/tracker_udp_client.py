"""UDP Tracker Client (BEP 15) for BitTorrent.

High-performance async UDP tracker communication with retry logic,
concurrent announces across multiple tracker tiers, and proper error handling.
"""

import asyncio
import logging
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .config import get_config


class TrackerAction(Enum):
    """UDP tracker actions."""
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


class TrackerEvent(Enum):
    """Tracker announce events."""
    NONE = 0
    COMPLETED = 1
    STARTED = 2
    STOPPED = 3


@dataclass
class TrackerResponse:
    """UDP tracker response."""
    action: TrackerAction
    transaction_id: int
    connection_id: Optional[int] = None
    interval: Optional[int] = None
    leechers: Optional[int] = None
    seeders: Optional[int] = None
    peers: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None


@dataclass
class TrackerSession:
    """UDP tracker session state."""
    url: str
    host: str
    port: int
    connection_id: Optional[int] = None
    connection_time: float = 0.0
    last_announce: float = 0.0
    retry_count: int = 0
    backoff_delay: float = 1.0
    max_retries: int = 3
    is_connected: bool = False


class AsyncUDPTrackerClient:
    """High-performance async UDP tracker client."""

    def __init__(self, peer_id: Optional[bytes] = None):
        """Initialize UDP tracker client.
        
        Args:
            peer_id: Our peer ID (20 bytes)
        """
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Tracker sessions
        self.sessions: Dict[str, TrackerSession] = {}

        # UDP socket
        self.socket: Optional[asyncio.DatagramProtocol] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.transaction_counter = 0

        # Pending requests
        self.pending_requests: Dict[int, asyncio.Future] = {}

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the UDP tracker client."""
        # Create UDP socket
        loop = asyncio.get_event_loop()
        self.transport, self.socket = await loop.create_datagram_endpoint(
            lambda: UDPTrackerProtocol(self),
            local_addr=("0.0.0.0", 0),
        )

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self.logger.info("UDP tracker client started")

    async def stop(self) -> None:
        """Stop the UDP tracker client."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self.transport:
            self.transport.close()

        # Cancel pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()

        self.logger.info("UDP tracker client stopped")

    async def announce(self, torrent_data: Dict[str, Any],
                      uploaded: int = 0, downloaded: int = 0, left: Optional[int] = None,
                      event: TrackerEvent = TrackerEvent.STARTED) -> List[Dict[str, Any]]:
        """Announce to UDP trackers and get peer list.
        
        Args:
            torrent_data: Parsed torrent data
            uploaded: Bytes uploaded
            downloaded: Bytes downloaded
            left: Bytes left to download
            event: Announce event
            
        Returns:
            List of peer dictionaries
        """
        if left is None:
            left = torrent_data["file_info"]["total_length"]

        # Get tracker URLs
        tracker_urls = self._extract_tracker_urls(torrent_data)
        if not tracker_urls:
            self.logger.warning("No UDP trackers found")
            return []

        # Announce to all trackers concurrently
        tasks = []
        for url in tracker_urls:
            task = asyncio.create_task(self._announce_to_tracker(
                url, torrent_data, uploaded, downloaded, left, event,
            ))
            tasks.append(task)

        # Wait for all announces to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all peers
        all_peers = []
        for result in results:
            if isinstance(result, list):
                all_peers.extend(result)
            elif isinstance(result, Exception):
                self.logger.debug(f"Tracker announce failed: {result}")

        # Deduplicate peers
        peer_set = set()
        unique_peers = []
        for peer in all_peers:
            peer_key = (peer["ip"], peer["port"])
            if peer_key not in peer_set:
                peer_set.add(peer_key)
                unique_peers.append(peer)

        self.logger.info(f"Got {len(unique_peers)} unique peers from {len(tracker_urls)} trackers")
        return unique_peers

    def _extract_tracker_urls(self, torrent_data: Dict[str, Any]) -> List[str]:
        """Extract UDP tracker URLs from torrent data."""
        urls = []

        # Single announce URL
        if "announce" in torrent_data:
            url = torrent_data["announce"]
            if url.startswith("udp://"):
                urls.append(url)

        # Announce list
        if "announce_list" in torrent_data:
            for tier in torrent_data["announce_list"]:
                for url in tier:
                    if url.startswith("udp://"):
                        urls.append(url)

        return urls

    async def _announce_to_tracker(self, url: str, torrent_data: Dict[str, Any],
                                 uploaded: int, downloaded: int, left: int,
                                 event: TrackerEvent) -> List[Dict[str, Any]]:
        """Announce to a single UDP tracker."""
        try:
            # Parse URL
            host, port = self._parse_udp_url(url)

            # Get or create session
            session_key = f"{host}:{port}"
            if session_key not in self.sessions:
                self.sessions[session_key] = TrackerSession(url, host, port)

            session = self.sessions[session_key]

            # Connect if needed
            if not session.is_connected:
                await self._connect_to_tracker(session)

            if not session.is_connected:
                return []

            # Send announce
            peers = await self._send_announce(session, torrent_data, uploaded, downloaded, left, event)
            return peers

        except Exception as e:
            self.logger.debug(f"Failed to announce to {url}: {e}")
            return []

    def _parse_udp_url(self, url: str) -> Tuple[str, int]:
        """Parse UDP tracker URL."""
        # Remove udp:// prefix
        if url.startswith("udp://"):
            url = url[6:]

        # Split host:port
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            port = int(port_str)
        else:
            host = url
            port = 80  # Default port

        return host, port

    async def _connect_to_tracker(self, session: TrackerSession) -> None:
        """Connect to a UDP tracker."""
        try:
            # Send connect request
            transaction_id = self._get_transaction_id()
            connect_data = struct.pack("!QII", 0x41727101980, TrackerAction.CONNECT.value, transaction_id)

            # Send request
            self.transport.sendto(connect_data, (session.host, session.port))

            # Wait for response
            response = await self._wait_for_response(transaction_id, timeout=10.0)

            if response and response.action == TrackerAction.CONNECT:
                session.connection_id = response.connection_id
                session.connection_time = time.time()
                session.is_connected = True
                session.retry_count = 0
                session.backoff_delay = 1.0
                self.logger.debug(f"Connected to tracker {session.host}:{session.port}")
            else:
                raise ConnectionError("Failed to connect to tracker")

        except Exception as e:
            session.is_connected = False
            session.retry_count += 1
            session.backoff_delay = min(session.backoff_delay * 2, 60.0)
            self.logger.debug(f"Failed to connect to {session.host}:{session.port}: {e}")
            raise

    async def _send_announce(self, session: TrackerSession, torrent_data: Dict[str, Any],
                           uploaded: int, downloaded: int, left: int,
                           event: TrackerEvent) -> List[Dict[str, Any]]:
        """Send announce request to tracker."""
        try:
            # Check if we need to reconnect
            if (time.time() - session.connection_time > 60.0 or
                not session.is_connected):
                await self._connect_to_tracker(session)

            if not session.is_connected:
                return []

            # Build announce request
            transaction_id = self._get_transaction_id()
            info_hash = torrent_data["info_hash"]

            announce_data = struct.pack(
                "!QII20s20sQQQIIIH",
                session.connection_id,
                TrackerAction.ANNOUNCE.value,
                transaction_id,
                info_hash,
                self.our_peer_id,
                downloaded,
                left,
                uploaded,
                event.value,
                0,  # IP address (0 = use sender IP)
                0,  # Key
                -1,  # num_want (-1 = default)
            )

            # Send request
            self.transport.sendto(announce_data, (session.host, session.port))

            # Wait for response
            response = await self._wait_for_response(transaction_id, timeout=10.0)

            if response and response.action == TrackerAction.ANNOUNCE:
                session.last_announce = time.time()
                session.interval = response.interval
                return response.peers or []
            self.logger.debug(f"Announce failed for {session.host}:{session.port}")
            return []

        except Exception as e:
            self.logger.debug(f"Announce error for {session.host}:{session.port}: {e}")
            return []

    def _get_transaction_id(self) -> int:
        """Get next transaction ID."""
        self.transaction_counter = (self.transaction_counter + 1) % 65536
        return self.transaction_counter

    async def _wait_for_response(self, transaction_id: int, timeout: float) -> Optional[TrackerResponse]:
        """Wait for UDP tracker response."""
        future = asyncio.Future()
        self.pending_requests[transaction_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self.logger.debug(f"Timeout waiting for tracker response {transaction_id}")
            return None
        finally:
            self.pending_requests.pop(transaction_id, None)

    def handle_response(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming UDP response."""
        try:
            if len(data) < 8:
                return

            # Parse response header
            action = struct.unpack("!I", data[0:4])[0]
            transaction_id = struct.unpack("!I", data[4:8])[0]

            # Check if we have a pending request for this transaction
            if transaction_id not in self.pending_requests:
                return

            future = self.pending_requests[transaction_id]
            if future.done():
                return

            # Parse response based on action
            if action == TrackerAction.CONNECT.value:
                if len(data) >= 16:
                    connection_id = struct.unpack("!Q", data[8:16])[0]
                    response = TrackerResponse(
                        action=TrackerAction.CONNECT,
                        transaction_id=transaction_id,
                        connection_id=connection_id,
                    )
                    future.set_result(response)

            elif action == TrackerAction.ANNOUNCE.value:
                if len(data) >= 20:
                    interval = struct.unpack("!I", data[8:12])[0]
                    leechers = struct.unpack("!I", data[12:16])[0]
                    seeders = struct.unpack("!I", data[16:20])[0]

                    # Parse peers (compact format)
                    peers = []
                    if len(data) > 20:
                        peer_data = data[20:]
                        for i in range(0, len(peer_data), 6):
                            if i + 6 <= len(peer_data):
                                peer_bytes = peer_data[i:i+6]
                                ip = ".".join(str(b) for b in peer_bytes[:4])
                                port = int.from_bytes(peer_bytes[4:6], "big")
                                peers.append({"ip": ip, "port": port})

                    response = TrackerResponse(
                        action=TrackerAction.ANNOUNCE,
                        transaction_id=transaction_id,
                        interval=interval,
                        leechers=leechers,
                        seeders=seeders,
                        peers=peers,
                    )
                    future.set_result(response)

            elif action == TrackerAction.ERROR.value:
                error_message = data[8:].decode("utf-8", errors="ignore")
                response = TrackerResponse(
                    action=TrackerAction.ERROR,
                    transaction_id=transaction_id,
                    error_message=error_message,
                )
                future.set_result(response)

        except Exception as e:
            self.logger.debug(f"Error parsing tracker response: {e}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old sessions."""
        while True:
            try:
                await asyncio.sleep(300.0)  # Clean every 5 minutes
                await self._cleanup_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_sessions(self) -> None:
        """Clean up old tracker sessions."""
        current_time = time.time()
        to_remove = []

        for session_key, session in self.sessions.items():
            # Remove sessions that haven't been used for 1 hour
            if current_time - session.last_announce > 3600.0 or session.retry_count >= session.max_retries:
                to_remove.append(session_key)

        for session_key in to_remove:
            del self.sessions[session_key]

    async def scrape(self, torrent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape tracker for statistics.
        
        Args:
            torrent_data: Parsed torrent data
            
        Returns:
            Scraped statistics
        """
        # TODO: Implement UDP scrape
        return {}


class UDPTrackerProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for tracker communication."""

    def __init__(self, client: AsyncUDPTrackerClient):
        self.client = client

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        self.client.handle_response(data, addr)

    def error_received(self, exc: Exception) -> None:
        """Handle UDP error."""
        self.client.logger.debug(f"UDP error: {exc}")


# Global UDP tracker client instance
_udp_tracker_client: Optional[AsyncUDPTrackerClient] = None


def get_udp_tracker_client() -> AsyncUDPTrackerClient:
    """Get the global UDP tracker client."""
    global _udp_tracker_client
    if _udp_tracker_client is None:
        _udp_tracker_client = AsyncUDPTrackerClient()
    return _udp_tracker_client


async def init_udp_tracker() -> AsyncUDPTrackerClient:
    """Initialize global UDP tracker client."""
    global _udp_tracker_client
    _udp_tracker_client = AsyncUDPTrackerClient()
    await _udp_tracker_client.start()
    return _udp_tracker_client


async def shutdown_udp_tracker() -> None:
    """Shutdown global UDP tracker client."""
    global _udp_tracker_client
    if _udp_tracker_client:
        await _udp_tracker_client.stop()
        _udp_tracker_client = None
