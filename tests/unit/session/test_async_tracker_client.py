"""Tests for async tracker client integration in session manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.models import PeerInfo, TrackerResponse
from ccbt.session.session import AsyncSessionManager


class TestGetPeersFromTrackers:
    """Test cases for _get_peers_from_trackers method."""

    @pytest.fixture
    def session_manager(self):
        """Create AsyncSessionManager instance."""
        return AsyncSessionManager()

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_success(self, session_manager):
        """Test successful peer retrieval from trackers."""
        tracker_urls = ["http://tracker1.example.com/announce", "http://tracker2.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        # Create mock peer responses
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        peer2 = PeerInfo(ip="192.168.1.2", port=6882, peer_source="tracker")
        peer3 = PeerInfo(ip="192.168.1.3", port=6883, peer_source="tracker")

        mock_response1 = TrackerResponse(
            interval=1800,
            peers=[peer1, peer2],
            complete=10,
            incomplete=5,
        )
        mock_response2 = TrackerResponse(
            interval=1800,
            peers=[peer2, peer3],  # peer2 is duplicate
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce = AsyncMock(side_effect=[mock_response1, mock_response2])

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            # Should have 3 unique peers (peer2 appears in both responses)
            assert len(peers) == 3
            assert {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"} in peers
            assert {"ip": "192.168.1.2", "port": 6882, "peer_source": "tracker"} in peers
            assert {"ip": "192.168.1.3", "port": 6883, "peer_source": "tracker"} in peers

            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_empty_urls(self, session_manager):
        """Test with empty tracker URLs list."""
        peers = await session_manager._get_peers_from_trackers([], b"test1234567890123456", 6881)
        assert peers == []

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_tracker_failure(self, session_manager):
        """Test handling of tracker announce failures."""
        tracker_urls = ["http://tracker1.example.com/announce", "http://tracker2.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        # First tracker succeeds, second fails
        mock_response = TrackerResponse(
            interval=1800,
            peers=[PeerInfo(ip="192.168.1.1", port=6881)],
            complete=10,
            incomplete=5,
        )
        mock_client.announce = AsyncMock(side_effect=[mock_response, Exception("Tracker error")])

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            # Should return peers from successful tracker
            assert len(peers) == 1
            assert {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"} in peers

            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_all_fail(self, session_manager):
        """Test when all trackers fail."""
        tracker_urls = ["http://tracker1.example.com/announce", "http://tracker2.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce = AsyncMock(side_effect=Exception("Tracker error"))

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            # Should return empty list
            assert peers == []
            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_client_start_failure(self, session_manager):
        """Test handling of tracker client start failure."""
        tracker_urls = ["http://tracker1.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        mock_client = AsyncMock()
        mock_client.start = AsyncMock(side_effect=Exception("Start error"))
        mock_client.stop = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            # Should return empty list
            assert peers == []

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_peer_deduplication(self, session_manager):
        """Test that peers are deduplicated by (ip, port)."""
        tracker_urls = ["http://tracker1.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        # Create duplicate peers
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        peer2 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")  # Duplicate

        mock_response = TrackerResponse(
            interval=1800,
            peers=[peer1, peer2],
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce = AsyncMock(return_value=mock_response)

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            # Should have only one peer (duplicates removed)
            assert len(peers) == 1
            assert {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"} in peers

    @pytest.mark.asyncio
    async def test_get_peers_from_trackers_empty_peer_source(self, session_manager):
        """Test that peer_source defaults to 'tracker' when None."""
        tracker_urls = ["http://tracker1.example.com/announce"]
        info_hash = b"test1234567890123456"
        port = 6881

        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source=None)

        mock_response = TrackerResponse(
            interval=1800,
            peers=[peer],
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce = AsyncMock(return_value=mock_response)

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            peers = await session_manager._get_peers_from_trackers(tracker_urls, info_hash, port)

            assert len(peers) == 1
            assert peers[0]["peer_source"] == "tracker"

