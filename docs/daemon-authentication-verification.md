# Daemon IPC Authentication Verification

This document verifies that all components correctly authenticate with the daemon IPC server.

## Authentication Flow

The daemon IPC server requires authentication via the `X-CCBT-API-Key` header for all HTTP REST endpoints (except `/api/v1/metrics`). WebSocket connections authenticate via query parameter or header.

## Verified Components

### 1. IPCClient (`ccbt/daemon/ipc_client.py`)

✅ **Verified**: All HTTP REST methods include authentication headers

- `_get_headers()` method correctly adds `X-CCBT-API-Key` header when `api_key` is set
- All HTTP methods (`get`, `post`, `put`, `delete`) use `headers=self._get_headers()`
- WebSocket connections include API key in URL query parameter: `?api_key={api_key}`

**Key Code**:
```python
def _get_headers(self) -> dict[str, str]:
    headers = {}
    if self.api_key:
        headers[API_KEY_HEADER] = self.api_key
    return headers
```

### 2. CLI (`ccbt/cli/main.py`)

✅ **Verified**: CLI creates IPCClient with API key from config

- Reads API key from `cfg.daemon.api_key`
- Creates `IPCClient(api_key=cfg.daemon.api_key)` in multiple locations:
  - Line 127: `client = IPCClient(api_key=cfg.daemon.api_key)`
  - Line 437: `client = IPCClient(api_key=cfg.daemon.api_key)`
  - Line 507: `client = IPCClient(api_key=cfg.daemon.api_key)`

**Pattern**: `cfg.daemon.api_key` → `IPCClient` → HTTP headers

### 3. Terminal Dashboard (`ccbt/interface/terminal_dashboard.py`)

✅ **Verified**: Terminal dashboard creates IPCClient with API key from config

- Reads API key from `cfg.daemon.api_key`
- Creates `IPCClient(api_key=cfg.daemon.api_key)` at:
  - Line 2689: `client = IPCClient(api_key=cfg.daemon.api_key)`
  - Line 2747: `client = IPCClient(api_key=cfg.daemon.api_key)`

**Pattern**: `cfg.daemon.api_key` → `IPCClient` → HTTP headers

### 4. DaemonSessionAdapter (`ccbt/executor/session_adapter.py`)

✅ **Verified**: Adapter wraps IPCClient, preserving authentication

- `DaemonSessionAdapter` takes `IPCClient` as parameter
- All adapter methods delegate to `ipc_client` methods
- Authentication flows through: `DaemonSessionAdapter` → `IPCClient` → HTTP headers

**Key Code**:
```python
class DaemonSessionAdapter(SessionAdapter):
    def __init__(self, ipc_client: Any):
        self.ipc_client = ipc_client
```

### 5. DaemonInterfaceAdapter (`ccbt/interface/daemon_session_adapter.py`)

✅ **Verified**: Interface adapter wraps IPCClient, preserving authentication

- `DaemonInterfaceAdapter` takes `IPCClient` as parameter
- Stores client as `self._client`
- All methods delegate to `self._client` methods
- Authentication flows through: `DaemonInterfaceAdapter` → `IPCClient` → HTTP headers

**Key Code**:
```python
class DaemonInterfaceAdapter:
    def __init__(self, ipc_client: IPCClient):
        self._client = ipc_client
```

### 6. UnifiedCommandExecutor (`ccbt/executor/executor.py`)

✅ **Verified**: Executor uses authenticated adapter

- `UnifiedCommandExecutor` takes `SessionAdapter` (can be `DaemonSessionAdapter`)
- All domain executors (torrent, file, queue, etc.) use the same adapter
- Authentication flows through: `UnifiedCommandExecutor` → `DaemonSessionAdapter` → `IPCClient` → HTTP headers

### 7. Command Executor (Interface) (`ccbt/interface/commands/executor.py`)

✅ **Verified**: Interface command executor uses authenticated client

- Detects `DaemonInterfaceAdapter` and extracts `IPCClient`
- Creates `DaemonSessionAdapter` with the IPC client
- Authentication flows through: `CommandExecutor` → `DaemonSessionAdapter` → `IPCClient` → HTTP headers

**Key Code**:
```python
if self._is_daemon_session:
    self._ipc_client = session._client
    adapter = DaemonSessionAdapter(self._ipc_client)
```

## Server-Side Authentication

The IPC server (`ccbt/daemon/ipc_server.py`) enforces authentication:

- **HTTP REST**: Middleware checks `X-CCBT-API-Key` header (lines 136-150)
- **WebSocket**: Checks `api_key` query parameter or `X-CCBT-API-Key` header (line 1663)
- **Exceptions**: `/api/v1/events` (WebSocket upgrade) and `/api/v1/metrics` don't require auth

## Test Coverage

Comprehensive tests in `tests/daemon/test_ipc_authentication.py` verify:

1. ✅ IPCClient sets API key header correctly
2. ✅ IPCClient handles missing API key gracefully
3. ✅ IPCClient includes API key in WebSocket URL
4. ✅ DaemonSessionAdapter preserves authentication
5. ✅ CLI creates IPCClient with API key from config
6. ✅ Interface creates IPCClient with API key from config
7. ✅ All HTTP methods include authentication headers
8. ✅ WebSocket authentication works correctly
9. ✅ Executor uses authenticated adapter
10. ✅ Command executor uses authenticated client

**Test Results**: All 11 tests pass ✅

## Authentication Chain Summary

```
Config (cfg.daemon.api_key)
    ↓
IPCClient(api_key=cfg.daemon.api_key)
    ↓
_get_headers() → {"X-CCBT-API-Key": api_key}
    ↓
HTTP Request Headers
    ↓
IPC Server Middleware (validates header)
    ↓
Request Handler
```

## Conclusion

✅ **All components correctly authenticate with the daemon IPC server**

- API key flows from config → IPCClient → HTTP headers
- All HTTP REST methods include authentication headers
- WebSocket connections include API key in URL
- Adapters and executors preserve authentication through the chain
- Server-side middleware enforces authentication

The authentication mechanism is consistent across CLI, executor, and interface components.

