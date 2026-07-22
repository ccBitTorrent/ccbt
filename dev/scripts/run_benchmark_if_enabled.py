#!/usr/bin/env python3
"""Wrapper script to conditionally run benchmarks based on SKIP_BENCHMARKS environment variable.

This script checks the SKIP_BENCHMARKS environment variable and skips benchmark execution
if it's set to a truthy value (1, true, yes, on).

Usage:
    uv run python dev/scripts/run_benchmark_if_enabled.py python tests/performance/bench_hash_verify.py --quick
    # Or with uv run:
    uv run python dev/scripts/run_benchmark_if_enabled.py uv run python tests/performance/bench_hash_verify.py --quick

To skip benchmarks:
    git commit --no-verify   # skips all pre-commit hooks including benchmarks
    SKIP_BENCHMARKS=1 git commit   # skips only benchmark hooks
    # Or set it in your shell:
    export SKIP_BENCHMARKS=1
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    """Main entry point."""
    # Check if benchmarks should be skipped
    skip_benchmarks = os.environ.get("SKIP_BENCHMARKS", "").lower()
    if skip_benchmarks in ("1", "true", "yes", "on"):
        print(f"Skipping benchmark (SKIP_BENCHMARKS={os.environ.get('SKIP_BENCHMARKS')})", file=sys.stderr)
        return 0

    if len(sys.argv) < 2:
        print("Usage: run_benchmark_if_enabled.py <command> [args...]", file=sys.stderr)
        return 1

    # Check if first arg is 'uv' and handle uv run commands
    cmd = sys.argv[1:]
    if cmd[0] == "uv" and len(cmd) > 1 and cmd[1] == "run":
        # Handle: uv run python script.py args...
        # Execute: uv run python script.py args...
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except Exception as e:
            print(f"Error running benchmark: {e}", file=sys.stderr)
            return 1
    elif cmd[0] == "python" or (shutil.which(cmd[0]) is not None):
        # Direct command execution
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except Exception as e:
            print(f"Error running benchmark: {e}", file=sys.stderr)
            return 1
    else:
        # Fallback: try to execute as-is
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except Exception as e:
            print(f"Error running benchmark: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())

