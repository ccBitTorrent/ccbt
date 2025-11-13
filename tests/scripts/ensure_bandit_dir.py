#!/usr/bin/env python3
"""Ensure bandit report directory exists before running bandit."""

import sys
from pathlib import Path

# Ensure site/reports/bandit directory exists
bandit_dir = Path("site/reports/bandit")
bandit_dir.mkdir(parents=True, exist_ok=True)

# Run bandit with all arguments passed through
import subprocess

cmd = [
    sys.executable, "-m", "bandit",
    "-r", "ccbt/",
    "-f", "json",
    "-o", "site/reports/bandit/bandit-report.json",
    "--severity-level", "medium",
    "-x", "tests,benchmarks,dev,dist,docs,htmlcov,site,.venv,.pre-commit-cache,.pre-commit-home,.pytest_cache,.ruff_cache,.hypothesis,.github,.ccbt,.cursor,.benchmarks,.mypy_cache,__pycache__,*.pyc,*.pyo,htmlcov,site",
]

sys.exit(subprocess.call(cmd))

