"""Unit tests for TorrentAdditionHandler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.torrent_addition import TorrentAdditionHandler


class TestTorrentAdditionHandler:
    """Test TorrentAdditionHandler functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock session manager."""
        manager = Mock()
        manager.queue_manager = None
        manager.logger = Mock()
        manager.config = Mock()
        manager.config.queue = Mock()
        manager.config.queue.default_priority = 0
        return manager

    @pytest.fixture
    def handler(self, mock_manager):
        """Create TorrentAdditionHandler instance."""
        return TorrentAdditionHandler(mock_manager)

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = Mock()
        session.info = Mock()
        session.info.name = "test_torrent"
        session.start = AsyncMock()
        session.get_status = AsyncMock(return_value={"status": "stopped"})
        return session

    @pytest.mark.asyncio
    async def test_add_torrent_background_without_queue(self, handler, mock_manager, mock_session):
        """Test adding torrent without queue manager."""
        info_hash = b"x" * 20

        await handler.add_torrent_background(mock_session, info_hash, resume=False)

        mock_session.start.assert_called_once_with(resume=False)

    @pytest.mark.asyncio
    async def test_add_torrent_background_with_queue(self, handler, mock_manager, mock_session):
        """Test adding torrent with queue manager."""
        info_hash = b"y" * 20

        # Mock queue manager
        queue_manager = Mock()
        queue_manager.add_torrent = AsyncMock()
        mock_manager.queue_manager = queue_manager

        # Mock session status to indicate queue started it
        mock_session.get_status = AsyncMock(return_value={"status": "downloading"})

        await handler.add_torrent_background(mock_session, info_hash, resume=False)

        queue_manager.add_torrent.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_torrent_background_handles_exceptions(self, handler, mock_manager, mock_session):
        """Test add_torrent_background handles exceptions."""
        info_hash = b"z" * 20

        mock_session.start = AsyncMock(side_effect=Exception("Error"))
        mock_manager.logger.exception = Mock()

        await handler.add_torrent_background(mock_session, info_hash, resume=False)

        mock_manager.logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_add_torrent_background_with_resume(self, handler, mock_manager, mock_session):
        """Test adding torrent with resume=True."""
        info_hash = b"resume" * 3

        await handler.add_torrent_background(mock_session, info_hash, resume=True)

        mock_session.start.assert_called_once_with(resume=True)

