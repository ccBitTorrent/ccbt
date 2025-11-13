# Getting Started

Welcome to ccBitTorrent! This guide will help you get up and running quickly with our high-performance BitTorrent client.

!!! tip "Key Feature: BEP XET Protocol Extension"
    ccBitTorrent includes the **Xet Protocol Extension (BEP XET)**, which enables content-defined chunking and cross-torrent deduplication. This transforms BitTorrent into a super-fast, updatable peer-to-peer file system optimized for collaboration. [Learn more about BEP XET →](bep_xet.md)

## Installation

### Prerequisites

- Python 3.8 or higher
- [UV](https://astral.sh/uv) package manager (recommended)

### Install UV

Install UV from the official installation script:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Install ccBitTorrent

Install from PyPI:
```bash
uv pip install ccbittorrent
```

Or install from source:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Entry points are defined in [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Main Entry Points

ccBitTorrent provides three main entry points:

### 1. Bitonic (Recommended)

**Bitonic** is the main terminal dashboard interface. It provides a live, interactive view of all torrents, peers, and system metrics.

- Entry point: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Defined in: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Launch: `uv run bitonic` or `uv run ccbt dashboard`

See [Bitonic Guide](bitonic.md) for detailed usage.

### 2. btbt CLI

**btbt** is the enhanced command-line interface with rich features.

- Entry point: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- Defined in: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Launch: `uv run btbt`

See [btbt CLI Reference](btbt-cli.md) for all available commands.

### 3. ccbt (Basic CLI)

**ccbt** is the basic command-line interface.

- Entry point: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- Defined in: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Launch: `uv run ccbt`

## Quick Start

### Launch Bitonic (Recommended)

Start the terminal dashboard:
```bash
uv run bitonic
```

Or via the CLI:
```bash
uv run ccbt dashboard
```

With custom refresh rate:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Download a Torrent

Using the CLI:
```bash
# Download from torrent file
uv run btbt download movie.torrent

# Download from magnet link
uv run btbt magnet "magnet:?xt=urn:btih:..."

# With rate limits
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

See [btbt CLI Reference](btbt-cli.md) for all download options.

### Configure ccBitTorrent

Create a `ccbt.toml` file in your working directory. Reference the example configuration:
- Default config: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Environment variables: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Configuration system: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

See [Configuration Guide](configuration.md) for detailed configuration options.

## Project Reports

View project quality metrics and reports:

- **Code Coverage**: [reports/coverage.md](reports/coverage.md) - Comprehensive code coverage analysis
- **Security Report**: [reports/bandit/index.md](reports/bandit/index.md) - Security scanning results from Bandit
- **Benchmarks**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Performance benchmark results

These reports are automatically generated and updated as part of our continuous integration process.

## Next Steps

- [Bitonic](bitonic.md) - Learn about the terminal dashboard interface
- [btbt CLI](btbt-cli.md) - Complete command-line interface reference
- [Configuration](configuration.md) - Detailed configuration options
- [Performance Tuning](performance.md) - Optimization guide
- [API Reference](API.md) - Python API documentation including monitoring features

## Getting Help

- Use `uv run bitonic --help` or `uv run btbt --help` for command help
- Check the [btbt CLI Reference](btbt-cli.md) for detailed options
- Visit our [GitHub repository](https://github.com/yourusername/ccbittorrent) for issues and discussions