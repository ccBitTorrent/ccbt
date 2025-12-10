#!/usr/bin/env python3
"""Example: Parsing and displaying BitTorrent Protocol v2 torrent information.

This example demonstrates how to parse v2 and hybrid torrents and display
their metadata, file trees, and piece layers.
"""

from pathlib import Path

from ccbt.core.bencode import decode
from ccbt.core.torrent_v2 import TorrentV2Parser


def parse_and_display_v2_torrent():
    """Parse and display v2 torrent information."""
    # First create a test v2 torrent
    test_file = Path("parse_test.txt")
    test_file.write_bytes(b"Test content for parsing " * 1000)

    parser = TorrentV2Parser()
    torrent_bytes = parser.generate_v2_torrent(
        source=test_file,
        output=Path("parse_test.torrent"),
        trackers=["http://tracker.example.com/announce"],
        comment="Test torrent for parsing example",
        piece_length=16384,
    )

    # Now parse it
    print("Parsing v2 torrent...")
    torrent_data = decode(torrent_bytes)
    v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

    # Display comprehensive information
    print("\n" + "=" * 60)
    print("V2 TORRENT INFORMATION")
    print("=" * 60)

    print(f"\nBasic Information:")
    print(f"  Name: {v2_info.name}")
    print(f"  Comment: {v2_info.comment}")
    print(f"  Created By: {v2_info.created_by}")
    print(f"  Creation Date: {v2_info.creation_date}")
    print(f"  Private: {v2_info.is_private}")

    print(f"\nHashes:")
    print(f"  Info Hash v2 (SHA-256): {v2_info.info_hash_v2.hex()}")
    print(f"  Info Hash v1 (SHA-1): {v2_info.info_hash_v1.hex() if v2_info.info_hash_v1 else 'N/A (v2-only)'}")

    print(f"\nSize Information:")
    print(f"  Total Length: {v2_info.total_length:,} bytes ({v2_info.total_length / 1024:.2f} KiB)")
    print(f"  Piece Length: {v2_info.piece_length:,} bytes ({v2_info.piece_length / 1024:.2f} KiB)")
    print(f"  Number of Pieces: {v2_info.num_pieces}")

    print(f"\nTracker Information:")
    print(f"  Primary Tracker: {v2_info.announce}")
    if v2_info.announce_list:
        print(f"  Tracker Tiers: {len(v2_info.announce_list)}")
        for i, tier in enumerate(v2_info.announce_list, 1):
            print(f"    Tier {i}: {len(tier)} tracker(s)")

    print(f"\nFiles:")
    print(f"  Total Files: {len(v2_info.files)}")
    for file_info in v2_info.files:
        print(f"    - {file_info.path_str}")
        print(f"      Size: {file_info.length:,} bytes")
        if hasattr(file_info, "pieces_root") and file_info.pieces_root:
            print(f"      Pieces Root: {file_info.pieces_root.hex()[:16]}...")

    print(f"\nFile Tree Structure:")
    for name, node in v2_info.file_tree.items():
        print(f"  {name}:")
        if node.is_file():
            print(f"    Type: File")
            print(f"    Length: {node.length:,} bytes")
            print(f"    Pieces Root: {node.pieces_root.hex()[:16]}...")
        else:
            print(f"    Type: Directory")
            print(f"    Children: {len(node.children)}")

    print(f"\nPiece Layers:")
    print(f"  Total Piece Layers: {len(v2_info.piece_layers)}")
    for pieces_root, layer in v2_info.piece_layers.items():
        print(f"    Pieces Root: {pieces_root.hex()[:16]}...")
        print(f"      Piece Length: {layer.piece_length:,} bytes")
        print(f"      Number of Pieces: {layer.num_pieces()}")
        print(f"      First Piece Hash: {layer.pieces[0].hex()[:16]}..." if layer.pieces else "      No pieces")

    # Clean up
    test_file.unlink()


def parse_hybrid_torrent():
    """Parse and display hybrid torrent information."""
    # Create test hybrid torrent
    test_file = Path("hybrid_parse_test.txt")
    test_file.write_bytes(b"Hybrid test content " * 1000)

    parser = TorrentV2Parser()
    torrent_bytes = parser.generate_hybrid_torrent(
        source=test_file,
        output=Path("hybrid_parse_test.torrent"),
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    # Parse hybrid torrent
    print("\n\nParsing hybrid torrent...")
    torrent_data = decode(torrent_bytes)
    v1_info, v2_info = parser.parse_hybrid(torrent_data[b"info"], torrent_data)

    print("\n" + "=" * 60)
    print("HYBRID TORRENT INFORMATION")
    print("=" * 60)

    print(f"\nHybrid Metadata:")
    print(f"  Meta Version: 3 (Hybrid)")
    print(f"  Name: {v2_info.name}")

    print(f"\nV1 Protocol Information:")
    print(f"  Info Hash (SHA-1): {v2_info.info_hash_v1.hex()}")
    print(f"  V1 Pieces: {len(torrent_data[b'info'][b'pieces']) // 20}")
    print(f"  V1 Piece Hash Size: 20 bytes (SHA-1)")

    print(f"\nV2 Protocol Information:")
    print(f"  Info Hash v2 (SHA-256): {v2_info.info_hash_v2.hex()}")
    print(f"  V2 File Tree Entries: {len(v2_info.file_tree)}")
    print(f"  V2 Piece Layers: {len(v2_info.piece_layers)}")
    print(f"  V2 Piece Hash Size: 32 bytes (SHA-256)")

    print(f"\nCompatibility:")
    print(f"  ✓ Can connect to v1-only peers")
    print(f"  ✓ Can connect to v2-only peers")
    print(f"  ✓ Can connect to hybrid-aware peers")
    print(f"  ✓ Maximizes swarm size")

    # Clean up
    test_file.unlink()


def compare_v1_vs_v2_metadata():
    """Compare metadata sizes between v1 and v2."""
    print("\n\nComparing v1, v2, and hybrid metadata sizes...")
    print("\n" + "=" * 60)
    print("METADATA SIZE COMPARISON")
    print("=" * 60)

    # Create test file
    test_file = Path("comparison_test.txt")
    test_file.write_bytes(b"x" * 100000)  # 100 KB

    parser = TorrentV2Parser()

    # Generate v2 torrent
    v2_bytes = parser.generate_v2_torrent(
        source=test_file,
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    # Generate hybrid torrent
    hybrid_bytes = parser.generate_hybrid_torrent(
        source=test_file,
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    print(f"\nTorrent File Sizes:")
    print(f"  V2-only: {len(v2_bytes):,} bytes")
    print(f"  Hybrid (v1+v2): {len(hybrid_bytes):,} bytes")
    print(f"  Size Increase: {len(hybrid_bytes) - len(v2_bytes):,} bytes ({((len(hybrid_bytes) / len(v2_bytes)) - 1) * 100:.1f}%)")

    # Parse to show piece hash differences
    v2_data = decode(v2_bytes)
    hybrid_data = decode(hybrid_bytes)

    v2_pieces = len(v2_data[b"info"][b"piece layers"])
    v1_pieces_size = len(hybrid_data[b"info"][b"pieces"])

    print(f"\nPiece Hash Storage:")
    print(f"  V2 piece layers: {v2_pieces} layer(s)")
    print(f"  V1 pieces field: {v1_pieces_size:,} bytes ({v1_pieces_size // 20} pieces × 20 bytes)")

    print(f"\nHash Algorithm Comparison:")
    print(f"  V1 (SHA-1): 20 bytes per piece, 160-bit security")
    print(f"  V2 (SHA-256): 32 bytes per piece, 256-bit security")
    print(f"  V2 overhead: +60% hash size, but better security")

    # Clean up
    test_file.unlink()


def main():
    """Run parsing examples."""
    print("=" * 60)
    print("Parsing BitTorrent Protocol v2 Torrents")
    print("=" * 60)

    print("\n1. Parsing v2-only torrent...")
    print("-" * 60)
    parse_and_display_v2_torrent()

    print("\n2. Parsing hybrid torrent...")
    print("-" * 60)
    parse_hybrid_torrent()

    print("\n3. Comparing metadata sizes...")
    print("-" * 60)
    compare_v1_vs_v2_metadata()

    print("\n" + "=" * 60)
    print("Parsing examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

