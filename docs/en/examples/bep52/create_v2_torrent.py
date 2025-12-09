#!/usr/bin/env python3
"""Example: Creating a BitTorrent Protocol v2 torrent.

This example demonstrates how to create a v2-only torrent file from a source file
or directory using the TorrentV2Parser.
"""

from pathlib import Path

from ccbt.core.bencode import decode
from ccbt.core.torrent_v2 import TorrentV2Parser


def create_v2_torrent_from_file():
    """Create v2 torrent from a single file."""
    # Create a test file
    test_file = Path("example_file.txt")
    test_file.write_bytes(b"Hello, BitTorrent v2!" * 1000)

    # Initialize parser
    parser = TorrentV2Parser()

    # Generate v2 torrent
    torrent_bytes = parser.generate_v2_torrent(
        source=test_file,
        output=Path("example_file.torrent"),
        trackers=[
            "http://tracker.example.com/announce",
            "udp://tracker.example.com:6969/announce",
        ],
        piece_length=16384,  # 16 KiB pieces
        comment="Example v2 torrent created with ccBitTorrent",
        created_by="ccBitTorrent v2 Example",
        private=False,
    )

    print("✅ V2 torrent created successfully!")
    print(f"   Output: example_file.torrent")
    print(f"   Size: {len(torrent_bytes)} bytes")

    # Parse and display info
    torrent_data = decode(torrent_bytes)
    v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

    print(f"\nTorrent Information:")
    print(f"  Name: {v2_info.name}")
    print(f"  Info Hash v2: {v2_info.info_hash_v2.hex()}")
    print(f"  Total Size: {v2_info.total_length:,} bytes")
    print(f"  Piece Length: {v2_info.piece_length:,} bytes")
    print(f"  Number of Pieces: {v2_info.num_pieces}")
    print(f"  Files: {len(v2_info.files)}")

    # Clean up
    test_file.unlink()


def create_v2_torrent_from_directory():
    """Create v2 torrent from a directory."""
    # Create test directory with files
    test_dir = Path("example_dir")
    test_dir.mkdir(exist_ok=True)

    (test_dir / "file1.txt").write_bytes(b"File 1 content " * 500)
    (test_dir / "file2.txt").write_bytes(b"File 2 content " * 500)
    (test_dir / "subdir").mkdir(exist_ok=True)
    (test_dir / "subdir" / "file3.txt").write_bytes(b"File 3 content " * 500)

    # Initialize parser
    parser = TorrentV2Parser()

    # Generate v2 torrent
    torrent_bytes = parser.generate_v2_torrent(
        source=test_dir,
        output=Path("example_dir.torrent"),
        trackers=["http://tracker.example.com/announce"],
        piece_length=None,  # Auto-calculate piece length
        comment="Multi-file v2 torrent example",
        private=False,
    )

    print("\n✅ Multi-file v2 torrent created successfully!")
    print(f"   Output: example_dir.torrent")
    print(f"   Size: {len(torrent_bytes)} bytes")

    # Parse and display info
    torrent_data = decode(torrent_bytes)
    v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

    print(f"\nTorrent Information:")
    print(f"  Name: {v2_info.name}")
    print(f"  Info Hash v2: {v2_info.info_hash_v2.hex()}")
    print(f"  Total Size: {v2_info.total_length:,} bytes")
    print(f"  Files: {len(v2_info.files)}")
    print(f"\n  File List:")
    for file_info in v2_info.files:
        print(f"    - {file_info.path_str}: {file_info.length:,} bytes")

    # Clean up
    import shutil

    shutil.rmtree(test_dir)


def main():
    """Run examples."""
    print("=" * 60)
    print("Creating BitTorrent Protocol v2 Torrents")
    print("=" * 60)

    print("\n1. Creating v2 torrent from single file...")
    print("-" * 60)
    create_v2_torrent_from_file()

    print("\n2. Creating v2 torrent from directory...")
    print("-" * 60)
    create_v2_torrent_from_directory()

    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

