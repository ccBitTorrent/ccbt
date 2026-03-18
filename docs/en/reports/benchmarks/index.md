# Performance Benchmarks

This page provides access to performance benchmark results for ccBitTorrent. Benchmark data (timeseries and runs) is generated in CI; links may be unavailable on Read the Docs. To view or generate data locally, use the commands under "Running Benchmarks" below.

## Benchmark Overview

Performance benchmarks measure various aspects of the BitTorrent client's performance, including:
- Disk I/O operations
- Encryption/decryption performance
- Hash verification speed
- Network throughput (loopback)
- Piece assembly operations

## Benchmark Data

### Time Series Data

Time series data tracks benchmark performance over time:
- [Loopback Throughput](timeseries/loopback_throughput_timeseries.json) - Network throughput over time

### Individual Runs

Individual benchmark run data is stored in the [runs/](runs/) directory, organized by:
- Benchmark name (e.g., `disk_io`, `encryption`, `hash_verify`, `loopback_throughput`, `piece_assembly`)
- Timestamp and git commit hash

## Benchmark Categories

### Disk I/O Benchmarks
Measure file read/write performance, buffer operations, and storage efficiency.

### Encryption Benchmarks
Evaluate encryption and decryption performance for secure peer connections. See the [Encryption benchmark report](../../performance/encryption_benchmark_report.md) for detailed results.

### Hash Verification
Test SHA-1 hash computation speed for piece verification.

### Network Throughput
Measure data transfer rates using loopback connections.

### Piece Assembly
Benchmark piece reconstruction and file assembly operations.

## Running Benchmarks

Benchmarks are run as part of the CI/CD pipeline and can also be executed locally. The main benchmark scripts live in `tests/performance/` and are run as Python scripts:

```bash
# Run all standalone benchmarks (quick mode)
uv run python tests/scripts/bench_all.py

# Run a specific benchmark script
uv run python tests/performance/bench_hash_verify.py --quick
uv run python tests/performance/bench_disk_io.py --quick
uv run python tests/performance/bench_piece_assembly.py --quick
uv run python tests/performance/bench_loopback_throughput.py --quick
uv run python tests/performance/bench_encryption.py --quick
```

For pytest-based performance tests (with optional pytest-benchmark plugin):

```bash
uv run pytest tests/performance/test_benchmarks.py -v
```

See the [Benchmark Assessment](BENCHMARK_ASSESSMENT.md) for what each benchmark measures and current gaps.

## Recording benchmarks

For recording modes and storage, benchmarks can be recorded with different modes to track performance over time.

### Recording modes

- **`pre-commit`**: Records during pre-commit hook runs (quick smoke tests)
- **`commit`**: Records during actual commits (full benchmarks, recorded in both per-run and timeseries)
- **`both`**: Records in both pre-commit and commit contexts
- **`auto`**: Automatically detects context (uses `PRE_COMMIT` env var)
- **`none`**: No recording (benchmark runs but doesn't save results)

### Running with recording

```bash
# Pre-commit mode (quick smoke test)
uv run python tests/performance/bench_hash_verify.py --quick --record-mode=pre-commit

# Commit mode (full benchmark)
uv run python tests/performance/bench_hash_verify.py --record-mode=commit

# Both modes
uv run python tests/performance/bench_hash_verify.py --record-mode=both

# Auto-detect mode (default)
uv run python tests/performance/bench_hash_verify.py --record-mode=auto
```

### Benchmark data storage

1. **Per-run files** (`docs/reports/benchmarks/runs/`): Individual JSON files per run; filename format `{benchmark_name}-{timestamp}-{commit_hash_short}.json`; full metadata (git commit, branch, author, platform, results).

2. **Time-series files** (`docs/reports/benchmarks/timeseries/`): Aggregated historical data; format `{benchmark_name}_timeseries.json` for performance trends.

Legacy artifacts may still be written to `site/reports/benchmarks/artifacts/` when using `--output-dir`; the recording system above is recommended for tracking over time.

## Performance Targets

See the [Performance Tuning Guide](../../performance.md) for performance optimization strategies and target metrics.

## Report Generation

Benchmark results are automatically collected and stored in JSON format. The benchmark system tracks:
- Execution time
- Throughput metrics
- Resource usage
- Platform information
- Git metadata

## Last Updated

Benchmark data is updated during CI/CD runs. Check individual JSON files for timestamps and commit information.

