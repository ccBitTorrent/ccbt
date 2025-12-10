"""Configuration management for ccBitTorrent.

from __future__ import annotations

Provides centralized configuration with TOML support, validation, hot-reload,
and hierarchical loading from defaults → config file → environment → CLI → per-torrent.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys
from pathlib import Path
from typing import Any

import toml

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment, misc]

from ccbt.models import (
    Config,
    DiscoveryConfig,
    DiskConfig,
    NetworkConfig,
    ObservabilityConfig,
    OptimizationConfig,
    OptimizationProfile,
    StrategyConfig,
)
from ccbt.utils.exceptions import ConfigurationError
from ccbt.utils.logging_config import get_logger, setup_logging

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Global configuration instance
_config_manager: ConfigManager | None = None


class ConfigManager:
    """Manages configuration loading, validation, and hot-reload."""

    def __init__(self, config_file: str | Path | None = None):
        """Initialize configuration manager.

        Args:
            config_file: Path to TOML config file. If None, searches for ccbt.toml

        """
        # internal
        self._hot_reload_task: asyncio.Task | None = None
        self._encryption_key: bytes | None = None
        self.config_file = self._find_config_file(config_file)
        self.config = self._load_config()
        
        # Apply optimization profile if specified (after config is loaded)
        if self.config.optimization.profile != OptimizationProfile.CUSTOM:
            self.apply_profile()
        
        self._setup_logging()

    def _find_config_file(
        self,
        config_file: str | Path | None,
    ) -> Path | None:
        """Find configuration file in standard locations."""
        if config_file:
            return Path(config_file)

        # Search in current directory, then home directory
        search_paths = [
            Path.cwd() / "ccbt.toml",
            Path.home() / ".config" / "ccbt" / "ccbt.toml",
            Path.home() / ".ccbt.toml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None  # pragma: no cover

    def _load_config(self) -> Config:
        """Load configuration from file and environment."""
        # Start with defaults
        config_data = {}

        # Load from TOML file if exists
        if self.config_file and self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    toml_data = toml.load(f)
                config_data.update(toml_data)

                # Parse list values from comma-separated strings
                if (
                    "security" in config_data
                    and "encryption_allowed_ciphers" in config_data.get("security", {})
                ):
                    value = config_data["security"]["encryption_allowed_ciphers"]
                    if isinstance(value, str) and "," in value:
                        config_data["security"]["encryption_allowed_ciphers"] = [
                            item.strip() for item in value.split(",") if item.strip()
                        ]

                if "proxy" in config_data and "proxy_bypass_list" in config_data.get(
                    "proxy", {}
                ):
                    value = config_data["proxy"]["proxy_bypass_list"]
                    if isinstance(value, str) and "," in value:
                        config_data["proxy"]["proxy_bypass_list"] = [
                            item.strip() for item in value.split(",") if item.strip()
                        ]

                # Decrypt proxy password if encrypted
                if "proxy" in config_data and config_data["proxy"].get(
                    "proxy_password"
                ):
                    password = config_data["proxy"]["proxy_password"]
                    if self._is_encrypted(password):
                        try:
                            decrypted = self._decrypt_proxy_password(password)
                            config_data["proxy"]["proxy_password"] = decrypted
                        except Exception as e:
                            logging.warning("Failed to decrypt proxy password: %s", e)
                            # Continue with encrypted value (will be re-encrypted on save)
            except Exception as e:
                logging.warning(
                    "Failed to load config file %s: %s", self.config_file, e
                )

        # Apply environment overrides
        env_config = self._get_env_config()
        config_data = self._merge_config(config_data, env_config)

        # CRITICAL FIX: Apply Windows-specific connection limits to prevent socket buffer exhaustion
        # Windows has stricter limits on socket buffers (WinError 10055)
        if IS_WINDOWS and "network" in config_data:
            network_config = config_data.get("network", {})
            # Reduce connection limits on Windows to prevent socket buffer exhaustion
            if network_config.get("max_global_peers", 600) > 200:
                network_config["max_global_peers"] = 200
                logging.debug("Reduced max_global_peers to 200 for Windows compatibility")
            if network_config.get("connection_pool_max_connections", 400) > 150:
                network_config["connection_pool_max_connections"] = 150
                logging.debug("Reduced connection_pool_max_connections to 150 for Windows compatibility")
            if network_config.get("max_peers_per_torrent", 200) > 100:
                network_config["max_peers_per_torrent"] = 100
                logging.debug("Reduced max_peers_per_torrent to 100 for Windows compatibility")
            config_data["network"] = network_config

        try:
            # Create Pydantic model with validation
            config = Config(**config_data)
            
            # Apply optimization profile if specified (after config is created)
            # We'll apply it in __init__ after self.config is set
            return config
        except Exception as e:
            msg = f"Invalid configuration: {e}"
            raise ConfigurationError(msg) from e

    def _get_env_config(self) -> dict[str, Any]:
        """Get configuration from environment variables."""
        env_config: dict[str, Any] = {}

        # Mapping of environment variables to config paths
        env_mappings: dict[str, str] = {
            # Network
            "CCBT_MAX_PEERS": "network.max_global_peers",
            "CCBT_MAX_PEERS_PER_TORRENT": "network.max_peers_per_torrent",
            "CCBT_LISTEN_PORT": "network.listen_port",
            "CCBT_LISTEN_PORT_TCP": "network.listen_port_tcp",
            "CCBT_LISTEN_PORT_UDP": "network.listen_port_udp",
            "CCBT_TRACKER_UDP_PORT": "network.tracker_udp_port",
            "CCBT_XET_PORT": "network.xet_port",
            "CCBT_XET_MULTICAST_ADDRESS": "network.xet_multicast_address",
            "CCBT_XET_MULTICAST_PORT": "network.xet_multicast_port",
            "CCBT_PIPELINE_DEPTH": "network.pipeline_depth",
            "CCBT_BLOCK_SIZE_KIB": "network.block_size_kib",
            "CCBT_CONNECTION_TIMEOUT": "network.connection_timeout",
            "CCBT_HANDSHAKE_TIMEOUT": "network.handshake_timeout",
            "CCBT_METADATA_EXCHANGE_TIMEOUT": "network.metadata_exchange_timeout",
            "CCBT_METADATA_PIECE_TIMEOUT": "network.metadata_piece_timeout",
            "CCBT_CONNECTION_HEALTH_CHECK_INTERVAL": "network.connection_health_check_interval",
            "CCBT_CONNECTION_VALIDATION_ENABLED": "network.connection_validation_enabled",
            "CCBT_PEER_VALIDATION_ENABLED": "network.peer_validation_enabled",
            "CCBT_SEND_BITFIELD_AFTER_METADATA": "network.send_bitfield_after_metadata",
            "CCBT_SEND_INTERESTED_AFTER_METADATA": "network.send_interested_after_metadata",
            "CCBT_MAX_CONCURRENT_CONNECTION_ATTEMPTS": "network.max_concurrent_connection_attempts",
            "CCBT_ENABLE_FAIL_FAST_DHT": "network.enable_fail_fast_dht",
            "CCBT_FAIL_FAST_DHT_TIMEOUT": "network.fail_fast_dht_timeout",
            "CCBT_KEEP_ALIVE_INTERVAL": "network.keep_alive_interval",
            "CCBT_GLOBAL_DOWN_KIB": "network.global_down_kib",
            "CCBT_GLOBAL_UP_KIB": "network.global_up_kib",
            "CCBT_PER_PEER_DOWN_KIB": "network.per_peer_down_kib",
            "CCBT_PER_PEER_UP_KIB": "network.per_peer_up_kib",
            "CCBT_MAX_UPLOAD_SLOTS": "network.max_upload_slots",
            "CCBT_TRACKER_TIMEOUT": "network.tracker_timeout",
            "CCBT_DNS_CACHE_TTL": "network.dns_cache_ttl",
            # Connection pool
            "CCBT_CONNECTION_POOL_MAX_CONNECTIONS": "network.connection_pool_max_connections",
            "CCBT_CONNECTION_POOL_MAX_IDLE_TIME": "network.connection_pool_max_idle_time",
            "CCBT_CONNECTION_POOL_WARMUP_ENABLED": "network.connection_pool_warmup_enabled",
            "CCBT_CONNECTION_POOL_WARMUP_COUNT": "network.connection_pool_warmup_count",
            "CCBT_CONNECTION_POOL_HEALTH_CHECK_INTERVAL": "network.connection_pool_health_check_interval",
            "CCBT_CONNECTION_POOL_ADAPTIVE_LIMIT_ENABLED": "network.connection_pool_adaptive_limit_enabled",
            "CCBT_CONNECTION_POOL_ADAPTIVE_LIMIT_MIN": "network.connection_pool_adaptive_limit_min",
            "CCBT_CONNECTION_POOL_ADAPTIVE_LIMIT_MAX": "network.connection_pool_adaptive_limit_max",
            "CCBT_CONNECTION_POOL_CPU_THRESHOLD": "network.connection_pool_cpu_threshold",
            "CCBT_CONNECTION_POOL_MEMORY_THRESHOLD": "network.connection_pool_memory_threshold",
            "CCBT_CONNECTION_POOL_PERFORMANCE_RECYCLING_ENABLED": "network.connection_pool_performance_recycling_enabled",
            "CCBT_CONNECTION_POOL_PERFORMANCE_THRESHOLD": "network.connection_pool_performance_threshold",
            "CCBT_CONNECTION_POOL_QUALITY_THRESHOLD": "network.connection_pool_quality_threshold",
            "CCBT_CONNECTION_POOL_GRACE_PERIOD": "network.connection_pool_grace_period",
            "CCBT_CONNECTION_POOL_MIN_DOWNLOAD_BANDWIDTH": "network.connection_pool_min_download_bandwidth",
            "CCBT_CONNECTION_POOL_MIN_UPLOAD_BANDWIDTH": "network.connection_pool_min_upload_bandwidth",
            "CCBT_CONNECTION_POOL_HEALTH_DEGRADATION_THRESHOLD": "network.connection_pool_health_degradation_threshold",
            "CCBT_CONNECTION_POOL_HEALTH_RECOVERY_THRESHOLD": "network.connection_pool_health_recovery_threshold",
            # Tracker HTTP session
            "CCBT_TRACKER_KEEPALIVE_TIMEOUT": "network.tracker_keepalive_timeout",
            "CCBT_TRACKER_ENABLE_DNS_CACHE": "network.tracker_enable_dns_cache",
            "CCBT_TRACKER_DNS_CACHE_TTL": "network.tracker_dns_cache_ttl",
            # Timeout and retry
            "CCBT_TIMEOUT_ADAPTIVE": "network.timeout_adaptive",
            "CCBT_TIMEOUT_MIN_SECONDS": "network.timeout_min_seconds",
            "CCBT_TIMEOUT_MAX_SECONDS": "network.timeout_max_seconds",
            "CCBT_TIMEOUT_RTT_MULTIPLIER": "network.timeout_rtt_multiplier",
            "CCBT_RETRY_EXPONENTIAL_BACKOFF": "network.retry_exponential_backoff",
            "CCBT_RETRY_BASE_DELAY": "network.retry_base_delay",
            "CCBT_RETRY_MAX_DELAY": "network.retry_max_delay",
            "CCBT_CIRCUIT_BREAKER_ENABLED": "network.circuit_breaker_enabled",
            "CCBT_CIRCUIT_BREAKER_FAILURE_THRESHOLD": "network.circuit_breaker_failure_threshold",
            "CCBT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "network.circuit_breaker_recovery_timeout",
            # Socket buffers
            "CCBT_SOCKET_ADAPTIVE_BUFFERS": "network.socket_adaptive_buffers",
            "CCBT_SOCKET_MIN_BUFFER_KIB": "network.socket_min_buffer_kib",
            "CCBT_SOCKET_MAX_BUFFER_KIB": "network.socket_max_buffer_kib",
            "CCBT_SOCKET_ENABLE_WINDOW_SCALING": "network.socket_enable_window_scaling",
            # Pipeline optimization
            "CCBT_PIPELINE_ADAPTIVE_DEPTH": "network.pipeline_adaptive_depth",
            "CCBT_PIPELINE_MIN_DEPTH": "network.pipeline_min_depth",
            "CCBT_PIPELINE_MAX_DEPTH": "network.pipeline_max_depth",
            "CCBT_PIPELINE_ENABLE_PRIORITIZATION": "network.pipeline_enable_prioritization",
            "CCBT_PIPELINE_ENABLE_COALESCING": "network.pipeline_enable_coalescing",
            "CCBT_PIPELINE_COALESCE_THRESHOLD_KIB": "network.pipeline_coalesce_threshold_kib",
            # uTP Transport
            "CCBT_UTP_PREFER_OVER_TCP": "network.utp.prefer_over_tcp",
            "CCBT_UTP_CONNECTION_TIMEOUT": "network.utp.connection_timeout",
            "CCBT_UTP_MAX_WINDOW_SIZE": "network.utp.max_window_size",
            "CCBT_UTP_MTU": "network.utp.mtu",
            "CCBT_UTP_INITIAL_RATE": "network.utp.initial_rate",
            "CCBT_UTP_MIN_RATE": "network.utp.min_rate",
            "CCBT_UTP_MAX_RATE": "network.utp.max_rate",
            "CCBT_UTP_ACK_INTERVAL": "network.utp.ack_interval",
            "CCBT_UTP_RETRANSMIT_TIMEOUT_FACTOR": "network.utp.retransmit_timeout_factor",
            "CCBT_UTP_MAX_RETRANSMITS": "network.utp.max_retransmits",
            # Strategy
            "CCBT_PIECE_SELECTION": "strategy.piece_selection",
            "CCBT_ENDGAME_DUPLICATES": "strategy.endgame_duplicates",
            "CCBT_ENDGAME_THRESHOLD": "strategy.endgame_threshold",
            "CCBT_STREAMING_MODE": "strategy.streaming_mode",
            "CCBT_BANDWIDTH_WEIGHTED_RAREST_WEIGHT": "strategy.bandwidth_weighted_rarest_weight",
            "CCBT_PROGRESSIVE_RAREST_TRANSITION_THRESHOLD": "strategy.progressive_rarest_transition_threshold",
            "CCBT_ADAPTIVE_HYBRID_PHASE_DETECTION_WINDOW": "strategy.adaptive_hybrid_phase_detection_window",
            # Disk
            "CCBT_PREALLOCATE": "disk.preallocate",
            "CCBT_USE_MMAP": "disk.use_mmap",
            "CCBT_MMAP_CACHE_MB": "disk.mmap_cache_mb",
            "CCBT_WRITE_BATCH_KIB": "disk.write_batch_kib",
            "CCBT_HASH_WORKERS": "disk.hash_workers",
            "CCBT_DISK_WORKERS": "disk.disk_workers",
            "CCBT_DIRECT_IO": "disk.direct_io",
            "CCBT_SYNC_WRITES": "disk.sync_writes",
            "CCBT_READ_AHEAD_KIB": "disk.read_ahead_kib",
            "CCBT_CHECKPOINT_ENABLED": "disk.checkpoint_enabled",
            "CCBT_CHECKPOINT_DIR": "disk.checkpoint_dir",
            "CCBT_CHECKPOINT_COMPRESSION": "disk.checkpoint_compression",
            "CCBT_AUTO_RESUME": "disk.auto_resume",
            "CCBT_FAST_RESUME_ENABLED": "disk.fast_resume_enabled",
            "CCBT_RESUME_SAVE_INTERVAL": "disk.resume_save_interval",
            "CCBT_RESUME_VERIFY_ON_LOAD": "disk.resume_verify_on_load",
            "CCBT_RESUME_VERIFY_PIECES": "disk.resume_verify_pieces",
            "CCBT_RESUME_DATA_FORMAT_VERSION": "disk.resume_data_format_version",
            # BEP 47: File Attributes
            "CCBT_ATTRIBUTES_PRESERVE_ATTRIBUTES": "disk.attributes.preserve_attributes",
            "CCBT_ATTRIBUTES_SKIP_PADDING_FILES": "disk.attributes.skip_padding_files",
            "CCBT_ATTRIBUTES_VERIFY_FILE_SHA1": "disk.attributes.verify_file_sha1",
            "CCBT_ATTRIBUTES_APPLY_SYMLINKS": "disk.attributes.apply_symlinks",
            "CCBT_ATTRIBUTES_APPLY_EXECUTABLE_BIT": "disk.attributes.apply_executable_bit",
            "CCBT_ATTRIBUTES_APPLY_HIDDEN_ATTR": "disk.attributes.apply_hidden_attr",
            # Xet Protocol
            "CCBT_XET_ENABLED": "disk.xet_enabled",
            "CCBT_XET_CHUNK_MIN_SIZE": "disk.xet_chunk_min_size",
            "CCBT_XET_CHUNK_MAX_SIZE": "disk.xet_chunk_max_size",
            "CCBT_XET_CHUNK_TARGET_SIZE": "disk.xet_chunk_target_size",
            "CCBT_XET_DEDUPLICATION_ENABLED": "disk.xet_deduplication_enabled",
            "CCBT_XET_CACHE_DB_PATH": "disk.xet_cache_db_path",
            "CCBT_XET_CHUNK_STORE_PATH": "disk.xet_chunk_store_path",
            "CCBT_XET_USE_P2P_CAS": "disk.xet_use_p2p_cas",
            "CCBT_XET_COMPRESSION_ENABLED": "disk.xet_compression_enabled",
            # Discovery
            "CCBT_ENABLE_DHT": "discovery.enable_dht",
            "CCBT_DHT_PORT": "discovery.dht_port",
            "CCBT_ENABLE_PEX": "discovery.enable_pex",
            "CCBT_ENABLE_UDP_TRACKERS": "discovery.enable_udp_trackers",
            "CCBT_ENABLE_HTTP_TRACKERS": "discovery.enable_http_trackers",
            "CCBT_TRACKER_ANNOUNCE_INTERVAL": "discovery.tracker_announce_interval",
            "CCBT_TRACKER_SCRAPE_INTERVAL": "discovery.tracker_scrape_interval",
            "CCBT_TRACKER_AUTO_SCRAPE": "discovery.tracker_auto_scrape",
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_ENABLED": "discovery.tracker_adaptive_interval_enabled",
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_MIN": "discovery.tracker_adaptive_interval_min",
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_MAX": "discovery.tracker_adaptive_interval_max",
            "CCBT_TRACKER_BASE_ANNOUNCE_INTERVAL": "discovery.tracker_base_announce_interval",
            "CCBT_TRACKER_PEER_COUNT_WEIGHT": "discovery.tracker_peer_count_weight",
            "CCBT_TRACKER_PERFORMANCE_WEIGHT": "discovery.tracker_performance_weight",
            "CCBT_DEFAULT_TRACKERS": "discovery.default_trackers",
            "CCBT_PEX_INTERVAL": "discovery.pex_interval",
            "CCBT_STRICT_PRIVATE_MODE": "discovery.strict_private_mode",
            # BEP 32: IPv6 Extension for DHT
            "CCBT_DHT_ENABLE_IPV6": "discovery.dht_enable_ipv6",
            "CCBT_DHT_PREFER_IPV6": "discovery.dht_prefer_ipv6",
            "CCBT_DHT_IPV6_BOOTSTRAP_NODES": "discovery.dht_ipv6_bootstrap_nodes",
            # BEP 43: Read-only DHT Nodes
            "CCBT_DHT_READONLY_MODE": "discovery.dht_readonly_mode",
            # BEP 45: Multiple-Address Operation for DHT
            "CCBT_DHT_ENABLE_MULTIADDRESS": "discovery.dht_enable_multiaddress",
            "CCBT_DHT_MAX_ADDRESSES_PER_NODE": "discovery.dht_max_addresses_per_node",
            # BEP 44: Storing Arbitrary Data in the DHT
            "CCBT_DHT_ENABLE_STORAGE": "discovery.dht_enable_storage",
            "CCBT_DHT_STORAGE_TTL": "discovery.dht_storage_ttl",
            "CCBT_DHT_MAX_STORAGE_SIZE": "discovery.dht_max_storage_size",
            # BEP 51: DHT Infohash Indexing
            "CCBT_DHT_ENABLE_INDEXING": "discovery.dht_enable_indexing",
            "CCBT_DHT_INDEX_SAMPLES_PER_KEY": "discovery.dht_index_samples_per_key",
            # DHT adaptive intervals and quality tracking
            "CCBT_DHT_ADAPTIVE_INTERVAL_ENABLED": "discovery.dht_adaptive_interval_enabled",
            "CCBT_AGGRESSIVE_INITIAL_DISCOVERY": "discovery.aggressive_initial_discovery",
            "CCBT_AGGRESSIVE_INITIAL_TRACKER_INTERVAL": "discovery.aggressive_initial_tracker_interval",
            "CCBT_AGGRESSIVE_INITIAL_DHT_INTERVAL": "discovery.aggressive_initial_dht_interval",
            # IMPROVEMENT: Aggressive discovery for popular torrents
            "CCBT_AGGRESSIVE_DISCOVERY_POPULAR_THRESHOLD": "discovery.aggressive_discovery_popular_threshold",
            "CCBT_AGGRESSIVE_DISCOVERY_ACTIVE_THRESHOLD_KIB": "discovery.aggressive_discovery_active_threshold_kib",
            "CCBT_AGGRESSIVE_DISCOVERY_INTERVAL_POPULAR": "discovery.aggressive_discovery_interval_popular",
            "CCBT_AGGRESSIVE_DISCOVERY_INTERVAL_ACTIVE": "discovery.aggressive_discovery_interval_active",
            "CCBT_AGGRESSIVE_DISCOVERY_MAX_PEERS_PER_QUERY": "discovery.aggressive_discovery_max_peers_per_query",
            "CCBT_DHT_BASE_REFRESH_INTERVAL": "discovery.dht_base_refresh_interval",
            "CCBT_DHT_ADAPTIVE_INTERVAL_MIN": "discovery.dht_adaptive_interval_min",
            "CCBT_DHT_ADAPTIVE_INTERVAL_MAX": "discovery.dht_adaptive_interval_max",
            "CCBT_DHT_QUALITY_TRACKING_ENABLED": "discovery.dht_quality_tracking_enabled",
            "CCBT_DHT_QUALITY_RESPONSE_TIME_WINDOW": "discovery.dht_quality_response_time_window",
            # DHT query parameters (Kademlia algorithm)
            "CCBT_DHT_NORMAL_ALPHA": "discovery.dht_normal_alpha",
            "CCBT_DHT_NORMAL_K": "discovery.dht_normal_k",
            "CCBT_DHT_NORMAL_MAX_DEPTH": "discovery.dht_normal_max_depth",
            "CCBT_DHT_AGGRESSIVE_ALPHA": "discovery.dht_aggressive_alpha",
            "CCBT_DHT_AGGRESSIVE_K": "discovery.dht_aggressive_k",
            "CCBT_DHT_AGGRESSIVE_MAX_DEPTH": "discovery.dht_aggressive_max_depth",
            # XET chunk discovery
            "CCBT_XET_CHUNK_QUERY_BATCH_SIZE": "discovery.xet_chunk_query_batch_size",
            "CCBT_XET_CHUNK_QUERY_MAX_CONCURRENT": "discovery.xet_chunk_query_max_concurrent",
            "CCBT_DISCOVERY_CACHE_TTL": "discovery.discovery_cache_ttl",
            # Security
            "CCBT_ENABLE_ENCRYPTION": "security.enable_encryption",
            "CCBT_ENCRYPTION_MODE": "security.encryption_mode",
            "CCBT_ENCRYPTION_DH_KEY_SIZE": "security.encryption_dh_key_size",
            "CCBT_ENCRYPTION_PREFER_RC4": "security.encryption_prefer_rc4",
            "CCBT_ENCRYPTION_ALLOWED_CIPHERS": "security.encryption_allowed_ciphers",
            "CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK": "security.encryption_allow_plain_fallback",
            "CCBT_VALIDATE_PEERS": "security.validate_peers",
            "CCBT_RATE_LIMIT_ENABLED": "security.rate_limit_enabled",
            "CCBT_MAX_CONNECTIONS_PER_PEER": "security.max_connections_per_peer",
            "CCBT_PEER_QUALITY_THRESHOLD": "security.peer_quality_threshold",
            # IP Filter
            "CCBT_ENABLE_IP_FILTER": "security.ip_filter.enable_ip_filter",
            "CCBT_FILTER_MODE": "security.ip_filter.filter_mode",
            "CCBT_FILTER_FILES": "security.ip_filter.filter_files",
            "CCBT_FILTER_URLS": "security.ip_filter.filter_urls",
            "CCBT_FILTER_UPDATE_INTERVAL": "security.ip_filter.filter_update_interval",
            "CCBT_FILTER_CACHE_DIR": "security.ip_filter.filter_cache_dir",
            "CCBT_FILTER_LOG_BLOCKED": "security.ip_filter.filter_log_blocked",
            # Blacklist
            "CCBT_BLACKLIST_ENABLE_PERSISTENCE": "security.blacklist.enable_persistence",
            "CCBT_BLACKLIST_FILE": "security.blacklist.blacklist_file",
            "CCBT_BLACKLIST_AUTO_UPDATE_ENABLED": "security.blacklist.auto_update_enabled",
            "CCBT_BLACKLIST_AUTO_UPDATE_INTERVAL": "security.blacklist.auto_update_interval",
            "CCBT_BLACKLIST_AUTO_UPDATE_SOURCES": "security.blacklist.auto_update_sources",
            "CCBT_BLACKLIST_DEFAULT_EXPIRATION_HOURS": "security.blacklist.default_expiration_hours",
            # Local Blacklist Source
            "CCBT_BLACKLIST_LOCAL_SOURCE_ENABLED": "security.blacklist.local_source.enabled",
            "CCBT_BLACKLIST_LOCAL_SOURCE_EVALUATION_INTERVAL": "security.blacklist.local_source.evaluation_interval",
            "CCBT_BLACKLIST_LOCAL_SOURCE_METRIC_WINDOW": "security.blacklist.local_source.metric_window",
            "CCBT_BLACKLIST_LOCAL_SOURCE_EXPIRATION_HOURS": "security.blacklist.local_source.expiration_hours",
            "CCBT_BLACKLIST_LOCAL_SOURCE_MIN_OBSERVATIONS": "security.blacklist.local_source.min_observations",
            # Observability
            "CCBT_LOG_LEVEL": "observability.log_level",
            "CCBT_LOG_FILE": "observability.log_file",
            "CCBT_ENABLE_METRICS": "observability.enable_metrics",
            "CCBT_METRICS_PORT": "observability.metrics_port",
            "CCBT_ENABLE_PEER_TRACING": "observability.enable_peer_tracing",
            # Event bus configuration
            "CCBT_EVENT_BUS_MAX_QUEUE_SIZE": "observability.event_bus_max_queue_size",
            "CCBT_EVENT_BUS_BATCH_SIZE": "observability.event_bus_batch_size",
            "CCBT_EVENT_BUS_BATCH_TIMEOUT": "observability.event_bus_batch_timeout",
            "CCBT_EVENT_BUS_EMIT_TIMEOUT": "observability.event_bus_emit_timeout",
            "CCBT_EVENT_BUS_QUEUE_FULL_THRESHOLD": "observability.event_bus_queue_full_threshold",
            "CCBT_EVENT_BUS_THROTTLE_DHT_NODE_FOUND": "observability.event_bus_throttle_dht_node_found",
            "CCBT_EVENT_BUS_THROTTLE_DHT_NODE_ADDED": "observability.event_bus_throttle_dht_node_added",
            "CCBT_EVENT_BUS_THROTTLE_MONITORING_HEARTBEAT": "observability.event_bus_throttle_monitoring_heartbeat",
            "CCBT_EVENT_BUS_THROTTLE_GLOBAL_METRICS_UPDATE": "observability.event_bus_throttle_global_metrics_update",
            # Daemon
            "CCBT_DAEMON_IPC_PORT": "daemon.ipc_port",
            "CCBT_DAEMON_IPC_HOST": "daemon.ipc_host",
            # NAT
            "CCBT_NAT_ENABLE_NAT_PMP": "nat.enable_nat_pmp",
            "CCBT_NAT_ENABLE_UPNP": "nat.enable_upnp",
            "CCBT_NAT_DISCOVERY_INTERVAL": "nat.nat_discovery_interval",
            "CCBT_NAT_PORT_MAPPING_LEASE_TIME": "nat.port_mapping_lease_time",
            "CCBT_NAT_AUTO_MAP_PORTS": "nat.auto_map_ports",
            "CCBT_NAT_MAP_TCP_PORT": "nat.map_tcp_port",
            "CCBT_NAT_MAP_UDP_PORT": "nat.map_udp_port",
            "CCBT_NAT_MAP_DHT_PORT": "nat.map_dht_port",
            "CCBT_NAT_MAP_XET_PORT": "nat.map_xet_port",
            "CCBT_NAT_MAP_XET_MULTICAST_PORT": "nat.map_xet_multicast_port",
            # WebTorrent
            "CCBT_WEBTORRENT_PORT": "webtorrent.webtorrent_port",
            # Dashboard
            "CCBT_DASHBOARD_ENABLE": "dashboard.enable_dashboard",
            "CCBT_DASHBOARD_HOST": "dashboard.host",
            "CCBT_DASHBOARD_PORT": "dashboard.port",
            "CCBT_DASHBOARD_REFRESH_INTERVAL": "dashboard.refresh_interval",
            "CCBT_DASHBOARD_DEFAULT_VIEW": "dashboard.default_view",
            "CCBT_DASHBOARD_ENABLE_GRAFANA_EXPORT": "dashboard.enable_grafana_export",
            # Terminal dashboard settings
            "CCBT_DASHBOARD_TERMINAL_REFRESH_INTERVAL": "dashboard.terminal_refresh_interval",
            "CCBT_DASHBOARD_TERMINAL_DAEMON_STARTUP_TIMEOUT": "dashboard.terminal_daemon_startup_timeout",
            "CCBT_DASHBOARD_TERMINAL_DAEMON_INITIAL_WAIT": "dashboard.terminal_daemon_initial_wait",
            "CCBT_DASHBOARD_TERMINAL_DAEMON_RETRY_DELAY": "dashboard.terminal_daemon_retry_delay",
            "CCBT_DASHBOARD_TERMINAL_DAEMON_CHECK_INTERVAL": "dashboard.terminal_daemon_check_interval",
            "CCBT_DASHBOARD_TERMINAL_CONNECTION_TIMEOUT": "dashboard.terminal_connection_timeout",
            "CCBT_DASHBOARD_TERMINAL_CONNECTION_CHECK_INTERVAL": "dashboard.terminal_connection_check_interval",
            # Queue
            "CCBT_MAX_ACTIVE_TORRENTS": "queue.max_active_torrents",
            "CCBT_MAX_ACTIVE_DOWNLOADING": "queue.max_active_downloading",
            "CCBT_MAX_ACTIVE_SEEDING": "queue.max_active_seeding",
            "CCBT_DEFAULT_PRIORITY": "queue.default_priority",
            "CCBT_BANDWIDTH_ALLOCATION_MODE": "queue.bandwidth_allocation_mode",
            "CCBT_AUTO_MANAGE_QUEUE": "queue.auto_manage_queue",
            # Proxy
            "CCBT_PROXY_ENABLE_PROXY": "proxy.enable_proxy",
            "CCBT_PROXY_TYPE": "proxy.proxy_type",
            "CCBT_PROXY_HOST": "proxy.proxy_host",
            "CCBT_PROXY_PORT": "proxy.proxy_port",
            "CCBT_PROXY_USERNAME": "proxy.proxy_username",
            "CCBT_PROXY_PASSWORD": "proxy.proxy_password",
            "CCBT_PROXY_FOR_TRACKERS": "proxy.proxy_for_trackers",
            "CCBT_PROXY_FOR_PEERS": "proxy.proxy_for_peers",
            "CCBT_PROXY_FOR_WEBSEEDS": "proxy.proxy_for_webseeds",
            "CCBT_PROXY_BYPASS_LIST": "proxy.proxy_bypass_list",
            # SSL/TLS
            "CCBT_ENABLE_SSL_TRACKERS": "security.ssl.enable_ssl_trackers",
            "CCBT_ENABLE_SSL_PEERS": "security.ssl.enable_ssl_peers",
            "CCBT_SSL_VERIFY_CERTIFICATES": "security.ssl.ssl_verify_certificates",
            "CCBT_SSL_CA_CERTIFICATES": "security.ssl.ssl_ca_certificates",
            "CCBT_SSL_CLIENT_CERTIFICATE": "security.ssl.ssl_client_certificate",
            "CCBT_SSL_CLIENT_KEY": "security.ssl.ssl_client_key",
            "CCBT_SSL_PROTOCOL_VERSION": "security.ssl.ssl_protocol_version",
            "CCBT_SSL_ALLOW_INSECURE_PEERS": "security.ssl.ssl_allow_insecure_peers",
            # BitTorrent Protocol v2 (BEP 52)
            "CCBT_PROTOCOL_V2_ENABLE": "network.protocol_v2.enable_protocol_v2",
            "CCBT_PROTOCOL_V2_PREFER": "network.protocol_v2.prefer_protocol_v2",
            "CCBT_PROTOCOL_V2_SUPPORT_HYBRID": "network.protocol_v2.support_hybrid",
            "CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT": "network.protocol_v2.v2_handshake_timeout",
            # UI/Internationalization
            "CCBT_LOCALE": "ui.locale",
            "CCBT_UI_LOCALE": "ui.locale",  # UI-specific override
            # XET Folder Synchronization
            "CCBT_XET_SYNC_ENABLE_XET": "xet_sync.enable_xet",
            "CCBT_XET_SYNC_CHECK_INTERVAL": "xet_sync.check_interval",
            "CCBT_XET_SYNC_DEFAULT_SYNC_MODE": "xet_sync.default_sync_mode",
            "CCBT_XET_SYNC_ENABLE_GIT_VERSIONING": "xet_sync.enable_git_versioning",
            "CCBT_XET_SYNC_ENABLE_LPD": "xet_sync.enable_lpd",
            "CCBT_XET_SYNC_ENABLE_GOSSIP": "xet_sync.enable_gossip",
            "CCBT_XET_SYNC_GOSSIP_FANOUT": "xet_sync.gossip_fanout",
            "CCBT_XET_SYNC_GOSSIP_INTERVAL": "xet_sync.gossip_interval",
            "CCBT_XET_SYNC_FLOODING_TTL": "xet_sync.flooding_ttl",
            "CCBT_XET_SYNC_FLOODING_PRIORITY_THRESHOLD": "xet_sync.flooding_priority_threshold",
            "CCBT_XET_SYNC_CONSENSUS_ALGORITHM": "xet_sync.consensus_algorithm",
            "CCBT_XET_SYNC_RAFT_ELECTION_TIMEOUT": "xet_sync.raft_election_timeout",
            "CCBT_XET_SYNC_RAFT_HEARTBEAT_INTERVAL": "xet_sync.raft_heartbeat_interval",
            "CCBT_XET_SYNC_ENABLE_BYZANTINE_FAULT_TOLERANCE": "xet_sync.enable_byzantine_fault_tolerance",
            "CCBT_XET_SYNC_BYZANTINE_FAULT_THRESHOLD": "xet_sync.byzantine_fault_threshold",
            "CCBT_XET_SYNC_WEIGHTED_VOTING": "xet_sync.weighted_voting",
            "CCBT_XET_SYNC_AUTO_ELECT_SOURCE": "xet_sync.auto_elect_source",
            "CCBT_XET_SYNC_SOURCE_ELECTION_INTERVAL": "xet_sync.source_election_interval",
            "CCBT_XET_SYNC_CONFLICT_RESOLUTION_STRATEGY": "xet_sync.conflict_resolution_strategy",
            "CCBT_XET_SYNC_GIT_AUTO_COMMIT": "xet_sync.git_auto_commit",
            "CCBT_XET_SYNC_CONSENSUS_THRESHOLD": "xet_sync.consensus_threshold",
            "CCBT_XET_SYNC_MAX_UPDATE_QUEUE_SIZE": "xet_sync.max_update_queue_size",
            "CCBT_XET_SYNC_ALLOWLIST_ENCRYPTION_KEY": "xet_sync.allowlist_encryption_key",
            # Optimization profile
            "CCBT_OPTIMIZATION_PROFILE": "optimization.profile",
            "CCBT_OPTIMIZATION_SPEED_AGGRESSIVE_PEER_RECYCLING": "optimization.speed_aggressive_peer_recycling",
            "CCBT_OPTIMIZATION_EFFICIENCY_CONNECTION_LIMIT_MULTIPLIER": "optimization.efficiency_connection_limit_multiplier",
            "CCBT_OPTIMIZATION_LOW_RESOURCE_MAX_CONNECTIONS": "optimization.low_resource_max_connections",
            "CCBT_OPTIMIZATION_ENABLE_ADAPTIVE_INTERVALS": "optimization.enable_adaptive_intervals",
            "CCBT_OPTIMIZATION_ENABLE_PERFORMANCE_BASED_RECYCLING": "optimization.enable_performance_based_recycling",
            "CCBT_OPTIMIZATION_ENABLE_BANDWIDTH_AWARE_SCHEDULING": "optimization.enable_bandwidth_aware_scheduling",
        }

        def _parse_env_value(
            raw: str, path: str
        ) -> bool | int | float | str | list[str]:
            # Handle list values (comma-separated strings)
            if path == "security.encryption_allowed_ciphers":
                return [item.strip() for item in raw.split(",") if item.strip()]
            if path in {
                "security.ip_filter.filter_files",
                "security.ip_filter.filter_urls",
                "security.blacklist.auto_update_sources",
                "discovery.dht_bootstrap_nodes",
                "discovery.dht_ipv6_bootstrap_nodes",
                "discovery.default_trackers",
                "proxy.proxy_bypass_list",
            }:
                return [item.strip() for item in raw.split(",") if item.strip()]

            low = raw.lower()
            if low in {"true", "1", "yes", "on"}:
                return True
            if low in {"false", "0", "no", "off"}:
                return False
            try:
                if "." in raw:
                    return float(raw)
                return int(raw)
            except ValueError:
                return raw

        def _set_nested(d: dict[str, Any], path: str, value: Any) -> None:
            parts = path.split(".")
            cur = d
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value

        for env_name, cfg_path in env_mappings.items():
            raw = os.getenv(env_name)
            if raw is None:
                continue
            _set_nested(env_config, cfg_path, _parse_env_value(raw, cfg_path))

        return env_config

    def _merge_config(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge configuration dictionaries recursively."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def export(self, fmt: str = "toml", encrypt_passwords: bool = True) -> str:
        """Export current configuration as a string in the given format.

        Args:
            fmt: one of "toml", "json", or "yaml"
            encrypt_passwords: If True, encrypt proxy passwords before export

        """
        data = self.config.model_dump(mode="json")

        # Encrypt proxy password before export if enabled
        if (
            encrypt_passwords
            and "proxy" in data
            and data["proxy"].get("proxy_password")
        ):
            password = data["proxy"]["proxy_password"]
            if password and not self._is_encrypted(password):
                try:
                    encrypted = self._encrypt_proxy_password(password)
                    data["proxy"]["proxy_password"] = encrypted
                except Exception as e:
                    logging.warning("Failed to encrypt proxy password: %s", e)
                    # Continue with plaintext (not recommended)

        fmt = (fmt or "toml").lower()
        if fmt == "toml":  # pragma: no cover
            try:  # pragma: no cover
                return toml.dumps(data)  # pragma: no cover
            except Exception as e:  # pragma: no cover
                msg = f"Failed to export TOML: {e}"  # pragma: no cover
                raise ConfigurationError(msg) from e  # pragma: no cover
        if fmt == "json":  # pragma: no cover
            import json  # pragma: no cover

            return json.dumps(data, indent=2)  # pragma: no cover
        if fmt == "yaml":  # pragma: no cover
            try:  # pragma: no cover
                import yaml  # pragma: no cover
            except Exception as e:  # pragma: no cover
                msg = "PyYAML not installed; cannot export YAML"  # pragma: no cover
                raise ConfigurationError(msg) from e  # pragma: no cover
            return yaml.safe_dump(data, sort_keys=False)  # pragma: no cover
        msg = f"Unsupported export format: {fmt}"  # pragma: no cover
        raise ConfigurationError(msg)  # pragma: no cover

    def _get_encryption_key(self) -> bytes | None:
        """Get or create encryption key for proxy passwords.

        Returns:
            Encryption key bytes, or None if cryptography not available

        """
        if Fernet is None:
            return None

        if self._encryption_key is not None:
            return self._encryption_key

        # Try to get key from config directory
        config_dir = Path.home() / ".config" / "ccbt"
        key_file = config_dir / ".proxy_key"

        if key_file.exists():
            try:
                self._encryption_key = key_file.read_bytes()
                return self._encryption_key
            except Exception as e:  # pragma: no cover - Defensive: IOError handling during key file read, tested via test_encryption_key_read_error
                logging.warning("Failed to read encryption key: %s", e)

        # Generate new key
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            self._encryption_key = Fernet.generate_key()
            key_file.write_bytes(self._encryption_key)
            key_file.chmod(0o600)  # Read/write for owner only
            logging.info("Generated new proxy credential encryption key")
        except Exception as e:  # pragma: no cover - Defensive: Exception handler for key file write failures, tested via mock write errors
            logging.warning("Failed to write encryption key: %s", e)
            # Use a temporary key (not persistent across restarts)
            self._encryption_key = Fernet.generate_key()

        return self._encryption_key

    def _is_encrypted(self, value: str) -> bool:
        """Check if a string appears to be encrypted.

        Args:
            value: String to check

        Returns:
            True if value appears to be encrypted

        """
        # Encrypted values are URL-safe base64-encoded Fernet tokens
        # Fernet tokens when base64-encoded start with 'gAAAA' (first 5 chars)
        if not value:
            return False
        try:
            # Fernet tokens are URL-safe base64 and start with 'gAAAA'
            # Check the prefix first (fast path)
            if value.startswith("gAAAA"):
                return True
            # Also check if it's a valid base64-encoded string that's reasonably long
            # (encrypted data should be at least 50+ characters)
            if len(value) >= 50:
                # Try to decode as base64 to verify it's valid
                try:
                    decoded = base64.urlsafe_b64decode(value.encode("ascii"))
                    # Valid base64 and reasonably long suggests encryption
                    return len(decoded) > 30
                except Exception:
                    # Not valid base64, probably not encrypted
                    return False
            return False
        except Exception:
            return False

    def _encrypt_proxy_password(self, password: str) -> str:
        """Encrypt proxy password for storage.

        Args:
            password: Plaintext password

        Returns:
            Encrypted password (base64-encoded)

        Raises:
            ConfigurationError: If encryption fails or cryptography not available

        """
        if not password:
            return password

        key = self._get_encryption_key()
        if key is None:
            logging.warning(
                "cryptography not available - proxy password will be stored in plaintext"
            )
            return password

        try:
            cipher = Fernet(key)
            encrypted = cipher.encrypt(password.encode("utf-8"))
            # Fernet.encrypt() returns bytes that are URL-safe base64-encoded
            # Decode to string directly (don't double-encode)
            return encrypted.decode("ascii")
        except Exception as e:
            msg = f"Failed to encrypt proxy password: {e}"
            raise ConfigurationError(msg) from e

    def _decrypt_proxy_password(self, encrypted: str) -> str:
        """Decrypt proxy password from storage.

        Args:
            encrypted: Encrypted password (base64-encoded)

        Returns:
            Plaintext password

        Raises:
            ConfigurationError: If decryption fails or cryptography not available

        """
        if not encrypted:
            return encrypted

        if not self._is_encrypted(encrypted):
            # Not encrypted, return as-is
            return encrypted

        key = self._get_encryption_key()
        if key is None:
            msg = "cryptography not available - cannot decrypt proxy password"
            raise ConfigurationError(msg)

        try:
            cipher = Fernet(key)
            # Fernet expects URL-safe base64-encoded bytes
            # The encrypted string is already URL-safe base64, so encode it to bytes
            encrypted_bytes = encrypted.encode("ascii")
            decrypted = cipher.decrypt(encrypted_bytes)
            return decrypted.decode("utf-8")
        except Exception as e:
            msg = f"Failed to decrypt proxy password: {e}"
            raise ConfigurationError(msg) from e

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        setup_logging(self.config.observability)

    async def start_hot_reload(self) -> None:
        """Start hot-reload monitoring."""
        if not self.config_file:  # pragma: no cover
            return  # pragma: no cover

        logger = get_logger(
            __name__
        )  # pragma: no cover - Hot reload loop, difficult to test
        logger.info("Starting configuration hot-reload monitoring")  # pragma: no cover
        try:  # pragma: no cover
            # track current task so stop_hot_reload can cancel it
            self._hot_reload_task = asyncio.current_task()  # pragma: no cover
        except Exception:  # pragma: no cover
            self._hot_reload_task = None  # pragma: no cover

        while await self._hot_reload_loop_step(logger):  # pragma: no cover
            pass  # pragma: no cover

    async def _hot_reload_loop_step(self, logger: logging.Logger) -> bool:
        """Execute a single hot-reload step. Return False to stop the loop."""
        try:  # pragma: no cover - Hot reload loop, difficult to test
            if (
                self.config_file is not None and self.config_file.exists()
            ):  # pragma: no cover
                current_mtime = self.config_file.stat().st_mtime  # pragma: no cover
                if (
                    hasattr(self, "_last_mtime") and current_mtime > self._last_mtime
                ):  # pragma: no cover
                    logger.info(
                        "Configuration file changed, reloading..."
                    )  # pragma: no cover
                    self.config = self._load_config()  # pragma: no cover
                    self._setup_logging()  # pragma: no cover
                    logger.info(
                        "Configuration reloaded successfully"
                    )  # pragma: no cover
                self._last_mtime = current_mtime  # pragma: no cover

            await asyncio.sleep(1.0)  # Check every second  # pragma: no cover
            return True  # pragma: no cover
        except (
            asyncio.CancelledError
        ):  # pragma: no cover - Cancellation during hot reload loop, difficult to test
            return False  # pragma: no cover
        except Exception:  # pragma: no cover
            logger.exception("Error in hot-reload monitoring")  # pragma: no cover
            await asyncio.sleep(5.0)  # pragma: no cover
            return True  # pragma: no cover

    def stop_hot_reload(self) -> None:
        """Stop hot-reload monitoring."""
        if (
            hasattr(self, "_hot_reload_task") and self._hot_reload_task
        ):  # pragma: no cover
            self._hot_reload_task.cancel()  # pragma: no cover

    def validate_detailed(self) -> tuple[bool, list[str]]:
        """Validate configuration with detailed error messages.

        Returns:
            Tuple of (is_valid, list_of_errors)

        """
        from ccbt.config.config_schema import ConfigValidator

        config_data = self.config.model_dump(mode="json")

        # Basic validation
        is_valid, errors = ConfigValidator.validate_with_details(config_data)

        # Cross-field validation
        if is_valid:
            cross_field_errors = ConfigValidator.validate_cross_field_rules(config_data)
            errors.extend(cross_field_errors)
            is_valid = len(cross_field_errors) == 0

        return is_valid, errors

    def get_schema(self) -> dict[str, Any]:
        """Get configuration schema.

        Returns:
            JSON Schema for the configuration

        """
        from ccbt.config.config_schema import ConfigSchema

        return ConfigSchema.generate_full_schema()

    def get_section_schema(self, section_name: str) -> dict[str, Any] | None:
        """Get schema for a specific configuration section.

        Args:
            section_name: Name of the configuration section

        Returns:
            Schema for the section or None if not found

        """
        from ccbt.config.config_schema import ConfigSchema

        return ConfigSchema.get_schema_for_section(section_name)

    def list_options(self) -> list[dict[str, Any]]:
        """List all configuration options with metadata.

        Returns:
            List of configuration options with metadata

        """
        from ccbt.config.config_schema import ConfigDiscovery

        return ConfigDiscovery.list_all_options()

    def get_option_metadata(self, key_path: str) -> dict[str, Any] | None:
        """Get metadata for a specific configuration option.

        Args:
            key_path: Dot-separated path to the option

        Returns:
            Metadata for the option or None if not found

        """
        from ccbt.config.config_schema import ConfigDiscovery

        return ConfigDiscovery.get_option_metadata(key_path)

    def validate_option(self, key_path: str, value: Any) -> tuple[bool, str]:
        """Validate a single configuration option.

        Args:
            key_path: Dot-separated path to the option
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        from ccbt.config.config_schema import ConfigValidator

        return ConfigValidator.validate_option(key_path, value)

    def apply_profile(self, profile: OptimizationProfile | str | None = None) -> None:
        """Apply optimization profile to configuration.
        
        Args:
            profile: Profile to apply. If None, uses config.optimization.profile.
                    Can be a string (will be converted to enum) or OptimizationProfile enum.
        
        """
        if profile is None:
            profile = self.config.optimization.profile
        elif isinstance(profile, str):
            try:
                profile = OptimizationProfile(profile.lower())
            except ValueError:
                raise ConfigurationError(
                    f"Invalid optimization profile: {profile}. "
                    f"Must be one of: {[p.value for p in OptimizationProfile]}"
                )
        
        # Profile definitions
        profiles = {
            OptimizationProfile.BALANCED: {
                "strategy": {
                    "piece_selection": "rarest_first",
                    "pipeline_capacity": 4,
                    "endgame_duplicates": 2,
                },
                "network": {
                    "max_connections_per_torrent": 50,
                    "max_global_peers": 200,
                },
                "discovery": {
                    "tracker_announce_interval": 60.0,
                },
                "optimization": {
                    "enable_adaptive_intervals": True,
                    "enable_performance_based_recycling": True,
                    "enable_bandwidth_aware_scheduling": True,
                },
            },
            OptimizationProfile.SPEED: {
                "strategy": {
                    "piece_selection": "bandwidth_weighted_rarest",
                    "pipeline_capacity": 8,
                    "endgame_duplicates": 3,
                },
                "network": {
                    "max_connections_per_torrent": 100,
                    "max_global_peers": 500,
                },
                "discovery": {
                    "tracker_announce_interval": 30.0,
                },
                "optimization": {
                    "enable_adaptive_intervals": True,
                    "enable_performance_based_recycling": True,
                    "speed_aggressive_peer_recycling": True,
                    "enable_bandwidth_aware_scheduling": True,
                },
            },
            OptimizationProfile.EFFICIENCY: {
                "strategy": {
                    "piece_selection": "adaptive_hybrid",
                    "pipeline_capacity": 6,
                    "endgame_duplicates": 2,
                },
                "network": {
                    "max_connections_per_torrent": 30,
                    "max_global_peers": 150,
                },
                "discovery": {
                    "tracker_announce_interval": 90.0,
                },
                "optimization": {
                    "enable_adaptive_intervals": True,
                    "enable_performance_based_recycling": True,
                    "efficiency_connection_limit_multiplier": 0.8,
                    "enable_bandwidth_aware_scheduling": True,
                },
            },
            OptimizationProfile.LOW_RESOURCE: {
                "strategy": {
                    "piece_selection": "rarest_first",
                    "pipeline_capacity": 2,
                    "endgame_duplicates": 1,
                },
                "network": {
                    "max_connections_per_torrent": 10,
                    "max_global_peers": 50,
                },
                "discovery": {
                    "tracker_announce_interval": 120.0,
                },
                "optimization": {
                    "enable_adaptive_intervals": False,
                    "enable_performance_based_recycling": False,
                    "low_resource_max_connections": 20,
                    "enable_bandwidth_aware_scheduling": False,
                },
            },
            OptimizationProfile.CUSTOM: {
                # CUSTOM profile doesn't override anything
                # User has full control via config file
            },
        }
        
        if profile == OptimizationProfile.CUSTOM:
            # Don't apply any overrides for CUSTOM profile
            return
        
        profile_config = profiles.get(profile)
        if not profile_config:
            raise ConfigurationError(f"Profile {profile} not found in profile definitions")
        
        # Apply profile settings
        for section, settings in profile_config.items():
            if section == "strategy":
                for key, value in settings.items():
                    if hasattr(self.config.strategy, key):
                        setattr(self.config.strategy, key, value)
            elif section == "network":
                for key, value in settings.items():
                    if hasattr(self.config.network, key):
                        setattr(self.config.network, key, value)
            elif section == "discovery":
                for key, value in settings.items():
                    if hasattr(self.config.discovery, key):
                        setattr(self.config.discovery, key, value)
            elif section == "optimization":
                for key, value in settings.items():
                    if hasattr(self.config.optimization, key):
                        setattr(self.config.optimization, key, value)
        
        # Update profile field
        self.config.optimization.profile = profile

    def export_schema(self, format_type: str = "json") -> str:
        """Export configuration schema in specified format.

        Args:
            format_type: Output format ("json" or "yaml")

        Returns:
            Schema as string in specified format

        """
        from ccbt.config.config_schema import ConfigSchema

        return ConfigSchema.export_schema(format_type)


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def init_config(config_file: str | Path | None = None) -> ConfigManager:
    """Initialize the global configuration manager."""
    return ConfigManager(config_file)


def reload_config() -> Config:
    """Reload configuration from file."""
    if _config_manager is None:  # pragma: no cover
        msg = "Configuration not initialized"  # pragma: no cover
        raise ConfigurationError(msg)  # pragma: no cover

    _config_manager.config = _config_manager._load_config()  # noqa: SLF001
    _config_manager._setup_logging()  # noqa: SLF001
    return _config_manager.config


def set_config(new_config: Config) -> None:
    """Replace the global configuration at runtime.

    Reconfigures logging based on the new config. Components that snapshot
    config must re-read values to pick up changes.
    """
    global _config_manager
    if _config_manager is None:  # pragma: no cover
        _config_manager = ConfigManager(None)  # pragma: no cover
    _config_manager.config = new_config
    _config_manager._setup_logging()  # noqa: SLF001


# Backward compatibility functions
def get_network_config() -> NetworkConfig:
    """Get network configuration (backward compatibility)."""
    return get_config().network


def get_disk_config() -> DiskConfig:
    """Get disk configuration (backward compatibility)."""
    return get_config().disk


def get_strategy_config() -> StrategyConfig:
    """Get strategy configuration (backward compatibility)."""
    return get_config().strategy


def get_discovery_config() -> DiscoveryConfig:
    """Get discovery configuration (backward compatibility)."""
    return get_config().discovery


def get_observability_config() -> ObservabilityConfig:
    """Get observability configuration (backward compatibility)."""
    return get_config().observability
