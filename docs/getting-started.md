# Getting Started

Welcome to ccBitTorrent! This guide will help you get up and running quickly with our high-performance BitTorrent client.

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

## Your First Download

### Download from Torrent File

```bash
# Basic download
uv run ccbt download movie.torrent

# Download to specific directory
uv run ccbt download movie.torrent --output /path/to/downloads

# Download with rate limits
uv run ccbt download movie.torrent --download-limit 1024 --upload-limit 512
```

### Download from Magnet Link

```bash
# Download from magnet link
uv run ccbt magnet "magnet:?xt=urn:btih:..."

# With output directory
uv run ccbt magnet "magnet:?xt=urn:btih:..." --output /path/to/downloads
```

### Launch Terminal Dashboard

The Terminal Dashboard provides a live view of all your downloads:

```bash
# Start the dashboard
uv run ccbt dashboard

# With custom refresh rate
uv run ccbt dashboard --refresh 2.0
```

## Basic Usage Patterns

### Interactive Mode

For more control during downloads:

```bash
# Start interactive mode
uv run ccbt interactive

# Download with interactive interface
uv run ccbt download movie.torrent --interactive
```

### Resume Downloads

ccBitTorrent automatically saves your progress and can resume downloads:

```bash
# Resume from checkpoint (if available)
uv run ccbt download movie.torrent --resume

# List available checkpoints
uv run ccbt checkpoints list

# Resume specific checkpoint
uv run ccbt resume <info_hash>
```

### Monitor Downloads

```bash
# Show current status
uv run ccbt status

# Start monitoring mode
uv run ccbt download movie.torrent --monitor
```

## Configuration

### Basic Configuration

Create a `ccbt.toml` file in your working directory:

```toml
[network]
max_global_peers = 200
listen_port = 6881

[disk]
download_path = "/path/to/downloads"
preallocate = "full"

[limits]
global_down_kib = 0  # 0 = unlimited
global_up_kib = 0    # 0 = unlimited
```

### Environment Variables

You can also use environment variables:

```bash
export CCBT_MAX_PEERS=100
export CCBT_LISTEN_PORT=6881
export CCBT_DOWN_LIMIT=1024
export CCBT_UP_LIMIT=512
```

## Next Steps

- [CLI Reference](cli-reference.md) - Complete command reference
- [Terminal Dashboard](dashboard-guide.md) - Dashboard features and usage
- [Configuration](configuration.md) - Detailed configuration options
- [Monitoring](monitoring.md) - Observability and metrics
- [Checkpoints](checkpoints.md) - Resume functionality

## Getting Help

- Use `uv run ccbt --help` for general help
- Use `uv run ccbt <command> --help` for command-specific help
- Check the [CLI Reference](cli-reference.md) for detailed options
- Visit our [GitHub repository](https://github.com/yourusername/ccbittorrent) for issues and discussions
