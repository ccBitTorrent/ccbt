# Protocol Instantiation and WebRTC/WebTorrent Pattern Analysis

## Summary

After reviewing the protocol instantiation, WebRTC, and WebTorrent implementations, I've identified several issues that need to be addressed to comply with the same patterns we established for UDP tracker client and DHT:

## Issues Found

### 1. ProtocolManager Singleton Pattern

**Location**: `ccbt/protocols/base.py` lines 757-766

**Issue**: `ProtocolManager` uses a global singleton pattern similar to the UDP tracker client we just removed:
```python
_protocol_manager: ProtocolManager | None = None

def get_protocol_manager() -> ProtocolManager:
    """Get the global protocol manager."""
    global _protocol_manager
    if _protocol_manager is None:
        _protocol_manager = ProtocolManager()
    return _protocol_manager
```

**Problem**: This breaks session logic and prevents proper lifecycle management. Multiple session managers or CLI instances could share the same protocol manager, causing conflicts.

**Fix Required**: 
- Remove singleton pattern
- Store `ProtocolManager` in `AsyncSessionManager` (similar to `udp_tracker_client`)
- Initialize at daemon startup
- Update all callers to use `session_manager.protocol_manager`

### 2. WebTorrent WebSocket Server Socket Management

**Location**: `ccbt/protocols/webtorrent.py` lines 160-192

**Issue**: Each `WebTorrentProtocol` instance creates its own WebSocket server on a configured port:
```python
async def _start_websocket_server(self) -> None:
    """Start WebSocket server for signaling."""
    # ...
    site = web.TCPSite(runner, host, port)
    await site.start()
```

**Problem**: 
- If multiple `WebTorrentProtocol` instances are created (e.g., in `HybridProtocol`), they will conflict on the same port
- WebSocket server socket is not managed at daemon startup
- No validation that socket is ready before use
- Similar to UDP tracker client socket recreation issues

**Fix Required**:
- Initialize WebSocket server once at daemon startup
- Store reference in `AsyncSessionManager.webtorrent_websocket_server`
- Ensure only one WebSocket server exists per session manager
- Add socket health checks and prevent recreation

### 3. WebRTCConnectionManager Lazy Initialization

**Location**: `ccbt/protocols/webtorrent.py` lines 607-620

**Issue**: `WebRTCConnectionManager` is created lazily in `connect_peer()`:
```python
if self.webrtc_manager is None:
    self.webrtc_manager = WebRTCConnectionManager(...)
```

**Problem**:
- Multiple `WebTorrentProtocol` instances could create multiple managers
- No shared state between protocol instances
- Manager creation happens during runtime, not at startup

**Fix Required**:
- Initialize `WebRTCConnectionManager` at daemon startup if WebTorrent is enabled
- Store in `AsyncSessionManager.webrtc_manager`
- Share same manager instance across all `WebTorrentProtocol` instances
- Pass manager reference to protocol instances

### 4. Protocol Instantiation in HybridProtocol

**Location**: `ccbt/protocols/hybrid.py` lines 90-119

**Issue**: `HybridProtocol` creates new protocol instances:
```python
self.sub_protocols[ProtocolType.BITTORRENT] = BitTorrentProtocol()
self.sub_protocols[ProtocolType.WEBTORRENT] = WebTorrentProtocol()
```

**Problem**:
- Each `HybridProtocol` instance creates new protocol instances
- No sharing of protocol state or resources
- WebTorrent protocols would each try to create their own WebSocket servers

**Fix Required**:
- Protocols should be managed at session manager level
- `HybridProtocol` should reference shared protocol instances from session manager
- Or protocols should be designed to support multiple instances safely

### 5. BitTorrentProtocol Session Manager Reference

**Location**: `ccbt/protocols/bittorrent.py` line 26+

**Issue**: `BitTorrentProtocol` accepts `session_manager` parameter in some cases but not consistently.

**Problem**: Inconsistent pattern - some protocols take session_manager, others don't.

**Fix Required**:
- Standardize protocol initialization to accept `session_manager` reference
- Ensure all protocols can access shared components (UDP tracker, DHT, etc.)

## Recommended Fixes

### Phase 1: Remove ProtocolManager Singleton

1. Remove `get_protocol_manager()` function
2. Add `protocol_manager: ProtocolManager | None = None` to `AsyncSessionManager`
3. Initialize at daemon startup in `session.py` `start()` method
4. Update all callers to use `session_manager.protocol_manager`

### Phase 2: Fix WebTorrent WebSocket Server

1. Add `webtorrent_websocket_server: Any | None = None` to `AsyncSessionManager`
2. Create startup function `start_webtorrent_websocket_server()` in `manager_startup.py`
3. Initialize WebSocket server once at daemon startup
4. Update `WebTorrentProtocol` to use shared server reference
5. Add socket health checks and prevent recreation

### Phase 3: Fix WebRTCConnectionManager

1. Add `webrtc_manager: Any | None = None` to `AsyncSessionManager`
2. Initialize at daemon startup if WebTorrent is enabled
3. Pass manager reference to `WebTorrentProtocol` instances
4. Remove lazy initialization from `connect_peer()`

### Phase 4: Standardize Protocol Initialization

1. Update all protocol `__init__()` methods to accept optional `session_manager` parameter
2. Store session_manager reference in protocols
3. Use session_manager components (UDP tracker, DHT, etc.) instead of creating new ones
4. Update `HybridProtocol` to use shared protocol instances or pass session_manager

## Compliance with Established Patterns

These fixes will ensure protocols comply with the same patterns we established:

✅ **No Singleton Patterns**: All components managed via session manager
✅ **Socket Initialization at Startup**: WebSocket server initialized once at daemon startup
✅ **Shared Resource Management**: WebRTC manager shared across protocol instances
✅ **Proper Lifecycle Management**: Components initialized in correct order at startup
✅ **Session Manager References**: All components accessible via session manager

## Testing Strategy

1. **Unit Tests**: Test singleton removal, protocol manager initialization
2. **Integration Tests**: Test WebTorrent WebSocket server initialization, WebRTC manager sharing
3. **End-to-End Tests**: Test full daemon startup with WebTorrent enabled
4. **Conflict Tests**: Test multiple protocol instances don't conflict on ports

## Files to Modify

- `ccbt/protocols/base.py` - Remove singleton, update ProtocolManager
- `ccbt/protocols/webtorrent.py` - Use shared WebSocket server and WebRTC manager
- `ccbt/protocols/bittorrent.py` - Standardize session_manager parameter
- `ccbt/protocols/hybrid.py` - Use shared protocol instances or pass session_manager
- `ccbt/session/session.py` - Add protocol_manager, webtorrent_websocket_server, webrtc_manager
- `ccbt/session/manager_startup.py` - Add startup functions for WebTorrent components
- Update all callers of `get_protocol_manager()`

