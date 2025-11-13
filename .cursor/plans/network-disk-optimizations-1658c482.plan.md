<!-- 1658c482-f56b-4850-b6dc-01bd5a8ed431 438e5472-4f98-4fc1-959b-5520eed26462 -->
# Network and Disk I/O Optimization Implementation Plan

## Analysis Summary

### Network Bottlenecks Identified

1. **Connection Management**: No effective reuse of peer connections; frequent connection establishment overhead
2. **HTTP Session Management**: aiohttp session not optimally configured for tracker requests
3. **Request Pipelining**: Limited pipeline depth (16) may not fully utilize high-bandwidth connections
4. **Socket Buffer Sizes**: Fixed sizes (256KB) may be suboptimal for modern high-speed networks
5. **DNS Resolution**: No DNS caching, causing repeated lookups for same trackers
6. **Write Buffer Management**: Ring buffer usage could be optimized
7. **Connection Pooling**: Connection pools exist but not fully utilized in async peer connections

### Disk I/O Bottlenecks Identified

1. **Write Batching**: 5ms timeout threshold too short; may flush prematurely on fast storage
2. **MMap Cache**: 128MB default may be too small for large torrents; eviction strategy too aggressive
3. **Checkpoint Frequency**: Saving on every piece completion creates I/O overhead
4. **Read-Ahead**: 64KB read-ahead may be insufficient for sequential reads
5. **I/O Queue Depth**: Default 200 may bottleneck on NVMe drives
6. **Hash Verification**: Parallel hash workers (4) may be insufficient for fast SSDs
7. **Direct I/O**: Not enabled by default; could improve performance on high-speed storage

## Implementation Tasks

### Phase 1: Network Optimizations

#### Task 1.1: Enhance Connection Pooling and Reuse

**File**: `ccbt/peer/connection_pool.py`, `ccbt/peer/async_peer_connection.py`

- **Sub-Task 1.1.1**: Improve connection validation and health checks
  - **Location**: `ccbt/peer/connection_pool.py:140-146`
  - **Change**: Add connection liveness check using socket getsockopt(SO_ERROR)
  - **Implementation**: 
    ```python
    def _is_connection_valid(self, connection: Any) -> bool:
        # Check socket state via getsockopt(SO_ERROR)
        # Check if reader/writer are still valid
        # Verify connection hasn't exceeded max idle time
    ```

- **Sub-Task 1.1.2**: Implement connection warmup strategy
  - **Location**: `ccbt/peer/connection_pool.py:234-256`
  - **Change**: Pre-establish connections to frequently accessed peers
  - **Implementation**: Add `warmup_connections()` method that creates connections for top N peers

- **Sub-Task 1.1.3**: Add connection reuse metrics
  - **Location**: `ccbt/peer/connection_pool.py:207-232`
  - **Change**: Track reuse rate, average connection lifetime
  - **Implementation**: Extend `get_pool_stats()` with reuse statistics

- **Sub-Task 1.1.4**: Integrate connection pool with AsyncPeerConnectionManager
  - **Location**: `ccbt/peer/async_peer_connection.py:387-451`
  - **Change**: Use PeerConnectionPool in `_connect_to_peer()` before creating new connection
  - **Implementation**: Check pool first, only create new connection if pool miss

#### Task 1.2: Optimize HTTP Session Configuration for Trackers

**File**: `ccbt/discovery/tracker.py:81-98`

- **Sub-Task 1.2.1**: Configure connection limits and keepalive
  - **Location**: `ccbt/discovery/tracker.py:81-98`
  - **Change**: Set connector limits and enable connection pooling
  - **Implementation**:
    ```python
    connector = aiohttp.TCPConnector(
        limit=self.config.network.tracker_connection_limit,
        limit_per_host=self.config.network.tracker_connections_per_host,
        ttl_dns_cache=self.config.network.dns_cache_ttl,
        keepalive_timeout=300,
        enable_cleanup_closed=True
    )
    ```

- **Sub-Task 1.2.2**: Implement DNS caching with TTL support
  - **Location**: `ccbt/discovery/tracker.py:100-123` (new method)
  - **Change**: Add DNS cache with TTL-based expiration
  - **Implementation**: Create `DNSCache` class with asyncio-based caching

- **Sub-Task 1.2.3**: Add HTTP session metrics
  - **Location**: `ccbt/discovery/tracker.py:499-518` (extend existing method)
  - **Change**: Track request/response times, connection reuse
  - **Implementation**: Add metrics collection to `_make_request_async()`

#### Task 1.3: Enhance Socket Buffer Management

**File**: `ccbt/utils/network_optimizer.py:66-189`

- **Sub-Task 1.3.1**: Implement adaptive buffer sizing
  - **Location**: `ccbt/utils/network_optimizer.py:71-113`
  - **Change**: Dynamically adjust buffer sizes based on network conditions
  - **Implementation**: Add `_calculate_optimal_buffer_size()` method using BDP (Bandwidth-Delay Product)

- **Sub-Task 1.3.2**: Add platform-specific buffer optimizations
  - **Location**: `ccbt/utils/network_optimizer.py:116-189`
  - **Change**: Use platform-specific maximum buffer sizes
  - **Implementation**: Query system limits and set buffers accordingly (Linux: /proc/sys/net/core/rmem_max)

- **Sub-Task 1.3.3**: Enable TCP window scaling
  - **Location**: `ccbt/utils/network_optimizer.py:116-189`
  - **Change**: Enable TCP window scaling for high-speed connections
  - **Implementation**: Check and enable TCP window scaling option

#### Task 1.4: Optimize Request Pipelining

**File**: `ccbt/peer/async_peer_connection.py:145-198`

- **Sub-Task 1.4.1**: Implement adaptive pipeline depth
  - **Location**: `ccbt/peer/async_peer_connection.py:149`
  - **Change**: Dynamically adjust `max_pipeline_depth` based on connection latency and bandwidth
  - **Implementation**: Add `_calculate_pipeline_depth()` method using latency measurements

- **Sub-Task 1.4.2**: Add request prioritization
  - **Location**: `ccbt/peer/async_peer_connection.py:148` (request_queue)
  - **Change**: Use priority queue instead of deque for request ordering
  - **Implementation**: Replace `deque` with `heapq`-based priority queue, prioritize rarest pieces

- **Sub-Task 1.4.3**: Implement request coalescing
  - **Location**: `ccbt/peer/async_peer_connection.py:1454-1488`
  - **Change**: Combine adjacent requests into single larger requests when possible
  - **Implementation**: Add `_coalesce_requests()` method before sending

#### Task 1.5: Improve Timeout and Retry Logic

**File**: `ccbt/discovery/tracker.py:510-518`, `ccbt/peer/async_peer_connection.py:487-490`

- **Sub-Task 1.5.1**: Implement exponential backoff with jitter
  - **Location**: `ccbt/discovery/tracker.py:510-518`
  - **Change**: Replace fixed backoff with exponential backoff + jitter
  - **Implementation**: 
    ```python
    backoff_delay = min(base_delay * (2 ** failure_count) + random.uniform(0, base_delay), max_delay)
    ```

- **Sub-Task 1.5.2**: Add adaptive timeout calculation
  - **Location**: `ccbt/peer/async_peer_connection.py:487-490`
  - **Change**: Calculate timeout based on measured RTT
  - **Implementation**: Use RTT * 3 for timeout calculation, with min/max bounds

- **Sub-Task 1.5.3**: Implement circuit breaker pattern
  - **Location**: `ccbt/utils/resilience.py` (new class)
  - **Change**: Add CircuitBreaker for peer connections that repeatedly fail
  - **Implementation**: Create `CircuitBreaker` class with open/half-open/closed states

### Phase 2: Disk I/O Optimizations

#### Task 2.1: Optimize Write Batching Strategy

**File**: `ccbt/storage/disk_io.py:628-691`

- **Sub-Task 2.1.1**: Implement adaptive batching timeout
  - **Location**: `ccbt/storage/disk_io.py:654`
  - **Change**: Adjust timeout based on storage device performance characteristics
  - **Implementation**: Detect storage type (SSD/NVMe/HDD) and set timeout accordingly (NVMe: 0.1ms, SSD: 5ms, HDD: 50ms)

- **Sub-Task 2.1.2**: Improve contiguous write detection
  - **Location**: `ccbt/storage/disk_io.py:785-792`
  - **Change**: More aggressive coalescing of near-contiguous writes
  - **Implementation**: Extend `_combine_contiguous_writes()` to merge writes within threshold distance (e.g., 4KB)

- **Sub-Task 2.1.3**: Add write-back caching awareness
  - **Location**: `ccbt/storage/disk_io.py:794-898`
  - **Change**: Detect if write-back cache is enabled and adjust flush strategy
  - **Implementation**: Query OS for cache mode and optimize flush frequency

- **Sub-Task 2.1.4**: Implement write queue prioritization
  - **Location**: `ccbt/storage/disk_io.py:125`
  - **Change**: Use priority queue for critical writes (checkpoints, metadata)
  - **Implementation**: Replace `asyncio.Queue` with priority queue, prioritize by write type

#### Task 2.2: Enhance MMap Cache Management

**File**: `ccbt/storage/disk_io.py:129-131, 900-985`

- **Sub-Task 2.2.1**: Implement LRU eviction with size awareness
  - **Location**: `ccbt/storage/disk_io.py:912-940`
  - **Change**: Replace simple LRU with size-aware eviction (evict large files first if needed)
  - **Implementation**: Modify `_cache_cleaner()` to prefer evicting large, less-frequently-accessed files

- **Sub-Task 2.2.2**: Add cache warmup on torrent start
  - **Location**: `ccbt/storage/disk_io.py:950-985` (new method)
  - **Change**: Pre-load frequently accessed files into mmap cache
  - **Implementation**: Add `warmup_cache()` method that loads files in background

- **Sub-Task 2.2.3**: Implement cache hit rate monitoring
  - **Location**: `ccbt/storage/disk_io.py:605-613`
  - **Change**: Track detailed cache statistics (hit rate, eviction rate, average access time)
  - **Implementation**: Extend `get_cache_stats()` with comprehensive metrics

- **Sub-Task 2.2.4**: Add adaptive cache size adjustment
  - **Location**: `ccbt/storage/disk_io.py:130-132`
  - **Change**: Dynamically adjust cache size based on available memory
  - **Implementation**: Monitor system memory and adjust cache_size_bytes accordingly

#### Task 2.3: Optimize Checkpoint I/O Operations

**File**: `ccbt/storage/checkpoint.py:108-213`

- **Sub-Task 2.3.1**: Implement incremental checkpoint saves
  - **Location**: `ccbt/storage/checkpoint.py:108-152`
  - **Change**: Only save changed pieces, not full checkpoint every time
  - **Implementation**: Add diff calculation between current and last checkpoint state

- **Sub-Task 2.3.2**: Optimize checkpoint compression
  - **Location**: `ccbt/storage/checkpoint.py:274-310`
  - **Change**: Use faster compression algorithm or compress in background thread
  - **Implementation**: Use zstd instead of gzip for faster compression, or compress asynchronously

- **Sub-Task 2.3.3**: Batch checkpoint writes
  - **Location**: `ccbt/storage/checkpoint.py:204-213`
  - **Change**: Batch multiple checkpoint updates into single write
  - **Implementation**: Queue checkpoint saves and flush periodically (e.g., every 10 pieces or 5 seconds)

- **Sub-Task 2.3.4**: Add checkpoint write deduplication
  - **Location**: `ccbt/storage/checkpoint.py:154-213`
  - **Change**: Skip checkpoint save if no meaningful changes since last save
  - **Implementation**: Compare current state hash with last saved state hash

#### Task 2.4: Enhance Read Operations

**File**: `ccbt/storage/disk_io.py:534-604`

- **Sub-Task 2.4.1**: Implement intelligent read-ahead
  - **Location**: `ccbt/storage/disk_io.py:534-565`
  - **Change**: Adaptive read-ahead size based on access pattern (sequential vs random)
  - **Implementation**: Detect sequential access and increase read-ahead dynamically (up to 1MB for sequential)

- **Sub-Task 2.4.2**: Add read prefetching for likely-next blocks
  - **Location**: `ccbt/storage/disk_io.py:534-565` (new method)
  - **Change**: Prefetch blocks that are likely to be requested next
  - **Implementation**: Track access patterns and prefetch predicted blocks in background

- **Sub-Task 2.4.3**: Optimize multi-file torrent reads
  - **Location**: `ccbt/storage/file_assembler.py:547-589`
  - **Change**: Parallelize reads across multiple file segments
  - **Implementation**: Use `asyncio.gather()` to read multiple segments concurrently

- **Sub-Task 2.4.4**: Add read buffer pooling
  - **Location**: `ccbt/storage/disk_io.py:534-565`
  - **Change**: Reuse read buffers to reduce allocations
  - **Implementation**: Add buffer pool for read operations, similar to write staging buffers

#### Task 2.5: Optimize I/O Queue and Worker Configuration

**File**: `ccbt/storage/disk_io.py:99-122, 718-898`

- **Sub-Task 2.5.1**: Implement adaptive worker count
  - **Location**: `ccbt/storage/disk_io.py:119-122`
  - **Change**: Dynamically adjust worker count based on I/O queue depth and system load
  - **Implementation**: Monitor queue depth and spawn/remove workers as needed

- **Sub-Task 2.5.2**: Add I/O priority management
  - **Location**: `ccbt/storage/disk_io.py:772-898`
  - **Change**: Set I/O priority for disk operations (Linux: ioprio_set)
  - **Implementation**: Set real-time I/O class for critical operations on Linux

- **Sub-Task 2.5.3**: Implement I/O scheduling optimization
  - **Location**: `ccbt/storage/disk_io.py:728-771`
  - **Change**: Sort writes by LBA (Logical Block Address) for optimal disk access
  - **Implementation**: Add LBA calculation and sort writes by physical location before flushing

- **Sub-Task 2.5.4**: Add NVMe-specific optimizations
  - **Location**: `ccbt/storage/disk_io.py:213-236`
  - **Change**: Detect NVMe and enable optimal settings (larger queue depth, multiple queues)
  - **Implementation**: Extend `_detect_platform_capabilities()` to detect NVMe and configure accordingly

#### Task 2.6: Enhance Hash Verification Performance

**File**: `ccbt/models.py:736-758` (config), hash verification locations

- **Sub-Task 2.6.1**: Implement parallel hash verification with work-stealing
  - **Location**: Hash verification code (to be located)
  - **Change**: Use thread pool with work-stealing for better load balancing
  - **Implementation**: Replace fixed worker pool with dynamic work-stealing queue

- **Sub-Task 2.6.2**: Add hash verification batching
  - **Location**: Hash verification code
  - **Change**: Batch multiple pieces for verification to reduce overhead
  - **Implementation**: Group pieces and verify in batches using vectorized operations where possible

- **Sub-Task 2.6.3**: Optimize hash chunk size
  - **Location**: `ccbt/models.py:748-752`
  - **Change**: Use larger chunks (1MB) for hash verification on fast storage
  - **Implementation**: Detect storage speed and adjust chunk size dynamically

### Phase 3: Configuration and Monitoring Enhancements

#### Task 3.1: Add Performance Monitoring

**File**: `ccbt/monitoring/metrics_collector.py` (existing), new metrics locations

- **Sub-Task 3.1.1**: Add network performance metrics
  - **Location**: Network components
  - **Change**: Track connection establishment time, RTT, throughput per connection
  - **Implementation**: Add metrics collection points in `AsyncPeerConnectionManager`

- **Sub-Task 3.1.2**: Add disk I/O performance metrics
  - **Location**: `ccbt/storage/disk_io.py:168-179`
  - **Change**: Track I/O latency percentiles, queue depth, cache efficiency
  - **Implementation**: Extend stats dictionary with detailed performance metrics

- **Sub-Task 3.1.3**: Implement performance alerts
  - **Location**: `ccbt/monitoring/alert_manager.py` (if exists)
  - **Change**: Alert on performance degradation (high latency, low throughput)
  - **Implementation**: Add thresholds and alert triggers for performance issues

#### Task 3.2: Auto-Tuning Configuration

**File**: `ccbt/config/config.py`, `ccbt/models.py`

- **Sub-Task 3.2.1**: Add automatic buffer size tuning
  - **Location**: Configuration initialization
  - **Change**: Detect system capabilities and set optimal buffer sizes
  - **Implementation**: Query system limits and set buffers to optimal values

- **Sub-Task 3.2.2**: Implement storage device detection and tuning
  - **Location**: `ccbt/storage/disk_io.py:210-236`
  - **Change**: Detect storage type and apply optimal settings automatically
  - **Implementation**: Extend detection to identify HDD/SSD/NVMe and configure accordingly

- **Sub-Task 3.2.3**: Add adaptive configuration based on system resources
  - **Location**: Configuration loading
  - **Change**: Adjust worker counts, queue sizes based on CPU cores, RAM, storage speed
  - **Implementation**: Query system resources and calculate optimal defaults

### Phase 4: Advanced Optimizations

#### Task 4.1: Implement Zero-Copy I/O Where Possible

**File**: `ccbt/storage/disk_io.py:794-898`

- **Sub-Task 4.1.1**: Use sendfile() for reading pieces to network
  - **Location**: Piece serving code
  - **Change**: Use OS-level zero-copy when sending data from disk to network
  - **Implementation**: Use `os.sendfile()` on Linux/FreeBSD, `TransmitFile()` on Windows

- **Sub-Task 4.1.2**: Optimize memoryview usage
  - **Location**: `ccbt/storage/file_assembler.py:458-493`
  - **Change**: Minimize copies by using memoryview consistently
  - **Implementation**: Ensure all data operations use memoryview where possible

#### Task 4.2: Implement io_uring Support (Linux)

**File**: `ccbt/storage/disk_io.py:814-817` (config), new io_uring module

- **Sub-Task 4.2.1**: Add io_uring backend
  - **Location**: New file `ccbt/storage/io_uring_backend.py`
  - **Change**: Implement async I/O using io_uring for Linux
  - **Implementation**: Create io_uring-based I/O backend with submission/completion queues

- **Sub-Task 4.2.2**: Integrate io_uring with DiskIOManager
  - **Location**: `ccbt/storage/disk_io.py:794-898`
  - **Change**: Use io_uring when available and enabled
  - **Implementation**: Add fallback mechanism to thread pool if io_uring unavailable

#### Task 4.3: Optimize Ring Buffer Usage

**File**: `ccbt/storage/disk_io.py:133-145, 731-770`

- **Sub-Task 4.3.1**: Improve ring buffer staging efficiency
  - **Location**: `ccbt/storage/disk_io.py:731-770`
  - **Change**: Better integration of ring buffer with write batching
  - **Implementation**: Ensure ring buffer data is properly staged before flush

- **Sub-Task 4.3.2**: Add ring buffer size tuning
  - **Location**: `ccbt/storage/disk_io.py:134-145`
  - **Change**: Dynamically size ring buffer based on write patterns
  - **Implementation**: Monitor write sizes and adjust ring buffer accordingly

## Implementation Order and Dependencies

1. **Phase 1, Task 1.1-1.2** (Connection pooling, HTTP sessions) - Foundation for network optimizations
2. **Phase 2, Task 2.1-2.2** (Write batching, MMap cache) - High-impact disk optimizations
3. **Phase 1, Task 1.3-1.4** (Socket buffers, pipelining) - Performance improvements
4. **Phase 2, Task 2.3-2.4** (Checkpoints, reads) - Additional disk optimizations
5. **Phase 3** (Monitoring, auto-tuning) - Validation and fine-tuning
6. **Phase 4** (Advanced) - Cutting-edge optimizations

## Testing Strategy

- Performance benchmarks for each optimization
- Integration tests with real torrents
- Resource usage monitoring (CPU, memory, I/O)
- Regression testing to ensure no functionality loss

## Estimated Impact

- **Network**: 20-40% improvement in connection establishment, 15-30% throughput increase
- **Disk I/O**: 30-50% improvement in write throughput, 20-35% reduction in read latency
- **Overall**: 25-40% improvement in download speeds on fast connections