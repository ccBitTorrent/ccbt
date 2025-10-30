#!/usr/bin/env python3
"""Map changed files to pytest markers based on .codecov.yml configuration.

This script reads changed file paths from stdin (provided by pre-commit)
and outputs a pytest marker expression that should be used to run only
tests relevant to the changed files.

Usage:
    echo "ccbt/peer.py" | python scripts/get_test_markers.py
    # Output: "peer"

    echo -e "ccbt/peer.py\nccbt/piece_manager.py" | python scripts/get_test_markers.py
    # Output: "peer or piece"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Critical files that should always trigger all tests
CRITICAL_FILES = {
    "ccbt/config.py",
    "tests/conftest.py",
    "pytest.ini",
    ".codecov.yml",
    ".pre-commit-config.yaml",
}


def load_codecov_config(config_path: Path = Path(".codecov.yml")) -> dict[str, Any]:
    """Load and parse .codecov.yml configuration file."""
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with config_path.open() as f:
        try:
            config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse {config_path}: {e}")
            sys.exit(1)


def build_file_to_marker_mapping(config: dict[str, Any]) -> dict[str, list[str]]:
    """Build a mapping from file paths to pytest markers.

    Returns:
        Dictionary mapping file paths/patterns to list of marker names.
    """
    mapping: dict[str, list[str]] = {}
    flags = config.get("flags", {})

    for flag_name, flag_config in flags.items():
        paths = flag_config.get("paths", [])
        for path_pattern in paths:
            # Keep trailing slash for directories to distinguish from files
            normalized = path_pattern

            # Skip unittests flag as it's too broad (matches everything)
            if flag_name == "unittests":
                continue

            # For integration tests, we don't want to map ccbt files to it
            if flag_name == "integration" and not normalized.startswith("tests/"):
                continue

            if normalized not in mapping:
                mapping[normalized] = []
            mapping[normalized].append(flag_name)

    return mapping


def match_file_to_markers(
    file_path: str,
    mapping: dict[str, list[str]],
) -> set[str]:
    """Match a file path to pytest markers.

    Args:
        file_path: Path to the changed file (relative to repo root)
        mapping: Dictionary mapping paths/patterns to markers

    Returns:
        Set of marker names that match this file.
    """
    markers: set[str] = set()
    normalized_path = file_path.replace("\\", "/")  # Normalize Windows paths

    # Check for exact file matches first
    if normalized_path in mapping:
        markers.update(mapping[normalized_path])

    # Check for directory matches
    for pattern_path, pattern_markers in mapping.items():
        # Skip if already matched as exact file
        if pattern_path == normalized_path:
            continue

        # Check if file is in this directory pattern
        if pattern_path.endswith("/"):
            # Directory pattern with trailing slash
            if normalized_path.startswith(pattern_path):
                markers.update(pattern_markers)
        else:
            # Directory pattern without trailing slash - check if file is in subdirectory
            if normalized_path.startswith(pattern_path + "/"):
                markers.update(pattern_markers)

    return markers


def is_critical_file(file_path: str) -> bool:
    """Check if a file is critical and should trigger all tests."""
    normalized = file_path.replace("\\", "/")
    return normalized in CRITICAL_FILES


def get_markers_for_files(file_paths: list[str]) -> set[str]:
    """Get all markers for a list of changed files.

    Args:
        file_paths: List of changed file paths

    Returns:
        Set of marker names (empty set means run all tests)
    """
    # Check for critical files first
    if any(is_critical_file(fp) for fp in file_paths):
        logger.info("Critical file detected - running all tests")
        return set()  # Empty set means run all tests

    # Load configuration
    config = load_codecov_config()
    mapping = build_file_to_marker_mapping(config)

    # Collect all markers for all changed files
    all_markers: set[str] = set()
    matched_files: list[str] = []

    for file_path in file_paths:
        # Skip test files and non-Python files
        if file_path.startswith("tests/") or file_path.startswith("benchmarks/"):
            continue
        if not file_path.endswith(".py"):
            continue

        file_markers = match_file_to_markers(file_path, mapping)
        if file_markers:
            all_markers.update(file_markers)
            matched_files.append(file_path)
            logger.debug(f"File {file_path} → markers: {sorted(file_markers)}")

    # If no markers found, run all tests (safety fallback)
    if not all_markers:
        logger.info("No markers matched - running all tests (safety fallback)")
        return set()

    logger.info(f"Matched {len(matched_files)} files to markers: {sorted(all_markers)}")
    return all_markers


def format_marker_expression(markers: set[str]) -> str:
    """Format markers as a pytest marker expression.

    Args:
        markers: Set of marker names

    Returns:
        Marker expression string (e.g., "core or peer") or empty string for all tests
    """
    if not markers:
        return ""  # Empty means run all tests

    sorted_markers = sorted(markers)
    return " or ".join(sorted_markers)


def main() -> None:
    """Main entry point."""
    # Read file paths from stdin (provided by pre-commit)
    file_paths = [line.strip() for line in sys.stdin if line.strip()]

    if not file_paths:
        # No files changed, nothing to do
        logger.info("No files changed")
        print("")
        return

    logger.info(f"Processing {len(file_paths)} changed file(s)")

    # Get markers for changed files
    markers = get_markers_for_files(file_paths)

    # Format and output marker expression
    marker_expr = format_marker_expression(markers)
    print(marker_expr)


if __name__ == "__main__":
    main()
