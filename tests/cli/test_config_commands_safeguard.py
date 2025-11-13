"""Tests for config commands safeguard functions.

Tests the _find_project_root and _should_skip_project_local_write functions
to ensure they properly protect the project root ccbt.toml file during tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ccbt.cli.config_commands import (
    _find_project_root,
    _should_skip_project_local_write,
    set_value,
)


@pytest.mark.unit
@pytest.mark.cli
class TestFindProjectRoot:
    """Tests for _find_project_root function."""

    def test_find_project_root_from_project_root(self, tmp_path):
        """Test finding project root when starting from project root."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / "ccbt.toml").write_text("[network]")
        
        root = _find_project_root(project_root)
        assert root == project_root

    def test_find_project_root_from_subdirectory(self, tmp_path):
        """Test finding project root when starting from a subdirectory."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / "ccbt.toml").write_text("[network]")
        subdir = project_root / "ccbt" / "cli"
        subdir.mkdir(parents=True)
        
        root = _find_project_root(subdir)
        assert root == project_root

    def test_find_project_root_by_git(self, tmp_path):
        """Test finding project root by .git directory."""
        # Create a mock project structure with .git instead of pyproject.toml
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "ccbt.toml").write_text("[network]")
        subdir = project_root / "ccbt" / "cli"
        subdir.mkdir(parents=True)
        
        root = _find_project_root(subdir)
        assert root == project_root

    def test_find_project_root_not_found(self, tmp_path):
        """Test when project root cannot be found."""
        # Create a directory without project markers
        some_dir = tmp_path / "random_dir"
        some_dir.mkdir()
        
        root = _find_project_root(some_dir)
        assert root is None

    def test_find_project_root_from_current_dir(self):
        """Test finding project root from current directory (should find actual project)."""
        root = _find_project_root()
        # Should find the actual project root (where pyproject.toml exists)
        assert root is not None
        assert (root / "pyproject.toml").exists() or (root / ".git").exists()


@pytest.mark.unit
@pytest.mark.cli
class TestShouldSkipProjectLocalWrite:
    """Tests for _should_skip_project_local_write function."""

    def test_skip_write_to_project_root_in_test_mode(self, tmp_path, monkeypatch):
        """Test that writes to project root ccbt.toml are skipped during tests."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        project_config.write_text("[network]\nmax_global_peers = 200\n")
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Mock _find_project_root to return our test project root
        with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
            should_skip = _should_skip_project_local_write(
                config_file=project_config,
                explicit_config_file=None
            )
            assert should_skip is True

    def test_allow_write_to_temp_directory_in_test_mode(self, tmp_path, monkeypatch):
        """Test that writes to temp directories are allowed during tests."""
        # Create a temp directory (not project root)
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_config = temp_dir / "ccbt.toml"
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Mock _find_project_root to return a different project root
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        
        with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
            should_skip = _should_skip_project_local_write(
                config_file=temp_config,
                explicit_config_file=None
            )
            assert should_skip is False

    def test_allow_write_when_not_in_test_mode(self, tmp_path, monkeypatch):
        """Test that writes are allowed when not in test mode."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        
        # Don't set test mode
        monkeypatch.delenv("CCBT_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        
        with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
            should_skip = _should_skip_project_local_write(
                config_file=project_config,
                explicit_config_file=None
            )
            assert should_skip is False

    def test_allow_write_with_explicit_config_file(self, tmp_path, monkeypatch):
        """Test that writes are allowed when explicit config file is provided."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Explicit config file should bypass safeguard
        with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
            should_skip = _should_skip_project_local_write(
                config_file=project_config,
                explicit_config_file=str(project_config)
            )
            assert should_skip is False

    def test_handle_project_root_not_found(self, tmp_path, monkeypatch):
        """Test behavior when project root cannot be found."""
        temp_config = tmp_path / "ccbt.toml"
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Mock _find_project_root to return None
        with patch("ccbt.cli.config_commands._find_project_root", return_value=None):
            should_skip = _should_skip_project_local_write(
                config_file=temp_config,
                explicit_config_file=None
            )
            # Should allow write when project root can't be determined
            assert should_skip is False

    def test_handle_exception_gracefully(self, tmp_path, monkeypatch):
        """Test that exceptions in safeguard are handled gracefully."""
        temp_config = tmp_path / "ccbt.toml"
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Mock _find_project_root to raise an exception
        with patch("ccbt.cli.config_commands._find_project_root", side_effect=Exception("Test error")):
            should_skip = _should_skip_project_local_write(
                config_file=temp_config,
                explicit_config_file=None
            )
            # Should allow write when exception occurs
            assert should_skip is False

    def test_skip_write_with_relative_path(self, tmp_path, monkeypatch):
        """Test safeguard with relative path config_file."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            relative_config = Path("ccbt.toml")
            
            # Mock _find_project_root to return project root from relative path
            def mock_find_project_root(start_path=None):
                if start_path is None:
                    return project_root
                # When called from config_file.parent, should find project root
                if str(start_path).replace("\\", "/") in str(project_root).replace("\\", "/"):
                    return project_root
                return None
            
            with patch("ccbt.cli.config_commands._find_project_root", side_effect=mock_find_project_root):
                should_skip = _should_skip_project_local_write(
                    config_file=relative_config,
                    explicit_config_file=None
                )
                assert should_skip is True
        finally:
            os.chdir(original_cwd)

    def test_skip_write_with_absolute_path_from_subdirectory(self, tmp_path, monkeypatch):
        """Test safeguard finds project root from config_file's directory."""
        # Create a mock project structure with subdirectory
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        subdir = project_root / "subdir"
        subdir.mkdir()
        
        # Set test mode
        monkeypatch.setenv("CCBT_TEST_MODE", "1")
        
        # Mock _find_project_root to return None from cwd, but project root from config_file.parent
        call_count = [0]
        def mock_find_project_root(start_path=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call from cwd - return None to test alt_root path
                return None
            # Second call from config_file.parent - return project root
            if start_path and str(start_path).replace("\\", "/") in str(project_root).replace("\\", "/"):
                return project_root
            return project_root
        
        with patch("ccbt.cli.config_commands._find_project_root", side_effect=mock_find_project_root):
            should_skip = _should_skip_project_local_write(
                config_file=project_config,
                explicit_config_file=None
            )
            assert should_skip is True


@pytest.mark.unit
@pytest.mark.cli
class TestSafeguardIntegration:
    """Integration tests for safeguard in actual commands."""

    def test_set_value_protects_project_root(self, tmp_path, monkeypatch):
        """Test that set_value command protects project root ccbt.toml."""
        # Create a mock project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        project_config = project_root / "ccbt.toml"
        project_config.write_text("[network]\nmax_global_peers = 200\n")
        
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            
            # Set test mode
            monkeypatch.setenv("CCBT_TEST_MODE", "1")
            
            # Mock _find_project_root to return our test project root
            with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
                runner = CliRunner()
                result = runner.invoke(set_value, [
                    "network.listen_port", "8080"
                ])
                
                # Should succeed but not actually write (safeguard should prevent it)
                assert result.exit_code == 0
                assert "OK" in result.output
                
                # Verify the file was NOT modified
                content = project_config.read_text()
                assert "listen_port" not in content
                assert "max_global_peers = 200" in content
                
        finally:
            os.chdir(original_cwd)

    def test_set_value_allows_temp_directory_write(self, tmp_path, monkeypatch):
        """Test that set_value allows writes to temp directories."""
        # Create a temp directory (not project root)
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            
            # Set test mode
            monkeypatch.setenv("CCBT_TEST_MODE", "1")
            
            # Mock the project root to be somewhere else
            project_root = tmp_path / "project"
            project_root.mkdir()
            (project_root / "pyproject.toml").write_text("[project]")
            
            with patch("ccbt.cli.config_commands._find_project_root", return_value=project_root):
                runner = CliRunner()
                result = runner.invoke(set_value, [
                    "network.listen_port", "8080"
                ])
                
                # Should succeed and write
                assert result.exit_code == 0
                temp_config = temp_dir / "ccbt.toml"
                assert temp_config.exists()
                
                import toml
                data = toml.load(str(temp_config))
                assert data["network"]["listen_port"] == 8080
                
        finally:
            os.chdir(original_cwd)

