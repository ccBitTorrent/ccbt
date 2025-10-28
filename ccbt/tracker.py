"""High-performance async tracker communication for BitTorrent client.

This module handles async communication with BitTorrent trackers to obtain
peer lists and announce the client's presence in the swarm with concurrent
announces and optimized HTTP handling.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import aiohttp

from ccbt.bencode import BencodeDecoder
from ccbt.config import get_config


class TrackerError(Exception):
    """Exception raised when tracker communication fails."""


@dataclass
class TrackerResponse:
    """Tracker response data."""

    interval: int
    peers: list[dict[str, Any]]
    complete: int | None = None
    incomplete: int | None = None
    download_url: str | None = None
    tracker_id: str | None = None
    warning_message: str | None = None


@dataclass
class TrackerSession:
    """Tracker session state."""

    url: str
    last_announce: float = 0.0
    interval: int = 1800
    min_interval: int | None = None
    tracker_id: str | None = None
    failure_count: int = 0
    last_failure: float = 0.0
    backoff_delay: float = 1.0


class AsyncTrackerClient:
    """High-performance async client for communicating with BitTorrent trackers."""

    def __init__(self, peer_id_prefix: str = "-CC0101-"):
        """Initialize the async tracker client.

        Args:
            peer_id_prefix: Prefix for generating peer IDs (default: -CC0101- for ccBitTorrent 0.1.0)
        """
        self.config = get_config()
        self.peer_id_prefix = peer_id_prefix.encode("utf-8")
        self.user_agent = "ccBitTorrent/0.1.0"

        # HTTP session
        self.session: aiohttp.ClientSession | None = None

        # Tracker sessions
        self.sessions: dict[str, TrackerSession] = {}

        # Background tasks
        self._announce_task: asyncio.Task | None = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the async tracker client."""
        # Create HTTP session with optimized settings
        timeout = aiohttp.ClientTimeout(
            total=self.config.network.connection_timeout,
            connect=self.config.network.connection_timeout,
        )

        connector = aiohttp.TCPConnector(
            limit=50,  # Default connection limit
            limit_per_host=10,  # Default per-host limit
            ttl_dns_cache=300,  # 5 minute DNS cache
            use_dns_cache=True,
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": self.user_agent},
        )

        self.logger.info("Async tracker client started")

    async def stop(self) -> None:
        """Stop the async tracker client."""
        if self._announce_task:
            self._announce_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._announce_task

        if self.session:
            await self.session.close()

        self.logger.info("Async tracker client stopped")

    async def announce(
        self,
        torrent_data: dict[str, Any],
        port: int = 6881,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> TrackerResponse:
        """Announce to the tracker and get peer list asynchronously.

        Args:
            torrent_data: Parsed torrent data from TorrentParser
            port: Port the client is listening on
            uploaded: Number of bytes uploaded (0 for initial announce)
            downloaded: Number of bytes downloaded (0 for initial announce)
            left: Number of bytes left to download (defaults to total file size)
            event: Event type ("started", "completed", "stopped", or "" for regular)

        Returns:
            TrackerResponse containing tracker response data

        Raises:
            TrackerError: If tracker communication fails
        """
        if not self.session:
            msg = "Tracker client not started"
            raise TrackerError(msg)

        try:
            # Generate peer ID if not already present
            if "peer_id" not in torrent_data:
                torrent_data["peer_id"] = self._generate_peer_id()

            # Set left to total file size if not specified
            if left is None:
                left = torrent_data["file_info"]["total_length"]

            # Build tracker URL with parameters
            tracker_url = self._build_tracker_url(
                torrent_data["announce"],
                torrent_data["info_hash"],
                torrent_data["peer_id"],
                port,
                uploaded,
                downloaded,
                left,
                event,
            )

            # Make async HTTP request
            response_data = await self._make_request_async(tracker_url)

            # Parse response
            response = self._parse_response_async(response_data)

            # Update tracker session
            self._update_tracker_session(torrent_data["announce"], response)

        except Exception as e:
            self._handle_tracker_failure(torrent_data["announce"])
            msg = f"Tracker announce failed: {e}"
            raise TrackerError(msg) from e
        else:
            return response

    async def announce_to_multiple(
        self,
        torrent_data: dict[str, Any],
        tracker_urls: list[str],
        port: int = 6881,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> list[TrackerResponse]:
        """Announce to multiple trackers concurrently.

        Args:
            torrent_data: Parsed torrent data
            tracker_urls: List of tracker URLs to announce to
            port: Port the client is listening on
            uploaded: Number of bytes uploaded
            downloaded: Number of bytes downloaded
            left: Number of bytes left to download
            event: Event type

        Returns:
            List of successful tracker responses
        """
        if not self.session:
            msg = "Tracker client not started"
            raise TrackerError(msg)

        # Create announce tasks for all trackers
        tasks = []
        for url in tracker_urls:
            # Create a copy of torrent data with this tracker URL
            torrent_copy = torrent_data.copy()
            torrent_copy["announce"] = url

            task = asyncio.create_task(
                self._announce_to_tracker(
                    torrent_copy,
                    port,
                    uploaded,
                    downloaded,
                    left,
                    event,
                ),
            )
            tasks.append(task)

        # Wait for all announces to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful responses
        successful_responses = []
        for result in results:
            if isinstance(result, TrackerResponse):
                successful_responses.append(result)
            elif isinstance(result, Exception):
                self.logger.warning("Tracker announce failed: %s", result)

        return successful_responses

    async def _announce_to_tracker(
        self,
        torrent_data: dict[str, Any],
        port: int,
        uploaded: int,
        downloaded: int,
        left: int | None,
        event: str,
    ) -> TrackerResponse:
        """Announce to a single tracker."""
        try:
            return await self.announce(
                torrent_data,
                port,
                uploaded,
                downloaded,
                left,
                event,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to announce to %s: %s",
                torrent_data["announce"],
                e,
            )
            raise

    def _generate_peer_id(self) -> bytes:
        """Generate a unique peer ID for this client."""
        # Use format: -CC0101- followed by 12 random bytes
        import secrets

        random_bytes = secrets.token_bytes(12)
        return self.peer_id_prefix + random_bytes

    def _build_tracker_url(
        self,
        base_url: str,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        event: str,
    ) -> str:
        """Build the complete tracker URL with all required parameters.

        Args:
            base_url: Base tracker URL from torrent
            info_hash: SHA-1 hash of info dictionary
            peer_id: Client's peer ID
            port: Client listening port
            uploaded: Bytes uploaded
            downloaded: Bytes downloaded
            left: Bytes left to download
            event: Event type

        Returns:
            Complete tracker URL with query parameters
        """
        # URL encode binary parameters
        info_hash_encoded = urllib.parse.quote(info_hash)
        peer_id_encoded = urllib.parse.quote(peer_id)

        # Build query parameters
        params = {
            "info_hash": info_hash_encoded,
            "peer_id": peer_id_encoded,
            "port": str(port),
            "uploaded": str(uploaded),
            "downloaded": str(downloaded),
            "left": str(left),
            "compact": "1",  # Request compact peer format
        }

        # Add event if specified
        if event:
            params["event"] = event

        # Build full URL
        separator = "&" if "?" in base_url else "?"
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}{separator}{query_string}"

    async def _make_request_async(self, url: str) -> bytes:
        """Make async HTTP GET request to tracker."""
        if self.session is None:
            msg = "HTTP session not initialized"
            raise RuntimeError(msg)
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    msg = f"HTTP {response.status}: {response.reason}"
                    raise TrackerError(msg)

                return await response.read()

        except aiohttp.ClientError as e:
            msg = f"Network error: {e}"
            raise TrackerError(msg) from e
        except Exception as e:
            msg = f"Request failed: {e}"
            raise TrackerError(msg) from e

    def _update_tracker_session(self, url: str, response: TrackerResponse) -> None:
        """Update tracker session with response data."""
        if url not in self.sessions:
            self.sessions[url] = TrackerSession(url=url)

        session = self.sessions[url]
        session.last_announce = time.time()
        session.interval = response.interval
        session.tracker_id = response.tracker_id
        session.failure_count = 0  # Reset failure count on success

    def _handle_tracker_failure(self, url: str) -> None:
        """Handle tracker failure with exponential backoff."""
        if url not in self.sessions:
            self.sessions[url] = TrackerSession(url=url)

        session = self.sessions[url]
        session.failure_count += 1
        session.last_failure = time.time()
        session.backoff_delay = min(session.backoff_delay * 2, 300)  # Max 5 minutes

    def _parse_response_async(self, response_data: bytes) -> TrackerResponse:
        """Parse tracker response asynchronously.

        Args:
            response_data: Raw response data from tracker

        Returns:
            TrackerResponse object

        Raises:
            TrackerError: If response parsing fails
        """
        try:
            # Decode bencoded response
            decoder = BencodeDecoder(response_data)
            decoded = decoder.decode()

            # Check for failure reason
            if b"failure reason" in decoded:
                reason = decoded[b"failure reason"].decode("utf-8", errors="ignore")
                msg = f"Tracker failure: {reason}"
                raise TrackerError(msg)

            # Validate required fields
            if b"interval" not in decoded:
                msg = "Missing interval in tracker response"
                raise TrackerError(msg)

            if b"peers" not in decoded:
                msg = "Missing peers in tracker response"
                raise TrackerError(msg)

            # Extract basic fields
            interval = decoded[b"interval"]
            peers_data = decoded[b"peers"]

            # Parse compact peers if present
            if isinstance(peers_data, bytes):
                peers = self._parse_compact_peers(peers_data)
            else:
                peers = peers_data

            # Extract optional fields
            complete = decoded.get(b"complete")
            incomplete = decoded.get(b"incomplete")
            download_url = decoded.get(b"download_url")
            if download_url and isinstance(download_url, bytes):
                download_url = download_url.decode("utf-8")

            tracker_id = decoded.get(b"tracker id")
            if tracker_id and isinstance(tracker_id, bytes):
                tracker_id = tracker_id.decode("utf-8")

            warning_message = decoded.get(b"warning message")
            if warning_message and isinstance(warning_message, bytes):
                warning_message = warning_message.decode("utf-8")

            return TrackerResponse(
                interval=interval,
                peers=peers,
                complete=complete,
                incomplete=incomplete,
                download_url=download_url,
                tracker_id=tracker_id,
                warning_message=warning_message,
            )

        except Exception as e:
            if isinstance(e, TrackerError):
                raise
            msg = f"Failed to parse tracker response: {e}"
            raise TrackerError(msg) from e

    def _parse_compact_peers(self, peers_data: bytes) -> list[dict[str, Any]]:
        """Parse compact peer format.

        In compact format, peers are encoded as 6 bytes per peer:
        - 4 bytes: IP address (network byte order)
        - 2 bytes: port (network byte order)

        Args:
            peers_data: Compact peer data

        Returns:
            List of peer dictionaries with 'ip' and 'port' keys

        Raises:
            TrackerError: If peer data is invalid
        """
        if len(peers_data) % 6 != 0:
            msg = f"Invalid compact peer data length: {len(peers_data)} bytes"
            raise TrackerError(
                msg,
            )

        peers = []
        num_peers = len(peers_data) // 6

        for i in range(num_peers):
            start = i * 6
            peer_bytes = peers_data[start : start + 6]

            # Extract IP (4 bytes)
            ip_bytes = peer_bytes[0:4]
            ip = ".".join(str(b) for b in ip_bytes)

            # Extract port (2 bytes, big-endian)
            port_bytes = peer_bytes[4:6]
            port = int.from_bytes(port_bytes, byteorder="big")

            peers.append(
                {
                    "ip": ip,
                    "port": port,
                },
            )

        return peers

    async def scrape(self, torrent_data: dict[str, Any]) -> dict[str, Any]:
        """Scrape tracker for statistics asynchronously (if supported).

        Note: Not all trackers support scraping.

        Args:
            torrent_data: Parsed torrent data

        Returns:
            Scraped statistics or empty dict if not supported
        """
        try:
            # Extract info hash from torrent data
            info_hash = torrent_data.get("info_hash")
            if not info_hash:
                return {}

            # Build scrape URL
            announce_url = torrent_data.get("announce")
            if not announce_url:
                return {}

            scrape_url = self._build_scrape_url(info_hash, announce_url)
            if not scrape_url:
                return {}

            # Make HTTP request
            async with aiohttp.ClientSession() as session, session.get(
                scrape_url
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    return self._parse_scrape_response(data)

            return {}

        except Exception:
            self.logger.exception("HTTP scrape failed")
            return {}

    def _build_scrape_url(self, info_hash: bytes, announce_url: str) -> str | None:
        """Build scrape URL from tracker URL."""
        try:
            # Convert tracker announce URL to scrape URL
            if announce_url.endswith("/announce"):
                scrape_url = announce_url.replace("/announce", "/scrape")
            else:
                scrape_url = announce_url.rstrip("/") + "/scrape"

            # Add info hash parameter
            info_hash_hex = info_hash.hex()
            scrape_url += f"?info_hash={info_hash_hex}"

            return scrape_url

        except Exception:
            return None

    def _parse_scrape_response(self, data: bytes) -> dict[str, Any]:
        """Parse scrape response."""
        try:
            # Parse bencoded response
            from ccbt import bencode

            response = bencode.decode(data)

            if "files" in response:
                files = response["files"]
                if files:
                    # Get first file's statistics
                    file_stats = next(iter(files.values()))
                    return {
                        "complete": file_stats.get("complete", 0),
                        "downloaded": file_stats.get("downloaded", 0),
                        "incomplete": file_stats.get("incomplete", 0),
                    }

            return {}

        except Exception:
            return {}


# Backward compatibility
class TrackerClient:
    """Synchronous tracker client for backward compatibility."""

    def __init__(self, peer_id_prefix: str = "-CC0101-"):
        """Initialize the tracker client.

        Args:
            peer_id_prefix: Prefix for generating peer IDs (default: -CC0101- for ccBitTorrent 0.1.0)
        """
        self.config = get_config()
        self.peer_id_prefix = peer_id_prefix.encode("utf-8")
        self.user_agent = "ccBitTorrent/0.1.0"

        # Tracker sessions
        self.sessions: dict[str, TrackerSession] = {}

        self.logger = logging.getLogger(__name__)

    def _generate_peer_id(self) -> bytes:
        """Generate a unique peer ID."""
        import secrets

        random_part = "".join(secrets.choice("0123456789abcdef") for _ in range(12))
        return self.peer_id_prefix + random_part.encode("utf-8")

    def _build_tracker_url(
        self,
        announce_url: str,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        event: str = "",
        compact: int = 1,
    ) -> str:
        """Build tracker URL with parameters."""
        params = {
            "info_hash": info_hash,
            "peer_id": peer_id,
            "port": port,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "left": left,
            "compact": compact,
        }

        if event:
            params["event"] = event

        # Build query string
        query_parts = []
        for key, param_val in params.items():
            value_str = param_val.hex() if isinstance(param_val, bytes) else param_val
            query_parts.append(f"{key}={value_str}")

        query_string = "&".join(query_parts)
        separator = "&" if "?" in announce_url else "?"
        return f"{announce_url}{separator}{query_string}"

    def _make_request(self, url: str) -> bytes:
        """Make HTTP GET request to tracker using urllib."""
        try:
            # Create request with user agent header
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ccBitTorrent/0.1.0")

            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                msg = f"Unsupported URL scheme: {parsed.scheme}"
                raise ValueError(msg)

            with urllib.request.urlopen(req) as response:  # nosec S310 - scheme validated
                return response.read()
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            raise TrackerError(msg) from e
        except urllib.error.URLError as e:
            msg = f"Network error: {e}"
            raise TrackerError(msg) from e
        except Exception as e:
            msg = f"Request failed: {e}"
            raise TrackerError(msg) from e

    def _parse_response(self, response_data: bytes) -> dict[str, Any]:
        """Parse tracker response."""
        try:
            # Decode bencoded response
            decoder = BencodeDecoder(response_data)
            decoded = decoder.decode()

            # Check for failure reason
            if b"failure reason" in decoded:
                failure_reason = decoded[b"failure reason"].decode(
                    "utf-8",
                    errors="ignore",
                )
                msg = f"Tracker failure: {failure_reason}"
                raise TrackerError(msg)

            # Validate required fields
            if b"interval" not in decoded:
                msg = "Missing interval in tracker response"
                raise TrackerError(msg)

            if b"peers" not in decoded:
                msg = "Missing peers in tracker response"
                raise TrackerError(msg)

            # Extract response data
            interval = decoded[b"interval"]

            # Parse peers
            peers = []
            if b"peers" in decoded:
                peers_data = decoded[b"peers"]
                if isinstance(peers_data, bytes):
                    # Compact peer format
                    peers = self._parse_compact_peers(peers_data)
                elif isinstance(peers_data, list):
                    # Dictionary format
                    for peer_info in peers_data:
                        if isinstance(peer_info, dict):
                            peer_ip = peer_info.get(b"ip", b"").decode(
                                "utf-8",
                                errors="ignore",
                            )
                            peer_port = peer_info.get(b"port", 0)
                            if peer_ip and peer_port:
                                peers.append({"ip": peer_ip, "port": peer_port})

            # Optional fields
            complete = decoded.get(b"complete")
            incomplete = decoded.get(b"incomplete")
            download_url = (
                decoded.get(b"download_url", b"").decode("utf-8", errors="ignore")
                if b"download_url" in decoded
                else None
            )
            tracker_id = (
                decoded.get(b"tracker id", b"").decode("utf-8", errors="ignore")
                if b"tracker id" in decoded
                else None
            )
            warning_message = (
                decoded.get(b"warning message", b"").decode("utf-8", errors="ignore")
                if b"warning message" in decoded
                else None
            )

        except Exception as e:
            msg = f"Failed to parse tracker response: {e}"
            raise TrackerError(msg) from e
        else:
            return {
                "interval": interval,
                "peers": peers,
                "complete": complete,
                "incomplete": incomplete,
                "download_url": download_url,
                "tracker_id": tracker_id,
                "warning_message": warning_message,
            }

    def _parse_compact_peers(self, peers_data: bytes) -> list[dict[str, Any]]:
        """Parse compact peer format (4 bytes IP + 2 bytes port)."""
        if len(peers_data) % 6 != 0:
            msg = f"Invalid compact peers data length: {len(peers_data)}"
            raise TrackerError(msg)

        peers = []
        for i in range(0, len(peers_data), 6):
            peer_bytes = peers_data[i : i + 6]
            ip_bytes = peer_bytes[0:4]
            port_bytes = peer_bytes[4:6]

            # Convert IP bytes to string
            ip = ".".join(str(b) for b in ip_bytes)

            # Convert port bytes to int (big-endian)
            port = int.from_bytes(port_bytes, byteorder="big")

            peers.append({"ip": ip, "port": port})

        return peers

    def _update_tracker_session(self, url: str, response: dict[str, Any]) -> None:
        """Update tracker session with response data."""
        if url not in self.sessions:
            self.sessions[url] = TrackerSession(url=url)

        session = self.sessions[url]
        session.last_announce = time.time()
        session.interval = response.get("interval", 1800)
        session.tracker_id = response.get("tracker_id")
        session.failure_count = 0  # Reset failure count on success

    def _handle_tracker_failure(self, url: str) -> None:
        """Handle tracker failure with exponential backoff."""
        if url not in self.sessions:
            self.sessions[url] = TrackerSession(url=url)

        session = self.sessions[url]
        session.failure_count += 1
        session.last_failure = time.time()
        session.backoff_delay = min(session.backoff_delay * 2, 300)  # Max 5 minutes

    def announce(
        self,
        torrent_data: dict[str, Any],
        port: int = 6881,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> dict[str, Any]:
        """Announce to the tracker and get peer list.

        Args:
            torrent_data: Parsed torrent data from TorrentParser
            port: Port the client is listening on
            uploaded: Number of bytes uploaded (0 for initial announce)
            downloaded: Number of bytes downloaded (0 for initial announce)
            left: Number of bytes left to download (defaults to total file size)
            event: Event type ("started", "completed", "stopped", or "" for regular)

        Returns:
            Dict containing tracker response data

        Raises:
            TrackerError: If tracker communication fails
        """
        try:
            # Generate peer ID if not already present
            if "peer_id" not in torrent_data:
                torrent_data["peer_id"] = self._generate_peer_id()

            # Set left to total file size if not specified
            if left is None:
                left = torrent_data.get("file_info", {}).get("total_length", 0)

            # Build tracker URL with parameters
            tracker_url = self._build_tracker_url(
                torrent_data["announce"],
                torrent_data["info_hash"],
                torrent_data["peer_id"],
                port,
                uploaded,
                downloaded,
                left,
                event,
            )

            # Make HTTP request
            response_data = self._make_request(tracker_url)

            # Parse response
            response = self._parse_response(response_data)

            # Update tracker session
            self._update_tracker_session(torrent_data["announce"], response)

        except TrackerError:
            # Update failure count and re-raise
            self._handle_tracker_failure(torrent_data["announce"])
            raise
        except Exception as e:
            # Handle unexpected errors
            self._handle_tracker_failure(torrent_data["announce"])
            msg = f"Tracker announce failed: {e}"
            raise TrackerError(msg) from e
        else:
            return response
