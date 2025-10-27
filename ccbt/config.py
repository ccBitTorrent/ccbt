"""Configuration management for ccBitTorrent.

Provides centralized configuration with TOML support, validation, hot-reload,
and hierarchical loading from defaults → config file → environment → CLI → per-torrent.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

import toml

from .exceptions import ConfigurationError
from .logging_config import get_logger, setup_logging
from .models import (
    Config,
    DiscoveryConfig,
    DiskConfig,
    NetworkConfig,
    ObservabilityConfig,
    StrategyConfig,
)

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Global configuration instance
_config_manager: Optional["ConfigManager"] = None


class ConfigManager:
    """Manages configuration loading, validation, and hot-reload."""

    def __init__(self, config_file: Optional[Union[str, Path]] = None):
        """Initialize configuration manager.
        
        Args:
            config_file: Path to TOML config file. If None, searches for ccbt.toml
        """
        self.config_file = self._find_config_file(config_file)
        self.config = self._load_config()
        self._setup_logging()
        # internal
        self._hot_reload_task: Optional[asyncio.Task] = None

    def _find_config_file(self, config_file: Optional[Union[str, Path]]) -> Optional[Path]:
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

        return None

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
            except Exception as e:
                logging.warning(f"Failed to load config file {self.config_file}: {e}")

        # Apply environment overrides
        env_config = self._get_env_config()
        config_data = self._merge_config(config_data, env_config)

        try:
            # Create Pydantic model with validation
            config = Config(**config_data)
            return config
        except Exception as e:
            raise ConfigurationError(f"Invalid configuration: {e}")

    def _get_env_config(self) -> Dict[str, Any]:
        """Get configuration from environment variables."""
        env_config: Dict[str, Any] = {}

        # Mapping of environment variables to config paths
        env_mappings: Dict[str, str] = {
            # Network
            "CCBT_MAX_PEERS": "network.max_global_peers",
            "CCBT_MAX_PEERS_PER_TORRENT": "network.max_peers_per_torrent",
            "CCBT_LISTEN_PORT": "network.listen_port",
            "CCBT_PIPELINE_DEPTH": "network.pipeline_depth",
            "CCBT_BLOCK_SIZE_KIB": "network.block_size_kib",
            "CCBT_CONNECTION_TIMEOUT": "network.connection_timeout",
            "CCBT_HANDSHAKE_TIMEOUT": "network.handshake_timeout",
            "CCBT_KEEP_ALIVE_INTERVAL": "network.keep_alive_interval",
            "CCBT_GLOBAL_DOWN_KIB": "network.global_down_kib",
            "CCBT_GLOBAL_UP_KIB": "network.global_up_kib",
            "CCBT_PER_PEER_DOWN_KIB": "network.per_peer_down_kib",
            "CCBT_PER_PEER_UP_KIB": "network.per_peer_up_kib",
            "CCBT_MAX_UPLOAD_SLOTS": "network.max_upload_slots",
            "CCBT_TRACKER_TIMEOUT": "network.tracker_timeout",
            "CCBT_DNS_CACHE_TTL": "network.dns_cache_ttl",

            # Strategy
            "CCBT_PIECE_SELECTION": "strategy.piece_selection",
            "CCBT_ENDGAME_DUPLICATES": "strategy.endgame_duplicates",
            "CCBT_ENDGAME_THRESHOLD": "strategy.endgame_threshold",
            "CCBT_STREAMING_MODE": "strategy.streaming_mode",

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

            # Discovery
            "CCBT_ENABLE_DHT": "discovery.enable_dht",
            "CCBT_DHT_PORT": "discovery.dht_port",
            "CCBT_ENABLE_PEX": "discovery.enable_pex",
            "CCBT_ENABLE_UDP_TRACKERS": "discovery.enable_udp_trackers",

            # Observability
            "CCBT_LOG_LEVEL": "observability.log_level",
            "CCBT_LOG_FILE": "observability.log_file",
            "CCBT_ENABLE_METRICS": "observability.enable_metrics",
            "CCBT_METRICS_PORT": "observability.metrics_port",
            "CCBT_ENABLE_PEER_TRACING": "observability.enable_peer_tracing",
        }

        def _parse_env_value(raw: str) -> Union[bool, int, float, str]:
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

        def _set_nested(d: Dict[str, Any], path: str, value: Any) -> None:
            parts = path.split(".")
            cur = d
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value

        for env_name, cfg_path in env_mappings.items():
            raw = os.getenv(env_name)
            if raw is None:
                continue
            _set_nested(env_config, cfg_path, _parse_env_value(raw))

        return env_config

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration dictionaries recursively."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def export(self, fmt: str = "toml") -> str:
        """Export current configuration as a string in the given format.

        Args:
            fmt: one of "toml", "json", or "yaml"
        """
        data = self.config.model_dump(mode="json")
        fmt = (fmt or "toml").lower()
        if fmt == "toml":
            try:
                return toml.dumps(data)
            except Exception as e:
                raise ConfigurationError(f"Failed to export TOML: {e}")
        if fmt == "json":
            import json
            return json.dumps(data, indent=2)
        if fmt == "yaml":
            try:
                import yaml  # type: ignore
            except Exception:
                raise ConfigurationError("PyYAML not installed; cannot export YAML")
            return yaml.safe_dump(data, sort_keys=False)
        raise ConfigurationError(f"Unsupported export format: {fmt}")

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        setup_logging(self.config.observability)

    async def start_hot_reload(self) -> None:
        """Start hot-reload monitoring."""
        if not self.config_file:
            return

        logger = get_logger(__name__)
        logger.info("Starting configuration hot-reload monitoring")
        try:
            # track current task so stop_hot_reload can cancel it
            self._hot_reload_task = asyncio.current_task()
        except Exception:
            self._hot_reload_task = None

        while True:
            try:
                if self.config_file.exists():
                    current_mtime = self.config_file.stat().st_mtime
                    if hasattr(self, "_last_mtime") and current_mtime > self._last_mtime:
                        logger.info("Configuration file changed, reloading...")
                        self.config = self._load_config()
                        self._setup_logging()
                        logger.info("Configuration reloaded successfully")
                    self._last_mtime = current_mtime

                await asyncio.sleep(1.0)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in hot-reload monitoring: {e}")
                await asyncio.sleep(5.0)

    def stop_hot_reload(self) -> None:
        """Stop hot-reload monitoring."""
        if hasattr(self, "_hot_reload_task") and self._hot_reload_task:
            self._hot_reload_task.cancel()


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def init_config(config_file: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Initialize the global configuration manager."""
    global _config_manager
    _config_manager = ConfigManager(config_file)
    return _config_manager


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config_manager
    if _config_manager is None:
        raise ConfigurationError("Configuration not initialized")

    _config_manager.config = _config_manager._load_config()
    _config_manager._setup_logging()
    return _config_manager.config


def set_config(new_config: Config) -> None:
    """Replace the global configuration at runtime.

    Reconfigures logging based on the new config. Components that snapshot
    config must re-read values to pick up changes.
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(None)
    _config_manager.config = new_config
    _config_manager._setup_logging()


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
