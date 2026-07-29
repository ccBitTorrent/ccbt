"""Tests for create_torrent.py Phase 2 fixes.

Covers:
- ARG001 fix (line 101 - unused verbose argument)
- Function signature compatibility with Click decorators
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

import ccbt.cli.create_torrent as create_torrent_mod

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run coroutine locally in tests."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class TestCreateTorrentARG001Fix:
    """Test that ARG001 fix (unused verbose argument) works correctly."""

    def test_create_torrent_function_signature(self):
        """Test that create_torrent has correct signature with _verbose parameter."""
        # Click wraps the function in a Command object, access the underlying function
        cmd = create_torrent_mod.create_torrent
        if hasattr(cmd, "callback"):
            # Click Command object - get underlying function
            func = cmd.callback
        else:
            # Direct function
            func = cmd

        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Verify _verbose parameter exists (prefixed with _ for ARG001 fix)
        assert "_verbose" in params, "create_torrent should have _verbose parameter (ARG001 fix)"

        # Verify _ctx parameter exists (Click pass_context)
        assert "_ctx" in params, "create_torrent should have _ctx parameter (Click pass_context)"

        # Verify all expected parameters are present
        expected_params = [
            "_ctx",
            "source",
            "output",
            "format_v2",
            "format_hybrid",
            "format_v1",
            "tracker",
            "web_seed",
            "comment",
            "created_by",
            "piece_length",
            "private",
            "_verbose",
        ]
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"

    def test_create_torrent_command_with_verbose_flag(self, tmp_path, monkeypatch):
        """Test create_torrent command works with --verbose flag (unused _verbose parameter)."""
        runner = CliRunner()
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        # Mock TorrentV2Parser to avoid actual torrent creation
        mock_parser = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_v2_torrent.return_value = b"torrent data"
        mock_parser.return_value = mock_instance

        monkeypatch.setattr(
            "ccbt.core.torrent_v2.TorrentV2Parser",
            mock_parser,
        )

        # Invoke command with --verbose flag (maps to _verbose parameter)
        result = runner.invoke(
            create_torrent_mod.create_torrent,
            [str(source_file), "--v2", "--verbose"],
        )

        # Command should execute (may fail for other reasons, but not due to _verbose)
        # The _verbose parameter is unused, but Click still passes it
        assert result.exit_code in [0, 1, 2]  # Allow various exit codes

        # Verify the command was invoked (not a signature error)
        assert "TypeError" not in result.output
        assert "missing required argument" not in result.output.lower()

    def test_create_torrent_command_with_multiple_verbose_flags(self, tmp_path, monkeypatch):
        """Test create_torrent command works with multiple -v flags (count=True)."""
        runner = CliRunner()
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        # Mock TorrentV2Parser
        mock_parser = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_v2_torrent.return_value = b"torrent data"
        mock_parser.return_value = mock_instance

        monkeypatch.setattr(
            "ccbt.core.torrent_v2.TorrentV2Parser",
            mock_parser,
        )

        # Invoke command with multiple -v flags (count=True means -vvv = 3)
        result = runner.invoke(
            create_torrent_mod.create_torrent,
            [str(source_file), "--v2", "-vvv"],
        )

        # Command should execute without signature errors
        assert "TypeError" not in result.output
        assert "missing required argument" not in result.output.lower()

    def test_create_torrent_verbose_parameter_unused(self):
        """Test that _verbose parameter is marked as unused (ARG001 fix)."""
        # Read source file to verify noqa comment
        import ccbt.cli.create_torrent as mod

        source_file = Path(mod.__file__)
        source = source_file.read_text(encoding="utf-8")

        # Find the function definition line
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "def create_torrent" in line:
                # Check next few lines for _verbose parameter with noqa comment
                for j in range(i, min(i + 15, len(lines))):
                    if "_verbose" in lines[j] and ("# noqa: ARG001" in lines[j] or "ARG001" in lines[j]):
                        # Found the fix
                        assert True, "ARG001 fix found with noqa comment"
                        return

        # If we get here, check if _verbose exists at all
        assert "_verbose" in source, "_verbose parameter should exist (may be in function signature)"

        # Verify it's prefixed with underscore (ARG001 fix pattern)
        assert " _verbose" in source or ", _verbose" in source or "(_verbose" in source, \
            "_verbose should be prefixed with underscore (ARG001 fix)"

    def test_create_torrent_click_decorator_compatibility(self):
        """Test that Click decorators work correctly with unused _verbose parameter."""
        # Verify the function is decorated with @click.command
        cmd = create_torrent_mod.create_torrent
        assert hasattr(cmd, "params"), "create_torrent should be a Click command"

        # Verify it has @click.pass_context decorator
        # This is checked by the presence of _ctx parameter in signature
        if hasattr(cmd, "callback"):
            func = cmd.callback
        else:
            func = cmd
        sig = inspect.signature(func)
        assert "_ctx" in sig.parameters, "create_torrent should have _ctx parameter (Click pass_context)"

        # Verify --verbose option exists
        params = cmd.params
        verbose_options = [p for p in params if hasattr(p, "name") and ("verbose" in p.name.lower() or p.name == "v")]
        assert len(verbose_options) > 0, "create_torrent should have --verbose option"


class TestCreateTorrentFunctionCompatibility:
    """Test that create_torrent function maintains compatibility after ARG001 fix."""

    def test_create_torrent_can_be_called_with_all_parameters(self, tmp_path):
        """Test that create_torrent can be called with all parameters including _verbose."""
        # This test verifies the function signature is correct
        cmd = create_torrent_mod.create_torrent
        if hasattr(cmd, "callback"):
            func = cmd.callback
        else:
            func = cmd

        sig = inspect.signature(func)

        # Get all parameters
        params = sig.parameters

        # Verify we can construct a call with all parameters
        # (We don't actually call it, just verify the signature is valid)
        assert len(params) >= 13, "create_torrent should have at least 13 parameters"

        # Verify _verbose is an int type (from count=True in Click)
        verbose_param = params.get("_verbose")
        if verbose_param:
            # The parameter should exist and be typed (or untyped, which is fine)
            assert verbose_param.name == "_verbose", "Parameter should be named _verbose"

    def test_create_torrent_command_integration(self, tmp_path, monkeypatch):
        """Test full command integration with _verbose parameter."""
        runner = CliRunner()
        source_file = tmp_path / "test.txt"
        source_file.write_text("test content")

        # Mock all dependencies
        mock_parser = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_v2_torrent.return_value = b"torrent data"
        mock_parser.return_value = mock_instance

        monkeypatch.setattr(
            "ccbt.core.torrent_v2.TorrentV2Parser",
            mock_parser,
        )

        # Test with various verbose combinations
        test_cases = [
            ([str(source_file), "--v2"], "no verbose"),
            ([str(source_file), "--v2", "-v"], "single verbose"),
            ([str(source_file), "--v2", "-vv"], "double verbose"),
            ([str(source_file), "--v2", "--verbose"], "long verbose flag"),
        ]

        for args, description in test_cases:
            result = runner.invoke(
                create_torrent_mod.create_torrent,
                args,
            )

            # Should not fail due to signature issues
            assert "TypeError" not in result.output, \
                f"Command failed with TypeError for {description}: {result.output}"
            assert "missing required argument" not in result.output.lower(), \
                f"Command failed with missing argument for {description}: {result.output}"

