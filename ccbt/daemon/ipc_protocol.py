"""IPC protocol definitions for daemon communication.

from __future__ import annotations

Defines constants, models, and types for HTTP REST and WebSocket IPC communication.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# API Constants
API_BASE_PATH = "/api/v1"
API_KEY_HEADER = "X-CCBT-API-Key"
SIGNATURE_HEADER = "X-CCBT-Signature"
PUBLIC_KEY_HEADER = "X-CCBT-Public-Key"
TIMESTAMP_HEADER = "X-CCBT-Timestamp"


class EventType(str, Enum):
    """WebSocket event types."""

    TORRENT_ADDED = "torrent_added"
    TORRENT_REMOVED = "torrent_removed"
    TORRENT_COMPLETED = "torrent_completed"
    TORRENT_STATUS_CHANGED = "torrent_status_changed"
    CONFIG_UPDATED = "config_updated"
    SHUTDOWN = "shutdown"
    SECURITY_BLACKLIST_UPDATED = "security_blacklist_updated"
    SECURITY_WHITELIST_UPDATED = "security_whitelist_updated"
    # Metadata exchange events
    METADATA_FETCH_STARTED = "metadata_fetch_started"
    METADATA_FETCH_PROGRESS = "metadata_fetch_progress"
    METADATA_FETCH_COMPLETED = "metadata_fetch_completed"
    METADATA_FETCH_FAILED = "metadata_fetch_failed"
    METADATA_READY = "metadata_ready"
    # File events
    FILE_SELECTION_CHANGED = "file_selection_changed"
    FILE_PRIORITY_CHANGED = "file_priority_changed"
    FILE_PROGRESS_UPDATED = "file_progress_updated"
    # Peer events
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    PEER_HANDSHAKE_COMPLETE = "peer_handshake_complete"
    PEER_BITFIELD_RECEIVED = "peer_bitfield_received"
    PEER_QUALITY_RANKED = "peer_quality_ranked"
    # Seeding events
    SEEDING_STARTED = "seeding_started"
    SEEDING_STOPPED = "seeding_stopped"
    SEEDING_STATS_UPDATED = "seeding_stats_updated"
    # Service/Component events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_RESTARTED = "service_restarted"
    COMPONENT_STARTED = "component_started"
    COMPONENT_STOPPED = "component_stopped"
    # Global stats events
    GLOBAL_STATS_UPDATED = "global_stats_updated"
    # Tracker events
    TRACKER_ANNOUNCE_STARTED = "tracker_announce_started"
    TRACKER_ANNOUNCE_SUCCESS = "tracker_announce_success"
    TRACKER_ANNOUNCE_ERROR = "tracker_announce_error"
    # Piece events (for real-time piece progress)
    PIECE_REQUESTED = "piece_requested"
    PIECE_DOWNLOADED = "piece_downloaded"
    PIECE_VERIFIED = "piece_verified"
    PIECE_COMPLETED = "piece_completed"
    # Progress events
    PROGRESS_UPDATED = "progress_updated"
    # Media streaming events
    MEDIA_STREAM_STARTED = "media_stream_started"
    MEDIA_STREAM_BUFFERING = "media_stream_buffering"
    MEDIA_STREAM_READY = "media_stream_ready"
    MEDIA_STREAM_STOPPED = "media_stream_stopped"
    MEDIA_STREAM_ERROR = "media_stream_error"
    # XET workspace events
    XET_FOLDER_ADDED = "xet_folder_added"
    XET_FOLDER_REMOVED = "xet_folder_removed"
    XET_FOLDER_CHANGED = "xet_folder_changed"
    XET_SYNC_PROGRESS = "xet_sync_progress"
    XET_SYNC_ERROR = "xet_sync_error"
    XET_METADATA_READY = "xet_metadata_ready"


class StatusResponse(BaseModel):
    """Daemon status response."""

    status: str = Field(..., description="Daemon status")
    pid: int = Field(..., description="Process ID")
    uptime: float = Field(..., description="Uptime in seconds")
    version: str = Field(..., description="Daemon version")
    num_torrents: int = Field(0, description="Number of active torrents")
    ipc_url: str = Field(..., description="IPC server URL")
    inbound_unknown_info_hash_metrics_top: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Top unknown inbound info-hash prefixes (16-char hex) by count across TCP listeners; "
            "empty when none. See GET /api/v1/status and network troubleshooting docs."
        ),
    )


class XetSyncModeRequest(BaseModel):
    """Request to update the live sync mode for an XET folder."""

    sync_mode: str = Field(..., description="Requested XET sync mode")
    source_peers: Optional[list[str]] = Field(
        default=None,
        description="Optional designated source peers for designated mode",
    )


class XetWorkspacePolicyRequest(BaseModel):
    """Request to update live XET workspace policy."""

    sync_mode: Optional[str] = Field(None, description="Requested sync mode override")
    source_peers: Optional[list[str]] = Field(
        default=None,
        description="Optional designated source peers for designated mode",
    )
    auth_scope: Optional[str] = Field(None, description="Workspace auth scope override")
    allowlist_path: Optional[str] = Field(
        None, description="Override path to workspace allowlist"
    )
    require_signed_metadata: Optional[bool] = Field(
        None, description="Require signed metadata for this workspace"
    )
    hash_algorithm: Optional[str] = Field(
        None,
        description="Override hash algorithm identity or name",
    )


class XetDiscoveryBackendStatus(BaseModel):
    """Status for a single XET discovery backend."""

    enabled: bool = Field(False, description="Whether backend is enabled")
    injected: bool = Field(False, description="Whether backend dependency is injected")
    health: bool = Field(False, description="Current backend health")
    last_success: Optional[float] = Field(
        None,
        description="Timestamp of last successful backend operation",
    )
    udp_tracker_client_ready: Optional[bool] = Field(
        None,
        description="UDP BEP-15 client running (tracker backend only)",
    )
    udp_tracker_client_init_failed: Optional[bool] = Field(
        None,
        description="UDP tracker client failed to start (tracker backend only)",
    )


class XetDiscoveryStatusResponse(BaseModel):
    """XET discovery backend status snapshot."""

    backends: dict[str, XetDiscoveryBackendStatus] = Field(
        default_factory=dict,
        description="Backend status map keyed by backend name",
    )


class XetFolderStatusResponse(BaseModel):
    """Typed XET folder status payload."""

    model_config = {"extra": "allow"}

    folder_key: Optional[str] = Field(None, description="Canonical folder key")
    workspace_id: Optional[str] = Field(None, description="Workspace identifier (hex)")
    sync_mode: Optional[str] = Field(None, description="Current sync mode")
    downgrade_reason: Optional[str] = Field(
        None,
        description="Reason the effective sync mode was downgraded",
    )
    status: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime status payload for folder sync",
    )
    backend_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Discovery backend status snapshot for this workspace",
    )


class XetWorkspacePolicyResponse(BaseModel):
    """Typed response for workspace policy updates."""

    workspace_id: str = Field(..., description="Workspace identifier (hex)")
    sync_mode: str = Field(..., description="Effective sync mode")
    downgrade_reason: Optional[str] = Field(
        None,
        description="Reason the effective sync mode was downgraded",
    )
    updated_folders: int = Field(0, description="Number of active runtimes updated")
    policy: dict[str, Any] = Field(
        default_factory=dict,
        description="Current transport policy snapshot after update",
    )


class TorrentAddRequest(BaseModel):
    """Request to add a torrent."""

    path_or_magnet: str = Field(..., description="Torrent file path or magnet URI")
    output_dir: Optional[str] = Field(None, description="Output directory override")
    resume: bool = Field(False, description="Resume from checkpoint if available")


class TorrentStatusResponse(BaseModel):
    """Torrent status response (external IPC API).

    External API uses num_peers/num_seeds. Internal canonical status uses
    connected_peers/active_peers; translation happens at executor/IPC boundary.
    """

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    name: str = Field(..., description="Torrent name")
    status: str = Field(..., description="Torrent status")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Download progress")
    download_rate: float = Field(0.0, description="Download rate in bytes/sec")
    upload_rate: float = Field(0.0, description="Upload rate in bytes/sec")
    num_peers: int = Field(0, description="Number of connected peers")
    num_seeds: int = Field(0, description="Number of connected seeds")
    total_size: int = Field(0, description="Total size in bytes")
    downloaded: int = Field(0, description="Downloaded bytes")
    uploaded: int = Field(0, description="Uploaded bytes")
    is_private: bool = Field(False, description="Whether torrent is private (BEP 27)")
    output_dir: Optional[str] = Field(
        None, description="Output directory where files are saved"
    )
    pieces_completed: int = Field(0, description="Number of completed pieces")
    pieces_total: int = Field(0, description="Total number of pieces")
    tracker_status: Optional[str] = Field(None, description="Tracker health state")
    last_tracker_error: Optional[str] = Field(
        None, description="Last tracker-specific error"
    )
    last_error: Optional[str] = Field(None, description="Last torrent/session error")
    productive_peers: int = Field(0, description="Peers currently making progress")
    requestable_peers: int = Field(
        0, description="Peers currently eligible for requests"
    )
    handshake_complete_peers: int = Field(
        0, description="Peers that completed the base BitTorrent handshake"
    )
    extension_capable_peers: int = Field(
        0, description="Peers that advertised BEP 10 extension support"
    )
    metadata_capable_peers: int = Field(
        0, description="Peers that advertised ut_metadata support"
    )
    hash_verification_failures: int = Field(
        0, description="Pieces rejected after hash verification"
    )


class TorrentListResponse(BaseModel):
    """List of torrents response."""

    torrents: list[TorrentStatusResponse] = Field(
        default_factory=list,
        description="List of torrent statuses",
    )


class PeerInfo(BaseModel):
    """Peer information."""

    ip: str = Field(..., description="Peer IP address")
    port: int = Field(..., description="Peer port")
    download_rate: float = Field(0.0, description="Download rate from peer (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate to peer (bytes/sec)")
    choked: bool = Field(False, description="Whether peer is choked")
    client: Optional[str] = Field(None, description="Peer client name")


class PeerListResponse(BaseModel):
    """Peer list response."""

    info_hash: str = Field(..., description="Torrent info hash")
    peers: list[PeerInfo] = Field(default_factory=list, description="List of peers")
    count: int = Field(0, description="Number of peers")


class GlobalPeerListResponse(BaseModel):
    """Global peer list response across all torrents."""

    total_peers: int = Field(0, description="Total number of unique peers")
    peers: list[dict[str, Any]] = Field(
        default_factory=list, description="List of peer metrics dictionaries"
    )
    count: int = Field(0, description="Number of peers in response")


class TrackerInfo(BaseModel):
    """Tracker information."""

    url: str = Field(..., description="Tracker URL")
    status: str = Field(..., description="Tracker status (working, error, updating)")
    seeds: int = Field(0, description="Number of seeds from last scrape")
    peers: int = Field(0, description="Number of peers from last scrape")
    downloaders: int = Field(0, description="Number of downloaders from last scrape")
    last_update: float = Field(0.0, description="Last update timestamp")
    error: Optional[str] = Field(None, description="Error message if any")


class TrackerListResponse(BaseModel):
    """Tracker list response."""

    info_hash: str = Field(..., description="Torrent info hash")
    trackers: list[TrackerInfo] = Field(
        default_factory=list, description="List of trackers"
    )
    count: int = Field(0, description="Number of trackers")


class TrackerAddRequest(BaseModel):
    """Request to add a tracker to a torrent."""

    url: str = Field(..., description="Tracker URL to add")


class TrackerRemoveRequest(BaseModel):
    """Request to remove a tracker from a torrent."""

    # No fields needed - tracker URL comes from path


class PieceAvailabilityResponse(BaseModel):
    """Piece availability response."""

    info_hash: str = Field(..., description="Torrent info hash")
    availability: list[int] = Field(
        default_factory=list,
        description="List of peer counts for each piece (index = piece index, value = peer count)",
    )
    num_pieces: int = Field(0, description="Total number of pieces")
    max_peers: int = Field(0, description="Maximum number of peers that have any piece")


class RateSample(BaseModel):
    """Single upload/download rate sample."""

    timestamp: float = Field(..., description="Sample timestamp (seconds since epoch)")
    download_rate: float = Field(
        0.0, description="Aggregated download rate (bytes/sec)"
    )
    upload_rate: float = Field(0.0, description="Aggregated upload rate (bytes/sec)")


class RateSamplesResponse(BaseModel):
    """Response containing historic rate samples."""

    resolution: float = Field(1.0, description="Sampling resolution in seconds")
    seconds: int = Field(120, description="Requested lookback window in seconds")
    sample_count: int = Field(0, description="Number of samples returned")
    samples: list[RateSample] = Field(
        default_factory=list,
        description="List of rate samples ordered by timestamp ascending",
    )


class DiskIOMetricsResponse(BaseModel):
    """Disk I/O metrics response."""

    read_throughput: float = Field(0.0, description="Read throughput in KiB/s")
    write_throughput: float = Field(0.0, description="Write throughput in KiB/s")
    cache_hit_rate: float = Field(
        0.0, description="Cache hit rate as percentage (0-100)"
    )
    timing_ms: float = Field(
        0.0, description="Average disk operation timing in milliseconds"
    )


class NetworkTimingMetricsResponse(BaseModel):
    """Network timing metrics response."""

    utp_delay_ms: float = Field(0.0, description="Average uTP delay in milliseconds")
    network_overhead_rate: float = Field(
        0.0, description="Network overhead rate in KiB/s"
    )


class RateLimitRequest(BaseModel):
    """Request to set rate limits."""

    download_kib: int = Field(..., ge=0, description="Download limit in KiB/s")
    upload_kib: int = Field(..., ge=0, description="Upload limit in KiB/s")


class GlobalRateLimitRequest(BaseModel):
    """Request to set global rate limits."""

    download_kib: int = Field(
        0, ge=0, description="Global download limit (KiB/s, 0 = unlimited)"
    )
    upload_kib: int = Field(
        0, ge=0, description="Global upload limit (KiB/s, 0 = unlimited)"
    )


class PerPeerRateLimitRequest(BaseModel):
    """Request to set per-peer upload rate limit."""

    peer_key: str = Field(..., description="Peer identifier (format: 'ip:port')")
    upload_limit_kib: int = Field(
        0, ge=0, description="Upload rate limit (KiB/s, 0 = unlimited)"
    )


class PerPeerRateLimitResponse(BaseModel):
    """Response for per-peer rate limit operations."""

    success: bool = Field(..., description="Whether operation succeeded")
    peer_key: str = Field(..., description="Peer identifier")
    upload_limit_kib: int = Field(..., description="Current upload rate limit (KiB/s)")


class AllPeersRateLimitRequest(BaseModel):
    """Request to set per-peer upload rate limit for all peers."""

    upload_limit_kib: int = Field(
        0, ge=0, description="Upload rate limit (KiB/s, 0 = unlimited)"
    )


class AllPeersRateLimitResponse(BaseModel):
    """Response for setting rate limits on all peers."""

    updated_count: int = Field(..., description="Number of peers updated")
    upload_limit_kib: int = Field(..., description="Upload rate limit applied (KiB/s)")


class ExportStateRequest(BaseModel):
    """Request to export session state."""

    path: Optional[str] = Field(
        None, description="Export path (optional, defaults to state dir)"
    )


class ImportStateRequest(BaseModel):
    """Request to import session state."""

    path: str = Field(..., description="Import path (required)")


class ResumeCheckpointRequest(BaseModel):
    """Request to resume from checkpoint."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    checkpoint: dict[str, Any] = Field(..., description="Checkpoint data")
    torrent_path: Optional[str] = Field(
        None, description="Optional explicit torrent file path"
    )


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class TorrentCancelRequest(BaseModel):
    """Request to cancel a torrent (pause but keep in session)."""

    # No fields needed - info_hash comes from path


class TorrentCancelResponse(BaseModel):
    """Response for cancel operation."""

    status: str = Field(..., description="Operation status")
    info_hash: str = Field(..., description="Torrent info hash")


class WebSocketSubscribeRequest(BaseModel):
    """WebSocket subscription request."""

    event_types: list[EventType] = Field(
        default_factory=list,
        description="Event types to subscribe to (empty = all events)",
    )
    info_hash: Optional[str] = Field(
        None,
        description="Filter events to specific torrent (optional)",
    )
    priority_filter: Optional[str] = Field(
        None,
        description="Filter by priority: 'critical', 'high', 'normal', 'low'",
    )
    rate_limit: Optional[float] = Field(
        None,
        description="Maximum events per second (throttling)",
    )


class WebSocketMessage(BaseModel):
    """WebSocket message."""

    action: str = Field(..., description="Message action")
    data: Optional[dict[str, Any]] = Field(None, description="Message data")


class WebSocketAuthMessage(BaseModel):
    """WebSocket authentication message."""

    api_key: str = Field(..., description="API key")


class WebSocketEvent(BaseModel):
    """WebSocket event.

    `type` remains the stable external event contract. `raw_type` preserves the
    original internal event name when the bridge has to collapse several
    internal events onto one external type.
    """

    type: EventType = Field(..., description="Event type")
    timestamp: float = Field(..., description="Event timestamp")
    raw_type: Optional[str] = Field(
        None,
        description="Original internal event type before IPC translation",
    )
    event_id: Optional[str] = Field(None, description="Unique event identifier")
    source: Optional[str] = Field(None, description="Source component")
    priority: Optional[str] = Field(None, description="Event priority")
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation identifier for related events",
    )
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")


# File Selection Models
class FileInfo(BaseModel):
    """File information."""

    index: int = Field(..., description="File index")
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    selected: bool = Field(..., description="Whether file is selected")
    priority: str = Field(..., description="File priority")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Download progress")
    attributes: Optional[str] = Field(None, description="File attributes")
    path: Optional[str] = Field(None, description="Resolved file path on disk")
    mime_type: Optional[str] = Field(None, description="Best-effort MIME type")
    is_media: bool = Field(False, description="Whether the file looks playable")


class FileListResponse(BaseModel):
    """File list response."""

    info_hash: str = Field(..., description="Torrent info hash")
    files: list[FileInfo] = Field(default_factory=list, description="List of files")


class MediaStreamStartRequest(BaseModel):
    """Request to start a media stream for a torrent file."""

    file_index: int = Field(..., ge=0, description="File index to stream")
    port: Optional[int] = Field(
        default=None,
        ge=0,
        le=65535,
        description="Optional preferred local port",
    )


class MediaStreamStopRequest(BaseModel):
    """Request to stop a media stream."""

    stream_id: str = Field(..., description="Media stream identifier")


class MediaStreamStartResponse(BaseModel):
    """Response returned after starting a media stream."""

    stream_id: str = Field(..., description="Media stream identifier")
    info_hash: str = Field(..., description="Torrent info hash")
    file_index: int = Field(..., ge=0, description="Selected file index")
    state: str = Field(..., description="Current media stream state")
    stream_url: str = Field(..., description="Tokenized localhost stream URL")
    launched_external: bool = Field(
        default=False,
        description="Whether an external player launch was requested",
    )


class MediaStreamStatusResponse(BaseModel):
    """Media stream status response."""

    stream_id: str = Field(..., description="Media stream identifier")
    info_hash: str = Field(..., description="Torrent info hash")
    file_index: int = Field(..., ge=0, description="Selected file index")
    file_name: str = Field(..., description="Selected file name")
    file_path: str = Field(..., description="Resolved file path")
    file_size: int = Field(..., ge=0, description="Selected file size in bytes")
    state: str = Field(..., description="Media stream state")
    stream_url: Optional[str] = Field(
        None, description="Tokenized localhost stream URL"
    )
    bind_host: str = Field(..., description="Bind host for the local HTTP server")
    bind_port: int = Field(..., ge=0, le=65535, description="Bound local HTTP port")
    token_expires_at: Optional[float] = Field(
        None,
        description="Epoch timestamp when the stream token expires",
    )
    bytes_served: int = Field(0, ge=0, description="Total bytes served")
    client_count: int = Field(0, ge=0, description="Number of active HTTP clients")
    current_range_start: Optional[int] = Field(
        None,
        ge=0,
        description="Start offset of the latest requested range",
    )
    current_range_end: Optional[int] = Field(
        None,
        ge=0,
        description="End offset of the latest requested range",
    )
    available_bytes: int = Field(
        0,
        ge=0,
        description="Best-effort locally readable bytes for the selected file",
    )
    buffer_progress: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Readiness estimate for startup buffering",
    )
    last_error: Optional[str] = Field(None, description="Latest stream error")


class FileSelectRequest(BaseModel):
    """Request to select/deselect files."""

    file_indices: list[int] = Field(..., description="File indices to select/deselect")


class FilePriorityRequest(BaseModel):
    """Request to set file priority."""

    file_index: int = Field(..., description="File index")
    priority: str = Field(..., description="Priority level")


# Queue Models
class QueueEntry(BaseModel):
    """Queue entry."""

    info_hash: str = Field(..., description="Torrent info hash")
    queue_position: int = Field(..., description="Position in queue")
    priority: str = Field(..., description="Priority level")
    status: str = Field(..., description="Status")
    allocated_down_kib: float = Field(
        0.0, description="Allocated download rate (KiB/s)"
    )
    allocated_up_kib: float = Field(0.0, description="Allocated upload rate (KiB/s)")


class QueueListResponse(BaseModel):
    """Queue list response."""

    entries: list[QueueEntry] = Field(default_factory=list, description="Queue entries")
    statistics: dict[str, Any] = Field(
        default_factory=dict, description="Queue statistics"
    )


class QueueAddRequest(BaseModel):
    """Request to add torrent to queue."""

    info_hash: str = Field(..., description="Torrent info hash")
    priority: str = Field(..., description="Priority level")


class QueueMoveRequest(BaseModel):
    """Request to move torrent in queue."""

    new_position: int = Field(..., description="New position in queue")


# NAT Models
class NATStatusResponse(BaseModel):
    """NAT status response."""

    enabled: bool = Field(..., description="Whether NAT traversal is enabled")
    method: Optional[str] = Field(None, description="NAT method (UPnP, NAT-PMP, etc.)")
    external_ip: Optional[str] = Field(None, description="External IP address")
    mapped_port: Optional[int] = Field(None, description="Mapped port")
    mappings: list[dict[str, Any]] = Field(
        default_factory=list, description="Active port mappings"
    )


class NATMapRequest(BaseModel):
    """Request to map a port."""

    internal_port: int = Field(..., description="Internal port")
    external_port: Optional[int] = Field(None, description="External port (optional)")
    protocol: str = Field("tcp", description="Protocol (tcp/udp)")


class ExternalIPResponse(BaseModel):
    """External IP address response."""

    external_ip: Optional[str] = Field(None, description="External IP address")
    method: Optional[str] = Field(
        None, description="Method used to obtain IP (UPnP, NAT-PMP, etc.)"
    )


class ExternalPortResponse(BaseModel):
    """External port mapping response."""

    internal_port: int = Field(..., description="Internal port")
    external_port: Optional[int] = Field(None, description="External port (if mapped)")
    protocol: str = Field("tcp", description="Protocol (tcp/udp)")


# Scrape Models
class ScrapeResult(BaseModel):
    """Scrape result."""

    info_hash: str = Field(..., description="Torrent info hash")
    seeders: int = Field(0, description="Number of seeders")
    leechers: int = Field(0, description="Number of leechers")
    completed: int = Field(0, description="Number of completed downloads")
    last_scrape_time: float = Field(..., description="Last scrape timestamp")
    scrape_count: int = Field(0, description="Number of scrapes")


class ScrapeRequest(BaseModel):
    """Request to scrape a torrent."""

    force: bool = Field(False, description="Force scrape even if recently scraped")


class ScrapeListResponse(BaseModel):
    """List of scrape results."""

    results: list[ScrapeResult] = Field(
        default_factory=list, description="Scrape results"
    )


# Security Models
class BlacklistResponse(BaseModel):
    """Blacklist response."""

    ips: list[str] = Field(
        default_factory=list, description="List of blacklisted IP addresses"
    )
    count: int = Field(0, description="Number of blacklisted IPs")


class WhitelistResponse(BaseModel):
    """Whitelist response."""

    ips: list[str] = Field(
        default_factory=list, description="List of whitelisted IP addresses"
    )
    count: int = Field(0, description="Number of whitelisted IPs")


class BlacklistAddRequest(BaseModel):
    """Request to add IP to blacklist."""

    ip: str = Field(..., description="IP address to blacklist")
    reason: Optional[str] = Field(None, description="Reason for blacklisting")


class WhitelistAddRequest(BaseModel):
    """Request to add IP to whitelist."""

    ip: str = Field(..., description="IP address to whitelist")
    reason: Optional[str] = Field(None, description="Reason for whitelisting")


class IPFilterStatsResponse(BaseModel):
    """IP filter statistics response."""

    enabled: bool = Field(..., description="Whether IP filter is enabled")
    total_rules: int = Field(0, description="Total number of filter rules")
    blocked_count: int = Field(0, description="Number of blocked connections")
    allowed_count: int = Field(0, description="Number of allowed connections")
    stats: dict[str, Any] = Field(
        default_factory=dict, description="Additional filter statistics"
    )


# Session Models
class GlobalStatsResponse(BaseModel):
    """Global statistics response."""

    num_torrents: int = Field(0, description="Total number of torrents")
    num_active: int = Field(0, description="Number of active torrents")
    num_paused: int = Field(0, description="Number of paused torrents")
    total_download_rate: float = Field(
        0.0, description="Total download rate (bytes/sec)"
    )
    total_upload_rate: float = Field(0.0, description="Total upload rate (bytes/sec)")
    total_downloaded: int = Field(0, description="Total downloaded bytes")
    total_uploaded: int = Field(0, description="Total uploaded bytes")
    stats: dict[str, Any] = Field(
        default_factory=dict, description="Additional statistics"
    )


# UI Snapshot (first-paint hydration)
class UISnapshotResponse(BaseModel):
    """Single response for dashboard first-paint: global stats, torrent list, services, and minimal rate history."""

    global_stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Global session statistics (same shape as session/stats)",
    )
    torrents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of torrent status dicts (same shape as GET /torrents)",
    )
    services_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Coarse status of dht, nat, tcp_server, peer_service, ipc_server",
    )
    rate_samples: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent rate samples for graph (timestamp, download_rate, upload_rate); may be truncated",
    )
    peers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Aggregated peer rows across torrents (capped) for first-paint peer panels; same shape as GET /torrents/{ih}/peers rows",
    )


# Protocol Models
class ProtocolInfo(BaseModel):
    """Protocol information."""

    enabled: bool = Field(..., description="Whether protocol is enabled")
    status: str = Field(..., description="Protocol status")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Protocol-specific details"
    )


# Per-Torrent Performance Models
class PeerPerformanceMetrics(BaseModel):
    """Performance metrics for a single peer."""

    peer_key: str = Field(..., description="Peer identifier (IP:port)")
    download_rate: float = Field(0.0, description="Download rate from peer (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate to peer (bytes/sec)")
    request_latency: float = Field(0.0, description="Average request latency (seconds)")
    pieces_served: int = Field(0, description="Number of pieces served to peer")
    pieces_received: int = Field(0, description="Number of pieces received from peer")
    connection_duration: float = Field(0.0, description="Connection duration (seconds)")
    consecutive_failures: int = Field(0, description="Consecutive request failures")
    bytes_downloaded: int = Field(0, description="Total bytes downloaded from peer")
    bytes_uploaded: int = Field(0, description="Total bytes uploaded to peer")


class PerTorrentPerformanceResponse(BaseModel):
    """Per-torrent performance metrics response."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    download_rate: float = Field(0.0, description="Download rate (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate (bytes/sec)")
    progress: float = Field(
        0.0, ge=0.0, le=1.0, description="Download progress (0.0-1.0)"
    )
    pieces_completed: int = Field(0, description="Number of completed pieces")
    pieces_total: int = Field(0, description="Total number of pieces")
    connected_peers: int = Field(0, description="Number of connected peers")
    active_peers: int = Field(0, description="Number of active peers")
    top_peers: list[PeerPerformanceMetrics] = Field(
        default_factory=list, description="Top performing peers"
    )
    bytes_downloaded: int = Field(0, description="Total bytes downloaded")
    bytes_uploaded: int = Field(0, description="Total bytes uploaded")
    piece_download_rate: float = Field(0.0, description="Pieces downloaded per second")
    swarm_availability: float = Field(0.0, description="Swarm availability (0.0-1.0)")


class SwarmHealthSample(BaseModel):
    """Single swarm health sample for a torrent."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    name: str = Field(..., description="Torrent name")
    timestamp: float = Field(..., description="Sample timestamp (seconds since epoch)")
    swarm_availability: float = Field(0.0, description="Swarm availability (0.0-1.0)")
    download_rate: float = Field(0.0, description="Download rate (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate (bytes/sec)")
    connected_peers: int = Field(0, description="Number of connected peers")
    active_peers: int = Field(0, description="Number of active peers")
    progress: float = Field(
        0.0, ge=0.0, le=1.0, description="Download progress (0.0-1.0)"
    )


class SwarmHealthMatrixResponse(BaseModel):
    """Response containing swarm health matrix with historical samples."""

    samples: list[SwarmHealthSample] = Field(
        default_factory=list,
        description="List of swarm health samples ordered by timestamp",
    )
    sample_count: int = Field(0, description="Number of samples returned")
    resolution: float = Field(2.5, description="Sampling resolution in seconds")
    rarity_percentiles: dict[str, float] = Field(
        default_factory=dict,
        description="Rarity percentiles (p25, p50, p75, p90) for swarm availability",
    )


class GlobalPeerMetrics(BaseModel):
    """Global peer metrics for a single peer across all torrents."""

    peer_key: str = Field(..., description="Peer identifier (IP:port)")
    ip: str = Field(..., description="Peer IP address")
    port: int = Field(..., description="Peer port")
    info_hashes: list[str] = Field(
        default_factory=list,
        description="Torrent info hashes this peer is connected to",
    )
    total_download_rate: float = Field(
        0.0, description="Total download rate from peer across all torrents (bytes/sec)"
    )
    total_upload_rate: float = Field(
        0.0, description="Total upload rate to peer across all torrents (bytes/sec)"
    )
    total_bytes_downloaded: int = Field(
        0, description="Total bytes downloaded from peer"
    )
    total_bytes_uploaded: int = Field(0, description="Total bytes uploaded to peer")
    client: Optional[str] = Field(None, description="Peer client name")
    choked: bool = Field(False, description="Whether peer is choked")
    connection_duration: float = Field(
        0.0, description="Connection duration in seconds"
    )
    pieces_received: int = Field(0, description="Total pieces received from peer")
    pieces_served: int = Field(0, description="Total pieces served to peer")
    request_latency: float = Field(0.0, description="Average request latency (seconds)")


class GlobalPeerMetricsResponse(BaseModel):
    """Response containing global peer metrics across all torrents."""

    total_peers: int = Field(0, description="Total number of unique peers")
    active_peers: int = Field(0, description="Number of active peers")
    peers: list[GlobalPeerMetrics] = Field(
        default_factory=list, description="List of global peer metrics"
    )


class DetailedPeerMetricsResponse(BaseModel):
    """Detailed metrics for a specific peer."""

    peer_key: str = Field(..., description="Peer identifier (IP:port)")
    bytes_downloaded: int = Field(0, description="Total bytes downloaded")
    bytes_uploaded: int = Field(0, description="Total bytes uploaded")
    download_rate: float = Field(0.0, description="Download rate (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate (bytes/sec)")
    request_latency: float = Field(0.0, description="Average request latency (seconds)")
    consecutive_failures: int = Field(0, description="Consecutive failures")
    connection_duration: float = Field(0.0, description="Connection duration (seconds)")
    pieces_served: int = Field(0, description="Pieces served to peer")
    pieces_received: int = Field(0, description="Pieces received from peer")
    pieces_per_second: float = Field(0.0, description="Average pieces per second")
    bytes_per_connection: float = Field(0.0, description="Bytes per connection")
    efficiency_score: float = Field(0.0, description="Efficiency score (0.0-1.0)")
    bandwidth_utilization: float = Field(
        0.0, description="Bandwidth utilization (0.0-1.0)"
    )
    connection_quality_score: float = Field(
        0.0, description="Connection quality score (0.0-1.0)"
    )
    error_rate: float = Field(0.0, description="Error rate (0.0-1.0)")
    success_rate: float = Field(1.0, description="Success rate (0.0-1.0)")
    average_block_latency: float = Field(
        0.0, description="Average block latency (seconds)"
    )
    peak_download_rate: float = Field(0.0, description="Peak download rate achieved")
    peak_upload_rate: float = Field(0.0, description="Peak upload rate achieved")
    performance_trend: str = Field(
        "stable", description="Performance trend: improving/stable/degrading"
    )
    piece_download_speeds: dict[int, float] = Field(
        default_factory=dict,
        description="Download speed per piece (piece_index -> bytes/sec)",
    )


class DetailedTorrentMetricsResponse(BaseModel):
    """Detailed metrics for a specific torrent."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    bytes_downloaded: int = Field(0, description="Total bytes downloaded")
    bytes_uploaded: int = Field(0, description="Total bytes uploaded")
    download_rate: float = Field(0.0, description="Download rate (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate (bytes/sec)")
    pieces_completed: int = Field(0, description="Number of completed pieces")
    pieces_total: int = Field(0, description="Total number of pieces")
    progress: float = Field(0.0, description="Download progress (0.0-1.0)")
    connected_peers: int = Field(0, description="Number of connected peers")
    active_peers: int = Field(0, description="Number of active peers")
    # Swarm health metrics
    piece_availability_distribution: dict[int, int] = Field(
        default_factory=dict,
        description="Distribution of piece availability (availability_count -> number_of_pieces)",
    )
    average_piece_availability: float = Field(
        0.0, description="Average number of peers per piece"
    )
    rarest_piece_availability: int = Field(
        0, description="Minimum availability across all pieces"
    )
    swarm_health_score: float = Field(0.0, description="Swarm health score (0.0-1.0)")
    # Peer performance distribution
    peer_performance_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Peer performance distribution (tier -> count)",
    )
    average_peer_download_speed: float = Field(
        0.0, description="Average peer download speed (bytes/sec)"
    )
    median_peer_download_speed: float = Field(
        0.0, description="Median peer download speed (bytes/sec)"
    )
    fastest_peer_speed: float = Field(0.0, description="Fastest peer speed (bytes/sec)")
    slowest_peer_speed: float = Field(0.0, description="Slowest peer speed (bytes/sec)")
    # Piece completion metrics
    piece_completion_rate: float = Field(0.0, description="Pieces per second")
    estimated_time_remaining: float = Field(
        0.0, description="Estimated time remaining (seconds)"
    )
    # Swarm efficiency
    swarm_efficiency: float = Field(0.0, description="Swarm efficiency (0.0-1.0)")
    peer_contribution_balance: float = Field(
        0.0, description="Peer contribution balance (0.0-1.0)"
    )


class DetailedGlobalMetricsResponse(BaseModel):
    """Detailed global metrics across all torrents."""

    # Global peer metrics
    total_peers: int = Field(0, description="Total number of unique peers")
    average_download_rate: float = Field(
        0.0, description="Average download rate across all peers"
    )
    average_upload_rate: float = Field(
        0.0, description="Average upload rate across all peers"
    )
    total_bytes_downloaded: int = Field(
        0, description="Total bytes downloaded from all peers"
    )
    total_bytes_uploaded: int = Field(
        0, description="Total bytes uploaded to all peers"
    )
    swarm_auth_gate_total: int = Field(
        0, description="Total swarm-auth gate evaluations"
    )
    swarm_auth_gate_by_mode_strict_total: int = Field(
        0, description="Swarm-auth gate decisions in strict mode"
    )
    swarm_auth_gate_by_mode_opportunistic_total: int = Field(
        0, description="Swarm-auth gate decisions in opportunistic mode"
    )
    swarm_auth_gate_by_mode_off_total: int = Field(
        0, description="Swarm-auth gate decisions when mode is off"
    )
    swarm_auth_gate_allow_total: int = Field(0, description="Swarm-auth allows")
    swarm_auth_gate_deny_total: int = Field(0, description="Swarm-auth denies")
    swarm_auth_gate_reason_invalid_signature_total: int = Field(
        0, description="Swarm-auth invalid signature denies"
    )
    swarm_auth_opportunistic_verify_failed_total: int = Field(
        0,
        description="Swarm-auth opportunistic verification failures in non-blocking mode",
    )
    swarm_auth_strict_ltep_timeout_total: int = Field(
        0, description="Swarm-auth strict LTEP timeout rejections"
    )
    swarm_auth_truststore_reload_total: int = Field(
        0, description="Swarm-auth truststore reload events"
    )
    swarm_auth_revocation_hits_total: int = Field(
        0, description="Swarm-auth revocation hits"
    )
    swarm_auth_discovery_suppressed_total: int = Field(
        0, description="Swarm-auth discovery suppression events"
    )
    peer_efficiency_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of peer efficiency (tier -> count)",
    )
    top_performers: list[str] = Field(
        default_factory=list, description="List of top performing peer keys"
    )
    cross_torrent_sharing: float = Field(
        0.0, description="Cross-torrent sharing efficiency (0.0-1.0)"
    )
    shared_peers_count: int = Field(
        0, description="Number of peers shared across multiple torrents"
    )
    # System-wide efficiency
    overall_efficiency: float = Field(
        0.0, description="Overall system efficiency (0.0-1.0)"
    )
    bandwidth_utilization: float = Field(
        0.0, description="Bandwidth utilization (0.0-1.0)"
    )
    connection_efficiency: float = Field(
        0.0, description="Connection efficiency (0.0-1.0)"
    )
    resource_utilization: float = Field(
        0.0, description="Resource utilization (0.0-1.0)"
    )
    peer_efficiency: float = Field(0.0, description="Peer efficiency (0.0-1.0)")
    cpu_usage: float = Field(0.0, description="CPU usage (0.0-1.0)")
    memory_usage: float = Field(0.0, description="Memory usage (0.0-1.0)")
    disk_usage: float = Field(0.0, description="Disk usage (0.0-1.0)")


# IMPROVEMENT: New metrics models for trickle improvements
class DHTQueryMetricsResponse(BaseModel):
    """DHT query effectiveness metrics for a torrent."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    peers_found_per_query: float = Field(
        0.0, description="Average peers found per DHT query"
    )
    query_depth_achieved: float = Field(0.0, description="Average query depth achieved")
    nodes_queried_per_query: float = Field(
        0.0, description="Average nodes queried per query"
    )
    total_queries: int = Field(0, description="Total DHT queries performed")
    total_peers_found: int = Field(0, description="Total peers discovered via DHT")
    aggressive_mode_enabled: bool = Field(
        False, description="Whether aggressive discovery mode is enabled"
    )
    last_query_duration: float = Field(
        0.0, description="Duration of last query in seconds"
    )
    last_query_peers_found: int = Field(0, description="Peers found in last query")
    last_query_depth: int = Field(0, description="Query depth of last query")
    last_query_nodes_queried: int = Field(0, description="Nodes queried in last query")
    routing_table_size: int = Field(0, description="Current DHT routing table size")
    bootstrap_success_count: int = Field(
        0, description="Number of successful bootstrap or rebootstrap attempts"
    )
    bootstrap_failure_count: int = Field(
        0, description="Number of failed bootstrap or rebootstrap attempts"
    )
    bootstrap_recovery_attempts: int = Field(
        0,
        description="Number of bootstrap recovery attempts (including rebootstrap and fallback)",
    )
    bootstrap_health_state: str = Field(
        "unknown", description="Current bootstrap health state"
    )
    bootstrap_zero_state_count: int = Field(
        0,
        description="Count of times bootstrap completed with zero routing-table nodes",
    )
    bootstrap_zero_nodes_last_reason: str = Field(
        "", description="Reason from the last zero-node bootstrap outcome"
    )
    rebootstrap_attempt_count: int = Field(
        0, description="Number of rebootstrap attempts"
    )
    rebootstrap_success_count: int = Field(
        0, description="Number of successful rebootstrap attempts"
    )
    rebootstrap_failure_count: int = Field(
        0, description="Number of failed rebootstrap attempts"
    )
    rebootstrap_last_outcome: str = Field(
        "not_attempted", description="Last rebootstrap attempt outcome"
    )
    rebootstrap_last_reason: str = Field(
        "", description="Reason label for last rebootstrap attempt"
    )
    rebootstrap_last_source: str = Field("", description="Source of last rebootstrap")
    rebootstrap_health_state: str = Field(
        "unknown", description="Current rebootstrap health state"
    )
    rebootstrap_consecutive_failures: int = Field(
        0, description="Consecutive rebootstrap failures"
    )
    last_bootstrap_reason: str = Field(
        "", description="Reason label for the last bootstrap attempt"
    )
    last_bootstrap_failure_reason: str = Field(
        "", description="Last recorded bootstrap failure reason"
    )
    last_zero_node_lookup_at: float = Field(
        0.0,
        description="Timestamp of the last lookup that queried zero nodes",
    )


class PeerQualityMetricsResponse(BaseModel):
    """Peer quality metrics for a torrent."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    total_peers_ranked: int = Field(0, description="Total peers ranked by quality")
    average_quality_score: float = Field(
        0.0, description="Average peer quality score (0.0-1.0)"
    )
    high_quality_peers: int = Field(
        0, description="Number of high-quality peers (score > 0.7)"
    )
    medium_quality_peers: int = Field(
        0, description="Number of medium-quality peers (0.3 < score <= 0.7)"
    )
    low_quality_peers: int = Field(
        0, description="Number of low-quality peers (score <= 0.3)"
    )
    top_quality_peers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top 10 highest quality peers with scores and details",
    )
    quality_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of peer quality scores (tier -> count)",
    )


class AggressiveDiscoveryStatusResponse(BaseModel):
    """Aggressive discovery mode status for a torrent."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    enabled: bool = Field(False, description="Whether aggressive discovery is enabled")
    reason: str = Field(
        "", description="Reason for enabling/disabling (popular/active/normal)"
    )
    current_peer_count: int = Field(0, description="Current connected peer count")
    current_download_rate_kib: float = Field(
        0.0, description="Current download rate in KB/s"
    )
    popular_threshold: int = Field(
        20, description="Peer count threshold for popular torrents"
    )
    active_threshold_kib: float = Field(
        1.0, description="Download rate threshold in KB/s for active torrents"
    )
    query_interval: float = Field(
        0.0, description="Current DHT query interval in seconds"
    )
    max_peers_per_query: int = Field(
        50, description="Maximum peers queried per DHT query"
    )


# Event Data Models
class MetadataReadyEventData(BaseModel):
    """Data for METADATA_READY event."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    name: str = Field(..., description="Torrent name")
    file_count: int = Field(..., description="Number of files")
    total_size: int = Field(..., description="Total size in bytes")
    files: list[FileInfo] = Field(
        default_factory=list, description="List of file information"
    )


class PeerEventData(BaseModel):
    """Data for peer events."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    peer_ip: str = Field(..., description="Peer IP address")
    peer_port: int = Field(..., description="Peer port")
    peer_id: Optional[str] = Field(None, description="Peer ID (hex)")
    client: Optional[str] = Field(None, description="Peer client name")
    download_rate: float = Field(0.0, description="Download rate from peer (bytes/sec)")
    upload_rate: float = Field(0.0, description="Upload rate to peer (bytes/sec)")
    pieces_available: int = Field(0, description="Number of pieces available from peer")


class FileSelectionEventData(BaseModel):
    """Data for file selection events."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    file_index: int = Field(..., description="File index")
    selected: bool = Field(..., description="Whether file is selected")
    priority: Optional[str] = Field(None, description="File priority")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="File download progress")


class SeedingEventData(BaseModel):
    """Data for seeding events."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    upload_rate: float = Field(0.0, description="Upload rate (bytes/sec)")
    connected_leechers: int = Field(0, description="Number of connected leechers")
    total_uploaded: int = Field(0, description="Total bytes uploaded")
    ratio: float = Field(0.0, description="Upload/download ratio")


class ServiceEventData(BaseModel):
    """Data for service/component events."""

    service_name: str = Field(..., description="Service name")
    component_name: Optional[str] = Field(None, description="Component name (optional)")
    status: str = Field(..., description="Service/component status")
    error: Optional[str] = Field(None, description="Error message if any")


class XetFolderEventData(BaseModel):
    """Data for XET folder and sync events."""

    model_config = {"extra": "allow"}

    folder_key: Optional[str] = Field(None, description="Canonical folder key")
    folder_path: Optional[str] = Field(None, description="Folder path")
    workspace_id: Optional[str] = Field(None, description="Workspace identifier (hex)")
    sync_mode: Optional[str] = Field(None, description="Effective sync mode")
    downgrade_reason: Optional[str] = Field(
        None,
        description="Reason sync mode was downgraded",
    )
    status: Optional[str] = Field(None, description="Human-readable status")
    error: Optional[str] = Field(None, description="Error message for failed sync")
