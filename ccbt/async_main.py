#!/usr/bin/env python3
"""ccBitTorrent - High-Performance Async BitTorrent Client.

from __future__ import annotations

Modern asyncio-based BitTorrent client with advanced performance optimizations.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
import time
from typing import TYPE_CHECKING, Any, Callable, cast

from ccbt.async_metadata_exchange import fetch_metadata_from_peers
from ccbt.async_peer_connection import AsyncPeerConnectionManager
from ccbt.async_piece_manager import AsyncPieceManager
from ccbt.config import Config, get_config, init_config

# from ccbt.disk_io import init_disk_io, shutdown_disk_io  # Functions don't exist yet
from ccbt.magnet import (
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)

# from ccbt.metrics import get_metrics_collector, init_metrics, shutdown_metrics  # Functions don't exist yet
from ccbt.torrent import TorrentParser

if TYPE_CHECKING:
    from ccbt.models import TorrentInfo


class AsyncDownloadManager:
    """High-performance async download manager."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | TorrentInfo,
        output_dir: str = ".",
        peer_id: bytes | None = None,
    ):
        """Initialize async download manager."""
        # Convert TorrentInfo to dict if needed
        if hasattr(torrent_data, "model_dump"):
            self.torrent_data = torrent_data.model_dump()  # type: ignore[call-arg]
        else:
            self.torrent_data = torrent_data
        self.output_dir = output_dir
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Initialize components
        if hasattr(torrent_data, "model_dump") and callable(torrent_data.model_dump):
            torrent_dict = torrent_data.model_dump()
        else:
            torrent_dict = torrent_data
        # Help type checker
        if not isinstance(torrent_dict, dict):
            msg = f"Expected dict for torrent_dict, got {type(torrent_dict)}"
            raise TypeError(msg)
        self.piece_manager = AsyncPieceManager(cast("dict[str, Any]", torrent_dict))
        self.peer_manager: AsyncPeerConnectionManager | None = None

        # State
        self.download_complete = False
        self.start_time: float | None = None
        self._background_tasks: set[asyncio.Task] = set()

        # Callbacks
        self.on_peer_connected: Callable | None = None
        self.on_peer_disconnected: Callable | None = None
        self.on_piece_completed: Callable | None = None
        self.on_download_complete: Callable | None = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the download manager."""
        await self.piece_manager.start()
        self.logger.info("Async download manager started")

    async def stop(self) -> None:
        """Stop the download manager."""
        if self.peer_manager:
            await self.peer_manager.stop()
        await self.piece_manager.stop()
        self.logger.info("Async download manager stopped")

    async def start_download(self, peers: list[dict[str, Any]]) -> None:
        """Start the download process."""
        self.start_time = time.time()

        # Initialize peer manager
        self.peer_manager = AsyncPeerConnectionManager(
            self.torrent_data,
            self.piece_manager,
            self.our_peer_id,
        )

        # Set up callbacks
        self.peer_manager.on_peer_connected = self._on_peer_connected
        self.peer_manager.on_peer_disconnected = self._on_peer_disconnected
        self.peer_manager.on_piece_received = self._on_piece_received
        self.peer_manager.on_bitfield_received = self._on_bitfield_received

        self.piece_manager.on_piece_completed = self._on_piece_completed
        self.piece_manager.on_piece_verified = self._on_piece_verified
        self.piece_manager.on_download_complete = self._on_download_complete

        # Start peer manager
        await self.peer_manager.start()

        # Connect to peers
        self.logger.info("Connecting to %s peers...", len(peers))
        await self.peer_manager.connect_to_peers(peers)

        # Start piece download
        self.logger.info("Starting piece download...")
        await self.piece_manager.start_download(self.peer_manager)

        self.logger.info("Download started successfully!")

    async def get_status(self) -> dict[str, Any]:
        """Get current download status."""
        piece_status = self.piece_manager.get_piece_status()
        progress = self.piece_manager.get_download_progress()

        connected_peers = 0
        active_peers = 0
        if self.peer_manager:
            connected_peers = len(self.peer_manager.get_connected_peers())
            active_peers = len(self.peer_manager.get_active_peers())

        return {
            "progress": progress,
            "piece_status": piece_status,
            "connected_peers": connected_peers,
            "active_peers": active_peers,
            "download_time": time.time() - self.start_time if self.start_time else 0,
            "download_complete": self.download_complete,
        }

    def _on_peer_connected(self, connection) -> None:
        """Handle peer connection."""
        self.logger.info("Connected to peer: %s", connection.peer_info)
        if self.on_peer_connected:
            self.on_peer_connected(connection)

    def _on_peer_disconnected(self, connection) -> None:
        """Handle peer disconnection."""
        self.logger.info("Disconnected from peer: %s", connection.peer_info)
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

    def _on_bitfield_received(self, connection, _bitfield) -> None:
        """Handle bitfield reception."""
        self.logger.debug("Received bitfield from %s", connection.peer_info)

    def _on_piece_received(self, connection, piece_message) -> None:
        """Handle piece reception."""
        # Update peer availability
        task = asyncio.create_task(
            self.piece_manager.update_peer_have(
                str(connection.peer_info),
                piece_message.piece_index,
            ),
        )
        # Store task reference to avoid dangling task warning
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Handle piece block
        task = asyncio.create_task(
            self.piece_manager.handle_piece_block(
                piece_message.piece_index,
                piece_message.begin,
                piece_message.block,
            ),
        )
        # Store task reference to avoid dangling task warning
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _on_piece_completed(self, piece_index: int) -> None:
        """Handle piece completion."""
        self.logger.info("Completed piece %s", piece_index)
        if self.on_piece_completed:
            self.on_piece_completed(piece_index)

    def _on_piece_verified(self, piece_index: int) -> None:
        """Handle piece verification."""
        self.logger.info("Verified piece %s", piece_index)

        # Broadcast HAVE to peers
        if self.peer_manager:
            task = asyncio.create_task(self.peer_manager.broadcast_have(piece_index))
            # Store task reference to avoid dangling task warning
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def _on_download_complete(self) -> None:
        """Handle download completion."""
        self.download_complete = True
        self.logger.info("Download complete!")

        if self.on_download_complete:
            self.on_download_complete()


class AsyncSessionManager:
    """Async session manager for multiple torrents."""

    def __init__(self, config: Config | None = None):
        """Initialize async session manager."""
        self.config = config or get_config()
        self.torrents: dict[str, AsyncDownloadManager] = {}
        # Placeholder - metrics collector doesn't exist yet
        # self.metrics = get_metrics_collector()

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the session manager."""
        # Initialize disk I/O (placeholder - functions don't exist yet)
        # await init_disk_io()

        # Initialize metrics (placeholder - functions don't exist yet)
        # await init_metrics()

        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the session manager."""
        # Stop all torrents
        for torrent_id in list(self.torrents.keys()):
            await self.remove_torrent(torrent_id)

        # Shutdown services
        # Shutdown metrics (placeholder - functions don't exist yet)
        # await shutdown_metrics()

        # Shutdown disk I/O (placeholder - functions don't exist yet)
        # await shutdown_disk_io()

        self.logger.info("Async session manager stopped")

    async def add_torrent(self, torrent_path: str, output_dir: str = ".") -> str:
        """Add a torrent file."""
        try:
            # Parse torrent
            parser = TorrentParser()
            torrent_data = parser.parse(torrent_path)
            torrent_id = torrent_data.info_hash.hex()

            # Create download manager
            download_manager = AsyncDownloadManager(torrent_data, output_dir)
            await download_manager.start()

            # Store torrent
            self.torrents[torrent_id] = download_manager

            self.logger.info("Added torrent: %s", torrent_id)
        except Exception:
            self.logger.exception("Failed to add torrent %s", torrent_path)
            raise
        else:
            return torrent_id

    async def add_magnet(self, magnet_uri: str, output_dir: str = ".") -> str:
        """Add a magnet link."""
        try:
            # Parse magnet
            magnet_info = parse_magnet(magnet_uri)
            torrent_data = build_minimal_torrent_data(
                magnet_info.info_hash,
                magnet_info.display_name,
                magnet_info.trackers,
            )

            # Try to fetch metadata from peers
            if magnet_info.trackers:
                # Get peers from trackers first
                # TODO: Implement async tracker client
                peers = []

                # Fetch metadata
                metadata = await fetch_metadata_from_peers(
                    magnet_info.info_hash,
                    peers,
                )

                if metadata:
                    torrent_data = build_torrent_data_from_metadata(
                        magnet_info.info_hash,
                        metadata,
                    )

            torrent_id = torrent_data["info_hash"].hex()

            # Create download manager
            download_manager = AsyncDownloadManager(torrent_data, output_dir)
            await download_manager.start()

            # Store torrent
            self.torrents[torrent_id] = download_manager

            self.logger.info("Added magnet: %s", torrent_id)
        except Exception:
            self.logger.exception("Failed to add magnet %s", magnet_uri)
            raise
        else:
            return torrent_id

    async def remove_torrent(self, torrent_id: str) -> bool:
        """Remove a torrent."""
        if torrent_id in self.torrents:
            download_manager = self.torrents.pop(torrent_id)
            await download_manager.stop()
            self.logger.info("Removed torrent: %s", torrent_id)
            return True
        return False

    async def get_status(self, torrent_id: str | None = None) -> dict[str, Any]:
        """Get status for a specific torrent or all torrents."""
        if torrent_id:
            if torrent_id in self.torrents:
                return await self.torrents[torrent_id].get_status()
            return {}

        # Return status for all torrents
        status = {}
        for tid, download_manager in self.torrents.items():
            status[tid] = await download_manager.get_status()

        return status


async def download_torrent(torrent_path: str, output_dir: str = ".") -> None:
    """Download a single torrent file."""
    try:
        # Parse torrent
        parser = TorrentParser()
        torrent_data = parser.parse(torrent_path)

        # Create download manager
        download_manager = AsyncDownloadManager(torrent_data, output_dir)
        await download_manager.start()

        # Set up progress monitoring
        async def monitor_progress():
            while not download_manager.download_complete:
                status = await download_manager.get_status()
                status["progress"] * 100
                status["connected_peers"]
                await asyncio.sleep(1)

        # Start monitoring
        monitor_task = asyncio.create_task(monitor_progress())

        # TODO: Implement tracker announce and peer discovery
        # For now, we'll just show the torrent info

        # Wait for completion or timeout
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(monitor_task, timeout=10.0)

        await download_manager.stop()

    except (OSError, RuntimeError, asyncio.CancelledError):
        # Ignore cleanup errors during shutdown
        pass  # Cleanup errors are expected during shutdown


async def download_magnet(magnet_uri: str, _output_dir: str = ".") -> None:
    """Download from a magnet link."""
    try:
        # Parse magnet
        magnet_info = parse_magnet(magnet_uri)

        # Try to fetch metadata
        metadata = await fetch_metadata_from_peers(magnet_info.info_hash, [])

        if metadata:
            # TODO: Continue with download
            pass
        else:
            pass

    except (ValueError, RuntimeError, asyncio.CancelledError):
        # Ignore magnet download errors
        pass  # Magnet download errors are expected


async def run_daemon(args) -> None:
    """Run in daemon mode."""
    session = AsyncSessionManager()
    await session.start()

    try:
        # Add torrents/magnets
        if args.add:
            for item in args.add:
                if item.startswith("magnet:"):
                    await session.add_magnet(item)
                else:
                    await session.add_torrent(item)

        # Show status if requested
        if args.status:
            status = await session.get_status()
            for torrent_status in status.values():
                torrent_status["progress"] * 100
            return

        # Run until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

    finally:
        await session.stop()


async def main() -> int:
    """Main async entry point."""
    parser = argparse.ArgumentParser(
        description="ccBitTorrent - High-Performance Async BitTorrent Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ccbt torrent.torrent                    # Download torrent file
  python -m ccbt "magnet:?xt=..."                  # Download from magnet
  python -m ccbt --daemon --add torrent.torrent    # Run daemon mode
  python -m ccbt --config custom.toml torrent.torrent  # Use custom config
        """,
    )

    parser.add_argument("torrent", nargs="?", help="Path to torrent file or magnet URI")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory")
    parser.add_argument("--port", type=int, help="Listen port (overrides config)")
    parser.add_argument("--max-peers", type=int, help="Max peers (overrides config)")
    parser.add_argument(
        "--down-limit",
        type=int,
        help="Download limit KiB/s (overrides config)",
    )
    parser.add_argument(
        "--up-limit",
        type=int,
        help="Upload limit KiB/s (overrides config)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (overrides config)",
    )
    parser.add_argument(
        "--magnet",
        action="store_true",
        help="Treat input as magnet URI",
    )
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument(
        "--add",
        action="append",
        help="Add torrent/magnet (daemon mode)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status (daemon mode)",
    )
    parser.add_argument("--metrics", action="store_true", help="Enable metrics server")
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Enable streaming mode",
    )

    args = parser.parse_args()

    # Initialize configuration
    config_manager = init_config(args.config)

    # Apply CLI overrides
    if args.port:
        config_manager.config.network.listen_port = args.port
    if args.max_peers:
        config_manager.config.network.max_global_peers = args.max_peers
    if args.down_limit:
        config_manager.config.limits.global_down_kib = args.down_limit
    if args.up_limit:
        config_manager.config.limits.global_up_kib = args.up_limit
    if args.log_level:
        config_manager.config.observability.log_level = args.log_level
    if args.streaming:
        config_manager.config.strategy.streaming_mode = True

    # Start hot-reload if config file exists
    if hasattr(config_manager.config, "_config_file") and getattr(
        config_manager.config, "_config_file", None
    ):
        await config_manager.start_hot_reload()

    try:
        if args.daemon:
            await run_daemon(args)
        elif args.torrent:
            if args.magnet or args.torrent.startswith("magnet:"):
                await download_magnet(args.torrent, args.output_dir)
            else:
                await download_torrent(args.torrent, args.output_dir)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        return 0
    except Exception:
        return 1
    finally:
        # Stop hot-reload
        if hasattr(config_manager.config, "_config_file") and getattr(
            config_manager.config, "_config_file", None
        ):
            config_manager.stop_hot_reload()

    return 0


def sync_main() -> int:
    """Synchronous entry point."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(sync_main())
