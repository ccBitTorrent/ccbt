# btbt CLI - Command Reference

**btbt** is the enhanced command-line interface for ccBitTorrent, providing comprehensive control over torrent operations, monitoring, configuration, and advanced features.

- Entry point: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- Defined in: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Main CLI group: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

## Basic Commands

### download

Download a torrent file.

Implementation: [ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)

Usage:
```bash
uv run btbt download <torrent_file> [options]
```

Options:
- `--output <dir>`: Output directory
- `--interactive`: Interactive mode
- `--monitor`: Monitor mode
- `--resume`: Resume from checkpoint
- `--no-checkpoint`: Disable checkpointing
- `--checkpoint-dir <dir>`: Checkpoint directory
- `--files <indices...>`: Select specific files to download (can specify multiple times, e.g., `--files 0 --files 1`)
- `--file-priority <spec>`: Set file priority as `file_index=priority` (e.g., `0=high,1=low`). Can specify multiple times.

Network options (see [ccbt/cli/main.py:_apply_network_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L67)):
- `--listen-port <int>`: Listen port
- `--max-peers <int>`: Maximum global peers
- `--max-peers-per-torrent <int>`: Maximum peers per torrent
- `--pipeline-depth <int>`: Request pipeline depth
- `--block-size-kib <int>`: Block size in KiB
- `--connection-timeout <float>`: Connection timeout
- `--global-down-kib <int>`: Global download limit (KiB/s)
- `--global-up-kib <int>`: Global upload limit (KiB/s)

Disk options (see [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L179)):
- `--hash-workers <int>`: Number of hash verification workers
- `--disk-workers <int>`: Number of disk I/O workers
- `--use-mmap`: Enable memory mapping
- `--no-mmap`: Disable memory mapping
- `--write-batch-kib <int>`: Write batch size in KiB
- `--write-buffer-kib <int>`: Write buffer size in KiB
- `--preallocate <str>`: Preallocation strategy (none|sparse|full)

Strategy options (see [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L151)):
- `--piece-selection <str>`: Piece selection strategy (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>`: Endgame duplicate requests
- `--endgame-threshold <float>`: Endgame threshold
- `--streaming`: Enable streaming mode

Discovery options (see [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L123)):
- `--enable-dht`: Enable DHT
- `--disable-dht`: Disable DHT
- `--enable-pex`: Enable PEX
- `--disable-pex`: Disable PEX
- `--enable-http-trackers`: Enable HTTP trackers
- `--disable-http-trackers`: Disable HTTP trackers
- `--enable-udp-trackers`: Enable UDP trackers
- `--disable-udp-trackers`: Disable UDP trackers

Observability options (see [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L217)):
- `--log-level <str>`: Log level (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>`: Log file path
- `--enable-metrics`: Enable metrics collection
- `--disable-metrics`: Disable metrics collection
- `--metrics-port <int>`: Metrics port

### magnet

Download from a magnet link.

Implementation: [ccbt/cli/main.py:magnet](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L608)

Usage:
```bash
uv run btbt magnet <magnet_link> [options]
```

Options: Same as `download` command.

### interactive

Start interactive CLI mode.

Implementation: [ccbt/cli/main.py:interactive](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L767)

Usage:
```bash
uv run btbt interactive
```

Interactive CLI: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/interactive.py#L41)

### status

Show current session status.

Implementation: [ccbt/cli/main.py:status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L789)

Usage:
```bash
uv run btbt status
```

## Checkpoint Commands

Checkpoint management group: [ccbt/cli/main.py:checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

List all available checkpoints.

Implementation: [ccbt/cli/main.py:list_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L863)

Usage:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Clean old checkpoints.

Implementation: [ccbt/cli/main.py:clean_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L930)

Usage:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Delete a specific checkpoint.

Implementation: [ccbt/cli/main.py:delete_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L978)

Usage:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Verify a checkpoint.

Implementation: [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1016)

Usage:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Export checkpoint to file.

Implementation: [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1058)

Usage:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Backup checkpoint to location.

Implementation: [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1099)

Usage:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restore checkpoint from backup.

Implementation: [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1138)

Usage:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrate checkpoint between formats.

Implementation: [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1173)

Usage:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Resume download from checkpoint.

Implementation: [ccbt/cli/main.py:resume](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1204)

Usage:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## Monitoring Commands

Monitoring command group: [ccbt/cli/monitoring_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Start terminal monitoring dashboard (Bitonic).

Implementation: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L20)

Usage:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

See [Bitonic Guide](bitonic.md) for detailed usage.

### alerts

Manage alert rules and active alerts.

Implementation: [ccbt/cli/monitoring_commands.py:alerts](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L48)

Usage:
```bash
# List alert rules
uv run btbt alerts --list

# List active alerts
uv run btbt alerts --list-active

# Add alert rule
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# Remove alert rule
uv run btbt alerts --remove --name <name>

# Clear all active alerts
uv run btbt alerts --clear-active

# Test alert rule
uv run btbt alerts --test --name <name> --value <value>

# Load rules from file
uv run btbt alerts --load <path>

# Save rules to file
uv run btbt alerts --save <path>
```

See the [API Reference](API.md#monitoring) for more information.

### metrics

Collect and export metrics.

Implementation: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)

Usage:
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

Examples:
```bash
# Export JSON metrics
uv run btbt metrics --format json --include-system --include-performance

# Export Prometheus format
uv run btbt metrics --format prometheus > metrics.txt
```

See the [API Reference](API.md#monitoring) for more information.

## File Selection Commands

File selection command group: [ccbt/cli/file_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py)

Manage file selection and priorities for multi-file torrents.

### files list

List all files in a torrent with their selection status, priorities, and download progress.

Implementation: [ccbt/cli/file_commands.py:files_list](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L28)

Usage:
```bash
uv run btbt files list <info_hash>
```

Output includes:
- File index and name
- File size
- Selection status (selected/deselected)
- Priority level
- Download progress

### files select

Select one or more files for download.

Implementation: [ccbt/cli/file_commands.py:files_select](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L72)

Usage:
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

Examples:
```bash
# Select files 0, 2, and 5
uv run btbt files select abc123... 0 2 5

# Select single file
uv run btbt files select abc123... 0
```

### files deselect

Deselect one or more files from download.

Implementation: [ccbt/cli/file_commands.py:files_deselect](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L108)

Usage:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Select all files in the torrent.

Implementation: [ccbt/cli/file_commands.py:files_select_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L144)

Usage:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Deselect all files in the torrent.

Implementation: [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L161)

Usage:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Set priority for a specific file.

Implementation: [ccbt/cli/file_commands.py:files_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L178)

Usage:
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

Priority levels:
- `do_not_download`: Do not download (equivalent to deselected)
- `low`: Low priority
- `normal`: Normal priority (default)
- `high`: High priority
- `maximum`: Maximum priority

Examples:
```bash
# Set file 0 to high priority
uv run btbt files priority abc123... 0 high

# Set file 2 to maximum priority
uv run btbt files priority abc123... 2 maximum
```

## Configuration Commands

Configuration command group: [ccbt/cli/config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands.py)

### config

Manage configuration.

Implementation: [ccbt/cli/main.py:config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L810)

Usage:
```bash
uv run btbt config [subcommand]
```

Extended configuration commands: [ccbt/cli/config_commands_extended.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands_extended.py)

See [Configuration Guide](configuration.md) for detailed configuration options.

## Advanced Commands

Advanced command group: [ccbt/cli/advanced_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py)

### performance

Performance analysis and benchmarking.

Implementation: [ccbt/cli/advanced_commands.py:performance](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L73)

Usage:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Security analysis and validation.

Implementation: [ccbt/cli/advanced_commands.py:security](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L170)

Usage:
```bash
uv run btbt security [options]
```

### recover

Recovery operations.

Implementation: [ccbt/cli/advanced_commands.py:recover](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L209)

Usage:
```bash
uv run btbt recover [options]
```

### test

Run tests and diagnostics.

Implementation: [ccbt/cli/advanced_commands.py:test](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L248)

Usage:
```bash
uv run btbt test [options]
```

## Command Line Options

### Global Options

Global options defined in: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

- `--config <path>`: Configuration file path
- `--verbose`: Verbose output
- `--debug`: Debug mode

### CLI Overrides

All CLI options override configuration in this order:
1. Defaults from [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)
2. Configuration file ([ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml))
3. Environment variables ([env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example))
4. CLI arguments

Override implementation: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)

## Examples

### Basic Download
```bash
uv run btbt download movie.torrent
```

### Download with Options
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### Selective File Download
```bash
# Download only specific files
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# Download with file priorities
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# Combined: select files and set priorities
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### Download from Magnet
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### File Selection Management
```bash
# List files in a torrent
uv run btbt files list abc123def456789...

# Select specific files after download starts
uv run btbt files select abc123... 3 4

# Set file priorities
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# Select/deselect all files
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### Checkpoint Management
```bash
# List checkpoints
uv run btbt checkpoints list --format json

# Export checkpoint
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# Clean old checkpoints
uv run btbt checkpoints clean --days 7
```

### Per-Torrent Configuration

Manage per-torrent configuration options and rate limits. These settings are persisted in checkpoints and daemon state.

Implementation: [ccbt/cli/torrent_config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/torrent_config_commands.py)

#### Set Per-Torrent Option

Set a configuration option for a specific torrent:

```bash
uv run btbt torrent config set <info_hash> <key> <value> [--save-checkpoint]
```

Examples:
```bash
# Set piece selection strategy
uv run btbt torrent config set abc123... piece_selection sequential

# Enable streaming mode
uv run btbt torrent config set abc123... streaming_mode true

# Set max peers per torrent
uv run btbt torrent config set abc123... max_peers_per_torrent 50

# Set option and save checkpoint immediately
uv run btbt torrent config set abc123... piece_selection rarest_first --save-checkpoint
```

#### Get Per-Torrent Option

Get a configuration option value for a specific torrent:

```bash
uv run btbt torrent config get <info_hash> <key>
```

Example:
```bash
uv run btbt torrent config get abc123... piece_selection
```

#### List All Per-Torrent Config

List all configuration options and rate limits for a torrent:

```bash
uv run btbt torrent config list <info_hash>
```

Example:
```bash
uv run btbt torrent config list abc123...
```

Output shows:
- All per-torrent options (piece_selection, streaming_mode, etc.)
- Rate limits (download/upload in KiB/s)

#### Reset Per-Torrent Config

Reset configuration options for a torrent:

```bash
uv run btbt torrent config reset <info_hash> [--key <key>]
```

Examples:
```bash
# Reset all per-torrent options
uv run btbt torrent config reset abc123...

# Reset a specific option
uv run btbt torrent config reset abc123... --key piece_selection
```

**Note**: Per-torrent configuration options are automatically saved to checkpoints when checkpoints are created. Use `--save-checkpoint` with `set` to immediately persist changes. These settings are also persisted in daemon state when running in daemon mode.

### Monitoring
```bash
# Start dashboard
uv run btbt dashboard --refresh 2.0

# Add alert rule
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# Export metrics
uv run btbt metrics --format json --include-system --include-performance
```

## Getting Help

Get help for any command:
```bash
uv run btbt --help
uv run btbt <command> --help
```

For more information:
- [Bitonic Guide](bitonic.md) - Terminal dashboard
- [Configuration Guide](configuration.md) - Configuration options
- [API Reference](API.md#monitoring) - Monitoring and metrics
- [Performance Tuning](performance.md) - Optimization guide