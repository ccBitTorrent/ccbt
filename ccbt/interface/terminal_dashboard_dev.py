"""Development entry point for Textual dev tools.

This allows running: textual run --dev -m ccbt.interface.terminal_dashboard_dev

Usage:
    textual run --dev -m ccbt.interface.terminal_dashboard_dev
    uv run textual run --dev -m ccbt.interface.terminal_dashboard_dev
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        DaemonInterfaceAdapter = None  # type: ignore[assignment, misc]
        AsyncSessionManager = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

# Import the dashboard and session classes
from ccbt.interface.terminal_dashboard import (
    TerminalDashboard,
    _ensure_daemon_running,  # noqa: PLC2701
    _show_startup_splash,  # noqa: PLC2701
)

# Cache for daemon readiness check to avoid redundant checks
_daemon_readiness_cache: dict[str, Any] = {
    "checked": False,
    "ready": False,
    "ipc_port": None,
    "api_key": None,
}


def get_app() -> TerminalDashboard:
    """Get TerminalDashboard app instance for textual run.
    
    Returns:
        TerminalDashboard app instance configured with session
        
    Raises:
        RuntimeError: If daemon cannot be started or is not accessible
        
    Note:
        The interface only becomes available when it's possible to connect to the daemon.
        This ensures clean connection without race conditions.
    """
    # CRITICAL: Dashboard ONLY works with daemon - no local sessions allowed
    # We use the executor pattern to connect through CLI commands when possible
    # The interface only becomes available when it's possible to connect
    # We must avoid asyncio.run() here as it creates a new event loop that conflicts with Textual's
    
    import threading
    
    from ccbt.config.config import get_config, init_config
    from ccbt.daemon.ipc_client import IPCClient
    from ccbt.daemon.utils import generate_api_key
    from ccbt.models import DaemonConfig
    from ccbt.executor.manager import ExecutorManager
    
    # Initialize config
    config_manager = init_config()
    cfg = get_config()
    
    if not cfg.daemon or not cfg.daemon.api_key:
        api_key = generate_api_key()
        cfg.daemon = DaemonConfig(api_key=api_key)
        logger.warning("Daemon config not found, generated new API key")
    else:
        api_key = cfg.daemon.api_key
    
    # CRITICAL: Cache daemon readiness check to avoid redundant checks
    # When get_app() is called multiple times (e.g., when app() is invoked), we don't want
    # to re-check daemon status every time. We cache the result and reuse it.
    global _daemon_readiness_cache
    
    # Check for --no-splash or -n flags in sys.argv
    import sys
    no_splash = "--no-splash" in sys.argv or "-n" in sys.argv
    
    # Start splash screen if enabled (for dev mode, always show splash to hide bootup logs)
    # Initialize before the if/else block so it's accessible throughout
    splash_manager = None
    splash_thread = None
    
    # Check if we've already verified daemon readiness
    if _daemon_readiness_cache["checked"] and _daemon_readiness_cache["ready"]:
        # Use cached values - skip the thread-based check
        logger.info("Using cached daemon readiness check (daemon already verified as ready)")
        ipc_port = _daemon_readiness_cache["ipc_port"]
        # Use cached API key if available, otherwise use config
        api_key = _daemon_readiness_cache.get("api_key") or api_key
        # Skip to creating IPCClient with cached values
        # No splash needed for cached check (daemon already running)
    else:
        # First time - check daemon readiness
        logger.info("Waiting for daemon to be ready before initializing interface...")
        
        # Start splash screen to hide bootup sequences (unless --no-splash or -n is set)
        try:
            if not no_splash:
                # For dev mode, show splash to hide bootup sequences
                # Verbosity count is 0 (NORMAL) for dev mode unless explicitly set
                # Create a console for splash screen (will be cleared before Textual starts)
                from rich.console import Console
                splash_console = Console()
                splash_manager, splash_thread = _show_startup_splash(
                    no_splash=no_splash,  # Respect --no-splash or -n flag
                    verbosity_count=0,  # Dev mode uses NORMAL verbosity
                    console=splash_console,  # Provide console for splash screen rendering
                )
        except Exception:
            # If splash fails, continue without it
            pass
        
        # Use a thread pool executor to run the async function in isolation
        # This prevents event loop conflicts with Textual
        result_container: list[tuple[bool, Any | None]] = []
        exception_container: list[Exception] = []
        
        async def _ensure_and_close() -> tuple[bool, Any | None]:
            """Ensure daemon is running and close the IPCClient before returning.
            
            This wrapper ensures the IPCClient is closed in the same event loop
            before asyncio.run() completes, preventing "Unclosed client session" warnings.
            Uses ONLY IPC client health checks - no PID file or process checks.
            """
            success, ipc_client = await _ensure_daemon_running(splash_manager=splash_manager)
            
            # CRITICAL: Close the IPCClient in the same event loop before returning
            # This prevents "Unclosed client session" warnings when the event loop closes
            # We create a new IPCClient in Textual's event loop, so we don't need this one
            if success and ipc_client:
                try:
                    await ipc_client.close()
                    logger.debug("Closed IPCClient from thread's event loop")
                except Exception as e:
                    logger.debug("Error closing IPCClient from thread: %s", e)
            
            # Return only success status - we don't need the client
            return (success, None)
        
        def run_in_thread():
            """Run async function in thread with its own event loop."""
            try:
                # Create new event loop in this thread (isolated from Textual's)
                # This checks if daemon is ready and starts it if needed
                # The wrapper ensures IPCClient is closed before the event loop closes
                result = asyncio.run(_ensure_and_close())
                result_container.append(result)
            except Exception as e:
                exception_container.append(e)
        
        # Start the thread
        thread = threading.Thread(target=run_in_thread, daemon=False)
        thread.start()
        
        # Wait for thread to complete (with timeout)
        # CRITICAL: Use a polling approach instead of blocking join to allow KeyboardInterrupt
        # to be handled properly. This prevents the thread.join() from blocking Ctrl+C.
        # CRITICAL: Use 90 second timeout minimum to allow for slow daemon startup
        # (NAT discovery ~35s, DHT bootstrap ~8s, IPC server startup, etc.)
        timeout = 90.0  # Minimum 90 seconds for daemon startup
        start_time = __import__('time').time()
        
        while thread.is_alive():
            elapsed = __import__('time').time() - start_time
            if elapsed >= timeout:
                # Thread is still running - timeout
                raise RuntimeError(
                    f"Timeout waiting for daemon to be ready (waited {timeout} seconds).\n"
                    "Please check:\n"
                    "  1. Daemon logs for startup errors\n"
                    "  2. Port conflicts (check if port is already in use)\n"
                    "  3. Permissions (ensure you have permission to start daemon)\n\n"
                    "To start daemon manually: 'btbt daemon start'"
                )
            # Use a short sleep to allow KeyboardInterrupt to be handled
            # CRITICAL: Catch KeyboardInterrupt here and re-raise it so it propagates properly
            try:
                thread.join(timeout=0.5)
            except KeyboardInterrupt:
                # User pressed Ctrl+C - cancel the thread and re-raise
                logger.info("Daemon wait interrupted by user (KeyboardInterrupt)")
                # CRITICAL FIX: Cannot set daemon status on active thread
                # Instead, just let the thread finish naturally - it's a daemon thread by default
                # The thread will exit when the main process exits
                raise
        
        # Check for exceptions
        if exception_container:
            e = exception_container[0]
            # Clear splash on error
            if splash_manager:
                try:
                    splash_manager.clear_progress_messages()
                except Exception:
                    pass
            logger.exception("Error ensuring daemon is ready: %s", e)
            raise RuntimeError(
                "Dashboard requires daemon to be running. "
                "Please start the daemon with 'btbt daemon start'"
            ) from e
        
        # Check result
        if not result_container:
            # Clear splash on error
            if splash_manager:
                try:
                    splash_manager.clear_progress_messages()
                except Exception:
                    pass
            raise RuntimeError(
                "Failed to get daemon connection result. "
                "Please start the daemon with 'btbt daemon start'"
            )
        
        success, _ = result_container[0]  # Don't reuse IPCClient from thread
        
        if not success:
            # Clear splash on error
            if splash_manager:
                try:
                    splash_manager.clear_progress_messages()
                except Exception:
                    pass
            raise RuntimeError(
                "Failed to start daemon. Cannot proceed without daemon.\n"
                "Please check:\n"
                "  1. Daemon logs for startup errors\n"
                "  2. Port conflicts (check if port is already in use)\n"
                "  3. Permissions (ensure you have permission to start daemon)\n\n"
                "To start daemon manually: 'btbt daemon start'"
            )
        
        # Cache the result for future calls
        from ccbt.cli.main import _get_daemon_ipc_port
        ipc_port = _get_daemon_ipc_port(cfg)
        _daemon_readiness_cache["checked"] = True
        _daemon_readiness_cache["ready"] = True
        _daemon_readiness_cache["ipc_port"] = ipc_port
        _daemon_readiness_cache["api_key"] = api_key  # Use api_key variable (already set from config above)
        logger.info("Cached daemon readiness check result (port=%s)", ipc_port)
    
    # CRITICAL: Create a NEW IPCClient in the current (synchronous) context
    # This client will be used in Textual's event loop, not the thread's event loop
    # The IPCClient's _ensure_session() will create the aiohttp session in Textual's loop
    # when it's first used (in on_mount -> _connect_to_daemon)
    # This prevents "Event loop is closed" and session duplication errors
    # ipc_port is already set from the cached check above
    client_host = "127.0.0.1"  # Always use 127.0.0.1 for client connections
    base_url = f"http://{client_host}:{ipc_port}"
    
    logger.info("Creating new IPCClient for Textual's event loop (base_url=%s)", base_url)
    # Create NEW IPCClient - will be bound to Textual's event loop when first used
    # DO NOT reuse the IPCClient from the thread - it's bound to a different (closed) event loop
    # Use api_key from cache or config (api_key is set above in both code paths)
    ipc_client = IPCClient(api_key=api_key, base_url=base_url)
    
    # Daemon is ready - get executor using executor pattern
    # This ensures we use CLI commands when possible
    executor_manager = ExecutorManager.get_instance()
    executor = executor_manager.get_executor(ipc_client=ipc_client)
    
    # Create session adapter that uses the executor pattern
    # The executor will handle connection through CLI commands when possible
    logger.info("Creating DaemonInterfaceAdapter...")
    session = DaemonInterfaceAdapter(ipc_client)
    logger.info("DaemonInterfaceAdapter created successfully (session=%s)", type(session).__name__)
    
    logger.info("Daemon is ready - interface is now available")
    
    # Create the TerminalDashboard app instance
    logger.info("Creating TerminalDashboard app instance...")
    try:
        # Pass splash_manager to TerminalDashboard so it can end when dashboard renders
        app = TerminalDashboard(session, refresh_interval=1.0, splash_manager=splash_manager)
        logger.info("TerminalDashboard app instance created successfully (app=%s, type=%s)", app, type(app).__name__)
        logger.info("Returning app to Textual's run command...")
        return app
    except Exception as e:
        # Clear splash on error
        if splash_manager:
            try:
                splash_manager.clear_progress_messages()
                # Restore log level if it was suppressed
                import logging
                root_logger = logging.getLogger()
                if hasattr(splash_manager, '_original_log_level'):
                    root_logger.setLevel(splash_manager._original_log_level)
            except Exception:
                pass
        logger.exception("Failed to create TerminalDashboard app: %s", e)
        raise RuntimeError(f"Failed to create TerminalDashboard app: {e}") from e


# CRITICAL: Textual's `run` command looks for an `app` variable in the module
# When using `textual run --dev ccbt.interface.terminal_dashboard_dev`, Textual will:
# 1. Import this module
# 2. Look for `app` variable (or `get_app()` function)
# 3. If `app` is found and callable, call it: `app().run()`
# 4. If `app` is found and not callable, use it directly: `app.run()`
# 5. If `get_app()` is found, call it to get the app instance
#
# Based on the error "TypeError: 'TerminalDashboard' object is not callable",
# Textual is trying to call `app()` as a function. So we make `app` a callable
# that returns the app instance. This allows lazy initialization - the app is
# only created when Textual calls `app()`, which happens after import.

# Expose app variable for Textual's run command
# CRITICAL: Textual's run command may try to call `app()` as a function
# So we need to make `app` a callable that returns the app instance
# We use lazy initialization to avoid creating the app twice
_app_instance: TerminalDashboard | None = None
_daemon_ready: bool = False

def _get_app_instance() -> TerminalDashboard:
    """Get or create the app instance (lazy initialization)."""
    global _app_instance, _daemon_ready
    
    if _app_instance is None:
        logger.info("Creating app instance for Textual's run command")
        try:
            _app_instance = get_app()  # This will block until daemon is ready
            _daemon_ready = True
            logger.info("App instance created and ready for Textual's run command")
        except KeyboardInterrupt:
            # If user presses Ctrl+C during daemon wait, re-raise it
            logger.info("App creation interrupted by user")
            raise
        except Exception as e:
            logger.exception("Failed to create app instance: %s", e)
            raise
    return _app_instance

# CRITICAL: Textual's run command behavior:
# - If `app` is callable, it calls `app()` and then calls `.run()` on the result
# - If `app` is an App instance, it calls `app.run()` directly
# - If `get_app()` function exists, it calls `get_app()` and then calls `.run()` on the result
#
# Based on testing, Textual seems to call `app()` when it's callable, but then might not
# be calling `.run()` on the result. So we'll make `app` directly return the instance
# and ensure Textual can call `.run()` on it.
#
# However, we need lazy initialization to avoid blocking on import. So we'll use a
# callable that returns the instance, but we'll also expose `get_app()` as a fallback.

# Make app a callable that returns the app instance
# Textual will call `app()` to get the instance, then call `.run()` on it
if __name__ != "__main__":
    # Being imported (likely by Textual's run command)
    # Create app as a callable that returns the instance
    # This will block on first call until daemon is ready
    logger.info("Module being imported - setting up app callable for Textual's run command")
    
    # CRITICAL: Textual's run command calls `app().run()` when `app` is callable
    # So we need to make `app` a callable that returns the instance
    # The instance will be created lazily on first call
    def app() -> TerminalDashboard:
        """Get app instance for Textual's run command.
        
        Textual will call this function, then call .run() on the returned instance.
        This allows lazy initialization - the app is only created when Textual calls app().
        """
        instance = _get_app_instance()
        logger.info("App instance retrieved (type=%s), Textual will call .run() on it", type(instance).__name__)
        # Verify the instance has a run method
        if not hasattr(instance, 'run'):
            logger.error("App instance does not have run() method!")
            raise AttributeError("App instance missing run() method")
        logger.info("App instance has run() method, ready for Textual")
        return instance
    
    logger.info("App callable ready for Textual's run command")
else:
    # Being executed directly - app will be created in main block
    app = None  # type: ignore[assignment]

# CRITICAL: When using `textual run --dev`, Textual will import this module and call `get_app()`
# directly. It will NOT execute the `if __name__ == "__main__":` block.
# 
# If you want to run this file directly (not via textual run), use:
#   python -m ccbt.interface.terminal_dashboard_dev
# This will execute the main block below.
#
# When using `textual run --dev ccbt\\interface\\terminal_dashboard_dev.py`, Textual executes
# the file directly, which triggers the main block. This is why we need to handle it here.

if __name__ == "__main__":
    # Direct execution fallback (for testing without textual run)
    # This block is executed when running the file directly (not via textual run -m)
    try:
        import sys
        # Check if we're being run by textual run command
        if "textual" in sys.modules and hasattr(sys.modules.get("textual"), "run"):
            # Being run by textual run - just call get_app() and let textual handle it
            logger.info("Running via textual run command")
            app = get_app()
            logger.info("Starting TerminalDashboard app via textual run...")
            app.run()
        else:
            # Direct execution - full initialization
            logger.info("Running TerminalDashboard directly (not via textual run)")
            app = get_app()
            logger.info("Starting TerminalDashboard app...")
            app.run()
    except KeyboardInterrupt:
        logger.info("TerminalDashboard interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("Failed to run TerminalDashboard: %s", e)
        raise

