#!/usr/bin/env python3
"""Regenerate terminal-output inventory appendix and per-file detailed report.

Run from repo root:
  uv run python dev/scripts/generate_terminal_output_inventory.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CCBT = ROOT / "ccbt"
APPENDIX = ROOT / "docs" / "en" / "reports" / "terminal-output-inventory-appendix.txt"
DETAILED = ROOT / "docs" / "en" / "reports" / "terminal-output-inventory-by-file.md"

MAX_OPENER_LINE_LEN = 60
SNIPPET_COL_MAX = 100

PATTERNS: list[tuple[str, str]] = [
    (r"console\.print\s*\(", "console.print"),
    (r"^\s*print\s*\(", "print"),
    (r"click\.echo\s*\(", "click.echo"),
    (r"sys\.stderr\.write\s*\(", "sys.stderr.write"),
    (r"sys\.stdout\.write\s*\(", "sys.stdout.write"),
]


def scan_sources() -> list[tuple[str, int, str, str]]:
    """Walk ``ccbt/**/*.py`` and collect terminal-output lines."""
    rows: list[tuple[str, int, str, str]] = []
    for path in sorted(CCBT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if "__pycache__" in rel:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for pat, kind in PATTERNS:
                if re.search(pat, line):
                    rows.append((rel, i, kind, line.strip()[:240]))
                    break
    return rows


def classify(path: str, kind: str, snippet: str) -> tuple[str, str]:  # noqa: PLR0911, PLR0912
    """Return (proposed_level, resolution_note)."""
    low = snippet.lower()
    s = snippet
    st = s.strip()

    if "rich_logging.py" in path and "stderr" in kind:
        return ("—", "Circular-log guard; keep stderr; do not log.")

    if "/i18n/scripts/" in path or path.endswith("i18n/extract.py"):
        return (
            "— (maintainer)",
            "Dev script; use print or optional DEBUG if integrated.",
        )

    if "interface/splash/" in path and "demo" in path:
        return ("— (demo)", "Interactive demo UX only.")

    if kind == "sys.stderr.write":
        return ("ERROR (optional)", "After logging is up, mirror once to logger.error.")

    if kind == "click.echo":
        if ", err=true)" in low or " err=true)" in low:
            return ("ERROR", "Dual: logger.error + click.echo for TTY.")
        if "json.dumps" in s or "yaml." in s or "toml.dumps" in s or "safe_dump" in s:
            return ("— (stdout)", "Machine-readable; do not spam log files.")
        if "✓" in s and "warning" in low and "no " in low:
            return ("INFO", "Positive check (no warnings); logger.info if auditing.")
        if "valid" in low and ("ok" in low or "✓" in s):
            return ("INFO", "Dual emit logger.info if operators need audit trail.")
        if "failed" in low or "error" in low or "✗" in s:
            return ("ERROR", "Dual emit logger.error.")
        if "warning" in low or "⚠" in s:
            return ("WARNING", "Dual emit logger.warning.")
        return ("INFO", "Default user message; dual INFO if log capture needed.")

    if kind == "print":
        if re.match(r'^\s*print\s*\(\s*["\']\\n', s) or re.match(
            r"^\s*print\s*\(\s*['\"]\\n['\"]\s*\)", s
        ):
            return ("—", "Whitespace only; skip logging.")
        if "error" in low or "failed" in low:
            return ("ERROR", "Prefer logger.error in runtime code.")
        return ("INFO", "Script progress; map to INFO if moved to logger.")

    # console.print — multiline opening (no args on same line)
    if kind == "console.print":
        if (
            st.rstrip().endswith("(")
            and "console.print(" in st
            and len(st) < MAX_OPENER_LINE_LEN
        ):
            return (
                "INFO",
                "Multiline console.print opener; same block as following lines; "
                "use INFO for tables/sections unless inner markup says otherwise.",
            )
        if re.match(r"^console\.print\s*\(\s*\w+\s*\)\s*$", st) and "table" in low:
            return (
                "INFO",
                "Variable table render; terminal-primary; "
                "one-line logger.info summary optional.",
            )
        if re.match(r"^console\.print\s*\(\s*\w+\s*\)\s*$", st):
            return (
                "INFO",
                "Variable render (Panel/Table/str); terminal-primary; "
                "optional logger.info.",
            )

    # console.print — styled / content
    if "[yellow]" in s and "✗" in s:
        return ("ERROR", "Failure styled yellow; prefer logger.error.")

    if "[red]" in s or "error:" in low:
        return ("ERROR", "logger.error + optional console.print.")

    if "failed" in low and "[green]" not in s and "console.print" in low:
        return ("ERROR", "logger.error + optional console.print.")

    if "[yellow]" in s or "⚠" in s:
        return ("WARNING", "logger.warning + optional console.")

    if "warning" in low and "[yellow]" not in s and "⚠" not in s:
        return (
            "INFO",
            "Mentions 'warning' in copy; default INFO unless alerting user.",
        )

    if "[green]" in s or "✓" in s:
        if "complete" in low or "success" in low:
            return ("INFO", "logger.info for milestones.")
        return ("INFO", "logger.info for success copy.")

    if "[cyan]" in s or "[blue]" in s or "[bold cyan]" in low:
        return ("INFO", "Progress/header; logger.info at DEBUG duplication optional.")

    if "[bold]" in s and "[/bold]" in s and "[red]" not in s:
        return ("INFO", "Section heading; logger.info if duplicating narrative to log.")

    if "[dim]" in s:
        return ("DEBUG", "logger.debug only if duplicating to log.")

    if "json.dumps" in s:
        return ("— (TTY)", "Structured/pretty output; terminal-primary.")

    if re.search(r"console\.print\s*\(\s*table\s*\)", s) or re.search(
        r"console\.print\s*\(\s*\w*table\s*\)", s
    ):
        return (
            "INFO",
            "Table result; terminal-primary; summary line to INFO optional.",
        )

    if 'console.print("\\n")' in s or "console.print('\\n')" in s:
        return ("—", "Spacer; no logger.")

    return ("INFO", "Default CLI message; classify after reading surrounding code.")


def main() -> None:
    """Write appendix text file and per-file Markdown report."""
    rows = scan_sources()
    APPENDIX.parent.mkdir(parents=True, exist_ok=True)
    with APPENDIX.open("w", encoding="utf-8") as f:
        for rel, i, kind, snippet in rows:
            f.write(f"{rel}:{i}:{kind}:{snippet}\n")

    by_file: dict[str, list[tuple[int, str, str, str, str]]] = defaultdict(list)
    for rel, i, kind, snippet in rows:
        level, note = classify(rel, kind, snippet)
        by_file[rel].append((i, kind, level, note, snippet))

    lines: list[str] = [
        "# Terminal output inventory — per-file detail",
        "",
        "Auto-generated by `dev/scripts/generate_terminal_output_inventory.py`. "
        "Regenerate after changing CLI output.",
        "",
        "**Legend:** Proposed levels assume you want the same information in "
        "**log files** when useful. `—` means *do not* map to the application "
        "logger for that line.",
        "",
        "| Proposed | Meaning |",
        "|----------|---------|",
        "| ERROR | `logger.error` |",
        "| WARNING | `logger.warning` |",
        "| INFO | `logger.info` |",
        "| DEBUG | `logger.debug` (visible at `-vv`) |",
        "| TRACE | `logger.log(TRACE, ...)` (visible at `-vvv`) |",
        "| — | No logger / stdout-only / script |",
        "",
    ]

    for path in sorted(by_file):
        entries = sorted(by_file[path], key=lambda x: x[0])
        lines.append(f"## `{path}`")
        lines.append("")
        lines.append("| Line | Kind | Proposed | Resolution | Snippet |")
        lines.append("|-----:|:-----|:---------|:-----------|:--------|")
        for line_no, kind, level, note, snip in entries:
            esc = snip.replace("|", "\\|").replace("\n", " ")
            if len(esc) > SNIPPET_COL_MAX:
                esc = esc[: SNIPPET_COL_MAX - 3] + "..."
            note_esc = note.replace("|", "\\|")
            row = (
                f"| {line_no} | `{kind}` | **{level}** | {note_esc} | `{esc}` |"
            )
            lines.append(row)
        lines.append("")

    DETAILED.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(rows)} lines -> {APPENDIX.relative_to(ROOT)}")
    print(f"Wrote {DETAILED.relative_to(ROOT)} ({len(by_file)} files)")


if __name__ == "__main__":
    main()
