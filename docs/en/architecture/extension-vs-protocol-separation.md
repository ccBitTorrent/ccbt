# Extension vs Protocol Separation Architecture

## Overview

ccBitTorrent has a clear separation between **BitTorrent Extensions** (BEP 10) and **Protocols**:

- **Extensions** (BEP 10): Extend the BitTorrent protocol (SSL, Xet, ut_metadata, PEX, Fast, DHT, etc.)
- **Protocols**: Separate protocols (BitTorrent, IPFS, WebTorrent, XET, Hybrid)

## Architecture

### BitTorrent Extensions (BEP 10)

**Location**: `ccbt/extensions/`

**Manager**: `ExtensionManager` (`ccbt/extensions/manager.py`)

**Handled By**: `AsyncPeerConnectionManager._handle_extension_message()`

**Examples**:
- **SSL Extension**: Encrypted peer connections (`ccbt/extensions/ssl.py`)
- **Xet Extension**: Chunk-based deduplication (`ccbt/extensions/xet.py`)
- **ut_metadata**: Metadata exchange for magnet links (BEP 9)
- **PEX**: Peer Exchange (BEP 11)
- **Fast Extension**: Fast peer extension (BEP 6)
- **DHT Extension**: DHT support (BEP 5)
- **WebSeed**: HTTP seeding support

**Message Format**:
```
<length (4 bytes)><message_id (20)><extension_id (1 byte)><extension_payload>
```

**Initialization**:
- Extensions are initialized in `ExtensionManager._initialize_extensions()`
- Registered with `ExtensionProtocol.register_extension()`
- Started via `ExtensionManager.start()`

**Message Handling**:
1. **ut_metadata** (BEP 9): Handled FIRST (critical for magnet links)
2. **Registered handlers**: Check `ExtensionProtocol.message_handlers` for pluggable extensions
3. **ExtensionManager handlers**: Fallback for SSL/Xet (backward compatibility)

### Protocols (Separate Protocols)

**Location**: `ccbt/protocols/`

**Manager**: `ProtocolManager` (`ccbt/protocols/base.py`)

**Handled By**: Protocol-specific handlers in `ProtocolManager`

**Examples**:
- **BitTorrent Protocol**: Standard BitTorrent (`ccbt/protocols/bittorrent.py`)
- **IPFS Protocol**: IPFS integration (`ccbt/protocols/ipfs.py`)
- **WebTorrent Protocol**: WebRTC-based (`ccbt/protocols/webtorrent.py`)
- **XET Protocol**: XET protocol (`ccbt/protocols/xet.py`)
- **Hybrid Protocol**: Multi-protocol support (`ccbt/protocols/hybrid.py`)

**Initialization**:
- Protocols are registered with `ProtocolManager.register_protocol()`
- Started via `ProtocolManager.start()`
- Each protocol has its own lifecycle and connection management

**Note**: IPFS is **NOT** a BitTorrent extension - it's a completely separate protocol with its own:
- Connection management
- Message format
- Peer discovery
- Content addressing (CIDs)

## Current Implementation

### Extension Message Handling Flow

```python
# In AsyncPeerConnectionManager._handle_extension_message():

1. Validate message_id == 20 (BEP 10 requirement)
2. Extract extension_id and extension_payload
3. Handle extension handshake (extension_id == 0)
4. For non-handshake messages:
   a. Check ut_metadata FIRST (critical for magnet links)
   b. Check registered handlers (pluggable architecture)
   c. Fallback to ExtensionManager handlers (SSL/Xet)
```

### Why ut_metadata is Prioritized

- **Critical for magnet links**: Without metadata, downloads can't start
- **Time-sensitive**: Metadata exchange has timeouts
- **State-dependent**: Requires active metadata exchange state
- **BEP 9 requirement**: Must be handled correctly for compatibility

### Why SSL/Xet Use ExtensionManager

- **Backward compatibility**: Existing code uses `ExtensionManager.handle_ssl_message()` and `handle_xet_message()`
- **State management**: ExtensionManager tracks extension states
- **Event emission**: ExtensionManager emits events for extension activities
- **Future migration**: Can migrate to registered handlers later

## Separation of Concerns

### Extensions (BEP 10)
- ✅ Extend BitTorrent protocol
- ✅ Use BEP 10 message format
- ✅ Managed by ExtensionManager
- ✅ Handled in `_handle_extension_message()`
- ✅ Registered with ExtensionProtocol

### Protocols
- ✅ Separate protocols (not BitTorrent extensions)
- ✅ Own connection management
- ✅ Own message formats
- ✅ Managed by ProtocolManager
- ✅ Started/stopped independently

## Future Improvements

### 1. Migrate SSL/Xet to Registered Handlers

**Current**: SSL/Xet use `ExtensionManager.handle_*_message()` methods

**Proposed**: Register handlers with `ExtensionProtocol.register_extension()`:

```python
# In ExtensionManager._initialize_extensions():
async def ssl_handler(peer_id: str, payload: bytes) -> bytes | None:
    return await self.handle_ssl_message(peer_id, extension_id, payload)

ssl_message_id = protocol_ext.register_extension("ssl", "1.0", handler=ssl_handler)
```

**Benefits**:
- Cleaner architecture
- Consistent with other extensions
- Easier to add new extensions
- Better separation of concerns

### 2. Separate Extension Startup

**Current**: Extensions are initialized in `ExtensionManager._initialize_extensions()`

**Proposed**: Each extension could have its own startup/shutdown lifecycle:

```python
class SSLExtension:
    async def start(self) -> None:
        # SSL-specific startup
        pass
    
    async def stop(self) -> None:
        # SSL-specific shutdown
        pass
```

**Benefits**:
- Better resource management
- Cleaner lifecycle management
- Easier to disable/enable extensions
- Better error isolation

### 3. Protocol-Specific Extension Handling

**Current**: All extensions handled in `AsyncPeerConnectionManager`

**Proposed**: Protocols could handle their own extensions:

```python
class IPFSProtocol(Protocol):
    async def handle_extension_message(self, connection, payload):
        # IPFS-specific extension handling
        pass
```

**Benefits**:
- Protocol-specific extensions
- Better encapsulation
- Easier to add protocol-specific features

## Current Status

✅ **Working Correctly**:
- SSL and Xet handlers are present and functional
- ut_metadata is prioritized correctly
- Extension registration system exists
- Fallback to ExtensionManager handlers works

✅ **Architecture is Sound**:
- Clear separation between extensions and protocols
- IPFS is correctly handled as a separate protocol
- ExtensionManager properly manages extension lifecycle

⚠️ **Potential Improvements**:
- Migrate SSL/Xet to registered handlers (optional)
- Add extension-specific startup/shutdown (optional)
- Consider protocol-specific extension handling (optional)

## Conclusion

The current architecture correctly separates:
- **BitTorrent Extensions** (BEP 10): Handled by ExtensionManager
- **Protocols**: Handled by ProtocolManager

SSL and Xet are **NOT removed** - they're still handled, just with a fallback mechanism that supports both registered handlers and ExtensionManager methods. This provides:
- Backward compatibility
- Future extensibility
- Clear separation of concerns

IPFS is correctly handled as a separate protocol, not a BitTorrent extension.

