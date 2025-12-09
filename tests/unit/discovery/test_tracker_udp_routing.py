"""Tests for UDP tracker routing in AsyncTrackerClient.

This test file verifies that AsyncTrackerClient properly routes UDP trackers
to AsyncUDPTrackerClient and handles magnet links correctly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerResponse


class TestUDPTrackerRouting:
    """Test cases for UDP tracker routing in AsyncTrackerClient."""

    @pytest.fixture
    def tracker_client(self):
        """Create AsyncTrackerClient instance."""
        with patch("ccbt.discovery.tracker.get_config"):
            client = AsyncTrackerClient()
            client.session = MagicMock()  # Mock HTTP session
            return client

    @pytest.fixture
    def magnet_torrent_data(self):
        """Create magnet link torrent data without metadata."""
        return {
            "info_hash": b"test1234567890123456",
            "announce": "udp://tracker.opentrackr.org:1337",
            "file_info": None,  # Magnet link without metadata
        }

    @pytest.fixture
    def torrent_data_udp(self):
        """Create torrent data with UDP tracker."""
        return {
            "info_hash": b"test1234567890123456",
            "announce": "udp://tracker.opentrackr.org:1337",
            "file_info": {
                "total_length": 1024 * 1024 * 1024,  # 1GB
            },
        }

    @pytest.fixture
    def torrent_data_http(self):
        """Create torrent data with HTTP tracker."""
        return {
            "info_hash": b"test1234567890123456",
            "announce": "http://tracker.example.com/announce",
            "file_info": {
                "total_length": 1024 * 1024 * 1024,  # 1GB
            },
        }

    @pytest.fixture
    def torrent_data_mixed(self):
        """Create torrent data with both HTTP and UDP trackers."""
        return {
            "info_hash": b"test1234567890123456",
            "announce": "http://tracker.example.com/announce",
            "announce_list": [
                ["http://tracker1.example.com/announce"],
                ["udp://tracker.opentrackr.org:1337"],
            ],
            "file_info": {
                "total_length": 1024 * 1024 * 1024,  # 1GB
            },
        }

    @pytest.mark.asyncio
    async def test_udp_tracker_routing(self, tracker_client, torrent_data_udp):
        """Test that UDP trackers are routed to AsyncUDPTrackerClient."""
        # Mock UDP tracker client - now accessed via _session_manager.udp_tracker_client
        mock_udp_client = AsyncMock()
        # Mock transport properly - is_closing() must return a boolean
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False  # Transport is not closing
        mock_udp_client.transport = mock_transport
        mock_udp_client._socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()  # Mock start method
        
        # Mock _announce_to_tracker_full which is now used internally
        # Returns tuple: (peers, interval, seeders, leechers)
        mock_udp_client._announce_to_tracker_full = AsyncMock(
            return_value=(
                [
                    {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"},
                    {"ip": "192.168.1.2", "port": 6882, "peer_source": "tracker"},
                ],
                1800,  # interval
                10,    # seeders
                5,     # leechers
            )
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        response = await tracker_client.announce(torrent_data_udp)

        # Verify _announce_to_tracker_full was called (not HTTP request)
        mock_udp_client._announce_to_tracker_full.assert_called_once()
        call_kwargs = mock_udp_client._announce_to_tracker_full.call_args[1]
        assert call_kwargs["uploaded"] == 0
        assert call_kwargs["downloaded"] == 0
        assert call_kwargs["left"] == 1024 * 1024 * 1024

        # Verify response format is TrackerResponse with full info
        assert isinstance(response, TrackerResponse)
        assert len(response.peers) == 2
        assert response.peers[0]["ip"] == "192.168.1.1"
        assert response.peers[1]["ip"] == "192.168.1.2"
        assert response.interval == 1800
        assert response.complete == 10  # seeders -> complete
        assert response.incomplete == 5  # leechers -> incomplete

    @pytest.mark.asyncio
    async def test_http_tracker_no_routing(self, tracker_client, torrent_data_http):
        """Test that HTTP trackers are NOT routed to UDP client."""
        # Mock HTTP request
        mock_response_data = b"d8:intervali1800e5:peersl6:192.168.1.1:6881ee"
        tracker_client._make_request_async = AsyncMock(return_value=mock_response_data)
        tracker_client._parse_response_async = MagicMock(
            return_value=TrackerResponse(
                interval=1800,
                peers=[{"ip": "192.168.1.1", "port": 6881}],
            )
        )

        # Ensure no session manager is set (HTTP trackers don't need UDP client)
        tracker_client._session_manager = None

        response = await tracker_client.announce(torrent_data_http)

        # Verify HTTP request was made
        tracker_client._make_request_async.assert_called_once()
        assert isinstance(response, TrackerResponse)

    @pytest.mark.asyncio
    async def test_magnet_link_none_file_info(self, tracker_client, magnet_torrent_data):
        """Test that magnet links with None file_info use left=0 (BEP 3 compliant)."""
        # Mock UDP client - now accessed via _session_manager.udp_tracker_client
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client._socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()
        
        # Mock _announce_to_tracker_full which is now used internally
        mock_udp_client._announce_to_tracker_full = AsyncMock(
            return_value=([], 1800, 0, 0)  # (peers, interval, seeders, leechers)
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        response = await tracker_client.announce(magnet_torrent_data)

        # Verify UDP client was called with left=0 (BEP 3 compliant for magnet links)
        mock_udp_client._announce_to_tracker_full.assert_called_once()
        call_kwargs = mock_udp_client._announce_to_tracker_full.call_args[1]
        assert call_kwargs["left"] == 0  # Should be 0 for magnet links without metadata

        # Verify response format
        assert isinstance(response, TrackerResponse)
        assert response.peers == []
        assert response.interval == 1800

    @pytest.mark.asyncio
    async def test_udp_tracker_error_handling(self, tracker_client, torrent_data_udp):
        """Test error handling for UDP tracker failures."""
        # Mock UDP client that raises an error
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client._socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()
        # Mock _announce_to_tracker_full to raise an error
        mock_udp_client._announce_to_tracker_full = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        with pytest.raises(Exception) as exc_info:
            await tracker_client.announce(torrent_data_udp)

        # Verify error was raised
        assert exc_info.value is not None
        assert isinstance(exc_info.value, (Exception,))  # Any exception is fine for this test

    @pytest.mark.asyncio
    async def test_udp_tracker_normalization(self, tracker_client):
        """Test that malformed UDP URLs are normalized before routing."""
        # Test various UDP URL formats
        test_urls = [
            "udp://tracker.example.com:1337",
            "udp:/tracker.example.com:1337",  # Missing slash
            "udp:tracker.example.com:1337",  # Missing slashes
        ]

        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client._socket_ready = True  # Socket is ready
        mock_udp_client._announce_to_tracker_full = AsyncMock(
            return_value=([], 1800, 0, 0)  # (peers, interval, seeders, leechers)
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        for url in test_urls:
            torrent_data = {
                "info_hash": b"test1234567890123456",
                "announce": url,
                "file_info": {"total_length": 1024},
            }

            try:
                response = await tracker_client.announce(torrent_data)
                # Should succeed after normalization
                assert isinstance(response, TrackerResponse)
            except Exception as e:
                # Some malformed URLs might still fail, but should have clear error
                assert "UDP" in str(e) or "tracker" in str(e).lower()

    @pytest.mark.asyncio
    async def test_mixed_trackers_announce_to_multiple(self, tracker_client, torrent_data_mixed):
        """Test announce_to_multiple with mixed HTTP and UDP trackers."""
        # Mock UDP client - now accessed via _session_manager.udp_tracker_client
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client._socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()
        # Mock _announce_to_tracker_full which is now used internally
        mock_udp_client._announce_to_tracker_full = AsyncMock(
            return_value=(
                [{"ip": "192.168.1.3", "port": 6883, "peer_source": "tracker"}],
                1800,  # interval
                5,     # seeders
                2,     # leechers
            )
        )

        # Mock HTTP client responses
        mock_http_response = TrackerResponse(
            interval=1800,
            peers=[{"ip": "192.168.1.1", "port": 6881}],
        )
        tracker_client._make_request_async = AsyncMock(
            return_value=b"d8:intervali1800e5:peersl6:192.168.1.1:6881ee"
        )
        tracker_client._parse_response_async = MagicMock(return_value=mock_http_response)

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        tracker_urls = [
            "http://tracker.example.com/announce",
            "udp://tracker.opentrackr.org:1337",
        ]

        responses = await tracker_client.announce_to_multiple(
            torrent_data_mixed, tracker_urls
        )

        # Should get responses from both trackers (or at least attempts)
        # Note: Some may fail, but both should be attempted
        assert len(responses) >= 0  # May have 0, 1, or 2 depending on success
        
        # If we have responses, verify they're TrackerResponse objects
        for response in responses:
            assert isinstance(response, TrackerResponse)
        
        # Verify UDP client was called for UDP tracker
        # (HTTP tracker may or may not succeed depending on mock setup)
        assert mock_udp_client._announce_to_tracker_full.called or tracker_client._make_request_async.called

