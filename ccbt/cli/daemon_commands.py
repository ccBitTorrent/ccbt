"""Daemon management commands for CLI.

Provides `btbt daemon start` and `btbt daemon exit` commands for daemon management.
"""

from __future__ import annotations

import asyncio
import sys
import time
import warnings

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ccbt.config.config import get_config, init_config
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
from ccbt.daemon.utils import generate_api_key
from ccbt.models import DaemonConfig
from ccbt.utils.logging_config import get_logger

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
        if exc_type == AttributeError and "_ssock" in str(exc_value):
            # Check if this is the ProactorEventLoop cleanup bug
            # The error occurs in __del__ during garbage collection
            if exc_traceback:
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
    help="Run in foreground (for debugging)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to config file",
)
@click.option(
    "--port",
    type=int,
    help="Override IPC server port",
)
@click.option(
    "--generate-api-key",
    "regenerate_api_key",
    is_flag=True,
    help="Generate new API key",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--no-wait",
    "--background-only",
    is_flag=True,
    help="Start daemon in background without waiting for completion (faster startup)",
)
def start(
    foreground: bool,
    config: str | None,
    port: int | None,
    regenerate_api_key: bool,
    verbose: bool,
    no_wait: bool,
) -> None:
    """Start the daemon process."""
    start_time = time.time()

    # Initialize config
    if verbose:
        console.print("[cyan]Initializing configuration...[/cyan]")
    config_manager = init_config(config)
    cfg = config_manager.config

    # Ensure daemon config exists
    daemon_config_created = False
    if not cfg.daemon:
        # Create default daemon config
        api_key = generate_api_key()
        cfg.daemon = DaemonConfig(api_key=api_key)
        daemon_config_created = True
        if verbose:
            console.print("[green]✓[/green] Generated new API key for daemon")
        logger.info("Generated new API key for daemon")
    elif regenerate_api_key or not cfg.daemon.api_key:
        # Generate new API key
        api_key = generate_api_key()
        cfg.daemon.api_key = api_key
        daemon_config_created = True
        if verbose:
            console.print("[green]✓[/green] Generated new API key for daemon")
        logger.info("Generated new API key for daemon")

    # Override port if specified
    if port:
        cfg.daemon.ipc_port = port
        if verbose:
            console.print(f"[cyan]Using custom IPC port: {port}[/cyan]")

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

                if verbose:
                    console.print(
                        f"[green]✓[/green] Updated config file: {config_manager.config_file}"
                    )
                logger.info("Updated config file with daemon configuration")
        except Exception as e:
            if verbose:
                console.print(
                    f"[yellow]⚠[/yellow] Could not save daemon config to config file: {e}"
                )
            logger.warning("Could not save daemon config to config file: %s", e)

    # Check if daemon is already running
    if verbose:
        console.print("[cyan]Checking for existing daemon instance...[/cyan]")
    daemon_manager = DaemonManager()
    if not daemon_manager.ensure_single_instance():
        pid = daemon_manager.get_pid()
        console.print(
            f"[red]✗[/red] Daemon is already running with PID {pid}", style="red"
        )
        raise click.Abort()

    if foreground:
        # Run in foreground
        if verbose:
            console.print("[cyan]Starting daemon in foreground mode...[/cyan]")
        console.print("Press Ctrl+C to stop the daemon")

        async def _run_foreground() -> None:
            """Run daemon in foreground."""
            from ccbt.daemon.main import DaemonMain

            daemon_main = DaemonMain(
                config_file=config,
                foreground=True,
            )
            await daemon_main.run()

        try:
            asyncio.run(_run_foreground())
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down daemon...[/yellow]")
    else:
        # Start daemon in background
        if verbose:
            console.print("[cyan]Starting daemon in background...[/cyan]")

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
                    f"[red]✗[/red] Daemon process (PID {pid}) exited immediately after starting"
                )
                console.print(
                    "[yellow]The daemon process crashed during initialization.[/yellow]"
                )
                if verbose:
                    console.print(
                        "[yellow]This usually indicates a configuration error, missing dependency, or initialization failure.[/yellow]"
                    )
                    console.print(
                        "[dim]Try running with --foreground flag to see detailed error output:[/dim]"
                    )
                    console.print("[dim]  uv run btbt daemon start --foreground[/dim]")
                else:
                    console.print(
                        "[yellow]Use -v flag for more details or try --foreground to see error output[/yellow]"
                    )
                raise click.Abort()

            # Small delay to ensure PID file is written and process is starting
            time.sleep(0.3)

            # Wait for daemon to be ready (unless --no-wait flag is set)
            if not no_wait:
                if verbose:
                    console.print("[cyan]Waiting for daemon to be ready...[/cyan]")
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TimeElapsedColumn(),
                        console=console,
                    ) as progress:
                        task = progress.add_task("Starting daemon...", total=None)
                        daemon_ready = _wait_for_daemon_with_progress(
                            cfg.daemon,
                            timeout=15.0,
                            progress=progress,
                            task=task,
                            verbose=verbose,
                            daemon_pid=pid,
                        )
                else:
                    daemon_ready = _wait_for_daemon(cfg.daemon, timeout=15.0)

                if daemon_ready:
                    elapsed = time.time() - start_time
                    console.print(
                        f"[green]✓[/green] Daemon started successfully (PID {pid}, took {elapsed:.1f}s)"
                    )
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Daemon process started (PID {pid}) but may not be fully ready yet"
                    )
                    console.print(
                        "[dim]Use 'btbt daemon status' to check daemon status[/dim]"
                    )
            else:
                console.print(f"[green]✓[/green] Daemon process started (PID {pid})")
                console.print(
                    "[dim]Use 'btbt daemon status' to check daemon status[/dim]"
                )

        except RuntimeError as e:
            console.print(f"[red]✗[/red] Failed to start daemon: {e}")
            raise click.Abort()


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


def _wait_for_daemon(daemon_config: DaemonConfig, timeout: float = 15.0) -> bool:
    """Wait for daemon to be ready.

    Args:
        daemon_config: Daemon configuration
        timeout: Timeout in seconds

    Returns:
        True if daemon is ready, False otherwise

    """

    async def _check_daemon_loop() -> bool:
        """Check if daemon is running in a loop."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            client = IPCClient(api_key=daemon_config.api_key)
            try:
                is_running = await client.is_daemon_running()
                if is_running:
                    return True
            except Exception:
                pass
            finally:
                await client.close()

            # Wait before next check
            await asyncio.sleep(0.5)

        return False

    try:
        # Use asyncio.run() to create a new event loop
        # Windows ProactorEventLoop cleanup warnings are handled at module level
        return asyncio.run(_check_daemon_loop())
    except Exception as e:
        logger.debug("Error waiting for daemon: %s", e)
        return False


def _wait_for_daemon_with_progress(
    daemon_config: DaemonConfig,
    timeout: float = 15.0,
    progress: Progress | None = None,
    task: int | None = None,
    verbose: bool = False,
    daemon_pid: int | None = None,
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
    INIT_STAGES = [
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
        try:
            is_running = daemon_manager.is_running()
        except Exception:
            pass

        if not is_running:
            return False, 1, INIT_STAGES[1]

        # Try to connect to IPC server
        client = IPCClient(api_key=daemon_config.api_key)
        try:
            is_accessible = await asyncio.wait_for(
                client.is_daemon_running(), timeout=1.5
            )

            if not is_accessible:
                return False, 2, INIT_STAGES[2]  # "Process starting..."

            # IPC server is accessible - session manager and IPC server are started
            # Try to get detailed status to confirm full readiness
            try:
                status = await asyncio.wait_for(client.get_status(), timeout=1.5)
                # If we can get status with valid data, daemon is fully ready
                if status.status and status.uptime >= 0:
                    return True, len(INIT_STAGES) - 1, INIT_STAGES[-1]
                # Status endpoint exists but not fully initialized
                return False, 3, INIT_STAGES[3]  # "Starting IPC server..."
            except (ConnectionError, TimeoutError, asyncio.TimeoutError):
                # IPC server accessible but status endpoint not ready - IPC server still starting
                return False, 3, INIT_STAGES[3]  # "Starting IPC server..."
            except Exception:
                # Status endpoint error - IPC server started but not fully ready
                return False, 3, INIT_STAGES[3]  # "Starting IPC server..."

        finally:
            await client.close()

    start_time = time.time()
    last_status = INIT_STAGES[0]
    check_count = 0
    stage_start_times: dict[int, float] = {}  # Track when each stage started
    last_detected_stage = -1

    # Track daemon PID to detect crashes
    # Use provided PID or try to get it from manager
    daemon_manager = DaemonManager()
    initial_pid = daemon_pid
    if initial_pid is None:
        # Fallback: try to get PID from file (may not exist yet)
        initial_pid = daemon_manager.get_pid()
    process_crashed = False

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
            check_count_local = check_count + 1

            # Check if daemon process is still running (detect crashes)
            # Only check if we have a valid PID
            if initial_pid is not None:
                is_alive = _is_process_alive(initial_pid)

                if not is_alive:
                    # Process crashed - process is dead
                    if progress and task is not None:
                        progress.update(
                            task, description="[red]Daemon process crashed[/red]"
                        )
                    if verbose:
                        console.print(
                            f"[red]✗[/red] Daemon process (PID {initial_pid}) crashed during startup (after {elapsed:.1f}s)"
                        )
                        console.print(
                            "[yellow]The daemon process exited unexpectedly. Check daemon logs for error details.[/yellow]"
                        )
                    else:
                        console.print(
                            f"[red]✗[/red] Daemon process (PID {initial_pid}) crashed during startup (after {elapsed:.1f}s)"
                        )
                        console.print(
                            "[yellow]The daemon process exited unexpectedly. Check daemon logs for error details.[/yellow]"
                        )
                        console.print(
                            "[dim]Use -v flag for more details or check daemon logs[/dim]"
                        )
                    return False

            try:
                is_ready, stage_idx, stage_desc = await _check_daemon_stage()

                # Track stage transitions
                if stage_idx != last_detected_stage:
                    stage_start_times[stage_idx] = time.time()
                    last_detected_stage = stage_idx

                if progress and task is not None:
                    progress.update(task, description=stage_desc)

                last_status = stage_desc

                if is_ready:
                    return True

            except Exception as e:
                if verbose:
                    logger.debug("Error checking daemon stage: %s", e)
                # Continue waiting

            # Brief sleep before next check
            await asyncio.sleep(0.3)

        # Timeout reached
        if progress and task is not None:
            progress.update(
                task,
                description=f"[yellow]Timeout waiting for daemon (last status: {last_status})[/yellow]",
            )

        if verbose:
            console.print(
                f"[yellow]⚠[/yellow] Daemon startup timeout after {timeout:.1f}s (last status: {last_status})"
            )
            console.print(
                "[dim]Daemon may still be starting. Use 'btbt daemon status' to check.[/dim]"
            )

        return False

    try:
        # Use asyncio.run() to create a new event loop
        # Windows ProactorEventLoop cleanup warnings are handled at module level
        return asyncio.run(_wait_loop())
    except Exception as e:
        logger.debug("Error waiting for daemon with progress: %s", e)
        return False


@daemon.command("exit")
@click.option(
    "--force",
    is_flag=True,
    help="Force kill without graceful shutdown",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Shutdown timeout in seconds",
)
def exit(force: bool, timeout: float) -> None:
    """Stop the daemon process."""
    daemon_manager = DaemonManager()

    if not daemon_manager.is_running():
        click.echo("Daemon is not running")
        return

    success = False

    if not force:
        # Try graceful shutdown via IPC
        try:
            config_manager = init_config()
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
                        # Wait for process to exit
                        start_time = time.time()
                        while time.time() - start_time < timeout:
                            if not daemon_manager.is_running():
                                click.echo("Daemon stopped gracefully")
                                return
                            time.sleep(0.5)
                except Exception as e:
                    logger.debug("Error sending shutdown request: %s", e)
                    click.echo("Could not send shutdown request, using signal...")

            # Fallback to signal-based shutdown
            success = daemon_manager.stop(timeout=timeout, force=False)
        except Exception:
            # If IPC fails entirely, fall back to signal
            success = daemon_manager.stop(timeout=timeout, force=False)
    else:
        # Force kill
        success = daemon_manager.stop(timeout=timeout, force=True)

    if success:
        click.echo("Daemon stopped")
    else:
        click.echo("Failed to stop daemon", err=True)
        if not force:
            click.echo("Use --force to force kill", err=True)
        raise click.Abort()


@daemon.command("status")
def status() -> None:
    """Show daemon status."""
    daemon_manager = DaemonManager()

    if not daemon_manager.is_running():
        console.print("[red]Daemon is not running[/red]")
        return

    pid = daemon_manager.get_pid()
    console.print(f"[green]Daemon is running[/green] (PID: {pid})")

    # Try to get detailed status via IPC
    try:
        config_manager = init_config()
        cfg = get_config()

        if cfg.daemon and cfg.daemon.api_key:

            async def _get_status() -> None:
                """Get daemon status via IPC."""
                client = IPCClient(api_key=cfg.daemon.api_key)  # type: ignore[union-attr]
                try:
                    status = await client.get_status()
                    console.print(f"\n[cyan]Status:[/cyan] {status.status}")
                    console.print(f"[cyan]Torrents:[/cyan] {status.num_torrents}")
                    console.print(f"[cyan]Uptime:[/cyan] {status.uptime:.1f}s")
                    if hasattr(status, "download_rate"):
                        console.print(
                            f"[cyan]Download:[/cyan] {status.download_rate:.2f} KiB/s"
                        )
                    if hasattr(status, "upload_rate"):
                        console.print(
                            f"[cyan]Upload:[/cyan] {status.upload_rate:.2f} KiB/s"
                        )
                finally:
                    await client.close()

            asyncio.run(_get_status())
        else:
            console.print(
                "[yellow]API key not found in config, cannot get detailed status[/yellow]"
            )
    except Exception as e:
        logger.debug("Error getting daemon status: %s", e)
        console.print("[yellow]Could not get detailed status via IPC[/yellow]")
