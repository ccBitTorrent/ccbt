"""IPC client for daemon communication.

from __future__ import annotations

Provides HTTP REST and WebSocket client for CLI-daemon communication.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp

from ccbt.daemon.ipc_protocol import (
    API_BASE_PATH,
    API_KEY_HEADER,
    PUBLIC_KEY_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    BlacklistAddRequest,
    BlacklistResponse,
    EventType,
    ExportStateRequest,
    ExternalIPResponse,
    ExternalPortResponse,
    FileListResponse,
    FilePriorityRequest,
    FileSelectRequest,
    GlobalStatsResponse,
    ImportStateRequest,
    IPFilterStatsResponse,
    NATMapRequest,
    NATStatusResponse,
    PeerListResponse,
    ProtocolInfo,
    QueueAddRequest,
    QueueListResponse,
    QueueMoveRequest,
    RateLimitRequest,
    ResumeCheckpointRequest,
    ScrapeListResponse,
    ScrapeRequest,
    ScrapeResult,
    StatusResponse,
    TorrentAddRequest,
    TorrentListResponse,
    TorrentStatusResponse,
    WebSocketEvent,
    WebSocketMessage,
    WebSocketSubscribeRequest,
    WhitelistAddRequest,
    WhitelistResponse,
)

logger = logging.getLogger(__name__)


class IPCClient:
    """IPC client for communicating with daemon via HTTP REST and WebSocket."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        key_manager: Any = None,  # Ed25519KeyManager
        timeout: float = 30.0,
    ):
        """Initialize IPC client.

        Args:
            api_key: API key for authentication (if None, will try to read from config)
            base_url: Base URL for daemon (if None, will construct from config or default)
            key_manager: Optional Ed25519KeyManager for cryptographic authentication
            timeout: Request timeout in seconds

        """
        self.api_key = api_key
        self.key_manager = key_manager
        self.base_url = base_url or self._get_default_url()
        self.timeout = aiohttp.ClientTimeout(total=timeout)

        self._session: aiohttp.ClientSession | None = None
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._websocket_task: asyncio.Task | None = None

    def _get_default_url(self) -> str:
        """Get default daemon URL from config or environment.

        Uses ConfigManager to read daemon configuration, ensuring consistency
        with the daemon's configuration source.
        """
        try:
            # Use ConfigManager to read daemon config (same source as daemon uses)
            from ccbt.config.config import get_config

            cfg = get_config()
            if cfg.daemon:
                ipc_port = cfg.daemon.ipc_port
                # Always connect via 127.0.0.1 (works with server binding to 0.0.0.0 or 127.0.0.1)
                # Server binding to 0.0.0.0 listens on all interfaces, including 127.0.0.1
                return f"http://127.0.0.1:{ipc_port}"
        except Exception as e:
            # Log but don't fail - fall back to defaults
            logger.debug("Could not read daemon config from ConfigManager: %s", e)

        # Fallback: Try to read from legacy config file (for backwards compatibility)
        config_file = Path.home() / ".ccbt" / "daemon" / "config.json"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
                    port = config.get("ipc_port", 8080)
                    # Always connect via 127.0.0.1 (works with server binding to 0.0.0.0 or 127.0.0.1)
                    return f"http://127.0.0.1:{port}"
            except Exception:
                pass

        # Default
        return "http://127.0.0.1:8080"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    def _get_headers(
        self, method: str = "GET", path: str = "", body: bytes | None = None
    ) -> dict[str, str]:
        """Get request headers with authentication.

        Args:
            method: HTTP method
            path: Request path
            body: Request body (for signing)

        Returns:
            Dictionary of headers

        """
        headers: dict[str, str] = {}

        # Try Ed25519 signing first if key_manager available
        if self.key_manager:
            try:
                import hashlib
                import time

                timestamp = str(time.time())
                body_hash = hashlib.sha256(body or b"").hexdigest()
                message = f"{method} {path}\n{timestamp}\n{body_hash}".encode()

                signature = self.key_manager.sign_message(message)
                public_key_hex = self.key_manager.get_public_key_hex()

                headers[SIGNATURE_HEADER] = signature.hex()
                headers[PUBLIC_KEY_HEADER] = public_key_hex
                headers[TIMESTAMP_HEADER] = timestamp
            except Exception as e:
                logger.debug("Failed to sign request with Ed25519: %s", e)
                # Fall through to API key

        # Fall back to API key if signing failed or key_manager not available
        if not headers.get(SIGNATURE_HEADER) and self.api_key:
            headers[API_KEY_HEADER] = self.api_key

        return headers

    async def close(self) -> None:
        """Close client connections.

        CRITICAL: This method must be called to prevent resource leaks.
        Ensures all connections are properly closed, even on errors.
        """
        # Close WebSocket first
        if self._websocket:
            try:
                await self._close_websocket()
            except Exception as e:
                logger.debug("Error closing WebSocket: %s", e)

        # Close HTTP session
        if self._session:
            try:
                if not self._session.closed:
                    await self._session.close()
                    # CRITICAL: Wait a small amount to ensure session cleanup completes
                    # This prevents "Unclosed client session" warnings on Windows
                    # Increased wait time on Windows for proper cleanup
                    import sys

                    wait_time = 0.2 if sys.platform == "win32" else 0.1
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.debug("Error closing HTTP session: %s", e)
            finally:
                # Ensure session is marked as closed even if close() failed
                self._session = None

    # HTTP REST Methods

    async def get_status(self) -> StatusResponse:
        """Get daemon status."""
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/status"
        path = f"{API_BASE_PATH}/status"

        async with session.get(url, headers=self._get_headers("GET", path)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return StatusResponse(**data)

    async def add_torrent(
        self,
        path_or_magnet: str,
        output_dir: str | None = None,
        resume: bool = False,
    ) -> str:
        """Add torrent or magnet.

        Args:
            path_or_magnet: Torrent file path or magnet URI
            output_dir: Optional output directory override
            resume: Whether to resume from checkpoint if available

        Returns:
            Info hash (hex string)

        Raises:
            aiohttp.ClientError: If connection fails or daemon returns error

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/add"

        req = TorrentAddRequest(
            path_or_magnet=path_or_magnet,
            output_dir=output_dir,
            resume=resume,
        )

        try:
            import json as json_lib

            body_json = json_lib.dumps(req.model_dump()).encode()
            path = f"{API_BASE_PATH}/torrents/add"
            async with session.post(
                url,
                json=req.model_dump(),
                headers=self._get_headers("POST", path, body_json),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["info_hash"]
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            logger.error(
                "Cannot connect to daemon at %s to add torrent: %s",
                self.base_url,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon at {self.base_url}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            logger.error(
                "Daemon returned error %d when adding torrent: %s",
                e.status,
                e.message,
            )
            # Try to get error details from response body if available
            error_msg = e.message
            try:
                # ClientResponseError doesn't have direct access to response
                # but we can use the request_info to get more context
                if hasattr(e, "request_info"):
                    error_msg = f"HTTP {e.status}: {e.message}"
            except Exception:
                pass
            raise RuntimeError(f"Daemon error when adding torrent: {error_msg}") from e
        except aiohttp.ClientError as e:
            # Other client errors
            logger.error(
                "Client error when adding torrent to daemon at %s: %s",
                self.base_url,
                e,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def remove_torrent(self, info_hash: str) -> bool:
        """Remove torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if removed, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            return True

    async def list_torrents(self) -> list[TorrentStatusResponse]:
        """List all torrents.

        Returns:
            List of torrent status responses

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            response = TorrentListResponse(**data)
            return response.torrents

    async def get_torrent_status(self, info_hash: str) -> TorrentStatusResponse | None:
        """Get torrent status.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Torrent status response or None if not found

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}"

        async with session.get(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            data = await resp.json()
            return TorrentStatusResponse(**data)

    async def pause_torrent(self, info_hash: str) -> bool:
        """Pause torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if paused, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/pause"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            return True

    async def resume_torrent(self, info_hash: str) -> bool:
        """Resume torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if resumed, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/resume"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            return True

    async def get_config(self) -> dict[str, Any]:
        """Get current config.

        Returns:
            Config dictionary

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/config"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def update_config(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Update config.

        Args:
            config_dict: Config updates (nested dict)

        Returns:
            Updated config dictionary

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/config"

        async with session.put(
            url,
            json=config_dict,
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def shutdown(self) -> bool:
        """Request daemon shutdown.

        Returns:
            True if shutdown request was sent

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/shutdown"

        try:
            async with session.post(url, headers=self._get_headers()) as resp:
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.debug("Error sending shutdown request: %s", e)
            return False

    # File Selection Methods

    async def get_torrent_files(self, info_hash: str) -> FileListResponse:
        """Get file list for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            File list response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/files"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return FileListResponse(**data)

    async def select_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Select files for download.

        Args:
            info_hash: Torrent info hash (hex string)
            file_indices: List of file indices to select

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/files/select"

        req = FileSelectRequest(file_indices=file_indices)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def deselect_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Deselect files.

        Args:
            info_hash: Torrent info hash (hex string)
            file_indices: List of file indices to deselect

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/files/deselect"

        req = FileSelectRequest(file_indices=file_indices)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def set_file_priority(
        self,
        info_hash: str,
        file_index: int,
        priority: str,
    ) -> dict[str, Any]:
        """Set file priority.

        Args:
            info_hash: Torrent info hash (hex string)
            file_index: File index
            priority: Priority level

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/files/priority"

        req = FilePriorityRequest(file_index=file_index, priority=priority)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def verify_files(self, info_hash: str) -> dict[str, Any]:
        """Verify torrent files.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/files/verify"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Queue Methods

    async def get_queue(self) -> QueueListResponse:
        """Get queue status.

        Returns:
            Queue list response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return QueueListResponse(**data)

    async def add_to_queue(self, info_hash: str, priority: str) -> dict[str, Any]:
        """Add torrent to queue.

        Args:
            info_hash: Torrent info hash (hex string)
            priority: Priority level

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/add"

        req = QueueAddRequest(info_hash=info_hash, priority=priority)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def remove_from_queue(self, info_hash: str) -> dict[str, Any]:
        """Remove torrent from queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/{info_hash}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def move_in_queue(self, info_hash: str, new_position: int) -> dict[str, Any]:
        """Move torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)
            new_position: New position in queue

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/{info_hash}/move"

        req = QueueMoveRequest(new_position=new_position)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def clear_queue(self) -> dict[str, Any]:
        """Clear queue.

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/clear"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def pause_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Pause torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/{info_hash}/pause"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def resume_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Resume torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/queue/{info_hash}/resume"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    # NAT Methods

    async def get_nat_status(self) -> NATStatusResponse:
        """Get NAT status.

        Returns:
            NAT status response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/status"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return NATStatusResponse(**data)

    async def discover_nat(self) -> dict[str, Any]:
        """Discover NAT devices.

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/discover"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def map_nat_port(
        self,
        internal_port: int,
        external_port: int | None = None,
        protocol: str = "tcp",
    ) -> dict[str, Any]:
        """Map a port via NAT.

        Args:
            internal_port: Internal port
            external_port: External port (optional)
            protocol: Protocol (tcp/udp)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/map"

        req = NATMapRequest(
            internal_port=internal_port,
            external_port=external_port,
            protocol=protocol,
        )
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def unmap_nat_port(self, port: int, protocol: str = "tcp") -> dict[str, Any]:
        """Unmap a port via NAT.

        Args:
            port: Port to unmap
            protocol: Protocol (tcp/udp)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/unmap"

        async with session.post(
            url,
            json={"port": port, "protocol": protocol},
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def refresh_nat_mappings(self) -> dict[str, Any]:
        """Refresh NAT mappings.

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/refresh"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Scrape Methods

    async def scrape_torrent(self, info_hash: str, force: bool = False) -> ScrapeResult:
        """Scrape a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            force: Force scrape even if recently scraped

        Returns:
            Scrape result

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/scrape/{info_hash}"

        req = ScrapeRequest(force=force)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ScrapeResult(**data)

    async def list_scrape_results(self) -> ScrapeListResponse:
        """List all cached scrape results.

        Returns:
            Scrape list response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/scrape"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ScrapeListResponse(**data)

    async def get_scrape_result(self, info_hash: str) -> ScrapeResult | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Scrape result if found, None otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/scrape/{info_hash}"

        async with session.get(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            data = await resp.json()
            return ScrapeResult(**data)

    # Protocol Methods

    async def get_xet_protocol(self) -> ProtocolInfo:
        """Get Xet protocol information.

        Returns:
            Protocol info

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/protocols/xet"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ProtocolInfo(**data)

    async def get_ipfs_protocol(self) -> ProtocolInfo:
        """Get IPFS protocol information.

        Returns:
            Protocol info

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/protocols/ipfs"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ProtocolInfo(**data)

    # Security Methods

    async def get_blacklist(self) -> BlacklistResponse:
        """Get blacklisted IPs.

        Returns:
            Blacklist response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/blacklist"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return BlacklistResponse(**data)

    async def get_whitelist(self) -> WhitelistResponse:
        """Get whitelisted IPs.

        Returns:
            Whitelist response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/whitelist"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return WhitelistResponse(**data)

    async def add_to_blacklist(self, ip: str, reason: str = "") -> dict[str, Any]:
        """Add IP to blacklist.

        Args:
            ip: IP address to blacklist
            reason: Optional reason for blacklisting

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/blacklist"

        req = BlacklistAddRequest(ip=ip, reason=reason)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def remove_from_blacklist(self, ip: str) -> dict[str, Any]:
        """Remove IP from blacklist.

        Args:
            ip: IP address to remove

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/blacklist/{ip}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def add_to_whitelist(self, ip: str, reason: str = "") -> dict[str, Any]:
        """Add IP to whitelist.

        Args:
            ip: IP address to whitelist
            reason: Optional reason for whitelisting

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/whitelist"

        req = WhitelistAddRequest(ip=ip, reason=reason)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def remove_from_whitelist(self, ip: str) -> dict[str, Any]:
        """Remove IP from whitelist.

        Args:
            ip: IP address to remove

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/whitelist/{ip}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def load_ip_filter(self) -> dict[str, Any]:
        """Load IP filter from config.

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/ip-filter/load"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_ip_filter_stats(self) -> IPFilterStatsResponse:
        """Get IP filter statistics.

        Returns:
            IP filter stats response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/security/ip-filter/stats"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return IPFilterStatsResponse(**data)

    # NAT Extended Methods

    async def get_external_ip(self) -> ExternalIPResponse:
        """Get external IP address.

        Returns:
            External IP response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/external-ip"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ExternalIPResponse(**data)

    async def get_external_port(
        self,
        internal_port: int,
        protocol: str = "tcp",
    ) -> ExternalPortResponse:
        """Get external port for an internal port.

        Args:
            internal_port: Internal port
            protocol: Protocol (tcp/udp)

        Returns:
            External port response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/nat/external-port/{internal_port}?protocol={protocol}"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return ExternalPortResponse(**data)

    # Torrent Extended Methods

    async def get_peers_for_torrent(self, info_hash: str) -> PeerListResponse:
        """Get list of peers for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Peer list response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/peers"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return PeerListResponse(**data)

    async def set_rate_limits(
        self,
        info_hash: str,
        download_kib: int,
        upload_kib: int,
    ) -> dict[str, Any]:
        """Set per-torrent rate limits.

        Args:
            info_hash: Torrent info hash (hex string)
            download_kib: Download limit in KiB/s
            upload_kib: Upload limit in KiB/s

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/rate-limits"

        req = RateLimitRequest(download_kib=download_kib, upload_kib=upload_kib)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def force_announce(self, info_hash: str) -> dict[str, Any]:
        """Force a tracker announce for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/announce"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def export_session_state(self, path: str | None = None) -> dict[str, Any]:
        """Export session state to a file.

        Args:
            path: Optional export path (defaults to state dir)

        Returns:
            Response dict with export path

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/export-state"

        req = ExportStateRequest(path=path)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file.

        Args:
            path: Import path (required)

        Returns:
            Imported state dictionary

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/import-state"

        req = ImportStateRequest(path=path)
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def resume_from_checkpoint(
        self,
        info_hash: str,
        checkpoint: dict[str, Any],
        torrent_path: str | None = None,
    ) -> dict[str, Any]:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (hex string)
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Response dict with resumed torrent info_hash

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/resume-checkpoint"

        req = ResumeCheckpointRequest(
            info_hash=info_hash,
            checkpoint=checkpoint,
            torrent_path=torrent_path,
        )
        async with session.post(
            url,
            json=req.model_dump(),
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Session Methods

    async def get_global_stats(self) -> GlobalStatsResponse:
        """Get global statistics across all torrents.

        Returns:
            Global stats response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/session/stats"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return GlobalStatsResponse(**data)

    # WebSocket Methods

    async def connect_websocket(self) -> bool:
        """Establish WebSocket connection.

        Returns:
            True if connected, False otherwise

        """
        if not self.api_key and not self.key_manager:
            logger.error(
                "API key or Ed25519 key manager required for WebSocket connection"
            )
            return False

        try:
            session = await self._ensure_session()
            ws_url = self.base_url.replace("http://", "ws://").replace(
                "https://", "wss://"
            )
            ws_path = f"{API_BASE_PATH}/events"

            # Try Ed25519 signing first
            if self.key_manager:
                try:
                    import time

                    timestamp = str(time.time())
                    message = f"GET {ws_path}\n{timestamp}".encode()
                    signature = self.key_manager.sign_message(message)
                    public_key_hex = self.key_manager.get_public_key_hex()

                    ws_url = f"{ws_url}{ws_path}?signature={signature.hex()}&public_key={public_key_hex}&timestamp={timestamp}"
                except Exception as e:
                    logger.debug("Failed to sign WebSocket request: %s", e)
                    # Fall through to API key
                    if self.api_key:
                        ws_url = f"{ws_url}{ws_path}?api_key={self.api_key}"
            else:
                ws_url = f"{ws_url}{ws_path}?api_key={self.api_key}"

            self._websocket = await session.ws_connect(ws_url)

            # Start receive task
            self._websocket_task = asyncio.create_task(self._websocket_receive_loop())

            return True
        except Exception as e:
            logger.exception("Error connecting WebSocket: %s", e)
            return False

    async def subscribe_events(self, event_types: list[EventType]) -> bool:
        """Subscribe to event types.

        Args:
            event_types: List of event types to subscribe to

        Returns:
            True if subscribed, False otherwise

        """
        if not self._websocket or self._websocket.closed:
            if not await self.connect_websocket():
                return False

        try:
            req = WebSocketSubscribeRequest(event_types=event_types)
            message = WebSocketMessage(action="subscribe", data=req.model_dump())

            if self._websocket and not self._websocket.closed:
                await self._websocket.send_json(message.model_dump())
                return True
            return False
        except Exception as e:
            logger.exception("Error subscribing to events: %s", e)
            return False

    async def receive_event(self, timeout: float = 1.0) -> WebSocketEvent | None:
        """Receive event from WebSocket.

        Args:
            timeout: Timeout in seconds

        Returns:
            WebSocket event or None if timeout

        """
        if not self._websocket or self._websocket.closed:
            return None

        try:
            msg = await asyncio.wait_for(
                self._websocket.receive(),
                timeout=timeout,
            )

            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "type" in data and "timestamp" in data:
                    return WebSocketEvent(**data)

            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.debug("Error receiving WebSocket event: %s", e)
            return None

    async def _websocket_receive_loop(self) -> None:
        """Background task to receive WebSocket messages."""
        if not self._websocket:
            return

        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # Messages are handled by receive_event
                    pass
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.warning("WebSocket error: %s", self._websocket.exception())
                    break
        except Exception as e:
            logger.debug("WebSocket receive loop error: %s", e)
        finally:
            await self._close_websocket()

    async def _close_websocket(self) -> None:
        """Close WebSocket connection."""
        if self._websocket_task:
            self._websocket_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._websocket_task
            self._websocket_task = None

        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
        self._websocket = None

    # Helper Methods

    async def is_daemon_running(self) -> bool:
        """Check if daemon is running and accessible.

        Returns:
            True if daemon is accessible, False otherwise

        """
        # CRITICAL: First verify socket is open before attempting HTTP connection
        # This helps diagnose Windows-specific networking issues
        try:
            import socket
            from urllib.parse import urlparse

            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8080

            # Quick socket test to verify port is open
            # CRITICAL FIX: On Windows, error 10035 (WSAEWOULDBLOCK) can be a false positive
            # Skip socket test if we get this error and proceed to HTTP check
            import sys

            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(1.0)
            try:
                result = test_sock.connect_ex((host, port))
                test_sock.close()
                if result != 0:
                    # On Windows, error 10035 (WSAEWOULDBLOCK) can be a false positive
                    # This can happen even when the server is listening
                    # Skip the socket test and proceed to HTTP check
                    if sys.platform == "win32" and result == 10035:
                        logger.debug(
                            "Socket test returned 10035 (WSAEWOULDBLOCK) on Windows for %s:%d. "
                            "This may be a false positive - proceeding with HTTP check.",
                            host,
                            port,
                        )
                        # Don't return False - continue to HTTP check
                    else:
                        logger.debug(
                            "Socket connection test to %s:%d failed (result=%d). "
                            "Port may not be open or firewall blocking. Proceeding with HTTP check anyway.",
                            host,
                            port,
                            result,
                        )
                        # Don't return False immediately - try HTTP check first
                        # HTTP check is more reliable than socket test on Windows
            except Exception as sock_error:
                test_sock.close()
                logger.debug(
                    "Socket test error for %s:%d: %s. Proceeding with HTTP check anyway.",
                    host,
                    port,
                    sock_error,
                )
                # Don't return False - continue to HTTP check
                # HTTP check is more reliable than socket test
        except Exception as test_error:
            logger.debug("Error in socket pre-check: %s", test_error)
            # Continue with HTTP check anyway

        try:
            # Use a shorter timeout for the status check to avoid long waits
            # The caller will handle retries with exponential backoff
            status = await asyncio.wait_for(self.get_status(), timeout=3.0)
            # Verify we got a valid status response
            return status is not None and hasattr(status, "status")
        except asyncio.TimeoutError:
            logger.debug(
                "Timeout checking daemon status at %s (daemon may be starting up or overloaded)",
                self.base_url,
            )
            return False
        except aiohttp.ClientConnectorError as e:
            # Connection refused or similar - daemon is not running or not accessible
            logger.debug(
                "Cannot connect to daemon at %s: %s (daemon may not be running or IPC server not started)",
                self.base_url,
                e,
            )
            return False
        except aiohttp.ClientError as e:
            # Other client errors (HTTP errors, etc.)
            logger.debug(
                "Client error checking daemon status at %s: %s (daemon may be starting up)",
                self.base_url,
                e,
            )
            return False
        except Exception as e:
            # Unexpected errors
            logger.debug(
                "Unexpected error checking daemon status at %s: %s",
                self.base_url,
                e,
                exc_info=e,
            )
            return False

    @staticmethod
    def get_daemon_pid() -> int | None:
        """Read daemon PID from file with validation and retry logic.

        Returns:
            PID or None if not found or invalid

        """
        pid_file = Path.home() / ".ccbt" / "daemon" / "daemon.pid"
        if not pid_file.exists():
            return None

        try:
            # CRITICAL FIX: Read with retry to handle race conditions
            import time

            pid_text = None
            for attempt in range(3):
                try:
                    pid_text = pid_file.read_text(encoding="utf-8")
                    if pid_text:
                        break
                except OSError as e:
                    if attempt < 2:
                        # File might be locked or being written - retry
                        time.sleep(0.1)
                        continue
                    logger.debug("Error reading PID file after retries: %s", e)
                    return None

            if not pid_text:
                # Empty file - remove it
                logger.debug("PID file is empty, removing")
                with contextlib.suppress(OSError):
                    pid_file.unlink()
                return None

            # Validate PID format
            pid_text = pid_text.strip()
            if not pid_text or not pid_text.isdigit():
                logger.warning(
                    "PID file contains invalid data: %r, removing", pid_text[:50]
                )
                with contextlib.suppress(OSError):
                    pid_file.unlink()
                return None

            pid = int(pid_text)

            # Validate PID is reasonable
            if pid <= 0 or pid > 2147483647:
                logger.warning("PID file contains invalid PID: %d, removing", pid)
                with contextlib.suppress(OSError):
                    pid_file.unlink()
                return None

            # Verify process is actually running
            # On Windows, os.kill() can raise ProcessLookupError or other exceptions
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                return pid
            except (OSError, ProcessLookupError):
                # Process doesn't exist, remove stale PID file
                pid_file.unlink()
                return None
            except Exception:
                # Handle any other unexpected exceptions (Windows-specific issues)
                # On Windows, os.kill() might raise exceptions with "exception set" errors
                pid_file.unlink()
                return None
        except (ValueError, OSError) as e:
            logger.debug("Error reading PID file: %s", e)
            return None

    @staticmethod
    def get_daemon_url() -> str:
        """Construct daemon URL from config or default.

        Uses ConfigManager to read daemon configuration, ensuring consistency
        with the daemon's configuration source.

        Returns:
            Daemon URL

        """
        try:
            # Use ConfigManager to read daemon config (same source as daemon uses)
            from ccbt.config.config import get_config

            cfg = get_config()
            if cfg.daemon:
                ipc_port = cfg.daemon.ipc_port
                # Always connect via 127.0.0.1 (works with server binding to 0.0.0.0 or 127.0.0.1)
                # Server binding to 0.0.0.0 listens on all interfaces, including 127.0.0.1
                return f"http://127.0.0.1:{ipc_port}"
        except Exception as e:
            # Log but don't fail - fall back to defaults
            logger.debug("Could not read daemon config from ConfigManager: %s", e)

        # Fallback: Try to read from legacy config file (for backwards compatibility)
        config_file = Path.home() / ".ccbt" / "daemon" / "config.json"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
                    port = config.get("ipc_port", 8080)
                    # Always connect via 127.0.0.1 (works with server binding to 0.0.0.0 or 127.0.0.1)
                    return f"http://127.0.0.1:{port}"
            except Exception:
                pass

        # Default
        return "http://127.0.0.1:8080"
