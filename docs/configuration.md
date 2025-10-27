# Configuration Guide

This guide explains configuration for ccBitTorrent, how to override values, and example setups.

## Sources and Precedence
- Defaults (compiled)
- TOML file (ccbt.toml in project or ~/.config/ccbt/ccbt.toml)
- Environment variables (CCBT_*)
- CLI options (download/magnet)

## Sections
- network: peers, pipeline, block sizes, encryption, IPv6, TCP/uTP
- disk: preallocation, batching, mmap, io_uring, direct I/O, checkpointing
- discovery: DHT, trackers, PEX
- strategy: piece selection, endgame
- observability: logging, metrics, alerts
- limits: global and per-scope limits
- security: validation, encryption, rate limiting

## Environment Variables (examples)
- CCBT_LISTEN_PORT=6881
- CCBT_MAX_PEERS=200
- CCBT_USE_MMAP=true
- CCBT_ENABLE_DHT=true

## Example (basic)
```toml
[network]
listen_port = 6881
max_global_peers = 200
pipeline_depth = 16
block_size_kib = 16

[disk]
preallocate = "full"
write_batch_kib = 64
write_buffer_kib = 1024
use_mmap = true

[discovery]
enable_dht = true

[strategy]
piece_selection = "rarest_first"

[observability]
log_level = "INFO"
enable_metrics = true
```

## Tips
- Increase disk.write_buffer_kib for large sequential writes
- Enable direct I/O on Linux/NVMe for better write throughput
- Tune pipeline_depth and block_size_kib for your network
