#!/usr/bin/env python3
"""Map changed files to pytest markers based on .codecov.yml configuration.

This script reads changed file paths from stdin (provided by pre-commit)
and outputs a pytest marker expression that should be used to run only
tests relevant to the changed files.

Enhanced with:
- Dependency-aware marker detection (finds modules that depend on changed files)
- Cross-cutting concern detection (config, models, events affect multiple modules)
- Improved pattern matching (handles glob patterns like dht_*.py)

Usage:
    echo "ccbt/peer.py" | python scripts/get_test_markers.py
    # Output: "peer"

    echo -e "ccbt/peer.py\nccbt/piece_manager.py" | python scripts/get_test_markers.py
    # Output: "peer or piece"
"""

from __future__ import annotations

import fnmatch
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
    "dev/pytest.ini",
    "dev/.codecov.yml",
    "dev/pre-commit-config.yaml",
}

# Cross-cutting concern patterns: (file_pattern, [markers])
# Empty markers list means run all tests
CRITICAL_PATTERNS = [
    ("ccbt/config/config.py", ["cli", "session", "core"]),
    ("ccbt/models.py", ["core", "piece", "tracker"]),
    ("ccbt/utils/events.py", []),  # Empty = all tests
]


def load_codecov_config(config_path: Path = Path("dev/.codecov.yml")) -> dict[str, Any]:
    """Load and parse .codecov.yml configuration file."""
    if not config_path.exists():
        logger.warning(f"Configuration file not found: {config_path}; defaulting to all tests")
        return {}

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

    # Check for directory matches and glob patterns
    for pattern_path, pattern_markers in mapping.items():
        # Skip if already matched as exact file
        if pattern_path == normalized_path:
            continue

        # Check for glob patterns (e.g., dht_*.py)
        if "*" in pattern_path:
            # Use fnmatch for glob pattern matching
            if fnmatch.fnmatch(normalized_path, pattern_path):
                markers.update(pattern_markers)
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


def get_cross_cutting_markers(file_path: str) -> set[str] | None:
    """Get markers for cross-cutting concern files.

    Args:
        file_path: Path to the changed file

    Returns:
        Set of markers if file is a cross-cutting concern, None otherwise.
        Empty set means run all tests.
    """
    normalized = file_path.replace("\\", "/")
    for pattern, markers in CRITICAL_PATTERNS:
        if normalized == pattern or normalized.endswith("/" + pattern):
            logger.info(f"Cross-cutting concern detected: {file_path} → {markers or 'all tests'}")
            return set(markers) if markers else set()  # Empty set = all tests
    return None


def get_markers_for_files(file_paths: list[str]) -> set[str]:
    """Get all markers for a list of changed files.

    Enhanced with dependency-aware detection and cross-cutting concerns.

    Args:
        file_paths: List of changed file paths

    Returns:
        Set of marker names (empty set means run all tests)
    """
    # Check for critical files first
    if any(is_critical_file(fp) for fp in file_paths):
        logger.info("Critical file detected - running all tests")
        return set()  # Empty set means run all tests

    # Check for cross-cutting concerns
    cross_cutting_markers: set[str] | None = None
    for file_path in file_paths:
        cc_markers = get_cross_cutting_markers(file_path)
        if cc_markers is not None:
            if not cc_markers:  # Empty set = all tests
                logger.info("Cross-cutting concern requires all tests")
                return set()
            cross_cutting_markers = cross_cutting_markers or set()
            cross_cutting_markers.update(cc_markers)

    # Load dependency graph for dependency-aware detection
    try:
        # Import with relative path handling
        import sys
        from pathlib import Path

        script_dir = Path(__file__).parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        from get_dependent_modules import get_dependent_modules, load_or_build_graph  # type: ignore[import-untyped]

        dependency_graph = load_or_build_graph()
        logger.debug(f"Loaded dependency graph with {len(dependency_graph)} entries")
    except Exception as e:
        logger.warning(f"Failed to load dependency graph: {e}, continuing without dependency detection")
        dependency_graph = None

    # Load configuration
    config = load_codecov_config()
    mapping = build_file_to_marker_mapping(config)

    # Collect all markers for all changed files
    all_markers: set[str] = set()
    matched_files: list[str] = []
    dependent_modules: set[str] = set()

    for file_path in file_paths:
        # Skip test files and non-Python files
        if file_path.startswith("tests/") or file_path.startswith("benchmarks/"):
            continue
        if not file_path.endswith(".py"):
            continue

        # Direct marker matching
        file_markers = match_file_to_markers(file_path, mapping)
        if file_markers:
            all_markers.update(file_markers)
            matched_files.append(file_path)
            logger.debug(f"File {file_path} → markers: {sorted(file_markers)}")

        # Dependency-aware detection: find modules that depend on this file
        if dependency_graph:
            try:
                dependents = get_dependent_modules([file_path], dependency_graph)
                if dependents:
                    dependent_modules.update(dependents)
                    logger.debug(
                        f"File {file_path} has {len(dependents)} dependent modules: "
                        f"{sorted(list(dependents)[:5])}..."
                    )
            except Exception as e:
                logger.debug(f"Failed to get dependents for {file_path}: {e}")

    # Map dependent modules back to markers
    if dependent_modules:
        for module_path in dependent_modules:
            # Convert module path to file path (e.g., "ccbt.peer.peer" -> "ccbt/peer/peer.py")
            module_file_path = module_path.replace(".", "/") + ".py"
            dep_markers = match_file_to_markers(module_file_path, mapping)
            if dep_markers:
                all_markers.update(dep_markers)
                logger.debug(f"Dependent module {module_path} → markers: {sorted(dep_markers)}")

    # Add cross-cutting markers
    if cross_cutting_markers:
        all_markers.update(cross_cutting_markers)

    # If no markers found, run all tests (safety fallback)
    if not all_markers:
        logger.info("No markers matched - running all tests (safety fallback)")
        return set()

    logger.info(f"Matched {len(matched_files)} files to markers: {sorted(all_markers)}")
    if dependent_modules:
        logger.info(f"Found {len(dependent_modules)} dependent modules")

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
