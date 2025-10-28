#!/usr/bin/env python3
"""ccBitTorrent - A BitTorrent client implementation."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from typing import Any, cast

from ccbt.dht import DHTClient
from ccbt.file_assembler import DownloadManager
from ccbt.magnet import (
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)
from ccbt.metadata_exchange import fetch_metadata_from_peers
from ccbt.session import SessionManager
from ccbt.torrent import TorrentParser
from ccbt.tracker import TrackerClient

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the BitTorrent client."""
    parser = argparse.ArgumentParser(description="ccBitTorrent - A BitTorrent client")
    parser.add_argument("torrent", help="Path to torrent file, URL, or magnet URI")
    parser.add_argument(
        "--port",
        type=int,
        default=6881,
        help="Port to listen on (default: 6881)",
    )
    parser.add_argument(
        "--magnet",
        action="store_true",
        help="Treat input as a magnet URI",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run long-lived multi-torrent session",
    )
    parser.add_argument(
        "--add",
        action="append",
        help="Add a torrent or magnet (repeatable)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status and exit (daemon mode)",
    )

    args = parser.parse_args()

    try:
        # If daemon mode
        if args.daemon:
            session = SessionManager()
            if args.add:
                for item in args.add:
                    if item.startswith("magnet:"):
                        session.add_magnet(item)
                    else:
                        session.add_torrent(item)
            if args.status:
                return 0

            # Run until interrupted
            try:
                while True:
                    time.sleep(2)
            except KeyboardInterrupt:
                return 0

        # Step 2: Parse torrent or magnet (single-run mode)
        if args.magnet or args.torrent.startswith("magnet:"):
            mi = parse_magnet(args.torrent)
            torrent_data = build_minimal_torrent_data(
                mi.info_hash,
                mi.display_name,
                mi.trackers,
            )
        else:
            torrent_parser = TorrentParser()
            torrent_data = torrent_parser.parse(args.torrent)

        # Step 3: Contact tracker
        tracker = TrackerClient()
        # TrackerClient.announce expects dict[str, Any]; convert if TorrentInfo
        if hasattr(torrent_data, "model_dump") and callable(torrent_data.model_dump):
            announce_input = torrent_data.model_dump()
        else:
            announce_input = torrent_data
        # Type assertion to help type checker
        if not isinstance(announce_input, dict):
            msg = f"Expected dict for announce_input, got {type(announce_input)}"
            raise TypeError(msg)
        response = tracker.announce(cast("dict[str, Any]", announce_input))

        if response["status"] == 200:
            # Print first few peers as example
            for _i, _peer in enumerate(response["peers"][:5]):
                pass
            if len(response["peers"]) > 5:
                pass

        else:
            return 1

        # If magnet minimal, try DHT peers
        # For magnets without full metadata, info may be missing
        td_info_missing = False
        if hasattr(torrent_data, "model_dump"):
            td_info_missing = False  # TorrentInfo always has info-derived fields
        elif isinstance(torrent_data, dict):
            td_info_missing = torrent_data.get("info") is None
        if td_info_missing:
            try:
                info_hash = (
                    torrent_data["info_hash"]
                    if isinstance(torrent_data, dict)
                    else torrent_data.info_hash
                )

                async def _lookup_dht_peers() -> list[tuple[str, int]]:
                    dht = DHTClient()
                    await dht.start()
                    try:
                        return await dht.get_peers(info_hash)
                    finally:
                        await dht.stop()

                dht_peers = asyncio.run(_lookup_dht_peers())
                if dht_peers:
                    response.setdefault("peers", [])
                    # Merge unique
                    merged = {(p["ip"], p["port"]) for p in response["peers"]}
                    for ip, port in dht_peers:
                        if (ip, port) not in merged:
                            response["peers"].append({"ip": ip, "port": port})
                            merged.add((ip, port))
            except Exception as e:
                logger.debug("Failed to merge DHT peers: %s", e)

        # If magnet without metadata, try to fetch metadata from peers
        if td_info_missing and response.get("peers"):
            try:
                info_hash = (
                    torrent_data["info_hash"]
                    if isinstance(torrent_data, dict)
                    else torrent_data.info_hash
                )
                info_dict = fetch_metadata_from_peers(
                    info_hash,
                    response["peers"],
                )
                if info_dict:
                    torrent_data = build_torrent_data_from_metadata(
                        info_hash,
                        info_dict,
                    )
            except Exception as e:
                logger.debug("Failed to fetch metadata: %s", e)

        # Initialize download manager
        if hasattr(torrent_data, "model_dump") and callable(torrent_data.model_dump):
            dm_input = torrent_data.model_dump()
        else:
            dm_input = torrent_data
        # Type assertion to help type checker
        if not isinstance(dm_input, dict):
            msg = f"Expected dict for dm_input, got {type(dm_input)}"
            raise TypeError(msg)
        download_manager = DownloadManager(cast("dict[str, Any]", dm_input))

        # Set up callbacks for monitoring
        def on_peer_connected(connection: Any) -> None:
            pass

        def on_peer_disconnected(connection: Any) -> None:
            pass

        def on_bitfield_received(connection: Any, bitfield: Any) -> None:
            pass

        def on_piece_completed(piece_index: Any) -> None:
            pass

        def on_piece_verified(piece_index: Any) -> None:
            pass

        def on_file_assembled(piece_index: Any) -> None:
            pass

        def on_download_complete() -> None:
            pass

        if hasattr(download_manager, "on_peer_connected"):
            download_manager.on_peer_connected = on_peer_connected  # type: ignore[assignment]
        if hasattr(download_manager, "on_peer_disconnected"):
            download_manager.on_peer_disconnected = on_peer_disconnected  # type: ignore[assignment]
        if hasattr(download_manager, "on_bitfield_received"):
            download_manager.on_bitfield_received = on_bitfield_received  # type: ignore[assignment]
        if hasattr(download_manager, "on_piece_completed"):
            download_manager.on_piece_completed = on_piece_completed  # type: ignore[assignment]
        if hasattr(download_manager, "on_piece_verified"):
            download_manager.on_piece_verified = on_piece_verified  # type: ignore[assignment]
        if hasattr(download_manager, "on_file_assembled"):
            download_manager.on_file_assembled = on_file_assembled  # type: ignore[assignment]
        if hasattr(download_manager, "on_download_complete"):
            download_manager.on_download_complete = on_download_complete  # type: ignore[assignment]

        # Start download
        download_manager.start_download(response["peers"])

        # Monitor progress
        max_wait_time = 60  # Wait up to 60 seconds for completion
        wait_count = 0

        while wait_count < max_wait_time and not download_manager.download_complete:
            time.sleep(2)  # Check every 2 seconds

            status = download_manager.get_status()

            # Show file creation progress
            sum(1 for exists in status["files_exist"].values() if exists)
            len(status["files_exist"])

            wait_count += 2

            if download_manager.download_complete:
                break

        # Show final status
        status = download_manager.get_status()

        # Show files
        for file_path, exists in status["files_exist"].items():
            if exists:
                status["file_sizes"][file_path]
            else:
                pass

        # Cleanup
        # Ensure dm_input is properly typed for stop_download
        if not isinstance(dm_input, dict):
            msg = f"Expected dict for dm_input, got {type(dm_input)}"
            raise TypeError(msg)
        download_manager.stop_download(cast("dict[str, Any]", dm_input))

    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
