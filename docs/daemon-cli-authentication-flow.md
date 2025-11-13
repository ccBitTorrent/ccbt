# Daemon-CLI Authentication Flow

This document explains how authentication works when the daemon and CLI run in separate terminal windows.

## Overview

Both the daemon and CLI read from the **same config file** (`ccbt.toml`). The API key is stored in this shared config file, allowing both processes to use the same authentication credentials.

## Config File Locations

Both daemon and CLI search for the config file in this order:

1. `ccbt.toml` in current working directory
2. `~/.config/ccbt/ccbt.toml` (user config directory)
3. `~/.ccbt.toml` (home directory)

**Both processes use the same search order**, ensuring they find the same config file.

## Authentication Flow Scenarios

### Scenario 1: CLI Starts Daemon (Recommended)

```
Terminal 1: User runs `btbt daemon start`
    ↓
CLI (daemon_commands.py):
    1. Reads config file (or creates default)
    2. Generates API key if needed: api_key = generate_api_key()
    3. Saves API key to config file:
       config_data["daemon"]["api_key"] = api_key
       toml.dump(config_data, config_file)
    4. Starts daemon process
    ↓
Terminal 2: Daemon process starts
    ↓
Daemon (main.py):
    1. Reads config file: init_config()
    2. Gets API key: api_key = cfg.daemon.api_key
    3. Creates IPCServer with API key: IPCServer(api_key=api_key)
    4. Starts IPC server on http://127.0.0.1:8080
    ↓
Terminal 1: User runs CLI command (e.g., `btbt download`)
    ↓
CLI (main.py):
    1. Reads config file: init_config()
    2. Gets API key: cfg.daemon.api_key
    3. Creates IPCClient: IPCClient(api_key=cfg.daemon.api_key)
    4. Makes HTTP request with header: X-CCBT-API-Key: {api_key}
    5. Daemon validates header matches its API key
    6. Request succeeds ✅
```

**Key Points:**
- CLI generates and saves API key **before** starting daemon
- Daemon reads API key from config file
- CLI reads same API key from same config file
- Both use the same API key → authentication succeeds

### Scenario 2: Daemon Started Directly (Not Recommended)

```
Terminal 1: User runs daemon directly (e.g., `python -m ccbt.daemon.main`)
    ↓
Daemon (main.py):
    1. Reads config file: init_config()
    2. If no API key in config:
       - Generates API key: api_key = generate_api_key()
       - Stores in memory: self.config.daemon.api_key = api_key
       - ⚠️ DOES NOT save to config file
    3. Creates IPCServer with API key
    4. Starts IPC server
    ↓
Terminal 2: User runs CLI command
    ↓
CLI (main.py):
    1. Reads config file: init_config()
    2. Gets API key: cfg.daemon.api_key
       - ⚠️ If daemon generated new key, this will be None or old key
    3. Creates IPCClient: IPCClient(api_key=cfg.daemon.api_key)
    4. Makes HTTP request with wrong/missing API key
    5. Daemon rejects request: 401 Unauthorized ❌
```

**Problem:** If daemon generates a new API key, it doesn't save it to the config file, so CLI can't authenticate.

**Solution:** Always start daemon via CLI (`btbt daemon start`) which ensures API key is saved to config file.

### Scenario 3: Both Running, Config File Updated

```
Terminal 1: Daemon running (using API key from config)
Terminal 2: CLI running (using API key from config)
    ↓
User updates config file manually (changes API key)
    ↓
Terminal 1: Daemon
    - Still using old API key from memory
    - Config hot-reload may update it (if implemented)
    ↓
Terminal 2: CLI
    - Reads new API key from config file
    - Creates IPCClient with new API key
    - Makes request with new API key
    - Daemon still expects old API key
    - Request fails: 401 Unauthorized ❌
```

**Solution:** Restart daemon after changing API key in config file.

## Code Flow Details

### 1. CLI Saves API Key (daemon_commands.py:108-130)

```python
# CLI generates API key
api_key = generate_api_key()
cfg.daemon.api_key = api_key

# CLI saves to config file
if config_manager.config_file:
    config_data = toml.load(config_file)
    config_data["daemon"]["api_key"] = cfg.daemon.api_key
    toml.dump(config_data, config_file)  # ✅ Saved to disk
```

### 2. Daemon Reads API Key (main.py:149-170)

```python
# Daemon reads config
daemon_config = getattr(self.config, "daemon", None)
if daemon_config:
    api_key = daemon_config.api_key  # ✅ Read from config
else:
    # Generate new key (but doesn't save it!)
    api_key = generate_api_key()
    daemon_config = DaemonConfig(api_key=api_key)
    self.config.daemon = daemon_config  # ⚠️ Only in memory
```

### 3. CLI Reads API Key (main.py:105-127)

```python
# CLI reads config
config_manager = init_config()
cfg = get_config()

# CLI gets API key
if cfg.daemon and cfg.daemon.api_key:
    client = IPCClient(api_key=cfg.daemon.api_key)  # ✅ Same key as daemon
```

### 4. IPCClient Adds Header (ipc_client.py:107-112)

```python
def _get_headers(self) -> dict[str, str]:
    headers = {}
    if self.api_key:
        headers[API_KEY_HEADER] = self.api_key  # ✅ X-CCBT-API-Key header
    return headers
```

### 5. Daemon Validates Header (ipc_server.py:136-150)

```python
# Middleware checks API key
api_key = request.headers.get(API_KEY_HEADER)
if not api_key or api_key != self.api_key:
    return ErrorResponse(error="Unauthorized", code="AUTH_REQUIRED")  # ❌ Reject
# ✅ Accept request
```

## Config File Structure

The API key is stored in the `[daemon]` section:

```toml
[daemon]
api_key = "d6bcd3466885d118d1d73e896dfc154c83d511f658d8e542f8b3b654f42a63be"
ipc_host = "127.0.0.1"
ipc_port = 8080
websocket_enabled = true
websocket_heartbeat_interval = 30.0
```

## Best Practices

1. **Always start daemon via CLI**: `btbt daemon start`
   - Ensures API key is saved to config file
   - Both processes use same API key

2. **Don't manually edit API key while daemon is running**
   - Daemon uses in-memory API key
   - CLI uses file-based API key
   - Mismatch causes authentication failures

3. **If you must change API key**:
   - Stop daemon: `btbt daemon stop`
   - Update config file
   - Start daemon: `btbt daemon start`

4. **Verify authentication**:
   - Check daemon status: `btbt daemon status`
   - Should show daemon is running and accessible

## Troubleshooting

### Problem: "Unauthorized" errors

**Cause:** API key mismatch between daemon and CLI

**Solutions:**
1. Check config file has API key: `cat ccbt.toml | grep api_key`
2. Restart daemon: `btbt daemon stop && btbt daemon start`
3. Verify both read same config file location

### Problem: "API key not found in config"

**Cause:** Config file doesn't have daemon section or API key

**Solution:**
1. Start daemon via CLI: `btbt daemon start`
2. CLI will generate and save API key automatically

### Problem: Daemon started directly, CLI can't connect

**Cause:** Daemon generated new API key but didn't save it

**Solution:**
1. Stop daemon
2. Start via CLI: `btbt daemon start`
3. CLI will ensure API key is saved

## Summary

✅ **Authentication works when:**
- Both daemon and CLI read from same config file
- API key is saved to config file (via CLI `daemon start`)
- Both processes use the same API key value

❌ **Authentication fails when:**
- Daemon generates new API key but doesn't save it
- Config file is manually edited while daemon is running
- Daemon and CLI read from different config files

**Recommended:** Always use `btbt daemon start` to ensure proper authentication setup.

