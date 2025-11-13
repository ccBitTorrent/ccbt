#!/usr/bin/env python3
"""Upload coverage reports to Codecov.

This script uploads coverage XML files to Codecov using the codecov CLI.
It reads the CODECOV_TOKEN environment variable for authentication.

Usage:
    python tests/scripts/upload_coverage.py [--file PATH] [--flags FLAGS]
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


def upload_to_codecov(
    coverage_file: Path,
    flags: str | None = None,
    token: str | None = None,
) -> int:
    """Upload coverage report to Codecov.

    Args:
        coverage_file: Path to coverage XML file
        flags: Optional coverage flags (e.g., "unittests")
        token: Codecov token (defaults to CODECOV_TOKEN env var)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if not coverage_file.exists():
        logger.warning(
            f"Coverage file not found: {coverage_file}. "
            "Skipping Codecov upload. "
            "Run tests with coverage first to generate the file."
        )
        return 0  # Don't fail if file doesn't exist (allows skipping upload)

    # Get token from parameter or environment
    if token is None:
        token = os.getenv("CODECOV_TOKEN")
        if not token:
            logger.warning(
                "CODECOV_TOKEN environment variable not set. "
                "Skipping Codecov upload. "
                "Set CODECOV_TOKEN to enable local coverage uploads."
            )
            return 0  # Don't fail if token is not set (allows local dev without token)

    # Build codecov command
    # The codecov Python package CLI format: python -m codecov [options]
    cmd = [
        sys.executable,
        "-m",
        "codecov",
        "--file",
        str(coverage_file),
    ]

    # Add token if provided
    if token:
        cmd.extend(["--token", token])

    # Add flags if provided
    if flags:
        cmd.extend(["--flags", flags])

    # Note: codecov CLI will auto-detect .codecov.yml in the project root
    # Our config is at dev/.codecov.yml, but codecov typically looks in root
    # The config file settings are mainly for CI/CD, local uploads use CLI args

    logger.info(f"Uploading coverage to Codecov: {coverage_file}")
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Successfully uploaded coverage to Codecov")
            if result.stdout:
                logger.debug(result.stdout)
        else:
            logger.error(f"Failed to upload coverage to Codecov: {result.stderr}")
            if result.stdout:
                logger.debug(result.stdout)
        return result.returncode
    except FileNotFoundError:
        logger.error(
            "codecov package not found. Install with: uv sync --dev"
        )
        return 1
    except Exception as e:
        logger.error(f"Error uploading to Codecov: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload coverage reports to Codecov"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("site/reports/coverage.xml"),
        help="Path to coverage XML file (default: site/reports/coverage.xml)",
    )
    parser.add_argument(
        "--flags",
        type=str,
        default="unittests",
        help="Coverage flags (default: unittests)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Codecov token (defaults to CODECOV_TOKEN env var)",
    )

    args = parser.parse_args()

    return upload_to_codecov(
        coverage_file=args.file,
        flags=args.flags,
        token=args.token,
    )


if __name__ == "__main__":
    sys.exit(main())

