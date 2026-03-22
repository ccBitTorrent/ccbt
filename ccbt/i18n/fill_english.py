"""Fill English translations (msgstr = msgid)."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

from ccbt.i18n.po_parse import iter_po_entries, render_po_entry

PO_FILE: Final[Path] = (
    Path(__file__).parent / "locales" / "en" / "LC_MESSAGES" / "ccbt.po"
)


def _fill_english(po_file: Path) -> list[str]:
    """Return updated PO file lines where empty English msgstrs are populated."""
    lines: list[str] = []
    for entry in iter_po_entries(po_file):
        entry_msgstr = entry.msgid if entry.msgid and not entry.msgstr else entry.msgstr
        lines.extend(render_po_entry(entry.msgid, entry_msgstr))
        lines.append("")
    return lines


def fill_english(po_file: Optional[Path]= None) -> None:
    """Fill empty English msgstr fields from msgid."""
    target = po_file or PO_FILE
    lines = _fill_english(target)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Run PO English fallback completion against the default locale file."""
    fill_english()


if __name__ == "__main__":
    main()