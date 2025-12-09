"""IPC server for daemon communication.

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
    DetailedGlobalMetricsResponse,
    DetailedPeerMetricsResponse,
    DetailedTorrentMetricsResponse,
    DiskIOMetricsResponse,
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
    GlobalPeerMetricsResponse,
    GlobalPeerListResponse,
    NetworkTimingMetricsResponse,
    PeerListResponse,
    PeerPerformanceMetrics,
    PerTorrentPerformanceResponse,
    PieceAvailabilityResponse,
    QueueAddRequest,
    QueueMoveRequest,
    RateSamplesResponse,
    RateLimitRequest,
    ResumeCheckpointRequest,
    ScrapeRequest,
    StatusResponse,
    TorrentAddRequest,
    TorrentListResponse,
    TrackerAddRequest,
    TrackerInfo,
    TrackerListResponse,
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
                    "Error handling request %s %s from %s",
                    request.method,
                    request.path,
                    request.remote,
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
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/rates",
            self._handle_rate_samples,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/disk-io",
            self._handle_disk_io_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/network-timing",
            self._handle_network_timing_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/performance",
            self._handle_per_torrent_performance,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/peers",
            self._handle_global_peer_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/peers/{{peer_key}}",
            self._handle_detailed_peer_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/peers/list",
            self._handle_global_peer_list,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/detailed",
            self._handle_detailed_torrent_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/global/detailed",
            self._handle_detailed_global_metrics,
        )
        
        # IMPROVEMENT: New metrics endpoints for trickle improvements
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/dht",
            self._handle_dht_query_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/peer-quality",
            self._handle_peer_quality_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/aggressive-discovery",
            self._handle_aggressive_discovery_status,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/torrents/{{info_hash}}/piece-selection",
            self._handle_piece_selection_metrics,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/metrics/swarm-health",
            self._handle_swarm_health,
        )

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
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/restart",
            self._handle_restart_torrent,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/cancel",
            self._handle_cancel_torrent,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/force-start",
            self._handle_force_start_torrent,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/peers",
            self._handle_get_torrent_peers,
        )
        # Batch operations
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/batch/pause",
            self._handle_batch_pause,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/batch/resume",
            self._handle_batch_resume,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/batch/restart",
            self._handle_batch_restart,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/batch/remove",
            self._handle_batch_remove,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/trackers",
            self._handle_get_torrent_trackers,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/trackers/add",
            self._handle_add_tracker,
        )
        self.app.router.add_delete(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/trackers/{{tracker_url}}",
            self._handle_remove_tracker,
        )
        # Per-peer rate limit endpoints
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/peers/{{peer_key}}/rate-limit",
            self._handle_set_per_peer_rate_limit,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/peers/{{peer_key}}/rate-limit",
            self._handle_get_per_peer_rate_limit,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/peers/rate-limit",
            self._handle_set_all_peers_rate_limit,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/piece-availability",
            self._handle_get_torrent_piece_availability,
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
            f"{API_BASE_PATH}/torrents/{{info_hash}}/pex/refresh",
            self._handle_refresh_pex,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/dht/aggressive",
            self._handle_set_dht_aggressive_mode,
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
        
        # Service restart endpoints
        self.app.router.add_post(
            f"{API_BASE_PATH}/services/{{service_name}}/restart",
            self._handle_restart_service,
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/services/status",
            self._handle_get_services_status,
        )

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
        self.app.router.add_get(
            f"{API_BASE_PATH}/torrents/{{info_hash}}/metadata/status",
            self._handle_get_metadata_status,
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
        self.app.router.add_post(
            f"{API_BASE_PATH}/global/pause-all",
            self._handle_global_pause_all,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/global/resume-all",
            self._handle_global_resume_all,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/global/force-start-all",
            self._handle_global_force_start_all,
        )
        self.app.router.add_post(
            f"{API_BASE_PATH}/global/rate-limits",
            self._handle_global_set_rate_limits,
        )

        # Protocol endpoints
        self.app.router.add_get(
            f"{API_BASE_PATH}/protocols/xet", self._handle_get_xet_protocol
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/protocols/ipfs", self._handle_get_ipfs_protocol
        )

        # XET folder endpoints
        self.app.router.add_post(
            f"{API_BASE_PATH}/xet/folders/add", self._handle_add_xet_folder
        )
        self.app.router.add_delete(
            f"{API_BASE_PATH}/xet/folders/{{folder_key}}", self._handle_remove_xet_folder
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/xet/folders", self._handle_list_xet_folders
        )
        self.app.router.add_get(
            f"{API_BASE_PATH}/xet/folders/{{folder_key}}", self._handle_get_xet_folder_status
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
        from ccbt.utils.version import get_version

        return get_version()

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

    async def _handle_rate_samples(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/rates - rate history samples."""
        seconds_param = request.query.get("seconds", "")
        seconds = 120
        if seconds_param:
            try:
                seconds_val = int(float(seconds_param))
                seconds = max(1, min(3600, seconds_val))
            except ValueError:
                seconds = 120

        try:
            # CRITICAL FIX: session_manager.get_rate_samples() returns list[dict[str, float]]
            # but RateSamplesResponse expects list[RateSample]
            samples_dict = await self.session_manager.get_rate_samples(seconds)
            logger.debug("IPCServer: Retrieved %d rate samples from session manager", len(samples_dict))
            
            # Convert dict samples to RateSample objects
            from ccbt.daemon.ipc_protocol import RateSample
            rate_samples = [
                RateSample(
                    timestamp=sample.get("timestamp", 0.0),
                    download_rate=sample.get("download_rate", 0.0),
                    upload_rate=sample.get("upload_rate", 0.0),
                )
                for sample in samples_dict
            ]
            
            response = RateSamplesResponse(
                resolution=1.0,
                seconds=seconds,
                sample_count=len(rate_samples),
                samples=rate_samples,
            )
            logger.debug("IPCServer: Returning RateSamplesResponse with %d samples", len(rate_samples))
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get rate samples")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get rate samples: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_disk_io_metrics(self, _request: Request) -> Response:
        """Handle GET /api/v1/metrics/disk-io - disk I/O metrics."""
        try:
            metrics = self.session_manager.get_disk_io_metrics()
            response = DiskIOMetricsResponse(**metrics)
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get disk I/O metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get disk I/O metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_network_timing_metrics(self, _request: Request) -> Response:
        """Handle GET /api/v1/metrics/network-timing - network timing metrics."""
        try:
            metrics = await self.session_manager.get_network_timing_metrics()
            response = NetworkTimingMetricsResponse(**metrics)
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get network timing metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get network timing metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_per_torrent_performance(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/performance - per-torrent performance metrics."""
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )

            # Get torrent status
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )

                # Get torrent status
                status = await self.session_manager.get_torrent_status(info_hash_hex)
                if not status:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Failed to get torrent status",
                            code="SERVER_ERROR",
                        ).model_dump(),
                        status=500,
                    )

                # Get peers
                peers_list = []
                if hasattr(torrent_session, "peers"):
                    from ccbt.monitoring import get_metrics_collector
                    metrics_collector = get_metrics_collector()
                    
                    for peer_key, peer in torrent_session.peers.items():
                        peer_metrics_data = None
                        if metrics_collector:
                            peer_metrics = metrics_collector.get_peer_metrics(str(peer_key))
                            if peer_metrics:
                                peer_metrics_data = {
                                    "download_rate": peer_metrics.download_rate,
                                    "upload_rate": peer_metrics.upload_rate,
                                    "request_latency": peer_metrics.request_latency,
                                    "pieces_served": peer_metrics.pieces_served,
                                    "pieces_received": peer_metrics.pieces_received,
                                    "connection_duration": peer_metrics.connection_duration,
                                    "consecutive_failures": peer_metrics.consecutive_failures,
                                    "bytes_downloaded": peer_metrics.bytes_downloaded,
                                    "bytes_uploaded": peer_metrics.bytes_uploaded,
                                }
                        
                        # Fallback to peer stats if metrics not available
                        if not peer_metrics_data and hasattr(peer, "stats"):
                            peer_stats = peer.stats
                            peer_metrics_data = {
                                "download_rate": getattr(peer_stats, "download_rate", 0.0),
                                "upload_rate": getattr(peer_stats, "upload_rate", 0.0),
                                "request_latency": getattr(peer_stats, "request_latency", 0.0),
                                "pieces_served": 0,
                                "pieces_received": 0,
                                "connection_duration": 0.0,
                                "consecutive_failures": getattr(peer_stats, "consecutive_failures", 0),
                                "bytes_downloaded": 0,
                                "bytes_uploaded": 0,
                            }
                        
                        if peer_metrics_data:
                            peer_key_str = f"{getattr(peer, 'ip', 'unknown')}:{getattr(peer, 'port', 0)}"
                            peers_list.append(
                                PeerPerformanceMetrics(
                                    peer_key=peer_key_str,
                                    **peer_metrics_data,
                                )
                            )

                # Sort peers by download rate (descending) and take top 10
                peers_list.sort(key=lambda p: p.download_rate, reverse=True)
                top_peers = peers_list[:10]

                # Calculate piece download rate
                piece_download_rate = 0.0
                if hasattr(torrent_session, "piece_manager"):
                    # Estimate from download rate and piece size
                    piece_size = getattr(torrent_session.piece_manager, "piece_length", 16384)
                    if piece_size > 0:
                        piece_download_rate = status.get("download_rate", 0.0) / piece_size

                # Calculate swarm availability (simplified)
                swarm_availability = 0.0
                if hasattr(torrent_session, "piece_manager"):
                    piece_manager = torrent_session.piece_manager
                    if hasattr(piece_manager, "availability"):
                        avail_list = piece_manager.availability
                        if avail_list:
                            swarm_availability = sum(avail_list) / len(avail_list) if len(avail_list) > 0 else 0.0

                response = PerTorrentPerformanceResponse(
                    info_hash=info_hash_hex,
                    download_rate=status.get("download_rate", 0.0),
                    upload_rate=status.get("upload_rate", 0.0),
                    progress=status.get("progress", 0.0),
                    pieces_completed=status.get("pieces_completed", 0),
                    pieces_total=status.get("pieces_total", 0),
                    connected_peers=status.get("num_peers", 0),
                    active_peers=status.get("num_seeds", 0),
                    top_peers=top_peers,
                    bytes_downloaded=status.get("downloaded", 0),
                    bytes_uploaded=status.get("uploaded", 0),
                    piece_download_rate=piece_download_rate,
                    swarm_availability=swarm_availability,
                )
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get per-torrent performance metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get per-torrent performance metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_global_peer_metrics(self, _request: Request) -> Response:
        """Handle GET /api/v1/metrics/peers - global peer metrics across all torrents."""
        try:
            metrics_data = await self.session_manager.get_global_peer_metrics()
            
            # Convert peer dictionaries to GlobalPeerMetrics objects
            from ccbt.daemon.ipc_protocol import GlobalPeerMetrics
            peer_metrics = [
                GlobalPeerMetrics(**peer_data)
                for peer_data in metrics_data.get("peers", [])
            ]
            
            response = GlobalPeerMetricsResponse(
                total_peers=metrics_data.get("total_peers", 0),
                active_peers=metrics_data.get("active_peers", 0),
                peers=peer_metrics,
            )
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get global peer metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get global peer metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_detailed_peer_metrics(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/peers/{peer_key} - detailed metrics for a specific peer."""
        try:
            peer_key = request.match_info.get("peer_key")
            if not peer_key:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing peer_key parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            # Get peer metrics from session manager's metrics collector
            peer_metrics = None
            if hasattr(self.session_manager, "metrics"):
                metrics_collector = self.session_manager.metrics
                if metrics_collector:
                    peer_metrics = metrics_collector.get_peer_metrics(peer_key)
            
            if not peer_metrics:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"Peer metrics not found for {peer_key}",
                        code="NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )
            
            # Convert to response model
            response = DetailedPeerMetricsResponse(
                peer_key=peer_metrics.peer_key,
                bytes_downloaded=peer_metrics.bytes_downloaded,
                bytes_uploaded=peer_metrics.bytes_uploaded,
                download_rate=peer_metrics.download_rate,
                upload_rate=peer_metrics.upload_rate,
                request_latency=peer_metrics.request_latency,
                consecutive_failures=peer_metrics.consecutive_failures,
                connection_duration=peer_metrics.connection_duration,
                pieces_served=peer_metrics.pieces_served,
                pieces_received=peer_metrics.pieces_received,
                pieces_per_second=peer_metrics.pieces_per_second,
                bytes_per_connection=peer_metrics.bytes_per_connection,
                efficiency_score=peer_metrics.efficiency_score,
                bandwidth_utilization=peer_metrics.bandwidth_utilization,
                connection_quality_score=peer_metrics.connection_quality_score,
                error_rate=peer_metrics.error_rate,
                success_rate=peer_metrics.success_rate,
                average_block_latency=peer_metrics.average_block_latency,
                peak_download_rate=peer_metrics.peak_download_rate,
                peak_upload_rate=peer_metrics.peak_upload_rate,
                performance_trend=peer_metrics.performance_trend,
                piece_download_speeds=peer_metrics.piece_download_speeds,
            )
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get detailed peer metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get detailed peer metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_global_peer_list(self, _request: Request) -> Response:
        """Handle GET /api/v1/peers/list - global list of all peers across all torrents with metrics."""
        try:
            # Get all peer connections from all torrents
            all_peers: list[dict[str, Any]] = []
            peer_keys_seen: set[str] = set()
            
            async with self.session_manager.lock:
                for info_hash, torrent_session in self.session_manager.torrents.items():
                    info_hash_hex = info_hash.hex()
                    if not hasattr(torrent_session, "download_manager"):
                        continue
                    
                    download_manager = torrent_session.download_manager
                    if not hasattr(download_manager, "peer_manager") or download_manager.peer_manager is None:
                        continue
                    
                    peer_manager = download_manager.peer_manager
                    connected_peers = peer_manager.get_connected_peers()
                    
                    for connection in connected_peers:
                        if not hasattr(connection, "peer_info") or not hasattr(connection, "stats"):
                            continue
                        
                        peer_key = str(connection.peer_info)
                        if peer_key in peer_keys_seen:
                            # Peer already added, skip to avoid duplicates
                            continue
                        peer_keys_seen.add(peer_key)
                        
                        stats = connection.stats
                        
                        # Get detailed metrics from metrics collector
                        peer_metrics = None
                        if hasattr(self.session_manager, "metrics"):
                            metrics_collector = self.session_manager.metrics
                            if metrics_collector:
                                peer_metrics = metrics_collector.get_peer_metrics(peer_key)
                        
                        # Get connection success rate
                        connection_success_rate = 0.0
                        if hasattr(self.session_manager, "metrics"):
                            metrics_collector = self.session_manager.metrics
                            if metrics_collector:
                                try:
                                    connection_success_rate = await metrics_collector.get_connection_success_rate(peer_key)
                                except Exception:
                                    pass
                        
                        # Build peer data dictionary with all metrics
                        peer_data: dict[str, Any] = {
                            "peer_key": peer_key,
                            "ip": connection.peer_info.ip,
                            "port": connection.peer_info.port,
                            "peer_source": getattr(connection.peer_info, "peer_source", "unknown"),
                            "info_hash": info_hash_hex,
                            # Basic stats
                            "bytes_downloaded": getattr(stats, "bytes_downloaded", 0),
                            "bytes_uploaded": getattr(stats, "bytes_uploaded", 0),
                            "download_rate": getattr(stats, "download_rate", 0.0),
                            "upload_rate": getattr(stats, "upload_rate", 0.0),
                            "request_latency": getattr(stats, "request_latency", 0.0),
                            "consecutive_failures": getattr(stats, "consecutive_failures", 0),
                            "connection_duration": getattr(stats, "connection_duration", 0.0),
                            "pieces_served": getattr(stats, "pieces_served", 0),
                            "pieces_received": getattr(stats, "pieces_received", 0),
                            "connection_success_rate": connection_success_rate,
                            # Performance metrics
                            "performance_score": getattr(stats, "performance_score", 0.0),
                            "efficiency_score": getattr(stats, "efficiency_score", 0.0),
                            "value_score": getattr(stats, "value_score", 0.0),
                            "connection_quality_score": getattr(stats, "connection_quality_score", 0.0),
                            "blocks_delivered": getattr(stats, "blocks_delivered", 0),
                            "blocks_failed": getattr(stats, "blocks_failed", 0),
                            "average_block_latency": getattr(stats, "average_block_latency", 0.0),
                        }
                        
                        # Add enhanced metrics from metrics collector if available
                        if peer_metrics:
                            peer_data.update({
                                "pieces_per_second": peer_metrics.pieces_per_second,
                                "bytes_per_connection": peer_metrics.bytes_per_connection,
                                "bandwidth_utilization": peer_metrics.bandwidth_utilization,
                                "error_rate": peer_metrics.error_rate,
                                "success_rate": peer_metrics.success_rate,
                                "peak_download_rate": peer_metrics.peak_download_rate,
                                "peak_upload_rate": peer_metrics.peak_upload_rate,
                                "performance_trend": peer_metrics.performance_trend,
                                "piece_download_speeds": peer_metrics.piece_download_speeds,
                                "piece_download_times": peer_metrics.piece_download_times,
                            })
                        
                        all_peers.append(peer_data)
            
            # Sort by performance score (highest first)
            all_peers.sort(key=lambda p: p.get("performance_score", 0.0), reverse=True)
            
            response = GlobalPeerListResponse(
                total_peers=len(peer_keys_seen),
                peers=all_peers,
                count=len(all_peers),
            )
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get global peer list")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get global peer list: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_detailed_torrent_metrics(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/detailed - detailed metrics for a specific torrent."""
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            # Get torrent status
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get torrent status
                status = await self.session_manager.get_torrent_status(info_hash_hex)
                if not status:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Failed to get torrent status",
                            code="SERVER_ERROR",
                        ).model_dump(),
                        status=500,
                    )
                
                # Get detailed metrics from utils/metrics.py MetricsCollector
                from ccbt.utils.metrics import MetricsCollector as UtilsMetricsCollector
                torrent_metrics = None
                if hasattr(self.session_manager, "metrics_collector"):
                    utils_collector = self.session_manager.metrics_collector
                    if utils_collector:
                        torrent_metrics = utils_collector.get_torrent_metrics(info_hash_hex)
                
                # Get piece availability if available
                piece_availability = []
                if hasattr(torrent_session, "piece_manager") and torrent_session.piece_manager:
                    piece_manager = torrent_session.piece_manager
                    piece_frequency = getattr(piece_manager, "piece_frequency", None)
                    if piece_frequency:
                        num_pieces = getattr(piece_manager, "num_pieces", 0)
                        if num_pieces == 0:
                            num_pieces = len(getattr(piece_manager, "pieces", []))
                        for piece_idx in range(num_pieces):
                            count = piece_frequency.get(piece_idx, 0)
                            piece_availability.append(count)
                
                # Get peer download speeds
                peer_download_speeds = []
                if hasattr(torrent_session, "peers"):
                    from ccbt.monitoring import get_metrics_collector
                    metrics_collector = get_metrics_collector()
                    for peer_key, peer in torrent_session.peers.items():
                        if metrics_collector:
                            peer_metrics = metrics_collector.get_peer_metrics(str(peer_key))
                            if peer_metrics:
                                peer_download_speeds.append(peer_metrics.download_rate)
                        elif hasattr(peer, "stats"):
                            peer_download_speeds.append(getattr(peer.stats, "download_rate", 0.0))
                
                # Build response with enhanced metrics
                response_data = {
                    "info_hash": info_hash_hex,
                    "bytes_downloaded": status.get("bytes_downloaded", 0),
                    "bytes_uploaded": status.get("bytes_uploaded", 0),
                    "download_rate": status.get("download_rate", 0.0),
                    "upload_rate": status.get("upload_rate", 0.0),
                    "pieces_completed": status.get("pieces_completed", 0),
                    "pieces_total": status.get("pieces_total", 0),
                    "progress": status.get("progress", 0.0),
                    "connected_peers": status.get("connected_peers", 0),
                    "active_peers": status.get("active_peers", 0),
                }
                
                # Add enhanced metrics if available
                if torrent_metrics:
                    response_data.update({
                        "piece_availability_distribution": torrent_metrics.piece_availability_distribution,
                        "average_piece_availability": torrent_metrics.average_piece_availability,
                        "rarest_piece_availability": torrent_metrics.rarest_piece_availability,
                        "swarm_health_score": torrent_metrics.swarm_health_score,
                        "peer_performance_distribution": torrent_metrics.peer_performance_distribution,
                        "average_peer_download_speed": torrent_metrics.average_peer_download_speed,
                        "median_peer_download_speed": torrent_metrics.median_peer_download_speed,
                        "fastest_peer_speed": torrent_metrics.fastest_peer_speed,
                        "slowest_peer_speed": torrent_metrics.slowest_peer_speed,
                        "piece_completion_rate": torrent_metrics.piece_completion_rate,
                        "estimated_time_remaining": torrent_metrics.estimated_time_remaining,
                        "swarm_efficiency": torrent_metrics.swarm_efficiency,
                        "peer_contribution_balance": torrent_metrics.peer_contribution_balance,
                    })
                else:
                    # Calculate from available data
                    if piece_availability:
                        from collections import Counter
                        availability_counter = Counter(piece_availability)
                        response_data["piece_availability_distribution"] = dict(availability_counter)
                        response_data["average_piece_availability"] = sum(piece_availability) / len(piece_availability) if piece_availability else 0.0
                        response_data["rarest_piece_availability"] = min(piece_availability) if piece_availability else 0
                    if peer_download_speeds:
                        import statistics
                        response_data["average_peer_download_speed"] = statistics.mean(peer_download_speeds)
                        response_data["median_peer_download_speed"] = statistics.median(peer_download_speeds)
                        response_data["fastest_peer_speed"] = max(peer_download_speeds)
                        response_data["slowest_peer_speed"] = min(peer_download_speeds)
                
                response = DetailedTorrentMetricsResponse(**response_data)
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get detailed torrent metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get detailed torrent metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_detailed_global_metrics(self, _request: Request) -> Response:
        """Handle GET /api/v1/metrics/global/detailed - detailed global metrics."""
        try:
            # Get global peer metrics
            global_peer_metrics = await self.session_manager.get_global_peer_metrics()
            
            # Get system-wide efficiency from session manager's metrics collector
            system_efficiency = {}
            connection_success_rate = 0.0
            if hasattr(self.session_manager, "metrics"):
                metrics_collector = self.session_manager.metrics
                if metrics_collector:
                    system_efficiency = metrics_collector.get_system_wide_efficiency()
                    # Get global connection success rate
                    try:
                        connection_success_rate = await metrics_collector.get_connection_success_rate()
                    except Exception as e:
                        logger.debug("Failed to get connection success rate: %s", e)
            
            # Combine into response
            response_data = {
                **global_peer_metrics,
                **system_efficiency,
                "connection_success_rate": connection_success_rate,
            }
            
            response = DetailedGlobalMetricsResponse(**response_data)
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get detailed global metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get detailed global metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_dht_query_metrics(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/dht - DHT query metrics."""
        from ccbt.daemon.ipc_protocol import DHTQueryMetricsResponse
        
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get DHT setup if available
                dht_setup = getattr(torrent_session, "_dht_setup", None)
                dht_client = getattr(torrent_session, "dht_client", None)
                aggressive_mode = getattr(dht_setup, "_aggressive_mode", False) if dht_setup else False
                
                # Get DHT query metrics if available
                dht_metrics = getattr(dht_setup, "_dht_query_metrics", None) if dht_setup else None
                
                # Initialize default metrics
                metrics = {
                    "info_hash": info_hash_hex,
                    "peers_found_per_query": 0.0,
                    "query_depth_achieved": 0.0,
                    "nodes_queried_per_query": 0.0,
                    "total_queries": 0,
                    "total_peers_found": 0,
                    "aggressive_mode_enabled": aggressive_mode,
                    "last_query_duration": 0.0,
                    "last_query_peers_found": 0,
                    "last_query_depth": 0,
                    "last_query_nodes_queried": 0,
                    "routing_table_size": 0,
                }
                
                # Use actual metrics if available
                if dht_metrics:
                    total_queries = dht_metrics.get("total_queries", 0)
                    total_peers = dht_metrics.get("total_peers_found", 0)
                    query_depths = dht_metrics.get("query_depths", [])
                    nodes_queried = dht_metrics.get("nodes_queried", [])
                    last_query = dht_metrics.get("last_query", {})
                    
                    metrics["total_queries"] = total_queries
                    metrics["total_peers_found"] = total_peers
                    metrics["peers_found_per_query"] = total_peers / total_queries if total_queries > 0 else 0.0
                    metrics["query_depth_achieved"] = sum(query_depths) / len(query_depths) if query_depths else 0.0
                    metrics["nodes_queried_per_query"] = sum(nodes_queried) / len(nodes_queried) if nodes_queried else 0.0
                    metrics["last_query_duration"] = last_query.get("duration", 0.0)
                    metrics["last_query_peers_found"] = last_query.get("peers_found", 0)
                    metrics["last_query_depth"] = last_query.get("depth", 0)
                    metrics["last_query_nodes_queried"] = last_query.get("nodes_queried", 0)
                
                # Get routing table size from DHT client
                if dht_client and hasattr(dht_client, "routing_table"):
                    routing_table = dht_client.routing_table
                    if hasattr(routing_table, "__len__"):
                        metrics["routing_table_size"] = len(routing_table)
                    elif hasattr(routing_table, "get_all_nodes"):
                        nodes = routing_table.get_all_nodes()
                        metrics["routing_table_size"] = len(nodes) if nodes else 0
                
                # Get aggressive mode status from DHT setup
                if dht_setup:
                    # Check if aggressive mode is enabled (stored in dht_setup)
                    aggressive_mode = getattr(dht_setup, "_aggressive_mode", False)
                    metrics["aggressive_mode_enabled"] = aggressive_mode
                
                # TODO: Track actual query metrics in DHT setup
                # For now, return placeholder metrics
                response = DHTQueryMetricsResponse(**metrics)
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get DHT query metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get DHT query metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_peer_quality_metrics(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/peer-quality - peer quality metrics."""
        from ccbt.daemon.ipc_protocol import PeerQualityMetricsResponse
        
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get peer manager
                peer_manager = None
                if hasattr(torrent_session, "download_manager"):
                    download_manager = torrent_session.download_manager
                    if hasattr(download_manager, "peer_manager"):
                        peer_manager = download_manager.peer_manager
                
                # Get peer quality metrics from PeerConnectionHelper if available
                peer_helper = getattr(torrent_session, "_peer_helper", None)
                peer_quality_metrics = getattr(peer_helper, "_peer_quality_metrics", None) if peer_helper else None
                
                # Collect peer quality scores
                quality_scores = []
                top_peers = []
                
                if peer_manager and hasattr(peer_manager, "get_active_peers"):
                    active_peers = peer_manager.get_active_peers()
                    for peer in active_peers:
                        if not hasattr(peer, "peer_info") or not hasattr(peer, "stats"):
                            continue
                        
                        # Calculate quality score (placeholder - should use actual ranking logic)
                        download_rate = getattr(peer.stats, "download_rate", 0.0)
                        upload_rate = getattr(peer.stats, "upload_rate", 0.0)
                        performance_score = getattr(peer.stats, "performance_score", 0.5)
                        
                        # Simple quality score calculation (matches ranking logic)
                        max_rate = 10 * 1024 * 1024
                        upload_norm = min(1.0, upload_rate / max_rate) if max_rate > 0 else 0.0
                        download_norm = min(1.0, download_rate / max_rate) if max_rate > 0 else 0.0
                        quality_score = (upload_norm * 0.6) + (download_norm * 0.4) + (performance_score * 0.2)
                        
                        quality_scores.append(quality_score)
                        top_peers.append({
                            "peer_key": str(peer.peer_info),
                            "ip": peer.peer_info.ip,
                            "port": peer.peer_info.port,
                            "quality_score": quality_score,
                            "download_rate": download_rate,
                            "upload_rate": upload_rate,
                        })
                
                # Sort top peers by quality
                top_peers.sort(key=lambda p: p["quality_score"], reverse=True)
                top_peers = top_peers[:10]  # Top 10
                
                # Calculate distribution
                high_quality = sum(1 for s in quality_scores if s > 0.7)
                medium_quality = sum(1 for s in quality_scores if 0.3 < s <= 0.7)
                low_quality = sum(1 for s in quality_scores if s <= 0.3)
                
                avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
                
                # Use stored metrics if available and current calculation is empty
                if not quality_scores and peer_quality_metrics:
                    last_ranking = peer_quality_metrics.get("last_ranking", {})
                    avg_score = last_ranking.get("average_score", 0.0)
                    high_quality = last_ranking.get("high_quality_count", 0)
                    medium_quality = last_ranking.get("medium_quality_count", 0)
                    low_quality = last_ranking.get("low_quality_count", 0)
                    total_ranked = last_ranking.get("peers_ranked", 0)
                    
                    # Get top peers from stored scores if available
                    stored_scores = peer_quality_metrics.get("quality_scores", [])
                    if stored_scores:
                        # Recalculate distribution
                        high_quality = sum(1 for s in stored_scores if s > 0.7)
                        medium_quality = sum(1 for s in stored_scores if 0.3 < s <= 0.7)
                        low_quality = sum(1 for s in stored_scores if s <= 0.3)
                        avg_score = sum(stored_scores) / len(stored_scores) if stored_scores else 0.0
                
                response = PeerQualityMetricsResponse(
                    info_hash=info_hash_hex,
                    total_peers_ranked=len(quality_scores),
                    average_quality_score=avg_score,
                    high_quality_peers=high_quality,
                    medium_quality_peers=medium_quality,
                    low_quality_peers=low_quality,
                    top_quality_peers=top_peers,
                    quality_distribution={
                        "high": high_quality,
                        "medium": medium_quality,
                        "low": low_quality,
                    },
                )
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get peer quality metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get peer quality metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_piece_selection_metrics(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/piece-selection - piece selection metrics."""
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get piece manager
                piece_manager = getattr(torrent_session, "piece_manager", None)
                if not piece_manager:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Piece manager not available",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get piece selection metrics
                metrics = piece_manager.get_piece_selection_metrics()
                
                return web.json_response(metrics)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get piece selection metrics")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get piece selection metrics: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_swarm_health(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/swarm-health - swarm health matrix with historical samples."""
        from ccbt.daemon.ipc_protocol import SwarmHealthMatrixResponse, SwarmHealthSample
        import time
        
        try:
            # Parse query parameters
            limit_param = request.query.get("limit", "6")
            seconds_param = request.query.get("seconds", "")
            
            limit = 6
            try:
                limit = max(1, min(100, int(limit_param)))
            except ValueError:
                limit = 6
            
            seconds = None
            if seconds_param:
                try:
                    seconds = max(1, min(3600, int(float(seconds_param))))
                except ValueError:
                    seconds = None
            
            # Get all torrents from session manager
            async with self.session_manager.lock:
                # Get all torrent statuses
                all_torrents = []
                for info_hash_bytes, torrent_session in self.session_manager.torrents.items():
                    try:
                        info_hash_hex = info_hash_bytes.hex()
                        status = await self.session_manager.get_torrent_status(info_hash_hex)
                        if status:
                            all_torrents.append((info_hash_hex, status, torrent_session))
                    except Exception as e:
                        logger.debug("Error getting status for torrent %s: %s", info_hash_bytes.hex()[:16], e)
                        continue
                
                if not all_torrents:
                    return web.json_response(  # type: ignore[attr-defined]
                        SwarmHealthMatrixResponse(samples=[], sample_count=0).model_dump()
                    )
                
                # Get top torrents by download rate
                def get_download_rate(item: tuple[str, dict[str, Any], Any]) -> float:
                    _, status, _ = item
                    return float(status.get("download_rate", 0.0))
                
                top_torrents = sorted(
                    all_torrents,
                    key=get_download_rate,
                    reverse=True,
                )[:limit]
                
                samples = []
                current_time = time.time()
                
                for info_hash_hex, status, torrent_session in top_torrents:
                    try:
                        # Get swarm availability from piece manager
                        swarm_availability = 0.0
                        if hasattr(torrent_session, "piece_manager"):
                            piece_manager = torrent_session.piece_manager
                            if hasattr(piece_manager, "availability"):
                                avail_list = piece_manager.availability
                                if avail_list:
                                    swarm_availability = sum(avail_list) / len(avail_list) if len(avail_list) > 0 else 0.0
                        
                        # Get active peers count
                        active_peers = 0
                        if hasattr(torrent_session, "download_manager"):
                            download_manager = torrent_session.download_manager
                            if hasattr(download_manager, "peer_manager"):
                                peer_manager = download_manager.peer_manager
                                if peer_manager and hasattr(peer_manager, "connections"):
                                    # Count active peers (those with download/upload activity)
                                    active_peers = sum(
                                        1 for conn in peer_manager.connections.values()
                                        if hasattr(conn, "stats") and (
                                            getattr(conn.stats, "download_rate", 0.0) > 0 or
                                            getattr(conn.stats, "upload_rate", 0.0) > 0
                                        )
                                    )
                        
                        sample = SwarmHealthSample(
                            info_hash=info_hash_hex,
                            name=str(status.get("name", info_hash_hex[:16])),
                            timestamp=current_time,
                            swarm_availability=swarm_availability,
                            download_rate=float(status.get("download_rate", 0.0)),
                            upload_rate=float(status.get("upload_rate", 0.0)),
                            connected_peers=int(status.get("num_peers", 0)),
                            active_peers=active_peers,
                            progress=float(status.get("progress", 0.0)),
                        )
                        samples.append(sample)
                    except Exception as e:
                        logger.debug("Error creating swarm health sample for %s: %s", info_hash_hex[:16], e)
                        continue
                
                # Calculate rarity percentiles
                availabilities = [s.swarm_availability for s in samples]
                availabilities.sort()
                n = len(availabilities)
                percentiles = {}
                if n > 0:
                    percentiles["p25"] = availabilities[n // 4] if n >= 4 else availabilities[0]
                    percentiles["p50"] = availabilities[n // 2] if n >= 2 else availabilities[0]
                    percentiles["p75"] = availabilities[3 * n // 4] if n >= 4 else availabilities[-1]
                    percentiles["p90"] = availabilities[9 * n // 10] if n >= 10 else availabilities[-1]
                
                response = SwarmHealthMatrixResponse(
                    samples=samples,
                    sample_count=len(samples),
                    resolution=2.5,  # Default resolution
                    rarity_percentiles=percentiles,
                )
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get swarm health matrix")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get swarm health matrix: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_aggressive_discovery_status(self, request: Request) -> Response:
        """Handle GET /api/v1/metrics/torrents/{info_hash}/aggressive-discovery - aggressive discovery status."""
        from ccbt.daemon.ipc_protocol import AggressiveDiscoveryStatusResponse
        from ccbt.config.config import get_config
        
        try:
            info_hash_hex = request.match_info.get("info_hash")
            if not info_hash_hex:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing info_hash parameter",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )
            
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
                
                # Get DHT setup
                dht_setup = getattr(torrent_session, "_dht_setup", None)
                aggressive_mode = getattr(dht_setup, "_aggressive_mode", False) if dht_setup else False
                
                # Get DHT query metrics if available
                dht_metrics = getattr(dht_setup, "_dht_query_metrics", None) if dht_setup else None
                
                # Get current peer count and download rate
                current_peer_count = 0
                current_download_rate = 0.0
                
                if hasattr(torrent_session, "download_manager"):
                    download_manager = torrent_session.download_manager
                    if hasattr(download_manager, "peer_manager"):
                        peer_manager = download_manager.peer_manager
                        if peer_manager and hasattr(peer_manager, "connections"):
                            current_peer_count = len(peer_manager.connections)
                    
                    if hasattr(torrent_session, "piece_manager"):
                        piece_manager = torrent_session.piece_manager
                        if hasattr(piece_manager, "stats"):
                            stats = piece_manager.stats
                            if hasattr(stats, "download_rate"):
                                current_download_rate = stats.download_rate
                
                # Determine reason
                config = get_config()
                popular_threshold = config.discovery.aggressive_discovery_popular_threshold
                active_threshold_kib = config.discovery.aggressive_discovery_active_threshold_kib
                
                reason = "normal"
                if current_peer_count >= popular_threshold:
                    reason = "popular"
                elif current_download_rate / 1024.0 >= active_threshold_kib:
                    reason = "active"
                
                # Get query interval
                query_interval = 15.0  # Default
                if aggressive_mode:
                    if reason == "active":
                        query_interval = config.discovery.aggressive_discovery_interval_active
                    elif reason == "popular":
                        query_interval = config.discovery.aggressive_discovery_interval_popular
                
                max_peers_per_query = config.discovery.aggressive_discovery_max_peers_per_query if aggressive_mode else 50
                
                response = AggressiveDiscoveryStatusResponse(
                    info_hash=info_hash_hex,
                    enabled=aggressive_mode,
                    reason=reason,
                    current_peer_count=current_peer_count,
                    current_download_rate_kib=current_download_rate / 1024.0,
                    popular_threshold=popular_threshold,
                    active_threshold_kib=active_threshold_kib,
                    query_interval=query_interval,
                    max_peers_per_query=max_peers_per_query,
                )
                return web.json_response(response.model_dump())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get aggressive discovery status")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=f"Failed to get aggressive discovery status: {exc}",
                    code="METRICS_ERROR",
                ).model_dump(),
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
                    logger.exception(
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
                    error_msg = result.error or "Failed to add torrent"
                    logger.warning(
                        "Executor returned failure for torrent/magnet %s: %s",
                        req.path_or_magnet[:100],
                        error_msg,
                    )
                    
                    # Check if torrent already exists - return more user-friendly response
                    if error_msg and "already exists" in error_msg.lower():
                        return web.json_response(  # type: ignore[attr-defined]
                            ErrorResponse(
                                error=f"Torrent is already in the list. {error_msg}",
                                code="TORRENT_ALREADY_EXISTS",
                            ).model_dump(),
                            status=409,  # 409 Conflict is more appropriate for "already exists"
                        )
                    
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error=error_msg,
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
            logger.exception("Error removing torrent %s", info_hash)
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
            logger.exception("Error listing torrents")
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
            logger.exception("Error getting torrent status for %s", info_hash)
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
            logger.exception("Error pausing torrent %s", info_hash)
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
            logger.exception("Error resuming torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to resume torrent",
                    code="RESUME_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_restart_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/restart."""
        info_hash = request.match_info["info_hash"]
        try:
            # Pause then resume
            pause_result = await self.executor.execute("torrent.pause", info_hash=info_hash)
            if not pause_result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=pause_result.error or "Failed to pause torrent",
                        code="RESTART_FAILED",
                    ).model_dump(),
                    status=400,
                )
            
            # Small delay before resume
            await asyncio.sleep(0.1)
            
            resume_result = await self.executor.execute("torrent.resume", info_hash=info_hash)
            if resume_result.success and resume_result.data.get("resumed"):
                return web.json_response({"status": "restarted"})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=resume_result.error or "Failed to resume torrent",
                    code="RESTART_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error restarting torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to restart torrent",
                    code="RESTART_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_cancel_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/cancel."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute("torrent.cancel", info_hash=info_hash)
            if result.success and result.data.get("cancelled"):
                return web.json_response({"status": "cancelled", "info_hash": info_hash})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to cancel torrent",
                    code="CANCEL_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error cancelling torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to cancel torrent",
                    code="CANCEL_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_force_start_torrent(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/force-start."""
        info_hash = request.match_info["info_hash"]
        try:
            result = await self.executor.execute("torrent.force_start", info_hash=info_hash)
            if result.success and result.data.get("force_started"):
                return web.json_response({"status": "force_started", "info_hash": info_hash})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to force start torrent",
                    code="FORCE_START_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error force starting torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to force start torrent",
                    code="FORCE_START_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_batch_pause(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/batch/pause."""
        try:
            data = await request.json()
            info_hashes = data.get("info_hashes", [])
            
            results = []
            for info_hash in info_hashes:
                result = await self.executor.execute("torrent.pause", info_hash=info_hash)
                results.append({
                    "info_hash": info_hash,
                    "success": result.success,
                    "error": result.error,
                })
            
            return web.json_response({"results": results})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error in batch pause")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to batch pause",
                    code="BATCH_PAUSE_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_batch_resume(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/batch/resume."""
        try:
            data = await request.json()
            info_hashes = data.get("info_hashes", [])
            
            results = []
            for info_hash in info_hashes:
                result = await self.executor.execute("torrent.resume", info_hash=info_hash)
                results.append({
                    "info_hash": info_hash,
                    "success": result.success,
                    "error": result.error,
                })
            
            return web.json_response({"results": results})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error in batch resume")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to batch resume",
                    code="BATCH_RESUME_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_batch_restart(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/batch/restart."""
        try:
            data = await request.json()
            info_hashes = data.get("info_hashes", [])
            
            results = []
            for info_hash in info_hashes:
                # Pause then resume
                pause_result = await self.executor.execute("torrent.pause", info_hash=info_hash)
                await asyncio.sleep(0.1)
                resume_result = await self.executor.execute("torrent.resume", info_hash=info_hash)
                
                results.append({
                    "info_hash": info_hash,
                    "success": pause_result.success and resume_result.success,
                    "error": resume_result.error if not resume_result.success else pause_result.error,
                })
            
            return web.json_response({"results": results})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error in batch restart")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to batch restart",
                    code="BATCH_RESTART_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_batch_remove(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/batch/remove."""
        try:
            data = await request.json()
            info_hashes = data.get("info_hashes", [])
            remove_data = data.get("remove_data", False)
            
            results = []
            for info_hash in info_hashes:
                result = await self.executor.execute(
                    "torrent.remove", info_hash=info_hash, remove_data=remove_data
                )
                results.append({
                    "info_hash": info_hash,
                    "success": result.success,
                    "error": result.error,
                })
            
            return web.json_response({"results": results})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error in batch remove")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to batch remove",
                    code="BATCH_REMOVE_FAILED",
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

    async def _handle_get_torrent_trackers(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/trackers."""
        info_hash = request.match_info["info_hash"]
        
        try:
            # Convert hex string to bytes for lookup
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
            
            # Get torrent session from session manager
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)
            if not torrent_session:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Torrent not found",
                        code="TORRENT_NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )
            
            # Get tracker information from torrent session
            tracker_infos = []
            
            # Get tracker URLs from torrent data
            tracker_urls: list[str] = []
            if hasattr(torrent_session, "torrent_data"):
                td = torrent_session.torrent_data
                if isinstance(td, dict):
                    if "announce" in td:
                        tracker_urls.append(td["announce"])
                    if "announce_list" in td:
                        for tier in td["announce_list"]:
                            if isinstance(tier, list):
                                tracker_urls.extend(tier)
                            else:
                                tracker_urls.append(tier)
                elif hasattr(td, "announce"):
                    tracker_urls.append(td.announce)
                    if hasattr(td, "announce_list") and td.announce_list:
                        for tier in td.announce_list:
                            if isinstance(tier, list):
                                tracker_urls.extend(tier)
                            else:
                                tracker_urls.append(tier)
            
            # Get tracker status from tracker client
            if hasattr(torrent_session, "tracker") and torrent_session.tracker:
                tracker_client = torrent_session.tracker
                if hasattr(tracker_client, "sessions"):
                    # Get tracker sessions
                    for url, tracker_session_obj in tracker_client.sessions.items():
                        status = "working"
                        if tracker_session_obj.failure_count > 0:
                            status = "error"
                        elif tracker_session_obj.last_announce == 0:
                            status = "updating"
                        
                        # Get scrape results if available
                        seeds = 0
                        peers = 0
                        downloaders = 0
                        if hasattr(tracker_client, "_session_metrics"):
                            metrics = tracker_client._session_metrics.get(url, {})
                            seeds = metrics.get("complete", 0)
                            peers = metrics.get("incomplete", 0)
                            downloaders = metrics.get("incomplete", 0)
                        
                        tracker_infos.append(
                            TrackerInfo(
                                url=url,
                                status=status,
                                seeds=seeds,
                                peers=peers,
                                downloaders=downloaders,
                                last_update=tracker_session_obj.last_announce,
                                error=None if tracker_session_obj.failure_count == 0 else f"Failed {tracker_session_obj.failure_count} times",
                            )
                        )
            
            # Add any trackers from announce_list that aren't in sessions yet
            for url in tracker_urls:
                if url and not any(t.url == url for t in tracker_infos):
                    tracker_infos.append(
                        TrackerInfo(
                            url=url,
                            status="updating",
                            seeds=0,
                            peers=0,
                            downloaders=0,
                            last_update=0.0,
                            error=None,
                        )
                    )
            
            response = TrackerListResponse(
                info_hash=info_hash,
                trackers=tracker_infos,
                count=len(tracker_infos),
            )
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
            
        except Exception as e:
            logger.exception("Error getting torrent trackers")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="INTERNAL_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_add_tracker(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/trackers/add."""
        info_hash = request.match_info["info_hash"]
        try:
            # Validate info hash format
            try:
                _ = bytes.fromhex(info_hash)
            except ValueError:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Invalid info hash format",
                        code="INVALID_INFO_HASH",
                    ).model_dump(),
                    status=400,
                )

            # Parse request body
            data = await request.json()
            req = TrackerAddRequest(**data)

            # Execute command via executor
            result = await self.executor.execute(
                "torrent.add_tracker",
                info_hash=info_hash,
                tracker_url=req.url,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to add tracker",
                        code="ADD_TRACKER_FAILED",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error adding tracker")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to add tracker",
                    code="ADD_TRACKER_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_remove_tracker(self, request: Request) -> Response:
        """Handle DELETE /api/v1/torrents/{info_hash}/trackers/{tracker_url}."""
        info_hash = request.match_info["info_hash"]
        tracker_url = request.match_info.get("tracker_url")
        
        try:
            # Validate info hash format
            try:
                _ = bytes.fromhex(info_hash)
            except ValueError:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Invalid info hash format",
                        code="INVALID_INFO_HASH",
                    ).model_dump(),
                    status=400,
                )

            # URL decode tracker URL if needed
            if tracker_url:
                from urllib.parse import unquote
                tracker_url = unquote(tracker_url)

            if not tracker_url:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Missing tracker_url in path",
                        code="MISSING_TRACKER_URL",
                    ).model_dump(),
                    status=400,
                )

            # Execute command via executor
            result = await self.executor.execute(
                "torrent.remove_tracker",
                info_hash=info_hash,
                tracker_url=tracker_url,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to remove tracker",
                        code="REMOVE_TRACKER_FAILED",
                    ).model_dump(),
                    status=400,
                )

            return web.json_response(result.data)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error removing tracker")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to remove tracker",
                    code="REMOVE_TRACKER_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_torrent_piece_availability(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/piece-availability."""
        info_hash = request.match_info["info_hash"]
        
        try:
            # Convert hex string to bytes for lookup
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
            
            # Get torrent session from session manager
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)
            if not torrent_session:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="Torrent not found",
                        code="TORRENT_NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )
            
            # Get piece availability from piece manager
            availability: list[int] = []
            num_pieces = 0
            max_peers = 0
            
            if hasattr(torrent_session, "piece_manager") and torrent_session.piece_manager:
                piece_manager = torrent_session.piece_manager
                
                # Get number of pieces
                num_pieces = getattr(piece_manager, "num_pieces", 0)
                if num_pieces == 0:
                    num_pieces = len(getattr(piece_manager, "pieces", []))
                
                # Get piece_frequency Counter
                piece_frequency = getattr(piece_manager, "piece_frequency", None)
                if piece_frequency:
                    # Build availability array
                    for piece_idx in range(num_pieces):
                        count = piece_frequency.get(piece_idx, 0)
                        availability.append(count)
                        max_peers = max(max_peers, count)
            
            response = PieceAvailabilityResponse(
                info_hash=info_hash,
                availability=availability,
                num_pieces=num_pieces,
                max_peers=max_peers,
            )
            return web.json_response(response.model_dump())  # type: ignore[attr-defined]
            
        except Exception as e:
            logger.exception("Error getting torrent piece availability")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="INTERNAL_ERROR",
                ).model_dump(),
                status=500,
            )

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
            logger.exception("Error setting rate limits")
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

    async def _handle_refresh_pex(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/pex/refresh."""
        info_hash = request.match_info["info_hash"]
        try:
            success = await self.session_manager.refresh_pex(info_hash)
            if success:
                return web.json_response(  # type: ignore[attr-defined]
                    {"status": "refreshed", "success": True}
                )
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Torrent not found or PEX not available",
                    code="PEX_REFRESH_FAILED",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error refreshing PEX for torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to refresh PEX",
                    code="PEX_REFRESH_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_set_dht_aggressive_mode(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/dht/aggressive."""
        info_hash = request.match_info["info_hash"]
        try:
            # Parse request body for enabled flag
            data = await request.json() if request.content_length else {}
            enabled = data.get("enabled", True)  # Default to True if not specified
            
            success = await self.session_manager.set_dht_aggressive_mode(info_hash, enabled)
            if success:
                return web.json_response(  # type: ignore[attr-defined]
                    {"status": "updated", "success": True, "enabled": enabled}
                )
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error="Torrent not found or DHT not available",
                    code="DHT_AGGRESSIVE_FAILED",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error setting DHT aggressive mode for torrent %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to set DHT aggressive mode",
                    code="DHT_AGGRESSIVE_ERROR",
                ).model_dump(),
                status=500,
            )

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
            logger.exception("Error exporting session state")
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
            logger.exception("Error importing session state")
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
            logger.exception("Error resuming from checkpoint")
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
            logger.exception("Error updating config")
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

    async def _handle_restart_service(self, request: Request) -> Response:
        """Handle POST /api/v1/services/{service_name}/restart."""
        service_name = request.match_info["service_name"]
        try:
            # Map service names to session manager components
            if service_name == "dht":
                # Restart DHT client
                if self.session_manager and self.session_manager.dht_client:
                    await self.session_manager.dht_client.stop()
                    await self.session_manager.dht_client.start()
                    # Emit COMPONENT_RESTARTED event
                    try:
                        await self._emit_websocket_event(
                            EventType.COMPONENT_STOPPED,
                            {"component_name": "dht_client", "status": "stopped"},
                        )
                        await self._emit_websocket_event(
                            EventType.COMPONENT_STARTED,
                            {"component_name": "dht_client", "status": "running"},
                        )
                    except Exception as e:
                        logger.debug("Failed to emit component events: %s", e)
                    return web.json_response({"status": "restarted", "service": service_name})  # type: ignore[attr-defined]
                else:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="DHT client not available",
                            code="SERVICE_NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
            elif service_name == "nat":
                # Restart NAT manager
                if self.session_manager and self.session_manager.nat_manager:
                    await self.session_manager.nat_manager.stop()
                    await self.session_manager.nat_manager.start()
                    return web.json_response({"status": "restarted", "service": service_name})  # type: ignore[attr-defined]
                else:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="NAT manager not available",
                            code="SERVICE_NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
            elif service_name == "tcp_server":
                # Restart TCP server
                if self.session_manager and self.session_manager.tcp_server:
                    await self.session_manager.tcp_server.stop()
                    await self.session_manager.tcp_server.start()
                    return web.json_response({"status": "restarted", "service": service_name})  # type: ignore[attr-defined]
                else:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="TCP server not available",
                            code="SERVICE_NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )
            else:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"Unknown service: {service_name}",
                        code="SERVICE_NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )
        except Exception as e:
            logger.exception("Error restarting service %s", service_name)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or f"Failed to restart service {service_name}",
                    code="RESTART_SERVICE_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_services_status(self, _request: Request) -> Response:
        """Handle GET /api/v1/services/status."""
        try:
            services = {}
            
            if self.session_manager:
                services["dht"] = {
                    "enabled": self.session_manager.dht_client is not None,
                    "status": "running" if self.session_manager.dht_client else "stopped",
                }
                services["nat"] = {
                    "enabled": self.session_manager.nat_manager is not None,
                    "status": "running" if self.session_manager.nat_manager else "stopped",
                }
                services["tcp_server"] = {
                    "enabled": self.session_manager.tcp_server is not None,
                    "status": "running" if self.session_manager.tcp_server else "stopped",
                }
                services["peer_service"] = {
                    "enabled": self.session_manager.peer_service is not None,
                    "status": "running" if self.session_manager.peer_service else "stopped",
                }
            
            services["ipc_server"] = {
                "enabled": True,
                "status": "running",
            }
            
            return web.json_response({"services": services})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error getting services status")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to get services status",
                    code="GET_SERVICES_STATUS_FAILED",
                ).model_dump(),
                status=500,
            )

    # File Selection Handlers

    async def _handle_get_torrent_files(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/files."""
        info_hash = request.match_info["info_hash"]
        try:
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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

    async def _handle_get_metadata_status(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/metadata/status."""
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

        try:
            async with self.session_manager.lock:
                torrent_session = self.session_manager.torrents.get(info_hash_bytes)
                if not torrent_session:
                    return web.json_response(  # type: ignore[attr-defined]
                        ErrorResponse(
                            error="Torrent not found",
                            code="TORRENT_NOT_FOUND",
                        ).model_dump(),
                        status=404,
                    )

                # Check if metadata is available (file_selection_manager exists)
                metadata_available = (
                    hasattr(torrent_session, "file_selection_manager")
                    and torrent_session.file_selection_manager is not None
                )

                # Check if it's a magnet link (no files initially)
                is_magnet = (
                    hasattr(torrent_session, "torrent_data")
                    and isinstance(torrent_session.torrent_data, dict)
                    and torrent_session.torrent_data.get("info_hash") is not None
                    and torrent_session.torrent_data.get("file_info", {}).get("total_length", 0) == 0
                )

                return web.json_response(  # type: ignore[attr-defined]
                    {
                        "info_hash": info_hash,
                        "available": metadata_available,
                        "is_magnet": is_magnet,
                        "ready": metadata_available,
                    }
                )
        except Exception as e:
            logger.exception("Error getting metadata status for %s", info_hash)
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to get metadata status",
                    code="METADATA_STATUS_ERROR",
                ).model_dump(),
                status=500,
            )

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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            _ = bytes.fromhex(info_hash)  # Validate hex format
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
            logger.exception("Error getting scrape result for %s", info_hash)
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

    # XET folder endpoints

    async def _handle_add_xet_folder(self, request: Request) -> Response:
        """Handle POST /api/v1/xet/folders/add."""
        try:
            data = await request.json()
            folder_path = data.get("folder_path")
            if not folder_path:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error="folder_path is required",
                        code="VALIDATION_ERROR",
                    ).model_dump(),
                    status=400,
                )

            result = await self.executor.execute(
                "xet.add_xet_folder",
                folder_path=folder_path,
                tonic_file=data.get("tonic_file"),
                tonic_link=data.get("tonic_link"),
                sync_mode=data.get("sync_mode"),
                source_peers=data.get("source_peers"),
                check_interval=data.get("check_interval"),
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to add XET folder",
                        code="XET_FOLDER_ERROR",
                    ).model_dump(),
                    status=500,
                )

            return web.json_response(  # type: ignore[attr-defined]
                {"status": "added", "folder_key": result.data.get("folder_key", folder_path)}
            )
        except Exception as e:
            logger.exception("Error adding XET folder")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="XET_FOLDER_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_remove_xet_folder(self, request: Request) -> Response:
        """Handle DELETE /api/v1/xet/folders/{folder_key}."""
        try:
            folder_key = request.match_info["folder_key"]

            result = await self.executor.execute(
                "xet.remove_xet_folder",
                folder_key=folder_key,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to remove XET folder",
                        code="XET_FOLDER_ERROR",
                    ).model_dump(),
                    status=500,
                )

            return web.json_response(  # type: ignore[attr-defined]
                {"status": "removed", "folder_key": folder_key}
            )
        except Exception as e:
            logger.exception("Error removing XET folder")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="XET_FOLDER_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_list_xet_folders(self, _request: Request) -> Response:
        """Handle GET /api/v1/xet/folders."""
        try:
            result = await self.executor.execute("xet.list_xet_folders")

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to list XET folders",
                        code="XET_FOLDER_ERROR",
                    ).model_dump(),
                    status=500,
                )

            folders = result.data.get("folders", [])
            return web.json_response({"folders": folders})  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error listing XET folders")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="XET_FOLDER_ERROR",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_xet_folder_status(self, request: Request) -> Response:
        """Handle GET /api/v1/xet/folders/{folder_key}."""
        try:
            folder_key = request.match_info["folder_key"]

            result = await self.executor.execute(
                "xet.get_xet_folder_status",
                folder_key=folder_key,
            )

            if not result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=result.error or "Failed to get XET folder status",
                        code="XET_FOLDER_ERROR",
                    ).model_dump(),
                    status=500,
                )

            status = result.data.get("status")
            if status is None:
                return web.json_response(  # type: ignore[attr-defined]
                    ErrorResponse(
                        error=f"XET folder {folder_key} not found",
                        code="NOT_FOUND",
                    ).model_dump(),
                    status=404,
                )

            return web.json_response(status)  # type: ignore[attr-defined]
        except Exception as e:
            logger.exception("Error getting XET folder status")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e),
                    code="XET_FOLDER_ERROR",
                ).model_dump(),
                status=500,
            )

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

    async def _handle_global_pause_all(self, request: Request) -> Response:
        """Handle POST /api/v1/global/pause-all."""
        try:
            result = await self.executor.execute("torrent.global_pause_all")
            if result.success:
                return web.json_response(result.data)  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to pause all torrents",
                    code="GLOBAL_PAUSE_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error pausing all torrents")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to pause all torrents",
                    code="GLOBAL_PAUSE_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_global_resume_all(self, request: Request) -> Response:
        """Handle POST /api/v1/global/resume-all."""
        try:
            result = await self.executor.execute("torrent.global_resume_all")
            if result.success:
                return web.json_response(result.data)  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to resume all torrents",
                    code="GLOBAL_RESUME_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error resuming all torrents")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to resume all torrents",
                    code="GLOBAL_RESUME_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_global_force_start_all(self, request: Request) -> Response:
        """Handle POST /api/v1/global/force-start-all."""
        try:
            result = await self.executor.execute("torrent.global_force_start_all")
            if result.success:
                return web.json_response(result.data)  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to force start all torrents",
                    code="GLOBAL_FORCE_START_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error force starting all torrents")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to force start all torrents",
                    code="GLOBAL_FORCE_START_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_global_set_rate_limits(self, request: Request) -> Response:
        """Handle POST /api/v1/global/rate-limits."""
        try:
            data = await request.json()
            download_kib = data.get("download_kib", 0)
            upload_kib = data.get("upload_kib", 0)

            result = await self.executor.execute(
                "torrent.global_set_rate_limits",
                download_kib=download_kib,
                upload_kib=upload_kib,
            )
            if result.success:
                return web.json_response({"success": True})  # type: ignore[attr-defined]

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to set global rate limits",
                    code="GLOBAL_RATE_LIMITS_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error setting global rate limits")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to set global rate limits",
                    code="GLOBAL_RATE_LIMITS_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_set_per_peer_rate_limit(self, request: Request) -> Response:
        """Handle POST /api/v1/torrents/{info_hash}/peers/{peer_key}/rate-limit."""
        info_hash = request.match_info["info_hash"]
        peer_key_encoded = request.match_info["peer_key"]
        from urllib.parse import unquote_plus

        peer_key = unquote_plus(peer_key_encoded)

        try:
            data = await request.json()
            upload_limit_kib = data.get("upload_limit_kib", 0)

            result = await self.executor.execute(
                "peer.set_rate_limit",
                info_hash=info_hash,
                peer_key=peer_key,
                upload_limit_kib=upload_limit_kib,
            )
            if result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    {
                        "success": True,
                        "peer_key": peer_key,
                        "upload_limit_kib": upload_limit_kib,
                    }
                )

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to set per-peer rate limit",
                    code="PER_PEER_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error setting per-peer rate limit")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to set per-peer rate limit",
                    code="PER_PEER_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_get_per_peer_rate_limit(self, request: Request) -> Response:
        """Handle GET /api/v1/torrents/{info_hash}/peers/{peer_key}/rate-limit."""
        info_hash = request.match_info["info_hash"]
        peer_key_encoded = request.match_info["peer_key"]
        from urllib.parse import unquote_plus

        peer_key = unquote_plus(peer_key_encoded)

        try:
            result = await self.executor.execute(
                "peer.get_rate_limit",
                info_hash=info_hash,
                peer_key=peer_key,
            )
            if result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    {
                        "success": True,
                        "peer_key": peer_key,
                        "upload_limit_kib": result.data.get("upload_limit_kib", 0),
                    }
                )

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to get per-peer rate limit",
                    code="PER_PEER_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=404,
            )
        except Exception as e:
            logger.exception("Error getting per-peer rate limit")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to get per-peer rate limit",
                    code="PER_PEER_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=500,
            )

    async def _handle_set_all_peers_rate_limit(self, request: Request) -> Response:
        """Handle POST /api/v1/peers/rate-limit."""
        try:
            data = await request.json()
            upload_limit_kib = data.get("upload_limit_kib", 0)

            result = await self.executor.execute(
                "peer.set_all_rate_limits",
                upload_limit_kib=upload_limit_kib,
            )
            if result.success:
                return web.json_response(  # type: ignore[attr-defined]
                    {
                        "success": True,
                        "updated_count": result.data.get("updated_count", 0),
                        "upload_limit_kib": upload_limit_kib,
                    }
                )

            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=result.error or "Failed to set all peers rate limit",
                    code="ALL_PEERS_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=400,
            )
        except Exception as e:
            logger.exception("Error setting all peers rate limit")
            return web.json_response(  # type: ignore[attr-defined]
                ErrorResponse(
                    error=str(e) or "Failed to set all peers rate limit",
                    code="ALL_PEERS_RATE_LIMIT_FAILED",
                ).model_dump(),
                status=500,
            )

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
            logger.exception("Error adding to blacklist")
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
            logger.exception("Error adding to whitelist")
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
            await ws.close(code=4001, message=b"Unauthorized")
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

    async def _setup_event_bridge(self) -> None:
        """Set up event bridge to convert utils.events to IPC WebSocket events."""
        try:
            from ccbt.utils.events import Event, EventHandler, get_event_bus
            
            # Event type mapping from utils.events to IPC EventType
            # Comprehensive mapping of all relevant events for interface/UI consumption
            event_type_mapping = {
                # Metadata events
                "metadata_ready": EventType.METADATA_READY,
                "metadata_fetch_started": EventType.METADATA_FETCH_STARTED,
                "metadata_fetch_progress": EventType.METADATA_FETCH_PROGRESS,
                "metadata_fetch_completed": EventType.METADATA_FETCH_COMPLETED,
                "metadata_fetch_failed": EventType.METADATA_FETCH_FAILED,
                # File events
                "file_selection_changed": EventType.FILE_SELECTION_CHANGED,
                "file_priority_changed": EventType.FILE_PRIORITY_CHANGED,
                "file_progress_updated": EventType.FILE_PROGRESS_UPDATED,
                # Peer events
                "peer_connected": EventType.PEER_CONNECTED,
                "peer_disconnected": EventType.PEER_DISCONNECTED,
                "peer_handshake_complete": EventType.PEER_HANDSHAKE_COMPLETE,
                "peer_bitfield_received": EventType.PEER_BITFIELD_RECEIVED,
                "peer_added": EventType.PEER_CONNECTED,  # Map to PEER_CONNECTED
                "peer_removed": EventType.PEER_DISCONNECTED,  # Map to PEER_DISCONNECTED
                "peer_connection_failed": EventType.PEER_DISCONNECTED,  # Map to PEER_DISCONNECTED
                # Piece events
                "piece_requested": EventType.PIECE_REQUESTED,
                "piece_downloaded": EventType.PIECE_DOWNLOADED,
                "piece_verified": EventType.PIECE_VERIFIED,
                "piece_completed": EventType.PIECE_COMPLETED,
                # Torrent events
                "torrent_added": EventType.TORRENT_ADDED,
                "torrent_removed": EventType.TORRENT_REMOVED,
                "torrent_started": EventType.TORRENT_STATUS_CHANGED,
                "torrent_stopped": EventType.TORRENT_STATUS_CHANGED,
                "torrent_completed": EventType.TORRENT_COMPLETED,
                # Seeding events
                "seeding_started": EventType.SEEDING_STARTED,
                "seeding_stopped": EventType.SEEDING_STOPPED,
                "seeding_stats_updated": EventType.SEEDING_STATS_UPDATED,
                # Tracker events
                "tracker_announce": EventType.TRACKER_ANNOUNCE_STARTED,
                "tracker_announce_success": EventType.TRACKER_ANNOUNCE_SUCCESS,
                "tracker_announce_error": EventType.TRACKER_ANNOUNCE_ERROR,
                "tracker_error": EventType.TRACKER_ANNOUNCE_ERROR,
                # DHT events
                "dht_node_found": EventType.COMPONENT_STARTED,  # Map to component event
                "dht_peer_found": EventType.PEER_CONNECTED,  # Map to peer event
                "dht_query_complete": EventType.COMPONENT_STARTED,  # Map to component event
                "dht_node_added": EventType.COMPONENT_STARTED,
                "dht_node_removed": EventType.COMPONENT_STOPPED,
                "dht_error": EventType.COMPONENT_STOPPED,
                # Performance events
                "performance_metric": EventType.GLOBAL_STATS_UPDATED,
                "bandwidth_update": EventType.GLOBAL_STATS_UPDATED,
                "disk_io_update": EventType.GLOBAL_STATS_UPDATED,
                "global_metrics_update": EventType.GLOBAL_STATS_UPDATED,
                # Service/Component events
                "service_started": EventType.SERVICE_STARTED,
                "service_stopped": EventType.SERVICE_STOPPED,
                "service_restarted": EventType.SERVICE_RESTARTED,
                "component_started": EventType.COMPONENT_STARTED,
                "component_stopped": EventType.COMPONENT_STOPPED,
                # System events
                "system_start": EventType.SERVICE_STARTED,
                "system_stop": EventType.SERVICE_STOPPED,
                "system_error": EventType.COMPONENT_STOPPED,
            }
            
            async def event_bridge_handler(event: Event) -> None:
                """Bridge event from utils.events to IPC WebSocket."""
                try:
                    # Map event type to IPC EventType
                    ipc_event_type = event_type_mapping.get(event.event_type)
                    if ipc_event_type:
                        # Extract data from event - handle both dict and object attributes
                        event_data = {}
                        if hasattr(event, "data") and event.data:
                            event_data = event.data if isinstance(event.data, dict) else event.data.__dict__
                        elif hasattr(event, "__dict__"):
                            # Extract non-internal attributes
                            event_data = {
                                k: v for k, v in event.__dict__.items()
                                if not k.startswith("_") and k != "event_type"
                            }
                        await self._emit_websocket_event(ipc_event_type, event_data)
                except Exception as e:
                    logger.debug("Error bridging event %s to IPC WebSocket: %s", event.event_type, e)
            
            # Register handler for all relevant event types
            event_bus = get_event_bus()
            
            # Ensure event bus is started
            if not event_bus.running:
                await event_bus.start()
            
            # Create a proper EventHandler subclass
            class IPCEventBridgeHandler(EventHandler):
                def __init__(self, bridge_func: Any, ipc_server: Any):
                    super().__init__("ipc_event_bridge")
                    self.bridge_func = bridge_func
                    self.ipc_server = ipc_server
                
                async def handle(self, event: Event) -> None:
                    await self.bridge_func(event)
            
            handler = IPCEventBridgeHandler(event_bridge_handler, self)
            
            for event_type_str in event_type_mapping.keys():
                event_bus.register_handler(event_type_str, handler)
            
            logger.debug("Event bridge set up for IPC WebSocket events (%d event types)", len(event_type_mapping))
        except Exception as e:
            logger.warning("Failed to set up event bridge: %s", e)

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
                ):
                    raise RuntimeError(
                        f"IPC server site.start() completed but no sockets are listening on {self.host}:{self.port}"
                    )
                sockets = self.site._server.sockets  # noqa: SLF001
                # Type guard for len() - sockets might be a sequence
                # Use try/except to handle type checker's conservative analysis
                try:
                    if hasattr(sockets, "__len__"):
                        socket_count = len(sockets)  # type: ignore[arg-type]
                    else:
                        socket_count = 0
                except (TypeError, AttributeError):
                    socket_count = 0
                logger.debug(
                    "IPC server verified: %d socket(s) listening on %s:%d",
                    socket_count,
                    self.host,
                    self.port,
                )
            except OSError as e:
                # Handle binding errors (port in use, permission denied, etc.)
                error_code = e.errno if hasattr(e, "errno") else None
                # sys is imported at module level (line 15), but ensure it's accessible
                import sys as _sys_module  # Re-import to ensure type checker sees it
                if (error_code == 10048 and _sys_module.platform == "win32") or (
                    error_code == 98 and _sys_module.platform != "win32"
                ):
                    # Port already in use - provide detailed resolution steps
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(self.port, "tcp")
                    error_msg = (
                        f"IPC server failed to bind to {self.host}:{self.port}: {e}\n\n"
                        f"{resolution}"
                    )
                    logger.exception("IPC server failed to bind to %s:%d", self.host, self.port)
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

            # Set up event bridge to forward utils.events to WebSocket
            await self._setup_event_bridge()

            # CRITICAL: On Windows, verify the server is actually accepting HTTP connections
            # Socket test alone isn't sufficient - aiohttp might not be ready for HTTP yet
            # If binding to 0.0.0.0, verify via 127.0.0.1; otherwise use the bound host
            import socket

            verify_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host  # nosec B104 - Verification host selection, converts 0.0.0.0 to 127.0.0.1 for testing

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
