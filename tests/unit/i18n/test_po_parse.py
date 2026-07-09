"""Tests for shared PO/POT parser helpers."""

from __future__ import annotations

from pathlib import Path

from ccbt.i18n.po_parse import (
    iter_po_entries,
    parse_pot_msgids,
    po_msgid_msgstr,
    pot_msgids,
    quote_po_lines,
    render_po_entry,
)


def test_iter_po_entries_with_multiline_and_escaped_values(tmp_path: Path) -> None:
    po_file = tmp_path / "messages.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n"Project-Id-Version: ccbt\\n"\n\n'
        'msgid "single line"\nmsgstr "translated"\n\n'
        'msgid ""\n"multi"\n"line"\nmsgstr ""\n"multi"\n"line"\n\n'
        '#, fuzzy\n'
        'msgid "fuzzy entry"\nmsgstr "placeholder"\n',
        encoding="utf-8",
    )

    entries = iter_po_entries(po_file)
    assert len(entries) == 4
    assert entries[1].msgid == "single line"
    assert entries[1].msgstr == "translated"
    assert entries[2].msgid == "multiline"
    assert entries[2].msgstr == "multiline"
    assert entries[3].fuzzy is True


def test_pot_msgids_and_po_msgid_msgstr(tmp_path: Path) -> None:
    po_file = tmp_path / "messages.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n\n'
        'msgid "greeting"\nmsgstr "hola"\n\n'
        'msgid "empty"\nmsgstr ""\n\n'
        'msgid "unused"\nmsgstr "unused"\n',
        encoding="utf-8",
    )

    assert pot_msgids(po_file) == {"greeting", "empty", "unused"}
    assert po_msgid_msgstr(po_file)["greeting"] == "hola"
    assert po_msgid_msgstr(po_file)["empty"] == ""
    assert po_msgid_msgstr(po_file)["unused"] == "unused"


def test_parse_pot_msgids_ignores_empty_messages(tmp_path: Path) -> None:
    po_file = tmp_path / "messages.po"
    po_file.write_text(
        'msgid ""\nmsgstr ""\n\n'
        'msgid "title"\nmsgstr "Titel"\n\n'
        'msgid "line\\nbreak"\nmsgstr ""\n\n'
        'msgid ""\n"continuation"\nmsgstr ""\n\n',
        encoding="utf-8",
    )

    assert pot_msgids(po_file) == {"title", "line\nbreak", "continuation"}
    assert parse_pot_msgids(po_file) == {"title", "line\nbreak", "continuation"}


def test_quote_po_lines() -> None:
    assert quote_po_lines("single") == ['"single"']
    assert quote_po_lines("a\nb") == ['""', '"a\\n"', '"b"']
    assert quote_po_lines("a\n") == ['""', '"a\\n"', '""']


def test_render_po_entry_uses_continuation_lines_without_repeating_prefixes() -> None:
    assert render_po_entry("line\nvalue", "line\nvalue") == [
        'msgid ""',
        '"line\\n"',
        '"value"',
        'msgstr ""',
        '"line\\n"',
        '"value"',
    ]
