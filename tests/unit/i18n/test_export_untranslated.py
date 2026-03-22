"""Tests for export_untranslated script."""

from __future__ import annotations

from pathlib import Path

from ccbt.i18n.scripts.export_untranslated import export_untranslated


def test_export_untranslated_writes_expected_files(tmp_path: Path) -> None:
    """Canonical and per-locale files include untranslated entries only."""
    locales_root = tmp_path / "locales"
    en_dir = locales_root / "en" / "LC_MESSAGES"
    es_dir = locales_root / "es" / "LC_MESSAGES"
    fr_dir = locales_root / "fr" / "LC_MESSAGES"
    en_dir.mkdir(parents=True)
    es_dir.mkdir(parents=True)
    fr_dir.mkdir(parents=True)

    pot_file = en_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr ""\n\n'
        'msgid "completed"\nmsgstr ""\n',
        encoding="utf-8",
    )

    es_file = es_dir / "ccbt.po"
    es_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr "descargado"\n',
        encoding="utf-8",
    )
    fr_file = fr_dir / "ccbt.po"
    fr_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "downloaded"\nmsgstr "téléchargé"\n\n'
        'msgid "completed"\nmsgstr ""\n',
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    export_untranslated(
        pot_path=pot_file,
        locales_root=locales_root,
        out_dir=out_dir,
        lang_filter=None,
    )

    canonical = out_dir / "msgids_canonical.txt"
    untranslated_es = out_dir / "untranslated_es.txt"
    untranslated_fr = out_dir / "untranslated_fr.txt"

    assert canonical.exists()
    assert "downloaded" in canonical.read_text(encoding="utf-8")
    assert "completed" in canonical.read_text(encoding="utf-8")

    es_lines = untranslated_es.read_text(encoding="utf-8").splitlines()
    fr_lines = untranslated_fr.read_text(encoding="utf-8").splitlines()

    assert "LANGUAGE: es" in es_lines
    assert "UNTRANSLATED: 1" in es_lines
    assert "completed" in es_lines
    assert "downloaded" not in es_lines

    assert "LANGUAGE: fr" in fr_lines
    assert "UNTRANSLATED: 1" in fr_lines
    assert "completed" in fr_lines
    assert "downloaded" not in fr_lines
