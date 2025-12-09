"""Enhanced CLI for ccBitTorrent.

from __future__ import annotations

Provides rich CLI interface with:
- Interactive TUI
- Progress bars
- Live statistics
- Configuration management
- Debug tools
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.advanced_commands import performance as performance_cmd
from ccbt.cli.advanced_commands import recover as recover_cmd
from ccbt.cli.advanced_commands import security as security_cmd
from ccbt.cli.advanced_commands import test as test_cmd
from ccbt.cli.config_commands import config as config_group
from ccbt.cli.config_commands_extended import config_extended
from ccbt.cli.daemon_commands import daemon as daemon_group
from ccbt.cli.downloads import start_basic_magnet_download
from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.monitoring_commands import alerts as alerts_cmd
from ccbt.cli.monitoring_commands import dashboard as dashboard_cmd
from ccbt.cli.monitoring_commands import metrics as metrics_cmd
from ccbt.cli.progress import ProgressManager
from ccbt.cli.torrent_config_commands import torrent as torrent_group
from ccbt.cli.verbosity import VerbosityManager
from ccbt.config.config import Config, ConfigManager, get_config, init_config
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
from ccbt.i18n import _
from ccbt.i18n.manager import TranslationManager
from ccbt.monitoring import (
    AlertManager,
    DashboardManager,
    MetricsCollector,
    TracingManager,
)
from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)

# Exception message templates
def _daemon_not_responding_msg(max_total_wait: float) -> str:
    """Generate daemon not responding error message."""
    return (
        f"Daemon PID file exists but daemon is not responding after {max_total_wait:.1f}s.\n"
        "Possible causes:\n"
        "  - Daemon is still starting up (wait a few seconds and try again)\n"
        "  - Daemon crashed (check logs or run 'btbt daemon status')\n"
        "  - IPC server is not accessible (check firewall/network settings)\n\n"
        "To resolve:\n"
        "  1. Run 'btbt daemon status' to check if daemon is actually running\n"
        "  2. If daemon is not running, remove stale PID file: 'btbt daemon exit --force'\n"
        "  3. If you want to run locally instead, stop the daemon: 'btbt daemon exit'"
    )


def _daemon_timeout_msg(elapsed: float) -> str:
    """Generate daemon timeout error message."""
    return (
        f"Daemon PID file exists but daemon is not responding (timeout after {elapsed:.1f}s).\n"
        "The daemon may be starting up or may have crashed.\n\n"
        "To resolve:\n"
        "  1. Run 'btbt daemon status' to check daemon state\n"
        "  2. Check daemon logs for errors\n"
        "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
        "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
    )


# Exception message constants
DAEMON_API_KEY_MISSING_MSG = (
    "Daemon PID file exists but API key is missing from config. "
    "Run 'btbt daemon status' to check daemon state, or restart the daemon."
)

DAEMON_NOT_RESPONDING_MSG = (
    "Daemon PID file exists but daemon is not responding. "
    "The daemon may be starting up or may have crashed.\n\n"
    "To resolve:\n"
    "  1. Run 'btbt daemon status' to check daemon state\n"
    "  2. Wait a few seconds if daemon is still starting up\n"
    "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
    "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
)

DAEMON_TIMEOUT_MSG = (
    "Daemon PID file exists but daemon is not responding (timeout). "
    "The daemon may be starting up or may have crashed.\n\n"
    "To resolve:\n"
    "  1. Run 'btbt daemon status' to check daemon state\n"
    "  2. Wait a few seconds if daemon is still starting up\n"
    "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
    "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
)

DAEMON_EXECUTOR_NOT_AVAILABLE_MSG = (
    "Daemon PID file exists but executor is not available. "
    "This indicates a serious initialization error."
)

DAEMON_CRITICAL_ERROR_MSG = (
    "CRITICAL ERROR: Daemon PID file exists but code path reached local session creation. "
    "This indicates a bug in daemon detection logic.\n\n"
    "Cannot create local session as it would cause port conflicts.\n\n"
    "To resolve:\n"
    "  1. Stop the daemon: 'btbt daemon exit'\n"
    "  2. Report this as a bug if daemon is not running"
)

DAEMON_WEB_INTERFACE_CONFLICT_MSG = (
    "Daemon is running. Cannot start local web interface while daemon is active.\n"
    "This would cause port conflicts and resource conflicts.\n\n"
    "To resolve:\n"
    "  1. Stop the daemon first: 'btbt daemon exit'\n"
    "  2. Or use the daemon's web interface if available\n"
    "  3. Or use daemon commands instead of local commands"
)

DAEMON_DEBUG_MODE_CONFLICT_MSG = (
    "Daemon is running. Cannot start local debug mode while daemon is active.\n"
    "This would cause port conflicts and resource conflicts.\n\n"
    "To resolve:\n"
    "  1. Stop the daemon first: 'btbt daemon exit'\n"
    "  2. Or use daemon commands for debugging\n"
    "  3. Or check daemon logs for debugging information"
)

DAEMON_RESUME_CONFLICT_MSG = (
    "Daemon is running. Cannot resume from checkpoint using local session while daemon is active.\n"
    "This would cause port conflicts and resource conflicts.\n\n"
    "To resolve:\n"
    "  1. Stop the daemon first: 'btbt daemon exit'\n"
    "  2. Or add the torrent to the daemon and let it resume automatically\n"
    "  3. The daemon will automatically resume from checkpoints when adding torrents"
)


def _daemon_connection_error_msg(error: Exception) -> str:
    """Generate daemon connection error message."""
    return (
        f"Daemon PID file exists but cannot connect to daemon (error: {error}).\n"
        "The daemon may be starting up or may have crashed.\n\n"
        "To resolve:\n"
        "  1. Run 'btbt daemon status' to check daemon state\n"
        "  2. Check if IPC server is running on the configured port\n"
        "  3. Verify API key in config matches daemon's API key\n"
        "  4. If daemon crashed, restart it: 'btbt daemon start'\n"
        "  5. If you want to run locally, stop the daemon: 'btbt daemon exit'"
    )


def _daemon_not_accessible_msg(elapsed: float) -> str:
    """Generate daemon not accessible error message."""
    return (
        f"Daemon PID file exists but daemon is not accessible after {elapsed:.1f}s.\n"
        "The daemon may be starting up or may have crashed.\n\n"
        "To resolve:\n"
        "  1. Run 'btbt daemon status' to check daemon state\n"
        "  2. Check daemon logs for startup errors\n"
        "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
        "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
    )


def _daemon_error_connecting_msg(error: Exception) -> str:
    """Generate daemon error connecting message."""
    return (
        f"Daemon PID file exists but error occurred while connecting: {error}.\n"
        "The daemon may be starting up or may have crashed.\n\n"
        "To resolve:\n"
        "  1. Run 'btbt daemon status' to check daemon state\n"
        "  2. Check daemon logs for connection errors\n"
        "  3. Verify IPC server is accessible on the configured port\n"
        "  4. If daemon crashed, restart it: 'btbt daemon start'\n"
        "  5. If you want to run locally, stop the daemon: 'btbt daemon exit'"
    )


def _unknown_operation_msg(operation: str) -> str:
    """Generate unknown operation error message."""
    return (
        f"Unknown operation '{operation}' requested but daemon PID file exists. "
        "This should not happen - please report this as a bug."
    )


def _error_executing_operation_msg(operation: str, error: Exception) -> str:
    """Generate error executing operation message."""
    return f"Error executing {operation} on daemon: {error}"


def _raise_cli_error(message: str) -> None:
    """Raise a ClickException with the given message."""
    raise click.ClickException(message) from None


def _get_daemon_ipc_port(cfg: Any) -> int:
    """Get daemon IPC port from config or daemon config file.
    
    Args:
        cfg: Config object from get_config()
        
    Returns:
        IPC port number (default: 8080)
    
    CRITICAL: This must match the daemon's actual IPC port to prevent connection failures.
    The daemon writes its IPC port to ~/.ccbt/daemon/config.json when it starts.

    """
    # CRITICAL FIX: Always try to read from daemon config file FIRST (most reliable source)
    # The daemon writes its actual IPC port here when it starts, so this is authoritative
    # This MUST be checked before main config to ensure we use the daemon's actual port
    import json

    # CRITICAL FIX: Use consistent path resolution helper
    from ccbt.daemon.daemon_manager import _get_daemon_home_dir
    home_dir = _get_daemon_home_dir()
    daemon_config_file = home_dir / ".ccbt" / "daemon" / "config.json"
    logger.debug(_("_get_daemon_ipc_port: Checking config_file=%s (home_dir=%s)"), daemon_config_file, home_dir)
    if daemon_config_file.exists():
        try:
            with open(daemon_config_file, encoding="utf-8") as f:
                daemon_config = json.load(f)
                ipc_port = daemon_config.get("ipc_port")
                if ipc_port:
                    logger.debug(_("Read IPC port %d from daemon config file (authoritative source)"), ipc_port)
                    return ipc_port
                logger.debug(_("Daemon config file exists but ipc_port not found, trying main config"))
        except Exception as e:
            logger.debug(_("Could not read daemon config file: %s"), e)

    # Fallback to main config (if daemon config file doesn't exist or doesn't have ipc_port)
    if cfg.daemon and cfg.daemon.ipc_port:
        logger.debug(_("Using IPC port %d from main config"), cfg.daemon.ipc_port)
        return cfg.daemon.ipc_port

    # Default fallback (should rarely be used if daemon is running)
    logger.debug(_("Using default IPC port 8080 (daemon config file may not exist)"))
    return 8080


async def _route_to_daemon_if_running(
    operation: str,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Route command to daemon if running.

    Args:
        operation: Operation name (e.g., 'add_torrent', 'add_magnet')
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        True if routed to daemon, False if daemon not running

    """
    # CRITICAL FIX: Check PID file existence directly before attempting os.kill()
    # This avoids Windows-specific os.kill() errors that can cause false negatives
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()

    # Try to check if daemon is running, but don't fail if os.kill() has issues
    # On Windows, os.kill() with signal 0 is unreliable and may raise exceptions
    # even when the process exists, so we always attempt IPC connection if PID file exists
    daemon_running = False
    if pid_file_exists:
        try:
            daemon_running = daemon_manager.is_running()
        except Exception as e:
            # On Windows, is_running() might raise exceptions due to os.kill() issues
            # If PID file exists, we'll still attempt IPC connection
            logger.debug(
                _("Error checking if daemon is running (Windows-specific issue?): %s - "
                "PID file exists, will attempt IPC connection"),
                e,
            )
            # Don't set daemon_running = False here - we'll check via IPC instead
            # The IPC connection check is the authoritative way to verify daemon is running

    # CRITICAL FIX: If PID file exists, we MUST attempt IPC connection
    # Don't skip IPC check just because is_running() failed on Windows
    # The IPC connection is the definitive test of whether the daemon is accessible
    if not pid_file_exists and not daemon_running:
        # No PID file and not running - daemon is definitely not running
        logger.debug(_("No daemon PID file found - daemon is not running"))
        return False

    # Get API key from config
    cfg = get_config()

    if not cfg.daemon or not cfg.daemon.api_key:
        if pid_file_exists or daemon_running:
            logger.warning(
                _("Daemon PID file exists but API key not found in config. "
                "Cannot route to daemon. Please check daemon configuration.")
            )
            # Don't return False here - we want to raise an error in the caller
            # to prevent local session creation
            api_key_missing_msg = (
                "Daemon appears to be running but API key is missing from config. "
                "Run 'btbt daemon status' to check daemon state, or restart the daemon."
            )
            raise click.ClickException(api_key_missing_msg)
        logger.debug(_("No daemon config or API key found - will create local session"))
        return False

    client: IPCClient | None = None
    try:
        # CRITICAL FIX: Create client and verify connection before attempting operation
        # Explicitly use host/port from config to ensure consistency with daemon
        # Note: If server binds to 0.0.0.0, client can still connect via 127.0.0.1
        # So we always use 127.0.0.1 for client connections (works with both 0.0.0.0 and 127.0.0.1 server bindings)
        # For client connection, always use 127.0.0.1 (works with server binding to 0.0.0.0 or 127.0.0.1)
        client_host = "127.0.0.1"
        ipc_port = _get_daemon_ipc_port(cfg)
        base_url = f"http://{client_host}:{ipc_port}"
        client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)

        # CRITICAL FIX: Verify daemon is actually accessible before routing
        # Increased timeout to 30 seconds to account for slow daemon startup (NAT discovery, DHT bootstrap, etc.)
        # Initial wait to give daemon time to start IPC server after PID file is written
        initial_wait = 1.0
        await asyncio.sleep(initial_wait)

        max_retries = 10  # Increased from 6 to 10 for better reliability
        retry_delay = 0.5
        max_total_wait = (
            30.0  # Increased from 15.0 to 30.0 seconds to account for slow startup
        )
        start_time = asyncio.get_event_loop().time()
        is_accessible = False

        for attempt in range(max_retries):
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= max_total_wait:
                logger.debug(
                    _("Exceeded maximum wait time (%.1fs) for daemon readiness"),
                    max_total_wait,
                )
                # If PID file exists, this is an error condition
                if pid_file_exists:
                    error_msg = _daemon_not_responding_msg(max_total_wait)
                    raise click.ClickException(error_msg)
                return False

            try:
                # Increase timeout to 5.0s to account for slow startup
                is_accessible = await asyncio.wait_for(
                    client.is_daemon_running(), timeout=5.0
                )
                if is_accessible:
                    logger.debug(
                        _("Daemon is accessible and ready (attempt %d/%d, took %.1fs)"),
                        attempt + 1,
                        max_retries,
                        elapsed,
                    )
                    break
                if attempt < max_retries - 1:
                    logger.debug(
                        _("Daemon is marked as running but not accessible (attempt %d/%d, elapsed %.1fs), "
                        "retrying in %.1fs..."),
                        attempt + 1,
                        max_retries,
                        elapsed,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * 1.5, 2.0
                    )  # Exponential backoff, capped at 2s
            except asyncio.TimeoutError as err:
                if attempt < max_retries - 1:
                    logger.debug(
                        _("Timeout checking daemon accessibility (attempt %d/%d, elapsed %.1fs), "
                        "retrying in %.1fs..."),
                        attempt + 1,
                        max_retries,
                        elapsed,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * 1.5, 2.0
                    )  # Exponential backoff, capped at 2s
                else:
                    logger.debug(
                        _("Timeout checking daemon accessibility after %d attempts (elapsed %.1fs)"),
                        max_retries,
                        elapsed,
                    )
                    # If PID file exists, this is an error condition
                    if pid_file_exists:
                        error_msg = _daemon_timeout_msg(elapsed)
                        raise click.ClickException(error_msg) from err
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(
                        _("Error checking daemon accessibility (attempt %d/%d, elapsed %.1fs): %s, "
                        "retrying in %.1fs..."),
                        attempt + 1,
                        max_retries,
                        elapsed,
                        e,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * 1.5, 2.0
                    )  # Exponential backoff, capped at 2s
                else:
                    logger.debug(
                        _("Error checking daemon accessibility after %d attempts (elapsed %.1fs): %s"),
                        max_retries,
                        elapsed,
                        e,
                    )
                    # If PID file exists, this is an error condition
                    if pid_file_exists:
                        error_msg = _daemon_connection_error_msg(e)
                        raise click.ClickException(error_msg) from e
                    return False

        if not is_accessible:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.debug(
                _("Daemon is marked as running but not accessible after %d attempts (elapsed %.1fs)"),
                max_retries,
                elapsed,
            )
            # If PID file exists, this is an error condition
            if pid_file_exists:
                error_msg = _daemon_not_accessible_msg(elapsed)
                raise click.ClickException(error_msg)
            return False

        # CRITICAL FIX: Perform the requested operation using executor
        # Wrap in try-except to ensure client is properly closed even on errors
        # CRITICAL FIX: Use ExecutorManager to ensure consistent executor creation
        from ccbt.executor.manager import ExecutorManager

        executor_manager = ExecutorManager.get_instance()
        executor = executor_manager.get_executor(ipc_client=client)
        console = Console()

        try:
            if operation == "add_torrent":
                path_or_magnet = args[0] if args else kwargs.get("path_or_magnet", "")
                if not path_or_magnet:
                    logger.warning(_("No torrent path or magnet provided"))
                    # If PID file exists, raise exception instead of returning False
                    if pid_file_exists:
                        no_torrent_msg = "No torrent path or magnet provided for add_torrent operation."
                        raise click.ClickException(no_torrent_msg)
                    return False

                result = await executor.execute(
                    "torrent.add",
                    path_or_magnet=path_or_magnet,
                    output_dir=kwargs.get("output_dir"),
                    resume=False,
                )

                if not result.success:
                    raise click.ClickException(
                        result.error or _("Failed to add torrent to daemon")
                    )

                info_hash = result.data["info_hash"]
                console.print(
                    _("[green]Torrent added to daemon: {hash}[/green]").format(
                        hash=info_hash
                    )
                )
                return True

            if operation == "add_magnet":
                magnet_uri = args[0] if args else kwargs.get("magnet_uri", "")
                if not magnet_uri:
                    logger.warning(_("No magnet URI provided"))
                    # If PID file exists, raise exception instead of returning False
                    if pid_file_exists:
                        no_magnet_msg = _("No magnet URI provided for add_magnet operation.")
                        raise click.ClickException(no_magnet_msg)
                    return False

                result = await executor.execute(
                    "torrent.add",
                    path_or_magnet=magnet_uri,
                    output_dir=kwargs.get("output_dir"),
                    resume=False,
                )

                if not result.success:
                    raise click.ClickException(
                        result.error or "Failed to add magnet to daemon"
                    )

                info_hash = result.data["info_hash"]
                console.print(
                    _("[green]Magnet added to daemon: {hash}[/green]").format(
                        hash=info_hash
                    )
                )
                return True

            if operation == "get_status":
                status = await client.get_status()
                console.print(
                    _("[green]Daemon status: {status}[/green]").format(
                        status=status.status
                    )
                )
                console.print(_("Torrents: {count}").format(count=status.num_torrents))
                console.print(_("Uptime: {uptime:.1f}s").format(uptime=status.uptime))
                return True
            logger.warning(_("Unknown operation: %s"), operation)
            # CRITICAL: If PID file exists, we should not return False
            # This indicates a programming error
            if pid_file_exists:
                error_msg = _unknown_operation_msg(operation)
                raise click.ClickException(error_msg)
            return False
        except click.ClickException:
            # Re-raise ClickException (user-facing errors)
            raise
        except Exception as op_error:
            # Log the error and re-raise as ClickException for user visibility
            logger.exception(
                "Error executing operation '%s' on daemon",
                operation,
            )
            error_msg = _error_executing_operation_msg(operation, op_error)
            raise click.ClickException(error_msg) from op_error

    except click.ClickException:
        # Re-raise ClickException (these are user-facing errors about daemon state)
        raise
    except Exception as e:
        # CRITICAL FIX: Distinguish between connection errors and other errors
        error_type = type(e).__name__
        error_str = str(e)
        is_connection_error = (
            "Connection" in error_type
            or "Timeout" in error_type
            or "Connect" in error_type
            or isinstance(e, (ConnectionError, TimeoutError, asyncio.TimeoutError))
        )

        # Check for Windows-specific os.kill() errors
        is_windows_kill_error = (
            "kill" in error_str.lower()
            or "exception set" in error_str.lower()
            or "built-in function kill" in error_str.lower()
        )

        # If PID file exists, this is an error condition - don't silently fall back
        if pid_file_exists:
            logger.warning(_("Error routing to daemon (PID file exists): %s"), e)
            error_msg = _daemon_error_connecting_msg(e)
            raise click.ClickException(error_msg) from e

        if is_windows_kill_error:
            logger.debug(
                _("Windows-specific error checking daemon (os.kill() issue): %s - "
                "no PID file found, will create local session"),
                e,
            )
        elif is_connection_error:
            logger.debug(
                _("Could not connect to daemon (no PID file): %s - will create local session"),
                e,
            )
        else:
            logger.debug(
                _("Error routing to daemon (no PID file): %s - will create local session"),
                e,
            )

        return False
    finally:
        # CRITICAL FIX: Always close client to prevent resource leaks
        if client:
            try:
                await client.close()
            except Exception as e:
                logger.debug(_("Error closing IPC client: %s"), e)


async def _get_executor() -> tuple[Any | None, bool]:
    """Get command executor (daemon or local).

    Returns:
        Tuple of (executor, is_daemon)
        If daemon is running, returns (executor with daemon adapter, True)
        If daemon is not running, returns (None, False)
        Raises ClickException if daemon PID exists but cannot connect

    """
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()

    if not pid_file_exists:
        return (None, False)

    # Get API key from config
    cfg = get_config()

    if not cfg.daemon or not cfg.daemon.api_key:
        raise click.ClickException(DAEMON_API_KEY_MISSING_MSG)

    # Explicitly use host/port from config to ensure consistency with daemon
    # CRITICAL FIX: Always use 127.0.0.1 for client connections (works with server binding to 0.0.0.0 or 127.0.0.1)
    # Server binding to 0.0.0.0 listens on all interfaces, including 127.0.0.1
    # CRITICAL FIX: Use helper function to read IPC port from config or daemon config file
    ipc_port = _get_daemon_ipc_port(cfg)
    client_host = "127.0.0.1"  # Always use 127.0.0.1 for client connections
    base_url = f"http://{client_host}:{ipc_port}"
    logger.debug(_("Connecting to daemon at %s (PID file exists)"), base_url)
    client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)

    # Verify daemon is accessible with retry logic (similar to _route_to_daemon_if_running)
    # This accounts for slow daemon startup (NAT discovery, DHT bootstrap, etc.)
    initial_wait = 1.0
    await asyncio.sleep(initial_wait)

    max_retries = 10
    retry_delay = 0.5
    max_total_wait = 30.0
    start_time = asyncio.get_event_loop().time()
    is_accessible = False

    for attempt in range(max_retries):
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= max_total_wait:
            await client.close()
            error_msg = _daemon_not_responding_msg(max_total_wait)
            raise click.ClickException(error_msg)

        try:
            is_accessible = await asyncio.wait_for(
                client.is_daemon_running(),
                timeout=5.0,
            )
            if is_accessible:
                logger.debug(
                    _("Daemon is accessible and ready (attempt %d/%d, took %.1fs)"),
                    attempt + 1,
                    max_retries,
                    elapsed,
                )
                break
            if attempt < max_retries - 1:
                logger.debug(
                    _("Daemon is marked as running but not accessible (attempt %d/%d, elapsed %.1fs), "
                    "retrying in %.1fs..."),
                    attempt + 1,
                    max_retries,
                    elapsed,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(
                    retry_delay * 1.5, 2.0
                )  # Exponential backoff, capped at 2s
        except asyncio.TimeoutError as err:
            if attempt < max_retries - 1:
                logger.debug(
                    _("Daemon connection timeout (attempt %d/%d, elapsed %.1fs), retrying in %.1fs..."),
                    attempt + 1,
                    max_retries,
                    elapsed,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 2.0)
            else:
                await client.close()
                error_msg = _daemon_timeout_msg(elapsed)
                raise click.ClickException(error_msg) from err
        except Exception as e:
            if attempt < max_retries - 1:
                logger.debug(
                    _("Daemon connection error (attempt %d/%d, elapsed %.1fs): %s, retrying in %.1fs..."),
                    attempt + 1,
                    max_retries,
                    elapsed,
                    e,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 2.0)
            else:
                await client.close()
                error_msg = _daemon_connection_error_msg(e)
                raise click.ClickException(error_msg) from e

    if not is_accessible:
        await client.close()
        timeout_msg = (
            "Daemon PID file exists but daemon is not responding after all retries. "
            "The daemon may be starting up or may have crashed.\n\n"
            "To resolve:\n"
            "  1. Run 'btbt daemon status' to check daemon state\n"
            "  2. Wait a few seconds if daemon is still starting up\n"
            "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
            "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
        )
        raise click.ClickException(timeout_msg)

    # Daemon is accessible - create executor via ExecutorManager
    # CRITICAL FIX: Use ExecutorManager to ensure consistent executor creation
    # This prevents duplicate executors and ensures proper session reference management
    # ExecutorManager will create DaemonSessionAdapter internally when ipc_client is provided
    from ccbt.executor.manager import ExecutorManager

    executor_manager = ExecutorManager.get_instance()
    executor = executor_manager.get_executor(ipc_client=client)
    return (executor, True)


async def _check_daemon_and_get_client() -> tuple[bool, IPCClient | None]:
    """Check if daemon is running and return IPC client if available.

    Returns:
        Tuple of (daemon_running, ipc_client)
        If daemon is not running, returns (False, None)
        If daemon is running, returns (True, IPCClient instance)
        Raises ClickException if daemon PID exists but cannot connect

    """
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()

    if not pid_file_exists:
        return (False, None)

    # Get API key from config
    cfg = get_config()

    if not cfg.daemon or not cfg.daemon.api_key:
        raise click.ClickException(DAEMON_API_KEY_MISSING_MSG)

    # Explicitly use host/port from config to ensure consistency with daemon
    # CRITICAL FIX: Always use 127.0.0.1 for client connections (works with server binding to 0.0.0.0 or 127.0.0.1)
    # Server binding to 0.0.0.0 listens on all interfaces, including 127.0.0.1
    # CRITICAL FIX: Use helper function to read IPC port from config or daemon config file
    ipc_port = _get_daemon_ipc_port(cfg)
    client_host = "127.0.0.1"  # Always use 127.0.0.1 for client connections
    base_url = f"http://{client_host}:{ipc_port}"
    logger.debug(_("Connecting to daemon at %s (PID file exists)"), base_url)
    client = IPCClient(api_key=cfg.daemon.api_key, base_url=base_url)

    # Verify daemon is accessible
    try:
        is_accessible = await asyncio.wait_for(
            client.is_daemon_running(),
            timeout=5.0,
        )
        if not is_accessible:
            await client.close()
            raise click.ClickException(DAEMON_NOT_RESPONDING_MSG)
        return (True, client)
    except asyncio.TimeoutError as err:
        await client.close()
        raise click.ClickException(DAEMON_TIMEOUT_MSG) from err
    except Exception as e:
        await client.close()
        error_msg = (
            f"Daemon PID file exists but cannot connect to daemon: {e}.\n\n"
            "To resolve:\n"
            "  1. Run 'btbt daemon status' to check daemon state\n"
            "  2. Check if IPC server is running on the configured port\n"
            "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
            "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
        )
        raise click.ClickException(error_msg) from e


def _ensure_no_daemon_or_warn() -> bool:
    """Check for daemon and warn if running.

    Returns:
        True if daemon is not running (safe to create local session)
        False if daemon is running (should warn user)

    """
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()

    if pid_file_exists:
        console = Console()
        console.print(
            _(
                "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]"
            )
        )
        console.print(
            _(
                "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]"
            )
        )
        return False

    return True


def _get_config_from_context(ctx: click.Context) -> ConfigManager:
    """Get ConfigManager from CLI context.

    Args:
        ctx: Click context

    Returns:
        ConfigManager instance

    """
    if ctx and ctx.obj and "config" in ctx.obj:
        return ConfigManager(ctx.obj["config"])
    return init_config()


async def _ensure_local_session_safe(force_local: bool = False) -> AsyncSessionManager:
    """Create and start a local AsyncSessionManager safely.

    Args:
        force_local: If True, ensures local session is created even if daemon is running

    Returns:
        Started AsyncSessionManager instance

    """
    session = AsyncSessionManager(".")
    await session.start()
    return session


# Helper to apply CLI overrides to the runtime config
def _apply_cli_overrides(cfg_mgr: ConfigManager, options: dict[str, Any]) -> None:
    """Apply CLI overrides to configuration."""
    cfg = cfg_mgr.config

    _apply_network_overrides(cfg, options)
    _apply_discovery_overrides(cfg, options)
    _apply_strategy_overrides(cfg, options)
    _apply_disk_overrides(cfg, options)
    _apply_observability_overrides(cfg, options)
    _apply_limit_overrides(cfg, options)


def _apply_network_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply network-related CLI overrides."""
    if options.get("listen_port") is not None:
        cfg.network.listen_port = int(options["listen_port"])
    if options.get("max_peers") is not None:
        cfg.network.max_global_peers = int(options["max_peers"])
    if options.get("max_peers_per_torrent") is not None:
        cfg.network.max_peers_per_torrent = int(options["max_peers_per_torrent"])
    if options.get("pipeline_depth") is not None:
        cfg.network.pipeline_depth = int(options["pipeline_depth"])
    if options.get("block_size_kib") is not None:
        cfg.network.block_size_kib = int(options["block_size_kib"])
    if options.get("connection_timeout") is not None:
        cfg.network.connection_timeout = float(options["connection_timeout"])
    if options.get("global_down_kib") is not None:
        cfg.network.global_down_kib = int(options["global_down_kib"])
    if options.get("global_up_kib") is not None:
        cfg.network.global_up_kib = int(options["global_up_kib"])

    # Additional network toggles
    if options.get("enable_ipv6"):
        cfg.network.enable_ipv6 = True
    if options.get("disable_ipv6"):
        cfg.network.enable_ipv6 = False
    if options.get("enable_tcp"):
        cfg.network.enable_tcp = True
    if options.get("disable_tcp"):
        cfg.network.enable_tcp = False
    if options.get("enable_utp"):
        cfg.network.enable_utp = True
    if options.get("disable_utp"):
        cfg.network.enable_utp = False
    if options.get("enable_encryption"):
        cfg.network.enable_encryption = True
    if options.get("disable_encryption"):
        cfg.network.enable_encryption = False
    if options.get("tcp_nodelay"):
        cfg.network.tcp_nodelay = True
    if options.get("no_tcp_nodelay"):
        cfg.network.tcp_nodelay = False
    if options.get("socket_rcvbuf_kib") is not None:
        cfg.network.socket_rcvbuf_kib = int(options["socket_rcvbuf_kib"])
    if options.get("socket_sndbuf_kib") is not None:
        cfg.network.socket_sndbuf_kib = int(options["socket_sndbuf_kib"])
    if options.get("listen_interface") is not None:
        cfg.network.listen_interface = str(options["listen_interface"])  # type: ignore[arg-type]
    if options.get("peer_timeout") is not None:
        cfg.network.peer_timeout = float(options["peer_timeout"])  # type: ignore[attr-defined]
    if options.get("dht_timeout") is not None:
        cfg.network.dht_timeout = float(options["dht_timeout"])  # type: ignore[attr-defined]
    if options.get("min_block_size_kib") is not None:
        cfg.network.min_block_size_kib = int(options["min_block_size_kib"])  # type: ignore[attr-defined]
    if options.get("max_block_size_kib") is not None:
        cfg.network.max_block_size_kib = int(options["max_block_size_kib"])  # type: ignore[attr-defined]


def _apply_discovery_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply discovery-related CLI overrides."""
    if options.get("enable_dht"):
        cfg.discovery.enable_dht = True
    if options.get("disable_dht"):
        cfg.discovery.enable_dht = False
    if options.get("dht_port") is not None:
        cfg.discovery.dht_port = int(options["dht_port"])
    if options.get("enable_http_trackers"):
        cfg.discovery.enable_http_trackers = True
    if options.get("disable_http_trackers"):
        cfg.discovery.enable_http_trackers = False
    if options.get("enable_udp_trackers"):
        cfg.discovery.enable_udp_trackers = True
    if options.get("disable_udp_trackers"):
        cfg.discovery.enable_udp_trackers = False
    if options.get("tracker_announce_interval") is not None:
        cfg.discovery.tracker_announce_interval = float(
            options["tracker_announce_interval"],
        )  # type: ignore[attr-defined]
    if options.get("tracker_scrape_interval") is not None:
        cfg.discovery.tracker_scrape_interval = float(
            options["tracker_scrape_interval"],
        )  # type: ignore[attr-defined]
    if options.get("pex_interval") is not None:
        cfg.discovery.pex_interval = float(options["pex_interval"])  # type: ignore[attr-defined]


def _apply_strategy_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply strategy-related CLI overrides."""
    if options.get("piece_selection") is not None:
        cfg.strategy.piece_selection = options["piece_selection"]
    if options.get("endgame_threshold") is not None:
        cfg.strategy.endgame_threshold = float(options["endgame_threshold"])
    if options.get("endgame_duplicates") is not None:
        cfg.strategy.endgame_duplicates = int(options["endgame_duplicates"])  # type: ignore[attr-defined]
    if options.get("streaming_mode"):
        cfg.strategy.streaming_mode = True
    if options.get("first_piece_priority"):
        try:
            cfg.strategy.first_piece_priority = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(_("Failed to set first piece priority: %s"), e)
    if options.get("last_piece_priority"):
        try:
            cfg.strategy.last_piece_priority = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(_("Failed to set last piece priority: %s"), e)
    if options.get("optimistic_unchoke_interval") is not None:
        cfg.network.optimistic_unchoke_interval = float(
            options["optimistic_unchoke_interval"],
        )  # type: ignore[attr-defined]
    if options.get("unchoke_interval") is not None:
        cfg.network.unchoke_interval = float(options["unchoke_interval"])  # type: ignore[attr-defined]


def _apply_disk_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply disk-related CLI overrides."""
    if options.get("hash_workers") is not None:
        cfg.disk.hash_workers = int(options["hash_workers"])
    if options.get("disk_workers") is not None:
        cfg.disk.disk_workers = int(options["disk_workers"])
    if options.get("use_mmap"):
        cfg.disk.use_mmap = True
    if options.get("no_mmap"):
        cfg.disk.use_mmap = False
    if options.get("mmap_cache_mb") is not None:
        cfg.disk.mmap_cache_mb = int(options["mmap_cache_mb"])
    if options.get("write_batch_kib") is not None:
        cfg.disk.write_batch_kib = int(options["write_batch_kib"])
    if options.get("write_buffer_kib") is not None:
        cfg.disk.write_buffer_kib = int(options["write_buffer_kib"])
    if options.get("preallocate") is not None:
        cfg.disk.preallocate = options["preallocate"]
    if options.get("sparse_files"):
        cfg.disk.sparse_files = True
    if options.get("no_sparse_files"):
        cfg.disk.sparse_files = False
    if options.get("enable_io_uring"):
        try:
            cfg.disk.enable_io_uring = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(_("Failed to enable io_uring: %s"), e)
    if options.get("disable_io_uring"):
        try:
            cfg.disk.enable_io_uring = False  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(_("Failed to disable io_uring: %s"), e)
    if options.get("direct_io"):
        cfg.disk.direct_io = True
    if options.get("sync_writes"):
        cfg.disk.sync_writes = True


def _apply_observability_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply observability-related CLI overrides."""
    if options.get("log_level") is not None:
        cfg.observability.log_level = options["log_level"]
    if options.get("enable_metrics"):
        cfg.observability.enable_metrics = True
    if options.get("disable_metrics"):
        cfg.observability.enable_metrics = False
    if options.get("metrics_port") is not None:
        cfg.observability.metrics_port = int(options["metrics_port"])
    if options.get("metrics_interval") is not None:
        cfg.observability.metrics_interval = float(options["metrics_interval"])  # type: ignore[attr-defined]
    if options.get("structured_logging"):
        cfg.observability.structured_logging = True  # type: ignore[attr-defined]
    if options.get("log_correlation_id"):
        cfg.observability.log_correlation_id = True  # type: ignore[attr-defined]


def _apply_limit_overrides(cfg: Config, options: dict[str, Any]) -> None:
    """Apply limit-related CLI overrides."""
    if options.get("download_limit") is not None:
        cfg.network.global_down_kib = int(options["download_limit"])
    if options.get("upload_limit") is not None:
        cfg.network.global_up_kib = int(options["upload_limit"])


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help=_("Configuration file path"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=_("Increase verbosity (-v: verbose, -vv: debug, -vvv: trace)"),
)
@click.option("--debug", "-d", is_flag=True, help=_("Enable debug mode (deprecated, use -vv)"))
@click.pass_context
def cli(ctx, config, verbose, debug):
    """CcBitTorrent - High-performance BitTorrent client."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    # Convert debug flag to verbosity count for backward compatibility
    if debug:
        verbose = max(verbose, 2)  # -d is equivalent to -vv
    ctx.obj["verbosity"] = verbose
    ctx.obj["verbose"] = verbose > 0  # Keep for backward compatibility
    ctx.obj["debug"] = debug

    # Initialize verbosity manager and update logging level
    verbosity_manager = VerbosityManager.from_count(verbose)
    ctx.obj["verbosity_manager"] = verbosity_manager

    # CRITICAL: Initialize translations FIRST, before any user-facing output
    # This ensures all subsequent strings are properly translated
    config_manager = None
    translation_manager = None
    with contextlib.suppress(Exception):
        config_manager = init_config(config)
        if config_manager:
            # Initialize translations immediately after config
            translation_manager = TranslationManager(config_manager.config)

            # Validate locale and warn if invalid
            from ccbt.i18n import _is_valid_locale, get_locale

            current_locale = get_locale()
            if not _is_valid_locale(current_locale):
                # Log warning but continue with default locale
                logger.warning(
                    _("Invalid locale '{current_locale}' specified. "
                    "Falling back to 'en'. Available locales: "
                    "en, es, fr, hi, ur, fa, arc, ja, ko, zh, th, sw, ha, yo, eu").format(
                        current_locale=current_locale
                    )
                )
            # Update logging level based on verbosity
            cfg = config_manager.config
            if hasattr(cfg, "observability"):
                from ccbt.models import LogLevel
                from ccbt.utils.logging_config import setup_logging

                # Temporarily override log level based on verbosity
                original_log_level = cfg.observability.log_level

                # Map verbosity to log level: -v=INFO, -vv/-vvv=DEBUG
                if verbosity_manager.is_debug():
                    cfg.observability.log_level = LogLevel.DEBUG
                elif verbosity_manager.is_verbose():
                    cfg.observability.log_level = LogLevel.INFO
                # else: keep original level (usually INFO)

                # Setup logging with verbosity-aware level
                setup_logging(cfg.observability)

                # Restore original log level (verbosity only affects console output)
                cfg.observability.log_level = original_log_level

    # docs command removed; docs are maintained in repository


@cli.command()
@click.argument("torrent_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help=_("Output directory"))
@click.option("--interactive", "-i", is_flag=True, help=_("Start interactive mode"))
@click.option("--monitor", "-m", is_flag=True, help=_("Enable monitoring"))
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    help=_("Resume from checkpoint if available"),
)
@click.option("--no-checkpoint", is_flag=True, help=_("Disable checkpointing"))
@click.option("--checkpoint-dir", type=click.Path(), help=_("Checkpoint directory"))
@click.option("--listen-port", type=int, help=_("Listen port"))
@click.option("--max-peers", type=int, help=_("Maximum global peers"))
@click.option("--max-peers-per-torrent", type=int, help=_("Maximum peers per torrent"))
@click.option("--pipeline-depth", type=int, help=_("Request pipeline depth"))
@click.option("--block-size-kib", type=int, help=_("Block size (KiB)"))
@click.option("--connection-timeout", type=float, help=_("Connection timeout (s)"))
@click.option("--download-limit", type=int, help=_("Global download limit (KiB/s)"))
@click.option("--upload-limit", type=int, help=_("Global upload limit (KiB/s)"))
@click.option("--dht-port", type=int, help=_("DHT port"))
@click.option("--enable-dht", is_flag=True, help=_("Enable DHT"))
@click.option("--disable-dht", is_flag=True, help=_("Disable DHT"))
@click.option(
    "--piece-selection",
    type=click.Choice(["round_robin", "rarest_first", "sequential"]),
)
@click.option("--endgame-threshold", type=float, help=_("Endgame threshold (0..1)"))
@click.option("--hash-workers", type=int, help=_("Hash verification workers"))
@click.option("--disk-workers", type=int, help=_("Disk I/O workers"))
@click.option("--use-mmap", is_flag=True, help=_("Use memory mapping"))
@click.option("--no-mmap", is_flag=True, help=_("Disable memory mapping"))
@click.option("--mmap-cache-mb", type=int, help=_("MMap cache size (MB)"))
@click.option("--write-batch-kib", type=int, help=_("Write batch size (KiB)"))
@click.option("--write-buffer-kib", type=int, help=_("Write buffer size (KiB)"))
@click.option("--preallocate", type=click.Choice(["none", "sparse", "full"]))
@click.option("--sparse-files", is_flag=True, help=_("Enable sparse files"))
@click.option("--no-sparse-files", is_flag=True, help=_("Disable sparse files"))
@click.option(
    "--enable-io-uring",
    is_flag=True,
    help=_("Enable io_uring on Linux if available"),
)
@click.option("--disable-io-uring", is_flag=True, help=_("Disable io_uring usage"))
@click.option(
    "--direct-io",
    is_flag=True,
    help=_("Enable direct I/O for writes when supported"),
)
@click.option("--sync-writes", is_flag=True, help=_("Enable fsync after batched writes"))
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
)
@click.option("--enable-metrics", is_flag=True, help=_("Enable metrics"))
@click.option("--disable-metrics", is_flag=True, help=_("Disable metrics"))
@click.option("--metrics-port", type=int, help=_("Metrics port"))
@click.option("--enable-ipv6", is_flag=True, help=_("Enable IPv6"))
@click.option("--disable-ipv6", is_flag=True, help=_("Disable IPv6"))
@click.option("--enable-tcp", is_flag=True, help=_("Enable TCP transport"))
@click.option("--disable-tcp", is_flag=True, help=_("Disable TCP transport"))
@click.option("--enable-utp", is_flag=True, help=_("Enable uTP transport"))
@click.option("--disable-utp", is_flag=True, help=_("Disable uTP transport"))
@click.option("--enable-encryption", is_flag=True, help=_("Enable protocol encryption"))
@click.option("--disable-encryption", is_flag=True, help=_("Disable protocol encryption"))
@click.option("--tcp-nodelay", is_flag=True, help=_("Enable TCP_NODELAY"))
@click.option("--no-tcp-nodelay", is_flag=True, help=_("Disable TCP_NODELAY"))
@click.option("--socket-rcvbuf-kib", type=int, help=_("Socket receive buffer (KiB)"))
@click.option("--socket-sndbuf-kib", type=int, help=_("Socket send buffer (KiB)"))
@click.option("--listen-interface", type=str, help=_("Listen interface"))
@click.option("--peer-timeout", type=float, help=_("Peer timeout (s)"))
@click.option("--dht-timeout", type=float, help=_("DHT timeout (s)"))
@click.option("--min-block-size-kib", type=int, help=_("Minimum block size (KiB)"))
@click.option("--max-block-size-kib", type=int, help=_("Maximum block size (KiB)"))
@click.option("--enable-http-trackers", is_flag=True, help=_("Enable HTTP trackers"))
@click.option("--disable-http-trackers", is_flag=True, help=_("Disable HTTP trackers"))
@click.option("--enable-udp-trackers", is_flag=True, help=_("Enable UDP trackers"))
@click.option("--disable-udp-trackers", is_flag=True, help=_("Disable UDP trackers"))
@click.option(
    "--tracker-announce-interval",
    type=float,
    help=_("Tracker announce interval (s)"),
)
@click.option(
    "--tracker-scrape-interval",
    type=float,
    help=_("Tracker scrape interval (s)"),
)
@click.option("--pex-interval", type=float, help=_("PEX interval (s)"))
@click.option("--endgame-duplicates", type=int, help=_("Endgame duplicate requests"))
@click.option("--streaming-mode", is_flag=True, help=_("Enable streaming mode"))
@click.option("--first-piece-priority", is_flag=True, help=_("Prioritize first piece"))
@click.option("--last-piece-priority", is_flag=True, help=_("Prioritize last piece"))
@click.option(
    "--optimistic-unchoke-interval",
    type=float,
    help=_("Optimistic unchoke interval (s)"),
)
@click.option("--unchoke-interval", type=float, help=_("Unchoke interval (s)"))
@click.option("--metrics-interval", type=float, help=_("Metrics interval (s)"))
@click.pass_context
def download(
    ctx,
    torrent_file,
    output,
    interactive,
    monitor,
    resume,
    no_checkpoint,
    checkpoint_dir,
    **kwargs,
):
    """Download a torrent file."""
    console = Console()

    try:
        # CRITICAL FIX: Always check for daemon PID file FIRST before calling _get_executor()
        # This prevents any possibility of creating a local session when daemon is running
        daemon_manager = DaemonManager()
        pid_file_exists = daemon_manager.pid_file.exists()

        if pid_file_exists:
            # Daemon PID file exists - MUST use daemon, never create local session
            # _get_executor() will raise exception if connection fails (prevents fallback to local)
            try:
                executor, is_daemon = asyncio.run(_get_executor())
                if executor is None or not is_daemon:
                    # This should never happen if PID file exists - _get_executor() should raise
                    raise click.ClickException(DAEMON_EXECUTOR_NOT_AVAILABLE_MSG)
            except click.ClickException:
                # Re-raise ClickException (these are user-facing errors about daemon state)
                raise
            except Exception as e:
                # Any other exception from _get_executor() means daemon connection failed
                error_msg = _(
                    "Daemon PID file exists but cannot connect to daemon: {error}\n\n"
                    "To resolve:\n"
                    "  1. Run 'btbt daemon status' to check daemon state\n"
                    "  2. Check IPC port configuration matches daemon port\n"
                    "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
                    "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
                ).format(error=e)
                raise click.ClickException(error_msg) from e
        else:
            # No PID file - safe to check for daemon via _get_executor() (will return None if not running)
            executor, is_daemon = asyncio.run(_get_executor())

        if executor is not None and is_daemon:
            # Daemon is running - use daemon executor
            async def _add_torrent_to_daemon():
                try:
                    result = await executor.execute(
                        "torrent.add",
                        path_or_magnet=str(torrent_file),
                        output_dir=str(output) if output else None,
                        resume=resume,
                    )
                    if not result.success:
                        error_msg = f"Failed to add torrent to daemon: {result.error}"
                        raise click.ClickException(error_msg)
                    console.print(
                        _("[green]Torrent added to daemon: {info_hash}[/green]").format(
                            info_hash=result.data.get("info_hash", "unknown")
                        )
                    )
                finally:
                    # Clean up IPC client for short-lived commands
                    if hasattr(executor.adapter, "ipc_client"):
                        try:
                            ipc_client = executor.adapter.ipc_client
                            if ipc_client and hasattr(ipc_client, "close"):
                                await ipc_client.close()  # type: ignore[attr-defined]
                        except Exception as e:
                            logger.debug(_("Error closing IPC client: %s"), e)

            asyncio.run(_add_torrent_to_daemon())
            return

        # CRITICAL FIX: Double-check daemon PID file before creating local session
        # This is a safety check - if we reach here, PID file should NOT exist
        # (because we checked it at the start and _get_executor() would have raised if it existed)
        if pid_file_exists:
            # This should never happen - we checked at the start and _get_executor() should have raised
            raise click.ClickException(DAEMON_CRITICAL_ERROR_MSG)

        # No daemon running - create local session and executor
        # CRITICAL FIX: Use ExecutorManager for consistency, even for local sessions
        from ccbt.executor.manager import ExecutorManager

        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        # Apply CLI overrides
        _apply_cli_overrides(config_manager, kwargs)
        config = config_manager.config

        # Override checkpoint settings if specified
        if no_checkpoint:
            config.disk.checkpoint_enabled = False
        if checkpoint_dir:
            config.disk.checkpoint_dir = checkpoint_dir

        # Create session (only when daemon is NOT running)
        session = AsyncSessionManager(".")

        # CRITICAL FIX: Start session immediately to initialize NAT manager, TCP server, and port bindings
        # This ensures components use configured ports instead of random ports
        # NOTE: This only runs when daemon is confirmed NOT running - no port conflicts possible
        asyncio.run(session.start())

        # CRITICAL FIX: Use ExecutorManager to ensure consistent executor creation
        # This prevents duplicate executors and ensures proper session reference management
        executor_manager = ExecutorManager.get_instance()
        executor = executor_manager.get_executor(session_manager=session)

        # Load torrent
        torrent_path = Path(torrent_file)
        torrent_data = session.load_torrent(torrent_path)

        if not torrent_data:
            console.print(
                _("[red]Error: Could not load torrent file {torrent_file}[/red]").format(torrent_file=torrent_file),
            )
            msg = "Command failed"
            _raise_cli_error(msg)

        # Check for existing checkpoint
        if config.disk.checkpoint_enabled and not resume:
            from ccbt.storage.checkpoint import CheckpointManager

            checkpoint_manager = CheckpointManager(config.disk)
            # Handle both dict and TorrentInfo types
            info_hash = (
                torrent_data["info_hash"]
                if isinstance(torrent_data, dict)
                else torrent_data.info_hash
                if torrent_data is not None
                else None
            )
            checkpoint = None
            if info_hash is not None:
                checkpoint = asyncio.run(
                    checkpoint_manager.load_checkpoint(info_hash),
                )

            if checkpoint:
                console.print(
                    _("[yellow]Found checkpoint for: {torrent_name}[/yellow]").format(
                        torrent_name=getattr(checkpoint, "torrent_name", "Unknown")
                    ),
                )
                console.print(
                    f"[blue]Progress: {len(getattr(checkpoint, 'verified_pieces', []))}/{getattr(checkpoint, 'total_pieces', 0)} pieces verified[/blue]",
                )

                # Prompt user if not in non-interactive mode
                import sys

                if sys.stdin.isatty():
                    from rich.prompt import Confirm

                    try:
                        should_resume = Confirm.ask(
                            "Resume from checkpoint?",
                            default=True,
                        )
                        if should_resume:
                            resume = True
                            console.print(_("[green]Resuming from checkpoint[/green]"))
                        else:
                            console.print(_("[yellow]Starting fresh download[/yellow]"))
                    except ImportError:
                        console.print(
                            _("[yellow]Rich not available, starting fresh download[/yellow]"),
                        )
                else:
                    console.print(
                        _("[yellow]Non-interactive mode, starting fresh download[/yellow]"),
                    )

        # Set output directory
        if output:
            if isinstance(torrent_data, dict):
                torrent_data["download_path"] = Path(output)
            else:
                # For TorrentInfo, we'll pass output_dir separately
                pass

        # Start monitoring if requested
        if monitor:
            asyncio.run(start_monitoring(session, console))

        # Start download
        if interactive:
            asyncio.run(
                start_interactive_download(
                    session,
                    torrent_data if torrent_data is not None else {},
                    console,
                    resume=resume,
                ),
            )
        else:
            asyncio.run(
                start_basic_download(
                    session,
                    torrent_data if torrent_data is not None else {},
                    console,
                    resume=resume,
                ),
            )

    except FileNotFoundError as e:
        console.print(_("[red]File not found: {error}[/red]").format(error=e))
        msg = _("Torrent file not found")
        raise click.ClickException(msg) from e
    except ValueError as e:
        console.print(_("[red]Invalid torrent file: {error}[/red]").format(error=e))
        msg = _("Invalid torrent file format")
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("magnet_link")
@click.option("--output", "-o", type=click.Path(), help=_("Output directory"))
@click.option("--interactive", "-i", is_flag=True, help=_("Start interactive mode"))
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    help=_("Resume from checkpoint if available"),
)
@click.option("--no-checkpoint", is_flag=True, help=_("Disable checkpointing"))
@click.option("--checkpoint-dir", type=click.Path(), help=_("Checkpoint directory"))
@click.option("--listen-port", type=int, help=_("Listen port"))
@click.option("--max-peers", type=int, help=_("Maximum global peers"))
@click.option("--max-peers-per-torrent", type=int, help=_("Maximum peers per torrent"))
@click.option("--pipeline-depth", type=int, help=_("Request pipeline depth"))
@click.option("--block-size-kib", type=int, help=_("Block size (KiB)"))
@click.option("--connection-timeout", type=float, help=_("Connection timeout (s)"))
@click.option("--download-limit", type=int, help=_("Global download limit (KiB/s)"))
@click.option("--upload-limit", type=int, help=_("Global upload limit (KiB/s)"))
@click.option("--dht-port", type=int, help=_("DHT port"))
@click.option("--enable-dht", is_flag=True, help=_("Enable DHT"))
@click.option("--disable-dht", is_flag=True, help=_("Disable DHT"))
@click.option(
    "--piece-selection",
    type=click.Choice(["round_robin", "rarest_first", "sequential"]),
)
@click.option("--endgame-threshold", type=float, help=_("Endgame threshold (0..1)"))
@click.option("--hash-workers", type=int, help=_("Hash verification workers"))
@click.option("--disk-workers", type=int, help=_("Disk I/O workers"))
@click.option("--use-mmap", is_flag=True, help=_("Use memory mapping"))
@click.option("--no-mmap", is_flag=True, help=_("Disable memory mapping"))
@click.option("--mmap-cache-mb", type=int, help=_("MMap cache size (MB)"))
@click.option("--write-batch-kib", type=int, help=_("Write batch size (KiB)"))
@click.option("--write-buffer-kib", type=int, help=_("Write buffer size (KiB)"))
@click.option("--preallocate", type=click.Choice(["none", "sparse", "full"]))
@click.option("--sparse-files", is_flag=True, help=_("Enable sparse files"))
@click.option("--no-sparse-files", is_flag=True, help=_("Disable sparse files"))
@click.option(
    "--enable-io-uring",
    is_flag=True,
    help=_("Enable io_uring on Linux if available"),
)
@click.option("--disable-io-uring", is_flag=True, help=_("Disable io_uring usage"))
@click.option(
    "--direct-io",
    is_flag=True,
    help=_("Enable direct I/O for writes when supported"),
)
@click.option("--sync-writes", is_flag=True, help=_("Enable fsync after batched writes"))
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
)
@click.option("--enable-metrics", is_flag=True, help=_("Enable metrics"))
@click.option("--disable-metrics", is_flag=True, help=_("Disable metrics"))
@click.option("--metrics-port", type=int, help=_("Metrics port"))
@click.option("--enable-ipv6", is_flag=True, help=_("Enable IPv6"))
@click.option("--disable-ipv6", is_flag=True, help=_("Disable IPv6"))
@click.option("--enable-tcp", is_flag=True, help=_("Enable TCP transport"))
@click.option("--disable-tcp", is_flag=True, help=_("Disable TCP transport"))
@click.option("--enable-utp", is_flag=True, help=_("Enable uTP transport"))
@click.option("--disable-utp", is_flag=True, help=_("Disable uTP transport"))
@click.option("--enable-encryption", is_flag=True, help=_("Enable protocol encryption"))
@click.option("--disable-encryption", is_flag=True, help=_("Disable protocol encryption"))
@click.option("--tcp-nodelay", is_flag=True, help=_("Enable TCP_NODELAY"))
@click.option("--no-tcp-nodelay", is_flag=True, help=_("Disable TCP_NODELAY"))
@click.option("--socket-rcvbuf-kib", type=int, help=_("Socket receive buffer (KiB)"))
@click.option("--socket-sndbuf-kib", type=int, help=_("Socket send buffer (KiB)"))
@click.option("--listen-interface", type=str, help=_("Listen interface"))
@click.option("--peer-timeout", type=float, help=_("Peer timeout (s)"))
@click.option("--dht-timeout", type=float, help=_("DHT timeout (s)"))
@click.option("--min-block-size-kib", type=int, help=_("Minimum block size (KiB)"))
@click.option("--max-block-size-kib", type=int, help=_("Maximum block size (KiB)"))
@click.option("--enable-http-trackers", is_flag=True, help=_("Enable HTTP trackers"))
@click.option("--disable-http-trackers", is_flag=True, help=_("Disable HTTP trackers"))
@click.option("--enable-udp-trackers", is_flag=True, help=_("Enable UDP trackers"))
@click.option("--disable-udp-trackers", is_flag=True, help=_("Disable UDP trackers"))
@click.option(
    "--tracker-announce-interval",
    type=float,
    help=_("Tracker announce interval (s)"),
)
@click.option(
    "--tracker-scrape-interval",
    type=float,
    help=_("Tracker scrape interval (s)"),
)
@click.option("--pex-interval", type=float, help=_("PEX interval (s)"))
@click.option("--endgame-duplicates", type=int, help=_("Endgame duplicate requests"))
@click.option("--streaming-mode", is_flag=True, help=_("Enable streaming mode"))
@click.option("--first-piece-priority", is_flag=True, help=_("Prioritize first piece"))
@click.option("--last-piece-priority", is_flag=True, help=_("Prioritize last piece"))
@click.option(
    "--optimistic-unchoke-interval",
    type=float,
    help=_("Optimistic unchoke interval (s)"),
)
@click.option("--unchoke-interval", type=float, help=_("Unchoke interval (s)"))
@click.option("--metrics-interval", type=float, help=_("Metrics interval (s)"))
@click.pass_context
def magnet(
    ctx,
    magnet_link,
    output,
    interactive,
    resume,
    no_checkpoint,
    checkpoint_dir,
    **kwargs,
):
    """Download from magnet link."""
    console = Console()

    try:
        # CRITICAL FIX: Use a single event loop for the entire operation
        # This prevents "Event loop is closed" errors when IPCClient is created
        # in one event loop and used in another
        # Capture variables from outer scope for closure
        _magnet_link = str(magnet_link)
        _output = str(output) if output else None
        _resume = [resume]  # Use list to allow modification in closure
        _interactive = interactive

        async def _magnet_operation():
            """Handle magnet operation in a single event loop."""
            # CRITICAL FIX: Always check for daemon PID file FIRST before calling _get_executor()
            # This prevents any possibility of creating a local session when daemon is running
            daemon_manager = DaemonManager()
            pid_file_exists = daemon_manager.pid_file.exists()
            pid_file_path = daemon_manager.pid_file

            logger.debug(
                _("Magnet command: PID file check - exists=%s, path=%s"),
                pid_file_exists,
                pid_file_path,
            )

            if pid_file_exists:
                # Daemon PID file exists - MUST use daemon, never create local session
                # _get_executor() will raise exception if connection fails (prevents fallback to local)
                try:
                    executor, is_daemon = await _get_executor()
                    if executor is None or not is_daemon:
                        # This should never happen if PID file exists - _get_executor() should raise
                        raise click.ClickException(DAEMON_EXECUTOR_NOT_AVAILABLE_MSG)
                except click.ClickException:
                    # Re-raise ClickException (these are user-facing errors about daemon state)
                    raise
                except Exception as e:
                    # Any other exception from _get_executor() means daemon connection failed
                    error_msg = (
                        f"Daemon PID file exists but cannot connect to daemon: {e}\n\n"
                        "To resolve:\n"
                        "  1. Run 'btbt daemon status' to check daemon state\n"
                        "  2. Check IPC port configuration matches daemon port\n"
                        "  3. If daemon crashed, restart it: 'btbt daemon start'\n"
                        "  4. If you want to run locally, stop the daemon: 'btbt daemon exit'"
                    )
                    raise click.ClickException(error_msg) from e
            else:
                # No PID file - safe to check for daemon via _get_executor() (will return None if not running)
                logger.debug(_("No PID file found, checking for daemon via _get_executor()"))
                executor, is_daemon = await _get_executor()
                logger.debug(_("_get_executor() returned: executor=%s, is_daemon=%s"), executor is not None, is_daemon)

            if executor is not None and is_daemon:
                logger.debug(_("Using daemon executor for magnet command"))
                # Daemon is running - use daemon executor
                try:
                    result = await executor.execute(
                        "torrent.add",
                        path_or_magnet=_magnet_link,
                        output_dir=_output,
                        resume=_resume[0],
                    )
                    if not result.success:
                        error_msg = f"Failed to add magnet link to daemon: {result.error}"
                        raise click.ClickException(error_msg)
                    console.print(
                        _("[green]Magnet link added to daemon: {info_hash}[/green]").format(
                            info_hash=result.data.get("info_hash", "unknown")
                        )
                    )
                finally:
                    # Clean up IPC client for short-lived commands
                    if hasattr(executor.adapter, "ipc_client"):
                        try:
                            ipc_client = executor.adapter.ipc_client
                            if ipc_client and hasattr(ipc_client, "close"):
                                await ipc_client.close()  # type: ignore[attr-defined]
                        except Exception as e:
                            logger.debug(_("Error closing IPC client: %s"), e)
                return

            # CRITICAL FIX: Double-check daemon PID file before creating local session
            # This is a safety check - if we reach here, PID file should NOT exist
            # (because we checked it at the start and _get_executor() would have raised if it existed)
            # But we check again as a defensive measure
            # CRITICAL: Re-check PID file in case it was created between initial check and now
            current_pid_file_exists = daemon_manager.pid_file.exists()
            if current_pid_file_exists or pid_file_exists:
                logger.error(
                    _("CRITICAL: PID file exists (initial=%s, current=%s, path=%s) but code reached local session creation! "
                    "This will cause port conflicts. Aborting."),
                    pid_file_exists,
                    current_pid_file_exists,
                    daemon_manager.pid_file,
                )
                error_msg = _("{msg}\n\nPID file path: {path}").format(msg=DAEMON_CRITICAL_ERROR_MSG, path=daemon_manager.pid_file)
                raise click.ClickException(error_msg)

            logger.debug(
                _("No daemon detected (PID file doesn't exist), creating local session. PID file path: %s"),
                daemon_manager.pid_file,
            )

            # No daemon running - create local session and executor
            # CRITICAL FIX: Use ExecutorManager for consistency, even for local sessions
            from ccbt.executor.manager import ExecutorManager

            # Load configuration
            config_manager = ConfigManager(ctx.obj["config"])
            _apply_cli_overrides(config_manager, kwargs)
            config = config_manager.config

            # Override checkpoint settings if specified
            if no_checkpoint:
                config.disk.checkpoint_enabled = False
            if checkpoint_dir:
                config.disk.checkpoint_dir = checkpoint_dir

            # Create session (only when daemon is NOT running)
            session = AsyncSessionManager(".")

            # CRITICAL FIX: Start session immediately to initialize NAT manager, TCP server, and port bindings
            # This ensures components use configured ports instead of random ports
            # NOTE: This only runs when daemon is confirmed NOT running - no port conflicts possible
            await session.start()

            # CRITICAL FIX: Use ExecutorManager to ensure consistent executor creation
            # This prevents duplicate executors and ensures proper session reference management
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=session)

            # Parse magnet link
            torrent_data = session.parse_magnet_link(_magnet_link)

            if not torrent_data:
                console.print(_("[red]Error: Could not parse magnet link[/red]"))
                msg = "Command failed"
                raise click.ClickException(msg)

            # Check for existing checkpoint
            if config.disk.checkpoint_enabled and not _resume[0]:
                from ccbt.storage.checkpoint import CheckpointManager

                checkpoint_manager = CheckpointManager(config.disk)
                # Handle both dict and TorrentInfo types
                info_hash = (
                    torrent_data["info_hash"]
                    if isinstance(torrent_data, dict)
                    else torrent_data.info_hash
                    if torrent_data is not None
                    else None
                )
                checkpoint = None
                if info_hash is not None:
                    checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

                if checkpoint:
                    console.print(
                        _("[yellow]Found checkpoint for: {name}[/yellow]").format(name=getattr(checkpoint, 'torrent_name', 'Unknown')),
                    )
                    console.print(
                        _("[blue]Progress: {verified}/{total} pieces verified[/blue]").format(
                            verified=len(getattr(checkpoint, 'verified_pieces', [])),
                            total=getattr(checkpoint, 'total_pieces', 0)
                        ),
                    )

                    # Prompt user if not in non-interactive mode
                    import sys

                    if sys.stdin.isatty():
                        from rich.prompt import Confirm

                        try:
                            should_resume = Confirm.ask(
                                _("Resume from checkpoint?"),
                                default=True,
                            )
                            if should_resume:
                                _resume[0] = True
                                console.print(_("[green]Resuming from checkpoint[/green]"))
                            else:
                                console.print(
                                    _("[yellow]Starting fresh download[/yellow]")
                                )
                        except ImportError:
                            console.print(
                                _("[yellow]Rich not available, starting fresh download[/yellow]"),
                            )
                    else:
                        console.print(
                            _("[yellow]Non-interactive mode, starting fresh download[/yellow]"),
                        )

            # Set output directory
            if _output:
                if isinstance(torrent_data, dict):
                    torrent_data["download_path"] = Path(_output)
                else:
                    # For TorrentInfo, we'll pass output_dir separately
                    pass

            # Start download
            if _interactive:
                await start_interactive_download(
                    session,
                    torrent_data if torrent_data is not None else {},
                    console,
                    resume=_resume[0],
                )
            else:
                # Non-interactive download - use basic download function
                await start_basic_magnet_download(
                    session,
                    _magnet_link,
                    console,
                    resume=_resume[0],
                )

        # Run the entire operation in a single event loop
        asyncio.run(_magnet_operation())
        return

    except ValueError as e:
        console.print(_("[red]Invalid magnet link: {e}[/red]").format(e=e))
        msg = _("Invalid magnet link format")
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.option("--port", "-p", type=int, default=9090, help=_("Port for web interface"))
@click.option("--host", "-h", default="localhost", help=_("Host for web interface"))
@click.pass_context
def web(ctx, port, host):
    """Start web interface."""
    console = Console()

    try:
        # CRITICAL FIX: Check for daemon PID file BEFORE creating local session
        # If PID file exists, we MUST prevent local session to avoid port conflicts
        daemon_manager = DaemonManager()
        pid_file_exists = daemon_manager.pid_file.exists()

        if pid_file_exists:
            raise click.ClickException(DAEMON_WEB_INTERFACE_CONFLICT_MSG)

        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session (only when daemon is NOT running)
        session = AsyncSessionManager(".")

        # Start web interface
        console.print(
            _("[green]Starting web interface on http://{host}:{port}[/green]").format(
                host=host, port=port
            )
        )
        asyncio.run(session.start_web_interface(host, port))

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start interactive mode."""
    console = Console()

    try:
        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Get executor (daemon or local) - this handles daemon detection and routing
        executor, is_daemon = asyncio.run(_get_executor())

        if executor is None:
            # No daemon running - create local session and executor
            # CRITICAL FIX: Use ExecutorManager for consistency
            from ccbt.executor.manager import ExecutorManager

            session = AsyncSessionManager(".")
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=session)
            # Get adapter from executor for InteractiveCLI
            adapter = executor.adapter

            # Start interactive CLI with local session
            interactive_cli = InteractiveCLI(
                executor, adapter, console, session=session
            )
        else:
            # Daemon is running - use daemon executor
            adapter = executor.adapter
            interactive_cli = InteractiveCLI(executor, adapter, console, session=None)

        asyncio.run(interactive_cli.run())

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def status(ctx):
    """Show client status."""
    console = Console()

    async def _get_status_async() -> None:
        """Async helper for status command."""
        try:
            # Get executor (daemon or local) - this handles daemon detection and routing
            executor, is_daemon = await _get_executor()

            if executor is not None and is_daemon:
                # Daemon is running - use daemon executor to get status
                try:
                    # Use IPC client directly to get daemon status
                    ipc_client = executor.adapter.ipc_client
                    status_response = await ipc_client.get_status()

                    # Display daemon status
                    from rich.table import Table

                    table = Table(title="ccBitTorrent Daemon Status")
                    table.add_column("Component", style="cyan")
                    table.add_column("Status", style="green")
                    table.add_column("Details")

                    table.add_row(
                        "Daemon",
                        "Running",
                        f"PID: {status_response.pid if hasattr(status_response, 'pid') else 'unknown'}",
                    )
                    table.add_row(
                        "IPC Server",
                        "Active",
                        f"{status_response.ipc_host if hasattr(status_response, 'ipc_host') else '127.0.0.1'}:{status_response.ipc_port if hasattr(status_response, 'ipc_port') else 8080}",
                    )
                    table.add_row(
                        "Session",
                        "Active",
                        f"Torrents: {status_response.torrent_count if hasattr(status_response, 'torrent_count') else 0}",
                    )

                    console.print(table)
                finally:
                    # Clean up IPC client for short-lived commands
                    if hasattr(executor.adapter, "ipc_client"):
                        try:
                            ipc_client = executor.adapter.ipc_client
                            if ipc_client and hasattr(ipc_client, "close"):
                                await ipc_client.close()  # type: ignore[attr-defined]
                        except Exception as e:
                            logger.debug(_("Error closing IPC client: %s"), e)
                return

            # No daemon running - create local session and show status
            # Load configuration
            ConfigManager(ctx.obj["config"])

            # Create session for local status (only when daemon is NOT running)
            session = AsyncSessionManager(".")

            # Create adapter and show status
            from ccbt.cli.status import show_status
            from ccbt.executor.session_adapter import LocalSessionAdapter

            adapter = LocalSessionAdapter(session)
            await show_status(adapter, console)

        except Exception as e:
            console.print(_("[red]Error: {error}[/red]").format(error=e))
            raise click.ClickException(str(e)) from e

    try:
        asyncio.run(_get_status_async())
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def config(ctx):
    """Manage configuration."""
    console = Console()

    try:
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Show configuration
        show_config(config, console)

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.option("--set", "locale_code", help=_("Set locale (e.g., 'en', 'es', 'fr')"))
@click.option("--list", "list_locales", is_flag=True, help=_("List available locales"))
@click.pass_context
def language(ctx, locale_code: str | None, list_locales: bool) -> None:
    """Manage language/locale settings."""
    from pathlib import Path

    from ccbt.i18n import get_locale, set_locale
    from ccbt.i18n.manager import TranslationManager

    console = Console()

    if list_locales:
        # List available locales
        locale_dir = Path(__file__).parent.parent / "i18n" / "locales"
        if locale_dir.exists():
            locales = [
                d.name
                for d in locale_dir.iterdir()
                if d.is_dir() and d.name != "__pycache__"
            ]
            console.print(_("Available locales: {locales}").format(locales=', '.join(sorted(locales))))
        else:
            console.print(_("No locales directory found"))
        console.print(_("Current locale: {locale}").format(locale=get_locale()))
    elif locale_code:
        set_locale(locale_code)
        console.print(_("[green]Locale set to: {locale_code}[/green]").format(locale_code=locale_code))
        # Optionally update config
        try:
            config_manager = ConfigManager(ctx.obj["config"])
            if hasattr(config_manager.config, "ui"):
                config_manager.config.ui.locale = locale_code
                # Note: ConfigManager doesn't have a save method, so this is in-memory only
                # For persistence, user should update config file manually
                TranslationManager(config_manager.config)
                console.print(
                    _("[yellow]Note: Update config file to persist locale setting[/yellow]")
                )
        except Exception:
            pass
    else:
        console.print(_("Current locale: {locale}").format(locale=get_locale()))


@cli.command()
@click.pass_context
def debug(ctx):
    """Start debug mode."""
    console = Console()

    try:
        # CRITICAL FIX: Check for daemon PID file BEFORE creating local session
        # If PID file exists, we MUST prevent local session to avoid port conflicts
        daemon_manager = DaemonManager()
        pid_file_exists = daemon_manager.pid_file.exists()

        if pid_file_exists:
            raise click.ClickException(DAEMON_DEBUG_MODE_CONFLICT_MSG)

        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session (only when daemon is NOT running)
        session = AsyncSessionManager(".")

        # Start debug mode
        asyncio.run(start_debug_mode(session, console))

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.group()
def checkpoints():
    """Manage download checkpoints."""


@checkpoints.command("list")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "binary", "both"]),
    default="both",
    help=_("Show checkpoints in specific format"),
)
@click.pass_context
def list_checkpoints(ctx, _checkpoint_format):
    """List available checkpoints."""
    console = Console()

    try:
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Create checkpoint manager
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config.disk)

        # List checkpoints
        checkpoints = asyncio.run(checkpoint_manager.list_checkpoints())

        if not checkpoints:
            console.print(_("[yellow]No checkpoints found[/yellow]"))
            return

        # Create table
        table = Table(title="Available Checkpoints")
        table.add_column("Info Hash", style="cyan")
        table.add_column("Format", style="green")
        table.add_column("Size", style="blue")
        table.add_column("Created", style="magenta")
        table.add_column("Updated", style="yellow")
        table.add_column("State", style="yellow")

        for checkpoint in checkpoints:
            # Try to load checkpoint to get state info
            checkpoint_data = None
            try:
                checkpoint_data = asyncio.run(
                    checkpoint_manager.load_checkpoint(checkpoint.info_hash)
                )
            except Exception:
                pass

            state_info = "unknown"
            if checkpoint_data:
                if hasattr(checkpoint_data, "session_state") and checkpoint_data.session_state:
                    state_info = checkpoint_data.session_state
                elif hasattr(checkpoint_data, "verified_pieces") and hasattr(checkpoint_data, "total_pieces"):
                    progress = len(checkpoint_data.verified_pieces) / max(checkpoint_data.total_pieces, 1)
                    if progress >= 1.0:
                        state_info = "completed"
                    else:
                        state_info = f"{progress:.1%}"

            table.add_row(
                checkpoint.info_hash.hex()[:16] + "...",
                checkpoint.checkpoint_format.value,
                f"{checkpoint.size:,} bytes",
                time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(checkpoint.created_at),
                ),
                time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(checkpoint.updated_at),
                ),
                state_info,
            )

        console.print(table)

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("clean")
@click.option(
    "--days",
    "-d",
    type=int,
    default=30,
    help=_("Remove checkpoints older than N days"),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=_("Show what would be deleted without actually deleting"),
)
@click.pass_context
def clean_checkpoints(ctx, days, dry_run):
    """Clean up old checkpoints."""
    console = Console()

    try:
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Create checkpoint manager
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config.disk)

        if dry_run:
            # List old checkpoints without deleting
            checkpoints = asyncio.run(checkpoint_manager.list_checkpoints())
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            old_checkpoints = [cp for cp in checkpoints if cp.updated_at < cutoff_time]

            if not old_checkpoints:
                console.print(
                    _("[green]No checkpoints older than {days} days found[/green]").format(days=days),
                )
                return

            console.print(
                _("[yellow]Would delete {count} checkpoints older than {days} days:[/yellow]").format(
                    count=len(old_checkpoints), days=days
                ),
            )
            for checkpoint in old_checkpoints:
                format_value = getattr(checkpoint, "format", None)
                format_str = format_value.value if format_value and hasattr(format_value, "value") else "unknown"
                console.print(
                    f"  - {checkpoint.info_hash.hex()[:16]}... ({format_str})",
                )
        else:
            # Actually clean up
            deleted_count = asyncio.run(
                checkpoint_manager.cleanup_old_checkpoints(days),
            )
            console.print(
                _("[green]Cleaned up {count} old checkpoints[/green]").format(
                    count=deleted_count
                )
            )

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("delete")
@click.argument("info_hash")
@click.pass_context
def delete_checkpoint(ctx, info_hash):
    """Delete a specific checkpoint."""
    console = Console()

    try:
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Create checkpoint manager
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config.disk)

        # Convert hex string to bytes
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)

        # Delete checkpoint
        deleted = asyncio.run(checkpoint_manager.delete_checkpoint(info_hash_bytes))

        if deleted:
            console.print(_("[green]Deleted checkpoint for {info_hash}[/green]").format(info_hash=info_hash))
        else:
            console.print(_("[yellow]No checkpoint found for {info_hash}[/yellow]").format(info_hash=info_hash))

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("verify")
@click.argument("info_hash")
@click.pass_context
def verify_checkpoint_cmd(ctx, info_hash):
    """Verify checkpoint integrity for a given info hash (hex)."""
    console = Console()
    try:
        config_manager = ConfigManager(ctx.obj["config"])
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config_manager.config.disk)
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)
        valid = asyncio.run(checkpoint_manager.verify_checkpoint(info_hash_bytes))
        if valid:
            console.print(_("[green]Checkpoint for {info_hash} is valid[/green]").format(info_hash=info_hash))
        else:
            console.print(
                f"[yellow]Checkpoint for {info_hash} is missing or invalid[/yellow]",
            )
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("export")
@click.argument("info_hash")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["json", "binary"]),
    default="json",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    required=True,
    help=_("Output file path"),
)
@click.pass_context
def export_checkpoint_cmd(ctx, info_hash, format_, output_path):
    """Export a checkpoint to a file in the given format."""
    console = Console()
    try:
        config_manager = ConfigManager(ctx.obj["config"])
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config_manager.config.disk)
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)
        data = asyncio.run(
            checkpoint_manager.export_checkpoint(info_hash_bytes, fmt=format_),
        )
        Path(output_path).write_bytes(data)
        console.print(
            _("[green]Exported checkpoint to {path}[/green]").format(path=output_path)
        )
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("backup")
@click.argument("info_hash")
@click.option(
    "--destination",
    "destination",
    type=click.Path(),
    required=True,
    help=_("Backup destination path"),
)
@click.option(
    "--compress",
    is_flag=True,
    default=True,
    help=_("Compress backup (default: yes)"),
)
@click.option("--encrypt", is_flag=True, help=_("Encrypt backup with generated key"))
@click.pass_context
def backup_checkpoint_cmd(ctx, info_hash, destination, compress, encrypt):
    """Backup a checkpoint to a destination path."""
    console = Console()
    try:
        config_manager = ConfigManager(ctx.obj["config"])
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config_manager.config.disk)
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)
        dest_path = Path(destination)
        final_path = asyncio.run(
            checkpoint_manager.backup_checkpoint(
                info_hash_bytes,
                dest_path,
                compress=compress,
                encrypt=encrypt,
            ),
        )
        console.print(
            _("[green]Backup created: {path}[/green]").format(path=final_path)
        )
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
@click.option(
    "--info-hash",
    "info_hash",
    type=str,
    default=None,
    help=_("Expected info hash (hex)"),
)
@click.pass_context
def restore_checkpoint_cmd(ctx, backup_file, info_hash):
    """Restore a checkpoint from a backup file."""
    console = Console()
    try:
        config_manager = ConfigManager(ctx.obj["config"])
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config_manager.config.disk)
        ih_bytes = None
        if info_hash:
            try:
                ih_bytes = bytes.fromhex(info_hash)
            except ValueError:
                console.print(
                    _("[red]Invalid info hash format: {hash}[/red]").format(
                        hash=info_hash
                    )
                )
                msg = "Command failed"
                _raise_cli_error(msg)
        cp = asyncio.run(
            checkpoint_manager.restore_checkpoint(
                Path(backup_file),
                info_hash=ih_bytes,
            ),
        )
        console.print(
            f"[green]Restored checkpoint for: {cp.torrent_name}[/green]\nInfo hash: {cp.info_hash.hex()}",
        )
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("migrate")
@click.argument("info_hash")
@click.option("--from-format", type=click.Choice(["json", "binary"]))
@click.option("--to-format", type=click.Choice(["json", "binary", "both"]))
@click.pass_context
def migrate_checkpoint_cmd(ctx, info_hash, from_format, to_format):
    """Migrate a checkpoint between formats."""
    console = Console()
    try:
        config_manager = ConfigManager(ctx.obj["config"])
        from ccbt.models import CheckpointFormat
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config_manager.config.disk)
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)
        src = CheckpointFormat[from_format.upper()]
        dst = CheckpointFormat[to_format.upper()]
        new_path = asyncio.run(
            checkpoint_manager.convert_checkpoint_format(info_hash_bytes, src, dst),
        )
        console.print(
            _("[green]Migrated checkpoint to {path}[/green]").format(path=new_path)
        )
    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("reload")
@click.argument("info_hash")
@click.option(
    "--peers/--no-peers",
    default=True,
    help=_("Reconnect to peers from checkpoint"),
)
@click.option(
    "--trackers/--no-trackers",
    default=True,
    help=_("Refresh tracker state from checkpoint"),
)
@click.pass_context
def checkpoint_reload(ctx, info_hash, peers, trackers):
    """Quick reload checkpoint for a torrent (incremental reload)."""
    console = Console()

    try:
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon executor
            from ccbt.executor.session_adapter import get_executor

            async def _reload_via_daemon() -> None:
                executor, _ = await get_executor()
                if not executor:
                    raise click.ClickException(
                        _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
                    )

                try:
                    result = await executor.execute(
                        "checkpoint.reload",
                        info_hash=info_hash,
                        reload_peers=peers,
                        reload_trackers=trackers,
                    )
                    if not result.success:
                        raise click.ClickException(result.error or _("Failed to reload checkpoint"))
                    console.print(
                        _("[green]Checkpoint reloaded for {hash}[/green]").format(hash=info_hash)
                    )
                finally:
                    if hasattr(executor.adapter, "ipc_client"):
                        await executor.adapter.ipc_client.close()

            asyncio.run(_reload_via_daemon())
        else:
            # Use local session
            from ccbt.session.session import AsyncSessionManager
            from ccbt.session.checkpoint_operations import CheckpointOperations

            session = AsyncSessionManager(".")
            checkpoint_ops = CheckpointOperations(session)

            try:
                info_hash_bytes = bytes.fromhex(info_hash)
            except ValueError:
                console.print(
                    _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
                )
                raise click.ClickException(_("Invalid info hash format"))

            success = asyncio.run(
                checkpoint_ops.quick_reload(info_hash_bytes)
            )

            if success:
                console.print(
                    _("[green]Checkpoint reloaded for {hash}[/green]").format(hash=info_hash)
                )
            else:
                console.print(
                    _("[yellow]Failed to reload checkpoint for {hash}[/yellow]").format(hash=info_hash)
                )
                raise click.ClickException(_("Failed to reload checkpoint"))

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@checkpoints.command("refresh")
@click.argument("info_hash")
@click.option(
    "--peers/--no-peers",
    default=True,
    help=_("Reconnect to peers from checkpoint"),
)
@click.option(
    "--trackers/--no-trackers",
    default=True,
    help=_("Refresh tracker state from checkpoint"),
)
@click.pass_context
def checkpoint_refresh(ctx, info_hash, peers, trackers):
    """Refresh checkpoint state without full restart."""
    console = Console()

    try:
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon executor
            from ccbt.executor.session_adapter import get_executor

            async def _refresh_via_daemon() -> None:
                executor, _ = await get_executor()
                if not executor:
                    raise click.ClickException(
                        _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
                    )

                try:
                    result = await executor.execute(
                        "checkpoint.refresh",
                        info_hash=info_hash,
                        reload_peers=peers,
                        reload_trackers=trackers,
                    )
                    if not result.success:
                        raise click.ClickException(result.error or _("Failed to refresh checkpoint"))
                    console.print(
                        _("[green]Checkpoint refreshed for {hash}[/green]").format(hash=info_hash)
                    )
                finally:
                    if hasattr(executor.adapter, "ipc_client"):
                        await executor.adapter.ipc_client.close()

            asyncio.run(_refresh_via_daemon())
        else:
            # Use local session
            from ccbt.session.session import AsyncSessionManager
            from ccbt.session.checkpoint_operations import CheckpointOperations

            session = AsyncSessionManager(".")
            checkpoint_ops = CheckpointOperations(session)

            try:
                info_hash_bytes = bytes.fromhex(info_hash)
            except ValueError:
                console.print(
                    _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
                )
                raise click.ClickException(_("Invalid info hash format"))

            success = asyncio.run(
                checkpoint_ops.refresh_checkpoint(
                    info_hash_bytes,
                    reload_peers=peers,
                    reload_trackers=trackers,
                )
            )

            if success:
                console.print(
                    _("[green]Checkpoint refreshed for {hash}[/green]").format(hash=info_hash)
                )
            else:
                console.print(
                    _("[yellow]Failed to refresh checkpoint for {hash}[/yellow]").format(hash=info_hash)
                )
                raise click.ClickException(_("Failed to refresh checkpoint"))

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("info_hash")
@click.option("--output", "-o", type=click.Path(), help=_("Output directory"))
@click.option("--interactive", "-i", is_flag=True, help=_("Start interactive mode"))
@click.pass_context
def resume(ctx, info_hash, _output, interactive):
    """Resume download from checkpoint."""
    console = Console()

    try:
        # CRITICAL FIX: Check for daemon PID file BEFORE creating local session
        # If PID file exists, we MUST prevent local session to avoid port conflicts
        daemon_manager = DaemonManager()
        pid_file_exists = daemon_manager.pid_file.exists()

        if pid_file_exists:
            raise click.ClickException(DAEMON_RESUME_CONFLICT_MSG)

        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Create session (only when daemon is NOT running)
        session = AsyncSessionManager(".")

        # Convert hex string to bytes
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(
                _("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)

        # Load checkpoint
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config.disk)
        checkpoint = asyncio.run(checkpoint_manager.load_checkpoint(info_hash_bytes))

        if not checkpoint:
            console.print(
                _("[red]No checkpoint found for {hash}[/red]").format(hash=info_hash)
            )
            msg = "Command failed"
            _raise_cli_error(msg)

        console.print(
            _("[green]Found checkpoint for: {torrent_name}[/green]").format(
                torrent_name=getattr(checkpoint, "torrent_name", "Unknown")
            )
        )
        console.print(
            _("[blue]Progress: {verified}/{total} pieces verified[/blue]").format(
                verified=len(getattr(checkpoint, 'verified_pieces', [])),
                total=getattr(checkpoint, 'total_pieces', 0)
            ),
        )

        # Check if checkpoint can be auto-resumed
        can_auto_resume = bool(
            getattr(checkpoint, "torrent_file_path", None)
            or getattr(checkpoint, "magnet_uri", None)
        )

        if not can_auto_resume:
            console.print(
                _("[yellow]Checkpoint cannot be auto-resumed - no torrent source found[/yellow]"),
            )
            console.print(
                _("[yellow]Please provide the original torrent file or magnet link[/yellow]"),
            )
            msg = _("Cannot auto-resume checkpoint")
            _raise_cli_error(msg)

        # Start session manager and resume
        asyncio.run(
            resume_download(session, info_hash_bytes, checkpoint, interactive, console),
        )

    except Exception as e:
        console.print(_("[red]Error: {error}[/red]").format(error=e))
        raise click.ClickException(str(e)) from e


async def resume_download(
    session: AsyncSessionManager,
    info_hash_bytes: bytes,
    checkpoint,
    interactive: bool,
    console: Console,
) -> None:
    """Async helper for resume command."""
    try:
        await session.start()

        # Attempt to resume from checkpoint
        console.print(_("[green]Resuming download from checkpoint...[/green]"))
        resumed_info_hash = await session.resume_from_checkpoint(
            info_hash_bytes,
            checkpoint,
        )

        console.print(
            _("[green]Successfully resumed download: {resumed_info_hash}[/green]").format(
                resumed_info_hash=resumed_info_hash
            ),
        )

        if interactive:
            # Start interactive mode
            from ccbt.executor import LocalSessionAdapter, UnifiedCommandExecutor

            adapter = LocalSessionAdapter(session)
            executor = UnifiedCommandExecutor(adapter)
            interactive_cli = InteractiveCLI(
                executor, adapter, console, session=session
            )
            await interactive_cli.run()
        else:
            # Monitor progress
            progress_manager = ProgressManager(console)

            with progress_manager.create_progress() as progress:
                task = progress.add_task(
                    f"Resuming {checkpoint.torrent_name}",
                    total=100,
                )

                # Monitor until completion
                while True:
                    torrent_status = await session.get_torrent_status(resumed_info_hash)
                    if not torrent_status:
                        console.print(_("[yellow]Torrent session ended[/yellow]"))
                        break

                    progress.update(
                        task,
                        completed=torrent_status.get("progress", 0) * 100,
                    )

                    if torrent_status.get("status") == "seeding":
                        console.print(
                            _("[green]Download completed: {name}[/green]").format(name=checkpoint.torrent_name),
                        )
                        break

                    await asyncio.sleep(1)

    except ValueError as e:
        console.print(_("[red]Validation error: {e}[/red]").format(e=e))
        msg = "Resume failed due to validation error"
        raise click.ClickException(msg) from e
    except FileNotFoundError as e:
        console.print(_("[red]File not found: {e}[/red]").format(e=e))
        msg = "Resume failed - torrent file not found"
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(_("[red]Unexpected error during resume: {e}[/red]").format(e=e))
        msg = "Resume failed due to unexpected error"
        raise click.ClickException(msg) from e
    finally:
        try:
            await session.stop()
        except Exception as e:
            console.print(
                _("[yellow]Warning: Error stopping session: {error}[/yellow]").format(
                    error=e
                )
            )


async def start_monitoring(_session: AsyncSessionManager, console: Console) -> None:
    """Start monitoring components."""
    # Initialize monitoring
    metrics_collector = MetricsCollector()
    AlertManager()
    TracingManager()
    DashboardManager()

    # Start monitoring
    asyncio.run(metrics_collector.start())

    console.print(_("[green]Monitoring started[/green]"))


async def start_interactive_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
) -> None:
    """Start interactive download."""
    from ccbt.executor import LocalSessionAdapter, UnifiedCommandExecutor

    # Create local executor for interactive download
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)
    interactive_cli = InteractiveCLI(executor, adapter, console, session=session)
    await interactive_cli.download_torrent(torrent_data, resume=resume)


async def start_basic_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
) -> None:
    """Start basic download with progress bar."""
    from ccbt.executor.executor import UnifiedCommandExecutor
    from ccbt.executor.session_adapter import LocalSessionAdapter

    # Create executor with local adapter
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)

    progress_manager = ProgressManager(console)

    with progress_manager.create_progress() as progress:
        torrent_name = (
            torrent_data.get("name", "Unknown")
            if isinstance(torrent_data, dict)
            else getattr(torrent_data, "name", "Unknown")
        )
        task = progress.add_task(f"Downloading {torrent_name}", total=100)

        # Add torrent using executor
        # For torrent data dict, we need to save it to a temp file or pass it differently
        # For now, use session.add_torrent directly since executor expects path or magnet
        if isinstance(torrent_data, dict) and "path" in torrent_data:
            # Use executor for file path
            torrent_path = torrent_data["path"]
            result = await executor.execute(
                "torrent.add",
                path_or_magnet=str(torrent_path),
                output_dir=torrent_data.get("download_path"),
                resume=resume,
            )
            if not result.success:
                raise RuntimeError(result.error or "Failed to add torrent")
            info_hash_hex = result.data["info_hash"]
        else:
            # Fallback to session method for dict data (not a file path)
            info_hash_hex = await session.add_torrent(torrent_data, resume=resume)

        # Monitor progress using executor
        while True:
            result = await executor.execute("torrent.status", info_hash=info_hash_hex)
            if not result.success or not result.data.get("status"):
                break

            torrent_status = result.data["status"]
            progress_val = (
                getattr(torrent_status, "progress", 0.0)
                if hasattr(torrent_status, "progress")
                else torrent_status.get("progress", 0.0)
                if isinstance(torrent_status, dict)
                else 0.0
            )
            status_str = (
                getattr(torrent_status, "status", "unknown")
                if hasattr(torrent_status, "status")
                else torrent_status.get("status", "unknown")
                if isinstance(torrent_status, dict)
                else "unknown"
            )

            progress.update(task, completed=progress_val * 100)

            if status_str == "seeding":
                console.print(
                    _("[green]Download completed: {name}[/green]").format(
                        name=torrent_name
                    )
                )
                break

            await asyncio.sleep(1)


def show_config(config, console: Console) -> None:
    """Show configuration."""
    # Create config table
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Add config rows
    table.add_row("Listen Port", str(config.network.listen_port))
    table.add_row("Max Peers", str(config.network.max_global_peers))
    table.add_row("Download Path", str(config.disk.download_path))
    table.add_row("Log Level", config.observability.log_level.value)
    table.add_row(
        "Metrics",
        "Enabled" if config.observability.enable_metrics else "Disabled",
    )

    console.print(table)


async def start_debug_mode(_session: AsyncSessionManager, console: Console) -> None:
    """Start debug mode."""
    console.print(_("[yellow]Debug mode not yet implemented[/yellow]"))


# Register external command groups at import time so they appear in --help
# Make tonic_commands optional since it requires cryptography
try:
    from ccbt.cli.tonic_commands import tonic as tonic_group
except ImportError:
    tonic_group = None  # type: ignore[assignment, misc]

from ccbt.cli.queue_commands import queue as queue_group
from ccbt.cli.torrent_commands import global_controls as global_controls_group
from ccbt.cli.torrent_commands import torrent as torrent_control_group
from ccbt.cli.torrent_commands import peer as peer_group
from ccbt.cli.torrent_commands import pex as pex_group
from ccbt.cli.torrent_commands import dht as dht_group
from ccbt.cli.file_commands import files as files_group

cli.add_command(config_group)
cli.add_command(config_extended)
cli.add_command(daemon_group)
cli.add_command(torrent_group)
cli.add_command(torrent_control_group)
cli.add_command(global_controls_group)
cli.add_command(peer_group)
cli.add_command(pex_group)
cli.add_command(dht_group)
cli.add_command(queue_group)
cli.add_command(files_group)
cli.add_command(dashboard_cmd)
cli.add_command(alerts_cmd)
cli.add_command(metrics_cmd)
cli.add_command(performance_cmd)
cli.add_command(security_cmd)
cli.add_command(recover_cmd)
cli.add_command(test_cmd)
if tonic_group is not None:
    cli.add_command(tonic_group)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()