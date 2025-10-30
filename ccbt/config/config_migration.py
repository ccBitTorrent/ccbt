"""Configuration migration system for ccBitTorrent.

This module provides version migration capabilities for configuration files,
allowing safe upgrades between different versions of the application.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from ccbt.models import Config

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """Configuration migration system."""

    # Current configuration version
    CURRENT_VERSION = "1.0.0"

    # Migration registry: version -> migration function
    MIGRATIONS: ClassVar[dict[str, str]] = {
        "0.9.0": "_migrate_0_9_0_to_1_0_0",
        "0.8.0": "_migrate_0_8_0_to_1_0_0",
    }

    @staticmethod
    def detect_version(config_data: dict[str, Any]) -> str:
        """Detect configuration version from data.

        Args:
            config_data: Configuration data

        Returns:
            Detected version string
        """
        # Check for explicit version field
        if "_version" in config_data:
            return config_data["_version"]

        # Check for version in metadata
        if "metadata" in config_data and "version" in config_data["metadata"]:
            return config_data["metadata"]["version"]

        # Detect version based on structure
        if "limits" in config_data:
            return "1.0.0"  # Current version
        if "global_down_kib" in config_data.get("network", {}):
            return "0.9.0"  # Legacy version with limits in network
        return "0.8.0"  # Very old version

    @staticmethod
    def migrate_config(
        config_data: dict[str, Any],
        target_version: str | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        """Migrate configuration to target version.

        Args:
            config_data: Configuration data to migrate
            target_version: Target version (defaults to current)

        Returns:
            Tuple of (migrated_config, migration_log)
        """
        if target_version is None:
            target_version = ConfigMigrator.CURRENT_VERSION

        current_version = ConfigMigrator.detect_version(config_data)
        migration_log = []

        if current_version == target_version:
            migration_log.append(f"Configuration already at version {target_version}")
            return config_data, migration_log

        migration_log.append(f"Migrating from {current_version} to {target_version}")

        # Create a copy to avoid modifying original
        migrated_config = config_data.copy()

        # Apply migrations in sequence
        versions_to_migrate = ConfigMigrator._get_migration_path(
            current_version, target_version
        )

        for version in versions_to_migrate:
            migration_func = ConfigMigrator.MIGRATIONS.get(version)
            if migration_func:
                migration_log.append(f"Applying migration: {migration_func}")
                migrated_config = getattr(ConfigMigrator, migration_func)(
                    migrated_config
                )
                migration_log.append(f"Migration {migration_func} completed")

        # Add version metadata
        migrated_config["_version"] = target_version
        migrated_config["_migration_log"] = migration_log

        return migrated_config, migration_log

    @staticmethod
    def _get_migration_path(from_version: str, to_version: str) -> list[str]:
        """Get migration path between versions.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            List of versions to migrate through
        """
        # Simple version comparison for now
        # In a real implementation, this would be more sophisticated
        if from_version == "0.8.0" and to_version == "1.0.0":
            return ["0.9.0", "1.0.0"]
        if from_version == "0.9.0" and to_version == "1.0.0":
            return ["0.9.0"]
        return []

    @staticmethod
    def _migrate_0_8_0_to_1_0_0(config_data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 0.8.0 to 1.0.0.

        Args:
            config_data: Configuration data

        Returns:
            Migrated configuration
        """
        migrated = config_data.copy()

        # Add missing sections with defaults
        if "limits" not in migrated:
            migrated["limits"] = {
                "global_down_kib": 0,
                "global_up_kib": 0,
                "per_torrent_down_kib": 0,
                "per_torrent_up_kib": 0,
                "scheduler_slice_ms": 100,
            }

        if "security" not in migrated:
            migrated["security"] = {
                "enable_encryption": False,
                "encryption_preference": "allow_plaintext",
                "validate_peers": True,
                "peer_validation_timeout": 30,
                "rate_limit_enabled": True,
                "max_connections_per_ip": 5,
                "max_connections_per_subnet": 20,
            }

        if "ml" not in migrated:
            migrated["ml"] = {
                "peer_selection_enabled": False,
                "piece_prediction_enabled": False,
                "adaptive_limiter_enabled": False,
                "peer_scoring_alpha": 0.5,
                "piece_prediction_threshold": 0.5,
                "limiter_update_interval": 300,
            }

        return migrated

    @staticmethod
    def _migrate_0_9_0_to_1_0_0(config_data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 0.9.0 to 1.0.0.

        Args:
            config_data: Configuration data

        Returns:
            Migrated configuration
        """
        migrated = config_data.copy()

        # Move global limits from network to limits section
        if "network" in migrated and "limits" not in migrated:
            network = migrated["network"]
            migrated["limits"] = {
                "global_down_kib": network.pop("global_down_kib", 0),
                "global_up_kib": network.pop("global_up_kib", 0),
                "per_torrent_down_kib": network.pop("per_torrent_down_kib", 0),
                "per_torrent_up_kib": network.pop("per_torrent_up_kib", 0),
                "scheduler_slice_ms": 100,
            }

        # Add missing sections with defaults
        if "security" not in migrated:
            migrated["security"] = {
                "enable_encryption": False,
                "encryption_preference": "allow_plaintext",
                "validate_peers": True,
                "peer_validation_timeout": 30,
                "rate_limit_enabled": True,
                "max_connections_per_ip": 5,
                "max_connections_per_subnet": 20,
            }

        if "ml" not in migrated:
            migrated["ml"] = {
                "peer_selection_enabled": False,
                "piece_prediction_enabled": False,
                "adaptive_limiter_enabled": False,
                "peer_scoring_alpha": 0.5,
                "piece_prediction_threshold": 0.5,
                "limiter_update_interval": 300,
            }

        return migrated

    @staticmethod
    def migrate_file(
        config_file: Path | str,
        backup: bool = True,
        target_version: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Migrate a configuration file.

        Args:
            config_file: Path to configuration file
            backup: Whether to create backup before migration
            target_version: Target version (defaults to current)

        Returns:
            Tuple of (success, migration_log)
        """
        config_path = Path(config_file)

        if not config_path.exists():
            return False, [f"Configuration file not found: {config_path}"]

        try:
            # Load configuration
            with open(config_path, encoding="utf-8") as f:
                if config_path.suffix.lower() == ".json":
                    config_data = json.load(f)
                else:
                    import toml

                    config_data = toml.load(f)

            # Create backup if requested
            if backup:
                backup_path = config_path.with_suffix(f"{config_path.suffix}.backup")
                with open(backup_path, "w", encoding="utf-8") as f:
                    if config_path.suffix.lower() == ".json":
                        json.dump(config_data, f, indent=2)
                    else:
                        toml.dump(config_data, f)

            # Migrate configuration
            migrated_config, migration_log = ConfigMigrator.migrate_config(
                config_data, target_version
            )

            # Save migrated configuration
            with open(config_path, "w", encoding="utf-8") as f:
                if config_path.suffix.lower() == ".json":
                    json.dump(migrated_config, f, indent=2)
                else:
                    toml.dump(migrated_config, f)

            migration_log.append(
                f"Configuration migrated successfully to {target_version or ConfigMigrator.CURRENT_VERSION}"
            )
            return True, migration_log

        except Exception as e:
            error_msg = f"Migration failed: {e}"
            logger.exception(error_msg)
            return False, [error_msg]

    @staticmethod
    def validate_migrated_config(config_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate migrated configuration.

        Args:
            config_data: Migrated configuration data

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            # Remove migration metadata for validation
            clean_config = config_data.copy()
            clean_config.pop("_version", None)
            clean_config.pop("_migration_log", None)

            Config(**clean_config)
            return True, []
        except Exception as e:
            return False, [f"Validation error: {e}"]

    @staticmethod
    def rollback_migration(
        config_file: Path | str,
        backup_file: Path | str | None = None,
    ) -> tuple[bool, list[str]]:
        """Rollback a migration using backup file.

        Args:
            config_file: Path to configuration file
            backup_file: Path to backup file (auto-detected if None)

        Returns:
            Tuple of (success, rollback_log)
        """
        config_path = Path(config_file)

        if backup_file is None:
            backup_path = config_path.with_suffix(f"{config_path.suffix}.backup")
        else:
            backup_path = Path(backup_file)

        if not backup_path.exists():
            return False, [f"Backup file not found: {backup_path}"]

        try:
            # Copy backup to config file
            import shutil

            shutil.copy2(backup_path, config_path)

            rollback_log = [f"Configuration rolled back from {backup_path}"]
            return True, rollback_log

        except Exception as e:
            error_msg = f"Rollback failed: {e}"
            logger.exception(error_msg)
            return False, [error_msg]

    @staticmethod
    def get_migration_history(config_data: dict[str, Any]) -> list[str]:
        """Get migration history from configuration.

        Args:
            config_data: Configuration data

        Returns:
            List of migration log entries
        """
        return config_data.get("_migration_log", [])

    @staticmethod
    def clean_migration_metadata(config_data: dict[str, Any]) -> dict[str, Any]:
        """Remove migration metadata from configuration.

        Args:
            config_data: Configuration data

        Returns:
            Cleaned configuration data
        """
        cleaned = config_data.copy()
        cleaned.pop("_version", None)
        cleaned.pop("_migration_log", None)
        return cleaned
