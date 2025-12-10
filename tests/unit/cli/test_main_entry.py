"""Tests for package __main__.py entry point.

Target: 95%+ coverage for ccbt/__main__.py.
"""

import argparse
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestMainEntry:
    """Tests for ccbt/__main__.py."""

    def test_main_with_torrent_file(self):
        """Test main with torrent file."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.torrent.TorrentParser") as mock_parser_class:
                mock_parser_instance = Mock()
                mock_parser_instance.parse.return_value = {
                    "info_hash": b"x" * 20,
                    "announce": "http://tracker.example.com",
                    "pieces_info": {"num_pieces": 1},
                }
                mock_parser_class.return_value = mock_parser_instance

                with patch("ccbt.discovery.tracker.TrackerClient") as mock_tracker_class:
                    mock_tracker_instance = Mock()
                    mock_tracker_instance.announce.return_value = {
                        "status": 200,
                        "peers": [{"ip": "192.168.1.1", "port": 6881}],
                    }
                    mock_tracker_class.return_value = mock_tracker_instance

                    with patch("ccbt.storage.file_assembler.DownloadManager") as mock_dm_class:
                        mock_dm_instance = Mock()
                        mock_dm_instance.download_complete = True
                        mock_dm_instance.get_status.return_value = {
                            "files_exist": {},
                            "file_sizes": {},
                        }
                        mock_dm_class.return_value = mock_dm_instance

                        with patch("time.sleep"):
                            result = main_module.main()

                            assert result == 0

    def test_main_with_magnet_uri(self):
        """Test main with magnet URI."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="magnet:?xt=urn:btih:test",
                port=6881,
                magnet=True,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.magnet.parse_magnet") as mock_parse_magnet:
                mock_magnet_info = Mock()
                mock_magnet_info.info_hash = b"x" * 20
                mock_magnet_info.display_name = "test"
                mock_magnet_info.trackers = []
                mock_parse_magnet.return_value = mock_magnet_info

                with patch("ccbt.core.magnet.build_minimal_torrent_data") as mock_build:
                    mock_build.return_value = {
                        "info_hash": b"x" * 20,
                        "announce": "http://tracker.example.com",
                        "pieces_info": {"num_pieces": 1},
                    }

                    with patch("ccbt.discovery.tracker.TrackerClient") as mock_tracker_class:
                        mock_tracker_instance = Mock()
                        mock_tracker_instance.announce.return_value = {
                            "status": 200,
                            "peers": [],
                        }
                        mock_tracker_class.return_value = mock_tracker_instance

                        with patch("ccbt.storage.file_assembler.DownloadManager") as mock_dm_class:
                            mock_dm_instance = Mock()
                            mock_dm_instance.download_complete = True
                            mock_dm_instance.get_status.return_value = {
                                "files_exist": {},
                                "file_sizes": {},
                            }
                            mock_dm_class.return_value = mock_dm_instance

                            with patch("time.sleep"):
                                result = main_module.main()

                                assert result == 0

    def test_main_daemon_mode_add_torrent(self):
        """Test main in daemon mode adding torrent."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=True,
                add=["test.torrent"],
                status=False,
            )

            with patch("ccbt.session.SessionManager") as mock_session_class:
                mock_session_instance = Mock()
                mock_session_class.return_value = mock_session_instance

                result = main_module.main()

                assert result == 0
                mock_session_instance.add_torrent.assert_called_once_with("test.torrent")

    def test_main_daemon_mode_add_magnet(self):
        """Test main in daemon mode adding magnet."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=True,
                add=["magnet:?xt=urn:btih:test"],
                status=False,
            )

            with patch("ccbt.session.SessionManager") as mock_session_class:
                mock_session_instance = Mock()
                mock_session_class.return_value = mock_session_instance

                result = main_module.main()

                assert result == 0
                mock_session_instance.add_magnet.assert_called_once()

    def test_main_daemon_mode_status(self):
        """Test main in daemon mode with status."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=True,
                add=None,
                status=True,
            )

            with patch("ccbt.session.SessionManager") as mock_session_class:
                mock_session_instance = Mock()
                mock_session_class.return_value = mock_session_instance

                result = main_module.main()

                assert result == 0

    def test_main_daemon_mode_add_exception(self):
        """Test main in daemon mode handling exception on add."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=True,
                add=["invalid.torrent"],
                status=False,
            )

            with patch("ccbt.session.SessionManager") as mock_session_class:
                mock_session_instance = Mock()
                mock_session_instance.add_torrent.side_effect = Exception("Test error")
                mock_session_class.return_value = mock_session_instance

                with patch.object(main_module, "logger") as mock_logger:
                    result = main_module.main()

                    assert result == 0
                    mock_logger.exception.assert_called()

    def test_main_tracker_error_status(self):
        """Test main with tracker error status."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.torrent.TorrentParser") as mock_parser_class:
                mock_parser_instance = Mock()
                mock_parser_instance.parse.return_value = {
                    "info_hash": b"x" * 20,
                    "announce": "http://tracker.example.com",
                    "pieces_info": {"num_pieces": 1},
                }
                mock_parser_class.return_value = mock_parser_instance

                with patch("ccbt.discovery.tracker.TrackerClient") as mock_tracker_class:
                    mock_tracker_instance = Mock()
                    mock_tracker_instance.announce.return_value = {
                        "status": 500,  # Error status
                        "peers": [],
                    }
                    mock_tracker_class.return_value = mock_tracker_instance

                    result = main_module.main()

                    assert result == 1

    def test_main_magnet_with_dht_peers(self):
        """Test main with magnet URI using DHT peer lookup."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="magnet:?xt=urn:btih:test",
                port=6881,
                magnet=True,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.magnet.parse_magnet") as mock_parse_magnet:
                mock_magnet_info = Mock()
                mock_magnet_info.info_hash = b"x" * 20
                mock_magnet_info.display_name = "test"
                mock_magnet_info.trackers = []
                mock_parse_magnet.return_value = mock_magnet_info

                with patch("ccbt.core.magnet.build_minimal_torrent_data") as mock_build:
                    # Return dict without info (triggers DHT lookup)
                    mock_build.return_value = {
                        "info_hash": b"x" * 20,
                        "announce": "http://tracker.example.com",
                    }

                    with patch("ccbt.discovery.tracker.TrackerClient") as mock_tracker_class:
                        mock_tracker_instance = Mock()
                        mock_tracker_instance.announce.return_value = {
                            "status": 200,
                            "peers": [],
                        }
                        mock_tracker_class.return_value = mock_tracker_instance

                        with patch("ccbt.discovery.dht.AsyncDHTClient") as mock_dht_class:
                            mock_dht_instance = Mock()
                            async def mock_get_peers(_info_hash):
                                return [("192.168.1.1", 6881)]
                            mock_dht_instance.get_peers = mock_get_peers
                            mock_dht_instance.start = Mock(return_value=None)
                            mock_dht_instance.stop = Mock(return_value=None)
                            mock_dht_instance.wait_for_bootstrap = Mock(return_value=True)
                            mock_dht_instance.routing_table = MagicMock()
                            mock_dht_instance.routing_table.nodes = {}
                            mock_dht_class.return_value = mock_dht_instance

                            with patch("asyncio.run") as mock_asyncio_run:
                                mock_asyncio_run.return_value = [("192.168.1.1", 6881)]

                                with patch("ccbt.storage.file_assembler.DownloadManager") as mock_dm_class:
                                    mock_dm_instance = Mock()
                                    mock_dm_instance.download_complete = True
                                    mock_dm_instance.get_status.return_value = {
                                        "files_exist": {},
                                        "file_sizes": {},
                                    }
                                    mock_dm_class.return_value = mock_dm_instance

                                    with patch("time.sleep"):
                                        result = main_module.main()

                                        assert result == 0

    def test_main_magnet_with_metadata_fetch(self):
        """Test main with magnet URI fetching metadata."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="magnet:?xt=urn:btih:test",
                port=6881,
                magnet=True,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.magnet.parse_magnet") as mock_parse_magnet:
                mock_magnet_info = Mock()
                mock_magnet_info.info_hash = b"x" * 20
                mock_magnet_info.display_name = "test"
                mock_magnet_info.trackers = []
                mock_parse_magnet.return_value = mock_magnet_info

                with patch("ccbt.core.magnet.build_minimal_torrent_data") as mock_build:
                    # Return dict with missing info (simulates magnet without metadata)
                    mock_build.return_value = {
                        "info_hash": b"x" * 20,
                        "announce": "http://tracker.example.com",
                    }

                    with patch("ccbt.discovery.tracker.TrackerClient") as mock_tracker_class:
                        mock_tracker_instance = Mock()
                        mock_tracker_instance.announce.return_value = {
                            "status": 200,
                            "peers": [{"ip": "192.168.1.1", "port": 6881}],
                        }
                        mock_tracker_class.return_value = mock_tracker_instance

                        with patch("ccbt.piece.metadata_exchange.fetch_metadata_from_peers") as mock_fetch:
                            mock_fetch.return_value = {
                                b"info": {b"name": b"test"},
                                b"announce": b"http://tracker.example.com",
                            }

                            with patch("ccbt.core.magnet.build_torrent_data_from_metadata") as mock_build_meta:
                                mock_build_meta.return_value = {
                                    "info_hash": b"x" * 20,
                                    "announce": "http://tracker.example.com",
                                    "pieces_info": {"num_pieces": 1},
                                }

                                with patch("ccbt.storage.file_assembler.DownloadManager") as mock_dm_class:
                                    mock_dm_instance = Mock()
                                    mock_dm_instance.download_complete = True
                                    mock_dm_instance.get_status.return_value = {
                                        "files_exist": {},
                                        "file_sizes": {},
                                    }
                                    mock_dm_class.return_value = mock_dm_instance

                                    with patch("time.sleep"):
                                        result = main_module.main()

                                        assert result == 0

    def test_main_type_error_on_announce_input(self):
        """Test main handles TypeError on announce input."""
        import ccbt.__main__ as main_module

        with patch.object(main_module, "argparse") as mock_argparse:
            mock_parser = Mock()
            mock_argparse.ArgumentParser.return_value = mock_parser
            mock_parser.parse_args.return_value = argparse.Namespace(
                torrent="test.torrent",
                port=6881,
                magnet=False,
                daemon=False,
                add=None,
                status=False,
            )

            with patch("ccbt.core.torrent.TorrentParser") as mock_parser_class:
                # Return non-dict, non-model_dump object
                mock_parser_instance = Mock()
                mock_parser_instance.parse.return_value = "invalid"
                mock_parser_class.return_value = mock_parser_instance

                with pytest.raises(TypeError, match="Expected dict for announce_input"):
                    main_module.main()
