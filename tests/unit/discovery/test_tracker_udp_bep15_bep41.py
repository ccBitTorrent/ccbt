"""Unit tests for BEP 15 IPv6 and BEP 41 UDP tracker support.

Tests _is_ipv6_address, _parse_peers_compact (IPv4/6-byte and IPv6/18-byte),
handle_response with IPv6 source, and _build_bep41_options.
"""

from __future__ import annotations

import asyncio
import socket
import struct

import pytest

from ccbt.discovery.tracker_udp_client import (
    AsyncUDPTrackerClient,
    TrackerAction,
)

pytestmark = [pytest.mark.unit, pytest.mark.tracker]


class TestBEP15IsIPv6Address:
    """Test _is_ipv6_address for BEP 15 response format detection."""

    def test_ipv4_returns_false(self):
        assert AsyncUDPTrackerClient._is_ipv6_address(("127.0.0.1", 80)) is False
        assert AsyncUDPTrackerClient._is_ipv6_address(("192.168.1.1", 6881)) is False

    def test_ipv6_returns_true(self):
        assert AsyncUDPTrackerClient._is_ipv6_address(("::1", 80)) is True
        assert AsyncUDPTrackerClient._is_ipv6_address(("2001:db8::1", 6881)) is True

    def test_empty_addr_returns_false(self):
        assert AsyncUDPTrackerClient._is_ipv6_address(("", 80)) is False
        assert AsyncUDPTrackerClient._is_ipv6_address((None, 80)) is False  # type: ignore[arg-type]


class TestBEP15ParsePeersCompact:
    """Test _parse_peers_compact for IPv4 (6-byte) and IPv6 (18-byte) stride."""

    def test_ipv4_single_peer(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        # 192.168.1.1 = 0xc0a80101, port 6881 = 0x1ae1
        peer_data = bytes([0xC0, 0xA8, 0x01, 0x01, 0x1A, 0xE1])
        peers, invalid = client._parse_peers_compact(peer_data, is_ipv6=False)
        assert len(peers) == 1
        assert peers[0]["ip"] == "192.168.1.1"
        assert peers[0]["port"] == 6881
        assert invalid == 0

    def test_ipv4_two_peers(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        p1 = bytes([0xC0, 0xA8, 0x01, 0x01, 0x1A, 0xE1])
        p2 = bytes([0x0A, 0x00, 0x00, 0x01, 0x1B, 0x39])  # 10.0.0.1:6969
        peers, invalid = client._parse_peers_compact(p1 + p2, is_ipv6=False)
        assert len(peers) == 2
        assert peers[0]["ip"] == "192.168.1.1" and peers[0]["port"] == 6881
        assert peers[1]["ip"] == "10.0.0.1" and peers[1]["port"] == 6969
        assert invalid == 0

    def test_ipv6_single_peer(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        ip_bytes = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
        port_bytes = (6969).to_bytes(2, "big")
        peer_data = ip_bytes + port_bytes
        peers, invalid = client._parse_peers_compact(peer_data, is_ipv6=True)
        assert len(peers) == 1
        assert peers[0]["ip"] == "2001:db8::1"
        assert peers[0]["port"] == 6969
        assert invalid == 0

    def test_ipv6_two_peers(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        ip1 = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
        ip2 = socket.inet_pton(socket.AF_INET6, "::1")
        port = (6881).to_bytes(2, "big")
        peer_data = ip1 + port + ip2 + port
        peers, invalid = client._parse_peers_compact(peer_data, is_ipv6=True)
        assert len(peers) == 2
        assert peers[0]["ip"] == "2001:db8::1"
        assert peers[1]["ip"] == "::1"
        assert invalid == 0

    def test_ipv4_invalid_port_zero(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        peer_data = bytes([0xC0, 0xA8, 0x01, 0x01, 0x00, 0x00])
        peers, invalid = client._parse_peers_compact(peer_data, is_ipv6=False)
        assert len(peers) == 0
        assert invalid == 1


class TestBEP15HandleResponseIPv6:
    """Test handle_response with IPv6 source address and 18-byte peer payload."""

    def test_announce_response_ipv6_peer_list(self):
        client = AsyncUDPTrackerClient(test_mode=True)
        client._socket_ready = True
        transaction_id = 12345
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            client.pending_requests[transaction_id] = future

            # BEP 15 announce response: action=1, tx_id, interval, leechers, seeders, then 18 bytes per peer
            interval, leechers, seeders = 1800, 1, 2
            ip_bytes = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
            port_bytes = (6881).to_bytes(2, "big")
            peer_bytes = ip_bytes + port_bytes
            data = (
                struct.pack("!I", TrackerAction.ANNOUNCE.value)
                + struct.pack("!I", transaction_id)
                + struct.pack("!I", interval)
                + struct.pack("!I", leechers)
                + struct.pack("!I", seeders)
                + peer_bytes
            )

            client.handle_response(data, ("2001:db8::1", 6969))

            assert future.done()
            resp = future.result()
            assert resp.action == TrackerAction.ANNOUNCE
            assert resp.peers is not None
            assert len(resp.peers) == 1
            assert resp.peers[0]["ip"] == "2001:db8::1"
            assert resp.peers[0]["port"] == 6881
        finally:
            client.pending_requests.pop(transaction_id, None)
            loop.close()


class TestBEP41BuildOptions:
    """Test _build_bep41_options for URLData extension."""

    def test_empty_url_returns_no_extension(self):
        result = AsyncUDPTrackerClient._build_bep41_options("")
        assert result == b""

    def test_url_without_path_or_query_returns_no_extension(self):
        result = AsyncUDPTrackerClient._build_bep41_options("udp://tracker.example.com:80")
        assert result == b""

    def test_conventional_announce_path_returns_no_extension(self):
        result = AsyncUDPTrackerClient._build_bep41_options("udp://tracker:80/announce")
        assert result == b""

    def test_url_with_path_and_query(self):
        result = AsyncUDPTrackerClient._build_bep41_options(
            "udp://tracker.example.com:80/announce?key=val"
        )
        # URLData type=0x2, length, then path+query bytes
        assert result[0] == 0x2
        assert result[1] == len(b"/announce?key=val")
        assert result[2:] == b"/announce?key=val"

    def test_nonstandard_path_only(self):
        result = AsyncUDPTrackerClient._build_bep41_options(
            "udp://tracker:80/custom/announce/path"
        )
        assert result[0] == 0x2
        assert result[2:] == b"/custom/announce/path"
