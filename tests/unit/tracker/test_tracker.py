"""Tests for tracker communication functionality.
"""

import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.core.bencode import encode
from ccbt.discovery import tracker as tracker_mod
from ccbt.discovery.tracker import (
    AsyncTrackerClient,
    TrackerClient,
    TrackerError,
    TrackerResponse,
    TrackerSession,
)


class TestTrackerClient:
    """Test cases for TrackerClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TrackerClient()
        # Clear any state from previous tests
        self.client.sessions.clear()

        # Sample torrent data
        self.torrent_data = {
            "announce": "http://tracker.example.com:6969/announce",
            "info_hash": b"x" * 20,
            "peer_id": b"-CC0101-" + b"x" * 12,
            "file_info": {
                "total_length": 12345,
            },
        }

    def test_generate_peer_id(self):
        """Test peer ID generation."""
        peer_id = self.client._generate_peer_id()

        assert isinstance(peer_id, bytes)
        assert len(peer_id) == 20
        assert peer_id.startswith(b"-CC0101-")

    def test_build_tracker_url(self):
        """Test tracker URL building."""
        url = self.client._build_tracker_url(
            "http://tracker.example.com:6969/announce",
            b"info_hash_20_bytes__",
            b"peer_id_20_bytes____",
            6881,
            0,
            0,
            12345,
            "started",
        )

        # Check base URL
        assert "http://tracker.example.com:6969/announce" in url

        # Check parameters
        assert "info_hash=" in url
        assert "peer_id=" in url
        assert "port=6881" in url
        assert "uploaded=0" in url
        assert "downloaded=0" in url
        assert "left=12345" in url
        assert "compact=1" in url
        assert "event=started" in url

    def test_build_tracker_url_no_event(self):
        """Test tracker URL building without event."""
        url = self.client._build_tracker_url(
            "http://tracker.example.com:6969/announce",
            b"info_hash_20_bytes__",
            b"peer_id_20_bytes____",
            6881,
            0,
            0,
            12345,
            "",
        )

        assert "event=" not in url

    def test_build_tracker_url_with_query_params(self):
        """Test tracker URL building when base URL already has query params."""
        url = self.client._build_tracker_url(
            "http://tracker.example.com:6969/announce?existing=param",
            b"info_hash_20_bytes__",
            b"peer_id_20_bytes____",
            6881,
            0,
            0,
            12345,
            "started",
        )

        assert "existing=param&" in url

    def test_parse_compact_peers(self):
        """Test parsing compact peer format."""
        # Create mock peer data: 2 peers
        # Peer 1: IP 192.168.1.100, port 6881
        # Peer 2: IP 10.0.0.5, port 12345
        peer_data = (
            b"\xc0\xa8\x01\x64"  # 192.168.1.100
            b"\x1a\xe1"  # 6881 (0x1ae1)
            b"\x0a\x00\x00\x05"  # 10.0.0.5
            b"\x30\x39"  # 12345 (0x3039)
        )

        peers = self.client._parse_compact_peers(peer_data)

        assert len(peers) == 2

        # Check first peer
        assert peers[0]["ip"] == "192.168.1.100"
        assert peers[0]["port"] == 6881

        # Check second peer
        assert peers[1]["ip"] == "10.0.0.5"
        assert peers[1]["port"] == 12345

    def test_parse_compact_peers_invalid_length(self):
        """Test parsing compact peer data with invalid length."""
        # Invalid length (not multiple of 6)
        invalid_data = b"x" * 7

        with pytest.raises(TrackerError, match="Invalid compact peers data length"):
            self.client._parse_compact_peers(invalid_data)

    def test_parse_response_success(self):
        """Test parsing successful tracker response."""
        # Mock tracker response
        response_data = {
            b"interval": 1800,
            b"peers": b"\xc0\xa8\x01\x64\x1a\xe1\x0a\x00\x00\x05\x30\x39",  # 2 peers
        }

        encoded_response = encode(response_data)

        response = self.client._parse_response(encoded_response)

        assert response["interval"] == 1800
        assert len(response["peers"]) == 2
        assert response["peers"][0]["ip"] == "192.168.1.100"
        assert response["peers"][0]["port"] == 6881

    def test_parse_response_failure(self):
        """Test parsing tracker failure response."""
        # Mock failure response
        response_data = {
            b"failure reason": b"Tracker is down for maintenance",
        }

        encoded_response = encode(response_data)

        with pytest.raises(TrackerError, match="Tracker failure"):
            self.client._parse_response(encoded_response)

    def test_parse_response_non_bencode_payload(self):
        """Test rejecting non-bencode tracker responses."""
        response_data = b"<html><body>tracker down for maintenance</body></html>"

        with pytest.raises(TrackerError, match="Invalid tracker payload"):
            self.client._parse_response(response_data)

    def test_parse_response_dictionary_peer_type_hardening(self):
        """Test dictionary peer payload ignores invalid peer entries but keeps valid ones."""
        response_data = {
            b"interval": 1800,
            b"peers": [
                {b"ip": b"192.168.1.100", b"port": 6881},
                {"ip": "198.51.100.5", "port": "6881"},
                {b"ip": b"", b"port": 6881},
                {"ip": "invalid", "port": "not_a_number"},
                "invalid-entry",
            ],
        }

        encoded_response = encode(response_data)
        response = self.client._parse_response(encoded_response)

        assert len(response["peers"]) == 2
        assert response["peers"][0]["ip"] == "192.168.1.100"
        assert response["peers"][0]["port"] == 6881
        assert response["peers"][1]["ip"] == "198.51.100.5"
        assert response["peers"][1]["port"] == 6881

    def test_parse_response_missing_fields(self):
        """Test parsing response missing required fields."""
        # Missing interval
        response_data = {
            b"peers": b"\xc0\xa8\x01\x64\x1a\xe1",
        }

        encoded_response = encode(response_data)

        with pytest.raises(TrackerError, match="Missing interval"):
            self.client._parse_response(encoded_response)

    @patch("urllib.request.urlopen")
    def test_make_request_success(self, mock_urlopen):
        """Test successful HTTP request to tracker."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = encode(
            {
                b"interval": 1800,
                b"peers": b"\xc0\xa8\x01\x64\x1a\xe1",
            },
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        response_data = self.client._make_request("http://tracker.example.com/announce")

        # Verify request was made correctly
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        assert call_args.full_url == "http://tracker.example.com/announce"
        from ccbt.utils.version import get_user_agent

        assert call_args.headers["User-agent"] == get_user_agent()

        # Verify response data
        assert isinstance(response_data, bytes)

    @patch("urllib.request.urlopen")
    def test_make_request_http_error(self, mock_urlopen):
        """Test HTTP error response from tracker."""
        # Mock HTTP error by making urlopen raise HTTPError
        mock_urlopen.side_effect = HTTPError(None, 404, "Not Found", None, None)

        with pytest.raises(TrackerError, match="HTTP 404"):
            self.client._make_request("http://tracker.example.com/announce")

    @patch("urllib.request.urlopen")
    def test_make_request_network_error(self, mock_urlopen):
        """Test network error when contacting tracker."""
        # Mock network error
        mock_urlopen.side_effect = Exception("Network timeout")

        with pytest.raises(TrackerError, match="Request failed"):
            self.client._make_request("http://tracker.example.com/announce")

    @patch("ccbt.discovery.tracker.TrackerClient._make_request")
    def test_announce_success(self, mock_make_request):
        """Test successful tracker announce."""
        # Mock tracker response
        response_data = encode(
            {
                b"interval": 1800,
                b"peers": b"\xc0\xa8\x01\x64\x1a\xe1\x0a\x00\x00\x05\x30\x39",
            },
        )
        mock_make_request.return_value = response_data

        response = self.client.announce(self.torrent_data)

        # Check response structure
        assert "interval" in response
        assert "peers" in response
        assert response["interval"] == 1800
        assert len(response["peers"]) == 2

        # Check that request was made with correct URL
        mock_make_request.assert_called_once()
        call_url = mock_make_request.call_args[0][0]
        assert "info_hash=" in call_url
        assert "peer_id=" in call_url
        assert "port=6881" in call_url
        assert "event=started" in call_url

    @patch("ccbt.discovery.tracker.TrackerClient._make_request")
    def test_announce_with_custom_params(self, mock_make_request):
        """Test tracker announce with custom parameters."""
        response_data = encode(
            {
                b"interval": 1800,
                b"peers": b"",
            },
        )
        mock_make_request.return_value = response_data

        self.client.announce(
            self.torrent_data,
            port=9999,
            uploaded=1000,
            downloaded=500,
            left=10000,
            event="completed",
        )

        # Check that custom parameters were used
        call_url = mock_make_request.call_args[0][0]
        assert "port=9999" in call_url
        assert "uploaded=1000" in call_url
        assert "downloaded=500" in call_url
        assert "left=10000" in call_url
        assert "event=completed" in call_url

    @patch("ccbt.discovery.tracker.TrackerClient._make_request")
    def test_announce_tracker_error(self, mock_make_request):
        """Test tracker announce with tracker error response."""
        # Ensure clean state - reset any cached state
        if hasattr(self.client, "_last_announce"):
            delattr(self.client, "_last_announce")

        # Clear tracker sessions to avoid state pollution
        self.client.sessions.clear()

        # Ensure torrent_data has required fields (may be modified by other tests)
        if "peer_id" not in self.torrent_data:
            self.torrent_data["peer_id"] = b"-CC0101-" + b"x" * 12
        if "info_hash" not in self.torrent_data:
            self.torrent_data["info_hash"] = b"x" * 20

        # Mock failure response
        response_data = encode(
            {
                b"failure reason": b"Invalid request",
            },
        )
        mock_make_request.return_value = response_data

        with pytest.raises(TrackerError, match="Tracker failure"):
            self.client.announce(self.torrent_data)

        # Verify the mock was called
        assert mock_make_request.called, "Tracker request was not made"

    def test_announce_generates_peer_id(self):
        """Test that announce generates peer ID if missing."""
        # Remove peer_id from torrent data
        del self.torrent_data["peer_id"]

        with patch.object(self.client, "_make_request") as mock_request:
            response_data = encode(
                {
                    b"interval": 1800,
                    b"peers": b"",
                },
            )
            mock_request.return_value = response_data

            self.client.announce(self.torrent_data)

            # Check that peer_id was added
            assert "peer_id" in self.torrent_data
            assert self.torrent_data["peer_id"].startswith(b"-CC0101-")



class TestAsyncTrackerClientTrackerResilience:
    """Tests for tracker resilience behavior in AsyncTrackerClient."""

    @pytest.mark.asyncio
    async def test_announce_to_multiple_skips_quarantined_trackers(self):
        """Quarantined trackers should not be announced until cooldown passes."""
        client = AsyncTrackerClient()
        client.session = Mock()
        client.health_manager._known_good_trackers = set()

        bad_url = "http://invalid.tracker.example/announce"
        client.sessions[bad_url] = TrackerSession(
            url=bad_url,
            quarantine_until=time.time() + 120.0,
            quarantine_reason="invalid payload",
        )

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": "http://fallback.tracker.example/announce",
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [bad_url],
            )

        assert responses == []

    @pytest.mark.asyncio
    async def test_announce_to_multiple_uses_fallback_for_quarantined_trackers(self):
        """Fallback trackers should still run when active trackers are temporarily quarantined."""
        client = AsyncTrackerClient()
        client.session = Mock()

        bad_url = "http://invalid.tracker.example/announce"
        fallback_url = "http://fallback.tracker.example/announce"
        client.sessions[bad_url] = TrackerSession(
            url=bad_url,
            quarantine_until=time.time() + 120.0,
            quarantine_reason="invalid payload",
        )
        client.health_manager._known_good_trackers = {fallback_url}

        announced_urls: list[str] = []

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            announced_urls.append(str(torrent_data["announce"]))
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": "http://invalid.tracker.example/announce",
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [bad_url],
            )

        assert len(responses) == 1
        assert announced_urls == [fallback_url]

    @pytest.mark.asyncio
    async def test_announce_to_multiple_uses_fallback_for_backed_off_trackers(self):
        """Backoff-skipped trackers should still fan out to fallback trackers."""
        client = AsyncTrackerClient()
        client.session = Mock()

        bad_url = "http://rate-limited.tracker.example/announce"
        fallback_url = "http://fallback.tracker.example/announce"
        client.sessions[bad_url] = TrackerSession(
            url=bad_url,
            failure_count=1,
            backoff_delay=120.0,
            last_failure=time.time(),
        )
        client.health_manager._known_good_trackers = {fallback_url}

        announced_urls: list[str] = []

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            announced_urls.append(str(torrent_data["announce"]))
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": bad_url,
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [bad_url],
            )

        assert len(responses) == 1
        assert announced_urls == [fallback_url]

    @pytest.mark.asyncio
    async def test_announce_to_multiple_fallback_preserves_healthy_trackers(self):
        """A single bad tracker should not suppress a healthy tracker in the same announce batch."""
        client = AsyncTrackerClient()
        client.session = Mock()

        bad_url = "http://bad.tracker.example/announce"
        good_url = "http://good.tracker.example/announce"
        client.sessions[bad_url] = TrackerSession(
            url=bad_url,
            quarantine_until=time.time() + 120.0,
            quarantine_reason="invalid payload",
        )

        announced_urls: list[str] = []

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            announced_urls.append(str(torrent_data["announce"]))
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            await client.announce_to_multiple(
                {
                    "announce": "http://good.tracker.example/announce",
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [bad_url, good_url],
            )

        assert announced_urls == [good_url]

    @pytest.mark.asyncio
    async def test_announce_to_multiple_continues_after_timeout_tracker_error(self):
        """Timeouts from one tracker should not block successful responses from others."""
        client = AsyncTrackerClient()
        client.session = Mock()

        timeout_url = "http://timeout.tracker.example/announce"
        healthy_url = "http://healthy.tracker.example/announce"

        announced_urls: list[str] = []

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            announce_url = str(torrent_data["announce"])
            announced_urls.append(announce_url)
            if announce_url == timeout_url:
                raise TimeoutError("Timeout waiting for tracker response")
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": timeout_url,
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [timeout_url, healthy_url],
            )

        assert len(responses) == 1
        assert len(announced_urls) == 2
        assert timeout_url in announced_urls
        assert healthy_url in announced_urls

    @pytest.mark.asyncio
    async def test_announce_to_multiple_non_tracker_error_updates_backoff(self):
        """Transport-level tracker errors should be tracked for backoff in announce_to_multiple."""
        client = AsyncTrackerClient()
        client.session = Mock()
        client.health_manager._known_good_trackers = set()

        timeout_url = "http://flaky.tracker.example/announce"
        announced_urls: list[str] = []

        async def fake_announce(
            torrent_data: dict[str, object], *_args: object, **_kwargs: object
        ) -> TrackerResponse:
            announce_url = str(torrent_data["announce"])
            announced_urls.append(announce_url)
            if announce_url == timeout_url:
                raise TimeoutError("transport timeout")
            return TrackerResponse(interval=1800, peers=[])

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": timeout_url,
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [timeout_url],
                allow_all_failure_retry=False,
            )

        assert responses == []
        assert announced_urls == [timeout_url]
        assert timeout_url in client.sessions
        timeout_session = client.sessions[timeout_url]
        assert timeout_session.failure_count == 1
        assert timeout_session.last_failure > 0.0

        with patch.object(client, "_announce_to_tracker", new=fake_announce):
            responses = await client.announce_to_multiple(
                {
                    "announce": timeout_url,
                    "info_hash": b"x" * 20,
                    "peer_id": b"-CC0101-" + b"x" * 12,
                    "file_info": {"total_length": 12345},
                },
                [timeout_url],
                allow_all_failure_retry=False,
            )

        assert responses == []
        assert timeout_session.failure_count == 1
        assert announced_urls == [timeout_url]

    def test_tracker_session_quarantine_on_repeated_invalid_payload_failures(self):
        """Invalid payload failures should increase streak and eventually quarantine a tracker."""
        client = AsyncTrackerClient()
        tracker_url = "http://invalid.tracker.example/announce"

        client._handle_tracker_failure(
            tracker_url,
            failure_reason="Invalid tracker payload (not bencode)",
        )
        first_session = client.sessions[tracker_url]
        assert first_session.failure_streak == 1
        assert first_session.quarantine_until == 0.0

        client._handle_tracker_failure(
            tracker_url,
            failure_reason="Invalid tracker payload (not bencode)",
        )
        second_session = client.sessions[tracker_url]
        assert second_session.failure_streak == 2
        assert second_session.quarantine_until > time.time()

    def test_tracker_session_quarantine_on_html_payload_on_first_failure(self) -> None:
        """HTML payloads should quarantine immediately because they are invalid tracker APIs."""
        client = AsyncTrackerClient()
        tracker_url = "http://html.tracker.example/announce"

        client._handle_tracker_failure(
            tracker_url,
            failure_reason="Invalid tracker payload (html/xml payload) for tracker response",
        )
        first_session = client.sessions[tracker_url]
        assert first_session.failure_streak == 1
        assert first_session.quarantine_until > time.time()

    @pytest.mark.asyncio
    async def test_announce_udp_skip_sets_context_reason_for_logging(self) -> None:
        """When UDP client is missing, skip reason is recorded for announce_to_multiple logs."""
        client = AsyncTrackerClient()
        await client.start()
        client._session_manager = SimpleNamespace(udp_tracker_client=None)
        td = {
            "announce": "udp://127.0.0.1:6969/announce",
            "info_hash": b"i" * 20,
            "peer_id": b"-CC0101-" + b"0" * 12,
            "file_info": {"total_length": 100},
        }
        out = await client.announce(td, port=6881, left=100, event="started")
        assert out is None
        assert (
            tracker_mod._tracker_announce_skip_reason.get()
            == "udp_client_unavailable"
        )
        await client.stop()

