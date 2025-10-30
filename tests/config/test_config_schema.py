"""Tests for configuration schema generation and validation."""

from __future__ import annotations

import json
import pytest

from ccbt.config.config_schema import ConfigSchema, ConfigDiscovery, ConfigValidator
from ccbt.models import Config, NetworkConfig, DiskConfig, StrategyConfig


class TestConfigSchema:
    """Test configuration schema generation."""

    def test_generate_schema_for_config(self):
        """Test schema generation for main Config model."""
        schema = ConfigSchema.generate_schema(Config)
        
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "type" in schema
        assert schema["type"] == "object"
        
        # Check that all main sections are present
        properties = schema["properties"]
        expected_sections = ["network", "disk", "strategy", "discovery", "observability", "limits", "security", "ml"]
        for section in expected_sections:
            assert section in properties

    def test_generate_schema_for_section(self):
        """Test schema generation for individual sections."""
        schema = ConfigSchema.generate_schema(NetworkConfig)
        
        assert isinstance(schema, dict)
        assert "properties" in schema
        
        # Check for some key network properties
        properties = schema["properties"]
        assert "listen_port" in properties
        assert "max_global_peers" in properties
        assert "enable_ipv6" in properties

    def test_generate_full_schema(self):
        """Test full schema generation."""
        schema = ConfigSchema.generate_full_schema()
        
        assert isinstance(schema, dict)
        assert "properties" in schema
        
        # Verify schema structure
        properties = schema["properties"]
        assert "network" in properties
        assert "disk" in properties
        assert "strategy" in properties

    def test_get_schema_for_section(self):
        """Test getting schema for specific section."""
        schema = ConfigSchema.get_schema_for_section("network")
        
        assert schema is not None
        # The schema should be a reference to the definition
        assert "$ref" in schema or "properties" in schema
        
        # If it's a reference, it should point to NetworkConfig
        if "$ref" in schema:
            assert "NetworkConfig" in schema["$ref"]
        else:
            # If it's the actual schema, check for network-specific properties
            properties = schema["properties"]
            assert "listen_port" in properties
            assert "max_global_peers" in properties

    def test_get_schema_for_nonexistent_section(self):
        """Test getting schema for non-existent section."""
        schema = ConfigSchema.get_schema_for_section("nonexistent")
        assert schema is None

    def test_export_schema_json(self):
        """Test schema export in JSON format."""
        schema_str = ConfigSchema.export_schema("json")
        
        assert isinstance(schema_str, str)
        
        # Parse back to verify it's valid JSON
        schema = json.loads(schema_str)
        assert "properties" in schema

    def test_export_schema_yaml(self):
        """Test schema export in YAML format."""
        try:
            schema_str = ConfigSchema.export_schema("yaml")
            assert isinstance(schema_str, str)
            assert "properties:" in schema_str
        except ImportError:
            pytest.skip("PyYAML not available")

    def test_export_schema_invalid_format(self):
        """Test schema export with invalid format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            ConfigSchema.export_schema("invalid")


class TestConfigDiscovery:
    """Test configuration discovery functionality."""

    def test_get_all_options(self):
        """Test getting all configuration options."""
        options = ConfigDiscovery.get_all_options()
        
        assert isinstance(options, dict)
        assert "properties" in options
        assert "definitions" in options
        assert "required" in options
        
        # Check that main sections are present
        properties = options["properties"]
        assert "network" in properties
        assert "disk" in properties

    def test_get_option_metadata_existing(self):
        """Test getting metadata for existing option."""
        metadata = ConfigDiscovery.get_option_metadata("network.listen_port")
        
        assert metadata is not None
        assert isinstance(metadata, dict)
        assert "type" in metadata

    def test_get_option_metadata_nonexistent(self):
        """Test getting metadata for non-existent option."""
        metadata = ConfigDiscovery.get_option_metadata("nonexistent.option")
        assert metadata is None

    def test_list_all_options(self):
        """Test listing all configuration options."""
        options = ConfigDiscovery.list_all_options()
        
        assert isinstance(options, list)
        assert len(options) > 0
        
        # Check structure of option entries
        for option in options:
            assert "path" in option
            assert "type" in option
            assert "description" in option
            assert isinstance(option["path"], str)
            assert isinstance(option["type"], str)

    def test_get_section_options(self):
        """Test getting options for specific section."""
        options = ConfigDiscovery.get_section_options("network")
        
        assert isinstance(options, list)
        assert len(options) > 0
        
        # Check that all options have network prefix
        for option in options:
            assert option["path"].startswith("network.")
        assert any(opt["path"] == "network.listen_port" for opt in options)

    def test_get_section_options_nonexistent(self):
        """Test getting options for non-existent section."""
        options = ConfigDiscovery.get_section_options("nonexistent")
        assert options == []


class TestConfigValidator:
    """Test configuration validation functionality."""

    def test_validate_with_details_valid_config(self):
        """Test validation with valid configuration."""
        config_data = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 200,
            },
            "disk": {
                "hash_workers": 4,
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        
        assert is_valid
        assert errors == []

    def test_validate_with_details_invalid_config(self):
        """Test validation with invalid configuration."""
        config_data = {
            "network": {
                "listen_port": "invalid",  # Should be int
                "max_global_peers": -1,    # Should be positive
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        
        assert not is_valid
        assert len(errors) > 0
        assert any("listen_port" in error for error in errors)

    def test_validate_section_valid(self):
        """Test section validation with valid data."""
        section_data = {
            "listen_port": 6881,
            "max_global_peers": 200,
            "enable_ipv6": True,
        }
        
        is_valid, errors = ConfigValidator.validate_section("network", section_data)
        
        assert is_valid
        assert errors == []

    def test_validate_section_invalid(self):
        """Test section validation with invalid data."""
        section_data = {
            "listen_port": "invalid",  # Should be int
            "max_global_peers": -1,    # Should be positive
        }
        
        is_valid, errors = ConfigValidator.validate_section("network", section_data)
        
        assert not is_valid
        assert len(errors) > 0

    def test_validate_section_nonexistent(self):
        """Test section validation with non-existent section."""
        section_data = {"some_field": "value"}
        
        is_valid, errors = ConfigValidator.validate_section("nonexistent", section_data)
        
        assert not is_valid
        assert "Unknown section" in errors[0]

    def test_validate_option_valid(self):
        """Test single option validation with valid value."""
        is_valid, error = ConfigValidator.validate_option("network.listen_port", 6881)
        
        assert is_valid
        assert error == ""

    def test_validate_option_invalid(self):
        """Test single option validation with invalid value."""
        is_valid, error = ConfigValidator.validate_option("network.listen_port", "invalid")
        
        assert not is_valid
        assert "listen_port" in error

    def test_validate_option_nonexistent(self):
        """Test single option validation with non-existent option."""
        is_valid, error = ConfigValidator.validate_option("nonexistent.option", "value")
        
        assert not is_valid
        assert "Unknown option" in error

    def test_validate_cross_field_rules_valid(self):
        """Test cross-field validation with valid configuration."""
        config_data = {
            "network": {"listen_port": 6881},
            "discovery": {"enable_dht": True, "dht_port": 6882},
            "limits": {
                "global_down_kib": 1000,
                "per_torrent_down_kib": 500,
                "global_up_kib": 1000,
                "per_torrent_up_kib": 500,
            },
            "disk": {"hash_workers": 4, "disk_workers": 2},
        }
        
        errors = ConfigValidator.validate_cross_field_rules(config_data)
        
        assert errors == []

    def test_validate_cross_field_rules_dht_port_conflict(self):
        """Test cross-field validation with DHT port conflict."""
        config_data = {
            "network": {"listen_port": 6881},
            "discovery": {"enable_dht": True, "dht_port": 6881},  # Same as listen port
        }
        
        # This should fail at the basic validation level due to model validator
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert not is_valid, "DHT port conflict should be caught by model validator"
        assert any("DHT port cannot be the same as listen port" in error for error in errors)

    def test_validate_cross_field_rules_limit_conflicts(self):
        """Test cross-field validation with limit conflicts."""
        config_data = {
            "limits": {
                "global_down_kib": 500,      # Lower than per-torrent
                "per_torrent_down_kib": 1000,
                "global_up_kib": 500,        # Lower than per-torrent
                "per_torrent_up_kib": 1000,
            }
        }
        
        errors = ConfigValidator.validate_cross_field_rules(config_data)
        
        assert len(errors) > 0
        assert any("Global download limit should be >=" in error for error in errors)
        assert any("Global upload limit should be >=" in error for error in errors)

    def test_validate_cross_field_rules_worker_warnings(self):
        """Test cross-field validation with worker warnings."""
        import os
        cpu_count = os.cpu_count() or 1
        
        # Use values that will actually trigger the warnings
        # Hash workers > cpu_count * 2
        # Disk workers > cpu_count
        hash_workers = min(32, cpu_count * 2 + 1)  # Just above threshold
        disk_workers = min(16, cpu_count + 1)      # Just above threshold
        
        # If the calculated values are at the field limits, skip the test
        if hash_workers == 32 and disk_workers == 16:
            pytest.skip("Cannot test worker warnings with current CPU count and field limits")
        
        config_data = {
            "disk": {
                "hash_workers": hash_workers,
                "disk_workers": disk_workers,
            }
        }
        
        errors = ConfigValidator.validate_cross_field_rules(config_data)
        
        # Should have warnings about high worker counts relative to CPU
        assert len(errors) > 0, f"Should have warnings for high worker counts: {errors}"
        assert any("Hash workers" in error for error in errors)
        assert any("Disk workers" in error for error in errors)


class TestConfigValidatorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_min_max_values(self):
        """Test validation with min/max boundary values."""
        # Test minimum valid values
        config_data = {
            "network": {
                "listen_port": 1024,  # Minimum valid port
                "max_global_peers": 1,  # Minimum valid peers
            },
            "disk": {
                "hash_workers": 1,  # Minimum workers
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid

    def test_validate_max_values(self):
        """Test validation with maximum valid values."""
        config_data = {
            "network": {
                "listen_port": 65535,  # Maximum valid port
                "max_global_peers": 10000,  # Maximum valid peers
            },
            "disk": {
                "hash_workers": 32,  # Maximum workers
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid

    def test_validate_out_of_range_values(self):
        """Test validation with out-of-range values."""
        config_data = {
            "network": {
                "listen_port": 1023,  # Below minimum
                "max_global_peers": 10001,  # Above maximum
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_enum_values(self):
        """Test validation with enum values."""
        # Valid enum values
        config_data = {
            "strategy": {
                "piece_selection": "rarest_first",
            },
            "disk": {
                "preallocate": "full",
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid

        # Invalid enum values
        config_data = {
            "strategy": {
                "piece_selection": "invalid_strategy",
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_empty_config(self):
        """Test validation with empty configuration."""
        config_data = {}
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid  # Empty config should be valid (uses defaults)

    def test_validate_partial_config(self):
        """Test validation with partial configuration."""
        config_data = {
            "network": {
                "listen_port": 6881,
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid  # Partial config should be valid

    def test_validate_extra_fields(self):
        """Test validation with extra unknown fields."""
        config_data = {
            "network": {
                "listen_port": 6881,
                "unknown_field": "value",  # Extra field
            }
        }
        
        # Pydantic allows extra fields by default, so this should be valid
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid, f"Extra fields should be allowed by default: {errors}"
