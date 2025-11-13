"""Test script to verify aiortc installation and basic functionality.

This script verifies that aiortc can be imported and basic WebRTC
functionality works correctly.
"""

import sys

try:
    from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer
    from aiortc import RTCDataChannel
    print("✓ Successfully imported aiortc modules")
except ImportError as e:
    print(f"✗ Failed to import aiortc: {e}")
    print("\nTo install aiortc, run:")
    print("  uv sync --extra webrtc")
    sys.exit(1)

try:
    # Test creating RTCConfiguration
    config = RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    print("✓ Successfully created RTCConfiguration")
except Exception as e:
    print(f"✗ Failed to create RTCConfiguration: {e}")
    sys.exit(1)

try:
    # Test creating RTCPeerConnection
    pc = RTCPeerConnection(configuration=config)
    print("✓ Successfully created RTCPeerConnection")
except Exception as e:
    print(f"✗ Failed to create RTCPeerConnection: {e}")
    sys.exit(1)

try:
    # Test creating data channel
    data_channel = pc.createDataChannel("test")
    print("✓ Successfully created RTCDataChannel")
except Exception as e:
    print(f"✗ Failed to create RTCDataChannel: {e}")
    sys.exit(1)

print("\n✓ All aiortc tests passed!")
print("aiortc is properly installed and basic functionality works.")

