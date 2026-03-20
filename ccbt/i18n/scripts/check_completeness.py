"""Check translation completeness of .po files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from ccbt.i18n.po_parse import PoEntry, po_entries_by_msgid, pot_msgids


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


def _is_translated(*, msgid: str, msgstr: str, locale: str, is_fuzzy: bool) -> bool:
    if is_fuzzy:
        return False
    if locale == "en":
        return bool(msgstr)
    return bool(msgstr) and msgstr != msgid


def check_po_completeness(
    po_path: Path,
    *,
    pot_msgid_set: set[str],
    locale: str,
) -> tuple[int, int, list[str]]:
    """Check completeness of a .po file using POT msgids."""
    entries: dict[str, PoEntry] = po_entries_by_msgid(po_path)
    untranslated: list[str] = []

    for msgid in pot_msgid_set:
        entry = entries.get(msgid)
        if entry is None or not _is_translated(
            msgid=msgid, msgstr=entry.msgstr, locale=locale, is_fuzzy=entry.fuzzy
        ):
            untranslated.append(msgid)

    total = len(pot_msgid_set)
    translated = total - len(untranslated)
    return total, translated, untranslated


def check_all(
    base_dir: Path,
    lang_filter: Optional[str] = None,
    output_path: Optional[Path] = None,
    output_untranslated: Optional[Path] = None,
    pot_path: Optional[Path] = None,
) -> None:
    """Check completeness of .po files; optionally write report to file."""
    if not base_dir.exists():
        msg = f"Locales directory not found: {base_dir}"
        if output_path:
            output_path.write_text(msg + "\n", encoding="utf-8")
        else:
            print(msg)
        return

    pot_file = (
        pot_path
        if pot_path is not None
        else (base_dir / "en" / "LC_MESSAGES" / "ccbt.pot")
    )
    if not pot_file.exists():
        msg = f"POT file not found: {pot_file}"
        if output_path:
            output_path.write_text(msg + "\n", encoding="utf-8")
        else:
            print(msg)
        return

    pot_msgid_set = pot_msgids(pot_file)

    if output_untranslated is not None:
        output_untranslated.mkdir(parents=True, exist_ok=True)
        canonical_file = output_untranslated / "msgids_canonical.txt"
        canonical_file.write_text("\n".join(sorted(pot_msgid_set)) + "\n", encoding="utf-8")

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

        total, translated, untranslated = check_po_completeness(
            po_file,
            pot_msgid_set=pot_msgid_set,
            locale=lang_dir.name,
        )
        percentage = (translated / total * 100) if total > 0 else 0

        lines.append(f"\n{lang_dir.name.upper()}:")
        lines.append(f"  Total strings: {total}")
        lines.append(f"  Translated: {translated} ({percentage:.1f}%)")
        lines.append(f"  Untranslated: {len(untranslated)}")

        if untranslated:
            lines.append("  First 10 untranslated strings:")
            for msg in untranslated[:10]:
                lines.append(f"    - {_safe_sample(msg)}")

            if output_untranslated is not None:
                untranslated_file = output_untranslated / f"untranslated_{lang_dir.name}.txt"
                untranslated_file.write_text(
                    "\n".join(
                        [
                            f"LANGUAGE: {lang_dir.name}",
                            f"TOTAL: {total}",
                            f"TRANSLATED: {translated}",
                            f"UNTRANSLATED: {len(untranslated)}",
                            "",
                            *sorted(untranslated),
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

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
    parser.add_argument(
        "--output-untranslated",
        type=Path,
        default=None,
        metavar="DIR",
        help="Write untranslated list per locale to directory",
    )
    parser.add_argument(
        "--pot",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to canonical POT file",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent / "locales"
    check_all(
        base_dir,
        lang_filter=args.lang,
        output_path=args.output,
        output_untranslated=args.output_untranslated,
        pot_path=args.pot,
    )


if __name__ == "__main__":
    main()
