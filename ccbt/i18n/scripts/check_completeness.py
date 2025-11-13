"""Check translation completeness of .po files."""

from __future__ import annotations

import re
from pathlib import Path


def check_po_completeness(po_path: Path) -> tuple[int, int, list[str]]:
    """Check completeness of a .po file.

    Args:
        po_path: Path to .po file

    Returns:
        Tuple of (total, translated, untranslated_msgids)

    """
    with open(po_path, encoding="utf-8") as f:
        content = f.read()

    # Find all msgid/msgstr pairs
    pattern = r'msgid\s+"([^"]+)"\s+msgstr\s+"([^"]*)"'
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)

    total = 0
    translated = 0
    untranslated = []

    for msgid, msgstr in matches:
        # Skip empty msgid (header)
        if not msgid:
            continue

        total += 1

        # Check if translated (msgstr not empty and not equal to msgid)
        if msgstr and msgstr != msgid:
            translated += 1
        else:
            untranslated.append(msgid[:50] + "..." if len(msgid) > 50 else msgid)

    return total, translated, untranslated


def check_all() -> None:
    """Check completeness of all .po files."""
    base_dir = Path(__file__).parent.parent / "locales"

    if not base_dir.exists():
        print(f"Locales directory not found: {base_dir}")
        return

    print("Translation Completeness Check\n" + "=" * 50)

    for lang_dir in sorted(base_dir.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue

        po_file = lang_dir / "LC_MESSAGES" / "ccbt.po"

        if not po_file.exists():
            continue

        total, translated, untranslated = check_po_completeness(po_file)
        percentage = (translated / total * 100) if total > 0 else 0

        print(f"\n{lang_dir.name.upper()}:")
        print(f"  Total strings: {total}")
        print(f"  Translated: {translated} ({percentage:.1f}%)")
        print(f"  Untranslated: {len(untranslated)}")

        if untranslated and len(untranslated) <= 10:
            print("  Untranslated strings:")
            for msg in untranslated[:10]:
                print(f"    - {msg}")
        elif untranslated:
            print("  First 10 untranslated strings:")
            for msg in untranslated[:10]:
                print(f"    - {msg}")


if __name__ == "__main__":
    check_all()
