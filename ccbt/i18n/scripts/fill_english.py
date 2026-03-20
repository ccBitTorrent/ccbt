"""Backward-compatible wrapper for the canonical fill_english script."""

from ccbt.i18n.fill_english import fill_english, PO_FILE


def main() -> None:
    """Fill English translations in the canonical PO file."""
    fill_english(PO_FILE)


if __name__ == "__main__":
    main()
