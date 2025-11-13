# Configuration Guide

ccBitTorrent uses a comprehensive configuration system with TOML support, validation, hot-reload, and hierarchical loading from multiple sources.

Configuration system: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Configuration Sources and Precedence

Configuration is loaded in this order (later sources override earlier ones):

1. **Defaults**: Built-in sensible defaults from [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Config File**: `ccbt.toml` in current directory or `~/.config/ccbt/ccbt.toml`. See [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Environment Variables**: `CCBT_*` prefixed variables. See [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI Arguments**: Command-line overrides. See [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Per-Torrent**: Individual torrent settings (future feature)

Configuration loading: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Configuration File

### Default Configuration

Reference the default configuration file: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

The configuration is organized into sections:

### Network Configuration

Network settings: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Connection limits: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Request pipeline: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Socket tuning: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Timeouts: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Listen settings: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Transport protocols: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Rate limits: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Choking strategy: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Tracker settings: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Network config model: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Disk Configuration

Disk settings: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Preallocation: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Write optimization: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Hash verification: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O threading: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Advanced settings: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Storage service settings: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Maximum file size limit in MB for storage service (0 or None = unlimited, max 1048576 = 1TB). Prevents unbounded disk writes during testing and can be configured for production use.
- Checkpoint settings: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Disk config model: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Strategy Configuration

Strategy settings: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Piece selection: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Advanced strategy: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Piece priorities: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Strategy config model: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Discovery Configuration

Discovery settings: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT settings: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX settings: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Tracker settings: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tracker announce interval in seconds (default: 1800.0, range: 60.0-86400.0)
  - `tracker_scrape_interval`: Tracker scrape interval in seconds for periodic scraping (default: 3600.0, range: 60.0-86400.0)
  - `tracker_auto_scrape`: Automatically scrape trackers when torrents are added (BEP 48) (default: false)
  - Environment variables: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Discovery config model: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Limits Configuration

Rate limits: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Global limits: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Per-torrent limits: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Per-peer limits: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Scheduler settings: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Limits config model: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Observability Configuration

Observability settings: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Logging: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Metrics: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Tracing and alerts: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Observability config model: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Security Configuration

Security settings: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Security config model: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

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

Encryption implementation: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Exchange: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML Configuration

Machine learning settings: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML config model: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Dashboard Configuration

Dashboard settings: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Dashboard config model: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Environment Variables

Environment variables use the `CCBT_` prefix and follow a hierarchical naming scheme.

Reference: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Format: `CCBT_<SECTION>_<OPTION>=<value>`

Examples:
- Network: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Disk: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Strategy: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Discovery: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Observability: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Limits: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Security: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Environment variable parsing: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Configuration Schema

Configuration schema and validation: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

The schema defines:
- Field types and constraints
- Default values
- Validation rules
- Documentation

## Configuration Capabilities

Configuration capabilities and feature detection: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Configuration Templates

Predefined configuration templates: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

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

Configuration hot-reload support: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

The configuration system supports hot-reloading changes without restarting the client.

## Configuration Migration

Configuration migration utilities: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Tools for migrating between configuration versions.

## Configuration Backup and Diff

Configuration management utilities:
- Backup: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Conditional Configuration

Conditional configuration support: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Tips and Best Practices

### Performance Tuning

- Increase `disk.write_buffer_kib` for large sequential writes: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Enable `direct_io` on Linux/NVMe for better write throughput: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Tune `network.pipeline_depth` and `network.block_size_kib` for your network: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Resource Optimization

- Adjust `disk.hash_workers` based on CPU cores: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Configure `disk.cache_size_mb` based on available RAM: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Set `network.max_global_peers` based on bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Network Configuration

- Configure timeouts based on network conditions: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Enable/disable protocols as needed: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Set rate limits appropriately: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

For detailed performance tuning, see [Performance Tuning Guide](performance.md).