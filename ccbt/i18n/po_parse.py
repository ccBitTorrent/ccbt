"""Shared gettext PO/POT parsing helpers.

This module centralizes robust `.po` parsing for completion checks,
translation export tooling, and source file updates.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Optional

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class PoEntry:
    """Represents one PO entry with the canonical `msgid` and `msgstr`."""

    msgid: str
    msgstr: str
    fuzzy: bool = False


_PREFIX_MSGID = "msgid "
_PREFIX_MSGID_PLURAL = "msgid_plural "
_PREFIX_MSGSTR = "msgstr "
_PREFIX_MSGCTXT = "msgctxt "
_PREFIX_MSGSTR_INDEX = "msgstr["


def _decode_po_literal(raw: str) -> str:
    """Decode a quoted gettext string literal.

    Args:
        raw: Raw quoted string from a PO file.

    Returns:
        Decoded text value.
    """
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return ""


def _parse_msgstr_index(line: str) -> Optional[int]:
    """Parse the index from `msgstr[<index>]`."""
    if not line.startswith(_PREFIX_MSGSTR_INDEX):
        return None
    end = line.find("]")
    if end <= len(_PREFIX_MSGSTR_INDEX):
        return None
    raw_index = line[len(_PREFIX_MSGSTR_INDEX) : end]
    try:
        return int(raw_index)
    except ValueError:
        return None


def _escape_po_value(value: str) -> str:
    """Escape a value so it can be written as a PO quoted string."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def quote_po_lines(value: str) -> list[str]:
    """Render a gettext string value into PO-style quoted lines."""
    if "\n" not in value:
        return [f'"{_escape_po_value(value)}"']

    lines = value.split("\n")
    quoted: list[str] = ['""']
    for idx, part in enumerate(lines):
        chunk = part
        if idx < len(lines) - 1:
            chunk += "\n"
        quoted.append(f'"{_escape_po_value(chunk)}"')
    return quoted


def render_po_entry(msgid: str, msgstr: str) -> list[str]:
    """Render one entry as `.po` text lines."""
    msgid_lines = quote_po_lines(msgid)
    msgstr_lines = quote_po_lines(msgstr)
    if not msgid_lines:
        msgid_lines = ['""']
    if not msgstr_lines:
        msgstr_lines = ['""']

    lines: list[str] = []
    if msgid_lines:
        lines.append(f"msgid {msgid_lines[0]}")
        lines.extend(msgid_lines[1:])
    else:
        lines.append('msgid ""')

    if msgstr_lines:
        lines.append(f"msgstr {msgstr_lines[0]}")
        lines.extend(msgstr_lines[1:])
    else:
        lines.append('msgstr ""')
    return lines


def iter_po_entries(path: Path) -> list[PoEntry]:
    """Parse all entries from a `.po`/`.pot` file."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    entries: list[PoEntry] = []

    current_msgid: list[str] = []
    current_msgstr: dict[int, list[str]] = {}
    current_msgstr_index: Optional[int] = None
    active = ""
    has_msgid = False
    is_fuzzy = False

    def _finalize_current() -> None:
        nonlocal \
            current_msgid, \
            current_msgstr, \
            current_msgstr_index, \
            active, \
            is_fuzzy, \
            has_msgid
        if not has_msgid:
            return

        msgid_value = "".join(current_msgid)
        msgstr_value = "".join(current_msgstr.get(0, []))
        entries.append(PoEntry(msgid=msgid_value, msgstr=msgstr_value, fuzzy=is_fuzzy))

        current_msgid = []
        current_msgstr = {}
        current_msgstr_index = None
        active = ""
        has_msgid = False
        is_fuzzy = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            _finalize_current()
            continue

        if line.startswith("#,"):
            if "fuzzy" in line:
                is_fuzzy = True
            continue

        if line.startswith("#"):
            continue

        if line.startswith(_PREFIX_MSGID):
            _finalize_current()
            has_msgid = True
            active = "msgid"
            current_msgid.append(_decode_po_literal(line[len(_PREFIX_MSGID) :].strip()))
            continue

        if line.startswith(_PREFIX_MSGID_PLURAL):
            active = "msgid_plural"
            continue

        if line.startswith(_PREFIX_MSGCTXT):
            active = "msgctxt"
            continue

        if line.startswith(_PREFIX_MSGSTR_INDEX):
            index = _parse_msgstr_index(line)
            if index is None:
                active = ""
                continue
            current_msgstr_index = index
            active = f"msgstr_index:{index}"
            remainder = line[line.find("]") + 1 :].strip()
            if remainder.startswith('"'):
                current_msgstr.setdefault(index, [])
                current_msgstr[index].append(_decode_po_literal(remainder))
            continue

        if line.startswith(_PREFIX_MSGSTR):
            active = "msgstr"
            remainder = line[len(_PREFIX_MSGSTR) :].strip()
            current_msgstr_index = 0
            current_msgstr.setdefault(0, [])
            if remainder.startswith('"'):
                current_msgstr[0].append(_decode_po_literal(remainder))
            continue

        if line.startswith('"') and active:
            value = _decode_po_literal(line)
            if active == "msgid":
                current_msgid.append(value)
            elif active in {"msgid_plural", "msgctxt"}:
                # msgid_plural and msgctxt are intentionally ignored for string-level completeness.
                continue
            elif current_msgstr_index is not None:
                current_msgstr.setdefault(current_msgstr_index, [])
                current_msgstr[current_msgstr_index].append(value)

    # finalize trailing entry
    _finalize_current()
    return entries


def pot_msgids(path: Path) -> set[str]:
    """Return non-empty canonical msgids from a POT template."""
    return {entry.msgid for entry in iter_po_entries(path) if entry.msgid}


def parse_pot_msgids(path: Path) -> set[str]:
    """Backward-compatible API-compatible alias for parsing POT msgids."""
    return pot_msgids(path)


def po_msgid_msgstr(path: Path) -> dict[str, str]:
    """Return `msgid -> msgstr` for non-empty msgids."""
    msgid_msgstr: dict[str, str] = {}
    for entry in iter_po_entries(path):
        if not entry.msgid:
            continue
        if entry.msgid not in msgid_msgstr or (
            not msgid_msgstr[entry.msgid] and entry.msgstr
        ):
            msgid_msgstr[entry.msgid] = entry.msgstr
    return msgid_msgstr


def po_entries_by_msgid(path: Path) -> dict[str, PoEntry]:
    """Return a canonical mapping of `msgid -> PoEntry`."""
    entries: dict[str, PoEntry] = {}
    for entry in iter_po_entries(path):
        if not entry.msgid:
            continue
        if entry.msgid not in entries or (
            not entries[entry.msgid].msgstr and entry.msgstr
        ):
            entries[entry.msgid] = entry
    return entries


SUPPORTED_LOCALES: Final[tuple[str, ...]] = (
    "en",
    "es",
    "eu",
    "fr",
    "ja",
    "ko",
    "hi",
    "ur",
    "fa",
    "th",
    "zh",
    "arc",
    "sw",
    "ha",
    "yo",
)
