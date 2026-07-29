# Examples

This section provides practical examples and code samples for using ccBitTorrent.

## Quick copy-paste examples

**CLI — download a torrent with options:**

```bash
uv run btbt download path/to/file.torrent -o ./downloads --max-connections 50
```

**Config — network section (e.g. in `ccbt.toml`):**

```toml
[network]
listen_port = 6881
max_connections = 200
max_uploads = 10
```

See [Configuration](configuration.md) and [btbt CLI](btbt-cli.md) for all options. More examples below.

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

The codebase implements **BitTorrent Protocol v2** (BEP 52) via `ccbt.core.torrent_v2.TorrentV2Parser`: v2-only and hybrid (v1 + v2) torrent generation and parsing. There is no standalone `create_v2_torrent` function; use the parser instance methods below.

::: ccbt.core.torrent_v2.TorrentV2Parser
    options:
      show_root_heading: false
      heading_level: 3

### Creating a v2 Torrent

**CLI (recommended):**

```bash
uv run btbt create-torrent ./my_files --v2 -o ./my_torrent.torrent -t http://tracker.example.com/announce --piece-length 16384
```

**Python API:** Use `TorrentV2Parser().generate_v2_torrent()`. Piece length must be a power of 2; pass `None` to auto-calculate.

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()
torrent_bytes = parser.generate_v2_torrent(
    source=Path("./my_files"),
    output=Path("./my_torrent.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=16384,  # 16 KiB (power of 2); or None for auto
    comment="My v2 torrent",
    created_by="ccBitTorrent",
    private=False,
)
# Returns bencoded bytes; if output= is set, file is also written
```

See [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) for runnable examples (single file and directory).

### Creating a Hybrid Torrent

Hybrid torrents contain both v1 (SHA-1) and v2 (SHA-256) metadata for compatibility with all clients.

**CLI:**

```bash
uv run btbt create-torrent ./my_files --hybrid -o ./my_torrent.torrent -t http://tracker.example.com/announce
```

**Python API:**

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("./my_files"),
    output=Path("./my_torrent.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=16384,
)
```

See [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) for a complete example.

### Parsing a v2 or Hybrid Torrent

**High-level (any v1/v2/hybrid file):** Use `TorrentParser.parse()` from `ccbt.core.torrent`; it returns a `TorrentInfo` and handles v2/hybrid internally.

```python
from pathlib import Path
from ccbt.core.torrent import TorrentParser

parser = TorrentParser()
info = parser.parse(Path("file.torrent"))
# info.info_hash, info.files, etc.; v2 fields present when applicable
```

**Low-level (v2 info only):** After decoding the bencoded file, use `TorrentV2Parser().parse_v2(info_dict, torrent_dict)` or `parse_hybrid(info_dict, torrent_dict)` for hybrid.

```python
from ccbt.core.bencode import decode
from ccbt.core.torrent_v2 import TorrentV2Parser

with open("file.torrent", "rb") as f:
    data = decode(f.read())
v2_info = TorrentV2Parser().parse_v2(data[b"info"], data)
# v2_info.name, v2_info.info_hash_v2, v2_info.files, v2_info.piece_layers, etc.
```

See [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) for full parsing examples.

### Protocol v2 Session

Protocol v2 support (handshake, negotiation, piece layers) is configured via `[network.protocol_v2]` in config and used automatically when downloading v2/hybrid torrents. For handshake and negotiation APIs see `ccbt.protocols.bittorrent_v2`.

See [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) for configuration, handshake creation, and protocol negotiation examples.

## Getting Started

For more information on getting started with ccBitTorrent, see the [Getting Started Guide](getting-started.md).
