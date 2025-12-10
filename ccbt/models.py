"""Pydantic models for ccBitTorrent.

from __future__ import annotations

Provides validated data models for type safety and runtime validation.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PieceSelectionStrategy(str, Enum):
    """Piece selection strategies."""

    ROUND_ROBIN = "round_robin"
    RAREST_FIRST = "rarest_first"
    SEQUENTIAL = "sequential"
    BANDWIDTH_WEIGHTED_RAREST = "bandwidth_weighted_rarest"
    PROGRESSIVE_RAREST = "progressive_rarest"
    ADAPTIVE_HYBRID = "adaptive_hybrid"


class PreallocationStrategy(str, Enum):
    """File preallocation strategies."""

    NONE = "none"
    SPARSE = "sparse"
    FULL = "full"
    FALLOCATE = "fallocate"


class PieceState(str, Enum):
    """Piece download states."""

    MISSING = "missing"
    REQUESTED = "requested"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    VERIFIED = "verified"


class ConnectionState(str, Enum):
    """Peer connection states."""

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


class CheckpointFormat(str, Enum):
    """Checkpoint file format options."""

    JSON = "json"
    BINARY = "binary"
    BOTH = "both"


class TorrentPriority(str, Enum):
    """Torrent priority levels for queue management."""

    PAUSED = "paused"  # Do not download
    LOW = "low"  # Lowest priority
    NORMAL = "normal"  # Default priority
    HIGH = "high"  # High priority
    MAXIMUM = "maximum"  # Highest priority


class BandwidthAllocationMode(str, Enum):
    """Bandwidth allocation strategies."""

    PROPORTIONAL = "proportional"  # Allocate by priority weight ratio
    EQUAL = "equal"  # Equal share to all active torrents
    FIXED = "fixed"  # Fixed KiB/s per priority level
    MANUAL = "manual"  # User-specified per torrent


class OptimizationProfile(str, Enum):
    """Optimization profiles for download performance."""

    BALANCED = "balanced"  # Balanced performance and resource usage
    SPEED = "speed"  # Maximum download speed
    EFFICIENCY = "efficiency"  # Maximum bandwidth efficiency
    LOW_RESOURCE = "low_resource"  # Minimal resource usage
    CUSTOM = "custom"  # Custom configuration


class MessageType(int, Enum):
    """BitTorrent message types."""

    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7
    CANCEL = 8


class PeerInfo(BaseModel):
    """Peer information."""

    ip: str = Field(..., description="Peer IP address")
    port: int = Field(..., ge=1, le=65535, description="Peer port number")
    peer_id: bytes | None = Field(None, description="Peer ID")
    peer_source: str | None = Field(
        default="tracker",
        description="Source of peer discovery (tracker/dht/pex/lsd/manual)",
    )
    ssl_capable: bool | None = Field(
        None,
        description="Whether peer supports SSL/TLS (None = unknown, discovered during extension handshake)",
    )
    ssl_enabled: bool = Field(
        False,
        description="Whether connection to this peer is using SSL/TLS encryption",
    )

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v):
        """Validate IP address format."""
        # Basic IP validation - could be enhanced with proper IP address validation
        if not v or len(v) == 0:
            msg = "IP address cannot be empty"
            raise ValueError(msg)
        return v

    def __str__(self) -> str:
        """String representation of peer info."""
        return f"{self.ip}:{self.port}"

    def __hash__(self) -> int:
        """Hash peer info for use as dictionary key."""
        return hash((self.ip, self.port))

    def __eq__(self, other) -> bool:
        """Equality comparison for peer info."""
        if not isinstance(other, PeerInfo):
            return False
        return self.ip == other.ip and self.port == other.port

    model_config = {"arbitrary_types_allowed": True}


class TrackerResponse(BaseModel):
    """Tracker response data."""

    interval: int = Field(..., ge=0, description="Announce interval in seconds")
    peers: list[PeerInfo] = Field(default_factory=list, description="List of peers")
    complete: int | None = Field(None, ge=0, description="Number of seeders")
    incomplete: int | None = Field(None, ge=0, description="Number of leechers")
    download_url: str | None = Field(None, description="Download URL")
    tracker_id: str | None = Field(None, description="Tracker ID")
    warning_message: str | None = Field(None, description="Warning message")


class PieceInfo(BaseModel):
    """Piece information."""

    index: int = Field(..., ge=0, description="Piece index")
    length: int = Field(..., gt=0, description="Piece length in bytes")
    hash: bytes = Field(
        ...,
        min_length=20,
        max_length=20,
        description="Piece SHA-1 hash",
    )
    state: PieceState = Field(default=PieceState.MISSING, description="Piece state")

    model_config = {"arbitrary_types_allowed": True}


class FileInfo(BaseModel):
    """File information for torrents.

    Supports BEP 47 padding files and extended file attributes:
    - Padding files (attr='p'): Used for piece alignment, skipped during download
    - Symlinks (attr='l'): Symbolic links with target path
    - Executable (attr='x'): Files with executable permission
    - Hidden (attr='h'): Hidden files (Windows)
    """

    name: str = Field(..., description="File name")
    length: int = Field(..., ge=0, description="File length in bytes")
    path: list[str] | None = Field(None, description="File path components")
    full_path: str | None = Field(None, description="Full file path")

    # BEP 47: Padding Files and Attributes
    attributes: str | None = Field(
        None,
        description="File attributes string from BEP 47 (e.g., 'p', 'x', 'h', 'l')",
    )
    symlink_path: str | None = Field(
        None,
        description="Symlink target path (required when attr='l')",
    )
    file_sha1: bytes | None = Field(
        None,
        description="SHA-1 hash of file contents (optional BEP 47 sha1 field, 20 bytes)",
    )

    @property
    def is_padding(self) -> bool:
        """Check if file is a padding file (BEP 47 attr='p')."""
        return self.attributes is not None and "p" in self.attributes

    @property
    def is_symlink(self) -> bool:
        """Check if file is a symlink (BEP 47 attr='l')."""
        return self.attributes is not None and "l" in self.attributes

    @property
    def is_executable(self) -> bool:
        """Check if file is executable (BEP 47 attr='x')."""
        return self.attributes is not None and "x" in self.attributes

    @property
    def is_hidden(self) -> bool:
        """Check if file is hidden (BEP 47 attr='h')."""
        return self.attributes is not None and "h" in self.attributes

    @field_validator("symlink_path")
    @classmethod
    def validate_symlink_path(cls, v: str | None, _info: Any) -> str | None:
        """Validate symlink_path is provided when attr='l'."""
        # Note: This validator runs before model_validator, so we can't check attributes here
        # The model_validator below handles the cross-field validation
        return v

    @field_validator("file_sha1")
    @classmethod
    def validate_file_sha1(cls, v: bytes | None, _info: Any) -> bytes | None:
        """Validate file_sha1 is 20 bytes (SHA-1 length) if provided."""
        if v is not None and len(v) != 20:
            msg = f"file_sha1 must be 20 bytes (SHA-1), got {len(v)} bytes"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_symlink_requirements(self) -> FileInfo:
        """Validate symlink_path is provided when attr='l'."""
        if self.attributes and "l" in self.attributes and not self.symlink_path:
            msg = "symlink_path is required when attributes contains 'l' (symlink)"
            raise ValueError(msg)
        return self


class XetChunkInfo(BaseModel):
    """Xet chunk information."""

    hash: bytes = Field(
        ..., min_length=32, max_length=32, description="BLAKE3-256 hash of chunk"
    )
    size: int = Field(..., ge=8192, le=131072, description="Chunk size in bytes")
    storage_path: str | None = Field(None, description="Local storage path")
    ref_count: int = Field(default=1, ge=1, description="Reference count")
    created_at: float = Field(
        default_factory=time.time, description="Creation timestamp"
    )
    last_accessed: float = Field(
        default_factory=time.time, description="Last access timestamp"
    )


class XetFileMetadata(BaseModel):
    """Xet file reconstruction metadata."""

    file_path: str = Field(..., description="File path")
    file_hash: bytes = Field(
        ..., min_length=32, max_length=32, description="Merkle root hash"
    )
    chunk_hashes: list[bytes] = Field(..., description="Ordered chunk hashes")
    xorb_refs: list[bytes] = Field(default_factory=list, description="Xorb hashes")
    total_size: int = Field(..., ge=0, description="Total file size in bytes")


class XetPieceMetadata(BaseModel):
    """Xet metadata for a BitTorrent piece."""

    piece_index: int = Field(..., ge=0, description="Piece index")
    chunk_hashes: list[bytes] = Field(..., description="Xet chunks in this piece")
    merkle_hash: bytes = Field(
        ..., min_length=32, max_length=32, description="Merkle tree root for piece"
    )


class XetTorrentMetadata(BaseModel):
    """Xet protocol metadata for a torrent."""

    chunk_hashes: list[bytes] = Field(
        default_factory=list,
        description="All chunk hashes in the torrent (deduplicated)",
    )
    file_metadata: list[XetFileMetadata] = Field(
        default_factory=list,
        description="Xet metadata for each file",
    )
    piece_metadata: list[XetPieceMetadata] = Field(
        default_factory=list,
        description="Xet metadata for each piece",
    )
    xorb_hashes: list[bytes] = Field(
        default_factory=list,
        description="All xorb hashes used in the torrent",
    )


class TonicFileInfo(BaseModel):
    """Information about a .tonic file."""

    folder_name: str = Field(..., description="Name of the folder")
    info_hash: bytes = Field(
        ..., min_length=32, max_length=32, description="32-byte SHA-256 info hash"
    )
    total_length: int = Field(..., ge=0, description="Total folder size in bytes")
    sync_mode: str = Field(
        default="best_effort",
        description="Synchronization mode (designated/best_effort/broadcast/consensus)",
    )
    git_refs: list[str] = Field(
        default_factory=list, description="Git commit hashes for version tracking"
    )
    source_peers: list[str] | None = Field(
        None, description="Designated source peer IDs (for designated mode)"
    )
    allowlist_hash: bytes | None = Field(
        None,
        min_length=32,
        max_length=32,
        description="32-byte hash of encrypted allowlist",
    )
    created_at: float = Field(
        default_factory=time.time, description="Creation timestamp"
    )
    version: int = Field(default=1, description="Tonic file format version")
    announce: str | None = Field(None, description="Primary tracker announce URL")
    announce_list: list[list[str]] | None = Field(
        None, description="List of tracker tiers"
    )
    comment: str | None = Field(None, description="Optional comment")
    xet_metadata: XetTorrentMetadata = Field(
        ..., description="XET metadata with chunk hashes and file info"
    )


class TonicLinkInfo(BaseModel):
    """Information extracted from a tonic?: link."""

    info_hash: bytes = Field(
        ..., min_length=32, max_length=32, description="32-byte SHA-256 info hash"
    )
    display_name: str | None = Field(None, description="Display name")
    trackers: list[str] | None = Field(None, description="List of tracker URLs")
    git_refs: list[str] | None = Field(
        None, description="List of git commit hashes/refs"
    )
    sync_mode: str | None = Field(
        None,
        description="Synchronization mode (designated/best_effort/broadcast/consensus)",
    )
    source_peers: list[str] | None = Field(
        None, description="List of source peer IDs"
    )
    allowlist_hash: bytes | None = Field(
        None,
        min_length=32,
        max_length=32,
        description="32-byte allowlist hash",
    )


class XetSyncStatus(BaseModel):
    """Status of XET folder synchronization."""

    folder_path: str = Field(..., description="Path to synced folder")
    sync_mode: str = Field(..., description="Current synchronization mode")
    is_syncing: bool = Field(default=False, description="Whether sync is in progress")
    last_sync_time: float | None = Field(
        None, description="Timestamp of last successful sync"
    )
    current_git_ref: str | None = Field(
        None, description="Current git commit hash"
    )
    pending_changes: int = Field(
        default=0, description="Number of pending file changes"
    )
    connected_peers: int = Field(
        default=0, description="Number of connected peers"
    )
    synced_peers: int = Field(
        default=0, description="Number of peers with latest version"
    )
    sync_progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Sync progress (0.0 to 1.0)"
    )
    error: str | None = Field(None, description="Error message if sync failed")
    last_check_time: float | None = Field(
        None, description="Timestamp of last folder check"
    )


class TorrentInfo(BaseModel):
    """Torrent information."""

    name: str = Field(..., description="Torrent name")
    info_hash: bytes = Field(..., min_length=20, max_length=20, description="Info hash")
    announce: str = Field(..., description="Announce URL")
    announce_list: list[list[str]] | None = Field(None, description="Announce list")
    comment: str | None = Field(None, description="Torrent comment")
    created_by: str | None = Field(None, description="Created by")
    creation_date: int | None = Field(None, description="Creation date")
    encoding: str | None = Field(None, description="String encoding")
    is_private: bool = Field(
        default=False,
        description="Whether torrent is marked as private (BEP 27)",
    )

    # File information
    files: list[FileInfo] = Field(default_factory=list, description="File list")
    total_length: int = Field(..., ge=0, description="Total length in bytes")

    # Piece information
    piece_length: int = Field(..., gt=0, description="Piece length in bytes")
    pieces: list[bytes] = Field(default_factory=list, description="Piece hashes")
    num_pieces: int = Field(..., ge=0, description="Number of pieces")

    # Protocol v2 fields (BEP 52)
    meta_version: int = Field(
        default=1, description="Protocol version (1=v1, 2=v2, 3=hybrid)"
    )
    info_hash_v2: bytes | None = Field(
        None,
        min_length=32,
        max_length=32,
        description="v2 info hash (SHA-256, 32 bytes)",
    )
    info_hash_v1: bytes | None = Field(
        None,
        min_length=20,
        max_length=20,
        description="v1 info hash (SHA-1, 20 bytes) for hybrid torrents",
    )
    file_tree: dict[str, Any] | None = Field(
        None,
        description="v2 file tree structure (hierarchical)",
    )
    piece_layers: dict[bytes, list[bytes]] | None = Field(
        None,
        description="v2 piece layers (pieces_root -> list of piece hashes)",
    )

    # Xet protocol metadata
    xet_metadata: XetTorrentMetadata | None = Field(
        None,
        description="Xet protocol metadata for content-defined chunking",
    )

    model_config = {"arbitrary_types_allowed": True}


class WebTorrentConfig(BaseModel):
    """WebTorrent protocol configuration."""

    enable_webtorrent: bool = Field(
        default=False,
        description="Enable WebTorrent protocol support",
    )
    webtorrent_signaling_url: str | None = Field(
        default=None,
        description="WebTorrent signaling server URL (optional, uses built-in server if None)",
    )
    webtorrent_port: int = Field(
        default=64126,
        ge=1024,
        le=65535,
        description="WebSocket signaling server port",
    )
    webtorrent_host: str = Field(
        default="localhost",
        description="WebSocket signaling server host",
    )
    webtorrent_stun_servers: list[str] = Field(
        default_factory=lambda: ["stun:stun.l.google.com:19302"],
        description="STUN server URLs for ICE",
    )
    webtorrent_turn_servers: list[str] = Field(
        default_factory=list,
        description="TURN server URLs for ICE",
    )
    webtorrent_max_connections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum WebRTC connections",
    )
    webtorrent_connection_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="WebRTC connection timeout in seconds",
    )


class ProtocolV2Config(BaseModel):
    """BitTorrent Protocol v2 (BEP 52) configuration.

    Controls support for BitTorrent Protocol v2 features including:
    - SHA-256 hashing
    - File tree structure
    - Piece layers
    - Hybrid torrent support (v1 + v2)
    """

    enable_protocol_v2: bool = Field(
        default=True,
        description="Enable BitTorrent Protocol v2 support (BEP 52)",
    )
    prefer_protocol_v2: bool = Field(
        default=False,
        description="Prefer v2 protocol when both v1 and v2 are available",
    )
    support_hybrid: bool = Field(
        default=True,
        description="Support hybrid torrents (both v1 and v2 metadata)",
    )
    v2_handshake_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="v2 handshake timeout in seconds",
    )


class UTPConfig(BaseModel):
    """uTP (uTorrent Transport Protocol) configuration.

    BEP 29: uTP provides reliable, ordered delivery over UDP with
    delay-based congestion control.
    """

    prefer_over_tcp: bool = Field(
        default=True,
        description="Prefer uTP over TCP when both are supported by peer",
    )
    connection_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="uTP connection timeout in seconds",
    )
    max_window_size: int = Field(
        default=65535,
        ge=8192,
        le=65535,
        description="Maximum uTP receive window size in bytes",
    )
    mtu: int = Field(
        default=1200,
        ge=576,
        le=65507,
        description="uTP MTU size (maximum UDP packet size)",
    )
    initial_rate: int = Field(
        default=1500,
        ge=1024,
        le=100000,
        description="Initial send rate in bytes/second",
    )
    min_rate: int = Field(
        default=512,
        ge=256,
        le=10000,
        description="Minimum send rate in bytes/second",
    )
    max_rate: int = Field(
        default=1000000,
        ge=10000,
        le=10000000,
        description="Maximum send rate in bytes/second",
    )
    ack_interval: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="ACK packet send interval in seconds",
    )
    retransmit_timeout_factor: float = Field(
        default=4.0,
        ge=2.0,
        le=10.0,
        description="RTT multiplier for retransmit timeout calculation",
    )
    max_retransmits: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Maximum retransmission attempts before connection failure",
    )


class NetworkConfig(BaseModel):
    """Network configuration."""

    max_global_peers: int = Field(
        default=200,
        ge=1,
        le=10000,
        description="Maximum global peers",
    )
    max_peers_per_torrent: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum peers per torrent",
    )
    pipeline_depth: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Request pipeline depth",
    )
    block_size_kib: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Block size in KiB",
    )
    min_block_size_kib: int = Field(
        default=4,
        ge=1,
        le=64,
        description="Minimum block size in KiB",
    )
    max_block_size_kib: int = Field(
        default=64,
        ge=1,
        le=1024,
        description="Maximum block size in KiB",
    )
    listen_port: int = Field(
        default=64122,
        ge=1024,
        le=65535,
        description="Listen port (deprecated: use listen_port_tcp and listen_port_udp)",
    )
    listen_port_tcp: int | None = Field(
        default=None,
        ge=1024,
        le=65535,
        description="TCP listen port for incoming peer connections",
    )
    listen_port_udp: int | None = Field(
        default=None,
        ge=1024,
        le=65535,
        description="UDP listen port for incoming peer connections",
    )
    tracker_udp_port: int | None = Field(
        default=None,
        ge=1024,
        le=65535,
        description="UDP port for tracker client communication",
    )
    xet_port: int | None = Field(
        default=None,
        ge=1024,
        le=65535,
        description="XET protocol port (uses listen_port_udp if not set)",
    )
    xet_multicast_address: str = Field(
        default="239.255.255.250",
        description="XET multicast address for local network discovery",
    )
    xet_multicast_port: int = Field(
        default=6882,
        ge=1024,
        le=65535,
        description="XET multicast port",
    )
    listen_interface: str | None = Field(
        default="0.0.0.0",  # nosec B104 - Default bind address for network services
        description="Listen interface",
    )
    enable_ipv6: bool = Field(default=True, description="Enable IPv6")
    enable_tcp: bool = Field(default=True, description="Enable TCP transport")
    enable_utp: bool = Field(default=False, description="Enable uTP transport")
    utp: UTPConfig = Field(
        default_factory=UTPConfig,
        description="uTP transport configuration",
    )
    enable_encryption: bool = Field(
        default=False,
        description="Enable protocol encryption",
    )
    socket_rcvbuf_kib: int = Field(
        default=256,
        ge=1,
        le=65536,
        description="Socket receive buffer size in KiB",
    )
    socket_sndbuf_kib: int = Field(
        default=256,
        ge=1,
        le=65536,
        description="Socket send buffer size in KiB",
    )
    tcp_nodelay: bool = Field(default=True, description="Enable TCP_NODELAY")
    max_connections_per_peer: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Max parallel connections per peer",
    )
    announce_interval: int = Field(
        default=1800,
        ge=60,
        le=86400,
        description="Announce interval in seconds",
    )

    # Connection settings
    connection_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Connection timeout in seconds",
    )
    handshake_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Handshake timeout in seconds",
    )
    keep_alive_interval: float = Field(
        default=120.0,
        ge=30.0,
        le=600.0,
        description="Keep alive interval in seconds",
    )
    peer_timeout: float = Field(
        default=60.0,
        ge=5.0,
        le=600.0,
        description="Peer inactivity timeout in seconds",
    )
    webtorrent: WebTorrentConfig = Field(
        default_factory=WebTorrentConfig,
        description="WebTorrent protocol configuration",
    )
    dht_timeout: float = Field(
        default=2.0,
        ge=1.0,
        le=60.0,
        description="DHT request timeout in seconds",
    )
    
    # Adaptive handshake timeout settings
    handshake_adaptive_timeout_enabled: bool = Field(
        default=True,
        description="Enable adaptive handshake timeouts based on peer health",
    )
    handshake_timeout_desperation_min: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Minimum handshake timeout in seconds for desperation mode (< 5 peers)",
    )
    handshake_timeout_desperation_max: float = Field(
        default=60.0,
        ge=30.0,
        le=180.0,
        description="Maximum handshake timeout in seconds for desperation mode (< 5 peers)",
    )
    handshake_timeout_normal_min: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Minimum handshake timeout in seconds for normal mode (5-20 peers)",
    )
    handshake_timeout_normal_max: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Maximum handshake timeout in seconds for normal mode (5-20 peers)",
    )
    handshake_timeout_healthy_min: float = Field(
        default=20.0,
        ge=10.0,
        le=120.0,
        description="Minimum handshake timeout in seconds for healthy mode (20+ peers)",
    )
    handshake_timeout_healthy_max: float = Field(
        default=40.0,
        ge=20.0,
        le=180.0,
        description="Maximum handshake timeout in seconds for healthy mode (20+ peers)",
    )

    # Connection health and validation settings (BitTorrent spec compliant)
    metadata_exchange_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=300.0,
        description="Metadata exchange timeout in seconds (BEP 9 compliant)",
    )
    metadata_piece_timeout: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Timeout per metadata piece request in seconds",
    )
    connection_health_check_interval: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Interval between connection health checks in seconds",
    )
    connection_validation_enabled: bool = Field(
        default=True,
        description="Enable connection state validation (BitTorrent spec compliant)",
    )
    connection_retry_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum connection retry attempts before giving up",
    )
    connection_retry_backoff_base: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Exponential backoff base for connection retries",
    )
    connection_retry_backoff_max: float = Field(
        default=60.0,
        ge=10.0,
        le=300.0,
        description="Maximum backoff delay in seconds between connection retries",
    )
    peer_validation_enabled: bool = Field(
        default=True,
        description="Enable peer validation before accepting connections",
    )
    peer_validation_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Timeout for peer validation in seconds",
    )
    connection_state_validation_enabled: bool = Field(
        default=True,
        description="Enable connection state validation to prevent stale connections",
    )
    connection_state_timeout: float = Field(
        default=120.0,
        ge=30.0,
        le=600.0,
        description="Timeout for connection state validation in seconds",
    )
    send_bitfield_after_metadata: bool = Field(
        default=True,
        description="Send bitfield to peers after metadata exchange completes (BEP 3 compliant)",
    )
    send_interested_after_metadata: bool = Field(
        default=True,
        description="Send INTERESTED message after metadata exchange completes (BEP 3 compliant)",
    )
    graceful_disconnect_enabled: bool = Field(
        default=True,
        description="Enable graceful disconnection with proper protocol messages",
    )
    connection_cleanup_delay: float = Field(
        default=2.0,
        ge=0.0,
        le=10.0,
        description="Delay before cleaning up disconnected connections in seconds",
    )
    max_concurrent_connection_attempts: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Maximum concurrent connection attempts to prevent OS socket exhaustion (BitTorrent spec compliant)",
    )
    connection_failure_threshold: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of consecutive failures before applying backoff to a peer",
    )
    connection_failure_backoff_base: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Exponential backoff base multiplier for connection failures",
    )
    connection_failure_backoff_max: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Maximum backoff delay in seconds for failed connection attempts",
    )
    enable_fail_fast_dht: bool = Field(
        default=True,
        description="Enable fail-fast DHT trigger when active_peers == 0 for >30s (allows DHT even if <50 peers)",
    )
    fail_fast_dht_timeout: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Timeout in seconds before triggering fail-fast DHT when active_peers == 0",
    )

    # Rate limiting
    global_down_kib: int = Field(
        default=0,
        ge=0,
        description="Global download limit in KiB/s (0 = unlimited)",
    )
    global_up_kib: int = Field(
        default=0,
        ge=0,
        description="Global upload limit in KiB/s (0 = unlimited)",
    )
    per_peer_down_kib: int = Field(
        default=0,
        ge=0,
        description="Per-peer download limit in KiB/s (0 = unlimited)",
    )
    per_peer_up_kib: int = Field(
        default=0,
        ge=0,
        description="Per-peer upload limit in KiB/s (0 = unlimited)",
    )

    # Upload slots
    max_upload_slots: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum upload slots",
    )

    # Choking strategy
    optimistic_unchoke_interval: float = Field(
        default=30.0,
        ge=1.0,
        le=600.0,
        description="Optimistic unchoke interval in seconds",
    )
    unchoke_interval: float = Field(
        default=10.0,
        ge=1.0,
        le=600.0,
        description="Unchoke interval in seconds",
    )
    
    # IMPROVEMENT: Choking optimization weights
    choking_upload_rate_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for upload rate in choking/unchoking decisions (0.0-1.0)",
    )
    choking_download_rate_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for download rate in choking/unchoking decisions (0.0-1.0)",
    )
    choking_performance_score_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for performance score in choking/unchoking decisions (0.0-1.0)",
    )
    
    # IMPROVEMENT: Peer quality ranking weights
    peer_quality_performance_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for historical performance in peer quality ranking (0.0-1.0)",
    )
    peer_quality_success_rate_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for connection success rate in peer quality ranking (0.0-1.0)",
    )
    peer_quality_source_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for source quality in peer quality ranking (0.0-1.0)",
    )
    peer_quality_proximity_weight: float = Field(
        default=0.05,  # RELAXED: Reduced from 0.2 to 0.05 to allow distant peers
        ge=0.0,
        le=1.0,
        description="Weight for geographic proximity in peer quality ranking (0.0-1.0). Lower values allow connecting to distant/slower peers.",
    )

    # Tracker settings
    tracker_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Tracker request timeout in seconds",
    )
    tracker_connect_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Tracker connection timeout in seconds",
    )
    tracker_connection_limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum tracker connections",
    )
    tracker_connections_per_host: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum connections per tracker host",
    )
    dns_cache_ttl: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="DNS cache TTL in seconds",
    )
    tracker_keepalive_timeout: float = Field(
        default=300.0,
        ge=30.0,
        le=3600.0,
        description="Tracker HTTP keepalive timeout in seconds",
    )
    tracker_enable_dns_cache: bool = Field(
        default=True,
        description="Enable DNS caching for tracker requests",
    )
    tracker_dns_cache_ttl: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Tracker DNS cache TTL in seconds",
    )
    protocol_v2: ProtocolV2Config = Field(
        default_factory=ProtocolV2Config,
        description="BitTorrent Protocol v2 (BEP 52) configuration",
    )

    # Connection pool settings
    connection_pool_max_connections: int = Field(
        default=200,
        ge=1,
        le=10000,
        description="Maximum connections in connection pool",
    )
    connection_pool_max_idle_time: float = Field(
        default=300.0,
        ge=1.0,
        le=3600.0,
        description="Maximum idle time before connection is closed (seconds)",
    )
    connection_pool_warmup_enabled: bool = Field(
        default=True,
        description="Enable connection warmup to pre-establish connections",
    )
    connection_pool_warmup_count: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Number of connections to warmup on torrent start",
    )
    connection_pool_health_check_interval: float = Field(
        default=60.0,
        ge=1.0,
        le=600.0,
        description="Interval for connection health checks (seconds)",
    )
    
    # Adaptive connection limit settings
    connection_pool_adaptive_limit_enabled: bool = Field(
        default=True,
        description="Enable adaptive connection limit calculation based on system resources and peer performance",
    )
    connection_pool_adaptive_limit_min: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Minimum adaptive connection limit",
    )
    connection_pool_adaptive_limit_max: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum adaptive connection limit",
    )
    connection_pool_cpu_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=0.95,
        description="CPU usage threshold (0.0-1.0) above which connection limit is reduced",
    )
    connection_pool_memory_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=0.95,
        description="Memory usage threshold (0.0-1.0) above which connection limit is reduced",
    )
    
    # Performance-based recycling settings
    connection_pool_performance_recycling_enabled: bool = Field(
        default=True,
        description="Enable performance-based connection recycling (recycle low-performing connections)",
    )
    connection_pool_performance_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Performance score threshold (0.0-1.0) below which connections are recycled",
    )
    
    # Connection quality scoring settings
    connection_pool_quality_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum connection quality score (0.0-1.0) for connection reuse. Connections below this are recycled.",
    )
    connection_pool_grace_period: float = Field(
        default=60.0,
        ge=0.0,
        le=600.0,
        description="Grace period in seconds for new connections before quality checks (allows time for bandwidth establishment)",
    )
    
    # Connection bandwidth thresholds
    connection_pool_min_download_bandwidth: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum download bandwidth in bytes/second for connections to be considered healthy (0 = disabled)",
    )
    connection_pool_min_upload_bandwidth: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum upload bandwidth in bytes/second for connections to be considered healthy (0 = disabled)",
    )
    
    # Connection health degradation/recovery thresholds
    connection_pool_health_degradation_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Health score threshold (0.0-1.0) below which connection health level is degraded",
    )
    connection_pool_health_recovery_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Health score threshold (0.0-1.0) above which degraded connection health can recover",
    )

    # Timeout and retry settings
    timeout_adaptive: bool = Field(
        default=True,
        description="Enable adaptive timeout calculation based on RTT",
    )
    timeout_min_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Minimum timeout in seconds",
    )
    timeout_max_seconds: float = Field(
        default=300.0,
        ge=10.0,
        le=600.0,
        description="Maximum timeout in seconds",
    )
    timeout_rtt_multiplier: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="RTT multiplier for timeout calculation",
    )
    retry_exponential_backoff: bool = Field(
        default=True,
        description="Use exponential backoff for retries",
    )
    retry_base_delay: float = Field(
        default=10.0,  # Standard initial retry delay (prevents overwhelming peers)
        ge=1.0,
        le=60.0,
        description="Base delay for retry backoff in seconds (standard: 10s)",
    )
    retry_max_delay: float = Field(
        default=300.0,
        ge=10.0,
        le=3600.0,
        description="Maximum delay for retry backoff in seconds",
    )
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker for peer connections",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of failures before opening circuit breaker",
    )
    circuit_breaker_recovery_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Recovery timeout for circuit breaker in seconds",
    )

    # Socket buffer optimization
    socket_adaptive_buffers: bool = Field(
        default=True,
        description="Enable adaptive socket buffer sizing based on BDP",
    )
    socket_min_buffer_kib: int = Field(
        default=64,
        ge=1,
        le=1024,
        description="Minimum socket buffer size in KiB",
    )
    socket_max_buffer_kib: int = Field(
        default=65536,
        ge=64,
        le=1048576,
        description="Maximum socket buffer size in KiB",
    )
    socket_enable_window_scaling: bool = Field(
        default=True,
        description="Enable TCP window scaling for high-speed connections",
    )

    # Pipeline optimization
    pipeline_adaptive_depth: bool = Field(
        default=True,
        description="Enable adaptive pipeline depth based on connection latency",
    )
    pipeline_min_depth: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Minimum pipeline depth",
    )
    pipeline_max_depth: int = Field(
        default=128,
        ge=4,
        le=256,
        description="Maximum pipeline depth (increased for better throughput)",
    )
    pipeline_enable_prioritization: bool = Field(
        default=True,
        description="Enable request prioritization (rarest pieces first)",
    )
    pipeline_enable_coalescing: bool = Field(
        default=True,
        description="Enable request coalescing (combine adjacent requests)",
    )
    pipeline_coalesce_threshold_kib: int = Field(
        default=4,
        ge=1,
        le=64,
        description="Maximum gap in KiB for coalescing adjacent requests",
    )


class NATConfig(BaseModel):
    """NAT traversal configuration."""

    enable_nat_pmp: bool = Field(
        default=True,
        description="Enable NAT-PMP protocol",
    )
    enable_upnp: bool = Field(
        default=True,
        description="Enable UPnP IGD protocol",
    )
    nat_discovery_interval: float = Field(
        default=300.0,
        ge=0.0,
        le=3600.0,
        description="NAT device discovery interval in seconds",
    )
    port_mapping_lease_time: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Port mapping lease time in seconds",
    )
    auto_map_ports: bool = Field(
        default=True,
        description="Automatically map ports on startup",
    )
    map_tcp_port: bool = Field(
        default=True,
        description="Map TCP listen port",
    )
    map_udp_port: bool = Field(
        default=True,
        description="Map UDP listen port",
    )
    map_dht_port: bool = Field(
        default=True,
        description="Map DHT UDP port",
    )
    map_xet_port: bool = Field(
        default=True,
        description="Map XET protocol UDP port",
    )
    map_xet_multicast_port: bool = Field(
        default=False,
        description="Map XET multicast UDP port (usually not needed for multicast)",
    )


class AttributeConfig(BaseModel):
    """BEP 47: File attribute handling configuration."""

    preserve_attributes: bool = Field(
        default=True,
        description="Preserve file attributes (executable, hidden, symlinks)",
    )
    skip_padding_files: bool = Field(
        default=True,
        description="Skip downloading padding files (BEP 47)",
    )
    verify_file_sha1: bool = Field(
        default=False,
        description="Verify file SHA-1 hashes when provided (BEP 47)",
    )
    apply_symlinks: bool = Field(
        default=True,
        description="Create symlinks for files with attr='l'",
    )
    apply_executable_bit: bool = Field(
        default=True,
        description="Set executable bit for files with attr='x'",
    )
    apply_hidden_attr: bool = Field(
        default=True,
        description="Apply hidden attribute for files with attr='h' (Windows)",
    )


class DiskConfig(BaseModel):  # noqa: PLR0913
    """Disk I/O configuration."""

    preallocate: PreallocationStrategy = Field(
        default=PreallocationStrategy.FULL,
        description="Preallocation strategy",
    )
    write_batch_kib: int = Field(
        default=64,
        ge=1,
        le=1024,
        description="Write batch size in KiB",
    )
    write_buffer_kib: int = Field(
        default=1024,
        ge=0,
        le=65536,
        description="Write buffer size in KiB",
    )
    write_batch_timeout_adaptive: bool = Field(
        default=True,
        description="Use adaptive write batching timeout based on storage type",
    )
    write_batch_timeout_ms: float = Field(
        default=5.0,
        ge=0.1,
        le=1000.0,
        description="Write batch timeout in milliseconds (used when adaptive is disabled)",
    )
    write_contiguous_threshold: int = Field(
        default=4096,
        ge=0,
        le=65536,
        description="Maximum gap in bytes to merge writes as contiguous",
    )
    write_queue_priority: bool = Field(
        default=True,
        description="Enable priority queue for writes (checkpoint > metadata > regular)",
    )
    use_mmap: bool = Field(default=True, description="Use memory mapping")
    sparse_files: bool = Field(
        default=False,
        description="Use sparse files if supported",
    )
    hash_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of hash verification workers",
    )
    hash_queue_size: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Hash verification queue size",
    )
    hash_chunk_size: int = Field(
        default=65536,
        ge=1024,
        le=1048576,
        description="Hash verification chunk size in bytes",
    )
    hash_batch_size: int = Field(
        default=4,
        ge=1,
        le=64,
        description="Pieces to verify in parallel batch",
    )
    hash_workers_adaptive: bool = Field(
        default=True,
        description="Dynamically adjust hash worker count with work-stealing",
    )
    hash_chunk_size_adaptive: bool = Field(
        default=True,
        description="Adaptive hash chunk size based on storage speed",
    )
    disk_workers: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Number of disk I/O workers",
    )
    disk_queue_size: int = Field(
        default=200,
        ge=10,
        le=1000,
        description="Disk I/O queue size",
    )
    disk_workers_adaptive: bool = Field(
        default=True,
        description="Dynamically adjust disk worker count based on queue depth",
    )
    disk_workers_min: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Minimum number of disk I/O workers",
    )
    disk_workers_max: int = Field(
        default=16,
        ge=1,
        le=32,
        description="Maximum number of disk I/O workers",
    )
    cache_size_mb: int = Field(
        default=256,
        ge=16,
        le=4096,
        description="Cache size in MB",
    )
    mmap_cache_mb: int = Field(
        default=128,
        ge=16,
        le=2048,
        description="Memory-mapped cache size in MB",
    )
    mmap_cache_cleanup_interval: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="MMap cache cleanup interval in seconds",
    )
    mmap_cache_warmup: bool = Field(
        default=True,
        description="Pre-load frequently accessed files into mmap cache on torrent start",
    )
    mmap_cache_adaptive: bool = Field(
        default=True,
        description="Dynamically adjust mmap cache size based on available memory",
    )
    max_file_size_mb: int | None = Field(
        default=None,
        ge=0,
        le=1048576,  # 1TB max
        description="Maximum file size in MB for storage service (None or 0 = unlimited)",
    )

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, v):
        """Convert 0 to None (unlimited)."""
        return None if v == 0 else v

    # Worker and queue settings

    # Advanced settings
    direct_io: bool = Field(default=False, description="Use direct I/O")
    sync_writes: bool = Field(default=False, description="Synchronize writes")
    read_ahead_kib: int = Field(
        default=64,
        ge=0,
        le=1024,
        description="Read ahead size in KiB",
    )
    read_ahead_adaptive: bool = Field(
        default=True,
        description="Adaptive read-ahead based on access pattern (sequential vs random)",
    )
    read_ahead_max_kib: int = Field(
        default=1024,
        ge=64,
        le=8192,
        description="Maximum read-ahead size in KiB for sequential access",
    )
    read_prefetch_enabled: bool = Field(
        default=True,
        description="Enable read prefetching for predicted next blocks",
    )
    read_parallel_segments: bool = Field(
        default=True,
        description="Parallelize reads across multiple file segments",
    )
    read_buffer_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of read buffers to pool for reuse",
    )
    enable_io_uring: bool = Field(
        default=False,
        description="Enable io_uring on Linux if available",
    )
    io_priority: str = Field(
        default="normal",
        description="I/O priority class: idle, normal, or realtime",
    )
    io_schedule_by_lba: bool = Field(
        default=True,
        description="Sort writes by Logical Block Address (LBA) for optimal disk access",
    )
    nvme_queue_depth: int = Field(
        default=1024,
        ge=64,
        le=65536,
        description="NVMe queue depth for optimal performance",
    )
    download_path: str | None = Field(
        default=None,
        description="Default download path",
    )
    download_dir: str = Field(
        default="downloads",
        description="Download directory",
    )

    # Xet protocol configuration
    xet_enabled: bool = Field(
        default=False,
        description="Enable Xet protocol for content-defined chunking and deduplication",
    )
    xet_chunk_min_size: int = Field(
        default=8192,
        ge=4096,
        le=65536,
        description="Minimum Xet chunk size in bytes",
    )
    xet_chunk_max_size: int = Field(
        default=131072,
        ge=32768,
        le=524288,
        description="Maximum Xet chunk size in bytes",
    )
    xet_chunk_target_size: int = Field(
        default=16384,
        ge=8192,
        le=65536,
        description="Target Xet chunk size in bytes",
    )
    xet_deduplication_enabled: bool = Field(
        default=True,
        description="Enable chunk-level deduplication",
    )
    xet_cache_db_path: str | None = Field(
        default=None,
        description="Path to Xet deduplication cache database (defaults to download_dir/.xet_cache/chunks.db)",
    )
    xet_chunk_store_path: str | None = Field(
        default=None,
        description="Path to Xet chunk storage directory (defaults to download_dir/.xet_chunks)",
    )
    enable_file_deduplication: bool = Field(
        default=True,
        description="Enable file-level deduplication for XET",
    )
    enable_data_aggregation: bool = Field(
        default=True,
        description="Enable data aggregation for batch chunk operations",
    )
    enable_defrag_prevention: bool = Field(
        default=True,
        description="Enable defragmentation prevention for chunk storage",
    )
    xet_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Batch size for XET data aggregation operations",
    )
    defrag_check_interval: float = Field(
        default=3600.0,
        ge=60.0,
        le=86400.0,
        description="Interval in seconds for defragmentation checks",
    )
    xet_use_p2p_cas: bool = Field(
        default=True,
        description="Use peer-to-peer Content Addressable Storage (DHT-based)",
    )
    xet_compression_enabled: bool = Field(
        default=False,
        description="Enable LZ4 compression for stored chunks",
    )

    # Checkpoint settings
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable download checkpointing",
    )
    checkpoint_format: CheckpointFormat = Field(
        default=CheckpointFormat.BOTH,
        description="Checkpoint file format",
    )
    checkpoint_dir: str | None = Field(
        None,
        description="Checkpoint directory (defaults to download_dir/.ccbt/checkpoints)",
    )
    checkpoint_interval: float = Field(
        default=30.0,
        ge=1.0,
        le=3600.0,
        description="Checkpoint save interval in seconds",
    )
    checkpoint_on_piece: bool = Field(
        default=True,
        description="Save checkpoint after each verified piece",
    )
    auto_resume: bool = Field(
        default=True,
        description="Automatically resume from checkpoint on startup",
    )
    checkpoint_compression: bool = Field(
        default=True,
        description="Compress binary checkpoint files",
    )
    checkpoint_compression_algorithm: str = Field(
        default="zstd",
        description="Checkpoint compression algorithm: zstd, gzip, or none",
    )
    checkpoint_incremental: bool = Field(
        default=True,
        description="Use incremental checkpoint saves (only save changed pieces)",
    )
    checkpoint_batch_interval: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Checkpoint batch flush interval in seconds",
    )
    checkpoint_batch_pieces: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of pieces before flushing checkpoint batch",
    )
    checkpoint_deduplication: bool = Field(
        default=True,
        description="Skip checkpoint save if no meaningful changes detected",
    )
    auto_delete_checkpoint_on_complete: bool = Field(
        default=True,
        description="Automatically delete checkpoint when download completes",
    )

    # Fast Resume settings
    fast_resume_enabled: bool = Field(
        default=True,
        description="Enable fast resume support",
    )
    resume_save_interval: float = Field(
        default=30.0,
        ge=1.0,
        le=3600.0,
        description="Interval to save resume data in seconds",
    )
    resume_verify_on_load: bool = Field(
        default=True,
        description="Verify resume data integrity on load",
    )
    resume_verify_pieces: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Number of pieces to verify on resume (0 = disable)",
    )
    resume_data_format_version: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Resume data format version",
    )
    checkpoint_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days to retain checkpoints before cleanup",
    )

    # BEP 47: File attributes configuration
    attributes: AttributeConfig = Field(
        default_factory=AttributeConfig,
        description="File attribute handling configuration (BEP 47)",
    )


class StrategyConfig(BaseModel):
    """Piece selection strategy configuration."""

    piece_selection: PieceSelectionStrategy = Field(
        default=PieceSelectionStrategy.RAREST_FIRST,
        description="Piece selection strategy",
    )
    endgame_duplicates: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Endgame duplicate requests",
    )
    endgame_threshold: float = Field(
        default=0.95,
        ge=0.1,
        le=1.0,
        description="Endgame mode threshold",
    )
    pipeline_capacity: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Request pipeline capacity",
    )
    streaming_mode: bool = Field(default=False, description="Enable streaming mode")

    # Advanced strategy settings
    rarest_first_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Rarest first threshold",
    )
    sequential_window: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Sequential window size (pieces ahead to download)",
    )
    sequential_priority_files: list[str] = Field(
        default_factory=list,
        description="File paths to prioritize in sequential mode",
    )
    sequential_fallback_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fallback to rarest-first if availability < threshold",
    )
    
    # Advanced piece selection strategies
    bandwidth_weighted_rarest_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for bandwidth in bandwidth-weighted rarest-first (0.0=rarity only, 1.0=bandwidth only)",
    )
    progressive_rarest_transition_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Progress threshold for transitioning from sequential to rarest-first in progressive mode",
    )
    adaptive_hybrid_phase_detection_window: int = Field(
        default=10,
        ge=5,
        le=50,
        description="Number of pieces to analyze for phase detection in adaptive hybrid mode",
    )


class OptimizationConfig(BaseModel):
    """Optimization profile configuration."""

    profile: OptimizationProfile = Field(
        default=OptimizationProfile.BALANCED,
        description="Optimization profile to use",
    )
    
    # Profile-specific overrides (applied when profile is not CUSTOM)
    # These allow fine-tuning of profile behavior
    speed_aggressive_peer_recycling: bool = Field(
        default=True,
        description="Aggressively recycle low-performing peers in speed profile",
    )
    efficiency_connection_limit_multiplier: float = Field(
        default=0.8,
        ge=0.5,
        le=1.5,
        description="Connection limit multiplier for efficiency profile (reduces connections for efficiency)",
    )
    low_resource_max_connections: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Maximum connections for low_resource profile",
    )
    
    # Adaptive settings
    enable_adaptive_intervals: bool = Field(
        default=True,
        description="Enable adaptive discovery intervals based on swarm health",
    )
    enable_performance_based_recycling: bool = Field(
        default=True,
        description="Enable performance-based peer connection recycling",
    )
    enable_bandwidth_aware_scheduling: bool = Field(
        default=True,
        description="Enable bandwidth-aware piece request scheduling",
    )


class DiscoveryConfig(BaseModel):
    """Peer discovery configuration."""

    enable_dht: bool = Field(default=True, description="Enable DHT")
    enable_pex: bool = Field(default=True, description="Enable Peer Exchange")
    enable_udp_trackers: bool = Field(default=True, description="Enable UDP trackers")
    enable_http_trackers: bool = Field(default=True, description="Enable HTTP trackers")

    # DHT settings
    dht_port: int = Field(default=64120, ge=1024, le=65535, description="DHT port")
    dht_bootstrap_nodes: list[str] = Field(
        default_factory=lambda: [
            "router.bittorrent.com:6881",
            "dht.transmissionbt.com:6881",
            "router.utorrent.com:6881",
            "dht.libtorrent.org:25401",
            "dht.aelitis.com:6881",
            "router.silotis.us:6881",
            "router.bitcomet.com:6881",
        ],
        description="DHT bootstrap nodes",
    )
    
    # DHT adaptive interval settings
    dht_adaptive_interval_enabled: bool = Field(
        default=True,
        description="Enable adaptive DHT lookup intervals based on swarm health",
    )
    dht_base_refresh_interval: float = Field(
        default=600.0,
        ge=60.0,
        le=3600.0,
        description="Base DHT refresh interval in seconds (used when adaptive is disabled or as base for adaptive calculation)",
    )
    dht_adaptive_interval_min: float = Field(
        default=60.0,
        ge=30.0,
        le=300.0,
        description="Minimum adaptive DHT refresh interval in seconds",
    )
    dht_adaptive_interval_max: float = Field(
        default=1920.0,  # 32 minutes (standard exponential backoff maximum)
        ge=300.0,
        le=3600.0,
        description="Maximum adaptive DHT refresh interval in seconds (32 minutes for standard exponential backoff)",
    )
    dht_quality_tracking_enabled: bool = Field(
        default=True,
        description="Enable DHT node quality tracking (response times, success rates)",
    )
    dht_quality_response_time_window: int = Field(
        default=10,
        ge=5,
        le=50,
        description="Number of recent response times to track per node for quality calculation",
    )
    
    # DHT adaptive timeout settings
    dht_adaptive_timeout_enabled: bool = Field(
        default=True,
        description="Enable adaptive DHT query timeouts based on peer health",
    )
    dht_timeout_desperation_min: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Minimum DHT query timeout in seconds for desperation mode (< 5 peers)",
    )
    dht_timeout_desperation_max: float = Field(
        default=60.0,
        ge=30.0,
        le=180.0,
        description="Maximum DHT query timeout in seconds for desperation mode (< 5 peers)",
    )
    dht_timeout_normal_min: float = Field(
        default=5.0,
        ge=2.0,
        le=30.0,
        description="Minimum DHT query timeout in seconds for normal mode (5-20 peers)",
    )
    dht_timeout_normal_max: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Maximum DHT query timeout in seconds for normal mode (5-20 peers)",
    )
    dht_timeout_healthy_min: float = Field(
        default=10.0,
        ge=5.0,
        le=60.0,
        description="Minimum DHT query timeout in seconds for healthy mode (20+ peers)",
    )
    dht_timeout_healthy_max: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Maximum DHT query timeout in seconds for healthy mode (20+ peers)",
    )

    # Tracker intervals
    tracker_announce_interval: float = Field(
        default=60.0,
        ge=20.0,
        le=86400.0,
        description="Tracker announce interval in seconds",
    )
    tracker_scrape_interval: float = Field(
        default=45.0,
        ge=20.0,
        le=86400.0,
        description="Tracker scrape interval in seconds",
    )
    
    # Tracker adaptive interval settings
    tracker_adaptive_interval_enabled: bool = Field(
        default=True,
        description="Enable adaptive tracker announce intervals based on performance and peer count",
    )
    tracker_adaptive_interval_min: float = Field(
        default=20.0,
        ge=10.0,
        le=300.0,
        description="Minimum adaptive tracker announce interval in seconds",
    )
    tracker_adaptive_interval_max: float = Field(
        default=3600.0,
        ge=300.0,
        le=86400.0,
        description="Maximum adaptive tracker announce interval in seconds",
    )
    tracker_base_announce_interval: float = Field(
        default=1800.0,
        ge=60.0,
        le=86400.0,
        description="Base tracker announce interval in seconds (used when adaptive is disabled or as base for adaptive calculation)",
    )
    tracker_peer_count_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for peer count in tracker performance ranking (0.0-1.0)",
    )
    tracker_performance_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for performance metrics in tracker performance ranking (0.0-1.0)",
    )
    tracker_auto_scrape: bool = Field(
        default=True,
        description="Automatically scrape trackers when adding torrents",
    )
    
    # Default trackers for magnet links without tr= parameters
    default_trackers: list[str] = Field(
        default_factory=lambda: [
            "https://tracker.opentrackr.org:443/announce",
            "https://tracker.torrent.eu.org:443/announce",
            "https://tracker.openbittorrent.com:443/announce",
            "http://tracker.opentrackr.org:1337/announce",
            "http://tracker.openbittorrent.com:80/announce",
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://tracker.openbittorrent.com:80/announce",
        ],
        description="Default trackers to use for magnet links without tr= parameters",
    )

    # PEX
    pex_interval: float = Field(
        default=60.0,
        ge=30.0,  # BEP 11 compliant: minimum 30s (max 1 message per minute)
        le=3600.0,
        description="Peer Exchange announce interval in seconds (BEP 11: max 1 per minute = 60s)",
    )

    # XET chunk discovery settings
    xet_chunk_query_batch_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Batch size for parallel chunk queries",
    )
    xet_chunk_query_max_concurrent: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum concurrent chunk queries",
    )
    # Aggressive initial discovery settings for faster peer discovery on popular torrents
    aggressive_initial_discovery: bool = Field(
        default=True,
        description="Enable aggressive initial discovery mode (shorter intervals for first few announces/queries)",
    )
    aggressive_initial_tracker_interval: float = Field(
        default=30.0,
        ge=10.0,
        le=300.0,
        description="Initial tracker announce interval in seconds when aggressive mode is enabled (for first 5 minutes)",
    )
    aggressive_initial_dht_interval: float = Field(
        default=30.0,
        ge=30.0,  # Minimum 30s to prevent peer blacklisting
        le=60.0,
        description="Initial DHT query interval in seconds when aggressive mode is enabled (for first 5 minutes, minimum 30s)",
    )
    
    # IMPROVEMENT: Aggressive discovery for popular torrents
    aggressive_discovery_popular_threshold: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Minimum peer count to enable aggressive discovery mode",
    )
    aggressive_discovery_active_threshold_kib: float = Field(
        default=1.0,
        ge=0.1,
        le=100.0,
        description="Minimum download rate (KB/s) to enable aggressive discovery mode",
    )
    aggressive_discovery_interval_popular: float = Field(
        default=60.0,
        ge=30.0,  # Minimum 30s to prevent peer blacklisting
        le=300.0,
        description="DHT query interval in seconds for popular torrents (20+ peers, minimum 30s)",
    )
    aggressive_discovery_interval_active: float = Field(
        default=30.0,
        ge=30.0,  # Minimum 30s to prevent peer blacklisting
        le=300.0,
        description="DHT query interval in seconds for actively downloading torrents (>1KB/s, minimum 30s)",
    )
    aggressive_discovery_max_peers_per_query: int = Field(
        default=100,
        ge=50,
        le=500,
        description="Maximum peers to query per DHT query in aggressive mode",
    )
    
    # DHT query parameters (Kademlia algorithm)
    dht_normal_alpha: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Number of parallel queries for normal DHT lookups (BEP 5 alpha parameter)",
    )
    dht_normal_k: int = Field(
        default=16,
        ge=8,
        le=64,
        description="Bucket size for normal DHT lookups (BEP 5 k parameter)",
    )
    dht_normal_max_depth: int = Field(
        default=12,
        ge=3,
        le=30,
        description="Maximum depth for normal DHT iterative lookups",
    )
    dht_aggressive_alpha: int = Field(
        default=8,
        ge=5,
        le=30,
        description="Number of parallel queries for aggressive DHT lookups (BEP 5 alpha parameter)",
    )
    dht_aggressive_k: int = Field(
        default=32,
        ge=16,
        le=128,
        description="Bucket size for aggressive DHT lookups (BEP 5 k parameter)",
    )
    dht_aggressive_max_depth: int = Field(
        default=15,
        ge=5,
        le=50,
        description="Maximum depth for aggressive DHT iterative lookups",
    )
    
    discovery_cache_ttl: float = Field(
        default=60.0,
        ge=1.0,
        le=3600.0,
        description="Discovery result cache TTL in seconds",
    )

    # Private torrent settings (BEP 27)
    strict_private_mode: bool = Field(
        default=True,
        description="Enforce strict BEP 27 rules for private torrents (disable DHT/PEX/LSD)",
    )

    # BEP 53: Magnet URI file index specification
    magnet_respect_indices: bool = Field(
        default=True,
        description="Respect file indices specified in magnet URI (BEP 53 so and x.pe parameters)",
    )

    # BEP 32: IPv6 Extension for DHT
    dht_enable_ipv6: bool = Field(
        default=True,
        description="Enable IPv6 DHT support (BEP 32)",
    )
    dht_prefer_ipv6: bool = Field(
        default=False,
        description="Prefer IPv6 addresses over IPv4 when available",
    )
    dht_ipv6_bootstrap_nodes: list[str] = Field(
        default_factory=list,
        description="IPv6 DHT bootstrap nodes (format: [hostname:port or [IPv6]:port])",
    )

    # BEP 43: Read-only DHT Nodes
    dht_readonly_mode: bool = Field(
        default=False,
        description="Enable read-only DHT mode (BEP 43). Read-only nodes can query but not store data.",
    )

    # BEP 45: Multiple-Address Operation for DHT
    dht_enable_multiaddress: bool = Field(
        default=True,
        description="Enable multi-address support (BEP 45). Nodes can advertise multiple network addresses.",
    )
    dht_max_addresses_per_node: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum number of addresses to track per node (BEP 45)",
    )

    # BEP 44: Storing Arbitrary Data in the DHT
    dht_enable_storage: bool = Field(
        default=False,
        description="Enable DHT storage (BEP 44). Allows storing arbitrary key-value data in DHT.",
    )
    dht_storage_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Storage TTL in seconds (BEP 44). Data expires after this time.",
    )
    dht_max_storage_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum storage value size in bytes (BEP 44). Default 1000 bytes.",
    )

    # BEP 51: DHT Infohash Indexing
    dht_enable_indexing: bool = Field(
        default=True,
        description="Enable infohash indexing (BEP 51). Enables efficient torrent discovery via DHT.",
    )
    dht_index_samples_per_key: int = Field(
        default=8,
        ge=1,
        le=100,
        description="Maximum number of samples per index key (BEP 51). Default 8 samples.",
    )


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    log_file: str | None = Field(None, description="Log file path")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(
        default=64125,
        ge=1024,
        le=65535,
        description="Metrics port",
    )
    enable_peer_tracing: bool = Field(default=False, description="Enable peer tracing")

    # Advanced logging
    structured_logging: bool = Field(default=True, description="Use structured logging")
    log_correlation_id: bool = Field(
        default=True,
        description="Include correlation IDs",
    )
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    metrics_interval: float = Field(
        default=5.0,
        ge=0.5,
        le=3600.0,
        description="Metrics collection interval in seconds",
    )
    trace_file: str | None = Field(default=None, description="Path to write traces")
    alerts_rules_path: str | None = Field(
        default=".ccbt/alerts.json",
        description="Path to alert rules JSON file",
    )

    # Event bus configuration
    event_bus_max_queue_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum size of event queue",
    )
    event_bus_batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of events to process per batch",
    )
    event_bus_batch_timeout: float = Field(
        default=0.05,
        ge=0.001,
        le=1.0,
        description="Timeout in seconds to wait when collecting a batch",
    )
    event_bus_emit_timeout: float = Field(
        default=0.01,
        ge=0.001,
        le=1.0,
        description="Timeout in seconds when trying to emit to a full queue",
    )
    event_bus_queue_full_threshold: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="Queue fullness threshold (0.0-1.0) for dropping low-priority events",
    )
    # Throttle intervals for high-frequency events (seconds)
    event_bus_throttle_dht_node_found: float = Field(
        default=0.1,
        ge=0.001,
        le=10.0,
        description="Throttle interval for dht_node_found events (max events per second = 1/interval)",
    )
    event_bus_throttle_dht_node_added: float = Field(
        default=0.1,
        ge=0.001,
        le=10.0,
        description="Throttle interval for dht_node_added events (max events per second = 1/interval)",
    )
    event_bus_throttle_monitoring_heartbeat: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Throttle interval for monitoring_heartbeat events (max events per second = 1/interval)",
    )
    event_bus_throttle_global_metrics_update: float = Field(
        default=0.5,
        ge=0.1,
        le=10.0,
        description="Throttle interval for global_metrics_update events (max events per second = 1/interval)",
    )


class UIConfig(BaseModel):
    """UI and internationalization configuration."""

    locale: str = Field(
        default="en",
        description="Language/locale code (e.g., 'en', 'es', 'fr')",
    )


class DashboardConfig(BaseModel):
    """Dashboard and web UI configuration."""

    enable_dashboard: bool = Field(
        default=True,
        description="Enable built-in dashboard/web UI",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Dashboard bind host",
    )
    port: int = Field(
        default=9090,
        ge=1024,
        le=65535,
        description="Dashboard HTTP port",
    )
    refresh_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="UI refresh interval in seconds",
    )
    default_view: str = Field(
        default="overview",
        description="Default dashboard view (overview|performance|network|security|alerts)",
    )
    enable_grafana_export: bool = Field(
        default=False,
        description="Enable Grafana dashboard JSON export endpoints",
    )
    # Terminal dashboard specific settings
    terminal_refresh_interval: float = Field(
        default=1.0,
        ge=0.5,
        le=10.0,
        description="Terminal dashboard UI refresh interval in seconds (WebSocket provides real-time updates, polling is backup)",
    )
    terminal_daemon_startup_timeout: float = Field(
        default=90.0,
        ge=10.0,
        le=300.0,
        description="Timeout in seconds for daemon startup checks (includes NAT discovery, DHT bootstrap, IPC server startup)",
    )
    terminal_daemon_initial_wait: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Initial wait time in seconds for IPC server to be ready",
    )
    terminal_daemon_retry_delay: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Delay in seconds between daemon readiness retry attempts",
    )
    terminal_daemon_check_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Interval in seconds for checking daemon readiness during startup",
    )
    terminal_connection_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Timeout in seconds for connecting to daemon after verification",
    )
    terminal_connection_check_interval: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Interval in seconds for checking daemon connection status",
    )


class LimitsConfig(BaseModel):
    """Global and per-scope rate limits and scheduler settings."""

    # Global rate limits (KiB/s, 0 = unlimited)
    global_down_kib: int = Field(
        default=0,
        ge=0,
        description="Global download limit in KiB/s",
    )
    global_up_kib: int = Field(
        default=0,
        ge=0,
        description="Global upload limit in KiB/s",
    )

    # Per-torrent rate limits (KiB/s, 0 = unlimited)
    per_torrent_down_kib: int = Field(
        default=0,
        ge=0,
        description="Per-torrent download limit in KiB/s",
    )
    per_torrent_up_kib: int = Field(
        default=0,
        ge=0,
        description="Per-torrent upload limit in KiB/s",
    )

    # Per-peer rate limits (KiB/s, 0 = unlimited)
    per_peer_up_kib: int = Field(
        default=0,
        ge=0,
        description="Per-peer upload limit in KiB/s",
    )

    # Scheduler
    scheduler_slice_ms: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Scheduler time slice in ms",
    )


class QueueEntry(BaseModel):
    """Represents a torrent in the queue."""

    info_hash: bytes = Field(..., description="Torrent info hash")
    priority: TorrentPriority = Field(
        default=TorrentPriority.NORMAL,
        description="Queue priority",
    )
    queue_position: int = Field(
        default=0,
        ge=0,
        description="Position in queue (0 = highest priority position)",
    )
    added_time: float = Field(
        default_factory=time.time,
        description="Time when added to queue",
    )
    status: str = Field(
        default="queued",
        description="Queue status: queued, active, paused, seeding",
    )
    allocated_down_kib: int = Field(
        default=0,
        ge=0,
        description="Allocated download bandwidth in KiB/s",
    )
    allocated_up_kib: int = Field(
        default=0,
        ge=0,
        description="Allocated upload bandwidth in KiB/s",
    )

    model_config = {"arbitrary_types_allowed": True}


class QueueConfig(BaseModel):
    """Torrent queue management configuration."""

    max_active_torrents: int = Field(
        default=5,
        ge=1,
        le=1000,
        description="Maximum number of active torrents",
    )
    max_active_downloading: int = Field(
        default=3,
        ge=0,
        le=1000,
        description="Maximum active downloading torrents (0 = unlimited)",
    )
    max_active_seeding: int = Field(
        default=2,
        ge=0,
        le=1000,
        description="Maximum active seeding torrents (0 = unlimited)",
    )
    default_priority: TorrentPriority = Field(
        default=TorrentPriority.NORMAL,
        description="Default priority for new torrents",
    )
    bandwidth_allocation_mode: BandwidthAllocationMode = Field(
        default=BandwidthAllocationMode.PROPORTIONAL,
        description="Bandwidth allocation strategy",
    )
    auto_manage_queue: bool = Field(
        default=True,
        description="Automatically start/stop torrents based on queue limits",
    )
    priority_weights: dict[TorrentPriority, float] = Field(
        default_factory=lambda: {
            TorrentPriority.MAXIMUM: 5.0,
            TorrentPriority.HIGH: 2.0,
            TorrentPriority.NORMAL: 1.0,
            TorrentPriority.LOW: 0.5,
        },
        description="Bandwidth weight multipliers per priority",
    )
    priority_bandwidth_kib: dict[TorrentPriority, int] = Field(
        default_factory=lambda: {
            TorrentPriority.MAXIMUM: 1000,
            TorrentPriority.HIGH: 500,
            TorrentPriority.NORMAL: 250,
            TorrentPriority.LOW: 100,
        },
        description="Fixed bandwidth in KiB/s per priority (fixed mode only)",
    )
    save_queue_state: bool = Field(
        default=True,
        description="Save queue state to checkpoint",
    )
    queue_state_save_interval: float = Field(
        default=30.0,
        ge=5.0,
        le=3600.0,
        description="Interval to save queue state in seconds",
    )


class SecurityConfig(BaseModel):
    """Security related configuration."""
    
    peer_quality_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum reputation score (0.0-1.0) for peers to be accepted during discovery. Peers below this threshold are filtered out.",
    )

    enable_encryption: bool = Field(
        default=False,
        description="Enable protocol encryption",
    )
    encryption_mode: str = Field(
        default="preferred",
        description="Encryption mode: disabled, preferred, or required",
    )
    encryption_dh_key_size: int = Field(
        default=768,
        description="DH key size in bits (768 or 1024)",
    )
    encryption_prefer_rc4: bool = Field(
        default=True,
        description="Prefer RC4 cipher for compatibility",
    )
    encryption_allowed_ciphers: list[str] = Field(
        default_factory=lambda: ["rc4", "aes"],
        description="List of allowed cipher types",
    )
    encryption_allow_plain_fallback: bool = Field(
        default=True,
        description="Allow fallback to plain connection if encryption fails",
    )
    validate_peers: bool = Field(
        default=True,
        description="Validate peers before exchanging data",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable security rate limiter",
    )
    max_connections_per_peer: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Maximum parallel connections per peer",
    )
    ip_filter: IPFilterConfig = Field(
        default_factory=lambda: IPFilterConfig(),  # type: ignore[name-defined]
        description="IP filter configuration",
    )
    blacklist: BlacklistConfig = Field(
        default_factory=lambda: BlacklistConfig(),  # type: ignore[name-defined]
        description="Blacklist configuration",
    )
    ssl: SSLConfig = Field(
        default_factory=lambda: SSLConfig(),  # type: ignore[name-defined]
        description="SSL/TLS configuration",
    )


class MLConfig(BaseModel):
    """Machine learning optimization settings."""

    peer_selection_enabled: bool = Field(
        default=False,
        description="Enable ML-based peer selection",
    )
    piece_prediction_enabled: bool = Field(
        default=False,
        description="Enable ML piece prediction",
    )
    # Future settings can be added here (model paths, thresholds, etc.)


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    enable_proxy: bool = Field(
        default=False,
        description="Enable proxy support",
    )
    proxy_type: str = Field(
        default="http",
        description="Proxy type (http/socks4/socks5)",
    )
    proxy_host: str | None = Field(
        default=None,
        description="Proxy server hostname or IP",
    )
    proxy_port: int | None = Field(
        default=None,
        ge=0,
        le=65535,
        description="Proxy server port (0 when disabled, 1-65535 when enabled)",
    )
    proxy_username: str | None = Field(
        default=None,
        description="Proxy username for authentication",
    )
    proxy_password: str | None = Field(
        default=None,
        description="Proxy password (encrypted in storage)",
    )
    proxy_for_trackers: bool = Field(
        default=True,
        description="Use proxy for tracker requests",
    )
    proxy_for_peers: bool = Field(
        default=False,
        description="Use proxy for peer connections",
    )
    proxy_for_webseeds: bool = Field(
        default=True,
        description="Use proxy for WebSeed requests",
    )
    proxy_bypass_list: list[str] = Field(
        default_factory=list,
        description="Hosts/IPs to bypass proxy (localhost and 127.0.0.1 always bypassed)",
    )

    @field_validator("proxy_type")
    @classmethod
    def validate_proxy_type(cls, v: str) -> str:
        """Validate proxy type."""
        allowed_types = {"http", "socks4", "socks5"}
        if v.lower() not in allowed_types:
            msg = f"proxy_type must be one of {allowed_types}, got {v}"
            raise ValueError(msg)
        return v.lower()

    @model_validator(mode="after")
    def validate_proxy_config(self) -> ProxyConfig:
        """Validate proxy configuration."""
        if self.enable_proxy:
            if not self.proxy_host:
                msg = "proxy_host is required when enable_proxy is True"
                raise ValueError(msg)
            if not self.proxy_port or self.proxy_port < 1:
                msg = "proxy_port must be >= 1 when enable_proxy is True"
                raise ValueError(msg)
        return self


class IPFilterConfig(BaseModel):
    """IP filter configuration."""

    enable_ip_filter: bool = Field(
        default=False,
        description="Enable IP filtering",
    )
    filter_mode: str = Field(
        default="block",
        description="Filter mode: block (default) or allow",
    )
    filter_files: list[str] = Field(
        default_factory=list,
        description="Paths to filter files (PeerGuardian format)",
    )
    filter_urls: list[str] = Field(
        default_factory=list,
        description="URLs to download filter lists from",
    )
    filter_update_interval: float = Field(
        default=86400.0,
        ge=3600.0,
        le=604800.0,
        description="Filter list update interval in seconds (1h-7d)",
    )
    filter_cache_dir: str = Field(
        default="~/.ccbt/filters",
        description="Directory to cache downloaded filter lists",
    )
    filter_log_blocked: bool = Field(
        default=True,
        description="Log blocked connection attempts",
    )

    @field_validator("filter_mode")
    @classmethod
    def validate_filter_mode(cls, v: str) -> str:
        """Validate filter mode."""
        allowed_modes = {"block", "allow"}
        v_lower = v.lower()
        if v_lower not in allowed_modes:
            msg = f"filter_mode must be one of {allowed_modes}, got {v}"
            raise ValueError(msg)
        return v_lower


class LocalBlacklistSourceConfig(BaseModel):
    """Configuration for local metric-based blacklist source."""

    enabled: bool = Field(
        default=True,
        description="Enable local metric-based blacklisting",
    )
    evaluation_interval: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Evaluation interval in seconds (1m-1h)",
    )
    metric_window: float = Field(
        default=3600.0,
        ge=300.0,
        le=86400.0,
        description="Metric aggregation window in seconds (5m-24h)",
    )
    thresholds: dict[str, Any] = Field(
        default_factory=lambda: {
            "failed_handshakes": 5,  # Blacklist after 5 failed handshakes
            "handshake_failure_rate": 0.8,  # 80% failure rate
            "spam_score": 10.0,  # Spam score threshold
            "violation_count": 3,  # 3 protocol violations
            "reputation_threshold": 0.2,  # Reputation below 0.2
            "connection_attempt_rate": 20,  # 20 attempts per minute
        },
        description="Thresholds for automatic blacklisting",
    )
    expiration_hours: float | None = Field(
        default=24.0,
        description="Expiration time for auto-blacklisted IPs (hours, None = permanent)",
    )
    min_observations: int = Field(
        default=3,
        ge=1,
        description="Minimum observations before blacklisting",
    )


class BlacklistConfig(BaseModel):
    """Blacklist configuration."""

    enable_persistence: bool = Field(
        default=True,
        description="Persist blacklist to disk",
    )
    blacklist_file: str = Field(
        default="~/.ccbt/security/blacklist.json",
        description="Path to blacklist file",
    )
    auto_update_enabled: bool = Field(
        default=False,
        description="Enable automatic blacklist updates",
    )
    auto_update_interval: float = Field(
        default=3600.0,
        ge=300.0,
        le=86400.0,
        description="Auto-update interval in seconds (5m-24h)",
    )
    auto_update_sources: list[str] = Field(
        default_factory=list,
        description="URLs for automatic blacklist updates",
    )
    default_expiration_hours: float | None = Field(
        default=None,
        description="Default expiration time for auto-blacklisted IPs in hours (None = permanent)",
    )
    local_source: LocalBlacklistSourceConfig = Field(
        default_factory=LocalBlacklistSourceConfig,
        description="Local metric-based blacklist source configuration",
    )


class MetricsPluginConfig(BaseModel):
    """Configuration for the metrics plugin."""

    enable_metrics_plugin: bool = Field(
        default=True,
        description="Enable the metrics plugin for event-driven metrics collection",
    )
    max_metrics: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum number of metrics to keep in memory",
    )
    enable_event_metrics: bool = Field(
        default=True,
        description="Enable event-driven metrics collection",
    )
    metrics_retention_seconds: int = Field(
        default=3600,
        ge=0,
        description="Metrics retention period in seconds (0 = unlimited)",
    )
    enable_aggregation: bool = Field(
        default=True,
        description="Enable metric aggregation",
    )
    aggregation_window: float = Field(
        default=60.0,
        ge=1.0,
        le=3600.0,
        description="Aggregation window in seconds",
    )


class PluginsConfig(BaseModel):
    """Configuration for the plugin system."""

    enable_plugins: bool = Field(
        default=True,
        description="Enable/disable plugin system",
    )
    auto_load_plugins: bool = Field(
        default=True,
        description="Automatically load plugins from configured directories",
    )
    plugin_directories: list[str] = Field(
        default_factory=list,
        description="Directories to search for plugins",
    )
    metrics: MetricsPluginConfig = Field(
        default_factory=MetricsPluginConfig,
        description="Metrics plugin configuration",
    )


class SSLConfig(BaseModel):
    """SSL/TLS configuration."""

    enable_ssl_trackers: bool = Field(
        default=True,
        description="Enable SSL/TLS for tracker connections (HTTPS)",
    )
    enable_ssl_peers: bool = Field(
        default=False,
        description="Enable SSL/TLS for peer connections (experimental)",
    )
    ssl_verify_certificates: bool = Field(
        default=True,
        description="Verify SSL certificates",
    )
    ssl_ca_certificates: str | None = Field(
        default=None,
        description="Path to CA certificates file or directory",
    )
    ssl_client_certificate: str | None = Field(
        default=None,
        description="Path to client certificate file (PEM format)",
    )
    ssl_client_key: str | None = Field(
        default=None,
        description="Path to client private key file (PEM format)",
    )
    ssl_protocol_version: str = Field(
        default="TLSv1.2",
        description="Minimum TLS protocol version (TLSv1.2, TLSv1.3, PROTOCOL_TLS)",
    )
    ssl_cipher_suites: list[str] = Field(
        default_factory=list,
        description="Allowed cipher suites (empty = system default)",
    )
    ssl_allow_insecure_peers: bool = Field(
        default=True,
        description="Allow peers with invalid certificates (for opportunistic encryption)",
    )
    ssl_extension_enabled: bool = Field(
        default=True,
        description="Enable SSL/TLS extension protocol (BEP 47) for opportunistic encryption",
    )
    ssl_extension_opportunistic: bool = Field(
        default=True,
        description="Fallback to plain connection if SSL extension negotiation fails",
    )
    ssl_extension_timeout: float = Field(
        default=5.0,
        description="Timeout in seconds for SSL extension negotiation",
        ge=0.1,
        le=60.0,
    )

    @field_validator("ssl_protocol_version")
    @classmethod
    def validate_protocol_version(cls, v: str) -> str:
        """Validate protocol version."""
        allowed_versions = {"TLSv1.2", "TLSv1.3", "PROTOCOL_TLS"}
        if v not in allowed_versions:
            msg = f"ssl_protocol_version must be one of {allowed_versions}, got {v}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_client_cert_config(self) -> SSLConfig:
        """Validate client certificate configuration."""
        if self.ssl_client_certificate and not self.ssl_client_key:
            msg = "ssl_client_key is required when ssl_client_certificate is set"
            raise ValueError(msg)
        if self.ssl_client_key and not self.ssl_client_certificate:
            msg = "ssl_client_certificate is required when ssl_client_key is set"
            raise ValueError(msg)
        return self


class PieceCheckpoint(BaseModel):
    """Checkpoint data for a single piece."""

    index: int = Field(..., ge=0, description="Piece index")
    state: PieceState = Field(..., description="Piece state")
    hash_verified: bool = Field(
        default=False,
        description="Whether piece hash is verified",
    )
    priority: int = Field(default=0, description="Piece priority")
    request_count: int = Field(
        default=0,
        description="Number of times piece was requested",
    )


class DownloadStats(BaseModel):
    """Download statistics for checkpoint."""

    bytes_downloaded: int = Field(default=0, ge=0, description="Total bytes downloaded")
    download_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Total download time in seconds",
    )
    average_speed: float = Field(
        default=0.0,
        ge=0.0,
        description="Average download speed in bytes/sec",
    )
    start_time: float = Field(default=0.0, description="Download start timestamp")
    last_update: float = Field(
        default=0.0,
        description="Last checkpoint update timestamp",
    )


class FileCheckpoint(BaseModel):
    """File information for checkpoint."""

    path: str = Field(..., description="File path")
    size: int = Field(..., ge=0, description="File size in bytes")
    exists: bool = Field(default=False, description="Whether file exists on disk")
    # BEP 47: File attributes
    attributes: str | None = Field(
        None,
        description="File attributes string (BEP 47, e.g., 'p', 'x', 'h', 'l')",
    )
    symlink_path: str | None = Field(
        None,
        description="Symlink target path (BEP 47, required when attr='l')",
    )
    file_sha1: bytes | None = Field(
        None,
        description="File SHA-1 hash (BEP 47, 20 bytes if provided)",
    )


class TorrentCheckpoint(BaseModel):
    """Complete torrent download checkpoint."""

    version: str = Field(default="1.0", description="Checkpoint format version")
    info_hash: bytes = Field(
        ...,
        min_length=20,
        max_length=20,
        description="Torrent info hash",
    )
    torrent_name: str = Field(..., description="Torrent name")
    created_at: float = Field(
        default_factory=time.time, description="Checkpoint creation timestamp"
    )
    updated_at: float = Field(
        default_factory=time.time, description="Last update timestamp"
    )

    # Torrent metadata
    total_pieces: int = Field(..., ge=0, description="Total number of pieces")
    piece_length: int = Field(default=16384, gt=0, description="Standard piece length")
    total_length: int = Field(default=0, ge=0, description="Total torrent size")

    # Download state
    verified_pieces: list[int] = Field(
        default_factory=list,
        description="List of verified piece indices",
    )
    piece_states: dict[int, PieceState] = Field(
        default_factory=dict,
        description="Piece states by index",
    )
    download_stats: DownloadStats | None = Field(
        default_factory=DownloadStats,
        description="Download statistics",
    )

    @field_validator("piece_states", mode="before")
    @classmethod
    def _coerce_piece_states(cls, v):
        """Coerce piece_states list to dict for test compatibility."""
        if isinstance(v, list):
            return {}
        return v

    @field_validator("download_stats", mode="before")
    @classmethod
    def _coerce_download_stats(cls, v):
        """Coerce None download_stats to default."""
        if v is None:
            return DownloadStats()
        return v

    # File information
    output_dir: str = Field(default="", description="Output directory")
    files: list[FileCheckpoint] = Field(
        default_factory=list,
        description="File information",
    )

    # Optional metadata
    peer_info: dict[str, Any] | None = Field(
        None,
        description="Peer availability info",
    )
    endgame_mode: bool = Field(default=False, description="Whether in endgame mode")

    # Torrent source metadata for resume functionality
    torrent_file_path: str | None = Field(
        None,
        description="Path to original .torrent file",
    )
    magnet_uri: str | None = Field(None, description="Original magnet link")
    announce_urls: list[str] = Field(
        default_factory=list,
        description="Tracker announce URLs",
    )
    display_name: str | None = Field(None, description="Torrent display name")

    # Fast resume data (optional)
    resume_data: dict[str, Any] | None = Field(
        None,
        description="Fast resume data (serialized FastResumeData)",
    )

    # File selection state
    file_selections: dict[int, dict[str, Any]] | None = Field(
        None,
        description="File selection state: {file_index: {selected: bool, priority: str, bytes_downloaded: int}}",
    )

    # Per-torrent configuration options
    per_torrent_options: dict[str, Any] | None = Field(
        None,
        description="Per-torrent configuration options (piece_selection, streaming_mode, max_peers_per_torrent, etc.)",
    )

    # Per-torrent rate limits
    rate_limits: dict[str, int] | None = Field(
        None,
        description="Per-torrent rate limits: {down_kib: int, up_kib: int}",
    )

    # Peer lists and state
    connected_peers: list[dict[str, Any]] | None = Field(
        None,
        description="List of connected peers: [{ip, port, peer_id, peer_source, stats}]",
    )
    active_peers: list[dict[str, Any]] | None = Field(
        None,
        description="List of active peers (subset of connected): [{ip, port, ...}]",
    )
    peer_statistics: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Peer statistics by peer_key: {peer_key: {bytes_downloaded, bytes_uploaded, ...}}",
    )

    # Tracker lists and state
    tracker_list: list[dict[str, Any]] | None = Field(
        None,
        description="List of trackers: [{url, last_announce, last_success, is_healthy, failure_count}]",
    )
    tracker_health: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Tracker health metrics: {url: {last_announce, last_success, failure_count, ...}}",
    )

    # Security state
    peer_whitelist: list[str] | None = Field(
        None,
        description="Per-torrent peer whitelist (IP addresses)",
    )
    peer_blacklist: list[str] | None = Field(
        None,
        description="Per-torrent peer blacklist (IP addresses)",
    )

    # Session state
    session_state: str | None = Field(
        None,
        description="Session state: 'active', 'paused', 'stopped', 'queued', 'seeding'",
    )
    session_state_timestamp: float | None = Field(
        None,
        description="Timestamp when session state changed",
    )

    # Event history
    recent_events: list[dict[str, Any]] | None = Field(
        None,
        description="Recent events for debugging: [{event_type, timestamp, data}]",
    )

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _coerce_compat_fields(self) -> TorrentCheckpoint:
        """Coerce legacy/loose inputs used in tests into valid structures.

        - Allow piece_states to be provided as a list (treated as empty mapping)
        - Replace download_stats None with default DownloadStats()
        """
        if isinstance(self.piece_states, list):
            self.piece_states = {}
        if self.download_stats is None:
            self.download_stats = DownloadStats()
        # Backward compatibility: ensure new fields default to None if not present
        # (Pydantic handles this automatically, but explicit for clarity)
        return self


class GlobalCheckpoint(BaseModel):
    """Global session manager checkpoint."""

    version: str = Field(default="1.0", description="Checkpoint format version")
    created_at: float = Field(
        default_factory=time.time, description="Checkpoint creation timestamp"
    )
    updated_at: float = Field(
        default_factory=time.time, description="Last update timestamp"
    )

    # Global state
    active_torrents: list[bytes] = Field(
        default_factory=list,
        description="List of active torrent info hashes",
    )
    paused_torrents: list[bytes] = Field(
        default_factory=list,
        description="List of paused torrent info hashes",
    )
    queued_torrents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Queue state: [{info_hash, position, priority, status}]",
    )

    # Global limits
    global_rate_limits: dict[str, int] | None = Field(
        None,
        description="Global rate limits: {down_kib: int, up_kib: int}",
    )

    # Global security state
    global_peer_whitelist: list[str] = Field(
        default_factory=list,
        description="Global peer whitelist",
    )
    global_peer_blacklist: list[str] = Field(
        default_factory=list,
        description="Global peer blacklist",
    )

    # DHT state
    dht_nodes: list[dict[str, Any]] | None = Field(
        None,
        description="Known DHT nodes: [{ip, port, node_id, last_seen}]",
    )

    # Global statistics
    global_stats: dict[str, Any] | None = Field(
        None,
        description="Global statistics snapshot",
    )

    model_config = {"arbitrary_types_allowed": True}


class PerTorrentOptions(BaseModel):
    """Per-torrent configuration options for validation."""

    piece_selection: str | None = Field(
        None,
        description="Piece selection strategy: round_robin, rarest_first, sequential",
    )
    streaming_mode: bool | None = Field(
        None, description="Enable streaming mode for sequential download"
    )
    sequential_window_size: int | None = Field(
        None,
        ge=1,
        description="Number of pieces ahead to download in sequential mode",
    )
    max_peers_per_torrent: int | None = Field(
        None,
        ge=0,
        description="Maximum peers for this torrent (0 = unlimited)",
    )
    enable_tcp: bool | None = Field(None, description="Enable TCP transport")
    enable_utp: bool | None = Field(None, description="Enable uTP transport")
    enable_encryption: bool | None = Field(
        None, description="Enable protocol encryption (BEP 3)"
    )
    auto_scrape: bool | None = Field(
        None, description="Automatically scrape tracker on torrent add"
    )
    enable_nat_mapping: bool | None = Field(
        None, description="Enable NAT port mapping for this torrent"
    )
    enable_xet: bool | None = Field(
        None, description="Enable XET folder synchronization for this torrent"
    )
    xet_sync_mode: str | None = Field(
        None,
        description="XET sync mode for this torrent (designated/best_effort/broadcast/consensus)",
    )
    xet_allowlist_path: str | None = Field(
        None, description="Path to XET allowlist file for this torrent"
    )

    @field_validator("piece_selection")
    @classmethod
    def validate_piece_selection(cls, v: str | None) -> str | None:
        """Validate piece_selection is a valid strategy."""
        if v is None:
            return v
        valid_strategies = {"round_robin", "rarest_first", "sequential"}
        if v not in valid_strategies:
            msg = f"Invalid piece_selection: {v}. Must be one of {valid_strategies}"
            raise ValueError(msg)
        return v

    @field_validator("xet_sync_mode")
    @classmethod
    def validate_xet_sync_mode(cls, v: str | None) -> str | None:
        """Validate xet_sync_mode is a valid mode."""
        if v is None:
            return v
        valid_modes = {"designated", "best_effort", "broadcast", "consensus"}
        if v not in valid_modes:
            msg = f"Invalid xet_sync_mode: {v}. Must be one of {valid_modes}"
            raise ValueError(msg)
        return v


class PerTorrentDefaultsConfig(BaseModel):
    """Default per-torrent configuration options applied to new torrents."""

    piece_selection: str | None = Field(
        None,
        description="Default piece selection strategy: round_robin, rarest_first, sequential",
    )
    streaming_mode: bool | None = Field(
        None, description="Default streaming mode for sequential download"
    )
    sequential_window_size: int | None = Field(
        None,
        ge=1,
        description="Default number of pieces ahead to download in sequential mode",
    )
    max_peers_per_torrent: int | None = Field(
        None,
        ge=0,
        description="Default maximum peers for torrents (0 = unlimited)",
    )
    enable_tcp: bool | None = Field(None, description="Default TCP transport enabled")
    enable_utp: bool | None = Field(None, description="Default uTP transport enabled")
    enable_encryption: bool | None = Field(
        None, description="Default protocol encryption enabled (BEP 3)"
    )
    auto_scrape: bool | None = Field(
        None, description="Default auto-scrape tracker on torrent add"
    )
    enable_nat_mapping: bool | None = Field(
        None, description="Default NAT port mapping enabled"
    )

    @field_validator("piece_selection")
    @classmethod
    def validate_piece_selection(cls, v: str | None) -> str | None:
        """Validate piece_selection is a valid strategy."""
        if v is None:
            return v
        valid_strategies = {"round_robin", "rarest_first", "sequential"}
        if v not in valid_strategies:
            msg = f"Invalid piece_selection: {v}. Must be one of {valid_strategies}"
            raise ValueError(msg)
        return v


class ScrapeResult(BaseModel):
    """Scrape result for a torrent (BEP 48)."""

    info_hash: bytes = Field(
        ...,
        description="Torrent info hash",
    )
    seeders: int = Field(
        default=0,
        ge=0,
        description="Number of seeders (complete peers)",
    )
    leechers: int = Field(
        default=0,
        ge=0,
        description="Number of leechers (incomplete peers)",
    )
    completed: int = Field(
        default=0,
        ge=0,
        description="Total number of completed downloads",
    )
    last_scrape_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Timestamp of last successful scrape",
    )
    scrape_count: int = Field(
        default=0,
        ge=0,
        description="Number of successful scrapes",
    )

    model_config = {"arbitrary_types_allowed": True}


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    api_key: str | None = Field(default=None, description="API key for authentication (auto-generated if not set)")
    ed25519_public_key: str | None = Field(
        None,
        description="Ed25519 public key for cryptographic authentication (hex format)",
    )
    ed25519_key_path: str | None = Field(
        None,
        description="Path to Ed25519 key storage directory (default: ~/.ccbt/keys)",
    )
    tls_certificate_path: str | None = Field(
        None, description="Path to TLS certificate file for HTTPS support"
    )
    tls_enabled: bool = Field(False, description="Enable TLS/HTTPS for IPC server")
    ipc_host: str = Field(
        "127.0.0.1",
        description="IPC server host (127.0.0.1 for local-only access, 0.0.0.0 for all interfaces)",
    )
    ipc_port: int = Field(64124, ge=1, le=65535, description="IPC server port")
    websocket_enabled: bool = Field(True, description="Enable WebSocket support")
    websocket_heartbeat_interval: float = Field(
        15.0,
        ge=1.0,
        description="WebSocket heartbeat interval in seconds (reduced for faster connection detection)",
    )
    auto_save_interval: float = Field(
        60.0,
        ge=1.0,
        description="Auto-save state interval in seconds",
    )
    state_dir: str | None = Field(
        None,
        description="State directory path (default: ~/.ccbt/daemon)",
    )


class IPFSConfig(BaseModel):
    """IPFS protocol configuration."""

    api_url: str = Field(
        default="http://127.0.0.1:5001",
        description="IPFS daemon API URL",
    )
    gateway_urls: list[str] = Field(
        default_factory=lambda: [
            "https://ipfs.io/ipfs/",
            "https://gateway.pinata.cloud/ipfs/",
            "https://cloudflare-ipfs.com/ipfs/",
        ],
        description="IPFS gateway URLs for fallback content retrieval",
    )
    enable_pinning: bool = Field(
        default=False,
        description="Automatically pin content when added to IPFS",
    )
    connection_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Connection timeout in seconds",
    )
    request_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )
    enable_dht: bool = Field(
        default=True,
        description="Enable DHT for peer discovery",
    )
    discovery_cache_ttl: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Discovery cache TTL in seconds",
    )

    model_config = {"arbitrary_types_allowed": True}


class XetSyncConfig(BaseModel):
    """XET folder synchronization configuration."""

    enable_xet: bool = Field(
        default=False,
        description="Enable XET folder synchronization globally",
    )
    check_interval: float = Field(
        default=5.0,
        ge=0.5,
        le=3600.0,
        description="Interval between folder checks in seconds",
    )
    default_sync_mode: str = Field(
        default="best_effort",
        description="Default synchronization mode (designated/best_effort/broadcast/consensus)",
    )
    enable_git_versioning: bool = Field(
        default=True,
        description="Enable git integration for version tracking",
    )
    enable_lpd: bool = Field(
        default=True,
        description="Enable Local Peer Discovery (BEP 14)",
    )
    enable_gossip: bool = Field(
        default=True,
        description="Enable gossip protocol for update propagation",
    )
    gossip_fanout: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Gossip fanout (number of peers to gossip to)",
    )
    gossip_interval: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Gossip interval in seconds",
    )
    flooding_ttl: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Controlled flooding TTL (max hops)",
    )
    flooding_priority_threshold: int = Field(
        default=100,
        ge=0,
        le=1000,
        description="Priority threshold for using flooding (0-1000)",
    )
    consensus_algorithm: str = Field(
        default="simple",
        description="Consensus algorithm (simple/raft)",
    )
    raft_election_timeout: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Raft election timeout in seconds",
    )
    raft_heartbeat_interval: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="Raft heartbeat interval in seconds",
    )
    enable_byzantine_fault_tolerance: bool = Field(
        default=False,
        description="Enable Byzantine fault tolerance",
    )
    byzantine_fault_threshold: float = Field(
        default=0.33,
        ge=0.0,
        le=0.5,
        description="Byzantine fault threshold (max fraction of faulty nodes)",
    )
    weighted_voting: bool = Field(
        default=False,
        description="Use weighted voting for consensus",
    )
    auto_elect_source: bool = Field(
        default=False,
        description="Automatically elect source peer",
    )
    source_election_interval: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Source peer election interval in seconds",
    )
    conflict_resolution_strategy: str = Field(
        default="last_write_wins",
        description="Conflict resolution strategy (last_write_wins/version_vector/three_way_merge/timestamp)",
    )
    git_auto_commit: bool = Field(
        default=False,
        description="Automatically commit changes on folder updates",
    )
    consensus_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Majority threshold for consensus mode (0.0 to 1.0)",
    )
    max_update_queue_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of queued updates",
    )
    allowlist_encryption_key: str | None = Field(
        None,
        description="Path to allowlist encryption key file",
    )


class Config(BaseModel):
    """Main configuration model."""

    network: NetworkConfig = Field(
        default_factory=NetworkConfig,
        description="Network configuration",
    )
    disk: DiskConfig = Field(
        default_factory=DiskConfig,
        description="Disk configuration",
    )
    strategy: StrategyConfig = Field(
        default_factory=StrategyConfig,
        description="Strategy configuration",
    )
    discovery: DiscoveryConfig = Field(
        default_factory=DiscoveryConfig,
        description="Discovery configuration",
    )
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig,
        description="Observability configuration",
    )
    limits: LimitsConfig = Field(
        default_factory=LimitsConfig,
        description="Rate limit configuration",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security configuration",
    )
    proxy: ProxyConfig = Field(
        default_factory=ProxyConfig,
        description="Proxy configuration",
    )
    ml: MLConfig = Field(
        default_factory=MLConfig,
        description="Machine learning configuration",
    )
    dashboard: DashboardConfig = Field(
        default_factory=DashboardConfig,
        description="Dashboard/web UI configuration",
    )
    ui: UIConfig = Field(
        default_factory=UIConfig,
        description="UI and internationalization configuration",
    )
    queue: QueueConfig = Field(
        default_factory=QueueConfig,
        description="Torrent queue management configuration",
    )
    nat: NATConfig = Field(
        default_factory=NATConfig,
        description="NAT traversal configuration",
    )
    ipfs: IPFSConfig = Field(
        default_factory=IPFSConfig,
        description="IPFS protocol configuration",
    )
    webtorrent: WebTorrentConfig = Field(
        default_factory=WebTorrentConfig,
        description="WebTorrent protocol configuration",
    )
    daemon: DaemonConfig | None = Field(
        None,
        description="Daemon configuration",
    )
    per_torrent_defaults: PerTorrentDefaultsConfig = Field(
        default_factory=PerTorrentDefaultsConfig,
        description="Default per-torrent configuration options applied to new torrents",
    )
    xet_sync: XetSyncConfig = Field(
        default_factory=XetSyncConfig,
        description="XET folder synchronization configuration",
    )
    plugins: PluginsConfig = Field(
        default_factory=PluginsConfig,
        description="Plugin system configuration",
    )
    optimization: OptimizationConfig = Field(
        default_factory=OptimizationConfig,
        description="Optimization profile configuration",
    )

    @model_validator(mode="after")
    def validate_config(self):
        """Validate configuration consistency and port conflicts."""
        network = self.network
        discovery = self.discovery

        # Backward compatibility: if new ports not set, use listen_port
        if network.listen_port_tcp is None:
            network.listen_port_tcp = network.listen_port
        if network.listen_port_udp is None:
            network.listen_port_udp = network.listen_port
        if network.tracker_udp_port is None:
            # Default tracker UDP port to listen_port_udp + 1, or 64123 if that would conflict
            if network.listen_port_udp + 1 != discovery.dht_port:
                network.tracker_udp_port = network.listen_port_udp + 1
            else:
                # Use 64123 as default if listen_port_udp + 1 conflicts with DHT port
                network.tracker_udp_port = 64123

        # Collect all ports for conflict detection (protocol-aware)
        # TCP and UDP can share the same port number (different protocols)
        tcp_ports: dict[str, int] = {}
        udp_ports: dict[str, int] = {}

        if network.listen_port_tcp:
            tcp_ports["TCP listen port"] = network.listen_port_tcp
        if network.listen_port_udp:
            udp_ports["UDP listen port"] = network.listen_port_udp
        if network.tracker_udp_port:
            udp_ports["UDP tracker port"] = network.tracker_udp_port
        if discovery.enable_dht and discovery.dht_port:
            udp_ports["DHT port"] = discovery.dht_port
        if self.daemon and self.daemon.ipc_port:
            tcp_ports["IPC port"] = self.daemon.ipc_port
        if self.observability.metrics_port:
            tcp_ports["Metrics port"] = self.observability.metrics_port
        if self.webtorrent.enable_webtorrent and self.webtorrent.webtorrent_port:
            tcp_ports["WebTorrent port"] = self.webtorrent.webtorrent_port

        # Check for port conflicts within each protocol
        conflicts: list[str] = []

        # Check TCP port conflicts
        seen_tcp_ports: dict[int, list[str]] = {}
        for name, port in tcp_ports.items():
            if port in seen_tcp_ports:
                seen_tcp_ports[port].append(name)
            else:
                seen_tcp_ports[port] = [name]

        for port, names in seen_tcp_ports.items():
            if len(names) > 1:
                conflicts.append(
                    f"TCP port {port} is used by: {', '.join(names)}"
                )

        # Check UDP port conflicts
        seen_udp_ports: dict[int, list[str]] = {}
        for name, port in udp_ports.items():
            if port in seen_udp_ports:
                seen_udp_ports[port].append(name)
            else:
                seen_udp_ports[port] = [name]

        for port, names in seen_udp_ports.items():
            if len(names) > 1:
                conflicts.append(
                    f"UDP port {port} is used by: {', '.join(names)}"
                )

        if conflicts:
            msg = "Port conflicts detected:\n  " + "\n  ".join(conflicts)
            raise ValueError(msg)

        # Legacy validation: DHT port cannot be same as listen port
        if (
            network
            and discovery
            and discovery.enable_dht
            and network.listen_port_tcp == discovery.dht_port
        ):
            msg = "DHT port cannot be the same as TCP listen port"
            raise ValueError(msg)

        # Backwards-compatibility: if limits are set, reflect to network globals when non-zero
        if self.limits:
            if self.limits.global_down_kib and not self.network.global_down_kib:
                self.network.global_down_kib = self.limits.global_down_kib
            if self.limits.global_up_kib and not self.network.global_up_kib:
                self.network.global_up_kib = self.limits.global_up_kib

        return self

    model_config = {"use_enum_values": True}
