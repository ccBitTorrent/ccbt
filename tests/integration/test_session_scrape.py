"""Integration tests for session scrape functionality.

Tests AsyncSessionManager.force_scrape() integration with protocol and tracker clients.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.session]


@pytest_asyncio.fixture
async def session_manager():
    """Create AsyncSessionManager instance for testing."""
    from ccbt.session.session import AsyncSessionManager

    with patch("ccbt.session.session.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        session = AsyncSessionManager()
        await session.start()
        yield session
        await session.stop()


@pytest.fixture
def mock_torrent_session():
    """Create mock torrent session."""
    mock_session = MagicMock()
    mock_session.torrent_data = {
        "name": "test_torrent",
        "info_hash": b"x" * 20,
        "announce": "http://tracker.example.com/announce",
        "announce_list": [["http://tracker.example.com/announce"]],
        "total_length": 1024,
        "file_info": {"piece_length": 16384},
    }
    return mock_session


class TestForceScrape:
    """Test force_scrape method."""

    @pytest.mark.asyncio
    async def test_force_scrape_success(
        self, session_manager, mock_torrent_session
    ):
        """Test successful force scrape."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 50, "leechers": 25, "completed": 500}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is True
            mock_protocol.scrape_torrent.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_zero_stats(
        self, session_manager, mock_torrent_session
    ):
        """Test force scrape with zero stats."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        # Mock protocol scrape returning zeros
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 0, "leechers": 0, "completed": 0}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is False  # Zero stats = not successful
            mock_protocol.scrape_torrent.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_invalid_info_hash_length(
        self, session_manager
    ):
        """Test force scrape with invalid info_hash length."""
        result = await session_manager.force_scrape("short_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_invalid_info_hash_format(
        self, session_manager
    ):
        """Test force scrape with invalid info_hash format."""
        result = await session_manager.force_scrape("X" * 40)  # Invalid hex

        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_torrent_not_found(self, session_manager):
        """Test force scrape when torrent not found."""
        info_hash_hex = "x" * 40

        result = await session_manager.force_scrape(info_hash_hex)

        assert result is False

        # Clean up if any
        async with session_manager.lock:
            session_manager.torrents.clear()

    @pytest.mark.asyncio
    async def test_force_scrape_with_torrent_info_model(
        self, session_manager, mock_torrent_session
    ):
        """Test force scrape with TorrentInfo model as torrent_data."""
        from ccbt.models import TorrentInfo

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Set torrent_data to TorrentInfo model
        mock_torrent_session.torrent_data = TorrentInfo(
            name="test_torrent",
            info_hash=info_hash,
            announce="http://tracker.example.com/announce",
            announce_list=[["http://tracker.example.com/announce"]],
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
        )

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is True
            mock_protocol.scrape_torrent.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_unsupported_torrent_data_type(
        self, session_manager, mock_torrent_session
    ):
        """Test force scrape with unsupported torrent_data type."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Set unsupported type
        mock_torrent_session.torrent_data = "unsupported_type"

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        result = await session_manager.force_scrape(info_hash_hex)

        assert result is False

        # Clean up if any
        async with session_manager.lock:
            session_manager.torrents.clear()

    @pytest.mark.asyncio
    async def test_force_scrape_protocol_exception(
        self, session_manager, mock_torrent_session
    ):
        """Test force scrape when protocol raises exception."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        # Mock protocol scrape raising exception
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            side_effect=Exception("Protocol error")
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is False

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_conversion_exception(
        self, session_manager, mock_torrent_session
    ):
        """Test force scrape when torrent_data conversion fails."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Set invalid torrent_data that will cause conversion error
        mock_torrent_session.torrent_data = {"invalid": "data", "info_hash": None}

        # Add torrent session
        async with session_manager.lock:
            session_manager.torrents[info_hash] = mock_torrent_session

        result = await session_manager.force_scrape(info_hash_hex)

        # Should handle exception gracefully
        assert result is False

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

