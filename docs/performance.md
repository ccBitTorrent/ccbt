# Performance Tuning Guide

This guide covers performance optimization techniques for ccBitTorrent to achieve maximum download speeds and efficient resource usage.

## Network Optimization

### Connection Settings

#### Pipeline Depth
Controls the number of outstanding requests per peer:

```toml
[network]
pipeline_depth = 32  # Default: 16, Range: 8-64
```

**Recommendations:**
- **High-latency connections**: 32-64 (satellite, mobile)
- **Low-latency connections**: 16-32 (fiber, cable)
- **Local networks**: 8-16 (LAN transfers)

#### Block Size
Size of data blocks requested from peers:

```toml
[network]
block_size_kib = 32  # Default: 16, Range: 4-64
```

**Recommendations:**
- **High-bandwidth**: 32-64 KiB (fiber, cable)
- **Medium-bandwidth**: 16-32 KiB (DSL, mobile)
- **Low-bandwidth**: 4-16 KiB (dial-up, slow mobile)

#### Socket Buffers
Increase for high-throughput scenarios:

```toml
[network]
socket_rcvbuf_kib = 1024  # Default: 256
socket_sndbuf_kib = 1024  # Default: 256
```

### Connection Limits

#### Global Peer Limits
```toml
[network]
max_global_peers = 200      # Default: 100
max_peers_per_torrent = 50  # Default: 25
```

**Tuning Guidelines:**
- **High-bandwidth**: Increase global peers (200-500)
- **Low-bandwidth**: Reduce global peers (50-100)
- **Many torrents**: Reduce per-torrent limit (10-25)
- **Few torrents**: Increase per-torrent limit (50-100)

#### Connection Timeouts
```toml
[network]
connection_timeout = 30.0    # Default: 15.0
peer_timeout = 120.0         # Default: 60.0
```

## Disk I/O Optimization

### Preallocation Strategy
```toml
[disk]
preallocate = "full"  # Options: none, sparse, full
```

**Recommendations:**
- **SSDs**: Use "full" for better performance
- **HDDs**: Use "sparse" to save space
- **Network storage**: Use "none" to avoid delays

### Write Optimization
```toml
[disk]
write_batch_kib = 128    # Default: 64
write_buffer_kib = 1024  # Default: 512
sync_writes = false      # Default: false
```

**Tuning Guidelines:**
- **Fast storage**: Increase batch size (128-256 KiB)
- **Slow storage**: Decrease batch size (32-64 KiB)
- **Critical data**: Enable sync_writes
- **Performance**: Disable sync_writes

### Memory Mapping
```toml
[disk]
use_mmap = true        # Default: false
mmap_cache_mb = 256    # Default: 128
```

**Benefits:**
- Faster reads for completed pieces
- Reduced memory usage
- Better OS caching

**Considerations:**
- Requires sufficient RAM
- May cause memory pressure
- Best for read-heavy workloads

### Advanced I/O Features

#### io_uring (Linux)
```toml
[disk]
enable_io_uring = true  # Default: false
```

**Requirements:**
- Linux kernel 5.1+
- Modern storage devices
- Sufficient system resources

#### Direct I/O
```toml
[disk]
direct_io = true  # Default: false
```

**Use Cases:**
- High-performance storage
- Bypass OS page cache
- Consistent performance

## Strategy Selection

### Piece Selection Algorithms

#### Rarest-First (Recommended)
```toml
[strategy]
piece_selection = "rarest_first"
```

**Benefits:**
- Optimal swarm health
- Faster completion times
- Better peer cooperation

#### Sequential
```toml
[strategy]
piece_selection = "sequential"
```

**Use Cases:**
- Streaming media files
- Sequential access patterns
- Priority-based downloads

#### Round-Robin
```toml
[strategy]
piece_selection = "round_robin"
```

**Use Cases:**
- Simple scenarios
- Debugging
- Legacy compatibility

### Endgame Optimization
```toml
[strategy]
endgame_threshold = 0.95    # Default: 0.9
endgame_duplicates = 3      # Default: 2
```

**Tuning:**
- **Fast connections**: Lower threshold (0.85-0.9)
- **Slow connections**: Higher threshold (0.95-0.98)
- **Many peers**: Increase duplicates (3-5)
- **Few peers**: Decrease duplicates (1-2)

## Rate Limiting

### Global Limits
```toml
[limits]
global_down_kib = 0  # 0 = unlimited
global_up_kib = 0    # 0 = unlimited
```

### Per-Torrent Limits
```bash
# Set limits via CLI
uv run ccbt download torrent.torrent --download-limit 1024 --upload-limit 512

# Or via configuration
[torrents.torrent_name]
download_limit_kib = 1024
upload_limit_kib = 512
```

### Adaptive Rate Limiting
```toml
[limits]
adaptive_limits = true
min_upload_ratio = 0.1
max_upload_ratio = 0.5
```

## Hash Verification

### Worker Threads
```toml
[disk]
hash_workers = 8  # Default: 4
```

**Tuning Guidelines:**
- **CPU cores**: Match or exceed core count
- **SSD storage**: Can handle more workers
- **HDD storage**: Limit workers (2-4)

### Verification Strategy
```toml
[disk]
verify_on_completion = true
verify_interval = 3600  # seconds
```

## Memory Management

### Buffer Sizes
```toml
[disk]
read_buffer_kib = 1024
write_buffer_kib = 1024
```

### Cache Settings
```toml
[disk]
piece_cache_mb = 512
metadata_cache_mb = 64
```

## System-Level Optimization

### File System Tuning

#### ext4 (Linux)
```bash
# Mount with performance options
mount -o noatime,nodiratime /dev/sda1 /downloads
```

#### NTFS (Windows)
```bash
# Disable last access time
fsutil behavior set disablelastaccess 1
```

### Network Stack Tuning

#### Linux
```bash
# Increase network buffers
echo 'net.core.rmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' >> /etc/sysctl.conf
sysctl -p
```

#### Windows
```powershell
# Increase TCP window size
netsh int tcp set global autotuninglevel=normal
```

## Monitoring Performance

### Key Metrics
- **Download Speed**: `ccbt_download_rate_bytes_per_second`
- **Upload Speed**: `ccbt_upload_rate_bytes_per_second`
- **Connected Peers**: `ccbt_connected_peers`
- **Disk Queue Depth**: `ccbt_disk_queue_depth`
- **Hash Queue Depth**: `ccbt_hash_queue_depth`

### Performance Profiling
```bash
# Enable detailed metrics
uv run ccbt download torrent.torrent --enable-metrics --metrics-port 9090

# View metrics
curl http://localhost:9090/metrics
```

## Troubleshooting Performance Issues

### Low Download Speeds

1. **Check peer connections**:
   ```bash
   uv run ccbt dashboard
   ```

2. **Verify piece selection**:
   ```toml
   [strategy]
   piece_selection = "rarest_first"
   ```

3. **Increase pipeline depth**:
   ```toml
   [network]
   pipeline_depth = 32
   ```

4. **Check rate limits**:
   ```bash
   uv run ccbt status
   ```

### High CPU Usage

1. **Reduce hash workers**:
   ```toml
   [disk]
   hash_workers = 2
   ```

2. **Disable memory mapping**:
   ```toml
   [disk]
   use_mmap = false
   ```

3. **Increase refresh intervals**:
   ```bash
   uv run ccbt dashboard --refresh 5.0
   ```

### Disk I/O Bottlenecks

1. **Enable write batching**:
   ```toml
   [disk]
   write_batch_kib = 128
   ```

2. **Use faster storage**:
   - Move downloads to SSD
   - Use RAID 0 for performance

3. **Optimize file system**:
   - Use appropriate file system
   - Tune mount options

## Benchmarking

### Test Different Configurations
```bash
# Test with different pipeline depths
for depth in 8 16 32 64; do
    echo "Testing pipeline_depth = $depth"
    uv run ccbt download test.torrent --pipeline-depth $depth
done
```

### Measure Performance
```bash
# Run performance benchmarks
python benchmarks/bench_throughput.py
python benchmarks/bench_disk.py
```

### Test and Coverage Artifacts

When running the full test suite (pre-push/CI), artifacts are emitted to:

- `tests/.reports/junit.xml` (JUnit report)
- `tests/.reports/pytest.log` (test logs)
- `coverage.xml` and `htmlcov/` (coverage reports)

These integrate with Codecov; flags in `.codecov.yml` are aligned to `ccbt/` subpackages to attribute coverage accurately (e.g., `peer`, `piece`, `protocols`, `extensions`).

## Best Practices

1. **Start with defaults**: Begin with default settings
2. **Measure baseline**: Establish performance baseline
3. **Change one setting**: Modify one setting at a time
4. **Test thoroughly**: Verify improvements
5. **Monitor resources**: Watch CPU, memory, disk usage
6. **Document changes**: Keep track of effective settings

## Configuration Templates

### High-Performance Setup
```toml
[network]
pipeline_depth = 32
block_size_kib = 32
max_global_peers = 300
socket_rcvbuf_kib = 1024
socket_sndbuf_kib = 1024

[disk]
preallocate = "full"
write_batch_kib = 128
use_mmap = true
hash_workers = 8
enable_io_uring = true

[strategy]
piece_selection = "rarest_first"
endgame_duplicates = 3
```

### Low-Resource Setup
```toml
[network]
pipeline_depth = 16
block_size_kib = 16
max_global_peers = 50

[disk]
preallocate = "sparse"
write_batch_kib = 64
use_mmap = false
hash_workers = 2

[strategy]
piece_selection = "rarest_first"
endgame_duplicates = 2
```

For more detailed configuration options, see the [Configuration](configuration.md) documentation.
