#!/usr/bin/env bash
# Wrapper script to conditionally run benchmarks based on SKIP_BENCHMARKS environment variable
# Usage: run_benchmark_if_enabled.sh <benchmark_command>
# Example: run_benchmark_if_enabled.sh "uv run python tests/performance/bench_hash_verify.py --quick"

set -e

if [ -n "${SKIP_BENCHMARKS}" ] && [ "${SKIP_BENCHMARKS}" != "0" ] && [ "${SKIP_BENCHMARKS}" != "false" ]; then
    echo "Skipping benchmark (SKIP_BENCHMARKS=${SKIP_BENCHMARKS})"
    exit 0
fi

# Execute the benchmark command
exec "$@"







