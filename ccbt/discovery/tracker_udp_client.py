"""UDP Tracker Client (BEP 15) for BitTorrent.

High-performance async UDP tracker communication with retry logic,
concurrent announces across multiple tracker tiers, and proper error handling.
"""

import asyncio
import contextlib
import logging
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ccbt.config.config import get_config

# Error message constants
_ERROR_UDP_TRANSPORT_NOT_INITIALIZED = "UDP transport is not initialized"


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
    connection_id: int | None = None
    interval: int | None = None
    leechers: int | None = None
    seeders: int | None = None
    peers: list[dict[str, Any]] | None = None
    error_message: str | None = None
    # Scrape-specific fields
    complete: int | None = None  # Seeders in scrape response
    downloaded: int | None = None  # Completed downloads in scrape response
    incomplete: int | None = None  # Leechers in scrape response


@dataclass
class TrackerSession:
    """UDP tracker session state."""

    url: str
    host: str
    port: int
    connection_id: int | None = None
    connection_time: float = 0.0
    last_announce: float = 0.0
    # Interval suggested by tracker for next announce (seconds)
    interval: int | None = None
    retry_count: int = 0
    backoff_delay: float = 1.0
    max_retries: int = 3
    is_connected: bool = False


class AsyncUDPTrackerClient:
    """High-performance async UDP tracker client."""

    def __init__(self, peer_id: bytes | None = None):
        """Initialize UDP tracker client.

        Args:
            peer_id: Our peer ID (20 bytes)

        """
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Tracker sessions
        self.sessions: dict[str, TrackerSession] = {}

        # UDP socket
        self.socket: asyncio.DatagramProtocol | None = None
        self.transport: asyncio.DatagramTransport | None = None
        self.transaction_counter = 0

        # Pending requests
        self.pending_requests: dict[int, asyncio.Future] = {}

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None

        # CRITICAL FIX: Add lock to prevent concurrent socket operations
        # Windows requires serialized access to UDP sockets to prevent WinError 10022
        self._socket_lock: asyncio.Lock = asyncio.Lock()
        self._socket_ready: bool = False

        # CRITICAL FIX: Track WinError 10022 warning frequency to reduce verbosity
        # Only log at WARNING level once per time period, then use DEBUG for subsequent occurrences
        self._last_winerror_warning_time: float = 0.0
        self._winerror_warning_interval: float = 30.0  # Log WARNING once per 30 seconds

        # CRITICAL FIX: Socket health monitoring to prevent aggressive recreation
        self._socket_error_count: int = 0
        self._socket_last_error_time: float = 0.0
        self._socket_health_check_interval: float = (
            5.0  # Check socket health every 5 seconds
        )
        self._socket_recreation_backoff: float = (
            1.0  # Exponential backoff for socket recreation
        )
        self._max_socket_recreation_backoff: float = 60.0  # Max backoff of 60 seconds
        self._socket_recreation_count: int = 0
        self._last_socket_health_check: float = 0.0

        self.logger = logging.getLogger(__name__)

    def _raise_connection_failed(self) -> None:
        """Raise ConnectionError for failed tracker connection."""
        msg = "Failed to connect to tracker"
        raise ConnectionError(msg)

    def _check_socket_health(self) -> bool:
        """Check if socket is healthy and ready for use.

        Returns:
            True if socket is healthy, False otherwise

        """
        if self.transport is None:
            return False
        if self.transport.is_closing():
            return False
        if not self._socket_ready:
            return False

        # Additional health checks
        try:
            # Check if transport has socket info
            sockname = self.transport.get_extra_info("sockname")
            if sockname is None:
                return False
        except Exception:
            return False

        return True

    def _validate_socket_ready(self) -> None:
        """Validate socket is ready, raise RuntimeError if not.

        CRITICAL: Socket must be initialized during daemon startup via start_udp_tracker_client().
        Socket recreation is not supported as it breaks session logic.
        """
        if not self._check_socket_health():
            # CRITICAL FIX: Don't recreate socket on transient errors
            # Only raise error if socket is truly invalid
            current_time = time.time()

            # Reset error count if enough time has passed
            if (
                current_time - self._socket_last_error_time
                > self._socket_health_check_interval
            ):
                self._socket_error_count = 0

            # Only raise error if socket is truly invalid (not just transient error)
            if self.transport is None or self.transport.is_closing():
                raise RuntimeError(
                    "UDP tracker client socket is invalid. "
                    "Socket must be initialized during daemon startup via start_udp_tracker_client(). "
                    "Socket recreation is not supported as it breaks session logic."
                )

            # If socket appears invalid but might be transient, log and allow retry
            if not self._socket_ready:
                self.logger.debug(
                    "Socket not ready but transport exists - may be transient (error_count: %d)",
                    self._socket_error_count,
                )
                # Don't raise error for transient issues - let retry logic handle it
                return

    async def start(self) -> None:
        """Start the UDP tracker client.

        CRITICAL: Socket must be initialized during daemon startup via start_udp_tracker_client().
        Socket recreation is not supported as it breaks session logic.
        """
        # CRITICAL FIX: Assert socket should never be recreated during runtime
        # If socket is already initialized and healthy, return immediately
        # Socket recreation breaks session logic and causes WinError 10022 on Windows
        if (
            self._socket_ready
            and self.transport is not None
            and not self.transport.is_closing()
        ):
            if self._check_socket_health():
                self.logger.debug(
                    "UDP socket already ready and healthy, skipping start() (socket should never be recreated)"
                )
                # Reset error counters since socket is healthy
                self._socket_error_count = 0
                self._socket_recreation_backoff = 1.0
                return
            # Socket is marked ready but health check failed - log warning
            self.logger.warning(
                "UDP socket marked ready but health check failed. "
                "Socket should have been initialized during daemon startup. "
                "Attempting recovery (this should not happen in normal operation)."
            )

        # Use lock to prevent concurrent start() calls
        async with self._socket_lock:
            # CRITICAL FIX: Double-check socket health after acquiring lock
            if (
                self._socket_ready
                and self.transport is not None
                and not self.transport.is_closing()
            ):
                if self._check_socket_health():
                    self.logger.debug(
                        "UDP socket already ready and healthy after lock acquisition, skipping start()"
                    )
                    return

            # CRITICAL FIX: Apply exponential backoff to prevent aggressive socket recreation
            current_time = time.time()
            time_since_last_recreation = current_time - self._socket_last_error_time

            if (
                self._socket_recreation_count > 0
                and time_since_last_recreation < self._socket_recreation_backoff
            ):
                wait_time = self._socket_recreation_backoff - time_since_last_recreation
                self.logger.debug(
                    "Socket recreation backoff active: waiting %.1fs before recreation (recreation_count: %d)",
                    wait_time,
                    self._socket_recreation_count,
                )
                await asyncio.sleep(wait_time)

            # Increment recreation counter and update backoff
            self._socket_recreation_count += 1
            self._socket_recreation_backoff = min(
                self._socket_recreation_backoff * 2.0,
                self._max_socket_recreation_backoff,
            )
            self._socket_last_error_time = current_time

            # CRITICAL FIX: Prevent socket recreation - fail gracefully instead
            # Socket should have been initialized during daemon startup
            # Recreation breaks session logic and causes WinError 10022 on Windows
            if self.transport is not None and not self.transport.is_closing():
                self.logger.error(
                    "CRITICAL: Attempted to recreate UDP tracker socket during runtime. "
                    "Socket should have been initialized during daemon startup and never recreated. "
                    "This breaks session logic. Socket state: ready=%s, transport=%s, closing=%s, error_count=%d. "
                    "Failing gracefully instead of recreating socket.",
                    self._socket_ready,
                    self.transport is not None,
                    self.transport.is_closing() if self.transport else None,
                    self._socket_error_count,
                )
                raise RuntimeError(
                    "UDP tracker socket recreation is not allowed. "
                    "Socket must be initialized during daemon startup via start_udp_tracker_client(). "
                    "If socket is invalid, daemon must be restarted."
                )

            # Mark socket as not ready before closing (lock already held)
            # Only close if transport exists and is closing (cleanup scenario)
            self._socket_ready = False
            if self.transport is not None:
                try:
                    self.transport.close()
                    # CRITICAL FIX: Wait longer on Windows Proactor for socket to fully close
                    import sys

                    loop = asyncio.get_event_loop()
                    is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                    if sys.platform == "win32" and is_proactor:
                        await asyncio.sleep(0.3)  # Longer wait for Proactor
                    else:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug("Error closing existing transport: %s", e)
                finally:
                    self.transport = None
                    self.socket = None

        # CRITICAL FIX: Only create new socket if transport is None or closing
        # This should only happen during initial daemon startup, not during runtime
        if self.transport is not None and not self.transport.is_closing():
            self.logger.error(
                "CRITICAL: Attempted to create new UDP socket when existing socket is valid. "
                "This should never happen - socket should be initialized once at daemon startup."
            )
            raise RuntimeError(
                "Cannot create new UDP socket - existing socket is valid"
            )

        # Create UDP socket
        import socket as std_socket

        loop = asyncio.get_event_loop()

        # Create socket with proper options
        sock = std_socket.socket(std_socket.AF_INET, std_socket.SOCK_DGRAM)

        try:
            # Set socket options
            try:
                sock.setsockopt(
                    std_socket.SOL_SOCKET, std_socket.SO_RCVBUF, 131072
                )  # 128KB
                sock.setsockopt(
                    std_socket.SOL_SOCKET, std_socket.SO_SNDBUF, 131072
                )  # 128KB
            except OSError:
                pass  # Continue if buffer size setting fails

            # Set socket to non-blocking mode for asyncio
            sock.setblocking(False)

            # Bind to configured tracker UDP port
            # Use tracker_udp_port if available, fallback to listen_port for backward compatibility
            configured_port = (
                self.config.network.tracker_udp_port
                or self.config.network.listen_port
            )
            sock.bind(("0.0.0.0", configured_port))  # nosec B104 - Bind to all interfaces on configured port
            self.logger.debug("Bound UDP tracker socket to port %d", configured_port)

        except OSError as e:
            sock.close()
            # CRITICAL FIX: Enhanced port conflict error handling
            error_code = e.errno if hasattr(e, "errno") else None
            import sys

            if sys.platform == "win32":
                if error_code == 10048:  # WSAEADDRINUSE
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(configured_port, "udp")
                    error_msg = (
                        f"UDP tracker port {configured_port} is already in use.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
                elif error_code == 10013:  # WSAEACCES
                    from ccbt.utils.port_checker import get_permission_error_resolution

                    resolution = get_permission_error_resolution(
                        configured_port, "udp", "network.tracker_udp_port"
                    )
                    error_msg = (
                        f"Permission denied binding to 0.0.0.0:{configured_port}.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
            else:
                if error_code == 98:  # EADDRINUSE
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(configured_port, "udp")
                    error_msg = (
                        f"UDP tracker port {configured_port} is already in use.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
                elif error_code == 13:  # EACCES
                    from ccbt.utils.port_checker import get_permission_error_resolution

                    resolution = get_permission_error_resolution(
                        configured_port, "udp", "network.tracker_udp_port"
                    )
                    error_msg = (
                        f"Permission denied binding to 0.0.0.0:{configured_port}.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
            # Re-raise other OSErrors as-is
            self.logger.error("Failed to create UDP socket: %s", e)
            raise

        # Create datagram endpoint with the configured socket
        try:
            self.transport, self.socket = await loop.create_datagram_endpoint(
                lambda: UDPTrackerProtocol(self),
                sock=sock,
            )
        except Exception as e:
            sock.close()
            self.logger.error("Failed to create datagram endpoint: %s", e)
            raise

        # Start cleanup task
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Verify socket is properly bound and listening
        if self.transport is None:
            raise RuntimeError("Transport not initialized after socket creation")

        # Log socket binding information
        try:
            sockname = self.transport.get_extra_info("sockname")
            if sockname:
                self.logger.info(
                    "UDP socket bound to %s:%d",
                    sockname[0] if sockname else "unknown",
                    sockname[1] if sockname else 0,
                )
        except Exception as e:
            self.logger.debug("Could not get socket name: %s", e)

        # Verify protocol is registered
        if not isinstance(self.socket, UDPTrackerProtocol):
            self.logger.warning("Socket protocol may not be properly registered")

        # CRITICAL FIX: Verify socket is actually ready before marking as ready
        # Perform a health check to ensure socket can send/receive
        try:
            # Verify transport is not closing
            if self.transport.is_closing():
                raise RuntimeError("Transport is closing immediately after creation")

            # Verify socket name is available (indicates socket is bound)
            sockname = self.transport.get_extra_info("sockname")
            if sockname is None:
                raise RuntimeError("Socket name not available after creation")

            # Mark socket as ready only after verification
            self._socket_ready = True

            # Reset error counters on successful initialization
            self._socket_error_count = 0
            self._socket_recreation_count = 0
            self._socket_recreation_backoff = 1.0
            self._last_socket_health_check = time.time()

            self.logger.info(
                "UDP tracker client started and ready (socket bound to %s:%d)",
                sockname[0] if sockname else "unknown",
                sockname[1] if sockname else 0,
            )
        except Exception as e:
            self._socket_ready = False
            self.logger.error(
                "Socket initialization verification failed: %s. Socket may not be ready.",
                e,
            )
            raise

    async def stop(self) -> None:
        """Stop the UDP tracker client."""
        # Mark socket as not ready first
        self._socket_ready = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # CRITICAL FIX: Ensure proper cleanup of transport on Windows
        # Close transport and wait for it to fully close before proceeding
        if self.transport:
            try:
                self.transport.close()
                # CRITICAL FIX: On Windows Proactor, wait for transport to fully close
                # This prevents WinError 10022 when socket is reused
                import sys

                loop = asyncio.get_event_loop()
                is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                if sys.platform == "win32" and is_proactor:
                    # Wait longer for Proactor to release socket resources
                    await asyncio.sleep(0.3)
                elif sys.platform == "win32":
                    await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.debug("Error closing transport: %s", e)
            finally:
                self.transport = None
                self.socket = None

        # Cancel pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()

        self.logger.info("UDP tracker client stopped")

    async def announce(
        self,
        torrent_data: dict[str, Any],
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: TrackerEvent = TrackerEvent.STARTED,
    ) -> list[dict[str, Any]]:
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
        if (
            not tracker_urls
        ):  # pragma: no cover - No trackers path, tested via trackers present
            self.logger.warning("No UDP trackers found")
            return []

        # Announce to all trackers concurrently
        tasks = []
        for url in tracker_urls:
            task = asyncio.create_task(
                self._announce_to_tracker(
                    url,
                    torrent_data,
                    port=None,  # Use config port (external port should be passed from AnnounceController via _announce_to_tracker_full)
                    uploaded=uploaded,
                    downloaded=downloaded,
                    left=left,
                    event=event,
                ),
            )
            tasks.append(task)

        # Wait for all announces to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all peers
        all_peers = []
        for result in results:
            if isinstance(result, list):
                all_peers.extend(result)
            elif isinstance(
                result, Exception
            ):  # pragma: no cover - Exception result path, tested via success paths
                self.logger.debug("Tracker announce failed: %s", result)

        # Deduplicate peers
        peer_set = set()
        unique_peers = []
        for peer in all_peers:
            peer_key = (peer["ip"], peer["port"])
            if peer_key not in peer_set:
                peer_set.add(peer_key)
                unique_peers.append(peer)

        self.logger.info(
            "Got %s unique peers from %s trackers",
            len(unique_peers),
            len(tracker_urls),
        )
        return unique_peers

    def _extract_tracker_urls(self, torrent_data: dict[str, Any]) -> list[str]:
        """Extract UDP tracker URLs from torrent data."""
        urls = []

        # Single announce URL
        if "announce" in torrent_data:
            url = torrent_data["announce"]
            if url.startswith("udp://"):
                urls.append(url)

        # Announce list
        if "announce_list" in torrent_data:
            urls.extend(
                url
                for tier in torrent_data["announce_list"]
                for url in tier
                if url.startswith("udp://")
            )

        return urls

    async def _announce_to_tracker(
        self,
        url: str,
        torrent_data: dict[str, Any],
        port: int | None = None,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        event: TrackerEvent = TrackerEvent.STARTED,
    ) -> list[dict[str, Any]]:
        """Announce to a single UDP tracker with enhanced error handling and logging.

        Args:
            url: Tracker URL
            torrent_data: Torrent metadata dictionary
            port: Client's external port from NAT manager (None to use config port)
            uploaded: Bytes uploaded
            downloaded: Bytes downloaded
            left: Bytes remaining
            event: Tracker event type

        """
        try:
            # Parse URL with enhanced error handling
            # CRITICAL FIX: Rename unpacked variable to avoid shadowing the port parameter
            try:
                host, tracker_port = self._parse_udp_url(url)
            except ValueError as e:
                self.logger.warning("Failed to parse UDP tracker URL %s: %s", url, e)
                return []

            # Get or create session
            session_key = f"{host}:{tracker_port}"
            if session_key not in self.sessions:
                self.sessions[session_key] = TrackerSession(url, host, tracker_port)

            session = self.sessions[session_key]

            # CRITICAL FIX: Check connection health and refresh if needed
            # Connection IDs expire after 60 seconds, so refresh before announce
            # Improved: Refresh earlier (50s) to avoid race conditions and add validation
            current_time = time.time()
            connection_expired = (
                not session.is_connected
                or session.connection_id is None
                or session.connection_time == 0.0
                or (
                    current_time - session.connection_time > 50.0
                )  # Refresh 10s before 60s expiry for better reliability
            )

            if connection_expired:
                self.logger.info(
                    "Refreshing tracker connection for %s:%d (expired=%s, age=%.1fs)",
                    session.host,
                    session.port,
                    connection_expired,
                    current_time - session.connection_time
                    if session.connection_time > 0
                    else 0,
                )
                try:
                    await self._connect_to_tracker(session)
                    if session.is_connected:
                        self.logger.info(
                            "Successfully connected to tracker %s:%d",
                            session.host,
                            session.port,
                        )
                except Exception as e:
                    self.logger.warning(
                        "Failed to refresh connection to tracker %s:%d: %s",
                        session.host,
                        session.port,
                        e,
                    )

            if not session.is_connected:  # pragma: no cover - Connection failed path, tested via successful connection
                self.logger.warning(
                    "Cannot announce to tracker %s:%d - not connected (retry_count: %d, backoff: %.1fs)",
                    session.host,
                    session.port,
                    session.retry_count,
                    session.backoff_delay,
                )
                return []

            # Send announce
            # CRITICAL FIX: Pass port parameter (client's external port from NAT manager) to use external port
            # This ensures trackers receive the correct port for routing incoming connections
            return await self._send_announce(
                session,
                torrent_data,
                port=port,  # Client's external port from NAT manager (not tracker_port)
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
                event=event,
            )

        except (
            Exception
        ) as e:  # pragma: no cover - Announce exception, defensive error handling
            self.logger.warning(
                "Failed to announce to tracker %s: %s (error type: %s)",
                url,
                e,
                type(e).__name__,
            )
            return []

    async def _announce_to_tracker_full(
        self,
        url: str,
        torrent_data: dict[str, Any],
        port: int | None = None,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        event: TrackerEvent = TrackerEvent.STARTED,
    ) -> tuple[list[dict[str, Any]], int | None, int | None, int | None] | None:
        """Announce to a single UDP tracker and return full response info.

        Returns:
            Tuple of (peers, interval, seeders, leechers) or None if announce failed

        """
        try:
            # Parse URL
            # CRITICAL FIX: Rename unpacked variable to avoid shadowing the port parameter
            # The port parameter is the client's external port from NAT manager
            host, tracker_port = self._parse_udp_url(url)

            # Get or create session
            session_key = f"{host}:{tracker_port}"
            if session_key not in self.sessions:
                self.sessions[session_key] = TrackerSession(url, host, tracker_port)

            session = self.sessions[session_key]

            # Check connection health and refresh if needed
            current_time = time.time()
            connection_expired = (
                not session.is_connected
                or session.connection_id is None
                or session.connection_time == 0.0
                or (current_time - session.connection_time > 55.0)
            )

            if connection_expired:
                self.logger.debug(
                    "Refreshing tracker connection for %s:%d (expired=%s, age=%.1fs)",
                    session.host,
                    session.port,
                    connection_expired,
                    current_time - session.connection_time
                    if session.connection_time > 0
                    else 0,
                )
                await self._connect_to_tracker(session)

            if not session.is_connected:
                self.logger.debug(
                    "Failed to connect to tracker %s:%d", session.host, session.port
                )
                return None

            # Send announce and get full response
            # CRITICAL FIX: Pass port parameter (client's external port from NAT manager) to use external port
            # This ensures trackers receive the correct port for routing incoming connections
            return await self._send_announce_full(
                session,
                torrent_data,
                port=port,  # Client's external port from NAT manager (not tracker_port)
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
                event=event,
            )

        except (
            Exception
        ) as e:  # pragma: no cover - Announce exception, defensive error handling
            self.logger.debug("Failed to announce to %s: %s", url, e)
            return None

    def _parse_udp_url(self, url: str) -> tuple[str, int]:
        """Parse UDP tracker URL.

        Handles URLs with and without paths, IPv4, IPv6, and various edge cases:
        - udp://host:port/announce -> (host, port)
        - udp://host:port -> (host, port)
        - udp://[2001:db8::1]:6881 -> ([2001:db8::1], 6881)
        - udp://[2001:db8::1]:6881/announce -> ([2001:db8::1], 6881)

        Args:
            url: UDP tracker URL (may include path like /announce)

        Returns:
            Tuple of (host, port)

        Raises:
            ValueError: If URL is malformed or port is invalid

        """
        original_url = url

        # Remove udp:// prefix
        if url.startswith("udp://"):
            url = url[6:]
        elif url.startswith("udp:/"):
            # Handle malformed URLs like "udp:/host:port"
            url = url[5:]

        # Remove any path components (e.g., /announce, /announce?param=value)
        # UDP trackers don't use paths, but some magnet links include them
        if "/" in url:
            url = url.split("/", 1)[0]

        # Remove query parameters if any (shouldn't happen after path removal, but be safe)
        if "?" in url:
            url = url.split("?", 1)[0]

        # CRITICAL FIX: Handle IPv6 addresses (enclosed in brackets)
        # IPv6 format: [2001:db8::1]:port
        if url.startswith("[") and "]" in url:
            # Extract IPv6 address and port
            bracket_end = url.index("]")
            host = url[1:bracket_end]  # Extract IPv6 address without brackets
            remaining = url[bracket_end + 1 :]

            # Extract port after ]
            if remaining.startswith(":"):
                port_str = remaining[1:]
                try:
                    port = int(port_str)
                except ValueError as e:
                    msg = f"Invalid port in UDP URL (IPv6): {original_url}"
                    raise ValueError(msg) from e
            else:
                # No port specified, use default
                port = 80
        # IPv4 or hostname - split on last colon (handles hostnames with colons in them)
        elif ":" in url:
            # Use rsplit to handle hostnames that might contain colons
            # But be careful - IPv6 without brackets would break this
            # However, that's invalid anyway, so we'll catch it in validation
            parts = url.rsplit(":", 1)
            if len(parts) == 2:
                host, port_str = parts
                try:
                    port = int(port_str)
                except ValueError as e:
                    msg = f"Invalid port in UDP URL: {original_url}"
                    raise ValueError(msg) from e
            else:
                # Multiple colons but not IPv6 format - invalid
                msg = f"Malformed UDP URL (multiple colons, not IPv6): {original_url}"
                raise ValueError(msg)
        else:  # pragma: no cover - Default port path, tested via port specified
            host = url
            port = 80  # Default port

        # Validate host and port
        if not host:
            msg = f"Empty host in UDP URL: {original_url}"
            raise ValueError(msg)

        # Remove brackets from IPv6 if still present (shouldn't happen, but be safe)
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]

        # Basic hostname validation
        # Allow IPv4, IPv6, hostnames, and localhost
        if not host or host.isspace():
            msg = f"Empty or whitespace-only host in UDP URL: {original_url}"
            raise ValueError(msg)

        if not (1 <= port <= 65535):
            msg = f"Invalid port range in UDP URL: {original_url} (port: {port})"
            raise ValueError(msg)

        return host, port

    async def _connect_to_tracker(self, session: TrackerSession) -> None:
        """Connect to a UDP tracker with health check and retry logic.

        CRITICAL: Socket must be initialized during daemon startup. Socket recreation
        is not supported as it breaks session logic.
        """
        # Validate socket is ready before use
        self._validate_socket_ready()

        max_retries = 5
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # CRITICAL FIX: Health check - reset connection state if stale
                if session.connection_time > 0 and (
                    time.time() - session.connection_time > 60.0
                ):
                    self.logger.debug(
                        "Resetting stale connection state for %s:%d (age=%.1fs)",
                        session.host,
                        session.port,
                        time.time() - session.connection_time,
                    )
                    session.is_connected = False
                    session.connection_id = None
                    session.connection_time = 0.0

                # Send connect request
                transaction_id = self._get_transaction_id()
                connect_data = struct.pack(
                    "!QII",
                    0x41727101980,
                    TrackerAction.CONNECT.value,
                    transaction_id,
                )

                # Send request
                # Validate socket is ready (already validated at start, but double-check)
                self._validate_socket_ready()

                # Use lock to serialize socket operations
                async with self._socket_lock:
                    # Log send attempt
                    self.logger.debug(
                        "Sending tracker connect request to %s:%d (transaction_id=%d)",
                        session.host,
                        session.port,
                        transaction_id,
                    )

                    # Send connect request (transport is guaranteed to be non-None after validation)
                    if self.transport is None:
                        raise RuntimeError("Transport is None after validation")

                    # CRITICAL FIX: Check socket health before send operation
                    if not self._check_socket_health():
                        # Socket appears unhealthy - increment error count
                        self._socket_error_count += 1
                        self._socket_last_error_time = time.time()

                        # If socket is truly invalid, raise error
                        if self.transport is None or self.transport.is_closing():
                            raise RuntimeError(
                                "Socket is invalid (transport=None or closing). "
                                "Socket should have been initialized during daemon startup."
                            )

                        # If socket just appears not ready, log and allow retry
                        self.logger.debug(
                            "Socket health check failed before send (error_count: %d, will retry)",
                            self._socket_error_count,
                        )
                        # Don't raise - let retry logic handle it
                        raise ConnectionError("Socket health check failed")

                    # CRITICAL FIX: On Windows ProactorEventLoop, ensure socket is fully ready before sendto
                    # WinError 10022 can occur if socket state is not properly synchronized
                    import sys
                    loop = asyncio.get_event_loop()
                    is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                    if sys.platform == "win32" and is_proactor:
                        # Small delay to ensure socket state is synchronized on Windows Proactor
                        await asyncio.sleep(0.01)
                    
                    # Wrap sendto in try/except to catch WinError 10022 and other socket errors
                    # These will be retried by the outer exception handler
                    try:
                        self.transport.sendto(
                            connect_data, (session.host, session.port)
                        )
                        # Reset error count on successful send
                        if self._socket_error_count > 0:
                            self.logger.debug(
                                "Socket send succeeded, resetting error count (was: %d)",
                                self._socket_error_count,
                            )
                            self._socket_error_count = 0
                    except OSError as send_error:
                        # CRITICAL FIX: Improved WinError 10022 detection and handling
                        import sys

                        error_code = getattr(send_error, "winerror", None) or getattr(
                            send_error, "errno", None
                        )
                        is_winerror_10022 = (
                            error_code == 10022
                            or (hasattr(send_error, "errno") and send_error.errno == 22)
                            or (sys.platform == "win32" and "10022" in str(send_error))
                        )
                        if is_winerror_10022:
                            # WinError 10022 is transient on Windows - add retry with exponential backoff
                            self._socket_error_count += 1
                            self._socket_last_error_time = time.time()

                            # CRITICAL FIX: Add exponential backoff for WinError 10022
                            # Wait before retrying to allow socket to recover
                            backoff_delay = min(
                                0.1 * (2 ** min(self._socket_error_count - 1, 4)), 1.0
                            )  # Max 1 second

                            # Only log at WARNING level if error count is high
                            if self._socket_error_count <= 3:
                                self.logger.debug(
                                    "WinError 10022 during sendto to %s:%d (error_count: %d, retrying after %.2fs): %s",
                                    session.host,
                                    session.port,
                                    self._socket_error_count,
                                    backoff_delay,
                                    send_error,
                                )
                            else:
                                self.logger.warning(
                                    "WinError 10022 during sendto to %s:%d (error_count: %d, retrying after %.2fs): %s. "
                                    "This may indicate socket state issues on Windows.",
                                    session.host,
                                    session.port,
                                    self._socket_error_count,
                                    backoff_delay,
                                    send_error,
                                )

                            # CRITICAL FIX: Wait before retrying to allow socket to recover
                            await asyncio.sleep(backoff_delay)

                            # CRITICAL FIX: Validate socket state before retrying
                            if (
                                not self._socket_ready
                                or self.transport is None
                                or self.transport.is_closing()
                            ):
                                self.logger.error(
                                    "Socket is invalid after WinError 10022 (ready=%s, transport=%s, closing=%s). "
                                    "Cannot retry - socket must be reinitialized.",
                                    self._socket_ready,
                                    self.transport is not None,
                                    self.transport.is_closing()
                                    if self.transport
                                    else None,
                                )
                                raise RuntimeError(
                                    "Socket is invalid after WinError 10022"
                                ) from send_error

                            # Retry the send operation
                            try:
                                self.transport.sendto(
                                    connect_data, (session.host, session.port)
                                )
                                self.logger.debug(
                                    "Successfully retried sendto after WinError 10022 to %s:%d",
                                    session.host,
                                    session.port,
                                )
                                # Reset error count on successful retry
                                self._socket_error_count = 0
                            except OSError as retry_error:
                                # Retry also failed - re-raise to be caught by outer handler
                                self.logger.debug(
                                    "Retry sendto after WinError 10022 also failed to %s:%d: %s",
                                    session.host,
                                    session.port,
                                    retry_error,
                                )
                                raise
                        else:
                            # Other socket errors - increment error count
                            self._socket_error_count += 1
                            self._socket_last_error_time = time.time()
                            self.logger.debug(
                                "Socket error during sendto to %s:%d (error_count: %d): %s",
                                session.host,
                                session.port,
                                self._socket_error_count,
                                send_error,
                            )
                            # Re-raise to be caught by outer exception handler for retry
                            raise

                # Wait for response with timeout
                # CRITICAL FIX: Increased timeout from 10-14s to 20-30s for slow networks
                # Initial timeout: 20s, increase by 2s per retry attempt
                timeout = 20.0 + (
                    attempt * 2.0
                )  # 20s, 22s, 24s, 26s, 28s for attempts 0-4
                self.logger.debug(
                    "Waiting for tracker response from %s:%d (timeout=%.1fs, attempt %d/%d)",
                    session.host,
                    session.port,
                    timeout,
                    attempt + 1,
                    max_retries,
                )
                response = await self._wait_for_response(
                    transaction_id, timeout=timeout
                )

                if response and response.action == TrackerAction.CONNECT:
                    session.connection_id = response.connection_id
                    session.connection_time = time.time()
                    session.is_connected = True
                    session.retry_count = 0
                    session.backoff_delay = 1.0
                    # Log successful connection at INFO level for visibility
                    self.logger.info(
                        "Successfully connected to UDP tracker %s:%d (attempt %d/%d, connection_id: %d)",
                        session.host,
                        session.port,
                        attempt + 1,
                        max_retries,
                        session.connection_id,
                    )
                    return  # Success
                # pragma: no cover - Connection failure response path, tested via success response
                self._raise_connection_failed()

            except asyncio.TimeoutError:
                # Network timeout - retry with exponential backoff
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    self.logger.warning(
                        "Tracker connection timeout (attempt %d/%d), retrying in %.1fs: %s:%d (timeout: %.1fs)",
                        attempt + 1,
                        max_retries,
                        delay,
                        session.host,
                        session.port,
                        timeout,
                    )
                    await asyncio.sleep(delay)
                else:
                    session.is_connected = False
                    session.retry_count += 1
                    session.backoff_delay = min(session.backoff_delay * 2, 60.0)
                    self.logger.warning(
                        "Failed to connect to tracker %s:%d after %d attempts: timeout (backoff: %.1fs)",
                        session.host,
                        session.port,
                        max_retries,
                        session.backoff_delay,
                    )
                    raise
            except (
                Exception
            ) as e:  # pragma: no cover - Connection exception, defensive error handling
                # Categorize error type
                error_type = type(e).__name__
                is_network_error = (
                    "Timeout" in error_type
                    or "Connection" in error_type
                    or "Network" in error_type
                    or isinstance(e, (OSError, ConnectionError))
                )

                # CRITICAL FIX: Check if this is a transient socket error that shouldn't trigger recreation
                import sys

                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                is_winerror_10022 = (
                    error_code == 10022
                    or (hasattr(e, "errno") and e.errno == 22)
                    or (sys.platform == "win32" and "10022" in str(e))
                )

                # For WinError 10022, use exponential backoff but don't mark socket as invalid
                if is_winerror_10022:
                    if attempt < max_retries - 1:
                        # Exponential backoff for WinError 10022
                        delay = retry_delay * (2**attempt)
                        self.logger.debug(
                            "WinError 10022 (attempt %d/%d), retrying in %.1fs: %s:%d (transient error, socket still valid)",
                            attempt + 1,
                            max_retries,
                            delay,
                            session.host,
                            session.port,
                        )
                        await asyncio.sleep(delay)
                        continue  # Retry without marking socket as invalid
                    # Max retries reached for WinError 10022
                    self.logger.warning(
                        "WinError 10022 persisted after %d attempts for %s:%d (socket may need recovery)",
                        max_retries,
                        session.host,
                        session.port,
                    )
                    # Don't raise - let the session handle it
                    session.is_connected = False
                    session.retry_count += 1
                    session.backoff_delay = min(session.backoff_delay * 2, 60.0)
                    return  # Return without raising to allow other operations

                if attempt < max_retries - 1 and is_network_error:
                    # Network errors: retry with exponential backoff
                    delay = retry_delay * (2**attempt)
                    self.logger.debug(
                        "Tracker connection network error (attempt %d/%d), retrying in %.1fs: %s:%d - %s",
                        attempt + 1,
                        max_retries,
                        delay,
                        session.host,
                        session.port,
                        e,
                    )
                    await asyncio.sleep(delay)
                else:
                    # Protocol errors or max retries: don't retry
                    session.is_connected = False
                    session.retry_count += 1
                    session.backoff_delay = min(session.backoff_delay * 2, 60.0)
                    # CRITICAL FIX: Enhanced error logging for connection failures
                    self.logger.warning(
                        "Failed to connect to tracker %s:%d after %d attempts: %s (type: %s, network_error: %s, backoff: %.1fs)",
                        session.host,
                        session.port,
                        max_retries,
                        e,
                        error_type,
                        is_network_error,
                        session.backoff_delay,
                    )
                    raise

    async def _send_announce(
        self,
        session: TrackerSession,
        torrent_data: dict[str, Any],
        port: int | None = None,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        event: TrackerEvent = TrackerEvent.STARTED,
    ) -> list[dict[str, Any]]:
        """Send announce request to tracker."""
        try:
            # Check if we need to reconnect
            # CRITICAL FIX: Check connection_id is None, connection_time is 0, or connection expired (>60s)
            current_time = time.time()
            connection_expired = (
                session.connection_id is None
                or session.connection_time == 0.0
                or (current_time - session.connection_time > 60.0)
            )

            if connection_expired or not session.is_connected:
                self.logger.debug(
                    "Reconnecting to tracker %s:%d (connection_id=%s, connection_time=%.1f, expired=%s, is_connected=%s)",
                    session.host,
                    session.port,
                    session.connection_id is not None,
                    session.connection_time,
                    connection_expired,
                    session.is_connected,
                )
                await self._connect_to_tracker(session)

            if (
                not session.is_connected or session.connection_id is None
            ):  # pragma: no cover - Reconnection failed path, tested via successful reconnection
                self.logger.warning(
                    "Cannot announce to tracker %s:%d: not connected or connection_id is None",
                    session.host,
                    session.port,
                )
                return []

            # Build announce request
            transaction_id = self._get_transaction_id()
            info_hash = torrent_data["info_hash"]

            # CRITICAL FIX: Use external port from NAT manager if provided, otherwise use config port
            # The port parameter should be the external port from NAT manager (passed from AnnounceController)
            # If None, fallback to internal port but log warning
            if port is not None:
                client_listen_port = int(port)
                self.logger.debug(
                    "Using external port %d for UDP tracker announce to %s:%d",
                    client_listen_port,
                    session.host,
                    session.port,
                )
            else:
                client_listen_port = int(self.config.network.listen_port)
                self.logger.warning(
                    "Port parameter is None for UDP tracker announce to %s:%d, using internal port %d. "
                    "This may prevent peers from connecting if behind NAT. "
                    "Ensure AnnounceController passes external port from NAT manager. "
                    "TROUBLESHOOTING: If peers cannot connect, check NAT port mapping is active for TCP port %d. "
                    "Also verify Windows Firewall allows incoming connections on this port.",
                    session.host,
                    session.port,
                    client_listen_port,
                    client_listen_port,
                )
            announce_data = struct.pack(
                "!QII20s20sQQQIIIiH",
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
                client_listen_port,  # Port (external port from NAT manager if available)
            )

            # Send request
            # Validate socket is ready
            self._validate_socket_ready()

            # Use lock to serialize socket operations
            async with self._socket_lock:
                # Send announce request (transport is guaranteed to be non-None after validation)
                if self.transport is None:
                    raise RuntimeError("Transport is None after validation")

                # CRITICAL FIX: On Windows ProactorEventLoop, ensure socket is fully ready before sendto
                import sys
                loop = asyncio.get_event_loop()
                is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                if sys.platform == "win32" and is_proactor:
                    # Small delay to ensure socket state is synchronized on Windows Proactor
                    await asyncio.sleep(0.01)

                # Wrap sendto in try/except to catch WinError 10022 and other socket errors
                try:
                    self.transport.sendto(
                        announce_data, (session.host, session.port)
                    )  # pragma: no cover - Network operation, tested via mocking
                except OSError as send_error:
                    # CRITICAL FIX: Improved WinError 10022 detection and handling (same as connect)
                    import sys

                    error_code = getattr(send_error, "winerror", None) or getattr(
                        send_error, "errno", None
                    )
                    is_winerror_10022 = (
                        error_code == 10022
                        or (hasattr(send_error, "errno") and send_error.errno == 22)
                        or (sys.platform == "win32" and "10022" in str(send_error))
                    )
                    if is_winerror_10022:
                        # WinError 10022 is transient on Windows - add retry with exponential backoff
                        self._socket_error_count += 1
                        self._socket_last_error_time = time.time()

                        # CRITICAL FIX: Add exponential backoff for WinError 10022
                        backoff_delay = min(
                            0.1 * (2 ** min(self._socket_error_count - 1, 4)), 1.0
                        )  # Max 1 second

                        if self._socket_error_count <= 3:
                            self.logger.debug(
                                "WinError 10022 during announce sendto to %s:%d (error_count: %d, retrying after %.2fs): %s",
                                session.host,
                                session.port,
                                self._socket_error_count,
                                backoff_delay,
                                send_error,
                            )
                        else:
                            self.logger.warning(
                                "WinError 10022 during announce sendto to %s:%d (error_count: %d, retrying after %.2fs): %s",
                                session.host,
                                session.port,
                                self._socket_error_count,
                                backoff_delay,
                                send_error,
                            )

                        # Wait before retrying
                        await asyncio.sleep(backoff_delay)

                        # Validate socket state before retrying
                        if (
                            not self._socket_ready
                            or self.transport is None
                            or self.transport.is_closing()
                        ):
                            self.logger.error(
                                "Socket is invalid after WinError 10022 during announce (ready=%s, transport=%s, closing=%s)",
                                self._socket_ready,
                                self.transport is not None,
                                self.transport.is_closing() if self.transport else None,
                            )
                            raise RuntimeError(
                                "Socket is invalid after WinError 10022"
                            ) from send_error

                        # Retry the send operation
                        try:
                            self.transport.sendto(
                                announce_data, (session.host, session.port)
                            )
                            self.logger.debug(
                                "Successfully retried announce sendto after WinError 10022 to %s:%d",
                                session.host,
                                session.port,
                            )
                            self._socket_error_count = 0
                        except OSError as retry_error:
                            self.logger.debug(
                                "Retry announce sendto after WinError 10022 also failed to %s:%d: %s",
                                session.host,
                                session.port,
                                retry_error,
                            )
                            raise
                    else:
                        # Other socket errors
                        self._socket_error_count += 1
                        self._socket_last_error_time = time.time()
                        self.logger.debug(
                            "Socket error during announce sendto to %s:%d (error_count: %d): %s",
                            session.host,
                            session.port,
                            self._socket_error_count,
                            send_error,
                        )
                        raise

            # Wait for response with timeout
            # CRITICAL FIX: Increased timeout from 15s to 30s for announce responses (trackers may be slow)
            announce_timeout = 30.0  # 30 seconds for announce (increased from 15s for better reliability)
            try:
                response = await self._wait_for_response(
                    transaction_id, timeout=announce_timeout
                )  # pragma: no cover - Async network wait, tested separately
            except asyncio.TimeoutError:
                self.logger.warning(
                    "Announce timeout for tracker %s:%d (exceeded %.1fs)",
                    session.host,
                    session.port,
                    announce_timeout,
                )
                raise

            if (
                response and response.action == TrackerAction.ANNOUNCE
            ):  # pragma: no cover - Successful response path requires real network or complex async mocking
                # CRITICAL FIX: Log successful announce with peer count
                peer_count = (
                    len(response.peers)
                    if (hasattr(response, "peers") and response.peers)
                    else 0
                )
                self.logger.info(
                    "Successfully announced to tracker %s:%d (peers: %d, interval: %ds)",
                    session.host,
                    session.port,
                    peer_count,
                    response.interval if hasattr(response, "interval") else 0,
                )
                session.last_announce = (
                    time.time()
                )  # pragma: no cover - Part of successful path
                session.interval = (
                    response.interval
                )  # pragma: no cover - Part of successful path
                return (
                    response.peers or []
                )  # pragma: no cover - Part of successful path
            self.logger.warning(
                "Announce failed for tracker %s:%d (invalid response or action mismatch)",
                session.host,
                session.port,
            )  # pragma: no cover - Logging statement, tested via other paths

        except (
            Exception
        ) as e:  # pragma: no cover - Announce exception, defensive error handling
            # CRITICAL FIX: Enhanced error logging for announce failures
            self.logger.warning(
                "Announce error for tracker %s:%d: %s (type: %s)",
                session.host,
                session.port,
                e,
                type(e).__name__,
            )
            return []
        else:  # pragma: no cover - Else branch for non-exception failure (timeout/invalid response), tested separately
            return []

    async def _send_announce_full(
        self,
        session: TrackerSession,
        torrent_data: dict[str, Any],
        port: int | None = None,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        event: TrackerEvent = TrackerEvent.STARTED,
    ) -> tuple[list[dict[str, Any]], int | None, int | None, int | None] | None:
        """Send announce request to tracker and return full response info.

        Returns:
            Tuple of (peers, interval, seeders, leechers) or None if announce failed

        """
        try:
            # Check if we need to reconnect
            current_time = time.time()
            connection_expired = (
                session.connection_id is None
                or session.connection_time == 0.0
                or (current_time - session.connection_time > 60.0)
            )

            if connection_expired or not session.is_connected:
                self.logger.debug(
                    "Reconnecting to tracker %s:%d (connection_id=%s, connection_time=%.1f, expired=%s, is_connected=%s)",
                    session.host,
                    session.port,
                    session.connection_id is not None,
                    session.connection_time,
                    connection_expired,
                    session.is_connected,
                )
                await self._connect_to_tracker(session)

            if (
                not session.is_connected or session.connection_id is None
            ):  # pragma: no cover - Reconnection failed path, tested via successful reconnection
                self.logger.warning(
                    "Cannot announce to tracker %s:%d: not connected or connection_id is None",
                    session.host,
                    session.port,
                )
                return None

            # Build announce request
            transaction_id = self._get_transaction_id()
            info_hash = torrent_data["info_hash"]

            # CRITICAL FIX: Use external port from NAT manager if provided, otherwise use config port
            # The port parameter should be the external port from NAT manager (passed from AnnounceController)
            # If None, fallback to internal port but log warning
            if port is not None:
                client_listen_port = int(port)
                self.logger.debug(
                    "Using external port %d for UDP tracker announce to %s:%d",
                    client_listen_port,
                    session.host,
                    session.port,
                )
            else:
                client_listen_port = int(self.config.network.listen_port)
                self.logger.warning(
                    "Port parameter is None for UDP tracker announce to %s:%d, using internal port %d. "
                    "This may prevent peers from connecting if behind NAT. "
                    "Ensure AnnounceController passes external port from NAT manager. "
                    "TROUBLESHOOTING: If peers cannot connect, check NAT port mapping is active for TCP port %d. "
                    "Also verify Windows Firewall allows incoming connections on this port.",
                    session.host,
                    session.port,
                    client_listen_port,
                    client_listen_port,
                )
            announce_data = struct.pack(
                "!QII20s20sQQQIIIiH",
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
                client_listen_port,  # Port (external port from NAT manager if available)
            )

            # Send request
            # Validate socket is ready
            self._validate_socket_ready()

            # Use lock to serialize socket operations
            async with self._socket_lock:
                # Send announce request (transport is guaranteed to be non-None after validation)
                if self.transport is None:
                    raise RuntimeError("Transport is None after validation")

                # CRITICAL FIX: On Windows ProactorEventLoop, ensure socket is fully ready before sendto
                import sys
                loop = asyncio.get_event_loop()
                is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                if sys.platform == "win32" and is_proactor:
                    # Small delay to ensure socket state is synchronized on Windows Proactor
                    await asyncio.sleep(0.01)

                # Wrap sendto in try/except to catch WinError 10022 and other socket errors
                try:
                    self.transport.sendto(
                        announce_data, (session.host, session.port)
                    )  # pragma: no cover - Network operation, tested via mocking
                except OSError as send_error:
                    # CRITICAL FIX: Improved WinError 10022 detection and handling (same as connect)
                    import sys

                    error_code = getattr(send_error, "winerror", None) or getattr(
                        send_error, "errno", None
                    )
                    is_winerror_10022 = (
                        error_code == 10022
                        or (hasattr(send_error, "errno") and send_error.errno == 22)
                        or (sys.platform == "win32" and "10022" in str(send_error))
                    )
                    if is_winerror_10022:
                        # WinError 10022 is transient on Windows - add retry with exponential backoff
                        self._socket_error_count += 1
                        self._socket_last_error_time = time.time()

                        # CRITICAL FIX: Add exponential backoff for WinError 10022
                        backoff_delay = min(
                            0.1 * (2 ** min(self._socket_error_count - 1, 4)), 1.0
                        )  # Max 1 second

                        if self._socket_error_count <= 3:
                            self.logger.debug(
                                "WinError 10022 during scrape sendto to %s:%d (error_count: %d, retrying after %.2fs): %s",
                                session.host,
                                session.port,
                                self._socket_error_count,
                                backoff_delay,
                                send_error,
                            )
                        else:
                            self.logger.warning(
                                "WinError 10022 during scrape sendto to %s:%d (error_count: %d, retrying after %.2fs): %s",
                                session.host,
                                session.port,
                                self._socket_error_count,
                                backoff_delay,
                                send_error,
                            )

                        # Wait before retrying
                        await asyncio.sleep(backoff_delay)

                        # Validate socket state before retrying
                        if (
                            not self._socket_ready
                            or self.transport is None
                            or self.transport.is_closing()
                        ):
                            self.logger.error(
                                "Socket is invalid after WinError 10022 during scrape (ready=%s, transport=%s, closing=%s)",
                                self._socket_ready,
                                self.transport is not None,
                                self.transport.is_closing() if self.transport else None,
                            )
                            raise RuntimeError(
                                "Socket is invalid after WinError 10022"
                            ) from send_error

                        # Retry the send operation
                        try:
                            self.transport.sendto(
                                announce_data, (session.host, session.port)
                            )
                            self.logger.debug(
                                "Successfully retried scrape sendto after WinError 10022 to %s:%d",
                                session.host,
                                session.port,
                            )
                            self._socket_error_count = 0
                        except OSError as retry_error:
                            self.logger.debug(
                                "Retry scrape sendto after WinError 10022 also failed to %s:%d: %s",
                                session.host,
                                session.port,
                                retry_error,
                            )
                            raise
                    else:
                        # Other socket errors
                        self._socket_error_count += 1
                        self._socket_last_error_time = time.time()
                        self.logger.debug(
                            "Socket error during scrape sendto to %s:%d (error_count: %d): %s",
                            session.host,
                            session.port,
                            self._socket_error_count,
                            send_error,
                        )
                        raise

            # Wait for response
            # CRITICAL FIX: Increased timeout from 10s to 30s to match _send_announce
            # Trackers may be slow, especially on first announce
            announce_timeout = 30.0  # 30 seconds for announce (matching _send_announce)
            response = await self._wait_for_response(
                transaction_id, timeout=announce_timeout
            )  # pragma: no cover - Async network wait, tested separately

            if (
                response and response.action == TrackerAction.ANNOUNCE
            ):  # pragma: no cover - Successful response path requires real network or complex async mocking
                session.last_announce = (
                    time.time()
                )  # pragma: no cover - Part of successful path
                session.interval = (
                    response.interval
                )  # pragma: no cover - Part of successful path
                # Return full response tuple: (peers, interval, seeders, leechers)
                return (
                    response.peers or [],
                    response.interval,
                    response.seeders,
                    response.leechers,
                )  # pragma: no cover - Part of successful path
            self.logger.debug(
                "Announce failed for %s:%s", session.host, session.port
            )  # pragma: no cover - Logging statement, tested via other paths

        except (
            Exception
        ) as e:  # pragma: no cover - Announce exception, defensive error handling
            self.logger.debug(
                "Announce error for %s:%s: %s",
                session.host,
                session.port,
                e,
            )
            return None
        else:  # pragma: no cover - Else branch for non-exception failure (timeout/invalid response), tested separately
            return None

    def _get_transaction_id(self) -> int:
        """Get next transaction ID."""
        self.transaction_counter = (self.transaction_counter + 1) % 65536
        return self.transaction_counter

    async def _wait_for_response(
        self,
        transaction_id: int,
        timeout: float,
    ) -> TrackerResponse | None:
        """Wait for UDP tracker response."""
        future = asyncio.Future()
        self.pending_requests[transaction_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            # CRITICAL FIX: Enhanced logging for timeouts - this is a common failure mode
            self.logger.warning(
                "Timeout waiting for tracker response (transaction_id=%d, timeout=%.1fs). "
                "This may indicate: (1) Tracker is slow/unresponsive, (2) Network issues, "
                "or (3) Firewall blocking responses. "
                "Pending requests: %d",
                transaction_id,
                timeout,
                len(self.pending_requests),
            )
            return None
        finally:
            self.pending_requests.pop(transaction_id, None)

    def handle_response(self, data: bytes, _addr: tuple[str, int]) -> None:
        """Handle incoming UDP response.

        CRITICAL: Socket should always be ready. If not, this indicates an initialization issue.
        """
        # If socket not ready, log warning and drop response (socket should always be ready)
        if not self._socket_ready:
            self.logger.warning(
                "Received UDP response from %s:%d but socket not ready (length=%d bytes). "
                "Socket should have been initialized during daemon startup. Dropping response.",
                _addr[0] if _addr else "unknown",
                _addr[1] if _addr else 0,
                len(data),
            )
            return

        # Add comprehensive logging for debugging
        self.logger.debug(
            "Received UDP datagram from %s:%d, length=%d bytes",
            _addr[0] if _addr else "unknown",
            _addr[1] if _addr else 0,
            len(data),
        )

        try:
            if len(data) < 8:
                self.logger.debug(
                    "UDP response too short: %d bytes (minimum 8)", len(data)
                )
                return

            # Parse response header
            action = struct.unpack("!I", data[0:4])[0]
            transaction_id = struct.unpack("!I", data[4:8])[0]

            self.logger.debug(
                "Parsed UDP response: action=%d, transaction_id=%d from %s:%d",
                action,
                transaction_id,
                _addr[0] if _addr else "unknown",
                _addr[1] if _addr else 0,
            )

            # Check if we have a pending request for this transaction
            if transaction_id not in self.pending_requests:
                # Enhanced logging for unmatched responses
                # This can happen if: (1) Response arrived after timeout, (2) Transaction ID collision,
                # or (3) Response from different tracker/client
                self.logger.warning(
                    "Received UDP response with transaction_id=%d from %s:%d but no pending request found. "
                    "This may indicate: (1) Response arrived after timeout, (2) Transaction ID collision, "
                    "or (3) Response from different tracker/client. "
                    "Pending transaction IDs: %s (count: %d). Response action: %d",
                    transaction_id,
                    _addr[0] if _addr else "unknown",
                    _addr[1] if _addr else 0,
                    sorted(list(self.pending_requests.keys()))[
                        :10
                    ],  # Show first 10 for brevity
                    len(self.pending_requests),
                    action,
                )
                return

            future = self.pending_requests[transaction_id]
            if future.done():
                self.logger.debug(
                    "Future for transaction_id=%d already done", transaction_id
                )
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

                    # CRITICAL FIX: Add detailed logging of raw tracker response
                    # Always log at INFO level for visibility - this is critical for debugging
                    self.logger.info(
                        "UDP Tracker ANNOUNCE response from %s:%d: "
                        "interval=%d, leechers=%d, seeders=%d, response_length=%d bytes",
                        _addr[0] if _addr else "unknown",
                        _addr[1] if _addr else 0,
                        interval,
                        leechers,
                        seeders,
                        len(data),
                    )

                    # CRITICAL FIX: Log FULL raw response data at INFO level for debugging
                    # This helps identify if peers are in the response but not being parsed
                    if len(data) > 0:
                        # Log first 200 bytes at INFO level, full response at DEBUG
                        preview_len = min(200, len(data))
                        self.logger.info(
                            "Raw tracker response (first %d/%d bytes): %s",
                            preview_len,
                            len(data),
                            data[:preview_len].hex(),
                        )
                        if len(data) > preview_len:
                            self.logger.debug(
                                "Raw tracker response (remaining %d bytes): %s",
                                len(data) - preview_len,
                                data[preview_len:].hex(),
                            )

                    # Parse peers (compact format)
                    # CRITICAL FIX: Improved peer parsing with validation and logging
                    peers = []
                    invalid_peers = 0

                    # CRITICAL FIX: Log raw response for debugging at INFO level for visibility
                    self.logger.info(
                        "UDP Tracker response parsing: length=%d bytes, action=ANNOUNCE, seeders=%d, leechers=%d",
                        len(data),
                        seeders,
                        leechers,
                    )
                    self.logger.debug(
                        "Raw tracker response hex (first 100 bytes): %s",
                        data[:100].hex() if len(data) >= 100 else data.hex(),
                    )

                    if len(data) > 20:
                        peer_data = data[20:]
                        peer_count = len(peer_data) // 6

                        # CRITICAL FIX: Validate peer data length is multiple of 6
                        if len(peer_data) % 6 != 0:
                            self.logger.warning(
                                "Peer data length not multiple of 6: %d bytes (expected multiple of 6 for compact format). "
                                "Truncating to valid length.",
                                len(peer_data),
                            )
                            # Truncate to valid length
                            peer_data = peer_data[
                                : len(peer_data) - (len(peer_data) % 6)
                            ]
                            peer_count = len(peer_data) // 6

                        # CRITICAL FIX: Enhanced logging for peer parsing
                        self.logger.info(
                            "Parsing %d peer(s) from tracker %s:%d (peer_data length: %d bytes, "
                            "expected peers: %d, seeders reported: %d, leechers reported: %d)",
                            peer_count,
                            _addr[0] if _addr else "unknown",
                            _addr[1] if _addr else 0,
                            len(peer_data),
                            peer_count,
                            seeders,
                            leechers,
                        )

                        # CRITICAL FIX: Log peer data preview for debugging
                        if len(peer_data) > 0:
                            preview_peers = min(3, peer_count)  # First 3 peers
                            preview_bytes = preview_peers * 6
                            self.logger.debug(
                                "Peer data preview (first %d peer(s), %d bytes): %s",
                                preview_peers,
                                preview_bytes,
                                peer_data[:preview_bytes].hex(),
                            )
                    else:
                        self.logger.warning(
                            "Tracker response has no peer data (response length: %d bytes, "
                            "minimum expected: 20 bytes for header)",
                            len(data),
                        )

                        # CRITICAL FIX: If tracker reports seeders/leechers but no peer data, log error
                        if (seeders > 0 or leechers > 0) and len(data) <= 20:
                            self.logger.error(
                                "INCONSISTENCY: Tracker %s:%d reports seeders=%d, leechers=%d but no peer data! "
                                "Response hex: %s",
                                _addr[0] if _addr else "unknown",
                                _addr[1] if _addr else 0,
                                seeders,
                                leechers,
                                data.hex()[:200],
                            )

                    # Parse peers from peer_data (if available)
                    if len(data) > 20:
                        peer_data = data[20:]
                        for i in range(0, len(peer_data), 6):
                            if i + 6 <= len(peer_data):
                                try:
                                    peer_bytes = peer_data[i : i + 6]

                                    # CRITICAL FIX: Validate peer_bytes length before parsing
                                    if len(peer_bytes) != 6:
                                        invalid_peers += 1
                                        self.logger.debug(
                                            "Invalid peer bytes length at offset %d: %d bytes (expected 6)",
                                            i,
                                            len(peer_bytes),
                                        )
                                        continue

                                    # Parse IP address (4 bytes)
                                    ip_bytes = peer_bytes[:4]
                                    ip = ".".join(str(b) for b in ip_bytes)

                                    # Parse port (2 bytes, big-endian)
                                    port_bytes = peer_bytes[4:6]
                                    if len(port_bytes) != 2:
                                        invalid_peers += 1
                                        self.logger.debug(
                                            "Invalid port bytes length at offset %d: %d bytes (expected 2)",
                                            i,
                                            len(port_bytes),
                                        )
                                        continue
                                    port = int.from_bytes(port_bytes, "big")

                                    # CRITICAL FIX: Validate IP and port (relaxed validation)
                                    # Only filter obviously invalid IPs - don't filter private IPs as they might be valid
                                    # Many valid peers use private IPs (NAT, VPN, etc.)
                                    ip_parts = ip.split(".")
                                    is_valid_ip = False
                                    try:
                                        is_valid_ip = (
                                            len(ip_parts) == 4
                                            and all(
                                                p.isdigit() and 0 <= int(p) <= 255
                                                for p in ip_parts
                                            )
                                            and ip != "0.0.0.0"
                                            # CRITICAL: Don't filter 127.x.x.x, 169.254.x.x, or private IPs
                                            # These might be valid in NAT/VPN scenarios
                                        )
                                    except (ValueError, AttributeError) as e:
                                        self.logger.debug(
                                            "Error validating IP %s: %s",
                                            ip,
                                            e,
                                        )

                                    # Check if port is valid
                                    is_valid_port = 1 <= port <= 65535

                                    if is_valid_ip and is_valid_port:
                                        peer_dict = {
                                            "ip": ip,
                                            "port": port,
                                            "peer_source": "tracker",  # Mark peers from tracker responses (BEP 27)
                                        }
                                        peers.append(peer_dict)
                                        # CRITICAL FIX: Log each parsed peer at INFO level for visibility
                                        self.logger.info(
                                            "Parsed peer from tracker: %s:%d (offset %d, peer %d/%d)",
                                            ip,
                                            port,
                                            i,
                                            len(peers),
                                            peer_count,
                                        )
                                    else:
                                        invalid_peers += 1
                                        self.logger.warning(
                                            "Skipping invalid peer from tracker: ip=%s, port=%d (valid_ip=%s, valid_port=%s, offset=%d)",
                                            ip,
                                            port,
                                            is_valid_ip,
                                            is_valid_port,
                                            i,
                                        )
                                except (
                                    ValueError,
                                    IndexError,
                                    struct.error,
                                    TypeError,
                                ) as e:
                                    invalid_peers += 1
                                    self.logger.warning(
                                        "Error parsing peer at offset %d: %s (peer_bytes=%s)",
                                        i,
                                        e,
                                        peer_bytes.hex()
                                        if "peer_bytes" in locals()
                                        else "N/A",
                                    )

                        if invalid_peers > 0:
                            self.logger.debug(
                                "Skipped %d invalid peer(s) from tracker response",
                                invalid_peers,
                            )

                        # CRITICAL FIX: Log at INFO level for visibility when peers are found
                        if len(peers) > 0:
                            self.logger.info(
                                "Parsed %d valid peer(s) from tracker %s:%d (seeders=%d, leechers=%d)",
                                len(peers),
                                _addr[0] if _addr else "unknown",
                                _addr[1] if _addr else 0,
                                seeders,
                                leechers,
                            )
                        else:
                            # CRITICAL FIX: Enhanced logging for 0 peers case
                            peer_data_len = (len(data) - 20) if len(data) > 20 else 0
                            self.logger.warning(
                                "Tracker %s:%d responded with 0 valid peers after parsing "
                                "(seeders=%d, leechers=%d, peer_data_length=%d bytes, "
                                "expected_peers=%d, invalid_peers_skipped=%d, response_length=%d bytes)",
                                _addr[0] if _addr else "unknown",
                                _addr[1] if _addr else 0,
                                seeders,
                                leechers,
                                peer_data_len,
                                peer_data_len // 6 if peer_data_len > 0 else 0,
                                invalid_peers,
                                len(data),
                            )

                            # If tracker reports seeders/leechers but no peer data, this is suspicious
                            if (seeders > 0 or leechers > 0) and peer_data_len == 0:
                                self.logger.error(
                                    "INCONSISTENCY: Tracker %s:%d reports seeders=%d, leechers=%d "
                                    "but provided NO peer data (response_length=%d bytes). "
                                    "This may indicate a tracker response format issue.",
                                    _addr[0] if _addr else "unknown",
                                    _addr[1] if _addr else 0,
                                    seeders,
                                    leechers,
                                    len(data),
                                )

                    response = TrackerResponse(
                        action=TrackerAction.ANNOUNCE,
                        transaction_id=transaction_id,
                        interval=interval,
                        leechers=leechers,
                        seeders=seeders,
                        peers=peers,
                    )
                    future.set_result(response)

            elif action == TrackerAction.SCRAPE.value:
                # Scrape response format:
                # action (4) + transaction_id (4) + [complete (4) + downloaded (4) + incomplete (4) per info_hash]
                if (
                    len(data) >= 20
                ):  # At least action + tx_id + one set of scrape data (12 bytes)
                    complete = struct.unpack("!I", data[8:12])[0]
                    downloaded = struct.unpack("!I", data[12:16])[0]
                    incomplete = struct.unpack("!I", data[16:20])[0]
                    response = TrackerResponse(
                        action=TrackerAction.SCRAPE,
                        transaction_id=transaction_id,
                        complete=complete,
                        downloaded=downloaded,
                        incomplete=incomplete,
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

        except Exception as e:  # pragma: no cover - Exception handling in response parsing, hard to trigger reliably in tests
            self.logger.debug(
                "Error parsing tracker response: %s", e
            )  # pragma: no cover - Logging statement in exception handler

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old sessions."""
        while True:  # pragma: no cover - Background loop, tested via cancellation
            try:
                await asyncio.sleep(300.0)  # Clean every 5 minutes
                await (
                    self._cleanup_sessions()
                )  # pragma: no cover - Tested via direct calls
            except asyncio.CancelledError:
                break  # pragma: no cover - Cancellation tested separately
            except Exception:  # pragma: no cover - Exception handling tested separately
                self.logger.exception("Error in cleanup loop")

    async def _cleanup_sessions(self) -> None:
        """Clean up old tracker sessions."""
        current_time = time.time()
        to_remove = []

        for session_key, session in self.sessions.items():
            # Remove sessions that haven't been used for 1 hour
            if (
                current_time - session.last_announce > 3600.0
                or session.retry_count >= session.max_retries
            ):
                to_remove.append(session_key)

        for session_key in to_remove:
            del self.sessions[session_key]

    async def scrape(self, torrent_data: dict[str, Any]) -> dict[str, Any]:
        """Scrape tracker for statistics.

        Args:
            torrent_data: Parsed torrent data with info_hash and announce URLs

        Returns:
            Scraped statistics with keys: seeders, leechers, completed
            Returns empty dict if scraping fails or is not supported

        """
        try:
            # Check if transport is initialized
            if self.transport is None:
                self.logger.warning("UDP transport not initialized, cannot scrape")
                return {}

            # Extract info hash from torrent data
            info_hash = torrent_data.get("info_hash")
            if not info_hash:
                self.logger.debug("No info_hash in torrent data")
                return {}

            # Validate info_hash length
            if len(info_hash) != 20:
                self.logger.debug("Invalid info_hash length: %d", len(info_hash))
                return {}

            # Get tracker URLs
            tracker_urls = self._extract_tracker_urls(torrent_data)
            if not tracker_urls:
                self.logger.debug("No UDP tracker URLs found")
                return {}

            # Use first UDP tracker
            tracker_url = tracker_urls[0]
            host, port = self._parse_udp_url(tracker_url)
            tracker_address = (host, port)

            # Get or create tracker session
            session_key = f"{host}:{port}"
            if session_key not in self.sessions:
                self.sessions[session_key] = TrackerSession(
                    url=tracker_url, host=host, port=port
                )

            session = self.sessions[session_key]

            # Ensure connection is established
            if not session.is_connected or time.time() - session.connection_time > 60.0:
                try:
                    await self._connect_to_tracker(session)
                except Exception as e:
                    self.logger.debug(
                        "Failed to connect to tracker %s:%s: %s", host, port, e
                    )
                    return {}

            if not session.is_connected:
                self.logger.debug(
                    "Not connected to tracker %s:%s", host, port
                )  # pragma: no cover - Connection check debug, tested via integration tests
                return {}  # pragma: no cover - Connection check early return, tested via integration tests

            if session.connection_id is None:
                self.logger.debug(
                    "No connection ID for tracker %s:%s", host, port
                )  # pragma: no cover - Connection ID check debug, tested via integration tests
                return {}  # pragma: no cover - Connection ID check early return, tested via integration tests

            # Create scrape request
            transaction_id = self._get_transaction_id()
            request_data = self._encode_scrape_request(
                session.connection_id, transaction_id, info_hash
            )

            # Send scrape request
            # Validate socket is ready
            self._validate_socket_ready()

            # Use lock to serialize socket operations
            async with self._socket_lock:
                # Send scrape request (transport is guaranteed to be non-None after validation)
                if self.transport is None:
                    raise RuntimeError("Transport is None after validation")

                # CRITICAL FIX: On Windows ProactorEventLoop, ensure socket is fully ready before sendto
                import sys
                loop = asyncio.get_event_loop()
                is_proactor = isinstance(loop, asyncio.ProactorEventLoop)
                if sys.platform == "win32" and is_proactor:
                    # Small delay to ensure socket state is synchronized on Windows Proactor
                    await asyncio.sleep(0.01)

                # Wrap sendto in try/except to catch WinError 10022 and other socket errors
                try:
                    self.transport.sendto(request_data, tracker_address)
                except OSError as send_error:
                    # Check if this is WinError 10022 (transient on Windows)
                    import sys

                    error_code = getattr(send_error, "winerror", None) or getattr(
                        send_error, "errno", None
                    )
                    is_winerror_10022 = (
                        error_code == 10022
                        or (hasattr(send_error, "errno") and send_error.errno == 22)
                        or (sys.platform == "win32" and "10022" in str(send_error))
                    )
                    if is_winerror_10022:
                        # WinError 10022 is transient - log and re-raise for caller to handle
                        self.logger.debug(
                            "WinError 10022 during sendto to %s:%d (will retry): %s",
                            tracker_address[0],
                            tracker_address[1],
                            send_error,
                        )
                    # Re-raise to be caught by caller's exception handler
                    raise

            # Wait for response
            response_data = await self._wait_for_response(transaction_id, timeout=10.0)

            if response_data:
                # Parse scrape response
                return self._decode_scrape_response(response_data, info_hash)

            self.logger.debug(
                "No response from tracker for scrape"
            )  # pragma: no cover - No response debug, tested via integration tests with timeout
            return {}  # pragma: no cover - No response early return, tested via integration tests

        except (
            Exception
        ):  # pragma: no cover - Scrape exception, defensive error handling
            self.logger.exception("UDP scrape failed")
            return {}

    def _encode_scrape_request(
        self, connection_id: int, transaction_id: int, info_hash: bytes
    ) -> bytes:
        """Encode UDP scrape request.

        Args:
            connection_id: Connection ID from tracker (8 bytes)
            transaction_id: Transaction ID for this request
            info_hash: Info hash of torrent to scrape (20 bytes)

        Returns:
            Encoded scrape request bytes

        """
        if len(info_hash) != 20:
            msg = f"Invalid info_hash length: {len(info_hash)}, expected 20"
            raise ValueError(msg)

        # UDP scrape request format:
        # connection_id (8) + action (4) + transaction_id (4) + info_hash (20)
        data = struct.pack(
            "!QII", connection_id, TrackerAction.SCRAPE.value, transaction_id
        )
        data += info_hash
        return data

    def _decode_scrape_response(
        self, response: TrackerResponse, _info_hash: bytes
    ) -> dict[str, Any]:
        """Decode UDP scrape response.

        Args:
            response: TrackerResponse object from handle_response (with scrape fields)
            info_hash: Info hash we scraped (for validation, multi-hash support)

        Returns:
            Dictionary with keys: seeders, leechers, completed
            Returns empty dict on parse failure

        """
        try:
            # Validate response action
            if response.action != TrackerAction.SCRAPE:
                self.logger.debug(
                    "Unexpected action in scrape response: %s", response.action
                )
                return {}

            # If response has error, return empty
            if response.error_message:
                self.logger.debug("Scrape response error: %s", response.error_message)
                return {}

            # Extract scrape data from TrackerResponse (now populated by handle_response)
            if (
                response.complete is None
                or response.downloaded is None
                or response.incomplete is None
            ):
                self.logger.debug("Missing scrape data in response")
                return {}

            # Return standardized format
            return {
                "seeders": response.complete,
                "leechers": response.incomplete,
                "completed": response.downloaded,
            }

        except Exception:
            self.logger.exception(
                "Failed to decode scrape response"
            )  # pragma: no cover - Decode scrape error handler, defensive error handling
            return {}  # pragma: no cover - Decode scrape error handler, defensive error handling

    def _decode_scrape_response_raw(
        self, data: bytes, transaction_id: int
    ) -> dict[str, Any]:
        """Decode raw UDP scrape response bytes.

        Args:
            data: Raw response bytes
            transaction_id: Expected transaction ID

        Returns:
            Dictionary with keys: seeders, leechers, completed

        """
        try:
            if len(data) < 8:
                return {}  # pragma: no cover - Short data validation, tested via integration tests with malformed responses

            action, tx_id = struct.unpack("!II", data[:8])

            # Validate action and transaction ID
            if action != TrackerAction.SCRAPE.value:
                self.logger.debug(
                    "Unexpected action in scrape response: %d", action
                )  # pragma: no cover - Action validation debug, tested via integration tests
                return {}  # pragma: no cover - Action validation early return, tested via integration tests

            if tx_id != transaction_id:
                self.logger.debug(
                    "Transaction ID mismatch: expected %d, got %d",
                    transaction_id,
                    tx_id,
                )  # pragma: no cover - Transaction ID validation debug, tested via integration tests
                return {}  # pragma: no cover - Transaction ID validation early return, tested via integration tests

            # Parse scrape data (complete, downloaded, incomplete for each info hash)
            # For single info_hash: 12 bytes total
            scrape_data = data[8:]
            if len(scrape_data) < 12:
                self.logger.debug(
                    "Insufficient scrape data: %d bytes", len(scrape_data)
                )  # pragma: no cover - Scrape data length validation debug, tested via integration tests
                return {}  # pragma: no cover - Scrape data length validation early return, tested via integration tests

            complete, downloaded, incomplete = struct.unpack("!III", scrape_data[:12])

            # Return standardized format
            return {
                "seeders": complete,
                "leechers": incomplete,
                "completed": downloaded,
            }

        except Exception:
            self.logger.exception(
                "Failed to decode raw scrape response"
            )  # pragma: no cover - Decode raw scrape error handler, defensive error handling
            return {}  # pragma: no cover - Decode raw scrape error handler, defensive error handling


class UDPTrackerProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for tracker communication."""

    def __init__(self, client: AsyncUDPTrackerClient):
        """Initialize UDP protocol handler."""
        self.client = client

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        self.client.handle_response(
            data, addr
        )  # pragma: no cover - UDP datagram callback, tested via handle_response directly

    def error_received(
        self, exc: Exception
    ) -> None:  # pragma: no cover - UDP error callback, tested separately
        """Handle UDP error.

        CRITICAL: Only log errors, don't mark socket as invalid. The actual send operations
        will handle errors via exceptions and can retry appropriately. This callback is
        called asynchronously and may be called for transient errors.

        Behavior is consistent with DHT and uTP implementations which also only log errors.
        """
        import sys

        error_code = (
            getattr(exc, "winerror", None) if hasattr(exc, "winerror") else None
        )
        error_code_alt = getattr(exc, "errno", None) if hasattr(exc, "errno") else None
        error_msg = str(exc)

        # Check if this is WinError 10022
        is_winerror_10022 = (
            error_code == 10022
            or error_code_alt == 10022
            or error_code_alt == 22  # Some systems use errno 22
            or "10022" in error_msg
            or ("Invalid argument" in error_msg and sys.platform == "win32")
        )

        if is_winerror_10022:
            # WinError 10022: Invalid argument - may be transient on Windows ProactorEventLoop
            # Reduce verbosity - only log WARNING once per interval, then DEBUG
            # Don't mark socket as invalid - let send operations handle errors via exceptions
            current_time = time.time()
            time_since_last_warning = (
                current_time - self.client._last_winerror_warning_time
            )

            if time_since_last_warning >= self.client._winerror_warning_interval:
                # First warning in this interval - log at WARNING level
                self.client.logger.warning(
                    "UDP socket error (WinError 10022) detected: %s. "
                    "This may be transient on Windows. Send operations will retry. "
                    "Subsequent occurrences will be logged at DEBUG level.",
                    exc,
                )
                self.client._last_winerror_warning_time = current_time
            else:
                # Subsequent warning in same interval - log at DEBUG level
                self.client.logger.debug(
                    "UDP socket error (WinError 10022) detected: %s", exc
                )
        else:
            # Other errors should be logged at appropriate level
            self.client.logger.debug(
                "UDP error: %s", exc
            )  # pragma: no cover - Logging statement, tested via other paths


# Global UDP tracker client instance
# Singleton pattern removed - UDP tracker client is now managed via AsyncSessionManager.udp_tracker_client
# This ensures proper lifecycle management and prevents socket recreation issues
