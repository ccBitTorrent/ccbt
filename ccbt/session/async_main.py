"""Deprecated async_main compatibility shim.

This module is kept for backward compatibility in tests and external code.
It delegates functionality to canonical modules:
- AsyncSessionManager: ccbt.session.session
- AsyncDownloadManager and helpers: ccbt.session.download_manager
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib

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
            with contextlib.suppress(Exception):
                await session.get_status()

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

    # Track active session managers and download managers for cleanup
    active_sessions = []
    active_download_managers = []

    try:
        if args.daemon:
            session = AsyncSessionManager()
            active_sessions.append(session)
            await session.start()
            await run_daemon(args)
            return 0
        if args.torrent:
            # For single downloads, we need to ensure proper cleanup
            try:
                if args.magnet or str(args.torrent).startswith("magnet:"):
                    dm = await download_magnet(args.torrent, args.output_dir)
                    if dm:
                        active_download_managers.append(dm)
                else:
                    dm = await download_torrent(args.torrent, args.output_dir)
                    if dm:
                        active_download_managers.append(dm)
                return 0
            except KeyboardInterrupt:
                # Ensure all background tasks are properly cancelled and awaited
                logger = logging.getLogger(__name__)
                logger.info("Received KeyboardInterrupt, shutting down gracefully...")

                # Stop download managers first
                for dm in active_download_managers:
                    try:
                        await dm.stop()
                        logger.info("Download manager stopped successfully")
                    except Exception as e:
                        logger.warning(f"Error stopping download manager: {e}")

                # Give tasks a moment to start their cancellation handlers
                await asyncio.sleep(0.1)

                # Cancel all remaining tasks in the event loop
                current_task = asyncio.current_task()
                all_tasks = [t for t in asyncio.all_tasks() if t != current_task and not t.done()]

                if all_tasks:
                    logger.info(f"Cancelling {len(all_tasks)} remaining background tasks...")
                    for task in all_tasks:
                        task.cancel()

                    # Wait for all tasks to complete their cancellation
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*all_tasks, return_exceptions=True),
                            timeout=5.0
                        )
                        logger.info("All background tasks cancelled successfully")
                    except asyncio.TimeoutError:
                        logger.warning("Some background tasks did not cancel within timeout")
                    except Exception as e:
                        logger.warning(f"Error during task cancellation: {e}")

                return 0
        # No action provided
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        return 1
    finally:
        # Clean up active sessions
        for session in active_sessions:
            try:
                await session.stop()
            except Exception as e:
                logging.getLogger(__name__).debug(f"Error stopping session: {e}")

        # Clean up active download managers
        for dm in active_download_managers:
            try:
                await dm.stop()
            except Exception as e:
                logging.getLogger(__name__).debug(f"Error stopping download manager: {e}")

        # Stop hot-reload if enabled in init_config
        if hasattr(config_manager.config, "_config_file") and getattr(
            config_manager.config, "_config_file", None
        ):
            with contextlib.suppress(Exception):
                config_manager.stop_hot_reload()


def sync_main() -> int:
    """Synchronous wrapper for compatibility."""
    return asyncio.run(main())
