#!/usr/bin/env python3
"""Find Click options/commands that use static ``help="..."`` (not ``lambda: _("...")``).

Run from repo root::

    uv run python dev/audit_click_help.py

Exit 0 always; prints paths and counts for i18n follow-up (P0 CLI/TUI audits).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _is_static_help_keyword(kw: ast.keyword) -> bool:
    if kw.arg != "help":
        return False
    if isinstance(kw.value, ast.Lambda):
        return False
    if isinstance(kw.value, ast.Call):
        # help=_("...") or similar — translatable at import time if _ is defined
        return False
    return isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, snippet) for each static help= string."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if not _is_static_help_keyword(kw):
                continue
            val = kw.value
            assert isinstance(val, ast.Constant) and isinstance(val.value, str)
            snippet = val.value.replace("\n", " ")[:72]
            hits.append((kw.lineno, snippet))
    return hits


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    targets = [root / "ccbt" / "cli", root / "ccbt" / "interface"]
    total = 0
    for base in targets:
        if not base.is_dir():
            print(f"Skip missing: {base}", file=sys.stderr)
            continue
        label = base.relative_to(root)
        print(f"## {label}")
        for py in sorted(base.rglob("*.py")):
            hits = _scan_file(py)
            if not hits:
                continue
            rel = py.relative_to(root)
            for line_no, snippet in hits:
                print(f"  {rel}:{line_no}  help={snippet!r}")
                total += 1
        print()
    print(f"Total static Click help= strings: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
