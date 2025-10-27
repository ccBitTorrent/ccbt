# ccBitTorrent - High-Performance BitTorrent Client

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## Features

### 🚀 Performance Optimizations
- **Async I/O**: Full asyncio implementation for superior concurrency
- **Rarest-First Selection**: Intelligent piece selection for optimal swarm health
- **Endgame Mode**: Duplicate requests for faster completion
- **Request Pipelining**: Deep request queues (16-64 outstanding requests per peer)
- **Tit-for-Tat Choking**: Fair bandwidth allocation with optimistic unchoke
- **Parallel Metadata**: Concurrent ut_metadata fetching from multiple peers
- **Disk I/O Optimization**: File preallocation, write batching, memory-mapped I/O
- **Hash Verification Pool**: Parallel SHA-1 verification across worker threads

### 🔧 Advanced Configuration
- **TOML Configuration**: Comprehensive config system with hot-reload
- **Per-Torrent Settings**: Individual torrent configuration overrides
- **Rate Limiting**: Global and per-torrent upload/download limits
- **Strategy Selection**: Round-robin, rarest-first, or sequential piece selection
- **Streaming Mode**: Priority-based piece selection for media files

### 🌐 Network Features
- **UDP Tracker Support**: BEP 15 compliant UDP tracker communication
- **Enhanced DHT**: Full Kademlia routing table with iterative lookups
- **Peer Exchange (PEX)**: BEP 11 compliant peer discovery
- **Connection Management**: Adaptive peer selection and connection limits
- **Protocol Optimizations**: Memory-efficient message handling with zero-copy paths

### 📊 Observability
- **Metrics Export**: Prometheus-compatible metrics for monitoring
- **Structured Logging**: Configurable logging with per-peer tracing
- **Performance Stats**: Real-time throughput, latency, and queue depth tracking
- **Health Monitoring**: Connection quality and peer reliability scoring

### 🔄 Resume Functionality
- **Checkpoint Management**: Automatic save/load of download progress
- **Smart Resume**: Auto-detection of existing checkpoints with user prompts
- **Source Tracking**: Stores torrent file paths and magnet links for easy resume
- **Format Support**: Both JSON and binary checkpoint formats with compression
- **Retention Policies**: Configurable cleanup of old and completed checkpoints
- **CLI Integration**: Complete command-line interface for checkpoint management
- **Error Recovery**: Graceful handling of corrupted or missing checkpoints

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Windows Users
For optimal performance on Windows, install pywin32:
```bash
pip install pywin32
```

## Configuration

ccBitTorrent uses a comprehensive TOML-based configuration system. Create a `ccbt.toml` file in your working directory or home directory:

### Basic Configuration
```toml
[network]
max_global_peers = 200
max_peers_per_torrent = 50
pipeline_depth = 16
block_size_kib = 16
listen_port = 6881

[disk]
preallocate = "full"
write_batch_kib = 64
use_mmap = true
hash_workers = 4

[strategy]
piece_selection = "rarest_first"
endgame_duplicates = 2
streaming_mode = false

[discovery]
enable_dht = true
enable_pex = true
enable_udp_trackers = true

[limits]
global_down_kib = 0  # 0 = unlimited
global_up_kib = 0     # 0 = unlimited

[observability]
log_level = "INFO"
enable_metrics = true
metrics_port = 9090
```

### Configuration Hierarchy
1. **Defaults**: Built-in sensible defaults
2. **Config File**: `ccbt.toml` in current directory or `~/.config/ccbt/ccbt.toml`
3. **Environment Variables**: `CCBT_*` prefixed variables
4. **CLI Arguments**: Command-line overrides
5. **Per-Torrent**: Individual torrent settings

### Environment Variables
```bash
export CCBT_MAX_PEERS=100
export CCBT_LISTEN_PORT=6881
export CCBT_PIECE_SELECTION=rarest_first
export CCBT_DOWN_LIMIT=1024  # KiB/s
export CCBT_UP_LIMIT=512     # KiB/s
export CCBT_LOG_LEVEL=DEBUG
```

## Usage

### Command Line Interface

#### Basic Usage
```bash
# Download a torrent file
python -m ccbt torrent.torrent

# Download from magnet link
python -m ccbt "magnet:?xt=urn:btih:..."

# Run in daemon mode with multiple torrents
python -m ccbt --daemon --add torrent1.torrent --add "magnet:?xt=..."
```

#### Advanced Options
```bash
# Override configuration
python -m ccbt --config custom.toml torrent.torrent

# Set rate limits
python -m ccbt --down-limit 1024 --up-limit 512 torrent.torrent

# Enable debug logging
python -m ccbt --log-level DEBUG torrent.torrent

# Streaming mode for media files
python -m ccbt --streaming torrent.torrent
```

#### Resume Functionality
```bash
# Resume download from checkpoint
python -m ccbt resume <info_hash>

# Resume with interactive mode
python -m ccbt resume <info_hash> --interactive

# Download with automatic checkpoint detection
python -m ccbt download torrent.torrent --resume

# Magnet with checkpoint detection
python -m ccbt magnet "magnet:?xt=urn:btih:..." --resume

# List all available checkpoints
python -m ccbt checkpoints list

# Clean old checkpoints (older than 7 days)
python -m ccbt checkpoints clean --days 7

# Delete specific checkpoint
python -m ccbt checkpoints delete <info_hash>
```

#### Checkpoint Management
```bash
# Enable checkpointing with custom directory
python -m ccbt --checkpoint-dir /path/to/checkpoints torrent.torrent

# Disable checkpointing
python -m ccbt --no-checkpoint torrent.torrent

# Force resume from checkpoint
python -m ccbt --resume torrent.torrent
```

### Python API

#### Basic Download
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

#### Advanced Configuration
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

#### Resume Functionality
```python
import asyncio
from ccbt.session import AsyncSessionManager
from ccbt.checkpoint import CheckpointManager
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

#### Checkpoint Management
```python
from ccbt.checkpoint import CheckpointManager
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

#### Interactive Resume
```python
from ccbt.session import AsyncSessionManager
from ccbt.checkpoint import CheckpointManager

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

## Performance Tuning

### Network Optimization
- **Pipeline Depth**: Increase for high-latency connections (16-64)
- **Block Size**: Larger blocks for high-bandwidth connections (16-64 KiB)
- **Socket Buffers**: Increase for high-throughput scenarios
- **Connection Limits**: Balance between discovery and resource usage

### Disk I/O Optimization
- **Preallocation**: Use "full" for better performance on SSDs
- **Write Batching**: Larger batches reduce system call overhead
- **Memory Mapping**: Enable for read-heavy workloads
- **Hash Workers**: Scale with CPU cores (4-8 workers)

### Strategy Selection
- **Rarest-First**: Best for swarm health and completion time
- **Sequential**: Good for streaming media files
- **Round-Robin**: Simple but less efficient

### Rate Limiting
- **Global Limits**: Overall bandwidth constraints
- **Per-Torrent Limits**: Individual torrent bandwidth allocation
- **Per-Peer Limits**: Prevent single peer from consuming all bandwidth

## Monitoring and Metrics

### Prometheus Metrics
Enable metrics export on port 9090:
```toml
[observability]
enable_metrics = true
metrics_port = 9090
```

Access metrics at `http://localhost:9090/metrics`

### Key Metrics
- `ccbt_download_rate_bytes_per_second`: Download speed
- `ccbt_upload_rate_bytes_per_second`: Upload speed
- `ccbt_connected_peers`: Number of connected peers
- `ccbt_pieces_completed`: Number of completed pieces
- `ccbt_disk_queue_depth`: Disk I/O queue depth
- `ccbt_hash_queue_depth`: Hash verification queue depth

### Logging
```toml
[observability]
log_level = "INFO"
log_file = "ccbt.log"
enable_peer_tracing = false
```

## Architecture

### Core Components
- **AsyncPeerConnectionManager**: High-performance peer connections with pipelining
- **AsyncPieceManager**: Advanced piece selection with rarest-first and endgame
- **AsyncMetadataExchange**: Parallel metadata fetching with reliability scoring
- **DiskIOManager**: Optimized disk I/O with preallocation and batching
- **ConfigManager**: Centralized configuration with hot-reload

### Data Flow
1. **Tracker Announce**: HTTP/UDP tracker communication for peer discovery
2. **DHT Bootstrap**: Kademlia DHT for additional peer discovery
3. **Peer Connection**: Async TCP connections with handshake and bitfield exchange
4. **Piece Selection**: Rarest-first algorithm with per-peer availability tracking
5. **Request Pipelining**: Deep request queues with adaptive block sizing
6. **Hash Verification**: Parallel SHA-1 verification with worker pool
7. **Disk Assembly**: Batched writes with memory-mapped reads

## Development

### Quick Start

#### With UV (Recommended - Fastest)
```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up development environment with UV
make uv-install

# Run all checks with UV
make uv-run-all
```

#### Traditional Setup
```bash
# Set up development environment
make setup-dev

# Install development dependencies
make install-dev

# Run all checks
make pre-commit
```

### Development Tools

This project uses modern Python tooling for development:

- **UV**: Ultra-fast Python package manager and project manager
- **Ruff**: Fast Python linter and formatter (replaces black, isort, flake8)
- **Ty**: Fast type checker (replaces mypy)
- **Pre-commit**: Git hooks for code quality
- **Pytest**: Testing framework with coverage
- **Bandit**: Security linting
- **Commitizen**: Conventional commit messages

### Available Commands

#### UV Commands (Recommended - Fastest)
```bash
# UV setup and management
make uv-install         # Install UV and sync dependencies
make uv-sync           # Sync dependencies with lock file
make uv-build          # Build the package
make uv-publish        # Publish to PyPI

# UV development commands
make uv-run-lint       # Run linting with UV
make uv-run-format     # Run formatting with UV
make uv-run-test       # Run tests with UV
make uv-run-type       # Run type checking with UV
make uv-run-security   # Run security checks with UV
make uv-run-all        # Run all checks with UV
```

#### Traditional Commands
```bash
# Development setup
make setup-dev          # Set up pre-commit hooks and run initial checks
make install-dev        # Install development dependencies

# Code quality
make lint               # Run linting (ruff)
make format             # Format code (ruff)
make type-check         # Run type checking (ty)
make pre-commit         # Run all pre-commit checks

# Testing
make test               # Run tests
make test-cov           # Run tests with coverage

# Cleanup
make clean              # Clean temporary files
```

### Running Tests
```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test categories
pytest tests/test_async_peer_connection.py -v
pytest tests/test_rarest_first.py -v
pytest tests/test_disk_io.py -v
```

### Benchmarks
```bash
# Run performance benchmarks
python benchmarks/bench_throughput.py
python benchmarks/bench_disk.py
```

### Code Quality
```bash
# Run all quality checks
make pre-commit

# Individual tools
make lint               # Ruff linting
make format             # Ruff formatting
make type-check         # Ty type checking

# Security checks
bandit -r ccbt/ -f json -o bandit-report.json
```

### Pre-commit Hooks

The project includes comprehensive pre-commit hooks that run automatically on commit:

- **Basic checks**: Trailing whitespace, file endings, YAML/JSON validation
- **Ruff**: Fast linting and formatting
- **Ty**: Fast type checking
- **Bandit**: Security vulnerability scanning
- **Pylint**: Additional code quality checks
- **Safety**: Dependency vulnerability scanning
- **Commitizen**: Conventional commit message validation

### Configuration Files

- `pyproject.toml`: Project configuration and tool settings
- `ruff.toml`: Ruff linting and formatting configuration
- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `mypy.ini`: Type checking configuration (for Ty compatibility)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- BitTorrent protocol specification (BEP 5, 10, 11, 15)
- libtorrent for reference implementation
- Python asyncio for high-performance I/O
- The BitTorrent community for protocol development