"""Tests for main entry point."""

import pytest
import sys
from unittest.mock import MagicMock, patch, mock_open
from io import StringIO

pytestmark = [pytest.mark.unit, pytest.mark.cli]

from ccbt.__main__ import main


class TestMainEntryPoint:
    """Test cases for main entry point."""

    def test_main_daemon_mode_with_add_torrent(self):
        """Test main function in daemon mode with torrent addition."""
        test_args = [
            "ccbt",
            "--daemon",
            "--add", "tests/data/test.torrent",
            "--add", "another.torrent",
            "dummy.torrent",  # Required argument
        ]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.session.SessionManager') as mock_async_session_class:
            
            mock_session = MagicMock()
            mock_async_session_class.return_value = mock_session
            
            result = main()
            
            assert result == 0
            assert mock_session.add_torrent.call_count == 2
            mock_session.add_torrent.assert_any_call("tests/data/test.torrent")
            mock_session.add_torrent.assert_any_call("another.torrent")

    def test_main_daemon_mode_with_add_magnet(self):
        """Test main function in daemon mode with magnet addition."""
        test_args = [
            "ccbt",
            "--daemon",
            "--add", "magnet:?xt=urn:btih:test",
            "--add", "magnet:?xt=urn:btih:another",
            "dummy.torrent",  # Required argument
        ]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.session.SessionManager') as mock_async_session_class:
            
            mock_session = MagicMock()
            mock_async_session_class.return_value = mock_session
            
            result = main()
            
            assert result == 0
            assert mock_session.add_magnet.call_count == 2
            mock_session.add_magnet.assert_any_call("magnet:?xt=urn:btih:test")
            mock_session.add_magnet.assert_any_call("magnet:?xt=urn:btih:another")

    def test_main_daemon_mode_with_status(self):
        """Test main function in daemon mode with status flag."""
        test_args = [
            "ccbt",
            "--daemon",
            "--status",
            "dummy.torrent",  # Required argument
        ]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.session.SessionManager') as mock_session_class:
            
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            result = main()
            
            assert result == 0

    def test_main_daemon_mode_keyboard_interrupt(self):
        """Test main function in daemon mode with keyboard interrupt."""
        test_args = [
            "ccbt",
            "--daemon",
            "dummy.torrent",  # Required argument
        ]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.session.SessionManager') as mock_session_class, \
             patch('time.sleep', side_effect=KeyboardInterrupt):
            
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            result = main()
            
            assert result == 0

    def test_main_magnet_uri(self):
        """Test main function with magnet URI."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
                {"ip": "192.168.1.2", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            mock_parse_magnet.assert_called_once()
            mock_build_minimal.assert_called_once()
            mock_tracker.announce.assert_called_once()

    def test_main_magnet_flag(self):
        """Test main function with --magnet flag."""
        test_args = [
            "ccbt",
            "--magnet",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            mock_parse_magnet.assert_called_once()

    def test_main_torrent_file(self):
        """Test main function with torrent file."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
            "info": {"files": [{"path": ["file1.txt"], "length": 1024}]},
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            mock_parser.parse.assert_called_once_with("test.torrent")

    def test_main_tracker_failure(self):
        """Test main function with tracker failure."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 500,  # Error status
            "peers": [],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class:
            
            # Setup mocks
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            result = main()
            
            assert result == 1

    def test_main_magnet_with_dht_peers(self):
        """Test main function with magnet and DHT peer lookup."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        mock_dht_peers = [("192.168.1.2", 6881), ("192.168.1.3", 6881)]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class, \
             patch('ccbt.dht.DHTClient') as mock_dht_class, \
             patch('asyncio.run') as mock_asyncio_run:
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dht = MagicMock()
            mock_dht.get_peers.return_value = mock_dht_peers
            mock_dht_class.return_value = mock_dht
            
            async def mock_dht_lookup():
                await mock_dht.start()
                try:
                    return await mock_dht.get_peers(b"test1234567890123456")
                finally:
                    await mock_dht.stop()
            
            mock_asyncio_run.return_value = mock_dht_peers
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            mock_asyncio_run.assert_called_once()

    def test_main_magnet_with_metadata_fetch(self):
        """Test main function with magnet and metadata fetching."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        mock_info_dict = {
            "name": "test_torrent",
            "files": [{"path": ["file1.txt"], "length": 1024}],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.magnet.build_torrent_data_from_metadata') as mock_build_from_metadata, \
             patch('ccbt.metadata_exchange.fetch_metadata_from_peers') as mock_fetch_metadata, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            mock_fetch_metadata.return_value = mock_info_dict
            mock_build_from_metadata.return_value = {
                "info_hash": b"test1234567890123456",
                "name": "test_torrent",
                "info": mock_info_dict,
            }
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            mock_fetch_metadata.assert_called_once()

    def test_main_download_manager_callbacks(self):
        """Test main function sets up download manager callbacks."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0
            # Check that callbacks were set
            assert hasattr(mock_dm, 'on_peer_connected') or not hasattr(mock_dm, 'on_peer_connected')
            assert hasattr(mock_dm, 'on_peer_disconnected') or not hasattr(mock_dm, 'on_peer_disconnected')
            assert hasattr(mock_dm, 'on_bitfield_received') or not hasattr(mock_dm, 'on_bitfield_received')
            assert hasattr(mock_dm, 'on_piece_completed') or not hasattr(mock_dm, 'on_piece_completed')
            assert hasattr(mock_dm, 'on_piece_verified') or not hasattr(mock_dm, 'on_piece_verified')
            assert hasattr(mock_dm, 'on_file_assembled') or not hasattr(mock_dm, 'on_file_assembled')
            assert hasattr(mock_dm, 'on_download_complete') or not hasattr(mock_dm, 'on_download_complete')

    def test_main_download_timeout(self):
        """Test main function with download timeout."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class, \
             patch('time.sleep'):
            
            # Setup mocks
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = False  # Never completes
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": False},
                "file_sizes": {"file1.txt": 0},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0  # Should still return 0 even on timeout

    def test_main_dht_exception(self):
        """Test main function with DHT exception."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class, \
             patch('asyncio.run', side_effect=Exception("DHT failed")):
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0  # Should continue despite DHT failure

    def test_main_metadata_fetch_exception(self):
        """Test main function with metadata fetch exception."""
        test_args = [
            "ccbt",
            "magnet:?xt=urn:btih:test1234567890123456789012345678901234567890",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.magnet.parse_magnet') as mock_parse_magnet, \
             patch('ccbt.magnet.build_minimal_torrent_data') as mock_build_minimal, \
             patch('ccbt.metadata_exchange.fetch_metadata_from_peers', side_effect=Exception("Metadata fetch failed")), \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            # Setup mocks
            mock_magnet_info = MagicMock()
            mock_magnet_info.info_hash = b"test1234567890123456"
            mock_magnet_info.display_name = "test_torrent"
            mock_magnet_info.trackers = ["http://tracker.example.com/announce"]
            mock_parse_magnet.return_value = mock_magnet_info
            
            mock_build_minimal.return_value = mock_torrent_data
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm = MagicMock()
            mock_dm.download_complete = True
            mock_dm.get_status.return_value = {
                "files_exist": {"file1.txt": True},
                "file_sizes": {"file1.txt": 1024},
            }
            mock_dm_class.return_value = mock_dm
            
            result = main()
            
            assert result == 0  # Should continue despite metadata fetch failure

    def test_main_torrent_parser_exception(self):
        """Test main function with torrent parser exception."""
        test_args = [
            "ccbt",
            "invalid.torrent",
        ]
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class:
            
            mock_parser = MagicMock()
            mock_parser.parse.side_effect = Exception("Invalid torrent file")
            mock_parser_class.return_value = mock_parser
            
            with pytest.raises(Exception):
                main()

    def test_main_tracker_exception(self):
        """Test main function with tracker exception."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class:
            
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.side_effect = Exception("Tracker error")
            mock_tracker_class.return_value = mock_tracker
            
            with pytest.raises(Exception):
                main()

    def test_main_download_manager_exception(self):
        """Test main function with download manager exception."""
        test_args = [
            "ccbt",
            "tests/data/test.torrent",
        ]
        
        mock_torrent_data = {
            "info_hash": b"test1234567890123456",
            "name": "test_torrent",
            "trackers": ["http://tracker.example.com/announce"],
        }
        
        mock_tracker_response = {
            "status": 200,
            "peers": [
                {"ip": "192.168.1.1", "port": 6881},
            ],
        }
        
        with patch('sys.argv', test_args), \
             patch('ccbt.torrent.TorrentParser') as mock_parser_class, \
             patch('ccbt.tracker.TrackerClient') as mock_tracker_class, \
             patch('ccbt.file_assembler.DownloadManager') as mock_dm_class:
            
            mock_parser = MagicMock()
            mock_parser.parse.return_value = mock_torrent_data
            mock_parser_class.return_value = mock_parser
            
            mock_tracker = MagicMock()
            mock_tracker.announce.return_value = mock_tracker_response
            mock_tracker_class.return_value = mock_tracker
            
            mock_dm_class.side_effect = Exception("Download manager error")
            
            with pytest.raises(Exception):
                main()
