# Performance Tuning Guide

This guide covers performance optimization techniques for ccBitTorrent to achieve maximum download speeds and efficient resource usage.

## Network Optimization

### Connection Settings

#### Pipeline Depth

Controls the number of outstanding requests per peer.

Configuration: [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)

**Recommendations:**
- **High-latency connections**: 32-64 (satellite, mobile)
- **Low-latency connections**: 16-32 (fiber, cable)
- **Local networks**: 8-16 (LAN transfers)

Implementation: [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py) - Request pipelining

#### Block Size

Size of data blocks requested from peers.

Configuration: [ccbt.toml:13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L13)

**Recommendations:**
- **High-bandwidth**: 32-64 KiB (fiber, cable)
- **Medium-bandwidth**: 16-32 KiB (DSL, mobile)
- **Low-bandwidth**: 4-16 KiB (dial-up, slow mobile)

Min/Max block sizes: [ccbt.toml:14-15](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L14-L15)

#### Socket Buffers

Increase for high-throughput scenarios.

Configuration: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18)

Default values: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18) (256 KiB each)

TCP_NODELAY setting: [ccbt.toml:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L19)

### Connection Limits

#### Global Peer Limits

Configuration: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7)

**Tuning Guidelines:**
- **High-bandwidth**: Increase global peers (200-500)
- **Low-bandwidth**: Reduce global peers (50-100)
- **Many torrents**: Reduce per-torrent limit (10-25)
- **Few torrents**: Increase per-torrent limit (50-100)

Implementation: [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py) - Connection pool management

Max connections per peer: [ccbt.toml:8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L8)

#### Connection Timeouts

Configuration: [ccbt.toml:22-25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L25)

- Connection timeout: [ccbt.toml:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22)
- Handshake timeout: [ccbt.toml:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L23)
- Keep alive interval: [ccbt.toml:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L24)
- Peer timeout: [ccbt.toml:25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L25)

## Disk I/O Optimization

### Preallocation Strategy

Configuration: [ccbt.toml:59](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59)

**Recommendations:**
- **SSDs**: Use "full" for better performance
- **HDDs**: Use "sparse" to save space
- **Network storage**: Use "none" to avoid delays

Sparse files option: [ccbt.toml:60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L60)

Implementation: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Disk I/O operations

### Write Optimization

Configuration: [ccbt.toml:63-64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L64)

**Tuning Guidelines:**
- **Fast storage**: Increase batch size (128-256 KiB)
- **Slow storage**: Decrease batch size (32-64 KiB)
- **Critical data**: Enable sync_writes
- **Performance**: Disable sync_writes

Write batch size: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)

Write buffer size: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Sync writes setting: [ccbt.toml:82](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L82)

File assembler: [ccbt/storage/file_assembler.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/file_assembler.py)

### Memory Mapping

Configuration: [ccbt.toml:65-66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65-L66)

**Benefits:**
- Faster reads for completed pieces
- Reduced memory usage
- Better OS caching

**Considerations:**
- Requires sufficient RAM
- May cause memory pressure
- Best for read-heavy workloads

Use MMAP: [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

MMAP cache size: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

MMAP cache cleanup interval: [ccbt.toml:67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L67)

### Advanced I/O Features

#### io_uring (Linux)

Configuration: [ccbt.toml:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L84)

**Requirements:**
- Linux kernel 5.1+
- Modern storage devices
- Sufficient system resources

#### Direct I/O

Configuration: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)

**Use Cases:**
- High-performance storage
- Bypass OS page cache
- Consistent performance

Read ahead size: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

## Strategy Selection

### Piece Selection Algorithms

Configuration: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)

#### Rarest-First (Recommended)

**Benefits:**
- Optimal swarm health
- Faster completion times
- Better peer cooperation

Implementation: [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py) - Piece selection logic

Rarest first threshold: [ccbt.toml:107](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107)

#### Sequential

**Use Cases:**
- Streaming media files
- Sequential access patterns
- Priority-based downloads

Sequential window: [ccbt.toml:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L108)

Streaming mode: [ccbt.toml:104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L104)

#### Round-Robin

**Use Cases:**
- Simple scenarios
- Debugging
- Legacy compatibility

Implementation: [ccbt/piece/piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/piece_manager.py)

### Endgame Optimization

Configuration: [ccbt.toml:102-103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102-L103)

**Tuning:**
- **Fast connections**: Lower threshold (0.85-0.9)
- **Slow connections**: Higher threshold (0.95-0.98)
- **Many peers**: Increase duplicates (3-5)
- **Few peers**: Decrease duplicates (1-2)

Endgame threshold: [ccbt.toml:103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L103)

Endgame duplicates: [ccbt.toml:102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102)

Pipeline capacity: [ccbt.toml:109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L109)

### Piece Priorities

Configuration: [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

First piece priority: [ccbt.toml:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112)

Last piece priority: [ccbt.toml:113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L113)

## Rate Limiting

### Global Limits

Configuration: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)

Global download limit: [ccbt.toml:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140) (0 = unlimited)

Global upload limit: [ccbt.toml:141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L141) (0 = unlimited)

Network-level limits: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Implementation: [ccbt/security/rate_limiter.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/rate_limiter.py) - Rate limiting logic

### Per-Torrent Limits

Set limits via CLI using [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369) with `--download-limit` and `--upload-limit` options.

Per-torrent configuration: [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)

Per-peer limits: [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)

### Scheduler Settings

Scheduler time slice: [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

## Hash Verification

### Worker Threads

Configuration: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

**Tuning Guidelines:**
- **CPU cores**: Match or exceed core count
- **SSD storage**: Can handle more workers
- **HDD storage**: Limit workers (2-4)

Hash chunk size: [ccbt.toml:71](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L71)

Hash batch size: [ccbt.toml:72](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L72)

Hash queue size: [ccbt.toml:73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L73)

Implementation: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Hash verification workers

## Memory Management

### Buffer Sizes

Write buffer: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Read ahead: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

### Cache Settings

Cache size: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)

MMAP cache: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

Disk queue size: [ccbt.toml:77](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L77)

Disk workers: [ccbt.toml:76](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76)

## System-Level Optimization

### File System Tuning

For system-level optimizations, refer to your operating system's documentation. These are general recommendations that apply outside of ccBitTorrent configuration.

### Network Stack Tuning

For network stack optimizations, refer to your operating system's documentation. These are system-level settings that affect overall network performance.

## Monitoring Performance

### Key Metrics

Monitor these key metrics via Prometheus:

- **Download Speed**: `ccbt_download_rate_bytes_per_second` - See [ccbt/utils/metrics.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L142)
- **Upload Speed**: `ccbt_upload_rate_bytes_per_second` - See [ccbt/utils/metrics.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L148)
- **Connected Peers**: Available via MetricsCollector
- **Disk Queue Depth**: Available via MetricsCollector - See [ccbt/monitoring/metrics_collector.py]
- **Hash Queue Depth**: Available via MetricsCollector

Prometheus metrics endpoint: [ccbt/utils/metrics.py:179](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L179)

### Performance Profiling

Enable metrics: [ccbt.toml:164](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L164)

Metrics port: [ccbt.toml:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L165)

Access metrics at `http://localhost:9090/metrics` when enabled.

View metrics via CLI: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

## Troubleshooting Performance Issues

### Low Download Speeds

1. **Check peer connections**:
   Launch Bitonic dashboard: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

2. **Verify piece selection**:
   Configure in [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)
   
   Implementation: [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)

3. **Increase pipeline depth**:
   Configure in [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)
   
   Implementation: [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)

4. **Check rate limits**:
   Configuration: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
   
   CLI status command: [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

### High CPU Usage

1. **Reduce hash workers**:
   Configure in [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

2. **Disable memory mapping**:
   Configure in [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

3. **Increase refresh intervals**:
   Bitonic refresh interval: [ccbt/interface/terminal_dashboard.py:303](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L303)
   
   Dashboard config: [ccbt.toml:189](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L189)

### Disk I/O Bottlenecks

1. **Enable write batching**:
   Configure write batch size: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)
   
   Implementation: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)

2. **Use faster storage**:
   - Move downloads to SSD
   - Use RAID 0 for performance

3. **Optimize file system**:
   - Use appropriate file system
   - Tune mount options

## Benchmarking

### Benchmark Scripts

Performance benchmark scripts are located in `tests/performance/`:

- Hash verification: `tests/performance/bench_hash_verify.py`
- Disk I/O: `tests/performance/bench_disk_io.py`
- Piece assembly: `tests/performance/bench_piece_assembly.py`
- Loopback throughput: `tests/performance/bench_loopback_throughput.py`
- Encryption: `tests/performance/bench_encryption.py`

Run all benchmarks: [tests/scripts/bench_all.py](https://github.com/ccBittorrent/ccbt/blob/main/tests/scripts/bench_all.py)

Benchmark configuration example: [example-config-performance.toml](examples/example-config-performance.toml)

### Benchmark Recording

Benchmarks can be recorded with different modes to track performance over time:

#### Recording Modes

- **`pre-commit`**: Records during pre-commit hook runs (quick smoke tests)
- **`commit`**: Records during actual commits (full benchmarks, recorded in both per-run and timeseries)
- **`both`**: Records in both pre-commit and commit contexts
- **`auto`**: Automatically detects context (uses `PRE_COMMIT` env var)
- **`none`**: No recording (benchmark runs but doesn't save results)

#### Running Benchmarks with Recording

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

#### Benchmark Data Storage

Benchmark results are stored in two formats:

1. **Per-run files** (`docs/reports/benchmarks/runs/`):
   - Individual JSON files for each benchmark run
   - Filename format: `{benchmark_name}-{timestamp}-{commit_hash_short}.json`
   - Contains full metadata: git commit hash, branch, author, platform info, results

2. **Time-series files** (`docs/reports/benchmarks/timeseries/`):
   - Aggregated historical data in JSON format
   - Filename format: `{benchmark_name}_timeseries.json`
   - Enables easy querying of performance trends over time

For detailed information on querying historical data and benchmark reports, see [Benchmark Reports](reports/benchmarks/index.md).

### Test and Coverage Artifacts

When running the full test suite (pre-push/CI), artifacts are emitted to:

- `tests/.reports/junit.xml` (JUnit report)
- `tests/.reports/pytest.log` (test logs)
- `coverage.xml` and `htmlcov/` (coverage reports)

These integrate with Codecov; flags in `dev/.codecov.yml` are aligned to `ccbt/` subpackages to attribute coverage accurately (e.g., `peer`, `piece`, `protocols`, `extensions`). The coverage HTML report is automatically integrated into the documentation via the `mkdocs-coverage` plugin, which reads from `site/reports/htmlcov/` and renders it in [reports/coverage.md](reports/coverage.md).

#### Legacy Benchmark Artifacts

Legacy benchmark artifacts are still written to `site/reports/benchmarks/artifacts/` for backward compatibility when using the `--output-dir` argument. However, the new recording system is recommended for tracking performance over time.

## Best Practices

1. **Start with defaults**: Begin with default settings from [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
2. **Measure baseline**: Establish performance baseline using [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)
3. **Change one setting**: Modify one setting at a time in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
4. **Test thoroughly**: Verify improvements
5. **Monitor resources**: Watch CPU, memory, disk usage via [Bitonic](bitonic.md)
6. **Document changes**: Keep track of effective settings

## Configuration Templates

### High-Performance Setup

Reference high-performance configuration template: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Key settings:
- Network: [ccbt.toml:11-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L42)
- Disk: [ccbt.toml:57-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L85)
- Strategy: [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

Example: [example-config-performance.toml](examples/example-config-performance.toml)

### Low-Resource Setup

Reference low-resource configuration template: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Key settings:
- Network: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7) - Reduce peer limits
- Disk: [ccbt.toml:59-65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L65) - Use sparse preallocation, disable MMAP
- Strategy: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101) - Rarest-first remains optimal

For more detailed configuration options, see the [Configuration](configuration.md) documentation.
