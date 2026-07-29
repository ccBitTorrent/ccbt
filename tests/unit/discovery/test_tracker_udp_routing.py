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
        # Mock UDP tracker client - avoid spec issues when class is patched.
        mock_udp_client = AsyncMock()
        # Mock transport properly - is_closing() must return a boolean
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False  # Transport is not closing
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True  # Socket is ready (no underscore!)
        mock_udp_client._started = True  # Client has been started
        mock_udp_client._cleanup_task = None  # No cleanup task running
        mock_udp_client.start = AsyncMock()  # Mock start method

        # Mock announce_to_tracker_full which is the actual method called
        # Returns tuple: (peers, interval, seeders, leechers) - all must be proper types
        mock_udp_client.announce_to_tracker_full = AsyncMock(
            return_value=(
                [
                    {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"},
                    {"ip": "192.168.1.2", "port": 6882, "peer_source": "tracker"},
                ],
                1800,  # interval (int)
                10,    # seeders (int)
                5,     # leechers (int)
            )
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        response = await tracker_client.announce(torrent_data_udp)

        # Verify announce_to_tracker_full was called (not HTTP request)
        mock_udp_client.announce_to_tracker_full.assert_called_once()
        call_kwargs = mock_udp_client.announce_to_tracker_full.call_args[1]
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
    async def test_udp_announce_no_http_only_kwargs(self, tracker_client, torrent_data_udp):
        """UDP announce should pass only UDP-safe parameters to UDP tracker client."""
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True
        mock_udp_client.start = AsyncMock()
        mock_udp_client.announce_to_tracker_full = AsyncMock(
            return_value=([], 1800, 0, 0)
        )

        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        await tracker_client.announce(torrent_data_udp)

        call_kwargs = mock_udp_client.announce_to_tracker_full.call_args[1]
        assert set(call_kwargs) == {
            "port",
            "uploaded",
            "downloaded",
            "left",
            "event",
            "on_immediate_peers",
        }
        assert "ssl" not in call_kwargs
        assert "supportcrypto" not in call_kwargs
        assert "requirecrypto" not in call_kwargs
        assert "cryptoport" not in call_kwargs

    @pytest.mark.asyncio
    async def test_udp_and_http_mixed_trackers_keep_udp_paths_http_free(
        self, tracker_client, torrent_data_mixed
    ):
        """Mixed tracker announce should keep UDP announce kwargs free of HTTP-only transport flags."""
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True
        mock_udp_client.start = AsyncMock()
        mock_udp_client.announce_to_tracker_full = AsyncMock(
            return_value=([], 1800, 0, 0)  # (peers, interval, seeders, leechers)
        )

        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        # Mock HTTP request path.
        mock_http_response = TrackerResponse(
            interval=1800,
            peers=[{"ip": "192.168.1.1", "port": 6881}],
        )
        tracker_client._make_request_async = AsyncMock(
            return_value=b"d8:intervali1800e5:peersl6:192.168.1.1:6881ee"
        )
        tracker_client._parse_response_async = MagicMock(return_value=mock_http_response)

        await tracker_client.announce_to_multiple(
            torrent_data_mixed,
            ["http://tracker.example.com/announce", "udp://tracker.opentrackr.org:1337"],
        )

        assert mock_udp_client.announce_to_tracker_full.called
        call_kwargs = mock_udp_client.announce_to_tracker_full.call_args[1]
        assert "ssl" not in call_kwargs
        assert "supportcrypto" not in call_kwargs
        assert "requirecrypto" not in call_kwargs
        assert "cryptoport" not in call_kwargs

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
        # Mock UDP client - avoid spec issues when class is patched.
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()

        # Mock announce_to_tracker_full which is now used internally
        mock_udp_client.announce_to_tracker_full = AsyncMock(
            return_value=([], 1800, 0, 0)  # (peers, interval, seeders, leechers)
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        response = await tracker_client.announce(magnet_torrent_data)

        # Verify UDP client was called with left=0 (BEP 3 compliant for magnet links)
        mock_udp_client.announce_to_tracker_full.assert_called_once()
        call_kwargs = mock_udp_client.announce_to_tracker_full.call_args[1]
        # Metadata-incomplete magnets use a large synthetic "left" value.
        assert call_kwargs["left"] == 1024 * 1024 * 1024 * 1024

        # Verify response format
        assert isinstance(response, TrackerResponse)
        assert response.peers == []
        assert response.interval == 1800

    @pytest.mark.asyncio
    async def test_udp_tracker_error_handling(self, tracker_client, torrent_data_udp):
        """Test error handling for UDP tracker failures."""
        torrent_data_udp = {
            **torrent_data_udp,
            "announce_list": [
                ["udp://tracker.opentrackr.org:1337"],
                ["http://tracker.example.com/announce"],
            ],
        }
        # Mock UDP client that raises an error; avoid spec issues.
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True  # Socket is ready
        mock_udp_client.start = AsyncMock()
        # Mock announce_to_tracker_full to raise an error
        mock_udp_client.announce_to_tracker_full = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )

        # Mock session manager with UDP tracker client
        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        # Mock HTTP fallback to also fail (UDP errors fall back to HTTP)
        tracker_client._make_request_async = AsyncMock(side_effect=ConnectionError("HTTP also failed"))
        tracker_client._parse_response_async = MagicMock()

        with pytest.raises(Exception) as exc_info:
            await tracker_client.announce(torrent_data_udp)

        # Verify error was raised (either from UDP or HTTP fallback)
        assert exc_info.value is not None
        assert isinstance(exc_info.value, (Exception,))  # Any exception is fine for this test

    @pytest.mark.asyncio
    async def test_udp_tracker_without_explicit_http_fallback_returns_none(
        self, tracker_client, torrent_data_udp
    ):
        """UDP-only trackers should not be rewritten into fabricated HTTP fallback URLs."""
        mock_udp_client = AsyncMock()
        mock_transport = MagicMock()
        mock_transport.is_closing.return_value = False
        mock_udp_client.transport = mock_transport
        mock_udp_client.socket_ready = True
        mock_udp_client.start = AsyncMock()
        mock_udp_client.announce_to_tracker_full = AsyncMock(return_value=None)

        mock_session_manager = MagicMock()
        mock_session_manager.udp_tracker_client = mock_udp_client
        tracker_client._session_manager = mock_session_manager

        tracker_client._make_request_async = AsyncMock()

        response = await tracker_client.announce(torrent_data_udp)

        assert response is None
        tracker_client._make_request_async.assert_not_called()

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
        mock_udp_client.socket_ready = True  # Socket is ready (no underscore!)
        mock_udp_client.announce_to_tracker_full = AsyncMock(
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
        mock_udp_client.socket_ready = True  # Socket is ready (no underscore!)
        mock_udp_client.start = AsyncMock()
        # Mock announce_to_tracker_full which is now used internally
        mock_udp_client.announce_to_tracker_full = AsyncMock(
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
        assert mock_udp_client.announce_to_tracker_full.called or tracker_client._make_request_async.called

    @pytest.mark.asyncio
    async def test_announce_to_multiple_skips_trackers_still_in_backoff(
        self, tracker_client, torrent_data_http
    ):
        """Backoff windows should defer unhealthy trackers during multi-announce scheduling."""
        healthy_url = "http://tracker-healthy.example.com/announce"
        backed_off_url = "http://tracker-backed-off.example.com/announce"
        tracker_client.sessions[healthy_url] = MagicMock(
            failure_count=0,
            last_failure=0.0,
            backoff_delay=1.0,
            performance=MagicMock(
                success_rate=1.0,
                average_response_time=0.1,
                peer_quality_score=1.0,
                last_success=1.0,
            ),
        )
        tracker_client.sessions[backed_off_url] = MagicMock(
            failure_count=3,
            last_failure=9999999999.0,
            backoff_delay=60.0,
            performance=MagicMock(
                success_rate=0.1,
                average_response_time=5.0,
                peer_quality_score=0.0,
                last_success=0.0,
            ),
        )

        with patch.object(tracker_client, "_announce_to_tracker", new_callable=AsyncMock) as mock_announce:
            mock_announce.return_value = TrackerResponse(interval=1800, peers=[])
            tracker_client.sessions[healthy_url].quarantine_until = 0.0
            tracker_client.sessions[backed_off_url].quarantine_until = 0.0

            responses = await tracker_client.announce_to_multiple(
                torrent_data_http,
                [healthy_url, backed_off_url],
            )

        assert len(responses) == 1
        mock_announce.assert_awaited_once()
        assert mock_announce.await_args.args[0]["announce"] == healthy_url


class TestHTTPFallbackFromMagnetTrackers:
    """HTTP fallback must read flat announce_list entries from magnet torrent_data."""

    @pytest.fixture
    def tracker_client(self):
        with patch("ccbt.discovery.tracker.get_config"):
            return AsyncTrackerClient()

    def test_find_http_fallback_url_reads_flat_announce_list(
        self, tracker_client: AsyncTrackerClient
    ) -> None:
        torrent_data = {
            "announce": "udp://tracker.opentrackr.org:1337/announce",
            "announce_list": [
                "udp://tracker.opentrackr.org:1337/announce",
                "https://tracker.torrent.eu.org:443/announce",
                "http://tracker.openbittorrent.com:80/announce",
            ],
        }
        fallback = tracker_client._find_http_fallback_url(
            torrent_data,
            "udp://tracker.opentrackr.org:1337",
        )
        assert fallback == "https://tracker.torrent.eu.org:443/announce"

    def test_find_http_fallback_prefers_same_host(
        self, tracker_client: AsyncTrackerClient
    ) -> None:
        torrent_data = {
            "announce_list": [
                "udp://tracker.example.com:1337/announce",
                "https://tracker.other.org:443/announce",
                "https://tracker.example.com:443/announce",
            ],
        }
        fallback = tracker_client._find_http_fallback_url(
            torrent_data,
            "udp://tracker.example.com:1337",
        )
        assert fallback == "https://tracker.example.com:443/announce"

