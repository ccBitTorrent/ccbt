"""Comprehensive unit tests for BitTorrentProtocol scrape_torrent method.

Tests protocol integration with HTTP/UDP tracker clients, result aggregation, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from ccbt.models import TorrentInfo, FileInfo

pytestmark = [pytest.mark.unit, pytest.mark.protocols]


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return Mock()


@pytest.fixture
def torrent_info():
    """Create sample TorrentInfo for testing."""
    return TorrentInfo(
        name="test_torrent",
        info_hash=b"x" * 20,
        announce="http://tracker.example.com/announce",
        announce_list=[["http://tracker.example.com/announce"]],
        files=[
            FileInfo(
                name="test_file.txt",
                length=1024,
                path=["test_file.txt"],
            )
        ],
        total_length=1024,
        piece_length=16384,
        pieces=[],
        num_pieces=1,
    )


@pytest.fixture
def protocol(mock_session_manager):
    """Create BitTorrentProtocol instance for testing."""
    from ccbt.protocols.bittorrent import BitTorrentProtocol

    return BitTorrentProtocol(session_manager=mock_session_manager)


class TestScrapeTorrent:
    """Test scrape_torrent method."""

    @pytest.mark.asyncio
    async def test_scrape_torrent_http_success(self, protocol, torrent_info):
        """Test successful scrape from HTTP tracker."""
        # Mock HTTP tracker client
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(
            return_value={"seeders": 50, "leechers": 25, "completed": 500}
        )

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            return_value=mock_http_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            assert result["seeders"] == 50
            assert result["leechers"] == 25
            assert result["completed"] == 500
            mock_http_client.start.assert_called_once()
            mock_http_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_torrent_udp_success(self, protocol, torrent_info):
        """Test successful scrape from UDP tracker."""
        torrent_info.announce = "udp://tracker.example.com:6969"
        torrent_info.announce_list = [["udp://tracker.example.com:6969"]]

        # Mock UDP tracker client
        mock_udp_client = AsyncMock()
        mock_udp_client.start = AsyncMock()
        mock_udp_client.stop = AsyncMock()
        mock_udp_client.scrape = AsyncMock(
            return_value={"seeders": 75, "leechers": 30, "completed": 600}
        )

        with patch(
            "ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient",
            return_value=mock_udp_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            assert result["seeders"] == 75
            assert result["leechers"] == 30
            assert result["completed"] == 600
            mock_udp_client.start.assert_called_once()
            mock_udp_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_torrent_no_trackers(self, protocol, torrent_info):
        """Test scrape with no tracker URLs."""
        torrent_info.announce = ""
        torrent_info.announce_list = []

        result = await protocol.scrape_torrent(torrent_info)

        assert result["seeders"] == 0
        assert result["leechers"] == 0
        assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_scrape_torrent_unsupported_scheme(self, protocol, torrent_info):
        """Test scrape with unsupported tracker scheme."""
        torrent_info.announce = "ftp://tracker.example.com/announce"
        torrent_info.announce_list = [["ftp://tracker.example.com/announce"]]

        result = await protocol.scrape_torrent(torrent_info)

        # Should return zeros (no valid tracker)
        assert result["seeders"] == 0
        assert result["leechers"] == 0
        assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_scrape_torrent_http_empty_result(self, protocol, torrent_info):
        """Test scrape when HTTP tracker returns empty result."""
        # Mock HTTP tracker client returning empty
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(return_value={})

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            return_value=mock_http_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            # Should continue to next tracker or return zeros
            assert result["seeders"] == 0
            assert result["leechers"] == 0
            assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_scrape_torrent_http_zero_stats(self, protocol, torrent_info):
        """Test scrape when HTTP tracker returns zero stats."""
        # Mock HTTP tracker client returning zeros
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(
            return_value={"seeders": 0, "leechers": 0, "completed": 0}
        )

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            return_value=mock_http_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            # Should return zeros (not considered successful)
            assert result["seeders"] == 0
            assert result["leechers"] == 0
            assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_scrape_torrent_http_exception(self, protocol, torrent_info):
        """Test scrape when HTTP tracker raises exception."""
        # Mock HTTP tracker client raising exception
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(side_effect=Exception("Network error"))

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            return_value=mock_http_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            # Should continue to next tracker or return zeros
            assert result["seeders"] == 0
            assert result["leechers"] == 0
            assert result["completed"] == 0
            mock_http_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_torrent_multiple_trackers_first_fails(
        self, protocol, torrent_info
    ):
        """Test scrape tries multiple trackers when first fails."""
        torrent_info.announce_list = [
            ["http://tracker1.example.com/announce"],
            ["http://tracker2.example.com/announce"],
        ]

        # Mock first tracker failing, second succeeding
        mock_client1 = AsyncMock()
        mock_client1.start = AsyncMock()
        mock_client1.stop = AsyncMock()
        mock_client1.scrape = AsyncMock(return_value={})

        mock_client2 = AsyncMock()
        mock_client2.start = AsyncMock()
        mock_client2.stop = AsyncMock()
        mock_client2.scrape = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        client_instances = [mock_client1, mock_client2]
        call_count = [0]

        def create_client():
            client = client_instances[call_count[0]]
            call_count[0] += 1
            return client

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            side_effect=create_client,
        ):
            result = await protocol.scrape_torrent(torrent_info)

            # Should succeed with second tracker
            assert result["seeders"] == 100
            assert result["leechers"] == 50
            assert result["completed"] == 1000

    @pytest.mark.asyncio
    async def test_scrape_torrent_generic_exception(self, protocol, torrent_info):
        """Test scrape handles generic exceptions."""
        # Cause exception in _torrent_info_to_dict or _get_tracker_urls
        with patch.object(
            protocol, "_torrent_info_to_dict", side_effect=Exception("Parse error")
        ), patch("ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock) as mock_emit:
            result = await protocol.scrape_torrent(torrent_info)

            # Should return zeros on exception
            assert result["seeders"] == 0
            assert result["leechers"] == 0
            assert result["completed"] == 0

            # Should emit error event
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == "protocol_error"
            assert call_args.data["protocol_type"] == "bittorrent"


class TestTorrentInfoToDict:
    """Test _torrent_info_to_dict helper method."""

    def test_torrent_info_to_dict_single_file(self, protocol, torrent_info):
        """Test conversion of single-file torrent."""
        result = protocol._torrent_info_to_dict(torrent_info)

        assert result["name"] == "test_torrent"
        assert result["info_hash"] == b"x" * 20
        assert result["announce"] == "http://tracker.example.com/announce"
        assert "file_info" in result
        assert result["file_info"]["type"] == "single"
        assert result["file_info"]["total_length"] == 1024

    def test_torrent_info_to_dict_multi_file(self, protocol):
        """Test conversion of multi-file torrent."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"x" * 20,
            announce="http://tracker.example.com/announce",
            announce_list=[["http://tracker.example.com/announce"]],
            files=[
                FileInfo(name="file1.txt", length=512, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=512, path=["file2.txt"]),
            ],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=1,
        )

        result = protocol._torrent_info_to_dict(torrent_info)

        assert result["file_info"]["type"] == "multi"
        assert len(result["file_info"]["files"]) == 2

    def test_torrent_info_to_dict_with_announce_list(self, protocol):
        """Test conversion with multiple announce tiers."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"x" * 20,
            announce="http://tracker1.example.com/announce",
            announce_list=[
                ["http://tracker1.example.com/announce"],
                ["http://tracker2.example.com/announce"],
            ],
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )

        result = protocol._torrent_info_to_dict(torrent_info)

        assert "announce_list" in result
        assert len(result["announce_list"]) >= 2


class TestGetTrackerUrls:
    """Test _get_tracker_urls helper method."""

    def test_get_tracker_urls_from_announce(self, protocol, torrent_info):
        """Test getting tracker URLs from announce field."""
        result = protocol._get_tracker_urls(torrent_info)

        assert "http://tracker.example.com/announce" in result
        assert len(result) >= 1

    def test_get_tracker_urls_from_announce_list(self, protocol):
        """Test getting tracker URLs from announce_list."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"x" * 20,
            announce="",
            announce_list=[
                ["http://tracker1.example.com/announce"],
                ["http://tracker2.example.com/announce", "udp://tracker3.example.com:6969"],
            ],
            files=[],
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )

        result = protocol._get_tracker_urls(torrent_info)

        assert "http://tracker1.example.com/announce" in result
        assert "http://tracker2.example.com/announce" in result
        assert "udp://tracker3.example.com:6969" in result
        assert len(result) == 3

