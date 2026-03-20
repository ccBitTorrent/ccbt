# Performance Tuning Guide

This guide covers performance optimization techniques for ccBitTorrent to achieve maximum download speeds and efficient resource usage. For option reference see [Configuration](configuration.md).

## Network Optimization

### Connection Settings

#### Pipeline Depth

Controls the number of outstanding requests per peer.

Configuration: [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Recommendations:**
- **High-latency connections**: 32-64 (satellite, mobile)
- **Low-latency connections**: 16-32 (fiber, cable)
- **Local networks**: 8-16 (LAN transfers)

::: ccbt.peer.async_peer_connection.AsyncPeerConnectionManager
    options:
      show_root_heading: false
      heading_level: 4

#### Block Size

Size of data blocks requested from peers.

Configuration: [ccbt.toml:13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Recommendations:**
- **High-bandwidth**: 32-64 KiB (fiber, cable)
- **Medium-bandwidth**: 16-32 KiB (DSL, mobile)
- **Low-bandwidth**: 4-16 KiB (dial-up, slow mobile)

Min/Max block sizes: [ccbt.toml:14-15](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

#### Socket Buffers

Increase for high-throughput scenarios.

Configuration: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Default values: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) (256 KiB each)

TCP_NODELAY setting: [ccbt.toml:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Connection Limits

#### Global Peer Limits

Configuration: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Tuning Guidelines:**
- **High-bandwidth**: Increase global peers (200-500)
- **Low-bandwidth**: Reduce global peers (50-100)
- **Many torrents**: Reduce per-torrent limit (10-25)
- **Few torrents**: Increase per-torrent limit (50-100)

::: ccbt.peer.connection_pool.PeerConnectionPool
    options:
      show_root_heading: false
      heading_level: 4

Max connections per peer: [ccbt.toml:8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

#### Connection Timeouts

Configuration: [ccbt.toml:22-25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

- Connection timeout: [ccbt.toml:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Handshake timeout: [ccbt.toml:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Keep alive interval: [ccbt.toml:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Peer timeout: [ccbt.toml:25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

## Disk I/O Optimization

### Preallocation Strategy

Configuration: [ccbt.toml:59](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Recommendations:**
- **SSDs**: Use "full" for better performance
- **HDDs**: Use "sparse" to save space
- **Network storage**: Use "none" to avoid delays

Sparse files option: [ccbt.toml:60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

::: ccbt.storage.disk_io.DiskIOManager
    options:
      show_root_heading: false
      heading_level: 4

### Write Optimization

Configuration: [ccbt.toml:63-64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Tuning Guidelines:**
- **Fast storage**: Increase batch size (128-256 KiB)
- **Slow storage**: Decrease batch size (32-64 KiB)
- **Critical data**: Enable sync_writes
- **Performance**: Disable sync_writes

Write batch size: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Write buffer size: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Sync writes setting: [ccbt.toml:82](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

File assembler: [ccbt/storage/file_assembler.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/file_assembler.py)

### Memory Mapping

Configuration: [ccbt.toml:65-66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Benefits:**
- Faster reads for completed pieces
- Reduced memory usage
- Better OS caching

**Considerations:**
- Requires sufficient RAM
- May cause memory pressure
- Best for read-heavy workloads

Use MMAP: [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

MMAP cache size: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

MMAP cache cleanup interval: [ccbt.toml:67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Advanced I/O Features

#### io_uring (Linux)

Configuration: [ccbt.toml:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Requirements:**
- Linux kernel 5.1+
- Modern storage devices
- Sufficient system resources

#### Direct I/O

Configuration: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Use Cases:**
- High-performance storage
- Bypass OS page cache
- Consistent performance

Read ahead size: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

## Strategy Selection

### Piece Selection Algorithms

Configuration: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

#### Rarest-First (Recommended)

**Benefits:**
- Optimal swarm health
- Faster completion times
- Better peer cooperation

::: ccbt.piece.async_piece_manager.AsyncPieceManager
    options:
      show_root_heading: false
      heading_level: 4

Rarest first threshold: [ccbt.toml:107](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

#### Sequential

**Use Cases:**
- Streaming media files
- Sequential access patterns
- Priority-based downloads

Sequential window: [ccbt.toml:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Streaming mode: [ccbt.toml:104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

#### Round-Robin

**Use Cases:**
- Simple scenarios
- Debugging
- Legacy compatibility

::: ccbt.piece.piece_manager.PieceManager
    options:
      show_root_heading: false
      heading_level: 4

### Endgame Optimization

Configuration: [ccbt.toml:102-103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Tuning:**
- **Fast connections**: Lower threshold (0.85-0.9)
- **Slow connections**: Higher threshold (0.95-0.98)
- **Many peers**: Increase duplicates (3-5)
- **Few peers**: Decrease duplicates (1-2)

Endgame threshold: [ccbt.toml:103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Endgame duplicates: [ccbt.toml:102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Pipeline capacity: [ccbt.toml:109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Piece Priorities

Configuration: [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

First piece priority: [ccbt.toml:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Last piece priority: [ccbt.toml:113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

## Rate Limiting

### Global Limits

Configuration: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Global download limit: [ccbt.toml:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) (0 = unlimited)

Global upload limit: [ccbt.toml:141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) (0 = unlimited)

Network-level limits: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

::: ccbt.security.rate_limiter.RateLimiter
    options:
      show_root_heading: false
      heading_level: 4

### Per-Torrent Limits

Set limits via CLI using [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) with `--download-limit` and `--upload-limit` options.

Per-torrent configuration: [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Per-peer limits: [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Scheduler Settings

Scheduler time slice: [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

## Hash Verification

### Worker Threads

Configuration: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

**Tuning Guidelines:**
- **CPU cores**: Match or exceed core count
- **SSD storage**: Can handle more workers
- **HDD storage**: Limit workers (2-4)

Hash chunk size: [ccbt.toml:71](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Hash batch size: [ccbt.toml:72](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Hash queue size: [ccbt.toml:73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Hash verification workers: see `DiskIOManager` above.

## Memory Management

### Buffer Sizes

Write buffer: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Read ahead: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Cache Settings

Cache size: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

MMAP cache: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Disk queue size: [ccbt.toml:77](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Disk workers: [ccbt.toml:76](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

## System-Level Optimization

### File System Tuning

For system-level optimizations, refer to your operating system's documentation. These are general recommendations that apply outside of ccBitTorrent configuration.

### Network Stack Tuning

For network stack optimizations, refer to your operating system's documentation. These are system-level settings that affect overall network performance.

## Monitoring Performance

### Key Metrics

Monitor these key metrics via Prometheus:

- **Download Speed**: `ccbt_download_rate_bytes_per_second` - See [ccbt/utils/metrics.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py)
- **Upload Speed**: `ccbt_upload_rate_bytes_per_second` - See [ccbt/utils/metrics.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py)
- **Connected Peers**: Available via MetricsCollector
- **Disk Queue Depth**: Available via MetricsCollector - See [ccbt/monitoring/metrics_collector.py]
- **Hash Queue Depth**: Available via MetricsCollector

Prometheus metrics endpoint: [ccbt/utils/metrics.py:179](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py)

### Performance Profiling

Enable metrics: [ccbt.toml:164](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Metrics port: [ccbt.toml:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Access metrics at `http://localhost:9090/metrics` when enabled.

View metrics via CLI: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

## Troubleshooting Performance Issues

### Low Download Speeds

1. **Check peer connections**:
   Launch Bitonic dashboard: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

2. **Verify piece selection**:
   Configure in [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
   
   Implementation: [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)

3. **Increase pipeline depth**:
   Configure in [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
   
   Implementation: [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)

4. **Check rate limits**:
   Configuration: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
   
   CLI status command: [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py)

### High CPU Usage

1. **Reduce hash workers**:
   Configure in [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

2. **Disable memory mapping**:
   Configure in [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

3. **Increase refresh intervals**:
   Bitonic refresh interval: [ccbt/interface/terminal_dashboard.py:303](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)
   
   Dashboard config: [ccbt.toml:189](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Disk I/O Bottlenecks

1. **Enable write batching**:
   Configure write batch size: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
   
   Implementation: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)

2. **Use faster storage**:
   - Move downloads to SSD
   - Use RAID 0 for performance

3. **Optimize file system**:
   - Use appropriate file system
   - Tune mount options

## Benchmarking

Benchmark scripts are in `tests/performance/` (`bench_hash_verify.py`, `bench_disk_io.py`, `bench_piece_assembly.py`, `bench_loopback_throughput.py`, `bench_encryption.py`) and use `tests/performance/example-config-performance.toml` for shared tuning.

Pre-commit no longer runs benchmarks. All benchmark execution and regression checks now run in CI via `.github/workflows/benchmark.yml` so developer workflow stays fast while still enforcing performance guardrails.

Latest generated comparison output and trend charts are published in [Benchmarks](reports/benchmarks/index.md), with CI-managed snapshots committed under `docs/en/reports/benchmarks/generated/`.

### Test and Coverage Artifacts

When running the full test suite (pre-push/CI), artifacts are emitted to:

- `tests/.reports/junit.xml` (JUnit report)
- `tests/.reports/pytest.log` (test logs)
- `coverage.xml` and `htmlcov/` (coverage reports)

These integrate with Codecov; flags in `dev/.codecov.yml` are aligned to `ccbt/` subpackages to attribute coverage accurately (e.g., `peer`, `piece`, `protocols`, `extensions`). The coverage HTML report is automatically integrated into the documentation via the `mkdocs-coverage` plugin, which reads from `site/reports/htmlcov/` and renders it in [reports/coverage.md](reports/coverage.md).

### Benchmark Documentation Artifacts

The current benchmarking workflow is documented in [Benchmark index](reports/benchmarks/index.md). CI now writes:

- `docs/en/reports/benchmarks/generated/comparison_latest.md` for the most recent comparison table
- `docs/en/reports/benchmarks/generated/trend_charts.md` for trend graphs
- `docs/en/reports/benchmarks/generated/benchmark_history.json` for bounded trend history used by docs rendering

These files are committed by CI so they are available in Read the Docs and repository snapshots.

## Best Practices

1. **Start with defaults**: Begin with default settings from [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
2. **Measure baseline**: Establish performance baseline using [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)
3. **Change one setting**: Modify one setting at a time in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
4. **Test thoroughly**: Verify improvements
5. **Monitor resources**: Watch CPU, memory, disk usage via [Bitonic](bitonic.md)
6. **Document changes**: Keep track of effective settings

## Configuration Templates

### High-Performance Setup

Reference high-performance configuration template: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Key settings:
- Network: [ccbt.toml:11-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Disk: [ccbt.toml:57-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Strategy: [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Example: [example-config-performance.toml](examples/example-config-performance.toml)

### Low-Resource Setup

Reference low-resource configuration template: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Key settings:
- Network: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) - Reduce peer limits
- Disk: [ccbt.toml:59-65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) - Use sparse preallocation, disable MMAP
- Strategy: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) - Rarest-first remains optimal

For more detailed configuration options, see the [Configuration](configuration.md) documentation.
