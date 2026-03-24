"""Configuration management for ccBitTorrent.

Provides centralized configuration with TOML support, validation, hot-reload,
and deterministic effective precedence for static loads:
file (base) → optimization profile overlay → environment → platform (Windows) clamp
→ validated :class:`~ccbt.models.Config`. CLI and per-torrent overrides apply at
their respective layers after this.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union, cast

import toml

# Windows workaround: Patch Pydantic plugin loader to prevent OSError [Errno 22]
# This error occurs during plugin loading on Windows when Pydantic tries to discover
# plugins via entry points. We patch the plugin loader to return empty list on error.
if sys.platform == "win32":
    try:
        # Try to import and patch the plugin loader
        # The import path may vary by Pydantic version, so we try multiple approaches
        _loader_module = None
        for import_path in [
            "pydantic.plugin._loader",
            "pydantic._internal.plugin._loader",
            "pydantic.plugin._schema_validator",
        ]:
            try:
                _loader_module = __import__(import_path, fromlist=["get_plugins"])
                break
            except (ImportError, AttributeError):
                continue

        if _loader_module and hasattr(_loader_module, "get_plugins"):
            _original_get_plugins = _loader_module.get_plugins

            def _safe_get_plugins():
                """Safe plugin getter that handles Windows OSError."""
                try:
                    return cast("Callable[[], Any]", _original_get_plugins)()
                except (OSError, ValueError):
                    # On Windows, plugin discovery can fail with OSError [Errno 22]
                    # Return empty list to allow models to be created without plugins
                    return []

            # Type ignore needed because we're dynamically patching a module attribute
            _loader_module.get_plugins = _safe_get_plugins  # type: ignore[assignment]
    except Exception:
        # If patching fails for any reason, continue - models may still work
        # This is a best-effort workaround, not critical for functionality
        pass

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment, misc]

from ccbt.config.config_cli_values import COMMA_SEPARATED_LIST_PATHS
from ccbt.models import (
    Config,
    DiscoveryConfig,
    DiskConfig,
    MaxPeersPerTorrentProvenance,
    NetworkConfig,
    ObservabilityConfig,
    OptimizationProfile,
    StrategyConfig,
)
from ccbt.utils.exceptions import ConfigurationError
from ccbt.utils.logging_config import (
    get_cli_session_log_level_override,
    get_logger,
    set_cli_session_log_level_override,
    setup_logging,
)

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def _optimization_profile_overlays() -> dict[
    OptimizationProfile, dict[str, dict[str, Any]]
]:
    """Return optimization profile overlays merged during load (after file, before env)."""
    return {
        OptimizationProfile.BALANCED: {
            "strategy": {
                "piece_selection": "rarest_first",
                "pipeline_capacity": 4,
                "endgame_duplicates": 2,
            },
            "network": {
                "max_peers_per_torrent": 50,
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
                "max_peers_per_torrent": 100,
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
                "max_peers_per_torrent": 30,
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
                "max_peers_per_torrent": 10,
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
        OptimizationProfile.CUSTOM: {},
    }


def resolve_effective_max_peers_per_torrent(
    *,
    network_cap: int,
    per_torrent: Optional[int],
) -> int:
    """Return peer cap after global config; per-torrent option replaces when set (>= 0)."""
    if per_torrent is not None and int(per_torrent) >= 0:
        return int(per_torrent)
    return int(network_cap)


def _strip_inline_comment_suffix(text: str) -> str:
    """Remove a trailing inline comment after whitespace+``#``.

    TOML treats ``#`` inside double-quoted strings as literal. If a line like
    ``max_global_peers = 10000  # cap`` is mistakenly pasted as a single
    quoted string, the whole fragment becomes the value and Pydantic cannot
    coerce it. This keeps the payload before the first whitespace-``#``.
    """
    s = text
    i = 0
    while True:
        idx = s.find("#", i)
        if idx == -1:
            return s
        if idx > 0 and s[idx - 1].isspace():
            return s[: idx - 1].rstrip()
        i = idx + 1


def _strip_inline_comments_deep(obj: Any) -> Any:
    """Apply :func:`_strip_inline_comment_suffix` to all strings in nested dict/list."""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            obj[key] = _strip_inline_comments_deep(val)
        return obj
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _strip_inline_comments_deep(item)
        return obj
    if isinstance(obj, str):
        return _strip_inline_comment_suffix(obj)
    return obj


def _prune_empty_string_config_values(obj: Any) -> None:
    r"""Drop dict keys whose value is empty or whitespace-only.

    ``.env`` lines like ``VAR=  # note`` and bare ``VAR=`` become ``""`` in
    ``os.environ``; TOML can also set ``key = \"\"``. Removing the key lets
    Pydantic use sub-model defaults (e.g. optional ports, ``daemon.ipc_port``).
    """
    if isinstance(obj, dict):
        empty_keys = [
            k for k, v in obj.items() if isinstance(v, str) and v.strip() == ""
        ]
        for k in empty_keys:
            del obj[k]
        for v in obj.values():
            _prune_empty_string_config_values(v)
    elif isinstance(obj, list):
        for item in obj:
            _prune_empty_string_config_values(item)


def _try_coerce_network_int(value: Any) -> Optional[int]:
    """Parse an int for Windows network clamp comparisons only.

    Returns ``None`` for missing values, booleans, and non-numeric strings so we
    skip clamping and let Pydantic report invalid ``network.*`` integers.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(value)
    if isinstance(value, str):
        text = _strip_inline_comment_suffix(value.strip())
        if not text:
            return None
        try:
            if any(c in text for c in ".eE"):
                return int(float(text))
            return int(text, 10)
        except ValueError:
            return None
    return None


def _snapshot_max_peers_per_torrent(config_data: dict[str, Any]) -> Optional[int]:
    """Return coerced ``network.max_peers_per_torrent`` from raw load data, if present."""
    net = config_data.get("network")
    if not isinstance(net, dict):
        return None
    return _try_coerce_network_int(net.get("max_peers_per_torrent"))


class ConfigManager:
    """Manages configuration loading, validation, and hot-reload."""

    def __init__(self, config_file: Optional[Union[str, Path]] = None):
        """Initialize configuration manager.

        Args:
            config_file: Path to TOML config file. If None, searches for ccbt.toml

        """
        # internal
        self._hot_reload_task: Optional[asyncio.Task] = None
        self._encryption_key: Optional[bytes] = None
        self.config_file = self._find_config_file(config_file)
        self.max_peers_per_torrent_provenance: Optional[
            MaxPeersPerTorrentProvenance
        ] = None
        self.config = self._load_config()

        self._setup_logging()

    def _find_config_file(
        self,
        config_file: Optional[Union[str, Path]],
    ) -> Optional[Path]:
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

    def _normalize_loaded_config_data(self, config_data: dict[str, Any]) -> None:
        """Normalize file-derived config in place (comma-lists, proxy password)."""
        _strip_inline_comments_deep(config_data)
        security = config_data.get("security")
        if isinstance(security, dict):

            def _normalize_encryption_mode_alias(value: Any) -> str:
                if value is None:
                    return "preferred"
                normalized = str(value).strip().lower().replace("-", "_")
                normalized = normalized.replace(" ", "_")
                if normalized in {
                    "disabled",
                    "off",
                    "false",
                    "0",
                    "none",
                    "plaintext_only",
                }:
                    return "disabled"
                if normalized in {
                    "preferred",
                    "prefer",
                    "optional",
                    "enable",
                    "enabled",
                    "true",
                    "yes",
                    "on",
                    "1",
                    "allow_plaintext",
                    "prefer_encrypted",
                    "prefer_plaintext",
                }:
                    # Legacy and human-friendly aliases are normalized to preferred.
                    return "preferred"
                if normalized in {
                    "required",
                    "mandatory",
                    "force",
                    "require_encrypted",
                }:
                    return "required"
                return normalized

            legacy_pref = security.pop("encryption_preference", None)
            if legacy_pref is not None and security.get("encryption_mode") is None:
                pref_key = (
                    str(legacy_pref).lower().strip().replace(" ", "_").replace("-", "_")
                )
                pref_to_mode = {
                    "allow_plaintext": "preferred",
                    "prefer_encrypted": "preferred",
                    "require_encrypted": "required",
                    "disabled": "disabled",
                }
                security["encryption_mode"] = pref_to_mode.get(pref_key, "preferred")
            elif isinstance(security.get("encryption_mode"), str):
                security["encryption_mode"] = _normalize_encryption_mode_alias(
                    security["encryption_mode"]
                )

            if "encryption_mode" not in security and "enable_encryption" in security:
                # No explicit mode means keep preferred by default.
                security["encryption_mode"] = "preferred"
            network = config_data.get("network")
            if (
                isinstance(network, dict)
                and "enable_encryption" in network
                and "enable_encryption" not in security
            ):
                security["enable_encryption"] = bool(network["enable_encryption"])

        if (
            "security" in config_data
            and "encryption_allowed_ciphers" in config_data.get("security", {})
        ):
            value = config_data["security"]["encryption_allowed_ciphers"]
            normalized: list[str] = []
            if isinstance(value, str):
                raw_items = value.split(",")
            elif isinstance(value, list):
                raw_items = []
                for item in value:
                    if isinstance(item, str):
                        raw_items.extend(item.split(","))
                    else:
                        raw_items.append(str(item))
            else:
                raw_items = [str(value)]

            for item in raw_items:
                token = _strip_inline_comment_suffix(str(item).strip())
                if token:
                    normalized.append(token)

            config_data["security"]["encryption_allowed_ciphers"] = normalized

        if "proxy" in config_data and "proxy_bypass_list" in config_data.get(
            "proxy", {}
        ):
            value = config_data["proxy"]["proxy_bypass_list"]
            if isinstance(value, str) and "," in value:
                config_data["proxy"]["proxy_bypass_list"] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]

        if "proxy" in config_data and config_data["proxy"].get("proxy_password"):
            password = config_data["proxy"]["proxy_password"]
            if self._is_encrypted(password):
                try:
                    decrypted = self._decrypt_proxy_password(password)
                    config_data["proxy"]["proxy_password"] = decrypted
                except Exception as e:
                    logging.warning("Failed to decrypt proxy password: %s", e)

    def _apply_env_windows_and_build_config(
        self,
        config_data: dict[str, Any],
        *,
        provenance_profile: Optional[OptimizationProfile] = None,
        provenance_after_file_mpt: Optional[int] = None,
        provenance_after_profile_mpt: Optional[int] = None,
    ) -> Config:
        """Merge env, apply Windows network caps, construct ``Config``, record MPT provenance.

        Precedence before this step: file (base) → optimization profile overlay →
        (this method) environment → Windows compatibility clamp → ``Config`` validation.
        Per-torrent caps are applied later in session/peer setup, not here.
        """
        env_config = self._get_env_config()
        config_data = self._merge_config(config_data, env_config)
        _strip_inline_comments_deep(config_data)
        _prune_empty_string_config_values(config_data)

        mpt_after_env = _snapshot_max_peers_per_torrent(config_data)
        env_ccbt_mpt_set = "CCBT_MAX_PEERS_PER_TORRENT" in os.environ

        win_strict_effective = False
        if IS_WINDOWS and "network" in config_data:
            network_config = config_data.get("network", {})
            strict_raw = os.environ.get("CCBT_WINDOWS_NETWORK_COMPAT_STRICT", "true")
            win_strict_effective = str(strict_raw).strip().lower() not in (
                "0",
                "false",
                "no",
                "off",
            )
            # Windows caps apply here during env merge. Additional network limit tweaks may
            # run later via config_conditional (e.g. interface-count-based max_global_peers).
            if win_strict_effective:
                mgp_raw = network_config.get("max_global_peers", 600)
                mgp = _try_coerce_network_int(mgp_raw)
                if mgp is not None and mgp > 200:
                    network_config["max_global_peers"] = 200
                    logging.info(
                        "Clamped network.max_global_peers from %s to 200 on Windows compatibility path",
                        mgp_raw,
                    )
                pool_raw = network_config.get("connection_pool_max_connections", 400)
                pool = _try_coerce_network_int(pool_raw)
                if pool is not None and pool > 150:
                    network_config["connection_pool_max_connections"] = 150
                    logging.info(
                        "Clamped network.connection_pool_max_connections from %s to 150 on Windows compatibility path",
                        pool_raw,
                    )
                mpt_raw = network_config.get("max_peers_per_torrent", 200)
                mpt = _try_coerce_network_int(mpt_raw)
                if mpt is not None and mpt > 100:
                    network_config["max_peers_per_torrent"] = 100
                    logging.info(
                        "Clamped network.max_peers_per_torrent from %s to 100 on Windows compatibility path",
                        mpt_raw,
                    )
            else:
                logging.warning(
                    "Windows peer-limit clamps skipped (CCBT_WINDOWS_NETWORK_COMPAT_STRICT=%r). "
                    "Higher limits can be unstable on some Windows stacks.",
                    strict_raw,
                )
            config_data["network"] = network_config

        mpt_after_platform = _snapshot_max_peers_per_torrent(config_data)
        win_clamp_mpt = (
            IS_WINDOWS
            and "network" in config_data
            and win_strict_effective
            and mpt_after_env is not None
            and mpt_after_platform is not None
            and mpt_after_env != mpt_after_platform
        )

        profile_value = (
            provenance_profile.value
            if provenance_profile is not None
            else OptimizationProfile.BALANCED.value
        )

        try:
            cfg = Config(**config_data)
        except Exception as e:
            self.max_peers_per_torrent_provenance = None
            msg = f"Invalid configuration: {e}"
            raise ConfigurationError(msg) from e

        self.max_peers_per_torrent_provenance = MaxPeersPerTorrentProvenance(
            optimization_profile=profile_value,
            value_after_file=provenance_after_file_mpt,
            value_after_profile=provenance_after_profile_mpt,
            value_after_env=mpt_after_env,
            value_after_platform_clamp=mpt_after_platform,
            final=cfg.network.max_peers_per_torrent,
            env_ccbt_max_peers_per_torrent_set=env_ccbt_mpt_set,
            windows_platform_clamp_applied_to_mpt=win_clamp_mpt,
        )
        return cfg

    def simulate_load_from_file_dict(self, file_dict: dict[str, Any]) -> Config:
        """Validate effective config as if the TOML file were ``file_dict``.

        Merges environment overrides and applies the same Windows adjustments as
        :meth:`_load_config`. Used by CLI ``config set`` / ``apply`` before persisting.

        Args:
            file_dict: Parsed TOML object representing the file to write.

        Returns:
            Validated ``Config`` instance.

        Raises:
            ConfigurationError: If the resulting configuration is invalid.

        """
        config_data = dict(file_dict)
        self._normalize_loaded_config_data(config_data)
        file_mpt = _snapshot_max_peers_per_torrent(config_data)
        profile_enum = self._parse_optimization_profile_from_config_data(config_data)
        self._merge_optimization_profile_into_config_data(config_data)
        after_prof_mpt = _snapshot_max_peers_per_torrent(config_data)
        return self._apply_env_windows_and_build_config(
            config_data,
            provenance_profile=profile_enum,
            provenance_after_file_mpt=file_mpt,
            provenance_after_profile_mpt=after_prof_mpt,
        )

    @staticmethod
    def _parse_optimization_profile_from_config_data(
        config_data: dict[str, Any],
    ) -> OptimizationProfile:
        """Read ``[optimization].profile`` from raw config before :class:`Config` exists."""
        opt = config_data.get("optimization")
        if not isinstance(opt, dict):
            return OptimizationProfile.BALANCED
        raw = opt.get("profile")
        if raw is None:
            return OptimizationProfile.BALANCED
        if isinstance(raw, OptimizationProfile):
            return raw
        if isinstance(raw, str):
            try:
                return OptimizationProfile(raw.lower())
            except ValueError as e:
                msg = (
                    f"Invalid optimization profile: {raw!r}. "
                    f"Must be one of: {[p.value for p in OptimizationProfile]}"
                )
                raise ConfigurationError(msg) from e
        msg = f"Invalid optimization profile type: {type(raw)!r}"
        raise ConfigurationError(msg)

    @staticmethod
    def _merge_optimization_profile_into_config_data(
        config_data: dict[str, Any],
    ) -> None:
        """Apply built-in profile overlays to ``config_data`` (file base already merged)."""
        profile = ConfigManager._parse_optimization_profile_from_config_data(
            config_data
        )
        if profile == OptimizationProfile.CUSTOM:
            return

        profile_config = _optimization_profile_overlays().get(profile)
        if not profile_config:
            msg = f"Profile {profile} not found in profile definitions"
            raise ConfigurationError(msg)

        for section, settings in profile_config.items():
            if section == "strategy":
                sec = config_data.setdefault("strategy", {})
                if not isinstance(sec, dict):
                    msg = (
                        f"Invalid [strategy] section: expected dict, got {type(sec)!r}"
                    )
                    raise ConfigurationError(msg)
                for key, value in settings.items():
                    sec[key] = value
            elif section == "network":
                sec = config_data.setdefault("network", {})
                if not isinstance(sec, dict):
                    msg = f"Invalid [network] section: expected dict, got {type(sec)!r}"
                    raise ConfigurationError(msg)
                for key, value in settings.items():
                    sec[key] = value
            elif section == "discovery":
                sec = config_data.setdefault("discovery", {})
                if not isinstance(sec, dict):
                    msg = (
                        f"Invalid [discovery] section: expected dict, got {type(sec)!r}"
                    )
                    raise ConfigurationError(msg)
                for key, value in settings.items():
                    sec[key] = value
            elif section == "optimization":
                sec = config_data.setdefault("optimization", {})
                if not isinstance(sec, dict):
                    msg = f"Invalid [optimization] section: expected dict, got {type(sec)!r}"
                    raise ConfigurationError(msg)
                for key, value in settings.items():
                    sec[key] = value

        opt = config_data.setdefault("optimization", {})
        if not isinstance(opt, dict):
            msg = f"Invalid [optimization] section: expected dict, got {type(opt)!r}"
            raise ConfigurationError(msg)
        opt["profile"] = profile.value

    def _load_config(self) -> Config:
        """Load configuration: file → profile overlay → env (+ Windows clamp) → ``Config``."""
        config_data: dict[str, Any] = {}

        if self.config_file and self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    toml_data = toml.load(f)
                config_data.update(toml_data)
                self._normalize_loaded_config_data(config_data)
            except Exception as e:
                logging.warning(
                    "Failed to load config file %s: %s", self.config_file, e
                )

        file_mpt = _snapshot_max_peers_per_torrent(config_data)
        profile_enum = self._parse_optimization_profile_from_config_data(config_data)
        self._merge_optimization_profile_into_config_data(config_data)
        after_prof_mpt = _snapshot_max_peers_per_torrent(config_data)
        return self._apply_env_windows_and_build_config(
            config_data,
            provenance_profile=profile_enum,
            provenance_after_file_mpt=file_mpt,
            provenance_after_profile_mpt=after_prof_mpt,
        )

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
            "CCBT_SPARSE_PIPELINE_STALE_PAYLOAD_CANCEL_S": (
                "network.sparse_pipeline_stale_payload_cancel_s"
            ),
            "CCBT_BLOCK_SIZE_KIB": "network.block_size_kib",
            "CCBT_CONNECTION_TIMEOUT": "network.connection_timeout",
            "CCBT_HANDSHAKE_TIMEOUT": "network.handshake_timeout",
            "CCBT_HANDSHAKE_TIMEOUT_DESPERATION_MIN": "network.handshake_timeout_desperation_min",
            "CCBT_HANDSHAKE_TIMEOUT_DESPERATION_MAX": "network.handshake_timeout_desperation_max",
            "CCBT_HANDSHAKE_TIMEOUT_NORMAL_MIN": "network.handshake_timeout_normal_min",
            "CCBT_HANDSHAKE_TIMEOUT_NORMAL_MAX": "network.handshake_timeout_normal_max",
            "CCBT_HANDSHAKE_TIMEOUT_HEALTHY_MIN": "network.handshake_timeout_healthy_min",
            "CCBT_HANDSHAKE_TIMEOUT_HEALTHY_MAX": "network.handshake_timeout_healthy_max",
            "CCBT_HANDSHAKE_ADAPTIVE_TIMEOUT_ENABLED": "network.handshake_adaptive_timeout_enabled",
            # false = deprecated legacy (always max timeout in desperation band)
            "CCBT_HANDSHAKE_TIMEOUT_DESPERATION_INTERPOLATE": (
                "network.handshake_timeout_desperation_interpolate"
            ),
            "CCBT_ADAPTIVE_TIMEOUT_HEALTH_PEER_SOURCE": (
                "network.adaptive_timeout_health_peer_source"
            ),
            "CCBT_ADAPTIVE_TIMEOUT_DESPERATION_MAX_PEERS": (
                "network.adaptive_timeout_desperation_max_peers"
            ),
            "CCBT_ADAPTIVE_TIMEOUT_NORMAL_MAX_PEERS": (
                "network.adaptive_timeout_normal_max_peers"
            ),
            "CCBT_METADATA_EXCHANGE_TIMEOUT": "network.metadata_exchange_timeout",
            "CCBT_PEER_QUALITY_PROBATION_TIMEOUT": "network.peer_quality_probation_timeout",
            "CCBT_METADATA_PIECE_TIMEOUT": "network.metadata_piece_timeout",
            "CCBT_BITFIELD_HAVE_WAIT_TIMEOUT_S": "network.bitfield_have_wait_timeout_s",
            "CCBT_BITFIELD_HAVE_WAIT_METADATA_INCOMPLETE_MULTIPLIER": (
                "network.bitfield_have_wait_metadata_incomplete_multiplier"
            ),
            "CCBT_CONNECTION_HEALTH_CHECK_INTERVAL": "network.connection_health_check_interval",
            "CCBT_CONNECTION_VALIDATION_ENABLED": "network.connection_validation_enabled",
            "CCBT_PEER_VALIDATION_ENABLED": "network.peer_validation_enabled",
            "CCBT_SEND_BITFIELD_AFTER_METADATA": "network.send_bitfield_after_metadata",
            "CCBT_SEND_INTERESTED_AFTER_METADATA": "network.send_interested_after_metadata",
            "CCBT_MAX_CONCURRENT_CONNECTION_ATTEMPTS": "network.max_concurrent_connection_attempts",
            "CCBT_CONNECT_TO_PEERS_PARALLEL_BATCHES": (
                "network.connect_to_peers_parallel_batches"
            ),
            "CCBT_MSE_INITIATOR_TIMEOUT_SCALE_ZERO_ACTIVE": (
                "network.mse_initiator_timeout_scale_zero_active"
            ),
            "CCBT_ENABLE_FAIL_FAST_DHT": "network.enable_fail_fast_dht",
            "CCBT_FAIL_FAST_DHT_TIMEOUT": "network.fail_fast_dht_timeout",
            "CCBT_KEEP_ALIVE_INTERVAL": "network.keep_alive_interval",
            "CCBT_GLOBAL_DOWN_KIB": "network.global_down_kib",
            "CCBT_GLOBAL_UP_KIB": "network.global_up_kib",
            "CCBT_PER_PEER_DOWN_KIB": "network.per_peer_down_kib",
            "CCBT_PER_PEER_UP_KIB": "network.per_peer_up_kib",
            "CCBT_MAX_UPLOAD_SLOTS": "network.max_upload_slots",
            "CCBT_RECIPROCATION_CHOKED_PEER_SCORE_BOOST": (
                "network.reciprocation_choked_peer_score_boost"
            ),
            "CCBT_RECIPROCATION_REMOTE_NOT_INTERESTED_BOOST": (
                "network.reciprocation_remote_not_interested_boost"
            ),
            "CCBT_LOW_DOWNLOAD_DIVERSITY_THRESHOLD": (
                "network.low_download_diversity_threshold"
            ),
            "CCBT_LOW_DOWNLOAD_DIVERSITY_FULL_UNCHOKE": (
                "network.low_download_diversity_full_unchoke"
            ),
            "CCBT_LOW_DOWNLOAD_DIVERSITY_USE_HYSTERESIS": (
                "network.low_download_diversity_use_hysteresis"
            ),
            "CCBT_LOW_DOWNLOAD_DIVERSITY_EXIT_MARGIN": (
                "network.low_download_diversity_exit_margin"
            ),
            "CCBT_LOW_DOWNLOAD_DIVERSITY_MAX_PEERS": (
                "network.low_download_diversity_max_peers"
            ),
            "CCBT_LEECH_HEAVY_SWARM_TOTAL_UPLOAD_BPS_THRESHOLD": (
                "network.leech_heavy_swarm_total_upload_bps_threshold"
            ),
            "CCBT_INBOUND_UNKNOWN_HASH_WARNING_SAMPLE_INTERVAL": (
                "network.inbound_unknown_hash_warning_sample_interval"
            ),
            "CCBT_INBOUND_MAX_PROBATION_INFLIGHT_PER_HASH": (
                "network.inbound_max_probation_inflight_per_hash"
            ),
            "CCBT_INBOUND_REGISTRATION_WAIT_CAP_NO_SESSIONS_S": (
                "network.inbound_registration_wait_cap_no_sessions_s"
            ),
            "CCBT_INBOUND_REGISTRATION_WAIT_CAP_DEFAULT_S": (
                "network.inbound_registration_wait_cap_default_s"
            ),
            "CCBT_INBOUND_REGISTRATION_WAIT_CAP_STORM_S": (
                "network.inbound_registration_wait_cap_storm_s"
            ),
            "CCBT_INBOUND_REGISTRATION_WAIT_CAP_METADATA_PENDING_S": (
                "network.inbound_registration_wait_cap_metadata_pending_s"
            ),
            "CCBT_INBOUND_GRACE_POLL_SECONDS_NO_SESSIONS_S": (
                "network.inbound_grace_poll_seconds_no_sessions_s"
            ),
            "CCBT_INBOUND_GRACE_POLL_SECONDS_STORM_S": (
                "network.inbound_grace_poll_seconds_storm_s"
            ),
            "CCBT_INBOUND_GRACE_POLL_SECONDS_DEFAULT_S": (
                "network.inbound_grace_poll_seconds_default_s"
            ),
            "CCBT_INBOUND_PROBATION_WINDOW_S": "network.inbound_probation_window_s",
            "CCBT_INBOUND_PROBATION_WINDOW_STORM_S": (
                "network.inbound_probation_window_storm_s"
            ),
            "CCBT_INBOUND_PROBATION_RETRY_INTERVAL_S": (
                "network.inbound_probation_retry_interval_s"
            ),
            "CCBT_INBOUND_UNKNOWN_HASH_STORM_THRESHOLD": (
                "network.inbound_unknown_hash_storm_threshold"
            ),
            "CCBT_INBOUND_PROBATION_WAIT_QUEUE_MAX_TOTAL": (
                "network.inbound_probation_wait_queue_max_total"
            ),
            "CCBT_INBOUND_PROBATION_QUEUED_MAX_WAIT_S": (
                "network.inbound_probation_queued_max_wait_s"
            ),
            "CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_ENABLED": (
                "network.choke_only_slot_replacement_enabled"
            ),
            "CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_MIN_ACTIVE_PEERS": (
                "network.choke_only_slot_replacement_min_active_peers"
            ),
            "CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_MIN_CHOKE_RATIO": (
                "network.choke_only_slot_replacement_min_choke_ratio"
            ),
            "CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_MAX_DISCONNECT_FRACTION": (
                "network.choke_only_slot_replacement_max_disconnect_fraction"
            ),
            "CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_AT_LIMIT_FRACTION": (
                "network.choke_only_slot_replacement_at_limit_fraction"
            ),
            "CCBT_RECIPROCATION_MAX_COMBINED_BOOST": (
                "network.reciprocation_max_combined_boost"
            ),
            "CCBT_OPTIMISTIC_UNCHOKE_TOP_CANDIDATES": (
                "network.optimistic_unchoke_top_candidates"
            ),
            "CCBT_OPTIMISTIC_UNCHOKE_USE_JITTER": (
                "network.optimistic_unchoke_use_jitter"
            ),
            "CCBT_PEER_CHOKED_HARD_TIMEOUT_SECONDS": (
                "network.peer_choked_hard_timeout_seconds"
            ),
            "CCBT_PEER_CHOKED_ANCHOR_TIMEOUT_SECONDS": (
                "network.peer_choked_anchor_timeout_seconds"
            ),
            "CCBT_PEER_CHOKED_SOLO_GRACE_SECONDS": (
                "network.peer_choked_solo_grace_seconds"
            ),
            "CCBT_PEER_CHOKED_SOLO_GRACE_ZERO_BYTES_CAP_SECONDS": (
                "network.peer_choked_solo_grace_zero_bytes_cap_seconds"
            ),
            "CCBT_PEER_QUALITY_PROBATION_SPARSE_CHOKE_GRACE_SECONDS": (
                "network.peer_quality_probation_sparse_choke_grace_seconds"
            ),
            "CCBT_PEER_RECYCLE_SPARSE_BACKOFF_CAP_SECONDS": (
                "network.peer_recycle_sparse_backoff_cap_seconds"
            ),
            "CCBT_RECYCLE_PRESSURE_THRESHOLD": "network.recycle_pressure_threshold",
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
            "CCBT_TRACKER_NETWORK_FAILURE_QUARANTINE_SECONDS": (
                "network.tracker_network_failure_quarantine_seconds"
            ),
            "CCBT_TRACKER_PAYLOAD_FAILURE_QUARANTINE_SECONDS": (
                "network.tracker_payload_failure_quarantine_seconds"
            ),
            "CCBT_TRACKER_DNS_REFUSED_ESCALATION_STREAK": (
                "network.tracker_dns_refused_escalation_streak"
            ),
            "CCBT_TRACKER_ZERO_ACTIVE_BATCHES_BEFORE_DHT_SHORT_CIRCUIT": (
                "network.tracker_zero_active_batches_before_dht_short_circuit"
            ),
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
            "CCBT_PEER_SELECTOR_ML_RANKING_WEIGHT": (
                "strategy.peer_selector_ml_ranking_weight"
            ),
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
            "CCBT_MIN_PEERS_BEFORE_DHT": "discovery.min_peers_before_dht",
            "CCBT_DHT_PORT": "discovery.dht_port",
            "CCBT_ENABLE_PEX": "discovery.enable_pex",
            "CCBT_ENABLE_UDP_TRACKERS": "discovery.enable_udp_trackers",
            "CCBT_ENABLE_HTTP_TRACKERS": "discovery.enable_http_trackers",
            "CCBT_TRACKER_ANNOUNCE_INTERVAL": "discovery.tracker_announce_interval",
            "CCBT_TRACKER_SCRAPE_INTERVAL": "discovery.tracker_scrape_interval",
            "CCBT_TRACKER_AUTO_SCRAPE": "discovery.tracker_auto_scrape",
            "CCBT_TRACKER_STOPPED_ANNOUNCE_TIMEOUT_S": (
                "discovery.tracker_stopped_announce_timeout_s"
            ),
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_ENABLED": "discovery.tracker_adaptive_interval_enabled",
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_MIN": "discovery.tracker_adaptive_interval_min",
            "CCBT_TRACKER_ADAPTIVE_INTERVAL_MAX": "discovery.tracker_adaptive_interval_max",
            "CCBT_TRACKER_BASE_ANNOUNCE_INTERVAL": "discovery.tracker_base_announce_interval",
            "CCBT_TRACKER_PEER_COUNT_WEIGHT": "discovery.tracker_peer_count_weight",
            "CCBT_TRACKER_PERFORMANCE_WEIGHT": "discovery.tracker_performance_weight",
            "CCBT_DEFAULT_TRACKERS": "discovery.default_trackers",
            "CCBT_TRACKER_UDP_PENDING_SOFT_CAP_PER_HOST": (
                "discovery.tracker_udp_pending_soft_cap_per_host"
            ),
            "CCBT_TRACKER_UDP_MAX_PENDING_REQUESTS": (
                "discovery.tracker_udp_max_pending_requests"
            ),
            "CCBT_TRACKER_UDP_WAIT_PACING_LOAD_RATIO": (
                "discovery.tracker_udp_wait_pacing_load_ratio"
            ),
            "CCBT_TRACKER_INGRESS_HOLD_PENDING_QUEUE_THRESHOLD": (
                "discovery.tracker_ingress_hold_pending_queue_threshold"
            ),
            # Deprecated to set false: legacy peer ordering; default true is supported path.
            "CCBT_STRICT_TRACKER_SOURCE_CONNECT_PRIORITY": (
                "discovery.strict_tracker_source_connect_priority"
            ),
            "CCBT_STRICT_TRACKER_PENDING_DHT_PEX_BOOST": (
                "discovery.strict_tracker_pending_dht_pex_boost"
            ),
            "CCBT_STRICT_TRACKER_PENDING_TRACKER_PREFIX": (
                "discovery.strict_tracker_pending_tracker_prefix"
            ),
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
            "CCBT_DHT_ADAPTIVE_TIMEOUT_ENABLED": "discovery.dht_adaptive_timeout_enabled",
            "CCBT_DHT_TIMEOUT_DESPERATION_MIN": "discovery.dht_timeout_desperation_min",
            "CCBT_DHT_TIMEOUT_DESPERATION_MAX": "discovery.dht_timeout_desperation_max",
            "CCBT_DHT_TIMEOUT_NORMAL_MIN": "discovery.dht_timeout_normal_min",
            "CCBT_DHT_TIMEOUT_NORMAL_MAX": "discovery.dht_timeout_normal_max",
            "CCBT_DHT_TIMEOUT_HEALTHY_MIN": "discovery.dht_timeout_healthy_min",
            "CCBT_DHT_TIMEOUT_HEALTHY_MAX": "discovery.dht_timeout_healthy_max",
            # DHT query parameters (Kademlia algorithm)
            "CCBT_DHT_NORMAL_ALPHA": "discovery.dht_normal_alpha",
            "CCBT_DHT_NORMAL_K": "discovery.dht_normal_k",
            "CCBT_DHT_NORMAL_MAX_DEPTH": "discovery.dht_normal_max_depth",
            "CCBT_DHT_AGGRESSIVE_ALPHA": "discovery.dht_aggressive_alpha",
            "CCBT_DHT_AGGRESSIVE_K": "discovery.dht_aggressive_k",
            "CCBT_DHT_AGGRESSIVE_MAX_DEPTH": "discovery.dht_aggressive_max_depth",
            "CCBT_DHT_BOOTSTRAP_NODES": "discovery.dht_bootstrap_nodes",
            "CCBT_BOOTSTRAP_SEED_REPLAY_LIMIT": "discovery.bootstrap_seed_replay_limit",
            "CCBT_DHT_BOOTSTRAP_RETRIES_MAX": "discovery.dht_bootstrap_retries_max",
            "CCBT_BOOTSTRAP_RETRY_MEMO_TTL_S": "discovery.bootstrap_retry_memo_ttl_s",
            "CCBT_DHT_BOOTSTRAP_MEMO_TTL_S": "discovery.dht_bootstrap_memo_ttl_s",
            "CCBT_DHT_DNS_HOST_BACKOFF_INITIAL_S": (
                "discovery.dht_dns_host_backoff_initial_s"
            ),
            "CCBT_DHT_DNS_HOST_BACKOFF_MAX_S": "discovery.dht_dns_host_backoff_max_s",
            "CCBT_DHT_DNS_HOST_BACKOFF_MULTIPLIER": (
                "discovery.dht_dns_host_backoff_multiplier"
            ),
            "CCBT_DHT_ZERO_STATE_REPROBE_WAIT_S": "discovery.dht_zero_state_reprobe_wait_s",
            "CCBT_DHT_EMPTY_STATE_BACKOFF_FACTOR": "discovery.dht_empty_state_backoff_factor",
            "CCBT_DHT_REBOOTSTRAP_TIMEOUT_S": "discovery.dht_rebootstrap_timeout_s",
            "CCBT_DHT_BOOTSTRAP_TIMEOUT_S": "discovery.dht_bootstrap_timeout_s",
            "CCBT_LOW_PEER_THRESHOLD": "discovery.low_peer_threshold",
            "CCBT_LOW_PEER_SUPPRESSION_WINDOW_S": "discovery.low_peer_suppression_window_s",
            "CCBT_PEER_COUNT_LOW_SKIP_DHT_REQUIRES_USABLE_PATH": (
                "discovery.peer_count_low_skip_dht_requires_usable_path"
            ),
            "CCBT_REQUESTABLE_DRIVEN_DISCOVERY_ENABLED": (
                "discovery.requestable_driven_discovery_enabled"
            ),
            "CCBT_TARGET_REQUESTABLE_PEERS": "discovery.target_requestable_peers",
            "CCBT_REQUESTABLE_TICK_INTERVAL_S": "discovery.requestable_tick_interval_s",
            "CCBT_REQUESTABLE_FORCE_DHT_WHEN_ZERO": (
                "discovery.requestable_force_dht_when_zero"
            ),
            "CCBT_MAX_CONNECT_BURST_PER_TICK": "discovery.max_connect_burst_per_tick",
            "CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_TOTAL": (
                "discovery.tracker_immediate_connect_burst_total"
            ),
            "CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_PER_SOURCE": (
                "discovery.tracker_immediate_connect_burst_per_source"
            ),
            "CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_S": (
                "discovery.tracker_immediate_connect_window_s"
            ),
            "CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_CAP": (
                "discovery.tracker_immediate_connect_window_cap"
            ),
            "CCBT_TRACKER_IMMEDIATE_PER_SOURCE_CAP_MODE": (
                "discovery.tracker_immediate_per_source_cap_mode"
            ),
            "CCBT_TRACKER_IMMEDIATE_PER_TRACKER_COOLDOWN_ENABLED": (
                "discovery.tracker_immediate_per_tracker_cooldown_enabled"
            ),
            "CCBT_MAX_TRACKER_URLS_PER_TORRENT": "discovery.max_tracker_urls_per_torrent",
            "CCBT_ANNOUNCE_MAX_TRACKERS_PER_ROUND": (
                "discovery.announce_max_trackers_per_round"
            ),
            # XET chunk discovery
            "CCBT_XET_CHUNK_QUERY_BATCH_SIZE": "discovery.xet_chunk_query_batch_size",
            "CCBT_XET_CHUNK_QUERY_MAX_CONCURRENT": "discovery.xet_chunk_query_max_concurrent",
            "CCBT_DISCOVERY_CACHE_TTL": "discovery.discovery_cache_ttl",
            # Media streaming
            "CCBT_ENABLE_MEDIA_STREAMING": "media.enable_media_streaming",
            "CCBT_MEDIA_BIND_HOST": "media.bind_host",
            "CCBT_MEDIA_DEFAULT_PORT": "media.default_port",
            "CCBT_MEDIA_STARTUP_BUFFER_SECONDS": "media.startup_buffer_seconds",
            "CCBT_MEDIA_REQUEST_WAIT_TIMEOUT_SECONDS": "media.request_wait_timeout_seconds",
            "CCBT_MEDIA_ASSUMED_BITRATE_BPS": "media.assumed_bitrate_bytes_per_second",
            "CCBT_MEDIA_STREAM_CHUNK_SIZE_KIB": "media.stream_chunk_size_kib",
            "CCBT_MEDIA_TOKEN_TTL_SECONDS": "media.token_ttl_seconds",
            "CCBT_MEDIA_VLC_EXECUTABLE_PATH": "media.vlc_executable_path",
            "CCBT_ENABLE_INLINE_MEDIA_PREVIEW": "media.enable_inline_media_preview",
            "CCBT_INLINE_MEDIA_PREVIEW_MODE": "media.inline_media_preview_mode",
            # Security / MSE-PE (BEP 3). Canonical toggle is security.enable_encryption;
            # CCBT_NETWORK_ENABLE_ENCRYPTION mirrors [network] enable_encryption in ccbt.toml
            # (merged into security by Config model validation).
            "CCBT_ENABLE_ENCRYPTION": "security.enable_encryption",
            "CCBT_NETWORK_ENABLE_ENCRYPTION": "network.enable_encryption",
            "CCBT_ENCRYPTION_MODE": "security.encryption_mode",
            "CCBT_ENCRYPTION_DH_KEY_SIZE": "security.encryption_dh_key_size",
            "CCBT_ENCRYPTION_PREFER_RC4": "security.encryption_prefer_rc4",
            "CCBT_ENCRYPTION_ALLOWED_CIPHERS": "security.encryption_allowed_ciphers",
            "CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK": "security.encryption_allow_plain_fallback",
            "CCBT_VALIDATE_PEERS": "security.validate_peers",
            "CCBT_RATE_LIMIT_ENABLED": "security.rate_limit_enabled",
            "CCBT_MAX_CONNECTIONS_PER_PEER": "security.max_connections_per_peer",
            "CCBT_PEER_QUALITY_THRESHOLD": "security.peer_quality_threshold",
            "CCBT_AUTHENTICATED_SWARMS_MODE": "security.authenticated_swarms.mode",
            "CCBT_AUTHENTICATED_SWARMS_DISCOVERY_MODE": (
                "security.authenticated_swarms.discovery_mode"
            ),
            "CCBT_AUTHENTICATED_SWARMS_DISCOVERY_STRICT_FOR_STRICT_MODE": (
                "security.authenticated_swarms.discovery_strict_for_strict_mode"
            ),
            "CCBT_AUTHENTICATED_SWARMS_STRICT_LTEP_TIMEOUT_S": (
                "security.authenticated_swarms.strict_ltep_handshake_timeout_s"
            ),
            "CCBT_AUTHENTICATED_SWARMS_TRUSTED_IDS": (
                "security.authenticated_swarms.trusted_swarm_ids"
            ),
            "CCBT_AUTHENTICATED_SWARMS_FAIL_CLOSED_ON_PARSE_ERRORS": (
                "security.authenticated_swarms.fail_closed_on_parse_errors"
            ),
            "CCBT_AUTHENTICATED_SWARMS_TRUST_STORE_PATH": (
                "security.authenticated_swarms.trust_store_path"
            ),
            "CCBT_AUTHENTICATED_SWARMS_TRUST_STORE_REFRESH_INTERVAL_S": (
                "security.authenticated_swarms.trust_store_refresh_interval_s"
            ),
            "CCBT_AUTHENTICATED_SWARMS_REVOCATION_PROFILE_PATH": (
                "security.authenticated_swarms.revocation_profile_path"
            ),
            "CCBT_AUTHENTICATED_SWARMS_REVOCATION_REFRESH_INTERVAL_S": (
                "security.authenticated_swarms.revocation_refresh_interval_s"
            ),
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
            "CCBT_LOG_FORMAT": "observability.log_format",
            "CCBT_LOG_CORRELATION_ID": "observability.log_correlation_id",
            "CCBT_ENABLE_METRICS": "observability.enable_metrics",
            "CCBT_METRICS_INTERVAL": "observability.metrics_interval",
            "CCBT_METRICS_PORT": "observability.metrics_port",
            "CCBT_ENABLE_PEER_TRACING": "observability.enable_peer_tracing",
            "CCBT_STRUCTURED_LOGGING": "observability.structured_logging",
            "CCBT_TRACE_FILE": "observability.trace_file",
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
            "CCBT_XET_SYNC_ALLOWLIST_PATH": "xet_sync.allowlist_path",
            "CCBT_XET_SYNC_AUTH_SCOPE": "xet_sync.auth_scope",
            "CCBT_XET_SYNC_HASH_ALGORITHM_POLICY": "xet_sync.hash_algorithm_policy",
            "CCBT_XET_SYNC_REQUIRE_SIGNED_METADATA": "xet_sync.require_signed_metadata",
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
        ) -> Union[bool, int, float, str, list[str]]:
            # Handle list values (comma-separated strings)
            if path in COMMA_SEPARATED_LIST_PATHS:
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

    def get_runtime_env_diagnostics(self) -> dict[str, Any]:
        """Return runtime env + dotenv provenance diagnostics for support reports."""
        import os

        return {
            "dotenv_loader_requested": str(os.getenv("CCBT_LOAD_DOTENV", "")).strip(),
            "dotenv_loaded": str(os.getenv("CCBT_DOTENV_LOADED", "0")).strip(),
            "dotenv_path_effective": str(
                os.getenv("CCBT_DOTENV_PATH_EFFECTIVE", "")
            ).strip(),
            "dotenv_keys_loaded": str(
                os.getenv("CCBT_DOTENV_KEYS_LOADED", "0")
            ).strip(),
            "max_peers_per_torrent_effective": int(
                getattr(self.config.network, "max_peers_per_torrent", 0) or 0
            ),
            "tracker_immediate_connect_burst_total": int(
                getattr(
                    self.config.discovery,
                    "tracker_immediate_connect_burst_total",
                    0,
                )
                or 0
            ),
            "tracker_immediate_per_tracker_cooldown_enabled": bool(
                getattr(
                    self.config.discovery,
                    "tracker_immediate_per_tracker_cooldown_enabled",
                    True,
                )
            ),
            "target_requestable_peers": int(
                getattr(self.config.discovery, "target_requestable_peers", 0) or 0
            ),
        }

    def save_config(self) -> None:
        """Save current configuration to file.

        Writes the current configuration to the config file (TOML format).
        If no config file exists, creates one in the current directory.
        """
        if self.config_file is None:
            # Create config file in current directory
            self.config_file = Path.cwd() / "ccbt.toml"

        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Export config as TOML and write to file
        config_str = self.export(fmt="toml", encrypt_passwords=True)
        self.config_file.write_text(config_str, encoding="utf-8")

    def _get_encryption_key(self) -> Optional[bytes]:
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
        override = get_cli_session_log_level_override()
        setup_logging(
            self.config.observability,
            effective_log_level=override,
        )

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

    def get_section_schema(self, section_name: str) -> Optional[dict[str, Any]]:
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

    def get_option_metadata(self, key_path: str) -> Optional[dict[str, Any]]:
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

    def apply_profile(
        self, profile: Optional[Union[OptimizationProfile, str]] = None
    ) -> None:
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
            except ValueError as e:
                msg = (
                    f"Invalid optimization profile: {profile}. "
                    f"Must be one of: {[p.value for p in OptimizationProfile]}"
                )
                raise ConfigurationError(msg) from e

        if profile == OptimizationProfile.CUSTOM:
            # Don't apply any overrides for CUSTOM profile
            return

        profile_config = _optimization_profile_overlays().get(profile)
        if not profile_config:
            msg = f"Profile {profile} not found in profile definitions"
            raise ConfigurationError(msg)

        # Apply profile settings
        for section, settings in profile_config.items():
            if section == "strategy":
                for key, value in settings.items():
                    if hasattr(self.config.strategy, key):
                        setattr(self.config.strategy, key, value)
            elif section == "network":
                for key, value in settings.items():
                    if not hasattr(self.config.network, key):
                        msg = (
                            f"Optimization profile {profile.value} contains unknown "
                            f"network key '{key}'"
                        )
                        raise ConfigurationError(msg)
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


def get_max_peers_per_torrent_provenance() -> Optional[MaxPeersPerTorrentProvenance]:
    """Return last recorded ``max_peers_per_torrent`` resolution chain, if config was loaded here."""
    if _config_manager is None:
        return None
    return _config_manager.max_peers_per_torrent_provenance


def init_config(config_file: Optional[Union[str, Path]] = None) -> ConfigManager:
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


def reset_config() -> None:
    """Reset the global configuration manager to None.

    This is primarily used for test isolation to ensure each test
    starts with a fresh config instance.
    """
    global _config_manager
    _config_manager = None
    set_cli_session_log_level_override(None)


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
