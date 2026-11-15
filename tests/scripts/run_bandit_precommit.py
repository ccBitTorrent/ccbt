#!/usr/bin/env python3
"""Create bandit report dirs and run a medium-severity scan (pre-commit)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Ensure report dirs exist, then run bandit against ccbt/."""
    for relative in ("docs/reports/bandit", "site/reports/bandit"):
        Path(relative).mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "bandit",
        "-c",
        "pyproject.toml",
        "-r",
        "ccbt/",
        "--severity-level",
        "medium",
        "-q",
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
