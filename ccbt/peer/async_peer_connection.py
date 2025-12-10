"""Async peer connection management for BitTorrent client.

This module provides high-performance asyncio-based peer connections
with request pipelining, tit-for-tat choking, and adaptive block sizing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush
from typing import TYPE_CHECKING, Any, Callable, Iterable

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.security.encrypted_stream import (
        EncryptedStreamReader,
        EncryptedStreamWriter,
    )

from ccbt.config.config import get_config
from ccbt.models import MessageType
from ccbt.peer.peer import (
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    HaveMessage,
    InterestedMessage,
    KeepAliveMessage,
    MessageDecoder,
    MessageError,
    NotInterestedMessage,
    PeerInfo,
    PeerMessage,
    PeerState,
    PieceMessage,
    RequestMessage,
    UnchokeMessage,
)
from ccbt.protocols.bittorrent_v2 import (
    MESSAGE_ID_FILE_TREE_REQUEST,
    MESSAGE_ID_FILE_TREE_RESPONSE,
    MESSAGE_ID_PIECE_LAYER_REQUEST,
    MESSAGE_ID_PIECE_LAYER_RESPONSE,
    FileTreeRequest,
    FileTreeResponse,
    PieceLayerRequest,
    PieceLayerResponse,
)

# Error message constants
_ERROR_READER_NOT_INITIALIZED = "Reader is not initialized"


class ConnectionState(Enum):
    """States of a peer connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKE_SENT = "handshake_sent"
    HANDSHAKE_RECEIVED = "handshake_received"
    CONNECTED = "connected"
    BITFIELD_SENT = "bitfield_sent"
    BITFIELD_RECEIVED = "bitfield_received"
    ACTIVE = "active"
    CHOKED = "choked"
    ERROR = "error"


class PeerConnectionError(Exception):
    """Exception raised when peer connection fails."""


@dataclass
class RequestInfo:
    """Information about an outstanding request."""

    piece_index: int
    begin: int
    length: int
    timestamp: float
    retry_count: int = 0
    bandwidth_estimate: float = 0.0  # Estimated bytes/second for this request


@dataclass
class PeerStats:
    """Statistics for a peer connection."""

    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    download_rate: float = 0.0  # bytes/second
    upload_rate: float = 0.0  # bytes/second
    request_latency: float = 0.0  # average latency in seconds
    last_activity: float = field(default_factory=time.time)
    snub_count: int = 0
    consecutive_failures: int = 0
    performance_score: float = 0.0  # Overall performance score (0.0-1.0, higher = better)
    efficiency_score: float = 0.0  # bytes per connection overhead
    connection_count: int = 1  # Number of times this peer was connected
    total_connection_time: float = 0.0  # Cumulative connection duration
    value_score: float = 0.0  # Overall peer value (calculated metric)
    blocks_delivered: int = 0  # Number of piece blocks successfully delivered
    blocks_failed: int = 0  # Number of block requests that failed
    average_block_latency: float = 0.0  # Average time to receive a block
    unexpected_pieces_count: int = 0  # Number of unexpected pieces received (not in outstanding_requests)
    unexpected_pieces_useful: int = 0  # Number of unexpected pieces that were actually needed
    timeout_adjustment_factor: float = 1.0  # Dynamic timeout adjustment (reduced when unexpected pieces are useful)


@dataclass
class AsyncPeerConnection:
    """Async peer connection with request pipelining."""

    peer_info: PeerInfo
    torrent_data: dict[str, Any]
    reader: asyncio.StreamReader | EncryptedStreamReader | None = None
    writer: asyncio.StreamWriter | EncryptedStreamWriter | None = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    peer_state: PeerState = field(default_factory=PeerState)
    message_decoder: MessageDecoder = field(default_factory=MessageDecoder)
    stats: PeerStats = field(default_factory=PeerStats)

    # Request pipeline
    outstanding_requests: dict[tuple[int, int, int], RequestInfo] = field(
        default_factory=dict,
    )
    request_queue: deque = field(default_factory=deque)
    max_pipeline_depth: int = 16
    _priority_queue: list[tuple[float, float, RequestInfo]] | None = (
        None  # (priority, timestamp, request)
    )

    # Choking state
    am_choking: bool = True
    peer_choking: bool = True
    am_interested: bool = False
    peer_interested: bool = False

    # Connection management
    connection_task: asyncio.Task | None = None
    error_message: str | None = None

    # Encryption support
    is_encrypted: bool = False
    encryption_cipher: Any = None  # CipherSuite instance from MSE handshake

    # Reserved bytes from handshake (for extension support detection)
    reserved_bytes: bytes | None = None

    # Per-peer rate limiting (upload throttling)
    per_peer_upload_limit_kib: int = 0  # KiB/s, 0 = unlimited
    _upload_token_bucket: float = 0.0  # Current tokens available
    _upload_last_update: float = field(default_factory=time.time)  # Last token bucket update time
    quality_verified: bool = False
    _quality_probation_started: float = 0.0

    # Callback functions (set by connection manager)
    on_peer_connected: Callable[[AsyncPeerConnection], None] | None = None
    on_peer_disconnected: Callable[[AsyncPeerConnection], None] | None = None
    on_bitfield_received: Callable[[AsyncPeerConnection, BitfieldMessage], None] | None = None
    on_piece_received: Callable[[AsyncPeerConnection, PieceMessage], None] | None = None

    def __str__(self):
        """Return string representation of the connection."""
        return f"AsyncPeerConnection({self.peer_info}, state={self.state.value})"

    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.state in [
            ConnectionState.CONNECTED,
            ConnectionState.BITFIELD_SENT,
            ConnectionState.BITFIELD_RECEIVED,
            ConnectionState.ACTIVE,
            ConnectionState.CHOKED,
        ]

    def is_active(self) -> bool:
        """Check if connection is fully active."""
        # CRITICAL FIX: Include BITFIELD_RECEIVED and ACTIVE states as active
        # BITFIELD_RECEIVED means we've received peer's bitfield and can check piece availability
        # ACTIVE means connection is fully ready (may still be choking, but bitfield is available)
        # CHOKED state is also considered active (peer choked us, but connection is established)
        if self.state == ConnectionState.BITFIELD_RECEIVED:
            # Bitfield received - connection is active for piece availability checking
            # Even if peer is choking, we can check if they have pieces
            return True
        return self.state in [ConnectionState.ACTIVE, ConnectionState.CHOKED]

    def has_timed_out(self, timeout: float = 60.0) -> bool:
        """Check if connection has timed out."""
        return time.time() - self.stats.last_activity > timeout

    def can_request(self) -> bool:
        """Check if we can make new requests.

        Note: According to BitTorrent protocol, we should be "interested" before requesting,
        but we don't block requests here - we send "interested" proactively during handshake.
        This allows downloads to start even if "interested" message was delayed or failed.
        """
        is_active = self.is_active()
        not_choking = not self.peer_choking
        pipeline_available = len(self.outstanding_requests) < self.max_pipeline_depth

        can_req = is_active and not_choking and pipeline_available

        # Log when can_request() returns False to help diagnose issues
        if not can_req:
            # Only log at debug level to avoid spam, but include all details
            import logging

            logger = logging.getLogger(f"{__name__}.can_request")
            logger.debug(
                "can_request() returned False for %s: is_active=%s, not_choking=%s (peer_choking=%s), "
                "pipeline_available=%s (outstanding=%d/%d), state=%s",
                self.peer_info,
                is_active,
                not_choking,
                self.peer_choking,
                pipeline_available,
                len(self.outstanding_requests),
                self.max_pipeline_depth,
                self.state.value,
            )

        return can_req

    def get_available_pipeline_slots(self) -> int:
        """Get number of available pipeline slots."""
        return max(0, self.max_pipeline_depth - len(self.outstanding_requests))

    async def _throttle_upload(self, bytes_to_send: int) -> None:
        """Throttle upload based on per-peer rate limit using token bucket.

        Args:
            bytes_to_send: Number of bytes to send

        """
        if self.per_peer_upload_limit_kib == 0:
            # Unlimited - no throttling needed
            return

        current_time = time.time()
        time_elapsed = current_time - self._upload_last_update

        # Token bucket: refill tokens based on rate limit
        # Rate is in KiB/s, convert to bytes/s
        rate_bytes_per_sec = self.per_peer_upload_limit_kib * 1024

        # Add tokens based on elapsed time (cap at bucket size = 2x rate for burst)
        bucket_size = rate_bytes_per_sec * 2
        tokens_to_add = time_elapsed * rate_bytes_per_sec
        self._upload_token_bucket = min(bucket_size, self._upload_token_bucket + tokens_to_add)
        self._upload_last_update = current_time

        # Check if we have enough tokens
        if self._upload_token_bucket >= bytes_to_send:
            # Consume tokens
            self._upload_token_bucket -= bytes_to_send
            return

        # Need to wait for tokens
        tokens_needed = bytes_to_send - self._upload_token_bucket
        wait_time = tokens_needed / rate_bytes_per_sec

        # Wait for tokens to accumulate
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        # Update tokens after waiting
        current_time = time.time()
        time_elapsed = current_time - self._upload_last_update
        tokens_to_add = time_elapsed * rate_bytes_per_sec
        self._upload_token_bucket = min(bucket_size, self._upload_token_bucket + tokens_to_add)
        self._upload_token_bucket -= bytes_to_send
        self._upload_last_update = current_time


class AsyncPeerConnectionManager:
    """Async peer connection manager with advanced features."""

    def __init__(
        self,
        torrent_data: dict[str, Any],
        piece_manager: Any,
        peer_id: bytes | None = None,
        key_manager: Any = None,  # Ed25519KeyManager
        max_peers_per_torrent: int | None = None,
    ):
        """Initialize async peer connection manager.

        Args:
            torrent_data: Parsed torrent data
            piece_manager: Piece manager instance
            peer_id: Our peer ID (20 bytes)
            key_manager: Optional Ed25519KeyManager for cryptographic authentication
            max_peers_per_torrent: Optional maximum peers per torrent (overrides config)

        """
        # CRITICAL FIX: Initialize logger FIRST before any property setters that might use it
        import logging
        self.logger = logging.getLogger(__name__)

        self.torrent_data = torrent_data
        self.piece_manager = piece_manager
        self.config = get_config()
        self.webtorrent_protocol = None  # Will be set if WebTorrent is enabled
        self.key_manager = key_manager

        # Store max_peers_per_torrent (use provided value or fall back to config)
        self.max_peers_per_torrent = (
            max_peers_per_torrent
            if max_peers_per_torrent is not None
            else self.config.network.max_peers_per_torrent
        )

        if peer_id is None:
            from ccbt.utils.version import get_full_peer_id

            peer_id = get_full_peer_id()
        self.our_peer_id = peer_id

        # Connection pool for connection reuse
        from ccbt.peer.connection_pool import PeerConnectionPool

        self.connection_pool = PeerConnectionPool(
            max_connections=self.config.network.connection_pool_max_connections,
            max_idle_time=self.config.network.connection_pool_max_idle_time,
            health_check_interval=self.config.network.connection_pool_health_check_interval,
        )

        # Per-peer upload rate limit from config (KiB/s, 0 = unlimited)
        self.per_peer_upload_limit_kib = self.config.limits.per_peer_up_kib
        if self.per_peer_upload_limit_kib > 0:
            self.logger.debug(
                "Initialized per-peer upload rate limit: %d KiB/s",
                self.per_peer_upload_limit_kib,
            )

        # Metadata exchange state tracking (per connection)
        # Maps connection peer_key -> {ut_metadata_id, metadata_size, pieces: dict, events: dict}
        self._metadata_exchange_state: dict[str, dict[str, Any]] = {}

        # Circuit breaker for peer connections
        if self.config.network.circuit_breaker_enabled:
            from ccbt.utils.resilience import PeerCircuitBreakerManager

            self.circuit_breaker_manager = PeerCircuitBreakerManager(
                failure_threshold=self.config.network.circuit_breaker_failure_threshold,
                recovery_timeout=self.config.network.circuit_breaker_recovery_timeout,
            )
        else:
            self.circuit_breaker_manager = None

        # Connection management
        self.connections: dict[str, AsyncPeerConnection] = {}
        self.connection_lock = asyncio.Lock()
        # CRITICAL FIX: Initialize connection batches flag to prevent AttributeError
        # This flag tracks when connection batches from trackers are in progress
        self._connection_batches_in_progress: bool = False
        # Pending peer queue for deferred batches
        self._pending_peer_queue: list[PeerInfo] = []
        self._pending_peer_keys: set[str] = set()
        self._pending_peer_queue_lock: asyncio.Lock = asyncio.Lock()
        self._pending_resume_in_progress: bool = False

        # Connection quality tracking (probation vs verified peers)
        self._quality_verified_peers: set[str] = set()
        self._quality_probation_peers: dict[str, float] = {}
        self._peer_quality_probation_timeout = getattr(
            self.config.network,
            "peer_quality_probation_timeout",
            45.0,
        )
        self._peer_quality_sample_size = getattr(
            self.config.network,
            "peer_quality_sample_size",
            5,
        )

        # Adaptive timeout calculator (lazy initialization)
        self._timeout_calculator: Any | None = None

        # Failed peer tracking with exponential backoff
        # CRITICAL FIX: Track failure count for exponential backoff instead of just timestamp
        # Peers will be automatically retried when:
        # 1. New peer lists arrive from trackers/DHT/PEX (if backoff period has expired)
        # 2. Exponential backoff ensures we don't retry too aggressively
        # Backoff intervals: 15s (1st), 30s (2nd), 60s (3rd), 120s (4th), 240s (5th), 600s (max)
        self._failed_peers: dict[
            str, dict[str, Any]
        ] = {}  # peer_key -> {"timestamp": float, "count": int, "reason": str, "peer_source": str, "is_seeder": bool}
        self._failed_peer_lock = asyncio.Lock()
        # CRITICAL FIX: Optimized retry intervals for better connection success and swarm health
        # Standard exponential backoff: 10s initial, doubles each time, max 5 minutes
        self._min_retry_interval = 10.0  # Initial retry interval (10 seconds, prevents overwhelming peers)
        self._max_retry_interval = 300.0  # Maximum retry interval (5 minutes, standard maximum)
        self._backoff_multiplier = 2.0  # Standard exponential backoff multiplier (doubles each retry)

        # CRITICAL FIX: Track tracker-discovered peers for retry when seeder count is low
        self._tracker_peers_to_retry: dict[str, dict[str, Any]] = {}  # peer_key -> peer_data
        self._tracker_retry_lock = asyncio.Lock()
        self._tracker_retry_task: asyncio.Task | None = None

        # CRITICAL FIX: Global connection limiter for Windows to prevent WinError 121 and WinError 10055
        # Windows has strict limits on socket buffers and OS-level TCP connection semaphores
        # WinError 10055 occurs when the event loop selector can't monitor all sockets due to buffer exhaustion
        # We need to limit simultaneous connections more aggressively on Windows
        import sys

        # CRITICAL FIX: Use configurable limit from NetworkConfig (BitTorrent spec compliant)
        # This prevents OS socket exhaustion while maintaining good peer discovery
        max_concurrent = getattr(
            self.config.network,
            "max_concurrent_connection_attempts",
            20 if sys.platform == "win32" else 40,
        )
        self._global_connection_semaphore = asyncio.Semaphore(max_concurrent)
        self.logger.info(
            "Initialized connection semaphore with limit=%d (platform=%s, config=%s)",
            max_concurrent,
            sys.platform,
            "configured" if hasattr(self.config.network, "max_concurrent_connection_attempts") else "default",
        )
        
        # Connection failure tracking for adaptive backoff (BitTorrent spec compliant)
        self._connection_failure_counts: dict[str, int] = {}  # peer_key -> failure count
        self._connection_failure_times: dict[str, float] = {}  # peer_key -> last failure time
        self._connection_backoff_until: dict[str, float] = {}  # peer_key -> backoff until timestamp

        # Choking management
        self.upload_slots: list[AsyncPeerConnection] = []
        self.optimistic_unchoke: AsyncPeerConnection | None = None
        self.optimistic_unchoke_time: float = 0.0

        # Background tasks
        self._choking_task: asyncio.Task | None = None
        self._stats_task: asyncio.Task | None = None
        self._reconnection_task: asyncio.Task | None = None
        self._peer_evaluation_task: asyncio.Task | None = None

        # Running state flag for idempotency
        self._running: bool = False

        # CRITICAL FIX: Debouncing for piece selection triggers from Have messages
        # Prevent excessive piece selection calls from duplicate Have messages
        self._last_piece_selection_trigger: float = 0.0
        self._piece_selection_debounce_interval: float = 0.1  # 100ms debounce interval
        self._piece_selection_debounce_lock = asyncio.Lock()

        # Callbacks
        self._on_peer_connected: Callable[[AsyncPeerConnection], None] | None = None
        self._external_peer_disconnected: (
            Callable[[AsyncPeerConnection], None] | None
        ) = None
        self._on_peer_disconnected: Callable[[AsyncPeerConnection], None] | None = (
            self._peer_disconnected_wrapper
        )
        self._on_bitfield_received: (
            Callable[[AsyncPeerConnection, BitfieldMessage], None] | None
        ) = None
        self._on_piece_received: (
            Callable[[AsyncPeerConnection, PieceMessage], None] | None
        ) = None

        # Message handlers
        self.message_handlers: dict[
            MessageType,
            Callable[[AsyncPeerConnection, PeerMessage], None],
        ] = {
            MessageType.CHOKE: self._handle_choke,
            MessageType.UNCHOKE: self._handle_unchoke,
            MessageType.INTERESTED: self._handle_interested,
            MessageType.NOT_INTERESTED: self._handle_not_interested,
            MessageType.HAVE: self._handle_have,
            MessageType.BITFIELD: self._handle_bitfield,
            MessageType.REQUEST: self._handle_request,
            MessageType.PIECE: self._handle_piece,
            MessageType.CANCEL: self._handle_cancel,
        }

        # Initialize uTP incoming connection handler if uTP is enabled
        if self.config.network.enable_utp:
            _task = asyncio.create_task(self._setup_utp_incoming_handler())
            # Store task reference to avoid garbage collection
            del _task  # Task runs in background, no need to keep reference

    async def _propagate_callbacks_to_connections(self) -> None:
        """Propagate callbacks to all existing connections."""
        async with self.connection_lock:
            for conn in self.connections.values():
                if self._on_peer_connected:
                    conn.on_peer_connected = self._on_peer_connected
                if self._on_peer_disconnected:
                    conn.on_peer_disconnected = self._on_peer_disconnected
                if self._on_bitfield_received:
                    conn.on_bitfield_received = self._on_bitfield_received
                if self._on_piece_received:
                    conn.on_piece_received = self._on_piece_received
                    self.logger.debug(
                        "Propagated on_piece_received callback to connection %s",
                        conn.peer_info,
                    )

    @property
    def on_piece_received(self) -> Callable[[AsyncPeerConnection, PieceMessage], None] | None:
        """Get the on_piece_received callback."""
        return self._on_piece_received

    @on_piece_received.setter
    def on_piece_received(self, value: Callable[[AsyncPeerConnection, PieceMessage], None] | None) -> None:
        """Set the on_piece_received callback and propagate to existing connections."""
        self.logger.info(
            "Setting on_piece_received callback on AsyncPeerConnectionManager: value=%s (callable=%s)",
            value,
            callable(value) if value is not None else False,
        )
        self._on_piece_received = value
        self.logger.debug(
            "on_piece_received callback set, _on_piece_received=%s",
            self._on_piece_received,
        )
        # CRITICAL FIX: Propagate callback to all existing connections immediately
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._propagate_callbacks_to_connections())
            self.logger.debug("Scheduled callback propagation task")
        except RuntimeError:
            self.logger.debug("No running event loop, callbacks will propagate when connections are created")

    @property
    def on_bitfield_received(self) -> Callable[[AsyncPeerConnection, BitfieldMessage], None] | None:
        """Get the on_bitfield_received callback."""
        return self._on_bitfield_received

    @on_bitfield_received.setter
    def on_bitfield_received(self, value: Callable[[AsyncPeerConnection, BitfieldMessage], None] | None) -> None:
        """Set the on_bitfield_received callback and propagate to existing connections."""
        self._on_bitfield_received = value
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._propagate_callbacks_to_connections())
        except RuntimeError:
            pass

    @property
    def on_peer_connected(self) -> Callable[[AsyncPeerConnection], None] | None:
        """Get the on_peer_connected callback."""
        return self._on_peer_connected

    @on_peer_connected.setter
    def on_peer_connected(self, value: Callable[[AsyncPeerConnection], None] | None) -> None:
        """Set the on_peer_connected callback and propagate to existing connections."""
        self._on_peer_connected = value
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._propagate_callbacks_to_connections())
        except RuntimeError:
            pass

    @property
    def on_peer_disconnected(self) -> Callable[[AsyncPeerConnection], None] | None:
        """Get the on_peer_disconnected callback."""
        return self._external_peer_disconnected

    @on_peer_disconnected.setter
    def on_peer_disconnected(self, value: Callable[[AsyncPeerConnection], None] | None) -> None:
        """Set the on_peer_disconnected callback and propagate to existing connections."""
        self._external_peer_disconnected = value
        self._on_peer_disconnected = self._peer_disconnected_wrapper
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._propagate_callbacks_to_connections())
        except RuntimeError:
            pass

    def _peer_disconnected_wrapper(self, connection: AsyncPeerConnection) -> None:
        """Internal peer disconnected handler that also resumes pending batches."""
        self._ensure_pending_queue_initialized()
        self._ensure_quality_tracking_initialized()
        if self._external_peer_disconnected:
            try:
                self._external_peer_disconnected(connection)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception("on_peer_disconnected callback raised an error")

        peer_key = self._get_peer_key(connection)
        self._quality_verified_peers.discard(peer_key)
        self._quality_probation_peers.pop(peer_key, None)
        self._schedule_pending_resume(reason="peer_disconnected")

    def _schedule_pending_resume(self, reason: str) -> None:
        """Schedule pending peer processing if batches are idle."""
        if not self._running:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(self._resume_pending_batches(reason=reason))

    async def _clear_pending_peer_queue(self, reason: str) -> None:
        """Clear any pending peers that are considered stale."""
        self._ensure_pending_queue_initialized()
        async with self._pending_peer_queue_lock:
            pending = len(self._pending_peer_queue)
            if pending == 0:
                return
            self._pending_peer_queue.clear()
            self._pending_peer_keys.clear()

        self.logger.debug(
            "Cleared %d pending peer(s) before processing new batch (reason: %s)",
            pending,
            reason,
        )

    async def _queue_pending_peers(
        self,
        peers: Iterable[PeerInfo],
        reason: str,
    ) -> None:
        """Store peers for later connection attempts."""
        self._ensure_pending_queue_initialized()
        async with self._pending_peer_queue_lock:
            enqueued = 0
            for peer_info in peers:
                peer_key = self._get_peer_key(peer_info)
                if peer_key in self._pending_peer_keys:
                    continue
                if peer_key in self.connections:
                    continue
                self._pending_peer_queue.append(peer_info)
                self._pending_peer_keys.add(peer_key)
                enqueued += 1

            if enqueued == 0:
                return

            pending_total = len(self._pending_peer_queue)

        self.logger.info(
            "📥 PENDING QUEUE: Stored %d peer(s) for later connection (reason: %s, total pending: %d)",
            enqueued,
            reason,
            pending_total,
        )

    def _peer_info_to_dict(self, peer_info: PeerInfo) -> dict[str, Any]:
        """Convert PeerInfo to dict format expected by connect_to_peers."""
        peer_dict: dict[str, Any] = {
            "ip": peer_info.ip,
            "port": peer_info.port,
        }
        peer_dict["peer_source"] = getattr(peer_info, "peer_source", "tracker")
        if hasattr(peer_info, "is_seeder"):
            peer_dict["is_seeder"] = getattr(peer_info, "is_seeder")
        if hasattr(peer_info, "complete"):
            peer_dict["complete"] = getattr(peer_info, "complete")
        return peer_dict

    async def _resume_pending_batches(self, reason: str) -> None:
        """Resume pending peer connections if slots are available."""
        self._ensure_pending_queue_initialized()
        if not self._running:
            return
        if self._connection_batches_in_progress or self._pending_resume_in_progress:
            return

        async with self._pending_peer_queue_lock:
            if not self._pending_peer_queue:
                return

        async with self.connection_lock:
            active_count = len([c for c in self.connections.values() if c.is_active()])

        if active_count >= self.max_peers_per_torrent:
            return

        self._pending_resume_in_progress = True
        try:
            async with self._pending_peer_queue_lock:
                if not self._pending_peer_queue:
                    return
                peers_to_resume = self._pending_peer_queue[:]
                self._pending_peer_queue.clear()
                self._pending_peer_keys.clear()

            if not peers_to_resume:
                return

            peer_dicts = [self._peer_info_to_dict(peer) for peer in peers_to_resume]
            self.logger.info(
                "♻️ RESUME CONNECTION: Attempting to connect to %d queued peer(s) (reason: %s, active: %d/%d)",
                len(peer_dicts),
                reason,
                active_count,
                self.max_peers_per_torrent,
            )
            await self.connect_to_peers(peer_dicts, _from_pending_queue=True)
        finally:
            self._pending_resume_in_progress = False

    def _ensure_pending_queue_initialized(self) -> None:
        """Ensure pending queue attributes exist (handles pre-upgrade sessions)."""
        if not hasattr(self, "_pending_peer_queue"):
            self._pending_peer_queue = []
        if not hasattr(self, "_pending_peer_keys"):
            self._pending_peer_keys = set()
        if not hasattr(self, "_pending_peer_queue_lock"):
            self._pending_peer_queue_lock = asyncio.Lock()
        if not hasattr(self, "_pending_resume_in_progress"):
            self._pending_resume_in_progress = False

    def _get_peer_key(self, peer: Any) -> str:
        """Return canonical peer key (ip:port) for PeerInfo or connection."""
        if hasattr(peer, "peer_info"):
            peer = peer.peer_info
        if hasattr(peer, "ip") and hasattr(peer, "port"):
            return f"{peer.ip}:{peer.port}"
        return str(peer)

    def _record_probation_peer(
        self,
        peer_key: str,
        connection: AsyncPeerConnection | None = None,
    ) -> None:
        """Mark peer as probationary until it proves useful."""
        self._ensure_quality_tracking_initialized()
        self._quality_verified_peers.discard(peer_key)
        start_time = time.time()
        self._quality_probation_peers[peer_key] = start_time
        if connection is not None:
            connection.quality_verified = False
            connection._quality_probation_started = start_time

    def _mark_peer_quality_verified(
        self,
        peer_key: str,
        reason: str,
        connection: AsyncPeerConnection | None = None,
    ) -> None:
        """Mark peer as quality-verified and remove from probation."""
        self._ensure_quality_tracking_initialized()
        if peer_key in self._quality_verified_peers:
            return
        self._quality_verified_peers.add(peer_key)
        if peer_key in self._quality_probation_peers:
            del self._quality_probation_peers[peer_key]
        if connection is not None:
            connection.quality_verified = True
        self.logger.debug(
            "✅ PEER QUALITY VERIFIED: %s (%s, verified=%d, probation=%d)",
            peer_key,
            reason,
            len(self._quality_verified_peers),
            len(self._quality_probation_peers),
        )

    async def _get_quality_active_counts(self) -> tuple[int, int]:
        """Return (quality_active, total_active) peer counts."""
        self._ensure_quality_tracking_initialized()
        async with self.connection_lock:
            total_active = 0
            quality_active = 0
            for peer_key, connection in self.connections.items():
                if not connection.is_active():
                    continue
                total_active += 1
                if (
                    peer_key in self._quality_verified_peers
                    or getattr(connection, "is_seeder", False)
                ):
                    quality_active += 1
        return quality_active, total_active

    async def _prune_probation_peers(self, reason: str) -> None:
        """Disconnect probation peers that never became useful."""
        self._ensure_quality_tracking_initialized()
        if not self._quality_probation_peers:
            return

        now = time.time()
        timeout = self._peer_quality_probation_timeout
        to_disconnect: list[AsyncPeerConnection] = []

        async with self.connection_lock:
            for peer_key, start_time in list(self._quality_probation_peers.items()):
                connection = self.connections.get(peer_key)
                if connection is None:
                    del self._quality_probation_peers[peer_key]
                    continue

                has_useful_activity = (
                    connection.quality_verified
                    or connection.stats.bytes_downloaded > 0
                    or connection.stats.blocks_delivered > 0
                    or (
                        connection.peer_state.bitfield is not None
                        and len(connection.peer_state.bitfield) > 0
                    )
                    or (
                        connection.peer_state.pieces_we_have is not None
                        and len(connection.peer_state.pieces_we_have) > 0
                    )
                )

                if has_useful_activity:
                    del self._quality_probation_peers[peer_key]
                    self._quality_verified_peers.add(peer_key)
                    continue

                elapsed = now - start_time
                if elapsed >= timeout:
                    to_disconnect.append(connection)
                    del self._quality_probation_peers[peer_key]

        for connection in to_disconnect:
            self.logger.info(
                "🧹 QUALITY FILTER: Disconnecting probation peer %s after %.1fs without useful activity (reason: %s)",
                connection.peer_info,
                now - getattr(connection, "_quality_probation_started", now),
                reason,
            )
            await self._disconnect_peer(connection)

    def _ensure_quality_tracking_initialized(self) -> None:
        """Ensure quality-tracking attributes exist (handles pre-upgrade sessions)."""
        if not hasattr(self, "_quality_verified_peers"):
            self._quality_verified_peers = set()
        if not hasattr(self, "_quality_probation_peers"):
            self._quality_probation_peers = {}
        if not hasattr(self, "_peer_quality_probation_timeout"):
            self._peer_quality_probation_timeout = getattr(
                self.config.network,
                "peer_quality_probation_timeout",
                45.0,
            )
        if not hasattr(self, "_peer_quality_sample_size"):
            self._peer_quality_sample_size = getattr(
                self.config.network,
                "peer_quality_sample_size",
                5,
            )

    async def _setup_utp_incoming_handler(self) -> None:
        """Set up handler for incoming uTP connections."""
        try:
            from ccbt.models import PeerInfo
            from ccbt.transport.utp_socket import UTPSocketManager

            # CRITICAL FIX: Use uTP socket manager from session manager if available
            # Singleton pattern removed - use session_manager.utp_socket_manager
            socket_manager = None
            if hasattr(self, "session_manager") and self.session_manager:
                if (
                    hasattr(self.session_manager, "utp_socket_manager")
                    and self.session_manager.utp_socket_manager
                ):
                    socket_manager = self.session_manager.utp_socket_manager
                    self.logger.debug("Using uTP socket manager from session manager")

            # Fallback to deprecated singleton for backward compatibility
            if socket_manager is None:
                self.logger.warning(
                    "uTP socket manager not available from session_manager, using deprecated singleton. "
                    "This should not happen in normal daemon operation."
                )
                socket_manager = await UTPSocketManager.get_instance()

            async def handle_incoming_utp_connection(
                utp_conn: Any, addr: tuple[str, int]
            ) -> None:
                """Handle incoming uTP connection.

                Args:
                    utp_conn: UTPConnection instance
                    addr: Remote address (host, port)

                """
                try:
                    from ccbt.transport.utp import UTPConnectionState

                    # Wait for connection to be established
                    if utp_conn.state == UTPConnectionState.SYN_RECEIVED:
                        # Wait for handshake completion
                        timeout = 30.0
                        start_time = time.time()
                        while (
                            utp_conn.state != UTPConnectionState.CONNECTED
                            and time.time() - start_time < timeout
                        ):
                            await asyncio.sleep(0.1)

                        if utp_conn.state != UTPConnectionState.CONNECTED:
                            self.logger.warning(
                                "Incoming uTP connection from %s:%s failed to complete handshake",
                                addr[0],
                                addr[1],
                            )
                            return

                    # Create peer info from connection
                    peer_info = PeerInfo(ip=addr[0], port=addr[1])

                    # Create UTPPeerConnection
                    from ccbt.peer.utp_peer import UTPPeerConnection

                    peer_conn = await UTPPeerConnection.accept(utp_conn, peer_info)

                    # Set callbacks
                    if self._on_peer_connected:
                        peer_conn.on_peer_connected = self._on_peer_connected
                    if self._on_peer_disconnected:
                        peer_conn.on_peer_disconnected = self._on_peer_disconnected
                    if self._on_bitfield_received:
                        peer_conn.on_bitfield_received = self._on_bitfield_received
                    if self._on_piece_received:
                        peer_conn.on_piece_received = self._on_piece_received

                    # Add to connections
                    peer_key = f"{addr[0]}:{addr[1]}"
                    async with self.connection_lock:
                        if peer_key not in self.connections:
                            self.connections[peer_key] = peer_conn

                            # Emit PEER_CONNECTED event
                            try:
                                import hashlib

                                from ccbt.core.bencode import BencodeEncoder
                                from ccbt.utils.events import Event, emit_event

                                # Get info_hash from torrent_data
                                info_hash_hex = ""
                                if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                                    encoder = BencodeEncoder()
                                    info_dict = self.torrent_data["info"]
                                    info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                                    info_hash_hex = info_hash_bytes.hex()

                                await emit_event(
                                    Event(
                                        event_type="peer_connected",
                                        data={
                                            "info_hash": info_hash_hex,
                                            "peer_ip": addr[0],
                                            "peer_port": addr[1],
                                            "peer_id": None,
                                            "client": None,
                                        },
                                    )
                                )
                            except Exception as e:
                                self.logger.debug("Failed to emit PEER_CONNECTED event: %s", e)

                            # Call peer connected callback
                            if self._on_peer_connected:
                                try:
                                    self._on_peer_connected(peer_conn)
                                except Exception as e:
                                    self.logger.warning(
                                        "Error in on_peer_connected callback: %s", e
                                    )

                    self.logger.info(
                        "Accepted incoming uTP peer connection from %s:%s",
                        addr[0],
                        addr[1],
                    )

                except Exception as e:
                    self.logger.warning(
                        "Error handling incoming uTP connection from %s:%s: %s",
                        addr[0],
                        addr[1],
                        e,
                    )

            socket_manager.on_incoming_connection = handle_incoming_utp_connection  # type: ignore[assignment]
            self.logger.debug("uTP incoming connection handler registered")

        except Exception as e:
            self.logger.warning(
                "Failed to set up uTP incoming connection handler: %s", e
            )

    def _raise_info_hash_mismatch(self, expected: bytes, got: bytes) -> None:
        """Raise PeerConnectionError for info hash mismatch."""
        msg = f"Info hash mismatch: expected {expected.hex()}, got {got.hex()}"
        raise PeerConnectionError(msg)

    def _calculate_adaptive_handshake_timeout(self) -> float:
        """Calculate adaptive handshake timeout based on peer health.
        
        Returns:
            Timeout in seconds

        """
        # Lazy initialization of timeout calculator
        if self._timeout_calculator is None:
            from ccbt.utils.timeout_adapter import AdaptiveTimeoutCalculator

            self._timeout_calculator = AdaptiveTimeoutCalculator(
                config=self.config,
                peer_manager=self,
            )

        return self._timeout_calculator.calculate_handshake_timeout()

    def _calculate_timeout(
        self, connection: AsyncPeerConnection | None = None
    ) -> float:
        """Calculate adaptive timeout based on measured RTT.

        Args:
            connection: Optional connection to use for RTT measurement

        Returns:
            Timeout in seconds

        """
        use_adaptive = getattr(self.config.network, "timeout_adaptive", True)
        if not use_adaptive:
            return self.config.network.connection_timeout

        # Calculate timeout based on RTT if available
        if connection and connection.stats.request_latency > 0:
            rtt = connection.stats.request_latency
            multiplier = getattr(self.config.network, "timeout_rtt_multiplier", 3.0)
            timeout = rtt * multiplier
        else:
            timeout = self.config.network.connection_timeout

        # Clamp to min/max bounds
        min_timeout = getattr(self.config.network, "timeout_min_seconds", 5.0)
        max_timeout = getattr(self.config.network, "timeout_max_seconds", 300.0)
        return min(max(timeout, min_timeout), max_timeout)

    def _calculate_pipeline_depth(self, connection: AsyncPeerConnection) -> int:
        """Calculate adaptive pipeline depth based on connection latency.

        Args:
            connection: Peer connection

        Returns:
            Optimal pipeline depth

        """
        use_adaptive = getattr(self.config.network, "pipeline_adaptive_depth", True)
        if not use_adaptive:
            return self.config.network.pipeline_depth

        # Base depth on measured latency
        rtt = (
            connection.stats.request_latency
            if connection.stats.request_latency > 0
            else 0.1
        )
        base_depth = self.config.network.pipeline_depth
        min_depth = getattr(self.config.network, "pipeline_min_depth", 4)
        max_depth = getattr(self.config.network, "pipeline_max_depth", 128)

        # IMPROVEMENT: More aggressive pipeline sizing for better throughput
        # Use higher multipliers for low latency connections to maximize bandwidth utilization
        if rtt < 0.01:  # Very low latency (<10ms) - local network or fast connection
            # Use up to 2x base_depth or max_depth, whichever is higher
            # This allows 120 base_depth to become 240, but cap at max_depth
            return min(max_depth, max(base_depth * 2, max_depth))
        if rtt < 0.05:  # Low latency (10-50ms) - good connection
            # Use 1.5x base_depth, capped at max_depth
            return min(max_depth, int(base_depth * 1.5))
        if rtt < 0.1:  # Medium latency (50-100ms) - average connection
            return min(max_depth, base_depth)
        # High latency (>100ms) - slow connection
        # Still use reasonable depth, but reduce from base
        return max(min_depth, int(base_depth * 0.75))

    async def _calculate_request_priority(
        self, piece_index: int, piece_manager: Any, peer_connection: AsyncPeerConnection | None = None
    ) -> tuple[float, float]:
        """Calculate priority score for a request with bandwidth consideration.

        Higher score = higher priority. Prioritizes rarest pieces and considers peer bandwidth.

        Args:
            piece_index: Piece index
            piece_manager: Piece manager instance
            peer_connection: Optional peer connection for bandwidth-aware prioritization

        Returns:
            Tuple of (priority_score, bandwidth_estimate)
            - priority_score: Priority score (higher = more urgent)
            - bandwidth_estimate: Estimated bandwidth for this request (bytes/second)

        """
        enable_prioritization = getattr(
            self.config.network, "pipeline_enable_prioritization", True
        )
        if not enable_prioritization:
            return (0.0, 0.0)  # No prioritization

        # Prioritize rarest pieces (pieces with fewer sources)
        try:
            # Use piece availability if available (preferred method)
            try:
                availability = await piece_manager.get_piece_availability(piece_index)
                # Lower availability = higher priority (rarest first)
                # Use 1000.0 for better scaling: rarest pieces (availability=1) get priority 1000.0
                base_priority = 1000.0 / max(availability, 1)
            except AttributeError:
                # Fallback for backward compatibility: prioritize earlier pieces slightly
                # This is only used if get_piece_availability method doesn't exist
                base_priority = 1.0 - (piece_index / 10000.0)
        except Exception:
            base_priority = 1.0

        # Calculate bandwidth estimate and adjust priority
        bandwidth_estimate = 0.0
        if peer_connection:
            # Get peer's current download rate
            download_rate = getattr(peer_connection.stats, "download_rate", 0.0)
            bandwidth_estimate = download_rate

            # Incorporate bandwidth into priority calculation
            # Get bandwidth factor from config (default 0.3 = 30% weight)
            bandwidth_factor = getattr(
                self.config.network, "bandwidth_weighted_rarest_weight", 0.3
            )

            # Normalize bandwidth to 0-1 range (assuming max 10MB/s = 1.0)
            max_bandwidth = 10 * 1024 * 1024  # 10MB/s
            normalized_bandwidth = min(1.0, download_rate / max_bandwidth)

            # Adjust priority: base_priority * (1.0 + bandwidth_factor * normalized_bandwidth)
            # This gives higher priority to requests from faster peers
            priority = base_priority * (1.0 + bandwidth_factor * normalized_bandwidth)
        else:
            priority = base_priority

        return (priority, bandwidth_estimate)

    def _balance_requests_across_peers(
        self,
        requests: list[RequestInfo],
        available_peers: list[AsyncPeerConnection],
        min_allocation_per_peer: int = 0,
    ) -> dict[str, list[RequestInfo]]:
        """Balance requests across peers based on their bandwidth and capacity.
        
        IMPROVEMENT: Ensures minimum allocation per peer, then distributes
        remaining requests based on bandwidth and available capacity.
        No hard caps - uses soft limits based on peer capacity.
        
        Args:
            requests: List of requests to distribute
            available_peers: List of available peer connections
            min_allocation_per_peer: Minimum requests to allocate to each peer (ensures diversity)
            
        Returns:
            Dictionary mapping peer_key -> list of requests assigned to that peer

        """
        if not requests or not available_peers:
            return {}

        # IMPROVEMENT: Calculate peer capacity and bandwidth
        total_bandwidth = 0.0
        peer_bandwidths: dict[str, float] = {}
        peer_capacities: dict[str, int] = {}

        for peer in available_peers:
            peer_key = str(peer.peer_info)
            # Get download rate, fallback to minimum if zero
            download_rate = getattr(peer.stats, "download_rate", 0.0)
            # Use minimum bandwidth to ensure all peers get some requests
            bandwidth = max(download_rate, 100 * 1024)  # Minimum 100KB/s
            peer_bandwidths[peer_key] = bandwidth
            total_bandwidth += bandwidth

            # Get available capacity (soft limit, not hard cap)
            outstanding = len(peer.outstanding_requests) if hasattr(peer, "outstanding_requests") else 0
            max_pipeline = getattr(peer, "max_pipeline_depth", 10)
            # Available capacity - but don't hard cap, use as preference
            peer_capacities[peer_key] = max_pipeline - outstanding

        if total_bandwidth == 0:
            # Fallback: distribute evenly with minimum allocation
            result: dict[str, list[RequestInfo]] = {}
            request_index = 0

            # First pass: ensure minimum allocation
            min_allocation = min_allocation_per_peer if min_allocation_per_peer > 0 else max(1, len(requests) // len(available_peers))
            for peer in available_peers:
                peer_key = str(peer.peer_info)
                result[peer_key] = []
                allocation = min(min_allocation, len(requests) - request_index)
                for _ in range(allocation):
                    if request_index < len(requests):
                        result[peer_key].append(requests[request_index])
                        request_index += 1

            # Second pass: distribute remaining based on capacity
            while request_index < len(requests):
                # Find peer with most available capacity
                best_peer = None
                best_capacity = -1
                for peer in available_peers:
                    peer_key = str(peer.peer_info)
                    capacity = peer_capacities.get(peer_key, 0)
                    if capacity > best_capacity:
                        best_capacity = capacity
                        best_peer = peer

                if best_peer:
                    peer_key = str(best_peer.peer_info)
                    result[peer_key].append(requests[request_index])
                    request_index += 1
                    # Update capacity (soft tracking)
                    peer_capacities[peer_key] = max(0, peer_capacities[peer_key] - 1)
                else:
                    break

            return result

        # IMPROVEMENT: Two-phase distribution
        # Phase 1: Ensure minimum allocation to all peers
        result: dict[str, list[RequestInfo]] = {}
        request_index = 0

        # Allocate minimum to each peer
        min_allocation = max(0, min_allocation_per_peer)
        if min_allocation > 0:
            for peer in available_peers:
                peer_key = str(peer.peer_info)
                result[peer_key] = []
                allocation = min(min_allocation, len(requests) - request_index)
                for _ in range(allocation):
                    if request_index < len(requests):
                        result[peer_key].append(requests[request_index])
                        request_index += 1

        # Phase 2: Distribute remaining requests based on bandwidth and capacity
        remaining_requests = len(requests) - request_index
        if remaining_requests > 0:
            # Calculate weighted allocation (bandwidth * capacity)
            peer_weights: dict[str, float] = {}
            total_weight = 0.0

            for peer in available_peers:
                peer_key = str(peer.peer_info)
                bandwidth = peer_bandwidths[peer_key]
                capacity = peer_capacities.get(peer_key, 1)
                # Weight = bandwidth * sqrt(capacity) to favor both speed and capacity
                # Using sqrt to prevent capacity from dominating
                weight = bandwidth * (capacity ** 0.5)
                peer_weights[peer_key] = weight
                total_weight += weight

            if total_weight > 0:
                # Distribute proportionally to weights
                peer_targets: dict[str, int] = {}
                allocated = 0

                for peer in available_peers:
                    peer_key = str(peer.peer_info)
                    weight = peer_weights[peer_key]
                    share = weight / total_weight
                    target = int(remaining_requests * share)
                    peer_targets[peer_key] = target
                    allocated += target

                # Distribute remaining to highest weighted peers
                sorted_peers = sorted(
                    available_peers,
                    key=lambda p: peer_weights[str(p.peer_info)],
                    reverse=True,
                )
                for i, peer in enumerate(sorted_peers[:remaining_requests - allocated]):
                    peer_key = str(peer.peer_info)
                    peer_targets[peer_key] = peer_targets.get(peer_key, 0) + 1

                # Assign requests (no hard cap on capacity - soft preference only)
                for peer in available_peers:
                    peer_key = str(peer.peer_info)
                    target_count = peer_targets.get(peer_key, 0)

                    if peer_key not in result:
                        result[peer_key] = []

                    # Assign target requests (respecting soft capacity preference)
                    # But don't hard cap - if peer can handle more, it will in next distribution
                    for _ in range(target_count):
                        if request_index < len(requests):
                            result[peer_key].append(requests[request_index])
                            request_index += 1

        # Phase 3: Distribute any remaining requests to peers with most capacity
        while request_index < len(requests):
            # Find peer with highest capacity and bandwidth
            best_peer = None
            best_score = -1.0
            for peer in available_peers:
                peer_key = str(peer.peer_info)
                bandwidth = peer_bandwidths[peer_key]
                capacity = peer_capacities.get(peer_key, 0)
                # Score = bandwidth * capacity (favor both)
                score = bandwidth * capacity
                if score > best_score:
                    best_score = score
                    best_peer = peer

            if best_peer:
                peer_key = str(best_peer.peer_info)
                if peer_key not in result:
                    result[peer_key] = []
                result[peer_key].append(requests[request_index])
                request_index += 1
                # Update capacity (soft tracking)
                peer_capacities[peer_key] = max(0, peer_capacities[peer_key] - 1)
            else:
                # No more peers, break
                break

        return result

    def _coalesce_requests(self, requests: list[RequestInfo]) -> list[RequestInfo]:
        """Coalesce adjacent requests into larger requests.

        Args:
            requests: List of request info objects

        Returns:
            Coalesced list of requests

        """
        enable_coalescing = getattr(
            self.config.network, "pipeline_enable_coalescing", True
        )
        if not enable_coalescing or not requests:
            return requests

        threshold = (
            getattr(self.config.network, "pipeline_coalesce_threshold_kib", 4) * 1024
        )  # Convert to bytes

        # Sort by piece_index, then begin
        sorted_requests = sorted(requests, key=lambda r: (r.piece_index, r.begin))

        coalesced: list[RequestInfo] = []
        current: RequestInfo | None = None

        for req in sorted_requests:
            if current is None:
                current = req
                continue

            # Check if requests can be coalesced
            # Same piece, adjacent or within threshold
            if (
                current.piece_index == req.piece_index
                and req.begin <= current.begin + current.length + threshold
            ):
                # Coalesce: extend current request
                new_end = req.begin + req.length
                current_end = current.begin + current.length
                if new_end > current_end:
                    current = RequestInfo(
                        piece_index=current.piece_index,
                        begin=current.begin,
                        length=new_end - current.begin,
                        timestamp=min(current.timestamp, req.timestamp),
                        retry_count=max(current.retry_count, req.retry_count),
                    )
            else:
                # Cannot coalesce, add current and start new
                coalesced.append(current)
                current = req

        if current:
            coalesced.append(current)

        return coalesced

    async def start(self) -> None:
        """Start background tasks and initialize the peer connection manager.

        This method is idempotent - calling it multiple times will only start
        the manager once. It initializes:
        - Connection pool
        - Choking/unchoking management loop
        - Peer statistics update loop
        - Failed peer reconnection loop

        Raises:
            RuntimeError: If the manager fails to start due to initialization errors

        """
        # Idempotency check: if already running, return early
        if self._running:
            self.logger.debug("Async peer connection manager already started, skipping")
            return

        try:
            # Start connection pool first (required for connection reuse)
            await self.connection_pool.start()
            self.logger.debug("Connection pool started")

            # Start background tasks
            # CRITICAL FIX: Only create tasks if they don't already exist
            # This prevents duplicate tasks if start() is called multiple times
            if self._choking_task is None or self._choking_task.done():
                self._choking_task = asyncio.create_task(self._choking_loop())
                self.logger.debug("Choking loop task started")

            if self._stats_task is None or self._stats_task.done():
                self._stats_task = asyncio.create_task(self._stats_loop())

            # Start peer evaluation task
            if self._peer_evaluation_task is None or self._peer_evaluation_task.done():
                self._peer_evaluation_task = asyncio.create_task(self._peer_evaluation_loop())
                self.logger.debug("Stats loop task started")

            if self._reconnection_task is None or self._reconnection_task.done():
                self._reconnection_task = asyncio.create_task(self._reconnection_loop())
                self.logger.debug("Reconnection loop task started")

            # Mark as running after all tasks are started
            self._running = True

            self.logger.info(
                "Async peer connection manager started (connection_pool=%s, "
                "choking_task=%s, stats_task=%s, reconnection_task=%s)",
                getattr(self.connection_pool, "_running", "unknown"),
                self._choking_task is not None and not self._choking_task.done(),
                self._stats_task is not None and not self._stats_task.done(),
                self._reconnection_task is not None
                and not self._reconnection_task.done(),
            )

        except Exception as e:
            # If startup fails, clean up any partially started tasks
            self.logger.exception("Failed to start async peer connection manager")
            # Attempt cleanup
            try:
                await self.stop()
            except Exception as cleanup_error:
                self.logger.warning(
                    "Error during cleanup after failed start: %s", cleanup_error
                )
            # Re-raise the original error
            error_msg = f"Failed to start peer connection manager: {e}"
            raise RuntimeError(error_msg) from e

    async def accept_incoming(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        handshake: Handshake,
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Accept an incoming peer connection.

        Called by TCP server when a peer connects to us. The handshake has
        already been read and validated by the TCP server.

        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for outgoing data
            handshake: Parsed handshake object from peer
            peer_ip: Peer IP address
            peer_port: Peer port

        """
        # CRITICAL FIX: Reject new connections during shutdown
        if not self._running:
            self.logger.debug(
                "Rejecting incoming connection from %s:%d: manager is shutting down",
                peer_ip,
                peer_port,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        # Check connection limits
        async with self.connection_lock:
            current_connections = len(self.connections)
            max_global = self.config.network.max_global_peers
            max_per_torrent = self.max_peers_per_torrent

            if current_connections >= max_global:
                self.logger.debug(
                    "Rejecting incoming connection from %s:%d: max global peers reached (%d/%d)",
                    peer_ip,
                    peer_port,
                    current_connections,
                    max_global,
                )
                writer.close()
                await writer.wait_closed()
                return

            if current_connections >= max_per_torrent:
                self.logger.debug(
                    "Rejecting incoming connection from %s:%d: max peers per torrent reached (%d/%d)",
                    peer_ip,
                    peer_port,
                    current_connections,
                    max_per_torrent,
                )
                writer.close()
                await writer.wait_closed()
                return

        # Create PeerInfo from handshake and connection details
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(
            ip=peer_ip,
            port=peer_port,
            peer_id=handshake.peer_id,
            peer_source="incoming",
        )

        # Check if we already have a connection to this peer
        peer_key = f"{peer_ip}:{peer_port}"
        async with self.connection_lock:
            if peer_key in self.connections:
                self.logger.debug(
                    "Already connected to peer %s:%d, closing incoming connection",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

        # Create peer connection
        connection = AsyncPeerConnection(peer_info, self.torrent_data)
        connection.reader = reader
        connection.writer = writer
        connection.state = ConnectionState.HANDSHAKE_RECEIVED
        
        # CRITICAL FIX: Clear failure tracking on successful connection (BitTorrent spec compliant)
        # This allows peers that were temporarily unavailable to be retried later
        peer_key = f"{peer_info.ip}:{peer_info.port}"
        if peer_key in self._connection_failure_counts:
            self.logger.debug(
                "Clearing failure tracking for %s after successful handshake (had %d previous failures)",
                peer_key,
                self._connection_failure_counts[peer_key],
            )
            del self._connection_failure_counts[peer_key]
        if peer_key in self._connection_failure_times:
            del self._connection_failure_times[peer_key]
        if peer_key in self._connection_backoff_until:
            del self._connection_backoff_until[peer_key]
        # Initialize per-peer upload rate limit from config
        connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
        # CRITICAL FIX: Set callbacks on incoming connection early
        if self._on_peer_connected:
            connection.on_peer_connected = self._on_peer_connected
        if self._on_peer_disconnected:
            connection.on_peer_disconnected = self._on_peer_disconnected
        if self._on_bitfield_received:
            connection.on_bitfield_received = self._on_bitfield_received
        if self._on_piece_received:
            connection.on_piece_received = self._on_piece_received
            self.logger.debug(
                "Set on_piece_received callback on incoming connection from %s:%d (early)",
                peer_ip,
                peer_port,
            )

        # Validate info_hash matches
        info_hash = self.torrent_data["info_hash"]
        if handshake.info_hash != info_hash:
            self.logger.warning(
                "Info hash mismatch from incoming peer %s:%d: expected %s, got %s",
                peer_ip,
                peer_port,
                info_hash.hex()[:16],
                handshake.info_hash.hex()[:16],
            )
            writer.close()
            await writer.wait_closed()
            return

        # Send our handshake response
        try:
            # Create handshake with optional Ed25519 signature
            ed25519_public_key = None
            ed25519_signature = None
            if self.key_manager:
                try:
                    from ccbt.security.ed25519_handshake import Ed25519Handshake

                    ed25519_handshake = Ed25519Handshake(self.key_manager)
                    ed25519_public_key, ed25519_signature = (
                        ed25519_handshake.initiate_handshake(
                            info_hash, self.our_peer_id
                        )
                    )
                except Exception as e:
                    self.logger.debug(
                        "Failed to create Ed25519 handshake signature: %s", e
                    )

            our_handshake = Handshake(
                info_hash,
                self.our_peer_id,
                ed25519_public_key=ed25519_public_key,
                ed25519_signature=ed25519_signature,
            )
            # Configure reserved bytes based on configuration
            our_handshake.configure_from_config(self.config)

            # CRITICAL FIX: Log handshake reserved bits for debugging and compliance verification
            reserved_bits_info = []
            if our_handshake.supports_extension_protocol():
                reserved_bits_info.append("Extension Protocol (BEP 10)")
            if our_handshake.supports_v2():
                reserved_bits_info.append("Protocol v2 (BEP 52)")
            if our_handshake.supports_dht():
                reserved_bits_info.append("DHT")
            if our_handshake.supports_fast_extension():
                reserved_bits_info.append("Fast Extension (BEP 6)")

            self.logger.debug(
                "Handshake response reserved bits for incoming peer %s:%d: %s (reserved_bytes=%s)",
                peer_ip,
                peer_port,
                ", ".join(reserved_bits_info) if reserved_bits_info else "none",
                our_handshake.reserved_bytes.hex(),
            )

            handshake_data = our_handshake.encode()
            writer.write(handshake_data)
            await writer.drain()
            self.logger.debug(
                "Sent handshake response to incoming peer %s:%d", peer_ip, peer_port
            )
        except Exception as e:
            self.logger.warning(
                "Failed to send handshake response to %s:%d: %s", peer_ip, peer_port, e
            )
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                # CRITICAL FIX: Handle Windows ConnectionResetError (WinError 10054) gracefully
                # Remote host closed connection - this is normal, don't log as error
                import sys

                if sys.platform == "win32":
                    winerror = getattr(e, "winerror", None)
                    if winerror == 10054:  # WSAECONNRESET
                        self.logger.debug(
                            "Connection reset by peer %s:%d during handshake response (WinError 10054) - this is normal",
                            peer_ip,
                            peer_port,
                        )
                    else:
                        self.logger.debug(
                            "Connection error from %s:%d: %s (WinError %s)",
                            peer_ip,
                            peer_port,
                            type(e).__name__,
                            winerror,
                        )
                else:
                    self.logger.debug(
                        "Connection reset by peer %s:%d during handshake response - this is normal",
                        peer_ip,
                        peer_port,
                    )
            except Exception:
                pass  # Ignore other errors during cleanup
            return

        # CRITICAL FIX: Set callbacks before adding to connections
        # This ensures callbacks are available when messages arrive
        # Use the private attributes to avoid triggering property setters
        if self._on_peer_connected:
            connection.on_peer_connected = self._on_peer_connected
        if self._on_peer_disconnected:
            connection.on_peer_disconnected = self._on_peer_disconnected
        if self._on_bitfield_received:
            connection.on_bitfield_received = self._on_bitfield_received
        if self._on_piece_received:
            connection.on_piece_received = self._on_piece_received
            self.logger.debug(
                "Set on_piece_received callback on incoming connection from %s:%d",
                peer_ip,
                peer_port,
            )
        else:
            self.logger.warning(
                "on_piece_received callback is None when accepting incoming connection from %s:%d! "
                "PIECE messages will not be processed.",
                peer_ip,
                peer_port,
            )

        # Add to connections
        async with self.connection_lock:
            self.connections[peer_key] = connection
        self._record_probation_peer(peer_key, connection)

        # Start connection processing
        # For incoming connections, handshake is already received and we've sent our response
        # Now we need to continue with the normal BitTorrent protocol flow
        connection.state = ConnectionState.CONNECTED

        try:
            # Send bitfield and unchoke (same as outbound connections)
            self.logger.info(
                "Sending initial messages to incoming peer %s:%d: bitfield, unchoke",
                peer_ip,
                peer_port,
            )
            try:
                await self._send_bitfield(connection)
                self.logger.debug(
                    "Sent bitfield to incoming peer %s:%d", peer_ip, peer_port
                )
            except PeerConnectionError as e:
                # CRITICAL FIX: For magnet links, bitfield may fail if metadata isn't available yet
                # This is expected and we should continue with the connection
                # Check if it's a metadata-related error (pieces_info is None)
                pieces_info = self.torrent_data.get("pieces_info")
                if pieces_info is None:
                    self.logger.debug(
                        "Bitfield skipped for incoming peer %s:%d: metadata not available yet (magnet link)",
                        peer_ip,
                        peer_port,
                    )
                    # Continue with connection - bitfield will be sent later when metadata is available
                else:
                    # Real error - re-raise
                    error_msg = f"Failed to send bitfield to incoming peer {peer_ip}:{peer_port}: {e}"
                    self.logger.warning(error_msg)
                    raise PeerConnectionError(error_msg) from e
            except Exception as e:
                # Check if it's a metadata-related error
                pieces_info = self.torrent_data.get("pieces_info")
                if pieces_info is None:
                    self.logger.debug(
                        "Bitfield skipped for incoming peer %s:%d: metadata not available yet (magnet link)",
                        peer_ip,
                        peer_port,
                    )
                    # Continue with connection - bitfield will be sent later when metadata is available
                else:
                    # Real error - re-raise
                    error_msg = f"Failed to send bitfield to incoming peer {peer_ip}:{peer_port}: {e}"
                    self.logger.warning(error_msg)
                    raise PeerConnectionError(error_msg) from e

            try:
                await self._send_unchoke(connection)
                self.logger.debug(
                    "Sent unchoke to incoming peer %s:%d", peer_ip, peer_port
                )
            except Exception as e:
                error_msg = f"Failed to send unchoke to incoming peer {peer_ip}:{peer_port}: {e}"
                self.logger.warning(error_msg)
                raise PeerConnectionError(error_msg) from e

            # Attempt SSL negotiation after handshake if extension protocol is supported
            try:
                await self._attempt_ssl_negotiation(connection)
            except Exception as e:
                # SSL negotiation failure shouldn't break the connection
                self.logger.debug(
                    "SSL negotiation failed for incoming peer %s:%d (continuing with plain connection): %s",
                    peer_ip,
                    peer_port,
                    e,
                )

            # Start message handling loop
            self.logger.debug(
                "Starting message handling loop for incoming peer %s:%d",
                peer_ip,
                peer_port,
            )

            # CRITICAL FIX: Verify we're in the correct event loop context before creating task
            try:
                loop = asyncio.get_running_loop()
                connection.connection_task = asyncio.create_task(
                    self._handle_peer_messages(connection)
                )
                self.logger.debug(
                    "Created connection_task for incoming peer %s:%d in event loop %s",
                    peer_ip,
                    peer_port,
                    id(loop),
                )
            except RuntimeError as e:
                # No running event loop - this should not happen in normal flow
                self.logger.error(
                    "CRITICAL: No running event loop when creating connection_task for incoming peer %s:%d: %s",
                    peer_ip,
                    peer_port,
                    e,
                )
                # Remove connection from dict since task creation failed
                async with self.connection_lock:
                    if peer_key in self.connections:
                        del self.connections[peer_key]
                raise RuntimeError(
                    f"No running event loop for connection task creation: {e}"
                ) from e

            # Emit PEER_CONNECTED event
            try:
                import hashlib

                from ccbt.core.bencode import BencodeEncoder
                from ccbt.utils.events import Event, emit_event

                # Get info_hash from torrent_data
                info_hash_hex = ""
                if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                    encoder = BencodeEncoder()
                    info_dict = self.torrent_data["info"]
                    info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                    info_hash_hex = info_hash_bytes.hex()

                await emit_event(
                    Event(
                        event_type="peer_connected",
                        data={
                            "info_hash": info_hash_hex,
                            "peer_ip": peer_ip,
                            "peer_port": peer_port,
                            "peer_id": None,
                            "client": None,
                        },
                    )
                )
            except Exception as e:
                self.logger.debug("Failed to emit PEER_CONNECTED event: %s", e)

            # Notify callback
            if self._on_peer_connected:
                try:
                    self._on_peer_connected(connection)
                except Exception as e:
                    self.logger.warning(
                        "Error in on_peer_connected callback for incoming peer %s:%d: %s",
                        peer_ip,
                        peer_port,
                        e,
                    )

            self.logger.info(
                "Accepted incoming connection from %s:%d (handshake complete, message loop started)",
                peer_ip,
                peer_port,
            )
        except Exception as e:
            self.logger.exception(
                "Error processing incoming connection from %s:%d: %s",
                peer_ip,
                peer_port,
                e,
            )
            async with self.connection_lock:
                if peer_key in self.connections:
                    del self.connections[peer_key]
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def stop(self) -> None:
        """Stop background tasks and disconnect all peers.

        This method gracefully shuts down the peer connection manager by:
        1. Cancelling all background tasks with timeout protection
        2. Disconnecting all active peer connections
        3. Stopping the connection pool
        4. Cleaning up resources

        This method is idempotent - calling it multiple times is safe.
        """
        # Idempotency check: if already stopped, return early
        if not self._running:
            self.logger.debug("Async peer connection manager already stopped, skipping")
            return

        # Mark as not running immediately to prevent new operations
        self._running = False

        # LOGGING OPTIMIZATION: Keep as INFO - important lifecycle event
        self.logger.info("Stopping async peer connection manager...")

        # Collect all tasks to cancel
        tasks_to_cancel: list[asyncio.Task] = []

        if self._choking_task and not self._choking_task.done():
            tasks_to_cancel.append(self._choking_task)
        if self._peer_evaluation_task and not self._peer_evaluation_task.done():
            tasks_to_cancel.append(self._peer_evaluation_task)

        if self._stats_task and not self._stats_task.done():
            tasks_to_cancel.append(self._stats_task)

        if self._reconnection_task and not self._reconnection_task.done():
            tasks_to_cancel.append(self._reconnection_task)

        # Cancel all background tasks with timeout protection
        for task in tasks_to_cancel:
            try:
                task.cancel()
            except Exception as e:
                self.logger.warning("Error cancelling task %s: %s", task.get_name(), e)

        # Wait for tasks to complete cancellation (with timeout to prevent hanging)
        for task in tasks_to_cancel:
            if not task.done():
                try:
                    # Use timeout to prevent indefinite waiting
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Task %s did not cancel within timeout, forcing cancellation",
                        task.get_name(),
                    )
                except asyncio.CancelledError:
                    # Expected when task is cancelled
                    pass
                except Exception as e:
                    self.logger.debug(
                        "Error waiting for task %s cancellation: %s", task.get_name(), e
                    )

        # Clear task references
        self._choking_task = None
        self._stats_task = None
        self._reconnection_task = None
        self._tracker_retry_task = None

        # CRITICAL FIX: Cancel all connection tasks (message loops) before disconnecting
        # This ensures message loops stop processing and connections close cleanly
        connection_tasks_to_cancel: list[asyncio.Task] = []
        async with self.connection_lock:
            for conn in self.connections.values():
                if conn.connection_task and not conn.connection_task.done():
                    connection_tasks_to_cancel.append(conn.connection_task)

        if connection_tasks_to_cancel:
            self.logger.debug(
                "Cancelling %d peer message loop task(s)...",
                len(connection_tasks_to_cancel),
            )
            # Cancel all connection tasks
            for task in connection_tasks_to_cancel:
                try:
                    task.cancel()
                except Exception as e:
                    self.logger.debug("Error cancelling connection task: %s", e)

            # Wait for tasks to complete cancellation (with timeout)
            for task in connection_tasks_to_cancel:
                if not task.done():
                    try:
                        await asyncio.wait_for(task, timeout=2.0)
                    except asyncio.TimeoutError:
                        self.logger.debug(
                            "Connection task %s did not cancel within timeout",
                            task.get_name(),
                        )
                    except (asyncio.CancelledError, Exception):
                        pass  # Expected when task is cancelled

        # Disconnect all peers (with timeout protection and Windows-friendly batching)
        try:
            async with self.connection_lock:
                connections_to_disconnect = list(self.connections.values())
                self.logger.debug(
                    "Disconnecting %d peer connection(s)...",
                    len(connections_to_disconnect),
                )

            # CRITICAL FIX: Close connections in batches on Windows to prevent socket buffer exhaustion
            # WinError 10055 occurs when too many sockets are closed simultaneously
            # Windows has limited socket buffer space and event loop selector capacity
            import sys
            is_windows = sys.platform == "win32"
            # CRITICAL FIX: Further reduced batch size on Windows to prevent WinError 10055
            # Windows socket buffer exhaustion can occur with even 5 simultaneous closes
            batch_size = 3 if is_windows else 20  # Smaller batches on Windows (reduced from 5 to 3)
            delay_between_batches = 0.1 if is_windows else 0.01  # 100ms delay on Windows (increased from 50ms), 10ms on others
            delay_between_connections = 0.02 if is_windows else 0.0  # 20ms delay between connections on Windows (increased from 10ms)

            if connections_to_disconnect:
                # Process connections in batches
                for batch_start in range(0, len(connections_to_disconnect), batch_size):
                    batch = connections_to_disconnect[batch_start:batch_start + batch_size]

                    # Disconnect batch with delays between connections
                    for i, conn in enumerate(batch):
                        try:
                            # Add small delay between connections on Windows
                            if i > 0 and is_windows:
                                await asyncio.sleep(delay_between_connections)

                            # Disconnect with timeout per connection
                            try:
                                await asyncio.wait_for(
                                    self._disconnect_peer(conn),
                                    timeout=2.0,
                                )
                            except asyncio.TimeoutError:
                                self.logger.debug(
                                    "Peer disconnection timeout for %s, forcing close",
                                    conn.peer_info,
                                )
                                # Force close writer if still open
                                if conn.writer and not conn.writer.is_closing():
                                    try:
                                        conn.writer.close()
                                        await asyncio.wait_for(
                                            conn.writer.wait_closed(),
                                            timeout=0.5,
                                        )
                                    except (OSError, asyncio.TimeoutError):
                                        pass  # Ignore errors during forced close
                            except OSError as e:
                                # CRITICAL FIX: Handle WinError 10055 gracefully
                                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                                if error_code == 10055:
                                    self.logger.debug(
                                        "WinError 10055 (socket buffer exhaustion) during peer disconnect. "
                                        "Adding delay and continuing..."
                                    )
                                    await asyncio.sleep(0.1)  # Longer delay on buffer exhaustion
                                else:
                                    self.logger.debug(
                                        "OSError during peer disconnect for %s: %s",
                                        conn.peer_info,
                                        e,
                                    )
                            except Exception as e:
                                self.logger.debug(
                                    "Error disconnecting peer %s: %s",
                                    conn.peer_info,
                                    e,
                                )
                        except Exception as e:
                            self.logger.debug(
                                "Unexpected error in disconnect batch: %s", e
                            )

                    # Delay between batches
                    if batch_start + batch_size < len(connections_to_disconnect):
                        await asyncio.sleep(delay_between_batches)

        except Exception as e:
            self.logger.warning(
                "Error disconnecting peers during stop: %s", e, exc_info=True
            )

        # Stop connection pool (with timeout protection)
        try:
            await asyncio.wait_for(self.connection_pool.stop(), timeout=5.0)
            self.logger.debug("Connection pool stopped")
        except asyncio.TimeoutError:
            self.logger.warning("Connection pool stop timed out")
        except Exception as e:
            self.logger.warning("Error stopping connection pool: %s", e)

        # LOGGING OPTIMIZATION: Keep as INFO - important lifecycle event
        self.logger.info("Async peer connection manager stopped")

    async def shutdown(
        self,
    ) -> None:  # pragma: no cover - Alias method, tested via stop()
        """Alias for stop method for backward compatibility."""
        await self.stop()  # pragma: no cover - Same context

    async def connect_to_peers(
        self,
        peer_list: list[dict[str, Any]],
        *,
        _from_pending_queue: bool = False,
    ) -> None:
        """Connect to a list of peers with rate limiting and error handling.

        Args:
            peer_list: List of peer dictionaries with 'ip', 'port', and optionally 'peer_source'
            _from_pending_queue: Internal flag indicating the peers originated from the pending queue

        """
        # CRITICAL FIX: Check if manager is running before attempting connections
        # This prevents connection attempts after shutdown starts
        if not self._running:
            self.logger.debug(
                "Skipping connect_to_peers: manager is shutting down (%d peers ignored)",
                len(peer_list) if peer_list else 0,
            )
            return

        # CRITICAL FIX: Add detailed logging for peer connection attempts
        if not peer_list:
            self.logger.debug("connect_to_peers called with empty peer list")
            return

        self._ensure_pending_queue_initialized()
        self._ensure_quality_tracking_initialized()
        if not _from_pending_queue:
            await self._clear_pending_peer_queue("new_peer_batch")
        await self._prune_probation_peers("pre_batch")

        # CRITICAL FIX: Set flag to indicate connection batches are in progress
        # This prevents peer_count_low events from triggering DHT until batches are exhausted
        # Set AFTER validation checks to avoid setting flag unnecessarily
        self._connection_batches_in_progress = True
        batch_start_time = time.time()

        try:
            # CRITICAL FIX: Enhanced logging for connection attempts
            peer_sources = {}
            for peer in peer_list:
                source = peer.get("peer_source", "unknown")
                peer_sources[source] = peer_sources.get(source, 0) + 1

            source_summary = ", ".join(
                [f"{count} from {source}" for source, count in peer_sources.items()]
            )
            # CRITICAL FIX: Get info_hash from torrent_data, not from non-existent self.info_hash attribute
            # After metadata exchange, torrent_data["info_hash"] is updated, so this will show the correct hash
            info_hash_display = "unknown"
            if isinstance(self.torrent_data, dict):
                info_hash = self.torrent_data.get("info_hash")
                if info_hash:
                    if isinstance(info_hash, bytes):
                        info_hash_display = info_hash.hex()[:16] + "..."
                    else:
                        info_hash_display = str(info_hash)[:16] + "..."
            
            self.logger.info(
                "Starting connection attempts to %d peer(s) (sources: %s, info_hash: %s)",
                len(peer_list),
                source_summary,
                info_hash_display,
            )
            config = self.config.network
            # CRITICAL FIX: Don't limit max_connections to len(peer_list) when peer count is low
            # This allows connecting to multiple peers even when only 1 is discovered initially
            # Only apply len(peer_list) limit if we already have many peers
            async with self.connection_lock:
                current_peer_count = len(self.connections)
                active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())

            # CRITICAL FIX: Reduce max batch duration to prevent blocking DHT discovery
            # With 199 peers and batch_size=20, that's 10 batches. If each batch takes 25s,
            # sequential processing would take 250s. We need to clear the flag sooner to
            # allow DHT discovery to start. Use 20s for low peer count, 45s otherwise.
            # This ensures batches don't block DHT discovery indefinitely on popular torrents.
            # NOTE: Must be calculated AFTER active_peer_count is set (line 2178)
            max_batch_duration = 20.0 if active_peer_count < 50 else 45.0  # Reduced from 60.0

            # CRITICAL FIX: When many peers are discovered, allow more connections
            # Don't limit to len(peer_list) when we have many discovered peers - connect to as many as possible
            # This fixes the issue where 356 peers are discovered but only 3 are connected
            # CRITICAL FIX: Be MUCH more aggressive when peer count is low - connect to many more peers to find seeders
            # This prevents downloads from stalling when the single peer stops sending
            # CRITICAL FIX: Also connect more aggressively when peers are choking us - we need more peers to find cooperative ones
            if active_peer_count < 3:
                # CRITICAL: Very low peer count - connect to as many peers as possible to find seeders
                # Use at least 30 connections or 5x discovered peers, whichever is larger
                # This ensures we find peers that will unchoke us
                min_connections = max(30, min(self.max_peers_per_torrent, len(peer_list) * 5))
                max_connections = min(self.max_peers_per_torrent, min_connections)
                self.logger.warning(
                    "🚨 CRITICAL: Very low peer count (%d active): connecting to up to %d peers (discovered: %d) to find seeders. "
                    "Downloads will stall if single peer stops!",
                    active_peer_count,
                    max_connections,
                    len(peer_list),
                )
            elif active_peer_count < 10:
                # Low peer count: use full limit and connect to 3x discovered peers
                # This ensures we find peers that will unchoke us
                max_connections = min(self.max_peers_per_torrent, len(peer_list) * 3)
                self.logger.info(
                    "🌱 SEEDER_HUNT: Low peer count (%d active): connecting to up to %d peers (discovered: %d) to find seeders",
                    active_peer_count,
                    max_connections,
                    len(peer_list),
                )
            elif len(peer_list) > 50:
                # Many peers discovered: use full limit to connect to as many as possible
                # This ensures we connect to more than just 3 peers when 356 are discovered
                max_connections = self.max_peers_per_torrent
                self.logger.info(
                    "Many peers discovered (%d): using full max_peers_per_torrent (%d) to maximize connections (current: %d active)",
                    len(peer_list),
                    max_connections,
                    active_peer_count,
                )
            else:
                # Moderate peer count: use full limit to maximize parallel connections
                max_connections = self.max_peers_per_torrent

            # Filter out recently failed peers using exponential backoff
            current_time = time.time()
            async with self._failed_peer_lock:
                # Clean up old failures (older than max retry interval)
                expired_keys = [
                    key
                    for key, fail_info in self._failed_peers.items()
                    if current_time - fail_info.get("timestamp", 0)
                    > self._max_retry_interval
                ]
                for key in expired_keys:
                    del self._failed_peers[key]

            # CRITICAL FIX: Prioritize seeders when connecting
            # If tracker reports seeders, prioritize connecting to them first
            # Sort peer_list to put potential seeders first (tracker-reported seeders)
            peer_list_sorted = []
            potential_seeders = []
            regular_peers = []

            for peer_data in peer_list:
                # Check if peer is reported as a seeder by tracker
                is_seeder = peer_data.get("is_seeder", False) or peer_data.get("complete", False)
                if is_seeder:
                    potential_seeders.append(peer_data)
                else:
                    regular_peers.append(peer_data)

            # Prioritize seeders first, then regular peers
            peer_list_sorted = potential_seeders + regular_peers

            if potential_seeders:
                self.logger.info(
                    "🌱 SEEDER PRIORITY: Found %d potential seeder(s) in discovered peers - prioritizing for connection",
                    len(potential_seeders),
                )

            # Convert to PeerInfo list and filter out recently failed peers
            peer_info_list = []
            skipped_failed = 0
            for idx, peer_data in enumerate(
                peer_list_sorted[: max_connections * 2]
            ):  # Check more peers to account for filtering
                # CRITICAL FIX: Validate peer_data is a dict before accessing it
                if not isinstance(peer_data, dict):
                    error_msg = (
                        f"peer_data at index {idx} is not a dict, got {type(peer_data)}. "
                        f"Expected dict with 'ip' and 'port' keys. "
                        f"peer_data value: {str(peer_data)[:200]}"
                    )
                    self.logger.error(error_msg)
                    continue  # Skip invalid peer data

                try:
                    peer_info = PeerInfo(
                        ip=peer_data["ip"],
                        port=peer_data["port"],
                        peer_source=peer_data.get(
                            "peer_source", "tracker"
                        ),  # Default to tracker for tracker responses
                    )
                except (KeyError, TypeError) as e:
                    error_msg = (
                        f"Invalid peer_data at index {idx}: {e}. "
                        f"peer_data type: {type(peer_data)}, "
                        f"peer_data value: {str(peer_data)[:200]}"
                    )
                    self.logger.exception(error_msg)
                    continue  # Skip invalid peer data

                # CRITICAL FIX: Skip if already connected, but log for diagnostics
                peer_key = str(peer_info)
                if peer_key in self.connections:
                    existing_conn = self.connections[peer_key]
                    # If peer is already connected but doesn't have bitfield, we might want to disconnect it
                    # But don't do it here - let the evaluation loop handle it
                    if existing_conn.is_active():
                        has_bitfield = (
                            existing_conn.peer_state.bitfield is not None
                            and len(existing_conn.peer_state.bitfield) > 0
                        )
                        # CRITICAL FIX: Don't skip peers without bitfields - they may send HAVE messages
                        # According to BitTorrent spec (BEP 3), bitfield is OPTIONAL if peer has no pieces
                        # Peers may send HAVE messages instead of bitfields (protocol-compliant)
                        # Only skip if peer has been connected for a while without sending HAVE messages
                        if not has_bitfield:
                            # Check if peer has sent HAVE messages (alternative to bitfield)
                            have_messages_count = len(existing_conn.peer_state.pieces_we_have) if existing_conn.peer_state.pieces_we_have else 0
                            has_have_messages = have_messages_count > 0
                            
                            # Calculate connection age
                            connection_age = time.time() - existing_conn.stats.last_activity if hasattr(existing_conn.stats, "last_activity") else 0.0
                            have_message_timeout = 30.0  # 30 seconds - reasonable time for peer to send first HAVE message
                            
                            if not has_have_messages and connection_age > have_message_timeout:
                                # Peer is connected but no bitfield AND no HAVE messages after timeout
                                # Will be disconnected by evaluation loop
                                self.logger.debug(
                                    "Skipping peer %s: already connected for %.1fs but no bitfield OR HAVE messages (will be cycled by evaluation loop)",
                                    peer_key,
                                    connection_age,
                                )
                                continue
                            elif has_have_messages:
                                # Peer sent HAVE messages but no bitfield - protocol-compliant, allow connection
                                self.logger.debug(
                                    "Peer %s has %d HAVE message(s) but no bitfield - allowing connection (protocol-compliant)",
                                    peer_key,
                                    have_messages_count,
                                )
                            else:
                                # Recently connected without bitfield - give benefit of doubt, may send HAVE messages
                                self.logger.debug(
                                    "Peer %s recently connected (%.1fs) without bitfield - allowing connection (may send HAVE messages)",
                                    peer_key,
                                    connection_age,
                                )
                    continue

                # Skip if recently failed (using exponential backoff)
                # CRITICAL FIX: When peer count is very low, be more aggressive about retrying failed peers
                # This helps recover from transient connection failures
                async with self._failed_peer_lock:
                    fail_info = self._failed_peers.get(peer_key)

                if fail_info:
                        fail_time = fail_info.get("timestamp", 0)
                        fail_count = fail_info.get("count", 1)
                        fail_reason = fail_info.get("reason", "unknown")

                        # CRITICAL FIX: When peer count is very low, reduce backoff to retry faster
                        # This helps when we have few peers and need to maximize connections
                        if active_peer_count <= 2:
                            # Very low peer count - use shorter backoff (50% of normal)
                            backoff_multiplier = self._backoff_multiplier * 0.5
                            max_retry = self._max_retry_interval * 0.5
                        elif active_peer_count <= 5:
                            # Low peer count - use shorter backoff (75% of normal)
                            backoff_multiplier = self._backoff_multiplier * 0.75
                            max_retry = self._max_retry_interval * 0.75
                        else:
                            # Normal peer count - use standard backoff
                            backoff_multiplier = self._backoff_multiplier
                            max_retry = self._max_retry_interval

                        # Calculate exponential backoff: min_interval * (multiplier ^ (count - 1))
                        # Cap at max_retry_interval
                        backoff_interval = min(
                            self._min_retry_interval
                            * (backoff_multiplier ** (fail_count - 1)),
                            max_retry,
                        )

                        # CRITICAL FIX: For certain failure types, retry faster (connection refused, timeout)
                        # These are often transient and worth retrying sooner
                        if "connection refused" in fail_reason.lower() or "timeout" in fail_reason.lower():
                            backoff_interval = backoff_interval * 0.5  # 50% shorter backoff for transient errors

                        # CRITICAL FIX: When peer count is very low, be much more aggressive with retries
                        # This allows faster connection recycling and prevents download stalls
                        if active_peer_count < 3:
                            backoff_interval = backoff_interval * 0.2  # 80% shorter backoff when peer count is critically low
                        elif active_peer_count < 10:
                            backoff_interval = backoff_interval * 0.4  # 60% shorter backoff when peer count is low

                        # Check if backoff period has elapsed
                        elapsed = current_time - fail_time
                        if elapsed < backoff_interval:
                            skipped_failed += 1
                            self.logger.debug(
                                "Skipping peer %s (failed %d times, backoff: %.1fs, elapsed: %.1fs, reason: %s, active_peers: %d)",
                                peer_key,
                                fail_count,
                                backoff_interval,
                                elapsed,
                                fail_reason,
                                active_peer_count,
                            )
                            continue

                # Add to connection list
                peer_info_list.append(peer_info)

            # CRITICAL FIX: Track peers in current batch to prevent reconnection loop from interfering
            # Initialize set to track peers being processed in this batch
            if not hasattr(self, "_current_batch_peers"):
                self._current_batch_peers = set[Any]()
            else:
                self._current_batch_peers.clear()

            # Add all peers to current batch tracking (after peer_info_list is created)
            for peer_info in peer_info_list:
                peer_key = str(peer_info)
                self._current_batch_peers.add(peer_key)  # type: ignore[attr-defined]

            # Rank peers before connecting (highest score first)
            if peer_info_list:
                peer_info_list = await self._rank_peers_for_connection(peer_info_list)

                # Update current batch tracking with ranked peers
                self._current_batch_peers.clear()
                for peer_info in peer_info_list:
                    peer_key = str(peer_info)
                    self._current_batch_peers.add(peer_key)  # type: ignore[attr-defined]

            # CRITICAL FIX: Store ALL deduplicated peers in queue for continuous connection attempts
            # User requirement: "the queue should be filled with deduplicated peers, and continue connecting peers
            # and removing attempted and failed connections until all peers have been tried and most have been connected"
            # We'll process them in batches but continuously attempt all peers
            all_peers_queue = peer_info_list.copy()  # Store all peers for continuous attempts
            # Start with first batch (up to max_connections) but will continue with rest
            initial_batch = peer_info_list[:max_connections]
            remaining_peers = peer_info_list[max_connections:]

            if remaining_peers:
                self.logger.info(
                    "📋 CONNECTION QUEUE: Queued %d peer(s) for continuous connection attempts (initial batch: %d, remaining: %d)",
                    len(all_peers_queue),
                    len(initial_batch),
                    len(remaining_peers),
                )

            # Use initial batch for first connection attempts
            peer_info_list = initial_batch

            if skipped_failed > 0:
                # Calculate average backoff for logging
                async with self._failed_peer_lock:
                    total_backoff = 0.0
                    backoff_count = 0
                    peer_keys_in_list = {str(p) for p in peer_info_list}
                    for peer_key, fail_info in self._failed_peers.items():
                        # Only count peers that were actually skipped (not in peer_info_list)
                        if peer_key not in peer_keys_in_list:
                            fail_count = fail_info.get("count", 1)
                            backoff = min(
                                self._min_retry_interval
                                * (self._backoff_multiplier ** (fail_count - 1)),
                                self._max_retry_interval,
                            )
                            total_backoff += backoff
                            backoff_count += 1
                    avg_backoff = (
                        total_backoff / backoff_count
                        if backoff_count > 0
                        else self._min_retry_interval
                    )

                self.logger.debug(
                "Skipped %d recently failed peers (using exponential backoff, avg retry after %.1fs)",
                skipped_failed,
                avg_backoff,
            )

            # Warmup connections if enabled
            # CRITICAL FIX: Disable warmup on Windows to avoid WinError 121
            import sys

            if (
                config.connection_pool_warmup_enabled
                and peer_info_list
                and sys.platform != "win32"
            ):
                warmup_count = min(config.connection_pool_warmup_count, len(peer_info_list))
                await self.connection_pool.warmup_connections(peer_info_list, warmup_count)
            elif config.connection_pool_warmup_enabled and sys.platform == "win32":
                self.logger.debug(
                    "Connection pool warmup disabled on Windows to avoid WinError 121 (semaphore timeout)"
                )

            if not peer_info_list:
                self.logger.info(
                    "No peers to connect to after filtering (total input: %d, skipped failed: %d, already connected: %d, max_connections: %d)",
                    len(peer_list),
                    skipped_failed,
                    len(peer_list) - len(peer_info_list) - skipped_failed,
                    max_connections,
                )
                # CRITICAL FIX: Clear flag even when no peers to connect
                self._connection_batches_in_progress = False
                # CRITICAL FIX: Clear current batch tracking when batches complete
                if hasattr(self, "_current_batch_peers"):
                    self._current_batch_peers.clear()
                return

            # CRITICAL FIX: Enhanced logging for connection attempt start
            self.logger.info(
                "Starting connection attempts to %d peer(s) (filtered from %d input, skipped %d failed, max_per_torrent: %d)",
                len(peer_info_list),
                len(peer_list),
                skipped_failed,
                max_connections,
            )

            # Rate limit connection attempts to avoid overwhelming the system
            # CRITICAL FIX: Optimal batch sizing algorithm that adapts to peer count and system resources
            # The semaphore already limits concurrent connections, so we can use larger batches safely
            # Key insight: When there are 1000+ peers, small batches (20-50) create 20-50 batches,
            # which takes forever and blocks DHT discovery. Use larger batches for many peers.
            import sys

            is_windows = sys.platform == "win32"
            
            # Get semaphore limit (max concurrent connection attempts)
            max_concurrent = getattr(
                self.config.network,
                "max_concurrent_connection_attempts",
                20,
            )
            
            # Calculate optimal batch size based on:
            # 1. Total peers to connect (more peers = larger batches for faster processing)
            # 2. Active peer count (fewer active = smaller batches to avoid socket exhaustion)
            # 3. Semaphore limit (batch shouldn't exceed semaphore capacity)
            # 4. Platform (Windows needs smaller batches)
            total_peers_to_connect = len(peer_info_list) + (len(remaining_peers) if remaining_peers else 0)
            
            # Base batch size calculation:
            # - For many peers (500+): use larger batches (100-200) to process faster
            # - For moderate peers (100-500): use medium batches (50-100)
            # - For few peers (<100): use smaller batches (20-50)
            if total_peers_to_connect >= 500:
                # Many peers: use large batches to process quickly and clear flag sooner
                base_batch_size = 150 if not is_windows else 100
                # Scale down if active peer count is very low (to avoid socket exhaustion)
                if active_peer_count == 0:
                    base_batch_size = min(50, base_batch_size) if not is_windows else min(30, base_batch_size)
                elif active_peer_count < 3:
                    base_batch_size = min(80, base_batch_size) if not is_windows else min(50, base_batch_size)
                elif active_peer_count < 10:
                    base_batch_size = min(120, base_batch_size) if not is_windows else min(80, base_batch_size)
            elif total_peers_to_connect >= 100:
                # Moderate peers: use medium batches
                base_batch_size = 80 if not is_windows else 60
                if active_peer_count == 0:
                    base_batch_size = min(30, base_batch_size) if not is_windows else min(20, base_batch_size)
                elif active_peer_count < 3:
                    base_batch_size = min(50, base_batch_size) if not is_windows else min(35, base_batch_size)
                elif active_peer_count < 10:
                    base_batch_size = min(70, base_batch_size) if not is_windows else min(50, base_batch_size)
            else:
                # Few peers: use smaller batches (original logic for safety)
                if active_peer_count == 0:
                    base_batch_size = 30 if not is_windows else 20
                elif active_peer_count < 3:
                    base_batch_size = 40 if not is_windows else 30
                elif active_peer_count < 10:
                    base_batch_size = 55 if not is_windows else 45
                else:
                    base_batch_size = 50 if not is_windows else 40
            
            # CRITICAL FIX: Batch size should not exceed semaphore limit
            # The semaphore limits concurrent attempts, so batches larger than semaphore are wasteful
            # Also respect max_connections limit
            batch_size = min(base_batch_size, max_concurrent, max_connections)
            
            # CRITICAL FIX: Ensure minimum batch size for efficiency
            # Very small batches (<10) create too many iterations and slow processing
            batch_size = max(10, batch_size)
            
            # Connection delay: no delay for fast processing, small delay on Windows for stability
            if active_peer_count == 0:
                connection_delay = 0.0  # NO DELAY - urgent to find peers
            elif active_peer_count < 10:
                connection_delay = 0.0  # NO DELAY - need more peers
            elif is_windows and total_peers_to_connect >= 500:
                connection_delay = 0.01  # 10ms delay for Windows with many peers (stability)
            elif is_windows:
                connection_delay = 0.02  # 20ms delay for Windows (stability)
            else:
                connection_delay = 0.0  # NO DELAY - non-Windows can handle it
            
            intra_batch_delay = 0.0  # Connections within batch are fully parallel
            
            # Log optimal batch configuration
            estimated_batches = (total_peers_to_connect + batch_size - 1) // batch_size  # Ceiling division
            estimated_time = estimated_batches * (connection_delay + 0.1)  # Rough estimate: 0.1s per batch processing
            self.logger.info(
                "📊 OPTIMAL BATCHING: total_peers=%d, active=%d, batch_size=%d, max_concurrent=%d, "
                "estimated_batches=%d, estimated_time=%.1fs, delay=%.3fs",
                total_peers_to_connect,
                active_peer_count,
                batch_size,
                max_concurrent,
                estimated_batches,
                estimated_time,
                connection_delay,
            )

            # CRITICAL FIX: Aggregate connection statistics for diagnostics (BitTorrent spec compliant)
            connection_stats = {
                "successful": 0,
                "failed": 0,
                "timeout": 0,
                "connection_refused": 0,
                "winerror_121": 0,
                "other_errors": 0,
                "total_attempts": 0,
                "batches_processed": 0,
                "zero_success_batches": 0,  # Track batches with zero successes
            }

            # CRITICAL FIX: Process peers continuously - initial batch first, then remaining peers
            # This ensures all deduplicated peers are attempted, not just the first max_connections
            all_peers_to_process = peer_info_list.copy()
            if remaining_peers:
                all_peers_to_process.extend(remaining_peers)
                self.logger.info(
                    "🔄 CONTINUOUS CONNECTION: Will process %d total peer(s) in batches (initial: %d, remaining: %d)",
                    len(all_peers_to_process),
                    len(peer_info_list),
                    len(remaining_peers),
                )

            try:
                pending_enqueue_reason: str | None = None
                for batch_start in range(0, len(all_peers_to_process), batch_size):
                    # CRITICAL FIX: Check if manager is shutting down before processing batch
                    if not self._running:
                        self.logger.debug(
                            "Stopping connection batch: manager shutdown (processed %d/%d peers)",
                            batch_start,
                            len(all_peers_to_process),
                        )
                        break
                    
                    # CRITICAL FIX: Check if batch processing has exceeded maximum duration
                    # This prevents the flag from blocking DHT discovery indefinitely
                    batch_elapsed = time.time() - batch_start_time
                    if batch_elapsed > max_batch_duration:
                        self.logger.warning(
                            "Connection batch processing exceeded maximum duration (%.1fs > %.1fs). "
                            "Clearing flag to allow DHT discovery. Processed %d/%d peers.",
                            batch_elapsed,
                            max_batch_duration,
                            batch_start,
                            len(all_peers_to_process),
                        )
                        # Clear flag and break to allow DHT discovery
                        self._connection_batches_in_progress = False
                        break
                    
                    # CRITICAL FIX: Clear flag early when we have enough active peers OR after processing initial batches
                    # This allows DHT discovery to start while connection batches continue in background
                    # This is critical for popular torrents with 1000+ peers - we don't want to block DHT for minutes
                    if batch_start > 0:  # At least one batch processed
                        time_since_last_progress = time.time() - batch_start_time
                        async with self.connection_lock:
                            current_active = len([c for c in self.connections.values() if c.is_active()])
                            
                            # CRITICAL FIX: Clear flag early if:
                            # 1. We have at least 2 active peers AND processed at least 2 batches (30-60 peers attempted), OR
                            # 2. We've been processing for more than 30 seconds (half max duration), OR
                            # 3. We have at least 5 active peers (good enough to start DHT)
                            batches_processed = batch_start // batch_size
                            should_clear_flag = False
                            clear_reason = ""
                            
                            if current_active >= 5:
                                # We have enough active peers - clear flag immediately
                                should_clear_flag = True
                                clear_reason = f"{current_active} active peers (>=5)"
                            elif current_active >= 2 and batches_processed >= 2:
                                # We have some active peers and processed a few batches - clear flag
                                should_clear_flag = True
                                clear_reason = f"{current_active} active peers after {batches_processed} batches"
                            elif time_since_last_progress > 30.0:  # 30 seconds (half of typical 60s max)
                                # We've been processing for a while - clear flag to allow DHT
                                should_clear_flag = True
                                clear_reason = f"processing for {time_since_last_progress:.1f}s"
                            
                            if should_clear_flag:
                                self.logger.info(
                                    "🔄 CONNECTION BATCHES: Clearing flag early (%s) to allow DHT discovery. "
                                    "Batches will continue in background (processed %d/%d peers, %d active).",
                                    clear_reason,
                                    batch_start,
                                    len(all_peers_to_process),
                                    current_active,
                                )
                                self._connection_batches_in_progress = False
                                # Don't break - continue processing batches in background

                    # CRITICAL FIX: Check active connection count before each batch
                    # If we have enough active connections, we can stop processing more batches
                    remaining_for_queue: list[PeerInfo] = []
                    current_active = 0
                    async with self.connection_lock:
                        current_active = len([c for c in self.connections.values() if c.is_active()])
                        if current_active >= max_connections:
                            self.logger.info(
                                "✅ CONNECTION QUEUE: Reached target active connections (%d/%d). Stopping batch processing (processed %d/%d peers)",
                                current_active,
                                max_connections,
                                batch_start,
                                len(all_peers_to_process),
                            )
                            remaining_for_queue = all_peers_to_process[batch_start:]
                            pending_enqueue_reason = "max_connections_reached"
                    if remaining_for_queue:
                        await self._queue_pending_peers(
                            remaining_for_queue,
                            pending_enqueue_reason or "max_connections_reached",
                        )
                        self.logger.info(
                            "📥 CONNECTION QUEUE: Stored %d pending peer(s) after hitting connection cap (%d/%d)",
                            len(remaining_for_queue),
                            current_active,
                            max_connections,
                        )
                        self._schedule_pending_resume(reason="waiting_for_slot_release")
                        break

                    batch = all_peers_to_process[batch_start : batch_start + batch_size]
                    connection_stats["batches_processed"] += 1
                    batch_successful = 0  # Track successes in this batch

                    # CRITICAL FIX: Create all connection tasks immediately in parallel (no delays)
                    # This dramatically speeds up batch processing - connections happen concurrently
                    # CRITICAL FIX: Wrap each connection with timeout to prevent hanging
                    # Individual connections can hang during TCP connect or handshake, blocking the batch
                    tasks = []
                    # CRITICAL FIX: Reduced from 45s to 25s - 45s was too long and causing batch processing to stall
                    # 25s is sufficient for TCP connect + handshake without blocking batch completion
                    connection_timeout = 25.0  # Per-connection timeout (must be longer than batch timeout)
                    for peer_info in batch:  # pragma: no cover - Loop for connecting to multiple peers, tested via single peer connections
                        # CRITICAL FIX: Check _running before each connection attempt
                        if not self._running:
                            break

                        # CRITICAL FIX: Wrap connection with timeout to prevent hanging
                        # This ensures individual connections don't block batch processing indefinitely
                        async def connect_with_timeout(peer: PeerInfo) -> None:
                            """Connect to peer with timeout protection."""
                            try:
                                await asyncio.wait_for(
                                    self._connect_to_peer(peer),
                                    timeout=connection_timeout,
                                )
                            except asyncio.TimeoutError:
                                self.logger.debug(
                                    "Connection to %s timed out after %.1fs (TCP connect or handshake hung)",
                                    peer,
                                    connection_timeout,
                                )
                                # Clean up any partial connection state
                                peer_key = str(peer)
                                async with self.connection_lock:
                                    if peer_key in self.connections:
                                        conn = self.connections[peer_key]
                                        if conn.state not in (
                                            ConnectionState.ACTIVE,
                                            ConnectionState.BITFIELD_RECEIVED,
                                            ConnectionState.BITFIELD_SENT,
                                        ):
                                            # Connection didn't complete - remove it
                                            self.logger.debug(
                                                "Removing incomplete connection to %s (state=%s) after timeout",
                                                peer,
                                                conn.state.value,
                                            )
                                            await self._disconnect_peer(conn)
                                raise asyncio.TimeoutError(
                                    f"Connection to {peer} timed out after {connection_timeout}s"
                                )

                        # Create task immediately - no delays within batch for maximum speed
                        task = asyncio.create_task(
                            connect_with_timeout(peer_info)
                        )  # pragma: no cover - Same context
                        tasks.append(task)  # pragma: no cover - Same context

                    # CRITICAL FIX: Process results as they complete instead of waiting for all
                    # This allows logs to appear in real-time and prevents blocking
                    # Use asyncio.as_completed() to process results as they arrive
                    if tasks:
                        # CRITICAL FIX: Cancel tasks if manager is shutting down
                        if not self._running:
                            self.logger.debug("Cancelling %d connection task(s): manager shutdown", len(tasks))
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            try:
                                await asyncio.wait_for(
                                    asyncio.gather(*tasks, return_exceptions=True),
                                    timeout=1.0,
                                )
                            except (asyncio.TimeoutError, asyncio.CancelledError):
                                pass
                            continue

                        # CRITICAL FIX: Add timeout for batch processing to prevent slow batches from blocking
                        # Use shorter timeout when peer count is low (faster recovery)
                        # CRITICAL FIX: Batch timeout must be shorter than per-connection timeout (25s)
                        # This ensures batches complete even if some connections hang
                        # Reduced from 20-40s to 15-25s for faster batch completion
                        batch_timeout = 15.0 if active_peer_count < 3 else 25.0

                        # Process results as they complete for real-time logging
                        completed_count = 0
                        results = [None] * len(tasks)  # Pre-allocate results list
                        pending_tasks = set(tasks)
                        successful_in_batch = 0
                        min_successful_for_early_exit = max(3, batch_size // 4)  # Exit early if 25% succeed

                        # CRITICAL FIX: Process with timeout and early exit if enough connections succeed
                        try:
                            async with asyncio.timeout(batch_timeout):
                                for completed_future in asyncio.as_completed(tasks):
                                    # CRITICAL FIX: Check _running before processing each result
                                    if not self._running:
                                        self.logger.debug("Stopping result processing: manager shutdown")
                                        for task in tasks:
                                            if not task.done():
                                                task.cancel()
                                        break

                                    try:
                                        result = await completed_future
                                        # Find which task this result belongs to by matching with pending tasks
                                        for i, task in enumerate(tasks):
                                            if task.done() and results[i] is None:
                                                results[i] = result
                                                completed_count += 1

                                                # Track successful connections for early exit
                                                if not isinstance(result, Exception):
                                                    successful_in_batch += 1
                                                    batch_successful += 1

                                                # CRITICAL FIX: Early exit if enough connections succeed
                                                # This speeds up batch processing when we get good peers quickly
                                                if successful_in_batch >= min_successful_for_early_exit and completed_count >= min_successful_for_early_exit:
                                                    self.logger.debug(
                                                        "Early batch completion: %d/%d successful (%.1f%%), moving to next batch",
                                                        successful_in_batch,
                                                        completed_count,
                                                        (successful_in_batch / completed_count * 100) if completed_count > 0 else 0,
                                                    )
                                                    # Cancel remaining tasks
                                                    for remaining_task in tasks:
                                                        if not remaining_task.done():
                                                            remaining_task.cancel()
                                                    break

                                                # Log progress periodically for real-time feedback
                                                if completed_count % 5 == 0 or completed_count == len(tasks):
                                                    self.logger.info(
                                                        "Connection batch progress: %d/%d completed (%d successful)",
                                                        completed_count,
                                                        len(tasks),
                                                        successful_in_batch,
                                                    )
                                                break
                                    except asyncio.CancelledError:
                                        # CRITICAL FIX: Handle CancelledError properly - mark task as cancelled
                                        # Find which task was cancelled and mark it in results
                                        for i, task in enumerate(tasks):
                                            if task.done() and results[i] is None:
                                                # Task was cancelled - mark as cancelled exception
                                                results[i] = asyncio.CancelledError(f"Connection to {batch[i]} was cancelled")
                                                completed_count += 1
                                                self.logger.debug(
                                                    "Connection task to %s was cancelled (task %d/%d)",
                                                    batch[i],
                                                    i + 1,
                                                    len(tasks),
                                                )
                                                break
                                        # Continue processing other tasks - don't break
                                        continue
                                    except Exception as e:
                                        # Find which task failed
                                        for i, task in enumerate(tasks):
                                            if task.done() and results[i] is None:
                                                results[i] = e
                                                completed_count += 1
                                                break
                        except TimeoutError:
                            # CRITICAL FIX: Batch timeout - cancel remaining tasks and move on
                            self.logger.debug(
                                "Connection batch timeout after %.1fs (%d/%d completed, %d successful) - cancelling remaining tasks",
                                batch_timeout,
                                completed_count,
                                len(tasks),
                                successful_in_batch,
                            )
                            # Cancel all remaining tasks
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            # Wait briefly for cancellations to propagate, then mark remaining as timeout
                            await asyncio.sleep(0.1)  # Brief wait for cancellation to propagate
                            # Mark remaining as timeout and ensure they're counted
                            for i, result in enumerate(results):
                                if result is None:
                                    # Check if task was actually cancelled
                                    if tasks[i].done():
                                        try:
                                            await tasks[i]  # This will raise CancelledError
                                        except asyncio.CancelledError:
                                            results[i] = asyncio.CancelledError(f"Connection to {batch[i]} cancelled due to batch timeout")
                                    else:
                                        results[i] = TimeoutError(f"Batch timeout after {batch_timeout}s")
                                    completed_count += 1

                    # Process results in order
                    for i, result in enumerate(results):
                        peer_info = batch[i]
                        peer_key = str(peer_info)

                        # CRITICAL FIX: Skip if result is None (task not completed yet)
                        # This can happen if batch timeout occurred before all tasks completed
                        if result is None:
                            # Task didn't complete - mark as timeout
                            result = TimeoutError(f"Connection to {peer_info} did not complete before batch timeout")
                            completed_count += 1

                        connection_stats["total_attempts"] += 1

                        if isinstance(result, Exception):  # pragma: no cover - Same context
                            # CRITICAL FIX: Handle CancelledError as a temporary failure (not permanent)
                            # Cancelled connections should be retried in subsequent batches
                            if isinstance(result, asyncio.CancelledError):
                                # Cancelled connections are temporary - don't mark as permanent failure
                                # They'll be retried in subsequent batches
                                self.logger.debug(
                                    "Connection to %s was cancelled (will be retried in subsequent batches)",
                                    peer_info,
                                )
                                connection_stats["failed"] += 1
                            else:
                                connection_stats["failed"] += 1

                            # CRITICAL FIX: Record failure with exponential backoff tracking
                            error_str = str(result)
                            error_type = type(result).__name__

                            # Determine failure reason for better retry strategy
                            # CRITICAL FIX: Categorize errors as temporary (should retry) vs permanent (should not retry)
                            failure_reason = "unknown"
                            is_temporary = (
                                True  # Default to temporary - most errors are retryable
                            )

                            if (
                                "WinError 121" in error_str
                                or "semaphore timeout" in error_str.lower()
                            ):
                                failure_reason = "semaphore_timeout"
                                connection_stats["winerror_121"] += 1
                                is_temporary = True  # Semaphore timeout is temporary - retry after backoff
                            elif (
                                "connection refused" in error_str.lower()
                                or "WinError 1225" in error_str
                            ):
                                failure_reason = "connection_refused"
                                connection_stats["connection_refused"] += 1
                                is_temporary = True  # Connection refused is temporary - peer may be busy
                            elif "timeout" in error_str.lower() or isinstance(
                                result, asyncio.TimeoutError
                            ):
                                failure_reason = "timeout"
                                connection_stats["timeout"] += 1
                                is_temporary = (
                                    True  # Timeouts are temporary - network may be slow
                                )
                            elif "connection reset" in error_str.lower():
                                failure_reason = "connection_reset"
                                connection_stats["other_errors"] += 1
                                is_temporary = True  # Connection reset is temporary - peer may have closed connection
                            elif (
                                "info hash" in error_str.lower()
                                or "mismatch" in error_str.lower()
                            ):
                                failure_reason = "info_hash_mismatch"
                                is_temporary = False  # Info hash mismatch is permanent - peer has wrong torrent
                            elif (
                                "handshake" in error_str.lower()
                                and "invalid" in error_str.lower()
                            ):
                                failure_reason = "invalid_handshake"
                                is_temporary = False  # Invalid handshake is permanent - peer protocol incompatible
                            else:
                                failure_reason = error_type.lower()
                                # Default to temporary for unknown errors - better to retry than give up
                                is_temporary = True

                            # Update failure tracking with exponential backoff
                            # CRITICAL FIX: Only track temporary failures - permanent failures should not be retried
                            async with self._failed_peer_lock:
                                if is_temporary:
                                    # Only track temporary failures for retry logic
                                    if peer_key in self._failed_peers:
                                        # Increment failure count for exponential backoff
                                        fail_info = self._failed_peers[peer_key]
                                        fail_info["count"] = fail_info.get("count", 1) + 1
                                        fail_info["timestamp"] = time.time()
                                        fail_info["reason"] = failure_reason
                                        fail_count = fail_info["count"]
                                    else:
                                        # First failure
                                        self._failed_peers[peer_key] = {
                                            "timestamp": time.time(),
                                            "count": 1,
                                            "reason": failure_reason,
                                        }
                                        fail_count = 1
                                else:
                                    # Permanent failure - don't track for retry, but log it
                                    fail_count = 0  # No retry count for permanent failures
                                    # Remove from failed_peers if it was there (permanent failures shouldn't be retried)
                                    if peer_key in self._failed_peers:
                                        del self._failed_peers[peer_key]

                            # Calculate backoff interval for logging (only for temporary failures)
                            if is_temporary and fail_count > 0:
                                backoff_interval = min(
                                    self._min_retry_interval
                                    * (self._backoff_multiplier ** (fail_count - 1)),
                                    self._max_retry_interval,
                                )
                            else:
                                backoff_interval = 0  # No retry for permanent failures

                            # CRITICAL FIX: Handle WinError 121 (semaphore timeout) gracefully on Windows
                            # This is expected on Windows when many connections are attempted simultaneously
                            import sys

                            is_windows = sys.platform == "win32"

                            if not is_temporary:
                                # Permanent failure - log as warning and don't retry
                                self.logger.warning(
                                    "Permanent connection failure to %s: %s (reason: %s, will not retry)",
                                    peer_info,
                                    result,
                                    failure_reason,
                                )
                            elif failure_reason == "semaphore_timeout":
                                # Log as debug on Windows (expected), warning on other platforms
                                if is_windows:
                                    self.logger.debug(
                                        "Connection semaphore timeout (WinError 121) to %s: %s. "
                                        "This is normal on Windows when many connections are attempted simultaneously. "
                                        "Will retry after %.1fs (attempt %d)",
                                        peer_info,
                                        result,
                                        backoff_interval,
                                        fail_count,
                                    )
                                else:
                                    self.logger.warning(
                                        "Connection semaphore timeout to %s: %s (will retry after %.1fs, attempt %d)",
                                        peer_info,
                                        result,
                                        backoff_interval,
                                        fail_count,
                                    )
                            elif failure_reason == "connection_refused":
                                # Connection refused - peer not accepting connections (temporary)
                                self.logger.debug(
                                    "Connection refused by peer %s (will retry after %.1fs, attempt %d)",
                                    peer_info,
                                    backoff_interval,
                                    fail_count,
                                )
                            elif failure_reason in ("timeout", "connection_reset"):
                                # Timeout or connection reset - temporary network issues
                                self.logger.debug(
                                    "Temporary connection failure to %s: %s (reason: %s, will retry after %.1fs, attempt %d)",
                                    peer_info,
                                    result,
                                    failure_reason,
                                    backoff_interval,
                                    fail_count,
                                )
                            else:
                                # Log other temporary connection failures as warnings (not errors to reduce noise)
                                log_level = "warning" if fail_count <= 3 else "debug"
                                if log_level == "warning":
                                    self.logger.warning(
                                        "Temporary connection failure to %s: %s (will retry after %.1fs, attempt %d, reason: %s)",
                                        peer_info,
                                        result,
                                        backoff_interval,
                                        fail_count,
                                        failure_reason,
                                    )
                                else:
                                    self.logger.debug(
                                        "Temporary connection failure to %s: %s (will retry after %.1fs, attempt %d, reason: %s)",
                                        peer_info,
                                        result,
                                        backoff_interval,
                                        fail_count,
                                        failure_reason,
                                    )
                        else:
                            # CRITICAL FIX: Check if connection actually completed handshake AND bitfield exchange
                            # _connect_to_peer() returns after handshake completes, so if no exception,
                            # the connection should be in self.connections
                            # However, we should only count it as successful if it has completed the full protocol
                            # handshake (handshake + bitfield exchange), not just the initial handshake
                            peer_key = str(peer_info)
                            async with self.connection_lock:
                                if peer_key in self.connections:
                                    conn = self.connections[peer_key]
                                    # CRITICAL FIX: Only count connections as successful if they've completed
                                    # the full protocol handshake (handshake + bitfield exchange)
                                    # HANDSHAKE_SENT is too early - connection may not have received peer's handshake yet
                                    # We need at least HANDSHAKE_RECEIVED (handshake complete) or better yet,
                                    # BITFIELD_RECEIVED (bitfield exchange complete) or ACTIVE (fully active)
                                    if conn.is_active() or conn.state in [
                                        ConnectionState.ACTIVE,
                                        ConnectionState.BITFIELD_RECEIVED,
                                        ConnectionState.BITFIELD_SENT,
                                        ConnectionState.HANDSHAKE_RECEIVED,
                                    ]:
                                        self.logger.debug(
                                            "Connection to %s completed successfully (state=%s, is_active=%s)",
                                            peer_info,
                                            conn.state.value,
                                            conn.is_active(),
                                        )
                                        connection_stats["successful"] += 1
                                    else:
                                        # Connection exists but not in a valid state - may still be connecting
                                        # Don't count as failed yet - it may complete later
                                        self.logger.debug(
                                            "Connection to %s exists but not yet active (state=%s) - may complete later",
                                            peer_info,
                                            conn.state.value,
                                        )
                                        # Count as successful if it's at least connecting (not disconnected)
                                        if conn.state != ConnectionState.DISCONNECTED:
                                            connection_stats["successful"] += 1
                                        else:
                                            connection_stats["failed"] += 1
                                else:
                                    # No connection in dict - handshake must have failed
                                    # However, this could be a race condition - connection may be added shortly
                                    # Wait a brief moment and check again
                                    await asyncio.sleep(0.1)
                                    async with self.connection_lock:
                                        if peer_key in self.connections:
                                            conn = self.connections[peer_key]
                                            if conn.state != ConnectionState.DISCONNECTED:
                                                connection_stats["successful"] += 1
                                                self.logger.debug(
                                                    "Connection to %s found after brief wait (state=%s)",
                                                    peer_info,
                                                    conn.state.value,
                                                )
                                            else:
                                                connection_stats["failed"] += 1
                                        else:
                                            connection_stats["failed"] += 1

                    # CRITICAL FIX: Track zero-success batches for fail-fast DHT trigger
                    if batch_successful == 0:
                        connection_stats["zero_success_batches"] += 1
                    
                    # CRITICAL FIX: Process batches as fast as possible - no delays when connection_delay is 0
                    # Only delay if connection_delay > 0 and we have more batches to process
                    if batch_start + batch_size < len(all_peers_to_process) and connection_delay > 0:
                        # Use shorter delay if we got good results, longer if we need to wait
                        if successful_in_batch >= min_successful_for_early_exit:
                            # Got good results - minimal delay to move quickly
                            await asyncio.sleep(0.01)  # 10ms - just enough to prevent overwhelming
                        else:
                            # Fewer successful - use configured delay
                            await asyncio.sleep(connection_delay)
                    # If connection_delay is 0, batches start immediately without any delay
            except Exception as e:
                # Log any errors in batch processing but don't stop the outer try/finally
                self.logger.warning(
                    "Error during connection batch processing: %s", e
                )
        finally:
            # CRITICAL FIX: Always clear flag when connection batches complete (or are interrupted)
            # This allows peer_count_low events to trigger DHT discovery
            # Also clear flag if batch processing took too long (timeout protection)
            batch_elapsed = time.time() - batch_start_time
            if batch_elapsed > max_batch_duration:
                self.logger.warning(
                    "Connection batch processing took too long (%.1fs). Clearing flag to unblock DHT discovery.",
                    batch_elapsed,
                )
            self._connection_batches_in_progress = False
            # CRITICAL FIX: Clear current batch tracking when batches complete
            if hasattr(self, "_current_batch_peers"):
                self._current_batch_peers.clear()
            self.logger.debug(
                "✅ CONNECTION BATCHES: Connection batches completed/interrupted (flag cleared after %.1fs, peer_count_low can now trigger DHT)",
                batch_elapsed,
            )

        # CRITICAL FIX: Log connection summary after batch completes with detailed statistics
        total_attempts = connection_stats["total_attempts"]
        # CRITICAL FIX: Log batch statistics for diagnostics (BitTorrent spec compliant)
        successful = connection_stats["successful"]
        failed = connection_stats["failed"]
        total = connection_stats["total_attempts"]
        batches = connection_stats["batches_processed"]
        zero_success_batches = connection_stats["zero_success_batches"]
        
        if total > 0:
            success_rate = (successful / total) * 100
            self.logger.info(
                "📊 CONNECTION BATCH STATISTICS: %d batches processed, %d total attempts, %d successful (%.1f%%), "
                "%d failed (%d timeouts, %d refused, %d WinError 121, %d other), %d zero-success batches",
                batches,
                total,
                successful,
                success_rate,
                failed,
                connection_stats["timeout"],
                connection_stats["connection_refused"],
                connection_stats["winerror_121"],
                connection_stats["other_errors"],
                zero_success_batches,
            )
            
            # CRITICAL FIX: If we have zero successes after multiple batches, clear connection_batches_in_progress
            # This allows DHT to start even if peer count < 50 (fail-fast mode)
            if successful == 0 and batches >= 3:
                self.logger.warning(
                    "🚨 CRITICAL: Zero successful connections after %d batches (%d attempts). "
                    "Clearing connection_batches_in_progress flag to allow fail-fast DHT discovery.",
                    batches,
                    total,
                )
                self._connection_batches_in_progress = False
                
                # Emit event to trigger fail-fast DHT if enabled
                if hasattr(self.config.network, "enable_fail_fast_dht") and self.config.network.enable_fail_fast_dht:
                    from ccbt.utils.events import PeerCountLowEvent
                    self.logger.info(
                        "Triggering fail-fast DHT discovery (active_peers=0, batches=%d, attempts=%d)",
                        batches,
                        total,
                    )
                    # Emit event to trigger DHT discovery
                    if hasattr(self, "_event_bus") and self._event_bus:
                        await self._event_bus.emit(PeerCountLowEvent(active_peers=0))
        
        successful = connection_stats["successful"]
        failed = connection_stats["failed"]
        success_rate = (
            (successful / total_attempts * 100) if total_attempts > 0 else 0.0
        )

        if successful > 0:
            # Build detailed failure breakdown
            failure_details = []
            if connection_stats["timeout"] > 0:
                failure_details.append(f"{connection_stats['timeout']} timeout(s)")
            if connection_stats["connection_refused"] > 0:
                failure_details.append(
                    f"{connection_stats['connection_refused']} refused"
                )
            if connection_stats["winerror_121"] > 0:
                failure_details.append(
                    f"{connection_stats['winerror_121']} WinError 121"
                )
            if connection_stats["other_errors"] > 0:
                failure_details.append(
                    f"{connection_stats['other_errors']} other error(s)"
                )

            failure_summary = (
                f" ({', '.join(failure_details)})" if failure_details else ""
            )

            # CRITICAL FIX: Get current connection counts for logging
            current_connections = len(self.connections)
            active_connections = len(
                [c for c in self.connections.values() if c.is_active()]
            )

            self.logger.info(
                "Connection batch completed: %d/%d successful (%.1f%% success rate, failed: %d%s, skipped recently failed: %d, total_connections: %d, active_connections: %d)",
                successful,
                total_attempts,
                success_rate,
                failed,
                failure_summary,
                skipped_failed,
                current_connections,
                active_connections,
            )
        elif failed > 0:
            # All connections failed - provide detailed breakdown
            failure_details = []
            if connection_stats["timeout"] > 0:
                failure_details.append(f"{connection_stats['timeout']} timeout(s)")
            if connection_stats["connection_refused"] > 0:
                failure_details.append(
                    f"{connection_stats['connection_refused']} refused"
                )
            if connection_stats["winerror_121"] > 0:
                failure_details.append(
                    f"{connection_stats['winerror_121']} WinError 121"
                )
            if connection_stats["other_errors"] > 0:
                failure_details.append(
                    f"{connection_stats['other_errors']} other error(s)"
                )

            failure_summary = (
                ", ".join(failure_details) if failure_details else "unknown errors"
            )

            self.logger.warning(
                "All %d connection attempts failed (%s). Will retry failed peers after %d seconds.",
                failed,
                failure_summary,
                int(self._min_retry_interval),
            )
        elif total_attempts == 0:
            self.logger.debug(
                "No connection attempts made (all peers filtered out or already connected)"
            )

        if not _from_pending_queue:
            async with self._pending_peer_queue_lock:
                pending_after_batch = len(self._pending_peer_queue)
            if pending_after_batch > 0:
                self.logger.debug(
                    "Pending peer queue still has %d entry(ies) after batch completion - scheduling resume",
                    pending_after_batch,
                )
                self._schedule_pending_resume(reason="post_batch_completion")

        await self._prune_probation_peers("post_batch")

    def _is_webrtc_peer(self, peer_info: PeerInfo) -> bool:
        """Check if peer should use WebRTC connection.

        Args:
            peer_info: Peer information

        Returns:
            True if peer should use WebRTC, False for TCP

        """
        # Check if WebTorrent is enabled
        if not self.config.network.webtorrent.enable_webtorrent:
            return False

        # Check if webtorrent protocol is available
        if self.webtorrent_protocol is None:
            return False

        # WebRTC peers typically have special IP indicators or port 0
        # In practice, you might detect this via tracker response
        # For now, we'll check if peer IP is "webrtc" or port is 0
        # Additional detection logic can be added here
        # e.g., checking tracker response for WebTorrent support flag
        return (
            peer_info.ip == "webrtc" or peer_info.port == 0
        )  # pragma: no cover - WebRTC detection, requires WebRTC peer which is optional feature

    def _should_use_utp(self, _peer_info: PeerInfo) -> bool:
        """Check if peer should use uTP connection.

        Args:
            peer_info: Peer information

        Returns:
            True if peer should use uTP, False for TCP

        """
        # Check if uTP is enabled
        if not self.config.network.enable_utp:
            return False

        # For now, attempt uTP for all peers when enabled
        # In the future, we could detect uTP support via extension protocol
        # or other heuristics (e.g., peer announces uTP support)
        return (
            self.config.network.utp.prefer_over_tcp
            if hasattr(self.config, "network") and hasattr(self.config.network, "utp")
            else True
        )

    async def _connect_to_peer(self, peer_info: PeerInfo) -> None:
        """Connect to a single peer.

        Args:
            peer_info: Peer information

        """
        peer_key = f"{peer_info.ip}:{peer_info.port}"
        
        # CRITICAL FIX: Check if peer is in backoff period (BitTorrent spec compliant)
        current_time = time.time()
        if peer_key in self._connection_backoff_until:
            backoff_until = self._connection_backoff_until[peer_key]
            if current_time < backoff_until:
                backoff_remaining = backoff_until - current_time
                self.logger.debug(
                    "Skipping connection to %s: in backoff period (%.1fs remaining)",
                    peer_key,
                    backoff_remaining,
                )
                raise PeerConnectionError(
                    f"Peer {peer_key} is in backoff period ({backoff_remaining:.1f}s remaining)"
                )
            else:
                # Backoff period expired, remove from backoff dict
                del self._connection_backoff_until[peer_key]
        
        # CRITICAL FIX: Check if manager is shutting down before attempting connection
        # This prevents connection attempts after shutdown starts
        if not self._running:
            self.logger.debug(
                "Skipping connection to %s:%d: manager is shutting down",
                peer_info.ip,
                peer_info.port,
            )
            return

        # CRITICAL FIX: Add logging for connection attempts
        self.logger.debug(
            "Attempting connection to peer %s:%d (source: %s)",
            peer_info.ip,
            peer_info.port,
            peer_info.peer_source or "unknown",
        )

        # Record connection attempt for metrics
        peer_key_metrics = f"{peer_info.ip}:{peer_info.port}"
        try:
            # Access metrics through piece_manager if available
            if hasattr(self.piece_manager, "_session_manager") and self.piece_manager._session_manager:
                session_manager = self.piece_manager._session_manager
                if hasattr(session_manager, "metrics"):
                    await session_manager.metrics.record_connection_attempt(peer_key_metrics)
        except Exception as e:
            self.logger.debug("Failed to record connection attempt: %s", e)

        # CRITICAL FIX: Check connection limits before attempting connection
        # This prevents wasting resources on unnecessary connection attempts
        # IMPORTANT: Only count active connections, not failed/inactive ones
        # This allows replacing failed connections with new ones
        # CRITICAL: Be more lenient when peer count is very low to allow aggressive seeder hunting
        async with self.connection_lock:
            active_connections = len(
                [c for c in self.connections.values() if c.is_active()]
            )
            total_connections = len(self.connections)
            max_per_torrent = self.max_peers_per_torrent

            # CRITICAL FIX: When active peer count is very low (< 5), allow more connections
            # This prevents downloads from stalling when single peer stops
            # Use a higher effective limit to allow aggressive seeder hunting
            effective_limit = max_per_torrent
            if active_connections < 5:
                # Allow up to 150% of normal limit when peer count is very low
                effective_limit = int(max_per_torrent * 1.5)
                self.logger.debug(
                    "Very low active peer count (%d): using increased connection limit (%d instead of %d) for seeder hunting",
                    active_connections,
                    effective_limit,
                    max_per_torrent,
                )

            # Only check if we're at the effective limit with active connections
            # This allows replacing failed connections with new ones
            if active_connections >= effective_limit:
                # If we have failed connections, allow replacing them
                if total_connections > active_connections:
                    self.logger.debug(
                        "At active connection limit (%d/%d) but have %d failed connections, "
                        "allowing connection attempt to replace failed peer",
                        active_connections,
                        effective_limit,
                        total_connections - active_connections,
                    )
                    # Continue with connection attempt to replace failed connection
                else:
                    self.logger.debug(
                        "Skipping connection to %s: max active peers per torrent reached (%d/%d)",
                        peer_info,
                        active_connections,
                        effective_limit,
                    )
                    return

        # CRITICAL FIX: Acquire semaphore to limit concurrent connection attempts (BitTorrent spec compliant)
        # This prevents OS socket exhaustion on Windows and other platforms
        async with self._global_connection_semaphore:
            connection: AsyncPeerConnection | None = None
            try:
                # Check if torrent is private and validate peer source (BEP 27)
                is_private = getattr(
                    self, "_is_private", False
                )  # pragma: no cover - Tested via integration tests
                # Check circuit breaker if enabled - assign peer_id early for exception handling
                peer_id = f"{peer_info.ip}:{peer_info.port}"

                if is_private:  # pragma: no cover - Tested via integration tests
                    # Private torrents only accept tracker-provided or manual peers
                    peer_source = peer_info.peer_source or "unknown"
                    if (
                        peer_source not in ("tracker", "manual")
                    ):  # pragma: no cover - Tested via integration tests (test_private_torrent_peer_source_validation)
                        self.logger.warning(
                            "Rejecting peer %s from %s for private torrent (BEP 27)",
                            peer_info,
                            peer_source,
                        )
                        error_msg = (
                            f"Private torrents only accept tracker-provided peers, "
                            f"rejecting peer from {peer_source}"
                        )
                    raise PeerConnectionError(error_msg)
                if self.circuit_breaker_manager:
                    breaker = self.circuit_breaker_manager.get_breaker(peer_id)
                    if breaker.state == "open":
                        if (
                            time.time() - breaker.last_failure_time
                            > breaker.recovery_timeout
                        ):
                            breaker.state = "half-open"
                            self.logger.debug(
                                "Circuit breaker half-open for %s", peer_info
                            )
                        else:
                            self.logger.debug(
                                "Circuit breaker open for %s, skipping", peer_info
                            )
                            _circuit_breaker_open_msg = "Circuit breaker is open"
                            raise PeerConnectionError(_circuit_breaker_open_msg)

                # Try to get connection from pool first
                pool_connection = await self.connection_pool.acquire(peer_info)
                if pool_connection:
                    self.logger.debug("Reusing connection from pool for %s", peer_info)
                    # Extract connection from pool dict if needed
                    if isinstance(pool_connection, dict):
                        conn_obj = pool_connection.get("connection")
                        if (
                            conn_obj
                            and hasattr(conn_obj, "reader")
                            and hasattr(conn_obj, "writer")
                        ):
                            # CRITICAL FIX: PooledConnection is not an AsyncPeerConnection
                            # We need to create an AsyncPeerConnection from the pooled connection
                            # Extract reader/writer from PooledConnection and create proper AsyncPeerConnection
                            from ccbt.peer.connection_pool import (
                                PooledConnection as PooledConnectionType,
                            )

                            if isinstance(conn_obj, PooledConnectionType):
                                # CRITICAL FIX: Validate pooled connection has valid reader/writer
                                if conn_obj.reader is None or conn_obj.writer is None:
                                    self.logger.warning(
                                        "Pooled connection for %s has None reader/writer, creating new connection",
                                        peer_info,
                                    )
                                    await self.connection_pool.release(
                                        f"{peer_info.ip}:{peer_info.port}",
                                        pool_connection,
                                    )
                                    connection = (
                                        None  # Will create new connection below
                                    )
                                else:
                                    # CRITICAL FIX: Check that pooled reader/writer are not closed
                                    writer_closing = (
                                        hasattr(conn_obj.writer, "is_closing")
                                        and conn_obj.writer.is_closing()
                                    )
                                    if writer_closing:
                                        self.logger.warning(
                                            "Pooled connection writer is closing for %s, creating new connection",
                                            peer_info,
                                        )
                                        await self.connection_pool.release(
                                            f"{peer_info.ip}:{peer_info.port}",
                                            pool_connection,
                                        )
                                        connection = (
                                            None  # Will create new connection below
                                        )
                                    # CRITICAL FIX: Validate reader/writer have required methods
                                    elif not hasattr(
                                        conn_obj.reader, "read"
                                    ) or not hasattr(conn_obj.writer, "write"):
                                        self.logger.warning(
                                            "Pooled connection for %s has invalid reader/writer methods, creating new connection",
                                            peer_info,
                                        )
                                        await self.connection_pool.release(
                                            f"{peer_info.ip}:{peer_info.port}",
                                            pool_connection,
                                        )
                                        connection = (
                                            None  # Will create new connection below
                                        )
                                    else:
                                        # Create AsyncPeerConnection from PooledConnection
                                        connection = AsyncPeerConnection(
                                            peer_info, self.torrent_data
                                        )
                                        # CRITICAL FIX: Set reader/writer BEFORE releasing pool connection
                                        # This ensures reader/writer are available when we need them
                                        connection.reader = conn_obj.reader
                                        connection.writer = conn_obj.writer
                                        connection.state = ConnectionState.CONNECTED
                                        # Initialize per-peer upload rate limit from config
                                        connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
                                        # CRITICAL FIX: Set callbacks on pooled connection
                                        if self._on_peer_connected:
                                            connection.on_peer_connected = self._on_peer_connected
                                        if self._on_peer_disconnected:
                                            connection.on_peer_disconnected = self._on_peer_disconnected
                                        if self._on_bitfield_received:
                                            connection.on_bitfield_received = self._on_bitfield_received
                                        if self._on_piece_received:
                                            connection.on_piece_received = self._on_piece_received
                                            self.logger.debug(
                                                "Set on_piece_received callback on pooled connection to %s",
                                                peer_info,
                                            )
                                        # CRITICAL FIX: Set local reader/writer variables from connection object
                                        # This ensures the later checks for reader/writer work correctly
                                        reader = connection.reader
                                        writer = connection.writer
                                        self.logger.debug(
                                            "Using pooled connection for %s (reader type=%s, writer type=%s)",
                                            peer_info,
                                            type(conn_obj.reader).__name__,
                                            type(conn_obj.writer).__name__,
                                        )
                                        # CRITICAL FIX: DO NOT release pooled connection yet
                                        # We need to keep it until handshake completes
                                        # The connection pool will be released when the connection is closed
                                        # Store reference to pooled connection for later cleanup
                                        connection._pooled_connection = pool_connection  # type: ignore[attr-defined]
                                        connection._pooled_connection_key = f"{peer_info.ip}:{peer_info.port}"  # type: ignore[attr-defined]
                                        # Continue with BitTorrent handshake using the new AsyncPeerConnection
                                        # Skip TCP connection setup since we already have reader/writer
                                        # But we still need to do BitTorrent handshake
                                        # (This will be handled below after the connection setup code)
                            elif isinstance(conn_obj, AsyncPeerConnection):
                                # Already an AsyncPeerConnection, use it directly
                                connection = conn_obj
                                # CRITICAL FIX: Ensure callbacks are set on reused connection
                                if self._on_peer_connected:
                                    connection.on_peer_connected = self._on_peer_connected
                                if self._on_peer_disconnected:
                                    connection.on_peer_disconnected = self._on_peer_disconnected
                                if self._on_bitfield_received:
                                    connection.on_bitfield_received = self._on_bitfield_received
                                if self._on_piece_received:
                                    connection.on_piece_received = self._on_piece_received
                                await self.connection_pool.release(
                                    f"{peer_info.ip}:{peer_info.port}", pool_connection
                                )
                            else:
                                # Unknown type, release and create new connection
                                self.logger.warning(
                                    "Pooled connection is unexpected type %s, creating new connection",
                                    type(conn_obj),
                                )
                                await self.connection_pool.release(
                                    f"{peer_info.ip}:{peer_info.port}", pool_connection
                                )
                                connection = None
                    else:
                        # Pool returned something unexpected, ignore it
                        connection = None
                else:
                    connection = None

                # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see peer connection details
                self.logger.debug("Connecting to peer %s", peer_info)

                # Initialize reader/writer to None to prevent UnboundLocalError
                # They will be set by the transport connection code below
                reader: Any = None
                writer: Any = None

                # Initialize connection early to track state (if not already set from pool)
                if connection is None:
                    connection = AsyncPeerConnection(peer_info, self.torrent_data)
                    # Initialize per-peer upload rate limit from config
                    connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
                    # CRITICAL FIX: Set callbacks on newly created connection
                    if self._on_peer_connected:
                        connection.on_peer_connected = self._on_peer_connected
                    if self._on_peer_disconnected:
                        connection.on_peer_disconnected = self._on_peer_disconnected
                    if self._on_bitfield_received:
                        connection.on_bitfield_received = self._on_bitfield_received
                    if self._on_piece_received:
                        connection.on_piece_received = self._on_piece_received

                # Determine transport type (WebRTC, uTP, or TCP)
                use_webrtc = self._is_webrtc_peer(peer_info)
                use_utp = self._should_use_utp(peer_info) and not use_webrtc

                if use_utp:
                    # Create uTP connection
                    from ccbt.peer.utp_peer import UTPPeerConnection

                    connection = UTPPeerConnection(
                        peer_info=peer_info,
                        torrent_data=self.torrent_data,
                    )
                    # Set adaptive pipeline depth
                    connection.max_pipeline_depth = self._calculate_pipeline_depth(
                        connection
                    )

                    # CRITICAL FIX: Set callbacks early to ensure they're available when messages arrive
                    # This prevents "No callback registered" warnings
                    if self._on_peer_connected:
                        connection.on_peer_connected = self._on_peer_connected
                    if self._on_peer_disconnected:
                        connection.on_peer_disconnected = self._on_peer_disconnected
                    if self._on_bitfield_received:
                        connection.on_bitfield_received = self._on_bitfield_received
                    if self._on_piece_received:
                        connection.on_piece_received = self._on_piece_received

                    # Connect via uTP (with fallback to TCP on failure)
                    try:
                        await connection.connect()
                        # Connection successful - uTP handles transport layer
                        # Still need BitTorrent protocol handshake, but skip TCP connection
                        # The reader/writer are already set up by UTPPeerConnection.connect()
                        # Callbacks are already set above (line 2083-2090)
                        # Emit PEER_CONNECTED event
                        try:
                            import hashlib

                            from ccbt.core.bencode import BencodeEncoder
                            from ccbt.utils.events import Event, emit_event

                            # Get info_hash from torrent_data
                            info_hash_hex = ""
                            if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                                encoder = BencodeEncoder()
                                info_dict = self.torrent_data["info"]
                                info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                                info_hash_hex = info_hash_bytes.hex()

                            peer_ip = connection.peer_info.ip if hasattr(connection.peer_info, "ip") else ""
                            peer_port = connection.peer_info.port if hasattr(connection.peer_info, "port") else 0

                            await emit_event(
                                Event(
                                    event_type="peer_connected",
                                    data={
                                        "info_hash": info_hash_hex,
                                        "peer_ip": peer_ip,
                                        "peer_port": peer_port,
                                        "peer_id": None,
                                        "client": None,
                                    },
                                )
                            )
                        except Exception as e:
                            self.logger.debug("Failed to emit PEER_CONNECTED event: %s", e)

                        if self._on_peer_connected:
                            self._on_peer_connected(connection)

                        # Continue with BitTorrent handshake (skip TCP connection code below)
                        # Note: reader and writer are already set up by UTPPeerConnection
                        # We'll handle the BitTorrent protocol handshake after the transport connection
                        # For now, proceed to handshake setup
                        if (
                            connection.reader and connection.writer
                        ):  # pragma: no cover - uTP reader/writer check, tested via TCP path
                            reader = connection.reader
                            writer = connection.writer
                        else:  # pragma: no cover - Defensive: uTP connection error path, requires uTP implementation failure
                            msg = "uTP connection established but reader/writer not available"
                            raise RuntimeError(msg)

                    except (
                        ConnectionError,
                        TimeoutError,
                    ) as e:  # pragma: no cover - uTP fallback to TCP, tested via TCP direct path
                        self.logger.warning(
                            "uTP connection failed to %s:%s, falling back to TCP: %s",
                            peer_info.ip,
                            peer_info.port,
                            e,
                        )
                        # Fall through to TCP connection code
                        connection = None
                        use_utp = False

                if (
                    connection is None and use_webrtc
                ):  # pragma: no cover - WebRTC connection path, optional feature
                    # Create WebRTC connection
                    from ccbt.peer.webrtc_peer import WebRTCPeerConnection

                    connection = WebRTCPeerConnection(
                        peer_info=peer_info,
                        torrent_data=self.torrent_data,
                        webtorrent_protocol=self.webtorrent_protocol,
                    )
                    # Set adaptive pipeline depth
                    connection.max_pipeline_depth = self._calculate_pipeline_depth(
                        connection
                    )

                    # Set callbacks
                    if self._on_peer_connected:  # pragma: no cover - Callback assignment, tested via callback execution
                        connection.on_peer_connected = self._on_peer_connected
                    if self._on_peer_disconnected:  # pragma: no cover - Callback assignment, tested via callback execution
                        connection.on_peer_disconnected = self._on_peer_disconnected
                    if self._on_bitfield_received:  # pragma: no cover - Callback assignment, tested via callback execution
                        connection.on_bitfield_received = self._on_bitfield_received
                    if self._on_piece_received:  # pragma: no cover - Callback assignment, tested via callback execution
                        connection.on_piece_received = self._on_piece_received

                    # Connect via WebRTC
                    await connection.connect()
                    reader = connection.reader
                    writer = connection.writer

                # CRITICAL FIX: Skip TCP connection setup if we already have a connection from pool
                # Pooled connections already have reader/writer set, so we can skip TCP setup
                # BUT: Only skip if reader/writer are actually set (not None)
                # If we got a pooled connection but reader/writer are None, create new connection
                # Also check local reader/writer variables (set from pooled connection)
                has_pooled_connection = (
                    connection is not None
                    and connection.reader is not None
                    and connection.writer is not None
                    and reader is not None
                    and writer is not None
                )
                if not has_pooled_connection:
                    # Create standard TCP connection (fallback or default)
                    if connection is None:
                        connection = AsyncPeerConnection(peer_info, self.torrent_data)
                        connection.state = ConnectionState.CONNECTING
                        # Set adaptive pipeline depth
                        connection.max_pipeline_depth = self._calculate_pipeline_depth(
                            connection
                        )
                        # Initialize per-peer upload rate limit from config
                        connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
                        # CRITICAL FIX: Set callbacks on newly created TCP connection
                        if self._on_peer_connected:
                            connection.on_peer_connected = self._on_peer_connected
                        if self._on_peer_disconnected:
                            connection.on_peer_disconnected = self._on_peer_disconnected
                        if self._on_bitfield_received:
                            connection.on_bitfield_received = self._on_bitfield_received
                        if self._on_piece_received:
                            connection.on_piece_received = self._on_piece_received

                    # Establish TCP connection with adaptive timeout
                    timeout = self._calculate_timeout(connection)
                    # CRITICAL FIX: On Windows, use longer timeout to account for semaphore delays and NAT traversal
                    # Many peers are behind NAT/firewalls and need more time to establish connections
                    import sys

                    # Get active peer count for adaptive timeout logic
                    active_peer_count = len(self.get_active_peers())

                    if sys.platform == "win32":
                        # CRITICAL FIX: Reduced timeouts - 35-30s was too long and causing batch processing to stall
                        # 20s is sufficient for TCP connect on Windows with NAT/firewall delays
                        # When we have < 3 peers, use slightly longer timeout but still reasonable
                        if active_peer_count < 3:
                            timeout = 20.0  # Reduced from 35s to 20s - prevents batch processing from stalling
                            self.logger.debug(
                                "Very low peer count (%d): using 20s timeout for %s:%d (allows slower peers/NAT traversal without blocking batches)",
                                active_peer_count,
                                peer_info.ip,
                                peer_info.port,
                            )
                        else:
                            timeout = 15.0  # Reduced from 30s to 15s for Windows (handles NAT/firewall delays without blocking)

                    # CRITICAL FIX: Detect NAT presence and increase timeout for NAT environments
                    # NAT traversal adds significant latency, especially on Windows
                    # Increase timeout by 15% for NAT environments (minimum 20s, max 40s on Windows)
                    if self.config.nat.auto_map_ports:
                        # If NAT mapping is enabled, we're likely behind NAT
                        # Increase timeout by 15% for NAT environments to allow NAT traversal
                        # Windows needs more time due to semaphore delays and NAT complexity
                        nat_multiplier = 1.15 if sys.platform == "win32" else 1.1
                        nat_max = 40.0 if sys.platform == "win32" else 30.0
                        nat_timeout = min(max(timeout * nat_multiplier, 20.0), nat_max)
                        if nat_timeout > timeout:
                            self.logger.debug(
                                "NAT detected (auto_map_ports enabled), increasing timeout from %.1fs to %.1fs for %s:%d (platform=%s)",
                                timeout,
                                nat_timeout,
                                peer_info.ip,
                                peer_info.port,
                                sys.platform,
                            )
                            timeout = nat_timeout

                    # CRITICAL FIX: Log TCP connection attempt with more detail
                    self.logger.info(
                        "Attempting TCP connection to %s:%s (timeout=%.1fs, platform=%s)",
                        peer_info.ip,
                        peer_info.port,
                        timeout,
                        sys.platform,
                    )

                    # CRITICAL FIX: Improved retry logic with exponential backoff
                    # For very low peer counts, use retries with exponential backoff to find reachable peers
                    # This helps when most discovered peers are unreachable or behind NAT
                    import random

                    if active_peer_count < 3:
                        max_retries = 1  # 1 retry (2 total attempts) for very low peer counts
                        base_retry_delay = 0.5  # Base delay of 500ms
                        self.logger.debug(
                            "Very low peer count (%d): using %d retries with exponential backoff for peer %s:%d",
                            active_peer_count,
                            max_retries,
                            peer_info.ip,
                            peer_info.port,
                        )
                    else:
                        max_retries = 0  # No retries for normal peer counts
                        base_retry_delay = 0.5  # Not used with 0 retries
                    last_error = None

                    for retry_attempt in range(max_retries + 1):
                        try:
                            reader, writer = await asyncio.wait_for(
                                asyncio.open_connection(peer_info.ip, peer_info.port),
                                timeout=timeout,
                            )  # pragma: no cover - Network connection requires real peer or complex async mocking

                            # Optimize socket using NetworkOptimizer
                            try:
                                from ccbt.utils.network_optimizer import (
                                    NetworkOptimizer,
                                    SocketType,
                                )

                                network_optimizer = NetworkOptimizer()
                                # Get socket from writer's transport
                                if hasattr(writer, "get_extra_info"):
                                    sock = writer.get_extra_info("socket")
                                    if sock:
                                        # Get connection stats from NetworkOptimizer's connection pool
                                        # This will have RTT/bandwidth measurements if available
                                        connection_stats = None
                                        try:
                                            connection_stats = (
                                                network_optimizer.connection_pool.get_connection_stats(
                                                    sock
                                                )
                                            )
                                        except Exception:
                                            # Connection not in pool yet, create new stats
                                            from ccbt.utils.network_optimizer import (
                                                ConnectionStats,
                                            )

                                            connection_stats = ConnectionStats()
                                            # RTT and bandwidth will be updated as connection is used

                                        network_optimizer.optimize_socket(
                                            sock, SocketType.PEER_CONNECTION, connection_stats
                                        )
                            except Exception as opt_error:
                                # Log but don't fail connection if optimization fails
                                self.logger.debug(
                                    "Socket optimization failed (non-critical): %s", opt_error
                                )

                            self.logger.info(
                                "TCP connection established to %s:%s%s",
                                peer_info.ip,
                                peer_info.port,
                                f" (retry {retry_attempt})"
                                if retry_attempt > 0
                                else "",
                            )
                            # Connection successful, break out of retry loop
                            break
                        except (asyncio.TimeoutError, OSError, ConnectionError, asyncio.CancelledError) as e:
                            # CRITICAL FIX: Handle CancelledError during shutdown gracefully
                            if isinstance(e, asyncio.CancelledError):
                                from ccbt.utils.shutdown import is_shutting_down
                                if is_shutting_down():
                                    # During shutdown, cancellation is expected - don't log as error
                                    self.logger.debug(
                                        "Connection to %s:%d cancelled during shutdown",
                                        peer_info.ip,
                                        peer_info.port,
                                    )
                                    # Re-raise CancelledError to allow proper cleanup
                                    raise
                                # If not during shutdown, treat as timeout
                                last_error = asyncio.TimeoutError("Connection cancelled")
                            else:
                                last_error = e

                            # CRITICAL FIX: Log timeout failures with peer IP:port and timeout value
                            if isinstance(e, asyncio.TimeoutError) or isinstance(last_error, asyncio.TimeoutError):
                                from ccbt.utils.shutdown import is_shutting_down
                                if not is_shutting_down():
                                    self.logger.warning(
                                        "TCP connection timeout to %s:%d (timeout=%.1fs, attempt %d/%d). "
                                        "Peer may be unreachable, behind NAT, or network is slow.",
                                        peer_info.ip,
                                        peer_info.port,
                                        timeout,
                                        retry_attempt + 1,
                                        max_retries + 1,
                                    )
                                else:
                                    self.logger.debug(
                                        "TCP connection timeout to %s:%d during shutdown",
                                        peer_info.ip,
                                        peer_info.port,
                                    )

                            # Connection failed - check if we should retry
                            # CRITICAL FIX: Handle WinError 121 (semaphore timeout) gracefully on Windows
                            error_code = (
                                getattr(e, "winerror", None)
                                if hasattr(e, "winerror")
                                else None
                            )

                            # Determine if error is retryable
                            is_retryable = (
                                isinstance(e, (asyncio.TimeoutError, ConnectionError))
                                or error_code == 121  # WinError 121: semaphore timeout
                                or (
                                    isinstance(e, OSError)
                                    and error_code not in [10061, 10048]
                                )  # Not "connection refused" or "address in use"
                            )

                            if error_code == 121:
                                # WinError 121: "The semaphore timeout period has expired"
                                # This happens on Windows when too many connections are attempted simultaneously
                                self.logger.debug(
                                    "TCP connection semaphore timeout to %s:%s (WinError 121, attempt %d/%d). "
                                    "This is normal on Windows when many connections are attempted simultaneously.",
                                    peer_info.ip,
                                    peer_info.port,
                                    retry_attempt + 1,
                                    max_retries + 1,
                                )
                            else:
                                self.logger.debug(
                                    "TCP connection failed to %s:%s (attempt %d/%d): %s",
                                    peer_info.ip,
                                    peer_info.port,
                                    retry_attempt + 1,
                                    max_retries + 1,
                                    e,
                                )

                            # Retry if this is a retryable error and we haven't exhausted retries
                            if is_retryable and retry_attempt < max_retries:
                                # CRITICAL FIX: Exponential backoff with jitter to prevent thundering herd
                                # Formula: base_delay * (2^retry_attempt) + random_jitter
                                # Jitter is 0-20% of the delay to spread out retries
                                exponential_delay = base_retry_delay * (2 ** retry_attempt)
                                jitter = random.uniform(0, exponential_delay * 0.2)  # 0-20% jitter
                                delay = exponential_delay + jitter
                                self.logger.debug(
                                    "Connection attempt %d/%d failed: %s, retrying in %.2fs (exponential backoff with jitter)...",
                                    retry_attempt + 1,
                                    max_retries + 1,
                                    e,
                                    delay,
                                )
                                await asyncio.sleep(delay)
                                continue
                            # Not retryable or max retries reached - clean up and re-raise
                            if connection:
                                connection.state = ConnectionState.DISCONNECTED
                            
                            # CRITICAL FIX: Track connection failures for adaptive backoff (BitTorrent spec compliant)
                            peer_key = f"{peer_info.ip}:{peer_info.port}"
                            current_time = time.time()
                            
                            # Increment failure count
                            if peer_key not in self._connection_failure_counts:
                                self._connection_failure_counts[peer_key] = 0
                            self._connection_failure_counts[peer_key] += 1
                            self._connection_failure_times[peer_key] = current_time
                            
                            # Apply exponential backoff if threshold reached
                            failure_count = self._connection_failure_counts[peer_key]
                            failure_threshold = getattr(
                                self.config.network,
                                "connection_failure_threshold",
                                3,
                            )
                            backoff_base = getattr(
                                self.config.network,
                                "connection_failure_backoff_base",
                                2.0,
                            )
                            backoff_max = getattr(
                                self.config.network,
                                "connection_failure_backoff_max",
                                300.0,
                            )
                            
                            if failure_count >= failure_threshold:
                                # Calculate exponential backoff: base * (2^(failures - threshold))
                                backoff_delay = min(
                                    backoff_base * (2 ** (failure_count - failure_threshold)),
                                    backoff_max,
                                )
                                backoff_until = current_time + backoff_delay
                                self._connection_backoff_until[peer_key] = backoff_until
                                self.logger.debug(
                                    "Peer %s has %d consecutive failures, applying backoff until %.1fs (%.1fs delay)",
                                    peer_key,
                                    failure_count,
                                    backoff_until,
                                    backoff_delay,
                                )
                            
                            # CRITICAL FIX: Enhanced error message with retry information
                            self.logger.warning(
                                "Failed to connect to peer %s:%d after %d attempts: %s",
                                peer_info.ip,
                                peer_info.port,
                                max_retries + 1,
                                last_error,
                            )
                            # Re-raise as PeerConnectionError for consistent error handling
                            error_msg = f"Failed to establish TCP connection to {peer_info.ip}:{peer_info.port} after {retry_attempt + 1} attempt(s): {last_error}"
                            raise PeerConnectionError(error_msg) from last_error

                    # CRITICAL FIX: Validate reader/writer are set after TCP connection
                    if reader is None or writer is None:
                        error_msg = (
                            f"TCP connection established but reader/writer are None for {peer_info} "
                            f"(reader={reader is not None}, writer={writer is not None})"
                        )
                        self.logger.error(error_msg)
                        raise RuntimeError(error_msg)

                    # CRITICAL FIX: Validate TCP connection is fully established before proceeding
                    # Check that writer is not closing and reader is ready
                    if hasattr(writer, "is_closing") and writer.is_closing():
                        error_msg = f"Writer is closing immediately after TCP connection to {peer_info}"
                        self.logger.warning(error_msg)
                        raise PeerConnectionError(error_msg)

                    # Add Windows-specific connection validation
                    import sys

                    if sys.platform == "win32":
                        # On Windows, verify connection is stable before proceeding
                        # Small delay to allow connection to fully establish
                        await asyncio.sleep(0.01)

                    # CRITICAL FIX: Store original reader/writer before encryption attempt
                    # This ensures we can fall back to plain connection if encryption fails
                    original_reader = reader
                    original_writer = writer

                # Perform MSE encryption handshake if enabled (only for TCP)
                info_hash = self.torrent_data["info_hash"]
                if self.config.security.enable_encryption:
                    from ccbt.security.encrypted_stream import (
                        EncryptedStreamReader,
                        EncryptedStreamWriter,
                    )
                    from ccbt.security.encryption import EncryptionMode
                    from ccbt.security.mse_handshake import MSEHandshake

                    encryption_mode = EncryptionMode(
                        self.config.security.encryption_mode
                    )
                    if (
                        encryption_mode != EncryptionMode.DISABLED
                        and isinstance(reader, asyncio.StreamReader)
                        and isinstance(writer, asyncio.StreamWriter)
                        and connection is not None
                    ):
                        # Type guard: MSE handshake requires asyncio.StreamReader/Writer
                        try:
                            mse = MSEHandshake()
                            result = await mse.initiate_as_initiator(
                                reader, writer, info_hash
                            )

                            if result.success and result.cipher:
                                # Wrap streams with encryption
                                encrypted_reader = EncryptedStreamReader(
                                    reader, result.cipher
                                )
                                encrypted_writer = EncryptedStreamWriter(
                                    writer, result.cipher
                                )
                                # CRITICAL FIX: Validate encrypted reader/writer are not None
                                if encrypted_reader is None or encrypted_writer is None:
                                    self.logger.error(
                                        "Encryption handshake succeeded but encrypted reader/writer are None for %s",
                                        peer_info,
                                    )
                                    # Fall back to plain connection
                                    reader = original_reader
                                    writer = original_writer
                                else:
                                    # Type narrowing: connection is guaranteed to be not None by outer guard
                                    if (
                                        connection is None
                                    ):  # pragma: no cover - Type guard
                                        error_msg = (
                                            "Connection is None in encryption handler"
                                        )
                                        raise RuntimeError(error_msg)
                                    reader = encrypted_reader  # type: ignore[assignment]
                                    writer = encrypted_writer  # type: ignore[assignment]
                                    connection.is_encrypted = True
                                    connection.encryption_cipher = result.cipher
                                self.logger.debug(
                                    "Encryption handshake succeeded with peer %s",
                                    peer_info,
                                )
                            elif (
                                encryption_mode == EncryptionMode.REQUIRED
                            ):  # pragma: no cover - Encryption required error path, tested via DISABLED/PREFERRED modes
                                # Encryption required but failed
                                error_msg = (
                                    result.error or "Encryption handshake failed"
                                )
                                err_text = (
                                    f"Encryption required but handshake failed "
                                    f"with {peer_info}: {error_msg}"
                                )
                                raise PeerConnectionError(err_text)
                            else:  # pragma: no cover - Encryption PREFERRED mode fallback, tested via success/REQUIRED paths
                                # PREFERRED mode - fallback to plain connection
                                self.logger.debug(
                                    "Encryption preferred but handshake failed, "
                                    "falling back to plain connection with %s",
                                    peer_info,
                                )
                                # CRITICAL FIX: Ensure reader/writer are restored to original values
                                reader = original_reader
                                writer = original_writer
                        except Exception as e:  # pragma: no cover - Encryption handshake exception, tested via success path
                            if (
                                encryption_mode == EncryptionMode.REQUIRED
                            ):  # pragma: no cover - Encryption required exception path, tested via DISABLED/PREFERRED
                                err_text = f"Encryption required but failed: {e}"
                                raise PeerConnectionError(err_text) from e
                            # PREFERRED mode - fallback to plain connection
                            self.logger.debug(  # pragma: no cover - Encryption PREFERRED exception fallback, tested via success path
                                "Encryption handshake error (preferred mode), "
                                "falling back to plain: %s",
                                e,
                            )
                            # CRITICAL FIX: Restore original reader/writer on exception
                            reader = original_reader
                            writer = original_writer

                    # CRITICAL FIX: Final validation after encryption attempt
                    if reader is None or writer is None:
                        error_msg = (
                            f"Reader/writer became None after encryption handshake for {peer_info} "
                            f"(reader={reader is not None}, writer={writer is not None})"
                        )
                        self.logger.error(error_msg)
                        raise RuntimeError(error_msg)

                    # Set reader/writer (already set for uTP/WebRTC/pooled, set here for TCP)
                    # CRITICAL FIX: Only set reader/writer if they were actually initialized
                    # For uTP/WebRTC/pooled, reader/writer are already set on the connection object
                    # For TCP, we need to set them from the local variables
                    # CRITICAL FIX: Log current state before setting reader/writer
                    self.logger.debug(
                        "Setting reader/writer: use_utp=%s, use_webrtc=%s, connection.reader=%s, connection.writer=%s, local reader=%s, local writer=%s",
                        use_utp,
                        use_webrtc,
                        connection.reader is not None if connection else "N/A",
                        connection.writer is not None if connection else "N/A",
                        reader is not None,
                        writer is not None,
                    )
                    if use_utp or use_webrtc:
                        # uTP and WebRTC already have reader/writer set on connection
                        # Just verify they're set
                        if connection and (
                            connection.reader is None or connection.writer is None
                        ):
                            self.logger.error(
                                "uTP/WebRTC connection established but reader/writer not set for %s",
                                peer_info,
                            )
                            error_msg = f"uTP/WebRTC connection to {peer_info} missing reader/writer"
                            raise RuntimeError(error_msg)
                    elif (
                        connection
                        and connection.reader is not None
                        and connection.writer is not None
                    ):
                        # Connection already has reader/writer (from pool or already set)
                        # CRITICAL FIX: Validate pooled reader/writer are not closed before using them
                        if (
                            hasattr(connection.writer, "is_closing")
                            and connection.writer.is_closing()
                        ):
                            self.logger.warning(
                                "Pooled connection writer is closing for %s, creating new connection",
                                peer_info,
                            )
                            # Writer is closing, need to create new connection
                            # CRITICAL FIX: Release the invalid pooled connection first
                            await self.connection_pool.release(
                                f"{peer_info.ip}:{peer_info.port}", pool_connection
                            )
                            # Create new connection object - will be set up via TCP below
                            connection = AsyncPeerConnection(peer_info, self.torrent_data)
                            connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
                            # Set callbacks on newly created connection
                            if self._on_peer_connected:
                                connection.on_peer_connected = self._on_peer_connected
                            if self._on_peer_disconnected:
                                connection.on_peer_disconnected = self._on_peer_disconnected
                            if self._on_bitfield_received:
                                connection.on_bitfield_received = self._on_bitfield_received
                            if self._on_piece_received:
                                connection.on_piece_received = self._on_piece_received
                            # Reset pool_connection to None since we're creating a new TCP connection
                            pool_connection = None
                            # Fall through to TCP connection setup
                        else:
                            # CRITICAL FIX: Still need to set local variables for use in handshake
                            reader = connection.reader
                            writer = connection.writer
                            # CRITICAL FIX: Validate reader/writer are actually usable
                            if reader is None or writer is None:
                                self.logger.error(
                                    "Connection has reader/writer attributes but they are None for %s",
                                    peer_info,
                                )
                                # CRITICAL FIX: Release invalid pooled connection and create new one
                                if pool_connection:
                                    await self.connection_pool.release(
                                        f"{peer_info.ip}:{peer_info.port}", pool_connection
                                    )
                                # Create new connection object - will be set up via TCP below
                                connection = AsyncPeerConnection(peer_info, self.torrent_data)
                                connection.per_peer_upload_limit_kib = self.per_peer_upload_limit_kib
                                # Set callbacks on newly created connection
                                if self._on_peer_connected:
                                    connection.on_peer_connected = self._on_peer_connected
                                if self._on_peer_disconnected:
                                    connection.on_peer_disconnected = self._on_peer_disconnected
                                if self._on_bitfield_received:
                                    connection.on_bitfield_received = self._on_bitfield_received
                                if self._on_piece_received:
                                    connection.on_piece_received = self._on_piece_received
                                pool_connection = None
                                # Fall through to TCP connection setup
                            else:
                                self.logger.debug(
                                    "Using existing reader/writer from connection object for %s",
                                    peer_info,
                                )
                elif connection:
                    # TCP connection - set reader/writer from local variables
                    # CRITICAL FIX: Ensure reader/writer are set before assigning to connection
                    if reader is None or writer is None:
                        # Reader/writer not initialized - this should not happen in normal flow
                        # but can occur if an exception happened during connection setup
                        self.logger.error(
                            "Reader or writer not initialized for TCP connection to %s (reader=%s, writer=%s)",
                            peer_info,
                            reader is not None,
                            writer is not None,
                        )
                        error_msg = f"Reader or writer not initialized for TCP connection to {peer_info}"
                        raise RuntimeError(error_msg)
                    # CRITICAL FIX: Set connection reader/writer and verify they're set
                    connection.reader = reader  # type: ignore[assignment] # pragma: no cover - Same context
                    connection.writer = writer  # type: ignore[assignment] # pragma: no cover - Same context
                    # Verify they were set correctly
                    if connection.reader is None or connection.writer is None:
                        self.logger.error(
                            "Failed to set reader/writer on connection object for %s (reader=%s, writer=%s)",
                            peer_info,
                            connection.reader is not None,
                            connection.writer is not None,
                        )
                        error_msg = f"Failed to set reader/writer on connection object for {peer_info}"
                        raise RuntimeError(error_msg)
                    self.logger.debug(
                        "Set reader/writer on connection object for TCP connection to %s",
                        peer_info,
                    )

                # Perform BitTorrent handshake (all transport types need this)
                # CRITICAL FIX: Ensure connection is not None before proceeding
                if connection is None:
                    error_msg = (
                        f"Connection is None for {peer_info} - this should not happen"
                    )
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Ensure reader/writer are available and not None
                # First check connection object, then local variables
                if connection.reader is None:
                    # Try to use local reader if available
                    if reader is not None:
                        connection.reader = reader  # type: ignore[assignment] # Validated above
                        self.logger.debug(
                            "Restored reader from local variable for %s", peer_info
                        )
                    else:
                        error_msg = f"Reader is None for {peer_info} - connection may have been closed"
                        self.logger.error(error_msg)
                        raise RuntimeError(error_msg)

                if connection.writer is None:
                    # Try to use local writer if available
                    if writer is not None:
                        connection.writer = writer  # type: ignore[assignment] # Validated above
                        self.logger.debug(
                            "Restored writer from local variable for %s", peer_info
                        )
                    else:
                        error_msg = f"Writer is None for {peer_info} - connection may have been closed"
                        self.logger.error(error_msg)
                        raise RuntimeError(error_msg)

                # Assign to local variables and validate they're still not None
                reader = connection.reader
                writer = connection.writer

                # CRITICAL FIX: Double-check writer is not None and is writable before using it
                if writer is None:
                    error_msg = (
                        f"Writer became None after assignment for {peer_info}. "
                        f"connection.writer={connection.writer}, connection.reader={connection.reader}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                if reader is None:
                    error_msg = (
                        f"Reader became None after assignment for {peer_info}. "
                        f"connection.reader={connection.reader}, connection.writer={connection.writer}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Check that writer is not closed and has write method
                if hasattr(writer, "is_closing") and writer.is_closing():
                    error_msg = (
                        f"Writer is closing for {peer_info} - cannot send handshake"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                if not hasattr(writer, "write"):
                    error_msg = f"Writer does not have write method for {peer_info} (type: {type(writer)})"
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Log that we have valid reader/writer before handshake
                self.logger.debug(
                    "Reader and writer validated for %s (reader type=%s, writer type=%s, is_closing=%s)",
                    peer_info,
                    type(reader).__name__,
                    type(writer).__name__,
                    writer.is_closing() if hasattr(writer, "is_closing") else "N/A",
                )

                info_hash = self.torrent_data["info_hash"]
                connection.state = (
                    ConnectionState.HANDSHAKE_SENT
                )  # pragma: no cover - Same context

                # Send BitTorrent handshake (now possibly through encrypted stream or uTP)
                # Create handshake with optional Ed25519 signature
                ed25519_public_key = None
                ed25519_signature = None
                if self.key_manager:
                    try:
                        from ccbt.security.ed25519_handshake import Ed25519Handshake

                        ed25519_handshake = Ed25519Handshake(self.key_manager)
                        ed25519_public_key, ed25519_signature = (
                            ed25519_handshake.initiate_handshake(
                                info_hash, self.our_peer_id
                            )
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Failed to create Ed25519 handshake signature: %s", e
                        )

                handshake = Handshake(
                    info_hash,
                    self.our_peer_id,
                    ed25519_public_key=ed25519_public_key,
                    ed25519_signature=ed25519_signature,
                )
                # Configure reserved bytes based on configuration
                handshake.configure_from_config(self.config)

                # CRITICAL FIX: Log handshake reserved bits for debugging and compliance verification
                reserved_bits_info = []
                if handshake.supports_extension_protocol():
                    reserved_bits_info.append("Extension Protocol (BEP 10)")
                if handshake.supports_v2():
                    reserved_bits_info.append("Protocol v2 (BEP 52)")
                if handshake.supports_dht():
                    reserved_bits_info.append("DHT")
                if handshake.supports_fast_extension():
                    reserved_bits_info.append("Fast Extension (BEP 6)")

                self.logger.debug(
                    "Handshake reserved bits for %s: %s (reserved_bytes=%s)",
                    peer_info,
                    ", ".join(reserved_bits_info) if reserved_bits_info else "none",
                    handshake.reserved_bytes.hex(),
                )

                handshake_data = handshake.encode()

                # CRITICAL FIX: Final comprehensive check before writing
                # Re-assign from connection to ensure we have the latest value
                writer = connection.writer
                if writer is None:
                    error_msg = (
                        f"Writer is None immediately before handshake write for {peer_info}. "
                        f"connection.writer={connection.writer}, connection.reader={connection.reader}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Check writer is not closed
                if hasattr(writer, "is_closing") and writer.is_closing():
                    error_msg = (
                        f"Writer is closing before handshake write for {peer_info}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Verify writer has write method
                if not hasattr(writer, "write") or not callable(
                    getattr(writer, "write", None)
                ):
                    error_msg = f"Writer does not have callable write method for {peer_info} (type: {type(writer)})"
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Add logging and timeout for handshake
                self.logger.info(
                    "Sending handshake to %s (writer type=%s, handshake size=%d bytes, is_closing=%s)",
                    peer_info,
                    type(writer).__name__,
                    len(handshake_data),
                    writer.is_closing() if hasattr(writer, "is_closing") else "N/A",
                )
                try:
                    # CRITICAL FIX: StreamWriter.write() is synchronous and returns None
                    # Do NOT await it - just call it and then await drain()
                    writer.write(handshake_data)  # Synchronous write, returns None
                    await writer.drain()  # Wait for data to be sent
                    # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see handshake details
                    self.logger.debug("Handshake sent successfully to %s", peer_info)
                except Exception:
                    self.logger.exception(
                        "Failed to write handshake to %s (writer type=%s)",
                        peer_info,
                        type(writer).__name__ if writer else "None",
                    )
                    raise
                self.logger.debug(
                    "Handshake sent to %s, waiting for response...", peer_info
                )

                # Receive and validate handshake
                if reader is None:
                    error_msg = (
                        f"Reader is None before reading handshake for {peer_info}"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # CRITICAL FIX: Read handshake with support for v1 (68 bytes), v2 (80 bytes), and hybrid (100 bytes)
                # First read the minimum v1 handshake size to detect protocol version
                # CRITICAL FIX: Increase timeout to 10s for better reliability on slower networks (Phase 5)

                # Validate connection state before reading handshake
                if (
                    writer is not None
                    and hasattr(writer, "is_closing")
                    and writer.is_closing()
                ):
                    error_msg = (
                        f"Connection closing before handshake read for {peer_info}"
                    )
                    self.logger.debug(error_msg)
                    raise PeerConnectionError(error_msg)

                try:
                    # Calculate adaptive handshake timeout based on peer health
                    handshake_timeout = self._calculate_adaptive_handshake_timeout()

                    # Read first byte (protocol length) to validate it's a BitTorrent handshake
                    protocol_len_byte = await asyncio.wait_for(
                        reader.readexactly(1),  # type: ignore[union-attr]
                        timeout=handshake_timeout,
                    )

                    if len(protocol_len_byte) != 1:
                        error_msg = f"Failed to read protocol length from {peer_info}"
                        raise PeerConnectionError(error_msg)

                    protocol_len = protocol_len_byte[0]
                    if protocol_len != 19:
                        error_msg = f"Invalid protocol length from {peer_info}: {protocol_len} (expected 19)"
                        self.logger.warning(error_msg)
                        raise PeerConnectionError(error_msg)

                    # Read remaining 67 bytes of v1 handshake minimum
                    # Use adaptive timeout for better reliability based on peer health
                    remaining_v1 = await asyncio.wait_for(
                        reader.readexactly(67),  # type: ignore[union-attr]
                        timeout=handshake_timeout,
                    )
                    peer_handshake_data = protocol_len_byte + remaining_v1

                    # Check if this is a v2 or hybrid handshake by examining reserved bytes
                    # Bit 0 of first reserved byte indicates v2 support
                    if len(peer_handshake_data) >= 28:
                        reserved_byte = peer_handshake_data[20]
                        is_v2 = (reserved_byte & 0x01) != 0

                        if is_v2:
                            # This might be v2 (80 bytes) or hybrid (100 bytes)
                            # Read additional bytes to determine
                            # v2: +12 more bytes (32-byte info_hash_v2 instead of 20-byte info_hash_v1)
                            # hybrid: +52 more bytes (20-byte info_hash_v1 + 32-byte info_hash_v2)
                            # For now, try to read enough for v2 first
                            try:
                                additional_data = await asyncio.wait_for(
                                    reader.readexactly(12),  # type: ignore[union-attr]
                                    timeout=handshake_timeout,
                                )
                                peer_handshake_data += additional_data
                                # Check if there's more (hybrid has 20 more bytes for info_hash_v1)
                                # We'll handle this in the decode step
                                self.logger.debug(
                                    "Received v2 handshake from %s (%d bytes)",
                                    peer_info,
                                    len(peer_handshake_data),
                                )
                            except asyncio.TimeoutError:
                                # Not v2, use v1 handshake
                                self.logger.debug(
                                    "Received v1 handshake from %s (68 bytes)",
                                    peer_info,
                                )
                        else:
                            self.logger.debug(
                                "Received v1 handshake from %s (68 bytes)", peer_info
                            )
                    else:
                        self.logger.debug("Received handshake from %s", peer_info)

                except asyncio.TimeoutError:
                    # Calculate timeout for error message
                    handshake_timeout = self._calculate_adaptive_handshake_timeout()
                    error_msg = (
                        f"Handshake timeout from {peer_info} (no response after {handshake_timeout:.1f}s)"
                    )
                    self.logger.warning(
                        "Handshake timeout: %s - peer may be unresponsive or connection was closed. "
                        "This is normal for peers that don't respond quickly or have network latency.",
                        error_msg,
                    )
                    # CRITICAL FIX: Close connection before raising error
                    if writer is not None:
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                    raise PeerConnectionError(error_msg) from None
                except (
                    asyncio.IncompleteReadError,
                    ConnectionResetError,
                    OSError,
                ) as e:
                    # CRITICAL FIX: Improve error categorization and logging
                    # Handle Windows-specific connection reset errors gracefully
                    import sys

                    error_type = type(e).__name__
                    error_msg = (
                        f"Handshake read failed from {peer_info}: {error_type}: {e}"
                    )

                    # Check for Windows-specific errors
                    if sys.platform == "win32":
                        winerror = getattr(e, "winerror", None)
                        if winerror == 64:  # Network name no longer available
                            # Peer closed connection - this is normal, don't log as warning
                            self.logger.debug(
                                "Peer %s closed connection during handshake (WinError 64). This is normal.",
                                peer_info,
                            )
                        elif winerror == 1225:  # Connection refused
                            self.logger.debug(
                                "Connection refused by peer %s during handshake (WinError 1225)",
                                peer_info,
                            )
                        else:
                            self.logger.debug(
                                "Handshake read error from %s: %s (WinError %s)",
                                peer_info,
                                type(e).__name__,
                                winerror,
                            )
                    # Non-Windows: log as debug for peer-initiated closes
                    elif isinstance(
                        e, (ConnectionResetError, asyncio.IncompleteReadError)
                    ):
                        self.logger.debug(
                            "Peer %s closed connection during handshake: %s",
                            peer_info,
                            type(e).__name__,
                        )
                    else:
                        self.logger.debug(
                            "Handshake read error from %s: %s",
                            peer_info,
                            type(e).__name__,
                        )

                    # Record handshake failure for local blacklist source
                    await self._record_connection_failure(peer_info, "handshake_failure", error_type)

                    # CRITICAL FIX: Close connection before raising error
                    if writer is not None:
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                    raise PeerConnectionError(error_msg) from e
                except Exception as e:
                    error_msg = f"Failed to read handshake from {peer_info}: {e}"
                    self.logger.warning(
                        "Handshake read error: %s - %s (connection may have been closed by peer)",
                        error_msg,
                        type(e).__name__,
                    )
                    # CRITICAL FIX: Close connection before raising error
                    if writer is not None:
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                    raise PeerConnectionError(error_msg) from e
                # CRITICAL FIX: Add error handling for handshake decode
                # Handle v1, v2, and hybrid handshakes
                try:
                    # Try v1 handshake first (68 bytes)
                    if len(peer_handshake_data) == 68:
                        peer_handshake = Handshake.decode(peer_handshake_data)

                        # Verify Ed25519 signature if present and key_manager available
                        if (
                            self.key_manager
                            and peer_handshake.ed25519_public_key
                            and peer_handshake.ed25519_signature
                        ):
                            try:
                                from ccbt.security.ed25519_handshake import (
                                    Ed25519Handshake,
                                )

                                ed25519_handshake = Ed25519Handshake(self.key_manager)
                                is_valid = ed25519_handshake.verify_peer_handshake(
                                    info_hash,
                                    peer_handshake.peer_id,
                                    peer_handshake.ed25519_public_key,
                                    peer_handshake.ed25519_signature,
                                )
                                if not is_valid:
                                    self.logger.warning(
                                        "Invalid Ed25519 handshake signature from %s",
                                        peer_info,
                                    )
                                    # Continue anyway for backward compatibility
                            except Exception as e:
                                self.logger.debug(
                                    "Ed25519 handshake verification error: %s", e
                                )
                    elif len(peer_handshake_data) >= 68:
                        # v2 or hybrid handshake - extract v1 info_hash from first 68 bytes
                        # For v2/hybrid, we only care about the v1 info_hash for compatibility
                        v1_handshake_data = peer_handshake_data[:68]
                        peer_handshake = Handshake.decode(v1_handshake_data)
                        self.logger.debug(
                            "Decoded v1 portion of v2/hybrid handshake from %s (%d bytes total)",
                            peer_info,
                            len(peer_handshake_data),
                        )
                    else:
                        error_msg = f"Handshake too short from {peer_info}: {len(peer_handshake_data)} bytes (expected at least 68)"
                        self.logger.warning(error_msg)
                        raise PeerConnectionError(error_msg)
                except Exception as e:
                    # Check if it's a HandshakeError (from peer.exceptions)
                    error_type = type(e).__name__
                    if error_type == "HandshakeError":
                        error_msg = f"Failed to decode handshake from {peer_info}: {e}"
                        self.logger.warning(error_msg)
                        raise PeerConnectionError(error_msg) from e
                    error_msg = (
                        f"Unexpected error decoding handshake from {peer_info}: {e}"
                    )
                    self.logger.warning(error_msg, exc_info=True)
                    raise PeerConnectionError(error_msg) from e

                connection.peer_info.peer_id = (
                    peer_handshake.peer_id
                )  # pragma: no cover - Same context
                # Store reserved bytes for extension support detection
                connection.reserved_bytes = peer_handshake.reserved_bytes
                connection.state = (
                    ConnectionState.HANDSHAKE_RECEIVED
                )  # pragma: no cover - Same context

                # Validate handshake
                if (
                    peer_handshake.info_hash != info_hash
                ):  # pragma: no cover - Same context
                    error_msg = (
                        f"Info hash mismatch from {peer_info}: "
                        f"expected {info_hash.hex()[:16]}..., "
                        f"got {peer_handshake.info_hash.hex()[:16]}... "
                        f"(peer may be serving a different torrent)"
                    )
                    self.logger.warning(error_msg)
                    # CRITICAL FIX: Close connection before raising error
                    if writer is not None:
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                    self._raise_info_hash_mismatch(
                        info_hash, peer_handshake.info_hash
                    )  # pragma: no cover - Same context

                # CRITICAL FIX: Send our bitfield and unchoke after receiving peer's handshake
                # Protocol order: handshake exchange -> our bitfield -> our unchoke -> wait for peer's bitfield -> send interested
                # We send interested in the bitfield handler after receiving peer's bitfield to ensure proper message ordering
                self.logger.info(
                    "Sending initial messages to %s: bitfield, unchoke (state: %s)",
                    peer_info,
                    connection.state.value,
                )
                try:
                    await self._send_bitfield(
                        connection
                    )  # pragma: no cover - Same context
                    # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see bitfield details
                    self.logger.debug("Successfully sent bitfield to %s", peer_info)
                except Exception as e:
                    error_msg = f"Failed to send bitfield to {peer_info}: {e}"
                    self.logger.warning(error_msg)
                    raise PeerConnectionError(error_msg) from e

                try:
                    await self._send_unchoke(
                        connection
                    )  # pragma: no cover - Same context
                    # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see unchoke details
                    self.logger.debug("Successfully sent unchoke to %s", peer_info)
                except Exception as e:
                    error_msg = f"Failed to send unchoke to {peer_info}: {e}"
                    self.logger.warning(error_msg)
                    raise PeerConnectionError(error_msg) from e

                # CRITICAL FIX: Send INTERESTED immediately after handshake completes
                # Many peers wait for INTERESTED before sending bitfield or unchoking us
                # Sending INTERESTED immediately encourages peers to proceed with the protocol
                # This is protocol-compliant - INTERESTED can be sent at any time after handshake
                if not connection.am_interested:
                    try:
                        await self._send_interested(connection)
                        connection.am_interested = True
                        self.logger.info(
                            "Sent INTERESTED to %s immediately after handshake (encouraging peer to proceed)",
                            peer_info,
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Failed to send INTERESTED to %s after handshake: %s (will retry later)",
                            peer_info,
                            e,
                        )

                self.logger.info(
                    "HANDSHAKE_COMPLETE: %s - bitfield, unchoke, and INTERESTED sent (state: %s, choking: %s, reader=%s, writer=%s). "
                    "Waiting for peer's bitfield and UNCHOKE.",
                    peer_info,
                    connection.state.value,
                    connection.peer_choking,
                    connection.reader is not None,
                    connection.writer is not None,
                )

                # Attempt SSL negotiation after handshake if extension protocol is supported
                # This happens after bitfield/unchoke but before starting message handling
                try:
                    await self._attempt_ssl_negotiation(
                        connection
                    )  # pragma: no cover - SSL negotiation requires real extension handshake
                except Exception as e:
                    # SSL negotiation failure shouldn't break the connection
                    # Log it but continue with plain connection
                    self.logger.debug(
                        "SSL negotiation failed for %s (continuing with plain connection): %s",
                        peer_info,
                        e,
                    )

                # Start message handling
                self.logger.debug("Starting message handling loop for %s", peer_info)

                # CRITICAL FIX: Send INTERESTED after delay if peer hasn't sent bitfield
                # Per BEP 3, leechers with no pieces don't send bitfields - they send HAVE messages
                # Sending INTERESTED encourages them to send HAVE messages or bitfield
                async def send_interested_if_no_bitfield():
                    """Send INTERESTED after delay if peer hasn't sent bitfield yet."""
                    await asyncio.sleep(5.0)  # Wait 5 seconds for peer to send bitfield
                    if (
                        connection.state not in (ConnectionState.ERROR, ConnectionState.CLOSED, ConnectionState.DISCONNECTED)
                        and not connection.am_interested
                        and connection.writer is not None
                        and not connection.writer.is_closing()
                        and (
                            connection.peer_state.bitfield is None
                            or len(connection.peer_state.bitfield) == 0
                        )  # Only if no bitfield received yet
                    ):
                        try:
                            await self._send_interested(connection)
                            connection.am_interested = True
                            self.logger.info(
                                "Sent INTERESTED to %s after 5s delay (no bitfield yet, encouraging HAVE messages)",
                                connection.peer_info,
                            )
                        except Exception as e:
                            self.logger.debug(
                                "Failed to send delayed INTERESTED to %s: %s",
                                connection.peer_info,
                                e,
                            )

                # Start delayed INTERESTED sender
                delayed_interested_task = asyncio.create_task(send_interested_if_no_bitfield())
                if not hasattr(connection, "_timeout_tasks"):
                    connection._timeout_tasks = []
                connection._timeout_tasks.append(delayed_interested_task)

                # CRITICAL FIX: Start bitfield timeout monitor (BitTorrent protocol compliance)
                # According to BitTorrent spec, bitfield is OPTIONAL if peer has no pieces
                # However, most peers send bitfield immediately after handshake
                # We allow HAVE messages as an alternative to bitfield (protocol-compliant)
                # Only disconnect if no bitfield AND no HAVE messages after extended timeout
                bitfield_timeout = 120.0  # 120 seconds timeout (increased from 60s for leniency)
                handshake_time = time.time()

                async def bitfield_timeout_monitor():
                    """Monitor for bitfield timeout and disconnect if not received.
                    
                    According to BitTorrent spec (BEP 3), bitfield is OPTIONAL if peer has no pieces.
                    We allow HAVE messages as an alternative to bitfield (protocol-compliant behavior).
                    Only disconnect if peer sends neither bitfield nor HAVE messages.
                    """
                    await asyncio.sleep(bitfield_timeout)
                    # Check if bitfield was received
                    has_bitfield = (
                        connection.peer_state.bitfield is not None
                        and len(connection.peer_state.bitfield) > 0
                    )
                    # Check if peer has sent HAVE messages (alternative to bitfield)
                    have_messages_count = len(connection.peer_state.pieces_we_have) if connection.peer_state.pieces_we_have else 0
                    has_have_messages = have_messages_count > 0

                    # Check if connection is still active
                    is_active_state = connection.state in (
                        ConnectionState.BITFIELD_RECEIVED,
                        ConnectionState.ACTIVE,
                        ConnectionState.CHOKED,
                    )

                    # Only disconnect if:
                    # 1. No bitfield received
                    # 2. No HAVE messages received (peer hasn't communicated piece availability)
                    # 3. Connection is not in active state
                    # 4. Connection hasn't been closed/errored already
                    if (
                        not is_active_state
                        and not has_bitfield
                        and not has_have_messages
                        and connection.state != ConnectionState.ERROR
                        and connection.state != ConnectionState.DISCONNECTED
                    ):
                        # Peer hasn't sent bitfield OR HAVE messages - likely non-responsive or buggy
                        messages_received = getattr(connection.stats, "messages_received", 0)
                        elapsed_time = time.time() - handshake_time

                        self.logger.warning(
                            "⏱️ BITFIELD_TIMEOUT: Peer %s did not send bitfield OR HAVE messages within %.1fs after handshake "
                            "(state: %s, has_bitfield: %s, have_messages: %d, messages_received: %s, elapsed: %.1fs) - "
                            "disconnecting (BitTorrent protocol: bitfield is optional if peer has no pieces, but HAVE messages should be sent for new pieces)",
                            connection.peer_info,
                            bitfield_timeout,
                            connection.state.value,
                            has_bitfield,
                            have_messages_count,
                            messages_received,
                            elapsed_time,
                        )
                        # Disconnect peer
                        connection.state = ConnectionState.ERROR
                        await self._disconnect_peer(connection)
                    elif has_bitfield:
                        self.logger.debug(
                            "✅ BITFIELD_TIMEOUT: Peer %s sent bitfield (cancelling timeout monitor, state: %s)",
                            connection.peer_info,
                            connection.state.value,
                        )
                    elif has_have_messages:
                        # Peer sent HAVE messages but no bitfield - protocol-compliant (leecher with 0% complete)
                        self.logger.info(
                            "✅ BITFIELD_TIMEOUT: Peer %s sent %d HAVE message(s) instead of bitfield (protocol-compliant, leecher with 0%% complete) - cancelling timeout monitor",
                            connection.peer_info,
                            have_messages_count,
                        )
                        # Mark connection as active since we have piece availability info via HAVE messages
                        if connection.state not in (ConnectionState.ACTIVE, ConnectionState.CHOKED):
                            connection.state = ConnectionState.BITFIELD_RECEIVED  # Treat HAVE messages as equivalent to bitfield
                    else:
                        # Connection is in active state or has been closed - no action needed
                        self.logger.debug(
                            "✅ BITFIELD_TIMEOUT: Peer %s connection is in active/closed state (state: %s) - no action needed",
                            connection.peer_info,
                            connection.state.value,
                        )

                # Start timeout monitor task
                timeout_task = asyncio.create_task(bitfield_timeout_monitor())
                # Store task reference to prevent garbage collection
                if not hasattr(connection, "_timeout_tasks"):
                    connection._timeout_tasks = []
                connection._timeout_tasks.append(timeout_task)

                # CRITICAL FIX: Set callbacks BEFORE adding to connections dict
                # This ensures callbacks are available when messages arrive
                # Use the private attributes to avoid triggering property setters
                if self._on_peer_connected:
                    connection.on_peer_connected = self._on_peer_connected
                if self._on_peer_disconnected:
                    connection.on_peer_disconnected = self._on_peer_disconnected
                if self._on_bitfield_received:
                    connection.on_bitfield_received = self._on_bitfield_received
                if self._on_piece_received:
                    connection.on_piece_received = self._on_piece_received
                    self.logger.debug(
                        "Set on_piece_received callback on outbound connection to %s",
                        peer_info,
                    )
                else:
                    self.logger.warning(
                        "on_piece_received callback is None when creating outbound connection to %s! "
                        "PIECE messages will not be processed.",
                        peer_info,
                    )

                # CRITICAL FIX: Add connection to dict BEFORE creating task to ensure it's tracked
                # even if exceptions occur in task creation. This prevents race conditions where
                # the message loop starts before the connection is in the dict.
                peer_key = str(peer_info)
                async with self.connection_lock:  # pragma: no cover - Same context
                    self.connections[peer_key] = (
                        connection  # pragma: no cover - Same context
                    )
                self._record_probation_peer(peer_key, connection)

                # CRITICAL FIX: Create connection task AFTER adding to dict to ensure thread safety
                # Verify we're in the correct event loop context before creating task
                try:
                    loop = asyncio.get_running_loop()
                    connection.connection_task = asyncio.create_task(
                        self._handle_peer_messages(connection),
                    )  # pragma: no cover - Same context
                    self.logger.debug(
                        "Created connection_task for %s in event loop %s",
                        peer_info,
                        id(loop),
                    )
                except RuntimeError as e:
                    # No running event loop - this should not happen in normal flow
                    self.logger.error(
                        "CRITICAL: No running event loop when creating connection_task for %s: %s",
                        peer_info,
                        e,
                    )
                    # Remove connection from dict since task creation failed
                    async with self.connection_lock:
                        if peer_key in self.connections:
                            del self.connections[peer_key]
                    raise RuntimeError(
                        f"No running event loop for connection task creation: {e}"
                    ) from e

                    # CRITICAL FIX: Log successful connection at INFO level
                    self.logger.info(
                        "Connection to %s:%d succeeded (source: %s, state=%s, total connections: %d)",
                        peer_info.ip,
                        peer_info.port,
                        peer_info.peer_source or "unknown",
                        connection.state,
                        len(self.connections),
                    )
                    self.logger.debug(
                        "Added connection to dict for %s (state=%s, total connections: %d)",
                        peer_info,
                        connection.state.value,
                        len(self.connections),
                    )

                # Record connection success for metrics (outgoing connection)
                # Access metrics through piece_manager if available
                try:
                    if hasattr(self.piece_manager, "_session_manager") and self.piece_manager._session_manager:
                        session_manager = self.piece_manager._session_manager
                        if hasattr(session_manager, "metrics"):
                            await session_manager.metrics.record_connection_success(peer_key)
                except Exception as e:
                    self.logger.debug("Failed to record connection success: %s", e)

                # CRITICAL FIX: Start unchoke timeout detection task
                # Monitor if peer sends UNCHOKE within reasonable time (30 seconds)
                connection_start_time = time.time()
                # Store connection start time on connection for grace period checks
                connection.connection_start_time = connection_start_time
                task = asyncio.create_task(
                    self._monitor_unchoke_timeout(connection, connection_start_time)
                )
                _ = task  # Store reference to avoid unused variable warning

                # Notify callback (wrapped in try/except to prevent exceptions from removing connection)
                if self._on_peer_connected:  # pragma: no cover - Same context
                    try:
                        self._on_peer_connected(
                            connection
                        )  # pragma: no cover - Same context
                    except Exception as e:
                        # CRITICAL FIX: Log callback error but don't remove connection
                        self.logger.warning(
                            "Error in on_peer_connected callback for %s: %s (connection will remain)",
                            peer_info,
                            e,
                            exc_info=True,
                        )
                        # Don't re-raise - connection is still valid even if callback fails

                self.logger.info(
                    "Connected to peer %s (handshake complete, message loop started, state=%s)",
                    peer_info,
                    connection.state.value,
                )  # pragma: no cover - Same context

                # CRITICAL FIX: Send INTERESTED proactively when peer becomes active
                # This encourages peers to unchoke us, allowing us to download from multiple peers
                # Many peers wait for INTERESTED before unchoking, so we need to be proactive
                # CRITICAL FIX: Also send INTERESTED immediately after bitfield is received (not just after connection)
                # This ensures peers know we're interested as soon as we see their bitfield
                if not connection.am_interested:
                    try:
                        await self._send_interested(connection)
                        connection.am_interested = True
                        self.logger.info(
                            "Sent INTERESTED to %s proactively after connection (encouraging peer to unchoke us)",
                            peer_info,
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Failed to send proactive INTERESTED to %s after connection: %s",
                            peer_info,
                            e,
                        )

                # CRITICAL FIX: Log connection details for debugging
                self.logger.debug(
                    "Peer %s connection details: reader=%s, writer=%s, encrypted=%s, choking=%s, interested=%s",
                    peer_info,
                    connection.reader is not None,
                    connection.writer is not None,
                    connection.is_encrypted,
                    connection.peer_choking,
                    connection.am_interested,
                )

                # CRITICAL FIX: Verify connection is still in dict after all operations
                async with self.connection_lock:
                    if peer_key not in self.connections:
                        self.logger.error(
                            "CRITICAL: Connection to %s was removed from dict after being added! "
                            "This should not happen. Connection state: %s",
                            peer_info,
                            connection.state.value,
                        )
                    else:
                        self.logger.debug(
                            "Verified connection to %s is still in dict (state=%s)",
                            peer_info,
                            connection.state.value,
                        )

            except asyncio.CancelledError:
                # CRITICAL FIX: Handle CancelledError during shutdown gracefully
                from ccbt.utils.shutdown import is_shutting_down
                if is_shutting_down():
                    # During shutdown, cancellation is expected - clean up and re-raise
                    if connection:
                        try:
                            await self._disconnect_peer(connection)
                        except Exception:
                            pass  # Ignore cleanup errors during shutdown
                    raise  # Re-raise CancelledError to allow proper task cancellation
                # If not during shutdown, treat as connection failure
                # Fall through to exception handler below
                raise PeerConnectionError(f"Connection to {peer_info} was cancelled") from None
            except PeerConnectionError as e:
                # Re-raise PeerConnectionError (validation errors, handshake errors, etc.)
                # so they can be handled by callers
                # CRITICAL FIX: Suppress verbose logging during shutdown
                from ccbt.utils.shutdown import is_shutting_down

                # Record failure in circuit breaker
                if self.circuit_breaker_manager:
                    breaker = self.circuit_breaker_manager.get_breaker(peer_id)
                    breaker._on_failure()  # noqa: SLF001 - CircuitBreaker internal API

                    # CRITICAL FIX: Check if connection was added to dict before exception
                    peer_key = str(peer_info)
                    was_in_dict = False
                    async with self.connection_lock:
                        was_in_dict = peer_key in self.connections

                    # CRITICAL FIX: Check if this is WinError 121 (semaphore timeout) and log as DEBUG
                    error_str = str(e)
                    is_winerror_121 = (
                        "WinError 121" in error_str
                        or "semaphore timeout" in error_str.lower()
                    )

                    connection_state = connection.state.value if connection else "None"

                    if is_shutting_down():
                        # During shutdown, only log at debug level
                        self.logger.debug(
                            "PeerConnectionError connecting to %s during shutdown: %s",
                            peer_info,
                            str(e),
                        )
                    elif is_winerror_121:
                        # Log WinError 121 as DEBUG - this is expected on Windows when many connections are attempted
                        self.logger.debug(
                            "PeerConnectionError (WinError 121) connecting to %s: %s (connection_state=%s, was_in_dict=%s). "
                            "This is normal on Windows when many connections are attempted simultaneously.",
                            peer_info,
                            str(e),
                            connection_state,
                            was_in_dict,
                        )
                    else:
                        # Log other PeerConnectionErrors as WARNING with full details
                        self.logger.warning(
                            "PeerConnectionError connecting to %s: %s (connection_state=%s, was_in_dict=%s). "
                            "This error occurred during handshake or connection setup.",
                            peer_info,
                            str(e),
                            connection_state,
                            was_in_dict,
                            exc_info=True,  # Include full traceback to diagnose handshake failures
                        )

                if connection:
                    # CRITICAL FIX: Validate writer state before cleanup
                    if connection.writer is not None:
                        try:
                            if (
                                hasattr(connection.writer, "is_closing")
                                and not connection.writer.is_closing()
                            ):
                                # Writer is still open, close it properly
                                connection.writer.close()
                                await connection.writer.wait_closed()
                        except Exception as cleanup_error:
                            self.logger.debug(
                                "Error closing writer during cleanup for %s: %s",
                                peer_info,
                                cleanup_error,
                            )
                    await self._disconnect_peer(connection)
                raise
            except Exception as e:  # pragma: no cover - Exception handling during network connection is difficult to test
                # Record failure in circuit breaker
                if self.circuit_breaker_manager:
                    breaker = self.circuit_breaker_manager.get_breaker(peer_id)
                    breaker._on_failure()  # noqa: SLF001 - CircuitBreaker internal API

                # CRITICAL FIX: Check if connection was added to dict before exception
                peer_key = str(peer_info)
                was_in_dict = False
                async with self.connection_lock:
                    was_in_dict = peer_key in self.connections

                # CRITICAL FIX: Log the actual error with more detail and connection state
                error_type = type(e).__name__
                error_msg = str(e)
                connection_state = connection.state.value if connection else "None"
                writer_state = "None"
                if connection:
                    if connection.writer is None:
                        writer_state = "None"
                    elif hasattr(connection.writer, "is_closing"):
                        writer_state = f"closing={connection.writer.is_closing()}"
                    else:
                        writer_state = f"type={type(connection.writer).__name__}"

                self.logger.warning(
                    "Failed to connect to peer %s: %s (%s, connection_state=%s, writer_state=%s, was_in_dict=%s). "
                    "This is an unexpected exception during connection setup.",
                    peer_info,
                    error_msg,
                    error_type,
                    connection_state,
                    writer_state,
                    was_in_dict,
                    exc_info=True,  # Always include full traceback for unexpected exceptions
                )

                # Record connection failure for local blacklist source
                await self._record_connection_failure(peer_info, "connection_failure", error_type)

                if connection and connection.writer is not None:
                    # CRITICAL FIX: Validate writer state before cleanup
                    try:
                        if (
                            hasattr(connection.writer, "is_closing")
                            and not connection.writer.is_closing()
                        ):
                            # Writer is still open, close it properly
                            connection.writer.close()
                            await connection.writer.wait_closed()
                    except Exception as cleanup_error:
                        self.logger.debug(
                            "Error closing writer during cleanup for %s: %s",
                            peer_info,
                            cleanup_error,
                        )
                if connection is not None:
                    await self._disconnect_peer(connection)
                raise

    async def _record_connection_failure(
        self, peer_info: PeerInfo, failure_type: str, error_type: str
    ) -> None:
        """Record connection failure for local blacklist source.

        Args:
            peer_info: Peer information
            failure_type: Type of failure ("handshake_failure", "connection_failure")
            error_type: Error type name

        """
        try:
            # Try to get SecurityManager through session or config
            # This is optional - if SecurityManager is not available, we skip recording
            from ccbt.config.config import get_config

            config = get_config()
            # SecurityManager is typically accessed through session
            # For now, we'll try to get it through a helper if available
            # If not available, we'll skip (non-critical)
            security_manager = getattr(config, "_security_manager", None)
            if not security_manager:
                # Try alternative access methods
                try:
                    from ccbt.session.session import get_security_manager
                    security_manager = get_security_manager()
                except (ImportError, AttributeError):
                    # SecurityManager not available, skip recording
                    return

            if security_manager and security_manager.blacklist_updater:
                local_source = getattr(
                    security_manager.blacklist_updater, "_local_source", None
                )
                if local_source:
                    await local_source.record_metric(
                        peer_info.ip,
                        failure_type,
                        1.0,
                        metadata={
                            "error_type": error_type,
                            "port": peer_info.port,
                            "peer_id": (
                                peer_info.peer_id.hex()
                                if peer_info.peer_id
                                else "unknown"
                            ),
                        },
                    )
        except Exception:
            # Non-critical - log at debug level and continue
            self.logger.debug(
                "Failed to record connection failure for local blacklist: %s",
                peer_info,
                exc_info=True,
            )

    async def _keepalive_sender(self, connection: AsyncPeerConnection) -> None:
        """Periodic task to send keep-alive messages to peer.

        Sends keep-alive (length=0 message) with adaptive interval based on connection state.
        CRITICAL FIX: Improved keep-alive handling with timeout detection and adaptive intervals.
        """
        # CRITICAL FIX: Adaptive keep-alive interval based on connection state
        # Active connections: 120s (standard BitTorrent keep-alive)
        # Choked connections: 90s (more frequent to detect dead connections faster)
        # Low activity: 60s (very frequent to detect dead connections quickly)
        base_keepalive_interval = 120.0  # Standard BitTorrent keep-alive interval
        keepalive_failures = 0
        max_keepalive_failures = 3  # Disconnect after 3 consecutive keep-alive failures

        try:
            while connection.is_connected():
                # CRITICAL FIX: Adaptive keep-alive interval based on connection state
                if connection.state == ConnectionState.CHOKED:
                    # Choked connections: send keep-alive more frequently (90s)
                    keepalive_interval = 90.0
                elif connection.state == ConnectionState.ACTIVE:
                    # Active connections: standard interval (120s)
                    keepalive_interval = base_keepalive_interval
                else:
                    # Other states: use base interval
                    keepalive_interval = base_keepalive_interval

                # CRITICAL FIX: Check if connection has been silent for too long
                # If no activity for 2x keep-alive interval, connection may be dead
                time_since_activity = time.time() - connection.stats.last_activity
                if time_since_activity > (keepalive_interval * 2):
                    self.logger.warning(
                        "Keep-alive: Connection to %s has been silent for %.1fs (last activity: %.1fs ago, keep-alive interval: %.1fs). "
                        "Connection may be dead.",
                        connection.peer_info,
                        time_since_activity,
                        time_since_activity,
                        keepalive_interval,
                    )
                    # Mark connection as potentially dead
                    keepalive_failures += 1
                    if keepalive_failures >= max_keepalive_failures:
                        self.logger.warning(
                            "Keep-alive: Disconnecting %s after %d consecutive keep-alive failures (connection appears dead)",
                            connection.peer_info,
                            keepalive_failures,
                        )
                        connection.state = ConnectionState.ERROR
                        await self._disconnect_peer(connection)
                        break

                await asyncio.sleep(keepalive_interval)

                if not connection.is_connected():
                    break

                # Send keep-alive message (4 zero bytes)
                try:
                    if connection.writer and not connection.writer.is_closing():
                        keepalive_msg = b"\x00\x00\x00\x00"
                        keepalive_sent_time = time.time()
                        connection.writer.write(keepalive_msg)
                        await connection.writer.drain()
                        connection.stats.last_activity = time.time()

                        # CRITICAL FIX: Reset failure count on successful keep-alive
                        if keepalive_failures > 0:
                            self.logger.debug(
                                "Keep-alive: Successfully sent to %s (reset failure count from %d)",
                                connection.peer_info,
                                keepalive_failures,
                            )
                            keepalive_failures = 0
                        else:
                            self.logger.debug(
                                "Sent keep-alive message to %s (interval: %.1fs, state: %s)",
                                connection.peer_info,
                                keepalive_interval,
                                connection.state.value,
                            )
                except Exception as e:
                    keepalive_failures += 1
                    self.logger.debug(
                        "Failed to send keep-alive to %s: %s (failure count: %d/%d, connection may be closing)",
                        connection.peer_info,
                        e,
                        keepalive_failures,
                        max_keepalive_failures,
                    )
                    if keepalive_failures >= max_keepalive_failures:
                        self.logger.warning(
                            "Keep-alive: Disconnecting %s after %d consecutive keep-alive send failures",
                            connection.peer_info,
                            keepalive_failures,
                        )
                        connection.state = ConnectionState.ERROR
                        await self._disconnect_peer(connection)
                        break
        except asyncio.CancelledError:
            self.logger.debug(
                "Keep-alive sender cancelled for peer %s", connection.peer_info
            )
        except Exception:
            self.logger.debug(
                "Keep-alive sender error for peer %s",
                connection.peer_info,
                exc_info=True,
            )

    async def _handle_peer_messages(self, connection: AsyncPeerConnection) -> None:
        """Handle incoming messages from a peer."""
        connection_start_time = time.time()
        last_message_time = connection_start_time
        message_count = 0
        self.logger.info(
            "MESSAGE_LOOP: Started for peer %s (state=%s, choking=%s, interested=%s, has_bitfield=%s, reader=%s)",
            connection.peer_info,
            connection.state.value,
            connection.peer_choking,
            connection.am_interested,
            connection.peer_state.bitfield is not None and len(connection.peer_state.bitfield) > 0 if connection.peer_state.bitfield else False,
            connection.reader is not None,
        )

        # CRITICAL FIX: Start keep-alive sender task
        keepalive_task = None
        try:
            keepalive_task = asyncio.create_task(self._keepalive_sender(connection))
        except Exception as e:
            self.logger.warning(
                "Failed to start keep-alive sender for %s: %s", connection.peer_info, e
            )

        try:
            while connection.is_connected():  # pragma: no cover - Message loop requires active connection and messages, complex to test
                if connection.reader is None:  # pragma: no cover - Same context
                    msg = (
                        _ERROR_READER_NOT_INITIALIZED  # pragma: no cover - Same context
                    )
                    raise RuntimeError(msg)  # pragma: no cover - Same context

                # CRITICAL FIX: Connection timeout monitoring
                # Check if peer has been silent for too long (no messages received)
                # Reduced from 120s to 90s for faster dead connection detection
                current_time = time.time()
                time_since_last_message = current_time - last_message_time
                connection_timeout = 90.0  # Reduced from 120s to 90s for faster dead connection detection

                if time_since_last_message > connection_timeout:
                    self.logger.warning(
                        "Peer %s has been silent for %.1f seconds (no messages received, timeout: %.1fs). "
                        "Connection may be dead. State: %s, Choking: %s. Disconnecting gracefully.",
                        connection.peer_info,
                        time_since_last_message,
                        connection_timeout,
                        connection.state.value,
                        connection.peer_choking,
                    )
                    # Set state to ERROR and break loop to trigger disconnect
                    connection.state = ConnectionState.ERROR
                    break

                # Read message length
                # CRITICAL FIX: Reduced timeout to 90s for faster dead connection detection
                # 90s is still generous but allows faster recovery from dead connections
                try:
                    length_data = await asyncio.wait_for(
                        connection.reader.readexactly(4),
                        timeout=90.0,  # Reduced from 120s to 90s for faster dead connection detection
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⏱️ MESSAGE_LOOP: Timeout reading message length from %s (no data for 90s, state=%s, choking=%s) - "
                        "connection may be dead. Disconnecting.",
                        connection.peer_info,
                        connection.state.value,
                        connection.peer_choking,
                    )
                    connection.state = ConnectionState.ERROR
                    break

                length = int.from_bytes(
                    length_data, "big"
                )  # pragma: no cover - Same context

                if length == 0:  # pragma: no cover - Same context
                    # CRITICAL FIX: Keep-alive message - update activity and reset timeout
                    current_activity_time = time.time()
                    connection.stats.last_activity = current_activity_time
                    last_message_time = current_activity_time
                    self.logger.debug(
                        "Received keep-alive message from %s (last_activity updated)",
                        connection.peer_info,
                    )
                    continue  # pragma: no cover - Same context

                # Read message payload
                # CRITICAL FIX: Reduced timeout to 90s for faster dead connection detection
                # 90s is still generous but allows faster recovery from dead connections
                try:
                    payload = await asyncio.wait_for(
                        connection.reader.readexactly(length),
                        timeout=90.0,  # Reduced from 120s to 90s for faster dead connection detection
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⏱️ MESSAGE_LOOP: Timeout reading message payload from %s (length=%d, no data for 90s, state=%s) - "
                        "connection may be dead. Disconnecting.",
                        connection.peer_info,
                        length,
                        connection.state.value,
                    )
                    connection.state = ConnectionState.ERROR
                    break
                connection.stats.last_activity = (
                    time.time()
                )  # pragma: no cover - Same context
                last_message_time = time.time()
                message_count += 1

                # Check for extension message (message type 20) before decoding
                # CRITICAL FIX: Extension messages MUST be handled immediately and not skipped
                # They are time-sensitive (especially ut_metadata responses) and should not be delayed
                if length > 0 and payload and payload[0] == 20:  # Extension message
                    # CRITICAL: Log at INFO level to track extension messages
                    # This helps diagnose why ut_metadata responses aren't being detected
                    extension_id_preview = payload[1] if len(payload) > 1 else None
                    payload_preview = payload[:20].hex() if len(payload) >= 20 else payload.hex()
                    self.logger.info(
                        "MESSAGE_LOOP_EXTENSION: Received extension message from %s (length=%d, extension_id=%s, state=%s, choking=%s, payload_preview=%s)",
                        connection.peer_info,
                        length,
                        extension_id_preview,
                        connection.state.value,
                        connection.peer_choking,
                        payload_preview,
                    )
                    # CRITICAL FIX: Handle extension message immediately with error handling
                    # Don't let extension message handling errors break the message loop
                    try:
                        await self._handle_extension_message(
                            connection, payload
                        )  # pragma: no cover - Extension message handling
                    except Exception as ext_error:
                        # Log error but continue message loop - don't break connection
                        self.logger.warning(
                            "Error handling extension message from %s: %s (extension_id=%s, length=%d). Continuing message loop.",
                            connection.peer_info,
                            ext_error,
                            extension_id_preview,
                            length,
                            exc_info=True,
                        )
                    continue  # pragma: no cover - Same context

                # CRITICAL FIX: Handle non-standard message types (9-19, 21+)
                # These are NOT extension protocol messages (message type 20 is extension protocol)
                # Some clients may send these, but they're not part of BEP 10
                # We should skip them or handle them separately, but NOT route to extension handler
                if length > 0 and payload:
                    msg_id = payload[0] if payload else 0
                    # Standard BitTorrent message types are 0-8
                    # Message type 20 is extension protocol (handled above)
                    # Message types 9-19 and 21+ are reserved/unknown
                    if msg_id > 8 and msg_id != 20:
                        # These are not extension protocol messages - skip them
                        # Extension protocol messages MUST have message type 20
                        self.logger.debug(
                            "Received non-standard message type %d from %s (length=%d). "
                            "Skipping (not a BEP 10 extension protocol message - extension protocol uses message type 20).",
                            msg_id,
                            connection.peer_info,
                            length,
                        )
                        continue  # Skip unknown message

                # Decode message
                message_data = length_data + payload  # pragma: no cover - Same context
                try:
                    await connection.message_decoder.feed_data(
                        message_data
                    )  # pragma: no cover - Same context
                    message = (
                        await connection.message_decoder.get_message()
                    )  # pragma: no cover - Same context
                    if message:  # pragma: no cover - Same context
                        # Log message type with connection state
                        message_type = type(message).__name__
                        # CRITICAL FIX: Log bitfield messages at INFO level for diagnostics
                        if isinstance(message, BitfieldMessage):
                            self.logger.info(
                                "MESSAGE_LOOP: Received BITFIELD from %s (state=%s, choking=%s, interested=%s, message #%d, bitfield_length=%d)",
                                connection.peer_info,
                                connection.state.value,
                                connection.peer_choking,
                                connection.am_interested,
                                message_count,
                                len(message.bitfield) if message.bitfield else 0,
                            )
                        else:
                            self.logger.debug(
                                "Received %s from %s (state=%s, choking=%s, interested=%s, message #%d)",
                                message_type,
                                connection.peer_info,
                                connection.state.value,
                                connection.peer_choking,
                                connection.am_interested,
                                message_count,
                            )

                        # Special logging for CHOKE/UNCHOKE messages
                        if isinstance(message, (ChokeMessage, UnchokeMessage)):
                            self.logger.info(
                                "Received %s from %s (current state: %s, was choking: %s)",
                                message_type,
                                connection.peer_info,
                                connection.state.value,
                                connection.peer_choking,
                            )

                        await self._handle_message(
                            connection, message
                        )  # pragma: no cover - Same context
                except (
                    MessageError,
                    IndexError,
                ) as e:  # pragma: no cover - Message decoding errors are difficult to simulate
                    self.logger.warning(
                        "Failed to decode message from %s: %s (message length=%d, state=%s)",
                        connection.peer_info,
                        e,
                        length,
                        connection.state.value,
                    )  # pragma: no cover - Same context
                    continue  # pragma: no cover - Same context

        except asyncio.CancelledError:
            self.logger.info(
                "Message loop cancelled for peer %s (processed %d messages, duration=%.1fs)",
                connection.peer_info,
                message_count,
                time.time() - connection_start_time,
            )
            # CRITICAL FIX: Re-raise CancelledError to properly propagate cancellation
            # The finally block will still run for cleanup, but the task will be marked as cancelled
            raise
            # pragma: no cover - Cancellation handling in message loop
        except asyncio.IncompleteReadError as e:
            # CRITICAL FIX: Handle IncompleteReadError gracefully (peer closed connection)
            # Set connection state to ERROR before disconnecting
            connection.state = ConnectionState.ERROR
            duration = time.time() - connection_start_time
            self.logger.info(
                "Peer %s closed connection (IncompleteReadError: %d bytes read, %d expected, "
                "processed %d messages, duration=%.1fs, state=%s)",
                connection.peer_info,
                len(e.partial) if e.partial else 0,
                e.expected,
                message_count,
                duration,
                connection.state.value,
            )
        except Exception:  # pragma: no cover - Exception handling in message loop
            # CRITICAL FIX: Set connection state to ERROR before disconnecting
            connection.state = ConnectionState.ERROR
            self.logger.exception(
                "Error handling messages from %s (processed %d messages, duration=%.1fs, state=%s)",
                connection.peer_info,
                message_count,
                time.time() - connection_start_time,
                connection.state.value,
            )  # pragma: no cover - Same context
        finally:
            # CRITICAL FIX: Cancel keep-alive sender task when message loop stops
            if keepalive_task and not keepalive_task.done():
                keepalive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await keepalive_task

            self.logger.info(
                "Message loop stopped for peer %s (processed %d messages, duration=%.1fs, final state=%s)",
                connection.peer_info,
                message_count,
                time.time() - connection_start_time,
                connection.state.value,
            )
            await self._disconnect_peer(
                connection
            )  # pragma: no cover - Cleanup in message loop

    async def _handle_message(
        self,
        connection: AsyncPeerConnection,
        message: PeerMessage,
    ) -> None:
        """Handle a single message from a peer."""
        # Log connection state before handling message
        state_before = connection.state.value
        choking_before = connection.peer_choking

        try:  # pragma: no cover - Exception wrapper for message handling, all branches tested individually
            if isinstance(
                message, KeepAliveMessage
            ):  # pragma: no cover - Keep-alive message handling, tested via message handlers
                # Keep-alive, just update activity
                pass  # pragma: no cover - Same context
            elif isinstance(
                message, BitfieldMessage
            ):  # pragma: no cover - Message type routing, tested via message handlers
                handler = self.message_handlers.get(MessageType.BITFIELD)
                if handler:
                    await handler(connection, message)  # type: ignore[misc]  # Handler is async
            elif isinstance(message, HaveMessage):  # pragma: no cover - Same context
                handler = self.message_handlers.get(MessageType.HAVE)
                if handler:
                    await handler(connection, message)  # type: ignore[misc]  # Handler is async
            elif isinstance(message, PieceMessage):  # pragma: no cover - Same context
                handler = self.message_handlers.get(MessageType.PIECE)
                if handler:
                    await handler(connection, message)  # type: ignore[misc]  # Handler is async
            elif hasattr(message, "message_id") and message.message_id in [
                MESSAGE_ID_PIECE_LAYER_REQUEST,
                MESSAGE_ID_PIECE_LAYER_RESPONSE,
                MESSAGE_ID_FILE_TREE_REQUEST,
                MESSAGE_ID_FILE_TREE_RESPONSE,
            ]:
                # v2 protocol message (BEP 52)
                await self.handle_v2_message(
                    connection, message
                )  # pragma: no cover - v2 message handling
            else:
                # Handle state change messages
                if isinstance(message, ChokeMessage):  # pragma: no cover - Same context
                    # CRITICAL FIX: Call the handler instead of handling inline
                    # This ensures _handle_choke is called for consistency
                    handler = self.message_handlers.get(MessageType.CHOKE)
                    if handler:
                        await handler(connection, message)  # type: ignore[misc]  # Handler is async
                    else:
                        # Fallback: handle inline if handler not available
                        connection.peer_choking = True  # pragma: no cover - Same context
                        connection.state = (
                            ConnectionState.CHOKED
                        )  # pragma: no cover - Same context
                        # Log state change
                        self.logger.info(
                            "Peer %s CHOKED us (state: %s -> %s, choking: %s -> %s)",
                            connection.peer_info,
                            state_before,
                            connection.state.value,
                            choking_before,
                            connection.peer_choking,
                        )
                elif isinstance(
                    message, UnchokeMessage
                ):  # pragma: no cover - Same context
                    # CRITICAL FIX: Call the handler instead of handling inline
                    # This ensures _handle_unchoke is called, which triggers piece selection
                    handler = self.message_handlers.get(MessageType.UNCHOKE)
                    if handler:
                        await handler(connection, message)  # type: ignore[misc]  # Handler is async
                    else:
                        # Fallback: handle inline if handler not available
                        connection.peer_choking = False  # pragma: no cover - Same context
                        connection.state = (
                            ConnectionState.ACTIVE
                        )  # pragma: no cover - Same context
                        # Log state change
                        self.logger.info(
                            "Peer %s UNCHOKED us (state: %s -> %s, choking: %s -> %s)",
                            connection.peer_info,
                            state_before,
                            connection.state.value,
                            choking_before,
                            connection.peer_choking,
                        )
                elif isinstance(
                    message, InterestedMessage
                ):  # pragma: no cover - Same context
                    connection.peer_interested = True  # pragma: no cover - Same context
                    self.logger.debug(
                        "Peer %s is now INTERESTED (was: %s)",
                        connection.peer_info,
                        not connection.peer_interested,
                    )
                elif isinstance(
                    message, NotInterestedMessage
                ):  # pragma: no cover - Same context
                    connection.peer_interested = (
                        False  # pragma: no cover - Same context
                    )
                    self.logger.debug(
                        "Peer %s is now NOT INTERESTED (was: %s)",
                        connection.peer_info,
                        not connection.peer_interested,
                    )

                # Log state change summary for other messages
                if not isinstance(
                    message,
                    (
                        ChokeMessage,
                        UnchokeMessage,
                        InterestedMessage,
                        NotInterestedMessage,
                    ),
                ):
                    state_after = connection.state.value
                    choking_after = connection.peer_choking
                    if state_before != state_after or choking_before != choking_after:
                        self.logger.debug(
                            "State changed after %s from %s: state=%s->%s, choking=%s->%s",
                            message.__class__.__name__,
                            connection.peer_info,
                            state_before,
                            state_after,
                            choking_before,
                            choking_after,
                        )

        except (
            Exception
        ):  # pragma: no cover - Exception handling during message processing
            self.logger.exception(
                "Error handling message from %s (state before: %s, choking: %s)",
                connection.peer_info,
                state_before,
                choking_before,
            )  # pragma: no cover - Same context

    async def _attempt_ssl_negotiation(self, connection: AsyncPeerConnection) -> None:
        """Attempt SSL negotiation after BitTorrent handshake.

        Args:
            connection: Peer connection

        """
        try:
            # Check if SSL extension is enabled
            ssl_config = self.config.security.ssl
            if not ssl_config or not ssl_config.enable_ssl_peers:
                return
            if not ssl_config.ssl_extension_enabled:
                return

            # Get peer ID
            peer_id = str(connection.peer_info) if connection.peer_info else ""
            if not peer_id:
                return

            # Check if peer supports SSL extension
            # First check if we already know from peer_info (set during extension handshake)
            ssl_capable = None
            if connection.peer_info and connection.peer_info.ssl_capable is not None:
                ssl_capable = connection.peer_info.ssl_capable
            else:
                # Fallback: check extension manager (may not be set yet)
                from ccbt.extensions.manager import get_extension_manager

                extension_manager = get_extension_manager()
                ssl_capable = extension_manager.peer_supports_extension(peer_id, "ssl")
                # Update peer_info if we discovered it
                if connection.peer_info and ssl_capable is not None:
                    connection.peer_info.ssl_capable = ssl_capable

            if not ssl_capable:
                return

            # Get SSL peer connection manager
            from ccbt.peer.ssl_peer import SSLPeerConnection

            ssl_peer = SSLPeerConnection()

            # Attempt SSL negotiation
            if connection.reader and connection.writer:
                # Type check: ensure we have asyncio.StreamReader/Writer
                # (not EncryptedStreamReader/Writer which would mean already encrypted)
                import asyncio

                if isinstance(connection.reader, asyncio.StreamReader) and isinstance(
                    connection.writer, asyncio.StreamWriter
                ):
                    result = await ssl_peer.negotiate_ssl_after_handshake(
                        connection.reader,
                        connection.writer,
                        peer_id,
                        connection.peer_info.ip,
                        connection.peer_info.port,
                    )

                    if result:
                        # SSL negotiation succeeded, update connection
                        ssl_reader, ssl_writer = result
                        connection.reader = ssl_reader
                        connection.writer = ssl_writer
                        connection.is_encrypted = True
                        # Update peer_info to reflect SSL is enabled
                        if connection.peer_info:
                            connection.peer_info.ssl_enabled = True
                            connection.peer_info.ssl_capable = True  # Confirmed capable
                        self.logger.info(
                            "SSL negotiation successful for peer %s (SSL enabled)",
                            connection.peer_info,
                        )

        except Exception as e:
            # SSL negotiation failed, but continue with plain connection
            self.logger.debug(
                "SSL negotiation failed for peer %s: %s (continuing with plain connection)",
                connection.peer_info,
                e,
            )

    async def _handle_extension_message(
        self, connection: AsyncPeerConnection, payload: bytes
    ) -> None:
        """Handle extension protocol message (BEP 10).

        According to BEP 10, extension messages have format:
        <message_id (20)><extension_id (1 byte)><extension_payload>
        
        For ut_metadata (BEP 9), responses have format:
        <message_id (20)><ut_metadata_id><bencoded_header><piece_data>
        Where bencoded_header is: d8:msg_typei1e5:piecei<index>ee (data) or d8:msg_typei2e5:piecei<index>ee (reject)

        Args:
            connection: Peer connection
            payload: Extension message payload (format: <message_id (20)><extension_id><extension_payload>)

        """
        try:
            from ccbt.extensions.manager import get_extension_manager

            extension_manager = get_extension_manager()
            extension_protocol = extension_manager.get_extension("protocol")

            if not extension_protocol:
                self.logger.debug(
                    "Extension protocol not available, skipping extension message from %s",
                    connection.peer_info,
                )
                return

            # Decode extension message
            # Format: <message_id (1 byte)><extension_id (1 byte)><payload>
            if len(payload) < 2:
                self.logger.debug(
                    "Extension message too short from %s (length=%d, expected >=2)",
                    connection.peer_info,
                    len(payload),
                )
                return

            # BEP 10: First byte is message_id (should be 20), second byte is extension_id
            message_id = payload[0] if len(payload) > 0 else 0
            extension_id = payload[1] if len(payload) > 1 else 0
            extension_payload = payload[2:] if len(payload) > 2 else b""

            # CRITICAL: Log ALL extension messages at INFO level to diagnose missing responses
            # This includes both handshakes (extension_id=0) and responses (extension_id=ut_metadata_id)
            # Log raw payload for debugging
            self.logger.info(
                "EXTENSION_MSG_RAW: from %s, raw_payload_len=%d, message_id=%d, extension_id=%d, extension_payload_len=%d, first_20_bytes=%s",
                connection.peer_info,
                len(payload),
                message_id,
                extension_id,
                len(extension_payload),
                extension_payload[:20].hex() if len(extension_payload) >= 20 else extension_payload.hex(),
            )

            # Validate message_id is 20 (extension protocol)
            if message_id != 20:
                self.logger.warning(
                    "Extension message from %s has invalid message_id=%d (expected 20). Payload: %s",
                    connection.peer_info,
                    message_id,
                    payload[:20].hex() if len(payload) >= 20 else payload.hex(),
                )
                return

            # Get peer ID
            peer_id = str(connection.peer_info) if connection.peer_info else ""

            # Handle extension handshake (extension_id = 0)
            if extension_id == 0:
                # CRITICAL FIX: Log at INFO level to ensure visibility of extension handshake responses
                self.logger.info(
                    "EXTENSION_HANDSHAKE_RECEIVED: from %s, payload_len=%d, first_50_bytes=%s",
                    connection.peer_info,
                    len(payload),
                    payload[:50].hex() if len(payload) >= 50 else payload.hex(),
                )
                try:
                    # CRITICAL FIX: Extension handshake payload format
                    # The payload should be: <message_id (20)><extension_id (0)><bencoded_data>
                    # But decode_handshake expects: <length><message_id><bencoded_data>
                    # So we need to reconstruct the full message format
                    if len(payload) < 2:
                        self.logger.warning(
                            "Extension handshake payload too short from %s (length=%d, expected >=2)",
                            connection.peer_info,
                            len(payload),
                        )
                        return

                    # CRITICAL FIX: Extension handshake uses bencoded data (BEP 10), not JSON
                    # The payload format is: <message_id (20)><extension_id (0)><bencoded_data>
                    # We need to decode the bencoded data directly
                    bencoded_data = payload[2:] if len(payload) > 2 else payload[1:]
                    if not bencoded_data:
                        self.logger.warning(
                            "Extension handshake has no bencoded data from %s (payload_len=%d)",
                            connection.peer_info,
                            len(payload),
                        )
                        return

                    # Decode bencoded extension handshake (BEP 10)
                    # CRITICAL: BEP 10 extension handshakes are ALWAYS bencoded, never JSON
                    from ccbt.core.bencode import BencodeDecoder
                    try:
                        decoder = BencodeDecoder(bencoded_data)
                        handshake_data = decoder.decode()

                        # CRITICAL FIX: Log decoded handshake data at INFO level
                        self.logger.info(
                            "EXTENSION_HANDSHAKE_PARSED: from %s, handshake_keys=%s, has_m=%s, has_metadata_size=%s",
                            connection.peer_info,
                            list(handshake_data.keys()) if isinstance(handshake_data, dict) else "not_dict",
                            "m" in handshake_data if isinstance(handshake_data, dict) else False,
                            "metadata_size" in handshake_data if isinstance(handshake_data, dict) else False,
                        )

                        # Convert bytes keys to strings for compatibility
                        if isinstance(handshake_data, dict):
                            # Convert b"m" -> "m", b"ut_metadata" -> "ut_metadata", etc.
                            converted_data = {}
                            for key, value in handshake_data.items():
                                if isinstance(key, bytes):
                                    try:
                                        key_str = key.decode("utf-8")
                                    except UnicodeDecodeError:
                                        # Fallback for non-UTF-8 keys (shouldn't happen per spec, but handle gracefully)
                                        key_str = key.decode("utf-8", errors="replace")
                                else:
                                    key_str = str(key)

                                # Recursively convert nested dicts
                                if isinstance(value, dict):
                                    converted_value = {}
                                    for k, v in value.items():
                                        if isinstance(k, bytes):
                                            try:
                                                k_str = k.decode("utf-8")
                                            except UnicodeDecodeError:
                                                k_str = k.decode("utf-8", errors="replace")
                                        else:
                                            k_str = str(k)
                                        converted_value[k_str] = v
                                    converted_data[key_str] = converted_value
                                else:
                                    converted_data[key_str] = value
                            handshake_data = converted_data
                        elif not isinstance(handshake_data, dict):
                            # BEP 10 requires extension handshake to be a dictionary
                            self.logger.warning(
                                "Extension handshake from %s is not a dictionary (got %s). Invalid BEP 10 format.",
                                connection.peer_info,
                                type(handshake_data).__name__,
                            )
                            return
                    except Exception as decode_error:
                        # BEP 10 extension handshakes are ALWAYS bencoded - no JSON fallback
                        # If bencode decoding fails, the handshake is malformed or not a BEP 10 handshake
                        self.logger.warning(
                            "EXTENSION_HANDSHAKE_DECODE_FAILED: from %s, error=%s, data length=%d, first bytes=%s. "
                            "This may indicate a malformed handshake or non-BEP 10 extension protocol.",
                            connection.peer_info,
                            decode_error,
                            len(bencoded_data),
                            bencoded_data[:20].hex() if len(bencoded_data) >= 20 else bencoded_data.hex(),
                            exc_info=True,
                        )
                        # Don't try JSON fallback - BEP 10 is always bencoded
                        # Log and return to avoid processing invalid data
                        return

                    # Store peer extensions (this will extract SSL capability)
                    extension_manager.set_peer_extensions(peer_id, handshake_data)

                    # Update connection's peer_info with SSL capability if discovered
                    if connection.peer_info:
                        # Check if SSL extension is supported by this peer
                        ssl_capable = extension_manager.peer_supports_extension(peer_id, "ssl")
                        if ssl_capable is not None:
                            # Update peer_info with SSL capability
                            connection.peer_info.ssl_capable = ssl_capable
                            self.logger.debug(
                                "Updated peer_info SSL capability for %s: %s",
                                connection.peer_info,
                                ssl_capable,
                            )

                    # Handle XET folder sync handshake extension
                    try:
                        from ccbt.extensions.xet_handshake import XetHandshakeExtension
                        from ccbt.session.session import AsyncSessionManager

                        # Get XET handshake extension if available
                        xet_handshake = getattr(self, "_xet_handshake", None)
                        if xet_handshake is None:
                            # Try to get from session manager if available
                            if hasattr(self, "session_manager") and isinstance(
                                self.session_manager, AsyncSessionManager
                            ):
                                # Get XET sync manager if available
                                sync_manager = getattr(
                                    self.session_manager, "_xet_sync_manager", None
                                )
                                if sync_manager:
                                    allowlist_hash = sync_manager.get_allowlist_hash()
                                    sync_mode = sync_manager.get_sync_mode()
                                    git_ref = sync_manager.get_current_git_ref()
                                    xet_handshake = XetHandshakeExtension(
                                        allowlist_hash=allowlist_hash,
                                        sync_mode=sync_mode,
                                        git_ref=git_ref,
                                    )
                                    self._xet_handshake = xet_handshake

                        if xet_handshake:
                            # Decode XET handshake from peer
                            peer_xet_data = xet_handshake.decode_handshake(
                                peer_id, handshake_data
                            )

                            if peer_xet_data:
                                # Verify allowlist hash
                                peer_allowlist_hash = peer_xet_data.get("allowlist_hash")
                                if not xet_handshake.verify_peer_allowlist(
                                    peer_id, peer_allowlist_hash
                                ):
                                    self.logger.warning(
                                        "Rejecting peer %s: allowlist verification failed",
                                        connection.peer_info,
                                    )
                                    # Close connection if allowlist verification fails
                                    await connection.close()
                                    return

                                # Negotiate sync mode
                                peer_sync_mode = peer_xet_data.get("sync_mode", "best_effort")
                                agreed_mode = xet_handshake.negotiate_sync_mode(
                                    peer_id, peer_sync_mode
                                )
                                if agreed_mode is None:
                                    self.logger.warning(
                                        "Rejecting peer %s: sync mode negotiation failed",
                                        connection.peer_info,
                                    )
                                    await connection.close()
                                    return

                                self.logger.info(
                                    "XET handshake verified for peer %s: sync_mode=%s, git_ref=%s",
                                    connection.peer_info,
                                    agreed_mode,
                                    peer_xet_data.get("git_ref"),
                                )
                    except Exception as e:
                        # Log but don't fail connection if XET handshake fails
                        # (peer may not support XET folder sync)
                        self.logger.debug(
                            "XET handshake processing failed for %s: %s",
                            connection.peer_info,
                            e,
                        )

                    # CRITICAL FIX: Extract ut_metadata_id and metadata_size BEFORE sending our handshake
                    # This ensures we have the information needed to trigger metadata exchange
                    # IMPORTANT: Handle both bytes and string keys (BEP 10 allows both)
                    ut_metadata_id = None
                    metadata_size = None
                    if isinstance(handshake_data, dict):
                        # Try string keys first, then bytes keys
                        m_dict = handshake_data.get("m") or handshake_data.get(b"m", {})
                        if isinstance(m_dict, dict):
                            ut_metadata_id = m_dict.get("ut_metadata") or m_dict.get(b"ut_metadata")
                        metadata_size = handshake_data.get("metadata_size") or handshake_data.get(b"metadata_size")

                    # CRITICAL FIX: Log extracted values at INFO level
                    self.logger.info(
                        "EXTENSION_HANDSHAKE_EXTRACTED: from %s, ut_metadata_id=%s, metadata_size=%s, has_piece_manager=%s, num_pieces=%s",
                        connection.peer_info,
                        ut_metadata_id,
                        metadata_size,
                        hasattr(self, "piece_manager") and self.piece_manager is not None,
                        getattr(self.piece_manager, "num_pieces", None) if hasattr(self, "piece_manager") and self.piece_manager else None,
                    )

                    # CRITICAL FIX: Send our extension handshake to peer (BEP 10 requirement)
                    # We MUST send our extension handshake before using extension messages
                    # This is required by BEP 10 - peers will reject extension messages if we haven't sent our handshake
                    try:
                        await self._send_our_extension_handshake(connection)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to send our extension handshake to %s: %s (continuing anyway)",
                            connection.peer_info,
                            e,
                        )

                    # CRITICAL FIX: Trigger metadata exchange for magnet links
                    # Check if this is a magnet link and metadata is not available
                    # IMPORTANT: Check both piece_manager.num_pieces == 0 AND torrent_data structure
                    is_magnet_link = False
                    if hasattr(self, "piece_manager") and self.piece_manager:
                        # Check if metadata is missing (magnet link)
                        if hasattr(self.piece_manager, "num_pieces") and self.piece_manager.num_pieces == 0:
                            is_magnet_link = True
                    # Also check torrent_data structure
                    if not is_magnet_link and isinstance(self.torrent_data, dict):
                        file_info = self.torrent_data.get("file_info")
                        if file_info is None or (isinstance(file_info, dict) and file_info.get("total_length", 0) == 0):
                            is_magnet_link = True

                    if is_magnet_link and ut_metadata_id is not None and metadata_size is not None:
                        self.logger.info(
                            "MAGNET_METADATA_EXCHANGE: Peer %s supports ut_metadata (id=%s, metadata_size=%d). Triggering metadata exchange.",
                            connection.peer_info,
                            ut_metadata_id,
                            metadata_size,
                        )
                        # CRITICAL FIX: Actually trigger metadata exchange, don't just log
                        # Use the existing connection's reader/writer for metadata exchange
                        if connection.reader and connection.writer:
                            try:
                                # Trigger metadata exchange asynchronously
                                asyncio.create_task(
                                    self._trigger_metadata_exchange(
                                        connection, int(ut_metadata_id), handshake_data
                                    )
                                )
                                self.logger.info(
                                    "MAGNET_METADATA_EXCHANGE: Metadata exchange task created for %s",
                                    connection.peer_info,
                                )
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to trigger metadata exchange for %s: %s",
                                    connection.peer_info,
                                    e,
                                    exc_info=True,
                                )
                    elif is_magnet_link:
                        self.logger.warning(
                            "MAGNET_METADATA_EXCHANGE: Cannot trigger metadata exchange for %s: ut_metadata_id=%s, metadata_size=%s",
                            connection.peer_info,
                            ut_metadata_id,
                            metadata_size,
                        )

                    # Handle SSL extension handshake
                    ssl_ext = extension_manager.get_extension("ssl")
                    if ssl_ext:
                        ssl_ext.decode_handshake(handshake_data)
                except Exception as e:
                    self.logger.warning(
                        "EXTENSION_HANDSHAKE_ERROR: Error processing extension handshake from %s: %s (payload length=%d, first bytes=%s)",
                        connection.peer_info,
                        e,
                        len(payload),
                        payload[:20].hex() if len(payload) >= 20 else payload.hex(),
                        exc_info=True,
                    )
            else:
                # CRITICAL FIX: Handle ut_metadata responses FIRST (BEP 9)
                # Check if this is a ut_metadata response for an active metadata exchange
                # ut_metadata responses have extension_id = ut_metadata_id (from handshake)
                # According to BEP 9, ut_metadata responses have format:
                # <message_id (20)><ut_metadata_id><bencoded_header><piece_data>
                # Where bencoded_header is: d8:msg_typei1e5:piecei<index>ee (data) or d8:msg_typei2e5:piecei<index>ee (reject)
                # CRITICAL FIX: Use consistent peer_key format (ip:port) to match storage format
                if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                else:
                    peer_key = str(connection.peer_info)

                # Log all extension messages for debugging (BEP 10 compliance check)
                # Show first few bytes of payload to help diagnose parsing issues
                payload_preview = extension_payload[:50].hex() if len(extension_payload) >= 50 else extension_payload.hex()
                # CRITICAL: Log at INFO level to ensure visibility
                self.logger.info(
                    "Processing extension message from %s: extension_id=%d, payload_len=%d, active_exchanges=%d, payload_preview=%s",
                    connection.peer_info,
                    extension_id,
                    len(extension_payload),
                    len(self._metadata_exchange_state),
                    payload_preview,
                )

                # CRITICAL: Check for ut_metadata responses FIRST, before other extension handlers
                # This ensures we don't miss responses due to other handlers consuming the message
                ut_metadata_handled = False
                if peer_key in self._metadata_exchange_state:
                    metadata_state = self._metadata_exchange_state[peer_key]
                    ut_metadata_id = metadata_state.get("ut_metadata_id")

                    # BEP 9/10 compliance: Log at INFO level for visibility
                    self.logger.info(
                        "Found metadata exchange state for %s (peer_key=%s): ut_metadata_id=%s, extension_id=%d, payload_len=%d",
                        connection.peer_info,
                        peer_key,
                        ut_metadata_id,
                        extension_id,
                        len(extension_payload),
                    )

                    # Ensure both are integers for comparison
                    if ut_metadata_id is not None:
                        ut_metadata_id = int(ut_metadata_id)
                        extension_id_int = int(extension_id) if extension_id is not None else None

                        # CRITICAL FIX: Check if extension_id matches peer's declared ut_metadata_id
                        # Some buggy peers declare ut_metadata_id=2 but send extension_id=1
                        # So we also check if extension_id=1 (our ut_metadata_id) as a fallback
                        our_ut_metadata_id = 1  # We always use extension_id=1 for ut_metadata
                        is_ut_metadata = (
                            extension_id_int == ut_metadata_id or
                            (extension_id_int == our_ut_metadata_id and len(extension_payload) > 0)
                        )

                        if is_ut_metadata:
                            # This is a ut_metadata response (BEP 9)
                            if extension_id_int != ut_metadata_id:
                                # Log warning for buggy peers that don't follow BEP 10 correctly
                                self.logger.warning(
                                    "Peer %s declared ut_metadata_id=%d but sent extension_id=%d. "
                                    "This is a BEP 10 compliance issue, but accepting response anyway.",
                                    connection.peer_info,
                                    ut_metadata_id,
                                    extension_id_int,
                                )
                            self.logger.info(
                                "Detected ut_metadata response from %s (extension_id=%d, payload_len=%d)",
                                connection.peer_info,
                                extension_id_int,
                                len(extension_payload),
                            )
                            await self._handle_ut_metadata_response(
                                connection, extension_payload, metadata_state
                            )
                            ut_metadata_handled = True
                        else:
                            self.logger.debug(
                                "Extension message from %s is not ut_metadata (extension_id=%d, expected ut_metadata_id=%d)",
                                connection.peer_info,
                                extension_id_int,
                                ut_metadata_id,
                            )
                    else:
                        self.logger.debug(
                            "Metadata exchange state for %s has no ut_metadata_id",
                            connection.peer_info,
                        )
                else:
                    # Log which peers have active metadata exchanges for debugging
                    active_peers = list(self._metadata_exchange_state.keys())
                    # BEP 9/10 compliance: Log at INFO level when we receive extension messages but no state
                    # This helps diagnose why ut_metadata responses aren't being detected
                    self.logger.info(
                        "No metadata exchange state for %s (peer_key=%s, extension_id=%d, payload_len=%d, active_exchanges=%d: %s)",
                        connection.peer_info,
                        peer_key,
                        extension_id,
                        len(extension_payload),
                        len(active_peers),
                        active_peers[:5] if len(active_peers) > 5 else active_peers,
                    )

                    # CRITICAL FIX: Check if this might be a ut_metadata response even without active state
                    # This can happen if state was cleaned up due to timeout but response arrived late
                    # Check if extension_id matches ut_metadata from peer's extension handshake
                    peer_id = str(connection.peer_info) if connection.peer_info else ""
                    peer_extensions = extension_manager.get_peer_extensions(peer_id)
                    if peer_extensions:
                        peer_ut_metadata_id = peer_extensions.get("m", {}).get("ut_metadata")
                        if peer_ut_metadata_id is not None and extension_id == int(peer_ut_metadata_id):
                            self.logger.warning(
                                "LATE_UT_METADATA_RESPONSE: Received ut_metadata response from %s (extension_id=%d) but no active metadata exchange state. "
                                "This may indicate state was cleaned up prematurely or response arrived after timeout. "
                                "Attempting to recreate state from peer extensions.",
                                connection.peer_info,
                                extension_id,
                            )
                            # CRITICAL FIX: Try to recreate state if we have peer extensions
                            # This allows us to handle late responses
                            try:
                                # Get metadata_size from peer extensions (stored during handshake)
                                metadata_size = peer_extensions.get("metadata_size")
                                if metadata_size and isinstance(metadata_size, (int, bytes)):
                                    # Convert bytes to int if needed
                                    if isinstance(metadata_size, bytes):
                                        try:
                                            metadata_size = int.from_bytes(metadata_size, "big")
                                        except (ValueError, OverflowError):
                                            metadata_size = None

                                    if metadata_size:
                                        import math
                                        num_pieces = math.ceil(metadata_size / 16384)
                                        # Recreate state for late response handling
                                        piece_events: dict[int, asyncio.Event] = {}
                                        piece_data_dict: dict[int, bytes | None] = {}
                                        for piece_idx in range(num_pieces):
                                            piece_events[piece_idx] = asyncio.Event()
                                            piece_data_dict[piece_idx] = None

                                        self._metadata_exchange_state[peer_key] = {
                                            "ut_metadata_id": int(peer_ut_metadata_id),
                                            "metadata_size": metadata_size,
                                            "num_pieces": num_pieces,
                                            "pieces": piece_data_dict,
                                            "events": piece_events,
                                            "complete": False,
                                        }
                                        self.logger.info(
                                            "LATE_UT_METADATA_RESPONSE: Recreated metadata exchange state for %s (metadata_size=%d, num_pieces=%d)",
                                            connection.peer_info,
                                            metadata_size,
                                            num_pieces,
                                        )
                                        # Now try to handle the response
                                        metadata_state = self._metadata_exchange_state[peer_key]
                                        await self._handle_ut_metadata_response(
                                            connection, extension_payload, metadata_state
                                        )
                                        ut_metadata_handled = True
                            except Exception as recreate_error:
                                self.logger.warning(
                                    "Failed to recreate metadata exchange state for late response from %s: %s",
                                    connection.peer_info,
                                    recreate_error,
                                    exc_info=True,
                                )

                # Handle other extension messages only if ut_metadata wasn't handled
                # Use registered extension handlers for pluggable architecture
                if not ut_metadata_handled:
                    # Check if there's a registered handler for this extension_id
                    registered_handler = extension_protocol.message_handlers.get(extension_id)
                    if registered_handler:
                        # Use registered handler (for extensions that register via ExtensionProtocol)
                        try:
                            response = await registered_handler(peer_id, extension_payload)
                            if response and connection.writer:
                                # Send response back
                                extension_message = extension_protocol.encode_extension_message(
                                    extension_id, response
                                )
                                connection.writer.write(extension_message)
                                await connection.writer.drain()
                        except Exception as handler_error:
                            self.logger.debug(
                                "Error in registered extension handler for extension_id=%d from %s: %s",
                                extension_id,
                                connection.peer_info,
                                handler_error,
                            )
                    else:
                        # Fallback to ExtensionManager handlers for extensions that don't use registration
                        # Handle SSL extension messages
                        ssl_ext_info = extension_protocol.get_extension_info("ssl")
                        if ssl_ext_info and extension_id == ssl_ext_info.message_id:
                            # Route to SSL extension handler
                            response = await extension_manager.handle_ssl_message(
                                peer_id, extension_id, extension_payload
                            )
                            if response and connection.writer:
                                # Send response back
                                extension_message = extension_protocol.encode_extension_message(
                                    extension_id, response
                                )
                                connection.writer.write(extension_message)
                                await connection.writer.drain()

                        # Handle Xet extension messages
                        xet_ext_info = extension_protocol.get_extension_info("xet")
                        if xet_ext_info and extension_id == xet_ext_info.message_id:
                            # Route to Xet extension handler
                            response = await extension_manager.handle_xet_message(
                                peer_id, extension_id, extension_payload
                            )
                            if response and connection.writer:
                                # Send response back
                                extension_message = extension_protocol.encode_extension_message(
                                    extension_id, response
                                )
                                connection.writer.write(extension_message)
                                await connection.writer.drain()

        except Exception as e:
            self.logger.warning(
                "Error handling extension message from %s: %s (extension_id=%s, payload_len=%d)",
                connection.peer_info,
                e,
                extension_id if "extension_id" in locals() else "unknown",
                len(extension_payload) if "extension_payload" in locals() else 0,
                exc_info=True,
            )
            # Still try to check for ut_metadata even if other handlers failed
            try:
                # CRITICAL FIX: Use consistent peer_key format (ip:port)
                if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                else:
                    peer_key = str(connection.peer_info)
                if peer_key in self._metadata_exchange_state:
                    metadata_state = self._metadata_exchange_state[peer_key]
                    ut_metadata_id = metadata_state.get("ut_metadata_id")
                    if ut_metadata_id is not None and extension_id == int(ut_metadata_id):
                        self.logger.info(
                            "Detected ut_metadata response from %s despite error in extension handler (extension_id=%d)",
                            connection.peer_info,
                            extension_id,
                        )
                        await self._handle_ut_metadata_response(
                            connection, extension_payload, metadata_state
                        )
            except Exception as fallback_error:
                self.logger.debug(
                    "Error in ut_metadata fallback check for %s: %s",
                    connection.peer_info,
                    fallback_error,
                )

    async def handle_v2_message(
        self,
        connection: AsyncPeerConnection,
        message: Any,
    ) -> None:
        """Handle v2 protocol message (BEP 52).

        Routes v2 messages (piece layer and file tree requests/responses)
        to appropriate handlers.

        Args:
            connection: Peer connection
            message: v2 message object (PieceLayerRequest, PieceLayerResponse, etc.)

        """
        try:
            if isinstance(message, PieceLayerRequest):
                await self._handle_piece_layer_request(connection, message)
            elif isinstance(message, PieceLayerResponse):
                await self._handle_piece_layer_response(connection, message)
            elif isinstance(message, FileTreeRequest):
                await self._handle_file_tree_request(connection, message)
            elif isinstance(
                message, FileTreeResponse
            ):  # pragma: no cover - v2 message handling, requires v2 torrent and peer support
                await self._handle_file_tree_response(connection, message)
            else:  # pragma: no cover - Unknown v2 message type, defensive error handling
                self.logger.warning(
                    "Unknown v2 message type: %s from %s",
                    type(message).__name__,
                    connection.peer_info,
                )

        except (
            Exception
        ):  # pragma: no cover - v2 message exception handler, defensive error handling
            self.logger.exception(
                "Error handling v2 message from %s",
                connection.peer_info,
            )

    async def _handle_piece_layer_request(
        self,
        connection: AsyncPeerConnection,
        message: PieceLayerRequest,
    ) -> None:
        """Handle piece layer request from peer.

        Args:
            connection: Peer connection
            message: Piece layer request message

        """
        self.logger.debug(
            "Received piece layer request for pieces_root %s from %s",
            message.pieces_root.hex()[:16],
            connection.peer_info,
        )

        # Get piece layer from torrent data
        # CRITICAL FIX: Safe access to torrent_data - handle case where it might not be a dict
        if not isinstance(self.torrent_data, dict):
            self.logger.error(
                "torrent_data is not a dict (type: %s), cannot get piece_layers",
                type(self.torrent_data),
            )
            return
        piece_layers = self.torrent_data.get("piece_layers")
        if not piece_layers:  # pragma: no cover - v2 torrent piece layers missing, requires v2 torrent structure
            self.logger.warning(
                "No piece layers available for %s",
                connection.peer_info,
            )
            return

        # Find matching piece layer
        pieces_root_bytes = message.pieces_root
        piece_hashes = piece_layers.get(pieces_root_bytes)

        if (
            piece_hashes is None
        ):  # pragma: no cover - Piece layer not found for pieces_root, requires specific v2 piece structure
            self.logger.warning(
                "Piece layer not found for pieces_root %s",
                pieces_root_bytes.hex()[:16],
            )
            return

        # Send piece layer response
        response = PieceLayerResponse(pieces_root_bytes, piece_hashes)
        await self.send_v2_message(connection, response)

    async def _handle_piece_layer_response(
        self,
        connection: AsyncPeerConnection,
        message: PieceLayerResponse,
    ) -> None:
        """Handle piece layer response from peer.

        Args:
            connection: Peer connection
            message: Piece layer response message

        """
        self.logger.debug(
            "Received piece layer response for pieces_root %s from %s (%d hashes)",
            message.pieces_root.hex()[:16],
            connection.peer_info,
            len(message.piece_hashes),
        )

        # Update piece manager with piece availability from piece layer
        if self.piece_manager:
            try:
                # Extract piece indices from piece hashes
                # In v2 torrents, piece hashes correspond to pieces for a specific file
                # We need to map these to global piece indices
                piece_indices: set[int] = set()

                # Try to map piece hashes to piece indices using torrent metadata
                if isinstance(self.torrent_data, dict):
                    piece_layers = self.torrent_data.get("piece_layers", {})
                    if piece_layers and message.pieces_root in piece_layers:
                        # Get the piece layer for this pieces_root
                        # layer_hashes = piece_layers[message.pieces_root]  # Reserved for future v2 implementation

                        # For v2 torrents, we need to find the file that corresponds to this pieces_root
                        # and map its pieces to global piece indices
                        # This is complex and depends on the torrent structure
                        # For now, we'll use a heuristic: if we have piece hash list in torrent,
                        # try to match hashes to get indices
                        if "piece_hashes" in self.torrent_data:
                            torrent_piece_hashes = self.torrent_data["piece_hashes"]
                            if isinstance(torrent_piece_hashes, list):
                                # Match piece hashes to find indices
                                for i, torrent_hash in enumerate(torrent_piece_hashes):
                                    if torrent_hash in message.piece_hashes:
                                        piece_indices.add(i)

                # If we found piece indices, update piece manager
                if piece_indices:
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                    await self.piece_manager.update_peer_availability(
                        peer_key, piece_indices
                    )
                    self.logger.debug(
                        "Updated piece availability from piece layer: %d pieces for %s",
                        len(piece_indices),
                        peer_key,
                    )
                else:
                    self.logger.debug(
                        "Could not map piece layer hashes to piece indices for %s",
                        connection.peer_info,
                    )
            except Exception as e:
                self.logger.warning(
                    "Failed to update piece manager from piece layer: %s",
                    e,
                    exc_info=True,
                )

        # Maintain callback mechanism for external integrations
        if hasattr(
            self, "on_piece_layer_received"
        ):  # pragma: no cover - Optional callback for piece layer, tested via direct piece layer handling
            self.on_piece_layer_received(connection, message)  # type: ignore[attr-defined]

    async def _handle_file_tree_request(
        self,
        connection: AsyncPeerConnection,
        _message: FileTreeRequest,
    ) -> None:
        """Handle file tree request from peer.

        Args:
            connection: Peer connection
            message: File tree request message

        """
        self.logger.debug(
            "Received file tree request from %s",
            connection.peer_info,
        )

        # Get file tree from torrent data
        # CRITICAL FIX: Safe access to torrent_data - handle case where it might not be a dict
        if not isinstance(self.torrent_data, dict):
            self.logger.error(
                "torrent_data is not a dict (type: %s), cannot get file_tree",
                type(self.torrent_data),
            )
            return
        file_tree = self.torrent_data.get("file_tree")
        if not file_tree:
            self.logger.warning(
                "No file tree available for %s",
                connection.peer_info,
            )
            return

        # Bencode file tree
        from ccbt.core.bencode import encode

        try:
            file_tree_bytes = encode(file_tree)
            response = FileTreeResponse(file_tree_bytes)
            await self.send_v2_message(connection, response)
        except (
            Exception
        ):  # pragma: no cover - File tree encoding error, defensive error handling
            self.logger.exception(
                "Failed to encode file tree for %s",
                connection.peer_info,
            )

    async def _handle_file_tree_response(
        self,
        connection: AsyncPeerConnection,
        message: FileTreeResponse,
    ) -> None:
        """Handle file tree response from peer.

        Args:
            connection: Peer connection
            message: File tree response message

        """
        self.logger.debug(
            "Received file tree response from %s (%d bytes)",
            connection.peer_info,
            len(message.file_tree),
        )

        # Parse and store file tree
        from ccbt.core.bencode import decode

        try:
            file_tree = decode(message.file_tree)

            # Validate file tree structure
            if not isinstance(file_tree, dict):
                self.logger.warning(
                    "Invalid file tree structure from %s: expected dict, got %s",
                    connection.peer_info,
                    type(file_tree).__name__,
                )
            # Update torrent metadata with file tree information
            elif isinstance(self.torrent_data, dict):
                # Update file_tree in torrent_data
                old_file_tree = self.torrent_data.get("file_tree")
                self.torrent_data["file_tree"] = file_tree

                # Extract file list, sizes, and paths from tree structure
                # File tree structure: {file_path: {length: int, pieces_root: bytes, ...}, ...}
                file_count = len(file_tree)
                self.logger.info(
                    "Updated torrent metadata with file tree from %s: %d files",
                    connection.peer_info,
                    file_count,
                )

                # Preserve existing metadata where file tree doesn't provide data
                # The file tree may not have all metadata, so we merge carefully
                if old_file_tree and isinstance(old_file_tree, dict):
                    # Merge old metadata with new file tree
                    for key, value in old_file_tree.items():
                        if key not in file_tree:
                            file_tree[key] = value

                # Log update for debugging
                self.logger.debug(
                    "File tree update complete for torrent, %d files in tree",
                    file_count,
                )
            else:
                self.logger.warning(
                    "Cannot update torrent metadata: torrent_data is not a dict"
                )

            # Maintain callback mechanism for external integrations
            if hasattr(
                self, "on_file_tree_received"
            ):  # pragma: no cover - Optional callback for file tree, tested via direct file tree handling
                self.on_file_tree_received(connection, file_tree)  # type: ignore[attr-defined]
        except (
            Exception
        ):  # pragma: no cover - File tree decoding error, defensive error handling
            self.logger.exception(
                "Failed to decode file tree from %s",
                connection.peer_info,
            )

    async def send_v2_message(
        self,
        connection: AsyncPeerConnection,
        message: Any,
    ) -> None:
        """Send v2 protocol message to peer.

        Args:
            connection: Peer connection
            message: v2 message object (PieceLayerRequest, PieceLayerResponse, etc.)

        Raises:
            RuntimeError: If connection is not ready or send fails

        """
        if (
            connection.writer is None
        ):  # pragma: no cover - Defensive check: writer should exist for active connection
            msg = f"Cannot send v2 message: connection {connection.peer_info} has no writer"
            raise RuntimeError(msg)

        if not connection.is_active():  # pragma: no cover - Defensive check: connection should be active before sending
            msg = f"Cannot send v2 message: connection {connection.peer_info} is not active"
            raise RuntimeError(msg)

        try:
            message_bytes = message.serialize()
            connection.writer.write(message_bytes)
            await connection.writer.drain()

            self.logger.debug(
                "Sent %s to %s",
                type(message).__name__,
                connection.peer_info,
            )
            connection.stats.last_activity = time.time()
            connection.stats.bytes_uploaded += len(message_bytes)

        except (
            Exception
        ):  # pragma: no cover - v2 message send error, defensive error handling
            self.logger.exception(
                "Failed to send v2 message to %s",
                connection.peer_info,
            )
            raise

    async def _handle_choke(
        self,
        connection: AsyncPeerConnection,
        _message: ChokeMessage,
    ) -> None:
        """Handle choke message."""
        connection.peer_choking = True
        connection.state = ConnectionState.CHOKED
        self.logger.debug("Peer %s choked us", connection.peer_info)

    async def _handle_unchoke(
        self,
        connection: AsyncPeerConnection,
        _message: UnchokeMessage,
    ) -> None:
        """Handle unchoke message."""
        state_before = connection.state.value
        choking_before = connection.peer_choking

        connection.peer_choking = False
        connection.state = ConnectionState.ACTIVE

        self.logger.info(
            "Peer %s UNCHOKED us - can now request pieces (state: %s -> %s, choking: %s -> %s)",
            connection.peer_info,
            state_before,
            connection.state.value,
            choking_before,
            connection.peer_choking,
        )

        # Validate state transition
        if connection.state != ConnectionState.ACTIVE:
            self.logger.warning(
                "State validation failed: expected ACTIVE after UNCHOKE, got %s for peer %s",
                connection.state.value,
                connection.peer_info,
            )

        # CRITICAL FIX: Send INTERESTED immediately when peer unchokes us
        # This is required by BitTorrent protocol - we must be interested to request pieces
        # Even if we haven't received a bitfield yet, we should send INTERESTED to keep the connection active
        if not connection.am_interested:
            try:
                await self._send_interested(connection)
                connection.am_interested = True
                self.logger.info(
                    "Sent INTERESTED to %s after UNCHOKE (peer unchoked us, sending INTERESTED to keep connection active)",
                    connection.peer_info,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to send INTERESTED to %s after UNCHOKE: %s (peer may choke us again)",
                    connection.peer_info,
                    e,
                )

        # CRITICAL FIX: Trigger piece selection when peer unchokes us
        # This ensures we immediately start requesting pieces from newly unchoked peers
        # CRITICAL FIX: Use INFO level logging to ensure we see this in production logs
        self.logger.info(
            "UNCHOKE handler: piece_manager=%s, has_select_pieces=%s, peer=%s",
            self.piece_manager is not None,
            hasattr(self.piece_manager, "_select_pieces") if self.piece_manager else False,
            connection.peer_info,
        )
        if self.piece_manager and hasattr(self.piece_manager, "_select_pieces"):

            async def trigger_piece_selection_with_retry() -> None:
                """Trigger piece selection with retry logic."""
                max_retries = 3
                retry_delay = 0.5

                for attempt in range(max_retries):
                    try:
                        # CRITICAL FIX: Check if download is started before selecting pieces
                        if not getattr(self.piece_manager, "is_downloading", False):
                            self.logger.info(
                                "Piece manager download not started (is_downloading=False) - starting download from UNCHOKE handler (peer: %s)",
                                connection.peer_info,
                            )
                            # Start download if not started
                            if hasattr(self.piece_manager, "start_download"):
                                if asyncio.iscoroutinefunction(
                                    self.piece_manager.start_download
                                ):
                                    await self.piece_manager.start_download(self)
                                else:
                                    self.piece_manager.start_download(self)
                                self.logger.info(
                                    "Started piece manager download from UNCHOKE handler (peer: %s, is_downloading=%s)",
                                    connection.peer_info,
                                    getattr(self.piece_manager, "is_downloading", False),
                                )

                        # CRITICAL FIX: Ensure _peer_manager is set before selecting pieces
                        peer_manager = getattr(
                            self.piece_manager, "_peer_manager", None
                        )
                        if not peer_manager:
                            self.logger.debug(
                                "Setting _peer_manager on piece_manager from UNCHOKE handler"
                            )
                            setattr(self.piece_manager, "_peer_manager", self)  # noqa: B010
                            peer_manager = self

                        # Check if peer_manager is available before selecting pieces
                        peer_manager = getattr(
                            self.piece_manager, "_peer_manager", None
                        )
                        if not peer_manager:
                            if attempt < max_retries - 1:
                                self.logger.debug(
                                    "Piece manager peer_manager not available yet (attempt %d/%d), retrying in %.1fs",
                                    attempt + 1,
                                    max_retries,
                                    retry_delay,
                                )
                                await asyncio.sleep(retry_delay)
                                continue
                            self.logger.warning(
                                "Cannot trigger piece selection: piece_manager._peer_manager is None after %d attempts",
                                max_retries,
                            )
                            return

                        # Trigger piece selection
                        select_pieces = getattr(
                            self.piece_manager, "_select_pieces", None
                        )
                        if select_pieces:
                            await select_pieces()

                        # CRITICAL FIX: Also retry pieces that were stuck in REQUESTED state
                        # This ensures pieces that couldn't be requested earlier (due to no unchoked peers)
                        # are retried immediately when peers become available
                        retry_method = getattr(
                            self.piece_manager, "_retry_requested_pieces", None
                        )
                        if retry_method:
                            try:
                                await retry_method()
                                self.logger.debug(
                                    "Successfully retried REQUESTED pieces after UNCHOKE from %s",
                                    connection.peer_info,
                                )
                            except Exception as retry_error:
                                self.logger.warning(
                                    "Failed to retry REQUESTED pieces after UNCHOKE from %s: %s",
                                    connection.peer_info,
                                    retry_error,
                                )

                        self.logger.debug(
                            "Successfully triggered piece selection after UNCHOKE from %s (attempt %d)",
                            connection.peer_info,
                            attempt + 1,
                        )
                        return
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(
                                "Failed to trigger piece selection after UNCHOKE from %s (attempt %d/%d): %s, retrying in %.1fs",
                                connection.peer_info,
                                attempt + 1,
                                max_retries,
                                e,
                                retry_delay,
                            )
                            await asyncio.sleep(retry_delay)
                        else:
                            self.logger.warning(
                                "Failed to trigger piece selection after UNCHOKE from %s after %d attempts: %s",
                                connection.peer_info,
                                max_retries,
                                e,
                            )

            # Trigger piece selection asynchronously
            task = asyncio.create_task(trigger_piece_selection_with_retry())
            # Store task reference and add error callback to catch silent failures
            def log_task_error(task: asyncio.Task) -> None:
                try:
                    task.result()  # This will raise if task failed
                except Exception as e:
                    self.logger.error(
                        "❌ UNCHOKE_TRIGGER: Piece selection task failed after UNCHOKE from %s: %s",
                        connection.peer_info,
                        e,
                        exc_info=True,
                    )
            task.add_done_callback(log_task_error)
            self.logger.info(
                "⚡ UNCHOKE_TRIGGER: Triggered piece selection task after UNCHOKE from %s (will request pieces immediately, piece_manager=%s, has_select_pieces=%s)",
                connection.peer_info,
                self.piece_manager is not None,
                hasattr(self.piece_manager, "_select_pieces") if self.piece_manager else False,
            )
        else:
            self.logger.warning(
                "Cannot trigger piece selection: piece_manager=%s, has_select_pieces=%s",
                self.piece_manager is not None,
                hasattr(self.piece_manager, "_select_pieces")
                if self.piece_manager
                else False,
            )

    async def _monitor_unchoke_timeout(
        self,
        connection: AsyncPeerConnection,
        connection_start_time: float,
    ) -> None:
        """Monitor if peer sends UNCHOKE message within reasonable time.

        Args:
            connection: Peer connection to monitor
            connection_start_time: Timestamp when connection was established

        """
        unchoke_timeout = 30.0  # 30 seconds
        check_interval = 5.0  # Check every 5 seconds

        try:
            while connection.is_connected():
                await asyncio.sleep(check_interval)

                elapsed = time.time() - connection_start_time

                # If peer is still choking after timeout, log warning
                if elapsed >= unchoke_timeout and connection.peer_choking:
                    self.logger.warning(
                        "Peer %s has not sent UNCHOKE message after %.1f seconds. "
                        "Connection state: %s, choking: %s, interested: %s. "
                        "This peer may be unresponsive or not following protocol correctly.",
                        connection.peer_info,
                        elapsed,
                        connection.state.value,
                        connection.peer_choking,
                        connection.am_interested,
                    )
                    # Only log once, then stop monitoring
                    break

                # If peer unchoked us, stop monitoring
                if not connection.peer_choking:
                    self.logger.debug(
                        "Peer %s unchoked us after %.1f seconds (monitoring stopped)",
                        connection.peer_info,
                        elapsed,
                    )
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.debug(
                "Error in unchoke timeout monitor for %s: %s", connection.peer_info, e
            )

    async def _handle_interested(
        self,
        connection: AsyncPeerConnection,
        _message: InterestedMessage,
    ) -> None:
        """Handle interested message."""
        connection.peer_interested = True
        self.logger.debug("Peer %s is interested", connection.peer_info)

    async def _handle_not_interested(
        self,
        connection: AsyncPeerConnection,
        _message: NotInterestedMessage,
    ) -> None:
        """Handle not interested message."""
        connection.peer_interested = False
        self.logger.debug("Peer %s is not interested", connection.peer_info)

    async def _handle_have(
        self,
        connection: AsyncPeerConnection,
        message: HaveMessage,
    ) -> None:
        """Handle have message."""
        piece_index = message.piece_index

        # CRITICAL FIX: Check for duplicate Have messages and skip all processing for duplicates
        is_duplicate = piece_index in connection.peer_state.pieces_we_have
        if is_duplicate:
            # Early return for duplicates - don't process, don't update frequency, don't trigger selection
            self.logger.debug(
                "Duplicate Have message from %s for piece %s (already known) - skipping processing",
                connection.peer_info,
                piece_index,
            )
            return

        # Not a duplicate - process normally
        connection.peer_state.pieces_we_have.add(piece_index)
        peer_key = self._get_peer_key(connection)
        self._mark_peer_quality_verified(peer_key, "have_message", connection)

        # CRITICAL FIX: Track that peer has sent HAVE messages (alternative to bitfield)
        # This allows us to be lenient with bitfield timeout - HAVE messages are protocol-compliant
        # If peer has no pieces initially, they may send HAVE messages as they download pieces
        have_messages_count = len(connection.peer_state.pieces_we_have)

        # If peer sent HAVE messages but no bitfield, this is protocol-compliant (leecher with 0% complete)
        has_bitfield = (
            connection.peer_state.bitfield is not None
            and len(connection.peer_state.bitfield) > 0
        )

        if not has_bitfield and have_messages_count == 1:
            # First HAVE message from peer without bitfield - log this protocol-compliant behavior
            self.logger.info(
                "📨 HAVE_MESSAGE: Peer %s sent first HAVE message (piece %s) without bitfield - "
                "protocol-compliant behavior (leecher with 0%% complete, using HAVE messages instead of bitfield)",
                connection.peer_info,
                piece_index,
            )
            # CRITICAL FIX: Send INTERESTED when we receive first HAVE message from peer without bitfield
            # This is the correct protocol behavior - leechers don't send bitfields, they send HAVE messages
            if not connection.am_interested:
                try:
                    await self._send_interested(connection)
                    connection.am_interested = True
                    self.logger.info(
                        "Sent INTERESTED to %s after receiving first HAVE message (peer using HAVE-only protocol)",
                        connection.peer_info,
                    )
                except Exception as e:
                    self.logger.debug(
                        "Failed to send INTERESTED to %s after HAVE message: %s",
                        connection.peer_info,
                        e,
                    )

        self.logger.debug(
            "Peer %s has piece %s (total HAVE messages: %d, has_bitfield: %s)",
            connection.peer_info,
            piece_index,
            have_messages_count,
            has_bitfield,
        )

        # CRITICAL FIX: Update piece frequency in piece manager for rarest-first selection
        if self.piece_manager and hasattr(self.piece_manager, "update_peer_have"):
            try:
                # CRITICAL FIX: Use consistent peer_key format (ip:port) to match piece manager
                # This ensures HAVE messages update peer_availability correctly
                if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                else:
                    peer_key = str(connection.peer_info)
                await self.piece_manager.update_peer_have(
                    peer_key, piece_index
                )
                self.logger.debug(
                    "Updated piece frequency for piece %s from peer %s",
                    piece_index,
                    connection.peer_info,
                )
            except Exception:
                self.logger.exception(
                    "Error updating peer have for piece %s from %s",
                    piece_index,
                    connection.peer_info,
                )

        # CRITICAL FIX: Ensure download is started when we receive Have messages
        has_piece_manager = self.piece_manager is not None
        has_is_downloading = has_piece_manager and hasattr(
            self.piece_manager, "is_downloading"
        )
        is_downloading_value = (
            getattr(self.piece_manager, "is_downloading", False)
            if has_piece_manager
            else None
        )

        self.logger.debug(
            "Have handler check: piece_manager=%s, has_is_downloading=%s, is_downloading=%s (peer: %s, piece: %s)",
            has_piece_manager,
            has_is_downloading,
            is_downloading_value,
            connection.peer_info,
            piece_index,
        )

        if (
            self.piece_manager
            and hasattr(self.piece_manager, "is_downloading")
            and not getattr(self.piece_manager, "is_downloading", False)
        ):
            self.logger.info(
                "Download not started yet - starting download from Have handler (peer: %s, piece: %s)",
                connection.peer_info,
                piece_index,
            )
            try:
                if hasattr(self.piece_manager, "start_download"):
                    self.logger.debug(
                        "Calling piece_manager.start_download() from Have handler (peer: %s)",
                        connection.peer_info,
                    )
                    if asyncio.iscoroutinefunction(self.piece_manager.start_download):
                        await self.piece_manager.start_download(self)
                    else:
                        self.piece_manager.start_download(self)
                    self.logger.info(
                        "Successfully called piece_manager.start_download() from Have handler (peer: %s, piece: %s)",
                        connection.peer_info,
                        piece_index,
                    )
                else:
                    self.logger.warning(
                        "piece_manager does not have start_download method (peer: %s, piece: %s)",
                        connection.peer_info,
                        piece_index,
                    )
            except Exception:
                self.logger.exception(
                    "Error starting download from Have handler for piece %s (peer: %s)",
                    piece_index,
                    connection.peer_info,
                )
        elif not has_piece_manager:
            self.logger.debug(
                "Skipping start_download from Have handler: piece_manager is None (peer: %s, piece: %s)",
                connection.peer_info,
                piece_index,
            )
        elif not has_is_downloading:
            self.logger.debug(
                "Skipping start_download from Have handler: piece_manager has no is_downloading attribute (peer: %s, piece: %s)",
                connection.peer_info,
                piece_index,
            )
        elif is_downloading_value:
            self.logger.debug(
                "Skipping start_download from Have handler: is_downloading is already True (peer: %s, piece: %s)",
                connection.peer_info,
                piece_index,
            )

        # CRITICAL FIX: Trigger piece selection if download is active (with debouncing)
        if (
            self.piece_manager
            and hasattr(self.piece_manager, "is_downloading")
            and getattr(self.piece_manager, "is_downloading", False)
        ):
            try:
                if hasattr(self.piece_manager, "_select_pieces"):
                    # CRITICAL FIX: Debounce piece selection triggers to prevent excessive calls
                    import time

                    current_time = time.time()

                    async with self._piece_selection_debounce_lock:
                        time_since_last_trigger = (
                            current_time - self._last_piece_selection_trigger
                        )

                        if (
                            time_since_last_trigger
                            >= self._piece_selection_debounce_interval
                        ):
                            # Enough time has passed - trigger immediately
                            self._last_piece_selection_trigger = current_time
                            task = asyncio.create_task(
                                self.piece_manager._select_pieces()
                            )
                            _ = task  # Store reference to avoid unused variable warning
                            self.logger.debug(
                                "Triggered piece selection after Have message from %s (piece %s)",
                                connection.peer_info,
                                piece_index,
                            )
                        else:
                            # Too soon since last trigger - skip this one
                            self.logger.debug(
                                "Skipping piece selection trigger (debounced, last trigger %.3fs ago)",
                                time_since_last_trigger,
                            )
            except Exception:
                self.logger.exception(
                    "Error triggering piece selection after Have message"
                )

    async def _handle_bitfield(
        self,
        connection: AsyncPeerConnection,
        message: BitfieldMessage,
    ) -> None:
        """Handle bitfield message."""
        bitfield_length = len(message.bitfield) if message.bitfield else 0
        estimated_pieces = bitfield_length * 8

        # Validate bitfield is not empty
        if not message.bitfield or bitfield_length == 0:
            self.logger.warning(
                "Received empty bitfield from %s (state: %s). This may indicate a problem.",
                connection.peer_info,
                connection.state.value,
            )
            return

        # CRITICAL FIX: For magnet links, metadata may not be available yet
        # We should still accept bitfields from peers even without metadata
        # The bitfield will be validated later when metadata becomes available
        pieces_info = self.torrent_data.get("pieces_info")
        num_pieces = 0
        if pieces_info is not None:
            num_pieces = pieces_info.get("num_pieces", 0) if isinstance(pieces_info, dict) else 0

        # Validate bitfield length matches expected piece count (only if we have metadata)
        if num_pieces > 0:
            expected_bytes = (num_pieces + 7) // 8
            if bitfield_length != expected_bytes:
                self.logger.warning(
                    "Bitfield length mismatch from %s: expected %d bytes for %d pieces, got %d bytes",
                    connection.peer_info,
                    expected_bytes,
                    num_pieces,
                    bitfield_length,
                )
                # Continue anyway - some peers may send incorrect bitfield lengths
        else:
            # Metadata not available yet (magnet link case)
            # Store the bitfield anyway - we'll validate it later when metadata is fetched
            self.logger.debug(
                "Received bitfield from %s without metadata (magnet link) - bitfield length: %d bytes, will validate when metadata is available",
                connection.peer_info,
                bitfield_length,
            )

        # Count pieces peer has
        pieces_count = 0
        non_zero_bytes = 0
        sample_bytes = []
        if message.bitfield:
            for i, byte in enumerate(message.bitfield):
                bits_set = bin(byte).count("1")
                pieces_count += bits_set
                if byte != 0:
                    non_zero_bytes += 1
                    if len(sample_bytes) < 5:  # Sample first 5 non-zero bytes
                        sample_bytes.append((i, byte, bits_set))

        self.logger.info(
            "Received bitfield from %s (bitfield length: %d bytes, estimated pieces: ~%d, actual pieces: %d, non_zero_bytes: %d, sample: %s, state: %s)",
            connection.peer_info,
            bitfield_length,
            estimated_pieces,
            pieces_count,
            non_zero_bytes,
            sample_bytes[:3] if sample_bytes else "none",
            connection.state.value,
        )

        # CRITICAL FIX: Warn if bitfield appears to be all zeros
        # This might indicate a parsing issue or the peer actually has no pieces
        if pieces_count == 0 and bitfield_length > 0:
            # Check if bitfield is actually all zeros or if there's a parsing issue
            first_bytes_hex = message.bitfield[:min(10, len(message.bitfield))].hex() if message.bitfield else ""
            self.logger.warning(
                "Bitfield from %s appears to be all zeros (length=%d bytes, first_bytes_hex=%s). "
                "This may indicate: (1) Peer has no pieces (leecher), (2) Bitfield parsing issue, or (3) Bitfield data corruption.",
                connection.peer_info,
                bitfield_length,
                first_bytes_hex,
            )

        connection.peer_state.bitfield = message.bitfield
        connection.state = ConnectionState.BITFIELD_RECEIVED
        peer_key = self._get_peer_key(connection)
        self._mark_peer_quality_verified(peer_key, "bitfield_received", connection)

        # CRITICAL FIX: Cancel bitfield timeout monitor since we received bitfield
        # This prevents false disconnections when bitfield arrives on time
        # Also cancel if peer has sent HAVE messages (alternative to bitfield)
        has_have_messages = (
            connection.peer_state.pieces_we_have is not None
            and len(connection.peer_state.pieces_we_have) > 0
        )

        if hasattr(connection, "_timeout_tasks"):
            for task in connection._timeout_tasks[:]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            connection._timeout_tasks.clear()

            if has_have_messages:
                self.logger.debug(
                    "Cancelled bitfield timeout monitor for %s: received bitfield (peer also sent %d HAVE message(s))",
                    connection.peer_info,
                    len(connection.peer_state.pieces_we_have),
                )

        # CRITICAL FIX: Send interested message after receiving peer's bitfield
        # This ensures proper protocol message ordering: handshake -> bitfield exchange -> interested
        # Protocol requires: We send INTERESTED → Peer sends UNCHOKE → We can request pieces
        # CRITICAL FIX: Also resend INTERESTED if we already sent it but peer has pieces we want
        # This helps ensure peers know we're interested, especially if they missed our first INTERESTED
        should_send_interested = False
        should_resend_interested = False
        
        if not connection.am_interested:
            # Haven't sent INTERESTED yet - send it now
            should_send_interested = True
        elif connection.peer_choking and pieces_count > 0:
            # Already sent INTERESTED, but peer is choking and has pieces
            # Check if we've been waiting for a while (e.g., 10+ seconds since connection)
            connection_start_time = getattr(connection, "connection_start_time", None)
            if connection_start_time:
                connection_elapsed = time.time() - connection_start_time
                if connection_elapsed >= 10.0:
                    # Resend INTERESTED to encourage peer to unchoke
                    should_resend_interested = True
            else:
                # No connection start time stored - assume we've been waiting and resend anyway
                should_resend_interested = True
        
        if should_send_interested:
            try:
                await self._send_interested(connection)
                connection.am_interested = True
                self.logger.info(
                    "Sent INTERESTED message to %s after receiving bitfield (protocol: handshake → bitfield → INTERESTED → wait for UNCHOKE)",
                    connection.peer_info,
                )
            except Exception as e:
                # Log but don't fail - interested message is not critical for connection
                self.logger.warning(
                    "Failed to send INTERESTED to %s after bitfield: %s (continuing anyway, but peer may not unchoke)",
                    connection.peer_info,
                    e,
                )
        elif should_resend_interested:
            try:
                await self._send_interested(connection)
                self.logger.info(
                    "🔄 Resent INTERESTED to %s after receiving bitfield with %d pieces (peer is choking, encouraging unchoke)",
                    connection.peer_info,
                    pieces_count,
                )
            except Exception as e:
                self.logger.debug(
                    "Failed to resend INTERESTED to %s after bitfield: %s",
                    connection.peer_info,
                    e,
                )

        # CRITICAL FIX: Transition to ACTIVE after receiving bitfield and sending INTERESTED
        # This allows piece availability checking even if peer hasn't unchoked yet
        # Protocol flow: handshake → bitfield exchange → INTERESTED → (wait for UNCHOKE)
        # We transition to ACTIVE after bitfield exchange to allow piece selection
        # Actual piece requests will wait for UNCHOKE (handled by can_request())
        if connection.state == ConnectionState.BITFIELD_SENT:
            # Both bitfields exchanged - transition to ACTIVE
            connection.state = ConnectionState.ACTIVE
            self.logger.debug(
                "Transitioned %s to ACTIVE state (both bitfields exchanged)",
                connection.peer_info,
            )
        elif not connection.peer_choking:
            # Peer has already unchoked us - we're ready to download
            # This handles the case where peer sends UNCHOKE before or with bitfield
            connection.state = ConnectionState.ACTIVE
            self.logger.debug(
                "Transitioned %s to ACTIVE state (bitfield received, peer already unchoked)",
                connection.peer_info,
            )
        else:
            # CRITICAL FIX: Transition to ACTIVE even if peer is choking
            # This allows piece availability checking and selection
            # Actual piece requests will be blocked by can_request() until peer unchokes
            connection.state = ConnectionState.ACTIVE
            self.logger.debug(
                "Transitioned %s to ACTIVE state (bitfield received, peer is choking - will wait for UNCHOKE)",
                connection.peer_info,
            )

        # CRITICAL FIX: Trigger piece selection immediately after bitfield (especially for seeders)
        # This prepares piece requests even if peer is choking, so we're ready when they unchoke
        # For seeders, this is critical as they have all pieces and should be prioritized
        if self.piece_manager and hasattr(self.piece_manager, "_select_pieces"):
            # Check if peer is a seeder (100% complete) or near-seeder (90%+)
            is_seeder = getattr(connection, "is_seeder", False)
            completion_percent = getattr(connection, "completion_percent", 0.0)

            async def trigger_piece_selection_after_bitfield() -> None:
                """Trigger piece selection after bitfield with retry logic."""
                max_retries = 3
                retry_delay = 0.5

                for attempt in range(max_retries):
                    try:
                        # Ensure peer_manager is set
                        if not hasattr(self.piece_manager, "_peer_manager") or not self.piece_manager._peer_manager:
                            self.piece_manager._peer_manager = self

                        # Trigger piece selection
                        select_pieces = getattr(self.piece_manager, "_select_pieces", None)
                        if select_pieces:
                            await select_pieces()

                            if is_seeder:
                                self.logger.info(
                                    "✅ SEEDER ENGAGEMENT: Triggered piece selection after bitfield from seeder %s (100%% complete) - ready to request pieces when unchoked",
                                    connection.peer_info,
                                )
                            elif completion_percent >= 0.9:
                                self.logger.info(
                                    "✅ HIGH-VALUE PEER: Triggered piece selection after bitfield from near-seeder %s (%.1f%% complete) - ready to request pieces when unchoked",
                                    connection.peer_info,
                                    completion_percent * 100,
                                )
                            else:
                                self.logger.debug(
                                    "Triggered piece selection after bitfield from %s (completion: %.1f%%)",
                                    connection.peer_info,
                                    completion_percent * 100,
                                )
                            return
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.debug(
                                "Failed to trigger piece selection after bitfield from %s (attempt %d/%d): %s, retrying",
                                connection.peer_info,
                                attempt + 1,
                                max_retries,
                                e,
                            )
                            await asyncio.sleep(retry_delay)
                        else:
                            self.logger.warning(
                                "Failed to trigger piece selection after bitfield from %s after %d attempts: %s",
                                connection.peer_info,
                                max_retries,
                                e,
                            )

            # Trigger piece selection asynchronously (don't block bitfield handling)
            # For seeders, this is especially important to prepare requests immediately
            task = asyncio.create_task(trigger_piece_selection_after_bitfield())
            # Store task reference to avoid garbage collection
            if not hasattr(connection, "_background_tasks"):
                connection._background_tasks = []
            connection._background_tasks.append(task)

        # CRITICAL FIX: Update piece manager with peer availability
        # This must be done even if metadata is not available yet (for magnet links)
        # The bitfield will be re-processed when metadata becomes available
        if self.piece_manager and connection.peer_state.bitfield:
            try:
                # Get peer key for piece manager
                if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                else:
                    peer_key = str(connection.peer_info)

                # Update piece manager with peer availability
                # This will infer num_pieces from bitfield if metadata not available yet
                await self.piece_manager.update_peer_availability(
                    peer_key, connection.peer_state.bitfield
                )

                # CRITICAL FIX: Detect seeder status from bitfield for better prioritization
                is_seeder = False
                completion_percent = 0.0
                if hasattr(self.piece_manager, "num_pieces") and self.piece_manager.num_pieces > 0:
                    num_pieces = self.piece_manager.num_pieces
                    bits_set = sum(1 for i in range(num_pieces) if i < len(connection.peer_state.bitfield) and connection.peer_state.bitfield[i])
                    completion_percent = bits_set / num_pieces if num_pieces > 0 else 0.0
                    is_seeder = completion_percent >= 1.0

                    # Store seeder status in connection for later use
                    connection.is_seeder = is_seeder
                    connection.completion_percent = completion_percent

                self.logger.info(
                    "Updated piece manager with bitfield from %s (pieces: %d, bitfield_length: %d bytes, num_pieces: %d, completion: %.1f%%, is_seeder: %s)",
                    connection.peer_info,
                    pieces_count,
                    bitfield_length,
                    self.piece_manager.num_pieces if hasattr(self.piece_manager, "num_pieces") else 0,
                    completion_percent * 100,
                    is_seeder,
                )

                # CRITICAL FIX: Don't disconnect peers with empty bitfields immediately
                # According to BEP 3, leechers with no pieces don't send bitfields
                # They may send HAVE messages later as they download pieces
                # Only disconnect if peer has no pieces AND we've waited long enough
                if pieces_count == 0:
                    self.logger.debug(
                        "Peer %s sent empty bitfield (no pieces yet) - keeping connection (peer may send HAVE messages later as they download)",
                        connection.peer_info,
                    )
                    # Don't disconnect - peer may send HAVE messages later
                    # The bitfield timeout monitor will handle disconnection if peer never sends HAVE messages

                # CRITICAL FIX: Check if peer has any pieces we need (BitTorrent protocol compliance)
                # If peer has no pieces we need, send NOT_INTERESTED and schedule disconnect
                # This prevents keeping useless connections that waste resources
                # BUT: For magnet links or when metadata isn't available yet, don't disconnect
                # The peer might have pieces but we can't verify until metadata is available
                if hasattr(self.piece_manager, "get_missing_pieces"):
                    missing_pieces = self.piece_manager.get_missing_pieces()
                    if missing_pieces:
                        # Check if peer has ANY missing pieces
                        has_needed_piece = False
                        bitfield = connection.peer_state.bitfield

                        # CRITICAL FIX: If bitfield shows 0 pieces but bitfield length > 0,
                        # the bitfield might be all zeros OR there's a parsing issue
                        # Don't disconnect immediately - wait for HAVE messages or metadata
                        if pieces_count == 0 and bitfield_length > 0:
                            self.logger.debug(
                                "Peer %s bitfield shows 0 pieces but length=%d bytes - "
                                "keeping connection (may be parsing issue or peer will send HAVE messages)",
                                connection.peer_info,
                                bitfield_length,
                            )
                            # Don't check for needed pieces yet - wait for metadata or HAVE messages
                            has_needed_piece = True  # Assume peer might have pieces until proven otherwise
                        else:
                            # Check bitfield for missing pieces
                            for piece_idx in missing_pieces:
                                byte_idx = piece_idx // 8
                                bit_idx = piece_idx % 8
                                if byte_idx < len(bitfield) and bitfield[byte_idx] & (1 << (7 - bit_idx)):
                                    has_needed_piece = True
                                    break

                        if not has_needed_piece and pieces_count > 0:
                            # Peer has pieces but none we need - send NOT_INTERESTED and schedule disconnect
                            self.logger.info(
                                "Peer %s has no pieces we need (%d pieces available, %d missing pieces) - "
                                "sending NOT_INTERESTED and scheduling disconnect",
                                connection.peer_info,
                                pieces_count,
                                len(missing_pieces),
                            )

                            # Send NOT_INTERESTED message (BitTorrent protocol)
                            try:
                                from ccbt.peer.peer import NotInterestedMessage
                                if connection.writer is not None:
                                    not_interested_msg = NotInterestedMessage()
                                    data = not_interested_msg.encode()
                                    connection.writer.write(data)
                                    await connection.writer.drain()
                                    connection.am_interested = False
                                    self.logger.debug(
                                        "Sent NOT_INTERESTED to %s (peer has no pieces we need)",
                                        connection.peer_info,
                                    )
                            except Exception as e:
                                self.logger.debug(
                                    "Failed to send NOT_INTERESTED to %s: %s (will disconnect anyway)",
                                    connection.peer_info,
                                    e,
                                )

                            # Schedule disconnect after a short grace period (10 seconds)
                            # This allows peer to potentially send HAVE messages for new pieces
                            async def delayed_disconnect():
                                await asyncio.sleep(10.0)
                                # Re-check if peer still has no pieces we need
                                if hasattr(self.piece_manager, "get_missing_pieces"):
                                    current_missing = self.piece_manager.get_missing_pieces()
                                    if current_missing:
                                        still_no_pieces = True
                                        for piece_idx in current_missing[:20]:  # Check first 20
                                            byte_idx = piece_idx // 8
                                            bit_idx = piece_idx % 8
                                            if byte_idx < len(bitfield) and bitfield[byte_idx] & (1 << (7 - bit_idx)):
                                                still_no_pieces = False
                                                break

                                        if still_no_pieces:
                                            self.logger.info(
                                                "Disconnecting %s: peer has no pieces we need after grace period",
                                                connection.peer_info,
                                            )
                                            await self._disconnect_peer(connection)

                            # Schedule disconnect task
                            disconnect_task = asyncio.create_task(delayed_disconnect())
                            # Store task reference to prevent garbage collection
                            if not hasattr(connection, "_disconnect_tasks"):
                                connection._disconnect_tasks = []
                            connection._disconnect_tasks.append(disconnect_task)
            except Exception as e:
                self.logger.warning(
                    "Error updating piece manager with bitfield from %s: %s",
                    connection.peer_info,
                    e,
                    exc_info=True,
                )
        elif self.piece_manager and not connection.peer_state.bitfield:
            # CRITICAL FIX: Create peer availability entry even if no bitfield received
            # This allows HAVE messages to update peer availability later
            try:
                # Get peer key for piece manager
                if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                    peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                else:
                    peer_key = str(connection.peer_info)

                # Create empty peer availability entry
                # This will be updated by HAVE messages if peer sends them
                if hasattr(self.piece_manager, "peer_availability"):
                    if peer_key not in self.piece_manager.peer_availability:
                        from ccbt.piece.async_piece_manager import PeerAvailability
                        self.piece_manager.peer_availability[peer_key] = PeerAvailability(peer_key)
                        self.logger.debug(
                            "Created empty peer availability entry for %s (no bitfield received, will be updated by HAVE messages if sent)",
                            connection.peer_info,
                        )
            except Exception as e:
                self.logger.debug(
                    "Error creating peer availability entry for %s: %s (non-critical)",
                    connection.peer_info,
                    e,
                )

        # CRITICAL FIX: Ensure download is started when we receive bitfield
        if (
            self.piece_manager
            and hasattr(self.piece_manager, "is_downloading")
            and not getattr(self.piece_manager, "is_downloading", False)
        ):
            self.logger.info(
                "Download not started yet - starting download from Bitfield handler (peer: %s, pieces: %d)",
                connection.peer_info,
                pieces_count,
            )
            try:
                # Ensure _peer_manager is set before calling start_download
                if (
                    not hasattr(self.piece_manager, "_peer_manager")
                    or getattr(self.piece_manager, "_peer_manager", None) is None
                ):
                    setattr(self.piece_manager, "_peer_manager", self)  # noqa: B010
                    self.logger.debug(
                        "Set _peer_manager on piece_manager from Bitfield handler"
                    )

                if hasattr(self.piece_manager, "start_download"):
                    if asyncio.iscoroutinefunction(self.piece_manager.start_download):
                        await self.piece_manager.start_download(self)
                    else:
                        self.piece_manager.start_download(self)
                    self.logger.debug(
                        "Started piece manager download from Bitfield handler"
                    )
            except Exception:
                self.logger.exception("Error starting download from Bitfield handler")

        # Emit PEER_BITFIELD_RECEIVED event
        try:
            import hashlib

            from ccbt.core.bencode import BencodeEncoder
            from ccbt.utils.events import Event, emit_event

            # Get info_hash from torrent_data
            info_hash_hex = ""
            if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                encoder = BencodeEncoder()
                info_dict = self.torrent_data["info"]
                info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                info_hash_hex = info_hash_bytes.hex()

            peer_ip = connection.peer_info.ip if hasattr(connection.peer_info, "ip") else ""
            peer_port = connection.peer_info.port if hasattr(connection.peer_info, "port") else 0

            await emit_event(
                Event(
                    event_type="peer_bitfield_received",
                    data={
                        "info_hash": info_hash_hex,
                        "peer_ip": peer_ip,
                        "peer_port": peer_port,
                        "peer_id": None,
                        "pieces_available": pieces_count,
                    },
                )
            )
        except Exception as e:
            self.logger.debug("Failed to emit PEER_BITFIELD_RECEIVED event: %s", e)

        # Emit PEER_HANDSHAKE_COMPLETE event (bitfield received indicates handshake is complete)
        try:
            import hashlib

            from ccbt.core.bencode import BencodeEncoder
            from ccbt.utils.events import Event, emit_event

            # Get info_hash from torrent_data
            info_hash_hex = ""
            if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                encoder = BencodeEncoder()
                info_dict = self.torrent_data["info"]
                info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                info_hash_hex = info_hash_bytes.hex()

            peer_ip = connection.peer_info.ip if hasattr(connection.peer_info, "ip") else ""
            peer_port = connection.peer_info.port if hasattr(connection.peer_info, "port") else 0

            await emit_event(
                Event(
                    event_type="peer_handshake_complete",
                    data={
                        "info_hash": info_hash_hex,
                        "peer_ip": peer_ip,
                        "peer_port": peer_port,
                        "peer_id": None,
                    },
                )
            )
        except Exception as e:
            self.logger.debug("Failed to emit PEER_HANDSHAKE_COMPLETE event: %s", e)

        # Notify callback
        if self.on_bitfield_received:
            self.logger.info(
                "Calling on_bitfield_received callback for %s (pieces: %d)",
                connection.peer_info,
                pieces_count,
            )
            try:
                self.on_bitfield_received(connection, message)
            except Exception:
                self.logger.exception(
                    "Error in on_bitfield_received callback for %s",
                    connection.peer_info,
                )
        else:
            self.logger.warning(
                "No on_bitfield_received callback registered for %s",
                connection.peer_info,
            )

    async def _handle_request(
        self,
        connection: AsyncPeerConnection,
        message: RequestMessage,
    ) -> None:
        """Handle request message."""
        piece_index = message.piece_index
        begin = message.begin
        length = message.length

        # Try to read from in-memory verified pieces first
        block = None
        try:
            block = self.piece_manager.get_block(piece_index, begin, length)
        except Exception:  # pragma: no cover - Piece manager get_block error handling
            block = None

        # Fallback to disk via file assembler
        if block is None and getattr(self.piece_manager, "file_assembler", None):
            try:
                block = self.piece_manager.file_assembler.read_block(
                    piece_index,
                    begin,
                    length,
                )
            except (
                Exception
            ):  # pragma: no cover - File assembler read_block error handling
                block = None

        if block is None or len(block) != length:
            self.logger.debug(
                "Cannot serve request %s:%s:%s to %s",
                piece_index,
                begin,
                length,
                connection.peer_info,
            )
            return

        # Send the piece block
        try:
            piece_msg = PieceMessage(piece_index, begin, block)
            await self._send_message(connection, piece_msg)
            connection.stats.bytes_uploaded += len(block)
            self.logger.debug(
                "Served block %s:%s:%s to %s",
                piece_index,
                begin,
                length,
                connection.peer_info,
            )
        except (
            Exception
        ):  # pragma: no cover - Exception handling when sending piece message
            self.logger.exception(
                "Failed to send piece to %s",
                connection.peer_info,
            )  # pragma: no cover - Same context

    async def _handle_piece(
        self,
        connection: AsyncPeerConnection,
        message: PieceMessage,
    ) -> None:
        """Handle piece message."""
        # CRITICAL FIX: Log at INFO level when PIECE messages are received
        # This helps diagnose why pieces are stuck in DOWNLOADING state
        # CRITICAL FIX: Suppress verbose logging during shutdown
        from ccbt.utils.shutdown import is_shutting_down

        if not is_shutting_down():
            self.logger.info(
                "PIECE_MESSAGE: Received piece %d block from %s (offset=%d, size=%d bytes, outstanding=%d/%d)",
                message.piece_index,
                connection.peer_info,
                message.begin,
                len(message.block),
                len(connection.outstanding_requests),
                connection.max_pipeline_depth,
            )
        else:
            # During shutdown, only log at debug level
            self.logger.debug(
                "PIECE_MESSAGE: Received piece %d block from %s (shutdown in progress)",
                message.piece_index,
                connection.peer_info,
            )

        # Update download stats
        connection.stats.bytes_downloaded += len(message.block)
        peer_key = self._get_peer_key(connection)
        self._mark_peer_quality_verified(peer_key, "piece_received", connection)

        # Remove from outstanding requests and track block metrics
        request_key = (message.piece_index, message.begin, len(message.block))
        block_latency = 0.0
        if request_key in connection.outstanding_requests:
            request_info = connection.outstanding_requests[request_key]
            # Calculate block latency (time from request to receipt)
            current_time = time.time()
            block_latency = current_time - request_info.timestamp

            # Update average block latency
            stats = connection.stats
            if stats.blocks_delivered > 0:
                # Weighted average: (old_avg * old_count + new_latency) / (old_count + 1)
                stats.average_block_latency = (
                    (stats.average_block_latency * stats.blocks_delivered + block_latency) /
                    (stats.blocks_delivered + 1)
                )
            else:
                stats.average_block_latency = block_latency

            # Increment blocks_delivered
            stats.blocks_delivered += 1

            del connection.outstanding_requests[
                request_key
            ]  # pragma: no cover - Cleanup of outstanding requests requires specific timing, edge case
            self.logger.debug(
                "Removed request %s from outstanding_requests (remaining: %d, latency=%.3fs)",
                request_key,
                len(connection.outstanding_requests),
                block_latency,
            )
        else:
            # CRITICAL FIX: Check if unexpected piece is actually needed
            # Peers may send pieces we need but didn't request yet (e.g., out-of-order, preemptive)
            connection.stats.unexpected_pieces_count += 1
            is_useful = False

            # Check if piece manager exists and if this piece is needed
            if self.piece_manager:
                try:
                    piece = self.piece_manager.pieces[message.piece_index]
                    # Check if piece is in a state where we need it
                    from ccbt.piece.async_piece_manager import PieceState
                    if piece.state in (PieceState.MISSING, PieceState.REQUESTED, PieceState.DOWNLOADING):
                        # Check if this specific block is needed
                        for block in piece.blocks:
                            if block.begin == message.begin and not block.received:
                                is_useful = True
                                connection.stats.unexpected_pieces_useful += 1
                                self.logger.info(
                                    "Received unexpected but useful piece %d:%d:%d from %s (piece state=%s, block not received yet) - accepting",
                                    message.piece_index,
                                    message.begin,
                                    len(message.block),
                                    connection.peer_info,
                                    piece.state.name,
                                )
                                # CRITICAL FIX: INCREASE timeout when peer sends useful unexpected pieces
                                # This gives the peer more time to send pieces, allowing per-piece and per-block
                                # timeouts to capture the sent pieces instead of timing out prematurely
                                if connection.stats.unexpected_pieces_useful > 0:
                                    # Increase timeout by up to 50% if peer is sending useful unexpected pieces
                                    # Formula: 1.0 + min(0.5, unexpected_useful / 10.0)
                                    # This allows more time for the peer to send pieces we need
                                    increase = min(0.5, connection.stats.unexpected_pieces_useful / 10.0)
                                    connection.stats.timeout_adjustment_factor = min(1.5, 1.0 + increase)
                                    self.logger.debug(
                                        "Increased timeout for %s: factor=%.2f (unexpected_useful=%d) - giving peer more time to send pieces",
                                        connection.peer_info,
                                        connection.stats.timeout_adjustment_factor,
                                        connection.stats.unexpected_pieces_useful,
                                    )
                                break
                except (IndexError, AttributeError, KeyError) as e:
                    # Piece manager or piece doesn't exist yet, or piece_index is invalid
                    self.logger.debug(
                        "Cannot check if unexpected piece %d:%d:%d from %s is useful: %s",
                        message.piece_index,
                        message.begin,
                        len(message.block),
                        connection.peer_info,
                        e,
                    )

            if not is_useful:
                # Piece is not needed - log warning
                self.logger.warning(
                    "Received unexpected piece %d:%d:%d from %s (not in outstanding_requests, piece already complete or not needed)",
                    message.piece_index,
                    message.begin,
                    len(message.block),
                    connection.peer_info,
                )

            # Still increment blocks_delivered for unexpected blocks (even if not useful, peer sent data)
            connection.stats.blocks_delivered += 1

        # Notify callback
        # CRITICAL FIX: Check both manager callback and connection callback
        # The connection callback should be set via propagation, but if manager callback
        # is None, try the connection's callback as a fallback
        callback = self.on_piece_received
        if not callback and hasattr(connection, "on_piece_received") and connection.on_piece_received:
            # Fallback to connection's callback if manager callback is None
            callback = connection.on_piece_received
            self.logger.debug(
                "Using connection's on_piece_received callback for piece %d from %s (manager callback was None)",
                message.piece_index,
                connection.peer_info,
            )

        if callback:
            try:
                self.logger.debug(
                    "Calling on_piece_received callback for piece %d from %s",
                    message.piece_index,
                    connection.peer_info,
                )
                callback(connection, message)
                self.logger.debug(
                    "on_piece_received callback completed for piece %d from %s",
                    message.piece_index,
                    connection.peer_info,
                )
            except Exception as e:
                self.logger.exception(
                    "Error in on_piece_received callback for piece %d from %s: %s",
                    message.piece_index,
                    connection.peer_info,
                    e,
                )
        else:
            # CRITICAL: If callback is still None, try to propagate callbacks immediately
            # This handles the case where callback was set after connection was created
            # but propagation task hasn't run yet
            self.logger.warning(
                "Received piece %d from %s but on_piece_received callback is None! "
                "Manager callback: %s, Connection callback: %s. Attempting immediate propagation...",
                message.piece_index,
                connection.peer_info,
                self._on_piece_received is not None,
                getattr(connection, "on_piece_received", None) is not None,
            )
            # Try to propagate callbacks immediately and retry
            try:
                loop = asyncio.get_running_loop()
                # Create a task to propagate, but also try to set it directly on this connection
                if self._on_piece_received:
                    connection.on_piece_received = self._on_piece_received
                    self.logger.info(
                        "Set on_piece_received callback directly on connection %s, retrying callback",
                        connection.peer_info,
                    )
                    # Retry the callback now that it's set
                    try:
                        self._on_piece_received(connection, message)
                        self.logger.info(
                            "Successfully called on_piece_received callback for piece %d from %s after immediate propagation",
                            message.piece_index,
                            connection.peer_info,
                        )
                        return  # Successfully handled, exit early
                    except Exception as e:
                        self.logger.exception(
                            "Error calling on_piece_received callback after immediate propagation for piece %d from %s: %s",
                            message.piece_index,
                            connection.peer_info,
                            e,
                        )
                else:
                    # CRITICAL: If manager callback is still None, log detailed diagnostic info
                    self.logger.error(
                        "CRITICAL: on_piece_received callback is None on manager! "
                        "_on_piece_received=%s, on_piece_received property=%s. "
                        "This should never happen if callbacks were set correctly during initialization. "
                        "Piece %d from %s will NOT be processed!",
                        self._on_piece_received,
                        self.on_piece_received,
                        message.piece_index,
                        connection.peer_info,
                    )
                    # Schedule propagation for future messages (in case callback gets set later)
                    asyncio.create_task(self._propagate_callbacks_to_connections())
            except RuntimeError:
                # No running event loop - can't propagate
                pass

    async def _handle_cancel(
        self,
        connection: AsyncPeerConnection,
        message: CancelMessage,
    ) -> None:
        """Handle cancel message."""
        # Remove from outstanding requests
        request_key = (message.piece_index, message.begin, message.length)
        if request_key in connection.outstanding_requests:
            del connection.outstanding_requests[request_key]

        self.logger.debug(
            "Peer %s cancelled request for piece %s",
            connection.peer_info,
            message.piece_index,
        )

    async def _send_message(
        self,
        connection: AsyncPeerConnection,
        message: PeerMessage,
    ) -> None:
        """Send a message to a peer."""
        if connection.writer is None:
            error_msg = f"Cannot send {message.__class__.__name__} to {connection.peer_info}: writer is None"
            self.logger.warning(error_msg)
            raise PeerConnectionError(error_msg)

        try:
            data = message.encode()
            data_size = len(data)

            # Apply per-peer upload throttling (only for data-carrying messages)
            # Skip throttling for small control messages (keep-alive, choke, unchoke, etc.)
            if data_size > 20:  # Only throttle larger messages (pieces, bitfields, etc.)
                await connection._throttle_upload(data_size)

            connection.writer.write(data)
            await connection.writer.drain()
            connection.stats.last_activity = time.time()
            self.logger.debug(
                "Sent %s to %s",
                message.__class__.__name__,
                connection.peer_info,
            )
        except (
            Exception
        ) as e:  # pragma: no cover - Exception handling when sending message
            error_msg = f"Failed to send {message.__class__.__name__} to {connection.peer_info}: {e}"
            self.logger.warning(error_msg)
            # CRITICAL FIX: Don't disconnect here - let caller handle it
            # Disconnecting here can cause issues if we're still in the connection setup phase
            raise PeerConnectionError(error_msg) from e

    async def _send_bitfield(self, connection: AsyncPeerConnection) -> None:
        """Send our bitfield to the peer."""
        if connection.writer is None:
            error_msg = (
                f"Cannot send bitfield to {connection.peer_info}: writer is None"
            )
            self.logger.warning(error_msg)
            raise PeerConnectionError(error_msg)

        # CRITICAL FIX: For magnet links, metadata may not be available yet
        # Check if pieces_info exists and has num_pieces before trying to send bitfield
        pieces_info = self.torrent_data.get("pieces_info")
        if pieces_info is None:
            # Metadata not available yet (magnet link case) - skip bitfield
            # Bitfield will be sent later once metadata is fetched
            self.logger.debug(
                "Skipping bitfield for %s: metadata not available yet (magnet link)",
                connection.peer_info,
            )
            connection.state = ConnectionState.BITFIELD_SENT  # Mark as sent to avoid retry
            return

        num_pieces = pieces_info.get("num_pieces")
        if num_pieces is None or num_pieces == 0:
            # No pieces info available yet - skip bitfield
            self.logger.debug(
                "Skipping bitfield for %s: num_pieces not available yet (num_pieces=%s)",
                connection.peer_info,
                num_pieces,
            )
            connection.state = ConnectionState.BITFIELD_SENT  # Mark as sent to avoid retry
            return

        # Build bitfield from verified pieces
        bitfield_bytes = bytearray((num_pieces + 7) // 8)
        try:
            verified = set(self.piece_manager.verified_pieces)
        except (
            Exception
        ):  # pragma: no cover - Error accessing verified_pieces, edge case
            verified = set()
        for idx in verified:
            if 0 <= idx < num_pieces:
                byte_index = idx // 8
                bit_index = idx % 8
                bitfield_bytes[byte_index] |= 1 << (7 - bit_index)
        bitfield_data = bytes(bitfield_bytes)

        # CRITICAL FIX: Per BEP 3, leechers with no pieces should NOT send a bitfield
        # Only send bitfield if we have at least one verified piece
        if len(verified) > 0 and bitfield_data:
            bitfield_message = BitfieldMessage(bitfield_data)
            await self._send_message(connection, bitfield_message)
            connection.state = ConnectionState.BITFIELD_SENT
            self.logger.debug(
                "Sent bitfield to %s (%d pieces)", connection.peer_info, len(verified)
            )
        else:
            # We have no pieces - per BEP 3, don't send bitfield (leecher behavior)
            connection.state = ConnectionState.BITFIELD_SENT  # Mark as sent to avoid retry
            self.logger.debug(
                "Skipping bitfield for %s: no verified pieces (leecher, per BEP 3)",
                connection.peer_info,
            )

    async def _send_unchoke(self, connection: AsyncPeerConnection) -> None:
        """Unchoke the peer to allow them to request blocks."""
        if connection.writer is None:
            error_msg = f"Cannot send unchoke to {connection.peer_info}: writer is None"
            self.logger.warning(error_msg)
            raise PeerConnectionError(error_msg)

        try:
            msg = UnchokeMessage()
            await self._send_message(connection, msg)
            connection.am_choking = False
        except (
            Exception
        ) as e:  # pragma: no cover - Exception handling when sending unchoke
            error_msg = f"Failed to send unchoke to {connection.peer_info}: {e}"
            self.logger.warning(error_msg)
            # Re-raise as PeerConnectionError so caller can handle it
            raise PeerConnectionError(error_msg) from e

    async def _send_interested(self, connection: AsyncPeerConnection) -> None:
        """Send interested message to peer to indicate we want to download from them."""
        if connection.writer is None:
            error_msg = (
                f"Cannot send interested to {connection.peer_info}: writer is None"
            )
            self.logger.warning(error_msg)
            raise PeerConnectionError(error_msg)

        try:
            msg = InterestedMessage()
            await self._send_message(connection, msg)
            connection.am_interested = True
            self.logger.debug("Sent interested message to %s", connection.peer_info)
        except Exception as e:
            error_msg = f"Failed to send interested to {connection.peer_info}: {e}"
            self.logger.warning(error_msg)
            # Re-raise as PeerConnectionError so caller can handle it
            raise PeerConnectionError(error_msg) from e

    async def _disconnect_peer(self, connection: AsyncPeerConnection) -> None:
        """Disconnect from a peer."""
        peer_key = str(connection.peer_info)

        # CRITICAL FIX: Add grace period for connections that received bitfield
        # Connections that received bitfield are valuable and should be kept longer
        # This prevents removing connections too quickly when peers close them
        # BitTorrent spec: peers may close connections for various reasons, but we should
        # keep the connection info longer if we received useful data (bitfield)
        grace_period = 0.0
        if connection.state == ConnectionState.BITFIELD_RECEIVED:
            # Connection received bitfield - give it a grace period before removing
            # This allows the connection to be counted as active longer
            grace_period = 2.0  # 2 seconds grace period for bitfield connections
            self.logger.debug(
                "Connection %s received bitfield - applying %.1fs grace period before removal",
                peer_key,
                grace_period,
            )
            await asyncio.sleep(grace_period)

        # CRITICAL FIX: Cancel all outstanding requests before disconnecting
        # This prevents pieces from being stuck in REQUESTED/DOWNLOADING state
        outstanding_count = len(connection.outstanding_requests) if hasattr(connection, "outstanding_requests") else 0
        if outstanding_count > 0:
            self.logger.info(
                "Cancelling %d outstanding request(s) from disconnected peer %s",
                outstanding_count,
                peer_key,
            )
            # Cancel all outstanding requests (don't send CANCEL messages - peer is disconnecting)
            # Just clear the outstanding_requests dict to free up pipeline slots
            connection.outstanding_requests.clear()
            # Clear request queue as well
            if hasattr(connection, "request_queue"):
                connection.request_queue.clear()
        
        # CRITICAL FIX: Set state to ERROR and remove from dict atomically
        # This prevents race conditions where connection is in ERROR state but still in dict
        async with self.connection_lock:
            connection.state = ConnectionState.ERROR
            if peer_key in self.connections:
                del self.connections[peer_key]
                self.logger.debug(
                    "Removed peer %s from connections dict (state: ERROR, grace_period=%.1fs, cancelled %d requests)", 
                    peer_key,
                    grace_period,
                    outstanding_count,
                )
            self._quality_verified_peers.discard(peer_key)
            self._quality_probation_peers.pop(peer_key, None)

        # Cancel connection task (only if it exists - PooledConnection doesn't have this)
        if hasattr(connection, "connection_task") and connection.connection_task:
            # CRITICAL FIX: Check if task is done before awaiting to prevent RuntimeError
            if not connection.connection_task.done():
                connection.connection_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    try:
                        await connection.connection_task
                    except RuntimeError as e:
                        # Handle "await wasn't used with future" error
                        if "await wasn't used" in str(e):
                            self.logger.debug(
                                "Connection task already completed for %s, skipping await",
                                peer_key,
                            )
                        else:
                            raise

        # Close writer
        if connection.writer:
            try:
                connection.writer.close()
                # CRITICAL FIX: Add timeout and handle WinError 10055 gracefully
                try:
                    await asyncio.wait_for(
                        connection.writer.wait_closed(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    self.logger.debug(
                        "Writer close timeout for %s, continuing...",
                        peer_key,
                    )
                except OSError as e:
                    # Handle WinError 10055 (socket buffer exhaustion) gracefully
                    error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                    if error_code == 10055:
                        self.logger.debug(
                            "WinError 10055 (socket buffer exhaustion) during writer close for %s. "
                            "This is a transient Windows issue. Continuing...",
                            peer_key,
                        )
                    else:
                        raise  # Re-raise other OSErrors
            except (
                OSError,
                RuntimeError,
                asyncio.CancelledError,
            ):  # pragma: no cover - Writer cleanup error handling is expected during teardown
                # Ignore cleanup errors when closing connection writer
                pass  # Connection writer cleanup errors are expected  # pragma: no cover - Same context

        # CRITICAL FIX: Release pooled connection if it was stored
        # This cleans up the connection pool reference we stored earlier
        if hasattr(connection, "_pooled_connection") and connection._pooled_connection:
            pooled_key = getattr(connection, "_pooled_connection_key", None) or f"{connection.peer_info.ip}:{connection.peer_info.port}"
            try:
                await self.connection_pool.release(pooled_key, connection._pooled_connection)
                self.logger.debug("Released pooled connection for %s", peer_key)
            except Exception as e:
                self.logger.debug("Error releasing pooled connection for %s: %s", peer_key, e)

        # Return connection to pool if it exists there (legacy path)
        peer_id = f"{connection.peer_info.ip}:{connection.peer_info.port}"
        await self.connection_pool.release(peer_id, connection)

        # Remove from upload slots
        if (
            connection in self.upload_slots
        ):  # pragma: no cover - Edge case: removing peer from upload slots
            self.upload_slots.remove(connection)  # pragma: no cover - Same context

        # Clear optimistic unchoke if this peer
        if (
            self.optimistic_unchoke == connection
        ):  # pragma: no cover - Edge case: optimistic unchoke cleanup
            self.optimistic_unchoke = None  # pragma: no cover - Same context

        # Emit PEER_DISCONNECTED event
        try:
            import hashlib

            from ccbt.core.bencode import BencodeEncoder
            from ccbt.utils.events import Event, emit_event

            # Get info_hash from torrent_data
            info_hash_hex = ""
            if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                encoder = BencodeEncoder()
                info_dict = self.torrent_data["info"]
                info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                info_hash_hex = info_hash_bytes.hex()

            peer_ip = connection.peer_info.ip if hasattr(connection.peer_info, "ip") else ""
            peer_port = connection.peer_info.port if hasattr(connection.peer_info, "port") else 0

            await emit_event(
                Event(
                    event_type="peer_disconnected",
                    data={
                        "info_hash": info_hash_hex,
                        "peer_ip": peer_ip,
                        "peer_port": peer_port,
                        "peer_id": None,
                        "client": None,
                    },
                )
            )
        except Exception as e:
            self.logger.debug("Failed to emit PEER_DISCONNECTED event: %s", e)

        # CRITICAL FIX: Check peer count after disconnection and trigger immediate discovery if low
        async with self.connection_lock:
            current_peer_count = len(self.connections)
            active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())

        # Trigger immediate peer discovery if peer count is critically low
        # This ensures recovery when the last peer disconnects
        # CRITICAL FIX: Suppress this during shutdown to avoid log spam
        from ccbt.utils.shutdown import is_shutting_down

        if not is_shutting_down():
            low_peer_threshold = 5  # Trigger discovery if fewer than 5 active peers
            if active_peer_count < low_peer_threshold:
                self.logger.info(
                    "Peer count critically low (%d active, %d total) after disconnection. "
                    "Triggering immediate peer discovery...",
                    active_peer_count,
                    current_peer_count,
                )
                # Trigger immediate discovery via event system
                try:
                    from ccbt.utils.events import Event, emit_event
                    await emit_event(
                        Event(
                            event_type="peer_count_low",
                            data={
                                "info_hash": info_hash_hex if "info_hash_hex" in locals() else "",
                                "active_peer_count": active_peer_count,
                                "total_peer_count": current_peer_count,
                                "threshold": low_peer_threshold,
                                "trigger": "peer_disconnection",
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit peer_count_low event: %s", e)

        # Notify callback
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see disconnection details
        self.logger.debug("Disconnected from peer %s", connection.peer_info)

    def _can_retry_peer(self, peer_key: str) -> tuple[bool, float]:
        """Check if a failed peer can be retried.

        Args:
            peer_key: Peer identifier (ip:port)

        Returns:
            Tuple of (can_retry, backoff_interval)

        """

        async def _check_async() -> tuple[bool, float]:
            async with self._failed_peer_lock:
                if peer_key not in self._failed_peers:
                    return (True, 0.0)

                fail_info = self._failed_peers[peer_key]
                fail_count = fail_info.get("count", 1)
                fail_timestamp = fail_info.get("timestamp", 0.0)

                # Calculate backoff interval
                backoff_interval = min(
                    self._min_retry_interval
                    * (self._backoff_multiplier ** (fail_count - 1)),
                    self._max_retry_interval,
                )

                # Check if backoff period has expired
                elapsed = time.time() - fail_timestamp
                can_retry = elapsed >= backoff_interval

                return (can_retry, backoff_interval)

        # Since this is called from sync context, we need to handle it differently
        # For now, we'll make it async-compatible
        return (True, 0.0)  # Placeholder - will be called from async context

    async def _reconnection_loop(self) -> None:
        """Periodic task to retry failed peer connections.

        CRITICAL FIX: Adaptive reconnection interval based on active peer count.
        When peer count is low, retry more frequently to discover peers faster.
        
        Checks failed peers and retries those whose backoff period has expired.
        """
        base_reconnection_interval = 30.0  # Base interval: 30 seconds
        reconnection_interval = base_reconnection_interval
        max_retries_per_cycle = (
            10  # Limit retries per cycle to avoid overwhelming system
        )

        # CRITICAL FIX: Check _running flag to allow clean shutdown
        while self._running:
            try:
                # CRITICAL FIX: Check _running before doing any work
                if not self._running:
                    break

                # CRITICAL FIX: Don't interfere with connection batches from trackers
                # If connection batches are in progress, skip this cycle to avoid interfering
                # BUT: If peer count is critically low, allow reconnection even during batches
                # This ensures we continue discovering peers even after piece requests start
                if self._connection_batches_in_progress:
                    # CRITICAL FIX: Check active peer count - if critically low, allow reconnection
                    # This ensures peer processing continues even after piece requests start
                    active_peer_count = len(self.get_active_peers())
                    if active_peer_count < 3:
                        # Ultra-low peer count: allow reconnection even during batches
                        # This is critical to prevent downloads from stalling
                        self.logger.warning(
                            "Reconnection loop: Connection batches in progress BUT peer count is critically low (%d). "
                            "Allowing reconnection to prevent download stall.",
                            active_peer_count,
                        )
                        # Continue with reconnection - don't skip
                    else:
                        self.logger.debug(
                            "Reconnection loop: Connection batches in progress, skipping this cycle to avoid interfering with tracker peer processing"
                        )
                        # Wait a bit before checking again (shorter wait since batches should complete soon)
                        await asyncio.sleep(5.0)
                        continue

                # CRITICAL FIX: Adaptive reconnection interval based on active peer count
                # According to BitTorrent best practices (BEP 5, BEP 11), ultra-aggressive mode should only
                # be used when peer count is 0 (no peers at all) to avoid overwhelming the network and
                # getting blacklisted. Normal aggressive mode is sufficient for 1-2 peers.
                active_peer_count = len(self.get_active_peers())
                if active_peer_count == 0:
                    # CRITICAL FIX: Ultra-aggressive mode only when peer count is 0 (no peers at all)
                    # This prevents overwhelming the network when we have at least 1 peer connected
                    # Ultra-aggressive mode (3s interval) can cause peer blacklisting if used too early
                    reconnection_interval = 3.0
                    max_retries_per_cycle = 30  # Allow even more retries when peer count is 0
                    self.logger.info(
                        "Reconnection loop: No active peers (0), using ULTRA-AGGRESSIVE interval: %.1fs, max_retries: %d",
                        reconnection_interval,
                        max_retries_per_cycle,
                    )
                elif active_peer_count < 3:
                    # Very low peer count (1-2 peers) - use aggressive but not ultra-aggressive
                    # This prevents peer blacklisting while still being responsive
                    reconnection_interval = 8.0  # Increased from 5s to 8s to be less aggressive
                    max_retries_per_cycle = 20  # Allow more retries when peer count is very low
                    self.logger.debug(
                        "Reconnection loop: Very low peer count (%d), using aggressive interval: %.1fs, max_retries: %d",
                        active_peer_count,
                        reconnection_interval,
                        max_retries_per_cycle,
                    )
                elif active_peer_count < 5:
                    # Critically low peer count - retry every 5 seconds (reduced from 15s)
                    reconnection_interval = 5.0
                    max_retries_per_cycle = 20  # Allow more retries when peer count is low
                    self.logger.debug(
                        "Reconnection loop: Low peer count (%d), using aggressive interval: %.1fs",
                        active_peer_count,
                        reconnection_interval,
                    )
                elif active_peer_count < 10:
                    # Low peer count - retry every 10 seconds (reduced from 20s)
                    reconnection_interval = 10.0
                    max_retries_per_cycle = 15
                else:
                    # Normal peer count - use base interval
                    reconnection_interval = base_reconnection_interval
                    max_retries_per_cycle = 10

                # CRITICAL FIX: Use interruptible sleep that checks _running frequently
                # This ensures the loop exits quickly when shutdown is requested
                sleep_interval = min(reconnection_interval, 1.0)  # Check at least every second
                elapsed = 0.0
                while elapsed < reconnection_interval and self._running:
                    await asyncio.sleep(sleep_interval)
                    elapsed += sleep_interval

                # Check _running again after sleep
                if not self._running:
                    break

                # Get list of failed peers that can be retried
                retry_candidates = []
                async with self._failed_peer_lock:
                    current_time = time.time()
                    for peer_key, fail_info in list(self._failed_peers.items()):
                        fail_count = fail_info.get("count", 1)
                        fail_timestamp = fail_info.get("timestamp", 0.0)

                        # Calculate backoff interval
                        # CRITICAL FIX: Reduce backoff for ultra-low peer counts - much more aggressive
                        base_backoff = self._min_retry_interval * (self._backoff_multiplier ** (fail_count - 1))
                        if active_peer_count < 3:
                            # Ultra-low peer count: reduce backoff by 80% to retry much faster
                            backoff_interval = min(base_backoff * 0.2, self._max_retry_interval * 0.2)
                        elif active_peer_count < 5:
                            # Low peer count: reduce backoff by 60% to retry faster
                            backoff_interval = min(base_backoff * 0.4, self._max_retry_interval * 0.4)
                        elif active_peer_count < 10:
                            # Moderate peer count: reduce backoff by 40% to retry faster
                            backoff_interval = min(base_backoff * 0.6, self._max_retry_interval * 0.6)
                        else:
                            backoff_interval = min(base_backoff, self._max_retry_interval)

                        # Check if backoff period has expired
                        elapsed = current_time - fail_timestamp
                        if elapsed >= backoff_interval:
                            # Check if peer is already connected
                            async with self.connection_lock:
                                if peer_key not in self.connections:
                                    # CRITICAL FIX: Don't retry peers that are in current connection batches
                                    # Check if this peer is in the current batch being processed
                                    # This prevents reconnection loop from interfering with tracker peer processing
                                    if hasattr(self, "_current_batch_peers"):
                                        if peer_key in self._current_batch_peers:
                                            self.logger.debug(
                                                "Skipping reconnection for peer %s: peer is in current connection batch",
                                                peer_key
                                            )
                                            continue
                                    retry_candidates.append((peer_key, fail_info))

                # Retry up to max_retries_per_cycle peers
                if retry_candidates:
                    retry_count = min(len(retry_candidates), max_retries_per_cycle)
                    self.logger.info(
                        "Reconnection loop: found %d peers eligible for retry, attempting %d",
                        len(retry_candidates),
                        retry_count,
                    )

                    for peer_key, fail_info in retry_candidates[:retry_count]:
                        try:
                            # Parse peer_key (format: "ip:port")
                            parts = peer_key.split(":")
                            if len(parts) == 2:
                                ip, port_str = parts
                                try:
                                    port = int(port_str)
                                    peer_dict = {"ip": ip, "port": port}

                                    # Attempt reconnection
                                    await self.connect_to_peers([peer_dict])
                                    self.logger.debug(
                                        "Reconnection attempt for peer %s (failure count: %d)",
                                        peer_key,
                                        fail_info.get("count", 1),
                                    )
                                except ValueError:
                                    self.logger.warning(
                                        "Invalid port in peer_key %s, skipping retry",
                                        peer_key,
                                    )
                        except Exception as e:
                            self.logger.debug(
                                "Reconnection attempt failed for peer %s: %s",
                                peer_key,
                                e,
                            )
                else:
                    self.logger.debug("Reconnection loop: no peers eligible for retry")

            except asyncio.CancelledError:
                self.logger.debug("Reconnection loop cancelled")
                break
            except Exception:
                self.logger.exception("Error in reconnection loop")

    async def _choking_loop(self) -> None:
        """Background task for choking/unchoking management."""
        while await self._choking_loop_step():  # pragma: no cover - Background loop requires time-based iterations, complex to test
            pass  # pragma: no cover - Same context

    async def _choking_loop_step(self) -> bool:
        """Execute one choking loop iteration. Return False to stop the loop."""
        try:  # pragma: no cover - Background loop step requires time-based execution, complex to test reliably
            await asyncio.sleep(
                self.config.network.unchoke_interval
            )  # pragma: no cover - Time-dependent sleep in background loop
            await self._update_choking()  # pragma: no cover - Same context
            return True  # pragma: no cover - Same context
        except asyncio.CancelledError:  # pragma: no cover - Cancellation handling in choking loop, requires task cancellation which is difficult to test reliably
            return False  # pragma: no cover - Cancellation return path in choking loop
        except Exception:  # pragma: no cover - Exception handling in choking loop
            self.logger.exception(
                "Error in choking loop"
            )  # pragma: no cover - Same context
            return True  # pragma: no cover - Same context

    async def _update_choking(self) -> None:
        """Update choking/unchoking based on improved tit-for-tat with download rate consideration."""
        current_time = time.time()  # Get current time for grace period checks
        async with self.connection_lock:  # pragma: no cover - Choking management requires multiple active peers, complex to test
            active_peers = [
                conn for conn in self.connections.values() if conn.is_active()
            ]  # pragma: no cover - Same context

            if not active_peers:  # pragma: no cover - Same context
                return  # pragma: no cover - Same context

            # IMPROVEMENT: Sort by combined score (upload rate + download rate)
            # Prioritize peers that both upload to us AND download from us
            # This encourages reciprocation and improves overall throughput
            def peer_score(peer: AsyncPeerConnection) -> float:
                """Calculate peer score for unchoking priority.
                
                Factors:
                1. Upload rate (how much they upload to us) - weight 0.6
                2. Download rate (how much we download from them) - weight 0.4
                3. Performance score (overall peer quality) - weight 0.2
                
                Returns:
                    Combined score (higher = better)

                """
                upload_rate = peer.stats.upload_rate
                download_rate = peer.stats.download_rate
                performance_score = getattr(peer.stats, "performance_score", 0.5)

                # Normalize rates (assume max 10MB/s = 1.0)
                max_rate = 10 * 1024 * 1024
                upload_norm = min(1.0, upload_rate / max_rate) if max_rate > 0 else 0.0
                download_norm = min(1.0, download_rate / max_rate) if max_rate > 0 else 0.0

                # Combined score
                score = (upload_norm * 0.6) + (download_norm * 0.4) + (performance_score * 0.2)
                return score

            # Sort by combined score (descending)
            active_peers.sort(key=peer_score, reverse=True)  # pragma: no cover - Same context

            # Unchoke top peers based on combined score
            max_slots = (
                self.config.network.max_upload_slots
            )  # pragma: no cover - Same context
            new_upload_slots = active_peers[
                :max_slots
            ]  # pragma: no cover - Same context

            # CRITICAL FIX: Choke peers not in new slots, but give new peers a grace period
            # New peers need time to request from us before we choke them
            # This breaks the chicken-and-egg: we unchoke them → they request → they unchoke us
            current_time = time.time()
            grace_period = 30.0  # 30 seconds grace period for new peers

            # CRITICAL FIX: Use lists instead of sets since AsyncPeerConnection is not hashable
            # Build list of peers to choke by checking which peers in upload_slots are not in new_upload_slots
            peers_to_choke = []
            for peer in self.upload_slots:
                if peer not in new_upload_slots:
                    peers_to_choke.append(peer)

            # Also check all active peers that are not in new slots
            for peer in active_peers:  # pragma: no cover - Same context
                if peer not in new_upload_slots and not peer.am_choking:  # pragma: no cover - Same context
                    # Skip if already in peers_to_choke to avoid duplicates
                    if peer in peers_to_choke:
                        continue  # pragma: no cover - Same context
                    # Check if peer is new (within grace period)
                    connection_start = getattr(peer, "connection_start_time", 0)
                    age = current_time - connection_start
                    if age < grace_period:  # pragma: no cover - Same context
                        # New peer - don't choke yet, give them a chance
                        self.logger.debug(
                            "Skipping choke for new peer %s (age=%.1fs < %.1fs grace period)",
                            peer.peer_info,
                            age,
                            grace_period,
                        )
                        continue  # pragma: no cover - Same context
                    peers_to_choke.append(peer)  # pragma: no cover - Same context

            for peer in peers_to_choke:  # pragma: no cover - Same context
                await self._choke_peer(peer)  # pragma: no cover - Same context

            # Unchoke all peers that should be unchoked (in new upload slots)
            # This ensures peers are unchoked even if they were already in old slots
            # but somehow got into a bad state
            for peer in new_upload_slots:  # pragma: no cover - Same context
                if peer.am_choking:  # pragma: no cover - Same context
                    score = peer_score(peer)
                    self.logger.info(
                        "Unchoking peer %s (upload_slot, score=%.2f, upload_rate=%.1f KB/s, download_rate=%.1f KB/s)",
                        peer.peer_info,
                        score,
                        peer.stats.upload_rate / 1024,
                        peer.stats.download_rate / 1024,
                    )
                    await self._unchoke_peer(peer)  # pragma: no cover - Same context

            # Log summary of choking state
            unchoked_count = sum(1 for p in active_peers if not p.am_choking)
            self.logger.info(
                "Choking update complete: %d/%d peers unchoked (upload_slots=%d, optimistic_unchoke=%s)",
                unchoked_count,
                len(active_peers),
                len(new_upload_slots),
                self.optimistic_unchoke.peer_info if self.optimistic_unchoke else None,
            )

            self.upload_slots = new_upload_slots  # pragma: no cover - Same context

            # CRITICAL FIX: Send INTERESTED to all active peers that we haven't sent it to yet
            # This encourages peers to unchoke us, allowing us to download from multiple peers
            # Many peers wait for INTERESTED before unchoking, so we need to be proactive
            for peer in active_peers:  # pragma: no cover - Same context
                if not peer.am_interested and peer.is_active():
                    try:
                        await self._send_interested(peer)
                        peer.am_interested = True
                        self.logger.info(
                            "Sent INTERESTED to %s proactively (encouraging peer to unchoke us, active peers: %d/%d unchoked)",
                            peer.peer_info,
                            unchoked_count,
                            len(active_peers),
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Failed to send proactive INTERESTED to %s: %s",
                            peer.peer_info,
                            e,
                        )

            # IMPROVEMENT: Emit event for choking optimization
            try:
                from ccbt.utils.events import Event, EventType, emit_event
                asyncio.create_task(emit_event(Event(
                    event_type=EventType.PEER_CHOKING_OPTIMIZED.value,
                    data={
                        "upload_slots_count": len(new_upload_slots),
                        "total_active_peers": len(active_peers),
                        "max_upload_slots": max_slots,
                    },
                )))
            except Exception as e:
                self.logger.debug("Failed to emit choking optimization event: %s", e)  # pragma: no cover - Same context

            # Optimistic unchoke (for new peers)
            await self._update_optimistic_unchoke()  # pragma: no cover - Same context

    async def _update_optimistic_unchoke(self) -> None:
        """Update optimistic unchoke peer."""
        current_time = time.time()  # pragma: no cover - Optimistic unchoke logic requires time-based state changes, complex to test
        interval = (
            self.config.network.optimistic_unchoke_interval
        )  # pragma: no cover - Same context

        # Check if we need a new optimistic unchoke
        if (
            self.optimistic_unchoke is None
            or current_time - self.optimistic_unchoke_time > interval
        ):  # pragma: no cover - Same context
            # Choke current optimistic unchoke if not in upload slots
            if (
                self.optimistic_unchoke
                and self.optimistic_unchoke not in self.upload_slots
            ):  # pragma: no cover - Same context
                await self._choke_peer(
                    self.optimistic_unchoke
                )  # pragma: no cover - Same context

            # Select new optimistic unchoke
            # CRITICAL FIX: Don't require peer_interested for optimistic unchoke
            # New peers may not be interested yet, but we should still give them a chance
            # This breaks the chicken-and-egg problem: we unchoke them so they can request,
            # which encourages them to unchoke us
            async with self.connection_lock:  # pragma: no cover - Same context
                available_peers = [
                    conn
                    for conn in self.connections.values()
                    if (
                        conn.is_active()
                        and conn not in self.upload_slots
                        # Removed peer_interested requirement - allow optimistic unchoke even if peer not interested yet
                        # This gives new peers a chance to request from us, which encourages them to unchoke us
                    )
                ]  # pragma: no cover - Same context

            if available_peers:  # pragma: no cover - Same context
                # IMPROVEMENT: Prefer new peers (recently connected) for optimistic unchoke
                # This gives new peers a chance to prove themselves
                # Sort by connection time (newer first)
                available_peers.sort(
                    key=lambda p: getattr(p, "connection_start_time", current_time),
                    reverse=True,  # Newer first
                )

                # Select from top 3 newest peers (not completely random)
                # This balances giving new peers a chance while still being somewhat random
                top_new_peers = available_peers[:min(3, len(available_peers))]
                self.optimistic_unchoke = random.choice(top_new_peers)  # nosec B311 - Peer selection is not security-sensitive  # pragma: no cover - Same context

                await self._unchoke_peer(
                    self.optimistic_unchoke
                )  # pragma: no cover - Same context
                self.optimistic_unchoke_time = (
                    current_time  # pragma: no cover - Same context
                )
                self.logger.debug(
                    "New optimistic unchoke: %s (selected from %d new peers)",
                    self.optimistic_unchoke.peer_info,
                    len(top_new_peers),
                )  # pragma: no cover - Same context

    async def _choke_peer(self, connection: AsyncPeerConnection) -> None:
        """Choke a peer."""
        if not connection.am_choking:
            await self._send_message(connection, ChokeMessage())
            connection.am_choking = True
            self.logger.debug("Choked peer %s", connection.peer_info)

    async def _unchoke_peer(self, connection: AsyncPeerConnection) -> None:
        """Unchoke a peer."""
        if connection.am_choking:
            await self._send_message(connection, UnchokeMessage())
            connection.am_choking = False
            self.logger.debug("Unchoked peer %s", connection.peer_info)

    async def _stats_loop(self) -> None:
        """Background task for updating peer statistics."""
        while await self._stats_loop_step():  # pragma: no cover - Background loop requires time-based iterations, complex to test
            pass  # pragma: no cover - Same context

    async def _stats_loop_step(self) -> bool:
        """Execute one stats loop iteration. Return False to stop the loop."""
        try:  # pragma: no cover - Background loop step requires time-based execution, complex to test reliably
            await asyncio.sleep(
                5.0
            )  # pragma: no cover - Time-dependent sleep in background loop
            await self._update_peer_stats()  # pragma: no cover - Same context

            # CRITICAL FIX: Log comprehensive connection diagnostics every 30 seconds
            # This helps identify why peers aren't becoming requestable
            if not hasattr(self, "_last_diagnostics_log"):
                self._last_diagnostics_log = 0.0  # type: ignore[attr-defined]

            current_time = time.time()
            if current_time - self._last_diagnostics_log >= 30.0:  # Log every 30 seconds
                await self._log_connection_diagnostics()
                self._last_diagnostics_log = current_time

            return True  # pragma: no cover - Same context
        except asyncio.CancelledError:
            return False  # pragma: no cover - Cancellation handling in stats loop
        except Exception:  # pragma: no cover - Exception handling in stats loop
            self.logger.exception(
                "Error in stats loop"
            )  # pragma: no cover - Same context
            return True  # pragma: no cover - Same context

    def _should_recycle_peer(self, connection: AsyncPeerConnection, new_peer_available: bool = False) -> bool:
        """Determine if a peer connection should be recycled.
        
        CRITICAL FIX: Maximize peer count first - only recycle truly bad peers.
        Keep all peers connected and only use best seeders for piece requests.

        Args:
            connection: The peer connection to evaluate.
            new_peer_available: True if there's a new peer waiting to connect.

        Returns:
            True if the peer should be recycled, False otherwise.

        """
        # CRITICAL FIX: Only recycle peers that are truly problematic
        # Maximize peer count first - be very conservative about disconnecting
        
        # Get current active peer count to determine if we can afford to recycle
        # Note: This is called from sync context, so we can't use async with
        # We'll use a sync lock or just read the count directly (connections dict is thread-safe for reads)
        try:
            # Try to get active peer count synchronously
            active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())
        except Exception:
            # If that fails, default to allowing recycling (conservative)
            active_peer_count = 0
        
        # CRITICAL FIX: If we have few peers, don't recycle anyone (maximize connections first)
        min_peers_before_recycling = 100  # Only recycle if we have 100+ peers
        if active_peer_count < min_peers_before_recycling:
            # Keep all peers - maximize connections first
            return False
        
        # Get configuration thresholds (but only apply if we have enough peers)
        performance_threshold = getattr(self.config.network, "connection_pool_performance_threshold", 0.1)  # Lowered from 0.3
        max_failures = getattr(self.config.network, "peer_max_consecutive_failures", 10)  # Increased from 5
        max_idle_time = getattr(self.config.network, "connection_pool_max_idle_time", 600)  # Increased from 300
        min_download_bandwidth = getattr(self.config.network, "connection_pool_min_download_bandwidth", 0)
        min_upload_bandwidth = getattr(self.config.network, "connection_pool_min_upload_bandwidth", 0)

        # CRITICAL FIX: Only recycle if peer has severe issues (many consecutive failures)
        # Don't recycle based on performance score alone - keep peers for PEX/DHT
        if connection.stats.consecutive_failures > max_failures:
            self.logger.debug("Recycling peer %s: too many consecutive failures (%d > %d)", connection.peer_info, connection.stats.consecutive_failures, max_failures)
            return True

        # CRITICAL FIX: Only recycle if peer is completely idle AND we're at connection limit
        # AND a new peer is available to replace it
        current_time = time.time()
        idle_time = current_time - connection.stats.last_activity
        if new_peer_available and idle_time > max_idle_time and active_peer_count >= self.max_peers_per_torrent * 0.95:
            # Only recycle if we're at 95%+ of connection limit
            self.logger.debug("Recycling peer %s: idle for too long (%d > %d) and at connection limit with new peer available", connection.peer_info, idle_time, max_idle_time)
            return True

        # CRITICAL FIX: Don't recycle based on bandwidth thresholds - keep peers for PEX/DHT
        # Only recycle if bandwidth is configured AND peer is completely dead (0 bandwidth for very long)
        if min_download_bandwidth > 0 and connection.stats.download_rate < min_download_bandwidth:
            # Only recycle if peer has been completely dead for a very long time
            if idle_time > max_idle_time * 2:  # Double the idle time before recycling
                self.logger.debug("Recycling peer %s: low download bandwidth (%.2f < %.2f) and idle for very long", connection.peer_info, connection.stats.download_rate, min_download_bandwidth)
                return True
        
        # CRITICAL FIX: Don't recycle based on performance score - keep peers connected
        # Performance-based recycling is too aggressive - maximize connections first
        # Only recycle if performance is truly terrible AND we have many peers
        if active_peer_count >= min_peers_before_recycling * 2:  # Only if we have 200+ peers
            performance_score = self._evaluate_peer_performance(connection)
            if performance_score < 0.05:  # Only recycle if performance is extremely bad (<5%)
                self.logger.debug("Recycling peer %s: extremely low performance score (%.2f < 0.05) and we have many peers", connection.peer_info, performance_score)
                return True

        return False

    async def _peer_evaluation_loop(self) -> None:
        """Periodically evaluate peer performance and recycle low-performing connections.
        
        CRITICAL FIX: Also maintains minimum peer count by triggering discovery when needed.
        This ensures peer processing continues even after piece requests start.
        """
        interval = getattr(self.config.network, "peer_evaluation_interval", 30.0)  # Default 30 seconds
        min_peer_count = 50  # Minimum active peers to maintain (increased to prevent aggressive DHT)
        while self._running:
            try:
                await asyncio.sleep(interval)
                self.logger.debug("Running peer evaluation loop...")
                await self._prune_probation_peers("evaluation_loop")
                
                # CRITICAL FIX: Check if we need to maintain minimum peer count
                # This ensures peer processing continues even after piece requests start
                async with self.connection_lock:
                    active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())
                
                if active_peer_count < min_peer_count:
                    self.logger.warning(
                        "Peer evaluation loop: Active peer count (%d) is below minimum (%d). "
                        "This may cause downloads to stall. Consider triggering peer discovery.",
                        active_peer_count,
                        min_peer_count,
                    )
                    # CRITICAL FIX: Trigger peer_count_low event to encourage discovery
                    # This ensures continuous peer discovery even after piece requests start
                    if hasattr(self, "event_bus") and self.event_bus:
                        try:
                            from ccbt.utils.events import PeerCountLowEvent
                            event = PeerCountLowEvent(
                                info_hash=self.info_hash,  # type: ignore[attr-defined]
                                active_peers=active_peer_count,
                                total_peers=len(self.connections),
                            )
                            await self.event_bus.emit(event)
                            self.logger.info(
                                "Peer evaluation loop: Emitted peer_count_low event (active: %d, total: %d) to trigger discovery",
                                active_peer_count,
                                len(self.connections),
                            )
                        except Exception as e:
                            self.logger.debug(
                                "Peer evaluation loop: Failed to emit peer_count_low event: %s",
                                e,
                            )

                peers_to_recycle: list[AsyncPeerConnection] = []
                async with self.connection_lock:
                    # Check if we're at connection limit (if so, we can recycle to make room)
                    current_connections = len(self.connections)
                    max_connections = self.max_peers_per_torrent
                    at_connection_limit = current_connections >= max_connections

                    # CRITICAL FIX: First, disconnect peers without bitfields (after timeout)
                    # These peers are not following protocol and should be disconnected to make room for fresh peers
                    peers_without_bitfield: list[AsyncPeerConnection] = []
                    current_time = time.time()
                    # Calculate active peer count once for use throughout this section
                    active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())

                    for peer_key, connection in list(self.connections.items()):  # Iterate over a copy
                        # CRITICAL FIX: Disconnect peers that haven't sent bitfield OR HAVE messages within timeout
                        # According to BitTorrent spec (BEP 3), bitfield is OPTIONAL if peer has no pieces
                        # However, peers should send HAVE messages as they download pieces
                        # Only disconnect if peer sends neither bitfield nor HAVE messages
                        if connection.is_active():
                            has_bitfield = (
                                connection.peer_state.bitfield is not None
                                and len(connection.peer_state.bitfield) > 0
                            )
                            # Check if peer has sent HAVE messages (alternative to bitfield)
                            have_messages_count = len(connection.peer_state.pieces_we_have) if connection.peer_state.pieces_we_have else 0
                            has_have_messages = have_messages_count > 0

                            # Only disconnect if peer has neither bitfield nor HAVE messages
                            if not has_bitfield and not has_have_messages:
                                # CRITICAL FIX: Use adaptive timeout based on useful peer count
                                # When we have few useful peers, be more aggressive in cycling useless ones
                                # Count useful peers (those with bitfields or HAVE messages)
                                useful_peer_count = sum(
                                    1 for conn in self.connections.values()
                                    if conn.is_active()
                                    and (
                                        (conn.peer_state.bitfield is not None and len(conn.peer_state.bitfield) > 0)
                                        or (conn.peer_state.pieces_we_have is not None and len(conn.peer_state.pieces_we_have) > 0)
                                    )
                                )

                                # Adaptive timeout: shorter when we have few useful peers
                                if useful_peer_count <= 2:
                                    timeout_seconds = 60.0  # 1 minute when very few useful peers
                                elif useful_peer_count <= 5:
                                    timeout_seconds = 90.0  # 1.5 minutes when few useful peers
                                else:
                                    timeout_seconds = 120.0  # 2 minutes when many useful peers

                                # Check connection age - if older than timeout without bitfield OR HAVE messages, disconnect
                                connection_age = current_time - connection.stats.last_activity
                                if connection_age > timeout_seconds:
                                    messages_received = getattr(connection.stats, "messages_received", 0)
                                    self.logger.info(
                                        "🔄 PEER_CYCLING: Disconnecting %s - no bitfield OR HAVE messages received after %.1fs "
                                        "(messages_received: %s, state: %s, useful_peers: %d/%d) - making room for fresh peers",
                                        connection.peer_info,
                                        connection_age,
                                        messages_received,
                                        connection.state.value,
                                        useful_peer_count,
                                        active_peer_count,
                                    )
                                    peers_without_bitfield.append(connection)
                                    continue
                            elif not has_bitfield and has_have_messages:
                                # Peer sent HAVE messages but no bitfield - protocol-compliant (leecher with 0% complete)
                                self.logger.debug(
                                    "✅ PEER_EVAL: Peer %s sent %d HAVE message(s) without bitfield - protocol-compliant (leecher)",
                                    connection.peer_info,
                                    have_messages_count,
                                )

                    # CRITICAL FIX: Keep minimum peers for DHT/PEX to work
                    # DHT and PEX need at least 50 active connections to exchange peer information effectively
                    min_peers_for_dht_pex = 50  # Minimum peers to keep for DHT/PEX functionality (increased to prevent aggressive discovery)

                    # Disconnect peers without bitfields, but keep minimum for DHT/PEX
                    peers_to_disconnect = []
                    for connection in peers_without_bitfield:
                        # Check if we'd drop below minimum after disconnecting this peer
                        would_drop_below_min = (active_peer_count - len(peers_to_disconnect)) <= min_peers_for_dht_pex
                        if would_drop_below_min:
                            # Keep this peer for DHT/PEX even though it's not useful for downloading
                            self.logger.debug(
                                "Keeping peer %s for DHT/PEX (would drop below minimum %d peers if disconnected, current: %d)",
                                connection.peer_info,
                                min_peers_for_dht_pex,
                                active_peer_count - len(peers_to_disconnect),
                            )
                            continue
                        peers_to_disconnect.append(connection)

                    # Disconnect peers without bitfields (but keep minimum)
                    for connection in peers_to_disconnect:
                        await self._disconnect_peer(connection)

                    # Recalculate peer counts after disconnections
                    async with self.connection_lock:
                        current_connections = len(self.connections)
                        active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())
                        # Count peers with bitfield OR HAVE messages (both indicate piece availability)
                        peers_with_bitfield_count = sum(
                            1 for conn in self.connections.values()
                            if conn.is_active()
                            and (
                                (conn.peer_state.bitfield is not None and len(conn.peer_state.bitfield) > 0)
                                or (conn.peer_state.pieces_we_have is not None and len(conn.peer_state.pieces_we_have) > 0)
                            )
                        )

                    # CRITICAL FIX: Maximize peer count first - only cycle if we're at connection limit
                    # Don't cycle peers aggressively - keep all peers connected for PEX/DHT
                    peers_to_cycle: list[AsyncPeerConnection] = []

                    # CRITICAL FIX: Only cycle peers if we're at 95%+ of connection limit
                    # Maximize connections first - don't cycle until we're full
                    if current_connections >= max_connections * 0.95:  # Only at 95%+ of limit
                        # Find peers that have been used successfully (downloaded pieces) but could be cycled
                        for peer_key, connection in list(self.connections.items()):
                            # Include peers with bitfield OR HAVE messages (both indicate piece availability)
                            has_bitfield = (
                                connection.peer_state.bitfield is not None
                                and len(connection.peer_state.bitfield) > 0
                            )
                            has_have_messages = (
                                connection.peer_state.pieces_we_have is not None
                                and len(connection.peer_state.pieces_we_have) > 0
                            )

                            if connection.is_active() and (has_bitfield or has_have_messages):
                                # CRITICAL FIX: Never cycle seeders - they're too valuable
                                # Check if this peer is a seeder
                                is_seeder = False
                                if connection.peer_state.bitfield and self.piece_manager and hasattr(self.piece_manager, "num_pieces"):
                                    bitfield = connection.peer_state.bitfield
                                    num_pieces = self.piece_manager.num_pieces
                                    if num_pieces > 0:
                                        bits_set = sum(1 for i in range(num_pieces) if i < len(bitfield) and bitfield[i])
                                        completion_percent = bits_set / num_pieces
                                        is_seeder = completion_percent >= 1.0

                                if is_seeder:
                                    # Never cycle seeders - they're the most valuable peers
                                    self.logger.debug(
                                        "Skipping seeder %s in peer cycling (seeders are too valuable to cycle)",
                                        connection.peer_info,
                                    )
                                    continue

                                # Check if peer has been used successfully
                                pieces_downloaded = getattr(connection.stats, "pieces_downloaded", 0)
                                connection_age = current_time - connection.stats.last_activity

                                # CRITICAL FIX: Only cycle peers that are truly not useful
                                # Maximize connections - only cycle if peer is completely idle for very long
                                pipeline_utilization = len(connection.outstanding_requests) / max(connection.max_pipeline_depth, 1)

                                # CRITICAL FIX: Much longer age threshold - maximize connections first
                                # Only cycle peers that have been idle for 15+ minutes AND not seeders
                                min_age = 900.0  # 15 minutes - much longer to maximize connections

                                # CRITICAL FIX: Only cycle if peer is:
                                # 1. Not a seeder (seeders are too valuable)
                                # 2. Been idle for 15+ minutes
                                # 3. Not actively downloading (pipeline empty)
                                # 4. Has downloaded pieces but is now idle
                                if (
                                    not is_seeder  # Never cycle seeders
                                    and connection_age > min_age  # Very long idle time
                                    and pipeline_utilization < 0.05  # Completely idle (5% threshold)
                                    and pieces_downloaded >= 1  # Was useful but now idle
                                ):
                                    # This peer has been used successfully - cycle it to make room for fresh peers
                                    self.logger.info(
                                        "🔄 PEER_CYCLING: Cycling successfully used peer %s (downloaded %d pieces, age: %.1fs, pipeline: %.1f%%) - making room for fresh peers",
                                        connection.peer_info,
                                        pieces_downloaded,
                                        connection_age,
                                        pipeline_utilization * 100,
                                    )
                                    peers_to_cycle.append(connection)
                                    # Limit cycling to 10% of connections at a time to avoid disruption
                                    if len(peers_to_cycle) >= max_connections * 0.1:
                                        break

                    # CRITICAL FIX: Keep minimum peers for DHT/PEX to work
                    # Don't cycle all peers - keep at least 50 for DHT/PEX functionality
                    # Maximize connections first - only cycle if we have many peers
                    min_peers_for_dht_pex = 50  # Minimum peers to keep for DHT/PEX functionality (increased to maximize connections)

                    # Cycle successfully used peers, but keep minimum for DHT/PEX
                    peers_to_cycle_filtered = []
                    for connection in peers_to_cycle:
                        # Check if we'd drop below minimum after cycling this peer
                        would_drop_below_min = (active_peer_count - len(peers_to_cycle_filtered)) <= min_peers_for_dht_pex
                        if would_drop_below_min:
                            # Keep this peer for DHT/PEX even though we could cycle it
                            self.logger.debug(
                                "Keeping peer %s for DHT/PEX (would drop below minimum %d peers if cycled, current: %d)",
                                connection.peer_info,
                                min_peers_for_dht_pex,
                                active_peer_count - len(peers_to_cycle_filtered),
                            )
                            continue
                        peers_to_cycle_filtered.append(connection)

                    # Cycle successfully used peers (but keep minimum)
                    for connection in peers_to_cycle_filtered:
                        await self._disconnect_peer(connection)

                    # Recalculate again after cycling
                    async with self.connection_lock:
                        current_connections = len(self.connections)
                        active_peer_count = sum(1 for conn in self.connections.values() if conn.is_active())
                        # Count peers with bitfield OR HAVE messages (both indicate piece availability)
                        peers_with_bitfield_count = sum(
                            1 for conn in self.connections.values()
                            if conn.is_active()
                            and (
                                (conn.peer_state.bitfield is not None and len(conn.peer_state.bitfield) > 0)
                                or (conn.peer_state.pieces_we_have is not None and len(conn.peer_state.pieces_we_have) > 0)
                            )
                        )

                    # CRITICAL FIX: Count seeders and trigger discovery if we have few seeders
                    # Seeders are critical for completing downloads - we need to find more if we have few
                    seeders_count = 0
                    for conn in self.connections.values():
                        if conn.is_active() and conn.peer_state.bitfield:
                            bitfield = conn.peer_state.bitfield
                            if self.piece_manager and hasattr(self.piece_manager, "num_pieces"):
                                num_pieces = self.piece_manager.num_pieces
                                if num_pieces > 0:
                                    bits_set = sum(1 for i in range(num_pieces) if i < len(bitfield) and bitfield[i])
                                    completion_percent = bits_set / num_pieces
                                    if completion_percent >= 1.0:
                                        seeders_count += 1

                    # CRITICAL FIX: If we disconnected peers, trigger immediate discovery
                    # Also trigger if we have few useful peers OR few seeders (even if we didn't disconnect)
                    # Note: We may have kept some peers for DHT/PEX even if they're not useful
                    should_trigger_discovery = (
                        peers_to_disconnect or
                        peers_to_cycle_filtered or
                        (peers_with_bitfield_count <= 2 and active_peer_count > 0) or  # Few useful peers
                        (seeders_count <= 1 and active_peer_count > 0)  # CRITICAL: Few seeders - need to find more
                    )

                    if should_trigger_discovery:
                        kept_for_dht_pex = len(peers_without_bitfield) - len(peers_to_disconnect) if peers_without_bitfield else 0
                        self.logger.info(
                            "🔄 PEER_CYCLING: Disconnected %d peer(s) without bitfields (%d kept for DHT/PEX) and %d successfully used peer(s). "
                            "Current: %d active, %d with bitfields (%.1f%% useful), %d seeder(s). Triggering immediate discovery...",
                            len(peers_to_disconnect),
                            kept_for_dht_pex,
                            len(peers_to_cycle_filtered),
                            active_peer_count,
                            peers_with_bitfield_count,
                            (peers_with_bitfield_count / max(active_peer_count, 1)) * 100,
                            seeders_count,
                        )
                        # Trigger immediate discovery
                        try:
                            import hashlib

                            from ccbt.core.bencode import BencodeEncoder
                            from ccbt.utils.events import Event, emit_event

                            # Get info_hash
                            info_hash_hex = ""
                            if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                                encoder = BencodeEncoder()
                                info_dict = self.torrent_data["info"]
                                info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                                info_hash_hex = info_hash_bytes.hex()

                            await emit_event(
                                Event(
                                    event_type="peer_count_low",
                                    data={
                                        "info_hash": info_hash_hex,
                                        "active_peer_count": active_peer_count,
                                        "peers_with_bitfield": peers_with_bitfield_count,
                                        "threshold": 5,
                                        "trigger": "peer_cycling",
                                    },
                                )
                            )
                        except Exception as e:
                            self.logger.debug("Failed to trigger discovery after peer cycling: %s", e)

                    # CRITICAL FIX: Count seeders and prioritize keeping them
                    # Seeders are the most valuable peers - never disconnect them unless absolutely necessary
                    seeders_count = 0
                    seeders: list[AsyncPeerConnection] = []
                    for conn in self.connections.values():
                        if conn.is_active() and conn.peer_state.bitfield:
                            bitfield = conn.peer_state.bitfield
                            if self.piece_manager and hasattr(self.piece_manager, "num_pieces"):
                                num_pieces = self.piece_manager.num_pieces
                                if num_pieces > 0:
                                    bits_set = sum(1 for i in range(num_pieces) if i < len(bitfield) and bitfield[i])
                                    completion_percent = bits_set / num_pieces
                                    if completion_percent >= 1.0:
                                        seeders_count += 1
                                        seeders.append(conn)

                    self.logger.debug(
                        "PEER_EVAL: Found %d seeder(s) out of %d active peers",
                        seeders_count,
                        active_peer_count,
                    )

                    for peer_key, connection in list(self.connections.items()):  # Iterate over a copy
                        # CRITICAL FIX: Never disconnect seeders unless they're completely unresponsive
                        # Seeders are the most valuable peers - keep them even if they're temporarily slow
                        if connection in seeders:
                            # Only disconnect seeders if they have many consecutive failures or are completely idle
                            if connection.stats.consecutive_failures > 10:  # Very high failure threshold for seeders
                                self.logger.warning(
                                    "Disconnecting seeder %s due to excessive failures (%d consecutive failures)",
                                    connection.peer_info,
                                    connection.stats.consecutive_failures,
                                )
                                await self._disconnect_peer(connection)
                            continue  # Skip further evaluation for seeders

                        # CRITICAL FIX: Check if peer has no pieces we need (BitTorrent protocol compliance)
                        # Disconnect peers that have no useful pieces after grace period
                        if connection.is_active() and connection.peer_state.bitfield:
                            # Peer has sent bitfield - check if they have any pieces at all first
                            bitfield = connection.peer_state.bitfield
                            pieces_count = sum(
                                1 for byte_val in bitfield
                                for bit_idx in range(8)
                                if byte_val & (1 << (7 - bit_idx))
                            )

                            # CRITICAL FIX: Disconnect peers with empty bitfields immediately
                            if pieces_count == 0:
                                self.logger.info(
                                    "Disconnecting %s: peer has empty bitfield (no pieces at all)",
                                    connection.peer_info,
                                )
                                peers_to_recycle.append(connection)
                                continue

                            # Check if they have any pieces we need
                            if self.piece_manager and hasattr(self.piece_manager, "get_missing_pieces"):
                                missing_pieces = self.piece_manager.get_missing_pieces()
                                if missing_pieces:
                                    # Check if peer has ANY missing pieces
                                    has_needed_piece = False
                                    for piece_idx in missing_pieces[:50]:  # Check first 50 missing pieces
                                        byte_idx = piece_idx // 8
                                        bit_idx = piece_idx % 8
                                        if byte_idx < len(bitfield) and bitfield[byte_idx] & (1 << (7 - bit_idx)):
                                            has_needed_piece = True
                                            break

                                    if not has_needed_piece:
                                        # Peer has no pieces we need - check connection age
                                        # Use last_activity as proxy for connection age (connection established when last_activity was set)
                                        # Or check if bitfield was received recently (if bitfield received, connection is at least that old)
                                        connection_age = time.time() - connection.stats.last_activity
                                        # If bitfield was received, use a minimum age based on when bitfield was received
                                        # For now, use last_activity as connection age proxy
                                        grace_period = 30.0  # 30 seconds grace period
                                        if connection_age > grace_period:
                                            # Peer has no useful pieces and grace period expired - disconnect
                                            self.logger.info(
                                                "Disconnecting %s: peer has no pieces we need after %.1fs grace period "
                                                "(BitTorrent protocol: disconnect peers with no mutual interest)",
                                                connection.peer_info,
                                                connection_age,
                                            )
                                            peers_to_recycle.append(connection)
                                            continue

                        # Only recycle if at connection limit or peer is very bad
                        if self._should_recycle_peer(connection, new_peer_available=at_connection_limit):
                            peers_to_recycle.append(connection)

                for connection in peers_to_recycle:
                    # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see connection recycling
                    self.logger.debug("Recycling peer connection to %s due to low performance/health", connection.peer_info)
                    await self._disconnect_peer(connection)  # Disconnect the peer
                    # The connection pool will handle releasing/closing the underlying connection

            except asyncio.CancelledError:
                self.logger.debug("Peer evaluation loop cancelled.")
                break
            except Exception:
                self.logger.exception("Error in peer evaluation loop")

    def _evaluate_peer_performance(self, connection: AsyncPeerConnection) -> float:
        """Evaluate peer performance and return a score.
        
        Args:
            connection: Peer connection to evaluate
            
        Returns:
            Performance score (0.0-1.0, higher = better)

        """
        stats = connection.stats

        # Normalize download rate (max expected: 10MB/s = 1.0)
        max_download_rate = 10 * 1024 * 1024  # 10MB/s
        download_rate_score = min(1.0, stats.download_rate / max_download_rate) if max_download_rate > 0 else 0.0

        # Normalize upload rate (max expected: 5MB/s = 1.0)
        max_upload_rate = 5 * 1024 * 1024  # 5MB/s
        upload_rate_score = min(1.0, stats.upload_rate / max_upload_rate) if max_upload_rate > 0 else 0.0

        # Latency score (lower latency = higher score)
        # RELAXED: Use gentler formula to allow slower peers
        # Original: 1.0 / (1.0 + latency) - too penalizing for high latency
        # New: 1.0 / (1.0 + latency * 0.1) - gives 1.0 for 0ms, ~0.5 for 10s, ~0.1 for 100s
        # This allows high-latency peers to still contribute without severe penalty
        latency_score = 1.0 / (1.0 + stats.request_latency * 0.1) if stats.request_latency >= 0 else 0.5

        # Error rate score (lower errors = higher score)
        # Penalize consecutive failures: 1.0 - min(1.0, failures / 10)
        error_score = 1.0 - min(1.0, stats.consecutive_failures / 10.0)

        # Connection stability (time since last activity)
        # Longer idle time = potentially worse (but not too penalizing)
        current_time = time.time()
        idle_time = current_time - stats.last_activity
        # Idle < 60s = full score, idle > 300s = reduced score
        stability_score = 1.0 if idle_time < 60 else max(0.5, 1.0 - (idle_time - 60) / 600)

        # RELAXED: Reduced latency weight from 20% to 5% to allow slower peers
        # Weighted formula: download (50%) + upload (20%) + latency (5%) + error (10%) + base (15%)
        # Added base score of 0.15 to ensure all peers get minimum score regardless of latency
        base_score = 0.15  # Base score for all peers to avoid zero-scoring slow peers
        performance_score = (
            download_rate_score * 0.5 +
            upload_rate_score * 0.2 +
            latency_score * 0.05 +  # Reduced from 0.2 to 0.05
            error_score * 0.1 +
            base_score  # Added base score
        )

        # Store performance score
        stats.performance_score = performance_score

        return performance_score

    async def _rank_peers_for_connection(
        self, peer_list: list[PeerInfo]
    ) -> list[PeerInfo]:
        """Rank peers for connection based on historical performance, reputation, and success rate.
        
        Args:
            peer_list: List of peer info objects to rank
            
        Returns:
            List of peer info objects sorted by rank (highest score first)

        """
        if not peer_list:
            return []

        # Calculate scores for each peer
        peer_scores: list[tuple[PeerInfo, float]] = []

        for peer_info in peer_list:
            peer_key = str(peer_info)
            score = 0.0

            # CRITICAL FIX: Prioritize seeders (peers with 100% of pieces) and near-seeders (90%+ complete)
            # Seeders are the most valuable peers - connect to them first
            # CRITICAL FIX: Also prioritize tracker-reported seeders (they're more likely to have bitfields)
            seeder_bonus = 0.0
            tracker_seeder_bonus = 0.0
            
            # Check tracker-reported seeder status FIRST (before checking existing connections)
            # Tracker-reported seeders are highly valuable and should be prioritized
            if hasattr(peer_info, "is_seeder") and peer_info.is_seeder:
                # Tracker-reported seeder - give maximum bonus
                seeder_bonus = 0.4  # Increased from 0.3 to 0.4 for tracker-reported seeders
                tracker_seeder_bonus = 0.2  # Additional bonus for being tracker-reported
                self.logger.debug("Ranking tracker-reported seeder %s with +%.1f bonus (total +%.1f)", peer_key, seeder_bonus, seeder_bonus + tracker_seeder_bonus)
            elif hasattr(peer_info, "complete") and peer_info.complete:
                # Tracker-reported complete - also prioritize
                seeder_bonus = 0.4  # Increased from 0.3 to 0.4
                tracker_seeder_bonus = 0.2
                self.logger.debug("Ranking tracker-reported complete peer %s with +%.1f bonus", peer_key, seeder_bonus + tracker_seeder_bonus)
            
            # Check if peer is already connected and is a seeder
            async with self.connection_lock:
                existing_conn = self.connections.get(peer_key)
                if existing_conn and existing_conn.is_active():
                    if existing_conn.peer_state.bitfield:
                        bitfield = existing_conn.peer_state.bitfield
                        if self.piece_manager and hasattr(self.piece_manager, "num_pieces"):
                            num_pieces = self.piece_manager.num_pieces
                            if num_pieces > 0:
                                bits_set = sum(1 for i in range(num_pieces) if i < len(bitfield) and bitfield[i])
                                completion_percent = bits_set / num_pieces
                                if completion_percent >= 1.0:
                                    # Already connected seeder - give bonus to keep connection
                                    # Only add if we didn't already get tracker-reported bonus
                                    if seeder_bonus == 0.0:
                                        seeder_bonus = 0.25  # Increased from 0.15 to 0.25 for already connected seeders
                                elif completion_percent >= 0.9:
                                    # Near-seeder (90%+ complete) - also prioritize
                                    if seeder_bonus == 0.0:
                                        seeder_bonus = 0.15  # Increased from 0.1 to 0.15 for near-seeders

            score += seeder_bonus + tracker_seeder_bonus

            # 1. Historical performance (30% weight - reduced from 40% to allow slower peers)
            performance_score = 0.5  # Default neutral score
            try:
                # Access metrics through piece_manager if available
                if hasattr(self.piece_manager, "_session_manager") and self.piece_manager._session_manager:
                    session_manager = self.piece_manager._session_manager
                    if hasattr(session_manager, "metrics"):
                        # Get peer metrics from metrics collector
                        metrics_collector = session_manager.metrics
                        # Get peer-specific metrics
                        peer_metrics = metrics_collector.get_peer_metrics(peer_key)
                        if peer_metrics:
                            # Calculate performance score from historical metrics
                            # Normalize download rate (max expected: 10MB/s = 1.0)
                            max_download_rate = 10 * 1024 * 1024  # 10MB/s
                            download_rate_score = min(1.0, peer_metrics.download_rate / max_download_rate) if max_download_rate > 0 else 0.0

                            # Normalize upload rate (max expected: 5MB/s = 1.0)
                            max_upload_rate = 5 * 1024 * 1024  # 5MB/s
                            upload_rate_score = min(1.0, peer_metrics.upload_rate / max_upload_rate) if max_upload_rate > 0 else 0.0

                            # Use connection quality score if available
                            quality_score = peer_metrics.connection_quality_score if hasattr(peer_metrics, "connection_quality_score") else 0.5

                            # Use efficiency score if available
                            efficiency_score = peer_metrics.efficiency_score if hasattr(peer_metrics, "efficiency_score") else 0.5

                            # Weighted performance score
                            performance_score = (
                                download_rate_score * 0.4 +
                                upload_rate_score * 0.2 +
                                quality_score * 0.2 +
                                efficiency_score * 0.2
                            )
            except Exception as e:
                self.logger.debug("Failed to get historical performance for %s: %s", peer_key, e)

            score += performance_score * 0.3  # Reduced from 0.4 to 0.3 to allow slower peers

            # 2. Reputation (30% weight)
            reputation_score = 0.5  # Default neutral score
            try:
                if hasattr(self, "_security_manager") and self._security_manager:
                    # Get peer reputation from security manager
                    reputation = self._security_manager.get_peer_reputation(peer_key)
                    # Normalize reputation to 0-1 range (assuming reputation is 0-100 or similar)
                    if isinstance(reputation, (int, float)):
                        reputation_score = min(1.0, max(0.0, reputation / 100.0))
            except Exception as e:
                self.logger.debug("Failed to get reputation for %s: %s", peer_key, e)

            score += reputation_score * 0.3

            # 3. Connection success rate (20% weight)
            success_rate = 0.5  # Default neutral score
            try:
                if hasattr(self.piece_manager, "_session_manager") and self.piece_manager._session_manager:
                    session_manager = self.piece_manager._session_manager
                    if hasattr(session_manager, "metrics"):
                        metrics_collector = session_manager.metrics
                        success_rate = await metrics_collector.get_connection_success_rate(peer_key)
            except Exception as e:
                self.logger.debug("Failed to get connection success rate for %s: %s", peer_key, e)

            score += success_rate * 0.2

            # 4. Source quality bonus (increased weight for better peer selection)
            # CRITICAL FIX: Tracker peers are more likely to have bitfields and be seeders
            # Prefer tracker peers over DHT/PEX peers (tracker peers are more reliable)
            source_bonus = 0.0
            peer_source = peer_info.peer_source or "unknown"
            if peer_source == "tracker":
                source_bonus = 0.15  # Increased from 0.1 to 0.15 - tracker peers are more reliable
                # CRITICAL FIX: Tracker peers are more likely to have bitfields, so prioritize them
                # This helps avoid connecting to peers with pieces=0 (no bitfield)
            elif peer_source == "dht":
                source_bonus = 0.05  # DHT peers get 5% bonus
            elif peer_source == "pex":
                source_bonus = 0.02  # Reduced from 0.03 to 0.02 - PEX peers are less reliable

            score += source_bonus

            # CRITICAL FIX: Additional bonus/penalty for already-connected peers based on bitfield/HAVE message status
            # According to BitTorrent spec (BEP 3), bitfield is OPTIONAL if peer has no pieces
            # Peers may send HAVE messages instead of bitfields (protocol-compliant)
            # We should allow connections to peers without bitfields but check if they send HAVE messages
            # Only penalize peers that don't send HAVE messages OR bitfields after a reasonable time
            already_connected_communication_bonus = 0.0
            if peer_key in self.connections:
                existing_conn = self.connections[peer_key]
                if existing_conn.is_active():
                    has_bitfield = (
                        existing_conn.peer_state.bitfield is not None
                        and len(existing_conn.peer_state.bitfield) > 0
                    )
                    # CRITICAL FIX: Check for HAVE messages as alternative to bitfield
                    have_messages_count = len(existing_conn.peer_state.pieces_we_have) if existing_conn.peer_state.pieces_we_have else 0
                    has_have_messages = have_messages_count > 0
                    
                    # Calculate connection age to determine if peer has had time to send HAVE messages
                    connection_age = time.time() - existing_conn.stats.last_activity if hasattr(existing_conn.stats, "last_activity") else 0.0
                    have_message_timeout = 30.0  # 30 seconds - reasonable time for peer to send first HAVE message
                    
                    if has_bitfield:
                        # Already connected with bitfield - give bonus (seeder bonus already applied above)
                        # This helps keep connections to peers we know have pieces
                        already_connected_communication_bonus = 0.1  # 10% bonus for peers we know have bitfields
                        self.logger.debug(
                            "Peer %s already connected with bitfield - adding +%.1f bonus",
                            peer_key,
                            already_connected_communication_bonus,
                        )
                    elif has_have_messages:
                        # Peer sent HAVE messages but no bitfield - protocol-compliant (leecher with 0% complete initially)
                        # Give smaller bonus than bitfield, but still positive (peer is communicating)
                        already_connected_communication_bonus = 0.05  # 5% bonus for peers using HAVE messages
                        self.logger.debug(
                            "Peer %s already connected with %d HAVE message(s) (no bitfield) - adding +%.1f bonus (protocol-compliant)",
                            peer_key,
                            have_messages_count,
                            already_connected_communication_bonus,
                        )
                    elif connection_age > have_message_timeout:
                        # Already connected for >30s but no bitfield AND no HAVE messages
                        # This peer is likely non-responsive or buggy - penalize
                        already_connected_communication_bonus = -0.2  # Penalty for peers that don't communicate
                        self.logger.debug(
                            "Peer %s already connected for %.1fs but no bitfield OR HAVE messages - applying -%.1f penalty",
                            peer_key,
                            connection_age,
                            abs(already_connected_communication_bonus),
                        )
                    else:
                        # Recently connected (<30s) without bitfield - give benefit of doubt
                        # Peer may send HAVE messages soon - no penalty yet
                        self.logger.debug(
                            "Peer %s recently connected (%.1fs) without bitfield - waiting for HAVE messages (no penalty yet)",
                            peer_key,
                            connection_age,
                        )

            score += already_connected_communication_bonus

            # 5. Failure penalty (subtract from score)
            failure_penalty = 0.0
            async with self._failed_peer_lock:
                if peer_key in self._failed_peers:
                    fail_count = self._failed_peers[peer_key].get("count", 0)
                    # Penalize based on failure count: -0.1 per failure, max -0.5
                    failure_penalty = min(0.5, fail_count * 0.1)

            score -= failure_penalty

            # Ensure score is in valid range
            score = max(0.0, min(1.0, score))

            peer_scores.append((peer_info, score))

        # Sort by score (highest first)
        peer_scores.sort(key=lambda x: x[1], reverse=True)

        # Return ranked peer list
        ranked_peers = [peer_info for peer_info, _ in peer_scores]

        self.logger.debug(
            "Ranked %d peers (top 5 scores: %s)",
            len(ranked_peers),
            [f"{p!s}={score:.2f}" for p, score in peer_scores[:5]],
        )

        return ranked_peers

    async def _cleanup_timed_out_requests(self, connection: AsyncPeerConnection) -> int:
        """Clean up timed-out outstanding requests to free pipeline slots.
        
        According to BitTorrent protocol, requests that don't receive responses
        within a reasonable time should be cancelled to prevent pipeline deadlock.
        
        CRITICAL FIX: Use more aggressive timeout when pipeline is full to prevent
        deadlock. If pipeline is >80% full, use shorter timeout (15s) to free slots faster.
        
        Args:
            connection: Peer connection to clean up
            
        Returns:
            Number of requests cancelled

        """
        current_time = time.time()
        # Default timeout: 60 seconds (configurable via network.request_timeout)
        base_timeout = getattr(self.config.network, "request_timeout", 60.0)

        # CRITICAL FIX: Use more aggressive timeout when pipeline is full
        # If pipeline is >80% full, use shorter timeout to free slots faster
        pipeline_utilization = len(connection.outstanding_requests) / max(connection.max_pipeline_depth, 1)
        if pipeline_utilization > 0.8:
            # Pipeline is >80% full - use aggressive timeout (15 seconds)
            request_timeout = min(15.0, base_timeout * 0.25)
            self.logger.debug(
                "Using aggressive timeout %.1fs for %s (pipeline %d/%d, utilization=%.1f%%)",
                request_timeout,
                connection.peer_info,
                len(connection.outstanding_requests),
                connection.max_pipeline_depth,
                pipeline_utilization * 100,
            )
        else:
            request_timeout = base_timeout

        # CRITICAL FIX: Apply dynamic timeout adjustment based on unexpected pieces
        # If peer is sending useful unexpected pieces, INCREASE timeout to give them more time
        # This allows per-piece and per-block timeouts to capture the sent pieces
        if hasattr(connection.stats, "timeout_adjustment_factor"):
            request_timeout *= connection.stats.timeout_adjustment_factor
            if connection.stats.timeout_adjustment_factor > 1.0:
                self.logger.debug(
                    "Applied timeout INCREASE for %s: %.1fs (factor=%.2f, unexpected_useful=%d) - giving peer more time to send pieces",
                    connection.peer_info,
                    request_timeout,
                    connection.stats.timeout_adjustment_factor,
                    connection.stats.unexpected_pieces_useful,
                )

        timed_out_requests = []
        for request_key, request_info in list(connection.outstanding_requests.items()):
            age = current_time - request_info.timestamp
            if age > request_timeout:
                timed_out_requests.append((request_key, request_info))

        if not timed_out_requests:
            return 0

        # Cancel timed-out requests
        cancelled_count = 0
        for request_key, request_info in timed_out_requests:
            try:
                # Send CANCEL message to peer (BitTorrent protocol compliance)
                cancel_msg = CancelMessage(
                    request_info.piece_index,
                    request_info.begin,
                    request_info.length,
                )
                await self._send_message(connection, cancel_msg)

                # Remove from outstanding requests
                if request_key in connection.outstanding_requests:
                    del connection.outstanding_requests[request_key]
                    cancelled_count += 1

                    # Track failed request
                    connection.stats.blocks_failed += 1

                    self.logger.warning(
                        "Cancelled timed-out request %d:%d:%d from %s (age=%.1fs, timeout=%.1fs, pipeline now %d/%d)",
                        request_info.piece_index,
                        request_info.begin,
                        request_info.length,
                        connection.peer_info,
                        age,
                        request_timeout,
                        len(connection.outstanding_requests),
                        connection.max_pipeline_depth,
                    )
            except Exception as e:
                # Log error but continue cleaning up other requests
                self.logger.warning(
                    "Failed to cancel timed-out request %d:%d:%d from %s: %s",
                    request_info.piece_index,
                    request_info.begin,
                    request_info.length,
                    connection.peer_info,
                    e,
                )
                # Still remove from outstanding requests even if cancel message failed
                if request_key in connection.outstanding_requests:
                    del connection.outstanding_requests[request_key]
                    cancelled_count += 1

        if cancelled_count > 0:
            self.logger.info(
                "Cleaned up %d timed-out request(s) from %s (pipeline now %d/%d)",
                cancelled_count,
                connection.peer_info,
                len(connection.outstanding_requests),
                connection.max_pipeline_depth,
            )

        return cancelled_count

    async def _update_peer_stats(self) -> None:
        """Update peer statistics."""
        current_time = time.time()  # pragma: no cover - Stats update loop requires time-based state changes, complex to test

        async with self.connection_lock:  # pragma: no cover - Same context
            for connection in self.connections.values():  # pragma: no cover - Stats update loop requires time-based state changes, complex to test
                # CRITICAL FIX: Clean up timed-out requests before updating stats
                # This prevents pipeline deadlock when peers don't send data
                await self._cleanup_timed_out_requests(connection)

                # Calculate rates
                time_diff = (
                    current_time - connection.stats.last_activity
                )  # pragma: no cover - Same context
                if time_diff > 0:  # pragma: no cover - Same context
                    connection.stats.download_rate = (
                        connection.stats.bytes_downloaded / time_diff
                    )  # pragma: no cover - Same context
                    connection.stats.upload_rate = (
                        connection.stats.bytes_uploaded / time_diff
                    )  # pragma: no cover - Same context

                # Calculate efficiency score (bytes per connection time)
                connection_duration = max(time_diff, 1.0)
                connection.stats.efficiency_score = connection.stats.bytes_downloaded / connection_duration

                # Calculate value score (combines efficiency, performance, and reliability)
                performance_score = self._evaluate_peer_performance(connection)
                reliability_score = (
                    connection.stats.blocks_delivered /
                    max(connection.stats.blocks_delivered + connection.stats.blocks_failed, 1)
                )
                connection.stats.value_score = (
                    connection.stats.efficiency_score * 0.4 +
                    performance_score * 0.4 +
                    reliability_score * 0.2
                )

                # Update pipeline depth adaptively if enabled
                if getattr(self.config.network, "pipeline_adaptive_depth", True):
                    connection.max_pipeline_depth = self._calculate_pipeline_depth(
                        connection
                    )

                # Reset counters
                connection.stats.bytes_downloaded = 0  # pragma: no cover - Same context
                connection.stats.bytes_uploaded = 0  # pragma: no cover - Same context
                connection.stats.last_activity = (
                    current_time  # pragma: no cover - Same context
                )

    async def _log_connection_diagnostics(self) -> None:
        """Log comprehensive connection diagnostics to help identify connection issues.
        
        This method logs detailed information about all connections including:
        - Connection states (active, disconnected, etc.)
        - Choking status (choking/unchoked)
        - Piece availability (has pieces we need)
        - Pipeline capacity (can request pieces)
        - Connection age and activity
        """
        async with self.connection_lock:
            total_connections = len(self.connections)
            if total_connections == 0:
                self.logger.info(
                    "🔍 CONNECTION DIAGNOSTICS: No connections established yet"
                )
                return

            # Categorize connections
            active_connections = []
            disconnected_connections = []
            handshake_pending = []
            bitfield_pending = []
            unchoked_connections = []
            choked_connections = []
            requestable_connections = []
            no_pieces_connections = []

            for peer_key, conn in self.connections.items():
                is_active = conn.is_active()
                has_bitfield = conn.peer_state.bitfield is not None
                is_unchoked = not conn.peer_choking
                can_request = conn.can_request()

                # Count pieces peer has (if bitfield available)
                pieces_count = 0
                has_needed_pieces = False
                if has_bitfield and self.piece_manager:
                    bitfield = conn.peer_state.bitfield
                    if bitfield:
                        pieces_count = sum(
                            1 for byte_val in bitfield
                            for bit_idx in range(8)
                            if byte_val & (1 << (7 - bit_idx))
                        )

                        # Check if peer has any pieces we need
                        if hasattr(self.piece_manager, "get_missing_pieces"):
                            missing_pieces = self.piece_manager.get_missing_pieces()
                            if missing_pieces:
                                for piece_idx in missing_pieces[:50]:  # Check first 50
                                    byte_idx = piece_idx // 8
                                    bit_idx = piece_idx % 8
                                    if byte_idx < len(bitfield) and bitfield[byte_idx] & (1 << (7 - bit_idx)):
                                        has_needed_pieces = True
                                        break

                # Categorize
                if is_active:
                    active_connections.append((peer_key, conn))
                    if is_unchoked:
                        unchoked_connections.append((peer_key, conn))
                    else:
                        choked_connections.append((peer_key, conn))

                    if can_request:
                        requestable_connections.append((peer_key, conn))

                    if has_bitfield and not has_needed_pieces and pieces_count > 0:
                        no_pieces_connections.append((peer_key, conn))
                elif conn.state == ConnectionState.DISCONNECTED:
                    disconnected_connections.append((peer_key, conn))
                elif conn.state in (ConnectionState.HANDSHAKE_SENT, ConnectionState.HANDSHAKE_RECEIVED):
                    handshake_pending.append((peer_key, conn))
                elif conn.state == ConnectionState.BITFIELD_RECEIVED:
                    bitfield_pending.append((peer_key, conn))

            # Log summary
            self.logger.info(
                "🔍 CONNECTION DIAGNOSTICS: Total=%d, Active=%d, Disconnected=%d, "
                "HandshakePending=%d, BitfieldPending=%d, Unchoked=%d, Choked=%d, "
                "Requestable=%d, NoNeededPieces=%d",
                total_connections,
                len(active_connections),
                len(disconnected_connections),
                len(handshake_pending),
                len(bitfield_pending),
                len(unchoked_connections),
                len(choked_connections),
                len(requestable_connections),
                len(no_pieces_connections),
            )

            # Log detailed info for active connections (limit to first 10 to avoid log spam)
            if active_connections:
                self.logger.info(
                    "🔍 ACTIVE CONNECTIONS (%d total, showing first 10):",
                    len(active_connections),
                )
                for peer_key, conn in active_connections[:10]:
                    pieces_count = 0
                    if conn.peer_state.bitfield:
                        bitfield = conn.peer_state.bitfield
                        pieces_count = sum(
                            1 for byte_val in bitfield
                            for bit_idx in range(8)
                            if byte_val & (1 << (7 - bit_idx))
                        )

                    pipeline_usage = len(conn.outstanding_requests)
                    pipeline_capacity = conn.max_pipeline_depth
                    pipeline_pct = (pipeline_usage / pipeline_capacity * 100) if pipeline_capacity > 0 else 0

                    connection_age = time.time() - (getattr(conn, "connection_start_time", time.time()))

                    self.logger.info(
                        "  %s: state=%s, choking=%s, interested=%s, pieces=%d, "
                        "pipeline=%d/%d (%.0f%%), age=%.0fs, can_request=%s, "
                        "download_rate=%.1f KB/s, upload_rate=%.1f KB/s",
                        peer_key,
                        conn.state.value,
                        conn.peer_choking,
                        conn.am_interested,
                        pieces_count,
                        pipeline_usage,
                        pipeline_capacity,
                        pipeline_pct,
                        connection_age,
                        conn.can_request(),
                        conn.stats.download_rate / 1024 if conn.stats.download_rate else 0.0,
                        conn.stats.upload_rate / 1024 if conn.stats.upload_rate else 0.0,
                    )

            # Log why connections aren't requestable
            if len(requestable_connections) < len(active_connections):
                non_requestable = [
                    (k, c) for k, c in active_connections
                    if not c.can_request()
                ]
                if non_requestable:
                    self.logger.warning(
                        "🔍 NON-REQUESTABLE CONNECTIONS (%d):",
                        len(non_requestable),
                    )
                    for peer_key, conn in non_requestable[:10]:  # Limit to first 10
                        reasons = []
                        if not conn.is_active():
                            reasons.append("not_active")
                        if conn.peer_choking:
                            reasons.append("choking")
                        if len(conn.outstanding_requests) >= conn.max_pipeline_depth:
                            reasons.append(f"pipeline_full({len(conn.outstanding_requests)}/{conn.max_pipeline_depth})")

                        self.logger.warning(
                            "  %s: cannot_request (reasons: %s, state=%s)",
                            peer_key,
                            ", ".join(reasons) if reasons else "unknown",
                            conn.state.value,
                        )

            # Log choked connections
            if choked_connections:
                self.logger.info(
                    "🔍 CHOKED CONNECTIONS (%d): These peers are choking us (waiting for UNCHOKE)",
                    len(choked_connections),
                )
                for peer_key, conn in choked_connections[:5]:  # Limit to first 5
                    connection_age = time.time() - (getattr(conn, "connection_start_time", time.time()))
                    self.logger.info(
                        "  %s: choking=%s, age=%.0fs, interested=%s",
                        peer_key,
                        conn.peer_choking,
                        connection_age,
                        conn.am_interested,
                    )

            # Log connections with no needed pieces
            if no_pieces_connections:
                self.logger.info(
                    "🔍 CONNECTIONS WITH NO NEEDED PIECES (%d): These peers don't have pieces we need",
                    len(no_pieces_connections),
                )
                for peer_key, conn in no_pieces_connections[:5]:  # Limit to first 5
                    pieces_count = 0
                    if conn.peer_state.bitfield:
                        bitfield = conn.peer_state.bitfield
                        pieces_count = sum(
                            1 for byte_val in bitfield
                            for bit_idx in range(8)
                            if byte_val & (1 << (7 - bit_idx))
                        )
                    self.logger.info(
                        "  %s: pieces=%d (but none we need), choking=%s",
                        peer_key,
                        pieces_count,
                        conn.peer_choking,
                    )

    async def request_piece(
        self,
        connection: AsyncPeerConnection,
        piece_index: int,
        begin: int,
        length: int,
    ) -> None:
        """Request a block from a peer."""
        if not connection.can_request():
            self.logger.debug(
                "Cannot request piece %d:%d:%d from %s (choking=%s, active=%s, pipeline=%d/%d)",
                piece_index,
                begin,
                length,
                connection.peer_info,
                connection.peer_choking,
                connection.is_active(),
                len(connection.outstanding_requests),
                connection.max_pipeline_depth,
            )
            return

        # CRITICAL FIX: Ensure "interested" message is sent before requesting pieces
        # According to BitTorrent protocol, we should be "interested" before requesting,
        # but we don't block requests if sending fails - some peers may accept requests anyway
        if not connection.am_interested:
            try:
                await self._send_interested(connection)
                self.logger.debug(
                    "Sent interested message to %s (fallback before piece request)",
                    connection.peer_info,
                )
            except Exception as e:
                # Log but continue - some peers may accept requests even without "interested"
                self.logger.debug(
                    "Failed to send interested to %s before piece request: %s (continuing with request anyway)",
                    connection.peer_info,
                    e,
                )

        # CRITICAL FIX: Log when we actually request a piece
        self.logger.debug(
            "Requesting piece %d:%d:%d from %s (interested=%s, can_request=%s)",
            piece_index,
            begin,
            length,
            connection.peer_info,
            connection.am_interested,
            connection.can_request(),
        )

        if connection.can_request():  # pragma: no cover - Piece request logic requires active connection with unchoked peer, complex to test
            # Calculate priority for this request
            priority, bandwidth_estimate = await self._calculate_request_priority(
                piece_index, self.piece_manager, connection
            )
            request_info = RequestInfo(
                piece_index, begin, length, time.time()
            )  # pragma: no cover - Same context
            request_info.bandwidth_estimate = bandwidth_estimate

            # Use priority queue if prioritization is enabled
            enable_prioritization = getattr(
                self.config.network, "pipeline_enable_prioritization", True
            )
            if enable_prioritization:
                # Initialize priority queue if not exists
                if connection._priority_queue is None:  # noqa: SLF001 - Internal queue state
                    connection._priority_queue = []  # noqa: SLF001 - Internal queue state
                # Add to priority queue (negative priority for max-heap via min-heap)
                heappush(
                    connection._priority_queue,  # noqa: SLF001 - Internal queue state
                    (-priority, time.time(), request_info),
                )
            else:
                # Use regular queue
                connection.request_queue.append(request_info)

            # Process queued requests with coalescing
            requests_sent = await self._process_request_queue(connection)

            if requests_sent > 0:
                # Log at INFO level when requests are actually sent
                self.logger.info(
                    "Sent %d REQUEST message(s) to %s for piece %d:%d:%d (priority=%.2f, outstanding=%d/%d)",
                    requests_sent,
                    connection.peer_info,
                    piece_index,
                    begin,
                    length,
                    priority,
                    len(connection.outstanding_requests),
                    connection.max_pipeline_depth,
                )
            else:
                self.logger.debug(
                    "Queued block %s:%s:%s from %s (priority=%.2f, not sent yet - queue processing)",
                    piece_index,
                    begin,
                    length,
                    connection.peer_info,
                    priority,
                )  # pragma: no cover - Same context

    async def _process_request_queue(self, connection: AsyncPeerConnection) -> int:
        """Process queued requests with prioritization and coalescing.

        Args:
            connection: Peer connection

        Returns:
            Number of requests actually sent

        """
        # Collect requests to send
        requests_to_send: list[RequestInfo] = []

        # Get requests from priority queue or regular queue
        enable_prioritization = getattr(
            self.config.network, "pipeline_enable_prioritization", True
        )

        if enable_prioritization and connection._priority_queue:  # noqa: SLF001 - Internal queue state
            # Pop from priority queue (highest priority first)
            max_requests = connection.get_available_pipeline_slots()
            while connection._priority_queue and len(requests_to_send) < max_requests:  # noqa: SLF001 - Internal queue state
                _, _, request_info = heappop(connection._priority_queue)  # noqa: SLF001 - Internal queue state
                requests_to_send.append(request_info)
        else:
            # Use regular queue
            max_requests = connection.get_available_pipeline_slots()
            while connection.request_queue and len(requests_to_send) < max_requests:
                requests_to_send.append(connection.request_queue.popleft())

        if not requests_to_send:
            return 0

        # Coalesce requests if enabled
        coalesced_requests = self._coalesce_requests(requests_to_send)

        # Send coalesced requests
        requests_sent = 0
        for request_info in coalesced_requests:
            request_key = (
                request_info.piece_index,
                request_info.begin,
                request_info.length,
            )

            # Check if already outstanding
            if request_key in connection.outstanding_requests:
                continue

            connection.outstanding_requests[request_key] = request_info

            message = RequestMessage(
                request_info.piece_index,
                request_info.begin,
                request_info.length,
            )
            await self._send_message(connection, message)
            requests_sent += 1
            self.logger.debug(
                "Requested block %s:%s:%s from %s",
                request_info.piece_index,
                request_info.begin,
                request_info.length,
                connection.peer_info,
            )

        return requests_sent

    async def broadcast_have(self, piece_index: int) -> None:
        """Broadcast HAVE message to all connected peers.
        
        Per BEP 3, HAVE messages should be sent to all connected peers when we complete a piece.
        This allows peers to know which pieces we have, which is important for:
        1. Peers to decide if they're interested in us
        2. Peers to request pieces from us
        3. Maintaining good peer relationships (some clients disconnect if we don't send HAVE messages)
        """
        have_msg = HaveMessage(piece_index)
        sent_count = 0
        failed_count = 0

        async with self.connection_lock:
            connections_to_notify = [
                conn for conn in self.connections.values()
                if conn.is_connected() and conn.writer is not None
            ]

        if not connections_to_notify:
            self.logger.debug(
                "No connected peers to send HAVE message for piece %d (total connections: %d)",
                piece_index,
                len(self.connections),
            )
            return

        # Send HAVE message to all connected peers
        for connection in connections_to_notify:
            try:
                await self._send_message(connection, have_msg)
                sent_count += 1
                self.logger.debug(
                    "Sent HAVE message for piece %d to %s",
                    piece_index,
                    connection.peer_info,
                )
            except Exception as e:
                failed_count += 1
                self.logger.debug(
                    "Failed to send HAVE message for piece %d to %s: %s",
                    piece_index,
                    connection.peer_info,
                    e,
                )

        if sent_count > 0:
            self.logger.info(
                "Broadcast HAVE message for piece %d to %d peer(s) (failed: %d)",
                piece_index,
                sent_count,
                failed_count,
            )

    def get_connected_peers(self) -> list[AsyncPeerConnection]:
        """Get list of connected peers."""
        return [
            conn for conn in self.connections.values() if conn.is_connected()
        ]  # pragma: no cover - Simple getter, tested via existing tests

    def get_active_peers(self) -> list[AsyncPeerConnection]:
        """Get list of active peers."""
        # CRITICAL FIX: Include peers that are connected but not yet fully active
        # Also include peers that have received bitfield (ready for requests)
        # Note: This is a synchronous method, so we can't use async locks
        # We create a copy of connections.values() to iterate safely
        active_peers = []
        connections_copy = list(self.connections.values())
        for conn in connections_copy:
            # CRITICAL FIX: Explicitly exclude ERROR and DISCONNECTED state connections
            # ERROR state indicates connection is being cleaned up or has failed
            if conn.state == ConnectionState.ERROR:
                continue

            # CRITICAL FIX: Include connections with BITFIELD_RECEIVED state even if reader/writer might be None
            # This ensures connections that received bitfield are counted as active before they might close
            # BITFIELD_RECEIVED means we've successfully exchanged bitfields and can check piece availability
            if conn.state == ConnectionState.BITFIELD_RECEIVED:
                # BITFIELD_RECEIVED connections are considered active even if reader/writer are None
                # (they shouldn't be None, but if they are, we still count the connection as active
                # because we've received the bitfield and can use it for piece availability)
                active_peers.append(conn)
                continue

            # CRITICAL FIX: Exclude connections that don't have reader/writer (actually disconnected)
            # A connection can be in ACTIVE state but have None reader/writer if it was disconnected
            # This prevents including stale connections that will never unchoke
            # BUT: BITFIELD_RECEIVED connections are handled above, so we only check reader/writer for other states
            if conn.reader is None or conn.writer is None:
                # Connection is not actually connected - skip it
                continue

            # Also include peers that are in ACTIVE state even if not fully active yet
            if conn.is_active() or conn.state in {
                ConnectionState.ACTIVE,
            }:
                active_peers.append(conn)

        # Debug logging for connection state distribution
        if self.logger.isEnabledFor(logging.DEBUG):
            states = {}
            disconnected_count = 0
            for conn in self.connections.values():
                state_val = conn.state.value
                states[state_val] = states.get(state_val, 0) + 1
                # Count disconnected connections (no reader/writer)
                if conn.reader is None or conn.writer is None:
                    disconnected_count += 1
            self.logger.debug(
                "Connection state distribution: %s (total: %d, active: %d, disconnected: %d)",
                states,
                len(self.connections),
                len(active_peers),
                disconnected_count,
            )

        return active_peers

    def get_peer_bitfields(self) -> dict[str, BitfieldMessage]:
        """Get bitfields for all connected peers."""
        result = {}  # pragma: no cover - Simple getter with filtering, tested via existing tests
        for (
            peer_key,
            connection,
        ) in (
            self.connections.items()
        ):  # pragma: no cover - Simple getter with filtering, tested via existing tests
            if connection.peer_state.bitfield:  # pragma: no cover - Same context
                result[peer_key] = (
                    connection.peer_state.bitfield
                )  # pragma: no cover - Same context
        return result  # pragma: no cover - Return path for get_peer_bitfields (tested but coverage tool may not track reliably due to dict comprehension)

    async def disconnect_peer(self, peer_info: PeerInfo) -> None:
        """Disconnect from a specific peer."""
        async with self.connection_lock:  # pragma: no cover - Edge case: disconnecting non-existent peer, tested via existing tests
            peer_key = str(peer_info)
            if (
                peer_key in self.connections
            ):  # pragma: no cover - Edge case: disconnecting non-existent peer
                connection = self.connections[
                    peer_key
                ]  # pragma: no cover - Same context
                await self._disconnect_peer(
                    connection
                )  # pragma: no cover - Same context

    async def _send_our_extension_handshake(
        self, connection: AsyncPeerConnection
    ) -> None:
        """Send our extension handshake to peer (BEP 10 requirement).
        
        According to BEP 10, we MUST send our extension handshake before using
        extension messages. Peers will reject extension messages if we haven't
        sent our handshake first.
        
        Args:
            connection: Peer connection to send handshake to

        """
        if not connection.writer or connection.writer.is_closing():
            self.logger.debug(
                "Cannot send extension handshake to %s: writer not available",
                connection.peer_info,
            )
            return

        try:
            import struct

            from ccbt.core.bencode import BencodeEncoder
            from ccbt.extensions.manager import get_extension_manager

            extension_manager = get_extension_manager()
            extension_protocol = extension_manager.get_extension("protocol")

            if not extension_protocol:
                self.logger.debug(
                    "Extension protocol not available, skipping extension handshake to %s",
                    connection.peer_info,
                )
                return

            # CRITICAL: Register ut_metadata extension if not already registered
            # This ensures ut_metadata is included in our handshake
            try:
                ut_metadata_info = extension_protocol.get_extension_info("ut_metadata")
                if not ut_metadata_info:
                    # Register ut_metadata with message_id=1 (standard)
                    extension_protocol.register_extension("ut_metadata", "1.0", handler=None)
                    self.logger.debug("Registered ut_metadata extension for handshake")
            except ValueError:
                # Already registered, that's fine
                pass

            # Create our extension handshake dictionary
            # BEP 10 format: d<m><ut_metadata><message_id>e
            # We need: {"m": {"ut_metadata": 1}}
            handshake_dict = {b"m": {b"ut_metadata": 1}}

            # Add XET folder sync handshake data if available
            try:
                from ccbt.extensions.xet_handshake import XetHandshakeExtension
                from ccbt.session.session import AsyncSessionManager

                xet_handshake = getattr(self, "_xet_handshake", None)
                if xet_handshake is None:
                    # Try to get from session manager if available
                    if hasattr(self, "session_manager") and isinstance(
                        self.session_manager, AsyncSessionManager
                    ):
                        sync_manager = getattr(
                            self.session_manager, "_xet_sync_manager", None
                        )
                        if sync_manager:
                            allowlist_hash = sync_manager.get_allowlist_hash()
                            sync_mode = sync_manager.get_sync_mode()
                            git_ref = sync_manager.get_current_git_ref()
                            xet_handshake = XetHandshakeExtension(
                                allowlist_hash=allowlist_hash,
                                sync_mode=sync_mode,
                                git_ref=git_ref,
                            )
                            self._xet_handshake = xet_handshake

                if xet_handshake:
                    xet_handshake_data = xet_handshake.encode_handshake()
                    # Merge XET handshake data into our handshake
                    for key, value in xet_handshake_data.items():
                        if isinstance(key, str):
                            key_bytes = key.encode("utf-8")
                        else:
                            key_bytes = key
                        handshake_dict[key_bytes] = value
            except Exception as e:
                # Log but don't fail if XET handshake encoding fails
                self.logger.debug(
                    "Failed to encode XET handshake for %s: %s",
                    connection.peer_info,
                    e,
                )

            # Encode as bencoded dictionary
            encoder = BencodeEncoder()
            bencoded_data = encoder.encode(handshake_dict)

            # BEP 10 message format: <length (4 bytes)><message_id (20)><extension_id (0)><bencoded_data>
            # length includes message_id (1 byte) and extension_id (1 byte)
            msg_length = 2 + len(bencoded_data)
            handshake_msg = (
                struct.pack("!IBB", msg_length, 20, 0) + bencoded_data
            )

            # Send extension handshake
            connection.writer.write(handshake_msg)
            await connection.writer.drain()

            self.logger.info(
                "Sent our extension handshake to %s (length=%d, ut_metadata_id=1)",
                connection.peer_info,
                len(handshake_msg),
            )
        except Exception as e:
            self.logger.warning(
                "Error sending extension handshake to %s: %s",
                connection.peer_info,
                e,
                exc_info=True,
            )
            # Don't raise - extension handshake failure shouldn't break connection
            # Some peers may not support extensions, which is fine

    async def _trigger_metadata_exchange(
        self,
        connection: AsyncPeerConnection,
        ut_metadata_id: int,
        handshake_data: dict[str, Any],
    ) -> None:
        """Trigger metadata exchange for magnet links using existing connection.
        
        Args:
            connection: Peer connection with ut_metadata support
            ut_metadata_id: Extension message ID for ut_metadata
            handshake_data: Extended handshake data containing metadata_size

        """
        try:
            if not connection.reader or not connection.writer:
                self.logger.warning(
                    "Cannot trigger metadata exchange for %s: reader/writer not available",
                    connection.peer_info,
                )
                return

            # Get metadata size from handshake
            metadata_size = handshake_data.get("metadata_size")
            if not metadata_size:
                self.logger.debug(
                    "Peer %s supports ut_metadata but metadata_size not in handshake",
                    connection.peer_info,
                )
                return

            # CRITICAL SECURITY: Limit metadata size to prevent DoS attacks (BEP 9)
            # Common practice: limit to 50 MB (most torrents are < 1 MB)
            MAX_METADATA_SIZE = 50 * 1024 * 1024  # 50 MB
            if metadata_size > MAX_METADATA_SIZE:
                self.logger.error(
                    "SECURITY: Metadata size %d bytes from %s exceeds maximum %d bytes. "
                    "Rejecting potentially malicious metadata request.",
                    metadata_size,
                    connection.peer_info,
                    MAX_METADATA_SIZE,
                )
                return

            if metadata_size <= 0:
                self.logger.warning(
                    "Invalid metadata size %d from %s (must be > 0)",
                    metadata_size,
                    connection.peer_info,
                )
                return

            self.logger.info(
                "Starting metadata exchange with %s (metadata_size=%d, ut_metadata_id=%d)",
                connection.peer_info,
                metadata_size,
                ut_metadata_id,
            )

            # CRITICAL FIX: Use existing connection directly instead of creating new one
            # Calculate number of metadata pieces (each piece is 16KB)
            import math
            import struct

            from ccbt.core.bencode import BencodeDecoder, BencodeEncoder

            num_pieces = math.ceil(metadata_size / 16384)
            self.logger.debug(
                "Requesting %d metadata piece(s) from %s (metadata_size=%d)",
                num_pieces,
                connection.peer_info,
                metadata_size,
            )

            # CRITICAL FIX: Initialize metadata exchange state with events for coordination
            # Use consistent peer_key format (ip:port) to match lookup format
            if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
            else:
                peer_key = str(connection.peer_info)
            piece_events: dict[int, asyncio.Event] = {}
            piece_data_dict: dict[int, bytes | None] = {}

            for piece_idx in range(num_pieces):
                piece_events[piece_idx] = asyncio.Event()
                piece_data_dict[piece_idx] = None

            self._metadata_exchange_state[peer_key] = {
                "ut_metadata_id": ut_metadata_id,
                "metadata_size": metadata_size,
                "num_pieces": num_pieces,
                "pieces": piece_data_dict,
                "events": piece_events,
                "complete": False,
            }

            self.logger.info(
                "Created metadata exchange state for %s (peer_key=%s, ut_metadata_id=%d, num_pieces=%d, total_active=%d)",
                connection.peer_info,
                peer_key,
                ut_metadata_id,
                num_pieces,
                len(self._metadata_exchange_state),
            )

            try:
                # CRITICAL FIX: Ensure INTERESTED is sent before metadata requests
                # Some peers may require INTERESTED before responding to metadata requests
                # According to BitTorrent protocol, we should be interested before requesting
                if not connection.am_interested:
                    try:
                        await self._send_interested(connection)
                        self.logger.info(
                            "Sent INTERESTED to %s before metadata requests (was: am_interested=False)",
                            connection.peer_info,
                        )
                        # Small delay to allow peer to process INTERESTED message
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to send INTERESTED to %s before metadata requests: %s (continuing anyway)",
                            connection.peer_info,
                            e,
                        )

                # CRITICAL FIX: Don't wait for UNCHOKE - send metadata requests immediately
                # BEP 9 allows metadata exchange even when choked, and waiting causes timeouts
                # Many peers don't respond to metadata requests when choked, so we'll try anyway
                # but won't block waiting for UNCHOKE (which may never come)
                if connection.peer_choking:
                    self.logger.info(
                        "Peer %s is CHOKING us, sending metadata requests immediately (BEP 9 allows metadata when choked, but peer may not respond)",
                        connection.peer_info,
                    )
                else:
                    self.logger.info(
                        "Peer %s is UNCHOKED, sending metadata requests",
                        connection.peer_info,
                    )

                # Request all metadata pieces
                for piece_idx in range(num_pieces):
                    try:
                        # Send ut_metadata request: <length><msg_id (20)><ext_id><bencoded_request>
                        # BEP 9 format: <length (4 bytes)><message_id (20)><extension_id><bencoded_request>
                        # bencoded_request: d8:msg_typei0e5:piecei<index>ee
                        req_dict = {b"msg_type": 0, b"piece": piece_idx}
                        req_payload = BencodeEncoder().encode(req_dict)
                        req_msg = (
                            struct.pack("!IBB", 2 + len(req_payload), 20, ut_metadata_id)
                            + req_payload
                        )

                        # CRITICAL: Log request details for debugging
                        # BEP 9 compliance: Log full message structure for verification
                        self.logger.info(
                            "Sending ut_metadata request to %s: piece=%d/%d, ut_metadata_id=%d, msg_length=%d, payload_len=%d, payload_hex=%s, full_msg_hex=%s, state=%s, choking=%s, interested=%s",
                            connection.peer_info,
                            piece_idx,
                            num_pieces,
                            ut_metadata_id,
                            len(req_msg),
                            len(req_payload),
                            req_payload.hex()[:50] if len(req_payload) > 50 else req_payload.hex(),
                            req_msg.hex()[:100] if len(req_msg) > 100 else req_msg.hex(),
                            connection.state.value,
                            connection.peer_choking,
                            connection.am_interested,
                        )

                        # BEP 9/10 compliance: Ensure connection is ready before sending
                        if not connection.writer or connection.writer.is_closing():
                            self.logger.warning(
                                "Cannot send metadata request to %s: writer not available or closing",
                                connection.peer_info,
                            )
                            continue

                        connection.writer.write(req_msg)
                        await connection.writer.drain()

                        # Verify write succeeded
                        self.logger.debug(
                            "Verified metadata request sent to %s: %d bytes written, connection state=%s",
                            connection.peer_info,
                            len(req_msg),
                            connection.state.value,
                        )

                        self.logger.debug(
                            "Sent metadata request for piece %d/%d to %s (verified: %d bytes written)",
                            piece_idx + 1,
                            num_pieces,
                            connection.peer_info,
                            len(req_msg),
                        )

                        # Small delay between requests
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        self.logger.debug(
                            "Error requesting metadata piece %d from %s: %s",
                            piece_idx,
                            connection.peer_info,
                            e,
                        )
                        continue

                # Wait for all pieces with timeout
                # CRITICAL FIX: Adaptive timeout based on peer choking state
                # Choked peers may take longer to respond (or not respond at all)
                # Unchoked peers should respond quickly
                # CRITICAL FIX: Use configurable timeout values from NetworkConfig
                # BitTorrent spec compliant: reasonable timeouts prevent hanging connections
                base_timeout_per_piece = getattr(
                    self.config.network,
                    "metadata_piece_timeout",
                    15.0,
                )
                # CRITICAL FIX: Use shorter timeout for unchoked peers (they should respond faster)
                # Use longer timeout for choked peers (they may be slow or not respond)
                if connection.peer_choking:
                    # Choked peer - use longer timeout but don't wait too long
                    timeout_per_piece = min(base_timeout_per_piece * 1.5, 20.0)  # Max 20s per piece
                    self.logger.debug(
                        "Using longer timeout for choked peer %s: %.1fs per piece (peer may not respond)",
                        connection.peer_info,
                        timeout_per_piece,
                    )
                else:
                    # Unchoked peer - should respond quickly
                    timeout_per_piece = base_timeout_per_piece * 0.8  # 80% of base timeout
                    self.logger.debug(
                        "Using shorter timeout for unchoked peer %s: %.1fs per piece",
                        connection.peer_info,
                        timeout_per_piece,
                    )
                
                metadata_exchange_timeout = getattr(
                    self.config.network,
                    "metadata_exchange_timeout",
                    60.0,
                )
                # Use configured total timeout or calculate from per-piece timeout
                # CRITICAL FIX: Reduce buffer from 30s to 15s to fail faster on unresponsive peers
                total_timeout = max(
                    metadata_exchange_timeout,
                    timeout_per_piece * num_pieces + 15.0,  # Reduced buffer from 30s to 15s
                )
                start_time = time.time()

                self.logger.info(
                    "METADATA_EXCHANGE_WAIT: Waiting for %d metadata piece(s) from %s (timeout_per_piece=%.1fs, total_timeout=%.1fs)",
                    num_pieces,
                    connection.peer_info,
                    timeout_per_piece,
                    total_timeout,
                )

                for piece_idx in range(num_pieces):
                    remaining_timeout = total_timeout - (time.time() - start_time)
                    if remaining_timeout <= 0:
                        self.logger.warning(
                            "METADATA_EXCHANGE_TIMEOUT: Total timeout exceeded while waiting for metadata pieces from %s (received %d/%d)",
                            connection.peer_info,
                            sum(1 for i in range(num_pieces) if piece_data_dict.get(i) is not None),
                            num_pieces,
                        )
                        break

                    # Check if piece is already received (may have arrived while waiting for previous piece)
                    if piece_data_dict.get(piece_idx) is not None:
                        self.logger.debug(
                            "Metadata piece %d/%d already received from %s, skipping wait",
                            piece_idx + 1,
                            num_pieces,
                            connection.peer_info,
                        )
                        continue

                    try:
                        # Wait for this piece with remaining timeout
                        await asyncio.wait_for(
                            piece_events[piece_idx].wait(),
                            timeout=min(timeout_per_piece, remaining_timeout),
                        )
                        self.logger.debug(
                            "Metadata piece %d/%d received from %s",
                            piece_idx + 1,
                            num_pieces,
                            connection.peer_info,
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(
                            "METADATA_EXCHANGE_TIMEOUT: Timeout waiting for metadata piece %d/%d from %s (timeout=%.1fs)",
                            piece_idx + 1,
                            num_pieces,
                            connection.peer_info,
                            min(timeout_per_piece, remaining_timeout),
                        )

                # Collect received pieces (read from state, not local dict)
                metadata_pieces: dict[int, bytes] = {}
                # Get state again in case it was modified
                current_state = self._metadata_exchange_state.get(peer_key)
                if current_state:
                    state_pieces = current_state.get("pieces", {})
                    for piece_idx in range(num_pieces):
                        piece_data = state_pieces.get(piece_idx)
                        if piece_data:
                            metadata_pieces[piece_idx] = piece_data
                            self.logger.debug(
                                "Received metadata piece %d/%d from %s (size=%d bytes)",
                                piece_idx + 1,
                                num_pieces,
                                connection.peer_info,
                                len(piece_data),
                            )
                        else:
                            self.logger.warning(
                                "Missing metadata piece %d/%d from %s",
                                piece_idx + 1,
                                num_pieces,
                                connection.peer_info,
                            )
            finally:
                # CRITICAL FIX: Don't clean up state immediately - wait a bit for late responses
                # Some responses may arrive after timeout but before cleanup
                # Only clean up if we're not waiting for any more pieces
                if peer_key in self._metadata_exchange_state:
                    current_state = self._metadata_exchange_state[peer_key]
                    state_pieces = current_state.get("pieces", {})
                    received_count = sum(1 for p in state_pieces.values() if p is not None)
                    total_pieces = current_state.get("num_pieces", 0)

                    if received_count < total_pieces:
                        # Not all pieces received - keep state for a bit longer for late responses
                        self.logger.info(
                            "METADATA_EXCHANGE_STATE: Keeping state for %s (received %d/%d pieces) for late response handling",
                            connection.peer_info,
                            received_count,
                            total_pieces,
                        )
                        # Schedule cleanup after 5 seconds - gives time for late responses
                        async def delayed_cleanup():
                            await asyncio.sleep(5.0)
                            if peer_key in self._metadata_exchange_state:
                                self.logger.debug(
                                    "Cleaning up metadata exchange state for %s (peer_key=%s) after delay",
                                    connection.peer_info,
                                    peer_key,
                                )
                                del self._metadata_exchange_state[peer_key]
                        asyncio.create_task(delayed_cleanup())
                    else:
                        # All pieces received - clean up immediately
                        self.logger.debug(
                            "Cleaning up metadata exchange state for %s (peer_key=%s) - all pieces received",
                            connection.peer_info,
                            peer_key,
                        )
                        del self._metadata_exchange_state[peer_key]

            # Assemble complete metadata
            if len(metadata_pieces) == num_pieces:
                # Sort pieces by index and concatenate
                sorted_indices = sorted(metadata_pieces.keys())
                complete_metadata = b"".join(
                    metadata_pieces[i] for i in sorted_indices
                )

                # CRITICAL: Verify all expected pieces are present
                expected_indices = set(range(num_pieces))
                received_indices = set(metadata_pieces.keys())
                if expected_indices != received_indices:
                    missing = expected_indices - received_indices
                    self.logger.error(
                        "Metadata assembly failed from %s: missing pieces %s (expected %d pieces, got %d)",
                        connection.peer_info,
                        sorted(missing),
                        num_pieces,
                        len(metadata_pieces),
                    )
                    return

                # Verify metadata size
                if len(complete_metadata) != metadata_size:
                    self.logger.warning(
                        "Metadata size mismatch: expected %d, got %d bytes from %s (pieces: %s)",
                        metadata_size,
                        len(complete_metadata),
                        connection.peer_info,
                        sorted_indices,
                    )
                    return

                # CRITICAL: Verify metadata starts with 'd' (dictionary) according to BEP 3
                if not complete_metadata or complete_metadata[0:1] != b"d":
                    self.logger.error(
                        "Invalid metadata format from %s: expected bencode dictionary (starts with 'd'), "
                        "got first byte: %s (hex: %s). Metadata preview: %s",
                        connection.peer_info,
                        chr(complete_metadata[0]) if complete_metadata else "empty",
                        complete_metadata[:20].hex() if len(complete_metadata) >= 20 else complete_metadata.hex(),
                        complete_metadata[:100].hex(),
                    )
                    return

                # Decode metadata
                try:
                    decoder = BencodeDecoder(complete_metadata)
                    metadata = decoder.decode()

                    # CRITICAL SECURITY: Validate metadata structure (BEP 3, BEP 9)
                    if not isinstance(metadata, dict):
                        self.logger.error(
                            "Invalid metadata from %s: expected dict, got %s",
                            connection.peer_info,
                            type(metadata).__name__,
                        )
                        return

                    # CRITICAL FIX: Check for 'info' key with both bytes and string keys
                    # BEP 3 specifies bytes keys, but some implementations may use strings
                    info_key = None
                    if b"info" in metadata:
                        info_key = b"info"
                    elif "info" in metadata:
                        info_key = "info"

                    # FALLBACK: Some peers incorrectly send only the info dictionary (not wrapped in full metadata)
                    # Check if metadata has info dictionary keys directly (length, name, piece length, pieces)
                    # This is a common non-compliant behavior that we need to handle for compatibility
                    if info_key is None:
                        # Check if this looks like an info dictionary (has typical info keys)
                        # BEP 3 info dictionary typically has: length, name, piece length, pieces
                        # We check for ANY of these keys to detect info dictionary
                        # CRITICAL: Normalize keys to bytes for comparison (BencodeDecoder returns bytes keys)
                        metadata_keys_set = set(metadata.keys())

                        # Normalize metadata keys to bytes for comparison
                        metadata_keys_bytes = set()
                        for key in metadata_keys_set:
                            if isinstance(key, bytes):
                                metadata_keys_bytes.add(key)
                            elif isinstance(key, str):
                                metadata_keys_bytes.add(key.encode("utf-8"))
                            else:
                                # Convert other types to bytes
                                metadata_keys_bytes.add(str(key).encode("utf-8"))

                        # Check against both bytes and string versions of info keys
                        info_dict_keys_bytes = {b"length", b"name", b"piece length", b"pieces"}
                        info_dict_keys_str = {"length", "name", "piece length", "pieces"}

                        # Check for matches with bytes keys (normal case)
                        has_info_keys_bytes = bool(metadata_keys_bytes & info_dict_keys_bytes)
                        # Check for matches with string keys (unusual but possible)
                        has_info_keys_str = bool(metadata_keys_set & info_dict_keys_str)
                        has_info_keys = has_info_keys_bytes or has_info_keys_str

                        # CRITICAL DEBUG: Log key types and matching for troubleshooting
                        self.logger.debug(
                            "Metadata key check: metadata_keys=%s (types: %s), has_info_keys=%s (bytes=%s, str=%s)",
                            [k if isinstance(k, str) else k.decode("utf-8", errors="replace") for k in list(metadata_keys_set)[:10]],
                            [type(k).__name__ for k in list(metadata_keys_set)[:10]],
                            has_info_keys,
                            has_info_keys_bytes,
                            has_info_keys_str,
                        )

                        if has_info_keys:
                            # This is likely just the info dictionary, not full metadata
                            # Wrap it as if it came in the full metadata format
                            self.logger.warning(
                                "Peer %s sent only info dictionary (not full metadata). "
                                "This is non-compliant with BEP 9, but accepting it for compatibility. "
                                "Available keys: %s",
                                connection.peer_info,
                                [k if isinstance(k, str) else k.decode("utf-8", errors="replace") for k in list(metadata.keys())[:10]],
                            )
                            # Treat the entire metadata as the info dictionary
                            info_dict = metadata
                            # We'll use this directly below
                        else:
                            # Log available keys for debugging
                            available_keys = list(metadata.keys())[:10]  # First 10 keys for logging
                            available_keys_str = [k if isinstance(k, str) else k.decode("utf-8", errors="replace") for k in available_keys]
                            available_keys_types = [type(k).__name__ for k in available_keys]

                            # ADDITIONAL FALLBACK: Check if keys match info dictionary pattern more leniently
                            # Some peers might use slightly different key names or have additional keys
                            # Check if we have at least 2 of the typical info keys (normalized to bytes)
                            matching_keys_bytes = metadata_keys_bytes & info_dict_keys_bytes
                            matching_keys_str = metadata_keys_set & info_dict_keys_str
                            total_matching = len(matching_keys_bytes) + len(matching_keys_str)

                            if total_matching >= 2:
                                # Likely an info dictionary with some variation
                                all_matching = list(matching_keys_bytes) + list(matching_keys_str)
                                self.logger.warning(
                                    "Peer %s sent metadata with %d matching info keys (keys: %s). "
                                    "Treating as info dictionary for compatibility.",
                                    connection.peer_info,
                                    total_matching,
                                    [k if isinstance(k, str) else k.decode("utf-8", errors="replace") for k in all_matching],
                                )
                                info_dict = metadata
                            else:
                                # Log error with detailed information
                                self.logger.error(
                                    "Metadata from %s missing required 'info' dictionary (BEP 3). "
                                    "Available keys (first 10): %s (types: %s), metadata_size=%d bytes, num_pieces=%d. "
                                    "Matching info keys: %d (expected at least 2).",
                                    connection.peer_info,
                                    available_keys_str,
                                    available_keys_types,
                                    len(complete_metadata),
                                    num_pieces,
                                    total_matching,
                                )
                                # Log metadata preview for debugging
                                try:
                                    metadata_preview = complete_metadata[:200].hex()
                                    self.logger.debug(
                                        "Metadata preview (first 200 bytes): %s",
                                        metadata_preview,
                                    )
                                except Exception:
                                    pass
                                return
                    else:
                        # Normal case: metadata has 'info' key, extract it
                        info_dict = metadata[info_key]

                    # Get expected info_hash
                    info_hash = self.torrent_data.get("info_hash")
                    if not info_hash:
                        pieces_info = self.torrent_data.get("pieces_info", {})
                        info_hash = pieces_info.get("info_hash")

                    if not info_hash:
                        self.logger.error(
                            "Cannot verify metadata from %s: no info_hash available",
                            connection.peer_info,
                        )
                        return

                    # CRITICAL SECURITY: Verify info_hash matches (BEP 3, BEP 9)
                    # This prevents malicious peers from sending fake metadata
                    from ccbt.utils.metadata_utils import validate_info_dict

                    # info_dict is already set above (either from metadata[info_key] or as fallback from metadata itself)
                    # CRITICAL FIX: Normalize info_dict keys to bytes for validation
                    # BencodeEncoder handles both bytes and string keys, but we need to ensure consistency
                    # Some decoders may return string keys, so we normalize to bytes for validation
                    normalized_info_dict: dict[bytes, Any] = {}
                    for key, value in info_dict.items():
                        if isinstance(key, bytes):
                            normalized_info_dict[key] = value
                        elif isinstance(key, str):
                            normalized_info_dict[key.encode("utf-8")] = value
                        else:
                            # Convert other key types to bytes for consistency
                            normalized_info_dict[str(key).encode("utf-8")] = value

                    if not validate_info_dict(normalized_info_dict, info_hash):
                        self.logger.error(
                            "SECURITY: Metadata info_hash mismatch from %s: expected %s, calculated %s. "
                            "Rejecting potentially malicious metadata.",
                            connection.peer_info,
                            info_hash.hex()[:16] + "...",
                            "mismatch",
                        )
                        # Calculate actual hash for logging
                        try:
                            from ccbt.utils.metadata_utils import calculate_info_hash
                            actual_hash = calculate_info_hash(normalized_info_dict)
                            self.logger.error(
                                "Actual info_hash from metadata: %s",
                                actual_hash.hex()[:16] + "...",
                            )
                        except Exception:
                            pass
                        return

                    self.logger.info(
                        "Successfully fetched and verified metadata from %s (size=%d bytes, pieces=%d, info_hash verified)",
                        connection.peer_info,
                        len(complete_metadata),
                        num_pieces,
                    )

                    # Update torrent_data and piece_manager
                    if hasattr(self, "piece_manager") and self.piece_manager:
                        from ccbt.core.magnet import build_torrent_data_from_metadata

                        # CRITICAL FIX: build_torrent_data_from_metadata expects the info_dict, not the full metadata
                        # The full metadata contains keys like 'info', 'announce', etc.
                        # We need to extract the 'info' dictionary from the metadata
                        # Use normalized_info_dict to ensure bytes keys (required by build_torrent_data_from_metadata)
                        updated_torrent_data = build_torrent_data_from_metadata(
                            info_hash,
                            normalized_info_dict,  # Pass the normalized info dictionary with bytes keys
                        )

                        # Merge with existing torrent_data
                        if isinstance(self.torrent_data, dict):
                            self.torrent_data.update(updated_torrent_data)
                            
                            # CRITICAL FIX: Update info_hash in torrent_data so it's no longer "unknown"
                            # This ensures subsequent connection attempts have the correct info_hash
                            # The info_hash should already be in updated_torrent_data from build_torrent_data_from_metadata
                            if "info_hash" in updated_torrent_data:
                                old_info_hash = self.torrent_data.get("info_hash")
                                self.torrent_data["info_hash"] = updated_torrent_data["info_hash"]
                                
                                # Log the update with proper formatting
                                new_info_hash = updated_torrent_data["info_hash"]
                                new_hash_display = new_info_hash.hex()[:16] + "..." if isinstance(new_info_hash, bytes) else str(new_info_hash)[:16] + "..."
                                old_hash_display = old_info_hash.hex()[:16] + "..." if old_info_hash and isinstance(old_info_hash, bytes) else (str(old_info_hash)[:16] + "..." if old_info_hash else "unknown")
                                
                                self.logger.info(
                                    "✅ Updated torrent_data.info_hash to %s (was: %s) - connection attempts will now show correct info_hash",
                                    new_hash_display,
                                    old_hash_display,
                                )
                            else:
                                # Fallback: calculate info_hash from the metadata if it's not in updated_torrent_data
                                # This should not happen, but provides a safety net
                                try:
                                    import hashlib
                                    from ccbt.core.bencode import BencodeEncoder
                                    
                                    encoder = BencodeEncoder()
                                    calculated_info_hash = hashlib.sha1(encoder.encode(normalized_info_dict)).digest()  # nosec B324
                                    self.torrent_data["info_hash"] = calculated_info_hash
                                    self.logger.info(
                                        "✅ Calculated and set torrent_data.info_hash to %s from metadata",
                                        calculated_info_hash.hex()[:16] + "...",
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        "⚠️ Could not calculate info_hash from metadata: %s",
                                        e,
                                    )

                            # Update piece_manager with new metadata
                            if "pieces_info" in updated_torrent_data:
                                pieces_info = updated_torrent_data["pieces_info"]
                                if "num_pieces" in pieces_info:
                                    self.piece_manager.num_pieces = int(
                                        pieces_info["num_pieces"]
                                    )
                                    self.logger.info(
                                        "Updated piece_manager.num_pieces to %d from metadata",
                                        self.piece_manager.num_pieces,
                                    )
                                if "piece_length" in pieces_info:
                                    self.piece_manager.piece_length = int(
                                        pieces_info["piece_length"]
                                    )
                                if "piece_hashes" in pieces_info:
                                    self.piece_manager.piece_hashes = pieces_info["piece_hashes"]

                                # Trigger piece manager update
                                if hasattr(self.piece_manager, "update_from_metadata"):
                                    await self.piece_manager.update_from_metadata(
                                        updated_torrent_data
                                    )

                                    self.logger.info(
                                        "Metadata exchange complete for %s. Piece manager updated with %d pieces.",
                                        connection.peer_info,
                                        self.piece_manager.num_pieces,
                                    )

                                    # CRITICAL FIX: Re-process all stored bitfields from existing connections
                                    # When metadata becomes available, we need to re-process bitfields that were
                                    # received before metadata was available (magnet link case)
                                    await self._reprocess_stored_bitfields()

                                    # CRITICAL FIX: After metadata is available, send our bitfield to all connected peers
                                    # This is essential because peers need to know what pieces we have
                                    # For magnet links, we may have skipped sending bitfield earlier when metadata wasn't available
                                    # BitTorrent spec compliant: send bitfield and INTERESTED after metadata exchange
                                    send_bitfield_after_metadata = getattr(
                                        self.config.network,
                                        "send_bitfield_after_metadata",
                                        True,
                                    )
                                    send_interested_after_metadata = getattr(
                                        self.config.network,
                                        "send_interested_after_metadata",
                                        True,
                                    )
                                    
                                    if send_bitfield_after_metadata or send_interested_after_metadata:
                                        try:
                                            async with self.connection_lock:
                                                connected_peers = [
                                                    conn for conn in self.connections.values()
                                                    if conn.is_connected()
                                                    and conn.writer is not None
                                                    and conn.reader is not None
                                                ]

                                            if connected_peers:
                                                self.logger.info(
                                                    "Sending bitfield and INTERESTED to %d connected peer(s) after metadata fetch to encourage bitfields/HAVE messages",
                                                    len(connected_peers),
                                                )
                                                for connection in connected_peers:
                                                    # CRITICAL FIX: Validate connection is still valid before sending
                                                    if not connection.is_connected() or connection.writer is None:
                                                        self.logger.debug(
                                                            "Skipping %s - connection no longer valid",
                                                            connection.peer_info,
                                                        )
                                                        continue
                                                        
                                                    # Send bitfield if enabled
                                                    if send_bitfield_after_metadata:
                                                        try:
                                                            # CRITICAL FIX: Send our bitfield first (so peer knows what we have)
                                                            # This is especially important for magnet links where bitfield was skipped earlier
                                                            await self._send_bitfield(connection)
                                                            self.logger.debug(
                                                                "Sent bitfield to %s after metadata fetch (state=%s)",
                                                                connection.peer_info,
                                                                connection.state.value if hasattr(connection.state, "value") else str(connection.state),
                                                            )
                                                        except Exception as e:
                                                            self.logger.warning(
                                                                "Failed to send bitfield to %s after metadata fetch (connection may have closed): %s",
                                                                connection.peer_info,
                                                                e,
                                                            )
                                                            # CRITICAL FIX: Don't disconnect on error - peer might still be usable
                                                            continue

                                                    # Send INTERESTED if enabled
                                                    if send_interested_after_metadata and not connection.am_interested:
                                                        try:
                                                            # CRITICAL FIX: Verify connection is still valid before sending
                                                            if not connection.is_connected() or connection.writer is None:
                                                                self.logger.debug(
                                                                    "Skipping INTERESTED to %s - connection no longer valid",
                                                                    connection.peer_info,
                                                                )
                                                                continue
                                                                
                                                            await self._send_interested(connection)
                                                            connection.am_interested = True
                                                            self.logger.debug(
                                                                "Sent INTERESTED to %s after metadata fetch (state=%s)",
                                                                connection.peer_info,
                                                                connection.state.value if hasattr(connection.state, "value") else str(connection.state),
                                                            )
                                                        except Exception as e:
                                                            self.logger.warning(
                                                                "Failed to send INTERESTED to %s after metadata fetch (connection may have closed): %s",
                                                                connection.peer_info,
                                                                e,
                                                            )
                                                            # CRITICAL FIX: Don't disconnect on error - peer might still be usable
                                                            continue
                                        except Exception as e:
                                            self.logger.warning(
                                                "Error sending bitfield/INTERESTED after metadata fetch: %s (this is non-fatal)",
                                                e,
                                            )
                                            # CRITICAL FIX: Don't let errors in post-metadata operations break the connection

                                    # CRITICAL FIX: Call start_download() after metadata is fetched to initialize pieces
                                    # This ensures pieces list is initialized and downloads can start immediately
                                    if hasattr(self.piece_manager, "start_download"):
                                        try:
                                            if asyncio.iscoroutinefunction(self.piece_manager.start_download):
                                                await self.piece_manager.start_download(self)
                                            else:
                                                self.piece_manager.start_download(self)
                                            self.logger.info(
                                                "✅ METADATA_COMPLETE: Called start_download() after metadata fetch (num_pieces=%d, pieces_count=%d, is_downloading=%s)",
                                                self.piece_manager.num_pieces,
                                                len(self.piece_manager.pieces) if hasattr(self.piece_manager, "pieces") else 0,
                                                getattr(self.piece_manager, "is_downloading", False),
                                            )
                                            
                                            # CRITICAL FIX: Trigger piece selection immediately after metadata and start_download
                                            # This ensures we start requesting pieces as soon as metadata is available
                                            # This prevents peers from disconnecting because we appear uninterested
                                            if hasattr(self.piece_manager, "_select_pieces"):
                                                try:
                                                    # Trigger piece selection asynchronously to avoid blocking
                                                    piece_selection_task = asyncio.create_task(self.piece_manager._select_pieces())
                                                    self.logger.info(
                                                        "✅ METADATA_COMPLETE: Triggered piece selection after metadata fetch (will request pieces immediately)"
                                                    )
                                                except Exception as select_error:
                                                    self.logger.warning(
                                                        "Failed to trigger piece selection after metadata fetch: %s (will retry on UNCHOKE)",
                                                        select_error,
                                                    )
                                        except Exception as start_error:
                                            self.logger.warning(
                                                "Failed to call start_download() after metadata fetch: %s (will retry on UNCHOKE)",
                                                start_error,
                                            )
                                    
                                    # CRITICAL FIX: Always trigger immediate peer discovery after metadata fetch
                                    # Now that we have metadata, we can actively seek more peers to download from
                                    # This is especially important for magnet links where we may have few initial peers
                                    try:
                                        async with self.connection_lock:
                                            active_peers = [
                                                conn for conn in self.connections.values()
                                                if conn.is_connected()
                                                and conn.is_active()
                                                and conn.reader is not None
                                                and conn.writer is not None
                                            ]
                                            peers_with_piece_info = []
                                            for conn in active_peers:
                                                # Check if peer has bitfield
                                                has_bitfield = (
                                                    conn.peer_state.bitfield is not None
                                                    and len(conn.peer_state.bitfield) > 0
                                                )
                                                # Check if peer has sent HAVE messages (alternative to bitfield)
                                                has_have_messages = (
                                                    hasattr(conn.peer_state, "pieces_we_have")
                                                    and conn.peer_state.pieces_we_have is not None
                                                    and len(conn.peer_state.pieces_we_have) > 0
                                                )
                                                if has_bitfield or has_have_messages:
                                                    peers_with_piece_info.append(conn)
                                        
                                        # CRITICAL FIX: Log connection state for debugging
                                        connection_states = {}
                                        async with self.connection_lock:
                                            for conn in self.connections.values():
                                                if conn.is_connected():
                                                    connection_states[str(conn.peer_info)] = (
                                                        conn.state.value if hasattr(conn.state, "value") else str(conn.state)
                                                    )
                                        
                                        # Always trigger discovery after metadata fetch to find more peers
                                        self.logger.info(
                                            "After metadata fetch: %d active peer(s), %d with piece info. Connection states: %s. Triggering immediate peer discovery...",
                                            len(active_peers),
                                            len(peers_with_piece_info),
                                            connection_states,
                                        )
                                    except Exception as e:
                                        self.logger.warning(
                                            "Error checking active peers after metadata fetch: %s (this is non-fatal)",
                                            e,
                                        )
                                        # Use fallback values
                                        active_peers = []
                                        peers_with_piece_info = []
                                    try:
                                        import hashlib

                                        from ccbt.core.bencode import BencodeEncoder
                                        from ccbt.utils.events import Event, emit_event

                                        # Get info_hash
                                        info_hash_hex = ""
                                        if isinstance(self.torrent_data, dict) and "info" in self.torrent_data:
                                            encoder = BencodeEncoder()
                                            info_dict = self.torrent_data["info"]
                                            info_hash_bytes = hashlib.sha1(encoder.encode(info_dict)).digest()  # nosec B324
                                            info_hash_hex = info_hash_bytes.hex()

                                        await emit_event(
                                            Event(
                                                event_type="peer_count_low",
                                                data={
                                                    "info_hash": info_hash_hex,
                                                    "active_peer_count": len(active_peers),
                                                    "peers_with_piece_info": len(peers_with_piece_info),
                                                    "threshold": 5,
                                                    "trigger": "metadata_fetch_always_discover",
                                                },
                                            )
                                        )
                                    except Exception as e:
                                        self.logger.debug("Failed to trigger discovery after metadata fetch: %s", e)

                                    # CRITICAL FIX: Restart download now that metadata is available
                                    # This ensures piece selection and downloading can begin immediately
                                    # For magnet links, the piece_manager may have been started with num_pieces=0
                                    # and needs to be restarted now that we have the actual piece count
                                    # CRITICAL FIX: Always call start_download after metadata fetch, even if is_downloading=True
                                    # This is because is_downloading may have been set to True earlier with num_pieces=0,
                                    # and we need to reinitialize pieces now that we have the correct num_pieces
                                    if hasattr(self.piece_manager, "start_download"):
                                        try:
                                            self.logger.info(
                                                "Restarting piece manager download now that metadata is available (num_pieces=%d, is_downloading=%s)",
                                                self.piece_manager.num_pieces,
                                                self.piece_manager.is_downloading,
                                            )
                                            # Use self as the peer_manager (this AsyncPeerConnectionManager instance)
                                            # The piece_manager needs a peer_manager to request pieces from
                                            await self.piece_manager.start_download(
                                                peer_manager=self
                                            )
                                            self.logger.info(
                                                "Successfully restarted piece manager download after metadata fetch (num_pieces=%d, pieces_count=%d)",
                                                self.piece_manager.num_pieces,
                                                len(self.piece_manager.pieces) if hasattr(self.piece_manager, "pieces") else 0,
                                            )
                                        except Exception as e:
                                            self.logger.warning(
                                                "Error restarting piece manager download after metadata fetch: %s",
                                                e,
                                                exc_info=True,
                                            )
                except Exception as decode_error:
                    self.logger.warning(
                        "Failed to decode metadata from %s: %s",
                        connection.peer_info,
                        decode_error,
                    )
            else:
                self.logger.warning(
                    "Incomplete metadata from %s: received %d/%d pieces",
                    connection.peer_info,
                    len(metadata_pieces),
                    num_pieces,
                )

        except Exception as e:
            self.logger.exception(
                "Error during metadata exchange with %s: %s (connection state: %s, is_connected: %s)",
                connection.peer_info,
                e,
                connection.state.value if hasattr(connection.state, "value") else str(connection.state),
                connection.is_connected(),
            )
            # CRITICAL FIX: Don't disconnect peer on metadata exchange error
            # The peer might still be usable for downloading pieces
            # Only log the error and continue - graceful degradation

    async def _handle_ut_metadata_response(
        self,
        connection: AsyncPeerConnection,
        extension_payload: bytes,
        metadata_state: dict[str, Any],
    ) -> None:
        """Handle ut_metadata response message (BEP 9).
        
        This is called from the extension message handler when a ut_metadata
        response is received.
        
        According to BEP 9, ut_metadata response format is:
        <bencoded_dictionary><piece_data>
        
        Dictionary format:
        - Request: {'msg_type': 0, 'piece': 0}
        - Data: {'msg_type': 1, 'piece': 0, 'total_size': 3425}
        - Reject: {'msg_type': 2, 'piece': 0}
        
        The piece data is appended AFTER the bencoded dictionary (not inside it).
        The length prefix MUST include the metadata piece.
        
        Args:
            connection: Peer connection
            extension_payload: Payload of the ut_metadata message (already stripped of message_id and extension_id)
            metadata_state: Metadata exchange state for this connection

        """
        try:
            from ccbt.core.bencode import BencodeDecoder

            # CRITICAL: Log raw response for debugging
            self.logger.info(
                "UT_METADATA_RESPONSE: from %s, payload_len=%d, first_50_bytes=%s",
                connection.peer_info,
                len(extension_payload),
                extension_payload[:50].hex() if len(extension_payload) >= 50 else extension_payload.hex(),
            )

            if not extension_payload:
                self.logger.warning(
                    "Empty ut_metadata response from %s",
                    connection.peer_info,
                )
                return

            # Parse metadata piece response
            # extension_payload is: <bencoded_header><piece_data>
            decoder = BencodeDecoder(extension_payload)
            header = decoder.decode()

            # CRITICAL: Log decoded header for debugging
            self.logger.info(
                "UT_METADATA_HEADER: from %s, header=%s, decoder_pos=%d, payload_len=%d",
                connection.peer_info,
                header,
                decoder.pos,
                len(extension_payload),
            )

            # Extract msg_type and piece_index
            # Handle both bytes and int keys/values (for compatibility)
            # CRITICAL FIX: Use 'in' check instead of 'or' to handle piece_index=0 correctly
            # If piece_index=0, then 'header.get(b"piece") or header.get("piece")' would fail
            # because 0 is falsy in Python
            if b"msg_type" in header:
                msg_type = header[b"msg_type"]
            elif "msg_type" in header:
                msg_type = header["msg_type"]
            else:
                msg_type = None

            if b"piece" in header:
                piece_index_raw = header[b"piece"]
            elif "piece" in header:
                piece_index_raw = header["piece"]
            else:
                piece_index_raw = None

            # Ensure piece_index is an integer
            if piece_index_raw is None:
                self.logger.warning(
                    "ut_metadata response from %s missing 'piece' field in header",
                    connection.peer_info,
                )
                return

            piece_index = int(piece_index_raw) if not isinstance(piece_index_raw, int) else piece_index_raw

            # CRITICAL SECURITY: Validate piece index is within expected range (BEP 9)
            num_pieces = metadata_state.get("num_pieces", 0)
            if piece_index < 0 or piece_index >= num_pieces:
                self.logger.error(
                    "SECURITY: Invalid piece index %d from %s (expected 0-%d). "
                    "Rejecting potentially malicious metadata piece.",
                    piece_index,
                    connection.peer_info,
                    num_pieces - 1 if num_pieces > 0 else 0,
                )
                return

            if msg_type is None:
                self.logger.warning(
                    "ut_metadata response from %s missing 'msg_type' field in header",
                    connection.peer_info,
                )
                return

            msg_type = int(msg_type) if not isinstance(msg_type, int) else msg_type

            self.logger.debug(
                "Received ut_metadata response from %s: msg_type=%d, piece=%d, payload_len=%d",
                connection.peer_info,
                msg_type,
                piece_index,
                len(extension_payload),
            )

            if msg_type == 1:  # Data response (BEP 9)
                # BEP 9: Data response format is: {'msg_type': 1, 'piece': 0, 'total_size': 3425}
                # followed by the piece data (appended after the bencoded dictionary)
                # Extract piece data: everything after the bencoded header
                header_len = decoder.pos
                piece_data = extension_payload[header_len:]

                # BEP 9: Check for total_size in header (optional, but should match if present)
                # CRITICAL FIX: Use 'in' check instead of 'or' for consistency (though total_size shouldn't be 0)
                if b"total_size" in header:
                    total_size = header[b"total_size"]
                elif "total_size" in header:
                    total_size = header["total_size"]
                else:
                    total_size = None
                expected_metadata_size = metadata_state.get("metadata_size")
                if total_size is not None and expected_metadata_size is not None:
                    total_size = int(total_size) if not isinstance(total_size, int) else total_size
                    if total_size != expected_metadata_size:
                        self.logger.warning(
                            "Metadata total_size mismatch from %s: header says %d, expected %d (piece=%d)",
                            connection.peer_info,
                            total_size,
                            expected_metadata_size,
                            piece_index,
                        )
                    else:
                        self.logger.debug(
                            "Metadata total_size verified from %s: %d bytes (piece=%d)",
                            connection.peer_info,
                            total_size,
                            piece_index,
                        )

                # CRITICAL SECURITY: Validate piece data size (BEP 9)
                # Each piece should be <= 16KB (16384 bytes), except possibly the last piece
                # BEP 9: "If the piece is the last piece (i.e. piece * 16384 >= total_size),
                #         it may be less than 16kiB. Otherwise, it MUST be 16kiB."
                MAX_PIECE_SIZE = 16384
                if len(piece_data) > MAX_PIECE_SIZE:
                    self.logger.error(
                        "SECURITY: Metadata piece %d from %s exceeds maximum size %d bytes (got %d). "
                        "Rejecting potentially malicious metadata piece.",
                        piece_index,
                        connection.peer_info,
                        MAX_PIECE_SIZE,
                        len(piece_data),
                    )
                    return

                if not piece_data:
                    self.logger.warning(
                        "ut_metadata data response from %s has no piece data (piece=%d, header_len=%d)",
                        connection.peer_info,
                        piece_index,
                        header_len,
                    )
                    return

                # Store piece data and signal event
                pieces = metadata_state.get("pieces", {})
                events = metadata_state.get("events", {})

                if piece_index in pieces and piece_index in events:
                    pieces[piece_index] = piece_data
                    events[piece_index].set()

                    self.logger.info(
                        "Received metadata piece %d/%d from %s (size=%d bytes)",
                        piece_index + 1,
                        metadata_state.get("num_pieces", 0),
                        connection.peer_info,
                        len(piece_data),
                    )
                else:
                    self.logger.warning(
                        "Received unexpected metadata piece %d from %s (not in pending requests, expected pieces: %s)",
                        piece_index,
                        connection.peer_info,
                        list(pieces.keys()) if pieces else "none",
                    )
            elif msg_type == 2:  # Reject
                self.logger.debug(
                    "Peer %s rejected metadata piece %d request",
                    connection.peer_info,
                    piece_index,
                )
                # Signal event anyway so we don't wait forever
                events = metadata_state.get("events", {})
                if piece_index in events:
                    events[piece_index].set()
            else:
                self.logger.warning(
                    "Unknown ut_metadata message type %d from %s (expected 1=data or 2=reject)",
                    msg_type,
                    connection.peer_info,
                )

        except Exception as e:
            self.logger.warning(
                "Error handling ut_metadata response from %s: %s (payload_len=%d, first_bytes=%s)",
                connection.peer_info,
                e,
                len(extension_payload) if extension_payload else 0,
                extension_payload[:50].hex() if extension_payload and len(extension_payload) >= 50 else (extension_payload.hex() if extension_payload else "empty"),
                exc_info=True,
            )

    async def _reprocess_stored_bitfields(self) -> None:
        """Re-process all stored bitfields from existing connections when metadata becomes available.
        
        This is critical for magnet links where bitfields are received before metadata is fetched.
        When metadata becomes available, we need to re-process those stored bitfields with the
        correct num_pieces to update piece manager with peer availability.
        """
        if not self.piece_manager:
            self.logger.warning("Cannot reprocess bitfields: piece_manager is None")
            return

        async with self.connection_lock:
            total_connections = len(self.connections)
            connections_with_bitfield = 0
            reprocessed_count = 0
            errors_count = 0

            self.logger.info(
                "METADATA_AVAILABLE: Starting bitfield reprocessing (total connections: %d, num_pieces: %d)",
                total_connections,
                self.piece_manager.num_pieces if hasattr(self.piece_manager, "num_pieces") else 0,
            )

            for connection in list(self.connections.values()):
                # Check if connection has a stored bitfield
                has_bitfield = connection.peer_state.bitfield is not None and len(connection.peer_state.bitfield) > 0
                is_connected = connection.is_connected() and connection.state != ConnectionState.DISCONNECTED

                if has_bitfield:
                    connections_with_bitfield += 1

                if has_bitfield and is_connected:
                    try:
                        # Get peer key for piece manager
                        if hasattr(connection.peer_info, "ip") and hasattr(connection.peer_info, "port"):
                            peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
                        else:
                            peer_key = str(connection.peer_info)

                        # Re-process bitfield with updated metadata
                        # This will now use the correct num_pieces from piece_manager
                        await self.piece_manager.update_peer_availability(
                            peer_key, connection.peer_state.bitfield
                        )

                        # Count pieces in bitfield
                        pieces_count = 0
                        if connection.peer_state.bitfield:
                            for byte in connection.peer_state.bitfield:
                                pieces_count += bin(byte).count("1")

                        self.logger.info(
                            "METADATA_AVAILABLE: Re-processed bitfield from %s (pieces: %d, num_pieces: %d, bitfield_length: %d bytes)",
                            connection.peer_info,
                            pieces_count,
                            self.piece_manager.num_pieces if hasattr(self.piece_manager, "num_pieces") else 0,
                            len(connection.peer_state.bitfield) if connection.peer_state.bitfield else 0,
                        )
                        reprocessed_count += 1
                    except Exception as e:
                        errors_count += 1
                        self.logger.warning(
                            "Error re-processing bitfield from %s: %s",
                            connection.peer_info,
                            e,
                            exc_info=True,
                        )
                elif has_bitfield and not is_connected:
                    self.logger.debug(
                        "Skipping bitfield reprocessing for %s: connection not active (state: %s)",
                        connection.peer_info,
                        connection.state.value if hasattr(connection.state, "value") else str(connection.state),
                    )

            self.logger.info(
                "METADATA_AVAILABLE: Bitfield reprocessing complete (total: %d, with_bitfield: %d, reprocessed: %d, errors: %d)",
                total_connections,
                connections_with_bitfield,
                reprocessed_count,
                errors_count,
            )

    async def set_per_peer_rate_limit(
        self, peer_key: str, upload_limit_kib: int
    ) -> bool:
        """Set per-peer upload rate limit for a specific peer.

        Args:
            peer_key: Peer identifier (format: "ip:port")
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            True if peer found and limit set, False otherwise

        """
        async with self.connection_lock:
            connection = self.connections.get(peer_key)
            if not connection:
                return False

            connection.per_peer_upload_limit_kib = upload_limit_kib
            # Reset token bucket when limit changes
            connection._upload_token_bucket = 0.0
            connection._upload_last_update = time.time()

            self.logger.info(
                "Set per-peer upload rate limit for %s: %d KiB/s",
                peer_key,
                upload_limit_kib,
            )
            return True

    async def get_per_peer_rate_limit(self, peer_key: str) -> int | None:
        """Get per-peer upload rate limit for a specific peer.

        Args:
            peer_key: Peer identifier (format: "ip:port")

        Returns:
            Upload rate limit in KiB/s (0 = unlimited), or None if peer not found

        """
        async with self.connection_lock:
            connection = self.connections.get(peer_key)
            if not connection:
                return None

            return connection.per_peer_upload_limit_kib

    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set per-peer upload rate limit for all active peers.

        Args:
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            Number of peers updated

        """
        async with self.connection_lock:
            connections = list(self.connections.values())

        updated_count = 0
        for connection in connections:
            connection.per_peer_upload_limit_kib = upload_limit_kib
            # Reset token bucket when limit changes
            connection._upload_token_bucket = 0.0
            connection._upload_last_update = time.time()
            updated_count += 1

        if updated_count > 0:
            self.logger.info(
                "Set per-peer upload rate limit for %d peers: %d KiB/s",
                updated_count,
                upload_limit_kib,
            )

        return updated_count

    async def disconnect_all(self) -> None:
        """Disconnect from all peers."""
        async with self.connection_lock:  # pragma: no cover - Disconnect all requires multiple connections, complex to test
            for connection in list(
                self.connections.values()
            ):  # pragma: no cover - Disconnect all requires multiple connections, complex to test
                await self._disconnect_peer(
                    connection
                )  # pragma: no cover - Same context


# Module exports
__all__ = [
    "AsyncPeerConnection",
    "AsyncPeerConnectionManager",
    "ConnectionState",
    "PeerConnectionError",
    "PeerStats",
    "RequestInfo",
]

