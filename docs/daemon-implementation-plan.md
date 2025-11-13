# Daemon IPC Implementation Plan

## Overview
This document outlines the comprehensive implementation plan for missing executor methods in the daemon IPC server. The plan is organized by domain (Security, NAT, Torrent, Session) with detailed tasks and subtasks.

## Analysis Summary

### Missing Implementations

1. **Security Executor** - 8 methods (100% missing)
2. **NAT Executor** - 2 methods (partial: 2 of 8 missing)
3. **Torrent Executor** - 6 methods (partial: 6 of 12 missing)
4. **Session Executor** - 1 method (100% missing)

**Total: 17 missing method implementations**

---

## Activity 1: Security Commands Implementation

### Objective
Implement all security-related IPC endpoints for blacklist, whitelist, and IP filter management.

### Tasks

#### Task 1.1: Protocol Models
**Priority:** High  
**Estimated Effort:** 2 hours

**Subtasks:**
1. Add `BlacklistResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `ips: list[str]`, `count: int`
2. Add `WhitelistResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `ips: list[str]`, `count: int`
3. Add `IPFilterStatsResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `enabled: bool`, `total_rules: int`, `blocked_count: int`, `allowed_count: int`, `stats: dict[str, Any]`
4. Add `BlacklistAddRequest` model
   - Fields: `ip: str`, `reason: str | None`
5. Add `WhitelistAddRequest` model
   - Fields: `ip: str`, `reason: str | None`

**Dependencies:** None  
**Files to Modify:**
- `ccbt/daemon/ipc_protocol.py`

#### Task 1.2: IPC Server Handlers
**Priority:** High  
**Estimated Effort:** 4 hours

**Subtasks:**
1. Add route registration in `IPCServer._setup_routes()`
   - `GET /api/v1/security/blacklist` → `_handle_get_blacklist`
   - `GET /api/v1/security/whitelist` → `_handle_get_whitelist`
   - `POST /api/v1/security/blacklist` → `_handle_add_to_blacklist`
   - `DELETE /api/v1/security/blacklist/{ip}` → `_handle_remove_from_blacklist`
   - `POST /api/v1/security/whitelist` → `_handle_add_to_whitelist`
   - `DELETE /api/v1/security/whitelist/{ip}` → `_handle_remove_from_whitelist`
   - `POST /api/v1/security/ip-filter/load` → `_handle_load_ip_filter`
   - `GET /api/v1/security/ip-filter/stats` → `_handle_get_ip_filter_stats`

2. Implement `_handle_get_blacklist()` handler
   - Execute `security.get_blacklist` via executor
   - Return `BlacklistResponse` with list of blacklisted IPs
   - Handle errors gracefully

3. Implement `_handle_get_whitelist()` handler
   - Execute `security.get_whitelist` via executor
   - Return `WhitelistResponse` with list of whitelisted IPs
   - Handle errors gracefully

4. Implement `_handle_add_to_blacklist()` handler
   - Parse `BlacklistAddRequest` from JSON body
   - Execute `security.add_to_blacklist` via executor
   - Return success response
   - Emit WebSocket event `SECURITY_BLACKLIST_UPDATED`

5. Implement `_handle_remove_from_blacklist()` handler
   - Extract IP from URL path parameter
   - Execute `security.remove_from_blacklist` via executor
   - Return success response
   - Emit WebSocket event `SECURITY_BLACKLIST_UPDATED`

6. Implement `_handle_add_to_whitelist()` handler
   - Parse `WhitelistAddRequest` from JSON body
   - Execute `security.add_to_whitelist` via executor
   - Return success response
   - Emit WebSocket event `SECURITY_WHITELIST_UPDATED`

7. Implement `_handle_remove_from_whitelist()` handler
   - Extract IP from URL path parameter
   - Execute `security.remove_from_whitelist` via executor
   - Return success response
   - Emit WebSocket event `SECURITY_WHITELIST_UPDATED`

8. Implement `_handle_load_ip_filter()` handler
   - Execute `security.load_ip_filter` via executor
   - Return success response
   - Handle errors (e.g., file not found, invalid format)

9. Implement `_handle_get_ip_filter_stats()` handler
   - Execute `security.get_ip_filter_stats` via executor
   - Return `IPFilterStatsResponse`
   - Handle case when IP filter is not enabled

**Dependencies:** Task 1.1  
**Files to Modify:**
- `ccbt/daemon/ipc_server.py`
- `ccbt/daemon/ipc_protocol.py` (add EventType.SECURITY_BLACKLIST_UPDATED, SECURITY_WHITELIST_UPDATED)

#### Task 1.3: IPC Client Methods
**Priority:** High  
**Estimated Effort:** 2 hours

**Subtasks:**
1. Implement `get_blacklist()` method
   - HTTP GET to `/api/v1/security/blacklist`
   - Parse and return `BlacklistResponse`
   - Handle errors (connection, HTTP errors)

2. Implement `get_whitelist()` method
   - HTTP GET to `/api/v1/security/whitelist`
   - Parse and return `WhitelistResponse`
   - Handle errors

3. Implement `add_to_blacklist(ip: str, reason: str = "")` method
   - HTTP POST to `/api/v1/security/blacklist`
   - Send `BlacklistAddRequest` in JSON body
   - Return success boolean

4. Implement `remove_from_blacklist(ip: str)` method
   - HTTP DELETE to `/api/v1/security/blacklist/{ip}`
   - Return success boolean

5. Implement `add_to_whitelist(ip: str, reason: str = "")` method
   - HTTP POST to `/api/v1/security/whitelist`
   - Send `WhitelistAddRequest` in JSON body
   - Return success boolean

6. Implement `remove_from_whitelist(ip: str)` method
   - HTTP DELETE to `/api/v1/security/whitelist/{ip}`
   - Return success boolean

7. Implement `load_ip_filter()` method
   - HTTP POST to `/api/v1/security/ip-filter/load`
   - Return success boolean
   - Handle errors (file not found, invalid format)

8. Implement `get_ip_filter_stats()` method
   - HTTP GET to `/api/v1/security/ip-filter/stats`
   - Parse and return `IPFilterStatsResponse`
   - Handle errors

**Dependencies:** Task 1.1, Task 1.2  
**Files to Modify:**
- `ccbt/daemon/ipc_client.py`

#### Task 1.4: Testing
**Priority:** Medium  
**Estimated Effort:** 3 hours

**Subtasks:**
1. Write unit tests for protocol models
   - Test `BlacklistResponse` serialization/deserialization
   - Test `WhitelistResponse` serialization/deserialization
   - Test `IPFilterStatsResponse` serialization/deserialization

2. Write integration tests for IPC server handlers
   - Test all 8 security endpoints
   - Test error cases (invalid IP, security manager not available)
   - Test WebSocket event emission

3. Write integration tests for IPC client methods
   - Test all 8 client methods
   - Test error handling (connection failures, HTTP errors)

**Dependencies:** Task 1.1, Task 1.2, Task 1.3  
**Files to Create:**
- `tests/integration/test_daemon_security.py`

---

## Activity 2: NAT Commands Enhancement

### Objective
Implement missing NAT commands: `get_external_ip` and `get_external_port`.

### Tasks

#### Task 2.1: Protocol Models
**Priority:** Medium  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Add `ExternalIPResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `external_ip: str | None`, `method: str | None` (UPnP, NAT-PMP, etc.)
2. Add `ExternalPortResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `internal_port: int`, `external_port: int | None`, `protocol: str`

**Dependencies:** None  
**Files to Modify:**
- `ccbt/daemon/ipc_protocol.py`

#### Task 2.2: IPC Server Handlers
**Priority:** Medium  
**Estimated Effort:** 2 hours

**Subtasks:**
1. Add route registration in `IPCServer._setup_routes()`
   - `GET /api/v1/nat/external-ip` → `_handle_get_external_ip`
   - `GET /api/v1/nat/external-port/{internal_port}` → `_handle_get_external_port`

2. Implement `_handle_get_external_ip()` handler
   - Execute `nat.get_external_ip` via executor
   - Return `ExternalIPResponse`
   - Handle case when NAT manager not available or external IP unknown

3. Implement `_handle_get_external_port()` handler
   - Extract `internal_port` and optional `protocol` from query parameters or path
   - Execute `nat.get_external_port` via executor
   - Return `ExternalPortResponse`
   - Handle case when port mapping not found

**Dependencies:** Task 2.1  
**Files to Modify:**
- `ccbt/daemon/ipc_server.py`

#### Task 2.3: IPC Client Methods
**Priority:** Medium  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Implement `get_external_ip()` method
   - HTTP GET to `/api/v1/nat/external-ip`
   - Parse and return `ExternalIPResponse`
   - Handle errors

2. Implement `get_external_port(internal_port: int, protocol: str = "tcp")` method
   - HTTP GET to `/api/v1/nat/external-port/{internal_port}?protocol={protocol}`
   - Parse and return `ExternalPortResponse`
   - Handle errors (port not mapped)

**Dependencies:** Task 2.1, Task 2.2  
**Files to Modify:**
- `ccbt/daemon/ipc_client.py`

#### Task 2.4: Testing
**Priority:** Low  
**Estimated Effort:** 2 hours

**Subtasks:**
1. Write unit tests for protocol models
2. Write integration tests for IPC server handlers
3. Write integration tests for IPC client methods

**Dependencies:** Task 2.1, Task 2.2, Task 2.3  
**Files to Create:**
- `tests/integration/test_daemon_nat_extended.py`

---

## Activity 3: Torrent Commands Enhancement

### Objective
Implement missing torrent commands: peer management, rate limits, force announce, state export/import, and checkpoint resume.

### Tasks

#### Task 3.1: Protocol Models
**Priority:** High  
**Estimated Effort:** 2 hours

**Subtasks:**
1. Add `PeerInfo` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `ip: str`, `port: int`, `download_rate: float`, `upload_rate: float`, `choked: bool`, `client: str | None`
2. Add `PeerListResponse` model
   - Fields: `info_hash: str`, `peers: list[PeerInfo]`, `count: int`
3. Add `RateLimitRequest` model
   - Fields: `download_kib: int`, `upload_kib: int`
4. Add `ExportStateRequest` model
   - Fields: `path: str` (optional, defaults to state dir)
5. Add `ImportStateRequest` model
   - Fields: `path: str` (required)
6. Add `ResumeCheckpointRequest` model
   - Fields: `info_hash: str`, `checkpoint: dict[str, Any]`, `torrent_path: str | None`

**Dependencies:** None  
**Files to Modify:**
- `ccbt/daemon/ipc_protocol.py`

#### Task 3.2: IPC Server Handlers
**Priority:** High  
**Estimated Effort:** 5 hours

**Subtasks:**
1. Add route registration in `IPCServer._setup_routes()`
   - `GET /api/v1/torrents/{info_hash}/peers` → `_handle_get_torrent_peers`
   - `POST /api/v1/torrents/{info_hash}/rate-limits` → `_handle_set_rate_limits`
   - `POST /api/v1/torrents/{info_hash}/announce` → `_handle_force_announce`
   - `POST /api/v1/torrents/export-state` → `_handle_export_session_state`
   - `POST /api/v1/torrents/import-state` → `_handle_import_session_state`
   - `POST /api/v1/torrents/resume-checkpoint` → `_handle_resume_from_checkpoint`

2. Implement `_handle_get_torrent_peers()` handler
   - Extract `info_hash` from path
   - Execute `torrent.get_peers` via executor
   - Return `PeerListResponse`
   - Handle case when torrent not found

3. Implement `_handle_set_rate_limits()` handler
   - Extract `info_hash` from path
   - Parse `RateLimitRequest` from JSON body
   - Execute `torrent.set_rate_limits` via executor
   - Return success response
   - Validate rate limit values (non-negative)

4. Implement `_handle_force_announce()` handler
   - Extract `info_hash` from path
   - Execute `torrent.force_announce` via executor
   - Return success response
   - Handle case when torrent not found or tracker unavailable

5. Implement `_handle_export_session_state()` handler
   - Parse `ExportStateRequest` from JSON body (optional path)
   - Execute `torrent.export_session_state` via executor
   - Return success response with export path
   - Handle errors (permission denied, disk full)

6. Implement `_handle_import_session_state()` handler
   - Parse `ImportStateRequest` from JSON body (required path)
   - Execute `torrent.import_session_state` via executor
   - Return imported state dictionary
   - Handle errors (file not found, invalid format, validation errors)

7. Implement `_handle_resume_from_checkpoint()` handler
   - Parse `ResumeCheckpointRequest` from JSON body
   - Validate `info_hash` format
   - Execute `torrent.resume_from_checkpoint` via executor
   - Return success response with resumed torrent info_hash
   - Handle errors (invalid checkpoint, torrent file not found)

**Dependencies:** Task 3.1  
**Files to Modify:**
- `ccbt/daemon/ipc_server.py`

#### Task 3.3: IPC Client Methods
**Priority:** High  
**Estimated Effort:** 3 hours

**Subtasks:**
1. Implement `get_peers_for_torrent(info_hash: str)` method
   - HTTP GET to `/api/v1/torrents/{info_hash}/peers`
   - Parse and return `PeerListResponse`
   - Handle errors (torrent not found)

2. Implement `set_rate_limits(info_hash: str, download_kib: int, upload_kib: int)` method
   - HTTP POST to `/api/v1/torrents/{info_hash}/rate-limits`
   - Send `RateLimitRequest` in JSON body
   - Return success boolean

3. Implement `force_announce(info_hash: str)` method
   - HTTP POST to `/api/v1/torrents/{info_hash}/announce`
   - Return success boolean

4. Implement `export_session_state(path: str | None = None)` method
   - HTTP POST to `/api/v1/torrents/export-state`
   - Send `ExportStateRequest` in JSON body (optional path)
   - Return export path string

5. Implement `import_session_state(path: str)` method
   - HTTP POST to `/api/v1/torrents/import-state`
   - Send `ImportStateRequest` in JSON body
   - Return imported state dictionary
   - Handle errors (file not found, invalid format)

6. Implement `resume_from_checkpoint(info_hash: str, checkpoint: dict, torrent_path: str | None = None)` method
   - HTTP POST to `/api/v1/torrents/resume-checkpoint`
   - Send `ResumeCheckpointRequest` in JSON body
   - Return resumed torrent info_hash
   - Handle errors (invalid checkpoint)

**Dependencies:** Task 3.1, Task 3.2  
**Files to Modify:**
- `ccbt/daemon/ipc_client.py`

#### Task 3.4: Testing
**Priority:** Medium  
**Estimated Effort:** 4 hours

**Subtasks:**
1. Write unit tests for protocol models
2. Write integration tests for IPC server handlers
   - Test all 6 torrent endpoints
   - Test error cases (torrent not found, invalid checkpoint, etc.)
3. Write integration tests for IPC client methods

**Dependencies:** Task 3.1, Task 3.2, Task 3.3  
**Files to Create:**
- `tests/integration/test_daemon_torrent_extended.py`

---

## Activity 4: Session Commands Implementation

### Objective
Implement session-level statistics endpoint.

### Tasks

#### Task 4.1: Protocol Models
**Priority:** Medium  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Add `GlobalStatsResponse` model to `ccbt/daemon/ipc_protocol.py`
   - Fields: `num_torrents: int`, `num_active: int`, `num_paused: int`, `total_download_rate: float`, `total_upload_rate: float`, `total_downloaded: int`, `total_uploaded: int`, `stats: dict[str, Any]`

**Dependencies:** None  
**Files to Modify:**
- `ccbt/daemon/ipc_protocol.py`

#### Task 4.2: IPC Server Handler
**Priority:** Medium  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Add route registration in `IPCServer._setup_routes()`
   - `GET /api/v1/session/stats` → `_handle_get_global_stats`
   - OR enhance existing `/api/v1/status` endpoint to include global stats

2. Implement `_handle_get_global_stats()` handler
   - Execute `session.get_global_stats` via executor
   - Return `GlobalStatsResponse`
   - Handle errors gracefully

**Dependencies:** Task 4.1  
**Files to Modify:**
- `ccbt/daemon/ipc_server.py`

#### Task 4.3: IPC Client Method
**Priority:** Medium  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Implement `get_global_stats()` method
   - HTTP GET to `/api/v1/session/stats`
   - Parse and return `GlobalStatsResponse`
   - Handle errors

**Dependencies:** Task 4.1, Task 4.2  
**Files to Modify:**
- `ccbt/daemon/ipc_client.py`

#### Task 4.4: Testing
**Priority:** Low  
**Estimated Effort:** 1 hour

**Subtasks:**
1. Write unit tests for protocol model
2. Write integration tests for IPC server handler
3. Write integration tests for IPC client method

**Dependencies:** Task 4.1, Task 4.2, Task 4.3  
**Files to Create:**
- `tests/integration/test_daemon_session.py`

---

## Implementation Order

### Phase 1: Foundation (Week 1)
1. Task 1.1: Security Protocol Models
2. Task 2.1: NAT Protocol Models
3. Task 3.1: Torrent Protocol Models
4. Task 4.1: Session Protocol Models

### Phase 2: Core Implementation (Week 2-3)
1. Task 1.2: Security IPC Server Handlers
2. Task 2.2: NAT IPC Server Handlers
3. Task 3.2: Torrent IPC Server Handlers
4. Task 4.2: Session IPC Server Handler

### Phase 3: Client Implementation (Week 3-4)
1. Task 1.3: Security IPC Client Methods
2. Task 2.3: NAT IPC Client Methods
3. Task 3.3: Torrent IPC Client Methods
4. Task 4.3: Session IPC Client Method

### Phase 4: Testing & Validation (Week 4-5)
1. Task 1.4: Security Testing
2. Task 2.4: NAT Testing
3. Task 3.4: Torrent Testing
4. Task 4.4: Session Testing

---

## Risk Assessment

### High Risk
- **State Export/Import**: Complex serialization, potential data corruption if format changes
- **Checkpoint Resume**: Requires careful validation of checkpoint data structure

### Medium Risk
- **Security Commands**: Need to ensure proper access control and validation
- **Rate Limits**: Need to validate limits don't conflict with global limits

### Low Risk
- **Peer List**: Read-only operation, low complexity
- **Force Announce**: Simple operation, well-tested in session manager
- **Global Stats**: Read-only operation, already implemented in session manager

---

## Dependencies

### External Dependencies
- None (all functionality exists in session manager)

### Internal Dependencies
- Security manager must be initialized in session manager
- NAT manager must be initialized in session manager
- Session manager must support all required methods

---

## Success Criteria

1. All 17 missing methods have IPC server handlers
2. All 17 missing methods have IPC client implementations
3. All protocol models are properly defined and validated
4. All endpoints return appropriate HTTP status codes
5. All endpoints handle errors gracefully
6. All endpoints have integration tests with >90% coverage
7. WebSocket events are emitted for state-changing operations
8. Documentation is updated for all new endpoints

---

## Notes

- All implementations should follow existing patterns in `ipc_server.py`
- Error handling should be consistent with existing handlers
- WebSocket events should be emitted for operations that change state
- All new endpoints should require API key authentication (via existing middleware)
- Rate limiting should be considered for state export/import operations (large payloads)

