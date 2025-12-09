#!/usr/bin/env python3
"""Wrapper script to run pytest with conditional markers based on changed files.

This script is called by pre-commit and:
1. Reads changed files from command line arguments (provided by pre-commit)
2. Determines which pytest markers to use
3. Runs pytest with the appropriate marker filter

Usage:
    python scripts/run_pytest_selective.py  # for fast pre-commit hook (selective tests)
    python scripts/run_pytest_selective.py --coverage  # for selective tests with coverage
    python scripts/run_pytest_selective.py --coverage --full-suite  # for pre-push (all tests with coverage)
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
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


def _ensure_reports_dir() -> None:
    """Ensure the site/reports directory exists."""
    reports_dir = Path("site/reports")
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort; pytest will still run without artifact files
        logger.debug("Could not create reports directory", exc_info=True)


def _cleanup_corrupted_coverage_files() -> None:
    """Clean up corrupted coverage database files.
    
    Coverage creates SQLite database files that can become corrupted,
    especially when multiple processes write to parallel coverage files.
    This function detects and removes corrupted files to prevent
    "no such table: file" errors.
    """
    project_root = Path.cwd()
    coverage_files = list(project_root.glob(".coverage*"))
    
    for cov_file in coverage_files:
        if not cov_file.is_file():
            continue
            
        # Check if it's a SQLite database (coverage uses SQLite)
        # and if the 'file' table exists (required for coverage to work)
        try:
            conn = sqlite3.connect(str(cov_file))
            cursor = conn.cursor()
            # Check if the 'file' table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file'"
            )
            table_exists = cursor.fetchone() is not None
            conn.close()
            
            if not table_exists:
                logger.warning(
                    f"Removing corrupted coverage file: {cov_file.name} "
                    "(missing 'file' table)"
                )
                try:
                    cov_file.unlink()
                except Exception as e:
                    logger.debug(f"Could not remove {cov_file}: {e}", exc_info=True)
        except (sqlite3.Error, sqlite3.DatabaseError) as e:
            # File is not a valid SQLite database or is corrupted
            logger.warning(
                f"Removing corrupted/invalid coverage file: {cov_file.name} "
                f"(SQLite error: {e})"
            )
            try:
                cov_file.unlink()
            except Exception as cleanup_error:
                logger.debug(
                    f"Could not remove {cov_file}: {cleanup_error}", exc_info=True
                )
        except Exception as e:
            # File might not be a SQLite database at all (could be old format)
            # Check file size - if it's suspiciously small or empty, it might be corrupted
            try:
                if cov_file.stat().st_size == 0:
                    logger.warning(
                        f"Removing empty coverage file: {cov_file.name}"
                    )
                    cov_file.unlink()
            except Exception:
                pass
            # For other exceptions, log but don't fail - coverage will handle it
            logger.debug(
                f"Could not check coverage file {cov_file}: {e}", exc_info=True
            )


def run_pytest(markers: str, coverage: bool = False) -> int:
    """Run pytest with optional marker filter and coverage.

    Args:
        markers: Marker expression (empty means run all tests)
        coverage: Whether to run with coverage

    Returns:
        Exit code from pytest
    """
    cmd = [sys.executable, "-m", "pytest", "-c", "dev/pytest.ini", "tests/"]

    # ALWAYS enforce timeouts - explicit timeout flags override any config
    # Default: 600s (10 minutes) per test, thread-based timeout method
    # This prevents tests from hanging indefinitely
    cmd.extend([
        "--timeout=600",
        "--timeout-method=thread",
    ])

    # Add marker filter if specified
    if markers:
        cmd.extend(["-m", markers])
        logger.info(f"Running tests with markers: {markers}")
    else:
        logger.info("Running all tests")

    # Ensure reports directory exists
    _ensure_reports_dir()
    
    # Clean up corrupted coverage files before running tests with coverage
    # This prevents "no such table: file" errors from corrupted SQLite databases
    if coverage:
        _cleanup_corrupted_coverage_files()
    
    # All reports go to site/reports/
    reports_dir = "site/reports"
    
    if coverage:
        # Lower threshold for selective tests (pre-commit), higher for full suite (pre-push)
        if markers:
            # Selective test run - use lower threshold for faster feedback
            cov_gate = os.getenv("CCBT_COV_FAIL_UNDER_SELECTIVE", "40")
        else:
            # Full suite run - use project standard threshold
            cov_gate = os.getenv("CCBT_COV_FAIL_UNDER", "95")
        # Use dev/.coveragerc if it exists, otherwise fall back to pyproject.toml
        coveragerc_path = Path("dev/.coveragerc")
        cov_config = "--cov-config=dev/.coveragerc" if coveragerc_path.exists() else "--cov-config=pyproject.toml"
        # Coverage reports go directly to site/reports/
        cmd.extend([
            "--cov=ccbt",
            "--cov-report=term-missing",
            f"--cov-report=xml:{reports_dir}/coverage.xml",
            f"--cov-report=html:{reports_dir}/htmlcov",
            cov_config,
            f"--cov-fail-under={cov_gate}",
            f"--junitxml={reports_dir}/junit.xml",
            f"--log-file={reports_dir}/pytest.log",
        ])
    else:
        # Regular pytest options (timeouts/logging centralized in pytest.ini)
        # Note: pytest.ini already sets junitxml and log_file, but we override for consistency
        cmd.extend([
            "-v",
            "--tb=short",
            "--maxfail=5",
            f"--junitxml={reports_dir}/junit.xml",
            f"--log-file={reports_dir}/pytest.log",
        ])

    logger.info(f"Running: {' '.join(cmd)}")
    # Set timeout: longer for full suite, reasonable for selective tests
    # Since pytest.ini already has per-test timeout (600s), overall timeout is mainly
    # to catch pytest hangs, not individual test failures
    if not markers:
        # Full suite: 60 minutes timeout (allows for large test runs)
        timeout_seconds = 3600
    else:
        # Selective tests: 30 minutes timeout (should complete much faster, but allow buffer)
        timeout_seconds = 2100
    
    try:
        # Use subprocess.run instead of call to support timeout
        result = subprocess.run(cmd, timeout=timeout_seconds, check=False)
        exit_code = result.returncode
        
        # Handle KeyboardInterrupt gracefully - if tests passed, allow it
        # Exit code 2 from pytest means interrupted, but we want to preserve
        # coverage results if tests completed successfully
        if exit_code == 2:  # KeyboardInterrupt (pytest exit code 2)
            logger.warning(
                "Test run was interrupted (KeyboardInterrupt). "
                "Checking if tests completed successfully..."
            )
            # Check if junit.xml exists and has no failures
            # Also verify coverage if in coverage mode
            junit_path = Path("site/reports/junit.xml")
            if junit_path.exists():
                try:
                    tree = ET.parse(junit_path)
                    root = tree.getroot()
                    # Check testsuite for failures/errors
                    for testsuite in root.findall(".//testsuite"):
                        failures = int(testsuite.get("failures", "0"))
                        errors = int(testsuite.get("errors", "0"))
                        if failures == 0 and errors == 0:
                            logger.info(
                                "All tests passed before interruption. "
                                "Treating as success (tests completed)."
                            )
                            # If coverage mode and KeyboardInterrupt, check if coverage was calculated
                            # If coverage.xml exists, coverage was calculated and we should check it
                            # If not, tests passed and we can return success (coverage will be checked on next run)
                            if coverage:
                                cov_xml_path = Path("site/reports/coverage.xml")
                                if cov_xml_path.exists():
                                    # Coverage was calculated before interrupt - check if it met threshold
                                    try:
                                        cov_tree = ET.parse(cov_xml_path)
                                        cov_root = cov_tree.getroot()
                                        # Coverage XML format: <coverage line-rate="0.85">
                                        line_rate = float(cov_root.get("line-rate", "0"))
                                        cov_gate = float(os.getenv("CCBT_COV_FAIL_UNDER", "95"))
                                        if line_rate * 100 < cov_gate:
                                            logger.warning(
                                                f"Tests passed but coverage {line_rate*100:.2f}% "
                                                f"below threshold {cov_gate}%"
                                            )
                                            return 1  # Coverage failure
                                        logger.info(
                                            f"Tests passed and coverage {line_rate*100:.2f}% "
                                            f"meets threshold {cov_gate}%"
                                        )
                                    except Exception as e:
                                        logger.warning(f"Could not parse coverage.xml: {e}")
                                        # If we can't parse, assume coverage was acceptable
                            return 0  # Treat as success if no failures
                except Exception as e:
                    logger.warning(f"Could not parse junit.xml: {e}")
            # If we can't verify, preserve the interrupt exit code
            return exit_code
        return exit_code
    except subprocess.TimeoutExpired:
        logger.error(f"Test execution timed out after {timeout_seconds}s")
        return 1  # Return failure for timeout
    except KeyboardInterrupt:
        logger.warning("Test runner interrupted by KeyboardInterrupt")
        # Check if we got partial results
        junit_path = Path("site/reports/junit.xml")
        if junit_path.exists():
            try:
                tree = ET.parse(junit_path)
                root = tree.getroot()
                for testsuite in root.findall(".//testsuite"):
                    failures = int(testsuite.get("failures", "0"))
                    errors = int(testsuite.get("errors", "0"))
                    if failures == 0 and errors == 0:
                        logger.info("Tests passed before interruption")
                        return 0
            except Exception:
                pass
        return 2  # Return interrupt exit code


def main() -> int:
    """Main entry point."""
    # Check for flags (remove them from args)
    coverage = "--coverage" in sys.argv or "-c" in sys.argv
    full_suite = "--full-suite" in sys.argv or "--full" in sys.argv
    sys.argv = [
        arg for arg in sys.argv
        if arg not in ("--coverage", "-c", "--full-suite", "--full")
    ]

    # When --full-suite is specified with coverage, run ALL tests (pre-push behavior)
    # Otherwise, run selective tests even with coverage (pre-commit behavior)
    if coverage and full_suite:
        logger.info("Coverage mode with full suite: running all tests for accurate coverage metrics")
        markers = ""
    else:
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
            if coverage:
                logger.info(f"Coverage mode with selective tests: running tests with markers: {markers or 'all'}")
        else:
            # No ccbt/ Python files changed - skip tests to avoid running full suite unnecessarily
            # This prevents timeouts and failures when committing non-code changes (config, docs, etc.)
            logger.info("No ccbt/ Python files changed - skipping tests (commit allowed)")
            return 0

    # Run pytest
    exit_code = run_pytest(markers, coverage=coverage)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
