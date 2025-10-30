#!/usr/bin/env python3
"""Wrapper script to run pytest with conditional markers based on changed files.

This script is called by pre-commit and:
1. Reads changed files from command line arguments (provided by pre-commit)
2. Determines which pytest markers to use
3. Runs pytest with the appropriate marker filter

Usage:
    python scripts/run_pytest_selective.py --coverage  # for coverage hook
    python scripts/run_pytest_selective.py  # for regular pytest hook
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_test_markers(file_paths: list[str]) -> str:
    """Get pytest marker expression for changed files.

    Args:
        file_paths: List of changed file paths

    Returns:
        Marker expression string (empty means run all tests)
    """
    script_path = Path(__file__).parent / "get_test_markers.py"
    if not script_path.exists():
        logger.error(f"get_test_markers.py not found at {script_path}")
        return ""

    # Run get_test_markers.py with file paths as input
    try:
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(input="\n".join(file_paths), timeout=30)

        if process.returncode != 0:
            logger.warning(f"get_test_markers.py failed: {stderr}")
            return ""  # Fallback to all tests

        marker_expr = stdout.strip()
        return marker_expr
    except Exception as e:
        logger.error(f"Failed to run get_test_markers.py: {e}")
        return ""  # Fallback to all tests


def _ensure_reports_dir() -> str:
    """Ensure the reports directory exists and return its path."""
    reports_dir = Path("tests/.reports")
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort; pytest will still run without artifact files
        logger.debug("Could not create reports directory", exc_info=True)
    return str(reports_dir)


def run_pytest(markers: str, coverage: bool = False) -> int:
    """Run pytest with optional marker filter and coverage.

    Args:
        markers: Marker expression (empty means run all tests)
        coverage: Whether to run with coverage

    Returns:
        Exit code from pytest
    """
    cmd = [sys.executable, "-m", "pytest", "tests/"]

    # Add marker filter if specified
    if markers:
        cmd.extend(["-m", markers])
        logger.info(f"Running tests with markers: {markers}")
    else:
        logger.info("Running all tests")

    # Add coverage options if requested
    if coverage:
        reports_dir = _ensure_reports_dir()
        cov_gate = os.getenv("CCBT_COV_FAIL_UNDER", "80")
        cmd.extend([
            "--cov=ccbt",
            "--cov-report=term-missing",
            "--cov-report=xml",
            f"--cov-fail-under={cov_gate}",
            f"--junitxml={reports_dir}/junit.xml",
            f"--log-file={reports_dir}/pytest.log",
        ])
    else:
        # Regular pytest options (timeouts/logging centralized in pytest.ini)
        cmd.extend([
            "-v",
            "--tb=short",
            "--maxfail=5",
        ])

    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> int:
    """Main entry point."""
    # Check for coverage flag (remove it from args)
    coverage = "--coverage" in sys.argv or "-c" in sys.argv
    sys.argv = [arg for arg in sys.argv if arg not in ("--coverage", "-c")]

    # With pass_filenames: true, pre-commit passes filenames as command line args
    # Filter out only Python files from ccbt/ directory
    file_paths = [
        arg
        for arg in sys.argv[1:]
        if arg.endswith(".py") and arg.startswith("ccbt/")
    ]

    if file_paths:
        logger.info(f"Processing {len(file_paths)} changed file(s): {file_paths}")
        markers = get_test_markers(file_paths)
    else:
        logger.info("No relevant files provided, running all tests")
        markers = ""

    # Run pytest
    exit_code = run_pytest(markers, coverage=coverage)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
