#!/usr/bin/env python3
"""Wrapper script to run benchmarks selectively based on changed files.

This script is called by pre-commit and:
1. Reads changed files from command line arguments (provided by pre-commit)
2. Determines which benchmarks to run
3. Runs only the relevant benchmarks

Usage:
    python tests/scripts/run_benchmarks_selective.py  # for selective benchmarks
    python tests/scripts/run_benchmarks_selective.py --full-suite  # for all benchmarks
"""

from __future__ import annotations

import logging
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

# Benchmark scripts directory
BENCHMARK_DIR = Path(__file__).parent.parent / "performance"

# Example config file for benchmarks
EXAMPLE_CONFIG = Path(__file__).parent.parent.parent / "docs" / "examples" / "example-config-performance.toml"


def get_benchmark_scripts(file_paths: list[str]) -> list[str]:
    """Get benchmark scripts to run for changed files.

    Args:
        file_paths: List of changed file paths

    Returns:
        List of benchmark script names (e.g., ["bench_disk_io.py"])
    """
    script_path = Path(__file__).parent / "get_benchmark_markers.py"
    if not script_path.exists():
        logger.error(f"get_benchmark_markers.py not found at {script_path}")
        return []

    # Run get_benchmark_markers.py with file paths as input
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
            logger.warning(f"get_benchmark_markers.py failed: {stderr}")
            return []  # Fallback to no benchmarks

        benchmark_names = stdout.strip().split()
        return benchmark_names
    except Exception as e:
        logger.error(f"Failed to run get_benchmark_markers.py: {e}")
        return []  # Fallback to no benchmarks


def get_all_benchmark_scripts() -> list[str]:
    """Get all available benchmark scripts.

    Returns:
        List of all benchmark script names
    """
    benchmarks = [
        "bench_disk_io.py",
        "bench_hash_verify.py",
        "bench_piece_assembly.py",
        "bench_encryption.py",
        "bench_loopback_throughput.py",
    ]
    # Verify they exist
    existing = []
    for bench in benchmarks:
        if (BENCHMARK_DIR / bench).exists():
            existing.append(bench)
        else:
            logger.warning(f"Benchmark script not found: {bench}")
    return existing


def run_benchmark(script_name: str, quick: bool = True) -> int:
    """Run a single benchmark script.

    Args:
        script_name: Name of benchmark script (e.g., "bench_disk_io.py")
        quick: Whether to run with --quick flag

    Returns:
        Exit code from benchmark
    """
    script_path = BENCHMARK_DIR / script_name
    if not script_path.exists():
        logger.error(f"Benchmark script not found: {script_path}")
        return 1

    cmd = [sys.executable, str(script_path)]

    # Add --quick flag for faster runs
    if quick:
        cmd.append("--quick")

    # Add config file if it exists
    if EXAMPLE_CONFIG.exists():
        cmd.extend(["--config-file", str(EXAMPLE_CONFIG)])

    # Add specific arguments for certain benchmarks
    if script_name == "bench_disk_io.py":
        cmd.extend(["--sizes", "256KiB", "1MiB"])

    logger.info(f"Running benchmark: {script_name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=False, timeout=600)  # 10 minute timeout per benchmark
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error(f"Benchmark {script_name} timed out after 600s")
        return 1
    except Exception as e:
        logger.error(f"Failed to run benchmark {script_name}: {e}")
        return 1


def run_benchmarks(script_names: list[str], quick: bool = True) -> int:
    """Run multiple benchmark scripts.

    Args:
        script_names: List of benchmark script names
        quick: Whether to run with --quick flag

    Returns:
        Exit code (0 if all passed, 1 if any failed)
    """
    if not script_names:
        logger.info("No benchmarks to run")
        return 0

    logger.info(f"Running {len(script_names)} benchmark(s): {', '.join(script_names)}")

    exit_code = 0
    for script_name in script_names:
        result = run_benchmark(script_name, quick=quick)
        if result != 0:
            exit_code = 1
            logger.error(f"Benchmark {script_name} failed with exit code {result}")
            # Continue running other benchmarks
        else:
            logger.info(f"Benchmark {script_name} completed successfully")

    return exit_code


def main() -> int:
    """Main entry point."""
    # Check for flags
    full_suite = "--full-suite" in sys.argv or "--full" in sys.argv
    sys.argv = [arg for arg in sys.argv if arg not in ("--full-suite", "--full")]

    if full_suite:
        logger.info("Full suite mode: running all benchmarks")
        benchmarks = get_all_benchmark_scripts()
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
            benchmarks = get_benchmark_scripts(file_paths)
            if benchmarks:
                logger.info(f"Selected benchmarks: {benchmarks}")
            else:
                logger.info("No relevant benchmarks found for changed files")
                return 0  # No benchmarks to run is not an error
        else:
            # No ccbt/ Python files changed - skip benchmarks
            logger.info("No ccbt/ Python files changed - skipping benchmarks")
            return 0

    # Run benchmarks
    exit_code = run_benchmarks(benchmarks, quick=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

