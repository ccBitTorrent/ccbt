# Unimplemented Methods Documentation

This document lists methods and features that are marked as incomplete or placeholder implementations in the ccBitTorrent codebase. These are identified by comments containing "would" indicating future implementation needs.

## Table of Contents

- [Connection Pool](#connection-pool)
- [Monitoring & Metrics](#monitoring--metrics)
- [Peer Connection](#peer-connection)
- [Security](#security)
- [Executor](#executor)
- [Interface & Daemon](#interface--daemon)
- [Piece Management](#piece-management)
- [ML Features](#ml-features)
- [Discovery (DHT)](#discovery-dht)
- [Storage](#storage)
- [Protocols](#protocols)
- [Transport](#transport)

---

## Connection Pool

### `ccbt/peer/connection_pool.py`

#### Connection Establishment Time Tracking
- **Location**: Line 274
- **Method**: `get_pool_stats()` 
- **Issue**: Connection establishment time tracking is not fully implemented
- **Comment**: `# (This would need to be tracked during connection creation)`
- **Status**: Partial - Currently attempts to read `establishment_time` from metrics, but tracking during connection creation is incomplete

#### Connection Creation Implementation
- **Location**: Line 326
- **Method**: `_create_connection()`
- **Issue**: Comment indicates this would be implemented by the actual connection manager
- **Comment**: `# This would be implemented by the actual connection manager`
- **Status**: Partial - Has implementation but may need connection manager integration

---

## Monitoring & Metrics

### `ccbt/monitoring/metrics_collector.py`

#### Connection Success Rate Tracking
- **Location**: Line 802
- **Method**: `_update_performance_metrics()`
- **Issue**: Connection attempt tracking is not implemented globally
- **Comment**: `# Note: This would require tracking connection attempts globally`
- **Status**: Placeholder - Uses heuristic based on active connections vs queued peers

### `ccbt/utils/metrics.py`

#### Global Rate Calculation
- **Location**: Line 273
- **Method**: `_calculate_global_rates()`
- **Issue**: Rate calculation based on historical data is not implemented
- **Comment**: `# This would calculate rates based on historical data`
- **Status**: Placeholder - Sets values to 0.0

---

## Peer Connection

### `ccbt/peer/async_peer_connection.py`

#### Piece Availability Tracking for Prioritization
- **Location**: Line 518
- **Method**: `_calculate_piece_priority()`
- **Issue**: Rarest piece prioritization requires piece availability tracking
- **Comment**: `# This would require piece availability tracking`
- **Status**: Partial - Has fallback heuristic using piece index

#### Piece Manager Update on Piece Layer
- **Location**: Line 3513
- **Method**: `_handle_piece_layer_message()`
- **Issue**: Piece manager update/trigger not fully implemented
- **Comment**: `# This would typically update piece manager or trigger piece selection`
- **Status**: Partial - Has conditional check for piece manager attribute

#### Torrent Metadata Update on File Tree
- **Location**: Line 3589
- **Method**: `_handle_file_tree_message()`
- **Issue**: Torrent metadata update not fully implemented
- **Comment**: `# This would typically update torrent metadata`
- **Status**: Partial - Has conditional check for metadata update

---

## Security

### `ccbt/security/messaging.py`

#### Private Key Access Method
- **Location**: Line 176
- **Method**: `sign_message()`
- **Issue**: Simplified implementation; proper implementation would need `get_private_key_bytes()` method in key_manager
- **Comment**: `# Note: This is a simplified implementation - proper implementation would need a get_private_key_bytes() method in key_manager`
- **Status**: Works but uses workaround to access private key bytes

### `ccbt/security/peer_validator.py`

#### Protocol Compliance Assessment
- **Location**: Line 406
- **Method**: `_assess_protocol_compliance()`
- **Issue**: Simplified assessment; real implementation would check for proper BitTorrent protocol compliance
- **Comment**: `# In a real implementation, this would check for proper BitTorrent protocol compliance`
- **Status**: Simplified implementation

---

## Executor

### `ccbt/executor/session_adapter.py`

#### File Verification
- **Location**: Line 679
- **Method**: `verify_files()`
- **Issue**: Placeholder method; actual verification not implemented
- **Comment**: `# Placeholder - actual verification would be implemented here`
- **Status**: Placeholder - Returns status message only

---

## Interface & Daemon

### `ccbt/interface/daemon_session_adapter.py`

#### Aggregated Statistics
- **Location**: Lines 297-299
- **Method**: `_refresh_cache()`
- **Issue**: Download rate, upload rate, and average progress aggregation not implemented
- **Comments**: 
  - `# Would need to aggregate` (download_rate)
  - `# Would need to aggregate` (upload_rate)
  - `# Would need to calculate` (average_progress)
- **Status**: Placeholder - Values set to 0.0

---

## Piece Management

### `ccbt/piece/async_piece_manager.py`

#### Work-Stealing Executor
- **Location**: Line 324
- **Method**: `_create_hash_verification_pool()`
- **Issue**: Actual work-stealing requires custom executor implementation
- **Comment**: `# Actual work-stealing would require a custom executor implementation`
- **Status**: Partial - Uses larger pool size as workaround

### `ccbt/piece/async_metadata_exchange.py`

#### Extended Handshake Sending
- **Location**: Line 1053
- **Method**: `_send_extended_handshake()`
- **Issue**: Stub for testing; actual extended handshake sending not implemented
- **Comment**: `# This would send the actual extended handshake`
- **Status**: Stub - For testing purposes only

#### Metadata Fetching
- **Location**: Line 1067
- **Method**: `_fetch_metadata_from_peer()`
- **Issue**: Stub for testing; actual metadata fetching not implemented
- **Comment**: `# This would implement the actual metadata fetching`
- **Status**: Stub - For testing purposes only

---

## ML Features

### `ccbt/ml/peer_selector.py`

#### ML Model Prediction
- **Location**: Line 358
- **Method**: `_predict_peer_quality()`
- **Issue**: Simplified prediction; real implementation would use trained ML model
- **Comment**: `# In a real implementation, this would use a trained ML model`
- **Status**: Simplified - Uses quality score calculation

#### Latency Estimation
- **Location**: Line 486
- **Method**: `_estimate_latency()`
- **Issue**: Placeholder implementation; real implementation would ping the peer
- **Comment**: `# In a real implementation, this would ping the peer`
- **Status**: Placeholder - Returns random latency value

#### Bandwidth Estimation
- **Location**: Line 496
- **Method**: `_estimate_bandwidth()`
- **Issue**: Placeholder implementation; real implementation would measure bandwidth
- **Comment**: `# In a real implementation, this would measure bandwidth`
- **Status**: Placeholder - Returns estimated value

---

## Discovery (DHT)

### `ccbt/discovery/dht_indexing.py`

#### Index Entry Creation/Update
- **Location**: Line 92
- **Method**: `create_index_entry()`
- **Issue**: Full implementation would create/update index entry and store via BEP 44
- **Comment**: `# Full implementation would create/update index entry and store via BEP 44`
- **Status**: Partial - Returns index key, actual storage handled by `index_infohash()` in dht.py

#### DHT Query Implementation
- **Location**: Line 114
- **Method**: `query_index()`
- **Issue**: Full implementation would query DHT using BEP 44 get operations
- **Comment**: `# In full implementation, this would query DHT using BEP 44 get operations`
- **Status**: Partial - Actual querying handled by `query_infohash_index()` in dht.py

### `ccbt/discovery/dht_multiaddr.py`

#### DHT Network Query
- **Location**: Line 294
- **Method**: `query_dht_for_addresses()`
- **Issue**: Full implementation would query the DHT network
- **Comment**: `# In a full implementation, this would query the DHT network`
- **Status**: Partial - Returns validated unique addresses from known_addresses only

---

## Storage

### `ccbt/storage/disk_io.py`

#### Dynamic Worker Adjustment
- **Location**: Lines 1506-1515
- **Method**: `_adjust_hash_workers_adaptive()`
- **Issue**: ThreadPoolExecutor doesn't support dynamic worker adjustment
- **Comments**: 
  - `# Log the recommendation - actual implementation would require recreating the executor or using a different approach`
  - `# This would require executor recreation or a custom pool implementation`
- **Status**: Partial - Logs recommendation but doesn't implement dynamic adjustment

#### File Reference Metadata Storage
- **Location**: Line 1714
- **Method**: `write_chunk()`
- **Issue**: File reference metadata would be stored in separate table in full implementation
- **Comment**: `# This would be stored in a separate table in a full implementation`
- **Status**: Partial - Reference count incremented but metadata storage incomplete

---

## Protocols

### `ccbt/protocols/ipfs.py`

#### IPFS Block Extraction
- **Location**: Line 1397
- **Method**: `convert_ipfs_to_torrent()`
- **Issue**: Blocks would need to be extracted from IPFS object
- **Comment**: `# Would need to extract from IPFS object`
- **Status**: Partial - Blocks array is empty

---

## Transport

### `ccbt/peer/utp_peer.py`

#### Time-Based Rate Tracking
- **Location**: Line 305
- **Method**: `update_stats()`
- **Issue**: Rate calculation is simplified; would need time-based tracking
- **Comment**: `# Calculate rates (simplified - would need time-based tracking)`
- **Status**: Partial - Uses basic elapsed time calculation

---

## Summary

### Implementation Status Categories

1. **Placeholder**: Method exists but returns default/empty values or uses stubs
   - Examples: `verify_files()`, `_estimate_latency()`, `_calculate_global_rates()`

2. **Partial**: Has some implementation but missing key features
   - Examples: `get_pool_stats()`, `_calculate_piece_priority()`, `create_index_entry()`

3. **Simplified**: Works but uses simplified logic instead of full implementation
   - Examples: `_predict_peer_quality()`, `_assess_protocol_compliance()`, `sign_message()`

4. **Stub**: Testing-only implementations
   - Examples: `_send_extended_handshake()`, `_fetch_metadata_from_peer()`

### Priority Areas for Implementation

1. **High Priority**:
   - Connection attempt tracking for metrics
   - File verification implementation
   - ML model integration for peer selection
   - DHT network querying for address discovery

2. **Medium Priority**:
   - Piece availability tracking for prioritization
   - Dynamic worker pool adjustment
   - Time-based rate tracking
   - Protocol compliance checking

3. **Low Priority**:
   - Testing stubs (if not needed for production)
   - Enhanced metadata storage
   - IPFS block extraction

---

## Notes

- Many "would" comments indicate future enhancements rather than critical missing functionality
- Some methods work with simplified implementations but could be enhanced
- Testing stubs are intentionally minimal and may not need full implementation
- Some features may be implemented in related modules (e.g., DHT indexing in `dht.py`)

