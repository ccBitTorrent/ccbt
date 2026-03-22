"""Tests for fill_english helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ccbt.i18n.fill_english import fill_english
from ccbt.i18n.po_parse import po_msgid_msgstr as parse_po_msgid_msgstr


def test_fill_english_populates_missing_strings(tmp_path: Path) -> None:
    po_file = tmp_path / "ccbt.po"
    po_file.write_text(
        'msgid ""\n'
        'msgstr ""\n'
        '"Project-Id-Version: ccbt\\\\n"\n\n'
        'msgid "translated"\n'
        'msgstr "already translated"\n\n'
        'msgid "missing"\n'
        'msgstr ""\n',
        encoding="utf-8",
    )

    fill_english(po_file)

    mappings = parse_po_msgid_msgstr(po_file)
    assert mappings["translated"] == "already translated"
    assert mappings["missing"] == "missing"


def test_fill_english_handles_multiline_msgid_values(tmp_path: Path) -> None:
    po_file = tmp_path / "ccbt.po"
    po_file.write_text(
        'msgid ""\n'
        'msgstr ""\n'
        '""\n'
        '"Content-Type: text/plain; charset=UTF-8\\\\n"\n\n'
        'msgid ""\n'
        '"line one"\n'
        '"line two"\n'
        'msgstr ""\n\n'
        'msgid "other"\n'
        'msgstr "value"\n',
        encoding="utf-8",
    )

    fill_english(po_file)

    mappings = parse_po_msgid_msgstr(po_file)
    assert mappings["line oneline two"] == "line oneline two"


def test_fill_english_script_main_accepts_po_file_argument(tmp_path: Path) -> None:
    po_file = tmp_path / "ccbt.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n\n'
        'msgid "missing"\nmsgstr ""\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.fill_english",
            "--po-file",
            str(po_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[3]),
    )

    assert result.returncode == 0
    mappings = parse_po_msgid_msgstr(po_file)
    assert mappings["missing"] == "missing"
