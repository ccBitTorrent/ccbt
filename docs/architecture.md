# Architecture Overview

This document provides a technical overview of ccBitTorrent's architecture, components, and data flow.

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

### AsyncSessionManager

The central orchestrator that manages the entire BitTorrent session:

```python
class AsyncSessionManager:
    """High-performance async session manager for multiple torrents."""
    
    def __init__(self, config: Config):
        self.config = config
        self.torrents: dict[str, Torrent] = {}
        self.peers: dict[str, Peer] = {}
        self.trackers: dict[str, TrackerClient] = {}
        self.dht: DHTManager | None = None
        self.metrics: MetricsCollector | None = None
```

**Responsibilities:**
- Torrent lifecycle management
- Peer connection coordination
- Resource allocation and limits
- Event dispatching
- Checkpoint management

### Peer Connection Manager

Handles all peer connections with advanced pipelining:

```python
class AsyncPeerConnectionManager:
    """High-performance peer connection manager with pipelining."""
    
    def __init__(self, config: NetworkConfig):
        self.connections: dict[str, AsyncPeerConnection] = {}
        self.pipeline_depth = config.pipeline_depth
        self.max_connections = config.max_global_peers
```

**Features:**
- Async TCP connections
- Request pipelining (16-64 outstanding requests)
- Adaptive block sizing
- Connection pooling
- Choking/unchoking algorithms

### Piece Manager

Implements advanced piece selection algorithms:

```python
class AsyncPieceManager:
    """Advanced piece selection with rarest-first and endgame."""
    
    def __init__(self, strategy: StrategyConfig):
        self.strategy = strategy
        self.piece_selection = PieceSelectionStrategy.RAREST_FIRST
        self.endgame_threshold = 0.9
        self.endgame_duplicates = 2
```

**Algorithms:**
- **Rarest-First**: Optimal swarm health
- **Sequential**: For streaming media
- **Round-Robin**: Simple fallback
- **Endgame Mode**: Duplicate requests for completion

### Disk I/O Manager

Optimized disk operations with multiple strategies:

```python
class DiskIOManager:
    """Optimized disk I/O with preallocation and batching."""
    
    def __init__(self, config: DiskConfig):
        self.config = config
        self.write_queue = asyncio.Queue()
        self.read_cache = {}
        self.hash_workers = config.hash_workers
```

**Optimizations:**
- File preallocation (sparse/full)
- Write batching and buffering
- Memory-mapped I/O
- io_uring support (Linux)
- Direct I/O for high-performance storage
- Parallel hash verification

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

The system uses an event-driven architecture for loose coupling:

```python
class EventType(Enum):
    TORRENT_ADDED = "torrent_added"
    TORRENT_COMPLETED = "torrent_completed"
    PEER_CONNECTED = "peer_connected"
    PIECE_COMPLETED = "piece_completed"
    ALERT_TRIGGERED = "alert_triggered"

async def emit_event(event: Event) -> None:
    """Emit event to all registered handlers."""
    for handler in event_handlers[event.event_type]:
        await handler(event)
```

## Configuration System

### Hierarchical Configuration

```python
class Config:
    """Main configuration class with validation."""
    
    network: NetworkConfig
    disk: DiskConfig
    strategy: StrategyConfig
    discovery: DiscoveryConfig
    observability: ObservabilityConfig
    limits: LimitsConfig
```

**Configuration Sources (in order):**
1. Default values
2. Configuration file (`ccbt.toml`)
3. Environment variables (`CCBT_*`)
4. CLI arguments
5. Per-torrent overrides

### Hot Reload

```python
class ConfigManager:
    """Configuration manager with hot-reload support."""
    
    async def reload_config(self) -> None:
        """Reload configuration without restart."""
        new_config = self.load_config()
        await self.apply_config_changes(new_config)
```

## Monitoring and Observability

### Metrics Collection

```python
class MetricsCollector:
    """Prometheus-compatible metrics collection."""
    
    def __init__(self):
        self.download_rate = Counter('ccbt_download_rate_bytes_per_second')
        self.upload_rate = Counter('ccbt_upload_rate_bytes_per_second')
        self.connected_peers = Gauge('ccbt_connected_peers')
        self.pieces_completed = Counter('ccbt_pieces_completed')
```

### Alert System

```python
class AlertManager:
    """Rule-based alert system."""
    
    def __init__(self):
        self.rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
    
    async def evaluate_rule(self, rule: AlertRule, value: float) -> None:
        """Evaluate alert rule against current value."""
        if rule.condition.evaluate(value):
            await self.trigger_alert(rule, value)
```

### Tracing

```python
class TracingManager:
    """Distributed tracing for performance analysis."""
    
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)
    
    def trace_peer_connection(self, peer_id: str) -> Span:
        """Create span for peer connection operations."""
        return self.tracer.start_span(f"peer_connection_{peer_id}")
```

## Security Features

### Peer Validation

```python
class PeerValidator:
    """Validates peer connections and behavior."""
    
    async def validate_peer(self, peer: Peer) -> bool:
        """Validate peer connection and behavior."""
        if self.is_blocked_ip(peer.ip):
            return False
        
        if self.has_suspicious_behavior(peer):
            await self.block_peer(peer)
            return False
        
        return True
```

### Rate Limiting

```python
class RateLimiter:
    """Adaptive rate limiting for bandwidth management."""
    
    def __init__(self, config: LimitsConfig):
        self.global_down_limit = config.global_down_kib
        self.global_up_limit = config.global_up_kib
        self.per_peer_limits = {}
```

## Extensibility

### Plugin System

```python
class PluginManager:
    """Manages optional plugins and extensions."""
    
    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self.hooks: dict[str, list[Callable]] = {}
    
    def register_plugin(self, plugin: Plugin) -> None:
        """Register a new plugin."""
        self.plugins[plugin.name] = plugin
        plugin.install(self)
```

### Protocol Extensions

```python
class ProtocolExtension:
    """Base class for BitTorrent protocol extensions."""
    
    def __init__(self, name: str):
        self.name = name
        self.capabilities = set()
    
    async def handle_message(self, peer: Peer, message: bytes) -> None:
        """Handle extension-specific messages."""
        pass
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

```python
class ConnectionPool:
    """Reusable connection pool for efficiency."""
    
    def __init__(self, max_connections: int):
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.active_connections = set()
    
    async def get_connection(self) -> Connection:
        """Get connection from pool or create new one."""
        try:
            return self.pool.get_nowait()
        except asyncio.QueueEmpty:
            return await self.create_connection()
```

## Testing Architecture

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Performance Tests**: Benchmarking and profiling
- **Chaos Tests**: Fault injection and resilience testing

### Test Utilities

```python
class MockPeer:
    """Mock peer for testing."""
    
    def __init__(self, pieces: set[int]):
        self.pieces = pieces
        self.upload_speed = 1024 * 1024  # 1 MB/s
        self.download_speed = 512 * 1024  # 512 KB/s
```

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
- IPFS integration
- WebTorrent compatibility

For more detailed information about specific components, see the individual documentation files and source code.
