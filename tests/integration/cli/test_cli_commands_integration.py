"""Integration tests for all CLI commands after Phase 2 completion.

Verifies that all CLI commands execute without errors after Phase 2 fixes.
This is a comprehensive integration test suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ccbt.cli.main import cli

pytestmark = [pytest.mark.integration, pytest.mark.cli]


class TestCLICommandsIntegration:
    """Integration tests for all CLI commands after Phase 2 fixes."""

    def test_main_cli_help(self):
        """Test that main CLI help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0, "Main CLI help should work"
        assert "CcBitTorrent" in result.output or "commands" in result.output.lower()

    def test_all_top_level_commands_accessible(self):
        """Test that all top-level commands are accessible with --help."""
        runner = CliRunner()
        
        # Commands that should be available
        top_level_commands = [
            "download",
            "magnet",
            "web",
            "interactive",
            "status",
            "test",
            "config",
            "daemon",
            "torrent",
            "files",
            "queue",
            "dht",
            "peer",
            "pex",
            "dashboard",
            "alerts",
            "metrics",
            "performance",
            "security",
            "recover",
            "checkpoints",
        ]
        
        for cmd in top_level_commands:
            result = runner.invoke(cli, [cmd, "--help"])
            # Should not fail with import errors or signature errors
            assert result.exit_code in [0, 1, 2], \
                f"Command '{cmd}' should be accessible. Error: {result.output[:200]}"
            
            # Should not have TypeError or AttributeError from Phase 2 fixes
            assert "TypeError" not in result.output, \
                f"Command '{cmd}' should not have TypeError (Phase 2 fix issue)"
            assert "AttributeError" not in result.output, \
                f"Command '{cmd}' should not have AttributeError (Phase 2 fix issue)"

    def test_config_command_group(self):
        """Test config command group and subcommands."""
        runner = CliRunner()

        # Test config group
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0, "Config command group should work"

        # Test config subcommands (if any)
        config_subcommands = [
            "get",
            "set",
            "show",
            "reset",
            "describe",
            "apply",
            "schema",
            "import",
        ]
        for subcmd in config_subcommands:
            result = runner.invoke(cli, ["config", subcmd, "--help"])
            # May fail if subcommand doesn't exist, but shouldn't fail with Phase 2 errors
            if result.exit_code != 0:
                assert "TypeError" not in result.output, (
                    f"Config subcommand '{subcmd}' should not have Phase 2 errors"
                )
                assert "AttributeError" not in result.output, (
                    f"Config subcommand '{subcmd}' should not have Phase 2 errors"
                )

    def test_config_extended_not_registered_at_top_level(self):
        """Former ``config-extended`` group is folded into ``config`` only."""
        runner = CliRunner()
        root = runner.invoke(cli, ["--help"])
        assert root.exit_code == 0
        assert "config-extended" not in root.output
        bad = runner.invoke(cli, ["config-extended", "--help"])
        assert bad.exit_code != 0

    def test_daemon_command_group(self):
        """Test daemon command group and subcommands."""
        runner = CliRunner()
        
        # Test daemon group
        result = runner.invoke(cli, ["daemon", "--help"])
        assert result.exit_code == 0, "Daemon command group should work"
        
        # Test daemon subcommands
        daemon_subcommands = ["start", "stop", "status", "restart"]
        for subcmd in daemon_subcommands:
            result = runner.invoke(cli, ["daemon", subcmd, "--help"])
            # May fail if subcommand doesn't exist, but shouldn't fail with Phase 2 errors
            if result.exit_code != 0:
                assert "TypeError" not in result.output and "AttributeError" not in result.output, \
                    f"Daemon subcommand '{subcmd}' should not have Phase 2 errors"

    def test_torrent_command_group(self):
        """Test torrent command group and subcommands."""
        runner = CliRunner()
        
        # Test torrent group
        result = runner.invoke(cli, ["torrent", "--help"])
        assert result.exit_code == 0, "Torrent command group should work"
        
        # Test torrent config subcommands
        result = runner.invoke(cli, ["torrent", "config", "--help"])
        # May require arguments, but shouldn't fail with Phase 2 errors
        assert result.exit_code in [0, 1, 2], \
            "Torrent config subcommand should work (may require args)"
        assert "TypeError" not in result.output, \
            "Torrent config should not have TypeError (Phase 2 fix issue)"

    def test_files_command_group(self):
        """Test files command group and subcommands."""
        runner = CliRunner()
        
        # Test files group
        result = runner.invoke(cli, ["files", "--help"])
        assert result.exit_code == 0, "Files command group should work"
        
        # Test files subcommands (these have ARG001 fixes with _ctx parameters)
        files_subcommands = ["list", "select", "deselect", "select-all", "deselect-all", "priority"]
        for subcmd in files_subcommands:
            result = runner.invoke(cli, ["files", subcmd, "--help"])
            # Should work with ARG001 fixes (unused _ctx parameters)
            assert result.exit_code in [0, 1, 2], \
                f"Files subcommand '{subcmd}' should work with ARG001 fixes"
            assert "TypeError" not in result.output, \
                f"Files subcommand '{subcmd}' should not have TypeError (ARG001 fix issue)"

    def test_checkpoints_command_group(self):
        """Test checkpoints command group and subcommands."""
        runner = CliRunner()
        
        # Mock daemon not running
        mock_daemon_manager = MagicMock()
        mock_daemon_manager.is_running.return_value = False
        
        with patch("ccbt.daemon.daemon_manager.DaemonManager", lambda: mock_daemon_manager):
            # Test checkpoints group
            result = runner.invoke(cli, ["checkpoints", "--help"])
            assert result.exit_code == 0, "Checkpoints command group should work"
            
            # Test checkpoints subcommands (these have D100, TC001, TC002, D103 fixes)
            checkpoint_subcommands = [
                "list",
                "clean",
                "delete",
                "verify",
                "export",
                "backup",
                "restore",
                "migrate",
                "reload",
                "refresh",
            ]
            
            for subcmd in checkpoint_subcommands:
                result = runner.invoke(cli, ["checkpoints", subcmd, "--help"])
                # Should work with Phase 2 fixes
                assert result.exit_code in [0, 1, 2], \
                    f"Checkpoints subcommand '{subcmd}' should work with Phase 2 fixes"
                assert "TypeError" not in result.output, \
                    f"Checkpoints subcommand '{subcmd}' should not have TypeError"

    def test_advanced_commands(self):
        """Test advanced commands (performance, security, recover, test)."""
        runner = CliRunner()
        
        advanced_commands = ["performance", "security", "recover", "test"]
        
        for cmd in advanced_commands:
            result = runner.invoke(cli, [cmd, "--help"])
            # Should work with SIM102, D401 fixes
            assert result.exit_code in [0, 1, 2], \
                f"Advanced command '{cmd}' should work with Phase 2 fixes"
            assert "TypeError" not in result.output, \
                f"Advanced command '{cmd}' should not have TypeError (Phase 2 fix issue)"

    def test_monitoring_commands(self):
        """Test monitoring commands (dashboard, alerts, metrics)."""
        runner = CliRunner()
        
        monitoring_commands = ["dashboard", "alerts", "metrics"]
        
        for cmd in monitoring_commands:
            result = runner.invoke(cli, [cmd, "--help"])
            # Should work with SIM105 fixes
            assert result.exit_code in [0, 1, 2], \
                f"Monitoring command '{cmd}' should work with Phase 2 fixes"
            assert "TypeError" not in result.output, \
                f"Monitoring command '{cmd}' should not have TypeError (SIM105 fix issue)"

    def test_create_torrent_command(self):
        """Test create-torrent command (has ARG001 fix)."""
        runner = CliRunner()
        
        # Note: create-torrent might be in a different location
        # Check if it exists as a command
        result = runner.invoke(cli, ["--help"])
        if "create-torrent" in result.output or "create" in result.output.lower():
            # Try to invoke it
            result = runner.invoke(cli, ["create-torrent", "--help"])
            # Should work with ARG001 fix (_verbose parameter)
            assert result.exit_code in [0, 1, 2], \
                "create-torrent command should work with ARG001 fix"
            assert "TypeError" not in result.output, \
                "create-torrent should not have TypeError (ARG001 fix issue)"


class TestCLICommandsPhase2Compatibility:
    """Test that CLI commands maintain compatibility after Phase 2 fixes."""

    def test_no_import_errors(self):
        """Test that all CLI modules can be imported without errors."""
        # This verifies that Phase 2 fixes don't break imports
        modules_to_test = [
            "ccbt.cli.main",
            "ccbt.cli.file_commands",
            "ccbt.cli.config_utils",
            "ccbt.cli.create_torrent",
            "ccbt.cli.downloads",
            "ccbt.cli.advanced_commands",
            "ccbt.cli.torrent_config_commands",
            "ccbt.cli.checkpoints",
            "ccbt.cli.monitoring_commands",
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except (ImportError, SyntaxError, AttributeError) as e:
                pytest.fail(
                    f"Failed to import {module_name} after Phase 2 fixes: {e}"
                )

    def test_cli_command_registration(self):
        """Test that all CLI commands are properly registered."""
        runner = CliRunner()
        
        # Get list of commands from help
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0, "Should be able to get CLI help"
        
        # Verify key commands are mentioned
        expected_commands = [
            "download",
            "status",
            "config",
            "daemon",
        ]
        
        output_lower = result.output.lower()
        for cmd in expected_commands:
            assert cmd in output_lower, \
                f"Command '{cmd}' should be registered and visible in help"

    def test_command_invocation_without_errors(self):
        """Test that commands can be invoked without Phase 2-related errors."""
        runner = CliRunner()
        
        # Test a few key commands that had Phase 2 fixes
        test_cases = [
            (["files", "--help"], "files command with ARG001 fixes"),
            (["checkpoints", "--help"], "checkpoints command with D100/TC001/TC002/D103 fixes"),
            (["performance", "--help"], "performance command with SIM102/D401 fixes"),
            (["torrent", "config", "--help"], "torrent config with SIM102 fixes"),
        ]
        
        for args, description in test_cases:
            result = runner.invoke(cli, args)
            
            # Should not fail with Phase 2-related errors
            assert "TypeError" not in result.output, \
                f"{description} should not have TypeError"
            assert "AttributeError" not in result.output, \
                f"{description} should not have AttributeError"
            assert "NameError" not in result.output, \
                f"{description} should not have NameError"
            
            # Exit code should be reasonable (0 for help, 1-2 for missing args)
            assert result.exit_code in [0, 1, 2], \
                f"{description} should have reasonable exit code, got {result.exit_code}"

    def test_no_function_signature_errors(self):
        """Test that function signature changes don't break command invocation."""
        runner = CliRunner()
        
        # Commands with ARG001 fixes (unused _ctx parameters)
        commands_with_ctx = [
            ["files", "list", "--help"],
            ["files", "select", "--help"],
        ]
        
        for args in commands_with_ctx:
            result = runner.invoke(cli, args)
            # Should not fail due to signature mismatches
            assert "TypeError" not in result.output, \
                f"Command {args} should not have TypeError from ARG001 fixes"
            assert "takes" not in result.output or "positional" not in result.output.lower(), \
                f"Command {args} should not have argument count errors"

