"""Deprecated async_main compatibility shim.

This module is kept for backward compatibility in tests and external code.
It delegates functionality to canonical modules:
- AsyncSessionManager: ccbt.session.session
- AsyncDownloadManager and helpers: ccbt.session.download_manager
"""

from __future__ import annotations

import argparse
import asyncio

from ccbt.config.config import get_config, init_config
from ccbt.session.download_manager import (
    AsyncDownloadManager,
    download_magnet,
    download_torrent,
)
from ccbt.session.session import AsyncSessionManager

__all__ = [
    "AsyncDownloadManager",
    "AsyncSessionManager",
    "download_magnet",
    "download_torrent",
    "get_config",
    "main",
    "run_daemon",
    "sync_main",
]


async def run_daemon(args) -> None:
    """Minimal daemon loop for compatibility with legacy tests."""
    session = AsyncSessionManager()
    await session.start()
    try:
        # Add items if requested
        if getattr(args, "add", None):
            for item in args.add:
                try:
                    if isinstance(item, str) and item.startswith("magnet:"):
                        await session.add_magnet(item)
                    else:
                        await session.add_torrent(item)
                except Exception:
                    # Best-effort: ignore add errors to keep daemon alive
                    pass

        # Show status if requested
        if getattr(args, "status", False):
            try:
                await session.get_status()
            except Exception:
                pass

        # Legacy behavior: return immediately (tests expect quick exit)
    finally:
        await session.stop()


async def main() -> int:
    """Compatibility main() that mirrors legacy async_main behavior."""
    parser = argparse.ArgumentParser(
        description="ccBitTorrent (compat) - Async entry point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("torrent", nargs="?", help="Path to torrent file or magnet URI")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory")
    parser.add_argument("--port", type=int, help="Listen port (overrides config)")
    parser.add_argument("--max-peers", type=int, help="Max peers (overrides config)")
    parser.add_argument("--down-limit", type=int, help="Download limit KiB/s")
    parser.add_argument("--up-limit", type=int, help="Upload limit KiB/s")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument(
        "--magnet", action="store_true", help="Treat input as magnet URI"
    )
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument(
        "--add", action="append", help="Add torrent/magnet (daemon mode)"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show status (daemon mode)"
    )
    parser.add_argument("--metrics", action="store_true", help="Enable metrics server")
    parser.add_argument(
        "--streaming", action="store_true", help="Enable streaming mode"
    )

    args = parser.parse_args()

    # Initialize configuration (compat)
    config_manager = init_config(args.config)
    # Apply selected minimal overrides used by tests
    if args.port:
        config_manager.config.network.listen_port = args.port
    if args.max_peers:
        config_manager.config.network.max_global_peers = args.max_peers
    if args.down_limit:
        config_manager.config.network.global_down_kib = args.down_limit  # type: ignore[attr-defined]
    if args.up_limit:
        config_manager.config.network.global_up_kib = args.up_limit  # type: ignore[attr-defined]
    if args.log_level:
        config_manager.config.observability.log_level = args.log_level
    if args.streaming:
        config_manager.config.strategy.streaming_mode = True

    try:
        if args.daemon:
            await run_daemon(args)
            return 0
        if args.torrent:
            if args.magnet or str(args.torrent).startswith("magnet:"):
                await download_magnet(args.torrent, args.output_dir)
            else:
                await download_torrent(args.torrent, args.output_dir)
            return 0
        # No action provided
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        return 1
    finally:
        # Stop hot-reload if enabled in init_config
        if hasattr(config_manager.config, "_config_file") and getattr(
            config_manager.config, "_config_file", None
        ):
            try:
                config_manager.stop_hot_reload()
            except Exception:
                pass


def sync_main() -> int:
    """Synchronous wrapper for compatibility."""
    return asyncio.run(main())
