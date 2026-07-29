# ccBitTorrent - High-Performance BitTorrent Client

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## Features

### Performance Optimizations
- **Async I/O**: Full asyncio implementation for superior concurrency. See [ccbt/session/async_main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/async_main.py)
- **Rarest-First Selection**: Intelligent piece selection for optimal swarm health. See [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)
- **Endgame Mode**: Duplicate requests for faster completion
- **Request Pipelining**: Deep request queues (16-64 outstanding requests per peer). See [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)
- **Tit-for-Tat Choking**: Fair bandwidth allocation with optimistic unchoke
- **Parallel Metadata**: Concurrent ut_metadata fetching from multiple peers. See [ccbt/piece/async_metadata_exchange.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py)
- **Disk I/O Optimization**: File preallocation, write batching, ring-buffer staging, memory-mapped I/O, io_uring/direct I/O (configurable). See [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)
- **Hash Verification Pool**: Parallel SHA-1 verification across worker threads

### Advanced Configuration
- **TOML Configuration**: Comprehensive config system with hot-reload. See [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
- **Per-Torrent Settings**: Individual torrent configuration overrides
- **Rate Limiting**: Global and per-torrent upload/download limits. See [ccbt.toml:38-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- **Strategy Selection**: Round-robin, rarest-first, or sequential piece selection. See [ccbt.toml:100-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- **Streaming Mode**: Priority-based piece selection for media files

### Network Features
- **UDP Tracker Support**: BEP 15 compliant UDP tracker communication. See [ccbt/discovery/tracker_udp_client.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py)
- **Enhanced DHT**: Full Kademlia routing table with iterative lookups. See [ccbt/discovery/dht.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/dht.py)
- **Peer Exchange (PEX)**: BEP 11 compliant peer discovery. See [ccbt/discovery/pex.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/pex.py)
- **Connection Management**: Adaptive peer selection and connection limits. See [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py)
- **Protocol Optimizations**: Memory-efficient message handling with zero-copy paths

## Xet Protocol Extension (BEP XET)

The Xet Protocol Extension is a key differentiator that transforms BitTorrent into a super-fast, updatable peer-to-peer file system optimized for collaboration. BEP XET enables:

- **Content-Defined Chunking**: Gearhash-based intelligent file segmentation (8KB-128KB chunks) for efficient updates. See [ccbt/storage/xet_chunking.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py)
- **Cross-Torrent Deduplication**: Chunk-level deduplication across multiple torrents. See [ccbt/storage/xet_deduplication.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py)
- **Peer-to-Peer CAS**: Decentralized Content Addressable Storage using DHT and trackers. See [ccbt/discovery/xet_cas.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py)
- **Super-Fast Updates**: Only changed chunks need redistribution, enabling rapid collaborative file sharing
- **P2P File System**: Transform BitTorrent into an updatable peer-to-peer file system optimized for collaboration
- **Merkle Tree Verification**: BLAKE3-256 hashing with SHA-256 fallback for integrity. See [ccbt/storage/xet_hashing.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py)

[Learn more about BEP XET →](bep_xet.md)

### Observability
- **Metrics Export**: Prometheus-compatible metrics for monitoring. See [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- **Structured Logging**: Configurable logging with per-peer tracing. See [ccbt/utils/logging_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/logging_config.py)
- **Performance Stats**: Real-time throughput, latency, and queue depth tracking
- **Health Monitoring**: Connection quality and peer reliability scoring
- **Terminal Dashboard**: Textual-based live dashboard (Bitonic). See [ccbt/interface/terminal_dashboard.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)
- **Alert Manager**: Rule-based alerts with persistence and testing via CLI. See [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)

## Quick Start

### Installation with UV

Install UV from [astral.sh/uv](https://astral.sh/uv), then install ccBitTorrent:

Entry points are defined in [pyproject.toml](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml) (project.scripts). **Bitonic:** `uv run bitonic` or `uv run ccbt dashboard`. **btbt CLI:** `uv run btbt`. **ccbt:** `uv run ccbt`. See [Getting Started](getting-started.md) for details.

## Documentation

- [BEP XET](bep_xet.md) - Xet Protocol Extension for content-defined chunking and deduplication
- [Getting Started](getting-started.md) - Installation and first steps
- [Bitonic](bitonic.md) - Terminal dashboard (main interface)
- [btbt CLI](btbt-cli.md) - Command-line interface reference
- [Configuration](configuration.md) - Configuration options and setup
- [Performance Tuning](performance.md) - Optimization guide
- [ccBT API Reference](API.md) - Python API documentation
- [Contributing](contributing.md) - How to contribute
- [Funding](funding.md) - Support the project

## License

This project is licensed under the **GNU General Public License v2 (GPL-2.0)** - see [license.md](license.md) for details.

Additionally, this project is subject to additional use restrictions under the **ccBT RAIL-AMS License** - see [ccBT-RAIL.md](ccBT-RAIL.md) for the complete terms and use restrictions.

**Important**: Both licenses apply to this software. You must comply with all terms and restrictions in both the GPL-2.0 license and the RAIL license.

## Reports

View project reports in the documentation:
- [Coverage Reports](reports/coverage.md) - Code coverage analysis
- [Bandit Security Report](reports/bandit/index.md) - Security scanning results
- [Benchmarks](reports/benchmarks/index.md) - Performance benchmark results

## Acknowledgments

- BitTorrent protocol specification (BEP 5, 10, 11, 15, 52)
- Xet protocol for content-defined chunking inspiration
- Python asyncio for high-performance I/O
- The BitTorrent community for protocol development