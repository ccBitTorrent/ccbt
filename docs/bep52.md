# BEP 52: BitTorrent Protocol v2

## Overview

BitTorrent Protocol v2 (BEP 52) is a major upgrade to the BitTorrent protocol that introduces SHA-256 hashing, improved metadata structure, and better support for large files. ccBitTorrent provides full support for v2-only torrents, v1-only torrents, and hybrid torrents that work with both protocols.

### Key Features

- **SHA-256 Hashing**: More secure than SHA-1 used in v1
- **Merkle Tree Structure**: Efficient piece validation and partial downloads
- **File Tree Format**: Hierarchical file organization
- **Piece Layers**: Per-file piece validation
- **Hybrid Torrents**: Backwards compatibility with v1 clients

## Architecture

### Core Components

#### 1. Torrent Metadata (`ccbt/core/torrent_v2.py`)

The v2 torrent parser handles all metadata operations:

```python
from ccbt.core.torrent_v2 import TorrentV2Parser, TorrentV2Info

# Parse v2 torrent
parser = TorrentV2Parser()
with open("torrent_file.torrent", "rb") as f:
    torrent_data = decode(f.read())
    
v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

# Access v2-specific data
print(f"Info Hash v2: {v2_info.info_hash_v2.hex()}")
print(f"File Tree: {v2_info.file_tree}")
print(f"Piece Layers: {len(v2_info.piece_layers)}")
```

#### 2. Protocol Communication (`ccbt/protocols/bittorrent_v2.py`)

Handles v2 handshakes and messages:

```python
from ccbt.protocols.bittorrent_v2 import (
    create_v2_handshake,
    send_v2_handshake,
    handle_v2_handshake,
    PieceLayerRequest,
    PieceLayerResponse,
)

# Create v2 handshake
info_hash_v2 = v2_info.info_hash_v2
peer_id = b"-CC0101-" + b"x" * 12
handshake = create_v2_handshake(info_hash_v2, peer_id)

# Send handshake
await send_v2_handshake(writer, info_hash_v2, peer_id)

# Receive handshake
version, peer_id, parsed = await handle_v2_handshake(reader, writer)
```

#### 3. SHA-256 Hashing (`ccbt/piece/hash_v2.py`)

Implements v2 hashing functions:

```python
from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_layer,
    hash_file_tree,
    verify_piece_v2,
)

# Hash a piece
piece_data = b"..." * 16384
piece_hash = hash_piece_v2(piece_data)

# Verify piece
is_valid = verify_piece_v2(piece_data, expected_hash)

# Build Merkle tree
piece_hashes = [hash_piece_v2(p) for p in pieces]
merkle_root = hash_piece_layer(piece_hashes)
```

## Configuration

### Enable Protocol v2

Configure v2 protocol support in `ccbt.toml`:

```toml
[network.protocol_v2]
enable_protocol_v2 = true      # Enable v2 support
prefer_protocol_v2 = false     # Prefer v2 over v1 when both available
support_hybrid = true          # Support hybrid torrents
v2_handshake_timeout = 30.0    # Handshake timeout in seconds
```

### Environment Variables

```bash
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
```

### CLI Flags

```bash
# Enable v2 protocol
ccbt download file.torrent --protocol-v2

# Prefer v2 when available
ccbt download file.torrent --protocol-v2-prefer

# Disable v2 protocol
ccbt download file.torrent --no-protocol-v2
```

## Creating Torrents

### V2-Only Torrents

Create torrents that only work with v2 clients:

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()

# Create from single file
torrent_bytes = parser.generate_v2_torrent(
    source=Path("video.mp4"),
    output=Path("video.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=262144,  # 256 KiB
    comment="My video file",
    private=False,
)

# Create from directory
torrent_bytes = parser.generate_v2_torrent(
    source=Path("my_files/"),
    output=Path("my_files.torrent"),
    trackers=[
        "http://tracker1.example.com/announce",
        "http://tracker2.example.com/announce",
    ],
    piece_length=None,  # Auto-calculate
)
```

### Hybrid Torrents

Create torrents compatible with both v1 and v2 clients:

```python
# Create hybrid torrent
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("archive.zip"),
    output=Path("archive.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=1048576,  # 1 MiB
    comment="Backwards compatible torrent",
    private=False,
)
```

### CLI Torrent Creation

```bash
# Create v2 torrent
ccbt create-torrent file.mp4 --v2 \
    --output file.torrent \
    --tracker http://tracker.example.com/announce \
    --piece-length 262144 \
    --comment "My file"

# Create hybrid torrent
ccbt create-torrent directory/ --hybrid \
    --output directory.torrent \
    --tracker http://tracker.example.com/announce \
    --private
```

## Protocol Details

### Handshake Format

#### V2 Handshake (80 bytes)
```
- 1 byte:  Protocol string length (19)
- 19 bytes: "BitTorrent protocol"
- 8 bytes:  Reserved bytes (bit 0 = 1 for v2 support)
- 32 bytes: SHA-256 info_hash_v2
- 20 bytes: Peer ID
```

#### Hybrid Handshake (100 bytes)
```
- 1 byte:  Protocol string length (19)
- 19 bytes: "BitTorrent protocol"
- 8 bytes:  Reserved bytes (bit 0 = 1)
- 20 bytes: SHA-1 info_hash_v1
- 32 bytes: SHA-256 info_hash_v2
- 20 bytes: Peer ID
```

### Protocol Version Negotiation

ccBitTorrent automatically negotiates the best protocol version:

```python
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    negotiate_protocol_version,
)

# Peer's handshake
peer_handshake = b"..."

# Our supported versions (in priority order)
supported = [
    ProtocolVersion.HYBRID,
    ProtocolVersion.V2,
    ProtocolVersion.V1,
]

# Negotiate
negotiated = negotiate_protocol_version(peer_handshake, supported)

if negotiated == ProtocolVersion.V2:
    # Use v2 protocol
    pass
elif negotiated == ProtocolVersion.HYBRID:
    # Use hybrid mode
    pass
elif negotiated == ProtocolVersion.V1:
    # Fall back to v1
    pass
else:
    # Incompatible
    pass
```

### V2-Specific Messages

#### Piece Layer Request (Message ID 20)

Request piece hashes for a file:

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerRequest

pieces_root = b"..." # 32-byte SHA-256 root hash
request = PieceLayerRequest(pieces_root)
message_bytes = request.serialize()
```

#### Piece Layer Response (Message ID 21)

Send piece hashes:

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerResponse

piece_hashes = [b"..." * 32 for _ in range(10)]  # List of SHA-256 hashes
response = PieceLayerResponse(pieces_root, piece_hashes)
message_bytes = response.serialize()
```

#### File Tree Request (Message ID 22)

Request complete file tree:

```python
from ccbt.protocols.bittorrent_v2 import FileTreeRequest

request = FileTreeRequest()
message_bytes = request.serialize()
```

#### File Tree Response (Message ID 23)

Send file tree structure:

```python
from ccbt.protocols.bittorrent_v2 import FileTreeResponse

file_tree_bencoded = encode(file_tree_dict)
response = FileTreeResponse(file_tree_bencoded)
message_bytes = response.serialize()
```

## File Tree Structure

V2 torrents use a hierarchical file tree:

```python
from ccbt.core.torrent_v2 import FileTreeNode

# Single file
file_node = FileTreeNode(
    name="video.mp4",
    length=1000000,
    pieces_root=b"..." * 32,
    children=None,
)

# Directory structure
dir_node = FileTreeNode(
    name="my_files",
    length=0,
    pieces_root=None,
    children={
        "file1.txt": FileTreeNode(...),
        "file2.txt": FileTreeNode(...),
        "subdir": FileTreeNode(...),
    },
)

# Check node type
if file_node.is_file():
    print(f"File: {file_node.length} bytes")
if dir_node.is_directory():
    print(f"Directory with {len(dir_node.children)} items")
```

## Piece Layers

Each file has its own piece layer with SHA-256 hashes:

```python
from ccbt.core.torrent_v2 import PieceLayer

# Create piece layer
layer = PieceLayer(
    piece_length=262144,  # 256 KiB
    pieces=[
        b"..." * 32,  # Piece 0 hash
        b"..." * 32,  # Piece 1 hash
        b"..." * 32,  # Piece 2 hash
    ],
)

# Get piece hash
piece_0_hash = layer.get_piece_hash(0)

# Number of pieces
num_pieces = layer.num_pieces()
```

## Best Practices

### When to Use V2

- **New torrents**: Always prefer v2 for new content
- **Large files**: V2 is more efficient for files > 1 GB
- **Security**: SHA-256 provides better collision resistance
- **Future-proofing**: V2 is the future of BitTorrent

### When to Use Hybrid

- **Maximum compatibility**: Reach both v1 and v2 clients
- **Transition period**: During ecosystem migration
- **Public torrents**: Wider distribution

### When to Use V1-Only

- **Legacy systems**: Only when v2 support is unavailable
- **Small files**: V1 overhead is acceptable for < 100 MB

### Piece Length Selection

Auto-calculation is recommended, but manual values:

- **Small files (< 16 MiB)**: 16 KiB
- **Medium files (16 MiB - 512 MiB)**: 256 KiB
- **Large files (> 512 MiB)**: 1 MiB
- **Very large files (> 10 GiB)**: 2-4 MiB

Piece length must be a power of 2.

## API Reference

### TorrentV2Parser

Main class for v2 torrent operations:

```python
class TorrentV2Parser:
    def parse_v2(self, info_dict: dict, torrent_data: dict) -> TorrentV2Info:
        """Parse v2 torrent info dictionary."""
        
    def parse_hybrid(self, info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]:
        """Parse hybrid torrent (returns v1 and v2 info)."""
        
    def generate_v2_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Generate v2-only torrent file."""
        
    def generate_hybrid_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Generate hybrid torrent file."""
```

### TorrentV2Info

Data model for v2 torrent information:

```python
@dataclass
class TorrentV2Info:
    name: str
    info_hash_v2: bytes  # 32-byte SHA-256
    info_hash_v1: bytes | None  # 20-byte SHA-1 (hybrid only)
    announce: str
    announce_list: list[list[str]] | None
    comment: str | None
    created_by: str | None
    creation_date: int | None
    encoding: str | None
    is_private: bool
    file_tree: dict[str, FileTreeNode]
    piece_layers: dict[bytes, PieceLayer]
    piece_length: int
    files: list[FileInfo]
    total_length: int
    num_pieces: int
    
    def get_file_paths(self) -> list[str]:
        """Get list of all file paths."""
        
    def get_piece_layer(self, pieces_root: bytes) -> PieceLayer | None:
        """Get piece layer for a file."""
```

### Protocol Functions

```python
# Handshake
def create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes
def create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes
def detect_protocol_version(handshake: bytes) -> ProtocolVersion
def parse_v2_handshake(data: bytes) -> dict
def negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None

# Async I/O
async def send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None
async def send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None
async def handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]
async def upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool
```

### Hash Functions

```python
# Piece hashing
def hash_piece_v2(data: bytes) -> bytes
def hash_piece_v2_streaming(data_source: bytes | IO) -> bytes
def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool

# Merkle trees
def hash_piece_layer(piece_hashes: list[bytes]) -> bytes
def verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool

# File trees
def hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes
```

## Examples

See [docs/examples/bep52/](examples/bep52/) for complete working examples:

- `create_v2_torrent.py`: Create v2 torrent from file
- `create_hybrid_torrent.py`: Create hybrid torrent
- `parse_v2_torrent.py`: Parse and display v2 torrent info
- `protocol_v2_session.py`: Start session with v2 support

## Troubleshooting

### Common Issues

**Problem**: v2 handshake fails with "Info hash v2 mismatch"
- **Solution**: Verify info_hash_v2 is correctly calculated (SHA-256 of bencoded info dict)

**Problem**: Piece layer validation fails
- **Solution**: Ensure piece_length matches between torrent and validation

**Problem**: File tree parsing errors
- **Solution**: Check file tree structure follows BEP 52 format (proper nesting, pieces_root length)

**Problem**: Protocol version negotiation returns None
- **Solution**: Peer may not support v2. Check reserved bytes in handshake.

### Debug Logging

Enable debug logging for v2 protocol:

```python
import logging
logging.getLogger("ccbt.core.torrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.protocols.bittorrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.piece.hash_v2").setLevel(logging.DEBUG)
```

## Performance Considerations

### Memory Usage

- V2 torrents use more memory for piece layers (32 bytes vs 20 bytes per piece)
- File tree structure adds overhead for multi-file torrents
- Hybrid torrents store both v1 and v2 metadata

### CPU Usage

- SHA-256 is ~2x slower than SHA-1 for hashing
- Merkle tree construction adds computational overhead
- Use piece length >= 256 KiB for large files to reduce CPU usage

### Network

- V2 handshakes are 12 bytes larger (80 vs 68 bytes)
- Hybrid handshakes are 32 bytes larger (100 vs 68 bytes)
- Piece layer exchange adds initial overhead but enables efficient resumption

## Standards Compliance

ccBitTorrent's BEP 52 implementation follows the official specification:

- **BEP 52**: [BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- **Test Suite**: 2500+ lines of comprehensive tests
- **Compatibility**: Interoperable with libtorrent, qBittorrent, Transmission

## See Also

- [API Documentation](API.md)
- [Configuration Guide](configuration.md)
- [Architecture Overview](architecture.md)
- [BEP Index](https://www.bittorrent.org/beps/bep_0000.html)

