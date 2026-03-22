"""Tests for check_string_coverage script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def tmp_source_with_strings(tmp_path: Path) -> Path:
    """Create a minimal source tree with one _() string."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "foo.py").write_text(
        'from ccbt.i18n import _\n\nx = _("hello world")\n',
        encoding="utf-8",
    )
    return src


@pytest.fixture
def tmp_pot_covered(tmp_path: Path, tmp_source_with_strings: Path) -> Path:
    """Create a .pot that contains the string from tmp_source_with_strings."""
    pot_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "hello world"\nmsgstr ""\n',
        encoding="utf-8",
    )
    return pot_file


def test_check_string_coverage_covered(
    tmp_source_with_strings: Path, tmp_pot_covered: Path
) -> None:
    """When all strings in source are in .pot, exit 0 even with --fail-on-gap."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.check_string_coverage",
            "--source-dir",
            str(tmp_source_with_strings),
            "--pot",
            str(tmp_pot_covered),
            "--fail-on-gap",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_source_with_strings.parent,
    )
    assert result.returncode == 0
    assert "Uncovered" in result.stdout or "Covered" in result.stdout


def test_check_string_coverage_uncovered_fail_on_gap(
    tmp_path: Path, tmp_source_with_strings: Path
) -> None:
    """When a string is in source but not in .pot, --fail-on-gap exits 1."""
    # .pot without "hello world"
    pot_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.check_string_coverage",
            "--source-dir",
            str(tmp_source_with_strings),
            "--pot",
            str(pot_file),
            "--fail-on-gap",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_source_with_strings.parent,
    )
    assert result.returncode == 1
    assert "hello world" in result.stdout or "Uncovered" in result.stdout


def test_check_string_coverage_collects_n_and_context_strings(
    tmp_path: Path,
) -> None:
    """_n() and _p() calls should be interpreted as covered user strings."""
    src = tmp_path / "src"
    src.mkdir()
    src_file = src / "gettext_calls.py"
    src_file.write_text(
        "from ccbt.i18n import _n, _p\n"
        'singular = _n("file", "files", 2)\n'
        '_p("ui_status", "Download complete")\n',
        encoding="utf-8",
    )

    pot_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "file"\nmsgstr ""\n\n'
        'msgid "Download complete"\nmsgstr ""\n\n'
        'msgid "files"\nmsgstr ""\n\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.check_string_coverage",
            "--source-dir",
            str(src),
            "--pot",
            str(pot_file),
            "--fail-on-gap",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "Uncovered" in result.stdout
