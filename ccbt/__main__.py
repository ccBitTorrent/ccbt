#!/usr/bin/env python3
"""ccBitTorrent - A BitTorrent client implementation
"""

import argparse
import sys
import time

from .dht import DHTClient
from .file_assembler import DownloadManager
from .magnet import (
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)
from .metadata_exchange import fetch_metadata_from_peers
from .session import SessionManager
from .torrent import TorrentParser
from .tracker import TrackerClient


def main():
    """Main entry point for the BitTorrent client."""
    parser = argparse.ArgumentParser(description="ccBitTorrent - A BitTorrent client")
    parser.add_argument("torrent", help="Path to torrent file, URL, or magnet URI")
    parser.add_argument("--port", type=int, default=6881,
                       help="Port to listen on (default: 6881)")
    parser.add_argument("--magnet", action="store_true", help="Treat input as a magnet URI")
    parser.add_argument("--daemon", action="store_true", help="Run long-lived multi-torrent session")
    parser.add_argument("--add", action="append", help="Add a torrent or magnet (repeatable)")
    parser.add_argument("--status", action="store_true", help="Show status and exit (daemon mode)")

    args = parser.parse_args()

    print("ccBitTorrent")

    try:
        # If daemon mode
        if args.daemon:
            session = SessionManager()
            if args.add:
                for item in args.add:
                    if item.startswith("magnet:"):
                        ih = session.add_magnet(item)
                        print(f"Added magnet: {ih}")
                    else:
                        ih = session.add_torrent(item)
                        print(f"Added torrent: {ih}")
            if args.status:
                print(session.status())
                return 0

            # Run until interrupted
            print("Session running. Press Ctrl+C to exit.")
            try:
                while True:
                    time.sleep(2)
            except KeyboardInterrupt:
                return 0

        # Step 2: Parse torrent or magnet (single-run mode)
        if args.magnet or args.torrent.startswith("magnet:"):
            mi = parse_magnet(args.torrent)
            torrent_data = build_minimal_torrent_data(mi.info_hash, mi.display_name, mi.trackers)
            print(f"Magnet: info hash {mi.info_hash.hex()}, trackers: {len(mi.trackers)}")
        else:
            torrent_parser = TorrentParser()
            torrent_data = torrent_parser.parse(args.torrent)

        print(f"Announce URL: {torrent_data['announce']}")
        print(f"Info hash: {torrent_data['info_hash'].hex()}")

        # Step 3: Contact tracker
        tracker = TrackerClient()
        response = tracker.announce(torrent_data)

        if response["status"] == 200:
            print(f"{response['status']} OK")
            print(f"Got {len(response['peers'])} peers")

            # Print first few peers as example
            for i, peer in enumerate(response["peers"][:5]):
                print(f"Peer {i} is ip: {peer['ip']} port: {peer['port']}")
            if len(response["peers"]) > 5:
                print("...")

        else:
            print(f"Tracker error: {response['status']}")
            return 1

        # If magnet minimal, try DHT peers
        if torrent_data.get("info") is None:
            try:
                dht = DHTClient()
                dht_peers = dht.get_peers(torrent_data["info_hash"])
                if dht_peers:
                    response.setdefault("peers", [])
                    # Merge unique
                    merged = {(p["ip"], p["port"]) for p in response["peers"]}
                    for ip, port in dht_peers:
                        if (ip, port) not in merged:
                            response["peers"].append({"ip": ip, "port": port})
                            merged.add((ip, port))
            except Exception:
                pass

        # If magnet without metadata, try to fetch metadata from peers
        if torrent_data.get("info") is None and response.get("peers"):
            try:
                info_dict = fetch_metadata_from_peers(torrent_data["info_hash"], response["peers"])
                if info_dict:
                    torrent_data = build_torrent_data_from_metadata(torrent_data["info_hash"], info_dict)
                    print("Fetched metadata via ut_metadata")
            except Exception as e:
                print(f"Metadata fetch failed: {e}")

        # Initialize download manager
        download_manager = DownloadManager(torrent_data)

        # Set up callbacks for monitoring
        def on_peer_connected(connection):
            print(f"[CONNECTED] Connected to peer: {connection.peer_info}")

        def on_peer_disconnected(connection):
            print(f"[DISCONNECTED] Disconnected from peer: {connection.peer_info}")

        def on_bitfield_received(connection, bitfield):
            print(f"[BITFIELD] Received bitfield from {connection.peer_info}: {len(bitfield.bitfield)} bytes")

        def on_piece_completed(piece_index):
            print(f"[PIECE] Piece {piece_index} downloaded and written to file")

        def on_piece_verified(piece_index):
            print(f"[VERIFIED] Piece {piece_index} verified")

        def on_file_assembled(piece_index):
            print(f"[FILE] Piece {piece_index} written to file")

        def on_download_complete():
            print("[COMPLETE] Download complete!")

        download_manager.on_peer_connected = on_peer_connected
        download_manager.on_peer_disconnected = on_peer_disconnected
        download_manager.on_bitfield_received = on_bitfield_received
        download_manager.on_piece_completed = on_piece_completed
        download_manager.on_piece_verified = on_piece_verified
        download_manager.on_file_assembled = on_file_assembled
        download_manager.on_download_complete = on_download_complete

        # Start download
        print(f"\n[PEERS] Connecting to {len(response['peers'])} peers...")
        download_manager.start_download(response["peers"])

        # Monitor progress
        print("\n[MONITOR] Monitoring download progress...")
        max_wait_time = 60  # Wait up to 60 seconds for completion
        wait_count = 0

        while wait_count < max_wait_time and not download_manager.download_complete:
            time.sleep(2)  # Check every 2 seconds

            status = download_manager.get_status()

            print(f"  Connected: {status['connected_peers']}, Active: {status['active_peers']}, Progress: {status['progress']*100:.1f}%")
            print(f"  Pieces: Missing={status['piece_status']['missing']}, Complete={status['piece_status']['complete']}, Verified={status['piece_status']['verified']}")

            # Show file creation progress
            files_created = sum(1 for exists in status["files_exist"].values() if exists)
            total_files = len(status["files_exist"])
            print(f"  Files: {files_created}/{total_files} created")

            wait_count += 2

            if download_manager.download_complete:
                break

        # Show final status
        print("\n[FINAL] Final Status:")
        status = download_manager.get_status()
        print(f"  Download progress: {status['progress']*100:.1f}%")
        print(f"  Assembly progress: {status['assembly_progress']*100:.1f}%")
        print(f"  Total time: {status['download_time']:.1f} seconds")

        # Show files
        print("\n  Files created:")
        for file_path, exists in status["files_exist"].items():
            if exists:
                size = status["file_sizes"][file_path]
                print(f"    OK {file_path}: {size} bytes")
            else:
                print(f"    MISSING {file_path}: not created")

        # Cleanup
        print("\n[SHUTDOWN] Shutting down...")
        download_manager.stop_download()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
