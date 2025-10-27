#!/usr/bin/env python3
"""ccBitTorrent - High-Performance Async BitTorrent Client

Modern asyncio-based BitTorrent client with advanced performance optimizations.
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import Any, Dict, List, Optional

from .async_metadata_exchange import fetch_metadata_from_peers
from .async_peer_connection import AsyncPeerConnectionManager
from .async_piece_manager import AsyncPieceManager
from .config import Config, get_config, init_config
from .disk_io import init_disk_io, shutdown_disk_io
from .magnet import (
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)
from .metrics import get_metrics_collector, init_metrics, shutdown_metrics
from .torrent import TorrentParser


class AsyncDownloadManager:
    """High-performance async download manager."""

    def __init__(self, torrent_data: Dict[str, Any], output_dir: str = ".",
                 peer_id: Optional[bytes] = None):
        """Initialize async download manager."""
        self.torrent_data = torrent_data
        self.output_dir = output_dir
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Initialize components
        self.piece_manager = AsyncPieceManager(torrent_data)
        self.peer_manager: Optional[AsyncPeerConnectionManager] = None

        # State
        self.download_complete = False
        self.start_time: Optional[float] = None

        # Callbacks
        self.on_peer_connected: Optional[callable] = None
        self.on_peer_disconnected: Optional[callable] = None
        self.on_piece_completed: Optional[callable] = None
        self.on_download_complete: Optional[callable] = None

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

    async def start_download(self, peers: List[Dict[str, Any]]) -> None:
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
        self.logger.info(f"Connecting to {len(peers)} peers...")
        await self.peer_manager.connect_to_peers(peers)

        # Start piece download
        self.logger.info("Starting piece download...")
        await self.piece_manager.start_download(self.peer_manager)

        self.logger.info("Download started successfully!")

    async def get_status(self) -> Dict[str, Any]:
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
        self.logger.info(f"Connected to peer: {connection.peer_info}")
        if self.on_peer_connected:
            self.on_peer_connected(connection)

    def _on_peer_disconnected(self, connection) -> None:
        """Handle peer disconnection."""
        self.logger.info(f"Disconnected from peer: {connection.peer_info}")
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

    def _on_bitfield_received(self, connection, bitfield) -> None:
        """Handle bitfield reception."""
        self.logger.debug(f"Received bitfield from {connection.peer_info}")

    def _on_piece_received(self, connection, piece_message) -> None:
        """Handle piece reception."""
        # Update peer availability
        asyncio.create_task(self.piece_manager.update_peer_have(
            str(connection.peer_info), piece_message.piece_index,
        ))

        # Handle piece block
        asyncio.create_task(self.piece_manager.handle_piece_block(
            piece_message.piece_index, piece_message.begin, piece_message.block,
        ))

    def _on_piece_completed(self, piece_index: int) -> None:
        """Handle piece completion."""
        self.logger.info(f"Completed piece {piece_index}")
        if self.on_piece_completed:
            self.on_piece_completed(piece_index)

    def _on_piece_verified(self, piece_index: int) -> None:
        """Handle piece verification."""
        self.logger.info(f"Verified piece {piece_index}")

        # Broadcast HAVE to peers
        if self.peer_manager:
            asyncio.create_task(self.peer_manager.broadcast_have(piece_index))

    def _on_download_complete(self) -> None:
        """Handle download completion."""
        self.download_complete = True
        self.logger.info("Download complete!")

        if self.on_download_complete:
            self.on_download_complete()


class AsyncSessionManager:
    """Async session manager for multiple torrents."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize async session manager."""
        self.config = config or get_config()
        self.torrents: Dict[str, AsyncDownloadManager] = {}
        self.metrics = get_metrics_collector()

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the session manager."""
        # Initialize disk I/O
        await init_disk_io()

        # Initialize metrics
        await init_metrics()

        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the session manager."""
        # Stop all torrents
        for torrent_id in list(self.torrents.keys()):
            await self.remove_torrent(torrent_id)

        # Shutdown services
        await shutdown_metrics()
        await shutdown_disk_io()

        self.logger.info("Async session manager stopped")

    async def add_torrent(self, torrent_path: str, output_dir: str = ".") -> str:
        """Add a torrent file."""
        try:
            # Parse torrent
            parser = TorrentParser()
            torrent_data = parser.parse(torrent_path)
            torrent_id = torrent_data["info_hash"].hex()

            # Create download manager
            download_manager = AsyncDownloadManager(torrent_data, output_dir)
            await download_manager.start()

            # Store torrent
            self.torrents[torrent_id] = download_manager

            self.logger.info(f"Added torrent: {torrent_id}")
            return torrent_id

        except Exception as e:
            self.logger.error(f"Failed to add torrent {torrent_path}: {e}")
            raise

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
                    magnet_info.info_hash, peers,
                )

                if metadata:
                    torrent_data = build_torrent_data_from_metadata(
                        magnet_info.info_hash, metadata,
                    )

            torrent_id = torrent_data["info_hash"].hex()

            # Create download manager
            download_manager = AsyncDownloadManager(torrent_data, output_dir)
            await download_manager.start()

            # Store torrent
            self.torrents[torrent_id] = download_manager

            self.logger.info(f"Added magnet: {torrent_id}")
            return torrent_id

        except Exception as e:
            self.logger.error(f"Failed to add magnet {magnet_uri}: {e}")
            raise

    async def remove_torrent(self, torrent_id: str) -> bool:
        """Remove a torrent."""
        if torrent_id in self.torrents:
            download_manager = self.torrents.pop(torrent_id)
            await download_manager.stop()
            self.logger.info(f"Removed torrent: {torrent_id}")
            return True
        return False

    async def get_status(self, torrent_id: Optional[str] = None) -> Dict[str, Any]:
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

        print(f"Torrent: {torrent_data.get('file_info', {}).get('name', 'Unknown')}")
        print(f"Info hash: {torrent_data['info_hash'].hex()}")
        print(f"Announce: {torrent_data.get('announce', 'Unknown')}")

        # Create download manager
        download_manager = AsyncDownloadManager(torrent_data, output_dir)
        await download_manager.start()

        # Set up progress monitoring
        async def monitor_progress():
            while not download_manager.download_complete:
                status = await download_manager.get_status()
                progress = status["progress"] * 100
                peers = status["connected_peers"]
                print(f"\rProgress: {progress:.1f}% | Peers: {peers}", end="", flush=True)
                await asyncio.sleep(1)
            print()  # New line after progress

        # Start monitoring
        monitor_task = asyncio.create_task(monitor_progress())

        # TODO: Implement tracker announce and peer discovery
        # For now, we'll just show the torrent info
        print("Note: Full peer discovery and download not yet implemented")
        print("This is a demonstration of the async architecture")

        # Wait for completion or timeout
        try:
            await asyncio.wait_for(monitor_task, timeout=10.0)
        except asyncio.TimeoutError:
            print("\nTimeout reached")

        await download_manager.stop()

    except Exception as e:
        print(f"Error downloading torrent: {e}")


async def download_magnet(magnet_uri: str, output_dir: str = ".") -> None:
    """Download from a magnet link."""
    try:
        # Parse magnet
        magnet_info = parse_magnet(magnet_uri)
        print(f"Magnet: {magnet_info.display_name}")
        print(f"Info hash: {magnet_info.info_hash.hex()}")
        print(f"Trackers: {len(magnet_info.trackers)}")

        # Try to fetch metadata
        print("Fetching metadata from peers...")
        metadata = await fetch_metadata_from_peers(magnet_info.info_hash, [])

        if metadata:
            print("Metadata fetched successfully!")
            # TODO: Continue with download
        else:
            print("Failed to fetch metadata")

    except Exception as e:
        print(f"Error downloading magnet: {e}")


async def run_daemon(args) -> None:
    """Run in daemon mode."""
    session = AsyncSessionManager()
    await session.start()

    try:
        # Add torrents/magnets
        if args.add:
            for item in args.add:
                if item.startswith("magnet:"):
                    torrent_id = await session.add_magnet(item)
                    print(f"Added magnet: {torrent_id}")
                else:
                    torrent_id = await session.add_torrent(item)
                    print(f"Added torrent: {torrent_id}")

        # Show status if requested
        if args.status:
            status = await session.get_status()
            print("Session status:")
            for torrent_id, torrent_status in status.items():
                progress = torrent_status["progress"] * 100
                print(f"  {torrent_id}: {progress:.1f}% complete")
            return

        # Run until interrupted
        print("Daemon running. Press Ctrl+C to exit.")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")

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
    parser.add_argument("--down-limit", type=int, help="Download limit KiB/s (overrides config)")
    parser.add_argument("--up-limit", type=int, help="Upload limit KiB/s (overrides config)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                      help="Log level (overrides config)")
    parser.add_argument("--magnet", action="store_true", help="Treat input as magnet URI")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--add", action="append", help="Add torrent/magnet (daemon mode)")
    parser.add_argument("--status", action="store_true", help="Show status (daemon mode)")
    parser.add_argument("--metrics", action="store_true", help="Enable metrics server")
    parser.add_argument("--streaming", action="store_true", help="Enable streaming mode")

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
    if config_manager.config._config_file:
        await config_manager.start_hot_reload()

    print("ccBitTorrent - High-Performance Async BitTorrent Client")
    print(f"Config: {config_manager.config._config_file or 'defaults'}")
    print(f"Log level: {config_manager.config.observability.log_level.value}")

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

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        # Stop hot-reload
        if config_manager.config._config_file:
            await config_manager.stop_hot_reload()


def main() -> int:
    """Synchronous entry point."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(main())
