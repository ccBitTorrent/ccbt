# Performance Benchmarks

This page provides access to performance benchmark results for ccBitTorrent.

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
Evaluate encryption and decryption performance for secure peer connections.

### Hash Verification
Test SHA-1 hash computation speed for piece verification.

### Network Throughput
Measure data transfer rates using loopback connections.

### Piece Assembly
Benchmark piece reconstruction and file assembly operations.

## Running Benchmarks

Benchmarks are run as part of the CI/CD pipeline and can also be executed locally:

```bash
# Run all benchmarks
uv run pytest benchmarks/ -v

# Run specific benchmark
uv run pytest benchmarks/bench_disk.py -v
```

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

