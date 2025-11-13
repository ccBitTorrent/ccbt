# ccBT API Reference

Comprehensive API documentation for ccBitTorrent with references to actual implementation files.

## Entry Points

### Main Entry Point (ccbt)

Main command-line entry point for basic torrent operations.

Implementation: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)

Features:
- Single torrent download mode
- Daemon mode for multi-torrent sessions: [ccbt/__main__.py:52](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L52)
- Magnet URI support: [ccbt/__main__.py:73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L73)
- Tracker announcement: [ccbt/__main__.py:89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L89)

Entry point configuration: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)

### Async Download Helpers

High-performance async helpers and download manager for advanced operations.

Implementation: [ccbt/session/download_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/download_manager.py)

Key exports:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

### AsyncDownloadManager

High-performance async download manager for individual torrents.

Implementation: [ccbt/session/download_manager.py:AsyncDownloadManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/download_manager.py)

Methods:
- `__init__()`: [ccbt/session/async_main.py:41](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L41) - Initialize with torrent data
- `start()`: [ccbt/session/async_main.py:110](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L110) - Start download manager
- `stop()`: [ccbt/session/async_main.py:115](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L115) - Stop download manager
- `start_download()`: [ccbt/session/async_main.py:122](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L122) - Start download with peers

Features:
- Peer connection management via AsyncPeerConnectionManager: [ccbt/session/async_main.py:127](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L127)
- Piece management via AsyncPieceManager: [ccbt/session/async_main.py:94](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L94)
- Callback system for events: [ccbt/session/async_main.py:103](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/async_main.py#L103)

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

- `parse()`: [ccbt/core/torrent.py:34](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/torrent.py#L34) - Parse torrent file from path or URL
- `_validate_torrent()`: [ccbt/core/torrent.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/torrent.py) - Validate torrent structure
- `_extract_torrent_data()`: [ccbt/core/torrent.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/torrent.py) - Extract and process torrent data

#### Bencode Encoding/Decoding

Bencode codec for BitTorrent protocol (BEP 3).

**Classes:**

- `BencodeDecoder`: [ccbt/core/bencode.py:BencodeDecoder](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L24) - Decoder for bencoded data
- `BencodeEncoder`: [ccbt/core/bencode.py:BencodeEncoder](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L156) - Encoder for Python objects to bencode

**Functions:**
- `decode()`: [ccbt/core/bencode.py:decode](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L221) - Decode bencoded bytes to Python object
- `encode()`: [ccbt/core/bencode.py:encode](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L227) - Encode Python object to bencode format

**Supported Types:**
- Integers: `i<number>e`
- Strings: `<length>:<data>`
- Lists: `l<items>e`
- Dictionaries: `d<key-value pairs>e`

**Exceptions:**
- `BencodeDecodeError`: [ccbt/core/bencode.py:BencodeDecodeError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L16) - Decoding errors
- `BencodeEncodeError`: [ccbt/core/bencode.py:BencodeEncodeError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/bencode.py#L20) - Encoding errors

#### Magnet URI Parsing

Parses magnet URIs (BEP 9) with BEP 53 file selection support.

**Functions:**
- `parse_magnet()`: [ccbt/core/magnet.py:parse_magnet](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py#L178) - Parse magnet URI and extract components

**Data Model:**
- `MagnetInfo`: [ccbt/core/magnet.py:MagnetInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py#L17) - Magnet info data model with BEP 53 support

**Features:**
- Info hash extraction: [ccbt/core/magnet.py:_hex_or_base32_to_bytes](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py#L28) - Supports hex (40 chars) and base32 (32 chars)
- Tracker URLs: Extracts `tr` parameters
- Web seeds: Extracts `ws` parameters
- BEP 53 file selection: [ccbt/core/magnet.py:_parse_index_list](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py#L40) - Parses `so` (selected) and `x.pe` (prioritized) parameters
- Display name: Extracts `dn` parameter

**Helper Functions:**
- `build_minimal_torrent_data()`: [ccbt/core/magnet.py:build_minimal_torrent_data](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py) - Build minimal torrent from magnet info
- `build_torrent_data_from_metadata()`: [ccbt/core/magnet.py:build_torrent_data_from_metadata](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py) - Build torrent from metadata exchange

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

Constructor: [ccbt/session/session.py:608](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L608)

--8<-- "ccbt/session/session.py:608:620"

#### Lifecycle Methods

- `start()`: [ccbt/session/session.py:637](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L637) - Start the async session manager

  --8<-- "ccbt/session/session.py:637:655"

- `stop()`: [ccbt/session/session.py:657](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L657) - Stop the async session manager

  --8<-- "ccbt/session/session.py:657:682"

#### Torrent Management

- `add_torrent()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Add torrent file
- `add_magnet()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Add magnet link
- `remove()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Remove torrent
- `pause_torrent()`: [ccbt/session/session.py:684](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L684) - Pause torrent
- `resume_torrent()`: [ccbt/session/session.py:701](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L701) - Resume torrent
- `set_rate_limits()`: [ccbt/session/session.py:715](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L715) - Set per-torrent rate limits

#### Status and Monitoring

- `get_global_stats()`: [ccbt/session/session.py:739](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L739) - Aggregate global statistics
- `get_status()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Get status for all or specific torrent
- `get_peers_for_torrent()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Get peers for a torrent

#### Advanced Operations

- `force_announce()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Force tracker announce
- `force_scrape()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Force tracker scrape
- `refresh_pex()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Refresh peer exchange
- `rehash_torrent()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Rehash torrent
- `export_session_state()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Export session state

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

**Key Methods:**

- `start()`: [ccbt/session/session.py:start](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L400) - Start torrent session, initialize download manager, trackers, and PEX
- `stop()`: [ccbt/session/session.py:stop](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L678) - Stop torrent session, save checkpoint, cleanup resources
- `pause()`: [ccbt/session/session.py:pause](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Pause download
- `resume()`: [ccbt/session/session.py:resume](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Resume download
- `get_status()`: [ccbt/session/session.py:get_status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Get torrent status

**Components:**
- `download_manager`: [ccbt/session/session.py:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L78) - AsyncDownloadManager for piece management
- `file_selection_manager`: [ccbt/session/session.py:86](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L86) - FileSelectionManager for multi-file torrents
- `piece_manager`: [ccbt/session/session.py:92](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L92) - AsyncPieceManager for piece selection
- `checkpoint_manager`: [ccbt/session/session.py:102](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L102) - CheckpointManager for resume functionality

**Data Model:** [ccbt/session/session.py:TorrentSessionInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L47)


## Peer Management

### Peer

Represents a peer connection.

Implementation: [ccbt/peer/peer.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/peer.py)

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

Implementation: [ccbt/peer/peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/peer_connection.py)

### ConnectionPool

Connection pool for managing peer connections.

Implementation: [ccbt/peer/connection_pool.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/connection_pool.py)

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

**Features:**
- Rarest-first piece selection
- Sequential piece selection
- Round-robin piece selection
- Endgame mode with duplicate requests
- File selection integration: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py#L308) - Filters pieces based on file selection state

**Configuration:** [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

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

Features:
- File selection state management: [ccbt/piece/file_selection.py:FileSelectionState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L31) - Tracks selection, priority, and progress per file
- File priority system: [ccbt/piece/file_selection.py:FilePriority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L18) - Priority levels (DO_NOT_DOWNLOAD, LOW, NORMAL, HIGH, MAXIMUM)
- Piece-to-file mapping: [ccbt/piece/file_selection.py:PieceToFileMapper](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L49) - Efficient bidirectional mapping between pieces and files
- Piece filtering: [ccbt/piece/file_selection.py:is_piece_needed](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L249) - Determines if a piece should be downloaded based on file selection
- Priority-based piece selection: [ccbt/piece/file_selection.py:get_piece_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L268) - Calculates piece priority from file priorities
- Progress tracking: [ccbt/piece/file_selection.py:update_file_progress](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L317) - Updates download progress per file

Key Methods:
- `select_file(file_index)`: [ccbt/piece/file_selection.py:select_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L142) - Select a file for download
- `deselect_file(file_index)`: [ccbt/piece/file_selection.py:deselect_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L159) - Deselect a file from download
- `set_file_priority(file_index, priority)`: [ccbt/piece/file_selection.py:set_file_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L177) - Set file download priority
- `is_piece_needed(piece_index)`: [ccbt/piece/file_selection.py:is_piece_needed](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L249) - Check if a piece is needed based on file selection
- `get_piece_priority(piece_index)`: [ccbt/piece/file_selection.py:get_piece_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L268) - Get priority for a piece based on file priorities
- `get_statistics()`: [ccbt/piece/file_selection.py:get_statistics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/file_selection.py#L359) - Get file selection statistics

Integration:
- Integrated with `AsyncPieceManager`: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py#L94) - File selection manager passed during initialization
- Integrated with `AsyncTorrentSession`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L182) - Automatically created for multi-file torrents
- Checkpoint persistence: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L637) - File selection state saved/restored in checkpoints

### PieceManager

Synchronous piece manager (legacy).

Implementation: [ccbt/piece/piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/piece_manager.py)

### AsyncMetadataExchange

Parallel metadata fetching with reliability scoring.

Implementation: [ccbt/piece/async_metadata_exchange.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_metadata_exchange.py)

Features:
- Concurrent metadata fetching from multiple peers
- Reliability scoring
- Failure handling

### MetadataExchange

Synchronous metadata exchange (legacy).

Implementation: [ccbt/piece/metadata_exchange.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/metadata_exchange.py)

## Protocols

### BaseProtocol

Base protocol implementation.

Implementation: [ccbt/protocols/base.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/base.py)

Protocol types: [ccbt/protocols/base.py:ProtocolType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/base.py#L25)


Protocol states: [ccbt/protocols/base.py:ProtocolState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/base.py#L34)


### BitTorrentProtocol

Standard BitTorrent protocol implementation.

Implementation: [ccbt/protocols/bittorrent.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/bittorrent.py)

Features:
- BitTorrent protocol message handling
- Handshake negotiation
- Piece requests and responses

### HybridProtocol

Hybrid protocol supporting multiple transport methods.

Implementation: [ccbt/protocols/hybrid.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/hybrid.py)

### WebTorrentProtocol

WebTorrent protocol support.

Implementation: [ccbt/protocols/webtorrent.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/webtorrent.py)

### IPFSProtocol

IPFS protocol integration for decentralized content addressing and peer-to-peer networking.

Implementation: [ccbt/protocols/ipfs.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py)

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

**Methods:**

- `start()`: [ccbt/protocols/ipfs.py:127](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L127)
  - Connect to IPFS daemon and initialize protocol
  - Verifies connection by querying node ID
  - Sets protocol state to CONNECTED

- `stop()`: [ccbt/protocols/ipfs.py:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L151)
  - Disconnect from IPFS daemon and cleanup resources
  - Closes all peer connections
  - Sets protocol state to DISCONNECTED

- `connect_peer(peer_info: PeerInfo) -> bool`: [ccbt/protocols/ipfs.py:300](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L300)
  - Connect to an IPFS peer using multiaddr format
  - Parses peer multiaddr and validates peer ID
  - Sets up message listener for peer communication
  - Returns `True` on success, `False` on failure

- `disconnect_peer(peer_id: str) -> None`: [ccbt/protocols/ipfs.py:450](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L450)
  - Disconnect from an IPFS peer
  - Cleans up message queues and listeners

- `send_message(peer_id: str, message: bytes) -> bool`: [ccbt/protocols/ipfs.py:470](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L470)
  - Send message to IPFS peer via pubsub
  - Creates topic from peer_id: `/ccbt/peer/{peer_id}`
  - Validates message size (max 1MB)
  - Returns `True` on success, `False` on failure

- `receive_message(peer_id: str) -> bytes | None`: [ccbt/protocols/ipfs.py:519](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L519)
  - Receive message from IPFS peer
  - Waits up to 1 second for message from peer queue
  - Returns message bytes or `None` if timeout

- `announce_torrent(torrent_info: TorrentInfo) -> list[PeerInfo]`: [ccbt/protocols/ipfs.py:550](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L550)
  - Announce torrent to IPFS network
  - Converts torrent to IPFS content (CID)
  - Discovers peers providing the content via DHT
  - Returns list of peer information

- `scrape_torrent(torrent_info: TorrentInfo) -> dict[str, int]`: [ccbt/protocols/ipfs.py:799](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L799)
  - Scrape torrent statistics from IPFS network
  - Returns dict with `seeders`, `leechers`, `completed` counts
  - Uses content statistics from IPFS object stats

- `add_content(data: bytes) -> str`: [ccbt/protocols/ipfs.py:882](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L882)
  - Add content to IPFS and return CID
  - Automatically pins content if `enable_pinning` is `True`
  - Returns CID string or empty string on failure

- `get_content(cid: str) -> bytes | None`: [ccbt/protocols/ipfs.py:962](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L962)
  - Retrieve content from IPFS by CID
  - Uses IPFS daemon `cat` command
  - Updates content tracking with access time
  - Returns content bytes or `None` if not found

- `pin_content(cid: str) -> bool`: [ccbt/protocols/ipfs.py:1012](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1012)
  - Pin content in IPFS to prevent garbage collection
  - Returns `True` on success, `False` on failure

- `unpin_content(cid: str) -> bool`: [ccbt/protocols/ipfs.py:1035](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1035)
  - Unpin content from IPFS
  - Returns `True` on success, `False` on failure

- `get_ipfs_peers() -> list[str]`: [ccbt/protocols/ipfs.py:1058](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1058)
  - Get list of connected IPFS peer IDs
  - Returns list of peer ID strings

- `get_ipfs_content() -> dict[str, IPFSContent]`: [ccbt/protocols/ipfs.py:1065](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1065)
  - Get all tracked IPFS content
  - Returns dict mapping CID to IPFSContent objects

- `get_content_stats(cid: str) -> dict[str, int]`: [ccbt/protocols/ipfs.py:1072](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1072)
  - Get statistics for specific content
  - Returns dict with `seeders`, `leechers`, `completed`

- `get_all_content_stats() -> dict[str, dict[str, int]]`: [ccbt/protocols/ipfs.py:1080](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/ipfs.py#L1080)
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
- Kademlia DHT implementation: [ccbt/discovery/dht.py:AsyncDHTClient](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py#L272) - Full Kademlia routing table
- Peer discovery via DHT: [ccbt/discovery/dht.py:find_peers](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Iterative lookup for peer discovery
- Node routing table management: [ccbt/discovery/dht.py:DHTNode](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py#L38) - IPv4/IPv6 node support with BEP 45 multi-address
- Token verification: [ccbt/discovery/dht.py:DHTToken](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py#L138) - Secure announce tokens
- Continuous refresh: [ccbt/discovery/dht.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Automatic routing table maintenance

**Key Methods:**
- `start()`: [ccbt/discovery/dht.py:start](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Start DHT client and bootstrap
- `stop()`: [ccbt/discovery/dht.py:stop](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Stop DHT client
- `find_peers()`: [ccbt/discovery/dht.py:find_peers](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Find peers for info hash
- `announce_peer()`: [ccbt/discovery/dht.py:announce_peer](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/dht.py) - Announce peer to DHT

**Configuration:** [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)

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
- HTTP tracker support: [ccbt/discovery/tracker.py:AsyncTrackerClient](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py#L119) - Async HTTP tracker communication
- UDP tracker support: [ccbt/discovery/tracker_udp_client.py:AsyncUDPTrackerClient](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_udp_client.py#L80) - Async UDP tracker communication
- Concurrent announces: [ccbt/discovery/tracker.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py) - Multiple tracker announces in parallel
- DNS caching: [ccbt/discovery/tracker.py:DNSCache](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py#L30) - TTL-based DNS cache for tracker hostnames
- Announce and scrape operations: [ccbt/discovery/tracker.py:announce](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py) - Peer discovery and statistics

**Key Methods:**
- `announce()`: [ccbt/discovery/tracker.py:announce](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py) - Announce torrent to tracker
- `scrape()`: [ccbt/discovery/tracker.py:scrape](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py) - Scrape tracker for statistics
- `get_session()`: [ccbt/discovery/tracker.py:TrackerSession](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker.py#L106) - Get or create tracker session

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
- BEP 15 compliant: [ccbt/discovery/tracker_udp_client.py:AsyncUDPTrackerClient](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_udp_client.py#L80) - Full UDP tracker protocol support
- Connection ID management: [ccbt/discovery/tracker_udp_client.py:TrackerSession](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_udp_client.py#L63) - Tracks connection IDs per tracker
- Transaction ID tracking: [ccbt/discovery/tracker_udp_client.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_udp_client.py) - Handles concurrent requests

### TrackerServerHTTP

HTTP tracker server implementation.

Implementation: [ccbt/discovery/tracker_server_http.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_server_http.py)

### TrackerServerUDP

UDP tracker server implementation.

Implementation: [ccbt/discovery/tracker_server_udp.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/tracker_server_udp.py)

### PEX

Peer Exchange (BEP 11) for peer discovery.

Implementation: [ccbt/discovery/pex.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/pex.py)

Features:
- Peer exchange with other clients
- Automatic peer sharing
- PEX extension support

Configuration: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)

## Services

### Service Base

Base service class for service-oriented architecture.

Implementation: [ccbt/services/base.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/base.py)

Service states: [ccbt/services/base.py:ServiceState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/base.py#L22)


Service error: [ccbt/services/base.py:ServiceError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/base.py#L33)


Service manager: [ccbt/services/base.py:ServiceManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/base.py)

### PeerService

Manages peer connections and communication.

Implementation: [ccbt/services/peer_service.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/peer_service.py)

Service exports: [ccbt/services/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/__init__.py)

### StorageService

Manages file system operations with high-performance chunked writes.

Implementation: [ccbt/services/storage_service.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/storage_service.py)

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

Write implementation: [ccbt/services/storage_service.py:_write_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/storage_service.py#L268)

#### Configuration

- `disk.max_file_size_mb`: Maximum file size in MB (0 or None = unlimited, max 1TB)
- `disk.write_buffer_kib`: Chunk size for large file writes
- Default: Unlimited (0) for production, configurable for testing

Configuration: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)

### TrackerService

Handles tracker communication.

Implementation: [ccbt/services/tracker_service.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/tracker_service.py)

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
- File preallocation: [ccbt/storage/disk_io.py:preallocate_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Supports NONE, SPARSE, FULL, FALLOCATE strategies
- Write batching: [ccbt/storage/disk_io.py:write_block](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Priority queue for write requests
- Memory-mapped I/O: [ccbt/storage/disk_io.py:MmapCache](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py#L130) - Cached memory-mapped files for fast access
- io_uring support (Linux): [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - High-performance async I/O on Linux
- Direct I/O support: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Bypass page cache for large files
- Parallel hash verification: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Thread pool for hash verification

**Key Methods:**
- `write_block()`: [ccbt/storage/disk_io.py:write_block](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Write data block to file with batching
- `read_block()`: [ccbt/storage/disk_io.py:read_block](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Read data block from file
- `preallocate_file()`: [ccbt/storage/disk_io.py:preallocate_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Preallocate file space
- `verify_piece()`: [ccbt/storage/disk_io.py:verify_piece](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - Verify piece hash

**Configuration:** [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

### FileAssembler

Assembles pieces into complete files.

Implementation: [ccbt/storage/file_assembler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/file_assembler.py)

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

**Configuration:** [ccbt.toml:88-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L88-L96)

**Checkpoint Model:** [ccbt/models.py:TorrentCheckpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)


### Buffers

Storage buffers for I/O operations.

Implementation: [ccbt/storage/buffers.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/buffers.py)

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
- System metrics collection: [ccbt/monitoring/metrics_collector.py:394](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/metrics_collector.py#L394)
- Performance metrics tracking: [ccbt/monitoring/metrics_collector.py:404](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/metrics_collector.py#L404)
- Custom metrics registration: [ccbt/monitoring/metrics_collector.py:190](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/metrics_collector.py#L190)
- Prometheus metrics export: [ccbt/utils/metrics.py:134](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L134)

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
- Alert rule engine: [ccbt/monitoring/alert_manager.py:AlertRule](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/alert_manager.py#L81)
- Notification channels: [ccbt/monitoring/alert_manager.py:NotificationChannel](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/alert_manager.py#L44)
- Alert escalation: [ccbt/monitoring/alert_manager.py]
- Alert suppression: [ccbt/monitoring/alert_manager.py]

**Alert Severity:** [ccbt/monitoring/alert_manager.py:AlertSeverity](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/alert_manager.py#L35)


### DashboardManager

Dashboard management system.

Implementation: [ccbt/monitoring/dashboard.py:DashboardManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/dashboard.py#L126)


Features:
- Dashboard creation: [ccbt/monitoring/dashboard.py:156](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/dashboard.py#L156)
- Grafana export: [ccbt/monitoring/dashboard.py:366](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/dashboard.py#L366)
- Widget system: [ccbt/monitoring/dashboard.py:WidgetType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/dashboard.py#L78)

Dashboard types: [ccbt/monitoring/dashboard.py:DashboardType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/dashboard.py#L67)

### TracingManager

Distributed tracing for performance analysis.

Implementation: [ccbt/monitoring/tracing.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/tracing.py)

Features:
- Span management: [ccbt/monitoring/tracing.py:Span](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/tracing.py#L50)
- Trace correlation: [ccbt/monitoring/tracing.py:Trace](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/tracing.py#L70)
- Performance profiling
- OpenTelemetry integration

Span status: [ccbt/monitoring/tracing.py:SpanStatus](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/tracing.py#L31)

Span kind: [ccbt/monitoring/tracing.py:SpanKind](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/tracing.py#L40)

## Security

### SecurityManager

Security management system.

Implementation: [ccbt/security/security_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/security_manager.py)

Features:
- Security policy enforcement
- Threat detection
- Security event handling

### Encryption

Protocol encryption support.

Implementation: [ccbt/security/encryption.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py)

Configuration: [ccbt.toml:174](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L174)

### PeerValidator

Validates peer connections and behavior.

Implementation: [ccbt/security/peer_validator.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/peer_validator.py)

Configuration: [ccbt.toml:175](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L175)

### RateLimiter

Adaptive rate limiting for bandwidth management.

Implementation: [ccbt/security/rate_limiter.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/rate_limiter.py)

Configuration: [ccbt.toml:176](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L176)

### AnomalyDetector

Detects anomalous behavior patterns.

Implementation: [ccbt/security/anomaly_detector.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/anomaly_detector.py)

Features:
- Behavior pattern analysis
- Anomaly detection algorithms
- Threat scoring

## Machine Learning

### PeerSelector

ML-based peer selection.

Implementation: [ccbt/ml/peer_selector.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/ml/peer_selector.py)

Configuration: [ccbt.toml:181](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L181)

### PiecePredictor

ML-based piece prediction.

Implementation: [ccbt/ml/piece_predictor.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/ml/piece_predictor.py)

Configuration: [ccbt.toml:182](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L182)

### AdaptiveLimiter

ML-based adaptive rate limiting.

Implementation: [ccbt/ml/adaptive_limiter.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/ml/adaptive_limiter.py)

Features:
- Adaptive bandwidth allocation
- Performance-based adjustment
- Learning from usage patterns

## Extensions

### ExtensionManager

Manages BitTorrent protocol extensions (BEP 10) with automatic negotiation and feature detection.

Implementation: [ccbt/extensions/manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/manager.py)

**Features:**
- Extension negotiation: [ccbt/extensions/protocol.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/protocol.py) - BEP 10 extension handshake
- Extension registration: Register custom extensions
- Message routing: Route extension messages to handlers
- Feature detection: Detect peer capabilities

**Supported Extensions:**
- Fast Extension (BEP 6): [ccbt/extensions/fast.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/fast.py) - Reject requests for pieces we don't have
- Peer Exchange (BEP 11): [ccbt/extensions/pex.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/pex.py) - Exchange peer lists
- DHT Extension (BEP 5): [ccbt/extensions/dht.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/dht.py) - DHT port announcement
- Compact Extension: [ccbt/extensions/compact.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/compact.py) - Compact peer format
- WebSeed Extension: [ccbt/extensions/webseed.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/webseed.py) - HTTP seeding support

### FastExtension

Fast extension (BEP 6) support.

Implementation: [ccbt/extensions/fast.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/fast.py)

### WebSeedExtension

Web seed extension support.

Implementation: [ccbt/extensions/webseed.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/webseed.py)

### PEXExtension

Peer Exchange extension (BEP 11) support.

Implementation: [ccbt/extensions/pex.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/pex.py)

### DHTExtension

DHT extension (BEP 5) support.

Implementation: [ccbt/extensions/dht.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/dht.py)

### CompactExtension

Compact peer format extension support.

Implementation: [ccbt/extensions/compact.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/compact.py)

## Utilities

### Events

Event system for asynchronous component communication.

Implementation: [ccbt/utils/events.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py)

Event priority: [ccbt/utils/events.py:EventPriority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py)


Event types: [ccbt/utils/events.py:EventType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py)


Event model: [ccbt/utils/events.py:Event](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py)


Functions:
- `emit_event()`: [ccbt/utils/events.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py) - Emit event to subscribers
- `subscribe_to_event()`: [ccbt/utils/events.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py) - Subscribe to event type
- `unsubscribe_from_event()`: [ccbt/utils/events.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/events.py) - Unsubscribe from event type

Event-driven architecture supports decoupled component communication across the entire codebase.

### Exceptions

Exception hierarchy for error handling.

Implementation: [ccbt/utils/exceptions.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/exceptions.py)

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

Implementation: [ccbt/utils/logging_config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/logging_config.py)

Configuration: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)

### Metrics Utils

Metrics utility functions.

Implementation: [ccbt/utils/metrics.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py)

Prometheus integration: [ccbt/utils/metrics.py:134](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L134)

### NetworkOptimizer

Network optimization utilities.

Implementation: [ccbt/utils/network_optimizer.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/network_optimizer.py)

Features:
- Network parameter optimization
- Connection tuning
- Performance analysis

### Resilience

Resilience and fault tolerance utilities.

Implementation: [ccbt/utils/resilience.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/resilience.py)

Features:
- Retry logic
- Circuit breaker patterns
- Error recovery

## Configuration

### ConfigManager

Configuration management with hot-reload.

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
- Configuration loading: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)
- File discovery: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
- Environment variable parsing: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)
- Hot reload support: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

### Config Models

Pydantic-based configuration models.

Implementation: [ccbt/models.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

Configuration sections:
- `NetworkConfig`: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `DiskConfig`: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `StrategyConfig`: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `DiscoveryConfig`: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `LimitsConfig`: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `ObservabilityConfig`: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `SecurityConfig`: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `MLConfig`: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
- `DashboardConfig`: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

Main config: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ConfigSchema

Configuration schema and validation.

Implementation: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

### ConfigTemplates

Predefined configuration templates.

Implementation: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Templates:
- High-performance setup
- Low-resource setup
- Security-focused setup
- Development setup

### ConfigMigration

Configuration migration utilities.

Implementation: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

### ConfigBackup

Configuration backup utilities.

Implementation: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)

### ConfigDiff

Configuration diff utilities.

Implementation: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

### ConfigCapabilities

Feature detection and capabilities.

Implementation: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

### ConfigConditional

Conditional configuration support.

Implementation: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Plugins

### Plugin Base

Base plugin class for extensibility.

Implementation: [ccbt/plugins/base.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/plugins/base.py)

Plugin states: [ccbt/plugins/base.py:PluginState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/plugins/base.py#L23)


Plugin error: [ccbt/plugins/base.py:PluginError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/plugins/base.py#L36)


### MetricsPlugin

Metrics collection plugin.

Implementation: [ccbt/plugins/metrics_plugin.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/plugins/metrics_plugin.py)

### LoggingPlugin

Logging plugin.

Implementation: [ccbt/plugins/logging_plugin.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/plugins/logging_plugin.py)

## Observability

### Profiler

Performance profiler for function-level, async, memory, and I/O profiling.

Implementation: [ccbt/observability/profiler.py:Profiler](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py#L67)


Profile types: [ccbt/observability/profiler.py:ProfileType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py#L30)

Profile entry model: [ccbt/observability/profiler.py:ProfileEntry](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py#L40)

Profile report model: [ccbt/observability/profiler.py:ProfileReport](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py#L56)

Methods:
- `start()`: [ccbt/observability/profiler.py:93](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py#L93) - Start profiling
- `stop()`: [ccbt/observability/profiler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py) - Stop profiling
- `profile_function()`: [ccbt/observability/profiler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py) - Profile a function
- `profile_async()`: [ccbt/observability/profiler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py) - Profile async operations
- `get_report()`: [ccbt/observability/profiler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/observability/profiler.py) - Get profiling report

Features:
- Function-level profiling with cProfile integration
- Async operation profiling
- Memory usage tracking
- I/O operation profiling
- Bottleneck detection

## Interface

### Terminal Dashboard (Bitonic)

Textual-based terminal dashboard for real-time monitoring.

Implementation: [ccbt/interface/terminal_dashboard.py:TerminalDashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L276)


Initialization: [ccbt/interface/terminal_dashboard.py:299](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L299)

Layout composition: [ccbt/interface/terminal_dashboard.py:321](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L321)

Key bindings: [ccbt/interface/terminal_dashboard.py:337](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L337)

Widgets:
- `Overview`: Global statistics overview
- `SpeedSparklines`: Real-time speed graphs
- `TorrentsTable`: Active torrents table
- `PeersTable`: Connected peers table
- `RichLog`: Logging output

Methods:
- `compose()`: [ccbt/interface/terminal_dashboard.py:321](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L321) - Compose dashboard layout
- `on_mount()`: [ccbt/interface/terminal_dashboard.py:346](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L346) - Initialize dashboard
- `_poll_once()`: [ccbt/interface/terminal_dashboard.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py) - Poll session for updates
- `_schedule_poll()`: [ccbt/interface/terminal_dashboard.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py) - Schedule periodic polling

Entry point: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py)

Entry point configuration: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)

## CLI Components

### Interactive CLI

Interactive command-line interface.

Implementation: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/interactive.py#L41)


Features:
- Interactive command processing
- Command history
- Auto-completion
- Session management integration

### CLI Progress Display

Progress bar and status display utilities.

Implementation: [ccbt/cli/progress.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/progress.py)

Features:
- Download progress bars
- Speed indicators
- ETA calculations
- Multi-torrent progress display

## Checkpoint Management

### CheckpointManager

Comprehensive checkpoint management for resume functionality with JSON and binary format support.

**Key Methods:**
- `save_checkpoint()`: [ccbt/storage/checkpoint.py:save_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/checkpoint.py) - Save checkpoint with format selection (JSON, binary, or both)
- `load_checkpoint()`: [ccbt/storage/checkpoint.py:load_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/checkpoint.py) - Load checkpoint from disk
- `list_checkpoints()`: [ccbt/storage/checkpoint.py:list_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/checkpoint.py) - List all available checkpoints
- `delete_checkpoint()`: [ccbt/storage/checkpoint.py:delete_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/checkpoint.py) - Delete checkpoint file
- `validate_checkpoint()`: [ccbt/storage/checkpoint.py:validate_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/checkpoint.py) - Validate checkpoint integrity

**Checkpoint Data:**
- Piece states: Tracks which pieces are verified, complete, or missing
- File progress: Per-file download progress for multi-file torrents
- Download statistics: Bytes downloaded, uploaded, speed, etc.
- Torrent metadata: Info hash, name, file paths

### Checkpoint Models

Checkpoint data models.

Implementation: [ccbt/models.py:TorrentCheckpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

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

- `resume_from_checkpoint()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Resume from checkpoint
- `list_resumable_checkpoints()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - List resumable checkpoints
- `find_checkpoint_by_name()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Find checkpoint by name
- `get_checkpoint_info()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Get checkpoint information
- `validate_checkpoint()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Validate checkpoint
- `cleanup_completed_checkpoints()`: [ccbt/session/session.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py) - Cleanup completed checkpoints

CLI checkpoint commands: [ccbt/cli/main.py:checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L849)

## CLI Integration

All API functionality is accessible via the CLI:

- Download commands: [ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)
- Magnet commands: [ccbt/cli/main.py:magnet](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L608)
- Checkpoint commands: [ccbt/cli/main.py:checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L849)
- Monitoring commands: [ccbt/cli/monitoring_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py)
- Advanced commands: [ccbt/cli/advanced_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py)

See [btbt CLI Reference](btbt-cli.md) for complete CLI documentation.

## Data Models

Comprehensive data models for all components with Pydantic validation.

Implementation: [ccbt/models.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Enumerations

- `LogLevel`: [ccbt/models.py:LogLevel](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L16) - Logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

  --8<-- "ccbt/models.py:16:25"

- `PieceSelectionStrategy`: [ccbt/models.py:PieceSelectionStrategy](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L26) - Piece selection algorithms (ROUND_ROBIN, RAREST_FIRST, SEQUENTIAL)

  --8<-- "ccbt/models.py:26:33"

- `PreallocationStrategy`: [ccbt/models.py:PreallocationStrategy](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L34) - File preallocation (NONE, SPARSE, FULL, FALLOCATE)

  --8<-- "ccbt/models.py:34:42"

- `PieceState`: [ccbt/models.py:PieceState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L43) - Piece download states (MISSING, REQUESTED, DOWNLOADING, COMPLETE, VERIFIED)

  --8<-- "ccbt/models.py:43:52"

- `ConnectionState`: [ccbt/models.py:ConnectionState](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L53) - Peer connection states

  --8<-- "ccbt/models.py:53:67"

- `CheckpointFormat`: [ccbt/models.py:CheckpointFormat](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L68) - Checkpoint formats (JSON, BINARY, BOTH)

  --8<-- "ccbt/models.py:68:75"

- `MessageType`: [ccbt/models.py:MessageType](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L76) - BitTorrent message types

  --8<-- "ccbt/models.py:76:84"

### Core Models

- `PeerInfo`: [ccbt/models.py:PeerInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L90) - Peer information with IP, port, peer_id

  --8<-- "ccbt/models.py:90:123"

- `TrackerResponse`: [ccbt/models.py:TrackerResponse](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L124) - Tracker announce response

  --8<-- "ccbt/models.py:124:135"

- `PieceInfo`: [ccbt/models.py:PieceInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L136) - Piece information with index, length, hash, state

  --8<-- "ccbt/models.py:136:151"

- `FileInfo`: [ccbt/models.py:FileInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L152) - File information with name, length, path

  --8<-- "ccbt/models.py:152:160"

- `TorrentInfo`: [ccbt/models.py:TorrentInfo](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L161) - Complete torrent metadata

  --8<-- "ccbt/models.py:161:184"

### Configuration Models

- `NetworkConfig`: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L185) - Network settings with validation

  --8<-- "ccbt/models.py:185:250"

- `DiskConfig`: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py#L251) - Disk I/O settings

- `StrategyConfig`: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Piece selection strategy

- `DiscoveryConfig`: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Tracker and DHT settings

- `LimitsConfig`: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Rate limiting configuration

- `ObservabilityConfig`: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Monitoring and logging

- `SecurityConfig`: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Security features

- `MLConfig`: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Machine learning features

- `DashboardConfig`: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Dashboard settings

- `Config`: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Main configuration aggregating all sections

### Checkpoint Models

- `TorrentCheckpoint`: [ccbt/models.py:TorrentCheckpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Complete checkpoint data with resume metadata
- `FileCheckpoint`: [ccbt/models.py:FileCheckpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - File-level checkpoint information
- `DownloadStats`: [ccbt/models.py:DownloadStats](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) - Download statistics in checkpoint

### Validation

All models use Pydantic field validators: [ccbt/models.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

Field constraints include:
- Range validation (ge, le, gt, lt)
- String length validation
- IP address format validation
- Type coercion and validation

## Module Exports

Public API exports: [ccbt/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__init__.py)

Key exports:
- `AsyncSessionManager`: [ccbt/__init__.py:94](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__init__.py#L94)
- `ConfigManager`: [ccbt/__init__.py]
- `TorrentParser`: [ccbt/__init__.py]
- Utility modules

## Best Practices

### Resource Management

Use async context managers where available. See [ccbt/session/session.py:AsyncSessionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L605)

### Error Handling

Handle exceptions appropriately:
- [ccbt/utils/exceptions.py:CCBTException](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/exceptions.py) - Base exception
- [ccbt/utils/exceptions.py:NetworkError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/exceptions.py) - Network errors
- [ccbt/utils/exceptions.py:DiskError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/exceptions.py) - Disk errors
- [ccbt/utils/exceptions.py:ProtocolError](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/exceptions.py) - Protocol errors

### Async Operations

All I/O operations are asynchronous. Always use `await`:
- Session operations: [ccbt/session/session.py:AsyncSessionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/session/session.py#L605)
- Peer operations: [ccbt/peer/async_peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/async_peer_connection.py)
- Piece operations: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py)
- Storage operations: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py)

### Configuration

Access configuration via ConfigManager: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Configuration file: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

Environment variables: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

### Monitoring

Enable monitoring for production use:
- Metrics: [ccbt.toml:164](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L164)
- Alerts: [ccbt.toml:170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L170)
- Tracing: [ccbt.toml:168](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168)

See the [Monitoring](#monitoring) section below for detailed setup.

## Helper Functions and Utilities

### Torrent Builder Functions

- `build_minimal_torrent_data()`: [ccbt/core/magnet.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py) - Build minimal torrent from magnet info
- `build_torrent_data_from_metadata()`: [ccbt/core/magnet.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/magnet.py) - Build torrent from metadata exchange

### Configuration Helpers

- `get_config()`: [ccbt/config/config.py:get_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py) - Get current configuration
- `init_config()`: [ccbt/config/config.py:init_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py) - Initialize configuration from file/environment

### Service Helpers

- `get_service_manager()`: [ccbt/services/base.py:get_service_manager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/services/base.py) - Get service manager instance
- `get_alert_manager()`: [ccbt/monitoring/__init__.py:get_alert_manager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/monitoring/__init__.py) - Get alert manager instance

### Metadata Exchange

- `fetch_metadata_from_peers()`: [ccbt/piece/async_metadata_exchange.py:fetch_metadata_from_peers](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_metadata_exchange.py) - Fetch metadata for magnet links

## Module Structure

### Package Exports

Public API: [ccbt/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__init__.py)

Key exports defined in `__all__`: [ccbt/__init__.py:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__init__.py#L108)

Includes:
- Core classes: `AsyncSessionManager`, `TorrentParser`, `BencodeEncoder`, `BencodeDecoder`
- Configuration: `Config`, `ConfigManager`
- Models: `MagnetInfo`
- Modules: All utility and component modules

Lazy attribute access: [ccbt/__init__.py:160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__init__.py#L160) - Supports dynamic imports

### Type Safety

Type marker file: [ccbt/py.typed](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/py.typed) - Indicates package supports type checking

All modules use comprehensive type hints with:
- Type annotations for all functions and methods
- Generic types where appropriate
- Pydantic models for runtime validation
- Protocol definitions for interfaces

## BitTorrent Protocol v2 (BEP 52) API

### TorrentV2Parser

Main class for BitTorrent Protocol v2 operations.

Implementation: [ccbt/core/torrent_v2.py:TorrentV2Parser](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/torrent_v2.py)

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

Implementation: [ccbt/core/torrent_v2.py:TorrentV2Info](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/core/torrent_v2.py)

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

Implementation: [ccbt/protocols/bittorrent_v2.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/protocols/bittorrent_v2.py)

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

Implementation: [ccbt/piece/hash_v2.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/hash_v2.py)

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

Implementation: [ccbt/models.py:ProtocolV2Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

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