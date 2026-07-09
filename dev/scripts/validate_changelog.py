#!/usr/bin/env python3
"""Validate changelog structure for release hygiene."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def validate_changelog() -> list[str]:
    """Return validation errors for the project changelog."""
    repo_root = Path(__file__).resolve().parents[2]
    changelog = repo_root / "dev" / "CHANGELOG.md"
    errors: list[str] = []

    if not changelog.is_file():
        return [f"Missing changelog: {changelog}"]

    text = changelog.read_text(encoding="utf-8")
    if not text.strip():
        return [f"Changelog is empty: {changelog}"]

    if "## [Unreleased]" not in text and not re.search(r"^## \[\d+\.\d+\.\d+\]", text, re.MULTILINE):
        errors.append(
            f"Changelog must contain an [Unreleased] section or a version heading: {changelog}"
        )

    return errors


def main() -> int:
    errors = validate_changelog()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
