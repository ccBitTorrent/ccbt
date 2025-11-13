"""Tests to cover uncovered lines in config_commands_extended.py.

Covers:
- Template apply file write (lines 219-221)
- Profile apply file write (lines 293-295)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import toml
from click.testing import CliRunner

from ccbt.cli.config_commands_extended import profile_cmd, template_cmd

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestTemplateApplyFileWrite:
    """Tests for template apply file write operations (lines 219-221)."""

    def test_template_apply_writes_file(self, tmp_path, monkeypatch):
        """Test template apply writes file when _should_skip_project_local_write returns False."""
        runner = CliRunner()
        
        # Change to tmp_path so we can write ccbt.toml there
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Mock the safeguard to allow file write
            with patch(
                "ccbt.cli.config_commands_extended._should_skip_project_local_write",
                return_value=False
            ):
                # Mock template operations
                template_config = {"network": {"max_global_peers": 200}}
                applied_config = {"network": {"max_global_peers": 200}}
                
                with patch(
                    "ccbt.cli.config_commands_extended.ConfigTemplates.validate_template",
                    return_value=(True, [])
                ):
                    with patch(
                        "ccbt.cli.config_commands_extended.ConfigTemplates.get_template",
                        return_value=template_config
                    ):
                        with patch(
                            "ccbt.cli.config_commands_extended.ConfigTemplates.apply_template",
                            return_value=applied_config
                        ):
                            with patch(
                                "ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES",
                                {"test-template": {"name": "Test", "description": "Test"}}
                            ):
                                result = runner.invoke(
                                    template_cmd,
                                    ["test-template", "--apply"]
                                )
                                
                                assert result.exit_code == 0
                                assert "applied" in result.output.lower()
                                
                                # Verify file was written (line 220)
                                config_file = tmp_path / "ccbt.toml"
                                assert config_file.exists(), "Config file should be created"
                                
                                # Verify file content (line 220)
                                data = toml.load(str(config_file))
                                assert data["network"]["max_global_peers"] == 200
                                
                                # Verify success message (line 221)
                                assert "Template applied" in result.output
        finally:
            os.chdir(original_cwd)

    def test_template_apply_with_output_file(self, tmp_path):
        """Test template apply with explicit output file path."""
        runner = CliRunner()
        
        output_file = tmp_path / "custom_config.toml"
        
        # Mock the safeguard to allow file write
        with patch(
            "ccbt.cli.config_commands_extended._should_skip_project_local_write",
            return_value=False
        ):
            # Mock template operations
            template_config = {"network": {"max_global_peers": 300}}
            applied_config = {"network": {"max_global_peers": 300}}
            
            with patch(
                "ccbt.cli.config_commands_extended.ConfigTemplates.validate_template",
                return_value=(True, [])
            ):
                with patch(
                    "ccbt.cli.config_commands_extended.ConfigTemplates.get_template",
                    return_value=template_config
                ):
                    with patch(
                        "ccbt.cli.config_commands_extended.ConfigTemplates.apply_template",
                        return_value=applied_config
                    ):
                        with patch(
                            "ccbt.cli.config_commands_extended.ConfigTemplates.TEMPLATES",
                            {"test-template": {"name": "Test", "description": "Test"}}
                        ):
                            result = runner.invoke(
                                template_cmd,
                                ["test-template", "--apply", "--output", str(output_file)]
                            )
                            
                            assert result.exit_code == 0
                            
                            # Verify file was written with parent directory creation (line 219)
                            assert output_file.exists(), "Output file should be created"
                            assert output_file.parent.exists(), "Parent directory should be created"
                            
                            # Verify file content (line 220)
                            data = toml.load(str(output_file))
                            assert data["network"]["max_global_peers"] == 300
                            
                            # Verify success message (line 221)
                            assert f"Template applied to {output_file}" in result.output


class TestProfileApplyFileWrite:
    """Tests for profile apply file write operations (lines 293-295)."""

    def test_profile_apply_writes_file(self, tmp_path, monkeypatch):
        """Test profile apply writes file when _should_skip_project_local_write returns False."""
        runner = CliRunner()
        
        # Change to tmp_path so we can write ccbt.toml there
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # Mock the safeguard to allow file write
            with patch(
                "ccbt.cli.config_commands_extended._should_skip_project_local_write",
                return_value=False
            ):
                # Mock profile operations
                profile_config = {"network": {"max_global_peers": 250}}
                applied_config = {"network": {"max_global_peers": 250}}
                
                with patch(
                    "ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile",
                    return_value=(True, [])
                ):
                    with patch(
                        "ccbt.cli.config_commands_extended.ConfigProfiles.get_profile",
                        return_value=profile_config
                    ):
                        with patch(
                            "ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile",
                            return_value=applied_config
                        ):
                            with patch(
                                "ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES",
                                {"test-profile": {"name": "Test", "description": "Test", "templates": ["t1"]}}
                            ):
                                result = runner.invoke(
                                    profile_cmd,
                                    ["test-profile", "--apply"]
                                )
                                
                                assert result.exit_code == 0
                                assert "applied" in result.output.lower()
                                
                                # Verify file was written (line 294)
                                config_file = tmp_path / "ccbt.toml"
                                assert config_file.exists(), "Config file should be created"
                                
                                # Verify file content (line 294)
                                data = toml.load(str(config_file))
                                assert data["network"]["max_global_peers"] == 250
                                
                                # Verify success message (line 295)
                                assert "Profile applied" in result.output
        finally:
            os.chdir(original_cwd)

    def test_profile_apply_with_output_file(self, tmp_path):
        """Test profile apply with explicit output file path."""
        runner = CliRunner()
        
        output_file = tmp_path / "profile_config.toml"
        
        # Mock the safeguard to allow file write
        with patch(
            "ccbt.cli.config_commands_extended._should_skip_project_local_write",
            return_value=False
        ):
            # Mock profile operations
            profile_config = {"network": {"max_global_peers": 350}}
            applied_config = {"network": {"max_global_peers": 350}}
            
            with patch(
                "ccbt.cli.config_commands_extended.ConfigProfiles.validate_profile",
                return_value=(True, [])
            ):
                with patch(
                    "ccbt.cli.config_commands_extended.ConfigProfiles.get_profile",
                    return_value=profile_config
                ):
                    with patch(
                        "ccbt.cli.config_commands_extended.ConfigProfiles.apply_profile",
                        return_value=applied_config
                    ):
                        with patch(
                            "ccbt.cli.config_commands_extended.ConfigProfiles.PROFILES",
                            {"test-profile": {"name": "Test", "description": "Test", "templates": ["t1"]}}
                        ):
                            result = runner.invoke(
                                profile_cmd,
                                ["test-profile", "--apply", "--output", str(output_file)]
                            )
                            
                            assert result.exit_code == 0
                            
                            # Verify file was written with parent directory creation (line 293)
                            assert output_file.exists(), "Output file should be created"
                            assert output_file.parent.exists(), "Parent directory should be created"
                            
                            # Verify file content (line 294)
                            data = toml.load(str(output_file))
                            assert data["network"]["max_global_peers"] == 350
                            
                            # Verify success message (line 295)
                            assert f"Profile applied to {output_file}" in result.output

