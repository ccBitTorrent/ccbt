# Getting Started

Welcome to ccBitTorrent! This guide will help you get up and running quickly with our high-performance BitTorrent client. For the TUI dashboard see [Bitonic](bitonic.md); for the full CLI see [btbt CLI](btbt-cli.md).

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
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
uv pip install -e .
```

Entry points are defined in [pyproject.toml](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml). **Bitonic** (recommended): `uv run bitonic` or `uv run ccbt dashboard` — see [Bitonic Guide](bitonic.md). **btbt CLI:** `uv run btbt` — see [btbt CLI Reference](btbt-cli.md). **ccbt:** `uv run ccbt`.

## Quick Start

### Start the Daemon {#start-daemon}

ccBitTorrent can run in daemon mode for background operation, or locally for single-session downloads.

**Start the daemon (recommended for multiple torrents):**
```bash
# Start daemon in background
uv run btbt daemon start

# Start daemon in foreground (for debugging)
uv run btbt daemon start --foreground

# Check daemon status
uv run btbt daemon status
```

The daemon runs in the background and manages all torrent sessions. CLI commands automatically connect to the daemon when it's running.

**Run locally (without daemon):**
```bash
# Commands will run in local mode if daemon is not running
uv run btbt download movie.torrent
```

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

### Download a Torrent {#download-torrent}

Using the CLI:
```bash
# Download from torrent file
uv run btbt download movie.torrent

# Download from magnet link
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Magnet with interactive file selection (wait for metadata, then choose files)
uv run btbt magnet "magnet:?xt=urn:btih:..." --interactive --select-files

# With rate limits
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512

# Resume from checkpoint
uv run btbt download movie.torrent --resume
```

See [btbt CLI Reference](btbt-cli.md) for all download options.

### Quick start: XET shared workspace {#xet-quick-start}

XET lets you sync folders over the BitTorrent network (content-defined chunking, P2P discovery). Use it to **share** a folder (get a link and start syncing) or **join** someone else's workspace.

**Prerequisites:** Start the daemon and enable XET:

```bash
uv run btbt daemon start
uv run ccbt xet enable
```

**Share a folder (create link and start syncing):**

```bash
# 1. Generate a .tonic file and shareable tonic?: link
uv run btbt tonic create ./my-project --generate-link

# 2. Register the folder with the daemon so it is watched and synced (choose one):
#    - Sync from the .tonic into the same folder (registers the workspace):
uv run btbt tonic sync ./my-project.tonic --output ./my-project
#    - Or add the folder via the Bitonic dashboard (XET / folder sync screen)
```

**Join a workspace from a link or .tonic file:**

```bash
# From a tonic?: link (share this format with others)
uv run btbt tonic sync "tonic?:xt=urn:xet:..." --output ./joined-workspace

# From a .tonic file (local path)
uv run btbt tonic sync ./project.tonic --output ./project-copy

# From a remote .tonic URL (http or https)
uv run btbt tonic sync "https://example.com/workspace.tonic" --output ./joined-workspace
```

Always specify an explicit `--output` directory when joining.

**Joining from a tonic?: link only (cold link):** If you have only the link and no .tonic file, the client will discover peers (using DHT and any trackers or source peers in the link), fetch the workspace metadata from those peers via the XET extension, then start syncing. Ensure the daemon is running and at least one peer for that workspace is reachable.

**Joining from a remote URL:** You can pass an `http://` or `https://` URL to a .tonic file; the client fetches the file from the URL and then proceeds as with a local .tonic path.

**Check sync status:**

```bash
uv run btbt tonic status ./my-project
```

**Other XET commands:**

```bash
# Generate shareable link from folder or .tonic file
uv run btbt tonic link ./my-project
uv run btbt tonic link ./my-project --tonic-file ./my-project.tonic

# XET protocol status and cache
uv run ccbt xet status
uv run ccbt xet stats
```

See [BEP XET](bep_xet.md) for protocol details, configuration, and the full CLI reference in [btbt CLI](btbt-cli.md#xet-workspace-commands). A one-command **share** flow (watch folder + get link in a single step) is planned; see [XET share feature plan](implementation-plans/xet-share-feature.md) for details.

### Configure ccBitTorrent {#configure}

Create a `ccbt.toml` file in your working directory. Reference the example configuration:
- Default config: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Environment variables: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Configuration system: [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

!!! warning "Windows Path Resolution"
    On Windows, daemon-related paths (PID files, state directories) use `_get_daemon_home_dir()` helper from `ccbt/daemon/daemon_manager.py` for consistent path resolution, especially with spaces in usernames. See [Configuration Guide - Windows Path Resolution](configuration.md#daemon-home-dir) for details.

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
- Visit our [GitHub repository](https://github.com/ccBittorrent/ccbt) for issues and discussions