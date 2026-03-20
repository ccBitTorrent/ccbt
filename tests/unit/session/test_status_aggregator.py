"""Unit tests for StatusAggregator."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.models import SessionContext
from ccbt.session.status_aggregation import StatusAggregator


class TestStatusAggregator:
    """Test StatusAggregator functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = Mock()
        session.info = Mock()
        session.info.info_hash = b"x" * 20
        session.info.name = "test_torrent"
        session.info.status = "downloading"
        session.info.added_time = 1000.0
        session.download_manager = Mock()
        session.logger = Mock()
        session._last_error = None
        session._tracker_connection_status = None
        session._last_tracker_error = None
        return session

    @pytest.fixture
    def aggregator(self, mock_session):
        """Create StatusAggregator instance."""
        return StatusAggregator(mock_session)

    @pytest.mark.asyncio
    async def test_get_torrent_status_with_download_manager(self, aggregator, mock_session):
        """Test getting status when download manager is available."""
        # Mock download manager get_status
        mock_status = {
            "downloaded": 1000,
            "uploaded": 500,
            "left": 9000,
            "peers": 5,
            "download_rate": 100.0,
            "upload_rate": 50.0,
            "progress": 0.1,
        }
        mock_session.download_manager.get_status = AsyncMock(return_value=mock_status)
        mock_session.output_dir = "."
        mock_session.is_private = False

        status = await aggregator.get_torrent_status()

        assert status["info_hash"] == (b"x" * 20).hex()
        assert status["name"] == "test_torrent"
        assert status["status"] == "downloading"
        assert status["downloaded"] == 1000
        assert status["uploaded"] == 500
        assert status["left"] == 9000
        # Canonical key is connected_peers (peers normalized in aggregator)
        assert status["connected_peers"] == 5
        assert "uptime" in status
        assert status["last_error"] is None

    @pytest.mark.asyncio
    async def test_get_torrent_status_without_download_manager(self, aggregator, mock_session):
        """Test getting status when download manager is not available."""
        mock_session.download_manager = None
        mock_session.output_dir = "."
        mock_session.is_private = False

        status = await aggregator.get_torrent_status()

        assert status["info_hash"] == (b"x" * 20).hex()
        assert status["name"] == "test_torrent"
        assert status["status"] == "downloading"
        assert status["download_rate"] == 0.0
        assert status["upload_rate"] == 0.0
        assert status["progress"] == 0.0

    @pytest.mark.asyncio
    async def test_get_torrent_status_with_error(self, aggregator, mock_session):
        """Test getting status when get_status raises an error."""
        mock_session.download_manager.get_status = AsyncMock(side_effect=Exception("Error"))
        mock_session.logger.warning = Mock()
        mock_session.output_dir = "."
        mock_session.is_private = False

        status = await aggregator.get_torrent_status()

        # Should return minimal status on error (normalized)
        assert status["info_hash"] == (b"x" * 20).hex()
        assert status["name"] == "test_torrent"
        mock_session.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_get_torrent_status_with_sync_get_status(self, aggregator, mock_session):
        """Test getting status when get_status is synchronous."""
        mock_status = {"downloaded": 2000, "uploaded": 1000}
        mock_session.download_manager.get_status = Mock(return_value=mock_status)
        mock_session.output_dir = "."
        mock_session.is_private = False

        status = await aggregator.get_torrent_status()

        assert status["downloaded"] == 2000
        assert status["uploaded"] == 1000

    @pytest.mark.asyncio
    async def test_get_torrent_status_with_last_error(self, aggregator, mock_session):
        """Test getting status includes last_error."""
        mock_session._last_error = "Connection failed"
        mock_session.download_manager.get_status = AsyncMock(return_value={})
        mock_session.output_dir = "."
        mock_session.is_private = False

        status = await aggregator.get_torrent_status()

        assert status["last_error"] == "Connection failed"

    @pytest.mark.asyncio
    async def test_get_torrent_status_with_tracker_status(self, aggregator, mock_session):
        """Test getting status includes tracker_status."""
        mock_session._tracker_connection_status = "connected"
        mock_session.download_manager.get_status = AsyncMock(return_value={})
        mock_session.output_dir = "."
        mock_session.is_private = False
        mock_session.torrent_file_path = "/tmp/test.torrent"
        mock_session.magnet_uri = "magnet:?xt=urn:btih:test"

        status = await aggregator.get_torrent_status()

        assert status["tracker_status"] == "connected"
        assert status["torrent_file_path"] == "/tmp/test.torrent"
        assert status["magnet_uri"] == "magnet:?xt=urn:btih:test"

