"""Pydantic models for ccBitTorrent.

Provides validated data models for type safety and runtime validation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

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
    peer_id: Optional[bytes] = Field(None, description="Peer ID")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v):
        # Basic IP validation - could be enhanced with proper IP address validation
        if not v or len(v) == 0:
            raise ValueError("IP address cannot be empty")
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
    peers: List[PeerInfo] = Field(default_factory=list, description="List of peers")
    complete: Optional[int] = Field(None, ge=0, description="Number of seeders")
    incomplete: Optional[int] = Field(None, ge=0, description="Number of leechers")
    download_url: Optional[str] = Field(None, description="Download URL")
    tracker_id: Optional[str] = Field(None, description="Tracker ID")
    warning_message: Optional[str] = Field(None, description="Warning message")


class PieceInfo(BaseModel):
    """Piece information."""
    index: int = Field(..., ge=0, description="Piece index")
    length: int = Field(..., gt=0, description="Piece length in bytes")
    hash: bytes = Field(..., min_length=20, max_length=20, description="Piece SHA-1 hash")
    state: PieceState = Field(default=PieceState.MISSING, description="Piece state")

    model_config = {"arbitrary_types_allowed": True}


class FileInfo(BaseModel):
    """File information for torrents."""
    name: str = Field(..., description="File name")
    length: int = Field(..., ge=0, description="File length in bytes")
    path: Optional[List[str]] = Field(None, description="File path components")
    full_path: Optional[str] = Field(None, description="Full file path")


class TorrentInfo(BaseModel):
    """Torrent information."""
    name: str = Field(..., description="Torrent name")
    info_hash: bytes = Field(..., min_length=20, max_length=20, description="Info hash")
    announce: str = Field(..., description="Announce URL")
    announce_list: Optional[List[List[str]]] = Field(None, description="Announce list")
    comment: Optional[str] = Field(None, description="Torrent comment")
    created_by: Optional[str] = Field(None, description="Created by")
    creation_date: Optional[int] = Field(None, description="Creation date")
    encoding: Optional[str] = Field(None, description="String encoding")

    # File information
    files: List[FileInfo] = Field(default_factory=list, description="File list")
    total_length: int = Field(..., ge=0, description="Total length in bytes")

    # Piece information
    piece_length: int = Field(..., gt=0, description="Piece length in bytes")
    pieces: List[bytes] = Field(default_factory=list, description="Piece hashes")
    num_pieces: int = Field(..., ge=0, description="Number of pieces")

    model_config = {"arbitrary_types_allowed": True}


class NetworkConfig(BaseModel):
    """Network configuration."""
    max_global_peers: int = Field(default=200, ge=1, le=10000, description="Maximum global peers")
    max_peers_per_torrent: int = Field(default=50, ge=1, le=1000, description="Maximum peers per torrent")
    pipeline_depth: int = Field(default=16, ge=1, le=128, description="Request pipeline depth")
    block_size_kib: int = Field(default=16, ge=1, le=64, description="Block size in KiB")
    min_block_size_kib: int = Field(default=4, ge=1, le=64, description="Minimum block size in KiB")
    max_block_size_kib: int = Field(default=64, ge=1, le=1024, description="Maximum block size in KiB")
    listen_port: int = Field(default=6881, ge=1024, le=65535, description="Listen port")
    listen_interface: Optional[str] = Field(default="0.0.0.0", description="Listen interface")
    enable_ipv6: bool = Field(default=True, description="Enable IPv6")
    enable_tcp: bool = Field(default=True, description="Enable TCP transport")
    enable_utp: bool = Field(default=False, description="Enable uTP transport")
    enable_encryption: bool = Field(default=False, description="Enable protocol encryption")
    socket_rcvbuf_kib: int = Field(default=256, ge=1, le=65536, description="Socket receive buffer size in KiB")
    socket_sndbuf_kib: int = Field(default=256, ge=1, le=65536, description="Socket send buffer size in KiB")
    tcp_nodelay: bool = Field(default=True, description="Enable TCP_NODELAY")
    max_connections_per_peer: int = Field(default=1, ge=1, le=8, description="Max parallel connections per peer")
    announce_interval: int = Field(default=1800, ge=60, le=86400, description="Announce interval in seconds")

    # Connection settings
    connection_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Connection timeout in seconds")
    handshake_timeout: float = Field(default=10.0, ge=1.0, le=60.0, description="Handshake timeout in seconds")
    keep_alive_interval: float = Field(default=120.0, ge=30.0, le=600.0, description="Keep alive interval in seconds")
    peer_timeout: float = Field(default=60.0, ge=5.0, le=600.0, description="Peer inactivity timeout in seconds")
    dht_timeout: float = Field(default=2.0, ge=1.0, le=60.0, description="DHT request timeout in seconds")

    # Rate limiting
    global_down_kib: int = Field(default=0, ge=0, description="Global download limit in KiB/s (0 = unlimited)")
    global_up_kib: int = Field(default=0, ge=0, description="Global upload limit in KiB/s (0 = unlimited)")
    per_peer_down_kib: int = Field(default=0, ge=0, description="Per-peer download limit in KiB/s (0 = unlimited)")
    per_peer_up_kib: int = Field(default=0, ge=0, description="Per-peer upload limit in KiB/s (0 = unlimited)")

    # Upload slots
    max_upload_slots: int = Field(default=4, ge=1, le=20, description="Maximum upload slots")

    # Choking strategy
    optimistic_unchoke_interval: float = Field(default=30.0, ge=1.0, le=600.0, description="Optimistic unchoke interval in seconds")
    unchoke_interval: float = Field(default=10.0, ge=1.0, le=600.0, description="Unchoke interval in seconds")

    # Tracker settings
    tracker_timeout: float = Field(default=30.0, ge=5.0, le=120.0, description="Tracker request timeout in seconds")
    tracker_connect_timeout: float = Field(default=10.0, ge=1.0, le=60.0, description="Tracker connection timeout in seconds")
    tracker_connection_limit: int = Field(default=50, ge=1, le=200, description="Maximum tracker connections")
    tracker_connections_per_host: int = Field(default=10, ge=1, le=50, description="Maximum connections per tracker host")
    dns_cache_ttl: int = Field(default=300, ge=60, le=3600, description="DNS cache TTL in seconds")


class DiskConfig(BaseModel):
    """Disk I/O configuration."""
    preallocate: PreallocationStrategy = Field(default=PreallocationStrategy.FULL, description="Preallocation strategy")
    write_batch_kib: int = Field(default=64, ge=1, le=1024, description="Write batch size in KiB")
    write_buffer_kib: int = Field(default=1024, ge=0, le=65536, description="Write buffer size in KiB")
    use_mmap: bool = Field(default=True, description="Use memory mapping")
    sparse_files: bool = Field(default=False, description="Use sparse files if supported")
    hash_workers: int = Field(default=4, ge=1, le=32, description="Number of hash verification workers")
    hash_queue_size: int = Field(default=100, ge=10, le=500, description="Hash verification queue size")
    hash_chunk_size: int = Field(default=65536, ge=1024, le=1048576, description="Hash verification chunk size in bytes")
    hash_batch_size: int = Field(default=4, ge=1, le=64, description="Pieces to verify in parallel batch")
    disk_workers: int = Field(default=2, ge=1, le=16, description="Number of disk I/O workers")
    disk_queue_size: int = Field(default=200, ge=10, le=1000, description="Disk I/O queue size")
    cache_size_mb: int = Field(default=256, ge=16, le=4096, description="Cache size in MB")
    mmap_cache_mb: int = Field(default=128, ge=16, le=2048, description="Memory-mapped cache size in MB")
    mmap_cache_cleanup_interval: float = Field(default=30.0, ge=1.0, le=300.0, description="MMap cache cleanup interval in seconds")

    # Worker and queue settings
    disk_workers: int = Field(default=2, ge=1, le=16, description="Number of disk I/O workers")
    disk_queue_size: int = Field(default=200, ge=10, le=1000, description="Disk I/O queue size")
    write_batch_kib: int = Field(default=64, ge=1, le=1024, description="Write batch size in KiB")

    # Advanced settings
    direct_io: bool = Field(default=False, description="Use direct I/O")
    sync_writes: bool = Field(default=False, description="Synchronize writes")
    read_ahead_kib: int = Field(default=64, ge=0, le=1024, description="Read ahead size in KiB")
    enable_io_uring: bool = Field(default=False, description="Enable io_uring on Linux if available")
    download_path: Optional[str] = Field(default=None, description="Default download path")

    # Checkpoint settings
    checkpoint_enabled: bool = Field(default=True, description="Enable download checkpointing")
    checkpoint_format: CheckpointFormat = Field(default=CheckpointFormat.BOTH, description="Checkpoint file format")
    checkpoint_dir: Optional[str] = Field(None, description="Checkpoint directory (defaults to download_dir/.ccbt/checkpoints)")
    checkpoint_interval: float = Field(default=30.0, ge=1.0, le=3600.0, description="Checkpoint save interval in seconds")
    checkpoint_on_piece: bool = Field(default=True, description="Save checkpoint after each verified piece")
    auto_resume: bool = Field(default=True, description="Automatically resume from checkpoint on startup")
    checkpoint_compression: bool = Field(default=True, description="Compress binary checkpoint files")
    auto_delete_checkpoint_on_complete: bool = Field(default=True, description="Automatically delete checkpoint when download completes")
    checkpoint_retention_days: int = Field(default=30, ge=1, le=365, description="Days to retain checkpoints before cleanup")


class StrategyConfig(BaseModel):
    """Piece selection strategy configuration."""
    piece_selection: PieceSelectionStrategy = Field(default=PieceSelectionStrategy.RAREST_FIRST, description="Piece selection strategy")
    endgame_duplicates: int = Field(default=2, ge=1, le=10, description="Endgame duplicate requests")
    endgame_threshold: float = Field(default=0.95, ge=0.1, le=1.0, description="Endgame mode threshold")
    pipeline_capacity: int = Field(default=4, ge=1, le=32, description="Request pipeline capacity")
    streaming_mode: bool = Field(default=False, description="Enable streaming mode")

    # Advanced strategy settings
    rarest_first_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="Rarest first threshold")
    sequential_window: int = Field(default=10, ge=1, le=100, description="Sequential window size")


class DiscoveryConfig(BaseModel):
    """Peer discovery configuration."""
    enable_dht: bool = Field(default=True, description="Enable DHT")
    enable_pex: bool = Field(default=True, description="Enable Peer Exchange")
    enable_udp_trackers: bool = Field(default=True, description="Enable UDP trackers")
    enable_http_trackers: bool = Field(default=True, description="Enable HTTP trackers")

    # DHT settings
    dht_port: int = Field(default=6882, ge=1024, le=65535, description="DHT port")
    dht_bootstrap_nodes: List[str] = Field(default_factory=lambda: [
        "router.bittorrent.com:6881",
        "dht.transmissionbt.com:6881",
        "router.utorrent.com:6881",
        "dht.libtorrent.org:25401",
    ], description="DHT bootstrap nodes")

    # Tracker intervals
    tracker_announce_interval: float = Field(default=1800.0, ge=60.0, le=86400.0, description="Tracker announce interval in seconds")
    tracker_scrape_interval: float = Field(default=3600.0, ge=60.0, le=86400.0, description="Tracker scrape interval in seconds")

    # PEX
    pex_interval: float = Field(default=30.0, ge=5.0, le=3600.0, description="Peer Exchange announce interval in seconds")


class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    log_file: Optional[str] = Field(None, description="Log file path")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Metrics port")
    enable_peer_tracing: bool = Field(default=False, description="Enable peer tracing")

    # Advanced logging
    structured_logging: bool = Field(default=True, description="Use structured logging")
    log_correlation_id: bool = Field(default=True, description="Include correlation IDs")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format string")
    metrics_interval: float = Field(default=5.0, ge=0.5, le=3600.0, description="Metrics collection interval in seconds")
    trace_file: Optional[str] = Field(default=None, description="Path to write traces")
    alerts_rules_path: Optional[str] = Field(default=".ccbt/alerts.json", description="Path to alert rules JSON file")


class LimitsConfig(BaseModel):
    """Global and per-scope rate limits and scheduler settings."""
    # Global rate limits (KiB/s, 0 = unlimited)
    global_down_kib: int = Field(default=0, ge=0, description="Global download limit in KiB/s")
    global_up_kib: int = Field(default=0, ge=0, description="Global upload limit in KiB/s")

    # Per-torrent rate limits (KiB/s, 0 = unlimited)
    per_torrent_down_kib: int = Field(default=0, ge=0, description="Per-torrent download limit in KiB/s")
    per_torrent_up_kib: int = Field(default=0, ge=0, description="Per-torrent upload limit in KiB/s")

    # Per-peer rate limits (KiB/s, 0 = unlimited)
    per_peer_up_kib: int = Field(default=0, ge=0, description="Per-peer upload limit in KiB/s")

    # Scheduler
    scheduler_slice_ms: int = Field(default=100, ge=1, le=1000, description="Scheduler time slice in ms")


class SecurityConfig(BaseModel):
    """Security related configuration."""
    enable_encryption: bool = Field(default=False, description="Enable protocol encryption")
    validate_peers: bool = Field(default=True, description="Validate peers before exchanging data")
    rate_limit_enabled: bool = Field(default=True, description="Enable security rate limiter")
    max_connections_per_peer: int = Field(default=1, ge=1, le=8, description="Maximum parallel connections per peer")


class MLConfig(BaseModel):
    """Machine learning optimization settings."""
    peer_selection_enabled: bool = Field(default=False, description="Enable ML-based peer selection")
    piece_prediction_enabled: bool = Field(default=False, description="Enable ML piece prediction")
    # Future settings can be added here (model paths, thresholds, etc.)


class PieceCheckpoint(BaseModel):
    """Checkpoint data for a single piece."""
    index: int = Field(..., ge=0, description="Piece index")
    state: PieceState = Field(..., description="Piece state")
    hash_verified: bool = Field(default=False, description="Whether piece hash is verified")
    priority: int = Field(default=0, description="Piece priority")
    request_count: int = Field(default=0, description="Number of times piece was requested")


class DownloadStats(BaseModel):
    """Download statistics for checkpoint."""
    bytes_downloaded: int = Field(default=0, ge=0, description="Total bytes downloaded")
    download_time: float = Field(default=0.0, ge=0.0, description="Total download time in seconds")
    average_speed: float = Field(default=0.0, ge=0.0, description="Average download speed in bytes/sec")
    start_time: float = Field(default=0.0, description="Download start timestamp")
    last_update: float = Field(default=0.0, description="Last checkpoint update timestamp")


class FileCheckpoint(BaseModel):
    """File information for checkpoint."""
    path: str = Field(..., description="File path")
    size: int = Field(..., ge=0, description="File size in bytes")
    exists: bool = Field(default=False, description="Whether file exists on disk")


class TorrentCheckpoint(BaseModel):
    """Complete torrent download checkpoint."""
    version: str = Field(default="1.0", description="Checkpoint format version")
    info_hash: bytes = Field(..., min_length=20, max_length=20, description="Torrent info hash")
    torrent_name: str = Field(..., description="Torrent name")
    created_at: float = Field(..., description="Checkpoint creation timestamp")
    updated_at: float = Field(..., description="Last update timestamp")

    # Torrent metadata
    total_pieces: int = Field(..., ge=0, description="Total number of pieces")
    piece_length: int = Field(..., gt=0, description="Standard piece length")
    total_length: int = Field(..., ge=0, description="Total torrent size")

    # Download state
    verified_pieces: List[int] = Field(default_factory=list, description="List of verified piece indices")
    piece_states: Dict[int, PieceState] = Field(default_factory=dict, description="Piece states by index")
    download_stats: DownloadStats = Field(default_factory=DownloadStats, description="Download statistics")

    # File information
    output_dir: str = Field(..., description="Output directory")
    files: List[FileCheckpoint] = Field(default_factory=list, description="File information")

    # Optional metadata
    peer_info: Optional[Dict[str, Any]] = Field(None, description="Peer availability info")
    endgame_mode: bool = Field(default=False, description="Whether in endgame mode")

    # Torrent source metadata for resume functionality
    torrent_file_path: Optional[str] = Field(None, description="Path to original .torrent file")
    magnet_uri: Optional[str] = Field(None, description="Original magnet link")
    announce_urls: List[str] = Field(default_factory=list, description="Tracker announce URLs")
    display_name: Optional[str] = Field(None, description="Torrent display name")

    model_config = {"arbitrary_types_allowed": True}


class Config(BaseModel):
    """Main configuration model."""
    network: NetworkConfig = Field(default_factory=NetworkConfig, description="Network configuration")
    disk: DiskConfig = Field(default_factory=DiskConfig, description="Disk configuration")
    strategy: StrategyConfig = Field(default_factory=StrategyConfig, description="Strategy configuration")
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig, description="Discovery configuration")
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig, description="Observability configuration")
    limits: LimitsConfig = Field(default_factory=LimitsConfig, description="Rate limit configuration")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")
    ml: MLConfig = Field(default_factory=MLConfig, description="Machine learning configuration")

    @model_validator(mode="after")
    def validate_config(self):
        """Validate configuration consistency."""
        network = self.network
        discovery = self.discovery

        if network and discovery:
            # Ensure DHT port doesn't conflict with listen port
            if discovery.enable_dht and network.listen_port == discovery.dht_port:
                raise ValueError("DHT port cannot be the same as listen port")

        # Backwards-compatibility: if limits are set, reflect to network globals when non-zero
        if self.limits:
            if self.limits.global_down_kib and not self.network.global_down_kib:
                self.network.global_down_kib = self.limits.global_down_kib
            if self.limits.global_up_kib and not self.network.global_up_kib:
                self.network.global_up_kib = self.limits.global_up_kib

        return self

    model_config = {"use_enum_values": True}
