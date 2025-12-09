# Examples

This section provides practical examples and code samples for using ccBitTorrent.

## Configuration Examples

### Basic Configuration

A minimal configuration file to get started:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

See [example-config-basic.toml](examples/example-config-basic.toml) for a complete basic configuration.

### Advanced Configuration

For advanced users who need fine-grained control:

See [example-config-advanced.toml](examples/example-config-advanced.toml) for advanced configuration options.

### Performance Configuration

Optimized settings for maximum performance:

See [example-config-performance.toml](examples/example-config-performance.toml) for performance tuning.

### Security Configuration

Security-focused configuration with encryption and validation:

See [example-config-security.toml](examples/example-config-security.toml) for security settings.

## BEP 52 Examples

### Creating a v2 Torrent

Create a BitTorrent v2 torrent file:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Create v2 torrent
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB pieces
)
```

See [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) for a complete example.

### Creating a Hybrid Torrent

Create a hybrid torrent that works with both v1 and v2 clients:

See [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) for a complete example.

### Parsing a v2 Torrent

Parse and inspect a BitTorrent v2 torrent file:

See [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) for a complete example.

### Protocol v2 Session

Use the BitTorrent v2 protocol in a session:

See [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) for a complete example.

## Getting Started

For more information on getting started with ccBitTorrent, see the [Getting Started Guide](getting-started.md).

