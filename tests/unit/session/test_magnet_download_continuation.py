"""Tests for magnet link download continuation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session, pytest.mark.integration]

from ccbt.models import PeerInfo, TrackerResponse
from ccbt.session.session import AsyncSessionManager
from ccbt.session.download_manager import download_magnet


class TestMagnetDownloadContinuation:
    """Test cases for magnet link download continuation."""

    @pytest.fixture
    def session_manager(self):
        """Create AsyncSessionManager instance."""
        return AsyncSessionManager()

    @pytest.mark.asyncio
    async def test_add_magnet_with_metadata_starts_download(self, session_manager):
        """Test that add_magnet starts download after metadata fetch."""
        magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test&tr=http://tracker.example.com/announce"

        # Mock metadata fetch
        mock_metadata = {
            b"info": {
                b"name": b"test",
                b"piece length": 16384,
                b"pieces": b"piece_hash_data",
                b"length": 1024,
            }
        }

        # Mock tracker responses
        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        mock_tracker_response = TrackerResponse(
            interval=1800,
            peers=[peer],
            complete=10,
            incomplete=5,
        )

        with patch("ccbt.core.magnet.parse_magnet") as mock_parse:
            from ccbt.core.magnet import MagnetInfo

            mock_parse.return_value = MagnetInfo(
                info_hash=b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                display_name="test",
                trackers=["http://tracker.example.com/announce"],
                web_seeds=[],
            )

            with patch("ccbt.piece.async_metadata_exchange.fetch_metadata_from_peers", return_value=mock_metadata):
                with patch("ccbt.core.magnet.build_torrent_data_from_metadata") as mock_build:
                    mock_build.return_value = {
                        "info_hash": b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                        "name": "test",
                        "announce": "http://tracker.example.com/announce",
                        "pieces_info": {
                            "num_pieces": 1,
                            "piece_length": 16384,
                            "piece_hashes": [b"piece_hash"],
                        },
                        "file_info": {
                            "total_length": 1024,
                        },
                    }

                    with patch("ccbt.session.session.AsyncDownloadManager") as mock_dm_class:
                        mock_dm = AsyncMock()
                        mock_dm.start = AsyncMock()
                        mock_dm.start_download = AsyncMock()
                        mock_dm_class.return_value = mock_dm

                        # Mock _get_peers_from_trackers to return peers
                        mock_peers = [{"ip": "192.168.1.1", "port": 6881, "peer_source": "tracker"}]
                        with patch.object(session_manager, "_get_peers_from_trackers", return_value=mock_peers):
                            with patch("ccbt.session.session.get_config") as mock_get_config:
                                mock_config = MagicMock()
                                mock_config.network.listen_port = 6881
                                mock_get_config.return_value = mock_config

                                torrent_id = await session_manager.add_magnet(magnet_uri)

                                # Verify download manager was created and started
                                mock_dm_class.assert_called_once()
                                mock_dm.start.assert_called_once()

                                # Verify download was started
                                mock_dm.start_download.assert_called_once()
                                call_args = mock_dm.start_download.call_args[0][0]
                                assert len(call_args) == 1
                                assert call_args[0] == mock_peers[0]

                                assert torrent_id is not None

    @pytest.mark.asyncio
    async def test_add_magnet_no_metadata_warning(self, session_manager):
        """Test that add_magnet logs warning when metadata is not fetched."""
        magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test&tr=http://tracker.example.com/announce"

        with patch("ccbt.core.magnet.parse_magnet") as mock_parse:
            from ccbt.core.magnet import MagnetInfo

            mock_parse.return_value = MagnetInfo(
                info_hash=b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                display_name="test",
                trackers=["http://tracker.example.com/announce"],
                web_seeds=[],
            )

            with patch("ccbt.piece.async_metadata_exchange.fetch_metadata_from_peers", return_value=None):
                with patch("ccbt.core.magnet.build_minimal_torrent_data") as mock_build:
                    mock_build.return_value = {
                        "info_hash": b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                        "name": "test",
                    }

                    with patch("ccbt.session.session.AsyncDownloadManager") as mock_dm_class:
                        mock_dm = AsyncMock()
                        mock_dm.start = AsyncMock()
                        mock_dm_class.return_value = mock_dm

                        with patch("ccbt.session.session.get_config") as mock_get_config:
                            mock_config = MagicMock()
                            mock_config.network.listen_port = 6881
                            mock_get_config.return_value = mock_config

                            # Capture log output
                            import logging
                            with patch.object(session_manager.logger, "warning") as mock_warning:
                                torrent_id = await session_manager.add_magnet(magnet_uri)

                                # Verify warning was logged
                                assert mock_warning.called
                                warning_calls = [str(call) for call in mock_warning.call_args_list]
                                assert any("Cannot start download without metadata" in str(call) for call in warning_calls)

                                # Verify download was not started
                                assert not mock_dm.start_download.called

                                assert torrent_id is not None

    @pytest.mark.asyncio
    async def test_download_magnet_success(self):
        """Test successful magnet download."""
        magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test&tr=http://tracker.example.com/announce"

        # Mock metadata fetch
        mock_metadata = {
            b"info": {
                b"name": b"test",
                b"piece length": 16384,
                b"pieces": b"piece_hash_data",
                b"length": 1024,
            }
        }

        # Mock tracker responses
        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
        mock_tracker_response = TrackerResponse(
            interval=1800,
            peers=[peer],
            complete=10,
            incomplete=5,
        )

        with patch("ccbt.core.magnet.parse_magnet") as mock_parse:
            from ccbt.core.magnet import MagnetInfo

            mock_parse.return_value = MagnetInfo(
                info_hash=b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                display_name="test",
                trackers=["http://tracker.example.com/announce"],
                web_seeds=[],
            )

            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            mock_client.stop = AsyncMock()
            mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
            mock_client.announce = AsyncMock(return_value=mock_tracker_response)
            mock_client.announce_to_multiple = AsyncMock(return_value=[mock_tracker_response])

            with patch("ccbt.piece.async_metadata_exchange.fetch_metadata_from_peers", return_value=mock_metadata):
                with patch("ccbt.core.magnet.build_torrent_data_from_metadata") as mock_build:
                    mock_build.return_value = {
                        "info_hash": b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                        "name": "test",
                        "announce": "http://tracker.example.com/announce",
                        "pieces_info": {
                            "num_pieces": 1,
                            "piece_length": 16384,
                            "piece_hashes": [b"piece_hash"],
                        },
                        "file_info": {
                            "total_length": 1024,
                        },
                    }

                    with patch("ccbt.session.session.AsyncDownloadManager") as mock_dm_class:
                        mock_dm = AsyncMock()
                        mock_dm.start = AsyncMock()
                        mock_dm.start_download = AsyncMock()
                        mock_dm.stop = AsyncMock()
                        mock_dm_class.return_value = mock_dm

                        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
                            with patch("ccbt.session.session.get_config") as mock_get_config:
                                mock_config = MagicMock()
                                mock_config.network.listen_port = 6881
                                mock_get_config.return_value = mock_config

                                await download_magnet(magnet_uri)

                                # Verify metadata fetch was called
                                # Verify download manager was created and started
                                mock_dm_class.assert_called_once()
                                mock_dm.start.assert_called_once()

                                # Verify tracker announce was called
                                assert mock_client.start.call_count >= 1
                                mock_client.announce_to_multiple.assert_called_once()

                                # Verify download was started
                                mock_dm.start_download.assert_called_once()

                                # Verify cleanup
                                mock_dm.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_magnet_no_metadata(self):
        """Test magnet download when metadata fetch fails."""
        magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test&tr=http://tracker.example.com/announce"

        with patch("ccbt.core.magnet.parse_magnet") as mock_parse:
            from ccbt.core.magnet import MagnetInfo

            mock_parse.return_value = MagnetInfo(
                info_hash=b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                display_name="test",
                trackers=["http://tracker.example.com/announce"],
                web_seeds=[],
            )

            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            mock_client.stop = AsyncMock()
            mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
            mock_client.announce = AsyncMock(return_value=TrackerResponse(
                interval=1800,
                peers=[],
                complete=10,
                incomplete=5,
            ))

            with patch("ccbt.piece.async_metadata_exchange.fetch_metadata_from_peers", return_value=None):
                with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
                    with patch("ccbt.session.session.get_config") as mock_get_config:
                        mock_config = MagicMock()
                        mock_config.network.listen_port = 6881
                        mock_get_config.return_value = mock_config

                        with patch("ccbt.session.download_manager.logging") as mock_logging:
                            # Should not raise exception
                            await download_magnet(magnet_uri)

                            # Verify warning was logged
                            mock_logger = mock_logging.getLogger.return_value
                            assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_download_magnet_tracker_failure(self):
        """Test magnet download when tracker announce fails."""
        magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test&tr=http://tracker.example.com/announce"

        # Mock metadata fetch
        mock_metadata = {
            b"info": {
                b"name": b"test",
                b"piece length": 16384,
                b"pieces": b"piece_hash_data",
                b"length": 1024,
            }
        }

        with patch("ccbt.core.magnet.parse_magnet") as mock_parse:
            from ccbt.core.magnet import MagnetInfo

            mock_parse.return_value = MagnetInfo(
                info_hash=b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                display_name="test",
                trackers=["http://tracker.example.com/announce"],
                web_seeds=[],
            )

            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            mock_client.stop = AsyncMock()
            mock_client._generate_peer_id = MagicMock(return_value=b"-CC0101-" + b"x" * 12)
            # Mock announce_to_multiple to return empty list (simulating failure)
            mock_client.announce_to_multiple = AsyncMock(return_value=[])

            with patch("ccbt.piece.async_metadata_exchange.fetch_metadata_from_peers", return_value=mock_metadata):
                with patch("ccbt.core.magnet.build_torrent_data_from_metadata") as mock_build:
                    mock_build.return_value = {
                        "info_hash": b"\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67\x89\xab\xcd\xef\x01\x23\x45\x67",
                        "name": "test",
                        "announce": "http://tracker.example.com/announce",
                        "pieces_info": {
                            "num_pieces": 1,
                            "piece_length": 16384,
                            "piece_hashes": [b"piece_hash"],
                        },
                        "file_info": {
                            "total_length": 1024,
                        },
                    }

                    with patch("ccbt.session.session.AsyncDownloadManager") as mock_dm_class:
                        mock_dm = AsyncMock()
                        mock_dm.start = AsyncMock()
                        mock_dm.stop = AsyncMock()
                        mock_dm_class.return_value = mock_dm

                        with patch("ccbt.discovery.tracker.AsyncTrackerClient", return_value=mock_client):
                            with patch("ccbt.session.session.get_config") as mock_get_config:
                                mock_config = MagicMock()
                                mock_config.network.listen_port = 6881
                                mock_get_config.return_value = mock_config

                                # Should not raise exception
                                await download_magnet(magnet_uri)

                                # Download should not be started without peers
                                assert not mock_dm.start_download.called

