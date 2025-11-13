# Debugging Daemon Silent Exit

## Problem
The daemon process exits silently when the CLI tries to connect to it, making it difficult to diagnose the root cause.

## Debugging Strategy

### 1. Comprehensive Debug Logging

A new debug logging system has been added that captures:
- All process lifecycle events
- Stack traces at critical points
- Event loop state
- Unhandled exceptions
- Process exit information

**Debug log location:** `~/.ccbt/daemon/debug.log`

### 2. What Gets Logged

The debug system automatically logs:
- Process startup and initialization
- DaemonMain instance creation
- Event loop state changes
- Main loop iterations (every 30 seconds)
- All exceptions with full stack traces
- Process exit events with stack traces
- Event loop closure detection
- Keep-alive task status

### 3. How to Use

#### Step 1: Start the daemon
```bash
uv run btbt -v daemon start --foreground
```

#### Step 2: In another terminal, try to connect
```bash
uv run btbt -v magnet "magnet:?xt=urn:btih:..."
```

#### Step 3: Check the debug log
```bash
# On Windows
type %USERPROFILE%\.ccbt\daemon\debug.log

# On Linux/Mac
cat ~/.ccbt/daemon/debug.log
```

### 4. What to Look For

The debug log will show:
1. **Where the daemon exits** - Look for "PROCESS EXITING" entries
2. **Stack trace at exit** - Shows what code was executing when exit occurred
3. **Event loop state** - Shows if the loop was closed or had no tasks
4. **Exceptions** - All exceptions are logged with full context
5. **Timing** - Timestamps show when events occurred

### 5. Key Debug Points

The debug system logs at these critical points:
- Process startup (`main()` entry)
- DaemonMain creation
- `daemon.run()` entry and exit
- Main loop entry
- Every 30 iterations (30 seconds)
- Event loop closure detection
- All exception handlers
- Process exit (via `atexit`)

### 6. Analyzing the Log

Look for patterns:
- **If daemon exits immediately after startup**: Check for exceptions during initialization
- **If daemon exits when CLI connects**: Check for IPC server errors or request handling issues
- **If event loop closes**: Check for task completion or loop closure
- **If no exit log**: Process may have been killed externally (check system logs)

### 7. Additional Debugging

If the debug log doesn't show the exit, check:
- System event logs (Windows Event Viewer)
- Process monitor (Task Manager / `htop`)
- Network connections (netstat / `ss`)
- Firewall logs
- Antivirus logs

### 8. Common Issues to Check

1. **Event loop exits**: Look for "Event loop is closed" messages
2. **IPC server crashes**: Look for IPC-related exceptions
3. **Signal handlers**: Check if signals are being sent
4. **Resource exhaustion**: Check memory/CPU usage
5. **Windows-specific issues**: Check for ProactorEventLoop errors

### 9. Next Steps

Once you have the debug log:
1. Identify the last logged event before exit
2. Check the stack trace at exit
3. Look for exceptions or errors
4. Check event loop state
5. Report findings with the debug log

## Example Debug Log Analysis

```
[2025-01-11 15:46:17] Daemon process starting - main() called
[2025-01-11 15:46:17] DaemonMain instance created successfully
[2025-01-11 15:46:17] Starting daemon.run()...
[2025-01-11 15:46:17] Daemon initialization complete, entering main loop
[2025-01-11 15:46:17] Entering main loop - waiting for shutdown signal
[2025-01-11 15:46:47] Main loop iteration 30 - daemon still running
[2025-01-11 15:47:17] Main loop iteration 60 - daemon still running
[2025-01-11 15:47:47] PROCESS EXITING - PID 12345
[2025-01-11 15:47:47] Current stack trace:
  File "ccbt/daemon/main.py", line 450, in run
    loop = asyncio.get_running_loop()
  ...
```

This shows the daemon was running normally, then exited. The stack trace shows where it exited.

