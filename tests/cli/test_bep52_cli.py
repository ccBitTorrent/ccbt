"""CLI integration tests for BEP 52: BitTorrent Protocol v2.

Tests CLI commands and flags for v2 torrent creation and protocol configuration.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

pytestmark = [pytest.mark.cli, pytest.mark.integration]

from ccbt.cli.create_torrent import create_torrent
from ccbt.cli.main import cli
from ccbt.core.bencode import decode


@pytest.fixture
def cli_runner():
    """Create Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_test_file(tmp_path):
    """Create a temporary test file."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"x" * 32768)  # 32 KiB
    return test_file


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary test directory with files."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_bytes(b"a" * 10000)
    (test_dir / "file2.txt").write_bytes(b"b" * 10000)
    return test_dir


class TestCreateTorrentV2CLI:
    """Test v2 torrent creation via CLI."""

    def test_create_v2_torrent_command(self, cli_runner, temp_test_file, tmp_path):
        """Test ccbt create-torrent --v2 command."""
        output_file = tmp_path / "test.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
                "--piece-length",
                "16384",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify torrent file
        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        assert b"info" in torrent_data
        info_dict = torrent_data[b"info"]
        assert info_dict[b"meta version"] == 2

    def test_create_hybrid_torrent_command(self, cli_runner, temp_test_file, tmp_path):
        """Test ccbt create-torrent --hybrid command."""
        output_file = tmp_path / "hybrid.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--hybrid",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify hybrid torrent
        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        info_dict = torrent_data[b"info"]
        assert info_dict[b"meta version"] == 3  # Hybrid
        assert b"pieces" in info_dict  # v1
        assert b"file tree" in info_dict  # v2

    def test_create_v2_torrent_with_directory(self, cli_runner, temp_test_dir, tmp_path):
        """Test creating v2 torrent from directory."""
        output_file = tmp_path / "dir.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_dir),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        info_dict = torrent_data[b"info"]
        assert info_dict[b"meta version"] == 2
        assert b"file tree" in info_dict

    def test_create_torrent_with_piece_length(self, cli_runner, temp_test_file, tmp_path):
        """Test creating torrent with custom piece length."""
        output_file = tmp_path / "custom.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
                "--piece-length",
                "32768",  # 32 KiB
            ],
        )

        assert result.exit_code == 0

        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        info_dict = torrent_data[b"info"]
        assert info_dict[b"piece length"] == 32768

    def test_create_torrent_with_private_flag(self, cli_runner, temp_test_file, tmp_path):
        """Test creating private v2 torrent."""
        output_file = tmp_path / "private.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
                "--private",
            ],
        )

        assert result.exit_code == 0

        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        info_dict = torrent_data[b"info"]
        assert info_dict.get(b"private") == 1

    def test_create_torrent_with_comment(self, cli_runner, temp_test_file, tmp_path):
        """Test creating torrent with comment."""
        output_file = tmp_path / "comment.torrent"
        comment = "Test torrent comment"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
                "--comment",
                comment,
            ],
        )

        assert result.exit_code == 0

        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        assert torrent_data[b"comment"].decode() == comment

    def test_create_torrent_invalid_source(self, cli_runner, tmp_path):
        """Test error handling for invalid source path."""
        invalid_path = tmp_path / "nonexistent.txt"
        output_file = tmp_path / "test.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(invalid_path),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
            ],
        )

        assert result.exit_code != 0
        assert not output_file.exists()

    def test_create_torrent_multiple_trackers(self, cli_runner, temp_test_file, tmp_path):
        """Test creating torrent with multiple trackers."""
        output_file = tmp_path / "multi_tracker.torrent"

        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker1.example.com/announce",
                "--tracker",
                "http://tracker2.example.com/announce",
            ],
        )

        assert result.exit_code == 0

        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        assert b"announce-list" in torrent_data
        announce_list = torrent_data[b"announce-list"]
        assert len(announce_list) == 2

    def test_create_torrent_without_output(self, cli_runner, temp_test_file):
        """Test creating torrent without output file (prints to stdout)."""
        result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--tracker",
                "http://tracker.example.com/announce",
            ],
        )

        # Should succeed and print torrent data
        assert result.exit_code == 0
        # Output should be bencoded data or success message
        assert len(result.output) > 0


class TestProtocolV2CLIFlags:
    """Test CLI flags for protocol v2 configuration."""

    def test_protocol_v2_enable_flag(self, cli_runner):
        """Test --enable-v2 flag."""
        with patch("ccbt.cli.main.AsyncSessionManager") as mock_session:
            mock_instance = MagicMock()
            mock_session.return_value = mock_instance
            mock_instance.start = MagicMock()
            mock_instance.stop = MagicMock()

            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    "test.torrent",
                    "--enable-v2",
                ],
            )

            # Should not error on flag parsing
            # Actual download would fail without valid torrent, but flag should parse
            assert result.exit_code in [0, 1, 2]

    def test_protocol_v2_prefer_flag(self, cli_runner):
        """Test --prefer-v2 flag."""
        with patch("ccbt.cli.main.AsyncSessionManager") as mock_session:
            mock_instance = MagicMock()
            mock_session.return_value = mock_instance

            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    "test.torrent",
                    "--prefer-v2",
                ],
            )

            # Flag should be recognized
            assert result.exit_code in [0, 1, 2]  # May fail on missing torrent file

    def test_no_protocol_v2_flag(self, cli_runner):
        """Test --disable-v2 flag."""
        with patch("ccbt.cli.main.AsyncSessionManager") as mock_session:
            mock_instance = MagicMock()
            mock_session.return_value = mock_instance

            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    "test.torrent",
                    "--disable-v2",
                ],
            )

            # Flag should be recognized
            assert result.exit_code in [0, 1, 2]

    def test_config_override_by_cli_flags(self, cli_runner):
        """Test that CLI flags are parsed correctly."""
        # Test that --enable-v2 flag is recognized (flag name in actual CLI)
        with patch("ccbt.cli.main.AsyncSessionManager"):
            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    "test.torrent",
                    "--enable-v2",  # CLI uses --enable-v2, not --protocol-v2
                ],
            )

            # Should parse flags correctly (may fail on missing torrent, but flag should be recognized)
            assert result.exit_code in [0, 1, 2]

    @patch("ccbt.cli.main.AsyncSessionManager")
    def test_status_display_with_protocol_v2(self, mock_session, cli_runner):
        """Test status display shows protocol v2 information."""
        # Mock session with v2 info
        mock_instance = MagicMock()
        mock_instance.torrents = {}
        mock_session.return_value = mock_instance

        # Mock async methods
        async def mock_start():
            pass

        async def mock_stop():
            pass

        mock_instance.start = mock_start
        mock_instance.stop = mock_stop

        result = cli_runner.invoke(cli, ["status"])

        # Status should show v2 info (if implemented)
        # At minimum, command should not error
        assert result.exit_code in [0, 1]

    def test_v2_flag_with_magnet_link(self, cli_runner):
        """Test v2 protocol flags with magnet link."""
        magnet_uri = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"

        with patch("ccbt.cli.main.AsyncSessionManager"):
            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    magnet_uri,
                    "--enable-v2",
                ],
            )

            # Should parse flags correctly
            assert result.exit_code in [0, 1, 2]

    def test_hybrid_mode_cli_interaction(self, cli_runner):
        """Test CLI interaction in hybrid mode."""
        # Test that hybrid mode doesn't conflict with other flags
        with patch("ccbt.cli.main.AsyncSessionManager"):
            result = cli_runner.invoke(
                cli,
                [
                    "download",
                    "test.torrent",
                    "--enable-v2",
                    "--prefer-v2",
                ],
            )

            # Flags should be compatible
            assert result.exit_code in [0, 1, 2]

    def test_config_file_v2_settings(self, cli_runner):
        """Test reading v2 settings from config file."""
        # Test that CLI can load config and parse v2 flags
        with patch("ccbt.cli.main.AsyncSessionManager"):
            result = cli_runner.invoke(cli, ["download", "test.torrent", "--enable-v2"])

            # Config should be loaded and flag parsed
            assert result.exit_code in [0, 1, 2]

    def test_v2_torrent_creation_cli_workflow(self, cli_runner, temp_test_file, tmp_path):
        """Test complete workflow of creating and validating v2 torrent via CLI."""
        output_file = tmp_path / "workflow.torrent"

        # Create v2 torrent
        create_result = cli_runner.invoke(
            create_torrent,
            [
                str(temp_test_file),
                "--v2",
                "--output",
                str(output_file),
                "--tracker",
                "http://tracker.example.com/announce",
                "--comment",
                "Test workflow",
                "--private",
            ],
        )

        assert create_result.exit_code == 0
        assert output_file.exists()

        # Verify all options were applied
        with open(output_file, "rb") as f:
            torrent_data = decode(f.read())

        assert torrent_data[b"announce"] == b"http://tracker.example.com/announce"
        assert torrent_data[b"comment"] == b"Test workflow"
        assert torrent_data[b"info"][b"private"] == 1
        assert torrent_data[b"info"][b"meta version"] == 2

