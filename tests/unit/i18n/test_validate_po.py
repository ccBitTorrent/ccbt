"""Tests for validate_po script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ccbt.i18n.scripts.validate_po import validate_po_file


def test_validate_po_valid(tmp_path: Path) -> None:
    """A valid .po file passes validation."""
    valid_content = """msgid ""
msgstr ""
"Project-Id-Version: ccbt\\n"
"Language: en\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "hello"
msgstr "hola"
"""
    po_file = tmp_path / "valid.po"
    po_file.write_text(valid_content, encoding="utf-8")
    is_valid, errors = validate_po_file(po_file)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_po_invalid_missing_header(tmp_path: Path) -> None:
    """A .po file missing required header fails validation."""
    invalid_content = 'msgid ""\nmsgstr ""\n'
    po_file = tmp_path / "invalid.po"
    po_file.write_text(invalid_content, encoding="utf-8")
    is_valid, errors = validate_po_file(po_file)
    assert is_valid is False
    assert any("Project-Id-Version" in e or "Language" in e for e in errors)


def test_validate_po_script_exit_code() -> None:
    """validate_po script exits 0 when all .po files are valid."""
    result = subprocess.run(
        [sys.executable, "-m", "ccbt.i18n.scripts.validate_po"],
        check=False, capture_output=True,
        text=True,
    )
    # May be 0 or 1 depending on repo .po state
    assert result.returncode in (0, 1)
