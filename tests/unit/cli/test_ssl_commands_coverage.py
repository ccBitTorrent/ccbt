"""Additional tests for SSL commands to improve coverage.

Covers:
- Path validation error handlers in ssl_set_ca_certs (lines 245-246, 249-252)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

cli_ssl_commands = __import__("ccbt.cli.ssl_commands", fromlist=["ssl"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestSSLPathValidationCoverage:
    """Tests for path validation error handlers in SSL commands."""

    def test_ssl_set_ca_certs_path_not_exists_coverage(self, monkeypatch, tmp_path):
        """Test SSL set-ca-certs with non-existent path (lines 245-246).

        We patch the Path methods at the point where they're called in the function.
        Since click.Path validates existence, we need to patch after click validation.
        """
        runner = CliRunner()

        # Create a real file first so click validates it
        test_path = tmp_path / "ca.pem"
        test_path.write_text("test")

        mock_ssl_config = SimpleNamespace()
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        # Patch Path.expanduser to return a path that doesn't exist
        # This simulates the case where expanduser returns a path that doesn't exist
        with patch("pathlib.Path.expanduser") as mock_expanduser:
            # Create a mock path that doesn't exist
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = False
            mock_path.__str__ = lambda self: str(test_path)
            mock_expanduser.return_value = mock_path

            # Use the real file path so click validates it
            result = runner.invoke(
                cli_ssl_commands.ssl, ["set-ca-certs", str(test_path)]
            )
            # The command should fail with our validation error
            assert result.exit_code != 0
            assert (
                "Path does not exist" in result.output
                or "does not exist" in result.output.lower()
            )

    def test_ssl_set_ca_certs_path_not_file_or_dir_coverage(self, monkeypatch, tmp_path):
        """Test SSL set-ca-certs with path that exists but is neither file nor directory (lines 249-252)."""
        runner = CliRunner()

        # Create a real file that click will validate
        test_path = tmp_path / "special_file"
        test_path.write_text("test")

        mock_ssl_config = SimpleNamespace()
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        # Patch Path methods to simulate special file (exists but not file/dir)
        with patch("pathlib.Path.expanduser") as mock_expanduser, patch(
            "pathlib.Path.exists", return_value=True
        ) as mock_exists, patch(
            "pathlib.Path.is_file", return_value=False
        ) as mock_is_file, patch(
            "pathlib.Path.is_dir", return_value=False
        ) as mock_is_dir:
            # Create a mock path that will be returned by expanduser
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True
            mock_path.is_file.return_value = False
            mock_path.is_dir.return_value = False
            mock_expanduser.return_value = mock_path

            # Invoke the command with a real file path
            result = runner.invoke(
                cli_ssl_commands.ssl, ["set-ca-certs", str(test_path)]
            )
            # The command should fail with the appropriate error
            assert result.exit_code != 0
            assert (
                "Path must be a file or directory" in result.output
                or "must be a file or directory" in result.output.lower()
            )

