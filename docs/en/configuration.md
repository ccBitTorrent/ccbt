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
| `[dashboard]` | Metrics dashboard and terminal refresh settings | `DashboardConfig` |
| `[discovery]` | DHT, PEX, trackers, DHT handshakes and adaptive behavior | `DiscoveryConfig` |
| `[disk]` | Preallocation, hash and disk workers, checkpoint/resume, nested disk settings | `DiskConfig` |
| `[ipfs]` | IPFS gateway and discovery behavior | `IPFSConfig` |
| `[limits]` | Global/per-torrent/per-peer rate limits and scheduler | `LimitsConfig` |
| `[media]` | Media streaming and token settings | `MediaConfig` |
| `[ml]` | Peer selection and piece prediction (ML) | `MLConfig` |
| `[nat]` | NAT-PMP, UPnP, and port mapping strategy | `NATConfig` |
| `[network]` | Connections, timeouts, listen ports, pool control, socket tuning | `NetworkConfig` |
| `[observability]` | Logging, metrics, event bus controls | `ObservabilityConfig` |
| `[optimization]` | Profile-based performance tuning defaults | `OptimizationConfig` |
| `[plugins]` | Plugin enablement and auto-load behavior | `PluginsConfig` |
| `[queue]` | Active torrent limits, priority, and bandwidth allocation | `QueueConfig` |
| `[security]` | Encryption, peer validation, and protection controls | `SecurityConfig` |
| `[strategy]` | Piece selection, endgame, streaming and sequencing | `StrategyConfig` |
| `[ui]` | Locale and localization behavior | `UIConfig` |
| `[webtorrent]` | WebTorrent enablement and endpoint defaults | `WebTorrentConfig` |
| `[xet_sync]` | XET sync enable, gossip, consensus and merge policy | `XetSyncConfig` |
| `[daemon]` | IPC host/port for daemon integration (included when daemon defaults are enabled) | `DaemonConfig` |

Nested sections are represented in TOML and environment naming conventions:
- `[network.utp]`, `[network.webtorrent]`, `[network.protocol_v2]`
- `[disk.attributes]`, `[disk.xet]`
- `[security.ip_filter]`, `[security.blacklist]`, `[security.blacklist.local_source]`, `[security.ssl]`, `[security.authenticated_swarms]`
- `[plugins.metrics]`

## Configuration Sources and Precedence

Configuration is loaded in this order (later sources override earlier ones):

1. **Defaults**: Built-in sensible defaults from [ccbt/models.py:Config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)
2. **Config File**: `ccbt.toml` in current directory or `~/.config/ccbt/ccbt.toml`. See [ccbt/config/config.py:_find_config_file](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L107)
3. **Environment Variables**: `CCBT_*` prefixed variables. See [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
4. **CLI Arguments**: Command-line overrides. See [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/overrides.py#L17) {#cli-overrides}
5. **Per-Torrent Defaults**: Global defaults for per-torrent options. See [Per-Torrent Configuration](#per-torrent-configuration) section
6. **Per-Torrent Overrides**: Individual torrent settings (set via CLI, TUI, or programmatically)

Configuration loading: [ccbt/config/config.py:_load_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L128)

### `btbt config` CLI (inspect and edit `ccbt.toml`)

All configuration introspection and file editing commands live under **`btbt config`** (there is no separate `config-extended` command).

| Command | Purpose |
|--------|---------|
| `btbt config describe` | List every nested option path with types, defaults, and descriptions; add `--include-current` for effective values (file + env). |
| `btbt config schema` | Dump JSON Schema for `Config` (optional `--model`, `-o`). |
| `btbt config show` / `config get` | Print effective merged configuration (not the full catalog). |
| `btbt config set` | Set one dotted path; validates before write; `--value`, `--dry-run`, JSON/comma-list parsing. |
| `btbt config apply` | Merge a JSON/TOML/YAML patch file (or stdin) into the target TOML; validates before write. |
| `btbt config import` | Import a file; `--mode replace` (full document) or `--mode merge` (deep-merge into existing file). |
| `btbt config validate` | Load and validate; `--detailed` adds system compatibility checks. |

See [btbt CLI – Configuration](btbt-cli.md#configuration-commands) and [ccbt/cli/config_group.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_group.py).

**Precedence reminder:** After editing the file with `set`/`apply`/`import`, environment variables can still override the same keys at runtime.

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

Recovery behavior uses the following network/discovery controls:

- `enable_fail_fast_dht` / `CCBT_ENABLE_FAIL_FAST_DHT`: allow a quicker fallback when active peers remain below `min_peers_before_dht`.
- `fail_fast_dht_timeout` / `CCBT_FAIL_FAST_DHT_TIMEOUT`: wait threshold before fail-fast recovery becomes available.
- `tracker_timeout` / `CCBT_TRACKER_TIMEOUT`: also used to bound immediate tracker handoff duration during low-peer recovery.
- `min_peers_before_dht` / `CCBT_MIN_PEERS_BEFORE_DHT`: threshold for deciding when immediate DHT fallback is needed.

Low-peer recovery outcomes are now logged per-cycle with a single structured summary line that includes tracker/DHT outcomes, queued peer count, retry plan, and final recovery state.

Discovery config model: `DiscoveryConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Limits Configuration

Rate limits: section `[limits]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Global and per-torrent/per-peer limits, scheduler slice.

Limits config model: `LimitsConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### Observability Configuration

Observability settings: section `[observability]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Supported keys include `log_level`, `log_file`, `structured_logging`, `log_correlation_id`, `metrics_interval`, `metrics_port`, `event_bus_*`, and `alerts_rules_path`.

Runtime precedence for observability values follows the global configuration order: defaults, TOML values, environment variables (`CCBT_LOG_LEVEL`, `CCBT_LOG_FORMAT`, `CCBT_LOG_CORRELATION_ID`, `CCBT_STRUCTURED_LOGGING`, `CCBT_METRICS_INTERVAL`, etc.), and then CLI overrides.

Verbosity remains CLI-driven: `-v` maps to INFO-style output, `-vv` to DEBUG, and `-vvv` to TRACE.

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

Security settings: section `[security]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml). Nested: `[security.ip_filter]`, `[security.blacklist]`, `[security.ssl]`, `[security.blacklist.local_source]`, `[security.authenticated_swarms]`. Models: `SecurityConfig`, `IPFilterConfig`, `BlacklistConfig`, `SSLConfig`, `AuthenticatedSwarmsConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

**Transport security (four separate concepts):**

1. **Plain BitTorrent** — Standard peer wire protocol over TCP without MSE/PE.
2. **MSE/PE (BEP 3)** — Optional **obfuscation** of peer traffic for ecosystem compatibility; it does **not** authenticate peer identity.
3. **HTTPS tracker TLS** — TLS for `https://` tracker announces only. **UDP trackers (BEP 15) use datagrams and have no TLS** in the standard protocol.
4. **Experimental peer TLS (BEP 10 extension)** — Optional post-handshake TLS upgrade between peers. This is **not** [BEP 47](https://www.bittorrent.org/beps/bep_0047.html) (BEP 47 covers padding files and extended file attributes).

#### Encryption Configuration

ccBitTorrent supports BEP 3 Message Stream Encryption (MSE) and Protocol Encryption (PE) for **peer traffic obfuscation and interop**, not for cryptographic authentication of peers.

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
- `enable_ssl_trackers` (bool, default: `true`): Use TLS for `https://` tracker announces. UDP trackers (BEP 15) are UDP datagrams and use no TLS in the standard protocol.
- `ssl_verify_certificates` (bool, default: `true`): Verify tracker/peer TLS certificates when TLS is used.

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
4. **Performance Impact**: Encryption adds minimal overhead (~1-5% for RC4, ~2-8% for AES) and can reduce passive visibility of peer traffic; it is not a substitute for authenticated transports.

**Implementation Details:**

Encryption implementation: [ccbt/security/encryption.py:EncryptionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/mse_handshake.py)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Exchange: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/dh_exchange.py)

#### Authenticated Swarms Configuration

Authenticated swarms validate whether peers are permitted for a swarm before exchange proceeds.

Settings: section `[security.authenticated_swarms]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml), with policy wiring implemented in `ccbt/security/swarm_auth_policy.py`.

**Authenticated Swarm Settings:**

- `mode` (str, default: `"off"`): Admission mode (`off`, `opportunistic`, `strict`)
- `discovery_mode` (str, default: `"trackers_only"`): Discovery mode for authenticated peers (`full`, `trackers_only`, `dht_only`, `pex_off`)
- `discovery_strict_for_strict_mode` (bool, default: `true`): When strict mode is active, enforce discovery restrictions
- `strict_ltep_handshake_timeout_s` (float, default: `30.0`): Timeout for inbound peers in strict mode to complete the extension handshake (LTEP) before they are dropped
- `trusted_swarm_ids` (list[str], default: `[]`): Trusted swarm IDs that bypass strict checks
- `fail_closed_on_parse_errors` (bool, default: `false`): Keep strict mode closed on parse/validation failures
- `trust_store_path` (str | null, default: `null`): Optional trust store file path
- `trust_store_refresh_interval_s` (float, default: `60.0`): Trust store refresh interval in seconds
- `revocation_profile_path` (str | null, default: `null`): Optional revocation profile file path
- `revocation_refresh_interval_s` (float, default: `300.0`): Revocation profile refresh interval in seconds

**Environment Variables:**

- `CCBT_AUTHENTICATED_SWARMS_MODE`
- `CCBT_AUTHENTICATED_SWARMS_DISCOVERY_MODE`
- `CCBT_AUTHENTICATED_SWARMS_DISCOVERY_STRICT_FOR_STRICT_MODE`
- `CCBT_AUTHENTICATED_SWARMS_STRICT_LTEP_TIMEOUT_S`
- `CCBT_AUTHENTICATED_SWARMS_TRUSTED_IDS`
- `CCBT_AUTHENTICATED_SWARMS_FAIL_CLOSED_ON_PARSE_ERRORS`
- `CCBT_AUTHENTICATED_SWARMS_TRUST_STORE_PATH`
- `CCBT_AUTHENTICATED_SWARMS_TRUST_STORE_REFRESH_INTERVAL_S`
- `CCBT_AUTHENTICATED_SWARMS_REVOCATION_PROFILE_PATH`
- `CCBT_AUTHENTICATED_SWARMS_REVOCATION_REFRESH_INTERVAL_S`

**Example Configuration:**

```toml
[security.authenticated_swarms]
mode = "opportunistic"
discovery_mode = "trackers_only"
strict_ltep_handshake_timeout_s = 30.0
trusted_swarm_ids = []
fail_closed_on_parse_errors = false
```

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

In the default `ccbt.toml`, the daemon section is omitted because daemon defaults are disabled by default, but it is still accepted when present and mapped via `CCBT_DAEMON_IPC_HOST`/`CCBT_DAEMON_IPC_PORT`.

Section `[daemon]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): IPC host and port for daemon mode. Model: `DaemonConfig` in [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py).

### WebTorrent Configuration

Section `[webtorrent]` in [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml): Enable WebTorrent, port, host.

## Environment Variables

Environment variables use the `CCBT_` prefix and follow a hierarchical naming scheme.

Reference: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Format: `CCBT_<SECTION>_<OPTION>=<value>`

Examples are grouped by canonical section in `env.example` (with aliases and legacy compatibility keys preserved in a dedicated section at the end).
Use the same section names shown in the TOML guide above to map between env and file keys.

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

Example templates are intentionally kept minimal and can be derived from:
- `env.example` (environment compatibility baseline)
- `ccbt.toml` (canonical defaults generated from `ccbt.models.Config`)
- Per-feature templates in your deployment automation or CI

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

- Increase `disk.write_buffer_kib` for large sequential writes in `ccbt.toml`.
- Enable `direct_io` on Linux/NVMe for better write throughput in `ccbt.toml`.
- Tune `network.pipeline_depth` and `network.block_size_kib` for your network in `ccbt.toml`.

### Resource Optimization

- Adjust `disk.hash_workers` based on CPU cores in `ccbt.toml`.
- Configure `disk.cache_size_mb` based on available RAM in `ccbt.toml`.
- Set `network.max_global_peers` based on bandwidth in `ccbt.toml`.

### Network Configuration

- Configure timeouts based on network conditions in `ccbt.toml`.
- Enable/disable protocols as needed in `ccbt.toml`.
- Set rate limits appropriately in `ccbt.toml`.

For detailed performance tuning, see [Performance Tuning Guide](performance.md).