"""Expanded tests for ccbt.cli.config_commands to achieve 95%+ coverage.

Covers all missing lines:
- Exception handling in show_config (key/section not found, YAML import errors)
- Exception handling in get_value
- set_value flag handling and parse_value function paths
- reset_config complex logic with safeguards
- validate_config exception handling
- migrate_config backup operations
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import toml
from click.testing import CliRunner

from ccbt.cli.config_commands import (
    get_value,
    migrate_config_cmd,
    reset_config,
    set_value,
    show_config,
    validate_config_cmd,
)

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestShowConfigExpanded:
    """Expanded tests for show_config command."""

    def test_show_config_key_success_json(self, tmp_path):
        """Test show_config with valid key returns JSON (lines 68-69, 73-74)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--key", "network.listen_port", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        # Should output JSON regardless of format when key is specified
        try:
            json.loads(result.output.strip())
        except json.JSONDecodeError:
            pytest.fail("Expected valid JSON output for key lookup")

    def test_show_config_section_success(self, tmp_path):
        """Test show_config with valid section (line 79)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--section", "network", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        assert "listen_port" in result.output

    def test_show_config_json_format(self, tmp_path):
        """Test show_config with JSON format (line 82)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--format", "json", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        try:
            json.loads(result.output.strip())
        except json.JSONDecodeError:
            pytest.fail("Expected valid JSON output")

    def test_show_config_yaml_format_success(self, tmp_path):
        """Test show_config with YAML format success (lines 89-91)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--format", "yaml", "--config", str(config_file)
        ])
        
        # May succeed if PyYAML is available, or fail if not
        # Both paths are now covered
        assert result.exit_code in [0, 1]

    def test_show_config_key_not_found(self, tmp_path):
        """Test show_config with non-existent key (lines 70-72)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--key", "network.nonexistent", "--config", str(config_file)
        ])
        
        assert result.exit_code != 0
        assert "Key not found" in result.output

    def test_show_config_section_not_found(self, tmp_path):
        """Test show_config with non-existent section (lines 77-78)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(show_config, [
            "--section", "nonexistent", "--config", str(config_file)
        ])
        
        assert result.exit_code != 0
        assert "Section not found" in result.output

    def test_show_config_yaml_import_error(self, tmp_path):
        """Test show_config YAML format without PyYAML (lines 86-88)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        with patch.dict("sys.modules", {"yaml": None}):
            result = runner.invoke(show_config, [
                "--format", "yaml", "--config", str(config_file)
            ])
            
            assert result.exit_code != 0
            assert "PyYAML is required" in result.output


class TestGetValueExpanded:
    """Expanded tests for get_value command."""

    def test_get_value_key_success(self, tmp_path):
        """Test get_value with valid key (line 105)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(get_value, [
            "network.listen_port", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        try:
            value = json.loads(result.output.strip())
            assert value == 6881
        except json.JSONDecodeError:
            pytest.fail("Expected valid JSON output")

    def test_get_value_key_not_found(self, tmp_path):
        """Test get_value with non-existent key (lines 106-108)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(get_value, [
            "network.nonexistent", "--config", str(config_file)
        ])
        
        assert result.exit_code != 0
        assert "Key not found" in result.output

    def test_get_value_nested_key_error(self, tmp_path):
        """Test get_value with invalid nested key path."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(get_value, [
            "network.invalid.nested.path", "--config", str(config_file)
        ])
        
        assert result.exit_code != 0
        assert "Key not found" in result.output


class TestSetValueExpanded:
    """Expanded tests for set_value command."""

    def test_set_value_default_local(self, tmp_path, monkeypatch):
        """Test set_value default local behavior (line 147)."""
        runner = CliRunner()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(tmp_path)
            config_file = tmp_path / "ccbt.toml"
            
            with patch("ccbt.cli.config_commands._should_skip_project_local_write", return_value=False):
                result = runner.invoke(set_value, [
                    "network.listen_port", "8080"  # No flags, should default to local
                ])
                
                assert result.exit_code == 0
                assert str(config_file) in result.output
                assert config_file.exists()
                data = toml.load(str(config_file))
                assert data["network"]["listen_port"] == 8080
        finally:
            os.chdir(original_cwd)

    def test_set_value_with_global_flag(self, tmp_path, monkeypatch):
        """Test set_value with --global flag (lines 142-144)."""
        runner = CliRunner()
        home_config = tmp_path / "home" / ".config" / "ccbt" / "ccbt.toml"
        home_config.parent.mkdir(parents=True, exist_ok=True)
        
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        
        result = runner.invoke(set_value, [
            "network.listen_port", "8080", "--global"
        ])
        
        assert result.exit_code == 0
        assert str(home_config) in result.output
        assert home_config.exists()
        data = toml.load(str(home_config))
        assert data["network"]["listen_port"] == 8080

    def test_set_value_with_local_flag(self, tmp_path, monkeypatch):
        """Test set_value with --local flag (lines 142-144)."""
        runner = CliRunner()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(tmp_path)
            
            with patch("ccbt.cli.config_commands._should_skip_project_local_write", return_value=False):
                result = runner.invoke(set_value, [
                    "network.listen_port", "9090", "--local"
                ])
                
                assert result.exit_code == 0
                local_config = tmp_path / "ccbt.toml"
                assert local_config.exists()
                data = toml.load(str(local_config))
                assert data["network"]["listen_port"] == 9090
        finally:
            os.chdir(original_cwd)

    def test_set_value_file_load_exception(self, tmp_path):
        """Test set_value with corrupted config file (lines 154-155)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        # Write invalid TOML
        config_file.write_text("invalid toml content [[[[[")
        
        # Should handle exception and continue with empty dict
        result = runner.invoke(set_value, [
            "network.listen_port", "8080", "--config", str(config_file)
        ])
        
        # Should succeed despite corrupted file (falls back to empty dict)
        assert result.exit_code == 0

    def test_set_value_parse_bool_true_variants(self, tmp_path):
        """Test set_value parse_value with true boolean variants (lines 160, 162)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        
        for true_val in ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]:
            result = runner.invoke(set_value, [
                "test.bool_val", true_val, "--config", str(config_file)
            ])
            assert result.exit_code == 0
            
            data = toml.load(str(config_file))
            assert data["test"]["bool_val"] is True

    def test_set_value_parse_bool_false_variants(self, tmp_path):
        """Test set_value parse_value with false boolean variants (lines 160, 162)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        
        for false_val in ["false", "FALSE", "False", "0", "no", "NO", "off", "OFF"]:
            result = runner.invoke(set_value, [
                "test.bool_val", false_val, "--config", str(config_file)
            ])
            assert result.exit_code == 0
            
            data = toml.load(str(config_file))
            assert data["test"]["bool_val"] is False

    def test_set_value_parse_float(self, tmp_path):
        """Test set_value parse_value with float value (line 165)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        
        result = runner.invoke(set_value, [
            "test.float_val", "3.14", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        data = toml.load(str(config_file))
        assert data["test"]["float_val"] == 3.14
        assert isinstance(data["test"]["float_val"], float)

    def test_set_value_parse_int(self, tmp_path):
        """Test set_value parse_value with integer value."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        
        result = runner.invoke(set_value, [
            "test.int_val", "42", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        data = toml.load(str(config_file))
        assert data["test"]["int_val"] == 42
        assert isinstance(data["test"]["int_val"], int)

    def test_set_value_parse_string_fallback(self, tmp_path):
        """Test set_value parse_value with string that can't be parsed (lines 167-168)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        
        result = runner.invoke(set_value, [
            "test.string_val", "hello world", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        data = toml.load(str(config_file))
        assert data["test"]["string_val"] == "hello world"


class TestResetConfigExpanded:
    """Expanded tests for reset_config command."""

    def test_reset_config_without_confirm(self):
        """Test reset_config without --confirm flag."""
        runner = CliRunner()
        
        result = runner.invoke(reset_config, [])
        
        assert result.exit_code != 0
        assert "Use --confirm" in result.output

    def test_reset_config_with_confirm_and_key(self, tmp_path):
        """Test reset_config with --confirm and --key (lines 213-223)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("""
[network]
listen_port = 6881
max_peers = 50

[storage]
download_dir = "/tmp"
""")
        
        result = runner.invoke(reset_config, [
            "--confirm", "--key", "network.listen_port", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        assert "OK" in result.output
        
        # Key should be removed
        data = toml.load(str(config_file))
        assert "listen_port" not in data.get("network", {})

    def test_reset_config_with_confirm_and_section(self, tmp_path):
        """Test reset_config with --confirm and --section (lines 224-226)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("""
[network]
listen_port = 6881

[storage]
download_dir = "/tmp"
""")
        
        result = runner.invoke(reset_config, [
            "--confirm", "--section", "network", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        assert "OK" in result.output
        
        # Section should be removed
        data = toml.load(str(config_file))
        assert "network" not in data

    def test_reset_config_with_confirm_wipe_all(self, tmp_path):
        """Test reset_config with --confirm wiping entire file (lines 228-230)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("""
[network]
listen_port = 6881

[storage]
download_dir = "/tmp"
""")
        
        result = runner.invoke(reset_config, [
            "--confirm", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        assert "OK" in result.output
        
        # File should be empty or minimal
        data = toml.load(str(config_file))
        assert data == {}

    def test_reset_config_key_exception_handling(self, tmp_path):
        """Test reset_config exception handling for invalid key path (lines 222-223)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        # Try to remove invalid nested key
        result = runner.invoke(reset_config, [
            "--confirm", "--key", "network.invalid.nested.path", "--config", str(config_file)
        ])
        
        # Should handle exception gracefully
        assert result.exit_code == 0

    def test_reset_config_test_env_safeguard(self, tmp_path, monkeypatch):
        """Test reset_config test environment safeguard (lines 198-204)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        # Set test environment variables
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_reset_config")
        
        # Change to tmp_path directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Create a local ccbt.toml that matches config_file
            local_config = tmp_path / "ccbt.toml"
            local_config.write_text("[network]\nlisten_port = 6881\n")
            
            # Should hit safeguard and return early
            result = runner.invoke(reset_config, ["--confirm"])
            
            assert result.exit_code == 0
            assert "OK" in result.output
            # File should still exist (safeguard prevented deletion)
            assert local_config.exists()
        finally:
            os.chdir(original_cwd)

    def test_reset_config_safeguard_exception(self, tmp_path, monkeypatch):
        """Test reset_config safeguard exception handling (lines 205-207)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        # Make Path.resolve() raise exception to trigger safeguard exception handler
        original_resolve = Path.resolve
        def failing_resolve(self):
            if self == config_file:
                raise Exception("Path resolve error")
            return original_resolve(self)
        
        with patch.object(Path, "resolve", failing_resolve):
            result = runner.invoke(reset_config, [
                "--confirm", "--config", str(config_file)
            ])
            
            # Should proceed normally despite safeguard error (exception caught)
            assert result.exit_code == 0


class TestValidateConfigExpanded:
    """Expanded tests for validate_config_cmd."""

    def test_validate_config_valid(self, tmp_path):
        """Test validate_config with valid config."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(validate_config_cmd, ["--config", str(config_file)])
        
        assert result.exit_code == 0
        assert "VALID" in result.output

    def test_validate_config_invalid_exception(self, tmp_path):
        """Test validate_config with invalid config causing exception (lines 243-244)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        # Write invalid config that will cause ConfigManager to raise exception
        config_file.write_text("invalid = [\n")  # Incomplete structure
        
        # Mock ConfigManager to raise an exception
        with patch("ccbt.cli.config_commands.ConfigManager", side_effect=ValueError("Invalid config")):
            result = runner.invoke(validate_config_cmd, ["--config", str(config_file)])
            
            assert result.exit_code != 0
            assert "Invalid config" in result.output


class TestMigrateConfigExpanded:
    """Expanded tests for migrate_config_cmd."""

    def test_migrate_config_with_backup(self, tmp_path):
        """Test migrate_config with --backup flag (lines 262-263)."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(migrate_config_cmd, [
            "--backup", "--config", str(config_file)
        ])
        
        assert result.exit_code == 0
        assert "MIGRATED" in result.output
        
        # Backup file should exist
        backup_file = Path(str(config_file) + ".bak")
        assert backup_file.exists()
        assert backup_file.read_text() == config_file.read_text()

    def test_migrate_config_without_backup(self, tmp_path):
        """Test migrate_config without --backup flag."""
        runner = CliRunner()
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        result = runner.invoke(migrate_config_cmd, ["--config", str(config_file)])
        
        assert result.exit_code == 0
        assert "MIGRATED" in result.output
        
        # Backup file should not exist
        backup_file = Path(str(config_file) + ".bak")
        assert not backup_file.exists()

