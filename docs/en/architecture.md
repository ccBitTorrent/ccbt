# Architecture Overview

This document provides a technical overview of ccBitTorrent's architecture, components, and data flow.

## Entry Points

ccBitTorrent provides multiple entry points for different use cases:

1. **Basic CLI (`ccbt`)**: Simple command-line interface for single torrent downloads
   - Entry point: `ccbt/__main__.py:main`
   - Usage: `python -m ccbt torrent.torrent` or `python -m ccbt "magnet:..."`

2. **Async CLI (`ccbt async`)**: High-performance async interface with full session management
   - Entry point: `ccbt/session/async_main.py:main`
   - Supports daemon mode, multiple torrents, and advanced features

3. **Enhanced CLI (`btbt`)**: Rich command-line interface with comprehensive features
   - Entry point: `ccbt/cli/main.py:main`
   - Provides interactive commands, monitoring, and advanced configuration

4. **Terminal Dashboard (`bitonic`)**: Live, interactive terminal dashboard (TUI)
   - Entry point: `ccbt/interface/terminal_dashboard.py:main`
   - Real-time visualization of torrents, peers, and system metrics

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ccBitTorrent Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  CLI Interface                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Basic     │ │ Interactive │ │  Dashboard   │              │
│  │   Commands  │ │     CLI     │ │   (TUI)     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Session Management                                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AsyncSessionManager                           │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Config    │ │   Events    │ │  Checkpoint │          │ │
│  │  │  Manager    │ │   System    │ │   Manager   │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Core Components                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    Peer     │ │    Piece    │ │    Disk     │              │
│  │  Connection │ │   Manager   │ │     I/O     │              │
│  │  Manager    │ │             │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Tracker   │ │     DHT     │ │  Metadata   │              │
│  │   Client    │ │   Manager   │ │  Exchange   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Network Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    TCP      │ │     UDP     │ │   WebRTC    │              │
│  │ Connections │ │  Trackers   │ │ (WebTorrent)│              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Monitoring & Observability                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Metrics   │ │   Alerts    │ │   Tracing   │              │
│  │  Collector  │ │   Manager   │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Services Architecture

ccBitTorrent uses a service-oriented architecture with several core services:

- **PeerService**: Manages peer connections and communication
  - Implementation: `ccbt/services/peer_service.py`
  - Tracks peer connections, bandwidth, and piece statistics
  
- **StorageService**: Manages file system operations with high-performance chunked writes
  - Implementation: `ccbt/services/storage_service.py`
  - Handles file creation, data read/write operations
  
- **TrackerService**: Manages tracker communication and health monitoring
  - Implementation: `ccbt/services/tracker_service.py`
  - Supports HTTP and UDP trackers with scrape support (BEP 48)

All services inherit from the base `Service` class which provides lifecycle management, health checks, and state tracking.

**Implementation:** `ccbt/services/base.py`

### AsyncSessionManager

The central orchestrator that manages the entire BitTorrent session. There are two implementations:

1. **AsyncSessionManager in `ccbt/session/async_main.py`**: Used by the async CLI entry point, manages multiple torrents with protocol support.

The `AsyncSessionManager` class is defined in `ccbt/session/async_main.py` starting at line 319. Key initialization attributes include:

- `config`: Configuration instance (uses global config if not provided)
- `torrents`: Dictionary mapping torrent IDs to `AsyncDownloadManager` instances
- `metrics`: `MetricsCollector` instance (initialized in `start()` if enabled)
- `disk_io_manager`: Disk I/O manager (initialized in `start()`)
- `security_manager`: Security manager (initialized in `start()`)
- `protocol_manager`: `ProtocolManager` for managing multiple protocols
- `protocols`: List of active protocol instances

See the full implementation:

```python
--8<-- "ccbt/session/async_main.py:319:374"
```

2. **AsyncSessionManager in `ccbt/session/session.py`**: More comprehensive implementation with DHT, queue management, NAT traversal, and scrape support.

The more comprehensive `AsyncSessionManager` in `ccbt/session/session.py` (starting at line 2278) includes additional components:

- `dht_client`: DHT client for peer discovery
- `peer_service`: `PeerService` instance for managing peer connections
- `queue_manager`: Torrent queue manager for prioritization
- `nat_manager`: NAT traversal manager for port mapping
- `private_torrents`: Set tracking private torrents (BEP 27)
- `scrape_cache`: Cache for tracker scrape results (BEP 48)
- `_task_supervisor`: `TaskSupervisor` for managing background task lifecycles
- `torrent_addition_handler`: `TorrentAdditionHandler` for torrent addition workflow
- `background_tasks`: `ManagerBackgroundTasks` for cleanup and metrics loops
- `scrape_manager`: `ScrapeManager` for tracker scraping operations

**Responsibilities:**
- Torrent lifecycle management (delegated to `TorrentAdditionHandler`)
- Peer connection coordination via `PeerService`
- Protocol management (`BitTorrentProtocol`, `IPFSProtocol`)
- Resource allocation and limits
- Event dispatching through `EventBus`
- Checkpoint management (delegated to `CheckpointOperations`)
- DHT client management
- Queue management for torrent prioritization
- NAT traversal via `NATManager`
- Tracker scraping (delegated to `ScrapeManager`)
- Background task supervision via `TaskSupervisor`

### AsyncTorrentSession

Represents one active torrent's lifecycle with async operations. The session uses a controller-based architecture with dependency injection via `SessionContext`.

**Key Components:**
- `_task_supervisor`: `TaskSupervisor` for managing background task lifecycles
- `ctx`: `SessionContext` - Dependency injection container for session components
- `lifecycle_controller`: `LifecycleController` - Manages start/pause/resume/stop sequencing
- `status_aggregator`: `StatusAggregator` - Collects and aggregates torrent status
- `checkpoint_controller`: `CheckpointController` - Handles checkpoint save/load with batching
- `checkpoint_manager`: `CheckpointManager` - Manages checkpoint persistence
- `piece_manager`: `AsyncPieceManager` - Manages piece downloading and verification
- `peer_manager`: `AsyncPeerManager` - Manages peer connections
- `download_manager`: `AsyncDownloadManager` - Manages download operations
- `file_selection_manager`: `FileSelectionManager` - Manages file selection for partial downloads

**SessionContext Pattern:**

The `SessionContext` provides dependency injection for session components, allowing controllers to access shared state without tight coupling:

```python
class SessionContext:
    """Dependency injection container for session components."""
    config: Any
    torrent_data: dict[str, Any] | TorrentInfoModel
    output_dir: Path
    info: TorrentInfo
    session_manager: AsyncSessionManager | None
    logger: logging.Logger
    piece_manager: PieceManagerProtocol | None
    peer_manager: PeerManagerProtocol | None
    tracker: AsyncTrackerClient | None
    dht_client: AsyncDHTClient | None
    checkpoint_manager: CheckpointManager | None
    download_manager: AsyncDownloadManager | None
    file_selection_manager: FileSelectionManager | None
```

Controllers receive the `SessionContext` in their constructors, providing access to all necessary dependencies without direct references to the session object.

#### Session Orchestration

The session management follows a delegation pattern where `AsyncSessionManager` orchestrates operations and delegates to specialized controllers. This modular architecture improves maintainability, testability, and separation of concerns.

**Core Infrastructure** (under `ccbt/session/`):
- `models.py`: `SessionContext` - Dependency injection container for session components
- `tasks.py`: `TaskSupervisor` - Manages lifecycle of background asyncio tasks with cancellation and error handling

**Session-Level Controllers** (per `AsyncTorrentSession`):
- `lifecycle.py`: `LifecycleController` - Manages start/pause/resume/stop sequencing
- `checkpointing.py`: `CheckpointController` - Checkpoint save/load operations with batching and fast resume support
- `status_aggregation.py`: `StatusAggregator` - Collects and aggregates torrent status from multiple sources
- `announce.py`: `AnnounceLoop` - Tracker announcement coordination with adaptive intervals
- `metrics_status.py`: `StatusLoop` - Background status monitoring and metrics emission
- `peer_events.py`: `PeerEventsBinder` - Consistent event binding for peer and piece managers
- `magnet_handling.py`: `MagnetHandler` - Magnet link file selection and metadata operations (BEP 53)
- `fast_resume.py`: `FastResumeLoader` - Fast resume data loading, validation, migration, and integrity verification

**Manager-Level Controllers** (per `AsyncSessionManager`):
- `torrent_addition.py`: `TorrentAdditionHandler` - Torrent addition workflow with queue integration and error recovery
- `manager_background.py`: `ManagerBackgroundTasks` - Background tasks for cleanup and metrics collection
- `scrape.py`: `ScrapeManager` - Tracker scraping operations with caching (BEP 48)
- `checkpoint_operations.py`: `CheckpointOperations` - Manager-level checkpoint operations (list, find, validate, cleanup)
- `manager_startup.py`: Component startup sequence coordination

**Peer Management Controllers**:
- `peers.py`: 
  - `PeerManagerInitializer` - Peer manager creation and callback wiring
  - `PeerConnectionHelper` - Centralized peer connection logic with deduplication
  - `PexBinder` - PEX (Peer Exchange) setup and binding (BEP 11)
- `dht_setup.py`: DHT discovery setup and metadata exchange for magnet links
- `download_startup.py`: Download initialization flow

**Command Executor** (`ccbt/executor/`):
- `executor.py`: `UnifiedCommandExecutor` routes commands to domain executors
- `manager.py`: `ExecutorManager` ensures single executor instance per session manager
- Domain executors: `TorrentExecutor`, `FileExecutor`, `QueueExecutor`, `NATExecutor`, `ScrapeExecutor`, `ConfigExecutor`, `ProtocolExecutor`, `SessionExecutor`, `SecurityExecutor`, `XetExecutor`
- `session_adapter.py`: `LocalSessionAdapter` and `DaemonSessionAdapter` for CLI/daemon communication

**Consensus Module** (`ccbt/consensus/`):
- `raft.py`: Raft consensus implementation for XET synchronization
- `byzantine.py`: Byzantine fault tolerance for distributed consensus
- `raft_state.py`: Raft state machine management

The executor pattern provides a unified interface for both CLI and daemon command execution, ensuring consistent behavior across execution contexts.

### Peer Connection Manager

Handles all peer connections with advanced pipelining. The `AsyncPeerConnectionManager` manages individual peer connections for a torrent session.

**Implementation:** `ccbt/peer/async_peer_connection.py`

**Features:**
- Async TCP connections
- Request pipelining (16-64 outstanding requests)
- Adaptive block sizing
- Connection pooling
- Choking/unchoking algorithms
- BitTorrent protocol handshake
- Extension protocol support (Fast, PEX, DHT, WebSeed, SSL, XET)

### Piece Manager

Implements advanced piece selection algorithms. The `AsyncPieceManager` coordinates piece downloading, verification, and completion tracking.

**Implementation:** `ccbt/piece/async_piece_manager.py`

**Algorithms:**
- **Rarest-First**: Optimal swarm health
- **Sequential**: For streaming media
- **Round-Robin**: Simple fallback
- **Endgame Mode**: Duplicate requests for completion
- File selection support for partial downloads

### Disk I/O Manager

Optimized disk operations with multiple strategies. The disk I/O system is initialized via `init_disk_io()` and managed through the session manager.

**Implementation:** `ccbt/storage/disk_io.py`

**Optimizations:**
- File preallocation (sparse/full)
- Write batching and buffering
- Memory-mapped I/O
- io_uring support (Linux)
- Direct I/O for high-performance storage
- Parallel hash verification
- Checkpoint management for resume capability

## Data Flow

### Download Process

```
1. Torrent Loading
   ┌─────────────┐
   │ Torrent File│ ──┐
   │ or Magnet   │   │
   └─────────────┘   │
                     │
2. Tracker Announce  │
   ┌─────────────┐   │
   │   Tracker  │ ◄──┘
   │   Client   │
   └─────────────┘
           │
           ▼
3. Peer Discovery
   ┌─────────────┐
   │    DHT     │
   │   Manager  │
   └─────────────┘
           │
           ▼
4. Peer Connections
   ┌─────────────┐
   │    Peer    │
   │ Connection │
   │   Manager  │
   └─────────────┘
           │
           ▼
5. Piece Selection
   ┌─────────────┐
   │    Piece    │
   │   Manager   │
   └─────────────┘
           │
           ▼
6. Data Transfer
   ┌─────────────┐
   │    Disk     │
   │     I/O     │
   │   Manager   │
   └─────────────┘
```

### Event System

The system uses an event-driven architecture for loose coupling. Events are emitted through the global `EventBus` and can be subscribed to by any component.

**Implementation:** `ccbt/utils/events.py`

The event system includes comprehensive event types:

The `EventType` enum defines all system events including peer, piece, torrent, tracker, DHT, protocol, extension, and security events. The complete enum with all event types:

```python
--8<-- "ccbt/utils/events.py:34:152"
```

Events are emitted using the global event bus via the `emit_event()` function:

```python
--8<-- "ccbt/utils/events.py:658:661"
```

## Configuration System

### Hierarchical Configuration

Configuration is managed by `ConfigManager` which loads settings from multiple sources in priority order.

**Implementation:** `ccbt/config/config.py`

The `ConfigManager` class handles configuration loading, validation, and hot-reload. It searches for configuration files in standard locations and supports encrypted proxy passwords. See the initialization:

```python
--8<-- "ccbt/config/config.py:46:60"
```

**Configuration Sources (in order):**
1. Default values (from Pydantic models)
2. Configuration file (`ccbt.toml` in current directory, `~/.config/ccbt/ccbt.toml`, or `~/.ccbt.toml`)
3. Environment variables (`CCBT_*`)
4. CLI arguments
5. Per-torrent overrides

### Hot Reload

The `ConfigManager` supports hot-reload of configuration files without restarting the application. Hot-reload is automatically started when a config file is detected.

## Monitoring and Observability

### Metrics Collection

Metrics collection is initialized via `init_metrics()` and provides Prometheus-compatible metrics.

**Implementation:** `ccbt/monitoring/metrics_collector.py`

Metrics are initialized in the session manager's `start()` method and can be accessed via `session.metrics` if enabled in configuration.

### Alert System

The alert system provides rule-based alerting for various system conditions.

**Implementation:** `ccbt/monitoring/alert_manager.py`

### Tracing

Distributed tracing support for performance analysis and debugging.

**Implementation:** `ccbt/monitoring/tracing.py`

## Security Features

### Security Manager

The `SecurityManager` provides comprehensive security features including IP filtering, peer validation, rate limiting, and anomaly detection.

**Implementation:** `ccbt/security/security_manager.py`

The security manager is initialized in the session manager's `start()` method and can load IP filters from configuration.

### Peer Validation

Peer validation is handled by the `PeerValidator` which checks for blocked IPs and suspicious behavior patterns.

**Implementation:** `ccbt/security/peer_validator.py`

### Rate Limiting

Adaptive rate limiting for bandwidth management is provided by the `RateLimiter` and `AdaptiveLimiter` (ML-based).

**Implementation:** `ccbt/security/rate_limiter.py`, `ccbt/ml/adaptive_limiter.py`

## Extensibility

### Plugin System

The plugin system allows for optional plugins and extensions to be registered and managed.

**Implementation:** `ccbt/plugins/base.py`

Plugins can be registered with the `PluginManager` and provide hooks for various system events.

### Protocol Extensions

BitTorrent protocol extensions are managed by the `ExtensionManager` which handles Fast Extension, PEX, DHT, WebSeed, SSL, and XET extensions.

**Implementation:** `ccbt/extensions/manager.py`

The `ExtensionManager` initializes all supported BitTorrent extensions including Protocol, SSL, Fast, PEX, and DHT extensions. Each extension is registered with its capabilities and status. See the initialization logic:

```python
--8<-- "ccbt/extensions/manager.py:51:110"
```

### Protocol Manager

The `ProtocolManager` manages multiple protocols (BitTorrent, IPFS, WebTorrent, XET, Hybrid) with circuit breaker support and performance tracking.

**Implementation:** `ccbt/protocols/base.py`

The `ProtocolManager` manages multiple protocols with circuit breaker support, performance tracking, and automatic event emission. Protocols are registered with their type and statistics are tracked per protocol. See the initialization and registration:

```python
--8<-- "ccbt/protocols/base.py:286:324"
```

## Performance Optimizations

### Async/Await Throughout

All I/O operations are asynchronous:
- Network operations
- Disk I/O
- Hash verification
- Configuration loading

### Memory Management

- Zero-copy message handling where possible
- Ring buffers for high-throughput scenarios
- Memory-mapped file I/O
- Efficient data structures

### Connection Pooling

Connection pooling is implemented in the peer connection layer to efficiently reuse TCP connections and manage connection limits.

**Implementation:** `ccbt/peer/connection_pool.py`

## Testing Architecture

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Performance Tests**: Benchmarking and profiling
- **Chaos Tests**: Fault injection and resilience testing

### Test Utilities

Test utilities and mocks are available in the `tests/` directory for unit, integration, property, and performance testing.

## Future Architecture Considerations

### Scalability

- Horizontal scaling with multiple session managers
- Distributed peer discovery
- Load balancing across instances

### Cloud Integration

- Cloud storage backends
- Serverless deployment options
- Container orchestration

### Advanced Features

- Machine learning for peer selection
- Blockchain-based peer discovery
- **IPFS integration** (Implemented)
- WebTorrent compatibility

## IPFS Protocol Integration

### Architecture Overview

The IPFS protocol integration provides decentralized content addressing and peer-to-peer networking capabilities through an IPFS daemon.

**Implementation:** `ccbt/protocols/ipfs.py`

### Integration Points

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS Protocol Integration                  │
├─────────────────────────────────────────────────────────────┤
│  Session Manager                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         AsyncSessionManager                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │         ProtocolManager                         │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │ │  │
│  │  │  │ BitTorrent   │  │    IPFS      │           │ │  │
│  │  │  │  Protocol    │  │  Protocol    │           │ │  │
│  │  │  └──────────────┘  └──────────────┘           │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  IPFS Protocol                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   HTTP API   │  │   Pubsub     │  │     DHT      │     │
│  │  Client      │  │  Messaging   │  │  Discovery   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Content    │  │   Gateway    │  │   Pinning    │     │
│  │  Operations  │  │   Fallback   │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  IPFS Daemon (External)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  IPFS Node (libp2p, Bitswap, DHT, Gateway)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Protocol Lifecycle

1. **Initialization**: Protocol created and registered in `ProtocolManager`
2. **Connection**: `start()` connects to IPFS daemon via HTTP API
3. **Verification**: Node ID queried to verify connection
4. **Operation**: Content operations, peer connections, messaging
5. **Cleanup**: `stop()` disconnects and cleans up resources

### Session Manager Integration

The IPFS protocol is automatically registered during session manager startup if enabled in configuration. The protocol is registered with the protocol manager and started, with graceful error handling that doesn't prevent session startup if IPFS is unavailable. See the initialization:

```python
--8<-- "ccbt/session/async_main.py:441:462"
```

### Content Addressing

IPFS uses Content Identifiers (CIDs) for immutable content addressing:

- **CIDv0**: Base58-encoded, legacy format (e.g., `Qm...`)
- **CIDv1**: Multibase-encoded, modern format (e.g., `bafybei...`)
- Content is addressed by its cryptographic hash
- Same content always produces the same CID

### Torrent-to-IPFS Conversion

Torrents can be converted to IPFS content:

1. Torrent metadata serialized to JSON
2. Metadata added to IPFS, generating CID
3. Piece hashes referenced as blocks
4. Content automatically pinned if configured

### Peer Communication

- **Pubsub**: Topic-based messaging (`/ccbt/peer/{peer_id}`)
- **Multiaddr**: Standard format for peer addresses
- **DHT**: Distributed hash table for peer discovery
- **Message Queues**: Per-peer queues for reliable delivery

### Content Operations

- **Add**: Content added to IPFS, returns CID
- **Get**: Content retrieved by CID
- **Pin**: Content pinned to prevent garbage collection
- **Unpin**: Content unpinned, may be garbage collected
- **Stats**: Content statistics (size, blocks, links)

### Configuration

IPFS configuration is part of the main `Config` model. See the configuration documentation for details on IPFS settings.

### Error Handling

- Connection failures: Automatic retry with exponential backoff
- Timeouts: Configurable per-operation timeouts
- Daemon unavailable: Graceful degradation, protocol remains registered
- Content not found: Returns `None`, logs warning

### Performance Considerations

- **Async Operations**: All IPFS API calls use `asyncio.to_thread` to avoid blocking
- **Caching**: Discovery results and content stats cached with TTL
- **Gateway Fallback**: Public gateways used if daemon unavailable
- **Connection Pooling**: Reuses HTTP connections to IPFS daemon

### Sequence Diagram

```
Session Manager          IPFS Protocol          IPFS Daemon
     │                         │                      │
     │  start()                │                      │
     ├────────────────────────>│                      │
     │                         │  connect()           │
     │                         ├─────────────────────>│
     │                         │  id()                │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
     │  add_content()           │                      │
     ├────────────────────────>│  add_bytes()         │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <CID>                  │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  get_content(CID)       │                      │
     ├────────────────────────>│  cat(CID)            │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <content>               │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  stop()                  │                      │
     ├────────────────────────>│  close()             │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
```

For more detailed information about specific components, see the individual documentation files and source code.
