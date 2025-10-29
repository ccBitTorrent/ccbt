# ccBitTorrent - High-Performance BitTorrent Client

[![codecov](https://codecov.io/gh/yourusername/ccbt/branch/master/graph/badge.svg)](https://codecov.io/gh/yourusername/ccbt)
[![codecov](https://codecov.io/gh/yourusername/ccbt/branch/master/graph/badge.svg?flag=unittests)](https://codecov.io/gh/yourusername/ccbt?flag=unittests)
[![codecov](https://codecov.io/gh/yourusername/ccbt/branch/master/graph/badge.svg?flag=security)](https://codecov.io/gh/yourusername/ccbt?flag=security)
[![codecov](https://codecov.io/gh/yourusername/ccbt/branch/master/graph/badge.svg?flag=ml)](https://codecov.io/gh/yourusername/ccbt?flag=ml)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## Quick Start

### Installation with UV

```bash
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ccBitTorrent
uv pip install ccbittorrent
```

### Your First Download

```bash
# Download from torrent file
uv run ccbt download movie.torrent

# Download from magnet link
uv run ccbt magnet "magnet:?xt=urn:btih:..."

# Launch Terminal Dashboard (Recommended)
uv run ccbt dashboard
```

## Documentation

- [Getting Started Guide](docs/getting-started.md) - Step-by-step tutorial
- [CLI Reference](docs/cli-reference.md) - Complete command reference
- [Terminal Dashboard](docs/dashboard-guide.md) - Dashboard features and usage
- [Configuration](docs/configuration.md) - Configuration options
- [Monitoring](docs/monitoring.md) - Observability and metrics
- [Checkpoints](docs/checkpoints.md) - Resume functionality
- [API Documentation](docs/API.md) - Python API usage
- [Performance Tuning](docs/performance.md) - Optimization guide
- [Architecture](docs/architecture.md) - Technical details

## Features

### 🚀 Performance Optimizations
- **Async I/O**: Full asyncio implementation for superior concurrency
- **Rarest-First Selection**: Intelligent piece selection for optimal swarm health
- **Endgame Mode**: Duplicate requests for faster completion
- **Request Pipelining**: Deep request queues (16-64 outstanding requests per peer)
- **Tit-for-Tat Choking**: Fair bandwidth allocation with optimistic unchoke
- **Parallel Metadata**: Concurrent ut_metadata fetching from multiple peers
- **Disk I/O Optimization**: File preallocation, write batching, ring-buffer staging, memory-mapped I/O, io_uring/direct I/O (configurable)
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
- **Terminal Dashboard**: Textual-based live dashboard for sessions, torrents, peers
- **Alert Manager**: Rule-based alerts with persistence and testing via CLI
- **Monitoring CLI**: `dashboard`, `alerts`, and `metrics` commands

### 🔄 Resume Functionality
- **Checkpoint Management**: Automatic save/load of download progress
- **Smart Resume**: Auto-detection of existing checkpoints with user prompts
- **Source Tracking**: Stores torrent file paths and magnet links for easy resume
- **Format Support**: Both JSON and binary checkpoint formats with compression
- **Retention Policies**: Configurable cleanup of old and completed checkpoints
- **CLI Integration**: Complete command-line interface for checkpoint management
- **Error Recovery**: Graceful handling of corrupted or missing checkpoints

## Terminal Dashboard

The Terminal Dashboard provides a live view of all torrents, peers, and system metrics in a beautiful terminal interface.

### Features
- **Real-time Updates**: Live torrent status and progress tracking
- **Peer Monitoring**: View connected peers, their speeds, and client information
- **Speed Visualization**: Download/upload speed graphs with sparklines
- **Alert System**: Real-time notifications for important events
- **Interactive Controls**: Keyboard shortcuts for common operations
- **Multi-torrent Support**: Monitor multiple downloads simultaneously

### Keyboard Shortcuts
- `q` - Quit dashboard
- `p` - Pause selected torrent
- `r` - Resume selected torrent
- `↑/↓` - Navigate torrent list
- `Enter` - View torrent details
- `Space` - Toggle pause/resume
- `D` - Delete selected torrent
- `H` - Show help

### Launching
```bash
# Start with default settings
uv run ccbt dashboard

# Custom refresh interval (seconds)
uv run ccbt dashboard --refresh 2.0

# Load alert rules on startup
uv run ccbt dashboard --rules /path/to/alert-rules.json
```

### Dashboard Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ ccBitTorrent Dashboard                    [Q] Quit [H] Help     │
├─────────────────────────────────────────────────────────────────┤
│ Overview                                                         │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐    │
│ │ Download Speed  │ │ Upload Speed    │ │ Connected Peers │    │
│ │ 1.2 MB/s        │ │ 256 KB/s        │ │ 12              │    │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│ Torrents                                    [P] Pause [R] Resume │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Name                Progress  Speed    Peers  Status        │ │
│ │ ████████████████░░░ 85.2%     1.2MB/s  12    Downloading   │ │
│ │ ████████████████████ 100%     0KB/s    8     Seeding       │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

For detailed dashboard usage, see the [Terminal Dashboard Guide](docs/dashboard-guide.md).

## Installation

### Prerequisites
- Python 3.8 or higher
- UV package manager (recommended)

### Install UV (if not already installed)

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install ccBitTorrent

```bash
# Install from PyPI
uv pip install ccbittorrent

# Or install from source
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

### Windows Users
For optimal performance on Windows, install pywin32:
```bash
uv pip install pywin32
```

## Usage

### Command Line Interface

#### Basic Usage
```bash
# Download a torrent file
uv run ccbt download torrent.torrent

# Download from magnet link
uv run ccbt magnet "magnet:?xt=urn:btih:..."

# Interactive mode
uv run ccbt interactive

# Terminal monitoring dashboard (Recommended)
uv run ccbt dashboard
```

#### Advanced Options
```bash
# Override configuration
uv run ccbt --config custom.toml torrent.torrent

# Set rate limits
uv run ccbt --down-limit 1024 --up-limit 512 torrent.torrent

# Enable debug logging
uv run ccbt --log-level DEBUG torrent.torrent

# Streaming mode for media files
uv run ccbt --streaming torrent.torrent
```

#### Resume Functionality
```bash
# Resume download from checkpoint
uv run ccbt resume <info_hash>

# Resume with interactive mode
uv run ccbt resume <info_hash> --interactive

# Download with automatic checkpoint detection
uv run ccbt download torrent.torrent --resume

# Magnet with checkpoint detection
uv run ccbt magnet "magnet:?xt=urn:btih:..." --resume

# List all available checkpoints
uv run ccbt checkpoints list

# Clean old checkpoints (older than 7 days)
uv run ccbt checkpoints clean --days 7

# Delete specific checkpoint
uv run ccbt checkpoints delete <info_hash>
```

#### Checkpoint Management
```bash
# Enable checkpointing with custom directory
uv run ccbt --checkpoint-dir /path/to/checkpoints torrent.torrent

# Disable checkpointing
uv run ccbt --no-checkpoint torrent.torrent

# Force resume from checkpoint
uv run ccbt --resume torrent.torrent
```

### Python API

For Python API usage, see the [API Documentation](docs/API.md).

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

For detailed configuration options, see the [Configuration Guide](docs/configuration.md).

## Performance Tuning

### Quick Tips
- **Pipeline Depth**: Increase for high-latency connections (16-64)
- **Block Size**: Larger blocks for high-bandwidth connections (16-64 KiB)
- **Preallocation**: Use "full" for better performance on SSDs
- **Memory Mapping**: Enable for read-heavy workloads
- **Hash Workers**: Scale with CPU cores (4-8 workers)

### Strategy Selection
- **Rarest-First**: Best for swarm health and completion time
- **Sequential**: Good for streaming media files
- **Round-Robin**: Simple but less efficient

For detailed performance optimization, see the [Performance Tuning Guide](docs/performance.md).

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

For detailed monitoring setup, see the [Monitoring Guide](docs/monitoring.md).

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

For detailed technical architecture, see the [Architecture Documentation](docs/architecture.md).

## Development

### Quick Start with UV (Recommended)

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up development environment with UV
make uv-install

# Run all checks with UV
make uv-run-all
```

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

For detailed development setup, see the project's development documentation.

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