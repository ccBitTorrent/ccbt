#!/usr/bin/env python3
"""Validate project version consistency across packaging metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _read_pyproject_version(repo_root: Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        msg = f"Could not find version in {pyproject}"
        raise ValueError(msg)
    return match.group(1)


def _read_package_version(repo_root: Path) -> str:
    init_path = repo_root / "ccbt" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        msg = f"Could not find __version__ in {init_path}"
        raise ValueError(msg)
    return match.group(1)


def validate_version() -> list[str]:
    """Return validation errors for version metadata."""
    repo_root = Path(__file__).resolve().parents[2]
    errors: list[str] = []
    try:
        pyproject_version = _read_pyproject_version(repo_root)
        package_version = _read_package_version(repo_root)
    except ValueError as exc:
        return [str(exc)]

    if pyproject_version != package_version:
        errors.append(
            "Version mismatch: "
            f"pyproject.toml has {pyproject_version!r}, "
            f"ccbt/__init__.py has {package_version!r}"
        )

    if not re.fullmatch(r"\d+\.\d+\.\d+", pyproject_version):
        errors.append(f"Invalid semver in pyproject.toml: {pyproject_version!r}")

    return errors


def main() -> int:
    errors = validate_version()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
