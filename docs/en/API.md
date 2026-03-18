# ccBT API Reference

Comprehensive API documentation for ccBitTorrent with references to actual implementation files.

## Public API

The package public API is defined by `__all__` in [ccbt/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__init__.py). Main exports include: **AsyncSessionManager**, **SessionManager**, **Config**, **ConfigManager**, **TorrentParser**, **BencodeDecoder**/**BencodeEncoder**, **MagnetInfo**, **parse_magnet**, **get_config**, **init_config**; submodules **bencode**, **magnet**, **torrent**, **config**, **session**, **tracker**, **dht**, **pex**, **peer**, **peer_connection**, **async_peer_connection**, **piece_manager**, **async_piece_manager**, **metadata_exchange**, **async_metadata_exchange**, **checkpoint**, **file_assembler**, **events**, **exceptions**, **metrics**, **logging_config**, **resilience**, **network_optimizer**; and helpers **build_minimal_torrent_data**, **build_torrent_data_from_metadata**. Use "View source" links from mkdocstrings-rendered sections below for current locations.

## Entry Points

### Main Entry Point (ccbt)

Main command-line entry point for basic torrent operations.

Implementation: [ccbt/__main__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py) — `main`. Features: single-torrent download, daemon mode, magnet URI support, tracker announcement. Entry point: [pyproject.toml](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml) (project.scripts).

### Async Download Helpers

High-performance async helpers and download manager for advanced operations.

Implementation: [ccbt/session/download_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

Key exports:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

### AsyncDownloadManager

High-performance async download manager for individual torrents.

Implementation: [ccbt/session/download_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/download_manager.py) — `AsyncDownloadManager`. Methods: `__init__`, `start`, `stop`, `start_download`. Uses peer connection and piece managers; see [ccbt/session/download_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/download_manager.py) for current implementation.

## Core Modules

### Torrent Parsing and Metadata

#### TorrentParser

Parses BitTorrent torrent files and extracts metadata.

::: ccbt.core.torrent.TorrentParser
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Key Methods:**

- `parse()`: Parse torrent file from path or URL. `_validate_torrent()`, `_extract_torrent_data()`: validation and extraction. See [ccbt/core/torrent.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/core/torrent.py).

#### Bencode Encoding/Decoding

Bencode codec for BitTorrent protocol (BEP 3). Use "View source" on the reference below for current locations.

::: ccbt.core.bencode
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"

**Supported Types:** Integers `i<number>e`, strings `<length>:<data>`, lists `l<items>e`, dictionaries `d<key-value pairs>e`.

#### Magnet URI Parsing

Parses magnet URIs (BEP 9) with BEP 53 file selection support. Public API: `parse_magnet()`, `MagnetInfo`, `build_minimal_torrent_data()`, `build_torrent_data_from_metadata()`. Use "View source" on the reference below.

::: ccbt.core.magnet
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"

## Session Management

### AsyncSessionManager

High-performance async session manager for multiple torrents.

::: ccbt.session.session.AsyncSessionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

#### Initialization

Constructor and lifecycle are implemented in `ccbt/session/session.py` (class `AsyncSessionManager`). Use the [API reference source links](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py) or mkdocstrings-generated "View source" when available.

#### Lifecycle Methods

- `start()`: Start the async session manager
- `stop()`: Stop the async session manager

See `ccbt/session/session.py` for the current implementation of these methods.

#### Torrent Management

See **AsyncSessionManager** above for source links: `add_torrent()`, `add_magnet()`, `remove()`, `pause_torrent()`, `resume_torrent()`, `set_rate_limits()`.

#### Status and Monitoring

See **AsyncSessionManager** above: `get_global_stats()`, `get_status()`, `get_peers_for_torrent()`.

#### Advanced Operations

See **AsyncSessionManager** above: `force_announce()`, `force_scrape()`, `refresh_pex()`, `rehash_torrent()`, `export_session_state()`.

### AsyncTorrentSession

Individual torrent session representing one active torrent's lifecycle with async operations.

::: ccbt.session.session.AsyncTorrentSession
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Key Methods:** See **AsyncTorrentSession** above for source links: `start()`, `stop()`, `pause()`, `resume()`, `get_status()`.

**Components:** `download_manager` (AsyncDownloadManager), `file_selection_manager` (FileSelectionManager), `piece_manager` (AsyncPieceManager), `checkpoint_manager` (CheckpointManager).

**Data Model:** `TorrentSessionInfo` in [ccbt/session/session.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py).


## Peer Management

### Peer

Represents a peer connection.

Implementation: [ccbt/peer/peer.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/peer/peer.py)

Properties and methods:
- Peer information: IP, port, peer ID, client identification
- Connection state: Connected, choked, interested
- Transfer rates: Download/upload speeds

### AsyncPeerConnection

Async peer connection with pipelining, tit-for-tat choking, and adaptive block sizing.

!!! note "Implementation Status"
    The `AsyncPeerConnection` class is currently under development. For peer connection management, see `AsyncPeerConnectionManager` below.

**Features:**
- Request pipelining for high throughput: Deep request queues (16-64 outstanding requests)
- Async message handling: Non-blocking message processing
- Tit-for-tat choking: Fair bandwidth allocation with optimistic unchoke
- Connection state management: Tracks connection lifecycle

**Key Methods:**
- `connect()`: Establish connection and perform handshake
- `disconnect()`: Close connection and cleanup
- `request_piece()`: Request piece blocks with pipelining
- `send_piece()`: Send piece data to peer

### AsyncPeerConnectionManager

Manages multiple peer connections with connection pooling and lifecycle management.

::: ccbt.peer.async_peer_connection.AsyncPeerConnectionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

### PeerConnection

Synchronous peer connection (legacy).

Implementation: [ccbt/peer/peer_connection.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/peer/peer_connection.py)

### ConnectionPool

Connection pool for managing peer connections.

Implementation: [ccbt/peer/connection_pool.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/peer/connection_pool.py)

Features:
- Connection reuse
- Connection limits
- Connection lifecycle management

## Piece Management

### AsyncPieceManager

Advanced piece selection with rarest-first and endgame.

::: ccbt.piece.async_piece_manager.AsyncPieceManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:** Rarest-first, sequential, round-robin piece selection; endgame mode; file selection integration via [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py).

**Configuration:** [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml) sections 99–114.

### FileSelectionManager

Manages file selection and prioritization for multi-file torrents.

::: ccbt.piece.file_selection.FileSelectionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

Features: State (`FileSelectionState`), priority (`FilePriority`), piece-to-file mapping (`PieceToFileMapper`), filtering (`is_piece_needed`), priority selection (`get_piece_priority`), progress (`update_file_progress`). Key methods: `select_file`, `deselect_file`, `set_file_priority`, `get_statistics`. Use **FileSelectionManager** above for source links.

Related: [ccbt/piece/file_selection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/file_selection.py) (`FileSelectionState`, `FilePriority`, `PieceToFileMapper`); integrated with [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py) and [ccbt/session/session.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py); checkpoint persistence in session.

### PieceManager

Synchronous piece manager (legacy).

Implementation: [ccbt/piece/piece_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/piece_manager.py)

### AsyncMetadataExchange

Parallel metadata fetching with reliability scoring.

Implementation: [ccbt/piece/async_metadata_exchange.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py)

Features:
- Concurrent metadata fetching from multiple peers
- Reliability scoring
- Failure handling

### MetadataExchange

Synchronous metadata exchange (legacy).

Implementation: [ccbt/piece/metadata_exchange.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/metadata_exchange.py)

## Protocols

### BaseProtocol

Base protocol implementation.

::: ccbt.protocols.base
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"


### BitTorrentProtocol

Standard BitTorrent protocol implementation.

Implementation: [ccbt/protocols/bittorrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/bittorrent.py)

Features:
- BitTorrent protocol message handling
- Handshake negotiation
- Piece requests and responses

### HybridProtocol

Hybrid protocol supporting multiple transport methods.

Implementation: [ccbt/protocols/hybrid.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/hybrid.py)

### WebTorrentProtocol

WebTorrent protocol support.

Implementation: [ccbt/protocols/webtorrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/webtorrent.py)

### IPFSProtocol

IPFS protocol integration for decentralized content addressing and peer-to-peer networking.

Implementation: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)

**Requirements:**
- IPFS daemon must be running (default: `http://127.0.0.1:5001`)
- Dependencies: `ipfshttpclient>=0.8.0a2`, `multiaddr>=0.0.9`, `py-multiformats>=0.2.1`

**Features:**
- IPFS daemon integration via HTTP API
- Content addressing with CID (Content Identifier)
- Peer-to-peer messaging via IPFS pubsub
- Content discovery via DHT (Distributed Hash Table)
- Content operations: add, get, pin, unpin
- Torrent-to-IPFS conversion
- Gateway fallback support
- Automatic content pinning (configurable)

**Configuration:**
- API URL: `config.ipfs.api_url` (default: `http://127.0.0.1:5001`)
- Gateway URLs: `config.ipfs.gateway_urls` (fallback for content retrieval)
- Enable pinning: `config.ipfs.enable_pinning` (default: `False`)
- Connection timeout: `config.ipfs.connection_timeout` (default: 30s)
- Request timeout: `config.ipfs.request_timeout` (default: 30s)
- DHT enabled: `config.ipfs.enable_dht` (default: `True`)
- Discovery cache TTL: `config.ipfs.discovery_cache_ttl` (default: 300s)

**Methods:** Use the **IPFSProtocol** reference below for source links.

::: ccbt.protocols.ipfs.IPFSProtocol
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"

- `start()`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Connect to IPFS daemon and initialize protocol
  - Verifies connection by querying node ID
  - Sets protocol state to CONNECTED

- `stop()`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Disconnect from IPFS daemon and cleanup resources
  - Closes all peer connections
  - Sets protocol state to DISCONNECTED

- `connect_peer(peer_info: PeerInfo) -> bool`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Connect to an IPFS peer using multiaddr format
  - Parses peer multiaddr and validates peer ID
  - Sets up message listener for peer communication
  - Returns `True` on success, `False` on failure

- `disconnect_peer(peer_id: str) -> None`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Disconnect from an IPFS peer
  - Cleans up message queues and listeners

- `send_message(peer_id: str, message: bytes) -> bool`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Send message to IPFS peer via pubsub
  - Creates topic from peer_id: `/ccbt/peer/{peer_id}`
  - Validates message size (max 1MB)
  - Returns `True` on success, `False` on failure

- `receive_message(peer_id: str) -> bytes | None`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Receive message from IPFS peer
  - Waits up to 1 second for message from peer queue
  - Returns message bytes or `None` if timeout

- `announce_torrent(torrent_info: TorrentInfo) -> list[PeerInfo]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Announce torrent to IPFS network
  - Converts torrent to IPFS content (CID)
  - Discovers peers providing the content via DHT
  - Returns list of peer information

- `scrape_torrent(torrent_info: TorrentInfo) -> dict[str, int]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Scrape torrent statistics from IPFS network
  - Returns dict with `seeders`, `leechers`, `completed` counts
  - Uses content statistics from IPFS object stats

- `add_content(data: bytes) -> str`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Add content to IPFS and return CID
  - Automatically pins content if `enable_pinning` is `True`
  - Returns CID string or empty string on failure

- `get_content(cid: str) -> bytes | None`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Retrieve content from IPFS by CID
  - Uses IPFS daemon `cat` command
  - Updates content tracking with access time
  - Returns content bytes or `None` if not found

- `pin_content(cid: str) -> bool`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Pin content in IPFS to prevent garbage collection
  - Returns `True` on success, `False` on failure

- `unpin_content(cid: str) -> bool`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Unpin content from IPFS
  - Returns `True` on success, `False` on failure

- `get_ipfs_peers() -> list[str]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Get list of connected IPFS peer IDs
  - Returns list of peer ID strings

- `get_ipfs_content() -> dict[str, IPFSContent]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Get all tracked IPFS content
  - Returns dict mapping CID to IPFSContent objects

- `get_content_stats(cid: str) -> dict[str, int]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Get statistics for specific content
  - Returns dict with `seeders`, `leechers`, `completed`

- `get_all_content_stats() -> dict[str, dict[str, int]]`: [ccbt/protocols/ipfs.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/ipfs.py)
  - Get statistics for all tracked content
  - Returns dict mapping CID to stats dicts

**CID Format:**
- IPFS uses Content Identifiers (CIDs) to uniquely identify content
- CIDv0 format: Base58-encoded, starts with `Qm` (e.g., `QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o`)
- CIDv1 format: Multibase-encoded, supports different bases (e.g., `bafybei...`)
- Default: CIDv1 is used for new content, CIDv0 for legacy content

**Example Usage:**

```python
from ccbt.protocols.ipfs import IPFSProtocol
from ccbt.models import PeerInfo

# Initialize protocol (normally done via session manager)
protocol = IPFSProtocol()
protocol.config = get_config()

# Start protocol
await protocol.start()

# Add content to IPFS
content = b"Hello, IPFS!"
cid = await protocol.add_content(content)
print(f"Content added with CID: {cid}")

# Retrieve content
retrieved = await protocol.get_content(cid)
assert retrieved == content

# Pin content
await protocol.pin_content(cid)

# Connect to peer
peer_info = PeerInfo(
    ip="192.168.1.1",
    port=4001,
    peer_id=b"QmPeerId1234567890abcdefghijklmnopqrstuvwxyz"
)
await protocol.connect_peer(peer_info)

# Send message
await protocol.send_message(peer_info.peer_id.hex(), b"Hello from IPFS!")

# Receive message
message = await protocol.receive_message(peer_info.peer_id.hex())

# Stop protocol
await protocol.stop()
```

**Session Manager Integration:**
The IPFS protocol is automatically registered when the session manager starts (if IPFS is configured):

```python
from ccbt.session.session import AsyncSessionManager
from ccbt.models import Config, IPFSConfig

config = Config()
config.ipfs = IPFSConfig(
    api_url="http://127.0.0.1:5001",
    enable_pinning=True,
    enable_dht=True,
)

session = AsyncSessionManager(config)
await session.start()

# IPFS protocol is now available in session.protocols
ipfs_protocol = next(p for p in session.protocols if isinstance(p, IPFSProtocol))
```

## Discovery

### AsyncDHTClient

Enhanced DHT (BEP 5) client with full Kademlia implementation for peer discovery.

::: ccbt.discovery.dht.AsyncDHTClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- Kademlia DHT implementation: [ccbt/discovery/dht.py:AsyncDHTClient](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Full Kademlia routing table
- Peer discovery via DHT: [ccbt/discovery/dht.py:find_peers](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Iterative lookup for peer discovery
- Node routing table management: [ccbt/discovery/dht.py:DHTNode](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - IPv4/IPv6 node support with BEP 45 multi-address
- Token verification: [ccbt/discovery/dht.py:DHTToken](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Secure announce tokens
- Continuous refresh: [ccbt/discovery/dht.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Automatic routing table maintenance

**Key Methods:**
- `start()`: [ccbt/discovery/dht.py:start](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Start DHT client and bootstrap
- `stop()`: [ccbt/discovery/dht.py:stop](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Stop DHT client
- `find_peers()`: [ccbt/discovery/dht.py:find_peers](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Find peers for info hash
- `announce_peer()`: [ccbt/discovery/dht.py:announce_peer](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/dht.py) - Announce peer to DHT

**Configuration:** [ccbt.toml:118-125](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### AsyncTrackerClient

High-performance async tracker communication for peer discovery.

::: ccbt.discovery.tracker.AsyncTrackerClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- HTTP tracker support: [ccbt/discovery/tracker.py:AsyncTrackerClient](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Async HTTP tracker communication
- UDP tracker support: [ccbt/discovery/tracker_udp_client.py:AsyncUDPTrackerClient](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py) - Async UDP tracker communication
- Concurrent announces: [ccbt/discovery/tracker.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Multiple tracker announces in parallel
- DNS caching: [ccbt/discovery/tracker.py:DNSCache](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - TTL-based DNS cache for tracker hostnames
- Announce and scrape operations: [ccbt/discovery/tracker.py:announce](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Peer discovery and statistics

**Key Methods:**
- `announce()`: [ccbt/discovery/tracker.py:announce](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Announce torrent to tracker
- `scrape()`: [ccbt/discovery/tracker.py:scrape](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Scrape tracker for statistics
- `get_session()`: [ccbt/discovery/tracker.py:TrackerSession](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker.py) - Get or create tracker session

### AsyncUDPTrackerClient

Async UDP tracker client implementation (BEP 15).

::: ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- BEP 15 compliant: [ccbt/discovery/tracker_udp_client.py:AsyncUDPTrackerClient](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py) - Full UDP tracker protocol support
- Connection ID management: [ccbt/discovery/tracker_udp_client.py:TrackerSession](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py) - Tracks connection IDs per tracker
- Transaction ID tracking: [ccbt/discovery/tracker_udp_client.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py) - Handles concurrent requests

### TrackerServerHTTP

HTTP tracker server implementation.

Implementation: [ccbt/discovery/tracker_server_http.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_server_http.py)

### TrackerServerUDP

UDP tracker server implementation.

Implementation: [ccbt/discovery/tracker_server_udp.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/tracker_server_udp.py)

### PEX

Peer Exchange (BEP 11) for peer discovery.

Implementation: [ccbt/discovery/pex.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/discovery/pex.py)

Features:
- Peer exchange with other clients
- Automatic peer sharing
- PEX extension support

Configuration: [ccbt.toml:128-129](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

## Services

### Service Base

Base service class for service-oriented architecture.

Implementation: [ccbt/services/base.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/base.py)

Service states: [ccbt/services/base.py:ServiceState](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/base.py)


Service error: [ccbt/services/base.py:ServiceError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/base.py)


Service manager: [ccbt/services/base.py:ServiceManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/base.py)

### PeerService

Manages peer connections and communication.

Implementation: [ccbt/services/peer_service.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/peer_service.py)

Service exports: [ccbt/services/__init__.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/__init__.py)

### StorageService

Manages file system operations with high-performance chunked writes.

Implementation: [ccbt/services/storage_service.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/storage_service.py)

Features:
- File creation and management
- Data read/write operations with chunked writes for large files
- File assembly coordination
- Configurable file size limits via `disk.max_file_size_mb`
- Integration with DiskIOManager for optimized disk I/O

#### Write Operations

The `write_file()` method implements chunked writes for optimal performance:

- **Small files** (≤ `write_buffer_kib`): Written in a single operation
- **Large files** (> `write_buffer_kib`): Written in chunks using `DiskIOManager.write_block()`
- **Memory efficiency**: Uses `memoryview` for zero-copy chunk slicing
- **Size limits**: Enforces `max_file_size_mb` from configuration (0/None = unlimited)

Write implementation: [ccbt/services/storage_service.py:_write_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/storage_service.py)

#### Configuration

- `disk.max_file_size_mb`: Maximum file size in MB (0 or None = unlimited, max 1TB)
- `disk.write_buffer_kib`: Chunk size for large file writes
- Default: Unlimited (0) for production, configurable for testing

Configuration: [ccbt.toml:87-89](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### TrackerService

Handles tracker communication.

Implementation: [ccbt/services/tracker_service.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/tracker_service.py)

Features:
- Tracker registration
- Announce coordination
- Scrape operations

## Storage

### DiskIOManager

High-performance disk I/O manager with preallocation, batching, memory-mapped I/O, and async operations.

::: ccbt.storage.disk_io.DiskIOManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- File preallocation: [ccbt/storage/disk_io.py:preallocate_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Supports NONE, SPARSE, FULL, FALLOCATE strategies
- Write batching: [ccbt/storage/disk_io.py:write_block](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Priority queue for write requests
- Memory-mapped I/O: [ccbt/storage/disk_io.py:MmapCache](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Cached memory-mapped files for fast access
- io_uring support (Linux): [ccbt/storage/disk_io.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - High-performance async I/O on Linux
- Direct I/O support: [ccbt/storage/disk_io.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Bypass page cache for large files
- Parallel hash verification: [ccbt/storage/disk_io.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Thread pool for hash verification

**Key Methods:**
- `write_block()`: [ccbt/storage/disk_io.py:write_block](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Write data block to file with batching
- `read_block()`: [ccbt/storage/disk_io.py:read_block](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Read data block from file
- `preallocate_file()`: [ccbt/storage/disk_io.py:preallocate_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Preallocate file space
- `verify_piece()`: [ccbt/storage/disk_io.py:verify_piece](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Verify piece hash

**Configuration:** [ccbt.toml:57-96](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### FileAssembler

Assembles pieces into complete files.

Implementation: [ccbt/storage/file_assembler.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/file_assembler.py)

Features:
- Piece-to-file mapping
- File assembly coordination
- Multi-file torrent support

### CheckpointManager

Checkpoint management for resume functionality.

::: ccbt.storage.checkpoint.CheckpointManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- Checkpoint save/load
- Checkpoint validation
- Checkpoint cleanup
- Multiple format support (JSON, binary)

**Configuration:** [ccbt.toml:88-96](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

**Checkpoint Model:** [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)


### Buffers

Storage buffers for I/O operations.

Implementation: [ccbt/storage/buffers.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/buffers.py)

Features:
- Ring buffers
- Write buffers
- Read buffers

## Monitoring

### MetricsCollector

Advanced metrics collection system.

::: ccbt.monitoring.metrics_collector.MetricsCollector
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- System metrics collection: [ccbt/monitoring/metrics_collector.py:394](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- Performance metrics tracking: [ccbt/monitoring/metrics_collector.py:404](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- Custom metrics registration: [ccbt/monitoring/metrics_collector.py:190](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- Prometheus metrics export: [ccbt/utils/metrics.py:134](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/metrics.py)

See the [MetricsCollector](#metricscollector) section below for detailed usage.

### AlertManager

Rule-based alert system.

::: ccbt.monitoring.alert_manager.AlertManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- Alert rule engine: [ccbt/monitoring/alert_manager.py:AlertRule](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)
- Notification channels: [ccbt/monitoring/alert_manager.py:NotificationChannel](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)
- Alert escalation: [ccbt/monitoring/alert_manager.py]
- Alert suppression: [ccbt/monitoring/alert_manager.py]

**Alert Severity:** [ccbt/monitoring/alert_manager.py:AlertSeverity](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)


### DashboardManager

Dashboard management system.

Implementation: [ccbt/monitoring/dashboard.py:DashboardManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/dashboard.py)


Features:
- Dashboard creation: [ccbt/monitoring/dashboard.py:156](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/dashboard.py)
- Grafana export: [ccbt/monitoring/dashboard.py:366](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/dashboard.py)
- Widget system: [ccbt/monitoring/dashboard.py:WidgetType](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/dashboard.py)

Dashboard types: [ccbt/monitoring/dashboard.py:DashboardType](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/dashboard.py)

### TracingManager

Distributed tracing for performance analysis.

Implementation: [ccbt/monitoring/tracing.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/tracing.py)

Features:
- Span management: [ccbt/monitoring/tracing.py:Span](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/tracing.py)
- Trace correlation: [ccbt/monitoring/tracing.py:Trace](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/tracing.py)
- Performance profiling
- OpenTelemetry integration

Span status: [ccbt/monitoring/tracing.py:SpanStatus](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/tracing.py)

Span kind: [ccbt/monitoring/tracing.py:SpanKind](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/tracing.py)

## Security

### SecurityManager

Security management system.

Implementation: [ccbt/security/security_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/security/security_manager.py)

Features:
- Security policy enforcement
- Threat detection
- Security event handling

### Encryption

Protocol encryption support.

Implementation: [ccbt/security/encryption.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/security/encryption.py)

Configuration: [ccbt.toml:174](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### PeerValidator

Validates peer connections and behavior.

Implementation: [ccbt/security/peer_validator.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/security/peer_validator.py)

Configuration: [ccbt.toml:175](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### RateLimiter

Adaptive rate limiting for bandwidth management.

Implementation: [ccbt/security/rate_limiter.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/security/rate_limiter.py)

Configuration: [ccbt.toml:176](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### AnomalyDetector

Detects anomalous behavior patterns.

Implementation: [ccbt/security/anomaly_detector.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/security/anomaly_detector.py)

Features:
- Behavior pattern analysis
- Anomaly detection algorithms
- Threat scoring

## Machine Learning

### PeerSelector

ML-based peer selection.

Implementation: [ccbt/ml/peer_selector.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/ml/peer_selector.py)

Configuration: [ccbt.toml:181](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### PiecePredictor

ML-based piece prediction.

Implementation: [ccbt/ml/piece_predictor.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/ml/piece_predictor.py)

Configuration: [ccbt.toml:182](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### AdaptiveLimiter

ML-based adaptive rate limiting.

Implementation: [ccbt/ml/adaptive_limiter.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/ml/adaptive_limiter.py)

Features:
- Adaptive bandwidth allocation
- Performance-based adjustment
- Learning from usage patterns

## Extensions

### ExtensionManager

Manages BitTorrent protocol extensions (BEP 10) with automatic negotiation and feature detection.

Implementation: [ccbt/extensions/manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/manager.py)

**Features:**
- Extension negotiation: [ccbt/extensions/protocol.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/protocol.py) - BEP 10 extension handshake
- Extension registration: Register custom extensions
- Message routing: Route extension messages to handlers
- Feature detection: Detect peer capabilities

**Supported Extensions:**
- Fast Extension (BEP 6): [ccbt/extensions/fast.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/fast.py) - Reject requests for pieces we don't have
- Peer Exchange (BEP 11): [ccbt/extensions/pex.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/pex.py) - Exchange peer lists
- DHT Extension (BEP 5): [ccbt/extensions/dht.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/dht.py) - DHT port announcement
- Compact Extension: [ccbt/extensions/compact.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/compact.py) - Compact peer format
- WebSeed Extension: [ccbt/extensions/webseed.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/webseed.py) - HTTP seeding support

### FastExtension

Fast extension (BEP 6) support.

Implementation: [ccbt/extensions/fast.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/fast.py)

### WebSeedExtension

Web seed extension support.

Implementation: [ccbt/extensions/webseed.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/webseed.py)

### PEXExtension

Peer Exchange extension (BEP 11) support.

Implementation: [ccbt/extensions/pex.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/pex.py)

### DHTExtension

DHT extension (BEP 5) support.

Implementation: [ccbt/extensions/dht.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/dht.py)

### CompactExtension

Compact peer format extension support.

Implementation: [ccbt/extensions/compact.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/extensions/compact.py)

## Utilities

### Events

Event system for asynchronous component communication.

Implementation: [ccbt/utils/events.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py)

Event priority: [ccbt/utils/events.py:EventPriority](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py)


Event types: [ccbt/utils/events.py:EventType](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py)


Event model: [ccbt/utils/events.py:Event](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py)


Functions:
- `emit_event()`: [ccbt/utils/events.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py) - Emit event to subscribers
- `subscribe_to_event()`: [ccbt/utils/events.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py) - Subscribe to event type
- `unsubscribe_from_event()`: [ccbt/utils/events.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/events.py) - Unsubscribe from event type

Event-driven architecture supports decoupled component communication across the entire codebase.

### Exceptions

Exception hierarchy for error handling.

Implementation: [ccbt/utils/exceptions.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/exceptions.py)

Exception types:
- `CCBTException`: Base exception class
- `NetworkError`: Network-related errors
- `DiskError`: Disk I/O errors
- `ProtocolError`: Protocol violations
- `ValidationError`: Data validation errors
- `ConfigurationError`: Configuration errors
- `TorrentError`: Torrent-related errors

### LoggingConfig

Logging configuration and setup.

Implementation: [ccbt/utils/logging_config.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/logging_config.py)

Configuration: [ccbt.toml:156-160](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

### Metrics Utils

Metrics utility functions.

Implementation: [ccbt/utils/metrics.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/metrics.py)

Prometheus integration: [ccbt/utils/metrics.py:134](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/metrics.py)

### NetworkOptimizer

Network optimization utilities.

Implementation: [ccbt/utils/network_optimizer.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/network_optimizer.py)

Features:
- Network parameter optimization
- Connection tuning
- Performance analysis

### Resilience

Resilience and fault tolerance utilities.

Implementation: [ccbt/utils/resilience.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/resilience.py)

Features:
- Retry logic
- Circuit breaker patterns
- Error recovery

## Configuration

### ConfigManager

Configuration management with hot-reload, hierarchical loading, and validation.

::: ccbt.config.config.ConfigManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Features:**
- Configuration loading: [ccbt/config/config.py:_load_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- File discovery: [ccbt/config/config.py:_find_config_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- Environment variable parsing: [ccbt/config/config.py:_get_env_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- Hot reload support: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- CLI overrides: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/overrides.py)

**Configuration Precedence:**
1. Defaults from `ccbt/models.py:Config`
2. Config file (`ccbt.toml` in current directory or `~/.config/ccbt/ccbt.toml`)
3. Environment variables (`CCBT_*` prefix)
4. CLI arguments (via `apply_cli_overrides()`)
5. Per-torrent defaults
6. Per-torrent overrides

**Example Usage:**
```python
from ccbt.config.config import ConfigManager, get_config, init_config

# Initialize configuration
config_manager = init_config()

# Get current configuration
config = get_config()

# Access configuration sections
network_config = config.network
disk_config = config.disk
```

### Config Models

Pydantic-based configuration models.

Implementation: [ccbt/models.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

Configuration sections:
- `NetworkConfig`: [ccbt/models.py:NetworkConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `DiskConfig`: [ccbt/models.py:DiskConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `StrategyConfig`: [ccbt/models.py:StrategyConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `DiscoveryConfig`: [ccbt/models.py:DiscoveryConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `LimitsConfig`: [ccbt/models.py:LimitsConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `ObservabilityConfig`: [ccbt/models.py:ObservabilityConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `SecurityConfig`: [ccbt/models.py:SecurityConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `MLConfig`: [ccbt/models.py:MLConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)
- `DashboardConfig`: [ccbt/models.py:DashboardConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

Main config: [ccbt/models.py:Config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

### ConfigSchema

Configuration schema and validation.

Implementation: [ccbt/config/config_schema.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_schema.py)

### ConfigTemplates

Predefined configuration templates.

Implementation: [ccbt/config/config_templates.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Templates:
- High-performance setup
- Low-resource setup
- Security-focused setup
- Development setup

### ConfigMigration

Configuration migration utilities.

Implementation: [ccbt/config/config_migration.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_migration.py)

### ConfigBackup

Configuration backup utilities.

Implementation: [ccbt/config/config_backup.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_backup.py)

### ConfigDiff

Configuration diff utilities.

Implementation: [ccbt/config/config_diff.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_diff.py)

### ConfigCapabilities

Feature detection and capabilities.

Implementation: [ccbt/config/config_capabilities.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_capabilities.py)

### ConfigConditional

Conditional configuration support.

Implementation: [ccbt/config/config_conditional.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config_conditional.py)

## Plugins

### Plugin Base

Base plugin class for extensibility.

Implementation: [ccbt/plugins/base.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/plugins/base.py)

Plugin states: [ccbt/plugins/base.py:PluginState](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/plugins/base.py)


Plugin error: [ccbt/plugins/base.py:PluginError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/plugins/base.py)


### MetricsPlugin

Metrics collection plugin.

Implementation: [ccbt/plugins/metrics_plugin.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/plugins/metrics_plugin.py)

### LoggingPlugin

Logging plugin.

Implementation: [ccbt/plugins/logging_plugin.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/plugins/logging_plugin.py)

## Observability

### Profiler

Performance profiler for function-level, async, memory, and I/O profiling.

Implementation: [ccbt/observability/profiler.py:Profiler](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py)


Profile types: [ccbt/observability/profiler.py:ProfileType](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py)

Profile entry model: [ccbt/observability/profiler.py:ProfileEntry](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py)

Profile report model: [ccbt/observability/profiler.py:ProfileReport](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py)

Methods:
- `start()`: [ccbt/observability/profiler.py:93](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py) - Start profiling
- `stop()`: [ccbt/observability/profiler.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py) - Stop profiling
- `profile_function()`: [ccbt/observability/profiler.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py) - Profile a function
- `profile_async()`: [ccbt/observability/profiler.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py) - Profile async operations
- `get_report()`: [ccbt/observability/profiler.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/observability/profiler.py) - Get profiling report

Features:
- Function-level profiling with cProfile integration
- Async operation profiling
- Memory usage tracking
- I/O operation profiling
- Bottleneck detection

## Interface

### Terminal Dashboard (Bitonic)

Textual-based terminal dashboard for real-time monitoring.

Implementation: [ccbt/interface/terminal_dashboard.py:TerminalDashboard](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)


Initialization: [ccbt/interface/terminal_dashboard.py:299](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)

Layout composition: [ccbt/interface/terminal_dashboard.py:321](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)

Key bindings: [ccbt/interface/terminal_dashboard.py:337](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)

Widgets:
- `Overview`: Global statistics overview
- `SpeedSparklines`: Real-time speed graphs
- `TorrentsTable`: Active torrents table
- `PeersTable`: Connected peers table
- `RichLog`: Logging output

Methods:
- `compose()`: [ccbt/interface/terminal_dashboard.py:321](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py) - Compose dashboard layout
- `on_mount()`: [ccbt/interface/terminal_dashboard.py:346](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py) - Initialize dashboard
- `_poll_once()`: [ccbt/interface/terminal_dashboard.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py) - Poll session for updates
- `_schedule_poll()`: [ccbt/interface/terminal_dashboard.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py) - Schedule periodic polling

Entry point: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)

Entry point configuration: [pyproject.toml:81](https://github.com/ccBitTorrent/ccbt/blob/main/pyproject.toml)

## CLI Components

### Interactive CLI

Interactive command-line interface.

Implementation: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/interactive.py)


Features:
- Interactive command processing
- Command history
- Auto-completion
- Session management integration

### CLI Progress Display

Progress bar and status display utilities.

Implementation: [ccbt/cli/progress.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/progress.py)

Features:
- Download progress bars
- Speed indicators
- ETA calculations
- Multi-torrent progress display

## Checkpoint Management

### CheckpointManager

Comprehensive checkpoint management for resume functionality with JSON and binary format support.

**Key Methods:**
- `save_checkpoint()`: [ccbt/storage/checkpoint.py:save_checkpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/checkpoint.py) - Save checkpoint with format selection (JSON, binary, or both)
- `load_checkpoint()`: [ccbt/storage/checkpoint.py:load_checkpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/checkpoint.py) - Load checkpoint from disk
- `list_checkpoints()`: [ccbt/storage/checkpoint.py:list_checkpoints](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/checkpoint.py) - List all available checkpoints
- `delete_checkpoint()`: [ccbt/storage/checkpoint.py:delete_checkpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/checkpoint.py) - Delete checkpoint file
- `validate_checkpoint()`: [ccbt/storage/checkpoint.py:validate_checkpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/checkpoint.py) - Validate checkpoint integrity

**Checkpoint Data:**
- Piece states: Tracks which pieces are verified, complete, or missing
- File progress: Per-file download progress for multi-file torrents
- Download statistics: Bytes downloaded, uploaded, speed, etc.
- Torrent metadata: Info hash, name, file paths

### Checkpoint Models

Checkpoint data models.

Implementation: [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

Properties:
- `info_hash`: Torrent info hash
- `torrent_name`: Torrent name
- `verified_pieces`: List of verified piece indices
- `piece_states`: Piece state mapping
- `torrent_file_path`: Original torrent file path
- `magnet_uri`: Original magnet URI

See the [CheckpointManager](#checkpointmanager) section below for detailed usage.

## Session Resume Methods

Resume functionality methods in AsyncSessionManager:

- `resume_from_checkpoint()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - Resume from checkpoint
- `list_resumable_checkpoints()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - List resumable checkpoints
- `find_checkpoint_by_name()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - Find checkpoint by name
- `get_checkpoint_info()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - Get checkpoint information
- `validate_checkpoint()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - Validate checkpoint
- `cleanup_completed_checkpoints()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - Cleanup completed checkpoints

CLI checkpoint commands: [ccbt/cli/main.py:checkpoints](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/main.py)

## CLI Integration

All API functionality is accessible via the CLI:

- Download commands: [ccbt/cli/main.py:download](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/main.py)
- Magnet commands: [ccbt/cli/main.py:magnet](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/main.py)
- Checkpoint commands: [ccbt/cli/main.py:checkpoints](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/main.py)
- Monitoring commands: [ccbt/cli/monitoring_commands.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)
- Advanced commands: [ccbt/cli/advanced_commands.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

See [btbt CLI Reference](btbt-cli.md) for complete CLI documentation.

## Data Models

Comprehensive data models for all components with Pydantic validation.

Implementation: [ccbt/models.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

### Enumerations

- `LogLevel`: Logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `PieceSelectionStrategy`: Piece selection algorithms (ROUND_ROBIN, RAREST_FIRST, SEQUENTIAL)
- `PreallocationStrategy`: File preallocation (NONE, SPARSE, FULL, FALLOCATE)
- `PieceState`: Piece download states (MISSING, REQUESTED, DOWNLOADING, COMPLETE, VERIFIED)
- `ConnectionState`: Peer connection states
- `CheckpointFormat`: Checkpoint formats (JSON, BINARY, BOTH)
- `MessageType`: BitTorrent message types

See [ccbt/models.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py) for enum and class definitions.

### Core Models

- `PeerInfo`: Peer information with IP, port, peer_id
- `TrackerResponse`: Tracker announce response
- `PieceInfo`: Piece information with index, length, hash, state
- `FileInfo`: File information with name, length, path
- `TorrentInfo`: Complete torrent metadata

### Configuration Models

- `NetworkConfig`: Network settings with validation

- `DiskConfig`: [ccbt/models.py:DiskConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Disk I/O settings

- `StrategyConfig`: [ccbt/models.py:StrategyConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Piece selection strategy

- `DiscoveryConfig`: [ccbt/models.py:DiscoveryConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Tracker and DHT settings

- `LimitsConfig`: [ccbt/models.py:LimitsConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Rate limiting configuration

- `ObservabilityConfig`: [ccbt/models.py:ObservabilityConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Monitoring and logging

- `SecurityConfig`: [ccbt/models.py:SecurityConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Security features

- `MLConfig`: [ccbt/models.py:MLConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Machine learning features

- `DashboardConfig`: [ccbt/models.py:DashboardConfig](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Dashboard settings

- `Config`: [ccbt/models.py:Config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Main configuration aggregating all sections

### Checkpoint Models

- `TorrentCheckpoint`: [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Complete checkpoint data with resume metadata
- `FileCheckpoint`: [ccbt/models.py:FileCheckpoint](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - File-level checkpoint information
- `DownloadStats`: [ccbt/models.py:DownloadStats](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py) - Download statistics in checkpoint

### Validation

All models use Pydantic field validators: [ccbt/models.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

Field constraints include:
- Range validation (ge, le, gt, lt)
- String length validation
- IP address format validation
- Type coercion and validation

## Module Exports

Public API exports: [ccbt/__init__.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__init__.py)

Key exports:
- `AsyncSessionManager`: [ccbt/__init__.py:94](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__init__.py)
- `ConfigManager`: [ccbt/__init__.py]
- `TorrentParser`: [ccbt/__init__.py]
- Utility modules

## Best Practices

### Resource Management

Use async context managers where available. See [ccbt/session/session.py:AsyncSessionManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py)

### Error Handling

Handle exceptions appropriately:
- [ccbt/utils/exceptions.py:CCBTException](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/exceptions.py) - Base exception
- [ccbt/utils/exceptions.py:NetworkError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/exceptions.py) - Network errors
- [ccbt/utils/exceptions.py:DiskError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/exceptions.py) - Disk errors
- [ccbt/utils/exceptions.py:ProtocolError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/utils/exceptions.py) - Protocol errors

### Async Operations

All I/O operations are asynchronous. Always use `await`:
- Session operations: [ccbt/session/session.py:AsyncSessionManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py)
- Peer operations: [ccbt/peer/async_peer_connection.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)
- Piece operations: [ccbt/piece/async_piece_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)
- Storage operations: [ccbt/storage/disk_io.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/storage/disk_io.py)

### Configuration

Access configuration via ConfigManager: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)

Configuration file: [ccbt.toml](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

Environment variables: [env.example](https://github.com/ccBitTorrent/ccbt/blob/main/env.example)

### Monitoring

Enable monitoring for production use:
- Metrics: [ccbt.toml:164](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)
- Alerts: [ccbt.toml:170](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)
- Tracing: [ccbt.toml:168](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml)

See the [Monitoring](#monitoring) section below for detailed setup.

## Helper Functions and Utilities

### Torrent Builder Functions

- `build_minimal_torrent_data()`: [ccbt/core/magnet.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py) - Build minimal torrent from magnet info
- `build_torrent_data_from_metadata()`: [ccbt/core/magnet.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py) - Build torrent from metadata exchange

### Configuration Helpers

- `get_config()`: [ccbt/config/config.py:get_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py) - Get current configuration
- `init_config()`: [ccbt/config/config.py:init_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py) - Initialize configuration from file/environment

### Service Helpers

- `get_service_manager()`: [ccbt/services/base.py:get_service_manager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/services/base.py) - Get service manager instance
- `get_alert_manager()`: [ccbt/monitoring/__init__.py:get_alert_manager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/monitoring/__init__.py) - Get alert manager instance

### Metadata Exchange

- `fetch_metadata_from_peers()`: [ccbt/piece/async_metadata_exchange.py:fetch_metadata_from_peers](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py) - Fetch metadata for magnet links

## Module Structure

### Package Exports

Public API: [ccbt/__init__.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__init__.py)

Key exports defined in `__all__`: [ccbt/__init__.py:108](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__init__.py)

Includes:
- Core classes: `AsyncSessionManager`, `TorrentParser`, `BencodeEncoder`, `BencodeDecoder`
- Configuration: `Config`, `ConfigManager`
- Models: `MagnetInfo`
- Modules: All utility and component modules

Lazy attribute access: [ccbt/__init__.py:160](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__init__.py) - Supports dynamic imports

### Type Safety

Type marker file: [ccbt/py.typed](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/py.typed) - Indicates package supports type checking

All modules use comprehensive type hints with:
- Type annotations for all functions and methods
- Generic types where appropriate
- Pydantic models for runtime validation
- Protocol definitions for interfaces

## BitTorrent Protocol v2 (BEP 52) API

### TorrentV2Parser

Main class for BitTorrent Protocol v2 operations.

Implementation: [ccbt/core/torrent_v2.py:TorrentV2Parser](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent_v2.py)

#### Methods

**`parse_v2(info_dict: dict, torrent_data: dict) -> TorrentV2Info`**

Parse v2-only torrent metadata.

- **Parameters:**
  - `info_dict`: Bencoded info dictionary from torrent file
  - `torrent_data`: Complete torrent data dictionary
- **Returns:** `TorrentV2Info` object with parsed metadata
- **Raises:** `ValueError` if parsing fails or metadata is invalid

**`parse_hybrid(info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]`**

Parse hybrid torrent (both v1 and v2 metadata).

- **Returns:** Tuple of (v1 TorrentInfo, v2 TorrentV2Info)
- **Raises:** `ValueError` if metadata is incomplete or invalid

**`generate_v2_torrent(...) -> bytes`**

Generate v2-only torrent file.

Parameters:
- `source: Path` - Source file or directory
- `output: Path | None = None` - Output torrent file path
- `trackers: list[str] | None = None` - Tracker announce URLs
- `web_seeds: list[str] | None = None` - WebSeed URLs
- `comment: str | None = None` - Torrent comment
- `created_by: str = "ccBitTorrent"` - Creator name
- `piece_length: int | None = None` - Piece length (auto-calculated if None)
- `private: bool = False` - Private torrent flag

Returns: Bencoded torrent file as bytes

**`generate_hybrid_torrent(...) -> bytes`**

Generate hybrid torrent compatible with both v1 and v2.

Parameters: Same as `generate_v2_torrent()`

Returns: Bencoded hybrid torrent file as bytes

### TorrentV2Info

Data model for v2 torrent metadata.

Implementation: [ccbt/core/torrent_v2.py:TorrentV2Info](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent_v2.py)

#### Attributes

- `name: str` - Torrent name
- `info_hash_v2: bytes` - 32-byte SHA-256 info hash
- `info_hash_v1: bytes | None` - 20-byte SHA-1 info hash (hybrid only)
- `announce: str` - Primary tracker URL
- `announce_list: list[list[str]] | None` - Tracker tiers
- `comment: str | None` - Torrent comment
- `created_by: str | None` - Creator name
- `creation_date: int | None` - Unix timestamp
- `encoding: str | None` - Character encoding
- `is_private: bool` - Private torrent flag
- `file_tree: dict[str, FileTreeNode]` - Hierarchical file structure
- `piece_layers: dict[bytes, PieceLayer]` - Piece layer hashes
- `piece_length: int` - Piece length in bytes
- `files: list[FileInfo]` - List of files in torrent
- `total_length: int` - Total size in bytes
- `num_pieces: int` - Total number of pieces

#### Methods

**`get_file_paths() -> list[str]`**

Get list of all file paths in torrent.

**`get_piece_layer(pieces_root: bytes) -> PieceLayer | None`**

Get piece layer for a specific file by its pieces root hash.

### Protocol Communication

Implementation: [ccbt/protocols/bittorrent_v2.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/protocols/bittorrent_v2.py)

#### Protocol Version Detection

**`detect_protocol_version(handshake: bytes) -> ProtocolVersion`**

Detect BitTorrent protocol version from handshake.

- **Returns:** `ProtocolVersion.V1`, `ProtocolVersion.V2`, or `ProtocolVersion.HYBRID`
- **Raises:** `ProtocolVersionError` if handshake is invalid

**`parse_v2_handshake(data: bytes) -> dict[str, Any]`**

Parse v2 or hybrid handshake into components.

Returns dictionary with keys:
- `protocol: bytes` - Protocol string
- `reserved_bytes: bytes` - Reserved bytes
- `info_hash_v1: bytes | None` - v1 hash (if present)
- `info_hash_v2: bytes` - v2 hash
- `peer_id: bytes` - Peer ID
- `version: ProtocolVersion` - Detected version

#### Handshake Creation

**`create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes`**

Create v2 handshake (80 bytes).

- **Parameters:**
  - `info_hash_v2`: 32-byte SHA-256 hash
  - `peer_id`: 20-byte peer ID
- **Raises:** `ProtocolVersionError` if lengths are invalid

**`create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes`**

Create hybrid handshake (100 bytes).

- **Parameters:**
  - `info_hash_v1`: 20-byte SHA-1 hash
  - `info_hash_v2`: 32-byte SHA-256 hash
  - `peer_id`: 20-byte peer ID

#### Protocol Negotiation

**`negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None`**

Negotiate protocol version with peer.

- **Parameters:**
  - `handshake`: Peer's handshake bytes
  - `supported`: List of versions we support (in priority order)
- **Returns:** Negotiated version or None if incompatible

#### Async Communication

**`async send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None`**

Send v2 handshake asynchronously.

**`async send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None`**

Send hybrid handshake asynchronously.

**`async handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]`**

Receive and validate v2 handshake.

Returns: (protocol_version, peer_id, parsed_handshake)

**`async upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool`**

Attempt to upgrade v1 connection to v2.

Returns: True if upgrade successful, False otherwise

#### V2 Messages

**PieceLayerRequest (Message ID 20)**

Request piece layer hashes for a file.

```python
request = PieceLayerRequest(pieces_root)
data = request.serialize()  # Returns bytes with length prefix
```

**PieceLayerResponse (Message ID 21)**

Respond with piece layer hashes.

```python
response = PieceLayerResponse(pieces_root, piece_hashes)
data = response.serialize()
```

**FileTreeRequest (Message ID 22)**

Request complete file tree structure.

```python
request = FileTreeRequest()
data = request.serialize()
```

**FileTreeResponse (Message ID 23)**

Send file tree structure (bencoded).

```python
response = FileTreeResponse(file_tree_bencoded)
data = response.serialize()
```

### SHA-256 Hashing

Implementation: [ccbt/piece/hash_v2.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/hash_v2.py)

#### Piece Hashing

**`hash_piece_v2(data: bytes) -> bytes`**

Hash piece data using SHA-256.

Returns: 32-byte hash

**`hash_piece_v2_streaming(data_source: bytes | IO) -> bytes`**

Hash piece data from file or stream.

**`verify_piece_v2(data: bytes, expected_hash: bytes) -> bool`**

Verify piece hash.

**`verify_piece_v2_streaming(data_source: bytes | IO, expected_hash: bytes) -> bool`**

Verify piece hash from stream.

#### Merkle Tree Hashing

**`hash_piece_layer(piece_hashes: list[bytes]) -> bytes`**

Build Merkle tree from piece hashes.

Returns: 32-byte root hash (pieces_root)

**`verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool`**

Verify piece layer against expected root.

#### File Tree Hashing

**`hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes`**

Hash file tree structure.

Returns: 32-byte file tree root hash

### Configuration

Protocol v2 settings in `ProtocolV2Config`:

Implementation: [ccbt/models.py:ProtocolV2Config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/models.py)

Attributes:
- `enable_protocol_v2: bool = True` - Enable v2 support
- `prefer_protocol_v2: bool = False` - Prefer v2 over v1
- `support_hybrid: bool = True` - Support hybrid torrents
- `v2_handshake_timeout: float = 30.0` - Handshake timeout

Access via: `config.network.protocol_v2`

Environment variables:
- `CCBT_PROTOCOL_V2_ENABLE`
- `CCBT_PROTOCOL_V2_PREFER`
- `CCBT_PROTOCOL_V2_SUPPORT_HYBRID`
- `CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT`

### CLI Commands

**Create v2 torrent:**
```bash
ccbt create-torrent file.mp4 --v2 --output file.torrent --tracker http://tracker.example.com/announce
```

**Create hybrid torrent:**
```bash
ccbt create-torrent directory/ --hybrid --output directory.torrent
```

**Enable v2 protocol:**
```bash
ccbt download file.torrent --protocol-v2
```

See [BEP 52 Guide](bep52.md) for comprehensive documentation and examples.

## Additional Resources

- [Getting Started](getting-started.md) - Quick start guide
- [Configuration Guide](configuration.md) - Detailed configuration
- [Performance Tuning](performance.md) - Performance optimization
- [Monitoring](#monitoring) - Observability and metrics
- [Bitonic Guide](bitonic.md) - Terminal dashboard
- [btbt CLI Reference](btbt-cli.md) - CLI documentation
- [BEP 52: Protocol v2](bep52.md) - BitTorrent Protocol v2 guide