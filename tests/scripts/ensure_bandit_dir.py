#!/usr/bin/env python3
"""Ensure bandit report directory exists before running bandit."""

from pathlib import Path

# Ensure docs/reports/bandit directory exists (used by workflows)
bandit_dir = Path("docs/reports/bandit")
bandit_dir.mkdir(parents=True, exist_ok=True)

# Also ensure site/reports/bandit exists (for backward compatibility)
site_bandit_dir = Path("site/reports/bandit")
site_bandit_dir.mkdir(parents=True, exist_ok=True)

