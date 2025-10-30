# ccBitTorrent API Reference

## Core Classes

### Session

The main client session that manages all BitTorrent operations.

```python
from ccbt import Session
from ccbt.config import ConfigManager

# Create session
config_manager = ConfigManager()
config = config_manager.config
session = Session(config)

# Start session
await session.start()

# Add torrent
torrent = await session.add_torrent("example.torrent")

# Start download
await session.start_download(torrent)

# Stop session
await session.stop()
```

#### Methods

##### `start() -> None`
Start the BitTorrent session.

##### `stop() -> None`
Stop the BitTorrent session.

##### `add_torrent(torrent_path: str) -> Torrent`
Add a torrent file to the session.

##### `remove_torrent(torrent: Torrent) -> None`
Remove a torrent from the session.

##### `get_torrents() -> List[Torrent]`
Get all active torrents.

##### `get_peers() -> List[Peer]`
Get all connected peers.

### Resume Functionality

ccBitTorrent provides comprehensive resume functionality for interrupted downloads through checkpoint management.

#### Checkpoint Management

```python
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.models import DiskConfig

# Create checkpoint manager
config = DiskConfig(checkpoint_enabled=True)
checkpoint_manager = CheckpointManager(config)

# Save checkpoint
await checkpoint_manager.save_checkpoint(checkpoint)

# Load checkpoint
checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

# List all checkpoints
checkpoints = await checkpoint_manager.list_checkpoints()

# Delete checkpoint
await checkpoint_manager.delete_checkpoint(info_hash)
```

#### Session Resume Methods

```python
from ccbt.session import AsyncSessionManager

session = AsyncSessionManager()

# Resume from checkpoint
info_hash_hex = await session.resume_from_checkpoint(
    info_hash_bytes, 
    checkpoint, 
    torrent_path="/path/to/torrent.torrent"  # Optional
)

# List resumable checkpoints
resumable = await session.list_resumable_checkpoints()

# Find checkpoint by name
checkpoint = await session.find_checkpoint_by_name("My Torrent")

# Get checkpoint info
info = await session.get_checkpoint_info(info_hash_bytes)

# Validate checkpoint
is_valid = await session.validate_checkpoint(checkpoint)

# Cleanup completed checkpoints
cleaned_count = await session.cleanup_completed_checkpoints()
```

#### Torrent Session Resume

```python
from ccbt.session import AsyncTorrentSession

# Create session with resume capability
session = AsyncTorrentSession(torrent_data, output_dir)

# Start with resume from checkpoint
await session.start(resume=True)

# Check if resuming from checkpoint
if session.resume_from_checkpoint:
    print("Resuming from checkpoint")
```

#### Configuration Options

```python
from ccbt.models import DiskConfig

config = DiskConfig(
    checkpoint_enabled=True,                    # Enable checkpointing
    checkpoint_format=CheckpointFormat.BOTH,   # JSON and binary formats
    checkpoint_dir="/path/to/checkpoints",      # Custom checkpoint directory
    checkpoint_interval=30.0,                   # Save interval in seconds
    checkpoint_on_piece=True,                   # Save after each piece
    auto_resume=True,                           # Auto-resume on startup
    checkpoint_compression=True,                # Compress binary checkpoints
    auto_delete_checkpoint_on_complete=True,    # Delete on completion
    checkpoint_retention_days=30                # Retention period
)
```

#### Checkpoint Model

```python
from ccbt.models import TorrentCheckpoint

checkpoint = TorrentCheckpoint(
    info_hash=b'\x00' * 20,
    torrent_name="My Torrent",
    created_at=time.time(),
    updated_at=time.time(),
    total_pieces=100,
    piece_length=16384,
    total_length=1638400,
    verified_pieces=[0, 1, 2],  # Verified piece indices
    piece_states={0: PieceState.VERIFIED, 1: PieceState.VERIFIED},
    download_stats=DownloadStats(...),
    output_dir="/downloads",
    files=[FileCheckpoint(...)],
    
    # Resume metadata
    torrent_file_path="/path/to/torrent.torrent",  # Original torrent file
    magnet_uri="magnet:?xt=urn:btih:...",         # Original magnet link
    announce_urls=["http://tracker.example.com/announce"],
    display_name="My Torrent"
)
```

#### CLI Resume Commands

```bash
# Resume download from checkpoint
ccbt resume <info_hash>

# Resume with interactive mode
ccbt resume <info_hash> --interactive

# List all checkpoints
ccbt checkpoints list

# Clean old checkpoints
ccbt checkpoints clean --days 7

# Delete specific checkpoint
ccbt checkpoints delete <info_hash>

# Download with checkpoint detection
ccbt download torrent.torrent --resume

# Magnet with checkpoint detection
ccbt magnet "magnet:?xt=urn:btih:..." --resume
```

#### Resume Priority Order

When resuming from checkpoint, the system follows this priority:

1. **Explicit torrent path** (if provided to `resume_from_checkpoint()`)
2. **Stored torrent file path** (from checkpoint metadata)
3. **Stored magnet URI** (from checkpoint metadata)
4. **Fail with informative error** (if no source found)

#### Interactive Prompts

When a checkpoint is found but `--resume` is not specified:

- **Interactive mode**: Prompts user "Resume from checkpoint? [Y/n]"
- **Non-interactive mode**: Starts fresh download
- **Auto-resume enabled**: Automatically resumes without prompt

#### Error Handling

```python
try:
    await session.resume_from_checkpoint(info_hash, checkpoint)
except ValueError as e:
    print(f"Cannot resume: {e}")
    # Handle missing torrent source
except CheckpointCorruptedError as e:
    print(f"Checkpoint corrupted: {e}")
    # Handle corrupted checkpoint
except CheckpointNotFoundError as e:
    print(f"Checkpoint not found: {e}")
    # Handle missing checkpoint
```

#### Best Practices

1. **Enable checkpointing** for long downloads
2. **Use both JSON and binary formats** for reliability
3. **Set appropriate retention period** to avoid disk bloat
4. **Enable auto-delete on completion** to clean up finished downloads
5. **Store torrent files** alongside checkpoints for easy resume
6. **Validate checkpoints** before attempting resume
7. **Handle resume errors gracefully** in applications

### Torrent

Represents a BitTorrent torrent file and its state.

```python
from ccbt import Torrent

# Create torrent from file
torrent = Torrent.from_file("example.torrent")

# Create torrent from magnet link
torrent = Torrent.from_magnet("magnet:?xt=urn:btih:...")

# Get torrent information
print(f"Name: {torrent.name}")
print(f"Size: {torrent.total_size}")
print(f"Progress: {torrent.progress_percentage():.1f}%")
```

#### Properties

- `name: str` - Torrent name
- `total_size: int` - Total size in bytes
- `downloaded_bytes: int` - Downloaded bytes
- `uploaded_bytes: int` - Uploaded bytes
- `progress_percentage() -> float` - Download progress
- `is_complete() -> bool` - Whether download is complete
- `files: List[FileInfo]` - File information
- `pieces: List[PieceInfo]` - Piece information

#### Methods

##### `start() -> None`
Start the torrent download.

##### `stop() -> None`
Stop the torrent download.

##### `pause() -> None`
Pause the torrent download.

##### `resume() -> None`
Resume the torrent download.

### Peer

Represents a peer connection.

```python
from ccbt import Peer

# Create peer
peer = Peer("192.168.1.1", 6881)

# Get peer information
print(f"IP: {peer.ip}")
print(f"Port: {peer.port}")
print(f"Download Speed: {peer.download_speed}")
print(f"Upload Speed: {peer.upload_speed}")
```

#### Properties

- `ip: str` - Peer IP address
- `port: int` - Peer port
- `peer_id: bytes` - Peer ID
- `download_speed: int` - Download speed in bytes/s
- `upload_speed: int` - Upload speed in bytes/s
- `progress_percentage() -> float` - Peer progress
- `is_connected() -> bool` - Whether peer is connected

### PieceManager

Manages piece selection and verification.

```python
from ccbt import PieceManager

# Create piece manager
piece_manager = PieceManager(torrent)

# Get next piece to download
next_piece = piece_manager.get_next_piece()

# Mark piece as completed
piece_manager.mark_piece_completed(piece_index)

# Verify piece
is_valid = piece_manager.verify_piece(piece_index, data)
```

#### Methods

##### `get_next_piece() -> Optional[int]`
Get the next piece to download.

##### `mark_piece_completed(piece_index: int) -> None`
Mark a piece as completed.

##### `verify_piece(piece_index: int, data: bytes) -> bool`
Verify a piece's hash.

##### `get_piece_progress() -> float`
Get overall piece progress.

### Tracker

Handles tracker communication.

```python
from ccbt import Tracker

# Create tracker
tracker = Tracker("http://tracker.example.com:8080/announce")

# Announce to tracker
response = await tracker.announce(torrent, peer_id, port)

# Scrape tracker
stats = await tracker.scrape(torrent)
```

#### Methods

##### `announce(torrent: Torrent, peer_id: bytes, port: int) -> TrackerResponse`
Announce to the tracker.

##### `scrape(torrent: Torrent) -> TrackerStats`
Scrape tracker for statistics.

### DHT

Distributed Hash Table for peer discovery.

```python
from ccbt import DHT

# Create DHT
dht = DHT(port=6881)

# Start DHT
await dht.start()

# Find peers
peers = await dht.find_peers(torrent.info_hash)

# Stop DHT
await dht.stop()
```

#### Methods

##### `start() -> None`
Start the DHT node.

##### `stop() -> None`
Stop the DHT node.

##### `find_peers(info_hash: bytes) -> List[PeerInfo]`
Find peers for a torrent.

##### `get_node_count() -> int`
Get the number of DHT nodes.

## Services

### PeerService

Manages peer connections and communication.

```python
from ccbt.services import PeerService

# Create peer service
peer_service = PeerService(session)

# Add peer
await peer_service.add_peer("192.168.1.1", 6881)

# Remove peer
await peer_service.remove_peer(peer)

# Get peer statistics
stats = peer_service.get_statistics()
```

### TrackerService

Handles tracker communication.

```python
from ccbt.services import TrackerService

# Create tracker service
tracker_service = TrackerService(session)

# Add tracker
tracker_service.add_tracker("http://tracker.example.com:8080/announce")

# Announce to all trackers
await tracker_service.announce_all(torrent)

# Get tracker statistics
stats = tracker_service.get_statistics()
```

### StorageService

Manages file system operations.

```python
from ccbt.services import StorageService

# Create storage service
storage_service = StorageService(session)

# Create file
await storage_service.create_file(file_info)

# Write data
await storage_service.write_data(file_info, offset, data)

# Read data
data = await storage_service.read_data(file_info, offset, length)
```

### SecurityService

Provides security features.

```python
from ccbt.security import SecurityService

# Create security service
security_service = SecurityService()

# Validate peer
is_valid = await security_service.validate_peer(peer_info)

# Check rate limit
is_allowed = await security_service.check_rate_limit(peer_id, limit_type)

# Report violation
await security_service.report_violation(peer_id, violation_type)
```

### MLService

Machine learning features.

```python
from ccbt.ml import MLService

# Create ML service
ml_service = MLService()

# Predict peer quality
prediction = await ml_service.predict_peer_quality(peer_info)

# Select optimal pieces
pieces = await ml_service.select_optimal_pieces(available_pieces)

# Update performance data
await ml_service.update_performance(peer_id, performance_data)
```

### MonitoringService

Metrics and observability.

```python
from ccbt.monitoring import MonitoringService

# Create monitoring service
monitoring_service = MonitoringService()

# Start monitoring
await monitoring_service.start()

# Record metric
monitoring_service.record_metric("download_speed", 1024*1024)

# Get statistics
stats = monitoring_service.get_statistics()
```

## Events

### Event System

The event system allows components to communicate asynchronously.

```python
from ccbt.events import Event, EventType, emit_event, subscribe_to_event

# Emit an event
await emit_event(Event(
    event_type=EventType.PEER_CONNECTED.value,
    data={
        'peer_id': peer_id,
        'ip': ip,
        'port': port
    }
))

# Subscribe to events
async def handle_peer_connected(event: Event):
    print(f"Peer connected: {event.data['ip']}")

subscribe_to_event(EventType.PEER_CONNECTED.value, handle_peer_connected)
```

### Event Types

- `PEER_CONNECTED` - Peer connection established
- `PEER_DISCONNECTED` - Peer connection lost
- `PIECE_COMPLETED` - Piece download completed
- `TORRENT_COMPLETED` - Torrent download completed
- `DOWNLOAD_STARTED` - Download started
- `DOWNLOAD_STOPPED` - Download stopped
- `ERROR_OCCURRED` - Error occurred
- `WARNING_OCCURRED` - Warning occurred

## Configuration

### Configuration Management

```python
from ccbt.config import ConfigManager

# Create configuration manager
config_manager = ConfigManager("config.toml")

# Get configuration
config = config_manager.config

# Update configuration
config.network.listen_port = 6882
config_manager.save_config()

# Hot reload configuration
await config_manager.start_hot_reload()
```

### Configuration Classes

#### NetworkConfig
- `listen_port: int` - Listening port
- `max_global_peers: int` - Maximum global peers
- `max_peers_per_torrent: int` - Maximum peers per torrent
- `connection_timeout: float` - Connection timeout
- `peer_timeout: float` - Peer timeout

#### DiskConfig
- `download_path: str` - Download directory
- `preallocate: str` - Preallocation strategy
- `use_mmap: bool` - Use memory mapping
- `write_buffer_kib: int` - Write buffer size

#### ObservabilityConfig
- `log_level: str` - Log level
- `enable_metrics: bool` - Enable metrics
- `metrics_port: int` - Metrics port
- `enable_tracing: bool` - Enable tracing

## Plugins

### Plugin System

```python
from ccbt.plugins import Plugin, PluginManager

# Create plugin
class MyPlugin(Plugin):
    def __init__(self):
        super().__init__("my_plugin")
    
    async def on_peer_connected(self, event: Event):
        print(f"Peer connected: {event.data['ip']}")
    
    async def on_piece_completed(self, event: Event):
        print(f"Piece completed: {event.data['piece_index']}")

# Register plugin
plugin_manager = PluginManager()
plugin_manager.register_plugin(MyPlugin())

# Start plugin
await plugin_manager.start_plugin("my_plugin")
```

### Plugin Hooks

- `on_peer_connected` - Peer connection established
- `on_peer_disconnected` - Peer connection lost
- `on_piece_completed` - Piece download completed
- `on_torrent_completed` - Torrent download completed
- `on_download_started` - Download started
- `on_download_stopped` - Download stopped
- `on_error_occurred` - Error occurred

## Error Handling

### Exception Hierarchy

```python
from ccbt.exceptions import CCBTException, NetworkError, DiskError, ProtocolError

try:
    await session.start()
except NetworkError as e:
    print(f"Network error: {e}")
except DiskError as e:
    print(f"Disk error: {e}")
except CCBTException as e:
    print(f"General error: {e}")
```

### Exception Types

- `CCBTException` - Base exception class
- `NetworkError` - Network-related errors
- `DiskError` - Disk I/O errors
- `ProtocolError` - Protocol violations
- `ValidationError` - Data validation errors
- `ConfigurationError` - Configuration errors

## Async/Await

### Async Operations

All I/O operations are asynchronous and should be awaited:

```python
# Start session
await session.start()

# Add torrent
torrent = await session.add_torrent("example.torrent")

# Start download
await session.start_download(torrent)

# Wait for completion
while not torrent.is_complete():
    await asyncio.sleep(1)

# Stop session
await session.stop()
```

### Event Loops

```python
import asyncio

async def main():
    # Create session
    session = Session(config)
    
    # Start session
    await session.start()
    
    # Add torrent
    torrent = await session.add_torrent("example.torrent")
    
    # Start download
    await session.start_download(torrent)
    
    # Wait for completion
    while not torrent.is_complete():
        await asyncio.sleep(1)
    
    # Stop session
    await session.stop()

# Run event loop
asyncio.run(main())
```

## Best Practices

### Resource Management

```python
# Use context managers
async with session:
    torrent = await session.add_torrent("example.torrent")
    await session.start_download(torrent)
    # Session automatically cleaned up
```

### Error Handling

```python
try:
    await session.start()
    torrent = await session.add_torrent("example.torrent")
    await session.start_download(torrent)
except CCBTException as e:
    print(f"Error: {e}")
    # Handle error appropriately
finally:
    await session.stop()
```

### Performance Optimization

```python
# Use appropriate buffer sizes
config.disk.write_buffer_kib = 1024
config.network.socket_rcvbuf_kib = 256

# Enable optimizations
config.disk.use_mmap = True
config.network.tcp_nodelay = True

# Use appropriate worker counts
config.disk.disk_workers = 4
config.disk.hash_workers = 2
```

### Monitoring

```python
# Enable monitoring
config.observability.enable_metrics = True
config.observability.enable_tracing = True

# Set up alerts
alert_manager = AlertManager()
alert_manager.add_alert_rule(
    name="high_cpu",
    metric_name="system_cpu_usage",
    condition="value > 80",
    severity="warning"
)
```

## Examples

### Basic Download

```python
import asyncio
from ccbt.config import init_config
from ccbt.session import AsyncSessionManager

async def main():
    # Initialize configuration
    config_manager = init_config()
    
    # Create session manager
    session = AsyncSessionManager()
    await session.start()
    
    # Add torrent
    torrent_id = await session.add_torrent("torrent.torrent")
    
    # Monitor progress
    while True:
        status = await session.get_status(torrent_id)
        print(f"Progress: {status['progress']*100:.1f}%")
        
        if status['completed']:
            break
        
        await asyncio.sleep(1)
    
    await session.stop()

asyncio.run(main())
```

### Advanced Configuration

```python
from ccbt.config import Config, NetworkConfig, StrategyConfig

# Create custom configuration
config = Config()
config.network.max_global_peers = 100
config.network.pipeline_depth = 32
config.strategy.piece_selection = PieceSelectionStrategy.RAREST_FIRST
config.strategy.endgame_duplicates = 3

# Use custom config
session = AsyncSessionManager(config=config)
```

### Resume Functionality

```python
import asyncio
from ccbt.session import AsyncSessionManager
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.models import DiskConfig

async def resume_example():
    # Configure checkpointing
    config = DiskConfig(
        checkpoint_enabled=True,
        auto_resume=True,
        checkpoint_interval=30.0
    )
    
    # Create session manager
    session = AsyncSessionManager()
    await session.start()
    
    # Check for existing checkpoints
    resumable = await session.list_resumable_checkpoints()
    print(f"Found {len(resumable)} resumable checkpoints")
    
    # Resume from specific checkpoint
    if resumable:
        checkpoint = resumable[0]
        info_hash_hex = await session.resume_from_checkpoint(
            checkpoint.info_hash, 
            checkpoint,
            torrent_path="/path/to/torrent.torrent"  # Optional
        )
        print(f"Resumed download: {info_hash_hex}")
    
    # Add new torrent with resume capability
    torrent_id = await session.add_torrent("new_torrent.torrent", resume=True)
    
    # Monitor progress
    while True:
        status = await session.get_status(torrent_id)
        print(f"Progress: {status['progress']*100:.1f}%")
        
        if status['completed']:
            break
        
        await asyncio.sleep(1)
    
    await session.stop()

asyncio.run(resume_example())
```

### Checkpoint Management

```python
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.models import TorrentCheckpoint, DiskConfig

async def checkpoint_management():
    config = DiskConfig(checkpoint_enabled=True)
    checkpoint_manager = CheckpointManager(config)
    
    # List all checkpoints
    checkpoints = await checkpoint_manager.list_checkpoints()
    print(f"Found {len(checkpoints)} checkpoints")
    
    # Get checkpoint info
    for checkpoint_info in checkpoints:
        checkpoint = await checkpoint_manager.load_checkpoint(checkpoint_info.info_hash)
        if checkpoint:
            print(f"Torrent: {checkpoint.torrent_name}")
            print(f"Progress: {len(checkpoint.verified_pieces)}/{checkpoint.total_pieces}")
            print(f"Can resume: {bool(checkpoint.torrent_file_path or checkpoint.magnet_uri)}")
    
    # Clean old checkpoints
    cleaned = await checkpoint_manager.cleanup_old_checkpoints(days=7)
    print(f"Cleaned {cleaned} old checkpoints")
    
    # Delete specific checkpoint
    if checkpoints:
        deleted = await checkpoint_manager.delete_checkpoint(checkpoints[0].info_hash)
        print(f"Deleted checkpoint: {deleted}")

asyncio.run(checkpoint_management())
```

### Interactive Resume

```python
from ccbt.session import AsyncSessionManager
from ccbt.storage.checkpoint import CheckpointManager

async def interactive_resume():
    session = AsyncSessionManager()
    checkpoint_manager = CheckpointManager()
    
    await session.start()
    
    # Check for checkpoints and prompt user
    checkpoints = await session.list_resumable_checkpoints()
    
    if checkpoints:
        print("Found existing checkpoints:")
        for i, checkpoint in enumerate(checkpoints):
            progress = len(checkpoint.verified_pieces) / checkpoint.total_pieces
            print(f"{i+1}. {checkpoint.torrent_name} ({progress*100:.1f}% complete)")
        
        # User selection (in real app, use proper input handling)
        choice = 0  # Simplified for example
        if 0 <= choice < len(checkpoints):
            selected_checkpoint = checkpoints[choice]
            
            # Resume selected checkpoint
            info_hash_hex = await session.resume_from_checkpoint(
                selected_checkpoint.info_hash,
                selected_checkpoint
            )
            print(f"Resumed: {info_hash_hex}")
    
    await session.stop()

asyncio.run(interactive_resume())
```

### Advanced Usage

```python
import asyncio
from ccbt import Session
from ccbt.config import ConfigManager
from ccbt.events import Event, EventType, subscribe_to_event

async def handle_piece_completed(event: Event):
    print(f"Piece {event.data['piece_index']} completed")

async def handle_torrent_completed(event: Event):
    print(f"Torrent {event.data['torrent_name']} completed")

async def main():
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.config
    
    # Enable monitoring
    config.observability.enable_metrics = True
    config.observability.enable_tracing = True
    
    # Create session
    session = Session(config)
    
    # Subscribe to events
    subscribe_to_event(EventType.PIECE_COMPLETED.value, handle_piece_completed)
    subscribe_to_event(EventType.TORRENT_COMPLETED.value, handle_torrent_completed)
    
    try:
        # Start session
        await session.start()
        
        # Add multiple torrents
        torrents = []
        for torrent_file in ["torrent1.torrent", "torrent2.torrent"]:
            torrent = await session.add_torrent(torrent_file)
            torrents.append(torrent)
        
        # Start downloads
        for torrent in torrents:
            await session.start_download(torrent)
        
        # Wait for all completions
        while not all(torrent.is_complete() for torrent in torrents):
            await asyncio.sleep(1)
        
        print("All downloads completed!")
        
    finally:
        # Stop session
        await session.stop()

if __name__ == "__main__":
    asyncio.run(main())
```
