#!/usr/bin/env python3
"""Map changed files to benchmark scripts.

This script reads changed file paths from stdin and outputs a list of
benchmark scripts that should be run based on the code changes.

Usage:
    echo "ccbt/storage/disk_io.py" | python tests/scripts/get_benchmark_markers.py
    # Output: bench_disk_io.py

    echo -e "ccbt/piece/piece_manager.py\nccbt/security/encryption.py" | python tests/scripts/get_benchmark_markers.py
    # Output: bench_hash_verify.py bench_piece_assembly.py bench_encryption.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Mapping from benchmark scripts to code paths they test
BENCHMARK_MAPPINGS = {
    "bench_disk_io.py": [
        "ccbt/storage/disk_io.py",
    ],
    "bench_hash_verify.py": [
        "ccbt/piece/",
    ],
    "bench_piece_assembly.py": [
        "ccbt/piece/",
        "ccbt/storage/file_assembler.py",
    ],
    "bench_encryption.py": [
        "ccbt/security/",
    ],
    "bench_loopback_throughput.py": [
        "ccbt/peer/",
        "ccbt/protocols/",
        "ccbt/utils/network_optimizer.py",
    ],
}


def get_file_module_path(file_path: str) -> str:
    """Convert file path to module path.

    Args:
        file_path: File path (e.g., "ccbt/peer/peer.py")

    Returns:
        Module path (e.g., "ccbt.peer.peer")
    """
    normalized = file_path.replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".")


def match_file_to_benchmarks(file_path: str) -> set[str]:
    """Match a file path to benchmark scripts.

    Args:
        file_path: Path to the changed file (relative to repo root)

    Returns:
        Set of benchmark script names that should be run
    """
    benchmarks: set[str] = set()
    normalized_path = file_path.replace("\\", "/")  # Normalize Windows paths

    # Skip non-Python files
    if not normalized_path.endswith(".py"):
        return benchmarks

    # Skip test files
    if normalized_path.startswith("tests/") or normalized_path.startswith("benchmarks/"):
        return benchmarks

    # Check each benchmark mapping
    for benchmark_script, code_paths in BENCHMARK_MAPPINGS.items():
        for code_path in code_paths:
            # Check for exact file matches
            if normalized_path == code_path:
                benchmarks.add(benchmark_script)
                continue

            # Check for directory matches
            if code_path.endswith("/"):
                # Directory pattern
                if normalized_path.startswith(code_path):
                    benchmarks.add(benchmark_script)
            else:
                # Check if file is in this directory/subdirectory
                if normalized_path.startswith(code_path + "/"):
                    benchmarks.add(benchmark_script)

    return benchmarks


def get_benchmarks_for_files(file_paths: list[str]) -> set[str]:
    """Get all benchmark scripts for a list of changed files.

    Args:
        file_paths: List of changed file paths

    Returns:
        Set of benchmark script names
    """
    all_benchmarks: set[str] = set()
    matched_files: list[str] = []

    # Check for dependency-aware selection (optional enhancement)
    # For now, we do direct matching. Can be enhanced later with dependency graph.
    try:
        # Import with relative path handling
        import sys
        from pathlib import Path

        script_dir = Path(__file__).parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        from get_dependent_modules import get_dependent_modules, load_or_build_graph  # type: ignore[import-untyped]

        dependency_graph = load_or_build_graph()
        logger.debug(f"Loaded dependency graph for benchmark selection ({len(dependency_graph)} entries)")
    except Exception as e:
        logger.debug(f"Failed to load dependency graph: {e}, using direct matching only")
        dependency_graph = None

    for file_path in file_paths:
        # Direct matching
        file_benchmarks = match_file_to_benchmarks(file_path)
        if file_benchmarks:
            all_benchmarks.update(file_benchmarks)
            matched_files.append(file_path)
            logger.debug(f"File {file_path} → benchmarks: {sorted(file_benchmarks)}")

        # Dependency-aware: if a module that benchmarks depend on changes,
        # also run those benchmarks
        if dependency_graph:
            try:
                # Check if any benchmark's code paths depend on this file
                module_path = get_file_module_path(file_path)
                dependents = get_dependent_modules([file_path], dependency_graph)

                # For each dependent module, check if it matches any benchmark mapping
                for dependent_module in dependents:
                    dependent_file_path = dependent_module.replace(".", "/") + ".py"
                    dep_benchmarks = match_file_to_benchmarks(dependent_file_path)
                    if dep_benchmarks:
                        all_benchmarks.update(dep_benchmarks)
                        logger.debug(
                            f"Dependent module {dependent_module} → benchmarks: {sorted(dep_benchmarks)}"
                        )
            except Exception as e:
                logger.debug(f"Failed to check dependencies for {file_path}: {e}")

    logger.info(f"Matched {len(matched_files)} files to benchmarks: {sorted(all_benchmarks)}")
    return all_benchmarks


def main() -> None:
    """Main entry point."""
    # Read file paths from stdin (provided by pre-commit)
    file_paths = [line.strip() for line in sys.stdin if line.strip()]

    if not file_paths:
        # No files changed, nothing to do
        logger.info("No files changed")
        print("")
        return

    logger.info(f"Processing {len(file_paths)} changed file(s) for benchmark selection")

    # Get benchmarks for changed files
    benchmarks = get_benchmarks_for_files(file_paths)

    # Output benchmark script names (space-separated)
    if benchmarks:
        print(" ".join(sorted(benchmarks)))
    else:
        print("")


if __name__ == "__main__":
    main()

