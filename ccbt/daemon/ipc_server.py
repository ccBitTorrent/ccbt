"""IPC server for daemon communication.

from __future__ import annotations

Provides HTTP REST API and WebSocket endpoints for CLI-daemon communication
with mandatory authentication.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import ssl
import sys
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import web

try:
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )
except ImportError:
    Encoding = None  # type: ignore[assignment, misc]
    NoEncryption = None  # type: ignore[assignment, misc]
    PrivateFormat = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from aiohttp.web_request import Request
    from aiohttp.web_response import Response
    from aiohttp.web_ws import WebSocketResponse
else:
    # Type stubs for runtime
    WebSocketResponse = web.WebSocketResponse  # type: ignore[attr-defined]

from ccbt.daemon.ipc_protocol import (
    API_BASE_PATH,
    API_KEY_HEADER,
    PUBLIC_KEY_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    BlacklistAddRequest,
    BlacklistResponse,
    ErrorResponse,
    EventType,
    ExportStateRequest,
    ExternalIPResponse,
    ExternalPortResponse,
    FilePriorityRequest,
    FileSelectRequest,
    GlobalStatsResponse,
    ImportStateRequest,
    IPFilterStatsResponse,
    NATMapRequest,
    PeerListResponse,
    QueueAddRequest,
    QueueMoveRequest,
    RateLimitRequest,
    ResumeCheckpointRequest,
    ScrapeRequest,
    StatusResponse,
    TorrentAddRequest,
    TorrentListResponse,
    WebSocketEvent,
    WebSocketMessage,
    WebSocketSubscribeRequest,
    WhitelistAddRequest,
    WhitelistResponse,
)

logger = logging.getLogger(__name__)


class IPCServer:
    """IPC server for daemon communication via HTTP REST and WebSocket."""

    def __init__(
        self,
        session_manager: Any,  # AsyncSessionManager
        api_key: str,
        key_manager: Any = None,  # Ed25519KeyManager
        host: str = "127.0.0.1",
        port: int = 8080,
        websocket_enabled: bool = True,
        websocket_heartbeat_interval: float = 30.0,
        tls_enabled: bool = False,
    ):
        """Initialize IPC server.

        Args:
            session_manager: AsyncSessionManager instance
            api_key: API key for authentication (required)
            key_manager: Optional Ed25519KeyManager for cryptographic authentication
            host: Host to bind to (default: 127.0.0.1 for local-only access, 0.0.0.0 for all interfaces)
            port: Port to bind to (default: 8080)
            websocket_enabled: Enable WebSocket support
            websocket_heartbeat_interval: WebSocket heartbeat interval in seconds
            tls_enabled: Enable TLS/HTTPS (requires key_manager)

        """
        self.session_manager = session_manager
        # CRITICAL FIX: Use ExecutorManager to get executor
        # This ensures we use the same executor instance initialized at daemon startup
        # which has access to all initialized components (UDP tracker, DHT, etc.)
        # ExecutorManager ensures single executor instance per session manager
        try:
            from ccbt.executor.manager import ExecutorManager

            executor_manager = ExecutorManager.get_instance()
            self.executor = executor_manager.get_executor(session_manager=session_manager)
            logger.debug(
                "Using executor from ExecutorManager (type: %s)",
                type(self.executor).__name__,
            )
        except Exception as e:
            logger.error(
                "Failed to get executor from ExecutorManager: %s. "
                "This may indicate initialization order issues.",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Failed to get executor: {e}") from e

        # CRITICAL FIX: Verify executor is ready
        # The executor should have access to session_manager and all required components
        if not hasattr(self.executor, "adapter") or self.executor.adapter is None:
            raise RuntimeError("Executor adapter not initialized")
        if (
            not hasattr(self.executor.adapter, "session_manager")
            or self.executor.adapter.session_manager is None
        ):
            raise RuntimeError("Executor session_manager not initialized")
        if self.executor.adapter.session_manager is not session_manager:
            raise RuntimeError("Executor session_manager reference mismatch")
        self.api_key = api_key
        self.key_manager = key_manager
        self.tls_enabled = tls_enabled
        self.host = host
        self.port = port
        self.websocket_enabled = websocket_enabled
        self.websocket_heartbeat_interval = websocket_heartbeat_interval

        self.app = web.Application()  # type: ignore[attr-defined]
        self.runner: web.AppRunner | None = None  # type: ignore[attr-defined]
        self.site: web.TCPSite | None = None  # type: ignore[attr-defined]
        self._start_time = time.time()

        # WebSocket connections
        self._websocket_connections: set[web.WebSocketResponse] = set()  # type: ignore[attr-defined]
        self._websocket_subscriptions: dict[web.WebSocketResponse, set[EventType]] = {}  # type: ignore[attr-defined]
        self._websocket_heartbeat_tasks: dict[web.WebSocketResponse, asyncio.Task] = {}  # type: ignore[attr-defined]

        # Setup routes and middleware
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """Set up middleware for authentication and error handling."""

        # Authentication middleware (applies to all routes)
        @web.middleware  # type: ignore[attr-defined]
        async def auth_middleware(request: Request, handler: Any) -> Response:
            """Mandatory authentication middleware."""
            try:
                # Skip authentication for WebSocket upgrade requests (handled separately)
                if (
                    request.path == f"{API_BASE_PATH}/events"
                    and request.method == "GET"
                ):
                    return await handler(request)

                # Skip authentication for metrics endpoint (Prometheus standard)
                if (
                    request.path == f"{API_BASE_PATH}/metrics"
                    and request.method == "GET"
                ):
                    return await handler(request)

                # Try Ed25519 signature authentication first (if key_manager available)
                authenticated = False
                # Defensive check: ensure key_manager exists and has required methods
                # Use try/except to handle any AttributeError from accessing key_manager
                try:
                    if self.key_manager is not None and hasattr(
                        self.key_manager, "verify_signature"
                    ):
                        signature = request.headers.get(SIGNATURE_HEADER)
                        public_key_hex = request.headers.get(PUBLIC_KEY_HEADER)
                        timestamp_str = request.headers.get(TIMESTAMP_HEADER)

                        if signature and public_key_hex and timestamp_str:
                            try:
                                # Verify timestamp (5-minute window)
                                import time

                                timestamp = float(timestamp_str)
                                current_time = time.time()
                                if abs(current_time - timestamp) > 300:  # 5 minutes
                                    logger.warning(
                                        "Request timestamp out of window: %s",
                                        request.remote,
                                    )
                                else:
                                    # Reconstruct signed message
                                    # For GET requests, body is empty. For POST/PUT with body,
                                    # we skip Ed25519 verification to avoid body consumption issues.
                                    # Ed25519 verification is primarily for GET requests.
                                    body = b""
                                    if request.method == "GET" or (
                                        request.content_length == 0
                                    ):
                                        # GET requests or requests with no body - safe to verify
                                        try:
                                            body_hash = hashlib.sha256(body).hexdigest()
                                            message = f"{request.method} {request.path}\n{timestamp}\n{body_hash}".encode()

                                            # Verify signature - handle invalid hex strings gracefully
                                            try:
                                                public_key_bytes = bytes.fromhex(
                                                    public_key_hex
                                                )
                                                signature_bytes = bytes.fromhex(
                                                    signature
                                                )
                                            except ValueError as hex_error:
                                                logger.debug(
                                                    "Invalid hex string in Ed25519 headers from %s: %s",
                                                    request.remote,
                                                    hex_error,
                                                )
                                                # Fall through to API key authentication
                                            else:
                                                # Only verify if hex conversion succeeded
                                                if self.key_manager.verify_signature(
                                                    message,
                                                    signature_bytes,
                                                    public_key_bytes,
                                                ):
                                                    authenticated = True
                                                else:
                                                    logger.warning(
                                                        "Invalid Ed25519 signature from %s",
                                                        request.remote,
                                                    )
                                        except Exception as verify_error:
                                            logger.debug(
                                                "Ed25519 signature verification error: %s",
                                                verify_error,
                                            )
                                            # Fall through to API key authentication
                                    else:
                                        # POST/PUT with body - skip Ed25519 verification to avoid body consumption
                                        # Fall through to API key authentication
                                        logger.debug(
                                            "Skipping Ed25519 verification for %s request with body (use API key)",
                                            request.method,
                                        )
                            except Exception as e:
                                logger.debug("Ed25519 authentication error: %s", e)
                except (AttributeError, TypeError) as e:
                    # Handle case where key_manager is in invalid state
                    logger.debug("Error accessing key_manager for Ed25519 auth: %s", e)
                    # Fall through to API key authentication

                # Fall back to API key authentication
                if not authenticated:
                    api_key = request.headers.get(API_KEY_HEADER)
                    if api_key and api_key == self.api_key:
                        authenticated = True

                if not authenticated:
                    logger.warning(
                        "Unauthorized request from %s to %s",
                        request.remote,
                        request.path,
                    )
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Unauthorized",
                            code="AUTH_REQUIRED",
                            details={
                                "message": "API key or Ed25519 signature required"
                            },
                        ).model_dump(),
                        status=401,
                    )

                return await handler(request)
            except Exception as auth_error:
                # Catch any exceptions in auth middleware to prevent daemon crash
                logger.exception(
                    "Error in authentication middleware: %s",
                    auth_error,
                )
                # Fall back to allowing the request through (will be caught by error middleware)
                # Or return unauthorized if we can't authenticate
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Authentication error",
                        code="AUTH_ERROR",
                        details={"message": str(auth_error)},
                    ).model_dump(),
                    status=500,
                )

        self.app.middlewares.append(auth_middleware)

        # Error handling middleware
        @web.middleware  # type: ignore[attr-defined]
        async def error_middleware(request: Request, handler: Any) -> Response:
            """Error handling middleware."""
            try:
                return await handler(request)
            except asyncio.CancelledError:
                # Don't log cancelled errors - they're expected during shutdown
                raise
            except Exception as e:
                # Log all exceptions with full context
                # This catches all exceptions including HTTP exceptions from aiohttp
                # We handle them all here to ensure the server never crashes
                logger.exception(
                    "Error handling request %s %s from %s: %s",
                    request.method,
                    request.path,
                    request.remote,
                    e,
                )
                # Return error response - never let exceptions crash the server
                try:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=str(e),
                            code="INTERNAL_ERROR",
                        ).model_dump(),
                        status=500,
                    )
                except Exception as response_error:
                    # Even error response creation failed - log and return minimal response
                    logger.critical(
                        "Failed to create error response: %s (original error: %s)",
                        response_error,
                        e,
                    )
                    # Return a minimal error response
                    return web.Response(  # type: ignore[attr-defined]
                        text="Internal Server Error",
                        status=500,
                        content_type="text/plain",
                    )

        self.app.middlewares.append(error_middleware)

    def _setup_routes(self) -> None:
        """Set up HTTP REST and WebSocket routes."""
        # Status endpoint
        self.app.router.add_get(f"{API_BASE_PATH}/status", self._handle_status)

        # Metrics endpoint (Prometheus format)
        self.app.router.add_get(f"{API_BASE_PATH}/metrics", self._handle_metrics)

        # Torrent management endpoints
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/add",
            self._handle_add_torrent,
        )
        self.app.router.add_delete(
            f"{API_BASE_PATH}/torrents/{{info_hash}}",
            self._handle_remove_torrent,
        )
        self.app.router.add_get(f"{API_BASE_PATH}/torrents", self._handle_list_torrents)
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}",
            self._handle_get_torrent_status,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/pause",
            self._handle_pause_torrent,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/resume",
            self._handle_resume_torrent,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/peers",
            self._handle_get_torrent_peers,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/rate-limits",
            self._handle_set_rate_limits,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/announce",
            self._handle_force_announce,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/export-state",
            self._handle_export_session_state,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/import-state",
            self._handle_import_session_state,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/resume-checkpoint",
            self._handle_resume_from_checkpoint,
        )

        # Config endpoints
        self.app.router.add_get(f"{API_BASE_PATH}/config", self._handle_get_config)
        self.app.router.add_put(f"{API_BASE_PATH}/config", self._handle_update_config)

        # Shutdown endpoint
        self.app.router.add_post(f"{API_BASE_PATH}/shutdown", self._handle_shutdown)

        # File selection endpoints
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/files",
            self._handle_get_torrent_files,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/files/select",
            self._handle_select_files,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/files/deselect",
            self._handle_deselect_files,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/files/priority",
            self._handle_set_file_priority,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/files/verify",
            self._handle_verify_files,
        )

        # Queue endpoints
        self.app.router.add_get(f"{API_BASE_PATH}/queue", self._handle_get_queue)
        self.app.router.add_post(f"{API_BASE_PATH}/queue/add", self._handle_queue_add)
        self.app.router.add_delete(
            f"{API_BASE_PATH}/queue/{{info_hash}}",
            self._handle_queue_remove,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/queue/{{info_hash}}/move",
            self._handle_queue_move,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/queue/clear", self._handle_queue_clear
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/queue/{{info_hash}}/pause",
            self._handle_queue_pause,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/queue/{{info_hash}}/resume",
            self._handle_queue_resume,
        )

        # NAT endpoints
        self.app.router.add_get(f"{API_BASE_PATH}/nat/status", self._handle_nat_status)
        self.app.router.add_post(
            f"{API_BASE_PATH}/nat/discover", self._handle_nat_discover
        )
        self.app.router.add_post(f"{API_BASE_PATH}/nat/map", self._handle_nat_map)
        self.app.router.add_post(f"{API_BASE_PATH}/nat/unmap", self._handle_nat_unmap)
        self.app.router.add_post(
            f"{API_BASE_PATH}/nat/refresh", self._handle_nat_refresh
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/nat/external-ip", self._handle_get_external_ip
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/nat/external-port/{{internal_port}}",
            self._handle_get_external_port,
        )

        # Scrape endpoints
        self.app.router.add_post(
            f"{API_BASE_PATH}/scrape/{{info_hash}}",
            self._handle_scrape,
        )
        self.app.router.add_get(f"{API_BASE_PATH}/scrape", self._handle_list_scrape)
        self.app.router.add_get(
            f"{API_BASE_PATH}/scrape/{{info_hash}}",
            self._handle_get_scrape_result,
        )

        # Session endpoints
        self.app.router.add_get(
            f"{API_BASE_PATH}/session/stats", self._handle_get_global_stats
        )

        # Protocol endpoints
        self.app.router.add_get(
            f"{API_BASE_PATH}/protocols/xet", self._handle_get_xet_protocol
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/protocols/ipfs", self._handle_get_ipfs_protocol
        )

        # Security endpoints
        self.app.router.add_get(
            f"{API_BASE_PATH}/security/blacklist", self._handle_get_blacklist
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/security/whitelist", self._handle_get_whitelist
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/security/blacklist", self._handle_add_to_blacklist
        )
        self.app.router.add_delete(
            f"{API_BASE_PATH}/security/blacklist/{{ip}}",
            self._handle_remove_from_blacklist,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/security/whitelist", self._handle_add_to_whitelist
        )
        self.app.router.add_delete(
            f"{API_BASE_PATH}/security/whitelist/{{ip}}",
            self._handle_remove_from_whitelist,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/security/ip-filter/load",
            self._handle_load_ip_filter,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/security/ip-filter/stats",
            self._handle_get_ip_filter_stats,
        )

        # WebSocket endpoint
        if self.websocket_enabled:
            self.app.router.add_get(
                f"{API_BASE_PATH}/events",
                self._handle_websocket,
            )

    # HTTP REST Handlers

    def _get_package_version(self) -> str:
        """Get package version from ccbt module.

        Returns:
            Package version string (e.g., "0.1.0")

        """
        try:
            import ccbt

            return getattr(ccbt, "__version__", "0.1.0")
        except ImportError:
            # Fallback if ccbt module not available
            return "0.1.0"

    async def _handle_status(self, _request: Request) -> Response:
        """Handle GET /api/v1/status."""
        uptime = time.time() - self._start_time
        pid = os.getpid()

        # Get global stats
        global_stats = await self.session_manager.get_global_stats()

        status = StatusResponse(
            status="running",
            pid=pid,
            uptime=uptime,
            version=self._get_package_version(),
            num_torrents=global_stats.get("num_torrents", 0),
            ipc_url=f"http://{self.host}:{self.port}",
        )

        return web.json_response(status.model_dump())  # type: ignore[attr-defined]

    async def _handle_metrics(self, _request: Request) -> Response:
        """Handle GET /api/v1/metrics - Prometheus metrics endpoint."""
        from ccbt.monitoring import get_metrics_collector

        try:
            metrics_collector = get_metrics_collector()
            if not metrics_collector or not metrics_collector.running:
                return web.Response(  # type: ignore[attr-defined]
                    text="# Metrics collection not enabled\n",
                    content_type="text/plain; version=0.0.4",
                    status=503,
                )

            # Export Prometheus format
            prometheus_data = metrics_collector._export_prometheus_format()  # noqa: SLF001

            return web.Response(  # type: ignore[attr-defined]
                text=prometheus_data,
                content_type="text/plain; version=0.0.4",
                charset="utf-8",
            )
        except Exception as e:
            logger.exception("Error exporting metrics")
            return web.Response(  # type: ignore[attr-defined]
                text=f"# Error exporting metrics: {e}\n",
                content_type="text/plain",
                status=500,
            )

    async def _handle_add_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/add."""
        info_hash_hex: str | None = None
        path_or_magnet: str = "unknown"
        try:
            # Parse JSON request body with error handling
            try:
                data = await request.json()
            except ValueError as json_error:
                logger.warning(
                    "Invalid JSON in add_torrent request from %s: %s",
                    request.remote,
                    json_error,
                )
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"Invalid JSON: {json_error}",
                        code="INVALID_JSON",
                    ).model_dump(),
                    status=400,
                )
            except Exception as json_error:
                logger.exception(
                    "Error parsing JSON in add_torrent request from %s: %s",
                    request.remote,
                    json_error,
                )
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"Error parsing request: {json_error}",
                        code="PARSE_ERROR",
                    ).model_dump(),
                    status=400,
                )

            # Validate request data
            try:
                req = TorrentAddRequest(**data)
                path_or_magnet = req.path_or_magnet
            except Exception as validation_error:
                logger.warning(
                    "Invalid request data in add_torrent from %s: %s",
                    request.remote,
                    validation_error,
                )
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"Invalid request data: {validation_error}",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )

            # CRITICAL FIX: Use executor pattern for consistency with all other handlers
            # Add timeout protection for add operations
            # This prevents the request from hanging indefinitely if something goes wrong
            # The timeout is generous (120s for magnets) to allow for metadata exchange
            try:
                # Use executor to add torrent/magnet (consistent with all other handlers)
                # CRITICAL FIX: Increase timeout for magnets to allow metadata exchange
                # Magnet links need time to fetch metadata from peers, which can take 30-120s
                timeout = 120.0 if req.path_or_magnet.startswith("magnet:") else 60.0

                # CRITICAL FIX: Wrap executor.execute in additional try-except to catch any
                # unexpected exceptions that might not be caught by the executor itself
                try:
                    result = await asyncio.wait_for(
                        self.executor.execute(
                            "torrent.add",
                            path_or_magnet=req.path_or_magnet,
                            output_dir=req.output_dir,
                            resume=req.resume,
                        ),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Timeout adding torrent/magnet: %s (operation took >%.0fs)",
                        req.path_or_magnet[:100],
                        timeout,
                    )
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=f"Operation timed out after {timeout:.0f}s - torrent may still be processing in background",
                            code="ADD_TORRENT_TIMEOUT",
                        ).model_dump(),
                        status=408,  # Request Timeout
                    )
                except Exception as executor_error:
                    # Log the full exception with context
                    logger.exception(
                        "Error in executor.execute() for torrent/magnet %s: %s",
                        req.path_or_magnet[:100],
                        executor_error,
                    )
                    # Return error response directly instead of re-raising
                    # This prevents the exception from propagating and potentially crashing the daemon
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=str(executor_error) or "Failed to add torrent",
                            code="ADD_TORRENT_ERROR",
                        ).model_dump(),
                        status=500,
                    )

                if not result.success:
                    logger.warning(
                        "Executor returned failure for torrent/magnet %s: %s",
                        req.path_or_magnet[:100],
                        result.error,
                    )
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=result.error or "Failed to add torrent",
                            code="ADD_TORRENT_ERROR",
                        ).model_dump(),
                        status=400,
                    )

                info_hash_hex = result.data.get("info_hash") if result.data else None
                if not info_hash_hex:
                    logger.warning(
                        "Executor returned success but no info_hash for torrent/magnet %s",
                        req.path_or_magnet[:100],
                    )
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent was not added (info_hash is None)",
                            code="ADD_TORRENT_ERROR",
                        ).model_dump(),
                        status=400,
                    )
            except Exception as add_error:
                # Catch any other unexpected errors (shouldn't happen due to inner try-except)
                # But this is a safety net to ensure the daemon never crashes
                logger.exception(
                    "Unexpected error in _handle_add_torrent for %s: %s",
                    req.path_or_magnet[:100] if "req" in locals() else "unknown",
                    add_error,
                )
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=str(add_error) or "Failed to add torrent",
                        code="ADD_TORRENT_ERROR",
                    ).model_dump(),
                    status=500,
                )

            # CRITICAL FIX: Emit WebSocket event with error isolation
            # WebSocket errors should not prevent the torrent from being added
            # If the torrent was successfully added, return success even if WebSocket fails
            try:
                await self._emit_websocket_event(
                    EventType.TORRENT_ADDED,
                    {"info_hash": info_hash_hex, "name": req.path_or_magnet},
                )
            except Exception as ws_error:
                # Log WebSocket error but don't fail the request
                # The torrent was already added successfully
                logger.warning(
                    "Failed to emit WebSocket event for added torrent %s: %s",
                    info_hash_hex,
                    ws_error,
                    exc_info=ws_error,
                )

            # Return success if torrent was added (even if WebSocket event failed)
            # CRITICAL FIX: This check should never be reached if the inner try-except
            # handled the case correctly, but we include it as a safety net
            if info_hash_hex:
                return web.json_response(
                    {"info_hash": info_hash_hex, "status": "added"}
                )  # type: ignore[attr-defined]
            # This should never happen due to the check at lines 672-684, but handle it gracefully
            logger.error(
                "Torrent was not added (info_hash is None) - this should not happen",
            )
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Torrent was not added (info_hash is None)",
                    code="ADD_TORRENT_ERROR",
                ).model_dump(),
                status=500,
            )

        except Exception as e:
            # Log the full exception with context for debugging
            logger.exception(
                "Error adding torrent/magnet %s: %s",
                path_or_magnet[:100] if path_or_magnet != "unknown" else "unknown",
                e,
            )
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(error=str(e), code="ADD_TORRENT_ERROR").model_dump(),
                status=400,
            )

    async def _handle_remove_torrent(self, request: Request) -> Response:
        """Handle DELETE /api/v1/torrents/{info_hash}."""
        info_hash = request.match_info["info_hash"]

        try:
            result = await self.executor.execute("torrent.remove", info_hash=info_hash)

            if result.success and result.data.get("removed"):
                # Emit WebSocket event with error isolation
                try:
                    await self._emit_websocket_event(
                        EventType.TORRENT_REMOVED,
                        {"info_hash": info_hash},
                    )
                except Exception as ws_error:
                    logger.warning(
                        "Failed to emit WebSocket event for removed torrent: %s",
                        ws_error,
                    )

                return web.json_response({"status": "removed"})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error removing torrent %s: %s", info_hash, e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to remove torrent",
                    code="REMOVE_TORRENT_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_list_torrents(self, _request: Request) -> Response:
        """Handle GET /api/v1/torrents."""
        try:
            result = await self.executor.execute("torrent.list")

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to list torrents",
                        code="LIST_FAILED",
                    ).model_dump(),
                    status=500,
                )

            torrents = result.data.get("torrents", [])
            response = TorrentListResponse(torrents=torrents)
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error listing torrents: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to list torrents",
                    code="LIST_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_torrent_status(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute("torrent.status", info_hash=info_hash)

            if not result.success or not result.data.get("status"):
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Torrent not found",
                        code="TORRENT_NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )

            status = result.data["status"]
            return web.json_response(status.model_dump())  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error getting torrent status for %s: %s", info_hash, e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to get torrent status",
                    code="GET_STATUS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_pause_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/pause."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute("torrent.pause", info_hash=info_hash)

            if result.success and result.data.get("paused"):
                return web.json_response({"status": "paused"})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error pausing torrent %s: %s", info_hash, e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to pause torrent",
                    code="PAUSE_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_resume_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/resume."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute("torrent.resume", info_hash=info_hash)

            if result.success and result.data.get("resumed"):
                return web.json_response({"status": "resumed"})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error resuming torrent %s: %s", info_hash, e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to resume torrent",
                    code="RESUME_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_torrent_peers(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/peers."""
        info_hash = request.match_info["info_hash"]

        result = await self.executor.execute("torrent.get_peers", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )

        peers = result.data.get("peers", [])
        from ccbt.daemon.ipc_protocol import PeerInfo

        peer_infos = [
            PeerInfo(
                ip=p.get("ip", ""),
                port=p.get("port", 0),
                download_rate=p.get("download_rate", 0.0),
                upload_rate=p.get("upload_rate", 0.0),
                choked=p.get("choked", False),
                client=p.get("client"),
            )
            for p in peers
        ]

        response = PeerListResponse(
            info_hash=info_hash,
            peers=peer_infos,
            count=len(peer_infos),
        )
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    async def _handle_set_rate_limits(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/rate-limits."""
        info_hash = request.match_info["info_hash"]

        try:
            data = await request.json()
            req = RateLimitRequest(**data)

            result = await self.executor.execute(
                "torrent.set_rate_limits",
                info_hash=info_hash,
                download_kib=req.download_kib,
                upload_kib=req.upload_kib,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to set rate limits",
                        code="RATE_LIMIT_ERROR",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error setting rate limits: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to set rate limits: {e}",
                    code="RATE_LIMIT_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_force_announce(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/announce."""
        info_hash = request.match_info["info_hash"]

        result = await self.executor.execute(
            "torrent.force_announce", info_hash=info_hash
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to force announce",
                    code="ANNOUNCE_ERROR",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_export_session_state(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/export-state."""
        try:
            data = await request.json() if request.content_length else {}
            req = ExportStateRequest(**data)

            result = await self.executor.execute(
                "torrent.export_session_state",
                path=req.path,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to export session state",
                        code="EXPORT_ERROR",
                    ).model_dump(),
                    status=500,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error exporting session state: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to export session state: {e}",
                    code="EXPORT_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_import_session_state(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/import-state."""
        try:
            data = await request.json()
            req = ImportStateRequest(**data)

            result = await self.executor.execute(
                "torrent.import_session_state",
                path=req.path,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to import session state",
                        code="IMPORT_ERROR",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error importing session state: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to import session state: {e}",
                    code="IMPORT_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_resume_from_checkpoint(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/resume-checkpoint."""
        try:
            data = await request.json()
            req = ResumeCheckpointRequest(**data)

            # Convert hex info_hash to bytes
            try:
                info_hash_bytes = bytes.fromhex(req.info_hash)
            except ValueError:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Invalid info hash format",
                        code="INVALID_INFO_HASH",
                    ).model_dump(),
                    status=400,
                )

            result = await self.executor.execute(
                "torrent.resume_from_checkpoint",
                info_hash=info_hash_bytes,
                checkpoint=req.checkpoint,
                torrent_path=req.torrent_path,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to resume from checkpoint",
                        code="RESUME_ERROR",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error resuming from checkpoint: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to resume from checkpoint: {e}",
                    code="RESUME_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_config(self, _request: Request) -> Response:
        """Handle GET /api/v1/config."""
        result = await self.executor.execute("config.get")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get config",
                    code="CONFIG_ERROR",
                ).model_dump(),
                status=500,
            )

        return web.json_response(result.data["config"])  # type: ignore[attr-defined]

    async def _handle_update_config(self, request: Request) -> Response:
        """Handle PUT /api/v1/config."""
        try:
            data = await request.json()

            result = await self.executor.execute("config.update", config_dict=data)

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to update config",
                        code="CONFIG_UPDATE_FAILED",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error updating config: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to update config: {e}",
                    code="CONFIG_UPDATE_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_shutdown(self, _request: Request) -> Response:
        """Handle POST /api/v1/shutdown."""
        logger.info("Shutdown requested via IPC")
        # Schedule shutdown (don't block the response)
        _ = asyncio.create_task(self._shutdown_async())
        return web.json_response({"status": "shutting_down"})  # type: ignore[attr-defined]

    async def _shutdown_async(self) -> None:
        """Async shutdown handler."""
        await asyncio.sleep(0.1)  # Give response time to send
        # Signal shutdown to daemon main (this will be handled by DaemonMain)
        # For now, we'll just log it
        logger.info("Shutdown signal sent")

    # File Selection Handlers

    async def _handle_get_torrent_files(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/files."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        result = await self.executor.execute("file.list", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get files",
                    code="FILE_LIST_FAILED",
                ).model_dump(),
                status=404,
            )

        file_list = result.data["files"]
        return web.json_response(file_list.model_dump())  # type: ignore[attr-defined]

    async def _handle_select_files(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/files/select."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        data = await request.json()
        req = FileSelectRequest(**data)

        result = await self.executor.execute(
            "file.select",
            info_hash=info_hash,
            file_indices=req.file_indices,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to select files",
                    code="FILE_SELECT_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_deselect_files(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/files/deselect."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        data = await request.json()
        req = FileSelectRequest(**data)

        result = await self.executor.execute(
            "file.deselect",
            info_hash=info_hash,
            file_indices=req.file_indices,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to deselect files",
                    code="FILE_DESELECT_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_set_file_priority(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/files/priority."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        data = await request.json()
        req = FilePriorityRequest(**data)

        result = await self.executor.execute(
            "file.priority",
            info_hash=info_hash,
            file_index=req.file_index,
            priority=req.priority,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to set file priority",
                    code="FILE_PRIORITY_FAILED",
                ).model_dump(),
                status=400,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_verify_files(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/files/verify."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        result = await self.executor.execute("file.verify", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to verify files",
                    code="FILE_VERIFY_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    # Queue Handlers

    async def _handle_get_queue(self, _request: Request) -> Response:
        """Handle GET /api/v1/queue."""
        result = await self.executor.execute("queue.list")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get queue",
                    code="QUEUE_GET_FAILED",
                ).model_dump(),
                status=404,
            )

        queue_list = result.data["queue"]
        return web.json_response(queue_list.model_dump())  # type: ignore[attr-defined]

    async def _handle_queue_add(self, request: Request) -> Response:
        """Handle POST /api/v1/queue/add."""
        data = await request.json()
        req = QueueAddRequest(**data)

        result = await self.executor.execute(
            "queue.add",
            info_hash=req.info_hash,
            priority=req.priority,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to add to queue",
                    code="QUEUE_ADD_FAILED",
                ).model_dump(),
                status=400,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_queue_remove(self, request: Request) -> Response:
        """Handle DELETE /api/v1/queue/{info_hash}."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        result = await self.executor.execute("queue.remove", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found in queue",
                    code="QUEUE_NOT_FOUND",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_queue_move(self, request: Request) -> Response:
        """Handle POST /api/v1/queue/{info_hash}/move."""
        info_hash = request.match_info["info_hash"]
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid info hash format",
                    code="INVALID_INFO_HASH",
                ).model_dump(),
                status=400,
            )

        data = await request.json()
        req = QueueMoveRequest(**data)

        result = await self.executor.execute(
            "queue.move",
            info_hash=info_hash,
            new_position=req.new_position,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to move in queue",
                    code="QUEUE_MOVE_FAILED",
                ).model_dump(),
                status=400,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_queue_clear(self, _request: Request) -> Response:
        """Handle POST /api/v1/queue/clear."""
        result = await self.executor.execute("queue.clear")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to clear queue",
                    code="QUEUE_CLEAR_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_queue_pause(self, request: Request) -> Response:
        """Handle POST /api/v1/queue/{info_hash}/pause."""
        info_hash = request.match_info["info_hash"]
        result = await self.executor.execute("queue.pause", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_queue_resume(self, request: Request) -> Response:
        """Handle POST /api/v1/queue/{info_hash}/resume."""
        info_hash = request.match_info["info_hash"]
        result = await self.executor.execute("queue.resume", info_hash=info_hash)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Torrent not found",
                    code="TORRENT_NOT_FOUND",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    # NAT Handlers

    async def _handle_nat_status(self, _request: Request) -> Response:
        """Handle GET /api/v1/nat/status."""
        result = await self.executor.execute("nat.status")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get NAT status",
                    code="NAT_STATUS_FAILED",
                ).model_dump(),
                status=500,
            )

        nat_status = result.data["status"]
        return web.json_response(nat_status.model_dump())  # type: ignore[attr-defined]

    async def _handle_nat_discover(self, _request: Request) -> Response:
        """Handle POST /api/v1/nat/discover."""
        result = await self.executor.execute("nat.discover")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to discover NAT",
                    code="NAT_DISCOVER_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_nat_map(self, request: Request) -> Response:
        """Handle POST /api/v1/nat/map."""
        data = await request.json()
        req = NATMapRequest(**data)

        result = await self.executor.execute(
            "nat.map",
            internal_port=req.internal_port,
            external_port=req.external_port,
            protocol=req.protocol,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to map NAT port",
                    code="NAT_MAP_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_nat_unmap(self, request: Request) -> Response:
        """Handle POST /api/v1/nat/unmap."""
        data = await request.json()
        port = data.get("port")
        protocol = data.get("protocol", "tcp")

        result = await self.executor.execute("nat.unmap", port=port, protocol=protocol)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to unmap NAT port",
                    code="NAT_UNMAP_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_nat_refresh(self, _request: Request) -> Response:
        """Handle POST /api/v1/nat/refresh."""
        result = await self.executor.execute("nat.refresh")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to refresh NAT mappings",
                    code="NAT_REFRESH_FAILED",
                ).model_dump(),
                status=404,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_get_external_ip(self, _request: Request) -> Response:
        """Handle GET /api/v1/nat/external-ip."""
        result = await self.executor.execute("nat.get_external_ip")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get external IP",
                    code="NAT_ERROR",
                ).model_dump(),
                status=500,
            )

        external_ip = result.data.get("external_ip")
        # Try to get method from NAT status if available
        method = None
        try:
            status_result = await self.executor.execute("nat.status")
            if status_result.success and status_result.data.get("status"):
                method = status_result.data["status"].get("method")
        except Exception:
            pass

        response = ExternalIPResponse(external_ip=external_ip, method=method)
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    async def _handle_get_external_port(self, request: Request) -> Response:
        """Handle GET /api/v1/nat/external-port/{internal_port}."""
        try:
            internal_port = int(request.match_info["internal_port"])
        except (ValueError, KeyError):
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Invalid internal port",
                    code="INVALID_PORT",
                ).model_dump(),
                status=400,
            )

        protocol = request.query.get("protocol", "tcp")

        result = await self.executor.execute(
            "nat.get_external_port",
            internal_port=internal_port,
            protocol=protocol,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get external port",
                    code="NAT_ERROR",
                ).model_dump(),
                status=404,
            )

        external_port = result.data.get("external_port")
        response = ExternalPortResponse(
            internal_port=internal_port,
            external_port=external_port,
            protocol=protocol,
        )
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    # Scrape Handlers

    async def _handle_scrape(self, request: Request) -> Response:
        """Handle POST /api/v1/scrape/{info_hash}."""
        info_hash = request.match_info["info_hash"]
        data = await request.json() if request.content_length else {}
        req = ScrapeRequest(**data)

        result = await self.executor.execute(
            "scrape.torrent",
            info_hash=info_hash,
            force=req.force,
        )

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to scrape torrent",
                    code="SCRAPE_FAILED",
                ).model_dump(),
                status=500,
            )

        scrape_result = result.data["result"]
        return web.json_response(scrape_result.model_dump())  # type: ignore[attr-defined]

    async def _handle_list_scrape(self, _request: Request) -> Response:
        """Handle GET /api/v1/scrape."""
        result = await self.executor.execute("scrape.list")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to list scrape results",
                    code="SCRAPE_LIST_FAILED",
                ).model_dump(),
                status=500,
            )

        scrape_list = result.data["results"]
        return web.json_response(scrape_list.model_dump())  # type: ignore[attr-defined]

    async def _handle_get_scrape_result(self, request: Request) -> Response:
        """Handle GET /api/v1/scrape/{info_hash}."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute(
                "scrape.get_result", info_hash=info_hash
            )

            if not result.success:
                # If result not found, return 404
                if "not found" in (result.error or "").lower():
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=result.error or "Scrape result not found",
                            code="SCRAPE_NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to get scrape result",
                        code="SCRAPE_GET_FAILED",
                    ).model_dump(),
                    status=500,
                )

            scrape_result = result.data.get("result")
            if scrape_result is None:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Scrape result not found",
                        code="SCRAPE_NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )

            return web.json_response(scrape_result.model_dump())  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error getting scrape result for %s: %s", info_hash, e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get scrape result: {e}",
                    code="SCRAPE_GET_ERROR",
                ).model_dump(),
                status=500,
            )

    # Protocol Handlers

    async def _handle_get_xet_protocol(self, _request: Request) -> Response:
        """Handle GET /api/v1/protocols/xet."""
        result = await self.executor.execute("protocol.get_xet")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get Xet protocol info",
                    code="PROTOCOL_ERROR",
                ).model_dump(),
                status=500,
            )

        protocol_info = result.data["protocol"]
        return web.json_response(protocol_info.model_dump())  # type: ignore[attr-defined]

    async def _handle_get_ipfs_protocol(self, _request: Request) -> Response:
        """Handle GET /api/v1/protocols/ipfs."""
        result = await self.executor.execute("protocol.get_ipfs")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get IPFS protocol info",
                    code="PROTOCOL_ERROR",
                ).model_dump(),
                status=500,
            )

        protocol_info = result.data["protocol"]
        return web.json_response(protocol_info.model_dump())  # type: ignore[attr-defined]

    # Session Handlers

    async def _handle_get_global_stats(self, _request: Request) -> Response:
        """Handle GET /api/v1/session/stats."""
        result = await self.executor.execute("session.get_global_stats")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get global stats",
                    code="SESSION_ERROR",
                ).model_dump(),
                status=500,
            )

        stats = result.data.get("stats", {})
        response = GlobalStatsResponse(
            num_torrents=stats.get("num_torrents", 0),
            num_active=stats.get("num_active", 0),
            num_paused=stats.get("num_paused", 0),
            total_download_rate=stats.get("total_download_rate", 0.0),
            total_upload_rate=stats.get("total_upload_rate", 0.0),
            total_downloaded=stats.get("total_downloaded", 0),
            total_uploaded=stats.get("total_uploaded", 0),
            stats=stats,
        )
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    # Security Handlers

    async def _handle_get_blacklist(self, _request: Request) -> Response:
        """Handle GET /api/v1/security/blacklist."""
        result = await self.executor.execute("security.get_blacklist")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get blacklist",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

        blacklist = result.data.get("blacklist", [])
        response = BlacklistResponse(ips=blacklist, count=len(blacklist))
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    async def _handle_get_whitelist(self, _request: Request) -> Response:
        """Handle GET /api/v1/security/whitelist."""
        result = await self.executor.execute("security.get_whitelist")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get whitelist",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

        whitelist = result.data.get("whitelist", [])
        response = WhitelistResponse(ips=whitelist, count=len(whitelist))
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    async def _handle_add_to_blacklist(self, request: Request) -> Response:
        """Handle POST /api/v1/security/blacklist."""
        try:
            data = await request.json()
            req = BlacklistAddRequest(**data)

            result = await self.executor.execute(
                "security.add_to_blacklist",
                ip=req.ip,
                reason=req.reason or "",
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to add to blacklist",
                        code="SECURITY_ERROR",
                    ).model_dump(),
                    status=400,
                )

            # Emit WebSocket event
            await self._emit_websocket_event(
                EventType.SECURITY_BLACKLIST_UPDATED,
                {"ip": req.ip, "action": "added"},
            )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error adding to blacklist: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to add to blacklist: {e}",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_remove_from_blacklist(self, request: Request) -> Response:
        """Handle DELETE /api/v1/security/blacklist/{ip}."""
        ip = request.match_info["ip"]

        result = await self.executor.execute("security.remove_from_blacklist", ip=ip)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to remove from blacklist",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=404,
            )

        # Emit WebSocket event
        await self._emit_websocket_event(
            EventType.SECURITY_BLACKLIST_UPDATED,
            {"ip": ip, "action": "removed"},
        )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_add_to_whitelist(self, request: Request) -> Response:
        """Handle POST /api/v1/security/whitelist."""
        try:
            data = await request.json()
            req = WhitelistAddRequest(**data)

            result = await self.executor.execute(
                "security.add_to_whitelist",
                ip=req.ip,
                reason=req.reason or "",
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to add to whitelist",
                        code="SECURITY_ERROR",
                    ).model_dump(),
                    status=400,
                )

            # Emit WebSocket event
            await self._emit_websocket_event(
                EventType.SECURITY_WHITELIST_UPDATED,
                {"ip": req.ip, "action": "added"},
            )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error adding to whitelist: %s", e)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to add to whitelist: {e}",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_remove_from_whitelist(self, request: Request) -> Response:
        """Handle DELETE /api/v1/security/whitelist/{ip}."""
        ip = request.match_info["ip"]

        result = await self.executor.execute("security.remove_from_whitelist", ip=ip)

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to remove from whitelist",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=404,
            )

        # Emit WebSocket event
        await self._emit_websocket_event(
            EventType.SECURITY_WHITELIST_UPDATED,
            {"ip": ip, "action": "removed"},
        )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_load_ip_filter(self, _request: Request) -> Response:
        """Handle POST /api/v1/security/ip-filter/load."""
        result = await self.executor.execute("security.load_ip_filter")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to load IP filter",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

        return web.json_response(result.data)  # type: ignore[attr-defined]

    async def _handle_get_ip_filter_stats(self, _request: Request) -> Response:
        """Handle GET /api/v1/security/ip-filter/stats."""
        result = await self.executor.execute("security.get_ip_filter_stats")

        if not result.success:
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get IP filter stats",
                    code="SECURITY_ERROR",
                ).model_dump(),
                status=500,
            )

        stats_data = result.data
        response = IPFilterStatsResponse(
            enabled=stats_data.get("enabled", False),
            total_rules=stats_data.get("stats", {}).get("total_rules", 0),
            blocked_count=stats_data.get("stats", {}).get("blocked_count", 0),
            allowed_count=stats_data.get("stats", {}).get("allowed_count", 0),
            stats=stats_data.get("stats", {}),
        )
        return web.json_response(response.model_dump())  # type: ignore[attr-defined]

    # WebSocket Handler

    async def _handle_websocket(self, request: Request) -> web.WebSocketResponse:  # type: ignore[attr-defined]
        """Handle WebSocket connection for real-time events."""
        ws = web.WebSocketResponse()  # type: ignore[attr-defined]
        await ws.prepare(request)

        # Authenticate WebSocket connection
        # Try Ed25519 signature authentication first
        authenticated = False
        if self.key_manager:
            signature = request.query.get("signature") or request.headers.get(
                SIGNATURE_HEADER
            )
            public_key_hex = request.query.get("public_key") or request.headers.get(
                PUBLIC_KEY_HEADER
            )
            timestamp_str = request.query.get("timestamp") or request.headers.get(
                TIMESTAMP_HEADER
            )

            if signature and public_key_hex and timestamp_str:
                try:
                    import time

                    timestamp = float(timestamp_str)
                    current_time = time.time()
                    if abs(current_time - timestamp) <= 300:  # 5 minutes
                        # Verify signature for WebSocket upgrade
                        message = f"GET {request.path}\n{timestamp}".encode()
                        public_key_bytes = bytes.fromhex(public_key_hex)
                        signature_bytes = bytes.fromhex(signature)

                        if self.key_manager.verify_signature(
                            message, signature_bytes, public_key_bytes
                        ):
                            authenticated = True
                except Exception as e:
                    logger.debug("WebSocket Ed25519 auth error: %s", e)

        # Fall back to API key
        if not authenticated:
            api_key = request.query.get("api_key") or request.headers.get(
                API_KEY_HEADER
            )
            if api_key and api_key == self.api_key:
                authenticated = True

        if not authenticated:
            logger.warning("Unauthorized WebSocket connection attempt")
            await ws.close(code=4001, message="Unauthorized")
            return ws

        # Add to connections
        self._websocket_connections.add(ws)
        self._websocket_subscriptions[ws] = set()

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            self._websocket_heartbeat(ws),
        )
        self._websocket_heartbeat_tasks[ws] = heartbeat_task

        try:
            # Wait for subscription message
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        message = WebSocketMessage(**data)

                        if message.action == "subscribe":
                            sub_req = WebSocketSubscribeRequest(**message.data or {})
                            self._websocket_subscriptions[ws].update(
                                sub_req.event_types
                            )
                            await ws.send_json(
                                {
                                    "action": "subscribed",
                                    "event_types": [
                                        e.value for e in sub_req.event_types
                                    ],
                                }
                            )

                        elif message.action == "unsubscribe":
                            if message.data and "event_types" in message.data:
                                event_types = [
                                    EventType(et) for et in message.data["event_types"]
                                ]
                                self._websocket_subscriptions[ws] -= set(event_types)
                                await ws.send_json({"action": "unsubscribed"})

                        elif message.action == "ping":
                            await ws.send_json({"action": "pong"})

                    except Exception as e:
                        logger.exception("Error processing WebSocket message")
                        await ws.send_json(
                            {"action": "error", "error": str(e)},
                        )

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.warning("WebSocket error: %s", ws.exception())
                    break

        except Exception:
            logger.exception("WebSocket connection error")
        finally:
            # Cleanup
            self._websocket_connections.discard(ws)
            self._websocket_subscriptions.pop(ws, None)
            if ws in self._websocket_heartbeat_tasks:
                task = self._websocket_heartbeat_tasks.pop(ws)
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        return ws

    async def _websocket_heartbeat(self, ws: web.WebSocketResponse) -> None:  # type: ignore[attr-defined]
        """Send periodic heartbeat to WebSocket connection."""
        try:
            while not ws.closed:
                await asyncio.sleep(self.websocket_heartbeat_interval)
                if not ws.closed:
                    await ws.send_json({"action": "ping"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("WebSocket heartbeat error: %s", e)

    async def _emit_websocket_event(
        self,
        event_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """Emit event to all subscribed WebSocket connections."""
        if not self.websocket_enabled:
            return

        event = WebSocketEvent(
            type=event_type,
            timestamp=time.time(),
            data=data,
        )

        # Send to all subscribed connections
        disconnected = []
        for ws in self._websocket_connections:
            if ws.closed:
                disconnected.append(ws)
                continue

            # Check if connection is subscribed to this event type
            subscriptions = self._websocket_subscriptions.get(ws, set())
            if not subscriptions or event_type in subscriptions:
                try:
                    await ws.send_json(event.model_dump())
                except Exception as e:
                    logger.debug("Error sending WebSocket event: %s", e)
                    disconnected.append(ws)

        # Cleanup disconnected connections
        for ws in disconnected:
            self._websocket_connections.discard(ws)
            self._websocket_subscriptions.pop(ws, None)
            if ws in self._websocket_heartbeat_tasks:
                task = self._websocket_heartbeat_tasks.pop(ws)
                task.cancel()

    # Server Lifecycle

    async def start(self) -> None:
        """Start the IPC server."""
        try:
            self.runner = web.AppRunner(self.app)  # type: ignore[attr-defined]
            await self.runner.setup()

            # Configure TLS only if explicitly enabled in config
            ssl_context = None
            if self.tls_enabled and self.key_manager:
                try:
                    # Check if cryptography is available
                    if (
                        Encoding is None
                        or PrivateFormat is None
                        or NoEncryption is None
                    ):
                        logger.warning(
                            "TLS requested but cryptography module not available. "
                            "TLS will be disabled."
                        )
                    else:
                        from ccbt.security.tls_certificates import TLSCertificateManager

                        cert_manager = TLSCertificateManager()
                        # Get private key from key manager
                        private_key, _ = self.key_manager.get_or_create_keypair()
                        # Get or create certificate
                        certificate, _ = cert_manager.get_or_create_certificate(
                            private_key
                        )

                        # Create SSL context
                        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        # Load certificate and key
                        cert_manager.certificate_file.write_bytes(
                            certificate.public_bytes(Encoding.PEM)
                        )
                        cert_manager.private_key_file.write_bytes(
                            private_key.private_bytes(
                                encoding=Encoding.PEM,
                                format=PrivateFormat.PKCS8,
                                encryption_algorithm=NoEncryption(),
                            )
                        )
                        ssl_context.load_cert_chain(
                            str(cert_manager.certificate_file),
                            str(cert_manager.private_key_file),
                        )
                        logger.info("TLS enabled for IPC server")
                except Exception as e:
                    logger.warning("Failed to configure TLS: %s", e)

            self.site = web.TCPSite(  # type: ignore[attr-defined]
                self.runner, self.host, self.port, ssl_context=ssl_context
            )
            try:
                await self.site.start()
                # CRITICAL: Verify the site actually started and is listening
                # Wait a moment for the server to fully initialize
                await asyncio.sleep(0.1)
                if not self.site._server:  # noqa: SLF001
                    raise RuntimeError(
                        f"IPC server site.start() completed but _server is None on {self.host}:{self.port}"
                    )
                if (
                    not hasattr(self.site._server, "sockets")
                    or not self.site._server.sockets
                ):  # noqa: SLF001
                    raise RuntimeError(
                        f"IPC server site.start() completed but no sockets are listening on {self.host}:{self.port}"
                    )
                logger.debug(
                    "IPC server verified: %d socket(s) listening on %s:%d",
                    len(self.site._server.sockets),  # noqa: SLF001
                    self.host,
                    self.port,
                )
            except OSError as e:
                # Handle binding errors (port in use, permission denied, etc.)
                error_code = e.errno if hasattr(e, "errno") else None
                if (error_code == 10048 and sys.platform == "win32") or (
                    error_code == 98 and sys.platform != "win32"
                ):
                    # Port already in use - provide detailed resolution steps
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(self.port, "tcp")
                    error_msg = (
                        f"IPC server failed to bind to {self.host}:{self.port}: {e}\n\n"
                        f"{resolution}"
                    )
                    logger.error(error_msg)
                    # Clean up runner if site failed to start
                    if self.runner:
                        await self.runner.cleanup()
                    raise RuntimeError(error_msg) from e
                # Other binding errors (permission denied, etc.)
                logger.exception(
                    "Failed to start IPC server on %s:%d: %s",
                    self.host,
                    self.port,
                    e,
                )
                # Clean up runner if site failed to start
                if self.runner:
                    await self.runner.cleanup()
                raise RuntimeError(
                    f"IPC server failed to bind to {self.host}:{self.port}: {e}"
                ) from e
            except Exception as e:
                # Catch any other unexpected errors during startup
                logger.exception(
                    "Unexpected error starting IPC server on %s:%d: %s",
                    self.host,
                    self.port,
                    e,
                )
                # Clean up runner if site failed to start
                if self.runner:
                    await self.runner.cleanup()
                raise RuntimeError(
                    f"IPC server failed to start on {self.host}:{self.port}: {e}"
                ) from e

            # Get actual port (in case port 0 was used for random port)
            if self.site._server and self.site._server.sockets:  # noqa: SLF001
                sock = self.site._server.sockets[0]  # noqa: SLF001
                self.port = sock.getsockname()[1]
                # Log actual binding address for debugging
                actual_addr = sock.getsockname()
                logger.debug(
                    "IPC server socket bound to %s:%d (requested: %s:%d)",
                    actual_addr[0],
                    actual_addr[1],
                    self.host,
                    self.port,
                )

            protocol = "https" if (self.tls_enabled and ssl_context) else "http"
            logger.info(
                "IPC server started on %s://%s:%d", protocol, self.host, self.port
            )

            # CRITICAL: On Windows, verify the server is actually accepting HTTP connections
            # Socket test alone isn't sufficient - aiohttp might not be ready for HTTP yet
            # If binding to 0.0.0.0, verify via 127.0.0.1; otherwise use the bound host
            import socket

            verify_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host

            # First do a socket test to verify the port is bound
            socket_ready = False
            for socket_attempt in range(5):
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(0.5)
                try:
                    result = test_sock.connect_ex((verify_host, self.port))
                    test_sock.close()
                    if result == 0:
                        socket_ready = True
                        logger.debug(
                            "IPC server socket verified on %s:%d (bound to %s)",
                            verify_host,
                            self.port,
                            self.host,
                        )
                        break
                    if socket_attempt < 4:
                        await asyncio.sleep(0.1)
                except Exception as verify_error:
                    test_sock.close()
                    logger.debug("Error verifying IPC server socket: %s", verify_error)
                    if socket_attempt < 4:
                        await asyncio.sleep(0.1)

            # CRITICAL: Now verify HTTP is actually working by making a real HTTP request
            # This is essential on Windows where socket test can pass but HTTP isn't ready
            http_ready = False
            if socket_ready:
                import aiohttp

                for http_attempt in range(10):  # More attempts for HTTP readiness
                    try:
                        # CRITICAL: Use context manager with explicit cleanup on Windows
                        async with aiohttp.ClientSession() as session:
                            url = f"http://{verify_host}:{self.port}{API_BASE_PATH}/status"
                            headers = {}
                            if self.api_key:
                                headers[API_KEY_HEADER] = self.api_key
                            async with session.get(
                                url,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=2.0),
                            ) as resp:
                                if resp.status == 200:
                                    http_ready = True
                                    logger.debug(
                                        "IPC server HTTP verified accepting connections on %s:%d (bound to %s)",
                                        verify_host,
                                        self.port,
                                        self.host,
                                    )
                                    # CRITICAL: On Windows, wait for session cleanup to complete
                                    # This prevents "Unclosed client session" warnings
                                    import sys

                                    if sys.platform == "win32":
                                        await asyncio.sleep(0.1)
                                    break
                    except (aiohttp.ClientError, asyncio.TimeoutError) as http_error:
                        if http_attempt < 9:
                            await asyncio.sleep(
                                0.2
                            )  # Wait longer between HTTP attempts
                        else:
                            logger.warning(
                                "IPC server socket is ready but HTTP test failed after %d attempts: %s. "
                                "Server may still be initializing.",
                                http_attempt + 1,
                                http_error,
                            )
                    except Exception as http_error:
                        logger.debug(
                            "Unexpected error during HTTP verification: %s", http_error
                        )
                        if http_attempt < 9:
                            await asyncio.sleep(0.2)

            if not http_ready and socket_ready:
                logger.warning(
                    "IPC server socket is listening but HTTP verification failed. "
                    "Server may still be initializing - this is normal on Windows."
                )
        except Exception as e:
            # Final safety net - log and re-raise any unhandled exceptions
            logger.exception(
                "Critical error during IPC server startup on %s:%d: %s",
                self.host,
                self.port,
                e,
            )
            raise

    async def stop(self) -> None:
        """Stop the IPC server."""
        # Close all WebSocket connections
        for ws in list(self._websocket_connections):
            if not ws.closed:
                await ws.close()

        # Cancel heartbeat tasks
        for task in self._websocket_heartbeat_tasks.values():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._websocket_connections.clear()
        self._websocket_subscriptions.clear()
        self._websocket_heartbeat_tasks.clear()

        # Stop server
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        logger.info("IPC server stopped")
