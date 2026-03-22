"""Backward-compatible wrapper for the canonical fill_english script."""

import argparse
from pathlib import Path

from ccbt.i18n.fill_english import fill_english, PO_FILE


def main() -> None:
    """Fill English translations in the canonical PO file."""
    parser = argparse.ArgumentParser(
        description="Fill empty English msgstr values with msgid."
    )
    parser.add_argument(
        "--po-file",
        type=Path,
        default=PO_FILE,
        help="Path to a .po file (defaults to canonical ccbt.po).",
    )
    args = parser.parse_args()
    fill_english(args.po_file)


if __name__ == "__main__":
    main()
