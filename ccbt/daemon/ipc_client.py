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
from typing import Any

import aiohttp

from ccbt.i18n import _
from ccbt.daemon.ipc_protocol import (
    API_BASE_PATH,
    API_KEY_HEADER,
    PUBLIC_KEY_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    AggressiveDiscoveryStatusResponse,
    BlacklistAddRequest,
    BlacklistResponse,
    DetailedGlobalMetricsResponse,
    DetailedPeerMetricsResponse,
    DetailedTorrentMetricsResponse,
    DiskIOMetricsResponse,
    DHTQueryMetricsResponse,
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
    GlobalPeerMetricsResponse,
    NetworkTimingMetricsResponse,
    PeerQualityMetricsResponse,
    PeerListResponse,
    PeerPerformanceMetrics,
    PerTorrentPerformanceResponse,
    PieceAvailabilityResponse,
    ProtocolInfo,
    QueueAddRequest,
    QueueListResponse,
    QueueMoveRequest,
    RateSamplesResponse,
    RateLimitRequest,
    ResumeCheckpointRequest,
    ScrapeListResponse,
    ScrapeRequest,
    ScrapeResult,
    StatusResponse,
    SwarmHealthMatrixResponse,
    TorrentAddRequest,
    TorrentListResponse,
    TorrentStatusResponse,
    TrackerInfo,
    TrackerListResponse,
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
        self._session_loop: asyncio.AbstractEventLoop | None = None  # Track loop session was created with
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
            logger.debug(_("Could not read daemon config from ConfigManager: %s"), e)

        # Fallback: Try to read from legacy config file (for backwards compatibility)
        # CRITICAL FIX: Use consistent path resolution helper to match daemon
        from ccbt.daemon.daemon_manager import _get_daemon_home_dir
        home_dir = _get_daemon_home_dir()
        config_file = home_dir / ".ccbt" / "daemon" / "config.json"
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
        """Ensure HTTP session is created.
        
        CRITICAL: Verifies event loop is running and recreates session if needed.
        This prevents "Event loop is closed" errors when the session tries to
        schedule timeout callbacks on a closed loop.
        
        The session is recreated if:
        - It doesn't exist
        - It's closed
        - The current event loop is closed (session's loop may be different/closed)
        """
        # CRITICAL FIX: Verify we're in an async context with a running event loop
        try:
            current_loop = asyncio.get_running_loop()
            if current_loop.is_closed():
                # Current loop is closed - cannot create or use session
                if self._session and not self._session.closed:
                    try:
                        await self._session.close()
                    except Exception:
                        pass  # Ignore errors when closing
                self._session = None
                raise RuntimeError(
                    "Event loop is closed. Cannot create aiohttp.ClientSession. "
                    "This usually indicates the event loop was closed while the IPC client "
                    "was still in use."
                )
        except RuntimeError as e:
            # get_running_loop() raises RuntimeError if not in async context
            if "no running event loop" in str(e).lower():
                raise RuntimeError(
                    "Not in async context. IPCClient methods must be called from an async function."
                ) from e
            raise
        
        # CRITICAL FIX: Recreate session if it's bound to a different or closed loop
        # aiohttp.ClientSession binds to the event loop when created. If the session was
        # created in a different loop (e.g., a previous asyncio.run() call), it cannot be
        # used in the current loop even if the old loop is closed.
        should_recreate = (
            self._session is None
            or self._session.closed
            or self._session_loop is None
            or self._session_loop is not current_loop
            or self._session_loop.is_closed()
        )
        
        if should_recreate:
            # Close existing session if it exists
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                    # CRITICAL FIX: On Windows, wait longer for session cleanup to prevent socket buffer exhaustion
                    import sys
                    if sys.platform == "win32":
                        await asyncio.sleep(0.2)  # Wait for Windows socket cleanup
                        # Also close connector if available
                        if hasattr(self._session, "connector"):
                            connector = self._session.connector
                            if connector and not connector.closed:
                                try:
                                    await connector.close()
                                    await asyncio.sleep(0.1)
                                except Exception:
                                    pass
                except Exception as e:
                    # CRITICAL FIX: Handle WinError 10055 gracefully
                    import sys
                    error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                    if sys.platform == "win32" and error_code == 10055:
                        logger.debug("WinError 10055 during session close (socket buffer exhaustion), continuing...")
                    else:
                        logger.debug("Error closing session: %s", e)
            
            # CRITICAL FIX: Create session in the current running loop context
            # aiohttp.ClientSession will automatically use the current running loop
            # In aiohttp 3.x+, we don't pass loop parameter (it's deprecated)
            # CRITICAL FIX: Add connection limits to prevent Windows socket buffer exhaustion (WinError 10055)
            # Windows has limited socket buffer space, so we need to limit concurrent connections
            import sys
            connector = aiohttp.TCPConnector(
                limit=10,  # Maximum number of connections in the pool
                limit_per_host=5,  # Maximum connections per host
                ttl_dns_cache=300,  # DNS cache TTL
                force_close=True,  # Force close connections after use (helps with Windows)
            )
            if sys.platform == "win32":
                # On Windows, be more aggressive with connection limits to prevent buffer exhaustion
                connector = aiohttp.TCPConnector(
                    limit=5,  # Lower limit on Windows
                    limit_per_host=3,  # Lower per-host limit on Windows
                    ttl_dns_cache=300,
                    force_close=True,
                    enable_cleanup_closed=True,  # Enable cleanup of closed connections
                )
            self._session = aiohttp.ClientSession(timeout=self.timeout, connector=connector)
            self._session_loop = current_loop  # Track the loop this session is bound to
        
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
                logger.debug(_("Failed to sign request with Ed25519: %s"), e)
                # Fall through to API key

        # Fall back to API key if signing failed or key_manager not available
        if not headers.get(SIGNATURE_HEADER) and self.api_key:
            headers[API_KEY_HEADER] = self.api_key

        return headers

    async def _get_json(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        requires_auth: bool = True,
    ) -> Any:
        """Helper to issue authenticated GET requests and return JSON payload."""
        session = await self._ensure_session()
        path = endpoint if endpoint.startswith(API_BASE_PATH) else f"{API_BASE_PATH}{endpoint}"
        url = f"{self.base_url}{path}"
        headers = self._get_headers("GET", path) if requires_auth else None

        async with session.get(url, params=params, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

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
                logger.debug(_("Error closing WebSocket: %s"), e)

        # Close HTTP session
        if self._session:
            try:
                if not self._session.closed:
                    await self._session.close()
                    # CRITICAL: Wait a small amount to ensure session cleanup completes
                    # This prevents "Unclosed client session" warnings on Windows
                    # Increased wait time on Windows for proper cleanup
                    import sys

                    wait_time = 0.5 if sys.platform == "win32" else 0.1  # Increased wait time on Windows
                    await asyncio.sleep(wait_time)
                    
                    # CRITICAL FIX: On Windows, also close the connector to ensure all sockets are released
                    if sys.platform == "win32" and hasattr(self._session, "connector"):
                        connector = self._session.connector
                        if connector and not connector.closed:
                            try:
                                await connector.close()
                                await asyncio.sleep(0.1)  # Additional wait for connector cleanup
                            except Exception:
                                pass  # Ignore errors during connector cleanup
            except Exception as e:
                logger.debug(_("Error closing HTTP session: %s"), e)
            finally:
                # CRITICAL FIX: On Windows, ensure connector is also closed to release all sockets
                import sys
                if sys.platform == "win32" and self._session and hasattr(self._session, "connector"):
                    connector = self._session.connector
                    if connector and not connector.closed:
                        try:
                            await connector.close()
                            await asyncio.sleep(0.1)  # Wait for connector cleanup
                        except Exception:
                            pass  # Ignore errors during connector cleanup
                
                # Ensure session is marked as closed even if close() failed
                self._session = None
                self._session_loop = None

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
            logger.exception("Cannot connect to daemon at %s to add torrent", self.base_url)
            error_msg = (
                f"Cannot connect to daemon at {self.base_url}. "
                "Is the daemon running? Try 'btbt daemon start'"
            )
            raise RuntimeError(error_msg) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            logger.exception("Daemon returned error %d when adding torrent", e.status)
            # Try to get error details from response body if available
            error_msg = e.message
            try:
                # ClientResponseError doesn't have direct access to response
                # but we can use the request_info to get more context
                if hasattr(e, "request_info"):
                    error_msg = f"HTTP {e.status}: {e.message}"
            except Exception:
                pass
            daemon_error_msg = f"Daemon error when adding torrent: {error_msg}"
            raise RuntimeError(daemon_error_msg) from e
        except RuntimeError as e:
            # CRITICAL FIX: Catch "Event loop is closed" errors specifically
            if "event loop is closed" in str(e).lower():
                logger.exception(
                    "Event loop is closed when adding torrent to daemon at %s. "
                    "This usually indicates the event loop was closed while the IPC client was in use.",
                    self.base_url
                )
                error_msg = (
                    f"Event loop is closed. This usually happens when the event loop "
                    f"was closed while communicating with the daemon. "
                    f"Try recreating the IPC client or ensure you're in an async context."
                )
                raise RuntimeError(error_msg) from e
            # Re-raise other RuntimeErrors
            raise
        except aiohttp.ClientError as e:
            # Other client errors
            logger.exception("Client error when adding torrent to daemon at %s", self.base_url)
            error_msg = f"Error communicating with daemon: {e}"
            raise RuntimeError(error_msg) from e

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

    async def restart_torrent(self, info_hash: str) -> bool:
        """Restart torrent (pause + resume).

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if restarted, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/restart"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            data = await resp.json()
            return data.get("status") == "restarted"

    async def cancel_torrent(self, info_hash: str) -> bool:
        """Cancel torrent (pause but keep in session).

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if cancelled, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/cancel"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            data = await resp.json()
            return data.get("status") == "cancelled"

    async def force_start_torrent(self, info_hash: str) -> bool:
        """Force start torrent (bypass queue limits).

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if force started, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/force-start"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            data = await resp.json()
            return data.get("status") == "force_started"

    async def refresh_pex(self, info_hash: str) -> dict[str, Any]:
        """Refresh Peer Exchange (PEX) for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Dictionary with refresh status:
            - success: bool indicating if refresh was successful
            - status: str status message ("refreshed" on success)

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/pex/refresh"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return {"success": False, "error": "Torrent not found or PEX not available"}
            resp.raise_for_status()
            data = await resp.json()
            # Ensure success field is set
            if "success" not in data:
                data["success"] = data.get("status") == "refreshed"
            return data

    async def set_dht_aggressive_mode(self, info_hash: str, enabled: bool = True) -> dict[str, Any]:
        """Set DHT aggressive discovery mode for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            enabled: Whether to enable aggressive mode (default: True)

        Returns:
            Dictionary with update status:
            - success: bool indicating if update was successful
            - status: str status message ("updated" on success)
            - enabled: bool indicating the new state

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/dht/aggressive"

        async with session.post(
            url,
            json={"enabled": enabled},
            headers=self._get_headers(),
        ) as resp:
            if resp.status == 404:
                return {"success": False, "error": "Torrent not found or DHT not available"}
            resp.raise_for_status()
            data = await resp.json()
            # Ensure success field is set
            if "success" not in data:
                data["success"] = data.get("status") == "updated"
            return data

    async def get_metadata_status(self, info_hash: str) -> dict[str, Any]:
        """Get metadata fetch status for magnet link.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Dictionary with metadata status information

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/metadata/status"

        async with session.get(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return {"available": False, "error": "Torrent not found"}
            resp.raise_for_status()
            return await resp.json()

    async def wait_for_metadata(
        self,
        info_hash: str,
        timeout: float = 120.0,
    ) -> bool:
        """Wait for metadata to be ready (for magnet links).

        Args:
            info_hash: Torrent info hash (hex string)
            timeout: Maximum time to wait in seconds

        Returns:
            True if metadata is ready, False if timeout

        """
        # Subscribe to METADATA_READY events
        if not await self.connect_websocket():
            return False

        await self.subscribe_events([EventType.METADATA_READY], info_hash=info_hash)

        end_time = asyncio.get_event_loop().time() + timeout
        try:
            while asyncio.get_event_loop().time() < end_time:
                event = await self.receive_event(timeout=min(1.0, end_time - asyncio.get_event_loop().time()))
                if event and event.type == EventType.METADATA_READY:
                    event_data = event.data or {}
                    if event_data.get("info_hash") == info_hash:
                        return True
        except Exception as e:
            logger.debug(_("Error waiting for metadata: %s"), e)
            return False

        return False

    async def restart_service(self, service_name: str) -> bool:
        """Restart a service component.

        Args:
            service_name: Name of service to restart (e.g., "dht", "nat", "tcp_server")

        Returns:
            True if restarted, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/services/{service_name}/restart"

        async with session.post(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            data = await resp.json()
            return data.get("status") == "restarted"

    async def get_services_status(self) -> dict[str, Any]:
        """Get status of all services.

        Returns:
            Dictionary with service status information

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/services/status"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def batch_pause_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Pause multiple torrents in a single request.

        Args:
            info_hashes: List of torrent info hashes (hex strings)

        Returns:
            Dictionary with results for each torrent

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/batch/pause"

        async with session.post(
            url, json={"info_hashes": info_hashes}, headers=self._get_headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def batch_resume_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Resume multiple torrents in a single request.

        Args:
            info_hashes: List of torrent info hashes (hex strings)

        Returns:
            Dictionary with results for each torrent

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/batch/resume"

        async with session.post(
            url, json={"info_hashes": info_hashes}, headers=self._get_headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def batch_restart_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Restart multiple torrents in a single request.

        Args:
            info_hashes: List of torrent info hashes (hex strings)

        Returns:
            Dictionary with results for each torrent

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/batch/restart"

        async with session.post(
            url, json={"info_hashes": info_hashes}, headers=self._get_headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def batch_remove_torrents(
        self, info_hashes: list[str], remove_data: bool = False
    ) -> dict[str, Any]:
        """Remove multiple torrents in a single request.

        Args:
            info_hashes: List of torrent info hashes (hex strings)
            remove_data: Whether to remove downloaded data (default: False)

        Returns:
            Dictionary with results for each torrent

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/batch/remove"

        async with session.post(
            url,
            json={"info_hashes": info_hashes, "remove_data": remove_data},
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

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
            logger.debug(_("Error sending shutdown request: %s"), e)
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

    # XET Folder Methods

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> dict[str, Any]:
        """Add XET folder for synchronization.

        Args:
            folder_path: Path to folder (or output directory if syncing from tonic)
            tonic_file: Path to .tonic file (optional)
            tonic_link: tonic?: link (optional)
            sync_mode: Synchronization mode (optional)
            source_peers: Designated source peer IDs (optional)
            check_interval: Check interval in seconds (optional)

        Returns:
            Response dict with status and folder_key

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/xet/folders/add"

        payload: dict[str, Any] = {"folder_path": folder_path}
        if tonic_file:
            payload["tonic_file"] = tonic_file
        if tonic_link:
            payload["tonic_link"] = tonic_link
        if sync_mode:
            payload["sync_mode"] = sync_mode
        if source_peers:
            payload["source_peers"] = source_peers
        if check_interval is not None:
            payload["check_interval"] = check_interval

        async with session.post(
            url, json=payload, headers=self._get_headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def remove_xet_folder(self, folder_key: str) -> dict[str, Any]:
        """Remove XET folder from synchronization.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            Response dict with status

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/xet/folders/{folder_key}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_xet_folders(self) -> dict[str, Any]:
        """List all registered XET folders.

        Returns:
            Response dict with folders list

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/xet/folders"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_xet_folder_status(self, folder_key: str) -> dict[str, Any]:
        """Get XET folder status.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            Folder status dict

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/xet/folders/{folder_key}"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

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

    async def get_torrent_trackers(self, info_hash: str) -> TrackerListResponse:
        """Get list of trackers for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Tracker list response

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/trackers"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return TrackerListResponse(**data)

    async def add_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Add a tracker URL to a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            tracker_url: Tracker URL to add

        Returns:
            Dict with success status

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/trackers/add"

        async with session.post(
            url, headers=self._get_headers(), json={"url": tracker_url}
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def remove_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Remove a tracker URL from a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            tracker_url: Tracker URL to remove (URL-encoded)

        Returns:
            Dict with success status

        """
        from urllib.parse import quote

        session = await self._ensure_session()
        # URL-encode the tracker URL for the path
        encoded_url = quote(tracker_url, safe="")
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/trackers/{encoded_url}"

        async with session.delete(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_torrent_piece_availability(self, info_hash: str) -> PieceAvailabilityResponse:
        """Get piece availability for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Piece availability response with availability array

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/piece-availability"

        async with session.get(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return PieceAvailabilityResponse(**data)

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

    async def global_pause_all(self) -> dict[str, Any]:
        """Pause all torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/global/pause-all"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def global_resume_all(self) -> dict[str, Any]:
        """Resume all paused torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/global/resume-all"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def global_force_start_all(self) -> dict[str, Any]:
        """Force start all torrents (bypass queue limits).

        Returns:
            Dict with success_count, failure_count, and results

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/global/force-start-all"

        async with session.post(url, headers=self._get_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits for all torrents.

        Args:
            download_kib: Global download limit (KiB/s, 0 = unlimited)
            upload_kib: Global upload limit (KiB/s, 0 = unlimited)

        Returns:
            True if limits set successfully

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/global/rate-limits"

        async with session.post(
            url,
            headers=self._get_headers(),
            json={"download_kib": download_kib, "upload_kib": upload_kib},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("success", False)

    async def set_per_peer_rate_limit(
        self, info_hash: str, peer_key: str, upload_limit_kib: int
    ) -> bool:
        """Set per-peer upload rate limit for a specific peer.

        Args:
            info_hash: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")
            upload_limit_kib: Upload rate limit (KiB/s, 0 = unlimited)

        Returns:
            True if peer found and limit set, False otherwise

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/peers/{peer_key}/rate-limit"

        # URL-encode the peer_key as it contains colons
        from urllib.parse import quote_plus

        encoded_peer_key = quote_plus(peer_key)
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/peers/{encoded_peer_key}/rate-limit"

        async with session.post(
            url,
            headers=self._get_headers(),
            json={"upload_limit_kib": upload_limit_kib},
        ) as resp:
            if resp.status == 404:
                return False
            resp.raise_for_status()
            data = await resp.json()
            return data.get("success", False)

    async def get_per_peer_rate_limit(
        self, info_hash: str, peer_key: str
    ) -> int | None:
        """Get per-peer upload rate limit for a specific peer.

        Args:
            info_hash: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")

        Returns:
            Upload rate limit in KiB/s (0 = unlimited), or None if peer not found

        """
        session = await self._ensure_session()
        from urllib.parse import quote_plus

        encoded_peer_key = quote_plus(peer_key)
        url = f"{self.base_url}{API_BASE_PATH}/torrents/{info_hash}/peers/{encoded_peer_key}/rate-limit"

        async with session.get(url, headers=self._get_headers()) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            data = await resp.json()
            return data.get("upload_limit_kib")

    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set per-peer upload rate limit for all active peers.

        Args:
            upload_limit_kib: Upload rate limit (KiB/s, 0 = unlimited)

        Returns:
            Number of peers updated

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/peers/rate-limit"

        async with session.post(
            url,
            headers=self._get_headers(),
            json={"upload_limit_kib": upload_limit_kib},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("updated_count", 0)

    async def get_metrics(self) -> str:
        """Get Prometheus metrics from daemon.

        Returns:
            Prometheus format metrics as string

        """
        session = await self._ensure_session()
        url = f"{self.base_url}{API_BASE_PATH}/metrics"

        async with session.get(url) as resp:  # Metrics endpoint doesn't require auth
            resp.raise_for_status()
            return await resp.text()

    async def get_rate_samples(self, seconds: int | None = None) -> RateSamplesResponse:
        """Get recent upload/download rate samples for graphing.

        Args:
            seconds: Optional lookback window in seconds (defaults to server default)

        Returns:
            RateSamplesResponse containing samples and metadata

        """
        params = {"seconds": str(seconds)} if seconds is not None else None
        data = await self._get_json("/metrics/rates", params=params)
        return RateSamplesResponse(**data)

    async def get_disk_io_metrics(self) -> DiskIOMetricsResponse:
        """Get disk I/O metrics from daemon.

        Returns:
            DiskIOMetricsResponse containing disk I/O metrics
        """
        data = await self._get_json("/metrics/disk-io")
        return DiskIOMetricsResponse(**data)

    async def get_network_timing_metrics(self) -> NetworkTimingMetricsResponse:
        """Get network timing metrics from daemon.

        Returns:
            NetworkTimingMetricsResponse containing network timing metrics
        """
        data = await self._get_json("/metrics/network-timing")
        return NetworkTimingMetricsResponse(**data)

    async def get_per_torrent_performance(self, info_hash: str) -> PerTorrentPerformanceResponse:
        """Get per-torrent performance metrics from daemon.

        Args:
            info_hash: Torrent info hash in hex format

        Returns:
            PerTorrentPerformanceResponse containing per-torrent performance metrics
        """
        data = await self._get_json(f"/metrics/torrents/{info_hash}/performance")
        return PerTorrentPerformanceResponse(**data)

    async def get_peer_metrics(self) -> GlobalPeerMetricsResponse:
        """Get global peer metrics across all torrents.

        Returns:
            GlobalPeerMetricsResponse containing peer metrics
        """
        data = await self._get_json("/metrics/peers")
        return GlobalPeerMetricsResponse(**data)

    async def get_torrent_dht_metrics(
        self,
        info_hash: str,
    ) -> DHTQueryMetricsResponse | None:
        """Get DHT query effectiveness metrics for a torrent."""
        try:
            data = await self._get_json(f"/metrics/torrents/{info_hash}/dht")
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                return None
            raise
        return DHTQueryMetricsResponse(**data)

    async def get_torrent_peer_quality(
        self,
        info_hash: str,
    ) -> PeerQualityMetricsResponse | None:
        """Get peer quality metrics for a torrent."""
        try:
            data = await self._get_json(f"/metrics/torrents/{info_hash}/peer-quality")
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                return None
            raise
        return PeerQualityMetricsResponse(**data)

    async def get_torrent_piece_selection_metrics(
        self,
        info_hash: str,
    ) -> dict[str, Any]:
        """Get piece selection metrics for a torrent."""
        try:
            return await self._get_json(
                f"/metrics/torrents/{info_hash}/piece-selection",
            )
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                return {}
            raise

    async def get_detailed_torrent_metrics(
        self,
        info_hash: str,
    ) -> DetailedTorrentMetricsResponse:
        """Get detailed metrics for a specific torrent.
        
        Args:
            info_hash: Torrent info hash (hex string)
            
        Returns:
            DetailedTorrentMetricsResponse with comprehensive torrent metrics
            
        Raises:
            aiohttp.ClientResponseError: If request fails or torrent not found
        """
        data = await self._get_json(f"/metrics/torrents/{info_hash}/detailed")
        return DetailedTorrentMetricsResponse(**data)

    async def get_detailed_global_metrics(
        self,
    ) -> DetailedGlobalMetricsResponse:
        """Get detailed global metrics across all torrents.
        
        Returns:
            DetailedGlobalMetricsResponse with comprehensive global metrics
            
        Raises:
            aiohttp.ClientResponseError: If request fails
        """
        data = await self._get_json("/metrics/global/detailed")
        return DetailedGlobalMetricsResponse(**data)

    async def get_detailed_peer_metrics(
        self,
        peer_key: str,
    ) -> DetailedPeerMetricsResponse:
        """Get detailed metrics for a specific peer.
        
        Args:
            peer_key: Peer identifier (hex string)
            
        Returns:
            DetailedPeerMetricsResponse with comprehensive peer metrics
            
        Raises:
            aiohttp.ClientResponseError: If request fails or peer not found
        """
        data = await self._get_json(f"/metrics/peers/{peer_key}")
        return DetailedPeerMetricsResponse(**data)

    async def get_aggressive_discovery_status(
        self,
        info_hash: str,
    ) -> AggressiveDiscoveryStatusResponse:
        """Get aggressive discovery status for a torrent.
        
        Args:
            info_hash: Torrent info hash (hex string)
            
        Returns:
            AggressiveDiscoveryStatusResponse with aggressive discovery status
            
        Raises:
            aiohttp.ClientResponseError: If request fails or torrent not found
        """
        data = await self._get_json(
            f"/metrics/torrents/{info_hash}/aggressive-discovery",
        )
        return AggressiveDiscoveryStatusResponse(**data)

    async def get_swarm_health_matrix(
        self,
        limit: int = 6,
        seconds: int | None = None,
    ) -> SwarmHealthMatrixResponse:
        """Get swarm health matrix combining performance, peer, and piece metrics.
        
        Aggregates data from multiple endpoints to provide a comprehensive
        view of swarm health across all torrents with historical samples.
        
        Args:
            limit: Maximum number of torrents to include (default: 6)
            seconds: Optional lookback window in seconds for historical samples
            
        Returns:
            SwarmHealthMatrixResponse containing samples and metadata
        """
        params: dict[str, Any] = {"limit": str(limit)}
        if seconds is not None:
            params["seconds"] = str(seconds)
        
        try:
            data = await self._get_json("/metrics/swarm-health", params=params)
            return SwarmHealthMatrixResponse(**data)
        except aiohttp.ClientResponseError as exc:
            # If endpoint doesn't exist yet, construct response from individual endpoints
            if exc.status == 404:
                # Fallback: construct from individual endpoints
                torrents = await self.list_torrents()
                if not torrents:
                    return SwarmHealthMatrixResponse(samples=[], sample_count=0)
                
                # Get top torrents by download rate
                top_torrents = sorted(
                    torrents,
                    key=lambda t: float(t.download_rate if hasattr(t, 'download_rate') else t.get('download_rate', 0.0)),
                    reverse=True,
                )[:limit]
                
                samples = []
                import time
                current_time = time.time()
                
                for torrent in top_torrents:
                    info_hash = torrent.info_hash if hasattr(torrent, 'info_hash') else torrent.get('info_hash')
                    if not info_hash:
                        continue
                    
                    try:
                        perf = await self.get_per_torrent_performance(info_hash)
                        samples.append({
                            "info_hash": info_hash,
                            "name": torrent.name if hasattr(torrent, 'name') else torrent.get('name', info_hash[:16]),
                            "timestamp": current_time,
                            "swarm_availability": float(perf.swarm_availability),
                            "download_rate": float(perf.download_rate),
                            "upload_rate": float(perf.upload_rate),
                            "connected_peers": int(perf.connected_peers),
                            "active_peers": int(perf.active_peers),
                            "progress": float(perf.progress),
                        })
                    except Exception:
                        continue
                
                # Calculate rarity percentiles
                availabilities = [s["swarm_availability"] for s in samples]
                availabilities.sort()
                n = len(availabilities)
                percentiles = {}
                if n > 0:
                    percentiles["p25"] = availabilities[n // 4] if n >= 4 else availabilities[0]
                    percentiles["p50"] = availabilities[n // 2] if n >= 2 else availabilities[0]
                    percentiles["p75"] = availabilities[3 * n // 4] if n >= 4 else availabilities[-1]
                    percentiles["p90"] = availabilities[9 * n // 10] if n >= 10 else availabilities[-1]
                
                return SwarmHealthMatrixResponse(
                    samples=samples,
                    sample_count=len(samples),
                    rarity_percentiles=percentiles,
                )
            raise

    # WebSocket Methods

    async def connect_websocket(self) -> bool:
        """Establish WebSocket connection.

        Returns:
            True if connected, False otherwise

        """
        if not self.api_key and not self.key_manager:
            logger.error(
                _("API key or Ed25519 key manager required for WebSocket connection")
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
                    logger.debug(_("Failed to sign WebSocket request: %s"), e)
                    # Fall through to API key
                    if self.api_key:
                        ws_url = f"{ws_url}{ws_path}?api_key={self.api_key}"
            else:
                ws_url = f"{ws_url}{ws_path}?api_key={self.api_key}"

            self._websocket = await session.ws_connect(ws_url)

            # Start receive task
            self._websocket_task = asyncio.create_task(self._websocket_receive_loop())

            return True
        except Exception:
            logger.exception("Error connecting WebSocket")
            return False

    async def subscribe_events(
        self,
        event_types: list[EventType] | None = None,
        info_hash: str | None = None,
        priority_filter: str | None = None,
        rate_limit: float | None = None,
    ) -> bool:
        """Subscribe to event types with optional filtering.

        Args:
            event_types: List of event types to subscribe to (None = all events)
            info_hash: Filter events to specific torrent (optional)
            priority_filter: Filter by priority: 'critical', 'high', 'normal', 'low' (optional)
            rate_limit: Maximum events per second (throttling, optional)

        Returns:
            True if subscribed, False otherwise

        """
        if (not self._websocket or self._websocket.closed) and not await self.connect_websocket():
            return False

        try:
            req = WebSocketSubscribeRequest(
                event_types=event_types or [],
                info_hash=info_hash,
                priority_filter=priority_filter,
                rate_limit=rate_limit,
            )
            message = WebSocketMessage(action="subscribe", data=req.model_dump())

            if self._websocket and not self._websocket.closed:
                await self._websocket.send_json(message.model_dump())
                return True
            return False
        except Exception:
            logger.exception("Error subscribing to events")
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
            logger.debug(_("Error receiving WebSocket event: %s"), e)
            return None

    async def receive_events_batch(
        self,
        timeout: float = 1.0,
        max_events: int = 10,
    ) -> list[WebSocketEvent]:
        """Receive multiple events in one call.

        Args:
            timeout: Timeout in seconds
            max_events: Maximum number of events to collect

        Returns:
            List of WebSocket events (may be empty if timeout)

        """
        events: list[WebSocketEvent] = []
        if not self._websocket or self._websocket.closed:
            return events

        end_time = asyncio.get_event_loop().time() + timeout
        try:
            while len(events) < max_events:
                remaining_time = end_time - asyncio.get_event_loop().time()
                if remaining_time <= 0:
                    break

                msg = await asyncio.wait_for(
                    self._websocket.receive(),
                    timeout=min(remaining_time, 0.1),
                )

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if "type" in data and "timestamp" in data:
                        events.append(WebSocketEvent(**data))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.warning(_("WebSocket error in batch receive: %s"), self._websocket.exception())
                    break
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(_("Error receiving WebSocket events batch: %s"), e)

        return events

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
                    logger.warning(_("WebSocket error: %s"), self._websocket.exception())
                    break
        except Exception as e:
            logger.debug(_("WebSocket receive loop error: %s"), e)
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
                            _("Socket test returned 10035 (WSAEWOULDBLOCK) on Windows for %s:%d. "
                            "This may be a false positive - proceeding with HTTP check."),
                            host,
                            port,
                        )
                        # Don't return False - continue to HTTP check
                    else:
                        logger.debug(
                            _("Socket connection test to %s:%d failed (result=%d). "
                            "Port may not be open or firewall blocking. Proceeding with HTTP check anyway."),
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
            logger.debug(_("Error in socket pre-check: %s"), test_error)
            # Continue with HTTP check anyway

        try:
            # Use a shorter timeout for the status check to avoid long waits
            # The caller will handle retries with exponential backoff
            status = await asyncio.wait_for(self.get_status(), timeout=3.0)
            # Verify we got a valid status response
            return status is not None and hasattr(status, "status")
        except asyncio.TimeoutError:
            logger.debug(
                _("Timeout checking daemon status at %s (daemon may be starting up or overloaded)"),
                self.base_url,
            )
            return False
        except aiohttp.ClientConnectorError as e:
            # Connection refused or similar - daemon is not running or not accessible
            # Log at INFO level when daemon config file doesn't exist (helps diagnose port issues)
            log_level = logger.info if "Cannot connect" in str(e) else logger.debug
            log_level(
                _("Cannot connect to daemon at %s: %s (daemon may not be running or IPC server not started)"),
                self.base_url,
                e,
            )
            return False
        except aiohttp.ClientResponseError as e:
            # HTTP error response (401, 403, 404, 500, etc.)
            # 401/403 usually means API key mismatch
            if e.status in (401, 403):
                logger.warning(
                    _("Authentication failed when checking daemon status at %s (status %d). "
                      "This usually indicates an API key mismatch. "
                      "Check that the API key in config matches the daemon's API key."),
                    self.base_url,
                    e.status,
                )
            else:
                logger.debug(
                    _("HTTP error checking daemon status at %s: %s (status %d)"),
                    self.base_url,
                    e.message,
                    e.status,
                )
            return False
        except aiohttp.ClientError as e:
            # Other client errors (HTTP errors, etc.)
            logger.debug(
                _("Client error checking daemon status at %s: %s (daemon may be starting up)"),
                self.base_url,
                e,
            )
            return False
        except Exception as e:
            # Unexpected errors
            logger.debug(
                _("Unexpected error checking daemon status at %s: %s"),
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
        # CRITICAL FIX: Use consistent path resolution helper to match daemon
        from ccbt.daemon.daemon_manager import _get_daemon_home_dir
        home_dir = _get_daemon_home_dir()
        pid_file = home_dir / ".ccbt" / "daemon" / "daemon.pid"
        logger.debug(_("IPCClient.get_daemon_pid: Checking pid_file=%s (home_dir=%s, exists=%s)"), pid_file, home_dir, pid_file.exists())
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
                    logger.debug(_("Error reading PID file after retries: %s"), e)
                    return None

            if not pid_text:
                # Empty file - remove it
                logger.debug(_("PID file is empty, removing"))
                with contextlib.suppress(OSError):
                    pid_file.unlink()
                return None

            # Validate PID format
            pid_text = pid_text.strip()
            if not pid_text or not pid_text.isdigit():
                logger.warning(
                    _("PID file contains invalid data: %r, removing"), pid_text[:50]
                )
                with contextlib.suppress(OSError):
                    pid_file.unlink()
                return None

            pid = int(pid_text)

            # Validate PID is reasonable
            if pid <= 0 or pid > 2147483647:
                logger.warning(_("PID file contains invalid PID: %d, removing"), pid)
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
            logger.debug(_("Error reading PID file: %s"), e)
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
            logger.debug(_("Could not read daemon config from ConfigManager: %s"), e)

        # Fallback: Try to read from legacy config file (for backwards compatibility)
        # CRITICAL FIX: Use consistent path resolution helper to match daemon
        from ccbt.daemon.daemon_manager import _get_daemon_home_dir
        home_dir = _get_daemon_home_dir()
        config_file = home_dir / ".ccbt" / "daemon" / "config.json"
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
