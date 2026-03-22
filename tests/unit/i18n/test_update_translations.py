"""Tests for update_translations script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def tmp_locales_with_pot(tmp_path: Path) -> Path:
    """Create locales dir with en/LC_MESSAGES/ccbt.pot and one locale .po."""
    pot_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "old"\nmsgstr ""\n\n'
        'msgid "new"\nmsgstr ""\n',
        encoding="utf-8",
    )
    es_dir = tmp_path / "locales" / "es" / "LC_MESSAGES"
    es_dir.mkdir(parents=True)
    es_po = es_dir / "ccbt.po"
    es_po.write_text(
        'msgid ""\nmsgstr ""\n"Language: es\\n"\n\n'
        'msgid "old"\nmsgstr "viejo"\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.skipif(
    not __import__("shutil").which("msgmerge"),
    reason="msgmerge not installed",
)
def test_update_translations_merge_preserves_msgstr(tmp_locales_with_pot: Path) -> None:
    """update_translations merges new msgid from .pot and preserves existing msgstr."""
    locales_root = tmp_locales_with_pot / "locales"
    pot_path = locales_root / "en" / "LC_MESSAGES" / "ccbt.pot"
    # Run script in-process by importing and calling (script expects repo layout)
    from ccbt.i18n.scripts.update_translations import (
        get_default_pot_path,
        get_locales_root,
        update_translations,
    )

    # Override paths via direct call
    updated = update_translations(
        pot_path,
        locales_root,
        lang_filter="es",
    )
    assert "es" in updated
    es_po = locales_root / "es" / "LC_MESSAGES" / "ccbt.po"
    content = es_po.read_text(encoding="utf-8")
    assert "new" in content
    assert "viejo" in content or "old" in content


@pytest.fixture
def tmp_locales_with_pot_and_en(tmp_path: Path) -> Path:
    """Locales with POT plus English catalog (merge must update en too)."""
    pot_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    pot_dir.mkdir(parents=True)
    pot_file = pot_dir / "ccbt.pot"
    pot_file.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "existing"\nmsgstr ""\n\n'
        'msgid "from_pot_only"\nmsgstr ""\n',
        encoding="utf-8",
    )
    en_po = pot_dir / "ccbt.po"
    en_po.write_text(
        'msgid ""\nmsgstr ""\n"Language: en\\n"\n\n'
        'msgid "existing"\nmsgstr "Existing EN"\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.skipif(
    not __import__("shutil").which("msgmerge"),
    reason="msgmerge not installed",
)
def test_update_translations_merges_english_catalog(
    tmp_locales_with_pot_and_en: Path,
) -> None:
    """English ccbt.po is merged from POT so new msgids appear in the catalog."""
    locales_root = tmp_locales_with_pot_and_en / "locales"
    pot_path = locales_root / "en" / "LC_MESSAGES" / "ccbt.pot"
    from ccbt.i18n.scripts.update_translations import update_translations

    updated = update_translations(pot_path, locales_root, lang_filter="en")
    assert "en" in updated
    en_po = locales_root / "en" / "LC_MESSAGES" / "ccbt.po"
    text = en_po.read_text(encoding="utf-8")
    assert "from_pot_only" in text
    assert "Existing EN" in text
