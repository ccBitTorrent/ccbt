from __future__ import annotations

import asyncio
import socket
import struct
import threading
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.tracker_server_udp import InMemoryPeerStore, UDPTracker


class TestInMemoryPeerStore:
    """Test in-memory peer store."""

    def test_announce_add_peer(self):
        """Test announcing a peer adds it to the store."""
        store = InMemoryPeerStore()
        info_hash = b"\x00" * 20
        peers = store.announce(info_hash, "192.168.1.1", 6881, event=2)  # started
        assert len(peers) == 6  # IPv4 (4) + port (2) = 6 bytes for first peer

        # Add another peer
        peers = store.announce(info_hash, "192.168.1.2", 6882, event=2)
        assert len(peers) == 12  # Two peers: 6 bytes each

    def test_announce_remove_peer(self):
        """Test announcing with stopped event removes peer."""
        store = InMemoryPeerStore()
        info_hash = b"\x00" * 20

        # Add peer
        store.announce(info_hash, "192.168.1.1", 6881, event=2)
        peers = store.announce(info_hash, "192.168.1.1", 6881, event=3)  # stopped
        assert len(peers) == 0

    def test_announce_cleanup_old_peers(self):
        """Test that old peers are cleaned up."""
        store = InMemoryPeerStore()
        info_hash = b"\x00" * 20

        # Add peer
        store.announce(info_hash, "192.168.1.1", 6881, event=2)

        # Manually set old timestamp
        store.torrents[info_hash][("192.168.1.1", 6881)] = time.time() - 7200

        # Announce again should cleanup
        peers = store.announce(info_hash, "192.168.1.2", 6882, event=2)
        assert ("192.168.1.1", 6881) not in store.torrents[info_hash]

    def test_announce_invalid_ip(self):
        """Test that invalid IPs are skipped."""
        store = InMemoryPeerStore()
        info_hash = b"\x00" * 20

        # Try to add invalid peer - should skip
        store.torrents[info_hash] = {("invalid", 6881): time.time()}
        peers = store.announce(info_hash, "192.168.1.1", 6882, event=2)
        # Should not crash, invalid peer skipped


class TestUDPTracker:
    """Test UDP tracker server."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        assert tracker.host == "127.0.0.1"
        assert tracker.sock is not None
        tracker.sock.close()

    def test_handle_connect(self):
        """Test handling connection request."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        addr = ("127.0.0.1", 12345)

        # Send connect request
        transaction_id = 12345
        request = struct.pack("!QII", 0x41727101980, 0, transaction_id)

        # Create a separate socket to receive the response
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(("127.0.0.1", 0))
        test_port = test_sock.getsockname()[1]

        # Send request from test socket
        tracker._handle_connect(request, ("127.0.0.1", test_port), transaction_id)

        # Receive response on test socket
        test_sock.settimeout(0.5)
        data, _ = test_sock.recvfrom(1024)
        assert len(data) == 16
        action, resp_trans_id, conn_id = struct.unpack("!IIQ", data)
        assert action == 0
        assert resp_trans_id == transaction_id
        assert conn_id != 0

        test_sock.close()
        tracker.sock.close()

    def test_handle_announce(self):
        """Test handling announce request."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        addr = ("127.0.0.1", 12345)

        # Build announce request
        transaction_id = 12345
        connection_id = 0x1234567890ABCDEF
        info_hash = b"\x00" * 20
        peer_id = b"\x11" * 20
        downloaded = 0
        left = 1000000
        uploaded = 0
        event = 2  # started
        ip = 0
        key = 0
        num_want = 50
        port = 6881

        request = (
            struct.pack("!QII", connection_id, 1, transaction_id)
            + info_hash
            + peer_id
            + struct.pack("!QQQ", downloaded, left, uploaded)
            + struct.pack("!IIIIH", event, ip, key, num_want, port)
        )

        tracker._handle_announce(request, addr, transaction_id)

        tracker.sock.close()

    def test_handle_announce_short_packet(self):
        """Test handling announce with too short packet."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        addr = ("127.0.0.1", 12345)

        # Send too short announce
        transaction_id = 12345
        request = struct.pack("!QII", 0x41727101980, 1, transaction_id)

        # Use separate socket to receive response
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(("127.0.0.1", 0))
        test_port = test_sock.getsockname()[1]

        tracker._handle_announce(request, ("127.0.0.1", test_port), transaction_id)

        # Should have sent error
        test_sock.settimeout(0.5)
        data, _ = test_sock.recvfrom(1024)
        assert len(data) >= 8
        action, resp_trans_id = struct.unpack("!II", data[:8])
        assert action == 3  # error
        assert resp_trans_id == transaction_id

        test_sock.close()
        tracker.sock.close()

    def test_send_error(self):
        """Test sending error response."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        addr = ("127.0.0.1", 12345)

        # Use separate socket to receive response
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(("127.0.0.1", 0))
        test_port = test_sock.getsockname()[1]

        tracker._send_error(("127.0.0.1", test_port), 12345, b"Test error")

        test_sock.settimeout(0.5)
        data, _ = test_sock.recvfrom(1024)
        assert len(data) >= 8
        action, transaction_id = struct.unpack("!II", data[:8])
        assert action == 3
        assert transaction_id == 12345

        test_sock.close()
        tracker.sock.close()

    @pytest.mark.asyncio
    async def test_serve_forever_connect_request(self):
        """Test serve_forever handles connect requests."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        port = tracker.sock.getsockname()[1]

        # Start server in background thread
        server_thread = threading.Thread(target=tracker.serve_forever, daemon=True)
        server_thread.start()

        # Give server time to start
        await asyncio.sleep(0.1)

        # Send connect request
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        transaction_id = 99999
        request = struct.pack("!QII", 0x41727101980, 0, transaction_id)
        sock.sendto(request, ("127.0.0.1", port))

        # Receive response
        sock.settimeout(1.0)
        data, _ = sock.recvfrom(1024)
        assert len(data) == 16
        action, resp_trans_id, conn_id = struct.unpack("!IIQ", data)
        assert action == 0
        assert resp_trans_id == transaction_id
        assert conn_id != 0

        sock.close()
        tracker.sock.close()

    @pytest.mark.asyncio
    async def test_serve_forever_unsupported_action(self):
        """Test serve_forever handles unsupported actions."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        port = tracker.sock.getsockname()[1]

        server_thread = threading.Thread(target=tracker.serve_forever, daemon=True)
        server_thread.start()

        await asyncio.sleep(0.1)

        # Send unsupported action
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        transaction_id = 88888
        request = struct.pack("!QII", 0x41727101980, 999, transaction_id)  # action 999
        sock.sendto(request, ("127.0.0.1", port))

        sock.settimeout(1.0)
        data, _ = sock.recvfrom(1024)
        assert len(data) >= 8
        action, resp_trans_id = struct.unpack("!II", data[:8])
        assert action == 3  # error
        assert resp_trans_id == transaction_id

        sock.close()
        tracker.sock.close()

    def test_serve_forever_short_packet(self):
        """Test serve_forever ignores short packets."""
        tracker = UDPTracker(host="127.0.0.1", port=0)
        port = tracker.sock.getsockname()[1]

        server_thread = threading.Thread(target=tracker.serve_forever, daemon=True)
        server_thread.start()

        time.sleep(0.1)

        # Send too short packet
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"short", ("127.0.0.1", port))

        # Should not crash, no response expected
        sock.close()
        tracker.sock.close()


if __name__ == "__main__":
    import asyncio

    pytest.main([__file__])

