#!/usr/bin/env python3
"""Example: Starting a BitTorrent session with Protocol v2 support.

This example demonstrates how to configure and use ccBitTorrent with
Protocol v2 features enabled, including handshake negotiation and
v2-specific message handling.
"""

import asyncio
from pathlib import Path

from ccbt.config.config import ConfigManager, get_config
from ccbt.core.bencode import decode
from ccbt.core.torrent_v2 import TorrentV2Parser
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    create_v2_handshake,
    detect_protocol_version,
    negotiate_protocol_version,
    parse_v2_handshake,
)


def configure_protocol_v2():
    """Configure ccBitTorrent for Protocol v2 support."""
    print("Configuring Protocol v2 Support...")
    print("-" * 60)

    # Get configuration
    config = get_config()

    # Enable Protocol v2
    config.network.protocol_v2.enable_protocol_v2 = True
    config.network.protocol_v2.prefer_protocol_v2 = True
    config.network.protocol_v2.support_hybrid = True
    config.network.protocol_v2.v2_handshake_timeout = 30.0

    print("✅ Protocol v2 Configuration:")
    print(f"  Enable v2: {config.network.protocol_v2.enable_protocol_v2}")
    print(f"  Prefer v2: {config.network.protocol_v2.prefer_protocol_v2}")
    print(f"  Support Hybrid: {config.network.protocol_v2.support_hybrid}")
    print(f"  Handshake Timeout: {config.network.protocol_v2.v2_handshake_timeout}s")

    return config


def demonstrate_handshake_creation():
    """Demonstrate v2 handshake creation."""
    print("\n\nDemonstrating V2 Handshake Creation...")
    print("-" * 60)

    # Create a test torrent to get info_hash_v2
    test_file = Path("handshake_test.txt")
    test_file.write_bytes(b"Test content " * 1000)

    parser = TorrentV2Parser()
    torrent_bytes = parser.generate_v2_torrent(
        source=test_file,
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    torrent_data = decode(torrent_bytes)
    v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

    # Create v2 handshake
    peer_id = b"-CC0001-" + b"x" * 12
    handshake = create_v2_handshake(v2_info.info_hash_v2, peer_id)

    print(f"\n✅ Created V2 Handshake:")
    print(f"  Size: {len(handshake)} bytes (v2 standard)")
    print(f"  Info Hash v2: {v2_info.info_hash_v2.hex()}")
    print(f"  Peer ID: {peer_id.decode('latin-1')}")

    # Detect protocol version from handshake
    detected = detect_protocol_version(handshake)
    print(f"  Detected Version: {detected.name}")

    # Parse handshake
    parsed = parse_v2_handshake(handshake)
    print(f"\n  Parsed Handshake Components:")
    print(f"    Protocol: {parsed['protocol'].decode()}")
    print(f"    Reserved Bytes: {parsed['reserved_bytes'].hex()}")
    print(f"    Info Hash v2: {parsed['info_hash_v2'].hex()}")
    print(f"    Peer ID: {parsed['peer_id'].decode('latin-1')}")
    print(f"    Version: {parsed['version'].name}")

    # Clean up
    test_file.unlink()


def demonstrate_protocol_negotiation():
    """Demonstrate protocol version negotiation."""
    print("\n\nDemonstrating Protocol Version Negotiation...")
    print("-" * 60)

    # Create test torrent
    test_file = Path("negotiate_test.txt")
    test_file.write_bytes(b"Test " * 1000)

    parser = TorrentV2Parser()

    # Create hybrid torrent
    torrent_bytes = parser.generate_hybrid_torrent(
        source=test_file,
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    torrent_data = decode(torrent_bytes)
    _, v2_info = parser.parse_hybrid(torrent_data[b"info"], torrent_data)

    # Create different handshake types
    peer_id = b"-CC0001-" + b"x" * 12

    from ccbt.protocols.bittorrent_v2 import create_hybrid_handshake

    hybrid_handshake = create_hybrid_handshake(
        v2_info.info_hash_v1, v2_info.info_hash_v2, peer_id
    )

    print("\n✅ Protocol Negotiation Scenarios:")

    # Scenario 1: We support v2, peer is hybrid
    supported = [ProtocolVersion.V2]
    negotiated = negotiate_protocol_version(hybrid_handshake, supported)
    print(f"\n  Scenario 1: V2-only client, Hybrid peer")
    print(f"    Our support: {[v.name for v in supported]}")
    print(f"    Peer type: HYBRID")
    print(f"    Negotiated: {negotiated.name if negotiated else 'INCOMPATIBLE'}")

    # Scenario 2: We support hybrid, peer is hybrid
    supported = [ProtocolVersion.HYBRID, ProtocolVersion.V2, ProtocolVersion.V1]
    negotiated = negotiate_protocol_version(hybrid_handshake, supported)
    print(f"\n  Scenario 2: Hybrid client, Hybrid peer")
    print(f"    Our support: {[v.name for v in supported]}")
    print(f"    Peer type: HYBRID")
    print(f"    Negotiated: {negotiated.name if negotiated else 'INCOMPATIBLE'}")

    # Scenario 3: We prefer v2
    supported = [ProtocolVersion.V2, ProtocolVersion.HYBRID, ProtocolVersion.V1]
    negotiated = negotiate_protocol_version(hybrid_handshake, supported)
    print(f"\n  Scenario 3: V2-preferred client, Hybrid peer")
    print(f"    Our support (priority order): {[v.name for v in supported]}")
    print(f"    Peer type: HYBRID")
    print(f"    Negotiated: {negotiated.name if negotiated else 'INCOMPATIBLE'}")

    print(f"\n  Negotiation Logic:")
    print(f"    1. Detect peer's protocol version from handshake")
    print(f"    2. Find highest common protocol version")
    print(f"    3. Prefer: HYBRID > V2 > V1")
    print(f"    4. Return negotiated version or None if incompatible")

    # Clean up
    test_file.unlink()


async def demonstrate_async_operations():
    """Demonstrate async v2 protocol operations."""
    print("\n\nDemonstrating Async V2 Protocol Operations...")
    print("-" * 60)

    from ccbt.protocols.bittorrent_v2 import (
        PieceLayerRequest,
        PieceLayerResponse,
        send_v2_handshake,
    )

    # Create mock writer
    class MockWriter:
        def __init__(self):
            self.data = bytearray()

        def write(self, data):
            self.data.extend(data)

        async def drain(self):
            pass

    # Create test torrent
    test_file = Path("async_test.txt")
    test_file.write_bytes(b"Async test " * 1000)

    parser = TorrentV2Parser()
    torrent_bytes = parser.generate_v2_torrent(
        source=test_file,
        trackers=["http://tracker.example.com/announce"],
        piece_length=16384,
    )

    torrent_data = decode(torrent_bytes)
    v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

    print("\n✅ Async Operations:")

    # Send handshake
    writer = MockWriter()
    peer_id = b"-CC0001-" + b"x" * 12
    await send_v2_handshake(writer, v2_info.info_hash_v2, peer_id)
    print(f"\n  1. Sent v2 handshake: {len(writer.data)} bytes")

    # Create piece layer request
    pieces_root = list(v2_info.piece_layers.keys())[0]
    request = PieceLayerRequest(pieces_root)
    request_data = request.serialize()
    print(f"\n  2. Created PieceLayerRequest:")
    print(f"     Pieces Root: {pieces_root.hex()[:32]}...")
    print(f"     Serialized Size: {len(request_data)} bytes")

    # Create piece layer response
    layer = v2_info.piece_layers[pieces_root]
    response = PieceLayerResponse(pieces_root, layer.pieces)
    response_data = response.serialize()
    print(f"\n  3. Created PieceLayerResponse:")
    print(f"     Number of Hashes: {len(layer.pieces)}")
    print(f"     Serialized Size: {len(response_data)} bytes")

    print(f"\n  Async Workflow:")
    print(f"    1. Establish connection with peer")
    print(f"    2. Send/receive v2 handshake")
    print(f"    3. Negotiate protocol version")
    print(f"    4. Exchange piece layer requests/responses")
    print(f"    5. Download and verify pieces using SHA-256")

    # Clean up
    test_file.unlink()


def show_configuration_examples():
    """Show various configuration examples."""
    print("\n\nConfiguration Examples...")
    print("-" * 60)

    print("\n✅ TOML Configuration (ccbt.toml):")
    print("""
[network.protocol_v2]
enable_protocol_v2 = true
prefer_protocol_v2 = true
support_hybrid = true
v2_handshake_timeout = 30.0
""")

    print("\n✅ Environment Variables:")
    print("""
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
""")

    print("\n✅ Command Line:")
    print("""
# Enable v2 protocol
ccbt download file.torrent --protocol-v2

# Prefer v2 over v1
ccbt download file.torrent --protocol-v2-prefer

# Disable v2 protocol
ccbt download file.torrent --no-protocol-v2
""")

    print("\n✅ Python API:")
    print("""
from ccbt.config.config import get_config

config = get_config()
config.network.protocol_v2.enable_protocol_v2 = True
config.network.protocol_v2.prefer_protocol_v2 = True
""")


def main():
    """Run protocol v2 session examples."""
    print("=" * 60)
    print("BitTorrent Protocol v2 Session Examples")
    print("=" * 60)

    # Configure
    configure_protocol_v2()

    # Demonstrate features
    demonstrate_handshake_creation()
    demonstrate_protocol_negotiation()

    # Run async demo
    print("\nRunning async operations...")
    asyncio.run(demonstrate_async_operations())

    # Show configuration
    show_configuration_examples()

    print("\n" + "=" * 60)
    print("Protocol v2 examples completed!")
    print("=" * 60)

    print("\n📚 Next Steps:")
    print("  - Read full documentation: docs/bep52.md")
    print("  - Check API reference: docs/API.md")
    print("  - Try creating your own v2 torrents")
    print("  - Experiment with protocol negotiation")


if __name__ == "__main__":
    main()

