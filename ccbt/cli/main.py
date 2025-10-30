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
from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.monitoring_commands import alerts as alerts_cmd
from ccbt.cli.monitoring_commands import dashboard as dashboard_cmd
from ccbt.cli.monitoring_commands import metrics as metrics_cmd
from ccbt.cli.progress import ProgressManager
from ccbt.config.config import Config, ConfigManager, init_config
from ccbt.monitoring import (
    AlertManager,
    DashboardManager,
    MetricsCollector,
    TracingManager,
)
from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


def _raise_cli_error(message: str) -> None:
    """Raise a ClickException with the given message."""
    raise click.ClickException(message) from None


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
            logger.debug("Failed to set first piece priority: %s", e)
    if options.get("last_piece_priority"):
        try:
            cfg.strategy.last_piece_priority = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Failed to set last piece priority: %s", e)
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
            logger.debug("Failed to enable io_uring: %s", e)
    if options.get("disable_io_uring"):
        try:
            cfg.disk.enable_io_uring = False  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Failed to disable io_uring: %s", e)
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
    help="Configuration file path",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--debug", "-d", is_flag=True, help="Enable debug mode")
@click.pass_context
def cli(ctx, config, verbose, debug):
    """CcBitTorrent - High-performance BitTorrent client."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug

    # Initialize global configuration early
    with contextlib.suppress(Exception):
        init_config(config)

    # docs command removed; docs are maintained in repository


@cli.command()
@click.argument("torrent_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive mode")
@click.option("--monitor", "-m", is_flag=True, help="Enable monitoring")
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    help="Resume from checkpoint if available",
)
@click.option("--no-checkpoint", is_flag=True, help="Disable checkpointing")
@click.option("--checkpoint-dir", type=click.Path(), help="Checkpoint directory")
@click.option("--listen-port", type=int, help="Listen port")
@click.option("--max-peers", type=int, help="Maximum global peers")
@click.option("--max-peers-per-torrent", type=int, help="Maximum peers per torrent")
@click.option("--pipeline-depth", type=int, help="Request pipeline depth")
@click.option("--block-size-kib", type=int, help="Block size (KiB)")
@click.option("--connection-timeout", type=float, help="Connection timeout (s)")
@click.option("--download-limit", type=int, help="Global download limit (KiB/s)")
@click.option("--upload-limit", type=int, help="Global upload limit (KiB/s)")
@click.option("--dht-port", type=int, help="DHT port")
@click.option("--enable-dht", is_flag=True, help="Enable DHT")
@click.option("--disable-dht", is_flag=True, help="Disable DHT")
@click.option(
    "--piece-selection",
    type=click.Choice(["round_robin", "rarest_first", "sequential"]),
)
@click.option("--endgame-threshold", type=float, help="Endgame threshold (0..1)")
@click.option("--hash-workers", type=int, help="Hash verification workers")
@click.option("--disk-workers", type=int, help="Disk I/O workers")
@click.option("--use-mmap", is_flag=True, help="Use memory mapping")
@click.option("--no-mmap", is_flag=True, help="Disable memory mapping")
@click.option("--mmap-cache-mb", type=int, help="MMap cache size (MB)")
@click.option("--write-batch-kib", type=int, help="Write batch size (KiB)")
@click.option("--write-buffer-kib", type=int, help="Write buffer size (KiB)")
@click.option("--preallocate", type=click.Choice(["none", "sparse", "full"]))
@click.option("--sparse-files", is_flag=True, help="Enable sparse files")
@click.option("--no-sparse-files", is_flag=True, help="Disable sparse files")
@click.option(
    "--enable-io-uring",
    is_flag=True,
    help="Enable io_uring on Linux if available",
)
@click.option("--disable-io-uring", is_flag=True, help="Disable io_uring usage")
@click.option(
    "--direct-io",
    is_flag=True,
    help="Enable direct I/O for writes when supported",
)
@click.option("--sync-writes", is_flag=True, help="Enable fsync after batched writes")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
)
@click.option("--enable-metrics", is_flag=True, help="Enable metrics")
@click.option("--disable-metrics", is_flag=True, help="Disable metrics")
@click.option("--metrics-port", type=int, help="Metrics port")
@click.option("--enable-ipv6", is_flag=True, help="Enable IPv6")
@click.option("--disable-ipv6", is_flag=True, help="Disable IPv6")
@click.option("--enable-tcp", is_flag=True, help="Enable TCP transport")
@click.option("--disable-tcp", is_flag=True, help="Disable TCP transport")
@click.option("--enable-utp", is_flag=True, help="Enable uTP transport")
@click.option("--disable-utp", is_flag=True, help="Disable uTP transport")
@click.option("--enable-encryption", is_flag=True, help="Enable protocol encryption")
@click.option("--disable-encryption", is_flag=True, help="Disable protocol encryption")
@click.option("--tcp-nodelay", is_flag=True, help="Enable TCP_NODELAY")
@click.option("--no-tcp-nodelay", is_flag=True, help="Disable TCP_NODELAY")
@click.option("--socket-rcvbuf-kib", type=int, help="Socket receive buffer (KiB)")
@click.option("--socket-sndbuf-kib", type=int, help="Socket send buffer (KiB)")
@click.option("--listen-interface", type=str, help="Listen interface")
@click.option("--peer-timeout", type=float, help="Peer timeout (s)")
@click.option("--dht-timeout", type=float, help="DHT timeout (s)")
@click.option("--min-block-size-kib", type=int, help="Minimum block size (KiB)")
@click.option("--max-block-size-kib", type=int, help="Maximum block size (KiB)")
@click.option("--enable-http-trackers", is_flag=True, help="Enable HTTP trackers")
@click.option("--disable-http-trackers", is_flag=True, help="Disable HTTP trackers")
@click.option("--enable-udp-trackers", is_flag=True, help="Enable UDP trackers")
@click.option("--disable-udp-trackers", is_flag=True, help="Disable UDP trackers")
@click.option(
    "--tracker-announce-interval",
    type=float,
    help="Tracker announce interval (s)",
)
@click.option(
    "--tracker-scrape-interval",
    type=float,
    help="Tracker scrape interval (s)",
)
@click.option("--pex-interval", type=float, help="PEX interval (s)")
@click.option("--endgame-duplicates", type=int, help="Endgame duplicate requests")
@click.option("--streaming-mode", is_flag=True, help="Enable streaming mode")
@click.option("--first-piece-priority", is_flag=True, help="Prioritize first piece")
@click.option("--last-piece-priority", is_flag=True, help="Prioritize last piece")
@click.option(
    "--optimistic-unchoke-interval",
    type=float,
    help="Optimistic unchoke interval (s)",
)
@click.option("--unchoke-interval", type=float, help="Unchoke interval (s)")
@click.option("--metrics-interval", type=float, help="Metrics interval (s)")
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

        # Create session
        session = AsyncSessionManager(".")

        # Load torrent
        torrent_path = Path(torrent_file)
        torrent_data = session.load_torrent(torrent_path)

        if not torrent_data:
            console.print(
                f"[red]Error: Could not load torrent file {torrent_file}[/red]",
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
                    f"[yellow]Found checkpoint for: {getattr(checkpoint, 'torrent_name', 'Unknown')}[/yellow]",
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
                            console.print("[green]Resuming from checkpoint[/green]")
                        else:
                            console.print("[yellow]Starting fresh download[/yellow]")
                    except ImportError:
                        console.print(
                            "[yellow]Rich not available, starting fresh download[/yellow]",
                        )
                else:
                    console.print(
                        "[yellow]Non-interactive mode, starting fresh download[/yellow]",
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
        console.print(f"[red]File not found: {e}[/red]")
        msg = "Torrent file not found"
        raise click.ClickException(msg) from e
    except ValueError as e:
        console.print(f"[red]Invalid torrent file: {e}[/red]")
        msg = "Invalid torrent file format"
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("magnet_link")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive mode")
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    help="Resume from checkpoint if available",
)
@click.option("--no-checkpoint", is_flag=True, help="Disable checkpointing")
@click.option("--checkpoint-dir", type=click.Path(), help="Checkpoint directory")
@click.option("--listen-port", type=int, help="Listen port")
@click.option("--max-peers", type=int, help="Maximum global peers")
@click.option("--max-peers-per-torrent", type=int, help="Maximum peers per torrent")
@click.option("--pipeline-depth", type=int, help="Request pipeline depth")
@click.option("--block-size-kib", type=int, help="Block size (KiB)")
@click.option("--connection-timeout", type=float, help="Connection timeout (s)")
@click.option("--download-limit", type=int, help="Global download limit (KiB/s)")
@click.option("--upload-limit", type=int, help="Global upload limit (KiB/s)")
@click.option("--dht-port", type=int, help="DHT port")
@click.option("--enable-dht", is_flag=True, help="Enable DHT")
@click.option("--disable-dht", is_flag=True, help="Disable DHT")
@click.option(
    "--piece-selection",
    type=click.Choice(["round_robin", "rarest_first", "sequential"]),
)
@click.option("--endgame-threshold", type=float, help="Endgame threshold (0..1)")
@click.option("--hash-workers", type=int, help="Hash verification workers")
@click.option("--disk-workers", type=int, help="Disk I/O workers")
@click.option("--use-mmap", is_flag=True, help="Use memory mapping")
@click.option("--no-mmap", is_flag=True, help="Disable memory mapping")
@click.option("--mmap-cache-mb", type=int, help="MMap cache size (MB)")
@click.option("--write-batch-kib", type=int, help="Write batch size (KiB)")
@click.option("--write-buffer-kib", type=int, help="Write buffer size (KiB)")
@click.option("--preallocate", type=click.Choice(["none", "sparse", "full"]))
@click.option("--sparse-files", is_flag=True, help="Enable sparse files")
@click.option("--no-sparse-files", is_flag=True, help="Disable sparse files")
@click.option(
    "--enable-io-uring",
    is_flag=True,
    help="Enable io_uring on Linux if available",
)
@click.option("--disable-io-uring", is_flag=True, help="Disable io_uring usage")
@click.option(
    "--direct-io",
    is_flag=True,
    help="Enable direct I/O for writes when supported",
)
@click.option("--sync-writes", is_flag=True, help="Enable fsync after batched writes")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
)
@click.option("--enable-metrics", is_flag=True, help="Enable metrics")
@click.option("--disable-metrics", is_flag=True, help="Disable metrics")
@click.option("--metrics-port", type=int, help="Metrics port")
@click.option("--enable-ipv6", is_flag=True, help="Enable IPv6")
@click.option("--disable-ipv6", is_flag=True, help="Disable IPv6")
@click.option("--enable-tcp", is_flag=True, help="Enable TCP transport")
@click.option("--disable-tcp", is_flag=True, help="Disable TCP transport")
@click.option("--enable-utp", is_flag=True, help="Enable uTP transport")
@click.option("--disable-utp", is_flag=True, help="Disable uTP transport")
@click.option("--enable-encryption", is_flag=True, help="Enable protocol encryption")
@click.option("--disable-encryption", is_flag=True, help="Disable protocol encryption")
@click.option("--tcp-nodelay", is_flag=True, help="Enable TCP_NODELAY")
@click.option("--no-tcp-nodelay", is_flag=True, help="Disable TCP_NODELAY")
@click.option("--socket-rcvbuf-kib", type=int, help="Socket receive buffer (KiB)")
@click.option("--socket-sndbuf-kib", type=int, help="Socket send buffer (KiB)")
@click.option("--listen-interface", type=str, help="Listen interface")
@click.option("--peer-timeout", type=float, help="Peer timeout (s)")
@click.option("--dht-timeout", type=float, help="DHT timeout (s)")
@click.option("--min-block-size-kib", type=int, help="Minimum block size (KiB)")
@click.option("--max-block-size-kib", type=int, help="Maximum block size (KiB)")
@click.option("--enable-http-trackers", is_flag=True, help="Enable HTTP trackers")
@click.option("--disable-http-trackers", is_flag=True, help="Disable HTTP trackers")
@click.option("--enable-udp-trackers", is_flag=True, help="Enable UDP trackers")
@click.option("--disable-udp-trackers", is_flag=True, help="Disable UDP trackers")
@click.option(
    "--tracker-announce-interval",
    type=float,
    help="Tracker announce interval (s)",
)
@click.option(
    "--tracker-scrape-interval",
    type=float,
    help="Tracker scrape interval (s)",
)
@click.option("--pex-interval", type=float, help="PEX interval (s)")
@click.option("--endgame-duplicates", type=int, help="Endgame duplicate requests")
@click.option("--streaming-mode", is_flag=True, help="Enable streaming mode")
@click.option("--first-piece-priority", is_flag=True, help="Prioritize first piece")
@click.option("--last-piece-priority", is_flag=True, help="Prioritize last piece")
@click.option(
    "--optimistic-unchoke-interval",
    type=float,
    help="Optimistic unchoke interval (s)",
)
@click.option("--unchoke-interval", type=float, help="Unchoke interval (s)")
@click.option("--metrics-interval", type=float, help="Metrics interval (s)")
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
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        _apply_cli_overrides(config_manager, kwargs)
        config = config_manager.config

        # Override checkpoint settings if specified
        if no_checkpoint:
            config.disk.checkpoint_enabled = False
        if checkpoint_dir:
            config.disk.checkpoint_dir = checkpoint_dir

        # Create session
        session = AsyncSessionManager(".")

        # Parse magnet link
        torrent_data = session.parse_magnet_link(magnet_link)

        if not torrent_data:
            console.print("[red]Error: Could not parse magnet link[/red]")
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
                    f"[yellow]Found checkpoint for: {getattr(checkpoint, 'torrent_name', 'Unknown')}[/yellow]",
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
                            console.print("[green]Resuming from checkpoint[/green]")
                        else:
                            console.print("[yellow]Starting fresh download[/yellow]")
                    except ImportError:
                        console.print(
                            "[yellow]Rich not available, starting fresh download[/yellow]",
                        )
                else:
                    console.print(
                        "[yellow]Non-interactive mode, starting fresh download[/yellow]",
                    )

        # Set output directory
        if output:
            if isinstance(torrent_data, dict):
                torrent_data["download_path"] = Path(output)
            else:
                # For TorrentInfo, we'll pass output_dir separately
                pass

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

    except ValueError as e:
        console.print(f"[red]Invalid magnet link: {e}[/red]")
        msg = "Invalid magnet link format"
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.option("--port", "-p", type=int, default=9090, help="Port for web interface")
@click.option("--host", "-h", default="localhost", help="Host for web interface")
@click.pass_context
def web(ctx, port, host):
    """Start web interface."""
    console = Console()

    try:
        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session
        session = AsyncSessionManager(".")

        # Start web interface
        console.print(f"[green]Starting web interface on http://{host}:{port}[/green]")
        asyncio.run(session.start_web_interface(host, port))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start interactive mode."""
    console = Console()

    try:
        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session
        session = AsyncSessionManager(".")

        # Start interactive CLI
        interactive_cli = InteractiveCLI(session, console)
        asyncio.run(interactive_cli.run())

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def status(ctx):
    """Show client status."""
    console = Console()

    try:
        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session
        session = AsyncSessionManager(".")

        # Show status
        asyncio.run(show_status(session, console))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.pass_context
def debug(ctx):
    """Start debug mode."""
    console = Console()

    try:
        # Load configuration
        ConfigManager(ctx.obj["config"])

        # Create session
        session = AsyncSessionManager(".")

        # Start debug mode
        asyncio.run(start_debug_mode(session, console))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
    help="Show checkpoints in specific format",
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
            console.print("[yellow]No checkpoints found[/yellow]")
            return

        # Create table
        table = Table(title="Available Checkpoints")
        table.add_column("Info Hash", style="cyan")
        table.add_column("Format", style="green")
        table.add_column("Size", style="blue")
        table.add_column("Created", style="magenta")
        table.add_column("Updated", style="yellow")

        for checkpoint in checkpoints:
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
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@checkpoints.command("clean")
@click.option(
    "--days",
    "-d",
    type=int,
    default=30,
    help="Remove checkpoints older than N days",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
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
                    f"[green]No checkpoints older than {days} days found[/green]",
                )
                return

            console.print(
                f"[yellow]Would delete {len(old_checkpoints)} checkpoints older than {days} days:[/yellow]",
            )
            for checkpoint in old_checkpoints:
                console.print(
                    f"  - {checkpoint.info_hash.hex()[:16]}... ({checkpoint.format.value})",
                )
        else:
            # Actually clean up
            deleted_count = asyncio.run(
                checkpoint_manager.cleanup_old_checkpoints(days),
            )
            console.print(f"[green]Cleaned up {deleted_count} old checkpoints[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)

        # Delete checkpoint
        deleted = asyncio.run(checkpoint_manager.delete_checkpoint(info_hash_bytes))

        if deleted:
            console.print(f"[green]Deleted checkpoint for {info_hash}[/green]")
        else:
            console.print(f"[yellow]No checkpoint found for {info_hash}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)
        valid = asyncio.run(checkpoint_manager.verify_checkpoint(info_hash_bytes))
        if valid:
            console.print(f"[green]Checkpoint for {info_hash} is valid[/green]")
        else:
            console.print(
                f"[yellow]Checkpoint for {info_hash} is missing or invalid[/yellow]",
            )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
    help="Output file path",
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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)
        data = asyncio.run(
            checkpoint_manager.export_checkpoint(info_hash_bytes, fmt=format_),
        )
        Path(output_path).write_bytes(data)
        console.print(f"[green]Exported checkpoint to {output_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@checkpoints.command("backup")
@click.argument("info_hash")
@click.option(
    "--destination",
    "destination",
    type=click.Path(),
    required=True,
    help="Backup destination path",
)
@click.option(
    "--compress",
    is_flag=True,
    default=True,
    help="Compress backup (default: yes)",
)
@click.option("--encrypt", is_flag=True, help="Encrypt backup with generated key")
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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
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
        console.print(f"[green]Backup created: {final_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@checkpoints.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
@click.option(
    "--info-hash",
    "info_hash",
    type=str,
    default=None,
    help="Expected info hash (hex)",
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
                console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
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
        console.print(f"[red]Error: {e}[/red]")
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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)
        src = CheckpointFormat[from_format.upper()]
        dst = CheckpointFormat[to_format.upper()]
        new_path = asyncio.run(
            checkpoint_manager.convert_checkpoint_format(info_hash_bytes, src, dst),
        )
        console.print(f"[green]Migrated checkpoint to {new_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("info_hash")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive mode")
@click.pass_context
def resume(ctx, info_hash, _output, interactive):
    """Resume download from checkpoint."""
    console = Console()

    try:
        # Load configuration
        config_manager = ConfigManager(ctx.obj["config"])
        config = config_manager.config

        # Create session
        session = AsyncSessionManager(".")

        # Convert hex string to bytes
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)

        # Load checkpoint
        from ccbt.storage.checkpoint import CheckpointManager

        checkpoint_manager = CheckpointManager(config.disk)
        checkpoint = asyncio.run(checkpoint_manager.load_checkpoint(info_hash_bytes))

        if not checkpoint:
            console.print(f"[red]No checkpoint found for {info_hash}[/red]")
            msg = "Command failed"
            _raise_cli_error(msg)

        console.print(
            f"[green]Found checkpoint for: {getattr(checkpoint, 'torrent_name', 'Unknown')}[/green]"
        )
        console.print(
            f"[blue]Progress: {len(getattr(checkpoint, 'verified_pieces', []))}/{getattr(checkpoint, 'total_pieces', 0)} pieces verified[/blue]",
        )

        # Check if checkpoint can be auto-resumed
        can_auto_resume = bool(
            getattr(checkpoint, "torrent_file_path", None)
            or getattr(checkpoint, "magnet_uri", None)
        )

        if not can_auto_resume:
            console.print(
                "[yellow]Checkpoint cannot be auto-resumed - no torrent source found[/yellow]",
            )
            console.print(
                "[yellow]Please provide the original torrent file or magnet link[/yellow]",
            )
            msg = "Cannot auto-resume checkpoint"
            _raise_cli_error(msg)

        # Start session manager and resume
        asyncio.run(
            resume_download(session, info_hash_bytes, checkpoint, interactive, console),
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
        console.print("[green]Resuming download from checkpoint...[/green]")
        resumed_info_hash = await session.resume_from_checkpoint(
            info_hash_bytes,
            checkpoint,
        )

        console.print(
            f"[green]Successfully resumed download: {resumed_info_hash}[/green]",
        )

        if interactive:
            # Start interactive mode
            interactive_cli = InteractiveCLI(session, console)
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
                        console.print("[yellow]Torrent session ended[/yellow]")
                        break

                    progress.update(
                        task,
                        completed=torrent_status.get("progress", 0) * 100,
                    )

                    if torrent_status.get("status") == "seeding":
                        console.print(
                            f"[green]Download completed: {checkpoint.torrent_name}[/green]",
                        )
                        break

                    await asyncio.sleep(1)

    except ValueError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        msg = "Resume failed due to validation error"
        raise click.ClickException(msg) from e
    except FileNotFoundError as e:
        console.print(f"[red]File not found: {e}[/red]")
        msg = "Resume failed - torrent file not found"
        raise click.ClickException(msg) from e
    except Exception as e:
        console.print(f"[red]Unexpected error during resume: {e}[/red]")
        msg = "Resume failed due to unexpected error"
        raise click.ClickException(msg) from e
    finally:
        try:
            await session.stop()
        except Exception as e:
            console.print(f"[yellow]Warning: Error stopping session: {e}[/yellow]")


async def start_monitoring(_session: AsyncSessionManager, console: Console) -> None:
    """Start monitoring components."""
    # Initialize monitoring
    metrics_collector = MetricsCollector()
    AlertManager()
    TracingManager()
    DashboardManager()

    # Start monitoring
    asyncio.run(metrics_collector.start())

    console.print("[green]Monitoring started[/green]")


async def start_interactive_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
) -> None:
    """Start interactive download."""
    interactive_cli = InteractiveCLI(session, console)
    await interactive_cli.download_torrent(torrent_data, resume=resume)


async def start_basic_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
) -> None:
    """Start basic download with progress bar."""
    progress_manager = ProgressManager(console)

    with progress_manager.create_progress() as progress:
        torrent_name = (
            torrent_data.get("name", "Unknown")
            if isinstance(torrent_data, dict)
            else getattr(torrent_data, "name", "Unknown")
        )
        task = progress.add_task(f"Downloading {torrent_name}", total=100)

        # Add torrent to session with resume option
        info_hash_hex = await session.add_torrent(torrent_data, resume=resume)

        # Monitor progress
        while True:
            torrent_status = await session.get_torrent_status(info_hash_hex)
            if not torrent_status:
                break

            progress.update(task, completed=torrent_status.get("progress", 0) * 100)

            if torrent_status.get("status") == "seeding":
                console.print(f"[green]Download completed: {torrent_name}[/green]")
                break

            await asyncio.sleep(1)


async def show_status(session: AsyncSessionManager, console: Console) -> None:
    """Show client status."""
    # Create status table
    table = Table(title="ccBitTorrent Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")

    # Add status rows
    table.add_row("Session", "Running", f"Port: {session.config.network.listen_port}")
    table.add_row("Peers", "Connected", f"Active: {len(session.peers)}")
    table.add_row("Torrents", "Active", f"Count: {len(session.torrents)}")
    table.add_row(
        "DHT",
        "Enabled",
        f"Nodes: {session.dht.node_count if session.dht else 0}",
    )

    console.print(table)


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
    console.print("[yellow]Debug mode not yet implemented[/yellow]")


# Register external command groups at import time so they appear in --help
cli.add_command(config_group)
cli.add_command(config_extended)
cli.add_command(dashboard_cmd)
cli.add_command(alerts_cmd)
cli.add_command(metrics_cmd)
cli.add_command(performance_cmd)
cli.add_command(security_cmd)
cli.add_command(recover_cmd)
cli.add_command(test_cmd)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
