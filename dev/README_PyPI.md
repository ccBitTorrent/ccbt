# ccBitTorrent

[![PyPI version](https://badge.fury.io/py/ccbt.svg)](https://badge.fury.io/py/ccbt)
[![Downloads](https://pepy.tech/badge/ccbt)](https://pepy.tech/project/ccbt)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

A modern, high-performance BitTorrent client.

## Installation

```bash
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ccBitTorrent
uv pip install ccbt
```

## Quick Start

### Basic Usage

```bash

# Launch Terminal Dashboard (Recommended)
bitonic
```

### Enhanced CLI

```bash
# Download from torrent file
ccbt download movie.torrent

# Download from magnet link
ccbt magnet "magnet:?xt=urn:btih:..."

```bash
# Interactive mode
btbt interactive

# View dashboard
btbt dashboard
```

## Configuration

it's quicker to use the presets 👇🏻

### Presets 

- **example env**: https://ccbittorrent.readthedocs.io/
- **example toml**: https://ccbittorrent.readthedocs.io/
- **presets**:

### Manual

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

