# BEP XET: Xet Protocol Extension for Content-Defined Chunking and Deduplication

## Overview

The Xet Protocol Extension (BEP XET) is a BitTorrent protocol extension that enables content-defined chunking (CDC) and cross-torrent deduplication through a peer-to-peer Content Addressable Storage (CAS) system. This extension transforms BitTorrent into a super-fast, updatable peer-to-peer file system optimized for collaboration and efficient data sharing.

## Rationale

The Xet protocol extension addresses key limitations of traditional BitTorrent:

1. **Fixed Piece Sizes**: Traditional BitTorrent uses fixed piece sizes, leading to inefficient redistribution when files are modified. CDC adapts to content boundaries.

2. **No Cross-Torrent Deduplication**: Each torrent is independent, even if sharing identical content. Xet enables chunk-level deduplication across torrents.

3. **Centralized Storage**: Traditional CAS systems require external services. Xet builds CAS directly into the BitTorrent network using DHT and trackers.

4. **Inefficient Updates**: Updating a shared file requires redistributing the entire file. Xet only redistributes changed chunks.

By combining CDC, deduplication, and P2P CAS, Xet transforms BitTorrent into a super-fast, updatable peer-to-peer file system optimized for collaboration.

### Key Features

- **Content-Defined Chunking (CDC)**: Gearhash-based intelligent file segmentation (8KB-128KB chunks)
- **Cross-Torrent Deduplication**: Chunk-level deduplication across multiple torrents
- **Peer-to-Peer CAS**: Decentralized Content Addressable Storage using DHT and trackers
- **Merkle Tree Verification**: BLAKE3-256 hashing with SHA-256 fallback for integrity
- **Xorb Format**: Efficient storage format for grouping multiple chunks
- **Shard Format**: Metadata storage for file information and CAS data
- **LZ4 Compression**: Optional compression for Xorb data

## Use Cases

### 1. Collaborative File Sharing

Xet enables efficient collaboration by:
- **Deduplication**: Shared files across multiple torrents share the same chunks
- **Fast Updates**: Only changed chunks need to be redistributed
- **Version Control**: Track file versions through Merkle tree roots

### 2. Large File Distribution

For large files or datasets:
- **Content-Defined Chunking**: Intelligent boundaries reduce chunk redistribution on edits
- **Parallel Downloads**: Download chunks from multiple peers simultaneously
- **Resume Capability**: Track individual chunks for reliable resume

### 3. Peer-to-Peer File System

Transform BitTorrent into a P2P file system:
- **CAS Integration**: Chunks stored in DHT for global availability
- **Metadata Storage**: Shards provide file system metadata
- **Fast Lookups**: Direct chunk access via hash eliminates need for full torrent download

## Implementation Status

The Xet protocol extension is fully implemented in ccBitTorrent:

- ✅ Content-Defined Chunking (Gearhash CDC)
- ✅ BLAKE3-256 hashing with SHA-256 fallback
- ✅ SQLite deduplication cache
- ✅ DHT integration (BEP 44)
- ✅ Tracker integration
- ✅ Xorb and Shard formats
- ✅ Merkle tree computation
- ✅ BitTorrent protocol extension (BEP 10)
- ✅ CLI integration
- ✅ Configuration management

## Configuration

### CLI Commands

```bash
# Enable Xet protocol
ccbt xet enable

# Show Xet status
ccbt xet status

# Show deduplication statistics
ccbt xet stats

# Clean up unused chunks
ccbt xet cleanup --max-age-days 30
```

### Enable Xet Protocol

Configure Xet support in `ccbt.toml`:

```toml
[disk]
# Xet Protocol Configuration
xet_enabled = false                        # Enable Xet protocol
xet_chunk_min_size = 8192                  # Minimum chunk size (bytes)
xet_chunk_max_size = 131072                # Maximum chunk size (bytes)
xet_chunk_target_size = 16384              # Target chunk size (bytes)
xet_deduplication_enabled = true           # Enable chunk-level deduplication
xet_cache_db_path = "data/xet_cache.db"    # SQLite cache database path
xet_chunk_store_path = "data/xet_chunks"   # Chunk storage directory
xet_use_p2p_cas = true                     # Use P2P Content Addressable Storage
xet_compression_enabled = true             # Enable LZ4 compression for Xorb data
```


## Protocol Specification

### Message Types

The Xet extension defines four message types:

1. **CHUNK_REQUEST (0x01)**: Request a specific chunk by hash
2. **CHUNK_RESPONSE (0x02)**: Response containing chunk data
3. **CHUNK_NOT_FOUND (0x03)**: Peer does not have the requested chunk
4. **CHUNK_ERROR (0x04)**: Error occurred while retrieving chunk

### Message Format

#### CHUNK_REQUEST

```
Offset  Size  Description
0       32    Chunk hash (BLAKE3-256 or SHA-256)
```

#### CHUNK_RESPONSE

```
Offset  Size  Description
0       32    Chunk hash
32      4     Chunk data length (big-endian)
36      N     Chunk data
```

#### CHUNK_NOT_FOUND

```
Offset  Size  Description
0       32    Chunk hash
```

#### CHUNK_ERROR

```
Offset  Size  Description
0       32    Chunk hash
32      4     Error code (big-endian)
36      N     Error message (UTF-8)
```

### Extension Handshake

The Xet extension follows BEP 10 (Extension Protocol) handshake:

1. Client sends `ut_metadata` extension handshake with Xet extension ID
2. Server responds with Xet extension ID and message ID mapping
3. Messages are sent using the assigned extension message ID

### Chunk Discovery

Chunks are discovered through multiple mechanisms:

1. **DHT (BEP 44)**: Store and retrieve chunk metadata using DHT
2. **Trackers**: Announce chunk availability to trackers
3. **Peer Exchange**: Exchange chunk availability information with peers
4. **Torrent Metadata**: Extract chunk hashes from torrent Xet metadata


## Architecture

### Core Components

#### 1. Protocol Extension (`ccbt/extensions/xet.py`)

The Xet extension implements BEP 10 (Extension Protocol) messages for chunk requests and responses.

::: ccbt.extensions.xet.XetExtension
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Message Types:**

```23:29:ccbt/extensions/xet.py
class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
```

**Key Methods:**
- `encode_chunk_request()`: [ccbt/extensions/xet.py:89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L89) - Encode chunk request message with request ID
- `decode_chunk_request()`: [ccbt/extensions/xet.py:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L108) - Decode chunk request message
- `encode_chunk_response()`: [ccbt/extensions/xet.py:136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L136) - Encode chunk response with data
- `handle_chunk_request()`: [ccbt/extensions/xet.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L210) - Handle incoming chunk request from peer
- `handle_chunk_response()`: [ccbt/extensions/xet.py:284](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L284) - Handle chunk response from peer

**Extension Handshake:**
- `encode_handshake()`: [ccbt/extensions/xet.py:61](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L61) - Encode Xet extension capabilities
- `decode_handshake()`: [ccbt/extensions/xet.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L75) - Decode peer's Xet extension capabilities

#### 2. Content-Defined Chunking (`ccbt/storage/xet_chunking.py`)

Gearhash CDC algorithm for intelligent file segmentation with variable-sized chunks based on content patterns.

::: ccbt.storage.xet_chunking.GearhashChunker
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Constants:**
- `MIN_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L21) - 8 KB minimum chunk size
- `MAX_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L22) - 128 KB maximum chunk size
- `TARGET_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:23](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L23) - 16 KB default target chunk size
- `WINDOW_SIZE`: [ccbt/storage/xet_chunking.py:24](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L24) - 48 bytes rolling hash window

**Key Methods:**
- `chunk_buffer()`: [ccbt/storage/xet_chunking.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L210) - Chunk data using Gearhash CDC algorithm
- `_find_chunk_boundary()`: [ccbt/storage/xet_chunking.py:242](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L242) - Find content-defined chunk boundary using rolling hash
- `_init_gear_table()`: [ccbt/storage/xet_chunking.py:54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L54) - Initialize precomputed gear table for rolling hash

**Algorithm:**
The Gearhash algorithm uses a rolling hash with a precomputed 256-element gear table to find content-defined boundaries. This ensures similar content in different files produces the same chunk boundaries, enabling cross-file deduplication.

#### 3. Deduplication Cache (`ccbt/storage/xet_deduplication.py`)

SQLite-based local deduplication cache with DHT integration for chunk-level deduplication.

::: ccbt.storage.xet_deduplication.XetDeduplication
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Database Schema:**
- `chunks` table: [ccbt/storage/xet_deduplication.py:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L65) - Stores chunk hash, size, storage path, reference count, timestamps
- Indexes: [ccbt/storage/xet_deduplication.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L75) - On size and last_accessed for efficient queries

**Key Methods:**
- `check_chunk_exists()`: [ccbt/storage/xet_deduplication.py:85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L85) - Check if chunk exists locally and update access time
- `store_chunk()`: [ccbt/storage/xet_deduplication.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L112) - Store chunk with deduplication (increments ref_count if exists)
- `get_chunk_path()`: [ccbt/storage/xet_deduplication.py:165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L165) - Get local storage path for chunk
- `cleanup_unused_chunks()`: [ccbt/storage/xet_deduplication.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L201) - Remove chunks not accessed within max_age_days

**Features:**
- Reference counting: Tracks how many torrents/files reference each chunk
- Automatic cleanup: Removes unused chunks based on access time
- Physical storage: Chunks stored in `xet_chunks/` directory with hash as filename

#### 4. Peer-to-Peer CAS (`ccbt/discovery/xet_cas.py`)

DHT and tracker-based chunk discovery and exchange for decentralized Content Addressable Storage.

::: ccbt.discovery.xet_cas.P2PCASClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Key Methods:**
- `announce_chunk()`: [ccbt/discovery/xet_cas.py:50](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L50) - Announce chunk availability to DHT (BEP 44) and trackers
- `find_chunk_peers()`: [ccbt/discovery/xet_cas.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L112) - Find peers that have a specific chunk via DHT and tracker queries
- `request_chunk_from_peer()`: [ccbt/discovery/xet_cas.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L200) - Request chunk from a specific peer using Xet extension protocol

**DHT Integration:**
- Uses BEP 44 (Distributed Hash Table for Mutable Items) to store chunk metadata
- Chunk metadata format: [ccbt/discovery/xet_cas.py:68](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L68) - `{"type": "xet_chunk", "available": True}`
- Supports multiple DHT methods: `store()`, `store_chunk_hash()`, `get_chunk_peers()`, `get_peers()`, `find_value()`

**Tracker Integration:**
- Announces chunks to trackers using first 20 bytes of chunk hash as info_hash
- Enables tracker-based peer discovery for chunks

## Storage Formats

### Xorb Format

Xorbs group multiple chunks for efficient storage and retrieval.

::: ccbt.storage.xet_xorb.Xorb
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Format Specification:**
- Header: [ccbt/storage/xet_xorb.py:123](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L123) - 16 bytes (magic `0x24687531`, version, flags, reserved)
- Chunk count: [ccbt/storage/xet_xorb.py:149](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L149) - 4 bytes (uint32, little-endian)
- Chunk entries: [ccbt/storage/xet_xorb.py:140](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L140) - Variable (hash, sizes, data for each chunk)
- Metadata: [ccbt/storage/xet_xorb.py:119](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L119) - 8 bytes (total uncompressed size as uint64)

**Constants:**
- `MAX_XORB_SIZE`: [ccbt/storage/xet_xorb.py:35](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L35) - 64 MiB maximum xorb size
- `XORB_MAGIC_INT`: [ccbt/storage/xet_xorb.py:36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L36) - `0x24687531` magic number
- `FLAG_COMPRESSED`: [ccbt/storage/xet_xorb.py:42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L42) - LZ4 compression flag

**Key Methods:**
- `add_chunk()`: [ccbt/storage/xet_xorb.py:62](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L62) - Add chunk to xorb (fails if exceeds MAX_XORB_SIZE)
- `serialize()`: [ccbt/storage/xet_xorb.py:84](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L84) - Serialize xorb to binary format with optional LZ4 compression
- `deserialize()`: [ccbt/storage/xet_xorb.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L200) - Deserialize xorb from binary format with automatic decompression

**Compression:**
- Optional LZ4 compression: [ccbt/storage/xet_xorb.py:132](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L132) - Compresses chunk data if `compress=True` and LZ4 available
- Automatic detection: [ccbt/storage/xet_xorb.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L22) - Falls back gracefully if LZ4 not installed

### Shard Format

Shards store file metadata and CAS information for efficient file system operations.

::: ccbt.storage.xet_shard.XetShard
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Format Specification:**
- Header: [ccbt/storage/xet_shard.py:142](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L142) - 24 bytes (magic `"SHAR"`, version, flags, file/xorb/chunk counts)
- File Info Section: [ccbt/storage/xet_shard.py:145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L145) - Variable (path, hash, size, xorb refs for each file)
- CAS Info Section: [ccbt/storage/xet_shard.py:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L148) - Variable (xorb hashes, chunk hashes)
- HMAC Footer: [ccbt/storage/xet_shard.py:150](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L150) - 32 bytes (HMAC-SHA256 if key provided)

**Constants:**
- `SHARD_MAGIC`: [ccbt/storage/xet_shard.py:19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L19) - `b"SHAR"` magic bytes
- `SHARD_VERSION`: [ccbt/storage/xet_shard.py:20](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L20) - Format version 1
- `HMAC_SIZE`: [ccbt/storage/xet_shard.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L22) - 32 bytes for HMAC-SHA256

**Key Methods:**
- `add_file_info()`: [ccbt/storage/xet_shard.py:47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L47) - Add file metadata with xorb references
- `add_chunk_hash()`: [ccbt/storage/xet_shard.py:80](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L80) - Add chunk hash to shard
- `add_xorb_hash()`: [ccbt/storage/xet_shard.py:93](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L93) - Add xorb hash to shard
- `serialize()`: [ccbt/storage/xet_shard.py:106](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L106) - Serialize shard to binary format with optional HMAC
- `deserialize()`: [ccbt/storage/xet_shard.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L201) - Deserialize shard from binary format with HMAC verification

**Integrity:**
- HMAC verification: [ccbt/storage/xet_shard.py:170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L170) - Optional HMAC-SHA256 for shard integrity

## Merkle Tree Computation

Files are verified using Merkle trees built from chunk hashes for efficient integrity verification.

::: ccbt.storage.xet_hashing.XetHasher
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Hash Functions:**
- `compute_chunk_hash()`: [ccbt/storage/xet_hashing.py:43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L43) - Compute BLAKE3-256 hash for chunk (falls back to SHA-256)
- `compute_xorb_hash()`: [ccbt/storage/xet_hashing.py:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L63) - Compute hash for xorb data
- `verify_chunk_hash()`: [ccbt/storage/xet_hashing.py:158](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L158) - Verify chunk data against expected hash

**Merkle Tree Construction:**
- `build_merkle_tree()`: [ccbt/storage/xet_hashing.py:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L78) - Build Merkle tree from chunk data (hashes chunks first)
- `build_merkle_tree_from_hashes()`: [ccbt/storage/xet_hashing.py:115](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L115) - Build Merkle tree from pre-computed chunk hashes

**Algorithm:**
The Merkle tree is built bottom-up by pairing hashes at each level:
1. Start with chunk hashes (leaf nodes)
2. Pair adjacent hashes and hash the combination
3. Repeat until single root hash remains
4. Odd numbers: duplicate the last hash for pairing

**Incremental Hashing:**
- `hash_file_incremental()`: [ccbt/storage/xet_hashing.py:175](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L175) - Compute file hash incrementally for memory efficiency

**Hash Size:**
- `HASH_SIZE`: [ccbt/storage/xet_hashing.py:40](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L40) - 32 bytes for BLAKE3-256 or SHA-256

**BLAKE3 Support:**
- Automatic detection: [ccbt/storage/xet_hashing.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L21) - Uses BLAKE3 if available, falls back to SHA-256
- Performance: BLAKE3 provides better performance for large files

## References

- [BEP 10: Extension Protocol](https://www.bittorrent.org/beps/bep_0010.html)
- [BEP 44: Distributed Hash Table for Mutable Items](https://www.bittorrent.org/beps/bep_0044.html)
- [BEP 52: BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- [Gearhash Algorithm](https://github.com/xetdata/xet-core)