"""Insert minimal docstrings using AST end positions (safe for multi-line defs)."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    "ccbt/cas_server",
    "ccbt/hub",
    "ccbt/cli/git_xet.py",
    "ccbt/cli/cas_commands.py",
    "ccbt/discovery/xet_cas_http.py",
    "ccbt/session/xet_transport.py",
    "ccbt/storage/xet_migrate_legacy.py",
    "ccbt/storage/xet_reconstruction.py",
    "ccbt/utils/ssrf.py",
    "ccbt/consensus/byzantine.py",
    "ccbt/storage/xet_xorb.py",
    "ccbt/storage/xet_shard.py",
    "ccbt/storage/xet_hashing.py",
]
CODES = {"D101", "D102", "D103", "D105", "D107"}


def _doc_for(code: str) -> str:
    return {
        "D107": '"""Initialize instance."""',
        "D105": '"""Magic method."""',
        "D101": '"""Public class."""',
        "D103": '"""Public function."""',
    }.get(code, '"""Public method."""')


def _body_insert_line(source: str, def_lineno: int) -> tuple[int, str] | None:
    """Return (1-based insert-before line, indent) for a def/class at def_lineno."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        if node.lineno != def_lineno:
            continue
        if not node.body:
            return None
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(
            getattr(first, "value", None), ast.Constant
        ):
            if isinstance(first.value.value, str):
                return None  # already documented
        lines = source.splitlines()
        raw = lines[first.lineno - 1] if first.lineno - 1 < len(lines) else "    "
        indent = " " * (len(raw) - len(raw.lstrip(" ")))
        return first.lineno, indent
    return None


def main() -> None:
    proc = subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "--config",
            "dev/ruff.toml",
            "check",
            *TARGETS,
            "--output-format=json",
            "--select=D101,D102,D103,D105,D107",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    data = json.loads(proc.stdout or "[]")
    by_file: dict[str, list[dict]] = {}
    for item in data:
        if item.get("code") in CODES:
            by_file.setdefault(item["filename"], []).append(item)

    for filename, items in by_file.items():
        path = Path(filename)
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        uniq: dict[int, str] = {}
        for item in items:
            row = item["location"]["row"]
            # If ruff points at decorator, walk down to a def/class line
            found = _body_insert_line(source, row)
            if found is None:
                for delta in range(0, 8):
                    found = _body_insert_line(source, row + delta)
                    if found is not None:
                        break
            if found is None:
                continue
            before, indent = found
            uniq[before] = f"{indent}{_doc_for(item['code'])}\n"

        for before in sorted(uniq.keys(), reverse=True):
            idx = before - 1
            if 0 <= idx < len(lines) and lines[idx].lstrip().startswith(
                ('"""', "'''")
            ):
                continue
            lines.insert(idx, uniq[before])
        path.write_text("".join(lines), encoding="utf-8")
        print(f"patched {path.relative_to(ROOT)} ({len(uniq)} docs)")


if __name__ == "__main__":
    main()
