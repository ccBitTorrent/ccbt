"""Configuration templates and profiles for ccBitTorrent.

This module provides predefined configuration templates and profiles
for different use cases and system types.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from ccbt.models import Config

logger = logging.getLogger(__name__)


class ConfigTemplates:
    """Configuration templates for different use cases."""

    TEMPLATES: ClassVar[dict[str, dict[str, Any]]] = {
        "performance": {
            "name": "Performance",
            "description": "High-performance settings optimized for maximum throughput",
            "config": {
                "network": {
                    "max_global_peers": 500,
                    "max_peers_per_torrent": 50,
                    "pipeline_depth": 8,
                    "block_size_kib": 32,
                    "socket_rcvbuf_kib": 1024,
                    "socket_sndbuf_kib": 1024,
                    "tcp_nodelay": True,
                    "max_connections_per_peer": 4,
                    "connection_timeout": 10,
                    "handshake_timeout": 10,
                    "keep_alive_interval": 30,
                    "peer_timeout": 60,
                    "max_upload_slots": 8,
                    "unchoke_interval": 10,
                    "optimistic_unchoke_interval": 30,
                },
                "disk": {
                    "hash_workers": 8,
                    "disk_workers": 4,
                    "hash_queue_size": 200,
                    "disk_queue_size": 500,
                    "write_batch_kib": 1024,
                    "read_ahead_kib": 1024,
                    "use_mmap": True,
                    "preallocate": "full",
                    "checkpoint_enabled": True,
                    "checkpoint_interval": 30,
                },
                "strategy": {
                    "piece_selection": "rarest_first",
                    "endgame_threshold": 0.95,
                    "endgame_duplicates": 2,
                    "streaming_mode": False,
                    "sequential_download": False,
                    "first_piece_priority": False,
                },
                "discovery": {
                    "enable_dht": True,
                    "dht_port": 6882,
                    "enable_pex": True,
                    "tracker_announce_interval": 900,
                    "tracker_min_interval": 60,
                    "tracker_max_interval": 3600,
                    "tracker_timeout": 15,
                    "tracker_connect_timeout": 10,
                    "tracker_connection_limit": 50,
                    "tracker_connections_per_host": 2,
                    "dht_bootstrap_nodes": [
                        "router.bittorrent.com:6881",
                        "dht.transmissionbt.com:6881",
                        "router.utorrent.com:6881",
                    ],
                },
                "limits": {
                    "global_down_kib": 0,  # Unlimited
                    "global_up_kib": 0,  # Unlimited
                    "per_torrent_down_kib": 0,  # Unlimited
                    "per_torrent_up_kib": 0,  # Unlimited
                    "scheduler_slice_ms": 100,
                },
                "observability": {
                    "log_level": "INFO",
                    "log_file": None,
                    "enable_metrics": True,
                    "metrics_port": 9090,
                    "enable_peer_tracing": False,
                    "peer_trace_file": None,
                    "enable_profiling": False,
                    "profiling_port": 6060,
                },
                "security": {
                    "enable_encryption": True,
                    "encryption_preference": "prefer_encrypted",
                    "validate_peers": True,
                    "peer_validation_timeout": 30,
                    "rate_limit_enabled": True,
                    "max_connections_per_ip": 5,
                    "max_connections_per_subnet": 20,
                },
                "ml": {
                    "peer_selection_enabled": True,
                    "piece_prediction_enabled": True,
                    "adaptive_limiter_enabled": True,
                    "peer_scoring_alpha": 0.7,
                    "piece_prediction_threshold": 0.8,
                    "limiter_update_interval": 60,
                },
            },
        },
        "low_resource": {
            "name": "Low Resource",
            "description": "Minimal resource usage for low-power systems",
            "config": {
                "network": {
                    "max_global_peers": 50,
                    "max_peers_per_torrent": 10,
                    "pipeline_depth": 2,
                    "block_size_kib": 16,
                    "socket_rcvbuf_kib": 64,
                    "socket_sndbuf_kib": 64,
                    "tcp_nodelay": False,
                    "max_connections_per_peer": 1,
                    "connection_timeout": 15,
                    "handshake_timeout": 15,
                    "keep_alive_interval": 60,
                    "peer_timeout": 120,
                    "max_upload_slots": 2,
                    "unchoke_interval": 30,
                    "optimistic_unchoke_interval": 60,
                },
                "disk": {
                    "hash_workers": 2,
                    "disk_workers": 1,
                    "hash_queue_size": 50,
                    "disk_queue_size": 100,
                    "write_batch_kib": 256,
                    "read_ahead_kib": 512,
                    "use_mmap": False,
                    "preallocate": "none",
                    "checkpoint_enabled": False,
                    "checkpoint_interval": 300,
                },
                "strategy": {
                    "piece_selection": "sequential",
                    "endgame_threshold": 0.9,
                    "endgame_duplicates": 1,
                    "streaming_mode": True,
                    "sequential_download": True,
                    "first_piece_priority": True,
                },
                "discovery": {
                    "enable_dht": False,
                    "dht_port": 6882,
                    "enable_pex": True,
                    "tracker_announce_interval": 1800,
                    "tracker_min_interval": 300,
                    "tracker_max_interval": 7200,
                    "tracker_timeout": 30,
                    "tracker_connect_timeout": 20,
                    "tracker_connection_limit": 10,
                    "tracker_connections_per_host": 1,
                    "dht_bootstrap_nodes": [],
                },
                "limits": {
                    "global_down_kib": 100,  # 100 KiB/s
                    "global_up_kib": 50,  # 50 KiB/s
                    "per_torrent_down_kib": 50,  # 50 KiB/s
                    "per_torrent_up_kib": 25,  # 25 KiB/s
                    "scheduler_slice_ms": 200,
                },
                "observability": {
                    "log_level": "WARNING",
                    "log_file": None,
                    "enable_metrics": False,
                    "metrics_port": 9090,
                    "enable_peer_tracing": False,
                    "peer_trace_file": None,
                    "enable_profiling": False,
                    "profiling_port": 6060,
                },
                "security": {
                    "enable_encryption": False,
                    "encryption_preference": "allow_plaintext",
                    "validate_peers": False,
                    "peer_validation_timeout": 60,
                    "rate_limit_enabled": True,
                    "max_connections_per_ip": 2,
                    "max_connections_per_subnet": 5,
                },
                "ml": {
                    "peer_selection_enabled": False,
                    "piece_prediction_enabled": False,
                    "adaptive_limiter_enabled": False,
                    "peer_scoring_alpha": 0.5,
                    "piece_prediction_threshold": 0.5,
                    "limiter_update_interval": 300,
                },
            },
        },
        "streaming": {
            "name": "Streaming",
            "description": "Optimized for streaming and sequential download",
            "config": {
                "network": {
                    "max_global_peers": 200,
                    "max_peers_per_torrent": 30,
                    "pipeline_depth": 4,
                    "block_size_kib": 32,
                    "socket_rcvbuf_kib": 512,
                    "socket_sndbuf_kib": 512,
                    "tcp_nodelay": True,
                    "max_connections_per_peer": 2,
                    "connection_timeout": 10,
                    "handshake_timeout": 10,
                    "keep_alive_interval": 30,
                    "peer_timeout": 60,
                    "max_upload_slots": 4,
                    "unchoke_interval": 15,
                    "optimistic_unchoke_interval": 30,
                },
                "disk": {
                    "hash_workers": 4,
                    "disk_workers": 2,
                    "hash_queue_size": 100,
                    "disk_queue_size": 300,
                    "write_batch_kib": 512,
                    "read_ahead_kib": 1024,
                    "use_mmap": True,
                    "preallocate": "sparse",
                    "checkpoint_enabled": True,
                    "checkpoint_interval": 60,
                },
                "strategy": {
                    "piece_selection": "sequential",
                    "endgame_threshold": 0.8,
                    "endgame_duplicates": 1,
                    "streaming_mode": True,
                    "sequential_download": True,
                    "first_piece_priority": True,
                },
                "discovery": {
                    "enable_dht": True,
                    "dht_port": 6882,
                    "enable_pex": True,
                    "tracker_announce_interval": 900,
                    "tracker_min_interval": 60,
                    "tracker_max_interval": 3600,
                    "tracker_timeout": 15,
                    "tracker_connect_timeout": 10,
                    "tracker_connection_limit": 30,
                    "tracker_connections_per_host": 2,
                    "dht_bootstrap_nodes": [
                        "router.bittorrent.com:6881",
                        "dht.transmissionbt.com:6881",
                    ],
                },
                "limits": {
                    "global_down_kib": 0,  # Unlimited
                    "global_up_kib": 0,  # Unlimited
                    "per_torrent_down_kib": 0,  # Unlimited
                    "per_torrent_up_kib": 0,  # Unlimited
                    "scheduler_slice_ms": 50,
                },
                "observability": {
                    "log_level": "INFO",
                    "log_file": None,
                    "enable_metrics": True,
                    "metrics_port": 9090,
                    "enable_peer_tracing": False,
                    "peer_trace_file": None,
                    "enable_profiling": False,
                    "profiling_port": 6060,
                },
                "security": {
                    "enable_encryption": True,
                    "encryption_preference": "prefer_encrypted",
                    "validate_peers": True,
                    "peer_validation_timeout": 30,
                    "rate_limit_enabled": True,
                    "max_connections_per_ip": 3,
                    "max_connections_per_subnet": 10,
                },
                "ml": {
                    "peer_selection_enabled": True,
                    "piece_prediction_enabled": False,  # Not needed for streaming
                    "adaptive_limiter_enabled": True,
                    "peer_scoring_alpha": 0.6,
                    "piece_prediction_threshold": 0.5,
                    "limiter_update_interval": 120,
                },
            },
        },
        "seeding": {
            "name": "Seeding",
            "description": "Optimized for seeding and sharing files",
            "config": {
                "network": {
                    "max_global_peers": 300,
                    "max_peers_per_torrent": 40,
                    "pipeline_depth": 6,
                    "block_size_kib": 32,
                    "socket_rcvbuf_kib": 512,
                    "socket_sndbuf_kib": 1024,  # Higher upload buffer
                    "tcp_nodelay": True,
                    "max_connections_per_peer": 3,
                    "connection_timeout": 10,
                    "handshake_timeout": 10,
                    "keep_alive_interval": 30,
                    "peer_timeout": 60,
                    "max_upload_slots": 12,  # More upload slots
                    "unchoke_interval": 10,
                    "optimistic_unchoke_interval": 30,
                },
                "disk": {
                    "hash_workers": 6,
                    "disk_workers": 3,
                    "hash_queue_size": 150,
                    "disk_queue_size": 400,
                    "write_batch_kib": 512,
                    "read_ahead_kib": 1024,
                    "use_mmap": True,
                    "preallocate": "full",
                    "checkpoint_enabled": True,
                    "checkpoint_interval": 60,
                },
                "strategy": {
                    "piece_selection": "rarest_first",
                    "endgame_threshold": 0.95,
                    "endgame_duplicates": 2,
                    "streaming_mode": False,
                    "sequential_download": False,
                    "first_piece_priority": False,
                },
                "discovery": {
                    "enable_dht": True,
                    "dht_port": 6882,
                    "enable_pex": True,
                    "tracker_announce_interval": 1800,  # Longer announce interval
                    "tracker_min_interval": 300,
                    "tracker_max_interval": 7200,
                    "tracker_timeout": 15,
                    "tracker_connect_timeout": 10,
                    "tracker_connection_limit": 40,
                    "tracker_connections_per_host": 2,
                    "dht_bootstrap_nodes": [
                        "router.bittorrent.com:6881",
                        "dht.transmissionbt.com:6881",
                        "router.utorrent.com:6881",
                    ],
                },
                "limits": {
                    "global_down_kib": 0,  # Unlimited
                    "global_up_kib": 0,  # Unlimited
                    "per_torrent_down_kib": 0,  # Unlimited
                    "per_torrent_up_kib": 0,  # Unlimited
                    "scheduler_slice_ms": 100,
                },
                "observability": {
                    "log_level": "INFO",
                    "log_file": None,
                    "enable_metrics": True,
                    "metrics_port": 9090,
                    "enable_peer_tracing": False,
                    "peer_trace_file": None,
                    "enable_profiling": False,
                    "profiling_port": 6060,
                },
                "security": {
                    "enable_encryption": True,
                    "encryption_preference": "prefer_encrypted",
                    "validate_peers": True,
                    "peer_validation_timeout": 30,
                    "rate_limit_enabled": True,
                    "max_connections_per_ip": 4,
                    "max_connections_per_subnet": 15,
                },
                "ml": {
                    "peer_selection_enabled": True,
                    "piece_prediction_enabled": True,
                    "adaptive_limiter_enabled": True,
                    "peer_scoring_alpha": 0.8,  # Higher weight for peer scoring
                    "piece_prediction_threshold": 0.9,
                    "limiter_update_interval": 60,
                },
            },
        },
    }

    @staticmethod
    def list_templates() -> list[dict[str, Any]]:
        """List all available configuration templates.

        Returns:
            List of template information dictionaries
        """
        return [
            {
                "name": template["name"],
                "description": template["description"],
                "key": key,
            }
            for key, template in ConfigTemplates.TEMPLATES.items()
        ]

    @staticmethod
    def get_template(template_name: str) -> dict[str, Any] | None:
        """Get a specific configuration template.

        Args:
            template_name: Name of the template

        Returns:
            Template configuration or None if not found
        """
        template = ConfigTemplates.TEMPLATES.get(template_name)
        if template:
            return template["config"]
        return None

    @staticmethod
    def apply_template(
        base_config: dict[str, Any],
        template_name: str,
        merge_strategy: str = "deep",
    ) -> dict[str, Any]:
        """Apply a configuration template to a base configuration.

        Args:
            base_config: Base configuration to apply template to
            template_name: Name of the template to apply
            merge_strategy: Merge strategy ("deep", "shallow", "replace")

        Returns:
            Merged configuration

        Raises:
            ValueError: If template not found or invalid merge strategy
        """
        template_config = ConfigTemplates.get_template(template_name)
        if not template_config:
            msg = f"Template '{template_name}' not found"
            raise ValueError(msg)

        if merge_strategy == "deep":
            return ConfigTemplates._deep_merge(base_config, template_config)
        if merge_strategy == "shallow":
            return {**base_config, **template_config}
        if merge_strategy == "replace":
            return template_config
        msg = f"Invalid merge strategy: {merge_strategy}"
        raise ValueError(msg)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigTemplates._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def validate_template(template_name: str) -> tuple[bool, list[str]]:
        """Validate a configuration template.

        Args:
            template_name: Name of the template to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        template_config = ConfigTemplates.get_template(template_name)
        if not template_config:
            return False, [f"Template '{template_name}' not found"]

        try:
            Config(**template_config)
            return True, []
        except Exception as e:
            return False, [f"Template validation error: {e}"]

    @staticmethod
    def export_template(template_name: str, format_type: str = "json") -> str:
        """Export a template in specified format.

        Args:
            template_name: Name of the template
            format_type: Output format ("json" or "yaml")

        Returns:
            Template as string in specified format

        Raises:
            ValueError: If template not found or invalid format
        """
        template_config = ConfigTemplates.get_template(template_name)
        if not template_config:
            msg = f"Template '{template_name}' not found"
            raise ValueError(msg)

        if format_type.lower() == "json":
            return json.dumps(template_config, indent=2)
        if format_type.lower() == "yaml":
            try:
                import yaml  # type: ignore[import-untyped]

                return yaml.safe_dump(template_config, sort_keys=False)
            except ImportError as e:
                msg = "PyYAML is required for YAML export"
                raise ImportError(msg) from e
        else:
            msg = f"Unsupported format: {format_type}"
            raise ValueError(msg)


class ConfigProfiles:
    """Configuration profiles for different system types."""

    PROFILES: ClassVar[dict[str, dict[str, Any]]] = {
        "desktop": {
            "name": "Desktop",
            "description": "Balanced settings for desktop users",
            "templates": ["performance"],
            "overrides": {
                "network": {
                    "max_global_peers": 200,
                    "max_peers_per_torrent": 30,
                },
                "disk": {
                    "hash_workers": 4,
                    "disk_workers": 2,
                },
                "observability": {
                    "log_level": "INFO",
                    "enable_metrics": True,
                },
            },
        },
        "server": {
            "name": "Server",
            "description": "High-performance server settings",
            "templates": ["performance", "seeding"],
            "overrides": {
                "network": {
                    "max_global_peers": 1000,
                    "max_peers_per_torrent": 100,
                },
                "disk": {
                    "hash_workers": 16,
                    "disk_workers": 8,
                },
                "observability": {
                    "log_level": "WARNING",
                    "enable_metrics": True,
                    "enable_profiling": True,
                },
            },
        },
        "mobile": {
            "name": "Mobile",
            "description": "Low-power, conservative settings for mobile devices",
            "templates": ["low_resource"],
            "overrides": {
                "network": {
                    "max_global_peers": 30,
                    "max_peers_per_torrent": 5,
                },
                "disk": {
                    "hash_workers": 1,
                    "disk_workers": 1,
                },
                "limits": {
                    "global_down_kib": 50,  # 50 KiB/s
                    "global_up_kib": 25,  # 25 KiB/s
                },
                "observability": {
                    "log_level": "ERROR",
                    "enable_metrics": False,
                },
            },
        },
        "seedbox": {
            "name": "Seedbox",
            "description": "Optimized for dedicated seedbox",
            "templates": ["seeding", "performance"],
            "overrides": {
                "network": {
                    "max_global_peers": 2000,
                    "max_peers_per_torrent": 200,
                    "max_upload_slots": 20,
                },
                "disk": {
                    "hash_workers": 32,
                    "disk_workers": 16,
                },
                "discovery": {
                    "tracker_announce_interval": 900,
                },
                "observability": {
                    "log_level": "WARNING",
                    "enable_metrics": True,
                },
            },
        },
    }

    @staticmethod
    def list_profiles() -> list[dict[str, Any]]:
        """List all available configuration profiles.

        Returns:
            List of profile information dictionaries
        """
        return [
            {
                "name": profile["name"],
                "description": profile["description"],
                "key": key,
                "templates": profile["templates"],
            }
            for key, profile in ConfigProfiles.PROFILES.items()
        ]

    @staticmethod
    def get_profile(profile_name: str) -> dict[str, Any] | None:
        """Get a specific configuration profile.

        Args:
            profile_name: Name of the profile

        Returns:
            Profile configuration or None if not found
        """
        profile = ConfigProfiles.PROFILES.get(profile_name)
        if profile:
            return profile
        return None

    @staticmethod
    def apply_profile(
        base_config: dict[str, Any],
        profile_name: str,
    ) -> dict[str, Any]:
        """Apply a configuration profile to a base configuration.

        Args:
            base_config: Base configuration to apply profile to
            profile_name: Name of the profile to apply

        Returns:
            Profile-applied configuration

        Raises:
            ValueError: If profile not found
        """
        profile = ConfigProfiles.get_profile(profile_name)
        if not profile:
            msg = f"Profile '{profile_name}' not found"
            raise ValueError(msg)

        result = base_config.copy()

        # Apply templates in order
        for template_name in profile["templates"]:
            result = ConfigTemplates.apply_template(result, template_name)

        # Apply profile-specific overrides
        overrides = profile.get("overrides", {})
        return ConfigProfiles._deep_merge(result, overrides)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigProfiles._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def create_custom_profile(
        name: str,
        description: str,
        templates: list[str],
        overrides: dict[str, Any],
        profile_file: Path | str | None = None,
    ) -> dict[str, Any]:
        """Create a custom configuration profile.

        Args:
            name: Profile name
            description: Profile description
            templates: List of template names to apply
            overrides: Profile-specific overrides
            profile_file: Optional file to save profile to

        Returns:
            Created profile configuration

        Raises:
            ValueError: If template not found
        """
        # Validate templates
        for template_name in templates:
            if not ConfigTemplates.get_template(template_name):
                msg = f"Template '{template_name}' not found"
                raise ValueError(msg)

        profile = {
            "name": name,
            "description": description,
            "templates": templates,
            "overrides": overrides,
        }

        # Save to file if specified
        if profile_file:
            profile_path = Path(profile_file)
            profile_path.parent.mkdir(parents=True, exist_ok=True)

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)

        return profile

    @staticmethod
    def load_custom_profile(profile_file: Path | str) -> dict[str, Any]:
        """Load a custom profile from file.

        Args:
            profile_file: Path to profile file

        Returns:
            Loaded profile configuration

        Raises:
            FileNotFoundError: If profile file not found
            ValueError: If profile file is invalid
        """
        profile_path = Path(profile_file)
        if not profile_path.exists():
            msg = f"Profile file not found: {profile_path}"
            raise FileNotFoundError(msg)

        try:
            with open(profile_path, encoding="utf-8") as f:
                profile = json.load(f)

            # Validate profile structure
            required_fields = ["name", "description", "templates", "overrides"]
            for field in required_fields:
                if field not in profile:
                    msg = f"Profile missing required field: {field}"
                    raise ValueError(msg)

            return profile
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in profile file: {e}"
            raise ValueError(msg) from e

    @staticmethod
    def validate_profile(profile_name: str) -> tuple[bool, list[str]]:
        """Validate a configuration profile.

        Args:
            profile_name: Name of the profile to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        profile = ConfigProfiles.get_profile(profile_name)
        if not profile:
            return False, [f"Profile '{profile_name}' not found"]

        errors = []

        # Validate templates
        for template_name in profile["templates"]:
            is_valid, template_errors = ConfigTemplates.validate_template(template_name)
            if not is_valid:
                errors.extend(
                    [f"Template '{template_name}': {e}" for e in template_errors]
                )

        # Validate overrides
        try:
            Config(**profile["overrides"])
        except Exception as e:
            errors.append(f"Profile overrides validation error: {e}")

        return len(errors) == 0, errors
