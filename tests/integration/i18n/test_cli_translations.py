"""Integration tests for CLI language/locale commands."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.integration
def test_cli_language_list() -> None:
    """Run btbt language --list; assert no crash and output contains locale info."""
    result = subprocess.run(
        [sys.executable, "-m", "ccbt.cli.main", "language", "--list"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "locale" in out.lower() or "en" in out or "Current" in out or "Available" in out


@pytest.mark.integration
def test_cli_language_set_then_list() -> None:
    """Run btbt language --set en then --list; assert no crash."""
    subprocess.run(
        [sys.executable, "-m", "ccbt.cli.main", "language", "--set", "en"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    result = subprocess.run(
        [sys.executable, "-m", "ccbt.cli.main", "language", "--list"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
