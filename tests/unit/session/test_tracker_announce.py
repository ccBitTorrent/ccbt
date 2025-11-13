"""Tests for tracker announce functionality in session manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.models import PeerInfo, TrackerResponse
from ccbt.session.download_manager import AsyncDownloadManager, _announce_to_trackers


class TestAnnounceToTrackers:
    """Test cases for _announce_to_trackers function."""

    @pytest.fixture
    def torrent_data(self):
        """Create sample torrent data."""
        return {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "announce": "http://tracker.example.com/announce",
            "announce_list": ["http://tracker1.example.com/announce", "http://tracker2.example.com/announce"],
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"piece_hash_1"]
            },
            "file_info": {
                "total_length": 1024
            }
        }

    @pytest.fixture
    def download_manager(self, torrent_data):
        """Create AsyncDownloadManager instance."""
        with patch("ccbt.session.download_manager.get_config"):
            with patch("ccbt.piece.async_piece_manager.AsyncPieceManager"):
                return AsyncDownloadManager(torrent_data)

    @pytest.mark.asyncio
    async def test_announce_to_trackers_success(self, torrent_data, download_manager):
        """Test successful tracker announce and download start."""
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        peer2 = PeerInfo(ip="192.168.1.2", port=6882, peer_source="tracker")

        mock_response1 = TrackerResponse(
            interval=1800,
            peers=[peer1],
            complete=10,
            incomplete=5,
        )
        mock_response2 = TrackerResponse(
            interval=1800,
            peers=[peer2],
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce_to_multiple = AsyncMock(return_value=[mock_response1, mock_response2])

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config") as mock_get_config:
                mock_config = MagicMock()
                mock_config.network.listen_port = 6881
                mock_get_config.return_value = mock_config

                await _announce_to_trackers(torrent_data, download_manager, port=6881)

                mock_client.start.assert_called_once()
                mock_client.announce_to_multiple.assert_called_once()
                download_manager.start_download.assert_called_once()

                # Verify peers were passed correctly
                call_args = download_manager.start_download.call_args[0][0]
                assert len(call_args) == 2
                assert {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"} in call_args
                assert {"ip": "192.168.1.2", "port": 6882, "peer_source": "tracker"} in call_args

                mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_announce_to_trackers_no_trackers(self, download_manager):
        """Test with no tracker URLs."""
        torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
        }

        download_manager.start_download = AsyncMock()

        with patch("ccbt.session.download_manager.get_config"):
            await _announce_to_trackers(torrent_data, download_manager, port=6881)

            # Should not start download
            assert not download_manager.start_download.called

    @pytest.mark.asyncio
    async def test_announce_to_trackers_fallback_to_announce(self, download_manager):
        """Test fallback to single announce URL when announce_list is empty."""
        torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "announce": "http://tracker.example.com/announce",
        }

        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
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
        mock_client.announce_to_multiple = AsyncMock(return_value=[mock_response])

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config"):
                await _announce_to_trackers(torrent_data, download_manager, port=6881)

                mock_client.announce_to_multiple.assert_called_once()
                download_manager.start_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_announce_to_trackers_no_peers(self, torrent_data, download_manager):
        """Test when trackers return no peers."""
        mock_response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce_to_multiple = AsyncMock(return_value=[mock_response])

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config"):
                with patch("ccbt.session.download_manager.logging") as mock_logging:
                    await _announce_to_trackers(torrent_data, download_manager, port=6881)

                    # Should not start download
                    assert not download_manager.start_download.called

                    mock_client.start.assert_called_once()
                    mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_announce_to_trackers_announce_failure(self, torrent_data, download_manager):
        """Test handling of tracker announce failures."""
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce_to_multiple = AsyncMock(side_effect=Exception("Tracker error"))

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config"):
                # Should not raise exception
                await _announce_to_trackers(torrent_data, download_manager, port=6881)

                # Should not start download
                assert not download_manager.start_download.called

                mock_client.start.assert_called_once()
                mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_announce_to_trackers_peer_deduplication(self, torrent_data, download_manager):
        """Test that peers are deduplicated across multiple tracker responses."""
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        peer2 = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")  # Duplicate

        mock_response1 = TrackerResponse(
            interval=1800,
            peers=[peer1],
            complete=10,
            incomplete=5,
        )
        mock_response2 = TrackerResponse(
            interval=1800,
            peers=[peer2],  # Same peer
            complete=10,
            incomplete=5,
        )

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
        mock_client.announce_to_multiple = AsyncMock(return_value=[mock_response1, mock_response2])

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config"):
                await _announce_to_trackers(torrent_data, download_manager, port=6881)

                # Should have only one peer (duplicate removed)
                call_args = download_manager.start_download.call_args[0][0]
                assert len(call_args) == 1
                assert {"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"} in call_args

    @pytest.mark.asyncio
    async def test_announce_to_trackers_filters_empty_urls(self, download_manager):
        """Test that empty or None tracker URLs are filtered out."""
        torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "announce_list": ["http://tracker1.example.com/announce", "", None, "http://tracker2.example.com/announce"],
        }

        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
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
        mock_client.announce_to_multiple = AsyncMock(return_value=[mock_response])

        download_manager.start_download = AsyncMock()

        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
            with patch("ccbt.session.download_manager.get_config"):
                await _announce_to_trackers(torrent_data, download_manager, port=6881)

                # Should only announce to non-empty URLs
                call = mock_client.announce_to_multiple.call_args
                tracker_urls = call[0][1]  # Second positional argument
                assert len(tracker_urls) == 2
                assert "http://tracker1.example.com/announce" in tracker_urls
                assert "http://tracker2.example.com/announce" in tracker_urls

