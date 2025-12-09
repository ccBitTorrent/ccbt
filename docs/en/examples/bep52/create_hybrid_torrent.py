#!/usr/bin/env python3
"""Example: Creating a hybrid BitTorrent torrent (v1 + v2).

This example demonstrates how to create a hybrid torrent that is compatible
with both v1 and v2 BitTorrent clients.
"""

from pathlib import Path

from ccbt.core.bencode import decode
from ccbt.core.torrent_v2 import TorrentV2Parser


def create_hybrid_torrent():
    """Create hybrid torrent compatible with both v1 and v2 clients."""
    # Create a test file
    test_file = Path("hybrid_example.txt")
    test_file.write_bytes(b"Hybrid torrent content " * 2000)

    # Initialize parser
    parser = TorrentV2Parser()

    # Generate hybrid torrent
    print("Creating hybrid torrent...")
    torrent_bytes = parser.generate_hybrid_torrent(
        source=test_file,
        output=Path("hybrid_example.torrent"),
        trackers=[
            "http://tracker1.example.com/announce",
            "http://tracker2.example.com/announce",
            "udp://tracker3.example.com:6969/announce",
        ],
        piece_length=16384,  # 16 KiB pieces
        comment="Hybrid torrent supporting both v1 and v2 clients",
        created_by="ccBitTorrent Hybrid Example",
        private=False,
    )

    print("✅ Hybrid torrent created successfully!")
    print(f"   Output: hybrid_example.torrent")
    print(f"   Size: {len(torrent_bytes)} bytes")

    # Parse torrent to show both v1 and v2 information
    torrent_data = decode(torrent_bytes)
    v1_info, v2_info = parser.parse_hybrid(torrent_data[b"info"], torrent_data)

    print(f"\nHybrid Torrent Information:")
    print(f"  Name: {v2_info.name}")
    print(f"  Meta Version: 3 (Hybrid)")
    print(f"\n  V1 Information:")
    print(f"    Info Hash v1 (SHA-1): {v2_info.info_hash_v1.hex()}")
    print(f"    Pieces (SHA-1): {len(torrent_data[b'info'][b'pieces']) // 20}")
    print(f"\n  V2 Information:")
    print(f"    Info Hash v2 (SHA-256): {v2_info.info_hash_v2.hex()}")
    print(f"    File Tree Entries: {len(v2_info.file_tree)}")
    print(f"    Piece Layers: {len(v2_info.piece_layers)}")

    print(f"\n  Shared Information:")
    print(f"    Total Size: {v2_info.total_length:,} bytes")
    print(f"    Piece Length: {v2_info.piece_length:,} bytes")
    print(f"    Number of Pieces: {v2_info.num_pieces}")

    # Clean up
    test_file.unlink()


def create_hybrid_multi_file_torrent():
    """Create hybrid multi-file torrent."""
    # Create test directory
    test_dir = Path("hybrid_dir")
    test_dir.mkdir(exist_ok=True)

    (test_dir / "document.txt").write_bytes(b"Document content " * 1000)
    (test_dir / "image.bin").write_bytes(b"\x89PNG" + b"\x00" * 5000)
    (test_dir / "data").mkdir(exist_ok=True)
    (test_dir / "data" / "data.dat").write_bytes(b"Binary data " * 800)

    # Initialize parser
    parser = TorrentV2Parser()

    # Generate hybrid torrent
    print("\nCreating hybrid multi-file torrent...")
    torrent_bytes = parser.generate_hybrid_torrent(
        source=test_dir,
        output=Path("hybrid_dir.torrent"),
        trackers=["http://tracker.example.com/announce"],
        web_seeds=["http://webseed.example.com/files/"],
        comment="Hybrid multi-file torrent",
        private=False,
    )

    print("✅ Hybrid multi-file torrent created!")
    print(f"   Output: hybrid_dir.torrent")

    # Parse and display
    torrent_data = decode(torrent_bytes)
    v1_info, v2_info = parser.parse_hybrid(torrent_data[b"info"], torrent_data)

    print(f"\nMulti-File Hybrid Torrent:")
    print(f"  Total Files: {len(v2_info.files)}")
    print(f"  File List:")
    for file_info in v2_info.files:
        print(f"    - {file_info.path_str}: {file_info.length:,} bytes")

    # Show compatibility
    print(f"\n  Compatibility:")
    print(f"    ✓ Works with v1 clients (using SHA-1 hashes)")
    print(f"    ✓ Works with v2 clients (using SHA-256 hashes)")
    print(f"    ✓ WebSeed support: {'Yes' if torrent_data.get(b'url-list') else 'No'}")

    # Clean up
    import shutil

    shutil.rmtree(test_dir)


def demonstrate_backwards_compatibility():
    """Demonstrate backwards compatibility of hybrid torrents."""
    print("\nDemonstrating Backwards Compatibility:")
    print("-" * 60)

    test_file = Path("compat_test.txt")
    test_file.write_bytes(b"Compatibility test " * 500)

    parser = TorrentV2Parser()
    torrent_bytes = parser.generate_hybrid_torrent(
        source=test_file,
        output=Path("compat_test.torrent"),
        trackers=["http://tracker.example.com/announce"],
    )

    torrent_data = decode(torrent_bytes)
    info_dict = torrent_data[b"info"]

    print("\n  Torrent contains both v1 and v2 metadata:")
    print(f"    ✓ V1 'pieces' field: {b'pieces' in info_dict}")
    print(f"    ✓ V2 'file tree' field: {b'file tree' in info_dict}")
    print(f"    ✓ V2 'piece layers' field: {b'piece layers' in info_dict}")
    print(f"    ✓ Meta version: {info_dict[b'meta version']}")

    print("\n  What each client type sees:")
    print("    V1-only client:")
    print("      - Uses SHA-1 info_hash")
    print("      - Uses 'pieces' field for validation")
    print("      - Ignores v2-specific fields")
    print("\n    V2-only client:")
    print("      - Uses SHA-256 info_hash_v2")
    print("      - Uses 'file tree' and 'piece layers'")
    print("      - May ignore v1 'pieces' field")
    print("\n    Hybrid-aware client (like ccBitTorrent):")
    print("      - Can use either protocol")
    print("      - Negotiates best version with peers")
    print("      - Maximizes peer pool by connecting to both v1 and v2 peers")

    test_file.unlink()


def main():
    """Run hybrid torrent examples."""
    print("=" * 60)
    print("Creating Hybrid BitTorrent Torrents (v1 + v2)")
    print("=" * 60)

    print("\n1. Creating hybrid torrent from single file...")
    print("-" * 60)
    create_hybrid_torrent()

    print("\n2. Creating hybrid multi-file torrent...")
    print("-" * 60)
    create_hybrid_multi_file_torrent()

    print("\n3. Demonstrating backwards compatibility...")
    print("-" * 60)
    demonstrate_backwards_compatibility()

    print("\n" + "=" * 60)
    print("Hybrid torrent examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

