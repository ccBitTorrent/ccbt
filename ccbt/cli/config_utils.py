"""Configuration utilities for CLI commands.

Provides functions to detect config changes requiring daemon restart
and handle daemon restart logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Confirm

from ccbt.config.config import ConfigManager
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:
    from ccbt.models import Config

logger = get_logger(__name__)
console = Console()


def requires_daemon_restart(old_config: Config, new_config: Config) -> bool:
    """Check if config changes require daemon restart.

    Args:
        old_config: Previous configuration
        new_config: New configuration

    Returns:
        True if daemon restart is required, False if hot reload is sufficient

    """
    # Daemon config changes always require restart
    if old_config.daemon != new_config.daemon:
        if old_config.daemon is None or new_config.daemon is None:
            return True
        # Check individual daemon fields
        if (
            old_config.daemon.api_key != new_config.daemon.api_key
            or old_config.daemon.ipc_host != new_config.daemon.ipc_host
            or old_config.daemon.ipc_port != new_config.daemon.ipc_port
            or old_config.daemon.websocket_enabled
            != new_config.daemon.websocket_enabled
            or old_config.daemon.websocket_heartbeat_interval
            != new_config.daemon.websocket_heartbeat_interval
            or old_config.daemon.auto_save_interval
            != new_config.daemon.auto_save_interval
            or old_config.daemon.state_dir != new_config.daemon.state_dir
        ):
            return True

    # Disk config changes require restart (affects checkpoint paths, download paths, etc.)
    old_disk = old_config.disk.model_dump()
    new_disk = new_config.disk.model_dump()
    if old_disk != new_disk:
        return True

    # Observability config changes that affect file paths or ports require restart
    if (
        old_config.observability.log_file != new_config.observability.log_file
        or old_config.observability.metrics_port
        != new_config.observability.metrics_port
        or old_config.observability.trace_file != new_config.observability.trace_file
    ):
        return True

    # Strategy config changes require restart (affects piece selection behavior)
    old_strategy = old_config.strategy.model_dump()
    new_strategy = new_config.strategy.model_dump()
    if old_strategy != new_strategy:
        return True

    # Security config changes beyond IP filters require restart
    # IP filters can be hot-reloaded, but other security settings cannot
    old_security = old_config.security.model_dump()
    new_security = new_config.security.model_dump()
    # Remove IP filter fields for comparison (they can be hot-reloaded)
    old_security.pop("ip_filter", None)
    new_security.pop("ip_filter", None)
    if old_security != new_security:
        return True

    # Network config changes not covered by reload_config require restart
    # reload_config handles: listen_port, enable_tcp, max_global_peers, connection_timeout
    # Everything else requires restart
    old_network = old_config.network.model_dump()
    new_network = new_config.network.model_dump()
    # Remove fields that can be hot-reloaded
    for field in [
        "listen_port",
        "enable_tcp",
        "max_global_peers",
        "connection_timeout",
    ]:
        old_network.pop(field, None)
        new_network.pop(field, None)
    if old_network != new_network:
        return True

    # Discovery config changes not covered by reload_config require restart
    # reload_config handles: enable_dht, dht_port
    old_discovery = old_config.discovery.model_dump()
    new_discovery = new_config.discovery.model_dump()
    # Remove fields that can be hot-reloaded
    for field in ["enable_dht", "dht_port"]:
        old_discovery.pop(field, None)
        new_discovery.pop(field, None)
    if old_discovery != new_discovery:
        return True

    # NAT config changes not covered by reload_config require restart
    # reload_config handles: auto_map_ports, enable_nat_pmp, enable_upnp
    old_nat = old_config.nat.model_dump()
    new_nat = new_config.nat.model_dump()
    # Remove fields that can be hot-reloaded
    for field in ["auto_map_ports", "enable_nat_pmp", "enable_upnp"]:
        old_nat.pop(field, None)
        new_nat.pop(field, None)
    if old_nat != new_nat:
        return True

    # Queue config changes require restart (affects queue management)
    old_queue = old_config.queue.model_dump()
    new_queue = new_config.queue.model_dump()
    if old_queue != new_queue:
        return True

    # Proxy config changes require restart
    old_proxy = old_config.proxy.model_dump()
    new_proxy = new_config.proxy.model_dump()
    if old_proxy != new_proxy:
        return True

    # ML config changes require restart
    old_ml = old_config.ml.model_dump()
    new_ml = new_config.ml.model_dump()
    if old_ml != new_ml:
        return True

    # Dashboard config changes require restart
    old_dashboard = old_config.dashboard.model_dump()
    new_dashboard = new_config.dashboard.model_dump()
    if old_dashboard != new_dashboard:
        return True

    # IPFS config changes require restart
    old_ipfs = old_config.ipfs.model_dump()
    new_ipfs = new_config.ipfs.model_dump()
    if old_ipfs != new_ipfs:
        return True

    # WebTorrent config changes require restart
    old_webtorrent = old_config.webtorrent.model_dump()
    new_webtorrent = new_config.webtorrent.model_dump()
    if new_webtorrent != old_webtorrent:
        return True

    # Limits config changes require restart
    old_limits = old_config.limits.model_dump()
    new_limits = new_config.limits.model_dump()
    if old_limits != new_limits:
        return True

    return False


async def _restart_daemon_async(force: bool = False) -> bool:
    """Restart daemon asynchronously.

    Args:
        force: Force kill if graceful shutdown fails

    Returns:
        True if restart was successful, False otherwise

    """
    from ccbt.config.config import get_config, init_config
    from ccbt.daemon.daemon_manager import DaemonManager

    daemon_manager = DaemonManager()

    if not daemon_manager.is_running():
        logger.debug("Daemon is not running, nothing to restart")
        return False

    # Stop daemon
    logger.info("Stopping daemon for restart...")
    try:
        config_manager = init_config()
        cfg = get_config()

        if cfg.daemon and cfg.daemon.api_key:
            try:
                client = IPCClient(api_key=cfg.daemon.api_key)
                try:
                    shutdown_success = await client.shutdown()
                    if shutdown_success:
                        # Wait for graceful shutdown
                        import asyncio
                        import time

                        start_time = time.time()
                        timeout = 30.0
                        while time.time() - start_time < timeout:
                            if not daemon_manager.is_running():
                                logger.info("Daemon stopped gracefully")
                                break
                            await asyncio.sleep(0.5)
                        else:
                            # Timeout, force stop
                            logger.warning("Graceful shutdown timeout, forcing stop")
                            daemon_manager.stop(timeout=5.0, force=True)
                finally:
                    await client.close()
            except Exception as e:
                logger.debug("Error sending shutdown request: %s", e)
                # Fallback to signal-based shutdown
                daemon_manager.stop(timeout=30.0, force=force)
        else:
            # No API key, use signal-based shutdown
            daemon_manager.stop(timeout=30.0, force=force)
    except Exception as e:
        logger.exception("Error stopping daemon: %s", e)
        return False

    # Wait a moment for process to fully exit
    import asyncio

    await asyncio.sleep(0.5)

    # Start daemon
    logger.info("Starting daemon...")
    try:
        pid = daemon_manager.start(foreground=False)
        if pid:
            # Wait a moment for daemon to initialize
            await asyncio.sleep(1.0)
            logger.info("Daemon restarted successfully (PID: %d)", pid)
            return True
        return False
    except Exception as e:
        logger.exception("Error starting daemon: %s", e)
        return False


def restart_daemon_if_needed(
    config_manager: ConfigManager,
    requires_restart: bool,
    auto_restart: bool | None = None,
    force: bool = False,
) -> bool:
    """Restart daemon if needed and running.

    Args:
        config_manager: ConfigManager instance
        requires_restart: Whether restart is required
        auto_restart: If True, restart without prompt. If False, skip restart.
                      If None, prompt user.
        force: Force kill if graceful shutdown fails

    Returns:
        True if restart was performed, False otherwise

    """
    if not requires_restart:
        return False

    daemon_manager = DaemonManager()
    if not daemon_manager.is_running():
        logger.debug("Daemon is not running, restart not needed")
        return False

    # Determine if we should restart
    should_restart = False
    if auto_restart is True:
        should_restart = True
    elif auto_restart is False:
        should_restart = False
        console.print(
            "[yellow]Warning: Configuration changes require daemon restart, but restart was skipped.[/yellow]"
        )
        console.print(
            "[dim]Please restart the daemon manually: 'btbt daemon restart'[/dim]"
        )
    else:
        # Prompt user
        console.print("[yellow]Configuration changes require daemon restart.[/yellow]")
        should_restart = Confirm.ask(
            "Restart daemon now?",
            default=True,
        )

    if not should_restart:
        return False

    # Perform restart
    console.print("[cyan]Restarting daemon...[/cyan]")
    try:
        import asyncio

        success = asyncio.run(_restart_daemon_async(force=force))
        if success:
            console.print("[green]Daemon restarted successfully[/green]")
            return True
        console.print("[red]Failed to restart daemon[/red]")
        console.print("[dim]Please restart manually: 'btbt daemon restart'[/dim]")
        return False
    except Exception as e:
        logger.exception("Error restarting daemon: %s", e)
        console.print(f"[red]Error restarting daemon: {e}[/red]")
        console.print("[dim]Please restart manually: 'btbt daemon restart'[/dim]")
        return False
