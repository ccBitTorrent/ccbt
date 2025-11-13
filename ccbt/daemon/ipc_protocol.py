"""IPC protocol definitions for daemon communication.

from __future__ import annotations

Defines constants, models, and types for HTTP REST and WebSocket IPC communication.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

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


class StatusResponse(BaseModel):
    """Daemon status response."""

    status: str = Field(..., description="Daemon status")
    pid: int = Field(..., description="Process ID")
    uptime: float = Field(..., description="Uptime in seconds")
    version: str = Field(..., description="Daemon version")
    num_torrents: int = Field(0, description="Number of active torrents")
    ipc_url: str = Field(..., description="IPC server URL")


class TorrentAddRequest(BaseModel):
    """Request to add a torrent."""

    path_or_magnet: str = Field(..., description="Torrent file path or magnet URI")
    output_dir: str | None = Field(None, description="Output directory override")
    resume: bool = Field(False, description="Resume from checkpoint if available")


class TorrentStatusResponse(BaseModel):
    """Torrent status response."""

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
    client: str | None = Field(None, description="Peer client name")


class PeerListResponse(BaseModel):
    """Peer list response."""

    info_hash: str = Field(..., description="Torrent info hash")
    peers: list[PeerInfo] = Field(default_factory=list, description="List of peers")
    count: int = Field(0, description="Number of peers")


class RateLimitRequest(BaseModel):
    """Request to set rate limits."""

    download_kib: int = Field(..., ge=0, description="Download limit in KiB/s")
    upload_kib: int = Field(..., ge=0, description="Upload limit in KiB/s")


class ExportStateRequest(BaseModel):
    """Request to export session state."""

    path: str | None = Field(
        None, description="Export path (optional, defaults to state dir)"
    )


class ImportStateRequest(BaseModel):
    """Request to import session state."""

    path: str = Field(..., description="Import path (required)")


class ResumeCheckpointRequest(BaseModel):
    """Request to resume from checkpoint."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    checkpoint: dict[str, Any] = Field(..., description="Checkpoint data")
    torrent_path: str | None = Field(
        None, description="Optional explicit torrent file path"
    )


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class WebSocketSubscribeRequest(BaseModel):
    """WebSocket subscription request."""

    event_types: list[EventType] = Field(
        default_factory=list,
        description="Event types to subscribe to",
    )


class WebSocketMessage(BaseModel):
    """WebSocket message."""

    action: str = Field(..., description="Message action")
    data: dict[str, Any] | None = Field(None, description="Message data")


class WebSocketAuthMessage(BaseModel):
    """WebSocket authentication message."""

    api_key: str = Field(..., description="API key")


class WebSocketEvent(BaseModel):
    """WebSocket event."""

    type: EventType = Field(..., description="Event type")
    timestamp: float = Field(..., description="Event timestamp")
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
    attributes: str | None = Field(None, description="File attributes")


class FileListResponse(BaseModel):
    """File list response."""

    info_hash: str = Field(..., description="Torrent info hash")
    files: list[FileInfo] = Field(default_factory=list, description="List of files")


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
    method: str | None = Field(None, description="NAT method (UPnP, NAT-PMP, etc.)")
    external_ip: str | None = Field(None, description="External IP address")
    mapped_port: int | None = Field(None, description="Mapped port")
    mappings: list[dict[str, Any]] = Field(
        default_factory=list, description="Active port mappings"
    )


class NATMapRequest(BaseModel):
    """Request to map a port."""

    internal_port: int = Field(..., description="Internal port")
    external_port: int | None = Field(None, description="External port (optional)")
    protocol: str = Field("tcp", description="Protocol (tcp/udp)")


class ExternalIPResponse(BaseModel):
    """External IP address response."""

    external_ip: str | None = Field(None, description="External IP address")
    method: str | None = Field(
        None, description="Method used to obtain IP (UPnP, NAT-PMP, etc.)"
    )


class ExternalPortResponse(BaseModel):
    """External port mapping response."""

    internal_port: int = Field(..., description="Internal port")
    external_port: int | None = Field(None, description="External port (if mapped)")
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
    reason: str | None = Field(None, description="Reason for blacklisting")


class WhitelistAddRequest(BaseModel):
    """Request to add IP to whitelist."""

    ip: str = Field(..., description="IP address to whitelist")
    reason: str | None = Field(None, description="Reason for whitelisting")


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


# Protocol Models
class ProtocolInfo(BaseModel):
    """Protocol information."""

    enabled: bool = Field(..., description="Whether protocol is enabled")
    status: str = Field(..., description="Protocol status")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Protocol-specific details"
    )
