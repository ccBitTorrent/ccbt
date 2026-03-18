# Configuration Guide

ccBitTorrent uses a comprehensive configuration system with TOML support, validation, hot-reload, and hierarchical loading from multiple sources. The btbt CLI applies overrides via command-line options; see [btbt CLI](btbt-cli.md). For tuning guidance see [Performance Tuning](performance.md).

Configuration system: **ConfigManager** in [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L85). Use the reference below for source links.

::: ccbt.config.config.ConfigManager
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      filters:
        - "!^_"

## Quick reference (ccbt.toml sections)

| Section | Description | Model (ccbt/models.py) |
|---------|-------------|-------------------------|
| `[network]` | Connection limits, pipeline, timeouts, listen ports, rate limits, connection pool, circuit breaker, socket tuning | `NetworkConfig` |
| `[plugins]` | Enable/auto-load plugins, plugin directories | `PluginsConfig` |
| `[disk]` | Preallocation, write/hash/disk workers, checkpoint, resume | `DiskConfig` |
| `[xet_sync]` | XET sync enable, check interval, sync mode, gossip, consensus | `XetSyncConfig` |
| `[strategy]` | Piece selection, endgame, streaming, priorities | `StrategyConfig` |
| `[discovery]` | DHT, PEX, trackers, handshake timeouts, aggressive discovery | `DiscoveryConfig` |
| `[observability]` | Logging, metrics, alerts, event bus | `ObservabilityConfig` |
| `[limits]` | Global/per-torrent/per-peer rate limits, scheduler | `LimitsConfig` |
| `[security]` | Encryption, peer validation, rate limit | `SecurityConfig` |
| `[proxy]` | HTTP proxy for trackers/peers/webseeds | `ProxyConfig` |
| `[ml]` | Peer selection and piece prediction (ML) | `MLConfig` |
| `[dashboard]` | Metrics dashboard and terminal refresh | `DashboardConfig` |
| `[queue]` | Active torrent limits, priority, bandwidth allocation | `QueueConfig` |
| `[ui]` | Locale | `UIConfig` |
| `[nat]` | NAT-PMP, UPnP, port mapping | `NATConfig` |
| `[daemon]` | IPC host/port for daemon | `DaemonConfig` |
| `[webtorrent]` | WebTorrent enable, port, host | (see webtorrent config) |
| `[network.utp]` | µTP transport tuning | (nested under network) |
| `[network.protocol_v2]` | Protocol v2 options | (nested under network) |
| `[plugins.metrics]` | Metrics plugin options | `MetricsPluginConfig` |
| `[disk.attributes]` | Disk attribute options | (nested under disk) |
| `[disk.xet]` | XET disk options | (nested under disk) |
| `[security.ip_filter]` | IP filter rules | `IPFilterConfig` |
| `[security.blacklist]` | Peer blacklist | `BlacklistConfig` |
| `[security.ssl]` | SSL/TLS options | `SSLConfig` |
| `[security.blacklist.local_source]` | Local blacklist source | (nested under security) |

## Configuration Sources and Precedence

Configuration is loaded in this order (later sources override earlier ones):

1. **Defaults**: Built-in sensible defaults from [ccbt/models.py:Config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)
2. **Config File**: `ccbt.toml` in current directory or `~/.config/ccbt/ccbt.toml`. See [ccbt/config/config.py:_find_config_file](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L107)
3. **Environment Variables**: `CCBT_*` prefixed variables. See [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
4. **CLI Arguments**: Command-line overrides. See [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/overrides.py#L17) {#cli-overrides}
5. **Per-Torrent Defaults**: Global defaults for per-torrent options. See [Per-Torrent Configuration](#per-torrent-configuration) section
6. **Per-Torrent Overrides**: Individual torrent settings (set via CLI, TUI, or programmatically)

Configuration loading: [ccbt/config/config.py:_load_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L128)

### Windows Path Resolution {#daemon-home-dir}

**CRITICAL**: Use `_get_daemon_home_dir()` helper from `ccbt/daemon/daemon_manager.py` for all daemon-related paths.

**Why**: Windows can resolve `Path.home()` or `os.path.expanduser("~")` differently in different processes, especially with spaces in usernames.

**Pattern**: Helper tries multiple methods (`expanduser`, `USERPROFILE`, `HOME`, `Path.home()`) and uses `Path.resolve()` for canonical path.

**Usage**: Always use helper instead of direct `Path.home()` or `os.path.expanduser("~")` for daemon PID files, state directories, config files.

**Files affected**: `DaemonManager`, `StateManager`, `IPCClient`, any code that reads/writes daemon PID file or state.

**Result**: Ensures daemon and CLI use same canonical path, preventing detection failures.

::: ccbt.daemon.daemon_manager.DaemonManager
    options:
      show_root_heading: false
      heading_level: 3

## Configuration File

### Default Configuration

Reference the default configuration file: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

The configuration is organized into sections:

### Network Configuration

Network settings: section `[network]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Covers connection limits, pipeline depth, block sizes, socket buffers, timeouts, listen ports (TCP/UDP/XET), transport (TCP/UTP/encryption), rate limits, choking, tracker timeouts, connection pool, circuit breaker, socket tuning, and pipeline tuning.

Network config model: `NetworkConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Plugins Configuration

Section `[plugins]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): `enable_plugins`, `auto_load_plugins`, `plugin_directories`. Model: `PluginsConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Disk Configuration

Disk settings: section `[disk]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Preallocation, write batch/buffer, MMAP, hash workers, disk workers, cache, direct I/O, sync writes, read-ahead, io_uring, download path, checkpoint and resume options. Nested: `[disk.attributes]`, `[disk.xet]`.

Disk config model: `DiskConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### XET Sync Configuration

Section `[xet_sync]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): XET enable, check interval, default sync mode, git versioning, LPD, gossip, consensus, conflict resolution. Model: `XetSyncConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Strategy Configuration

Strategy settings: section `[strategy]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Piece selection, endgame, streaming mode, rarest-first/sequential options, pipeline capacity, piece priorities.

Strategy config model: `StrategyConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Discovery Configuration

Discovery settings: section `[discovery]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). DHT (port, bootstrap, IPv6, storage, indexing), PEX, HTTP/UDP trackers, announce/scrape intervals, handshake and DHT timeouts, aggressive discovery. Key options: `min_peers_before_dht`, `dht_enable_storage`, `tracker_announce_interval`, `tracker_scrape_interval`, `tracker_auto_scrape`. Environment variables: `CCBT_MIN_PEERS_BEFORE_DHT`, `CCBT_DHT_ENABLE_STORAGE`, `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`.

Discovery config model: `DiscoveryConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Limits Configuration

Rate limits: section `[limits]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Global and per-torrent/per-peer limits, scheduler slice.

Limits config model: `LimitsConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Observability Configuration

Observability settings: section `[observability]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Log level, log file, metrics port/interval, event bus, alerts rules path.

Observability config model: `ObservabilityConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Optimization Configuration {#optimization-profile}

Optimization profiles provide pre-configured settings for different use cases.

::: ccbt.models.OptimizationProfile
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3

**Available Profiles:**
- `BALANCED`: Balanced performance and resource usage (default)
- `SPEED`: Maximum download speed
- `EFFICIENCY`: Maximum bandwidth efficiency
- `LOW_RESOURCE`: Optimized for low-resource systems
- `CUSTOM`: Use custom settings without profile overrides

Optimization config model: [ccbt/models.py:OptimizationConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Security Configuration

Security settings: section `[security]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Nested: `[security.ip_filter]`, `[security.blacklist]`, `[security.ssl]`, `[security.blacklist.local_source]`. Models: `SecurityConfig`, `IPFilterConfig`, `BlacklistConfig`, `SSLConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

#### Encryption Configuration

ccBitTorrent supports BEP 3 Message Stream Encryption (MSE) and Protocol Encryption (PE) for secure peer connections.

**Encryption Settings:**

- `enable_encryption` (bool, default: `false`): Enable protocol encryption support
- `encryption_mode` (str, default: `"preferred"`): Encryption mode
    - `"disabled"`: No encryption (plain connections only)
    - `"preferred"`: Attempt encryption, fallback to plain if unavailable
    - `"required"`: Encryption mandatory, connection fails if encryption unavailable
- `encryption_dh_key_size` (int, default: `768`): Diffie-Hellman key size in bits (768 or 1024)
- `encryption_prefer_rc4` (bool, default: `true`): Prefer RC4 cipher for compatibility with older clients
- `encryption_allowed_ciphers` (list[str], default: `["rc4", "aes"]`): Allowed cipher types
    - `"rc4"`: RC4 stream cipher (most compatible)
    - `"aes"`: AES cipher in CFB mode (more secure)
    - `"chacha20"`: ChaCha20 cipher (not yet implemented)
- `encryption_allow_plain_fallback` (bool, default: `true`): Allow fallback to plain connection if encryption fails (only applies when `encryption_mode` is `"preferred"`)

**Environment Variables:**

- `CCBT_ENABLE_ENCRYPTION`: Enable/disable encryption (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Encryption mode (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH key size (`768` or `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Prefer RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Comma-separated list (e.g., `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Allow plain fallback (`true`/`false`)

**Example Configuration:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Security Considerations:**

1. **RC4 Compatibility**: RC4 is supported for compatibility but is cryptographically weak. Use AES for better security when possible.
2. **DH Key Size**: 768-bit DH keys provide adequate security for most use cases. 1024-bit provides stronger security but increases handshake latency.
3. **Encryption Modes**:
   - `preferred`: Best for compatibility - attempts encryption but falls back gracefully
   - `required`: Most secure but may fail to connect with peers that don't support encryption
4. **Performance Impact**: Encryption adds minimal overhead (~1-5% for RC4, ~2-8% for AES) but improves privacy and helps avoid traffic shaping.

**Implementation Details:**

Encryption implementation: [ccbt/security/encryption.py:EncryptionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/mse_handshake.py)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Exchange: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/dh_exchange.py)

### Proxy Configuration

Section `[proxy]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): HTTP proxy enable, host, port, auth, use for trackers/peers/webseeds, bypass list. Model: `ProxyConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### ML Configuration

Machine learning settings: section `[ml]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Peer selection and piece prediction. Model: `MLConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Dashboard Configuration

Dashboard settings: section `[dashboard]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Host, port, refresh interval, terminal daemon timeouts. Model: `DashboardConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Queue Configuration

Section `[queue]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): Max active torrents/downloading/seeding, default priority, bandwidth allocation, auto-manage. Model: `QueueConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### UI Configuration

Section `[ui]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): Locale. Model: `UIConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### NAT Configuration

Section `[nat]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): NAT-PMP, UPnP, discovery interval, port mapping (TCP/UDP/DHT/XET). Model: `NATConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Daemon Configuration

Section `[daemon]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): IPC host and port for daemon mode. Model: `DaemonConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### WebTorrent Configuration

Section `[webtorrent]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): Enable WebTorrent, port, host.

## Environment Variables

Environment variables use the `CCBT_` prefix and follow a hierarchical naming scheme.

Reference: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Format: `CCBT_<SECTION>_<OPTION>=<value>`

Examples:
- Network: [env.example:10-58](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Disk: [env.example:62-102](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Strategy: [env.example:106-121](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Discovery: [env.example:125-141](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Observability: [env.example:145-162](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Limits: [env.example:166-180](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Security: [env.example:184-189](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- ML: [env.example:193-196](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Environment variable parsing: [ccbt/config/config.py:_get_env_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

## Configuration Schema

Configuration schema and validation: [ccbt/config/config_schema.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_schema.py)

The schema defines:
- Field types and constraints
- Default values
- Validation rules
- Documentation

## Configuration Capabilities

Configuration capabilities and feature detection: [ccbt/config/config_capabilities.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_capabilities.py)

## Configuration Templates

Predefined configuration templates: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Templates for:
- High-performance setup
- Low-resource setup
- Security-focused setup
- Development setup

## Configuration Examples

Example configurations are available in the [examples/](examples/) directory:

- Basic configuration: [example-config-basic.toml](examples/example-config-basic.toml)
- Advanced configuration: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Performance configuration: [example-config-performance.toml](examples/example-config-performance.toml)
- Security configuration: [example-config-security.toml](examples/example-config-security.toml)

## Hot Reload

Configuration hot-reload support: [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L85)

The configuration system supports hot-reloading changes without restarting the client.

## Configuration Migration

Configuration migration utilities: [ccbt/config/config_migration.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_migration.py)

Tools for migrating between configuration versions.

## Configuration Backup and Diff

Configuration management utilities:
- Backup: [ccbt/config/config_backup.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_diff.py)

## Conditional Configuration

Conditional configuration support: [ccbt/config/config_conditional.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_conditional.py)

## Per-Torrent Configuration

Per-torrent configuration allows you to override global settings for individual torrents. These settings are persisted in checkpoints and daemon state, ensuring they survive restarts.

### Per-Torrent Options

Per-torrent options are stored in `AsyncTorrentSession.options` and can include:

- `piece_selection`: Piece selection strategy (`"rarest_first"`, `"sequential"`, `"random"`)
- `streaming_mode`: Enable streaming mode for media files (`true`/`false`)
- `sequential_window_size`: Size of sequential download window (bytes)
- `max_peers_per_torrent`: Maximum number of peers for this torrent
- Custom options as needed

Implementation: [ccbt/session/session.py:AsyncTorrentSession](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L122)

### Per-Torrent Rate Limits

Rate limits can be set per-torrent using `AsyncSessionManager.set_rate_limits()`:

- `down_kib`: Download rate limit in KiB/s (0 = unlimited)
- `up_kib`: Upload rate limit in KiB/s (0 = unlimited)

Implementation: [ccbt/session/session.py:set_rate_limits](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L4737)

### Global Per-Torrent Defaults

You can set default per-torrent options in your `ccbt.toml` file:

```toml
[per_torrent_defaults]
piece_selection = "rarest_first"
streaming_mode = false
max_peers_per_torrent = 50
sequential_window_size = 10485760  # 10 MiB
```

These defaults are merged into each torrent's options when the torrent session is created.

Model: [ccbt/models.py:PerTorrentDefaultsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Setting Per-Torrent Options

#### Via CLI

```bash
# Set a per-torrent option
uv run btbt torrent config set <info_hash> piece_selection sequential

# Set rate limits (via session manager)
# Note: Rate limits are typically set via the TUI or programmatically
```

See [CLI Reference](btbt-cli.md#per-torrent-configuration) for full CLI documentation.

#### Via TUI

The terminal dashboard provides an interactive interface for managing per-torrent configuration:

- Navigate to torrent configuration screen
- Edit options and rate limits
- Changes are automatically saved to checkpoints

Implementation: [ccbt/interface/screens/config/torrent_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/screens/config/torrent_config.py#L85)

#### Programmatically

```python
# Set per-torrent options
torrent_session.options["piece_selection"] = "sequential"
torrent_session.options["streaming_mode"] = True
torrent_session._apply_per_torrent_options()

# Set rate limits
await session_manager.set_rate_limits(info_hash_hex, down_kib=100, up_kib=50)
```

### Persistence

Per-torrent configuration is persisted in:

1. **Checkpoints**: Saved automatically when checkpoints are created. Restored when resuming from checkpoint.
   - Model: [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)
   - Save: [ccbt/session/checkpointing.py:save_checkpoint_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/checkpointing.py)
   - Load: [ccbt/session/session.py:_resume_from_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py)

2. **Daemon State**: Saved when daemon state is persisted. Restored when daemon restarts.
   - Model: [ccbt/daemon/state_models.py:TorrentState](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_models.py)
   - Save: [ccbt/daemon/state_manager.py:_build_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_manager.py)
   - Load: [ccbt/daemon/main.py:_restore_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/main.py)

## Tips and Best Practices

### Performance Tuning

- Increase `disk.write_buffer_kib` for large sequential writes: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Enable `direct_io` on Linux/NVMe for better write throughput: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Tune `network.pipeline_depth` and `network.block_size_kib` for your network: [ccbt.toml:11-13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Resource Optimization

- Adjust `disk.hash_workers` based on CPU cores: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Configure `disk.cache_size_mb` based on available RAM: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Set `network.max_global_peers` based on bandwidth: [ccbt.toml:6](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

### Network Configuration

- Configure timeouts based on network conditions: [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Enable/disable protocols as needed: [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Set rate limits appropriately: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

For detailed performance tuning, see [Performance Tuning Guide](performance.md).