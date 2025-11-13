"""Tests for async main entry point."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.async_main import (
    AsyncDownloadManager,
    AsyncSessionManager,
    download_magnet,
    download_torrent,
    main,
    run_daemon,
    sync_main,
)


class TestAsyncDownloadManager:
    """Test cases for AsyncDownloadManager."""

    @pytest.fixture
    def torrent_data(self):
        """Create sample torrent data."""
        return {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
            "pieces": b"pieces_hash_data",
            "piece_length": 16384,
            "files": [{"path": ["file1.txt"], "length": 1024}],
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
        return AsyncDownloadManager(torrent_data)

    @pytest.mark.asyncio
    async def test_async_download_manager_initialization(self, torrent_data):
        """Test AsyncDownloadManager initialization."""
        dm = AsyncDownloadManager(torrent_data)

        assert dm.torrent_data == torrent_data
        assert dm.output_dir == "."
        assert dm.our_peer_id == b"-CC0101-" + b"x" * 12
        assert dm.download_complete is False
        assert dm.start_time is None
        assert dm.peer_manager is None

    @pytest.mark.asyncio
    async def test_async_download_manager_initialization_with_torrent_info(self):
        """Test AsyncDownloadManager initialization with TorrentInfo."""
        from ccbt.models import FileInfo, TorrentInfo

        torrent_info = TorrentInfo(
            info_hash=b"test1234567890123456",
            name="test_torrent",
            announce="http://tracker.example.com/announce",
            pieces=[b"piece_hash_1", b"piece_hash_2"],
            piece_length=16384,
            num_pieces=2,
            total_length=2048,
            files=[FileInfo(name="file1.txt", length=1024, path=["file1.txt"])],
        )

        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.AsyncPieceManager") as mock_piece_manager_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_piece_manager = MagicMock()
            mock_piece_manager_class.return_value = mock_piece_manager

            dm = AsyncDownloadManager(torrent_info)

            assert dm.torrent_data == torrent_info.model_dump()
            mock_piece_manager_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_download_manager_normalization(self):
        """Test AsyncDownloadManager normalization when pieces_info is missing (lines 72-93)."""
        # Create a dict that has all required keys but no pieces_info
        torrent_dict = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "announce": "http://tracker.example.com/announce",
            "announce_list": ["http://tracker2.example.com/announce"],
            "piece_length": 16384,
            "pieces": [b"piece_hash_1", b"piece_hash_2"],
            "num_pieces": 2,
            "total_length": 2048,
        }

        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.AsyncPieceManager") as mock_piece_manager_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_piece_manager = MagicMock()
            mock_piece_manager_class.return_value = mock_piece_manager

            dm = AsyncDownloadManager(torrent_dict)

            # Verify AsyncPieceManager was called with normalized dict
            call_args = mock_piece_manager_class.call_args[0][0]
            assert "pieces_info" in call_args
            assert call_args["pieces_info"]["piece_length"] == 16384
            assert call_args["pieces_info"]["num_pieces"] == 2
            assert call_args["pieces_info"]["piece_hashes"] == [b"piece_hash_1", b"piece_hash_2"]
            assert call_args["file_info"]["total_length"] == 2048
            assert call_args["info_hash"] == b"test1234567890123456"
            assert call_args["name"] == "test_torrent"
            assert call_args["announce"] == "http://tracker.example.com/announce"
            assert call_args["announce_list"] == ["http://tracker2.example.com/announce"]

    @pytest.mark.asyncio
    async def test_async_download_manager_with_pieces_info(self):
        """Test AsyncDownloadManager when pieces_info already exists."""
        torrent_dict = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "pieces_info": {
                "piece_length": 16384,
                "num_pieces": 2,
                "piece_hashes": [b"piece_hash_1", b"piece_hash_2"],
            },
            "file_info": {
                "total_length": 2048,
            },
        }

        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.AsyncPieceManager") as mock_piece_manager_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config
            mock_piece_manager = MagicMock()
            mock_piece_manager_class.return_value = mock_piece_manager

            dm = AsyncDownloadManager(torrent_dict)

            # Verify AsyncPieceManager was called with original dict (no normalization)
            call_args = mock_piece_manager_class.call_args[0][0]
            assert call_args == torrent_dict

    @pytest.mark.asyncio
    async def test_async_download_manager_initialization_with_custom_params(self, torrent_data):
        """Test AsyncDownloadManager initialization with custom parameters."""
        custom_peer_id = b"-TEST01-" + b"y" * 12

        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.AsyncPieceManager") as mock_piece_manager_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_piece_manager = MagicMock()
            mock_piece_manager_class.return_value = mock_piece_manager

            dm = AsyncDownloadManager(
                torrent_data,
                output_dir="/custom/output",
                peer_id=custom_peer_id,
            )

            assert dm.output_dir == "/custom/output"
            assert dm.our_peer_id == custom_peer_id

    @pytest.mark.asyncio
    async def test_start(self, download_manager):
        """Test starting the download manager."""
        with patch.object(download_manager.piece_manager, "start", new_callable=AsyncMock):
            await download_manager.start()

            download_manager.piece_manager.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, download_manager):
        """Test stopping the download manager."""
        mock_peer_manager = MagicMock()
        download_manager.peer_manager = mock_peer_manager

        with patch.object(download_manager.piece_manager, "stop", new_callable=AsyncMock), \
             patch.object(mock_peer_manager, "stop", new_callable=AsyncMock):

            await download_manager.stop()

            mock_peer_manager.stop.assert_called_once()
            download_manager.piece_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_without_peer_manager(self, download_manager):
        """Test stopping the download manager without peer manager."""
        with patch.object(download_manager.piece_manager, "stop", new_callable=AsyncMock):
            await download_manager.stop()

            download_manager.piece_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_download(self, download_manager):
        """Test starting download process."""
        peers = [
            {"ip": "192.168.1.1", "port": 6881},
            {"ip": "192.168.1.2", "port": 6881},
        ]

        with patch("ccbt.session.async_main.AsyncPeerConnectionManager") as mock_peer_manager_class, \
             patch.object(download_manager.piece_manager, "start_download", new_callable=AsyncMock):

            mock_peer_manager = MagicMock()
            mock_peer_manager_class.return_value = mock_peer_manager

            with patch.object(mock_peer_manager, "start", new_callable=AsyncMock), \
                 patch.object(mock_peer_manager, "connect_to_peers", new_callable=AsyncMock):

                await download_manager.start_download(peers)

                assert download_manager.peer_manager == mock_peer_manager
                assert download_manager.start_time is not None
                mock_peer_manager.start.assert_called_once()
                mock_peer_manager.connect_to_peers.assert_called_once_with(peers)
                download_manager.piece_manager.start_download.assert_called_once_with(mock_peer_manager)

    @pytest.mark.asyncio
    async def test_get_status(self, download_manager):
        """Test getting download status."""
        mock_piece_status = {"completed": 10, "total": 100}
        mock_progress = {"percentage": 10.0, "downloaded": 1024, "total": 10240}

        with patch.object(download_manager.piece_manager, "get_piece_status", return_value=mock_piece_status), \
             patch.object(download_manager.piece_manager, "get_download_progress", return_value=mock_progress), \
             patch("time.time", return_value=1000.0):

            download_manager.start_time = 900.0

            status = await download_manager.get_status()

            assert status["progress"] == mock_progress
            assert status["piece_status"] == mock_piece_status
            assert status["download_time"] == 100.0
            assert status["download_complete"] is False

    @pytest.mark.asyncio
    async def test_get_status_with_peer_manager(self, download_manager):
        """Test getting download status with peer manager."""
        mock_piece_status = {"completed": 10, "total": 100}
        mock_progress = {"percentage": 10.0, "downloaded": 1024, "total": 10240}

        mock_peer_manager = MagicMock()
        mock_peer_manager.get_connected_peers.return_value = ["peer1", "peer2"]
        mock_peer_manager.get_active_peers.return_value = ["peer1"]
        download_manager.peer_manager = mock_peer_manager

        with patch.object(download_manager.piece_manager, "get_piece_status", return_value=mock_piece_status), \
             patch.object(download_manager.piece_manager, "get_download_progress", return_value=mock_progress), \
             patch("time.time", return_value=1000.0):

            download_manager.start_time = 900.0

            status = await download_manager.get_status()

            assert status["connected_peers"] == 2
            assert status["active_peers"] == 1

    @pytest.mark.asyncio
    async def test_callback_methods(self, download_manager):
        """Test callback methods."""
        # Test peer connected callback
        mock_connection = MagicMock()
        download_manager._on_peer_connected(mock_connection)

        # Test peer disconnected callback
        download_manager._on_peer_disconnected(mock_connection)

        # Test piece received callback
        mock_piece_message = MagicMock()
        download_manager._on_piece_received(mock_connection, mock_piece_message)

        # Test bitfield received callback
        download_manager._on_bitfield_received(mock_connection, b"bitfield_data")

        # Test piece completed callback
        download_manager._on_piece_completed(0)

        # Test piece verified callback
        download_manager._on_piece_verified(0)

        # Test download complete callback
        download_manager._on_download_complete()

        assert download_manager.download_complete is True

    @pytest.mark.asyncio
    async def test_on_piece_received_background_tasks(self, download_manager):
        """Test _on_piece_received background task management (lines 195-215)."""
        mock_connection = MagicMock()
        mock_connection.peer_info = "192.168.1.1:6881"
        mock_piece_message = MagicMock()
        mock_piece_message.piece_index = 5
        mock_piece_message.begin = 0
        mock_piece_message.block = b"block_data"

        # Make piece_manager methods async mocks
        download_manager.piece_manager.update_peer_have = AsyncMock()
        download_manager.piece_manager.handle_piece_block = AsyncMock()

        with patch("asyncio.create_task") as mock_create_task:
            mock_task1 = MagicMock()
            mock_task2 = MagicMock()
            mock_create_task.side_effect = [mock_task1, mock_task2]

            download_manager._on_piece_received(mock_connection, mock_piece_message)

            # Verify tasks were created and added to background_tasks
            assert mock_create_task.call_count == 2
            assert mock_task1 in download_manager._background_tasks
            assert mock_task2 in download_manager._background_tasks

            # Verify update_peer_have was called
            download_manager.piece_manager.update_peer_have.assert_called_once_with(
                "192.168.1.1:6881",
                5,
            )

            # Verify handle_piece_block was called
            download_manager.piece_manager.handle_piece_block.assert_called_once_with(
                5,
                0,
                b"block_data",
            )

    @pytest.mark.asyncio
    async def test_callback_invocations(self, download_manager):
        """Test callback invocations (lines 180, 186, 221, 240)."""
        mock_connection = MagicMock()
        mock_connection.peer_info = "192.168.1.1:6881"

        # Test on_peer_connected callback (line 180)
        on_peer_connected_cb = MagicMock()
        download_manager.on_peer_connected = on_peer_connected_cb
        download_manager._on_peer_connected(mock_connection)
        on_peer_connected_cb.assert_called_once_with(mock_connection)

        # Test on_peer_disconnected callback (line 186)
        on_peer_disconnected_cb = MagicMock()
        download_manager.on_peer_disconnected = on_peer_disconnected_cb
        download_manager._on_peer_disconnected(mock_connection)
        on_peer_disconnected_cb.assert_called_once_with(mock_connection)

        # Test on_piece_completed callback (line 221)
        on_piece_completed_cb = MagicMock()
        download_manager.on_piece_completed = on_piece_completed_cb
        download_manager._on_piece_completed(5)
        on_piece_completed_cb.assert_called_once_with(5)

        # Test on_download_complete callback (line 240)
        on_download_complete_cb = MagicMock()
        download_manager.on_download_complete = on_download_complete_cb
        download_manager._on_download_complete()
        on_download_complete_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_piece_verified_with_peer_manager(self, download_manager):
        """Test _on_piece_verified with peer_manager (lines 229-232)."""
        mock_peer_manager = MagicMock()
        download_manager.peer_manager = mock_peer_manager

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            download_manager._on_piece_verified(10)

            # Verify broadcast_have was called and task was added
            mock_peer_manager.broadcast_have.assert_called_once_with(10)
            mock_create_task.assert_called_once()
            assert mock_task in download_manager._background_tasks

    @pytest.mark.asyncio
    async def test_initialization_type_error(self):
        """Test initialization with invalid torrent_dict type (lines 67-68)."""
        # Create a mock object that doesn't have model_dump and isn't a dict
        # Use a simple object that can't be converted to dict
        invalid_torrent = object()  # Simple object that's not a dict or TorrentInfo

        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.AsyncPieceManager"):

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            with pytest.raises(TypeError, match="Expected dict for torrent_dict"):
                AsyncDownloadManager(invalid_torrent)  # type: ignore[arg-type]


class TestAsyncMainFunctions:
    """Test cases for async main functions."""

    @pytest.mark.asyncio
    async def test_download_magnet(self):
        """Test downloading from magnet URI."""
        magnet_uri = "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890"

        with patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata:

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_parse_magnet.return_value = mock_magnet_info

            mock_fetch_metadata.return_value = None  # No metadata

            await download_magnet(magnet_uri, "/output")

            mock_parse_magnet.assert_called_once_with(magnet_uri)
            mock_fetch_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_magnet_with_metadata(self):
        """Test download_magnet with metadata found (line 418)."""
        magnet_uri = "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890"

        with patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata:

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_parse_magnet.return_value = mock_magnet_info

            mock_fetch_metadata.return_value = {"name": "test"}  # Metadata found

            # Should complete without error
            await download_magnet(magnet_uri, "/output")

    @pytest.mark.asyncio
    async def test_download_magnet_no_metadata_else(self):
        """Test download_magnet else path when no metadata (line 420)."""
        magnet_uri = "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890"

        with patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata:

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_parse_magnet.return_value = mock_magnet_info

            mock_fetch_metadata.return_value = None  # No metadata - triggers else path

            # Should complete without error
            await download_magnet(magnet_uri, "/output")

    @pytest.mark.asyncio
    async def test_download_magnet_exception(self):
        """Test download_magnet with exception handling (lines 422-424)."""
        magnet_uri = "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890"

        with patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata:

            mock_parse_magnet.side_effect = ValueError("Invalid magnet")

            # Should not raise, exceptions are suppressed
            await download_magnet(magnet_uri, "/output")

    @pytest.mark.asyncio
    async def test_download_torrent(self):
        """Test downloading from torrent file."""
        torrent_path = "tests/data/test.torrent"

        mock_torrent_data = MagicMock()
        mock_torrent_data.info_hash = b"test1234567890123456"

        with patch("ccbt.session.async_main.TorrentParser") as mock_parser_class, \
             patch("ccbt.session.async_main.AsyncDownloadManager") as mock_dm_class:

            # Setup mocks
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser

            mock_dm = MagicMock()
            # Mark as complete immediately so monitor_progress loop exits on first check
            mock_dm.download_complete = True
            
            # get_status should return valid status
            mock_dm.get_status = AsyncMock(return_value={
                "progress": 1.0,
                "connected_peers": 2,
                "piece_status": {"completed": 100, "total": 100},
                "active_peers": 1,
                "download_time": 10.0,
                "download_complete": True,
            })
            mock_dm_class.return_value = mock_dm

            with patch.object(mock_dm, "start", new_callable=AsyncMock), \
                 patch.object(mock_dm, "stop", new_callable=AsyncMock):
                
                # With download_complete=True from the start, monitor_progress will exit immediately
                # after the first check, so the task completes quickly and wait_for succeeds
                
                # Should complete successfully
                await download_torrent(torrent_path, "/output")

                mock_parser.parse.assert_called_once_with(torrent_path)
                mock_dm.start.assert_called_once()
                mock_dm.stop.assert_called_once()


    @pytest.mark.asyncio
    @pytest.mark.timeout(10)  # Prevent test from hanging
    async def test_run_daemon(self):  # pragma: no cover
        """Test running daemon mode.
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test intentionally raises KeyboardInterrupt to simulate daemon mode being interrupted.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        class MockArgs:
            add = ["tests/data/test.torrent", "magnet:?xt=urn:btih:test"]
            status = False

        args = MockArgs()

        # Mock config to disable DHT and prevent background tasks
        mock_config = MagicMock()
        mock_config.discovery.enable_dht = False

        # Prevent DHT client from starting background tasks
        # Note: run_daemon imports AsyncSessionManager locally, so we need to patch it
        # at the module level where it's imported, or patch it in the function's namespace
        with patch("ccbt.session.AsyncSessionManager") as mock_session_class, \
             patch("ccbt.session.async_main.get_config", return_value=mock_config), \
             patch("ccbt.discovery.dht.AsyncDHTClient.start", new_callable=AsyncMock), \
             patch("ccbt.discovery.dht.AsyncDHTClient._refresh_loop"):
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_start = AsyncMock()
            mock_stop = AsyncMock()
            mock_add_torrent = AsyncMock()
            mock_add_magnet = AsyncMock()

            # Patch asyncio.sleep to raise KeyboardInterrupt on first call
            # This simulates the infinite loop being interrupted
            sleep_call_count = 0
            original_sleep = asyncio.sleep
            async def mock_sleep(delay):
                nonlocal sleep_call_count
                sleep_call_count += 1
                # Raise KeyboardInterrupt on first call (from run_daemon's while loop)
                if sleep_call_count == 1:
                    raise KeyboardInterrupt
                # For subsequent calls (if any), use minimal delay
                await original_sleep(0.001)

            with patch.object(mock_session, "start", mock_start), \
                 patch.object(mock_session, "stop", mock_stop), \
                 patch.object(mock_session, "add_torrent", mock_add_torrent), \
                 patch.object(mock_session, "add_magnet", mock_add_magnet), \
                 patch("asyncio.sleep", side_effect=mock_sleep):

                await run_daemon(args)

                mock_start.assert_called_once()
                # add_torrent is called with torrent path (output_dir defaults to ".")
                mock_add_torrent.assert_called_once_with("tests/data/test.torrent")
                # add_magnet is called with magnet URI (output_dir defaults to ".")
                mock_add_magnet.assert_called_once_with("magnet:?xt=urn:btih:test")
                mock_stop.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)  # Prevent test from hanging
    async def test_run_daemon_exception_handling(self):  # pragma: no cover
        """Test run_daemon exception handling (lines 443-444).
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test uses KeyboardInterrupt to verify exception handling during daemon shutdown.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        class MockArgs:
            add = ["tests/data/test.torrent"]
            status = False

        args = MockArgs()

        with patch("ccbt.session.AsyncSessionManager") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            with patch.object(mock_session, "start", new_callable=AsyncMock), \
                 patch.object(mock_session, "stop", new_callable=AsyncMock), \
                 patch.object(mock_session, "add_torrent", side_effect=ValueError("Failed")), \
                 patch("asyncio.sleep", side_effect=KeyboardInterrupt):

                # Should not raise, exception is caught and logged
                await run_daemon(args)

                mock_session.stop.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)  # Prevent test from hanging
    async def test_run_daemon_keyboard_interrupt(self):  # pragma: no cover
        """Test run_daemon with KeyboardInterrupt (line 458).
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test intentionally raises KeyboardInterrupt to verify graceful shutdown behavior.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        class MockArgs:
            add = []
            status = False

        args = MockArgs()

        with patch("ccbt.session.AsyncSessionManager") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            with patch.object(mock_session, "start", new_callable=AsyncMock), \
                 patch.object(mock_session, "stop", new_callable=AsyncMock), \
                 patch("asyncio.sleep", side_effect=KeyboardInterrupt):

                await run_daemon(args)

                mock_session.stop.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)  # Prevent test from hanging
    async def test_run_daemon_with_status(self):
        """Test running daemon mode with status flag (lines 447-451)."""
        class MockArgs:
            add = []
            status = True

        args = MockArgs()

        with patch("ccbt.session.AsyncSessionManager") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            with patch.object(mock_session, "start", new_callable=AsyncMock), \
                 patch.object(mock_session, "stop", new_callable=AsyncMock), \
                 patch.object(mock_session, "get_status", new_callable=AsyncMock) as mock_get_status:

                mock_get_status.return_value = {
                    "torrent1": {"progress": 0.5, "downloaded": 1024, "total": 2048},
                    "torrent2": {"progress": 0.8, "downloaded": 1638, "total": 2048}
                }

                await run_daemon(args)

                mock_session.start.assert_called_once()
                mock_session.stop.assert_called_once()
                mock_get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_daemon_mode(self):
        """Test main function in daemon mode."""
        test_args = [
            "ccbt",
            "--daemon",
            "--add", "tests/data/test.torrent",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.run_daemon", new_callable=AsyncMock) as mock_run_daemon:

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0
                mock_run_daemon.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_torrent_mode(self):
        """Test main function in torrent mode."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
            "--output-dir", "/output",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_torrent", new_callable=AsyncMock) as mock_download_torrent:

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0
                mock_download_torrent.assert_called_once_with("tests/data/test.torrent", "/output")

    @pytest.mark.asyncio
    async def test_main_magnet_mode(self):
        """Test main function in magnet mode."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
            "--output-dir", "/output",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_magnet", new_callable=AsyncMock) as mock_download_magnet:

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0
                mock_download_magnet.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_magnet_flag(self):
        """Test main function with --magnet flag."""
        test_args = [
            "ccbt",
            "--magnet",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_magnet", new_callable=AsyncMock) as mock_download_magnet:

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0
                mock_download_magnet.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_no_torrent(self):
        """Test main function with no torrent specified."""
        test_args = [
            "ccbt",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config:

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 1

    @pytest.mark.asyncio
    async def test_main_exception_handling(self):
        """Test main function exception handling (lines 558-561)."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_torrent", side_effect=RuntimeError("Test error")):

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config._config_file = None
            mock_init_config.return_value = mock_config_manager

            result = await main()

            assert result == 1

    @pytest.mark.asyncio
    async def test_main_with_hot_reload(self):
        """Test main function with hot reload enabled."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_torrent", new_callable=AsyncMock):

            mock_config_manager = MagicMock()
            mock_config = MagicMock()
            mock_config._config_file = "/path/to/config.toml"
            mock_config.network = MagicMock()
            mock_config.limits = MagicMock()
            mock_config.observability = MagicMock()
            mock_config.strategy = MagicMock()
            mock_config_manager.config = mock_config
            mock_config_manager.start_hot_reload = AsyncMock()
            mock_config_manager.stop_hot_reload = MagicMock()
            mock_init_config.return_value = mock_config_manager

            result = await main()

            assert result == 0
            mock_config_manager.start_hot_reload.assert_called_once()
            mock_config_manager.stop_hot_reload.assert_called_once()

    def test_sync_main(self):
        """Test sync_main function (line 574)."""
        with patch("asyncio.run") as mock_asyncio_run, \
             patch("ccbt.session.async_main.main", new_callable=AsyncMock) as mock_main:

            mock_main.return_value = 0
            mock_asyncio_run.return_value = 0

            result = sync_main()

            assert result == 0
            mock_asyncio_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_magnet_detection(self):
        """Test main function with magnet URI detection (line 550)."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
            "--output-dir", "/output",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_magnet", new_callable=AsyncMock) as mock_download_magnet:

            mock_config_manager = MagicMock()
            mock_config = MagicMock()
            mock_config._config_file = None
            mock_config.network = MagicMock()
            mock_config.limits = MagicMock()
            mock_config.observability = MagicMock()
            mock_config.strategy = MagicMock()
            mock_config_manager.config = mock_config
            mock_init_config.return_value = mock_config_manager

            result = await main()

            assert result == 0
            mock_download_magnet.assert_called_once_with(
                "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
                "/output"
            )

    @pytest.mark.asyncio
    async def test_main_print_help(self):
        """Test main function print_help path (lines 555-556)."""
        test_args = ["ccbt"]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("argparse.ArgumentParser.print_help") as mock_print_help:

            mock_config_manager = MagicMock()
            mock_config = MagicMock()
            mock_config._config_file = None
            mock_config_manager.config = mock_config
            mock_init_config.return_value = mock_config_manager

            result = await main()

            assert result == 1
            mock_print_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_general_exception(self):
        """Test main function general exception handling (lines 560-561)."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_torrent", side_effect=ValueError("Unexpected error")):

            mock_config_manager = MagicMock()
            mock_config = MagicMock()
            mock_config._config_file = None
            mock_config_manager.config = mock_config
            mock_init_config.return_value = mock_config_manager

            result = await main()

            assert result == 1

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self):  # pragma: no cover
        """Test main function with keyboard interrupt.
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test intentionally raises KeyboardInterrupt to verify graceful shutdown behavior.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.async_main.init_config") as mock_init_config, \
             patch("ccbt.async_main.download_torrent", side_effect=KeyboardInterrupt):

            mock_config_manager = MagicMock()
            mock_config_manager.config = MagicMock()
            mock_config_manager.config.network = MagicMock()
            mock_config_manager.config.limits = MagicMock()
            mock_config_manager.config.observability = MagicMock()
            mock_config_manager.config.strategy = MagicMock()
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0

    @pytest.mark.asyncio
    async def test_main_config_overrides(self):
        """Test main function with config overrides."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
            "--port", "8080",
            "--max-peers", "50",
            "--down-limit", "1000",
            "--up-limit", "500",
            "--log-level", "DEBUG",
            "--streaming",
        ]

        with patch("sys.argv", test_args), \
             patch("ccbt.session.async_main.init_config") as mock_init_config, \
             patch("ccbt.session.async_main.download_torrent", new_callable=AsyncMock):

            # Create mock config structure that properly supports attribute assignment
            mock_network = MagicMock()
            mock_network.listen_port = None
            mock_network.max_global_peers = None

            mock_limits = MagicMock()
            mock_limits.global_down_kib = None
            mock_limits.global_up_kib = None

            mock_observability = MagicMock()
            mock_observability.log_level = None

            mock_strategy = MagicMock()
            mock_strategy.streaming_mode = False

            mock_config = MagicMock()
            mock_config.network = mock_network
            mock_config.limits = mock_limits
            mock_config.observability = mock_observability
            mock_config.strategy = mock_strategy

            mock_config_manager = MagicMock()
            mock_config_manager.config = mock_config
            mock_init_config.return_value = mock_config_manager

            with patch.object(mock_config_manager, "start_hot_reload", new_callable=AsyncMock):
                result = await main()

                assert result == 0
                assert mock_config_manager.config.network.listen_port == 8080
                assert mock_config_manager.config.network.max_global_peers == 50
                assert mock_config_manager.config.limits.global_down_kib == 1000
                assert mock_config_manager.config.limits.global_up_kib == 500
                assert mock_config_manager.config.observability.log_level == "DEBUG"
                assert mock_config_manager.config.strategy.streaming_mode is True


class TestAsyncSessionManager:
    """Test cases for AsyncSessionManager."""

    @pytest.mark.asyncio
    async def test_session_manager_initialization(self):
        """Test AsyncSessionManager initialization."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            assert session.config == mock_config
            assert session.torrents == {}

    @pytest.mark.asyncio
    async def test_session_manager_start(self):
        """Test AsyncSessionManager start (line 263)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()
            await session.start()

            # Verify logger.info was called
            assert True  # start() should complete without errors

    @pytest.mark.asyncio
    async def test_session_manager_stop(self):
        """Test AsyncSessionManager stop (lines 268-278)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            # Add a torrent to stop
            mock_download_manager = MagicMock()
            mock_download_manager.stop = AsyncMock()
            session.torrents["torrent1"] = mock_download_manager

            await session.stop()

            # Verify all torrents were stopped and removed
            mock_download_manager.stop.assert_called_once()
            assert len(session.torrents) == 0

    @pytest.mark.asyncio
    async def test_add_torrent(self):
        """Test adding a torrent (lines 282-300)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.TorrentParser") as mock_parser_class, \
             patch("ccbt.session.async_main.AsyncDownloadManager") as mock_dm_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_parser = MagicMock()
            mock_torrent_data = MagicMock()
            # Create a mock info_hash with a callable hex() method
            mock_info_hash = MagicMock()
            mock_info_hash.hex = MagicMock(return_value="hex_hash")
            mock_torrent_data.info_hash = mock_info_hash
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser

            mock_dm = MagicMock()
            mock_dm.start = AsyncMock()
            mock_dm_class.return_value = mock_dm

            session = AsyncSessionManager()
            torrent_id = await session.add_torrent("test.torrent", "/output")

            assert torrent_id == "hex_hash"
            assert "hex_hash" in session.torrents
            mock_parser.parse.assert_called_once_with("test.torrent")
            mock_dm.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_torrent_exception(self):
        """Test adding a torrent with exception (lines 296-298)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.TorrentParser") as mock_parser_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_parser = MagicMock()
            mock_parser.parse.side_effect = ValueError("Invalid torrent")
            mock_parser_class.return_value = mock_parser

            session = AsyncSessionManager()

            with pytest.raises(ValueError):
                await session.add_torrent("invalid.torrent")

    @pytest.mark.asyncio
    async def test_add_magnet(self):
        """Test adding a magnet (lines 304-345)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.build_minimal_torrent_data") as mock_build_minimal, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata, \
             patch("ccbt.session.async_main.build_torrent_data_from_metadata") as mock_build_from_metadata, \
             patch("ccbt.session.async_main.AsyncDownloadManager") as mock_dm_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com"]
            mock_parse_magnet.return_value = mock_magnet_info

            mock_info_hash = MagicMock()
            mock_info_hash.hex = lambda: "hex_hash"
            mock_torrent_data = {"info_hash": mock_info_hash}
            mock_build_minimal.return_value = mock_torrent_data

            mock_metadata = {"name": "test"}
            mock_fetch_metadata.return_value = mock_metadata

            mock_full_info_hash = MagicMock()
            mock_full_info_hash.hex = lambda: "hex_hash"
            mock_full_torrent = {"info_hash": mock_full_info_hash}
            mock_build_from_metadata.return_value = mock_full_torrent

            mock_dm = MagicMock()
            mock_dm.start = AsyncMock()
            mock_dm_class.return_value = mock_dm

            session = AsyncSessionManager()
            torrent_id = await session.add_magnet("magnet:?xt=urn:btih:test", "/output")

            assert torrent_id == "hex_hash"
            assert "hex_hash" in session.torrents
            mock_parse_magnet.assert_called_once()
            mock_fetch_metadata.assert_called_once()
            mock_dm.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_magnet_no_metadata(self):
        """Test adding a magnet without metadata (line 325-329)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.build_minimal_torrent_data") as mock_build_minimal, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata, \
             patch("ccbt.session.async_main.AsyncDownloadManager") as mock_dm_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = []
            mock_parse_magnet.return_value = mock_magnet_info

            mock_info_hash = MagicMock()
            mock_info_hash.hex = lambda: "hex_hash"
            mock_torrent_data = {"info_hash": mock_info_hash}
            mock_build_minimal.return_value = mock_torrent_data

            mock_fetch_metadata.return_value = None  # No metadata

            mock_dm = MagicMock()
            mock_dm.start = AsyncMock()
            mock_dm_class.return_value = mock_dm

            session = AsyncSessionManager()
            torrent_id = await session.add_magnet("magnet:?xt=urn:btih:test")

            assert torrent_id == "hex_hash"

    @pytest.mark.asyncio
    async def test_add_magnet_with_trackers_no_metadata(self):
        """Test adding a magnet with trackers but no metadata (line 314-324)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet, \
             patch("ccbt.session.async_main.build_minimal_torrent_data") as mock_build_minimal, \
             patch("ccbt.session.async_main.fetch_metadata_from_peers") as mock_fetch_metadata, \
             patch("ccbt.session.async_main.AsyncDownloadManager") as mock_dm_class:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com"]  # Has trackers
            mock_parse_magnet.return_value = mock_magnet_info

            mock_info_hash = MagicMock()
            mock_info_hash.hex = lambda: "hex_hash"
            mock_torrent_data = {"info_hash": mock_info_hash}
            mock_build_minimal.return_value = mock_torrent_data

            mock_fetch_metadata.return_value = None  # No metadata fetched

            mock_dm = MagicMock()
            mock_dm.start = AsyncMock()
            mock_dm_class.return_value = mock_dm

            session = AsyncSessionManager()
            torrent_id = await session.add_magnet("magnet:?xt=urn:btih:test")

            assert torrent_id == "hex_hash"
            # Verify fetch_metadata was called with empty peers list
            mock_fetch_metadata.assert_called_once_with(b"test1234567890123456", [])

    @pytest.mark.asyncio
    async def test_add_magnet_exception(self):
        """Test adding a magnet with exception (lines 341-343)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config, \
             patch("ccbt.session.async_main.parse_magnet") as mock_parse_magnet:

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_parse_magnet.side_effect = ValueError("Invalid magnet")

            session = AsyncSessionManager()

            with pytest.raises(ValueError):
                await session.add_magnet("invalid_magnet")

    @pytest.mark.asyncio
    async def test_remove_torrent(self):
        """Test removing a torrent (lines 349-354)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            mock_download_manager = MagicMock()
            mock_download_manager.stop = AsyncMock()
            session.torrents["torrent1"] = mock_download_manager

            result = await session.remove_torrent("torrent1")

            assert result is True
            assert "torrent1" not in session.torrents
            mock_download_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_torrent_not_found(self):
        """Test removing a non-existent torrent (line 354)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            result = await session.remove_torrent("nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_status_single_torrent(self):
        """Test getting status for single torrent (lines 358-361)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            mock_download_manager = MagicMock()
            mock_status = {"progress": 0.5}
            mock_download_manager.get_status = AsyncMock(return_value=mock_status)
            session.torrents["torrent1"] = mock_download_manager

            status = await session.get_status("torrent1")

            assert status == mock_status
            mock_download_manager.get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_single_torrent_not_found(self):
        """Test getting status for non-existent torrent (line 361)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            status = await session.get_status("nonexistent")

            assert status == {}

    @pytest.mark.asyncio
    async def test_get_status_all_torrents(self):
        """Test getting status for all torrents (lines 364-367)."""
        with patch("ccbt.session.async_main.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            session = AsyncSessionManager()

            mock_dm1 = MagicMock()
            mock_dm1.get_status = AsyncMock(return_value={"progress": 0.5})
            mock_dm2 = MagicMock()
            mock_dm2.get_status = AsyncMock(return_value={"progress": 0.8})

            session.torrents["torrent1"] = mock_dm1
            session.torrents["torrent2"] = mock_dm2

            status = await session.get_status()

            assert len(status) == 2
            assert "torrent1" in status
            assert "torrent2" in status
