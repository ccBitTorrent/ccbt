# CLI Reference

## Main Commands
- download <torrent_file> [options]
- magnet <magnet_link> [options]
- interactive
- status
- checkpoints (list, clean, delete, verify, export, backup, restore, migrate)
- monitoring: dashboard, alerts, metrics
- advanced: performance, security, recover, test

## Common Options (download/magnet)
- --listen-port <int>
- --max-peers <int>
- --pipeline-depth <int>
- --block-size-kib <int>
- --hash-workers <int>
- --disk-workers <int>
- --use-mmap / --no-mmap
- --write-batch-kib <int>
- --write-buffer-kib <int>
- --preallocate [none|sparse|full]
- --enable-dht / --disable-dht
- --piece-selection [round_robin|rarest_first|sequential]
- --download-limit / --upload-limit
- --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]

## Examples
```bash
ccbt download test.torrent --listen-port 7001 --enable-dht --use-mmap
ccbt magnet "magnet:?xt=urn:btih:..." --download-limit 1024 --upload-limit 256
ccbt checkpoints list --format json
ccbt checkpoints export <infohash> --format json --output checkpoint.json
ccbt performance --analyze --benchmark
ccbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning
ccbt metrics --format json --include-system --include-performance
```
