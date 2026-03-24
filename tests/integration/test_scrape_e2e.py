"""End-to-end integration tests for tracker scraping (BEP 48).

Tests the full flow: Session -> Protocol -> Tracker Clients (HTTP/UDP) -> Response parsing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.tracker]


@pytest_asyncio.fixture
async def session_manager():
    """Create AsyncSessionManager instance for testing."""
    from ccbt.session.session import AsyncSessionManager

    with patch("ccbt.session.session.get_config") as mock_get_config:
        mock_config = MagicMock()
        # Set rate limits to integers (not MagicMock) to avoid comparison errors
        mock_config.limits = MagicMock()
        mock_config.limits.global_down_kib = 0
        mock_config.limits.global_up_kib = 0
        mock_config.discovery = MagicMock()
        mock_config.discovery.tracker_auto_scrape = False
        mock_config.discovery.enable_dht = False
        mock_config.nat = MagicMock()
        mock_config.nat.auto_map_ports = False
        mock_config.security = MagicMock()
        mock_config.security.ip_filter = MagicMock()
        mock_config.security.ip_filter.filter_update_interval = 3600.0
        mock_config.queue = MagicMock()
        mock_config.queue.auto_manage_queue = False
        mock_config.disk = MagicMock()
        mock_config.disk.checkpoint_interval = 30.0
        mock_config.disk.resume_save_interval = 30.0
        mock_config.disk.fast_resume_enabled = False
        from ccbt.models import CheckpointFormat
        mock_config.disk.checkpoint_format = CheckpointFormat.BINARY
        mock_config.disk.checkpoint_enabled = True
        mock_config.network = MagicMock()
        mock_config.network.max_global_peers = 100
        mock_config.network.connection_timeout = 30.0
        mock_get_config.return_value = mock_config

        session = AsyncSessionManager()
        await session.start()
        yield session
        await session.stop()


@pytest.fixture
def torrent_data_dict():
    """Create sample torrent data dictionary."""
    from tests.conftest import create_test_torrent_dict

    return create_test_torrent_dict(
        name="test_torrent",
        info_hash=b"x" * 20,
        announce="http://tracker.example.com/announce",
        file_length=1024,
        piece_length=16384,
        num_pieces=1,
    )


class TestEndToEndScrapeHTTP:
    """Test end-to-end scrape flow with HTTP tracker."""

    @pytest.mark.asyncio
    async def test_e2e_scrape_http_success(
        self, session_manager, torrent_data_dict
    ):
        """Test complete scrape flow: session -> protocol -> HTTP tracker."""
        from ccbt.session.session import AsyncTorrentSession

        info_hash = torrent_data_dict["info_hash"]
        info_hash_hex = info_hash.hex()

        # Create real torrent session
        torrent_session = AsyncTorrentSession(
            torrent_data_dict, output_dir=".", session_manager=session_manager
        )

        # Add to session manager
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock HTTP tracker client to return successful scrape
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_http_client
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is True
            mock_http_client.start.assert_called()
            mock_http_client.stop.assert_called()
            mock_http_client.scrape.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_e2e_scrape_udp_success(
        self, session_manager, torrent_data_dict
    ):
        """Test complete scrape flow: session -> protocol -> UDP tracker."""
        from ccbt.session.session import AsyncTorrentSession

        # Update torrent data for UDP tracker
        torrent_data_dict["announce"] = "udp://tracker.example.com:6969"
        torrent_data_dict["announce_list"] = [["udp://tracker.example.com:6969"]]

        info_hash = torrent_data_dict["info_hash"]
        info_hash_hex = info_hash.hex()

        # Create real torrent session
        torrent_session = AsyncTorrentSession(
            torrent_data_dict, output_dir=".", session_manager=session_manager
        )

        # Add to session manager
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

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
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is True
            mock_udp_client.start.assert_called()
            mock_udp_client.stop.assert_called()
            mock_udp_client.scrape.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_e2e_scrape_multiple_trackers(
        self, session_manager, torrent_data_dict
    ):
        """Test scrape tries multiple trackers when first fails."""
        from ccbt.session.session import AsyncTorrentSession

        # Set up multiple trackers
        torrent_data_dict["announce"] = "http://tracker1.example.com/announce"
        torrent_data_dict["announce_list"] = [
            ["http://tracker1.example.com/announce"],
            ["http://tracker2.example.com/announce"],
            ["udp://tracker3.example.com:6969"],
        ]

        info_hash = torrent_data_dict["info_hash"]
        info_hash_hex = info_hash.hex()

        # Create real torrent session
        torrent_session = AsyncTorrentSession(
            torrent_data_dict, output_dir=".", session_manager=session_manager
        )

        # Add to session manager
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock trackers: first two fail, third succeeds
        client_instances = []
        call_order = []

        def create_http_client():
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            mock_client.stop = AsyncMock()
            if len(call_order) < 2:
                mock_client.scrape = AsyncMock(return_value={})  # Empty result
                call_order.append("http_fail")
            else:
                mock_client.scrape = AsyncMock(
                    return_value={"seeders": 200, "leechers": 100, "completed": 2000}
                )
                call_order.append("http_success")
            client_instances.append(mock_client)
            return mock_client

        def create_udp_client():
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            mock_client.stop = AsyncMock()
            mock_client.scrape = AsyncMock(
                return_value={"seeders": 150, "leechers": 75, "completed": 1500}
            )
            call_order.append("udp_success")
            client_instances.append(mock_client)
            return mock_client

        http_patcher = patch(
            "ccbt.discovery.tracker.AsyncTrackerClient", side_effect=create_http_client
        )
        udp_patcher = patch(
            "ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient",
            side_effect=create_udp_client,
        )

        with http_patcher, udp_patcher:
            result = await session_manager.force_scrape(info_hash_hex)

            # Should succeed with one of the trackers
            assert result is True
            # At least one client should have been called
            assert len(call_order) > 0

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_e2e_scrape_all_trackers_fail(
        self, session_manager, torrent_data_dict
    ):
        """Test scrape when all trackers fail."""
        from ccbt.session.session import AsyncTorrentSession

        info_hash = torrent_data_dict["info_hash"]
        info_hash_hex = info_hash.hex()

        # Create real torrent session
        torrent_session = AsyncTorrentSession(
            torrent_data_dict, output_dir=".", session_manager=session_manager
        )

        # Add to session manager
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock HTTP tracker to always fail
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(return_value={})  # Empty result

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_http_client
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            # Should fail (zero stats)
            assert result is False

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_e2e_scrape_with_torrent_info_model(
        self, session_manager
    ):
        """Test scrape flow with TorrentInfo model."""
        from ccbt.models import FileInfo, TorrentInfo
        from ccbt.session.session import AsyncTorrentSession

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Create TorrentInfo model
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=info_hash,
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

        # Create torrent session with TorrentInfo
        torrent_session = AsyncTorrentSession(
            torrent_info, output_dir=".", session_manager=session_manager
        )

        # Add to session manager
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock HTTP tracker
        mock_http_client = AsyncMock()
        mock_http_client.start = AsyncMock()
        mock_http_client.stop = AsyncMock()
        mock_http_client.scrape = AsyncMock(
            return_value={"seeders": 50, "leechers": 25, "completed": 500}
        )

        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_http_client
        ):
            result = await session_manager.force_scrape(info_hash_hex)

            assert result is True
            mock_http_client.scrape.assert_called_once()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

