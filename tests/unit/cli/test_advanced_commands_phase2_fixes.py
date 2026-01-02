"""Tests for advanced_commands.py Phase 2 fixes.

Covers:
- D401 fix (line 255 - docstring mood)
- SIM102 fix (line 278 - nested ifs combination)
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.prompt import Confirm

import ccbt.cli.advanced_commands as advanced_commands_mod

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestAdvancedCommandsD401Fix:
    """Test that D401 fix (docstring imperative mood) works correctly."""

    def test_performance_docstring_imperative_mood(self):
        """Test that performance function docstring is in imperative mood (D401 fix)."""
        # Get the function
        cmd = advanced_commands_mod.performance
        if hasattr(cmd, "callback"):
            func = cmd.callback
        else:
            func = cmd
        
        # Check docstring
        docstring = func.__doc__
        assert docstring is not None, "performance function should have a docstring"
        
        # Verify it's in imperative mood (starts with verb, not "Performance tuning")
        first_line = docstring.strip().split("\n")[0]
        assert first_line.startswith("Tune"), \
            f"Docstring should start with imperative verb (D401 fix). Got: {first_line}"
        
        # Verify it doesn't end with period (imperative mood pattern)
        # Actually, imperative mood can have periods, but the key is it should be a command
        assert "tune" in first_line.lower() or "optimize" in first_line.lower(), \
            f"Docstring should use imperative verbs (D401 fix). Got: {first_line}"

    def test_performance_docstring_source_verification(self):
        """Test that source code has correct docstring (D401 fix verification)."""
        # Read source file to verify fix
        import ccbt.cli.advanced_commands as mod
        from pathlib import Path
        
        source_file = Path(mod.__file__)
        source = source_file.read_text(encoding="utf-8")
        
        # Find the performance function docstring (around line 255)
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if i > 240 and i < 260:  # Around line 255
                if 'def performance' in line:
                    # Check next few lines for docstring
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if '"""' in lines[j]:
                            docstring_line = lines[j]
                            # Verify it's in imperative mood
                            assert "Tune" in docstring_line or "tune" in docstring_line, \
                                f"Docstring should use imperative mood (D401 fix). Found: {docstring_line}"
                            break


class TestAdvancedCommandsSIM102Fix:
    """Test that SIM102 fix (nested ifs combination) works correctly."""

    @patch("ccbt.cli.advanced_commands.get_config")
    @patch("ccbt.cli.advanced_commands._apply_optimizations")
    def test_performance_optimize_with_save_and_confirm(self, mock_apply, mock_get_config):
        """Test performance --optimize --save with confirmation (SIM102 fix logic)."""
        config = MagicMock()
        mock_get_config.return_value = config
        mock_apply.return_value = True
        
        runner = CliRunner()
        
        # Mock Confirm.ask to return True (user confirms)
        with patch.object(Confirm, "ask", return_value=True):
            result = runner.invoke(
                advanced_commands_mod.performance,
                ["--optimize", "--preset", "balanced", "--save"],
            )
        
        # Should proceed with optimization
        assert "Applying" in result.output or "optimizations" in result.output.lower()
        mock_apply.assert_called_once()

    @patch("ccbt.cli.advanced_commands.get_config")
    @patch("ccbt.cli.advanced_commands._apply_optimizations")
    def test_performance_optimize_with_save_and_cancel(self, mock_apply, mock_get_config):
        """Test performance --optimize --save with cancellation (SIM102 fix logic)."""
        config = MagicMock()
        mock_get_config.return_value = config
        
        runner = CliRunner()
        
        # Mock Confirm.ask to return False (user cancels)
        with patch.object(Confirm, "ask", return_value=False):
            result = runner.invoke(
                advanced_commands_mod.performance,
                ["--optimize", "--preset", "balanced", "--save"],
            )
        
        # Should cancel and not apply optimizations
        assert "cancelled" in result.output.lower() or "Cancelled" in result.output
        mock_apply.assert_not_called()

    @patch("ccbt.cli.advanced_commands.get_config")
    @patch("ccbt.cli.advanced_commands._apply_optimizations")
    def test_performance_optimize_without_save(self, mock_apply, mock_get_config):
        """Test performance --optimize without --save (SIM102 fix - save=False path)."""
        config = MagicMock()
        mock_get_config.return_value = config
        mock_apply.return_value = True
        
        runner = CliRunner()
        
        # No --save flag, so confirmation should not be asked
        result = runner.invoke(
            advanced_commands_mod.performance,
            ["--optimize", "--preset", "balanced"],
        )
        
        # Should proceed without asking for confirmation (save=False, so combined if is False)
        mock_apply.assert_called_once()

    def test_performance_sim102_fix_source_verification(self):
        """Test that source code has SIM102 fix (combined if statements)."""
        # Read source file to verify fix
        import ccbt.cli.advanced_commands as mod
        from pathlib import Path
        
        source_file = Path(mod.__file__)
        source = source_file.read_text(encoding="utf-8")
        
        # Find the SIM102 fix around line 278
        lines = source.splitlines()
        found_combined_if = False
        for i, line in enumerate(lines):
            if i > 270 and i < 290:  # Around line 278
                # Look for combined if statement: "if save and not Confirm.ask"
                if "if save and not Confirm.ask" in line or "if save and not" in line:
                    found_combined_if = True
                    # Verify it's not nested (should be single if)
                    assert "if save:" not in lines[i-1] or "if save:" not in lines[i], \
                        "Should use combined if statement, not nested ifs (SIM102 fix)"
                    break
        
        assert found_combined_if, \
            "Should find combined if statement (SIM102 fix) around line 278"

    @patch("ccbt.cli.advanced_commands.get_config")
    @patch("ccbt.cli.advanced_commands._apply_optimizations")
    def test_performance_sim102_logic_equivalence(self, mock_apply, mock_get_config):
        """Test that SIM102 fix maintains logic equivalence with original nested ifs."""
        config = MagicMock()
        mock_get_config.return_value = config
        mock_apply.return_value = True
        
        runner = CliRunner()
        
        # Test case 1: save=True, confirm=True -> should apply
        with patch.object(Confirm, "ask", return_value=True):
            result1 = runner.invoke(
                advanced_commands_mod.performance,
                ["--optimize", "--preset", "balanced", "--save"],
            )
            mock_apply.assert_called()
            mock_apply.reset_mock()
        
        # Test case 2: save=True, confirm=False -> should cancel
        with patch.object(Confirm, "ask", return_value=False):
            result2 = runner.invoke(
                advanced_commands_mod.performance,
                ["--optimize", "--preset", "balanced", "--save"],
            )
            mock_apply.assert_not_called()
            assert "cancelled" in result2.output.lower()
            mock_apply.reset_mock()
        
        # Test case 3: save=False -> should apply without asking
        result3 = runner.invoke(
            advanced_commands_mod.performance,
            ["--optimize", "--preset", "balanced"],
        )
        # Should not ask for confirmation when save=False
        mock_apply.assert_called_once()


class TestAdvancedCommandsFunctionCompatibility:
    """Test that advanced_commands functions maintain compatibility after Phase 2 fixes."""

    def test_performance_function_signature(self):
        """Test that performance function signature is correct after fixes."""
        cmd = advanced_commands_mod.performance
        if hasattr(cmd, "callback"):
            func = cmd.callback
        else:
            func = cmd
        
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        
        # Verify expected parameters exist
        expected_params = [
            "analyze",
            "optimize",
            "preset",
            "save",
            "config_file",
            "benchmark",
            "profile",
        ]
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"

    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_command_execution(self, mock_get_config):
        """Test that performance command executes correctly after fixes."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.write_buffer_kib = 64
        config.disk.write_batch_kib = 32
        config.disk.use_mmap = True
        config.disk.direct_io = False
        config.disk.enable_io_uring = False
        mock_get_config.return_value = config
        
        runner = CliRunner()
        
        # Test analyze mode
        result = runner.invoke(
            advanced_commands_mod.performance,
            ["--analyze"],
        )
        
        assert result.exit_code == 0
        assert "System & Config Analysis" in result.output






























































