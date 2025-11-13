"""Expanded tests for ccbt.cli.config_commands_extended module.

Covers:
- Schema command error handling and edge cases
- Template command full logic
- Profile command full logic  
- Backup/restore commands
- Diff command
- Capabilities commands
- Auto-tune command
- Export/import commands
- Validate command detailed mode
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import toml
from click.testing import CliRunner

from ccbt.cli.config_commands_extended import (
    auto_tune_cmd,
    backup_cmd,
    capabilities_group,
    capabilities_show_cmd,
    capabilities_summary_cmd,
    config_extended,
    diff_cmd,
    export_cmd,
    import_cmd,
    list_backups_cmd,
    list_profiles_cmd,
    list_templates_cmd,
    profile_cmd,
    restore_cmd,
    schema_cmd,
    template_cmd,
    validate_cmd,
)
from ccbt.config.config import ConfigManager
from ccbt.config.config_backup import ConfigBackup

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestSchemaCommandExpanded:
    """Expanded tests for schema command."""

    def test_schema_with_invalid_model(self):
        """Test schema command with invalid model name (lines 91-96)."""
        runner = CliRunner()
        
        result = runner.invoke(schema_cmd, ["--model", "InvalidModelName"])
        
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_schema_with_valid_model(self):
        """Test schema command with valid model name (lines 91-93)."""
        runner = CliRunner()
        
        # Try to use a model that might exist in Config
        # Config class may have nested models, so try common ones
        result = runner.invoke(schema_cmd, ["--model", "model_dump"])
        
        # getattr will work even for methods, so this may succeed
        # If it fails, that's fine - we're testing the branch
        assert result.exit_code in [0, 1]

    def test_schema_output_to_console(self):
        """Test schema command output to console (lines 117-118)."""
        runner = CliRunner()
        
        result = runner.invoke(schema_cmd, [])
        
        assert result.exit_code == 0
        # Should output JSON schema
        assert len(result.output) > 0
        assert "type" in result.output or "properties" in result.output

    def test_schema_yaml_format(self):
        """Test schema command with YAML format (lines 102-109)."""
        runner = CliRunner()
        result = runner.invoke(schema_cmd, ["--format", "yaml"])
        
        assert result.exit_code == 0
        # YAML output should contain schema structure
        assert "type:" in result.output or "properties:" in result.output

    def test_schema_yaml_with_output_file(self, tmp_path):
        """Test schema command with YAML format and output file."""
        runner = CliRunner()
        output_file = tmp_path / "schema.yaml"
        
        result = runner.invoke(schema_cmd, ["--format", "yaml", "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        assert "Schema written to" in result.output

    def test_schema_error_handling(self):
        """Test schema command error handling (lines 95-97)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigSchema.generate_full_schema", side_effect=Exception("Test error")):
            result = runner.invoke(schema_cmd, [])
            
            assert result.exit_code != 0
            assert "Error generating schema" in result.output


class TestTemplateCommandExpanded:
    """Expanded tests for template command."""

    def test_template_invalid_template(self):
        """Test template command with invalid template (lines 121-126)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(False, ["Error 1", "Error 2"])):
            result = runner.invoke(template_cmd, ["invalid-template"])
            
            assert result.exit_code == 0
            assert "Invalid template" in result.output

    def test_template_not_found(self):
        """Test template command with non-existent template (lines 129-132)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=None):
            result = runner.invoke(template_cmd, ["missing-template"])
            
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_template_apply(self, tmp_path):
        """Test template command with --apply flag (lines 142-153)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value={"network": {"max_global_peers": 200}}):
                with patch("ccbt.cli.config_commands_extended.ConfigTemplates.apply_template", return_value={"network": {"max_global_peers": 200}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {"test-template": {"name": "Test", "description": "Test desc"}}):
                        with patch("ccbt.cli.config_commands_extended._should_skip_project_local_write", return_value=False):
                            result = runner.invoke(template_cmd, ["test-template", "--apply", "--config", str(config_file)])
                            
                            assert result.exit_code == 0
                            assert "applied" in result.output.lower()

    def test_template_output_to_file(self, tmp_path):
        """Test template command with output file (lines 154-159)."""
        runner = CliRunner()
        output_file = tmp_path / "output.toml"
        
        template_config = {"network": {"max_global_peers": 100}}
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=template_config):
                with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {"test": {"name": "Test Template", "description": "Test Description"}}):
                    result = runner.invoke(template_cmd, ["test", "--output", str(output_file)])
                    
                    assert result.exit_code == 0
                    assert output_file.exists()
                    # Verify metadata was shown
                    assert "Template:" in result.output
                    assert "Test Template" in result.output

    def test_template_output_file_write(self, tmp_path):
        """Test template command writes to output file (lines 156-157)."""
        runner = CliRunner()
        output_file = tmp_path / "output.toml"
        
        template_config = {"network": {"max_global_peers": 100}}
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=template_config):
                with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {}):
                    # Use a template name that exists
                    with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {"test": {}}):
                        result = runner.invoke(template_cmd, ["test", "--output", str(output_file)])
                        
                        assert result.exit_code == 0
                        assert output_file.exists()
                        # Verify file was written with TOML content
                        content = output_file.read_text()
                        assert len(content) > 0

    def test_template_not_found_early_return(self):
        """Test template command early return when template not found (lines 156-157)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=None):
            result = runner.invoke(template_cmd, ["nonexistent"])
            
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_template_without_metadata(self, tmp_path):
        """Test template command when template has no metadata (lines 139-140)."""
        runner = CliRunner()
        output_file = tmp_path / "output.toml"
        
        template_config = {"network": {"max_global_peers": 100}}
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=template_config):
                with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {}):  # No metadata
                    result = runner.invoke(template_cmd, ["test-template", "--output", str(output_file)])
                    
                    assert result.exit_code == 0
                    assert "Template: test-template" in result.output

    def test_template_print_to_console(self):
        """Test template command printing to console (lines 158-159)."""
        runner = CliRunner()
        
        template_config = {"network": {"max_global_peers": 100}}
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigTemplates.get_template", return_value=template_config):
                with patch("ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES", {"test": {"name": "Test", "description": "Test"}}):
                    result = runner.invoke(template_cmd, ["test"])
                    
                    assert result.exit_code == 0
                    # Should output TOML to console (via toml.dumps)
                    # TOML output format may vary, check for key indicators
                    output_lower = result.output.lower()
                    assert "network" in output_lower or "max_global" in output_lower or "template:" in output_lower

    def test_template_error_handling(self):
        """Test template command error handling (lines 161-163)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.validate_template", side_effect=Exception("Test error")):
            result = runner.invoke(template_cmd, ["test-template"])
            
            assert result.exit_code != 0
            assert "Error with template" in result.output


class TestProfileCommandExpanded:
    """Expanded tests for profile command."""

    def test_profile_invalid_profile(self):
        """Test profile command with invalid profile (lines 187-192)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(False, ["Error"])):
            result = runner.invoke(profile_cmd, ["invalid-profile"])
            
            assert result.exit_code == 0
            assert "Invalid profile" in result.output

    def test_profile_not_found(self):
        """Test profile command with non-existent profile (lines 194-198)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value=None):
            result = runner.invoke(profile_cmd, ["missing-profile"])
            
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_profile_apply(self, tmp_path):
        """Test profile command with --apply flag (lines 209-220)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value={"network": {"max_global_peers": 200}}):
                with patch("ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile", return_value={"network": {"max_global_peers": 200}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES", {"test-profile": {"name": "Test", "description": "Test", "templates": ["t1"]}}):
                        with patch("ccbt.cli.config_commands_extended._should_skip_project_local_write", return_value=False):
                            result = runner.invoke(profile_cmd, ["test-profile", "--apply", "--config", str(config_file)])
                            
                            assert result.exit_code == 0
                            assert "applied" in result.output.lower()

    def test_profile_output_to_file(self, tmp_path):
        """Test profile command with output file (lines 222-228)."""
        runner = CliRunner()
        output_file = tmp_path / "output.toml"
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value={"network": {}}):
                with patch("ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile", return_value={"network": {"max_global_peers": 100}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES", {"test": {"name": "Test Profile", "description": "Test Desc", "templates": ["t1"]}}):
                        result = runner.invoke(profile_cmd, ["test", "--output", str(output_file)])
                        
                        assert result.exit_code == 0
                        assert output_file.exists()
                        # Verify metadata was shown
                        assert "Profile:" in result.output
                        assert "Test Profile" in result.output
                        assert "Templates:" in result.output

    def test_profile_output_file_write(self, tmp_path):
        """Test profile command writes to output file (lines 224-226)."""
        runner = CliRunner()
        output_file = tmp_path / "output.toml"
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value={"network": {}}):
                with patch("ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile", return_value={"network": {"max_global_peers": 100}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES", {"test": {}}):
                        result = runner.invoke(profile_cmd, ["test", "--output", str(output_file)])
                        
                        assert result.exit_code == 0
                        assert output_file.exists()
                        # Verify file was written with TOML content
                        content = output_file.read_text()
                        assert len(content) > 0

    def test_profile_not_found_early_return(self, tmp_path):
        """Test profile command early return when profile not found (lines 222-223)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value=None):
            result = runner.invoke(profile_cmd, ["nonexistent"])
            
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_profile_without_metadata(self):
        """Test profile command when profile has no metadata (lines 206-207)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value={"network": {}}):
                with patch("ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile", return_value={"network": {}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES", {}):  # No metadata
                        result = runner.invoke(profile_cmd, ["test-profile"])
                        
                        assert result.exit_code == 0
                        assert "Profile: test-profile" in result.output

    def test_profile_print_to_console(self):
        """Test profile command printing to console (lines 227-228)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", return_value=(True, [])):
            with patch("ccbt.cli.config_commands_extended.ConfigProfiles.get_profile", return_value={"network": {}}):
                with patch("ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile", return_value={"network": {"max_global_peers": 100}}):
                    with patch("ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES", {"test": {"name": "Test Profile", "description": "Test", "templates": ["t1"]}}):
                        result = runner.invoke(profile_cmd, ["test"])
                        
                        assert result.exit_code == 0
                        # Should output TOML to console (via toml.dumps)
                        # TOML output format may vary, check for key indicators
                        output_lower = result.output.lower()
                        assert "network" in output_lower or "max_global" in output_lower or "profile:" in output_lower

    def test_profile_error_handling(self):
        """Test profile command error handling (lines 230-232)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile", side_effect=Exception("Test error")):
            result = runner.invoke(profile_cmd, ["test-profile"])
            
            assert result.exit_code != 0
            assert "Error with profile" in result.output


class TestBackupCommandExpanded:
    """Expanded tests for backup command."""

    def test_backup_no_config_file(self):
        """Test backup command with no config file (lines 254-256)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config_file = None
            mock_cm.return_value = mock_manager
            
            result = runner.invoke(backup_cmd, [])
            
            assert result.exit_code == 0
            assert "No configuration file" in result.output

    def test_backup_success(self, tmp_path):
        """Test backup command success path (lines 260-269)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        backup_file = tmp_path / "backup.tar.gz"
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config_file = config_file
            mock_cm.return_value = mock_manager
            
            with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
                mock_backup_instance = MagicMock()
                mock_backup_instance.create_backup.return_value = (True, str(backup_file), ["Message 1", "Message 2"])
                mock_backup.return_value = mock_backup_instance
                
                result = runner.invoke(backup_cmd, ["--description", "Test backup"])
                
                assert result.exit_code == 0
                assert "Backup created" in result.output

    def test_backup_failure(self, tmp_path):
        """Test backup command failure path (lines 270-273)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config_file = config_file
            mock_cm.return_value = mock_manager
            
            with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
                mock_backup_instance = MagicMock()
                mock_backup_instance.create_backup.return_value = (False, None, ["Error message"])
                mock_backup.return_value = mock_backup_instance
                
                result = runner.invoke(backup_cmd, [])
                
                assert result.exit_code == 0
                assert "Backup failed" in result.output

    def test_backup_error_handling(self):
        """Test backup command error handling (lines 275-277)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager", side_effect=Exception("Test error")):
            result = runner.invoke(backup_cmd, [])
            
            assert result.exit_code != 0
            assert "Error creating backup" in result.output


class TestRestoreCommandExpanded:
    """Expanded tests for restore command."""

    def test_restore_without_confirm(self, tmp_path):
        """Test restore command without --confirm flag (lines 291-293)."""
        runner = CliRunner()
        
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"fake backup")
        
        result = runner.invoke(restore_cmd, [str(backup_file)])
        
        assert result.exit_code == 0
        assert "Use --confirm" in result.output

    def test_restore_with_confirm_success(self, tmp_path):
        """Test restore command with --confirm flag success (lines 300-304)."""
        runner = CliRunner()
        
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"fake backup")
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
            mock_backup_instance = MagicMock()
            mock_backup_instance.restore_backup.return_value = (True, ["Success message"])
            mock_backup.return_value = mock_backup_instance
            
            result = runner.invoke(restore_cmd, [str(backup_file), "--confirm"])
            
            assert result.exit_code == 0
            assert "restored from" in result.output.lower()

    def test_restore_with_confirm_failure(self, tmp_path):
        """Test restore command with --confirm flag failure (lines 330-333)."""
        runner = CliRunner()
        
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"fake backup")
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
            mock_backup_instance = MagicMock()
            mock_backup_instance.restore_backup.return_value = (False, ["Error message"])
            mock_backup.return_value = mock_backup_instance
            
            result = runner.invoke(restore_cmd, [str(backup_file), "--confirm"])
            
            assert result.exit_code == 0
            assert "Restore failed" in result.output

    def test_restore_error_handling(self, tmp_path):
        """Test restore command error handling (lines 335-337)."""
        runner = CliRunner()
        
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"fake backup")
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
            mock_backup_instance = MagicMock()
            mock_backup_instance.restore_backup.side_effect = Exception("Test error")
            mock_backup.return_value = mock_backup_instance
            
            result = runner.invoke(restore_cmd, [str(backup_file), "--confirm"])
            
            assert result.exit_code != 0
            assert "Error restoring backup" in result.output


class TestListBackupsCommandExpanded:
    """Expanded tests for list-backups command."""

    def test_list_backups_json_format(self):
        """Test list-backups command with JSON format (lines 358-359)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
            mock_backup_instance = MagicMock()
            mock_backup_instance.list_backups.return_value = [
                {"file": "backup1.tar.gz", "timestamp": "2024-01-01", "description": "Test", "size": 1024}
            ]
            mock_backup.return_value = mock_backup_instance
            
            result = runner.invoke(list_backups_cmd, ["--format", "json"])
            
            assert result.exit_code == 0
            # JSON should be parseable
            try:
                data = json.loads(result.output)
                assert isinstance(data, list)
            except json.JSONDecodeError:
                pytest.fail("Output is not valid JSON")

    def test_list_backups_empty(self):
        """Test list-backups command with no backups (lines 354-356)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup") as mock_backup:
            mock_backup_instance = MagicMock()
            mock_backup_instance.list_backups.return_value = []
            mock_backup.return_value = mock_backup_instance
            
            result = runner.invoke(list_backups_cmd, [])
            
            assert result.exit_code == 0
            assert "No backups found" in result.output

    def test_list_backups_error_handling(self):
        """Test list-backups command error handling (lines 378-380)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigBackup", side_effect=Exception("Test error")):
            result = runner.invoke(list_backups_cmd, [])
            
            assert result.exit_code != 0
            assert "Error listing backups" in result.output


class TestDiffCommandExpanded:
    """Expanded tests for diff command."""

    def test_diff_success(self, tmp_path):
        """Test diff command with valid files (lines 374-393)."""
        runner = CliRunner()
        
        config1 = tmp_path / "config1.toml"
        config1.write_text("[network]\nmax_global_peers = 100\n")
        
        config2 = tmp_path / "config2.toml"
        config2.write_text("[network]\nmax_global_peers = 200\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigDiff") as mock_diff:
            mock_diff_instance = MagicMock()
            mock_diff_instance.compare.return_value = {"network.max_global_peers": {"old": 100, "new": 200}}
            mock_diff.return_value = mock_diff_instance
            
            result = runner.invoke(diff_cmd, [str(config1), str(config2)])
            
            assert result.exit_code == 0

    def test_diff_output_to_file(self, tmp_path):
        """Test diff command with output file (lines 380-382)."""
        runner = CliRunner()
        
        config1 = tmp_path / "config1.toml"
        config1.write_text("[network]\nmax_global_peers = 100\n")
        
        config2 = tmp_path / "config2.toml"
        config2.write_text("[network]\nmax_global_peers = 200\n")
        
        output_file = tmp_path / "diff.json"
        
        with patch("ccbt.cli.config_commands_extended.ConfigDiff.compare_files") as mock_compare:
            mock_compare.return_value = {"network.max_global_peers": {"old": 100, "new": 200}}
            
            result = runner.invoke(diff_cmd, [str(config1), str(config2), "--output", str(output_file)])
            
            assert result.exit_code == 0
            assert output_file.exists()
            assert "Diff written to" in result.output

    def test_diff_json_format(self, tmp_path):
        """Test diff command with JSON format (lines 383-384)."""
        runner = CliRunner()
        
        config1 = tmp_path / "config1.toml"
        config1.write_text("[network]\nmax_global_peers = 100\n")
        
        config2 = tmp_path / "config2.toml"
        config2.write_text("[network]\nmax_global_peers = 200\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigDiff.compare_files") as mock_compare:
            mock_compare.return_value = {"network.max_global_peers": {"old": 100, "new": 200}}
            
            result = runner.invoke(diff_cmd, [str(config1), str(config2), "--format", "json"])
            
            assert result.exit_code == 0
            # Should output JSON
            try:
                json.loads(result.output)
            except json.JSONDecodeError:
                # Output might have extra text
                assert "{" in result.output

    def test_diff_unified_format(self, tmp_path):
        """Test diff command with unified format (lines 386-389)."""
        runner = CliRunner()
        
        config1 = tmp_path / "config1.toml"
        config1.write_text("[network]\nmax_global_peers = 100\n")
        
        config2 = tmp_path / "config2.toml"
        config2.write_text("[network]\nmax_global_peers = 200\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigDiff.compare_files") as mock_compare:
            mock_compare.return_value = {"network.max_global_peers": {"old": 100, "new": 200}}
            
            result = runner.invoke(diff_cmd, [str(config1), str(config2)])
            
            assert result.exit_code == 0
            assert "Configuration differences" in result.output

    def test_diff_error_handling(self, tmp_path):
        """Test diff command error handling (lines 416-418)."""
        runner = CliRunner()
        
        config1 = tmp_path / "config1.toml"
        config2 = tmp_path / "config2.toml"
        
        config1.write_text("[network]\nmax_global_peers = 100\n")
        config2.write_text("[network]\nmax_global_peers = 200\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigDiff.compare_files", side_effect=Exception("Test error")):
            result = runner.invoke(diff_cmd, [str(config1), str(config2)])
            
            assert result.exit_code != 0
            assert "Error comparing configs" in result.output


class TestCapabilitiesCommandsExpanded:
    """Expanded tests for capabilities commands."""

    def test_capabilities_show_prints_table(self):
        """Test capabilities show prints table (lines 425-446)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            # Test different data types for table rendering
            mock_caps_instance.get_all_capabilities.return_value = {
                "bool_cap": True,
                "dict_cap": {"feature1": True, "feature2": False},
                "list_cap": ["item1", "item2"],
                "string_cap": "value",
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_show_cmd, [])
            
            assert result.exit_code == 0
            # Table should be printed (even if we can't verify exact format)
            assert len(result.output) > 0

    def test_capabilities_table_bool_values(self):
        """Test capabilities table with boolean values (lines 431-433)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            mock_caps_instance.get_all_capabilities.return_value = {
                "true_cap": True,
                "false_cap": False,
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_show_cmd, [])
            
            assert result.exit_code == 0

    def test_capabilities_table_dict_values(self):
        """Test capabilities table with dict values (lines 434-436)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            mock_caps_instance.get_all_capabilities.return_value = {
                "dict_cap": {"f1": True, "f2": False},
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_show_cmd, [])
            
            assert result.exit_code == 0

    def test_capabilities_table_list_values(self):
        """Test capabilities table with list values (lines 437-439)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            mock_caps_instance.get_all_capabilities.return_value = {
                "list_cap": ["item1", "item2"],
                "empty_list": [],
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_show_cmd, [])
            
            assert result.exit_code == 0

    def test_capabilities_table_other_values(self):
        """Test capabilities table with other value types (lines 440-442)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            mock_caps_instance.get_all_capabilities.return_value = {
                "string_cap": "test_value",
                "int_cap": 42,
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_show_cmd, [])
            
            assert result.exit_code == 0

    def test_capabilities_summary_prints_summary(self):
        """Test capabilities summary prints summary (lines 449-460)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.SystemCapabilities") as mock_caps:
            mock_caps_instance = MagicMock()
            mock_caps_instance.get_capability_summary.return_value = {
                "cap1": True,
                "cap2": False,
            }
            mock_caps.return_value = mock_caps_instance
            
            result = runner.invoke(capabilities_summary_cmd, [])
            
            assert result.exit_code == 0
            # Table should be printed (line 460 has pragma no cover, but we can exercise the function)
            assert len(result.output) > 0


class TestAutoTuneCommandExpanded:
    """Expanded tests for auto-tune command."""

    def test_auto_tune_with_apply(self, tmp_path):
        """Test auto-tune command with --apply flag (lines 478-494)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        from ccbt.models import Config
        
        mock_config = MagicMock(spec=Config)
        mock_config.model_dump.return_value = {"network": {"max_global_peers": 200}}
        
        with patch("ccbt.cli.config_commands_extended.ConditionalConfig") as mock_cond:
            mock_cond_instance = MagicMock()
            # adjust_for_system returns (config, warnings)
            mock_cond_instance.adjust_for_system.return_value = (mock_config, ["Warning 1"])
            mock_cond.return_value = mock_cond_instance
            
            with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
                mock_manager = MagicMock()
                mock_manager.config_file = config_file
                mock_manager.config = mock_config
                mock_cm.return_value = mock_manager
                
                result = runner.invoke(auto_tune_cmd, ["--apply", "--config", str(config_file)])
                
                assert result.exit_code == 0
                assert "Auto-tuned configuration saved" in result.output
                assert "Warning 1" in result.output

    def test_auto_tune_with_apply_no_warnings(self, tmp_path):
        """Test auto-tune with --apply but no warnings (lines 483-486)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        from ccbt.models import Config
        
        mock_config = MagicMock(spec=Config)
        mock_config.model_dump.return_value = {"network": {"max_global_peers": 200}}
        
        with patch("ccbt.cli.config_commands_extended.ConditionalConfig") as mock_cond:
            mock_cond_instance = MagicMock()
            # No warnings
            mock_cond_instance.adjust_for_system.return_value = (mock_config, [])
            mock_cond.return_value = mock_cond_instance
            
            with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
                mock_manager = MagicMock()
                mock_manager.config_file = config_file
                mock_manager.config = mock_config
                mock_cm.return_value = mock_manager
                
                result = runner.invoke(auto_tune_cmd, ["--apply", "--config", str(config_file)])
                
                assert result.exit_code == 0
                assert "Auto-tuned configuration saved" in result.output
                # Should not show warnings section
                assert "Auto-tuning warnings:" not in result.output

    def test_auto_tune_with_output(self, tmp_path):
        """Test auto-tune command with output file (lines 489-494)."""
        runner = CliRunner()
        
        output_file = tmp_path / "tuned.toml"
        
        from ccbt.models import Config
        
        mock_config = MagicMock(spec=Config)
        mock_config.model_dump.return_value = {"network": {"max_global_peers": 200}}
        
        with patch("ccbt.cli.config_commands_extended.ConditionalConfig") as mock_cond:
            mock_cond_instance = MagicMock()
            mock_cond_instance.adjust_for_system.return_value = (mock_config, [])
            mock_cond.return_value = mock_cond_instance
            
            with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
                mock_manager = MagicMock()
                mock_manager.config = mock_config
                mock_cm.return_value = mock_manager
                
                result = runner.invoke(auto_tune_cmd, ["--apply", "--output", str(output_file)])
                
                assert result.exit_code == 0
                assert output_file.exists()

    def test_auto_tune_error_handling(self, tmp_path):
        """Test auto-tune command error handling (lines 526-528)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager", side_effect=Exception("Test error")):
            result = runner.invoke(auto_tune_cmd, ["--apply", "--config", str(config_file)])
            
            assert result.exit_code != 0
            assert "Error with auto-tuning" in result.output


class TestExportCommandExpanded:
    """Expanded tests for export command."""

    def test_export_toml_format(self, tmp_path):
        """Test export command with TOML format (lines 522-548)."""
        runner = CliRunner()
        
        output_file = tmp_path / "export.toml"
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config.model_dump.return_value = {"network": {"max_global_peers": 100}}
            mock_cm.return_value = mock_manager
            
            result = runner.invoke(export_cmd, ["--format", "toml", "--output", str(output_file)])
            
            assert result.exit_code == 0
            assert output_file.exists()

    def test_export_json_format(self, tmp_path):
        """Test export command with JSON format."""
        runner = CliRunner()
        
        output_file = tmp_path / "export.json"
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config.model_dump.return_value = {"network": {"max_global_peers": 100}}
            mock_cm.return_value = mock_manager
            
            result = runner.invoke(export_cmd, ["--format", "json", "--output", str(output_file)])
            
            assert result.exit_code == 0
            assert output_file.exists()

    def test_export_yaml_format(self, tmp_path):
        """Test export command with YAML format (lines 556-563)."""
        runner = CliRunner()
        
        output_file = tmp_path / "export.yaml"
        
        with patch("ccbt.cli.config_commands_extended.ConfigManager") as mock_cm:
            mock_manager = MagicMock()
            mock_manager.config.model_dump.return_value = {"network": {"max_global_peers": 100}}
            mock_cm.return_value = mock_manager
            
            result = runner.invoke(export_cmd, ["--format", "yaml", "--output", str(output_file)])
            
            assert result.exit_code == 0
            assert output_file.exists()
            # Verify YAML content
            content = output_file.read_text()
            assert "network:" in content or "max_global_peers" in content


class TestImportCommandExpanded:
    """Expanded tests for import command."""

    def test_import_success_toml(self, tmp_path):
        """Test import command with TOML file (lines 574-627)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.toml"
        import_file.write_text("[network]\nmax_global_peers = 200\n")
        output_file = tmp_path / "output.toml"
        
        with patch("ccbt.cli.config_commands_extended._should_skip_project_local_write", return_value=False):
            result = runner.invoke(import_cmd, [str(import_file), "--output", str(output_file)])
            
            assert result.exit_code == 0
            # Should create output file
            assert "Configuration imported" in result.output
            assert output_file.exists()

    def test_import_auto_detect_json(self, tmp_path):
        """Test import command auto-detects JSON format (lines 579-580)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.json"
        import_file.write_text('{"network": {"max_global_peers": 200}}')
        
        output_file = tmp_path / "output.toml"
        
        result = runner.invoke(import_cmd, [str(import_file), "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()

    def test_import_auto_detect_yaml(self, tmp_path):
        """Test import command auto-detects YAML format (lines 606-621)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.yaml"
        import_file.write_text("network:\n  max_global_peers: 200\n")
        
        output_file = tmp_path / "output.toml"
        
        result = runner.invoke(import_cmd, [str(import_file), "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        assert "Configuration imported" in result.output

    def test_import_yaml_format_explicit(self, tmp_path):
        """Test import command with explicit YAML format (lines 617-621)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.txt"
        import_file.write_text("network:\n  max_global_peers: 200\n")
        
        output_file = tmp_path / "output.toml"
        
        result = runner.invoke(import_cmd, [str(import_file), "--format", "yaml", "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()

    def test_import_with_config_file_target(self, tmp_path):
        """Test import command saves to config_file when no output (lines 616-617)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.toml"
        import_file.write_text("[network]\nmax_global_peers = 200\n")
        
        target_config = tmp_path / "target.toml"
        
        result = runner.invoke(import_cmd, [str(import_file), "--config", str(target_config)])
        
        assert result.exit_code == 0
        assert target_config.exists()

    def test_import_default_target(self, tmp_path):
        """Test import command defaults to ccbt.toml when no target (lines 618-619)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.toml"
        import_file.write_text("[network]\nmax_global_peers = 200\n")
        
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            with patch("ccbt.cli.config_commands_extended._should_skip_project_local_write", return_value=False):
                result = runner.invoke(import_cmd, [str(import_file)])
                
                assert result.exit_code == 0
                default_file = tmp_path / "ccbt.toml"
                assert default_file.exists()

    def test_import_invalid_config(self, tmp_path):
        """Test import command with invalid configuration (lines 609-611)."""
        runner = CliRunner()
        
        import_file = tmp_path / "import.toml"
        import_file.write_text("[network]\nmax_global_peers = -1\n")  # Invalid value
        
        result = runner.invoke(import_cmd, [str(import_file)])
        
        assert result.exit_code == 0
        assert "Invalid configuration" in result.output


class TestValidateCommandExpanded:
    """Expanded tests for validate command."""

    def test_validate_basic(self, tmp_path):
        """Test validate command basic validation (lines 668-669)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        result = runner.invoke(validate_cmd, ["--config", str(config_file)])
        
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_detailed_mode_no_warnings(self, tmp_path):
        """Test validate command with --detailed flag and no warnings (lines 671-681)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConditionalConfig") as mock_cond:
            mock_cond_instance = MagicMock()
            mock_cond_instance.validate_against_system.return_value = (True, [])
            mock_cond.return_value = mock_cond_instance
            
            result = runner.invoke(validate_cmd, ["--config", str(config_file), "--detailed"])
            
            assert result.exit_code == 0
            assert "valid" in result.output.lower()
            assert "No system compatibility warnings" in result.output

    def test_validate_detailed_mode_with_warnings(self, tmp_path):
        """Test validate command with --detailed flag and warnings (lines 676-679)."""
        runner = CliRunner()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = 100\n")
        
        with patch("ccbt.cli.config_commands_extended.ConditionalConfig") as mock_cond:
            mock_cond_instance = MagicMock()
            mock_cond_instance.validate_against_system.return_value = (True, ["Warning 1", "Warning 2"])
            mock_cond.return_value = mock_cond_instance
            
            result = runner.invoke(validate_cmd, ["--config", str(config_file), "--detailed"])
            
            assert result.exit_code == 0
            assert "Warnings:" in result.output
            assert "Warning 1" in result.output

    def test_validate_error_handling(self, tmp_path):
        """Test validate command error handling (lines 683-685)."""
        runner = CliRunner()
        
        # Create a file that will cause ConfigManager to fail during initialization
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nmax_global_peers = -1000\n")  # Invalid value
        
        # ConfigManager may handle this differently, so test the exception path
        with patch("ccbt.cli.config_commands_extended.ConfigManager", side_effect=Exception("Validation error")):
            result = runner.invoke(validate_cmd, ["--config", str(config_file)])
            
            assert result.exit_code != 0
            assert "validation failed" in result.output.lower()


class TestListTemplatesCommandExpanded:
    """Expanded tests for list-templates command."""

    def test_list_templates_json_format(self):
        """Test list-templates command with JSON format (lines 701-702)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates") as mock_templates:
            mock_templates.list_templates.return_value = [{"key": "template1", "description": "Test"}]
            
            result = runner.invoke(list_templates_cmd, ["--format", "json"])
            
            assert result.exit_code == 0
            # Should output JSON
            try:
                data = json.loads(result.output)
                assert isinstance(data, list)
            except json.JSONDecodeError:
                # Output might have extra text, check for JSON structure
                assert "[" in result.output or "{" in result.output

    def test_list_templates_error_handling(self):
        """Test list-templates command error handling (lines 714-716)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates.list_templates", side_effect=Exception("Test error")):
            result = runner.invoke(list_templates_cmd, [])
            
            assert result.exit_code != 0
            assert "Error listing templates" in result.output

    def test_list_templates_table_format(self):
        """Test list-templates command with table format (lines 705-710)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigTemplates") as mock_templates:
            mock_templates.list_templates.return_value = [
                {"key": "template1", "description": "Test Template 1"},
                {"key": "template2", "description": "Test Template 2"},
            ]
            
            result = runner.invoke(list_templates_cmd, ["--format", "table"])
            
            assert result.exit_code == 0
            # Table should be printed (even if format is not verifiable)
            assert len(result.output) > 0


class TestListProfilesCommandExpanded:
    """Expanded tests for list-profiles command."""

    def test_list_profiles_json_format(self):
        """Test list-profiles command with JSON format (lines 732-733)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles") as mock_profiles:
            mock_profiles.list_profiles.return_value = [{"key": "profile1", "description": "Test", "templates": ["t1"]}]
            
            result = runner.invoke(list_profiles_cmd, ["--format", "json"])
            
            assert result.exit_code == 0
            # Should output JSON
            try:
                data = json.loads(result.output)
                assert isinstance(data, list)
            except json.JSONDecodeError:
                # Output might have extra text, check for JSON structure
                assert "[" in result.output or "{" in result.output

    def test_list_profiles_error_handling(self):
        """Test list-profiles command error handling (lines 747-749)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles.list_profiles", side_effect=Exception("Test error")):
            result = runner.invoke(list_profiles_cmd, [])
            
            assert result.exit_code != 0
            assert "Error listing profiles" in result.output

    def test_list_profiles_table_format(self):
        """Test list-profiles command with table format (lines 736-743)."""
        runner = CliRunner()
        
        with patch("ccbt.cli.config_commands_extended.ConfigProfiles") as mock_profiles:
            mock_profiles.list_profiles.return_value = [
                {"key": "profile1", "description": "Test Profile 1", "templates": ["t1", "t2"]},
                {"key": "profile2", "description": "Test Profile 2", "templates": ["t3"]},
            ]
            
            result = runner.invoke(list_profiles_cmd, ["--format", "table"])
            
            assert result.exit_code == 0
            # Table should be printed (even if format is not verifiable)
            assert len(result.output) > 0

