#!/usr/bin/env python3
"""Validate benchmark runner scripts before CI executes them."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def validate_benchmark_scripts() -> list[str]:
    """Return a list of validation errors for benchmark scripts."""
    repo_root = Path(__file__).resolve().parents[2]
    targets = [
        repo_root / "dev" / "scripts" / "run_benchmark_suite.py",
        repo_root / "dev" / "scripts" / "compare_benchmark_json.py",
        repo_root / "dev" / "scripts" / "render_benchmark_docs.py",
        repo_root / "dev" / "scripts" / "validate_benchmark_scripts.py",
        *sorted((repo_root / "tests" / "performance").glob("bench_*.py")),
    ]
    errors: list[str] = []
    for path in targets:
        if not path.is_file():
            errors.append(f"missing benchmark script: {path}")
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"syntax error in {path}: {exc}")
    return errors


def main() -> int:
    errors = validate_benchmark_scripts()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
