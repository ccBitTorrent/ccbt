#!/usr/bin/env python3
"""Record benchmark results on git commits.

This script is called by the post-commit git hook and:
1. Gets changed files from the last commit
2. Determines which benchmarks to run based on changed files
3. Runs benchmarks with --record-mode=commit
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


def get_changed_files_in_commit() -> list[str]:
    """Get list of files changed in the last commit.

    Returns:
        List of file paths relative to repository root
    """
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return files
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"Failed to get changed files from git: {e}")
        return []


def get_benchmarks_to_run() -> list[str]:
    """Determine which benchmarks to run based on changed files.

    Returns:
        List of benchmark script names (e.g., ["bench_hash_verify.py"])
    """
    changed_files = get_changed_files_in_commit()
    if not changed_files:
        logger.info("No files changed in commit, skipping benchmarks")
        return []

    # Import get_benchmarks_for_files from get_benchmark_markers
    try:
        # Add tests/scripts to path if needed
        script_dir = Path(__file__).parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        from get_benchmark_markers import get_benchmarks_for_files  # type: ignore[import-untyped]

        benchmarks = get_benchmarks_for_files(changed_files)
        logger.info(f"Changed files: {changed_files}")
        logger.info(f"Selected benchmarks: {sorted(benchmarks)}")
        return sorted(benchmarks)
    except ImportError as e:
        logger.error(f"Failed to import get_benchmark_markers: {e}")
        return []


def run_benchmark_commit(script_name: str) -> int:
    """Run a benchmark script with commit recording mode.

    Args:
        script_name: Name of benchmark script (e.g., "bench_hash_verify.py")

    Returns:
        Exit code from benchmark script
    """
    repo_root = Path(__file__).parent.parent.parent
    script_path = repo_root / "tests" / "performance" / script_name
    config_file = repo_root / "docs" / "examples" / "example-config-performance.toml"

    if not script_path.exists():
        logger.error(f"Benchmark script not found: {script_path}")
        return 1

    cmd = [
        "uv",
        "run",
        "python",
        str(script_path),
        "--record-mode=commit",
        f"--config-file={config_file}",
    ]

    logger.info(f"Running benchmark: {script_name}")
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            check=False,
            timeout=600,  # 10 minute timeout
        )
        if result.returncode == 0:
            logger.info(f"Benchmark {script_name} completed successfully")
        else:
            logger.warning(f"Benchmark {script_name} exited with code {result.returncode}")
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error(f"Benchmark {script_name} timed out after 10 minutes")
        return 1
    except Exception as e:
        logger.error(f"Failed to run benchmark {script_name}: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    benchmarks = get_benchmarks_to_run()
    if not benchmarks:
        logger.info("No benchmarks to run")
        return 0

    logger.info(f"Running {len(benchmarks)} benchmark(s) for commit")
    exit_code = 0
    for benchmark in benchmarks:
        result = run_benchmark_commit(benchmark)
        if result != 0:
            exit_code = result
            # Continue running other benchmarks even if one fails

    if exit_code == 0:
        logger.info("All benchmarks completed successfully")
    else:
        logger.warning("Some benchmarks failed, but continuing")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

