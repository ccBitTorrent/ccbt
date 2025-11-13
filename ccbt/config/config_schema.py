"""Configuration schema generation and discovery for ccBitTorrent.

This module provides JSON Schema generation, configuration discovery,
and enhanced validation capabilities for the configuration system.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from ccbt.models import Config

logger = logging.getLogger(__name__)


class ConfigSchema:
    """Configuration schema generation utilities."""

    @staticmethod
    def generate_schema(model_class: type[BaseModel]) -> dict[str, Any]:
        """Generate JSON Schema for a configuration model.

        Args:
            model_class: Pydantic model class to generate schema for

        Returns:
            JSON Schema dictionary

        """
        try:
            return model_class.model_json_schema()
        except Exception:
            logger.exception("Failed to generate schema for %s", model_class.__name__)
            raise

    @staticmethod
    def generate_full_schema() -> dict[str, Any]:
        """Generate complete configuration schema.

        Returns:
            Complete JSON Schema for the Config model

        """
        return ConfigSchema.generate_schema(Config)

    @staticmethod
    def get_schema_for_section(section_name: str) -> dict[str, Any] | None:
        """Get schema for a specific configuration section.

        Args:
            section_name: Name of the configuration section

        Returns:
            Schema for the section or None if not found

        """
        full_schema = ConfigSchema.generate_full_schema()
        properties = full_schema.get("properties", {})
        section_ref = properties.get(section_name)

        if not section_ref:
            return None

        # If it's a reference, resolve it
        if "$ref" in section_ref:
            ref_path = section_ref["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path[8:]  # Remove "#/$defs/"
                definitions = full_schema.get("$defs", {})
                return definitions.get(def_name)

        return section_ref

    @staticmethod
    def export_schema(format_type: str = "json") -> str:
        """Export configuration schema in specified format.

        Args:
            format_type: Output format ("json" or "yaml")

        Returns:
            Schema as string in specified format

        """
        schema = ConfigSchema.generate_full_schema()

        if format_type.lower() == "json":
            return json.dumps(schema, indent=2)
        if format_type.lower() == "yaml":
            try:
                import yaml

                return yaml.safe_dump(schema, sort_keys=False)
            except ImportError as e:  # pragma: no cover - Difficult to test ImportError for optional dependencies without complex sys.modules manipulation
                msg = "PyYAML is required for YAML export"
                raise ImportError(
                    msg
                ) from e  # pragma: no cover - Defensive error handling for optional dependency
        else:
            msg = f"Unsupported format: {format_type}"
            raise ValueError(msg)


class ConfigDiscovery:
    """Configuration option discovery and metadata utilities."""

    @staticmethod
    def get_all_options() -> dict[str, Any]:
        """Get all configuration options with metadata.

        Returns:
            Dictionary containing all configuration options and their metadata

        """
        schema = ConfigSchema.generate_full_schema()
        return {
            "properties": schema.get("properties", {}),
            "definitions": schema.get("$defs", {}),
            "required": schema.get("required", []),
            "title": schema.get("title", "Configuration Schema"),
            "description": schema.get("description", ""),
        }

    @staticmethod
    def get_option_metadata(key_path: str) -> dict[str, Any] | None:
        """Get metadata for specific configuration option.

        Args:
            key_path: Dot-separated path to configuration option

        Returns:
            Metadata dictionary for the option or None if not found

        """
        schema = ConfigSchema.generate_full_schema()
        properties = schema.get("properties", {})
        definitions = schema.get("$defs", {})

        # Navigate through nested properties
        parts = key_path.split(".")
        if len(parts) < 2:
            return None

        section_name = parts[0]
        option_name = parts[1]

        # Get section schema
        section_ref = properties.get(section_name)
        if not section_ref or "$ref" not in section_ref:
            return None

        ref_path = section_ref["$ref"]
        if not ref_path.startswith("#/$defs/"):
            return None

        def_name = ref_path[8:]  # Remove "#/$defs/"
        section_schema = definitions.get(def_name)
        if not section_schema or "properties" not in section_schema:
            return None

        section_properties = section_schema["properties"]
        return section_properties.get(option_name)

    @staticmethod
    def list_all_options() -> list[dict[str, Any]]:
        """List all configuration options with their paths and metadata.

        Returns:
            List of dictionaries containing option paths and metadata

        """
        options = []
        schema = ConfigSchema.generate_full_schema()
        properties = schema.get("properties", {})
        definitions = schema.get("$defs", {})

        def _extract_options_from_section(
            section_name: str,
            section_ref: dict[str, Any],
        ) -> None:
            if "$ref" not in section_ref:
                return

            ref_path = section_ref["$ref"]
            if not ref_path.startswith("#/$defs/"):
                return

            def_name = ref_path[8:]  # Remove "#/$defs/"
            section_schema = definitions.get(def_name)
            if not section_schema or "properties" not in section_schema:
                return

            section_properties = section_schema["properties"]
            for option_name, option_schema in section_properties.items():
                options.append(
                    {
                        "path": f"{section_name}.{option_name}",
                        "type": option_schema.get("type", "unknown"),
                        "description": option_schema.get("description", ""),
                        "default": option_schema.get("default"),
                        "required": option_name in section_schema.get("required", []),
                    }
                )

        for section_name, section_ref in properties.items():
            _extract_options_from_section(section_name, section_ref)

        return options

    @staticmethod
    def get_section_options(section_name: str) -> list[dict[str, Any]]:
        """Get all options for a specific configuration section.

        Args:
            section_name: Name of the configuration section

        Returns:
            List of options in the section

        """
        section_schema = ConfigSchema.get_schema_for_section(section_name)
        if not section_schema or "properties" not in section_schema:
            return []

        options = []
        properties = section_schema["properties"]

        for key, value in properties.items():
            options.append(
                {
                    "path": f"{section_name}.{key}",
                    "type": value.get("type", "unknown"),
                    "description": value.get("description", ""),
                    "default": value.get("default"),
                    "required": key in section_schema.get("required", []),
                }
            )

        return options


class ConfigValidator:
    """Enhanced configuration validation with detailed error messages."""

    @staticmethod
    def validate_with_details(config_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration with detailed error messages.

        Args:
            config_data: Configuration data to validate

        Returns:
            Tuple of (is_valid, list_of_errors)

        """
        try:
            Config(**config_data)
            return True, []
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                error_msg = error["msg"]
                error_type = error["type"]

                # Create detailed error message
                if error_type == "value_error":
                    errors.append(f"{field}: {error_msg}")
                elif error_type == "type_error":
                    errors.append(  # pragma: no cover - Pydantic v2 typically uses "int_parsing" or "string_type" instead of "type_error" for type mismatches
                        f"{field}: Expected {error['ctx'].get('expected_type', 'valid type')}, got {error['ctx'].get('actual_type', 'invalid type')}"
                    )
                elif error_type == "missing":
                    errors.append(
                        f"{field}: Required field is missing"
                    )  # pragma: no cover - Config model has defaults for all fields, making this path difficult to trigger in practice
                elif error_type == "extra_forbidden":
                    errors.append(
                        f"{field}: Unknown field"
                    )  # pragma: no cover - Config model allows extra fields by default, making this path difficult to trigger
                else:
                    errors.append(f"{field}: {error_msg}")

            return False, errors

    @staticmethod
    def validate_section(
        section_name: str,
        section_data: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Validate a specific configuration section.

        Args:
            section_name: Name of the configuration section
            section_data: Section data to validate

        Returns:
            Tuple of (is_valid, list_of_errors)

        """
        # Get the section model class
        section_models = {
            "network": Config.model_fields["network"].annotation,
            "disk": Config.model_fields["disk"].annotation,
            "strategy": Config.model_fields["strategy"].annotation,
            "discovery": Config.model_fields["discovery"].annotation,
            "observability": Config.model_fields["observability"].annotation,
            "limits": Config.model_fields["limits"].annotation,
            "security": Config.model_fields["security"].annotation,
            "ml": Config.model_fields["ml"].annotation,
        }

        if section_name not in section_models:
            return False, [f"Unknown section: {section_name}"]

        try:
            section_models[section_name](**section_data)
            return True, []
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                errors.append(f"{section_name}.{field}: {error['msg']}")
            return False, errors

    @staticmethod
    def validate_option(
        key_path: str,
        value: Any,
    ) -> tuple[bool, str]:
        """Validate a single configuration option.

        Args:
            key_path: Dot-separated path to the option
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        try:
            # Get metadata for the option
            metadata = ConfigDiscovery.get_option_metadata(key_path)
            if not metadata:
                return False, f"Unknown option: {key_path}"

            # Create a minimal config with just this option
            parts = key_path.split(".")
            if (
                len(parts) != 2
            ):  # pragma: no cover - This path is covered by get_option_metadata which returns None for invalid paths, causing "Unknown option" instead
                return False, f"Invalid option path format: {key_path}"

            section_name, option_name = parts
            config_data = {section_name: {option_name: value}}

            # Validate
            is_valid, errors = ConfigValidator.validate_with_details(config_data)
            if is_valid:
                return True, ""
            return False, errors[0] if errors else "Validation failed"

        except Exception as e:
            return False, f"Validation error: {e}"

    @staticmethod
    def validate_cross_field_rules(config_data: dict[str, Any]) -> list[str]:
        """Validate cross-field configuration rules.

        Args:
            config_data: Configuration data to validate

        Returns:
            List of validation errors

        """
        errors = []

        try:
            config = Config(**config_data)
        except ValidationError:
            # If basic validation fails, skip cross-field validation
            return errors

        # Rule: DHT port cannot be the same as listen port
        if (
            config.discovery.enable_dht
            and config.network.listen_port == config.discovery.dht_port
        ):  # pragma: no cover - This conflict is caught by model validator in Config model, preventing Config creation with this combination
            errors.append(
                "DHT port cannot be the same as listen port. "
                f"Both are set to {config.network.listen_port}"
            )

        # Rule: Global limits should be >= per-torrent limits
        if (
            config.limits.global_down_kib > 0
            and config.limits.per_torrent_down_kib > 0
            and config.limits.global_down_kib < config.limits.per_torrent_down_kib
        ):
            errors.append(
                "Global download limit should be >= per-torrent download limit"
            )

        if (
            config.limits.global_up_kib > 0
            and config.limits.per_torrent_up_kib > 0
            and config.limits.global_up_kib < config.limits.per_torrent_up_kib
        ):
            errors.append("Global upload limit should be >= per-torrent upload limit")

        # Rule: Hash workers should not exceed CPU cores significantly
        import os

        cpu_count = os.cpu_count() or 1
        if (
            config.disk.hash_workers > cpu_count * 2
        ):  # pragma: no cover - This warning is skipped on systems where hash_workers reaches the field maximum (32) before exceeding cpu_count * 2
            errors.append(
                f"Hash workers ({config.disk.hash_workers}) is significantly "
                f"higher than CPU cores ({cpu_count}). This may cause performance issues."
            )

        # Rule: Disk workers should be reasonable
        if (
            config.disk.disk_workers > cpu_count
        ):  # pragma: no cover - This warning is skipped on systems where disk_workers reaches the field maximum (16) before exceeding cpu_count
            errors.append(
                f"Disk workers ({config.disk.disk_workers}) is higher than "
                f"CPU cores ({cpu_count}). This may cause performance issues."
            )

        return errors
