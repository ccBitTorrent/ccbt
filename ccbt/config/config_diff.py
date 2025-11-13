"""Configuration diff and merge system for ccBitTorrent.

This module provides configuration comparison and merge capabilities,
allowing users to see differences between configurations and merge changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigDiff:
    """Configuration difference and merge system."""

    @staticmethod
    def compare_configs(
        config1: dict[str, Any],
        config2: dict[str, Any],
        ignore_metadata: bool = True,
    ) -> dict[str, Any]:
        """Compare two configurations and generate diff.

        Args:
            config1: First configuration
            config2: Second configuration
            ignore_metadata: Whether to ignore migration metadata

        Returns:
            Dictionary containing diff information

        """
        # Clean metadata if requested
        if ignore_metadata:
            config1 = ConfigDiff._clean_metadata(config1)
            config2 = ConfigDiff._clean_metadata(config2)

        diff = {
            "added": {},
            "removed": {},
            "modified": {},
            "unchanged": {},
        }

        # Find all keys in both configs
        all_keys = set(ConfigDiff._get_all_keys(config1))
        all_keys.update(ConfigDiff._get_all_keys(config2))

        for key in all_keys:
            value1 = ConfigDiff._get_nested_value(config1, key)
            value2 = ConfigDiff._get_nested_value(config2, key)

            if value1 is None and value2 is not None:
                # Added
                diff["added"][key] = value2
            elif value1 is not None and value2 is None:
                # Removed
                diff["removed"][key] = value1
            elif value1 != value2:
                # Modified
                diff["modified"][key] = {
                    "old": value1,
                    "new": value2,
                }
            else:
                # Unchanged
                diff["unchanged"][key] = value1

        return diff

    @staticmethod
    def merge_configs(
        base_config: dict[str, Any],
        *configs: dict[str, Any],
        strategy: str = "deep",
        conflict_resolution: str = "last_wins",
    ) -> tuple[dict[str, Any], list[str]]:
        """Merge multiple configurations.

        Args:
            base_config: Base configuration
            *configs: Configurations to merge
            strategy: Merge strategy ("deep", "shallow")
            conflict_resolution: Conflict resolution strategy ("last_wins", "first_wins", "manual")

        Returns:
            Tuple of (merged_config, conflict_log)

        """
        merged = base_config.copy()
        conflict_log = []

        for i, config in enumerate(configs):
            if strategy == "deep":
                merged, conflicts = ConfigDiff._deep_merge_with_conflicts(
                    merged, config, conflict_resolution
                )
            else:
                merged, conflicts = ConfigDiff._shallow_merge_with_conflicts(
                    merged, config, conflict_resolution
                )

            if conflicts:
                conflict_log.extend(
                    [f"Config {i + 1}: {conflict}" for conflict in conflicts]
                )

        return merged, conflict_log

    @staticmethod
    def apply_changes(
        base_config: dict[str, Any],
        changes: dict[str, Any],
        change_types: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Apply specific changes to a configuration.

        Args:
            base_config: Base configuration
            changes: Changes to apply
            change_types: Type of each change ("add", "remove", "modify")

        Returns:
            Configuration with changes applied

        """
        if change_types is None:
            change_types = {}

        result = base_config.copy()

        for key, value in changes.items():
            change_type = change_types.get(key, "modify")

            if change_type == "add":
                ConfigDiff._set_nested_value(result, key, value)
            elif change_type == "remove":
                ConfigDiff._remove_nested_value(result, key)
            else:  # modify
                ConfigDiff._set_nested_value(result, key, value)

        return result

    @staticmethod
    def generate_diff_report(
        diff: dict[str, Any],
        format_type: str = "text",
    ) -> str:
        """Generate a human-readable diff report.

        Args:
            diff: Diff dictionary from compare_configs
            format_type: Output format ("text", "json", "yaml")

        Returns:
            Formatted diff report

        """
        if format_type == "text":
            return ConfigDiff._generate_text_report(diff)
        if format_type == "json":
            return json.dumps(diff, indent=2)
        if format_type == "yaml":
            try:
                import yaml

                return yaml.safe_dump(diff, sort_keys=False)
            except ImportError as e:
                msg = "PyYAML is required for YAML output"
                raise ImportError(msg) from e
        else:
            msg = f"Unsupported format: {format_type}"
            raise ValueError(msg)

    @staticmethod
    def _clean_metadata(config: dict[str, Any]) -> dict[str, Any]:
        """Remove metadata from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Cleaned configuration

        """
        cleaned = config.copy()
        cleaned.pop("_version", None)
        cleaned.pop("_migration_log", None)
        return cleaned

    @staticmethod
    def _get_all_keys(config: dict[str, Any], prefix: str = "") -> list[str]:
        """Get all keys from nested configuration.

        Args:
            config: Configuration dictionary
            prefix: Key prefix

        Returns:
            List of all keys

        """
        keys = []

        for key, value in config.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                keys.extend(ConfigDiff._get_all_keys(value, current_key))
            else:
                keys.append(current_key)

        return keys

    @staticmethod
    def _get_nested_value(config: dict[str, Any], key: str) -> Any:
        """Get value from nested configuration.

        Args:
            config: Configuration dictionary
            key: Dot-separated key path

        Returns:
            Value or None if not found

        """
        parts = key.split(".")
        current = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    @staticmethod
    def _set_nested_value(config: dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested configuration.

        Args:
            config: Configuration dictionary
            key: Dot-separated key path
            value: Value to set

        """
        parts = key.split(".")
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    @staticmethod
    def _remove_nested_value(config: dict[str, Any], key: str) -> None:
        """Remove value from nested configuration.

        Args:
            config: Configuration dictionary
            key: Dot-separated key path

        """
        parts = key.split(".")
        current = config

        for part in parts[:-1]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return

        if isinstance(current, dict) and parts[-1] in current:
            del current[parts[-1]]

    @staticmethod
    def _deep_merge_with_conflicts(
        base: dict[str, Any],
        override: dict[str, Any],
        conflict_resolution: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Deep merge with conflict detection.

        Args:
            base: Base configuration
            override: Override configuration
            conflict_resolution: Conflict resolution strategy

        Returns:
            Tuple of (merged_config, conflict_list)

        """
        result = base.copy()
        conflicts = []

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursive merge
                merged, sub_conflicts = ConfigDiff._deep_merge_with_conflicts(
                    result[key], value, conflict_resolution
                )
                result[key] = merged
                conflicts.extend(sub_conflicts)
            elif key in result and result[key] != value:
                # Conflict detected
                conflict_msg = f"Conflict at '{key}': '{result[key]}' vs '{value}'"
                conflicts.append(conflict_msg)

                if conflict_resolution == "last_wins":
                    result[key] = value
                elif conflict_resolution == "first_wins":
                    pass  # Keep base value (already in result)
                # Manual resolution - use callback if provided, otherwise keep base value
                # Check if ConfigDiff class has a conflict resolver callback set
                # Note: This requires setting ConfigDiff._conflict_resolver as a class attribute
                # For static method usage, manual resolution means keeping base value
                elif (
                    hasattr(ConfigDiff, "_conflict_resolver")
                    and ConfigDiff._conflict_resolver
                ):
                    try:
                        resolved_value = ConfigDiff._conflict_resolver(
                            key, result[key], value
                        )
                        if resolved_value is not None:
                            result[key] = resolved_value
                        # If resolver returns None, keep base value (already in result)
                    except Exception as e:
                        logger.warning(
                            "Error in conflict resolver for key '%s': %s", key, e
                        )
                        # On error, keep base value (already in result)
                else:
                    # No resolver available, keep base value (already in result)
                    pass
            else:
                # No conflict
                result[key] = value

        return result, conflicts

    @staticmethod
    def _shallow_merge_with_conflicts(
        base: dict[str, Any],
        override: dict[str, Any],
        conflict_resolution: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Shallow merge with conflict detection.

        Args:
            base: Base configuration
            override: Override configuration
            conflict_resolution: Conflict resolution strategy

        Returns:
            Tuple of (merged_config, conflict_list)

        """
        result = base.copy()
        conflicts = []

        for key, value in override.items():
            if key in result and result[key] != value:
                # Conflict detected
                conflict_msg = f"Conflict at '{key}': '{result[key]}' vs '{value}'"
                conflicts.append(conflict_msg)

                if conflict_resolution == "last_wins":
                    result[key] = value
                elif conflict_resolution == "first_wins":
                    pass  # Keep base value
                else:
                    # Manual resolution - keep base value for now
                    pass  # pragma: no cover - Manual resolution strategy in shallow merge, tested via deep merge with manual resolution
            else:
                # No conflict
                result[key] = value

        return result, conflicts

    @staticmethod
    def _generate_text_report(diff: dict[str, Any]) -> str:
        """Generate text format diff report.

        Args:
            diff: Diff dictionary

        Returns:
            Text report

        """
        report = []

        # Added items
        if diff["added"]:
            report.append("=== ADDED ===")
            for key, value in diff["added"].items():
                report.append(f"+ {key}: {value}")
            report.append("")

        # Removed items
        if diff["removed"]:
            report.append("=== REMOVED ===")
            for key, value in diff["removed"].items():
                report.append(f"- {key}: {value}")
            report.append("")

        # Modified items
        if diff["modified"]:
            report.append("=== MODIFIED ===")
            for key, change in diff["modified"].items():
                report.append(f"~ {key}:")
                report.append(f"  - {change['old']}")
                report.append(f"  + {change['new']}")
            report.append("")

        # Summary
        total_changes = (
            len(diff["added"]) + len(diff["removed"]) + len(diff["modified"])
        )
        report.append(
            f"Summary: {total_changes} changes ({len(diff['added'])} added, {len(diff['removed'])} removed, {len(diff['modified'])} modified)"
        )

        return "\n".join(report)

    @staticmethod
    def compare_files(
        file1: Path | str,
        file2: Path | str,
        ignore_metadata: bool = True,
    ) -> dict[str, Any]:
        """Compare two configuration files.

        Args:
            file1: First configuration file
            file2: Second configuration file
            ignore_metadata: Whether to ignore migration metadata

        Returns:
            Diff dictionary

        """
        config1 = ConfigDiff._load_config_file(Path(file1))
        config2 = ConfigDiff._load_config_file(Path(file2))

        return ConfigDiff.compare_configs(config1, config2, ignore_metadata)

    @staticmethod
    def _load_config_file(config_path: Path) -> dict[str, Any]:
        """Load configuration file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration data

        """
        with open(config_path, encoding="utf-8") as f:
            if config_path.suffix.lower() == ".json":
                return json.load(f)
            import toml

            return toml.load(f)
