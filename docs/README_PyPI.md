# ccBitTorrent

[![PyPI version](https://badge.fury.io/py/ccbt.svg)](https://badge.fury.io/py/ccbt)
[![Downloads](https://pepy.tech/badge/ccbt)](https://pepy.tech/project/ccbt)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## Installation

### Using UV (Recommended)

```bash
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ccBitTorrent
uv pip install ccbt
```

### Using pip

```bash
pip install ccbt
```

## Quick Start

### Basic Usage

```bash
# Download from torrent file
ccbt download movie.torrent

# Download from magnet link
ccbt magnet "magnet:?xt=urn:btih:..."

# Launch Terminal Dashboard (Recommended)
bitonic
```

### Enhanced CLI

```bash
# Use the enhanced CLI with rich features
btbt download movie.torrent

# Interactive mode
btbt interactive

# View dashboard
btbt dashboard
```

## Features

- **Async I/O**: Full asyncio implementation for superior concurrency
- **Rarest-First Selection**: Intelligent piece selection for optimal swarm health
- **Endgame Mode**: Duplicate requests for faster completion
- **Request Pipelining**: Deep request queues (16-64 outstanding requests per peer)
- **Parallel Metadata**: Concurrent ut_metadata fetching from multiple peers
- **Disk I/O Optimization**: File preallocation, write batching, memory-mapped I/O
- **Hash Verification Pool**: Parallel SHA-1 verification across worker threads
- **Terminal Dashboard**: Beautiful Textual-based live dashboard
- **Comprehensive Monitoring**: Prometheus metrics, structured logging, alerts

## Configuration

Create a `ccbt.toml` file in your working directory or `~/.config/ccbt/`:

```toml
[network]
max_global_peers = 200
max_peers_per_torrent = 50
pipeline_depth = 16

[disk]
preallocate = "full"
write_batch_kib = 64
use_mmap = true
hash_workers = 4

[strategy]
piece_selection = "rarest_first"
endgame_duplicates = 2
```

## Documentation

- **Full Documentation**: https://ccbittorrent.readthedocs.io/
- **GitHub Repository**: https://github.com/ccBittorrent/ccbt
- **Issue Tracker**: https://github.com/ccBittorrent/ccbt/issues

## Requirements

- Python 3.8 or higher
- UV package manager (recommended) or pip

## License

This project is licensed under the **GNU General Public License v2 (GPL-2.0)**.

Additionally, this project is subject to additional use restrictions under the **ccBT RAIL-AMS License**.

**Important**: Both licenses apply to this software. You must comply with all terms and restrictions in both licenses.

## Support

- **Documentation**: https://ccbittorrent.readthedocs.io/
- **Issues**: https://github.com/ccBittorrent/ccbt/issues
- **Discussions**: https://github.com/ccBittorrent/ccbt/discussions

