# CLI Command Protocol Violations Assessment

## Overview
This document identifies CLI commands that violate the configuration and session management protocol established in `ccbt/cli/main.py`.

## Protocol Requirements

### 1. Session Management Protocol
- **MUST** check for daemon PID file before creating `AsyncSessionManager`
- **MUST** route to daemon via IPC if PID file exists
- **MUST NOT** create local session when daemon is running (causes port conflicts)
- **SHOULD** warn user if daemon is running but command needs local execution

### 2. Configuration Management Protocol
- **MUST** use `ConfigManager(ctx.obj["config"])` to get config from CLI context
- **MUST** use `apply_cli_overrides(config_manager, kwargs)` when CLI options modify config
- **SHOULD** use `init_config()` only when no context is available

## Violations by Category

### Critical: Commands Creating AsyncSessionManager Without Daemon Check

These commands will cause port conflicts when daemon is running:

#### `ccbt/cli/file_commands.py` (6 violations)
- `list()` - Line 42: Creates session without daemon check
- `select()` - Line 167: Creates session without daemon check
- `deselect()` - Line 215: Creates session without daemon check
- `priority()` - Line 262: Creates session without daemon check
- `show()` - Line 307: Creates session without daemon check
- `verify()` - Line 362: Creates session without daemon check

**Impact**: All file management commands will conflict with daemon ports.

#### `ccbt/cli/queue_commands.py` (7 violations)
- `list()` - Line 32: Creates session without daemon check
- `add()` - Line 100: Creates session without daemon check
- `remove()` - Line 141: Creates session without daemon check
- `move()` - Line 181: Creates session without daemon check
- `clear()` - Line 222: Creates session without daemon check
- `pause()` - Line 262: Creates session without daemon check
- `resume()` - Line 298: Creates session without daemon check

**Impact**: All queue management commands will conflict with daemon ports.

#### `ccbt/cli/nat_commands.py` (5 violations)
- `status()` - Line 31: Creates session without daemon check
- `discover()` - Line 110: Creates session without daemon check
- `map()` - Line 174: Creates session without daemon check
- `unmap()` - Line 236: Creates session without daemon check
- `refresh()` - Line 276: Creates session without daemon check

**Impact**: All NAT commands will conflict with daemon ports.

#### `ccbt/cli/monitoring_commands.py` (1 violation)
- `dashboard()` - Line 32: Creates session without daemon check

**Impact**: Monitoring dashboard will conflict with daemon ports.

#### `ccbt/cli/diagnostics.py` (1 violation)
- `run_diagnostics()` - Line 48: Creates session without daemon check

**Impact**: Diagnostics will conflict with daemon ports (though this is a test command).

#### `ccbt/cli/xet_commands.py` (1 violation)
- `_get_xet_protocol()` helper - Line 26: Creates session without daemon check

**Impact**: All XET commands using this helper will conflict with daemon ports.

#### `ccbt/cli/ipfs_commands.py` (1 violation)
- `_get_ipfs_protocol()` helper - Line 32: Creates session without daemon check

**Impact**: All IPFS commands using this helper will conflict with daemon ports.

#### `ccbt/cli/scrape_commands.py` (2 violations)
- `scrape()` - Line 53: Creates session without daemon check
- `scrape_batch()` - Line 128: Creates session without daemon check

**Impact**: Scrape commands will conflict with daemon ports.

#### `ccbt/cli/main.py` (4 violations with warnings)
- `interactive()` - Line 1272: Creates session with warning but no routing
- `web()` - Line 1240: Creates session with warning but no routing
- `debug()` - Line 1362: Creates session with warning but no routing
- `resume()` - Line 1757: Creates session with warning but no routing

**Impact**: These commands warn but still create local sessions, causing conflicts.

### Moderate: Configuration Management Issues

#### Commands Not Using CLI Context
- `ccbt/cli/xet_commands.py`: Uses `ConfigManager(config_file)` directly instead of `ctx.obj["config"]`
- `ccbt/cli/utp_commands.py`: Line 230 uses `ConfigManager()` without context
- `ccbt/cli/proxy_commands.py`: Lines 107, 308 use `ConfigManager()` without context
- `ccbt/cli/ssl_commands.py`: Multiple commands use `ConfigManager()` without context
- `ccbt/cli/config_commands.py`: Uses `ConfigManager(config_file)` directly (acceptable for config commands)
- `ccbt/cli/interactive.py`: Uses `ConfigManager(None)` directly (acceptable for interactive mode)

#### Commands Not Applying CLI Overrides
- Most commands in `file_commands.py`, `queue_commands.py`, `nat_commands.py` don't have CLI options that modify config, so this is acceptable
- Commands that should use `apply_cli_overrides` but don't: None identified (most don't have config-modifying options)

## Summary Statistics

- **Total violations**: 28 commands creating sessions without daemon check
- **Critical violations**: 24 commands (will cause port conflicts)
- **Moderate violations**: 4 commands (warn but still create sessions)
- **Configuration issues**: 5+ files using ConfigManager without context (may be acceptable in some cases)

## Recommended Fixes

### Priority 1: Critical Session Management Violations

1. **Add daemon check pattern to all commands creating AsyncSessionManager:**
   ```python
   daemon_manager = DaemonManager()
   pid_file_exists = daemon_manager.pid_file.exists()
   
   if pid_file_exists:
       # Route to daemon via IPC or raise error
       # DO NOT create local session
   else:
       # Safe to create local session
       session = AsyncSessionManager(".")
   ```

2. **Commands that should route to daemon:**
   - All file management commands (should use IPC to modify daemon's torrents)
   - All queue management commands (should use IPC to modify daemon's queue)
   - NAT commands (should query daemon's NAT status)
   - Scrape commands (should use daemon's session for scraping)

3. **Commands that may need local execution:**
   - `diagnostics.py`: Test command, may need local session
   - `interactive.py`: TUI mode, may need local session (but should warn)
   - `web()`: Web interface, may need local session (but should warn)
   - `debug()`: Debug mode, may need local session (but should warn)

### Priority 2: Configuration Management

1. **Standardize ConfigManager usage:**
   - Use `ConfigManager(ctx.obj["config"])` when context is available
   - Use `init_config()` only when no context (daemon commands, standalone scripts)

2. **Apply CLI overrides:**
   - Commands with config-modifying options should use `apply_cli_overrides()`

## Implementation Notes

- The pattern established in `download()` and `magnet()` commands should be followed
- Helper functions like `_get_xet_protocol()` and `_get_ipfs_protocol()` should check for daemon
- Commands that need local execution should at minimum warn the user about potential conflicts

