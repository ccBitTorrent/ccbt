"""Daemon main entry point.

from __future__ import annotations

Main entry point for background daemon process.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from ccbt.config.config import init_config
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_protocol import EventType
from ccbt.daemon.ipc_server import IPCServer  # type: ignore[attr-defined]
from ccbt.daemon.state_manager import StateManager
from ccbt.monitoring import init_metrics, shutdown_metrics
from ccbt.session.session import AsyncSessionManager
from ccbt.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


async def _restore_torrent_config(
    session_manager: AsyncSessionManager,
    info_hash_hex: str,
    torrent_state: Any,
) -> None:
    """Restore per-torrent options and rate limits from state.

    Args:
        session_manager: Session manager instance
        info_hash_hex: Torrent info hash as hex string
        torrent_state: TorrentState instance with per_torrent_options and rate_limits

    """
    try:
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        async with session_manager.lock:
            torrent_session = session_manager.torrents.get(info_hash_bytes)
            if torrent_session:
                # Restore per-torrent options
                if torrent_state.per_torrent_options:
                    torrent_session.options.update(torrent_state.per_torrent_options)
                    # Apply the restored options
                    if hasattr(torrent_session, "_apply_per_torrent_options"):
                        torrent_session._apply_per_torrent_options()
                    logger.debug(
                        "Restored per-torrent options for %s: %s",
                        info_hash_hex[:12],
                        list(torrent_state.per_torrent_options.keys()),
                    )

                # Restore rate limits
                if torrent_state.rate_limits:
                    down_kib = torrent_state.rate_limits.get("down_kib", 0)
                    up_kib = torrent_state.rate_limits.get("up_kib", 0)
                    await session_manager.set_rate_limits(
                        info_hash_hex, down_kib, up_kib
                    )
                    logger.debug(
                        "Restored rate limits for %s: down=%d KiB/s, up=%d KiB/s",
                        info_hash_hex[:12],
                        down_kib,
                        up_kib,
                    )
    except Exception as e:
        logger.debug("Failed to restore per-torrent config for %s: %s", info_hash_hex[:12], e)


class DaemonMain:
    """Main daemon process manager."""

    def __init__(
        self,
        config_file: str | Path | None = None,
        foreground: bool = False,
    ):
        """Initialize daemon main.

        Args:
            config_file: Path to config file
            foreground: Run in foreground (for debugging)

        """
        self.foreground = foreground
        self.config_manager = init_config(config_file)
        self.config = self.config_manager.config

        # Initialize components
        # Handle case where daemon config might be None
        daemon_state_dir = None
        if hasattr(self.config, "daemon") and self.config.daemon is not None:
            daemon_state_dir = self.config.daemon.state_dir

        self.daemon_manager = DaemonManager(
            state_dir=daemon_state_dir,
        )

        self.state_manager = StateManager(
            state_dir=daemon_state_dir,
        )

        self.session_manager: AsyncSessionManager | None = None
        self.ipc_server: IPCServer | None = None

        self._shutdown_event = asyncio.Event()
        self._auto_save_task: asyncio.Task | None = None
        self._stopping = False  # Flag to prevent double-calling stop()

    async def start(self) -> None:
        """Start daemon process."""
        logger.info("Starting ccBitTorrent daemon...")

        # CRITICAL FIX: Acquire lock file EARLY in startup process
        # This prevents multiple daemon instances from starting simultaneously
        # Must be done BEFORE any initialization to prevent resource conflicts
        if not self.daemon_manager.acquire_lock():
            # Check if lock file exists and if process is still running
            if self.daemon_manager.lock_file.exists():
                try:
                    lock_pid_text = self.daemon_manager.lock_file.read_text(
                        encoding="utf-8"
                    ).strip()
                    if lock_pid_text.isdigit():
                        import os

                        lock_pid = int(lock_pid_text)
                        try:
                            os.kill(lock_pid, 0)  # Check if process exists
                            raise RuntimeError(
                                f"Daemon is already running (PID {lock_pid}). "
                                "Cannot start another instance."
                            )
                        except (OSError, ProcessLookupError) as e:
                            # Process is dead - remove stale lock and retry
                            logger.warning(
                                "Removing stale lock file (process %d not running)", lock_pid
                            )
                            with contextlib.suppress(OSError):
                                self.daemon_manager.lock_file.unlink()
                            # Retry acquiring lock
                            if not self.daemon_manager.acquire_lock():
                                raise RuntimeError(
                                    "Cannot acquire daemon lock file. "
                                    "Another daemon may be starting."
                                ) from e
                except Exception as e:
                    logger.warning("Error checking lock file: %s, removing stale lock", e)
                    with contextlib.suppress(OSError):
                        self.daemon_manager.lock_file.unlink()
                    # Retry acquiring lock
                    if not self.daemon_manager.acquire_lock():
                        raise RuntimeError(
                            "Cannot acquire daemon lock file. "
                            "Another daemon may be starting."
                        ) from e
            else:
                raise RuntimeError(
                    "Cannot acquire daemon lock file. "
                    "Another daemon may be starting."
                )

        # Setup signal handlers (before writing PID file)
        self.daemon_manager.setup_signal_handlers(self._shutdown_handler)

        # CRITICAL FIX: Initialize security components BEFORE session manager
        # This ensures API key, Ed25519 keys, and TLS are ready before NAT manager starts
        # Security initialization must happen before any network components
        daemon_config = self.config.daemon
        api_key: str | None = None
        key_manager = None
        tls_enabled = False

        if daemon_config:
            # Get or generate API key
            api_key = daemon_config.api_key
            if not api_key:
                # Generate a new API key if not set
                import secrets

                api_key = secrets.token_hex(32)
                daemon_config.api_key = api_key
                logger.info("Generated new API key for daemon")
            else:
                logger.debug("Using existing API key from config")
        else:
            # Generate a default API key if daemon_config is None
            import secrets

            api_key = secrets.token_hex(32)
            logger.info("Generated default API key for daemon (no daemon config)")

            # Initialize Ed25519 key manager
            try:
                from ccbt.security.key_manager import Ed25519KeyManager

                key_dir = daemon_config.ed25519_key_path if daemon_config else None
                key_manager = Ed25519KeyManager(key_dir=key_dir)
                # Get or create key pair
                key_manager.get_or_create_keypair()
                # Store public key in config
                public_key_hex = key_manager.get_public_key_hex()
                if daemon_config:
                    if not daemon_config.ed25519_public_key:
                        daemon_config.ed25519_public_key = public_key_hex
                        logger.info("Stored Ed25519 public key in daemon config")
                # Update config if it was just created
                elif daemon_config:
                    daemon_config.ed25519_public_key = public_key_hex
            except Exception as e:
                logger.warning(
                    "Failed to initialize Ed25519 key manager: %s. "
                    "Continuing with api_key authentication only.",
                    e,
                )

            # Get TLS enabled flag from config (defaults to False)
            tls_enabled = daemon_config.tls_enabled if daemon_config else False
            if tls_enabled:
                logger.info("TLS/HTTPS enabled for IPC server")
            else:
                logger.debug("TLS/HTTPS disabled for IPC server (using HTTP)")

        # Store security components for later use in IPC server
        self._api_key = api_key
        self._key_manager = key_manager
        self._tls_enabled = tls_enabled

        # Initialize session manager (after security initialization)
        # Use config.disk.download_dir if set, otherwise default to "."
        default_output_dir = (
            self.config.disk.download_dir
            if self.config.disk.download_dir and self.config.disk.download_dir.strip()
            else "."
        )
        self.session_manager = AsyncSessionManager(
            output_dir=default_output_dir,
        )

        try:
            # Start session manager (must be started before restoring torrents)
            # NAT manager will start as part of session manager startup
            await self.session_manager.start()

            # Initialize metrics collection
            try:
                metrics_collector = await init_metrics()
                if metrics_collector:
                    # Set session reference to enable collection of DHT, queue, disk I/O, and tracker metrics
                    metrics_collector.set_session(self.session_manager)
                    logger.info(
                        "Metrics collection initialized and session reference set"
                    )
                else:
                    logger.debug(
                        "Metrics collection not enabled or failed to initialize"
                    )
            except Exception:
                logger.exception(
                    "Error initializing metrics collection, continuing without metrics"
                )

            # CRITICAL FIX: IPC server initialization moved here (after session manager start)
            # Security components were initialized earlier, so we can use them now
            # Get IPC configuration
            ipc_host = daemon_config.ipc_host if daemon_config else "127.0.0.1"
            ipc_port = daemon_config.ipc_port if daemon_config else 64124
            websocket_enabled = (
                daemon_config.websocket_enabled if daemon_config else True
            )
            websocket_heartbeat = (
                daemon_config.websocket_heartbeat_interval
                if daemon_config
                else 30.0
            )

            # CRITICAL FIX: Check if IPC port is available before attempting to bind
            from ccbt.utils.port_checker import (
                get_port_conflict_resolution,
                is_port_available,
            )

            bind_host = ipc_host if ipc_host != "0.0.0.0" else "127.0.0.1"  # nosec B104 - IPC server converts 0.0.0.0 to 127.0.0.1 for localhost-only binding
            port_available, port_error = is_port_available(bind_host, ipc_port, "tcp")
            if not port_available:
                # CRITICAL FIX: Distinguish between permission errors and port conflicts
                # Check for permission denied in multiple ways (error code 10013 on Windows, 13 on Unix)
                from ccbt.utils.port_checker import get_permission_error_resolution

                is_permission_error = (
                    port_error
                    and (
                        "Permission denied" in port_error
                        or "10013" in str(port_error)
                        or "WSAEACCES" in str(port_error)
                        or "EACCES" in str(port_error)
                        or "forbidden" in str(port_error).lower()
                    )
                )
                if is_permission_error:
                    resolution = get_permission_error_resolution(ipc_port, "tcp")
                    error_msg = (
                        f"IPC server port {ipc_port} cannot be bound.\n"
                        f"{port_error}\n\n"
                        f"{resolution}"
                    )
                else:
                    resolution = get_port_conflict_resolution(ipc_port, "tcp")
                    error_msg = (
                        f"IPC server port {ipc_port} is not available.\n"
                        f"{port_error}\n\n"
                        f"Port {ipc_port} (TCP) may be already in use.\n"
                        f"{resolution}"
                    )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Ensure api_key is not None (required by IPCServer)
            if not self._api_key:
                import secrets

                self._api_key = secrets.token_hex(32)
                logger.warning("API key was None, generated a new one")

            self.ipc_server = IPCServer(
                session_manager=self.session_manager,
                api_key=self._api_key,
                key_manager=self._key_manager,
                host=ipc_host,
                port=ipc_port,
                websocket_enabled=websocket_enabled,
                websocket_heartbeat_interval=websocket_heartbeat,
                tls_enabled=self._tls_enabled,
            )

            # CRITICAL FIX: Set up session manager callbacks to emit WebSocket events
            # This ensures completion events are properly propagated to clients
            async def on_torrent_complete_callback(info_hash: bytes, name: str) -> None:
                """Handle torrent completion and emit WebSocket event."""
                try:
                    info_hash_hex = info_hash.hex()
                    logger.info(
                        "Torrent completed: %s (%s)", name, info_hash_hex[:16]
                    )
                    # Emit WebSocket event for completion
                    await self.ipc_server._emit_websocket_event(
                        EventType.TORRENT_COMPLETED,
                        {"info_hash": info_hash_hex, "name": name},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to emit WebSocket event for completed torrent %s: %s",
                        info_hash.hex()[:16] if info_hash else "unknown",
                        e,
                        exc_info=True,
                    )

            self.session_manager.on_torrent_complete = on_torrent_complete_callback

            # Start IPC server
            await self.ipc_server.start()

            # Emit SERVICE_STARTED event for IPC server
            try:
                await self.ipc_server._emit_websocket_event(
                    EventType.SERVICE_STARTED,
                    {"service_name": "ipc_server", "status": "running"},
                )
            except Exception as e:
                logger.debug("Failed to emit SERVICE_STARTED event for IPC server: %s", e)
            
            # Set up event bridge to convert utils.events to IPC WebSocket events
            await self.ipc_server._setup_event_bridge()

            # CRITICAL FIX: Verify IPC server is actually accepting HTTP connections before writing PID file
            # Socket test alone isn't sufficient - aiohttp might not be ready for HTTP yet
            # This ensures CLI can connect immediately after PID file is written
            import aiohttp

            from ccbt.daemon.ipc_protocol import API_KEY_HEADER

            verify_host = (
                "127.0.0.1"
                if self.ipc_server.host == "0.0.0.0"  # nosec B104 - Verification host for IPC server, converts 0.0.0.0 to 127.0.0.1
                else self.ipc_server.host
            )
            max_retries = 5  # Reduced from 15 - sufficient for local server (optimized for faster startup)
            retry_delay = 0.1  # Reduced from 0.2 - faster checks
            http_ready = False

            # Use HTTPS if TLS is enabled, otherwise HTTP
            protocol = "https" if self._tls_enabled else "http"
            url = f"{protocol}://{verify_host}:{self.ipc_server.port}/api/v1/status"

            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        headers = {}
                        if self._api_key:
                            headers[API_KEY_HEADER] = self._api_key
                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=2.0),
                            ssl=False,  # Disable SSL verification for local connections
                        ) as resp:
                            if resp.status == 200:
                                http_ready = True
                                logger.debug(
                                    "IPC server HTTP verified as ready on %s:%d (bound to %s)",
                                    verify_host,
                                    self.ipc_server.port,
                                    self.ipc_server.host,
                                )
                                break
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < max_retries - 1:
                        logger.debug(
                            "IPC server HTTP not yet ready (attempt %d/%d): %s, retrying in %.1fs...",
                            attempt + 1,
                            max_retries,
                            e,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        raise RuntimeError(
                            f"IPC server HTTP not ready on {self.ipc_server.host}:{self.ipc_server.port} "
                            f"after {max_retries} attempts (last error: {e})"
                        ) from e
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(
                            "Error verifying IPC server HTTP (attempt %d/%d): %s, retrying in %.1fs...",
                            attempt + 1,
                            max_retries,
                            e,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        raise RuntimeError(
                            f"IPC server HTTP verification failed on {self.ipc_server.host}:{self.ipc_server.port} "
                            f"after {max_retries} attempts (last error: {e})"
                        ) from e

            if not http_ready:
                raise RuntimeError(
                    f"IPC server HTTP not ready on {self.ipc_server.host}:{self.ipc_server.port} "
                    f"after {max_retries} attempts"
                )

            # CRITICAL FIX: Write PID file ONLY after IPC server is ready
            # This ensures CLI can connect immediately after PID file is written
            # Lock is already acquired at start of this method
            self.daemon_manager.write_pid(acquire_lock=False)

            # Start auto-save task
            auto_save_interval = (
                daemon_config.auto_save_interval if daemon_config else 60.0
            )

            self._auto_save_task = asyncio.create_task(
                self._auto_save_loop(auto_save_interval),
            )

            # Load persisted state and restore torrents
            state = await self.state_manager.load_state()
            if state:
                logger.info(
                    "Loaded persisted state with %d torrents", len(state.torrents)
                )
                if await self.state_manager.validate_state(state):
                    restored_count = 0
                    for info_hash_hex, torrent_state in state.torrents.items():
                        try:
                            # Restore torrent using source info
                            from pathlib import Path

                            if (
                                torrent_state.torrent_file_path
                                and Path(torrent_state.torrent_file_path).exists()
                            ):
                                await self.session_manager.add_torrent(
                                    torrent_state.torrent_file_path,
                                    resume=True,
                                )
                                # Restore per-torrent options and rate limits
                                await _restore_torrent_config(
                                    self.session_manager,
                                    info_hash_hex,
                                    torrent_state,
                                )
                                restored_count += 1
                                logger.info(
                                    "Restored torrent from file: %s",
                                    torrent_state.torrent_file_path,
                                )
                            elif torrent_state.magnet_uri:
                                await self.session_manager.add_magnet(
                                    torrent_state.magnet_uri,
                                    resume=True,
                                )
                                # Restore per-torrent options and rate limits
                                await _restore_torrent_config(
                                    self.session_manager,
                                    info_hash_hex,
                                    torrent_state,
                                )
                                restored_count += 1
                                logger.info(
                                    "Restored torrent from magnet: %s",
                                    torrent_state.magnet_uri[:50] + "...",
                                )
                            else:
                                logger.warning(
                                    "Torrent %s has no source info, skipping",
                                    info_hash_hex,
                                )
                        except Exception:
                            logger.exception(
                                "Failed to restore torrent %s",
                                info_hash_hex,
                            )
                    logger.info(
                        "Restored %d/%d torrents from state",
                        restored_count,
                        len(state.torrents),
                    )
                else:
                    logger.warning("State validation failed, skipping restoration")

            logger.info("Daemon started successfully")
        except Exception as e:
            # CRITICAL FIX: Remove PID file if startup fails
            # This prevents CLI from thinking daemon is running when it crashed
            logger.exception(
                "Failed to start daemon (error: %s), cleaning up PID file and lock",
                e,
            )
            try:
                # Release lock and remove PID file on error
                self.daemon_manager.release_lock()
                self.daemon_manager.remove_pid()
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to remove PID file/lock during cleanup: %s",
                    cleanup_error,
                )
            # Re-raise to let main() handle it
            raise

    async def _shutdown_handler(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown requested")
        self._shutdown_event.set()

    async def _auto_save_loop(self, interval: float) -> None:
        """Periodic auto-save loop.

        Args:
            interval: Save interval in seconds

        """
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(interval)
                if not self._shutdown_event.is_set() and self.session_manager:
                    try:
                        await self.state_manager.save_state(self.session_manager)
                        logger.debug("Auto-saved state")
                    except Exception:
                        logger.exception("Error auto-saving state")
        except asyncio.CancelledError:
            pass

    async def run(self) -> None:
        """Run daemon main loop."""
        from ccbt.daemon.debug_utils import (
            debug_log,
            debug_log_event_loop_state,
            debug_log_exception,
            debug_log_stack,
        )

        try:
            debug_log("DaemonMain.run() called - starting daemon...")
            debug_log_stack("Stack at start of run()")
            await self.start()
            logger.info("Daemon initialization complete, entering main loop")
            debug_log("Daemon initialization complete, entering main loop")
            debug_log_event_loop_state()
        except Exception as e:
            debug_log_exception("Fatal error during daemon startup", e)
            debug_log_stack("Stack after startup failure")
            logger.exception("Fatal error during daemon startup: %s", e)
            # Clean up PID file if startup failed
            with contextlib.suppress(Exception):
                self.daemon_manager.remove_pid()
            raise

        try:
            # Wait for shutdown signal
            # CRITICAL FIX: Use an infinite loop with periodic checks instead of await wait()
            # On Windows, await event.wait() may not keep the event loop alive if there are no other tasks
            # The IPC server site should create tasks, but we need to ensure the loop stays alive
            logger.debug("Waiting for shutdown signal...")
            # CRITICAL: Verify IPC server is still running before waiting
            # Use a more lenient check - just verify the site exists, not the internal sockets
            # The sockets check can be unreliable on Windows and may cause false positives
            if self.ipc_server and self.ipc_server.site:
                # Only check if site exists, not the internal socket state
                # The site will keep the server alive as long as it exists
                if not hasattr(self.ipc_server.site, "_server"):
                    logger.warning(
                        "IPC server site has no _server attribute - this may be a false positive. "
                        "Continuing anyway - the server should still be running."
                    )
                    # Don't raise - just log a warning and continue
                    # The site.start() already verified the server is listening at startup
                # Don't check sockets - this can be unreliable and cause false positives
                # The site.start() already verified the server is listening

            # CRITICAL FIX: Use a loop with periodic sleep to keep the event loop alive
            # This ensures the daemon stays running even on Windows where event.wait() might not be enough
            # The periodic sleep creates tasks that keep the event loop from exiting
            # Also verify IPC server is still running periodically
            iteration = 0
            consecutive_errors = 0
            max_consecutive_errors = 10  # Allow some errors but not too many

            from ccbt.daemon.debug_utils import debug_log, debug_log_event_loop_state

            # CRITICAL FIX: Initialize keep_alive to None to ensure it's always in scope
            # This prevents NameError if exception occurs before task creation
            keep_alive: asyncio.Task | None = None

            # CRITICAL: Create a background task to keep the event loop alive
            # This ensures the loop never exits even if all other tasks complete
            async def keep_alive_task():
                """Background task to keep event loop alive."""
                try:
                    debug_log("Keep-alive task started")
                    while not self._shutdown_event.is_set():
                        # Use interruptible sleep that checks for shutdown frequently
                        # This ensures the task responds quickly to shutdown signals
                        sleep_interval = 5.0  # Check every 5 seconds
                        elapsed = 0.0
                        total_sleep = 60.0  # Original sleep duration
                        while elapsed < total_sleep and not self._shutdown_event.is_set():
                            await asyncio.sleep(sleep_interval)
                            elapsed += sleep_interval
                        
                        if self._shutdown_event.is_set():
                            break
                            
                        logger.debug("Keep-alive task: event loop is still alive")
                        debug_log("Keep-alive task: event loop is still alive")
                        debug_log_event_loop_state()
                except asyncio.CancelledError:
                    logger.debug("Keep-alive task cancelled (shutdown)")
                    debug_log("Keep-alive task cancelled (shutdown)")

            keep_alive = asyncio.create_task(keep_alive_task())
            debug_log("Keep-alive task created: %s", keep_alive)

            try:
                debug_log("Entering main loop - waiting for shutdown signal")
                while not self._shutdown_event.is_set():
                    try:
                        # CRITICAL FIX: Use wait with timeout for more responsive shutdown
                        # This allows the loop to check the shutdown event more frequently
                        # while still keeping the event loop alive
                        try:
                            # Wait for shutdown event with 0.1 second timeout
                            # This makes shutdown more responsive (checks 10 times per second)
                            await asyncio.wait_for(
                                self._shutdown_event.wait(), timeout=0.1
                            )
                            # If we get here, shutdown event was set
                            break
                        except asyncio.TimeoutError:
                            # Timeout is expected - continue loop to check again
                            # CRITICAL FIX: Check shutdown event immediately after timeout
                            # This ensures we break immediately if shutdown was requested
                            if self._shutdown_event.is_set():
                                break
                            pass
                        except KeyboardInterrupt:
                            # CRITICAL FIX: Handle KeyboardInterrupt by setting shutdown event and breaking
                            # Don't re-raise - let the signal handler and outer handler deal with it
                            # The signal handler should have already set the shutdown event, but set it here too
                            logger.info("KeyboardInterrupt detected in main loop wait_for()")
                            debug_log("KeyboardInterrupt detected in main loop wait_for()")
                            # Set shutdown event to ensure cleanup
                            self._shutdown_event.set()
                            # Break out of the loop immediately
                            break
                        
                        # CRITICAL FIX: Check shutdown event again before continuing
                        # This ensures we break immediately if shutdown was requested during the wait
                        if self._shutdown_event.is_set():
                            break
                        
                        iteration += 1
                        consecutive_errors = (
                            0  # Reset error counter on successful iteration
                        )

                        # Debug logging every 30 iterations (30 seconds)
                        if iteration % 30 == 0:
                            debug_log(
                                "Main loop iteration %d - daemon still running",
                                iteration,
                            )
                            debug_log_event_loop_state()

                        # Periodically verify IPC server is still running (every 10 seconds)
                        if iteration % 10 == 0:
                            if self.ipc_server and self.ipc_server.site:
                                # Verify site is still active
                                if (
                                    not hasattr(self.ipc_server.site, "_server")
                                    or not self.ipc_server.site._server
                                ):
                                    logger.warning(
                                        "IPC server site lost _server attribute - this may indicate a problem"
                                    )
                            else:
                                logger.warning(
                                    "IPC server or site is None - daemon may be in invalid state"
                                )

                        # CRITICAL: Verify event loop is still running
                        # On Windows, the loop can exit if there are no tasks
                        try:
                            loop = asyncio.get_running_loop()
                            if loop.is_closed():
                                logger.critical(
                                    "Event loop is closed! This should not happen."
                                )
                                debug_log("CRITICAL: Event loop is closed!")
                                debug_log_stack("Stack when loop closed detected")
                                break
                        except RuntimeError as e:
                            logger.critical(
                                "Cannot get running event loop! This should not happen."
                            )
                            debug_log("CRITICAL: Cannot get running event loop: %s", e)
                            debug_log_stack("Stack when loop access failed")
                            break

                        # CRITICAL FIX: Check shutdown event one more time before sleep
                        # This ensures we break immediately if shutdown was requested
                        if self._shutdown_event.is_set():
                            break

                        # Check if shutdown was requested (will be checked in the while condition)
                    except asyncio.CancelledError:
                        # Cancelled errors are expected during shutdown
                        logger.debug(
                            "Main loop iteration cancelled (shutdown in progress)"
                        )
                        debug_log(
                            "Main loop iteration cancelled (shutdown in progress)"
                        )
                        break
                    except KeyboardInterrupt:
                        # CRITICAL FIX: Handle KeyboardInterrupt by setting shutdown event and breaking
                        # The signal handler should have already set the shutdown event, but set it here too
                        logger.info("KeyboardInterrupt detected in main loop (outer handler)")
                        debug_log("KeyboardInterrupt detected in main loop (outer handler)")
                        # Set shutdown event to ensure cleanup
                        self._shutdown_event.set()
                        # Break out of the loop immediately - don't re-raise
                        break
                    except Exception as e:
                        # CRITICAL: Catch any exceptions in the main loop to prevent daemon from exiting
                        from ccbt.daemon.debug_utils import debug_log_exception

                        consecutive_errors += 1
                        debug_log_exception(
                            "Error in daemon main loop iteration (error %d/%d)"
                            % (consecutive_errors, max_consecutive_errors),
                            e,
                        )
                        logger.exception(
                            "Error in daemon main loop iteration (error %d/%d)",
                            consecutive_errors,
                            max_consecutive_errors,
                        )

                        # If we get too many consecutive errors, something is seriously wrong
                        if consecutive_errors >= max_consecutive_errors:
                            logger.critical(
                                "Too many consecutive errors in daemon main loop (%d). "
                                "This may indicate a serious problem. Daemon will continue running but may be unstable.",
                                consecutive_errors,
                            )
                            # Reset counter to allow recovery
                            consecutive_errors = 0

                        # CRITICAL FIX: Check shutdown event before sleep
                        # This ensures we break immediately if shutdown was requested
                        if self._shutdown_event.is_set():
                            break

                        # Continue the loop - don't exit
                        await asyncio.sleep(1.0)  # Wait before next iteration

                logger.info("Shutdown signal received")
            finally:
                # Cancel keep-alive task
                # CRITICAL FIX: Check if keep_alive exists and is not done before cancelling
                if keep_alive is not None and not keep_alive.done():
                    keep_alive.cancel()
                    with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                        # Use wait_for with timeout to prevent hanging
                        await asyncio.wait_for(keep_alive, timeout=1.0)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            from ccbt.daemon.debug_utils import debug_log, debug_log_stack

            debug_log("Received keyboard interrupt")
            debug_log_stack("Stack after KeyboardInterrupt")
            # CRITICAL FIX: Set global shutdown flag early to suppress verbose logging
            try:
                from ccbt.utils.shutdown import set_shutdown
                set_shutdown()
            except Exception:
                pass  # Don't fail if shutdown module isn't available
            
            # CRITICAL FIX: Set shutdown event when KeyboardInterrupt is caught
            # This ensures shutdown happens even if signal handler didn't execute
            self._shutdown_event.set()
            logger.debug("Shutdown event set from KeyboardInterrupt handler")
            
            # CRITICAL FIX: Cancel keep-alive task immediately to ensure quick shutdown
            # This prevents the task from continuing to run after KeyboardInterrupt
            if keep_alive is not None and not keep_alive.done():
                keep_alive.cancel()
                logger.debug("Keep-alive task cancelled from KeyboardInterrupt handler")
                # Wait for cancellation to complete with timeout
                try:
                    await asyncio.wait_for(keep_alive, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass  # Expected during cancellation
            
            # CRITICAL FIX: Cancel all remaining tasks to ensure clean shutdown
            # This prevents tasks from blocking shutdown
            try:
                current_task = asyncio.current_task()
                all_tasks = [
                    t for t in asyncio.all_tasks()
                    if t != current_task and not t.done()
                ]
                if all_tasks:
                    logger.debug("Cancelling %d remaining tasks...", len(all_tasks))
                    for task in all_tasks:
                        task.cancel()
                    # Wait for tasks to cancel with timeout
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*all_tasks, return_exceptions=True),
                            timeout=2.0
                        )
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        logger.debug("Some tasks did not cancel within timeout")
            except Exception as e:
                logger.debug("Error cancelling tasks: %s", e)
            
            # CRITICAL FIX: Call stop() directly in KeyboardInterrupt handler
            # This ensures proper shutdown even if asyncio.run() cancels the event loop
            # We do this here instead of relying on the finally block because
            # asyncio.run() may cancel tasks and close the loop before finally executes
            try:
                logger.info("Initiating shutdown from KeyboardInterrupt handler...")
                # Use wait_for with timeout to ensure shutdown completes
                # If the event loop is being cancelled, this may still fail, but we try
                try:
                    await asyncio.wait_for(self.stop(), timeout=10.0)
                    logger.info("Shutdown completed from KeyboardInterrupt handler")
                except (asyncio.TimeoutError, asyncio.CancelledError) as e:
                    # Timeout or cancellation - event loop may be closing
                    logger.warning(
                        "Shutdown %s during KeyboardInterrupt - forcing cleanup",
                        "timeout" if isinstance(e, asyncio.TimeoutError) else "cancelled"
                    )
                    # At least try to remove PID file
                    try:
                        self.daemon_manager.remove_pid()
                    except Exception:
                        pass
            except Exception as e:
                logger.exception("Error during shutdown from KeyboardInterrupt: %s", e)
                # At least try to remove PID file
                try:
                    self.daemon_manager.remove_pid()
                except Exception:
                    pass
        except Exception as e:
            from ccbt.daemon.debug_utils import (
                debug_log_event_loop_state,
                debug_log_exception,
                debug_log_stack,
            )

            debug_log_exception("Unexpected error in daemon main loop", e)
            debug_log_stack("Stack after unexpected error")
            debug_log_event_loop_state()
            logger.exception("Unexpected error in daemon main loop: %s", e)
            # CRITICAL: Log the full exception context to help diagnose daemon crashes
            import traceback

            logger.critical(
                "Daemon main loop exited with exception. Full traceback:\n%s",
                traceback.format_exc(),
            )
            # Don't re-raise - try to shutdown gracefully
        finally:
            from ccbt.daemon.debug_utils import debug_log, debug_log_stack

            logger.info("Daemon main loop exiting, starting shutdown...")
            debug_log("Daemon main loop exiting, starting shutdown...")
            debug_log_stack("Stack in finally block before stop()")
            # CRITICAL FIX: Only call stop() if it hasn't been called already
            # (e.g., from KeyboardInterrupt handler)
            if not self._stopping:
                try:
                    await self.stop()
                    debug_log("Daemon stop() completed")
                except Exception as e:
                    logger.exception("Error in finally block stop(): %s", e)
                    debug_log("Error in finally block stop(): %s", e)
            else:
                logger.debug("Stop() already called, skipping in finally block")
                debug_log("Stop() already called, skipping in finally block")

    async def stop(self) -> None:
        """Stop daemon process with proper shutdown sequence."""
        # CRITICAL FIX: Make stop() idempotent to prevent double-calling
        if self._stopping:
            logger.debug("Stop() already in progress, skipping duplicate call")
            return
        
        self._stopping = True
        
        # CRITICAL FIX: Set global shutdown flag early to suppress verbose logging
        from ccbt.utils.shutdown import set_shutdown
        
        set_shutdown()
        logger.info("Stopping daemon...")

        # CRITICAL FIX: Verify daemon is actually running before stopping
        # This prevents issues with stale PID files
        try:
            pid = self.daemon_manager.get_pid()
            if pid is not None:
                import os

                try:
                    os.kill(pid, 0)  # Signal 0 just checks if process exists
                    logger.debug("Verified daemon process %d is running", pid)
                except (OSError, ProcessLookupError):
                    logger.warning(
                        "Daemon PID file exists but process %d is not running. "
                        "Removing stale PID file.",
                        pid,
                    )
                    self.daemon_manager.remove_pid()
                    return
        except Exception as e:
            logger.debug("Error verifying daemon process: %s", e)

        # Cancel auto-save task
        if self._auto_save_task:
            self._auto_save_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._auto_save_task

        # Shutdown metrics collection
        try:
            await shutdown_metrics()
        except Exception:
            logger.exception("Error shutting down metrics collection")

        # Save state (before stopping services)
        if self.session_manager:
            try:
                await self.state_manager.save_state(self.session_manager)
                logger.info("State saved")
            except Exception:
                logger.exception("Error saving state during shutdown")

        # Stop IPC server (releases IPC port)
        if self.ipc_server:
            try:
                await self.ipc_server.stop()
                logger.debug("IPC server stopped (port released)")
            except Exception:
                logger.exception("Error stopping IPC server")

        # Stop session manager (releases all network ports via TCP server, UDP tracker, DHT, NAT)
        if self.session_manager:
            try:
                # CRITICAL FIX: Add delay before stopping session manager on Windows
                # This prevents socket buffer exhaustion (WinError 10055) when closing many sockets at once
                import sys
                if sys.platform == "win32":
                    await asyncio.sleep(0.1)  # Small delay to allow socket cleanup
                await self.session_manager.stop()
                logger.debug("Session manager stopped (all ports released)")
            except OSError as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully during shutdown
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    logger.warning(
                        "WinError 10055 (socket buffer exhaustion) during session manager shutdown. "
                        "This is a transient Windows issue. Continuing shutdown..."
                    )
                else:
                    logger.exception("OSError stopping session manager: %s", e)
            except Exception:
                logger.exception("Error stopping session manager")

        # Remove PID file and release lock (must be last)
        self.daemon_manager.remove_pid()

        logger.info("Daemon stopped (all ports released, PID file removed)")


async def main() -> int:
    """Run the main daemon process."""
    import argparse

    parser = argparse.ArgumentParser(description="ccBitTorrent Daemon")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (for debugging)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v: verbose, -vv: debug, -vvv: trace)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set log level directly",
    )

    args = parser.parse_args()

    # CRITICAL DEBUG: Enable debug logging FIRST before anything else
    # This captures all events including early initialization failures
    from ccbt.daemon.debug_utils import debug_log, debug_log_stack, enable_debug_logging

    enable_debug_logging()
    debug_log("Daemon process starting - main() called")
    debug_log_stack("Initial stack trace")

    # Setup logging FIRST before any other operations
    # This ensures we can log errors during initialization
    try:
        debug_log("Initializing configuration...")
        config_manager = init_config(args.config)
        debug_log("Configuration initialized, setting up logging...")
        
        # CRITICAL FIX: Apply verbosity/log-level overrides from CLI arguments
        # This ensures daemon respects verbosity flags just like CLI commands
        if args.log_level:
            from ccbt.models import LogLevel
            config_manager.config.observability.log_level = LogLevel(args.log_level)
        elif args.verbose > 0:
            from ccbt.models import LogLevel
            from ccbt.cli.verbosity import VerbosityManager
            
            verbosity_manager = VerbosityManager.from_count(args.verbose)
            if verbosity_manager.is_debug():
                config_manager.config.observability.log_level = LogLevel.DEBUG
            elif verbosity_manager.is_verbose():
                config_manager.config.observability.log_level = LogLevel.INFO
        
        setup_logging(config_manager.config.observability)
        # Get logger after setup_logging
        from ccbt.utils.logging_config import get_logger

        logger = get_logger(__name__)
        logger.info("Logging initialized")
        debug_log("Logging initialized successfully")
    except Exception as e:
        # If logging setup fails, we can't log, so print to stderr
        debug_log("CRITICAL: Failed to setup logging: %s", e)
        # Use sys.stderr.write for critical errors when logging unavailable
        sys.stderr.write(f"CRITICAL: Failed to setup logging: {e}\n")
        sys.stderr.flush()
        # Try to continue anyway with default logging
        import logging

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.warning("Using fallback logging configuration")

    # CRITICAL FIX: Set up event loop exception handler to catch unhandled exceptions
    # in background tasks. This prevents the daemon from crashing when background tasks
    # raise unhandled exceptions (e.g., from session.start() creating tasks).
    # The handler is set up here after the loop is created by asyncio.run()
    def exception_handler(
        loop: asyncio.AbstractEventLoop, context: dict[str, Any]
    ) -> None:
        """Handle unhandled exceptions in background tasks."""
        exception = context.get("exception")
        message = context.get("message", "Unhandled exception in background task")
        task = context.get("task")
        source_traceback = context.get("source_traceback")

        # CRITICAL: Check if this is a SystemExit or KeyboardInterrupt - these should exit
        # However, KeyboardInterrupt should NOT be caught here - it should propagate to the main coroutine
        # The exception handler is only for background tasks, not the main coroutine
        if isinstance(exception, SystemExit):
            # SystemExit should propagate
            return
        # NOTE: KeyboardInterrupt should propagate naturally from the main coroutine
        # We don't catch it here because it needs to reach the KeyboardInterrupt handler in run()

        # CRITICAL FIX: Suppress CancelledError logging during shutdown
        # CancelledError is expected when tasks are cancelled during shutdown
        if isinstance(exception, asyncio.CancelledError):
            from ccbt.utils.shutdown import is_shutting_down
            
            if is_shutting_down():
                # During shutdown, CancelledError is expected - don't log it
                return
            # If not shutting down, CancelledError might indicate a problem - log it
            logger.debug(
                "Task cancelled (not during shutdown): %s (task=%s)",
                message,
                task,
            )
            return

        # CRITICAL FIX: Handle Windows socket buffer exhaustion (WinError 10055) gracefully
        # This can occur:
        # 1. In the event loop selector during shutdown when many sockets are closed
        # 2. During normal operation when too many sockets are registered simultaneously
        #    (the selector can't monitor all sockets due to Windows buffer limits)
        if isinstance(exception, OSError):
            error_code = getattr(exception, "winerror", None) or getattr(exception, "errno", None)
            if error_code == 10055:
                from ccbt.utils.shutdown import is_shutting_down
                
                if is_shutting_down():
                    # During shutdown, this is expected - log at DEBUG level
                    logger.debug(
                        "WinError 10055 (socket buffer exhaustion) in event loop selector during shutdown. "
                        "This is a transient Windows issue and can be safely ignored."
                    )
                else:
                    # CRITICAL: This happened during normal operation - log as WARNING
                    # This indicates too many concurrent connections and may cause daemon instability
                    logger.warning(
                        "WinError 10055 (socket buffer exhaustion) in event loop selector during normal operation. "
                        "The selector cannot monitor all sockets due to Windows buffer limits. "
                        "This may indicate too many concurrent connections. "
                        "Consider reducing connection limits. The daemon will attempt to continue."
                    )
                    # Don't return - let it be logged but don't crash the daemon
                    # The error will propagate but we've logged it
                return  # Don't log as error - we've handled it above

        # CRITICAL FIX: Suppress verbose logging during shutdown
        from ccbt.utils.shutdown import is_shutting_down
        
        if is_shutting_down():
            # During shutdown, only log critical errors, not routine exceptions
            # This prevents log flooding when tasks are being cancelled
            # CRITICAL FIX: Suppress PeerConnectionError during shutdown (connection tasks being cancelled)
            if isinstance(exception, Exception):
                # Check if this is a connection-related error that's expected during shutdown
                try:
                    from ccbt.utils.exceptions import PeerConnectionError
                    connection_errors = (OSError, ConnectionError, PeerConnectionError, asyncio.CancelledError)
                except ImportError:
                    # If PeerConnectionError not available, use base exceptions
                    connection_errors = (OSError, ConnectionError, asyncio.CancelledError)
                
                if isinstance(exception, connection_errors):
                    # Network/connection errors during shutdown are expected - don't log them
                    return
                # Log non-network errors at debug level during shutdown
                logger.debug(
                    "Exception during shutdown (suppressed verbose logging): %s (task=%s)",
                    type(exception).__name__,
                    task,
                )
                return
            # Other exceptions during shutdown - don't log them
            return

        # Log the exception with full context
        if exception:
            logger.exception(
                "Unhandled exception in background task: %s (task=%s, source_traceback=%s)",
                message,
                task,
                source_traceback,
                exc_info=exception,
            )
        else:
            logger.error(
                "Unhandled exception in background task: %s (task=%s, source_traceback=%s)",
                message,
                task,
                source_traceback,
            )

        # CRITICAL: Don't crash the daemon - just log and continue
        # The error middleware in IPC server will handle request-level errors
        # This handler ensures background tasks don't silently fail and crash the daemon
        # IMPORTANT: We do NOT re-raise the exception - we want the daemon to keep running

    # Set the exception handler on the current event loop
    # This is safe here because asyncio.run() has already created the loop
    # CRITICAL: Set this BEFORE creating any tasks to ensure all exceptions are caught
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(exception_handler)
        logger.debug("Event loop exception handler installed")
    except RuntimeError as e:
        # If we can't get the running loop, log and continue
        # This should not happen with asyncio.run(), but handle gracefully
        logger.warning("Could not set event loop exception handler: %s", e)

    # Create and run daemon
    daemon = None
    try:
        debug_log("Creating DaemonMain instance...")
        daemon = DaemonMain(
            config_file=args.config,
            foreground=args.foreground,
        )
        logger.info("DaemonMain instance created")
        debug_log("DaemonMain instance created successfully")
        debug_log_stack("Stack after DaemonMain creation")

        # CRITICAL FIX: Run daemon in a way that ensures the event loop stays alive
        # Wrap in try-except to catch any unexpected exits and log them
        try:
            debug_log("Starting daemon.run()...")
            debug_log_stack("Stack before daemon.run()")
            await daemon.run()
            logger.info("Daemon main loop exited normally")
            debug_log("Daemon main loop exited normally")
            debug_log_stack("Stack after normal exit")
            return 0
        except asyncio.CancelledError:
            # This is expected during shutdown
            logger.info("Daemon main loop was cancelled (shutdown)")
            debug_log("Daemon main loop was cancelled (shutdown)")
            debug_log_stack("Stack after cancellation")
            return 0
        except Exception as e:
            # CRITICAL: Log any unexpected exceptions that cause the daemon to exit
            from ccbt.daemon.debug_utils import (
                debug_log_event_loop_state,
                debug_log_exception,
            )

            debug_log_exception("Daemon run() exited with unexpected exception", e)
            debug_log_event_loop_state()
            debug_log_stack("Stack after exception in daemon.run()")
            logger.critical(
                "Daemon run() exited with unexpected exception: %s. "
                "This should not happen - the daemon should only exit on shutdown signal.",
                e,
                exc_info=True,
            )
            # Try to cleanup
            if daemon is not None:
                try:
                    debug_log("Attempting daemon cleanup...")
                    await daemon.stop()
                    debug_log("Daemon cleanup completed")
                except Exception as cleanup_error:
                    debug_log_exception("Error during daemon cleanup", cleanup_error)
                    logger.exception("Error during daemon cleanup: %s", cleanup_error)
            return 1
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
        return 0
    except SystemExit as e:
        logger.info("Daemon received system exit signal: %s", e)
        return e.code if isinstance(e.code, int) else 0
    except Exception as e:
        logger.exception("Fatal error in daemon: %s", e)
        # CRITICAL FIX: Ensure PID file is removed on fatal error
        # This is a safety net in case start() didn't clean up
        if daemon is not None:
            try:
                daemon.daemon_manager.remove_pid()
                logger.info("Removed PID file after fatal error")
            except Exception as cleanup_error:
                logger.exception(
                    "Error removing PID file during cleanup: %s", cleanup_error
                )
        return 1


if __name__ == "__main__":
    # CRITICAL FIX: Suppress ProactorEventLoop _ssock AttributeError on Windows
    # This is a known Python bug where ProactorEventLoop.__del__ tries to access
    # _ssock attribute that doesn't exist in some cases during cleanup
    import sys

    if sys.platform == "win32":
        # Suppress the specific AttributeError during ProactorEventLoop cleanup
        # This happens when the event loop is garbage collected
        original_excepthook = sys.excepthook

        def filtered_excepthook(exc_type, exc_value, exc_traceback):
            # Filter out the known ProactorEventLoop _ssock AttributeError
            if (
                exc_type is AttributeError
                and "_ssock" in str(exc_value)
                and exc_traceback is not None
            ):
                # Check if this is the ProactorEventLoop cleanup bug
                import traceback

                tb_str = "".join(traceback.format_tb(exc_traceback))
                if "ProactorEventLoop" in tb_str and "__del__" in tb_str:
                    # This is the known bug - suppress it
                    return
            # For all other exceptions, use the original handler
            original_excepthook(exc_type, exc_value, exc_traceback)

        sys.excepthook = filtered_excepthook

    # CRITICAL FIX: Use SelectorEventLoop instead of ProactorEventLoop on Windows
    # ProactorEventLoop has known bugs with UDP sockets (WinError 10022)
    # SelectorEventLoop uses select() which properly supports UDP on Windows
    # Note: Policy should already be set in ccbt/__init__.py, but ensure it here as well
    if sys.platform == "win32":
        current_policy = asyncio.get_event_loop_policy()
        # If policy is wrapped by _SafeEventLoopPolicy, check the base
        if hasattr(current_policy, "_base"):
            base_policy = current_policy._base
            was_wrapped = True
        else:
            base_policy = current_policy
            was_wrapped = False

        # Only set if we're still using ProactorEventLoopPolicy
        if isinstance(base_policy, asyncio.WindowsProactorEventLoopPolicy):
            selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
            # Re-wrap with _SafeEventLoopPolicy if it was wrapped before
            if was_wrapped:
                # Import _SafeEventLoopPolicy from ccbt
                import ccbt
                if hasattr(ccbt, "_SafeEventLoopPolicy"):
                    safe_policy = ccbt._SafeEventLoopPolicy(selector_policy)  # type: ignore[attr-defined]
                    asyncio.set_event_loop_policy(safe_policy)
                else:
                    asyncio.set_event_loop_policy(selector_policy)
            else:
                asyncio.set_event_loop_policy(selector_policy)

    # CRITICAL FIX: Add better error handling to prevent premature exit
    # This ensures the daemon stays alive and handles errors gracefully
    # Note: Event loop exception handler is set inside main() after the loop is created
    try:
        return_code = asyncio.run(main())
        sys.exit(return_code)
    except KeyboardInterrupt:
        # User interrupted - exit cleanly
        sys.exit(0)
    except OSError as e:
        # CRITICAL FIX: Handle Windows socket buffer exhaustion (WinError 10055)
        # This can occur:
        # 1. During shutdown when many sockets are closed at once
        # 2. During normal operation when the event loop selector hits buffer limits
        #    (happens when too many sockets are registered simultaneously)
        # It's a transient Windows issue that indicates we need to reduce connection limits
        error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
        if error_code == 10055 or (hasattr(e, "errno") and e.errno == 10055):
            # WinError 10055: An operation on a socket could not be performed because
            # the system lacked sufficient buffer space or because a queue was full
            # This occurs when the event loop selector can't monitor all registered sockets
            try:
                import logging
                logger = logging.getLogger(__name__)
                from ccbt.utils.shutdown import is_shutting_down
                
                if is_shutting_down():
                    logger.warning(
                        "WinError 10055 (socket buffer exhaustion) during shutdown. "
                        "This is a transient Windows issue and doesn't affect functionality. "
                        "Shutdown completed successfully."
                    )
                else:
                    # CRITICAL: This happened during normal operation, not shutdown
                    # This indicates too many concurrent connections - log as error
                    logger.error(
                        "WinError 10055 (socket buffer exhaustion) during normal operation. "
                        "The event loop selector cannot monitor all sockets due to buffer limits. "
                        "This may indicate too many concurrent connections. "
                        "Consider reducing connection limits in configuration. "
                        "Daemon will exit to prevent further issues."
                    )
            except Exception:
                # If logging fails, write to stderr directly
                sys.stderr.write(
                    "Error: WinError 10055 (socket buffer exhaustion). "
                    "Too many concurrent connections. Daemon exiting.\n"
                )
                sys.stderr.flush()
            # Exit cleanly - but with non-zero code if not during shutdown
            # This allows monitoring systems to detect the issue
            try:
                from ccbt.utils.shutdown import is_shutting_down
                sys.exit(0 if is_shutting_down() else 1)
            except Exception:
                sys.exit(1)
        else:
            # Other OSError - log and exit with error
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Fatal OSError in daemon main: %s", e)
            except Exception:
                sys.stderr.write(f"Fatal OSError in daemon main: {e}\n")
                sys.stderr.flush()
            sys.exit(1)
    except Exception as e:
        # Log fatal error if possible
        try:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Fatal error in daemon main: %s", e)
        except Exception:
            # If logging fails, write to stderr directly
            sys.stderr.write(f"Fatal error in daemon main: {e}\n")
            sys.stderr.flush()
        sys.exit(1)
