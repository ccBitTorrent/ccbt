# btbt CLI - Command Reference

**btbt** is the enhanced command-line interface for ccBitTorrent, providing comprehensive control over torrent operations, monitoring, configuration, and advanced features. For configuration options and overrides see [Configuration](configuration.md).

::: ccbt.cli.main.cli
    options:
      show_root_heading: false
      heading_level: 2

Entry point: `main` in `ccbt/cli/main.py`; CLI group above. Defined in [pyproject.toml](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml) (project.scripts).

## Quick reference

| Command / group | Description |
|-----------------|-------------|
| [download](#download) | Download from a torrent file |
| [magnet](#magnet) | Download from a magnet link (BEP 53 file selection supported) |
| [daemon](#daemon-commands) | Start/stop/status daemon |
| [dashboard](#dashboard) | Launch Bitonic TUI |
| [status](#status) | Show session status |
| [config](#config) | Show or edit configuration |
| [language](#language) | Set or show UI language |
| [checkpoints](#checkpoint-commands) | list, clean, delete, verify, export, backup, restore, migrate, reload, refresh |
| [resume](#resume) | Resume download from checkpoint |
| [resume-data](#resume-data) | resume-data save / resume-data verify (manage resume data) |
| [tonic](#tonic-commands) | Tonic create/link/sync/status (XET) |
| [alerts](#alerts) | List/add/remove alert rules |
| [metrics](#metrics) | Show Prometheus metrics |
| [files](#file-commands) | files list/select/deselect/priority |
| [interactive](#interactive) | Interactive CLI mode |
| [performance](#performance), [security](#security), [recover](#recover), [test](#test) | Advanced commands |

## Basic Commands

### download

Download a torrent file.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `download`

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

Network options (see [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_network_overrides`):
- `--listen-port <int>`: Listen port
- `--max-peers <int>`: Maximum global peers
- `--max-peers-per-torrent <int>`: Maximum peers per torrent
- `--pipeline-depth <int>`: Request pipeline depth
- `--block-size-kib <int>`: Block size in KiB
- `--connection-timeout <float>`: Connection timeout
- `--global-down-kib <int>`: Global download limit (KiB/s)
- `--global-up-kib <int>`: Global upload limit (KiB/s)

Disk options (see [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_disk_overrides`):
- `--hash-workers <int>`: Number of hash verification workers
- `--disk-workers <int>`: Number of disk I/O workers
- `--use-mmap`: Enable memory mapping
- `--no-mmap`: Disable memory mapping
- `--write-batch-kib <int>`: Write batch size in KiB
- `--write-buffer-kib <int>`: Write buffer size in KiB
- `--preallocate <str>`: Preallocation strategy (none|sparse|full)

Strategy options (see [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_strategy_overrides`):
- `--piece-selection <str>`: Piece selection strategy (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>`: Endgame duplicate requests
- `--endgame-threshold <float>`: Endgame threshold
- `--streaming`: Enable streaming mode

`--streaming` enables seek-aware sequential prioritization for playback-oriented downloads. In the Bitonic media tab, this is paired with a daemon-managed localhost HTTP range stream; playback itself remains external to the terminal UI, typically via VLC.

Discovery options (see [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_discovery_overrides`):
- `--enable-dht`: Enable DHT
- `--disable-dht`: Disable DHT
- `--enable-pex`: Enable PEX
- `--disable-pex`: Disable PEX
- `--enable-http-trackers`: Enable HTTP trackers
- `--disable-http-trackers`: Disable HTTP trackers
- `--enable-udp-trackers`: Enable UDP trackers
- `--disable-udp-trackers`: Disable UDP trackers

Observability options (see [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_observability_overrides`):
- `--log-level <str>`: Log level (DEBUG|TRACE|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>`: Log file path
- `--enable-metrics`: Enable metrics collection
- `--disable-metrics`: Disable metrics collection
- `--metrics-port <int>`: Metrics port
- `--metrics-interval <float>`: Metrics collection interval in seconds

### magnet

Download from a magnet link.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `magnet`

Magnet links support **BEP 53** file selection: if the magnet URI includes `so=` (selected indices) or `x.pe=` (prioritized indices), that selection is applied automatically after metadata is fetched. For interactive downloads, you can also choose files at the CLI or in the Bitonic file-selection dialog.

Usage:
```bash
uv run btbt magnet <magnet_link> [options]
```

Options: Same as `download` command, plus:

- `--select-files`: (Interactive only.) After adding the magnet, wait for metadata (up to a timeout), then show the file list and prompt for which files to download (`[a]ll`, `[n]one`, or indices like `0,2-5`). Applies selection via `file.select` / `file.deselect` before starting the interactive download.

### interactive

Start interactive CLI mode.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `interactive`

Usage:
```bash
uv run btbt interactive
```

Interactive CLI: [ccbt/cli/interactive.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/interactive.py) — `InteractiveCLI`

### status

Show current session status.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `status`

Usage:
```bash
uv run btbt status
```

## Checkpoint Commands

Checkpoint management group: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `checkpoints`

### checkpoints list

List all available checkpoints.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `list_checkpoints`

Usage:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Clean old checkpoints.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `clean_checkpoints`

Usage:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Delete a specific checkpoint.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `delete_checkpoint`

Usage:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Verify a checkpoint.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `verify_checkpoint_cmd`

Usage:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Export checkpoint to file.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `export_checkpoint_cmd`

Usage:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Backup checkpoint to location.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `backup_checkpoint_cmd`

Usage:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restore checkpoint from backup.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `restore_checkpoint_cmd`

Usage:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrate checkpoint between formats.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `migrate_checkpoint_cmd`

Usage:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Resume download from checkpoint.

Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `resume`

Usage:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

### resume-data {#resume-data}

Manage resume data and checkpoints. Subcommands: `resume-data save <info_hash>`, `resume-data verify <info_hash> [--verify-pieces N]`. Implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `resume_cmd`, `resume_save`, `resume_verify`.

## Monitoring Commands

Monitoring command group: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Start terminal monitoring dashboard (Bitonic).
This command requires daemon mode; local dashboard startup is intentionally unsupported.

Implementation: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py) — `dashboard`

Usage:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

`--no-daemon` is deprecated for the dashboard command.

See [Bitonic Guide](bitonic.md) for detailed usage.

For XET workspace sharing, treat `.tonic` files and `tonic?:` links as workspace sources and always choose an explicit output directory when joining a workspace. See [Getting Started — Quick start: XET shared workspace](getting-started.md#xet-quick-start) for a short workflow.

## XET Workspace Commands

All `tonic` subcommands are under the main CLI: `uv run btbt tonic <subcommand>`. Implementation: [ccbt/cli/tonic_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/tonic_commands.py).

### tonic create

Generate a `.tonic` file from a folder (and optionally a shareable `tonic?:` link).

Usage:
```bash
uv run btbt tonic create <folder_path> [--output <path>] [--sync-mode ...] [--generate-link]
```

- Use `--generate-link` to also print the `tonic?:` link. The folder is not registered with the daemon until you run `tonic sync` with that .tonic (or add it via the dashboard).

### tonic link

Generate a shareable `tonic?:` link from a folder or an existing `.tonic` file.

Usage:
```bash
uv run btbt tonic link <folder_path> [--tonic-file <path>] [--sync-mode ...]
```

### tonic sync

Start syncing a workspace from a `.tonic` file, a remote .tonic URL, or a `tonic?:` link.

`<tonic_input>` can be:

- **Local path** to a .tonic file (e.g. `./project.tonic`).
- **Remote URL** to a .tonic file (e.g. `https://example.com/workspace.tonic`). The client fetches the file from the URL then proceeds.
- **tonic?: link** (e.g. `tonic?:xt=urn:xet:<hash>&...`). If you have only the link (no .tonic file), the client discovers peers from the link (DHT and optional trackers/source peers), fetches workspace metadata from those peers via the XET extension, then starts syncing (cold link).

Usage:
```bash
uv run btbt tonic sync <tonic_input> [--output <dir>] [--check-interval <seconds>]
```

Behavior notes:
- Uses the executor/daemon runtime path instead of constructing a transient `XetFolder`.
- Returns a live `folder_key` and workspace identity for the registered runtime.
- When joining from a link or URL, provide an explicit output directory for materialization.

### tonic status

Show the status of a registered XET workspace.

Usage:
```bash
uv run btbt tonic status <folder_path>
```

Behavior notes:
- Reads the live runtime status through the executor/session path.
- Fails if the folder is not currently registered as an active XET workspace.
- Reports the runtime `folder_key` and `workspace_id` alongside sync metrics.

### tonic share (planned)

A single-command flow to register a folder with the daemon and print the shareable link is planned. See [XET share feature plan](implementation-plans/xet-share-feature.md).

### alerts

Manage alert rules and active alerts.

Implementation: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py) — `alerts`

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

Implementation: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py) — `metrics`

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

File selection command group: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py)

Manage file selection and priorities for multi-file torrents.

### files list

List all files in a torrent with their selection status, priorities, and download progress.

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_list`

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

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_select`

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

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_deselect`

Usage:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Select all files in the torrent.

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_select_all`

Usage:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Deselect all files in the torrent.

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_deselect_all`

Usage:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Set priority for a specific file.

Implementation: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py) — `files_priority`

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

The `config` command group is defined in [ccbt/cli/config_group.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_group.py). Core handlers live in [ccbt/cli/config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands.py); additional subcommands (schema, import, export, template, profile, backup, diff, auto-tune, etc.) are implemented in [ccbt/cli/config_commands_extended.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands_extended.py) and are **registered on the same** `btbt config` group (there is no separate `config-extended` CLI).

### config

Manage configuration (show, get, set, apply, describe, validate, migrate, reset, plus extended subcommands above).

Usage:
```bash
uv run btbt config --help
uv run btbt config describe --format table
uv run btbt config set network.listen_port 6882 --dry-run
```

See [Configuration Guide](configuration.md) for detailed configuration options.

## Advanced Commands

Advanced command group: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

### performance

Performance analysis and benchmarking.

Implementation: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py) — `performance`

Usage:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Security analysis and validation.

Implementation: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py) — `security`

Usage:
```bash
uv run btbt security [options]
```

### recover

Recovery operations.

Implementation: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py) — `recover`

Usage:
```bash
uv run btbt recover [options]
```

### test

Run tests and diagnostics.

Implementation: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py) — `test`

Usage:
```bash
uv run btbt test [options]
```

## Command Line Options

### Global Options

Global options defined in: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `cli`

- `--config <path>`: Configuration file path
- `--verbose/-v`: Verbose output (`-v`: info, `-vv`: debug, `-vvv`: trace)
- `--debug/-d`: Debug mode (deprecated alias for `-vv`)

### CLI Overrides

All CLI options override configuration in this order:
1. Defaults from [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
2. Configuration file ([ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml))
3. Environment variables ([env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example))
4. CLI arguments

Override implementation: [ccbt/cli/main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py) — `_apply_cli_overrides`

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

Implementation: [ccbt/cli/torrent_config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/torrent_config_commands.py)

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