"""Daemon management commands for CLI.

Provides `btbt daemon start` and `btbt daemon exit` commands for daemon management.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
import time
import warnings
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ccbt.config.config import get_config, init_config
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
from ccbt.daemon.utils import generate_api_key
from ccbt.i18n import _
from ccbt.models import DaemonConfig
from ccbt.utils.logging_config import get_logger, log_info_normal

logger = get_logger(__name__)
console = Console()

# CRITICAL FIX: Suppress Windows ProactorEventLoop cleanup warnings
# This is a known Python bug (https://bugs.python.org/issue39232) where
# ProactorEventLoop cleanup raises AttributeError for _ssock during __del__
# The error occurs during garbage collection and doesn't affect functionality
if sys.platform == "win32":
    # Suppress RuntimeWarning about unawaited coroutines (Windows cleanup issue)
    warnings.filterwarnings(
        "ignore",
        category=RuntimeWarning,
        message=".*coroutine.*was never awaited.*",
    )
    # Suppress AttributeError during ProactorEventLoop cleanup
    # We can't catch this in try/except since it happens in __del__ during GC
    # So we install a custom excepthook to filter it
    _original_excepthook = sys.excepthook

    def _filter_proactor_cleanup_error(exc_type, exc_value, exc_traceback):
        """Filter out known Windows ProactorEventLoop cleanup errors.

        This filters the specific AttributeError that occurs during ProactorEventLoop
        garbage collection cleanup on Windows. This is a known Python bug that doesn't
        affect functionality - it's just a cleanup issue.
        """
        # Only filter AttributeError with _ssock (the known bug signature)
        if exc_type is AttributeError and "_ssock" in str(exc_value) and exc_traceback:
            # Check if this is the ProactorEventLoop cleanup bug
            # The error occurs in __del__ during garbage collection
                try:
                    import traceback

                    tb_lines = traceback.format_exception(
                        exc_type, exc_value, exc_traceback
                    )
                    tb_str = "".join(tb_lines)
                    # Very specific check: must be ProactorEventLoop.__del__ trying to access _ssock
                    if (
                        "ProactorEventLoop" in tb_str
                        and "__del__" in tb_str
                        and "_close_self_pipe" in tb_str
                    ):
                        # This is the known cleanup bug - silently ignore it
                        return
                except Exception:
                    # If we can't parse the traceback, don't filter (be safe)
                    pass
        # Call original excepthook for all other exceptions
        _original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _filter_proactor_cleanup_error


@click.group()
def daemon():
    """Daemon management commands."""


@daemon.command("start")
@click.option(
    "--foreground",
    "-f",
    is_flag=True,
    help=_("Run in foreground (for debugging)"),
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help=_("Path to config file"),
)
@click.option(
    "--port",
    type=int,
    help=_("Override IPC server port"),
)
@click.option(
    "--generate-api-key",
    "regenerate_api_key",
    is_flag=True,
    help=_("Generate new API key"),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=_("Increase verbosity (-v: verbose, -vv: debug, -vvv: trace)"),
)
@click.option(
    "--vv",
    is_flag=True,
    help=_("Enable debug verbosity (equivalent to -vv)"),
)
@click.option(
    "--vvv",
    is_flag=True,
    help=_("Enable trace verbosity (equivalent to -vvv)"),
)
@click.option(
    "--no-wait",
    "--background-only",
    is_flag=True,
    help=_("Start daemon in background without waiting for completion (faster startup)"),
)
@click.option(
    "--no-splash",
    "-d",
    is_flag=True,
    help=_("Disable splash screen (useful for debugging)"),
)
def start(
    foreground: bool,
    config: str | None,
    port: int | None,
    regenerate_api_key: bool,
    verbose: int,
    vv: bool,
    vvv: bool,
    no_wait: bool,
    no_splash: bool,
) -> None:
    """Start the daemon process."""
    from ccbt.cli.verbosity import VerbosityManager

    # Combine -v count with --vv and --vvv flags
    if vvv:
        verbose = max(verbose, 3)  # --vvv is equivalent to -vvv
    elif vv:
        verbose = max(verbose, 2)  # --vv is equivalent to -vv

    start_time = time.time()
    verbosity = VerbosityManager.from_count(verbose)

    # Initialize config
    if verbosity.is_verbose():
        console.print(_("[cyan]Initializing configuration...[/cyan]"))
    config_manager = init_config(config)
    cfg = config_manager.config

    # Ensure daemon config exists
    daemon_config_created = False
    if not cfg.daemon:
        # Create default daemon config
        api_key = generate_api_key()
        cfg.daemon = DaemonConfig(api_key=api_key)
        daemon_config_created = True
        if verbosity.is_verbose():
            console.print(_("[green]✓[/green] Generated new API key for daemon"))
        # LOGGING OPTIMIZATION: Use verbosity-aware logging - important operation
        log_info_normal(logger, verbosity, _("Generated new API key for daemon"))
    elif regenerate_api_key or not cfg.daemon.api_key:
        # Generate new API key
        api_key = generate_api_key()
        cfg.daemon.api_key = api_key
        daemon_config_created = True
        if verbosity.is_verbose():
            console.print(_("[green]✓[/green] Generated new API key for daemon"))
        # LOGGING OPTIMIZATION: Use verbosity-aware logging - important operation
        log_info_normal(logger, verbosity, _("Generated new API key for daemon"))

    # Override port if specified
    if port:
        cfg.daemon.ipc_port = port
        if verbosity.is_verbose():
            console.print(_("[cyan]Using custom IPC port: {port}[/cyan]").format(port=port))

    # Save config if daemon config was created or modified
    # This ensures DaemonMain can read the config when it initializes
    if cfg.daemon and (
        daemon_config_created
        or regenerate_api_key
        or not cfg.daemon.api_key
        or port is not None
    ):
        try:
            if config_manager.config_file:
                # Reload and update config file
                import toml

                config_data = {}
                if config_manager.config_file.exists():
                    with open(config_manager.config_file, encoding="utf-8") as f:
                        config_data = toml.load(f)

                # Update daemon config
                if "daemon" not in config_data:
                    config_data["daemon"] = {}
                if cfg.daemon.api_key:
                    config_data["daemon"]["api_key"] = cfg.daemon.api_key
                if port:
                    config_data["daemon"]["ipc_port"] = port
                # Save other daemon config fields if they exist
                if hasattr(cfg.daemon, "state_dir") and cfg.daemon.state_dir:
                    config_data["daemon"]["state_dir"] = str(cfg.daemon.state_dir)

                # Write back
                with open(config_manager.config_file, "w", encoding="utf-8") as f:
                    toml.dump(config_data, f)

                if verbosity.is_verbose():
                    console.print(
                        _("[green]✓[/green] Updated config file: {file}").format(file=config_manager.config_file)
                    )
                # LOGGING OPTIMIZATION: Use verbosity-aware logging - important operation
                log_info_normal(logger, verbosity, _("Updated config file with daemon configuration"))
        except Exception as e:
            if verbosity.is_verbose():
                console.print(
                    _("[yellow]⚠[/yellow] Could not save daemon config to config file: {e}").format(e=e)
                )
            logger.warning(_("Could not save daemon config to config file: %s"), e)

    # Check if daemon is already running
    if verbosity.is_verbose():
        console.print(_("[cyan]Checking for existing daemon instance...[/cyan]"))
    daemon_manager = DaemonManager()
    if not daemon_manager.ensure_single_instance():
        pid = daemon_manager.get_pid()
        console.print(
            _("[red]✗[/red] Daemon is already running with PID {pid}").format(pid=pid), style="red"
        )
        raise click.Abort

    if foreground:
        # Run in foreground
        if verbosity.is_verbose():
            console.print(_("[cyan]Starting daemon in foreground mode...[/cyan]"))
        console.print(_("Press Ctrl+C to stop the daemon"))

        # Show splash screen for foreground mode (allow with -v and -vv, but hide with -vvv or higher)
        splash_manager = None
        splash_thread = None
        expected_duration = 60.0  # Default duration, will be overridden if detector available
        if verbosity.verbosity_count <= 2 and not no_splash:  # Allow with -v and -vv, hide with -vvv+
            from ccbt.interface.splash.splash_manager import SplashManager
            from ccbt.cli.task_detector import get_detector
            import threading
            
            detector = get_detector()
            if detector.should_show_splash("daemon.start"):
                splash_manager = SplashManager.from_verbosity_count(verbose, console=console)
                expected_duration = detector.get_expected_duration("daemon.start")
                # Update splash message to indicate daemon is starting
                try:
                    splash_manager.update_progress_message("Starting daemon process...")
                except Exception:
                    pass  # Ignore errors updating splash
                # Start splash screen in background thread
                def run_splash():
                    asyncio.run(
                        splash_manager.show_splash_for_task(
                            task_name="daemon start",
                            max_duration=expected_duration,
                            show_progress=True,
                        )
                    )
                splash_thread = threading.Thread(target=run_splash, daemon=True)
                splash_thread.start()

        daemon_main_ref: Any = None

        async def _run_foreground() -> None:
            """Run daemon in foreground."""
            from ccbt.daemon.main import DaemonMain

            nonlocal daemon_main_ref
            daemon_main = DaemonMain(
                config_file=config,
                foreground=True,
            )
            daemon_main_ref = daemon_main
            
            # Signal handlers are set up in daemon_main.start() via daemon_manager
            # The signal handler will set _shutdown_event, which run() checks in its loop
            # The run() method catches KeyboardInterrupt and calls stop() in its finally block
            await daemon_main.run()

        try:
            # CRITICAL FIX: Use asyncio.run() - it properly handles KeyboardInterrupt
            # The daemon's run() method also catches KeyboardInterrupt and ensures cleanup
            # On Windows, asyncio.run() should properly propagate KeyboardInterrupt
            asyncio.run(_run_foreground())
            console.print(_("[green]Daemon stopped[/green]"))
        except KeyboardInterrupt:
            # KeyboardInterrupt caught by asyncio.run()
            # The daemon's run() method should have already handled cleanup in its KeyboardInterrupt handler
            console.print(_("\n[yellow]Shutting down daemon...[/yellow]"))
            # Ensure shutdown event is set if it wasn't already
            if daemon_main_ref is not None:
                if daemon_main_ref._shutdown_event and not daemon_main_ref._shutdown_event.is_set():
                    daemon_main_ref._shutdown_event.set()
                    logger.debug("Shutdown event set from CLI KeyboardInterrupt handler")
                
                # CRITICAL FIX: If stop() wasn't called yet (event loop was cancelled before handler ran),
                # try to ensure shutdown completes in a new event loop
                if not daemon_main_ref._stopping:
                    try:
                        async def _ensure_shutdown() -> None:
                            """Ensure daemon shutdown completes."""
                            try:
                                # Use timeout to prevent hanging
                                await asyncio.wait_for(daemon_main_ref.stop(), timeout=10.0)
                            except asyncio.TimeoutError:
                                logger.warning("Shutdown timeout - forcing cleanup")
                                # At least try to remove PID file
                                try:
                                    daemon_main_ref.daemon_manager.remove_pid()
                                except Exception:
                                    pass
                            except Exception as e:
                                logger.warning("Error ensuring shutdown: %s", e)
                                # At least try to remove PID file
                                try:
                                    daemon_main_ref.daemon_manager.remove_pid()
                                except Exception:
                                    pass
                        
                        # Run in a new event loop to ensure shutdown completes
                        asyncio.run(_ensure_shutdown())
                    except Exception as e:
                        logger.warning("Could not ensure shutdown completion: %s", e)
                        # Last resort: try to remove PID file directly
                        try:
                            if daemon_main_ref.daemon_manager:
                                daemon_main_ref.daemon_manager.remove_pid()
                        except Exception:
                            pass
            
            console.print(_("[green]Daemon stopped[/green]"))
    else:
        # Start daemon in background
        if verbosity.is_verbose():
            console.print(_("[cyan]Starting daemon in background...[/cyan]"))

        # Show splash screen (allow with -v and -vv, but hide with -vvv or higher)
        # Start splash screen just before daemon process actually starts
        splash_manager = None
        splash_thread = None
        expected_duration = 60.0  # Default duration, will be overridden if detector available
        if verbosity.verbosity_count <= 2 and not no_splash:  # Allow with -v and -vv, hide with -vvv+
            from ccbt.interface.splash.splash_manager import SplashManager
            from ccbt.cli.task_detector import get_detector
            import threading
            
            detector = get_detector()
            if detector.should_show_splash("daemon.start"):
                splash_manager = SplashManager.from_verbosity_count(verbose, console=console)
                expected_duration = detector.get_expected_duration("daemon.start")
                # Update splash message to indicate daemon is starting
                try:
                    splash_manager.update_progress_message("Starting daemon process...")
                except Exception:
                    pass  # Ignore errors updating splash
                # Start splash screen in background thread
                def run_splash():
                    asyncio.run(
                        splash_manager.show_splash_for_task(
                            task_name="daemon start",
                            max_duration=expected_duration,
                            show_progress=True,
                        )
                    )
                splash_thread = threading.Thread(target=run_splash, daemon=True)
                splash_thread.start()

        try:
            pid = daemon_manager.start(foreground=False)

            # Give the process a moment to initialize before checking
            time.sleep(0.2)

            # Check if process is still alive immediately after start
            import os

            try:
                os.kill(pid, 0)  # Check if process exists
            except (OSError, ProcessLookupError, Exception):
                # Process died immediately
                console.print(
                    _("[red]✗[/red] Daemon process (PID {pid}) exited immediately after starting").format(pid=pid)
                )
                console.print(
                    _("[yellow]The daemon process crashed during initialization.[/yellow]")
                )
                if verbosity.is_verbose():
                    console.print(
                        _("[yellow]This usually indicates a configuration error, missing dependency, or initialization failure.[/yellow]")
                    )
                    console.print(
                        _("[dim]Try running with --foreground flag to see detailed error output:[/dim]")
                    )
                    console.print(_("[dim]  uv run btbt daemon start --foreground[/dim]"))
                else:
                    console.print(
                        _("[yellow]Use -v flag for more details or try --foreground to see error output[/yellow]")
                    )
                raise click.Abort from None

            # Small delay to ensure PID file is written and process is starting
            time.sleep(0.3)

            # Wait for daemon to be ready (unless --no-wait flag is set)
            if not no_wait:
                # Update splash message to indicate initialization
                if splash_manager:
                    try:
                        splash_manager.update_progress_message("Initializing daemon components...")
                    except Exception:
                        pass  # Ignore errors updating splash
                
                if verbosity.is_verbose():
                    console.print(_("[cyan]Waiting for daemon to be ready...[/cyan]"))
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TimeElapsedColumn(),
                        console=console,
                    ) as progress:
                        task = progress.add_task("Starting daemon...", total=None)
                        daemon_ready = _wait_for_daemon_with_progress(
                            cfg.daemon,
                            timeout=expected_duration,
                            progress=progress,
                            task=task,
                            verbosity=verbosity,
                            daemon_pid=pid,
                            splash_manager=splash_manager,
                        )
                else:
                    daemon_ready = _wait_for_daemon(cfg.daemon, timeout=expected_duration, splash_manager=splash_manager)

                if daemon_ready:
                    elapsed = time.time() - start_time
                    # Update splash screen message to indicate initialization complete
                    if splash_manager:
                        try:
                            splash_manager.update_progress_message("Daemon initialization complete!")
                        except Exception:
                            pass  # Ignore errors updating splash
                    # Small additional delay to ensure "Daemon initialization complete" message has been logged
                    time.sleep(0.5)
                    console.print(
                        _("[green]✓[/green] Daemon started successfully (PID {pid}, took {elapsed:.1f}s)").format(pid=pid, elapsed=elapsed)
                    )
                    # Clear splash screen only after daemon initialization is fully complete
                    if splash_manager:
                        try:
                            splash_manager.clear_progress_messages()
                        except Exception:
                            pass  # Ignore errors clearing splash
                else:
                    console.print(
                        _("[yellow]⚠[/yellow] Daemon process started (PID {pid}) but may not be fully ready yet").format(pid=pid)
                    )
                    console.print(
                        _("[dim]Use 'btbt daemon status' to check daemon status[/dim]")
                    )
            else:
                console.print(_("[green]✓[/green] Daemon process started (PID {pid})").format(pid=pid))
                console.print(
                    _("[dim]Use 'btbt daemon status' to check daemon status[/dim]")
                )

        except RuntimeError as e:
            console.print(_("[red]✗[/red] Failed to start daemon: {e}").format(e=e))
            raise click.Abort from e


async def _run_daemon_foreground(
    daemon_config: DaemonConfig, config_file: str | None
) -> None:
    """Run daemon in foreground mode."""
    from ccbt.daemon.main import DaemonMain

    daemon = DaemonMain(
        config_file=config_file,
        foreground=True,
    )

    await daemon.run()


def _wait_for_daemon(daemon_config: DaemonConfig, timeout: float = 15.0, splash_manager: Any | None = None) -> bool:
    """Wait for daemon to be ready.

    Args:
        daemon_config: Daemon configuration
        timeout: Timeout in seconds
        splash_manager: Optional splash manager for progress updates

    Returns:
        True if daemon is ready, False otherwise

    """

    async def _check_daemon_loop() -> bool:
        """Check if daemon is running in a loop."""
        start_time = time.time()
        last_stage = ""

        while time.time() - start_time < timeout:
            client = IPCClient(api_key=daemon_config.api_key)
            try:
                is_running = await client.is_daemon_running()
                if is_running:
                    # Update splash to indicate waiting for full initialization
                    if splash_manager and last_stage != "waiting":
                        try:
                            splash_manager.update_progress_message("Waiting for daemon to be ready...")
                            last_stage = "waiting"
                        except Exception:
                            pass
                    # Small delay to ensure daemon has fully initialized (including "Daemon initialization complete" message)
                    await asyncio.sleep(1.0)
                    return True
            except Exception:
                pass
            finally:
                await client.close()

            # Update splash message during wait
            if splash_manager and last_stage != "checking":
                try:
                    splash_manager.update_progress_message("Checking daemon status...")
                    last_stage = "checking"
                except Exception:
                    pass

            # Wait before next check
            await asyncio.sleep(0.5)

        return False

    try:
        # Use asyncio.run() to create a new event loop
        # Windows ProactorEventLoop cleanup warnings are handled at module level
        return asyncio.run(_check_daemon_loop())
    except Exception as e:
        logger.debug(_("Error waiting for daemon: %s"), e)
        return False


def _wait_for_daemon_with_progress(
    daemon_config: DaemonConfig,
    timeout: float = 15.0,
    progress: Progress | None = None,
    task: int | None = None,
    verbosity: Any | None = None,
    daemon_pid: int | None = None,
    splash_manager: Any | None = None,
) -> bool:
    """Wait for daemon to be ready with progress indicator.

    Args:
        daemon_config: Daemon configuration
        timeout: Timeout in seconds
        progress: Rich Progress object (optional)
        task: Task ID for progress (optional)
        verbose: Enable verbose output
        daemon_pid: Daemon PID to monitor

    Returns:
        True if daemon is ready, False otherwise

    """
    init_stages = [
        "Starting daemon process...",
        "Waiting for process to initialize...",
        "Checking IPC server...",
        "Verifying daemon status...",
        "Daemon ready!",
    ]

    async def _check_daemon_stage() -> tuple[bool, int, str]:
        """Check daemon readiness stage.

        Returns:
            Tuple of (is_ready, stage_index, stage_description)

        """
        # Check if process is running
        daemon_manager = DaemonManager()
        is_running = False
        with contextlib.suppress(Exception):
            is_running = daemon_manager.is_running()

        if not is_running:
            return False, 1, init_stages[1]

        # Try to connect to IPC server
        client = IPCClient(api_key=daemon_config.api_key)
        try:
            is_accessible = await asyncio.wait_for(
                client.is_daemon_running(), timeout=1.5
            )

            if not is_accessible:
                return False, 2, init_stages[2]  # "Process starting..."

            # IPC server is accessible - session manager and IPC server are started
            # Try to get detailed status to confirm full readiness
            try:
                status = await asyncio.wait_for(client.get_status(), timeout=1.5)
                # If we can get status with valid data, daemon is fully ready
                if status.status and status.uptime >= 0:
                    return True, len(init_stages) - 1, init_stages[-1]
                # Status endpoint exists but not fully initialized
                return False, 3, init_stages[3]  # "Starting IPC server..."
            except (ConnectionError, TimeoutError, asyncio.TimeoutError):
                # IPC server accessible but status endpoint not ready - IPC server still starting
                return False, 3, init_stages[3]  # "Starting IPC server..."
            except Exception:
                # Status endpoint error - IPC server started but not fully ready
                return False, 3, init_stages[3]  # "Starting IPC server..."

        finally:
            await client.close()

    start_time = time.time()
    last_status = init_stages[0]
    # check_count = 0  # Reserved for future use
    stage_start_times: dict[int, float] = {}  # Track when each stage started
    last_detected_stage = -1

    # Track daemon PID to detect crashes
    # Use provided PID or try to get it from manager
    daemon_manager = DaemonManager()
    initial_pid = daemon_pid
    if initial_pid is None:
        # Fallback: try to get PID from file (may not exist yet)
        initial_pid = daemon_manager.get_pid()

    def _is_process_alive(pid: int | None) -> bool:
        """Check if process is actually running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise

        """
        if pid is None:
            return False
        try:
            import os

            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False
        except Exception:
            # Handle any other unexpected exceptions (Windows-specific issues)
            # On Windows, os.kill() might raise exceptions with "exception set" errors
            return False

    async def _wait_loop() -> bool:
        """Async loop to check daemon readiness."""
        nonlocal last_status, last_detected_stage

        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time

            # Check if daemon process is still running (detect crashes)
            # Only check if we have a valid PID
            if initial_pid is not None:
                is_alive = _is_process_alive(initial_pid)

                if not is_alive:
                    # Process crashed - process is dead
                    if progress and task is not None:
                        progress.update(
                            task, description=_("[red]Daemon process crashed[/red]")
                        )
                    if verbosity and verbosity.is_verbose():
                        console.print(
                            _("[red]✗[/red] Daemon process (PID {pid}) crashed during startup (after {elapsed:.1f}s)").format(
                                pid=initial_pid, elapsed=elapsed
                            )
                        )
                        console.print(
                            _("[yellow]The daemon process exited unexpectedly. Check daemon logs for error details.[/yellow]")
                        )
                    else:
                        console.print(
                            _("[red]✗[/red] Daemon process (PID {pid}) crashed during startup (after {elapsed:.1f}s)").format(
                                pid=initial_pid, elapsed=elapsed
                            )
                        )
                        console.print(
                            _("[yellow]The daemon process exited unexpectedly. Check daemon logs for error details.[/yellow]")
                        )
                        console.print(
                            _("[dim]Use -v flag for more details or check daemon logs[/dim]")
                        )
                    return False

            try:
                is_ready, stage_idx, stage_desc = await _check_daemon_stage()

                # Track stage transitions
                if stage_idx != last_detected_stage:
                    stage_start_times[stage_idx] = time.time()
                    last_detected_stage = stage_idx
                    # Update splash screen with stage description
                    if splash_manager:
                        try:
                            splash_manager.update_progress_message(stage_desc)
                        except Exception:
                            pass  # Ignore errors updating splash

                if progress and task is not None:
                    progress.update(task, description=stage_desc)

                last_status = stage_desc

                if is_ready:
                    # Update splash to indicate waiting for full initialization
                    if splash_manager:
                        try:
                            splash_manager.update_progress_message("Waiting for daemon initialization to complete...")
                        except Exception:
                            pass
                    # Small delay to ensure daemon has fully initialized (including "Daemon initialization complete" message)
                    await asyncio.sleep(1.0)
                    return True

            except Exception as e:
                if verbosity and verbosity.is_debug():
                    logger.debug(_("Error checking daemon stage: %s"), e)
                # Continue waiting

            # Brief sleep before next check
            await asyncio.sleep(0.3)

        # Timeout reached
        if progress and task is not None:
            progress.update(
                task,
                description=_("[yellow]Timeout waiting for daemon (last status: {last_status})[/yellow]").format(last_status=last_status),
            )

        if verbosity and verbosity.is_verbose():
            console.print(
                _("[yellow]⚠[/yellow] Daemon startup timeout after {timeout:.1f}s (last status: {last_status})").format(timeout=timeout, last_status=last_status)
            )
            console.print(
                _("[dim]Daemon may still be starting. Use 'btbt daemon status' to check.[/dim]")
            )

        return False

    try:
        # Use asyncio.run() to create a new event loop
        # Windows ProactorEventLoop cleanup warnings are handled at module level
        return asyncio.run(_wait_loop())
    except Exception as e:
        logger.debug(_("Error waiting for daemon with progress: %s"), e)
        return False


@daemon.command("exit")
@click.option(
    "--force",
    is_flag=True,
    help=_("Force kill without graceful shutdown"),
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help=_("Shutdown timeout in seconds"),
)
def exit_daemon(force: bool, timeout: float) -> None:
    """Stop the daemon process."""
    daemon_manager = DaemonManager()

    if not daemon_manager.is_running():
        click.echo(_("Daemon is not running"))
        return

    success = False

    if not force:
        # Try graceful shutdown via IPC
        try:
            cfg = get_config()

            if cfg.daemon and cfg.daemon.api_key:
                try:

                    async def _shutdown_daemon() -> bool:
                        """Send shutdown request to daemon."""
                        client = IPCClient(api_key=cfg.daemon.api_key)  # type: ignore[union-attr]
                        try:
                            return await client.shutdown()
                        finally:
                            await client.close()

                    if asyncio.run(_shutdown_daemon()):
                        click.echo(
                            "Shutdown request sent, waiting for daemon to stop..."
                        )
                        # Wait for process to exit with progress
                        start_time = time.time()
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            TimeElapsedColumn(),
                            console=console,
                        ) as progress:
                            task = progress.add_task(_("Stopping daemon..."), total=None)
                            while time.time() - start_time < timeout:
                                if not daemon_manager.is_running():
                                    progress.update(
                                        task, description=_("[green]Daemon stopped gracefully[/green]")
                                    )
                                    click.echo(_("Daemon stopped gracefully"))
                                    return
                                elapsed = time.time() - start_time
                                progress.update(
                                    task,
                                    description=_("Stopping daemon... ({elapsed:.1f}s)").format(elapsed=elapsed),
                                )
                                time.sleep(0.5)
                except Exception as e:
                    logger.debug(_("Error sending shutdown request: %s"), e)
                    click.echo(_("Could not send shutdown request, using signal..."))

            # Fallback to signal-based shutdown
            success = daemon_manager.stop(timeout=timeout, force=False)
        except Exception:
            # If IPC fails entirely, fall back to signal
            success = daemon_manager.stop(timeout=timeout, force=False)
    else:
        # Force kill
        success = daemon_manager.stop(timeout=timeout, force=True)

    if success:
        click.echo(_("Daemon stopped"))
    else:
        click.echo(_("Failed to stop daemon"), err=True)
        if not force:
            click.echo(_("Use --force to force kill"), err=True)
        raise click.Abort


@daemon.command("status")
def status() -> None:
    """Show daemon status."""
    daemon_manager = DaemonManager()

    if not daemon_manager.is_running():
        console.print(_("[red]Daemon is not running[/red]"))
        return

    pid = daemon_manager.get_pid()
    console.print(_("[green]Daemon is running[/green] (PID: {pid})").format(pid=pid))

    # Try to get detailed status via IPC
    try:
        cfg = get_config()

        if cfg.daemon and cfg.daemon.api_key:

            async def _get_status() -> None:
                """Get daemon status via IPC."""
                client = IPCClient(api_key=cfg.daemon.api_key)  # type: ignore[union-attr]
                try:
                    status = await client.get_status()
                    console.print(_("\n[cyan]Status:[/cyan] {status}").format(status=status.status))
                    console.print(_("[cyan]Torrents:[/cyan] {num_torrents}").format(num_torrents=status.num_torrents))
                    console.print(_("[cyan]Uptime:[/cyan] {uptime:.1f}s").format(uptime=status.uptime))
                    if hasattr(status, "download_rate"):
                        console.print(
                            _("[cyan]Download:[/cyan] {rate:.2f} KiB/s").format(rate=status.download_rate)
                        )
                    if hasattr(status, "upload_rate"):
                        console.print(
                            _("[cyan]Upload:[/cyan] {rate:.2f} KiB/s").format(rate=status.upload_rate)
                        )
                finally:
                    await client.close()

            asyncio.run(_get_status())
        else:
            console.print(
                _("[yellow]API key not found in config, cannot get detailed status[/yellow]")
            )
    except Exception as e:
        logger.debug(_("Error getting daemon status: %s"), e)
        console.print(_("[yellow]Could not get detailed status via IPC[/yellow]"))
