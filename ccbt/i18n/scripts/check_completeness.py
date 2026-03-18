"""Check translation completeness of .po files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

# Max length for untranslated string samples (chars) to avoid huge lines
_SAMPLE_MAX_LEN = 60


def _safe_sample(msg: str) -> str:
    """Return a safe, truncated sample for display (ASCII or escaped)."""
    if len(msg) > _SAMPLE_MAX_LEN:
        msg = msg[:_SAMPLE_MAX_LEN] + "..."
    # On Windows, if stdout is not UTF-8, replace non-ASCII with escapes
    if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
        return "".join(
            c if ord(c) < 128 else f"\\u{ord(c):04x}"
            for c in msg
        )
    return msg


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
            sample = msgid[:50] + "..." if len(msgid) > 50 else msgid
            untranslated.append(sample)

    return total, translated, untranslated


def check_all(
    base_dir: Path,
    lang_filter: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> None:
    """Check completeness of .po files; optionally write report to file."""
    if not base_dir.exists():
        msg = f"Locales directory not found: {base_dir}"
        if output_path:
            output_path.write_text(msg + "\n", encoding="utf-8")
        else:
            print(msg)
        return

    lines: list[str] = []
    lines.append("Translation Completeness Check")
    lines.append("=" * 50)

    for lang_dir in sorted(base_dir.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        if lang_filter is not None and lang_dir.name != lang_filter:
            continue

        po_file = lang_dir / "LC_MESSAGES" / "ccbt.po"

        if not po_file.exists():
            continue

        total, translated, untranslated = check_po_completeness(po_file)
        percentage = (translated / total * 100) if total > 0 else 0

        lines.append(f"\n{lang_dir.name.upper()}:")
        lines.append(f"  Total strings: {total}")
        lines.append(f"  Translated: {translated} ({percentage:.1f}%)")
        lines.append(f"  Untranslated: {len(untranslated)}")

        if untranslated:
            lines.append("  First 10 untranslated strings:")
            for msg in untranslated[:10]:
                lines.append(f"    - {_safe_sample(msg)}")

    report = "\n".join(lines)
    if output_path is not None:
        output_path.write_text(report + "\n", encoding="utf-8")
        print(f"Report written to {output_path}")
        return

    # Safe stdout: try UTF-8 on Windows
    if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    print(report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check translation completeness of .po files."
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        metavar="CODE",
        help="Check only this locale (e.g. hi, es)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write full report to file (UTF-8)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent / "locales"
    check_all(base_dir, lang_filter=args.lang, output_path=args.output)


if __name__ == "__main__":
    main()
