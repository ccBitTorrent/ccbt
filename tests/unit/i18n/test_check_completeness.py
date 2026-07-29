"""Tests for check_completeness script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def create_locale_tree(tmp_path: Path) -> None:
    """Create a small locale tree with POT + two translated locales."""
    locales = tmp_path / "locales"
    pot_dir = locales / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr ""\n\n'
        'msgid "completed"\nmsgstr ""\n\n'
        'msgid "hello"\nmsgstr ""\n\n',
        encoding="utf-8",
    )

    es_dir = locales / "es" / "LC_MESSAGES"
    fr_dir = locales / "fr" / "LC_MESSAGES"
    es_dir.mkdir(parents=True)
    fr_dir.mkdir(parents=True)

    es_file = es_dir / "ccbt.po"
    es_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr "descargado"\n\n'
        'msgid "completed"\nmsgstr "completado"\n'
        # "hello" intentionally left untranslated
        ,
        encoding="utf-8",
    )
    fr_file = fr_dir / "ccbt.po"
    fr_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr "téléchargé"\n\n'
        'msgid "completed"\nmsgstr "terminé"\n'
        'msgid "hello"\nmsgstr "bonjour"\n',
        encoding="utf-8",
    )


def test_check_completeness_reports_untranslated_and_outputs_files(tmp_path: Path) -> None:
    create_locale_tree(tmp_path)
    output_path = tmp_path / "out" / "report.txt"
    out_dir = tmp_path / "out" / "untranslated"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.check_completeness",
            "--output",
            str(output_path),
            "--output-untranslated",
            str(out_dir),
        ],
        check=False, capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "ES:" in output_path.read_text(encoding="utf-8")
    assert "UNTRANSLATED" in out_dir.joinpath("untranslated_es.txt").read_text(
        encoding="utf-8"
    )
    assert "hello" in out_dir.joinpath("untranslated_es.txt").read_text(encoding="utf-8")
    assert out_dir.joinpath("msgids_canonical.txt").exists()


def test_check_completeness_lang_filter_only_outputs_target_locale(tmp_path: Path) -> None:
    create_locale_tree(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccbt.i18n.scripts.check_completeness",
            "--lang",
            "es",
        ],
        check=False, capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    output = result.stdout
    assert "ES:" in output
    assert "FR:" not in output
