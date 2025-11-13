"""Comprehensive tests for ccbt.discovery.tracker_server_http to achieve 95%+ coverage.

Covers missing lines:
- InMemoryTrackerStore.announce with stopped event (lines 33-34)
- Stale peer cleanup (lines 39-42)
- OSError handling in compact peer building (lines 50-51)
- AnnounceHandler.do_GET with non-announce path (line 69)
- Missing params error handling (lines 79-81)
- Exception handling in do_GET (lines 97-103)
- run_http_tracker function (lines 106-112)
"""

from __future__ import annotations

import socket
import time
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from ccbt.discovery.tracker_server_http import (
    AnnounceHandler,
    InMemoryTrackerStore,
    run_http_tracker,
)

pytestmark = [pytest.mark.unit, pytest.mark.tracker]


class TestInMemoryTrackerStore:
    """Test InMemoryTrackerStore operations."""

    def test_announce_stopped_event(self):
        """Test announce with stopped event (lines 33-34)."""
        store = InMemoryTrackerStore()
        info_hash = b"\x00" * 20

        # Announce peer
        store.announce(info_hash, "127.0.0.1", 6881, "started")
        assert (("127.0.0.1", 6881) in store.torrents[info_hash])

        # Stop peer
        store.announce(info_hash, "127.0.0.1", 6881, "stopped")
        assert (("127.0.0.1", 6881) not in store.torrents[info_hash])

    def test_announce_stale_peer_cleanup(self):
        """Test announce stale peer cleanup (lines 39-42)."""
        store = InMemoryTrackerStore()
        info_hash = b"\x00" * 20

        # Add peer with old timestamp
        peers = store.torrents.setdefault(info_hash, {})
        old_time = time.time() - 7200  # 2 hours ago (stale)
        peers[("127.0.0.1", 6881)] = old_time

        # Announce new peer (should trigger cleanup)
        store.announce(info_hash, "192.168.1.1", 6882, "started")

        # Old peer should be removed
        assert (("127.0.0.1", 6881) not in store.torrents[info_hash])
        # New peer should be present
        assert (("192.168.1.1", 6882) in store.torrents[info_hash])

    def test_announce_oserror_handling(self):
        """Test announce OSError handling in compact peer building (lines 50-51)."""
        store = InMemoryTrackerStore()
        info_hash = b"\x00" * 20

        # Add peer with invalid IP that will cause OSError
        peers = store.torrents.setdefault(info_hash, {})
        peers[("invalid.ip.address", 6881)] = time.time()

        # Mock socket.inet_aton to raise OSError
        with patch("socket.inet_aton", side_effect=OSError("Invalid IP")):
            result = store.announce(info_hash, "127.0.0.1", 6882, "started")

            # Should still return valid response (invalid peer skipped)
            assert result is not None
            # Response should be bencoded
            assert b"interval" in result

    def test_announce_response_format(self):
        """Test announce response format."""
        store = InMemoryTrackerStore()
        info_hash = b"\x00" * 20

        # Announce multiple peers
        store.announce(info_hash, "127.0.0.1", 6881, "started")
        store.announce(info_hash, "192.168.1.1", 6882, "started")

        result = store.announce(info_hash, "10.0.0.1", 6883, "started")

        # Decode to verify
        from ccbt.core.bencode import decode

        decoded = decode(result)
        assert b"interval" in decoded
        assert b"peers" in decoded
        assert isinstance(decoded[b"peers"], bytes)
        # Should have 3 peers * 6 bytes = 18 bytes
        assert len(decoded[b"peers"]) >= 6  # At least one peer


class TestAnnounceHandler:
    """Test AnnounceHandler operations."""

    def _create_handler(self):
        """Create a properly mocked AnnounceHandler."""
        # Mock request object
        mock_request = Mock()
        mock_request.makefile.return_value = BytesIO(b"GET / HTTP/1.1\r\n\r\n")

        # Create handler with proper mocks
        handler = AnnounceHandler(mock_request, ("127.0.0.1", 8080), None)

        # Set up response mocks
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.send_error = Mock()
        handler.wfile = BytesIO()

        return handler

    def test_do_get_non_announce_path(self):
        """Test do_GET with non-announce path (line 69)."""
        handler = self._create_handler()

        # Test with non-announce path
        handler.path = "/not_announce?info_hash=test"
        handler.do_GET()

        # Should send 404 error
        handler.send_error.assert_called_once_with(404)

    def test_do_get_missing_params_error(self):
        """Test do_GET with missing params error (lines 79-81)."""
        handler = self._create_handler()

        # Test with missing info_hash
        handler.path = "/announce?peer_id=test"
        handler.do_GET()

        # Should write failure response
        handler.wfile.seek(0)
        response = handler.wfile.read()
        assert b"failure reason" in response
        assert b"missing info_hash" in response.lower() or b"missing" in response.lower()

        # Test with missing peer_id
        handler.wfile = BytesIO()
        handler.path = "/announce?info_hash=test"
        handler.do_GET()

        handler.wfile.seek(0)
        response = handler.wfile.read()
        assert b"failure reason" in response

    def test_do_get_successful_announce(self):
        """Test do_GET successful announce path."""
        handler = self._create_handler()

        # Test with valid params
        from urllib.parse import quote

        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881&event=started"

        handler.do_GET()

        # Should send 200 response
        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_called_with("Content-Type", "text/plain")

        # Response body should be bencoded
        handler.wfile.seek(0)
        response = handler.wfile.read()
        assert response.startswith(b"d")  # Bencoded dict

    def test_do_get_exception_handling(self):
        """Test do_GET exception handling (lines 97-103)."""
        handler = self._create_handler()

        # Test with invalid port (will cause ValueError in int())
        from urllib.parse import quote

        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=invalid"

        handler.do_GET()

        # Should send 200 with failure response
        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_called_with("Content-Type", "text/plain")
        handler.end_headers.assert_called_once()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        assert b"failure reason" in response

    def test_do_get_with_valid_event_types(self):
        """Test do_GET with different event types."""
        handler = self._create_handler()

        from urllib.parse import quote

        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20

        # Test started event
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881&event=started"
        handler.do_GET()
        handler.send_response.assert_called_with(200)

        # Test completed event
        handler.wfile = BytesIO()
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881&event=completed"
        handler.do_GET()

        # Test stopped event
        handler.wfile = BytesIO()
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881&event=stopped"
        handler.do_GET()

        # Verify store has correct state (stopped removes peer)
        assert (("127.0.0.1", 6881) not in handler.store.torrents[info_hash])

    def test_do_get_client_address_handling(self):
        """Test do_GET client_address attribute handling (line 89)."""
        handler = self._create_handler()
        
        from urllib.parse import quote
        
        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881"
        handler.client_address = ("192.168.1.100", 54321)
        
        handler.do_GET()
        
        # Should use client_address[0] for IP
        handler.send_response.assert_called_once_with(200)
        # Peer should be announced with client IP
        assert (("192.168.1.100", 6881) in handler.store.torrents[info_hash])

    def test_do_get_port_validation_edge_cases(self):
        """Test do_GET port validation edge cases."""
        handler = self._create_handler()
        
        from urllib.parse import quote
        
        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20
        
        # Test with zero port
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=0"
        handler.wfile = BytesIO()
        handler.do_GET()
        handler.send_response.assert_called_with(200)
        
        # Test with maximum port
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=65535"
        handler.wfile = BytesIO()
        handler.do_GET()
        handler.send_response.assert_called_with(200)

    def test_do_get_default_event_parameter(self):
        """Test do_GET with default event parameter (line 77)."""
        handler = self._create_handler()
        
        from urllib.parse import quote
        
        info_hash = b"\x00" * 20
        peer_id = b"\x01" * 20
        # No event parameter - should default to empty string
        handler.path = f"/announce?info_hash={quote(info_hash)}&peer_id={quote(peer_id)}&port=6881"
        
        handler.do_GET()
        
        # Should succeed with default event
        handler.send_response.assert_called_once_with(200)
        # Peer should be added (not stopped)
        assert (("127.0.0.1", 6881) in handler.store.torrents[info_hash])


class TestRunHTTPTracker:
    """Test run_http_tracker function."""

    def test_run_http_tracker(self):
        """Test run_http_tracker function (lines 106-112)."""
        # Mock HTTPServer to avoid actually starting a server
        with patch("ccbt.discovery.tracker_server_http.HTTPServer") as mock_server_class:
            mock_server = Mock()
            mock_server.serve_forever = Mock()
            mock_server.server_close = Mock()
            mock_server_class.return_value = mock_server

            # Test normal execution
            run_http_tracker("127.0.0.1", 6969)

            # Verify server was created
            mock_server_class.assert_called_once()
            # Verify serve_forever was called
            mock_server.serve_forever.assert_called_once()
            # Verify server_close was called (in finally)
            mock_server.server_close.assert_called_once()

    def test_run_http_tracker_exception_handling(self):
        """Test run_http_tracker with exception.
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test intentionally raises KeyboardInterrupt to verify server cleanup on interrupt.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        with patch("ccbt.discovery.tracker_server_http.HTTPServer") as mock_server_class:
            mock_server = Mock()
            mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt())
            mock_server.server_close = Mock()
            mock_server_class.return_value = mock_server

            # Should still close server on exception
            run_http_tracker("127.0.0.1", 6969)

            # Verify server_close was called (in finally)
            mock_server.server_close.assert_called_once()
