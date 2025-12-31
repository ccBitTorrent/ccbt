"""Unit tests for MagnetHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.magnet_handling import MagnetHandler


class TestMagnetHandler:
    """Test MagnetHandler functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = Mock()
        session.magnet_info = None
        session.file_selection_manager = None
        session.torrent_data = {}
        session.config = Mock()
        session.config.discovery = Mock()
        session.config.discovery.magnet_respect_indices = True
        session.logger = Mock()
        return session

    @pytest.fixture
    def handler(self, mock_session):
        """Create MagnetHandler instance."""
        return MagnetHandler(mock_session)

    @pytest.mark.asyncio
    async def test_apply_file_selection_no_magnet_info(self, handler, mock_session):
        """Test apply_file_selection when no magnet_info."""
        mock_session.magnet_info = None

        await handler.apply_file_selection()

        # Should return early without error

    @pytest.mark.asyncio
    async def test_apply_file_selection_no_file_selection_manager(self, handler, mock_session):
        """Test apply_file_selection when file_selection_manager doesn't exist."""
        from ccbt.core.magnet import MagnetInfo

        mock_session.magnet_info = MagnetInfo(
            info_hash=b"x" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
        )
        mock_session.ensure_file_selection_manager = AsyncMock(return_value=False)

        await handler.apply_file_selection()

        mock_session.ensure_file_selection_manager.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_file_selection_single_file(self, handler, mock_session):
        """Test apply_file_selection with single-file torrent."""
        from ccbt.core.magnet import MagnetInfo
        from ccbt.models import FileInfo, TorrentInfo

        mock_session.magnet_info = MagnetInfo(
            info_hash=b"x" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
        )
        mock_session.ensure_file_selection_manager = AsyncMock(return_value=True)

        # Mock get_torrent_info to return single-file torrent
        with patch("ccbt.session.magnet_handling.get_torrent_info") as mock_get_info:
            mock_get_info.return_value = TorrentInfo(
                name="test",
                info_hash=b"x" * 20,
                announce="http://tracker.example.com/announce",
                files=[
                    FileInfo(
                        name="test.txt",
                        length=1000,
                        path=["test.txt"],
                    )
                ],
                total_length=1000,
                piece_length=16384,
                num_pieces=1,
            )

            await handler.apply_file_selection()

            # Should return early for single-file torrent

    @pytest.mark.asyncio
    async def test_apply_file_selection_multi_file(self, handler, mock_session):
        """Test apply_file_selection with multi-file torrent."""
        from ccbt.core.magnet import MagnetInfo
        from ccbt.models import FileInfo, TorrentInfo

        mock_session.magnet_info = MagnetInfo(
            info_hash=b"x" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2],
        )
        mock_session.ensure_file_selection_manager = AsyncMock(return_value=True)
        mock_session.file_selection_manager = Mock()

        # Mock get_torrent_info to return multi-file torrent
        with patch("ccbt.session.magnet_handling.get_torrent_info") as mock_get_info, patch(
            "ccbt.core.magnet.apply_magnet_file_selection", new_callable=AsyncMock
        ) as mock_apply:
            mock_get_info.return_value = TorrentInfo(
                name="test",
                info_hash=b"x" * 20,
                announce="http://tracker.example.com/announce",
                files=[
                    FileInfo(
                        name="file1.txt",
                        length=1000,
                        path=["file1.txt"],
                    ),
                    FileInfo(
                        name="file2.txt",
                        length=1000,
                        path=["file2.txt"],
                    ),
                    FileInfo(
                        name="file3.txt",
                        length=1000,
                        path=["file3.txt"],
                    ),
                ],
                total_length=3000,
                piece_length=16384,
                num_pieces=1,
            )

            await handler.apply_file_selection()

            mock_apply.assert_called_once()

