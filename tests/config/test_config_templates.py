"""Tests for configuration templates and profiles."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from ccbt.config_templates import ConfigTemplates, ConfigProfiles
from ccbt.models import Config


class TestConfigTemplates:
    """Test configuration templates functionality."""

    def test_list_templates(self):
        """Test listing all available templates."""
        templates = ConfigTemplates.list_templates()
        
        assert isinstance(templates, list)
        assert len(templates) > 0
        
        # Check template structure
        for template in templates:
            assert "name" in template
            assert "description" in template
            assert "key" in template
            assert isinstance(template["name"], str)
            assert isinstance(template["description"], str)
            assert isinstance(template["key"], str)

    def test_get_template_existing(self):
        """Test getting an existing template."""
        template = ConfigTemplates.get_template("performance")
        
        assert template is not None
        assert isinstance(template, dict)
        assert "network" in template
        assert "disk" in template
        assert "strategy" in template

    def test_get_template_nonexistent(self):
        """Test getting a non-existent template."""
        template = ConfigTemplates.get_template("nonexistent")
        assert template is None

    def test_apply_template_deep_merge(self):
        """Test applying template with deep merge strategy."""
        base_config = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 100,
            },
            "disk": {
                "hash_workers": 2,
            }
        }
        
        result = ConfigTemplates.apply_template(base_config, "performance", "deep")
        
        # Should merge template values with base config
        assert result["network"]["listen_port"] == 6881  # From base
        assert result["network"]["max_global_peers"] == 500  # From template
        assert result["disk"]["hash_workers"] == 8  # From template

    def test_apply_template_shallow_merge(self):
        """Test applying template with shallow merge strategy."""
        base_config = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 100,
            },
            "disk": {
                "hash_workers": 2,
            }
        }
        
        result = ConfigTemplates.apply_template(base_config, "performance", "shallow")
        
        # Should replace entire sections
        assert "network" in result
        assert "disk" in result
        # The entire network section should be from template
        assert result["network"]["max_global_peers"] == 500

    def test_apply_template_replace(self):
        """Test applying template with replace strategy."""
        base_config = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 100,
            },
            "disk": {
                "hash_workers": 2,
            }
        }
        
        result = ConfigTemplates.apply_template(base_config, "performance", "replace")
        
        # Should completely replace base config
        assert result == ConfigTemplates.get_template("performance")

    def test_apply_template_invalid_strategy(self):
        """Test applying template with invalid merge strategy."""
        base_config = {"network": {"listen_port": 6881}}
        
        with pytest.raises(ValueError, match="Invalid merge strategy"):
            ConfigTemplates.apply_template(base_config, "performance", "invalid")

    def test_apply_template_nonexistent(self):
        """Test applying non-existent template."""
        base_config = {"network": {"listen_port": 6881}}
        
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            ConfigTemplates.apply_template(base_config, "nonexistent")

    def test_validate_template_valid(self):
        """Test validating a valid template."""
        is_valid, errors = ConfigTemplates.validate_template("performance")
        
        assert is_valid
        assert errors == []

    def test_validate_template_nonexistent(self):
        """Test validating a non-existent template."""
        is_valid, errors = ConfigTemplates.validate_template("nonexistent")
        
        assert not is_valid
        assert len(errors) > 0
        assert "not found" in errors[0]

    def test_export_template_json(self):
        """Test exporting template in JSON format."""
        json_str = ConfigTemplates.export_template("performance", "json")
        
        assert isinstance(json_str, str)
        
        # Parse back to verify it's valid JSON
        template = json.loads(json_str)
        assert "network" in template
        assert "disk" in template

    def test_export_template_yaml(self):
        """Test exporting template in YAML format."""
        try:
            yaml_str = ConfigTemplates.export_template("performance", "yaml")
            assert isinstance(yaml_str, str)
            assert "network:" in yaml_str
        except ImportError:
            pytest.skip("PyYAML not available")

    def test_export_template_invalid_format(self):
        """Test exporting template with invalid format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            ConfigTemplates.export_template("performance", "invalid")

    def test_export_template_nonexistent(self):
        """Test exporting non-existent template."""
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            ConfigTemplates.export_template("nonexistent")

    def test_deep_merge_nested_dicts(self):
        """Test deep merge with nested dictionaries."""
        base = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 100,
                "settings": {
                    "timeout": 30,
                    "retries": 3,
                }
            }
        }
        
        override = {
            "network": {
                "max_global_peers": 200,
                "settings": {
                    "retries": 5,
                    "new_setting": "value",
                }
            },
            "disk": {
                "hash_workers": 4,
            }
        }
        
        result = ConfigTemplates._deep_merge(base, override)
        
        # Should preserve base values not overridden
        assert result["network"]["listen_port"] == 6881
        assert result["network"]["settings"]["timeout"] == 30
        
        # Should override specified values
        assert result["network"]["max_global_peers"] == 200
        assert result["network"]["settings"]["retries"] == 5
        
        # Should add new values
        assert result["network"]["settings"]["new_setting"] == "value"
        assert result["disk"]["hash_workers"] == 4

    def test_all_templates_valid(self):
        """Test that all predefined templates are valid."""
        templates = ConfigTemplates.list_templates()
        
        for template_info in templates:
            template_name = template_info["key"]
            is_valid, errors = ConfigTemplates.validate_template(template_name)
            
            assert is_valid, f"Template '{template_name}' is invalid: {errors}"

    def test_template_composition(self):
        """Test composing multiple templates."""
        base_config = {}
        
        # Apply low_resource template first
        result = ConfigTemplates.apply_template(base_config, "low_resource")
        
        # Then apply performance template
        result = ConfigTemplates.apply_template(result, "performance")
        
        # Should have performance settings (last applied)
        assert result["network"]["max_global_peers"] == 500
        assert result["disk"]["hash_workers"] == 8


class TestConfigProfiles:
    """Test configuration profiles functionality."""

    def test_list_profiles(self):
        """Test listing all available profiles."""
        profiles = ConfigProfiles.list_profiles()
        
        assert isinstance(profiles, list)
        assert len(profiles) > 0
        
        # Check profile structure
        for profile in profiles:
            assert "name" in profile
            assert "description" in profile
            assert "key" in profile
            assert "templates" in profile
            assert isinstance(profile["name"], str)
            assert isinstance(profile["description"], str)
            assert isinstance(profile["key"], str)
            assert isinstance(profile["templates"], list)

    def test_get_profile_existing(self):
        """Test getting an existing profile."""
        profile = ConfigProfiles.get_profile("desktop")
        
        assert profile is not None
        assert "name" in profile
        assert "description" in profile
        assert "templates" in profile
        assert "overrides" in profile

    def test_get_profile_nonexistent(self):
        """Test getting a non-existent profile."""
        profile = ConfigProfiles.get_profile("nonexistent")
        assert profile is None

    def test_apply_profile(self):
        """Test applying a profile to base configuration."""
        base_config = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 100,
            },
            "disk": {
                "hash_workers": 2,
            }
        }
        
        result = ConfigProfiles.apply_profile(base_config, "desktop")
        
        # Should apply templates and overrides
        assert result["network"]["max_global_peers"] == 200  # From desktop overrides
        assert result["disk"]["hash_workers"] == 4  # From desktop overrides
        # Should have template values for other settings
        assert "strategy" in result
        assert "discovery" in result

    def test_apply_profile_nonexistent(self):
        """Test applying non-existent profile."""
        base_config = {"network": {"listen_port": 6881}}
        
        with pytest.raises(ValueError, match="Profile 'nonexistent' not found"):
            ConfigProfiles.apply_profile(base_config, "nonexistent")

    def test_create_custom_profile(self):
        """Test creating a custom profile."""
        profile = ConfigProfiles.create_custom_profile(
            name="Test Profile",
            description="Test description",
            templates=["performance"],
            overrides={
                "network": {
                    "max_global_peers": 300,
                }
            }
        )
        
        assert profile["name"] == "Test Profile"
        assert profile["description"] == "Test description"
        assert profile["templates"] == ["performance"]
        assert profile["overrides"]["network"]["max_global_peers"] == 300

    def test_create_custom_profile_with_file(self, tmp_path):
        """Test creating a custom profile and saving to file."""
        profile_file = tmp_path / "test_profile.json"
        
        profile = ConfigProfiles.create_custom_profile(
            name="Test Profile",
            description="Test description",
            templates=["performance"],
            overrides={"network": {"max_global_peers": 300}},
            profile_file=profile_file,
        )
        
        # Check file was created
        assert profile_file.exists()
        
        # Check file contents
        with open(profile_file, "r", encoding="utf-8") as f:
            saved_profile = json.load(f)
        
        assert saved_profile == profile

    def test_create_custom_profile_invalid_template(self):
        """Test creating custom profile with invalid template."""
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            ConfigProfiles.create_custom_profile(
                name="Test Profile",
                description="Test description",
                templates=["nonexistent"],
                overrides={}
            )

    def test_load_custom_profile(self, tmp_path):
        """Test loading a custom profile from file."""
        profile_file = tmp_path / "test_profile.json"
        
        # Create a profile file
        profile_data = {
            "name": "Test Profile",
            "description": "Test description",
            "templates": ["performance"],
            "overrides": {"network": {"max_global_peers": 300}}
        }
        
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f)
        
        # Load the profile
        loaded_profile = ConfigProfiles.load_custom_profile(profile_file)
        
        assert loaded_profile == profile_data

    def test_load_custom_profile_nonexistent(self, tmp_path):
        """Test loading non-existent profile file."""
        profile_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError):
            ConfigProfiles.load_custom_profile(profile_file)

    def test_load_custom_profile_invalid_json(self, tmp_path):
        """Test loading profile file with invalid JSON."""
        profile_file = tmp_path / "invalid.json"
        
        with open(profile_file, "w", encoding="utf-8") as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            ConfigProfiles.load_custom_profile(profile_file)

    def test_load_custom_profile_missing_fields(self, tmp_path):
        """Test loading profile file with missing required fields."""
        profile_file = tmp_path / "incomplete.json"
        
        incomplete_profile = {
            "name": "Test Profile",
            # Missing description, templates, overrides
        }
        
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(incomplete_profile, f)
        
        with pytest.raises(ValueError, match="Profile missing required field"):
            ConfigProfiles.load_custom_profile(profile_file)

    def test_validate_profile_valid(self):
        """Test validating a valid profile."""
        is_valid, errors = ConfigProfiles.validate_profile("desktop")
        
        assert is_valid
        assert errors == []

    def test_validate_profile_nonexistent(self):
        """Test validating a non-existent profile."""
        is_valid, errors = ConfigProfiles.validate_profile("nonexistent")
        
        assert not is_valid
        assert len(errors) > 0
        assert "not found" in errors[0]

    def test_all_profiles_valid(self):
        """Test that all predefined profiles are valid."""
        profiles = ConfigProfiles.list_profiles()
        
        for profile_info in profiles:
            profile_name = profile_info["key"]
            is_valid, errors = ConfigProfiles.validate_profile(profile_name)
            
            assert is_valid, f"Profile '{profile_name}' is invalid: {errors}"

    def test_profile_inheritance(self):
        """Test profile inheritance from templates."""
        base_config = {}
        
        # Apply desktop profile
        result = ConfigProfiles.apply_profile(base_config, "desktop")
        
        # Should have template values
        assert "strategy" in result
        assert "discovery" in result
        assert "limits" in result
        
        # Should have profile-specific overrides
        assert result["network"]["max_global_peers"] == 200  # From desktop overrides
        assert result["disk"]["hash_workers"] == 4  # From desktop overrides

    def test_profile_template_order(self):
        """Test that templates are applied in correct order."""
        base_config = {}
        
        # Apply server profile (has multiple templates)
        result = ConfigProfiles.apply_profile(base_config, "server")
        
        # Should have values from both templates
        assert "strategy" in result  # From performance template
        assert "discovery" in result  # From performance template
        
        # Should have server-specific overrides
        assert result["network"]["max_global_peers"] == 1000  # From server overrides
        assert result["disk"]["hash_workers"] == 16  # From server overrides

    def test_profile_override_precedence(self):
        """Test that profile overrides take precedence over templates."""
        base_config = {
            "network": {
                "max_global_peers": 50,  # Base value
            }
        }
        
        # Apply mobile profile
        result = ConfigProfiles.apply_profile(base_config, "mobile")
        
        # Should use mobile profile override, not base or template
        assert result["network"]["max_global_peers"] == 30  # From mobile overrides

    def test_profile_with_multiple_templates(self):
        """Test profile with multiple templates."""
        base_config = {}
        
        # Apply seedbox profile (has multiple templates)
        result = ConfigProfiles.apply_profile(base_config, "seedbox")
        
        # Should have values from both seeding and performance templates
        assert result["network"]["max_upload_slots"] == 20  # From seedbox overrides
        assert result["strategy"]["piece_selection"] == "rarest_first"  # From seeding template
        assert result["network"]["tcp_nodelay"] is True  # From performance template
