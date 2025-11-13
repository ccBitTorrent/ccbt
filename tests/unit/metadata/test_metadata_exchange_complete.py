"""Complete successful path tests for metadata exchange.

Uses proper socket pair mocking to exercise the full successful metadata fetch flow.
"""

from __future__ import annotations

import hashlib
import math
import socket
import struct
from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.metadata]

from ccbt.core.bencode import BencodeDecoder, BencodeEncoder
from ccbt.piece.metadata_exchange import (
    METADATA_PIECE_SIZE,
    _read_exact,
    _recv_message,
    fetch_metadata_from_peers,
)


class SocketBuffer:
    """Helper to simulate socket recv with proper buffering."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def recv(self, n: int) -> bytes:
        """Simulate socket.recv with proper behavior."""
        if self.pos >= len(self.data):
            return b""
        result = self.data[self.pos : self.pos + n]
        self.pos += len(result)
        return result


@pytest.fixture
def socket_pair():
    """Create socket pair for testing."""
    s1, s2 = socket.socketpair()
    yield s1, s2
    s1.close()
    s2.close()


class TestMetadataExchangeCompleteFlow:
    """Test complete successful metadata exchange flow."""

    @patch("socket.create_connection")
    def test_fetch_metadata_complete_success_single_piece(self, mock_create_connection):
        """Test complete successful fetch with single piece (covers lines 100-163)."""
        # Create real metadata
        metadata_dict = {b"name": b"test_torrent", b"length": 1000}
        metadata_bytes = BencodeEncoder().encode(metadata_dict)
        info_hash = hashlib.sha1(metadata_bytes).digest()
        
        # Create socket pair
        s1, s2 = socket.socketpair()
        
        # Prepare peer response
        pstr_len = struct.pack("B", 19)
        pstr = b"BitTorrent protocol"
        reserved = bytearray(b"\x00" * 8)
        reserved[5] |= 0x10  # Extension protocol flag
        handshake_resp = pstr_len + pstr + bytes(reserved) + info_hash + b"\x22" * 20
        
        # Extended handshake
        ext_handshake_payload = BencodeEncoder().encode({
            b"m": {b"ut_metadata": 1},
            b"metadata_size": len(metadata_bytes),
        })
        ext_handshake_msg = struct.pack("!IBB", 2 + len(ext_handshake_payload), 20, 0) + ext_handshake_payload
        
        # Piece response (single piece)
        piece_header = BencodeEncoder().encode({
            b"msg_type": 1,
            b"piece": 0,
        })
        piece_msg = struct.pack("!IBB", 2 + len(piece_header) + len(metadata_bytes), 20, 1) + piece_header + metadata_bytes
        
        # Combine all responses
        full_response = handshake_resp + ext_handshake_msg + piece_msg
        
        # Send data on s2 side in background
        def send_data():
            """Send data on s2 side."""
            try:
                import time
                s2.sendall(handshake_resp)
                time.sleep(0.01)
                s2.sendall(ext_handshake_msg)
                time.sleep(0.01)
                s2.sendall(piece_msg)
            except Exception:
                pass
        
        import threading
        send_thread = threading.Thread(target=send_data, daemon=True)
        send_thread.start()
        
        # Mock create_connection to return our socket
        mock_create_connection.return_value.__enter__ = Mock(return_value=s1)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        
        # Wait a bit for send
        import time
        time.sleep(0.1)
        
        # Test fetch
        peers = [{"ip": "127.0.0.1", "port": 6881}]
        result = fetch_metadata_from_peers(info_hash, peers, timeout=0.5)
        
        # Should succeed
        assert result is not None
        assert result == metadata_dict
        
        s1.close()
        s2.close()

    @patch("socket.create_connection")
    def test_fetch_metadata_complete_success_multiple_pieces(self, mock_create_connection):
        """Test complete successful fetch with multiple pieces."""
        # Create larger metadata
        large_data = b"x" * (METADATA_PIECE_SIZE + 1000)  # More than one piece
        metadata_dict = {b"name": b"large_torrent", b"data": large_data}
        metadata_bytes = BencodeEncoder().encode(metadata_dict)
        info_hash = hashlib.sha1(metadata_bytes).digest()
        num_pieces = math.ceil(len(metadata_bytes) / METADATA_PIECE_SIZE)
        
        s1, s2 = socket.socketpair()
        
        # Prepare responses
        pstr_len = struct.pack("B", 19)
        pstr = b"BitTorrent protocol"
        reserved = bytearray(b"\x00" * 8)
        reserved[5] |= 0x10
        handshake_resp = pstr_len + pstr + bytes(reserved) + info_hash + b"\x22" * 20
        
        ext_handshake_payload = BencodeEncoder().encode({
            b"m": {b"ut_metadata": 1},
            b"metadata_size": len(metadata_bytes),
        })
        ext_handshake_msg = struct.pack("!IBB", 2 + len(ext_handshake_payload), 20, 0) + ext_handshake_payload
        
        # Build piece messages
        piece_messages = []
        for idx in range(num_pieces):
            start = idx * METADATA_PIECE_SIZE
            end = min(start + METADATA_PIECE_SIZE, len(metadata_bytes))
            piece_data = metadata_bytes[start:end]
            
            piece_header = BencodeEncoder().encode({
                b"msg_type": 1,
                b"piece": idx,
            })
            piece_msg = struct.pack("!IBB", 2 + len(piece_header) + len(piece_data), 20, 1) + piece_header + piece_data
            piece_messages.append(piece_msg)
        
        full_response = handshake_resp + ext_handshake_msg + b"".join(piece_messages)
        
        def send_data():
            try:
                s2.sendall(handshake_resp)
                import time
                time.sleep(0.01)
                s2.sendall(ext_handshake_msg)
                time.sleep(0.01)
                for piece_msg in piece_messages:
                    s2.sendall(piece_msg)
                    time.sleep(0.01)
            except Exception:
                pass
        
        import threading
        send_thread = threading.Thread(target=send_data, daemon=True)
        send_thread.start()
        
        mock_create_connection.return_value.__enter__ = Mock(return_value=s1)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        
        import time
        time.sleep(0.1)
        
        peers = [{"ip": "127.0.0.1", "port": 6881}]
        result = fetch_metadata_from_peers(info_hash, peers, timeout=1.0)
        
        # Should succeed
        assert result is not None
        assert b"name" in result
        
        s1.close()
        s2.close()

    @patch("socket.create_connection")
    def test_fetch_metadata_extended_handshake_loop_iterations(self, mock_create_connection):
        """Test extended handshake loop with multiple iterations (line 96)."""
        info_hash = b"\x00" * 20
        
        s1, s2 = socket.socketpair()
        
        # Send handshake
        pstr_len = struct.pack("B", 19)
        pstr = b"BitTorrent protocol"
        reserved = bytearray(b"\x00" * 8)
        reserved[5] |= 0x10
        handshake_resp = pstr_len + pstr + bytes(reserved) + info_hash + b"\x22" * 20
        
        def send_responses():
            try:
                s2.sendall(handshake_resp)
                import time
                time.sleep(0.01)
                # Send keepalive first (length 0)
                s2.sendall(struct.pack("!I", 0))
                time.sleep(0.01)
                # Send non-extended message (ID 1)
                s2.sendall(struct.pack("!IB", 1, 1))
                time.sleep(0.01)
                # Then send extended handshake
                ext_handshake_payload = BencodeEncoder().encode({
                    b"m": {b"ut_metadata": 1},
                    b"metadata_size": 100,
                })
                ext_handshake_msg = struct.pack("!IBB", 2 + len(ext_handshake_payload), 20, 0) + ext_handshake_payload
                s2.sendall(ext_handshake_msg)
            except Exception:
                pass
        
        import threading
        send_thread = threading.Thread(target=send_responses, daemon=True)
        send_thread.start()
        
        mock_create_connection.return_value.__enter__ = Mock(return_value=s1)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        
        import time
        time.sleep(0.1)
        
        peers = [{"ip": "127.0.0.1", "port": 6881}]
        result = fetch_metadata_from_peers(info_hash, peers, timeout=0.5)
        # Should continue through keepalive and non-extended messages
        assert result is None  # But no pieces, so fails
        
        s1.close()
        s2.close()

    @patch("socket.create_connection")
    def test_fetch_metadata_missing_ut_metadata_id_continues(self, mock_create_connection):
        """Test when ut_metadata_id is missing, should continue to next peer (line 114-115)."""
        info_hash = b"\x00" * 20
        
        s1, s2 = socket.socketpair()
        
        # Send handshake
        pstr_len = struct.pack("B", 19)
        pstr = b"BitTorrent protocol"
        reserved = bytearray(b"\x00" * 8)
        reserved[5] |= 0x10
        handshake_resp = pstr_len + pstr + bytes(reserved) + info_hash + b"\x22" * 20
        
        # Extended handshake WITHOUT ut_metadata
        ext_handshake_payload = BencodeEncoder().encode({
            b"m": {},  # Empty m dict, no ut_metadata
            b"metadata_size": 1000,  # Has metadata_size but no ut_metadata_id
        })
        ext_handshake_msg = struct.pack("!IBB", 2 + len(ext_handshake_payload), 20, 0) + ext_handshake_payload
        
        def send_responses():
            try:
                import time
                s2.sendall(handshake_resp)
                time.sleep(0.01)
                s2.sendall(ext_handshake_msg)
            except Exception:
                pass
        
        import threading
        send_thread = threading.Thread(target=send_responses, daemon=True)
        send_thread.start()
        
        mock_create_connection.return_value.__enter__ = Mock(return_value=s1)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        
        import time
        time.sleep(0.1)
        
        peers = [{"ip": "127.0.0.1", "port": 6881}]
        result = fetch_metadata_from_peers(info_hash, peers, timeout=0.5)
        # Should continue (line 115) because ut_metadata_id is None
        assert result is None
        
        s1.close()
        s2.close()

    @patch("socket.create_connection")
    def test_fetch_metadata_incomplete_pieces_continues(self, mock_create_connection):
        """Test when pieces are incomplete, should continue (line 153-154)."""
        info_hash = b"\x00" * 20
        metadata_dict = {b"name": b"test"}
        metadata_bytes = BencodeEncoder().encode(metadata_dict)
        
        s1, s2 = socket.socketpair()
        
        # Send handshake and extended handshake
        pstr_len = struct.pack("B", 19)
        pstr = b"BitTorrent protocol"
        reserved = bytearray(b"\x00" * 8)
        reserved[5] |= 0x10
        handshake_resp = pstr_len + pstr + bytes(reserved) + info_hash + b"\x22" * 20
        
        ext_handshake_payload = BencodeEncoder().encode({
            b"m": {b"ut_metadata": 1},
            b"metadata_size": len(metadata_bytes),
        })
        ext_handshake_msg = struct.pack("!IBB", 2 + len(ext_handshake_payload), 20, 0) + ext_handshake_payload
        
        request_received = [False]
        
        def send_responses():
            try:
                import time
                s2.sendall(handshake_resp)
                time.sleep(0.05)
                s2.sendall(ext_handshake_msg)
                time.sleep(0.1)  # Wait for piece request
                # Check if request was received by reading from socket
                try:
                    # Read piece request (will timeout, but that's ok)
                    s2.settimeout(0.1)
                    s2.recv(1024)  # This will trigger request_received if sent
                    request_received[0] = True
                except Exception:
                    pass
                # Don't send any piece responses - pieces will remain None
            except Exception:
                pass
        
        import threading
        send_thread = threading.Thread(target=send_responses, daemon=True)
        send_thread.start()
        
        mock_create_connection.return_value.__enter__ = Mock(return_value=s1)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        
        import time
        time.sleep(0.15)
        
        peers = [{"ip": "127.0.0.1", "port": 6881}]
        result = fetch_metadata_from_peers(info_hash, peers, timeout=1.0)
        # Should continue (line 154) because pieces are None (no piece responses sent)
        assert result is None
        
        s1.close()
        s2.close()

