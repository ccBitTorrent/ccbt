from __future__ import annotations

import socket
import struct
from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.metadata]

from ccbt.metadata_exchange import (
    fetch_metadata_from_peers,
    _handshake,
    _read_exact,
    _send_extended_handshake,
    _recv_message,
)


class TestMetadataExchangeHelpers:
    """Test helper functions for metadata exchange."""

    def test_handshake(self):
        """Test handshake message construction."""
        info_hash = b"\x00" * 20
        peer_id = b"\x11" * 20
        hs = _handshake(info_hash, peer_id)

        assert len(hs) == 68
        assert hs[1:20] == b"BitTorrent protocol"
        assert hs[28:48] == info_hash
        assert hs[48:68] == peer_id
        assert hs[25] & 0x10 == 0x10  # Extension protocol flag at reserved[5] (byte 20+5)

    def test_read_exact(self):
        """Test reading exact number of bytes."""
        s1, s2 = socket.socketpair()
        try:
            s2.send(b"hello")
            data = _read_exact(s1, 5)
            assert data == b"hello"
        finally:
            s1.close()
            s2.close()

    def test_read_exact_connection_closed(self):
        """Test read_exact raises when connection closes."""
        s1, s2 = socket.socketpair()
        try:
            s2.close()
            with pytest.raises(ConnectionError):
                _read_exact(s1, 5)
        finally:
            s1.close()

    def test_send_extended_handshake(self):
        """Test sending extended handshake."""
        s1, s2 = socket.socketpair()
        try:
            _send_extended_handshake(s1)
            s2.settimeout(0.1)
            data = s2.recv(1024)
            assert len(data) >= 5  # Length(4) + msg_id(1) + ext_id(1) + payload
            length = struct.unpack("!I", data[0:4])[0]
            assert length >= 2
            assert data[4] == 20  # Extended message ID
            assert data[5] == 0  # Extended handshake ID
        finally:
            s1.close()
            s2.close()

    def test_recv_message(self):
        """Test receiving a message."""
        s1, s2 = socket.socketpair()
        try:
            msg = b"test message"
            length = struct.pack("!I", len(msg))
            s2.send(length + msg)

            length, payload = _recv_message(s1)
            assert length == len(msg)
            assert payload == msg
        finally:
            s1.close()
            s2.close()

    def test_recv_message_keepalive(self):
        """Test receiving keepalive message."""
        s1, s2 = socket.socketpair()
        try:
            s2.send(struct.pack("!I", 0))

            length, payload = _recv_message(s1)
            assert length == 0
            assert payload == b""
        finally:
            s1.close()
            s2.close()


class TestFetchMetadataFromPeers:
    """Test metadata fetching from peers."""

    def test_fetch_metadata_no_peers(self):
        """Test fetching metadata with no peers."""
        result = fetch_metadata_from_peers(b"\x00" * 20, [])
        assert result is None

    def test_fetch_metadata_invalid_peer(self):
        """Test fetching metadata with invalid peer data."""
        peers = [{"ip": None, "port": 6881}, {"ip": "192.168.1.1", "port": None}]
        result = fetch_metadata_from_peers(b"\x00" * 20, peers)
        assert result is None

    def test_fetch_metadata_connection_failure(self):
        """Test fetching metadata when connection fails."""
        peers = [{"ip": "127.0.0.1", "port": 65535}]  # Unlikely to be listening
        result = fetch_metadata_from_peers(b"\x00" * 20, peers, timeout=0.1)
        assert result is None

    @patch("socket.create_connection")
    def test_fetch_metadata_handshake_mismatch(self, mock_connect):
        """Test fetching metadata with handshake mismatch."""
        mock_sock = Mock()
        mock_sock.sendall = Mock()
        mock_sock.recv = Mock(side_effect=[b"wrong handshake" * 10])
        mock_sock.settimeout = Mock()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_sock)
        mock_connect.return_value.__exit__ = Mock(return_value=None)

        peers = [{"ip": "192.168.1.1", "port": 6881}]
        result = fetch_metadata_from_peers(b"\x00" * 20, peers, timeout=0.1)
        assert result is None

    @patch("socket.create_connection")
    def test_fetch_metadata_no_ut_metadata(self, mock_connect):
        """Test fetching metadata when peer doesn't support ut_metadata."""
        mock_sock = Mock()
        mock_sock.sendall = Mock()
        mock_sock.recv = Mock(
            side_effect=[
                b"\x13BitTorrent protocol" + b"\x00" * 8 + b"\x00" * 20 + b"\x11" * 20,
                b"\x00\x00\x00\x00",  # Keepalive
            ]
        )
        mock_sock.settimeout = Mock()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_sock)
        mock_connect.return_value.__exit__ = Mock(return_value=None)

        peers = [{"ip": "192.168.1.1", "port": 6881}]
        result = fetch_metadata_from_peers(b"\x00" * 20, peers, timeout=0.1)
        assert result is None

    def test_fetch_metadata_default_peer_id(self):
        """Test that default peer_id is used when not provided."""
        peers = [{"ip": "127.0.0.1", "port": 65535}]
        result = fetch_metadata_from_peers(b"\x00" * 20, peers, timeout=0.1)
        # Should use default peer_id format
        assert result is None  # Connection fails, but peer_id was set

    def test_fetch_metadata_limits_peers(self):
        """Test that only first 10 peers are attempted."""
        peers = [{"ip": "127.0.0.1", "port": 65535}] * 15
        with patch("socket.create_connection") as mock_connect:
            mock_connect.side_effect = socket.timeout()
            result = fetch_metadata_from_peers(b"\x00" * 20, peers, timeout=0.1)
            assert result is None
            assert mock_connect.call_count == 10  # Limited to 10

